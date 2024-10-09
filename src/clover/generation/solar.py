#!/usr/bin/python3
########################################################################################
# solar.py - Solar generation module  .                                                #
#                                                                                      #
# Author: Phil Sandwell                                                                #
# Copyright: Phil Sandwell, 2021                                                       #
# License: Open source                                                                 #
# Most recent update: 14/07/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
solar.py - The solar-profile-generation module for CLOVER.

This module fetches solar profiles from renewables.ninja, parses them and saves them
for use locally within CLOVER.

"""

import enum
import math

from abc import ABC, abstractmethod
from dataclasses import dataclass
from logging import Logger
from typing import Any, Type

import pandas as pd

from sklearn.linear_model._coordinate_descent import Lasso

from ..__utils__ import (
    BColours,
    FlowRateError,
    HEAT_CAPACITY_OF_WATER,
    InputFileError,
    Location,
    NAME,
    ProgrammerJudgementFault,
    RenewablesNinjaError,
    RegressorType,
    SolarPanelType,
    ZERO_CELCIUS_OFFSET,
)
from .__utils__ import BaseRenewablesNinjaThread, SolarDataType, total_profile_output

__all__ = (
    "COLLECTOR_FROM_TYPE",
    "get_profile_prefix",
    "HybridPVTPanel",
    "PerformanceCurve",
    "PVPanel",
    "SolarDataThread",
    "SolarDataType",
    "SolarThermalPanel",
    "solar_degradation",
    "SOLAR_LOGGER_NAME",
    "total_solar_output",
)


# Default tracking:
#   The default keyword to use for fixed-mounted panels.
_DEFAULT_TRACKING: str = "fixed"

# Default PV unit:
#   The default PV unit size to use, measured in kWp.
DEFAULT_PV_UNIT: float = 1  # [kWp]

# ELECTRIC_PERFORMANCE_CURVE:
#   Keyword for the electric performance curve.
ELECTRIC_PERFORMANCE_CURVE: str = "electric_performance_curve"

# FIRST_ORDER:
#   Keyword for parsing first-order coefficient.
FIRST_ORDER: str = "first_order"

# LAND_USE:
#   Keyword for the land use of each panel.
LAND_USE: str = "land_use"

# Low irradiance threshold:
#   The threshold at which to switch between a low-irradiance model and a standard-
#   irradiance model.
LOW_IRRADIANCE_THRESHOLD: float = 25  # [W/m^2]

# Low temperature threshold:
#   The threshold at which to switch between a low-temperature model and a standard-
#   temperature model.
LOW_TEMPERATURE_THRESHOLD: float = 50  # [degC]

# Maximum mass flow rate:
#   Keyword for parsing the maximum--mass flow rate information.
MAX_MASS_FLOW_RATE: str = "max_mass_flow_rate"

# Minimum mass flow rate:
#   Keyword for parsing the minimum--mass flow rate information.
MIN_MASS_FLOW_RATE: str = "min_mass_flow_rate"

# NOMINAL_MASS_FLOW_RATE:
#   Keyword for the nominal mass flow rate of HTF through the panel.
NOMINAL_MASS_FLOW_RATE: str = "nominal_mass_flow_rate"

# NOMINAL_POWER:
#   Keyword for the nominal power of the panel.
NOMINAL_POWER: str = "nominal_power"

# PV_MODULE_CHARACTERISTICS:
#   Keyword for module characteristics.
PV_MODULE_CHARACTERISTICS: str = "pv_module_characteristics"

# REFERENCE_EFFICIENCY:
#   Keyword for the reference efficiency of a PV panel.
REFERENCE_EFFICIENCY: str = "reference_efficiency"

# Reference solar irradiance:
#   The reference solar irradiance, used to compute fractional PV-T electric
#   performance values.
REFERENCE_SOLAR_IRRADIANCE: float = 1000  # [W/m^2]

# REFERENCE_TEMPERATURE:
#   Keyword for the reference temperature of a PV panel.
REFERENCE_TEMPERATURE: str = "reference_temperature"

# SECOND_ORDER:
#   Keyword for parsing second-order coefficient.
SECOND_ORDER: str = "second_order"

# Solar logger name:
#   The name to use for the solar logger.
SOLAR_LOGGER_NAME = "solar_generation"

# STAGNATION_TEMPERATURE:
#   Keyword for the stagnation temperature of the collector.
STAGNATION_TEMPERATURE: str = "stagnation_temperature"

# STEFAN_BOLTZMAN_CONSTANT:
#   The Stefan-Boltzman constant in SI units.
STEFAN_BOLTZMAN_CONSTANT: float = 5.670374419 * (10**-8)

# THERMAL_COEFFICIENT:
#   Keyword for the temperature coefficient for the performance of a PV panel.
THERMAL_COEFFICIENT: str = "thermal_coefficient"

# THERMALPERFORMANCE_CURVE:
#   Keyword for the thermal performance curve.
THERMAL_PERFORMANCE_CURVE: str = "thermal_performance_curve"

# Tracking map:
#   Map used for determining the tracking state of the panels.
_TRACKING_MAP: dict[str, int] = {
    _DEFAULT_TRACKING: 0,
    "single": 1,
    "single_axis": 1,
    "azimuthal": 1,
    "dual": 2,
    "dual_axis": 2,
}

# ZEROTH_ORDER:
#   Keyword for parsing zeroth-order coefficient.
ZEROTH_ORDER: str = "zeroth_order"


@dataclass
class PerformanceCurve:
    """
    Represents a performance curve for a solar-thermal collector.

    Solar-thermal collectors can be characterised by a performance curve,

        eta = eta_0 + c_1 * (T_c - T_a) / G + c_2 * (T_c - T_a)^2 / G,

    where `eta_0`, `c_1` and `c_2` give the zeroth-, first- and second-order
    coefficients which characterise the performance of the collector, `T_c` is the
    average temperature of the collector and `T_a` the ambient temperature, both
    measured in either degrees Kelvin or Celsius, but the same unit for each, and `G` is
    the solar irradiance, measured in Watts per meter squared.

    The attributes, `eta_0`, `c_1` and `c_2` are inherent properties of the collector
    and are contained within this class.

    .. attribute:: zeroth_order_cefficient
        The zeroth-order term for the performance curve.

    .. attribute:: first_order_cefficient
        The zeroth-order term for the performance curve.

    .. attribute:: second_order_cefficient
        The zeroth-order term for the performance curve.

    """

    zeroth_order_coefficient: float
    first_order_coefficient: float
    second_order_coefficient: float

    @property
    def eta_0(self) -> float:
        """
        Wrapper around the zeroth-order coefficient.

        Outputs:
            - The zeroth-order coefficient.

        """

        return self.zeroth_order_coefficient

    @property
    def c_1(self) -> float:
        """
        Wrapper around the first-order coefficient.

        Outputs:
            - The first-order coefficient.

        """

        return self.first_order_coefficient

    @property
    def c_2(self) -> float:
        """
        Wrapper around the second-order coefficient.

        Outputs:
            - The second-order coefficient.

        """

        return self.second_order_coefficient


@dataclass
class PVModuleCharacteristics:
    """
    Represents characteristcs of the PV module.

    .. attribute:: nominal_power
        Denoste the nominal power of the PV module in kWp.

    .. attribute:: reference_efficiency
        Denotes the reference efficiency of the PV module.

    .. attribute:: reference_temperature
        Denotes the reference temperature of the PV module, measured in degrees Kelvin.

    .. attribute:: thermal_coefficient
        Denotes the thermal coefficienct of the PV module.

    """

    nominal_power: float
    reference_efficiency: float
    _reference_temperature: float
    thermal_coefficient: float

    @property
    def reference_temperature(self) -> float:
        """
        Return the reference temperature in degrees Kelvin.

        Outputs:
            The reference temperature in degrees Kelvin.

        """

        return self._reference_temperature + ZERO_CELCIUS_OFFSET


class Tracking(enum.Enum):
    """
    Specifies the tracking state of the panel being considered.

    - FIXED:
        Denotes that the panel is fixed in both its azimuthal orientation and tilt.
    - SINGLE_AXIS:
        Denotes that the panel is single-axis tracking, i.e., has a fixed tilt but its
        azimuthal orietntation can change.
    - DUAL_AXIS:
        Denotes that the panel is dual-axis tracking, i.e., both its azimuthal
        orientation and tilt can change.

    """

    FIXED: int = 0
    SINGLE_AXIS: int = 1
    DUAL_AXIS: int = 2

    @classmethod
    def from_text(cls, logger: Logger, text: str) -> Any:
        """
        Used to instntiate the :class:`Tracking` instance based on the input text.

        Inputs:
            - text:
                The text describing the tracking from the input file.

        """

        try:
            return cls(_TRACKING_MAP[text])
        except KeyError as err:
            logger.error(
                "Input value of %s for tracking type is not valid. Valid tracking modes: %s",
                text,
                ", ".join([f"'{key}'" for key in _TRACKING_MAP]),
            )
            raise InputFileError(
                "solar_generation_inputs", f"Tracking mode '{text}' is not valid."
            ) from err

    @property
    def as_string(self) -> str:
        """
        Return a string representing the class.

        :return:
            A `str` containing the tracking information.

        """

        if self.value == 0:
            return "fixed"
        if self.value == 1:
            return "single_axis"
        return "dual_axis"


def _thermal_performance(
    ambient_temperature: float,
    area: float,
    htf_heat_capacity: float | None,
    input_temperature: float,
    mass_flow_rate: float,
    performance_curve: PerformanceCurve,
    solar_irradiance: float,
) -> tuple[float | None, float]:
    """
    Calculates the roots for the thermal performance of the collectors.

    Each collector has a characteristic performance curve, which is related to the
    efficiency of the collector by a simple equation:

        eta = eta_0
            + c_1 * (T_c - T_amb) / G
            + c_2 * (T_c - T_amb) ** 2 / G

    where `eta_0`, `c_1` and `c_2` give the zeroth-, first- and second-order
    coefficients which characterise the performance of the collector, `T_c` is the
    average temperature of the collector and `T_a` the ambient temperature, both
    measured in either degrees Kelvin or Celsius, but the same unit for each, and
    `G` is the solar irradiance, measured in Watts per meter squared. The attributes
    `eta_0`, `c_1` and `c_2` are inherent properties of the collector and are
    contained within the `performance_curve` attribute.

    This equation can be rearranged by expressing the efficiency as the energy
    gained by the heat-transfer fluid within the collector as a fraction of the
    total energy incident on the collector:

        eta = m_htf * c_htf * (T_out - T_in) / (A * G)

    where `T_out` and `T_in` give the output and input HTF temperatures
    respectively, and `m_htf` and `c_htf` give the mass-flow rate and specific heat
    capacityof the HTF through the collector. Combining these two yields

        0 = 4 * eta_0 * A * G                   \\ = c = zeroth_order_coefficient
            + 4 * m_htf * c_htf * T_in            |
            + 2 * c_1 * A * (T_in - T_amb)        |
            + c_2 * A * (T_in - T_amb) ** 2       /
            + (                                   \\ = b = first_order_coefficient
            - 4 * m_htf * c_htf                 |
            + 2 * c_1 * A                       |
            + 2 * c_2 * A * (T_in - T_amb)      /
            ) * T_out
            + (                                   \\ = a = second_order_coefficient
            4 * eta_0 * A * G                   |
            + 4 * m_htf * c_htf * T_in          |
            + 2 * c_1 * A * (T_in - T_amb)      |
            + c_2 * A * (T_in - T_amb) ** 2     /
            ) * T_out ** 2

    which can then be solved quadratically to determine the output temperature of
    HTF leaving the collector.

    Inputs:
        - ambient_temperature:
            The ambient temperature, measured in degrees Kelvin.
        - area:
            The area of the collector, in meters squared.
        - htf_heat_capacity:
            The heat capacity of the HTF entering the collector, measured in Joules
            per kilogram Kelvin (J/kgK).
        - input_temperature:
            The input temperature of the HTF entering the collector, measured in
            in degrees Kelvin.
        - mass_flow_rate:
            The mass-flow rate of HTF passing through the collector, measured in
            kilograms per second.
        - performance_curve:
            The performance curve for the collector.
        - solar_irradiance:
            The solar irradiance incident on the surface of the collector, measured
            in Watts per meter squared.

    Outputs:
        Both roots from the equation:
        - positive_root:
            The positive root taken from solving the quadratic equation, measured in
            Kelvin.
        - negative_root:
            The negative root taken from solving the quadratic equation, measured in
            Kelvin.

    """

    # Sanitise the HTF heat capacity
    htf_heat_capacity = float(
        htf_heat_capacity if htf_heat_capacity is not None else HEAT_CAPACITY_OF_WATER
    )

    # If noly a linear calculation is required, solve linearly.
    if performance_curve.c_2 == 0:
        return (
            None,
            (
                2 * performance_curve.eta_0 * area * solar_irradiance
                + 2 * mass_flow_rate * htf_heat_capacity * input_temperature
                + performance_curve.c_1
                * area
                * (input_temperature - 2 * ambient_temperature)
            )
            / (2 * mass_flow_rate * htf_heat_capacity - performance_curve.c_1 * area),
        )

    # Compute the various terms of the equation
    a: float = performance_curve.c_2 * area  # pylint: disable=invalid-name

    b: float = (  # pylint: disable=invalid-name
        2 * performance_curve.c_1 * area
        + 2
        * performance_curve.c_2
        * area
        * (input_temperature - 2 * ambient_temperature)
        - 4 * mass_flow_rate * htf_heat_capacity
    )

    c: float = (  # pylint: disable=invalid-name
        4 * performance_curve.eta_0 * area * solar_irradiance
        + 4 * mass_flow_rate * htf_heat_capacity * input_temperature
        + 2
        * performance_curve.c_1
        * area
        * (input_temperature - 2 * ambient_temperature)
        + performance_curve.c_2
        * area
        * (input_temperature - 2 * ambient_temperature) ** 2
    )

    # Use numpy or Pandas to solve the quadratic to determine the performance of
    # the collector
    positive_root: float = (  # pylint: disable=unused-variable
        -b + math.sqrt(b**2 - 4 * a * c)
    ) / (2 * a)
    negative_root: float = float((-b - math.sqrt(b**2 - 4 * a * c)) / (2 * a))

    return positive_root, negative_root


def reduced_temperature(
    ambient_temperature: float, average_temperature: float, solar_irradiance: float
) -> float | None:
    """
    Computes the reduced temperature of the collector.

    NOTE: The ambient temperature and average temperature need to be measured in the
    same units, whether it's Kelvin or Celcius, but it does not matter which of these
    two is used.

    Inputs:
        - ambient_temperature:
            The ambient temperature surrounding the collector.
        - average_temperature:
            The average temperature of the collector.
        - solar_irradiance:
            The solar irradiance, measured in Watts per meter squared.

    Outputs:
        The reduced temperature of the collector in Kelvin meter squared per Watt.

    """

    # The reduced temperature cannot be computed when there is no solar irradiance
    if solar_irradiance == 0:
        return None

    return (average_temperature - ambient_temperature) / solar_irradiance


class SolarPanel:  # pylint: disable=too-few-public-methods
    """
    Represents a solar panel being considered.

    .. attribute:: azimuthal_orientation
        The azimuthal orientation of the panel, defined in degrees from North.

    .. attribute:: lifetime
        The lifetime of the panel in years.

    .. attribute:: name
        The name of the panel being considered.

    .. attribite:: panel_type
        The type of panel being considered.

    .. attribute:: tilt
        The angle between the panel and the horizontal.

    """

    panel_type: SolarPanelType

    def __init__(
        self,
        azimuthal_orientation: float,
        lifetime: int,
        name: str,
        tilt: float,
    ) -> None:
        """
        Instantiate a :class:`SolarPanel` instance.

        Inputs:
            - azimuthal_orientation:
                The azimuthal orientation of the :class:`SolarPanel`.
            - lifetime:
                The lifetime of the :class:`SolarPanel` in years.
            - name:
                The name to assign to the :class:`SolarPanel` in order to uniquely
                identify it.
            - tilt:
                The tilt of the panel in degrees above the horizontal.

        """

        self.azimuthal_orientation: float = azimuthal_orientation
        self.lifetime: int = lifetime
        self.name: str = name
        self.tilt: float = tilt

    def __init_subclass__(cls, panel_type: SolarPanelType) -> None:
        """
        The init_subclass hook, run on instantiation of the :class:`SolarPanel`.

        Inputs:
            - panel_type:
                The type of panel being considered.

        Outputs:
            An instantiated :class:`SolarPanel` instance.

        """

        cls.panel_type = panel_type

        return super().__init_subclass__()

    @abstractmethod
    def calculate_performance(
        self,
        ambient_temperature: float,
        htf_heat_capacity: float,
        input_temperature: float,
        logger: Logger,
        mass_flow_rate: float,
        solar_irradiance: float,
        wind_speed: float,
    ) -> tuple[float | None, float | None]:
        """
        Abstract method for calculation of collector performance.

        Inputs:
            - ambient_temperature:
                The ambient temperature, measured in degrees Celsius.
            - htf_heat_capacity:
                The heat capacity of the HTF entering the collector, measured in Joules
                per kilogram Kelvin (J/kgK).
            - input_temperature:
                The input temperature of the HTF entering the collector, measured in
                in degrees Celsius.
            - logger:
                The :class:`logging.Logger` to use for the run.
            - mass_flow_rate:
                The mass-flow rate of HTF passing through the collector, measured in
                kilograms per second.
            - solar_irradiance:
                The solar irradiance incident on the surface of the collector, measured
                in Watts per meter squared.
            - wind_speed:
                The wind speed at the collector, measured in meters per second.

        Outputs:
            - fractional_electric_performance:
                The fractional electric performance defined between 0 (panel is not
                operating, i.e., no output) and 1 (panel is operating at full test
                potential of reference efficiency under reference irradiance).
            - output_temperature:
                The temperature of the HTF leaving the collector, measured in degrees
                Celsius.

        """


# class PVPanel(
#     SolarPanel, panel_type=SolarPanelType.PV
# ):  # pylint: disable=too-few-public-methods
#     """
#     Represents a photovoltaic panel.

