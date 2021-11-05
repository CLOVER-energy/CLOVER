#!/usr/bin/env python
#!/usr/bin/python3
########################################################################################
# clover.py - Primary entry point for the CLOVER package.                              #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 16/09/2021                                                             #
# License: Open source                                                                 #
########################################################################################
"""
clover.py - Primary entry point for the CLOVER package.

CLOVER (Continuous Lifetime Optimisation of Variable Electricity Resources) can evaluate
and optimise minigrid systems, determining whether a demand is met whilst minimising
environmental and economic impacts. The main flow of CLOVER can be executed by running
the clover module from the command-line interface.

"""

import sys

from ..__main__ import main as clover_main


def main() -> None:
    """
    Main function of the CLOVER entry-point script.

    """

    clover_main(sys.argv[1:])
