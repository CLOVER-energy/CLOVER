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
import pandas as pd  # type: ignore  # pylint: disable=import-error
import scipy  # type: ignore  # pylint: disable=import-error
import yaml  # type: ignore  # pylint: disable=import-error

from tqdm import tqdm  # type: ignore  # pylint: disable=import-error

__all__ = (
    "BColours",
    "CleanWaterMode",
    "CUT_OFF_TIME",
    "daily_sum_to_monthly_sum",
    "DemandType",
    "DieselMode",
    "DONE",
    "ELECTRIC_POWER",
    "FAILED",
    "get_logger",
    "HEAT_CAPACITY_OF_WATER",
    "hourly_profile_to_daily_sum",
    "InputFileError",
    "InternalError",
    "KEROSENE_DEVICE_NAME",
    "KeyResults",
    "ResourceType",
    "LOCATIONS_FOLDER_NAME",
    "LOGGER_DIRECTORY",
    "monthly_profile_to_daily_profile",
    "open_simulation",
    "OperatingMode",
    "Criterion",
    "OptimisationParameters",
    "read_yaml",
    "RenewablesNinjaError",
    "save_simulation",
    "Scenario",
    "Simulation",
    "SystemAppraisal",
    "SystemDetails",
    "Criterion",
)


# Cut off time:
#   The time up and to which information about the load of each device will be returned.
CUT_OFF_TIME: int = 72  # [hours]

# Done message:
#   The message to display when a task was successful.
DONE: str = "[   DONE   ]"

# Electric power:
#   Keyword used for parsing electric power.
ELECTRIC_POWER: str = "electric_power"

# Failed message:
#   The message to display when a task has failed.
FAILED: str = "[  FAILED  ]"

# Heat capacity of water:
#   The heat capacity of water, measured in Joules per kilogram Kelvin.
HEAT_CAPACITY_OF_WATER: int = 4182

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
MAX = "max"

# Min:
#   Keyword used when parsing information about the minimum system size to consider in
#   optimisations.
MIN = "min"

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

# Number of iterations:
#   The number of iterations to consider in the optimisation.
NUMBER_OF_ITERATIONS: str = "number_of_iterations"

