#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Author(s):

#   Christian Kliche <chk@ebp.de>
#   Panu Lahtinen <panu.lahtinen@fmi.fi>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

'''This module defines functions to create images out of dataset messages
'''
from urlparse import urlparse
from functools import partial
import logging
import numpy as np
import scipy.ndimage as ndi
from fnmatch import fnmatch
from mpop.projector import get_area_def
from pyresample.geometry import AreaDefinition
from dwd_extensions.tools.image_io import read_image
from datetime import datetime

LOGGER = logging.getLogger(__name__)


def create_world_composite(msg, proc_func_params):
    """
    Creates a world composite images out of an dataset message
    """
    items = []
    for elem in msg.data['dataset']:
        url = urlparse(elem['uri'])
        if url.netloc != '':
            LOGGER.error('uri not supported: %s',
                         format(elem['uri']))
            return None

        area = get_area_def(msg.data['area']['name'])
        t_gatherer = msg.data['gatherer_time']
        if not isinstance(t_gatherer, datetime):
            try:
                t_gatherer = datetime.strptime(
                    t_gatherer, '%Y%m%d%H%M%S')
            except:
                t_gatherer = None
        items.append((url.path, area, t_gatherer))

    lon_limits = {}
    erosion_size = None
    smooth_width = None

    if proc_func_params:
        # order images
        if 'order' in proc_func_params:
            order_list = proc_func_params['order'].split('|')
            sort_key = partial(_match_order_index, order_list)
            items = sorted(items, key=sort_key, reverse=True)

        if 'lon_limits' in proc_func_params:
            sat_lon_list = proc_func_params['lon_limits'].split('|')
            for sat_lon in sat_lon_list:
                sat, min_lon, max_lon = sat_lon.split(',')
                lon_limits[sat] = (float(min_lon), float(max_lon))

        if 'erosion_size' in proc_func_params:
            erosion_size = float(proc_func_params['erosion_size'])

        if 'smooth_width' in proc_func_params:
            smooth_width = float(proc_func_params['smooth_width'])

    return _create_world_composite(items, lon_limits=lon_limits,
                                   erosion_size=erosion_size,
                                   smooth_width=smooth_width)


def _match_order_index(order_list, item):
    for idx, pattern in enumerate(order_list):
        if fnmatch(item[0], pattern):
            return idx
    return len(order_list)


def _create_world_composite(items, lon_limits=None,
                            erosion_size=20,
                            smooth_width=20):
    # smooth_sigma = 4

    img = None
    for (path, area, timeslot) in items:

        if not isinstance(area, AreaDefinition):
            area = get_area_def(area)

        next_img = read_image(path, area, timeslot)

        if img is None:
            img = next_img
        else:
            # scaled_smooth_sigma = smooth_sigma * (float(img.width) / 1000.0)

            img_mask = reduce(np.ma.mask_or,
                              [chn.mask for chn in img.channels])
            next_img_mask = reduce(np.ma.mask_or,
                                   [chn.mask for chn in next_img.channels])

            # Mask overlapping areas away
            if lon_limits:
                for sat in lon_limits:
                    if sat in path:
                        mask_limits = calc_pixel_mask_limits(area,
                                                             lon_limits[sat])
                        for lim in mask_limits:
                            next_img_mask[:, lim[0]:lim[1]] = 1
                        break

            alpha = np.ones(next_img_mask.shape, dtype='float')
            alpha[next_img_mask] = 0.0

            if erosion_size is not None and smooth_width is not None:
                scaled_erosion_size = erosion_size * (float(img.width) /
                                                      1000.0)
                scaled_smooth_width = smooth_width * (float(img.width) /
                                                      1000.0)

                # smooth_alpha = ndi.gaussian_filter(
                #     ndi.grey_erosion(alpha, size=(scaled_erosion_size,
                #                                   scaled_erosion_size)),
                #        scaled_smooth_sigma)
                smooth_alpha = ndi.uniform_filter(
                    ndi.grey_erosion(alpha, size=(scaled_erosion_size,
                                                  scaled_erosion_size)),
                    scaled_smooth_width)
                smooth_alpha[img_mask] = alpha[img_mask]
            else:
                smooth_alpha = alpha

            for i in range(0, min(len(img.channels), len(next_img.channels))):
                chdata = next_img.channels[i].data * smooth_alpha + \
                    img.channels[i].data * (1 - smooth_alpha)
                chmask = np.logical_and(img_mask, next_img_mask)
                img.channels[i] = \
                    np.ma.masked_where(chmask, chdata)

    return img


def calc_pixel_mask_limits(adef, lon_limits):
    """Calculate pixel intervals from longitude ranges."""
    # We'll assume global grid from -180 to 180 longitudes
    scale = 360. / adef.shape[1]  # degrees per pixel

    left_limit = int((lon_limits[0] + 180) / scale)
    right_limit = int((lon_limits[1] + 180) / scale)

    # Satellite data spans 180th meridian
    if right_limit < left_limit:
        return [[right_limit, left_limit]]
    else:
        return [[0, left_limit], [right_limit, adef.shape[1]]]
