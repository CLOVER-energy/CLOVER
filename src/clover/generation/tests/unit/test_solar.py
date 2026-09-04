#!/usr/bin/python3.10
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

from unittest import mock
from clover.__utils__ import (
    HEAT_CAPACITY_OF_WATER,
    BColours,
    ProgrammerJudgementFault,
    RegressorType,
    SolarPanelType,
)

from ...solar import (
    LOW_IRRADIANCE_THRESHOLD,
    LOW_TEMPERATURE_THRESHOLD,
    REFERENCE_SOLAR_IRRADIANCE,
    HybridPVTPanel,
    PVPanel,
    PerformanceCurve,
    SolarThermalPanel,
)


class TestPerformanceCurve(unittest.TestCase):
    """
    Tests the :class:`PerformanceCurve` class.

    The :class:`PerformanceCurve` instances expose three property methods which are
    tested here.

    """

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
                "o&m": 5,
            },
            "emissions": {
                "ghgs": 3000,
                "ghg_decrease": 5,
                "installation_ghgs": 50,
                "installation_ghg_decrease": 0,
                "o&m": 5,
            },
        }
        super().setUp()

    def test_instantiate_no_override(self) -> None:
        """Tests instantiation with the default PV unit."""

        PVPanel.from_dict(mock.MagicMock(), self.input_data)

    def test_instantiate_override_unit(self) -> None:
        """
        Tests instantiation with an overriden PV unit."""

        overriden_unit: float = 0.5
        self.input_data["pv_unit"] = overriden_unit
        pv_panel = PVPanel.from_dict(mock.MagicMock(), self.input_data)

        self.assertEqual(overriden_unit, pv_panel.pv_unit)
        self.assertTrue(pv_panel.pv_unit_overrided)

    def test_calculate_performance(self) -> None:
        """Tests the calculate performance method."""

        pv_panel = PVPanel.from_dict(mock.MagicMock(), self.input_data)
        with self.assertRaises(ProgrammerJudgementFault):
            pv_panel.calculate_performance(
                ambient_temperature=0,
                htf_heat_capacity=0,
                input_temperature=0,
                logger=mock.MagicMock(),
                mass_flow_rate=0,
                solar_irradiance=0,
                wind_speed=0,
            )


class TestHybridPVTPanelPerformance(unittest.TestCase):
    """Tests the `calculate_performance` function of the hybrid PV-T panel."""

    def setUp(self) -> None:
        """Sets up functionality in common across test cases."""

        self.input_data = {
            "name": "default_pvt",
            "area": 1.876,
            "azimuthal_orientation": 231,
            "costs": {"cost": 1022.0},
            "emissions": {"ghgs": 362.74},
            "land_use": 1.876,
            "lifetime": 20,
            "max_mass_flow_rate": None,
            "min_mass_flow_rate": 0.0,
            "nominal_mass_flow_rate": 60.0,
            "pv_module_characteristics": {
                "nominal_power": 0.4,
                "reference_efficiency": 0.213,
                "reference_temperature": 25.0,
                "thermal_coefficient": 0.0034,
            },
            "stagnation_temperature": 90.0,
            "thermal_performance_curve": {
                "zeroth_order": 0.621,
                "first_order": -7.4,
                "second_order": 0.0,
            },
            "tilt": 15,
            "type": "pv_t",
        }

        # Set up required mocks for instantiation.
        self.ambient_temperature = 313
        self.input_temperature = 303
        self.irradiance = 1000
        self.mass_flow_rate = 15
        self.test_logger = mock.Mock()
        self.wind_speed = 10

        # Create the PVT Panel instance.
        self.pvt_collector = HybridPVTPanel.from_dict(
            (test_logger := mock.Mock()), self.input_data
        )

        super().setUp()

    def test_mainline(self) -> None:
        """
        Tests the mainline case.

        The output temperature of the PV-T collector is calculated and then used to
        compute the efficiency of the collector two ways:

            eta = eta_0
                + c_1 * (T_c - T_amb) / G
                + c_2 * (T_c - T_amb) ** 2 / G ,                        (1)

            eta = m_htf * c_htf * (T_out - T_in) / (A * G) .            (2)

        Tests that the electrical efficiency is calculated also based on the average
        temperature of the collector.

        """

        (
            electrical_efficiency,
            output_temperature,
            reduced_temperature,
            thermal_efficiency,
        ) = self.pvt_collector.calculate_performance(
            ambient_temperature=self.ambient_temperature,
            htf_heat_capacity=HEAT_CAPACITY_OF_WATER,
            input_temperature=self.input_temperature,
            logger=self.test_logger,
            mass_flow_rate=self.mass_flow_rate,
            solar_irradiance=self.irradiance,
            wind_speed=self.wind_speed,
        )

        # Type-check the outputs
        self.assertIsInstance(output_temperature, float)

        # Compute the efficiency two ways and check that these are equal.
        collector_temperature = 0.5 * (self.input_temperature + output_temperature)  # type: ignore [operator]
        efficiency_by_equation = (
            self.pvt_collector.thermal_performance_curve.eta_0
            + self.pvt_collector.thermal_performance_curve.c_1
            * (collector_temperature - self.ambient_temperature)
            / self.irradiance
            + self.pvt_collector.thermal_performance_curve.c_2
            * (collector_temperature - self.ambient_temperature) ** 2
            / self.irradiance
        )
        efficiency_by_output: float = (
            (self.mass_flow_rate)
            * HEAT_CAPACITY_OF_WATER
            * (output_temperature - self.input_temperature)  # type: ignore [operator]
        ) / (self.pvt_collector.area * self.irradiance)

        self.assertEqual(round(thermal_efficiency, 8), round(efficiency_by_equation, 8))
        self.assertEqual(
            round(efficiency_by_equation, 8), round(efficiency_by_output, 8)
        )