# Step:
#   Keyword used when parsing information about the system size step to consider in
#   optimisations.
STEP = "step"


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
        The clean-water demand will only be fulfiled using minigrid power as backup.

    - PRIORITISE:
        The clean-water demand will be fulfiled always.

    """

    BACKUP = "backup"
    PRIORITISE = "prioritise"


@dataclasses.dataclass
class CleanWaterScenario:
    """
    Specifies the clean-water scenario being carried out.

    .. attribute:: mode
        The clean water mode being modelled.

    .. attribute:: supply_temperature
        The temperature, in degrees Celcius, of the water supply to the temperature.

    """

    mode: CleanWaterMode
    supply_temperature: float


def daily_sum_to_monthly_sum(daily_profile):
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
        start_day = month_days.iloc[month][0]
        end_day = month_days.iloc[month + 1][0]
        monthly_sum = monthly_sum.append(
            pd.DataFrame([np.sum(daily_profile[start_day:end_day])[0]])
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


class DieselMode(enum.Enum):
    """
    The diesel mode being used.

    - BACKUP:
        The diesel generator is used as a 'load-following' backup generator.

    - CYCLE_CHARGING:
        The diesel generator is operated as a dynamic 'cycle-charging' generator.

    """

    BACKUP = "backup"
    CYCLE_CHARGING = "cycle_charging"


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


def get_logger(logger_name: str) -> logging.Logger:
    """
    Set-up and return a logger.

    Inputs:
        - logger_name:
            The name for the logger, which is also used to denote the filename with a
            "<logger_name>.log" format.

    Outputs:
        - The logger for the component.

    """

    # Create a logger and logging directory.
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    os.makedirs(LOGGER_DIRECTORY, exist_ok=True)

    # Create a formatter.
    formatter = logging.Formatter(
        "%(asctime)s: %(name)s: %(levelname)s: %(message)s",
        datefmt="%d/%m/%Y %I:%M:%S %p",
    )

    # Create a console handler.
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)
    console_handler.setFormatter(formatter)

    # Delete the existing log if there is one already.
    if os.path.isfile(os.path.join(LOGGER_DIRECTORY, f"{logger_name}.log")):
        os.remove(os.path.join(LOGGER_DIRECTORY, f"{logger_name}.log"))

    # Create a file handler.
    file_handler = logging.FileHandler(
        os.path.join(LOGGER_DIRECTORY, f"{logger_name}.log")
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # Add the file handler to the logger.
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def hourly_profile_to_daily_sum(hourly_profile: pd.DataFrame):
    """
    Converts an hour-by-hour profile to a sum for each day.

    Inputs:
        - hourly_profile:
            Hour-by-hour profile.

    Outputs:
        - Day-by-day profile of sum of hourly values.

    """

    days = int(hourly_profile.shape[0] / (24))
    daily_profile = pd.DataFrame(hourly_profile.values.reshape((days, 24)))
    # return pd.DataFrame(np.sum(daily_profile, 1))
    return daily_profile.sum(axis=1)


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

    average_daily_diesel_energy_supplied: Optional[float] = None
    average_daily_dumped_energy: Optional[float] = None
    average_daily_energy_consumption: Optional[float] = None
    average_daily_grid_energy_supplied: Optional[float] = None
    average_daily_pv_energy_supplied: Optional[float] = None
    average_daily_renewables_energy_supplied: Optional[float] = None
    average_daily_renewables_energy_used: Optional[float] = None
    average_daily_stored_energy_supplied: Optional[float] = None
    average_daily_unmet_energy: Optional[float] = None
    average_pv_generation: Optional[float] = None
    average_pvt_electric_generation: Optional[float] = None
    blackouts: Optional[float] = None
    clean_water_blackouts: Optional[float] = None
    cumulative_pv_generation: Optional[float] = None
    diesel_times: Optional[float] = None
    grid_daily_hours: Optional[float] = None

    def to_dict(self) -> Dict[str, float]:
        """
        Returns the :class:`KeyResults` information as a `dict` ready for saving.

        Outputs:
            - A `dict` containing the information stored in the :class:`KeyResult`
              instance.

        """

        data_dict: Dict[str, float] = {}

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
            data_dict["Clean water blackouts"] = round(self.clean_water_blackouts, 3)
        if self.cumulative_pv_generation is not None:
            data_dict["Cumulative pv generation / kWh"] = round(
                self.cumulative_pv_generation, 3
            )
        if self.diesel_times is not None:
            data_dict["Diesel times"] = round(self.diesel_times, 3)
        if self.grid_daily_hours is not None:
            data_dict["Average grid availability / hours/day"] = round(
                self.grid_daily_hours, 3
            )

        return data_dict


class ResourceType(enum.Enum):
    """
    Specifies the type of load being investigated.

    - CLEAN_WATER:
        Represents a clean-water load.

    - ELECTRIC:
        Represents an electric load.

    """

    CLEAN_WATER = "clean_water"
    ELECTRIC = "electricity"
    HOT_CLEAN_WATER = "hot_water"
    HOT_UNCLEAN_WATER = "hot_groundwater"
    UNCLEAN_WATER = "groundwater"


# Load name to load type mapping:
#   Maps the load name to the load type, used for parsing scenario files.
RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING = {
    "clean_water": ResourceType.CLEAN_WATER,
    ELECTRIC_POWER: ResourceType.ELECTRIC,
    "hot_water": ResourceType.HOT_CLEAN_WATER,
    "hot_untreated_water": ResourceType.HOT_UNCLEAN_WATER,
    "groundwater": ResourceType.UNCLEAN_WATER,
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
    def from_dict(cls, location_inputs: Dict[Union[int, str], Any]) -> Any:
        """
        Creates a :class:`Location` instance based on the inputs provided.

        Inputs:
            - location_inputs:
                The location input information, extracted form the location inputs file.

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

    day_one_profile = pd.DataFrame(np.zeros((24, 1)))
    for hour in range(24):
        day_one_profile[0][hour] = 0.5 * (  # type: ignore
            monthly_profile[0][hour] + monthly_profile[11][hour]  # type: ignore
        )

    extended_year_profile = pd.DataFrame(np.zeros((24, 14)))
    extended_year_profile[0] = day_one_profile[0]  # type: ignore

    for month in range(12):
        extended_year_profile[month + 1] = monthly_profile[month]  # type: ignore
        extended_year_profile[13] = day_one_profile[0]  # type: ignore

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


