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

__version__ = "5.0.7b2"

import datetime
import logging
import math
import os
import sys

from argparse import Namespace
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd  # pylint: disable=import-error

from tqdm import tqdm

from . import analysis, argparser
from .conversion.conversion import WaterSource
from .fileparser import (
    INPUTS_DIRECTORY,
    KEROSENE_TIMES_FILE,
    KEROSENE_USAGE_FILE,
    parse_input_files,
)
from .generation import solar, weather, wind
from .load import load
from .mains_supply import grid, water_source
from .scripts import new_location
from .simulation import energy_system

from .optimisation.__utils__ import save_optimisation
from .optimisation.appraisal import appraise_system
from .optimisation.optimisation import multiple_optimisation_step
from .printer import generate_optimisation_string, generate_simulation_string

from .__utils__ import (
    BColours,
    DONE,
    FAILED,
    InternalError,
    Location,
    ResourceType,
    SystemAppraisal,
    get_logger,
    InputFileError,
    LOCATIONS_FOLDER_NAME,
    LOGGER_DIRECTORY,
    OperatingMode,
    save_simulation,
)
from .simulation.__utils__ import check_scenario

__all__ = ("main",)

# Auto-generated-files directory:
#   The name of the directory in which to save auto-generated files, relative to the
# root of the location.
AUTO_GENERATED_FILES_DIRECTORY = "auto_generated"

# Clover header string:
#   The ascii text to display when starting CLOVER.
CLOVER_HEADER_STRING = """
\033[38;5;40m
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
\033[0m


       Continuous Lifetime Optimisation of Variable Electricity Resources
                         Copyright Phil Sandwell, 2018
{version_line}

                         For more information, contact
                   Phil Sandwell (philip.sandwell@gmail.com),
                    Hamish Beath (hamishbeath@outlook.com),
               or Ben Winchester (benedict.winchester@gmail.com)

"""

# Debug string:
#   Text to display when debug mode is selected.
DEBUG_STRING: str = """{okblue}                        CLOVER is running in debug mode.
          For more information on debug mode, consult the user guide.
    If you did not intend to use debug mode, re-run without the debug flag.
{endc}"""

# Logger name:
#   The name to use for the main logger for CLOVER
LOGGER_NAME = "clover"

# Number of Workers:
#   The number of CPUs to use, which dictates the number of workers to use for parllel
#   jobs.
NUM_WORKERS = 8

# Outputs folder:
#   The folder into which outputs should be saved.
OUTPUTS_FOLDER = "outputs"

# Optimisation outputs folder:
#   The output folder into which to save the optimisation outputs.
OPTIMISATION_OUTPUTS_FOLDER = os.path.join(OUTPUTS_FOLDER, "optimisation_outputs")

# Simulation outputs folder:
#   The folder into which outputs should be saved.
SIMULATION_OUTPUTS_FOLDER = os.path.join(OUTPUTS_FOLDER, "simulation_outputs")


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


def _prepare_location(location: str, logger: logging.Logger) -> None:
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
        raise FileNotFoundError(f"The location, {location}, could not be found.")

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


