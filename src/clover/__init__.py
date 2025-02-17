#!/usr/bin/python3
########################################################################################
# __init__.py - Python internals module, used to expose code here.                     #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 05/07/2021                                                             #
# License: Open source                                                                 #
########################################################################################
"""
The internals module"""

from .__main__ import (
    main,
    OPTIMISATION_OUTPUTS_FOLDER,
    OUTPUTS_FOLDER,
    SIMULATION_OUTPUTS_FOLDER,
)
from .__utils__ import (
    BColours,
    CleanWaterMode,
    Criterion,
    CUT_OFF_TIME,
    daily_sum_to_monthly_sum,
    DEFAULT_SCENARIO,
    DemandType,
    DesalinationScenario,
    dict_to_dataframe,
    DieselMode,
    DONE,
    ELECTRIC_POWER,
    EXCHANGER,
    FAILED,
    get_locations_foldername,
    get_logger,
    HEAT_CAPACITY_OF_WATER,
    HotWaterScenario,
    hourly_profile_to_daily_sum,
    HTFMode,
    InputFileError,
    InternalError,
    Inverter,
    KEROSENE_DEVICE_NAME,
    KeyResults,
    Location,
    LOCATIONS_FOLDER_NAME,
    LOGGER_DIRECTORY,
    monthly_profile_to_daily_profile,
    monthly_times_to_daily_times,
    NAME,
    open_simulation,
    OperatingMode,
    PACKAGE_NAME,
    ProgrammerJudgementFault,
    RAW_CLOVER_PATH,
    read_yaml,
    RenewableEnergySource,
    ResourceType,
    RenewablesNinjaError,
    save_simulation,
    Scenario,
    Simulation,
    SystemAppraisal,
    SystemDetails,
    ZERO_CELCIUS_OFFSET,
)
from .analysis import *
from .argparser import parse_args, validate_args
from .fileparser import (
    GENERATION_INPUTS_FILE,
    INPUTS_DIRECTORY,
    KEROSENE_TIMES_FILE,
    KEROSENE_USAGE_FILE,
    parse_input_files,
    parse_scenario_inputs,
)
from .printer import generate_optimisation_string, generate_simulation_string
