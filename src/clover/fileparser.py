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
import pickle
import pkgutil

from collections import defaultdict
from logging import Logger
from typing import Any, DefaultDict, Dict, List, Optional, Set, Tuple, Union

import json
import pandas as pd  # pylint: disable=import-error

# from sklearn.linear_model._coordinate_descent import Lasso

from . import load
from .generation import solar
from .impact.finance import COSTS, FINANCE_IMPACT, ImpactingComponent
from .impact.ghgs import EMISSIONS, GHG_IMPACT
from .simulation.diesel import DIESEL_CONSUMPTION, MINIMUM_LOAD, DieselWaterHeater

from .__utils__ import (
    AuxiliaryHeaterType,
    BColours,
    DesalinationScenario,
    DieselMode,
    EXCHANGER,
    HotWaterScenario,
    HTFMode,
    InputFileError,
    InternalError,
    KEROSENE_DEVICE_NAME,
    ResourceType,
    Location,
    LOCATIONS_FOLDER_NAME,
    NAME,
    PACKAGE_NAME,
    RAW_CLOVER_PATH,
    read_yaml,
    Scenario,
    Simulation,
)
from .conversion.conversion import (
    Converter,
    MultiInputConverter,
    ThermalDesalinationPlant,
    WaterSource,
)
from .optimisation.__utils__ import Optimisation, OptimisationParameters
from .simulation.diesel import DieselGenerator
from .simulation.energy_system import Minigrid
from .simulation.transmission import Transmitter

__all__ = (
    "GENERATION_INPUTS_FILE",
    "INPUTS_DIRECTORY",
    "KEROSENE_TIMES_FILE",
    "KEROSENE_USAGE_FILE",
    "LOCATIONS_FOLDER_NAME",
    "parse_input_files",
    "parse_scenario_inputs",
)


# Battery:
#   Keyword used for parsing battery-related information.
BATTERY: str = "battery"

# Battery inputs file:
#   The relative path to the battery inputs file.
BATTERY_INPUTS_FILE: str = os.path.join("simulation", "battery_inputs.yaml")

# Conventional water-source-availability directory:
#   The directory containing availability profiles for conventional water sources.
CONVENTIONAL_WATER_SOURCE_AVAILABILITY_DIRECTORY: str = os.path.join(
    "generation", "conventional_water_sources"
)

# Conversion inputs file:
#   The relative path to the conversion-inputs file.
CONVERSION_INPUTS_FILE: str = os.path.join("generation", "conversion_inputs.yaml")

# Desalination scenarios:
#   Keyword used for parsing desalination scenarios.
DESALINATION_SCENARIOS: str = "desalination_scenarios"

# Desalination scenario inputs file:
#   The relative path to the desalination-scenario inputs file.
DESALINATION_SCENARIO_INPUTS_FILE: str = os.path.join(
    "scenario", "desalination_scenario.yaml"
)

# Load inputs directory path:
#   The relative path to the load inputs directory to use when parsing total load
# profiles.
LOAD_INPUTS_DIRECTORY: str = "load"

# Device inputs file:
#   The relative path to the device-inputs file.
DEVICE_INPUTS_FILE: str = os.path.join(LOAD_INPUTS_DIRECTORY, "devices.yaml")

# Device utilisation template filename:
#   The template filename of device-utilisation profiles used for parsing the files.
DEVICE_UTILISATION_TEMPLATE_FILENAME: str = "{device}_times.csv"

# Device utilisations input directory:
#   The relative path to the directory contianing the device-utilisaion information.
DEVICE_UTILISATIONS_INPUT_DIRECTORY: str = os.path.join(
    LOAD_INPUTS_DIRECTORY, "device_utilisation"
)

# Diesel generator:
#   Keyword used for parsing diesel-generator information.
DIESEL_GENERATOR: str = "diesel_generator"

# Diesel generators:
#   Keyword used for parsing diesel-generator information.
DIESEL_GENERATORS: str = "diesel_generators"

# Diesel inputs file:
#   The relative path to the diesel-inputs file.
DIESEL_INPUTS_FILE: str = os.path.join("generation", "diesel_inputs.yaml")

# Diesel water heater:
#   Keyword used for parsing diesel-water-heater information.
DIESEL_WATER_HEATER: str = "diesel_water_heater"

# Diesel generators:
#   Keyword used for parsing diesel-generator information.
DIESEL_WATER_HEATERS: str = "diesel_water_heaters"

# Fast electric model file:
#   The relative path to the electric model file to use when running .
ELECTRIC_MODEL_FAST_FILE: str = os.path.join("src", "electric_tree.sav")

# Electric model file:
#   The relative path to the electric model file.
ELECTRIC_MODEL_FILE: str = os.path.join("src", "electric_forest.sav")

# Electric water heater:
#   Keyword used for parsing electric water-heater information.
ELECTRIC_WATER_HEATER: str = "electric_water_heater"

# Energy-system inputs file:
#   The relative path to the energy-system-inputs file.
ENERGY_SYSTEM_INPUTS_FILE: str = os.path.join("simulation", "energy_system.yaml")

# Exchangers:
#   Keyword used for parsing heat-exchanger information.
EXCHANGERS: str = "exchangers"

# Exchanger inputs file:
#   The relative path to the heat-exchanger-inputs file.
EXCHANGER_INPUTS_FILE: str = os.path.join("simulation", "heat_exchanger_inputs.yaml")

# Finance inputs file:
#   The relative path to the finance-inputs file.
FINANCE_INPUTS_FILE: str = os.path.join("impact", "finance_inputs.yaml")

# Generation inputs file:
#   The relative path to the generation-inputs file.
GENERATION_INPUTS_FILE: str = os.path.join("generation", "generation_inputs.yaml")

# GHG inputs file:
#   The relative path to the GHG inputs file.
GHG_INPUTS_FILE: str = os.path.join("impact", "ghg_inputs.yaml")

# Grid inputs file:
#   The relative path to the grid-inputs file.
GRID_TIMES_FILE: str = os.path.join("generation", "grid_times.csv")

# Hot-water scenarios:
#   Keyword used for parsing hot-water scenarios.
HOT_WATER_SCENARIOS: str = "hot_water_scenarios"

# Hot-water scenario inputs file:
#   The relative path to the hot-water scenario inputs file.
HOT_WATER_SCENARIO_INPUTS_FILE: str = os.path.join(
    "scenario", "hot_water_scenario.yaml"
)

# Inputs directory:
#   The directory containing user inputs.
INPUTS_DIRECTORY: str = "inputs"

# Kerosene filepath:
#   The path to the kerosene information file which needs to be provided for CLOVER.
KEROSENE_TIMES_FILE: str = os.path.join(
    LOAD_INPUTS_DIRECTORY, "device_utilisation", "kerosene_times.csv"
)

# Kerosene utilisation filepath:
#   The path to the kerosene utilisation profile.
KEROSENE_USAGE_FILE: str = os.path.join(
    LOAD_INPUTS_DIRECTORY, "device_usage", "kerosene_in_use.csv"
)

# Location inputs file:
#   The relative path to the location inputs file.
LOCATION_INPUTS_FILE: str = os.path.join("location_data", "location_inputs.yaml")

# Optimisation inputs file:
#   The relative path to the optimisation-input information file.
OPTIMISATION_INPUTS_FILE: str = os.path.join("optimisation", "optimisation_inputs.yaml")

# Optimisations:
#   Key used to extract the list of optimisations from the input file.
OPTIMISATIONS: str = "optimisations"

# Scenarios:
#   Keyword used for parsing scenario information.
SCENARIOS: str = "scenarios"

# Scenario inputs file:
#   The relative path to the scenario inputs file.
SCENARIO_INPUTS_FILE: str = os.path.join("scenario", "scenario_inputs.yaml")

# Simulation inputs file:
#   The relative path to the simulation inputs file.
SIMULATIONS_INPUTS_FILE: str = os.path.join("simulation", "simulations.yaml")

# Solar inputs file:
#   The relative path to the solar inputs file.
SOLAR_INPUTS_FILE: str = os.path.join("generation", "solar_generation_inputs.yaml")

# Tank inputs file:
#   The relative path to the tank inputs file.
TANK_INPUTS_FILE: str = os.path.join("simulation", "tank_inputs.yaml")

# Fast thermal model file:
#   The relative path to the thermal model file.
THERMAL_MODEL_FAST_FILE: str = os.path.join("src", "thermal_tree.sav")

# Thermal model file:
#   The relative path to the thermal model file.
THERMAL_MODEL_FILE: str = os.path.join("src", "thermal_forest.sav")

# Transmission inputs file:
#   The relative path to the transmission inputs file.
TRANSMISSION_INPUTS_FILE: str = os.path.join("simulation", "transmission_inputs.yaml")

# Transmitters:
#   Keyword used to parse transmitter information.
TRANSMITTERS: str = "transmitters"

# Water pump:
#   Keyword used to parse water-pump information.
WATER_PUMP: str = "water_pump"

# Water source availability template filename:
#   A template filename for parsing water-source availability profiles.
WATER_SOURCE_AVAILABILTY_TEMPLATE_FILENAME: str = "{water_source}_times.csv"

# Water source inputs file:
#   The relative path to the water-source inputs file.
WATER_SOURCE_INPUTS_FILE: str = os.path.join("generation", "water_source_inputs.yaml")


def _parse_battery_inputs(
    energy_system_inputs: Dict[str, Any],
    inputs_directory_relative_path: str,
    logger: Logger,
    scenarios: List[Scenario],
) -> Tuple[
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    List[Dict[str, Any]],
    str,
]:
    """
    Parses the battery inputs file.

    Inputs:
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenarios:
            The `list` of :class:`Scenario` instances available for the run.

    Outputs:
        A `tuple` containing:
        - The battery cost information;
        - The battery emissions information;
        - The raw battery input information;
        - The battery inputs filepath.

    """

    # Parse the battery inputs file.
    battery_inputs_filepath = os.path.join(
        inputs_directory_relative_path, BATTERY_INPUTS_FILE
    )
    battery_inputs = read_yaml(battery_inputs_filepath, logger)
    if not isinstance(battery_inputs, list):
        raise InputFileError(
            "battery inputs", "Battery input file is not of type `list`."
        )
    logger.info("Battery inputs successfully parsed.")

    # Determine the costs and emissions.
    if any(scenario.battery for scenario in scenarios):
        logger.info("Parsing battery impact information.")
        try:
            battery_costs: Optional[Dict[str, float]] = [
                entry[COSTS]
                for entry in battery_inputs
                if entry[NAME] == energy_system_inputs[BATTERY]
            ][0]
        except (KeyError, IndexError):
            logger.error("Failed to determine battery cost information.")
            raise
        logger.info("Battery cost information successfully parsed.")

        try:
            battery_emissions: Optional[Dict[str, float]] = [
                entry[EMISSIONS]
                for entry in battery_inputs
                if entry[NAME] == energy_system_inputs[BATTERY]
            ][0]
        except (KeyError, IndexError):
            logger.error("Failed to determine battery emission information.")
            raise
        logger.info("Battery emission information successfully parsed.")
    else:
        battery_costs = None
        battery_emissions = None
        logger.info(
            "Battery disblaed in scenario file, skipping battery impact parsing."
        )

    return battery_costs, battery_emissions, battery_inputs, battery_inputs_filepath


