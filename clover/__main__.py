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
from typing import Any, Dict, List, Set

import pandas as pd

from . import argparser
from .generation import grid, solar
from .load import load
from .scripts import new_location
from .simulation import energy_system

from atpbar import atpbar

from .__utils__ import (
    BColours,
    Device,
    get_logger,
    InvalidLocationError,
    KEROSENE_DEVICE_NAME,
    Location,
    LOCATIONS_FOLDER_NAME,
    LOGGER_DIRECTORY,
    OperatingMode,
    read_yaml,
    Scenario,
    Simulation,
    save_simulation,
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

# Logger name:
#   The name to use for the main logger for CLOVER
LOGGER_NAME = "clover"

# Number of Workers:
#   The number of CPUs to use, which dictates the number of workers to use for parllel
#   jobs.
NUM_WORKERS = 8

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
            "%sThe specified location, '%s', does not exist. Try running the "
            "'new_location' script to ensure all necessary files and folders are "
            "present.%s",
            BColours.fail,
            location,
            BColours.endc,
        )
        raise FileNotFoundError(
            "The location, {}, could not be found.".format(location)
        )

    if not os.path.isfile(
        os.path.join(
            LOCATIONS_FOLDER_NAME, location, INPUTS_DIRECTORY, KEROSENE_TIMES_FILE
        )
    ):
        logger.info(
            "%sThe specified location, '%s', does not contain a kerosene times file. "
            "The auto-generation script will be run to replace the lost file.%s",
            BColours.warning,
            location,
            BColours.endc,
        )
        new_location.create_new_location(None, location, logger, True)
        logger.info("%s succesfully updated with missing files.", location)

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
            "%sInvalid command-line arguments. Check that all required arguments have "
            "been specified. See %s for details.%s",
            BColours.fail,
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
            BColours.endc,
        )
        raise ValueError(
            "The command-line arguments were invalid. See {} for details.".format(
                "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME))
            )
        )

    logger.info("Command-line arguments successfully validated.")

    print(CLOVER_HEADER_STRING)

    # Try to determine the operating mode.
    if parsed_args.simulation:
        operating_mode = OperatingMode.SIMULATION
        logger.info(
            "A single CLOVER simulation will be run for locatation '%s'.",
            parsed_args.location,
        )
        print(f"A single CLOVER simulation will be run for {parsed_args.location}.")
    elif parsed_args.optimisation:
        operating_mode = OperatingMode.OPTIMISATION
        logger.info(
            "A CLOVER optimisation will be run for location '%s'.", parsed_args.location
        )
        print(f"A CLOVER optimisation will be run for {parsed_args.location}.")
    else:
        operating_mode = OperatingMode.PROFILE_GENERATION
        logger.info("No CLI mode was specified, CLOVER will only generate profiles.")
        print(
            "Neither `simulation` or `optimisation` specified, running profile "
            f"generation only for {parsed_args.location}."
        )

    # If the location does not exist or does not meet the required specification, then
    # exit now.
    print("Verifying location information ................................    ", end="")
    logger.info("Checking location %s.", parsed_args.location)
    if not _check_location(parsed_args.location, logger):
        print("[  FAILED  ]\n")
        logger.error(
            "%sThe location, '%s', is invalid. Try running the `new_location` script to"
            "identify missing files. See %s for details.%s",
            BColours.fail,
            parsed_args.location,
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
            BColours.endc,
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
        print("[  FAILED  ]\n")
        logger.error(
            "%sNot all input files present. See %s for details: %s%s",
            BColours.fail,
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
            str(e),
            BColours.endc,
        )
        raise
    except Exception as e:
        print("[  FAILED  ]\n")
        logger.error(
            "%sAn unexpected error occured parsing input files. See %s for details: "
            "%s%s",
            BColours.fail,
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
            str(e),
            BColours.endc,
        )
        raise

    logger.info("All input files successfully parsed.")
    print(
        "[   DONE   ]\nGenerating necessary profiles",
        end="\n",
    )

    # Generate and save the solar data for each year as a background task.
    logger.info("Beginning solar-data fetching.")
    solar_data_thread = solar.SolarDataThread(
        os.path.join(auto_generated_files_directory, "solar"),
        location,
        parsed_args.regenerate,
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
            devices,
            device_utilisations,
            location,
            logger,
            parsed_args.regenerate,
        )
    except Exception as e:
        print(
            "Generating necessary profiles ................................. "
            "[  FAILED  ]\n"
        )
        logger.error(
            "%sAn unexpected error occurred generating the load profiles. See %s for "
            "details: %s%s",
            BColours.fail,
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
            str(e),
            BColours.endc,
        )
        raise

    # Generate the grid-availability profiles.
    logger.info("Generating grid-availability profiles.")
    try:
        grid.get_lifetime_grid_status(
            os.path.join(auto_generated_files_directory, "grid"),
            grid_inputs,
            logger,
            location.max_years,
        )
    except Exception as e:
        print(
            "Generating necessary profiles ................................. "
            "[  FAILED  ]\n"
        )
        logger.error(
            "%sAn unexpected error occurred generating the grid profiles. See %s for "
            "details: %s%s",
            BColours.fail,
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
            str(e),
            BColours.endc,
        )
        raise

    logger.info("Grid-availability profiles successfully generated.")

    # Wait for all threads to finish before proceeding.
    logger.info("Waiting for all setup threads to finish before proceeding.")
    solar_data_thread.join()
    logger.info("All setup threads finished.")

    logger.info("Generating and saving total solar output file.")
    total_solar_output = solar.total_solar_output(
        os.path.join(auto_generated_files_directory, "solar"),
        solar_generation_inputs["start_year"],
    )
    logger.info("Total solar output successfully computed and saved.")

    logger.info("Setup complete, continuing to CLOVER simulation.")

    print(
        "Generating necessary profiles ................................. "
        "   [   DONE   ]\n"
        "Beginning CLOVER simulation run ...............................    ",
        end="",
    )

    # ******* #
    # *  3  * #
    # ******* #

    # Load the relevant grid profile.
    with open(
        os.path.join(
            auto_generated_files_directory,
            "grid",
            f"{scenario.grid_type}_grid_status.csv",
        ),
        "r",
    ) as f:
        grid_profile = pd.read_csv(
            f,
            index_col=0,
        )

    # Load the relevant kerosene profile.
    with open(
        os.path.join(auto_generated_files_directory, KEROSENE_USAGE_FILE), "r"
    ) as f:
        kerosene_usage = pd.read_csv(f, index_col=0)

        # Remove the index from the file.
        kerosene_usage.reset_index(drop=True)

    # * Run a simulation or optimisation as appropriate.
    if operating_mode == OperatingMode.SIMULATION:
        try:
            (
                time_delta,
                system_performance_outputs,
                system_details,
            ) = energy_system.run_simulation(
                minigrid,
                grid_profile,
                kerosene_usage,
                location,
                parsed_args.pv_system_size,
                scenario,
                simulation,
                solar_generation_inputs["lifetime"],
                parsed_args.storage_size,
                total_load,
                total_solar_output,
            )
        except Exception as e:
            print("[  FAILED  ]\n")
            logger.error(
                "%sAn unexpected error occurred running a CLOVER simulation. See %s for "
                "details: %s%s",
                BColours.fail,
                "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
                str(e),
                BColours.endc,
            )
            raise

        print("[   DONE   ]")
        print(
            "Time taken for simulation: {0:.2f} seconds per year.".format(
                (time_delta.microseconds * 0.000001)
                / float(simulation.end_year - simulation.start_year)
            ),
            end="\n",
        )

        # Save the simulation output.
        save_simulation(
            parsed_args.output,
            logger,
            os.path.join(
                LOCATIONS_FOLDER_NAME, parsed_args.location, SIMULATION_OUTPUTS_FOLDER
            ),
            system_performance_outputs,
        )

    # ******* #
    # *  4  * #
    # ******* #

    # * Run any and all analysis as appropriate.
    print("No analysis to be carried out.")

    print(
        "Finished. See {} for output files.".format(
            os.path.join(LOCATIONS_FOLDER_NAME, parsed_args.location, "outputs")
        )
    )


if __name__ == "__main__":
    main(sys.argv[1:])
