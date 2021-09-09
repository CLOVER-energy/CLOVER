#!/usr/bin/python3
########################################################################################
# conversion.py - Conversion module for CLOVER.                                        #
#                                                                                      #
# Authors: Phil Sandwell, Ben Winchester                                               #
# Copyright: Phil Sandwell, 2021                                                       #
# License: Open source                                                                 #
# Most recent update: 14/07/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
conversion.py - The conversion module of CLOVER.

This module contains functionality enabling the conversion of one energy type into
another.

"""

from logging import Logger
from typing import Any, Dict, List, Union

from ..__utils__ import (
    BColours,
    InputFileError,
    RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING,
    ResourceType,
)

__all__ = (
    "Convertor",
    "MultiInputConvertor",
    "WaterSource",
)


# Maximum output:
#   Keyword used for parsing maximum output information.
MAXIMUM_OUTPUT = "maximum_output"

# Name:
#   Keyword used for parsing convertor name information.
NAME = "name"

# Output:
#   Keyword used for parsing output information.
OUTPUT = "output"


class Convertor:
    """
    Represents a device that is able to convert one form of energy into another.

    .. attribute:: consumption
        The amount of input load which is consumed per unit output load produced.

    .. attribute:: input_resource_type
        The type of energy which is inputted into the device.

    .. attribute:: maximum_output_capacity
        The maximum capacity of the device in producing its output.

    .. attribute:: output_resource_type
        The type of energy which is outputted by the device.

    """

    def __init__(
        self,
        input_resource_consumption: Dict[ResourceType, float],
        maximum_output_capacity: float,
        name: str,
        output_resource_type: ResourceType,
    ) -> None:
        """
        Instantiate a :class:`Convertor` instance.

        Inputs:
            - consunmption:
                The amount of input load type which is consumed per unit output load
                produced.
            - input_resource_types:
                The types of load inputted to the device.
            - maximum_output_capcity:
                The maximum output capacity of the device.
            - name:
                The name of the device.
            - output_resource_type:
                The type of output produced by the device.

        """

        self.input_resource_consumption: Dict[
            ResourceType, float
        ] = input_resource_consumption
        self.maximum_output_capacity: float = maximum_output_capacity
        self.name: str = name
        self.output_resource_type: ResourceType = output_resource_type

    def __eq__(self, other) -> bool:
        """
        Returns whether two :class:`Conversion` instances are equal.

        The comparison is made on the consumption and whether their input and output
        types are the same.

        Outputs:
            - Whether the two instances are equal.

        """

        return (
            self.input_resource_consumption == other.input_resource_consumption
            and self.output_resource_type == other.output_resource_type
            and self.consumption == other.consumption
        )

    def __lt__(self, other) -> bool:
        """
        Returns whether the current instance is less than another instance.

        The comparison is made purely on the consumption.

        Outputs:
            - Whether the current instance is less than the other in consumption.

        Raises:
            - An Exception if the two instances are not of the same type and an attempt
              was made at this comparison.

        """

        if self.output_resource_type != other.output_resource_type:
            raise Exception(
                "An attempt was made to compare two conversion instances that use "
                "different output types."
            )

        return self.consumption < other.consumption

    def __repr__(self) -> str:
        """
        Returns a nice-looking `str` representing the :class:`Convertor` instance.

        Outputs:
            - A nidee-looking `str` representing the :class:`Convertor` instance.

        """

        return self.__str__()

    def __str__(self) -> str:
        """
        Returns a nice-looking `str` representing the :class:`Convertor` instance.

        Outputs:
            - A nidee-looking `str` representing the :class:`Convertor` instance.

        """

        return (
            "Convertor("
            + f"name={self.name}"
            + ", input_resource_consumption=({})".format(
                ", ".join(
                    [
                        f"{key.value}={value}"
                        for key, value in self.input_resource_consumption.items()
                    ]
                )
            )
            + f", output_resource_type = {self.output_resource_type.value}"
            + f", maximum_output_capacity = {self.maximum_output_capacity}"
            + ")"
        )

    @property
    def consumption(self) -> float:
        """
        Used only when dealing with a single input resource type.

        Outputs:
            - The consumption of the input resource type.

        """

        if len(self.input_resource_consumption) > 1:
            raise InputFileError(
                "conversion inputs",
                "Multiple inputs were defined where only one was expected on a "
                + f"convertor instance: {self.name}",
            )

        return list(self.input_resource_consumption.values())[0]


class MultiInputConvertor(Convertor):
    """
    Represents a convertor that is capable of having multiple input resource types.

    """

    def __lt__(self, other) -> bool:
        """
        Returns whether the current instance is less than another instance.

        The comparison is made purely on the consumption.

        Outputs:
            - Whether the current instance is less than the other in consumption.

        Raises:
            - An Exception if the two instances are not of the same type and an attempt
              was made at this comparison.

        """

        return (
            list(self.input_resource_consumption.values())[0]
            < list(other.input_resource_consumption.values())[0]
        )

    @classmethod
    def from_dict(cls, input_data: Dict[Union[int, str], Any], logger: Logger) -> Any:
        """
        Generates a :class:`Convertor` instance based on the input data provided.

        Inputs:
            - input_data:
                The input data, parsed from the input file.

        Outputs:
            - A :class:`Convertor` instance based on the input data.

        """

        if not all(isinstance(key, str) for key in input_data):
            raise InputFileError(
                "conversion inputs", "All conversion input keys must be of type `str`."
            )

        # Determine the input load type.
        input_resource_list: List[str] = [
            str(key)
            for key in input_data
            if key in RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING
        ]
        # Determine the output load type.
        try:
            output_resource_type = ResourceType(input_data[OUTPUT])
        except KeyError as e:
            logger.error(
                "%sOutput load type of water pump is not valid: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise Exception(
                f"{BColours.fail}Output load type invalid: {str(e)}{BColours.endc}"
            ) from None

        # Determine the power consumption of the device.
        maximum_output = input_data[MAXIMUM_OUTPUT]
        try:
            maximum_output = float(maximum_output)
        except TypeError as e:
            logger.error(
                "%sInvalid entry in conversion file, check all value types are "
                "correct: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise Exception(
                f"{BColours.fail}Invalid value type in conversion file: {str(e)}{BColours.endc}"
            ) from None

        input_resource_consumption: Dict[ResourceType, float] = {}

        for input_resource in input_resource_list:
            try:
                input_resource_consumption[
                    ResourceType(RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING[input_resource])
                ] = float(input_data[input_resource])
            except TypeError as e:
                logger.error(
                    "%sInvalid entry in conversion file, check all value types are "
                    "correct: %s%s",
                    BColours.fail,
                    str(e),
                    BColours.endc,
                )
                raise Exception(
                    f"{BColours.fail}Invalid value type in conversion file: {str(e)}{BColours.endc}"
                ) from None

        return cls(
            input_resource_consumption,
            maximum_output,
            str(input_data[NAME]),
            output_resource_type,
        )


class WaterSource(Convertor):
    """Represents a water source which takes in electricity and outputs water."""

    @classmethod
    def from_dict(cls, input_data: Dict[Union[int, str], Any], logger: Logger) -> Any:
        """
        Generates a :class:`Convertor` instance based on the input data provided.

        Inputs:
            - input_data:
                The input data, parsed from the input file.

        Outputs:
            - A :class:`Convertor` instance based on the input data.

        """

        if not all(isinstance(key, str) for key in input_data):
            raise InputFileError(
                "conversion inputs", "All conversion input keys must be of type `str`."
            )

        # Determine the input load type.
        input_resource_list: List[str] = [
            str(key)
            for key in input_data
            if key in RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING
        ]
        if len(input_resource_list) > 1:
            logger.info(
                "%sCurrently only one input is allowed for water pumps.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "conversion inputs",
                f"{BColours.fail}Currently only one load type is supported in the "
                + f"conversion inputs file.{BColours.endc}",
            )

        input_resource_type = ResourceType(
            RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING[input_resource_list[0]]
        )

        # Determine the output load type.
        try:
            output_resource_type = ResourceType(input_data[OUTPUT])
        except KeyError as e:
            logger.error(
                "%sOutput load type of water pump is not valid: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise Exception(
                f"{BColours.fail}Output load type invalid: {str(e)}{BColours.endc}"
            ) from None

        # Determine the power consumption of the device.
        maximum_output = input_data[MAXIMUM_OUTPUT]
        corresponding_input = input_data[input_resource_list[0]]
        try:
            maximum_output = float(maximum_output)
        except TypeError as e:
            logger.error(
                "%sInvalid entry in conversion file, check all value types are "
                "correct: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise Exception(
                f"{BColours.fail}Invalid value type in conversion file: {str(e)}{BColours.endc}"
            ) from None

        try:
            corresponding_input = float(corresponding_input)
        except TypeError as e:
            logger.error(
                "%sInvalid entry in conversion file, check all value types are "
                "correct: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise Exception(
                f"{BColours.fail}Invalid value type in conversion file: {str(e)}{BColours.endc}"
            ) from None

        consumption = maximum_output / corresponding_input

        return cls(
            {input_resource_type: consumption},
            maximum_output,
            str(input_data[NAME]),
            output_resource_type,
        )
