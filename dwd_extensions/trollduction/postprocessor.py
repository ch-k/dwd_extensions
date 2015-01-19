# -*- coding: utf-8 -*-
# 
# Copyright (c) 2014
# 
# Author(s):
# 
#   Panu Lahtinen <panu.lahtinen@fmi.fi>
#   Martin Raspaud <martin.raspaud@smhi.se>
# 
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

'''PostProcessor module

'''

from trollduction.listener import ListenerContainer
from mpop.satellites import GenericFactory as GF
import time
from mpop.projector import get_area_def
import sys
from threading import Thread
from pyorbital import astronomy
import numpy as np
import os
import Queue
import logging
import logging.handlers
from fnmatch import fnmatch
import trollduction.helper_functions as helper_functions
from trollsift import Parser
from posttroll.publisher import NoisyPublisher
from posttroll.message import Message

LOGGER = logging.getLogger(__name__)

# Config watcher stuff

import pyinotify

# Generic event handler

class EventHandler(pyinotify.ProcessEvent):
    """Handle events with a generic *fun* function.
    """

    def __init__(self, fun, file_to_watch=None, item=None):
        pyinotify.ProcessEvent.__init__(self)
        self._file_to_watch = file_to_watch
        self._item = item
        self._fun = fun

    def process_file(self, pathname):
        '''Process event *pathname*
        '''
        if self._file_to_watch is None:
            self._fun(pathname, self._item)
        elif fnmatch(self._file_to_watch, os.path.basename(pathname)):
            self._fun(pathname, self._item)

    def process_IN_CLOSE_WRITE(self, event):
        """On closing after writing.
        """
        self.process_file(event.pathname)

    def process_IN_CREATE(self, event):
        """On closing after linking.
        """
        try:
            if os.stat(event.pathname).st_nlink > 1:
                self.process_file(event.pathname)
        except OSError:
            return

    def process_IN_MOVED_TO(self, event):
        """On closing after moving.
        """
        self.process_file(event.pathname)

class ConfigWatcher(object):
    """Watch a given config file and run reload_config.
    """

    def __init__(self, config_file, config_item, reload_config):
        mask = (pyinotify.IN_CLOSE_WRITE |
            pyinotify.IN_MOVED_TO |
            pyinotify.IN_CREATE)
        self.config_file = config_file
        self.config_item = config_item
        self.watchman = pyinotify.WatchManager()

        LOGGER.debug("Setting up watcher for %s", config_file)

        self.notifier = \
            pyinotify.ThreadedNotifier(self.watchman,
                                       EventHandler(reload_config,
                                                    os.path.basename(config_file
                                                                     ),
                                                    self.config_item
                                                    )
                                       )
        self.watchman.add_watch(os.path.dirname(config_file), mask)

    def start(self):
        """Start the config watcher.
        """
        LOGGER.info("Start watching %s", self.config_file)
        self.notifier.start()

    def stop(self):
        """Stop the config watcher.
        """
        LOGGER.info("Stop watching %s", self.config_file)
        self.notifier.stop()

class DataProcessor(object):
    """Process the data.
    """
    def __init__(self):
        self.product_config = None
        self._data_ok = True
        self.writer = DataWriter()
        self.writer.start()

    def run(self, product_config, msg):
        """Process the data
        """
        LOGGER.info('New data available: %s', msg.data['product_filename'])

        self._data_ok = True
        self.product_config = product_config

        t1a = time.time()
                 #   self.writer.write(self.write_netcdf, 'local_data')
      

        LOGGER.info('pr %.1f s', (time.time()-t1a))

        # Wait for the writer to finish
        if self._data_ok:
            LOGGER.debug("Waiting for the files to be saved")
        self.writer.prod_queue.join()
        if self._data_ok:
            LOGGER.debug("All files saved")

            LOGGER.info('File %s processed in %.1f s', msg.data['product_filename'],
                        time.time() - t1a)

        if not self._data_ok:
            LOGGER.warning("File %s not processed due to " \
                           "incomplete/missing/corrupted data." % \
                           msg.data['product_filename'])

    def create_info_dict(self, area=None, product=None):
        '''create info dictionary.  Parameter *area* is for area-level
        configuration dictionary, *product* for product-level
        configuration dictionary.  
        '''

        try:
            time_slot = self.local_data.time_slot
        except AttributeError:
            time_slot = self.global_data.time_slot

        info_dict = {}
        info_dict['time'] = time_slot

        if area is not None:
            info_dict['areaname'] = area['name']
        else:
            info_dict['areaname'] = ''

        if product is not None:
            info_dict['composite'] = product['name']
        else:
            info_dict['composite'] = ''

        info_dict['platform'] = self.global_data.info['satname']
        info_dict['satnumber'] = self.global_data.info['satnumber']

        if self.global_data.info['orbit'] is not None:
            info_dict['orbit'] = self.global_data.info['orbit']
        else:
            info_dict['orbit'] = ''

        info_dict['instrument'] = self.global_data.info['instrument']

        return info_dict

    
    def parse_filename(self, area=None, product=None, fname_key='filename'):
        '''Parse filename for saving.  Parameter *area* is for area-level
        configuration dictionary, *product* for product-level
        configuration dictionary.  Parameter *fname_key* tells which
        dictionary key holds the filename pattern.
        '''
        try:
            out_dir = product['output_dir']
        except (KeyError, TypeError):
            try:
                out_dir = area['output_dir']
            except (KeyError, TypeError):
                out_dir = self.product_config['common']['output_dir']

        try:
            fname = product[fname_key]
        except (KeyError, TypeError):
            try:
                fname = area[fname_key]
            except (KeyError, TypeError):
                fname = self.product_config['common'][fname_key]

        fname = os.path.join(out_dir, fname)

        par = Parser(fname)
        try:
            time_slot = self.local_data.time_slot
        except AttributeError:
            time_slot = self.global_data.time_slot


        info_dict = self.create_info_dict(area, product)
       
        info_dict['file_ending'] = 'png'

        fname = par.compose(info_dict)

        return fname


