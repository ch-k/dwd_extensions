# -*- coding: utf-8 -*-
#
# Copyright (c) 2016
#
# Author(s):
#
#   Christian Kliche <chk@ebp.de>
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''utility functions to fill and access rrd files

'''

import logging
import random
import pytz
from datetime import datetime, timedelta

try:
    import rrdtool as rrd
except ImportError:
    rrd = None

LOGGER = logging.getLogger("postprocessor")
HOUR = 60 * 60
DAY = HOUR * 24
MONTH = DAY * 31


def to_unix_seconds(dt):
    # http://stackoverflow.com/a/11743262
    if dt.tzinfo is None:
        return int((dt - datetime(1970, 1, 1)).total_seconds())
    else:
        return int((dt - datetime(1970, 1, 1,
                                  tzinfo=pytz.utc)).total_seconds())
    # return int(dt.strftime("%s"))


def _rra(cf, interval, timespan, step_size):
        rrd_param = 'RRA:{}:0.5:{}:{}'.format(
            cf,
            interval / step_size,
            timespan / interval)
        return rrd_param


def create_rrd_file(rrd_fname, timeslot_sec, rrd_steps):
    if rrd:
        rrd.create(
            rrd_fname,
            '--start', str(timeslot_sec - rrd_steps),
            # step size 900s=15min
            # each step represents one time slot
            '--step', str(rrd_steps),
            ['DS:epi2product:GAUGE:{}:U:U'.format(
                rrd_steps),
             'DS:timeslot2product:GAUGE:{}:U:U'.format(
                rrd_steps)],
            # keep step_size max for 4 months
            _rra('MAX', rrd_steps, 4 * MONTH, rrd_steps),
            # hourly average over 12 months days
            _rra('AVERAGE', HOUR, 12 * MONTH, rrd_steps),
            # hourly maximum over 12 months days
            _rra('MAX', HOUR, 12 * MONTH, rrd_steps),
            # hourly minumum over 12 months days
            _rra('MIN', HOUR, 12 * MONTH, rrd_steps))
    else:
        LOGGER.info("rrd update skipped, rrdtool not available")


def update_rrd_file(rrd_fname, timeslot_sec, t_epi, t_product):
    if rrd:
        update_stmt = str(timeslot_sec) + \
            ':' + str(int(t_product - t_epi)) + \
            ':' + str(int(t_product - timeslot_sec))
        LOGGER.debug("rrd update %s %s" % (rrd_fname, update_stmt))
        rrd.update(rrd_fname, update_stmt)
    else:
        LOGGER.info("rrd update skipped, rrdtool not available")


def create_sample_rrd(filename, timeslots, rrd_steps):
    create_rrd_file(filename,
                    to_unix_seconds(timeslots[0]),
                    rrd_steps)

    for sample_timeslot in timeslots:
        ran_num = 2.0 * random.random()
        update_rrd_file(
            filename,
            to_unix_seconds(sample_timeslot),
            to_unix_seconds(sample_timeslot +
                            timedelta(seconds=int(ran_num * 500))),
            to_unix_seconds(sample_timeslot +
                            timedelta(seconds=int(ran_num * 700)))
        )


def fetch(filename, timeslots):
    step = rrd.info(filename)['step']
    data = rrd.fetch(
        filename,
        'MAX',
        # '--start', timeslots[0].strftime(FETCH_DATEFORMAT),
        '--start', str(to_unix_seconds(timeslots[0]) - step),
        '--end', str(to_unix_seconds(timeslots[-1])))

    # data shift by step size, so add one to match
    # the output of "rrdtool dump"
    basetime = data[0][0] + step
    basetime_dt = datetime.fromtimestamp(basetime, tz=pytz.utc)
    dt_dict = {}
    for n, elem in enumerate(data[2]):
        dt_dict[basetime_dt + timedelta(seconds=n * step)] = elem

    res = [(ts, dt_dict.get(ts, (None, None))) for ts in timeslots]
    return res
