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
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np  # type: ignore  # pylint: disable=import-error
import pandas as pd  # type: ignore  # pylint: disable=import-error

from tqdm import tqdm  # type: ignore  # pylint: disable=import-error

from ..__utils__ import (
    BColours,
    CleanWaterMode,
    DieselMode,
    DemandType,
    DistributionNetwork,
    InputFileError,
    ResourceType,
    Location,
    Scenario,
    Simulation,
    SystemDetails,
)
from ..conversion.conversion import Convertor
from ..generation.solar import solar_degradation
from ..load.load import population_hourly
from .diesel import (
    DieselBackupGenerator,
    get_diesel_energy_and_times,
    get_diesel_fuel_usage,
)
from .solar import PVPanel
from .storage import Battery, CleanWaterTank

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

    .. attribute:: clean_water_tank
        The clean-water tank being modelled, if applicable.

    .. attribute:: dc_to_ac_conversion_efficiency
        The conversion efficiency from DC to AC.

    .. attribute:: dc_to_dc_conversion_efficiency
        The conversion efficiency from DC to DC.

    .. attribute:: dc_transmission_efficiency
        The DC transmission efficiency, if applicable.

    .. attribute:: diesel_backup_generator
        The diesel backup generator associated with the minigrid system.

    .. attribute:: pv_panel
        The PV panel being considered.

    """

    ac_to_ac_conversion_efficiency: Optional[float]
    ac_to_dc_conversion_efficiency: Optional[float]
    ac_transmission_efficiency: Optional[float]
    battery: Optional[Battery]
    clean_water_tank: Optional[CleanWaterTank]
    dc_to_ac_conversion_efficiency: Optional[float]
    dc_to_dc_conversion_efficiency: Optional[float]
    dc_transmission_efficiency: Optional[float]
    diesel_backup_generator: Optional[DieselBackupGenerator]
    pv_panel: PVPanel

    @classmethod
    def from_dict(
        cls,
        diesel_backup_generator: DieselBackupGenerator,
        minigrid_inputs: Dict[Union[int, str], Any],
        pv_panel: PVPanel,
        battery_inputs: Optional[List[Dict[Union[int, str], Any]]] = None,
        tank_inputs: Optional[List[Dict[Union[int, str], Any]]] = None,
    ) -> Any:
        """
        Returns a :class:`Minigrid` instance based on the inputs provided.

        Inputs:
            - diesel_backup_generator:
                The diesel backup generator to use for the run.
            - minigrid_inputs:
                The inputs for the minigrid/energy system, extracted from the input
                file.
            - pv_panel:
                 The :class:`PVPanel` instance to use for the run.
            - battery_inputs:
                The battery input information.
            - tank_inputs:
                The tank input information.

        Outputs:
            - A :class:`Minigrid` instance based on the inputs provided.

        """

        # Parse the battery information.
        if battery_inputs is not None:
            batteries = {
                entry["name"]: Battery.from_dict(entry) for entry in battery_inputs
            }
        else:
            batteries = dict()

        # Parse the tank information.
        if tank_inputs is not None:
            tanks = {
                entry["name"]: CleanWaterTank.from_dict(entry) for entry in tank_inputs
            }
        else:
            tanks = dict()

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
            tanks[minigrid_inputs["clean_water_tank"]]
            if "clean_water_tank" in minigrid_inputs
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
            pv_panel,
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


def _get_electric_battery_storage_profile(
    *,
    grid_profile: pd.DataFrame,
    kerosene_usage: pd.DataFrame,
    logger: Logger,
    minigrid: Minigrid,
    processed_total_electric_load: pd.DataFrame,
    scenario: Scenario,
    solar_lifetime: int,
    total_solar_power_produced: pd.DataFrame,
    end_hour: int = 4,
    pv_size: float = 10,
    start_hour: int = 0,
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
        - processed_total_electric_load:
            The total electric load for the system.
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

    Outputs:
        - load_energy:
            Amount of energy (kWh) required to satisfy theloads
        - renewables_energy:
            Amount of energy (kWh) provided by renewables to the system
        - renewables_energy_used_directly:
            Amount of energy (kWh) from renewables used directly to satisfy load (kWh)
        - grid_energy:
            Amount of energy (kWh) supplied by the grid
        - battery_storage_profile:
            Amount of energy (kWh) into (+ve) and out of (-ve) the battery
        - kerosene_usage:
            Number of kerosene lamps in use (if no power available)

    """

    # Initialise power generation, including degradation of PV
    pv_generation_array = total_solar_power_produced * pv_size
    solar_degradation_array = solar_degradation(solar_lifetime)[  # type: ignore
        0 : (end_hour - start_hour)
    ][0]
    pv_generation = pd.DataFrame(
        np.asarray(pv_generation_array[start_hour:end_hour])  # type: ignore
        * np.asarray(solar_degradation_array)
    )

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

    # Combine energy from all renewables sources
    renewables_energy: pd.DataFrame = pv_energy  # + wind_energy + ...
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

    load_energy.columns = pd.Index(["Load energy (kWh)"])
    renewables_energy.columns = pd.Index(["Renewables energy supplied (kWh)"])
    renewables_energy_used_directly.columns = pd.Index(["Renewables energy used (kWh)"])
    grid_energy.columns = pd.Index(["Grid energy (kWh)"])
    battery_storage_profile.columns = pd.Index(["Storage profile (kWh)"])
    kerosene_usage.columns = pd.Index(["Kerosene lamps"])

    return (
        load_energy,
        renewables_energy,
        renewables_energy_used_directly,
        grid_energy,
        battery_storage_profile,
        kerosene_usage,
    )


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


