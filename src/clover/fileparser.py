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

from logging import Logger
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import json
from numpy import isin
import pandas as pd  # pylint: disable=import-error

from sklearn.linear_model._coordinate_descent import Lasso

from . import load
from .generation import solar
from .impact.finance import COSTS, ImpactingComponent
from .impact.ghgs import EMISSIONS
from .simulation.diesel import DIESEL_CONSUMPTION, MINIMUM_LOAD, DieselWaterHeater

from .__utils__ import (
    AuxiliaryHeaterType,
    BColours,
    DesalinationScenario,
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
    OptimisationParameters,
    PACKAGE_NAME,
    RAW_CLOVER_PATH,
    read_yaml,
    Scenario,
    Simulation,
)
from .conversion.conversion import (
    Convertor,
    MultiInputConvertor,
    ThermalDesalinationPlant,
    WaterSource,
)
from .optimisation.optimisation import Optimisation
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

# Desalination scenario inputs file:
#   The relative path to the desalination-scenario inputs file.
DESALINATION_SCENARIO_INPUTS_FILE: str = os.path.join(
    "scenario", "desalination_scenario.yaml"
)

# Device inputs file:
#   The relative path to the device-inputs file.
DEVICE_INPUTS_FILE: str = os.path.join("load", "devices.yaml")

# Device utilisation template filename:
#   The template filename of device-utilisation profiles used for parsing the files.
DEVICE_UTILISATION_TEMPLATE_FILENAME: str = "{device}_times.csv"

# Device utilisations input directory:
#   The relative path to the directory contianing the device-utilisaion information.
DEVICE_UTILISATIONS_INPUT_DIRECTORY: str = os.path.join("load", "device_utilisation")

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

# Finance impact:
#   Default `str` used as the format for specifying unique financial impacts.
FINANCE_IMPACT: str = "{type}_{name}"

# Finance inputs file:
#   The relative path to the finance-inputs file.
FINANCE_INPUTS_FILE: str = os.path.join("impact", "finance_inputs.yaml")

# Generation inputs file:
#   The relative path to the generation-inputs file.
GENERATION_INPUTS_FILE: str = os.path.join("generation", "generation_inputs.yaml")

# GHG impact:
#   A base `str` used for specifying unique ghg impacts.
GHG_IMPACT: str = "{type}_{name}"

# GHG inputs file:
#   The relative path to the GHG inputs file.
GHG_INPUTS_FILE: str = os.path.join("impact", "ghg_inputs.yaml")

# Grid inputs file:
#   The relative path to the grid-inputs file.
GRID_TIMES_FILE: str = os.path.join("generation", "grid_times.csv")

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
    "load", "device_utilisation", "kerosene_times.csv"
)

# Kerosene utilisation filepath:
#   The path to the kerosene utilisation profile.
KEROSENE_USAGE_FILE: str = os.path.join("load", "device_usage", "kerosene_in_use.csv")

# Location inputs file:
#   The relative path to the location inputs file.
LOCATION_INPUTS_FILE: str = os.path.join("location_data", "location_inputs.yaml")

# Optimisation inputs file:
#   The relative path to the optimisation-input information file.
OPTIMISATION_INPUTS_FILE: str = os.path.join("optimisation", "optimisation_inputs.yaml")

# Optimisations:
#   Key used to extract the list of optimisations from the input file.
OPTIMISATIONS: str = "optimisations"

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


