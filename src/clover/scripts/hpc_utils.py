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

from dataclasses import dataclass
from typing import List, Optional, Union

from ..__utils__ import OperatingMode, read_yaml


__all__ = (
    "HpcRunType",
    "HpcOptimisation",
    "HpcSimulation",
    "parse_args_and_hpc_input_file"
)


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

    def __init__(self, location: str, total_load: bool, total_load_file: Optional[str] = None) -> None:
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


class HpcOptimisation(_BaseHpcRun, type=HpcRunType.OPTIMISATION):
    """
    Represents an optimisation to be carried out on the HPC.

    """

    pass

class HpcSimulation(_BaseHpcRun, type=HpcRunType.SIMULATION):
    """
    Representst a simulation, or multiple simulations, to be carried out on the HPC.

    .. attribute:: scenario
        The name of the scenario to use.

    """

    def __init__(self, location: str, scenario: str, total_load: bool, total_load_file: Optional[str] = None) -> None:
        """
        Instantiate a :class:`HpcSimulation` instance.

        Inputs:
            - location:
                The name of the location to use for the simulation(s).
            - scenario:
                The scenario to use for the simulation(s).
            - total_load:
                Whether a total-load file should be used for the simulation(s).
            - total_load_file:
                If being used, the name of the total-load file for the simulation(s).

        """

        super().__init__(location, total_load, total_load_file)
        self.scenario = scenario


def _parse_hpc_args() -> argparse.Namespace:
    """
    Parses the input arguments to the hpc script to determine the HPC input file.

    Inputs:
        - args:
            Unparsed command-line arguments.

    Outputs:
        - The parsed HPC arguments.

    """


def _process_hpc_input_file() -> List[Union[HpcOptimisation, HpcSimulation]]:
    """
    Parses the HPC input file.

    Outputs:
        - A `list` of the hpc optimisations and simulations to be carried out.

    """

    # Open the file and extract the YAML data.
    # Parse this into HPC Optimisations and Simulations.
    # Return this list of HPC optimisations and simulations.


def parse_args_and_hpc_input_file(args) -> List[Union[HpcOptimisation, HpcSimulation]]:
    """
    Parses command-line arguments and returns the HPC runs to be carried out.

    Inputs:
        - args:
            Unparsed command-line arguments.

    Outputs:
        - A `list` of the hpc optimisations and simulations to be carried out.

    """

    # Parse the arguments to determine the input file.
    # Check that the input file exists, and error if not.
    # Parse the input file to determine the runs to be carried out.
    # Return these runs.

