#!/usr/bin/python3
########################################################################################
# solar.py - Solar generation module  .                                                #
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
solar.py - The solar-profile-generation module for CLOVER.

This module fetches solar profiles from renewables.ninja, parses them and saves them
for use locally within CLOVER.

"""

import json
import os
import threading
import time

from json.decoder import JSONDecodeError
from logging import Logger
from typing import Any, Dict

import numpy as np
import pandas as pd
import requests

from tqdm import tqdm  # type: ignore

from .__utils__ import BaseRenewablesNinjaThread
from ..__utils__ import Location

__all__ = (
    "SolarDataThread",
    "solar_degradation",
    "SOLAR_LOGGER_NAME",
    "total_solar_output",
)


# Solar logger name:
#   The name to use for the solar logger.
SOLAR_LOGGER_NAME = "solar_generation"


def solar_degradation(lifetime: int) -> pd.DataFrame:
    """
    Calculates the solar degredation.

    Inputs:
        - lifetime:
            The lifetime of the solar setup in years.

    Outputs:
        - The lifetime degredation of the solar setup.

    """

    # lifetime = self.input_data.loc["lifetime"]
    hourly_degradation = 0.20 / (lifetime * 365 * 24)
    lifetime_degradation = []

    for i in range((20 * 365 * 24) + 1):
        equiv = 1.0 - i * hourly_degradation
        lifetime_degradation.append(equiv)

    return pd.DataFrame(lifetime_degradation)


def total_solar_output(
    generation_directory: str, regenerate: bool, start_year: int = 2007
) -> pd.DataFrame:
    """
    Generates 20 years of solar output data by taking 10 consecutive years repeated.

    Inputs:
        - generation_directory:
            The directory in which generated solar profiles are saved.
        - regenerate:
            Whether to regenerate the profiles.
        - start_year:
            The year for which to begin the simulation.
    Outputs:
        .csv file for twenty years of PV output data
    """

    output = pd.DataFrame([])

    total_solar_output_filename = os.path.join(
        generation_directory, "solar_generation_20_years.csv"
    )

    # If the total solar output file already exists then simply read this in.
    if os.path.isfile(total_solar_output_filename) and not regenerate:
        with open(total_solar_output_filename, "r") as f:
            output = pd.read_csv(f, header=None, index_col=0)

    else:
        # Get data for each year using iteration, and add that data to the output file
        for year_index in tqdm(
            np.arange(10), desc="total solar profile", leave=True, unit="year"
        ):
            iteration_year = start_year + year_index
            with open(
                os.path.join(
                    generation_directory, f"solar_generation_{iteration_year}.csv"
                ),
                "r",
            ) as f:
                iteration_year_data = pd.read_csv(
                    f,
                    header=None,  # type: ignore
                    index_col=0,
                )
            output = pd.concat([output, iteration_year_data], ignore_index=True)

        # Repeat the initial 10 years in two consecutive periods
        output = pd.concat([output, output], ignore_index=True)
        with open(total_solar_output_filename, "w") as f:
            output.to_csv(
                f,  # type: ignore
                header=None,  # type: ignore
            )

    return output


class SolarDataThread(
    BaseRenewablesNinjaThread, profile_name="solar", profile_key="pv"
):
    """
    Class to use when calling the solar data thread.

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
