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
from typing import Any, Dict, Optional

from ..__utils__ import BColours, OptimisationCriterion, ThresholdCriterion

__all__ = (
    "CriterionMode",
    "Optimisation",
    "OptimisationParameters",
    "PVSystemSize",
    "StorageSystemSize",
    "ThresholdMode",
)


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

    optimisation_criteria: Dict[OptimisationCriterion, CriterionMode]
    thershold_criteria: Dict[ThresholdCriterion, float]

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
            + f", thershold_criteria: {self.thershold_criteria}"
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
                OptimisationCriterion(key): CriterionMode(value)
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
                ThresholdCriterion(key): value
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
class OptimisationParameters:
    """
    Parameters that define the scope of the optimisation.

    .. attribute:: iteration_length
        The length of each iteration to be run.

    .. attribute:: number_of_iterations
        The number of iterations to run.

    .. attribute:: pv_size_max
        The maximum size of PV capacity to be considered, used only as an initial value,
        measured in kWp.

    .. attribute:: pv_size_min
        The minimum size of PV capacity to be considered, measured in kWp.

    .. attribute:: pv_size_step
        The optimisation resolution for the PV size, measured in kWp.

    .. attribute:: storage_size_max
        The maximum size of storage capacity to be considered, used only as an initial
        value, measured in kWh.

    .. attribute:: storage_size_min
        The minimum size of storage capacity to be considered, measured in kWh.

    .. attribute:: storage_size_step
        The optimisation restolution for the storage size, measured in kWh.

    """

    iteration_length: int
    number_of_iterations: int
    pv_size_max: float
    pv_size_min: float
    pv_size_step: float
    storage_size_max: float
    storage_size_min: float
    storage_size_step: float

    @classmethod
    def from_dict(cls, optimisation_inputs: Dict[str, Any]) -> Any:
        """
        Returns a :class:`OptimisationParameters` instance based on the input info.

        Outputs:
            - A :class:`OptimisationParameters` instanced based on the information
            passed in.

        """

        return cls(
            optimisation_inputs["iteration_length"],
            optimisation_inputs["number_of_iterations"],
            optimisation_inputs["pv_size"]["max"],
            optimisation_inputs["pv_size"]["min"],
            optimisation_inputs["pv_size"]["step"],
            optimisation_inputs["storage_size"]["max"],
            optimisation_inputs["storage_size"]["min"],
            optimisation_inputs["storage_size"]["step"],
        )

    @property
    def scenario_length(self) -> int:
        """
        Calculates and returns the scenario length for the optimisation.

        Outputs:
            - The scenario length for the optimisation.

        """

        return self.iteration_length * self.number_of_iterations


@dataclasses.dataclass
class PVSystemSize:
    """
    Used to wrap the pv-system-size information.

    .. attribute:: max
        The maximum size of the system, measured in kWp.

    .. attribute:: min
        The minimum size of the system, measured in kWp.

    .. attribute:: step
        The step to use for the system, measured in kWp.

    """

    max: float
    min: float
    step: float


@dataclasses.dataclass
class StorageSystemSize:
    """
    Used to wrap the storage-system-size information.

    .. attribute:: max
        The maximum size of the system, measured in kWh.

    .. attribute:: min
        The minimum size of the system, measured in kWh.

    .. attribute:: step
        The step to use for the system, measured in kWh.

    """

    max: float
    min: float
    step: float

