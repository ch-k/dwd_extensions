# -*- coding: utf-8 -*-

# Copyright (c) 2016 Ernst Basler + Partner

# Author(s):

#   Christian Kliche <christian.kliche@ebp.de>

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

'''This module defines functions to calculate QM stats
'''
from datetime import datetime, timedelta
import os
import csv
import pytz
from dwd_extensions.qm.emc_daily_logs.service import DailyLogService
from dwd_extensions.qm.afd_alda_logs.service import AldaLogService
from dwd_extensions.tools.rrd_utils import fetch as rrd_fetch


def calc_month_timeslots(year, month, steps):
    timeslot = datetime(year, month, 1, 0, 0, tzinfo=pytz.UTC)
    offset = timedelta(seconds=steps)
    res = []
    while timeslot.month == month:
        res.append(timeslot)
        timeslot += offset
    return res


def get_availability_dailylog(timeslots,
                              product_name,
                              dailylog_config_file):
    service = DailyLogService(config_yml_filename=dailylog_config_file)
    res = []
    for timeslot in timeslots:
        counts = service.get_record_remark_count(timeslot, product_name)
        ts_res = (timeslot,
                  True if counts['total'] > 0 and counts['total_invalid'] == 0
                  else False)
        res.append(ts_res)
    return res


def get_availability_alda_log(timeslots,
                              product_name,
                              aldalog_config_file):
    service = AldaLogService(config_yml_filename=aldalog_config_file)
    res = []
    for timeslot in timeslots:
        (records, res_ok) = service.get_records_for_timeslot(timeslot,
                                                             product_name)
        ts_res = (timeslot, res_ok)
        res.append(ts_res)
    return res


class QmStats:
    count_timeslots = None
    count_received_dailylog = None
    count_failed_dailylog = None
    count_received_afd = None
    count_failed_afd = None
    count_processed_pytroll = None
    count_processed_pytroll_rel_afd = None
    count_failed_pytroll = None
    mean_process_time_pytroll = None
    process_time_pytroll_exceeded = None

    param_product_name = None
    param_period_year = None
    param_period_month = None
    param_allowed_process_time = None
    param_steps = None

    def __repr__(self):
        return "<QmStats("\
            "count_timeslots='{}'"\
            ", count_received_dailylog='{}'"\
            ", count_failed_dailylog='{}'"\
            ", count_received_afd='{}'"\
            ", count_failed_afd='{}'"\
            ", count_processed_pytroll='{}'"\
            ", count_processed_pytroll_rel_afd='{}'"\
            ", count_failed_pytroll='{}'"\
            ", mean_process_time_pytroll='{}'"\
            ", process_time_pytroll_exceeded='{}'"\
            ")>".format(
                self.count_timeslots,
                self.count_received_dailylog,
                self.count_failed_dailylog,
                self.count_received_afd,
                self.count_failed_afd,
                self.count_processed_pytroll,
                self.count_processed_pytroll_rel_afd,
                self.count_failed_pytroll,
                self.mean_process_time_pytroll,
                self.process_time_pytroll_exceeded)


def calc_qm_stats(rrd_dir, dailylog_config_filename, aldalog_config_filename,
                  product_name, timeslots,
                  allowed_process_time=None):
    res = QmStats()

    # AP6 Nr. 1 == timeslots
    res.count_timeslots = len(timeslots)

    # AP6 Nr. 2
    availability_dailylog = get_availability_dailylog(
        timeslots,
        product_name,
        dailylog_config_filename)
    failed_dailylog = [el[0] for el in availability_dailylog
                       if el[1] is False]
    res.count_failed_dailylog = len(failed_dailylog)
    received_dailylog = [el[0] for el in availability_dailylog
                         if el[1] is True]
    res.count_received_dailylog = len(received_dailylog)

    # AP6 Nr. 3
    availability_aldalog = get_availability_alda_log(
        timeslots,
        product_name,
        aldalog_config_filename)
    failed_aldalog = [el[0] for el in availability_aldalog
                      if el[1] is False]
    res.count_failed_afd = len(failed_aldalog)
    received_aldalog = [el[0] for el in availability_aldalog
                        if el[1] is True]
    res.count_received_afd = len(received_aldalog)

    # AP6 Nr. 4a (abs)
    rrd_filename = os.path.join(rrd_dir, product_name + '.rrd')
    availability_pytroll = rrd_fetch(rrd_filename, timeslots)
    failed_pytroll = [el[0] for el in availability_pytroll
                      if el[1][0] is None]
    res.count_failed_pytroll = len(failed_pytroll)

    processed_pytroll = [(el[0], el[1][0]) for el in availability_pytroll
                         if el[1][0] is not None]

    # AP6 Nr. 4b (rel)
    res.count_processed_pytroll = len(processed_pytroll)
    if res.count_received_afd:
        res.count_processed_pytroll_rel_afd = \
            float(res.count_processed_pytroll) / float(res.count_received_afd)

    # AP6 Nr. 5
    if res.count_processed_pytroll > 0:
        res.mean_process_time_pytroll = \
            (sum([el[1] for el in processed_pytroll]) /
                res.count_processed_pytroll)

    # AP6 Nr. 6
    if allowed_process_time is not None:
        res.process_time_pytroll_exceeded = \
            len([el[1] for el in processed_pytroll if el[1] >
                 allowed_process_time])

    return res


def calc_monthly_qm_stats(rrd_dir, dailylog_config_filename,
                          aldalog_config_filename,
                          product_name, product_rrd_steps, year, month,
                          allowed_process_time=None):

    # AP6 Nr. 1
    timeslots = calc_month_timeslots(year, month, product_rrd_steps)

    res = calc_qm_stats(rrd_dir,
                        dailylog_config_filename,
                        aldalog_config_filename,
                        product_name,
                        timeslots, allowed_process_time)

    # add additional infos to be stored in csv file
    res.param_period_month = month
    res.param_period_year = year
    res.param_product_name = product_name
    res.param_allowed_process_time = allowed_process_time
    res.param_steps = product_rrd_steps

    return res


def append_qm_stats_to_csv(qm_stats, csv_filename):
    fields = ['count_timeslots',
              'count_received_dailylog',
              'count_failed_dailylog',
              'count_received_afd',
              'count_failed_afd',
              'count_processed_pytroll',
              'count_processed_pytroll_rel_afd',
              'count_failed_pytroll',
              'mean_process_time_pytroll',
              'process_time_pytroll_exceeded',
              'param_product_name',
              'param_period_year',
              'param_period_month',
              'param_allowed_process_time',
              'param_steps']

    add_header = not os.path.isfile(csv_filename)
    with open(csv_filename, 'a') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields, dialect="excel")
        if add_header:
            writer.writeheader()
        writer.writerow(qm_stats.__dict__)
