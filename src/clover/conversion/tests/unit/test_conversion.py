#!/usr/bin/python3
########################################################################################
# test_conversion.py - Tests for CLOVER's conversion module.                           #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 05/07/2021                                                             #
# License: Open source                                                                 #
########################################################################################
"""
test_conversion.py - Tests for the conversion module of CLOVER.

"""

import unittest

from unittest import mock  # pylint: disable=unused-import

from ...conversion import (  # pylint: disable=unused-import
    _parse_waste_production,
    Converter,
    MultiInputConverter,
    ThermalDesalinationPlant,
    WasteProduct,
)


class TestConverter(unittest.TestCase):
    """Tests the convertor class."""


class TestMultiInputConvertor(unittest.TestCase):
    """Tests the convertor class."""


class TestParseWasteProduction(unittest.TestCase):
    """Tests the waste-production parsing method."""


class TestThermalDesalinationPlant(unittest.TestCase):
    """Tests the convertor class."""


class TestWasteProduct(unittest.TestCase):
    """Tests the convertor class."""


if __name__ == "__main__":
    unittest.main()
