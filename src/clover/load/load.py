#!/usr/bin/python3
########################################################################################
# load.py - Load-profile generation module.                                            #
#                                                                                      #
# Authors: Phil Sandwell, Ben Winchester                                               #
# Copyright: Phil Sandwell, 2018                                                       #
# License: Open source                                                                 #
# Most recent update: 14/07/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
load.py - The load-profile generation module of CLOVER.

This module generates load profiles for CLOVER based on the device information passed
in.

"""

import dataclasses
import math
import os

from logging import Logger
from typing import Any, Dict, Optional, Set, Tuple

import numpy as np  # pylint: disable=import-error
import pandas as pd  # pylint: disable=import-error

from tqdm import tqdm  # pylint: disable=import-error

from ..__utils__ import (
    BColours,
    CUT_OFF_TIME,
    ColumnHeader,
    DemandType,
    ELECTRIC_POWER,
    InputFileError,
    InternalError,
    KEROSENE_DEVICE_NAME,
    ResourceType,
    Location,
    Scenario,
    monthly_times_to_daily_times,
)

__all__ = (
    "compute_total_hourly_load",
    "compute_processed_load_profile",
    "DEFAULT_KEROSENE_DEVICE",
    "Device",
    "LOAD_LOGGER_NAME",
    "ResourceType",
    "population_hourly",
    "process_device_hourly_power",
    "process_device_hourly_usage",
    "process_device_ownership",
    "process_device_utilisation",
    "process_load_profiles",
)


# Available:
#   Keyword used for parsing whether a device is available.
AVAILABLE: str = "available"

# Clean-water usage:
#   Keyword used for parsing the clean-water usage of a device.
CLEAN_WATER_USAGE: str = "clean_water_usage"

# Device:
#   Keyword used for parsing the name of a device.
DEVICE: str = "device"

# Final ownership:
#   Keyword used for parsing the final ownership of a device.
FINAL_OWNERSHIP: str = "final_ownership"

# Hot-water usage:
#   Keyword used for parsing the hot-water usage of a device.
HOT_WATER_USAGE: str = "hot_water_usage"

# Initial ownership:
#   Keyword used for parsing the initial ownership of a device.
INITIAL_OWNERSHIP: str = "initial_ownership"

# Innovation:
#   Keyword used for parsing the innovation of a device.
INNOVATION: str = "innovation"

# Imitation:
#   Keyword used for parsing the imitation of a device.
IMITATION: str = "imitation"

# Load logger name:
#   The name to use for the load module logger.
LOAD_LOGGER_NAME: str = "load"

# Mean column name:
#   The name to use for the "mean" column in the yearly-load statistics.
MEAN: str = "Mean"

# Median column name:
#   The name to use for the "median" column in the yearly-load statistics.
MEDIAN: str = "Median"


@dataclasses.dataclass
class Device:
    """
    Represents a device being modelled.

    .. attribute:: available
        Whether the device is available.

    .. attribute:: demand_type
        The type of demand with which the device is associated.

    .. attribute:: electric_power
        The electric power consumption of the device, measured in Watts.

    .. attribute:: final_ownership
        The average ownership of the device per household at the end of the time period
        being modelled.

    .. attribute:: initial_ownership
        The initial average ownership of the device per household.

    .. attribute:: innovation
        The rate of innovation for the device: the rate at which new households acquire
        the device.

    .. attribute:: imitation
        The rate of imitation for the device: the rate at which households copy others
        and acquire the device.

    .. attribute:: name
        The name of the device.

    .. attribute:: clean_water_usage
        The clean-water usage of the device, measured in litres per hour.

    .. attribute:: hot_water_usage
        The hot-water usage of the device, measured in litres per hour.

    """

    available: bool
    demand_type: DemandType
    electric_power: Optional[float]
    final_ownership: float
    initial_ownership: float
    innovation: float
    imitation: float
    name: str
    clean_water_usage: Optional[float]
    hot_water_usage: Optional[float]

    def __hash__(self) -> int:
        """
        Return a unique identifier for the device.

        Outputs:
            A unique identifier for the device.

        """

        return hash(self.__str__())

    def __str__(self) -> str:
        """
        Return a nice-looking output for the device.

        Outputs:
            - A nice-looking string representation for the device.

        """

        representation_string = (
            "Device("
            + f"name={self.name}, "
            + ("available, " if self.available else "unavailable, ")
            + f"electric_power={self.electric_power} W, "
            + f"final_ownership={self.final_ownership}, "
            + f"initial_ownership={self.initial_ownership}, "
            + f"innovation={self.innovation}, "
            + f"imitation={self.imitation}, "
            + f"clean_water_usage={self.clean_water_usage} litres/hour, "
            + f"hot_water_usage={self.hot_water_usage} litres/hour"
            + ")"
        )

        return representation_string

    @classmethod
    def from_dict(cls, device_input: Dict[str, Any]) -> Any:
        """
        Processes input data to generate a :class:`Device` instance.

        Inputs:
            - device_input:
                The device input data extracted from the devices input file.

        Outputs:
            - The :class:`Device` instancce based on the input data.

        """

        demand_type = DemandType(device_input["type"])

        if ELECTRIC_POWER not in device_input:
            raise InputFileError(
                "device inputs",
                "All devices must specify an electric power value explicitly, even if "
                "this is set to zero. "
                f"The device, {device_input['device']}, does not specify such a value.",
            )

        return cls(
            device_input[AVAILABLE],
            demand_type,
            device_input[ELECTRIC_POWER],
            device_input[FINAL_OWNERSHIP],
            device_input[INITIAL_OWNERSHIP],
            device_input[INNOVATION],
            device_input[IMITATION],
            device_input[DEVICE],
            device_input[CLEAN_WATER_USAGE]
            if CLEAN_WATER_USAGE in device_input
            else None,
            device_input[HOT_WATER_USAGE] if HOT_WATER_USAGE in device_input else None,
        )


# Default kerosene device:
#   The default kerosene device to use in the event that no kerosene information is
#   provided.
DEFAULT_KEROSENE_DEVICE = Device(
    False, DemandType.DOMESTIC, 1, 0, 0, 0, 0, KEROSENE_DEVICE_NAME, 0, 0
)


def _cumulative_sales_daily(
    current_market_proportion: float,
    maximum_market_proportion: float,
    innovation: float,
    imitation: float,
    years: int,
) -> pd.DataFrame:
    """
    Return the ownership (sales) of devices in the community.

    Computes and returns the sales (ownership) of devices in the community over the
    lifetime of the simulation.

    Inputs:
        - current_market_proportion:
            The current proportion of potential owners who own the device.
        - maximum_market_proportion:
            The maximum saturation of ownership within the market.
        - innovation:
            The rate of innovation, i.e., new customers spontaneously purchasing the
            device.
        - imitation:
            The rate of customers copying those around them and purchasing the device.
        - years:
            The number of years for which the simulation is being run.

    Outputs:
        - A dataframe of the ownership of that device type for each day.

    Notes:
        Uses the Bass diffusion model

    """

    maximisation_ratio = maximum_market_proportion - current_market_proportion
    daily_innovation = innovation / 365
    daily_imitation = imitation / 365
    cum_sales = {}
    for day in range(0, 365 * years):
        num = 1 - math.exp(-1 * (daily_innovation + daily_imitation) * day)
        den = 1 + (daily_imitation / daily_innovation) * math.exp(
            -1 * (daily_innovation + daily_imitation) * day
        )
        cum_sales[day] = maximisation_ratio * num / den + current_market_proportion
    return pd.DataFrame(list(cum_sales.values()))


def _population_growth_daily(
    community_growth_rate: float, community_size: int, num_years: int
) -> pd.DataFrame:
    """
    Calculates the growth in the number of households in the community

    Inputs:
        Takes inputs from "Location inputs.csv" in the "Location data" folder

    Outputs:
        Gives a DataFrame of the number of households in the community for each day

    Notes:
        Simple compound interest-style growth rate

    """

    population = []
    growth_rate_daily = (1 + community_growth_rate) ** (1 / 365.0) - 1
    for day in range(0, 365 * num_years):
        population.append(math.floor(community_size * (1 + growth_rate_daily) ** day))
    return pd.DataFrame(population)


def _yearly_load_statistics(total_load: pd.DataFrame, years: int) -> pd.DataFrame:
    """
    Calculates the load statistics for each year on an hourly basis.

    Inputs:
        - total_load:
            Hourly total load of the system.
        - years:
            The number of years for which the simulation is being run.

    Outputs:
        - A dataframe containing the maximum, mean and median hourly loads.

    """

    total_load_yearly = pd.DataFrame(
        np.reshape(
            pd.DataFrame(total_load.sum(axis=1)).values,
            (years, 365 * 24),
        )
    )

    yearly_maximum: pd.DataFrame = pd.DataFrame(
        total_load_yearly.max(axis=1)  # type: ignore
    )
    yearly_maximum.columns = pd.Index([ColumnHeader.MAXIMUM.value])
    yearly_mean: pd.DataFrame = pd.DataFrame(
        total_load_yearly.mean(axis=1).round(0)  # type: ignore
    )
    yearly_mean.columns = pd.Index([MEAN])
    yearly_median: pd.DataFrame = pd.DataFrame(
        np.percentile(total_load_yearly, 50, axis=1)  # type: ignore
    )
    yearly_median.columns = pd.Index([MEDIAN])
    yearly_load_statistics = pd.concat(
        [yearly_maximum, yearly_mean, yearly_median], axis=1
    )

    return yearly_load_statistics


def _number_of_devices_daily(
    device: Device,
    location: Location,
    logger: Logger,
) -> pd.DataFrame:
    """
    Calculates the number of devices owned by the community on each day

    Inputs:
        - device:
            The device currently being considered.
        - location:
            The location currently being considered.
        - logger:
            The logger to use for the run.
    Outputs:
        - daily_ownership:
            Returns the number of devives that are owned by the community on a given
            day. Devices which are not permitted by "Devices.csv" should return a list
            composed entirely of zeroes.

    """

    if device.available:
        logger.info(
            "Calculating ownership for device %s.",
            device.name,
        )
        population_growth_rate = _population_growth_daily(
            location.community_growth_rate,
            location.community_size,
            location.max_years,
        )
        if device.final_ownership != device.initial_ownership:
            logger.info(
                "%s ownership changes over time, calculating.",
                device.name,
            )
            cum_sales = _cumulative_sales_daily(
                device.initial_ownership,
                device.final_ownership,
                device.innovation,
                device.imitation,
                location.max_years,
            )
            daily_ownership = pd.DataFrame(
                np.floor(cum_sales.values * population_growth_rate.values)
            )

        else:
            logger.info(
                "%s ownership remains constant.",
                device.name,
            )
            daily_ownership = pd.DataFrame(
                np.floor(population_growth_rate * device.initial_ownership)  # type: ignore
            )
        logger.info(
            "Ownership for device %s calculated.",
            device.name,
        )

    else:
        logger.info(
            "Device %s was marked as unavailable, setting ownership to zero.",
            device.name,
        )
        daily_ownership = pd.DataFrame(np.zeros((location.max_years * 365, 1)))

    return daily_ownership


def compute_total_hourly_load(  # pylint: disable=too-many-locals
    *,
    device_hourly_loads: Dict[str, pd.DataFrame],
    devices: Set[Device],
    disable_tqdm: bool,
    generated_device_load_filepath: str,
    logger: Logger,
    total_load_profile: Optional[pd.DataFrame],
    years: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calculates the aggregated load of all devices.

    Inputs:
        - device_hourly_loads:
            A mapping between device name and the hourly load profile of the device.
        - devices:
            The set of devices included in the system.
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - generated_device_load_filepath:
            The directory in which to store the generated hourly load profiles for the
            device.
        - logger:
            The logger to use for the run.
        - regenerate:
            Whether to force regenerate the profiles.
        - total_load_profile:
            The total load profile to use in lieu of profile generation if specified.
        - years:
            The nbumber of years for which the simulation is being run.

    Outputs:
        - The total load of all devices;
        - The yearly-load statistics.

    """

    # If the files already exist, simply read the data and quit.
    total_load_filepath = os.path.join(generated_device_load_filepath, "total_load.csv")
    yearly_load_statistics_filepath = os.path.join(
        generated_device_load_filepath, "yearly_load_statistics.csv"
    )

    if total_load_profile is None:
        logger.info(
            "Total load data must be recomputed each run unless an override profile is "
            "specified. Calculating total load data."
        )

        # Instantiate empty dataframes.
        domestic_load = pd.DataFrame(np.zeros((years * 365 * 24, 1)))
        commercial_load = pd.DataFrame(np.zeros((years * 365 * 24, 1)))
        public_load = pd.DataFrame(np.zeros((years * 365 * 24, 1)))

        # Sum over the device loads.
        for device in tqdm(
            devices,
            desc="total load profile",
            disable=disable_tqdm,
            leave=True,
            unit="device",
        ):
            # Skip the device if it is not available in the community.
            if not device.available:
                continue

            if device.demand_type == DemandType.DOMESTIC:
                domestic_load = pd.DataFrame(
                    domestic_load.values + device_hourly_loads[device.name].values
                )
            elif device.demand_type == DemandType.COMMERCIAL:
                commercial_load = pd.DataFrame(
                    commercial_load.values + device_hourly_loads[device.name].values
                )
            elif device.demand_type == DemandType.PUBLIC:
                public_load = pd.DataFrame(
                    public_load.values + device_hourly_loads[device.name].values
                )
            else:
                logger.error(
                    "Demand type of device %s is unknown. Type: %s.",
                    device.name,
                    device.demand_type,
                )

        logger.info("Total load for all devices successfully computed.")
        total_load = pd.concat([domestic_load, commercial_load, public_load], axis=1)
        total_load.columns = pd.Index(
            [
                DemandType.DOMESTIC.value,
                DemandType.COMMERCIAL.value,
                DemandType.PUBLIC.value,
            ]
        )

        logger.info("Saving total load.")
        with open(total_load_filepath, "w") as f:
            total_load.to_csv(f, line_terminator="")  # type: ignore
        logger.info("Total device load successfully saved to %s.", total_load_filepath)

    else:
        total_load = total_load_profile
        if not all(
            total_load.columns
            == pd.Index(
                [
                    DemandType.DOMESTIC.value,
                    DemandType.COMMERCIAL.value,
                    DemandType.PUBLIC.value,
                ]
            )
        ):
            logger.error(
                "%sThe total load profile specified is not of the right format. See "
                "logs for details.%s",
                BColours.fail,
                BColours.endc,
            )
            logger.info(
                "The total load file given must have columns which match %s.",
                ", ".join(f"'{e.value}'" for e in DemandType),
            )
            raise InputFileError(
                "total-load file",
                "The total load profile is not of the correct format.",
            )

    # Attempt to read the yearly load statistics from a file and compute if it doesn't
    # exist.
    logger.info(
        "Yearly load statistics must be recomputed, calculating yearly load statistics."
    )
    yearly_load_statistics = _yearly_load_statistics(total_load, years)

    logger.info("Saving yearly load statistics.")
    with open(yearly_load_statistics_filepath, "w") as f:
        yearly_load_statistics.to_csv(
            f, index=False, line_terminator=""  # type: ignore
        )
    logger.info("Yearly load statistics successfully saved.")

    return total_load, yearly_load_statistics