def _determine_available_convertors(
    convertors: Dict[str, Convertor],
    logger: Logger,
    minigrid: Minigrid,
    scenario: Scenario,
) -> List[Convertor]:
    """
    Determines the available :class:`Convertor` instances based on the :class:`Scenario`

    Inputs:
        - convertors:
            The :class:`Convertor` instances defined, parsed from the conversion inputs
            file.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - minigrid:
            The :class:`Minigrid` to use for the run.
        - scenario:
            The :class:`Scenario` to use for the run.

    Outputs:
        - A `list` of :class:`Convertor` instances available to the system.

    """

    available_convertors: List[Convertor] = []

    if scenario.desalination_scenario is None and scenario.hot_water_scenario is None:
        return available_convertors

    # Determine the available convertors from the scenarios file.
    if scenario.desalination_scenario is not None:
        # Process the clean-water convertors.
        for entry in scenario.desalination_scenario.clean_water_scenario.sources:
            try:
                available_convertors.append(convertors[entry])
            except KeyError as e:
                logger.error(
                    "%sUnknown clean-water source specified in the scenario file: %s%s",
                    BColours.fail,
                    entry,
                    BColours.endc,
                )
                raise InputFileError(
                    "desalination scenario",
                    f"{BColours.fail}Unknown clean-water source(s) in the scenario "
                    + f"file: {entry}{BColours.endc}",
                ) from None

        # Process the feedwater sources.
        for entry in scenario.desalination_scenario.unclean_water_sources:
            try:
                available_convertors.append(convertors[entry])
            except KeyError as e:
                logger.error(
                    "%sUnknown unclean-water source specified in the scenario file: %s"
                    "%s",
                    BColours.fail,
                    entry,
                    BColours.endc,
                )
                raise InputFileError(
                    "desalination scenario",
                    f"{BColours.fail}Unknown unclean-water source in the scenario "
                    + f"file: {entry}{BColours.endc}",
                ) from None

    if scenario.hot_water_scenario is not None:
        # Process the hot-water convertors.
        for entry in scenario.hot_water_scenario.conventional_sources:
            try:
                available_convertors.append(convertors[entry])
            except KeyError as e:
                logger.error(
                    "%sUnknown conventional hot-water source specified in the "
                    "hot-water scenario file: %s%s",
                    BColours.fail,
                    entry,
                    BColours.endc,
                )
                raise InputFileError(
                    "hot-water scenario",
                    f"{BColours.fail}Unknown conventional hot-water source(s) in the "
                    + f"hot-water scenario file: {entry}{BColours.endc}",
                ) from None

        if scenario.hot_water_scenario.auxiliary_heater == AuxiliaryHeaterType.ELECTRIC:
            if minigrid.electric_water_heater is None:
                logger.error(
                    "%sAuxiliary heating method of electric heating specified despite "
                    "no electric water heater being selected in the energy-system "
                    "inputs.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise InputFileError(
                    "energy system inputs OR hot-water scenario",
                    "Mismatch between electric water heating scenario.",
                )
            available_convertors.append(convertors[minigrid.electric_water_heater.name])

    return available_convertors


def _parse_battery_inputs(
    energy_system_inputs: Dict[str, Any],
    inputs_directory_relative_path: str,
    logger: Logger,
    scenario: Scenario,
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
        - scenario:
            The :class:`Scneario` to use for the run.

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
    if scenario.battery:
        logger.info("Parsing battery impact information.")
        try:
            battery_costs: Optional[Dict[str, float]] = [
                entry[COSTS]
                for entry in battery_inputs
                if entry[NAME] == energy_system_inputs[BATTERY]
            ][0]
        except IndexError:
            logger.error("Failed to determine battery cost information.")
            raise
        else:
            logger.info("Battery cost information successfully parsed.")
        try:
            battery_emissions: Optional[Dict[str, float]] = [
                entry[EMISSIONS]
                for entry in battery_inputs
                if entry[NAME] == energy_system_inputs[BATTERY]
            ][0]
        except IndexError:
            logger.error("Failed to determine battery emission information.")
            raise
        else:
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
) -> Tuple[str, Dict[str, Convertor]]:
    """
    Parses the conversion inputs file.

    Inputs:
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.

    Outputs:
        - The conversion inputs relative path;
        - A `dict` mapping convertor names (`str`) to :class:`conversion.Convertor`
          instances based on the input information provided.

    """

    # Determine the conversion inputs file path.
    conversion_file_relative_path = os.path.join(
        inputs_directory_relative_path, CONVERSION_INPUTS_FILE
    )

    # If the file exists, parse the convertors contained.
    if os.path.isfile(conversion_file_relative_path):
        parsed_convertors: List[Convertor] = []
        conversion_inputs = read_yaml(conversion_file_relative_path, logger)
        if conversion_inputs is not None:
            if not isinstance(conversion_inputs, list):
                logger.error(
                    "%sThe conversion inputs file must be a `list` of valid convertors.%s",
                    BColours.fail,
                    BColours.endc,
                )
        if conversion_inputs is not None and len(conversion_inputs) > 0:
            for entry in conversion_inputs:
                if not isinstance(entry, dict):
                    logger.error(
                        "%sConvertor not of correct format `dict`: %s%s",
                        BColours.fail,
                        str(entry),
                        BColours.endc,
                    )
                    raise InputFileError(
                        "conversion inputs", "Convertors not correctly defined."
                    )

                # Attempt to parse as a water source.
                try:
                    parsed_convertors.append(WaterSource.from_dict(entry, logger))
                except InputFileError:
                    logger.info(
                        "Failed to create a single-input convertor, trying a thermal "
                        "desalination plant."
                    )

                    # Attempt to parse as a thermal desalination plant.
                    try:
                        parsed_convertors.append(
                            ThermalDesalinationPlant.from_dict(entry, logger)
                        )
                    except KeyError:
                        logger.info(
                            "Failed to create a thermal desalination plant, trying "
                            "a multi-input convertor."
                        )

                        # Parse as a generic multi-input convertor.
                        parsed_convertors.append(
                            MultiInputConvertor.from_dict(entry, logger)
                        )
                        logger.info("Parsed multi-input convertor from input data.")
                    logger.info("Parsed thermal desalination plant from input data.")

                else:
                    logger.info("Parsed single-input convertor from input data.")

            # Convert the list to the required format.
            convertors: Dict[str, Convertor] = {
                convertor.name: convertor for convertor in parsed_convertors
            }

        else:
            convertors = {}
            logger.info("Conversion file empty, continuing with no defined convertors.")

    else:
        convertors = {}
        logger.info("No conversion file, skipping convertor parsing.")

    return conversion_file_relative_path, convertors


