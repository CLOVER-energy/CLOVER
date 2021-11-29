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
from typing import Any, Dict, List, Pattern, Set, Union

import json
import re
import tqdm

from ..__utils__ import (
    BColours,
    Criterion,
    ITERATION_LENGTH,
    MAX,
    MIN,
    NUMBER_OF_ITERATIONS,
    STEP,
    InputFileError,
    SystemAppraisal,
)
from ..conversion.conversion import Convertor

__all__ = (
    "ConvertorSize",
    "CriterionMode",
    "Optimisation",
    "OptimisationParameters",
    "save_optimisation",
    "SolarSystemSize",
    "StorageSystemSize",
    "TankSize",
    "ThresholdMode",
)

# Convertor name string:
#   The name used for parsing the convertor name group.
#   NOTE: This name is not updated within the regex and needs to be updated separately.
CONVERTOR_NAME_STRING: str = "name"

# Convertor size regex:
#   Regular expression used for parsing the size of various convertors for
# optimisations.
#   NOTE: The name of the group is not updated automatically in accordance with the
# above string and needs to be udpated separately.
CONVERTOR_SIZE_REGEX: Pattern[str] = re.compile(r"(?P<name>.*)_size")


@dataclasses.dataclass
class ConvertorSize:
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
    def from_dict(
        cls,
        available_convertors: List[Convertor],
        logger: Logger,
        optimisation_inputs: Dict[str, Any],
    ) -> Any:
        """
        Returns a :class:`OptimisationParameters` instance based on the input info.

        Inputs:
            - available_convertors:
                The `list` of :class:`conversion.Convertor` instances that are defined
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

        # Parse the convertors that are to be optimised.
        convertor_sizing_inputs: Dict[str, Dict[str, float]] = {
            key: value  # type: ignore
            for key, value in optimisation_inputs.items()
            if CONVERTOR_SIZE_REGEX.match(key) is not None
        }
        convertor_sizing_inputs = {
            CONVERTOR_SIZE_REGEX.match(key).group(CONVERTOR_NAME_STRING): value
            for key, value in convertor_sizing_inputs.items()
            if CONVERTOR_SIZE_REGEX.match(key).group(CONVERTOR_NAME_STRING)
            in {convertor.name for convertor in available_convertors}
        }
        convertor_name_to_convertor = {
            convertor.name: convertor for convertor in available_convertors
        }
        try:
            convertor_sizes: Dict[Convertor, ConvertorSize] = {
                convertor_name_to_convertor[key]: ConvertorSize(
                    entry[MAX], entry[MIN], entry[STEP]
                )
                for key, entry in convertor_sizing_inputs.items()
            }
        except KeyError:
            logger.error(
                "%sNot all information was provided for the convertors defined within "
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


def save_optimisation(
    logger: Logger,
    optimisation_inputs: OptimisationParameters,
    optimisation_number: int,
    output: str,
    output_directory: str,
    system_appraisals: List[SystemAppraisal],
) -> None:
    """
    Saves simulation outputs to a .csv file

    Inputs:
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
        "system_appraisals": system_appraisals_dict,
    }

    with tqdm(total=1, desc="saving output files", leave=False, unit="file") as pbar:
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
