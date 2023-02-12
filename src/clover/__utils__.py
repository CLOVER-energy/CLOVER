#!/usr/bin/python3
########################################################################################
# __utils__.py - CLOVER Utility module.                                                #
#                                                                                      #
# Author: Phil Sandwell, Ben Winchester                                                #
# Copyright: Phil Sandwell, 2018                                                       #
# Date created: 13/07/2021                                                             #
#                                                                                      #
# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
__utils__.py - Utility module for CLOVER.

The utility module contains functionality which is used by various scripts, modules, and
components across CLOVER, as well as commonly-held variables to prevent dependency
issues and increase the ease of code alterations.

"""

import dataclasses
import enum
import logging
import os

from typing import Any, Dict, List, Optional, Set, Union

import json
import numpy as np  # pylint: disable=import-error
import pandas as pd  # pylint: disable=import-error
import scipy  # pylint: disable=import-error
import yaml  # pylint: disable=import-error

from tqdm import tqdm  # pylint: disable=import-error

__all__ = (
    "BColours",
    "CleanWaterMode",
    "Criterion",
    "CUT_OFF_TIME",
    "daily_sum_to_monthly_sum",
    "DEFAULT_SCENARIO",
    "DemandType",
    "DesalinationScenario",
    "dict_to_dataframe",
    "DieselMode",
    "DONE",
    "ELECTRIC_POWER",
    "EXCHANGER",
    "FAILED",
    "get_logger",
    "HEAT_CAPACITY_OF_WATER",
    "HotWaterScenario",
    "hourly_profile_to_daily_sum",
    "HTFMode",
    "InputFileError",
    "InternalError",
    "KEROSENE_DEVICE_NAME",
    "KeyResults",
    "Location",
    "LOCATIONS_FOLDER_NAME",
    "LOGGER_DIRECTORY",
    "monthly_profile_to_daily_profile",
    "monthly_times_to_daily_times",
    "NAME",
    "open_simulation",
    "OperatingMode",
    "PACKAGE_NAME",
    "ProgrammerJudgementFault",
    "RAW_CLOVER_PATH",
    "read_yaml",
    "RenewableEnergySource",
    "ResourceType",
    "RenewablesNinjaError",
    "save_simulation",
    "Scenario",
    "Simulation",
    "SystemAppraisal",
    "SystemDetails",
    "ZERO_CELCIUS_OFFSET",
)


# Cold water:
#   Used for parsing cold-water related information.
COLD_WATER: str = "cold_water"

# Conventional sources:
#   Keyword used for parsing conventional-source information.
CONVENTIONAL_SOURCES: str = "conventional_sources"

# Cut off time:
#   The time up and to which information about the load of each device will be returned.
CUT_OFF_TIME: int = 72  # [hours]

# Default scenario:
#   The name of the default scenario to be used in CLOVER.
DEFAULT_SCENARIO: str = "default"

# Desalination scenario:
#   Keyword for parsing the desalination scenario from the scenario inputs.
DESALINATION_SCENARIO: str = "desalination_scenario"

# Done message:
#   The message to display when a task was successful.
DONE: str = "[   DONE   ]"

# Electric power:
#   Keyword used for parsing electric power.
ELECTRIC_POWER: str = "electric_power"

# Exchanger:
#   Keyword used for parsing heat-exchanger information.
EXCHANGER: str = "heat_exchanger"

# Failed message:
#   The message to display when a task has failed.
FAILED: str = "[  FAILED  ]"

# Heat capacity of water:
#   The heat capacity of water, measured in Joules per kilogram Kelvin.
HEAT_CAPACITY_OF_WATER: int = 4182

# Hot water scenario:
#   Keyword used for parsing the hot-water scenario to use.
HOT_WATER_SCENARIO: str = "hot_water_scenario"

# Hours per year:
#   The number of hours in a year, used for reshaping arrays.
HOURS_PER_YEAR: int = 8760

# Iteration length:
#   Used when parsing information about the iteration length to use in optimisations.
ITERATION_LENGTH: str = "iteration_length"

# Kerosene device name:
#   The name used to denote the kerosene device.
KEROSENE_DEVICE_NAME: str = "kerosene"

# Locations folder name:
#   The name of the locations folder.
LOCATIONS_FOLDER_NAME: str = "locations"

# Logger directory:
#   The directory in which to save logs.
LOGGER_DIRECTORY: str = "logs"

# Max:
#   Keyword used when parsing information about the maximum system size to consider in
#   optimisations.
MAX: str = "max"

# Min:
#   Keyword used when parsing information about the minimum system size to consider in
#   optimisations.
MIN: str = "min"

# Mode:
#   Used for parsing various operation modes.
MODE: str = "mode"

# Month mid-day:
#   The "day" in the year that falls in the middle of the month.
MONTH_MID_DAY: List[int] = [
    0,
    14,
    45,
    72,
    104,
    133,
    164,
    194,
    225,
    256,
    286,
    317,
    344,
    364,
]

# Month start day:
#   The "day" in the year that falls at the start of each month.
MONTH_START_DAY: List[int] = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]

# Name:
#   Keyword used for parsing converter name information.
NAME: str = "name"

# Number of iterations:
#   The number of iterations to consider in the optimisation.
NUMBER_OF_ITERATIONS: str = "number_of_iterations"

# Package name:
#   The name of the CLOVER directory, used for locating files that are installed when
#   packaged but are accessed locally in developer code.
PACKAGE_NAME: str = "clover"

# PVT Scenario:
#   Keyword used for parsing PV-T scenario information.
PVT_SCENARIO: str = "pvt_scenario"

# Raw CLOVER path:
#   The path to the clover source directory to use when running in github mode.
RAW_CLOVER_PATH: str = os.path.join("src", "clover")

# Skipped:
#   Keyword used when skipping part of the CLOVER flow.
SKIPPING: str = "[ SKIPPING ]"

# Step:
#   Keyword used when parsing information about the system size step to consider in
#   optimisations.
STEP: str = "step"

# Supply temperature:
#   Used to parse supply-temperature information.
SUPPLY_TEMPERATURE: str = "supply_temperature"

# Zero celcius offset:
#   Used for offsetting zero degrees celcius in Kelvin.
ZERO_CELCIUS_OFFSET: float = 273.15


class AuxiliaryHeaterType(enum.Enum):
    """
    Denotes the type of auxiliary heater used in the system.

    - DIESEL:
        Denotes that a diesel heater is being used.

    - ELECTRIC:
        Denotes that an electrically-powered heater is being used.

    """

    DIESEL = "diesel"
    ELECTRIC = "electric"


# Auxiliary heater name to type mapping:
#   Used to parse auxiliary heater types, allowing for more than are defined on the
#   base enum class.
AUXILIARY_HEATER_NAME_TO_TYPE_MAPPING: Dict[str, Optional[AuxiliaryHeaterType]] = {
    e.value: e for e in AuxiliaryHeaterType
}
AUXILIARY_HEATER_NAME_TO_TYPE_MAPPING["none"] = None


@dataclasses.dataclass
class BColours:
    """
    Contains various colours used for pretty-printing out to the command-line on stdout.

    - FAIL:
        Used for a failure message.

    - WARNING, OKBLUE:
        Various colours used.

    - ENDC:
        Used to reset the colour of the terminal output.

    - BOLD, UNDERLINE:
        Used to format the text.

    """

    fail = "\033[91m"
    warning = "\033[93m"
    okblue = "\033[94m"
    endc = "\033[0m"
    bolc = "\033[1m"
    underline = "\033[4m"


class CleanWaterMode(enum.Enum):
    """
    Used to specify the clean-water mode for the system.

    - BACKUP:
        The clean-water demand will only be fulfiled using minigrid power as backup to
        carry out electric desalination if there are any electric desalination
        converters present.

    - PRIORITISE:
        The clean-water demand will be fulfiled always, utilising diesel generators if
        necessary to carry out electric desalination during clean-water blackouts..

    """

    BACKUP = "backup"
    PRIORITISE = "prioritise"
    THERMAL_ONLY = "thermal_only"


@dataclasses.dataclass
class CleanWaterScenario:
    """
    Specifies the clean-water scenario being carried out.

    .. attribute:: conventional_sources
        A `set` of the names of conventional drinking-water sources specified.

    .. attribute:: mode
        The clean water mode being modelled.

    .. attribute:: sources
        A `set` of the names of clean-water sources specified.

    """

    conventional_sources: List[str]
    mode: CleanWaterMode
    sources: List[str]


class ColdWaterSupply(enum.Enum):
    """
    Specifies the source of cold water to the hot-water system.

    - CLEAN_WATER:
        Denotes that cold water is sourced from the clean-water system.

    - UNLIMITED:
        Denotes that an unlimited supply of cold water is available. I.E., the
        desalination and/or cleaning of the feedwater to the overall water-demand system
        is ignored and it is assumed that there exists a supply that can fulfil the
        input needs of the hot-water system.

    """

    CLEAN_WATER = "clean_water"
    UNLIMITED = "unlimited"


class ColumnHeader(enum.Enum):
    """
    Contains column header information.

    - BLACKOUTS:
        The times for which the electricity system experienced a blackout in supply.

    - BATTERY_HEALTH:
        The health of the batteries installed.

    - BUFFER_TANK_OUTPUT:
        The output of the buffer tank(s) installed.

    - BUFFER_TANK_TEMPERATURE:
        The temperature of any buffer tank(s) installed in the system.

    - CLEAN_WATER_BLACKOUTS:
        Blackout times in the clean water supply.

    - CLEAN_WATER_FROM_CONVENTIONAL_SOURCES:
        Clean water produced from conventional sources.

    - CLEAN_WATER_FROM_EXCESS_ELECTRICITY:
        Clean water produced from excess electricity available within the system.

    - CLEAN_WATER_FROM_PRIORITISATION:
        The clean water which was supplied through prioritising clean-water loads.

    - CLEAN_WATER_FROM_RENEWABLES:
        The clean water which was supplied by renewable technologies.

    - CLEAN_WATER_FROM_STORAGE:
        The clean water which was supplied from tank storage.

    - CW_PVT_ELECTRICITY_SUPPLIED:
        The electricity supplied by the clean-water PV-T.

    - CW_PVT_ELECTRICITY_SUPPLIED_PER_KWP:
        The electricity supplied by the clean-water PV-T per kWp installed.

    - CW_PVT_OUTPUT_TEMPERATURE:
        The output temperature of the clean-water PV-T installed.

    - CW_TANK_STORAGE_PROFILE:
        The storage profile of the clean-water tanks.

    - DIESEL_ENERGY_SUPPLIED:
        The energy which was supplied by the diesel generators present in the system.

    - DIESEL_FUEL_USAGE:
        The diesel fuel usage in litres by the system.

    - DIESEL_GENERATOR_TIMES:
        The times for which the backup electrical diesel generator was operating in
        order to meet demand.

    - DISCOUNT_RATE:
        The discount rate for parts which are periodically replaced.

    - DISCOUNTED_EXPENDITURE:
        The discounted expenditure on replacing parts which require periodic
        replacement.

    - DUMPED_ELECTRICITY:
        Excess electricity which was dumped due to the system being unable to either
        utilise or store it.

    - GRID_ENERGY:
        Energy that was supplied by the grid.

    - ELECTRICITY_FROM_STORAGE:
        Electricity that was supplied by installed storage.

    - EXCESS_POWER_CONSUMED_BY_DESALINATION:
        Excess power consumed by desalination.

    - HOURLY_STORAGE_PROFILE:
        The hourly battery storage profile for the system.

    - HOUSEHOLDS:
        The number of households present in the community.

    - HW_PVT_OUTPUT_TEMPERATURE:
        The output temperature of HTF leaving the hot-water PV-T installed.

    - HW_PVT_ELECTRICITY_SUPPLIED:
        The electricity supplied by the hot-water PV-T.

    - HW_PVT_ELECTRICITY_SUPPLIED_PER_KWP:
        The electricity supplied by the hot-water PV-T per kWp of installed PV.

    - HW_RENEWABLES_FRACTION:
        The fraction of hot-water demand that was met through renewables.

    - HW_TANK_OUTPUT:
        The output volume from the hot-water tank(s) installed.

    - HW_TANK_TEMPERATURE:
        The temperature profile of the hot-water tank(s) installed.

    - INSTALLATION_YEAR:
        The year in which the installation was made.

    - INVERTER_COST:
        The cost of the inverter installed.

    - INVERTER_SIZE:
        The size of the inverter installed.

    - KEROSENE_LAMPS:
        The number of kerosene lamps that were in use.

    - KEROSENE_MITIGATION:
        The kerosene usage that was mitigated by utilising the system.

    - LOAD_ENERGY:
        The electric load that was placed on the system.

    - MAXIMUM:
        Used in the yearly load statistics.

    - POWER_CONSUMED_BY_DESALINATION:
        The power that was consumed carrying out desalination, either using electricity
        as the primary driving force, or using it in a supplementary way.

    - POWER_CONSUMED_BY_ELECTRIC_DEVICES:
        Power consumed by electric devices present within the system.

    - POWER_CONSUMED_BY_HOT_WATER:
        Power consumed by providing hot water, either through pumps etc. or by
        auxiliary heating.

    - POWER_CONSUMED_BY_THERMAL_DESALINATION:
        Power consumed by thermal desalination.

    - PV_ELECTRICITY_SUPPLIED:
        The electricity supplied by the PV installed.

    - RENEWABLE_ELECTRICITY_SUPPLIED:
        The electricity that was supplied renewably.

    - RENEWABLE_ELECTRICITY_USED_DIRECTLY:
        The renewables produced that were used directly to meet loads.

    - STORAGE_PROFILE:
        The profile for the electric storage system.

    - TOTAL_CW_CONSUMED:
        The total clean water that was consumed.

    - TOTAL_CW_LOAD:
        The total clean-water load placed on the system.

    - TOTAL_CW_SUPPLIED:
        The total clean water that was supplied by the system.

    - TOTAL_ELECTRICITY_CONSUMED:
        The total electricity that was consumed in the system.

    - TOTAL_GHGS:
        The total GHGs information.

    - TOTAL_HW_LOAD:
        The total hot-water load that was placed on the system.

    - TOTAL_PVT_ELECTRICITY_SUPPLIED:
        The total electricity that was supplied by PV-T installed.

    - UNMET_CLEAN_WATER:
        The clean-water demand that was unmet by the system.

    - UNMET_ELECTRICITY:
        The electricity demand that went unmet by the system.

    - WATER_SURPLUS:
        The water surplus that was generated by the system.

    """

    BLACKOUTS = "Blackouts"
    BATTERY_HEALTH = "Battery health"
    BUFFER_TANK_OUTPUT = "Buffer tank output volume (l)"
    BUFFER_TANK_TEMPERATURE = "Buffer tank temperature (degC)"
    CLEAN_WATER_BLACKOUTS = "Clean water blackouts"
    CLEAN_WATER_FROM_CONVENTIONAL_SOURCES = (
        "Drinking water supplied via conventional sources (l)"
    )
    CLEAN_WATER_FROM_EXCESS_ELECTRICITY = (
        "Clean water supplied using excess minigrid energy (l)"
    )
    CLEAN_WATER_FROM_PRIORITISATION = "Clean water supplied via backup desalination (l)"
    CLEAN_WATER_FROM_RENEWABLES = "Renewable clean water produced (l)"
    CLEAN_WATER_FROM_STORAGE = "Clean water supplied via tank storage (l)"
    CW_PVT_ELECTRICITY_SUPPLIED = "Clean-water PV-T electric energy supplied (kWh)"
    CW_PVT_ELECTRICITY_SUPPLIED_PER_KWP = (
        "Clean-water PV-T electric energy supplied per kWp"
    )
    CW_PVT_OUTPUT_TEMPERATURE = "Clean-water PV-T output temperature (degC)"
    CW_TANK_STORAGE_PROFILE = "Water held in clean-water storage tanks (l)"
    DIESEL_ENERGY_SUPPLIED = "Diesel energy (kWh)"
    DIESEL_FUEL_USAGE = "Diesel fuel usage (l)"
    DIESEL_GENERATOR_TIMES = "Diesel times"
    DISCOUNTED_EXPENDITURE = "Discounted expenditure ($)"
    DISCOUNT_RATE = "Discount rate"
    DUMPED_ELECTRICITY = "Dumped energy (kWh)"
    ELECTRICITY_FROM_STORAGE = "Storage energy supplied (kWh)"
    EXCESS_POWER_CONSUMED_BY_DESALINATION = (
        "Excess power consumed desalinating clean water (kWh)"
    )
    GRID_ENERGY = "Grid energy (kWh)"
    HOURLY_STORAGE_PROFILE = "Hourly storage (kWh)"
    HOUSEHOLDS = "Households"
    HW_PVT_OUTPUT_TEMPERATURE = "Hot-water PV-T output temperature (degC)"
    HW_PVT_ELECTRICITY_SUPPLIED = "Hot-water PV-T electric energy supplied (kWh)"
    HW_PVT_ELECTRICITY_SUPPLIED_PER_KWP = (
        "Hot-water PV-T electric energy supplied per kWp"
    )
    HW_RENEWABLES_FRACTION = "Renewable hot-water fraction"
    HW_TANK_OUTPUT = "Hot-water tank volume supplied (l)"
    HW_TANK_TEMPERATURE = "Hot-water tank temperature (degC)"
    INSTALLATION_YEAR = "Installation year"
    INVERTER_COST = "Inverter cost ($/kW)"
    INVERTER_SIZE = "Inverter size (kW)"
    KEROSENE_LAMPS = "Kerosene lamps"
    KEROSENE_MITIGATION = "Kerosene mitigation"
    LOAD_ENERGY = "Load energy (kWh)"
    MAXIMUM = "Maximum"
    POWER_CONSUMED_BY_DESALINATION = "Power consumed providing clean water (kWh)"
    POWER_CONSUMED_BY_ELECTRIC_DEVICES = "Power consumed providing electricity (kWh)"
    POWER_CONSUMED_BY_HOT_WATER = "Power consumed providing hot water (kWh)"
    POWER_CONSUMED_BY_THERMAL_DESALINATION = (
        "Power consumed running thermal desalination (kWh)"
    )
    PV_ELECTRICITY_SUPPLIED = "PV energy supplied (kWh)"
    RENEWABLE_CW_USED_DIRECTLY = "Renewable clean water used directly (l)"
    RENEWABLE_ELECTRICITY_SUPPLIED = "Renewables energy supplied (kWh)"
    RENEWABLE_ELECTRICITY_USED_DIRECTLY = "Renewables energy used (kWh)"
    STORAGE_PROFILE = "Storage profile (kWh)"
    TOTAL_CW_CONSUMED = "Total clean water consumed (l)"
    TOTAL_CW_LOAD = "Total clean water demand (l)"
    TOTAL_CW_SUPPLIED = "Total clean water supplied (l)"
    TOTAL_ELECTRICITY_CONSUMED = "Total energy used (kWh)"
    TOTAL_GHGS = "Total ghgs (kgCO2)"
    TOTAL_HW_LOAD = "Total hot-water demand (l)"
    TOTAL_PVT_ELECTRICITY_SUPPLIED = "Total PV-T electric energy supplied (kWh)"
    UNMET_CLEAN_WATER = "Unmet clean water demand (l)"
    UNMET_ELECTRICITY = "Unmet energy (kWh)"
    WATER_SURPLUS = "Water surplus (l)"


def daily_sum_to_monthly_sum(daily_profile: pd.DataFrame) -> pd.DataFrame:
    """
    Converts an day-by-day profile to a sum for each month.

    Inputs:
        - daily_profile:
            Day-by-day profile.

    Outputs:
        - Month-by-month profile of sum of daily values.

    """

    years = int(daily_profile.shape[0] / 365)
    month_start = pd.DataFrame(MONTH_START_DAY)
    month_days = pd.DataFrame([])
    for year in range(0, years):
        month_days = month_days.append(month_start + (year * 365))
    month_days = month_days.append(pd.DataFrame([365 * years]))
    monthly_sum = pd.DataFrame([])
    for month in range(0, month_days.shape[0] - 1):
        start_day = month_days.iloc[month, 0]
        end_day = month_days.iloc[month + 1, 0]
        monthly_sum = monthly_sum.append(
            pd.DataFrame([np.sum(daily_profile.iloc[start_day:end_day, 0])])  # type: ignore
        )
    return monthly_sum


@dataclasses.dataclass
class Demands:
    """
    The demands being modelled.

    .. attribute:: commercial
        Whether commercial demand is being modelled.

    .. attribute:: domestic
        Whether domestic demand is being modelled.

    .. attribute:: public
        Whether public demand is being modelled.

    """

    commercial: bool
    domestic: bool
    public: bool


class DemandType(enum.Enum):
    """
    The type of demand being considered.

    - COMMERCIAL:
        Denotes demand from commercial enterprises.

    - DOMESTIC:
        Denotes domestic demand generated by individuals within the community.

    - PUBLIC:
        Denotes demand from public institutions, e.g., streetlights.

    """

    COMMERCIAL = "commercial"
    DOMESTIC = "domestic"
    PUBLIC = "public"


def dict_to_dataframe(
    input_dict: Union[Dict[int, float], Dict[int, int]], logger: logging.Logger
) -> pd.DataFrame:
    """
    Converts a `dict` to a :class:`pandas.DataFrame`.

    Inputs:
        - input_dict:
            The input `dict` do convert.
        - logger:
            The :class:`logging.Logger` to use for the run.

    Outputs:
        The converted :class:`pandas.DataFrame`.

    """

    if not isinstance(input_dict, dict):
        logger.error(
            "%sThe `dict_to_dataframe` function can only be called with a `dict`.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InternalError(
            f"Misuse of internal helper functions. See {LOGGER_DIRECTORY} for details."
        )

    frame = pd.DataFrame(
        list(input_dict.values()), index=list(input_dict.keys())
    ).sort_index()

    if not isinstance(frame, pd.DataFrame):
        logger.error(
            "%sThe `dict_to_dataframe` function was called but did not successfully "
            "generate a :class:`pandas.DataFrame`.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InternalError(
            f"Failure of internal helper functions. See {LOGGER_DIRECTORY} for details."
        )

    return frame


class DieselMode(enum.Enum):
    """
    The diesel mode being used.

    - BACKUP:
        The diesel generator is used as a 'load-following' backup generator.

    - BACKUP_UNMET:
        The diesel generator is used as a 'load-following' backup generator,
        with unmet energy as the threshold criterion.

    - CYCLE_CHARGING:
        The diesel generator is operated as a dynamic 'cycle-charging' generator.

    - DISABLED:
        No diesel generator is present.

    """

    BACKUP = "backup"
    BACKUP_UNMET = "backup_unmet"
    CYCLE_CHARGING = "cycle_charging"
    DISABLED = "disabled"


@dataclasses.dataclass
class DieselScenario:
    """
    Contains information about the diesel scenario being modelled.

    .. attribute:: backup_threshold
        The backup threshold.

    .. attribute:: mode
        The mode being used for the diesel operation.

    """

    backup_threshold: Optional[float]
    mode: DieselMode

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns a `dict` summarising the :class:`DieselScenario` instance.

        Outputs:
            - A `dict` summarising the information contained within the
              :class:`DieselScenario` instance.

        """

        return {
            "backup_threshold": float(self.backup_threshold)
            if self.backup_threshold is not None
            else str(None),
            "mode": str(self.mode.value),
        }


