#!/usr/bin/python3
########################################################################################
# minigrid.py - Energy-system main module for CLOVER.                                  #
#                                                                                      #
# Authors: Phil Sandwell, Ben Winchester                                               #
# Copyright: Phil Sandwell, 2018                                                       #
# Date created: 13/07/2021                                                             #
# License: Open source                                                                 #
#                                                                                      #
# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
minigrid.py - The energy-system module for CLOVER.

This module carries out a simulation for an energy system based on the various inputs
and profile files that have been parsed/generated.

"""

import datetime
import math

from logging import Logger
from re import L, T
from typing import Dict, List, Optional, Tuple, Union

import numpy as np  # pylint: disable=import-error
import pandas as pd  # pylint: disable=import-error

from tqdm import tqdm

from ..__utils__ import (
    AuxiliaryHeaterType,
    BColours,
    CleanWaterMode,
    ColdWaterSupply,
    DieselMode,
    DemandType,
    DistributionNetwork,
    HTFMode,
    InputFileError,
    InternalError,
    RenewableEnergySource,
    ResourceType,
    Location,
    Scenario,
    Simulation,
    SystemDetails,
    dict_to_dataframe,
)
from ..conversion.conversion import Convertor, ThermalDesalinationPlant, WaterSource
from ..generation.solar import SolarPanelType, solar_degradation
from ..load.load import HOT_WATER_USAGE, population_hourly
from .__utils__ import Minigrid
from .diesel import (
    DieselWaterHeater,
    get_diesel_energy_and_times,
    get_diesel_fuel_usage,
)
from .solar import calculate_pvt_output
from .storage import CleanWaterTank

__all__ = (
    "Minigrid",
    "run_simulation",
)


def _battery_iteration_step(
    battery_storage_profile: pd.DataFrame,
    hourly_battery_storage: Dict[int, float],
    initial_battery_storage: float,
    logger: Logger,
    maximum_battery_storage: float,
    minigrid: Minigrid,
    minimum_battery_storage: float,
    *,
    time_index: int,
) -> Tuple[float, float, float]:
    """
    Carries out an iteration calculation for the battery.

    Inputs:
        - battery_storage_profile:
            The battery storage profile, as a :class:`pandas.DataFrame`, giving the net
            flow into and out of the battery due to renewable electricity generation.
        - hourly_battery_storage:
            The mapping between time and computed battery storage.
        - initial_battery_storage:
            The initial amount of energy stored in the batteries.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - maximum_battery_storage:
            The maximum amount of energy that can be stored in the batteries.
        - minigrid:
            The :class:`Minigrid` representing the system being considered.
        - minimum_battery_storage:
            The minimum amount of energy that can be stored in the batteries.
        - time_index:
            The current time (hour) being considered.

    Outputs:
        - battery_energy_flow:
            The net flow into or out of the battery.
        - excess_energy:
            The energy surplus generated which could not be stored in the batteries.
        - new_hourly_battery_storage;
            The computed level of energy stored in the batteries at this time step.

    """

    if minigrid.battery is None:
        logger.error(
            "%sNo battery was defined on the minigrid despite the iteration "
            "calculation being called to compute the energy stored within the "
            "batteries. Either define a valid battery for the energy system, or adjust "
            "the scenario to no longer consider battery inputs.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "energy system inputs",
            "Battery undefined despite an itteration step being called.",
        )

    battery_energy_flow = battery_storage_profile.iloc[time_index, 0]
    if time_index == 0:
        new_hourly_battery_storage = initial_battery_storage + battery_energy_flow
    else:
        # Battery charging
        if battery_energy_flow >= 0.0:
            new_hourly_battery_storage = hourly_battery_storage[time_index - 1] * (
                1.0 - minigrid.battery.leakage
            ) + minigrid.battery.conversion_in * min(
                battery_energy_flow,
                minigrid.battery.charge_rate
                * (maximum_battery_storage - minimum_battery_storage),
            )
        # Battery discharging
        else:
            new_hourly_battery_storage = hourly_battery_storage[time_index - 1] * (
                1.0 - minigrid.battery.leakage
            ) + (1.0 / minigrid.battery.conversion_out) * max(
                battery_energy_flow,
                (-1.0)
                * minigrid.battery.discharge_rate
                * (maximum_battery_storage - minimum_battery_storage),
            )

    excess_energy = max(new_hourly_battery_storage - maximum_battery_storage, 0.0)

    return battery_energy_flow, excess_energy, new_hourly_battery_storage


def _calculate_backup_diesel_generator_usage(
    blackout_times: pd.DataFrame,
    minigrid: Minigrid,
    scenario: Scenario,
    unmet_energy: pd.DataFrame,
) -> Tuple[float, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Calculates the backup diesel generator usage based on the scenario.

    Inputs:
        - blackout_times:
            The times for which the system experienced a blackout.
        - minigrid:
            The :class:`Minigrid` being considered.
        - scenario:
            The :class:`Scenario` being used for the run.
        - unmet_energy:
            The energy demand which went unmet through renewables.

    Outputs:
        - diesel_capacity:
            The capacity of diesel that needed to be installed to meet the demand.
        - diesel_energy:
            The total energy that was supplied by the diesel system.
        - diesel_fuel_usage:
            The total amount of fuel that was consumed byt he diesel generators.
        - diesel_times:
            The times forw hich the diesel generator was operating.
        - unmet_energy:
            The remaining energy demand which went uynmet after the diesel generator
            fulfilled demand to the :class:`Scenario`'s specification.

    """

    if scenario.diesel_scenario.backup_threshold is None:
        raise InputFileError(
            "diesel inputs",
            "Diesel mode `backup` was selected but no backup threshold was "
            "specified.",
        )
    if minigrid.diesel_generator is None:
        raise InputFileError(
            "energy system inputs",
            "No backup diesel generato was provided on the energy system despite "
            "the diesel mode `backup` being selected.",
        )
    diesel_energy, diesel_times = get_diesel_energy_and_times(
        unmet_energy,
        blackout_times,
        float(scenario.diesel_scenario.backup_threshold),
    )
    diesel_capacity: float = float(math.ceil(np.max(diesel_energy)))
    diesel_fuel_usage = pd.DataFrame(
        get_diesel_fuel_usage(
            int(diesel_capacity),
            minigrid.diesel_generator,
            diesel_energy,
            diesel_times,
        ).values
    )
    unmet_energy = pd.DataFrame(unmet_energy.values - diesel_energy.values)
    diesel_energy = diesel_energy.abs()  # type: ignore

    return diesel_capacity, diesel_energy, diesel_fuel_usage, diesel_times, unmet_energy


def _calculate_electric_desalination_parameters(
    convertors: List[Convertor],
    feedwater_sources: List[Convertor],
    logger: Logger,
    scenario: Scenario,
) -> Tuple[List[Convertor], float, float]:
    """
    Calculates parameters needed for computing electric desalination.

    Inputs:
        - convertors:
            The `list` of :class:`Convertor` instances defined for the system.
        - feedwater_sources:
            The `list` of :class:`WaterSource` instances that produce feedwater as their
            outputs.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenario:
            The :class:`Scenario` for the run.

    Outputs:
        - The `list` of electric desalinators :class:`Convertor` instances defined on
          the system.
        - The electric energy consumed per desalinated litre of water produced.
        - The maximum throughput of the electric desalination system.

    """

    # If the mode is backup or prioritise.
    if (
        scenario.desalination_scenario is not None
        and scenario.desalination_scenario.clean_water_scenario.mode
        in {CleanWaterMode.BACKUP, CleanWaterMode.PRIORITISE}
    ):
        # Initialise deslination convertors.
        electric_desalinators: List[Convertor] = sorted(
            [
                convertor
                for convertor in convertors
                if list(convertor.input_resource_consumption)
                == [ResourceType.ELECTRIC, ResourceType.UNCLEAN_WATER]
                and convertor.output_resource_type == ResourceType.CLEAN_WATER
            ]
        )

        # Raise an error if there were no electric desalinators defined.
        if len(electric_desalinators) == 0:
            logger.error(
                "%sNo electric desalinators defined despite the desalination mode being %s%s",
                BColours.fail,
                scenario.desalination_scenario.clean_water_scenario.mode.value,
                BColours.endc,
            )
            raise InputFileError(
                "desalination scenario",
                "No electric desalination devices defined but are required by the scenario.",
            )
        logger.debug(
            "Electric desalinators: %s",
            ", ".join(str(entry) for entry in electric_desalinators),
        )

        # Compute the amount of energy required per litre desalinated.
        energy_per_desalinated_litre: float = 0.001 * np.mean(
            [
                desalinator.input_resource_consumption[ResourceType.ELECTRIC]
                / desalinator.maximum_output_capacity
                + desalinator.input_resource_consumption[ResourceType.UNCLEAN_WATER]
                * feedwater_sources[0].input_resource_consumption[ResourceType.ELECTRIC]
                / desalinator.maximum_output_capacity
                for desalinator in electric_desalinators
            ]
        )

        # Compute the maximum throughput
        maximum_water_throughput: float = min(
            sum(
                [
                    desalinator.maximum_output_capacity
                    for desalinator in electric_desalinators
                ]
            ),
            sum([source.maximum_output_capacity for source in feedwater_sources]),
        )
    else:
        electric_desalinators = []
        energy_per_desalinated_litre = 0
        maximum_water_throughput = 0

    return electric_desalinators, energy_per_desalinated_litre, maximum_water_throughput


