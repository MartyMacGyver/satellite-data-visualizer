# Satellite Data Visualizer for Python

A Python 3.6+ tool for visualizing satellite positions from using TLE (two-line element set) formatted data using matplotlib and your choice of graphical backends (Tcl/Tk by default).

![Sample screenshot](/docs/screenshot.jpg?raw=true)

More about TLE data at https://en.wikipedia.org/wiki/Two-line_element_set

Note: This is developed and tested using Python 3.6 on Windows and cross-tested using Python 3.6 on OS X, but as long as the same libraries are available in your OS this should work there as well.

## Installation

Install Python 3.6 or later

Optional: [use `venv` to create a workspace](https://docs.python.org/3/library/venv.html) (it's a nice, clean way to manage application-specific dependencies)

Install requirements: `pip install -U -r requirements.txt`

Select a backend: This application initially uses the Tcl/Tk ('TkAgg') backend that's available on most systems by default, but I've successfully used the Qt5 ('Qt5Agg') and wxPython ('WxAgg') backends instead. You can change this in `config.ini`. Additional requirements as follows:

 * Qt5Agg: `pip install -U pyqt5`
 * WxAgg: `pip install -U wxpython`

OS X note: If you see `"urllib.error.URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"`, this is [a known issue](https://stackoverflow.com/a/42098127/760905). To fix it:

  - Open the Finder
  - Go to `Applications` -> `Python 3.7` (or later)
  - Run `Install Certificates.command`

## Usage

For geocoding data (converting an address to coordinates and elevation), you'll need [a Google Geocoding API key](https://developers.google.com/maps/documentation/geocoding/get-api-key). There appears to be [a generous monthly credit](https://cloud.google.com/maps-platform/pricing/) that negates the marginal cost of this. Enter the key when prompted, or set it in your environment (e.g., `export GOOGLE_API_KEY=[secret_key]` in Linux/OSX or `set GOOGLE_API_KEY=[secret_key]` in Windows) before running the app.

Reminder: you can always just enter your coordinates (and optional elevation) directly to avoid this.

Run: `satellite-data-visualizer.py`

Enter a location (in quotes on the command line, or at the prompt):
  - H:M:S coordinates (specify N/S and E/W, or use -/+ degrees relative to N,E)
  - Decimal coordinates (-/+ degrees relative to N,E)
    - Elevation is optional with coordinate entries (default is 0.0m)
  - or a place name, e.g., "Seattle"
    - Elevation is automatically looked up for place name entries

Interesting locations (elevations for coordinate pairs are up to the user):
  - 90:00:00.0N,   0:00:00.0W = Geographic North Pole
  - 90:00:00.0S,   0:00:00.0E = Geographic South Pole
  - 86:17:24.0N, 160:03:36.0W = North Magnetic Pole (2015)
  - 64:31:48.0S, 137:51:36.0E = South Magnetic Pole (2015)
  - 80:30:00.0N,  72:48:00.0W = North Geomagnetic Pole (2017)
  - 80:30:00.0S, 107:12:00.0E = South Geomagnetic Pole (2017)
  - 00:00:00.0N, xxx:xx:xx.xE = Longitudes along the equator
  - "Pontianak, Indonesia" and "Quito, Ecuador" are places right on the equator

## Credits:

This project is a fork of the code provided on Reddit by /u/chknoodle_aggie in the thread https://www.reddit.com/r/Python/comments/3gwzjr/using_pyephem_i_just_plotted_every_tleinfo/

This project also includes elements of the Python 3 port of this code by pklaus as published at https://gist.github.com/pklaus/469e603b105905170992

Some TLE data is sourced from http://www.tle.info/ - this site appears to be IPv6-only now so if you have problems downloading from there be sure you are using an IPv6-capable connection.