#     .. attribute:: pv_unit
#         The unit of PV power being considered, defaulting to 1 kWp.

#     .. attribute:: pv_unit_overrided
#         Whether the default PV unit was overrided (True) or not (False).

#     .. attribute:: reference_efficiency
#         The efficiency of the PV layer under standard test conditions.

#     .. attribute:: reference_temperature
#         The reference temperature of the PV layer of the panel, measured in degrees
#         Celsius.

#     .. attribute:: thermal_coefficient
#         The thermal coefficient of performance of the PV layer of the panel, measured in
#         kelvin^(-1).

#     """

#     def __init__(
#         self,
#         azimuthal_orientation: float | None,
#         lifetime: int,
#         name: str,
#         pv_unit: float | None,
#         pv_unit_overrided: bool,
#         reference_efficiency: float | None,
#         reference_temperature: float | None,
#         thermal_coefficient: float | None,
#         tilt: float | None,
#         tracking: Tracking,
#     ) -> None:
#         """
#         Instantiate a :class:`PVPanel` instance.

#         Inputs:
#             - azimuthal_orientation:
#                 The azimuthal orientation of the :class:`SolarPanel`.
#             - lifetime:
#                 The lifetime of the :class:`SolarPanel` in years.
#             - name:
#                 The name to assign to the :class:`SolarPanel` in order to uniquely
#                 identify it.
#             - pv_unit:
#                 The output power, in Watts, of the PV layer of the panel per unit panel
#                 installed.
#             - pv_unit_overrided:
#                 Whether this unit has been overrided from its default value (True) or
#                 not (False).
#             - reference_efficiency:
#                 The reference efficiency of the panel, if required, otherwise `None`.
#             - reference_temperature:
#                 The temperature, in degrees Celsius, at which the reference efficiency
#                 is defined, if required, otherwise `None`.
#             - thermal_coefficient:
#                 The thermal coefficient of the PV layer of the panel, if required,
#                 otherwise `None`.
#             - tilt:
#                 The tilt of the panel in degrees above the horizontal.

#         """

#         super().__init__(
#             azimuthal_orientation,
#             lifetime,
#             name,
#             tilt,
#         )

#         self.azimuthal_orientation: float | None = azimuthal_orientation
#         self.lifetime: int = lifetime
#         self.name: str = name
#         self.pv_unit: float = pv_unit
#         self.pv_unit_overrided: bool = pv_unit_overrided
#         self.reference_efficiency: float | None = reference_efficiency
#         self.reference_temperature: float | None = reference_temperature
#         self.thermal_coefficient: float | None = thermal_coefficient
#         self.tilt: float | None = tilt
#         self.tracking = tracking

#     def __init_subclass__(cls, panel_type: SolarPanelType) -> None:
#         """
#         The init_subclass hook, run on instantiation of the :class:`SolarPanel`.

#         Inputs:
#             - panel_type:
#                 The type of panel being considered.

#         Outputs:
#             An instantiated :class:`SolarPanel` instance.

#         """

#         cls.panel_type = panel_type

#         return super().__init_subclass__()


#     def __hash__(self) -> int:
#         """
#         Return a unique identifier for the panel.

#         Because the solar panel instances are used for fetching weather data, panels
#         with unique tilt, azimuthal orientation, and tracking, need to be kept separate.

