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

import pandas as pd  # type: ignore


from .__utils__ import BaseRenewablesNinjaThread, total_profile_output
from ..__utils__ import Location

__all__ = (
    "WeatherDataThread",
    "WEATHER_LOGGER_NAME",
    "total_weather_output",
)


# Weather logger name:
#   The name to use for the weather logger.
WEATHER_LOGGER_NAME = "weather_generation"


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
        sleep_multiplier: int = 1,
    ):
        """
        Instantiate a :class:`WeatherDataThread` instance.

        The weather variables that can be fetched are:
            - var_t2m:
                Surface temperature in degrees Celcius.
            - var_prectotland:
                Precipitation in mm/hour.
            - var_precsnoland
                Snowfall in mm/hour.
            - var_snomas:
                The mass of snow per land area in mm/m^2.
            - var_rhoa:
                The air density, at ground level, measured in kg/m^3.
            - var_swgdn:
                The solar irradiance at ground level, measured in W/m^2.
            - var_swtdn:
                The solar irradiance at the top of the atmosphere, measured in W/m^2.
            - var_cldtot:
                The cloud cover fraction, defined between 0 and 1.

        """

        # Add the additional parameters which are need when calling the weather data.
        renewables_ninja_params = {
            "lat": float(location.latitude),
            "lon": float(location.longitude),
            "local_time": "false",
            "header": "true",
            "var_t2m": "true",
            "var_prectotland": "true",
            "var_swgdn": "true",
            "var_cldtot": "true",
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


def total_weather_output(*args, **kwargs) -> pd.DataFrame:
    """
    Wrapper function to wrap the total weather output.

    """

    return total_profile_output(*args, **kwargs, profile_name="weather")