class DistributionNetwork(enum.Enum):
    """
    The distribution network being used.

    - AC:
        Corresponds to an AC distribution network.

    - DC:
        Corresponds to a DC distribution network.

    """

    AC = "ac"
    DC = "dc"


def get_logger(logger_name: str, verbose: bool = False) -> logging.Logger:
    """
    Set-up and return a logger.

    Inputs:
        - logger_name:
            The name for the logger, which is also used to denote the filename with a
            "<logger_name>.log" format.
        - verbose:
            Whether the log level should be verbose (True) or standard (False).

    Outputs:
        - The logger for the component.

    """

    # Create a logger and logging directory.
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    os.makedirs(LOGGER_DIRECTORY, exist_ok=True)

    # Create a formatter.
    formatter = logging.Formatter(
        "%(asctime)s: %(name)s: %(levelname)s: %(message)s",
        datefmt="%d/%m/%Y %I:%M:%S %p",
    )

    # Create a console handler.
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    # Delete the existing log if there is one already.
    if os.path.isfile(os.path.join(LOGGER_DIRECTORY, f"{logger_name}.log")):
        os.remove(os.path.join(LOGGER_DIRECTORY, f"{logger_name}.log"))

    # Create a file handler.
    file_handler = logging.FileHandler(
        os.path.join(LOGGER_DIRECTORY, f"{logger_name}.log")
    )
    file_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    file_handler.setFormatter(formatter)

    # Add the file handler to the logger.
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def hourly_profile_to_daily_sum(
    hourly_profile: Union[pd.DataFrame, pd.Series]
) -> pd.Series:
    """
    Converts an hour-by-hour profile to a sum for each day.

    Inputs:
        - hourly_profile:
            Hour-by-hour profile.

    Outputs:
        - Day-by-day profile of sum of hourly values.

    """

    days = int(hourly_profile.shape[0] / (24))
    daily_profile = pd.DataFrame(hourly_profile.values.reshape((days, 24)))  # type: ignore
    # return pd.DataFrame(np.sum(daily_profile, 1))
    return daily_profile.sum(axis=1)  # type: ignore


