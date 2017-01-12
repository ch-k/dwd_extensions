#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Author(s):

#   Christian Kliche <chk@ebp.de>

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

"""Unit testing for dataset processors
"""

import unittest
import tempfile
import os
import shutil
from StringIO import StringIO
from mock import patch
from datetime import datetime

from dwd_extensions.qm.sat_incidents.repository import Repository
from dwd_extensions.qm.sat_incidents.repository import AnnouncementImpactEnum
from dwd_extensions.qm.sat_incidents.reader \
    import EumetsatUserNotifcationReader
from dwd_extensions.qm.sat_incidents.service import SatDataAvailabilityService

xml_annons = """<?xml version="1.0" encoding="UTF-8"?>
<announcements>
    <announcement ann-creation="2016-10-05T15:42:27"
    ann-subject="ground-segment-anomaly"
    ann-revision="1" impact="data-degraded"
    ann-type="Service Alert"
    status="recovered"
    start-time="2016-10-05T15:36:00"
    ann-number="2265"
    end-time="2016-10-05T15:37:00">
        <satellites>
            <satellite>MET-7</satellite>
        </satellites>
        <services>
            <operational-service-group name="Meteosat Services">
                <operational-service name="57° E IODC">
            <product-group name="IODC Meteosat Meteorological Products" />
            <product-group name="IODC HRI Data" />
                </operational-service>
            </operational-service-group>
        </services>
        <detail>Slot 32 was disseminated with errors,</detail>
    </announcement>
    <announcement ann-creation="2016-10-05T10:56:18"
    ann-subject="ground-segment-maintenance"
    ann-revision="1"
    impact="risk-of-interruption"
    ann-type="Planned Maintenance"
    status="scheduled"
    start-time="2016-10-06T07:30:00"
    ann-number="2264"
    end-time="2016-10-06T11:00:00">
        <services>
            <operational-service-group name="Data Access Services">
                <operational-service name="Web Service">
                    <product-group name="Web Service" />
                </operational-service>
            </operational-service-group>
        </services>
        <detail>Maintenance on the EUMETView Pilot service. Disruption to
         this service can be expected during the indicated time period.
         </detail>
    </announcement>
    <announcement ann-creation="2016-10-04T19:32:35"
    ann-subject="EARS-ground-segment-anomaly"
    ann-revision="1"
    impact="data-unavailable"
    ann-type="Service Alert"
    status="recovered"
    start-time="2016-10-04T15:31:00"
    ann-number="2263"
    end-time="2016-10-04T18:53:00">
        <services>
            <operational-service-group name=" Regional Data Services">
                <operational-service name="RDS-EARS">
                    <product-group name="EARS-ATOVS" />
                </operational-service>
            </operational-service-group>
        </services>
        <detail>Data from Gilmore Creek station(s) affected.</detail>
    </announcement>
    <announcement ann-creation="2016-09-21T11:01:55"
    ann-subject="Sun-colinearity"
    ann-revision="1"
    impact="data-unavailable"
    ann-type="Planned Maintenance"
    status="scheduled"
    start-time="2016-10-02T11:00:00"
    ann-number="2230"
    end-time="2016-10-12T11:15:00">
        <satellites>
            <satellite>MET-9</satellite>
        </satellites>
        <services>
            <operational-service-group name="Meteosat Services">
                <operational-service name="9.5° E RSS">
            <product-group name="RSS SEVIRI Level 1.5 Image Data" />
            <product-group name="RSS Meteosat Meteorological Products" />
                </operational-service>
            </operational-service-group>
        </services>
        <detail>Sun Co-linearity. Repeat cycles 11:00 to 11:15
        may be affected</detail>
    </announcement>
</announcements>
"""


