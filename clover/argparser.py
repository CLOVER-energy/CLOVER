#!/usr/bin/python3
########################################################################################
# argparser.py - Argument-parsing code for CLOVER.                                     #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 13/07/2021                                                             #
# License: Open source                                                                 #
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

    # Mandatory arguments regardless of the use case.
    mandatory_arguments = parser.add_argument_group("mandatory arguments")
    mandatory_arguments.add_argument(
        "--location", type=str, help="The name of the location for which to run CLOVER."
    )

    # Arguments used only when specifying how profiles should be generated or used.
    profile_arguments = parser.add_argument_group("profile arguments")
    profile_arguments.add_argument(
        "--refetch",
        action="store_true",
        default=False,
        help="If specified, CLOVER will refetch the various profiles used from the "
        "renewables.ninja API. Otherwise, existing profiles will be used if present.",
    )
    profile_arguments.add_argument(
        "--regenerate",
        action="store_true",
        default=False,
        help="If specified, CLOVER will regenerate the various profiles used. "
        "Otherwise, existing profiles will be used if present.",
    )

    # Arguments in common to both simulations and optimisations
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
    clean_water_parser = parser.add_argument_group(
        "clean-water-only arguments",
    )
    clean_water_parser.add_argument(
        "--num-clean-water-tanks",
        default=0,
        type=int,
        help="The number of clean-water tanks to be included in the system.",
    )

    # Simulation-specific arguments.
    simulation_parser = parser.add_argument_group(
        "simulation-only arguments",
    )
    simulation_parser.add_argument(
        "--simulation",
        action="store_true",
        default=False,
        help="If specified, CLOVER will carry out a single simulation.",
    )
    simulation_parser.add_argument(
        "--analyse",
        action="store_true",
        default=False,
        help="If specified, plots will be generated and saved and key results will be "
        "calculated and saved for the simulation.",
    )

    # Optimisation arguments
    optimisation_parser = parser.add_argument_group(
        "optimisation-only arguments",
    )
    optimisation_parser.add_argument(
        "--optimisation",
        action="store_true",
        default=False,
        help="If specified, CLOVER will carry out optimisations in accordance with "
        "the `optimisation_inputs` file.",
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

    if parsed_args.simulation:
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

    if parsed_args.simulation and parsed_args.optimisation:
        logger.error(
            "%sCannot run both a simulation and an optimisation.%s",
            BColours.fail,
            BColours.endc,
        )
        return False

    return True
