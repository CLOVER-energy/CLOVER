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

__version__ = "5.0.0a1.dev5"

import datetime
import logging
import math
import os
import sys

from argparse import Namespace
from typing import Any, Dict, List, Optional, Tuple

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
from .optimisation.optimisation import multiple_optimisation_step

from .__utils__ import (
    BColours,
    DONE,
    ELECTRIC_POWER,
    FAILED,
    InternalError,
    Location,
    ResourceType,
    get_logger,
    InputFileError,
    LOCATIONS_FOLDER_NAME,
    LOGGER_DIRECTORY,
    OperatingMode,
    save_optimisation,
    save_simulation,
)
from .generation.__utils__ import SolarDataType

__all__ = ("main",)

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
{version_line}

                         For more information, contact
                   Phil Sandwell (philip.sandwell@gmail.com)
               or Ben Winchester (benedict.winchester@gmail.com)

"""

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


def _prepate_water_system(
    available_conventional_sources: List[str],
    auto_generated_files_directory: str,
    device_utilisations: Dict[load.Device, pd.DataFrame],
    location: Location,
    logger: logging.Logger,
    parsed_args: Namespace,
    resource_type: ResourceType,
    water_source_times: Dict[WaterSource, pd.DataFrame],
) -> Tuple[
    Dict[WaterSource, pd.DataFrame], pd.DataFrame, Dict[str, pd.DataFrame], pd.DataFrame
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
            resource_type,
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
            "%sAn unexpected error occurred generating the %s load profiles. See %s "
            "for details: %s%s",
            BColours.fail,
            resource_type.value,
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
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
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
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
        ", ".join(
            [str(source) for source in conventional_water_source_profiles.keys()]
        ),
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


def main(args: List[Any]) -> None:
    """
    The main module for CLOVER executing all functionality as appropriate.

    Inputs:
        - args
            The command-line arguments, passed in as a list.

    """

    # Parse the command-line arguments and instantiate the logger.
    parsed_args = argparser.parse_args(args)
    logger = get_logger(f"{parsed_args.location}_{LOGGER_NAME}", parsed_args.verbose)
    logger.info("CLOVER run initiated. Options specified: %s", " ".join(args))

    # Validate the command-line arguments.
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

    version_string = f"Version {__version__}"
    print(
        CLOVER_HEADER_STRING.format(
            version_line="{}{}{}".format(
                " " * (40 - math.ceil(len(version_string) / 2)),
                version_string,
                " " * (40 - math.floor(len(version_string) / 2)),
            )
        )
    )

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
        logger.info(
            "A single CLOVER simulation will be run for locatation '%s'",
            parsed_args.location,
        )
        print(f"A single CLOVER simulation will be run for {parsed_args.location}.")
    if operating_mode == OperatingMode.OPTIMISATION:
        logger.info(
            "A CLOVER optimisation will be run for location '%s'", parsed_args.location
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
        if os.path.isdir(os.path.join(simulation_output_directory, parsed_args.output)):
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
            print(f"Output directory {output} will be used for simulation results.")
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
            grid_times,
            location,
            optimisation_inputs,
            optimisations,
            scenario,
            simulations,
            water_source_times,
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

    # If the inputs do not match up correctly, then raise errors.
    if scenario.desalination_scenario is not None and minigrid.clean_water_tank is None:
        raise InputFileError(
            "energy system inputs",
            "No clean-water tank was provided despite there needing to be a tank "
            "specified for dealing with clean-water demands.",
        )
    if operating_mode == OperatingMode.SIMULATION:
        if (scenario.pv and parsed_args.pv_system_size is None) or (
            not scenario.pv and parsed_args.pv_system_size is not None
        ):
            raise InputFileError(
                "scenario",
                "PV mode in the scenario file must match the command-line usage.",
            )
        if (
            parsed_args.clean_water_pvt_system_size is not None
            and (scenario.desalination_scenario is None)
        ) or (
            parsed_args.clean_water_pvt_system_size is None
            and (scenario.desalination_scenario is not None)
        ):
            logger.error(
                "%sPV-T mode and available resources in the scenario file must match "
                "the command-line usage. Check the clean-water and PV-T scenario "
                "specification.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "scenario",
                "Mismatch between command-line usage and in-file usage.",
            )
        if (
            parsed_args.hot_water_pvt_system_size is not None
            and (scenario.hot_water_scenario is None)
        ) or (
            parsed_args.hot_water_pvt_system_size is None
            and (scenario.hot_water_scenario is not None in scenario.resource_types)
        ):
            logger.error(
                "%sPV-T mode in the scenario file must match the command-line usage. "
                "Check the hot-water and PV-T scenario specification.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "scenario",
                "Mismatch between command-line usage and in-file usage.",
            )
        if (
            scenario.pv_t
            and scenario.desalination_scenario is None
            and scenario.hot_water_scenario is None
        ) or (
            not scenario.pv_t
            and scenario.desalination_scenario is not None
            and scenario.hot_water_scenario is not None
        ):
            logger.error(
                "%sDesalination or hot-water scenario usage does not match the "
                "system's PV-T panel inclusion.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "scenario",
                "The PV-T mode does not match the hot-water or desalination scenarios.",
            )
        if (scenario.battery and parsed_args.storage_size is None) or (
            not scenario.battery and parsed_args.storage_size is not None
        ):
            raise InputFileError(
                "scenario",
                "Battery mode in the scenario file must match the command-line usage.",
            )

    print("Generating necessary profiles", end="\n")

    # Determine the number of background tasks to carry out.
    num_ninjas: int = (
        1
        + (1 if scenario.pv_t else 0)
        + (1 if scenario.desalination_scenario is not None else 0)
    )

    # Generate and save the wind data for each year as a background task.
    if scenario.pv_t:
        logger.info("Beginning wind-data fetching.")
        wind_data_thread: Optional[wind.WindDataThread] = wind.WindDataThread(
            os.path.join(auto_generated_files_directory, "wind"),
            generation_inputs,
            location,
            f"{parsed_args.location}_{wind.WIND_LOGGER_NAME}",
            parsed_args.refetch,
            num_ninjas,
        )
        if wind_data_thread is None:
            raise InternalError("Wind data thread failed to successfully instantiate.")
        wind_data_thread.start()
        logger.info(
            "Wind-data thread successfully instantiated. See %s for details.",
            "{}.log".format(os.path.join(LOGGER_DIRECTORY, wind.WIND_LOGGER_NAME)),
        )
    else:
        wind_data_thread = None

    # Generate and save the weather data for each year as a background task.
    if scenario.desalination_scenario is not None:
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
        )
        if weather_data_thread is None:
            raise InternalError(
                "Weather data thread failed to successfully instantiate."
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

    # Generate and save the solar data for each year as a background task.
    logger.info("Beginning solar-data fetching.")
    solar_data_thread = solar.SolarDataThread(
        os.path.join(auto_generated_files_directory, "solar"),
        generation_inputs,
        location,
        f"{parsed_args.location}_{solar.SOLAR_LOGGER_NAME}",
        parsed_args.refetch,
        minigrid.pv_panel,
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

    initial_electric_hourly_loads: Optional[Dict[str, pd.DataFrame]] = None
    total_electric_load: Optional[pd.DataFrame] = None
    electric_yearly_load_statistics: Optional[pd.DataFrame] = None

    if ResourceType.ELECTRIC in scenario.resource_types:
        try:
            (
                initial_electric_hourly_loads,
                total_electric_load,
                electric_yearly_load_statistics,
            ) = load.process_load_profiles(
                auto_generated_files_directory,
                device_utilisations,
                load.ResourceType.ELECTRIC,
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

    clean_water_yearly_load_statistics: Optional[pd.DataFrame] = None
    conventional_clean_water_source_profiles: Optional[
        Dict[WaterSource, pd.DataFrame]
    ] = None
    initial_clean_water_hourly_loads: Optional[Dict[str, pd.DataFrame]] = None
    total_clean_water_load: Optional[pd.DataFrame] = None

    if scenario.desalination_scenario is not None:
        (
            conventional_clean_water_source_profiles,
            initial_clean_water_hourly_loads,
            total_clean_water_load,
            clean_water_yearly_load_statistics,
        ) = _prepate_water_system(
            scenario.desalination_scenario.clean_water_scenario.conventional_sources,
            auto_generated_files_directory,
            device_utilisations,
            location,
            logger,
            parsed_args,
            ResourceType.CLEAN_WATER,
            water_source_times,
        )

    conventional_hot_water_source_profiles: Optional[
        Dict[WaterSource, pd.DataFrame]
    ] = None
    hot_water_yearly_load_statistics: Optional[pd.DataFrame] = None
    initial_hot_water_hourly_loads: Optional[Dict[str, pd.DataFrame]] = None
    total_hot_water_load: Optional[pd.DataFrame] = None

    if scenario.hot_water_scenario is not None:
        (
            conventional_hot_water_source_profiles,
            initial_hot_water_hourly_loads,
            total_hot_water_load,
            hot_water_yearly_load_statistics,
        ) = _prepate_water_system(
            scenario.hot_water_scenario.conventional_sources,
            auto_generated_files_directory,
            device_utilisations,
            location,
            logger,
            parsed_args,
            ResourceType.HOT_CLEAN_WATER,
            water_source_times,
        )

    # Assemble a means of storing the relevant loads.
    total_loads: Dict[ResourceType, Optional[pd.DataFrame]] = {
        ResourceType.CLEAN_WATER: total_clean_water_load,
        ResourceType.ELECTRIC: 0.001 * total_electric_load,
        ResourceType.HOT_CLEAN_WATER: total_hot_water_load,
    }

    # Generate the grid-availability profiles.
    logger.info("Generating grid-availability profiles.")
    try:
        grid.get_lifetime_grid_status(
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

    if (
        scenario.desalination_scenario is not None
        or scenario.hot_water_scenario is not None
    ):
        logger.info("Generating and saving total weather output file.")
        total_weather_data = weather.total_weather_output(
            os.path.join(auto_generated_files_directory, "weather"),
            parsed_args.regenerate,
            generation_inputs["start_year"],
            location.max_years,
        )
        logger.info("Total weather output successfully computed and saved.")

    if scenario.pv_t:
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
            grid_profile = pd.read_csv(
                f,
                index_col=0,
            )
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
        kerosene_usage = pd.read_csv(f, header=None, index_col=False)

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
            "Beginning CLOVER simulation runs {}    ".format(
                "." * 30,
            ),
            end="\n",
        )
        simulation_times: List[str] = []

        simulation_string: str = (
            (
                (
                    f"- {parsed_args.pv_system_size * minigrid.pv_panel.pv_unit} kWp of PV"
                    + (
                        (
                            f" ({parsed_args.pv_system_size}x "
                            + f"{minigrid.pv_panel.pv_unit} kWp panels)"
                        )
                        if overrided_default_sizes
                        else ""
                    )
                    + "\n"
                )
                if parsed_args.pv_system_size is not None and scenario.pv
                else ""
            )
            + f"- {parsed_args.storage_size * minigrid.battery.storage_unit} kWh of "
            + "storage"
            + (
                (
                    f" ({parsed_args.storage_size}x "
                    + f"{minigrid.battery.storage_unit} kWh batteries)"
                )
                if overrided_default_sizes
                else ""
            )
            + "\n"
            + (
                "- {} Clean-water PV-T panel units ({} kWp PV per unit)\n".format(
                    parsed_args.clean_water_pvt_system_size,
                    minigrid.pvt_panel.pv_unit,
                )
                if parsed_args.clean_water_pvt_system_size is not None
                else ""
            )
            + (
                "- {}x {} litres clean-water storage{}".format(
                    parsed_args.num_clean_water_tanks,
                    minigrid.clean_water_tank.mass,
                    "\n" if scenario.hot_water_scenario is not None else "",
                )
                if scenario.desalination_scenario is not None
                else ""
            )
            + (
                "- {} Hot-water PV-T panel units ({} kWp PV per unit)\n".format(
                    parsed_args.hot_water_pvt_system_size,
                    minigrid.pvt_panel.pv_unit,
                )
                if parsed_args.hot_water_pvt_system_size is not None
                else ""
            )
            + (
                "- {}x {} litres hot-water storage".format(
                    parsed_args.num_hot_water_tanks, minigrid.hot_water_tank.mass
                )
                if scenario.hot_water_scenario is not None
                else ""
            )
        )
        print(f"Running a simulation with:\n{simulation_string}")

        for simulation_number, simulation in enumerate(
            tqdm(simulations, desc="simulations", unit="simulation"), 1
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
                    conventional_clean_water_source_profiles,
                    convertors,
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
                print(
                    "Beginning CLOVER simulation runs {}    {}".format("." * 30, FAILED)
                )
                logger.error(
                    "%sAn unexpected error occurred running a CLOVER simulation. See "
                    "%s for "
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
                    (time_delta.seconds + time_delta.microseconds * 0.000001)
                    / (simulation.end_year - simulation.start_year)
                )
            )

            # Add the input file information to the system details file.
            system_details.file_information = input_file_info

            # Compute the key results.
            key_results = analysis.get_key_results(
                grid_times[scenario.grid_type],
                simulation.end_year - simulation.start_year,
                system_performance_outputs,
                total_solar_data[solar.SolarDataType.ELECTRICITY.value]
                * minigrid.pv_panel.pv_unit,
            )

            if parsed_args.analyse:
                # Generate and save the various plots.
                analysis.plot_outputs(
                    grid_times[scenario.grid_type],
                    grid_profile,
                    initial_clean_water_hourly_loads,
                    initial_electric_hourly_loads,
                    initial_hot_water_hourly_loads,
                    simulation.end_year - simulation.start_year,
                    simulation_output_directory,
                    output,
                    simulation_number,
                    system_performance_outputs,
                    total_loads,
                    total_solar_data[solar.SolarDataType.ELECTRICITY.value]
                    * minigrid.pv_panel.pv_unit,
                )
            else:
                logger.info("No analysis to be carried out.")

            # Save the simulation output.
            save_simulation(
                key_results,
                logger,
                output,
                simulation_output_directory,
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
        print(
            "Beginning CLOVER optimisation runs {}    ".format(
                "." * 28,
            ),
            end="\n",
        )
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

        optimisation_string: str = "\n".join(
            [
                entry
                for entry in [
                    "- PV resolution of {} units ({} kWp per unit)".format(
                        optimisation_inputs.pv_size_step, minigrid.pv_panel.pv_unit
                    )
                    if scenario.pv and optimisation_inputs.pv_size_step is not None
                    else None,
                    "- Storage resolution of {} units ({} kWh per unit)".format(
                        optimisation_inputs.storage_size_step,
                        minigrid.battery.storage_unit,
                    )
                    if scenario.battery
                    and optimisation_inputs.storage_size_step is not None
                    else None,
                    (
                        "- PV-T resolution of "
                        + "{} units ({} kWp and {} kWth per unit)".format(
                            optimisation_inputs.pvt_size_step,
                            minigrid.pvt_panel.pv_unit,
                            minigrid.pvt_panel.thermal_unit,
                        )
                    )
                    if scenario.pv_t and optimisation_inputs.pvt_size_step is not None
                    else "",
                    (
                        "- Clean-water tank resolution of {} ".format(
                            optimisation_inputs.clean_water_tanks_step
                        )
                        + "units (1 tank of size {} litres per unit)".format(
                            minigrid.clean_water_tank.mass
                        )
                    )
                    if scenario.desalination_scenario is not None
                    and optimisation_inputs.clean_water_tanks_step is not None
                    else None,
                ]
                if entry is not None
            ]
        )
        print(f"Running an optimisation with:\n{optimisation_string}")

        for optimisation_number, optimisation in enumerate(
            tqdm(optimisations, desc="optimisations", unit="optimisation"), 1
        ):
            try:
                time_delta, optimisation_results = multiple_optimisation_step(
                    convertors,
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
                    scenario,
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
                print(
                    "Beginning CLOVER optimisation runs {}    {}".format(
                        "." * 28, FAILED
                    )
                )
                logger.error(
                    "%sAn unexpected error occurred running a CLOVER optimisation. See "
                    "%s for "
                    "details: %s%s",
                    BColours.fail,
                    "{}.log".format(os.path.join(LOGGER_DIRECTORY, LOGGER_NAME)),
                    str(e),
                    BColours.endc,
                )
                raise

            # Add the time to the counter.
            optimisation_times.append(
                "{0:.3f} s/year".format(
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
                logger,
                optimisation_inputs,
                optimisation_number,
                output,
                optimisation_output_directory,
                optimisation_results,
            )

        print("Beginning CLOVER optimisation runs {}    {}".format("." * 28, DONE))

        print(
            "Time taken for optimisations: {}".format(", ".join(optimisation_times)),
            end="\n",
        )

    if operating_mode == OperatingMode.PROFILE_GENERATION:
        print("No simulations or optimisations to be carried out.")

    print(
        "Finished. See {} for output files.".format(
            os.path.join(LOCATIONS_FOLDER_NAME, parsed_args.location, "outputs")
        )
    )


if __name__ == "__main__":
    main(sys.argv[1:])
