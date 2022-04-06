#!/usr/bin/python3
########################################################################################
# update_api_token.py - Script for updating API tokens in locations.                   #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 21/09/2021                                                             #
#                                                                                      #
# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
update_api_token.py - Script for updating API tokens within locations.

This script, when run, scans through locations in search of API tokens to update.

"""

import argparse
import os
import sys

from typing import Any, Dict, List

import yaml  # pylint: disable=import-error

from ..__utils__ import get_logger, read_yaml
from ..fileparser import GENERATION_INPUTS_FILE, INPUTS_DIRECTORY, LOCATIONS_FOLDER_NAME
from ..generation.__utils__ import TOKEN

__all__ = ("main",)

# Logger name:
#   The name to use for the logger.
LOGGER_NAME: str = "update_api_token"


def _parse_args(args: List[Any]) -> argparse.Namespace:
    """
    Parse the CLI arguments to determine the flow of the script.

    """

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--token",
        type=str,
        help="The renewables.ninja API token to use.",
    )
    parser.add_argument(
        "--location", type=str, help="The name of the location to update."
    )

    return parser.parse_args(args)


def main(args: List[Any]) -> None:
    """
    The main method of the update api token script.

    Inputs:
        - args:
            The un-parsed command-line arguments.

    """

    logger = get_logger(LOGGER_NAME)
    logger.info("Update API token script called with arguments: %s", args)

    # Parse the command-line arguments.
    parsed_args = _parse_args(args)
    logger.info("Commane-line arguments successfully parsed.")

    # Error if not all arguments passed in.
    if parsed_args.location is None:
        raise Exception("A location to update must be specified.")
    if parsed_args.token is None:
        raise Exception("The renewables.ninja API token must be specifeid.")

    # Check whether the generation file exists.
    generation_file_path = os.path.join(
        LOCATIONS_FOLDER_NAME,
        parsed_args.location,
        INPUTS_DIRECTORY,
        GENERATION_INPUTS_FILE,
    )

    if not os.path.isfile(generation_file_path):
        raise FileNotFoundError(
            "The generation inputs file could not be found within the location "
            f"{parsed_args.location}.",
        )

    # Attempt to update the token.
    filedata: Dict[str, Any]
    try:
        filedata = read_yaml(generation_file_path, logger)  # type: ignore
    except Exception:
        logger.error("Error reading generation inputs file '%s'.", generation_file_path)
        raise

    filedata[TOKEN] = parsed_args.token

    logger.info("Attempting to save updated token to the generation inputs file.")
    with open(generation_file_path, "w") as f:
        yaml.dump(filedata, f)
    logger.info("Updated API token successfully saved.")


if __name__ == "__main__":
    main(sys.argv[1:])