def _prepare_water_system(
    available_conventional_sources: Set[str],
    auto_generated_files_directory: str,
    device_utilisations: Dict[load.Device, pd.DataFrame],
    disable_tqdm: bool,
    location: Location,
    logger: logging.Logger,
    parsed_args: Namespace,
    resource_type: ResourceType,
    water_source_times: Dict[WaterSource, pd.DataFrame],
) -> Tuple[
    Dict[WaterSource, pd.DataFrame], Dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame
]:
    """
    Prepares the conventional-water system.

    Inputs:
        - available_conventional_sources:
            The `list` of available conventional sources for the system.
        - auto_generated_files_directory:
            The directory into which auto-generated files should be saved.
        - device_utilisations:
            The utilisation profile for each :class:`load.Device` being modelled.
        - location:
            The :class:`Location` being considered.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - parsed_args:
            The parsed command-line arguments.
        - resource_type:
            The :class:`ResourceType` being considered.
        - water_source_times:
            The availability profile of each :class:`WaterSource` being considered.

    Outputs:
        - conventional_water_source_profiles:
            The availability profiles of the conventional water sources being
            considered.
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - initial_loads:
            The initial hourly loads placed on the conventional water system.
        - total_load:
            The total water load for each load type placed on the conventional water
            system.
        - yearly_load_statistics:
            The yearly load statistics for the conventional water system being
            considered.

    """

    # Raise an error if there are no water devices specified.
    if (
        resource_type == ResourceType.HOT_CLEAN_WATER
        and (
            len(
                {
                    device
                    for device in device_utilisations
                    if device.hot_water_usage is not None
                }
            )
            == 0
        )
        or resource_type == ResourceType.CLEAN_WATER
        and (
            len(
                {
                    device
                    for device in device_utilisations
                    if device.clean_water_usage is not None
                }
            )
            == 0
        )
    ):
        raise InputFileError(
            "devices input flie",
            f"No {resource_type.value} input devices were specified despite the "
            + "scenario containing a clean-water system.",
        )

    try:
        (
            initial_loads,
            total_load,
            yearly_load_statistics,
        ) = load.process_load_profiles(
            auto_generated_files_directory,
            device_utilisations,
            disable_tqdm,
            location,
            logger,
            parsed_args.regenerate,
            resource_type,
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
            "%sAn unexpected error occurred generating the %s load profiles. See %s "
            "for details: %s%s",
            BColours.fail,
            resource_type.value,
            f"{os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)}.log",
            str(e),
            BColours.endc,
        )
        raise

    # Generate the conventional-clean-water source availability profiles.
    logger.info(
        "Generating conventional %s water-source availability profiles.",
        resource_type.value,
    )
    try:
        conventional_water_source_profiles = (
            water_source.get_lifetime_water_source_status(
                disable_tqdm,
                os.path.join(auto_generated_files_directory, resource_type.value),
                resource_type.value.split("_")[0],
                location,
                logger,
                parsed_args.regenerate,
                water_source_times,
            )
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
            "%sAn unexpected error occurred generating the conventional %s "
            "water-source profiles. See %s for details: %s%s",
            BColours.fail,
            resource_type.value,
            f"{os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)}.log",
            str(e),
            BColours.endc,
        )
        raise

    logger.info(
        "Conventional %s water sources successfully parsed.", resource_type.value
    )
    logger.debug(
        "Conventional %s water sources: %s",
        resource_type.value,
        ", ".join([str(source) for source in conventional_water_source_profiles]),
    )

    conventional_water_source_profiles = {
        key: value
        for key, value in conventional_water_source_profiles.items()
        if key in available_conventional_sources
    }

    return (
        conventional_water_source_profiles,
        initial_loads,
        total_load,
        yearly_load_statistics,
    )


