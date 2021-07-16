#!/usr/bin/python3
########################################################################################
# energy_system.py - Energy-system main module for CLOVER.                             #
#                                                                                      #
# Authors: Phil Sandwell, Ben Winchester                                               #
# Copyright: Phil Sandwell, 2018                                                       #
# Date created: 13/07/2021                                                             #
# License: Open source                                                                 #

# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                        #
########################################################################################
"""
energy_system.py - The energy-system module for CLOVER.

This module carries out a simulation for an energy system based on the various inputs
and profile files that have been parsed/generated.

"""

import dataclasses
import datetime
import math
import os

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from ..__utils__ import (
    DieselMode,
    DemandType,
    DistributionNetwork,
    Location,
    Scenario,
    Simulation,
)
from ..generation.solar import solar_degradation, total_solar_output
from ..generation.diesel import Diesel
from ..load.load import population_hourly

from .storage import Battery

__all__ = (
    "EnergySystem",
    "run_simulation",
)


@dataclasses.dataclass
class EnergySystem:
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

    """

    ac_to_ac_conversion_efficiency: Optional[float]
    ac_to_dc_conversion_efficiency: Optional[float]
    ac_transmission_efficiency: Optional[float]
    battery: Optional[Battery]
    dc_to_ac_conversion_efficiency: Optional[float]
    dc_to_dc_conversion_efficiency: Optional[float]
    dc_transmission_efficiency: Optional[float]


def _get_storage_profile(
    *,
    energy_system: EnergySystem,
    grid_profile: pd.DataFrame,
    scenario: Scenario,
    solar_lifetime: int,
    total_solar_output: pd.DataFrame,
    end_year: int = 4,
    pv_size: int = 10,
    start_year: int = 0,
) -> pd.DataFrame:
    """
    Gets the storage profile (energy in/out the battery) and other system energies.

    Inputs:
        - energy_system:
            The energy system being modelled.
        - grid_profile:
            The relevant grid profile, based on the scenario, for the simulation.
        - scenario:
            The scenatio being considered.
        - solar_lifetime:
            The lifetime of the solar setup.
        - total_solar_output:
            The total solar power output over the time period.
        - end_year:
            End year of this simulation period
        - pv_size:
            Amount of PV in kWp
        - start_year:
            Start year of this simulation period

    Outputs:
        load_energy                     Amount of energy (kWh) required to satisfy the loads
        renewables_energy               Amount of energy (kWh) provided by renewables to the system
        renewables_energy_used_directly Amount of energy (kWh) from renewables used directly to satisfy load (kWh)
        grid_energy                     Amount of energy (kWh) supplied by the grid
        storage_profile                 Amount of energy (kWh) into (+ve) and out of (-ve) the battery
        kerosene_usage                  Number of kerosene lamps in use (if no power available)
    """

    # Initialise simulation parameters
    start_hour = start_year * 8760
    end_hour = end_year * 8760

    # Initialise power generation, including degradation of PV
    pv_generation = total_solar_output.mul(pv_size).mul(
        solar_degradation(solar_lifetime)[0 : (end_hour - start_hour)]
    )
    grid_status = pd.DataFrame(grid_profile[start_hour:end_hour].values)
    load_profile = pd.DataFrame(self.get_load_profile()[start_hour:end_hour].values)

    # Consider power distribution network
    if scenario.distribution_network == DistributionNetwork.DC:
        pv_generation = pv_generation.mul(energy_system.dc_to_dc_conversion_efficiency)
        transmission_efficiency = energy_system.dc_transmission_efficiency
        # grid_conversion_eff = energy_system.ac_to_dc_conversion

    else:
        pv_generation = pv_generation.mul(energy_system.dc_to_ac_conversion_efficiency)
        transmission_efficiency = energy_system.ac_transmission_efficiency
        # grid_conversion_efficiency = energy_system.ac_to_ac_conversion

    # Consider transmission efficiency
    load_energy = load_profile.div(transmission_efficiency)
    pv_energy = pv_generation.mul(transmission_efficiency)

    # Combine energy from all renewables sources
    renewables_energy = pv_energy  # + wind_energy + ...
    # Add more renewable sources here as required

    # Check for self-generation prioritisation
    if scenario.prioritise_self_generation:
        # Take energy from PV first
        remaining_profile = pd.DataFrame(renewables_energy.values - load_energy.values)
        renewables_energy_used_directly = pd.DataFrame(
            (remaining_profile > 0) * load_energy.values
            + (remaining_profile < 0) * renewables_energy.values
        )

        # Then take energy from grid
        grid_energy = pd.DataFrame(
            ((remaining_profile < 0) * remaining_profile).values
            * -1.0
            * grid_status.values
        )
        storage_profile = pd.DataFrame(remaining_profile.values + grid_energy.values)

    else:
        # Take energy from grid first
        grid_energy = load_energy.mul(grid_status)
        # as needed for load
        remaining_profile = (grid_energy <= 0).mul(load_energy)
        # Then take energy from PV
        storage_profile = renewables_energy.values.subtrace(remaining_profile.values)
        renewables_energy_used_directly = (
            (storage_profile > 0)
            .mul(remaining_profile)
            .add((storage_profile < 0).mul(renewables_energy))
        )

    # Get kerosene usage
    kerosene_usage = pd.DataFrame(self.kerosene_usage[start_hour:end_hour].values)

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


def run_simulation(
    energy_system: EnergySystem,
    grid_profile: pd.DataFrame,
    location: Location,
    pv_size: float,
    scenario: Scenario,
    simulation: Simulation,
    solar_lifetime: int,
    storage_size: float,
) -> Tuple[float, pd.DataFrame]:
    """
    Simulates a minigrid system

    This function simulates the energy system of a given capacity and to the parameters
    stated in the input files.

    Inputs:
        - energy_system:
            The energy system being considered.
        - grid_profile:
            The grid-availability profile.
        - kerosene_profile:
            The kerosene profile.
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

    Outputs:
        - The time taken for the simulation.
        - tuple([system_performance_outputs,system_details]):
            system_performance_outputs          Hourly performance of the simulated system
                load_energy                     Amount of energy (kWh) required to satisfy the loads
                total_energy_used               Amount of energy (kWh) used by the system
                unmet_energy                    Amount of energy (kWh) unmet by the system
                blackout_times                  Times with power is available (0) or unavailable (1)
                renewables_energy_used_directly Amount of energy (kWh) from renewables used directly to satisfy load (kWh)
                storage_power_supplied          Amount of energy (kWh) supplied by battery storage
                grid_energy                     Amount of energy (kWh) supplied by the grid
                diesel_energy                   Amount of energy (kWh) supplied from diesel generator
                diesel_times                    Times when diesel generator is on (1) or off (0)
                diesel_fuel_usage               Amount of diesel (l) used by the generator
                storage_profile                 Amount of energy (kWh) into (+ve) and out of (-ve) the battery
                renewables_energy               Amount of energy (kWh) provided by renewables to the system
                hourly_storage                  Amount of energy (kWh) in the battery
                energy_surplus                  Amount of energy (kWh) dumped owing to overgeneration
                battery_health                  Relative capactiy of the battery compared to new (0.0-1.0)
                households                      Number of households in the community
                kerosene_usage                  Number of kerosene lamps in use (if no power available)
                kerosene_mitigation             Number of kerosene lamps not used (when power is available)
            system details                      Information about the installed system
                Start year                      Start year of the simulation
                End year                        End year of the simulation
                Initial PV size                 Capacity of PV installed (kWp)
                Initial storage size            Capacity of battery storage installed (kWh)
                Final PV size                   Equivalent capacity of PV (kWp) after simulation
                Final storage size              Equivalent capacity of battery storage (kWh) after simulation
                Diesel capacity                 Capacity of diesel generation installed (kW)
    """

    # Start timer to see how long simulation will take
    timer_start = datetime.datetime.now()

    # Get input profiles
    (
        load_energy,
        renewables_energy,
        renewables_energy_used_directly,
        grid_energy,
        storage_profile,
        kerosene_profile,
    ) = _get_storage_profile(
        energy_system=energy_system,
        grid_profile=grid_profile,
        scenario=scenario,
        solar_lifetime=solar_lifetime,
        total_solar_output=total_solar_output,
        end_year=simulation.end_year,
        pv_size=pv_size,
        start_year=simulation.start_year,
    )
    households = pd.DataFrame(
        population_hourly(location)[
            simulation.start_year * 8760 : simulation.end_year * 8760
        ].values
    )

    # Initialise battery storage parameters
    max_energy_throughput = storage_size * energy_system.battery.cycle_lifetime
    initial_storage = storage_size * energy_system.battery.maximum_charge
    max_storage = storage_size * energy_system.battery.maximum_charge
    min_storage = storage_size * energy_system.battery.minimum_charge
    cumulative_storage_power = 0.0
    hourly_storage = []
    new_hourly_storage = []
    battery_health = []

    # Initialise energy accounting parameters
    energy_surplus = []
    energy_deficit = []
    storage_power_supplied = []

    # Begin simulation, iterating over timesteps
    for t in range(0, int(storage_profile.size)):
        # Check if any storage is being used
        if storage_size == 0:
            simulation_hours = int(storage_profile.size)
            hourly_storage = pd.DataFrame([0] * simulation_hours)
            storage_power_supplied = pd.DataFrame([0] * simulation_hours)
            energy_surplus = ((storage_profile > 0) * storage_profile).abs()
            energy_deficit = ((storage_profile < 0) * storage_profile).abs()
            battery_health = pd.DataFrame([0] * simulation_hours)
            break
        battery_energy_flow = storage_profile.iloc[t][0]
        if t == 0:
            new_hourly_storage = initial_storage + battery_energy_flow
        else:
            if battery_energy_flow >= 0.0:  # Battery charging
                new_hourly_storage = hourly_storage[t - 1] * (
                    1.0 - energy_system.battery.leakage
                ) + energy_system.battery.conversion_in * min(
                    battery_energy_flow,
                    energy_system.battery.charge_rate * (max_storage - min_storage),
                )
            else:  # Battery discharging
                new_hourly_storage = hourly_storage[t - 1] * (
                    1.0 - energy_system.battery.leakage
                ) + (1.0 / energy_system.battery.conversion_out) * max(
                    battery_energy_flow,
                    (-1.0)
                    * energy_system.battery.discharge_rate
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
        elif new_hourly_storage <= min_storage:
            new_hourly_storage = min_storage
        # Update hourly_storage
        hourly_storage.append(new_hourly_storage)

        # Update battery health
        if t == 0:
            storage_power_supplied.append(0.0 - battery_energy_flow)
        else:
            storage_power_supplied.append(
                max(
                    hourly_storage[t - 1] * (1.0 - energy_system.battery.leakage)
                    - hourly_storage[t],
                    0.0,
                )
            )
        cumulative_storage_power = cumulative_storage_power + storage_power_supplied[t]

        storage_degradation = 1.0 - energy_system.battery.lifetime_loss * (
            cumulative_storage_power / max_energy_throughput
        )
        max_storage = (
            storage_degradation * storage_size * energy_system.battery.maximum_charge
        )
        min_storage = (
            storage_degradation * storage_size * energy_system.battery.minimum_charge
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
    if scenario.diesel_scenario == DieselMode.BACKUP:
        diesel_energy, diesel_times = Diesel().get_diesel_energy_and_times(
            unmet_energy, blackout_times, scenario.diesel_scenario.backup_threshold
        )
        diesel_capacity = math.ceil(np.max(diesel_energy))
        diesel_fuel_usage = pd.DataFrame(
            Diesel()
            .get_diesel_fuel_usage(diesel_capacity, diesel_energy, diesel_times)
            .values
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
    kerosene_usage = blackout_times.values.mul(kerosene_profile.values)
    kerosene_mitigation = (1 - blackout_times).mul(kerosene_profile.values)

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

    # Find total energy used by the system
    total_energy_used = pd.DataFrame(
        renewables_energy_used_directly.values
        + storage_power_supplied.values
        + grid_energy.values
        + diesel_energy.values
    )
    total_energy_used.columns = ["Total energy used (kWh)"]

    # System details
    system_details = pd.DataFrame(
        {
            "Start year": simulation.start_year,
            "End year": simulation.end_year,
            "Initial PV size": pv_size,
            "Initial storage size": storage_size,
            "Final PV size": pv_size
            * solar_degradation(solar_lifetime)[0][
                8760 * (simulation.end_year - simulation.start_year)
            ],
            "Final storage size": storage_size
            * np.min(battery_health["Battery health"]),
            "Diesel capacity": diesel_capacity,
        },
        index=["System details"],
    )

    # End simulation timer
    timer_end = datetime.datetime.now()
    time_delta = timer_end - timer_start

    # Return all outputs
    system_performance_outputs = pd.concat(
        [
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
        ],
        axis=1,
    )

    return time_delta, system_performance_outputs, system_details


#%%
class EnergySystemOld:
    """
    Represents an energy system in the context of CLOVER.

    """

    def __init__(self):
        """
        Instantiate a :class:`energy_system.EnergySystem` instance.

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
        Function:
            Simulates a minigrid system over the course of its lifetime to get the complete technical
                performance of the system
        Inputs:
            optimisation_report     Report of outputs from Optimisation().multiple_optimisation_step()
        Outputs:
            lifetime_output         The lifetime technical performance of the system
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
    def get_load_profile(self, scenario: Scenario, total_load: pd.DataFrame):
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

        total_energy_system_load: pd.DataFrame = pd.DataFrame(
            np.zeros(total_load[DemandType.DOMESTIC.value].shape)
        )

        # If no loads were specified, raise an error.
        if (
            not scenario.demands.domestic
            or scenario.demands.commercial
            or scenario.demands.public
        ):
            raise Exception(
                "At least one of domestic, commercial and public loads needs to be considered."
            )

        if scenario.demands.domestic:
            total_energy_system_load += total_load[DemandType.DOMESTIC.value]

        if scenario.demands.commercial:
            total_energy_system_load += total_load[DemandType.COMMERCIAL.value]

        if scenario.demands.public:
            total_energy_system_load += total_load[DemandType.PUBLIC.value]

        return total_energy_system_load
