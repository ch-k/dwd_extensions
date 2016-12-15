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
import random
from StringIO import StringIO
from mock import patch
from datetime import datetime, tzinfo
from datetime import timedelta
import pytz

from dwd_extensions.tools.rrd_utils import to_unix_seconds
from dwd_extensions.tools.rrd_utils import create_rrd_file
from dwd_extensions.tools.rrd_utils import update_rrd_file
from dwd_extensions.tools.rrd_utils import create_sample_rrd
from dwd_extensions.tools.rrd_utils import fetch as rrd_fetch
from dwd_extensions.tools.rrd_utils import MONTH

from dwd_extensions.emc_dailylogs.service import DailyLogService
from dwd_extensions.sat_incidents.service import SatDataAvailabilityService
from dwd_extensions.qm.stats import calc_month_timeslots
from dwd_extensions.qm.stats import get_availability_dailylog


class TestCalcQMStats(unittest.TestCase):
    """Unit testing for EUMETCAST Daily Log import
    """

    def setUp(self):
        """Setting up the testing
        """
        self.tempdir = tempfile.mkdtemp()
        self.testdatadir = os.path.join(os.path.dirname(__file__), 'data')

        self._prepare_dailylog()

        self.product_name = 'METEOSAT_EUROPA_GESAMT_IR108_xxx'
        self.rrd_filename = os.path.join(self.tempdir,
                                         self.product_name + '.rrd')

    def _prepare_dailylog(self):
        # load yml config as provided with test
        with open(os.path.join(self.testdatadir,
                               'dailylog_cfg.yml'), "r") as fid:
            config = yaml.safe_load(fid)

        # adjust path to database file
        config['daily_log_db_filename'] = os.path.join(
            self.tempdir, 'daily_log.db')

        # and store temporary version of config
        self.dailylog_config_filename = os.path.join(self.tempdir,
                                                     'dailylog_cfg.yml')
        with open(self.dailylog_config_filename, 'w') as fid:
                yaml.dump(config, fid, default_flow_style=True)

        # create service with temporary config and import data
        service = DailyLogService(
            config_yml_filename=self.dailylog_config_filename)

        # print "warning - import skipped"
        service.import_dailylog_file(os.path.join(
            self.testdatadir,
            'E-UNS_-MSG_0DEG-H_SEVIRI____-DAILY_LOG-161204_01'
            '-201612050202-___qm_stats_test'))

    def test_calc_qm(self):
        """Test calculation """

        rrd_steps = 900
        timeslots = calc_month_timeslots(2016, 12, rrd_steps)

        # take only 4th december because we have sample data for that day
        timeslots = [t for t in timeslots if t.day == 4]
        print "total count of possible timeslots: {}".format(len(timeslots))

        # create sample rrd file with gaps from 4:00 to 4:45 and 8:00 to 8:45
        timeslots_with_gap = [t for t in timeslots if t.hour not in (4, 8)]
        create_sample_rrd(self.rrd_filename,
                          timeslots_with_gap,
                          rrd_steps)

        availability_pytroll = rrd_fetch(self.rrd_filename, timeslots)
        failed_pytroll = [el[0] for el in availability_pytroll
                          if el[1][0] is None]
        count_failed_pytroll = len(failed_pytroll)
        print "number of timeslots missing in pytroll output: {}".format(
            count_failed_pytroll)

        # dailylog contains entries between 00:00 and 10:00
        # 04:00 marked as "not_send"
        # 04:15 marked as "sent_not_confirmed"
        availability_dailylog = get_availability_dailylog(
            timeslots,
            self.product_name,
            self.dailylog_config_filename)
        failed_dailylog = [el[0] for el in availability_dailylog
                           if el[1] is False]
        count_failed_dailylog = len(failed_dailylog)
        print "number of timeslots missing in dailylog (not "\
            "transfered by EUMETCAST): {}".format(count_failed_dailylog)
        # print avail_dailylog

        self.assertEqual(len(timeslots), 96)
        self.assertEqual(count_failed_pytroll, 10)
        self.assertEqual(count_failed_dailylog, 57)

    def tearDown(self):
        """Closing down
        """
        shutil.rmtree(self.tempdir)


def suite():
    """The suite for test_trollduction
    """
    loader = unittest.TestLoader()
    mysuite = unittest.TestSuite()
    mysuite.addTest(loader.loadTestsFromTestCase(TestCalcQMStats))

    return mysuite

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite())
