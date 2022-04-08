#!/usr/bin/python3
########################################################################################
# __utils__.py - CLOVER Scripts Utility module.                                        #
#                                                                                      #
# Author: Phil Sandwell, Ben Winchester                                                #
# Copyright: Phil Sandwell, 2018                                                       #
# Date created: 249/03/2022                                                             #
#                                                                                      #
# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
__utils__.py - Utility module for CLOVER's Scripts Component.

The utility module contains functionality which is used by the various scripts within
CLOVER designed to improve ease of use.

"""

import argparse
import enum

from logging import Logger
from typing import Any, Dict, List, Optional, Tuple, Union

from ..__utils__ import DEFAULT_SCENARIO, BColours, read_yaml


__all__ = (
    "HpcRunType",
    "HpcOptimisation",
    "HpcSimulation",
    "parse_args_and_hpc_input_file",
)

# False:
#   Keyword for parsing no total-load file info.
FALSE: str = "false"

# Type:
#   Keyword used for parsing the type of run taking place.
TYPE: str = "type"


class HpcRunType(enum.Enum):
    """
    Denotes the type of run being carried out on the HPC.

    - SIMULATION:
        Denotes a simulation or multiple simulations.

    - OPTIMISATION:
        Denotes an optimisation or multiple optimisations.

    """

    SIMULATION = "simulation"
    OPTIMISATION = "optimisation"


class InvalidRunError(Exception):
    """Raised when an HPC run is invalid."""

    def __init__(self, msg: str) -> None:
        """
        Instantiate an invalid run error.

        Inputs:
            - msg:
                Message to append.

        """

        super().__init__(f"Invalid HPC run in hpc inputs file: {msg}")


class _BaseHpcRun:
    """
    Represents a base run that can be carried out on the HPC.

    .. attribute:: location
        The name of the location.

    .. attribute:: total_load
        Whether a total-load file is being used (True) or not (False).

    .. attribute:: total_load_file
        The name of the total-load file, if relevant.

    .. attribute:: type:
        Whether an optimisation or simulation is being run.

    """

    type: HpcRunType

    def __init__(
        self, location: str, total_load: bool, total_load_file: Optional[str] = None
    ) -> None:
        """
        Instantiate a :class:`_BaseHpcRun` instance.

        Inputs:
            - location:
                The name of the location to use.
            - total_load:
                Whether a total-load file should be used.
            - total_load_file:
                If being used, the name of the total-load file.

        """

        self.location = location
        self.total_load = total_load
        self.total_load_file = total_load_file

    def __init_subclass__(cls, type: HpcRunType) -> None:
        """
        Method run when instantiating a :class:`BaseRenewablesNinjaThread` child.

        Inputs:
            - profile_name:
                The name of the profile that is being generated.

        """

        super().__init_subclass__()
        cls.type = type

    def __str__(self) -> str:
        """
        Returns a nice-looking `str` representing the run.

        Outputs:
            - A nice-looking `str` representing the run.

        """

        return (
            f"HpcRun(type={self.type}, location={self.location}"
            + f", total_load={self.total_load}"
            + (
                f", total_load_file={self.total_load_file}"
                if self.total_load_file is not None
                else ""
            )
            + ")"
        )


class HpcOptimisation(_BaseHpcRun, type=HpcRunType.OPTIMISATION):
    """
    Represents an optimisation to be carried out on the HPC.

    """

    pass

    @classmethod
    def from_dict(cls, input_data: Dict[str, Any], logger: Logger) -> Any:
        """
        Creates a :class:`HpcOptimisation` instance based on the inputs provided.

        Inputs:
            - input_data:
                The input information, extracted from the HPC inputs file.
            - logger:
                The logger being used for the run.

        Outputs:
            - A :class:`HpcOptimisation` instance based on the input information provided.

        """

        total_load_input: Union[str, bool] = input_data.get("total_load", False)

        if not total_load_input:
            total_load: bool = False
            total_load_file: Optional[str] = None
        elif not isinstance(total_load_input, str):
            logger.error(
                "%sCannot set total-load to be `true`.%s", BColours.fail, BColours.endc
            )
            raise InvalidRunError(
                "Cannot set total-load file to be `true` in HPC input file. Either "
                "`false` or the name of the file can be used."
            )
        else:
            total_load = True
            total_load_file = total_load_input

        return cls(input_data["location"], total_load, total_load_file)


class HpcSimulation(_BaseHpcRun, type=HpcRunType.SIMULATION):
    """
    Representst a simulation, or multiple simulations, to be carried out on the HPC.

    .. attribute:: pv_system_size
        The size of the PV system.

    .. attribute:: scenario
        The name of the scenario to use.

    .. attribute:: storage_size
        The size of the storage installed.

    """

    def __init__(
        self,
        location: str,
        pv_system_size: float,
        scenario: str,
        storage_size: float,
        total_load: bool,
        total_load_file: Optional[str] = None,
    ) -> None:
        """
        Instantiate a :class:`HpcSimulation` instance.

        Inputs:
            - location:
                The name of the location to use for the simulation(s).
            - pv_system_size:
                The size of the PV system installed.
            - scenario:
                The scenario to use for the simulation(s).
            - storage_size:
                The size of the storage system installed.
            - total_load:
                Whether a total-load file should be used for the simulation(s).
            - total_load_file:
                If being used, the name of the total-load file for the simulation(s).

        """

        super().__init__(location, total_load, total_load_file)
        self.pv_system_size = pv_system_size
        self.scenario = scenario
        self.storage_size = storage_size

    @classmethod
    def from_dict(cls, input_data: Dict[str, Any], logger: Logger) -> Any:
        """
        Creates a :class:`HpcOptimisation` instance based on the inputs provided.

        Inputs:
            - input_data:
                The input information, extracted from the HPC inputs file.
            - logger:
                The logger being used for the run.

        Outputs:
            - A :class:`HpcOptimisation` instance based on the input information provided.

        """

        total_load_input: str = input_data.get("total_load", False)

        if not total_load_input:
            total_load: bool = False
            total_load_file: Optional[str] = None
        else:
            total_load = True
            total_load_file = total_load_input

        try:
            pv_system_size: float = float(input_data["pv_system_size"])
        except KeyError:
            logger.error(
                "%sMissing pv system size information.%s", BColours.fail, BColours.endc
            )
            raise InvalidRunError("Missing pv system size information in input file.")
        except ValueError:
            logger.error(
                "%PV system size must be either an integer or float, `str` is not "
                "allowed.%s",
                BColours.fail,
                BColours.endc,
            )

        scenario: str = input_data.get("scenario", DEFAULT_SCENARIO)

        try:
            storage_size: float = float(input_data["storage_size"])
        except KeyError:
            logger.error(
                "%sMissing storage size information.%s", BColours.fail, BColours.endc
            )
            raise InvalidRunError("Missing storage size information in input file.")
        except ValueError:
            logger.error(
                "%sStorage size must be either an integer or float, `str` is not "
                "allowed.%s",
                BColours.fail,
                BColours.endc,
            )

        return cls(
            input_data["location"],
            pv_system_size,
            scenario,
            storage_size,
            total_load,
            total_load_file,
        )


def _parse_hpc_args(args: List[Any]) -> argparse.Namespace:
    """
    Parses the input arguments to the hpc script to determine the HPC input file.

    Inputs:
        - args:
            Unparsed command-line arguments.

    Outputs:
        - The parsed HPC arguments.

    """

    parser = argparse.ArgumentParser()

    # Runs:
    #   The name of the HPC runs file.
    parser.add_argument("--runs", "-r", type=str, help="The path to the HPC runs file.")

    # Verbose:
    #   Used for generating verbose logs for debugging.
    parser.add_argument(
        "--verbose", "-v", action="store_true", default=False, help=argparse.SUPPRESS
    )

    return parser.parse_args(args)


def _parse_hpc_input_file(input_filename: str, logger: Logger) -> List[Dict[str, Any]]:
    """
    Parses the HPC input file into a dictionary.

    Inputs:
        - input_filename:
            The name of the input file for the HPC runs.
        - logger:
            The :class:`logging.Logger` to use for the run.

    Outputs:
        - The raw data

    """

    # Open the file and extract the YAML data.
    try:
        filedata = read_yaml(input_filename, logger)
    except FileNotFoundError:
        logger.error(
            "%sHPC input file '%s' could not be found.%s",
            BColours.fail,
            input_filename,
            BColours.endc,
        )
        raise

    # Raise an error if the format of the file is invalid.
    if not isinstance(filedata, list):
        logger.error(
            "%sHPC input file '%s' was not of format `list`.%s",
            BColours.fail,
            input_filename,
            BColours.endc,
        )
        raise

    logger.info("HPC input successfully parsed.")

    return filedata


def _process_hpc_input_file(
    input_filename: str, logger: Logger
) -> List[Union[HpcOptimisation, HpcSimulation]]:
    """
    Parses the HPC input file into a list of runs.

    Inputs:
        - input_filename:
            The name of the input file for the HPC runs.
        - logger:
            The :class:`logging.Logger` to use for the run.

    Outputs:
        - A `list` of the hpc optimisations and simulations to be carried out.

    """

    # Parse the HPC input file.
    filedata = _parse_hpc_input_file(input_filename, logger)

    # Parse this into HPC Optimisations and Simulations.
    runs: List[Union[HpcOptimisation, HpcSimulation]] = []
    for entry in filedata:
        if entry[TYPE] == HpcRunType.OPTIMISATION.value:
            runs.append(HpcOptimisation.from_dict(entry, logger))
        elif entry[TYPE] == HpcRunType.SIMULATION.value:
            runs.append(HpcSimulation.from_dict(entry, logger))
        else:
            logger.error(
                "%sInvalid HPC run type '%s'. Valid types are %s.%s",
                BColours.fail,
                entry[TYPE],
                ", ".join([str(e.value) for e in HpcRunType]),
                BColours.endc,
            )
            raise InvalidRunError(f"Invalid HPC run type {entry[TYPE]}.")

    # Return this list of HPC optimisations and simulations.
    return runs


def parse_args_and_hpc_input_file(
    args: List[Any], logger: Logger
) -> Tuple[str, List[Union[HpcOptimisation, HpcSimulation]], bool]:
    """
    Parses command-line arguments and returns the HPC runs to be carried out.

    Inputs:
        - args:
            Unparsed command-line arguments.

    Outputs:
        - The run file name.
        - A `list` of the hpc optimisations and simulations to be carried out.

    """

    # Parse the arguments to determine the input file.
    parsed_args = _parse_hpc_args(args)
    logger.info("Command-line arguments successfully parsed.")

    # Parse the input file to determine the runs to be carried out.
    runs = _process_hpc_input_file(parsed_args.runs, logger)

    # Return these runs along with the filename.
    return parsed_args.runs, runs, parsed_args.verbose