def _parse_diesel_inputs(
    energy_system_inputs: Dict[str, Any],
    inputs_directory_relative_path: str,
    logger: Logger,
    scenario: Scenario,
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
        - scenario:
            The :class:`Scenario` for the run.

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
                "Diesel generator '{}' not found in diesel inputs.".format(
                    energy_system_inputs[DIESEL_GENERATOR]
                ),
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
    except IndexError:
        logger.error("Failed to determine diesel cost information.")
        raise
    else:
        logger.info("Diesel cost information successfully parsed.")

    # Determine the diesel emissions.
    try:
        diesel_emissions = [
            entry[EMISSIONS]
            for entry in diesel_inputs[DIESEL_GENERATORS]
            if entry[NAME] == diesel_generator.name
        ][0]
    except IndexError:
        logger.error("Failed to determine diesel emission information.")
        raise
    else:
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
                "Diesel water heater '{}' not found in diesel inputs.".format(
                    energy_system_inputs[DIESEL_WATER_HEATER]
                ),
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
        except IndexError:
            logger.error(
                "%sFailed to determine diesel water-heater cost information.%s",
                BColours.fail,
                BColours.endc,
            )
            raise
        else:
            logger.info("Diesel water-heater cost information successfully parsed.")

        # Determine the diesel emissions.
        try:
            diesel_water_heater_emissions: Optional[Dict[str, float]] = [
                entry[EMISSIONS]
                for entry in diesel_inputs[DIESEL_WATER_HEATERS]
                if entry[NAME] == diesel_water_heater.name
            ][0]
        except IndexError:
            logger.error(
                "%sFailed to determine diesel water-heater emission information.%s",
                BColours.fail,
                BColours.endc,
            )
            raise
        else:
            logger.info("Diesel water-heater emission information successfully parsed.")

    elif (
        scenario.hot_water_scenario is not None
        and scenario.hot_water_scenario.auxiliary_heater == AuxiliaryHeaterType.DIESEL
    ):
        logger.error(
            "%sDiesel water heater must be specified in the energy system inputs file "
            "if the hot-water scenario states that a diesel water heater is present.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "energy system inputs",
            "No diesel water heater was specified despite being required by the "
            f"current scenario. Use the {DIESEL_WATER_HEATER} keyword to select a "
            + "valid diesel generator.",
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
    if not isinstance(device_inputs_filepath, list):
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
    scenario: Scenario,
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
        - scenario:
            The :class:`Scneario` to use for the run.

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
        scenario.desalination_scenario is not None
        and scenario.desalination_scenario.pvt_scenario.heats == HTFMode.CLOSED_HTF
    ) or scenario.hot_water_scenario is not None:
        logger.info("Parsing exchanger impact information.")
        try:
            exchanger_costs = [
                entry[COSTS]
                for entry in exchanger_inputs[EXCHANGERS]
                if entry[NAME] == energy_system_inputs[EXCHANGER]
            ][0]
        except IndexError:
            logger.error("Failed to determine exchanger cost information.")
            raise
        else:
            logger.info("Exchanger cost information successfully parsed.")
        try:
            exchanger_emissions = [
                entry[EMISSIONS]
                for entry in exchanger_inputs[EXCHANGERS]
                if entry[NAME] == energy_system_inputs[EXCHANGER]
            ][0]
        except IndexError:
            logger.error("Failed to determine exchanger emission information.")
            raise
        else:
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


def _parse_pvt_reduced_models(
    logger: Logger, scenario: Scenario
) -> Tuple[Lasso, Lasso]:
    """
    Parses the PV-T models from the installed package or raw files.

    Inputs:
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenario:
            The current :class:`Scneario` for the run.

    Outputs:
        - A `list` of :class:`DieselGenerator` instances based on the input information
          provided.

    """

    if scenario.pv_t:
        # Attempt to read the thermal model file as per CLOVER being an installed
        # package.
        logger.info(
            "Attempting to read PV-T reduced thermal model from installed package info."
        )
        try:
            thermal_model: Optional[Lasso] = pickle.load(
                pkgutil.get_data(PACKAGE_NAME, THERMAL_MODEL_FILE)  # type: ignore
            )
        except (AttributeError, FileNotFoundError, TypeError):
            logger.info("Failed to read data as if package was installed.")

            # Attempt to read the thermal model file from raw source information.
            logger.info(
                "Attempting to read PV-T reduced thermal model from raw source file."
            )
            try:
                with open(os.path.join(RAW_CLOVER_PATH, THERMAL_MODEL_FILE), "rb") as f:
                    thermal_model = pickle.load(f)
            except Exception:
                logger.error(
                    "Failed to read PV-T reduced thermal model from raw source."
                )
                logger.critical("Failed to determine PV-T reduced thermal model.")
                raise
            logger.info(
                "Successfully read PV-T reduced thermal model form local source."
            )

        else:
            logger.info(
                "Successfully read PV-T reduced thermal model form installed package file."
            )

        logger.info("PV-T reduced thermal model file successfully read.")

        # Read the electric model.
        logger.info(
            "Attempting to read PV-T reduced electric model from installed package info."
        )
        try:
            # Attempt to read the electric model file as per CLOVER being an installed
            # package.
            electric_model: Optional[Lasso] = pickle.load(
                pkgutil.get_data(PACKAGE_NAME, ELECTRIC_MODEL_FILE)  # type: ignore
            )
        except (AttributeError, FileNotFoundError, TypeError):
            logger.info("Failed to read data as if package was installed.")

            # Attempt to read the electric model from raw source information.
            logger.info(
                "Attempting to read PV-T reduced electric model from raw source file."
            )
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
                "Successfully read PV-T reduced electric model form local source."
            )

        else:
            logger.info(
                "Successfully read PV-T reduced electric model form installed package file."
            )

        logger.info("PV-T reduced electric model file successfully read.")

    # If there is no PV-T being used in the system, do not attempt to read the files.
    else:
        thermal_model = None
        electric_model = None

    return electric_model, thermal_model


