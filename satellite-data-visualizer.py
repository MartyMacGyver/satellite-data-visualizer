#!/usr/bin/env python3

"""
    Satellite Data Visualizer for Python
    ---------------------------------------------------------------------------

    Copyright (c) 2015-2017 Martin F. Falatic

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

    ---------------------------------------------------------------------------
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
from configobj import ConfigObj
from pprint import pprint
try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request
try:
    input = raw_input
except NameError:
    pass

class SatDataViz(object):
    def __init__(self, win_label="title", config_file=None):
        self.win_label = win_label
        if config_file:
            self.load_config(config_file)

    def save_config(self, config_file=None):
        if config_file:
            self.config.filename = config_file
        #self.config.unrepr = True
        self.config.write()

    def load_config(self, config_file):
        self.config = ConfigObj(config_file)
        #pprint(sdv.config)
        # TODO: validate inputs to avoid possible crashes
        #    self.config['main']['color_outline']
        #    self.config['main']['color_alpha']
        #    self.config['main']['update_pause_ms']
        #    self.config['main']['window_size']
        #    self.config['main']['user_agent']
        #    self.config['main']['default_location']

    def readTLEfile(self, source):
        ''' Get and read a TLE file (unzip if necessary) '''
        user_agent = self.config['main']['user_agent']
        source_name = source['name']
        source_file = source['file']
        source_url = source['url']

        print('Querying TLE data source {}'.format(source_url))
        try:
            req = Request(source_url, headers={'User-Agent': user_agent})
            response = urlopen(req)
            headers = response.info()
            new_etag = self.dequote(headers["ETag"])
            new_size = int(headers["Content-Length"])
        except Exception as err:
            print("Error: Failed to query url ({})".format(err))
            return None
        
        if os.path.isfile(source_file):
            curr_size = os.path.getsize(source_file)
            curr_modtime = time.ctime(os.path.getmtime(source_file))
            print('Checking local TLE data {} ({}, {})'.format(
                  source_file, curr_size, curr_modtime))
        else:
            curr_size = 0
        #print(curr_size, new_size, curr_size == new_size)
        #print(source['etag'], new_etag, source['etag'] == new_etag)
        if (curr_size == new_size) and (source['etag'] == new_etag):
            print('Existing TLE data is current'.format(source_url))
        else:
            print('Retrieving TLE data from {}'.format(source_url))
            try:
                data = response.read() 
            except Exception as err:
                print("Error: Failed to download data ({})".format(err))
                return None
            source['etag'] = new_etag
            source['size'] = new_size
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

    def process_tle_data(self):
        ''' Process each TLE entry '''
        sats = []
        tleSources = [s for s in self.config.sections if s.startswith('source ')]
        for source_section in tleSources:
            source = self.config[source_section]
            print("Processing {}".format(source['name']))
            temp_content = self.readTLEfile(source=source)
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
        self.savedsats = sats

    def get_location(self):
        ''' Get user location based on input '''
        # Note: Pontianak, Indonesia and Quito, Ecuador are right on the equator
        default_location = self.config['main']['default_location']
        location_keyword = ''
        while not location_keyword:
            location_keyword = input(
                'Enter location (default="{}"): '.format(default_location))
            if not location_keyword or location_keyword.isspace():
                location_keyword = default_location
            g = geocoder.google(location_keyword)
            if g.status != 'OK':
                print('Location not found: "{}"'.format(location_keyword))
                location_keyword = ''
            else:
                print()
                print('Location found: "{}"'.format(g.location))
        self.config['main']['default_location'] = location_keyword
        #print()
        #print(g.json)
        #print()
        (latitude, longitude) = g.latlng
        elevation = geocoder.elevation(g.latlng).meters
        self.home = ephem.Observer()
        self.home.lat = str(latitude)    # +N
        self.home.lon = str(longitude)   # +E
        self.home.elevation = elevation  # meters
        print('Given: {}N {}E, {}m'.format(latitude, longitude, elevation))
        print('Ephem: {}N {}E, {}m'.format(self.home.lat, self.home.lon, self.home.elevation))
        print()

    def plot_sats(self):
        warnings.filterwarnings("ignore",
            ".*Using default event loop until function specific to this GUI is implemented")

        color_outline = self.config['main']['color_outline']
        color_alpha = float(self.config['main']['color_alpha'])
        update_pause_ms = int(self.config['main']['update_pause_ms'])
        window_size = self.config['main']['window_size']
        secs_per_step = int(self.config['main']['secs_per_step'])

        print('-'*79)
        print()

        plt.rcParams['toolbar'] = 'None'
        plt.ion()
        fig = plt.figure()
        DPI = fig.get_dpi()
        fig.set_size_inches(int(window_size[0])/float(DPI), int(window_size[1])/float(DPI))
        # mng = plt.get_current_fig_manager()
        # mng.resize(1600,900)
        fig.canvas.set_window_title(win_label)

        self.curr_time = time.time()
        currdate = datetime.utcnow()
        errored_sats = set()
        watched_sat = {'name':"", 'theta':0.0, 'radius':0.0, 'txt':''}

        running = True

        def onpick(event):
            if time.time() - self.curr_time < 1.0:  # limits calls to 1 per second
                return
            self.curr_time = time.time()
            ind = event.ind
            radius = np.take(radius_plot, ind)[0]
            theta = np.take(theta_plot, ind)[0]
            for satdata in self.savedsats:
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
            print()
            print("Close event received")

        fig.canvas.mpl_connect('pick_event', onpick)
        fig.canvas.mpl_connect('close_event', handle_close)

        while running:
            if secs_per_step:
                currdate += timedelta(seconds=secs_per_step)
            else:
                currdate = datetime.utcnow()
            self.home.date = currdate
            theta_plot = []
            radius_plot = []
            colors = []

            for satdata in self.savedsats:  # for each satellite in the savedsats list
                try:
                    satdata['body'].compute(self.home)
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
            pltTitle = str(self.home.date)
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
                self.notate_sat_data(ax=ax, notation=watched_sat)
            try:
                plt.pause(update_pause_ms/1000.0)  # A pause is needed here, but the loop is rather slow
                #fig.clf()
                plt.cla()
            except Exception as e:
                running = False
                # TODO: Hiding a lot of Tk noise for now - improve this
                if not str(e).startswith("can't invoke \"update\" command:"):
                    print(e)

    def dequote(self, s):
        """
        From https://stackoverflow.com/a/20577580/760905
        If a string has single or double quotes around it, remove them.
        Make sure the pair of quotes match.
        If a matching pair of quotes is not found, return the string unchanged.
        """
        if (s[0] == s[-1]) and s.startswith(("'", '"')):
            return s[1:-1]
        return s

    def notate_sat_data(self, ax, notation):
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
    win_label = "Satellite Data Visualizer for Python"
    config_file = 'config.ini'

    print()
    print('-'*79)
    print(win_label)
    print('-'*79)
    print()

    sdv = SatDataViz(win_label=win_label)
    sdv.load_config(config_file)
    sdv.get_location()
    sdv.process_tle_data()
    sdv.save_config()
    sdv.plot_sats()

    print()
    print("Exiting...")
