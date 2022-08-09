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
from clover.__utils__ import (
    HEAT_CAPACITY_OF_WATER,
    BColours,
    ProgrammerJudgementFault,
    RegressorType,
    SolarPanelType,
)  # pylint: disable=unused-import

import pytest  # pylint: disable=import-error

from ...solar import (
    LOW_IRRADIANCE_THRESHOLD,
    LOW_TEMPERATURE_THRESHOLD,
    REFERENCE_SOLAR_IRRADIANCE,
    HybridPVTPanel,
    PVPanel,
    PerformanceCurve,
)


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
            self.solar_panels,
            self.thermal_models,
        )

        super().setUp()

    @pytest.mark.unit
    def test_electrical_model_error(self) -> None:
        """Tests the case where there is an error in the electric calculation."""

        # Set up input parameters.
        input_temperature = LOW_TEMPERATURE_THRESHOLD - 0.1
        irradiance = LOW_IRRADIANCE_THRESHOLD - 0.1
        test_exception = Exception("TEST EXCEPTION")

        # Set up electrical and thermal model return values.
        self.pvt_panel.electric_models[
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

    @pytest.mark.unit
    def test_low_irradiance_low_temperature(self) -> None:
        """Tests the case with low irradiance and low temperature."""

        # Set up input parameters.
        electrical_efficiency = 0.15
        input_temperature = LOW_TEMPERATURE_THRESHOLD - 0.1
        irradiance = LOW_IRRADIANCE_THRESHOLD - 0.1
        output_temperature = 80

        # Set up electrical and thermal model return values.
        self.pvt_panel.electric_models[
            RegressorType.LOW_IRRADIANCE_LOW_TEMPERATURE
        ].predict.return_value = electrical_efficiency
        self.pvt_panel.thermal_models[
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

        # Assert the calculation was correct.
        expected_fractional_electrical_performance = (
            electrical_efficiency / self.pvt_panel.pv_layer.reference_efficiency
        ) * (irradiance / REFERENCE_SOLAR_IRRADIANCE)
        self.assertEqual(
            expected_fractional_electrical_performance,
            calculated_fractional_electrical_performance,
        )
        self.assertEqual(output_temperature, calculated_output_temperature)

    @pytest.mark.unit
    def test_low_irradiance_high_temperature(self) -> None:
        """Tests the case with low irradiance and high temperature."""

        # Set up input parameters.
        electrical_efficiency = 0.15
        input_temperature = LOW_TEMPERATURE_THRESHOLD
        irradiance = LOW_IRRADIANCE_THRESHOLD - 0.1
        output_temperature = 80

        # Set up electrical and thermal model return values.
        self.pvt_panel.electric_models[
            RegressorType.LOW_IRRADIANCE_HIGH_TEMPERATURE
        ].predict.return_value = electrical_efficiency
        self.pvt_panel.thermal_models[
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

        # Assert the calculation was correct.
        expected_fractional_electrical_performance = (
            electrical_efficiency / self.pvt_panel.pv_layer.reference_efficiency
        ) * (irradiance / REFERENCE_SOLAR_IRRADIANCE)
        self.assertEqual(
            expected_fractional_electrical_performance,
            calculated_fractional_electrical_performance,
        )
        self.assertEqual(output_temperature, calculated_output_temperature)

    @pytest.mark.unit
    def test_high_irradiance_low_temperature(self) -> None:
        """Tests the case with high irradiance and low temperature."""

        # Set up input parameters.
        electrical_efficiency = 0.15
        input_temperature = LOW_TEMPERATURE_THRESHOLD - 0.1
        irradiance = LOW_IRRADIANCE_THRESHOLD
        output_temperature = 80

        # Set up electrical and thermal model return values.
        self.pvt_panel.electric_models[
            RegressorType.STANDARD_IRRADIANCE_LOW_TEMPERATURE
        ].predict.return_value = electrical_efficiency
        self.pvt_panel.thermal_models[
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

        # Assert the calculation was correct.
        expected_fractional_electrical_performance = (
            electrical_efficiency / self.pvt_panel.pv_layer.reference_efficiency
        ) * (irradiance / REFERENCE_SOLAR_IRRADIANCE)
        self.assertEqual(
            expected_fractional_electrical_performance,
            calculated_fractional_electrical_performance,
        )
        self.assertEqual(output_temperature, calculated_output_temperature)

    @pytest.mark.unit
    def test_high_irradiance_high_temperature(self) -> None:
        """Tests the case with high irradiance and high temperature."""

        # Set up input parameters.
        electrical_efficiency = 0.15
        input_temperature = LOW_TEMPERATURE_THRESHOLD
        irradiance = LOW_IRRADIANCE_THRESHOLD
        output_temperature = 80

        # Set up electrical and thermal model return values.
        self.pvt_panel.electric_models[
            RegressorType.STANDARD_IRRADIANCE_HIGH_TEMPERATURE
        ].predict.return_value = electrical_efficiency
        self.pvt_panel.thermal_models[
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

        # Assert the calculation was correct.
        expected_fractional_electrical_performance = (
            electrical_efficiency / self.pvt_panel.pv_layer.reference_efficiency
        ) * (irradiance / REFERENCE_SOLAR_IRRADIANCE)
        self.assertEqual(
            expected_fractional_electrical_performance,
            calculated_fractional_electrical_performance,
        )
        self.assertEqual(output_temperature, calculated_output_temperature)

    @pytest.mark.unit
    def test_no_electric_models(self) -> None:
        """Tests the case where there are no electric models on the instance."""

        self.pvt_panel.electric_models = None
        with self.assertRaises(ProgrammerJudgementFault):
            self.pvt_panel.calculate_performance(
                self.ambient_temperature,
                HEAT_CAPACITY_OF_WATER,
                None,
                self.test_logger,
                self.mass_flow_rate,
                None,
                self.wind_speed,
            )

        self.test_logger.error.assert_called_once_with(
            "%sThe PV-T instance does not have well-defined and loaded models.%s",
            BColours.fail,
            BColours.endc,
        )

    @pytest.mark.unit
    def test_no_thermal_models(self) -> None:
        """Tests the case where there are no thermal models on the instance."""

        self.pvt_panel.thermal_models = None
        with self.assertRaises(ProgrammerJudgementFault):
            self.pvt_panel.calculate_performance(
                self.ambient_temperature,
                HEAT_CAPACITY_OF_WATER,
                None,
                self.test_logger,
                self.mass_flow_rate,
                None,
                self.wind_speed,
            )

        self.test_logger.error.assert_called_once_with(
            "%sThe PV-T instance does not have well-defined and loaded models.%s",
            BColours.fail,
            BColours.endc,
        )

    @pytest.mark.unit
    def test_thermal_model_error(self) -> None:
        """Tests the case where the thermal model throws and error."""

        # Set up input parameters.
        input_temperature = LOW_TEMPERATURE_THRESHOLD - 0.1
        irradiance = LOW_IRRADIANCE_THRESHOLD - 0.1
        test_exception = Exception("TEST EXCEPTION")

        # Set up electrical and thermal model return values.
        self.pvt_panel.electric_models[
            RegressorType.LOW_IRRADIANCE_LOW_TEMPERATURE
        ].predict.return_value = 0
        self.pvt_panel.thermal_models[
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
