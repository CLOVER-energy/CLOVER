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

import os

from typing import Set

from .__utils__ import Device, read_yaml

__all__ = ("parse_input_files",)


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

# Scenario inputs file:
#   The relative path to the scenario inputs file.
SCENARIO_INPUTS_FILE = os.path.join("scenario", "scenario_inputs.yaml")

# Simulation inputs file:
#   The relative path to the simulation inputs file.
SIMULATION_INPUTS_FILE = os.path.join("simulation", "simulation.yaml")

# Simulation outputs folder:
#   The folder into which outputs should be saved.
SIMULATION_OUTPUTS_FOLDER = os.path.join("outputs", "simulation_outputs")

# Solar inputs file:
#   The relative path to the solar inputs file.
SOLAR_INPUTS_FILE = os.path.join("generation", "solar", "solar_generation_inputs.yaml")


def parse_input_files(location: str):
    """
    Parse the various input files and return content-related information.

    Inputs:
        - location:
            The name of the location being considered.

    """

    inputs_directory_relative_path = os.path.join(
        LOCATIONS_FOLDER_NAME,
        location,
        INPUTS_DIRECTORY,
    )

    try:
        devices: Set[Device] = {
            Device.from_dict(entry)
            for entry in read_yaml(
                os.path.join(
                    inputs_directory_relative_path,
                    DEVICE_INPUTS_FILE,
                ),
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

        device_utilisations: Dict[Device, pd.DataFrame] = dict()
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

        location = Location.from_dict(
            read_yaml(
                os.path.join(
                    inputs_directory_relative_path,
                    LOCATION_INPUTS_FILE,
                ),
                logger,
            )
        )
        logger.info("Location inputs successfully parsed.")

        scenario_inputs = read_yaml(
            os.path.join(
                inputs_directory_relative_path,
                SCENARIO_INPUTS_FILE,
            ),
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

        simulation = Simulation.from_dict(
            read_yaml(
                os.path.join(
                    inputs_directory_relative_path,
                    SIMULATION_INPUTS_FILE,
                ),
                logger,
            )
        )

        solar_generation_inputs = read_yaml(
            os.path.join(
                inputs_directory_relative_path,
                SOLAR_INPUTS_FILE,
            ),
            logger,
        )
        logger.info("Solar generation inputs successfully parsed.")
    except FileNotFoundError as e:
        print(FAILED)
        logger.error(
            "%sNot all input files present. See %s for details: %s%s",
            BColours.fail,
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
            str(e),
            BColours.endc,
        )
        raise
    except Exception as e:
        print(FAILED)
        logger.error(
            "%sAn unexpected error occured parsing input files. See %s for details: "
            "%s%s",
            BColours.fail,
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
            str(e),
            BColours.endc,
        )
        raise
