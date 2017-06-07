# Satellite Data Visualizer for Python

A Python 2.7+/3.4+ tool for visualizing satellite positions from using TLE (two-line element set) formatted data using matplotlib

![Sample screenshot](/docs/screenshot.jpg?raw=true)

This project is a fork of the code provided on Reddit by /u/chknoodle_aggie in the thread https://www.reddit.com/r/Python/comments/3gwzjr/using_pyephem_i_just_plotted_every_tleinfo/

This project also includes elements of the Python 3 port of this code by pklaus as published at https://gist.github.com/pklaus/469e603b105905170992

TLE data is sourced from http://www.tle.info/

NOTE: TLE.INFO appears to be IPv6 only now. Try browsing to their page - if it doesn't load unless you use IPv6 then that may be a permanent change by them.

More about TLE at https://en.wikipedia.org/wiki/Two-line_element_set

Note: This is developed and tested using Python 2.7 and 3.6 on Windows and cross-tested using Python 3.6 on OS X, but as long as the same libraries are available in your OS this should work there as well.

Use `virtualenv` to keep a clean development environment!

Install Python (I favor Python 3.6+), and then `pip install` the following
  - ephem
  - numpy
  - configobj
  - matplotlib (includes pytz, six, cycler, pyparsing, python-dateutil)
  - geocoder (includes idna, chardet, certifi, urllib3, requests, click, decorator, ratelim)

Getting "urllib.error.URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed" on OS X?
  Go to `Applications` -> `Python 3.6` -> `Install Certificates.command`
  (Thanks to https://stackoverflow.com/a/42098127/760905)