def _parse_conventional_water_source_inputs(
    inputs_directory_relative_path: str,
    logger: Logger,
) -> Tuple[List[Dict[str, Any]], str, Set[WaterSource]]:
    """
    Parses the device inputs file.

    Inputs:
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.

    Outputs:
        - The raw water-source inputs information extracted from the input YAML file.
        - The relative path to the conventional-water-source inputs file;
        - A `set` of :class:`conversion.conversion.WaterSource` instances based on the
          input information provided.

    """

    water_source_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        WATER_SOURCE_INPUTS_FILE,
    )
    water_source_inputs = read_yaml(
        water_source_inputs_filepath,
        logger,
    )
    if not isinstance(water_source_inputs, list):
        logger.error(
            "%sWater source inputs information must be of type `list`.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "water source inputs", "Water source input information of the wrong type."
        )
    water_sources: Set[WaterSource] = {
        WaterSource.from_dict(entry, logger) for entry in water_source_inputs
    }

    return water_source_inputs, water_source_inputs_filepath, water_sources


def _parse_conversion_inputs(
    inputs_directory_relative_path: str,
    logger: Logger,
) -> Tuple[
    str,
    Dict[Converter, Dict[str, float]],
    Dict[Converter, Dict[str, float]],
    Dict[str, Converter],
]:
    """
    Parses the conversion inputs file.

    Inputs:
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.

    Outputs:
        - conversion_inputs_filepath:
            The conversion inputs relative path;
        - converter_costs:
            A `dict` mapping :class:`conversion.Converter` instances to their associated
            costs.
        - converter_emissions:
            A `dict` mapping :class:`conversion.Converter` instances to their associated
            emissions.
        - converters:
            A `dict` mapping converter names (`str`) to :class:`conversion.Converter`
            instances based on the input information provided.

    """

    # Determine the conversion inputs file path.
    conversion_file_relative_path = os.path.join(
        inputs_directory_relative_path, CONVERSION_INPUTS_FILE
    )

    converter_costs: Dict[Converter, Dict[str, float]] = {}
    converter_emissions: Dict[Converter, Dict[str, float]] = {}

    # If the file exists, parse the converters contained.
    if os.path.isfile(conversion_file_relative_path):
        parsed_converters: List[Converter] = []
        conversion_inputs: List[Dict[str, Any]] = read_yaml(  # type: ignore
            conversion_file_relative_path, logger
        )
        if conversion_inputs is not None:
            if not isinstance(conversion_inputs, list):
                logger.error(
                    "%sThe conversion inputs file must be a `list` of valid converters.%s",
                    BColours.fail,
                    BColours.endc,
                )
            if len(conversion_inputs) > 0:
                for entry in conversion_inputs:
                    if not isinstance(entry, dict):
                        logger.error(
                            "%sConverter not of correct format `dict`: %s%s",
                            BColours.fail,
                            str(entry),
                            BColours.endc,
                        )
                        raise InputFileError(
                            "conversion inputs", "Converters not correctly defined."
                        )

                    # Attempt to parse as a water source.
                    try:
                        parsed_converters.append(WaterSource.from_dict(entry, logger))
                    except InputFileError:
                        logger.info(
                            "Failed to create a single-input converter, trying a thermal "
                            "desalination plant."
                        )

                        # Attempt to parse as a thermal desalination plant.
                        try:
                            parsed_converters.append(
                                ThermalDesalinationPlant.from_dict(entry, logger)
                            )
                        except KeyError:
                            logger.info(
                                "Failed to create a thermal desalination plant, trying "
                                "a multi-input converter."
                            )

                            # Parse as a generic multi-input converter.
                            parsed_converters.append(
                                MultiInputConverter.from_dict(entry, logger)
                            )
                            logger.info("Parsed multi-input converter from input data.")
                        logger.info(
                            "Parsed thermal desalination plant from input data."
                        )

                    else:
                        logger.info("Parsed single-input converter from input data.")

                # Convert the list to the required format.
                converters: Dict[str, Converter] = {
                    converter.name: converter for converter in parsed_converters
                }

                # Parse the transmission impact information.
                for converter in converters.values():
                    try:
                        converter_costs[converter] = [
                            entry[COSTS]
                            for entry in conversion_inputs
                            if entry[NAME] == converter.name
                        ][0]
                    except (KeyError, IndexError):
                        logger.error(
                            "Failed to determine converter cost information for %s.",
                            converter.name,
                        )
                        raise
                    logger.info(
                        "Converter cost information for %s successfully parsed.",
                        converter.name,
                    )
                    try:
                        converter_emissions[converter] = [
                            entry[EMISSIONS]
                            for entry in conversion_inputs
                            if entry[NAME] == converter.name
                        ][0]
                    except (KeyError, IndexError):
                        logger.error(
                            "Failed to determine converter emission information for %s.",
                            converter.name,
                        )
                        raise
                    logger.info(
                        "Converter emission information for %s successfully parsed.",
                        converter.name,
                    )

            else:
                converters = {}
                logger.info(
                    "Conversion file empty, continuing with no defined converters."
                )

    else:
        converters = {}
        logger.info("No conversion file, skipping converter parsing.")

    return (
        conversion_file_relative_path,
        converter_costs,
        converter_emissions,
        converters,
    )


def _parse_diesel_inputs(  # pylint: disable=too-many-statements
    energy_system_inputs: Dict[str, Any],
    inputs_directory_relative_path: str,
    logger: Logger,
    scenarios: List[Scenario],
) -> Tuple[
    Dict[str, float],
    Dict[str, float],
    DieselGenerator,
    str,
    Optional[DieselWaterHeater],
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
]:
    """
    Parses the diesel inputs file.

    Inputs:
        - energy_system_inputs:
            The un-processed energy-system input information.
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenarios:
            The `list` of :class:`Scenario` instances available for the run.

    Outputs:
        A `tuple` containing:
        - The path to the diesel inputs file;
        - The diesel-generator cost information;
        - The diesel-generator emissions information;
        - The diesel generator to use for the run;
        - The diesel water heater to use for the run, if applicable;
        - The diesel water heater emissions information, if applicable;
        - The diesel water heater to use for the run, if applicable.

    """

    # Parse the diesel inputs file.
    diesel_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        DIESEL_INPUTS_FILE,
    )
    diesel_inputs = read_yaml(
        diesel_inputs_filepath,
        logger,
    )

    if not isinstance(diesel_inputs, dict):
        raise InputFileError("diesel inputs", "Diesel inputs are not of type `dict`.")

    # Instantiate DieselGenerators for every entry in the input file.
    try:
        diesel_generators: List[DieselGenerator] = [
            DieselGenerator(entry[DIESEL_CONSUMPTION], entry[MINIMUM_LOAD], entry[NAME])
            for entry in diesel_inputs[DIESEL_GENERATORS]
        ]
    except KeyError as e:
        logger.error(
            "%sMissing information in diesel inputs file: %s%s",
            BColours.fail,
            str(e),
            BColours.endc,
        )
        raise
    logger.info("Diesel inputs successfully parsed.")

    # Determine the diesel generator being modelled.
    if DIESEL_GENERATOR in energy_system_inputs:
        try:
            diesel_generator = [
                generator
                for generator in diesel_generators
                if generator.name == energy_system_inputs[DIESEL_GENERATOR]
            ][0]
        except IndexError:
            logger.error(
                "%sNo matching diesel generator information for generator %s found in "
                "diesel inputs file.%s",
                BColours.fail,
                energy_system_inputs[DIESEL_GENERATOR],
                BColours.endc,
            )
            raise InputFileError(
                "energy system inputs",
                f"Diesel generator '{energy_system_inputs[DIESEL_GENERATOR]}' not "
                + "found in diesel inputs.",
            ) from None
    else:
        logger.error(
            "%sDiesel generator must be specified in the energy system inputs file.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "energy system inputs",
            f"No diesel generator was specified. Use the {DIESEL_GENERATOR} keyword to "
            + "select a valid diesel generator.",
        )

    # Determine the diesel costs.
    try:
        diesel_costs = [
            entry[COSTS]
            for entry in diesel_inputs[DIESEL_GENERATORS]
            if entry[NAME] == diesel_generator.name
        ][0]
    except (KeyError, IndexError):
        logger.error("Failed to determine diesel cost information.")
        raise
    logger.info("Diesel cost information successfully parsed.")

    # Determine the diesel emissions.
    try:
        diesel_emissions = [
            entry[EMISSIONS]
            for entry in diesel_inputs[DIESEL_GENERATORS]
            if entry[NAME] == diesel_generator.name
        ][0]
    except (KeyError, IndexError):
        logger.error("Failed to determine diesel emission information.")
        raise
    logger.info("Diesel emission information successfully parsed.")

    # Instantiate diesel water heaters for every entry in the input file.
    if DIESEL_WATER_HEATERS in diesel_inputs:
        try:
            diesel_water_heaters: List[DieselWaterHeater] = [
                DieselWaterHeater.from_dict(entry, logger)
                for entry in diesel_inputs[DIESEL_WATER_HEATERS]
            ]
        except KeyError as e:
            logger.error(
                "%sMissing information in diesel inputs file: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise
        logger.info("Diesel water-heater inputs successfully parsed.")
    else:
        diesel_water_heaters = []
        logger.info(
            "No diesel water heaters defined in the diesel inputs file, continuing."
        )

    # Determine the diesel generator being modelled.
    if DIESEL_WATER_HEATER in energy_system_inputs:
        try:
            diesel_water_heater: Optional[DieselWaterHeater] = [
                heater
                for heater in diesel_water_heaters
                if heater.name == energy_system_inputs[DIESEL_WATER_HEATER]
            ][0]
        except IndexError:
            logger.error(
                "%sNo matching diesel water-heater information for generator %s found "
                "in diesel inputs file.%s",
                BColours.fail,
                energy_system_inputs[DIESEL_WATER_HEATER],
                BColours.endc,
            )
            raise InputFileError(
                "energy system inputs",
                f"Diesel water heater '{energy_system_inputs[DIESEL_WATER_HEATER]}' "
                + "not found in diesel inputs.",
            ) from None

        if diesel_water_heater is None:
            logger.error(
                "%sParsed diesel water heater information does not correspond to valid "
                "diesel water heater instances.%s"
            )
            raise InputFileError(
                "diesel inputs",
                "Diesel water heater information parsed failed to successfully create "
                "valid diesel water heater instances.",
            )

        # Determine the diesel costs.
        try:
            diesel_water_heater_costs: Optional[Dict[str, float]] = [
                entry[COSTS]
                for entry in diesel_inputs[DIESEL_WATER_HEATERS]
                if entry[NAME] == diesel_water_heater.name
            ][0]
        except (KeyError, IndexError):
            logger.error(
                "%sFailed to determine diesel water-heater cost information.%s",
                BColours.fail,
                BColours.endc,
            )
            raise
        logger.info("Diesel water-heater cost information successfully parsed.")

        # Determine the diesel emissions.
        try:
            diesel_water_heater_emissions: Optional[Dict[str, float]] = [
                entry[EMISSIONS]
                for entry in diesel_inputs[DIESEL_WATER_HEATERS]
                if entry[NAME] == diesel_water_heater.name
            ][0]
        except (KeyError, IndexError):
            logger.error(
                "%sFailed to determine diesel water-heater emission information.%s",
                BColours.fail,
                BColours.endc,
            )
            raise
        logger.info("Diesel water-heater emission information successfully parsed.")

    elif any(scenario.hot_water_scenario is not None for scenario in scenarios) and any(
        scenario.hot_water_scenario.auxiliary_heater == AuxiliaryHeaterType.DIESEL  # type: ignore
        for scenario in [
            scenario
            for scenario in scenarios
            if scenario.hot_water_scenario is not None
        ]
    ):
        logger.error(
            "%sDiesel water heater must be specified in the energy system inputs file "
            "if any hot-water scenarios states that a diesel water heater is present."
            "%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "energy system inputs",
            "No diesel water heater was specified despite being required by a scenario "
            f"defined within the scenario inputs. Use the {DIESEL_WATER_HEATER} "
            + "keyword to select a valid diesel generator.",
        )

    else:
        diesel_water_heater = None
        diesel_water_heater_costs = None
        diesel_water_heater_emissions = None

    return (
        diesel_costs,
        diesel_emissions,
        diesel_generator,
        diesel_inputs_filepath,
        diesel_water_heater,
        diesel_water_heater_costs,
        diesel_water_heater_emissions,
    )


def _parse_device_inputs(
    inputs_directory_relative_path: str,
    logger: Logger,
) -> Tuple[str, Set[load.load.Device]]:
    """
    Parses the device inputs file.

    Inputs:
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.

    Outputs:
        - The relative path to the deivce inputs file;
        - A `set` of :class:`load.load.Device` instances based on the input information
          provided.

    """

    device_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        DEVICE_INPUTS_FILE,
    )
    device_inputs = read_yaml(
        device_inputs_filepath,
        logger,
    )
    if not isinstance(device_inputs, list):
        logger.error(
            "%sDevice input information was not of type `list`. The devices file must "
            "specify a list of valid devices.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "device inputs", "The device inputs file must contain a list of devices."
        )

    devices: Set[load.load.Device] = {
        load.load.Device.from_dict(entry) for entry in device_inputs
    }

    # Ensure that a kerosene device is correctly defined and instantiated.
    if KEROSENE_DEVICE_NAME not in {device.name for device in devices}:
        logger.info(
            "%sNo kerosene device information provided in the device file. "
            "Auto-generating device information.%s",
            BColours.warning,
            BColours.endc,
        )
        devices.add(load.load.DEFAULT_KEROSENE_DEVICE)
        logger.info("Default kerosene device added.")
    else:
        logger.info("Kerosene device information found, using in-file information.")

    return device_inputs_filepath, devices


