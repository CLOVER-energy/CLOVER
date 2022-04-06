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
performance under environmental conditions needs to be calculated.

"""

import collections

from logging import Logger
from typing import Dict, Optional, Tuple

import pandas as pd  # pylint: disable=import-error

from scipy import linalg
from tqdm import tqdm

from ..__utils__ import (
    BColours,
    HTFMode,
    InputFileError,
    InternalError,
    ResourceType,
    Scenario,
    ZERO_CELCIUS_OFFSET,
    dict_to_dataframe,
)
from ..conversion.conversion import ThermalDesalinationPlant
from .__utils__ import Minigrid
from .storage_utils import HotWaterTank


__all__ = ("calculate_pvt_output",)


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


def _htf_fed_buffer_tank_mass_flow_rate(
    ambient_temperature: float,
    best_guess_tank_temperature: float,
    buffer_tank: HotWaterTank,
    thermal_desalination_plant: ThermalDesalinationPlant,
) -> float:
    """
    Computes the mass-flow rate of HTF from the buffer tanks to the desalination plant.

    Inputs:
        - ambient_temperature:
            The ambient temperature, used as the base against which heat is being
            supplied. This is realistic as the final stage of desalination plants can be
            no less than the ambient temprature. This is measured in degrees Celcius.
        - best_guess_tank_temperature:
            The best guess at the tank temperature at the current time step, measured in
            degrees Celcius. This is the temperature at which HTF is removed from the
            tank to supply the desalination plant.
        - buffer_tank:
            The HTF hot-water tank.
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
            * (best_guess_tank_temperature - ambient_temperature)  # [K]
        )
    )  # [kg/hour]


