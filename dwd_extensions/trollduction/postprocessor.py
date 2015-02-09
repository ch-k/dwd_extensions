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
from PIL import Image


LOGGER = logging.getLogger("postprocessor")

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


def read_geotiff(filename):
    from osgeo import gdal, osr
    logger = LOGGER
    
    dst = gdal.Open(filename)

    #
    # Dataset information
    #
    geotransform = dst.GetGeoTransform()
    projection = dst.GetProjection()
    metadata = dst.GetMetadata()

    logger.debug('description: %s'%dst.GetDescription())
    logger.debug('driver: %s / %s'%(dst.GetDriver().ShortName,
                                    dst.GetDriver().LongName))
    logger.debug('size: %d x %d x %d'%(dst.RasterXSize, dst.RasterYSize,
                                       dst.RasterCount))
    logger.debug('geo transform: %s'%str(geotransform))
    logger.debug('origin: %.3f, %.3f'%(geotransform[0], geotransform[3]))
    logger.debug('pixel size: %.3f, %.3f'%(geotransform[1], geotransform[5]))
    logger.debug('projection: %s'%projection)
    logger.debug('metadata: %s', metadata)

    #
    # Fetching raster data
    #
    bands_data = []
    for i in xrange(1,dst.RasterCount+1):
        band = dst.GetRasterBand(i)
        logger.info('Band(%d) type: %s, size %d x %d'%(i,
                gdal.GetDataTypeName(band.DataType),
                dst.RasterXSize, dst.RasterYSize))
        shape = (dst.RasterYSize, dst.RasterXSize)
        if band.GetOverviewCount() > 0:
            logger.debug('overview count: %d'%band.GetOverviewCount())
        if not band.GetRasterColorTable() is None:
            logger.debug('colortable size: %d'%
                         band.GetRasterColorTable().GetCount())
    
        data = band.ReadAsArray(0, 0, shape[1], shape[0])
        logger.info('fetched array: %s %s %s [%d -> %.2f -> %d]'%
                    (type(data), str(data.shape), data.dtype,
                     data.min(), data.mean(), data.max()))
        bands_data.append(data)

    params = dict((('geotransform', geotransform),
                   ('projection', projection),
                   ('metadata', metadata)))

    return params, bands_data


class DataProcessor(object):
    """Process the data.
    """
    def __init__(self):
        self.product_config = None
        self._data_ok = True
        self.writer = DataWriter()
        self.writer.start()
        
    def set_config(self, product_config):
        self.product_config = product_config
        self.out_boxes = dict()
        self.rules = dict()
        for key, values in product_config['post_processing'].iteritems():
            for value in values: 
                if key == 'out_box':
                    self.out_boxes[value['name']] = value
                elif key == 'rule':
                    self.rules[value['input_pattern']] = value
                    

    def read_image(self, filename, area, timeslot):
        channels = []
        params, bands_data = read_geotiff(filename)
        for data in bands_data:
            arr = np.array(data)
            channels.append(np.ma.array(arr[:, :] / 255.0))
            
        if len(channels) == 1:
            mode = "L"
            fill_value=(0)
        else:
            mode = "RGB"
            fill_value=(0, 0, 0)
        
        import mpop.imageo.geo_image as geo_image
        geo_img = geo_image.GeoImage(tuple(channels),
                     area,
                     timeslot,
                     fill_value=fill_value,
                     mode=mode)
        return geo_img

    def save_img(self, geo_img, fname, **kwargs):
        geo_img.save(fname, **kwargs)
        
    def run(self, product_config, msg):
        """Process the data
        """
        LOGGER.info('New data available: %s', msg.data['product_filename'])

        t1a = time.time()

        self._data_ok = True
        self.set_config(product_config)
        
        in_filename = msg.data['product_filename'] 
        in_filename_base = os.path.basename(in_filename)
        rules_to_apply = []
        
        # find matching rules 
        for pattern, rule in self.rules.iteritems():
            if fnmatch(in_filename_base, pattern):
                LOGGER.info("Rule match (%s)" % rule)
                rules_to_apply.append(rule)
        
        if len(rules_to_apply) > 0:
                # load image
                area = get_area_def(msg.data['areaname'])
                geo_img = self.read_image(in_filename, area, msg.data['time'])
                name_params = dict((k,v) for k,v in msg.data.items())
                
                # and apply each rule
                for rule in rules_to_apply:
                    box_out_dir = self.out_boxes[rule['out_box_ref']]\
                    ['output_dir']
                    fname = self.create_filename(rule['dest_filename'],
                                                 box_out_dir,
                                                 name_params)
                    self.writer.write(self.save_img, 
                                  geo_img, 
                                  fname, 
                                  **self.get_save_arguments(rule))

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
            
    def get_save_arguments(self, rule):
        save_kwords = {}
        
        # check if a certain format is specified
        if 'format' in rule:
            save_kwords['fformat'] = rule['format']
             
        # check if a special physical unit is required   
        if 'physical_unit' in rule:
            save_kwords['physic_unit'] = rule['physical_unit']
                
        # check if a specific ninjo product name is given
        if 'ninjo_product' in rule:
            save_kwords['ninjo_product_name'] = rule['ninjo_product']
            
        # check if there is a satid is defined
        if 'sat_id' in rule:
            save_kwords['sat_id'] = rule['sat_id']

        return save_kwords

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

    
    def create_filename(self, fname_pattern, dir_pattern, params=None):
        '''Parse filename for saving.
        '''
        fname = os.path.join(dir_pattern, fname_pattern)
        par = Parser(fname)
        fname = par.compose(params)
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
