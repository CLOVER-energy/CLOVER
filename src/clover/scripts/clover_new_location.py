#!/usr/bin/env python
########################################################################################
# clover_new_location.py - Entry point for creating new locations.                     #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 16/09/2021                                                             #
# License: Open source                                                                 #
########################################################################################
"""
clover_new_location.py - Entry point for creating new locations.

CLOVER works on the basis of locations, and, as such, the ability to create new
locations is integral to the operation of CLOVER.

"""

import sys

from .new_location import main as new_location_main


def main() -> None:
    """
    Main function of the new-location entry-point script.

    """

    new_location_main(sys.argv[1:])