def run_simulation(
    convertors: List[Convertor],
    minigrid: Minigrid,
    grid_profile: pd.DataFrame,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    number_of_clean_water_tanks: int,
    pv_size: float,
    scenario: Scenario,
    simulation: Simulation,
    electric_storage_size: float,
    total_clean_water_load: Optional[pd.DataFrame],
    total_electric_load: pd.DataFrame,
    total_solar_power_produced: pd.DataFrame,
) -> Tuple[datetime.timedelta, pd.DataFrame, SystemDetails]:
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
        - number_of_clean_water_tanks:
            The number of clean-water tanks installed in the system.
        - pv_size:
            Amount of PV in kWp
        - scenario:
            The scenario being considered.
        - simulation:
            The simulation to run.
        - electric_storage_size:
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

    ###############
    # Clean water #
    ###############

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
            pd.DataFrame([0] * simulation_hours),
        )
        total_clean_water_supplied = pd.DataFrame(
            renewable_clean_water_used_directly.values
        )
    else:
        clean_water_power_consumed = pd.DataFrame([0] * simulation_hours)
        renewable_clean_water_used_directly = pd.DataFrame([0] * simulation_hours)

    ###############
    # Electricity #
    ###############

    processed_total_electric_load = pd.DataFrame(
        _get_processed_load_profile(scenario, total_electric_load)[
            start_hour:end_hour
        ].values
        + clean_water_power_consumed.values
    )

    # Get electric input profiles
    (
        load_energy,
        renewables_energy,
        renewables_energy_used_directly,
        grid_energy,
        battery_storage_profile,
        kerosene_profile,
    ) = _get_electric_battery_storage_profile(
        grid_profile=grid_profile[start_hour:end_hour],  # type: ignore
        kerosene_usage=kerosene_usage[start_hour:end_hour],  # type: ignore
        logger=logger,
        minigrid=minigrid,
        processed_total_electric_load=processed_total_electric_load,
        scenario=scenario,
        solar_lifetime=minigrid.pv_panel.lifetime,
        total_solar_power_produced=total_solar_power_produced,
        end_hour=end_hour,
        pv_size=pv_size,
        start_hour=start_hour,
    )
    households = pd.DataFrame(
        population_hourly(location)[  # type: ignore
            simulation.start_year * 8760 : simulation.end_year * 8760
        ].values
    )

    # Initialise battery storage parameters
    max_energy_throughput: float = (
        electric_storage_size * minigrid.battery.cycle_lifetime
    )
    initial_battery_storage: float = (
        electric_storage_size * minigrid.battery.maximum_charge
    )
    max_battery_storage: float = electric_storage_size * minigrid.battery.maximum_charge
    min_battery_storage: float = electric_storage_size * minigrid.battery.minimum_charge
    cumulative_battery_storage_power: float = 0.0
    hourly_battery_storage: Dict[int, float] = {}
    new_hourly_battery_storage: float = 0.0
    battery_health: Dict[int, float] = {}

    # Initialise tank storage parameters
    if ResourceType.CLEAN_WATER in scenario.resource_types:
        clean_water_power_consumed_mapping: Dict[
            int, float
        ] = clean_water_power_consumed[  # type: ignore
            0
        ].to_dict()
        hourly_tank_storage: Dict[int, float] = {}
        initial_tank_storage: float = 0.0

        try:
            max_tank_storage: float = (
                number_of_clean_water_tanks
                * minigrid.clean_water_tank.mass  # type: ignore
                * minigrid.clean_water_tank.maximum_charge  # type: ignore
            )
        except AttributeError:
            raise InputFileError(
                "energy system OR tank",
                "No clean-water tank was provided on the energy system despite clean-"
                "water demands being expected.",
            ) from None

        try:
            min_tank_storage: float = (
                number_of_clean_water_tanks
                * minigrid.clean_water_tank.mass  # type: ignore
                * minigrid.clean_water_tank.minimum_charge  # type: ignore
            )
        except AttributeError:
            raise InputFileError(
                "energy system OR tank",
                "No clean-water tank was provided on the energy system despite clean-"
                "water demands being expected.",
            ) from None

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
        water_pumps: List[Convertor] = sorted(
            [
                convertor
                for convertor in convertors
                if list(convertor.input_resource_consumption) == [ResourceType.ELECTRIC]
                and convertor.output_resource_type == ResourceType.UNCLEAN_WATER
            ]
        )

        # Compute the amount of energy required per litre desalinated.
        energy_per_desalinated_litre = 0.001 * np.mean(
            [
                desalinator.input_resource_consumption[ResourceType.ELECTRIC]
                / desalinator.maximum_output_capacity
                + desalinator.input_resource_consumption[ResourceType.UNCLEAN_WATER]
                * water_pumps[0].input_resource_consumption[ResourceType.ELECTRIC]
                / desalinator.maximum_output_capacity
                for desalinator in electric_desalinators
            ]
        )

        # Compute the maximum throughput
        maximum_water_throughput = min(
            sum(
                [
                    desalinator.maximum_output_capacity
                    for desalinator in electric_desalinators
                ]
            ),
            sum([water_pumps[0].maximum_output_capacity]),
        )

        # Intialise tank accounting parameters
        backup_desalinator_water_supplied: Dict[int, float] = {}
        excess_energy_used_desalinating: Dict[int, float] = {}
        storage_water_supplied: Dict[int, float] = {}
        water_demand_met_by_excess_energy: Dict[int, float] = {}
        water_supplied_by_excess_energy: Dict[int, float] = {}
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
            ###############
            # Electricity #
            ###############

            battery_energy_flow = battery_storage_profile.iloc[t][0]
            if t == 0:
                new_hourly_battery_storage = (
                    initial_battery_storage + battery_energy_flow
                )
            else:
                # Battery charging
                if battery_energy_flow >= 0.0:
                    new_hourly_battery_storage = hourly_battery_storage[t - 1] * (
                        1.0 - minigrid.battery.leakage
                    ) + minigrid.battery.conversion_in * min(
                        battery_energy_flow,
                        minigrid.battery.charge_rate
                        * (max_battery_storage - min_battery_storage),
                    )
                # Battery discharging
                else:
                    new_hourly_battery_storage = hourly_battery_storage[t - 1] * (
                        1.0 - minigrid.battery.leakage
                    ) + (1.0 / minigrid.battery.conversion_out) * max(
                        battery_energy_flow,
                        (-1.0)
                        * minigrid.battery.discharge_rate
                        * (max_battery_storage - min_battery_storage),
                    )

            excess_energy = max(battery_energy_flow - max_battery_storage, 0.0)

            ###############
            # Clean water #
            ###############

            if ResourceType.CLEAN_WATER in scenario.resource_types:
                tank_water_flow = tank_storage_profile.iloc[t][0]  # type: ignore

                # Compute the new tank level based on the previous level and the flow.
                if t == 0:
                    current_net_water_flow = initial_tank_storage + tank_water_flow
                else:
                    current_net_water_flow = (
                        hourly_tank_storage[t - 1]
                        * (1.0 - minigrid.clean_water_tank.leakage)  # type: ignore
                        + tank_water_flow
                    )

                # Use the excess energy to desalinate if there is space.
                if excess_energy > 0:
                    # Compute the maximum amount of water that can be desalinated.
                    max_desalinated_water = min(
                        excess_energy / energy_per_desalinated_litre,
                        maximum_water_throughput,
                    )

                    # Add this to the tank and fulfil the demand if relevant.
                    current_hourly_tank_storage = (
                        current_net_water_flow + max_desalinated_water
                    )

                    # Compute the amount of water that was actually desalinated.
                    desalinated_water = min(
                        max_desalinated_water,
                        max_tank_storage - current_net_water_flow,
                    )

                    # Compute the remaining excess energy and the energy used in
                    # desalination.
                    energy_consumed = energy_per_desalinated_litre * desalinated_water
                    new_hourly_battery_storage -= energy_consumed

                    # Ensure that the excess energy is normalised correctly.
                    excess_energy = max(
                        new_hourly_battery_storage - max_battery_storage, 0.0
                    )

                    # Store this as water and electricity supplied using excess power.
                    excess_energy_used_desalinating[t] = energy_consumed
                    water_demand_met_by_excess_energy[t] = max(
                        0, -current_net_water_flow
                    )
                    water_supplied_by_excess_energy[t] = desalinated_water
                else:
                    excess_energy_used_desalinating[t] = 0
                    water_demand_met_by_excess_energy[t] = 0
                    water_supplied_by_excess_energy[t] = 0
                    current_hourly_tank_storage = current_net_water_flow

                # If there is still unmet water demand, then carry out desalination and
                # pumping to fulfil the demand.
                if (
                    current_hourly_tank_storage < 0
                    and scenario.clean_water_mode == CleanWaterMode.PRIORITISE
                ):
                    # If there is unmet demand, then carry out desalination and pumping to
                    # fulfil the demand.
                    current_unmet_water_demand = -current_hourly_tank_storage

                    # Compute the electricity consumed meeting this demand.
                    energy_consumed = (
                        energy_per_desalinated_litre * current_unmet_water_demand
                    )

                    # Withdraw this energy from the batteries.
                    new_hourly_battery_storage -= (
                        1.0 / minigrid.battery.conversion_out
                    ) * energy_consumed

                    # Ensure that the excess energy is normalised correctly.
                    excess_energy = max(
                        new_hourly_battery_storage - max_battery_storage, 0.0
                    )

                    # Store this as water and electricity supplied by backup.
                    clean_water_power_consumed_mapping[t] += energy_consumed
                    backup_desalinator_water_supplied[t] = current_unmet_water_demand
                else:
                    clean_water_power_consumed_mapping[t] = 0
                    backup_desalinator_water_supplied[t] = 0

                current_hourly_tank_storage = min(
                    current_hourly_tank_storage, max_tank_storage
                )
                current_hourly_tank_storage = max(
                    current_hourly_tank_storage, min_tank_storage
                )

                hourly_tank_storage[t] = current_hourly_tank_storage

                if t == 0:
                    storage_water_supplied[t] = 0.0 - tank_water_flow
                else:
                    storage_water_supplied[t] = max(
                        hourly_tank_storage[t - 1]
                        * (1.0 - minigrid.clean_water_tank.leakage)  # type: ignore
                        - hourly_tank_storage[t],
                        0.0,
                    )

            ###############
            # Electricity #
            ###############

            # Dumped energy and unmet demand
            energy_surplus[t] = excess_energy  # Battery too full
            energy_deficit[t] = max(
                min_battery_storage - new_hourly_battery_storage, 0.0
            )  # Battery too empty

            # Battery capacities and blackouts (if battery is too full or empty)
            new_hourly_battery_storage = min(
                new_hourly_battery_storage, max_battery_storage
            )
            new_hourly_battery_storage = max(
                new_hourly_battery_storage, min_battery_storage
            )

            # Update hourly_battery_storage
            hourly_battery_storage[t] = new_hourly_battery_storage

            # Update battery health
            if t == 0:
                storage_power_supplied[t] = 0.0 - battery_energy_flow
            else:
                storage_power_supplied[t] = max(
                    hourly_battery_storage[t - 1] * (1.0 - minigrid.battery.leakage)
                    - hourly_battery_storage[t],
                    0.0,
                )
            cumulative_battery_storage_power += storage_power_supplied[t]

            battery_storage_degradation = 1.0 - minigrid.battery.lifetime_loss * (
                cumulative_battery_storage_power / max_energy_throughput
            )
            max_battery_storage = (
                battery_storage_degradation
                * electric_storage_size
                * minigrid.battery.maximum_charge
            )
            min_battery_storage = (
                battery_storage_degradation
                * electric_storage_size
                * minigrid.battery.minimum_charge
            )
            battery_health[t] = battery_storage_degradation

    # Process the various outputs into dataframes.
    battery_health_frame: pd.DataFrame = pd.DataFrame(  # type: ignore
        list(battery_health.values()), index=list(battery_health.keys())
    ).sort_index()
    # energy_deficit_frame: pd.DataFrame = pd.DataFrame(  # type: ignore
    #     list(energy_deficit.values()), index=list(energy_deficit.keys())
    # ).sort_index()
    energy_surplus_frane: pd.DataFrame = pd.DataFrame(  # type: ignore
        list(energy_surplus.values()), index=list(energy_surplus.keys())
    ).sort_index()
    hourly_battery_storage_frame: pd.DataFrame = pd.DataFrame(  # type: ignore
        list(hourly_battery_storage.values()), index=list(hourly_battery_storage.keys())
    ).sort_index()
    storage_power_supplied_frame: pd.DataFrame = pd.DataFrame(  # type: ignore
        list(storage_power_supplied.values()), index=list(storage_power_supplied.keys())
    ).sort_index()

    if ResourceType.CLEAN_WATER in scenario.resource_types:
        backup_desalinator_water_frame: pd.DataFrame = pd.DataFrame(  # type: ignore
            list(backup_desalinator_water_supplied.values()),
            index=list(backup_desalinator_water_supplied.keys()),
        ).sort_index()
        clean_water_power_consumed: pd.DataFrame = pd.DataFrame(  # type: ignore
            list(clean_water_power_consumed_mapping.values()),
            index=list(clean_water_power_consumed_mapping.keys()),
        ).sort_index()
        excess_energy_used_desalinating_frame: pd.DataFrame = pd.DataFrame(  # type: ignore
            list(excess_energy_used_desalinating.values()),
            index=list(excess_energy_used_desalinating.keys()),
        ).sort_index()
        hourly_tank_storage_frame: pd.DataFrame = pd.DataFrame(  # type: ignore
            list(hourly_tank_storage.values()), index=list(hourly_tank_storage.keys())
        ).sort_index()
        storage_water_supplied_frame: pd.DataFrame = pd.DataFrame(  # type: ignore
            list(storage_water_supplied.values()),
            index=list(storage_water_supplied.keys()),
        ).sort_index()
        water_demand_met_by_excess_energy: pd.DataFrame = pd.DataFrame(  # type: ignore
            list(water_demand_met_by_excess_energy.values()),
            index=list(water_demand_met_by_excess_energy.keys()),
        ).sort_index()
        water_supplied_by_excess_energy_frame: pd.DataFrame = pd.DataFrame(  # type: ignore
            list(water_supplied_by_excess_energy.values()),
            index=list(water_supplied_by_excess_energy.keys()),
        ).sort_index()
        water_surplus_frame: pd.DataFrame = pd.DataFrame(  # type: ignore
            list(water_surplus.values()), index=list(water_surplus.keys())
        ).sort_index()

    # Find unmet energy
    unmet_energy = pd.DataFrame(
        (
            load_energy.values
            + clean_water_power_consumed.values
            - renewables_energy_used_directly.values
            - grid_energy.values
            - storage_power_supplied_frame.values
        )
    )
    blackout_times = ((unmet_energy > 0) * 1).astype(float)

    # Use backup diesel generator
    if scenario.diesel_scenario.mode == DieselMode.BACKUP:
        if scenario.diesel_scenario.backup_threshold is None:
            raise InputFileError(
                "diesel inputs",
                "Diesel mode `backup` was selected but no backup threshold was "
                "specified.",
            )
        if minigrid.diesel_backup_generator is None:
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
                minigrid.diesel_backup_generator,
                diesel_energy,
                diesel_times,
            ).values
        )
        unmet_energy = pd.DataFrame(unmet_energy.values - diesel_energy.values)
        diesel_energy = diesel_energy.abs()  # type: ignore
    elif scenario.diesel_scenario.mode == DieselMode.CYCLE_CHARGING:
        logger.error(
            "%sCycle charing is not currently supported.%s",
            BColours.fail,
            BColours.endc,
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
            # + clean_water_power_consumed.values
            + excess_energy_used_desalinating_frame.values
        )

        power_used_on_electricity = (
            total_energy_used
            - excess_energy_used_desalinating_frame  # type: ignore
            - clean_water_power_consumed  # type: ignore
        )

        # Compute the outputs from the itteration stage
        total_clean_water_supplied = pd.DataFrame(
            renewable_clean_water_used_directly.values
            + storage_water_supplied_frame.values
            + backup_desalinator_water_frame.values
            + water_supplied_by_excess_energy_frame.values
        )

        water_surplus_frame = (
            total_clean_water_supplied - processed_total_clean_water_load > 0  # type: ignore
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

        # Clean-water system performance outputs
        backup_desalinator_water_frame.columns = pd.Index(
            ["Clean water supplied via backup desalination (l)"]
        )
        clean_water_power_consumed.columns = pd.Index(
            ["Power consumed providing clean water (kWh)"]
        )
        excess_energy_used_desalinating_frame.columns = pd.Index(
            ["Excess power consumed desalinating clean water (kWh)"]
        )
        hourly_tank_storage_frame.columns = pd.Index(
            ["Water held in storage tanks (l)"]
        )
        processed_total_clean_water_load.columns = pd.Index(
            ["Total clean water demand (l)"]
        )
        power_used_on_electricity.columns = pd.Index(
            ["Power consumed providing electricity (kWh)"]
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
        water_supplied_by_excess_energy_frame.columns = pd.Index(
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

    # System performance outputs
    blackout_times.columns = pd.Index(["Blackouts"])
    hourly_battery_storage_frame.columns = pd.Index(["Hourly storage (kWh)"])
    energy_surplus_frane.columns = pd.Index(["Dumped energy (kWh)"])
    unmet_energy.columns = pd.Index(["Unmet energy (kWh)"])
    storage_power_supplied_frame.columns = pd.Index(["Storage energy supplied (kWh)"])
    diesel_energy.columns = pd.Index(["Diesel energy (kWh)"])
    battery_health_frame.columns = pd.Index(["Battery health"])
    diesel_times.columns = pd.Index(["Diesel times"])
    diesel_fuel_usage.columns = pd.Index(["Diesel fuel usage (l)"])
    households.columns = pd.Index(["Households"])
    kerosene_usage.columns = pd.Index(["Kerosene lamps"])
    kerosene_mitigation.columns = pd.Index(["Kerosene mitigation"])
    total_energy_used.columns = pd.Index(["Total energy used (kWh)"])

    # System details
    system_details = SystemDetails(
        diesel_capacity,
        simulation.end_year,
        pv_size
        * float(
            solar_degradation(minigrid.pv_panel.lifetime)[0][  # type: ignore
                8760 * (simulation.end_year - simulation.start_year)
            ]
        ),
        float(electric_storage_size * np.min(battery_health_frame["Battery health"])),
        pv_size,
        float(electric_storage_size),
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
        storage_power_supplied_frame,
        grid_energy,
        diesel_energy,
        diesel_times,
        diesel_fuel_usage,
        battery_storage_profile,
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
                clean_water_power_consumed,
                excess_energy_used_desalinating_frame,
                hourly_tank_storage_frame,
                power_used_on_electricity,
                processed_total_clean_water_load,
                renewable_clean_water_used_directly,
                storage_water_supplied_frame,
                total_clean_water_supplied,
                total_clean_water_used,
                unmet_clean_water,
                water_supplied_by_excess_energy_frame,
                water_surplus_frame,
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
