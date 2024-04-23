#!/usr/bin/python3
########################################################################################
# wind.py - Wind generation module  .                                                  #
#                                                                                      #
# Author: Phil Sandwell                                                                #
# Copyright: Phil Sandwell, 2021                                                       #
# License: Open source                                                                 #
# Most recent update: 14/07/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
wind.py - The wind-profile-generation module for CLOVER.

This module fetches wind profiles from renewables.ninja, parses them and saves them for
use locally within CLOVER.

"""

import enum

import pandas as pd  # pylint: disable=import-error

from ..__utils__ import Location
from .__utils__ import BaseRenewablesNinjaThread, total_profile_output

__all__ = (
    "WindDataThread",
    "WIND_LOGGER_NAME",
    "total_wind_output",
)


# Wind logger name:
#   The name to use for the wind logger.
WIND_LOGGER_NAME = "wind_generation"


class WindDataThread(
    BaseRenewablesNinjaThread, profile_name="wind", profile_key="wind"
):
    """
    Class to use when calling the wind data thread.

    NOTE: Heights of wind turbines are limited to between 10 m and 150 m by the
    Renewables.Ninja API. This should be checked before attempting to fetch data beyond
    this range.

    """

    def __init__(
        self,
        auto_generated_files_directory: str,
        global_settings_inputs: dict[str, int | str],
        location: Location,
        logger_name: str,
        pause_time: int,
        regenerate: bool,
        sleep_multiplier: int = 1,
        verbose: bool = False,
    ):
        """
        Instantiate a :class:`WindDataThread` instance.

        """

        # Add the additional parameters which are need when calling the wind data.
        renewables_ninja_params = {
            "lat": float(location.latitude),
            "lon": float(location.longitude),
            "local_time": "false",
            "capacity": 1.0,
            "height": 10,
            "turbine": "Vestas V80 2000",
            "raw": "true",
        }
        super().__init__(
            auto_generated_files_directory,
            global_settings_inputs,
            location,
            logger_name,
            pause_time,
            regenerate,
            sleep_multiplier,
            verbose,
            renewables_ninja_params=renewables_ninja_params,
        )


def total_wind_output(*args, **kwargs) -> pd.DataFrame:
    """
    Wrapper function to wrap the total wind output.

    """

    return total_profile_output(*args, **kwargs, profile_name="wind")


class WindDataType(enum.Enum):
    """
    Stores weather condition information for extracting data from renewables ninja.

    - ELECTRICITY:
        Denotes the electricity generated by the wind turbine.

    - WIND_SPEED:
        Denotes the wind speed at the height specified for the data.

    """

    ELECTRICITY = "electricity"
    WIND_SPEED = "wind_speed"
