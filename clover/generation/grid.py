#!/usr/bin/python3
########################################################################################
# solar.py - Solar generation module  .                                                #
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
import random

from logging import Logger
from typing import Dict, List

import pandas as pd

from tqdm import tqdm  # type: ignore

__all__ = (
    "get_lifetime_grid_status",
    # "GridStatusThread",
)


def get_lifetime_grid_status(
    generation_directory: str, grid_inputs: pd.DataFrame, logger: Logger, max_years: int
) -> Dict[str, pd.DataFrame]:
    """
    Calculates, and saves, the grid-availability profiles of all input types.

    Inputs:
        - generation_directory:
            The directory in which auto-generated files should be saved.
        - grid_inputs:
            Grid inputs information, read from the grid-inputs file.
        - logger:
            The logger to use for the run.
        - max_years:
            The maximum number of years for which the simulation should run.

    Outputs:
        - grid_profiles:
            A dictionary mapping the grid name to the grid profile.

    """

    # Extract the grid-profile names from the dataframe.
    grid_types: List[str] = list(grid_inputs)

    # Set up a holder dictionary to contain the grid information.
    grid_profiles: Dict[str, pd.DataFrame] = dict()

    # Loop through all the various grid profiles that have been defined.
    for grid_index in tqdm(
        range(grid_inputs.shape[1]),
        desc="grid profiles",
        leave=True,
        unit="grid",
    ):
        grid_name = grid_types[grid_index]
        grid_filename = os.path.join(
            generation_directory, f"{grid_name}_grid_status.csv"
        )

        # If the profile already exists, simply read from the file.
        if os.path.isfile(grid_filename):
            with open(grid_filename, "r") as f:
                grid_times = pd.read_csv(f)
            grid_profiles[grid_name] = grid_times
            logger.info(
                "Grid availability profile for %s successfully read from file %s",
                grid_name,
                grid_filename,
            )
            continue

        grid_hours = pd.DataFrame(grid_inputs[grid_types[grid_index]])
        grid_status = []
        for _ in range(365 * int(max_years)):
            for hour in range(grid_hours.size):
                if random.random() < grid_hours.iloc[hour].values:
                    grid_status.append(1)
                else:
                    grid_status.append(0)
        grid_times = pd.DataFrame(grid_status)
        grid_profiles[grid_name] = grid_times
        logger.info(
            "Grid availability profile for %s successfully generated.", grid_name
        )

        with open(grid_filename, "w") as f:
            grid_times.to_csv(f)  # type: ignore
        logger.info(
            "Grid-availability profile for %s successfullly saved to %s.",
            grid_name,
            grid_filename,
        )

    return grid_profiles


#     #%%
#     def change_grid_coverage(self, grid_type="bahraich", hours=12):
#         grid_profile = self.grid_inputs[grid_type]
#         baseline_hours = np.sum(grid_profile)
#         new_profile = pd.DataFrame([0] * 24)
#         for hour in range(24):
#             m = interp1d([0, baseline_hours, 24], [0, grid_profile[hour], 1])
#             new_profile.iloc[hour] = m(hours).round(3)
#         new_profile.columns = [grid_type + "_" + str(hours)]
#         return new_profile

#     def save_grid_coverage(self, grid_type="bahraich", hours=12):
#         new_profile = self.change_grid_coverage(grid_type, hours)
#         new_profile_name = grid_type + "_" + str(hours)
#         output = self.grid_inputs
#         if new_profile_name in output.columns:
#             output[new_profile_name] = new_profile
#         else:
#             output = pd.concat([output, new_profile], axis=1)
#         output.to_csv(self.generation_filepath + "Grid inputs.csv")


# class GridStatusThread(threading.Thread):
#     """
#     Calculates the grid status profiles in a stand-alone thread.

#     .. attribute:: grid_autogenerated_directory
#         The directory in which to save the auto-generated grid-availability profiles.

#     .. attribute:: grid_inputs
#         The grid input information, extracted from the grid inputs file.

#     .. attribute:: logger
#         The logger to use for the run.

#     .. attribute:: years
#         The number of years for which the simulation is being run.

#     """

#     def __init__(
#         self,
#         grid_autogenerated_directory: str,
#         grid_inputs: pd.DataFrame,
#         logger: Logger,
#         years: int,
#     ) -> None:
#         """
#         Instantiate a :class:`grid.GridStatusThread`.

#         Inputs:
#             - grid_autogenerated_directory:
#                 The directory in which to save the auto-generated grid-availability
#                 profiles.

#             - grid_inputs:
#                 The grid input information, extracted from the grid inputs file.

#             - logger:
#                 The logger to use for the run.

#             - years:
#                 The number of years for which the simulation is being run.

#         """

#         self.grid_autogenerated_directory = grid_autogenerated_directory
#         self.grid_inputs = grid_inputs
#         self.logger = logger
#         self.years = years

#         super().__init__()

#     def run(self) -> None:
#         """
#         Execute the grid-status thread.

#         """

#         self.logger.info("Generating grid-availability profiles.")
#         grid_profiles = get_lifetime_grid_status(
#             self.grid_autogenerated_directory, self.grid_inputs, self.logger, self.years
#         )
#         self.logger.info("Grid-availability profiles successfully generated.")
