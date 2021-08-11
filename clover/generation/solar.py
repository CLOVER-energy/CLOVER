#!/usr/bin/python3
########################################################################################
# solar.py - Solar generation module  .                                                #
#                                                                                      #
# Author: Phil Sandwell                                                                #
# Copyright: Phil Sandwell, 2021                                                       #
# License: Open source                                                                 #
# Most recent update: 14/07/2021                                                       #
#                                                                                      #
# Additional credits:                                                                  #
#     Iain Staffell, Stefan Pfenninger & Scot Wheeler                                  #
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

from ..__utils__ import BColours, get_logger, InputFileError, Location

__all__ = (
    "get_solar_output",
    "save_solar_output",
    "SolarDataThread",
    "solar_degradation",
    "SOLAR_LOGGER_NAME",
    "total_solar_output",
)


# Renewables.ninja sleep time:
#   To avoid being locked out of the renewables.ninja API, it is necessary for CLOVER to
#   sleep between requests. The time taken for this, in seconds, is set below.
RENEWABLES_NINJA_SLEEP_TIME = 12

# Solar logger name:
#   The name to use for the solar logger.
SOLAR_LOGGER_NAME = "solar_generation"


def _get_solar_generation_from_rn(
    location: Location,
    logger: Logger,
    solar_generation_inputs: Dict[Any, Any],
    year=2014,
):
    """
    Gets data from Renewables.ninja for a given year (kW/kWp) in UTC time

    Credit:
        Renewables.ninja, API interface and all data accessed by this function by Iain
            Staffell & Stefan Pfenninger.
        Python code from:
            https://www.renewables.ninja/documentation/api/python-example
        Cite these papers in your documents!
            - S. Pfenninger and I. Staffell, 2016. Long-term patterns of European PV
              output using 30 years of validated hourly reanalysis and satellite data.
              Energy, 114, 1251–1265.
            - I. Staffell and S. Pfenninger, 2016. Using Bias-Corrected Reanalysis to
              Simulate Current and Future Wind Power Output. Energy, 114, 1224–1239.
        Adapted from code by Scot Wheeler

    Inputs:
        - location:
            The location currently being considered.
        - logger:
            The logger to use for the run.
        - solar_generation_inputs:
            Input file data with tilt angle, azimuthal angle and the renewables.ninja
            API token.
        - year:
            The year for which to fetch data, valid values are from 2000-2016 inclusive.

    Outputs:
        PV output data in kW/kWp in UTC time

    Notes:
        Data produced is not in local time.

    """

    # Access information
    api_base = "https://www.renewables.ninja/api/"
    session = requests.session()
    url = api_base + "data/pv"
    try:
        session.headers = requests.structures.CaseInsensitiveDict(
            {"Authorization": "Token " + str(solar_generation_inputs["token"])}
        )
    except TypeError as e:  # pylint: disable=invalid-name
        logger.error(
            "The token specified was of the incorrect type. Check the solar-generation "
            "inputs file: %s",
            str(e),
        )
        raise

    # Gets some data from input file
    args = {
        "lat": float(location.latitude),
        "lon": float(location.longitude),
        "date_from": str(year) + "-01-01",
        "date_to": str(year) + "-12-31",
        "dataset": "merra2",
        "capacity": 1.0,
        "system_loss": 0,
        "tracking": 0,
        "tilt": float(solar_generation_inputs["tilt"]),
        "azim": float(solar_generation_inputs["azimuthal_orientation"]),
        "format": "json",
        # Metadata and raw data now supported by different function in API
        #            'metadata': False,
        #            'raw': False
    }
    session_url = session.get(url, params=args)  # type: ignore

    # Parse JSON to get a pandas.DataFrame
    try:
        parsed_response = json.loads(session_url.text)
    except JSONDecodeError as e:  # pylint: disable=invalid-name
        logger.error(
            "%sFailed to parse renewables.ninja data. Check that you correctly specified "
            "your API key: %s%s",
            BColours.fail,
            str(e),
            BColours.endc,
        )
        raise InputFileError(
            "solar inputs",
            "Failed to parse renewables.ninja data. Check that you correctly specified "
            "your API key",
        ) from None

    data_frame = pd.read_json(json.dumps(parsed_response["data"]), orient="index")
    data_frame = data_frame.reset_index(drop=True)

    # Remove leap days
    if year % 4 == 0:
        feb_29 = (31 + 28) * 24
        data_frame = data_frame.drop(list(range(feb_29, feb_29 + 24)))  # type: ignore
        data_frame = data_frame.reset_index(drop=True)
    return data_frame


def _get_solar_local_time(solar_data_utc: pd.DataFrame, time_difference: float = 0):
    """
    Converts data from Renewables.ninja (kW/kWp in UTC time) to user-defined local time.

    Inputs:
        - solar_data_utc
            Solar data in UTC.
        - time_difference
            The desired time zone difference.

    Outputs:
        PV output data (kW/kWp) in local time

    """

    #   Round time difference to nearest hour (NB India, Nepal etc. do not do this)
    time_difference = round(time_difference)

    # East of Greenwich
    if time_difference > 0:
        splits = np.split(solar_data_utc, [len(solar_data_utc) - time_difference])
        solar_data_local = pd.concat([splits[1], splits[0]], ignore_index=True)
    # West of Greenwich
    elif time_difference < 0:
        splits = np.split(solar_data_utc, [abs(time_difference)])
        solar_data_local = pd.concat([splits[1], splits[0]], ignore_index=True)
    # No time difference, included for completeness
    else:
        solar_data_local = solar_data_utc

    return solar_data_local


