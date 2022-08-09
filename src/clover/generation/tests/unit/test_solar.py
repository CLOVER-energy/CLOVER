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

from tkinter import N
import unittest

from unittest import mock
from clover.__utils__ import ProgrammerJudgementFault, RegressorType  # pylint: disable=unused-import

import pytest

from ...solar import HybridPVTPanel, PVPanel, PerformanceCurve


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


class TestPVPanel(unittest.TestCase):
    """Tests the :class:`PVPanel` instance."""

    def setUp(self) -> None:
        """Sets up functionality in common across test cases."""
        self.input_data = {
            "name": "default_pv",
            "azimuthal_orientation": 180,
            "lifetime": 20,
            "reference_efficiency": 0.125,
            "reference_temperature": 25,
            "thermal_coefficient": 0.0053,
            "tilt": 29,
            "type": "pv",
            "costs": {
                "cost": 500,
                "cost_decrease": 5,
                "installation_cost": 100,
                "installation_cost_decrease": 0,
                "o&m": 5
            },
            "emissions":{
            "ghgs": 3000,
            "ghg_decrease": 5,
            "installation_ghgs": 50,
            "installation_ghg_decrease": 0,
            "o&m": 5}
        }
        super().setUp()

    @pytest.mark.unit
    def test_instantiate_no_override(self) -> None:
        """Tests instantiation with the default PV unit."""

        PVPanel.from_dict(mock.MagicMock(), self.input_data)

    @pytest.mark.unit
    def test_instantiate_override_unit(self) -> None:
        """
        Tests instantiation with an overriden PV unit."""

        overriden_unit: float = 0.5
        self.input_data["pv_unit"] = overriden_unit
        pv_panel = PVPanel.from_dict(mock.MagicMock(), self.input_data)

        self.assertEqual(overriden_unit, pv_panel.pv_unit)
        self.assertTrue(pv_panel.pv_unit_overrided)

    @pytest.mark.unit
    def test_calculate_performance(self) -> None:
        """Tests the calculate performance method."""

        pv_panel = PVPanel.from_dict(mock.MagicMock(), self.input_data)
        with self.assertRaises(ProgrammerJudgementFault):
            pv_panel.calculate_performance(0, 0, 0, 0, 0, 0, 0)


class TestHybridPVTPanelPerformance(unittest.TestCase):
    """Tests the `calculate_performance` function of the hybrid PV-T panel."""


    def setUp(self) -> None:
        """Sets up functionality in common across test cases."""
        self.input_data = {
            "name": "default_pvt",
            "azimuthal_orientation": 180,
            "lifetime": 20,
            "max_mass_flow_rate": 7.37,
            "min_mass_flow_rate": 7.37,
            "pv": "default_pv",
            "pv_unit": 0.2,
            "reference_efficiency": 0.125,
            "reference_temperature": 25,
            "thermal_coefficient": 0.0053,
            "tilt": 29,
            "type": "pv_t",
            "costs": {
                "cost": 500,
                "cost_decrease": 5,
                "installation_cost": 100,
                "installation_cost_decrease": 0,
                "o&m": 5
            },
            "emissions":{
            "ghgs": 3000,
            "ghg_decrease": 5,
            "installation_ghgs": 50,
            "installation_ghg_decrease": 0,
            "o&m": 5}
        }
        super().setUp()

    