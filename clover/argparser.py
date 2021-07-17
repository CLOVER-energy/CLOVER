#!/usr/bin/python3
########################################################################################
# argparser.py - Argument-parsing code for CLOVER.
#
# Author: Ben Winchester
# Copyright: Ben Winchester, 2021
# Date created: 13/07/2021
# License: Open source
########################################################################################
"""
argparser.py - The argument-parsing module for CLOVER.

"""

import argparse
import logging

from typing import Any, List

from .__utils__ import BColours, OperatingMode

__all__ = (
    "parse_args",
    "validate_args",
)


class MissingParametersError(Exception):
    """
    Raised when not all parameters have been specified on the command line.

    """

    def __init__(self, missing_parameter: str) -> None:
        """
        Instantiate a missing parameters error.

        Inputs:
            - missing_parameter:
                The parameter which has not been specified.

        """

        super().__init__(
            f"Missing command-line parameters: {missing_parameter}. "
            + "Run `clover --help` for more information."
        )


def parse_args(args: List[Any]) -> argparse.Namespace:
    """
    Parses command-line arguments into a :class:`argparse.NameSpace`.

    """

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "mode",
        type=str,
        help="The mode to run CLOVER in: 'profile_generation', 'simulation' or 'optimisation'.",
    )

    # Mandatory arguments regardless of the use case.
    mandatory_arguments = parser.add_argument_group("mandatory arguments")
    mandatory_arguments.add_argument(
        "--location", type=str, help="The name of the location for which to run CLOVER."
    )

    # Arguments used only when specifying how profiles should be generated or used.
    profile_arguments = parser.add_argument_group("profile arguments")
    profile_arguments.add_argument(
        "--regenerate",
        action="store_true",
        default=False,
        help="If specified, CLOVER will regenerate the various profiles used. "
        "Otherwise, existing profiles will be used if present.",
    )

    # Argumnets in common to both simulations and optimisations
    action_arguments = parser.add_argument_group(
        "simulation and optimisation arguments",
    )
    action_arguments.add_argument(
        "--load-profile",
        type=str,
        help="The name of the load profile to use for the run.",
    )
    action_arguments.add_argument(
        "--output",
        type=str,
        help="The location of the output file in which simulation data will be saved.",
    )
    action_arguments.add_argument(
        "--pv-system-size",
        type=float,
        help="The size of the PV system being modelled in kWp.",
    )
    action_arguments.add_argument(
        "--scenario",
        type=str,
        help="The location of the scenario file to use for the run.",
    )
    action_arguments.add_argument(
        "--storage-size",
        type=float,
        help="The size of the battery system being modelled in kWh.",
    )

    # Simulation-specific arguments.
    simulation_parser = parser.add_argument_group(
        "simulation-only arguments",
    )

    # Optimisation arguments
    optimisation_parser = parser.add_argument_group(
        "optimisation-only arguments",
    )
    optimisation_parser.add_argument(
        "--optimisation",
        type=str,
        help="The location of the optimisation file to use for the run, specifying the "
        "various optimisations to be carried out.",
    )

    return parser.parse_args(args)


def validate_args(logger: logging.Logger, parsed_args: argparse.Namespace) -> bool:
    """
    Validates the command-line arguments passed in.

    Inputs:
        - parsed_args
            The parsed command-line arguments.

    Outputs:
        - A boolean giving whether the arguments are valid (True) or not (False).

    Raises: MissingParameterError
        - Raised when a CLI parameter is missing.

    """

    if parsed_args.location is None:
        logger.error(
            "%sThe required argument, 'location', was not specified.%s",
            BColours.fail,
            BColours.endc,
        )
        raise MissingParametersError("location")

    if parsed_args.mode is None:
        logger.error(
            "%sThe mode of operation must be specified.%s", BColours.fail, BColours.endc
        )
        raise MissingParametersError("mode")

    if parsed_args.mode == OperatingMode.SIMULATION:
        if parsed_args.pv_system_size is None:
            logger.error(
                "%sIf running a simulation, the pv system size must be specified.%s",
                BColours.fail,
                BColours.endc,
            )
            raise MissingParametersError("pv-system-size")

        if parsed_args.storage_size is None:
            logger.error(
                "%sIf running a simulation, the storage size must be specified.%s",
                BColours.fail,
                BColours.endc,
            )
            raise MissingParametersError("storage size")

    return True
