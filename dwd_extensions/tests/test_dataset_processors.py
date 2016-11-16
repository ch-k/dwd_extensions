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

"""Unit testing for dataset processors
"""

import unittest
import numpy
from mock import patch
from datetime import datetime
import os
from dwd_extensions.tools.dataset_processors import _create_world_composite
from dwd_extensions.tools.image_io import read_image


class TestWorldComposite(unittest.TestCase):
    """Unit testing for dataset processors
    """

    def setUp(self):
        """Setting up the testing
        """
        dirname = os.path.dirname(__file__)
        self.files = [
            os.path.join(dirname, 'data',
                         'goes13_IR_107_testwcm_201604291015.tif'),
            os.path.join(dirname, 'data',
                         'goes15_IR_107_testwcm_201604291015.tif'),
            os.path.join(dirname, 'data',
                         'himawari8_IR1_testwcm_201604291015.tif'),
            os.path.join(dirname, 'data',
                         'meteosat7_IR_115_testwcm_201604291015.tif'),
            os.path.join(dirname, 'data',
                         'meteosat10_IR_108_testwcm_201604291015.tif')
        ]

    @patch('mpop.projector.get_area_file',
           return_value=os.path.join(os.path.dirname(__file__),
                                     'data', 'testareas.def'))
    def test_create_world_composite(self, get_area_file_function):
        """Test the creation of world composite"""

        timeslot = datetime(2016, 4, 29, 10, 15)
        area = 'testwcm'

        lon_limits = {'meteosat10': [-37.5, 28.75],
                      'meteosat7': [28.75, 83.2],
                      'himawari8': [83.2, -177.15],
                      'goes15': [-177.15, -105.],
                      'goes13': [-105., -37.5]
                      }

        items = [(path, area, timeslot) for path in self.files]
        image = _create_world_composite(items, lon_limits, erosion_size=None,
                                        smooth_width=None)
        # image.save(os.path.join(os.path.dirname(__file__),
        #                         'data', 'reference.tif'))
        # image.show()

        ref_image = read_image(os.path.join(os.path.dirname(__file__),
                                            'data',
                                            'reference.tif'),
                               area, timeslot)
        # ref_image.show()

        self.assertTrue(image is not None)
        self.assertTrue(_compare_images(image.pil_image(),
                                        ref_image.pil_image()) == 0)

    @patch('mpop.projector.get_area_file',
           return_value=os.path.join(os.path.dirname(__file__),
                                     'data', 'testareas.def'))
    def test_create_world_composite_smooth(self, get_area_file_function):
        """Test the creation of world composite with smooth overlaping"""

        timeslot = datetime(2016, 4, 29, 10, 15)
        area = 'testwcm'

        lon_limits = {'meteosat10': [-37.5, 28.75],
                      'meteosat7': [20.75, 83.2],
                      'himawari8': [73.2, -177.15],
                      'goes15': [-177.15, -105.],
                      'goes13': [-105., -37.5]
                      }
        items = [(path, area, timeslot) for path in self.files]
        image = _create_world_composite(items, lon_limits)
        # image.save(os.path.join(os.path.dirname(__file__),
        #                         'data', 'reference_smooth.tif'))
        # image.show()

        ref_image = read_image(os.path.join(os.path.dirname(__file__),
                                            'data',
                                            'reference_smooth.tif'),
                               area, timeslot)
        # ref_image.show()

        self.assertTrue(image is not None)
        self.assertTrue(_compare_images(image.pil_image(),
                                        ref_image.pil_image()) == 0)

    def tearDown(self):
        """Closing down
        """
        pass


def _compare_images(img1, img2):
    if img1.size != img2.size or img1.getbands() != img2.getbands():
        return -1

    err_sum = 0
    if len(img1.getbands()) == 1:
        data1 = numpy.array(img1.getdata()).reshape(*img1.size)
        data2 = numpy.array(img2.getdata()).reshape(*img2.size)
        err_sum += numpy.sum(numpy.abs(data1 - data2))
    else:
        for band_index, _ in enumerate(img1.getbands()):
            data1 = numpy.array([p[band_index]
                                 for p in img1.getdata()]).reshape(*img1.size)
            data2 = numpy.array([p[band_index]
                                 for p in img2.getdata()]).reshape(*img2.size)
            err_sum += numpy.sum(numpy.abs(data1 - data2))
    return err_sum


def suite():
    """The suite for test_trollduction
    """
    loader = unittest.TestLoader()
    mysuite = unittest.TestSuite()
    mysuite.addTest(loader.loadTestsFromTestCase(TestWorldComposite))

    return mysuite

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite())
