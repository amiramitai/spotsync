''' subscription list '''

import os
import pprint
import sys
import pickle
import time
import json

from datetime import datetime
from multiprocessing.pool import ThreadPool

from common import token, retry
from playlist import cache_playlist, get_playlist_tracks, search_playlists

import spotipy
import spotipy.util as util


CACHE_TRACKS_FILENAME = '.cache-tracks'
CACHE_PL_FILENAME = '.cache-playlists'
DAY_FRAME = 60  # how many days to look back
def main():
    ''' main sync '''
    sp = spotipy.Spotify(auth=token)
    try:
        playlists_map = pickle.load(open(CACHE_PL_FILENAME, 'rb'))
    except:
        print('[!] No synced trackes to load')
        playlists_map = {}

    queries = sys.argv[1:]

    os.makedirs('playlists_cache', exist_ok=True)
    total_songs = [0]
    def handle_playlist_result(pl_id):
        path = os.path.join('playlists_cache', '%s.json' % (pl_id))
        if pl_id in playlists_map or os.path.exists(path):
            print('[+] %4d. already cached: %s' % (total_songs[0], pl_id))
            return 
        tracks = get_playlist_tracks(sp, pl_id)
        playlists_map[pl_id] = tracks
        cache_playlist(pl_id, tracks)
    
    with ThreadPool(32) as pool:
        for q in queries:
            try:
                pool.map(handle_playlist_result, search_playlists(sp, q, 1000))
            except:
                raise
    
    pickle.dump(playlists_map, open(CACHE_PL_FILENAME, 'wb'))


if __name__ == '__main__':
    main()