def population_hourly(location: Location) -> pd.DataFrame:
    """
    Calculates the growth in the number of households in the community for each hour

    Inputs:
        - location:
            The location being considered.

    Outputs:
        - A DataFrame of the number of households in the community for each hour.

    Notes:
        Simple compound interest-style growth rate.

    """

    growth_rate_hourly = (1 + location.community_growth_rate) ** (
        1 / (24.0 * 365.0)
    ) - 1
    population = [
        math.floor(location.community_size * (1 + growth_rate_hourly) ** hour)
        for hour in range(0, 365 * 24 * location.max_years)
    ]

    return pd.DataFrame(population)


def process_device_hourly_power(
    device: Device,
    *,
    generated_device_load_filepath: str,
    hourly_device_usage: pd.DataFrame,
    resource_type: ResourceType,
    logger: Logger,
    regenerate: bool,
) -> pd.DataFrame:
    """
    Calculate the hourly power consumption of the device.

    Inputs:
        - device:
            The device to be processed.
        - generated_device_load_filepath:
            The directory in which to store the generated hourly load profiles for the
            device.
        - hourly_device_usage:
            The hourly usage profile for the device.
        - logger:
            The logger to use for the run.
        - power_type:
            The type of power being investigated, e.g., "electric_power".
        - regenerate:
            Whether to force-regenerate the various profiles.

    Outputs:
        - The hourly load of the device as a :class:`pandas.DataFrame`.

    """

    filename = f"{device.name}_load.csv"
    hourly_usage_filepath = os.path.join(generated_device_load_filepath, filename)

    # If the hourly power usage file already exists, load the data in.
    logger.info("Processing hourly power profile for %s.", device.name)
    if os.path.isfile(hourly_usage_filepath) and not regenerate:
        with open(hourly_usage_filepath, "r") as f:
            device_load: pd.DataFrame = pd.read_csv(f, header=None)
        logger.info(
            "Hourly power profile for %s successfully read from file %s.",
            device.name,
            hourly_usage_filepath,
        )
    else:
        # Compute the hourly load profile.
        logger.info("Computing hourly power usage for %s.", device.name)
        if resource_type == ResourceType.ELECTRIC:
            if device.electric_power is None:
                raise Exception(
                    f"{BColours.fail}Internal error processing device "
                    + f"'{device.name}', electric power unexpectedly `None`.{BColours.endc}",
                )
            device_load = hourly_device_usage * device.electric_power
            logger.info(
                "Electric hourly power usage for %s successfully computed.", device.name
            )
        elif resource_type == ResourceType.CLEAN_WATER:
            if device.clean_water_usage is None:
                raise InternalError(
                    f"{BColours.fail}Internal error processing device "
                    + f"'{device.name}', clean-water usage unexpectedly `None`."
                    + f"{BColours.endc}",
                )

            device_load = hourly_device_usage * device.clean_water_usage
            logger.info("Water usage for %s successfully computed.", device.name)
        elif resource_type == ResourceType.HOT_CLEAN_WATER:
            if device.hot_water_usage is None:
                raise InternalError(
                    f"{BColours.fail}Internal error processing device "
                    + f"'{device.name}', hot-water usage unexpectedly `None`."
                    + f"{BColours.endc}",
                )

            device_load = hourly_device_usage * device.hot_water_usage
        else:
            logger.error(
                "%sUnsuported load type used: %s%s",
                BColours.fail,
                resource_type.value,
                BColours.endc,
            )

        # Reset the index on the device load.
        try:
            device_load = device_load.reset_index(drop=True)
        except UnboundLocalError:
            logger.error(
                "%sHandling of resource load failed due to unknown load type: %s%s",
                BColours.fail,
                resource_type.value,
                BColours.endc,
            )
            raise

        # Save the hourly power profile.
        logger.info("Saving hourly power usage for %s.", device.name)

        with open(
            hourly_usage_filepath,
            "w",
        ) as f:
            device_load.to_csv(
                f, header=None, index=False, line_terminator=""  # type: ignore
            )

        logger.info(
            "Hourly power proifle for %s successfully saved to %s.",
            device.name,
            hourly_usage_filepath,
        )

    return device_load


