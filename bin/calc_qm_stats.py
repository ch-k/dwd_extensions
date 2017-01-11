#!/usr/bin/env python

import os
import stat
import fnmatch
import re
import yaml
import calendar
from os.path import basename
from os.path import splitext
from tempfile import mkstemp
from datetime import datetime
from datetime import timedelta
from optparse import OptionParser
from dwd_extensions.qm.stats import append_qm_stats_to_csv
from dwd_extensions.qm.stats import calc_monthly_qm_stats


def checkRequiredArguments(opts, parser):
    missing_options = []
    for option in parser.option_list:
        if re.match(r'^\[REQUIRED\]', option.help) and eval('opts.' + option.dest) == None:
            missing_options.extend(option._long_opts)
    if len(missing_options) > 0:
        parser.print_help()
        parser.error('Missing REQUIRED parameters: ' + str(missing_options))


def add_months(sourcedate, months):
    ''' http://stackoverflow.com/a/4131114
    '''
    month = sourcedate.month - 1 + months
    year = int(sourcedate.year + month / 12)
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return datetime(year, month, day)


def main():

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

    checkRequiredArguments(options, parser)

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