#         These parameters are hence used to determine the "unique" hash for the panel.

#         """

#         return hash(
#             self.tracking.value
#             + 3
#             * (
#                 self.azimuthal_orientation
#                 if self.azimuthal_orientation is not None
#                 else 0
#             )
#             + 540 * (self.tilt if self.tilt is not None else 0)
#         )

#     def __eq__(self, other: Any) -> bool:
#         """Used to determine whether to instances are identical for creating a set."""

#         return (  # type: ignore[no-any-return]
#             self.tracking == other.tracking
#             and self.azimuthal_orientation == other.azimuthal_orientation
#             and self.tilt == other.tilt
#         )

#     @property
#     def as_dict(self) -> dict[str, Any]:
#         """
#         Return a dictionary based on the panel information.

#         Outputs:
#             - A mapping containing the input information based on the panel.

#         """

#         return {
#             "azimuthal_orientation": self.azimuthal_orientation,
#             "lifetime": self.lifetime,
#             "name": self.name,
#             "pv_unit": self.pv_unit,
#             "pv_unit_overrided": self.pv_unit_overrided,
#             "reference_efficiency": self.reference_efficiency,
#             "reference_temperature": self.reference_temperature,
#             "thermal_coefficient": self.thermal_coefficient,
#             "tilt": self.tilt,
#             "tracking": self.tracking.as_string,
#             "type": self.panel_type.value,
#         }

#     @classmethod
#     def from_dict(cls, logger: Logger, solar_inputs: dict[str, Any]) -> Any:
#         """
#         Instantiate a :class:`PVPanel` instance based on the input data.

#         Inputs:
#             - logger:
#                 The logger to use for the run.
#             - solar_inputs:
#                 The solar input data for the panel.

#         Outputs:
#             A :class:`PVPanel` instance.

#         """

#         logger.info("Attempting to create PVPanel from solar input data.")

#         if "pv_unit" in solar_inputs:
#             pv_unit: float = solar_inputs["pv_unit"]
#             pv_unit_overrided: bool = True
#             logger.info(
#                 "`pv_unit` variable specified, using a pv unit of %s kWp", pv_unit
#             )
#         else:
#             pv_unit = DEFAULT_PV_UNIT
#             pv_unit_overrided = False
#             logger.info("No `pv_unit` keyword specified, defaulting to %s kWp", pv_unit)

#         tracking: Tracking = Tracking.from_text(
#             logger, solar_inputs.get("tracking", _DEFAULT_TRACKING)
#         )

#         if tracking == Tracking.FIXED:
#             azimuthal_orientation: float | None = solar_inputs["azimuthal_orientation"]
#         else:
#             azimuthal_orientation = None

#         if tracking != Tracking.DUAL_AXIS:
#             tilt: float | None = solar_inputs["tilt"]
#         else:
#             tilt = None

#         return cls(
#             azimuthal_orientation,
#             solar_inputs["lifetime"],
#             solar_inputs[NAME],
#             pv_unit,
#             pv_unit_overrided,
#             (
#                 solar_inputs["reference_efficiency"]
#                 if "reference_efficiency" in solar_inputs
#                 else None
#             ),
#             (
#                 solar_inputs["reference_temperature"]
#                 if "reference_temperature" in solar_inputs
#                 else None
#             ),
#             (
#                 solar_inputs["thermal_coefficient"]
#                 if "thermal_coefficient" in solar_inputs
#                 else None
#             ),
#             tilt,
#             tracking,
#         )

#     def calculate_performance(
#         self,
#         ambient_temperature: float,
#         htf_heat_capacity: float,
#         input_temperature: float,
#         logger: Logger,
#         mass_flow_rate: float,
#         solar_irradiance: float,
#         wind_speed: float,
#     ) -> tuple[float | None, float | None]:
#         """
#         Not yet developed.

#         Once developed, this function will calculate the performance of the PV panel.
#         This issue is being tracked: https://github.com/CLOVER-energy/CLOVER/issues/93

#         """

#         raise ProgrammerJudgementFault(
#             ":class:`PVPanel`::calculate_performance",
#             "The calculation of the performance of electrical PV collectors is not yet "
#             "supported.",
#         )


# class HybridPVTPanel(SolarPanel, panel_type=SolarPanelType.PV_T):
#     """
#     Represents a PV-T panel.

#     .. attribute:: electric_model
#         The model(s) of the electric performance of the collector, stored as a mapping
#         between :class:`RegressorType` instances and :class:`Lasso` models.

#     .. attribute:: max_mass_flow_rate
#         The maximum mass-flow rate of heat-transfer fluid through the PV-T collector,
#         measured in litres per hour.

#     .. attribute:: min_mass_flow_rate
#         The minimum mass-flow rate of heat-transfer fluid through the PV-T collector,
#         measured in litres per hour.

#     .. attribute:: pv_layer
#         The PV layer associated with the collector.

#     .. attribute:: thermal_models
#         The model(s) of the thermal performance of the collector, stored as a mapping
#         between :class:`RegressorType` instances and :class:`Lasso` models.

#     .. attribute:: thermal_unit
#         The unit of thermal panel that the panel can output which is being considered,
#         measured in kWth.

#     """

#     def __init__(
#         self,
#         electric_models: dict[RegressorType, Lasso] | None,
#         logger: Logger,
#         solar_inputs: dict[str, Any],
#         solar_panels: list[SolarPanel],
#         thermal_models: dict[RegressorType, Lasso] | None,
#     ) -> None:
#         """
#         Instantiate a :class:`HybridPVTPanel` instance based on the input data.

#         Inputs:
#             - electric_model:
#                 The reduced electrical-efficiency model(s) to use when generating the
#                 electric properties of the collector.
#             - logger:
#                 The logger to use for the run.
#             - solar_inputs:
#                 The solar input data specific to this panel.
#             - solar_panels:
#                 The full set of solar generation data.
#             - thermal_model:
#                 The reduced thermal model (s)to use when generating the thermal
#                 properties of the collector.

#         """

#         # Attempt to extract information about the corresponding PV layer.
#         try:
#             pv_layer = [
#                 panel for panel in solar_panels if panel.name == solar_inputs["pv"]
#             ][0]
#         except IndexError:
#             logger.error(
#                 "Could not find corresponding PV-layer data for layer %s for panel %s.",
#                 solar_inputs["pv"],
#                 solar_inputs[NAME],
#             )
#             raise InputFileError(
#                 "solar generation inputs",
#                 f"PV-layer data for layer {solar_inputs['pv']} could not be found "
#                 + f"whilst processing PV-T panel {solar_inputs[NAME]}.",
#             ) from None

#         if pv_layer.panel_type != SolarPanelType.PV:
#             logger.error(
#                 "%sThe PV layer defined, %s, is not a PVPanel instance.%s",
#                 BColours.fail,
#                 solar_inputs["pv"],
#                 BColours.endc,
#             )
#             raise InputFileError(
#                 "solar generation inputs",
#                 f"PV-layer data for layer {solar_inputs['pv']} is not a valid PV panel.",
#             ) from None

#         if pv_layer.reference_efficiency is None:  # type: ignore [attr-defined]
#             logger.error("PV reference efficiency must be defined if using PV-T.")
#             raise InputFileError(
#                 "solar generation inputs",
#                 "PV reference efficiency must be defined if using PV-T",
#             )
#         if pv_layer.reference_temperature is None:  # type: ignore [attr-defined]
#             logger.error("PV reference temperature must be defined if using PV-T.")
#             raise InputFileError(
#                 "solar generation inputs",
#                 "PV reference temperature must be defined if using PV-T",
#             )
#         if pv_layer.thermal_coefficient is None:  # type: ignore [attr-defined]
#             logger.error("PV thermal coefficient must be defined if using PV-T.")
#             raise InputFileError(
#                 "solar generation inputs",
#                 "PV thermal coefficient must be defined if using PV-T",
#             )

#         if "pv_unit" not in solar_inputs:
#             logger.error("PV unit size must be specified for PV-T panels.")
#             raise InputFileError(
#                 "solar generation inputs",
#                 "PV unit size must be specified when considering PV-T panels.",
#             )

#         # Override any PV-layer params as appropriate
#         pv_layer.pv_unit = solar_inputs["pv_unit"]  # type: ignore [attr-defined]
#         pv_layer.pv_unit_overrided = True  # type: ignore [attr-defined]

#         super().__init__(
#             solar_inputs["azimuthal_orientation"],
#             solar_inputs["lifetime"],
#             solar_inputs[NAME],
#             solar_inputs["tilt"],
#         )

#         self.electric_models = electric_models
#         self.max_mass_flow_rate = solar_inputs["max_mass_flow_rate"]
#         self.min_mass_flow_rate = solar_inputs["min_mass_flow_rate"]
#         self.pv_layer: PVPanel = pv_layer  # type: ignore [assignment]
#         self.thermal_models = thermal_models
#         self.thermal_unit = solar_inputs.get("thermal_unit", None)

#     def __repr__(self) -> str:
#         """
#         Return a nice-looking representation of the panel.

#         Outputs:
#             - A nice-looking representation of the panel.

#         """

#         return (
#             "HybridPVTPanel("
#             + f"azimuthal_orientation={self.azimuthal_orientation}"
#             + f", electric_models defined={self.electric_models is not None}"
#             + f", lifetime={self.lifetime}"
#             + f", max_mass_flow_rate={self.max_mass_flow_rate}"
#             + f", min_mass_flow_rate={self.min_mass_flow_rate}"
#             + f", name={self.name}"
#             + f", pv_unit={self.pv_layer.pv_unit}"
#             + f", reference_efficiency={self.pv_layer.reference_efficiency}"
#             + f", reference_temperature={self.pv_layer.reference_temperature}"
#             + f", thermal_coefficient={self.pv_layer.thermal_coefficient}"
#             + f", thermal_models defined={self.thermal_models is not None}"
#             + f", thermal_unit={self.thermal_unit}"
#             + f", tilt={self.tilt}"
#             + ")"
#         )

#     def __hash__(self) -> int:
#         """
#         Return a unique identifier for the panel.

#         Because the solar panel instances are used for fetching weather data, panels
#         with unique tilt, azimuthal orientation, and tracking, need to be kept separate.

#         These parameters are hence used to determine the "unique" hash for the panel.

#         """

#         return hash(
#             3
#             * (
#                 self.azimuthal_orientation
#                 if self.azimuthal_orientation is not None
#                 else 0
#             )
#             + 540 * (self.tilt if self.tilt is not None else 0)
#         )

#     def __eq__(self, other: Any) -> bool:
#         """Used to determine whether to instances are identical for creating a set."""

#         return (  # type: ignore[no-any-return]
#             self.azimuthal_orientation == other.azimuthal_orientation
#             and self.tilt == other.tilt
#         )

