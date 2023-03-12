''' subscription list '''

import os
import pprint
import sys
import pickle
import time
import json
import glob

from datetime import datetime
from multiprocessing.pool import ThreadPool


from common import *
from playlist import get_playlist_tracks_cache_aware

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

@retry
def get_new_likes(sp, cur_likes=[]):
    offset = 0
    it = sp.current_user_saved_tracks()
    new_likes = []
    print('[+] caching liked songs..')
    while it['next']:
        ptotal = it['total']
        for r in it['items']:
            tid = r['track']['id']
            if tid in cur_likes:
                print('[+] no more liked songs')
                # break if we've reached our last liked songs
                return new_likes
            new_likes.append(tid)
            offset += 1
        it = sp.next(it)
    if it.get('items'):
        new_likes.extend([r['track']['id'] for r in it['items']])
    return new_likes

def main():
    ''' main sync '''
    sp = spotipy.Spotify(auth=token)
    # import bpdb; bpdb.set_trace()

    try:
        liked_tracks = pickle.load(open(CACHE_LIKES_FILENAME, 'rb'))
    except:
        print('[!] No liked trackes to load..')
        liked_tracks = []
    
    new_likes = get_new_likes(sp, liked_tracks)
    if new_likes:
        print('[+] %d new likes' % len(new_likes))
        liked_tracks.extend(new_likes)
        pickle.dump(liked_tracks, open(CACHE_LIKES_FILENAME, 'wb'))

    disliked = []
    if len(sys.argv) == 3:
        dislike_list_id = sys.argv[2]
        print("[+] getting disliked songs from:", dislike_list_id)
        disliked = get_playlist_tracks_cache_aware(sp, dislike_list_id)
        print('[+] got %d disliked songs..' % len(disliked))

    playlist_id = sys.argv[1].split('playlist/')[1].split("?")[0]
    it = sp.user_playlist(0, playlist_id)['tracks']
    tracks = [a['track']['id'] for a in it['items']]
    pls = []
    print('[+] processing...')
    def handle_json(l):
        path = os.path.join('playlists_cache', l)
        pltracks = json.loads(open(path, 'r').read())
        matches = 0
        for t in tracks:
            if t in disliked:
                print('[+] dislike detected.. PUNISH!')
                # matches -= 1
            elif t in pltracks:
                matches += 1
                # print('[+] like detected.. matches++')
        pls.append((l, matches))
            
    with ThreadPool(8) as pool:
        pool.map(handle_json, os.listdir('playlists_cache/'))

    print('[+] 0. %d pls' % len(pls))
    above_thresh = list(filter(lambda x: x[1] > 3, pls))
    print('[+] 0. %d above thresh' % len(above_thresh))
    matches = {}
    for l, m in above_thresh:
        path = os.path.join('playlists_cache', l)
        pltracks = json.loads(open(path, 'r').read())
        for t in pltracks:
            if t in tracks:
                # only new songs
                continue
            if t not in matches:
                matches[t] = 0
            matches[t] += 1
        
    print('[+] 1. %d matches' % len(matches))
    s = sorted(matches.items(), key=lambda x: x[1], reverse=True)
    print('[+] 2. %d s' % len(s))
    s = list(filter(lambda x: x[0] is not None, s))
    print('[+] 3. %d s' % len(s))

    cuser = sp.current_user()
    cid = cuser['id']
    pl_name = f'based on: {playlist_id}'
    def divide_chunks(l, n):        
        # looping till length l
        for i in range(0, len(l), n):
            yield l[i:i + n]
    tracks = []
    for a in s:
        t = sp.track(a[0])['id']
        if t in liked_tracks:
            print('[+] skipping liked track:', t)
            continue
        if t in disliked:
            print('[+] skipping disliked track:', t)
            continue
        tracks.append(t)
        if len(tracks) >= 100:
            break
    print('[+] 5. %d tracks' % len(s))
    if len(tracks) == 0:
        print('[!] no tracks found')
        return
    pl = sp.user_playlist_create(cid, pl_name)
    sp.user_playlist_add_tracks(cid, pl['id'], tracks)
        


if __name__ == '__main__':
    main()