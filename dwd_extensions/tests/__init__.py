#!/usr/bin/env python
'''
Created on 12.05.2016

@author: Christian Kliche
'''
import unittest
import doctest
from dwd_extensions.tests import (test_dataset_processors)


def suite():
    """The global test suite.
    """
    mysuite = unittest.TestSuite()
    mysuite.addTests(test_dataset_processors.suite())

    return mysuite