def get_solar_output(
    location: Location,
    logger: Logger,
    solar_generation_inputs: Dict[Any, Any],
    gen_year: int = 2014,
) -> pd.DataFrame:
    """
    Generates solar data from Renewables Ninja and returns it in a DataFrame.

    Inputs:
        - location:
            The location currently being considered.
        - logger:
            The logger to use for the run.
        - solar_generation_inputs:
            The solar-generation inputs, extracted from the input file.
        - gen_year
            The year for which to fetch the data.

    Outputs:
        - The generated solar data for the year.

    """

    # Get solar output in local time for the given year
    solar_output = _get_solar_local_time(
        _get_solar_generation_from_rn(
            location, logger, solar_generation_inputs, gen_year
        ),
        time_difference=float(location.time_difference),
    )

    return solar_output


def save_solar_output(
    filepath: str,
    gen_year: int,
    logger: Logger,
    solar_data: pd.DataFrame,
) -> None:
    """
    Saves PV generation data as a named .csv file in the location generation file.

    Inputs:
        - filepath:
            The path to save the file to, including the directory in which the data file
            should be saved and the filename to use.
        - gen_year:
            The year for which the data was generated.
        - logger:
            The logger to use for the run.
        - solar_data:
            The generated solar-data DataFrame to be saved in the CSV file.

    """

    solar_data.to_csv(
        filepath,
        header=None,  # type: ignore
    )

    logger.info(
        "Solar output data for year %s successfully saved to %s.", gen_year, filepath
    )


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


class SolarDataThread(threading.Thread):
    """
    A :class:`threading.Thread` child for running solar-data fetching in the background.

    .. attribute:: auto_generated_files_directory
        The directory in which CLOVER-generated files should be saved.

    .. attribute:: location
        The location currently being considered.

    .. attribute:: logger
        The :class:`logging.Logger` to use for the run.

    .. attribute:: regenerate
        Whether the profiles are to be regenerated, i.e., re-fetched from the
        renewables.ninja API (True) or whether existing profiles should be used if
        present (False).

    .. attribute:: solar_generation_inputs:
        The solar-generation inputs information, extracted from the
        solar-generation-inputs file.

    """

    def __init__(
        self,
        auto_generated_files_directory: str,
        location: Location,
        regenerate: bool,
        solar_generation_inputs: Dict[Any, Any],
    ) -> None:
        """
        Instantiate a solar-data thread.

        Inputs:
            - auto_generated_files_directory:
                The directory in which CLOVER-generated files should be saved.
            - location:
                The location currently being considerted.
            - regenerate:
                Whether to regenerate the profiles.
            - solar_generation_inputs:
                The solar-generation inputs.

        """

        self.auto_generated_files_directory: str = auto_generated_files_directory
        self.location: Location = location
        self.logger: Logger = get_logger(SOLAR_LOGGER_NAME)
        self.regenerate: bool = regenerate
        self.solar_generation_inputs: Dict[Any, Any] = solar_generation_inputs

        super().__init__()

    def run(
        self,
    ) -> None:
        """
        Execute a solar-data thread.

        """

        self.logger.info("Solar data thread instantiated.")

        # A counter is used to keep track of calls to renewables.ninja to prevent
        # overloading.
        try:
            for year in tqdm(
                range(
                    self.solar_generation_inputs["start_year"],
                    self.solar_generation_inputs["end_year"] + 1,
                ),
                desc="solar profiles",
                unit="year",
            ):
                # If the solar-data file for the year already exists, skip.
                filename = f"solar_generation_{year}.csv"
                filepath = os.path.join(self.auto_generated_files_directory, filename)

                if os.path.isfile(filepath) and not self.regenerate:
                    self.logger.info(
                        "Solar data file for year %s already exists, skipping.", year
                    )
                    continue

                self.logger.info("Fetching solar data for year %s.", year)
                try:
                    solar_data = get_solar_output(
                        self.location,
                        self.logger,
                        self.solar_generation_inputs,
                        year,
                    )
                except KeyError as e:  # pylint: disable=invalid-name
                    self.logger.error("Missing data from input files: %s", str(e))
                    raise

                self.logger.info("Solar data successfully fetched, saving.")
                save_solar_output(
                    filepath,
                    year,
                    self.logger,
                    solar_data,
                )

                # The system waits to prevent overloading the renewables.ninja API and being
                # locked out.
                if year != self.solar_generation_inputs["end_year"]:
                    time.sleep(RENEWABLES_NINJA_SLEEP_TIME)

        except Exception:
            self.logger.error(
                "Error occured in solar-profile fetching. See %s for details.",
                "/logs/{}".format(SOLAR_LOGGER_NAME),
            )
            raise
