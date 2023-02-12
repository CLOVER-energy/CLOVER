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

from logging import Logger
from typing import Any, Dict, List, Optional, Union

import numpy as np  # pylint: disable=import-error
import pandas as pd  # pylint: disable=import-error

from .__utils__ import ImpactingComponent, LIFETIME, SIZE_INCREMENT
from ..__utils__ import (
    BColours,
    ColumnHeader,
    hourly_profile_to_daily_sum,
    InputFileError,
    InternalError,
    Location,
    Scenario,
)

__all_ = (
    "connections_expenditure",
    "COSTS",
    "diesel_fuel_expenditure",
    "discounted_energy_total",
    "discounted_equipment_cost",
    "expenditure",
    "get_total_equipment_cost",
    "ImpactingComponent",
    "independent_expenditure",
    "total_om",
)

# Capacity cost:
#   Keyword used to denote the capacity-based costs of a component.
CAPACITY_COST: str = "capacity_cost"

# Connection cost:
#   Keyword used to denote the connection cost for a household within the community.
CONNECTION_COST = "connection_cost"

# Cost:
#   Keyword used to denote the cost of a component.
COST: str = "cost"

# Costs:
#   Keyword used for parsing device-specific cost information.
COSTS: str = "costs"

# Cost decrease:
#   Keyword used to denote the cost decrease of a component.
COST_DECREASE: str = "cost_decrease"

# Discount rate:
#   Keyword used to denote the discount rate.
DISCOUNT_RATE = "discount_rate"

# Finance impact:
#   Default `str` used as the format for specifying unique financial impacts.
FINANCE_IMPACT: str = "{type}_{name}"

# Fixed cost:
#   Keyword used to denote the fixed misc. costs of a componnet of the system.
FIXED_COST: str = "fixed_cost"

# General OM:
#   Keyword used to denote general O&M costs of the system.
GENERAL_OM = "general_o&m"

# Installation cost:
#   Keyword used to denote the installation cost of a component.
INSTALLATION_COST: str = "installation_cost"

# Installation cost decrease:
#   Keyword used to denote the installation cost decrease of a component.
INSTALLATION_COST_DECREASE: str = "installation_cost_decrease"

# OM:
#   Keyword used to denote O&M costs.
OM = "o&m"


####################
# Helper functions #
####################


def _component_cost(
    component_cost: float,
    component_cost_decrease: float,
    component_size: float,
    installation_year: int = 0,
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
    return float(system_wide_cost * (1 - annual_reduction) ** installation_year)


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
    end_year: int,
) -> float:
    """
    Computes the O&M cost of a component.

    """

    om_cost_daily = (component_size * component_om_cost) / 365
    total_daily_cost = pd.DataFrame([om_cost_daily] * (end_year - start_year) * 365)

    return discounted_energy_total(
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

    return float(((1.0 + discount_rate) ** (1.0 / 365.0)) - 1.0)


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
        denominator**-time for time in range(start_day, end_day)
    ]

    return pd.DataFrame(discounted_fraction_array)


