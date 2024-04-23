#!/usr/bin/python3
########################################################################################
# __utils__.py - CLOVER Impact Utility module.                                         #
#                                                                                      #
# Author: Phil Sandwell, Ben Winchester                                                #
# Copyright: Phil Sandwell, 2018                                                       #
# Date created: 24/08/2021                                                             #
#                                                                                      #
# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
__utils__.py - Utility module for CLOVER's Impact Component.

The utility module contains functionality which is used by the impact component modules,
namely the GHG and finance impact modules.

"""

import enum

from ..__utils__ import (
    CleanWaterMode,
    EXCHANGER,
    ProgrammerJudgementFault,
    ResourceType,
    Scenario,
    TechnicalAppraisal,
)

__all__ = (
    "ImpactingComponent",
    "LIFETIME",
    "update_diesel_costs",
)

# Lifetime:
#   Keyword to denote the lifetime of a component.
LIFETIME = "lifetime"

# Size increment:
#   Keyword to denote increments in the size of a component.
SIZE_INCREMENT = "size_increment"


class ImpactingComponent(enum.Enum):
    """
    Used to keep tracek of components within the systems that have associated impacts.

    - BOS:
        Denotes the balance-of-systems aspect of the system.

    - BUFFER_TANK:
        Denotes the buffer tank component of the system.

    - CLEAN_WATER_TANK:
        Denotes the clean-water tank component of the system.

    - CONVENTIONAL_SOURCE:
        Denotes conventional sources which would be utilised during minigrid supply
        downtimes.

    - CONVERTER:
        Denotes a component of the system responsible for the conversion of one
        resource type into another.

    - DIESEL:
        Denotes the diesel component of the system.

    - DIESEL_FUEL:
        Denotes the diesel fuel component of the system.

    - DIESEL_WATER_HEATER:
        Denotes the diesel water heater component of the system.

    - ELECTRIC_WATER_HEATER:
        Denotes the electric water heater component of the system.

    - GENERAL:
        Denotes impacts generally associated with the system but not a specific
        component.

    - GRID:
        Denotes the grid component of the system.

    - HEAT_EXCHANGER:
        Denotes the heat exchanger component of the system.

    - HOT_WATER_TANK:
        Denotes the hot-water tank component of the system.

    - HOUSEHOLDS:
        Denotes households.

    - INVERTER:
        Denotes the inverter component of the system.

    - KEROSENE:
        Denotes the kerosene component of the system.

    - MISC:
        Denotes misc. aspects of the system.

    - PV:
        Denotes the PV component of the system.

    - PV_T:
        Denotes the PV-T component of the system.

    - STORAGE:
        Denotes the storage component of the system.

    - TRANSMITTER:
        Denotes a component of the system responsible for transmitting one resource type
        at the expense of another.

    """

    BOS = "bos"
    BUFFER_TANK = "buffer_tank"
    CLEAN_WATER_TANK = "clean_water_tank"
    CONVENTIONAL_SOURCE = "conventional_source"
    CONVERTER = "converter"
    DIESEL = "diesel_generator"
    DIESEL_FUEL = "diesel_fuel"
    DIESEL_WATER_HEATER = "diesel_water_heater"
    ELECTRIC_WATER_HEATER = "electric_water_heater"
    GENERAL = "general"
    GRID = "grid"
    HEAT_EXCHANGER = EXCHANGER
    HOUSEHOLDS = "households"
    HOT_WATER_TANK = "hot_water_tank"
    INVERTER = "inverter"
    KEROSENE = "kerosene"
    MISC = "misc"
    PV = "pv"
    PV_T = "pv_t"
    STORAGE = "storage"
    TRANSMITTER = "transmitter"


def update_diesel_costs(
    diesel_impact: float,
    scenario: Scenario,
    subsystem_impacts: dict[ResourceType, float],
    technical_appraisal: TechnicalAppraisal,
) -> None:
    """
    Calculates the diesel costs associated with each subsystem.

    Depending on how the system is operating, various resources will use/won't use the
    diesel electric generators. As such, these costs need to be split among the various
    :class:`ResourceType`s depending on the scenario and the power consumed by each.

    Inputs:
        - diesel_impact:
            The impact of the diesel system which is being split amongst the various
            :class:`ResourceType` subsystems.
        - scenario:
            The scenario for the run.
        - subsystem_impacts:
            The impacts on the subsystem so far.
        - technical_appraisal:
            The :class:`TechnicalAppraisal` of the system that has just run.

    """

    if technical_appraisal.power_consumed_fraction is None:
        raise ProgrammerJudgementFault(
            "impact.__utils__",
            "No power consumed fraction on technical appraisal despite being needed.",
        )

    if (
        scenario.desalination_scenario is not None
        and scenario.desalination_scenario.clean_water_scenario.mode
        == CleanWaterMode.PRIORITISE
    ):
        # Diesel costs to be split equally among all resource types.
        subsystem_impacts[ResourceType.CLEAN_WATER] += (
            diesel_impact
        ) * technical_appraisal.power_consumed_fraction[ResourceType.CLEAN_WATER]
        subsystem_impacts[ResourceType.ELECTRIC] += (
            diesel_impact
        ) * technical_appraisal.power_consumed_fraction[ResourceType.ELECTRIC]
        subsystem_impacts[ResourceType.DIESEL] += (
            diesel_impact
            * technical_appraisal.power_consumed_fraction[ResourceType.HOT_CLEAN_WATER]
        )
    else:
        # Diesel costs to only be split amongst electric and hot-water resource
        # types.
        total_diesel_frac: float = (
            technical_appraisal.power_consumed_fraction[ResourceType.ELECTRIC]
            + technical_appraisal.power_consumed_fraction[ResourceType.HOT_CLEAN_WATER]
        )
        subsystem_impacts[ResourceType.ELECTRIC] += (
            diesel_impact
            * technical_appraisal.power_consumed_fraction[ResourceType.ELECTRIC]
            / total_diesel_frac
        )
        subsystem_impacts[ResourceType.HOT_CLEAN_WATER] += (
            diesel_impact
            * technical_appraisal.power_consumed_fraction[ResourceType.HOT_CLEAN_WATER]
            / total_diesel_frac
        )
