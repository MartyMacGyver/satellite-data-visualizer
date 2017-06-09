# Satellite Data Visualizer for Python

A Python 3.4+ tool for visualizing satellite positions from using TLE (two-line element set) formatted data using matplotlib and your choice of graphical backends (Tcl/Tk by default).

While this currently works with Python 2.7, future support for this project with Python 2 is being deprecated.

![Sample screenshot](/docs/screenshot.jpg?raw=true)

More about TLE data at https://en.wikipedia.org/wiki/Two-line_element_set

Note: This is developed and tested using Python 3.6 on Windows and cross-tested using Python 3.6 on OS X, but as long as the same libraries are available in your OS this should work there as well.

## Usage

(See the installaton section for how to install)

run: `satellite-data-visualizer.py` or `python3 satellite-data-visualizer.py`

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

## Installation

This application initially uses the Tcl/Tk ('TkAgg') backend that's available on most systems by default, but I've successfully used the Qt5 ('Qt5Agg') and wxPython ('WxAgg') backends instead. You can change this in `config.ini`.

Use `virtualenv` to keep a clean development environment!

Install Python (I favor Python 3.6+), and then `pip install` the following dependencies:
  - ephem
  - numpy
  - configobj
  - matplotlib *(includes pytz, six, cycler, pyparsing, python-dateutil)*
  - geocoder *(includes idna, chardet, certifi, urllib3, requests, click, decorator, ratelim)*

OS X: if you see `"urllib.error.URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"`

  - Open the Finder
  - Go to `Applications` -> `Python 3.6`
  - run `Install Certificates.command`
  
(This is a known issue per https://stackoverflow.com/a/42098127/760905)

## Credits:

This project is a fork of the code provided on Reddit by /u/chknoodle_aggie in the thread https://www.reddit.com/r/Python/comments/3gwzjr/using_pyephem_i_just_plotted_every_tleinfo/

This project also includes elements of the Python 3 port of this code by pklaus as published at https://gist.github.com/pklaus/469e603b105905170992

Some TLE data is sourced from http://www.tle.info/ - this site appears to be IPv6-only now. Try browsing to their page - if it doesn't load unless you use IPv6 then that may be a permanent change by them.
