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

import os

from logging import Logger
from typing import Dict

import pandas as pd  # pylint: disable=import-error

from tqdm import tqdm

from ..__utils__ import BColours, Location, monthly_times_to_daily_times, SKIPPING
from ..conversion.conversion import WaterSource

__all__ = ("get_lifetime_water_source_status",)


def _process_water_source_availability(
    water_source: WaterSource,
    *,
    availability: pd.DataFrame,
    generated_water_source_availability_directory: str,
    keyword: str,
    location: Location,
    logger: Logger,
    regenerate: bool,
) -> pd.DataFrame:
    """
    Process water-source data files.

    Processes the water-source data files, taking the availability probabilities and
    converting them to a :class:`pd.DataFrame` giving the availability of the water
    source for every hour of the simulation.

    Inputs:
        - water_source:
            The data for the :class:`conversion.WaterSource` to be processed.
        - availability:
            A :class:`pandas.DataFrame` giving the availability of the
            :class:`WaterSource` being considered.
        - generated_water_source_availability_directory:
            The directory in which to store the generated water-source availability
            profiles.
        - keyword:
            A `str` used for differentiating the different types of conventional source
            when printing or making log calls.
        - location:
            The location currently being considered.
        - logger:
            The logger to use for the run.
        - regenerate:
            Whether to force-regenerate the profiles.

    Outputs:
        - The interpolated daily availability profile for each water source.

    """

    logger.info(
        "Water-source availability process instantiated for %s water-source %s.",
        keyword,
        water_source.name,
    )

    daily_times_filename = f"{water_source.name}_daily_times.csv"
    filepath = os.path.join(
        generated_water_source_availability_directory, daily_times_filename
    )

    # If the file already exists, simply read in the data.
    if os.path.isfile(filepath) and not regenerate:
        with open(filepath, "r") as f:
            interpolated_daily_profile = pd.read_csv(f, header=None)
        logger.info(
            "Daily %s water-source availability profile for %s successfully read from "
            "file %s.",
            keyword,
            water_source.name,
            filepath,
        )

    else:
        logger.info(
            "Computing %s water-source availability profile for %s.",
            keyword,
            water_source.name,
        )
        interpolated_daily_profile = monthly_times_to_daily_times(
            availability,
            location.max_years,
        )
        logger.info(
            "Daily %s water-source availability profile for %s successfully computed.",
            keyword,
            water_source.name,
        )

        # Save this to the output file.
        with open(filepath, "w") as f:
            interpolated_daily_profile.to_csv(
                f, header=None, index=False, line_terminator=""  # type: ignore
            )
        logger.info(
            "Daily %s water-source availability profile for %s successfully saved to "
            "%s.",
            keyword,
            water_source.name,
            daily_times_filename,
        )

    return interpolated_daily_profile


