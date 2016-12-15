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
import pytz
from dwd_extensions.emc_dailylogs.service import DailyLogService


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
