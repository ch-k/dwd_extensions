"""
Created on 17.09.2015

@author: Christian Kliche <chk@ebp.de>
"""
import multiprocessing
import mmap
import glob
import os
import logging
import numpy as np
from mpop.channel import Channel
from mpop.projector import get_area_def
from dwd_extensions.tools.config_watcher import ConfigWatcher

LOGGER = logging.getLogger(__name__)


class AsyncProcessor(object):
    """ executes functions in forked process and offers
    access to computation results
    """
    def __init__(self):
        self.worker_process = None
        self.multiproc_mgr = multiprocessing.Manager()
        self.results = self.multiproc_mgr.dict()
        self.call_params = self.multiproc_mgr.dict()

    def _start(self, async_function, async_function_args, result_key):
        """Starts a new worker_process
        """
        if self.worker_process is not None and self.worker_process.is_alive():
            self.worker_process.join()

        self.call_params['async_function'] = async_function
        self.call_params['async_function_args'] = async_function_args
        self.worker_process = multiprocessing.Process(
            target=self._call_async_function,
            args=(self.call_params, self.results, result_key)
        )
        self.worker_process.start()

    def join(self):
        """Calls join method on the calculation worker_process.
        """
        if self.worker_process is not None:
            self.worker_process.join()

    def get_result(self, result_key):
        """Returns the calculation result for a key.
        """
        return self.results.get(result_key, None)

    def _call_async_function(self, call_params, results,
                             result_key):
        async_function = call_params['async_function']
        async_function_args = call_params['async_function_args']
        results[result_key] = async_function(*async_function_args)


class ViewZenithFromTleAsyncProcessor(AsyncProcessor):
    """Handles the satellite zenith angles calculation.
    Computations are based on TLE files
    """
    def __init__(self, tle_path, aliases):
        super(ViewZenithFromTleAsyncProcessor, self).__init__()
        self.tle_path = tle_path
        self.aliases = aliases

    def _get_sat_name(self, platform, sat_number):
        """Returns the complete satellite name including its alias
        for TLE file parsing.
        """
        sat_name = platform + "-" + sat_number
        try:
            for key, val in self.aliases['platform'].iteritems():
                if val.upper() == platform.upper():
                    sat_name += " (" + key + '-'
                    break
            for key, val in self.aliases['satnumber'].iteritems():
                if val == sat_number:
                    sat_name += key + ")"
                    break
        except:
            pass
        return sat_name.upper()

    def _check_tle_file(self, tle_file, sat_name):
        """Returns True if the given tle file contains the corresponding
        satellite name; False otherwise.
        """
        with open(tle_file, 'r') as f:
            mm = mmap.mmap(f.fileno(), 0, prot=mmap.PROT_READ)
            if mm.find(sat_name) > -1:
                return True
        return False

    def get_tle_file(self, platform, sat_number):
        """Returns the most recent TLE file containing the
        corresponding satellite data.
        """
        sat_name = self._get_sat_name(platform, sat_number)
        files = glob.glob(os.path.join(self.tle_path, '*.tle'))
        files.sort(key=os.path.getctime)
        for i in reversed(range(len(files))):
            tle_file = files[i]
            if self._check_tle_file(tle_file, sat_name):
                return tle_file
        return ''

    def start(self, tle_file, area_def_name, time_slot, platform, sat_number):
        """Starts a new worker_process for satellite zenith angle calculation.
        """
        sat_name = self._get_sat_name(platform, sat_number)
        AsyncProcessor._start(self,
                              async_function=get_view_zen_angles,
                              async_function_args=(sat_name,
                                                   tle_file,
                                                   area_def_name,
                                                   time_slot),
                              result_key=area_def_name)


class ViewZenithFromSubLonAsyncProcessor(AsyncProcessor):
    """Handles the satellite zenith angles calculation.
    Based on longitude of sub satellite point. Primary purpose
    is to calculate satellite zenith angles for geostationary
    satellites
    """
    def __init__(self):
        super(ViewZenithFromSubLonAsyncProcessor, self).__init__()

    def start(self, sublon, area_def_name):
        """Starts a new worker_process for satellite zenith angle calculation.
        """
        AsyncProcessor._start(self,
                              async_function=get_geostationary_view_zen_angles,
                              async_function_args=(sublon,
                                                   area_def_name),
                              result_key=area_def_name)


