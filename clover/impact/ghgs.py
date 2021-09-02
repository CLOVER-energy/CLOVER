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

from typing import Any, Dict, List

import numpy as np  # pylint: disable=import-error
import pandas as pd  # pylint: disable=import-error

from .__utils__ import SIZE_INCREMENT, ImpactingComponent, LIFETIME
from ..__utils__ import Location, hourly_profile_to_daily_sum

__all__ = (
    "calculate_connections_ghgs",
    "calculate_diesel_fuel_ghgs",
    "calculate_grid_ghgs",
    "calculate_independent_ghgs",
    "calculate_kerosene_ghgs",
    "calculate_kerosene_ghgs_mitigated",
    "calculate_total_equipment_ghgs",
    "calculate_total_om",
)


# Connection ghgs:
#   Keyword used for denoting connection ghgs.
CONNECTION_GHGS = "connection_ghgs"

# Extension ghgs:
#   Keyword used for denoting extension ghgs.
EXTENSION_GHGS = "extension_ghgs"

# GHGS:
#   Keyword for describing GHG data.
GHGS = "ghgs"

# GHG_DECREASE:
#   Keyword for describing GHG decrease.
GHG_DECREASE = "ghg_decrease"

# Initial GHGs:
#   Keyword for the initial GHGs.
INITIAL_GHGS = "initial_ghgs"

# Infrastructure Ghgs:
#   Keyword used for denoting infrastructure ghgs.
INFRASTRUCTURE_GHGS = "infrastructure_ghgs"

# Final GHGs:
#   Keyword for the final GHGs.
FINAL_GHGS = "final_ghgs"

# OM GHGs:
#   Keyword for the O&M GHGs.
OM_GHGS = "o&m_ghgs"


def calculate_ghgs(
    capacity: float,
    ghg_inputs: Dict[str, Any],
    system_component: ImpactingComponent,
    year=0,
):
    """
    Calculates ghgs of PV

    Inputs:
        - capacity:
            The capacity of the relevant component.
        - ghg_inputs:
            GHG input data.
        - system_component:
            The component of the system currently being considered.
        - year:
            Installation year

    Outputs:
        GHGs

    """

    ghgs = capacity * ghg_inputs[system_component.value][GHGS]
    annual_reduction = 0.01 * ghg_inputs[system_component.value][GHG_DECREASE]
    return ghgs * (1.0 - annual_reduction) ** year


# Installation ghgs
def calculate_installation_ghgs(
    capacity: float,
    ghg_inputs: Dict[str, Any],
    system_component: ImpactingComponent,
    year=0,
) -> float:
    """

    Calculates ghgs of installation
    Inputs:
        - capacity:
            The capacity of the relevant component.
        - ghg_inputs:
            GHG input data.
        - system_component:
            The component of the system currently being considered.
        - year:
            Installation year

    Outputs:
        GHGs

    """

    installation_ghgs = capacity * ghg_inputs[system_component.value][GHGS]
    annual_reduction = 0.01 * ghg_inputs[system_component.value][GHG_DECREASE]

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

    misc_ghgs = capacity * ghg_inputs[ImpactingComponent.MISC.value][GHGS]
    return misc_ghgs


def calculate_total_equipment_ghgs(
    diesel_size: float,
    ghg_inputs: Dict[str, Any],
    pv_array_size: float,
    storage_size: float,
    year=0,
) -> float:
    """
    Calculates ghgs of all newly installed equipment

    Inputs:
        - diesel_size:
            Capacity of diesel generator being installed
        - ghg_inputs:
            GHG input information.
        - pv_array_size:
            Capacity of PV being installed
        - storage_size:
            Capacity of battery storage being installed
        - year:
            Installation year

    Outputs:
        GHGs

    """

    # Calculate system ghgs.
    bos_ghgs = calculate_ghgs(pv_array_size, ghg_inputs, ImpactingComponent.BOS, year)
    diesel_ghgs = calculate_ghgs(
        diesel_size, ghg_inputs, ImpactingComponent.DIESEL, year
    )
    pv_ghgs = calculate_ghgs(pv_array_size, ghg_inputs, ImpactingComponent.PV, year)
    storage_ghgs = calculate_ghgs(
        storage_size, ghg_inputs, ImpactingComponent.STORAGE, year
    )

    # Calculate installation ghgs.
    pv_installation_ghgs = calculate_installation_ghgs(
        pv_array_size, ghg_inputs, ImpactingComponent.PV, year
    )
    diesel_installation_ghgs = calculate_installation_ghgs(
        diesel_size, ghg_inputs, ImpactingComponent.DIESEL, year
    )
    misc_ghgs = calculate_misc_ghgs(diesel_size + pv_array_size, ghg_inputs)

    return (
        bos_ghgs
        + diesel_ghgs
        + pv_ghgs
        + storage_ghgs
        + pv_installation_ghgs
        + diesel_installation_ghgs
        + misc_ghgs
    )


def calculate_connections_ghgs(ghg_inputs: Dict[str, Any], households: pd.Series):
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
    new_connections = np.max(households_data_frame) - np.min(households_data_frame)

    # Calculate the associated ghgs.
    connection_ghgs = ghg_inputs[ImpactingComponent.HOUSEHOLDS.value][CONNECTION_GHGS]
    connections_ghgs = float(connection_ghgs * new_connections)

    return connections_ghgs