class InputFileError(Exception):
    """Raised when there is an error in an input file."""

    def __init__(self, input_file: str, msg: str) -> None:
        """
        Instantiate a :class:`InputFileError` instance.

        Inputs:
            - input_file:
                The name of the input file which contained the invalid data.
            - msg:
                The error message to append.

        """

        super().__init__(
            f"Error parsing input file '{input_file}', invalid data in file: {msg}"
        )


class InternalError(Exception):
    """Raised when an internal error occurs in CLOVER."""

    def __init__(self, msg: str) -> None:
        """
        Instantiate a :class:`InternalError` instance.

        Inputs:
            - msg:
                The message to append to the internal error.

        """

        super().__init__(f"An error occured internally within CLOVER: {msg}")


@dataclasses.dataclass
class KeyResults:
    """
    Contains the key results from a simulation.

    .. attribute:: average_pv_generation
        The average energy generated by the PV set up per day, measured in kWh/day.

    .. attribute:: blackouts
        The fraction of time for which blackouts occurred.

    .. attribute:: clean_water_blackouts
        The fraction of time for which the clean-water system experienced a blackout.

    .. attribute:: cumulative_pv_generation
        The total electric power that was generated by the PV installation over its
        lifetime, measured in kWh.

    .. attribute:: diesel_times
        The fraction of the time for which the diesel generator was running.

    .. attribute:: grid_daily_hours
        The average number of hours per day for which the grid is available.

    """

    average_daily_cw_demand_covered: Optional[float] = None
    average_daily_cw_pvt_generation: Optional[float] = None
    average_daily_cw_supplied: Optional[float] = None
    average_daily_diesel_energy_supplied: Optional[float] = None
    average_daily_dumped_energy: Optional[float] = None
    average_daily_energy_consumption: Optional[float] = None
    average_daily_grid_energy_supplied: Optional[float] = None
    average_daily_hw_demand_covered: Optional[float] = None
    average_daily_hw_pvt_generation: Optional[float] = None
    average_daily_hw_supplied: Optional[float] = None
    average_daily_pv_energy_supplied: Optional[float] = None
    average_daily_renewables_energy_supplied: Optional[float] = None
    average_daily_renewables_energy_used: Optional[float] = None
    average_daily_stored_energy_supplied: Optional[float] = None
    average_daily_unmet_energy: Optional[float] = None
    average_pv_generation: Optional[float] = None
    average_pvt_electric_generation: Optional[float] = None
    blackouts: Optional[float] = None
    clean_water_blackouts: Optional[float] = None
    cumulative_cw_load: Optional[float] = None
    cumulative_cw_pvt_generation: Optional[float] = None
    cumulative_cw_supplied: Optional[float] = None
    cumulative_hw_load: Optional[float] = None
    cumulative_hw_pvt_generation: Optional[float] = None
    cumulative_hw_supplied: Optional[float] = None
    cumulative_pv_generation: Optional[float] = None
    diesel_times: Optional[float] = None
    grid_daily_hours: Optional[float] = None
    max_buffer_tank_temperature: Optional[float] = None
    max_cw_pvt_output_temperature: Optional[float] = None
    mean_buffer_tank_temperature: Optional[float] = None
    mean_cw_pvt_output_temperature: Optional[float] = None
    min_buffer_tank_temperature: Optional[float] = None
    min_cw_pvt_output_temperature: Optional[float] = None

    def to_dict(  # pylint: disable=too-many-branches, too-many-statements
        self,
    ) -> Dict[str, float]:
        """
        Returns the :class:`KeyResults` information as a `dict` ready for saving.

        Outputs:
            - A `dict` containing the information stored in the :class:`KeyResult`
              instance.

        """

        data_dict: Dict[str, float] = {}

        if self.average_daily_cw_demand_covered is not None:
            data_dict["Average daily clean-water demand covered"] = round(
                self.average_daily_cw_demand_covered, 3
            )
        if self.average_daily_cw_supplied is not None:
            data_dict["Average daily clean water supplied / litres"] = round(
                self.average_daily_cw_supplied, 3
            )
        if self.average_daily_cw_pvt_generation is not None:
            data_dict[
                "Average daily clean-water PV-T electricity supplied / kWh"
            ] = round(self.average_daily_cw_pvt_generation, 3)
        if self.average_daily_diesel_energy_supplied is not None:
            data_dict["Average daily diesel energy supplied / kWh"] = round(
                self.average_daily_diesel_energy_supplied, 3
            )
        if self.average_daily_dumped_energy is not None:
            data_dict["Average daily dumped energy / kWh"] = round(
                self.average_daily_dumped_energy, 3
            )
        if self.average_daily_energy_consumption is not None:
            data_dict["Average daily energy consumption / kWh"] = round(
                self.average_daily_energy_consumption, 3
            )
        if self.average_daily_grid_energy_supplied is not None:
            data_dict["Average daily grid energy supplied / kWh"] = round(
                self.average_daily_grid_energy_supplied, 3
            )
        if self.average_daily_hw_demand_covered is not None:
            data_dict["Average hot-water demand covered"] = round(
                self.average_daily_hw_demand_covered, 3
            )
        if self.average_daily_hw_pvt_generation is not None:
            data_dict[
                "Average daily hot-water PV-T electricity supplied / kWh"
            ] = round(self.average_daily_hw_pvt_generation, 3)
        if self.average_daily_hw_supplied is not None:
            data_dict["Average daily hot water supplied / litres"] = round(
                self.average_daily_hw_supplied, 3
            )
        if self.average_daily_renewables_energy_supplied is not None:
            data_dict["Average daily renewables energy suppied / kWh"] = round(
                self.average_daily_renewables_energy_supplied, 3
            )
        if self.average_daily_renewables_energy_used is not None:
            data_dict["Average daily renewables energy used / kWh"] = round(
                self.average_daily_renewables_energy_used, 3
            )
        if self.average_daily_stored_energy_supplied is not None:
            data_dict["Average daily stored energy supplied / kWh"] = round(
                self.average_daily_stored_energy_supplied, 3
            )
        if self.average_daily_unmet_energy is not None:
            data_dict["Average daily unmet energy / kWh"] = round(
                self.average_daily_unmet_energy, 3
            )
        if self.average_pv_generation is not None:
            data_dict["Average pv generation / kWh/day"] = round(
                self.average_pv_generation, 3
            )
        if self.average_pvt_electric_generation is not None:
            data_dict["Average pv-t electric generation / kWh/day"] = round(
                self.average_pvt_electric_generation, 3
            )
        if self.blackouts is not None:
            data_dict["Blackouts"] = round(self.blackouts, 3)
        if self.clean_water_blackouts is not None:
            data_dict[ColumnHeader.CLEAN_WATER_BLACKOUTS.value] = round(
                self.clean_water_blackouts, 3
            )
        if self.cumulative_cw_load is not None:
            data_dict["Cumulative clean-water load / litres"] = round(
                self.cumulative_cw_load, 3
            )
        if self.cumulative_cw_pvt_generation is not None:
            data_dict["Cumulative clean-water PV-T generation / kWh"] = round(
                self.cumulative_cw_pvt_generation, 3
            )
        if self.cumulative_cw_supplied is not None:
            data_dict["Cumulative clean-water supplied / litres"] = round(
                self.cumulative_cw_supplied, 3
            )
        if self.cumulative_hw_pvt_generation is not None:
            data_dict["Cumulative hot-water PV-T generation / kWh"] = round(
                self.cumulative_hw_pvt_generation, 3
            )
        if self.cumulative_pv_generation is not None:
            data_dict["Cumulative pv generation / kWh/kWp"] = round(
                self.cumulative_pv_generation, 3
            )
        if self.diesel_times is not None:
            data_dict[ColumnHeader.DIESEL_GENERATOR_TIMES.value] = round(
                self.diesel_times, 3
            )
        if self.grid_daily_hours is not None:
            data_dict["Average grid availability / hours/day"] = round(
                self.grid_daily_hours, 3
            )
        if self.max_buffer_tank_temperature is not None:
            data_dict["Maximum buffer-tank temperature / degC"] = round(
                self.max_buffer_tank_temperature, 3
            )
        if self.max_cw_pvt_output_temperature is not None:
            data_dict["Maximum clean-water PV-T output temperature / degC"] = round(
                self.max_cw_pvt_output_temperature, 3
            )
        if self.mean_buffer_tank_temperature is not None:
            data_dict["Mean buffer-tank temperature / degC"] = round(
                self.mean_buffer_tank_temperature, 3
            )
        if self.mean_cw_pvt_output_temperature is not None:
            data_dict["Mean clean-water PV-T output temperature / degC"] = round(
                self.mean_cw_pvt_output_temperature, 3
            )
        if self.min_buffer_tank_temperature is not None:
            data_dict["Minimum buffer-tank temperature / degC"] = round(
                self.min_buffer_tank_temperature, 3
            )
        if self.min_cw_pvt_output_temperature is not None:
            data_dict["Minimum clean-water PV-T output temperature / degC"] = round(
                self.min_cw_pvt_output_temperature, 3
            )

        data_dict = {str(key): float(value) for key, value in data_dict.items()}

        return data_dict


