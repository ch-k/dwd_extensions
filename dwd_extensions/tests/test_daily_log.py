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
import tempfile
import os
import shutil
import yaml
from StringIO import StringIO
from mock import patch
from datetime import datetime

from dwd_extensions.qm.emc_daily_logs.repository import Repository
from dwd_extensions.qm.emc_daily_logs.reader \
    import EumetcastDailylogReaderReader
from dwd_extensions.qm.emc_daily_logs.service import DailyLogService


class TestEumetcastDailylog(unittest.TestCase):
    """Unit testing for EUMETCAST Daily Log import
    """

    def setUp(self):
        """Setting up the testing
        """
        self.dirname = os.path.dirname(__file__)
        self.tempdir = tempfile.mkdtemp()
        self.db_filename = os.path.join(self.tempdir,
                                        'daily_log.db')

    @unittest.skip("testing skipping (slow)")
    def test_import_full(self):
        """Test import of csv file into repository"""
        self.filename = os.path.join(
            self.dirname, 'data',
            'E-UNS_-MSG_0DEG-H_SEVIRI____'
            '-DAILY_LOG-161204_01-201612050202-___')
        reader = EumetcastDailylogReaderReader(self.filename)
        repo = Repository(self.db_filename)
        repo.add(reader.get_items())

        self.assertEqual(repo.record_count(), 10944)

    def tearDown(self):
        """Closing down
        """
        shutil.rmtree(self.tempdir)


class TestEumetcastDailylogService(unittest.TestCase):
    """Unit testing for EUMETCAST Daily Log import
    """

    def setUp(self):
        """Setting up the testing
        """
        self.tempdir = tempfile.mkdtemp()

        dirname = os.path.dirname(__file__)
        db_filename = os.path.join(
            self.tempdir,
            'daily_log.db')

        with open(os.path.join(dirname, 'data',
                               'dailylog_cfg.yml'), "r") as fid:
            config = yaml.safe_load(fid)

        config['daily_log_db_filename'] = db_filename
        filename = os.path.join(
            dirname,
            'data',
            'E-UNS_-MSG_0DEG-H_SEVIRI____'
            '-DAILY_LOG-161204_01-201612050202-___short')

        self.service = DailyLogService(config=config)
        self.service.import_file(filename)

    def test_service_query_all_records(self):
        """Test service query for one timeslot with product
        pattern in short version csv file """

        res = self.service.get_records_for_timeslot(
            datetime(2016, 12, 4, 5, 15),
            'METEOSAT_EUROPA_GESAMT_IR108_')
        self.assertEqual(len(res), 9)

    def test_service_query_remark_count_all_ok(self):
        """Test service query for one timeslot with product
        pattern in short version csv file """

        res = self.service.get_record_remark_count(
            datetime(2016, 12, 4, 5, 0),
            'METEOSAT_EUROPA_GESAMT_IR108_')
        print res
        self.assertEqual(res['total'], 9)
        self.assertEqual(res['confirmed'], 9)
        self.assertEqual(res['total_invalid'], 0)

    def test_service_query_remark_count_some_failed(self):
        """Test service query for one timeslot with product
        pattern in short version csv file """

        # csv file manually modified for timeslot to simulate
        # error entries
        res = self.service.get_record_remark_count(
            datetime(2016, 12, 4, 5, 15),
            'METEOSAT_EUROPA_GESAMT_IR108_')
        print res
        self.assertEqual(res['total'], 9)
        self.assertEqual(res['confirmed'], 7)
        self.assertEqual(res['total_invalid'], 2)

    def test_service_delete(self):
        """Test deletion of old records """
        len_before = self.service.repo.record_count()
        old_records = self.service.get_records_for_timeslot(
            datetime(2016, 9, 3, 4, 0), None)
        self.assertEqual(len(old_records), 2)
        self.assertEqual(
            old_records[0].reference_time,
            datetime(2016, 9, 3, 4, 0, 0))
        self.assertEqual(
            old_records[1].reference_time,
            datetime(2016, 9, 3, 4, 0, 1))

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

        self.assertEqual(len_after, len_before - 2)

        old_records = self.service.get_records_for_timeslot(
            datetime(2016, 9, 3, 4, 0),
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
    mysuite.addTest(loader.loadTestsFromTestCase(TestEumetcastDailylog))
    mysuite.addTest(loader.loadTestsFromTestCase(TestEumetcastDailylogService))

    return mysuite

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite())
