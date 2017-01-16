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
import shutil
import os
import yaml

from dwd_extensions.tools.rrd_utils import to_unix_seconds
from dwd_extensions.tools.rrd_utils import create_sample_rrd

from dwd_extensions.qm.emc_daily_logs.service import DailyLogService
from dwd_extensions.qm.afd_alda_logs.service import AldaLogService
from dwd_extensions.qm.sat_incidents.service import SatDataAvailabilityService
from dwd_extensions.qm.stats import calc_month_timeslots
from dwd_extensions.qm.stats import calc_qm_stats
from dwd_extensions.qm.stats import calc_monthly_qm_stats
from dwd_extensions.qm.stats import append_qm_stats_to_csv


class TestCalcQMStats(unittest.TestCase):
    """Unit testing for EUMETCAST Daily Log import
    """

    def setUp(self):
        """Setting up the testing
        """
        self.tempdir = tempfile.mkdtemp()
        self.testdatadir = os.path.join(os.path.dirname(__file__), 'data')

        self._prepare_dailylog()
        self._prepare_aldalog()

        self.rrd_dir = os.path.join(self.tempdir, "rrd_dir1")
        os.makedirs(self.rrd_dir)

        self.rrd_dir_2 = os.path.join(self.tempdir, "rrd_dir2")
        os.makedirs(self.rrd_dir_2)

        self.rrd_dir_3 = os.path.join(self.tempdir, "rrd_dir3")
        os.makedirs(self.rrd_dir_3)

        self.product_name = 'METEOSAT_EUROPA_GESAMT_IR108_xxx'

        self.rrd_filename = os.path.join(self.rrd_dir,
                                         self.product_name + '.rrd')
        self.rrd_filename_2 = os.path.join(self.rrd_dir_2,
                                           self.product_name + '.rrd')
        self.rrd_filename_3 = os.path.join(self.rrd_dir_3,
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
        service.import_file(os.path.join(
            self.testdatadir,
            'E-UNS_-MSG_0DEG-H_SEVIRI____-DAILY_LOG-161204_01'
            '-201612050202-___qm_stats_test'))

    def _prepare_aldalog(self):
        # load yml config as provided with test
        with open(os.path.join(self.testdatadir,
                               'alda_log_cfg.yml'), "r") as fid:
            config = yaml.safe_load(fid)

        # adjust path to database file
        config['alda_log_db_filename'] = os.path.join(
            self.tempdir, 'alda_log.db')

        # and store temporary version of config
        self.alda_log_config_filename = os.path.join(self.tempdir,
                                                     'alda_log_cfg.yml')
        with open(self.alda_log_config_filename, 'w') as fid:
                yaml.dump(config, fid, default_flow_style=True)

        # create service with temporary config and import data
        service = AldaLogService(
            config_yml_filename=self.alda_log_config_filename)

        # print "warning - import skipped"
        service.import_file(os.path.join(
            self.testdatadir,
            'afd-alda-msg-epi-hermes_qm_stats_test'))

    def test_calc_qm(self):
        """Test calculation """

        # AP6 Nr. 1
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

        # dailylog contains entries between 00:00 and 10:00
        # 04:00 marked as "not_send"
        # 04:15 marked as "sent_not_confirmed"

        res = calc_qm_stats(self.rrd_dir,
                            self.dailylog_config_filename,
                            self.alda_log_config_filename,
                            self.product_name,
                            timeslots, allowed_process_time=300)
        print res

        # AP6 Nr. 2
        # dailylog contains entries between 00:00 and 10:00
        # 04:00 marked as "not_send"
        # 04:15 marked as "sent_not_confirmed"
        print "number of timeslots missing in dailylog (not "\
            "transfered by EUMETCAST): {}".format(res.count_failed_dailylog)

        # AP6 Nr. 4a
        print "number of timeslots missing in pytroll output: {}".format(
            res.count_failed_pytroll)

        print "number of timeslots processed by pytroll: {}".format(
            res.count_processed_pytroll)
        print "mean processing time pytroll: {}".format(
            res.mean_process_time_pytroll)
        print "exceeeded processing time process: {}".format(
            res.process_time_pytroll_exceeded)

        self.assertEqual(res.count_timeslots, 96,
                         'astronomical timeslots')
        self.assertEqual(res.count_processed_pytroll, 86,
                         'processed by pytroll')
        self.assertEqual(res.count_failed_pytroll, 10,
                         'not processed by pytroll')
        self.assertEqual(res.count_failed_dailylog, 57,
                         'not marked as sent by EUMETCAST')
        self.assertEqual(res.count_received_dailylog, 39,
                         'marked as sent by EUMETCAST')
        self.assertEqual(res.count_failed_afd, 53,
                         'not transferred by AFD to pytroll server')
        self.assertEqual(res.count_received_afd, 43,
                         'transferred by AFD to pytroll server')

    def test_calc_monthly_qm(self):
        """Test calculation for a month"""

        # AP6 Nr. 1
        rrd_steps = 900
        month = 12
        year = 2016

        timeslots = calc_month_timeslots(year, month, rrd_steps)

        # take only 4th december because we have sample data for that day
        timeslots = [t for t in timeslots if t.day == 4]

        # create sample rrd file with gaps from 4:00 to 4:45 and 8:00 to 8:45
        timeslots_with_gap = [t for t in timeslots if t.hour not in (4, 8)]
        create_sample_rrd(self.rrd_filename,
                          timeslots_with_gap,
                          rrd_steps)

        # dailylog contains entries between 00:00 and 10:00
        # 04:00 marked as "not_send"
        # 04:15 marked as "sent_not_confirmed"

        res = calc_monthly_qm_stats(self.rrd_dir,
                                    self.dailylog_config_filename,
                                    self.alda_log_config_filename,
                                    self.product_name,
                                    rrd_steps, year, month,
                                    allowed_process_time=300)
        print res
        append_qm_stats_to_csv(res, '/home/pytroll/pytroll_qm_stats.csv')

        self.assertEqual(res.count_timeslots, 2976,
                         'astronomical timeslots')
        self.assertEqual(res.count_processed_pytroll, 86,
                         'processed by pytroll')
        self.assertEqual(res.count_failed_pytroll, 2890,
                         'not processed by pytroll')
        self.assertEqual(res.count_failed_dailylog, 2937,
                         'not marked as sent by EUMETCAST')
        self.assertEqual(res.count_received_dailylog, 39,
                         'marked as sent by EUMETCAST')
        self.assertEqual(res.count_failed_afd, 2933,
                         'not transferred by AFD to pytroll server')
        self.assertEqual(res.count_received_afd, 43,
                         'transferred by AFD to pytroll server')

    def test_calc_monthly_qm_three_rrddirs(self):
        """Test calculation for a month using three rrd directories"""

        # AP6 Nr. 1
        rrd_steps = 900
        month = 12
        year = 2016

        timeslots = calc_month_timeslots(year, month, rrd_steps)

        # take only 4th december because we have sample data for that day
        timeslots = [t for t in timeslots if t.day == 4]

        # create sample rrd file with gaps from 4:00 to 4:45 and 8:00 to 8:45
        timeslots_with_gap = [t for t in timeslots if t.hour not in (4, 8)]
        create_sample_rrd(self.rrd_filename,
                          timeslots_with_gap,
                          rrd_steps)

        # create sample rrd file with gaps from 8:00 to 8:45
        timeslots_with_gap = [t for t in timeslots if t.hour != 8]
        create_sample_rrd(self.rrd_filename_2,
                          timeslots_with_gap,
                          rrd_steps)

        # create sample rrd file with gaps from 9:00 to 9:45
        timeslots_with_gap = [t for t in timeslots if t.hour != 9]
        create_sample_rrd(self.rrd_filename_3,
                          timeslots_with_gap,
                          rrd_steps)

        # dailylog contains entries between 00:00 and 10:00
        # 04:00 marked as "not_send"
        # 04:15 marked as "sent_not_confirmed"

        res = calc_monthly_qm_stats([self.rrd_dir, self.rrd_dir_2],
                                    self.dailylog_config_filename,
                                    self.alda_log_config_filename,
                                    self.product_name,
                                    rrd_steps, year, month,
                                    allowed_process_time=300)
        print res
        #append_qm_stats_to_csv(res, '/home/pytroll/pytroll_qm_stats.csv')

        self.assertEqual(res.count_timeslots, 2976,
                         'astronomical timeslots')
        self.assertEqual(res.count_processed_pytroll, 91,
                         'processed by pytroll')
        self.assertEqual(res.count_failed_pytroll, 2885,
                         'not processed by pytroll')
        self.assertEqual(res.count_failed_dailylog, 2937,
                         'not marked as sent by EUMETCAST')
        self.assertEqual(res.count_received_dailylog, 39,
                         'marked as sent by EUMETCAST')
        self.assertEqual(res.count_failed_afd, 2933,
                         'not transferred by AFD to pytroll server')
        self.assertEqual(res.count_received_afd, 43,
                         'transferred by AFD to pytroll server')

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
