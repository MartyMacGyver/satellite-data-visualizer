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
import matplotlib as mpl
mpl.use('TkAgg')  # Must happen before pyplot import!
import matplotlib.pyplot as plt
import zipfile
import geocoder
import warnings
from configobj import ConfigObj
import threading
try:
    import urllib
    from urllib.request import urlopen, Request
except ImportError:
    import urllib2 # pylint: disable=unused-import
    from urllib2 import urlopen, Request


def mkdir_checked(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def sanitize_filename(name):
    ok_chars = list(r"""._' ,;[](){}!@#%^&""")
    return "".join(c for c in name if c.isalnum() or c in ok_chars).rstrip()

def dequote(s):
    """
    From https://stackoverflow.com/a/20577580/760905
    If a string has single or double quotes around it, remove them.
    Make sure the pair of quotes match.
    If a matching pair of quotes is not found, return the string unchanged.
    """
    if (s[0] == s[-1]) and s.startswith(("'", '"')):
        return s[1:-1]
    return s


class SatDataViz(object):
    def __init__(self, win_label=None, config_file=None):
        if win_label:
            self.win_label = win_label
        else:
            self.win_label = "Satellite Data Visualizer for Python"
        print(self.win_label)
        print()
        self.click_wait_s = 0.10
        self.data_dir = "tledata"
        self.savedsats = None
        self.curr_time = None
        self.home = None
        self.latlng = None
        self.location = None
        self.elevation = None
        if config_file:
            self.config_file = config_file
        else:
            self.config_file = 'config.ini'
        mkdir_checked(self.data_dir)
        self.load_config()

    def load_config(self, config_file=None):
        if not config_file:
            config_file = self.config_file
        self.config = ConfigObj(config_file)
        #pprint(sdv.config)
        # TODO: validate inputs to avoid possible crashes
        #    self.config['main']['color_outline']
        #    self.config['main']['color_alpha']
        #    self.config['main']['update_pause_ms']
        #    self.config['main']['window_size']
        #    self.config['main']['user_agent']
        #    self.config['main']['default_location']

    def save_config(self, config_file=None):
        if config_file:
            self.config.filename = config_file
        #self.config.unrepr = True
        self.config.write()

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
            new_etag = dequote(headers["ETag"])
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
            zip_data.extractall(path=self.data_dir)
            source_file = os.path.join(self.data_dir, sanitize_filename(zip_data.namelist()[0]))
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
                        number = partsTLEdat1[1]
                        designator = partsTLEdat1[2]
                        (body_namepart, body_datapart) = body.writedb().split(',', 1)
                        new_sat = {'name': body.name,
                                   'number': number,
                                   'designator': designator,
                                   'source_num': source_section.split(' ', 1)[1],
                                   'source_name': source['name'],
                                   'color': source['color'],
                                   'body': body,
                                   'picked': False,
                                  }
                        if body_datapart in bodies_dedup:
                            sat_index = bodies_dedup[body_datapart]
                            self.savedsats[sat_index] = new_sat
                            print("Updated idx {} for {}".format(sat_index, body_namepart))
                        else:
                            self.savedsats.append(new_sat)
                            sat_index = len(self.savedsats)-1
                            bodies_dedup[body_datapart] = sat_index
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
            gloc = geocoder.google(location_keyword)
            if gloc.status != 'OK':
                print('Location not found: "{}"'.format(location_keyword))
                location_keyword = ''
            else:
                print()
        #print()
        #print(gloc.json)
        #print()
        self.location = gloc.address
        self.config['main']['default_location'] = self.location
        self.latlng = "{}, {}".format(gloc.lat, gloc.lng)
        self.elevation = geocoder.elevation(gloc.latlng).meters
        self.home = ephem.Observer()
        self.home.elevation = self.elevation  # meters
        (latitude, longitude) = gloc.latlng
        self.home.lat = str(latitude)  # +N
        self.home.lon = str(longitude)  # +E
        print("Location: {} ({}) {}m".format(self.location, self.latlng, self.elevation))
        print("Ephem: {}N {}E, {:0.2f}m".format(self.home.lat, self.home.lon, self.home.elevation))
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
                    del picked_sats[:]
            click_ok.set()
        fig.canvas.mpl_connect('button_press_event', onclick)

        running = True
        while running:
            click_ok.wait()  # Pause while processing a click
            data_ok.clear()  # Don't let clicks use stale data
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
                        radius_plot.append(math.cos(satdata['body'].alt))
                        theta_plot.append(satdata['body'].az)
                        if satdata['picked']:
                            colors.append("#000000")
                        else:
                            colors.append(satdata['color'])
                        if satdata['picked']:
                            noted_sats.append(satdata)  # Finalized data here
                        plotted_sats.append(satdata)
                        plot_idx += 1
            # plot initialization and display
            ax = plt.subplot(111, polar=True)
            title_locn = "{} ({}) {}m".format(self.location, self.latlng, self.elevation)
            title_date = "{} UTC".format(curr_date)
            title_stat = "Satellites overhead: {}".format(len(plotted_sats))
            ax.set_title('\n'.join([title_locn, title_date, title_stat]), va='bottom')
            ax.set_theta_offset(np.pi / 2.0)  # Top = 0 deg = North
            ax.set_theta_direction(-1)  # clockwise
            ax.xaxis.set_ticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'])
            ax.yaxis.set_ticklabels([])  # hide radial tick labels
            ax.grid(True)
            ax.set_facecolor('ivory')
            marker = mpl.markers.MarkerStyle(marker='o', fillstyle='full')
            # Note: you can't currently pass multiple marker styles in an array like colors
            ax.scatter(theta_plot, radius_plot, marker=marker,
                       picker=1, # This sets the tolerance for clicking on a point
                       c=colors, edgecolors=color_outline, alpha=color_alpha,
                      )
            ax.set_rmax(1.0)
            self.notate_sat_data(ax=ax, noted_sats=picked_sats)
            plt.subplots_adjust(left=0.05, right=0.6)
            data_ok.set()  # Done
            try:
                plt.pause(update_pause_ms/1000.0)  # Required, but the loop is rather slow anyway
                #fig.clf()
                plt.cla()
            except Exception as e:
                running = False
                # TODO: Hiding a lot of Tk noise for now - improve this if possible
                if not str(e).startswith("can't invoke \"update\" command:"):
                    print(e)

    def notate_sat_data(self, ax, noted_sats):
        notes = ["Tracking list:\n"]
        for satdata in noted_sats:
            notes.append(
                '[{:s}] "{:s}" [{:s}/{:s}] (alt={:0.2f} az={:0.2f}) (ra={:0.2f} dec={:0.2f})'.format(
                    satdata['source_num'],
                    satdata['name'],
                    satdata['number'],
                    satdata['designator'],
                    math.degrees(satdata['body'].alt),
                    math.degrees(satdata['body'].az),
                    math.degrees(satdata['body'].ra),
                    math.degrees(satdata['body'].dec),
            ))
        if len(notes) <= 1:
            notes.append("(none)")
        ax.annotate(
            '\n'.join(notes),
            xy=(0.0, 0.0),  # theta, radius
            xytext=(math.pi/2.0, 1.25),    # fraction, fraction
            horizontalalignment='left',
            verticalalignment='center',
        )

if __name__ == "__main__":
    print()
    print('-'*79)

    sdv = SatDataViz()
    sdv.get_location()
    sdv.process_tle_data()
    sdv.save_config()
    sdv.plot_sats()

    print()
    print("Exiting...")