class TestSolarThermalPanelPerformance(unittest.TestCase):
    """Tests the `calculate_performance` function of the solar-thermal collector."""

    def setUp(self) -> None:
        """Sets up functionality in common across test cases."""

        self.input_data = {
            "name": "default_solar_thermal",
            "area": 2.106,
            "azimuthal_orientation": 180,
            "land_use": 2.52,
            "lifetime": 20,
            "max_mass_flow_rate": 250,
            "min_mass_flow_rate": 60,
            "nominal_mass_flow_rate": 125,
            "stagnation_temperature": 183.4,
            "tilt": 29,
            "type": "solar_thermal",
            "costs": {
                "cost": 500,
                "cost_decrease": 5,
                "installation_cost": 100,
                "installation_cost_decrease": 0,
                "o&m": 5,
            },
            "emissions": {
                "ghgs": 3000,
                "ghg_decrease": 5,
                "installation_ghgs": 50,
                "installation_ghg_decrease": 0,
                "o&m": 5,
            },
            "thermal_performance_curve": {
                "zeroth_order": 0.694,
                "first_order": 3.53,
                "second_order": 0.0047,
            },
        }

        # Set up required mocks for instantiation.
        self.ambient_temperature = 313
        self.input_temperature = 303
        self.irradiance = 1000
        self.mass_flow_rate = 15
        self.test_logger = mock.Mock()
        self.wind_speed = 10

        # Create the solar-thermal
        self.solar_thermal_panel: SolarThermalPanel = SolarThermalPanel.from_dict(
            self.test_logger, self.input_data
        )

        super().setUp()

    def test_mainline(self) -> None:
        """
        Tests the mainline case.

        The output temperature of the solar-thermal collector is calculated and then
        used to compute the efficiency of the collector two ways:

            eta = eta_0
                + c_1 * (T_c - T_amb) / G
                + c_2 * (T_c - T_amb) ** 2 / G ,                        (1)

            eta = m_htf * c_htf * (T_out - T_in) / (A * G) .            (2)

        """

        _, output_temperature, reduced_temperature, thermal_efficiency = (
            self.solar_thermal_panel.calculate_performance(
                ambient_temperature=self.ambient_temperature,
                htf_heat_capacity=HEAT_CAPACITY_OF_WATER,
                input_temperature=self.input_temperature,
                logger=self.test_logger,
                mass_flow_rate=self.solar_thermal_panel.nominal_mass_flow_rate,
                solar_irradiance=self.irradiance,
                wind_speed=self.wind_speed,
            )
        )

        # Type-check the outputs
        self.assertIsInstance(output_temperature, float)

        # Compute the efficiency two ways and check that these are equal.
        collector_temperature = 0.5 * (self.input_temperature + output_temperature)  # type: ignore [operator]
        efficiency_by_equation = (
            self.solar_thermal_panel.thermal_performance_curve.eta_0
            + self.solar_thermal_panel.thermal_performance_curve.c_1
            * (collector_temperature - self.ambient_temperature)
            / self.irradiance
            + self.solar_thermal_panel.thermal_performance_curve.c_2
            * (collector_temperature - self.ambient_temperature) ** 2
            / self.irradiance
        )
        if self.solar_thermal_panel.nominal_mass_flow_rate is None:
            raise ProgrammerJudgementFault(
                "test_solar::TestSolarThermalPanelPerformance.test_mainline",
                "Solar-thermal panel instantiated incorrectly.",
            )
        efficiency_by_output: float = (
            (self.solar_thermal_panel.nominal_mass_flow_rate)
            * HEAT_CAPACITY_OF_WATER
            * (output_temperature - self.input_temperature)  # type: ignore [operator]
        ) / (self.solar_thermal_panel.area * self.irradiance)

        if not isinstance(thermal_efficiency, float):
            raise ProgrammerJudgementFault(
                "test_solar::TestSolarThermalPanelPerformance.test_mainline",
                "No thermal performance returned from thermal collector.",
            )
        self.assertEqual(round(thermal_efficiency, 8), round(efficiency_by_equation, 8))
        self.assertEqual(
            round(efficiency_by_equation, 8), round(efficiency_by_output, 8)
        )
