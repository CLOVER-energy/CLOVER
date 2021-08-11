#!/usr/bin/python3
########################################################################################
# weather.py - Weather generation module  .                                            #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 11/08/2021                                                             #
# License: Open source                                                                 #
# Most recent update: 11/08/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
weather.py - The weather-profile-generation module for CLOVER.

This module fetches weather profiles from renewables.ninja, parses them and saves them
for use locally within CLOVER.

"""

from typing import Any, Dict

import pandas as pd


from .__utils__ import BaseRenewablesNinjaThread, total_profile_output
from ..__utils__ import Location

__all__ = (
    "WeatherDataThread",
    "WEATHER_LOGGER_THREAD",
    "total_weather_output",
)


# Weather logger name:
#   The name to use for the weather logger.
WEATHER_DATA_THREAD = "weather_generation"


class WeatherDataThread(
    BaseRenewablesNinjaThread, profile_name="weather", profile_key="weather"
):
    """
    Class to use when calling the weather data thread.

    """

    def __init__(
        self,
        auto_generated_files_directory: str,
        generation_inputs: Dict[Any, Any],
        location: Location,
        logger_name: str,
        regenerate: bool,
        solar_generation_inputs: Dict[str, Any],
        sleep_multiplier: int = 1,
    ):
        """
        Instantiate a :class:`SolarDataThread` instance.

        """

        # Add the additional parameters which are need when calling the solar data.
        renewables_ninja_params = {
            "lat": float(location.latitude),
            "lon": float(location.longitude),
            "local_time": "false",
            "capacity": 1.0,
            "system_loss": 0,
            "tracking": 0,
            "tilt": solar_generation_inputs["tilt"],
            "azim": solar_generation_inputs["azimuthal_orientation"],
        }
        super().__init__(
            auto_generated_files_directory,
            generation_inputs,
            location,
            logger_name,
            regenerate,
            sleep_multiplier,
            renewables_ninja_params=renewables_ninja_params,
        )


def total_solar_output(*args, **kwargs) -> pd.DataFrame:
    """
    Wrapper function to wrap the total solar output.

    """

    return total_profile_output(*args, **kwargs, profile_name="solar")
