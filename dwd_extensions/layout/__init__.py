# Copyright (c) 2015 Ernst Basler + Partner AG (EBP).
# All Rights Reserved.
# http://www.ebp.ch/
#
# This software is the confidential and proprietary information of Ernst
# Basler + Partner AG ("Confidential Information").  You shall not
# disclose such Confidential Information and shall use it only in
# accordance with the terms of the license agreement you entered into
# with EBP.
#
# EBP MAKES NO REPRESENTATIONS OR WARRANTIES ABOUT THE SUITABILITY OF
# THE SOFTWARE, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE, OR NON-INFRINGEMENT. EBP SHALL NOT BE LIABLE FOR ANY DAMAGES
# SUFFERED BY LICENSEE AS A RESULT OF USING, MODIFYING OR DISTRIBUTING
# THIS SOFTWARE OR ITS DERIVATIVES.

import ConfigParser
import os
import numpy as np
import logging

from pycoast import ContourWriterAGG  # @UnresolvedImport
from mpop.projector import get_area_def  # @UnresolvedImport
from ConfigParser import NoSectionError, NoOptionError

LOGGER = logging.getLogger(__name__)


class LayouterFactory(object):
    """Creates a certain Layouter depending on the configuration.
    """
    def create_layouter(product_config, base_layouter):
        """Returns a Layouter object fitting the needs of
        the product config.
        """
        # simple example; has to parse the config here
        return CoastLineLayouter(BorderLayouter(base_layouter))
    create_layouter = staticmethod(create_layouter)


class LayoutHandler(object):
    """Handles the configured layouts.
    """
    def __init__(self, prod_config, config_dir):
        self.product_config = prod_config
        self.set_shapes_dir(config_dir)

    def set_shapes_dir(self, config_dir):
        """Sets the path to the shape files.
        """
        conf = ConfigParser.ConfigParser()
        conf.read(os.path.join(os.path.dirname(config_dir), "mpop.cfg"))
        try:
            self.shapes_dir = conf.get('shapes', 'dir')
        except NoSectionError, NoOptionError:
            self.shapes_dir = ''

    def layout(self, img, area):
        """Sets the layout in the given image for the specified area.
        """
        if not self.shapes_dir:
            raise ValueError("Missing path to shape files.")

        layout_area = area
        if layout_area is None:
            raise ValueError("Area of image is None, can't add layout.")

        if isinstance(layout_area, str):
            layout_area = get_area_def(area)

        pil_image = img.pil_image()
        resolution = self._get_resolution(area)
        base_layouter = Layouter(
            pil_image, layout_area, self.shapes_dir, resolution)
        layouter = LayouterFactory.create_layouter(
            self.product_config, base_layouter)
        layouter.layout()

        arr = np.array(pil_image)
        if len(img.channels) == 1:
            img.channels[0] = np.ma.array(arr[:, :] / 255.0)
        else:
            for idx in range(len(img.channels)):
                img.channels[idx] = np.ma.array(arr[:, :, idx] / 255.0)

    def _get_resolution(self, area):
        """Returns the resolution depending on the given area.
        """
        x_resolution = ((area.area_extent[2] -
                         area.area_extent[0]) / area.x_size)
        y_resolution = ((area.area_extent[3] -
                         area.area_extent[1]) / area.y_size)
        res = min(x_resolution, y_resolution)

        if res > 25000:
            return "c"
        elif res > 5000:
            return "l"
        elif res > 1000:
            return "i"
        elif res > 200:
            return "h"
        else:
            return "f"


class Layouter(object):
    """Acts as an abstract base class.
    """
    def __init__(self, img, area, shapes, resolution):
        self.image = img
        self.area = area
        self.shapes = shapes
        self.resolution = resolution

    def layout(self):
        pass


class CoastLineLayouter(object):
    """Decorates a Layouter object with coast lines.
    """

    MAX_LEVEL = 6

    def __init__(self, layouter):
        self.layouter = layouter

    def __getattr__(self, name):
        return getattr(self.layouter, name)

    def layout(self):
        self.layouter.layout()
        cw = ContourWriterAGG(self.layouter.shapes)
        LOGGER.debug("Add coast line layout (resolution %s, level %s)" %
                     (self.resolution, CoastLineLayouter.MAX_LEVEL))
        cw.add_coastlines(self.layouter.image,
                          self.layouter.area,
                          resolution=self.resolution,
                          level=1)


class BorderLayouter(object):
    """Decorates a Layouter object with borders.
    """

    MAX_LEVEL = 3

    def __init__(self, layouter):
        self.layouter = layouter

    def __getattr__(self, name):
        return getattr(self.layouter, name)

    def layout(self):
        self.layouter.layout()
        cw = ContourWriterAGG(self.layouter.shapes)
        LOGGER.debug("Add border layout (resolution %s, level %s)" %
                     (self.resolution, BorderLayouter.MAX_LEVEL))
        cw.add_borders(self.layouter.image,
                       self.layouter.area,
                       resolution=self.resolution,
                       level=1)


class RiverLayouter(object):
    """Decorates a Layouter object with rivers.
    """

    MAX_LEVEL = 10

    def __init__(self, layouter):
        self.layouter = layouter

    def __getattr__(self, name):
        return getattr(self.layouter, name)

    def layout(self):
        self.layouter.layout()
        cw = ContourWriterAGG(self.layouter.shapes)
        LOGGER.debug("Add river layout (resolution %s, level %s)" %
                     (self.resolution, RiverLayouter.MAX_LEVEL))
        cw.add_rivers(self.layouter.image,
                      self.layouter.area,
                      resolution=self.resolution,
                      level=1)


class GridLayouter(object):
    """Decorates a Layouter object with a grid.
    """

    def __init__(
            self, layouter, font=None, write_text=True, fill=None,
            outline='white', minor_outline='white', minor_is_tick=True,
            lon_placement='tb', lat_placement='lr'):
        self.layouter = layouter
        self.grid_values['font'] = font
        self.grid_values['write_text'] = write_text
        self.grid_values['fill'] = fill
        self.grid_values['outline'] = outline
        self.grid_values['minor_outline'] = minor_outline
        self.grid_values['minor_is_tick'] = minor_is_tick
        self.grid_values['lon_placement'] = lon_placement
        self.grid_values['lat_placement'] = lat_placement

    def __getattr__(self, name):
        return getattr(self.layouter, name)

    def layout(self):
        self.layouter.layout()
        cw = ContourWriterAGG(self.layouter.shapes)
        LOGGER.debug("Add grid layout")
        cw.add_grid(
            self.layouter.image, self.layouter.area, (30.0, 30.0),
            (10.0, 10.0), **self.grid_values)