def _calculate_renewable_clean_water_profiles(
    convertors: List[Convertor],
    end_hour: int,
    irradiance_data: pd.Series,
    logger: Logger,
    minigrid: Minigrid,
    pvt_size: int,
    scenario: Scenario,
    start_hour: int,
    temperature_data: pd.Series,
    wind_speed_data: Optional[pd.Series],
) -> Tuple[
    Optional[pd.DataFrame],
    pd.DataFrame,
    List[Convertor],
    Optional[pd.DataFrame],
    pd.DataFrame,
    pd.DataFrame,
    List[Convertor],
    pd.DataFrame,
]:
    """
    Calculates PV-T related profiles.

    Inputs:
        - convertors:
            The `list` of :class:`Convertor` instances available to be used.
        - end_hour:
            The final hour for which the simulation will be carried out.
        - irradiance_data:
            The total solar irradiance data.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - minigrid:
            The energy system being considered.
        - pvt_size:
            Amount of PV-T in PV-T units.
        - scenario:
            The scenario being considered.
        - start_hour:
            The first hour for which the simulation will be carried out.
        - temperature_data:
            The temperature data series.
        - wind_speed_data:
            The wind-speed data series.

    Outputs:
        - buffer_tank_temperature:
            The temperature of the buffer tank, measured in degrees Celcius.
        - buffer_tank_volume_supplied:
            The volume of buffer solution outputted by the HTF buffer tanks.
        - feedwater_sources:
            The :class:`Convertor` instances which are a source of feedwater to the PV-T
            system.
        - clean_water_pvt_collector_output_temperature:
            The output temperature of HTF from the PV-T collectors, measured in degrees
            Celcius.
        - clean_water_pvt_electric_power_per_unit:
            The electric power produced by the PV-T, in kWh, per unit of PV-T installed.
        - renewable_clean_water_produced:
            The amount of clean water produced renewably, measured in litres.
        - required_feedwater_sources:
            The `list` of feedwater sources required to supply the needs of the
            desalination system.
        - thermal_desalination_electric_power_consumed:
            The electric power consumed in operating the thermal desalination plant,
            measured in kWh.

    """

    if scenario.desalination_scenario is not None:
        # Determine the list of available feedwater sources.
        feedwater_sources: List[Convertor] = sorted(
            [
                convertor
                for convertor in convertors
                if list(convertor.input_resource_consumption) == [ResourceType.ELECTRIC]
                and convertor.output_resource_type == ResourceType.UNCLEAN_WATER
            ]
        )
    else:
        feedwater_sources = []

    if scenario.pv_t and scenario.desalination_scenario is not None:
        if wind_speed_data is None:
            raise InternalError(
                "Wind speed data required in PV-T computation and not passed to the "
                "energy system module."
            )
        if minigrid.water_pump is None:
            logger.error(
                "%sNo water pump defined on the minigrid despite PV-T modelling being "
                "requested via the scenario files.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "No water pump defined as part of the energy system despite the PV-T "
                "modelling being requested."
            )

        # Determine the thermal desalination plant being used.
        logger.info("Determining desalination plant.")
        try:
            thermal_desalination_plant: ThermalDesalinationPlant = [
                convertor
                for convertor in convertors
                if isinstance(convertor, ThermalDesalinationPlant)
            ][0]
        except IndexError:
            logger.error(
                "%sNo valid thermal desalination plants specified despite PV-T being "
                "specified.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "conversion inputs", "No valid thermal desalination plants specified."
            ) from None
        logger.info(
            "Desalination plant determined: %s", thermal_desalination_plant.name
        )

        # Determine whether the water pump is capable for supplying the PV-T panels with
        # enough throughput.
        if (
            scenario.desalination_scenario.pvt_scenario.mass_flow_rate * pvt_size
            > minigrid.water_pump.throughput
        ):
            logger.error(
                "%sThe water pump supplied, %s, is incapable of meeting the required "
                "PV-T flow rate of %s litres/hour. Max pump throughput: %s litres/hour."
                "%s",
                BColours.fail,
                minigrid.water_pump.name,
                scenario.desalination_scenario.pvt_scenario.mass_flow_rate * pvt_size,
                minigrid.water_pump.throughput,
                BColours.endc,
            )
            raise InputFileError(
                "transmission inputs",
                "The water pump defined is unable to meet PV-T flow requirements.",
            )

        if thermal_desalination_plant.htf_mode == HTFMode.CLOSED_HTF:
            thermal_desalination_plant_input_type: ResourceType = (
                ResourceType.UNCLEAN_WATER
            )
        if thermal_desalination_plant.htf_mode == HTFMode.FEEDWATER_HEATING:
            thermal_desalination_plant_input_type = ResourceType.HOT_UNCLEAN_WATER
        if thermal_desalination_plant.htf_mode == HTFMode.COLD_WATER_HEATING:
            logger.error(
                "%sCold-water heating thermal desalination plants are not supported.%s",
                BColours.fail,
                BColours.endc,
            )
            InputFileError(
                "convertor inputs OR desalination scenario",
                f"The htf mode '{HTFMode.COLD_WATER_HEATING.value}' is not currently "
                "supported.",
            )

        thermal_desalination_plant_input_flow_rate = (
            thermal_desalination_plant.input_resource_consumption[
                thermal_desalination_plant_input_type
            ]
        )

        if (
            sum(
                [
                    feedwater_source.maximum_output_capacity
                    for feedwater_source in feedwater_sources
                ]
            )
            < thermal_desalination_plant_input_flow_rate
        ):
            logger.error(
                "%sThe feedwater sources are unable to supply enough throughput to "
                "facilitate the thermal desalination plant.%s",
                BColours.fail,
                BColours.endc,
            )
            logger.info(
                "Feedwater sources: %s",
                ", ".join([str(source) for source in feedwater_sources]),
            )
            logger.info("Desalination plant: %s", thermal_desalination_plant)
            raise InputFileError(
                "desalination scenario",
                "The feedwater sources cannot meet the thermal desalination plant input demand.",
            )

        logger.info("Determining required feedwater sources.")
        feedwater_capacity: float = 0
        required_feedwater_sources: List[Convertor] = []
        while (
            feedwater_capacity
            < thermal_desalination_plant.input_resource_consumption[
                thermal_desalination_plant_input_type
            ]
        ):
            required_feedwater_sources.append(feedwater_sources.pop(0))
            feedwater_capacity += required_feedwater_sources[-1].maximum_output_capacity

        feedwater_sources.extend(required_feedwater_sources)
        logger.info("Required feedwater sources determined.")
        logger.debug(
            "Required feedwater sources: %s",
            ", ".join([str(source) for source in required_feedwater_sources]),
        )

        # Compute the output of the PV-T system.
        clean_water_pvt_collector_output_temperature: Optional[pd.DataFrame]
        buffer_tank_temperature: Optional[pd.DataFrame]
        (
            clean_water_pvt_collector_output_temperature,
            clean_water_pvt_electric_power_per_unit,
            clean_water_pvt_pump_times,
            buffer_tank_temperature,
            buffer_tank_volume_supplied,
        ) = calculate_pvt_output(
            end_hour,
            irradiance_data[start_hour:end_hour],
            logger,
            minigrid,
            None,
            pvt_size,
            ResourceType.CLEAN_WATER,
            scenario,
            start_hour,
            temperature_data[start_hour:end_hour],
            thermal_desalination_plant,
            wind_speed_data[start_hour:end_hour],
        )
        logger.info("PV-T performance successfully computed.")

        # Compute the clean water supplied by the desalination unit.
        renewable_clean_water_produced: pd.DataFrame = (
            buffer_tank_volume_supplied > 0
        ) * thermal_desalination_plant.maximum_output_capacity

        # Compute the power consumed by the thermal desalination plant.
        thermal_desalination_electric_power_consumed: pd.DataFrame = pd.DataFrame(
            (
                (renewable_clean_water_produced > 0)
                * (
                    0.001
                    * thermal_desalination_plant.input_resource_consumption[
                        ResourceType.ELECTRIC
                    ]
                    + 0.001
                    * sum(
                        [
                            source.input_resource_consumption[ResourceType.ELECTRIC]
                            for source in required_feedwater_sources
                        ]
                    )
                )
            ).values
            + (clean_water_pvt_pump_times > 0) * 0.001 * minigrid.water_pump.consumption
        )

        buffer_tank_temperature = buffer_tank_temperature.reset_index(drop=True)
        clean_water_pvt_collector_output_temperature = (
            clean_water_pvt_collector_output_temperature.reset_index(drop=True)
        )
        clean_water_pvt_electric_power_per_unit = (
            clean_water_pvt_electric_power_per_unit.reset_index(drop=True)
        )
        renewable_clean_water_produced = renewable_clean_water_produced.reset_index(
            drop=True
        )
        buffer_tank_volume_supplied = buffer_tank_volume_supplied.reset_index(drop=True)
        thermal_desalination_electric_power_consumed = (
            thermal_desalination_electric_power_consumed.reset_index(drop=True)
        )

    else:
        buffer_tank_temperature = None
        buffer_tank_volume_supplied = pd.DataFrame([0] * (end_hour - start_hour))
        clean_water_pvt_collector_output_temperature = None
        clean_water_pvt_electric_power_per_unit = pd.DataFrame(
            [0] * (end_hour - start_hour)
        )
        renewable_clean_water_produced = pd.DataFrame([0] * (end_hour - start_hour))
        required_feedwater_sources = []
        thermal_desalination_electric_power_consumed = pd.DataFrame(
            [0] * (end_hour - start_hour)
        )

    return (
        buffer_tank_temperature,
        buffer_tank_volume_supplied,
        feedwater_sources,
        clean_water_pvt_collector_output_temperature,
        clean_water_pvt_electric_power_per_unit,
        renewable_clean_water_produced,
        required_feedwater_sources,
        thermal_desalination_electric_power_consumed,
    )


