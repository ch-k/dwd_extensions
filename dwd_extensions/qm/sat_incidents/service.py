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
from dwd_extensions.qm.sat_incidents.repository import Announcement
from dwd_extensions.qm.sat_incidents.repository import AnnouncementImpactEnum
from dwd_extensions.qm.sat_incidents.repository import Repository
from dwd_extensions.qm.sat_incidents.reader \
    import EumetsatUserNotifcationReader
from dwd_extensions.qm.importer_base import BaseService, get_file_modtime


class SatDataAvailabilityService(BaseService):
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
            self.config['sat_incidents_db_filename'],
            prod2affected_entity_pattern_map=self.config[
                'product2affected_entity_map'])

    def import_file(self, filename):
        reader = EumetsatUserNotifcationReader(filename)
        self.repo.add(reader.get_items())

    def get_worst_announcement(self, timeslot, product_name):
        anns = self.repo.find_announcments_by_timeslot(timeslot, product_name)
        anns = sorted(anns, key=self._ann_prio)
        if len(anns) > 0:
            return anns[0]
        return None

    _ann_impact_prio = {
        AnnouncementImpactEnum.DATA_UNAVAILABLE: 0,
        AnnouncementImpactEnum.DATA_INTERRUPTED: 1,
        AnnouncementImpactEnum.DATA_DEGRADED: 2,
        AnnouncementImpactEnum.DATA_DELAYED: 3
    }

    def _ann_prio(self, ann):
        prio = self._ann_impact_prio.get(ann.impact, 999)
        return prio

    def get_data_availability_error(self, timeslot, product_name):
        ann = self.get_worst_announcement(timeslot, product_name)
        if ann:
            return ann.impact
        return None
