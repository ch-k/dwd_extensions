# -*- coding: utf-8 -*-
from sphinx.builders.gettext import timestamp
from _csv import Dialect

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
'''This module defines a readers for log files created by AFD alda
'''
import csv
from dwd_extensions.qm.afd_alda_logs.repository import AldaLogEntry
from trollsift.parser import parse as trollsift_parse
from datetime import datetime
from os.path import basename

DATE_FORMAT = '%Y%m%d%H%M%S'
TIME_ONLY_FORMAT = '%H:%M:%S'


class AldaLogReader(object):
    '''
    Reader for log files created by AFD alda
    '''

    def __init__(self, aldalog_filename, filename_patterns):
        '''
        Constructor
        '''
        self.filename = aldalog_filename
        self.filename_patterns = filename_patterns

    def get_items(self):
        '''
        Generator for entries in csv file
        '''
        with open(self.filename, 'r') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=' ',
                                    fieldnames=['timestamp',
                                                'dest_host',
                                                'filename'],
                                    dialect=Dialect(skipinitialspace=True))
            for row in reader:
                try:
                    record = AldaLogEntry(
                        timestamp=self._parse_datetime(
                            row,
                            'timestamp',
                            DATE_FORMAT),
                        dest_host=row['dest_host'],
                        filename=row['filename'],
                        slot_time=self._parse_slot_time(
                            row,
                            'filename')
                    )
                    yield record

                except Exception as ex:
                    print row
                    print str(ex)

    def _parse_datetime(self, row, field, format):
        val = row.get(field, None)
        if val in (None, ''):
            return None
        return datetime.strptime(val, format)

    def _parse_slot_time(self, row, field):
        val = row.get(field, None)
        if val in (None, ''):
            return None
        for filename_pat in self.filename_patterns:
            try:
                vals = trollsift_parse(filename_pat, val)
                return vals['time']
            except:
                # try next
                pass
        return None