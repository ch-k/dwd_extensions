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

'''This module defines a service for accessing imported AFD alda log data
'''
import yaml
import os
from datetime import datetime
from dwd_extensions.qm.afd_alda_logs.repository import AldaLogEntry
from dwd_extensions.qm.afd_alda_logs.repository import Repository
from dwd_extensions.qm.afd_alda_logs.reader import AldaLogReader


def _get_file_modtime(filename):
    return datetime.fromtimestamp(os.path.getmtime(filename))


class AldaLogService(object):
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
            self.config['alda_log_db_filename'],
            prod2aldalog_records_pattern_map=self.config[
                'prod2aldalog_records_pattern_map'])

    def import_log_files(self, filenames):
        filenames = sorted(filenames, reverse=True, key=_get_file_modtime)
        for filename in filenames:
            self.import_log_file(filename)

    def import_log_file(self, filename):
        max_date = self.get_oldest_allowed_date()
        if max_date is not None:
            moddate = _get_file_modtime(filename)
            if moddate < max_date:
                print "skipping {}, file too old ({} < {})".format(filename,
                                                                   moddate,
                                                                   max_date)
                return
        print "importing " + filename
        reader = AldaLogReader(filename,
                               self.config['reader_filename_patterns'])
        self.repo.add(reader.get_items())
        self.delete_old_entries()

    def get_records_for_timeslot(self, timeslot, product_name):
        (records, res_ok) = self.repo.find_records_by_timeslot(timeslot,
                                                               product_name)
        return (records, res_ok)

    def get_oldest_allowed_date(self):
        days = self.config.get("max_age_days", 120)
        return self.repo.get_oldest_allowed_date(days)

    def delete_old_entries(self):
        days = self.config.get("max_age_days", 120)
        self.repo.delete_older_than(days)
