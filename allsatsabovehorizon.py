#!/usr/bin/env python

# Fork by Martin Falatic

# Original Python 2 version by user /u/chknoodle_aggie 2015-08-14 as posted in
# https://www.reddit.com/r/Python/comments/3gwzjr/using_pyephem_i_just_plotted_every_tleinfo/

from __future__ import print_function   # PEP 3105: Make print a function

import math
import time
from datetime import datetime
import sys
import os.path
import ephem
import numpy as np
import matplotlib.pyplot as plt
import zipfile
import geocoder

try:
    from urllib.request import URLopener
except ImportError:
    from urllib import URLopener

try:
    input = raw_input
except NameError:
    pass

# http://www.celestrak.com/NORAD/elements/
# import tle data from NORAD if internet_on(), save as sat=ephem.readtle(.

updateTLE = False

if updateTLE:
    print('Retrieving TLE data...')
    file = URLopener()
    try:
        file.retrieve('http://www.tle.info/data/ALL_TLE.ZIP', 'ALL_TLE.ZIP')
    except:
        print("Error: Failed to get TLE data")
        sys.exit(1)
    else:
        print('ALL_TLE.ZIP updated')
else:
    print('Using saved ALL_TLE.ZIP (' +
          time.ctime(os.path.getmtime('ALL_TLE.ZIP')) + ')')

content = []

print('Unzipping ALL_TLE.ZIP...')
zip = zipfile.ZipFile('ALL_TLE.ZIP')
zip.extractall('.')
print('Done unzipping')

# load TLE data into python array
with open('ALL_TLE.TXT') as f:
    content = f.readlines()
    print(int(len(content) / 3), 'TLEs loaded from ALL_TLE.TXT')
    for i in range(0, len(content)):
        content[i] = content[i].replace('\n', '')  # remove endlines

# from geopy.geocoders import GoogleV3  # Nominatim
# geolocator = GoogleV3()  # Nominatim()
# location = geolocator.geocode(locationKeyword)
# print(repr(location.address).encode(sys.stdout.encoding, errors='replace'))
# print((location.latitude, location.longitude, location.altitude))
# print(repr(location.raw).encode(sys.stdout.encoding, errors='replace'))

# Set observer location
defaultLocation = "Abilene, TX"
locationKeyword = ''
while not locationKeyword:
    locationKeyword = input('Location keyword: ')
    if not locationKeyword or locationKeyword.isspace():
        locationKeyword = defaultLocation
        print("Using default location {}".format(locationKeyword))

    g = geocoder.google(locationKeyword)
    if g.status != 'OK':
        print('Location "{}" not found'.format(locationKeyword))
        locationKeyword = ''

print(g.json)
home = ephem.Observer()
(latitude, longitude) = g.latlng
elevation = geocoder.elevation(g.latlng).meters

home.lat = str(latitude)    # +N
home.lon = str(longitude)   # +E
home.elevation = elevation  # 524.0  # meters

# Abilene, TX
# home.lat = '32.45'      # +N
# home.lon = '-99.74'     # +E
# home.elevation = 524.0  # meters

print('{}N {}E, {}m'.
      format((home.lat), (home.lon), home.elevation))


# read in each tle entry and save to list
savedsats = []
satnames = []
i_name = 0
while 3 * i_name + 2 <= len(content):
    # for each satellite in the content list...
    savedsats.append(ephem.readtle(
        content[3 * i_name], content[3 * i_name + 1], content[3 * i_name + 2]))
    satnames.append(content[3 * i_name])
    i_name += 1

fig = plt.figure()

t = time.time()

while 1:
    fig.clf()
    home.date = datetime.utcnow()

    theta_plot = []
    r_plot = []

    # click on a satellite to print its TLE name to the console
    def onpick(event):
        global t
        if time.time() - t < 1.0:  # limits calls to 1 per second
            return
        t = time.time()
        ind = event.ind
        r = np.take(r_plot, ind)[0]
        theta = np.take(theta_plot, ind)[0]
        i = 0
        while (i < len(savedsats) and
               (math.degrees(theta) != math.degrees(savedsats[i].az) or
                math.cos(savedsats[i].alt) != r)):
            i += 1
        print(satnames[i], 'az=' + str(math.degrees(savedsats[i].az)),
              'alt=' + str(math.degrees(savedsats[i].alt)))

    for sat in savedsats:  # for each satellite in the savedsats list...
        sat.compute(home)
        if math.degrees(sat.alt) > 0.0:
            theta_plot.append(sat.az)
            r_plot.append(math.cos(sat.alt))

    # plot initialization and display
    ax = plt.subplot(111, polar=True)
    ax.set_theta_direction(-1)  # clockwise
    ax.set_theta_offset(np.pi / 2)  # put 0 degrees (north) at top of plot
    ax.yaxis.set_ticklabels([])  # hide radial tick labels
    ax.grid(True)
    title = str(home.date)
    ax.set_title(title, va='bottom')
    ax.scatter(theta_plot, r_plot, picker=True)
    fig.canvas.mpl_connect('pick_event', onpick)
    ax.set_rmax(1.0)
    plt.pause(1.0)
