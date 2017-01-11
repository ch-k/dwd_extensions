# -*- coding: utf-8 -*-
from fileinput import filename

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
import yaml
from datetime import datetime
import os
from dwd_extensions.qm.emc_dailylogs.repository import DailyLogEntry
from dwd_extensions.qm.emc_dailylogs.repository import RemarkEnum
from dwd_extensions.qm.emc_dailylogs.repository import Repository
from dwd_extensions.qm.emc_dailylogs.reader import EumetcastDailylogReaderReader


def _get_file_modtime(filename):
    return datetime.fromtimestamp(os.path.getmtime(filename))


class DailyLogService(object):
    '''
    Service providing information about current and historical satellite
    data availability
    '''

    def __init__(self, config=None, config_yml_filename=None):
        '''
        Constructor
        '''
        if config is None:
            if config_yml_filename is None:
                raise "Either config or config_yml_filename "\
                    "has to be specified!"
            self.filename = config_yml_filename

            with open(config_yml_filename, "r") as fid:
                self.config = yaml.safe_load(fid)
        else:
            self.config = config

        self.repo = Repository(
            self.config['daily_log_db_filename'],
            prod2dailylog_records_pattern_map=self.config[
                'prod2dailylog_records_pattern_map'])

    def import_dailylog_files(self, filenames):
        filenames = sorted(filenames, reverse=True, key=_get_file_modtime)
        for filename in filenames:
            self.import_dailylog_file(filename)

    def import_dailylog_file(self, filename):
        max_date = self.get_oldest_allowed_date()
        if max_date is not None:
            moddate = _get_file_modtime(filename)
            if moddate < max_date:
                print "skipping {}, file too old ({} < {})".format(filename,
                                                                   moddate,
                                                                   max_date)
                return
        print "importing " + filename
        reader = EumetcastDailylogReaderReader(filename)
        self.repo.add(reader.get_items())
        self.delete_old_entries()

    def get_records_for_timeslot(self, timeslot, product_name):
        records = self.repo.find_records_by_timeslot(timeslot, product_name)
        return records

    def get_record_remark_count(self, timeslot, product_name):
        '''returns dict with count of valid and invalid records
        belonging to specified timeslot and product_name
        result dict contains following entries:
            'total': *total record count*,
               'confirmed': *count RECEPTION_CONFIRMED*,
               'not confirmed': *count SENT_NOT_CONFIRMED*
               'not sent': *count NOT_SENT*
               'unknown': *count NOT_SENT*
               'total_invalid': TOTAL - CONFIRMED
        '''

        records = self.repo.find_records_by_timeslot(timeslot, product_name)
        remark_dict = {}
        for record in records:
            remark_dict.setdefault(record.remark, []).append(record)
        res = {'total': len(records),
               'confirmed': len(remark_dict.get(RemarkEnum.RECEPTION_CONFIRMED,
                                                [])),
               'not confirmed': len(remark_dict.get(
                   RemarkEnum.SENT_NOT_CONFIRMED, [])),
               'not sent': len(remark_dict.get(RemarkEnum.NOT_SENT, [])),
               'unknown': len(remark_dict.get(RemarkEnum.NOT_SENT, []))
               }
        res['total_invalid'] = res['total'] - res['confirmed']
        return res

    def delete_old_entries(self):
        days = self.config.get("max_age_days", 120)
        self.repo.delete_older_than(days)

    def get_oldest_allowed_date(self):
        days = self.config.get("max_age_days", 120)
        return self.repo.get_oldest_allowed_date(days)
