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
import os

from logging import Logger
from typing import Any, Dict, List, Optional, Pattern, Tuple, Union

import json
import re

import pandas as pd  # pylint: disable=import-error
from tqdm import tqdm

from ..simulation import energy_system

from ..__utils__ import (
    DEFAULT_SCENARIO,
    BColours,
    Criterion,
    InputFileError,
    ITERATION_LENGTH,
    Location,
    MAX,
    MIN,
    NUMBER_OF_ITERATIONS,
    ProgrammerJudgementFault,
    RenewableEnergySource,
    ResourceType,
    Scenario,
    Simulation,
    STEP,
    SystemAppraisal,
)
from ..conversion.conversion import Converter, WaterSource
from ..impact.__utils__ import ImpactingComponent

from .appraisal import appraise_system

__all__ = (
    "converters_from_sizing",
    "ConverterSize",
    "CriterionMode",
    "get_sufficient_appraisals",
    "Optimisation",
    "OptimisationParameters",
    "recursive_iteration",
    "save_optimisation",
    "SolarSystemSize",
    "StorageSystemSize",
    "TankSize",
    "ThresholdMode",
)

# Converter name string:
#   The name used for parsing the converter name group.
#   NOTE: This name is not updated within the regex and needs to be updated separately.
CONVERTER_NAME_STRING: str = "name"

# Converter size regex:
#   Regular expression used for parsing the size of various converters for
# optimisations.
#   NOTE: The name of the group is not updated automatically in accordance with the
# above string and needs to be udpated separately.
CONVERTER_SIZE_REGEX: Pattern[str] = re.compile(r"(?P<name>.*)_size")

# Scenario:
#   Keyword used for parsing the scenario to use for a given optimisation.
SCENARIO: str = "scenario"


def converters_from_sizing(converter_sizes: Dict[Converter, int]) -> List[Converter]:
    """
    Generates a `list` of available converters based on the number of each available.

    As the system is optimised, it becomes necessary to generate a `list` containing the
    available converters, with duplicates allowed to indiciate multiple instances of a
    single type present, from the various values.

    Inputs:
        - converter_sizes:
            A `dict` mapping :class:`Converter` instances to the number of each type
            present during the iteration.

    Outputs:
        - A `list` of :class:`Converter` instances present based on the mapping passed
        in.

    """

    converters: List[Converter] = []

    for converter, size in converter_sizes.items():
        converters.extend([converter] * size)

    return converters


