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

from .__utils__ import BColours, DEFAULT_SCENARIO

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

    # Misc. arguments.
    # Fast mode:
    #   Used for debugging purposes to run with fsat models.
    parser.add_argument(
        "--debug", "-d", action="store_true", default=False, help=argparse.SUPPRESS
    )
    # Verbose:
    #   Used for generating verbose logs for debugging.
    parser.add_argument(
        "--verbose", "-v", action="store_true", default=False, help=argparse.SUPPRESS
    )

    # Mandatory arguments regardless of the use case.
    mandatory_arguments = parser.add_argument_group("mandatory arguments")
    mandatory_arguments.add_argument(
        "--location",
        "-l",
        type=str,
        help="The name of the location for which to run CLOVER.",
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
        "--electric-load-profile",
        "-el",
        type=str,
        help="The name of the load profile to use for the run. This overrides CLOVER's "
        "in-built load-profile generation.",
    )
    action_arguments.add_argument(
        "--output",
        "-o",
        type=str,
        help="The location of the output file in which simulation data will be saved.",
    )
    action_arguments.add_argument(
        "--pv-system-size",
        "-pv",
        type=float,
        help="The size of the PV system being modelled in PV panel units, defaulting "
        "to kWp.",
    )
    action_arguments.add_argument(
        "--scenario",
        "-s",
        type=str,
        default=DEFAULT_SCENARIO,
        help="The name of the scenario to use for the run.",
    )
    action_arguments.add_argument(
        "--storage-size",
        "-b",
        type=float,
        help="The size of the battery system being modelled in battery units, "
        "defaulting to kWh.",
    )

    # Clean-water-specific arguments.
    clean_water_parser = parser.add_argument_group(
        "clean-water-only arguments",
    )
    clean_water_parser.add_argument(
        "--num-clean-water-tanks",
        "-ncwt",
        default=0,
        type=int,
        help="The number of clean-water tanks to be included in the system.",
    )
    clean_water_parser.add_argument(
        "--clean-water-pvt-system-size",
        "-cwpvt",
        type=float,
        help="The size of the PV-T system being modelled, associated with the "
        "clean-water supply system, in PV-T panel units.",
    )

    # Hot-water-specific arguments.
    hot_water_parser = parser.add_argument_group(
        "hot-water-only arguments",
    )
    hot_water_parser.add_argument(
        "--num-hot-water-tanks",
        "-nhwt",
        default=0,
        type=int,
        help="The number of hpt-water tanks to be included in the system.",
    )
    hot_water_parser.add_argument(
        "--hot-water-pvt-system-size",
        "-hwpvt",
        type=float,
        help="The size of the PV-T system being modelled, associated with the "
        "hot-water supply system, in PV-T panel units.",
    )

    # Simulation-specific arguments.
    simulation_parser = parser.add_argument_group(
        "simulation-only arguments",
    )
    simulation_parser.add_argument(
        "--simulation",
        "-sim",
        action="store_true",
        default=False,
        help="If specified, CLOVER will carry out a single simulation.",
    )
    simulation_parser.add_argument(
        "--analyse",
        "-a",
        action="store_true",
        default=False,
        help="If specified, plots will be generated and saved and key results will be "
        "calculated and saved for the simulation.",
    )
    simulation_parser.add_argument(
        "--skip-plots",
        "-sp",
        action="store_true",
        default=False,
        help="If specified, plots will be skipped. Note, only affects cases where "
        "analysis has been requested; plot generation cannot be carried out without "
        "analysis.",
    )

    # Optimisation arguments
    optimisation_parser = parser.add_argument_group(
        "optimisation-only arguments",
    )
    optimisation_parser.add_argument(
        "--optimisation",
        "-opt",
        action="store_true",
        default=False,
        help="If specified, CLOVER will carry out optimisations in accordance with "
        "the `optimisation_inputs` file.",
    )
    action_arguments.add_argument(
        "--optimisation-inputs-file",
        "-opt-file",
        type=str,
        help="The name of the optimisation inputs file to use for the run. This "
        "overrides CLOVER's in-built optimisation inputs filename.",
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

    if parsed_args.simulation and parsed_args.optimisation:
        logger.error(
            "%sCannot run both a simulation and an optimisation.%s",
            BColours.fail,
            BColours.endc,
        )
        return False

    if parsed_args.electric_load_profile is not None and parsed_args.regenerate:
        logger.error(
            "%sCannot request profile regeneration if a total-load profile is "
            "specified.%s",
            BColours.fail,
            BColours.endc,
        )
        return False

    return True
