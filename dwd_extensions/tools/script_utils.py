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
'''utility functions for python scripts
'''
import re
from fnmatch import fnmatch
import os


def check_required_arguments(opts, parser):
    """ exit with error message if required arguments are missing"""

    missing_options = []
    for option in parser.option_list:
        if re.match(r'^\[REQUIRED\]', option.help) \
                and eval('opts.' + option.dest) == None:
            missing_options.extend(option._long_opts)
    if len(missing_options) > 0:
        parser.print_help()
        parser.error('Missing REQUIRED parameters: ' + str(missing_options))


def listfiles(d, pattern):
    """return list of files in directory"""
    return [os.path.join(d, o) for o in os.listdir(d)
            if os.path.isfile(os.path.join(d, o)) and
            fnmatch(o, pattern)]
