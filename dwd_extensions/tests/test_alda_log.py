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

"""Unit testing for AFD alda log reader
"""

import unittest
import tempfile
import os
import shutil
import yaml
from StringIO import StringIO
from mock import patch
from datetime import datetime

from dwd_extensions.qm.afd_alda_logs.repository import Repository
from dwd_extensions.qm.afd_alda_logs.reader import AldaLogReader
from dwd_extensions.qm.afd_alda_logs.service import AldaLogService


class TestAldaLogService(unittest.TestCase):
    """Unit testing for AFD alda log import
    """

    def setUp(self):
        """Setting up the testing
        """
        self.tempdir = tempfile.mkdtemp()

        dirname = os.path.dirname(__file__)
        db_filename = os.path.join(
            self.tempdir,
            'alda_log.db')

        with open(os.path.join(dirname, 'data',
                               'alda_log_cfg.yml'), "r") as fid:
            config = yaml.safe_load(fid)

        config['alda_log_db_filename'] = db_filename
        filename = os.path.join(
            dirname,
            'data',
            'afd-alda-msg-epi-hermes')

        self.service = AldaLogService(config=config)
        self.service.import_log_file(filename)

    def test_service_query_all_records(self):
        """Test service query for one timeslot with product
        pattern in short version csv file """

        (res, res_ok) = self.service.get_records_for_timeslot(
            datetime(2016, 12, 15, 23, 30),
            'METEOSAT_EUROPA_GESAMT_IR108_')
        self.assertEqual(len(res), 1)
        self.assertEqual(res_ok, True)

    def test_service_query_all_records_missing(self):
        """Test service query for one timeslot with product
        pattern in short version csv file """

        (res, res_ok) = self.service.get_records_for_timeslot(
            datetime(2016, 12, 15, 23, 30),
            'WarnappbildRGBA_')
        self.assertEqual(len(res), 1)
        self.assertEqual(res_ok, False)

    def test_service_delete(self):
        """Test deletion of old records """
        len_before = self.service.repo.record_count()
        old_records, res_ok = self.service.get_records_for_timeslot(
            datetime(2016, 9, 15, 13, 30), None)
        self.assertEqual(len(old_records), 9)
        for rec in old_records:
            self.assertEqual(rec.timestamp,
                             datetime(2016, 9, 15, 13, 4, 4))

        # nothing should be deleted here
        self.service.config['max_age_days'] = 100
        self.service.delete_old_entries()
        len_after = self.service.repo.record_count()
        self.assertEqual(len_after, len_before)

        # two entries are older than 90 days
        # they should be deleted
        self.service.config['max_age_days'] = 90
        self.service.delete_old_entries()
        len_after = self.service.repo.record_count()

        self.assertEqual(len_after, len_before - 9)

        old_records, res_ok = self.service.get_records_for_timeslot(
            datetime(2016, 9, 15, 13, 30),
            None)
        self.assertEqual(len(old_records), 0)

    def tearDown(self):
        """Closing down
        """
        shutil.rmtree(self.tempdir)


def suite():
    """The suite for test_trollduction
    """
    loader = unittest.TestLoader()
    mysuite = unittest.TestSuite()
    mysuite.addTest(loader.loadTestsFromTestCase(TestAldaLogService))

    return mysuite

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite())