#     def calculate_performance(
#         self,
#         ambient_temperature: float,
#         htf_heat_capacity: float,
#         input_temperature: float,
#         logger: Logger,
#         mass_flow_rate: float,
#         solar_irradiance: float,
#         wind_speed: float,
#     ) -> tuple[float, float]:
#         """
#         Calculates the performance characteristics of the hybrid PV-T collector.

#         The technical PV-T model developed by Benedict Winchester is reduced to a
#         smaller, quick-to-run model which is loaded and utilised here.

#         Inputs:
#             - ambient_temperature:
#                 The ambient temperature, measured in degrees Celsius.
#             - htf_heat_capacity:
#                 The heat capacity of the HTF entering the collector, measured in Joules
#                 per kilogram Kelvin (J/kgK).
#             - input_temperature:
#                 The input temperature of the HTF entering the PV-T collector, measured
#                 in degrees Celsius.
#             - logger:
#                 The :class:`logging.Logger` to use for the run.
#             - mass_flow_rate:
#                 The mass-flow rate of HTF passing through the collector, measured in
#                 kilograms per second.
#             - solar_irradiance:
#                 The solar irradiance incident on the surface of the collector, measured
#                 in Watts per meter squared.
#             - wind_speed:
#                 The wind speed at the collector, measured in meters per second.

#         Outputs:
#             - fractional_electric_performance:
#                 The fractional electric performance defined between 0 (panel is not
#                 operating, i.e., no output) and 1 (panel is operating at full test
#                 potential of reference efficiency under reference irradiance).
#             - output_temperature:
#                 The temperature of the HTF leaving the collector, measured in degrees
#                 Celsius.

#         """

#         if self.electric_models is None or self.thermal_models is None:
#             logger.error(
#                 "%sThe PV-T instance does not have well-defined and loaded models.%s",
#                 BColours.fail,
#                 BColours.endc,
#             )
#             raise ProgrammerJudgementFault(
#                 "pv-t modelling",
#                 "The PV-T instance does not have well-defined and loaded models. This "
#                 "could be due to the files being incorrectly parsed, mishandled, or "
#                 "dropped inadvertently due to internal code flow.",
#             )
#         if self.pv_layer.reference_efficiency is None:
#             logger.error(
#                 "%sThe PV-T output function was called without a reference efficiency "
#                 "being defined for the PV-T panel being considered.%s",
#                 BColours.fail,
#                 BColours.endc,
#             )
#             raise InputFileError(
#                 "solar generation inputs",
#                 "A reference efficiency must be defined for PV-T panels.",
#             )

#         input_data_frame = pd.DataFrame(
#             [
#                 [
#                     ambient_temperature,
#                     input_temperature,
#                     mass_flow_rate,
#                     solar_irradiance,
#                     wind_speed,
#                 ]
#             ]
#         )

#         # Determine which models to use.
#         if solar_irradiance < LOW_IRRADIANCE_THRESHOLD:
#             if input_temperature < LOW_TEMPERATURE_THRESHOLD:
#                 regressor_type: RegressorType = (
#                     RegressorType.LOW_IRRADIANCE_LOW_TEMPERATURE
#                 )
#             else:
#                 regressor_type = RegressorType.LOW_IRRADIANCE_HIGH_TEMPERATURE
#         else:
#             if input_temperature < LOW_TEMPERATURE_THRESHOLD:
#                 regressor_type = RegressorType.STANDARD_IRRADIANCE_LOW_TEMPERATURE
#             else:
#                 regressor_type = RegressorType.STANDARD_IRRADIANCE_HIGH_TEMPERATURE

#         electric_model = self.electric_models[regressor_type]
#         thermal_model = self.thermal_models[regressor_type]

#         # Use the model selected to predict the collector performance.
#         try:
#             electric_efficiency = float(electric_model.predict(input_data_frame))
#         except Exception as e:  # pylint: disable=broad-except
#             logger.error(
#                 "Error attempting to predict electric efficiency of the PV-T collector: %s",
#                 str(e),
#             )
#             raise

#         # Convert the efficiency to a fractional performance.
#         fractional_electric_performance: float = (
#             electric_efficiency / self.pv_layer.reference_efficiency
#         ) * (solar_irradiance / REFERENCE_SOLAR_IRRADIANCE)

#         try:
#             output_temperature = float(thermal_model.predict(input_data_frame))
#         except Exception as e:  # pylint: disable=broad-except
#             logger.error(
#                 "Error attempting to predict electric efficiency of the PV-T collector: %s",
#                 str(e),
#             )
#             raise

#         return fractional_electric_performance, output_temperature


# class SolarThermalPanel(SolarPanel, panel_type=SolarPanelType.SOLAR_THERMAL):
#     """
#     Represents a solar-thermal panel.

#     .. attribute:: area
#         The area of the collector in meters squared, used to calculate the input power
#         to the collector.

#     .. attribute:: max_mass_flow_rate
#         The maximum mass-flow rate of heat-transfer fluid through the PV-T collector,
#         measured in litres per hour.

#     .. attribute:: min_mass_flow_rate
#         The minimum mass-flow rate of heat-transfer fluid through the PV-T collector,
#         measured in litres per hour.

#     .. attribute:: nominal_mass_flow_rate
#         The nominal mass-flow rate of heat-transfer fluid through the PV-T collector,
#         measured in litres per hour.

#     .. attribute:: performance_curve
#         The performance curve for the collector.

#     """

#     def __init__(
#         self,
#         performance_curve: PerformanceCurve,
#         solar_inputs: dict[str, Any],
#     ) -> None:
#         """
#         Instantiate a :class:`SolarThermalPanel` instance based on the input data.

#         Inputs:
#             - performance_curve:
#                 The :class:`PeformanceCurve` associated with this panel.
#             - solar_inputs:
#                 The solar input data specific to this panel.

#         """

#         super().__init__(
#             solar_inputs["azimuthal_orientation"],
#             solar_inputs["lifetime"],
#             solar_inputs[NAME],
#             solar_inputs["tilt"],
#         )

#         self.area = solar_inputs["area"]
#         self.max_mass_flow_rate = solar_inputs["max_mass_flow_rate"]
#         self.min_mass_flow_rate = solar_inputs["min_mass_flow_rate"]
#         self.nominal_mass_flow_rate = solar_inputs["nominal_mass_flow_rate"]
#         self.performance_curve = performance_curve

#     def __repr__(self) -> str:
#         """
#         Return a nice-looking representation of the panel.

#         Outputs:
#             - A nice-looking representation of the panel.

#         """

#         return (
#             "SolarThermalPanel("
#             + f"area={self.area}"
#             + f", azimuthal_orientation={self.azimuthal_orientation}"
#             + f", lifetime={self.lifetime}"
#             + f", max_mass_flow_rate={self.max_mass_flow_rate}"
#             + f", min_mass_flow_rate={self.min_mass_flow_rate}"
#             + f", name={self.name}"
#             + f", nominal_mass_flow_rate={self.nominal_mass_flow_rate}"
#             + f", performance_curve={str(self.performance_curve)}"
#             + f", tilt={self.tilt}"
#             + ")"
#         )

#     def calculate_performance(
#         self,
#         ambient_temperature: float,
#         htf_heat_capacity: float,
#         input_temperature: float,
#         logger: Logger,
#         mass_flow_rate: float,
#         solar_irradiance: float,
#         wind_speed: float,
#     ) -> tuple[float | None, float | None]:
#         """
#         Calculates the performance characteristics of the solar-thermal collector.

#         Each collector has a characteristic performance curve, which is related to the
#         efficiency of the collector by a simple equation:

#             eta = eta_0
#                 + c_1 * (T_c - T_amb) / G
#                 + c_2 * (T_c - T_amb) ** 2 / G

#         where `eta_0`, `c_1` and `c_2` give the zeroth-, first- and second-order
#         coefficients which characterise the performance of the collector, `T_c` is the
#         average temperature of the collector and `T_a` the ambient temperature, both
#         measured in either degrees Kelvin or Celsius, but the same unit for each, and
#         `G` is the solar irradiance, measured in Watts per meter squared. The attributes
#         `eta_0`, `c_1` and `c_2` are inherent properties of the collector and are
#         contained within the `performance_curve` attribute.

#         This equation can be rearranged by expressing the efficiency as the energy
#         gained by the heat-transfer fluid within the collector as a fraction of the
#         total energy incident on the collector:

#             eta = m_htf * c_htf * (T_out - T_in) / (A * G)

#         where `T_out` and `T_in` give the output and input HTF temperatures
#         respectively, and `m_htf` and `c_htf` give the mass-flow rate and specific heat
#         capacityof the HTF through the collector. Combining these two yields

#             0 = 4 * eta_0 * A * G                   \\ = c = zeroth_order_coefficient
#               + 4 * m_htf * c_htf * T_in            |
#               + 2 * c_1 * A * (T_in - T_amb)        |
#               + c_2 * A * (T_in - T_amb) ** 2       /
#               + (                                   \\ = b = first_order_coefficient
#                 - 4 * m_htf * c_htf                 |
#                 + 2 * c_1 * A                       |
#                 + 2 * c_2 * A * (T_in - T_amb)      /
#               ) * T_out
#               + (                                   \\ = a = second_order_coefficient
#                 4 * eta_0 * A * G                   |
#                 + 4 * m_htf * c_htf * T_in          |
#                 + 2 * c_1 * A * (T_in - T_amb)      |
#                 + c_2 * A * (T_in - T_amb) ** 2     /
#               ) * T_out ** 2

#         which can then be solved quadratically to determine the output temperature of
#         HTF leaving the collector.

#         Inputs:
#             - ambient_temperature:
#                 The ambient temperature, measured in degrees Celsius.
#             - htf_heat_capacity:
#                 The heat capacity of the HTF entering the collector, measured in Joules
#                 per kilogram Kelvin (J/kgK).
#             - input_temperature:
#                 The input temperature of the HTF entering the PV-T collector, measured
#                 in degrees Celsius.
#             - logger:
#                 The :class:`logging.Logger` to use for the run.
#             - mass_flow_rate:
#                 The mass-flow rate of HTF passing through the collector, measured in
#                 kilograms per hour.
#             - solar_irradiance:
#                 The solar irradiance incident on the surface of the collector, measured
#                 in kilo Watts per meter squared.
#             - wind_speed:
#                 The wind speed passing over the collector, measured in meters per
#                 second. This parameter is not used, but is defined in the base function.

#         Outputs:
#             - fractional_electric_performance:
#                 The fractional electric performance defined between 0 (panel is not
#                 operating, i.e., no output) and 1 (panel is operating at full test
#                 potential of reference efficiency under reference irradiance).
#             - output_temperature:
#                 The temperature of the HTF leaving the collector, measured in degrees
#                 Celsius.