def _inverter_expenditure(  # pylint: disable=too-many-locals
    finance_inputs: Dict[str, Any],
    location: Location,
    logger: Logger,
    scenario: Scenario,
    yearly_load_statistics: pd.DataFrame,
    *,
    start_year: int,
    end_year: int,
) -> float:
    """
    Calculates cost of inverters based on load calculations

    Inputs:
        - finance_inputs:
            The finance-input information for the system.
        - location:
            The location being considered.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - yearly_load_statistics:
            The yearly-load statistics for the system.
        - scenario:
            The :class:`Scenario` currently being considered.
        - start_year:
            Start year of simulation period
        - end_year:
            End year of simulation period

    Outputs:
        Discounted cost

    """

    # Initialise inverter replacement periods
    replacement_period = finance_inputs[ImpactingComponent.INVERTER.value][LIFETIME]
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
        inverter_discounted_cost = float(0.0)
        return inverter_discounted_cost

    # Initialise inverter sizing calculation
    max_power = []
    inverter_step = finance_inputs[ImpactingComponent.INVERTER.value][SIZE_INCREMENT]
    inverter_size: List[float] = []
    for i in range(len(replacement_intervals)):
        # Calculate maximum power in interval years
        start = replacement_intervals[ColumnHeader.INSTALLATION_YEAR.value].iloc[i]
        end = start + replacement_period
        max_power_interval = (
            yearly_load_statistics[ColumnHeader.MAXIMUM.value].iloc[start:end].max()
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
    # Calculate
    inverter_info[ColumnHeader.DISCOUNT_RATE.value] = [
        (1 - finance_inputs[DISCOUNT_RATE])
        ** inverter_info[ColumnHeader.INSTALLATION_YEAR.value].iloc[i]
        for i in range(len(inverter_info))
    ]
    inverter_info["Inverter cost ($/kW)"] = [
        finance_inputs[ImpactingComponent.INVERTER.value][COST]
        * (1 - 0.01 * finance_inputs[ImpactingComponent.INVERTER.value][COST_DECREASE])
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

    inverter_info[ColumnHeader.DISCOUNTED_EXPENDITURE.value] = [
        inverter_info[ColumnHeader.DISCOUNT_RATE.value].iloc[i]
        * (
            inverter_info[ColumnHeader.INVERTER_SIZE.value].iloc[i]
            if not scenario.fixed_inverter_size
            else scenario.fixed_inverter_size
        )
        * inverter_info["Inverter cost ($/kW)"].iloc[i]
        for i in range(len(inverter_info))
    ]
    inverter_discounted_cost = np.sum(
        inverter_info.iloc[
            inverter_info.index[
                inverter_info[ColumnHeader.INSTALLATION_YEAR.value].isin(
                    list(np.array(range(start_year, end_year)))
                )
            ]
        ][ColumnHeader.DISCOUNTED_EXPENDITURE.value]
    ).round(2)

    return inverter_discounted_cost


def _misc_costs(
    diesel_size: float,
    misc_capacity_cost: float,
    misc_fixed_cost: float,
    pv_array_size: float,
) -> float:
    """
    Calculates cost of miscellaneous capacity-related costs

    Inputs:
        - diesel_size:
            Capacity of diesel generator being installed
        - misc_capacity_cost:
            The misc. costs of the system which scale with the capacity of the system.
        - misc_fixed_cost:
            The misc. costs of the system which do not scale with the capacity of the
            system and which are fixed.
        - pv_array_size:
            Capacity of PV being installed

    Outputs:
        The undiscounted cost.

    """

    total_misc_capacity_cost = (pv_array_size + diesel_size) * misc_capacity_cost

    return total_misc_capacity_cost + misc_fixed_cost


###############################
# Externally facing functions #
###############################


def get_total_equipment_cost(  # pylint: disable=too-many-locals, too-many-statements
    buffer_tanks: float,
    clean_water_tanks: float,
    converters: Dict[str, int],
    diesel_size: float,
    finance_inputs: Dict[str, Any],
    heat_exchangers: float,
    hot_water_tanks: float,
    logger: Logger,
    pv_array_size: float,
    pvt_array_size: float,
    storage_size: float,
    installation_year: int = 0,
) -> float:
    """
    Calculates all equipment costs.

    Inputs:
        - buffer_tanks:
            The number of buffer tanks being installed.
        - clean_water_tanks:
            The number of clean-water tanks being installed.
        - converters:
            A mapping between converter names and the size of each that was added to the
            system this iteration.
        - diesel_size:
            Capacity of diesel generator being installed
        - finance_inputs:
            The finance-input information, parsed from the finance-inputs file.
        - heat_exchangers:
            The number of heat exchangers being installed.
        - hot_water_tanks:
            The number of hot-water tanks being installed.
        - logger:
            The logger to use for the run.
        - pv_array_size:
            Capacity of PV being installed
        - pvt_array_size:
            Capacity of PV-T being installed
        - storage_size:
            Capacity of battery storage being installed
        - installation_year:
            ColumnHeader.INSTALLATION_YEAR.value

    Outputs:
        The combined undiscounted cost of the system equipment.

    """

    # Calculate the various system costs.
    bos_cost = _component_cost(
        finance_inputs[ImpactingComponent.BOS.value][COST],
        finance_inputs[ImpactingComponent.BOS.value][COST_DECREASE],
        pv_array_size,
        installation_year,
    )

    if ImpactingComponent.BUFFER_TANK.value not in finance_inputs and buffer_tanks > 0:
        logger.error(
            "%sNo buffer tank financial input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "tank inputs",
            "No buffer tank financial input information provided and a non-zero number "
            "of clean-water tanks are being considered.",
        )
    buffer_tank_cost: float = 0
    buffer_tank_installation_cost: float = 0
    if buffer_tanks > 0:
        buffer_tank_cost = _component_cost(
            finance_inputs[ImpactingComponent.BUFFER_TANK.value][COST],
            finance_inputs[ImpactingComponent.BUFFER_TANK.value][COST_DECREASE],
            buffer_tanks,
            installation_year,
        )
        buffer_tank_installation_cost = _component_installation_cost(
            buffer_tanks,
            finance_inputs[ImpactingComponent.BUFFER_TANK.value][INSTALLATION_COST],
            finance_inputs[ImpactingComponent.BUFFER_TANK.value][
                INSTALLATION_COST_DECREASE
            ],
            installation_year,
        )

    if (
        ImpactingComponent.CLEAN_WATER_TANK.value not in finance_inputs
        and clean_water_tanks > 0
    ):
        logger.error(
            "%sNo clean-water tank financial input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "tank inputs",
            "No clean-water financial input information provided and a non-zero "
            "number of clean-water tanks are being considered.",
        )
    clean_water_tank_cost: float = 0
    clean_water_tank_installation_cost: float = 0
    if clean_water_tanks > 0:
        clean_water_tank_cost = _component_cost(
            finance_inputs[ImpactingComponent.CLEAN_WATER_TANK.value][COST],
            finance_inputs[ImpactingComponent.CLEAN_WATER_TANK.value][COST_DECREASE],
            clean_water_tanks,
            installation_year,
        )
        clean_water_tank_installation_cost = _component_installation_cost(
            clean_water_tanks,
            finance_inputs[ImpactingComponent.CLEAN_WATER_TANK.value][
                INSTALLATION_COST
            ],
            finance_inputs[ImpactingComponent.CLEAN_WATER_TANK.value][
                INSTALLATION_COST_DECREASE
            ],
            installation_year,
        )

    converter_costs = sum(
        _component_cost(
            finance_inputs[
                FINANCE_IMPACT.format(
                    type=ImpactingComponent.CONVERTER.value, name=converter
                )
            ][COST],
            finance_inputs[
                FINANCE_IMPACT.format(
                    type=ImpactingComponent.CONVERTER.value, name=converter
                )
            ][COST_DECREASE],
            size,
            installation_year,
        )
        for converter, size in converters.items()
    )
    converter_installation_costs = sum(
        _component_installation_cost(
            size,
            finance_inputs[
                FINANCE_IMPACT.format(
                    type=ImpactingComponent.CONVERTER.value, name=converter
                )
            ][INSTALLATION_COST],
            finance_inputs[
                FINANCE_IMPACT.format(
                    type=ImpactingComponent.CONVERTER.value, name=converter
                )
            ][INSTALLATION_COST_DECREASE],
            installation_year,
        )
        for converter, size in converters.items()
    )

    diesel_cost = _component_cost(
        finance_inputs[ImpactingComponent.DIESEL.value][COST],
        finance_inputs[ImpactingComponent.DIESEL.value][COST_DECREASE],
        diesel_size,
        installation_year,
    )
    diesel_installation_cost = _component_installation_cost(
        diesel_size,
        finance_inputs[ImpactingComponent.DIESEL.value][INSTALLATION_COST],
        finance_inputs[ImpactingComponent.DIESEL.value][INSTALLATION_COST_DECREASE],
        installation_year,
    )

    if (
        ImpactingComponent.HEAT_EXCHANGER.value not in finance_inputs
        and heat_exchangers > 0
    ):
        logger.error(
            "%sNo heat exchanger financial input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "heat exchanger inputs",
            "No heat exchanger financial input information provided and a non-zero "
            "number of clean-water tanks are being considered.",
        )
    heat_exchanger_cost: float = 0
    heat_exchanger_installation_cost: float = 0
    if heat_exchangers > 0:
        heat_exchanger_cost = _component_cost(
            finance_inputs[ImpactingComponent.HEAT_EXCHANGER.value][COST],
            finance_inputs[ImpactingComponent.HEAT_EXCHANGER.value][COST_DECREASE],
            heat_exchangers,
            installation_year,
        )
        heat_exchanger_installation_cost = _component_installation_cost(
            heat_exchangers,
            finance_inputs[ImpactingComponent.HEAT_EXCHANGER.value][INSTALLATION_COST],
            finance_inputs[ImpactingComponent.HEAT_EXCHANGER.value][
                INSTALLATION_COST_DECREASE
            ],
            installation_year,
        )

    if (
        ImpactingComponent.HOT_WATER_TANK.value not in finance_inputs
        and hot_water_tanks > 0
    ):
        logger.error(
            "%sNo hot-water tank financial input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "tank inputs",
            "No hot-water financial input information provided and a non-zero "
            "number of clean-water tanks are being considered.",
        )
    hot_water_tank_cost: float = 0
    hot_water_tank_installation_cost: float = 0
    if hot_water_tanks > 0:
        hot_water_tank_cost = _component_cost(
            finance_inputs[ImpactingComponent.HOT_WATER_TANK.value][COST],
            finance_inputs[ImpactingComponent.HOT_WATER_TANK.value][COST_DECREASE],
            hot_water_tanks,
            installation_year,
        )
        hot_water_tank_installation_cost = _component_installation_cost(
            hot_water_tanks,
            finance_inputs[ImpactingComponent.HOT_WATER_TANK.value][INSTALLATION_COST],
            finance_inputs[ImpactingComponent.HOT_WATER_TANK.value][
                INSTALLATION_COST_DECREASE
            ],
            installation_year,
        )

    pv_cost = _component_cost(
        finance_inputs[ImpactingComponent.PV.value][COST],
        finance_inputs[ImpactingComponent.PV.value][COST_DECREASE],
        pv_array_size,
        installation_year,
    )
    pv_installation_cost = _component_installation_cost(
        pv_array_size,
        finance_inputs[ImpactingComponent.PV.value][INSTALLATION_COST],
        finance_inputs[ImpactingComponent.PV.value][INSTALLATION_COST_DECREASE],
        installation_year,
    )

    if ImpactingComponent.PV_T.value not in finance_inputs and pvt_array_size > 0:
        logger.error(
            "%sNo PV-T financial input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "finance inputs",
            "No PV-T financial input information provided and a non-zero number of PV-T"
            "panels are being considered.",
        )
    pvt_cost: float = 0
    pvt_installation_cost: float = 0
    if pvt_array_size > 0:
        pvt_cost = _component_cost(
            finance_inputs[ImpactingComponent.PV_T.value][COST],
            finance_inputs[ImpactingComponent.PV_T.value][COST_DECREASE],
            pv_array_size,
            installation_year,
        )
        pvt_installation_cost = _component_installation_cost(
            pvt_array_size,
            finance_inputs[ImpactingComponent.PV_T.value][INSTALLATION_COST],
            finance_inputs[ImpactingComponent.PV_T.value][INSTALLATION_COST_DECREASE],
            installation_year,
        )

    storage_cost = _component_cost(
        finance_inputs[ImpactingComponent.STORAGE.value][COST],
        finance_inputs[ImpactingComponent.STORAGE.value][COST_DECREASE],
        storage_size,
        installation_year,
    )

    total_installation_cost = (
        buffer_tank_installation_cost
        + clean_water_tank_installation_cost
        + converter_installation_costs
        + diesel_installation_cost
        + heat_exchanger_installation_cost
        + hot_water_tank_installation_cost
        + pv_installation_cost
        + pvt_installation_cost
    )

    # Determine the capacity-based misc. costs associated with the system.
    try:
        misc_capacity_cost: float = finance_inputs[ImpactingComponent.MISC.value][
            CAPACITY_COST
        ]
    except KeyError:
        logger.warning(
            "Using %s for misc. capacity costs is depreceated. Consider using %s.",
            COST,
            CAPACITY_COST,
        )
        try:
            misc_capacity_cost = finance_inputs[ImpactingComponent.MISC.value][COST]
        except KeyError:
            logger.error(
                "Neither %s nor the depreceated keyword %s used for misc. system costs.",
                CAPACITY_COST,
                COST,
            )
            raise

    try:
        misc_fixed_cost: float = finance_inputs[ImpactingComponent.MISC.value][
            FIXED_COST
        ]
    except KeyError:
        logger.warning(
            "Missing fixed capacity costs in finance inputs file, assuming zero."
        )
        misc_fixed_cost = 0

    misc_costs: float = _misc_costs(
        diesel_size,
        misc_capacity_cost,
        misc_fixed_cost,
        pv_array_size,
    )

    return (
        bos_cost
        + buffer_tank_cost
        + clean_water_tank_cost
        + converter_costs
        + diesel_cost
        + heat_exchanger_cost
        + hot_water_tank_cost
        + misc_costs
        + pv_cost
        + pvt_cost
        + storage_cost
        + total_installation_cost
    )


def connections_expenditure(
    finance_inputs: Dict[str, Any], households: pd.Series, installation_year: int = 0
) -> float:
    """
    Calculates cost of connecting households to the system

    Inputs:
        - finance_inputs:
            The finance input information.
        - households:
            A :class:`pd.Series` of households from Energy_System().simulation(...)
        - year:
            ColumnHeader.INSTALLATION_YEAR.value

    Outputs:
        Discounted cost

    """

    new_connections = np.max(households) - np.min(households)
    undiscounted_cost = float(
        finance_inputs[ImpactingComponent.HOUSEHOLDS.value][CONNECTION_COST]
        * new_connections
    )
    discount_fraction: float = (
        1.0 - finance_inputs[DISCOUNT_RATE]
    ) ** installation_year
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


def diesel_fuel_expenditure(
    diesel_fuel_usage_hourly: pd.Series,
    finance_inputs: Dict[str, Any],
    logger: Logger,
    *,
    start_year: int = 0,
    end_year: int = 20,
) -> float:
    """
    Calculates cost of diesel fuel used by the system

    Inputs:
        - diesel_fuel_usage_hourly:
            Output from Energy_System().simulation(...)
        - finance_inputs:
            The finance input information.
        - logger:
            The logger to use for the run.
        - start_year:
            Start year of simulation period
        - end_year:
            End year of simulation period

    Outputs:
        Discounted cost

    """

    diesel_fuel_usage_daily = hourly_profile_to_daily_sum(diesel_fuel_usage_hourly)
    start_day = start_year * 365
    end_day = end_year * 365
    r_y = 0.01 * finance_inputs[ImpactingComponent.DIESEL_FUEL.value][COST_DECREASE]
    r_d = ((1.0 + r_y) ** (1.0 / 365.0)) - 1.0
    diesel_price_daily: pd.DataFrame = pd.DataFrame(
        [
            finance_inputs[ImpactingComponent.DIESEL_FUEL.value][COST]
            * (1.0 - r_d) ** day
            for day in range(start_day, end_day)
        ]
    )

    total_daily_cost = pd.DataFrame(
        diesel_fuel_usage_daily.values * diesel_price_daily.values
    )
    total_discounted_cost = discounted_energy_total(
        finance_inputs,
        logger,
        total_daily_cost,
        start_year=start_year,
        end_year=end_year,
    )

    return total_discounted_cost


def discounted_energy_total(
    finance_inputs: Dict[str, Any],
    logger: Logger,
    total_daily: Union[pd.DataFrame, pd.Series],
    *,
    start_year: int = 0,
    end_year: int = 20,
) -> float:
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
    if not isinstance(total_daily, pd.Series):
        try:
            total_daily = total_daily.iloc[:, 0]
        except pd.core.indexing.IndexingError as e:  # type: ignore
            logger.error(
                "%sAn unexpected internal error occured in the financial inputs file "
                "when casting `pd.Series` to `pd.DataFrame`: %s%s",
                str(e),
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "An error occured casting between pandas types."
            ) from None
    discounted_energy = pd.DataFrame(discounted_fraction.iloc[:, 0] * total_daily)
    return float(np.sum(discounted_energy))  # type: ignore


def discounted_equipment_cost(
    buffer_tanks: int,
    clean_water_tanks: int,
    converters: Dict[str, int],
    diesel_size: float,
    finance_inputs: Dict[str, Any],
    heat_exchangers: int,
    hot_water_tanks: int,
    logger: Logger,
    pv_array_size: float,
    pvt_array_size: float,
    storage_size: float,
    installation_year: int = 0,
) -> float:
    """
    Calculates cost of all equipment costs

    Inputs:
        - buffer_tanks:
            The number of buffer tanks being installed.
        - clean_water_tanks:
            The number of clean-water tanks being installed.
        - converters:
            A mapping between converter names and the size of each that was added to the
            system this iteration.
        - diesel_size:
            Capacity of diesel generator being installed
        - finance_inputs:
            The finance input information.
        - heat_exchangers:
            The number of heat exchangers being installed.
        - hot_water_tanks:
            The number of hot-water tanks being installed.
        - logger:
            The logger to use for the run.
        - pv_array_size:
            Capacity of PV being installed
        - pvt_array_size:
            Capacity of PV-T being installed
        - storage_size:
            Capacity of battery storage being installed
        - installation_year:
            ColumnHeader.INSTALLATION_YEAR.value
    Outputs:
        Discounted cost
    """

    undiscounted_cost = get_total_equipment_cost(
        buffer_tanks,
        clean_water_tanks,
        converters,
        diesel_size,
        finance_inputs,
        heat_exchangers,
        hot_water_tanks,
        logger,
        pv_array_size,
        pvt_array_size,
        storage_size,
        installation_year,
    )
    discount_fraction = (
        1.0 - float(finance_inputs[DISCOUNT_RATE])
    ) ** installation_year

    return undiscounted_cost * discount_fraction


def expenditure(
    component: ImpactingComponent,
    finance_inputs: Dict[str, Any],
    hourly_usage: pd.Series,
    logger: Logger,
    *,
    start_year: int = 0,
    end_year: int = 20,
) -> float:
    """
    Calculates cost of the usage of a component.

    Inputs:
        - component:
            The component to consider.
        - finance_inputs:
            The financial input information.
        - hourly_usage:
            Output from Energy_System().simulation(...)
        - start_year:
            Start year of simulation period
        - end_year:
            End year of simulation period

    Outputs:
        Discounted cost

    """

    hourly_cost = hourly_usage * finance_inputs[component.value][COST]
    total_daily_cost = hourly_profile_to_daily_sum(hourly_cost)
    total_discounted_cost = discounted_energy_total(
        finance_inputs,
        logger,
        total_daily_cost,
        start_year=start_year,
        end_year=end_year,
    )
    return total_discounted_cost


def independent_expenditure(
    finance_inputs: Dict[str, Any],
    location: Location,
    logger: Logger,
    scenario: Scenario,
    yearly_load_statistics: pd.DataFrame,
    *,
    start_year: int,
    end_year: int,
) -> float:
    """
    Calculates cost of equipment which is independent of simulation periods

    Inputs:
        - finance_inputs:
            The financial input information.
        - location:
            The location currently being considered.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - yearly_load_statistics:
            The yearly load statistics information.
        - scenario:
            The :class:`Scenario` currently being considered.
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
        logger,
        scenario,
        yearly_load_statistics,
        start_year=start_year,
        end_year=end_year,
    )
    total_expenditure = inverter_expenditure  # ... + other components as required
    return total_expenditure


def total_om(  # pylint: disable=too-many-locals
    buffer_tanks: int,
    clean_water_tanks: int,
    converters: Optional[Dict[str, int]],
    diesel_size: float,
    finance_inputs: Dict[str, Any],
    heat_exchangers: int,
    hot_water_tanks: int,
    logger: Logger,
    pv_array_size: float,
    pvt_array_size: float,
    storage_size: float,
    *,
    start_year: int = 0,
    end_year: int = 20,
) -> float:
    """
    Calculates total O&M cost over the simulation period

    Inputs:
        - buffer_tanks:
            The number of buffer tanks installed.
        - clean_water_tanks:
            The number of clean-water tanks installed.
        - converters:
            A mapping between converter names and the size of each that was added to the
            system this iteration.
        - diesel_size:
            Capacity of diesel generator installed.
        - finance_inputs:
            Finance input information.
        - heat_exchangers:
            The number of heat exchangers installed.
        - hot_water_tanks:
            The number of hot-water tanks installed.
        - logger:
            The logger to use for the run.
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
        Discounted cost

    """

    if ImpactingComponent.BUFFER_TANK.value not in finance_inputs and buffer_tanks > 0:
        logger.error(
            "%sNo buffer-tank financial input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "tank inputs",
            "No buffer-tank financial input information provided and a non-zero number "
            "of buffer tanks are being considered.",
        )
    buffer_tank_om: float = 0
    if buffer_tanks > 0:
        buffer_tank_om = _component_om(
            finance_inputs[ImpactingComponent.BUFFER_TANK.value][OM],
            buffer_tanks,
            finance_inputs,
            logger,
            start_year=start_year,
            end_year=end_year,
        )

    if (
        ImpactingComponent.CLEAN_WATER_TANK.value not in finance_inputs
        and clean_water_tanks > 0
    ):
        logger.error(
            "%sNo clean-water-tank financial input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "tank inputs",
            "No clean-water tank financial input information provided and a non-zero "
            "number of clean-water tanks are being considered.",
        )
    clean_water_tank_om: float = 0
    if clean_water_tanks > 0:
        clean_water_tank_om = _component_om(
            finance_inputs[ImpactingComponent.CLEAN_WATER_TANK.value][OM],
            clean_water_tanks,
            finance_inputs,
            logger,
            start_year=start_year,
            end_year=end_year,
        )

    converters_om: float
    if converters is not None:
        converters_om = sum(
            _component_om(
                finance_inputs[
                    FINANCE_IMPACT.format(
                        type=ImpactingComponent.CONVERTER.value, name=converter
                    )
                ][OM],
                size,
                finance_inputs,
                logger,
                start_year=start_year,
                end_year=end_year,
            )
            for converter, size in converters.items()
        )
    else:
        logger.debug(
            "No converters were installed in the system, hence no OM costs to compute."
        )

    diesel_om = _component_om(
        finance_inputs[ImpactingComponent.DIESEL.value][OM],
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

    if (
        ImpactingComponent.HEAT_EXCHANGER.value not in finance_inputs
        and heat_exchangers > 0
    ):
        logger.error(
            "%sNo heat-exchanger financial input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "heat exchanger inputs",
            "No heat-exchanger financial input information provided and a non-zero "
            "number of heat exchangers are being considered.",
        )
    heat_exchanger_om: float = 0
    if heat_exchangers > 0:
        heat_exchanger_om = _component_om(
            finance_inputs[ImpactingComponent.HEAT_EXCHANGER.value][OM],
            heat_exchangers,
            finance_inputs,
            logger,
            start_year=start_year,
            end_year=end_year,
        )

    if (
        ImpactingComponent.HOT_WATER_TANK.value not in finance_inputs
        and hot_water_tanks > 0
    ):
        logger.error(
            "%sNo hot-water-tank financial input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "tank inputs",
            "No hot-water tank financial input information provided and a non-zero "
            "number of clean-water tanks are being considered.",
        )
    hot_water_tank_om: float = 0
    if hot_water_tanks > 0:
        hot_water_tank_om = _component_om(
            finance_inputs[ImpactingComponent.HOT_WATER_TANK.value][OM],
            hot_water_tanks,
            finance_inputs,
            logger,
            start_year=start_year,
            end_year=end_year,
        )

    pv_om = _component_om(
        finance_inputs[ImpactingComponent.PV.value][OM],
        pv_array_size,
        finance_inputs,
        logger,
        start_year=start_year,
        end_year=end_year,
    )

    if ImpactingComponent.PV_T.value not in finance_inputs and pvt_array_size > 0:
        logger.error(
            "%sNo PV-T financial input information provided.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "finance inputs",
            "No PV-T financial input information provided and a non-zero number of PV-T"
            "panels are being considered.",
        )
    pvt_om: float = 0
    if pvt_array_size > 0:
        pvt_om = _component_om(
            finance_inputs[ImpactingComponent.PV_T.value][OM],
            pvt_array_size,
            finance_inputs,
            logger,
            start_year=start_year,
            end_year=end_year,
        )

    storage_om = _component_om(
        finance_inputs[ImpactingComponent.STORAGE.value][OM],
        storage_size,
        finance_inputs,
        logger,
        start_year=start_year,
        end_year=end_year,
    )

    return (
        buffer_tank_om
        + clean_water_tank_om
        + converters_om
        + diesel_om
        + general_om
        + heat_exchanger_om
        + hot_water_tank_om
        + pv_om
        + pvt_om
        + storage_om
    )


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
#         year                        ColumnHeader.INSTALLATION_YEAR.value
#     Outputs:
#         Discounted cost
#     """
#     grid_extension_cost = self.finance_inputs.iloc["Grid extension cost"]  # per km
#     grid_infrastructure_cost = self.finance_inputs.iloc["Grid infrastructure cost"]
#     discount_fraction = (1.0 - self.finance_inputs.iloc[ColumnHeader.DISCOUNT_RATE.value]) ** year
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
