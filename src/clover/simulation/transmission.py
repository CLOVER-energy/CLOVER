#!/usr/bin/python3
########################################################################################
# transmission.py - Transmission module.                                               #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2020                                                      #
# Date created: 08/11/2021                                                             #
# License: Open source                                                                 #
# Most recent update: 08/11/2021                                                       #
########################################################################################
"""
transmission.py - The transmission module for CLOVER.

CLOVER considers the transportation of different media around the minigrid. This module
is concerned with the modelling and consideration of these aspects of the energy system.

"""

import dataclasses

from logging import Logger
from typing import Any, Dict, List

from ..__utils__ import (
    BColours,
    InputFileError,
    NAME,
    RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING,
    ResourceType,
)

__all__ = ("Transmitter",)


# Maximum throughput:
#   The maximum throughput through the transmitter.
MAXIMUM_THROUGHPUT: str = "maximum_throughput"

# Transmits:
#   Keyword used for parsing the material transmitted by the transmitter.
TRANSMITS: str = "transmits"


@dataclasses.dataclass
class Transmitter:
    """
    Represents a transmitter of a resource within the minigrid system.

    .. attribute:: consumption
        The consumption of the :class:`Transmitter`.

    .. attribute:: name
        The name of the :class:`Transmitter`.

    .. attribute:: power_source_material
        The :class:`ResourceType` which is consumed to power the :class:`Tranismitter`.

    .. attribute:: throughput
        The maximum throughput of the :class:`Transmitter`.

    .. attribute:: transmission_material
        The :class:`ResourceType` being conveyed by the transmitter.

    """

    consumption: float
    name: str
    power_source_material: ResourceType
    throughput: float
    transmission_material: ResourceType

    def __hash__(self) -> int:
        """
        Return a unique identifier for the device.

        Outputs:
            A unique identifier for the device.

        """

        return hash(self.__str__())

    def __str__(self) -> str:
        """
        Return a nice-looking output for the device.

        Outputs:
            - A nice-looking string representation for the device.

        """

        representation_string = (
            "Transmitter("
            + f"name={self.name} transmitting {self.transmission_material}, "
            + f"conusming {self.consumption} {self.power_source_material}, "
            + f"throughput={self.throughput}"
            + ")"
        )

        return representation_string

    @classmethod
    def from_dict(cls, input_data: Dict[str, Any], logger: Logger) -> Any:
        """
        Processes input data to generate a :class:`Transmitter` instance.

        Inputs:
            - input_data:
                The transmitter input data extracted from the transmission input file.

        Outputs:
            - The :class:`Transmitter` instancce based on the input data.

        """

        # Determine the input load type.
        input_resource_list: List[str] = [
            str(key)
            for key in input_data
            if key in RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING
        ]
        if len(input_resource_list) > 1:
            logger.error(
                "%sTransmitters can only be powered by a single resource.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "transmission inputs",
                "Transmitters can only be powered by a single resource.",
            )

        # Determine the consumption of this resource.
        input_resource_consumption: Dict[ResourceType, float] = {}
        for input_resource in input_resource_list:
            try:
                input_resource_consumption[
                    ResourceType(RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING[input_resource])
                ] = float(input_data[input_resource])
            except TypeError as e:
                logger.error(
                    "%sInvalid entry in transmission file, check all value types are "
                    "correct: %s%s",
                    BColours.fail,
                    str(e),
                    BColours.endc,
                )
                raise InputFileError(
                    "transmission inputs",
                    f"Invalid value type in transmission file: {str(e)}",
                ) from None

        # Determine the single resource type allowed for the transmitter.
        input_resource = input_resource_list[0]

        consumption = input_resource_consumption[
            RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING[input_resource]
        ]

        return cls(
            consumption,
            input_data[NAME],
            ResourceType(RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING[input_resource]),
            input_data[MAXIMUM_THROUGHPUT],
            input_data[TRANSMITS],
        )
