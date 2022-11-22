# BBC Sounds HiFi CLI

As outlined [here](https://www.hifiwigwam.com/forum/threads/high-quality-320kbps-streams-for-all-bbc-radio-stations.82711/) - whilst BBC usually broadcasts digitally at 128kbps - higher quality 320kbps streams are also avaulable in m3u8 format.

These m3u8 files can be used to access high quality streams of all BBC radio stations - however don't contain any metadata about the songs being played in the way that BBC Sounds does. So I decided to write a simple CLI which would make use of both.

I was originally planning to use beautiful soup to scrape the data from the HTML - however found that there was additional metadata hidden in the JavaScript, so wrote a horrible function to find it.

One complication was that BBC Sounds only shows live metadata for users who are logged in so (otherwise it lags a minute or two behind). This script will work fine without any credentials - though for totally up to date metadata a valid email & password for your a BBC account should be set via the `BBC_SOUNDS_EMAIL` & `BBC_SOUNDS_PASSWORD` env vars.

(Warning - this code is 🗑 - I don't write code like this for work 😄)

### Install dependencies

```
brew install mpv
pip3 install mpv python-mpv
```
### Usage
```
❱  r --help
usage: radio.py [-h] [-v] [-s] [station]

CLI to play BBC Radio Staions in 320kbs

positional arguments:
  station        The station you want to play [1, 1x, 2, 3, 4, 5, 6]

options:
  -h, --help     show this help message and exit
  -v, --verbose  show additional metadata for the previous tracks
  -s, --static   prevent ticker animation
```

![radio-demo](https://user-images.githubusercontent.com/47319147/202790338-847c1321-4898-4a62-bca6-77317bedca92.gif)
