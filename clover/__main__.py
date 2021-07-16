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

from functools import partial
from multiprocessing import Pool
from typing import Any, Dict, List

import pandas as pd

from . import argparser
from .generation import grid, solar
from .load import load

from atpbar import atpbar

from .__utils__ import (
    get_logger,
    InvalidLocationError,
    LOCATIONS_FOLDER_NAME,
    LOGGER_DIRECTORY,
    read_yaml,
)

# Auto-generated-files directory:
#   The name of the directory in which to save auto-generated files, relative to the
# root of the location.
AUTO_GENERATED_FILES_DIRECTORY = "auto_generated"
# Clover header string:
#   The ascii text to display when starting CLOVER.
CLOVER_HEADER_STRING = """

        (((((*    /(((
        ((((((( ((((((((
   (((((((((((( ((((((((((((
   ((((((((((((*(((((((((((((       _____ _      ______      ________ _____
     *((((((((( ((((((((((((       / ____| |    / __ \\ \\    / /  ____|  __ \\
   (((((((. /((((((((((/          | |    | |   | |  | \\ \\  / /| |__  | |__) |
 ((((((((((((((((((((((((((,      | |    | |   | |  | |\\ \\/ / |  __| |  _  /
 (((((((((((*  (((((((((((((      | |____| |___| |__| | \\  /  | |____| | \\ \\
   ,(((((((. (  (((((((((((/       \\_____|______\\____/   \\/   |______|_|  \\_\\
   .((((((   (   ((((((((
             /     (((((
             ,
              ,
               (
                 (
                   (



       Continuous Lifetime Optimisation of Variable Electricity Resources
                         Copyright Phil Sandwell, 2018

                 For more information, contact Phil Sandwell at
                           philip.sandwell@gmail.com


"""
# Device inputs file:
#   The relative path to the device-inputs file.
DEVICE_INPUTS_FILE = os.path.join("load", "devices.yaml")
# Device utilisation template filename:
#   The template filename of device-utilisation profiles used for parsing the files.
DEVICE_UTILISATION_TEMPLATE_FILENAME = "{device}_times.csv"
# Device utilisations input directory:
#   The relative path to the directory contianing the device-utilisaion information.
DEVICE_UTILISATIONS_INPUT_DIRECTORY = os.path.join("load", "device_utilisation")
# Diesel inputs file:
#   The relative path to the diesel-inputs file.
DIESEL_INPUTS_FILE = os.path.join("generation", "diesel", "diesel_inputs.yaml")
# Energy-system inputs file:
#   The relative path to the energy-system-inputs file.
ENERGY_SYSTEM_INPUTS_FILE = os.path.join("generation", "diesel", "diesel_inputs.yaml")
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
# Number of Workers:
#   The number of CPUs to use, which dictates the number of workers to use for parllel
#   jobs.
NUM_WORKERS = 8
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
            "been specified. See %s for details.",
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
        )
        raise ValueError(
            "The command-line arguments were invalid. See {} for details.".format(
                "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME))
            )
        )
    logger.info("Command-line arguments successfully validated.")

    print(CLOVER_HEADER_STRING)

    # If the location does not exist or does not meet the required specification, then
    # exit now.
    print("Verifying location information ................................    ", end="")
    logger.info("Checking location %s.", parsed_args.location)
    if not _check_location(parsed_args.location, logger):
        logger.error(
            "The location, '%s', is invalid. Try running the `new_location` script to"
            "identify missing files. See %s for details.",
            parsed_args.location,
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
        )
        raise InvalidLocationError(parsed_args.location)
    logger.info("Location, '%s', has been verified and is valid.", parsed_args.location)

    print(
        "[   DONE   ]\nParsing input files ........................................... "
        "   ",
        end="",
    )

    # Define common variables.
    auto_generated_files_directory = os.path.join(
        LOCATIONS_FOLDER_NAME,
        parsed_args.location,
        AUTO_GENERATED_FILES_DIRECTORY,
    )

    # Parse the various input files.
    logger.info("Parsing input files.")
    inputs_directory_relative_path = os.path.join(
        LOCATIONS_FOLDER_NAME,
        parsed_args.location,
        INPUTS_DIRECTORY,
    )

    try:
        device_inputs: List[Dict[str, Any]] = read_yaml(
            os.path.join(
                inputs_directory_relative_path,
                DEVICE_INPUTS_FILE,
            ),
            logger,
        )
        logger.info("Device inputs successfully parsed.")

        try:
            device_utilisations = {
                device["device"]: pd.read_csv(
                    os.path.join(
                        inputs_directory_relative_path,
                        DEVICE_UTILISATIONS_INPUT_DIRECTORY,
                        DEVICE_UTILISATION_TEMPLATE_FILENAME.format(
                            device=device["device"]
                        ),
                    ),
                    header=None,
                    index_col=None,
                )
                for device in device_inputs
            }
        except FileNotFoundError:
            logger.error(
                "Error parsing device-utilisation profiles, check that all device "
                "names are consistent and use the same case. File not found: %s."
            )
            raise

        diesel_inputs_filepath = os.path.join(
            inputs_directory_relative_path,
            DIESEL_INPUTS_FILE,
        )
        diesel_inputs = read_yaml(
            diesel_inputs_filepath,
            logger,
        )
        logger.info("Diesel inputs successfully parsed.")

        with open(
            os.path.join(
                inputs_directory_relative_path,
                GRID_INPUTS_FILE,
            ),
            "r",
        ) as grid_inputs_file:
            grid_inputs = pd.read_csv(
                grid_inputs_file,
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
    except FileNotFoundError as e:
        print("[  FAILED  ]\n")
        logger.error(
            "Not all input files present.  See %s for details: %s",
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
            str(e),
        )
        raise
    except Exception as e:
        print("[  FAILED  ]\n")
        logger.error(
            "An unexpected error occured parsing input files. See %s for details: %s",
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
            str(e),
        )
        raise

    logger.info("All input files successfully parsed.")
    print(
        "[   DONE   ]\nGenerating necessary profiles ................................. "
        "   ",
        end="\n",
    )

    # Generate and save the solar data for each year as a background task.
    logger.info("Beginning solar-data fetching.")
    solar_data_thread = solar.SolarDataThread(
        os.path.join(auto_generated_files_directory, "solar"),
        location_inputs,
        solar_generation_inputs,
    )
    solar_data_thread.start()
    logger.info(
        "Solar-data thread successfully instantiated. See %s for details.",
        "{}.log".format(os.path.join(LOGGER_DIRECTORY, solar.SOLAR_LOGGER_NAME)),
    )
    logger.info("Solar-data thread not run due to time efficiencies.")

    # Generate and save the device-ownership profiles.
    logger.info("Processing device informaiton.")
    # load_logger = get_logger(load.LOAD_LOGGER_NAME)

    try:
        total_load, _ = load.process_load_profiles(
            auto_generated_files_directory,
            device_inputs,
            device_utilisations,
            location_inputs,
            logger,
        )
    except Exception as e:
        print(
            "Generating necessary profiles ................................. "
            "[  FAILED  ]\n"
        )
        logger.error(
            "An unexpected error occurred generating the load profiles. See %s for "
            "details: %s",
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
            str(e),
        )
        raise

    # Generate the grid-availability profiles.
    logger.info("Generating grid-availability profiles.")
    try:
        grid_profiles = grid.get_lifetime_grid_status(
            os.path.join(auto_generated_files_directory, "grid"),
            grid_inputs,
            logger,
            location_inputs["max_years"],
        )
    except Exception as e:
        print(
            "Generating necessary profiles ................................. "
            "[  FAILED  ]\n"
        )
        logger.error(
            "An unexpected error occurred generating the grid profiles. See %s for "
            "details: %s",
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
            str(e),
        )
        raise

    logger.info("Grid-availability profiles successfully generated.")

    # Wait for all threads to finish before proceeding.
    logger.info("Waiting for all setup threads to finish before proceeding.")
    solar_data_thread.join()
    logger.info("All setup threads finished, continuing to CLOVER simulation.")

    print(
        "Generating necessary profiles ................................. "
        "   [   DONE   ]\n"
        "Beginning CLOVER run           ................................    ",
        end="",
    )

    # ******* #
    # *  3  * #
    # ******* #

    # * Run a simulation or optimisation as appropriate.

    # ******* #
    # *  4  * #
    # ******* #

    # * Run any and all analysis as appropriate.

    print(
        "Finished. See {} for output files.".format(
            os.path.join(LOCATIONS_FOLDER_NAME, "outputs")
        )
    )


if __name__ == "__main__":
    main(sys.argv[1:])
