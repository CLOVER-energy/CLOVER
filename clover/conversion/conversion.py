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
from typing import Any, Dict, List, Type, Union

from ..__utils__ import BColours, LOAD_NAME_TO_LOAD_TYPE_MAPPING, LoadType

__all__ = ("Convertor",)


class Convertor:
    """
    Represents a device that is able to convert one form of energy into another.

    .. attribute:: consumption
        The amount of input load which is consumed per unit output load produced.

    .. attribute:: input_load_type
        The type of energy which is inputted into the device.

    .. attribute:: maximum_output_capacity
        The maximum capacity of the device in producing its output.

    .. attribute:: output_load_type
        The type of energy which is outputted by the device.

    """

    def __init__(
        self,
        consumption: float,
        input_load_type: LoadType,
        maximum_output_capacity: float,
        name: str,
        output_load_type: LoadType,
    ) -> None:
        """
        Instantiate a :class:`Convertor` instance.

        Inputs:
            - consunmption:
                The amount of input load type which is consumed per unit output load
                produced.
            - input_load_type:
                The type of load inputted to the device.
            - maximum_output_capcity:
                The maximum output capacity of the device.
            - name:
                The name of the device.
            - output_load_type:
                The type of output produced by the device.

        """

        self.consumption: float = consumption
        self.input_load_type: LoadType = input_load_type
        self.maximum_output_capacity: float = maximum_output_capacity
        self.name: str = name
        self.output_load_type: LoadType = output_load_type

    def __eq__(self, other) -> bool:
        """
        Returns whether two :class:`Conversion` instances are equal.

        The comparison is made on the consumption and whether their input and output
        types are the same.

        Outputs:
            - Whether the two instances are equal.

        """

        return (
            (self.consumption == other.consumption)
            and self.input_load_type == other.input_load_type
            and self.output_load_type == other.output_load_type
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

        if (
            self.input_load_type != other.input_load_type
            or self.output_load_type != other.output_load_type
        ):
            raise Exception(
                "An attempt was made to compare two conversion instances that use different input and output types."
            )

        return self.consumption == other.consumption

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
            + f", input_load_type={self.input_load_type.value}"
            + f", output_load_type={self.output_load_type.value}"
            + f", consumption={self.consumption} units_out/unit_in"
            + f", maximum_output_capacity={self.maximum_output_capacity}"
            + ")"
        )

    @classmethod
    def from_dict(cls, input_data: Dict[str, Union[str, float]], logger: Logger) -> Any:
        """
        Generates a :class:`Convertor` instance based on the input data provided.

        Inputs:
            - input_data:
                The input data, parsed from the input file.

        Outputs:
            - A :class:`Convertor` instance based on the input data.

        """

        # Determine the input load type.
        input_load_types: List[str] = [
            key for key in input_data if key in LOAD_NAME_TO_LOAD_TYPE_MAPPING
        ]
        if len(input_load_types) > 1:
            logger.error(
                "%sCurrently only one load type is supported.%s",
                BColours.fail,
                BColours.endc,
            )
            raise Exception(
                f"{BColours.fail}Currently only one load type is supported in the "
                + f"conversion inputs file.{BColours.endc}"
            )

        input_load_type = LoadType(LOAD_NAME_TO_LOAD_TYPE_MAPPING[input_load_types[0]])

        # Determine the output load type.
        try:
            output_load_type = LoadType(input_data["output"])
        except KeyError as e:
            logger.error(
                "%sOutput load type of convertor not valid: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise Exception(
                f"{BColours.fail}Output load type invalid: {str(e)}{BColours.endc}"
            )

        # Determine the power consumption of the device.
        maximum_output = input_data["maximum_output"]
        corresponding_input = input_data[input_load_types[0]]
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
            )

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
            )

        consumption = maximum_output / corresponding_input

        return cls(
            consumption,
            input_load_type,
            maximum_output,
            str(input_data["name"]),
            output_load_type,
        )