def _parse_exchanger_inputs(
    energy_system_inputs: Dict[str, Any],
    inputs_directory_relative_path: str,
    logger: Logger,
    scenarios: List[Scenario],
) -> Tuple[
    Optional[Dict[str, float]], Optional[Dict[str, float]], List[Dict[str, float]], str
]:
    """
    Parses the exchanger inputs file.

    Inputs:
        - energy_system_inputs:
            The energy-system input information.
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenarios:
            The `list` of :class:`Scenario` instances available for the run.

    Outputs:
        A `tuple` containing:
        - The exchanger cost information;
        - The exchanger emissions information;
        - The raw exchanger input information;
        - The exchanger inputs filepath.

    """

    # Parse the exchanger inputs file.
    exchanger_inputs_filepath = os.path.join(
        inputs_directory_relative_path, EXCHANGER_INPUTS_FILE
    )
    exchanger_inputs = read_yaml(exchanger_inputs_filepath, logger)
    if not isinstance(exchanger_inputs, dict):
        raise InputFileError(
            "exchanger inputs", "Exchanger input file is not of type `dict`."
        )
    logger.info("Exchanger inputs successfully parsed.")

    # Determine the costs and emissions.
    if (
        any(scenario.desalination_scenario is not None for scenario in scenarios)
        and any(
            scenario.desalination_scenario.pvt_scenario.heats == HTFMode.CLOSED_HTF  # type: ignore
            for scenario in [
                scenario
                for scenario in scenarios
                if scenario.desalination_scenario is not None
            ]
        )
    ) or any(scenario.hot_water_scenario is not None for scenario in scenarios):
        logger.info("Parsing exchanger impact information.")
        try:
            exchanger_costs = [
                entry[COSTS]
                for entry in exchanger_inputs[EXCHANGERS]
                if entry[NAME] == energy_system_inputs[EXCHANGER]
            ][0]
        except (KeyError, IndexError):
            logger.error("Failed to determine exchanger cost information.")
            raise
        logger.info("Exchanger cost information successfully parsed.")
        try:
            exchanger_emissions = [
                entry[EMISSIONS]
                for entry in exchanger_inputs[EXCHANGERS]
                if entry[NAME] == energy_system_inputs[EXCHANGER]
            ][0]
        except (KeyError, IndexError):
            logger.error("Failed to determine exchanger emission information.")
            raise
        logger.info("Exchanger emission information successfully parsed.")
    else:
        logger.info(
            "Exchanger disblaed in scenario file, skipping battery impact parsing."
        )
        exchanger_costs = None
        exchanger_emissions = None

    return (
        exchanger_costs,
        exchanger_emissions,
        exchanger_inputs[EXCHANGERS],
        exchanger_inputs_filepath,
    )


def _parse_pvt_reduced_models(  # pylint: disable=too-many-statements
    debug: bool, logger: Logger, scenarios: List[Scenario]
) -> Tuple[Any, Any]:
    """
    Parses the PV-T models from the installed package or raw files.

    Inputs:
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenarios:
            The `list` of :class:`Scenario` instances available for the run.

    Outputs:
        - A `list` of :class:`DieselGenerator` instances based on the input information
          provided.

    """

    # If any of the scenarios defined specify that PV-T should be used.
    if any(scenario.pv_t for scenario in scenarios):
        # Attempt to read the thermal model file as per CLOVER being an installed
        # package.
        logger.info(
            "Attempting to read PV-T reduced thermal model from installed package info."
        )
        try:
            thermal_model: Optional[Any] = pickle.load(
                pkgutil.get_data(PACKAGE_NAME, THERMAL_MODEL_FILE)  # type: ignore
            )
        except (AttributeError, FileNotFoundError, TypeError):
            logger.info("Failed to read data as if package was installed.")

            # Attempt to read the thermal model file from raw source information.
            logger.info(
                "Attempting to read PV-T reduced thermal model from raw source file."
            )
            if debug:
                try:
                    with open(
                        os.path.join(RAW_CLOVER_PATH, THERMAL_MODEL_FAST_FILE), "rb"
                    ) as f:
                        thermal_model = pickle.load(f)
                except Exception:
                    logger.error(
                        "Failed to read fast PV-T reduced thermal model from raw source."
                    )
                    logger.critical("Failed to determine PV-T reduced thermal model.")
                    raise

            else:
                try:
                    with open(
                        os.path.join(RAW_CLOVER_PATH, THERMAL_MODEL_FILE), "rb"
                    ) as f:
                        thermal_model = pickle.load(f)
                except Exception:
                    logger.error(
                        "Failed to read PV-T reduced thermal model from raw source."
                    )
                    logger.critical("Failed to determine PV-T reduced thermal model.")
                    raise
            logger.info(
                "Successfully read PV-T reduced thermal model from local source."
            )

        else:
            logger.info(
                "Successfully read PV-T reduced thermal model from installed package "
                "file."
            )

        logger.info("PV-T reduced thermal model file successfully read.")

        # Read the electric model.
        logger.info(
            "Attempting to read PV-T reduced electric model from installed package info."
        )
        try:
            # Attempt to read the electric model file as per CLOVER being an installed
            # package.
            electric_model: Optional[Any] = pickle.load(
                pkgutil.get_data(PACKAGE_NAME, ELECTRIC_MODEL_FILE)  # type: ignore
            )
        except (AttributeError, FileNotFoundError, TypeError):
            logger.info("Failed to read data as if package was installed.")

            # Attempt to read the electric model from raw source information.
            logger.info(
                "Attempting to read PV-T reduced electric model from raw source file."
            )
            if debug:
                try:
                    with open(
                        os.path.join(RAW_CLOVER_PATH, ELECTRIC_MODEL_FAST_FILE), "rb"
                    ) as f:
                        electric_model = pickle.load(f)
                except Exception:
                    logger.error(
                        "Failed to read fast PV-T reduced electric model from raw "
                        "source."
                    )
                    logger.critical("Failed to determine PV-T reduced electric model.")
                    raise
            else:
                try:
                    with open(
                        os.path.join(RAW_CLOVER_PATH, ELECTRIC_MODEL_FILE), "rb"
                    ) as f:
                        electric_model = pickle.load(f)
                except Exception:
                    logger.error(
                        "Failed to read PV-T reduced electric model from raw source."
                    )
                    logger.critical("Failed to determine PV-T reduced electric model.")
                    raise

            logger.info(
                "Successfully read PV-T reduced electric model from local source."
            )

        else:
            logger.info(
                "Successfully read PV-T reduced electric model from installed package file."
            )

        logger.info("PV-T reduced electric model file successfully read.")

    # If there is no PV-T being used in the system, do not attempt to read the files.
    else:
        thermal_model = None
        electric_model = None

    return electric_model, thermal_model


