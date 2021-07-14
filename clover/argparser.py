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

__all__ = (
    "parse_args",
    "validate_args",
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

    """

    if parsed_args.location is None:
        logger.error("The required argument, 'location', was not specified.")
        return False

    return True
