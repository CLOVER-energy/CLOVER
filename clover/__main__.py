#!/usr/bin/python3
########################################################################################
# __main__.py - Main module for CLOVER.                                                #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 13/07/2021                                                             #
# License: Open source                                                                 #
########################################################################################
"""
__main__.py - The main module for CLOVER.

CLOVER (Continuous Lifetime Optimisation of Variable Electricity Resources) can evaluate
and optimise minigrid systems, determining whether a demand is met whilst minimising
environmental and economic impacts. The main flow of CLOVER can be executed by running
the clover module from the command-line interface.

"""

import logging
import os
import sys

from argparse import ArgumentError
from typing import Any, Dict, List

import pandas as pd

from . import argparser
from .generation import grid, solar

from .__utils__ import (
    get_logger,
    InvalidLocationError,
    LOCATIONS_FOLDER_NAME,
    read_yaml,
)

# Auto-generated-files directory:
#   The name of the directory in which to save auto-generated files, relative to the
# root of the location.
AUTO_GENERATED_FILES_DIRECTORY = "auto_generated"
# Device inputs file:
#   The relative path to the device-inputs file.
DEVICE_INPUTS_FILE = os.path.join("load", "devices.yaml")
# Diesel inputs file:
#   The relative path to the diesel-inputs file.
DIESEL_INPUTS_FILE = os.path.join("generation", "diesel", "diesel_inputs.yaml")
# Grid inputs file:
#   The relative path to the grid-inputs file.
GRID_INPUTS_FILE = os.path.join("generation", "grid", "grid_inputs.csv")
# Inputs directory:
#   The directory containing user inputs.
INPUTS_DIRECTORY = "inputs"
# Location inputs file:
#   The relative path to the location inputs file.
LOCATION_INPUTS_FILE = os.path.join("location_data", "location_inputs.yaml")
# Logger name:
#   The name to use for the main logger for CLOVER
LOGGER_NAME = "clover"
# Solar inputs file:
#   The relative path to the solar inputs file.
SOLAR_INPUTS_FILE = os.path.join("generation", "solar", "solar_generation_inputs.yaml")


def _check_location(location: str, logger: logging.Logger) -> bool:
    """
    Returns whether the specified location meets the requirements for CLOVER.

    Inputs:
        - location
            The name of the location to check.

    Outputs:
        - Whether the location meets the requirements as a boolean variable.

    Raises:
        - FileNotFoundError:
            Raised if the location cannot be found.

    """

    if not os.path.isdir(os.path.join(LOCATIONS_FOLDER_NAME, location)):
        logger.error(
            "The specified location, '%s', does not exist. Try running the "
            "'new_location' script to ensure all necessary files and folders are "
            "present.",
            location,
        )
        raise FileNotFoundError(
            "The location, {}, could not be found.".format(location)
        )

    # Read in the information about the files that should be present.
    # new_location_data = read_yaml(NEW_LOCATION_DATA_FILE)
    # new_location_data[0][DIRECTORY].format(
    #     location=location, locations_folder_name=LOCATIONS_FOLDER_NAME
    # )
    # logger.info("New-location information succesfully parsed.")

    return True


def _parse_location_information(
    filepath: str, location: str, logger: logging.Logger
) -> Dict[Any, Any]:
    """
    Parse information about the required format of a location folder for verification.

    Inputs:
        - filepath:
            The path to the new-location data file.
        - location:
            The name of the location being considered.
        - logger:
            The logger to use for the run.

    Outputs:
        - The parsed folder and file structure.

    """


def main(args: List[Any]) -> None:
    """
    The main module for CLOVER executing all functionality as appropriate.

    Inputs:
        - args
            The command-line arguments, passed in as a list.

    """

    logger = get_logger(LOGGER_NAME)
    logger.info("CLOVER run initiated. Options specified: %s", " ".join(args))

    parsed_args = argparser.parse_args(args)
    logger.info("Command-line arguments successfully parsed.")

    if not argparser.validate_args(logger, parsed_args):
        logger.error(
            "Invalid command-line arguments. Check that all required arguments have "
            "been specified. See /logs for details."
        )
        raise ValueError(
            "The command-line arguments were invalid. See /logs for details."
        )
    logger.info("Command-line arguments successfully validated.")

    # ******* #
    # *  1  * #
    # ******* #

    # If the location does not exist or does not meet the required specification, then
    # exit now.
    logger.info("Checking location %s.", parsed_args.location)
    if not _check_location(parsed_args.location, logger):
        logger.error(
            "The location, '%s', is invalid. Try running the `new_location` script to"
            "identify missing files. See /logs for details.",
            parsed_args.location,
        )
        raise InvalidLocationError(parsed_args.location)
    logger.info("Location, '%s', has been verified and is valid.", parsed_args.location)

    # Define common variables.
    auto_generated_files_directory = os.path.join(
        LOCATIONS_FOLDER_NAME,
        parsed_args.location,
        AUTO_GENERATED_FILES_DIRECTORY,
    )

    # ******* #
    # *  2  * #
    # ******* #

    # Parse the various input files.
    logger.info("Parsing input files.")
    inputs_directory_relative_path = os.path.join(
        LOCATIONS_FOLDER_NAME,
        parsed_args.location,
        INPUTS_DIRECTORY,
    )

    device_inputs = read_yaml(
        os.path.join(
            inputs_directory_relative_path,
            DEVICE_INPUTS_FILE,
        ),
        logger,
    )
    logger.info("Device inputs successfully parsed.")

    diesel_inputs = read_yaml(
        os.path.join(
            inputs_directory_relative_path,
            DIESEL_INPUTS_FILE,
        ),
        logger,
    )
    logger.info("Diesel inputs successfully parsed.")

    grid_inputs = pd.read_csv(
        os.path.join(
            inputs_directory_relative_path,
            GRID_INPUTS_FILE,
        ),
        index_col=0,
    )
    logger.info("Grid inputs successfully parsed.")

    location_inputs = read_yaml(
        os.path.join(
            inputs_directory_relative_path,
            LOCATION_INPUTS_FILE,
        ),
        logger,
    )
    logger.info("Location inputs successfully parsed.")

    solar_generation_inputs = read_yaml(
        os.path.join(
            inputs_directory_relative_path,
            SOLAR_INPUTS_FILE,
        ),
        logger,
    )
    logger.info("Solar generation inputs successfully parsed.")
    logger.info("All input files successfully parsed.")

    # Generate and save the solar data for each year as a background task.
    logger.info("Beginning solar-data fetching.")
    solar_data_thread = solar.SolarDataThread(
        os.path.join(auto_generated_files_directory, "solar"),
        location_inputs,
        logger,
        solar_generation_inputs,
    )
    solar_data_thread.start()
    logger.info("Solar-data thread successfully instantiated.")

    # Generate the grid-availability profiles.
    logger.info("Generating grid-availability profiles.")
    grid_filename, grid_times = grid.get_lifetime_grid_status(
        os.path.join(auto_generated_files_directory, "grid"),
        grid_inputs,
        location_inputs["max_years"],
    )
    logger.info("Grid-availability profiles successfully generated.")
    grid_times.to_csv(grid_filename)
    logger.info("Grid availability profiles successfully saved to %s.", grid_filename)

    # * Generate and save the grid-availibility profiles.
    # * Generate and save any additional profiles, such as diesel-generator profiles.

    # ******* #
    # *  3  * #
    # ******* #

    # * Run a simulation or optimisation as appropriate.

    # ******* #
    # *  4  * #
    # ******* #

    # * Run any and all analysis as appropriate.


if __name__ == "__main__":
    main(sys.argv[1:])