def parse_scenario_inputs(
    inputs_directory_relative_path: str,
    logger: Logger,
) -> Tuple[str, str, List[Scenario], str]:
    """
    Parses the scenario input files.

    Inputs:
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.

    Outputs:
        - The desalination inputs filepath;
        - The hot-water inputs filepath;
        - The :class:`Scenario` to use for the run;
        - The scenario inputs filepath.

    """

    desalination_scenario_inputs_filepath: str = os.path.join(
        inputs_directory_relative_path,
        DESALINATION_SCENARIO_INPUTS_FILE,
    )
    hot_water_scenario_inputs_filepath: str = os.path.join(
        inputs_directory_relative_path, HOT_WATER_SCENARIO_INPUTS_FILE
    )

    # Parse the desalination scenario inputs information if relevant.
    if os.path.isfile(desalination_scenario_inputs_filepath):
        logger.info("Parsing desalination inputs file.")
        desalination_scenario_inputs = read_yaml(
            desalination_scenario_inputs_filepath,
            logger,
        )
        if not isinstance(desalination_scenario_inputs, dict):
            raise InputFileError(
                "scenario inputs", "Desalination scenario inputs is not of type `dict`."
            )
        try:
            desalination_scenarios: Optional[List[DesalinationScenario]] = [
                DesalinationScenario.from_dict(entry, logger)
                for entry in desalination_scenario_inputs[DESALINATION_SCENARIOS]
            ]
        except Exception as e:
            logger.error(
                "%sError generating deslination scenario from inputs file: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise
        logger.info("Desalination scenarios successfully parsed.")
    else:
        desalination_scenarios = None
        logger.info("No desalination scenarios files provided, skipping.")

    # Parse the hot-water scenario inputs information if relevant.
    if os.path.isfile(hot_water_scenario_inputs_filepath):
        logger.info("Parsing hot-water inputs file.")
        hot_water_scenario_inputs = read_yaml(
            hot_water_scenario_inputs_filepath,
            logger,
        )
        if not isinstance(hot_water_scenario_inputs, dict):
            raise InputFileError(
                "hot-water inputs", "Hot-water scenario inputs is not of type `dict`."
            )
        try:
            hot_water_scenarios: Optional[List[HotWaterScenario]] = [
                HotWaterScenario.from_dict(entry, logger)
                for entry in hot_water_scenario_inputs[HOT_WATER_SCENARIOS]
            ]
        except Exception as e:
            logger.error(
                "%sError generating hot-water scenarios from inputs file: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise
        logger.info("Hot-water scenarios successfully parsed.")
    else:
        hot_water_scenarios = None
        logger.info("No hot-water scenario file provided, skipping.")

    # Parse the scenario input information.
    scenario_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        SCENARIO_INPUTS_FILE,
    )
    scenario_inputs = read_yaml(
        scenario_inputs_filepath,
        logger,
    )
    if not isinstance(scenario_inputs, dict):
        raise InputFileError(
            "scenario inputs", "Scenario inputs is not of type `dict`."
        )

    try:
        scenarios: List[Scenario] = [
            Scenario.from_dict(
                desalination_scenarios, hot_water_scenarios, logger, entry
            )
            for entry in scenario_inputs[SCENARIOS]
        ]
    except Exception as e:
        logger.error(
            "%sError generating scenario from inputs file: %s%s",
            BColours.fail,
            str(e),
            BColours.endc,
        )
        raise

    for scenario in scenarios:
        # The system should ignore the desalination scenario if there is no clean-water to
        # consider.
        if ResourceType.CLEAN_WATER not in scenario.resource_types:
            scenario.desalination_scenario = None
        # If there is clean water to consider, but the scenario is not defined, then raise.
        elif scenario.desalination_scenario is None:
            logger.error(
                "%sClean-water is specified in the scenario file but no desalination "
                "scenario was defined. For help creating this file, consult the user guide "
                "or run the update-location script on your location.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "desalination scenario",
                "No desalination scenario file was defined for the location despite clean "
                "water being selected as a resource type to model.",
            )

        # The system should igrnore the hot-water scenario if there is no hot-water to
        # consider.
        if ResourceType.HOT_CLEAN_WATER not in scenario.resource_types:
            scenario.hot_water_scenario = None
        # If there is hot water to consider, but the scenario is not defined, then raise.
        elif scenario.hot_water_scenario is None:
            logger.error(
                "%sHot-water is specified in the scenario file but no hot-water scenario "
                "was defined. For help creating this file, consult the user guide or run "
                "the update-location script on your location.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "hot-water scenario",
                "No hot-water scenario file was defined for the location despite hot water "
                "being selected as a resource type to model.",
            )

    return (
        desalination_scenario_inputs_filepath,
        hot_water_scenario_inputs_filepath,
        scenarios,
        scenario_inputs_filepath,
    )


def _parse_solar_inputs(  # pylint: disable=too-many-locals, too-many-statements
    debug: bool,
    energy_system_inputs: Dict[str, Any],
    inputs_directory_relative_path: str,
    logger: Logger,
    scenarios: List[Scenario],
) -> Tuple[
    solar.PVPanel,
    Dict[str, float],
    Dict[str, float],
    Optional[solar.HybridPVTPanel],
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    str,
]:
    """
    Parses the solar inputs file.

    Inputs:
        - debug:
            Whether to use the PV-T reduced models (False) or invented data for
            debugging purposes (True).
        - energy_system_inputs:
            The un-processed energy-system input information.
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenarios:
            The `list` of :class:`Scenario` instances available for the run.

    Outputs:
        A `tuple` containing:
        - The :class:`solar.PVPanel` being used for the run;
        - The pv-panel cost information;
        - The pv-panel emissions information;
        - The :class:`HybridPVTPanel` being used for the run, if relevant;
        - The pv-t-panel cost information, if relevant;
        - The pv-t-panel emissions information, if relevant;
        - The relative path to the solar generation inputs filepath.

    """

    # Parse the solar input information.
    solar_generation_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        SOLAR_INPUTS_FILE,
    )
    solar_generation_inputs = read_yaml(
        solar_generation_inputs_filepath,
        logger,
    )
    if not isinstance(solar_generation_inputs, dict):
        raise InputFileError(
            "solar generation inputs", "Solar generation inputs are not of type `dict`."
        )
    logger.info("Solar generation inputs successfully parsed.")

    # Parse the PV-panel information.
    solar_panels: List[solar.SolarPanel] = []
    for panel_input in solar_generation_inputs["panels"]:
        if panel_input["type"] == solar.SolarPanelType.PV.value:
            solar_panels.append(solar.PVPanel.from_dict(logger, panel_input))

    # Parse the PV-T models if relevant for the code flow.
    electric_model, thermal_model = _parse_pvt_reduced_models(debug, logger, scenarios)

    # Parse the PV-T panel information
    for panel_input in solar_generation_inputs["panels"]:
        if panel_input["type"] == solar.SolarPanelType.PV_T.value:
            solar_panels.append(
                solar.HybridPVTPanel(
                    electric_model,
                    logger,
                    panel_input,
                    solar_panels,
                    thermal_model,
                )
            )

    # Determine the PV panel being modelled.
    try:
        pv_panel: Union[solar.PVPanel, solar.SolarPanel] = [
            panel
            for panel in solar_panels
            if panel.panel_type == solar.SolarPanelType.PV  # type: ignore
            and panel.name == energy_system_inputs["pv_panel"]
        ][0]
    except IndexError:
        logger.error(
            "%sPV panel %s not found in pv panel inputs.%s",
            BColours.fail,
            energy_system_inputs["pv_panel"],
            BColours.endc,
        )
        raise

    if not isinstance(pv_panel, solar.PVPanel):
        logger.error(
            "%sThe PV panel selected is not a valid PV panel.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "solar inputs OR energy system inputs",
            "The PV panel selected is not a valid PV panel.",
        )

    # Determine the PV panel costs.
    try:
        pv_panel_costs: Dict[str, float] = [
            panel_data[COSTS]
            for panel_data in solar_generation_inputs["panels"]
            if panel_data[NAME] == pv_panel.name
        ][0]
    except (KeyError, IndexError):
        logger.error(
            "%sFailed to determine costs for PV panel %s.%s",
            BColours.fail,
            energy_system_inputs["pv_panel"],
            BColours.endc,
        )
        raise
    logger.info("PV panel costs successfully determined.")

    # Determine the PV panel emissions.
    try:
        pv_panel_emissions: Dict[str, float] = [
            panel_data[EMISSIONS]
            for panel_data in solar_generation_inputs["panels"]
            if panel_data[NAME] == pv_panel.name
        ][0]
    except (KeyError, IndexError):
        logger.error(
            "%sFailed to determine emissions for PV panel %s.%s",
            BColours.fail,
            energy_system_inputs["pv_panel"],
            BColours.endc,
        )
        raise
    logger.info("PV panel emissions successfully determined.")

    # Determine the PVT panel being modelled, if appropriate.
    if "pvt_panel" in energy_system_inputs:
        try:
            pvt_panel: Optional[Union[solar.HybridPVTPanel, solar.SolarPanel]] = [
                panel
                for panel in solar_panels
                if panel.panel_type == solar.SolarPanelType.PV_T  # type: ignore
                and panel.name == energy_system_inputs["pvt_panel"]
            ][0]
            logger.info("PV-T panel successfully determined.")
        except IndexError:
            logger.error(
                "%sPV-T panel %s not found in pv panel inputs.%s",
                BColours.fail,
                energy_system_inputs["pvt_panel"],
                BColours.endc,
            )
            raise

        if pvt_panel is None:
            logger.error(
                "%sThe PV-T panel selected caused an internal error when determining "
                "the relevant panel data.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "The PV-T panel selected was found but the information concerning it "
                "was not successfully parsed."
            )
        if not isinstance(pvt_panel, solar.HybridPVTPanel):
            logger.error(
                "%sThe PV-T panel selected %s is not a valid PV-T panel.%s",
                BColours.fail,
                energy_system_inputs["pv_panel"],
                BColours.endc,
            )
            raise InputFileError(
                "solar inputs OR energy system inputs",
                "The PV-T panel selected is not a valid HybridPVTPanel.",
            )

        logger.info("PV-T panel successfully parsed: %s.", pvt_panel.name)

        try:
            pvt_panel_costs: Optional[Dict[str, float]] = [
                panel_data[COSTS]
                for panel_data in solar_generation_inputs["panels"]
                if panel_data[NAME] == pvt_panel.name
            ][0]
        except (KeyError, IndexError):
            logger.error(
                "%sFailed to determine costs for PV-T panel %s.%s",
                BColours.fail,
                energy_system_inputs["pvt_panel"],
                BColours.endc,
            )
            raise
        logger.info("PV-T panel costs successfully determined.")
        try:
            pvt_panel_emissions: Optional[Dict[str, float]] = [
                panel_data[EMISSIONS]
                for panel_data in solar_generation_inputs["panels"]
                if panel_data[NAME] == pvt_panel.name
            ][0]
        except (KeyError, IndexError):
            logger.error(
                "%sFailed to determine emissions for PV-T panel %s.%s",
                BColours.fail,
                energy_system_inputs["pvt_panel"],
                BColours.endc,
            )
            raise
        logger.info("PV-T panel emissions successfully determined.")
    else:
        pvt_panel = None
        pvt_panel_costs = None
        pvt_panel_emissions = None

    return (
        pv_panel,
        pv_panel_costs,
        pv_panel_emissions,
        pvt_panel,
        pvt_panel_costs,
        pvt_panel_emissions,
        solar_generation_inputs_filepath,
    )


