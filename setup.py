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
                'dwd_extensions.sat_incidents'],
      scripts=['bin/configure.py',
               'bin/postprocessor.py',
               'bin/supervisor_event_launcher.py',
               'bin/check_products_rrd.py',
               'bin/import_unc_xml_file.py',
               'bin/create_graphs.py'],
      zip_safe=False,
      install_requires=['SQLAlchemy',
                        'enum34',
                        'pyyaml', ],
      license="",
      classifiers=[],
      test_suite='',
      )
