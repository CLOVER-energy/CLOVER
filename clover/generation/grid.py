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

from typing import Tuple

import pandas as pd

__all__ = ("get_lifetime_grid_status",)


def get_lifetime_grid_status(
    generation_directory: str, grid_inputs: pd.DataFrame, max_years: int
) -> Tuple[str, pd.DataFrame]:
    """
    Calculates, and saves, the grid-availability profiles of all input types.

    Inputs:
        - generation_directory:
            The directory in which auto-generated files should be saved.
        - grid_inputs:
            Grid inputs information, read from the grid-inputs file.
        - max_years:
            The maximum number of years for which the simulation should run.

    Outputs:
        - grid_filename:
            The filename to use when saving the grid information.
        - grid_times:
            A :class:`pandas.DataFrame` containing the grid times.

    """

    grid_types = list(grid_inputs)

    for i in range(grid_inputs.shape[1]):
        grid_hours = pd.DataFrame(grid_inputs[grid_types[i]])
        grid_status = []
        for _ in range(365 * int(max_years)):
            for hour in range(grid_hours.size):
                if random.random() < grid_hours.iloc[hour].values:
                    grid_status.append(1)
                else:
                    grid_status.append(0)
        grid_times = pd.DataFrame(grid_status)
        grid_name = grid_types[i]

    grid_filename = os.path.join(generation_directory, f"{grid_name}_grid_status.csv")

    return grid_filename, grid_times


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