def _parse_tank_inputs(  # pylint: disable=too-many-statements
    energy_system_inputs: Dict[str, Any],
    inputs_directory_relative_path: str,
    logger: Logger,
    scenarios: List[Scenario],
) -> Tuple[
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    List[Dict[str, Any]],
    str,
]:
    """
    Parses the tank inputs file.

    Inputs:
        - energy_system_inputs:
            The un-processed energy-system input information.
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenarios:
            The `list` of :class:`Scenario` instances available for the run.

    Outputs:
        A `tuple` containing:
        - The buffer-water-tank cost information;
        - The buffer-water-tank emissions information;
        - The clean-water-tank cost information;
        - The clean-water-tank emissions information;
        - The hot-water tank cost information;
        - The hot-water tank emissions information;
        - The raw tank inputs information;
        - The tank inputs filepath.

    """

    # Parse the tank input information.
    tank_inputs_filepath = os.path.join(
        inputs_directory_relative_path, TANK_INPUTS_FILE
    )
    tank_inputs = read_yaml(tank_inputs_filepath, logger)
    if not isinstance(tank_inputs, list):
        raise InputFileError("tank inputs", "Tank inputs file is not of type `list`.")

    # If clean-water is present, extract the cost and emissions information.
    if any(scenario.desalination_scenario is not None for scenario in scenarios):
        logger.info("Parsing clean-water tank impact information.")
        # Parse the clean-water tank costs information.
        try:
            clean_water_tank_costs: Optional[Dict[str, float]] = [
                entry[COSTS]
                for entry in tank_inputs
                if entry[NAME]
                == energy_system_inputs[ImpactingComponent.CLEAN_WATER_TANK.value]
            ][0]
        except (KeyError, IndexError):
            logger.error(
                "Failed to determine clean-water tank cost information or failed to "
                "determine clean-water tank from the energy-system inputs file."
            )
            raise
        logger.info("Clean-water tank cost information successfully parsed.")

        # Parse the clean-water tank emissions information.
        try:
            clean_water_tank_emissions: Optional[Dict[str, float]] = [
                entry[EMISSIONS]
                for entry in tank_inputs
                if entry[NAME]
                == energy_system_inputs[ImpactingComponent.CLEAN_WATER_TANK.value]
            ][0]
        except IndexError:
            logger.error("Failed to determine clean-water tank emission information.")
            raise
        except KeyError:
            logger.error(
                "Failed to determine clean-water tank from the energy-system inputs "
                "file."
            )
            raise
        logger.info("Clean-water tank emission information successfully parsed.")

    else:
        clean_water_tank_costs = None
        clean_water_tank_emissions = None
        logger.info(
            "Clean-water tank disblaed in scenario file, skipping battery impact "
            "parsing."
        )

    # If clean-water is present, extract the cost and emissions information.
    if any(
        scenario.desalination_scenario is not None for scenario in scenarios  # type: ignore
    ) and any(
        scenario.desalination_scenario.pvt_scenario.heats == HTFMode.CLOSED_HTF  # type: ignore
        for scenario in [
            scenario
            for scenario in scenarios
            if scenario.desalination_scenario is not None
        ]
    ):
        logger.info("Parsing buffer-water tank impact information.")
        # Parse the buffer-water tank costs information.
        try:
            buffer_tank_costs: Optional[Dict[str, float]] = [
                entry[COSTS]
                for entry in tank_inputs
                if entry[NAME]
                == energy_system_inputs[ImpactingComponent.BUFFER_TANK.value]
            ][0]
        except IndexError:
            logger.error("Failed to determine buffer-water tank cost information.")
            raise
        except KeyError:
            logger.error(
                "Failed to determine buffer-water tank from the energy-system inputs file."
            )
            raise
        logger.info("HOt-water tank cost information successfully parsed.")

        # Parse the buffer-water tank emissions information.
        try:
            buffer_tank_emissions: Optional[Dict[str, float]] = [
                entry[EMISSIONS]
                for entry in tank_inputs
                if entry[NAME]
                == energy_system_inputs[ImpactingComponent.BUFFER_TANK.value]
            ][0]
        except IndexError:
            logger.error("Failed to determine buffer-water tank emission information.")
            raise
        except KeyError:
            logger.error(
                "Failed to determine buffer-water tank from the energy-system inputs "
                "file."
            )
            raise
        logger.info("Buffer-water tank emission information successfully parsed.")

    else:
        buffer_tank_costs = None
        buffer_tank_emissions = None
        logger.info(
            "Buffer-water tank disblaed in scenario file, skipping battery impact parsing."
        )

    if any(scenario.hot_water_scenario is not None for scenario in scenarios):
        logger.info("Parsing hot-water tank impact information.")
        # Parse the hot-water tank costs information.
        try:
            hot_water_tank_costs: Optional[Dict[str, float]] = [
                entry[COSTS]
                for entry in tank_inputs
                if entry[NAME]
                == energy_system_inputs[ImpactingComponent.HOT_WATER_TANK.value]
            ][0]
        except IndexError:
            logger.error("Failed to determine hot-water tank cost information.")
            raise
        except KeyError:
            logger.error(
                "Failed to determine hot-water tank from the energy-system inputs "
                "file."
            )
            raise
        logger.info("Hot-water tank cost information successfully parsed.")

        # Parse the hot-water tank emissions information.
        try:
            hot_water_tank_emissions: Optional[Dict[str, float]] = [
                entry[EMISSIONS]
                for entry in tank_inputs
                if entry[NAME]
                == energy_system_inputs[ImpactingComponent.HOT_WATER_TANK.value]
            ][0]
        except IndexError:
            logger.error("Failed to determine hot-water tank emission information.")
            raise
        except KeyError:
            logger.error(
                "Failed to determine hot-water tank from the energy-system inputs "
                "file."
            )
            raise
        logger.info("Hot-water tank emission information successfully parsed.")

    else:
        hot_water_tank_costs = None
        hot_water_tank_emissions = None
        logger.info(
            "Hot-water tank disblaed in scenario file, skipping battery impact parsing."
        )

    return (
        buffer_tank_costs,
        buffer_tank_emissions,
        clean_water_tank_costs,
        clean_water_tank_emissions,
        hot_water_tank_costs,
        hot_water_tank_emissions,
        tank_inputs,
        tank_inputs_filepath,
    )


