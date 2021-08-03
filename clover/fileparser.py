#!/usr/bin/python3
########################################################################################
# fileparser.py - File-parsing code for CLOVER.                                        #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 13/07/2021                                                             #
# License: Open source                                                                 #
########################################################################################
"""
fileparser.py - The argument-parsing module for CLOVER.

"""

from clover.scripts.new_location import DIRECTORY
import os

from logging import Logger
from typing import Any, Dict, Optional, Set, Tuple

import pandas as pd

from . import load
from .simulation import energy_system
from .optimisation.optimisation import Optimisation

from .__utils__ import (
    BColours,
    KEROSENE_DEVICE_NAME,
    Location,
    LOCATIONS_FOLDER_NAME,
    read_yaml,
    Scenario,
    Simulation,
)

__all__ = (
    "INPUTS_DIRECTORY",
    "KEROSENE_TIMES_FILE",
    "KEROSENE_USAGE_FILE",
    "parse_input_files",
)


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
ENERGY_SYSTEM_INPUTS_FILE = os.path.join("simulation", "energy_system.yaml")

# Finance inputs file:
#   The relative path to the finance-inputs file.
FINANCE_INPUTS_FILE = os.path.join("impact", "finance_inputs.yaml")

# GHG inputs file:
#   The relative path to the GHG inputs file.
GHG_INPUTS_FILE = os.path.join("impact", "ghg_inputs.yaml")

# Grid inputs file:
#   The relative path to the grid-inputs file.
GRID_INPUTS_FILE = os.path.join("generation", "grid", "grid_inputs.csv")

# Inputs directory:
#   The directory containing user inputs.
INPUTS_DIRECTORY = "inputs"

# Kerosene filepath:
#   The path to the kerosene information file which needs to be provided for CLOVER.
KEROSENE_TIMES_FILE = os.path.join("load", "device_utilisation", "kerosene_times.csv")

# Kerosene utilisation filepath:
#   The path to the kerosene utilisation profile.
KEROSENE_USAGE_FILE = os.path.join("load", "device_usage", "kerosene_in_use.csv")

# Location inputs file:
#   The relative path to the location inputs file.
LOCATION_INPUTS_FILE = os.path.join("location_data", "location_inputs.yaml")

# Optimisation inputs file:
#   The relative path to the optimisation-input information file.
OPTIMISATION_INPUTS_FILE = os.path.join("optimisation", "optimisation_inputs.yaml")

# Scenario inputs file:
#   The relative path to the scenario inputs file.
SCENARIO_INPUTS_FILE = os.path.join("scenario", "scenario_inputs.yaml")

# Simulation inputs file:
#   The relative path to the simulation inputs file.
SIMULATIONS_INPUTS_FILE = os.path.join("simulation", "simulations.yaml")

# Solar inputs file:
#   The relative path to the solar inputs file.
SOLAR_INPUTS_FILE = os.path.join("generation", "solar", "solar_generation_inputs.yaml")


