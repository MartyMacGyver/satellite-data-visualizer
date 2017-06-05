#!/usr/bin/env python3.6

#   Copyright (c) 2015-2017 Martin F. Falatic
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
Satellite Data Visualizer for Python
------------------------------------

Author: Martin Falatic, 2015-10-15
Based on code by user /u/chknoodle_aggie 2015-08-14 as posted in
https://www.reddit.com/radius/Python/comments/3gwzjr/using_pyephem_i_just_plotted_every_tleinfo/

More about TLE:
https://en.wikipedia.org/wiki/Two-line_element_set
http://spaceflight.nasa.gov/realdata/sightings/SSapplications/Post/JavaSSOP/SSOP_Help/tle_def.html

"""

from __future__ import print_function   # PEP 3105: Make print a function

import math
import time
from datetime import datetime, timedelta
import sys
import os.path
import ephem
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import zipfile
import geocoder
import warnings
from collections import namedtuple

try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request

try:
    input = raw_input
except NameError:
    pass

warnings.filterwarnings("ignore",
    ".*Using default event loop until function specific to this GUI is implemented")

Point = namedtuple('Point', ['x', 'y'])
curr_time = time.time()

TITLE = "Satellite Data Visualizer for Python"
DEBUG = False
SIMSECS = 0  # 60*60
defaultLocation = "San Francisco, CA"
color_outline = '#808080'
color_alpha = 0.75
user_agent = 'Mozilla/5.0'
window_size = Point(x=1200, y=1000)
update_pause_ms = 100
running = True

tleSources = [
    {'name':  'McCant\'s classifieds',
     'url':   'https://www.prismnet.com/~mmccants/tles/classfd.zip',
     'file':  'classfd.zip',
     'color': '#000000'},

    {'name':  'AUS-CITY all',
     'url':   'http://www.tle.info/data/ALL_TLE.ZIP',
     'file':  'ALL_TLE.ZIP',
     'color': '#ffffff'},

    {'name':  'AUS-CITY GPS',
     'url':   'http://www.tle.info/data/gps-ops.txt',
     'file':  'gps-ops.txt',
     'color': '#ff0000'},

    {'name':  'Celestrak visual',
     'url':   'http://www.celestrak.com/NORAD/elements/visual.txt',
     'file':  'visual.txt',
     'color': '#00ff00'},

    {'name':  'Planet Labs',
     'url':   'http://ephemerides.planet-labs.com/planet_mc.tle',
     'file':  'planet_mc.tle',
     'color': '#00ffff'},

    # {'name':  'Celestrak BREEZE-M radius/B',
    #  'url':   'http://www.celestrak.com/NORAD/elements/2012-044.txt',
    #  'file':  '2012-044.txt',
    #  'color': '#0000ff'},
    ]


def readTLEfile(source):
    ''' Read a TLE file (unzip if necessary) '''
    source_name = source['name']
    source_file = source['file']
    source_url = source['url']
    if os.path.isfile(source_file):
        print('Using saved TLE data {} ({})'.format(source_file,
              time.ctime(os.path.getmtime(source_file))))
    else:
        print('Retrieving TLE data from {}'.format(source_url))
        try:
            print("here")
            req = Request(source_url, headers={'User-Agent': user_agent})
            response = urlopen(req)
            data = response.read() 
        except Exception as err:
            print("Error: Failed to get TLE data ({})".format(err))
            return None
        else:
            with open(source_file, 'wb') as f:
                f.write(data)
            print('{} updated'.format(source_file))

    if source_file.lower().endswith('.zip'):
        print('Unzipping {}...'.format(source_file))
        zip_data = zipfile.ZipFile(source_file)
        zip_data.extractall('.')
        source_file = zip_data.namelist()[0]
        print('Extracted {}'.format(zip_data.namelist()))

    temp_content = []
    with open(source_file) as f:
        for aline in f:
            temp_content.append(aline.replace('\n', ''))
        print(len(temp_content) // 3,
              'TLEs loaded from {}'.format(source_file))

    return temp_content


def processTLEdata(tleSources):
    ''' Process each TLE entry '''
    sats = []
    for source in tleSources:
        print("Processing {}".format(source['name']))
        temp_content = readTLEfile(source=source)
        print()
        if temp_content:
            i_name = 0
            while 3 * i_name + 2 <= len(temp_content):
                rawTLEname = temp_content[3 * i_name + 0]
                rawTLEdat1 = temp_content[3 * i_name + 1]
                rawTLEdat2 = temp_content[3 * i_name + 2]
                partsTLEdat1 = rawTLEdat1.split()
                try:
                    body = ephem.readtle(rawTLEname, rawTLEdat1, rawTLEdat2)
                except ValueError:
                    print("Error: line does not conform to tle format")
                    print("       " + rawTLEname)
                    print("       " + rawTLEdat1)
                    print("       " + rawTLEdat2)
                    print()
                else:
                    name = body.name
                    number = partsTLEdat1[1]
                    designator = partsTLEdat1[2]
                    sats.append({'name': name,
                                 'number': number,
                                 'designator': designator,
                                 'color': source['color'],
                                 'body': body, })
                    # print("{} {} {} {}".
                    #     format(name, number, designator, body))
                i_name += 1
                # if i_name > 100:
                #     break
    return sats


def getLocation():
    ''' Get user location based on input '''
    # Note: Pontianak, Indonesia and Quito, Ecuador are right on the equator
    locationKeyword = ''
    while not locationKeyword:
        locationKeyword = input(
            'Enter location (default="{}"): '.format(defaultLocation))
        if not locationKeyword or locationKeyword.isspace():
            locationKeyword = defaultLocation
        g = geocoder.google(locationKeyword)
        if g.status != 'OK':
            print('Location not found: "{}"'.format(locationKeyword))
            locationKeyword = ''
        else:
            print()
            print('Location found: "{}"'.format(g.location))
    if DEBUG:
        print()
        print(g.json)
    return g


def plotSats(savedsats, latitude, longitude, elevation):
    home = ephem.Observer()
    home.lat = str(latitude)    # +N
    home.lon = str(longitude)   # +E
    home.elevation = elevation  # meters

    if DEBUG:
        print('{}N {}E, {}m'.format(latitude, longitude, elevation))
        print('{}N {}E, {}m'.format(home.lat, home.lon, home.elevation))
        print()

    print('-'*79)
    print()

    #fig = gcf()

    fig = plt.figure()
    DPI = fig.get_dpi()
    fig.set_size_inches(window_size.x/float(DPI), window_size.y/float(DPI))
    # mng = plt.get_current_fig_manager()
    # mng.resize(1600,900)
    fig.canvas.set_window_title(TITLE)

    global curr_time
    curr_time = time.time()
    currdate = datetime.utcnow()
    errored_sats = set()
    watched_sat = {'name':"", 'theta':0.0, 'radius':0.0, 'txt':''}

    running = True

    def onpick(event):
        global curr_time
        if time.time() - curr_time < 1.0:  # limits calls to 1 per second
            return
        curr_time = time.time()
        ind = event.ind
        radius = np.take(radius_plot, ind)[0]
        theta = np.take(theta_plot, ind)[0]
        for satdata in savedsats:
            if (math.degrees(theta) == math.degrees(satdata['body'].az) and
                    math.cos(satdata['body'].alt) == radius):
                break
        sat_printable = '{:s}{:s}(az={:0.2f} alt={:0.2f})'.format(
            satdata['body'].name,
            ' ',
            math.degrees(satdata['body'].az),
            math.degrees(satdata['body'].alt),
        )
        print(sat_printable)
        sat_printable = '{:s}{:s}(az={:0.2f} alt={:0.2f})'.format(
            satdata['body'].name,
            '\n',
            math.degrees(satdata['body'].az),
            math.degrees(satdata['body'].alt),
        )
        watched_sat['name'] = satdata['body'].name
        watched_sat['txt'] = sat_printable
        watched_sat['theta'] = theta
        watched_sat['radius'] = radius

    def handle_close(event):
        # Any way to make this more useful?
        print("Close event received")

    fig.canvas.mpl_connect('pick_event', onpick)
    fig.canvas.mpl_connect('close_event', handle_close)

    while running:
        if SIMSECS > 0:
            currdate += timedelta(seconds=SIMSECS)
        else:
            currdate = datetime.utcnow()
        home.date = currdate
        theta_plot = []
        radius_plot = []
        colors = []

        for satdata in savedsats:  # for each satellite in the savedsats list
            try:
                satdata['body'].compute(home)
                alt = satdata['body'].alt
            except ValueError:
                #print("Date out of range")
                pass
            except RuntimeError as err:
                if satdata['name'] not in errored_sats:
                    errored_sats.add(satdata['name'])
                    print("Cannot compute position for {}".format(satdata['name']))
            else:
                if math.degrees(alt) > 0.0:
                    theta_plot.append(satdata['body'].az)
                    radius_plot.append(math.cos(satdata['body'].alt))
                    colors.append(satdata['color'])

        # plot initialization and display
        pltTitle = str(home.date)
        ax = plt.subplot(111, polar=True)
        ax.set_title(pltTitle, va='bottom')
        ax.set_theta_offset(np.pi / 2.0)  # Top = 0 deg = north
        ax.set_theta_direction(-1)  # clockwise
        ax.xaxis.set_ticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'])
        ax.yaxis.set_ticklabels([])  # hide radial tick labels
        ax.grid(True)
        marker = mpl.markers.MarkerStyle(marker='o', fillstyle='full')
        ax.scatter(theta_plot, radius_plot,
                   marker=marker, picker=True,
                   c=colors, edgecolors=color_outline, alpha=color_alpha,
                  )
        ax.set_rmax(1.0)
        if watched_sat:
            notate_sat_data(ax=ax, notation=watched_sat)
        try:
            plt.pause(update_pause_ms/1000.0)  # A pause is needed here, but the loop is rather slow
            #fig.clf()
            plt.cla()
        except Exception as e:
            running = False
            # TODO: Hiding a lot of Tk noise for now - improve this
            if not str(e).startswith("can't invoke \"update\" command:"):
                print(e)

def notate_sat_data(ax, notation):
    noted = ax.annotate(
        notation['txt'],
        xy=(notation['theta'], notation['radius']),  # theta, radius
        #xytext=(0.05, 0.05),    # fraction, fraction
        xytext=(3, 1.1),    # fraction, fraction
        horizontalalignment='left',
        verticalalignment='bottom',
        )
    return noted

if __name__ == "__main__":
    print()
    print('-'*79)
    print(TITLE)
    print('-'*79)
    print()
    plt.rcParams['toolbar'] = 'None'
    plt.ion()
    savedsats = processTLEdata(tleSources)
    myloc = getLocation()
    (latitude, longitude) = myloc.latlng
    elevation = geocoder.elevation(myloc.latlng).meters
    plotSats(savedsats=savedsats, latitude=latitude,
             longitude=longitude, elevation=elevation)
    print()
    print("Exiting")