def process_device_hourly_usage(
    device: Device,
    *,
    daily_device_ownership: pd.DataFrame,
    daily_device_utilisation: pd.DataFrame,
    generated_device_usage_filepath: str,
    logger: Logger,
    regenerate: bool,
    years: int,
) -> pd.DataFrame:
    """
    Calculate the number of devices in use by the community.

    Inputs:
        - device:
            The data for the device to be processed.
        - daily_device_ownership:
            The ownership data for the device.
        - daily_device_utilisation:
            The utilisation data for the device.
        - generated_device_usage_filepath:
            The directory in which to store the generated hourly device-usage profiles.
        - logger:
            The logger to use for the run.
        - regenerate:
            Whether to force-regenerate the profiles.
        - years:
            The number of years for which the simulation is being run.

    Outputs:
        - The hourly usage of the device specified as a :class:`pandas.DataFrame`.

    """

    filename = f"{device.name}_in_use.csv"
    filepath = os.path.join(generated_device_usage_filepath, filename)

    # If the device hourly usage already exists, then read the data in from the file.
    if os.path.isfile(filepath) and not regenerate:
        with open(filepath, "r") as f:
            hourly_device_usage = pd.read_csv(f, header=None)
        logger.info(
            "Hourly device usage for %s successfully read from file: %s",
            device.name,
            filepath,
        )

    else:
        daily_device_utilisation = daily_device_utilisation.reset_index(drop=True)
        daily_device_ownership = daily_device_ownership.reset_index(drop=True)

        hourly_device_usage = pd.DataFrame()

        # Calculate the hourly-usage profile.
        # This processes a random distribution for usage based on the device ownership and
        # utilisation on any given day for all days within the simulation range.
        #

        logger.info("Calculating number of %ss in use", device.name)
        try:
            hourly_device_usage = pd.concat(  # type: ignore
                [
                    pd.DataFrame(  # type: ignore
                        np.random.binomial(  # type: ignore
                            float(daily_device_ownership.iloc[day, 0]),
                            daily_device_utilisation.iloc[day, :],
                        )
                    )
                    for day in range(0, 365 * years)
                ]
            )
        except ValueError as e:
            logger.error(
                "%sError computing device hourly usage profile for %s: type error in "
                "variables: %s%s",
                BColours.fail,
                device.name,
                str(e),
                BColours.endc,
            )
            raise

        logger.info("Hourly usage profile for %s successfully calculated.", device.name)

        # Save the hourly-usage profile.
        logger.info("Saving hourly usage profile for %s.", device.name)

        with open(
            filepath,
            "w",
        ) as f:
            hourly_device_usage.to_csv(
                f, header=None, index=False, line_terminator=""  # type: ignore
            )

        logger.info(
            "Hourly usage proifle for %s successfully saved to %s.",
            device.name,
            filename,
        )

    return hourly_device_usage