class ViewZenithAngleCacheManager(object):
    """ Creates and caches view zenith angles asynchronously
    for further images corrections
    """
    def __init__(self, tle_path, aliases):
        self.tle_watcher = None
        # has to be synchronized in case of multiple DataProcessors
        self.view_zen_data_cache = {}
        self.processing = False
        self.area_def_name = None
        self.tle_path = tle_path
        self.aliases = aliases
        self.tle_watcher = ConfigWatcher(
            tle_path,
            None,
            self._set_tle_file)
        self.tle_watcher.start()

        self._set_tle_file(tle_path)
        self.tle_processor = None
        self.sublon_processor = None

    def _init_tle_processor(self):
        if self.tle_processor is None:
            self.tle_processor = ViewZenithFromTleAsyncProcessor(self.tle_path,
                                                                 self.aliases)

    def _init_sublon_processor(self):
        if self.sublon_processor is None:
            self.sublon_processor = ViewZenithFromSubLonAsyncProcessor()

    def prepare(self, msg, area_def_name, time_slot):
        self.is_geo = msg.data['orbit_number'] is None
        if self.is_geo:
            LOGGER.info("no orbit defined, assuming geostationary satellite "
                        "(vza based on sublon parameter provided by sat data)")
        else:
            LOGGER.info("orbit defined, assuming non-geostationary satellite "
                        "(vza based on tle files)")

        if self.is_geo:
            self._prepare_sublon(msg, area_def_name, time_slot)
        else:
            self._prepare_tle(msg, area_def_name, time_slot)

    def _prepare_sublon(self, msg, area_def_name, time_slot):
        self.area_def_name = area_def_name

    def _prepare_tle(self, msg, area_def_name, time_slot):
        # retrieve the satellite zenith angles for the corresponding area
        cached_filename = self.view_zen_data_cache.get('tle_filename', '')
        if cached_filename != os.path.basename(self.tle_file):
            # get the checked tle file which can differ
            # from the most recent one
            tle_file = self.tle_processor.get_tle_file(
                msg.data['platform'], msg.data['satnumber'])
            if tle_file != self.tle_file:
                self.tle_file = tle_file
            if cached_filename != os.path.basename(tle_file):
                # reset the cached data
                self.view_zen_data_cache.clear()
                self.view_zen_data_cache['tle_filename'] = \
                    os.path.basename(tle_file)

        self.processing = False
        self.area_def_name = area_def_name

        if area_def_name not in self.view_zen_data_cache:
            if not self.view_zen_data_cache.get('tle_filename', ''):
                LOGGER.error("Missing TLE file with valid satellite " +
                             "data " + msg.data['platform'] + "-" +
                             msg.data['satnumber'])
            else:
                LOGGER.debug(
                    "starting view zenith angle data processing for " +
                    area_def_name + " using TLE file " +
                    self.view_zen_data_cache['tle_filename'])
                self._init_tle_processor()
                self.processing = True
                self.tle_processor.start(
                    os.path.join(os.path.dirname(self.tle_file),
                                 self.view_zen_data_cache['tle_filename']),
                    area_def_name,
                    time_slot,
                    msg.data['platform'],
                    msg.data['satnumber'])

    def notify_channels_loaded(self, channels):
        if self.is_geo:
            self._notify_channels_loaded_sublon(channels)
        else:
            self._notify_channels_loaded_tle(channels)

    def _notify_channels_loaded_tle(self, channels):
        pass

    def _notify_channels_loaded_sublon(self, channels):
        sublon = None
        sublons = set([x for x in
                       [ch.info.get('sublon', None) for ch in channels]
                       if x is not None])
        if not sublons:
            LOGGER.error(
                'no sublon values found in loaded channels')
        else:
            if len(sublons) > 1:
                LOGGER.error(
                    'multiple different sublon values '
                    'found in loaded channels: %s' % sublons)
            sublon = sublons.pop()

        cache_sublon_key = 'sublon'
        cached_sublon = self.view_zen_data_cache.get(cache_sublon_key, None)
        if cached_sublon != sublon:
            self.view_zen_data_cache.clear()
            self.view_zen_data_cache[cache_sublon_key] = sublon

        self.processing = False

        if self.area_def_name not in self.view_zen_data_cache:
                LOGGER.debug(
                    "starting view zenith angle data processing for %s "
                    "using sublon %s", self.area_def_name, sublon)
                self._init_sublon_processor()
                self.processing = True
                self.sublon_processor.start(sublon, self.area_def_name)

    def waitForViewZenithChannel(self):
        if self.is_geo:
            return self._wait_for_view_zenith_ch_sublon()
        else:
            return self._wait_for_view_zenith_ch_tle()

    def _wait_for_view_zenith_ch_tle(self):
        # wait for the satellite zenith angle calculation worker_process
        if self.processing is True:
            self.tle_processor.join()
            self.view_zen_data_cache[self.area_def_name] = \
                self.tle_processor.get_result(self.area_def_name)
            LOGGER.debug(
                "finished view zenith angle data processing for " +
                self.area_def_name)

        # provide satellite zenith angle data as channel in local_data
        vza_chn = Channel(
            name=self.area_def_name + "_VZA",
            data=self.view_zen_data_cache.get(self.area_def_name, None))

        return vza_chn

    def _wait_for_view_zenith_ch_sublon(self):
        # wait for the satellite zenith angle calculation worker_process
        if self.processing is True:
            self.sublon_processor.join()
            self.view_zen_data_cache[self.area_def_name] = \
                self.sublon_processor.get_result(self.area_def_name)
            LOGGER.debug(
                "finished view zenith angle data processing for " +
                self.area_def_name)

        # provide satellite zenith angle data as channel in local_data
        vza_chn = Channel(
            name=self.area_def_name + "_VZA",
            data=self.view_zen_data_cache.get(self.area_def_name, None))

        return vza_chn

    def shutdown(self):
        if self.tle_watcher is not None:
            self.tle_watcher.stop()
            self.tle_watcher = None
        if self.tle_processor is not None:
            self.tle_processor.multiproc_mgr.shutdown()
            self.tle_processor = None
        if self.sublon_processor is not None:
            self.sublon_processor.multiproc_mgr.shutdown()
            self.sublon_processor = None

    def _set_tle_file(self, tle_path):
        """Sets the newest TLE file.
        """
        if os.path.isdir(tle_path):
            # find the newest TLE file in the configured path
            files = glob.iglob(os.path.join(tle_path, '*.tle'))
            if any(files):
                self.tle_file = max(files, key=os.path.getctime)
        else:
            self.tle_file = tle_path


