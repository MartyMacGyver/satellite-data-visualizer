#!/usr/bin/env python3

"""
    Satellite Data Visualizer for Python
    ---------------------------------------------------------------------------

    Copyright (c) 2015-2018 Martin F. Falatic

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

import math
import time
from datetime import datetime, timedelta
import sys
import os
import os.path
import errno
import ephem
import numpy as np
import zipfile
import geocoder
import warnings
import getpass
from configobj import ConfigObj
import threading
try:
    import urllib
    from urllib.request import urlopen, Request
except ImportError:
    import urllib2  # noqa: disable=unused-import
    from urllib2 import urlopen, Request
import matplotlib as mpl

SECRET_API_KEY = ''
RETRY_DELAY = 0.5
MAX_RETRIES = 10
DEFAULT_ELEVATION = 0.0


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
        self.curr_date = None
        self.home = None
        self.latitude = None
        self.longitude = None
        self.location = None
        self.friendly_location = None
        self.elevation = None
        mkdir_checked(self.data_dir)
        # Config file defaults
        self.secs_per_step = 0
        self.default_location = "San Francisco, CA, USA"
        self.color_outline = "#808080"
        self.color_alpha = 0.75
        self.user_agent = "Mozilla/5.0"
        self.window_size = [1700, 1000]
        self.update_pause_ms = 20
        self.mpl_backend = 'TkAgg'
        if config_file:
            self.config_file = config_file
        else:
            self.config_file = 'config.ini'
        self._load_config()
        print("Selected the '{}' backend for MatPlotLib".format(self.mpl_backend))
        print()
        mpl.use(self.mpl_backend)  # Must happen before pyplot import!
        import matplotlib.pyplot
        self.plt = matplotlib.pyplot

    def _load_config(self, config_file=None):
        if not config_file:
            config_file = self.config_file
        self.config = ConfigObj(config_file, encoding='UTF8')
        self.secs_per_step = self._verify_config_item(
            self.secs_per_step, 'secs_per_step', int)
        self.default_location = self._verify_config_item(
            self.default_location, 'default_location', str)
        self.color_outline = self._verify_config_item(
            self.color_outline, 'color_outline', str)
        self.color_alpha = self._verify_config_item(
            self.color_alpha, 'color_alpha', float)
        self.user_agent = self._verify_config_item(
            self.user_agent, 'user_agent', str)
        self.window_size = self._verify_config_item(
            self.window_size, 'window_size', list)
        self.update_pause_ms = self._verify_config_item(
            self.update_pause_ms, 'update_pause_ms', int)
        self.mpl_backend = self._verify_config_item(
            self.mpl_backend, 'mpl_backend', str)

    def _verify_config_item(self, default, item_name, item_type):
        try:
            rval = item_type(self.config['main'][item_name])
        except KeyError:
            print("Config item '{:s}' not found, using default value ({})".format(
                item_name, default))
            rval = self.config['main'][item_name] = default
        except ValueError:
            print("Config item '{:s}' malformed, using default value ({})".format(
                item_name, default))
            rval = self.config['main'][item_name] = default
        return rval

    def save_config(self, config_file=None):
        if config_file:
            self.config.filename = config_file
        # self.config.unrepr = True
        self.config.write()

    def readTLEfile(self, source):
        ''' Get and read a TLE file (unzip if necessary) '''
        source_name = source['name']
        source_file = os.path.join(self.data_dir, sanitize_filename(source['file']))
        source_url = source['url']
        print('Querying TLE data source \"{}\" at {}'.format(source_name, source_url))
        fallback_mode = False
        new_etag = ''
        try:
            req = Request(source_url, headers={'User-Agent': self.user_agent})
            response = urlopen(req)
            headers = response.info()
            new_etag = dequote(headers["ETag"])
            new_size = int(headers["Content-Length"])
        except urllib.error.HTTPError as e:
            print("Error: Failed to query url ({})".format(e))
            fallback_mode = True
        except TimeoutError as e:
            print("Error: Failed to query url ({})".format(e))
            fallback_mode = True
        except urllib.error.URLError as e:
            print("Error: Failed to query url ({})".format(e))
            fallback_mode = True
        curr_size = 0
        if os.path.isfile(source_file):
            curr_size = os.path.getsize(source_file)
            curr_modtime = time.ctime(os.path.getmtime(source_file))
            print('Checking local TLE data {} ({}, {})'.format(
                  source_file, curr_size, curr_modtime))
        else:
            if fallback_mode:
                print('Cannot access current or cached TLE data for this site, skipping')
                return None
        if fallback_mode or (
                source['etag'] == new_etag and curr_size == new_size):
            print('Using existing TLE data')
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
                        new_sat = {
                            'name': body.name,
                            'number': number,
                            'designator': designator,
                            'source_num': source_section.split(' ', 1)[1],
                            'source_name': source['name'],
                            'color': source['color'],
                            'body': body,
                            'picked': False,
                        }
                        # # Handling specially selected objects
                        # if new_sat['name'] == 'TIANGONG 1':
                        #     new_sat['color'] = '#FFFF00'
                        #     print(new_sat)
                        if body_datapart in bodies_dedup:
                            sat_index = bodies_dedup[body_datapart]
                            self.savedsats[sat_index] = new_sat
                            # print("Updated idx {} for '{}'".format(sat_index, body_namepart))
                            print("Updated entry for '{}'".format(body_namepart))
                        else:
                            self.savedsats.append(new_sat)
                            sat_index = len(self.savedsats) - 1
                            bodies_dedup[body_datapart] = sat_index
                    i_name += 1
            print()

    def _parse_coords(self, coords):
        coord_parts = [s.strip() for s in coords.split(',')]
        coord_parts_parsed = []
        test_ephem = ephem.Observer()
        if 2 <= len(coord_parts) <= 3:
            for idx, part in enumerate(coord_parts):
                try:
                    if part[-1].upper() in list('SW'):
                        part = '-' + part
                    if idx == 0:
                        test_ephem.lat = str(part)  # pylint: disable=assigning-non-slot
                    elif idx == 1:
                        test_ephem.lon = str(part)  # pylint: disable=assigning-non-slot
                    elif idx == 2:
                        test_ephem.elevation = float(part)  # pylint: disable=assigning-non-slot
                except ValueError:
                    return None
                coord_parts_parsed.append(part)
        if len(coord_parts) == 2:
            coord_parts_parsed.append(0.0)  # Default elevation
        return coord_parts_parsed

    def get_location(self, given_location=None):
        ''' Get user location based on input '''
        print('Location input examples:')
        print('    "San Francisco, CA, USA"')
        print('    "37.7749295,  -122.4194155,  15.60"')
        print('    "37:46:29.7N, -122:25:09.9E, 15.60"')
        print('')
        input_function = input
        self.home = ephem.Observer()
        coords = None
        while True:
            if given_location:
                print('Given location: "{}"'.format(given_location))
                location_keyword = given_location
                given_location = None
            else:
                location_keyword = input_function(
                    'Enter location ["{}"]: '.format(self.default_location))
            if not location_keyword or location_keyword.isspace():
                location_keyword = self.default_location
            coords = self._parse_coords(location_keyword)
            if coords:
                self.location = location_keyword
                (self.latitude, self.longitude, self.elevation) = coords
                self.elevation = float(self.elevation)
                self.friendly_location = "coordinates"
                break
            else:
                gloc = geocoder.google(location_keyword, key=SECRET_API_KEY)
                print(location_keyword, gloc.status)
                if gloc.status != 'OK':
                    print('Location not found: "{}"'.format(location_keyword))
                    location_keyword = None
                else:
                    self.location = gloc.address
                    if SECRET_API_KEY == '':
                        print("No API key - using default elevation {}m".format(DEFAULT_ELEVATION))
                        self.elevation = DEFAULT_ELEVATION
                    else:
                        for _ in range(MAX_RETRIES):
                            self.elevation = geocoder.elevation(gloc.latlng, key=SECRET_API_KEY).meters
                            if self.elevation is not None:
                                break
                            time.sleep(RETRY_DELAY)
                        else:
                            print("Retries exceeded - using default elevation {}m".format(DEFAULT_ELEVATION))
                            self.elevation = DEFAULT_ELEVATION

                    (self.latitude, self.longitude) = gloc.latlng
                    # (self.latitude, self.longitude) = (gloc.lat, gloc.lng)
                    self.friendly_location = u"{}".format(self.location)
                    # print(gloc.json)
                    print()
                    break
        self.config['main']['default_location'] = self.location
        print(self.elevation)
        self.home.elevation = self.elevation  # meters
        self.home.lat = str(self.latitude)  # +N
        self.home.lon = str(self.longitude)  # +E
        print("Found: {}N, {}E, {:0.2f}m".format(
            self.home.lat, self.home.lon, self.home.elevation))
        self.friendly_location = "{} ({:4.7f}N, {:4.7f}E) {:0.2f}m".format(
            self.friendly_location,
            self.home.lat / ephem.degree,
            self.home.lon / ephem.degree,
            self.home.elevation)
        print("Location: {}".format(self.friendly_location))
        print()

    def plot_sats(self):
        warnings.filterwarnings(
            "ignore",
            ".*Using default event loop until function specific to this GUI is implemented")
        print('-' * 79)
        print()
        self.plt.rcParams['toolbar'] = 'None'
        fig = self.plt.figure()
        DPI = fig.get_dpi()
        fig.set_size_inches(
            int(self.window_size[0]) / float(DPI),
            int(self.window_size[1]) / float(DPI))
        # mng = self.plt.get_current_fig_manager()
        # mng.resize(1600,900)
        fig.canvas.set_window_title(self.win_label)
        self.curr_time = time.time()
        self.curr_date = datetime.utcnow()
        errored_sats = set()
        picked_sats = []
        plotted_sats = []
        last_picked = [None]  # Keep data mutable
        update_lock = threading.Lock()
        close_event = threading.Event()
        ax = None

        def handle_close(event):
            print()
            print("Event received ({:s})".format(event.name))
            close_event.set()
        fig.canvas.mpl_connect('close_event', handle_close)

        def onpick(event):
            ''' These *only* happen with data points get clicked by any button '''
            # print("Picked  in", time.time(), event.mouseevent)
            last_picked[0] = event.mouseevent
            if time.time() - self.curr_time < self.click_wait_s:  # Rate limiting
                return
            self.curr_time = time.time()
            update_lock.acquire(True)
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
            update_lock.release()
            # print("Picked  out", time.time(), event.mouseevent)
        fig.canvas.mpl_connect('pick_event', onpick)

        def onclick(event):
            ''' These follow onpick() events as well '''
            # print("Clicked at", time.time(), event)
            if time.time() - self.curr_time < self.click_wait_s:  # Rate limiting
                return
            self.curr_time = time.time()
            update_lock.acquire(True)
            if last_picked[0] == event:
                pass  # print("Part of last pick")
            else:
                if event.button == 3:
                    for satdata in picked_sats[:]:
                        satdata['picked'] = False
                    del picked_sats[:]
            update_lock.release()
        fig.canvas.mpl_connect('button_press_event', onclick)

        while True:
            if close_event.is_set():
                self.plt.close(fig)
                self.plt.close()
                break
            update_lock.acquire(True)
            if self.secs_per_step:
                self.curr_date += timedelta(seconds=self.secs_per_step)
            else:
                self.curr_date = datetime.utcnow()
            self.home.date = self.curr_date
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
                    # print("Date out of range")
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
            if not ax:
                ax = self.plt.subplot(111, polar=True)
                self.plt.subplots_adjust(left=0.05, right=0.6)
            ax.cla()  # a bit less heavy than self.plt.cla()?
            #TODO: ax2 = self.plt.axes([0.81, 0.05, 0.1, 0.075])
            #TODO: mpl.widgets.Button(ax2, "aButton")
            # def submit(text):
            #     print(text)
            # text_box = mpl.widgets.TextBox(ax2, 'textbox', initial="some text")
            # text_box.on_submit(submit)
            marker = mpl.markers.MarkerStyle(marker='o', fillstyle='full')
            # Note: you can't currently pass multiple marker styles in an array
            ax.scatter(theta_plot, radius_plot, marker=marker,
                       picker=1,  # This sets the tolerance for clicking on a point
                       c=colors, edgecolors=self.color_outline, alpha=self.color_alpha,
                       )
            title_locn = self.friendly_location
            title_date = "{}.{:02d} UTC".format(
                self.curr_date.strftime('%Y-%m-%d %H:%M:%S'),
                int(round(self.curr_date.microsecond / 10000.0)))
            title_stat = "Satellites overhead: {}".format(len(plotted_sats))
            ax.set_title('\n'.join([title_locn, title_date, title_stat]), va='bottom')
            ax.set_facecolor('ivory')
            ax.set_theta_offset(np.pi / 2.0)  # Top = 0 deg = North
            ax.set_theta_direction(-1)  # clockwise
            ax.set_rmax(1.0)
            ax.grid(True)
            ax.xaxis.set_ticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'])
            ax.yaxis.set_ticklabels([])  # hide radial tick labels
            self.notate_sat_data(ax=ax, noted_sats=picked_sats)
            update_lock.release()
            try:
                self.plt.pause(self.update_pause_ms / 1000.0)
            except Exception as e:  # pylint: disable=broad-except
                # Ignore this specific tkinter error on close (intrinsic to pyplot)
                if not(repr(e).startswith("TclError") and
                       str(e).startswith("can't invoke \"update\" command:")
                       ):
                    raise e
                break

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
                )
            )
        if len(notes) <= 1:
            notes.append("(none)")
        ax.annotate(
            '\n'.join(notes),
            xy=(0.0, 0.0),  # theta, radius
            xytext=(math.pi / 2.0, 1.25),    # fraction, fraction
            horizontalalignment='left',
            verticalalignment='center',
        )

    def get_api_key(self):
        global SECRET_API_KEY
        if 'GOOGLE_API_KEY' in os.environ and os.environ['GOOGLE_API_KEY']:
            print(os.environ['GOOGLE_API_KEY'])
            SECRET_API_KEY = os.environ['GOOGLE_API_KEY']
        else:
            if SECRET_API_KEY == '':
                default_text = '<not set>'
            else:
                default_text = '<secret>'
            new_key = getpass.getpass("Enter Google Maps Geocoding API key [{}]: ".format(default_text))
            if new_key != '':
                SECRET_API_KEY = new_key


if __name__ == "__main__":
    print()
    print('-' * 79)

    location_arg = None
    if len(sys.argv) > 1:
        location_arg = sys.argv[1]

    sdv = SatDataViz()
    sdv.get_api_key()
    sdv.get_location(given_location=location_arg)
    sdv.process_tle_data()
    sdv.save_config()
    sdv.plot_sats()

    print()
    print("Exiting...")
