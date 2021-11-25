#!/usr/bin/python3
########################################################################################
# __utils__.py - CLOVER Optimisation Utility module.                                   #
#                                                                                      #
# Author: Phil Sandwell, Ben Winchester                                                #
# Copyright: Phil Sandwell, 2018                                                       #
# Date created: 24/08/2021                                                             #
#                                                                                      #
# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
__utils__.py - Utility module for CLOVER's Optimisation Component.

The utility module contains functionality which is used by the optimisation and
appraisal modules within the optimisation component.

"""

import dataclasses
import enum

from logging import Logger
from typing import Any, Dict

import re

from ..__utils__ import (
    BColours,
    Criterion,
    ITERATION_LENGTH,
    MAX,
    MIN,
    NUMBER_OF_ITERATIONS,
    STEP,
)
from ..conversion.conversion import Convertor

__all__ = (
    "ConvertorSize",
    "CriterionMode",
    "Optimisation",
    "OptimisationParameters",
    "SolarSystemSize",
    "StorageSystemSize",
    "TankSize",
    "ThresholdMode",
)

# Convertor size regex:
#   Regular expression used for parsing the size of various convertors for
# optimisations.
CONVERTOR_SIZE_REGEX: str = re.compile(r"(?P<name>.*)_size")


class ConvertorSize(enum.Enum):
    """
    Used to wrap the convertor size information.

    .. atttribute:: max
        The maximum size of the :class:`converseion.Convertor` in question, measured in
        number of :class:`conversion.Convertor` instances.

    .. attribute:: min
        The minimum size of the :class:`converseion.Convertor` in question, measured in
        number of :class:`conversion.Convertor` instances.

    .. attribute:: step
        The step to use for the :class:`converseion.Convertor` in question, measured in
        number of :class:`conversion.Convertor` instances.

    """

    max: int = 0
    min: int = 0
    step: int = 0


class CriterionMode(enum.Enum):
    """
    The mode of optimisation of the criterion.

    - MAXIMISE:
        Denotes that the optimisation criterion is to be maximised.

    - MINIMISE:
        Denotes that the optimisation criterion is to be minimised.

    """

    MAXIMISE = "maximise"
    MINIMISE = "minimise"

    def __str__(self) -> str:
        """
        Returns a nice-looking `str` representing the :class:`CriterionMode`.

        Outputs:
            - A nice-looking `str` representing the :class:`CriterionMode`
              instance.

        """

        return f"CriterionMode(mode={self.value})"


class ThresholdMode(enum.Enum):
    """
    Represents whether a threshold value is a maximum or minimum limit on the system.

    - MAXIMUM:
        Denotes that the threshold is a maximum to be placed on the system.
    - MINIMUM:
        Denotes that the threshold is a minimum to be placed on the system.

    """

    MAXIMUM = "maximum"
    MINIMUM = "minimum"


@dataclasses.dataclass
class Optimisation:
    """
    Represents an optimisation to be carried out.

    .. attribute:: optimisation_criteria
        A `dict` mapping optimisation criteria to whether they should be maximised or
        minimised.

    .. attribute:: threshold_criteria
        A `dict` mapping threshold criteria to their values.

    """

    optimisation_criteria: Dict[Criterion, CriterionMode]
    threshold_criteria: Dict[Criterion, float]

    def __str__(self) -> str:
        """
        Returns a nice-looking `str` summarising the :class:`Optimisation` instance.

        Outputs:
            - A nice-looking `str` summarising the information contained within the
              :class:`Optimisation` instance.

        """

        return (
            "Optimisation("
            + f"optimisation_crtieria: {self.optimisation_criteria}"
            + f", threshold_criteria: {self.threshold_criteria}"
            + ")"
        )

    def __hash__(self) -> int:
        """
        Returns an `int` representing the :class:`Optimisation` instance for sorting.

        In order to efficiently store :class:`Optimisation` instances, a unique hash is
        required. This method computes such a hash and returns it.

        Outputs:
            - A unique `int` representing the :class:`Optimisation` instance.

        """

        return hash(str(self))

    @classmethod
    def from_dict(cls, logger: Logger, optimisation_data: Dict[str, Any]) -> Any:
        """
        Creates a :class:`Optimisation` instance based on the input data.

        Inputs:
            - logger:
                The logger to use for the run.
            - optimisation_data:
                The optimisation data, extracted from the input file.

        Outputs:
            - A :class:`Optimisation` instance based on the input data.

        """

        try:
            optimisation_criteria = {
                Criterion(key): CriterionMode(value)
                for entry in optimisation_data["optimisation_criteria"]
                for key, value in entry.items()
            }
        except KeyError as e:
            logger.error(
                "%sError processing optimisation criteria, missing entry: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise

        try:
            threshold_criteria = {
                Criterion(key): value
                for entry in optimisation_data["threshold_criteria"]
                for key, value in entry.items()
            }
        except KeyError as e:
            logger.error(
                "%sError processing threshold criteria, missing entry: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise

        return cls(optimisation_criteria, threshold_criteria)


@dataclasses.dataclass
class OptimisationComponent(enum.Enum):
    """
    Contains information about the components which are variable in an optimisation.

    - CLEAN_WATER_TANKS:
        Denotes the number of clean-water tanks in the system.

    - PV_SIZE:
        Denotes the size of the PV system, measured in PV units.

    - PVT_SIZE:
        Denotes the size of the PV-T system, measured in PV-T units.

    - STORAGE_SIZE:
        Denotes the size of the storage system, measured in storage units, i.e.,
        batteries.

    """

    CLEAN_WATER_PVT = "cw_pvt_size"
    CLEAN_WATER_TANKS = "cw_tanks"
    HOT_WATER_PVT = "hw_pvt_size"
    HOT_WATER_TANKS = "hw_tanks"
    PV_SIZE = "pv_size"
    STORAGE_SIZE = "storage_size"


@dataclasses.dataclass
class SolarSystemSize:
    """
    Used to wrap the solar-system-size information.

    .. attribute:: max
        The maximum size of the system, measured in PV or PV-T units.

    .. attribute:: min
        The minimum size of the system, measured in PV or PV-T units.

    .. attribute:: step
        The step to use for the system, measured in PV or PV-T units.

    """

    max: float = 0
    min: float = 0
    step: float = 0


@dataclasses.dataclass
class StorageSystemSize:
    """
    Used to wrap the storage-system-size information.

    .. attribute:: max
        The maximum size of the system, measured in storage units, i.e., batteries.

    .. attribute:: min
        The minimum size of the system, measured in storage units, i.e., batteries.

    .. attribute:: step
        The step to use for the system, measured in storage units, i.e., batteries.

    """

    max: float = 0
    min: float = 0
    step: float = 0


@dataclasses.dataclass
class TankSize:
    """
    Used to wrap the tank size information.

    .. atttribute:: max
        The maximum size of the tank system, measured in number of tanks.

    .. attribute:: min
        The minimum size of the tank system, measured in number of tanks.

    .. attribute:: step
        The step to use for the tank system, measured in number of tanks.

    """

    max: int = 0
    min: int = 0
    step: int = 0


@dataclasses.dataclass
class OptimisationParameters:
    """
    Parameters that define the scope of the optimisation.

    .. attribute:: clean_water_tanks
        The sizing bounds for the clean-water tanks.

    .. attribute:: convertor_sizes
        The sizing bounds for the various :class:`conversion.Convertor` instances
        associated with the system.

    .. attribute:: cw_pvt_size
        The sizing bounds for the clean-water PV-T collectors.

    .. attribute:: hot_water_tanks
        The sizing bounds for the hot-water tanks.

    .. attribute:: hw_pvt_size
        The sizing bounds for the hot-water PV-T collectors.

    .. attribute:: iteration_length
        The length of the iterations to be carried out.

    .. attribute:: number_of_iterations
        The number of iterations to carry out.

    .. attribute:: pv_size
        The sizing bounds for the PV panels.

    .. attribute:: storage_size
        The sizing bounds for the electricity storage system (i.e., batteries).

    """

    clean_water_tanks: TankSize
    convertor_sizes: Dict[Convertor, ConvertorSize]
    cw_pvt_size: SolarSystemSize
    hot_water_tanks: TankSize
    hw_pvt_size: SolarSystemSize
    iteration_length: int
    number_of_iterations: int
    pv_size: SolarSystemSize
    storage_size: StorageSystemSize

    @classmethod
    def from_dict(cls, logger: Logger, optimisation_inputs: Dict[str, Any]) -> Any:
        """
        Returns a :class:`OptimisationParameters` instance based on the input info.

        Inputs:
            - logger:
                The :class:`logging.Loggger` to use for the run.
            - optimisation_inputs:
                The optimisation input information, extracted from the input file.

        Outputs:
            - A :class:`OptimisationParameters` instanced based on the information
            passed in.

        """

        # Parse the clean-water tank information.
        if OptimisationComponent.CLEAN_WATER_TANKS.value in optimisation_inputs:
            try:
                clean_water_tanks: TankSize = TankSize(
                    int(
                        optimisation_inputs[
                            OptimisationComponent.CLEAN_WATER_TANKS.value
                        ][MAX]
                    ),
                    int(
                        optimisation_inputs[
                            OptimisationComponent.CLEAN_WATER_TANKS.value
                        ][MIN]
                    ),
                    int(
                        optimisation_inputs[
                            OptimisationComponent.CLEAN_WATER_TANKS.value
                        ][STEP]
                    ),
                )
            except KeyError:
                logger.error(
                    "%sNot all clean-water tank information specified in the "
                    "optimisation inputs file.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise
        else:
            clean_water_tanks = TankSize()

        # Parse the clean-water tank information.
        if OptimisationComponent.HOT_WATER_TANKS.value in optimisation_inputs:
            try:
                hot_water_tanks: TankSize = TankSize(
                    int(
                        optimisation_inputs[
                            OptimisationComponent.HOT_WATER_TANKS.value
                        ][MAX]
                    ),
                    int(
                        optimisation_inputs[
                            OptimisationComponent.HOT_WATER_TANKS.value
                        ][MIN]
                    ),
                    int(
                        optimisation_inputs[
                            OptimisationComponent.HOT_WATER_TANKS.value
                        ][STEP]
                    ),
                )
            except KeyError:
                logger.error(
                    "%sNot all hot-water tank information specified in the "
                    "optimisation inputs file.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise
        else:
            hot_water_tanks = TankSize()

        if OptimisationComponent.PV_SIZE.value in optimisation_inputs:
            try:
                pv_size = SolarSystemSize(
                    optimisation_inputs[OptimisationComponent.PV_SIZE.value][MAX],
                    optimisation_inputs[OptimisationComponent.PV_SIZE.value][MIN],
                    optimisation_inputs[OptimisationComponent.PV_SIZE.value][STEP],
                )
            except KeyError:
                logger.error(
                    "%sNot all PV size information specified in the optimisation "
                    "inputs file.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise
        else:
            pv_size = SolarSystemSize()

        if OptimisationComponent.STORAGE_SIZE.value in optimisation_inputs:
            try:
                storage_size = SolarSystemSize(
                    optimisation_inputs[OptimisationComponent.STORAGE_SIZE.value][MAX],
                    optimisation_inputs[OptimisationComponent.STORAGE_SIZE.value][MIN],
                    optimisation_inputs[OptimisationComponent.STORAGE_SIZE.value][STEP],
                )
            except KeyError:
                logger.error(
                    "%sNot all battery storage size information specified in the "
                    "optimisation inputs file.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise
        else:
            storage_size = StorageSystemSize()

        return cls(
            clean_water_tanks,
            convertor_sizes,
            cw_pvt_size,
            hot_water_tanks,
            hw_pvt_size,
            optimisation_inputs[ITERATION_LENGTH],
            optimisation_inputs[NUMBER_OF_ITERATIONS],
            pv_size,
            storage_size,
        )

    @property
    def scenario_length(self) -> int:
        """
        Calculates and returns the scenario length for the optimisation.

        Outputs:
            - The scenario length for the optimisation.

        """

        return self.iteration_length * self.number_of_iterations

    def to_dict(self) -> Dict[str, Union[int, float]]:
        """
        Returns a `dict` representation of the :class:`OptimisationParameters` instance.

        Outputs:
            A `dict` containing the :class:`OptimisationParameters` information.

        """

        optimisation_parameters_dict = {
            "clean_water_tanks_max": int(self.clean_water_tanks_max)
            if self.clean_water_tanks_max is not None
            else None,
            "clean_water_tanks_min": int(self.clean_water_tanks_min)
            if self.clean_water_tanks_min is not None
            else None,
            "clean_water_tanks_step": int(self.clean_water_tanks_step)
            if self.clean_water_tanks_step is not None
            else None,
            ITERATION_LENGTH: round(self.iteration_length, 3),
            NUMBER_OF_ITERATIONS: round(self.number_of_iterations, 3),
            "pv_size_max": round(self.pv_size_max, 3),
            "pv_size_min": round(self.pv_size_min, 3),
            "pv_size_step": round(self.pv_size_step, 3),
            "pvt_size_max": int(self.pvt_size_max)
            if self.pvt_size_max is not None
            else None,
            "pvt_size_min": int(self.pvt_size_min)
            if self.pvt_size_min is not None
            else None,
            "pvt_size_step": int(self.pvt_size_step)
            if self.pvt_size_step is not None
            else None,
            "storage_size_max": round(self.storage_size_max, 3),
            "storage_size_min": round(self.storage_size_min, 3),
            "storage_size_step": round(self.storage_size_step, 3),
        }

        return {
            key: value
            for key, value in optimisation_parameters_dict.items()
            if value is not None
        }
