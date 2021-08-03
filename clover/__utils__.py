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
import datetime
import enum
import logging
import os

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import scipy  # type: ignore
import yaml


__all__ = (
    "BColours",
    "daily_sum_to_monthly_sum",
    "DemandType",
    "get_logger",
    "hourly_profile_to_daily_sum",
    "KEROSENE_DEVICE_NAME",
    "LOCATIONS_FOLDER_NAME",
    "LOGGER_DIRECTORY",
    "monthly_profile_to_daily_profile",
    "open_simulation",
    "OperatingMode",
    "read_yaml",
    "save_simulation",
    "Scenario",
    "Simulation",
)


# Kerosene device name:
#   The name used to denote the kerosene device.
KEROSENE_DEVICE_NAME = "kerosene"

# Locations folder name:
#   The name of the locations folder.
LOCATIONS_FOLDER_NAME = "locations"

# Logger directory:
#   The directory in which to save logs.
LOGGER_DIRECTORY = "logs"

# Month mid-day:
#   The "day" in the year that falls in the middle of the month.
MONTH_MID_DAY = [0, 14, 45, 72, 104, 133, 164, 194, 225, 256, 286, 317, 344, 364]

# Month start day:
#   The "day" in the year that falls at the start of each month.
MONTH_START_DAY = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]


@dataclasses.dataclass
class BColours:
    """
    Contains various colours used for pretty-printing out to the command-line on stdout.

    .. attribute:: FAIL
        Used for a failure message.

    .. attributes:: WARNING, OKBLUE
        Various colours used.

    .. attribute:: ENDC
        Used to reset the colour of the terminal output.

    .. attribute:: BOLD, UNDERLINE
        Used to format the text.

    """

    fail = "\033[91m"
    warning = "\033[93m"
    okblue = "\033[94m"
    endc = "\033[0m"
    bolc = "\033[1m"
    underline = "\033[4m"


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

    """

    BACKUP = "backup"


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
    return daily_profile.sum()


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


# class ProgressBarQueue(queue.Queue):
#     """
#     A child of :class:`queue.Queue` used for tracking progress.

#     The progress bar is designed to hold messages containing tuples of the format:
#         - Thread identifier,
#         - Current stage index,
#         - Number of stages until the task is completed.

#     """

#     # Private Attributes:
#     # .. attribute:: _previous_message_length
#     #   Used to keep track of the previous message length to determine the number of
#     #   line return characters needed.
#     #

#     def __init__(self) -> None:
#         """
#         Instantiate a progress queue.

#         """

#         self._previous_message_length = 1

#         super().__init__()

#     def _message_from_entry(self, entry: Tuple[str, str, str]) -> str:
#         """
#         Generates a message for the queue based on a queue entry.

#         Inputs:
#             - entry:
#                 An entry in the queue, usually a Tuple.

#         """

#         # Generate integer-based data off the entries.
#         current_marker = int(entry[1])
#         final_marker = int(entry[2])
#         percentage: int = int(100 * current_marker / final_marker)

#         # Return the entry as a nicely-formatted progress bar.
#         return "\r{}{}: [{}{}] {}{}%\r".format(
#             entry[0],
#             " " * (15 - len(str(entry[0]))),
#             "#" * int(56 * entry[1] / entry[2]),
#             "-" * int(56 * (1 - entry[1] / entry[2])),
#             " " * (3 - len(str(percentage))),
#             percentage,
#         )

#     def get_message(self) -> Optional[str]:
#         """
#         Returns the message to display out to the console.

#         """

#         message_queue = self.get()

#         # If the message queue is empty, then return `None`.
#         if len(message_queue) == 0:
#             return None

#         status_message = "{}".format("\033[A" * (self._previous_message_length + 2))

#         # If the queue contains multiple entries, then report back all of these.
#         if isinstance(message_queue, list):
#             status_message = "\n".join(
#                 [self._message_from_entry(entry) for entry in message_queue]
#             )
#             self._previous_message_length = len(message_queue)

