# -*- coding: utf-8 -*-
#
# Copyright (c) 2015
#
# Author(s):
#
#   Panu Lahtinen <panu.lahtinen@fmi.fi>
#   Martin Raspaud <martin.raspaud@smhi.se>
#   Christian Kliche <chk@ebp.de>
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

import Queue
import datetime
from dwd_extensions.layout import LayoutHandler
from dwd_extensions.tools.config_watcher import ConfigWatcher
import logging
from mpop.projector import get_area_def
import os
import re
import shutil
from threading import Thread
import time
from trollduction.listener import ListenerContainer
from trollsift import Parser
from urlparse import urlparse

from dwd_extensions.tools.image_io import read_image
import mpop.imageo.geo_image as geo_image
import numpy as np
import trollduction.helper_functions as helper_functions
try:
    import rrdtool as rrd
except ImportError:
    rrd = None

LOGGER = logging.getLogger("postprocessor")


def to_unix_seconds(dt):
    return int(dt.strftime("%s"))


class DataProcessor(object):

    """Process the data.
    """

    def __init__(self):
        self.product_config = None
        self._data_ok = True
        self.rrd_dir = 'rrd'
        self.writer = DataWriter()
        self.writer.start()
        self.layout_handler = None

    def set_config(self, product_config):
        self.product_config = product_config
        self.out_boxes = dict()
        self.rules = []
        self.dataset_processors = []
        
        for key, values in product_config['post_processing'].iteritems():
            if key == 'rrd_dir':
                self.rrd_dir = values
            else:
                for value in values:
                    if key == 'out_box':
                        self.out_boxes[value['name']] = value
                    elif key == 'rule':
                        # in case of only one rule is defined
                        if (isinstance(value, str)):
                            self.rules.append(values)
                        else:
                            self.rules.append(value)
                    elif key == 'dataset_processor':
                        # in case of only one dataset_processors is defined
                        if (isinstance(value, str)):
                            self.dataset_processors.append(values)
                        else:
                            self.dataset_processors.append(value)

    def save_img(self, geo_img, src_fname, dest_fname, rrd_fname, rrd_steps, params):
        save_params = self.get_save_arguments(params)
        dest_dir = os.path.dirname(dest_fname)
        # first write to file with prefix "." (to ensure that
        # 3rd party software do not read incomplete files (i.e. AFD)
        tmp_fname = os.path.join(dest_dir,
                                 '.' + os.path.basename(dest_fname))
        if geo_img is None and src_fname is not None:
            LOGGER.info("Copying file only from %s to %s",
                        src_fname, dest_fname)
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            shutil.copy(src_fname, tmp_fname)
        else:
            geo_img.save(tmp_fname, **save_params)
        # rename after writing is complete
        os.rename(tmp_fname, dest_fname)

        # writing performance data to rrd file
        if rrd is not None:
            if os.path.exists(dest_fname):
                timeslot = to_unix_seconds(params['time_eos'])
                if not os.path.exists(rrd_fname):
                    rrd.create(rrd_fname,
                               '--start', str(timeslot - rrd_steps),
                               # step size 900s=15min
                               # each step represents one time slot
                               '--step', str(rrd_steps),
                               ['DS:epi2product:GAUGE:' + str(rrd_steps) + ':U:U',
                                'DS:timeslot2product:GAUGE:' + str(rrd_steps) + ':U:U'],
                               'RRA:MAX:0.5:1:1',
                               # keep 15 min max for 1 day
                               'RRA:MAX:0.5:1:1d',
                               # hourly average over 7 days
                               'RRA:AVERAGE:0.5:1h:7d',
                               # hourly maximum over 90 days
                               'RRA:MAX:0.5:1h:7d',
                               # hourly minimum over 90 days
                               'RRA:MIN:0.5:1h:7d',
                               # daily average over 90 days
                               'RRA:AVERAGE:0.5:1d:90d',
                               # daily maximum over 90 days
                               'RRA:MAX:0.5:1d:90d',
                               # daily minimum over 90 days
                               'RRA:MIN:0.5:1d:90d')

                skip = False
                try:
                    t_epi = os.path.getmtime(params['source_uri'])
                except Exception as e:
                    LOGGER.error(
                        "Could not read modification time of {0} ({1})".format(
                            params['source_uri'], e))
                    skip = True
                try:
                    t_product = os.path.getmtime(dest_fname)
                except Exception as e:
                    LOGGER.error(
                        "Could not read modification time of {0} ({1})".format(
                            dest_fname, e))
                    skip = True

                if skip is False:
                    try:
                        update_stmt = str(timeslot) +\
                            ':' + str(int(t_product - t_epi)) +\
                            ':' + str(int(t_product - timeslot))
                        LOGGER.debug(
                            "rrd update %s %s" % (rrd_fname, update_stmt))
                        rrd.update(rrd_fname, update_stmt)
                    except Exception as e:
                        LOGGER.error(
                            "Could not update rrd file. ({0})".format(e))
        else:
            LOGGER.info("skipping rrd update (no rrdtool found)")

    def run(self, product_config, msg, config_dir):
        """Process the data
        """
        LOGGER.info('New data available: type = %s', msg.type)
        
        self._data_ok = True
        self.set_config(product_config)
        self.layout_handler = LayoutHandler(product_config, config_dir)
        
        if msg.type in ['dataset']:
            for ds_proc in self.dataset_processors:
                if re.match(ds_proc['msg_subject_pattern'], msg.subject):
                    module_name, function_name = ds_proc['processing_function'].split('|')
                    func = get_custom_function(module_name, function_name)
                    geo_img = func(msg)
                    in_filename_base = ds_proc['output_name']
                    in_filename = None
                    break
            if geo_img is None:
                LOGGER.warning("no image created by dataset_processpor")
        else:
            geo_img = None

            LOGGER.info('uri: %s', msg.data['uri'])
            
            p = urlparse(msg.data['uri'])
            if p.netloc != '':
                LOGGER.error('uri not supported: {0}'.format(msg.data['uri']))
                return
    
            in_filename = p.path
            in_filename_base = os.path.basename(in_filename)
            
        rules_to_apply = []
        rules_to_apply_groups = set()
        copy_src_file_only = True
        # find matching rules
        for rule in self.rules:
            pattern = rule['input_pattern']
            if re.match(pattern, in_filename_base):
                # if fnmatch(in_filename_base, pattern):
                if 'rule_group' in rule:
                    rg = rule['rule_group']
                    if rg in rules_to_apply_groups:
                        continue
                    else:
                        rules_to_apply_groups.add(rg)

                LOGGER.info("Rule match (%s)" % rule)
                rules_to_apply.append(rule)

                if rule.get('copySrcFileOnly', 'false').lower() not in ["true",
                                                                        "yes",
                                                                        "1"]:
                    copy_src_file_only = False

        if len(rules_to_apply) > 0:
            t1a = time.time()

            # load image
            area = get_area_def(msg.data['area']['name'])

            # load image only when necessary
            if geo_img is None:
                if not copy_src_file_only:
                    geo_img = read_image(in_filename, area,
                                         msg.data['time_eos'])

            # and apply each rule
            for rule in rules_to_apply:
                params = self.merge_and_resolve_parameters(msg,
                                                           rule)

                box_out_dir = self.out_boxes[rule['out_box_ref']]['output_dir']
                fname_pattern = rule['dest_filename']
                fname = self.create_filename(fname_pattern,
                                             box_out_dir,
                                             params)

                if not os.path.exists(self.rrd_dir):
                    os.makedirs(self.rrd_dir)
                rrd_fname = self.create_filename(re.sub(r"\{time.*\}",
                                                        "xx",
                                                        fname_pattern) +
                                                 ".rrd",
                                                 self.rrd_dir,
                                                 params)
                rrd_steps = int(rule.get('rrd_steps', '900'))

                # todo:  layouting etc