def process_device_ownership(
    device: Device,
    *,
    generated_device_ownership_directory: str,
    location: Location,
    logger: Logger,
    regenerate: bool,
) -> pd.DataFrame:
    """
    Process device-data files.

    Processes the device files, including device ownership and utilisation, for a given
    device.

    Inputs:
        - device:
            The device to be processed.
        - generated_device_ownership_directory:
            The directory in which to store the generated device-ownership profiles.
        - location:
            The location currently being considered.
        - logger:
            The logger to use for the run.
        - regenerate:
            Whether to force-regenerate the profiles.

    Outputs:
        - The daily ownership of the device.

    """

    logger.info("Load ownership process instantiated for device %s.", device.name)

    daily_ownership_filename = f"{device.name}_daily_ownership.csv"
    daily_ownership_filepath = os.path.join(
        generated_device_ownership_directory,
        daily_ownership_filename,
    )

    # If the daily ownership file already exists, then read the data from the file.
    if os.path.isfile(daily_ownership_filepath) and not regenerate:
        with open(daily_ownership_filepath, "r") as f:
            daily_ownership = pd.read_csv(f, header=None)
        logger.info(
            "Monthly device-ownership profile for %s successfully read from %s.",
            device.name,
            daily_ownership_filepath,
        )

    else:
        # Compute the device-ownership profiles.
        logger.info("Computing device ownership for %s.", device.name)

        # Compute the daily device usage.
        daily_ownership = _number_of_devices_daily(
            device,
            location,
            logger,
        )
        logger.info(
            "Monthly device ownership profile for %s successfully computed.",
            device.name,
        )

        # Save the usage to the output file.
        with open(
            daily_ownership_filepath,
            "w",
        ) as f:
            daily_ownership.to_csv(
                f, header=None, index=False, line_terminator=""  # type: ignore
            )
        logger.info(
            "Monthly deivice-ownership profile for %s successfully saved to %s.",
            device.name,
            daily_ownership_filename,
        )

    return daily_ownership