def _parse_minigrid_inputs(  # pylint: disable=too-many-locals, too-many-statements
    converters: Dict[str, Converter],
    debug: bool,
    inputs_directory_relative_path: str,
    logger: Logger,
    scenarios: List[Scenario],
) -> Tuple[
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    str,
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    Dict[str, float],
    Dict[str, float],
    str,
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    str,
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    Optional[str],
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    Minigrid,
    Dict[str, float],
    Dict[str, float],
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    str,
    Optional[str],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    str,
    Dict[str, Transmitter],
]:
    """
    Parses the energy-system-related input files.

    Inputs:
        - converters:
            The `list` of :class:`Converter` instances available to the system.
        - debug:
            Whether to use the PV-T reduced models (False) or invented data for
            debugging purposes (True).
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenarios:
            The `list` of :class:`Scenario` instances being used for the run.

    Outputs:
        - Battery costs,
        - Battery emissions,
        - Battery input filepath,
        - Buffer tank costs,
        - Buffer tank emissions,
        - Clean-water tank tank costs,
        - Clean-water tank tank emissions,
        - Diesel costs,
        - Diesel emissions,
        - Diesel input filepath,
        - Diesel water heater costs,
        - Diesel water heater emissions,
        - Energy system filepath,
        - Hot-water tank costs,
        - Hot-water tank emissions,
        - The :class:`Minigrid` to use for the run,
        - PV costs,
        - PV emissions,
        - PV-T costs,
        - PV-T emissions,
        - Solar inputs filepath,
        - Tank inputs filepath,
        - Transmission costs,
        - Transmission emissions,
        - Transmission inputs filepath,
        - Transmitters.

    """

    # Parse the energy system input.
    energy_system_inputs_filepath = os.path.join(
        inputs_directory_relative_path, ENERGY_SYSTEM_INPUTS_FILE
    )
    energy_system_inputs = read_yaml(energy_system_inputs_filepath, logger)
    if not isinstance(energy_system_inputs, dict):
        raise InputFileError(
            "energy system inputs", "Energy system inputs are not of type `dict`."
        )
    logger.info("Energy system inputs successfully parsed.")

    # Parse the diesel inputs information.
    diesel_costs: Dict[str, float]
    diesel_emissions: Dict[str, float]
    diesel_generator: DieselGenerator
    diesel_inputs_filepath: str
    diesel_water_heater: Optional[DieselWaterHeater]
    diesel_water_heater_costs: Optional[Dict[str, float]]
    diesel_water_heater_emissions: Optional[Dict[str, float]]
    (
        diesel_costs,
        diesel_emissions,
        diesel_generator,
        diesel_inputs_filepath,
        diesel_water_heater,
        diesel_water_heater_costs,
        diesel_water_heater_emissions,
    ) = _parse_diesel_inputs(
        energy_system_inputs,
        inputs_directory_relative_path,
        logger,
        scenarios,
    )
    logger.info(
        "Diesel generator %sinformation successfully parsed.",
        "and water heater " if diesel_water_heater is not None else "",
    )

    pv_panel: solar.PVPanel
    pv_panel_costs: Dict[str, float]
    pv_panel_emissions: Dict[str, float]
    pvt_panel: Optional[solar.HybridPVTPanel]
    pvt_panel_costs: Optional[Dict[str, float]]
    pvt_panel_emissions: Optional[Dict[str, float]]
    solar_generation_inputs_filepath: str
    (
        pv_panel,
        pv_panel_costs,
        pv_panel_emissions,
        pvt_panel,
        pvt_panel_costs,
        pvt_panel_emissions,
        solar_generation_inputs_filepath,
    ) = _parse_solar_inputs(
        debug,
        energy_system_inputs,
        inputs_directory_relative_path,
        logger,
        scenarios,
    )
    logger.info("Solar panel information successfully parsed.")

    (
        battery_costs,
        battery_emissions,
        battery_inputs,
        battery_inputs_filepath,
    ) = _parse_battery_inputs(
        energy_system_inputs,
        inputs_directory_relative_path,
        logger,
        scenarios,
    )
    logger.info("Battery information successfully parsed.")

    # Parse the transmission inputs file.
    transmission_inputs_filepath: str
    transmitters: Dict[str, Transmitter]

    (
        transmission_costs,
        transmission_emissions,
        transmission_inputs_filepath,
        transmitters,
    ) = _parse_transmission_inputs(
        inputs_directory_relative_path,
        logger,
    )
    logger.info("Transmission inputs successfully parsed.")

    buffer_tank_costs: Optional[Dict[str, float]]
    buffer_tank_emissions: Optional[Dict[str, float]]
    clean_water_tank_costs: Optional[Dict[str, float]]
    clean_water_tank_emissions: Optional[Dict[str, float]]
    hot_water_tank_costs: Optional[Dict[str, float]]
    hot_water_tank_emissions: Optional[Dict[str, float]]
    exchanger_costs: Optional[Dict[str, float]]
    exchanger_emissions: Optional[Dict[str, float]]
    exchanger_inputs: Optional[List[Dict[str, Any]]]
    exchanger_inputs_filepath: Optional[str]
    tank_inputs: Optional[List[Dict[str, Any]]]
    tank_inputs_filepath: Optional[str]
    if any(scenario.desalination_scenario is not None for scenario in scenarios) or any(
        scenario.hot_water_scenario is not None for scenario in scenarios
    ):
        (
            buffer_tank_costs,
            buffer_tank_emissions,
            clean_water_tank_costs,
            clean_water_tank_emissions,
            hot_water_tank_costs,
            hot_water_tank_emissions,
            tank_inputs,
            tank_inputs_filepath,
        ) = _parse_tank_inputs(
            energy_system_inputs,
            inputs_directory_relative_path,
            logger,
            scenarios,
        )
        logger.info("Tank information successfully parsed.")

        (
            exchanger_costs,
            exchanger_emissions,
            exchanger_inputs,
            exchanger_inputs_filepath,
        ) = _parse_exchanger_inputs(
            energy_system_inputs, inputs_directory_relative_path, logger, scenarios
        )
        logger.info("Heat exchanger information successfully parsed.")

        try:
            water_pump: Optional[Transmitter] = transmitters[
                energy_system_inputs[WATER_PUMP]
            ]
        except KeyError:
            logger.error(
                "%sWater pump was not defined in the energy-system inputs file.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "energy system inputs", "Water pump not defined."
            ) from None

    else:
        buffer_tank_costs = None
        buffer_tank_emissions = None
        clean_water_tank_costs = None
        clean_water_tank_emissions = None
        hot_water_tank_costs = None
        hot_water_tank_emissions = None
        exchanger_costs = None
        exchanger_emissions = None
        exchanger_inputs = None
        exchanger_inputs_filepath = None
        tank_inputs = None
        tank_inputs_filepath = None
        water_pump = None

    # If applicable, determine the electric water heater for the system.
    if any(scenario.hot_water_scenario is not None for scenario in scenarios) and any(
        scenario.hot_water_scenario.auxiliary_heater == AuxiliaryHeaterType.ELECTRIC  # type: ignore
        for scenario in [
            scenario
            for scenario in scenarios
            if scenario.hot_water_scenario is not None
        ]
    ):
        try:
            electric_water_heater: Optional[Converter] = converters[
                energy_system_inputs[ELECTRIC_WATER_HEATER]
            ]
        except KeyError:
            logger.error(
                "%sNo electric water heater defined in the conversion inputs despite "
                "the hot-water scenario specifying that auxiliary heating is carried "
                "out electrically. See the user guide for more information on defining "
                "a valid electric water heater.%s",
                BColours.fail,
                BColours.endc,
            )
            raise
    else:
        electric_water_heater = None

    minigrid: Minigrid = Minigrid.from_dict(
        diesel_generator,
        diesel_water_heater,
        electric_water_heater,
        energy_system_inputs,
        pv_panel,
        pvt_panel,
        battery_inputs,
        exchanger_inputs,
        tank_inputs,
        water_pump,
    )

    if (
        any(scenario.desalination_scenario is not None for scenario in scenarios)
        and minigrid.clean_water_tank is None
    ):
        raise InputFileError(
            "scenario OR minigrid",
            "An available scenario specifies a clean-water system but no clean-water "
            "tank is defined.",
        )
    if (
        any(scenario.desalination_scenario is not None for scenario in scenarios)
        and minigrid.buffer_tank is None
    ):
        raise InputFileError(
            "scenario OR minigrid",
            "An available scenario specifies a desalination scenario but no buffer "
            "tank is defined.",
        )
    if (
        any(
            ResourceType.HOT_CLEAN_WATER in scenario.resource_types
            for scenario in scenarios
        )
        and minigrid.hot_water_tank is None
    ):
        raise InputFileError(
            "scenario OR minigrid",
            "An available scenario specifies a hot-water system but no hot-water tank "
            "is defined.",
        )

    return (
        battery_costs,
        battery_emissions,
        battery_inputs_filepath,
        buffer_tank_costs,
        buffer_tank_emissions,
        clean_water_tank_costs,
        clean_water_tank_emissions,
        diesel_costs,
        diesel_emissions,
        diesel_inputs_filepath,
        diesel_water_heater_costs,
        diesel_water_heater_emissions,
        energy_system_inputs_filepath,
        exchanger_costs,
        exchanger_emissions,
        exchanger_inputs_filepath,
        hot_water_tank_costs,
        hot_water_tank_emissions,
        minigrid,
        pv_panel_costs,
        pv_panel_emissions,
        pvt_panel_costs,
        pvt_panel_emissions,
        solar_generation_inputs_filepath,
        tank_inputs_filepath,
        transmission_costs,
        transmission_emissions,
        transmission_inputs_filepath,
        transmitters,
    )


def _parse_transmission_inputs(
    inputs_directory_relative_path: str,
    logger: Logger,
) -> Tuple[
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    str,
    Dict[str, Transmitter],
]:
    """
    Parses the transmission inputs file.

    Inputs:
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.

    Outputs:
        - The costs associated with the transmitters;
        - The emissions associated with the transmitters;
        - The transmission inputs relative path;
        - A `dict` mapping converter names (`str`) to :class:`transmission.Transmitter`
          instances based on the input information provided.

    """

    # Determine the conversion inputs file path.
    transmission_file_relative_path = os.path.join(
        inputs_directory_relative_path, TRANSMISSION_INPUTS_FILE
    )

    transmission_costs: Dict[str, Dict[str, float]] = {}
    transmission_emissions: Dict[str, Dict[str, float]] = {}

    # If the file exists, parse the converters contained.
    if os.path.isfile(transmission_file_relative_path):
        parsed_transmitters: List[Transmitter] = []
        transmission_inputs = read_yaml(transmission_file_relative_path, logger)
        if not isinstance(transmission_inputs, dict):
            logger.error(
                "%sTransmission inputs must be of type `dict`: the file must contain a "
                "`list` of valid transmitters for the system defined with the '%s'"
                "keyword.%s",
                BColours.fail,
                TRANSMITTERS,
                BColours.endc,
            )
            raise InputFileError(
                "transmission inputs",
                "The transmission inputs file must contain a list of transmitters.",
            )

        for entry in transmission_inputs[TRANSMITTERS]:
            if not isinstance(entry, dict):
                logger.error(
                    "%Transmitter not of correct format `dict`: %s%s",
                    BColours.fail,
                    str(entry),
                    BColours.endc,
                )
                raise InputFileError(
                    "transmission inputs", "Transmitter not correctly defined."
                )

            # Attempt to parse as a water source.
            try:
                parsed_transmitters.append(Transmitter.from_dict(entry, logger))
            except InputFileError:
                logger.info("Failed to parse a Transmitter from input information.")
                raise

        # Convert the list to the required format.
        transmitters: Dict[str, Transmitter] = {
            transmitter.name: transmitter for transmitter in parsed_transmitters
        }

        # Parse the transmission impact information.
        for transmitter in transmitters.values():
            try:
                transmission_costs[transmitter.name] = [
                    entry[COSTS]
                    for entry in transmission_inputs[TRANSMITTERS]
                    if entry[NAME] == transmitter.name
                ][0]
            except (KeyError, IndexError):
                logger.error(
                    "Failed to determine transmitter cost information for %s.",
                    transmitter.name,
                )
                raise
            logger.info(
                "Transmitter cost information for %s successfully parsed.",
                transmitter.name,
            )
            try:
                transmission_emissions[transmitter.name] = [
                    entry[EMISSIONS]
                    for entry in transmission_inputs[TRANSMITTERS]
                    if entry[NAME] == transmitter.name
                ][0]
            except (KeyError, IndexError):
                logger.error(
                    "Failed to determine transmitter emission information for %s.",
                    transmitter.name,
                )
                raise
            logger.info(
                "Transmitter emission information for %s successfully parsed.",
                transmitter.name,
            )

    else:
        transmitters = {}
        logger.info("No transmission file, skipping transmitter parsing.")

    return (
        transmission_costs,
        transmission_emissions,
        transmission_file_relative_path,
        transmitters,
    )


