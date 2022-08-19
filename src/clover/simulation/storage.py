#!/usr/bin/python3
########################################################################################
# storage.py - Storage module.                                                         #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2020                                                      #
# Date created: 16/07/2021                                                             #
# License: Open source                                                                 #
# Most recent update: 16/07/2021                                                       #
########################################################################################
"""
storage.py - The storage module for CLOVER.

CLOVER considers several storage media for various forms of energy. The various
calculations associated with these storage media are carried out in this module.

"""

from logging import Logger
from typing import Dict, Optional, Tuple

import pandas as pd
import numpy as np

from ..__utils__ import (
    BColours,
    CleanWaterMode,
    ColumnHeader,
    DistributionNetwork,
    InputFileError,
    InternalError,
    Location,
    RenewableEnergySource,
    Scenario,
)
from .__utils__ import Minigrid
from ..conversion.conversion import WaterSource
from ..generation.solar import solar_degradation

__all__ = (
    "battery_iteration_step",
    "cw_tank_iteration_step",
    "get_electric_battery_storage_profile",
    "get_water_storage_profile",
)


def battery_iteration_step(
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


def cw_tank_iteration_step(  # pylint: disable=too-many-locals
    backup_desalinator_water_supplied: Dict[int, float],
    clean_water_power_consumed_mapping: Dict[int, float],
    clean_water_demand_met_by_excess_energy: Dict[int, float],
    clean_water_supplied_by_excess_energy: Dict[int, float],
    conventional_cw_source_profiles: Optional[Dict[WaterSource, pd.DataFrame]],
    conventional_water_supplied: Dict[int, float],
    energy_per_desalinated_litre: float,
    excess_energy: float,
    excess_energy_used_desalinating: Dict[int, float],
    hourly_cw_tank_storage: Dict[int, float],
    initial_cw_tank_storage: float,
    logger: Logger,
    maximum_battery_storage: float,
    maximum_cw_tank_storage: float,
    maximum_water_throughput: float,
    minigrid: Minigrid,
    minimum_cw_tank_storage: float,
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
        - conventioanl_cw_source_profiles:
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
        - hourly_cw_tank_storage:
            A mapping between time index and the amount of clean water stored in the
            system.
        - initial_cw_tank_storage:
            The initial level of the clean water tanks.
        - maximum_battery_storage:
            The maximum amount of energy that can be stored in the batteries.
        - maximum_cw_tank_storage:
            The maximum storage of the clean-water tanks.
        - maximum_water_throughput:
            The maximum amount of water that can be desalinated electrically.
        - minigrid:
            The :class:`Minigrid` being used for the run.
        - minimum_cw_tank_storage:
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

        # Raise an error if there is no clean-water tank defined.
        if minigrid.clean_water_tank is not None:
            logger.error(
                "%sNo clean-water tank defined despite desalination being carried out"
                ".%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "minigrid inputs",
                "No clean-water tank defined despite desalination being modelled.",
            )

        # Compute the new tank level based on the previous level and the flow.
        if time_index == 0:
            current_net_water_flow = initial_cw_tank_storage + tank_water_flow
        else:
            current_net_water_flow = (
                hourly_cw_tank_storage[time_index - 1]
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
            current_hourly_cw_tank_storage = (
                current_net_water_flow + maximum_desalinated_water
            )

            # Compute the amount of water that was actually desalinated.
            desalinated_water = min(
                maximum_desalinated_water,
                maximum_cw_tank_storage - current_net_water_flow,
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
            current_hourly_cw_tank_storage = current_net_water_flow

        # If there is still unmet water demand, then carry out desalination and
        # pumping to fulfil the demand.
        current_unmet_water_demand: float = -current_hourly_cw_tank_storage
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
                1.0 / minigrid.battery.conversion_out  # type: ignore
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
            conventional_cw_available: float = 0
            if conventional_cw_source_profiles is not None:
                conventional_cw_available = float(
                    sum(  # type: ignore [arg-type]
                        entry.iloc[time_index]
                        for entry in conventional_cw_source_profiles.values()
                    )
                )
            conventional_cw_supplied = min(
                conventional_cw_available, current_unmet_water_demand
            )
            current_unmet_water_demand -= conventional_cw_supplied

            # Store this as water supplied through conventional means.
            conventional_water_supplied[time_index] = conventional_cw_supplied
        else:
            conventional_water_supplied[time_index] = 0

        current_hourly_cw_tank_storage = min(
            current_hourly_cw_tank_storage,
            maximum_cw_tank_storage,
        )
        current_hourly_cw_tank_storage = max(
            current_hourly_cw_tank_storage,
            minimum_cw_tank_storage,
        )

        hourly_cw_tank_storage[time_index] = current_hourly_cw_tank_storage

        if time_index == 0:
            storage_water_supplied[time_index] = 0.0 - tank_water_flow
        else:
            storage_water_supplied[time_index] = max(
                hourly_cw_tank_storage[time_index - 1]
                * (1.0 - minigrid.clean_water_tank.leakage)  # type: ignore
                - hourly_cw_tank_storage[time_index],
                0.0,
            )

    return excess_energy


def get_electric_battery_storage_profile(  # pylint: disable=too-many-locals, too-many-statements
    *,
    grid_profile: pd.Series,
    kerosene_usage: pd.Series,
    location: Location,
    logger: Logger,
    minigrid: Minigrid,
    processed_total_electric_load: pd.DataFrame,
    renewables_power_produced: Dict[RenewableEnergySource, pd.DataFrame],
    scenario: Scenario,
    clean_water_pvt_size: int = 0,
    end_hour: int = 4,
    hot_water_pvt_size: int = 0,
    pv_size: float = 10,
    start_hour: int = 0,
) -> Tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.Series,
    pd.DataFrame,
    pd.DataFrame,
    Dict[RenewableEnergySource, pd.DataFrame],
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
        pvt_degradation_array = solar_degradation(  # type: ignore
            minigrid.pvt_panel.lifetime, location.max_years
        )[0 : (end_hour - start_hour)]

        if (
            RenewableEnergySource.CLEAN_WATER_PVT not in renewables_power_produced
            and RenewableEnergySource.HOT_WATER_PVT not in renewables_power_produced
        ):
            logger.error(
                "%sA PV-T panel was defined on the system but no clean-water PV-T or "
                "hot-water PV-T electricity was generated.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "No PV-T electric power produced despite a PV-T panel being defined "
                "for the system.."
            )

        # Compute the clean-water PV-T electricity generated.
        if RenewableEnergySource.CLEAN_WATER_PVT in renewables_power_produced:
            try:
                clean_water_pvt_electric_power_produced = renewables_power_produced[
                    RenewableEnergySource.CLEAN_WATER_PVT
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
        if RenewableEnergySource.HOT_WATER_PVT in renewables_power_produced:
            try:
                hot_water_pvt_electric_power_produced = renewables_power_produced[
                    RenewableEnergySource.HOT_WATER_PVT
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
            hot_water_pvt_electric_generation: pd.DataFrame = pd.DataFrame(
                np.asarray(hot_water_pvt_electric_generation_array)
                * np.asarray(pvt_degradation_array)
            )
        else:
            hot_water_pvt_electric_generation = pd.DataFrame(
                [0] * (end_hour - start_hour)
            )

    else:
        clean_water_pvt_electric_generation = pd.DataFrame(
            [0] * (end_hour - start_hour)
        )
        hot_water_pvt_electric_generation = pd.DataFrame([0] * (end_hour - start_hour))

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
    renewables_energy_map: Dict[RenewableEnergySource, pd.DataFrame] = {
        RenewableEnergySource.PV: pv_energy,
        RenewableEnergySource.CLEAN_WATER_PVT: pvt_cw_electric_energy,
        RenewableEnergySource.HOT_WATER_PVT: pvt_hw_electric_energy,
        # RenewableGenerationSource.WIND: wind_energy, etc.
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

        # Then take energy from grid if available
        if scenario.grid:
            grid_energy: pd.DataFrame = pd.DataFrame(
                ((remaining_profile < 0) * remaining_profile).iloc[:, 0]  # type: ignore
                * -1.0
                * grid_profile.values
            )
        else:
            grid_energy = pd.DataFrame([0] * (end_hour - start_hour))
        battery_storage_profile: pd.DataFrame = pd.DataFrame(
            remaining_profile.values + grid_energy.values
        )

    else:
        # Take energy from grid first if available
        if scenario.grid:
            grid_energy = pd.DataFrame(grid_profile.mul(load_energy[0]))  # type: ignore
        else:
            grid_energy = pd.DataFrame([0] * (end_hour - start_hour))
        # as needed for load
        remaining_profile = (grid_energy[0] <= 0).mul(load_energy[0])  # type: ignore
        logger.debug(
            "Remainig profile: %s kWh",
            round(float(np.sum(remaining_profile)), 2),  # type: ignore [arg-type]
        )

        # Then take energy from PV if generated
        logger.debug(
            "Renewables profile: %s kWh",
            f"{round(float(np.sum(renewables_energy)), 2)}",  # type: ignore [arg-type]
        )
        battery_storage_profile = pd.DataFrame(
            renewables_energy[0].values - remaining_profile.values  # type: ignore
        )
        logger.debug(
            "Storage profile: %s kWh",
            f"{round(float(np.sum(battery_storage_profile)), 2)}",  # type: ignore [arg-type]
        )

        renewables_energy_used_directly = pd.DataFrame(
            ((renewables_energy[0] > 0) * (remaining_profile > 0))  # type: ignore [call-overload]
            * pd.concat(  # type: ignore [call-overload]
                [renewables_energy[0], remaining_profile], axis=1  # type: ignore [call-overload]
            ).min(axis=1)
        )

        logger.debug(
            "Grid energy: %s kWh",
            f"{round(float(np.sum(grid_energy)), 2)}",  # type: ignore [arg-type]
        )
        renewables_direct_rounded: float = round(
            float(np.sum(renewables_energy_used_directly)), 2  # type: ignore [arg-type]
        )
        logger.debug(
            "Renewables direct: %s kWh",
            round(float(np.sum(renewables_energy_used_directly)), 2),  # type: ignore [arg-type]
        )
        logger.debug("Renewables direct: %s kWh", renewables_direct_rounded)

    battery_storage_profile.columns = pd.Index([ColumnHeader.STORAGE_PROFILE.value])
    grid_energy.columns = pd.Index([ColumnHeader.GRID_ENERGY.value])
    load_energy.columns = pd.Index([ColumnHeader.LOAD_ENERGY.value])
    renewables_energy.columns = pd.Index(
        [ColumnHeader.RENEWABLE_ELECTRICITY_SUPPLIED.value]
    )
    renewables_energy_map[RenewableEnergySource.PV].columns = pd.Index(
        [ColumnHeader.PV_ELECTRICITY_SUPPLIED.value]
    )
    renewables_energy_map[RenewableEnergySource.CLEAN_WATER_PVT].columns = pd.Index(
        [ColumnHeader.CW_PVT_ELECTRICITY_SUPPLIED.value]
    )
    renewables_energy_map[RenewableEnergySource.HOT_WATER_PVT].columns = pd.Index(
        [ColumnHeader.HW_PVT_ELECTRICITY_SUPPLIED.value]
    )
    renewables_energy_used_directly.columns = pd.Index(
        [ColumnHeader.RENEWABLE_ELECTRICITY_USED_DIRECTLY.value]
    )

    return (
        battery_storage_profile,
        grid_energy,
        kerosene_usage,
        load_energy,
        renewables_energy,
        renewables_energy_map,
        renewables_energy_used_directly,
    )


def get_water_storage_profile(
    processed_total_cw_load: pd.DataFrame,
    renewable_cw_produced: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Gets the storage profile for the clean-water system.

    Inputs:
        - minigrid:
            The minigrid being modelled.
        - processed_total_cw_load:
            The total clean-water load placed on the system.
        - renewable_cw_produced:
            The total clean water produced directly from renewables, i.e., solar-based
            or solar-thermal-based desalination technologies.
        - scenario:
            The scenario being considered.

    Outputs:
        - power_consumed:
            The electric power consumed in providing the water demand.
        - renewable_cw_used_directly:
            The renewable clean water which was directly consumed.
        - tank_storage_profile:
            The amount of water (litres) into (+ve) and out of (-ve) the clean-water
            tanks.

    """

    # Clean water is either produced directly or drawn from the storage tanks.
    remaining_profile = pd.DataFrame(
        renewable_cw_produced.values - processed_total_cw_load.values
    )
    renewable_cw_used_directly: pd.DataFrame = pd.DataFrame(
        (remaining_profile > 0) * processed_total_cw_load.values
        + (remaining_profile < 0) * renewable_cw_produced.values
    )

    tank_storage_profile: pd.DataFrame = pd.DataFrame(remaining_profile.values)

    electric_power_consumed: pd.DataFrame = 0.001 * pd.DataFrame(  # type: ignore
        [0] * processed_total_cw_load.size
    )

    return (
        electric_power_consumed,
        renewable_cw_used_directly,
        tank_storage_profile,
    )