def open_simulation(filename: str):
    """
    Opens a previously saved simulation from a .csv file

    Inputs:
        - filename
            Name of the .csv file to be opened including the file extension.

    Outputs:
        - DataFrame of previously performed simulation

    """

    output = pd.read_csv(os.path.join(filename), index_col=0)
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


@dataclasses.dataclass
class OptimisationComponent(enum.Enum):
    """
    Contains information about the components which are variable in an optimisation.

    - CLEAN_WATER_TANKS:
        Denotes the number of clean-water tanks in the system.

    - PV_SIZE:
        Denotes the size of the PV system, measured in PV units.

    - PVT_SIZE:
        Denotes the size of the PV-T system, measured in PV-T units.

    - STORAGE_SIZE:
        Denotes the size of the storage system, measured in storage units, i.e.,
        batteries.

    """

    CLEAN_WATER_TANKS = "clean_water_tanks"
    PV_SIZE = "pv_size"
    PVT_SIZE = "pvt_size"
    STORAGE_SIZE = "storage_size"


@dataclasses.dataclass
class OptimisationParameters:
    """
    Parameters that define the scope of the optimisation.

    .. attribute:: clean_water_tanks_max
        The maximum size of clean-water tank capacity to be considered, used only as an
        initial value, measured in number of tanks.

    .. attribute:: clean_water_tanks_min
        The minimum size of clean-water tank capacity to be considered, used only as an
        initial value, measured in number of tanks.

    .. attribute:: clean_water_tanks_step
        The optimisation resolution for the clean water tanks, measured in clean-water
        tanks.

    .. attribute:: iteration_length
        The length of each iteration to be run.

    .. attribute:: number_of_iterations
        The number of iterations to run.

    .. attribute:: pv_size_max
        The maximum size of PV capacity to be considered, used only as an initial value,
        measured in PV units.

    .. attribute:: pv_size_min
        The minimum size of PV capacity to be considered, measured in PV units.

    .. attribute:: pv_size_step
        The optimisation resolution for the PV size, measured in PV units.

    .. attribute:: pvt_size_max
        The maximum size of PV capacity to be considered, used only as an initial value,
        measured in units of PV-T.

    .. attribute:: pvt_size_min
        The minimum size of PV capacity to be considered, measured in units of PV-T.

    .. attribute:: pvt_size_step
        The optimisation resolution for the PV-T size, measured in units of PV-T.

    .. attribute:: storage_size_max
        The maximum size of storage capacity to be considered, used only as an initial
        value, measured in batteries.

    .. attribute:: storage_size_min
        The minimum size of storage capacity to be considered, measured in batteries.

    .. attribute:: storage_size_step
        The optimisation restolution for the storage size, measured in batteries.

    """

    clean_water_tanks_max: Optional[int]
    clean_water_tanks_min: Optional[int]
    clean_water_tanks_step: Optional[int]
    iteration_length: int
    number_of_iterations: int
    pv_size_max: float
    pv_size_min: float
    pv_size_step: float
    pvt_size_max: Optional[float]
    pvt_size_min: Optional[float]
    pvt_size_step: Optional[float]
    storage_size_max: float
    storage_size_min: float
    storage_size_step: float

    @classmethod
    def from_dict(cls, optimisation_inputs: Dict[Union[int, str], Any]) -> Any:
        """
        Returns a :class:`OptimisationParameters` instance based on the input info.

        Outputs:
            - A :class:`OptimisationParameters` instanced based on the information
            passed in.

        """

        return cls(
            int(optimisation_inputs[OptimisationComponent.CLEAN_WATER_TANKS.value][MAX])
            if OptimisationComponent.CLEAN_WATER_TANKS.value in optimisation_inputs
            else None,
            int(optimisation_inputs[OptimisationComponent.CLEAN_WATER_TANKS.value][MIN])
            if OptimisationComponent.CLEAN_WATER_TANKS.value in optimisation_inputs
            else None,
            int(
                optimisation_inputs[OptimisationComponent.CLEAN_WATER_TANKS.value][STEP]
            )
            if OptimisationComponent.CLEAN_WATER_TANKS.value in optimisation_inputs
            else None,
            optimisation_inputs[ITERATION_LENGTH],
            optimisation_inputs[NUMBER_OF_ITERATIONS],
            optimisation_inputs[OptimisationComponent.PV_SIZE.value][MAX],
            optimisation_inputs[OptimisationComponent.PV_SIZE.value][MIN],
            optimisation_inputs[OptimisationComponent.PV_SIZE.value][STEP],
            optimisation_inputs[OptimisationComponent.PVT_SIZE.value][MAX]
            if OptimisationComponent.PVT_SIZE.value in optimisation_inputs
            else None,
            optimisation_inputs[OptimisationComponent.PVT_SIZE.value][MIN]
            if OptimisationComponent.PVT_SIZE.value in optimisation_inputs
            else None,
            optimisation_inputs[OptimisationComponent.PVT_SIZE.value][STEP]
            if OptimisationComponent.PVT_SIZE.value in optimisation_inputs
            else None,
            optimisation_inputs[OptimisationComponent.STORAGE_SIZE.value][MAX],
            optimisation_inputs[OptimisationComponent.STORAGE_SIZE.value][MIN],
            optimisation_inputs[OptimisationComponent.STORAGE_SIZE.value][STEP],
        )

    @property
    def scenario_length(self) -> int:
        """
        Calculates and returns the scenario length for the optimisation.

        Outputs:
            - The scenario length for the optimisation.

        """

        return self.iteration_length * self.number_of_iterations

    def to_dict(self) -> Dict[str, Union[int, float]]:
        """
        Returns a `dict` representation of the :class:`OptimisationParameters` instance.

        Outputs:
            A `dict` containing the :class:`OptimisationParameters` information.

        """

        optimisation_parameters_dict = {
            "clean_water_tanks_max": int(self.clean_water_tanks_max)
            if self.clean_water_tanks_max is not None
            else None,
            "clean_water_tanks_min": int(self.clean_water_tanks_min)
            if self.clean_water_tanks_min is not None
            else None,
            "clean_water_tanks_step": int(self.clean_water_tanks_step)
            if self.clean_water_tanks_step is not None
            else None,
            ITERATION_LENGTH: round(self.iteration_length, 3),
            NUMBER_OF_ITERATIONS: round(self.number_of_iterations, 3),
            "pv_size_max": round(self.pv_size_max, 3),
            "pv_size_min": round(self.pv_size_min, 3),
            "pv_size_step": round(self.pv_size_step, 3),
            "pvt_size_max": int(self.pvt_size_max)
            if self.pvt_size_max is not None
            else None,
            "pvt_size_min": int(self.pvt_size_min)
            if self.pvt_size_min is not None
            else None,
            "pvt_size_step": int(self.pvt_size_step)
            if self.pvt_size_step is not None
            else None,
            "storage_size_max": round(self.storage_size_max, 3),
            "storage_size_min": round(self.storage_size_min, 3),
            "storage_size_step": round(self.storage_size_step, 3),
        }

        return {
            key: value
            for key, value in optimisation_parameters_dict.items()
            if value is not None
        }


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

    .. attribute:: cycles_per_hour
        The number of times, per hour, that the HTF cycles through the PV-T collector
        system.

    """

    cycles_per_hour: float
    mode: PVTMode


def read_yaml(
    filepath: str, logger: logging.Logger
) -> Union[Dict[Union[int, str], Any], List[Dict[Union[int, str], Any]],]:
    """
    Reads a YAML file and returns the contents.


    """

    # Process the new-location data.
    try:
        with open(filepath, "r") as filedata:
            file_contents = yaml.safe_load(filedata)
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
class Scenario:
    """
    Represents a scenario being run.

    .. attribute:: battery
        Whether battery storage is being included in the scenario.

    .. attribute:: clean_water_scenario
        The clean-water scenario.

    .. attribute:: demands
        The demands being modelled.

    .. attribute:: diesel_scenario
        The diesel scenario being modelled.

    .. attribute:: distribution_network
        The distribution-network type being modelled.

    .. attribute:: grid
        Whether the grid is being included in the scenario.

    .. attribute:: grid_type
        The type of grid being modelled, i.e., whether the grid is full, etc. These
        options are written in the grid inputs file as headers.

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

    .. attribute:: pv_t_scenario
        The PV-T scenario.

    .. attribute:: water_supply_temperature
        The supply temperature of the water input to the system.

    """

    battery: bool
    clean_water_scenario: Optional[CleanWaterScenario]
    demands: Demands
    diesel_scenario: DieselScenario
    distribution_network: DistributionNetwork
    grid: bool
    grid_type: str
    resource_types: Set[ResourceType]
    prioritise_self_generation: bool
    pv: bool
    pv_d: bool
    pv_t: bool
    pv_t_scenario: Optional[PVTScenario]

    @classmethod
    def from_dict(cls, scenario_inputs: Dict[Union[int, str], Any]) -> Any:
        """
        Returns a :class:`Scenario` instance based on the input data.

        Inputs:
            - scenario_inputs:
                The input data extracted from the scenario file.

        Outputs:
            - A :class:`Scenario` instance based on the input data provided.

        """

        clean_water_mode = (
            CleanWaterMode(scenario_inputs[ResourceType.CLEAN_WATER.value]["mode"])
            if ResourceType.CLEAN_WATER.value in scenario_inputs
            else None
        )

        clean_water_scenario = CleanWaterScenario(
            clean_water_mode,
            scenario_inputs[ResourceType.CLEAN_WATER.value]["supply_temperature"],
        )

        demands = Demands(
            scenario_inputs["demands"][DemandType.COMMERCIAL.value],
            scenario_inputs["demands"][DemandType.DOMESTIC.value],
            scenario_inputs["demands"][DemandType.PUBLIC.value],
        )

        diesel_scenario = DieselScenario(
            scenario_inputs["diesel"]["backup"]["threshold"]
            if scenario_inputs["diesel"]["mode"] == DieselMode.BACKUP.value
            else None,
            DieselMode(scenario_inputs["diesel"]["mode"]),
        )

        distribution_network = DistributionNetwork(
            scenario_inputs["distribution_network"]
        )

        if "pv_t" in scenario_inputs:
            pv_t_scenario: Optional[PVTScenario] = PVTScenario(
                scenario_inputs["pv_t"]["cycles_per_hour"],
                PVTMode(scenario_inputs["pv_t"]["mode"])
            )
        else:
            pv_t_scenario = None

        resource_types = {
            ResourceType(RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING[resource_name])
            for resource_name in scenario_inputs["resource_types"]
        }

        return cls(
            scenario_inputs["battery"],
            clean_water_scenario,
            demands,
            diesel_scenario,
            distribution_network,
            scenario_inputs["grid"],
            scenario_inputs["grid_type"],
            resource_types,
            scenario_inputs["prioritise_self_generation"],
            scenario_inputs["pv"],
            scenario_inputs["pv_d"] if "pv_d" in scenario_inputs else False,
            scenario_inputs["pv_t"] if "pv_t" in scenario_inputs else False,
            pv_t_scenario
        )


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
    def from_dict(cls, simulation_inputs: Dict[Union[int, str], Any]) -> Any:
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

    .. attribute:: final_num_clean_water_tanks
        The final number of clean-water tanks installed in the system.

    .. attribute:: final_pv_size
        The final pv size of the system.

    .. attribute:: final_pvt_size
        The final pv-t size of the system.

    .. attribute:: final_storage_size
        The final storage size of the system.

    .. attribute:: initial_num_clean_water_tanks
        The initial number of clean-water tanks installed in the system.

    .. attribute:: initial_pv_size
        The initial pv size of the system.

    .. attribute:: initial_pvt_size
        The initial pv-t size of the system.

    .. attribute:: initial_storage_size
        The initial storage size of the system.

    .. attribute:: start_year
        The start year of the system.

    .. attribute:: file_information
        Information on the input files used for the run.

    """

    diesel_capacity: float = 0
    end_year: int = 0
    final_num_clean_water_tanks: Optional[float] = 0
    final_pv_size: float = 0
    final_pvt_size: Optional[float] = 0
    final_storage_size: float = 0
    initial_num_clean_water_tanks: Optional[float] = 0
    initial_pv_size: float = 0
    initial_pvt_size: Optional[float] = 0
    initial_storage_size: float = 0
    start_year: int = 0
    file_information: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Optional[Union[int, float, str, Dict[str, str]]]]:
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

        if self.initial_num_clean_water_tanks is not None:
            system_details_as_dict["initial_num_clean_water_tanks"] = round(
                self.initial_num_clean_water_tanks, 3
            )
        if self.final_num_clean_water_tanks is not None:
            system_details_as_dict["final_num_clean_water_tanks"] = round(
                self.final_num_clean_water_tanks, 3
            )
        if self.initial_pvt_size is not None:
            system_details_as_dict["initial_pvt_size"] = round(self.initial_pvt_size, 3)
        if self.final_pvt_size is not None:
            system_details_as_dict["final_pvt_size"] = round(self.final_pvt_size, 3)

        return system_details_as_dict