def parse_input_files(
    location: str,
    logger: Logger,
    optimisations_file: Optional[str],
) -> Tuple[
    Dict[load.load.Device, pd.DataFrame],
    Dict[str, Any],
    energy_system.Minigrid,
    Dict[str, Any],
    Dict[str, Any],
    pd.DataFrame,
    Dict[str, Any],
    Set[Optimisation],
    Scenario,
    Set[Simulation],
    Dict[str, Any],
    Dict[str, str],
]:
    """
    Parse the various input files and return content-related information.

    Inputs:
        - location:
            The name of the location being considered.
        - logger:
            The logger to use for the run.
        - optimisations_file:
            The path to the optimisations file to use.

    Outputs:
        - A tuple containing:
            - device_utilisations,
            - diesel_inputs,
            - minigrid,
            - finance_inputs,
            - ghg_inputs,
            - grid_inputs,
            - optimisation_inputs,
            - optimisations, the `set` of optimisations to run,
            - scenario,
            - simulations, the `set` of simulations to run,
            - solar_generation_inputs,
            - a `dict` containing information about the input files used.

    """

    inputs_directory_relative_path = os.path.join(
        LOCATIONS_FOLDER_NAME,
        location,
        INPUTS_DIRECTORY,
    )

    device_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        DEVICE_INPUTS_FILE,
    )
    devices: Set[load.load.Device] = {
        load.load.Device.from_dict(entry)
        for entry in read_yaml(
            device_inputs_filepath,
            logger,
        )
    }
    logger.info("Device inputs successfully parsed.")

    # Add the kerosene device information if it was not provided.
    if KEROSENE_DEVICE_NAME not in {device.name for device in devices}:
        logger.info(
            "%sNo kerosene device information provided in the device file. "
            "Auto-generating device information.%s",
            BColours.warning,
            BColours.endc,
        )
        devices.add(load.DEFAULT_KEROSENE_DEVICE)
        logger.info("Default kerosene device added.")

    device_utilisations: Dict[load.load.Device, pd.DataFrame] = dict()
    for device in devices:
        try:
            with open(
                os.path.join(
                    inputs_directory_relative_path,
                    DEVICE_UTILISATIONS_INPUT_DIRECTORY,
                    DEVICE_UTILISATION_TEMPLATE_FILENAME.format(device=device.name),
                ),
                "r",
            ) as f:
                device_utilisations[device] = pd.read_csv(
                    f,
                    header=None,
                    index_col=None,
                )
        except FileNotFoundError:
            logger.error(
                "%sError parsing device-utilisation profile for %s, check that the "
                "profile is present and that all device names are consistent.%s",
                BColours.fail,
                device.name,
                BColours.endc,
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

    energy_system_inputs_filepath = os.path.join(
        inputs_directory_relative_path, ENERGY_SYSTEM_INPUTS_FILE
    )
    minigrid = energy_system.Minigrid.from_dict(
        read_yaml(energy_system_inputs_filepath, logger)
    )
    logger.info("Energy-system inputs successfully parsed.")

    finance_inputs_filepath = os.path.join(
        inputs_directory_relative_path, FINANCE_INPUTS_FILE
    )
    finance_inputs = read_yaml(finance_inputs_filepath, logger)
    logger.info("Finance inputs successfully parsed.")

    ghg_inputs_filepath = os.path.join(inputs_directory_relative_path, GHG_INPUTS_FILE)
    ghg_inputs = read_yaml(ghg_inputs_filepath, logger)
    logger.info("GHG inputs successfully parsed.")

    grid_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        GRID_INPUTS_FILE,
    )
    with open(
        grid_inputs_filepath,
        "r",
    ) as grid_inputs_file:
        grid_inputs = pd.read_csv(
            grid_inputs_file,
            index_col=0,
        )
    logger.info("Grid inputs successfully parsed.")

    location_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        LOCATION_INPUTS_FILE,
    )
    location = Location.from_dict(
        read_yaml(
            location_inputs_filepath,
            logger,
        )
    )
    logger.info("Location inputs successfully parsed.")

    optimisation_inputs_filepath = os.path.join(
        inputs_directory_relative_path, OPTIMISATION_INPUTS_FILE
    )
    optimisation_inputs = read_yaml(optimisation_inputs_filepath, logger)
    logger.info("Optimisation inputs successfully parsed.")

    if optimisations_file is not None:
        optimisations_filepath = os.path.join(
            inputs_directory_relative_path, optimisations_file
        )
        optimisations_inputs = read_yaml(optimisations_filepath, logger)
        try:
            optimisations = {
                Optimisation.from_dict(logger, entry) for entry in optimisations_inputs
            }
        except Exception as e:
            logger.error(
                "%sError generating optimisations from inputs file: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise
        logger.info("Optimisations file successfully parsed.")
    else:
        logger.info("Optimisations file path not provided, skipping.")

    scenario_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        SCENARIO_INPUTS_FILE,
    )
    scenario_inputs = read_yaml(
        scenario_inputs_filepath,
        logger,
    )
    try:
        scenario = Scenario.from_dict(scenario_inputs)
    except Exception as e:
        logger.error(
            "%sError generating scenario from inputs file: %s%s",
            BColours.fail,
            str(e),
            BColours.endc,
        )
        raise
    logger.info("Scenario inputs successfully parsed.")

    simulations_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        SIMULATIONS_INPUTS_FILE,
    )
    simulations_file_contents = read_yaml(
        simulations_inputs_filepath,
        logger,
    )
    simulations = {Simulation.from_dict(entry) for entry in simulations_file_contents}

    solar_generation_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        SOLAR_INPUTS_FILE,
    )
    solar_generation_inputs = read_yaml(
        solar_generation_inputs_filepath,
        logger,
    )
    logger.info("Solar generation inputs successfully parsed.")

    # Generate a dictionary with information about the input files used.
    input_file_info = {
        "devices": device_inputs_filepath,
        "diesel_inputs": diesel_inputs_filepath,
        "energy_system": energy_system_inputs_filepath,
        "finance_inputs": finance_inputs_filepath,
        "ghg_inputs": ghg_inputs_filepath,
        "grid_inputs": grid_inputs_filepath,
        "location_inputs": location_inputs_filepath,
        "optimisation_inputs": optimisation_inputs_filepath,
        "optimisations": optimisations_filepath,
        "scenario": scenario_inputs_filepath,
        "simularion": simulations_inputs_filepath,
        "solar_inputs": solar_generation_inputs_filepath,
    }

    return (
        device_utilisations,
        diesel_inputs,
        minigrid,
        finance_inputs,
        ghg_inputs,
        grid_inputs,
        location,
        optimisation_inputs,
        optimisations,
        scenario,
        simulations,
        solar_generation_inputs,
        input_file_info,
    )
