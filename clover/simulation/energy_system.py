#!/usr/bin/python3
########################################################################################
# minigrid.py - Energy-system main module for CLOVER.                             #
#                                                                                      #
# Authors: Phil Sandwell, Ben Winchester                                               #
# Copyright: Phil Sandwell, 2018                                                       #
# Date created: 13/07/2021                                                             #
# License: Open source                                                                 #

# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
minigrid.py - The energy-system module for CLOVER.

This module carries out a simulation for an energy system based on the various inputs
and profile files that have been parsed/generated.

"""

import dataclasses
import datetime
import math
import os

from logging import Logger
from typing import Any, Dict, List, Optional, Tuple

import numpy as np  # type: ignore
import pandas as pd  # type: ignore

from tqdm import tqdm  # type: ignore

from ..__utils__ import (
    BColours,
    DieselMode,
    DemandType,
    DistributionNetwork,
    InputFileError,
    LoadType,
    Location,
    Scenario,
    Simulation,
    SystemDetails,
)
from ..conversion.conversion import Convertor
from ..generation.solar import solar_degradation
from ..load.load import population_hourly
from ..simulation.diesel import (
    DieselBackupGenerator,
    get_diesel_energy_and_times,
    get_diesel_fuel_usage,
)

from .storage import Battery

__all__ = (
    "Minigrid",
    "run_simulation",
)


@dataclasses.dataclass
class Minigrid:
    """
    Represents an energy system.

    .. attribute:: ac_to_ac_conversion_efficiency
        The conversion efficiency from AC to AC.

    .. attribute:: ac_to_dc_conversion_efficiency
        The conversion efficiency from AC to DC.

    .. attribute:: ac_transmission_efficiency
        The AC transmission efficiency, if applicable.

    .. attribute:: battery
        The battery being modelled, if applicable.

    .. attribute:: dc_to_ac_conversion_efficiency
        The conversion efficiency from DC to AC.

    .. attribute:: dc_to_dc_conversion_efficiency
        The conversion efficiency from DC to DC.

    .. attribute:: dc_transmission_efficiency
        The DC transmission efficiency, if applicable.

    .. attribute:: diesel_backup_generator
        The diesel backup generator associated with the minigrid system.

    """

    ac_to_ac_conversion_efficiency: Optional[float]
    ac_to_dc_conversion_efficiency: Optional[float]
    ac_transmission_efficiency: Optional[float]
    battery: Optional[Battery]
    dc_to_ac_conversion_efficiency: Optional[float]
    dc_to_dc_conversion_efficiency: Optional[float]
    dc_transmission_efficiency: Optional[float]
    diesel_backup_generator: Optional[DieselBackupGenerator]

    @classmethod
    def from_dict(
        cls,
        diesel_backup_generator: DieselBackupGenerator,
        minigrid_inputs: Dict[str, Any],
        battery_inputs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Returns a :class:`Minigrid` instance based on the inputs provided.

        Inputs:
            - diesel_backup_generator:
                The diesel backup generator to use for the run.
            - minigrid_inputs:
                The inputs for the minigrid/energy system, extracted from the input
                file.

        Outputs:
            - A :class:`Minigrid` instance based on the inputs provided.

        """

        # Parse the battery information.
        batteries = {
            entry["name"]: Battery.from_dict(entry) for entry in battery_inputs
        }

        # Return the minigrid instance.
        return cls(
            minigrid_inputs["conversion"]["ac_to_ac"]
            if "ac_to_ac" in minigrid_inputs["conversion"]
            else None,
            minigrid_inputs["conversion"]["ac_to_ac"]
            if "ac_to_dc" in minigrid_inputs["conversion"]
            else None,
            minigrid_inputs["ac_transmission_efficiency"]
            if "ac_transmission_efficiency" in minigrid_inputs
            else None,
            batteries[minigrid_inputs["battery"]]
            if "battery" in minigrid_inputs
            else None,
            minigrid_inputs["conversion"]["ac_to_ac"]
            if "dc_to_ac" in minigrid_inputs["conversion"]
            else None,
            minigrid_inputs["conversion"]["ac_to_ac"]
            if "dc_to_dc" in minigrid_inputs["conversion"]
            else None,
            minigrid_inputs["dc_transmission_efficiency"]
            if "dc_transmission_efficiency" in minigrid_inputs
            else None,
            diesel_backup_generator,
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
            processed_total_load = total_load[DemandType.COMMERCIAL.value]  # type: ignore

    if scenario.demands.public:
        if processed_total_load is not None:
            processed_total_load += pd.DataFrame(
                total_load[DemandType.PUBLIC.value].values
            )
        else:
            processed_total_load = total_load[DemandType.PUBLIC.value]  # type: ignore

    if processed_total_load is None:
        raise Exception("At least one load type must be specified.")

    return processed_total_load


def _get_electric_storage_profile(
    *,
    grid_profile: pd.DataFrame,
    kerosene_usage: pd.DataFrame,
    logger: Logger,
    minigrid: Minigrid,
    scenario: Scenario,
    solar_lifetime: int,
    total_solar_power_produced: pd.DataFrame,
    end_hour: int = 4,
    pv_size: int = 10,
    start_hour: int = 0,
    total_electric_load: pd.DataFrame,
) -> Tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame
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
        - scenario:
            The scenatio being considered.
        - solar_lifetime:
            The lifetime of the solar setup.
        - total_solar_power_produced:
            The total solar power output over the time period.
        - end_year:
            End year of this simulation period
        - pv_size:
            Amount of PV in kWp
        - start_year:
            Start year of this simulation period
        - total_electric_load:
            The total electric load for the system.

    Outputs:
        - load_energy:
            Amount of energy (kWh) required to satisfy theloads
        - renewables_energy:
            Amount of energy (kWh) provided by renewables to the system
        - renewables_energy_used_directly:
            Amount of energy (kWh) from renewables used directly to satisfy load (kWh)
        - grid_energy:
            Amount of energy (kWh) supplied by the grid
        - storage_profile:
            Amount of energy (kWh) into (+ve) and out of (-ve) the battery
        - kerosene_usage:
            Number of kerosene lamps in use (if no power available)

    """

    # Initialise power generation, including degradation of PV
    pv_generation_array = total_solar_power_produced * pv_size
    solar_degradation_array = solar_degradation(solar_lifetime)[  # type: ignore
        0 : (end_hour - start_hour)
    ]
    pv_generation = pd.DataFrame(
        np.asarray(pv_generation_array[start_hour:end_hour])  # type: ignore
        * np.asarray(solar_degradation_array)
    )
    grid_status = pd.DataFrame(grid_profile[start_hour:end_hour].values)  # type: ignore

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
    load_energy = total_electric_load / transmission_efficiency
    pv_energy = pv_generation.mul(transmission_efficiency)

    # Combine energy from all renewables sources
    renewables_energy = pv_energy  # + wind_energy + ...
    # Add more renewable sources here as required

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
            ((remaining_profile < 0) * remaining_profile).values
            * -1.0
            * grid_status.values
        )
        storage_profile: pd.DataFrame = pd.DataFrame(
            remaining_profile.values + grid_energy.values
        )

    else:
        # Take energy from grid first
        grid_energy = load_energy.mul(grid_status)
        # as needed for load
        remaining_profile = (grid_energy <= 0).mul(load_energy)
        # Then take energy from PV
        storage_profile = pd.DataFrame(
            renewables_energy.values.subtrace(remaining_profile.values)
        )
        renewables_energy_used_directly = pd.DataFrame(
            (storage_profile > 0)
            .mul(remaining_profile)
            .add((storage_profile < 0).mul(renewables_energy))
        )

    load_energy.columns = ["Load energy (kWh)"]
    renewables_energy.columns = ["Renewables energy supplied (kWh)"]
    renewables_energy_used_directly.columns = ["Renewables energy used (kWh)"]
    grid_energy.columns = ["Grid energy (kWh)"]
    storage_profile.columns = ["Storage profile (kWh)"]
    kerosene_usage.columns = ["Kerosene lamps"]

    return (
        load_energy,
        renewables_energy,
        renewables_energy_used_directly,
        grid_energy,
        storage_profile,
        kerosene_usage,
    )


def _get_water_storage_profile(
    convertors: List[Convertor],
    processed_total_clean_water_load: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Gets the storage profile for the clean-water system.

    Inputs:
        - convertors:
            The list of convertors available to the system.
        - processed_total_clean_water_load:
            The total clean-water load placed on the system.

    Outputs:
        - demand_met_through_electric_power:
            The demand which was met through electric power taken from the minigrid.
        - power_consumed:
            The electric power consumed in providing the water demand.
        - unmet_water:
            The unmet water demand.

    """

    water_convertors: List[Convertor] = sorted(
        [
            convertor
            for convertor in convertors
            if convertor.input_load_type == LoadType.ELECTRIC
            and convertor.output_load_type == LoadType.CLEAN_WATER
        ]
    )
    unmet_water = processed_total_clean_water_load.copy()

    demand_met_through_electric_power = pd.DataFrame([0] * unmet_water.size)
    power_consumed: pd.DataFrame = pd.DataFrame([0] * unmet_water.size)

    # While there is unmet water demand and there are still water convertors available:
    while any(unmet_water.values > 0) and len(water_convertors) > 0:
        current_convertor = water_convertors.pop(0)

        # Compute the delivered water as the minimum of the values in the unmet water
        # and the total water that is deliverable from this conversion device.
        delivered_water = pd.DataFrame(
            [
                min(entry, current_convertor.maximum_output_capacity)
                for entry in unmet_water[0]
            ]
        )

        # Compute the power that was consumed and the remaining unmet water demand.
        demand_met_through_electric_power += delivered_water
        power_consumed += delivered_water.mul(current_convertor.consumption)
        unmet_water -= delivered_water

    # Return the unmet water and power consumed.
    return demand_met_through_electric_power, power_consumed, unmet_water


def run_simulation(
    convertors: List[Convertor],
    minigrid: Minigrid,
    grid_profile: pd.DataFrame,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    pv_size: float,
    scenario: Scenario,
    simulation: Simulation,
    solar_lifetime: int,
    storage_size: float,
    total_clean_water_load: pd.DataFrame,
    total_electric_load: pd.DataFrame,
    total_solar_power_produced: pd.DataFrame,
) -> Tuple[float, pd.DataFrame, SystemDetails]:
    """
    Simulates a minigrid system

    This function simulates the energy system of a given capacity and to the parameters
    stated in the input files.

    Inputs:
        - convertors:
            The `list` of :class:`Convertor` instances available to be used.
        - diesel_backup_generator:
            The backup diesel generator for the system being modelled.
        - minigrid:
            The energy system being considered.
        - grid_profile:
            The grid-availability profile.
        - kerosene_usage:
            The kerosene-usage profile.
        - location:
            The location being considered.
        - pv_size:
            Amount of PV in kWp
        - scenario:
            The scenario being considered.
        - simulation:
            The simulation to run.
        - solar_lifetime:
            The lifetime of the solar system being considered.
        - storage_size:
            Amount of storage in kWh
        - total_clean_water_load:
            The total water load placed on the system.
        - total_electric_load:
            The total load in Watts.
        - total_solar_power_produced:
            The total energy outputted by the solar system.

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
            - storage_profile:
                Amount of energy (kWh) into (+ve) and out of (-ve) the battery
            - renewables_energy:
                Amount of energy (kWh) provided by renewables to the system
            - hourly_storage:
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

    ###############
    # Clean water #
    ###############

    if LoadType.CLEAN_WATER in scenario.load_types:
        processed_total_clean_water_load = _get_processed_load_profile(
            scenario, total_clean_water_load
        )[start_hour:end_hour]
        (
            clean_water_demand_met_through_electric_power,
            clean_water_power_consumed,
            unmet_clean_water,
        ) = _get_water_storage_profile(convertors, processed_total_clean_water_load)
        total_clean_water_supplied = pd.DataFrame(
            clean_water_demand_met_through_electric_power.values
        )
    else:
        clean_water_demand_met_through_electric_power = None
        clean_water_power_consumed = pd.DataFrame([0] * (end_hour - start_hour))
        total_clean_water_supplied = None
        unmet_clean_water = None

    ###############
    # Electricity #
    ###############

    processed_total_electric_load = (
        _get_processed_load_profile(scenario, total_electric_load)[start_hour:end_hour]
        + 0.001 * clean_water_power_consumed
    )

    # Get electric input profiles
    (
        load_energy,
        renewables_energy,
        renewables_energy_used_directly,
        grid_energy,
        storage_profile,
        kerosene_profile,
    ) = _get_electric_storage_profile(
        grid_profile=grid_profile,
        kerosene_usage=kerosene_usage,
        logger=logger,
        minigrid=minigrid,
        scenario=scenario,
        solar_lifetime=solar_lifetime,
        total_solar_power_produced=total_solar_power_produced,
        end_hour=end_hour,
        pv_size=pv_size,
        start_hour=start_hour,
        total_electric_load=processed_total_electric_load,
    )
    households = pd.DataFrame(
        population_hourly(location)[
            simulation.start_year * 8760 : simulation.end_year * 8760
        ].values
    )

    # Initialise battery storage parameters
    max_energy_throughput = storage_size * minigrid.battery.cycle_lifetime
    initial_storage = storage_size * minigrid.battery.maximum_charge
    max_storage = storage_size * minigrid.battery.maximum_charge
    min_storage = storage_size * minigrid.battery.minimum_charge
    cumulative_storage_power = 0.0
    hourly_storage = []
    new_hourly_storage = []
    battery_health = []

    # Initialise energy accounting parameters
    energy_surplus = []
    energy_deficit = []
    storage_power_supplied = []

    # Do not do the itteration if no storage is being used
    if storage_size == 0:
        simulation_hours = int(storage_profile.size)
        hourly_storage = pd.DataFrame([0] * simulation_hours)
        storage_power_supplied = pd.DataFrame([0] * simulation_hours)
        energy_surplus = ((storage_profile > 0) * storage_profile).abs()
        energy_deficit = ((storage_profile < 0) * storage_profile).abs()
        battery_health = pd.DataFrame([0] * simulation_hours)

    else:
        # Begin simulation, iterating over timesteps
        for t in tqdm(
            range(int(storage_profile.size)),
            desc="hourly computation",
            leave=False,
            unit="hour",
        ):
            battery_energy_flow = storage_profile.iloc[t][0]
            if t == 0:
                new_hourly_storage = initial_storage + battery_energy_flow
            else:
                # Battery charging
                if battery_energy_flow >= 0.0:
                    new_hourly_storage = hourly_storage[t - 1] * (
                        1.0 - minigrid.battery.leakage
                    ) + minigrid.battery.conversion_in * min(
                        battery_energy_flow,
                        minigrid.battery.charge_rate * (max_storage - min_storage),
                    )
                # Battery discharging
                else:
                    new_hourly_storage = hourly_storage[t - 1] * (
                        1.0 - minigrid.battery.leakage
                    ) + (1.0 / minigrid.battery.conversion_out) * max(
                        battery_energy_flow,
                        (-1.0)
                        * minigrid.battery.discharge_rate
                        * (max_storage - min_storage),
                    )

            # Dumped energy and unmet demand
            energy_surplus.append(
                max(new_hourly_storage - max_storage, 0.0)
            )  # Battery too full
            energy_deficit.append(
                max(min_storage - new_hourly_storage, 0.0)
            )  # Battery too empty

            # Battery capacities and blackouts (if battery is too full or empty)
            if new_hourly_storage >= max_storage:
                new_hourly_storage = max_storage
            if new_hourly_storage <= min_storage:
                new_hourly_storage = min_storage

            # Update hourly_storage
            hourly_storage.append(new_hourly_storage)

            # Update battery health
            if t == 0:
                storage_power_supplied.append(0.0 - battery_energy_flow)
            else:
                storage_power_supplied.append(
                    max(
                        hourly_storage[t - 1] * (1.0 - minigrid.battery.leakage)
                        - hourly_storage[t],
                        0.0,
                    )
                )
            cumulative_storage_power = (
                cumulative_storage_power + storage_power_supplied[t]
            )

            storage_degradation = 1.0 - minigrid.battery.lifetime_loss * (
                cumulative_storage_power / max_energy_throughput
            )
            max_storage = (
                storage_degradation * storage_size * minigrid.battery.maximum_charge
            )
            min_storage = (
                storage_degradation * storage_size * minigrid.battery.minimum_charge
            )
            battery_health.append(storage_degradation)

    # Consolidate outputs from iteration stage
    storage_power_supplied = pd.DataFrame(storage_power_supplied)

    # Find unmet energy
    unmet_energy = pd.DataFrame(
        (
            load_energy.values
            - renewables_energy_used_directly.values
            - grid_energy.values
            - storage_power_supplied.values
        )
    )
    blackout_times = ((unmet_energy > 0) * 1).astype(float)

    # Use backup diesel generator
    if scenario.diesel_scenario.mode == DieselMode.BACKUP:
        diesel_energy, diesel_times = get_diesel_energy_and_times(
            unmet_energy, blackout_times, scenario.diesel_scenario.backup_threshold
        )
        diesel_capacity = math.ceil(np.max(diesel_energy))
        diesel_fuel_usage = pd.DataFrame(
            get_diesel_fuel_usage(
                diesel_capacity,
                minigrid.diesel_backup_generator,
                diesel_energy,
                diesel_times,
            ).values
        )
        unmet_energy = pd.DataFrame(unmet_energy.values - diesel_energy.values)
        diesel_energy = diesel_energy.abs()
    else:
        diesel_energy = pd.DataFrame([0.0] * int(storage_profile.size))
        diesel_times = pd.DataFrame([0.0] * int(storage_profile.size))
        diesel_fuel_usage = pd.DataFrame([0.0] * int(storage_profile.size))
        diesel_capacity = 0.0

    # Find new blackout times, according to when there is unmet energy
    blackout_times = ((unmet_energy > 0) * 1).astype(float)
    # Ensure all unmet energy is calculated correctly, removing any negative values
    unmet_energy = ((unmet_energy > 0) * unmet_energy).abs()

    # Find how many kerosene lamps are in use
    kerosene_usage = blackout_times.mul(kerosene_profile[start_hour:end_hour].values)
    kerosene_mitigation = (1 - blackout_times).mul(
        kerosene_profile[start_hour:end_hour].values
    )

    # Find total energy used by the system
    total_energy_used = pd.DataFrame(
        renewables_energy_used_directly.values
        + storage_power_supplied.values
        + grid_energy.values
        + diesel_energy.values
        + 0.001 * clean_water_power_consumed.values
    )

    if LoadType.CLEAN_WATER in scenario.load_types:
        # Determine the clean water which was not delivered due to there not being
        # enough electricity.
        blackout_water = pd.DataFrame(
            [
                1 if entry > 0 else 0
                for entry in clean_water_demand_met_through_electric_power.mul(
                    blackout_times
                ).values
            ]
        )
        clean_water_demand_met_through_electric_power -= blackout_water
        unmet_clean_water += blackout_water

        # Find out how much of the minigrid power was used providing electricity as
        # opposed to clean water.
        power_used_on_electricity = (
            total_energy_used - 0.001 * clean_water_power_consumed
        )

        # Clean-water system performance outputs
        blackout_water.columns = ["Water supply blackouts"]
        clean_water_demand_met_through_electric_power.columns = [
            "Water supplied by direct electricity (l)"
        ]
        clean_water_power_consumed.columns = [
            "Power consumed providing clean water (kWh)"
        ]
        power_used_on_electricity.columns = [
            "Power consumed providing electricity (kWh)"
        ]
        total_clean_water_supplied.columns = ["Total clean water supplied (l)"]
        unmet_clean_water.columns = ["Unmet clean water demand (l)"]

    # System performance outputs
    blackout_times.columns = ["Blackouts"]
    hourly_storage = pd.DataFrame(hourly_storage)
    hourly_storage.columns = ["Hourly storage (kWh)"]
    energy_surplus = pd.DataFrame(energy_surplus)
    energy_surplus.columns = ["Dumped energy (kWh)"]
    unmet_energy.columns = ["Unmet energy (kWh)"]
    storage_power_supplied.columns = ["Storage energy supplied (kWh)"]
    diesel_energy.columns = ["Diesel energy (kWh)"]
    battery_health = pd.DataFrame(battery_health)
    battery_health.columns = ["Battery health"]
    diesel_times.columns = ["Diesel times"]
    diesel_fuel_usage.columns = ["Diesel fuel usage (l)"]
    households.columns = ["Households"]
    kerosene_usage.columns = ["Kerosene lamps"]
    kerosene_mitigation.columns = ["Kerosene mitigation"]
    total_energy_used.columns = ["Total energy used (kWh)"]

    # System details
    system_details = SystemDetails(
        diesel_capacity,
        simulation.end_year,
        pv_size
        * float(
            solar_degradation(solar_lifetime)[0][
                8760 * (simulation.end_year - simulation.start_year)
            ]
        ),
        float(storage_size * np.min(battery_health["Battery health"])),
        pv_size,
        float(storage_size),
        simulation.start_year,
    )

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
        storage_power_supplied,
        grid_energy,
        diesel_energy,
        diesel_times,
        diesel_fuel_usage,
        storage_profile,
        renewables_energy,
        hourly_storage,
        energy_surplus,
        battery_health,
        households,
        kerosene_usage,
        kerosene_mitigation,
    ]

    if LoadType.CLEAN_WATER in scenario.load_types:
        system_performance_outputs_list.extend(
            [
                blackout_water,
                clean_water_demand_met_through_electric_power,
                0.001 * clean_water_power_consumed,
                power_used_on_electricity,
                total_clean_water_supplied,
                unmet_clean_water,
            ]
        )

    system_performance_outputs = pd.concat(
        system_performance_outputs_list,
        axis=1,
    )

    return time_delta, system_performance_outputs, system_details


#%%
class MinigridOld:
    """
    Represents an energy system in the context of CLOVER.

    """

    def __init__(self):
        """
        Instantiate a :class:`minigrid.Minigrid` instance.

        """

        self.kerosene_data_filepath = os.path.join(
            self.location_filepath, "Load", "Devices in use", "kerosene_in_use.csv"
        )
        self.kerosene_usage = pd.read_csv(
            self.kerosene_data_filepath, index_col=0
        ).reset_index(drop=True)

    #%%
    # =============================================================================
    # SIMULATION FUNCTIONS
    #       This function simulates the energy system of a given capacity and to
    #       the parameters stated in the input files.
    # =============================================================================

    #%%
    # =============================================================================
    # GENERAL FUNCTIONS
    #       These functions allow users to save simulations and open previous ones,
    #       and resimulate the entire lifetime of a previously-optimised system
    #       including consideration of increasing capacity.
    # =============================================================================

    def lifetime_simulation(self, optimisation_report):
        """
        Simulates a minigrid over its lifetime.

        Simulates a minigrid system over the course of its lifetime to get the complete
        technical performance of the system

        Inputs:
            - optimisation_report:
                Report of outputs from Optimisation().multiple_optimisation_step()

        Outputs:
            - lifetime_output:
                The lifetime technical performance of the system

        """
        # Initialise
        optimisation_report = optimisation_report.reset_index(drop=True)
        lifetime_output = pd.DataFrame([])
        simulation_periods = np.size(optimisation_report, 0)
        # Iterate over all simulation periods
        for sim in range(simulation_periods):
            system_performance_outputs = self.simulation(
                start_year=int(optimisation_report["Start year"][sim]),
                end_year=int(optimisation_report["End year"][sim]),
                pv_size=float(optimisation_report["Initial PV size"][sim]),
                storage_size=float(optimisation_report["Initial storage size"][sim]),
            )
            lifetime_output = pd.concat(
                [lifetime_output, system_performance_outputs[0]], axis=0
            )
        return lifetime_output.reset_index(drop=True)

    #%%
    # =============================================================================
    # ENERGY BALANCE FUNCTIONS
    #       These functions identify the sources and uses of energy in the system,
    #       such as generation, loads and the overall balance
    # =============================================================================
    #%% Energy balance

    #%% Energy usage