class ProgrammerJudgementFault(Exception):
    """
    Raised when a programmer judgement faul occurs.

    """

    def __init__(self, location: str, message: str) -> None:
        """
        Instantiates a :class:`ProgrammerJudgementFault instance.

        Inputs:
            - location:
                The location within CLOVER where the error has occured.
            - message:
                The more verbose message to display to the end user.

        """

        super().__init__(
            f"Internal programmer judgement fault concerning {location}: {message}"
        )


class RenewableEnergySource(enum.Enum):
    """
    Specfiies the renewable energy sources that can be included in the system.

    - CLEAN_WATER_PVT:
        Denotes PV-T associated with clean-water production.

    - HOT_WATER_PVT:
        Denotes PV-T associated with hot-water production.

    - PV:
        Denotes purely electric PV-T panels.

    """

    CLEAN_WATER_PVT = "clean_water_pv_t"
    HOT_WATER_PVT = "hot_water_pv_t"
    PV = "pv"


class ResourceType(enum.Enum):
    """
    Specifies the type of load being investigated.

    - CLEAN_WATER:
        Represents a clean-water load.

    - DIESEL:
        Represents the resource of diesel.

    - ELECTRIC:
        Represents an electric load.

    - GENERIC_WATER:
        Represents water where the exact specifiction of the water is not needed. E.G.,
        in defining parts of the energy system that work with a fluid as opposed to an
        electrical flow, but which can be used for different types of fluid within the
        system.

    - HEAT:
        Represents raw heat.

    - HOT_CLEAN_WATER:
        Represents water which has either been cleaned within the minigrid or supplied
        as clean to the system and which has been heated.

    - HOT_UNCLEAN_WATER:
        Represents feedwater which has been heated by the minigrid but which has not yet
        been treated.

    - MISC:
        Used internaly to fulfil Pythonic class definitions.

    - UNCLEAN_WATER:
        Represents feedwater which has not yet been warmed or heated by the minigrid.

    """

    CLEAN_WATER = "clean_water"
    DIESEL = "diesel"
    ELECTRIC = "electricity"
    GENERIC_WATER = "generic_water"
    HEAT = "heat"
    HOT_CLEAN_WATER = "hot_water"
    HOT_UNCLEAN_WATER = "hot_feedwater"
    MISC = "misc"
    UNCLEAN_WATER = "feedwater"


# Resource name to resource type mapping:
#   Maps the load name to the load type, used for parsing scenario files.
RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING = {
    "clean_water": ResourceType.CLEAN_WATER,
    "cold_water": ResourceType.CLEAN_WATER,
    "diesel_consumption": ResourceType.DIESEL,
    ELECTRIC_POWER: ResourceType.ELECTRIC,
    "feedwater": ResourceType.UNCLEAN_WATER,
    "heat": ResourceType.HEAT,
    "hot_water": ResourceType.HOT_CLEAN_WATER,
    "hot_untreated_water": ResourceType.HOT_UNCLEAN_WATER,
    "water": ResourceType.GENERIC_WATER,
}


class HTFMode(enum.Enum):
    """
    Specifies the type of material being used as the PV-T HTF.

    - CLOSED_HTF:
        Denotes that a closed (i.e., self-contained) HTF is being used.

    - COLD_WATER_HEATING:
        Denotes that clean water is heated by the PV-T panels directly.

    - FEEDWATER_HEATING:
        Denotes that feedwater is being heated directly.

    """

    CLOSED_HTF = "htf"
    COLD_WATER_HEATING = COLD_WATER
    FEEDWATER_HEATING = ResourceType.UNCLEAN_WATER.value


# HTF name to HTF type mapping:
#   Maps the HTF name to the HTF type, used for parsing desalination scenario files.
HTF_NAME_TO_HTF_TYPE_MAPPING = {
    "cold_water": HTFMode.COLD_WATER_HEATING,
    "feedwater": HTFMode.FEEDWATER_HEATING,
    "htf": HTFMode.CLOSED_HTF,
}


@dataclasses.dataclass
class Location:
    """
    Represents the location being modelled.

    .. attribute:: community_growth_rate
        Fractional growth rate per year.

    .. attribute:: community_size
        Initial number of households in community.

    .. attribute:: country
        The location country.

    .. attribute:: latitude
        Degrees of latitude (North +ve).

    .. attribute:: longitude
        Degrees of longitude (East +ve).

    .. attribute:: max_years
        The maximum number of years of simulation.

    .. attribute:: name
        The name of the location.

    .. attribute:: time_difference
        The time difference, in hours, at the location vs. UTC.

    """

    community_growth_rate: float
    community_size: int
    country: str
    latitude: float
    longitude: float
    max_years: int
    name: str
    time_difference: float

    @classmethod
    def from_dict(cls, location_inputs: Dict[str, Any]) -> Any:
        """
        Creates a :class:`Location` instance based on the inputs provided.

        Inputs:
            - location_inputs:
                The location input information, extracted from the location inputs file.

        Outputs:
            - A :class:`Location` instance based on the input information provided.

        """

        return cls(
            location_inputs["community_growth_rate"],
            location_inputs["community_size"],
            location_inputs["country"],
            location_inputs["latitude"],
            location_inputs["longitude"],
            location_inputs["max_years"],
            location_inputs["location"],
            location_inputs["time_difference"],
        )


def monthly_profile_to_daily_profile(monthly_profile: pd.DataFrame) -> pd.DataFrame:
    """
    Convert hourly profiles to daily sums.

    Function:
        Converts a DataFrame of representative monthly values to a DataFrame of
        representative daily values.

    Inputs:
        - monthly_profile:
            A 24x12 DataFrame of hourly values for each month of the year.

    Outputs:
        - A 24x365 DataFrame of hourly values for each day of the year.

    """

    day_one_profile: pd.DataFrame = pd.DataFrame(np.zeros((24, 1)))
    for hour in range(24):
        day_one_profile.iloc[hour, 0] = 0.5 * (
            monthly_profile.iloc[hour, 0] + monthly_profile.iloc[hour, 11]
        )

    extended_year_profile: pd.DataFrame = pd.DataFrame(np.zeros((24, 14)))
    extended_year_profile.iloc[:, 0] = day_one_profile.iloc[:, 0]

    for month in range(12):
        extended_year_profile.iloc[:, month + 1] = monthly_profile.iloc[:, month]
        extended_year_profile.iloc[:, 13] = day_one_profile.iloc[:, 0]

    # Interpolate the value that falls in the middle of the month.
    daily_profile = {
        hour: scipy.interp(range(365), MONTH_MID_DAY, extended_year_profile.iloc[hour])
        for hour in range(24)
    }

    return pd.DataFrame(list(daily_profile.values()))
    # NOTE:
    #   The following line should be uncommented if older python versions are used in
    #   which dictionaries are unsorted.
    # return pd.DataFrame([entry[1] for entry in sorted(daily_profile.items())])


def monthly_times_to_daily_times(
    monthly_profile: pd.DataFrame, years: int
) -> pd.DataFrame:
    """
    Converts the monthly profiles to daily profiles.

    When dealing with various CLOVER inputs, utilsations or availabilities for a whole
    month need to be converted to daily profiles with similar information. This function
    calculates this.

    Inputs:
        - monthly_profile:
            The monthly profile for the device.
        - years:
            The number of years for the simulation.

    Outputs:
        - The daily profile as a :class:`pandas.DataFrame`.

    Notes:
        Gives a daily utilisation for all devices, even those which are not permitted by
        `devices.yaml`, when called by the load module.
        When called from the water-source module, similarly, a daily grid availability
        profile is generated.

    """

    # Convert the monthly profile to a daily profile.
    yearly_profile = pd.DataFrame.transpose(
        monthly_profile_to_daily_profile(monthly_profile)
    )

    # Concatenate the profile by the number of years such that it repeats.
    concatenated_yearly_profile = pd.concat([yearly_profile] * years)

    return concatenated_yearly_profile


def open_simulation(filename: str) -> pd.DataFrame:
    """
    Opens a previously saved simulation from a .csv file

    Inputs:
        - filename
            Name of the .csv file to be opened including the file extension.

    Outputs:
        - DataFrame of previously performed simulation

    """

    output: pd.DataFrame = pd.read_csv(os.path.join(filename), index_col=0)

    return output