class TestEumetsatUNS(unittest.TestCase):
    """Unit testing for dataset processors
    """

    def setUp(self):
        """Setting up the testing
        """
        self.dirname = os.path.dirname(__file__)
        self.tempdir = tempfile.mkdtemp()
        self.db_filename = os.path.join(self.tempdir,
                                        'sat_incidents.db')

    def test_import(self):
        """Test import of xml file into repository"""
        self.xml_filename = os.path.join(self.dirname, 'data',
                                         'eumetsat_unc_results.xml')
        reader = EumetsatUserNotifcationReader(self.xml_filename)
        repo = Repository(self.db_filename)
        repo.add(reader.get_items())

        self.assertEqual(repo.announcement_count(), 2202)
        self.assertEqual(repo.affected_entity_count(), 210)

    def test_query_timeslot(self):
        """Test repository query for one timeslot in short version
        xml file """
        reader = EumetsatUserNotifcationReader(StringIO(xml_annons))

        repo = Repository(self.db_filename)

        repo.add(reader.get_items())

        anns = repo.find_announcments_by_timeslot(
            datetime(2016, 10, 4, 15, 30),
            'FernsehbildRGBA_nqeuro3km_xx_contrast_optim.tif.rrd')

        self.assertEqual(len(anns), 1)
        self.assertEqual(anns[0].number, 2230)

    def test_query_timeslot_no_match(self):
        """Test repository query for one timeslot without match
        in short version xml file """
        reader = EumetsatUserNotifcationReader(StringIO(xml_annons))

        repo = Repository(self.db_filename)
        repo.add(reader.get_items())

        anns = repo.find_announcments_by_timeslot(
            datetime(2016, 10, 4, 16, 31),
            'FernsehbildRGBA_nqeuro3km_xx_contrast_optim.tif.rrd')

        self.assertEqual(len(anns), 2)

    def test_query_timeslot_with_prod_pattern(self):
        """Test repository query for one timeslot with product pattern
        in short version xml file """
        reader = EumetsatUserNotifcationReader(StringIO(xml_annons))

        import yaml
        with open(os.path.join(self.dirname, 'data',
                               'sat_incidents_cfg.yml'), "r") as fid:
            config = yaml.safe_load(fid)

        repo = Repository(
            self.db_filename,
            prod2affected_entity_pattern_map=config[
                'product2affected_entity_map'])

        repo.add(reader.get_items())

        anns = repo.find_announcments_by_timeslot(
            datetime(2016, 10, 4, 16, 31),
            'FernsehbildRGBA_nqeuro3km_xx_contrast_optim.tif.rrd')

        self.assertEqual(len(anns), 1)
        self.assertEqual(anns[0].number, 2230)

    def test_service_query_with_prod_pattern_file_cfg(self):
        """Test service query for one timeslot with product pattern
        in short version xml file """

        import yaml
        with open(os.path.join(self.dirname, 'data',
                               'sat_incidents_cfg.yml'), "r") as fid:
            config = yaml.safe_load(fid)
        config['sat_incidents_db_filename'] = self.db_filename
        service = SatDataAvailabilityService(config=config)
        service.import_file(StringIO(xml_annons))
        res = service.get_data_availability_error(
            datetime(2016, 10, 4, 16, 31),
            'FernsehbildRGBA_nqeuro3km_xx_contrast_optim.tif.rrd')
        self.assertEqual(res, AnnouncementImpactEnum.DATA_UNAVAILABLE)

    def test_service_query_with_prod_pattern(self):
        """Test service query for one timeslot with product pattern
        in short version xml file """

        config = {}
        config['sat_incidents_db_filename'] = self.db_filename
        config['product2affected_entity_map'] = {
            '.*Fernsehbild.*': ['HIMA.*', 'MET.*'],
            '.*Test2.*': ['Dep1.*', 'Dep2.*']
        }
        service = SatDataAvailabilityService(config=config)
        service.import_file(StringIO(xml_annons))
        res = service.get_data_availability_error(
            datetime(2016, 10, 4, 16, 31),
            'FernsehbildRGBA_nqeuro3km_xx_contrast_optim.tif.rrd')
        self.assertEqual(res, AnnouncementImpactEnum.DATA_UNAVAILABLE)

    def test_service_query_with_prod_pattern_no_sat_match(self):
        """Test service query for one timeslot with product pattern
        but no matching affected entity
        in short version xml file """

        config = {}
        config['sat_incidents_db_filename'] = self.db_filename
        config['product2affected_entity_map'] = {
            '.*Fernsehbild.*': ['HIMA.*'],
            '.*Test2.*': ['Dep1.*', 'Dep2.*']
        }
        service = SatDataAvailabilityService(config=config)
        service.import_file(StringIO(xml_annons))
        res = service.get_data_availability_error(
            datetime(2016, 10, 4, 16, 31),
            'FernsehbildRGBA_nqeuro3km_xx_contrast_optim.tif.rrd')
        self.assertEqual(res, None)

    def tearDown(self):
        """Closing down
        """
        shutil.rmtree(self.tempdir)


def suite():
    """The suite for test_trollduction
    """
    loader = unittest.TestLoader()
    mysuite = unittest.TestSuite()
    mysuite.addTest(loader.loadTestsFromTestCase(TestEumetsatUNS))

    return mysuite

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite())
