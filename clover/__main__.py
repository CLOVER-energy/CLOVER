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

import datetime
import logging
import os
import sys

from argparse import Namespace
from functools import partial
from multiprocessing import Pool
from typing import Any, Dict, List, Optional, Set

import pandas as pd  # type: ignore

from tqdm import tqdm  # type: ignore

from . import analysis, argparser
from .fileparser import (
    INPUTS_DIRECTORY,
    KEROSENE_TIMES_FILE,
    KEROSENE_USAGE_FILE,
    parse_input_files,
)
from .generation import grid, solar, weather
from .load import load
from .scripts import new_location
from .simulation import energy_system

from .__utils__ import (
    BColours,
    LoadType,
    get_logger,
    InputFileError,
    LOCATIONS_FOLDER_NAME,
    LOGGER_DIRECTORY,
    OperatingMode,
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

# Done message:
#   The message to display when a task was successful.
DONE = "[   DONE   ]"

# Failed message:
#   The message to display when a task has failed.
FAILED = "[  FAILED  ]"

# Logger name:
#   The name to use for the main logger for CLOVER
LOGGER_NAME = "clover"

# Number of Workers:
#   The number of CPUs to use, which dictates the number of workers to use for parllel
#   jobs.
NUM_WORKERS = 8

# Simulation outputs folder:
#   The folder into which outputs should be saved.
SIMULATION_OUTPUTS_FOLDER = os.path.join("outputs", "simulation_outputs")


def _get_operating_mode(parsed_args: Namespace) -> OperatingMode:
    """
    Determine the operating mode for CLOVER based on the command-line arguments.

    Inputs:
        - parsed_args:
            The parsed command-line arguments.

    Outputs:
        - The operating mode to use for the run.

    """

    # Try to determine the operating mode.
    if parsed_args.simulation:
        return OperatingMode.SIMULATION
    if parsed_args.optimisation:
        return OperatingMode.OPTIMISATION
    return OperatingMode.PROFILE_GENERATION


def _prepare_location(location: str, logger: logging.Logger):
    """
    Prepares the location and raises an error if the location cannot be found.

    Inputs:
        - location
            The name of the location to check.

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


def main(args: List[Any]) -> None:
    """
    The main module for CLOVER executing all functionality as appropriate.

    Inputs:
        - args
            The command-line arguments, passed in as a list.

    """

    logger = get_logger(LOGGER_NAME)
    logger.info("CLOVER run initiated. Options specified: %s", " ".join(args))

    # Parse and validate the command-line arguments.
    parsed_args = argparser.parse_args(args)
    logger.info("Command-line arguments successfully parsed.")

    if not argparser.validate_args(logger, parsed_args):
        logger.error(
            "%sInvalid command-line arguments. Check that all required arguments have "
            "been specified correctly. See %s for details.%s",
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

    # Define common variables.
    auto_generated_files_directory = os.path.join(
        LOCATIONS_FOLDER_NAME, parsed_args.location, AUTO_GENERATED_FILES_DIRECTORY,
    )

    # If the output filename is not provided, then generate it.
    output_directory = os.path.join(
        LOCATIONS_FOLDER_NAME, parsed_args.location, SIMULATION_OUTPUTS_FOLDER,
    )

    # Determine the operating mode for the run.
    operating_mode = _get_operating_mode(parsed_args)
    if operating_mode == OperatingMode.SIMULATION:
        logger.info(
            "A single CLOVER simulation will be run for locatation '%s'.",
            parsed_args.location,
        )
        print(f"A single CLOVER simulation will be run for {parsed_args.location}.")
    if operating_mode == OperatingMode.OPTIMISATION:
        logger.info(
            "A CLOVER optimisation will be run for location '%s'.", parsed_args.location
        )
        print(f"A CLOVER optimisation will be run for {parsed_args.location}.")
    if operating_mode == OperatingMode.PROFILE_GENERATION:
        logger.info("No CLI mode was specified, CLOVER will only generate profiles.")
        print(
            "Neither `simulation` or `optimisation` specified, running profile "
            f"generation only for {parsed_args.location}."
        )

    # If the output folder already exists, then confirm from the user that they wish to
    # overwrite its contents.
    if parsed_args.output is not None:
        if os.path.isdir(os.path.join(output_directory, parsed_args.output)):
            try:
                confirm_overwrite = {"y": True, "n": False, "Y": True, "N": False}[
                    input(
                        f"Output folder, {parsed_args.output}, already exists, Overwrite? [y/n] "
                    )
                ]
            except KeyError:
                logger.error(
                    "Either 'y' or 'n' must be specified to confirm overwrite. Quitting."
                )
                raise
        if confirm_overwrite:
            output = parsed_args.output
        else:
            output = input("Specify new output folder name: ")
        print(f"Output directory {output} will be used for simulation results.")
    else:
        output: str = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

    # Verify the location as containing all the required files.
    print("Verifying location information ................................    ", end="")
    logger.info("Checking location %s.", parsed_args.location)
    try:
        _prepare_location(parsed_args.location, logger)
    except FileNotFoundError:
        print(FAILED)
        logger.error(
            "%sThe location, '%s', is missing files. Try running the `new_location` "
            "script to identify missing files. See %s for details.%s",
            BColours.fail,
            parsed_args.location,
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
            BColours.endc,
        )
        raise

    # Parse the various input files.
    print(
        f"{DONE}\nParsing input files ...........................................    ",
        end="",
    )
    logger.info("Parsing input files.")

    try:
        (
            convertors,
            device_utilisations,
            minigrid,
            finance_inputs,
            generation_inputs,
            ghg_inputs,
            grid_inputs,
            location,
            optimisation_inputs,
            optimisations,
            pv_panel,
            scenario,
            simulations,
            solar_generation_inputs,
            input_file_info,
        ) = parse_input_files(parsed_args.location, logger)
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
    except InputFileError as e:
        print(FAILED)
        logger.error("Input file error occured: %s", str(e))
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
    else:
        logger.info("All input files successfully parsed.")
        print(DONE)

    print("Generating necessary profiles", end="\n")

    # Generate and save the weather data for each year as a background task.
    if LoadType.CLEAN_WATER in scenario.load_types:
        # Set up the system to call renewables.ninja at a slower rate.
        num_ninjas = 2
        logger.info("Beggining weather-data fetching.")
        weather_data_thread: Optional[
            weather.WeatherDataThread
        ] = weather.WeatherDataThread(
            os.path.join(auto_generated_files_directory, "weather"),
            generation_inputs,
            location,
            weather.WEATHER_LOGGER_NAME,
            parsed_args.refetch,
            num_ninjas,
        )
        weather_data_thread.start()
        logger.info(
            "Weather-data thread successfully instantiated. See %s for details.",
            "{}.log".format(
                os.path.join(LOGGER_DIRECTORY, weather.WEATHER_LOGGER_NAME)
            ),
        )
    else:
        weather_data_thread = None
        num_ninjas = 1

    # Generate and save the solar data for each year as a background task.
    logger.info("Beginning solar-data fetching.")
    solar_data_thread = solar.SolarDataThread(
        os.path.join(auto_generated_files_directory, "solar"),
        generation_inputs,
        location,
        solar.SOLAR_LOGGER_NAME,
        parsed_args.refetch,
        solar_generation_inputs,
        num_ninjas,
    )
    solar_data_thread.start()
    logger.info(
        "Solar-data thread successfully instantiated. See %s for details.",
        "{}.log".format(os.path.join(LOGGER_DIRECTORY, solar.SOLAR_LOGGER_NAME)),
    )

    # Generate and save the device-ownership profiles.
    logger.info("Processing device informaiton.")
    # load_logger = get_logger(load.LOAD_LOGGER_NAME)

    if LoadType.ELECTRIC in scenario.load_types:
        try:
            (
                initial_electric_hourly_loads,
                total_electric_load,
                electric_yearly_load_statistics,
            ) = load.process_load_profiles(
                auto_generated_files_directory,
                device_utilisations,
                load.LoadType.ELECTRIC,
                location,
                logger,
                parsed_args.regenerate,
            )
        except InputFileError:
            print(
                "Generating necessary profiles .................................    "
                + f"{FAILED}"
            )
            raise
        except Exception as e:
            print(
                "Generating necessary profiles .................................    "
                + f"{FAILED}"
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
    else:
        initial_electric_hourly_loads = None
        total_electric_load = None
        electric_yearly_load_statistics = None

    if LoadType.CLEAN_WATER in scenario.load_types:
        # Raise an error if there are no clean-water devices specified.
        if (
            len(
                {
                    device
                    for device in device_utilisations
                    if device.clean_water_usage is not None
                }
            )
            == 0
        ):
            raise InputFileError(
                "devices input flie",
                "No clean-water input devices were specified despite the scenario "
                "containing a clean-water system.",
            )

        try:
            (
                initial_clean_water_hourly_loads,
                total_clean_water_load,
                clean_water_yearly_load_statistics,
            ) = load.process_load_profiles(
                auto_generated_files_directory,
                device_utilisations,
                load.LoadType.CLEAN_WATER,
                location,
                logger,
                parsed_args.regenerate,
            )
        except InputFileError:
            print(
                "Generating necessary profiles .................................    "
                + f"{FAILED}"
            )
            raise
        except Exception as e:
            print(
                "Generating necessary profiles .................................    "
                + f"{FAILED}"
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
    else:
        initial_clean_water_hourly_loads = None
        total_clean_water_load = None
        clean_water_yearly_load_statistics = None

    # Generate the grid-availability profiles.
    logger.info("Generating grid-availability profiles.")
    try:
        grid.get_lifetime_grid_status(
            os.path.join(auto_generated_files_directory, "grid"),
            grid_inputs,
            logger,
            location.max_years,
        )
    except InputFileError:
        print(
            "Generating necessary profiles .................................    "
            + f"{FAILED}"
        )
        raise
    except Exception as e:
        print(
            "Generating necessary profiles .................................    "
            + f"{FAILED}"
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
    if weather_data_thread is not None:
        weather_data_thread.join()
    logger.info("All setup threads finished.")

    logger.info("Generating and saving total solar output file.")
    total_solar_output = solar.total_solar_output(
        os.path.join(auto_generated_files_directory, "solar"),
        parsed_args.regenerate,
        generation_inputs["start_year"],
        location.max_years,
    )
    logger.info("Total solar output successfully computed and saved.")

    logger.info("Generating and saving total weather output file.")
    total_weather_output = weather.total_weather_output(
        os.path.join(auto_generated_files_directory, "weather"),
        parsed_args.regenerate,
        generation_inputs["start_year"],
        location.max_years,
    )
    total_temperature_output = total_weather_output[0]
    total_precipitation_output = total_weather_output[1]
    total_solar_irradiance_output = total_weather_output[2]
    total_cloud_cover_fraction_output = total_weather_output[3]
    logger.info("Total weather output successfully computed and saved.")

    logger.info("Setup complete, continuing to CLOVER simulation.")

    print(
        f"Generating necessary profiles .................................    {DONE}",
        end="\n",
    )

    # Load the relevant grid profile.
    try:
        with open(
            os.path.join(
                auto_generated_files_directory,
                "grid",
                f"{scenario.grid_type}_grid_status.csv",
            ),
            "r",
        ) as f:
            grid_profile = pd.read_csv(f, index_col=0,)
    except FileNotFoundError as e:
        logger.error(
            "%sGrid profile file for profile '%s' could not be found: %s%s",
            BColours.fail,
            scenario.grid_type,
            str(e),
            BColours.endc,
        )
        raise

    # Load the relevant kerosene profile.
    with open(
        os.path.join(auto_generated_files_directory, KEROSENE_USAGE_FILE), "r"
    ) as f:
        kerosene_usage = pd.read_csv(f, index_col=0)

        # Remove the index from the file.
        kerosene_usage.reset_index(drop=True)

    # * Run a simulation or optimisation as appropriate.
    if operating_mode == OperatingMode.SIMULATION:
        print(
            "Beginning CLOVER simulation runs {}    ".format("." * 30,), end="\n",
        )
        simulation_times: List[str] = []

        for simulation_number, simulation in enumerate(
            tqdm(simulations, desc="simulations", unit="simulation"), 1
        ):
            try:
                (
                    time_delta,
                    system_performance_outputs,
                    system_details,
                ) = energy_system.run_simulation(
                    convertors,
                    minigrid,
                    grid_profile,
                    kerosene_usage,
                    location,
                    logger,
                    parsed_args.pv_system_size,
                    scenario,
                    simulation,
                    solar_generation_inputs["lifetime"],
                    parsed_args.storage_size,
                    0.001 * total_electric_load,
                    total_solar_output,
                    total_clean_water_load,
                )
            except Exception as e:
                print(
                    "Beginning CLOVER simulation runs {}    {}".format("." * 30, FAILED)
                )
                logger.error(
                    "%sAn unexpected error occurred running a CLOVER simulation. See %s for "
                    "details: %s%s",
                    BColours.fail,
                    "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
                    str(e),
                    BColours.endc,
                )
                raise

            # Add the time to the counter.
            simulation_times.append(
                "{0:.3f} s/year".format(
                    time_delta.microseconds
                    * 0.0000010
                    / (simulation.end_year - simulation.start_year)
                )
            )

            # Add the input file information to the system details file.
            system_details.file_information = input_file_info

            # Compute the key results.
            key_results = analysis.get_key_results(
                grid_inputs[scenario.grid_type],
                simulation.end_year - simulation.start_year,
                system_performance_outputs,
                total_solar_output,
            )

            if parsed_args.analyse:
                # Generate and save the various plots.
                analysis.plot_outputs(
                    grid_inputs[scenario.grid_type],
                    grid_profile,
                    initial_clean_water_hourly_loads,
                    initial_electric_hourly_loads,
                    simulation.end_year - simulation.start_year,
                    output_directory,
                    output,
                    simulation_number,
                    system_performance_outputs,
                    total_clean_water_load,
                    0.001 * total_electric_load,
                    total_solar_output,
                )
            else:
                logger.info("No analysis to be carried out.")

            # Save the simulation output.
            save_simulation(
                key_results,
                logger,
                output,
                output_directory,
                system_performance_outputs,
                simulation_number,
                system_details,
            )

        print("Beginning CLOVER simulation runs {}    {}".format("." * 30, DONE))

        print(
            "Time taken for simulations: {}".format(", ".join(simulation_times)),
            end="\n",
        )

    if operating_mode == OperatingMode.OPTIMISATION:
        pass
        # run_optimisation()

    if operating_mode == OperatingMode.PROFILE_GENERATION:
        print("No simulations or optimisations to be carried out.")

    # ******* #
    # *  4  * #
    # ******* #

    print(
        "Finished. See {} for output files.".format(
            os.path.join(LOCATIONS_FOLDER_NAME, parsed_args.location, "outputs")
        )
    )


if __name__ == "__main__":
    main(sys.argv[1:])
