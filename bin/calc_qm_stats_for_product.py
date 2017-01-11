#!/usr/bin/env python

import os
import stat
import fnmatch
import re
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


def main():

    # override default formater to allow line breaks
    OptionParser.format_description = \
        lambda self, formatter: self.description

    description = """\
This script calculates monthly QM statistics for a product and appends the
results to csv file.
"""

    parser = OptionParser(description=description)
    parser.add_option("--rrd-directory",
                      action="store",
                      type="string",
                      dest="rrddir",
                      metavar="PATH",
                      help="[REQUIRED] Path to rrd files.")

    parser.add_option("--daily-log-config",
                      action="store",
                      type="string",
                      dest="daily_log_config",
                      metavar="FILE",
                      help="[REQUIRED] Path to configuration file for cached"
                      "EUMETCAST daily log access.")

    parser.add_option("--alda-log-config",
                      action="store",
                      type="string",
                      dest="alda_log_config",
                      metavar="FILE",
                      help="[REQUIRED] Path to configuration file for cached"
                      "AFD alda log access.")

    parser.add_option("-p", "--product-name",
                      action="store",
                      type="string",
                      dest="product_name",
                      metavar="PRODUCT_NAME",
                      help="[REQUIRED] Name of the product to calculate statistics for.")

    parser.add_option("-s", "--product-rrd-steps",
                      action="store",
                      type="int",
                      default=900,
                      dest="product_rrd_steps",
                      metavar="SECONDS",
                      help="Steps/interval of between two timeslots "
                      "of the product.")

    parser.add_option("-y", "--year",
                      action="store",
                      type="int",
                      dest="year",
                      metavar="YEAR",
                      help="[REQUIRED] Year of the time period to be analysed.")

    parser.add_option("-m", "--month",
                      action="store",
                      type="int",
                      dest="month",
                      metavar="MONTH",
                      help="[REQUIRED] Month of the time period to be analysed. i.e. "
                      "'12' for december")

    parser.add_option("--allowed-process-time",
                      action="store",
                      type="float",
                      dest="allowed_process_time",
                      metavar="SECONDS",
                      help="Maximum allowed proessing time for one timeslot "
                      "in pytroll. The timeslot will be handled as 'delayed'"
                      " this threshold is exceeded.")

    parser.add_option("-o", "--output-csv-file",
                      action="store",
                      type="string",
                      dest="output_csv_file",
                      metavar="FILE",
                      help="[REQUIRED] Path to csv file to append results. If this file "
                      "does not exist, a new file with header line "
                      "will be created.")

    try:
        (options, _) = parser.parse_args()
    except:
        parser.print_help()
        exit()

    checkRequiredArguments(options, parser)

    res = calc_monthly_qm_stats(options.rrddir,
                                options.daily_log_config,
                                options.alda_log_config,
                                options.product_name,
                                options.product_rrd_steps,
                                options.year,
                                options.month,
                                options.allowed_process_time)
    print res
    append_qm_stats_to_csv(res, options.output_csv_file)

if __name__ == "__main__":
    main()
