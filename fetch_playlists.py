''' subscription list '''

import os
import pprint
import sys
import pickle
import time
import json

from datetime import datetime
from multiprocessing.pool import ThreadPool

import spotipy
import spotipy.util as util


CACHE_TRACKS_FILENAME = '.cache-tracks'
CACHE_PL_FILENAME = '.cache-playlists'
DAY_FRAME = 60  # how many days to look back



def retry(func):
    def wrapper(*args, **kwargs):
        for i in range(5):
            try:
                return func(*args, **kwargs)
            except:
                # import traceback
                # traceback.print_exc()
                print('[+] sleeping: %d seconds' % (2.0 ** i))
                time.sleep(2.0 ** i)
    return wrapper

try:
    settings = json.load(open('settings.json', 'r'))
except:
    settings = {}
    settings['SPOTIPY_CLIENT_ID'] = input('App Client ID: ')
    settings['SPOTIPY_CLIENT_SECRET'] = input('App Client Secret: ')
    settings['SPOTIPY_REDIRECT_URI'] = input('App redirect URI: ')
    settings['SPOTIPY_USERNAME'] = input('Username: ')
    json.dump(settings, open('settings.json', 'w'))

if 'CACHE_TRACKS_FILENAME' in settings:
    custom_cache_path = settings['CACHE_TRACKS_FILENAME']
    print('[+] using custom cache path:', custom_cache_path)
    CACHE_TRACKS_FILENAME = custom_cache_path

os.environ.update(settings)

scope = 'playlist-modify-public,user-follow-read'
token = util.prompt_for_user_token(settings['SPOTIPY_USERNAME'], scope)

if not token:
    raise RuntimeError('no token')


def get_date(spot_date):
    ''' returns date '''
    if spot_date.count('-') == 2:
        return datetime.strptime(spot_date, '%Y-%m-%d')

    if spot_date.count('-') == 1:
        return datetime.strptime(spot_date, '%Y-%m')

    n = datetime.now()
    return datetime(int(spot_date), n.month, n.day)


def auto_retry(func, *args):
    ''' auto retries a given function + args '''
    for i in range(5):
        try:
            if i > 0:
                print('retrying..')
            return func(*args)
        except:
            time.sleep(2.0)


def get_tracks_from_artist(sp, artist, days_old=DAY_FRAME):
    ret = []
    artists_name_printed = False
    # tts = sp.artist_top_tracks(item['id'])
    tts = auto_retry(sp.artist_top_tracks, artist['id'])
    if not tts:
        return ret

    for track in tts['tracks']:
        album = track['album']
        arelease_date = get_date(album['release_date'])
        if (datetime.now() - arelease_date).days > days_old:
            continue

        if not artists_name_printed:
            print(artist['name'])
            artists_name_printed = True

        ret.append(track['id'])
        print('   ', track['name'])

    return ret


def get_tracks(sp, days_old=DAY_FRAME):
    ''' retrieves tracks from the given days frame '''
    ret = []
    # sp.trace = False
    response = sp.current_user_followed_artists()
    while response:
        artists = response['artists']
        with ThreadPool(8) as pool:
            artists_tracks = pool.map(lambda artist: get_tracks_from_artist(sp, artist, days_old), artists['items'])
            map(ret.extend, artists_tracks)
        # for artist in artists['items']:
        #     ret.extend()

        if artists['next']:
            response = sp.next(artists)
        else:
            response = None
    return ret

@retry
def get_playlists(sp, query, total=60):
    offset = 0
    it = sp.search(query, limit=20, offset=offset, type="playlist")['playlists']
    a = it['next']    
    while it['next']:
        ptotal = it['total']
        for r in it['items']:
            yield r
            offset += 1
            # import bpdb; bpdb.set_trace()
            if offset >= total or offset >= ptotal:
                return
        it = sp.next(it)['playlists']

def main():
    ''' main sync '''
    sp = spotipy.Spotify(auth=token)
    try:
        playlists_map = pickle.load(open(CACHE_PL_FILENAME, 'rb'))
    except:
        print('[!] No synced trackes to load')
        playlists_map = {}
    # queries = [
    #     'psytrance',
    #     'psy trance',
    #     'psychedelic trance',
    #     'full on trance',
    #     'progressive trance',
    #     'hi tech trance',
    #     'hitech trance',
    #     'dark trance',
    #     'dark psy',
    #     'psydark',
    #     'psycore',
    # ]
    queries = sys.argv[1:]

    os.makedirs('playlists_cache', exist_ok=True)

    def normalize_pl(pl):
        if 'total' in pl:
            pass
        return pl

    pindex = 0
    total_songs = [0]
    @retry
    def handle_playlist(args):
        pindex, pl = args
        oid = pl['owner']['id']
        pid = pl['id']
        path = os.path.join('playlists_cache', '%s.json' % (pid))
        if pid in playlists_map or os.path.exists(path):
            print('[+] %4d. already cached: %s' % (total_songs[0], pl['name']))
            return
        print('[+] %4d. caching: %s' % (total_songs[0], pl['name']))
        it = sp.user_playlist_tracks(oid, pid)
        tracks = []
        while it['next']:
            tracks.extend([t['track']['id'] for t in it['items']])
            it = sp.next(it)
        total_songs[0] += len(tracks)
        playlists_map[pid] = tracks
        open(path, 'w').write(json.dumps(tracks, indent=4))
    
    with ThreadPool(32) as pool:
        for q in queries:
            try:
                print('[+] Total Songs: %d' % total_songs[0])
                print('[+] Query: %s' % q)
                pool.map(handle_playlist, enumerate(get_playlists(sp, q, 1000)))
                # pickle.dump(playlists_map, open(CACHE_PL_FILENAME, 'wb'))
            except:
                raise
                continue
    
    pickle.dump(playlists_map, open(CACHE_PL_FILENAME, 'wb'))
        
    # import bpdb; bpdb.set_trace()

    return
    print('-----------------------------')
    try:
        synced_tracks = pickle.load(open(CACHE_TRACKS_FILENAME, 'rb'))
    except:
        print('[!] No synced trackes to load')
        synced_tracks = []
    new_tracks = [t for t in tracks if t not in synced_tracks]

    if not new_tracks:
        print('[+] Did not found any new tracks. bye!')
        return

    cuser = sp.current_user()
    cid = cuser['id']
    pl_name = datetime.now().strftime('Subs%Y%m%d%H%M%S')
    # pl = sp.user_playlist_create(cid, pl_name)
    sp.user_playlist_add_tracks(cid, pl['id'], new_tracks)

    print('[+] Caching %d newly found tracks' % (len(new_tracks)))
    pickle.dump(synced_tracks + new_tracks, open(CACHE_TRACKS_FILENAME, 'wb'))


if __name__ == '__main__':
    main()