class OperatingMode(enum.Enum):
    """
    Represents the mode of operation.

    - OPTIMISATION:
        Denotes that an optimisation is being run.

    - PROFILE_GENERATION:
        Denotes that only profile-generation is being run.

    - SIMULATION:
        Denotes that a simulation is being run

    """

    OPTIMISATION = "optimisation"
    PROFILE_GENERATION = "profile_generation"
    SIMULATION = "simulation"


class Criterion(enum.Enum):
    """
    The optimisation criteria values that are allowed.

    - BLACKOUTS:
        Denotes the portion of time for which the system experienced a blackout.

    - CLEAN_WATER_BLACKOUTS:
        Denotes the portion of time for which the clean-water system experienced a
        blackout.

    - CUMULATIVE_COST:
        Denotes the cumulative cost incurred.

    - CUMULATIVE_GHGS:
        Denotes the cumulative GHGs emitted.

    - CUMULATIVE_SYSTEM_COST:
        Denotes the cumulative cost of the system.

    - CUMULATIVE_SYSTEM_GHGS:
        Denotes the cumulative GHGs emitted by the system.

    - EMISSIONS_INTENSITY:
        Denotes the intensity of GHG emissions emitted.

    - KEROSENE_COST_MITIGATED:
        The cost of kerosene which was not incurred through use of the system.

    - KEROSENE_DISPLACEMENT:
        The amount of kerosene usage that was displaced.

    - KEROSENE_GHGS_MITIGATED:
        The mitigated GHGs by not consuming kerosene.

    - LCUE:
        Denotes the levilised code of electricity.

    - RENEWABLES_FRACTION:
        The fraction of energy which was emitted renewably.

    - TOTAL_COST:
        The total cost incurred.

    - TOTAL_GHGS:
        The total GHGs emitted.

    - TOTAL_SYSTEM_COST:
        The total cost of the system.

    - TOTAL_SYSTEM_GHGS:
        The total GHGs emitted by the system.

    - UNMET_ENERGY_FRACTION:
        The fraction of energy which went unmet.

    """

    BLACKOUTS = "blackouts"
    CLEAN_WATER_BLACKOUTS = "clean_water_blackouts"
    CUMULATIVE_COST = "cumulative_cost"
    CUMULATIVE_GHGS = "cumulative_ghgs"
    CUMULATIVE_SYSTEM_COST = "cumulative_system_cost"
    CUMULATIVE_SYSTEM_GHGS = "cumulative_system_ghgs"
    EMISSIONS_INTENSITY = "emissions_intensity"
    KEROSENE_COST_MITIGATED = "kerosene_cost_mitigated"
    KEROSENE_DISPLACEMENT = "kerosene_displacement"
    KEROSENE_GHGS_MITIGATED = "kerosene_ghgs_mitigated"
    LCUE = "lcue"
    RENEWABLES_FRACTION = "renewables_fraction"
    TOTAL_COST = "total_cost"
    TOTAL_GHGS = "total_ghgs"
    TOTAL_SYSTEM_COST = "total_system_cost"
    TOTAL_SYSTEM_GHGS = "total_system_ghgs"
    UNMET_ENERGY_FRACTION = "unmet_energy_fraction"

    def __str__(self) -> str:
        """
        Returns a nice-looking `str` representing the :class:`Criterion`.

        Outputs:
            - A nice-looking `str` representing the :class:`Criterion`
              instance.

        """

        return f"Criterion({self.value})"


class PVTMode(enum.Enum):
    """
    The PV-T mode being used.

    - MULTI_PASS:
        HTF passes multiple times through the PV-T collector array before being fed into
        the hot-water tanks.

    """

    MULTI_PASS = "multi-pass"


@dataclasses.dataclass
class PVTScenario:
    """
    Specifies the PV-T scenario being carried out.

    .. attribute:: heats
        The resource which is heated by the PV-T system.

    .. attribute:: htf_heat_capacity
        The capacity of the HTF being used.

    .. attribute:: mass_flow_rate

    """

    heats: HTFMode
    htf_heat_capacity: float
    mass_flow_rate: float