def _volume_withdrawn_from_tank(
    ambient_temperature: float,
    best_guess_tank_temperature: float,
    hot_water_load: Optional[float],
    logger: Logger,
    minigrid: Minigrid,
    previous_tank_temperature: Optional[float],
    resource_type: ResourceType,
    thermal_desalination_plant: Optional[ThermalDesalinationPlant],
) -> Tuple[bool, float]:
    """
    Computes whether the tank is supplying an output, and what this output is.

    Inputs:


    Outputs:
        A `tuple` containing:
        - tank_supply_on:
            Whether liquid was withdrawn from the tank (True) or not (False).
        - volume_supplied:
            The volume supplied, measured in kg/hour.

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
                > thermal_desalination_plant.minimum_htf_temperature
            )
            volume_supplied: float = (
                _htf_fed_buffer_tank_mass_flow_rate(
                    ambient_temperature,
                    best_guess_tank_temperature,
                    minigrid.buffer_tank,
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
        tank_supply_on = hot_water_load > 0
        volume_supplied = hot_water_load

    return tank_supply_on, volume_supplied


def calculate_pvt_output(  # pylint: disable=too-many-locals, too-many-statements
    disable_tqdm: bool,
    end_hour: int,
    irradiances: pd.Series,
    logger: Logger,
    minigrid: Minigrid,
    num_tanks: int,
    processed_total_hw_load: Optional[pd.Series],
    pvt_system_size: int,
    resource_type: ResourceType,
    scenario: Scenario,
    start_hour: int,
    temperatures: pd.Series,
    thermal_desalination_plant: Optional[ThermalDesalinationPlant],
    wind_speeds: pd.Series,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Computes the output of a PV-T system.

    Inputs:
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
        - pvt_system_size:
            The size of the PV-T system being modelled.
        - resource_type:
            The resource type for which the PV-T output is being determined.
        - scenario:
            The :class:`Scenario` being considered.
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
        - pvt_collector_output_temperature:
            The output temperature of the PV-T collectors at each time step.
        - pvt_electric_power_per_unit:
            The electric power, per unit PV-T, delivered by the PV-T system.
        - pvt_pump_times_frame:
            The times for which the PV-T pump was switched on.
        - tank_temperature:
            The tank temperatures throughout the simulation, measured in degrees C.
        - tank_volume_supplied:
            The amount of hot water supplied by the hot-water tanks to the desalination
            system.

    """

    if minigrid.pvt_panel is None:
        logger.error(
            "%sThe energy system does not contain a PV-T panel despite the PV-T output "
            "computation function being called.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "energy system inputs",
            "The energy system specified does not contain a PV-T panel but PV-T "
            "modelling was requested.",
        )
    if minigrid.heat_exchanger is None:
        logger.error(
            "%sThe energy system does not contain a heat exchanger despite the PV-T "
            "output computation function being called which is reliant on the "
            "definition of a heat exchanger.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "energy system inputs",
            "The energy system specified does not contain a heat exchanger but PV-T "
            "modelling was requested for which this is required.",
        )

    # Instantiate debugging variables
    runs: int = 0

    # Instantiate maps for easy PV-T power lookups.
    pvt_electric_power_per_unit_map: Dict[int, float] = {}
    pvt_pump_times_map: Dict[int, int] = {}
    tank_supply_temperature_map: Dict[  # pylint: disable=unused-variable
        int, float
    ] = {}
    tank_volume_supplied_map: Dict[int, float] = {}

    # Compute the various terms which remain common across all time steps.
    if (
        scenario.desalination_scenario is not None
        and resource_type == ResourceType.CLEAN_WATER
    ):
        if minigrid.buffer_tank is None:
            logger.error(
                "%sThe energy system does not contain a buffer tank despite the PV-T "
                "output computation function being called for a clean-water load.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "energy system inputs",
                "The energy system specified does not contain a buffer tank but PV-T "
                "modelling for desalination was requested.",
            )

        default_supply_temperature: float = (
            scenario.desalination_scenario.feedwater_supply_temperature
        )
        mass_flow_rate: float = (
            scenario.desalination_scenario.pvt_scenario.mass_flow_rate
        )
        tank: HotWaterTank = minigrid.buffer_tank

        pvt_heat_transfer: float = (
            pvt_system_size
            * mass_flow_rate  # [kg/hour]
            * scenario.desalination_scenario.pvt_scenario.htf_heat_capacity  # [J/kg*K]
            * minigrid.heat_exchanger.efficiency
            / 3600  # [s/hour]
        )  # [W/K]
        tank_replacement_temperature: float = default_supply_temperature  # [degC]

        # Throw an error if the PV-T is not heating an intermediary HTF.
        if scenario.desalination_scenario.pvt_scenario.heats != HTFMode.CLOSED_HTF:
            logger.error(
                "%sCurrently, closed HTF PV-T modelling is supported only.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "desalination scenario",
                "The PV-T heating mode requested is not supported.",
            )

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

        default_supply_temperature = (
            scenario.hot_water_scenario.cold_water_supply_temperature
        )
        mass_flow_rate = scenario.hot_water_scenario.pvt_scenario.mass_flow_rate
        tank = minigrid.hot_water_tank

        pvt_heat_transfer = (
            pvt_system_size
            * mass_flow_rate  # [kg/hour]
            * scenario.hot_water_scenario.pvt_scenario.htf_heat_capacity  # [J/kg*K]
            * minigrid.heat_exchanger.efficiency
            / 3600  # [s/hour]
        )  # [W/K]
        tank_replacement_temperature = default_supply_temperature  # [degC]

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

    best_guess_collector_input_temperature: float = default_supply_temperature
    pvt_collector_output_temperature_map: Dict[int, float] = collections.defaultdict(
        lambda: default_supply_temperature
    )
    tank_environment_heat_transfer: float = (
        num_tanks * tank.heat_transfer_coefficient
    )  # [W/K]
    tank_internal_energy: float = (
        num_tanks
        * tank.mass
        * tank.heat_capacity
        / 3600  # [kg]  # [J/kg*K]  # [s/hour]
    )  # [W/K]
    tank_temperature_map: Dict[int, float] = collections.defaultdict(
        lambda: default_supply_temperature
    )

    logger.info(
        "Beggining hourly %s PV-T performance calculation.", resource_type.value
    )
    for index in tqdm(
        range(start_hour, end_hour),
        desc=f"{resource_type.value.replace('_', ' ')} pv-t performance",
        disable=disable_tqdm,
        leave=False,
        unit="hour",
    ):
        # Determine whether the PV-T is flowing.
        if index > start_hour:
            pvt_flow_on: bool = (
                pvt_collector_output_temperature_map[index - 1]
                > tank_temperature_map[index - 1]
            ) and irradiances[index] > 0
        else:
            pvt_flow_on = False

        previous_tank_temperature: float = (
            tank_temperature_map[index - 1]
            if index > start_hour
            else default_supply_temperature
        )

        # Determine the volume withdrawn from the buffer tanks
        tank_supply_on, volume_supplied = _volume_withdrawn_from_tank(
            temperatures[index],
            previous_tank_temperature,
            processed_total_hw_load[index]
            if processed_total_hw_load is not None
            else None,
            logger,
            minigrid,
            previous_tank_temperature,
            resource_type,
            thermal_desalination_plant,
        )

        # Only compute outputs if there is input irradiance.
        solution_found: bool = False
        # Keep processing until the temperatures are consistent.
        while not solution_found:
            # Use the AI to determine the output temperature of the collector, based on
            # the best guess of the collector input temperature.
            if irradiances[index] > 0:
                (
                    fractional_electric_performance,
                    collector_output_temperature,
                ) = minigrid.pvt_panel.calculate_performance(
                    temperatures[index],
                    best_guess_collector_input_temperature,
                    logger,
                    mass_flow_rate,
                    1000 * irradiances[index],
                    wind_speeds[index],
                )
            else:
                fractional_electric_performance = 0
                collector_output_temperature = default_supply_temperature

            tank_load_enthalpy_transfer = (
                volume_supplied  # [kg/hour]
                * tank.heat_capacity  # [J/kg*K]
                / 3600  # [s/hour]
            )  # [W/K]

            # Determine the tank temperature and collector input temperature that match.
            resultant_vector = [
                (
                    pvt_heat_transfer
                    * (collector_output_temperature + ZERO_CELCIUS_OFFSET)
                    if pvt_flow_on
                    else 0
                )
                + tank_environment_heat_transfer
                * (temperatures[index] + ZERO_CELCIUS_OFFSET)
                + tank_internal_energy
                * (previous_tank_temperature + ZERO_CELCIUS_OFFSET)
                + (
                    tank_load_enthalpy_transfer
                    * (tank_replacement_temperature + ZERO_CELCIUS_OFFSET)
                    if tank_supply_on
                    else 0
                ),
                (
                    (1 - minigrid.heat_exchanger.efficiency)
                    * (collector_output_temperature + ZERO_CELCIUS_OFFSET)
                ),
            ]

            matrix = [
                [
                    0,
                    (
                        (pvt_heat_transfer if pvt_flow_on else 0)
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

            # Convert into Celcius.
            collector_input_temperature -= ZERO_CELCIUS_OFFSET
            tank_temperature -= ZERO_CELCIUS_OFFSET

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
                    "Index: %s: Run # %s: PV-T=%s, Plant=%s: Solution not yet found, "
                    "re-iterating: T_c,in=%s degC, best-guess T_c,in=%s degC, "
                    "T_tank=%s degC",
                    index,
                    runs,
                    "on" if pvt_flow_on else "off",
                    "on" if tank_supply_on else "off",
                    round(collector_input_temperature, 3),
                    round(best_guess_collector_input_temperature, 3),
                    round(tank_temperature, 3),
                )
            best_guess_collector_input_temperature = collector_input_temperature

        # Save the fractional electrical performance and output temp.
        pvt_collector_output_temperature_map[index] = collector_output_temperature
        pvt_electric_power_per_unit_map[index] = (
            fractional_electric_performance * minigrid.pvt_panel.pv_unit
        )
        pvt_pump_times_map[index] = int(pvt_flow_on)
        tank_temperature_map[index] = tank_temperature
        tank_volume_supplied_map[index] = volume_supplied

    logger.info("Hourly %s PV-T performance calculation complete.", resource_type.value)

    # Convert these outputs to dataframes and return.
    pvt_collector_output_temperature: pd.DataFrame = dict_to_dataframe(
        pvt_collector_output_temperature_map, logger
    )
    pvt_electric_power_per_unit: pd.DataFrame = dict_to_dataframe(
        pvt_electric_power_per_unit_map, logger
    )
    pvt_pump_times_frame: pd.DataFrame = dict_to_dataframe(pvt_pump_times_map, logger)
    tank_temperature_frame: pd.DataFrame = dict_to_dataframe(
        tank_temperature_map, logger
    )
    tank_volume_output_supplied: pd.DataFrame = dict_to_dataframe(
        tank_volume_supplied_map, logger
    )

    return (
        pvt_collector_output_temperature,
        pvt_electric_power_per_unit,
        pvt_pump_times_frame,
        tank_temperature_frame,
        tank_volume_output_supplied,
    )
