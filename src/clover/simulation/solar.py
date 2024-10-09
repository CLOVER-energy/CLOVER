#!/usr/bin/python3
########################################################################################
# solar.py - Solar panel modelling code for CLOVER.                                    #
#                                                                                      #
# Authors: Ben Winchester                                                              #
# Copyright: Phil Sandwell, 2021                                                       #
# Date created: 12/08/2021                                                             #
# License: Open source                                                                 #

# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
solar.py - Solar-panel modelling code for CLOVER.

In order to accurately model a solar panel within CLOVER, various information about its
performance under environmental conditions needs to be calculated. This module provides
the functionality to model various types of solar collectors, including solar-thermal
and PV-T collectors, over the course of the simulation, computing their output
parameters using a quasi-steady-state model.

"""

import collections

from logging import Logger

import pandas as pd  # pylint: disable=import-error

from scipy import linalg
from tqdm import tqdm

from ..__utils__ import (
    BColours,
    DesalinationScenario,
    HotWaterScenario,
    dict_to_dataframe,
    HTFMode,
    InputFileError,
    InternalError,
    ProgrammerJudgementFault,
    ResourceType,
    Scenario,
    ZERO_CELCIUS_OFFSET,
    SolarPanelType,
    ThermalCollectorScenario,
)
from ..conversion.conversion import ThermalDesalinationPlant
from ..generation.solar import HybridPVTPanel, SolarPanel, SolarThermalPanel
from .__utils__ import Minigrid
from .storage_utils import HotWaterTank


__all__ = ("calculate_solar_thermal_output",)


# Minimum irradiance threshold;
#   To avoid edge cases, where a very small, but non-zero, irradiance causes the AI to
#   predict
MINIMUM_IRRADIANCE_THRESHOLD: float = 0  # [W/m^2]

# Temperature precision:
#   The precision required when solving the differential equation for the system
#   temperatures.
TEMPERATURE_PRECISION: float = 1.44


class MassFlowRateTooLargeError(Exception):
    """
    Raise when the mass-flow rate being specified is too large for the system to cope.

    """

    def __init__(self, msg: str) -> None:
        """
        Instantiate a :class:`MassFlowRateTooLargeError` instance.

        Inputs:
            - msg:
                The message to append.

        """

        super().__init__(
            f"The mass-flow rate was too large for the system to cope with: {msg}"
        )


class MassFlowRateTooSmallError(Exception):
    """
    Raise when the mass-flow rate being specified is too small for the system to cope.

    """

    def __init__(self, msg: str) -> None:
        """
        Instantiate a :class:`MassFlowRateTooSmallError` instance.

        Inputs:
            - msg:
                The message to append.

        """

        super().__init__(
            f"The mass-flow rate was too small for the system to operate: {msg}"
        )


def _volume_withdrawn_from_tank(
    ambient_temperature: float,
    best_guess_tank_temperature: float,
    hot_water_load: float | None,
    logger: Logger,
    minigrid: Minigrid,
    num_tanks: int,
    previous_tank_temperature: float | None,
    resource_type: ResourceType,
    scenario: Scenario,
    thermal_desalination_plant: ThermalDesalinationPlant | None,
) -> tuple[bool, float]:
    """
    Computes whether the tank is supplying an output, and what this output is.

    Inputs:

    Outputs:
        A `tuple` containing:
        - tank_supply_on:
            Whether liquid was withdrawn from the tank (True) or not (False).
        - volume_supplied:
            The volume supplied, measured in kg/hour, by all of the tanks combined.

    """

    if resource_type == ResourceType.CLEAN_WATER:
        if previous_tank_temperature is None or thermal_desalination_plant is None:
            logger.error(
                "%sNot enough parameters specified to determine buffer-tank mass-flow "
                "rate.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "Not enough desalination-specific parameters specified to determine "
                "the buffer-tank mass-flow rate."
            )
        if minigrid.buffer_tank is None:
            logger.error(
                "%sNo buffer tank specified when attempting to determine the volume "
                "withdrawn from the tank.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "No buffer tank was found defined for the minigrid specified despite "
                "clean-water loads being requested."
            )

        # If the plant is heated by HTF.
        if thermal_desalination_plant.htf_mode == HTFMode.CLOSED_HTF:
            if thermal_desalination_plant.minimum_htf_temperature is None:
                logger.error(
                    "%sNo minimum htf temperature defined despite '%s' being the HTF "
                    "mode.%s",
                    BColours.fail,
                    thermal_desalination_plant.htf_mode.value,
                    BColours.endc,
                )
                raise InternalError(
                    "Minimum HTF temperature unexpectly undefined when computing plant "
                    "supply volume."
                )

            tank_supply_on: bool = (
                previous_tank_temperature
                > (
                    thermal_desalination_plant.minimum_htf_temperature
                    + ZERO_CELCIUS_OFFSET
                )
            ) or scenario.desalination_scenario.auxiliary_heater is not None
            volume_supplied: float = (
                _htf_fed_buffer_tank_mass_flow_rate(
                    ambient_temperature,
                    best_guess_tank_temperature,
                    minigrid.buffer_tank,
                    num_tanks,
                    thermal_desalination_plant,
                )
                * tank_supply_on
            )

        if thermal_desalination_plant.htf_mode == HTFMode.FEEDWATER_HEATING:
            if thermal_desalination_plant.minimum_feedwater_temperature is None:
                logger.error(
                    "%sNo minimum feedwater temperature defined despite '%s' being the "
                    "HTF mode.%s",
                    BColours.fail,
                    thermal_desalination_plant.htf_mode.value,
                    BColours.endc,
                )
                raise InternalError(
                    "Minimum feedwater temperature unexpectly undefined when computing "
                    "plant supply volume."
                )

            tank_supply_on = (
                previous_tank_temperature
                > thermal_desalination_plant.minimum_feedwater_temperature
            )
            volume_supplied = (
                thermal_desalination_plant.input_resource_consumption[
                    ResourceType.HOT_UNCLEAN_WATER
                ]
                * tank_supply_on
            )

    elif resource_type == ResourceType.HOT_CLEAN_WATER:
        if hot_water_load is None:
            logger.error(
                "%sNo hot-water load defined despite a hot-water system being "
                "specified.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "No hot-water load was provided to the 'tank volume supplied' "
                "calculation method despite hot water being defined in the scenario "
                "file."
            )
        if minigrid.hot_water_tank is None:
            logger.error(
                "%sNo hot-water tank defined despite a hot-water system being "
                "specified.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "No hot-water tank was defined on the minigrid when calling the 'tank "
                "volume supplied' calculation method despite hot water being defined "
                "in the scenario file."
            )

        # The tank should only supply water if the load is less than the capacity of the
        # tanks.
        if hot_water_load <= num_tanks * minigrid.hot_water_tank.mass:
            tank_supply_on = hot_water_load > 0
            volume_supplied = hot_water_load
        # Otherwise, no water should be supplied.
        else:
            tank_supply_on = hot_water_load > 0
            volume_supplied = num_tanks * minigrid.hot_water_tank.mass

    return tank_supply_on, volume_supplied  # pylint: disable=used-before-assignment


def _get_collector_output_temperatures(
    collector_input_temperature: float,
    irradiance: dict[SolarPanelType, float],
    logger: Logger,
    pvt_collector_mass_flow_rate: float | None,
    relevant_scenarios: dict[SolarPanelType, ThermalCollectorScenario],
    solar_thermal_collectors: dict[SolarPanelType, HybridPVTPanel | SolarThermalPanel],
    st_collector_mass_flow_rate: float | None,
    temperature: dict[SolarPanelType, float],
    wind_speed: float,
) -> tuple[float, float | None, float | None, float | None]:
    """
    Calculate the output temperatures for the solar-thermal and PV-T collectors.

    Inputs:
        - collector_input_temperature:
            The input temperature to use for the collector system.
        - irradiance:
            The irradiance, in kW/m^2.
        - logger:
            The logger to use for the run.
        - pvt_collector_mass_flow_rate:
            The mass flow rate through the PV-T collectors.
        - relevant_scenarios:
            The set relevant scenarios, keyed by panel type.
        - solar_thermal_collectors:
            The `list` of solar-thermal and PV-T collectors to use.
        - st_collector_mass_flow_rate:
            The mass flow rate through any solar-thermal collectors present.
        - temperature:
            The current ambient temperature.
        - wind_speed:
            The current wind speed.

    Outputs:
        - collector_system_output_temperature:
            The output temperature of the collector system as a whole.
        - fractional_electric_performance:
            The fractional electrical performance of the PV-T collectors.
        - st_collector_output_temperature:
            The output temperature of the solar-thermal collectors installed, if
            applicable.
        - pvt_collector_output_temperature:
            The output temperature of the PV-T collectors installed, if applicable.

    """

    # Determine the PV-T output if present.
    if SolarPanelType.PV_T in solar_thermal_collectors:
        if pvt_collector_mass_flow_rate is None:
            logger.error(
                "%sNo PV-T mass-flow rate provided despite modelling requested.%s",
                BColours.fail,
                BColours.endc,
            )
            raise ProgrammerJudgementFault(
                "simulation.solar::_get_collector_output_temperatures",
                "No PV-T collector mass-flow rate when modelling PV-T collector "
                "performance.",
            )

        # Calculate the output temperature map from the collector.
        (
            fractional_electrical_performance,
            pvt_output_temperature,
            reduced_pvt_collector_temperature,
            pvt_thermal_efficiency,
        ) = solar_thermal_collectors[SolarPanelType.PV_T].calculate_performance(
            temperature[SolarPanelType.PV_T] + ZERO_CELCIUS_OFFSET,
            logger,
            1000 * irradiance[SolarPanelType.PV_T],
            relevant_scenarios[SolarPanelType.PV_T].htf_heat_capacity,
            collector_input_temperature,
            pvt_collector_mass_flow_rate,
            wind_speed,
        )
    else:
        fractional_electrical_performance = None
        pvt_output_temperature = None
        reduced_pvt_collector_temperature = None
        pvt_thermal_efficiency = None

    # Determine the solar-thermal output if present
    if SolarPanelType.SOLAR_THERMAL in solar_thermal_collectors:
        # Determine the correct input temperature to use if using a series setup or a
        # solar-thermal-only system.
        solar_thermal_input_temperature: float = (
            pvt_output_temperature
            if pvt_output_temperature is not None
            else collector_input_temperature
        )

        if st_collector_mass_flow_rate is None:
            logger.error(
                "%sNo solar-thermal mass-flow rate provided despite modelling requested.%s",
                BColours.fail,
                BColours.endc,
            )
            raise ProgrammerJudgementFault(
                "simulation.solar::_get_collector_output_temperatures",
                "No solar-thermal collector mass flow rate when modelling "
                "solar-thermal collector performance.",
            )

        # Calculate the output temperature map from the collector.
        (
            _,
            solar_thermal_output_temperature,
            reduced_solar_thermal_collector_temperature,
            solar_thermal_thermal_efficiency,
        ) = solar_thermal_collectors[
            SolarPanelType.SOLAR_THERMAL
        ].calculate_performance(
            temperature[SolarPanelType.SOLAR_THERMAL] + ZERO_CELCIUS_OFFSET,
            logger,
            1000 * irradiance[SolarPanelType.SOLAR_THERMAL],
            relevant_scenarios[SolarPanelType.SOLAR_THERMAL].htf_heat_capacity,
            solar_thermal_input_temperature,
            st_collector_mass_flow_rate,
            wind_speed,
        )
    else:
        solar_thermal_output_temperature = None
        reduced_solar_thermal_collector_temperature = None
        solar_thermal_thermal_efficiency = None

    if solar_thermal_output_temperature is None and pvt_output_temperature is None:
        logger.error(
            "%sFailed to calculate either solar-thermal or PV-T output temperatures.%s",
            BColours.fail,
            BColours.endc,
        )
        raise ProgrammerJudgementFault(
            "simulation.solar::_get_collector_output_temperatures",
            "No output temperatures were determined as a result of the function call.",
        )

    return (
        (
            solar_thermal_output_temperature  # type: ignore [return-value]
            if solar_thermal_output_temperature is not None
            else pvt_output_temperature
        ),
        fractional_electrical_performance,
        pvt_output_temperature,
        pvt_thermal_efficiency,
        reduced_pvt_collector_temperature,
        solar_thermal_output_temperature,
        solar_thermal_thermal_efficiency,
        reduced_solar_thermal_collector_temperature,
    )


def _get_relevant_thermal_scenario(
    resource_type: ResourceType,
    scenario: Scenario,
) -> DesalinationScenario | HotWaterScenario:
    """
    Determines the relevant thermal scenario based on other information.

    Inputs:
        - resource_type:
            The :class:`ResourceType` for the run.
        - scenario:
            The :class:`Scenario` being used for the run.
        - solar_thermal_collector:
            The relevant solar-thermal collector being used for the run.

    Outputs:
        The relevant thermal scenario.

    Raises:
        - ProgrammerJudgementFault:
            Raised if the scenario could not be returned as it would have been `None`.

    """

    if resource_type == ResourceType.CLEAN_WATER:
        if scenario.desalination_scenario is None:
            raise ProgrammerJudgementFault(
                "simulation.solar::_get_relevant_thermal_scenario",
                "Could not return desalination scenario as no desalination scenario to return.",
            )
        return scenario.desalination_scenario

    if resource_type in {ResourceType.HOT_CLEAN_WATER, ResourceType.HOT_UNCLEAN_WATER}:
        if scenario.hot_water_scenario is None:
            raise ProgrammerJudgementFault(
                "simulation.solar::_get_relevant_thermal_scenario",
                "Could not return hot-water scenario as no hot-water scenario to return.",
            )
        return scenario.hot_water_scenario

    raise ProgrammerJudgementFault(
        "simularion.solar::_get_relevant_thermal_scenario",
        "Could not determine relevant scenario for resource type "
        f"{ResourceType.value}",
    )


def _get_relevant_collector_scenario(
    resource_type: ResourceType,
    scenario: Scenario,
    solar_thermal_collector: HybridPVTPanel | SolarThermalPanel,
) -> ThermalCollectorScenario:
    """
    Determines the relevant collector scenario based on other information.

    Inputs:
        - resource_type:
            The :class:`ResourceType` for the run.
        - scenario:
            The :class:`Scenario` being used for the run.
        - solar_thermal_collector:
            The relevant solar-thermal collector being used for the run.

    Outputs:
        The relevant thermal collector scenario.

    Raises:
        - ProgrammerJudgementFault:
            Raised if the scenario could not be returned as it would have been `None`.

    """

    thermal_scenario = _get_relevant_thermal_scenario(resource_type, scenario)

    if solar_thermal_collector.panel_type == SolarPanelType.PV_T:
        if thermal_scenario.pvt_scenario is None:
            raise ProgrammerJudgementFault(
                "simulation.solar::_get_relevant_collector_scenario",
                "Requested to get PV-T scenario but no PV-T scenario defined.",
            )
        return thermal_scenario.pvt_scenario
    if solar_thermal_collector.panel_type == SolarPanelType.SOLAR_THERMAL:
        if thermal_scenario.solar_thermal_scenario is None:
            raise ProgrammerJudgementFault(
                "simulation.solar::_get_relevant_collector_scenario",
                "Requested to get solar-thermal scenario but no solar-thermal scenario "
                "defined.",
            )
        return thermal_scenario.solar_thermal_scenario

    raise ProgrammerJudgementFault(
        "simulation.solar::_get_relevant_scenario",
        "Did not know how to process panel and resource-type information to determine "
        "the relevant scenario.",
    )


def _get_supply_flow_rate(
    collector_system_sizes: dict[SolarPanelType, int],
    pvt_collector_mass_flow_rate: float,
    solar_thermal_panels: list[HybridPVTPanel | SolarThermalPanel],
    st_collector_mass_flow_rate: float,
    thermal_scenario: DesalinationScenario | HotWaterScenario,
) -> float:
    """
    Calculates the flow rate of HTF through a collector system of 1+ collector types.

    Inputs:
        - collector_system_sizes:
            A mapping between panel types and system sizes.
        - pvt_collector_mass_flow_rate:
            The mass flow rate through the PV-T collectors.
        - solar_thermal_panels:
            The list of solar-thermal and PV-T panels associated with the system.
        - st_collector_mass_flow_rate:
            The mass flow rate through the solar-thermal collectors.
        - thermal_scenario:
            The relevant thermal scenario.

    Outputs:
        The mass flow rate of the HTF through the system.

    Raises:
        - InputFileError:
            Raised if multiple collector types were specified but no throughput mass
            flow rate was provided.
        - ProgrammerJudgementFault:
            Raised if only a single collector type was specified but this was not of a
            supported type.

    """

    # Use the throughput flow rate if provided.
    if thermal_scenario.throughput_mass_flow_rate is not None:
        return thermal_scenario.throughput_mass_flow_rate

    if len(solar_thermal_panels) > 1:
        raise InputFileError(
            f"{thermal_scenario.name} scenario",
            "If not using a throughput mass flow rate, only one collector type can be specified.",
        )
    solar_thermal_panel = solar_thermal_panels.pop()

    # Otherwise, as only one collector type is being used, use the appropriate
    # flow rate.
    if solar_thermal_panel.panel_type == SolarPanelType.SOLAR_THERMAL:
        return (
            st_collector_mass_flow_rate
            * collector_system_sizes[SolarPanelType.SOLAR_THERMAL]
        )

    if solar_thermal_panel.panel_type == SolarPanelType.PV_T:
        return (
            pvt_collector_mass_flow_rate * collector_system_sizes[SolarPanelType.PV_T]
        )

    raise ProgrammerJudgementFault(
        "simulation.solar::_get_htf_flow_rate",
        "Function called with unsupported panel type "
        f"'{solar_thermal_panel.panel_type}'. Valid types are "
        + f"'{SolarPanelType.PV_T.value}' and '{SolarPanelType.SOLAR_THERMAL.value}'.",
    )


def _thermal_plant_hot_water_return_temperature(
    ambient_temperature: float,
    thermal_desalination_plant: ThermalDesalinationPlant,
) -> float:
    """
    Return the hot-water return temperature from the desalination plant.

    Inputs:
        - ambient_temperature:
            The ambient temperature.
        - thermal_desalination_plant:
            The thermal desalination plant.

    Outputs:
        The thermal desalination plant temperature in Celsius.

    """

    if (
        plant_return_temperature := thermal_desalination_plant.hot_water_return_temperature
    ) is not None:
        return plant_return_temperature

    return ambient_temperature


def _htf_fed_buffer_tank_mass_flow_rate(
    ambient_temperature: float,
    best_guess_tank_temperature: float,
    buffer_tank: HotWaterTank,
    num_tanks: int,
    thermal_desalination_plant: ThermalDesalinationPlant,
) -> float:
    """
    Computes the mass-flow rate of HTF from the buffer tanks to the desalination plant.

    Inputs:
        - ambient_temperature:
            The ambient temperature, used as the base against which heat is being
            supplied. This is realistic as the final stage of desalination plants can be
            no less than the ambient temprature. This is measured in degrees Kelvin.
        - best_guess_tank_temperature:
            The best guess at the tank temperature at the current time step, measured in
            degrees Celsius. This is the temperature at which HTF is removed from the
            tank to supply the desalination plant.
        - buffer_tank:
            The HTF hot-water tank.
        - num_tanks:
            The number of buffer tanks.
        - thermal_desalination_plant:
            The thermal desalination plant being modelled.

    Outputs:
        - The mass-flow rate of HTF from the bugger tanks to the desalination plant,
          measured in litres per hour.

    Raises:
        - InputFileError:
            Raised if the thermal desalination plant does not use heat from the HTF.

    """

    if ResourceType.HEAT not in thermal_desalination_plant.input_resource_consumption:
        raise InputFileError(
            "converter inputs",
            "The thermal desalination plant selected does define its heat consumption.",
        )

    return (
        thermal_desalination_plant.input_resource_consumption[ResourceType.HEAT]
        * 3600  # [s/h]
        / (  # [Wth]
            buffer_tank.heat_capacity  # [J/kg*K]
            * num_tanks
            * (
                (thermal_desalination_plant.minimum_htf_temperature)
                - _thermal_plant_hot_water_return_temperature(
                    (ambient_temperature - ZERO_CELCIUS_OFFSET),
                    thermal_desalination_plant,
                )
            )  # [K]
        )
    )  # [kg/hour]


def _calculate_closed_loop_solar_thermal_output(  # pylint: disable=too-many-locals, too-many-statements
    collector_system_sizes: dict[SolarPanelType, int],
    disable_tqdm: bool,
    end_hour: int,
    irradiances: dict[SolarPanel, pd.Series],
    logger: Logger,
    minigrid: Minigrid,
    num_tanks: int,
    processed_total_hw_load: pd.Series | None,
    relevant_scenarios: dict[SolarPanelType, ThermalCollectorScenario],
    resource_type: ResourceType,
    scenario: Scenario,
    solar_thermal_collectors: dict[SolarPanelType, HybridPVTPanel | SolarThermalPanel],
    start_hour: int,
    temperatures: dict[SolarPanel, pd.Series],
    thermal_desalination_plant: ThermalDesalinationPlant | None,
    wind_speeds: pd.Series,
) -> tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame
]:
    """
    Computes the output of a closed-loop (HTF-heating) solar-thermal system.

    For closed-loop, i.e., htf-heating, solar-thermal-based systems, the input
    temperature of HTF to the collectors depends on the output temperature of HTF from
    the hot-water/heat-stroage tanks. As such, a matrix equation is required. This
    function should **not** be called directly. Rather, the externally-exposed API
    should be called which will decide whether to call this function.

    Inputs:
        - collector_system_sizes:
            The size of the PV-T or solar-thermal system being modelled.
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - end_hour:
            The end hour for the simulation being carried out.
        - irradiances:
            The :class:`pd.Series` containing irradiance information for the time
            period being modelled.
        - logger:
            The logger to use for the run.
        - minigrid:
            The minigrid being modelled currently.
        - num_tanks:
            The number of hot-water tanks being modelled currently, which can either be
            buffer tanks (for desalination systems), or hot-water tanks (for hot-water
            systems).
        - processed_total_hw_load:
            The total hot-water load placed on the system, measured in litres per hour.
        - resource_type:
            The resource type for which the PV-T or solar-thermal output is being
            determined.
        - scenario:
            The :class:`Scenario` being considered.
        - solar_thermal_collectors:
            The solar-thermal collector(s) to model, either a solar-thermal collector as
            a `list` of :class:`SolarThermalPanel` or :class:`HybridPVTPanel` instances.
        - start_hour:
            The start hour for the simulation being carried out.
        - temperatures:
            The :class:`pd.Series` containing temperature information for the time
            period being modelled.
        - thermal_desalination_plant:
            The thermal desalination plant being considered.
        - wind_speeds:
            The :class:`pd.Series` containing wind-speed information for the time period
            being modelled.

    Outputs:
        - collector_input_temperature:
            The input temperature of the HTF entering the PV-T/solar-thermal collectors
            at each time step.
        - collector_output_temperature:
            The output temperature of HTF leaving the PV-T/solar-thermal collectors at
            each time step.
        - electric_power_per_unit:
            The electric power, per unit PV-T or solar-thermal collector, delivered by
            the PV-T/solar-thermal system.
        - output_temperature:
            The output temperatures throughout the simulation, measured in degrees
            Celsius.
        - pump_times_frame:
            The times for which the PV-T/solar-thermal HTF pump was switched on.
        - tank_temperature:
            The tank temperatures throughout the simulation, measured in degrees
            Celsius.
        - volume_supplied:
            The amount of hot water supplied by the system, measured in litres.

    """

    if minigrid.heat_exchanger is None:
        logger.error(
            "%sThe energy system does not contain a heat exchanger despite the %s "
            "output computation function being called which is reliant "
            "on the definition of a heat exchanger.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "energy system inputs",
            "The energy system specified does not contain a heat exchanger but "
            "solar-thermal or PV-T modelling was requested for which this is required.",
        )

    if minigrid.hot_water_tank is None:
        logger.error(
            "%sNo hot-water tank was defined for the minigrid despite hot-water"
            "modelling being requested.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InternalError(
            "No water pump defined as part of the energy system despite PV-T or "
            "solar-thermal modelling being requested."
        )

    # Instantiate variables
    pvt_collector_mass_flow_rate: float | None = None
    runs: int = 0
    st_collector_mass_flow_rate: float | None = None

    # Determine information useful across all time steps information.
    thermal_scenario = _get_relevant_thermal_scenario(resource_type, scenario)
    default_supply_temperature: float = (
        thermal_scenario.htf_supply_temperature + ZERO_CELCIUS_OFFSET
    )
    best_guess_collector_input_temperature: float = (
        default_supply_temperature + ZERO_CELCIUS_OFFSET
    )
    tank_replacement_temperature: float = (
        thermal_desalination_plant.hot_water_return_temperature
        if thermal_desalination_plant.htf_mode == HTFMode.CLOSED_HTF
        else default_supply_temperature
    ) + ZERO_CELCIUS_OFFSET  # [degC]

    # The collector heat transfer depends only on the parameters of the final
    # collector in any series configuration.
    if SolarPanelType.PV_T in relevant_scenarios:
        collector_heat_transfer: float = (
            collector_system_sizes[SolarPanelType.PV_T]
            * relevant_scenarios[SolarPanelType.PV_T].mass_flow_rate  # [kg/s]
            * relevant_scenarios[SolarPanelType.PV_T].htf_heat_capacity  # [J/kg*K]
            * minigrid.heat_exchanger.efficiency
            # / 3600  # [s/hour]
        )  # [W/K]
        pvt_collector_mass_flow_rate = (
            (
                thermal_scenario.throughput_mass_flow_rate
                / collector_system_sizes[SolarPanelType.PV_T]
            )
            if thermal_scenario.throughput_mass_flow_rate is not None
            else relevant_scenarios[SolarPanelType.PV_T].mass_flow_rate
        )
        logger.debug(
            "Mass flow rate through PV-T collectors: %s",
            round(pvt_collector_mass_flow_rate, 2),
        )

    if SolarPanelType.SOLAR_THERMAL in relevant_scenarios:
        collector_heat_transfer = (
            collector_system_sizes[SolarPanelType.SOLAR_THERMAL]
            * relevant_scenarios[SolarPanelType.SOLAR_THERMAL].mass_flow_rate  # [kg/s]
            * relevant_scenarios[
                SolarPanelType.SOLAR_THERMAL
            ].htf_heat_capacity  # [J/kg*K]
            * minigrid.heat_exchanger.efficiency
            # / 3600  # [s/hour]
        )  # [W/K]
        st_collector_mass_flow_rate = (
            (
                thermal_scenario.throughput_mass_flow_rate
                / collector_system_sizes[SolarPanelType.SOLAR_THERMAL]
            )
            if thermal_scenario.throughput_mass_flow_rate is not None
            else relevant_scenarios[SolarPanelType.SOLAR_THERMAL].mass_flow_rate
        )
        logger.debug(
            "Mass flow rate through solar-thermal collectors: %s",
            round(st_collector_mass_flow_rate, 2),  # type: ignore [arg-type]
        )

    if (
        SolarPanelType.PV_T not in relevant_scenarios
        and SolarPanelType.SOLAR_THERMAL not in relevant_scenarios
    ):
        raise ProgrammerJudgementFault(
            "simulation.solar::_calculate_closed_loop_solar_thermal_output",
            "Either solar-thermal or PV-T collectors, or both, are required if "
            "carrying out thermal modelling.",
        )

    # For desalination, a buffer tank is required
    if (
        scenario.desalination_scenario is not None
        and resource_type == ResourceType.CLEAN_WATER
    ):
        if minigrid.buffer_tank is None:
            logger.error(
                "%sThe energy system does not contain a buffer tank despite the %s "
                "output computation function being called for a "
                "clean-water load.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "energy system inputs",
                "The energy system specified does not contain a buffer tank but "
                "solar-thermal or PV-T modelling was requested.",
            )

        tank: HotWaterTank = minigrid.buffer_tank

    # For hot-water heating, hot water is directly heated.
    elif (
        scenario.hot_water_scenario is not None
        and resource_type == ResourceType.HOT_CLEAN_WATER
    ):
        if minigrid.hot_water_tank is None:
            logger.error(
                "%sThe energy system does not contain a hot-water tank despite the "
                "PV-T output computation function being called for a hot-water load.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "energy system inputs",
                "The energy system specified does not contain a hot-water tank but "
                "PV-T modelling for hot-water loads was requested.",
            )

        tank = minigrid.hot_water_tank

    # One of these scenarios must be specified, so throw an error if not.
    else:
        logger.error(
            "%sNeither desalination nor hot-water scenarios were defined despite PV-T "
            "output being requested.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InternalError(
            "Neither desalination nor hot-water scenarios were specified despite PV-T "
            "being called."
        )

    # Instantiate maps for easy PV-T power lookups.
    electric_power_per_unit_map: dict[int, float] = {}
    pump_times_map: dict[int, int] = {}

    # Instantiate maps for easy HTF and tank lookups.
    tank_supply_temperature_map: dict[
        int, float
    ] = {}  # pylint: disable=unused-variable
    tank_volume_supplied_map: dict[int, float] = {}

    auxiliary_heating_map: dict[int, float] = {}
    collector_input_temperature_map: dict[
        SolarPanelType, dict[int, float]
    ] = collections.defaultdict(
        lambda: collections.defaultdict(lambda: default_supply_temperature)
    )
    collector_output_temperature_map: dict[
        SolarPanelType, dict[int, float]
    ] = collections.defaultdict(
        lambda: collections.defaultdict(lambda: default_supply_temperature)
    )
    collector_thermal_efficiencies_map: dict[
        SolarPanelType, dict[int, float | None]
    ] = collections.defaultdict(lambda: collections.defaultdict(lambda: None))
    collector_reduced_temperatures_map: dict[
        SolarPanelType, dict[int, float]
    ] = collections.defaultdict(lambda: collections.defaultdict(lambda: 0))
    collector_system_output_temperature_map: dict[int, float] = collections.defaultdict(
        float
    )
    renewable_heating_map: dict[int, float] = collections.defaultdict(float)
    best_guess_collector_input_temperature: float = default_supply_temperature
    tank_environment_heat_transfer: float = (
        num_tanks * tank.heat_transfer_coefficient
    )  # [W/K]
    tank_internal_energy: float = (
        num_tanks
        * tank.mass
        * tank.heat_capacity
        / 3600  # [kg]  # [J/kg*K]  # [s/hour]
    )  # [W/K]
    tank_temperature_map: dict[int, float] = collections.defaultdict(
        lambda: default_supply_temperature
    )

    logger.info(
        "Beggining hourly %s closed-loop performance calculation.", resource_type.value
    )

    for index in tqdm(
        range(start_hour, end_hour),
        desc=f"{resource_type.value.replace('_', ' ')} "
        + " and ".join(
            panel_type.value.replace("_", "-") for panel_type in collector_system_sizes
        )
        + " performance",
        disable=disable_tqdm,
        leave=False,
        unit="hour",
    ):
        # Determine whether the PV-T is flowing.
        if index > start_hour:
            collector_flow_on: bool = (
                collector_system_output_temperature_map[index - 1]
                > tank_temperature_map[index - 1]
            ) and irradiances[solar_thermal_collectors[SolarPanelType.PV_T]][index] > 0
        else:
            collector_flow_on = False

        ##############################
        # All temperatures in Kelvin #
        ##############################

        previous_tank_temperature: float = (
            tank_temperature_map[index - 1] + ZERO_CELCIUS_OFFSET
            if index > start_hour
            else (
                _thermal_plant_hot_water_return_temperature(
                    (
                        current_ambient_temperature := max(
                            temperature_series[index]
                            for temperature_series in temperatures.values()
                        )
                    ),
                    thermal_desalination_plant,
                )
                + ZERO_CELCIUS_OFFSET
                if thermal_desalination_plant.hot_water_return_temperature is not None
                else default_supply_temperature
            )
        )

        # Determine the volume withdrawn from the buffer tanks
        tank_supply_on, volume_supplied = _volume_withdrawn_from_tank(
            (
                current_ambient_temperature_kelvin := current_ambient_temperature
                + ZERO_CELCIUS_OFFSET
            ),
            previous_tank_temperature,
            (
                processed_total_hw_load[index]
                if processed_total_hw_load is not None
                else None
            ),
            logger,
            minigrid,
            num_tanks,
            previous_tank_temperature,
            resource_type,
            scenario,
            thermal_desalination_plant,
        )

        # Only compute outputs if there is input irradiance.
        collector_system_output_temperature: float
        fractional_electric_performance: float | None
        solution_found: bool = False
        pvt_collector_output_temperature: float | None
        st_collector_output_temperature: float | None

        # Keep processing until the temperatures are consistent.
        while not solution_found:
            # Use the AI to determine the output temperature of the collector, based on
            # the best guess of the collector input temperature.
            if (
                1000
                * max(
                    irradiance_series[index]
                    for irradiance_series in irradiances.values()
                )
            ) > MINIMUM_IRRADIANCE_THRESHOLD:
                # If there is enough irradiance to trigger reliable modelling, use the
                # in-built modelling tools.
                # FIXME: Check units on mass-flow rate here.
                (
                    collector_system_output_temperature,
                    fractional_electric_performance,
                    pvt_collector_output_temperature,
                    pvt_thermal_efficiency,
                    reduced_pvt_collector_temperature,
                    st_collector_output_temperature,
                    st_thermal_efficiency,
                    reduced_st_collector_temperature,
                ) = _get_collector_output_temperatures(
                    best_guess_collector_input_temperature,
                    {
                        panel.panel_type: irradiance_series[index]
                        for panel, irradiance_series in irradiances.items()
                    },
                    logger,
                    pvt_collector_mass_flow_rate,
                    relevant_scenarios,
                    solar_thermal_collectors,
                    st_collector_mass_flow_rate,
                    {
                        panel.panel_type: temperature_series[index]
                        for panel, temperature_series in temperatures.items()
                    },
                    wind_speeds[index],
                )

                if fractional_electric_performance is None and scenario.pv_t:
                    logger.error(
                        "%s%s performance function returned `None` for electrical "
                        "output.%s",
                        BColours.fail,
                        SolarPanelType.PV_T.value.capitalize(),
                        BColours.endc,
                    )
                    raise ProgrammerJudgementFault(
                        f"simularion/solar/{SolarPanelType.PV_T.value.capitalize()}::"
                        "calculate_performance",
                        "Function returned `None` for electrical performance of a PV-T "
                        "collector.",
                    )

                if collector_system_output_temperature is None:
                    logger.error(
                        "%s%s performance function returned `None` for thermal output."
                        "%s",
                        BColours.fail,
                        resource_type.value.capitalize(),
                        BColours.endc,
                    )
                    raise ProgrammerJudgementFault(
                        "simularion.solar::_calcualte_closed_loop_solar_thermal_output",
                        "Function returned `None` for thermal performance of a "
                        f"closed-loop {resource_type.value.capitalize()} system.",
                    )

            else:
                # Otherwise, assume that the collector is in steady state with the
                # environment, a reasonable assumption given the one-hour resolution.
                fractional_electric_performance = 0 if scenario.pv_t else None
                st_collector_output_temperature = max(
                    (default_supply_temperature if scenario.solar_thermal else None),
                    tank_replacement_temperature,
                    current_ambient_temperature_kelvin,
                )
                pvt_collector_output_temperature = max(
                    (default_supply_temperature if scenario.pv_t else None),
                    tank_replacement_temperature,
                    current_ambient_temperature_kelvin,
                )
                pvt_thermal_efficiency = None
                reduced_pvt_collector_temperature = 0
                st_thermal_efficiency = None
                reduced_st_collector_temperature = 0
                collector_system_output_temperature = max(
                    tank_replacement_temperature,
                    current_ambient_temperature_kelvin,
                )

            # If the collector flow was not on, then the output temperature should
            # simply be the same as the input temperature.
            if not collector_flow_on:
                collector_system_output_temperature = max(
                    best_guess_collector_input_temperature,
                    tank_replacement_temperature,
                    current_ambient_temperature_kelvin,
                )

            tank_load_enthalpy_transfer = (
                volume_supplied  # [kg/hour]
                * tank.heat_capacity  # [J/kg*K]
                / 3600  # [s/hour]
            )  # [W/K]

            # Determine the tank temperature and collector input temperature that match.
            resultant_vector = [
                collector_heat_transfer * (collector_system_output_temperature)
                + tank_environment_heat_transfer * current_ambient_temperature_kelvin
                + tank_internal_energy * (previous_tank_temperature)
                + (
                    tank_load_enthalpy_transfer
                    # * (tank_replacement_temperature + ZERO_CELCIUS_OFFSET)
                    * (
                        max(
                            current_ambient_temperature_kelvin,
                            tank_replacement_temperature,
                        )
                    )
                    if tank_supply_on
                    else 0
                ),
                (
                    (1 - minigrid.heat_exchanger.efficiency)
                    * (collector_system_output_temperature)
                ),
            ]

            matrix = [
                [
                    0,
                    (
                        collector_heat_transfer
                        + tank_environment_heat_transfer
                        + tank_internal_energy
                        + (tank_load_enthalpy_transfer if tank_supply_on else 0)
                    ),
                ],
                [1, -minigrid.heat_exchanger.efficiency],
            ]

            collector_input_temperature, tank_temperature = linalg.solve(
                a=matrix, b=resultant_vector
            )

            # If a solution has been found, then break the loop.
            if (
                abs(
                    collector_input_temperature - best_guess_collector_input_temperature
                )
                < TEMPERATURE_PRECISION
            ):
                runs = 0
                solution_found = True

            runs += 1
            if runs > 10:
                logger.debug(
                    "Index: %s: Run # %s: Input=%s, PV-T=%s, ST=%s, Plant=%s: Solution not yet found, "
                    "re-iterating: T_c,in=%s degC, best-guess T_c,in=%s degC, "
                    "T_tank=%s degC",
                    index,
                    runs,
                    "on" if collector_flow_on else "off",
                    "on" if tank_supply_on else "off",
                    round(collector_input_temperature, 3),
                    (
                        round(pvt_collector_output_temperature, 3)
                        if pvt_collector_output_temperature is not None
                        else "N/A"
                    ),
                    (
                        round(st_collector_output_temperature, 3)
                        if st_collector_output_temperature is not None
                        else "N/A"
                    ),
                    round(best_guess_collector_input_temperature, 3),
                    round(tank_temperature, 3),
                )

            best_guess_collector_input_temperature = collector_input_temperature

        ###############################
        # All temperatures in Clesius #
        ###############################

        collector_input_temperature -= ZERO_CELCIUS_OFFSET
        tank_temperature -= ZERO_CELCIUS_OFFSET

        # Save the performance characteristics and output temp.
        collector_input_temperature_map[SolarPanelType.PV_T][index] = (
            collector_input_temperature if scenario.pv_t else None
        )
        collector_input_temperature_map[SolarPanelType.SOLAR_THERMAL][index] = (
            pvt_collector_output_temperature - ZERO_CELCIUS_OFFSET
            if scenario.pv_t
            else collector_input_temperature
        )

        if scenario.pv_t:
            collector_output_temperature_map[SolarPanelType.PV_T][index] = (
                pvt_collector_output_temperature - ZERO_CELCIUS_OFFSET
            )  # type: ignore [assignment]
            collector_thermal_efficiencies_map[SolarPanelType.PV_T][
                index
            ] = pvt_thermal_efficiency
            collector_reduced_temperatures_map[SolarPanelType.PV_T][
                index
            ] = reduced_pvt_collector_temperature

        if scenario.solar_thermal:
            collector_output_temperature_map[SolarPanelType.SOLAR_THERMAL][index] = (
                st_collector_output_temperature - ZERO_CELCIUS_OFFSET
            )  # type: ignore [assignment]
            collector_thermal_efficiencies_map[SolarPanelType.SOLAR_THERMAL][
                index
            ] = st_thermal_efficiency
            collector_reduced_temperatures_map[SolarPanelType.SOLAR_THERMAL][
                index
            ] = reduced_st_collector_temperature

        auxiliary_heating_map[index] = max(
            tank_load_enthalpy_transfer
            * (
                (
                    thermal_desalination_plant.minimum_htf_temperature
                    if thermal_desalination_plant.htf_mode == HTFMode.CLOSED_HTF
                    else thermal_desalination_plant.minimum_feedwater_temperature
                )
                - tank_temperature
            ),
            0,
        )
        collector_system_output_temperature_map[index] = (
            collector_system_output_temperature - ZERO_CELCIUS_OFFSET
        )
        pump_times_map[index] = int(collector_flow_on)
        renewable_heating_map[index] = max(
            tank_load_enthalpy_transfer
            * (
                tank_temperature
                - (
                    thermal_desalination_plant.hot_water_return_temperature
                    if thermal_desalination_plant.hot_water_return_temperature
                    is not None
                    else current_ambient_temperature
                )
            ),
            0,
        )
        tank_temperature_map[index] = tank_temperature
        tank_volume_supplied_map[index] = volume_supplied

        if fractional_electric_performance is not None:
            electric_power_per_unit_map[index] = (
                fractional_electric_performance  # type: ignore [operator]
                * solar_thermal_collectors[SolarPanelType.PV_T].pv_unit  # type: ignore [union-attr]
            )

    # @@@ Fractional electrical performance map is not saving entries for non times.

    logger.info(
        "Hourly %s %s%s%s performance calculation complete.",
        resource_type.value,
        SolarPanelType.PV_T.value if scenario.pv_t else "",
        " and " if scenario.pv_t and scenario.solar_thermal else "",
        SolarPanelType.SOLAR_THERMAL.value if scenario.solar_thermal else "",
    )

    # Convert these outputs to dataframes and return.
    auxiliary_heating_frame: pd.DataFrame = dict_to_dataframe(
        auxiliary_heating_map, logger
    )

    collector_input_temperature_frame: pd.DataFrame = pd.DataFrame(
        collector_input_temperature_map
    )
    collector_input_temperature_frame.columns = [
        key.value for key in collector_input_temperature_map.keys()
    ]

    collector_output_temperature_frame: pd.DataFrame = pd.DataFrame(
        collector_output_temperature_map
    )
    collector_output_temperature_frame.columns = [
        key.value for key in collector_output_temperature_map.keys()
    ]

    collector_reduced_temperatures_frame = pd.DataFrame(
        {k.value: v for k, v in collector_reduced_temperatures_map.items()}
    )

    collector_system_output_temperature_frame = dict_to_dataframe(
        collector_system_output_temperature_map, logger
    ).reset_index(drop=True)

    collector_thermal_efficiencies_frame = pd.DataFrame(
        {k.value: v for k, v in collector_thermal_efficiencies_map.items()}
    )

    electric_power_per_unit: pd.DataFrame = dict_to_dataframe(
        electric_power_per_unit_map, logger
    ).reset_index(drop=True)

    pump_times_frame: pd.DataFrame = dict_to_dataframe(
        pump_times_map, logger
    ).reset_index(drop=True)

    renewable_heating_frame: pd.DataFrame = dict_to_dataframe(
        renewable_heating_map, logger
    ).reset_index(drop=True)

    tank_temperature_frame: pd.DataFrame = dict_to_dataframe(
        tank_temperature_map, logger
    ).reset_index(drop=True)

    tank_volume_output_supplied: pd.DataFrame = dict_to_dataframe(
        tank_volume_supplied_map, logger
    ).reset_index(drop=True)

    # import seaborn as sns

    # sns.set_style("ticks")
    # sns.set_context("notebook")
    # thesis_traffic_lights = sns.color_palette(
    #     [
    #         "#144E56",
    #         "#27BFE6",  # SDG 6
    #         "#EFF2DD",
    #         "#F9A130",
    #         "#E04606",
    #         "#D8247C",  # Pink
    #         "#EDEDED",  # Pale pink
    #         "#E7DFBE",  # Pale yellow
    #     ]
    # )
    # sns.set_palette(thesis_traffic_lights)

    # un_color_palette = sns.color_palette(
    #     [
    #         # "#C51A2E",
    #         # "#ED6A30",
    #         # "#FBC219",
    #         # "#2CBCE0",
    #         # "#2297D5",
    #         # "#0D699F",
    #         # "#19496A",
    #         "#8F1838",
    #         "#D9302F",
    #         "#F36D25",
    #         "#FDB713",
    #         "#00AED9",
    #         "#0169A4",
    #         "#183668",
    #     ]
    # )
    # sns.set_palette(un_color_palette)

    # import matplotlib.pyplot as plt

    # pvt_temperature_frame = pd.DataFrame(
    #     {
    #         "input": collector_input_temperature_frame["pv_t"].values,
    #         "output": collector_output_temperature_frame["pv_t"].values,
    #     }
    # )
    # st_temperature_frame = pd.DataFrame(
    #     {
    #         "input": collector_input_temperature_frame["solar_thermal"].values,
    #         "output": collector_output_temperature_frame["solar_thermal"].values,
    #     }
    # )

    # plt.figure(figsize=(48 / 5, 32 / 5))
    # sns.scatterplot(pvt_temperature_frame[:24], marker="h", palette="Blues", s=100)
    # sns.scatterplot(st_temperature_frame[:24], marker="h", palette="Reds", s=100)
    # plt.plot(tank_temperature_frame[:24].index, tank_temperature_frame[:24].values, dashes=(2, 2), color="teal", label="Tank")
    # plt.fill_between(
    #     pvt_temperature_frame[:24].index,
    #     pvt_temperature_frame[:24]["input"],
    #     pvt_temperature_frame[:24]["output"],
    #     color="blue",
    #     alpha=0.3,
    # )
    # plt.fill_between(
    #     st_temperature_frame[:24].index,
    #     st_temperature_frame[:24]["input"],
    #     st_temperature_frame[:24]["output"],
    #     color="red",
    #     alpha=0.3,
    # )
    # plt.show()

    # pvt_temperature_frame["hour"] = pvt_temperature_frame.index % 24
    # st_temperature_frame["hour"] = st_temperature_frame.index % 24
    # tank_temperature_frame["hour"] = tank_temperature_frame.index % 24

    # plt.figure(figsize=(48/5, 32/5))

    # plt.plot((mean_pvt_frame:=pvt_temperature_frame.groupby("hour").mean()).index, mean_pvt_frame["input"], "--", color="C6", label="Input")
    # plt.fill_between((std_pvt_frame:=pvt_temperature_frame.groupby("hour").std()).index, (mean_pvt_frame - std_pvt_frame)["input"], (mean_pvt_frame + std_pvt_frame)["input"], color="C6", alpha=0.2)

    # plt.plot(mean_pvt_frame.index, mean_pvt_frame["output"], color="C2", label="Output")
    # plt.fill_between(std_pvt_frame.index, (mean_pvt_frame - std_pvt_frame)["output"], (mean_pvt_frame + std_pvt_frame)["output"], color="C2", alpha=0.2)

    # plt.xlabel("Hour of the day / hour")
    # plt.ylabel("Temperature / $^\circ$C")
    # plt.legend()

    # plt.show()

    # plt.figure(figsize=(48/5, 32/5))

    # plt.plot((mean_st_frame:=st_temperature_frame.groupby("hour").mean()).index, mean_st_frame["input"], "--", color="C4")
    # plt.fill_between((std_st_frame:=st_temperature_frame.groupby("hour").std()).index, (mean_st_frame - std_st_frame)["input"], (mean_st_frame + std_st_frame)["input"], color="C4", alpha=0.2)

    # plt.plot(mean_st_frame.index, mean_st_frame["output"], color="C0")
    # plt.fill_between(std_st_frame.index, (mean_st_frame - std_st_frame)["output"], (mean_st_frame + std_st_frame)["output"], color="C0", alpha=0.2)

    # plt.xlabel("Hour of the day / hour")
    # plt.ylabel("Temperature / $^\circ$C")
    # plt.legend()

    # plt.show()

    # plt.figure(figsize=(48/5, 32/5))

    # plt.plot(mean_pvt_frame.index, mean_pvt_frame["input"], "--", color="C6", label="Collector-system (PV-T) input")
    # plt.fill_between(std_pvt_frame.index, (mean_pvt_frame - std_pvt_frame)["input"], (mean_pvt_frame + std_pvt_frame)["input"], color="C6", alpha=0.2)
    # # plt.plot(mean_st_frame.index, mean_st_frame["input"], color="C2")
    # # plt.fill_between(std_st_frame.index, (mean_st_frame - std_st_frame)["input"], (mean_st_frame + std_st_frame)["input"], color="C2", alpha=0.2)

    # plt.plot(mean_pvt_frame.index, mean_pvt_frame["output"], ":", color="C2", label="PV-T output/ST input")
    # plt.fill_between(std_pvt_frame.index, (mean_pvt_frame - std_pvt_frame)["output"], (mean_pvt_frame + std_pvt_frame)["output"], color="C2", alpha=0.2)
    # plt.plot(mean_st_frame.index, mean_st_frame["output"], color="C0", label="Collector-system (ST) output")
    # plt.fill_between(std_st_frame.index, (mean_st_frame - std_st_frame)["output"], (mean_st_frame + std_st_frame)["output"], color="C0", alpha=0.2)

    # plt.plot((mean_tank_frame:=tank_temperature_frame.groupby("hour").mean()).index, mean_tank_frame.values, "-.", color="C3", label="Buffer tank")
    # plt.fill_between((std_tank_frame:=tank_temperature_frame.groupby("hour").std()).index, (mean_tank_frame - std_tank_frame)[0], (mean_tank_frame + std_tank_frame)[0], color="C3", alpha=0.2)

    # plt.fill_between((x_series:=std_tank_frame.index), [thermal_desalination_plant.minimum_htf_temperature] * len(x_series), [thermal_desalination_plant.maximum_htf_temperature] * len(x_series), color="grey", alpha=0.1, hatch="//", label="Required temperature range")

    # plt.xlabel("Hour of the day / hour")
    # plt.ylabel("Temperature / $^\circ$C")
    # plt.legend()

    # plt.show()

    # pvt_thermal_efficiency_frame = pd.DataFrame({"eta": collector_thermal_efficiencies_frame["pv_t"].values, "t_r": collector_reduced_temperatures_frame["pv_t"].values})
    # st_thermal_efficiency_frame = pd.DataFrame({"eta": collector_thermal_efficiencies_frame["solar_thermal"].values, "t_r": collector_reduced_temperatures_frame["solar_thermal"].values})

    # sns.set_palette(sns.color_palette(["teal", "orange"]))

    # plt.figure(figsize=(48 / 5, 32 / 5))
    # sns.scatterplot(pvt_thermal_efficiency_frame, x="t_r", y="eta", marker="D", alpha=0.1, s=100)
    # sns.scatterplot(st_thermal_efficiency_frame, x="t_r", y="eta", marker="D", alpha=0.1, s=100)
    # plt.show()

    return (
        auxiliary_heating_frame,
        collector_input_temperature_frame,
        collector_output_temperature_frame,
        collector_reduced_temperatures_frame,
        collector_thermal_efficiencies_frame,
        electric_power_per_unit,
        collector_system_output_temperature_frame,
        pump_times_frame,
        renewable_heating_frame,
        tank_temperature_frame,
        tank_volume_output_supplied,
    )


def _calculate_direct_heating_solar_thermal_output(  # pylint: disable=too-many-locals
    collector_system_sizes: dict[SolarPanelType, int],
    disable_tqdm: bool,
    end_hour: int,
    irradiances: pd.Series,
    logger: Logger,
    processed_total_hw_load: pd.Series | None,
    relevant_scenarios: dict[SolarPanelType, ThermalCollectorScenario],
    resource_type: ResourceType,
    solar_thermal_collectors: dict[SolarPanelType, HybridPVTPanel | SolarThermalPanel],
    start_hour: int,
    temperatures: pd.Series,
    thermal_scenario: DesalinationScenario | HotWaterScenario,
    wind_speeds: pd.Series,
) -> tuple[
    dict[SolarPanelType, pd.DataFrame],
    dict[SolarPanelType, pd.DataFrame],
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    None,
    pd.DataFrame,
]:
    """
    Computes the output of a direct-heating solar-thermal system.

    For direct-heating solar-thermal systems, the HTF which is passing through the
    collectors is directly fed into the output. I.E., it passes only once through the
    collectors.

    Inputs:
        - collector_system_sizes:
            The size of the PV-T or solar-thermal system being modelled.
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - end_hour:
            The end hour for the simulation being carried out.
        - irradiances:
            The :class:`pd.Series` containing irradiance information for the time
            period being modelled.
        - logger:
            The logger to use for the run.
        - processed_total_hw_load:
            The total hot-water load placed on the system, measured in litres per hour.
        - resource_type:
            The resource type for which the PV-T output is being determined.
        - solar_thermal_collectors:
            The solar-thermal collector(s) to model, either a solar-thermal collector as
            a `list` of :class:`SolarThermalPanel` or :class:`HybridPVTPanel` instances.
        - start_hour:
            The start hour for the simulation being carried out.
        - temperatures:
            The :class:`pd.Series` containing temperature information for the time
            period being modelled.
        - thermal_scenario:
            The :class:`DeslinationScenario` or :class:`HotWaterScenario` being considered.
        - wind_speeds:
            The :class:`pd.Series` containing wind-speed information for the time period
            being modelled.

    Outputs:
        - collector_input_temperature:
            The input temperature of the HTF entering the PV-T/solar-thermal collectors
            at each time step.
        - collector_output_temperature:
            The output temperature of HTF leaving the PV-T/solar-thermal collectors at
            each time step.
        - electric_power_per_unit:
            The electric power, per unit PV-T or solar-thermal collector, delivered by
            the PV-T/solar-thermal system.
        - output_temperature:
            The output temperatures throughout the simulation, measured in degrees
            Celsius.
        - pump_times_frame:
            The times for which the PV-T/solar-thermal HTF pump was switched on.
        - tank_temperature:
            The tank temperatures throughout the simulation, measured in degrees
            Celsius.
        - volume_supplied:
            The amount of hot water supplied by the system, measured in litres.

    """

    # Raise an error if both are present and a throughput is not specified.
    if (
        len(solar_thermal_collectors) > 1
        and thermal_scenario.throughput_mass_flow_rate is None
    ):
        logger.error(
            "%sThroughput mass flow rate not specified despite multiple collector "
            "types being requested.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            f"{resource_type.value.replace('_', ' ')} scenario",
            "Throughput mass flow rate not specified despite multiple collector types "
            "requested.",
        )

    collector_input_temperature: dict[SolarPanelType, dict[int, float]] = {}
    collector_output_temperature: dict[SolarPanelType, dict[int, float]] = {}

    # Determine the PV-T output if present.
    if SolarPanelType.PV_T in solar_thermal_collectors:
        logger.info("Carrying out direct-heating PV-T calculation.")

        # Determine the mass flow rate.
        pvt_collector_mass_flow_rate: float | None = (
            (
                thermal_scenario.throughput_mass_flow_rate
                / collector_system_sizes[SolarPanelType.PV_T]
            )
            if thermal_scenario.throughput_mass_flow_rate is not None
            else thermal_scenario.pvt_scenario.mass_flow_rate
        )
        logger.debug(
            "Mass flow rate through PV-T collectors: %s",
            round(pvt_collector_mass_flow_rate, 2),
        )

        # Calculate the output temperature map from the collector.
        pvt_output_performance: list[tuple[float, float]] = [
            solar_thermal_collectors[SolarPanelType.PV_T].calculate_performance(
                temperatures[index],
                logger,
                relevant_scenarios[SolarPanelType.PV_T].htf_heat_capacity,
                thermal_scenario.htf_supply_temperature,
                pvt_collector_mass_flow_rate,
                1000 * irradiances[index],
                wind_speeds[index],
            )
            for index in tqdm(
                range(start_hour, end_hour),
                desc=f"{resource_type.value.replace('_', ' ')} "
                + f"{SolarPanelType.PV_T.value.replace('_', '-')} performance",
                disable=disable_tqdm,
                leave=False,
                unit="hour",
            )
        ]

        fractional_electrical_performance: dict[int, float] | None = {
            (start_hour + index): float(performance_output[0])
            for index, performance_output in enumerate(pvt_output_performance)
        }
        pvt_output_temperature: dict[int, float] | None = {
            (start_hour + index): float(performance_output[1])
            for index, performance_output in enumerate(pvt_output_performance)
        }

        collector_input_temperature[SolarPanelType.PV_T] = {
            time: thermal_scenario.htf_supply_temperature
            for time in range(start_hour, end_hour)
        }
        collector_output_temperature[SolarPanelType.PV_T] = pvt_output_temperature
        logger.info("Direct-heating PV-T calculation completed.")

    else:
        logger.info("No PV-T collector provided, skipping calcultion.")
        fractional_electrical_performance = None
        pvt_collector_mass_flow_rate = None
        pvt_output_temperature = None

    # Determine the solar-thermal output if present
    if SolarPanelType.SOLAR_THERMAL in solar_thermal_collectors:
        logger.info("Carrying out direct-heating PV-T calculation.")

        # Determine the mass flow rate.
        st_collector_mass_flow_rate: float | None = (
            (
                thermal_scenario.throughput_mass_flow_rate
                / collector_system_sizes[SolarPanelType.SOLAR_THERMAL]
            )
            if thermal_scenario.throughput_mass_flow_rate is not None
            else thermal_scenario.solar_thermal_scenario.mass_flow_rate
        )
        logger.debug(
            "Mass flow rate through solar-thermal collectors: %s",
            round(st_collector_mass_flow_rate, 2),
        )

        # Determine the supply temperature
        solar_thermal_input_temperature: dict[int, float] = (
            pvt_output_temperature
            if pvt_output_temperature is not None
            else {
                time: thermal_scenario.htf_supply_temperature
                for time in range(start_hour, end_hour)
            }
        )

        # Calculate the output temperature map from the collector.
        solar_thermal_output_performance: list[tuple[float | None, float]] = [
            solar_thermal_collectors[
                SolarPanelType.SOLAR_THERMAL
            ].calculate_performance(
                temperatures[index],
                logger,
                relevant_scenarios[SolarPanelType.SOLAR_THERMAL].htf_heat_capacity,
                solar_thermal_input_temperature[index],
                st_collector_mass_flow_rate,
                irradiances[index],
                wind_speeds[index],
            )
            for index in tqdm(
                range(start_hour, end_hour),
                desc=f"{resource_type.value.replace('_', ' ')} "
                + f"{SolarPanelType.SOLAR_THERMAL.value.replace('_', '-')} performance",
                disable=disable_tqdm,
                leave=False,
                unit="hour",
            )
        ]
        solar_thermal_output_temperature: dict[int, float] | None = {
            (start_hour + index): performance_output[1]
            for index, performance_output in enumerate(solar_thermal_output_performance)
        }
        logger.info("Direct-heating solar-thermal calculation completed.")

        collector_input_temperature[
            SolarPanelType.SOLAR_THERMAL
        ] = solar_thermal_input_temperature
        collector_output_temperature[
            SolarPanelType.SOLAR_THERMAL
        ] = solar_thermal_output_temperature

    else:
        logger.info("No solar-thermal collector provided, skipping calcultion.")
        solar_thermal_output_temperature = None
        st_collector_mass_flow_rate = None

    # Determine the flow rate of fluid supplied.
    supply_flow_rate: float = _get_supply_flow_rate(
        collector_system_sizes,
        pvt_collector_mass_flow_rate,
        solar_thermal_collectors,
        st_collector_mass_flow_rate,
        thermal_scenario,
    )
    # Determine the output temperature of fluid supplied.
    if SolarPanelType.SOLAR_THERMAL in collector_output_temperature:
        output_temperature: dict[int, float] = collector_output_temperature[
            SolarPanelType.SOLAR_THERMAL
        ]
    else:
        output_temperature = collector_output_temperature[SolarPanelType.PV_T]

    # Sanitise the output temperature frame
    output_temperature = {
        key: max(value, thermal_scenario.htf_supply_temperature)
        for key, value in output_temperature.items()
    }

    # Determine the pump times: the pump should run if supply is needed or heat is
    # gained.
    pump_times = {
        time: processed_total_hw_load[time] > 0 for time in range(start_hour, end_hour)
    }

    volume_supplied: dict[int, float] = {
        time: min(processed_total_hw_load[time], supply_flow_rate)
        for time in range(start_hour, end_hour)
    }

    # Cast everything to expected type outputs
    collector_input_temperature_frame_map = {
        key: dict_to_dataframe(value, logger).reset_index(drop=True)
        for key, value in collector_input_temperature.items()
    }
    collector_output_temperature_frame_map = {
        key: dict_to_dataframe(value, logger).reset_index(drop=True)
        for key, value in collector_output_temperature.items()
    }
    electric_power_per_unit = (
        dict_to_dataframe(fractional_electrical_performance, logger).reset_index(
            drop=True
        )
        if fractional_electrical_performance is not None
        else None
    )
    output_temperature_frame = dict_to_dataframe(
        output_temperature, logger
    ).reset_index(drop=True)
    pump_times_frame = dict_to_dataframe(pump_times, logger).reset_index(drop=True)
    volume_supplied_frame = dict_to_dataframe(volume_supplied, logger).reset_index(
        drop=True
    )

    return (
        collector_input_temperature_frame_map,
        collector_output_temperature_frame_map,
        electric_power_per_unit,
        output_temperature_frame,
        pump_times_frame,
        None,
        volume_supplied_frame,
    )


def calculate_solar_thermal_output(  # pylint: disable=too-many-locals, too-many-statements
    collector_system_sizes: dict[SolarPanelType, int],
    disable_tqdm: bool,
    end_hour: int,
    irradiances: dict[SolarPanel, pd.Series],
    logger: Logger,
    minigrid: Minigrid,
    num_tanks: int,
    processed_total_hw_load: pd.Series | None,
    resource_type: ResourceType,
    scenario: Scenario,
    solar_thermal_collectors: list[
        SolarPanelType, HybridPVTPanel | SolarThermalPanel | None
    ],
    start_hour: int,
    temperatures: dict[SolarPanel, pd.Series],
    thermal_desalination_plant: ThermalDesalinationPlant | None,
    wind_speeds: pd.Series,
) -> tuple[
    dict[SolarPanelType, pd.DataFrame],
    dict[SolarPanelType, pd.DataFrame],
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame | None,
    pd.DataFrame,
]:
    """
    Computes the output of a solar-thermal system, either PV-T or solar-thermal.

    Solar-thermal-based systems can either heat water directly for consumption as hot
    water, or can heat a heat-transfer fluid (HTF) which is never used and whose only
    purpose is to transmit heat from the collectors to a storage vessel.

    This function, depending on the above scenarios, checks the various inputs and calls
    the appropriate calculation function.

    Inputs:
        - collector_system_sizes:
            The size of the PV-T or solar-thermal system being modelled.
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - end_hour:
            The end hour for the simulation being carried out.
        - irradiances:
            The :class:`pd.Series` containing irradiance information for the time
            period being modelled.
        - logger:
            The logger to use for the run.
        - minigrid:
            The minigrid being modelled currently.
        - num_tanks:
            The number of hot-water tanks being modelled currently, which can either be
            buffer tanks (for desalination systems), or hot-water tanks (for hot-water
            systems).
        - processed_total_hw_load:
            The total hot-water load placed on the system, measured in litres per hour.
        - resource_type:
            The resource type for which the PV-T output is being determined.
        - scenario:
            The :class:`Scenario` being considered.
        - solar_thermal_collectors:
            The solar-thermal collectors to model, either a solar-thermal collector as a
            :class:`SolarThermalPanel` instance, or a :class:`HybridPVTPanel` instance.
            These are stored as a `list` to allow for multiple collectors to be
            considered.
        - start_hour:
            The start hour for the simulation being carried out.
        - temperatures:
            The :class:`pd.Series` containing temperature information for the time
            period being modelled.
        - thermal_desalination_plant:
            The thermal desalination plant being considered.
        - wind_speeds:
            The :class:`pd.Series` containing wind-speed information for the time period
            being modelled.

    Outputs:
        - auxiliary_heating_frame
            The auxiliary heating requirements in kWh, either electrical or thermal.
        - collector_input_temperature:
            The input temperature of the HTF entering the PV-T/solar-thermal collectors
            at each time step.
        - collector_output_temperature:
            The output temperature of HTF leaving the PV-T/solar-thermal collectors at
            each time step.
        - collector_reduced_temperatures_frame:
            The reduced temperatures of the collectors.
        - collector_thermal_efficiencies_frame:
            The thermal efficiencies of the collectors.
        - electric_power_per_unit:
            The electric power, per unit PV-T or solar-thermal collector, delivered by
            the PV-T/solar-thermal system.
        - output_temperature:
            The output temperatures throughout the simulation, measured in degrees
            Celsius.
        - pump_times_frame:
            The times for which the PV-T/solar-thermal HTF pump was switched on.
        - tank_temperature:
            The tank temperatures throughout the simulation, measured in degrees
            Celsius.
        - volume_supplied:
            The amount of hot water supplied by the system, measured in litres.

    Raises:
        - InputFileError:
            Raised if there are issues in the input files.

    """

    # Determine the relevant scenario for each collector.
    relevant_collector_scenarios: dict[SolarPanelType, ThermalCollectorScenario] = {
        panel_type: _get_relevant_collector_scenario(resource_type, scenario, collector)
        for panel_type, collector in solar_thermal_collectors.items()
        if collector is not None
    }
    thermal_scenario = _get_relevant_thermal_scenario(resource_type, scenario)

    # Remove unneeded collector information.
    if not scenario.pv_t and SolarPanelType.PV_T in solar_thermal_collectors:
        solar_thermal_collectors.pop(SolarPanelType.PV_T)

    if (
        not scenario.solar_thermal
        and SolarPanelType.SOLAR_THERMAL in solar_thermal_collectors
    ):
        solar_thermal_collectors.pop(SolarPanelType.SOLAR_THERMAL)

    # Check that all collectors have the same HTF mode.
    if (
        len(
            {
                collector_scenario.heats
                for collector_scenario in relevant_collector_scenarios.values()
            }
        )
        > 1
    ):
        logger.error(
            "%sMultiple-collector-type flow was requested, but different collectors "
            "had different HTF modes within the same scenario. Ensure that each "
            "collector within a single scenario has the same HTF mode.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            f"{resource_type.value} scenario",
            "HTF modes must match across multiple collectors if using series-based "
            "flow.",
        )

    # If a matrix-based equation is required, call the matrix-solving code.
    if all(
        collector_scenario.heats == HTFMode.CLOSED_HTF
        for collector_scenario in relevant_collector_scenarios.values()
    ):
        return _calculate_closed_loop_solar_thermal_output(
            collector_system_sizes,
            disable_tqdm,
            end_hour,
            irradiances,
            logger,
            minigrid,
            num_tanks,
            processed_total_hw_load,
            relevant_collector_scenarios,
            resource_type,
            scenario,
            solar_thermal_collectors,  # type: ignore [arg-type]
            start_hour,
            temperatures,
            thermal_desalination_plant,
            wind_speeds,
        )

    # If a direct-heating calculation is required, simply call the direct-heating code.
    if all(
        collector_scenario.heats == HTFMode.FEEDWATER_HEATING
        for collector_scenario in relevant_collector_scenarios.values()
    ):
        return _calculate_direct_heating_solar_thermal_output(  # type: ignore [no-any-return]
            collector_system_sizes,
            disable_tqdm,
            end_hour,
            irradiances,
            logger,
            processed_total_hw_load,
            relevant_collector_scenarios,
            resource_type,
            solar_thermal_collectors,  # type: ignore [arg-type]
            start_hour,
            temperatures,
            thermal_scenario,
            wind_speeds,
        )

    logger.error(
        "%sUnsupported mode requested: Currently, only %s modes are supported for HTF "
        "heating.%s",
        BColours.fail,
        ", ".join(
            f"{e.value}" for e in (HTFMode.CLOSED_HTF, HTFMode.FEEDWATER_HEATING)
        ),
        BColours.endc,
    )
    raise InputFileError(
        "scenario inputs",
        f"Unsuported heating mode requested. Only {HTFMode.CLOSED_HTF.value} and "
        + f"{HTFMode.FEEDWATER_HEATING} heating modes are supported and all "
        + f"collectors {BColours.bolc}must{BColours.endc} have the same heating mode.",
    )
