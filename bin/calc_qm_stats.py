#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2017
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
"""Script for calculating monthly QM statistics for a bunch of products
"""
import calendar
from optparse import OptionParser
import yaml
from datetime import datetime
from dwd_extensions.qm.stats import append_qm_stats_to_csv
from dwd_extensions.qm.stats import calc_monthly_qm_stats
from dwd_extensions.tools.script_utils import check_required_arguments


def add_months(sourcedate, months):
    """ add *months* to the *sourcedate"
    http://stackoverflow.com/a/4131114
    """
    month = sourcedate.month - 1 + months
    year = int(sourcedate.year + month / 12)
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return datetime(year, month, day)


def main():
    """ main script function"""

    # override default formater to allow line breaks
    OptionParser.format_description = \
        lambda self, formatter: self.description

    description = """\
This script calculates monthly QM statistics for a month and appends the
results to csv file.
"""

    parser = OptionParser(description=description)

    parser.add_option("--config",
                      action="store",
                      type="string",
                      dest="config",
                      metavar="FILE",
                      help="[REQUIRED] Path to configuration file")

    parser.add_option("-y", "--year",
                      action="store",
                      type="int",
                      default=None,
                      dest="year",
                      metavar="YEAR",
                      help="Year of the time period to be analysed.")

    parser.add_option("-m", "--month",
                      action="store",
                      type="int",
                      default=None,
                      dest="month",
                      metavar="MONTH",
                      help="Month of the time period to be analysed. i.e. "
                      "'12' for december")

    try:
        (options, _) = parser.parse_args()
    except:
        parser.print_help()
        exit()

    check_required_arguments(options, parser)

    with open(options.config, "r") as fid:
        config = yaml.safe_load(fid)

    year = options.year
    month = options.month
    now = datetime.now()
    if year is None or month is None:
        prev_month_date = add_months(now, -1)
        year = prev_month_date.year
        month = prev_month_date.month

    for product_cfg in config['products']:
        res = calc_monthly_qm_stats(config['rrd_directory'],
                                    config['daily_log_config'],
                                    config['alda_log_config'],
                                    product_cfg['name'],
                                    product_cfg['steps'],
                                    year,
                                    month,
                                    product_cfg['allowed_process_time'])
        print res
        append_qm_stats_to_csv(res, product_cfg['output_csv_file'])

if __name__ == "__main__":
    main()
