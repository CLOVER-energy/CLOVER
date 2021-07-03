#!/usr/bin/python3
########################################################################################
# new_location.py - Script for generating a new location folder.
#
# Author: Ben Winchester
# Date created: 01/07/2021
# License: Open source
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


# The keyword used to denote the contents of a file or folder.
CONTENTS = "contents"
# The keyword used to denote a directory.
DIRECTORY = "directory"
# The keyword used to denote a file.
FILE = "file"
# The directory in which to save logs.
LOGGER_DIRECTORY = "logs"
# The name of the logger to use.
LOGGER_NAME = "new_location"
# The path to the new-location data file.
NEW_LOCATION_DATA_FILE = os.path.join("src", "new_location.yaml")


def _create_file(contents: str, directory: str, filename: str) -> None:
    """
    Creates a file within the directory specified with the contents passed in.

    :param contents:
        The contents of the file to be created.

    :param directory:
        The name of the directory in which to create the file.

    :param filename:
        The name of the file to be created.

    """

    if not os.path.isdir(directory):
        raise FileNotFoundError(
            "The directory {} could not be found.".format(directory)
        )

    with open(os.path.join(directory, filename), "w") as new_file:
        new_file.write(contents)


def _create_folder_and_contents(
    contents: List[Any], directory_name: str, parent_directory: str
) -> None:
    """
    Creates a folder and all files and folders contained within it.

    :param contents:
        The contents of the folder.

    :param directory_name:
        The name of the directory being created.

    :param parent_directory:
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
            )
            continue
        if DIRECTORY in entry:
            _create_folder_and_contents(
                entry[CONTENTS] if CONTENTS in entry else [],
                entry[DIRECTORY],
                os.path.join(parent_directory, directory_name),
            )


def _get_logger() -> logging.Logger:
    """
    Set-up and return a logger.

    :return:
        The logger for the component.

    """

    # Create a logger and logging directory.
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    os.makedirs(LOGGER_DIRECTORY, exist_ok=True)

    # Create a formatter.
    formatter = logging.Formatter(
        "%(asctime)s: %(name)s: %(levelname)s: %(message)s",
        datefmt="%d/%m/%Y %I:%M:%S %p",
    )

    # Create a console handler.
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)
    console_handler.setFormatter(formatter)

    # Delete the existing log if there is one already.
    if os.path.isfile(os.path.join(LOGGER_DIRECTORY, f"{LOGGER_NAME}.log")):
        os.remove(os.path.join(LOGGER_DIRECTORY, f"{LOGGER_NAME}.log"))

    # Create a file handler.
    file_handler = logging.FileHandler(
        os.path.join(LOGGER_DIRECTORY, f"{LOGGER_NAME}.log")
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # Add the file handler to the logger.
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def _parse_args(args: List[Any]) -> argparse.Namespace:
    """
    Parse the CLI arguments to determine the flow of the script.

    """

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "location", type=str, help="The name of the new location to be created."
    )
    parser.add_argument(
        "--from-existing",
        type=str,
        help="The name of an existing location off which to model the new location.",
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

    logger = _get_logger()
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
        location=parsed_args.location
    )

    # Generate files as per the hard-coded directory structure.
    logger.info("Creating new-location folder for location %s.", parsed_args.location)
    _create_folder_and_contents(
        new_location_data[0][CONTENTS], new_location_directory, os.getcwd()
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
            location=parsed_args.from_existing
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
