#!/usr/bin/python3
########################################################################################
# ghgs.py - GHG impact assessment module.                                              #
#                                                                                      #
# Author: Phil Sandwell, Ben Winchester                                                #
# Copyright: Phil Sandwell, 2021                                                       #
# License: Open source                                                                 #
# Most recent update: 24/08/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
ghgs.py - The ghgs module for CLOVER.

When assessing the impact of a system, the ghg impact, i.e., the greenhouse gasses
emitted by the system, need to be assed.

"""

from logging import Logger
from typing import Any, Dict, List, Optional

import numpy as np  # pylint: disable=import-error
import pandas as pd  # pylint: disable=import-error

from ..__utils__ import (
    BColours,
    ColumnHeader,
    hourly_profile_to_daily_sum,
    InputFileError,
    Location,
    Scenario,
)
from .__utils__ import ImpactingComponent, LIFETIME, SIZE_INCREMENT

__all__ = (
    "calculate_connections_ghgs",
    "calculate_diesel_fuel_ghgs",
    "calculate_grid_ghgs",
    "calculate_independent_ghgs",
    "calculate_kerosene_ghgs",
    "calculate_kerosene_ghgs_mitigated",
    "calculate_total_equipment_ghgs",
    "calculate_total_om",
    "EMISSIONS",
)


# Connection ghgs:
#   Keyword used for denoting connection ghgs.
CONNECTION_GHGS = "connection_ghgs"

# Emissions:
#   Keyword used for denoting device-specific ghg information.
EMISSIONS = "emissions"

# Extension ghgs:
#   Keyword used for denoting extension ghgs.
EXTENSION_GHGS = "extension_ghgs"

# GHGS:
#   Keyword for describing GHG data.
GHGS = "ghgs"

# GHG_DECREASE:
#   Keyword for describing GHG decrease.
GHG_DECREASE = "ghg_decrease"

# GHG impact:
#   A base `str` used for specifying unique ghg impacts.
GHG_IMPACT: str = "{type}_{name}"

# Initial GHGs:
#   Keyword for the initial GHGs.
INITIAL_GHGS = "initial_ghgs"

# Infrastructure Ghgs:
#   Keyword used for denoting infrastructure ghgs.
INFRASTRUCTURE_GHGS = "infrastructure_ghgs"

# Installation GHGS:
#   Keyword for describing GHG data.
INSTALLATION_GHGS = "installation_ghgs"

# GHG_DECREASE:
#   Keyword for describing GHG decrease.
INSTALLATION_GHGS_DECREASE = "installation_ghg_decrease"

# Final GHGs:
#   Keyword for the final GHGs.
FINAL_GHGS = "final_ghgs"

# OM GHGs:
#   Keyword for the O&M GHGs.
OM_GHGS = "o&m"


def calculate_ghgs(
    capacity: float,
    ghg_inputs: Dict[str, Any],
    system_component: str,
    year: int = 0,
) -> float:
    """
    Calculates ghgs of PV

    Inputs:
        - capacity:
            The capacity of the relevant component.
        - ghg_inputs:
            GHG input data.
        - system_component:
            The component of the system currently being considered, passed in as a `str`
            representing a component rather than a component.
        - year:
            ColumnHeader.INSTALLATION_YEAR.value

    Outputs:
        GHGs

    """

    ghgs: float = capacity * float(ghg_inputs[system_component][GHGS])
    annual_reduction: float = 0.01 * ghg_inputs[system_component][GHG_DECREASE]
    return ghgs * (1.0 - annual_reduction) ** year


# Installation ghgs
def calculate_installation_ghgs(
    capacity: float,
    ghg_inputs: Dict[str, Any],
    system_component: str,
    year: int = 0,
) -> float:
    """

    Calculates ghgs of installation
    Inputs:
        - capacity:
            The capacity of the relevant component.
        - ghg_inputs:
            GHG input data.
        - system_component:
            The component of the system currently being considered, passed in as a `str`
            representing the component rather than the component.
        - year:
            ColumnHeader.INSTALLATION_YEAR.value

    Outputs:
        GHGs

    """

    installation_ghgs: float = (
        capacity * ghg_inputs[system_component][INSTALLATION_GHGS]
    )
    annual_reduction: float = (
        0.01 * ghg_inputs[system_component][INSTALLATION_GHGS_DECREASE]
    )

    return installation_ghgs * (1.0 - annual_reduction) ** year


#   Miscellaneous ghgs
def calculate_misc_ghgs(capacity: float, ghg_inputs: Dict[str, Any]) -> float:
    """
    Calculates ghgs of miscellaneous capacity-related equipment

    Inputs:
        - capacity:
            The capacity of the relevant component.
        - ghg_inputs:
            GHG input data.

    Outputs:
        Misc. ghgs

    """

    misc_ghgs: float = capacity * ghg_inputs[ImpactingComponent.MISC.value][GHGS]
    return misc_ghgs


def calculate_total_equipment_ghgs(  # pylint: disable=too-many-locals
    buffer_tanks: int,
    clean_water_tanks: int,
    converters: Dict[str, int],
    diesel_size: float,
    ghg_inputs: Dict[str, Any],
    heat_exchangers: int,
    hot_water_tanks: int,
    logger: Logger,
    pv_array_size: float,
    pvt_array_size: float,
    storage_size: float,
    year: int = 0,
) -> float:
    """
    Calculates ghgs of all newly installed equipment

    Inputs:
        - buffer_tanks:
            Number of buffer tanks being installed.
        - clean_water_tanks:
            Capacity of clean-water tanks being installed.
        - converters:
            A mapping between converter names and the size of each that was added to the
            system this iteration.
        - diesel_size:
            Capacity of diesel generator being installed
        - ghg_inputs:
            GHG input information.
        - heat_exchangers:
            Number of heat exchangers being installed.
        - hot_water_tanks:
            Capactiy of hot-water tanks being installed.
        - pv_array_size:
            Capacity of PV being installed.
        - pvt_array_size:
            Capacity of PV-T being installed.
        - storage_size:
            Capacity of battery storage being installed.
        - year:
            ColumnHeader.INSTALLATION_YEAR.value.

    Outputs:
        GHGs

    """

    # Calculate system ghgs.
    bos_ghgs = calculate_ghgs(
        pv_array_size, ghg_inputs, ImpactingComponent.BOS.value, year
    )

    if ImpactingComponent.BUFFER_TANK.value not in ghg_inputs and buffer_tanks > 0:
        logger.error(
            "%sNo buffer-tank GHG input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "tank inputs",
            "No buffer tank ghg input information provided and a non-zero number of "
            "buffer tanks are being considered.",
        )
    buffer_tank_ghgs: float = 0
    buffer_tank_installation_ghgs: float = 0
    if buffer_tanks > 0:
        buffer_tank_ghgs = calculate_ghgs(
            buffer_tanks,
            ghg_inputs,
            ImpactingComponent.BUFFER_TANK.value,
            year,
        )
        buffer_tank_installation_ghgs = calculate_installation_ghgs(
            buffer_tanks, ghg_inputs, ImpactingComponent.BUFFER_TANK.value, year
        )

    if (
        ImpactingComponent.CLEAN_WATER_TANK.value not in ghg_inputs
        and clean_water_tanks > 0
    ):
        logger.error(
            "%sNo clean-water tank GHG input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "tank inputs",
            "No clean-water tank ghg input information provided and a non-zero number "
            "of clean-water tanks are being considered.",
        )
    clean_water_tank_ghgs: float = 0
    clean_water_tank_installation_ghgs: float = 0
    if clean_water_tanks > 0:
        clean_water_tank_ghgs = calculate_ghgs(
            clean_water_tanks,
            ghg_inputs,
            ImpactingComponent.CLEAN_WATER_TANK.value,
            year,
        )
        clean_water_tank_installation_ghgs = calculate_installation_ghgs(
            clean_water_tanks,
            ghg_inputs,
            ImpactingComponent.CLEAN_WATER_TANK.value,
            year,
        )

    converter_ghgs = sum(
        calculate_ghgs(
            size,
            ghg_inputs,
            GHG_IMPACT.format(type=ImpactingComponent.CONVERTER.value, name=converter),
            year,
        )
        for converter, size in converters.items()
    )
    converter_installation_ghgs = sum(
        calculate_installation_ghgs(
            size,
            ghg_inputs,
            GHG_IMPACT.format(type=ImpactingComponent.CONVERTER.value, name=converter),
            year,
        )
        for converter, size in converters.items()
    )

    diesel_ghgs = calculate_ghgs(
        diesel_size, ghg_inputs, ImpactingComponent.DIESEL.value, year
    )
    diesel_installation_ghgs = calculate_installation_ghgs(
        diesel_size, ghg_inputs, ImpactingComponent.DIESEL.value, year
    )

    if (
        ImpactingComponent.HEAT_EXCHANGER.value not in ghg_inputs
        and heat_exchangers > 0
    ):
        logger.error(
            "%sNo heat-exchanger tank GHG input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "heat exchanger inputs",
            "No heat-exchanger ghg input information provided and a non-zero number of "
            "heat exchangers are being considered.",
        )
    heat_exchanger_ghgs: float = 0
    heat_exchanger_installation_ghgs: float = 0
    if heat_exchangers > 0:
        heat_exchanger_ghgs = calculate_ghgs(
            heat_exchangers,
            ghg_inputs,
            ImpactingComponent.HEAT_EXCHANGER.value,
            year,
        )
        heat_exchanger_installation_ghgs = calculate_installation_ghgs(
            heat_exchangers, ghg_inputs, ImpactingComponent.HEAT_EXCHANGER.value, year
        )

    if (
        ImpactingComponent.HOT_WATER_TANK.value not in ghg_inputs
        and hot_water_tanks > 0
    ):
        logger.error(
            "%sNo hot-water tank GHG input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "tank inputs",
            "No hot-water tank ghg input information provided and a non-zero number of "
            "hot-water tanks are being considered.",
        )
    hot_water_tank_ghgs: float = 0
    hot_water_tank_installation_ghgs: float = 0
    if hot_water_tanks > 0:
        hot_water_tank_ghgs = calculate_ghgs(
            hot_water_tanks,
            ghg_inputs,
            ImpactingComponent.HOT_WATER_TANK.value,
            year,
        )
        hot_water_tank_installation_ghgs = calculate_installation_ghgs(
            hot_water_tanks, ghg_inputs, ImpactingComponent.HOT_WATER_TANK.value, year
        )

    pv_ghgs = calculate_ghgs(
        pv_array_size, ghg_inputs, ImpactingComponent.PV.value, year
    )
    pv_installation_ghgs = calculate_installation_ghgs(
        pv_array_size, ghg_inputs, ImpactingComponent.PV.value, year
    )

    if ImpactingComponent.PV_T.value not in ghg_inputs and pvt_array_size > 0:
        logger.error(
            "%sNo PV-T GHG input information provided.%s", BColours.fail, BColours.endc
        )
        raise InputFileError(
            "solar generation inputs",
            "No PV-T ghg input information provided and a non-zero number of PV-T"
            "panels are being considered.",
        )
    pvt_ghgs: float = 0
    pvt_installation_ghgs: float = 0
    if pvt_array_size > 0:
        pvt_ghgs = calculate_ghgs(
            pvt_array_size,
            ghg_inputs,
            ImpactingComponent.PV_T.value,
            year,
        )
        pvt_installation_ghgs = calculate_installation_ghgs(
            pvt_array_size, ghg_inputs, ImpactingComponent.PV.value, year
        )

    storage_ghgs = calculate_ghgs(
        storage_size, ghg_inputs, ImpactingComponent.STORAGE.value, year
    )

    # Calculate misc GHGs.
    misc_ghgs = calculate_misc_ghgs(diesel_size + pv_array_size, ghg_inputs)

    return (
        bos_ghgs
        + buffer_tank_ghgs
        + buffer_tank_installation_ghgs
        + clean_water_tank_installation_ghgs
        + clean_water_tank_ghgs
        + converter_ghgs
        + converter_installation_ghgs
        + diesel_installation_ghgs
        + diesel_ghgs
        + heat_exchanger_ghgs
        + heat_exchanger_installation_ghgs
        + hot_water_tank_ghgs
        + hot_water_tank_installation_ghgs
        + misc_ghgs
        + pv_ghgs
        + pv_installation_ghgs
        + pvt_ghgs
        + pvt_installation_ghgs
        + storage_ghgs
    )


def calculate_connections_ghgs(
    ghg_inputs: Dict[str, Any], households: pd.Series
) -> float:
    """
    Calculates ghgs of connecting households to the system

    Inputs:
        - ghg_inputs:
            GHG input information.
        - households:
            DataFrame of households from Energy_System().simulation(...)

    Outputs:
        GHGs

    """

    # Ensure that the correct type is being used.
    households_data_frame: pd.DataFrame = pd.DataFrame(households)

    # Compute the number of new households that were added to the system.
    new_connections: float = np.max(households_data_frame) - np.min(
        households_data_frame
    )

    # Calculate the associated ghgs.
    connection_ghgs: float = ghg_inputs[ImpactingComponent.HOUSEHOLDS.value][
        CONNECTION_GHGS
    ]
    connections_ghgs = float(connection_ghgs * new_connections)

    return connections_ghgs


def calculate_grid_extension_ghgs(
    ghg_inputs: Dict[str, Any], grid_extension_distance: float
) -> float:
    """
    Calculates ghgs of extending the grid network to a community

    Inputs:
        - ghg_inputs:
            GHG input information.
        - grid_extension_distance:
            Distance to the existing grid network

    Outputs:
        GHGs

    """

    return grid_extension_distance * float(
        ghg_inputs[ImpactingComponent.GRID.value][EXTENSION_GHGS]
    ) + float(ghg_inputs[ImpactingComponent.GRID.value][INFRASTRUCTURE_GHGS])


def _calculate_inverter_ghgs(  # pylint: disable=too-many-locals
    electric_yearly_load_statistics: pd.DataFrame,
    end_year: int,
    ghg_inputs: Dict[str, Any],
    location: Location,
    logger: Logger,
    scenario: Scenario,
    start_year: int,
) -> float:
    """
    Calculates ghgs of inverters based on load calculations

    Inputs:
        - electric_yearly_load_statistics:
            The yearly load statistics for the electric load.
        - end_year:
            End year of simulation period
        - ghg_inputs:
            GHG input information.
        - location:
            The location being considered.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenario:
            The :class:`Scenario` currently being considered.
        - start_year:
            Start year of simulation period

    Outputs:
        GHGs

    """

    # Calcualte inverter replacement periods
    replacement_period = int(ghg_inputs[ImpactingComponent.INVERTER.value][LIFETIME])
    replacement_intervals = pd.DataFrame(
        np.arange(0, location.max_years, replacement_period)
    )
    replacement_intervals.columns = pd.Index([ColumnHeader.INSTALLATION_YEAR.value])

    # Check if inverter should be replaced in the specified time interval
    if not any(
        replacement_intervals[ColumnHeader.INSTALLATION_YEAR.value].isin(
            list(np.array(range(start_year, end_year)))
        )
    ):
        return float(0.0)

    # Initialise inverter sizing calculation
    max_power = []
    inverter_step = float(ghg_inputs[ImpactingComponent.INVERTER.value][SIZE_INCREMENT])
    inverter_size: List[float] = []
    for i in range(len(replacement_intervals)):
        # Calculate maximum power in interval years
        start = replacement_intervals[ColumnHeader.INSTALLATION_YEAR.value].iloc[i]
        end = start + replacement_period
        max_power_interval = (
            electric_yearly_load_statistics[ColumnHeader.MAXIMUM.value]
            .iloc[start:end]
            .max()
        )
        max_power.append(max_power_interval)

        # Calculate resulting inverter size
        inverter_size_interval: float = (
            np.ceil(0.001 * max_power_interval / inverter_step) * inverter_step
        )
        inverter_size.append(inverter_size_interval)

    inverter_size_data_frame: pd.DataFrame = pd.DataFrame(inverter_size)
    inverter_size_data_frame.columns = pd.Index([ColumnHeader.INVERTER_SIZE.value])
    inverter_info = pd.concat([replacement_intervals, inverter_size_data_frame], axis=1)

    # Calculate the associated ghgs
    inverter_info["Inverter ghgs (kgCO2/kW)"] = [
        ghg_inputs[ImpactingComponent.INVERTER.value][GHGS]
        * (1 - 0.01 * ghg_inputs[ImpactingComponent.INVERTER.value][GHG_DECREASE])
        ** inverter_info[ColumnHeader.INSTALLATION_YEAR.value].iloc[i]
        for i in range(len(inverter_info))
    ]

    # If a static inverter size has been used, use this, otherwise, use the dynamically
    # calculated values.
    if scenario.fixed_inverter_size and any(
        inverter_info[ColumnHeader.INVERTER_SIZE.value] > scenario.fixed_inverter_size
    ):
        logger.info(
            "The static inverter size specified, %s, was below that calculated "
            "within CLOVER. Calculated inverter sizes:\n%s",
            scenario.fixed_inverter_size,
            "\n".join(
                [
                    f"Size for year {year}: {size} kW"
                    for year, size in zip(
                        replacement_intervals[ColumnHeader.INSTALLATION_YEAR.value],
                        inverter_info[ColumnHeader.INVERTER_SIZE.value],
                    )
                ]
            ),
        )

    inverter_info[ColumnHeader.TOTAL_GHGS.value] = [
        (
            inverter_info[ColumnHeader.INVERTER_SIZE.value].iloc[i]
            if not scenario.fixed_inverter_size
            else scenario.fixed_inverter_size
        )
        * inverter_info["Inverter ghgs (kgCO2/kW)"].iloc[i]
        for i in range(len(inverter_info))
    ]
    inverter_ghgs: float = np.sum(
        inverter_info.iloc[
            inverter_info.index[
                inverter_info[ColumnHeader.INSTALLATION_YEAR.value].isin(
                    list(np.array(range(start_year, end_year)))
                )
            ]
        ][ColumnHeader.TOTAL_GHGS.value]
    ).round(2)

    return inverter_ghgs


def calculate_independent_ghgs(
    electric_yearly_load_statistics: pd.DataFrame,
    end_year: int,
    ghg_inputs: Dict[str, Any],
    location: Location,
    logger: Logger,
    scenario: Scenario,
    start_year: int,
) -> float:
    """
    Calculates ghgs of equipment which is independent of simulation periods

    Inputs:
        - electric_yearly_load_statistics:
            The electric yearly load statistics for the simulation period.
        - end_year:
            End year of simulation period
        - ghg_inputs:
            The GHG input informaiton.
        - location:
            The location being considered.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenario:
            The :class:`Scenario` currently being considered.
        - start_year:
            Start year of simulation period

    Outputs:
        GHGs

    """

    inverter_ghgs = _calculate_inverter_ghgs(
        electric_yearly_load_statistics,
        end_year,
        ghg_inputs,
        location,
        logger,
        scenario,
        start_year,
    )
    total_ghgs = inverter_ghgs  # ... + other components as required

    return total_ghgs


def calculate_kerosene_ghgs(
    ghg_inputs: Dict[str, Any], kerosene_lamps_in_use_hourly: pd.Series
) -> float:
    """
    Calculates ghgs of kerosene usage.

    Inputs:
        - kerosene_lamps_in_use_hourly:
            Output from Energy_System().simulation(...)

    Outputs:
        GHGs

    """

    kerosene_ghgs = (
        kerosene_lamps_in_use_hourly
        * ghg_inputs[ImpactingComponent.KEROSENE.value][GHGS]
    )

    return float(np.sum(kerosene_ghgs))


def calculate_kerosene_ghgs_mitigated(
    ghg_inputs: Dict[str, Any], kerosene_lamps_mitigated_hourly: pd.Series
) -> float:
    """
    Calculates ghgs of kerosene usage that has been avoided by using the system.

    Inputs:
        - kerosene_lamps_mitigated_hourly:
            Output from Energy_System().simulation(...)

    Outputs:
        GHGs

    """

    kerosene_ghgs = (
        kerosene_lamps_mitigated_hourly
        * ghg_inputs[ImpactingComponent.KEROSENE.value][GHGS]
    )

    return float(np.sum(kerosene_ghgs))


def calculate_grid_ghgs(
    ghg_inputs: Dict[str, Any],
    grid_energy_hourly: pd.Series,
    location: Location,
    start_year: int = 0,
    end_year: int = 20,
) -> float:
    """
    Calculates ghgs of grid electricity used by the system

    Inputs:
        - ghg_inputs:
            The GHG inputs.
        - grid_energy_hourly:
            Output from Energy_System().simulation(...)
        - location:
            The location currently being considered.
        - start_year:
            Start year of simulation period
        - end_year:
            End year of simulation period

    Outputs:
        GHGs

    """
    # Initialise
    grid_ghgs_initial = ghg_inputs[ImpactingComponent.GRID.value][INITIAL_GHGS]
    grid_ghgs_final = ghg_inputs[ImpactingComponent.GRID.value][FINAL_GHGS]
    days = int(365 * (end_year - start_year))
    total_daily_energy = pd.DataFrame(
        hourly_profile_to_daily_sum(pd.DataFrame(grid_energy_hourly.dropna()))  # type: ignore
    )

    # Account for reduction in grid GHG intensity
    yearly_decrease = (grid_ghgs_initial - grid_ghgs_final) / location.max_years

    # Compute the daily decrease:
    #   daily_decrease = yearly_decrease / days
    grid_ghgs_start = grid_ghgs_initial - start_year * yearly_decrease
    grid_ghgs_end = grid_ghgs_initial - end_year * yearly_decrease
    daily_emissions_intensity = pd.DataFrame(
        np.linspace(grid_ghgs_start, grid_ghgs_end, days)
    )

    # Calculate daily emissions
    daily_emissions = pd.DataFrame(
        total_daily_energy.values * daily_emissions_intensity.values
    )

    return float(np.sum(daily_emissions, axis=0))  # type: ignore


def calculate_diesel_fuel_ghgs(
    diesel_fuel_usage_hourly: pd.Series, ghg_inputs: Dict[str, Any]
) -> float:
    """
    Calculates ghgs of diesel fuel used by the system

    Inputs:
        - diesel_fuel_usage_hourly:
            Output from Energy_System().simulation(...)
        - ghg_inputs:
            GHG input information.

    Outputs:
        GHGs

    """

    diesel_fuel_ghgs = ghg_inputs[ImpactingComponent.DIESEL_FUEL.value][GHGS]
    return float(np.sum(diesel_fuel_usage_hourly) * diesel_fuel_ghgs)  # type: ignore


def calculate_om_ghgs(
    capacity: float,
    ghg_inputs: Dict[str, Any],
    system_component: str,
    start_year: int = 0,
    end_year: int = 20,
) -> float:
    """
    Calculates the O&M GHGs of a component.

    Inputs:
        - capacity:
            The capacity of the relevant component.
        - ghg_inputs:
            GHG input data.
        - system_component:
            The component of the system currently being considered, as a `str`
            representing the component rather than the component.
        - start_year:
            The start year for the simulation.
        - end_year:
            The end year for the simulation.

    Outputs:
        GHGs

    """

    return (
        capacity
        * float(ghg_inputs[system_component][OM_GHGS])
        * (end_year - start_year)
    )


#   Total O&M for entire system
def calculate_total_om(  # pylint: disable=too-many-locals
    buffer_tanks: int,
    clean_water_tanks: int,
    converters: Optional[Dict[str, int]],
    diesel_size: float,
    ghg_inputs: Dict[str, Any],
    heat_exchangers: int,
    hot_water_tanks: int,
    logger: Logger,
    pv_array_size: float,
    pvt_array_size: float,
    storage_size: float,
    start_year: int = 0,
    end_year: int = 20,
) -> float:
    """
    Calculates total O&M ghgs over the simulation period

    Inputs:
        - buffer_tanks:
            Capacity of buffer tanks installed.
        - clean_water_tanks:
            Capacity of clean-water tanks installed.
        - converters:
            A mapping between converter names and the size of each that was added to the
            system this iteration.
        - diesel_size:
            Capacity of diesel generator installed.
        - ghg_inputs:
            The GHG input information.
        - heat_exchangers:
            Capacity of heat exchangers installed.
        - hot_water_tanks:
            Capacity of hot-water tanks installed.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - pv_array_size:
            Capacity of PV installed.
        - pvt_array_size:
            Capacity of PV-T installed.
        - storage_size:
            Capacity of battery storage installed.
        - start_year:
            Start year of simulation period.
        - end_year:
            End year of simulation period.

    Outputs:
        GHGs

    """

    if ImpactingComponent.BUFFER_TANK.value not in ghg_inputs and buffer_tanks > 0:
        logger.error(
            "%sNo buffer tank GHG input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "tank inputs",
            "No buffer tank ghg input information provided and a non-zero number of "
            "buffer tanks are being considered.",
        )
    buffer_tank_om_ghgs: float = 0
    if buffer_tanks > 0:
        buffer_tank_om_ghgs = calculate_om_ghgs(
            buffer_tanks,
            ghg_inputs,
            ImpactingComponent.BUFFER_TANK.value,
            start_year,
            end_year,
        )

    if (
        ImpactingComponent.CLEAN_WATER_TANK.value not in ghg_inputs
        and clean_water_tanks > 0
    ):
        logger.error(
            "%sNo clean-water tank GHG input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "tank inputs",
            "No clean-water tank ghg input information provided and a non-zero number "
            "of clean-water tanks are being considered.",
        )
    clean_water_tank_om_ghgs: float = 0
    if clean_water_tanks > 0:
        clean_water_tank_om_ghgs = calculate_om_ghgs(
            clean_water_tanks,
            ghg_inputs,
            ImpactingComponent.CLEAN_WATER_TANK.value,
            start_year,
            end_year,
        )

    converter_om_ghgs: float = 0
    if converters is not None:
        converter_om_ghgs = sum(
            calculate_om_ghgs(
                size,
                ghg_inputs,
                GHG_IMPACT.format(
                    type=ImpactingComponent.CONVERTER.value, name=converter
                ),
                start_year,
                end_year,
            )
            for converter, size in converters.items()
        )
    else:
        logger.debug("No converters installed so no converter OM GHGs to calcualte.")

    diesel_om_ghgs = calculate_om_ghgs(
        diesel_size, ghg_inputs, ImpactingComponent.PV.value, start_year, end_year
    )

    general_om_ghgs = calculate_om_ghgs(
        1, ghg_inputs, ImpactingComponent.GENERAL.value, start_year, end_year
    )

    if (
        ImpactingComponent.HEAT_EXCHANGER.value not in ghg_inputs
        and heat_exchangers > 0
    ):
        logger.error(
            "%sNo heat-exchanger GHG input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "heat exchanger inputs",
            "No heat-exchanger ghg input information provided and a non-zero number of "
            "heat exchangers are being considered.",
        )
    heat_exchanger_om_ghgs: float = 0
    if heat_exchangers > 0:
        heat_exchanger_om_ghgs = calculate_om_ghgs(
            heat_exchangers,
            ghg_inputs,
            ImpactingComponent.HEAT_EXCHANGER.value,
            start_year,
            end_year,
        )

    if (
        ImpactingComponent.HOT_WATER_TANK.value not in ghg_inputs
        and hot_water_tanks > 0
    ):
        logger.error(
            "%sNo hot-water tank GHG input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "tank inputs",
            "No hot-water tank ghg input information provided and a non-zero number of "
            "hot-water tanks are being considered.",
        )
    hot_water_tank_om_ghgs: float = 0
    if hot_water_tanks > 0:
        hot_water_tank_om_ghgs = calculate_om_ghgs(
            hot_water_tanks,
            ghg_inputs,
            ImpactingComponent.HOT_WATER_TANK.value,
            start_year,
            end_year,
        )

    pv_om_ghgs = calculate_om_ghgs(
        pv_array_size, ghg_inputs, ImpactingComponent.PV.value, start_year, end_year
    )

    if ImpactingComponent.PV_T.value not in ghg_inputs and pvt_array_size > 0:
        logger.error(
            "%sNo PV-T GHG input information provided.%s", BColours.fail, BColours.endc
        )
        raise InputFileError(
            "solar generation inputs",
            "No PV-T ghg input information provided and a non-zero number of PV-T"
            "panels are being considered.",
        )
    pvt_om_ghgs: float = 0
    if pvt_array_size > 0:
        pvt_om_ghgs = calculate_om_ghgs(
            pvt_array_size,
            ghg_inputs,
            ImpactingComponent.PV_T.value,
            start_year,
            end_year,
        )
    storage_om_ghgs = calculate_om_ghgs(
        storage_size, ghg_inputs, ImpactingComponent.STORAGE.value, start_year, end_year
    )

    return (
        buffer_tank_om_ghgs
        + clean_water_tank_om_ghgs
        + converter_om_ghgs
        + diesel_om_ghgs
        + general_om_ghgs
        + heat_exchanger_om_ghgs
        + hot_water_tank_om_ghgs
        + pv_om_ghgs
        + pvt_om_ghgs
        + storage_om_ghgs
    )
