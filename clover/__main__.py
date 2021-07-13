#!/usr/bin/python3
########################################################################################
# __main__.py - Main module for CLOVER.
#
# Author: Ben Winchester
# Copyright: Ben Winchester, 2021
# Date created: 13/07/2021
# License: Open source
########################################################################################
"""
__main__.py - The main module for CLOVER.

CLOVER (Continuous Lifetime Optimisation of Variable Electricity Resources) can evaluate
and optimise minigrid systems, determining whether a demand is met whilst minimising
environmental and economic impacts. The main flow of CLOVER can be executed by running
the clover module from the command-line interface.

"""

import sys

from typing import Any, List

from .argparser import parse_args
from .__utils__ import get_logger

# Logger name:
#   The name to use for the main logger for CLOVER
LOGGER_NAME = "clover"


def main(args: List[Any]) -> None:
    """
    The main module for CLOVER executing all functionality as appropriate.

    Inputs:
        - args
            The command-line arguments, passed in as a list.

    """

    logger = get_logger(LOGGER_NAME)
    logger.info("CLOVER run initiated. Options specified: %s", " ".join(args))

    parsed_args = parse_args(args)
    logger.info("Command-line arguments successfully parsed.")

    # ******* #
    # *  1  * #
    # ******* #

    # If the location does not exist or does not meet the required specification, then
    # exit now.
    if _check_location(parsed_args.location):
        # Provide the user with information on what they should do to get CLOVER running
        # correctly.
        sys.exit(1)

    # ******* #
    # *  2  * #
    # ******* #

    # * Generate the profiles where appropriate based on the arguments passed in.
    # * Generate and save the PV profiles.
    # * Generate and save the grid-availibility profiles.
    # * Generate and save any additional profiles, such as diesel-generator profiles.

    # ******* #
    # *  3  * #
    # ******* #

    # * Run a simulation or optimisation as appropriate.

    # ******* #
    # *  4  * #
    # ******* #

    # * Run any and all analysis as appropriate.


if __name__ == "__main__":
    main(sys.argv[1:])
