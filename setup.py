#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup
import imp

version = imp.load_source('dwd_extensions.version',
                          'dwd_extensions/version.py')


setup(name="dwd_extensions",
      version=version.__version__,
      description='DWD specific PyTroll extensions',
      author='The EBP team',
      author_email='',
      url="",
      packages=['dwd_extensions',
                'dwd_extensions.layout',
                'dwd_extensions.mpop',
                'dwd_extensions.tools',
                'dwd_extensions.trollduction',
                'dwd_extensions.qm',
                'dwd_extensions.qm.sat_incidents',
                'dwd_extensions.qm.afd_alda_logs',
                'dwd_extensions.qm.emc_dailylogs'
                ],
      scripts=['bin/configure.py',
               'bin/postprocessor.py',
               'bin/supervisor_event_launcher.py',
               'bin/check_products_rrd.py',
               'bin/import_uns_xml_file.py',
               'bin/import_afd_alda_logs.py',
               'bin/import_daily_logs.py',
               'bin/calc_qm_stats_for_product.py',
               'bin/calc_qm_stats.py',
               'bin/create_graphs.py'],
      zip_safe=False,
      install_requires=['SQLAlchemy',
                        'enum34',
                        'pyyaml', ],
      license="",
      classifiers=[],
      test_suite='',
      )