#         # If there is only one message in the queue, then print this message.
#         else:
#             status_message = self._message_from_entry(message_queue)
#             self._previous_message_length = 1

#         # Update the message length in lines for use next time.

#         return status_message


# class ProgressBarThread(threading.Thread):
#     """
#     A :class:`threading.Thread` child used for monitoring CLOVER's progress.

#     """

#     # Private Attributes:
#     # .. attribute:: progress_queue
#     #   A :class:`ProgressBarQueue` instance used for tracking the various messages
#     #   that report the progress of running threads.
#     #

#     def __init__(self, progress_queue: ProgressBarQueue) -> None:
#         """
#         Instantiate a :class:`ProgressBarThread` instance.

#         Inputs:
#             - progress_queue:
#                 The queue to use for tracking the progress of the various threads.

#         """

#         self._progress_queue = progress_queue

#         super().__init__()

#     def run(self) -> None:
#         """
#         Run the thread.

#         """

#         message = ""

#         # Run until there are no messages to report, then exit.
#         while message is not None:
#             message = self._progress_queue.get_message()
#             print(f"{message}", end="\r")
#             time.sleep(1)


def read_yaml(filepath: str, logger: logging.Logger) -> Dict[Any, Any]:
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


def save_simulation(
    filename: Optional[str],
    logger: logging.Logger,
    output_directory: str,
    simulation: pd.DataFrame,
    system_details: Dict[str, Any],
):
    """
    Saves simulation outputs to a .csv file

    Inputs:
        - filename:
            The .csv file name to use (defaults to timestamp).
        - logger:
            The logger to use for the run.
        - output_directory:
            The directory into which the files should be saved.
        - simulation:
            DataFrame output from Energy_System().simulation(...).
        - system_details:
            Information about the run to save.

    """

    # If the filename is not provided, then generate it.
    if filename is None:
        filename = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

    # Add the file extension if appropriate.
    filepath = os.path.join(output_directory, filename)
    if not filepath.endswith(".csv"):
        filepath += ".csv"

    # Save the simulation data in a CSV file.
    logger.info("Saving simulation output.")
    with open(filepath, "w") as f:
        simulation.to_csv(f)  # type: ignore
    logger.info("Simulation successfully saved to %s.", filepath)
    print(f"Simulation saved to {filepath}.")

    # Save the system data.
    simulation_details_filepath = os.path.join(
        output_directory, filename + "_info.yaml"
    )
    logger.info("Saving simulation details.")
    with open(simulation_details_filepath, "w") as f:
        yaml.dump(system_details, f, indent=4)
    logger.info(
        "Simulation details successfully saved to %s.", simulation_details_filepath
    )


@dataclasses.dataclass
class Scenario:
    """
    Represents a scenario being run.

    .. attribute:: battery
        Whether battery storage is being included in the scenario.

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

    .. attribute:: prioritise_self_generation
        Whether self generation should be prioritised.

    .. attribute:: pv
        Whether PV is being included in the scenario.

    """

    battery: bool
    demands: Demands
    diesel_scenario: DieselScenario
    distribution_network: DistributionNetwork
    grid: bool
    grid_type: str
    prioritise_self_generation: bool
    pv: bool

    @classmethod
    def from_dict(cls, scenario_inputs: Dict[str, Any]) -> Any:
        """
        Returns a :class:`Scenario` instance based on the input data.

        Inputs:
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
            if scenario_inputs["diesel"]["mode"] == DieselMode.BACKUP.value
            else None,
            DieselMode(scenario_inputs["diesel"]["mode"]),
        )

        distribution_network = DistributionNetwork(
            scenario_inputs["distribution_network"]
        )

        return cls(
            scenario_inputs["battery"],
            demands,
            diesel_scenario,
            distribution_network,
            scenario_inputs["grid"],
            scenario_inputs["grid_type"],
            scenario_inputs["prioritise_self_generation"],
            scenario_inputs["pv"],
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
