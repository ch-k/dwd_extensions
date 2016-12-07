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
from lxml import etree
from dwd_extensions.sat_incidents.repository import Announcement
from dwd_extensions.sat_incidents.repository import AffectedEntity
from dwd_extensions.sat_incidents.repository import AnnouncementImpactEnum
from dwd_extensions.sat_incidents.repository import AnnouncementTypeEnum
from datetime import datetime

DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'


class EumetsatUserNotifcationReader(object):
    '''
    Reader for EUMETSAT User Notification Service xml
    files.
    '''

    def __init__(self, xml_filename):
        '''
        Constructor
        '''
        self.filename = xml_filename

    def get_items(self):
        '''
        Generator for announcements in xml file
        '''
        doc = etree.parse(self.filename)
        for ann_el in doc.getiterator('announcement'):
            start_time = datetime.strptime(ann_el.attrib['start-time'],
                                           DATE_FORMAT)
            try:
                end_time = datetime.strptime(ann_el.attrib['end-time'],
                                             DATE_FORMAT)
            except KeyError:
                end_time = None

            try:
                status = ann_el.attrib['status']
            except KeyError:
                status = None

            try:
                impact = self._parse_impact(ann_el.attrib['impact'])
            except KeyError:
                impact = AnnouncementImpactEnum.NONE

            ann = Announcement(
                importsource='EUMETSAT_UNS',
                number=ann_el.attrib['ann-number'],
                revision=ann_el.attrib['ann-revision'],
                subject=ann_el.attrib['ann-subject'],
                start_time=start_time,
                end_time=end_time,
                impact=impact,
                ann_type=self._parse_type(ann_el.attrib['ann-type']),
                status=status
            )

            for sat_el in ann_el.getiterator('satellite'):
                aff_entity = AffectedEntity(name=sat_el.text.strip().upper())
                ann.affected_entities.append(aff_entity)
            for os_el in ann_el.getiterator('operational-service'):
                aff_entity = AffectedEntity(
                    name=unicode(os_el.attrib['name'].strip().upper()))
                ann.affected_entities.append(aff_entity)
            for pg_el in ann_el.getiterator('product-group'):
                aff_entity = AffectedEntity(
                    name=unicode(pg_el.attrib['name'].strip().upper()))
                ann.affected_entities.append(aff_entity)

            yield ann

    def _parse_impact(self, input_string):
        input_string = input_string.lower()
        if 'degrade' in input_string:
            return AnnouncementImpactEnum.DATA_DEGRADED
        elif 'interrupt' in input_string:
            return AnnouncementImpactEnum.DATA_INTERRUPTED
        elif 'delay' in input_string:
            return AnnouncementImpactEnum.DATA_DELAYED
        elif 'unavailab' in input_string:
            return AnnouncementImpactEnum.DATA_UNAVAILABLE

        return AnnouncementImpactEnum.UNKNOWN

    def _parse_type(self, input_string):
        input_string = input_string.lower()
        if 'alert' in input_string:
            return AnnouncementTypeEnum.ALERT
        elif 'planned' in input_string:
            return AnnouncementTypeEnum.PLANNED_MAINTENANCE
        elif 'enhance' in input_string:
            return AnnouncementTypeEnum.SERVICE_ENHANCEMENT

        return AnnouncementTypeEnum.UNKNOWN
