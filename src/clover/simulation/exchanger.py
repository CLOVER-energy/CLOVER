#!/usr/bin/python3
########################################################################################
# exchanger.py - Heat-exchanger module for CLOVER.                                     #
#                                                                                      #
# Authors: Phil Sandwell, Ben Winchester                                               #
# Copyright: Phil Sandwell, 2018                                                       #
# Date created: 25/10/2021                                                             #
# License: Open source                                                                 #
#                                                                                      #
# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
The exchanger module for CLOVER.

This module represents the heat exchanger within CLOVER energy systems. The heat
exchanger is usually located within the hot-water tank, but CLOVER may access the
heat-exchanger related information from anywhere within CLOVER.

"""

import dataclasses

from typing import Any, Dict

from ..__utils__ import NAME

__all__ = ("Exchanger",)


# Efficiency:
#   Keyword used to parse the efficiency of the heat exchanger.
EFFICIENCY: str = "efficiency"


@dataclasses.dataclass
class Exchanger:
    """
    Represents a physical heat exchanger within a hot-water tank.

    .. attribute:: efficiency
        The efficiency of the heat exchanger, defined between 0 and 1.

    """

    efficiency: float
    name: str

    def __repr__(self) -> str:
        """
        Returns a nice representation of the heat exchanger.

        :return:
            A `str` giving a nice representation of the heat exchanger.

        """

        return f"Exchanger(name={self.name}, efficiency={self.efficiency})"

    @classmethod
    def from_dict(cls, exchanger_inputs: Dict[str, Any]) -> Any:
        """
        Instantiate a :class:`Exchanger` based on the input information.

        Inputs:
            - exchanger_inputs:
                The exchanger input informaiton.

        Outputs:
            - A :class:`Exchanger` instance.

        """

        return cls(exchanger_inputs[EFFICIENCY], exchanger_inputs[NAME])