#                 try:
#                     self.layout_handler.layout(geo_img, area)
#                 except ValueError as e:
#                     LOGGER.error("Layouting failed: " + str(e))
                if rule.get('copySrcFileOnly', 'false').lower() in ["true",
                                                                    "yes",
                                                                    "1"]:
                    # copy inputput file only
                    rule_geo_img = None
                else:
                    rule_geo_img = geo_img

                self.writer.write(self.save_img,
                                  rule_geo_img,
                                  in_filename,
                                  fname,
                                  rrd_fname,
                                  rrd_steps,
                                  params)

            LOGGER.info('pr %.1f s', (time.time() - t1a))

            # Wait for the writer to finish
            if self._data_ok:
                LOGGER.debug("Waiting for the files to be saved")
            self.writer.prod_queue.join()
            if self._data_ok:
                LOGGER.debug("All files saved")

                LOGGER.info(
                    'File %s processed in %.1f s', in_filename,
                    time.time() - t1a)

            if not self._data_ok:
                LOGGER.warning("File %s not processed due to "
                               "incomplete/missing/corrupted data." %
                               msg.data['product_filename'])
        else:
            LOGGER.warning(
                "no matching rule found for %s" % in_filename)

    def get_save_arguments(self, rule):
        save_kwords = {}

        # check if a certain format is specified
        if 'format' in rule:
            save_kwords['fformat'] = rule['format']

        if 'format_params' in rule:
            save_kwords.update(rule['format_params'])

        # set some defaults
        if 'compression' not in save_kwords:
            save_kwords['compression'] = 6

        if 'blocksize' not in save_kwords:
            save_kwords['blocksize'] = 0

        if 'inv_def_temperature_cmap' not in save_kwords:
            save_kwords['inv_def_temperature_cmap'] = False

        if 'omit_filename_path' not in save_kwords:
            save_kwords['omit_filename_path'] = True

        return save_kwords

    def create_filename(self, fname_pattern, dir_pattern, params=None):
        '''Parse filename for saving.
        '''
        fname = os.path.join(dir_pattern, fname_pattern)
        par = Parser(fname)
        fname = par.compose(params)
        return fname

    def merge_and_resolve_parameters(self, msg, rule):
        ''' creates parameters dictionary based on data received via posttroll
            and rule and resolves enclosed variables
        '''
        params = dict((k, v) for k, v in msg.data.items())
        params.update(rule)

        product_name = None
        if 'product_name' in params:
            product_name = params['product_name']
        elif 'productname' in params:
            product_name = params['productname']
        else:
            print "no product_name key"

        # special addition to simplify rules
        params['productname_no_underscore'] =\
            product_name.replace('_', '')
        params['product_name_no_underscore'] =\
            product_name.replace('_', '')
        params['productname'] = product_name
        params['product_name'] = product_name

        params['areaname'] = params['area']['name']

        if 'time' in params:
            t = params['time']
            t_eos = t + datetime.timedelta(minutes=15)  # @UndefinedVariable
            params['time_eos'] = t_eos
        else:
            print "no time key"

        return self._resolve(params, params)
