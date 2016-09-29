#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Author(s):

#   Christian Kliche <chk@ebp.de>

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
import logging
import numpy as np
import scipy.ndimage as ndi
from mpop.projector import get_area_def
from dwd_extensions.tools.image_io import read_image
import datetime

LOGGER = logging.getLogger(__name__)


def create_world_composite(msg):
    """
    Creates a world composite images out of an dataset message
    """
    items = []
    for elem in msg.data['dataset']:
        url = urlparse(elem['uri'])
        if url.netloc != '':
            LOGGER.error('urifrom scipy.misc import toimag not supported: %s',
                         format(elem['uri']))
            return None

        area = get_area_def(msg.data['area']['name'])
        t_gatherer = msg.data['gatherer_time']
        if not isinstance(t_gatherer, datetime.datetime):
            try:
                t_gatherer = datetime.datetime.strptime(
                    t_gatherer, '%Y%m%d%H%M%S')
            except:
                t_gatherer = None
        items.append((url.path, area, t_gatherer))

    return _create_world_composite(items)


def _create_world_composite(items):
    erosion_size = 20
#     smooth_sigma = 4
    smooth_width = 20

    img = None
    for (path, area, timeslot) in items:
        next_img = read_image(path, area, timeslot)
        if img is None:
            img = next_img
        else:
            scaled_erosion_size = erosion_size * (float(img.width) / 1000.0)
#             scaled_smooth_sigma = smooth_sigma * (float(img.width) / 1000.0)
            scaled_smooth_width = smooth_width * (float(img.width) / 1000.0)

            img_mask = reduce(np.ma.mask_or,
                              [chn.mask for chn in img.channels])
            next_img_mask = reduce(np.ma.mask_or,
                                   [chn.mask for chn in next_img.channels])

            alpha = np.ones(next_img_mask.shape, dtype='float')
            alpha[next_img_mask] = 0.0

#             smooth_alpha = ndi.gaussian_filter(
#                 ndi.grey_erosion(alpha, size=(scaled_erosion_size, scaled_erosion_size)),
#                 scaled_smooth_sigma)
            smooth_alpha = ndi.uniform_filter(
                ndi.grey_erosion(alpha, size=(scaled_erosion_size, scaled_erosion_size)),
                scaled_smooth_width)
            smooth_alpha[img_mask] = alpha[img_mask]

            for i in range(0, min(len(img.channels), len(next_img.channels))):
                chdata = next_img.channels[i].data * smooth_alpha + \
                    img.channels[i].data * (1 - smooth_alpha)
                chmask = np.logical_and(img_mask, next_img_mask)
                img.channels[i] = \
                    np.ma.masked_where(chmask, chdata)
#             show(img.channels[i])
#     img.save("/vagrant/wc_{0}_{1}_uniform.png".format(scaled_erosion_size, scaled_smooth_width))
    return img

# def show(ch):
#     gimg = geo_image.Image(ch)
#     gimg.show()
