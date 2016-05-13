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
import os
from dwd_extensions.tools.dataset_processors import _create_world_composite


class TestWorldComposite(unittest.TestCase):
    """Unit testing for dataset processors
    """

    def setUp(self):
        """Setting up the testing
        """
        dirname = os.path.dirname(__file__)
        self.files = [
            os.path.join(dirname, 'data',
                         'goes13_IR_107_wcm3km_201604291015.tif'),
            os.path.join(dirname, 'data',
                         'goes15_IR_107_wcm3km_201604291015.tif'),
            os.path.join(dirname, 'data',
                         'himawari8_IR1_wcm3km_201604291015.tif'),
            os.path.join(dirname, 'data',
                         'meteosat7_IR_115_wcm3km_201604291015.tif'),
            os.path.join(dirname, 'data',
                         'meteosat10_IR_108_wcm3km_201604291015.tif')
        ]

    def test_create_world_composite(self):
        """Test the creation of world composite"""
        items = [(path, 'wcm3km', '201604291015') for path in self.files]
        image = _create_world_composite(items)
        image.show()

        self.assertTrue(image is not None)

    def tearDown(self):
        """Closing down
        """
        pass


def suite():
    """The suite for test_trollduction
    """
    loader = unittest.TestLoader()
    mysuite = unittest.TestSuite()
    mysuite.addTest(loader.loadTestsFromTestCase(TestWorldComposite))

    return mysuite

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite())
