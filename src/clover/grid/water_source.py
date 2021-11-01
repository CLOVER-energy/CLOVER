#!/usr/bin/python3
########################################################################################
# water_source.py - Water source profile generation module.                            #
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
water_source.py - The water-source generation module for CLOVER.

This module generates availability profiles for conventional water sources for CLOVER.

"""

from logging import Logger
from typing import Dict

import pandas as pd  # type: ignore # pylint: disable=import-error

from .__utils__ import get_intermittent_supply_status
from ..conversion.conversion import WaterSource

__all__ = ("get_lifetime_water_source_status",)


def _process_water_source_availability(
    water_source: WaterSource,
    *,
    generated_water_source_availability_directory: str,
    location: Location,
    logger: Logger,
    regenerate: bool,
    water_source_times: Dict[WaterSource, pd.DataFrame],
) -> pd.DataFrame:
    """
    Process water-source data files.

    Processes the water-source data files, taking the availability probabilities and
    converting them to a :class:`pd.DataFrame` giving the availability of the water
    source for every hour of the simulation.

    Inputs:
        - water_source:
            The data for the :class:`conversion.WaterSource` to be processed.
        - generated_device_utilisation_directory:
            The directory in which to store the generated device-utilisation profiles.
        - location:
            The location currently being considered.
        - logger:
            The logger to use for the run.
        - regenerate:
            Whether to force-regenerate the profiles.
        - water_source_times:
            The set of water-source availabilities to process.

    Outputs:
        - The interpolated daily availability profile for each water source.

    """

    logger.info(
        "Water-source availability process instantiated for water-source %s.",
        water_source.name,
    )

    daily_times_filename = f"{water_source.name}_daily_times.csv"
    filepath = os.path.join(
        generated_device_utilisation_directory, daily_times_filename
    )

    # If the file already exists, simply read in the data.
    if os.path.isfile(filepath) and not regenerate:
        with open(filepath, "r") as f:
            interpolated_daily_profile = pd.read_csv(f, header=None)
        logger.info(
            "Daily water-source availability profile for %s successfully read from "
            "file %s.",
            water_source.name,
            filepath,
        )

    else:
        logger.info(
            "Computing water-source availability profile for %s.", water_source.name
        )
        interpolated_daily_profile = monthly_times_to_daily_times(
            water_source_times[water_source],
            location.max_years,
        )
        logger.info(
            "Daily water-source availability profile for %s successfully computed.",
            water_source.name,
        )

        # Save this to the output file.
        with open(filepath, "w") as f:
            interpolated_daily_profile.to_csv(f, header=None, index=False, line_terminator="")  # type: ignore
        logger.info(
            "Daily water-source availability profile for %s successfully saved to %s.",
            water_source_times.name,
            daily_times_filename,
        )

    return interpolated_daily_profile


def get_lifetime_water_source_status(
    generation_directory: str,
    logger: Logger,
    max_years: int,
    water_source: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    """
    Calculates, and saves, the water-source availability profiles of all input types.

    Inputs:
        - generation_directory:
            The directory in which auto-generated files should be saved.
        - water_source_inputs:
            Water-source inputs information, read from the water-source inputs file.
        - logger:
            The logger to use for the run.
        - max_years:
            The maximum number of years for which the simulation should run.

    Outputs:
        - water_source_profiles:
            A dictionary mapping the water-source name to its associated availability
            profile.

    """

    #