def _parse_scenario_inputs(
    inputs_directory_relative_path: str,
    logger: Logger,
) -> Tuple[str, str, Scenario, str]:
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
            desalination_scenario: Optional[
                DesalinationScenario
            ] = DesalinationScenario.from_dict(desalination_scenario_inputs, logger)
        except Exception as e:
            logger.error(
                "%sError generating deslination scenario from inputs file: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise
        logger.info("Desalination scenario successfully parsed.")
    else:
        desalination_scenario = None
        logger.info("No desalination scenario provided, skipping.")

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
            hot_water_scenario: Optional[HotWaterScenario] = HotWaterScenario.from_dict(
                hot_water_scenario_inputs, logger
            )
        except Exception as e:
            logger.error(
                "%sError generating hot-water scenario from inputs file: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise
        logger.info("Hot-water scenario successfully parsed.")
    else:
        hot_water_scenario = None
        logger.info("No hot-water scenario provided, skipping.")

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
        scenario: Scenario = Scenario.from_dict(
            desalination_scenario, hot_water_scenario, logger, scenario_inputs
        )
    except Exception as e:
        logger.error(
            "%sError generating scenario from inputs file: %s%s",
            BColours.fail,
            str(e),
            BColours.endc,
        )
        raise

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
        scenario,
        scenario_inputs_filepath,
    )


def _parse_solar_inputs(
    energy_system_inputs: Dict[str, Any],
    inputs_directory_relative_path: str,
    logger: Logger,
    scenario: Scenario,
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
        - energy_system_inputs:
            The un-processed energy-system input information.
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenario:
            The current :class:`Scneario` for the run.

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
    electric_model, thermal_model = _parse_pvt_reduced_models(logger, scenario)

    # Parse the PV-T panel information
    for panel_input in solar_generation_inputs["panels"]:
        if panel_input["type"] == solar.SolarPanelType.PV_T.value:
            solar_panels.append(
                solar.HybridPVTPanel(
                    electric_model, logger, panel_input, solar_panels, thermal_model
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
    except IndexError:
        logger.error(
            "%sFailed to determine costs for PV panel %s.%s",
            BColours.fail,
            energy_system_inputs["pv_panel"],
            BColours.endc,
        )
        raise
    else:
        logger.info("PV panel costs successfully determined.")

    # Determine the PV panel emissions.
    try:
        pv_panel_emissions: Dict[str, float] = [
            panel_data[EMISSIONS]
            for panel_data in solar_generation_inputs["panels"]
            if panel_data[NAME] == pv_panel.name
        ][0]
    except IndexError:
        logger.error(
            "%sFailed to determine emissions for PV panel %s.%s",
            BColours.fail,
            energy_system_inputs["pv_panel"],
            BColours.endc,
        )
        raise
    else:
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
        except IndexError:
            logger.error(
                "%sFailed to determine costs for PV-T panel %s.%s",
                BColours.fail,
                energy_system_inputs["pvt_panel"],
                BColours.endc,
            )
            raise
        else:
            logger.info("PV-T panel costs successfully determined.")
        try:
            pvt_panel_emissions: Optional[Dict[str, float]] = [
                panel_data[EMISSIONS]
                for panel_data in solar_generation_inputs["panels"]
                if panel_data[NAME] == pvt_panel.name
            ][0]
        except IndexError:
            logger.error(
                "%sFailed to determine emissions for PV-T panel %s.%s",
                BColours.fail,
                energy_system_inputs["pvt_panel"],
                BColours.endc,
            )
            raise
        else:
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


def _parse_tank_inputs(
    energy_system_inputs: Dict[str, Any],
    inputs_directory_relative_path: str,
    logger: Logger,
    scenario: Scenario,
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
        - scenario:
            The current :class:`Scneario` for the run.

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
    if scenario.desalination_scenario is not None:
        logger.info("Parsing clean-water tank impact information.")
        # Parse the clean-water tank costs information.
        try:
            clean_water_tank_costs: Optional[Dict[str, float]] = [
                entry[COSTS]
                for entry in tank_inputs
                if entry[NAME]
                == energy_system_inputs[ImpactingComponent.CLEAN_WATER_TANK.value]
            ][0]
        except IndexError:
            logger.error("Failed to determine clean-water tank cost information.")
            raise
        except KeyError:
            logger.error(
                "Failed to determine clean-water tank from the energy-system inputs "
                "file."
            )
            raise
        else:
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
        else:
            logger.info("Clean-water tank emission information successfully parsed.")

    else:
        clean_water_tank_costs = None
        clean_water_tank_emissions = None
        logger.info(
            "Clean-water tank disblaed in scenario file, skipping battery impact "
            "parsing."
        )

    # If clean-water is present, extract the cost and emissions information.
    if (
        scenario.desalination_scenario is not None
        and scenario.desalination_scenario.pvt_scenario.heats == HTFMode.CLOSED_HTF
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
        else:
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
        else:
            logger.info("Buffer-water tank emission information successfully parsed.")

    else:
        buffer_tank_costs = None
        buffer_tank_emissions = None
        logger.info(
            "Buffer-water tank disblaed in scenario file, skipping battery impact parsing."
        )

    if scenario.hot_water_scenario is not None:
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
        else:
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
        else:
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


def _parse_minigrid_inputs(
    convertors: Dict[str, Convertor],
    inputs_directory_relative_path: str,
    logger: Logger,
    scenario: Scenario,
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
        - convertors:
            The `list` of :class:`Convertor` instances available to the system.
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenario:
            The :class:`Scenario` being used for the run.

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
        scenario,
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
        energy_system_inputs,
        inputs_directory_relative_path,
        logger,
        scenario,
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
        scenario,
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
    if (
        scenario.desalination_scenario is not None
        or scenario.hot_water_scenario is not None
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
            scenario,
        )
        logger.info("Tank information successfully parsed.")

        (
            exchanger_costs,
            exchanger_emissions,
            exchanger_inputs,
            exchanger_inputs_filepath,
        ) = _parse_exchanger_inputs(
            energy_system_inputs, inputs_directory_relative_path, logger, scenario
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
            raise InputFileError("energy system inputs", "Water pump not defined.")

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
    if (
        scenario.hot_water_scenario is not None
        and scenario.hot_water_scenario.auxiliary_heater == AuxiliaryHeaterType.ELECTRIC
    ):
        try:
            electric_water_heater: Optional[Convertor] = convertors[
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

    if scenario.desalination_scenario is not None and minigrid.clean_water_tank is None:
        raise InputFileError(
            "scenario OR minigrid",
            "The scenario specifies a clean-water system but no clean-water tank is defined.",
        )
    if scenario.desalination_scenario is not None and minigrid.buffer_tank is None:
        raise InputFileError(
            "scenario OR minigrid",
            "The scenario specifies a desalination scenario but no buffer tank is defined.",
        )
    if (
        ResourceType.HOT_CLEAN_WATER in scenario.resource_types
        and minigrid.hot_water_tank is None
    ):
        raise InputFileError(
            "scenario OR minigrid",
            "The scenario specifies a hot-water system but no hot-water tank is defined.",
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
        - The transmission inputs relative path;
        - The costs associated with the transmitters;
        - The emissions associated with the transmitters;
        - A `dict` mapping convertor names (`str`) to :class:`transmission.Transmitter`
          instances based on the input information provided.

    """

    # Determine the conversion inputs file path.
    transmission_file_relative_path = os.path.join(
        inputs_directory_relative_path, TRANSMISSION_INPUTS_FILE
    )

    transmission_costs: Dict[str, Dict[str, float]] = {}
    transmission_emissions: Dict[str, Dict[str, float]] = {}

    # If the file exists, parse the convertors contained.
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
            except IndexError:
                logger.error(
                    "Failed to determine transmitter cost information for %s.",
                    transmitter.name,
                )
                raise
            else:
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
            except IndexError:
                logger.error(
                    "Failed to determine transmitter emission information for %s.",
                    transmitter.name,
                )
                raise
            else:
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


def parse_input_files(
    location_name: str, logger: Logger
) -> Tuple[
    List[Convertor],
    Dict[load.load.Device, pd.DataFrame],
    Minigrid,
    Dict[str, Dict[str, float]],
    Dict[str, Union[int, str]],
    Dict[str, Dict[str, float]],
    pd.DataFrame,
    Location,
    Optional[OptimisationParameters],
    Set[Optimisation],
    Scenario,
    List[Simulation],
    Dict[WaterSource, pd.DataFrame],
    Dict[str, str],
]:
    """
    Parse the various input files and return content-related information.

    Inputs:
        - location_name:
            The name of the location_name being considered.
        - logger:
            The logger to use for the run.

    Outputs:
        - A tuple containing:
            - device_utilisations,
            - diesel_inputs,
            - minigrid,
            - finance_inputs,
            - ghg_inputs,
            - grid_times,
            - optimisation_inputs,
            - optimisations, the `set` of optimisations to run,
            - scenario,
            - simulations, the `list` of simulations to run,
            - a `list` of :class:`solar.SolarPanel` instances and their children which
              contain information about the PV panels being considered,
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
    conversion_file_relative_path, convertors = _parse_conversion_inputs(
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

    # Parse the scenario input information.
    (
        desalination_scenario_inputs_filepath,
        hot_water_scenario_inputs_filepath,
        scenario,
        scenario_inputs_filepath,
    ) = _parse_scenario_inputs(inputs_directory_relative_path, logger)
    logger.info("Scenario inputs successfully parsed.")

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
        convertors, inputs_directory_relative_path, logger, scenario
    )
    logger.info("Energy-system inputs successfully parsed.")

    # Determine the available convertors.
    available_convertors: List[Convertor] = _determine_available_convertors(
        convertors, logger, minigrid, scenario
    )
    logger.info("Subset of available convertors determined.")

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

    if scenario.desalination_scenario is not None:
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

    optimisation_inputs_filepath = os.path.join(
        inputs_directory_relative_path, OPTIMISATION_INPUTS_FILE
    )
    optimisation_inputs = read_yaml(optimisation_inputs_filepath, logger)
    if not isinstance(optimisation_inputs, dict):
        raise InputFileError(
            "optimisation inputs", "Optimisation inputs is not of type `dict`."
        )
    try:
        optimisation_parameters = OptimisationParameters.from_dict(optimisation_inputs)
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
        optimisations: Set[Optimisation] = {
            Optimisation.from_dict(logger, entry)
            for entry in optimisation_inputs[OPTIMISATIONS]
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

    # Parse and collate the impact information.
    finance_inputs_filepath = os.path.join(
        inputs_directory_relative_path, FINANCE_INPUTS_FILE
    )
    # Finance input type: Dict[str, Union[float, Dict[str, float]]]
    finance_inputs = read_yaml(finance_inputs_filepath, logger)
    if not isinstance(finance_inputs, dict):
        raise InputFileError(
            "finance inputs", "Finance inputs must be of type `dict` not `list`."
        )
    logger.info("Finance inputs successfully parsed.")

    ghg_inputs_filepath = os.path.join(inputs_directory_relative_path, GHG_INPUTS_FILE)
    # Ghg data type: Dict[str, Union[float, Dict[str, float]]]
    ghg_data = read_yaml(ghg_inputs_filepath, logger)
    if not isinstance(ghg_data, dict):
        raise InputFileError(
            "ghg inputs", "GHG inputs must be of type `dict` not `list`."
        )
    logger.info("GHG inputs successfully parsed.")

    # Update the finance and GHG inputs accordingly with the PV data.
    logger.info("Updating with PV impact data.")
    finance_inputs[ImpactingComponent.PV.value] = pv_panel_costs
    ghg_data[ImpactingComponent.PV.value] = pv_panel_emissions
    logger.info("PV impact data successfully updated.")

    # Update the impact inputs with the diesel data.
    logger.info("Updating with diesel impact data.")
    finance_inputs[ImpactingComponent.DIESEL.value] = diesel_costs
    ghg_data[ImpactingComponent.DIESEL.value] = diesel_emissions
    logger.info("Diesel impact data successfully updated.")

    # Update the impact inputs with the battery data.
    logger.info("Updating with battery impact data.")
    finance_inputs[ImpactingComponent.STORAGE.value] = battery_costs
    ghg_data[ImpactingComponent.STORAGE.value] = battery_emissions
    logger.info("Battery impact data successfully updated.")

    if minigrid.pvt_panel is not None and scenario.pv_t:
        if pvt_panel_costs is None or pvt_panel_emissions is None:
            raise InternalError("Error processing PV-T panel cost and emissions.")
        finance_inputs[ImpactingComponent.PV_T.value] = pvt_panel_costs
        ghg_data[ImpactingComponent.PV_T.value] = pvt_panel_emissions
    else:
        logger.info("PV-T disblaed in scenario file, skipping PV-T impact parsing.")

    # Add transmitter impacts.
    for transmitter in transmitters:
        logger.info("Updating with %s impact data.", transmitter)
        finance_inputs[
            FINANCE_IMPACT.format(
                type=ImpactingComponent.TRANSMITTER.value, name=transmitter
            )
        ] = transmission_costs[transmitter]
        ghg_data[
            GHG_IMPACT.format(
                type=ImpactingComponent.TRANSMITTER.value, name=transmitter
            )
        ] = transmission_emissions[transmitter]
        logger.info("Transmitter %s impact data successfully updated.", transmitter)

    # Add desalination-specific impacts.
    if (
        scenario.desalination_scenario is not None
        and scenario.desalination_scenario.pvt_scenario.heats == HTFMode.CLOSED_HTF
    ):
        # Update the clean-water tank impacts.
        logger.info("Updating with clean-water tank impact data.")
        finance_inputs[
            ImpactingComponent.CLEAN_WATER_TANK.value
        ] = clean_water_tank_costs
        ghg_data[ImpactingComponent.CLEAN_WATER_TANK.value] = clean_water_tank_emissions
        logger.info("Clean-water tank impact data successfully updated.")

        # Update the buffer tank impacts.
        logger.info("Updating with buffer tank impact data.")
        if buffer_tank_costs is None or buffer_tank_emissions is None:
            raise InternalError("Error processing buffer-tank cost and emissions.")
        finance_inputs[ImpactingComponent.BUFFER_TANK.value] = buffer_tank_costs
        ghg_data[ImpactingComponent.BUFFER_TANK.value] = buffer_tank_emissions
        logger.info("Buffer tank impact data successfully updated.")

        # Update the heat-exchanger imapcts.
        logger.info("Updating with heat-exchanger impact data.")
        if exchanger_costs is None or exchanger_emissions is None:
            raise InternalError("Error processing heat-exchanger cost and emissions.")
        finance_inputs[ImpactingComponent.HEAT_EXCHANGER.value] = exchanger_costs
        ghg_data[ImpactingComponent.HEAT_EXCHANGER.value] = exchanger_emissions
        logger.info("Heat-exchanger impact data successfully updated.")

        # Include the impacts of conventional water sources.
        logger.info("Updating with conventional water-source impact data.")
        if (
            scenario.desalination_scenario is not None
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
                except KeyError:
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
                ] = conventional_source_costs

                try:
                    conventional_source_emissions: Union[float, Dict[str, float]] = [
                        entry[EMISSIONS]
                        for entry in conventional_water_source_inputs
                        if entry[NAME] == source.name
                    ][0]
                except KeyError:
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

                ghg_data[
                    f"{ImpactingComponent.CONVENTIONAL_SOURCE.value}_{source.name}"
                ] = conventional_source_emissions

    # Add hot-water-specific impacts.
    if scenario.hot_water_scenario is not None:
        # Update the hot-water tank impacts.
        logger.info("Updating with hot-water tank impact data.")
        finance_inputs[ImpactingComponent.HOT_WATER_TANK.value] = hot_water_tank_costs
        ghg_data[ImpactingComponent.HOT_WATER_TANK.value] = hot_water_tank_emissions
        logger.info("Hot-water tank impact data successfully updated.")

        # Update the diesel water-heater impacts.
        logger.info("Updating with diesel water-heater impact data.")
        finance_inputs[
            ImpactingComponent.DIESEL_WATER_HEATER.value
        ] = diesel_water_heater_costs
        ghg_data[
            ImpactingComponent.DIESEL_WATER_HEATER.value
        ] = diesel_water_heater_emissions
        logger.info("Diesel water-heater impact data successfully updated.")

    # Generate a dictionary with information about the input files used.
    input_file_info: Dict[str, str] = {
        "batteries": battery_inputs_filepath,
        "convertors": conversion_file_relative_path,
        "devices": device_inputs_filepath,
        "diesel_inputs": diesel_inputs_filepath,
        "energy_system": energy_system_inputs_filepath,
        "finance_inputs": finance_inputs_filepath,
        "generation_inputs": generation_inputs_filepath,
        "ghg_inputs": ghg_inputs_filepath,
        "grid_times": grid_times_filepath,
        "location_inputs": location_inputs_filepath,
        "optimisation_inputs": optimisation_inputs_filepath,
        "scenario": scenario_inputs_filepath,
        "simularion": simulations_inputs_filepath,
        "solar_inputs": solar_generation_inputs_filepath,
        "transmission_inputs": transmission_inputs_filepath,
    }

    if scenario.desalination_scenario is not None:
        if conventional_water_source_inputs_filepath is not None:
            input_file_info[
                "conventional_water_source_inputs"
            ] = conventional_water_source_inputs_filepath
        if tank_inputs_filepath is not None:
            input_file_info["tank_inputs"] = tank_inputs_filepath

    if (
        scenario.desalination_scenario is not None
        and scenario.desalination_scenario.pvt_scenario.heats == HTFMode.CLOSED_HTF
    ):
        input_file_info["desalination_scenario"] = desalination_scenario_inputs_filepath
        if exchanger_inputs_filepath is not None:
            input_file_info["exchanger_inputs"] = exchanger_inputs_filepath

    if scenario.hot_water_scenario is not None:
        input_file_info["hot_water_scenario"] = hot_water_scenario_inputs_filepath

    logger.debug("Input file parsing complete.")
    logger.debug(
        "Available convertors: %s",
        ", ".join([str(convertor) for convertor in available_convertors]),
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
    logger.debug("Scenario: %s", scenario)
    logger.debug("Desalination scenario: %s", scenario.desalination_scenario)
    logger.debug(
        "Simulations: %s", ", ".join([str(simulation) for simulation in simulations])
    )
    logger.debug(
        "Transmitters: %s",
        ", ".join([f"{key}: {value}" for key, value in transmitters.items()]),
    )
    logger.debug("Input file information: %s", input_file_info)

    return (
        available_convertors,
        device_utilisations,
        minigrid,
        finance_inputs,
        generation_inputs,
        ghg_data,
        grid_times,
        location,
        optimisation_parameters,
        optimisations,
        scenario,
        simulations,
        water_source_times,
        input_file_info,
    )
