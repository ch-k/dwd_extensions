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

'''This module defines a readers for satellite incidents and announcements
'''
import csv
from dwd_extensions.qm.emc_dailylogs.repository import DailyLogEntry, RemarkEnum
from datetime import datetime
from os.path import basename

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
TIME_ONLY_FORMAT = '%H:%M:%S'


class EumetcastDailylogReaderReader(object):
    '''
    Reader for EUMETCAST Daily Logs
    '''

    def __init__(self, dailylog_filename):
        '''
        Constructor
        '''
        self.filename = dailylog_filename
        fn_parts = basename(self.filename).split('-')
        self.source = fn_parts[2].strip('_')
        self.service = fn_parts[3].strip('_')

    def get_items(self):
        '''
        Generator for entries in csv file
        '''
        with open(self.filename, 'r') as csvfile:
            reader = csv.DictReader(csvfile, delimiter='|')
            for row in reader:
                try:
                    record = DailyLogEntry(
                        source=self.source,
                        service=self.service,
                        reference_time=self._parse_datetime(
                            row,
                            'reference time',
                            DATE_FORMAT),
                        filename=row['filename'],
                        received_timeliness=self._parse_datetime(
                            row,
                            'received timeliness',
                            TIME_ONLY_FORMAT),
                        remark=self._parse_remark(row['remark']),
                        slot_time=datetime.strptime(
                            row['slot time'],
                            DATE_FORMAT),
                        satellite=row['satellite'],
                        channel=row['channel'],
                        segment=row['segment']
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

    def _parse_remark(self, input_string):
        input_string = input_string.lower()
        if 'reception_confirmed' in input_string:
            return RemarkEnum.RECEPTION_CONFIRMED
        elif 'sent_not_confirmed' in input_string:
            return RemarkEnum.SENT_NOT_CONFIRMED
        elif 'not_sent' in input_string:
            return RemarkEnum.NOT_SENT
        return RemarkEnum.UNKNOWN
