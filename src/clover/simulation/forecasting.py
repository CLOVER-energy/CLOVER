########################################################################################
# forecasting.py - Forecast generation module.                                         #
#                                                                                      #
########################################################################################

"""
forecasting.py - The forecast module for CLOVER.

"description"
"""

import os

from logging import Logger
from typing import DefaultDict, Union

import pandas as pd
import numpy as np

__all__ = ()


def _get_forecast_accuracy(
    forecast_accuracies: pd.DataFrame,
    max_years,
) -> pd.DataFrame:

    if forecast_accuracies.empty:
        raise ValueError("forecast_accuracies is empty.")
    elif forecast_accuracies.shape != (24, 12):
        import pdb

        pdb.set_trace()
        raise ValueError("forecast_accuracies is wrong shape")

    # build hourly df for forecast corrections
    hours_total = 365 * max_years * 24

    probs = forecast_accuracies.to_numpy(dtype=float)
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    # TODO: leap years not yet considered

    p_one_year = []
    for m, days in enumerate(days_in_month):
        month_hour_probs = probs[:, m]
        p_one_year.extend(np.tile(month_hour_probs, days))

    p_one_year = np.asarray(p_one_year, dtype=float)
    p_all = np.tile(p_one_year, max_years)
    # X ~ B(n = 1, p = forecast_accuracies)
    simulated = np.random.binomial(n=1, p=p_all, size=hours_total)

    return simulated


def calculate_true_solar(
    forecast_accuracies_filepath: str,
    generation_directory: str,
    logger,
    max_years: int,
    pv_produced: pd.DataFrame,
):
    # if modified curve csv already exists in auto_generated folder, read that and return
    filename = os.path.join(generation_directory, f"true_solar_output.csv")
    if os.path.isfile(filename):
        with open(filename, "r") as f:
            true_solar_profile = pd.read_csv(f, index_col=0)
        logger.info(
            "True solar profile successfully read from file %s",
            filename,
        )
        return true_solar_profile

    # otherwise:
    # make forecast_accuracies probability df from forecast_accuracies.csv
    with open(
        forecast_accuracies_filepath,
        "r",
    ) as forecast_accuracies_file:
        forecast_accuracies: pd.DataFrame = pd.read_csv(
            forecast_accuracies_file, sep="\t", header=None
        )
        logger.info("Forecast accuracies successfully parsed.")

    # make hourly booleans from get_forecast_accuracy
    accurate_times = _get_forecast_accuracy(forecast_accuracies, max_years)

    # make alternative solar profile
    hours_in_a_year = 8760
    true_solar_profile = pv_produced.copy()
    # if 1 in accurate_times, keep data from pv_produced, pass
    # otherwise, it is 0, take data from the another year for that hour,
    inaccurate_hours = np.where(accurate_times == 0)[0]
    inaccurate_hours_iter = ((k, t) for k, t in enumerate(inaccurate_hours))

    # precompute per-index year and hour-of-year
    years = inaccurate_hours // hours_in_a_year
    hour_of_year = inaccurate_hours % hours_in_a_year

    rng = np.random.default_rng()

    for k, t in inaccurate_hours_iter:
        y = years[k]
        h = hour_of_year[k]
        alt_year = rng.choice([i for i in range(0, max_years) if i != y])

        replacement_hour = alt_year * hours_in_a_year + h
        true_solar_profile.loc[t] = pv_produced.loc[replacement_hour]

    # save the data
    true_solar_profile.to_csv(
        os.path.join(generation_directory, f"true_solar_output.csv")
    )
    # return the modified solar curve
    return true_solar_profile
