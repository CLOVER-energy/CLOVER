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
from typing import Any, Dict, List, Optional

from ..__utils__ import (
    BColours,
    HTFMode,
    InputFileError,
    NAME,
    RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING,
    ResourceType,
)
from ..impact.__utils__ import WasteProduct

__all__ = (
    "Converter",
    "MultiInputConverter",
    "ThermalDesalinationPlant",
    "WaterSource",
)


# Heat source:
#   Keyword used for parsing the heat source of thermal desalination plants.
HEAT_SOURCE: str = "heat_source"

# Maximum feedwater input temperature:
#   Keyword used for parsing maximum feedwater temperature information.
MAXIMUM_FEEDWATER_TEMPERATURE: str = "max_feedwater_temperature"

# Maximum htf input temperature:
#   Keyword used for parsing maximum htf temperature information.
MAXIMUM_HTF_TEMPERATURE: str = "max_htf_temperature"

# Maximum output:
#   Keyword used for parsing maximum output information.
MAXIMUM_OUTPUT: str = "maximum_output"

# Maximum feedwater input temperature:
#   Keyword used for parsing maximum feedwater temperature information.
MINIMUM_FEEDWATER_TEMPERATURE: str = "min_feedwater_temperature"

# Minimum water input temperature:
#   Keyword used for parsing minimum htf temperature information.
MINIMUM_HTF_TEMPERATURE: str = "min_htf_temperature"

# Minimum output:
#   Keyword used for parsing minimum output information.
MINIMUM_OUTPUT: str = "minimum_output"

# Output:
#   Keyword used for parsing output information.
OUTPUT: str = "output"

# Waste products:
#   Keyword used for parsing waste-product information.
WASTE_PRODUCTS: str = "waste_products"


def _parse_waste_production(
    logger: Logger, name: str, waste_product_inputs: Dict[str, float]
) -> Dict[WasteProduct, float]:
    """
    Parses waste-product information.

    Inputs:
        - logger:
            The :class:`logging.Logger` to use for the run.
        - name:
            The name of the :class:`Converter` being parsed.
        - waste_product_inputs:
            The waste-product input information for the :class:`Converter` being parsed.

    Outputs:
        - A mapping between the :class:`WasteProduct` and its associated output
        produced.

    """

    waste_production: Dict[WasteProduct, float] = {}

    for waste_product, amount_produced in waste_product_inputs.items():
        try:
            waste_production[WasteProduct(waste_product)] = amount_produced
        except ValueError:
            logger.error(
                "%sInvalid waste product specified: '%s'. Valid values are %s.%s",
                BColours.fail,
                waste_product,
                ", ".join(e.value for e in WasteProduct),
                BColours.endc,
            )
            raise InputFileError(
                "conversion inputs",
                f"Converter {name} has invalid waste-product '{waste_product}'. Valid "
                + f"waste products are {', '.join(str(e.value) for e in WasteProduct)}.",
            ) from None

        # Type check the value generated.
        if not isinstance(waste_production[WasteProduct(waste_product)], (int, float)):
            logger.error(
                "%sInvalid value for waste-product '%s' for plant '%s': "
                "value must be of type float.%s",
                BColours.fail,
                waste_product,
                BColours.endc,
            )
            raise InputFileError(
                "conversion inputs",
                f"Converter {name} has invalid waste-product type.",
            )

    return waste_production