#         Raises:
#             - FlowRateError:
#                 Raised if the flow rates are mismatched.

#         """

#         # Raise a flow-rate error if the flow rate is insufficient.
#         if (
#             mass_flow_rate < self.min_mass_flow_rate
#             or mass_flow_rate > self.max_mass_flow_rate
#         ):
#             raise FlowRateError(
#                 self.name,
#                 f"Flow rate of {mass_flow_rate:.2f} is out of bounds, range is "
#                 + f"{self.min_mass_flow_rate:.2f} to {self.max_mass_flow_rate:.2f} litres/hour.",
#             )

#         # FIXME: Check units on temperatures here.
#         ambient_temperature += ZERO_CELCIUS_OFFSET
#         input_temperature += ZERO_CELCIUS_OFFSET
#         mass_flow_rate /= 3600  # [s/hour]
#         solar_irradiance *= 1000

#         # Compute the various terms of the equation
#         a: float = self.performance_curve.c_2 * self.area

#         b: float = (
#             +2 * self.performance_curve.c_1 * self.area
#             + 2
#             * self.performance_curve.c_2
#             * self.area
#             * (input_temperature - 2 * ambient_temperature)
#             - 4 * mass_flow_rate * htf_heat_capacity
#         )

#         c: float = (
#             4 * self.performance_curve.eta_0 * self.area * solar_irradiance
#             + 4 * mass_flow_rate * htf_heat_capacity * input_temperature
#             + 2
#             * self.performance_curve.c_1
#             * self.area
#             * (input_temperature - 2 * ambient_temperature)
#             + self.performance_curve.c_2
#             * self.area
#             * (input_temperature - 2 * ambient_temperature) ** 2
#         )

#         # Use numpy or Pandas to solve the quadratic to determine the performance of
#         # the collector
#         positive_root: float = (  # pylint: disable=unused-variable
#             -b + math.sqrt(b**2 - 4 * a * c)
#         ) / (2 * a) - ZERO_CELCIUS_OFFSET
#         negative_root: float = (-b - math.sqrt(b**2 - 4 * a * c)) / (
#             2 * a
#         ) - ZERO_CELCIUS_OFFSET

#         return None, negative_root

#     @classmethod
#     def from_dict(
#         cls,
#         logger: Logger,
#         solar_inputs: dict[str, Any],
#     ) -> Any:
#         """
#         Instantiate a :class:`SolarThermalPanel` instance based on the input data.

#         Inputs:
#             - logger:
#                 The :class:`logging.Logger` to use for the run.
#             - solar_inputs:
#                 The solar input data specific to this panel.

#         """

#         logger.info("Attempting to create SolarThermalPanel from solar input data.")

#         try:
#             performance_curve_inputs = solar_inputs["performance_curve"]
#         except KeyError:
#             logger.error(
#                 "%sNo performance curve defined for solar-thermal panel '%s'.%s",
#                 BColours.fail,
#                 solar_inputs["name"],
#                 BColours.endc,
#             )
#             raise InputFileError(
#                 "solar generation inputs",
#                 f"Solar thermal panel {solar_inputs['name']} is missing a performance curve.",
#             ) from None

#         try:
#             performance_curve = PerformanceCurve(
#                 performance_curve_inputs["zeroth_order"],
#                 performance_curve_inputs["first_order"],
#                 performance_curve_inputs["second_order"],
#             )
#         except KeyError as e:
#             logger.error(
#                 "%sMissing performance curve input(s): %s%s",
#                 BColours.fail,
#                 str(e),
#                 BColours.endc,
#             )
#             raise

#         return cls(performance_curve, solar_inputs)


class SolarPanel(ABC):  # pylint: disable=too-few-public-methods
    """
    Represents a solar panel being considered.

    .. attribute:: area
        The area of the collector in meters squared, used to calculate the input power
        to the collector.

    .. attribute:: azimuthal_orientation
        The azimuthal orientation of the panel, defined in degrees from North.

    .. attribute:: lifetime
        The lifetime of the panel in years.

    .. attribute:: name
        The name of the panel being considered.

    .. attribite:: panel_type
        The type of panel being considered.

    .. attribute:: tilt
        The angle between the panel and the horizontal.

    .. attribute:: tracking
        The :class:`Tracking` instance describing the tracking state of the collector.

    """

    panel_type: SolarPanelType

    def __init__(
        self,
        area: float,
        azimuthal_orientation: float,
        land_use: float,
        lifetime: int,
        name: str,
        tilt: float,
        tracking: Tracking,
    ) -> None:
        """
        Instantiate a :class:`SolarPanel` instance.

        Inputs:
            - area:
                The surface area of the panel in meters squared.
            - azimuthal_orientation:
                The azimuthal orientation of the :class:`SolarPanel`.
            - land_use:
                The land occupied by the panel in meters squared.
            - lifetime:
                The lifetime of the :class:`SolarPanel` in years.
            - name:
                The name to assign to the :class:`SolarPanel` in order to uniquely
                identify it.
            - tilt:
                The tilt of the panel in degrees above the horizontal.

        """

        self.area: float = area
        self.azimuthal_orientation: float = azimuthal_orientation
        self.land_use: float = land_use
        self.lifetime: int = lifetime
        self.name: str = name
        self.tilt: float = tilt
        self.tracking: Tracking = tracking

    def __init_subclass__(cls, panel_type: SolarPanelType) -> None:
        """
        The init_subclass hook, run on instantiation of the :class:`SolarPanel`.

        Inputs:
            - panel_type:
                The type of panel being considered.

        Outputs:
            An instantiated :class:`SolarPanel` instance.

        """

        cls.panel_type = panel_type

        return super().__init_subclass__()

    @abstractmethod
    def calculate_performance(
        self,
        *,
        ambient_temperature: float,
        htf_heat_capacity: float | None,
        input_temperature: float | None,
        logger: Logger,
        mass_flow_rate: float | None,
        solar_irradiance: float,
        wind_speed: float | None,
    ) -> tuple[float | None, float | None, float | None, float | None,]:
        """
        Abstract method for calculation of collector performance.

        Inputs:
            - ambient_temperature:
                The ambient temperature, measured in degrees Kelvin.
            - htf_heat_capacity:
                The heat capacity of the HTF entering the collector, measured in Joules
                per kilogram Kelvin (J/kgK).
            - input_temperature:
                The input temperature of the HTF entering the collector, measured in
                in degrees Kelvin.
            - logger:
                The :class:`logging.Logger` to use for the run.
            - mass_flow_rate:
                The mass-flow rate of HTF passing through the collector, measured in
                kilograms per second.
            - solar_irradiance:
                The solar irradiance incident on the surface of the collector, measured
                in Watts per meter squared.
            - wind_speed:
                The wind speed in meters per second.

        Outputs:
            - electrical_efficiency:
                The electrical efficiency of the PV panel.
            - output_temperature:
                The output temperature of the HTF leaving the collector.
            - reduced_temperature:
                The reduced temperature of the collector.
            - thermal_efficiency:
                The thermal efficiency of the collector.

        """

    @classmethod
    @abstractmethod
    def from_dict(
        cls,
        logger: Logger,
        solar_inputs: dict[str, Any],
    ) -> Any:
        """
        Instantiate a :class:`SolarPanel` instance based on the input data.

        Inputs:
            - logger:
                The :class:`logging.Logger` to use for the run.
            - solar_inputs:
                The solar input data specific to this panel.

        """


