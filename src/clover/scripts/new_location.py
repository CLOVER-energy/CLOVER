#!/usr/bin/python3
########################################################################################
# new_location.py - Script for generating a new location folder.                       #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 01/07/2021                                                             #
#                                                                                      #
# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
new_location.py - Script for generating a new location folder.

This script, when run, generates a new location for the user, copying files from an
existing location if asked for.

"""

import argparse
import logging
import os
import pkgutil
import shutil
import sys

from typing import Any, List, Optional, Pattern

import re
import yaml  # pylint: disable=import-error

from ..__utils__ import (
    InternalError,
    get_logger,
    LOCATIONS_FOLDER_NAME,
    PACKAGE_NAME,
    RAW_CLOVER_PATH,
    read_yaml,
)
from ..fileparser import INPUTS_DIRECTORY

__all__ = (
    "CONTENTS",
    "create_new_location",
    "DIRECTORY",
    "FILE",
    "NEW_LOCATION_DATA_FILE",
)


# Contents:
#   The keyword used to denote the contents of a file or folder.
CONTENTS: str = "contents"

# Directory:
#   The keyword used to denote a directory.
DIRECTORY: str = "directory"

# File:
#   The keyword used to denote a file.
FILE: str = "file"

# Logger name:
#   The name of the logger to use.
LOGGER_NAME: str = "new_location"

# New-location data file:
#   The path to the new-location data file.
NEW_LOCATION_DATA_FILE: str = os.path.join("src", "new_location.yaml")

# Regex used to find lines that should be repeated, used to save YAML file space.
REPEATED_LINE_REGEX: Pattern[str] = re.compile(
    r"(?P<multiplier>\d*):(?P<line_to_repeat>.*)\n"
)


def _create_file(
    contents: str, directory: str, filename: str, logger: logging.Logger
) -> None:
    """
    Creates a file within the directory specified with the contents passed in.

    Inputs:
        - contents:
            The contents of the file to be created.
        - directory:
            The name of the directory in which to create the file.
        - filename:
            The name of the file to be created.
        - logger:
            The logger to use for the run.

    """

    if not os.path.isdir(directory):
        raise FileNotFoundError(f"The directory '{directory}' could not be found.")

    if os.path.isfile(os.path.join(directory, filename)):
        logger.info(
            "File already exists, skipping creation: %s",
            os.path.relpath(os.path.join(directory, filename), os.getcwd()),
        )
        return

    # Repeat lines where appropriate.
    if filename.endswith(".csv"):
        for match in REPEATED_LINE_REGEX.finditer(contents):
            contents = re.sub(
                rf"{match.group('multiplier')}:{match.group('line_to_repeat')}",
                "\n".join(
                    [str(match.group("line_to_repeat"))]
                    * int(match.group("multiplier"))
                ),
                contents,
            )

    with open(os.path.join(directory, filename), "w") as new_file:
        new_file.write(contents)

    logger.info("File successfully created: %s", os.path.join(directory, filename))


def _create_folder_and_contents(
    contents: List[Any],
    directory_name: str,
    logger: logging.Logger,
    parent_directory: str,
) -> None:
    """
    Creates a folder and all files and folders contained within it.

    Inputs:
        - contents:
            The contents of the file to be created.
        - directory_name:
            The name of the directory being created.
        - logger:
            The logger to use for the run.
        - parent_directory:
            The directory in which this directory should be created.

    """

    # Start by creating this directory.
    os.makedirs(os.path.join(parent_directory, directory_name), exist_ok=True)

    for entry in contents:
        if FILE in entry:
            _create_file(
                entry[CONTENTS],
                os.path.join(parent_directory, directory_name),
                entry[FILE],
                logger,
            )
            continue
        if DIRECTORY in entry:
            _create_folder_and_contents(
                entry[CONTENTS] if CONTENTS in entry else [],
                entry[DIRECTORY],
                logger,
                os.path.join(parent_directory, directory_name),
            )


def _parse_args(args: List[Any]) -> argparse.Namespace:
    """
    Parse the CLI arguments to determine the flow of the script.

    """

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--from-existing",
        type=str,
        help="The name of an existing location off which to model the new location.",
    )
    parser.add_argument(
        "location", type=str, help="The name of the new location to be created."
    )
    parser.add_argument(
        "--update",
        action="store_true",
        default=False,
        help="To update an existing location with new or missing files.",
    )

    return parser.parse_args(args)


def create_new_location(
    from_existing: Optional[str],
    location: str,
    logger: logging.Logger,
    update: bool,
) -> None:
    """
    Creates a new location based on the specified inputs.

    Inputs:
        - from_existing:
            The name of an existing location from which to copy across files.
        - location:
            The name of the new location to create.
        - logger:
            The logger to use for the run.
        - parsed_args:
            The parsed command-line arguments.
        - update:
            Whether the new location should be updated.

    """

    # Read the location data.
    logger.info("Attempting to read location data from installed package info.")
    try:
        package_data = pkgutil.get_data(PACKAGE_NAME, NEW_LOCATION_DATA_FILE)
        if package_data is None:
            raise AttributeError("Package data read but no data within file.")
    except AttributeError:
        logger.info("Failed to read data as if package was installed.")
        logger.info("Attempting to read location data from raw source file.")
        try:
            new_location_data = read_yaml(
                os.path.join(RAW_CLOVER_PATH, NEW_LOCATION_DATA_FILE), logger
            )
        except Exception:
            logger.error("Failed to read location data from raw source.")
            logger.critical("Failed to determine location of the location data file.")
            raise
        logger.info("Successfully read location data file from local source.")
    else:
        if package_data is None:
            raise Exception("Package data read but no data within file.")
        new_location_data = yaml.safe_load(package_data)
        logger.info("Successfully read location data file from installed package file.")
    logger.info("Data file successfully read.")

    if not isinstance(new_location_data, list):
        raise InternalError(
            "New location data source file is no longer of type `list`."
        )

    # Process the new-location data into a usable format.
    new_location_directory = str(new_location_data[0][DIRECTORY]).format(
        location=location, locations_folder_name=LOCATIONS_FOLDER_NAME
    )

    # If the new location already exists and the script is not run to update, then exit.
    if os.path.isdir(new_location_directory) and not update:
        logger.error(
            "The new location directory already exists and the script was not run with "
            "--update."
        )
        sys.exit(1)

    # Generate files as per the hard-coded directory structure.
    if update:
        logger.info(
            "Updating location folder with new and updated files %s.",
            location,
        )
    else:
        logger.info("Creating new-location folder for location %s.", location)
    _create_folder_and_contents(
        new_location_data[0][CONTENTS], new_location_directory, logger, os.getcwd()
    )
    logger.info("New location folder for %s successfully created/updated.", location)

    # Copy across files from the existing structure if they exist, otherwise, generate
    # them afresh.
    if from_existing is not None:
        logger.info("Copying files across from existing location %s.", from_existing)
        # Determine the existing location to copy files from and report an error if it
        # does not exist.
        existing_location_directory = new_location_data[0][DIRECTORY].format(
            location=from_existing,
            locations_folder_name=LOCATIONS_FOLDER_NAME,
        )
        if not os.path.isdir(existing_location_directory):
            logger.error(
                "The new-locations script was called to create a location from an "
                "existing location, but the existing location, %s, could not be found.",
                from_existing,
            )
            raise FileNotFoundError(
                f"The existing location, {existing_location_directory}, could not be found."
            )

        # Copy over any of the files as per the set up in the new location.
        for directory, _, filenames in os.walk(
            os.path.join(existing_location_directory, INPUTS_DIRECTORY)
        ):
            for filename in filenames:
                try:
                    shutil.copy2(
                        os.path.join(
                            directory,
                            filename,
                        ),
                        os.path.join(
                            new_location_directory,
                            os.path.relpath(directory, existing_location_directory),
                            filename,
                        ),
                    )
                    logger.info(
                        "File copied over from existing location: %s",
                        os.path.join(
                            os.path.relpath(directory, new_location_directory), filename
                        ),
                    )
                except FileNotFoundError:
                    logger.info(
                        "File could not be copied over: %s",
                        os.path.join(
                            os.path.relpath(directory, new_location_directory), filename
                        ),
                    )
            logger.info(
                "Directory %s successfully copied over.",
                os.path.join(
                    os.path.relpath(directory, existing_location_directory),
                    os.path.relpath(directory, new_location_directory),
                ),
            )


def main(args: List[Any]) -> None:
    """
    The main method for the new-location-folder generation script.

    This will generate a new directory in the locations folder based on the command-line
    arguments passed in.

    Inputs:
        - args:
            The un-parsed command-line arguments.

    """

    logger = get_logger(LOGGER_NAME)
    logger.info("New location script called with arguments: %s", args)
    parsed_args = _parse_args(args)
    create_new_location(
        parsed_args.from_existing, parsed_args.location, logger, parsed_args.update
    )
    logger.info("New-location script complete. Exiting.")


if __name__ == "__main__":
    main(sys.argv[1:])