def _process_water_soure_hourly_probability(
    water_source: WaterSource,
    *,
    daily_water_source_availability: pd.DataFrame,
    generated_water_source_availability_directory: str,
    keyword: str,
    logger: Logger,
    regenerate: bool,
) -> pd.DataFrame:
    """
    Calculate the probability that the water source is available at any given time.

    Inputs:
        - water_source:
            The data for the :class:`conversion.WaterSource` to be processed.
        - availability:
            A :class:`pandas.DataFrame` giving the availability of the
            :class:`WaterSource` being considered.
        - generated_water_source_availability_directory:
            The directory in which to store the generated water-source availability
            profiles.
        - keyword:
            A `str` used for differentiating the different types of conventional source
            when printing or making log calls.
        - logger:
            The logger to use for the run.
        - regenerate:
            Whether to force-regenerate the profiles.
        - years:
            The number of years for which the simulation is being run.

    Outputs:
        - The hourly availability of the conventional :class:`WaterSource` specified as
        a :class:`pandas.DataFrame`.

    """

    filename = f"{water_source.name}_availability.csv"
    filepath = os.path.join(generated_water_source_availability_directory, filename)

    # If the device hourly usage already exists, then read the data in from the file.
    if os.path.isfile(filepath) and not regenerate:
        with open(filepath, "r") as f:
            hourly_availability = pd.read_csv(f, header=None)
        logger.info(
            "Hourly %s water-source availability for %s successfully read from file: "
            "%s",
            keyword,
            water_source.name,
            filepath,
        )

    else:
        daily_water_source_availability = daily_water_source_availability.reset_index(
            drop=True
        )

        # Calculate the hourly-usage profile.
        logger.info("Calculating probability of %s availability", water_source.name)
        try:
            hourly_availability = pd.concat(
                [
                    daily_water_source_availability[column]
                    for column in daily_water_source_availability.columns
                ],
                axis=0,
            )
        except ValueError as e:
            logger.error(
                "%sError computing hourly %s water-source availability usage profile "
                "for %s: type error in variables: %s%s",
                BColours.fail,
                keyword,
                water_source.name,
                str(e),
                BColours.endc,
            )
            raise

        hourly_availability = hourly_availability.reset_index(drop=True)

        logger.info(
            "Hourly %s water-source availability profile for %s successfully "
            "calculated.",
            keyword,
            water_source.name,
        )

        # Save the hourly-usage profile.
        logger.info(
            "Saving hourly %s water-source availability profile for %s.",
            keyword,
            water_source.name,
        )

        with open(
            filepath,
            "w",
        ) as f:
            hourly_availability.to_csv(
                f, header=None, index=False, line_terminator=""  # type: ignore
            )

        logger.info(
            "Hourly %s water-source availability proifle for %s successfully saved to "
            "%s.",
            keyword,
            water_source.name,
            filename,
        )

    return hourly_availability


def get_lifetime_water_source_status(
    disable_tqdm: bool,
    generation_directory: str,
    keyword: str,
    location: Location,
    logger: Logger,
    regenerate: bool,
    water_source_times: Dict[WaterSource, pd.DataFrame],
) -> Dict[WaterSource, pd.DataFrame]:
    """
    Calculates, and saves, the water-source availability profiles of all input types.

    Inputs:
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - generation_directory:
            The directory in which auto-generated files should be saved.
        - keyword:
            A `str` used for differentiating the different types of conventional source
            when printing or making log calls.
        - location:
            The :class:`Location` being considered.
        - logger:
            The logger to use for the run.
        - max_years:
            The maximum number of years for which the simulation should run.
        - regenerate:
            Whether to renerate (True) the profiles or use existing profiles if present
            (False).
        - water_source_timess:
            Water-source inputs information, read from the water-source inputs file and
            directory, stored as a mapping between :class:`WaterSource` instances,
            representing the conventional :class:`WaterSource`s available to the system,
            and :class:`pandas.DataFrame` instances giving their availability profiles.

    Outputs:
        - water_source_profiles:
            A dictionary mapping the water-source name to its associated maximum-output
            profile.

    """

    water_source_profiles: Dict[WaterSource, pd.DataFrame] = {}

    # Do not compute conventional profiles if there are none available.
    if len(water_source_times) == 0:
        tqdm.write(
            f"No conventional {keyword} water profiles defined "
            + "." * (35 - (len(keyword) + len(SKIPPING)))
            + f"    {SKIPPING}"
        )
        return water_source_profiles

    for source, availability in tqdm(
        water_source_times.items(),
        desc=f"conventional {keyword} water availability",
        disable=disable_tqdm,
        leave=True,
        unit="source",
    ):
        # Transform the profiles into daily profiles by interpolating across the months.
        interpolated_daily_profile = _process_water_source_availability(
            source,
            availability=availability,
            generated_water_source_availability_directory=os.path.join(
                generation_directory, "available_times"
            ),
            keyword=keyword,
            location=location,
            logger=logger,
            regenerate=regenerate,
        )

        # Compute the hourly water-source availability profile.
        hourly_availability = _process_water_soure_hourly_probability(
            source,
            daily_water_source_availability=interpolated_daily_profile,
            generated_water_source_availability_directory=os.path.join(
                generation_directory, "available_probability"
            ),
            keyword=keyword,
            logger=logger,
            regenerate=regenerate,
        )

        water_source_profiles[source] = (
            hourly_availability * source.maximum_output_capacity
        )

    return water_source_profiles