class Converter:
    """
    Represents a device that is able to convert one from of energy into another.

    .. attribute:: consumption
        The amount of input load which is consumed per unit output load produced.

    .. attribute:: input_resource_consumption
        A mapping between :class:`ResourceType` and the amount of input required, from
        that :class:`ResourceType`, when the :class:`Converter` is operating at its
        maximum throughput.

    .. attribute:: maximum_output_capacity
        The maximum capacity of the device in producing its output.

    .. attribute:: name
        The name of the :class:`Converter` instance.

    .. attribute:: output_resource_type
        The type of energy which is outputted by the device.

    .. attribute:: waste_production
        A mapping between :class:`WasteProduct` instances and the amount of each waste
        product that is produced per unit output.

    """

    def __init__(
        self,
        input_resource_consumption: Dict[ResourceType, float],
        maximum_output_capacity: float,
        name: str,
        output_resource_type: ResourceType,
        waste_production: Optional[Dict[WasteProduct, float]] = None,
    ) -> None:
        """
        Instantiate a :class:`Converter` instance.

        Inputs:
            - input_resource_types:
                The types of load inputted to the converter.
            - maximum_output_capcity:
                The maximum output capacity of the converter.
            - name:
                The name of the converter.
            - output_resource_type:
                The type of output produced by the converter.
            - waste_production:
                The waste production of the converter.

        """

        self.input_resource_consumption: Dict[
            ResourceType, float
        ] = input_resource_consumption
        self.maximum_output_capacity: float = maximum_output_capacity
        self.name: str = name
        self.output_resource_type: ResourceType = output_resource_type
        self.waste_production: Dict[WasteProduct, float] = (
            waste_production if waste_production is not None else {}
        )

    def __eq__(self, other: Any) -> bool:
        """
        Returns whether two :class:`Conversion` instances are equal.

        The comparison is made on the consumption and whether their input and output
        types are the same.

        Outputs:
            - Whether the two instances are equal.

        """

        return bool(
            self.input_resource_consumption == other.input_resource_consumption
            and self.output_resource_type == other.output_resource_type
            and self.consumption == other.consumption
            and self.waste_production == other.waste_production
        )

    def __hash__(self) -> int:
        """
        Returns a unique `int` identifying the :class:`Converter` instance.

        Outputs:
            A unique `int` identifying the :class:`Converter` instance.

        """

        consumption_dict = dict(enumerate(self.input_resource_consumption.values()))
        consumption_int = sum(
            value * 10 ** (5 * index) for index, value in consumption_dict.items()
        )

        return hash((consumption_int + self.maximum_output_capacity) ** 2)

    def __lt__(self, other: Any) -> bool:
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

        return bool(self.consumption < other.consumption)

    def __repr__(self) -> str:
        """
        Returns a nice-looking `str` representing the :class:`Converter` instance.

        Outputs:
            - A nidee-looking `str` representing the :class:`Converter` instance.

        """

        return self.__str__()

    def __str__(self) -> str:
        """
        Returns a nice-looking `str` representing the :class:`Converter` instance.

        Outputs:
            - A nidee-looking `str` representing the :class:`Converter` instance.

        """

        input_resource_consumption = ", ".join(
            [
                f"{key.value}={value}"
                for key, value in self.input_resource_consumption.items()
            ]
        )

        return (
            "Converter("
            + f"name={self.name}"
            + f", input_resource_consumption=({input_resource_consumption})"
            + f", output_resource_type = {self.output_resource_type.value}"
            + f", maximum_output_capacity = {self.maximum_output_capacity}"
            + (
                f", waste_production = {self.waste_production}"
                if len(self.waste_production) > 0
                else ""
            )
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
                + f"converter instance: {self.name}",
            )

        return list(self.input_resource_consumption.values())[0]

    @property
    def value(self) -> str:
        """
        Used to mimic the behaviour of enums.

        In order to utilise :class:`Converter` instances in the same way that
        :class:`enum.Enum` instances are, it is necessary to include a '.value'
        property.

        Outputs:
            - A `str` giving the value associated with the :class:`Converter` instance,
              i.e., its name.

        """

        return self.name