class PVPanel(SolarPanel, panel_type=SolarPanelType.PV):
    """
    Represents a photovoltaic panel.

    .. attribute:: absorptivity
        The absorptivity of the panel, defined between 0 (none of the incident light is
        absorbed by the panel) to 1 (all of the incident light is absorbed by the
        panel).

    .. attribute:: emissivity
        The emissivity of the panel, defined between 0 (none of the incident light on
        the panel is emitted) to 1 (the panel radiates all incoming light).

    .. attribute:: pv_unit
        The unit of PV power being considered, defaulting to 1 kWp.

    .. attribute:: reference_efficiency
        The efficiency of the PV layer under standard test conditions.

    .. attribute:: reference_temperature
        The reference temperature of the PV layer of the panel, measured in degrees
        Kelvin.

    .. attribute:: thermal_coefficient
        The thermal coefficient of performance of the PV layer of the panel, measured in
        kelvin^(-1).

    """

    def __init__(
        self,
        absorptivity: float,
        area: float,
        azimuthal_orientation: float,
        emissivity: float,
        land_use: float,
        lifetime: int,
        name: str,
        pv_unit: float,
        reference_efficiency: float,
        reference_temperature: float,
        thermal_coefficient: float,
        tilt: float | None,
        tracking: Tracking,
    ) -> None:
        """
        Instantiate a :class:`PVPanel` instance.

        Inputs:
            - absorptivity:
                The absorptivity of the panel.
            - area:
                The surface area of the panel in meters squared.
            - azimuthal_orientation:
                The azimuthal orientation of the :class:`SolarPanel`.
            - emissivity:
                The emissivity of the panel.
            - land_use:
                The land occupied by the panel in meters squared.
            - lifetime:
                The lifetime of the :class:`SolarPanel` in years.
            - name:
                The name to assign to the :class:`PVPanel` in order to uniquely identify
                it.
            - pv_unit:
                The output power, in Watts, of the PV layer of the panel per unit panel
                installed.
            - reference_efficiency:
                The reference efficiency of the panel, if required, otherwise `None`.
            - reference_temperature:
                The temperature, in degrees Celsius, at which the reference efficiency
                is defined, if required, otherwise `None`.
            - thermal_coefficient:
                The thermal coefficient of the PV layer of the panel, if required,
                otherwise `None`.
            - tilt:
                The tilt of the panel in degrees above the horizontal.

        """

        super().__init__(
            area,
            azimuthal_orientation,
            land_use,
            lifetime,
            name,
            tilt,
            tracking,
        )

        self.absorptivity = absorptivity
        self.emissivity = emissivity
        self.pv_unit: float = pv_unit
        self.reference_efficiency: float = reference_efficiency
        self._reference_temperature: float = reference_temperature
        self.thermal_coefficient: float = thermal_coefficient

    @property
    def reference_temperature(self) -> float:
        """
        Return the reference temperature in degrees Kelvin.

        Outputs:
            The reference temperature in degrees Kelvin.

        """

        return self._reference_temperature + ZERO_CELCIUS_OFFSET

    def __repr__(self) -> str:
        """
        Return a nice-looking representation of the panel.

        Outputs:
            - A nice-looking representation of the panel.

        """

        return (
            "PVPanel("
            + f"name={self.name}"
            + f", area={self.area:.2g}"
            + f", reference_efficiency={self.reference_efficiency:.2g}"
            + f", reference_temperature={self.reference_temperature:.2g} K"
            + f" ({self._reference_temperature:.2g} degC"
            + f", thermal_coefficient={self.thermal_coefficient:.2g}"
            + ")"
        )

    @classmethod
    def from_dict(cls, logger: Logger, solar_inputs: dict[str, Any]) -> Any:
        """
        Instantiate a :class:`PVPanel` instance based on the input data.

        Inputs:
            - logger:
                The logger to use for the run.
            - solar_inputs:
                The solar input data for the panel.

        Outputs:
            A :class:`PVPanel` instance.

        """

        logger.debug("Attempting to create PVPanel from solar input data.")
        try:
            assert solar_inputs.pop("type") == SolarPanelType.PV.value
        except KeyError:
            pass

        tracking: Tracking = Tracking.from_text(
            logger, solar_inputs.get("tracking", _DEFAULT_TRACKING)
        )

        if tracking == Tracking.FIXED:
            azimuthal_orientation: float | None = solar_inputs["azimuthal_orientation"]
        else:
            azimuthal_orientation = None

        if tracking != Tracking.DUAL_AXIS:
            tilt: float | None = solar_inputs["tilt"]
        else:
            tilt = None

        return cls(
            solar_inputs.get("absorptivity", 1),
            (area := solar_inputs.get("area", 1)),
            azimuthal_orientation,
            solar_inputs.get("emissivity", 1),
            solar_inputs.get("land_use", area),
            solar_inputs.get("lifetime", 30),
            solar_inputs["name"],
            solar_inputs.get("pv_unit", DEFAULT_PV_UNIT),
            solar_inputs.get("reference_efficiency", 0.125),
            solar_inputs.get("reference_temperature", 25),
            solar_inputs.get("thermal_coefficient", 0.005),
            tilt,
            tracking,
        )

    # def _average_module_temperature(
    #     self,
    #     ambient_temperature: float,
    #     logger: Logger,
    #     solar_irradiance: float,
    #     wind_speed: float,
    # ) -> float:
    #     """
    #     Calculate the temperature of the PV module in Kelvin.

    #     Uses a heat-balance calculation iteratively to solve for the average temperature of
    #     the PV module:
    #         0W = a_pv G (1 - eta_el)
    #              + h_air (T_air - T_pv)
    #              + e' sigma (T_sky - Tpv),
    #         where:
    #             a_pv    is the absorptivity of the collector,
    #             G       the solar irradiance in Watts per meter squared,
    #             eta_el  the electrical efficiency of the collector,
    #             h_air   the conductive heat-transfer coefficient between the collector
    #                     and the surrounding air,
    #             e'      the effective emissivity made linear by combining temperature
    #                     terms of higher orders,
    #         and sigma   is the Stefan-Boltzman coefficient.

    #     This can be rearranged to the form employed here:
    #         T_pv = (
    #             a_pv G (1 - eta_ref (1 + beta T_ref))
    #             + h_air T_amb
    #             + e' sigma T_sky
    #         ) / (
    #             e' sigma + h_air - a_pv beta eta_ref G
    #         )
    #     which is linear in temperature and can be solved iteratively as the value of e'
    #     contains higher-order terms in temperature.

    #     Inputs:
    #         - ambient_temperature:
    #             The ambient temperature, measured in degrees Kelvin.
    #         - logger:
    #             The logger to use for the run.
    #         - solar_irradiance:
    #             The solar irradiance incident on the collector, measured in Watts per
    #             meter squared.
    #         - wind_speed:
    #             The wind speed in meters per second.

    #     Outputs:
    #         The average temperature of the PV module installed.

    #     """

    #     # Calculate variable values which remain constant throughout the iteration
    #     sky_temperature: float = _sky_temperature(ambient_temperature)

    #     # Setup inputs for the iterative loop
    #     best_guess_average_temperature: float = ambient_temperature
    #     solution_found: bool = False

    #     # Loop through until a solution is found
    #     logger.debug("Beginning iterative calculation for the PV module temperature.")
    #     while not solution_found:
    #         # Compute the necessary coefficients
    #         radiation_to_sky_coefficient = _radiation_to_sky_coefficient(
    #             self.emissivity, best_guess_average_temperature, sky_temperature
    #         )

    #         # Calculate the average temperature of the collector
    #         average_temperature: float = (
    #             (self.absorptivity * solar_irradiance)
    #             * (
    #                 1
    #                 - self.reference_efficiency
    #                 * (1 + self.thermal_coefficient * self.reference_temperature)
    #             )
    #             + _conductive_air_heat_transfer_coefficient(wind_speed)
    #             * ambient_temperature
    #             + radiation_to_sky_coefficient * sky_temperature
    #         ) / (
    #             radiation_to_sky_coefficient
    #             + _conductive_air_heat_transfer_coefficient(wind_speed)
    #             - self.absorptivity
    #             * self.thermal_coefficient
    #             * self.reference_efficiency
    #             * solar_irradiance
    #         )

    #         # Break if this average temperature is within the required precision.
    #         if (
    #             abs(best_guess_average_temperature - average_temperature)
    #             < TEMPERATURE_PRECISION
    #         ):
    #             solution_found = True
    #             logger.debug(
    #                 "Solution for PV-module temperature of %s found, returning.",
    #                 average_temperature,
    #             )

    #         best_guess_average_temperature = average_temperature
    #         logger.debug(
    #             "No solution found yet, re-iterating. Best guess: %s",
    #             best_guess_average_temperature,
    #         )

    #     return average_temperature

    def calculate_performance(
        self,
        ambient_temperature: float,
        htf_heat_capacity: float,
        input_temperature: float,
        logger: Logger,
        mass_flow_rate: float,
        solar_irradiance: float,
        wind_speed: float,
    ) -> tuple[float | None, float | None]:
        """
        Not yet developed.

        Once developed, this function will calculate the performance of the PV panel.
        This issue is being tracked: https://github.com/CLOVER-energy/CLOVER/issues/93

        """

        raise ProgrammerJudgementFault(
            ":class:`PVPanel`::calculate_performance",
            "The calculation of the performance of electrical PV collectors is not yet "
            "supported.",
        )


