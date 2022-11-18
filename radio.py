# !/usr/bin/python
import os, sys, mpv, time, json, curses, requests, argparse, traceback, multiprocessing

default_station = os.environ.get('BBC_SOUNDS_DEFAULT_STATION', '6')
parser = argparse.ArgumentParser(description="CLI to play BBC Radio Staions in 320kbs")
parser.add_argument('station', help='The station you want to play [1, 1x, 2, 3, 4, 5, 6]', nargs='?', default=default_station)
parser.add_argument('-v', '--verbose', help='show additional metadata for the previous tracks', action='store_true', default=False)
parser.add_argument('-s', '--static', help='prevent ticker animation', action='store_true', default=False)
args = parser.parse_args()

url_suffixes = ['1xtra', 'radio_one', 'radio_two', 'radio_three', 'radio_fourfm', 'radio_five_live', '6music']
station_suffix = "1xtra" if args.station == "1x" else url_suffixes[int(args.station or default_station)]
stream_url = f'http://a.files.bbci.co.uk/media/live/manifesto/audio/simulcast/hls/uk/sbr_high/ak/bbc_{station_suffix}.m3u8'
metadata_url = f'https://www.bbc.co.uk/sounds/play/live:bbc_{station_suffix}'
player = mpv.MPV(ytdl=True, input_default_bindings=True, input_vo_keyboard=True)

def stream_station():
  player.play(stream_url)
  player.wait_for_playback()

def find_hidden_json_metadata(html):
  start = 'window.__PRELOADED_STATE__ = '; end = '};'
  j = html[html.find(start) + len(start):]; j = j[:j.find(end)];
  data = json.loads(j + '}')
  return data["modules"]["data"]

def sign_in():
  session = requests.Session()
  signin_url = session.get('https://account.bbc.com/signin').url
  payload = { 'username': os.environ.get('BBC_SOUNDS_EMAIL', ''), 'password': os.environ.get('BBC_SOUNDS_PASSWORD', ''), 'attempts': '0', 'jsEnabled': 'false' }
  session.post(signin_url, data=payload)
  return session

def ticker(ticker_text, sleep_time=5):
  if args.static == True:
    print("\033[K\033[F\033[K" + ticker_text, end="\n\r")
  else:
    window = curses.initscr()
    width = window.getmaxyx()[1]
    for i in range(width):
      space = " " * (width - i)
      time.sleep(0.1)
      print("\033[K" + space + ticker_text[0:i], end='\r')
  time.sleep(sleep_time)

def print_verbose_track_data(root_data, station=station_suffix.title().replace('_', ' '), show='🔥', secondary_title=None, description=None):
  os.system('cls' if os.name == 'nt' else 'clear')
  all_track_data = [x for x in root_data if x["title"]=="Recent Tracks"][0]["data"]
  print(f"\r{station} - {show} ({secondary_title})", "\r")
  print(description, "\n") if description else print("\n")
  for track_data in reversed(all_track_data):
    artist = track_data["titles"]["primary"]
    song = track_data["titles"]["secondary"]
    time_played = track_data["offset"]["label"]
    print("\033[K" + f'\r{time_played}: "{song}" by {artist}\r')
  time.sleep(5)

def refresh_bbc_sounds_metadata(session):
  while True:
    try:
      root_data = find_hidden_json_metadata(session.get(metadata_url).text)
      latest_track_data = [x for x in root_data if x["title"]=="Recent Tracks"][0]["data"][0] or []
      station_info = [x for x in root_data if x["title"]=="Player"][0]["data"][0] or []
      if station_info:
        station = station_info["network"]["short_title"]
        show = station_info["titles"]["primary"]
        secondary_title = station_info["titles"]["secondary"]
        description = station_info["synopses"]["short"]
        info = f'{show} on {station}'
      if latest_track_data:
        artist = latest_track_data["titles"]["primary"]
        song = latest_track_data["titles"]["secondary"]
        time_played = latest_track_data["offset"]["label"]
        info = f'{time_played}: "{song}" by {artist} on {station} ({show})'
    except KeyError:
      ticker("Looking for BBC metadata... 📻")
      continue
    except requests.exceptions.ConnectionError:
      ticker("Reconnecting... 📻")
      session = sign_in()
      continue
    if (os.environ.get('BBC_SOUNDS_ALWAYS_VERBOSE', args.verbose)):
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
    print("\rByeee! 👋\r")
  except:
    print("\nUh oh! 🚧", sys.exc_info())
    print("🚧", traceback.print_exc())
