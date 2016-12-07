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

'''This module defines a repository for satellite incidents and announcements
'''

from datetime import datetime
import logging
import os
import enum
import re
from sqlalchemy import Column, String, Integer, DateTime, Table, ForeignKey
from sqlalchemy import ForeignKeyConstraint, Enum
from sqlalchemy import create_engine, func, and_, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()

association_table = Table(
    'ann2affectedentity',
    Base.metadata,
    Column('ann_number', Integer),
    Column('ann_importsource', String),
    Column('ae_name', String, ForeignKey('affected_entity.name')),
    ForeignKeyConstraint(
        ('ann_number', 'ann_importsource'),
        ('announcement.number', 'announcement.importsource'))
)


class AnnouncementTypeEnum(enum.Enum):
    ALERT = "service-alert"
    PLANNED_MAINTENANCE = "planned-maintenance"
    SERVICE_ENHANCEMENT = "service-enhancement"
    UNKNOWN = "unknown"


class AnnouncementImpactEnum(enum.Enum):
    DATA_UNAVAILABLE = "data-unavailable"
    DATA_INTERRUPTED = "data-interrupted"
    DATA_DEGRADED = "data-degraded"
    DATA_DELAYED = "data-delayed"
    NONE = "none"
    UNKNOWN = "unknown"


class Announcement(Base):
    ''' EUMETSAT UNS announcement '''
    __tablename__ = 'announcement'
    number = Column(Integer, primary_key=True)
    importsource = Column(String, primary_key=True)
    revision = Column(Integer)
    subject = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    impact = Column(Enum(AnnouncementImpactEnum))
    ann_type = Column(Enum(AnnouncementTypeEnum))
    status = Column(String)
    affected_entities = relationship(
        "AffectedEntity",
        secondary=association_table,
        backref="announcements")

    def __repr__(self):
        return "<Announcement("\
            "number='{}'"\
            ", revision='{}'"\
            ", subject='{}'"\
            ", impact='{}'"\
            ", type='{}'"\
            ", start='{}'"\
            ", end='{}'"\
            ", affected_entities='{}'"\
            ")>".format(
                self.number,
                self.revision,
                self.subject,
                self.impact,
                self.ann_type,
                self.start_time,
                self.end_time,
                self.affected_entities)


class AffectedEntity(Base):
    __tablename__ = 'affected_entity'
    # id = Column('id', Integer, primary_key=True), sqlite_autoincrement=True)
    name = Column(String, primary_key=True)

    def __repr__(self):
        return u"<AffectedEntity(name='{0}')>".format(
            self.name).encode('utf8')


class Repository(object):
    ''' Class to interact with underlying repository '''
    def __init__(self, database, app_root=None,
                 prod2affected_entity_pattern_map=None):
        ''' Initialize repository '''

        if ':///' not in database:
            database = 'sqlite:///%s' % database

        self.engine = create_engine('%s' % database, echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        self.prod2affected_entity_pattern_map = \
            prod2affected_entity_pattern_map

    def add(self, announcements):
        ''' Insert a record into the repository '''

        try:
            # self.session.begin()
            for ann in announcements:
                # session.add_all
                self.session.merge(ann)
            self.session.commit()
        except Exception as err:
            self.session.rollback()
            raise

    def find_all(self):
        ''' find all accouncements in repository '''
        return self.session.query(Announcement).all()

    def announcement_count(self):
        ''' return count of accouncements in repository '''
        return self.session.query(
            func.count('*')).select_from(Announcement).scalar()

    def affected_entity_count(self):
        ''' return count of potentially affected entities in repository '''
        return self.session.query(
            func.count('*')).select_from(AffectedEntity).scalar()

    def find_announcments_by_timeslot(self, timeslot, product_name=None):
        ''' find all accouncements in repository for specified
        *timeslot* and (optional) *product_name*

        To determine if an announcement could be relevant for the
        *product_name*, the ctor parameter *prod2affected_entity_pattern_map*
        is used.
        '''
        anns = self.session.query(Announcement).filter(
            and_(Announcement.start_time <= timeslot,
                 or_(Announcement.end_time >= timeslot,
                     Announcement.end_time.is_(None)))).all()

        if product_name in (None, '*') \
                or not self.prod2affected_entity_pattern_map:
            return anns

        affected_entity_patterns = \
            self._get_aff_entity_pat_for_prod(product_name)

        return [a for a in anns
                if self._aff_entity_pat_matches(
                    a,
                    affected_entity_patterns)]

    def _get_aff_entity_pat_for_prod(self, product_name):
        ''' returns affected entity patterns for product
        with name *product_name*
        '''
        if self.prod2affected_entity_pattern_map:
            for key, value in self.prod2affected_entity_pattern_map.items():
                if re.match(key, product_name):
                    return value
            return []
        return None

    def _aff_entity_pat_matches(self,
                                announcement,
                                affected_entity_patterns):
        ''' returns affected entity of *announcement* that match one of
        the specified patterns in list affected_entity_patterns
        with name *product_name*
        '''
        for aep in affected_entity_patterns:
            for ae in announcement.affected_entities:
                if re.match(aep, ae.name):
                    return True
        return False
