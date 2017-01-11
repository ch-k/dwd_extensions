#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Ernst Basler + Partner

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

from optparse import OptionParser
from dwd_extensions.qm.afd_alda_logs.service import AldaLogService
from fnmatch import fnmatch
import os


def listfiles(d, pattern):
    """return list of files in directory"""
    return [os.path.join(d, o) for o in os.listdir(d)
            if os.path.isfile(os.path.join(d, o)) and
            fnmatch(o, pattern)]

if __name__ == "__main__":
    # override default formater to allow line breaks
    OptionParser.format_description = \
        lambda self, formatter: self.description
    OptionParser.format_epilog = \
        lambda self, formatter: self.epilog

    description = """\
Importer for AFD alda log files
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
        default="*",
        metavar="PATTERN",
        help="file pattern to match files in input directory")

    parser.add_option(
        "-c", "--config-file",
        action="store",
        type="string",
        dest="config_file",
        metavar="FILE",
        help="path to configuration of "
        "alda log service")

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

    service = AldaLogService(
        config_yml_filename=options.config_file)
    if options.dump:
        service.dump()
    else:
        print "starting import ..."
        csv_files = listfiles(options.directory, options.file_pattern)
        for csv_file in csv_files:
            print "importing " + csv_file
            service.import_log_file(csv_file)
        print "import finished"
