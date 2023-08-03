#!/usr/bin/python3
########################################################################################
# __utils__.py - Hourly-source profile generation module.                              #
#                                                                                      #
# Author: Phil Sandwell, Ben Winchester                                                #
# Copyright: Phil Sandwell, 2018                                                       #
# License: Open source                                                                 #
# Most recent update: 01/11/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
__utils__.py - The hourly-source profile generation utility module.

This module generates availability profiles for sources which specify an hourly
availability profile such as a grid connection or other source with an intermittent and
seasonal supply.

"""

import os
import random

from logging import Logger
from typing import Dict, List

import pandas as pd  # pylint: disable=import-error

from tqdm import tqdm  # pylint: disable=import-error

__all__ = ("get_intermittent_supply_status",)


def get_intermittent_supply_status(  # pylint: disable=too-many-locals
    disable_tqdm: bool,
    generation_directory: str,
    inputs_directory_relative_path: str,
    keyword: str,
    logger: Logger,
    max_years: int,
    profile_inputs: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    """
    Computes the availability profiles for an intermittent supply.

    Inputs:
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - generation_directory:
            The directory into which the generated inputs should be saved.
        - keyword:
            A `str` giving the profile keying information.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - max_years:
            The maximum number of years for which the simulation should be run and for
            which the profiles should be generated.
        - profile_inputs:
            Profile input information, read from the relevant input file.

    Outputs:
        - A mapping between the profile name and its hourly availability.

    """

    # Extract the profile names from the dataframe.
    profile_types: List[str] = list(profile_inputs)

    # Set up a holder dictionary to contain the grid information.
    profiles: Dict[str, pd.DataFrame] = {}

    # Loop through all the various grid profiles that have been defined.
    for index in tqdm(
        range(profile_inputs.shape[1]),
        desc=f"{keyword} profiles",
        disable=disable_tqdm,
        leave=True,
        unit=keyword,
    ):
        name = profile_types[index]
        filename = os.path.join(generation_directory, f"{name}_{keyword}_status.csv")

        # If the profile already exists, simply read from the file.
        if os.path.isfile(filename):
            with open(filename, "r") as f:
                times = pd.read_csv(f)
            profiles[name] = times
            logger.info(
                "Availability profile for %s::%s successfully read from file %s",
                keyword,
                name,
                filename,
            )
            continue

        logger.info("No existing profile found for %s::%s, generating.", keyword, name)

        hours = pd.DataFrame(profile_inputs[profile_types[index]])
        status = []
        for _ in range(365 * int(max_years)):
            for hour in range(hours.size):
                if random.random() < hours.iloc[hour].values:
                    status.append(1)
                else:
                    status.append(0)
        times = pd.DataFrame(status)

        attributes_filename = os.path.join(
            inputs_directory_relative_path, f"{name}_grid_attributes.csv"
        )
        grid_attributes: pd.DataFrame = pd.read_csv(attributes_filename)

        # Blackout times, the list of hours for which the times occur (z_indicies)
        zero_indices = times.index[times.iloc[:, 0] == 0]
        blackout_times: List[int] = zero_indices.tolist()
        blackout_hours: List[int] = grid_attributes.iloc[zero_indices % 24, 1].tolist()

        # Create a mapping between the hour and the times
        time_to_length_mapping: dict[int, int] = {
            hour: blackout_hours[index] for index, hour in enumerate(blackout_times)
        }

        # Create a blank mappnig to include the hours and times that need including.
        blackout_times_to_include: dict[int, int] = {}

        # Loop through and determine which hours should be included.
        for blackout_time in blackout_times:
            for hour, length in {
                hour: length
                for hour, length in blackout_times_to_include.items()
                if hour < blackout_time
            }.items():
                if blackout_time < hour + length:
                    break
            else:
                blackout_times_to_include[blackout_time] = time_to_length_mapping[
                    blackout_time
                ]

        for blackout_time, length in blackout_times_to_include.items():
            times.iloc[blackout_time : blackout_time + length, :] = 0

        profiles[name] = times
        logger.info(
            "Availability profile for %s::%s successfully generated.", keyword, name
        )

        with open(filename, "w") as f:
            times.to_csv(f)  # type: ignore
        logger.info(
            "Availability profile for %s::%s successfullly saved to %s.",
            keyword,
            name,
            filename,
        )

    return profiles