def _calculate_renewable_hot_water_profiles(
    convertors: List[Convertor],
    end_hour: int,
    irradiance_data: pd.Series,
    logger: Logger,
    minigrid: Minigrid,
    processed_total_hot_water_load: pd.DataFrame,
    pvt_size: int,
    scenario: Scenario,
    start_hour: int,
    temperature_data: pd.Series,
    wind_speed_data: Optional[pd.Series],
) -> Tuple[
    Optional[Union[Convertor, DieselWaterHeater]],
    pd.DataFrame,
    Optional[pd.DataFrame],
    pd.DataFrame,
    Optional[pd.DataFrame],
    Optional[pd.DataFrame],
    Optional[pd.DataFrame],
]:
    """
    Calculates PV-T related profiles for the hot-water system.

    Inputs:
        - convertors:
            The `list` of :class:`Convertor` instances available to be used.
        - end_hour:
            The final hour for which the simulation will be carried out.
        - irradiance_data:
            The total solar irradiance data.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - minigrid:
            The energy system being considered.
        - processed_total_hot_water_load:
            The total hot-water load placed on the system, defined in litres/hour at
            every time step.
        - pvt_size:
            Amount of PV-T in PV-T units.
        - scenario:
            The scenario being considered.
        - start_hour:
            The first hour for which the simulation will be carried out.
        - temperature_data:
            The temperature data series.
        - wind_speed_data:
            The wind-speed data series.

    Outputs:
        - auxiliary_heater:
            The auxiliary heater associated with the system.
        - hot_water_power_consumed:
            The electric power consumed by the hot-water system, including any water
            pumps and electricity that was used meeting unmet hot-water demand.
        - hot_water_pvt_collector_output_temperature:
            The output temperature from the PV-T panels associated with the hot-water
            system.
        - hot_water_pvt_electric_power_per_unit:
            The electric power produced by the PV-T, in kWh, per unit of PV-T installed.
        - hot_water_tank_temperature:
            The temperature of the hot-water tank, in degrees Celcius, at each time
            step throughout the simulation period.
        - hot_water_tank_volume_supplied:
            The volume of hot-water supplied by the hot-water tank.
        - renewable_hot_water_fraction:
            The fraction of the hot-water demand which was covered using renewables vs
            which was covered using auxiliary means.

    """

    if scenario.pv_t and scenario.hot_water_scenario is not None:
        if wind_speed_data is None:
            raise InternalError(
                "Wind speed data required in PV-T computation and not passed to the "
                "energy system module."
            )

        if scenario.hot_water_scenario.cold_water_supply != ColdWaterSupply.UNLIMITED:
            logger.error(
                "%sOnly '%s' cold-water supplies for the hot-water system are "
                "currently supported.%s",
                BColours.fail,
                ColdWaterSupply.UNLIMITED.value,
                BColours.endc,
            )

        if minigrid.hot_water_tank is None:
            logger.error(
                "%sNo hot-water tank was defined for the minigrid despite hot-water"
                "modelling being requested.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "No water pump defined as part of the energy system despite the PV-T "
                "modelling being requested."
            )

        if minigrid.water_pump is None:
            logger.error(
                "%sNo water pump defined on the minigrid despite PV-T modelling being "
                "requested via the scenario files.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "No water pump defined as part of the energy system despite the PV-T "
                "modelling being requested."
            )

        # Determine whether the water pump is capable for supplying the PV-T panels with
        # enough throughput.
        if (
            scenario.hot_water_scenario.pvt_scenario.mass_flow_rate * pvt_size
            > minigrid.water_pump.throughput
        ):
            logger.error(
                "%sThe water pump supplied, %s, is incapable of meeting the required "
                "PV-T flow rate of %s litres/hour. Max pump throughput: %s litres/hour."
                "%s",
                BColours.fail,
                minigrid.water_pump.name,
                scenario.hot_water_scenario.pvt_scenario.mass_flow_rate * pvt_size,
                minigrid.water_pump.throughput,
                BColours.endc,
            )
            raise InputFileError(
                "transmission inputs",
                "The water pump defined is unable to meet PV-T flow requirements.",
            )

        # Determine the auxiliary heater associated with the system.
        if scenario.hot_water_scenario.auxiliary_heater == AuxiliaryHeaterType.DIESEL:
            auxiliary_heater: Optional[
                Union[Convertor, DieselWaterHeater]
            ] = minigrid.diesel_water_heater
        if scenario.hot_water_scenario.auxiliary_heater == AuxiliaryHeaterType.ELECTRIC:
            try:
                auxiliary_heater = [
                    convertor
                    for convertor in convertors
                    if convertor.output_resource_type == ResourceType.HOT_CLEAN_WATER
                    and ResourceType.ELECTRIC in convertor.input_resource_consumption
                    and ResourceType.CLEAN_WATER in convertor.input_resource_consumption
                ][0]
            except IndexError:
                logger.error(
                    "%sFailed to determine electric water heater despite an electric "
                    "auxiliary hot-water type being selected.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise InputFileError(
                    "energy system inputs OR hot-water scenario",
                    "No electric water heater defined despite the hot-water scenario "
                    "specifying that this is needed.",
                )

        if auxiliary_heater is None:
            logger.error(
                "%sDiesel water heater not defined despite hot-water auxiliary "
                "heating mode being specified as diesel.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "energy system inputs OR hot-water scenario",
                "No diesel hot-water heater defined despite the hot-water "
                "scenario specifying that this is needed.",
            )

        logger.info("Auxiliary heater successfully determined.")
        logger.debug("Auxiliary heater: %s", str(auxiliary_heater))

        # Compute the output of the PV-T system.
        hot_water_pvt_collector_output_temperature: pd.DataFrame
        hot_water_pvt_electric_power_per_unit: pd.DataFrame
        hot_water_pvt_pump_times: pd.DataFrame
        hot_water_tank_temperature: pd.DataFrame
        hot_water_tank_volume_supplied: pd.DataFrame
        (
            hot_water_pvt_collector_output_temperature,
            hot_water_pvt_electric_power_per_unit,
            hot_water_pvt_pump_times,
            hot_water_tank_temperature,
            hot_water_tank_volume_supplied,
        ) = calculate_pvt_output(
            end_hour,
            irradiance_data[start_hour:end_hour],
            logger,
            minigrid,
            processed_total_hot_water_load.iloc[:, 0],
            pvt_size,
            ResourceType.HOT_CLEAN_WATER,
            scenario,
            start_hour,
            temperature_data[start_hour:end_hour],
            None,
            wind_speed_data[start_hour:end_hour],
        )
        logger.info("Hot-water PV-T performance successfully computed.")

        # Compute the heat consumed by the auxiliary heater.
        auxiliary_heater_heat_consumption: pd.DataFrame = pd.DataFrame(
            (hot_water_tank_volume_supplied > 0)
            * hot_water_tank_volume_supplied
            * minigrid.hot_water_tank.heat_capacity
            * (
                scenario.hot_water_scenario.demand_temperature
                - hot_water_tank_temperature
            )
        )

        # Compute the electric power consumed by the auxiliary heater.
        auxiliary_heater_power_consumption: pd.DataFrame = pd.DataFrame(
            0.001
            * auxiliary_heater.input_resource_consumption[
                ResourceType.ELECTRIC
            ]  # [Wh/degC]
            * (
                hot_water_tank_volume_supplied
                / auxiliary_heater.input_resource_consumption[ResourceType.CLEAN_WATER]
            )  # [operating fraction]
            * (hot_water_tank_volume_supplied > 0)
            * (
                scenario.hot_water_scenario.demand_temperature
                - hot_water_tank_temperature
            )
        )

        # Compute the power consumed by the thermal desalination plant.
        hot_water_power_consumed: pd.DataFrame = pd.DataFrame(
            auxiliary_heater_power_consumption
            + 0.001 * (hot_water_pvt_pump_times > 0) * minigrid.water_pump.consumption
        )

        # Determine the fraction of the output which was met renewably.
        renewable_hot_water_fraction: pd.DataFrame = (
            hot_water_tank_temperature
            - scenario.hot_water_scenario.cold_water_supply_temperature
        ) / (
            scenario.hot_water_scenario.demand_temperature
            - scenario.hot_water_scenario.cold_water_supply_temperature
        )

        hot_water_power_consumed = hot_water_power_consumed.reset_index(drop=True)
        hot_water_pvt_collector_output_temperature = (
            hot_water_pvt_collector_output_temperature.reset_index(drop=True)
        )
        hot_water_pvt_electric_power_per_unit = (
            hot_water_pvt_electric_power_per_unit.reset_index(drop=True)
        )
        hot_water_tank_temperature = hot_water_tank_temperature.reset_index(drop=True)
        hot_water_tank_volume_supplied = hot_water_tank_volume_supplied.reset_index(
            drop=True
        )
        renewable_hot_water_fraction = renewable_hot_water_fraction.reset_index(
            drop=True
        )

    else:
        auxiliary_heater = None
        hot_water_power_consumed = pd.DataFrame([0] * (end_hour - start_hour))
        hot_water_pvt_collector_output_temperature = None
        hot_water_pvt_electric_power_per_unit = pd.DataFrame(
            [0] * (end_hour - start_hour)
        )
        hot_water_tank_temperature = None
        hot_water_tank_volume_supplied = None
        renewable_hot_water_fraction = None

    return (
        auxiliary_heater,
        hot_water_power_consumed,
        hot_water_pvt_collector_output_temperature,
        hot_water_pvt_electric_power_per_unit,
        hot_water_tank_temperature,
        hot_water_tank_volume_supplied,
        renewable_hot_water_fraction,
    )


def _clean_water_tank_iteration_step(
    backup_desalinator_water_supplied: Dict[int, float],
    clean_water_power_consumed_mapping: Dict[int, float],
    clean_water_demand_met_by_excess_energy: Dict[int, float],
    clean_water_supplied_by_excess_energy: Dict[int, float],
    conventional_clean_water_source_profiles: Dict[WaterSource, pd.DataFrame],
    conventional_water_supplied: Dict[int, float],
    energy_per_desalinated_litre: float,
    excess_energy: float,
    excess_energy_used_desalinating: Dict[int, float],
    hourly_clean_water_tank_storage: pd.DataFrame,
    initial_clean_water_tank_storage: float,
    maximum_battery_storage: float,
    maximum_clean_water_tank_storage: float,
    maximum_water_throughput: float,
    minigrid: Minigrid,
    minimum_clean_water_tank_storage: float,
    new_hourly_battery_storage: float,
    scenario: Scenario,
    storage_water_supplied: Dict[int, float],
    tank_storage_profile: pd.DataFrame,
    *,
    time_index: int,
) -> float:
    """
    Caries out an iteration calculation for the clean-water tanks.

    Inputs:
        - backup_desalinator_water_supplied:
            The water supplied by the backup (electric) desalination.
        - clean_water_power_consumed_mapping:
            The power consumed in providing clean water.
        - clean_water_demand_met_by_excess_energy:
            The clean-water demand that was met through excess energy from the renewable
            system.
        - clean_water_supplied_by_excess_energy:
            The clean water that was supplied by the excess energy from the renewable
            system.
        - conventioanl_clean_water_source_profiles:
            A mapping between :class:`WaterSource` instances, corresponding to
            conventional sources of drinking water within the system, and their
            associated maximum output throughout the duration of the simulation.
        - conventional_water_supplied:
            A mapping between time index and the amount of clean water supplied through
            conventional sources available to the system.
        - energy_per_desalinated_litre:
            The electrical energy required to desalinate a single litre.
        - excess_energy:
            The excess electrical energy from the renewable system.
        - excess_energy_used_desalinating:
            The amount of excess electrical energy that was used desalinating.
        - hourly_clean_water_tank_storage:
            A mapping between time index and the amount of clean water stored in the
            system.
        - initial_clean_water_tank_storage:
            The initial level of the clean water tanks.
        - maximum_battery_storage:
            The maximum amount of energy that can be stored in the batteries.
        - maximum_clean_water_tank_storage:
            The maximum storage of the clean-water tanks.
        - maximum_water_throughput:
            The maximum amount of water that can be desalinated electrically.
        - minigrid:
            The :class:`Minigrid` being used for the run.
        - minimum_clean_water_tank_storage:
            The minimum amount of water that must be held in the clean-water tanks.
        - new_hourly_battery_storage:
            The level of electricity stored in the batteries at the time step being
            considered.
        - scenario:
            The :class:`Scenario` for the run being carried out.
        - storage_water_supplied:
            The amount of clean water, in litres, that was supplied by the clean-water
            storage tanks.
        - time_index:
            The current index being considered.

    Outputs:
        - excess_energy:
            The excess electrical energy, generated by the renewables, after what can be
            used for desalination has been used for electrical desalination.

    """

    if scenario.desalination_scenario is not None:
        tank_water_flow = tank_storage_profile.iloc[time_index, 0]

        # Compute the new tank level based on the previous level and the flow.
        if time_index == 0:
            current_net_water_flow = initial_clean_water_tank_storage + tank_water_flow
        else:
            current_net_water_flow = (
                hourly_clean_water_tank_storage[time_index - 1]
                * (1.0 - minigrid.clean_water_tank.leakage)
                + tank_water_flow
            )

        # Use the excess energy to desalinate if there is space.
        if (
            excess_energy > 0
            and scenario.desalination_scenario is not None
            and scenario.desalination_scenario.clean_water_scenario.mode
            == CleanWaterMode.BACKUP
        ):
            # Compute the maximum amount of water that can be desalinated.
            maximum_desalinated_water = min(
                excess_energy / energy_per_desalinated_litre,
                maximum_water_throughput,
            )

            # Add this to the tank and fulfil the demand if relevant.
            current_hourly_clean_water_tank_storage = (
                current_net_water_flow + maximum_desalinated_water
            )

            # Compute the amount of water that was actually desalinated.
            desalinated_water = min(
                maximum_desalinated_water,
                maximum_clean_water_tank_storage - current_net_water_flow,
            )

            # Compute the remaining excess energy and the energy used in
            # desalination.
            energy_consumed = energy_per_desalinated_litre * desalinated_water
            new_hourly_battery_storage -= energy_consumed

            # Ensure that the excess energy is normalised correctly.
            excess_energy = max(
                new_hourly_battery_storage - maximum_battery_storage, 0.0
            )

            # Store this as water and electricity supplied using excess power.
            excess_energy_used_desalinating[time_index] = energy_consumed
            clean_water_demand_met_by_excess_energy[time_index] = max(
                0, -current_net_water_flow
            )
            clean_water_supplied_by_excess_energy[time_index] = desalinated_water
        else:
            excess_energy_used_desalinating[time_index] = 0
            clean_water_demand_met_by_excess_energy[time_index] = 0
            clean_water_supplied_by_excess_energy[time_index] = 0
            current_hourly_clean_water_tank_storage = current_net_water_flow

        # If there is still unmet water demand, then carry out desalination and
        # pumping to fulfil the demand.
        current_unmet_water_demand: float = -current_hourly_clean_water_tank_storage
        if (
            current_unmet_water_demand > 0
            and scenario.desalination_scenario is not None
            and scenario.desalination_scenario.clean_water_scenario.mode
            == CleanWaterMode.PRIORITISE
        ):
            # Compute the electricity consumed meeting this demand.
            energy_consumed = energy_per_desalinated_litre * current_unmet_water_demand

            # Withdraw this energy from the batteries.
            new_hourly_battery_storage -= (
                1.0 / minigrid.battery.conversion_out
            ) * energy_consumed

            # Ensure that the excess energy is normalised correctly.
            excess_energy = max(
                new_hourly_battery_storage - maximum_battery_storage, 0.0
            )

            # Store this as water and electricity supplied by backup.
            clean_water_power_consumed_mapping[time_index] += energy_consumed
            backup_desalinator_water_supplied[time_index] = current_unmet_water_demand
        else:
            clean_water_power_consumed_mapping[time_index] = 0
            backup_desalinator_water_supplied[time_index] = 0

        # Any remaining unmet water demand should be met using conventional clean-water
        # sources if available.
        if current_unmet_water_demand > 0:
            # Compute the clean water supplied using convnetional sources.
            conventional_clean_water_available = float(
                sum(
                    entry.iloc[time_index]
                    for entry in conventional_clean_water_source_profiles.values()
                )
            )
            conventional_clean_water_supplied = min(
                conventional_clean_water_available, current_unmet_water_demand
            )
            current_unmet_water_demand -= conventional_clean_water_supplied

            # Store this as water supplied through conventional means.
            conventional_water_supplied[time_index] = conventional_clean_water_supplied
        else:
            conventional_water_supplied[time_index] = 0

        current_hourly_clean_water_tank_storage = min(
            current_hourly_clean_water_tank_storage,
            maximum_clean_water_tank_storage,
        )
        current_hourly_clean_water_tank_storage = max(
            current_hourly_clean_water_tank_storage,
            minimum_clean_water_tank_storage,
        )

        hourly_clean_water_tank_storage[
            time_index
        ] = current_hourly_clean_water_tank_storage

        if time_index == 0:
            storage_water_supplied[time_index] = 0.0 - tank_water_flow
        else:
            storage_water_supplied[time_index] = max(
                hourly_clean_water_tank_storage[time_index - 1]
                * (1.0 - minigrid.clean_water_tank.leakage)
                - hourly_clean_water_tank_storage[time_index],
                0.0,
            )

    return excess_energy