def read_yaml(
    filepath: str, logger: logging.Logger
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Reads a YAML file and returns the contents.


    """

    # Process the new-location data.
    try:
        with open(filepath, "r") as filedata:
            file_contents: Union[Dict[str, Any], List[Dict[str, Any]]] = yaml.safe_load(
                filedata
            )
    except FileNotFoundError:
        logger.error(
            "The file specified, %s, could not be found. "
            "Ensure that you run the new-locations script from the workspace root.",
            filepath,
        )
        raise
    return file_contents


class RenewablesNinjaError(Exception):
    """Raised when there is an error in an input file."""

    def __init__(self) -> None:
        """
        Instantiate a :class:`InputFileError` instance.

        Inputs:
            - input_file:
                The name of the input file which contained the invalid data.
            - msg:
                The error message to append.

        """

        super().__init__(
            "Failed to parse renewables.ninja data. Check that you correctly specified "
            "your API key and that you have not exceeded the hourly quota of 50 "
            "profiles."
        )


@dataclasses.dataclass
class DesalinationScenario:
    """
    Represents the deslination-related scenario being run.

    .. attribute:: clean_water_scenario
        The clean-water scenario.

    .. attribute:: feedwater_supply_temperature
        The supply temperature of the feedwater input to the system.

    .. attribute:: name
        The name of the scenario.

    .. attribute:: pvt_scenario
        The PV-T scenario.

    .. attribute:: unclean_water_sources
        A `set` of `str` giving the unclean water sources.

    """

    clean_water_scenario: CleanWaterScenario
    feedwater_supply_temperature: float
    name: str
    pvt_scenario: PVTScenario
    unclean_water_sources: List[str]

    @classmethod
    def from_dict(
        cls, desalination_inputs: Dict[str, Any], logger: logging.Logger
    ) -> Any:
        """
        Returns a :class:`DesalinationScenario` instance based on the input data.

        Inputs:
            - desalination_inputs:
                The input data extracted from the scenario file.
            - logger:
                The :class:`logging.Logger` to use for the run.

        Outputs:
            - A :class:`DesalinationScenario` instance based on the input data provided.

        """

        try:
            clean_water_mode = CleanWaterMode(
                desalination_inputs[ResourceType.CLEAN_WATER.value][MODE]
            )
        except ValueError:
            logger.error(
                "%sInvalid clean-water mode specified: %s%s",
                BColours.fail,
                desalination_inputs[ResourceType.CLEAN_WATER.value][MODE],
                BColours.endc,
            )
            raise InputFileError(
                "desalination scenario",
                "Invalid clean-water mode specified in clean-water scenario.",
            ) from None
        except KeyError:
            logger.error(
                "%sMissing clean-water information in deslination scenario file.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "desalination scenario", "Missing clean-water scenario information."
            ) from None

        clean_water_scenario: CleanWaterScenario = CleanWaterScenario(
            desalination_inputs[ResourceType.CLEAN_WATER.value][CONVENTIONAL_SOURCES]
            if CONVENTIONAL_SOURCES
            in desalination_inputs[ResourceType.CLEAN_WATER.value]
            else [],
            clean_water_mode,
            list(desalination_inputs[ResourceType.CLEAN_WATER.value]["sources"]),
        )

        try:
            pvt_scenario: PVTScenario = PVTScenario(
                HTFMode(desalination_inputs[PVT_SCENARIO]["heats"]),
                desalination_inputs[PVT_SCENARIO]["htf_heat_capacity"]
                if "htf_heat_capacity" in desalination_inputs[PVT_SCENARIO]
                else HEAT_CAPACITY_OF_WATER,
                desalination_inputs[PVT_SCENARIO]["mass_flow_rate"],
            )
        except ValueError:
            logger.error(
                "%sInvalid HTF mode specified: %s%s",
                BColours.fail,
                desalination_inputs[PVT_SCENARIO]["heats"],
                BColours.endc,
            )
            raise InputFileError(
                "desalination scenario", "Invalid HTF mode specified in PV-T scenario."
            ) from None
        except KeyError:
            logger.error(
                "%sMissing PV-T information in deslination scenario file.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "desalination scenario", "Missing PV-T scenario information."
            ) from None

        try:
            feedwater_supply_temperature = desalination_inputs[
                ResourceType.UNCLEAN_WATER.value
            ][SUPPLY_TEMPERATURE]
        except KeyError:
            logger.error(
                "%sMissing feedwater supply temperature information in desalination "
                "inputs.%s",
                BColours.fail,
                BColours.endc,
            )

        try:
            unclean_water_sources = list(
                desalination_inputs[ResourceType.UNCLEAN_WATER.value]["sources"]
            )
        except KeyError:
            logger.error(
                "%sFeedwater sources not specified in desalinaiton inputs file.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "desalination scenario", "Feedwater sources not specified correctly."
            ) from None

        return cls(
            clean_water_scenario,
            feedwater_supply_temperature,
            desalination_inputs[NAME],
            pvt_scenario,
            unclean_water_sources,
        )


@dataclasses.dataclass
class HotWaterScenario:
    """
    Represents the hot-water-related scenario being run.

    .. attribute:: auxiliary_heater
        The type of auxiliary heater assigned to the system, or `None` if there is no
        auxiliary heater present, stored as a :class:`AuxiliaryHeaterType` instance.

    .. attribute:: cold_water_supply
        How input cold water is sourced for the hot-water system.

    .. attribute:: cold_water_supply_temperature
        The supply temperature of the cold-water input to the system.

    .. attribute:: conventional_sources
        A `list` of conventional sources.

    .. attribute:: demand_temperature
        The temperature, in degrees Celcius, at which hot water should be supplied to the end user.

    .. attribute:: name
        The name of the hot-water scenario.

    .. attribute:: pvt_scenario
        The PV-T scenario.

    """

    auxiliary_heater: Optional[AuxiliaryHeaterType]
    cold_water_supply: ColdWaterSupply
    cold_water_supply_temperature: float
    conventional_sources: List[str]
    demand_temperature: float
    name: str
    pvt_scenario: PVTScenario

    @classmethod
    def from_dict(cls, hot_water_inputs: Dict[str, Any], logger: logging.Logger) -> Any:
        """
        Returns a :class:`DesalinationScenario` instance based on the input data.

        Inputs:
            - hot_water_inputs:
                The input data extracted from the hot-water scenario file.
            - logger:
                The :class:`logging.Logger` to use for the run.

        Outputs:
            - A :class:`HotWaterScenario` instance based on the input data provided.

        """

        try:
            auxiliary_heater = AUXILIARY_HEATER_NAME_TO_TYPE_MAPPING[
                hot_water_inputs[ResourceType.HOT_CLEAN_WATER.value]["auxiliary_heater"]
            ]
        except ValueError:
            logger.error(
                "%sInvalid auxiliary heater mode specified: %s. Valid options are %s."
                "%s",
                BColours.fail,
                hot_water_inputs[ResourceType.HOT_CLEAN_WATER.value][
                    "auxiliary_heater"
                ],
                ", ".join(f"'{e.value}'" for e in AuxiliaryHeaterType),
                BColours.endc,
            )
            raise InputFileError(
                "hot-water scenario",
                "Invalid auxiliary heater mode specified in hot-water scenario.",
            ) from None
        except KeyError:
            logger.error(
                "%sMissing auxiliary-heater mode in hot-water scenario file.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "hot-water scenario", "Missing auxiliary-heater mode information."
            ) from None

        try:
            cold_water_supply = ColdWaterSupply(hot_water_inputs[COLD_WATER]["supply"])
        except ValueError:
            logger.error(
                "%sInvalid cold-water supply specified: %s%s",
                BColours.fail,
                hot_water_inputs[COLD_WATER]["supply"],
                BColours.endc,
            )
            raise InputFileError(
                "hot-water scenario",
                "Invalid clean-water mode specified in hot-water scenario.",
            ) from None
        except KeyError:
            logger.error(
                "%sMissing cold-water supply information in hot-water scenario file.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "hot-water scenario", "Missing cold-water source information."
            ) from None

        try:
            cold_water_supply_temperature: float = hot_water_inputs[COLD_WATER][
                SUPPLY_TEMPERATURE
            ]
        except KeyError:
            logger.error(
                "%sMissing cold-water supply temperature information in hot-water "
                "inputs.%s",
                BColours.fail,
                BColours.endc,
            )

        try:
            conventional_sources: List[str] = hot_water_inputs[
                ResourceType.HOT_CLEAN_WATER.value
            ][CONVENTIONAL_SOURCES]
        except KeyError:
            logger.info("Missing hot-water conventional sources in hot-water inputs.")
            logger.debug(
                "Hot-water input information: %s", json.dumps(hot_water_inputs)
            )
            logger.info("Continuing with no conventional hot-water sources.")
            conventional_sources = []

        try:
            demand_temperature = hot_water_inputs[ResourceType.HOT_CLEAN_WATER.value][
                "demand_temperature"
            ]
        except ValueError:
            logger.error(
                "%sInvalid hot-water demand temperature specified: %s%s",
                BColours.fail,
                hot_water_inputs[ResourceType.HOT_CLEAN_WATER.value][
                    "demand_temperature"
                ],
                BColours.endc,
            )
            raise InputFileError(
                "hot-water scenario",
                "Invalid hot-water demand temperature specified in hot-water scenario.",
            ) from None
        except KeyError:
            logger.error(
                "%sMissing hot-water demand temperature in hot-water scenario file.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "hot-water scenario", "Missing demand temperature."
            ) from None

        try:
            pvt_scenario: PVTScenario = PVTScenario(
                HTFMode(hot_water_inputs[PVT_SCENARIO]["heats"]),
                hot_water_inputs[PVT_SCENARIO]["htf_heat_capacity"]
                if "htf_heat_capacity" in hot_water_inputs[PVT_SCENARIO]
                else HEAT_CAPACITY_OF_WATER,
                hot_water_inputs[PVT_SCENARIO]["mass_flow_rate"],
            )
        except ValueError:
            logger.error(
                "%sInvalid HTF mode specified: %s%s",
                BColours.fail,
                hot_water_inputs[PVT_SCENARIO]["heats"],
                BColours.endc,
            )
            raise InputFileError(
                "hot-water scenario", "Invalid HTF mode specified in PV-T scenario."
            ) from None
        except KeyError:
            logger.error(
                "%sMissing PV-T information in hot-water scenario file.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "hot-water scenario", "Missing PV-T scenario information."
            ) from None

        return cls(
            auxiliary_heater,
            cold_water_supply,
            cold_water_supply_temperature,
            conventional_sources,
            demand_temperature,
            hot_water_inputs[NAME],
            pvt_scenario,
        )


@dataclasses.dataclass
class Scenario:
    """
    Represents a scenario being run.

    .. attribute:: battery
        Whether battery storage is being included in the scenario.

    .. attribute:: demands
        The demands being modelled.

    .. attribute:: desalination_scenario
        The :class:`DesalinationScenario` for the run.

    .. attribute:: diesel_scenario
        The diesel scenario being modelled.

    .. attribute:: distribution_network
        The distribution-network type being modelled.

    .. attribute:: grid
        Whether the grid is being included in the scenario.

    .. attribute:: grid_type
        The type of grid being modelled, i.e., whether the grid is full, etc. These
        options are written in the grid inputs file as headers.

    .. attribute:: hot_water_scneario
        The :class:`HotWaterScenario` for the run.

    .. attribute:: name
        The name of the scenario.

    .. attribute:: resource_types
        The load types being modelled.

    .. attribute:: prioritise_self_generation
        Whether self generation should be prioritised.

    .. attribute:: pv
        Whether PV is being included in the scenario.

    .. attribute:: pv_d
        Whether PV-D is being included in the scenario.

    .. attribute:: pv_t
        Whether PV-T is being included in the scenario.

    """

    battery: bool
    demands: Demands
    desalination_scenario: Optional[DesalinationScenario]
    diesel_scenario: DieselScenario
    distribution_network: DistributionNetwork
    fixed_inverter_size: Union[float, bool]
    grid: bool
    grid_type: str
    hot_water_scenario: Optional[HotWaterScenario]
    name: str
    resource_types: Set[ResourceType]
    prioritise_self_generation: bool
    pv: bool
    pv_d: bool
    pv_t: bool

    @classmethod
    def from_dict(
        cls,
        desalination_scenarios: Optional[List[DesalinationScenario]],
        hot_water_scenarios: Optional[List[HotWaterScenario]],
        logger: logging.Logger,
        scenario_inputs: Dict[str, Any],
    ) -> Any:
        """
        Returns a :class:`Scenario` instance based on the input data.

        Inputs:
            - desalination_scenarios:
                The list of :class:`DesalinationScenario` to use for the run.
            - hot_water_scenarios:
                The list of :class:`HotWaterScenario` to use for the run.
            - logger:
                The :class:`logging.Logger` to use for the run.
            - scenario_inputs:
                The input data extracted from the scenario file.

        Outputs:
            - A :class:`Scenario` instance based on the input data provided.

        """

        demands = Demands(
            scenario_inputs["demands"][DemandType.COMMERCIAL.value],
            scenario_inputs["demands"][DemandType.DOMESTIC.value],
            scenario_inputs["demands"][DemandType.PUBLIC.value],
        )

        diesel_scenario = DieselScenario(
            scenario_inputs["diesel"]["backup"]["threshold"]
            if scenario_inputs["diesel"][MODE]
            in (DieselMode.BACKUP.value, DieselMode.BACKUP_UNMET.value)
            else None,
            DieselMode(scenario_inputs["diesel"][MODE]),
        )

        distribution_network = DistributionNetwork(
            scenario_inputs["distribution_network"]
        )

        resource_types = {
            ResourceType(RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING[resource_name])
            for resource_name in scenario_inputs["resource_types"]
        }

        # Determine the desalination and hot-water scenarios to use for the run.
        if desalination_scenarios is not None:
            if DESALINATION_SCENARIO in scenario_inputs:
                try:
                    desalination_scenario: Optional[DesalinationScenario] = [
                        entry
                        for entry in desalination_scenarios
                        if entry.name == scenario_inputs[DESALINATION_SCENARIO]
                    ][0]
                except IndexError:
                    logger.error(
                        "%sError creating scenario from inputs. Deslination scenario '%s' "
                        "could not be found in scenario '%s'.%s",
                        BColours.fail,
                        scenario_inputs[DESALINATION_SCENARIO],
                        scenario_inputs[NAME],
                        BColours.endc,
                    )
            else:
                try:
                    desalination_scenario = [
                        entry
                        for entry in desalination_scenarios
                        if entry.name == DEFAULT_SCENARIO
                    ][0]
                except IndexError:
                    logger.error(
                        "%sError creating scenario from inputs. Deslination scenario '%s' "
                        "could not be found in scenario '%s'.%s",
                        BColours.fail,
                        scenario_inputs[DESALINATION_SCENARIO],
                        scenario_inputs[NAME],
                        BColours.endc,
                    )
        else:
            desalination_scenario = None

        if hot_water_scenarios is not None:
            if HOT_WATER_SCENARIO in scenario_inputs:
                try:
                    hot_water_scenario: Optional[HotWaterScenario] = [
                        entry
                        for entry in hot_water_scenarios
                        if entry.name == scenario_inputs[HOT_WATER_SCENARIO]
                    ][0]
                except IndexError:
                    logger.error(
                        "%sError creating scenario from inputs. Hot-water scenario '%s' "
                        "could not be found in scenario '%s'.%s",
                        BColours.fail,
                        scenario_inputs[HOT_WATER_SCENARIO],
                        scenario_inputs[NAME],
                        BColours.endc,
                    )
                    raise
            else:
                try:
                    hot_water_scenario = [
                        entry
                        for entry in hot_water_scenarios
                        if entry.name == DEFAULT_SCENARIO
                    ][0]
                except IndexError:
                    logger.error(
                        "%sError creating scenario from inputs. Hot-water scenario '%s' "
                        "could not be found in scenario '%s'.%s",
                        BColours.fail,
                        scenario_inputs[HOT_WATER_SCENARIO],
                        scenario_inputs[NAME],
                        BColours.endc,
                    )
                    raise
        else:
            hot_water_scenario = None

        return cls(
            scenario_inputs["battery"],
            demands,
            desalination_scenario,
            diesel_scenario,
            distribution_network,
            scenario_inputs.get("fixed_inverter_size", False),
            scenario_inputs["grid"],
            scenario_inputs["grid_type"],
            hot_water_scenario,
            scenario_inputs[NAME],
            resource_types,
            scenario_inputs["prioritise_self_generation"],
            scenario_inputs["pv"],
            scenario_inputs.get("pv_d", False),
            scenario_inputs.get("pv_t", False),
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns a `dict` summarising the :class:`Scenario` instance.

        Outputs:
            - A `dict` summarising the information contained within the
              :class:`Scenario` instance.

        """

        scenario_dict = {
            "battery": self.battery,
            "demands": {
                DemandType.COMMERCIAL.value: self.demands.commercial,
                DemandType.DOMESTIC.value: self.demands.domestic,
                DemandType.PUBLIC.value: self.demands.public,
            },
            "diesel_scenario": self.diesel_scenario.to_dict(),
            "distribution_network": str(self.distribution_network.value),
            "grid": self.grid,
            "grid_type": self.grid_type,
            "name": self.name,
            "resource_types": [str(e.value) for e in self.resource_types],
            "prioritise_self_generation": self.prioritise_self_generation,
            "pv": self.pv,
        }

        return scenario_dict


@dataclasses.dataclass
class Simulation:
    """
    Represents a simulation being run.

    .. attribute:: end_year
        The end year for the simulation.

    .. attribute:: start_year
        The start year for the simulation.

    """

    end_year: int
    start_year: int

    def __hash__(self) -> int:
        """
        Return a unique hash of the :class:`Simulation` instance.

        Outputs:
            - A unique hash identifying the :class:`Simulation` instance.

        """

        return hash(
            (
                (self.start_year + self.end_year)
                * (self.start_year + self.end_year + 1)
                / 2
            )
            + self.end_year
        )

    @classmethod
    def from_dict(cls, simulation_inputs: Dict[str, Any]) -> Any:
        """
        Returns a :class:`Simulation` instance based on the input data.

        Inputs:
            - simulation_inputs:
                The input data extracted from the simulation file.

        Outputs:
            - A :class:`Simulation` instance based on the input data provided.

        """

        return cls(simulation_inputs["end_year"], simulation_inputs["start_year"])


@dataclasses.dataclass
class SystemDetails:
    """
    Contains system-detail information.

    .. attribute:: diesel_capacity
        The diesel capacity of the system.

    .. attribute:: end_year
        The end year of the simulation.

    .. attribute:: final_converter_sizes:
        A mapping between the name of the various converters associated with the system
        and the final size of each that remained at the end of the simiulation.

    .. attribute:: final_cw_pvt_size
        The final clean-water pv-t size of the system.

    .. attribute:: final_hw_pvt_size
        The final hot-water pv-t size of the system.

    .. attribute:: final_num_buffer_tanks
        The final number of buffer tanks installed in the system.

    .. attribute:: final_num_clean_water_tanks
        The final number of clean-water tanks installed in the system.

    .. attribute:: final_num_hot_water_tanks
        The final number of hot-water tanks installed in the system.

    .. attribute:: final_pv_size
        The final pv size of the system.

    .. attribute:: final_storage_size
        The final storage size of the system.

    .. attribute:: initial_converter_sizes:
        A mapping between the name of the various converters associated with the system
        and the initial size of each that was installed.

    .. attribute:: initial_cw_pvt_size
        The initial clean-water pv-t size of the system.

    .. attribute:: initial_hw_pvt_size
        The initial hot-water pv-t size of the system.

    .. attribute:: initial_num_buffer_tanks
        The initial number of buffer tanks installed in the system.

    .. attribute:: initial_num_clean_water_tanks
        The initial number of clean-water tanks installed in the system.

    .. attribute:: initial_num_hot_water_tanks
        The initial number of hot-water tanks installed in the system.

    .. attribute:: initial_pv_size
        The initial pv size of the system.

    .. attribute:: initial_storage_size
        The initial storage size of the system.

    .. attribute:: required_feedwater_sources
        The `list` of feedwater sources which were required to supply the desalination
        plant(s) associated with the system.

    .. attribute:: start_year
        The start year of the system.

    .. attribute:: file_information
        Information on the input files used for the run.

    """

    diesel_capacity: float = 0
    end_year: int = 0
    final_converter_sizes: Optional[Dict[str, int]] = None
    final_cw_pvt_size: Optional[float] = 0
    final_hw_pvt_size: Optional[float] = 0
    final_num_buffer_tanks: Optional[int] = 0
    final_num_clean_water_tanks: Optional[int] = 0
    final_num_hot_water_tanks: Optional[int] = 0
    final_pv_size: float = 0
    final_storage_size: float = 0
    initial_converter_sizes: Optional[Dict[str, int]] = None
    initial_cw_pvt_size: Optional[float] = 0
    initial_hw_pvt_size: Optional[float] = 0
    initial_num_buffer_tanks: Optional[int] = 0
    initial_num_clean_water_tanks: Optional[int] = 0
    initial_num_hot_water_tanks: Optional[int] = 0
    initial_pv_size: float = 0
    initial_storage_size: float = 0
    required_feedwater_sources: Optional[List[str]] = None
    start_year: int = 0
    file_information: Optional[Dict[str, str]] = None

    def to_dict(
        self,
    ) -> Dict[
        str, Optional[Union[int, float, str, Dict[str, str]]]
    ]:  # pylint: disable=too-many-branches
        """
        Returns a `dict` containing information the :class:`SystemDetails`' information.

        Outputs:
            A `dict` containing the information stored within the :class:`SystemDetails`
            instance.

        """

        system_details_as_dict: Dict[
            str, Optional[Union[int, float, str, Dict[str, str]]]
        ] = {
            "diesel_capacity": round(self.diesel_capacity, 3),
            "end_year": round(self.end_year, 3),
            "final_pv_size": round(self.final_pv_size, 3),
            "final_storage_size": round(self.final_storage_size, 3),
            "initial_pv_size": round(self.initial_pv_size, 3),
            "initial_storage_size": round(self.initial_storage_size, 3),
            "input_files": self.file_information,
            "start_year": round(self.start_year, 3),
        }

        if self.initial_converter_sizes is not None:
            system_details_as_dict.update(
                {
                    f"intial_num_{key}": value
                    for key, value in self.initial_converter_sizes.items()
                }
            )
        if self.final_converter_sizes is not None:
            system_details_as_dict.update(
                {
                    f"intial_num_{key}": value
                    for key, value in self.final_converter_sizes.items()
                }
            )
        if self.initial_num_buffer_tanks is not None:
            system_details_as_dict["initial_num_buffer_tanks"] = round(
                self.initial_num_buffer_tanks, 3
            )
        if self.final_num_buffer_tanks is not None:
            system_details_as_dict["final_num_buffer_tanks"] = round(
                self.final_num_buffer_tanks, 3
            )
        if self.initial_num_clean_water_tanks is not None:
            system_details_as_dict["initial_num_clean_water_tanks"] = round(
                self.initial_num_clean_water_tanks, 3
            )
        if self.final_num_clean_water_tanks is not None:
            system_details_as_dict["final_num_clean_water_tanks"] = round(
                self.final_num_clean_water_tanks, 3
            )
        if self.initial_num_hot_water_tanks is not None:
            system_details_as_dict["initial_num_hot_water_tanks"] = round(
                self.initial_num_hot_water_tanks, 3
            )
        if self.final_num_hot_water_tanks is not None:
            system_details_as_dict["final_num_hot_water_tanks"] = round(
                self.final_num_hot_water_tanks, 3
            )
        if self.initial_cw_pvt_size is not None:
            system_details_as_dict["initial_cw_pvt_size"] = round(
                self.initial_cw_pvt_size, 3
            )
        if self.final_cw_pvt_size is not None:
            system_details_as_dict["final_cw_pvt_size"] = round(
                self.final_cw_pvt_size, 3
            )
        if self.initial_hw_pvt_size is not None:
            system_details_as_dict["initial_hw_pvt_size"] = round(
                self.initial_hw_pvt_size, 3
            )
        if self.final_hw_pvt_size is not None:
            system_details_as_dict["final_hw_pvt_size"] = round(
                self.final_hw_pvt_size, 3
            )
        if self.required_feedwater_sources is not None:
            system_details_as_dict["required_feedwater_sources"] = ", ".join(
                self.required_feedwater_sources
            )

        return system_details_as_dict

    @property
    def initial_pvt_size(self) -> float:
        """
        Returns the total size of the PV-T system initially installed.

        Outputs:
            - The total size of the PV-T system initially installed.

        """

        return (
            self.initial_cw_pvt_size if self.initial_cw_pvt_size is not None else 0
        ) + (self.initial_hw_pvt_size if self.initial_hw_pvt_size is not None else 0)

    @property
    def final_pvt_size(self) -> float:
        """
        Returns the total size of the PV-T system installed at the end of the iteration.

        Outputs:
            - The total size of the PV-T system installed at the end of the simulation.

        """

        return (self.final_cw_pvt_size if self.final_cw_pvt_size is not None else 0) + (
            self.final_hw_pvt_size if self.final_hw_pvt_size is not None else 0
        )


@dataclasses.dataclass
class CumulativeResults:
    """
    Contains cumulative results about the system.

    .. attribute:: clean_water
        The cumulative clean water produced, measured in litres.

    .. attribute:: cost
        The cumulative cost, measured in USD.

    .. attribute:: discounted_energy
        The discounted energy produced, measured in kWh.

    .. attribute:: energy
        The energy produced, measured in kWh.

    .. attribute:: ghgs
        The total green-house gasses emitted by the system, mesaured in kgCO2eq.

    .. attribute:: system_cost
        The cumulative cost of the system, measured in USD.

    .. attribute:: system_ghgs
        The total system-related GHGs, mesaured in kgCO2eq.

    """

    clean_water: Optional[float] = None
    cost: float = 0
    discounted_energy: float = 0
    energy: float = 0
    ghgs: float = 0
    system_cost: float = 0
    system_ghgs: float = 0
    waste_produced: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns a dictionary representation of the :class:`CumulativeResults` instance.

        Outputs:
            A `dict` representing the :class:`CumulativeResults` for storage purposes.

        """

        cumulative_results = {
            "cumulative_cost": self.cost,
            "cumulative_discounted_energy": self.discounted_energy,
            "cumulative_energy": self.energy,
            "cumulative_ghgs": self.ghgs,
            "cumulative_system_cost": self.system_cost,
            "cumulative_system_ghgs": self.system_ghgs,
        }

        if self.clean_water is not None:
            cumulative_results["clean_water"] = self.clean_water
        if self.waste_produced is not None:
            for key, value in self.waste_produced.items():
                cumulative_results[f"cumulative_{key}_waste"] = value

        return cumulative_results


@dataclasses.dataclass
class EnvironmentalAppraisal:
    """
    Contains environmental-appraisal information.

    .. attribute:: diesel_ghgs
        The diesel-fuel GHGs emitted.

    .. attribute:: grid_ghgs
        The grid GHGs emitted.

    .. attribute:: kerosene_ghgs
        The GHGs emitted by burning kerosene.

    .. attribute:: kerosene_ghgs_mitigated
        The GHGs mitigated by not burning kerosene lamps.

    .. attribute:: new_connection_ghgs
        The GHGs emitted by installing new connections.

    .. attribute:: new_equipment_ghgs
        The GHGs emitted by the new equipment installed.

    .. attribute:: om_ghgs
        The O&M GHGs emitted by the system.

    .. attribute:: total_ghgs
        The total GHGs emitted.

    .. attribute:: total_system_ghgs
        The total system-related GHGs.

    """

    diesel_ghgs: float = 0
    grid_ghgs: float = 0
    kerosene_ghgs: float = 0
    kerosene_ghgs_mitigated: float = 0
    new_connection_ghgs: float = 0
    new_equipment_ghgs: float = 0
    om_ghgs: float = 0
    total_ghgs: float = 0
    total_system_ghgs: float = 0

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns a dictionary representation of the :class:`EnvironmentalAppraisal` instance.

        Outputs:
            A `dict` representing the :class:`EnvironmentalAppraisal` for storage purposes.

        """

        return {
            "diesel_ghgs": self.diesel_ghgs,
            "grid_ghgs": self.grid_ghgs,
            "kerosene_ghgs": self.kerosene_ghgs,
            "kerosene_ghgs_mitigated": self.kerosene_ghgs_mitigated,
            "new_connection_ghgs": self.new_connection_ghgs,
            "new_equipment_ghgs": self.new_equipment_ghgs,
            "om_ghgs": self.om_ghgs,
            "total_ghgs": self.total_ghgs,
            "total_system_ghgs": self.total_system_ghgs,
        }


@dataclasses.dataclass
class FinancialAppraisal:
    """
    Contains financial-appraisal information.

    .. attribute:: diesel_cost
        The cost of diesel fuel used, measured in USD.

    .. attribute:: grid_cost
        The cost of grid energy used, measured in USD.

    .. attribute:: kerosene_cost
        The cost of kerosene used, measured in USD.

    .. attribute:: kerosene_cost_mitigated
        The value of the kerosene which was not used, measured in USD.

    .. attribute:: new_connection_cost
        The cost of connecting a new household to the grid, measured in USD

    .. attribute:: new_equipment_cost
        The cost of the new equipment purchased in this optimisation cycle, measured in
        USD

    .. attribute:: om_cost
        The O&M cost, measured in USD.

    .. attribute:: total_cost
        The total cost of the energy system and fuel etc. used, measured in USD

    .. attribute:: total_system_cost
        The total cost of the energy system, measured in USD

    """

    diesel_cost: float = 0
    grid_cost: float = 0
    kerosene_cost: float = 0
    kerosene_cost_mitigated: float = 0
    new_connection_cost: float = 0
    new_equipment_cost: float = 0
    om_cost: float = 0
    total_cost: float = 0
    total_system_cost: float = 0

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns a dictionary representation of the :class:`FinancialAppraisal` instance.

        Outputs:
            A `dict` representing the :class:`FinancialAppraisal` for storage purposes.

        """

        return {
            "diesel_cost": self.diesel_cost,
            "grid_cost": self.grid_cost,
            "kerosene_cost": self.kerosene_cost,
            "kerosene_cost_mitigated": self.kerosene_cost_mitigated,
            "new_connection_cost": self.new_connection_cost,
            "new_equipment_cost": self.new_equipment_cost,
            "om_cost": self.om_cost,
            "total_cost": self.total_cost,
            "total_system_cost": self.total_system_cost,
        }


@dataclasses.dataclass
class TechnicalAppraisal:
    """
    Contains financial-appraisal information.

    .. attribute:: blackouts
        The proportion of time for which the system suffered a blackout, defined between
        0 (none of the time) and 1 (all of the time).

    .. attribute:: clean_water_blackouts
        The portion of time for which the clean-water system experienced a blackout.

    .. attribute:: diesel_energy
        The total amount of energy which was provided by the diesel generators, measured
        in kWh.

    .. attribute:: diesel_fuel_usage
        The amount of diesel fuel usage, measured in litres.

    .. attribute:: discounted_energy
        The total discounted energy consumed, measured in kWh.

    .. attribute:: grid_energy
        The total energy which was supplied by the grid, measured in kWh.

    .. attribute:: kerosene_displacement
        The proportion of kerosene which was displacement by the minigrid, defined
        between 0 (all of the kerosene that would have been used was used) and 1 (none
        of the kerosene that would have been used was used and all was mitigated by the
        minigrid).

    .. attribute:: new_connection_cost
        The cost of connecting a new household to the grid, measured in USD.

    .. attribute:: pv_energy
        The total amount of energy that was supplied by the PV system, measured in kWh.

    .. attribute:: renewable_energy
        The total amount of renewable energy that was supplied by all the renewable
        sources, measured in kWh.

    .. attribute:: renewable_energy_fraction
        The fraction of energy that was supplied through renewables, defined between 0
        (no renewable energy supplied) and 1 (all energy supplied through renewables).

    .. attribute:: storage_energy
        The total energy which was supplied by the storage system, measured in kWh.

    .. attribute:: total_clean_water
        The total clean water which was produced by the system, measured in litres.

    .. attribute:: total_energy
        The total energy which was used in the system, measured in kWh.

    .. attribute:: unmet_energy
        The total energy which went unmet, measured in kWh.

    .. attribute:: unmet_energy_fraction
        The fraction of energy demand which went unmet, defined between 0 (no unmet
        energy) and 1 (all energy went unmet).

    """

    blackouts: float = 0
    clean_water_blackouts: Optional[float] = 0
    diesel_energy: float = 0
    diesel_fuel_usage: float = 0
    discounted_energy: float = 0
    grid_energy: float = 0
    kerosene_displacement: float = 0
    pv_energy: float = 0
    pvt_energy: Optional[float] = 0
    renewable_energy: float = 0
    renewable_energy_fraction: float = 0
    storage_energy: float = 0
    total_clean_water: float = 0
    total_energy: float = 0
    unmet_energy: float = 0
    unmet_energy_fraction: float = 0

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns a dictionary representation of the :class:`TechnicalAppraisal` instance.

        Outputs:
            A `dict` representing the :class:`TechnicalAppraisal` for storage purposes.

        """

        technical_appraisal_dict = {
            "blackouts": self.blackouts,
            "diesel_energy": self.diesel_energy,
            "diesel_fuel_usage": self.diesel_fuel_usage,
            "discounted_energy": self.discounted_energy,
            "grid_energy": self.grid_energy,
            "kerosene_displacement": self.kerosene_displacement,
            "renewable_energy": self.renewable_energy,
            "renewable_energy_fraction": self.renewable_energy_fraction,
            "storage_energy": self.storage_energy,
            "total_clean_water": self.total_clean_water,
            "total_energy": self.total_energy,
            "unmet_energy": self.unmet_energy,
            "unmet_energy_fraction": self.unmet_energy_fraction,
        }

        if self.clean_water_blackouts is not None:
            technical_appraisal_dict[
                "clean_water_blackouts"
            ] = self.clean_water_blackouts

        technical_appraisal_dict = {
            str(key): float(value) for key, value in technical_appraisal_dict.items()
        }

        return technical_appraisal_dict


@dataclasses.dataclass
class SystemAppraisal:
    """
    Contains information appraising the system.

    .. attribute:: cumulative_results
        The cumulative results of the systems that are being appraised.

    .. attribute:: environmental_appraisal
        A :class:`EnvironmentalAppraisal` of the system.

    .. attribute:: financial_appraisal
        A :class:`FinancialAppraisal` of the system.

    .. attribute:: system_details
        The details of the system.

    .. attribute:: technical_appraisal
        A :class:`TechnicalAppraisal` of the system.

    .. attribute:: criteria
        A mapping between the :class:`Criterion` instances that could be
        relevant and their associated values for the system being appraised.

    """

    cumulative_results: CumulativeResults
    environmental_appraisal: EnvironmentalAppraisal
    financial_appraisal: FinancialAppraisal
    system_details: SystemDetails
    technical_appraisal: TechnicalAppraisal
    criteria: Optional[Dict[Criterion, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns a dictionary representation of the :class:`SystemAppraisal` instance.

        Outputs:
            A `dict` representing the :class:`SystemAppraisal` for storage purposes.

        """

        return {
            "cumulative_results": self.cumulative_results.to_dict(),
            "environmental_appraisal": self.environmental_appraisal.to_dict(),
            "financial_appraisal": self.financial_appraisal.to_dict(),
            "system_details": self.system_details.to_dict(),
            "technical_appraisal": self.technical_appraisal.to_dict(),
            "criteria": {str(key.value): value for key, value in self.criteria.items()}
            if self.criteria is not None
            else "None",
        }


def save_simulation(
    disable_tqdm: bool,
    key_results: KeyResults,
    logger: logging.Logger,
    output: str,
    output_directory: str,
    simulation: pd.DataFrame,
    simulation_number: int,
    system_appraisal: Optional[SystemAppraisal],
    system_details: SystemDetails,
) -> None:
    """
    Saves simulation outputs to a .csv file

    Inputs:
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - key_results:
            The key results from the run.
        - logger:
            The logger to use for the run.
        - output:
            The output name to use when labelling the simulation: this is the name given
            to the output folder in which the system files are saved.
        - output_directory:
            The directory into which the files should be saved.
        - simulation:
            DataFrame output from Energy_System().simulation(...).
        - simulation_number:
            The number of the simulation being run.
        - system_appraisal:
            An optional appraisal of the system.
        - system_details:
            Information about the run to save.

    """

    # Remove the file extension if appropriate.
    if output.endswith(".csv"):
        output = output.rsplit(".csv", 1)[0]

    # Create the output directory.
    simulation_output_folder = os.path.join(output_directory, output)
    os.makedirs(simulation_output_folder, exist_ok=True)

    # Add the key results to the system data.
    simulation_details_dict: Dict[str, Any] = system_details.to_dict()
    simulation_details_dict["analysis_results"] = key_results.to_dict()

    # Add the appraisal results to the system data if relevant.
    if system_appraisal is not None:
        simulation_details_dict["system_appraisal"] = system_appraisal.to_dict()

    # Save the system data.
    simulation_details_filepath = os.path.join(
        simulation_output_folder, "info_file.json"
    )
    if os.path.isfile(simulation_details_filepath):
        with open(simulation_details_filepath, "r") as f:
            existing_simulation_details = json.load(f)
    else:
        existing_simulation_details = {}

    # Update the system info with the new simulation information.
    existing_simulation_details[
        f"simulation_{simulation_number}"
    ] = simulation_details_dict

    with tqdm(
        total=2,
        desc="saving output files",
        disable=disable_tqdm,
        leave=False,
        unit="file",
    ) as pbar:
        # Save the simulation data in a CSV file.
        logger.info("Saving simulation output.")

        # Save the system data.
        logger.info("Saving simulation details.")
        with open(simulation_details_filepath, "w") as f:
            json.dump(existing_simulation_details, f, indent=4)
        logger.info(
            "Simulation details successfully saved to %s.", simulation_details_filepath
        )
        pbar.update(1)

        with open(
            os.path.join(
                simulation_output_folder, f"simulation_output_{simulation_number}.csv"
            ),
            "w",
        ) as f:
            simulation.to_csv(
                f,  # type: ignore
                line_terminator="\n",
            )
        logger.info("Simulation successfully saved to %s.", simulation_output_folder)
        pbar.update(1)
