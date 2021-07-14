#!/usr/bin/python3
########################################################################################
# __main__.py - Main module for CLOVER.
#
# Author: Ben Winchester
# Copyright: Ben Winchester, 2021
# Date created: 13/07/2021
# License: Open source
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

from typing import Any, Dict, List

from .__utils__ import (
    get_logger,
    InvalidLocationError,
    LOCATIONS_FOLDER_NAME,
    read_yaml,
)
from .argparser import parse_args
from .scripts.new_location import DIRECTORY, NEW_LOCATION_DATA_FILE

# Logger name:
#   The name to use for the main logger for CLOVER
LOGGER_NAME = "clover"


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

    parsed_args = parse_args(args)
    logger.info("Command-line arguments successfully parsed.")

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

    # ******* #
    # *  2  * #
    # ******* #

    # * Generate the profiles where appropriate based on the arguments passed in.
    # Generate and save the PV profiles.
    # @ BenWinchester FIXME
    # The solar data should not be closed and then re-opened as CLOVER runs.

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
