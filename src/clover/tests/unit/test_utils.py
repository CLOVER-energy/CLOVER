#!/usr/bin/python3
########################################################################################
# test_utils.py - Tests for CLOVER's utility module.                                   #
#                                                                                      #
# Author: Ben Winchester, Phil Sandwell                                                #
# Copyright: Ben Winchester, 2022                                                      #
# Date created: 08/03/2022                                                             #
# License: Open source                                                                 #
########################################################################################
"""
test_utils.py - Module-level tests for CLOVER's utility module.

"""

import logging
import unittest

from typing import Any, Dict
from unittest import mock  # pylint: disable=unused-import

import pytest  # pylint: disable=import-error

from ...__utils__ import (
    SUPPLY_TEMPERATURE,
    DesalinationScenario,
    HTFMode,
    InputFileError,
    ResourceType,
    SolarPanelType,
    ThermalCollectorScenario,
)


class TestHTFMode(unittest.TestCase):
    """
    Tests the :class:`HTFMode` class.

    """

    @pytest.mark.unit
    def test_instantiate(self) -> None:
        """Tests that a :class:`HTFMode` can be instantiated as expected."""

        test_mode: str = "htf"

        try:
            htf_mode = HTFMode(test_mode)
        except Exception:
            print("Failed to instantiate HTFMode.")
            raise

        self.assertEqual(test_mode, htf_mode.value)


class TestSolarPanelType(unittest.TestCase):
    """Tests the :class:`SolarPanelType` class."""

    @pytest.mark.unit
    def test_panel_types(self) -> None:
        """Tests that the expected panel types are present."""

        self.assertEqual(
            ["pv", "pv_t", "solar_thermal"], sorted({e.value for e in SolarPanelType})
        )


class TestThermalCollectorScenario(unittest.TestCase):
    """
    Tests the :class:`ThermalCollectorScenario` class.

    """

    @pytest.mark.unit
    def test_instantiate(self) -> None:
        """
        Tests that a :class:`ThermalCollectorScenario` can be instantiated as expected.

        """

        test_panel_type: SolarPanelType = SolarPanelType.PV_T
        test_htf_mode: HTFMode = HTFMode.CLOSED_HTF
        test_htf_heat_capacity: float = 10
        test_mass_flow_rate: float = 20

        try:
            thermal_collector_scenario = ThermalCollectorScenario(
                test_panel_type,
                test_htf_mode,
                test_htf_heat_capacity,
                test_mass_flow_rate,
            )
        except Exception:
            print("Failed to instantiate ThermalCollectorScenario.")
            raise

        self.assertEqual(test_panel_type, thermal_collector_scenario.collector_type)
        self.assertEqual(test_htf_mode, thermal_collector_scenario.heats)
        self.assertEqual(
            test_htf_heat_capacity, thermal_collector_scenario.htf_heat_capacity
        )
        self.assertEqual(test_mass_flow_rate, thermal_collector_scenario.mass_flow_rate)


class TestDesalinationScenario(unittest.TestCase):
    """
    Tests the :class:`DesalinationScenario` class.

    The desalination scenario class has a `from_dict` method which takes in input data
    and transforms it into an instance of the class. These test cases test the flow
    through this instantiation process.

    """

    def setUp(self) -> None:
        """Sets up functionality in common across the tests."""

        super().setUp()
        self.input_data: Dict[str, Any] = {
            "name": "default",
            "clean_water": {
                "mode": "backup",
                "conventional_sources": ["river"],
                "sources": ["reverse_osmosis"],
            },
            "feedwater": {
                "sources": ["bore_hole", "bore_hole", "bore_hole"],
                "supply_temperature": 10,
            },
            "solar_thermal_collector_scenarios": [
                {
                    "type": "solar_thermal",
                    "heats": "htf",
                    "mass_flow_rate": 72,
                },
                {
                    "type": "pv_t",
                    "heats": "cold_water",
                    "mass_flow_rate": 72,
                },
            ],
        }

    @pytest.mark.unit
    def test_valid_inputs(self) -> None:
        """Tests the case where all the inputs are valid."""

        logger = logging.getLogger("src.clover.__utils__")

        with mock.patch.object(logger, "debug") as mock_logger:
            DesalinationScenario.from_dict(self.input_data, mock_logger)
            mock_logger.assert_not_called()

    @pytest.mark.unit
    def test_missing_data(self) -> None:
        """Tests the cases where input data is missing."""

        # Test missing clean-water scenario
        test_logger = mock.MagicMock()
        missing_info_data = self.input_data.copy()
        missing_info_data.pop(ResourceType.CLEAN_WATER.value)
        with self.assertRaises(InputFileError), mock.MagicMock() as test_logger:
            DesalinationScenario.from_dict(missing_info_data, test_logger)
        test_logger.error.assert_called_once_with(
            "%sMissing clean-water information in deslination scenario file.%s",
            "\x1b[91m",
            "\x1b[0m",
        )

        # Test missing feedwater supply temperature
        test_logger = mock.MagicMock()
        missing_info_data = self.input_data.copy()
        missing_info_data[ResourceType.UNCLEAN_WATER.value].pop(SUPPLY_TEMPERATURE)
        with self.assertRaises(InputFileError):
            DesalinationScenario.from_dict(missing_info_data, test_logger)
        test_logger.error.assert_called_once_with(
            "%sMissing feedwater supply temperature information in desalination inputs."
            "%s",
            "\x1b[91m",
            "\x1b[0m",
        )

        # Test missing feedwater sources
        test_logger = mock.MagicMock()
        missing_info_data = self.input_data.copy()
        missing_info_data[ResourceType.UNCLEAN_WATER.value].pop("sources")
        with self.assertRaises(InputFileError):
            DesalinationScenario.from_dict(missing_info_data, test_logger)
        test_logger.error.assert_called_once_with(
            "%sFeedwater sources not specified in desalinaiton inputs.%s",
            "\x1b[91m",
            "\x1b[0m",
        )

    @pytest.mark.unit
    def test_invalid_clean_water_mode(self) -> None:
        """Tests the cases where input data is missing."""

    @pytest.mark.unit
    def test_invalid_thermal_collector_scenarios(self) -> None:
        """Tests the cases where input data is missing."""
