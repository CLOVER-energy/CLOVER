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

import math
import os
import threading

from logging import Logger
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..__utils__ import (
    get_logger,
    LOCATIONS_FOLDER_NAME,
    monthly_profile_to_daily_profile,
)

__all__ = (
    "DeviceOwnershipThread",
    "LOAD_LOGGER_NAME",
)


# Load logger name:
#   The name to use for the load module logger.
LOAD_LOGGER_NAME = "load"


def _device_daily_profile(monthly_profile: pd.DataFrame, years: int) -> pd.DataFrame:
    """
    Converts the monthly utilisation profiles to daily utilisation profiles.

    Inputs:
        - monthly_profile:
            The monthly ownership profile for the device.
        - years:
            The number of years for the simulation.

    Outputs:
        - The daily-device profile as a :class:`pandas.DataFrame`.

    Notes:
        Gives a daily utilisation for all devices, even those which are not
        permitted by "Devices.csv"

    """

    # Convert the monthly profile to a daily profile.
    yearly_profile = pd.DataFrame.transpose(
        monthly_profile_to_daily_profile(monthly_profile)
    )
    for _ in range(years):
        yearly_profile = yearly_profile.append(yearly_profile)

    return yearly_profile


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
    cum_sales = dict()
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


def _number_of_devices_daily(
    device: Dict[str, Any],
    location_inputs: Dict[str, Any],
    logger: Logger,
    max_years: int,
) -> pd.DataFrame:
    """
    Calculates the number of devices owned by the community on each day

    Inputs:
        - device_inputs:
            The device inputs file contents.
        - location_inputs:
            The location inputs file contents.
        - logger:
            The logger to use for the run.
        - max_years:
            The maximum number of years for which the simulation can run.

    Outputs:
        - daily_ownership:
            Returns the number of devives that are owned by the community on a given
            day. Devices which are not permitted by "Devices.csv" should return a list
            composed entirely of zeroes.

    """

    if device["available"]:
        logger.info(
            "Calculating ownership for device %s.",
            device["device"],
        )
        population_growth_rate = _population_growth_daily(
            location_inputs["community_growth_rate"],
            location_inputs["community_size"],
            location_inputs["max_years"],
        )
        if device["final_ownership"] != device["initial_ownership"]:
            logger.info(
                "%s ownership changes over time, calculating.",
                device["device"],
            )
            cum_sales = _cumulative_sales_daily(
                device["initial_ownership"],
                device["final_ownership"],
                device["innovation"],
                device["imitation"],
                max_years,
            )
            daily_ownership = pd.DataFrame(
                np.floor(cum_sales.mul(population_growth_rate))  # type: ignore
            )
        else:
            logger.info(
                "%s ownership remains constant.",
                device["device"],
            )
            daily_ownership = pd.DataFrame(
                np.floor(population_growth_rate * device["initial_ownership"])
            )
        logger.info(
            "Ownership for device %s calculated.",
            device["device"],
        )
    else:
        logger.info(
            "Device %s was marked as unavailable, setting ownership to zero.",
            device["device"],
        )
        daily_ownership = pd.DataFrame(np.zeros((max_years * 365, 1)))

    return daily_ownership


class DeviceOwnershipThread(threading.Thread):
    """
    A :class:`threading.Thread` child for computing device-ownership profiles.

    .. attribute:: devices
        A `list` of device-related information, extracted from the devices input file.

    .. attribute:: generated_device_profiles_directory
        The directory in which CLOVER-generated files should be saved.

    .. attribute:: location_inputs
        The location inputs information, extracted from the location-inputs file.

    .. attribute:: logger
        The :class:`logging.Logger` to use for the run.

    .. attribute:: max_years
        The maximum number of years for which to run the simulation

    """

    def __init__(
        self,
        devices: List[Dict[str, Any]],
        generated_device_profiles_directory: str,
        location_inputs: Dict[str, Any],
    ) -> None:
        """
        Instantiate a device-ownership thread.

        Inputs:
            - devices:
                Device information extracted from the device-inputs file.
            - generated_device_profiles_directory:
                The directory in which to store the generated profiles.
            - max_years:
                The maximum number of years for the run.

        """

        self.devices: List[Dict[str, Any]] = devices
        self.generated_device_profiles_directory = generated_device_profiles_directory
        self.location_inputs = location_inputs
        self.logger: Logger = get_logger(LOAD_LOGGER_NAME)

        super().__init__()

    def run(
        self,
    ) -> None:
        """
        Execute a solar-data thread.

        """

        for device in self.devices:
            # Compute the daily device usage.
            daily_ownership = _number_of_devices_daily(
                device,
                self.location_inputs,
                self.logger,
                self.location_inputs["max_years"],
            )
            self.logger.info(
                "Monthly device ownership profile for %s successfully computed.",
                device["device"],
            )

            # Save the usage to the output file.
            daily_ownership_filename = f'{device["device"]}_daily_ownership.csv'
            daily_ownership.to_csv(
                os.path.join(
                    self.generated_device_profiles_directory,
                    daily_ownership_filename,
                )
            )
            self.logger.info(
                "Monthly deivice-ownership profile for %s successfully saved to %s.",
                device["device"],
                daily_ownership_filename,
            )

            # Compute daily-utilisation profile.
            interpolated_daily_profile = _device_daily_profile(
                daily_ownership, self.location_inputs["max_years"]
            )
            self.logger.info(
                "Daily device ownership profile for %s successfully computed.",
                device["device"],
            )

            # Save this to the output file.
            daily_times_filename = f'{device["device"]}_daily_times.csv'
            interpolated_daily_profile.to_csv(
                os.path.join(
                    self.generated_device_profiles_directory, daily_times_filename
                )
            )
            self.logger.info(
                "Daily deivice-ownership profile for %s successfully saved to %s.",
                device["device"],
                daily_times_filename,
            )

        self.logger.info(
            "All device daily-ownership profiles computed.",
        )