def parse_input_files(  # pylint: disable=too-many-locals, too-many-statements
    debug: bool,
    electric_load_profile: Optional[str],
    location_name: str,
    logger: Logger,
    optimisation_inputs_file: Optional[str],
) -> Tuple[
    Dict[str, Converter],
    Dict[load.load.Device, pd.DataFrame],
    Minigrid,
    DefaultDict[str, DefaultDict[str, float]],
    Dict[str, Union[int, str]],
    DefaultDict[str, DefaultDict[str, float]],
    pd.DataFrame,
    Location,
    Optional[OptimisationParameters],
    List[Optimisation],
    List[Scenario],
    List[Simulation],
    Optional[pd.DataFrame],
    Dict[WaterSource, pd.DataFrame],
    Dict[str, str],
]:
    """
    Parse the various input files and return content-related information.

    Inputs:
        - debug:
            Whether to use the PV-T reduced models (False) or invented data for
            debugging purposes (True).
        - electric_load_profile:
            If specified, the name of the overriding electric load profile file to use
            in for the run.
        - location_name:
            The name of the location_name being considered.
        - logger:
            The logger to use for the run.
        - optimisation_inputs_file:
            If specified, the name of the overriding optimisation inputs file to use for
            the run.

    Outputs:
        - A tuple containing:
            - converters,
            - device_utilisations, optional if carrying out load-profile generation,
            - diesel_inputs,
            - minigrid,
            - finance_inputs,
            - ghg_inputs,
            - grid_times,
            - optimisation_inputs,
            - optimisations, the `set` of optimisations to run,
            - scenarios,
            - simulations, the `list` of simulations to run,
            - a `list` of :class:`solar.SolarPanel` instances and their children which
              contain information about the PV panels being considered,
            - total_load_profile, optional if specified to be overriden,
            - a `dict` mapping the :class:`WaterSource`s available to provide
              conventional water to the system and the seasonal availabilities,
            - a `dict` containing information about the input files used.

    """

    inputs_directory_relative_path = os.path.join(
        LOCATIONS_FOLDER_NAME,
        location_name,
        INPUTS_DIRECTORY,
    )

    # Parse the conversion inputs file.
    (
        conversion_file_relative_path,
        converter_costs,
        converter_emissions,
        converters,
    ) = _parse_conversion_inputs(
        inputs_directory_relative_path,
        logger,
    )
    logger.info("Conversion inputs successfully parsed.")

    # Parse the device inputs file.
    device_inputs_filepath, devices = _parse_device_inputs(
        inputs_directory_relative_path,
        logger,
    )
    logger.info("Device inputs successfully parsed.")

    # Parse the device utilisation files.
    device_utilisations: Dict[load.load.Device, pd.DataFrame] = {}
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

    # Parse the override electric profile file if specified.
    if electric_load_profile is not None:
        try:
            with open(
                os.path.join(
                    inputs_directory_relative_path,
                    LOAD_INPUTS_DIRECTORY,
                    electric_load_profile,
                ),
                "r",
            ) as f:
                total_load_profile: Optional[pd.DataFrame] = pd.read_csv(f, index_col=0)
        except FileNotFoundError:
            logger.error(
                "%sTotal load profile '%s' could not be found.%s",
                BColours.fail,
                electric_load_profile,
                BColours.endc,
            )
            raise
    else:
        total_load_profile = None

    # Parse the scenario input information.
    (
        desalination_scenario_inputs_filepath,
        hot_water_scenario_inputs_filepath,
        scenarios,
        scenario_inputs_filepath,
    ) = parse_scenario_inputs(inputs_directory_relative_path, logger)
    logger.info("Scenario inputs successfully parsed.")

    # Parse the optimisation input information.
    optimisation_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        optimisation_inputs_file
        if optimisation_inputs_file is not None
        else OPTIMISATION_INPUTS_FILE,
    )
    optimisation_inputs = read_yaml(optimisation_inputs_filepath, logger)
    if not isinstance(optimisation_inputs, dict):
        raise InputFileError(
            "optimisation inputs", "Optimisation inputs is not of type `dict`."
        )
    try:
        optimisation_parameters = OptimisationParameters.from_dict(
            list(converters.values()), logger, optimisation_inputs
        )
    except Exception as e:
        logger.error(
            "%sAn error occurred parsing the optimisation inputs file: %s%s",
            BColours.fail,
            str(e),
            BColours.endc,
        )
        raise
    logger.info("Optimisation inputs successfully parsed.")

    try:
        optimisations: List[Optimisation] = [
            Optimisation.from_dict(logger, entry, scenarios)
            for entry in optimisation_inputs[OPTIMISATIONS]
        ]
    except Exception as e:
        logger.error(
            "%sError generating optimisations from inputs file: %s%s",
            BColours.fail,
            str(e),
            BColours.endc,
        )
        raise
    logger.info("Optimisations file successfully parsed.")

    # Parse the simulation(s) input information.
    simulations_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        SIMULATIONS_INPUTS_FILE,
    )
    simulations_file_contents = read_yaml(
        simulations_inputs_filepath,
        logger,
    )
    if not isinstance(simulations_file_contents, list):
        raise InputFileError(
            "simulation inputs", "Simulation inputs must be of type `list`."
        )
    simulations: List[Simulation] = [
        Simulation.from_dict(entry) for entry in simulations_file_contents
    ]

    # Parse the energy-system input information.
    (
        battery_costs,
        battery_emissions,
        battery_inputs_filepath,
        buffer_tank_costs,
        buffer_tank_emissions,
        clean_water_tank_costs,
        clean_water_tank_emissions,
        diesel_costs,
        diesel_emissions,
        diesel_inputs_filepath,
        diesel_water_heater_costs,
        diesel_water_heater_emissions,
        energy_system_inputs_filepath,
        exchanger_costs,
        exchanger_emissions,
        exchanger_inputs_filepath,
        hot_water_tank_costs,
        hot_water_tank_emissions,
        minigrid,
        pv_panel_costs,
        pv_panel_emissions,
        pvt_panel_costs,
        pvt_panel_emissions,
        solar_generation_inputs_filepath,
        tank_inputs_filepath,
        transmission_costs,
        transmission_emissions,
        transmission_inputs_filepath,
        transmitters,
    ) = _parse_minigrid_inputs(
        converters, debug, inputs_directory_relative_path, logger, scenarios
    )
    logger.info("Energy-system inputs successfully parsed.")

    generation_inputs_filepath = os.path.join(
        inputs_directory_relative_path, GENERATION_INPUTS_FILE
    )
    generation_inputs = read_yaml(generation_inputs_filepath, logger)
    if not isinstance(generation_inputs, dict):
        logger.error(
            "%sThe generation inputs file was invalid: information must be contained "
            "within a `dict`. See the user-guide.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "generation inputs",
            "The contents of the generation inputs file must be a key-value "
            "dictionary.",
        )
    logger.info("Generation inputs successfully parsed.")

    grid_times_filepath = os.path.join(
        inputs_directory_relative_path,
        GRID_TIMES_FILE,
    )
    with open(
        grid_times_filepath,
        "r",
    ) as grid_times_file:
        grid_times: pd.DataFrame = pd.read_csv(
            grid_times_file,
            index_col=0,
        )
    logger.info("Grid times successfully parsed.")

    if any(scenario.desalination_scenario is not None for scenario in scenarios):
        # Parse the water-source inputs file.
        conventional_water_source_inputs: Optional[List[Dict[str, float]]]
        conventional_water_source_inputs_filepath: Optional[str]
        conventional_water_sources: Optional[Set[WaterSource]]
        (
            conventional_water_source_inputs,
            conventional_water_source_inputs_filepath,
            conventional_water_sources,
        ) = _parse_conventional_water_source_inputs(
            inputs_directory_relative_path,
            logger,
        )
        logger.info("Conventional water-source inputs file successfully parsed.")
        logger.debug(
            "Conventional water sources: %s",
            ", ".join([source.name for source in conventional_water_sources]),
        )

        water_source_times: Dict[WaterSource, pd.DataFrame] = {}
        for source in conventional_water_sources:
            try:
                with open(
                    os.path.join(
                        inputs_directory_relative_path,
                        CONVENTIONAL_WATER_SOURCE_AVAILABILITY_DIRECTORY,
                        WATER_SOURCE_AVAILABILTY_TEMPLATE_FILENAME.format(
                            water_source=source.name
                        ),
                    ),
                    "r",
                ) as f:
                    water_source_times[source] = pd.read_csv(
                        f,
                        header=None,
                        index_col=None,
                    )
            except FileNotFoundError:
                logger.error(
                    "%sError parsing water-source availability profile for %s, check "
                    "that the profile is present and that all conventional "
                    "water-source names are consistent.%s",
                    BColours.fail,
                    source.name,
                    BColours.endc,
                )
                raise

        logger.info("Conventional water-source times successfully parsed.")
    # Otherwise, instantiate an empty dict.
    else:
        conventional_water_source_inputs = None
        conventional_water_source_inputs_filepath = None
        conventional_water_sources = None
        water_source_times = {}

    location_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        LOCATION_INPUTS_FILE,
    )
    location_inputs = read_yaml(
        location_inputs_filepath,
        logger,
    )
    if not isinstance(location_inputs, dict):
        raise InputFileError(
            "location inputs", "Location inputs is not of type `dict`."
        )
    location: Location = Location.from_dict(location_inputs)
    if not isinstance(location, Location):
        raise InternalError(
            "Location was not returned when calling `Location.from_dict`."
        )
    logger.info("Location inputs successfully parsed.")

    # Parse and collate the impact information.
    finance_inputs_filepath = os.path.join(
        inputs_directory_relative_path, FINANCE_INPUTS_FILE
    )
    # Finance input type: Dict[str, Union[float, Dict[str, float]]]
    finance_data = read_yaml(finance_inputs_filepath, logger)
    if not isinstance(finance_data, dict):
        raise InputFileError(
            "finance inputs", "Finance inputs must be of type `dict` not `list`."
        )
    finance_inputs: DefaultDict[str, DefaultDict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    finance_inputs.update(finance_data)
    logger.info("Finance inputs successfully parsed.")

    ghg_inputs_filepath = os.path.join(inputs_directory_relative_path, GHG_INPUTS_FILE)
    # Ghg data type: Dict[str, Union[float, Dict[str, float]]]
    ghg_data = read_yaml(ghg_inputs_filepath, logger)
    if not isinstance(finance_data, dict):
        raise InputFileError(
            "ghg inputs", "GHG inputs must be of type `dict` not `list`."
        )
    # Generate a default dict to take care of missing data.
    ghg_inputs: DefaultDict[str, DefaultDict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    ghg_inputs.update(ghg_data)  # type: ignore
    logger.info("GHG inputs successfully parsed.")

    # Update the finance and GHG inputs accordingly with the PV data.
    logger.info("Updating with PV impact data.")
    finance_inputs[ImpactingComponent.PV.value] = defaultdict(float, pv_panel_costs)
    ghg_inputs[ImpactingComponent.PV.value] = defaultdict(float, pv_panel_emissions)
    logger.info("PV impact data successfully updated.")

    # Update the impact inputs with the diesel data.
    if any(
        scenario.diesel_scenario.mode != DieselMode.DISABLED for scenario in scenarios
    ):
        logger.info("Updating with diesel impact data.")
        finance_inputs[ImpactingComponent.DIESEL.value] = defaultdict(
            float, diesel_costs
        )
        ghg_inputs[ImpactingComponent.DIESEL.value] = defaultdict(
            float, diesel_emissions
        )
        logger.info("Diesel impact data successfully updated.")
    else:
        logger.info("No diesel generator present, skipping impact data.")

    # Update the impact inputs with the battery data.
    if any(scenario.battery for scenario in scenarios):
        if battery_costs is None:
            logger.error(
                "%sNo battery cost information parsed despite a battery being present "
                "in one or more of the scenarios.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "scenario inputs OR finance inputs",
                "No battery cost information despite a battery being requested.",
            )
        if battery_emissions is None:
            logger.error(
                "%sNo battery emissions information parsed despite a battery being "
                "present in one or more of the scenarios.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "scenario inputs OR finance inputs",
                "No battery emissions information despite a battery being requested.",
            )
        logger.info("Updating with battery impact data.")
        finance_inputs[ImpactingComponent.STORAGE.value] = defaultdict(
            float, battery_costs
        )
        ghg_inputs[ImpactingComponent.STORAGE.value] = defaultdict(
            float, battery_emissions
        )
        logger.info("Battery impact data successfully updated.")
    else:
        logger.info("No battery present, skipping impact data.")

    if minigrid.pvt_panel is not None and any(scenario.pv_t for scenario in scenarios):
        if pvt_panel_costs is None or pvt_panel_emissions is None:
            raise InternalError("Error processing PV-T panel cost and emissions.")
        finance_inputs[ImpactingComponent.PV_T.value] = defaultdict(
            float, pvt_panel_costs
        )
        ghg_inputs[ImpactingComponent.PV_T.value] = defaultdict(
            float, pvt_panel_emissions
        )
    else:
        logger.info("PV-T disblaed in scenario file, skipping PV-T impact parsing.")

    # Add transmitter impacts.
    for converter in converters.values():
        logger.info("Updating with %s impact data.", converter.name)
        finance_inputs[
            FINANCE_IMPACT.format(
                type=ImpactingComponent.CONVERTER.value, name=converter.name
            )
        ] = defaultdict(float, converter_costs[converter])
        ghg_inputs[
            GHG_IMPACT.format(
                type=ImpactingComponent.CONVERTER.value, name=converter.name
            )
        ] = defaultdict(float, converter_emissions[converter])
        logger.info("Converter %s impact data successfully updated.", converter.name)

    # Add transmitter impacts.
    for transmitter in transmitters:
        logger.info("Updating with %s impact data.", transmitter)
        finance_inputs[
            FINANCE_IMPACT.format(
                type=ImpactingComponent.TRANSMITTER.value, name=transmitter
            )
        ] = defaultdict(float, transmission_costs[transmitter])
        ghg_inputs[
            GHG_IMPACT.format(
                type=ImpactingComponent.TRANSMITTER.value, name=transmitter
            )
        ] = defaultdict(float, transmission_emissions[transmitter])
        logger.info("Transmitter %s impact data successfully updated.", transmitter)

    # Add desalination-specific impacts.
    if any(
        scenario.desalination_scenario is not None
        and scenario.desalination_scenario.pvt_scenario.heats == HTFMode.CLOSED_HTF
        for scenario in scenarios
    ):
        # Update the clean-water tank impacts.
        logger.info("Updating with clean-water tank impact data.")
        finance_inputs[ImpactingComponent.CLEAN_WATER_TANK.value] = defaultdict(
            float, clean_water_tank_costs  # type: ignore
        )
        ghg_inputs[ImpactingComponent.CLEAN_WATER_TANK.value] = defaultdict(
            float, clean_water_tank_emissions  # type: ignore
        )
        logger.info("Clean-water tank impact data successfully updated.")

        # Update the buffer tank impacts.
        logger.info("Updating with buffer tank impact data.")
        if buffer_tank_costs is None or buffer_tank_emissions is None:
            raise InternalError("Error processing buffer-tank cost and emissions.")
        finance_inputs[ImpactingComponent.BUFFER_TANK.value] = defaultdict(
            float, buffer_tank_costs
        )
        ghg_inputs[ImpactingComponent.BUFFER_TANK.value] = defaultdict(
            float, buffer_tank_emissions
        )
        logger.info("Buffer tank impact data successfully updated.")

        # Update the heat-exchanger imapcts.
        logger.info("Updating with heat-exchanger impact data.")
        if exchanger_costs is None or exchanger_emissions is None:
            raise InternalError("Error processing heat-exchanger cost and emissions.")
        finance_inputs[ImpactingComponent.HEAT_EXCHANGER.value] = defaultdict(
            float, exchanger_costs
        )
        ghg_inputs[ImpactingComponent.HEAT_EXCHANGER.value] = defaultdict(
            float, exchanger_emissions
        )
        logger.info("Heat-exchanger impact data successfully updated.")

        # Include the impacts of conventional water sources.
        logger.info("Updating with conventional water-source impact data.")
        if (
            any(scenario.desalination_scenario is not None for scenario in scenarios)
            and conventional_water_sources is not None
            and conventional_water_source_inputs is not None
        ):
            for source in conventional_water_sources:
                try:
                    conventional_source_costs: Union[float, Dict[str, float]] = [
                        entry[COSTS]
                        for entry in conventional_water_source_inputs
                        if entry[NAME] == source.name
                    ][0]
                except (KeyError, IndexError):
                    logger.error(
                        "%sNo finance inputs for conventional source %s.%s",
                        BColours.fail,
                        source.name,
                        BColours.endc,
                    )
                    raise

                if not isinstance(conventional_source_costs, dict):
                    logger.error(
                        "%sConventional water source cost information must be a "
                        "key-value `dict`. See the user guide for more information.%s",
                        BColours.fail,
                        BColours.endc,
                    )
                    raise InputFileError(
                        "water source inputs",
                        f"Conventional water source {source.name} has invalid cost "
                        "information.",
                    )

                finance_inputs[
                    f"{ImpactingComponent.CONVENTIONAL_SOURCE.value}_{source.name}"
                ] = defaultdict(float, conventional_source_costs)

                try:
                    conventional_source_emissions: Union[float, Dict[str, float]] = [
                        entry[EMISSIONS]
                        for entry in conventional_water_source_inputs
                        if entry[NAME] == source.name
                    ][0]
                except (KeyError, IndexError):
                    logger.error(
                        "%sNo ghg inputs for conventional source %s.%s",
                        BColours.fail,
                        source.name,
                        BColours.endc,
                    )
                    raise

                if not isinstance(conventional_source_emissions, dict):
                    logger.error(
                        "%sConventional water source emission information must be a "
                        "key-value `dict`. See the user guide for more information.%s",
                        BColours.fail,
                        BColours.endc,
                    )
                    raise InputFileError(
                        "water source inputs",
                        f"Conventional water source {source.name} has invalid emission "
                        "information.",
                    )

                ghg_inputs[
                    f"{ImpactingComponent.CONVENTIONAL_SOURCE.value}_{source.name}"
                ] = defaultdict(float, conventional_source_emissions)

    # Add hot-water-specific impacts.
    if any(scenario.hot_water_scenario is not None for scenario in scenarios):
        # Update the hot-water tank impacts.
        logger.info("Updating with hot-water tank impact data.")
        finance_inputs[ImpactingComponent.HOT_WATER_TANK.value] = defaultdict(
            float, hot_water_tank_costs  # type: ignore
        )
        ghg_inputs[ImpactingComponent.HOT_WATER_TANK.value] = defaultdict(
            float, hot_water_tank_emissions  # type: ignore
        )
        logger.info("Hot-water tank impact data successfully updated.")

        # Update the diesel water-heater impacts.
        logger.info("Updating with diesel water-heater impact data.")
        finance_inputs[ImpactingComponent.DIESEL_WATER_HEATER.value] = defaultdict(
            float, diesel_water_heater_costs  # type: ignore
        )
        ghg_inputs[ImpactingComponent.DIESEL_WATER_HEATER.value] = defaultdict(
            float, diesel_water_heater_emissions  # type: ignore
        )
        logger.info("Diesel water-heater impact data successfully updated.")

    # Generate a dictionary with information about the input files used.
    input_file_info: Dict[str, str] = {
        "batteries": battery_inputs_filepath,
        "converters": conversion_file_relative_path,
        "devices": device_inputs_filepath,
        "diesel_inputs": diesel_inputs_filepath,
        "energy_system": energy_system_inputs_filepath,
        "finance_inputs": finance_inputs_filepath,
        "generation_inputs": generation_inputs_filepath,
        "ghg_inputs": ghg_inputs_filepath,
        "grid_times": grid_times_filepath,
        "location_inputs": location_inputs_filepath,
        "optimisation_inputs": optimisation_inputs_filepath,
        "scenarios": scenario_inputs_filepath,
        "simularion": simulations_inputs_filepath,
        "solar_inputs": solar_generation_inputs_filepath,
        "transmission_inputs": transmission_inputs_filepath,
    }

    if any(scenario.desalination_scenario is not None for scenario in scenarios):
        if conventional_water_source_inputs_filepath is not None:
            input_file_info[
                "conventional_water_source_inputs"
            ] = conventional_water_source_inputs_filepath
        if tank_inputs_filepath is not None:
            input_file_info["tank_inputs"] = tank_inputs_filepath

    if any(
        scenario.desalination_scenario is not None
        and scenario.desalination_scenario.pvt_scenario.heats == HTFMode.CLOSED_HTF
        for scenario in scenarios
    ):
        input_file_info["desalination_scenario"] = desalination_scenario_inputs_filepath
        if exchanger_inputs_filepath is not None:
            input_file_info["exchanger_inputs"] = exchanger_inputs_filepath

    if any(scenario.hot_water_scenario is not None for scenario in scenarios):
        input_file_info["hot_water_scenario"] = hot_water_scenario_inputs_filepath

    logger.debug("Input file parsing complete.")
    logger.debug(
        "Converters: %s",
        ", ".join([str(converter) for converter in converters]),
    )
    logger.debug("Devices: %s", ", ".join([str(device) for device in devices]))
    logger.debug("Energy system/minigrid: %s", str(minigrid))
    logger.debug(
        "Financial input information: %s", json.dumps(finance_inputs, indent=4)
    )
    logger.debug("GHG input information: %s", json.dumps(ghg_data, indent=4))
    logger.debug("Location: %s", str(location))
    logger.debug("Optimisation parameters: %s", optimisation_parameters)
    logger.debug(
        "Optimisations: %s",
        ", ".join([str(optimisation) for optimisation in optimisations]),
    )
    logger.debug("Scenarios: %s", ", ".join([str(entry) for entry in scenarios]))
    logger.debug(
        "Simulations: %s", ", ".join([str(simulation) for simulation in simulations])
    )
    logger.debug(
        "Transmitters: %s",
        ", ".join([f"{key}: {value}" for key, value in transmitters.items()]),
    )
    logger.debug("Input file information: %s", input_file_info)

    return (
        converters,
        device_utilisations,
        minigrid,
        finance_inputs,
        generation_inputs,
        ghg_inputs,
        grid_times,
        location,
        optimisation_parameters,
        optimisations,
        scenarios,
        simulations,
        total_load_profile,
        water_source_times,
        input_file_info,
    )