def calculate_grid_extension_ghgs(
    ghg_inputs: Dict[str, Any], grid_extension_distance: float
):
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

    return (
        grid_extension_distance
        * ghg_inputs[ImpactingComponent.GRID.value][EXTENSION_GHGS]
        + ghg_inputs[ImpactingComponent.GRID.value][INFRASTRUCTURE_GHGS]
    )


def calculate_independent_ghgs(
    electric_yearly_load_statistics: pd.DataFrame,
    end_year: int,
    ghg_inputs: Dict[str, Any],
    location: Location,
    start_year: int,
):
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
        - start_year:
            Start year of simulation period

    Outputs:
        GHGs

    """

    inverter_ghgs = calculate_inverter_ghgs(
        electric_yearly_load_statistics, end_year, ghg_inputs, location, start_year
    )
    total_ghgs = inverter_ghgs  # ... + other components as required

    return total_ghgs


def calculate_inverter_ghgs(
    electric_yearly_load_statistics: pd.DataFrame,
    end_year: int,
    ghg_inputs: Dict[str, Any],
    location: Location,
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
    replacement_intervals.columns = pd.Index(["Installation year"])

    # Check if inverter should be replaced in the specified time interval
    if replacement_intervals.loc[
        replacement_intervals["Installation year"].isin(
            list(range(start_year, end_year))
        )
    ].empty:
        return float(0.0)

    # Initialise inverter sizing calculation
    max_power = []
    inverter_step = float(ghg_inputs[ImpactingComponent.INVERTER.value][SIZE_INCREMENT])
    inverter_size: List[float] = []
    for i in range(len(replacement_intervals)):
        # Calculate maximum power in interval years
        start = replacement_intervals["Installation year"].iloc[i]
        end = start + replacement_period
        max_power_interval = (
            electric_yearly_load_statistics["Maximum"].iloc[start:end].max()
        )
        max_power.append(max_power_interval)

        # Calculate resulting inverter size
        inverter_size_interval: float = (
            np.ceil(0.001 * max_power_interval / inverter_step) * inverter_step
        )
        inverter_size.append(inverter_size_interval)

    inverter_size_data_frame: pd.DataFrame = pd.DataFrame(inverter_size)
    inverter_size_data_frame.columns = pd.Index(["Inverter size (kW)"])
    inverter_info = pd.concat([replacement_intervals, inverter_size_data_frame], axis=1)

    # Calculate the associated ghgs
    inverter_info["Inverter ghgs (kgCO2/kW)"] = [
        ghg_inputs[ImpactingComponent.INVERTER.value][GHGS]
        * (1 - 0.01 * ghg_inputs[ImpactingComponent.INVERTER.value][GHG_DECREASE])
        ** inverter_info["Installation year"].iloc[i]
        for i in range(len(inverter_info))
    ]
    inverter_info["Total ghgs (kgCO2)"] = [
        inverter_info["Inverter size (kW)"].iloc[i]
        * inverter_info["Inverter ghgs (kgCO2/kW)"].iloc[i]
        for i in range(len(inverter_info))
    ]
    inverter_ghgs = np.sum(
        inverter_info.loc[  # type: ignore
            inverter_info["Installation year"].isin(
                list(np.array(range(start_year, end_year)))
            )
        ]["Total ghgs (kgCO2)"]
    ).round(2)

    return inverter_ghgs


def calculate_kerosene_ghgs(
    ghg_inputs: Dict[str, Any], kerosene_lamps_in_use_hourly: pd.Series
):
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

    return np.sum(kerosene_ghgs)


def calculate_kerosene_ghgs_mitigated(
    ghg_inputs: Dict[str, Any], kerosene_lamps_mitigated_hourly: pd.Series
):
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

    return np.sum(kerosene_ghgs)


def calculate_grid_ghgs(
    ghg_inputs: Dict[str, Any],
    grid_energy_hourly: pd.Series,
    location: Location,
    start_year=0,
    end_year=20,
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
        hourly_profile_to_daily_sum(pd.DataFrame(grid_energy_hourly))
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
    system_component: ImpactingComponent,
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
            The component of the system currently being considered.
        - year:
            Installation year

    Outputs:
        GHGs

    """

    return (
        capacity * ghg_inputs[system_component.value][OM_GHGS] * (end_year - start_year)
    )


#   Total O&M for entire system
def calculate_total_om(
    diesel_size: float,
    ghg_inputs: Dict[str, Any],
    pv_array_size: float,
    storage_size: float,
    start_year: int = 0,
    end_year: int = 20,
):
    """
    Calculates total O&M ghgs over the simulation period

    Inputs:
        - diesel_size:
            Capacity of diesel generator installed
        - ghg_inputs:
            The GHG input information.
        - pv_array_size:
            Capacity of PV installed
        - storage_size:
            Capacity of battery storage installed
        - start_year:
            Start year of simulation period
        - end_year:
            End year of simulation period

    Outputs:
        GHGs

    """

    pv_om_ghgs = calculate_om_ghgs(
        pv_array_size, ghg_inputs, ImpactingComponent.PV, start_year, end_year
    )
    storage_om_ghgs = calculate_om_ghgs(
        storage_size, ghg_inputs, ImpactingComponent.STORAGE, start_year, end_year
    )
    diesel_om_ghgs = calculate_om_ghgs(
        diesel_size, ghg_inputs, ImpactingComponent.PV, start_year, end_year
    )
    general_om_ghgs = calculate_om_ghgs(
        1, ghg_inputs, ImpactingComponent.GENERAL, start_year, end_year
    )

    return pv_om_ghgs + storage_om_ghgs + diesel_om_ghgs + general_om_ghgs