def process_device_utilisation(
    device: Device,
    *,
    device_utilisations: Dict[Device, pd.DataFrame],
    generated_device_utilisation_directory: str,
    location: Location,
    logger: Logger,
    regenerate: bool,
) -> pd.DataFrame:
    """
    Process device-data files.

    Processes the device files, including device ownership and utilisation, for a given
    device.

    Inputs:
        - device:
            The data for the device to be processed.
        - device_uilisations:
            The set of device utilisations to process.
        - generated_device_utilisation_directory:
            The directory in which to store the generated device-utilisation profiles.
        - location:
            The location currently being considered.
        - logger:
            The logger to use for the run.
        - regenerate:
            Whether to force-regenerate the profiles.

    Outputs:
        - The interpolated daily utilisation profile.

    """

    logger.info("Load utilisation process instantiated for device %s.", device.name)

    daily_times_filename = f"{device.name}_daily_times.csv"
    filepath = os.path.join(
        generated_device_utilisation_directory, daily_times_filename
    )

    # If the file already exists, simply read in the data.
    if os.path.isfile(filepath) and not regenerate:
        with open(filepath, "r") as f:
            interpolated_daily_profile = pd.read_csv(f, header=None)
        logger.info(
            "Daily device-utilisation profile for %s successfully read from file %s.",
            device.name,
            filepath,
        )

    else:
        logger.info("Computing device-utilisation profile for %s.", device.name)
        interpolated_daily_profile = monthly_times_to_daily_times(
            device_utilisations[device],
            location.max_years,
        )
        logger.info(
            "Daily device-utilisation profile for %s successfully computed.",
            device.name,
        )

        # Save this to the output file.
        with open(filepath, "w") as f:
            interpolated_daily_profile.to_csv(
                f, header=None, index=False, line_terminator=""  # type: ignore
            )
        logger.info(
            "Daily deivice-utilisation profile for %s successfully saved to %s.",
            device.name,
            daily_times_filename,
        )

    return interpolated_daily_profile