def _get_electric_battery_storage_profile(
    *,
    grid_profile: pd.DataFrame,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: Minigrid,
    processed_total_electric_load: pd.DataFrame,
    renewables_power_produced: Dict[SolarPanelType, pd.DataFrame],
    scenario: Scenario,
    clean_water_pvt_size: int = 0,
    end_hour: int = 4,
    hot_water_pvt_size: int = 0,
    pv_size: float = 10,
    start_hour: int = 0,
) -> Tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    Dict[SolarPanelType, pd.DataFrame],
    pd.DataFrame,
]:
    """
    Gets the storage profile (energy in/out the battery) and other system energies.

    Inputs:
        - grid_profile:
            The relevant grid profile, based on the scenario, for the simulation.
        - kerosene_usage:
            The kerosene usage.
        - logger:
            The logger to use for the run.
        - minigrid:
            The energy system being modelled.
        - processed_total_electric_load:
            The total electric load for the system.
        - renewables_power_produced:
            The total electric power produced, per renewable type, as a mapping between
            :class:`SolarPanelType` and :class:`pandas.DataFrame` instances, with units
            of technology size.
        - scenario:
            The scenatio being considered.
        - clean_water_pvt_size:
            Amount of PV-T in units of PV-T associated with the clean-water system.
        - end_year:
            End year of this simulation period.
        - hot_water_pvt_size:
            Amount of PV-T in units of PV-T associated with the hot-water system.
        - pv_size:
            Amount of PV in units of PV.
        - start_year:
            Start year of this simulation period.

    Outputs:
        - battery_storage_profile:
            Amount of energy (kWh) into (+ve) and out of (-ve) the battery.
        - grid_energy:
            Amount of energy (kWh) supplied by the grid.
        - kerosene_usage:
            Number of kerosene lamps in use (if no power available).
        - load_energy:
            Amount of energy (kWh) required to satisfy the loads.
        - pvt_energy:
            Amount of energy (kWh) provided by PV to the system.
        - pvt_energy:
            Amount of electric energy (kWh) provided by PV-T to the system.
        - renewables_energy:
            Amount of energy (kWh) provided by renewables to the system.
        - renewables_energy_map:
            A mapping between :class:`RenewableEnergySource` and the associated
            electrical energy produced.
        - renewables_energy_used_directly:
            Amount of energy (kWh) from renewables used directly to satisfy load (kWh).

    """

    # Initialise power generation, including degradation of PV
    try:
        pv_power_produced = renewables_power_produced[RenewableEnergySource.PV]
    except KeyError:
        logger.critical(
            "%sCould not determine PV power produced from renewables production.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InternalError(
            "No PV power in renewables_power_produced mapping, fatal."
        ) from None
    pv_generation_array = pv_power_produced * pv_size
    solar_degradation_array = solar_degradation(
        minigrid.pv_panel.lifetime, location.max_years
    ).iloc[start_hour:end_hour, 0]
    pv_generation = pd.DataFrame(
        np.asarray(pv_generation_array.iloc[start_hour:end_hour])
        * np.asarray(solar_degradation_array)
    )

    # Initialise PV-T power generation, including degradation of PV
    if minigrid.pvt_panel is not None:
        # Determine the PV-T degredation.
        pvt_degradation_array = solar_degradation(
            minigrid.pvt_panel.lifetime, location.max_years
        )[0 : (end_hour - start_hour)]

        if (
            RenewableEnergySource.CLEAN_WATER_PV_T not in renewables_power_produced
            and RenewableEnergySource.HOT_WATER_PV_T not in renewables_power_produced
        ):
            logger.error(
                "%sA PV-T panel was defined on the system but no clean-water PV-T or "
                "hot-water PV-T electricity was generated.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "No PV-T electric power produced despite a PV-T panel being defined for the system.."
            )

        # Compute the clean-water PV-T electricity generated.
        if RenewableEnergySource.CLEAN_WATER_PV_T in renewables_power_produced:
            try:
                clean_water_pvt_electric_power_produced = renewables_power_produced[
                    RenewableEnergySource.CLEAN_WATER_PV_T
                ]
            except KeyError:
                logger.error(
                    "%sCould not determine clean-water PV-T power produced from "
                    "renewables production despite a PV-T panel being defined on the "
                    "system.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise InternalError(
                    "No PV-T power in renewables_power_produced mapping despite a PV-T "
                    "panel being specified."
                ) from None
            clean_water_pvt_electric_generation_array = (
                clean_water_pvt_electric_power_produced * clean_water_pvt_size
            )
            clean_water_pvt_electric_generation: pd.DataFrame = pd.DataFrame(
                np.asarray(clean_water_pvt_electric_generation_array)
                * np.asarray(pvt_degradation_array)
            )
        else:
            clean_water_pvt_electric_generation = pd.DataFrame(
                [0] * (end_hour - start_hour)
            )

        # Compute the clean-water source.
        if RenewableEnergySource.HOT_WATER_PV_T in renewables_power_produced:
            try:
                hot_water_pvt_electric_power_produced = renewables_power_produced[
                    RenewableEnergySource.HOT_WATER_PV_T
                ]
            except KeyError:
                logger.error(
                    "%sCould not determine PV-T power produced from renewables "
                    "production despite a PV-T panel being defined on the system.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise InternalError(
                    "No PV-T power in renewables_power_produced mapping despite a PV-T "
                    "panel being specified."
                ) from None
            hot_water_pvt_electric_generation_array = (
                hot_water_pvt_electric_power_produced * hot_water_pvt_size
            )
            hot_water_pvt_electric_generation: Optional[pd.DataFrame] = pd.DataFrame(
                np.asarray(hot_water_pvt_electric_generation_array)
                * np.asarray(pvt_degradation_array)
            )
        else:
            hot_water_pvt_electric_generation = pd.DataFrame(
                [0] * (end_hour - start_hour)
            )

        pvt_electric_generation: Optional[pd.DataFrame] = pd.DataFrame(
            clean_water_pvt_electric_generation.values
            + hot_water_pvt_electric_generation.values
        )

    else:
        pvt_electric_generation = None

    # Consider power distribution network
    if scenario.distribution_network == DistributionNetwork.DC:
        pv_generation = pv_generation.mul(minigrid.dc_to_dc_conversion_efficiency)
        transmission_efficiency = minigrid.dc_transmission_efficiency
        # grid_conversion_eff = minigrid.ac_to_dc_conversion

    else:
        pv_generation = pv_generation.mul(minigrid.dc_to_ac_conversion_efficiency)
        transmission_efficiency = minigrid.ac_transmission_efficiency
        # grid_conversion_efficiency = minigrid.ac_to_ac_conversion

    if transmission_efficiency is None:
        logger.error(
            "%sNo valid transmission efficiency was determined based on the energy "
            "system inputs. Check this before continuing.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "energy system inputs",
            "No valid transmission efficiency was determined based on the energy "
            "system inputs. Check this before continuing.",
        )

    # Consider transmission efficiency
    load_energy: pd.DataFrame = processed_total_electric_load / transmission_efficiency
    pv_energy = pv_generation * transmission_efficiency

    if clean_water_pvt_electric_generation is not None:
        pvt_cw_electric_energy: pd.DataFrame = (
            clean_water_pvt_electric_generation * transmission_efficiency
        )
    else:
        pvt_cw_electric_energy = pd.DataFrame([0] * pv_energy.size)

    if hot_water_pvt_electric_generation is not None:
        pvt_hw_electric_energy: pd.DataFrame = (
            hot_water_pvt_electric_generation * transmission_efficiency
        )
    else:
        pvt_hw_electric_energy = pd.DataFrame([0] * pv_energy.size)

    # Combine energy from all renewables sources
    renewables_energy_map: Dict[SolarPanelType, pd.DataFrame] = {
        RenewableEnergySource.PV: pv_energy,
        RenewableEnergySource.CLEAN_WATER_PV_T: pvt_cw_electric_energy,
        RenewableEnergySource.HOT_WATER_PV_T: pvt_hw_electric_energy,
        # RenewableGenerationSource.WIND: wind_energy, etc.
    }

    # Add more renewable sources here as required
    renewables_energy: pd.DataFrame = pd.DataFrame(sum(renewables_energy_map.values()))

    # Check for self-generation prioritisation
    if scenario.prioritise_self_generation:
        # Take energy from PV first
        remaining_profile = pd.DataFrame(renewables_energy.values - load_energy.values)
        renewables_energy_used_directly: pd.DataFrame = pd.DataFrame(
            (remaining_profile > 0) * load_energy.values
            + (remaining_profile < 0) * renewables_energy.values
        )

        # Then take energy from grid
        grid_energy = pd.DataFrame(
            ((remaining_profile < 0) * remaining_profile).iloc[:, 0]
            * -1.0
            * grid_profile.values
        )
        battery_storage_profile: pd.DataFrame = pd.DataFrame(
            remaining_profile.values + grid_energy.values
        )

    else:
        # Take energy from grid first
        grid_energy = grid_profile.mul(load_energy)
        # as needed for load
        remaining_profile = (grid_energy <= 0).mul(load_energy)
        # Then take energy from PV
        battery_storage_profile = pd.DataFrame(
            renewables_energy.values.subtrace(remaining_profile.values)
        )
        renewables_energy_used_directly = pd.DataFrame(
            (battery_storage_profile > 0)
            .mul(remaining_profile)
            .add((battery_storage_profile < 0).mul(renewables_energy))
        )

    battery_storage_profile.columns = pd.Index(["Storage profile (kWh)"])
    grid_energy.columns = pd.Index(["Grid energy (kWh)"])
    kerosene_usage.columns = pd.Index(["Kerosene lamps"])
    load_energy.columns = pd.Index(["Load energy (kWh)"])
    renewables_energy.columns = pd.Index(["Renewables energy supplied (kWh)"])
    renewables_energy_map[RenewableEnergySource.PV].columns = pd.Index(
        ["PV energy supplied (kWh)"]
    )
    renewables_energy_map[RenewableEnergySource.CLEAN_WATER_PV_T].columns = pd.Index(
        ["Clean-water PV-T electric energy supplied (kWh)"]
    )
    renewables_energy_map[RenewableEnergySource.HOT_WATER_PV_T].columns = pd.Index(
        ["Hot-water PV-T electric energy supplied (kWh)"]
    )
    renewables_energy_used_directly.columns = pd.Index(["Renewables energy used (kWh)"])

    return (
        battery_storage_profile,
        grid_energy,
        kerosene_usage,
        load_energy,
        renewables_energy,
        renewables_energy_map,
        renewables_energy_used_directly,
    )


