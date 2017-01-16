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

'''This module defines a readers for satellite incidents and announcements
'''
from abc import ABCMeta, abstractmethod
import yaml
from datetime import datetime
import os
import shutil


def get_file_modtime(filename):
    return datetime.fromtimestamp(os.path.getmtime(filename))


class BaseService:
    '''
    Service providing information about current and historical satellite
    data availability
    '''
    __metaclass = ABCMeta

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

        self.repo = None

    def import_files(self, filenames, move_to_directory=None):
        filenames = sorted(filenames, reverse=True, key=get_file_modtime)
        for filename in filenames:
            self.import_file(filename)
            if move_to_directory:
                if not os.path.exists(move_to_directory):
                    os.makedirs(move_to_directory)
                if os.path.isdir(move_to_directory):
                    try:
                        os.remove(os.path.join(move_to_directory,
                                               os.path.basename(filename)))
                    except OSError:
                        pass
                    shutil.move(filename, move_to_directory)
                    print "{} moved to {}".format(filename,
                                                  move_to_directory)

    @abstractmethod
    def import_file(self, filename):
        pass

    def delete_old_entries(self):
        days = self.config.get("max_age_days", 120)
        self.repo.delete_older_than(days)

    def get_oldest_allowed_date(self):
        days = self.config.get("max_age_days", 120)
        return self.repo.get_oldest_allowed_date(days)

    def dump(self):
        '''
        print all stored entries to stdout
        '''
        print "dumping current database content:"
        recs = self.repo.find_all()
        for rec in recs:
            print rec
