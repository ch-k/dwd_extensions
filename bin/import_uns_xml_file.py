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
"""Script to import EUMETSAT user notification service files
into cache database
"""
from optparse import OptionParser
from dwd_extensions.qm.sat_incidents.service import SatDataAvailabilityService


def main():
    """ main script function"""
    # override default formater to allow line breaks
    OptionParser.format_description = \
        lambda self, formatter: self.description
    OptionParser.format_epilog = \
        lambda self, formatter: self.epilog

    description = """\
Importer for EUMETSAT User Notification Service XML files
"""
    parser = OptionParser(description=description)
    parser.add_option(
        "-f", "--uns-xml-file",
        action="store",
        type="string",
        dest="uns_xml_file",
        metavar="FILE",
        help="path to EUMETSAT User Notification Service XML file")

    parser.add_option(
        "-s", "--sat-data-availability-config",
        action="store",
        type="string",
        dest="sat_availability_config",
        metavar="FILE",
        help="path to configuration of "
        "satellite availability service")

    parser.add_option(
        "-d", "--dump",
        action="store_true",
        dest="dump",
        default=False,
        help="dump database content")

    try:
        (options, _) = parser.parse_args()
    except:
        parser.print_help()
        exit()

    service = SatDataAvailabilityService(
        config_yml_filename=options.sat_availability_config)
    if options.dump:
        service.dump()
    else:
        print "starting import ..."
        service.import_file(options.uns_xml_file)
        print "import finished"


if __name__ == "__main__":
    main()