class HybridPVTPanel(SolarPanel, panel_type=SolarPanelType.PV_T):
    """
    Represents a PV-T panel.

    .. attribute:: electric_performance_curve:
        The electrical performance curve of the panel.

    .. attribute:: max_mass_flow_rate
        The maximum mass-flow rate of heat-transfer fluid through the PV-T collector,
        measured in litres per hour.

    .. attribute:: min_mass_flow_rate
        The minimum mass-flow rate of heat-transfer fluid through the PV-T collector,
        measured in litres per hour.

    .. attribute:: thermal_performance_curve
        The thermal performance curve of the panel.

    """

    def __init__(
        self,
        electric_performance_curve: PerformanceCurve | None,
        logger: Logger,
        pv_module_characteristics: PVModuleCharacteristics,
        solar_inputs: dict[str, Any],
        thermal_performance_curve: PerformanceCurve,
    ) -> None:
        """
        Instantiate a :class:`HybridPVTPanel` instance based on the input data.

        Inputs:
            - electric_performance_curve:
                The electric performance curve associated with the panel.
            - logger:
                The logger to use for the run.
            - pv_module_characteristics:
                The characteristics of the PV module which is part of the PV-T
                collector.
            - solar_inputs:
                The solar input data specific to this panel.
            - thermal_performance_curve:
                The thermal performance curve associated with the panel.

        """

        super().__init__(
            solar_inputs["area"],
            solar_inputs["azimuthal_orientation"],
            solar_inputs["land_use"],
            solar_inputs["lifetime"],
            solar_inputs["name"],
            solar_inputs["tilt"],
            Tracking(solar_inputs.get("tracking", 0)),
        )

        self.electric_performance_curve: PerformanceCurve | None = (
            electric_performance_curve
        )
        self._max_mass_flow_rate: float = solar_inputs[MAX_MASS_FLOW_RATE]
        self._min_mass_flow_rate: float = solar_inputs[MIN_MASS_FLOW_RATE]
        self.pv_module_characteristics: PVModuleCharacteristics = (
            pv_module_characteristics
        )
        self.thermal_performance_curve: PerformanceCurve = thermal_performance_curve

    @property
    def max_mass_flow_rate(self) -> float | None:
        """
        Return the maximum mass flow rate in kg/s.

        Outputs:
            The maximum mass flow rate of HTF through the collectors in kg/s.

        """

        return (
            self._max_mass_flow_rate / 3600
            if self._max_mass_flow_rate is not None
            else None
        )

    @property
    def min_mass_flow_rate(self) -> float:
        """
        Return the minimum mass flow rate in kg/s.

        Outputs:
            The minimum mass flow rate of HTF through the collectors in kg/s.

        """

        return float(
            self._min_mass_flow_rate / 3600
            if self._min_mass_flow_rate is not None
            else 0
        )

    @property
    def pv_unit(self) -> float:
        """
        Placeholder to return the PV unit of the Hybrid PV-T panel.

        """

        # return self.area * self.electric_performance_curve.eta_0 * REFERENCE_SOLAR_IRRADIANCE * self.pv_module_characteristics.nominal_power

        return self.pv_module_characteristics.nominal_power

    def __repr__(self) -> str:
        """
        Return a nice-looking representation of the panel.

        Outputs:
            - A nice-looking representation of the panel.

        """

        return (
            "HybridPVTPanel("
            + f"name={self.name}"
            + (
                (
                    f", max_mass_flow_rate={self.max_mass_flow_rate:.2g} kg/s"
                    + f" ({self._max_mass_flow_rate:.2g} l/h)"
                )
                if self.max_mass_flow_rate is not None
                else ""
            )
            + (
                f", min_mass_flow_rate={self.min_mass_flow_rate:.2g} kg/s"
                + f" ({self._min_mass_flow_rate:.2g} l/h)"
            )
            + ")"
        )

    @classmethod
    def from_dict(
        cls,
        logger: Logger,
        solar_inputs: dict[str, Any],
    ) -> Any:
        """
        Instantiate a :class:`HybridPVTPanel` instance based on the input data.

        Inputs:
            - logger:
                The :class:`logging.Logger` to use for the run.
            - solar_inputs:
                The solar input data specific to this panel.

        """

        logger.debug("Attempting to create a HybridPVTPanel from solar input data.")

        try:
            thermal_performance_inputs = solar_inputs[THERMAL_PERFORMANCE_CURVE]
        except KeyError:
            logger.error(
                "No performance curve defined for solar-thermal panel '%s'.",
                solar_inputs["name"],
            )
            raise InputFileError(
                "solar generation inputs",
                f"Solar thermal panel {solar_inputs.get(NAME, '<not supplied>')} "
                "is missing a thermal performance curve.",
            ) from None

        try:
            thermal_performance_curve = PerformanceCurve(
                thermal_performance_inputs[ZEROTH_ORDER],
                thermal_performance_inputs[FIRST_ORDER],
                thermal_performance_inputs[SECOND_ORDER],
            )
        except KeyError as exception:
            logger.error(
                "Missing thermal performance curve input(s): %s",
                str(exception),
            )
            raise

        if ELECTRIC_PERFORMANCE_CURVE in solar_inputs:
            electric_performance_inputs = solar_inputs[ELECTRIC_PERFORMANCE_CURVE]
            try:
                electric_performance_curve: PerformanceCurve | None = PerformanceCurve(
                    electric_performance_inputs[ZEROTH_ORDER],
                    electric_performance_inputs[FIRST_ORDER],
                    electric_performance_inputs[SECOND_ORDER],
                )
            except KeyError as exception:
                logger.info(
                    "Missing electric performance curve input(s): %s",
                    str(exception),
                )
                electric_performance_curve = None
        else:
            logger.info(
                "Missing electric performance curve input(s) for panel %s.",
                solar_inputs[NAME],
            )
            electric_performance_curve = None

        if PV_MODULE_CHARACTERISTICS in solar_inputs:
            pv_module_characteristics_inputs = solar_inputs[PV_MODULE_CHARACTERISTICS]
            try:
                pv_module_characteristics: PVModuleCharacteristics = (
                    PVModuleCharacteristics(
                        pv_module_characteristics_inputs[NOMINAL_POWER],
                        pv_module_characteristics_inputs[REFERENCE_EFFICIENCY],
                        pv_module_characteristics_inputs[REFERENCE_TEMPERATURE],
                        pv_module_characteristics_inputs[THERMAL_COEFFICIENT],
                    )
                )
            except KeyError as exception:
                logger.error(
                    "Missing module characteristics: %s",
                    str(exception),
                )
                raise
        else:
            logger.error(
                "No module characteristics defined for PV-T panel '%s'.",
                (name := solar_inputs["name"]),
            )
            raise InputFileError(
                "solar inputs",
                f"No PV module characteristics defined for panel {name}.",
            )

        return cls(
            electric_performance_curve,
            logger,
            pv_module_characteristics,
            solar_inputs,
            thermal_performance_curve,
        )

    def calculate_performance(
        self,
        ambient_temperature: float,
        logger: Logger,
        solar_irradiance: float,
        htf_heat_capacity: float | None,
        input_temperature: float | None,
        mass_flow_rate: float | None,
        wind_speed: float | None = None,
    ) -> tuple[float | None, float | None, float | None, float | None,]:
        """
        Calculates the performance characteristics of the hybrid PV-T collector.

        The technical PV-T model developed by Benedict Winchester is reduced to a
        smaller, quick-to-run model which is loaded and utilised here.

        Inputs:
            - ambient_temperature:
                The ambient temperature, measured in degrees Kelvin.
            - htf_heat_capacity:
                The heat capacity of the HTF entering the collector, measured in Joules
                per kilogram Kelvin (J/kgK).
            - input_temperature:
                The input temperature of the HTF entering the PV-T collector, measured
                in degrees Kelvin.
            - logger:
                The :class:`logging.Logger` to use for the run.
            - mass_flow_rate:
                The mass-flow rate of HTF passing through the collector, measured in
                kilograms per second.
            - solar_irradiance:
                The solar irradiance incident on the surface of the collector, measured
                in Watts per meter squared.
            - wind_speed:
                The wind speed in meters per second.

        Outputs:
            - electrical_efficiency:
                The electrical efficiency of the PV panel.
            - output_temperature:
                The output temperature of the HTF leaving the collector, measured in degrees
                Kelvin.
            - reduced_temperature:
                The reduced temperature of the collector.
            - thermal_efficiency:
                The thermal efficiency of the collector.

        """

        if mass_flow_rate is None:
            logger.error(
                "Cannot calculate solar-thermal collector performance with no mass flow "
                "rate provided."
            )
            raise ProgrammerJudgementFault(
                "solar:HybridPVTPanel:calculate_performance",
                "Cannot calculate performance of solar-thermal collector if no mass-"
                "flow rate provided.",
            )

        # Raise a flow-rate error if the flow rate is insufficient.
        if (
            mass_flow_rate < self.min_mass_flow_rate
            if self.min_mass_flow_rate is not None
            else False
        ) or (
            mass_flow_rate > self.max_mass_flow_rate
            if self.max_mass_flow_rate is not None
            else False
        ):
            logger.debug(
                "Flow rate of %s kg/s is out of bounds, range is %s to %s kilograms/second.",
                mass_flow_rate,
                self.min_mass_flow_rate,
                self.max_mass_flow_rate,
            )
            raise FlowRateError(
                self.name,
                f"Flow rate of {mass_flow_rate:.2g} kg/s is out of bounds, range is "
                + f"{self.min_mass_flow_rate:.2g} to {self.max_mass_flow_rate:.2g} "
                "kilograms/second.",
            )

        if input_temperature is None:
            logger.error(
                "Cannot calculate solar-thermal collector performance with no input "
                "temperature provided."
            )
            raise ProgrammerJudgementFault(
                "solar:HybridPVTPanel:calculate_performance",
                "Cannot calculate performance of solar-thermal collector if no input "
                "temperature provided.",
            )

        _, negative_root = _thermal_performance(
            ambient_temperature,
            self.area,
            htf_heat_capacity,
            input_temperature,
            mass_flow_rate,
            self.thermal_performance_curve,
            solar_irradiance,
        )

        # Compute temperature quantities.
        average_temperature = 0.5 * (negative_root + input_temperature)
        reduced_collector_temperature = reduced_temperature(
            ambient_temperature, average_temperature, solar_irradiance
        )

        # If the reduced temperature is None, performance cannot be computed.
        if reduced_collector_temperature is None:
            return (None, negative_root, None, None)

        # Compute the efficiencies of the collector.
        if self.electric_performance_curve is not None:
            electrical_efficiency = (
                self.electric_performance_curve.eta_0
                + self.electric_performance_curve.c_1 * reduced_collector_temperature
                + self.electric_performance_curve.c_2 * reduced_collector_temperature
            )
        elif self.pv_module_characteristics is not None:
            electrical_efficiency = (
                self.pv_module_characteristics.reference_efficiency
                * (
                    1
                    - self.pv_module_characteristics.thermal_coefficient
                    * (
                        average_temperature
                        - self.pv_module_characteristics.reference_temperature
                    )
                )
            )
        else:
            raise Exception(
                f"PV-T collector {self.name} had neither PV module characteristics or "
                "an electric performance curve."
            )

        thermal_efficiency = (
            self.thermal_performance_curve.eta_0
            + self.thermal_performance_curve.c_1 * reduced_collector_temperature
            + self.thermal_performance_curve.c_2
            * solar_irradiance
            * reduced_collector_temperature**2
        )

        # Return the output information.
        return (
            electrical_efficiency,
            negative_root,
            reduced_collector_temperature,
            thermal_efficiency,
        )


