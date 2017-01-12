#!/usr/bin/env python
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
"""Script to import EUMETCAST daily log files into cache database
"""
from optparse import OptionParser
from dwd_extensions.qm.emc_daily_logs.service import DailyLogService
from dwd_extensions.tools.script_utils import listfiles


def main():
    """ main script function"""
    # override default formater to allow line breaks
    OptionParser.format_description = \
        lambda self, formatter: self.description
    OptionParser.format_epilog = \
        lambda self, formatter: self.epilog

    description = """\
Importer for EUMETCAST Daily Log files
"""
    parser = OptionParser(description=description)
    parser.add_option(
        "-d", "--directory",
        action="store",
        type="string",
        dest="directory",
        metavar="FILE",
        help="path to daily log files directory")

    parser.add_option(
        "-p", "--file-pattern",
        action="store",
        type="string",
        dest="file_pattern",
        default="E-UNS*",
        metavar="PATTERN",
        help="file pattern to match files in input directory")

    parser.add_option(
        "-c", "--config-file",
        action="store",
        type="string",
        dest="config_file",
        metavar="FILE",
        help="path to configuration of "
        "daily log service")

    parser.add_option(
        "--dump",
        action="store_true",
        dest="dump",
        default=False,
        help="dump database content")

    try:
        (options, _) = parser.parse_args()
    except:
        parser.print_help()
        exit()

    service = DailyLogService(
        config_yml_filename=options.config_file)
    if options.dump:
        service.dump()
    else:
        print "starting import ..."
        csv_files = listfiles(options.directory, options.file_pattern)
        service.import_files(csv_files)
        print "import finished"

if __name__ == "__main__":
    main()
