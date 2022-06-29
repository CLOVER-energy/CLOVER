#!/usr/bin/python3
########################################################################################
# grid.py - Grid-profile generation module.                                            #
#                                                                                      #
# Author: Phil Sandwell                                                                #
# Copyright: Phil Sandwell, 2018                                                       #
# License: Open source                                                                 #
# Most recent update: 14/07/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
grid.py - The grid-generation module for CLOVER.

This module generates grid-availability profiles for CLOVER.

"""

import os

from logging import Logger
from typing import Dict, Optional

import pandas as pd

from ..__utils__ import BColours, Scenario
from .__utils__ import get_intermittent_supply_status

__all__ = (
    "get_lifetime_grid_status",
    "load_grid_profile",
)


def get_lifetime_grid_status(
    disable_tqdm: bool,
    generation_directory: str,
    grid_times: pd.DataFrame,
    logger: Logger,
    max_years: int,
) -> Dict[str, pd.DataFrame]:
    """
    Calculates, and saves, the grid-availability profiles of all input types.

    Inputs:
        - disable_tqdm:
            Whether to disable tqdm progress bars (True) or display them (False).
        - generation_directory:
            The directory in which auto-generated files should be saved.
        - grid_times:
            Grid inputs information, read from the grid-inputs file.
        - logger:
            The logger to use for the run.
        - max_years:
            The maximum number of years for which the simulation should run.

    Outputs:
        - grid_profiles:
            A dictionary mapping the grid name to the grid profiles (DataFrame).

    """

    return get_intermittent_supply_status(
        disable_tqdm, generation_directory, "grid", logger, max_years, grid_times
    )


def load_grid_profile(
    auto_generated_files_directory: str, logger: Logger, scenario: Scenario
) -> Optional[pd.DataFrame]:
    """
    Loads the grid profile required for the run.

    Inputs:
        - auto_generated_files_directory:
            The file into which auto-generated files are saved.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenario:
            The scenario to use for the run.

    """

    grid_profiles: Optional[Dict[str, pd.DataFrame]] = {}

    if scenario.grid:
        for grid_type in scenario.grid_types:
            try:
                with open(
                    os.path.join(
                        auto_generated_files_directory,
                        "grid",
                        f"{grid_type}_grid_status.csv",
                    ),
                    "r",
                ) as f:
                    grid_profiles[grid_type] = pd.read_csv(
                        f,
                        index_col=0,
                    )
            except FileNotFoundError as e:
                logger.error(
                    "%sGrid profile file for profile '%s' could not be found: %s%s",
                    BColours.fail,
                    grid_type,
                    str(e),
                    BColours.endc,
                )
                raise

    return grid_profiles