class DataWriter(Thread):
    """Writes data to disk.

    This is separate from the DataProcessor since it IO takes time and we don't
    want to block processing.
    """
    def __init__(self):
        Thread.__init__(self)
        self.prod_queue = Queue.Queue()
        self._loop = True

    def run(self):
        """Run the thread.
        """
        while self._loop:
            try:
                fun, args, kwargs = self.prod_queue.get(True, 1)
            except Queue.Empty:
                pass
            else:
                fun(*args, **kwargs)
                self.prod_queue.task_done()

    def write(self, fun, *args, **kwargs):
        '''Write to queue.
        '''
        self.prod_queue.put((fun, args, kwargs))

    def stop(self):
        '''Stop the data writer.
        '''
        LOGGER.info("stopping data writer")
        self._loop = False

from trollduction.minion import Minion

class PostProcessor(Minion):
    """PostProcessor takes in messages and generates DataProcessor jobs.
    """

    def __init__(self, config, managed=True):
        LOGGER.debug("Minion should be starting now")
        Minion.__init__(self)

        self.td_config = None
        self.product_config = None
        self.listener = None

        self.global_data = None
        self.local_data = None

        self._loop = True
        self.thr = None
        self.config_watcher = None

        # read everything from the Trollduction config file
        try:
            self.update_td_config_from_file(config['config_file'],
                                            config['config_item'])
            
            self.data_processor = DataProcessor()
            
            if not managed:
                self.config_watcher = \
                    ConfigWatcher(config['config_file'],
                                  self.update_td_config_from_file)
                self.config_watcher.start()

        except AttributeError:
            self.td_config = config
            self.update_td_config()
        Minion.start(self)

    # def start(self):
        # Minion.start(self)
        # self.thr = Thread(target=self.run_single).start()

    def update_td_config_from_file(self, fname, config_item=None):
        '''Read Trollduction config file and use the new parameters.
        '''
        self.td_config = helper_functions.read_config_file(fname, config_item)
        self.update_td_config()

    def update_td_config(self):
        '''Setup Trollduction with the loaded configuration.
        '''

        LOGGER.info('Trollduction configuration read successfully.')

        # Initialize/restart listener
        if self.listener is None:
            self.listener = \
                            ListenerContainer(topic=\
                                              self.td_config['td_product_finished_topic'])
#            self.listener = ListenerContainer()
            LOGGER.info("Listener started")
        else:
#            self.listener.restart_listener('file')
            self.listener.restart_listener(self.td_config['td_product_finished_topic'])
            LOGGER.info("Listener restarted")

        try:
            self.update_product_config(self.td_config['product_config_file'], \
                                       self.td_config['config_item'])
        except KeyError:
            print ""
            print self.td_config
            print ""
            LOGGER.critical("Key 'product_config_file' or 'config_item' is "
                            "missing from Trollduction config")

    def update_product_config(self, fname, config_item):
        '''Update area definitions, associated product names, output
        filename prototypes and other relevant information from the
        given file.
        '''

        product_config = \
                         helper_functions.read_config_file(fname,
                                                           config_item=\
                                                           config_item)

        # add checks, or do we just assume the config to be valid at
        # this point?
        self.product_config = product_config
        if self.td_config['product_config_file'] != fname:
            self.td_config['product_config_file'] = fname

        LOGGER.info('Product config read from %s', fname)


    def cleanup(self):
        '''Cleanup Trollduction before shutdown.
        '''

        LOGGER.info('Shutting down Trollduction.')

        # more cleanup needed?
        self._loop = False
        self.data_processor.writer.stop()
        self.data_processor._pub.stop()
        if self.config_watcher is not None:
            self.config_watcher.stop()
        if self.listener is not None:
            self.listener.stop()


    def stop(self):
        """Stop running.
        """
        self.cleanup()
        Minion.stop(self)

    def shutdown(self):
        '''Shutdown trollduction.
        '''
        self.stop()

    def run_single(self):
        """Run trollduction.
        """
        while self._loop:
            # wait for new messages
            try:
                msg = self.listener.queue.get(True, 5)
            except KeyboardInterrupt:
                LOGGER.info('Keyboard interrupt detected')
                self.stop()
                raise
            except Queue.Empty:
                continue

            # For 'file' type messages, update product config and run
            # production
            if msg.type == "file":
                self.update_product_config(self.td_config['product_config_file'],
                                           self.td_config['config_item'])
                self.data_processor.run(self.product_config, msg)
#            else:
#                LOGGER.debug("Message type was %s" % msg.type)
