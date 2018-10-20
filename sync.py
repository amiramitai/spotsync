''' subscription list '''

import os
import pprint
import sys
import pickle
import time
import json

from datetime import datetime

import spotipy
import spotipy.util as util


CACHE_TRACKS_FILENAME = '.cache-tracks'
DAY_FRAME = 60  # how many days to look back


try:
    settings = json.load(open('settings.json', 'r'))
except:
    settings = {}
    settings['SPOTIPY_CLIENT_ID'] = input('App Client ID: ')
    settings['SPOTIPY_CLIENT_SECRET'] = input('App Client Secret: ')
    settings['SPOTIPY_REDIRECT_URI'] = input('App redirect URI: ')
    settings['SPOTIPY_USERNAME'] = input('Username: ')
    json.dump(settings, open('settings.json', 'w'))

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


def get_tracks(sp, days_old=DAY_FRAME):
    ''' retrieves tracks from the given days frame '''
    ret = []
    # sp.trace = False
    response = sp.current_user_followed_artists()
    while response:
        artists = response['artists']
        for item in artists['items']:
            artists_name_printed = False
            # tts = sp.artist_top_tracks(item['id'])
            tts = auto_retry(sp.artist_top_tracks, item['id'])
            if not tts:
                continue

            for track in tts['tracks']:
                album = track['album']
                arelease_date = get_date(album['release_date'])
                if (datetime.now() - arelease_date).days > days_old:
                    continue

                if not artists_name_printed:
                    print(item['name'])
                    artists_name_printed = True

                ret.append(track['id'])
                print('   ', track['name'])

        if artists['next']:
            response = sp.next(artists)
        else:
            response = None
    return ret


def main():
    ''' main sync '''
    sp = spotipy.Spotify(auth=token)
    tracks = get_tracks(sp)
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
    pl = sp.user_playlist_create(cid, pl_name)
    sp.user_playlist_add_tracks(cid, pl['id'], new_tracks)

    print('[+] Caching %d newly found tracks' % (len(new_tracks)))
    pickle.dump(synced_tracks + new_tracks, open(CACHE_TRACKS_FILENAME, 'wb'))


if __name__ == '__main__':
    main()