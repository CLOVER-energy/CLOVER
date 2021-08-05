#!/usr/bin/python3
########################################################################################
# finance.py - Financial impact assessment module.                                     #
#                                                                                      #
# Author: Phil Sandwell, Ben Winchester                                                #
# Copyright: Phil Sandwell, 2021                                                       #
# License: Open source                                                                 #
# Most recent update: 05/08/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
finance.py - The finance module for CLOVER.

When assessing the impact of a system, the financial impact, i.e., the costs, need to be
considered. This module assesses the costs of a system based on the financial
information and system-sizing information provided.

"""

import enum
import os

from logging import Logger
from typing import Any, Dict

import numpy as np
import pandas as pd

from ..__utils__ import (
    BColours,
    Location,
)

__all_ = (
    "connections_expenditure",
    "discounted_total",
    "discounted_equipment_cost",
    "get_total_equipment_cost",
    "independent_expenditure",
    "total_om",
)

# Connection cost:
#   Keyword used to denote the connection cost for a household within the community.
CONNECTION_COST = "connection_cost"

# Cost:
#   Keyword used to denote the cost of a component.
COST: str = "cost"

# Cost decrease:
#   Keyword used to denote the cost decrease of a component.
COST_DECREASE: str = "cost_decrease"

# Discount rate:
#   Keyword used to denote the discount rate.
DISCOUNT_RATE = "discount_rate"

# General OM:
#   Keyword used to denote general O&M costs of the system.
GENERAL_OM = "general_o&m"

# Households:
#   Keyword used to denote households within the community.
HOUSEHOLDS = "households"

# Installation cost:
#   Keyword used to denote the installation cost of a component.
INSTALLATION_COST: str = "cost"

# Installation cost decrease:
#   Keyword used to denote the installation cost decrease of a component.
INSTALLATION_COST_DECREASE: str = "cost_decrease"

# Lifetime:
#   Keyword to denote the lifetime of a component.
LIFETIME = "lifetime"

# OM:
#   Keyword used to denote O&M costs.
OM = "o&m"

# Size increment:
#   Keyword to denote increments in the size of a component.
SIZE_INCREMENT = "size_increment"


class ImpactingComponent(enum.Enum):
    """
    Used to keep tracek of components within the systems that have associated impacts.

    - BOS:
        Denotes the balance-of-systems aspect of the system.
    - DIESEL:
        Denotes the diesel component of the system.
    - INVERTER:
        Denotes the inverter component of the system.
    - MISC:
        Denotes misc. costs.
    - PV:
        Denotes the PV component of the system.
    - STORAGE:
        Denotes the storage component of the system.

    """

    BOS = "bos"
    DIESEL = "diesel"
    INVERTER = "inverter"
    MISC = "misc_costs"
    PV = "pv"
    STORAGE = "storage"


####################
# Helper functions #
####################


def _component_cost(
    component_cost: float,
    component_cost_decrease: float,
    component_size: float,
    installation_year=0,
) -> float:
    """
    Computes and returns the cost the system componenet based on the parameters.

    The various system component costs are comnputed using the following formula:
        size * cost * (1 - 0.01 * cost_decrease) ** installation_year

    Inputs:
        - component_cost:
            The cost of the component being considered.
        - component_cost_decrease:
            The cost decrease of the component being considered.
        - component_size:
            The size of the component within the minigrid system.
        - installation_year:
            The year that the component was installed.

    Outputs:
        - The undiscounted cost of the component.

    """

    system_wide_cost = component_cost * component_size
    annual_reduction = 0.01 * component_cost_decrease
    return system_wide_cost * (1 - annual_reduction) ** installation_year


def _component_installation_cost(
    component_size: float,
    installation_cost: float,
    installation_cost_decrease: float,
    installation_year: int = 0,
) -> float:
    """
    Calculates cost of system installation.

    The formula used is:
        installation_cost = (
            component_size * installation_cost * (
                1 - 0.01 * installation_cost_decrease
            ) ** installation_year
        )

    Inputs:
        - component_size:
            The size of the component within the minigrid system.
        - installation_cost:
            The cost of the installation.
        - installation_cost_decrease:
            The decrease in the cost of the installation.
        - installation_year:
            The installation year.

    Outputs:
        The undiscounted installation cost.

    """

    total_component_installation_cost = component_size * installation_cost
    annual_reduction = 0.01 * installation_cost_decrease

    return (
        total_component_installation_cost
        * (1.0 - annual_reduction) ** installation_year
    )


def _component_om(
    component_om_cost: float,
    component_size: float,
    finance_inputs: Dict[str, Any],
    logger: Logger,
    *,
    start_year: int,
    end_year: int
) -> float:
    """
    Computes the O&M cost of a component.

    """

    om_cost_daily = (component_size * component_om_cost) / 365
    total_daily_cost = pd.DataFrame([om_cost_daily] * (end_year - start_year) * 265)

    return discounted_total(
        finance_inputs,
        logger,
        total_daily_cost,
        start_year=start_year,
        end_year=end_year,
    )


def _daily_discount_rate(discount_rate: float) -> float:
    """
    Calculates equivalent discount rate at a daily resolution

    Inputs:
        - discount_rate:
            The discount rate.

    Outputs:
        - The daily discount rate.

    """

    return ((1.0 + discount_rate) ** (1.0 / 365.0)) - 1.0


def _discounted_fraction(
    discount_rate: float, *, start_year: int = 0, end_year: int = 20
) -> pd.DataFrame:
    """
    Calculates the discounted fraction at a daily resolution

    Inputs:
        - discount_rate:
            The discount rate.
        - start_year:
            Start year of simulation period
        - end_year:
            End year of simulation period

    Outputs:
        Discounted fraction for each day of the simulation as a
        :class:`pandas.DataFrame` instance.

    """

    # Intialise various variables.
    start_day = int(start_year * 365)
    end_day = int(end_year * 365)

    # Convert the discount rate into the denominator.
    r_d = _daily_discount_rate(discount_rate)
    denominator = 1.0 + r_d

    # Compute a list containing all the discounted fractions over the time period.
    discounted_fraction_array = [
        denominator ** -time for time in range(start_day, end_day)
    ]

    return pd.DataFrame(discounted_fraction_array)


def _inverter_expenditure(
    finance_inputs: Dict[str, Any],
    location: Location,
    yearly_load_statistics: pd.DataFrame,
    *,
    start_year: int,
    end_year: int
) -> float:
    """
    Calculates cost of inverters based on load calculations

    Inputs:
        - finance_inputs:
            The finance-input information for the system.
        - location:
            The location being considered.
        - yearly_load_statistics:
            The yearly-load statistics for the system.
        - start_year:
            Start year of simulation period
        - end_year:
            End year of simulation period

    Outputs:
        Discounted cost

    """

    # Initialise inverter replacement periods
    replacement_period = finance_inputs[ImpactingComponent.INVERTER][LIFETIME]
    replacement_intervals = pd.DataFrame(
        np.arange(0, location.max_years, replacement_period)
    )
    replacement_intervals.columns = ["Installation year"]

    # Check if inverter should be replaced in the specified time interval
    if replacement_intervals.loc[
        replacement_intervals["Installation year"].isin(range(start_year, end_year))
    ].empty:
        inverter_discounted_cost = float(0.0)
        return inverter_discounted_cost

    # Initialise inverter sizing calculation
    max_power = []
    inverter_step = finance_inputs[ImpactingComponent.INVERTER][SIZE_INCREMENT]
    inverter_size = []
    for i in range(len(replacement_intervals)):
        # Calculate maximum power in interval years
        start = replacement_intervals["Installation year"].iloc[i]
        end = start + replacement_period
        max_power_interval = yearly_load_statistics["Maximum"].iloc[start:end].max()
        max_power.append(max_power_interval)
        # Calculate resulting inverter size
        inverter_size_interval = (
            np.ceil(0.001 * max_power_interval / inverter_step) * inverter_step
        )
        inverter_size.append(inverter_size_interval)
    inverter_size = pd.DataFrame(inverter_size)
    inverter_size.columns = ["Inverter size (kW)"]
    inverter_info = pd.concat([replacement_intervals, inverter_size], axis=1)
    # Calculate
    inverter_info["Discount rate"] = [
        (1 - finance_inputs[DISCOUNT_RATE])
        ** inverter_info["Installation year"].iloc[i]
        for i in range(len(inverter_info))
    ]
    inverter_info["Inverter cost ($/kW)"] = [
        finance_inputs[ImpactingComponent.INVERTER][COST]
        * (1 - 0.01 * finance_inputs[ImpactingComponent.INVERTER][COST_DECREASE])
        ** inverter_info["Installation year"].iloc[i]
        for i in range(len(inverter_info))
    ]
    inverter_info["Discounted expenditure ($)"] = [
        inverter_info["Discount rate"].iloc[i]
        * inverter_info["Inverter size (kW)"].iloc[i]
        * inverter_info["Inverter cost ($/kW)"].iloc[i]
        for i in range(len(inverter_info))
    ]
    inverter_discounted_cost = np.sum(
        inverter_info.loc[
            inverter_info["Installation year"].isin(
                np.array(range(start_year, end_year))
            )
        ]["Discounted expenditure ($)"]
    ).round(2)
    return inverter_discounted_cost


def _misc_costs(diesel_size: float, misc_costs: float, pv_array_size: float) -> float:
    """
    Calculates cost of miscellaneous capacity-related costs

    Inputs:
        - diesel_size:
            Capacity of diesel generator being installed
        - misc_costs:
            The misc. costs of the system.
        - pv_array_size:
            Capacity of PV being installed

    Outputs:
        The undiscounted cost.

    """
    misc_costs = (pv_array_size + diesel_size) * misc_costs
    return misc_costs


###############################
# Externally facing functions #
###############################


def get_total_equipment_cost(
    diesel_size: float,
    finance_inputs: Dict[str, Any],
    pv_array_size: float,
    storage_size: float,
    installation_year: int = 0,
) -> float:
    """
    Calculates all equipment costs.

    Inputs:
        - diesel_size:
            Capacity of diesel generator being installed
        - finance_inputs:
            The finance-input information, parsed from the finance-inputs file.
        - pv_array_size:
            Capacity of PV being installed
        - storage_size:
            Capacity of battery storage being installed
        - installation_year:
            Installation year

    Outputs:
        The combined undiscounted cost of the system equipment.
    """

    # Calculate the various system costs.
    bos_cost = _component_cost(
        finance_inputs[ImpactingComponent.BOS][COST],
        finance_inputs[ImpactingComponent.BOS][COST_DECREASE],
        pv_array_size,
        installation_year,
    )
    diesel_cost = _component_cost(
        finance_inputs[ImpactingComponent.DIESEL][COST],
        finance_inputs[ImpactingComponent.DIESEL][COST_DECREASE],
        diesel_size,
        installation_year,
    )
    pv_cost = _component_cost(
        finance_inputs[ImpactingComponent.PV][COST],
        finance_inputs[ImpactingComponent.PV][COST_DECREASE],
        pv_array_size,
        installation_year,
    )
    storage_cost = _component_cost(
        finance_inputs[ImpactingComponent.STORAGE][COST],
        finance_inputs[ImpactingComponent.STORAGE][COST_DECREASE],
        storage_size,
        installation_year,
    )

    # Calculate the installation costs.
    diesel_installation_cost = _component_installation_cost(
        pv_array_size,
        finance_inputs[ImpactingComponent.DIESEL][INSTALLATION_COST],
        finance_inputs[ImpactingComponent.DIESEL][INSTALLATION_COST_DECREASE],
        installation_year,
    )
    pv_installation_cost = _component_installation_cost(
        pv_array_size,
        finance_inputs[ImpactingComponent.PV][INSTALLATION_COST],
        finance_inputs[ImpactingComponent.PV][INSTALLATION_COST_DECREASE],
        installation_year,
    )
    total_installation_cost = diesel_installation_cost + pv_installation_cost

    misc_costs = _misc_costs(
        diesel_size, finance_inputs[ImpactingComponent.MISC], pv_array_size
    )
    return (
        pv_cost
        + bos_cost
        + storage_cost
        + diesel_cost
        + total_installation_cost
        + misc_costs
    )


def connections_expenditure(
    finance_inputs: Dict[str, Any], households: pd.DataFrame, installation_year=0
):
    """
    Calculates cost of connecting households to the system

    Inputs:
        - finance_inputs:
            The finance input information.
        - households:
            DataFrame of households from Energy_System().simulation(...)
        - year:
            Installation year

    Outputs:
        Discounted cost

    """

    new_connections = np.max(households) - np.min(households)
    undiscounted_cost = float(
        finance_inputs[HOUSEHOLDS][CONNECTION_COST] * new_connections
    )
    discount_fraction = (1.0 - finance_inputs[DISCOUNT_RATE]) ** installation_year
    total_discounted_cost = undiscounted_cost * discount_fraction

    # Section in comments allows a more accurate consideration of the discounted cost
    # for new connections, but substantially increases the processing time.

    # new_connections = [0]
    # for t in range(int(households.shape[0])-1):
    #     new_connections.append(households['Households'][t+1] - households['Households'][t])
    # new_connections = pd.DataFrame(new_connections)
    # new_connections_daily = hourly_profile_to_daily_sum(new_connections)
    # total_daily_cost = connection_cost * new_connections_daily
    # total_discounted_cost = self.discounted_cost_total(total_daily_cost,start_year,end_year)

    return total_discounted_cost


def discounted_total(
    finance_inputs: Dict[str, Any],
    logger: Logger,
    total_daily: pd.DataFrame,
    *,
    start_year: int = 0,
    end_year: int = 20
):
    """
    Calculates the total discounted cost of some parameter.

    Inputs:
        - finance_inputs:
            The finance input information.
        - logger:
            The logger to use for the run.
        - total_daily:
            Undiscounted energy at a daily resolution
        - start_year:
            Start year of simulation period
        - end_year:
            End year of simulation period

    Outputs:
        The discounted energy total cost.

    """

    try:
        discount_rate = finance_inputs[DISCOUNT_RATE]
    except KeyError:
        logger.error(
            "%sNo discount rate in the finance inputs, missing key: %s%s",
            BColours.fail,
            DISCOUNT_RATE,
            BColours.endc,
        )
        raise

    discounted_fraction = _discounted_fraction(
        discount_rate, start_year=start_year, end_year=end_year
    )
    discounted_energy = discounted_fraction * total_daily
    return np.sum(discounted_energy)[0]


def discounted_equipment_cost(
    diesel_size: float,
    finance_inputs: Dict[str, Any],
    pv_array_size: float,
    storage_size: float,
    installation_year=0,
):
    """
    Calculates cost of all equipment costs

    Inputs:
        - diesel_size:
            Capacity of diesel generator being installed
        - finance_inputs:
            The finance input information.
        - pv_array_size:
            Capacity of PV being installed
        - storage_size:
            Capacity of battery storage being installed
        - installation_year:
            Installation year
    Outputs:
        Discounted cost
    """

    undiscounted_cost = get_total_equipment_cost(
        diesel_size, finance_inputs, pv_array_size, storage_size, installation_year
    )
    discount_fraction = (1.0 - finance_inputs[DISCOUNT_RATE]) ** installation_year

    return undiscounted_cost * discount_fraction


def independent_expenditure(
    finance_inputs: Dict[str, Any],
    location: Location,
    yearly_load_statistics: pd.DataFrame,
    *,
    start_year: int,
    end_year: int
):
    """
    Calculates cost of equipment which is independent of simulation periods

    Inputs:
        - finance_inputs:
            The financial input information.
        - location:
            The location currently being considered.
        - yearly_load_statistics:
            The yearly load statistics information.
        - start_year:
            Start year of simulation period
        - end_year:
            End year of simulation period

    Outputs:
        Discounted cost

    """

    inverter_expenditure = _inverter_expenditure(
        finance_inputs,
        location,
        yearly_load_statistics,
        start_year=start_year,
        end_year=end_year,
    )
    total_expenditure = inverter_expenditure  # ... + other components as required
    return total_expenditure


def total_om(
    diesel_size: float,
    finance_inputs: Dict[str, Any],
    logger: Logger,
    pv_array_size: float,
    storage_size: float,
    *,
    start_year: int = 0,
    end_year: int = 20
):
    """
    Calculates total O&M cost over the simulation period

    Inputs:
        - diesel_size:
            Capacity of diesel generator installed
        - finance_inputs:
            Finance input information.
        - logger:
            The logger to use for the run.
        - pv_array_size:
            Capacity of PV installed
        - storage_size:
            Capacity of battery storage installed
        - start_year:
            Start year of simulation period
        - end_year:
            End year of simulation period

    Outputs:
        Discounted cost

    """

    pv_om = _component_om(
        finance_inputs[ImpactingComponent.PV][OM],
        pv_array_size,
        finance_inputs,
        logger,
        start_year=start_year,
        end_year=end_year,
    )
    storage_om = _component_om(
        finance_inputs[ImpactingComponent.STORAGE][OM],
        storage_size,
        finance_inputs,
        logger,
        start_year=start_year,
        end_year=end_year,
    )
    diesel_om = _component_om(
        finance_inputs[ImpactingComponent.DIESEL][OM],
        diesel_size,
        finance_inputs,
        logger,
        start_year=start_year,
        end_year=end_year,
    )
    general_om = _component_om(
        finance_inputs[GENERAL_OM],
        1,
        finance_inputs,
        logger,
        start_year=start_year,
        end_year=end_year,
    )
    return pv_om + storage_om + diesel_om + general_om


# #%%
# # ==============================================================================
# #   EQUIPMENT EXPENDITURE (DISCOUNTED)
# #       Find system equipment capital expenditure (discounted) for new equipment
# # ==============================================================================


# #   Grid extension components
# def get_grid_extension_cost(self, grid_extension_distance, year):
#     """
#     Function:
#         Calculates cost of extending the grid network to a community
#     Inputs:
#         grid_extension_distance     Distance to the existing grid network
#         year                        Installation year
#     Outputs:
#         Discounted cost
#     """
#     grid_extension_cost = self.finance_inputs.loc["Grid extension cost"]  # per km
#     grid_infrastructure_cost = self.finance_inputs.loc["Grid infrastructure cost"]
#     discount_fraction = (1.0 - self.finance_inputs.loc["Discount rate"]) ** year
#     return (
#         grid_extension_distance * grid_extension_cost * discount_fraction
#         + grid_infrastructure_cost
#     )