@dataclasses.dataclass
class ConverterSize:
    """
    Used to wrap the converter size information.

    .. atttribute:: max
        The maximum size of the :class:`converseion.Converter` in question, measured in
        number of :class:`conversion.Converter` instances.

    .. attribute:: min
        The minimum size of the :class:`converseion.Converter` in question, measured in
        number of :class:`conversion.Converter` instances.

    .. attribute:: step
        The step to use for the :class:`converseion.Converter` in question, measured in
        number of :class:`conversion.Converter` instances.

    """

    max: int = 0
    min: int = 0
    step: int = 1


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

    .. attribute:: scenario
        The :class:`Scenario` to use for this optimisation.

    .. attribute:: threshold_criteria
        A `dict` mapping threshold criteria to their values.

    """

    optimisation_criteria: Dict[Criterion, CriterionMode]
    scenario: Scenario
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
            + f", scenario: {self.scenario}"
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
    def from_dict(
        cls,
        logger: Logger,
        optimisation_data: Dict[str, Any],
        scenarios: List[Scenario],
    ) -> Any:
        """
        Creates a :class:`Optimisation` instance based on the input data.

        Inputs:
            - logger:
                The logger to use for the run.
            - optimisation_data:
                The optimisation data, extracted from the input file.
            - scenarios:
                The `list` of :class:`Scenario` instances available for the run.

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

        if SCENARIO in optimisation_data:
            try:
                scenario = [
                    scenario
                    for scenario in scenarios
                    if scenario.name == optimisation_data["scenario"]
                ][0]
            except IndexError:
                logger.error(
                    "%sError determining scenario for optimisation run: scenario '%s' "
                    "could not be found.%s",
                    BColours.fail,
                    optimisation_data["scenario"],
                    BColours.endc,
                )
                raise InputFileError(
                    "optimisation inputs/scenario inputs",
                    f"Scenario {optimisation_data['scenario']} could not be found.",
                ) from None
        else:
            try:
                scenario = [
                    scenario
                    for scenario in scenarios
                    if scenario.name == DEFAULT_SCENARIO
                ][0]
            except IndexError:
                logger.error(
                    "%sError determining scenario for optimisation run: default "
                    "scenario '%s' could not be found.%s",
                    BColours.fail,
                    DEFAULT_SCENARIO,
                    BColours.endc,
                )
                raise InputFileError(
                    "optimisation inputs/scenario inputs",
                    f"Default scenario {DEFAULT_SCENARIO} could not be found.",
                ) from None

        return cls(optimisation_criteria, scenario, threshold_criteria)

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns a `dict` summarising the :class:`Optimisation` instance.

        Outputs:
            - A `dict` summarising the information contained within the
              :class:`Optimisation` instance.

        """

        optimisation_criteria = {
            str(key.value): str(value.value)
            for key, value in self.optimisation_criteria.items()
        }
        threshold_criteria = {
            str(key.value): float(value)
            for key, value in self.threshold_criteria.items()
        }

        return {
            "optimisation_criteria": optimisation_criteria,
            "scenario": self.scenario.to_dict(),
            "threshold_criteria": threshold_criteria,
        }


@dataclasses.dataclass
class OptimisationComponent(enum.Enum):
    """
    Contains information about the components which are variable in an optimisation.

    - CLEAN_WATER_PVT_SIZE:
        Denotes the size of the clean-water PV-T system, measured in PV-T units.

    - CLEAN_WATER_TANKS:
        Denotes the number of clean-water tanks in the system.

    - HOT_WATER_PVT_SIZE:
        Denotes the size of the hot-water PV-T system, measured in PV-T units.

    - HOT_WATER_TANKS:
        Denotes the number of hot-water tanks in the system.

    - PV_SIZE:
        Denotes the size of the PV system, measured in PV units.

    - STORAGE_SIZE:
        Denotes the size of the storage system, measured in storage units, i.e.,
        batteries.

    """

    CLEAN_WATER_PVT_SIZE = "cw_pvt_size"
    CLEAN_WATER_TANKS = "cw_tanks"
    HOT_WATER_PVT_SIZE = "hw_pvt_size"
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
    step: float = 1


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
    step: float = 1


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
    step: int = 1


@dataclasses.dataclass
class OptimisationParameters:
    """
    Parameters that define the scope of the optimisation.

    .. attribute:: clean_water_tanks
        The sizing bounds for the clean-water tanks.

    .. attribute:: converter_sizes
        The sizing bounds for the various :class:`conversion.Converter` instances
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
    converter_sizes: Dict[Converter, ConverterSize]
    cw_pvt_size: SolarSystemSize
    hot_water_tanks: TankSize
    hw_pvt_size: SolarSystemSize
    iteration_length: int
    number_of_iterations: int
    pv_size: SolarSystemSize
    storage_size: StorageSystemSize

    @classmethod
    def from_dict(  # pylint: disable=too-many-statements
        cls,
        available_converters: List[Converter],
        logger: Logger,
        optimisation_inputs: Dict[str, Any],
    ) -> Any:
        """
        Returns a :class:`OptimisationParameters` instance based on the input info.

        Inputs:
            - available_converters:
                The `list` of :class:`conversion.Converter` instances that are defined
                and which are available to the system.
            - logger:
                The :class:`logging.Loggger` to use for the run.
            - optimisation_inputs:
                The optimisation input information, extracted from the input file.

        Outputs:
            - A :class:`OptimisationParameters` instanced based on the information
            passed in.

        """

        # Parse the clean-water PV-T system size.
        if OptimisationComponent.CLEAN_WATER_PVT_SIZE.value in optimisation_inputs:
            try:
                cw_pvt_size = SolarSystemSize(
                    optimisation_inputs[
                        OptimisationComponent.CLEAN_WATER_PVT_SIZE.value
                    ][MAX],
                    optimisation_inputs[
                        OptimisationComponent.CLEAN_WATER_PVT_SIZE.value
                    ][MIN],
                    optimisation_inputs[
                        OptimisationComponent.CLEAN_WATER_PVT_SIZE.value
                    ][STEP],
                )
            except KeyError:
                logger.error(
                    "%sNot all clean-water PV-T size information specified in the "
                    "optimisation inputs file.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise
            if cw_pvt_size.min == 0 or cw_pvt_size.max == 0:
                logger.error(
                    "%sCannot have zero clean-water PV-T collectors when modelling the "
                    "clean-water system.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise InputFileError(
                    "optimisation inputs",
                    "If modelling a clean-water system, none of the clean-water PV-T "
                    "size options can be set to zero.",
                )
        else:
            cw_pvt_size = SolarSystemSize()

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
            if clean_water_tanks.min == 0 or clean_water_tanks.max == 0:
                logger.error(
                    "%sCannot have zero clean-water tanks when modelling the "
                    "clean-water system.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise InputFileError(
                    "optimisation inputs",
                    "If modelling a clean-water system, none of the clean-water tank "
                    "size options can be set to zero.",
                )
        else:
            clean_water_tanks = TankSize()

        # Parse the converters that are to be optimised.
        converter_sizing_inputs: Dict[str, Dict[str, int]] = {
            key: value  # type: ignore
            for key, value in optimisation_inputs.items()
            if CONVERTER_SIZE_REGEX.match(key) is not None
        }

        # NOTE: Explicit error handling is done for the type-check ignored lines.
        try:
            converter_sizing_inputs = {
                CONVERTER_SIZE_REGEX.match(key).group(CONVERTER_NAME_STRING): value  # type: ignore
                for key, value in converter_sizing_inputs.items()
                if CONVERTER_SIZE_REGEX.match(key).group(CONVERTER_NAME_STRING)  # type: ignore
                in {converter.name for converter in available_converters}
            }
        except AttributeError:
            logger.error(
                "%sError parsing converter input information, unable to match groups."
                "%s",
                BColours.fail,
                BColours.endc,
            )
            raise

        converter_name_to_converter = {
            converter.name: converter for converter in available_converters
        }
        try:
            converter_sizes: Dict[Converter, ConverterSize] = {
                converter_name_to_converter[key]: ConverterSize(
                    entry[MAX], entry[MIN], entry[STEP]
                )
                for key, entry in converter_sizing_inputs.items()
            }
        except KeyError:
            logger.error(
                "%sNot all information was provided for the converters defined within "
                "the optimisation inputs file.%s",
                BColours.fail,
                BColours.endc,
            )
            raise

        # Parse the hot-water PV-T size information.
        if OptimisationComponent.HOT_WATER_PVT_SIZE.value in optimisation_inputs:
            try:
                hw_pvt_size = SolarSystemSize(
                    optimisation_inputs[OptimisationComponent.HOT_WATER_PVT_SIZE.value][
                        MAX
                    ],
                    optimisation_inputs[OptimisationComponent.HOT_WATER_PVT_SIZE.value][
                        MIN
                    ],
                    optimisation_inputs[OptimisationComponent.HOT_WATER_PVT_SIZE.value][
                        STEP
                    ],
                )
            except KeyError:
                logger.error(
                    "%sNot all hot-water PV-T size information specified in the "
                    "optimisation inputs file.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise
            if hw_pvt_size.min == 0 or hw_pvt_size.max == 0:
                logger.error(
                    "%sCannot have zero hot-water PV-T collectors when modelling the "
                    "hot-water system.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise InputFileError(
                    "optimisation inputs",
                    "If modelling an hot-water system, none of the hot-water PV-T size "
                    "options can be set to zero.",
                )
        else:
            hw_pvt_size = SolarSystemSize()

        # Parse the hot-water tank information.
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
            if hot_water_tanks.min == 0 or hot_water_tanks.max == 0:
                logger.error(
                    "%sCannot have zero hot-water tanks when modelling the "
                    "hot-water system.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise InputFileError(
                    "optimisation inputs",
                    "If modelling an hot-water system, none of the hot-water tank "
                    "size options can be set to zero.",
                )
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
                storage_size = StorageSystemSize(
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
            converter_sizes,
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
            "clean_water_pvt_size_max": int(self.cw_pvt_size.max)
            if self.cw_pvt_size is not None
            else None,
            "clean_water_pvt_size_min": int(self.cw_pvt_size.min)
            if self.cw_pvt_size is not None
            else None,
            "clean_water_pvt_size_step": int(self.cw_pvt_size.step)
            if self.cw_pvt_size is not None
            else None,
            "clean_water_tanks_max": int(self.clean_water_tanks.max)
            if self.clean_water_tanks is not None
            else None,
            "clean_water_tanks_min": int(self.clean_water_tanks.min)
            if self.clean_water_tanks is not None
            else None,
            "clean_water_tanks_step": int(self.clean_water_tanks.step)
            if self.clean_water_tanks is not None
            else None,
            "hot_water_pvt_size_max": int(self.hw_pvt_size.max)
            if self.hw_pvt_size is not None
            else None,
            "hot_water_pvt_size_min": int(self.hw_pvt_size.min)
            if self.hw_pvt_size is not None
            else None,
            "hot_water_pvt_size_step": int(self.hw_pvt_size.step)
            if self.hw_pvt_size is not None
            else None,
            "hot_water_tanks_max": int(self.hot_water_tanks.max)
            if self.hot_water_tanks is not None
            else None,
            "hot_water_tanks_min": int(self.hot_water_tanks.min)
            if self.hot_water_tanks is not None
            else None,
            "hot_water_tanks_step": int(self.hot_water_tanks.step)
            if self.hot_water_tanks is not None
            else None,
            ITERATION_LENGTH: round(self.iteration_length, 3),
            NUMBER_OF_ITERATIONS: round(self.number_of_iterations, 3),
            "pv_size_max": round(self.pv_size.max, 3),
            "pv_size_min": round(self.pv_size.min, 3),
            "pv_size_step": round(self.pv_size.step, 3),
            "storage_size_max": round(self.storage_size.max, 3),
            "storage_size_min": round(self.storage_size.min, 3),
            "storage_size_step": round(self.storage_size.step, 3),
        }

        return {
            key: value
            for key, value in optimisation_parameters_dict.items()
            if value is not None
        }


# Threshold-criterion-to-mode mapping:
#   Maps the threshold criteria to the modes, i.e., whether they are maximisable or
#   minimisable.
THRESHOLD_CRITERION_TO_MODE: Dict[Criterion, ThresholdMode] = {
    Criterion.BLACKOUTS: ThresholdMode.MAXIMUM,
    Criterion.CLEAN_WATER_BLACKOUTS: ThresholdMode.MAXIMUM,
    Criterion.CUMULATIVE_COST: ThresholdMode.MAXIMUM,
    Criterion.CUMULATIVE_GHGS: ThresholdMode.MAXIMUM,
    Criterion.CUMULATIVE_SYSTEM_COST: ThresholdMode.MAXIMUM,
    Criterion.EMISSIONS_INTENSITY: ThresholdMode.MAXIMUM,
    Criterion.KEROSENE_COST_MITIGATED: ThresholdMode.MINIMUM,
    Criterion.KEROSENE_DISPLACEMENT: ThresholdMode.MINIMUM,
    Criterion.KEROSENE_GHGS_MITIGATED: ThresholdMode.MINIMUM,
    Criterion.LCUE: ThresholdMode.MAXIMUM,
    Criterion.RENEWABLES_FRACTION: ThresholdMode.MINIMUM,
    Criterion.TOTAL_COST: ThresholdMode.MAXIMUM,
    Criterion.TOTAL_GHGS: ThresholdMode.MAXIMUM,
    Criterion.TOTAL_SYSTEM_COST: ThresholdMode.MAXIMUM,
    Criterion.TOTAL_SYSTEM_GHGS: ThresholdMode.MAXIMUM,
    Criterion.UNMET_ENERGY_FRACTION: ThresholdMode.MAXIMUM,
}


def get_sufficient_appraisals(
    optimisation: Optimisation, system_appraisals: List[SystemAppraisal]
) -> List[SystemAppraisal]:
    """
    Checks whether any of the system appraisals fulfill the threshold criterion

    Inputs:
        - optimisation:
            The optimisation currently being considered.
        - system_appraisals:
            Appraisals of the systems which have been simulated

    Outputs:
        - sufficient_systems:
            Appraisals of the systems which meet the threshold criterion (sufficient systems)

    """

    sufficient_appraisals: List[SystemAppraisal] = []

    # Cycle through the provided appraisals.
    for appraisal in system_appraisals:
        if appraisal.criteria is None:
            raise ProgrammerJudgementFault(
                "appraisal",
                "A system appraisal was returned which does not have criteria defined.",
            )
        criteria_met = set()
        for (
            threshold_criterion,
            threshold_value,
        ) in optimisation.threshold_criteria.items():
            # Add a `True` marker if the threshold criteria are met, otherwise add
            # False.
            if (
                THRESHOLD_CRITERION_TO_MODE[threshold_criterion]
                == ThresholdMode.MAXIMUM
            ):
                if appraisal.criteria[threshold_criterion] <= threshold_value:
                    criteria_met.add(True)
                else:
                    criteria_met.add(False)
            if (
                THRESHOLD_CRITERION_TO_MODE[threshold_criterion]
                == ThresholdMode.MINIMUM
            ):
                if appraisal.criteria[threshold_criterion] >= threshold_value:
                    criteria_met.add(True)
                else:
                    criteria_met.add(False)

        # Store the system to return provided it is sufficient.
        if all(criteria_met):
            sufficient_appraisals.append(appraisal)

    return sufficient_appraisals


def recursive_iteration(  # pylint: disable=too-many-locals
    conventional_cw_source_profiles: Optional[Dict[WaterSource, pd.DataFrame]],
    disable_tqdm: bool,
    end_year: int,
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    grid_profile: Optional[pd.DataFrame],
    irradiance_data: pd.Series,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    optimisation: Optimisation,
    previous_system: Optional[SystemAppraisal],
    start_year: int,
    temperature_data: pd.Series,
    total_loads: Dict[ResourceType, Optional[pd.DataFrame]],
    total_solar_pv_power_produced: pd.Series,
    wind_speed_data: Optional[pd.Series],
    yearly_electric_load_statistics: pd.DataFrame,
    *,
    component_sizes: Dict[
        Union[Converter, ImpactingComponent, RenewableEnergySource],
        Union[int, float],
    ],
    parameter_space: List[
        Tuple[
            Union[Converter, ImpactingComponent, RenewableEnergySource],
            str,
            Union[List[int], List[float]],
        ]
    ],
    system_appraisals: List[SystemAppraisal],
) -> List[SystemAppraisal]:
    """
    Recursively look for sufficient systems through a series of parameter spaces.

    To recursively search through the parameter space, two objects are utilised:
    - a mapping between the component and the size to model for it;
    - a `list` of `tuple`s containing the components along with a list of possible
      values.

    At each stage in the process, a single component is removed from the `list` and
    added to the mapping such that a definite value is assigned. This is then passed
    through recursively with the function being called each time from a loop. In this
    way, a single level of the recursion deals with a single component of the system
    and its possible sizes, whilst the lowest (deepest) level of recursion deals with
    the actual simulations that are being carried out.

    In order to specify unique values, i.e., components of the system which have a fixed
    size and do not require iteration, use the mapping directly. In this way, the
    recursive function will be unaware of whether there exists a recursive layer for
    this parameter or whether the value has been uniquely defined.

    Inputs: (NOTE: Only inputs are listed which are utilised within this function.)
        - component_sizes:
            Specific values for the varoius :class:`finance.ImpactingComponent` sizes
            and :class:`RenewableEnergySource` sizes to use for the simulation to be
            carried out.
        - parameter_spaces:
            A `list` containing `tuple`s as entries that specify:
            - The :class:`finance.ImpactingComponent` that should have its sizes
              iterated through;
            - The unit to display to the user, as a `str`;
            - The `list` of values to iterate through.
        - system_appraisals:
            The `list` containing the :class:`SystemAppraisal` instances that correspond
            to sufficient systems.

    Outputs:
        - A `list` of sufficient systems.

    """

    # If there are no more things to iterate through, then run a simulation and return
    # whether the system was sufficient.
    if len(parameter_space) == 0:
        logger.info(
            "Running simulation with component sizes:\n- %s",
            "\n- ".join(
                [f"{key.value} size={value}" for key, value in component_sizes.items()]
            ),
        )

        # Determine the converter sizes.
        if not all(isinstance(value, int) for value in component_sizes.values()):
            logger.info(
                "%sNon-integer component sizes were specified.%s",
                BColours.fail,
                BColours.endc,
            )
        converters = converters_from_sizing(
            {
                key: int(value)
                for key, value in component_sizes.items()
                if isinstance(key, Converter)
            }
        )

        # Run the simulation
        (
            _,
            simulation_results,
            system_details,
        ) = energy_system.run_simulation(
            int(component_sizes[RenewableEnergySource.CLEAN_WATER_PVT]),
            conventional_cw_source_profiles,
            converters,
            disable_tqdm,
            component_sizes[ImpactingComponent.STORAGE],
            grid_profile,
            int(component_sizes[RenewableEnergySource.HOT_WATER_PVT]),
            irradiance_data,
            kerosene_usage,
            location,
            logger,
            minigrid,
            int(component_sizes[ImpactingComponent.CLEAN_WATER_TANK]),
            int(component_sizes[ImpactingComponent.HOT_WATER_TANK]),
            total_solar_pv_power_produced,
            component_sizes[RenewableEnergySource.PV],
            optimisation.scenario,
            Simulation(end_year, start_year),
            temperature_data,
            total_loads,
            wind_speed_data,
        )

        new_appraisal = appraise_system(
            yearly_electric_load_statistics,
            end_year,
            finance_inputs,
            ghg_inputs,
            location,
            logger,
            previous_system,
            optimisation.scenario,
            simulation_results,
            start_year,
            system_details,
        )

        return get_sufficient_appraisals(optimisation, [new_appraisal])

    # If there are things to iterate through, then iterate through these, calling the
    # function recursively.
    component, unit, sizes = parameter_space.pop()

    for size in tqdm(
        sizes,
        desc=f"{component.value} size options",
        disable=disable_tqdm,
        leave=False,
        unit=unit,
    ):
        # Update the set of fixed sizes accordingly.
        updated_component_sizes: Dict[
            Union[Converter, ImpactingComponent, RenewableEnergySource],
            Union[int, float],
        ] = component_sizes.copy()
        updated_component_sizes[component] = size

        # Call the function recursively.
        sufficient_appraisals = recursive_iteration(
            conventional_cw_source_profiles,
            disable_tqdm,
            end_year,
            finance_inputs,
            ghg_inputs,
            grid_profile,
            irradiance_data,
            kerosene_usage,
            location,
            logger,
            minigrid,
            optimisation,
            previous_system,
            start_year,
            temperature_data,
            total_loads,
            total_solar_pv_power_produced,
            wind_speed_data,
            yearly_electric_load_statistics,
            component_sizes=updated_component_sizes,
            parameter_space=parameter_space.copy(),
            system_appraisals=system_appraisals,
        )
        if sufficient_appraisals == []:
            logger.info("No sufficient systems at this resolution.")
            if len(parameter_space) == 0:
                logger.info("Probing lowest depth - skipping further size options.")
                break
            logger.info("Probing non-lowest depth - continuing iteration.")
            continue

        # Store the new appraisal if it is sufficient.
        logger.info("Sufficient system found, storing.")
        for appraisal in sufficient_appraisals:
            if appraisal.criteria is None:
                logger.error(
                    "%sNo appraisal criteria for appraisal.%s",
                    BColours.fail,
                    BColours.endc,
                )
                logger.debug("System appraisal: %s", appraisal)
                raise ProgrammerJudgementFault(
                    "appraisal module",
                    "When processing debug output for sufficient appraisals, an error "
                    "occured as there were no criteria attached to the appraisal. More "
                    "information can be found in the logger directory.",
                )
            logger.debug(
                "Threshold criteria: %s",
                json.dumps(
                    {
                        str(key.value): value
                        for key, value in appraisal.criteria.items()
                    },
                    indent=4,
                ),
            )
        system_appraisals.extend(sufficient_appraisals)

    # Return the sufficient appraisals that were found at this resolution.
    return sufficient_appraisals


def save_optimisation(
    disable_tqdm: bool,
    logger: Logger,
    optimisation_inputs: OptimisationParameters,
    optimisation_number: int,
    output: str,
    output_directory: str,
    scenario: Scenario,
    system_appraisals: List[SystemAppraisal],
) -> None:
    """
    Saves simulation outputs to a .csv file

    Inputs:
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - logger:
            The logger to use for the run.
        - optimisation_inputs:
            The optimisation input information.
        - optimisation_number:
            The number of the optimisation that has just been carried out.
        - output:
            The output name to use when labelling the simulation: this is the name given
            to the output folder in which the system files are saved.
        - output_directory:
            The directory into which the files should be saved.
        - scenario:
            The scenario for the optimisation.
        - system_appraisals:
            A `list` of the :class:`SystemAppraisal` instances which specify the
            optimum systems at each time step.

    """

    # Remove the file extension if appropriate.
    if output.endswith(".json"):
        output = output.rsplit(".json", 1)[0]

    # Create the output directory.
    optimisation_output_folder = os.path.join(output_directory, output)
    os.makedirs(optimisation_output_folder, exist_ok=True)

    # Add the key results to the system data.
    system_appraisals_dict = {
        f"iteration_{index}": appraisal.to_dict()
        for index, appraisal in enumerate(system_appraisals)
    }

    # Add the optimisation parameter information.
    output_dict = {
        "optimisation_inputs": optimisation_inputs.to_dict(),
        "scenario": scenario.to_dict(),
        "system_appraisals": system_appraisals_dict,
    }

    with tqdm(
        total=1,
        desc="saving output files",
        disable=disable_tqdm,
        leave=False,
        unit="file",
    ) as pbar:
        # Save the optimisation data.
        logger.info("Saving optimisation output.")
        with open(
            os.path.join(
                optimisation_output_folder,
                f"optimisation_output_{optimisation_number}.json",
            ),
            "w",
        ) as f:
            json.dump(output_dict, f, indent=4)
        logger.info(
            "Optimisation successfully saved to %s.", optimisation_output_folder
        )
        pbar.update(1)