def process_load_profiles(  # pylint: disable=too-many-locals
    auto_generated_files_directory: str,
    device_utilisations: Dict[Device, pd.DataFrame],
    disable_tqdm: bool,
    location: Location,
    logger: Logger,
    regenerate: bool,
    resource_type: ResourceType,
    total_load_profile: Optional[pd.DataFrame] = None,
) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    """
    Process all the load information and profiles to generate the total load.

    This function runs through the processing of all the various load profiles and
    is the default access point for this module.

    Inputs:
        - auto_generated_files_directory:
            The directory in which auto-generated files should be saved.
        - device_utilisations:
            The processed device utilisation information.
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - resource_type:
            The type of load being investigated.
        - location:
            The location currently being considered.
        - logger:
            The logger to use for the run.
        - regenerate:
            Whether to force-regenerate the various profiles.
        - total_load_profile:
            The total load profile to use in lieu of profile generation if specified.

    Outputs:
        - A mapping between the device and the load demand that it generates for the
          first few cycles;
        - The total load use for all devices;
        - The yearly load statistics.

    """

    device_hourly_loads: Dict[str, pd.DataFrame] = {}
    if resource_type == ResourceType.ELECTRIC:
        resource_name: str = "electric"
        relevant_device_utilisations: Dict[Device, pd.DataFrame] = {
            device: device_utilisation
            for device, device_utilisation in device_utilisations.items()
            if device.electric_power is not None
        }
    elif resource_type == ResourceType.CLEAN_WATER:
        resource_name = "clean_water"
        relevant_device_utilisations = {
            device: device_utilisation
            for device, device_utilisation in device_utilisations.items()
            if device.clean_water_usage is not None
        }
    elif resource_type == ResourceType.HOT_CLEAN_WATER:
        resource_name = "hot_water"
        relevant_device_utilisations = {
            device: device_utilisation
            for device, device_utilisation in device_utilisations.items()
            if device.hot_water_usage is not None
        }

    else:
        logger.error(
            "%sUnknown load type when calling the load module to generate profiles: %s%s",
            BColours.fail,
            resource_type.value,
            BColours.endc,
        )
        raise Exception(
            f"{BColours.fail}Unknown load type: {resource_type.value}{BColours.endc}"
        )

    for device in tqdm(
        relevant_device_utilisations,
        desc=f"{resource_name.replace('_', ' ')} load profiles",
        disable=disable_tqdm,
        leave=True,
        unit="device",
    ):
        # If the device is not available, then skip it.
        if not device.available and not device.name == KEROSENE_DEVICE_NAME:
            continue

        # Compute the device ownership.
        daily_device_ownership = process_device_ownership(
            device,
            generated_device_ownership_directory=os.path.join(
                auto_generated_files_directory,
                "load",
                "device_ownership",
            ),
            location=location,
            logger=logger,
            regenerate=regenerate,
        )
        logger.info(
            "Device ownership information for %s successfully computed.",
            device.name,
        )

        # Compute the device utilisation.
        daily_device_utilisaion = process_device_utilisation(
            device,
            device_utilisations=relevant_device_utilisations,
            generated_device_utilisation_directory=os.path.join(
                auto_generated_files_directory,
                "load",
                "device_utilisation",
            ),
            location=location,
            logger=logger,
            regenerate=regenerate,
        )
        logger.info(
            "Device utilisation information for %s successfully computed.",
            device.name,
        )

        # Compute the device usage.
        hourly_device_usage = process_device_hourly_usage(
            device,
            daily_device_ownership=daily_device_ownership,
            daily_device_utilisation=daily_device_utilisaion,
            generated_device_usage_filepath=os.path.join(
                auto_generated_files_directory, "load", "device_usage"
            ),
            logger=logger,
            years=location.max_years,
            regenerate=regenerate,
        )
        logger.info(
            "Device hourly usage information for %s successfully computed.",
            device.name,
        )

        # Compute the load profile based on this usage.
        device_hourly_loads[device.name] = process_device_hourly_power(
            device,
            generated_device_load_filepath=os.path.join(
                auto_generated_files_directory, "load", resource_name, "device_load"
            ),
            hourly_device_usage=hourly_device_usage,
            resource_type=resource_type,
            logger=logger,
            regenerate=regenerate,
        )
        logger.info(
            "Device hourly load information for %s successfully computed.",
            device.name,
        )

    logger.info("Computing the total device hourly load and yearly load statistics.")
    total_load, yearly_statistics = compute_total_hourly_load(
        device_hourly_loads=device_hourly_loads,
        devices=set(relevant_device_utilisations.keys()),
        disable_tqdm=disable_tqdm,
        generated_device_load_filepath=os.path.join(
            auto_generated_files_directory, "load", resource_name, "device_load"
        ),
        logger=logger,
        total_load_profile=total_load_profile,
        years=location.max_years,
    )
    logger.info("Total load and yearly statistics successfully computed.")

    return (
        {
            device_name: load.iloc[0:CUT_OFF_TIME, :]
            for device_name, load in device_hourly_loads.items()
        },
        total_load,
        yearly_statistics,
    )


def compute_processed_load_profile(
    scenario: Scenario, total_load: pd.DataFrame
) -> pd.DataFrame:
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
            processed_total_load = pd.DataFrame(total_load[DemandType.COMMERCIAL.value])

    if scenario.demands.public:
        if processed_total_load is not None:
            processed_total_load += pd.DataFrame(  # type: ignore
                total_load[DemandType.PUBLIC.value].values
            )
        else:
            processed_total_load = pd.DataFrame(total_load[DemandType.PUBLIC.value])

    if processed_total_load is None:
        raise Exception("At least one load type must be specified.")

    return processed_total_load
