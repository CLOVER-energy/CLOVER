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

import pandas as pd  # type: ignore  # pylint: disable=import-error

from sklearn.linear_model._coordinate_descent import Lasso

from . import load
from .generation import solar
from .impact.finance import COSTS, ImpactingComponent
from .impact.ghgs import EMISSIONS

from .__utils__ import (
    BColours,
    DesalinationScenario,
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

# Electric model file:
#   The relative path to the electric model file.
ELECTRIC_MODEL_FILE: str = os.path.join("src", "best_electric_tree.sav")

# Energy-system inputs file:
#   The relative path to the energy-system-inputs file.
ENERGY_SYSTEM_INPUTS_FILE: str = os.path.join("simulation", "energy_system.yaml")

# Exchanger:
#   Keyword used for parsing heat-exchanger information.
EXCHANGER: str = "heat_exchanger"

# Exchangers:
#   Keyword used for parsing heat-exchanger information.
EXCHANGERS: str = "exchangers"

# Exchanger inputs file:
#    The relative path to the heat-exchanger-inputs file.
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
GRID_INPUTS_FILE: str = os.path.join("generation", "grid_inputs.csv")

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
THERMAL_MODEL_FILE: str = os.path.join("src", "best_thermal_tree.sav")


def _determine_available_convertors(
    convertors: Dict[str, Convertor], logger: Logger, scenario: Scenario
) -> List[Convertor]:
    """
    Determines the available :class:`Convertor` instances based on the :class:`Scenario`

    Inputs:
        - convertors:
            The :class:`Convertor` instances defined, parsed from the conversion inputs
            file.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenario:
            The :class:`Scenario` to use for the run.

    Outputs:
        - A `list` of :class:`Convertor` instances available to the system.

    """

    # Determine the available convertors from the scenarios file.
    if ResourceType.CLEAN_WATER in scenario.resource_types:
        available_convertors: List[Convertor] = []

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
    # Otherwise, there are no convertors available.
    else:
        available_convertors = []

    return available_convertors


def _parse_battery_inputs(
    energy_system_inputs: Dict[str, Any],
    inputs_directory_relative_path: str,
    logger: Logger,
    scenario: Scenario,
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float], str]:
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
            battery_costs = [
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
            battery_emissions = [
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
        logger.info(
            "Battery disblaed in scenario file, skipping battery impact parsing."
        )

    return battery_costs, battery_emissions, battery_inputs, battery_inputs_filepath


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
        logger.info("No conversion file, skipping convertor parsing.")

    return conversion_file_relative_path, convertors


def _parse_diesel_inputs(
    energy_system_inputs: Dict[str, Any],
    inputs_directory_relative_path: str,
    logger: Logger,
) -> Tuple[Dict[str, float], Dict[str, float], DieselGenerator, str]:
    """
    Parses the diesel inputs file.

    Inputs:
        - energy_system_inputs:
            The un-processed energy-system input information.
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.

    Outputs:
        A `tuple` containing:
        - The path to the diesel inputs file;
        - The diesel-generator cost information;
        - The diesel-generator emissions information;
        - The diesel generator to use for the run.

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
            DieselGenerator(
                entry["diesel_consumption"], entry["minimum_load"], entry[NAME]
            )
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
            "No diesel generator was specified. Use the `diesel_generator` keyword to "
            "select a valid diesel generator.",
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

    return diesel_costs, diesel_emissions, diesel_generator, diesel_inputs_filepath


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
    devices: Set[load.load.Device] = {
        load.load.Device.from_dict(entry)
        for entry in read_yaml(
            device_inputs_filepath,
            logger,
        )
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
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float], str]:
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
    if scenario.desalination_scenario.pvt_scenario.heats == HTFMode.CLOSED_HTF:
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
                pkgutil.get_data(PACKAGE_NAME, THERMAL_MODEL_FILE)
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
                pkgutil.get_data(PACKAGE_NAME, ELECTRIC_MODEL_FILE)
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
) -> Tuple[str, Scenario, str]:
    """
    Parses the scenario input files.

    Inputs:
        - inputs_directory_relative_path:
            The relative path to the inputs folder directory.
        - logger:
            The :class:`logging.Logger` to use for the run.

    Outputs:
        - The desalination inputs filepath;
        - The :class:`Scenario` to use for the run;
        - The scenario inputs filepath.

    """

    desalination_scenario_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        DESALINATION_SCENARIO_INPUTS_FILE,
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
            desalination_scenario: DesalinationScenario = (
                DesalinationScenario.from_dict(desalination_scenario_inputs, logger)
            )
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
        logger.info("No desalination scenario provided, skipping.")

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
            desalination_scenario, logger, scenario_inputs
        )
    except Exception as e:
        logger.error(
            "%sError generating scenario from inputs file: %s%s",
            BColours.fail,
            str(e),
            BColours.endc,
        )
        raise

    return desalination_scenario_inputs_filepath, scenario, scenario_inputs_filepath


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
        pv_panel: solar.PVPanel = [
            panel  # type: ignore
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
            pvt_panel: Optional[solar.HybridPVTPanel] = [
                panel  # type: ignore
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
        else:
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
    Dict[str, float],
    Dict[str, float],
    Dict[str, float],
    Dict[str, float],
    Dict[str, Any],
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
    if ResourceType.CLEAN_WATER in scenario.resource_types:
        logger.info("Parsing clean-water tank impact information.")

        # Parse the clean-water tank costs information.
        try:
            clean_water_tank_costs = [
                entry[COSTS]
                for entry in tank_inputs
                if entry[NAME]
                == energy_system_inputs[ImpactingComponent.CLEAN_WATER_TANK.value]
            ][0]
        except IndexError:
            logger.error("Failed to determine clean-water tank cost information.")
            raise
        else:
            logger.info("Clean-water tank cost information successfully parsed.")

        # Parse the clean-water tank emissions information.
        try:
            clean_water_tank_emissions = [
                entry[EMISSIONS]
                for entry in tank_inputs
                if entry[NAME]
                == energy_system_inputs[ImpactingComponent.CLEAN_WATER_TANK.value]
            ][0]
        except IndexError:
            logger.error("Failed to determine clean-water tank emission information.")
            raise
        else:
            logger.info("Clean-water tank emission information successfully parsed.")

    else:
        logger.info(
            "Clean-water tank disblaed in scenario file, skipping battery impact parsing."
        )

    # If clean-water is present, extract the cost and emissions information.
    if scenario.desalination_scenario.pvt_scenario.heats == HTFMode.CLOSED_HTF:
        logger.info("Parsing hot-water tank impact information.")

        # Parse the clean-water tank costs information.
        try:
            hot_water_tank_costs = [
                entry[COSTS]
                for entry in tank_inputs
                if entry[NAME]
                == energy_system_inputs[ImpactingComponent.HOT_WATER_TANK.value]
            ][0]
        except IndexError:
            logger.error("Failed to determine hot-water tank cost information.")
            raise
        else:
            logger.info("HOt-water tank cost information successfully parsed.")

        # Parse the clean-water tank emissions information.
        try:
            hot_water_tank_emissions = [
                entry[EMISSIONS]
                for entry in tank_inputs
                if entry[NAME]
                == energy_system_inputs[ImpactingComponent.HOT_WATER_TANK.value]
            ][0]
        except IndexError:
            logger.error("Failed to determine hot-water tank emission information.")
            raise
        else:
            logger.info("Hot-water tank emission information successfully parsed.")

    else:
        logger.info(
            "Hot-water tank disblaed in scenario file, skipping battery impact parsing."
        )

    return (
        clean_water_tank_costs,
        clean_water_tank_emissions,
        hot_water_tank_costs,
        hot_water_tank_emissions,
        tank_inputs,
        tank_inputs_filepath,
    )


def _parse_minigrid_inputs(
    inputs_directory_relative_path: str,
    logger: Logger,
    scenario: Scenario,
) -> Tuple[
    Dict[str, float],
    Dict[str, float],
    str,
    Dict[str, float],
    Dict[str, float],
    Dict[str, float],
    Dict[str, float],
    str,
    str,
    Dict[str, float],
    Dict[str, float],
    str,
    Dict[str, float],
    Dict[str, float],
    Minigrid,
    Dict[str, float],
    Dict[str, float],
    Dict[str, float],
    Dict[str, float],
    str,
    str,
]:
    """
    Parses the energy-system-related input files.

    Inputs:
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
        - Clean water costs,
        - Clean water emissions,
        - Diesel costs,
        - Diesel emissions,
        - Diesel input filepath,
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
    (
        diesel_costs,
        diesel_emissions,
        diesel_generator,
        diesel_inputs_filepath,
    ) = _parse_diesel_inputs(
        energy_system_inputs,  # type: ignore
        inputs_directory_relative_path,
        logger,
    )
    logger.info("Diesel generator information successfully parsed.")

    (
        pv_panel,
        pv_panel_costs,
        pv_panel_emissions,
        pvt_panel,
        pvt_panel_costs,
        pvt_panel_emissions,
        solar_generation_inputs_filepath,
    ) = _parse_solar_inputs(
        energy_system_inputs,  # type: ignore
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
        energy_system_inputs,  # type: ignore
        inputs_directory_relative_path,
        logger,
        scenario,
    )
    logger.info("Battery information successfully parsed.")

    (
        clean_water_tank_costs,
        clean_water_tank_emissions,
        hot_water_tank_costs,
        hot_water_tank_emissions,
        tank_inputs,
        tank_inputs_filepath,
    ) = _parse_tank_inputs(
        energy_system_inputs,  # type: ignore
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

    minigrid = Minigrid.from_dict(
        diesel_generator,
        energy_system_inputs,  # type: ignore
        pv_panel,
        pvt_panel,
        battery_inputs,  # type: ignore
        exchanger_inputs,  # type: ignore
        tank_inputs,  # type: ignore
    )

    return (
        battery_costs,
        battery_emissions,
        battery_inputs_filepath,
        clean_water_tank_costs,
        clean_water_tank_emissions,
        diesel_costs,
        diesel_emissions,
        diesel_inputs_filepath,
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
            - grid_inputs,
            - optimisation_inputs,
            - optimisations, the `set` of optimisations to run,
            - scenario,
            - simulations, the `list` of simulations to run,
            - a `list` of :class:`solar.SolarPanel` instances and their children which
              contain information about the PV panels being considered,
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
        scenario,
        scenario_inputs_filepath,
    ) = _parse_scenario_inputs(inputs_directory_relative_path, logger)
    logger.info("Scenario inputs successfully parsed.")

    # Determine the available convertors.
    available_convertors: List[Convertor] = _determine_available_convertors(
        convertors, logger, scenario
    )

    # Parse the energy-system input information.
    (
        battery_costs,
        battery_emissions,
        battery_inputs_filepath,
        clean_water_tank_costs,
        clean_water_tank_emissions,
        diesel_costs,
        diesel_emissions,
        diesel_inputs_filepath,
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
    ) = _parse_minigrid_inputs(inputs_directory_relative_path, logger, scenario)
    logger.info("Energy-system inputs successfully parsed.")

    generation_inputs_filepath = os.path.join(
        inputs_directory_relative_path, GENERATION_INPUTS_FILE
    )
    generation_inputs: Dict[str, Union[int, str]] = read_yaml(  # type: ignore
        generation_inputs_filepath, logger
    )
    logger.info("Generation inputs successfully parsed.")

    grid_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        GRID_INPUTS_FILE,
    )
    with open(
        grid_inputs_filepath,
        "r",
    ) as grid_inputs_file:
        grid_inputs: pd.DataFrame = pd.read_csv(
            grid_inputs_file,
            index_col=0,
        )
    logger.info("Grid inputs successfully parsed.")

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
    finance_inputs: Dict[str, Union[float, Dict[str, float]]] = read_yaml(  # type: ignore
        finance_inputs_filepath, logger
    )
    if not isinstance(finance_inputs, dict):
        raise InputFileError(
            "finance inputs", "Finance inputs must be of type `dict` not `list`."
        )
    logger.info("Finance inputs successfully parsed.")

    ghg_inputs_filepath = os.path.join(inputs_directory_relative_path, GHG_INPUTS_FILE)
    ghg_data: Dict[str, Any] = read_yaml(ghg_inputs_filepath, logger)  # type: ignore
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
        finance_inputs[ImpactingComponent.PV_T.value] = pvt_panel_costs
        ghg_data[ImpactingComponent.PV_T.value] = pvt_panel_emissions
    else:
        logger.info("PV-T disblaed in scenario file, skipping PV-T impact parsing.")

    logger.info("Updating with clean-water tank impact data.")
    finance_inputs[ImpactingComponent.CLEAN_WATER_TANK.value] = clean_water_tank_costs
    ghg_data[ImpactingComponent.CLEAN_WATER_TANK.value] = clean_water_tank_emissions
    logger.info("Clean-water tank impact data successfully updated.")

    if scenario.desalination_scenario.pvt_scenario.heats == HTFMode.CLOSED_HTF:
        logger.info("Updating with hot-water tank impact data.")
        finance_inputs[ImpactingComponent.HOT_WATER_TANK.value] = hot_water_tank_costs
        ghg_data[ImpactingComponent.HOT_WATER_TANK.value] = hot_water_tank_emissions
        logger.info("Hot-water tank impact data successfully updated.")

        logger.info("Updating with heat-exchanger impact data.")
        finance_inputs[ImpactingComponent.HEAT_EXCHANGER.value] = exchanger_costs
        ghg_data[ImpactingComponent.HEAT_EXCHANGER.value] = exchanger_emissions
        logger.info("Heat-exchanger impact data successfully updated.")

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
        "grid_inputs": grid_inputs_filepath,
        "location_inputs": location_inputs_filepath,
        "optimisation_inputs": optimisation_inputs_filepath,
        "scenario": scenario_inputs_filepath,
        "simularion": simulations_inputs_filepath,
        "solar_inputs": solar_generation_inputs_filepath,
    }

    if ResourceType.CLEAN_WATER in scenario.resource_types:
        input_file_info["tank_inputs"] = tank_inputs_filepath

    if scenario.desalination_scenario.pvt_scenario.heats == HTFMode.CLOSED_HTF:
        input_file_info["desalination_scenario"] = desalination_scenario_inputs_filepath
        input_file_info["exchanger_inputs"] = exchanger_inputs_filepath

    logger.debug("Input file parsing complete.")
    logger.debug(
        "Available convertors: %s",
        ", ".join([str(convertor) for convertor in available_convertors]),
    )
    logger.debug("Devices: %s", ", ".join([str(device) for device in devices]))
    logger.debug("Energy system/minigrid: %s", str(minigrid)),
    logger.debug("Financial input information: %s", finance_inputs)
    logger.debug("GHG input information: %s", ghg_data)
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
    logger.debug("Input file information: %s", input_file_info)

    return (
        available_convertors,
        device_utilisations,
        minigrid,
        finance_inputs,
        generation_inputs,
        ghg_data,
        grid_inputs,
        location,
        optimisation_parameters,
        optimisations,
        scenario,
        simulations,
        input_file_info,
    )
