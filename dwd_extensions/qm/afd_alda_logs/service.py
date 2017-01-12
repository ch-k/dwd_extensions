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
from dwd_extensions.qm.afd_alda_logs.repository import AldaLogEntry
from dwd_extensions.qm.afd_alda_logs.repository import Repository
from dwd_extensions.qm.afd_alda_logs.reader import AldaLogReader
from dwd_extensions.qm.importer_base import BaseService, get_file_modtime


class AldaLogService(BaseService):
    '''
    Service providing information about current and historical satellite
    data availability
    '''

    def __init__(self, config=None, config_yml_filename=None):
        '''
        Constructor
        '''
        BaseService.__init__(self, config, config_yml_filename)

        self.repo = Repository(
            self.config['alda_log_db_filename'],
            prod2aldalog_records_pattern_map=self.config[
                'prod2aldalog_records_pattern_map'])

    def import_file(self, filename):
        max_date = self.get_oldest_allowed_date()
        if max_date is not None:
            moddate = get_file_modtime(filename)
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
