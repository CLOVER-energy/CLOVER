# -*- coding: utf-8 -*-
"""
===============================================================================
                            SOLAR GENERATION FILE
===============================================================================
                            Most recent update:
                             19 November 2019
===============================================================================
Made by:
    Philip Sandwell
Additional credits:
    Iain Staffell, Stefan Pfenninger & Scot Wheeler
For more information, please email:
    philip.sandwell@googlemail.com
===============================================================================
"""
import json
import os

from typing import Optional

import numpy as np
import pandas as pd
import requests

__all__ = (
    "get_solar_output",
    "save_solar_output",
    "solar_degradation",
    "total_solar_output",
)


def _get_solar_generation_from_rn(self, year=2014):
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
        - year
            The year for which to fetch data, valid values are from 2000-2016 inclusive.
        - pv_generation_inputs
            Input file data with location latitude, longitude, tilt angle and azimuth.
        - token
            Renewables Ninja API token

    Outputs:
        PV output data in kW/kWp in UTC time

    Notes:
        Data produced is not in local time.

    """

    # Access information
    api_base = "https://www.renewables.ninja/api/"
    session = requests.session()
    url = api_base + "data/pv"
    token = str(self.location_input_data.loc["token"])
    session.headers = {"Authorization": "Token " + token}

    # Gets some data from input file
    args = {
        "lat": float(self.location_input_data.loc["Latitude"]),
        "lon": float(self.location_input_data.loc["Longitude"]),
        "date_from": str(year) + "-01-01",
        "date_to": str(year) + "-12-31",
        "dataset": "merra2",
        "capacity": 1.0,
        "system_loss": 0,
        "tracking": 0,
        "tilt": float(self.input_data.loc["tilt"]),
        "azim": float(self.input_data.loc["azim"]),
        "format": "json",
        # Metadata and raw data now supported by different function in API
        #            'metadata': False,
        #            'raw': False
    }
    session_url = session.get(url, params=args)

    # Parse JSON to get a pandas.DataFrame
    parsed_response = json.loads(session_url.text)
    data_frame = pd.read_json(json.dumps(parsed_response["data"]), orient="index")
    data_frame = data_frame.reset_index(drop=True)

    # Remove leap days
    if year in {2004, 2008, 2012, 2016, 2020}:
        feb_29 = (31 + 28) * 24
        data_frame = data_frame.drop(range(feb_29, feb_29 + 24))
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


def get_solar_output(time_difference: float, gen_year: int = 2014) -> pd.DataFrame:
    """
    Generates solar data from Renewables Ninja and returns it in a DataFrame.

    Inputs:
        - gen_year
            The year for which to fetch the data.

    Outputs:
        - The generated solar data for the year.

    """

    # Get input data from "Location data" file
    time_dif = float(time_difference)

    # Get solar output in local time for the given year
    solar_output = _get_solar_local_time(
        _get_solar_generation_from_rn(gen_year), time_difference=time_dif
    )

    return solar_output


def save_solar_output(
    generation_directory: str,
    gen_year: int,
    solar_data: pd.DataFrame,
    filename: Optional[str] = None,
) -> None:
    """
    Saves PV generation data as a named .csv file in the location generation file.

    Inputs:
        - generation_directory:
            The directory in which the data file should be saved.
        - gen_year:
            The year for which the data was generated.
        - solar_data:
            The generated solar-data DataFrame to be saved in the CSV file.
        - filename:
            The filename to use, which can be `None` and auto-generated from the year.

    """

    if filename is None:
        filename = f"solar_generation_{gen_year}.csv"

    solar_data.to_csv(
        os.path.join(generation_directory, filename),
        header=False,
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


def total_solar_output(generation_directory: str, start_year: int = 2007):
    """
    Generates 20 years of solar output data by taking 10 consecutive years repeated.

    Inputs:
        - generation_directory:
            The directory in which generated solar profiles are saved.
        - start_year:
            The year for which to begin the simulation.
    Outputs:
        .csv file for twenty years of PV output data
    """

    output = pd.DataFrame([])

    # Get data for each year using iteration, and add that data to the output file
    for i in np.arange(10):
        iteration_year = start_year + i
        iteration_year_data = pd.read_csv(
            os.path.join(
                generation_directory, f"solar_generation_{iteration_year}.csv"
            ),
            header=False,
            index_col=0,
        )
        output = pd.concat([output, iteration_year_data], ignore_index=True)

    # Repeat the initial 10 years in two consecutive periods
    output = pd.concat([output, output], ignore_index=True)
    output.to_csv(
        os.path.join(generation_directory, "solar_generation_20_years.csv"),
        header=False,
    )


# class Solar:
#     def __init__(self):
#         self.location = "Bahraich"
#         self.CLOVER_filepath = os.getcwd()
#         self.location_filepath = os.path.join(
#             self.CLOVER_filepath, LOCATIONS_FOLDER_NAME, self.location
#         )
#         self.generation_filepath = os.path.join(
#             self.location_filepath, "Generation", "PV"
#         )
#         self.input_data = pd.read_csv(
#             os.path.join(self.generation_filepath, "PV generation inputs.csv"),
#             header=None,
#             index_col=0,
#         )[1]
#         self.location_data_filepath = os.path.join(
#             self.location_filepath, "Location Data"
#         )
#         self.location_input_data = pd.read_csv(
#             os.path.join(self.location_data_filepath, "Location inputs.csv"),
#             header=None,
#             index_col=0,
#         )[1]
