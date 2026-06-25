#!/usr/bin/env python3
import os, sys, re, time, json, curses, requests, argparse, traceback, multiprocessing

try:
  import mpv
except OSError:
  # ctypes.util.find_library doesn't search Homebrew paths on macOS; patch and retry
  import ctypes.util
  _orig = ctypes.util.find_library
  ctypes.util.find_library = lambda n: next(
    (p for p in ['/opt/homebrew/lib/libmpv.dylib', '/usr/local/lib/libmpv.dylib']
     if n == 'mpv' and os.path.exists(p)),
    _orig(n)
  )
  import mpv
  ctypes.util.find_library = _orig

default_station = os.environ.get('BBC_SOUNDS_DEFAULT_STATION', '6')
parser = argparse.ArgumentParser(description='CLI to play BBC Radio Stations in 320kbps')
parser.add_argument('station', help='Station to play [1, 1x, 2, 3, 4, 5, 6]', nargs='?', default=default_station)
parser.add_argument('-v', '--verbose', help='show additional metadata for the previous tracks', action='store_true')
parser.add_argument('-s', '--static', help='prevent ticker animation', action='store_true')
args = parser.parse_args()

url_suffixes = ['1xtra', 'radio_one', 'radio_two', 'radio_three', 'radio_fourfm', 'radio_five_live', '6music']
station_suffix = '1xtra' if args.station == '1x' else url_suffixes[int(args.station or default_station)]

# BBC retired the old manifesto HLS URLs in 2025; stations now use per-station Akamai pool IDs
_ak = 'http://as-hls-ww-live.akamaized.net/pool_{p}/live/ww/bbc_{s}/bbc_{s}.isml/bbc_{s}-audio=320000.norewind.m3u8'
STREAM_URLS = {
  '1xtra':           _ak.format(p='92079267', s='1xtra'),
  'radio_one':       'http://a.files.bbci.co.uk/ms6/live/3441A116-B12E-4D2F-ACA8-C1984642FA4B/audio/simulcast/hls/nonuk/pc_hd_abr_v2/ak/bbc_radio_one.m3u8',
  'radio_two':       _ak.format(p='74208725', s='radio_two'),
  'radio_three':     _ak.format(p='23461179', s='radio_three'),
  'radio_fourfm':    _ak.format(p='55057080', s='radio_fourfm'),
  'radio_five_live': _ak.format(p='89021708', s='radio_five_live'),
  '6music':          _ak.format(p='81827798', s='6music'),
}
stream_url = STREAM_URLS[station_suffix]
metadata_url = f'https://www.bbc.co.uk/sounds/play/live:bbc_{station_suffix}'
segments_url = f'https://rms.api.bbc.co.uk/v2/services/bbc_{station_suffix}/segments/latest'
player = mpv.MPV(ytdl=True, input_default_bindings=True, input_vo_keyboard=True)

def stream_station():
  player.play(stream_url)
  player.wait_for_playback()

def find_hidden_json_metadata(html):
  script = re.search(r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>', html, re.DOTALL)
  if not script:
    raise ValueError('No application/json script block found in page')
  data = json.loads(script.group(1))
  queries = data['props']['pageProps']['dehydratedState']['queries']
  for q in queries:
    state_data = q.get('state', {}).get('data', {})
    if 'ExperienceResponse' in state_data.get('$schema', ''):
      return state_data['data']
  raise ValueError('ExperienceResponse query not found in page data')

def sign_in():
  session = requests.Session()
  session.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'})

  # Step 1: submit username to get the password page
  r = session.get('https://account.bbc.com/signin')
  action = re.search(r'<form[^>]+action=["\'](.*?)["\']', r.text).group(1).replace('&amp;', '&')
  r2 = session.post('https://account.bbc.com' + action,
    data={'username': os.environ.get('BBC_SOUNDS_EMAIL', '')})

  # Step 2: submit password (with any hidden fields the form carries)
  pass_action = re.search(r'<form[^>]+action=["\'](.*?)["\']', r2.text).group(1).replace('&amp;', '&')
  hidden = dict(re.findall(r'<input[^>]+type=["\']hidden["\'][^>]+name=["\'](.*?)["\']\s+value=["\'](.*?)["\']', r2.text))
  session.post('https://account.bbc.com' + pass_action,
    data={**hidden,
          'username': os.environ.get('BBC_SOUNDS_EMAIL', ''),
          'password': os.environ.get('BBC_SOUNDS_PASSWORD', '')},
    allow_redirects=True)

  return session

def ticker(ticker_text, sleep_time=5):
  if args.static:
    print('\033[K\033[F\033[K' + ticker_text, end='\n\r')
  else:
    window = curses.initscr()
    width = window.getmaxyx()[1]
    for i in range(width):
      space = ' ' * (width - i)
      time.sleep(0.1)
      print('\033[K' + space + ticker_text[0:i], end='\r')
  time.sleep(sleep_time)

def print_verbose_track_data(root_data, station=station_suffix.title().replace('_', ' '), show='🔥', secondary_title=None, description=None):
  os.system('cls' if os.name == 'nt' else 'clear')
  all_track_data = [x for x in root_data if x['title'] == 'Recent Tracks'][0]['data']
  print(f'\r{station} - {show} ({secondary_title})', '\r')
  print(description, '\n') if description else print('\n')
  for track_data in reversed(all_track_data):
    artist = track_data['titles']['primary']
    song = track_data['titles']['secondary']
    time_played = track_data['offset']['label']
    print('\033[K' + f'\r{time_played}: "{song}" by {artist}\r')
  time.sleep(5)

def refresh_bbc_sounds_metadata(session):
  # Show/station info changes hourly at most; fetch from page and cache it
  station = station_suffix.replace('_', ' ').title()
  show = secondary_title = description = ''
  root_data = None
  tick = 0

  while True:
    try:
      # Refresh show/station info from the page every 2 minutes (24 × ~5s ticks)
      if tick % 24 == 0:
        root_data = find_hidden_json_metadata(session.get(metadata_url).text)
        station_info = [x for x in root_data if x['title'] == 'Player'][0]['data'][0]
        station = station_info['network']['short_title']
        show = station_info['titles']['primary']
        secondary_title = station_info['titles']['secondary']
        description = (station_info.get('synopses') or {}).get('short', '')

      # Real-time track data from the lightweight RMS segments API
      # Segments are ordered most-recent first; index 0 is always the current track
      segments = session.get(segments_url).json().get('data', [])
      if segments:
        latest = segments[0]
        artist = latest['titles']['primary']
        song = latest['titles']['secondary']
        time_played = latest['offset']['label']
        info = f'{time_played}: "{song}" by {artist} on {station} ({show})'
      else:
        info = f'{show} on {station}'

    except KeyError:
      ticker('Looking for BBC metadata... 📻')
      continue
    except requests.exceptions.ConnectionError:
      ticker('Reconnecting... 📻')
      session = sign_in()
      continue

    tick += 1
    if os.environ.get('BBC_SOUNDS_ALWAYS_VERBOSE', args.verbose):
      print_verbose_track_data(root_data, station, show, secondary_title, description)
    else:
      ticker(info)

if __name__ == '__main__':
  process = multiprocessing.Process(target=refresh_bbc_sounds_metadata, args=(sign_in(),))
  try:
    print(' Connecting...', end='\r')
    process.start()
    stream_station()
  except KeyboardInterrupt:
    process.join()
    process.terminate()
    os.system('cls' if os.name == 'nt' else 'clear')
    print('\rByeee! 👋\r')
  except:
    print('\nUh oh! 🚧', sys.exc_info())
    print('🚧', traceback.print_exc())