class Load:
    def __init__(self):
        self.location = "Bahraich"
        self.CLOVER_filepath = os.getcwd()
        self.location_filepath = os.path.join(
            self.CLOVER_filepath, LOCATIONS_FOLDER_NAME, self.location
        )
        self.location_inputs = pd.read_csv(
            os.path.join(
                self.location_filepath, "Location Data", "Location inputs.csv"
            ),
            header=None,
            index_col=0,
        )[1]
        self.device_filepath = os.path.join(self.location_filepath, "Load")
        self.device_ownership_filepath = os.path.join(
            self.device_filepath, "Device ownership"
        )
        self.device_inputs = pd.read_csv(
            os.path.join(self.device_filepath, "Devices.csv")
        )
        self.device_utilisation_filepath = os.path.join(
            self.device_filepath, "Device utilisation"
        )
        self.device_usage_filepath = os.path.join(
            self.device_filepath, "Devices in use"
        )
        self.device_load_filepath = os.path.join(self.device_filepath, "Device load")

    # =============================================================================
    #       Calculate the load of devices in the community
    # =============================================================================

    def total_load_hourly(self):
        """
        Function:
            Calculates the aggregated load of all devices
        Inputs:
            Takes in the .csv files of the loads of all devices
        Outputs:
            Gives a .csv file with columns for the load of domestic and
            commercial devices to be used in later simulations and a .csv file
            of the load statistics from Load().yearly_load_statistics(...)
        """
        domestic_load = pd.DataFrame(
            np.zeros((int(self.location_inputs["Years"]) * 365 * 24, 1))
        )
        commercial_load = pd.DataFrame(
            np.zeros((int(self.location_inputs["Years"]) * 365 * 24, 1))
        )
        public_load = pd.DataFrame(
            np.zeros((int(self.location_inputs["Years"]) * 365 * 24, 1))
        )
        for i in range(len(self.device_inputs)):
            device_info = self.device_inputs.iloc[i]
            if device_info["Type"] == "Domestic":
                add_load = pd.read_csv(
                    self.device_load_filepath + device_info["Device"] + "_load.csv",
                    index_col=0,
                ).reset_index(drop=True)
                domestic_load = pd.DataFrame(domestic_load.values + add_load.values)
            elif device_info["Type"] == "Commercial":
                add_load = pd.read_csv(
                    self.device_load_filepath + device_info["Device"] + "_load.csv",
                    index_col=0,
                ).reset_index(drop=True)
                commercial_load = pd.DataFrame(commercial_load.values + add_load.values)
            elif device_info["Type"] == "Public":
                add_load = pd.read_csv(
                    self.device_load_filepath + device_info["Device"] + "_load.csv",
                    index_col=0,
                ).reset_index(drop=True)
                public_load = pd.DataFrame(public_load.values + add_load.values)
        total_load = pd.concat([domestic_load, commercial_load, public_load], axis=1)
        total_load.columns = ["Domestic", "Commercial", "Public"]
        total_load.to_csv(self.device_load_filepath + "total_load.csv")

        yearly_load_statistics = self.yearly_load_statistics(total_load)
        yearly_load_statistics.to_csv(
            self.device_load_filepath + "yearly_load_statistics.csv"
        )

    def device_load_hourly(self):
        """
        Function:
            Calculates the total power for each device
        Inputs:
            Takes power from "Devices.csv" and uses the .csv files which give the
            number of devices in use at a given time
        Outputs:
            Gives .csv files of the hourly load for each device
        """
        for i in range(len(self.device_inputs)):
            device_info = self.device_inputs.iloc[i]
            device_load = float(device_info["Power"]) * pd.read_csv(
                self.device_usage_filepath + device_info["Device"] + "_in_use.csv",
                index_col=0,
            )
            device_load.to_csv(
                self.device_load_filepath + device_info["Device"] + "_load.csv"
            )

    # =============================================================================
    #       Calculate the maximum loads for each year
    # =============================================================================
    def yearly_load_statistics(self, total_load):
        """
        Function:
            Calculates the load statistics for each year on an hourly basis
        Inputs:
            total_load      Hourly total load of the system
        Outputs:
            Gives dataframe of the maximum, mean and median hourly loads
        """
        total_load_yearly = pd.DataFrame(
            np.reshape(
                pd.DataFrame(total_load.sum(axis=1)).values,
                (int(self.location_inputs["Years"]), 365 * 24),
            )
        )
        yearly_maximum = pd.DataFrame(total_load_yearly.max(axis=1))
        yearly_maximum.columns = ["Maximum"]
        yearly_mean = pd.DataFrame(total_load_yearly.mean(axis=1).round(0))
        yearly_mean.columns = ["Mean"]
        yearly_median = pd.DataFrame(np.percentile(total_load_yearly, 50, axis=1))
        yearly_median.columns = ["Median"]
        yearly_load_statistics = pd.concat(
            [yearly_maximum, yearly_mean, yearly_median], axis=1
        )
        return yearly_load_statistics

    def get_yearly_load_statistics(self, load_profile_filename):
        """
        Function:
            Outputs the load statistics for a prespecified load profile, which
              must have 'Domestic', 'Commercial' and 'Public' headings
        Inputs:
            load_profile_filename      Filename of load profile CSV
        Outputs:
            CSV file of yearly load statistics
        """

        load_profile = pd.read_csv(
            self.device_load_filepath + load_profile_filename, index_col=0
        ).reset_index(drop=True)
        yearly_load_statistics = self.yearly_load_statistics(load_profile)
        yearly_load_statistics.to_csv(
            self.device_load_filepath + "yearly_load_statistics.csv"
        )

    # =============================================================================
    #       Calculate the number of devices in use by the community
    # =============================================================================
    def devices_in_use_hourly(self):
        """
        Function:
            Calculates the number of devices in use at each hour of the simulation.
        Inputs:
            Requires .csv files of device utilisation at daily resolution
        Outputs:
            Generates a .csv file for each device with the number in use at any
            given time
        Notes:
            The number in use will always be less than or equal to the number
            owned by the community. Uses random binomial statistics.
        """
        for i in range(len(self.device_inputs)):
            device_info = self.device_inputs.iloc[i]
            device_daily_profile = pd.read_csv(
                self.device_utilisation_filepath
                + device_info["Device"]
                + "_daily_times.csv",
                index_col=0,
            )
            device_daily_profile = device_daily_profile.reset_index(drop=True)
            daily_devices = pd.read_csv(
                self.device_ownership_filepath
                + device_info["Device"]
                + "_daily_ownership.csv",
                index_col=0,
            )
            daily_devices = daily_devices.reset_index(drop=True)
            device_hourlist = pd.DataFrame()
            print("Calculating number of " + device_info["Device"] + "s in use\n")
            for day in range(0, 365 * int(self.location_inputs["Years"])):
                devices = float(daily_devices.iloc[day])
                day_profile = device_daily_profile.iloc[day]
                day_devices_on = pd.DataFrame(np.random.binomial(devices, day_profile))
                device_hourlist = device_hourlist.append(day_devices_on)
            device_hourlist.to_csv(
                self.device_usage_filepath + device_info["Device"] + "_in_use.csv"
            )
        print("\nAll devices in use calculated")

    # =============================================================================
    #      Calculate the total number of each device owned by the community
    # =============================================================================

    def population_hourly(self):
        """
        Function:
            Calculates the growth in the number of households in the community for each hour
        Inputs:
            Takes inputs from "Location inputs.csv" in the "Location data" folder
        Outputs:
            Gives a DataFrame of the number of households in the community for each hour
        Notes:
            Simple compound interest-style growth rate
        """
        community_size = float(self.location_inputs["Community size"])
        growth_rate = float(self.location_inputs["Community growth rate"])
        years = int(self.location_inputs["Years"])
        population = []
        growth_rate_hourly = (1 + growth_rate) ** (1 / (24.0 * 365.0)) - 1
        for t in range(0, 365 * 24 * years):
            population.append(
                math.floor(community_size * (1 + growth_rate_hourly) ** t)
            )
        return pd.DataFrame(population)
