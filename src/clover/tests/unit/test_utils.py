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

import json
import pytest  # pylint: disable=unused-import

from ...__utils__ import (
    CONVENTIONAL_SOURCES,
    AuxiliaryHeaterType,
    BColours,
    COLD_WATER,
    DesalinationScenario,
    HTFMode,
    HotWaterScenario,
    InputFileError,
    ResourceType,
    SolarPanelType,
    SUPPLY_TEMPERATURE,
    ThermalCollectorScenario,
)


class TestHTFMode(unittest.TestCase):
    """
    Tests the :class:`HTFMode` class.

    """

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

    def test_panel_types(self) -> None:
        """Tests that the expected panel types are present."""

        self.assertEqual(
            ["pv", "pv_t", "solar_thermal"], sorted({e.value for e in SolarPanelType})
        )


class TestThermalCollectorScenario(unittest.TestCase):
    """
    Tests the :class:`ThermalCollectorScenario` class.

    """

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

    def test_missing_clean_water_data(self) -> None:
        """Tests the case where input clean-water data is missing."""

        # Test missing clean-water scenario
        test_logger = mock.MagicMock()
        self.input_data.pop(ResourceType.CLEAN_WATER.value)
        test_logger = mock.MagicMock()
        with self.assertRaises(InputFileError):
            DesalinationScenario.from_dict(self.input_data, test_logger)
        test_logger.error.assert_called_once_with(
            "%sMissing clean-water information in deslination scenario file.%s",
            BColours.fail,
            BColours.endc,
        )

    def test_missing_feedwater_sources(self) -> None:
        """Tests the case where feedwater sources input data is missing."""

        # Test missing feedwater sources
        test_logger = mock.MagicMock()
        self.input_data[ResourceType.UNCLEAN_WATER.value].pop("sources")
        with self.assertRaises(InputFileError):
            DesalinationScenario.from_dict(self.input_data, test_logger)
        test_logger.error.assert_called_once_with(
            "%sFeedwater sources not specified in desalinaiton inputs file.%s",
            "\x1b[91m",
            "\x1b[0m",
        )

    def test_missing_feedwater_supply_temperature(self) -> None:
        """Tests the case where input feedwater supply data is missing."""

        # Test missing feedwater supply temperature
        test_logger = mock.MagicMock()
        self.input_data[ResourceType.UNCLEAN_WATER.value].pop(SUPPLY_TEMPERATURE)
        with self.assertRaises(InputFileError):
            DesalinationScenario.from_dict(self.input_data, test_logger)
        test_logger.error.assert_called_once_with(
            "%sMissing feedwater supply temperature information in desalination inputs."
            "%s",
            "\x1b[91m",
            "\x1b[0m",
        )

    def test_valid_inputs(self) -> None:
        """Tests the case where all the inputs are valid."""

        logger = logging.getLogger("src.clover.__utils__")

        with mock.patch.object(logger, "debug") as mock_logger:
            DesalinationScenario.from_dict(self.input_data, mock_logger)
            mock_logger.assert_not_called()


class TestHotWaterScenario(unittest.TestCase):
    """
    Tests the :class:`HotWaterScenario` class.

    The hot-water scenario class has a `from_dict` method which takes in input data and
    transforms it into an instance of the class. These test cases test the flow through
    this instantiation process.

    """

    def setUp(self) -> None:
        """Sets up functionality in common across the tests."""

        super().setUp()
        self.input_data: Dict[str, Any] = {
            "name": "default",
            "hot_water": {
                "auxiliary_heater": "none",
                "conventional_sources": ["natural_gas"],
                "demand_temperature": 60,
            },
            "cold_water": {"supply": "unlimited", "supply_temperature": 10},
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

    def test_invalid_auxiliary_heater(self) -> None:
        """Tests the case where auxiliary heater data is invalid."""

        # Test missing clean-water scenario
        test_logger = mock.MagicMock()
        self.input_data[ResourceType.HOT_CLEAN_WATER.value][
            "auxiliary_heater"
        ] = "INVALID"
        test_logger = mock.MagicMock()
        with self.assertRaises(InputFileError):
            HotWaterScenario.from_dict(self.input_data, test_logger)
        test_logger.error.assert_called_once_with(
            "%sInvalid auxiliary heater mode specified: %s. Valid options are %s.%s",
            BColours.fail,
            self.input_data[ResourceType.HOT_CLEAN_WATER.value]["auxiliary_heater"],
            ", ".join(f"'{e.value}'" for e in AuxiliaryHeaterType),
            BColours.endc,
        )

    def test_invalid_cold_water_supply(self) -> None:
        """Tests the case where cold-water-supply data is invalid."""

        # Test missing clean-water scenario
        test_logger = mock.MagicMock()
        self.input_data[COLD_WATER]["supply"] = "INVALID"
        test_logger = mock.MagicMock()
        with self.assertRaises(InputFileError):
            HotWaterScenario.from_dict(self.input_data, test_logger)
        test_logger.error.assert_called_once_with(
            "%sInvalid cold-water supply specified: %s%s",
            BColours.fail,
            self.input_data[COLD_WATER]["supply"],
            BColours.endc,
        )

    def test_missing_cold_water_supply_temperature(self) -> None:
        """Tests the case where the cold-water-supply temperature is missing."""

        # Test missing clean-water scenario
        test_logger = mock.MagicMock()
        self.input_data[COLD_WATER].pop(SUPPLY_TEMPERATURE)
        test_logger = mock.MagicMock()
        with self.assertRaises(InputFileError):
            HotWaterScenario.from_dict(self.input_data, test_logger)
        test_logger.error.assert_called_once_with(
            "%sMissing cold-water supply temperature information in hot-water "
            "inputs.%s",
            BColours.fail,
            BColours.endc,
        )

    def test_missing_conventional_sources(self) -> None:
        """Tests the case where the cold-water-supply temperature is missing."""

        # Test missing clean-water scenario
        test_logger = mock.MagicMock()
        self.input_data[ResourceType.HOT_CLEAN_WATER.value].pop(CONVENTIONAL_SOURCES)
        HotWaterScenario.from_dict(self.input_data, test_logger)
        test_logger.info.assert_has_calls(
            [
                mock.call(
                    "Missing hot-water conventional sources in hot-water inputs."
                ),
                mock.call("Continuing with no conventional hot-water sources."),
            ]
        )
        test_logger.debug.assert_called_with(
            "Hot-water input information: %s", json.dumps(self.input_data)
        )

    def test_missing_demand_temperature(self) -> None:
        """Tests the case where the cold-water-supply temperature is missing."""

        # Test missing clean-water scenario
        test_logger = mock.MagicMock()
        self.input_data[ResourceType.HOT_CLEAN_WATER.value].pop("demand_temperature")
        test_logger = mock.MagicMock()
        with self.assertRaises(InputFileError):
            HotWaterScenario.from_dict(self.input_data, test_logger)
        test_logger.error.assert_called_with(
            "%sMissing hot-water demand temperature in hot-water scenario file.%s",
            BColours.fail,
            BColours.endc,
        )

    def test_valid_inputs(self) -> None:
        """Tests the case where all the inputs are valid."""

        logger = logging.getLogger("src.clover.__utils__")

        with mock.patch.object(logger, "debug") as mock_logger:
            HotWaterScenario.from_dict(self.input_data, mock_logger)
            mock_logger.assert_not_called()