# #%%
# # =============================================================================
# #   EQUIPMENT EXPENDITURE (DISCOUNTED) ON INDEPENDENT EXPENDITURE
# #       Find expenditure (discounted) on items independent of simulation periods
# # =============================================================================


# #%%
# # ==============================================================================
# #   EXPENDITURE (DISCOUNTED) ON RUNNING COSTS
# #       Find expenditure (discounted) incurred during the simulation period
# # ==============================================================================
# def get_kerosene_expenditure(
#     self, kerosene_lamps_in_use_hourly, start_year=0, end_year=20
# ):
#     """
#     Function:
#         Calculates cost of kerosene usage
#     Inputs:
#         kerosene_lamps_in_use_hourly        Output from Energy_System().simulation(...)
#         start_year                          Start year of simulation period
#         end_year                            End year of simulation period
#     Outputs:
#         Discounted cost
#     """
#     kerosene_cost = (
#         kerosene_lamps_in_use_hourly * self.finance_inputs.loc["Kerosene cost"]
#     )
#     total_daily_cost = hourly_profile_to_daily_sum(kerosene_cost)
#     total_discounted_cost = self.discounted_cost_total(
#         total_daily_cost, start_year, end_year
#     )
#     return total_discounted_cost


# def get_kerosene_expenditure_mitigated(
#     self, kerosene_lamps_mitigated_hourly, start_year=0, end_year=20
# ):
#     """
#     Function:
#         Calculates cost of kerosene usage that has been avoided by using the system
#     Inputs:
#         kerosene_lamps_mitigated_hourly     Output from Energy_System().simulation(...)
#         start_year                          Start year of simulation period
#         end_year                            End year of simulation period
#     Outputs:
#         Discounted cost
#     """
#     kerosene_cost = (
#         kerosene_lamps_mitigated_hourly * self.finance_inputs.loc["Kerosene cost"]
#     )
#     total_daily_cost = hourly_profile_to_daily_sum(kerosene_cost)
#     total_discounted_cost = self.discounted_cost_total(
#         total_daily_cost, start_year, end_year
#     )
#     return total_discounted_cost


