#!/usr/bin/python3
########################################################################################
# test_solar.py - Tests for CLOVER's solar generation module.                          #
#                                                                                      #
# Author: Ben Winchester, Phil Sandwell                                                #
# Copyright: Ben Winchester, 2022                                                      #
# Date created: 08/03/2022                                                             #
# License: Open source                                                                 #
########################################################################################
"""
test_solar.py - Tests for the solar generation module of CLOVER.

"""

import unittest

from unittest import mock  # pylint: disable=unused-import

import pytest

from ...solar import PerformanceCurve


class TestPerformanceCurve(unittest.TestCase):
    """
    Tests the :class:`PerformanceCurve` class.

    The :class:`PerformanceCurve` instances expose three property methods which are
    tested here.

    """

    @pytest.mark.unit
    def test_properties(self) -> None:
        """Tests that a :class:`PerformanceCurve` can be instantiated as expected."""

        zeroth: float = 0.0
        first: float = 1.0
        second: float = 2.0

        performance_curve = PerformanceCurve(zeroth, first, second)

        self.assertEqual(zeroth, performance_curve.eta_0)
        self.assertEqual(first, performance_curve.c_1)
        self.assertEqual(second, performance_curve.c_2)
