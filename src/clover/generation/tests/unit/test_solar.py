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

        # Set up required mocks for instantiation.
        self.ambient_temperature = 40
        self.electric_models = {
            regressor_type: mock.Mock() for regressor_type in RegressorType
        }
        self.mass_flow_rate = 15
        self.test_logger = mock.Mock()
        self.thermal_models = {
            regressor_type: mock.Mock() for regressor_type in RegressorType
        }

        solar_panel = mock.Mock()
        solar_panel.name = self.input_data["pv"]
        solar_panel.reference_efficiency = 0.125
        solar_panel.panel_type = SolarPanelType.PV
        self.solar_panels = [solar_panel]

        self.wind_speed = 10

        # Create the PVT Panel instance.
        self.pvt_panel = HybridPVTPanel(
            self.electric_models,
            self.test_logger,
            self.input_data,
            self.solar_panels,  # type: ignore [arg-type]
            self.thermal_models,
        )

        super().setUp()

    def test_electrical_model_error(self) -> None:
        """Tests the case where there is an error in the electric calculation."""

        # Set up input parameters.
        input_temperature = LOW_TEMPERATURE_THRESHOLD - 0.1
        irradiance = LOW_IRRADIANCE_THRESHOLD - 0.1
        test_exception = Exception("TEST EXCEPTION")

        # Set up electrical and thermal model return values.
        self.pvt_panel.electric_models[  # type: ignore [index]
            RegressorType.LOW_IRRADIANCE_LOW_TEMPERATURE
        ].predict.side_effect = test_exception

        # Call the calculation method.
        with self.assertRaises(Exception) as e:
            self.pvt_panel.calculate_performance(
                self.ambient_temperature,
                HEAT_CAPACITY_OF_WATER,
                input_temperature,
                self.test_logger,
                self.mass_flow_rate,
                irradiance,
                self.wind_speed,
            )

        self.assertEqual(e.exception, test_exception)
        self.test_logger.error.assert_called_once_with(
            "Error attempting to predict electric efficiency of the PV-T collector: %s",
            str(e.exception),
        )

    def test_low_irradiance_low_temperature(self) -> None:
        """Tests the case with low irradiance and low temperature."""

        # Set up input parameters.
        electrical_efficiency = 0.15
        input_temperature = LOW_TEMPERATURE_THRESHOLD - 0.1
        irradiance = LOW_IRRADIANCE_THRESHOLD - 0.1
        output_temperature = 80

        # Set up electrical and thermal model return values.
        self.pvt_panel.electric_models[  # type: ignore [index]
            RegressorType.LOW_IRRADIANCE_LOW_TEMPERATURE
        ].predict.return_value = electrical_efficiency
        self.pvt_panel.thermal_models[  # type: ignore [index]
            RegressorType.LOW_IRRADIANCE_LOW_TEMPERATURE
        ].predict.return_value = output_temperature

        # Call the calculation method.
        (
            calculated_fractional_electrical_performance,
            calculated_output_temperature,
        ) = self.pvt_panel.calculate_performance(
            self.ambient_temperature,
            HEAT_CAPACITY_OF_WATER,
            input_temperature,
            self.test_logger,
            self.mass_flow_rate,
            irradiance,
            self.wind_speed,
        )

        # Type-check the results
        self.assertIsInstance(electrical_efficiency, float)

        # Assert the calculation was correct.
        expected_fractional_electrical_performance = (
            electrical_efficiency / self.pvt_panel.pv_layer.reference_efficiency  # type: ignore [operator]
        ) * (irradiance / REFERENCE_SOLAR_IRRADIANCE)
        self.assertEqual(
            expected_fractional_electrical_performance,
            calculated_fractional_electrical_performance,
        )
        self.assertEqual(output_temperature, calculated_output_temperature)

    def test_low_irradiance_high_temperature(self) -> None:
        """Tests the case with low irradiance and high temperature."""

        # Set up input parameters.
        electrical_efficiency = 0.15
        input_temperature = LOW_TEMPERATURE_THRESHOLD
        irradiance = LOW_IRRADIANCE_THRESHOLD - 0.1
        output_temperature = 80

        # Set up electrical and thermal model return values.
        self.pvt_panel.electric_models[  # type: ignore [index]
            RegressorType.LOW_IRRADIANCE_HIGH_TEMPERATURE
        ].predict.return_value = electrical_efficiency
        self.pvt_panel.thermal_models[  # type: ignore [index]
            RegressorType.LOW_IRRADIANCE_HIGH_TEMPERATURE
        ].predict.return_value = output_temperature

        # Call the calculation method.
        (
            calculated_fractional_electrical_performance,
            calculated_output_temperature,
        ) = self.pvt_panel.calculate_performance(
            self.ambient_temperature,
            HEAT_CAPACITY_OF_WATER,
            input_temperature,
            self.test_logger,
            self.mass_flow_rate,
            irradiance,
            self.wind_speed,
        )

        # Type-check the returned variables
        self.assertIsInstance(calculated_fractional_electrical_performance, float)
        self.assertIsInstance(calculated_output_temperature, float)

        # Assert the calculation was correct.
        expected_fractional_electrical_performance = (
            electrical_efficiency / self.pvt_panel.pv_layer.reference_efficiency  # type: ignore [operator]
        ) * (irradiance / REFERENCE_SOLAR_IRRADIANCE)
        self.assertEqual(
            expected_fractional_electrical_performance,
            calculated_fractional_electrical_performance,
        )
        self.assertEqual(output_temperature, calculated_output_temperature)

    def test_high_irradiance_low_temperature(self) -> None:
        """Tests the case with high irradiance and low temperature."""

        # Set up input parameters.
        electrical_efficiency = 0.15
        input_temperature = LOW_TEMPERATURE_THRESHOLD - 0.1
        irradiance = LOW_IRRADIANCE_THRESHOLD
        output_temperature = 80

        # Set up electrical and thermal model return values.
        self.pvt_panel.electric_models[  # type: ignore [index]
            RegressorType.STANDARD_IRRADIANCE_LOW_TEMPERATURE
        ].predict.return_value = electrical_efficiency
        self.pvt_panel.thermal_models[  # type: ignore [index]
            RegressorType.STANDARD_IRRADIANCE_LOW_TEMPERATURE
        ].predict.return_value = output_temperature

        # Call the calculation method.
        (
            calculated_fractional_electrical_performance,
            calculated_output_temperature,
        ) = self.pvt_panel.calculate_performance(
            self.ambient_temperature,
            HEAT_CAPACITY_OF_WATER,
            input_temperature,
            self.test_logger,
            self.mass_flow_rate,
            irradiance,
            self.wind_speed,
        )

        # Type-check the returned variables
        self.assertIsInstance(calculated_fractional_electrical_performance, float)
        self.assertIsInstance(calculated_output_temperature, float)

        # Assert the calculation was correct.
        expected_fractional_electrical_performance = (
            electrical_efficiency / self.pvt_panel.pv_layer.reference_efficiency  # type: ignore [operator]
        ) * (irradiance / REFERENCE_SOLAR_IRRADIANCE)
        self.assertEqual(
            expected_fractional_electrical_performance,
            calculated_fractional_electrical_performance,
        )
        self.assertEqual(output_temperature, calculated_output_temperature)

    def test_high_irradiance_high_temperature(self) -> None:
        """Tests the case with high irradiance and high temperature."""

        # Set up input parameters.
        electrical_efficiency = 0.15
        input_temperature = LOW_TEMPERATURE_THRESHOLD
        irradiance = LOW_IRRADIANCE_THRESHOLD
        output_temperature = 80

        # Set up electrical and thermal model return values.
        self.pvt_panel.electric_models[  # type: ignore [index]
            RegressorType.STANDARD_IRRADIANCE_HIGH_TEMPERATURE
        ].predict.return_value = electrical_efficiency
        self.pvt_panel.thermal_models[  # type: ignore [index]
            RegressorType.STANDARD_IRRADIANCE_HIGH_TEMPERATURE
        ].predict.return_value = output_temperature

        # Call the calculation method.
        (
            calculated_fractional_electrical_performance,
            calculated_output_temperature,
        ) = self.pvt_panel.calculate_performance(
            self.ambient_temperature,
            HEAT_CAPACITY_OF_WATER,
            input_temperature,
            self.test_logger,
            self.mass_flow_rate,
            irradiance,
            self.wind_speed,
        )

        # Type-check the outputs
        self.assertIsInstance(calculated_fractional_electrical_performance, float)
        self.assertIsInstance(calculated_output_temperature, float)

        # Assert the calculation was correct.
        expected_fractional_electrical_performance = (
            electrical_efficiency / self.pvt_panel.pv_layer.reference_efficiency  # type: ignore [operator]
        ) * (irradiance / REFERENCE_SOLAR_IRRADIANCE)
        self.assertEqual(
            expected_fractional_electrical_performance,
            calculated_fractional_electrical_performance,
        )
        self.assertEqual(output_temperature, calculated_output_temperature)

    def test_no_electric_models(self) -> None:
        """Tests the case where there are no electric models on the instance."""

        self.pvt_panel.electric_models = None
        with self.assertRaises(ProgrammerJudgementFault):
            self.pvt_panel.calculate_performance(
                self.ambient_temperature,
                HEAT_CAPACITY_OF_WATER,
                mock.MagicMock(),  # type: ignore [arg-type]
                self.test_logger,
                self.mass_flow_rate,
                mock.MagicMock(),  # type: ignore [arg-type]
                self.wind_speed,
            )

        self.test_logger.error.assert_called_once_with(
            "%sThe PV-T instance does not have well-defined and loaded models.%s",
            BColours.fail,
            BColours.endc,
        )

    def test_no_thermal_models(self) -> None:
        """Tests the case where there are no thermal models on the instance."""

        self.pvt_panel.thermal_models = None
        with self.assertRaises(ProgrammerJudgementFault):
            self.pvt_panel.calculate_performance(
                self.ambient_temperature,
                HEAT_CAPACITY_OF_WATER,
                mock.MagicMock(),  # type: ignore [arg-type]
                self.test_logger,
                self.mass_flow_rate,
                mock.MagicMock(),  # type: ignore [arg-type]
                self.wind_speed,
            )

        self.test_logger.error.assert_called_once_with(
            "%sThe PV-T instance does not have well-defined and loaded models.%s",
            BColours.fail,
            BColours.endc,
        )

    def test_thermal_model_error(self) -> None:
        """Tests the case where the thermal model throws and error."""

        # Set up input parameters.
        input_temperature = LOW_TEMPERATURE_THRESHOLD - 0.1
        irradiance = LOW_IRRADIANCE_THRESHOLD - 0.1
        test_exception = Exception("TEST EXCEPTION")

        # Set up electrical and thermal model return values.
        self.pvt_panel.electric_models[  # type: ignore [index]
            RegressorType.LOW_IRRADIANCE_LOW_TEMPERATURE
        ].predict.return_value = 0
        self.pvt_panel.thermal_models[  # type: ignore [index]
            RegressorType.LOW_IRRADIANCE_LOW_TEMPERATURE
        ].predict.side_effect = test_exception

        # Call the calculation method.
        with self.assertRaises(Exception) as e:
            self.pvt_panel.calculate_performance(
                self.ambient_temperature,
                HEAT_CAPACITY_OF_WATER,
                input_temperature,
                self.test_logger,
                self.mass_flow_rate,
                irradiance,
                self.wind_speed,
            )

        self.assertEqual(e.exception, test_exception)
        self.test_logger.error.assert_called_once_with(
            "Error attempting to predict electric efficiency of the PV-T collector: %s",
            str(e.exception),
        )