def get_view_zen_angles(sat_name, tle_filename, area_def_name,
                        time_slot):
    """Calculate the satellite zenith angles for the given satellite
    (*sat_name*, *tle_filename*), *area_def_name* and *time slot*.
    Stores the result in the given *cache* parameter.
    """
    try:
        from pyorbital.orbital import Orbital
    except ImportError:
        LOGGER.warning("Could not load pyorbital modules")
        return

    area_def = get_area_def(area_def_name)
    lons, lats = area_def.get_lonlats()
    orbital_obj = Orbital(sat_name, tle_filename)
    elevation = orbital_obj.get_observer_look(time_slot, lons, lats, 0)[1]
    view_zen_data = np.subtract(90, np.ma.masked_outside(elevation, 0, 90))
    return view_zen_data


def get_geostationary_view_zen_angles(sublon, area_def_name):
    """Calculate the satellite zenith angles for geostationary satellites
    providing the earth location (*sublon*)
    and *area_def_name*.
    Stores the result in the given *cache* parameter.
    """

    area_def = get_area_def(area_def_name)
    lons, lats = area_def.get_lonlats()

    TWOPI = 6.28318
    R = 6371.
    H = 35680.
    DEGRAD = 360. / TWOPI

    zlon = np.ma.masked_array(lons)
    zlon[zlon < 0] += 360.

    zsublon = sublon
    if zsublon < 0:
        zsublon += 360.

    diflon = abs(zlon - zsublon) / DEGRAD
    diflat = abs(lats) / DEGRAD

    cospsi = np.cos(diflon) * np.cos(diflat)
    psi = np.arccos(cospsi)
    ssqr = R * R + (R + H) * (R + H) - 2 * R * (R + H) * cospsi
    s = np.sqrt(ssqr)
    sinndr = (R / s) * np.sin(psi)
    sinzen = ((R + H) / R) * sinndr
    angzen = np.arcsin(sinzen) * DEGRAD

    # store the result in the cache
    return angzen