class MultiInputConverter(Converter):
    """
    Represents a converter that is capable of having multiple input resource types.

    """

    def __lt__(self, other: Any) -> bool:
        """
        Returns whether the current instance is less than another instance.

        The comparison is made purely on the consumption.

        Outputs:
            - Whether the current instance is less than the other in consumption.

        Raises:
            - An Exception if the two instances are not of the same type and an attempt
              was made at this comparison.

        """

        return bool(
            list(self.input_resource_consumption.values())[0]
            < list(other.input_resource_consumption.values())[0]
        )

    @classmethod
    def from_dict(cls, input_data: Dict[str, Any], logger: Logger) -> Any:
        """
        Generates a :class:`MultiInputConverter` instance based on the input data.

        Inputs:
            - input_data:
                The input data, parsed from the input file.

        Outputs:
            - A :class:`MultiInputConverter` instance based on the input data.

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
                raise InputFileError(
                    "conversion inputs",
                    f"Invalid value type in conversion file: {str(e)}",
                ) from None

        waste_production: Dict[WasteProduct, float] = {}

        if WASTE_PRODUCTS in input_data:
            waste_production = _parse_waste_production(
                logger, input_data[NAME], input_data[WASTE_PRODUCTS]
            )

        return cls(
            input_resource_consumption,
            maximum_output,
            str(input_data[NAME]),
            output_resource_type,
            waste_production,
        )


class ThermalDesalinationPlant(MultiInputConverter):
    """
    Represents a thermal desalination plant.

    .. attribute:: htf_mode
        The mode of inputting HTF to the thermal desalination plant.

    .. attribute:: maximum_feedwater_temperature
        The maximum temperature of feedwater allowed by the plant, measured in degrees
        Celcius.

    .. attribute:: maximum_htf_temperature
        The maximum temperature of HTF allowed by the plant, measured in degrees
        Celcius.

    .. attribute:: minimum_feedwater_temperature
        The minimum temperature of feedwater allowed by the plant, measured in degrees
        Celcius.

    .. attribute:: minimum_htf_temperature
        The minumum temperature of HTF allowed by the plant, measured in degrees
        Celcius.

    .. attribute:: minimum_output_capacity
        The minimum output flow rate of the plant.

    """

    def __init__(
        self,
        htf_mode: HTFMode,
        input_resource_consumption: Dict[ResourceType, float],
        maximum_feedwater_temperature: Optional[float],
        maximum_htf_temperature: Optional[float],
        maximum_output_capacity: float,
        minimum_feedwater_temperature: Optional[float],
        minimum_htf_temperature: Optional[float],
        minimum_output_capacity: float,
        name: str,
        output_resource_type: ResourceType,
        waste_production: Dict[WasteProduct, float],
    ) -> None:
        """
        Instantiate a :class:`ThermalDesalinationPlant` instance.

        Inputs:
            - htf_mode:
                The mode of inputting heat to the plant.
            - input_resource_types:
                The types of load inputted to the plant.
            - maximum_feedwater_temperature:
                The maximum temperature of feedwater allowed into the plant, measured in
                degrees Celcius.
            - maximum_htf_temperature:
                The maximum temperature of water allowed into the plant, measured in
                degrees Celcius.
            - maximum_output_capcity:
                The maximum output capacity of the plant.
            - minimum_feedwater_temperature:
                The minimum temperature of feedwater allowed into the plant, measured in
                degrees Celcius.
            - minimum_htf_temperature:
                The mibimum temperature of water allowed into the plant, measured in
                degrees Celcius.
            - minimum_output_capcity:
                The minimum output capacity of the plant.
            - name:
                The name of the plant.
            - output_resource_type:
                The type of output produced by the plant.
            - waste_production:
                The waste products produced.

        """

        super().__init__(
            input_resource_consumption,
            maximum_output_capacity,
            name,
            output_resource_type,
            waste_production,
        )

        self.htf_mode = htf_mode
        self.maximum_feedwater_temperature: Optional[
            float
        ] = maximum_feedwater_temperature
        self.maximum_htf_temperature: Optional[float] = maximum_htf_temperature
        self.minimum_feedwater_temperature: Optional[
            float
        ] = minimum_feedwater_temperature
        self.minimum_htf_temperature: Optional[float] = minimum_htf_temperature
        self.minimum_output_capacity: Optional[float] = minimum_output_capacity

    @classmethod
    def from_dict(cls, input_data: Dict[str, Any], logger: Logger) -> Any:
        """
        Generates a :class:`ThermalDesalinationPlant` instance based on the input data.

        Inputs:
            - input_data:
                The input data, parsed from the input file.

        Outputs:
            - A :class:`ThermalDesalinationPlant` instance based on the input data.

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

        try:
            htf_mode = HTFMode(input_data[HEAT_SOURCE])
        except KeyError:
            logger.info(
                "%sThe plant, %s, did not specify the source of heat. Cannot "
                "create a thermal desalination plant for %s%s",
                BColours.fail,
                str(input_data[NAME]),
                str(input_data[NAME]),
                BColours.endc,
            )
            raise

        waste_production: Dict[WasteProduct, float] = {}

        if WASTE_PRODUCTS in input_data:
            waste_production = _parse_waste_production(
                logger, input_data[NAME], input_data[WASTE_PRODUCTS]
            )

        return cls(
            htf_mode,
            input_resource_consumption,
            float(input_data[MAXIMUM_FEEDWATER_TEMPERATURE])
            if MAXIMUM_FEEDWATER_TEMPERATURE in input_data
            else None,
            float(input_data[MAXIMUM_HTF_TEMPERATURE])
            if MAXIMUM_HTF_TEMPERATURE in input_data
            else None,
            maximum_output,
            float(input_data[MINIMUM_FEEDWATER_TEMPERATURE])
            if MINIMUM_FEEDWATER_TEMPERATURE in input_data
            else None,
            float(input_data[MINIMUM_HTF_TEMPERATURE])
            if MINIMUM_HTF_TEMPERATURE in input_data
            else None,
            float(input_data[MINIMUM_OUTPUT]),
            str(input_data[NAME]),
            output_resource_type,
            waste_production,
        )


class WaterSource(Converter):
    """Represents a water source which takes in electricity and outputs water."""

    def __str__(self) -> str:
        """
        Returns a nice-looking `str` representing the :class:`Converter` instance.

        Outputs:
            - A nidee-looking `str` representing the :class:`Converter` instance.

        """

        input_resource_consumption = ", ".join(
            [
                f"{key.value}={value} units/output unit"
                for key, value in self.input_resource_consumption.items()
            ]
        )

        return (
            "Converter("
            + f"name={self.name}"
            + f", input_resource_consumption=({input_resource_consumption})"
            + f", output_resource_type = {self.output_resource_type.value}"
            + f", maximum_output_capacity = {self.maximum_output_capacity}"
            + ")"
        )

    @classmethod
    def from_dict(cls, input_data: Dict[str, Any], logger: Logger) -> Any:
        """
        Generates a :class:`Converter` instance based on the input data provided.

        Inputs:
            - input_data:
                The input data, parsed from the input file.

        Outputs:
            - A :class:`Converter` instance based on the input data.

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
                "%sCurrently only one input is allowed for water sources.%s",
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

        consumption = corresponding_input / maximum_output

        waste_production: Dict[WasteProduct, float] = {}

        if WASTE_PRODUCTS in input_data:
            waste_production = _parse_waste_production(
                logger, input_data[NAME], input_data[WASTE_PRODUCTS]
            )

        return cls(
            {input_resource_type: consumption},
            maximum_output,
            str(input_data[NAME]),
            output_resource_type,
            waste_production,
        )