#         resolved_params = dict()
#         for k, v in params.items():
#             # take only string parameters
#             if isinstance(v, (str, unicode)):
#                 par = Parser(v)
#                 resolved_params[k] = par.compose(params)
#             else:
#                 resolved_params[k] = v
#
#         return resolved_params

    def _resolve(self, params, ref_params):
        resolved_params = dict()
        for k, v in params.items():
            # take only string parameters
            if isinstance(v, (str, unicode)):
                par = Parser(v)
                resolved_params[k] = par.compose(ref_params)
            elif isinstance(v, dict):
                resolved_params[k] = self._resolve(v, ref_params)
            else:
                resolved_params[k] = v

        return resolved_params


def get_custom_function(module_name, function_name):
    """Get the home made methods for building composites for a given satellite
    or instrument *name*.
    """
    return getattr(__import__(module_name, globals(), locals(), [function_name]), function_name)


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
                fun = None
                args = None
                kwargs = None
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

# from trollduction.minion import Minion


# class PostProcessor(Minion):
class PostProcessor(object):

    """PostProcessor takes in messages and generates DataProcessor jobs.
    """

    def __init__(self, config, managed=True):
        LOGGER.debug("Minion should be starting now")
        # Minion.__init__(self)

        self.stop_called = False
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
        # Minion.start(self)

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
            self.listener = ListenerContainer(
                topics=self.td_config['td_product_finished_topic'].split(','))
#            self.listener = ListenerContainer()
            LOGGER.info("Listener started")
        else:
            #            self.listener.restart_listener('file')
            self.listener.restart_listener(
                self.td_config['td_product_finished_topic'].split(','))
            LOGGER.info("Listener restarted")

        try:
            self.update_product_config(self.td_config['product_config_file'],
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
                                              config_item=config_item)

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
        if self.data_processor is not None:
            self.data_processor.writer.stop()
        if self.config_watcher is not None:
            self.config_watcher.stop()
            self.config_watcher = None
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
        if self.data_processor is not None:
            self.data_processor = None

    def stop(self):
        """Stop running.
        """
        if self.stop_called is False:
            self.stop_called = True
            self.cleanup()
            # Minion.stop(self)

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
            if msg.type in ["file", "dataset"]:
                self.update_product_config(
                    self.td_config['product_config_file'],
                    self.td_config['config_item'])
                self.data_processor.run(
                    self.product_config,
                    msg,
                    os.path.dirname(self.td_config['product_config_file']))
#            else:
#                LOGGER.debug("Message type was %s" % msg.type)