class SolarThermalPanel(SolarPanel, panel_type=SolarPanelType.SOLAR_THERMAL):
    """
    Represents a solar-thermal panel.

    .. attribute:: max_mass_flow_rate
        The maximum mass-flow rate of heat-transfer fluid through the PV-T collector,
        measured in litres per hour.

    .. attribute:: min_mass_flow_rate
        The minimum mass-flow rate of heat-transfer fluid through the PV-T collector,
        measured in litres per hour.

    .. attribute:: nominal_mass_flow_rate
        The nominal mass-flow rate of heat-transfer fluid through the PV-T collector,
        measured in litres per hour.

    .. attribute:: stagnation_temperature
        The stagnation temperature of the collector. This is the temperature at which
        the heat losses from the collector are equal to the potential heat gain from any
        incident solar irradiance. At temperatures beyond this value, the collector can
        only output heat-transfer fluid (HTF) at its stagnation temperature.

    .. attribute:: thermal_performance_curve
        The performance curve for the collector.

    """

    def __init__(
        self,
        performance_curve: PerformanceCurve,
        solar_inputs: dict[str, Any],
    ) -> None:
        """
        Instantiate a :class:`SolarThermalPanel` instance based on the input data.

        Inputs:
            - performance_curve:
                The :class:`PeformanceCurve` associated with this panel.
            - solar_inputs:
                The solar input data specific to this panel.

        """

        super().__init__(
            solar_inputs["area"],
            solar_inputs["azimuthal_orientation"],
            solar_inputs["land_use"],
            solar_inputs["lifetime"],
            solar_inputs["name"],
            solar_inputs["tilt"],
            Tracking(solar_inputs.get("tracking", 0)),
        )

        self._max_mass_flow_rate: float = solar_inputs[MAX_MASS_FLOW_RATE]
        self._min_mass_flow_rate: float = solar_inputs.get(MIN_MASS_FLOW_RATE, 0)
        self._nominal_mass_flow_rate: float | None = solar_inputs.get(
            NOMINAL_MASS_FLOW_RATE, None
        )
        self._stagnation_temperature: float = solar_inputs[STAGNATION_TEMPERATURE]
        self.thermal_performance_curve: PerformanceCurve = performance_curve

    @property
    def max_mass_flow_rate(self) -> float:
        """
        Return the maximum mass flow rate in kg/s.

        Outputs:
            The maximum mass flow rate of HTF through the collectors in kg/s.

        """

        return (
            self._max_mass_flow_rate / 3600
            if self._max_mass_flow_rate is not None
            else None
        )

    @property
    def min_mass_flow_rate(self) -> float:
        """
        Return the minimum mass flow rate in kg/s.

        Outputs:
            The minimum mass flow rate of HTF through the collectors in kg/s.

        """

        return (
            self._min_mass_flow_rate / 3600
            if self._min_mass_flow_rate is not None
            else None
        )

    @property
    def nominal_mass_flow_rate(self) -> float | None:
        """
        Return the nominal mass flow rate in kg/s or `None` if no value to convert.

        Outputs:
            The nominal mass flow rate of HTF through the collectors in kg/s.

        """

        return (
            self._nominal_mass_flow_rate / 3600
            if self._nominal_mass_flow_rate is not None
            else None
        )

    @property
    def pv_unit(self) -> float:
        """
        Placeholder to return the PV unit of the Hybrid PV-T panel.

        """

        return 0

    def __repr__(self) -> str:
        """
        Return a nice-looking representation of the panel.

        Outputs:
            - A nice-looking representation of the panel.

        """

        return (
            "SolarThermalPanel("
            + f"area={self.area}"
            + (
                (
                    f", max_mass_flow_rate={self.max_mass_flow_rate:.2g} kg/s"
                    + f" ({self._max_mass_flow_rate:.2g} l/h)"
                )
                if self.max_mass_flow_rate is not None
                else ""
            )
            + (
                (
                    f", min_mass_flow_rate={self.min_mass_flow_rate:.2g} kg/s"
                    + f" ({self._min_mass_flow_rate:.2g} l/h)"
                )
                if self.min_mass_flow_rate is not None
                else ""
            )
            + f", name={self.name}"
            + (
                (
                    f", nominal_mass_flow_rate={self.nominal_mass_flow_rate:.2g} kg/s"
                    + f" ({self._nominal_mass_flow_rate:.2g} l/h)"
                )
                if self.nominal_mass_flow_rate is not None
                else ""
            )
            + ")"
        )

    @property
    def stagnation_temperature(self) -> float:
        """
        Return the stagnation temperature of the collector in degrees Kelvin.

        Outputs:
            The stagnation temperature of the collector, measured in degrees Kelvin.

        """

        return self._stagnation_temperature + ZERO_CELCIUS_OFFSET

    def calculate_performance(
        self,
        ambient_temperature: float,
        logger: Logger,
        solar_irradiance: float,
        htf_heat_capacity: float | None,
        input_temperature: float | None,
        mass_flow_rate: float | None,
        wind_speed: float | None = None,
    ) -> tuple[float | None, float | None, float | None, float | None,]:
        """
        Calculates the performance characteristics of the solar-thermal collector.

        Inputs:
            - ambient_temperature:
                The ambient temperature, measured in degrees Kelvin.
            - htf_heat_capacity:
                The heat capacity of the HTF entering the collector, measured in Joules
                per kilogram Kelvin (J/kgK).
            - input_temperature:
                The input temperature of the HTF entering the PV-T collector, measured
                in degrees Kelvin.
            - logger:
                The :class:`logging.Logger` to use for the run.
            - mass_flow_rate:
                The mass-flow rate of HTF passing through the collector, measured in
                kilograms per second.
            - solar_irradiance:
                The solar irradiance incident on the surface of the collector, measured
                in Watts per meter squared.
            - wind_speed:
                The wind speed in meters per second.

        Outputs:
            - `None`:
                There is no electrical component to the collector.
            - output_temperature:
                The output temperature of the HTF leaving the collector, measured in
                degrees Kelvin.
            - reduced_temperature:
                The reduced temperature of the collector.
            - thermal_efficiency:
                The thermal efficiency of the collector.

        Raises:
            - FlowRateError:
                Raised if the flow rates are mismatched.

        """

        if mass_flow_rate is None:
            logger.error(
                "Cannot calculate solar-thermal collector performance with no mass flow "
                "rate provided."
            )
            raise ProgrammerJudgementFault(
                "solar:SolarThermalPanel:calculate_performance",
                "Cannot calculate performance of solar-thermal collector if no mass-"
                "flow rate provided.",
            )

        # Raise a flow-rate error if the flow rate is insufficient.
        if (
            mass_flow_rate < self.min_mass_flow_rate
            if self.min_mass_flow_rate is not None
            else False
        ) or (
            mass_flow_rate > self.max_mass_flow_rate
            if self.max_mass_flow_rate is not None
            else False
        ):
            logger.debug(
                "Flow rate of %s kg/s is out of bounds, range is %s to %s kilograms/second.",
                mass_flow_rate,
                self.min_mass_flow_rate,
                self.max_mass_flow_rate,
            )
            raise FlowRateError(
                self.name,
                f"Flow rate of {mass_flow_rate:.2g} kg/s is out of bounds, range is "
                + f"{self.min_mass_flow_rate} to {self.max_mass_flow_rate} "
                "kilograms/second.",
            )

        if input_temperature is None:
            logger.error(
                "Cannot calculate solar-thermal collector performance with no input "
                "temperature provided."
            )
            raise ProgrammerJudgementFault(
                "solar:SolarThermalPanel:calculate_performance",
                "Cannot calculate performance of solar-thermal collector if no input "
                "temperature provided.",
            )

        _, negative_root = _thermal_performance(
            ambient_temperature,
            self.area,
            htf_heat_capacity,
            input_temperature,
            mass_flow_rate,
            self.thermal_performance_curve,
            solar_irradiance,
        )

        # Ensure that the collector has not stagnated.
        if negative_root > self.stagnation_temperature:
            logger.debug(
                "Collector %s outputted HTF at %s degC, above its stagnation "
                "temperature of %s degC",
                self.name,
                negative_root,
                self.stagnation_temperature,
            )
            negative_root = self.stagnation_temperature

        # Compute temperature quantities.
        average_temperature = 0.5 * (negative_root + input_temperature)  # [K]
        reduced_collector_temperature = reduced_temperature(
            ambient_temperature, average_temperature, solar_irradiance
        )  # [K/G]

        # If the reduced temperature is None, the performance cannot be computed.
        if reduced_collector_temperature is None:
            return (None, negative_root, None, None)

        # Compute the thermal efficiency of the collector.
        thermal_efficiency = (
            self.thermal_performance_curve.eta_0
            + self.thermal_performance_curve.c_1 * reduced_collector_temperature
            + self.thermal_performance_curve.c_2
            * solar_irradiance
            * reduced_collector_temperature**2
        )

        return (
            None,
            negative_root,
            reduced_collector_temperature,
            thermal_efficiency,
        )

    @classmethod
    def from_dict(
        cls,
        logger: Logger,
        solar_inputs: dict[str, Any],
    ) -> Any:
        """
        Instantiate a :class:`SolarThermalPanel` instance based on the input data.

        Inputs:
            - logger:
                The :class:`logging.Logger` to use for the run.
            - solar_inputs:
                The solar input data specific to this panel.

        """

        logger.debug("Attempting to create SolarThermalPanel from solar input data.")

        try:
            performance_curve_inputs = solar_inputs[THERMAL_PERFORMANCE_CURVE]
        except KeyError:
            logger.error(
                "No performance curve defined for solar-thermal panel '%s'.",
                solar_inputs["name"],
            )
            raise InputFileError(
                "solar generation inputs",
                f"Solar thermal panel {solar_inputs.get(NAME, '<not supplied>')} is "
                "missing a performance curve.",
            ) from None

        try:
            performance_curve = PerformanceCurve(
                performance_curve_inputs[ZEROTH_ORDER],
                performance_curve_inputs[FIRST_ORDER],
                performance_curve_inputs[SECOND_ORDER],
            )
        except KeyError as exception:
            logger.error(
                "Missing performance curve input(s): %s",
                str(exception),
            )
            raise

        return cls(performance_curve, solar_inputs)


# COLLECTOR_FROM_TYPE:
#   Mapping from collector type to collector.
COLLECTOR_FROM_TYPE: dict[SolarPanelType, Type[SolarPanel]] = {
    SolarPanelType.PV: PVPanel,
    SolarPanelType.PV_T: HybridPVTPanel,
    SolarPanelType.SOLAR_THERMAL: SolarThermalPanel,
}


def get_profile_prefix(panel: PVPanel | HybridPVTPanel) -> str:
    """
    Determine the prefix to use for profile names based on the tracking and angles.

    Inputs:
        - panel:
            The :class:`PVPanel` to determine the profile prefix for.

    """

    # if isinstance(panel, HybridPVTPanel):
    #     tracking = Tracking.DUAL_AXIS
    # else:
    #     tracking = panel.tracking

    if (tracking := panel.tracking) == Tracking.SINGLE_AXIS:
        return f"single_axis_tilt_{panel.tilt}_"
    if tracking == Tracking.DUAL_AXIS:
        return "dual_axis_"
    if tracking == Tracking.FIXED:
        return f"fixed_tilt_{panel.tilt}_azim_{panel.azimuthal_orientation}_"

    raise ProgrammerJudgementFault(
        "generation.solar::get_profile_prefix",
        f"Code not written for switch for tracking value {tracking.value}",
    )


def solar_degradation(lifetime: int, num_years: int) -> pd.DataFrame:
    """
    Calculates the solar degredation.

    Inputs:
        - lifetime:
            The lifetime of the solar setup in years.
        - num_years:
            The number of years for which the simulation is being carried out.

    Outputs:
        - The lifetime degredation of the solar setup.

    """

    # lifetime = self.input_data.iloc["lifetime"]
    hourly_degradation = 0.20 / (lifetime * 365 * 24)
    lifetime_degradation = []

    for i in range((num_years * 365 * 24) + 1):
        equiv = 1.0 - i * hourly_degradation
        lifetime_degradation.append(equiv)

    return pd.DataFrame(lifetime_degradation)


class SolarDataThread(
    BaseRenewablesNinjaThread, profile_name="solar", profile_key="pv"
):
    """
    Class to use when calling the solar data thread.

    Options which are not immediately obvious are documented here:
    - tracking:
        Used for specifying whether the panels are tracking. Available options:
        - 0 -> The panels do not track the sun;
        - 1 -> The panels are single-axis tracking, i.e., track azimuthally but have a
            fixed tilt angle;
        - 2 -> The panels are dual-axis tracking, i.e., track both azimuthally and with
            their tilt.

    """

    def __init__(
        self,
        auto_generated_files_directory: str,
        global_settings_inputs: dict[str, int | str],
        location: Location,
        logger_name: str,
        pause_time: int,
        regenerate: bool,
        pv_panel: PVPanel,
        sleep_multiplier: int = 1,
        verbose: bool = False,
    ):
        """
        Instantiate a :class:`SolarDataThread` instance.

        """

        # Add the additional parameters which are need when calling the solar data.
        renewables_ninja_params = {
            "dataset": "merra2",
            "lat": float(location.latitude),
            "lon": float(location.longitude),
            "local_time": "false",
            "capacity": 1.0,
            "system_loss": 0,
            "tracking": pv_panel.tracking.value,
            "raw": "true",
        }

        renewables_ninja_params["azim"] = (
            pv_panel.azimuthal_orientation
            if pv_panel.azimuthal_orientation is not None
            else "false"
        )
        renewables_ninja_params["tilt"] = (
            pv_panel.tilt if pv_panel.tilt is not None else "false"
        )

        # Determine the prefix to use for the solar profiles dependent on tracking.
        profile_prefix = get_profile_prefix(pv_panel)

        super().__init__(
            auto_generated_files_directory,
            global_settings_inputs,
            location,
            logger_name,
            pause_time,
            regenerate,
            sleep_multiplier,
            verbose,
            renewables_ninja_params=renewables_ninja_params,
            profile_prefix=profile_prefix,
        )


def total_solar_output(
    *args, pv_panel: PVPanel | HybridPVTPanel
) -> pd.DataFrame:  # type: ignore
    """
    Wrapper function to wrap the total solar output.

    """

    try:
        return total_profile_output(
            *args,
            profile_name="solar",
            profile_prefix=get_profile_prefix(pv_panel),
        )
    except FileNotFoundError:
        raise RenewablesNinjaError() from None