def main(  # pylint: disable=too-many-locals, too-many-statements
    args: List[Any], disable_tqdm: bool = False, run_number: Optional[int] = None
) -> None:
    """
    The main module for CLOVER executing all functionality as appropriate.

    Inputs:
        - args
            The command-line arguments, passed in as a list.
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - run_number:
            Used to differentiate between runs if multiple runs are being carried out
            for the same location.

    """

    # Parse the command-line arguments and instantiate the logger.
    parsed_args = argparser.parse_args(args)
    run_number_string: str = f"_{run_number}" if run_number is not None else ""
    logger = get_logger(
        f"{parsed_args.location}_{LOGGER_NAME}{run_number_string}",
        parsed_args.verbose,
    )
    logger.info("CLOVER run initiated. Options specified: %s", " ".join(args))

    # Validate the command-line arguments.
    logger.info("Command-line arguments successfully parsed.")

    if not argparser.validate_args(logger, parsed_args):
        logger.error(
            "%sInvalid command-line arguments. Check that all required arguments have "
            "been specified correctly. See %s for details.%s",
            BColours.fail,
            f"{os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)}.log",
            BColours.endc,
        )
        raise ValueError(
            "The command-line arguments were invalid. See "
            f"{os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)}.log for details."
        )

    logger.info("Command-line arguments successfully validated.")

    version_string = f"Version {__version__}"
    print(
        CLOVER_HEADER_STRING.format(
            version_line=(
                " " * (40 - math.ceil(len(version_string) / 2))
                + version_string
                + " " * (40 - math.floor(len(version_string) / 2))
            )
        )
    )

    if parsed_args.debug:
        print(DEBUG_STRING.format(okblue=BColours.okblue, endc=BColours.endc))

    # Define common variables.
    auto_generated_files_directory = os.path.join(
        LOCATIONS_FOLDER_NAME,
        parsed_args.location,
        AUTO_GENERATED_FILES_DIRECTORY,
    )

    # If the output filename is not provided, then generate it.
    simulation_output_directory = os.path.join(
        LOCATIONS_FOLDER_NAME,
        parsed_args.location,
        SIMULATION_OUTPUTS_FOLDER,
    )
    optimisation_output_directory = os.path.join(
        LOCATIONS_FOLDER_NAME, parsed_args.location, OPTIMISATION_OUTPUTS_FOLDER
    )

    # Determine the operating mode for the run.
    operating_mode = _get_operating_mode(parsed_args)
    if operating_mode == OperatingMode.SIMULATION:
        output_directory: Optional[str] = simulation_output_directory
        logger.info(
            "A single CLOVER simulation will be run for locatation '%s'",
            parsed_args.location,
        )
        print(
            f"A single CLOVER simulation will be run for {parsed_args.location}"
            + (
                f" {BColours.okblue}in debug mode{BColours.endc}"
                if parsed_args.debug
                else ""
            )
        )
    if operating_mode == OperatingMode.OPTIMISATION:
        output_directory = optimisation_output_directory
        logger.info(
            "A CLOVER optimisation will be run for location '%s'", parsed_args.location
        )
        print(
            f"A CLOVER optimisation will be run for {parsed_args.location}"
            + (
                f" {BColours.okblue}in debug mode{BColours.endc}"
                if parsed_args.debug
                else ""
            )
        )
    if operating_mode == OperatingMode.PROFILE_GENERATION:
        output_directory = None
        logger.info("No CLI mode was specified, CLOVER will only generate profiles.")
        print(
            "Neither `simulation` or `optimisation` specified, running profile "
            f"generation only for {parsed_args.location}"
            + (
                f" {BColours.okblue}in debug mode{BColours.endc}"
                if parsed_args.debug
                else ""
            )
        )

    # If the output folder already exists, then confirm from the user that they wish to
    # overwrite its contents.
    if parsed_args.output is not None:
        if output_directory is None:
            logger.error(
                "%sCannot specify an output directory if only profile generation is "
                "taking place.%s",
                BColours.fail,
                BColours.endc,
            )
            raise Exception(
                "The `output` flag can only be used if a simulation or optimisation "
                "output is expected."
            )
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
                output: str = str(parsed_args.output)
            else:
                output = input("Specify new output folder name: ")
            print(f"\nOutput directory {output} will be used for simulation results.")
        else:
            output = str(parsed_args.output)
    else:
        output = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

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
            f"{os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)}.log",
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
            converters,
            device_utilisations,
            minigrid,
            finance_inputs,
            generation_inputs,
            ghg_inputs,
            grid_times,
            location,
            optimisation_inputs,
            optimisations,
            scenarios,
            simulations,
            electric_load_profile,
            water_source_times,
            input_file_info,
        ) = parse_input_files(
            parsed_args.debug,
            parsed_args.electric_load_profile,
            parsed_args.location,
            logger,
            parsed_args.optimisation_inputs_file,
        )
    except FileNotFoundError as e:
        print(FAILED)
        logger.error(
            "%sNot all input files present. See %s for details: %s%s",
            BColours.fail,
            f"{os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)}.log",
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
            f"{os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)}.log",
            str(e),
            BColours.endc,
        )
        raise

    logger.info("All input files successfully parsed.")
    print(DONE)

    print("Generating necessary profiles", end="\n")

    # Determine the number of background tasks to carry out.
    num_ninjas: int = (
        1
        + (1 if any(scenario.pv_t for scenario in scenarios) else 0)
        + (
            1
            if any(scenario.desalination_scenario for scenario in scenarios) is not None
            else 0
        )
    )

    # Generate and save the wind data for each year as a background task.
    if any(scenario.pv_t for scenario in scenarios):
        logger.info("Beginning wind-data fetching.")
        wind_data_thread: Optional[wind.WindDataThread] = wind.WindDataThread(
            os.path.join(auto_generated_files_directory, "wind"),
            generation_inputs,
            location,
            f"{parsed_args.location}_{wind.WIND_LOGGER_NAME}",
            parsed_args.refetch,
            num_ninjas,
            parsed_args.verbose,
        )
        if wind_data_thread is None:
            raise InternalError("Wind data thread failed to successfully instantiate.")
        wind_data_thread.start()
        logger.info(
            "Wind-data thread successfully instantiated. See %s for details.",
            f"{os.path.join(LOGGER_DIRECTORY, wind.WIND_LOGGER_NAME)}.log",
        )
    else:
        wind_data_thread = None

    # Generate and save the weather data for each year as a background task.
    if any(scenario.desalination_scenario is not None for scenario in scenarios):
        # Set up the system to call renewables.ninja at a slower rate.
        logger.info("Begining weather-data fetching.")
        weather_data_thread: Optional[
            weather.WeatherDataThread
        ] = weather.WeatherDataThread(
            os.path.join(auto_generated_files_directory, "weather"),
            generation_inputs,
            location,
            f"{parsed_args.location}_{weather.WEATHER_LOGGER_NAME}",
            parsed_args.refetch,
            num_ninjas,
            parsed_args.verbose,
        )
        if weather_data_thread is None:
            raise InternalError(
                "Weather data thread failed to successfully instantiate."
            )
        weather_data_thread.start()
        logger.info(
            "Weather-data thread successfully instantiated. See %s for details.",
            f"{os.path.join(LOGGER_DIRECTORY, weather.WEATHER_LOGGER_NAME)}.log",
        )
    else:
        weather_data_thread = None

    # Generate and save the solar data for each year as a background task.
    logger.info("Beginning solar-data fetching.")
    solar_data_thread = solar.SolarDataThread(
        os.path.join(auto_generated_files_directory, "solar"),
        generation_inputs,
        location,
        f"{parsed_args.location}_{solar.SOLAR_LOGGER_NAME}{run_number_string}",
        parsed_args.refetch,
        minigrid.pv_panel,
        num_ninjas,
        parsed_args.verbose,
    )
    solar_data_thread.start()
    logger.info(
        "Solar-data thread successfully instantiated. See %s for details.",
        f"{os.path.join(LOGGER_DIRECTORY, solar.SOLAR_LOGGER_NAME)}.log",
    )

    # Generate and save the device-ownership profiles.
    logger.info("Processing device informaiton.")
    # load_logger = get_logger(load.LOAD_LOGGER_NAME)

    initial_electric_hourly_loads: Optional[Dict[str, pd.DataFrame]] = None
    total_electric_load: Optional[pd.DataFrame] = None
    electric_yearly_load_statistics: Optional[pd.DataFrame] = None

    if any(ResourceType.ELECTRIC in scenario.resource_types for scenario in scenarios):
        try:
            (
                initial_electric_hourly_loads,
                total_electric_load,
                electric_yearly_load_statistics,
            ) = load.process_load_profiles(
                auto_generated_files_directory,
                device_utilisations,
                disable_tqdm,
                location,
                logger,
                parsed_args.regenerate,
                load.ResourceType.ELECTRIC,
                electric_load_profile,
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
                f"{os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)}.log",
                str(e),
                BColours.endc,
            )
            raise

    clean_water_yearly_load_statistics: pd.DataFrame  # pylint: disable=unused-variable
    conventional_cw_source_profiles: Optional[Dict[WaterSource, pd.DataFrame]] = None
    initial_cw_hourly_loads: Optional[Dict[str, pd.DataFrame]] = None
    total_cw_load: Optional[pd.DataFrame] = None

    if any(scenario.desalination_scenario is not None for scenario in scenarios):
        # Create a set of all the conventional clean-water sources available.
        # @ BenWinchester - Repair conventional sources logic.
        conventional_sources: Set[str] = {
            source
            for scenario in scenarios
            if scenario.desalination_scenario is not None
            for source in scenario.desalination_scenario.clean_water_scenario.conventional_sources
        }

        # Generate the clean-water load profiles.
        (
            conventional_cw_source_profiles,
            initial_cw_hourly_loads,
            total_cw_load,
            clean_water_yearly_load_statistics,
        ) = _prepare_water_system(
            conventional_sources,
            auto_generated_files_directory,
            device_utilisations,
            disable_tqdm,
            location,
            logger,
            parsed_args,
            ResourceType.CLEAN_WATER,
            water_source_times,
        )

    conventional_hw_source_profiles: Dict[  # pylint: disable=unused-variable
        WaterSource, pd.DataFrame
    ]
    hot_water_yearly_load_statistics: pd.DataFrame  # pylint: disable=unused-variable
    initial_hw_hourly_loads: Optional[Dict[str, pd.DataFrame]] = None
    total_hw_load: Optional[pd.DataFrame] = None

    if any(scenario.hot_water_scenario is not None for scenario in scenarios):
        # Create a set of all the conventional hot-water sources available.
        # @ BenWinchester - Repair conventional sources logic.
        conventional_sources = {
            source
            for scenario in scenarios
            if scenario.hot_water_scenario is not None
            for source in scenario.hot_water_scenario.conventional_sources
        }

        (
            conventional_hw_source_profiles,
            initial_hw_hourly_loads,
            total_hw_load,
            hot_water_yearly_load_statistics,
        ) = _prepare_water_system(
            conventional_sources,
            auto_generated_files_directory,
            device_utilisations,
            disable_tqdm,
            location,
            logger,
            parsed_args,
            ResourceType.HOT_CLEAN_WATER,
            water_source_times,
        )

    # Assemble a means of storing the relevant loads.
    total_loads: Dict[ResourceType, Optional[pd.DataFrame]] = {
        ResourceType.CLEAN_WATER: total_cw_load,
        ResourceType.ELECTRIC: 0.001 * total_electric_load,  # type: ignore
        ResourceType.HOT_CLEAN_WATER: total_hw_load,
    }

    # Generate the grid-availability profiles if relevant.
    if any(scenario.grid for scenario in scenarios):
        logger.info("Generating grid-availability profiles.")
        try:
            grid.get_lifetime_grid_status(
                disable_tqdm,
                os.path.join(auto_generated_files_directory, "grid"),
                grid_times,
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
                f"{os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)}.log",
                str(e),
                BColours.endc,
            )
            raise

        logger.info("Grid-availability profiles successfully generated.")

    else:
        logger.info("Grid disabled, no grid profiles to be generated.")

    # Wait for all threads to finish before proceeding.
    logger.info("Waiting for all setup threads to finish before proceeding.")
    solar_data_thread.join()
    if weather_data_thread is not None:
        weather_data_thread.join()
    if wind_data_thread is not None:
        wind_data_thread.join()
    logger.info("All setup threads finished.")

    logger.info("Generating and saving total solar output file.")
    total_solar_data = solar.total_solar_output(
        os.path.join(auto_generated_files_directory, "solar"),
        parsed_args.regenerate,
        generation_inputs["start_year"],
        location.max_years,
    )
    logger.info("Total solar output successfully computed and saved.")

    if any(scenario.desalination_scenario is not None for scenario in scenarios) or any(
        scenario.hot_water_scenario is not None for scenario in scenarios
    ):
        logger.info("Generating and saving total weather output file.")
        total_weather_data = (  # pylint: disable=unused-variable
            weather.total_weather_output(
                os.path.join(auto_generated_files_directory, "weather"),
                parsed_args.regenerate,
                generation_inputs["start_year"],
                location.max_years,
            )
        )
        logger.info("Total weather output successfully computed and saved.")

    if any(scenario.pv_t for scenario in scenarios):
        logger.info("Generating and saving total wind data output file.")
        total_wind_data: Optional[pd.DataFrame] = wind.total_wind_output(
            os.path.join(auto_generated_files_directory, "wind"),
            parsed_args.regenerate,
            generation_inputs["start_year"],
            location.max_years,
        )
        logger.info("Total wind output successfully computed and saved.")
    else:
        total_wind_data = None

    logger.info(
        "Setup complete, continuing to CLOVER %s.",
        "main flow"
        if operating_mode == OperatingMode.PROFILE_GENERATION
        else operating_mode.value,
    )

    print(
        f"Generating necessary profiles .................................    {DONE}",
        end="\n",
    )

    # Load the relevant kerosene profile.
    try:
        with open(
            os.path.join(auto_generated_files_directory, KEROSENE_USAGE_FILE), "r"
        ) as f:
            kerosene_usage = pd.read_csv(f, header=None, index_col=False)
    except FileNotFoundError:
        logger.error(
            "%sKerosene usage file '%s' could not be found in '%s'. Check that this "
            "file has not been deleted.%s",
            BColours.fail,
            KEROSENE_USAGE_FILE,
            auto_generated_files_directory,
            BColours.endc,
        )
        raise

    # Remove the index from the file.
    kerosene_usage.reset_index(drop=True)

    # Determine whether any default sizes have been overrided.
    overrided_default_sizes: bool = (
        minigrid.pv_panel.pv_unit_overrided
        if minigrid.pv_panel is not None
        else False or minigrid.battery.storage_unit
        if minigrid.battery is not None
        else False
    )

    # Run a simulation or optimisation as appropriate.
    if operating_mode == OperatingMode.SIMULATION:
        print(
            f"Beginning CLOVER simulation runs {'.' * 30}    ",
            end="\n",
        )

        simulation_times: List[str] = []

        # Determine the scenario to use for the simulation.
        try:
            scenario = [
                scenario
                for scenario in scenarios
                if scenario.name == parsed_args.scenario
            ][0]
        except IndexError:
            logger.error(
                "%sUnable to locate scenario '%s' from scenarios.%s",
                BColours.fail,
                parsed_args.scenario,
                BColours.endc,
            )
            raise

        logger.info("Scenario '%s' successfully determined.", parsed_args.scenario)

        logger.info("Checking scenario parameters.")
        check_scenario(logger, minigrid, operating_mode, parsed_args, scenario)
        logger.info("Scenario parameters valid.")

        logger.info("Loading grid profile.")
        grid_profile = grid.load_grid_profile(
            auto_generated_files_directory, logger, scenario
        )
        logger.info("Grid '%s' profile successfully loaded.", scenario.grid_type)

        simulation_string: str = generate_simulation_string(
            minigrid, overrided_default_sizes, parsed_args, scenario
        )
        print(f"Running a simulation with:\n{simulation_string}")

        for simulation_number, simulation in enumerate(
            tqdm(
                simulations, desc="simulations", disable=disable_tqdm, unit="simulation"
            ),
            1,
        ):
            logger.info(
                "Carrying out simulation %s of %s.", simulation_number, len(simulations)
            )
            try:
                (
                    time_delta,
                    system_performance_outputs,
                    system_details,
                ) = energy_system.run_simulation(
                    parsed_args.clean_water_pvt_system_size
                    if parsed_args.clean_water_pvt_system_size is not None
                    else 0,
                    conventional_cw_source_profiles,
                    converters,
                    disable_tqdm,
                    parsed_args.storage_size,
                    grid_profile,
                    parsed_args.hot_water_pvt_system_size
                    if parsed_args.hot_water_pvt_system_size is not None
                    else 0,
                    total_solar_data[solar.SolarDataType.TOTAL_IRRADIANCE.value],
                    kerosene_usage,
                    location,
                    logger,
                    minigrid,
                    parsed_args.num_clean_water_tanks,
                    parsed_args.num_hot_water_tanks,
                    total_solar_data[solar.SolarDataType.ELECTRICITY.value]
                    * minigrid.pv_panel.pv_unit,
                    parsed_args.pv_system_size
                    if parsed_args.pv_system_size is not None
                    else 0,
                    scenario,
                    simulation,
                    total_solar_data[solar.SolarDataType.TEMPERATURE.value],
                    total_loads,
                    total_wind_data[wind.WindDataType.WIND_SPEED.value]
                    if total_wind_data is not None
                    else None,
                )
            except Exception as e:
                print(f"Beginning CLOVER simulation runs {'.' * 30}    {FAILED}")
                logger.error(
                    "%sAn unexpected error occurred running a CLOVER simulation. See "
                    "%s for "
                    "details: %s%s",
                    BColours.fail,
                    f"{os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)}.log",
                    str(e),
                    BColours.endc,
                )
                raise

            # Add the time to the counter.
            simulation_times.append(
                "{0:.3f} s/year".format(  # pylint: disable=consider-using-f-string
                    (time_delta.seconds + time_delta.microseconds * 0.000001)
                    / (simulation.end_year - simulation.start_year)
                )
            )

            # Add the input file information to the system details file.
            system_details.file_information = input_file_info

            # Compute the key results.
            key_results = analysis.get_key_results(  # type: ignore
                grid_profile,
                simulation.end_year - simulation.start_year,
                system_performance_outputs,
                total_solar_data[solar.SolarDataType.ELECTRICITY.value]
                * minigrid.pv_panel.pv_unit
                * scenario.pv,
            )

            if parsed_args.analyse:
                if not parsed_args.skip_plots:
                    # Generate and save the various plots.
                    analysis.plot_outputs(  # type: ignore
                        grid_times[scenario.grid_type],
                        grid_profile,
                        initial_cw_hourly_loads,
                        initial_electric_hourly_loads,
                        initial_hw_hourly_loads,
                        simulation.end_year - simulation.start_year,
                        simulation_output_directory,
                        output,
                        simulation_number,
                        system_performance_outputs,
                        total_loads,
                        total_solar_data[solar.SolarDataType.ELECTRICITY.value]
                        * minigrid.pv_panel.pv_unit,
                    )

                # Carry out an appraisal of the system.
                if electric_yearly_load_statistics is None:
                    raise InternalError(
                        "No electric yearly load statistics were computed for the "
                        "system despite these being needed to appraise the system."
                    )
                system_appraisal: Optional[SystemAppraisal] = appraise_system(
                    electric_yearly_load_statistics,
                    simulation.end_year,
                    finance_inputs,
                    ghg_inputs,
                    location,
                    logger,
                    None,
                    scenario,
                    system_performance_outputs,
                    simulation.start_year,
                    system_details,
                )
            else:
                system_appraisal = None
                logger.info("No analysis to be carried out.")

            # Save the simulation output.
            save_simulation(
                disable_tqdm,
                key_results,
                logger,
                output,
                simulation_output_directory,
                system_performance_outputs,
                simulation_number,
                system_appraisal,
                system_details,
            )

        print(f"Beginning CLOVER simulation runs {'.' * 30}    {DONE}")

        print(
            f"Time taken for simulations: {', '.join(simulation_times)}",
            end="\n",
        )

    if operating_mode == OperatingMode.OPTIMISATION:
        print(f"Beginning CLOVER optimisation runs {'.' * 28}    ", end="\n")
        optimisation_times: List[str] = []

        # Enforce that the optimisation inputs are set correctly before attempting an
        # optimisation.

        if optimisation_inputs is None:
            raise InputFileError(
                "optimisation inputs",
                "Optimisation inputs were not specified despite an optimisation being "
                "called.",
            )
        if electric_yearly_load_statistics is None:
            raise InternalError(
                "Electric yearly load statistics were not correctly computed despite "
                "being needed for an optimisation."
            )

        if (
            optimisation_inputs.number_of_iterations
            * optimisation_inputs.iteration_length
            > location.max_years
        ):
            raise InputFileError(
                "optimisation inputs",
                "An optimisation was requested that runs over the maximum lifetime of "
                "the system.",
            )

        for optimisation_number, optimisation in enumerate(
            tqdm(
                optimisations,
                desc="optimisations",
                disable=disable_tqdm,
                unit="optimisation",
            ),
            1,
        ):
            # Determine the scenario to use for the simulation.
            logger.info("Checking scenario parameters.")
            check_scenario(
                logger, minigrid, operating_mode, parsed_args, optimisation.scenario
            )
            logger.info("Scenario parameters valid.")

            logger.info("Loading grid profile.")
            grid_profile = grid.load_grid_profile(
                auto_generated_files_directory, logger, optimisation.scenario
            )
            logger.info(
                "Grid '%s' profile successfully loaded.",
                optimisation.scenario.grid_type,
            )

            optimisation_string = generate_optimisation_string(
                minigrid, optimisation_inputs, optimisation.scenario
            )
            print(f"Running an optimisation with:\n{optimisation_string}")

            try:
                time_delta, optimisation_results = multiple_optimisation_step(
                    conventional_cw_source_profiles,
                    converters,
                    disable_tqdm,
                    finance_inputs,
                    ghg_inputs,
                    grid_profile,
                    total_solar_data[solar.SolarDataType.TOTAL_IRRADIANCE.value],
                    kerosene_usage,
                    location,
                    logger,
                    minigrid,
                    optimisation,
                    optimisation_inputs,
                    total_solar_data[solar.SolarDataType.TEMPERATURE.value],
                    total_loads,
                    total_solar_data[solar.SolarDataType.ELECTRICITY.value]
                    * minigrid.pv_panel.pv_unit,
                    total_wind_data[wind.WindDataType.WIND_SPEED.value]
                    if total_wind_data is not None
                    else None,
                    electric_yearly_load_statistics,
                )
            except Exception as e:
                print(f"Beginning CLOVER optimisation runs {'.' * 28}    {FAILED}")
                logger.error(
                    "%sAn unexpected error occurred running a CLOVER optimisation. See "
                    "%s for "
                    "details: %s%s",
                    BColours.fail,
                    f"{os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)}.log",
                    str(e),
                    BColours.endc,
                )
                raise

            # Add the time to the counter.
            optimisation_times.append(
                "{0:.3f} s/year".format(  # pylint: disable=consider-using-f-string
                    (time_delta.seconds + time_delta.microseconds * 0.000001)
                    / (
                        optimisation_results[-1].system_details.end_year
                        - optimisation_results[0].system_details.start_year
                    )
                )
            )

            # Add the input file information to the system details file.
            for appraisal in optimisation_results:
                appraisal.system_details.file_information = input_file_info

            # Save the optimisation output.
            save_optimisation(
                disable_tqdm,
                logger,
                optimisation_inputs,
                optimisation_number,
                output,
                optimisation_output_directory,
                optimisation.scenario,
                optimisation_results,
            )

        print(f"Beginning CLOVER optimisation runs {'.' * 28}    {DONE}")

        print(
            f"Time taken for optimisations: {', '.join(optimisation_times)}",
            end="\n",
        )

    if operating_mode == OperatingMode.PROFILE_GENERATION:
        print("No simulations or optimisations to be carried out.")

    print(
        "Finished. See "
        + os.path.join(LOCATIONS_FOLDER_NAME, parsed_args.location, "outputs")
        + " for output files."
    )


if __name__ == "__main__":
    main(sys.argv[1:])