class TestSolarThermalPanelPerformance(unittest.TestCase):
    """Tests the `calculate_performance` function of the solar-thermal collector."""

    def setUp(self) -> None:
        """Sets up functionality in common across test cases."""

        self.input_data = {
            "name": "default_solar_thermal",
            "area": 2.106,
            "azimuthal_orientation": 180,
            "lifetime": 20,
            "max_mass_flow_rate": 250,
            "min_mass_flow_rate": 60,
            "nominal_mass_flow_rate": 125,
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
            "performance_curve": {
                "zeroth_order": 0.694,
                "first_order": 3.53,
                "second_order": 0.0047,
            },
        }

        # Set up required mocks for instantiation.
        self.ambient_temperature = 40
        self.input_temperature = 30
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

        _, output_temperature = self.solar_thermal_panel.calculate_performance(
            self.ambient_temperature,
            HEAT_CAPACITY_OF_WATER,
            self.input_temperature,
            self.test_logger,
            self.solar_thermal_panel.nominal_mass_flow_rate,
            self.irradiance / 1000,
            self.wind_speed,
        )

        # Type-check the outputs
        self.assertIsInstance(output_temperature, float)

        # Compute the efficiency two ways and check that these are equal.
        collector_temperature = 0.5 * (self.input_temperature + output_temperature)  # type: ignore [operator]
        efficiency_by_equation = (
            self.solar_thermal_panel.performance_curve.eta_0
            + self.solar_thermal_panel.performance_curve.c_1
            * (collector_temperature - self.ambient_temperature)
            / self.irradiance
            + self.solar_thermal_panel.performance_curve.c_2
            * (collector_temperature - self.ambient_temperature) ** 2
            / self.irradiance
        )
        efficiency_by_output: float = (
            (self.solar_thermal_panel.nominal_mass_flow_rate / 3600)
            * HEAT_CAPACITY_OF_WATER
            * (output_temperature - self.input_temperature)  # type: ignore [operator]
        ) / (self.solar_thermal_panel.area * self.irradiance)

        self.assertEqual(
            round(efficiency_by_equation, 8), round(efficiency_by_output, 8)
        )
