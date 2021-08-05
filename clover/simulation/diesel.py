#!/usr/bin/python3
########################################################################################
# diesel.py - Energy-system diesel module                                              #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# License: Open source                                                                 #
# Most recent update: 05/08/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
diesel.py - The energy-system's diesel module.

This module represents diesel generators within the energy system.

"""


import dataclasses

__all__ = ("DieselBackupGenerator",)


@dataclasses.dataclass
class DieselBackupGenerator:
    """
    Represents a diesel backup generator.

    .. attribute:: diesel_consumption
        The diesel consumption of the generator, measured in litres per kW produced.

    .. attribute:: minimum_load
        The minimum capacity of the generator, defined between 0 (able to operate with
        any load) and 1 (only able to operate at maximum load).

    """

    diesel_consumption: float
    minimum_load: float
