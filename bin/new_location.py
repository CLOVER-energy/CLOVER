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
import os
import sys


import yaml


from typing import Any, List


# The keyword used to denote the contents of a file or folder.
CONTENTS = "contents"
# The keyword used to denote a directory.
DIRECTORY = "directory"
# The keyword used to denote a file.
FILE = "file"
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

    with open(os.path.join(directory, filename), "w") as f:
        f.write(contents)


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
        if DIRECTORY in entry:
            _create_folder_and_contents(
                entry[CONTENTS],
                entry[DIRECTORY],
                os.path.join(parent_directory, directory_name),
            )


def _parse_args(args: List[Any]) -> argparse.Namespace:
    """
    Parse the CLI arguments to determine the flow of the script.

    """

    parser = argparse.ArgumentParser()

    parser.add_argument("location", help="The name of the new location to be created.")
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

    parsed_args = _parse_args(args)
    try:
        with open(NEW_LOCATION_DATA_FILE, "r") as f:
            new_location_data = yaml.safe_load(f)
    except FileNotFoundError:
        print(
            "ERROR: The new-location data file could not be found. "
            "Ensure that you run the new-locations script from the workspace root."
        )
        raise

    # Process the new-location data into a usable format.
    import pdb

    pdb.set_trace()
    new_location_data[0][DIRECTORY] = new_location_data[0][DIRECTORY].format(
        location=parsed_args.location
    )

    # Generate files as per the hard-coded directory structure.
    _create_folder_and_contents(
        new_location_data[0][CONTENTS], new_location_data[0][DIRECTORY], os.getcwd()
    )

    # Copy across files from the existing structure if they exist, otherwise, generate
    # them afresh.


if __name__ == "__main__":
    main(sys.argv[1:])
