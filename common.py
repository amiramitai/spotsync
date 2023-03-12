import json
import os
import spotipy
import spotipy.util as util
import time

CACHE_TRACKS_FILENAME = '.cache-tracks'
CACHE_PL_FILENAME = '.cache-playlists'
CACHE_LIKES_FILENAME = '.cache-likes'
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

scope = 'playlist-modify-public,user-follow-read,user-library-modify,user-library-read'
# scope = 'playlist-modify-public,user-follow-read'
# scope = 'playlist-modify-public,user-follow-read'
token = util.prompt_for_user_token(settings['SPOTIPY_USERNAME'], scope)

if not token:
    raise RuntimeError('no token')
