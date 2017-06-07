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
import os
import os.path
import errno
import ephem
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import zipfile
import geocoder
import warnings
from configobj import ConfigObj
import threading
#from collections import namedtuple
#from pprint import pprint
try:
    import urllib
    from urllib.request import urlopen, Request
except ImportError:
    import urllib2
    from urllib2 import urlopen, Request

def mkdir_checked(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def sanitize_filename(n):
    ok_chars = list(r"""._' ,;[](){}!@#%^&""")
    return "".join(c for c in n if c.isalnum() or c in ok_chars).rstrip()

class SatDataViz(object):
    def __init__(self, win_label="title", config_file=None):
        self.click_wait_s = 0.10
        self.data_dir = "tledata"
        self.win_label = win_label
        self.savedsats = None
        self.curr_time = None
        self.home = None
        mkdir_checked(self.data_dir)
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
        source_file = os.path.join(self.data_dir, sanitize_filename(source['file']))
        source_url = source['url']

        print('Querying TLE data source \"{}\" at {}'.format(source_name, source_url))
        try:
            req = Request(source_url, headers={'User-Agent': user_agent})
            response = urlopen(req)
            headers = response.info()
            new_etag = self.dequote(headers["ETag"])
            new_size = int(headers["Content-Length"])
        except urllib.error.HTTPError as e:
            print("Error: Failed to query url ({})".format(e))

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
            print('Existing TLE data is current')
        else:
            print('Retrieving TLE data')
            try:
                data = response.read() 
            except urllib.error.HTTPError as e:
                print("Error: Failed to download data ({})".format(e))
                print("Will use existing data if present")
            else:
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
        self.savedsats = []
        bodies_dedup = {}
        tleSources = [s for s in self.config.sections if s.startswith('source ')]
        for source_section in tleSources:
            source = self.config[source_section]
            print("Processing {}".format(source['name']))
            temp_content = self.readTLEfile(source=source)
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
                        (body_namepart, body_datapart) = body.writedb().split(',', 1)
                        new_sat = {'name': body.name,
                                     'number': number,
                                     'designator': designator,
                                     'color': source['color'],
                                     'body': body,
                                     'picked': False,
                                    }
                        if body_datapart in bodies_dedup:
                            print("Updated idx {} for {}".format(sat_index, body_namepart))
                            sat_index = bodies_dedup[body_datapart]
                            self.savedsats[sat_index] = new_sat
                        else:
                            self.savedsats.append(new_sat)
                            sat_index = len(self.savedsats)-1
                            bodies_dedup[body_datapart] = sat_index
                        #print("[{}] {} {} {} {}".
                        #    format(source_section, body.name, number, designator, body.writedb())
                    i_name += 1
            print()

    def get_location(self):
        ''' Get user location based on input '''
        # Note: Pontianak, Indonesia and Quito, Ecuador are right on the equator
        if sys.version_info < (3,0):
            input_function = raw_input # pylint:disable=undefined-variable
        else:
            input_function = input
        default_location = self.config['main']['default_location']
        location_keyword = ''
        while not location_keyword:
            location_keyword = input_function(
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
        print('Given: {}N {}E, {:0.2f}m'.format(latitude, longitude, elevation))
        print('Ephem: {}N {}E, {:0.2f}m'.format(self.home.lat, self.home.lon, self.home.elevation))
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
        fig.canvas.set_window_title(self.win_label)
        self.curr_time = time.time()
        curr_date = datetime.utcnow()
        errored_sats = set()
        picked_sats = []
        plotted_sats = []
        last_picked = [None]  # Keep data mutable
        data_ok = threading.Event()
        data_ok.set()
        click_ok = threading.Event()
        click_ok.set()

        def handle_close(event):
            # Any way to make this more useful?
            print()
            print("Event received ({:s})".format(event.name))
        fig.canvas.mpl_connect('close_event', handle_close)

        def onpick(event):
            ''' These *only* happen with data points get clicked by any button '''
            # print("Picked  at", time.time(), event.mouseevent)
            last_picked[0] = event.mouseevent
            if time.time() - self.curr_time < self.click_wait_s:  # Rate limiting
                return
            self.curr_time = time.time()
            data_ok.wait()  # Pause while processing data
            click_ok.clear()
            for plot_idx in event.ind:
                satdata = plotted_sats[plot_idx]
                # print(satdata['name'], "plot_idx=", satdata['plot_idx'])
                if satdata['picked']:
                    satdata['picked'] = False
                    if satdata in picked_sats:
                        picked_sats.remove(satdata)
                else:
                    satdata['picked'] = True
                    picked_sats.append(satdata)
            click_ok.set()
        fig.canvas.mpl_connect('pick_event', onpick)

        def onclick(event):
            ''' These follow onpick() events as well '''
            # print("Clicked at", time.time(), event)
            if time.time() - self.curr_time < self.click_wait_s:  # Rate limiting
                return
            self.curr_time = time.time()
            data_ok.wait()  # Pause while processing data
            click_ok.clear()
            if last_picked[0] == event:
                pass  # print("Part of last pick")
            else:
                if event.button == 3:
                    for satdata in picked_sats[:]:
                        satdata['picked'] = False
                    picked_sats.clear()
            # print(picked_sats)
            # print()
            click_ok.set()
        fig.canvas.mpl_connect('button_press_event', onclick)

        running = True
        while running:
            click_ok.wait()  # Pause while processing a click
            data_ok.clear()
            if secs_per_step:
                curr_date += timedelta(seconds=secs_per_step)
            else:
                curr_date = datetime.utcnow()
            self.home.date = curr_date
            theta_plot = []
            radius_plot = []
            colors = []
            plot_idx = 0
            noted_sats = []
            plotted_sats = []
            for satdata in self.savedsats:  # for each satellite in the savedsats list
                satdata['plot_idx'] = None
                try:
                    satdata['body'].compute(self.home)
                    alt = satdata['body'].alt
                except ValueError:
                    #print("Date out of range")
                    pass
                except RuntimeError as e:
                    if satdata['name'] not in errored_sats:
                        errored_sats.add(satdata['name'])
                        print("Cannot compute position for {}".format(satdata['name']))
                else:
                    if math.degrees(alt) > 0.0:
                        satdata['plot_idx'] = plot_idx
                        theta_plot.append(satdata['body'].az)
                        radius_plot.append(math.cos(satdata['body'].alt))
                        if satdata['picked']:
                            colors.append("#000000")
                        else:
                            colors.append(satdata['color'])
                        if satdata['picked']:
                            noted_sats.append(satdata)  # Finalized data here
                        plotted_sats.append(satdata)
                        plot_idx += 1
            data_ok.set()  # Done with the critical part
            # plot initialization and display
            ax = plt.subplot(111, polar=True)
            pltTitle = "{} UTC\nSatellites overhead: {}".format(
                curr_date, len(plotted_sats))
            ax.set_title(pltTitle, va='bottom')
            ax.set_theta_offset(np.pi / 2.0)  # Top = 0 deg = North
            ax.set_theta_direction(-1)  # clockwise
            ax.xaxis.set_ticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'])
            ax.yaxis.set_ticklabels([])  # hide radial tick labels
            ax.grid(True)
            marker = mpl.markers.MarkerStyle(marker='o', fillstyle='full')
            # Note: you can't currently pass multiple marker styles in an array like colors
            ax.scatter(theta_plot, radius_plot, marker=marker,
                       picker=1, # This sets the tolerance for clicking on a point
                       c=colors, edgecolors=color_outline, alpha=color_alpha,
                      )
            ax.set_rmax(1.0)
            self.notate_sat_data(ax=ax, noted_sats=noted_sats)
            plt.subplots_adjust(right=0.6)
            try:
                plt.pause(update_pause_ms/1000.0)  # A pause is needed here, but the loop is rather slow
                #fig.clf()
                plt.cla()
            except Exception as e:
                running = False
                # TODO: Hiding a lot of Tk noise for now - improve this if possible
                if not str(e).startswith("can't invoke \"update\" command:"):
                    print(e)

    def notate_sat_data(self, ax, noted_sats):
        notes = []
        for satdata in noted_sats:
            notes.append(
                '{:s} (az={:0.2f} alt={:0.2f})'.format(
                    satdata['body'].name,
                    math.degrees(satdata['body'].az),
                    math.degrees(satdata['body'].alt),
            ))
        ax.annotate(
            '\n'.join(notes),
            xy=(0.0, 0.0),  # theta, radius
            xytext=(math.pi/2.0, 1.2),    # fraction, fraction
            horizontalalignment='left',
            verticalalignment='center',
            )

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

if __name__ == "__main__":
    my_win_label = "Satellite Data Visualizer for Python"
    my_config_file = 'config.ini'

    print()
    print('-'*79)
    print(my_win_label)
    print('-'*79)
    print()

    sdv = SatDataViz(win_label=my_win_label)
    sdv.load_config(my_config_file)
    sdv.get_location()
    sdv.process_tle_data()
    sdv.save_config()
    sdv.plot_sats()

    print()
    print("Exiting...")
