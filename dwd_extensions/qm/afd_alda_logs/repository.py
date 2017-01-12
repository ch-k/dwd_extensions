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

'''This module defines a repository for log files created by AFD alda
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


class AldaLogEntry(Base):
    '''represents alda Log entry / line '''
    __tablename__ = 'alda_log_entry'
    dest_host = Column(String, index=True, primary_key=True)
    filename = Column(String, index=True, primary_key=True)
    slot_time = Column(DateTime, index=True)
    timestamp = Column(DateTime)

    def __repr__(self):
        return "<AldaLogEntry("\
            "dest_host='{}'"\
            ", filename='{}'"\
            ", slot_time='{}'"\
            ", timestamp='{}'"\
            ")>".format(
                self.dest_host,
                self.filename,
                self.slot_time,
                self.timestamp)


class Repository(object):
    ''' Class to interact with underlying repository '''
    def __init__(self, database, app_root=None,
                 prod2aldalog_records_pattern_map=None):
        ''' Initialize repository '''

        if ':///' not in database:
            database = 'sqlite:///%s' % database

        self.engine = create_engine('%s' % database, echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        self.prod2aldalog_records_pattern_map = \
            prod2aldalog_records_pattern_map

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
        return self.session.query(AldaLogEntry).all()

    def get_oldest_allowed_date(self, days):
        ''' delete all records with reference_time older
        than *days* before newest record '''
        max_date = self.session.query(
            func.max(AldaLogEntry.timestamp)).select_from(
                AldaLogEntry).scalar()

        if max_date is not None:
            if max_date > datetime.utcnow():
                print "max date in database is in future, using current date"
                max_date = datetime.utcnow()

            max_date = max_date - timedelta(days=days)

        return max_date

    def delete_older_than(self, days):
        ''' delete all records with reference_time older
        than *days* before newest record '''

        max_date = self.get_oldest_allowed_date(days)
        if max_date is not None:
            print "deleting all records before {}".format(max_date)

            self.session.query(AldaLogEntry).filter(
                AldaLogEntry.timestamp < max_date).delete()

    def record_count(self):
        ''' return count of accouncements in repository '''
        return self.session.query(
            func.count('*')).select_from(AldaLogEntry).scalar()

    def find_records_by_timeslot(self, timeslot, product_name=None):
        ''' find all records in repository for specified
        *timeslot* and (optional) *product_name*

        To determine if an record could be relevant for the
        *product_name*, the ctor parameter *prod2aldalog_records_pattern_map*
        is used.
        '''

        if product_name in (None, '*') \
                or not self.prod2aldalog_records_pattern_map:
            records = self.session.query(AldaLogEntry).filter(
                AldaLogEntry.slot_time == timeslot).all()
            return (records, True)

        records_patterns = \
            self._get_pat_for_prod(product_name)

        all_records = []
        res_ok = True
        for pat in records_patterns:
            pat_records = self.session.query(AldaLogEntry).filter(
                and_(AldaLogEntry.slot_time == timeslot,
                     and_(AldaLogEntry.dest_host.like(pat['dest_host']),
                          AldaLogEntry.filename.like(pat['filename'])))).all()
            res_ok &= len(pat_records) >= pat['min_count']
            all_records.extend(pat_records)
        return (all_records, res_ok)

    def _get_pat_for_prod(self, product_name):
        ''' returns affected entity patterns for product
        with name *product_name*
        '''
        if self.prod2aldalog_records_pattern_map:
            for key, value in self.prod2aldalog_records_pattern_map.items():
                if re.match(key, product_name):
                    return value
            return []
        return None