def _get_processed_load_profile(scenario: Scenario, total_load: pd.DataFrame):
    """
    Gets the total community load over 20 years in kW

    Inputs:
        - scenario:
            Information about the scenario currently being run.
        - total_load:
            The total load as a :class:`pandas.DataFrame`.

    Outputs:
        - A :class:`pandas.DataFrame` with columns for the load of domestic,
            commercial and public devices.

    """

    processed_total_load: Optional[pd.DataFrame] = None

    if scenario.demands.domestic:
        processed_total_load = pd.DataFrame(
            total_load[DemandType.DOMESTIC.value].values
        )

    if scenario.demands.commercial:
        if processed_total_load is not None:
            processed_total_load += pd.DataFrame(
                total_load[DemandType.COMMERCIAL.value].values
            )
        else:
            processed_total_load = total_load[DemandType.COMMERCIAL.value]

    if scenario.demands.public:
        if processed_total_load is not None:
            processed_total_load += pd.DataFrame(
                total_load[DemandType.PUBLIC.value].values
            )
        else:
            processed_total_load = total_load[DemandType.PUBLIC.value]

    if processed_total_load is None:
        raise Exception("At least one load type must be specified.")

    return processed_total_load


def _get_water_storage_profile(
    processed_total_clean_water_load: pd.DataFrame,
    renewable_clean_water_produced: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Gets the storage profile for the clean-water system.

    Inputs:
        - minigrid:
            The minigrid being modelled.
        - processed_total_clean_water_load:
            The total clean-water load placed on the system.
        - renewable_clean_water_produced:
            The total clean water produced directly from renewables, i.e., solar-based
            or solar-thermal-based desalination technologies.
        - scenario:
            The scenario being considered.

    Outputs:
        - power_consumed:
            The electric power consumed in providing the water demand.
        - renewable_clean_water_used_directly:
            The renewable clean water which was directly consumed.
        - tank_storage_profile:
            The amount of water (litres) into (+ve) and out of (-ve) the clean-water
            tanks.

    """

    # Clean water is either produced directly or drawn from the storage tanks.
    remaining_profile = pd.DataFrame(
        renewable_clean_water_produced.values - processed_total_clean_water_load.values
    )
    renewable_clean_water_used_directly: pd.DataFrame = pd.DataFrame(
        (remaining_profile > 0) * processed_total_clean_water_load.values
        + (remaining_profile < 0) * renewable_clean_water_produced.values
    )

    tank_storage_profile: pd.DataFrame = pd.DataFrame(remaining_profile.values)

    return (
        0.001 * pd.DataFrame([0] * processed_total_clean_water_load.size),
        renewable_clean_water_used_directly,
        tank_storage_profile,
    )


def _setup_tank_storage_profiles(
    logger: Logger,
    number_of_tanks: int,
    power_consumed: pd.DataFrame,
    resource_type: ResourceType,
    scenario: Scenario,
    tank: Optional[CleanWaterTank],
) -> Tuple[Optional[Dict[int, float]], float, float, float, Dict[int, float]]:
    """
    Sets up tank storage parameters.

    Inputs:
        - logger:
            The :class:`logging.Logger` to use for the run.
        - number_of_tanks:
            The number of tanks of this type to use for the run.
        - power_consumed:
            The electric power consumed associated with the storage of these
            :class:`ResourceType` tanks.
        - resource_type:
            The :class:`ResourceType` held within the :class:`CleanWaterTank`.
        - scenario:
            The :class:`Scneario` for the run.
        - tank:
            The :class:`CleanWaterTank`, representing either a clean- or hot-water tank,
            to use for the run.

    Outputs:
        - hourly_tank_storage:
            The hourly tank storage.
        - initial_tank_storage:
            The amount of water initially in the tank.
        - minimum_tank_storage:
            The minimum level of the tank permitted.
        - power_consumed_mapping:
            A mapping between time as `int` and the electric power consumed.

    """

    power_consumed_mapping: Dict[int, float] = power_consumed[0].to_dict()

    if (
        resource_type in scenario.resource_types
        and scenario.desalination_scenario is not None
    ):
        if tank is None:
            logger.error(
                "%sNo tank specifeid when attempting to compute %s loads.%s",
                BColours.fail,
                resource_type.value,
                BColours.endc,
            )
            raise InternalError(
                f"No {resource_type.value} tank specified on the energy system despite "
                + f"{resource_type.value} loads being requested.",
            )
        hourly_tank_storage: Optional[Dict[int, float]] = {}
        initial_tank_storage: float = 0.0

        # Determine the maximum tank storage.
        try:
            maximum_tank_storage: float = (
                number_of_tanks * tank.mass * tank.maximum_charge
            )
        except AttributeError:
            logger.error(
                "%sNo %s water tank provided on the energy system despite associated demands expected.%s",
                BColours.fail,
                resource_type.value,
                BColours.endc,
            )
            raise InputFileError(
                "energy system OR tank",
                f"No {resource_type.value} water tank was provided on the energy system despite "
                + f"{resource_type.value}-water demands being expected.",
            ) from None

        try:
            minimum_tank_storage: float = (
                number_of_tanks * tank.mass * tank.minimum_charge
            )
        except AttributeError:
            logger.error(
                "%sNo %s water tank provided on the energy system despite associated demands expected.%s",
                BColours.fail,
                resource_type.value,
                BColours.endc,
            )
            raise InputFileError(
                "energy system OR tank",
                f"No {resource_type.value} water tank was provided on the energy system despite "
                + f"{resource_type.value}-water demands being expected.",
            ) from None

    else:
        hourly_tank_storage = None
        initial_tank_storage = 0
        maximum_tank_storage = 0
        minimum_tank_storage = 0

    return (
        hourly_tank_storage,
        initial_tank_storage,
        maximum_tank_storage,
        minimum_tank_storage,
        power_consumed_mapping,
    )


def _update_battery_health(
    battery_energy_flow: float,
    battery_health: Dict[int, float],
    cumulative_battery_storage_power: float,
    electric_storage_size: float,
    hourly_battery_storage: Dict[int, float],
    maximum_battery_energy_throughput: float,
    minigrid: Minigrid,
    storage_power_supplied: Dict[int, float],
    *,
    time_index: int,
) -> Tuple[float, float, float]:
    """
    Updates the health of the batteries.

    Inputs:
        - battery_energy_flow:
            The net energy flow, into, or out of, the battery.
        - battery_health:
            The battery health at each time step.
        - cumulative_battery_storage_power: float:
            The cumulative amount of power that has been stored in the batteries,
            measured in kWh.
        - electric_storage_size:
            The size of the electric storage system.
        - hourly_battery_storage:
            The battery storage at each time step.
        - maximum_battery_energy_throughput:
            The maximum energy throughput through the batteries.
        - minigrid:
            The :class:`Minigrid` being modelled.
        - storage_power_supplied:
            The amount of power supplied by the storage system.
        - time_index:
            The current time (hour) being considered.

    Outputs:
        - cumulative_battery_storage_power:
            The cumulative amount of electricity that has been stored in the batteries.
        - maximum_battery_storage:
            The newly calculated maximum amount of energy that can be stored in the
            batteries having acounted for battery degredation.
        - minimum_battery_storage:
            The newly calculated minimum amount of energy that can be stored in the
            batteries having acounted for battery degredation.

    """

    if time_index == 0:
        storage_power_supplied[time_index] = 0.0 - battery_energy_flow
    else:
        storage_power_supplied[time_index] = max(
            hourly_battery_storage[time_index - 1] * (1.0 - minigrid.battery.leakage)
            - hourly_battery_storage[time_index],
            0.0,
        )
    cumulative_battery_storage_power += storage_power_supplied[time_index]

    battery_storage_degradation = 1.0 - minigrid.battery.lifetime_loss * (
        cumulative_battery_storage_power / maximum_battery_energy_throughput
    )
    maximum_battery_storage = (
        battery_storage_degradation
        * electric_storage_size
        * minigrid.battery.maximum_charge
        * minigrid.battery.storage_unit
    )
    minimum_battery_storage = (
        battery_storage_degradation
        * electric_storage_size
        * minigrid.battery.minimum_charge
        * minigrid.battery.storage_unit
    )
    battery_health[time_index] = battery_storage_degradation

    return (
        cumulative_battery_storage_power,
        maximum_battery_storage,
        minimum_battery_storage,
    )


def run_simulation(
    clean_water_pvt_size: int,
    conventional_clean_water_source_profiles: Dict[WaterSource, pd.DataFrame],
    convertors: List[Convertor],
    electric_storage_size: float,
    grid_profile: pd.DataFrame,
    hot_water_pvt_size: int,
    irradiance_data: pd.Series,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: Minigrid,
    number_of_clean_water_tanks: int,
    pv_power_produced: pd.Series,
    pv_size: float,
    scenario: Scenario,
    simulation: Simulation,
    temperature_data: pd.Series,
    total_loads: Dict[ResourceType, Optional[pd.DataFrame]],
    wind_speed_data: Optional[pd.Series],
) -> Tuple[datetime.timedelta, pd.DataFrame, SystemDetails]:
    """
    Simulates a minigrid system

    This function simulates the energy system of a given capacity and to the parameters
    stated in the input files.

    Inputs:
        - clean_water_pvt_size:
            Amount of PV-T in PV-T units associated with the clean-water system.
        - conventional_clean_water_source_profiles:
            A mapping between :class:`WaterSource` instances and the associated water
            that can be drawn from the source throughout the duration of the simulation.
        - convertors:
            The `list` of :class:`Convertor` instances available to be used.
        - diesel_generator:
            The backup diesel generator for the system being modelled.
        - electric_storage_size:
            Amount of storage in terms of the number of batteries included.
        - grid_profile:
            The grid-availability profile.
        - hot_water_pvt_size:
            Amount of PV-T in PV-T units associated with the hot-water system.
        - irradiance_data:
            The total solar irradiance data.
        - kerosene_usage:
            The kerosene-usage profile.
        - location:
            The location being considered.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - minigrid:
            The energy system being considered.
        - number_of_clean_water_tanks:
            The number of clean-water tanks installed in the system.
        - pv_size:
            Amount of PV in PV units.
        - pv_power_produced:
            The total energy outputted by the solar system per PV unit.
        - renewable_clean_water_produced:
            The amount of clean-water produced renewably, mesaured in litres.
        - scenario:
            The scenario being considered.
        - simulation:
            The simulation to run.
        - temperature_data:
            The temperature data series.
        - total_loads:
            A mapping between :class:`ResourceType`s and their associated total loads
            placed on the system.
        - wind_speed_data:
            The wind-speed data series.

    Outputs:
        - The time taken for the simulation.
        - System performance outputs:
            - system_performance_outputs:
                Hourly performance of the simulated system
            - load_energy:
                Amount of energy (kWh) required to satisfy the loads
            - total_energy_used:
                Amount of energy (kWh) used by the system
            - unmet_energy:
                Amount of energy (kWh) unmet by the system
            - blackout_times:
                Times with power is available (0) or unavailable (1)
            - renewables_energy_used_directly:
                Amount of energy (kWh) from renewables used directly to satisfy load (kWh)
            - storage_power_supplied:
                Amount of energy (kWh) supplied by battery storage
            - grid_energy:
                Amount of energy (kWh) supplied by the grid
            - diesel_energy:
                Amount of energy (kWh) supplied from diesel generator
            - diesel_times:
                Times when diesel generator is on (1) or off (0)
            - diesel_fuel_usage:
                Amount of diesel (l) used by the generator
            - battery_storage_profile:
                Amount of energy (kWh) into (+ve) and out of (-ve) the battery
            - renewables_energy:
                Amount of energy (kWh) provided by renewables to the system
            - hourly_battery_storage:
                Amount of energy (kWh) in the battery
            - energy_surplus:
                Amount of energy (kWh) dumped owing to overgeneration
            - battery_health:
                Relative capactiy of the battery compared to new (0.0-1.0)
            - households:
                Number of households in the community
            - kerosene_usage:
                Number of kerosene lamps in use (if no power available)
            - kerosene_mitigation:
                Number of kerosene lamps not used (when power is available)
        - System details about the run.

    """

    # Currently, only systems including batteries are supported.
    if minigrid.battery is None:
        logger.error(
            "%sNo battery information available when calling the energy system.%s",
            BColours.fail,
            BColours.endc,
        )
        raise Exception(
            "No battery information available when calling the energy system."
        )

    # Start timer to see how long simulation will take
    timer_start = datetime.datetime.now()

    # Initialise simulation parameters
    start_hour = simulation.start_year * 8760
    end_hour = simulation.end_year * 8760
    simulation_hours = end_hour - start_hour
    total_clean_water_load: Optional[pd.DataFrame] = total_loads[
        ResourceType.CLEAN_WATER
    ]
    total_electric_load: Optional[pd.DataFrame] = total_loads[ResourceType.ELECTRIC]
    total_hot_water_load: Optional[pd.DataFrame] = total_loads[
        ResourceType.HOT_CLEAN_WATER
    ]

    # Calculate PV-T related performance profiles.
    buffer_tank_temperature: Optional[pd.DataFrame]
    feedwater_sources: List[Convertor]
    clean_water_pvt_collector_output_temperature: Optional[pd.DataFrame]
    clean_water_pvt_electric_power_per_unit: pd.DataFrame
    renewable_clean_water_produced: pd.DataFrame
    buffer_tank_volume_supplied: pd.DataFrame
    thermal_desalination_electric_power_consumed: pd.DataFrame

    logger.info("Calculating clean-water PV-T performance profiles.")
    (
        buffer_tank_temperature,
        buffer_tank_volume_supplied,
        feedwater_sources,
        clean_water_pvt_collector_output_temperature,
        clean_water_pvt_electric_power_per_unit,
        renewable_clean_water_produced,
        required_clean_water_feedwater_sources,
        thermal_desalination_electric_power_consumed,
    ) = _calculate_renewable_clean_water_profiles(
        convertors,
        end_hour,
        irradiance_data,
        logger,
        minigrid,
        clean_water_pvt_size,
        scenario,
        start_hour,
        temperature_data,
        wind_speed_data,
    )
    logger.info("Clean-water PV-T performance profiles determined.")
    logger.debug(
        "Mean buffer tank temperature: %s",
        np.mean(buffer_tank_temperature.values)
        if buffer_tank_temperature is not None
        else "N/A",
    )
    logger.debug(
        "Soruces of feedwater: %s",
        ", ".join([str(source) for source in feedwater_sources]),
    )
    logger.debug(
        "Mean clean-water PV-T electric power per unit: %s",
        np.mean(clean_water_pvt_electric_power_per_unit.values),
    )
    logger.debug(
        "Maximum thermal desalination plant power consumption: %s",
        np.max(thermal_desalination_electric_power_consumed.values),
    )
    logger.debug(
        "Mean thermal desalination plant power consumption: %s",
        np.mean(thermal_desalination_electric_power_consumed.values),
    )

    # Calculate clean-water-related performance profiles.
    clean_water_power_consumed: pd.DataFrame
    renewable_clean_water_used_directly: pd.DataFrame
    tank_storage_profile: Optional[pd.DataFrame] = None
    total_clean_water_supplied: Optional[pd.DataFrame] = None

    if scenario.desalination_scenario is not None:
        if total_clean_water_load is None:
            raise Exception(
                f"{BColours.fail}A simulation was run that specified a clean-water "
                + f"load but no clean-water load was passed in.{BColours.endc}"
            )
        # Process the load profile based on the relevant scenario.
        processed_total_clean_water_load = pd.DataFrame(
            _get_processed_load_profile(scenario, total_clean_water_load)[
                start_hour:end_hour
            ].values
        )

        # Determine the water-tank storage profile.
        (
            clean_water_power_consumed,
            renewable_clean_water_used_directly,
            tank_storage_profile,
        ) = _get_water_storage_profile(
            processed_total_clean_water_load,
            renewable_clean_water_produced,
        )
        number_of_buffer_tanks: int = 1
    else:
        clean_water_power_consumed = pd.DataFrame([0] * simulation_hours)
        number_of_buffer_tanks = 0
        renewable_clean_water_used_directly = pd.DataFrame([0] * simulation_hours)

    # Calculate hot-water-related profiles.
    processed_total_hot_water_load: pd.DataFrame
    if scenario.hot_water_scenario is not None:
        if total_hot_water_load is None:
            raise Exception(
                f"{BColours.fail}A simulation was run that specified a hot-water load "
                + f"but no hot-water load was passed in.{BColours.endc}"
            )
        # Process the load profile based on the relevant scenario.
        number_of_hot_water_tanks: int = 0
        processed_total_hot_water_load = pd.DataFrame(
            _get_processed_load_profile(scenario, total_hot_water_load)[
                start_hour:end_hour
            ]
        )
    else:
        number_of_hot_water_tanks = 0
        processed_total_hot_water_load = pd.DataFrame([0] * (end_hour - start_hour))

    # Calculate hot-water PV-T related performance profiles.
    hot_water_pump_electric_power_consumed: pd.DataFrame
    hot_water_pvt_collector_output_temperature: Optional[pd.DataFrame]
    hot_water_pvt_electric_power_per_unit: pd.DataFrame
    hot_water_tank_temperature: Optional[pd.DataFrame]
    hot_water_tank_volume_supplied: pd.DataFrame
    renewable_hot_water_fraction: pd.DataFrame

    logger.info("Calculating hot-water PV-T performance profiles.")
    (
        auxiliary_heater,
        hot_water_power_consumed,
        hot_water_pvt_collector_output_temperature,
        hot_water_pvt_electric_power_per_unit,
        hot_water_tank_temperature,
        hot_water_tank_volume_supplied,
        renewable_hot_water_fraction,
    ) = _calculate_renewable_hot_water_profiles(
        convertors,
        end_hour,
        irradiance_data,
        logger,
        minigrid,
        processed_total_hot_water_load,
        hot_water_pvt_size,
        scenario,
        start_hour,
        temperature_data,
        wind_speed_data,
    )
    logger.info("Hot-water PV-T performance profiles determined.")
    logger.debug(
        "Mean hot-water tank temperature: %s",
        np.mean(hot_water_tank_temperature.values)
        if hot_water_tank_temperature is not None
        else "N/A",
    )
    logger.debug(
        "Mean hot-water PV-T electric power per unit: %s",
        np.mean(hot_water_pvt_electric_power_per_unit.values),
    )

    # Calculate electricity-related profiles.
    if total_electric_load is None:
        logger.error(
            "No electric load was supplied to the energy_system.run_simulation method "
            "despite this being necessary for the simulation of energy systems."
        )
        raise InternalError(
            "No electric load was supplied to the energy_system.run_simulation method "
            "despite this being necessary for the simulation of energy systems."
        )
    processed_total_electric_load = pd.DataFrame(
        _get_processed_load_profile(scenario, total_electric_load)[
            start_hour:end_hour
        ].values
        + clean_water_power_consumed.values
        + hot_water_power_consumed.values
        + thermal_desalination_electric_power_consumed.values
    )

    # Compute the electric input profiles.
    battery_storage_profile: pd.DataFrame
    grid_energy: pd.DataFrame
    kerosene_profile: pd.DataFrame
    load_energy: pd.DataFrame
    renewables_energy: pd.DataFrame
    renewables_energy_map: Dict[RenewableEnergySource, pd.DataFrame] = {
        RenewableEnergySource.PV: pv_power_produced,
        RenewableEnergySource.CLEAN_WATER_PV_T: (
            clean_water_pvt_electric_power_per_unit
        ),
        RenewableEnergySource.HOT_WATER_PV_T: hot_water_pvt_electric_power_per_unit,
    }
    renewables_energy_used_directly: pd.DataFrame
    (
        battery_storage_profile,
        grid_energy,
        kerosene_profile,
        load_energy,
        renewables_energy,
        renewables_energy_map,
        renewables_energy_used_directly,
    ) = _get_electric_battery_storage_profile(
        clean_water_pvt_size=clean_water_pvt_size,
        grid_profile=grid_profile.iloc[start_hour:end_hour, 0],
        hot_water_pvt_size=hot_water_pvt_size,
        kerosene_usage=kerosene_usage.iloc[start_hour:end_hour, 0],
        location=location,
        logger=logger,
        minigrid=minigrid,
        processed_total_electric_load=processed_total_electric_load,
        renewables_power_produced=renewables_energy_map,
        scenario=scenario,
        end_hour=end_hour,
        pv_size=pv_size,
        start_hour=start_hour,
    )

    if all(renewables_energy.values == 0):
        logger.warning(
            "%sNo renewable electricity was generated. Continuing with grid and diesel "
            "only.%s",
            BColours.warning,
            BColours.endc,
        )

    # Determine the number of households in the community.
    households = pd.DataFrame(
        population_hourly(location)[
            simulation.start_year * 8760 : simulation.end_year * 8760
        ].values
    )

    # Initialise battery storage parameters
    maximum_battery_energy_throughput: float = (
        electric_storage_size
        * minigrid.battery.cycle_lifetime
        * minigrid.battery.storage_unit
    )
    initial_battery_storage: float = (
        electric_storage_size
        * minigrid.battery.maximum_charge
        * minigrid.battery.storage_unit
    )
    maximum_battery_storage: float = (
        electric_storage_size
        * minigrid.battery.maximum_charge
        * minigrid.battery.storage_unit
    )
    minimum_battery_storage: float = (
        electric_storage_size
        * minigrid.battery.minimum_charge
        * minigrid.battery.storage_unit
    )
    cumulative_battery_storage_power: float = 0.0
    hourly_battery_storage: Dict[int, float] = {}
    new_hourly_battery_storage: float = 0.0
    battery_health: Dict[int, float] = {}

    # Initialise tank storage parameters
    (
        hourly_clean_water_tank_storage,
        initial_clean_water_tank_storage,
        maximum_clean_water_tank_storage,
        minimum_clean_water_tank_storage,
        clean_water_power_consumed_mapping,
    ) = _setup_tank_storage_profiles(
        logger,
        number_of_clean_water_tanks,
        clean_water_power_consumed,
        ResourceType.CLEAN_WATER,
        scenario,
        minigrid.clean_water_tank,
    )

    (
        hourly_hot_water_tank_storage,
        initial_hot_water_tank_storage,
        maximum_hot_water_tank_storage,
        minimum_hot_water_tank_storage,
        hot_water_power_consumed_mapping,
    ) = _setup_tank_storage_profiles(
        logger,
        number_of_hot_water_tanks,
        hot_water_power_consumed,
        ResourceType.HOT_CLEAN_WATER,
        scenario,
        minigrid.hot_water_tank,
    )

    # Initialise electric desalination paramteters.
    (
        electric_desalinators,
        energy_per_desalinated_litre,
        maximum_water_throughput,
    ) = _calculate_electric_desalination_parameters(
        convertors, feedwater_sources, logger, scenario
    )

    # Intialise tank accounting parameters
    backup_desalinator_water_supplied: Dict[int, float] = {}
    clean_water_demand_met_by_excess_energy: Dict[int, float] = {}
    clean_water_supplied_by_excess_energy: Dict[int, float] = {}
    conventional_water_supplied: Dict[int, float] = {}
    excess_energy_used_desalinating: Dict[int, float] = {}
    storage_water_supplied: Dict[int, float] = {}
    water_surplus: Dict[int, float] = {}
    # water_deficit: List[float] = []

    # Initialise energy accounting parameters
    energy_surplus: Dict[int, float] = {}
    energy_deficit: Dict[int, float] = {}
    storage_power_supplied: Dict[int, float] = {}

    # Do not do the itteration if no storage is being used
    if electric_storage_size == 0:
        energy_surplus = ((battery_storage_profile > 0) * battery_storage_profile).abs()
        energy_deficit = ((battery_storage_profile < 0) * battery_storage_profile).abs()
    # Carry out the itteration if there is some storage involved in the system.
    else:
        # Begin simulation, iterating over timesteps
        for t in tqdm(
            range(int(battery_storage_profile.size)),
            desc="hourly computation",
            leave=False,
            unit="hour",
        ):
            # Calculate the electric iteration.
            (
                battery_energy_flow,
                excess_energy,
                new_hourly_battery_storage,
            ) = _battery_iteration_step(
                battery_storage_profile,
                hourly_battery_storage,
                initial_battery_storage,
                logger,
                maximum_battery_storage,
                minigrid,
                minimum_battery_storage,
                time_index=t,
            )

            # Calculate the hot-water iteration.

            # Calculate the clean-water iteration.
            excess_energy = _clean_water_tank_iteration_step(
                backup_desalinator_water_supplied,
                clean_water_power_consumed_mapping,
                clean_water_demand_met_by_excess_energy,
                clean_water_supplied_by_excess_energy,
                conventional_clean_water_source_profiles,
                conventional_water_supplied,
                energy_per_desalinated_litre,
                excess_energy,
                excess_energy_used_desalinating,
                hourly_clean_water_tank_storage,
                initial_clean_water_tank_storage,
                maximum_battery_storage,
                maximum_clean_water_tank_storage,
                maximum_water_throughput,
                minigrid,
                minimum_clean_water_tank_storage,
                new_hourly_battery_storage,
                scenario,
                storage_water_supplied,
                tank_storage_profile,
                time_index=t,
            )

            # Dumped energy and unmet demand
            energy_surplus[t] = excess_energy  # Battery too full
            energy_deficit[t] = max(
                minimum_battery_storage - new_hourly_battery_storage, 0.0
            )  # Battery too empty

            # Battery capacities and blackouts (if battery is too full or empty)
            new_hourly_battery_storage = min(
                new_hourly_battery_storage, maximum_battery_storage
            )
            new_hourly_battery_storage = max(
                new_hourly_battery_storage, minimum_battery_storage
            )

            # Update hourly_battery_storage
            hourly_battery_storage[t] = new_hourly_battery_storage

            # Update battery health
            (
                cumulative_battery_storage_power,
                maximum_battery_storage,
                minimum_battery_storage,
            ) = _update_battery_health(
                battery_energy_flow,
                battery_health,
                cumulative_battery_storage_power,
                electric_storage_size,
                hourly_battery_storage,
                maximum_battery_energy_throughput,
                minigrid,
                storage_power_supplied,
                time_index=t,
            )

    # Process the various outputs into dataframes.
    battery_health_frame: pd.DataFrame = dict_to_dataframe(battery_health, logger)
    # energy_deficit_frame: pd.DataFrame = dict_to_dataframe(energy_deficit)
    energy_surplus_frane: pd.DataFrame = dict_to_dataframe(energy_surplus, logger)
    hourly_battery_storage_frame: pd.DataFrame = dict_to_dataframe(
        hourly_battery_storage, logger
    )
    storage_power_supplied_frame: pd.DataFrame = dict_to_dataframe(
        storage_power_supplied, logger
    )

    if scenario.desalination_scenario is not None:
        backup_desalinator_water_frame: pd.DataFrame = dict_to_dataframe(
            backup_desalinator_water_supplied, logger
        )
        clean_water_demand_met_by_excess_energy: pd.DataFrame = dict_to_dataframe(
            clean_water_demand_met_by_excess_energy, logger
        )
        clean_water_power_consumed: pd.DataFrame = dict_to_dataframe(
            clean_water_power_consumed_mapping, logger
        )
        clean_water_supplied_by_excess_energy_frame: pd.DataFrame = dict_to_dataframe(
            clean_water_supplied_by_excess_energy, logger
        )
        conventional_clean_water_supplied_frame: pd.DataFrame = dict_to_dataframe(
            conventional_water_supplied, logger
        )
        excess_energy_used_desalinating_frame: pd.DataFrame = dict_to_dataframe(
            excess_energy_used_desalinating, logger
        )
        hourly_clean_water_tank_storage_frame: pd.DataFrame = dict_to_dataframe(
            hourly_clean_water_tank_storage, logger
        )
        storage_water_supplied_frame: pd.DataFrame = dict_to_dataframe(
            storage_water_supplied, logger
        )
        water_surplus_frame: pd.DataFrame = dict_to_dataframe(water_surplus, logger)

    # Find unmet energy
    unmet_energy = pd.DataFrame(
        (
            load_energy.values
            + thermal_desalination_electric_power_consumed.values
            + clean_water_power_consumed.values
            - renewables_energy_used_directly.values
            - grid_energy.values
            - storage_power_supplied_frame.values
        )
    )
    if thermal_desalination_electric_power_consumed is not None:
        unmet_energy = pd.DataFrame(
            (unmet_energy.values + thermal_desalination_electric_power_consumed.values)
        )

    # Determine the times for which the system experienced a blackout.
    blackout_times = ((unmet_energy > 0) * 1).astype(float)

    # Use backup diesel generator
    diesel_energy: pd.DataFrame
    diesel_fuel_usage: pd.DataFrame
    diesel_times: pd.DataFrame
    if scenario.diesel_scenario.mode == DieselMode.BACKUP:
        diesel_fuel_usage: pd.DataFrame
        (
            diesel_capacity,
            diesel_energy,
            diesel_fuel_usage,
            diesel_times,
            unmet_energy,
        ) = _calculate_backup_diesel_generator_usage(
            blackout_times, minigrid, scenario, unmet_energy
        )
    elif scenario.diesel_scenario.mode == DieselMode.CYCLE_CHARGING:
        logger.error(
            "%sCycle charing is not currently supported.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "scenario inputs", "Cycle charing is not currently supported."
        )
    else:
        diesel_energy = pd.DataFrame([0.0] * int(battery_storage_profile.size))
        diesel_times = pd.DataFrame([0.0] * int(battery_storage_profile.size))
        diesel_fuel_usage = pd.DataFrame([0.0] * int(battery_storage_profile.size))
        diesel_capacity = 0.0

    # Find new blackout times, according to when there is unmet energy
    blackout_times = ((unmet_energy > 0) * 1).astype(float)
    # Ensure all unmet energy is calculated correctly, removing any negative values
    unmet_energy = ((unmet_energy > 0) * unmet_energy).abs()
    # Ensure all unmet clean-water energy is considered.
    clean_water_power_consumed = clean_water_power_consumed.mul(1 - blackout_times)
    thermal_desalination_electric_power_consumed = (
        thermal_desalination_electric_power_consumed.mul(1 - blackout_times)
    )

    # Find how many kerosene lamps are in use
    kerosene_usage = blackout_times.loc[:, 0].mul(kerosene_profile.values)
    kerosene_mitigation = (1 - blackout_times).loc[:, 0].mul(kerosene_profile.values)

    if scenario.desalination_scenario is not None:
        # Compute the amount of time for which the backup water was able to operate.
        backup_desalinator_water_frame = backup_desalinator_water_frame.mul(
            1 - blackout_times
        )

        # Find total energy used by the system
        total_energy_used = pd.DataFrame(
            renewables_energy_used_directly.values
            + storage_power_supplied_frame.values
            + grid_energy.values
            + diesel_energy.values
            + excess_energy_used_desalinating_frame.values
        )

        power_used_on_electricity = (
            total_energy_used
            - excess_energy_used_desalinating_frame
            - clean_water_power_consumed
            - thermal_desalination_electric_power_consumed
            - hot_water_power_consumed
        )

        # Compute the outputs from the itteration stage
        total_clean_water_supplied = pd.DataFrame(
            renewable_clean_water_used_directly.values
            + storage_water_supplied_frame.values
            + backup_desalinator_water_frame.values
            + clean_water_supplied_by_excess_energy_frame.values
            + conventional_clean_water_supplied_frame.values
        ).mul((1 - blackout_times))

        water_surplus_frame = (
            (total_clean_water_supplied - processed_total_clean_water_load) > 0
        ) * (total_clean_water_supplied - processed_total_clean_water_load)

        total_clean_water_used = total_clean_water_supplied - water_surplus_frame

        # Compute when the water demand went unmet.
        unmet_clean_water = pd.DataFrame(
            processed_total_clean_water_load.values - total_clean_water_supplied.values
        )
        unmet_clean_water = unmet_clean_water * (unmet_clean_water > 0)

        # Convert the PV-T units to kWh.
        clean_water_pvt_electric_power_per_kwh = (
            clean_water_pvt_electric_power_per_unit / minigrid.pvt_panel.pv_unit
        )

        # Find the new clean-water blackout times, according to when there is unmet demand
        clean_water_blackout_times = ((unmet_clean_water > 0) * 1).astype(float)

        # Clean-water system performance outputs
        backup_desalinator_water_frame.columns = pd.Index(
            ["Clean water supplied via backup desalination (l)"]
        )
        clean_water_blackout_times.columns = pd.Index(["Clean water blackouts"])
        clean_water_power_consumed.columns = pd.Index(
            ["Power consumed providing clean water (kWh)"]
        )
        clean_water_supplied_by_excess_energy_frame.columns = pd.Index(
            ["Clean water supplied using excess minigrid energy (l)"]
        )
        conventional_clean_water_supplied_frame.columns = pd.Index(
            ["Drinking water supplied via conventional sources (l)"]
        )
        excess_energy_used_desalinating_frame.columns = pd.Index(
            ["Excess power consumed desalinating clean water (kWh)"]
        )
        hourly_clean_water_tank_storage_frame.columns = pd.Index(
            ["Water held in clean-water storage tanks (l)"]
        )
        processed_total_clean_water_load.columns = pd.Index(
            ["Total clean water demand (l)"]
        )
        power_used_on_electricity.columns = pd.Index(
            ["Power consumed providing electricity (kWh)"]
        )
        renewable_clean_water_produced.columns = pd.Index(
            ["Renewable clean water produced (l)"]
        )
        renewable_clean_water_used_directly.columns = pd.Index(
            ["Renewable clean water used directly (l)"]
        )
        storage_water_supplied_frame.columns = pd.Index(
            ["Clean water supplied via tank storage (l)"]
        )
        total_clean_water_used.columns = pd.Index(["Total clean water consumed (l)"])
        total_clean_water_supplied.columns = pd.Index(
            ["Total clean water supplied (l)"]
        )
        unmet_clean_water.columns = pd.Index(["Unmet clean water demand (l)"])
        water_surplus_frame.columns = pd.Index(["Water surplus (l)"])

        if scenario.pv_t:
            buffer_tank_temperature.columns = pd.Index(
                ["Buffer tank temperature (degC)"]
            )
            buffer_tank_volume_supplied.columns = pd.Index(
                ["Buffer tank output volume (l)"]
            )
            clean_water_pvt_collector_output_temperature.columns = pd.Index(
                ["Clean-water PV-T output temperature (degC)"]
            )
            clean_water_pvt_electric_power_per_kwh.columns = pd.Index(
                ["Clean-water PV-T electric energy supplied per kWh"]
            )
            thermal_desalination_electric_power_consumed.columns = pd.Index(
                ["Power consumed running thermal desalination (kWh)"]
            )

    else:
        # Find total energy used by the system
        total_energy_used = pd.DataFrame(
            renewables_energy_used_directly.values
            + storage_power_supplied_frame.values
            + grid_energy.values
            + diesel_energy.values
        )

    if scenario.hot_water_scenario is not None:
        # Process any errors.
        if hot_water_tank_temperature is None:
            raise InternalError("Hot-water tank temperature undefined.")
        if hot_water_pvt_collector_output_temperature is None:
            raise InternalError("Hot-water PV-T output temperature undefined.")
        if minigrid.pvt_panel is None:
            raise InternalError("PV-T panel not defined.")

        # Convert the PV-T units to kWh.
        hot_water_pvt_electric_power_per_kwh: pd.DataFrame = pd.DataFrame(
            hot_water_pvt_electric_power_per_unit / minigrid.pvt_panel.pv_unit  # type: ignore
        )
        hot_water_power_consumed.columns = pd.Index(
            ["Power consumed providing hot water (kWh)"]
        )

        # Add headers to the columns.
        hot_water_power_consumed.columns = pd.Index(
            ["Power consumed supplying hot water (kWh)"]
        )
        hot_water_pvt_collector_output_temperature.columns = pd.Index(
            ["Hot-water PV-T output temperature (degC)"]
        )
        hot_water_pvt_electric_power_per_kwh.columns = pd.Index(
            ["Hot-water PV-T electric energy supplied per kWh"]
        )
        hot_water_tank_temperature.columns = pd.Index(
            ["Hot-water tank temperature (degC)"]
        )
        hot_water_tank_volume_supplied.columns = pd.Index(
            ["Hot-water tank volume supplied (l)"]
        )
        processed_total_hot_water_load.columns = pd.Index(
            ["Total hot-water demand (l)"]
        )
        renewable_hot_water_fraction.columns = pd.Index(
            ["Renewable hot-water fraction"]
        )

    # System performance outputs
    battery_health_frame.columns = pd.Index(["Battery health"])
    blackout_times.columns = pd.Index(["Blackouts"])
    diesel_fuel_usage.columns = pd.Index(["Diesel fuel usage (l)"])
    diesel_times.columns = pd.Index(["Diesel times"])
    energy_surplus_frane.columns = pd.Index(["Dumped energy (kWh)"])
    hourly_battery_storage_frame.columns = pd.Index(["Hourly storage (kWh)"])
    households.columns = pd.Index(["Households"])
    diesel_energy.columns = pd.Index(["Diesel energy (kWh)"])
    kerosene_mitigation.columns = pd.Index(["Kerosene mitigation"])
    kerosene_usage.columns = pd.Index(["Kerosene lamps"])
    storage_power_supplied_frame.columns = pd.Index(["Storage energy supplied (kWh)"])
    total_energy_used.columns = pd.Index(["Total energy used (kWh)"])
    unmet_energy.columns = pd.Index(["Unmet energy (kWh)"])

    # System details
    system_details = SystemDetails(
        diesel_capacity,
        simulation.end_year,
        clean_water_pvt_size
        * float(
            solar_degradation(minigrid.pvt_panel.lifetime, location.max_years).iloc[
                8760 * (simulation.end_year - simulation.start_year), 0
            ]
        )
        if minigrid.pvt_panel is not None and scenario.desalination_scenario is not None
        else None,
        hot_water_pvt_size
        * float(
            solar_degradation(minigrid.pvt_panel.lifetime, location.max_years).iloc[
                8760 * (simulation.end_year - simulation.start_year), 0
            ]
        )
        if minigrid.pvt_panel is not None and scenario.hot_water_scenario is not None
        else None,
        number_of_buffer_tanks if scenario.desalination_scenario is not None else None,
        number_of_clean_water_tanks
        if scenario.desalination_scenario is not None
        else None,
        number_of_hot_water_tanks if scenario.hot_water_scenario is not None else None,
        pv_size
        * float(
            solar_degradation(minigrid.pv_panel.lifetime, location.max_years).iloc[
                8760 * (simulation.end_year - simulation.start_year), 0
            ]
        ),
        float(
            electric_storage_size
            * minigrid.battery.storage_unit
            * np.min(battery_health_frame["Battery health"])
        ),
        clean_water_pvt_size
        if minigrid.pvt_panel is not None and scenario.desalination_scenario is not None
        else None,
        hot_water_pvt_size
        if minigrid.pvt_panel is not None and scenario.hot_water_scenario is not None
        else None,
        number_of_buffer_tanks if scenario.desalination_scenario is not None else None,
        number_of_clean_water_tanks
        if scenario.desalination_scenario is not None
        else None,
        number_of_hot_water_tanks if scenario.hot_water_scenario is not None else None,
        pv_size,
        float(electric_storage_size * minigrid.battery.storage_unit),
        [source.name for source in required_clean_water_feedwater_sources]
        if len(required_clean_water_feedwater_sources) > 0
        else None,
        simulation.start_year,
    )

    # Separate out the various renewable inputs.
    pv_energy = renewables_energy_map[RenewableEnergySource.PV]
    clean_water_pvt_energy = renewables_energy_map[
        RenewableEnergySource.CLEAN_WATER_PV_T
    ]
    hot_water_pvt_energy = renewables_energy_map[RenewableEnergySource.HOT_WATER_PV_T]
    total_pvt_energy = pd.DataFrame(
        clean_water_pvt_energy.values + hot_water_pvt_energy.values
    )
    total_pvt_energy.columns = pd.Index(["Total PV-T electric energy supplied (kWh)"])

    # End simulation timer
    timer_end = datetime.datetime.now()
    time_delta = timer_end - timer_start

    # Return all outputs
    system_performance_outputs_list = [
        load_energy,
        total_energy_used,
        unmet_energy,
        blackout_times,
        renewables_energy_used_directly,
        storage_power_supplied_frame,
        grid_energy,
        diesel_energy,
        diesel_times,
        diesel_fuel_usage,
        battery_storage_profile,
        pv_energy,
        renewables_energy,
        hourly_battery_storage_frame,
        energy_surplus_frane,
        battery_health_frame,
        households,
        kerosene_usage,
        kerosene_mitigation,
    ]

    if (
        scenario.desalination_scenario is not None
        or scenario.hot_water_scenario is not None
    ):
        system_performance_outputs_list.append(total_pvt_energy)
    if scenario.desalination_scenario is not None:
        system_performance_outputs_list.extend(
            [
                backup_desalinator_water_frame,
                clean_water_blackout_times,
                clean_water_power_consumed,
                clean_water_supplied_by_excess_energy_frame,
                conventional_clean_water_supplied_frame,
                excess_energy_used_desalinating_frame,
                hourly_clean_water_tank_storage_frame,
                power_used_on_electricity,
                processed_total_clean_water_load,
                renewable_clean_water_produced,
                renewable_clean_water_used_directly,
                storage_water_supplied_frame,
                total_clean_water_supplied,
                total_clean_water_used,
                unmet_clean_water,
                water_surplus_frame,
            ]
        )
        if scenario.pv_t:
            system_performance_outputs_list.extend(
                [
                    buffer_tank_temperature,
                    buffer_tank_volume_supplied,
                    clean_water_pvt_collector_output_temperature,
                    clean_water_pvt_electric_power_per_kwh,
                    clean_water_pvt_energy,
                    thermal_desalination_electric_power_consumed,
                ]
            )

    if scenario.hot_water_scenario is not None:
        system_performance_outputs_list.extend(
            [
                hot_water_power_consumed,
                hot_water_pvt_collector_output_temperature,
                hot_water_pvt_electric_power_per_kwh,
                hot_water_pvt_electric_power_per_unit,
                hot_water_pvt_energy,
                hot_water_tank_temperature,
                hot_water_tank_volume_supplied,
                processed_total_hot_water_load,
                renewable_hot_water_fraction,
            ]
        )

    system_performance_outputs = pd.concat(
        system_performance_outputs_list,
        axis=1,
    )

    return time_delta, system_performance_outputs, system_details


# #%%
# class MinigridOld:
#     """
#     Represents an energy system in the context of CLOVER.

#     """

#     def __init__(self):
#         """
#         Instantiate a :class:`minigrid.Minigrid` instance.

#         """

#         self.kerosene_data_filepath = os.path.join(
#             self.location_filepath, "Load", "Devices in use", "kerosene_in_use.csv"
#         )
#         self.kerosene_usage = pd.read_csv(
#             self.kerosene_data_filepath, index_col=0
#         ).reset_index(drop=True)

#     #%%
#     # =============================================================================
#     # SIMULATION FUNCTIONS
#     #       This function simulates the energy system of a given capacity and to
#     #       the parameters stated in the input files.
#     # =============================================================================

#     #%%
#     # =============================================================================
#     # GENERAL FUNCTIONS
#     #       These functions allow users to save simulations and open previous ones,
#     #       and resimulate the entire lifetime of a previously-optimised system
#     #       including consideration of increasing capacity.
#     # =============================================================================

#     def lifetime_simulation(self, optimisation_report):
#         """
#         Simulates a minigrid over its lifetime.

#         Simulates a minigrid system over the course of its lifetime to get the complete
#         technical performance of the system

#         Inputs:
#             - optimisation_report:
#                 Report of outputs from Optimisation().multiple_optimisation_step()

#         Outputs:
#             - lifetime_output:
#                 The lifetime technical performance of the system

#         """
#         # Initialise
#         optimisation_report = optimisation_report.reset_index(drop=True)
#         lifetime_output = pd.DataFrame([])
#         simulation_periods = np.size(optimisation_report, 0)
#         # Iterate over all simulation periods
#         for sim in range(simulation_periods):
#             system_performance_outputs = self.simulation(
#                 start_year=int(optimisation_report["Start year"][sim]),
#                 end_year=int(optimisation_report["End year"][sim]),
#                 pv_size=float(optimisation_report["Initial PV size"][sim]),
#                 electric_storage_size=float(
#                     optimisation_report["Initial storage size"][sim]
#                 ),
#             )
#             lifetime_output = pd.concat(
#                 [lifetime_output, system_performance_outputs[0]], axis=0
#             )
#         return lifetime_output.reset_index(drop=True)

#     #%%
#     # =============================================================================
#     # ENERGY BALANCE FUNCTIONS
#     #       These functions identify the sources and uses of energy in the system,
#     #       such as generation, loads and the overall balance
#     # =============================================================================
#     #%% Energy balance

#     #%% Energy usage
