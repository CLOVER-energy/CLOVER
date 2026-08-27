########################################################################################
# forecasting.py - Forecast generation module.                                         #
#                                                                                      #
########################################################################################

"""
forecasting.py - The forecast module for CLOVER.

This module generates the modified solar irradiance curve, to account for errors in
weather forecast accuracy
"""

import os

import pandas as pd
import numpy as np

__all__ = "calculate_true_solar"


def calculate_true_solar(
    forecast_accuracies_filepath: str,
    generation_directory: str,
    logger,
    max_years: int,
    pv_produced: pd.DataFrame,
) -> pd.DataFrame:
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
    if len(forecast_accuracies) != 12:
        raise ValueError(
            "forecast_accuracies.csv must contain exactly 12 rows: one value for each month of the year."
        )
    logger.info("Forecast accuracies successfully parsed.")

    # calculate daily anomalies
    daily_mean_pv = np.mean(
        np.reshape(pv_produced.values, (365 * max_years, 24)), axis=1
    )
    climatological_mean = np.mean(daily_mean_pv)
    daily_anom = daily_mean_pv - np.full(len(daily_mean_pv), climatological_mean)

    # calculate correlation coefficients, between months
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    total_num_months = 12 * max_years
    corr_matrix = np.ones((total_num_months, total_num_months), dtype=float)
    rms_matrix = np.zeros((total_num_months, total_num_months), dtype=float)

    monthly_idx = []
    start = 0
    for _ in range(max_years):
        for days in days_in_month:
            # monthly_idx.append(daily_anom[start : start + days])
            monthly_idx.append(range(start, (start + days)))
            start += days

    for fcst_month in range(total_num_months):
        x_days = monthly_idx[fcst_month]
        x = daily_anom[x_days]  # data in forecast month
        for obs_month in range(fcst_month + 1, total_num_months):
            if obs_month == fcst_month:  # if same month, keep correlation as 1
                continue

            y_days = monthly_idx[obs_month]
            y = daily_anom[y_days]
            num_days = min(len(x), len(y))
            corr = np.corrcoef(x[:num_days], y[:num_days])[0, 1]
            rms = np.sqrt(np.mean((x[:num_days]) ** 2)) - np.sqrt(
                np.mean((y[:num_days]) ** 2)
            )

            if len(y) < len(x):
                corr_matrix[fcst_month, obs_month] = np.nan
                corr_matrix[obs_month, fcst_month] = corr
                rms_matrix[fcst_month, obs_month] = np.nan
                rms_matrix[obs_month, fcst_month] = rms
                continue
            elif len(x) < len(y):
                corr_matrix[fcst_month, obs_month] = corr
                corr_matrix[obs_month, fcst_month] = np.nan
                rms_matrix[fcst_month, obs_month] = rms
                rms_matrix[obs_month, fcst_month] = np.nan
                continue
            corr_matrix[fcst_month, obs_month] = corr
            corr_matrix[obs_month, fcst_month] = corr
            rms_matrix[fcst_month, obs_month] = rms
            rms_matrix[obs_month, fcst_month] = rms

    # synthesise profile that best fits forecast_accuracies.csv values
    true_solar_profile = pv_produced.copy()
    heatmap_matrix = np.zeros((12, 12))
    for fcst_month in range(total_num_months):
        # find replacement month
        month_of_year = fcst_month % 12
        target_corr = forecast_accuracies.iloc[month_of_year, 0]

        candidate_corr = corr_matrix[fcst_month].copy()
        # candidate_corr[fcst_month] = np.nan
        candidate_rms = rms_matrix[fcst_month].copy()

        best_obs_month = int(
            np.nanargmin(np.abs(candidate_corr - target_corr) + np.abs(candidate_rms))
        )

        # replace forecast with observation
        num_fcst_hrs = len(monthly_idx[fcst_month]) * 24
        fcst_hrs = range(
            min(monthly_idx[fcst_month]) * 24, (max(monthly_idx[fcst_month]) + 1) * 24
        )
        obs_hrs = range(
            min(monthly_idx[best_obs_month]) * 24,
            (max(monthly_idx[best_obs_month]) + 1) * 24,
        )
        # num_days = len(monthly_idx[fcst_month])

        true_solar_profile.iloc[fcst_hrs] = pv_produced.iloc[
            obs_hrs[:num_fcst_hrs]
        ].to_numpy()
        heatmap_matrix[month_of_year][best_obs_month % 12] += 1

    # save the data
    true_solar_profile.to_csv(
        os.path.join(generation_directory, f"true_solar_output.csv")
    )
    logger.info("True solar profile successfully generated.")
    # return the modified solar curve
    return true_solar_profile