@dataclasses.dataclass
class CumulativeResults:
    """
    Contains cumulative results about the system.

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

    cost: float = 0
    discounted_energy: float = 0
    energy: float = 0
    ghgs: float = 0
    system_cost: float = 0
    system_ghgs: float = 0

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns a dictionary representation of the :class:`CumulativeResults` instance.

        Outputs:
            A `dict` representing the :class:`CumulativeResults` for storage purposes.

        """

        return {
            "cumulative_cost": self.cost,
            "cumulative_discounted_energy": self.discounted_energy,
            "cumulative_energy": self.energy,
            "cumulative_ghgs": self.ghgs,
            "cumulative_system_cost": self.system_cost,
            "cumulative_system_ghgs": self.system_ghgs,
        }


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
    total_energy: float = 0
    unmet_energy: float = 0
    unmet_energy_fraction: float = 0

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns a dictionary representation of the :class:`TechnicalAppraisal` instance.

        Outputs:
            A `dict` representing the :class:`TechnicalAppraisal` for storage purposes.

        """

        return {
            "blackouts": self.blackouts,
            "clean_water_blackouts": self.clean_water_blackouts,
            "diesel_energy": self.diesel_energy,
            "diesel_fuel_usage": self.diesel_fuel_usage,
            "discounted_energy": self.discounted_energy,
            "grid_energy": self.grid_energy,
            "kerosene_displacement": self.kerosene_displacement,
            "renewable_energy": self.renewable_energy,
            "renewable_energy_fraction": self.renewable_energy_fraction,
            "storage_energy": self.storage_energy,
            "total_energy": self.total_energy,
            "unmet_energy": self.unmet_energy,
            "unmet_energy_fraction": self.unmet_energy_fraction,
        }


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


def save_optimisation(
    logger: logging.Logger,
    optimisation_inputs: OptimisationParameters,
    optimisation_number: int,
    output: str,
    output_directory: str,
    system_appraisals: List[SystemAppraisal],
):
    """
    Saves simulation outputs to a .csv file

    Inputs:
        - logger:
            The logger to use for the run.
        - optimisation_inputs:
            The optimisation input information.
        - optimisation_number:
            The number of the optimisation that has just been carried out.
        - output:
            The output name to use when labelling the simulation: this is the name given
            to the output folder in which the system files are saved.
        - output_directory:
            The directory into which the files should be saved.
        - system_appraisals:
            A `list` of the :class:`SystemAppraisal` instances which specify the
            optimum systems at each time step.

    """

    # Remove the file extension if appropriate.
    if output.endswith(".json"):
        output = output.rsplit(".json", 1)[0]

    # Create the output directory.
    optimisation_output_folder = os.path.join(output_directory, output)
    os.makedirs(optimisation_output_folder, exist_ok=True)

    # Add the key results to the system data.
    system_appraisals_dict = {
        f"iteration_{index}": appraisal.to_dict()
        for index, appraisal in enumerate(system_appraisals)
    }

    # Add the optimisation parameter information.
    output_dict = {
        "optimisation_inputs": optimisation_inputs.to_dict(),
        "system_appraisals": system_appraisals_dict,
    }

    with tqdm(total=1, desc="saving output files", leave=False, unit="file") as pbar:
        # Save the optimisation data.
        logger.info("Saving optimisation output.")
        with open(
            os.path.join(
                optimisation_output_folder,
                f"optimisation_output_{optimisation_number}.json",
            ),
            "w",
        ) as f:
            json.dump(output_dict, f, indent=4)
        logger.info(
            "Optimisation successfully saved to %s.", optimisation_output_folder
        )
        pbar.update(1)


def save_simulation(
    key_results: KeyResults,
    logger: logging.Logger,
    output: str,
    output_directory: str,
    simulation: pd.DataFrame,
    simulation_number: int,
    system_details: SystemDetails,
):
    """
    Saves simulation outputs to a .csv file

    Inputs:
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

    with tqdm(total=2, desc="saving output files", leave=False, unit="file") as pbar:
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
            simulation.to_csv(f, line_terminator="\n")  # type: ignore
        logger.info("Simulation successfully saved to %s.", simulation_output_folder)
        pbar.update(1)
