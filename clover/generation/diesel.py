#!/usr/bin/python3
########################################################################################
# diesel.py - Diesel generation module  .                                              #
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
diesel.py - The diesel-generator module for CLOVER.

This module models the diesel-generator functionality within CLOVER.

"""

import dataclasses
import os

from typing import Tuple

import numpy as np
import pandas as pd

from .. import fileparser

from ..__utils__ import LOCATIONS_FOLDER_NAME, get_logger, read_yaml
from ..simulation.diesel import DieselBackupGenerator

__all__ = (
    "get_diesel_energy_and_times",
    "get_diesel_fuel_usage",
)


def _find_deficit_threshold(
    unmet_energy: pd.DataFrame, blackouts: pd.DataFrame, backup_threshold: float
) -> float:
    """
    Identifies the threshold energy level at which the diesel backup generator turns on.

    Inputs:
        - backup_threshold:
            Desired level of reliability after diesel backup
        - blackouts:
            Current blackout profile before diesel backup
        - unmet_energy:
            Load profile of currently unment energy

    Outputs:
        - energy_threshold:
            The energy threshold (kWh) at which the diesel backup switches on.

    """

    # Find the blackout percentage
    blackout_percentage = np.mean(blackouts)[0]

    # Find the difference in reliability
    reliability_difference = blackout_percentage - backup_threshold
    percentile_threshold = 100.0 * (1.0 - reliability_difference)

    if reliability_difference > 0.0:
        energy_threshold = np.percentile(unmet_energy, percentile_threshold)
    else:
        energy_threshold = np.max(unmet_energy)[0] + 1.0

    return energy_threshold


def get_diesel_energy_and_times(
    unmet_energy: pd.DataFrame, blackouts: pd.DataFrame, backup_threshold: float
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Finds times when the load is greater than the energy threshold.

    Calculates the times at which the diesel backup generator is used, and the energy
    output during those times

    Inputs:
        - backup_threshold:
            Desired level of reliability after diesel backup
        - blackouts:
            Current blackout profile before diesel backup
        - unmet_energy:
            Load profile of currently unment energy

    Outputs:
        - diesel_energy:
            Profile of energy supplued by diesel backup
        - diesel_times:
            Profile of times when generator is on (1) or off (0)

    """

    energy_threshold = _find_deficit_threshold(
        unmet_energy, blackouts, backup_threshold
    )

    diesel_energy = (unmet_energy >= energy_threshold) * unmet_energy
    diesel_times = (unmet_energy >= energy_threshold) * 1
    diesel_times = diesel_times.astype(float)

    return diesel_energy, diesel_times


def get_diesel_fuel_usage(
    capacity: int,
    diesel_backup_generator: DieselBackupGenerator,
    diesel_energy: pd.DataFrame,
    diesel_times: pd.DataFrame,
) -> pd.DataFrame:
    """
    Find diesel fuel consumption.

    Calculates the fuel usage of the diesel backup generator

    Inputs:
        - capacity:
            Capacity (kW) of the diesel generator.
        - diesel_backup_generator:

        - diesel_energy:
            Profile of energy supplued by diesel backup.
        - diesel_times:
            Profile of times when generator is on (1) or off (0).

    Outputs:
        - fuel_usage:
            Hourly profile of diesel fuel usage (litres).

    """

    load_factor = diesel_energy / capacity
    above_minimum = load_factor * (load_factor > diesel_backup_generator.minimum_load)
    below_minimum = diesel_backup_generator.minimum_load * (
        load_factor <= diesel_backup_generator.minimum_load
    )
    load_factor = (
        pd.DataFrame(above_minimum.values + below_minimum.values) * diesel_times
    )

    fuel_usage = load_factor * capacity * diesel_backup_generator.diesel_consumption
    fuel_usage = fuel_usage.astype(float)

    return fuel_usage
