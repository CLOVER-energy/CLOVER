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
import shutil
import sys


from typing import Any, List


import yaml


from ..__utils__ import get_logger, LOCATIONS_FOLDER_NAME


# The keyword used to denote the contents of a file or folder.
CONTENTS = "contents"
# The keyword used to denote a directory.
DIRECTORY = "directory"
# The keyword used to denote a file.
FILE = "file"
# The name of the logger to use.
LOGGER_NAME = "new_location"
# The path to the new-location data file.
NEW_LOCATION_DATA_FILE = os.path.join("src", "new_location.yaml")


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
        raise FileNotFoundError(
            "The directory {} could not be found.".format(directory)
        )

    if os.path.isfile(os.path.join(directory, filename)):
        logger.info(
            "File already exists, skipping creation: {}".format(
                os.path.join(directory, filename)
            )
        )
        return

    with open(os.path.join(directory, filename), "w") as new_file:
        new_file.write(contents)

    logger.info(
        "File successfully created: {}".format(os.path.join(directory, filename))
    )


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


def main(args: List[Any]) -> None:
    """
    The main method for the new-location-folder generation script.

    This will generate a new directory in the locations folder based on the command-line
    arguments passed in.

    :param args:
        The un-parsed command-line arguments.

    """

    logger = get_logger(LOGGER_NAME)
    logger.info("New location script called with arguments: %s", args)
    parsed_args = _parse_args(args)

    # Process the new-location data.
    try:
        with open(NEW_LOCATION_DATA_FILE, "r") as new_location_data_file:
            new_location_data = yaml.safe_load(new_location_data_file)
    except FileNotFoundError:
        logger.error(
            "The new-location data file could not be found. "
            "Ensure that you run the new-locations script from the workspace root."
        )
        raise
    logger.info("Data file successfully read.")

    # Process the new-location data into a usable format.
    new_location_directory = new_location_data[0][DIRECTORY].format(
        location=parsed_args.location, locations_folder_name=LOCATIONS_FOLDER_NAME
    )

    # If the new location already exists and the script is not run to update, then exit.
    if os.path.isdir(new_location_directory) and not parsed_args.update:
        logger.error(
            "The new location directory already exists and the script was not run with "
            "--update."
        )
        sys.exit(1)

    # Generate files as per the hard-coded directory structure.
    if parsed_args.update:
        logger.info(
            "Updating location folder with new and updated files %s.",
            parsed_args.location,
        )
    else:
        logger.info(
            "Creating new-location folder for location %s.", parsed_args.location
        )
    _create_folder_and_contents(
        new_location_data[0][CONTENTS], new_location_directory, logger, os.getcwd()
    )
    logger.info(
        "New location folder for %s successfully created.", parsed_args.location
    )

    # Copy across files from the existing structure if they exist, otherwise, generate
    # them afresh.
    if parsed_args.from_existing is not None:
        logger.info(
            "Copying files across from existing location %s.", parsed_args.from_existing
        )
        # Determine the existing location to copy files from and report an error if it
        # does not exist.
        existing_location_directory = new_location_data[0][DIRECTORY].format(
            location=parsed_args.from_existing,
            locations_folder_name=LOCATIONS_FOLDER_NAME,
        )
        if not os.path.isdir(existing_location_directory):
            logger.error(
                "The new-locations script was called to create a location from an "
                "existing location, but the existing location, %s, could not be found.",
                parsed_args.from_existing,
            )
            raise FileNotFoundError(
                "The existing location, {}, could not be found.".format(
                    existing_location_directory
                )
            )

        # Copy over any of the files as per the set up in the new location.
        for directory, _, filenames in os.walk(new_location_directory):
            for filename in filenames:
                try:
                    shutil.copy2(
                        os.path.join(
                            existing_location_directory,
                            os.path.relpath(directory, new_location_directory),
                            filename,
                        ),
                        os.path.join(directory, filename),
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
            logger.info("File copying complete.")
    logger.info("New-location script complete. Exiting.")


if __name__ == "__main__":
    main(sys.argv[1:])
