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
from re import T
from typing import Dict, List, Optional, Tuple

import numpy as np  # type: ignore  # pylint: disable=import-error
import pandas as pd  # type: ignore  # pylint: disable=import-error

from tqdm import tqdm

from ..__utils__ import (
    BColours,
    CleanWaterMode,
    DieselMode,
    DemandType,
    DistributionNetwork,
    HTFMode,
    InputFileError,
    InternalError,
    ResourceType,
    Location,
    Scenario,
    Simulation,
    SystemDetails,
    dict_to_dataframe,
)
from ..conversion.conversion import Convertor, ThermalDesalinationPlant, WaterSource
from ..generation.solar import SolarPanelType, solar_degradation
from ..load.load import population_hourly
from .__utils__ import Minigrid
from .diesel import (
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
    maximum_battery_storage: float,
    minigrid: Minigrid,
    minimum_battery_storage: float,
    *,
    time_index: int,
) -> Tuple[float, float]:
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
        - maximum_battery_storage:
            The maximum amount of energy that can be stored in the batteries.
        - minigrid:
            The :class:`Minigrid` representing the system being considered.
        - minimum_battery_storage:
            The minimum amount of energy that can be stored in the batteries.
        - time_index:
            The current time (hour) being considered.

    Outputs:
        - excess_energy:
            The energy surplus generated which could not be stored in the batteries.
        - new_hourly_battery_storage;
            The computed level of energy stored in the batteries at this time step.

    """

    battery_energy_flow = battery_storage_profile.iloc[time_index][0]
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
        ResourceType.CLEAN_WATER in scenario.resource_types
        and scenario.desalination_scenario is not None
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


def _calculate_pvt_and_thermal_desalination_profiles(
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
    List[Convertor],
    Optional[pd.DataFrame],
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
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
        - feedwater_sources:
            The :class:`Convertor` instances which are a source of feedwater to the PV-T
            system.
        - pvt_collector_output_temperature:
            The output temperature of HTF from the PV-T collectors, measured in degrees
            Celcius.
        - pvt_electric_power_per_unit:
            The electric power produced by the PV-T, in kWh, per unit of PV-T installed.
        - renewable_clean_water_produced:
            The amount of clean water produced renewably, measured in litres.
        - tank_volume_supplied:
            The volume of buffer solution outputted by the HTF buffer tanks.
        - thermal_desalination_electric_power_consumed:
            The electric power consumed in operating the thermal desalination plant,
            measured in kWh.

    """

    if scenario.pv_t:
        if wind_speed_data is None:
            raise InternalError(
                "Wind speed data required in PV-T computation and not passed to the "
                "energy system module."
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

        # Determine the list of available feedwater sources.
        feedwater_sources: List[Convertor] = sorted(
            [
                convertor
                for convertor in convertors
                if list(convertor.input_resource_consumption) == [ResourceType.ELECTRIC]
                and convertor.output_resource_type == ResourceType.UNCLEAN_WATER
            ]
        )

        if (
            sum(
                [
                    feedwater_source.maximum_output_capacity
                    for feedwater_source in feedwater_sources
                ]
            )
            < thermal_desalination_plant.input_resource_consumption[
                ResourceType.UNCLEAN_WATER
            ]
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
                ResourceType.UNCLEAN_WATER
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
        pvt_collector_output_temperature: Optional[pd.DataFrame]
        buffer_tank_temperature: Optional[pd.DataFrame]
        (
            pvt_collector_output_temperature,
            pvt_electric_power_per_unit,
            buffer_tank_temperature,
            tank_volume_supplied,
        ) = calculate_pvt_output(
            end_hour,
            irradiance_data[start_hour:end_hour],  # type: ignore
            logger,
            minigrid,
            pvt_size,
            scenario,
            start_hour,
            temperature_data[start_hour:end_hour],  # type: ignore
            thermal_desalination_plant,
            wind_speed_data[start_hour:end_hour],  # type: ignore
        )
        logger.info("PV-T performance successfully computed.")

        # Compute the clean water supplied by the desalination unit.
        renewable_clean_water_produced: pd.DataFrame = pd.DataFrame(
            thermal_desalination_plant.maximum_output_capacity  # type: ignore
            * (tank_volume_supplied > 0)  # type: ignore
        )

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
        )

        buffer_tank_temperature = buffer_tank_temperature.reset_index(drop=True)
        pvt_collector_output_temperature = pvt_collector_output_temperature.reset_index(drop=True)
        pvt_electric_power_per_unit = pvt_electric_power_per_unit.reset_index(drop=True)
        renewable_clean_water_produced = renewable_clean_water_produced.reset_index(drop=True)
        tank_volume_supplied = tank_volume_supplied.reset_index(drop=True)
        thermal_desalination_electric_power_consumed = thermal_desalination_electric_power_consumed.reset_index(drop=True)

    else:
        buffer_tank_temperature = None
        feedwater_sources = []
        pvt_collector_output_temperature = None
        pvt_electric_power_per_unit = pd.DataFrame([0] * (end_hour - start_hour))
        renewable_clean_water_produced = pd.DataFrame([0] * (end_hour - start_hour))
        tank_volume_supplied = pd.DataFrame([0] * (end_hour - start_hour))
        thermal_desalination_electric_power_consumed = pd.DataFrame(
            [0] * (end_hour - start_hour)
        )

    return (
        buffer_tank_temperature,
        feedwater_sources,
        pvt_collector_output_temperature,
        pvt_electric_power_per_unit,
        renewable_clean_water_produced,
        tank_volume_supplied,
        thermal_desalination_electric_power_consumed,
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

    if ResourceType.CLEAN_WATER in scenario.resource_types:
        tank_water_flow = tank_storage_profile.iloc[time_index][0]  # type: ignore

        # Compute the new tank level based on the previous level and the flow.
        if time_index == 0:
            current_net_water_flow = initial_clean_water_tank_storage + tank_water_flow
        else:
            current_net_water_flow = (
                hourly_clean_water_tank_storage[time_index - 1]
                * (1.0 - minigrid.clean_water_tank.leakage)  # type: ignore
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
                * (1.0 - minigrid.clean_water_tank.leakage)  # type: ignore
                - hourly_clean_water_tank_storage[time_index],
                0.0,
            )

        return excess_energy


def _get_electric_battery_storage_profile(
    *,
    grid_profile: pd.DataFrame,
    kerosene_usage: pd.DataFrame,
    logger: Logger,
    minigrid: Minigrid,
    processed_total_electric_load: pd.DataFrame,
    renewables_power_produced: Dict[SolarPanelType, pd.DataFrame],
    scenario: Scenario,
    end_hour: int = 4,
    pv_size: float = 10,
    pvt_size: int = 0,
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
        - end_year:
            End year of this simulation period.
        - pv_size:
            Amount of PV in units of PV.
        - pvt_size:
            Amount of PV-T in units of PV-T.
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
            A mapping between :class:`SolarPanelType` and the associated electrical
            energy produced.
        - renewables_energy_used_directly:
            Amount of energy (kWh) from renewables used directly to satisfy load (kWh).

    """

    # Initialise power generation, including degradation of PV
    try:
        pv_power_produced = renewables_power_produced[SolarPanelType.PV]
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
    solar_degradation_array = solar_degradation(minigrid.pv_panel.lifetime)[  # type: ignore
        0 : (end_hour - start_hour)
    ][
        0
    ]
    pv_generation = pd.DataFrame(
        np.asarray(pv_generation_array[start_hour:end_hour])  # type: ignore
        * np.asarray(solar_degradation_array)
    )

    # Initialise PV-T power generation, including degradation of PV
    if minigrid.pvt_panel is not None:
        try:
            pvt_electric_power_produced = renewables_power_produced[SolarPanelType.PV_T]
        except KeyError:
            logger.error(
                "%sCould not determine PV-T power produced from renewables production "
                "despite a PV-T panel being defined on the system.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "No PV-T power in renewables_power_produced mapping despite a PV-T "
                "panel being specified."
            ) from None
        pvt_electric_generation_array = pvt_electric_power_produced * pvt_size
        pvt_degradation_array = solar_degradation(minigrid.pvt_panel.lifetime)[  # type: ignore
            0 : (end_hour - start_hour)
        ]
        pvt_electric_generation: Optional[pd.DataFrame] = pd.DataFrame(
            np.asarray(pvt_electric_generation_array)
            * np.asarray(pvt_degradation_array)
        )
    else:
        pvt_electric_generation = None

    # Consider power distribution network
    if scenario.distribution_network == DistributionNetwork.DC:
        pv_generation = pv_generation.mul(  # type: ignore
            minigrid.dc_to_dc_conversion_efficiency
        )
        transmission_efficiency = minigrid.dc_transmission_efficiency
        # grid_conversion_eff = minigrid.ac_to_dc_conversion

    else:
        pv_generation = pv_generation.mul(  # type: ignore
            minigrid.dc_to_ac_conversion_efficiency
        )
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
    load_energy: pd.DataFrame = (
        processed_total_electric_load / transmission_efficiency  # type: ignore
    )
    pv_energy = pv_generation * transmission_efficiency

    if pvt_electric_generation is not None:
        pvt_electric_energy: pd.DataFrame = (
            pvt_electric_generation * transmission_efficiency
        )
    else:
        pvt_electric_energy = pd.DataFrame([0] * pv_energy.size)

    # Combine energy from all renewables sources
    renewables_energy_map: Dict[SolarPanelType, pd.DataFrame] = {
        SolarPanelType.PV: pv_energy,
        SolarPanelType.PV_T: pvt_electric_energy,
        # RenewableGenerationSource.WIND: wind_energy,
    }
    # Add more renewable sources here as required
    renewables_energy: pd.DataFrame = pd.DataFrame(
        sum(renewables_energy_map.values())  # type: ignore
    )

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
            ((remaining_profile < 0) * remaining_profile).values  # type: ignore
            * -1.0
            * grid_profile.values
        )
        battery_storage_profile: pd.DataFrame = pd.DataFrame(
            remaining_profile.values + grid_energy.values
        )

    else:
        # Take energy from grid first
        grid_energy = grid_profile.mul(load_energy)  # type: ignore
        # as needed for load
        remaining_profile = (grid_energy <= 0).mul(load_energy)  # type: ignore
        # Then take energy from PV
        battery_storage_profile = pd.DataFrame(
            renewables_energy.values.subtrace(remaining_profile.values)  # type: ignore
        )
        renewables_energy_used_directly = pd.DataFrame(
            (battery_storage_profile > 0)  # type: ignore
            .mul(remaining_profile)
            .add((battery_storage_profile < 0).mul(renewables_energy))  # type: ignore
        )

    battery_storage_profile.columns = pd.Index(["Storage profile (kWh)"])
    grid_energy.columns = pd.Index(["Grid energy (kWh)"])
    kerosene_usage.columns = pd.Index(["Kerosene lamps"])
    load_energy.columns = pd.Index(["Load energy (kWh)"])
    renewables_energy.columns = pd.Index(["Renewables energy supplied (kWh)"])
    renewables_energy_map[SolarPanelType.PV].columns = pd.Index(["PV energy supplied (kWh)"])
    renewables_energy_map[SolarPanelType.PV_T].columns = pd.Index(["PV-T electric energy supplied (kWh)"])
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
            processed_total_load += pd.DataFrame(  # type: ignore
                total_load[DemandType.COMMERCIAL.value].values
            )
        else:
            processed_total_load = total_load[DemandType.COMMERCIAL.value]  # type: ignore

    if scenario.demands.public:
        if processed_total_load is not None:
            processed_total_load += pd.DataFrame(  # type: ignore
                total_load[DemandType.PUBLIC.value].values
            )
        else:
            processed_total_load = total_load[DemandType.PUBLIC.value]  # type: ignore

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
        0.001  # type: ignore
        * pd.DataFrame([0] * processed_total_clean_water_load.size),  # type: ignore
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

    power_consumed_mapping: Dict[int, float] = power_consumed[  # type: ignore
        0
    ].to_dict()

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
                number_of_tanks
                * tank.mass  # type: ignore
                * tank.maximum_charge  # type: ignore
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
                number_of_tanks
                * tank.mass  # type: ignore
                * tank.minimum_charge  # type: ignore
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
) -> Tuple[float, float]:
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
            THe amount of power supplied by the storage system.
        - time_index:
            The current time (hour) being considered.

    Outputs:
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

    return maximum_battery_storage, minimum_battery_storage


def run_simulation(
    conventional_clean_water_source_profiles: Dict[WaterSource, pd.DataFrame],
    convertors: List[Convertor],
    electric_storage_size: float,
    grid_profile: pd.DataFrame,
    irradiance_data: pd.Series,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: Minigrid,
    number_of_clean_water_tanks: int,
    pv_power_produced: pd.Series,
    pv_size: float,
    pvt_size: int,
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
        - pvt_size:
            Amount of PV-T in PV-T units.
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
    pvt_collector_output_temperature: Optional[pd.DataFrame]
    pvt_electric_power_per_unit: pd.DataFrame
    renewable_clean_water_produced: pd.DataFrame
    tank_volume_supplied: pd.DataFrame
    thermal_desalination_electric_power_consumed: pd.DataFrame

    logger.info("Calculating PV-T performance profiles.")
    (
        buffer_tank_temperature,
        feedwater_sources,
        pvt_collector_output_temperature,
        pvt_electric_power_per_unit,
        renewable_clean_water_produced,
        tank_volume_supplied,
        thermal_desalination_electric_power_consumed,
    ) = _calculate_pvt_and_thermal_desalination_profiles(
        convertors,
        end_hour,
        irradiance_data,
        logger,
        minigrid,
        pvt_size,
        scenario,
        start_hour,
        temperature_data,
        wind_speed_data,
    )
    logger.info("PV-T performance profiles determined.")
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
        "Mean PV-T electric power per unit: %s",
        np.mean(pvt_electric_power_per_unit.values),
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

    if ResourceType.CLEAN_WATER in scenario.resource_types:
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
            renewable_clean_water_produced,  # type: ignore
        )
        number_of_buffer_tanks: int = 1
    else:
        clean_water_power_consumed = pd.DataFrame([0] * simulation_hours)
        number_of_buffer_tanks = 0
        renewable_clean_water_used_directly = pd.DataFrame([0] * simulation_hours)

    # Calculate hot-water-related profiles.
    processed_total_hot_water_load: Optional[pd.DataFrame]
    if ResourceType.HOT_CLEAN_WATER in scenario.resource_types:
        if total_hot_water_load is None:
            raise Exception(
                f"{BColours.fail}A simulation was run that specified a hot-water load "
                + f"but no hot-water load was passed in.{BColours.endc}"
            )
        # Process the load profile based on the relevant scenario.
        hot_water_power_consumed = pd.DataFrame([0] * (end_hour - start_hour))
        number_of_hot_water_tanks: int = 0
        processed_total_hot_water_load = pd.DataFrame(
            _get_processed_load_profile(scenario, total_hot_water_load)[
                start_hour:end_hour
            ].values
        )
    else:
        hot_water_power_consumed = pd.DataFrame([0] * (end_hour - start_hour))
        number_of_hot_water_tanks = 0
        processed_total_hot_water_load = None

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
        + thermal_desalination_electric_power_consumed.values
    )

    # Compute the electric input profiles.
    battery_storage_profile: pd.DataFrame
    grid_energy: pd.DataFrame
    kerosene_profile: pd.DataFrame
    load_energy: pd.DataFrame
    renewables_energy: pd.DataFrame
    renewables_energy_map: Dict[SolarPanelType, pd.DataFrame] = {
        SolarPanelType.PV: pv_power_produced,
        SolarPanelType.PV_T: pvt_electric_power_per_unit,
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
        grid_profile=grid_profile[start_hour:end_hour],  # type: ignore
        kerosene_usage=kerosene_usage[start_hour:end_hour],  # type: ignore
        logger=logger,
        minigrid=minigrid,
        processed_total_electric_load=processed_total_electric_load,
        renewables_power_produced=renewables_energy_map,
        scenario=scenario,
        end_hour=end_hour,
        pv_size=pv_size,
        pvt_size=pvt_size,
        start_hour=start_hour,
    )

    # Determine the number of households in the community.
    households = pd.DataFrame(
        population_hourly(location)[  # type: ignore
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
        energy_surplus = (
            (battery_storage_profile > 0) * battery_storage_profile  # type: ignore
        ).abs()  # type: ignore
        energy_deficit = (
            (battery_storage_profile < 0) * battery_storage_profile  # type: ignore
        ).abs()  # type: ignore
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
                maximum_battery_storage,
                minigrid,
                minimum_battery_storage,
                time_index=t,
            )

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
                storage_power_supplied,
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
            maximum_battery_storage, minimum_battery_storage = _update_battery_health(
                battery_energy_flow,
                battery_health,
                cumulative_battery_storage_power,
                electric_storage_size,
                hourly_battery_storage,
                maximum_battery_energy_throughput,
                minigrid,
                storage_water_supplied,
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

    if ResourceType.CLEAN_WATER in scenario.resource_types:
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
            + clean_water_power_consumed.values
            + thermal_desalination_electric_power_consumed.values
            - renewables_energy_used_directly.values
            - grid_energy.values
            - storage_power_supplied_frame.values
        )
    )
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
    unmet_energy = ((unmet_energy > 0) * unmet_energy).abs()  # type: ignore
    # Ensure all unmet clean-water energy is considered.
    clean_water_power_consumed = clean_water_power_consumed.mul(  # type: ignore
        1 - blackout_times
    )
    thermal_desalination_electric_power_consumed = thermal_desalination_electric_power_consumed.mul(  # type: ignore
        1 - blackout_times
    )

    # Find how many kerosene lamps are in use
    kerosene_usage = blackout_times.mul(kerosene_profile.values)  # type: ignore
    kerosene_mitigation = (1 - blackout_times).mul(  # type: ignore
        kerosene_profile.values
    )

    if ResourceType.CLEAN_WATER in scenario.resource_types:
        # Compute the amount of time for which the backup water was able to operate.
        backup_desalinator_water_frame = backup_desalinator_water_frame.mul(  # type: ignore
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
            - excess_energy_used_desalinating_frame  # type: ignore
            - clean_water_power_consumed  # type: ignore
            - thermal_desalination_electric_power_consumed  # type: ignore
        )

        # Compute the outputs from the itteration stage
        total_clean_water_supplied = pd.DataFrame(
            renewable_clean_water_used_directly.values
            + storage_water_supplied_frame.values
            + backup_desalinator_water_frame.values
            + clean_water_supplied_by_excess_energy_frame.values
        ).mul(
            (1 - blackout_times)
        )  # type: ignore

        water_surplus_frame = (
            (total_clean_water_supplied - processed_total_clean_water_load) > 0  # type: ignore
        ) * (
            total_clean_water_supplied - processed_total_clean_water_load  # type: ignore
        )

        total_clean_water_used = (
            total_clean_water_supplied - water_surplus_frame  # type: ignore
        )

        # Compute when the water demand went unmet.
        unmet_clean_water = pd.DataFrame(
            processed_total_clean_water_load.values - total_clean_water_supplied.values
        )
        unmet_clean_water = unmet_clean_water * (unmet_clean_water > 0)  # type: ignore

        # Convert the PV-T units to kWh.
        pvt_electric_power_per_kwh = (
            pvt_electric_power_per_unit / minigrid.pvt_panel.pv_unit
        )

        # Find the new clean-water blackout times, according to when there is unmet demand
        clean_water_blackout_times = ((unmet_clean_water > 0) * 1).astype(float)

        # Clean-water system performance outputs
        backup_desalinator_water_frame.columns = pd.Index(
            ["Clean water supplied via backup desalination (l)"]
        )
        buffer_tank_temperature.columns = pd.Index(["Buffer tank temperature (degC)"])
        clean_water_blackout_times.columns = pd.Index(["Clean water blackouts"])
        clean_water_power_consumed.columns = pd.Index(
            ["Power consumed providing clean water (kWh)"]
        )
        conventional_clean_water_supplied_frame.columns = pd.Index(
            ["Clean water supplied via conventional sources (l)"]
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
        pvt_collector_output_temperature.columns = pd.Index(
            ["PV-T output temperature (degC)"]
        )
        pvt_electric_power_per_kwh.columns = pd.Index(
            ["PV-T electric energy supplied per kWh"]
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
        tank_volume_supplied.columns = pd.Index(["Buffer tank output volume (l)"])
        thermal_desalination_electric_power_consumed.columns = pd.Index(
            ["Power consumed running thermal desalination (kWh)"]
        )
        total_clean_water_used.columns = pd.Index(["Total clean water consumed (l)"])
        total_clean_water_supplied.columns = pd.Index(
            ["Total clean water supplied (l)"]
        )
        unmet_clean_water.columns = pd.Index(["Unmet clean water demand (l)"])
        clean_water_supplied_by_excess_energy_frame.columns = pd.Index(
            ["Clean water supplied using excess minigrid energy (l)"]
        )
        water_surplus_frame.columns = pd.Index(["Water surplus (l)"])

    else:
        # Find total energy used by the system
        total_energy_used = pd.DataFrame(
            renewables_energy_used_directly.values
            + storage_power_supplied_frame.values
            + grid_energy.values
            + diesel_energy.values
        )

    if ResourceType.HOT_CLEAN_WATER in scenario.resource_types:
        processed_total_hot_water_load.columns = pd.Index(
            ["Total hot-water demand (l)"]
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
        number_of_buffer_tanks
        if ResourceType.CLEAN_WATER in scenario.resource_types
        else None,
        number_of_clean_water_tanks
        if ResourceType.CLEAN_WATER in scenario.resource_types
        else None,
        number_of_hot_water_tanks
        if ResourceType.HOT_CLEAN_WATER in scenario.resource_types
        else None,
        pv_size
        * float(
            solar_degradation(minigrid.pv_panel.lifetime)[0][  # type: ignore
                8760 * (simulation.end_year - simulation.start_year)
            ]
        ),
        pvt_size
        * float(
            solar_degradation(minigrid.pvt_panel.lifetime)[0][  # type: ignore
                8760 * (simulation.end_year - simulation.start_year)
            ]
        )
        if minigrid.pvt_panel is not None
        else None,
        float(
            electric_storage_size
            * minigrid.battery.storage_unit
            * np.min(battery_health_frame["Battery health"])
        ),
        number_of_buffer_tanks
        if ResourceType.CLEAN_WATER in scenario.resource_types
        else None,
        number_of_clean_water_tanks
        if ResourceType.CLEAN_WATER in scenario.resource_types
        else None,
        number_of_hot_water_tanks
        if ResourceType.HOT_CLEAN_WATER in scenario.resource_types
        else None,
        pv_size,
        pvt_size if minigrid.pvt_panel is not None else None,
        float(electric_storage_size * minigrid.battery.storage_unit),
        simulation.start_year,
    )

    # Separate out the various renewable inputs.
    pv_energy = renewables_energy_map[SolarPanelType.PV].loc[start_hour:end_hour]
    pvt_energy = renewables_energy_map[SolarPanelType.PV_T].loc[start_hour:end_hour]

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

    if ResourceType.CLEAN_WATER in scenario.resource_types:
        system_performance_outputs_list.extend(
            [
                backup_desalinator_water_frame,
                buffer_tank_temperature,
                clean_water_blackout_times,
                clean_water_power_consumed,
                conventional_clean_water_supplied_frame,
                excess_energy_used_desalinating_frame,
                hourly_clean_water_tank_storage_frame,
                power_used_on_electricity,
                processed_total_clean_water_load,
                pvt_collector_output_temperature,
                pvt_electric_power_per_kwh,
                pvt_energy,
                renewable_clean_water_produced,
                renewable_clean_water_used_directly,
                storage_water_supplied_frame,
                tank_volume_supplied,
                thermal_desalination_electric_power_consumed,
                total_clean_water_supplied,
                total_clean_water_used,
                unmet_clean_water,
                clean_water_supplied_by_excess_energy_frame,
                water_surplus_frame,
            ]
        )
    if ResourceType.HOT_CLEAN_WATER in scenario.resource_types:
        system_performance_outputs_list.extend([processed_total_hot_water_load])

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
