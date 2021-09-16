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


__all__ = (
    "ImpactingComponent",
    "LIFETIME",
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
    - CLEAN_WATER_TANK:
        Denotes the clean-water tank component of the system.
    - DIESEL:
        Denotes the diesel component of the system.
    - DIESEL_FUEL:
        Denotes the diesel fuel component of the system.
    - GENERAL:
        Denotes impacts generally associated with the system but not a specific
        component.
    - GRID:
        Denotes the grid component of the system.
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

    """

    BOS = "bos"
    CLEAN_WATER_TANK = "clean_water_tank"
    DIESEL = "diesel_generator"
    DIESEL_FUEL = "diesel_fuel"
    GENERAL = "general"
    GRID = "grid"
    HOUSEHOLDS = "households"
    INVERTER = "inverter"
    KEROSENE = "kerosene"
    MISC = "misc"
    PV = "pv"
    PV_T = "pv_t"
    STORAGE = "storage"