# def get_grid_expenditure(self, grid_energy_hourly, start_year=0, end_year=20):
#     """
#     Function:
#         Calculates cost of grid electricity used by the system
#     Inputs:
#         grid_energy_hourly                  Output from Energy_System().simulation(...)
#         start_year                          Start year of simulation period
#         end_year                            End year of simulation period
#     Outputs:
#         Discounted cost
#     """
#     grid_cost = grid_energy_hourly * self.finance_inputs.loc["Grid cost"]
#     total_daily_cost = hourly_profile_to_daily_sum(grid_cost)
#     total_discounted_cost = self.discounted_cost_total(
#         total_daily_cost, start_year, end_year
#     )
#     return total_discounted_cost


# def get_diesel_fuel_expenditure(
#     self, diesel_fuel_usage_hourly, start_year=0, end_year=20
# ):
#     """
#     Function:
#         Calculates cost of diesel fuel used by the system
#     Inputs:
#         diesel_fuel_usage_hourly            Output from Energy_System().simulation(...)
#         start_year                          Start year of simulation period
#         end_year                            End year of simulation period
#     Outputs:
#         Discounted cost
#     """
#     diesel_fuel_usage_daily = hourly_profile_to_daily_sum(diesel_fuel_usage_hourly)
#     start_day = start_year * 365
#     end_day = end_year * 365
#     diesel_price_daily = []
#     original_diesel_price = self.finance_inputs.loc["Diesel fuel cost"]
#     r_y = 0.01 * self.finance_inputs.loc["Diesel fuel cost decrease"]
#     r_d = ((1.0 + r_y) ** (1.0 / 365.0)) - 1.0
#     for t in range(start_day, end_day):
#         diesel_price = original_diesel_price * (1.0 - r_d) ** t
#         diesel_price_daily.append(diesel_price)
#     diesel_price_daily = pd.DataFrame(diesel_price_daily)
#     total_daily_cost = pd.DataFrame(
#         diesel_fuel_usage_daily.values * diesel_price_daily.values
#     )
#     total_discounted_cost = self.discounted_cost_total(
#         total_daily_cost, start_year, end_year
#     )
#     return total_discounted_cost


# #%%
# # ==============================================================================
# #   FINANCING CALCULATIONS
# #       Functions to calculate discount rates and discounted expenditures
# # ==============================================================================


# #   Calculate LCUE using total discounted costs ($) and discounted energy (kWh)
# def get_LCUE(self, total_discounted_costs, total_discounted_energy):
#     """
#     Function:
#         Calculates the levelised cost of used electricity (LCUE)
#     Inputs:
#         total_discounted_costs        Discounted costs total
#         total_discounted_energy       Discounted energy total
#     Outputs:
#         Levelised cost of used electricity
#     """
#     return total_discounted_costs / total_discounted_energy
