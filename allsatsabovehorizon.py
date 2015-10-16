#!/usr/bin/env python

"""
Python Satellite Data Visualizer
--------------------------------

Author: Martin Falatic, 2015-10-15

Based on code by user /u/chknoodle_aggie 2015-08-14 as posted in
https://www.reddit.com/r/Python/comments/3gwzjr/using_pyephem_i_just_plotted_every_tleinfo/
"""

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

tleSources = {
    'AUS-CITY all':
        ('http://www.tle.info/data/ALL_TLE.ZIP',
         'ALL_TLE.ZIP'),
    'Celestrak visual':
        ('http://www.celestrak.com/NORAD/elements/visual.txt',
         'visual.txt'),
    'Celestrak BREEZE-M R/B':
        ('http://www.celestrak.com/NORAD/elements/2012-044.txt',
         '2012-044.txt'),
}

content = []
for sourceName in sorted(tleSources):
    (sourceUrl, sourceFile) = tleSources[sourceName]
    if os.path.isfile(sourceFile):
        print('Using saved TLE data {} ({})'.format(sourceName,
              time.ctime(os.path.getmtime(sourceFile))))
    else:
        print('Retrieving TLE data from {}'.format(sourceName))
        file = URLopener()
        try:
            file.retrieve(sourceUrl, sourceFile)
        except:
            print("Error: Failed to get TLE data")
            sys.exit(1)
        else:
            print('{} updated'.format(sourceFile))

    if sourceFile.lower().endswith('.zip'):
        print('Unzipping {}...'.format(sourceFile))
        zip = zipfile.ZipFile(sourceFile)
        zip.extractall('.')
        sourceFile = zip.namelist()[0]
        print('Extracted {}'.format(zip.namelist()))

    with open(sourceFile) as f:
        tempContent = f.readlines()
        print(int(len(tempContent) / 3),
              'TLEs loaded from {}'.format(sourceFile))
        for i in range(0, len(tempContent)):
            tempContent[i] = tempContent[i].replace('\n', '')

    content.extend(tempContent)

print()

# Set observer location
defaultLocation = "Abilene, TX"
# Pontianak, Indonesia and Quito, Ecuador are right on the equator
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

print()
print(g.json)
home = ephem.Observer()
(latitude, longitude) = g.latlng
elevation = geocoder.elevation(g.latlng).meters
home.lat = str(latitude)    # +N
home.lon = str(longitude)   # +E
home.elevation = elevation  # 524.0  # meters
print()
print('{}N {}E, {}m'.
      format(latitude, longitude, elevation))
print('{}N {}E, {}m'.
      format(home.lat, home.lon, home.elevation))
print()

# Read in each TLE entry and save to list
savedsats = []
satnames = []
i_name = 0
while 3 * i_name + 2 <= len(content):
    # For each satellite in the content list...
    savedsats.append(ephem.readtle(
        content[3 * i_name],
        content[3 * i_name + 1],
        content[3 * i_name + 2]))
    satnames.append(content[3 * i_name])
    i_name += 1

fig = plt.figure()
t = time.time()

while 1:
    fig.clf()
    home.date = datetime.utcnow()

    theta_plot = []
    r_plot = []

    def handle_close(event):
        print("Close event received")

    # Click on a satellite to print its TLE name to the console
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
    ax.scatter(theta_plot, r_plot, picker=True, c='y')
    fig.canvas.mpl_connect('pick_event', onpick)
    fig.canvas.mpl_connect('close_event', handle_close)
    ax.set_rmax(1.0)
    plt.pause(0.25)
