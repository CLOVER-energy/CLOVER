#!/usr/bin/python3
########################################################################################
# __utils__.py - CLOVER Utility module.                                                #
#                                                                                      #
# Author: Phil Sandwell, Ben Winchester                                                #
# Copyright: Phil Sandwell, 2018                                                       #
# Date created: 13/07/2021                                                             #
#                                                                                      #
# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
__utils__.py - Utility module for CLOVER.

The utility module contains functionality which is used by various scripts, modules, and
components across CLOVER, as well as commonly-held variables to prevent dependency
issues and increase the ease of code alterations.

"""

import logging
import os

from typing import Any, Dict

import yaml

__all__ = (
    "get_logger",
    "LOCATIONS_FOLDER_NAME",
    "LOGGER_DIRECTORY",
    "read_yaml",
)


# Locations folder name:
#   The name of the locations folder.
LOCATIONS_FOLDER_NAME = "locations"

# Logger directory:
#   The directory in which to save logs.
LOGGER_DIRECTORY = "logs"


def get_logger(logger_name: str) -> logging.Logger:
    """
    Set-up and return a logger.

    Inputs:
        - logger_name:
            The name for the logger, which is also used to denote the filename with a
            "<logger_name>.log" format.

    Outputs:
        - The logger for the component.

    """

    # Create a logger and logging directory.
    logger = logging.getLogger(logger_name)
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
    if os.path.isfile(os.path.join(LOGGER_DIRECTORY, f"{logger_name}.log")):
        os.remove(os.path.join(LOGGER_DIRECTORY, f"{logger_name}.log"))

    # Create a file handler.
    file_handler = logging.FileHandler(
        os.path.join(LOGGER_DIRECTORY, f"{logger_name}.log")
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # Add the file handler to the logger.
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def read_yaml(filepath: str, logger: logging.Logger) -> Dict[Any, Any]:
    """
    Reads a YAML file and returns the contents.


    """

    # Process the new-location data.
    try:
        with open(filepath, "r") as filedata:
            file_contents = yaml.safe_load(filedata)
    except FileNotFoundError:
        logger.error(
            "The file specified, %s, could not be found. "
            "Ensure that you run the new-locations script from the workspace root.",
            filepath,
        )
        raise
    return file_contents
