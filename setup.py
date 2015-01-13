#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup
import sys
import imp

version = imp.load_source('dwd_extensions.version', 'dwd_extensions/version.py')


setup(name="dwd_extensions",
      version=version.__version__,
      description='DWD specific pytroll extensions',
      author='The EBP team',
      author_email='',
      url="",
      packages=['dwd_extensions'],
      scripts=['bin/dwd_extensions.py'],
      zip_safe=False,
      license="",
      classifiers=[],
      test_suite='',
      )
