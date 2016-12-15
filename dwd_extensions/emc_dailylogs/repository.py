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

from datetime import datetime, timedelta
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


class RemarkEnum(enum.Enum):
    RECEPTION_CONFIRMED = "reception_confirmed"
    SENT_NOT_CONFIRMED = "sent_not_confirmed"
    NOT_SENT = "not_sent"
    UNKNOWN = "unknown"


class DailyLogEntry(Base):
    '''represents EUMETCAST Daily Log entry / line '''
    __tablename__ = 'daily_log_entry'
    # __table_args__ = {'sqlite_autoincrement': True}
    # id = Column(Integer, primary_key=True)
    source = Column(String, index=True, primary_key=True)
    service = Column(String, index=True, primary_key=True)
    reference_time = Column(DateTime)
    filename = Column(String)
    received_timeliness = Column(DateTime)
    remark = Column(Enum(RemarkEnum))
    slot_time = Column(DateTime, index=True, primary_key=True)
    satellite = Column(String, index=True, primary_key=True)
    channel = Column(String, index=True, primary_key=True)
    segment = Column(String, index=True, primary_key=True)

    def __repr__(self):
        return "<DailyLogEntry("\
            "source='{}'"\
            ", service='{}'"\
            ", reference_time='{}'"\
            ", filename='{}'"\
            ", received_timeliness='{}'"\
            ", remark='{}'"\
            ", slot_time='{}'"\
            ", satellite='{}'"\
            ", channel='{}'"\
            ", segment='{}'"\
            ")>".format(
                # self.id,
                self.source,
                self.service,
                self.reference_time,
                self.filename,
                self.received_timeliness,
                self.remark,
                self.slot_time,
                self.satellite,
                self.channel,
                self.segment)


class Repository(object):
    ''' Class to interact with underlying repository '''
    def __init__(self, database, app_root=None,
                 prod2dailylog_records_pattern_map=None):
        ''' Initialize repository '''

        if ':///' not in database:
            database = 'sqlite:///%s' % database

        self.engine = create_engine('%s' % database, echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        self.prod2dailylog_records_pattern_map = \
            prod2dailylog_records_pattern_map

    def add(self, records):
        ''' Insert a record into the repository '''

        try:
            # fast but constraint violation for repeated imports
            # self.session.add_all(records)
            for record in records:
                self.session.merge(record)
            self.session.commit()
        except Exception as err:
            self.session.rollback()
            raise

    def find_all(self):
        ''' find all records in repository '''
        return self.session.query(DailyLogEntry).all()

    def delete_older_than(self, days):
        ''' delete all records with reference_time older
        than *days* before newest record '''
        max_date = self.session.query(
            func.max(DailyLogEntry.reference_time)).select_from(
                DailyLogEntry).scalar()

        if max_date > datetime.utcnow():
            print "max date in database is in future, using current date"
            max_date = datetime.utcnow()

        max_date = max_date - timedelta(days=days)

        print "deleting all records before {}".format(max_date)

        self.session.query(DailyLogEntry).filter(
            DailyLogEntry.reference_time < max_date).delete()

    def record_count(self):
        ''' return count of accouncements in repository '''
        return self.session.query(
            func.count('*')).select_from(DailyLogEntry).scalar()

    def find_records_by_timeslot(self, timeslot, product_name=None):
        ''' find all dailylog records in repository for specified
        *timeslot* and (optional) *product_name*

        To determine if an record could be relevant for the
        *product_name*, the ctor parameter *prod2dailylog_records_pattern_map*
        is used.
        '''

        if product_name in (None, '*') \
                or not self.prod2dailylog_records_pattern_map:
            records = self.session.query(DailyLogEntry).filter(
                DailyLogEntry.slot_time == timeslot).all()
            return records

        dailylog_records_patterns = \
            self._get_pat_for_prod(product_name)

        filter = [and_(
            DailyLogEntry.source.like(pat['source']),
            DailyLogEntry.service.like(pat['service']),
            DailyLogEntry.satellite.like(pat['satellite']),
            DailyLogEntry.channel.like(pat['channel']),
            DailyLogEntry.segment.like(pat['segment']))
            for pat in dailylog_records_patterns]

        records = self.session.query(DailyLogEntry).filter(
            and_(DailyLogEntry.slot_time == timeslot,
                 or_(*filter))).all()

        return records

    def _get_pat_for_prod(self, product_name):
        ''' returns affected entity patterns for product
        with name *product_name*
        '''
        if self.prod2dailylog_records_pattern_map:
            for key, value in self.prod2dailylog_records_pattern_map.items():
                if re.match(key, product_name):
                    return value
            return []
        return None
