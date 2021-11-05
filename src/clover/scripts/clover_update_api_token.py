#!/usr/bin/env python
########################################################################################
# clover_update_api_token.py - Entry point for updating renewable.ninja api tokens.    #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 21/09/2021                                                             #
# License: Open source                                                                 #
########################################################################################
"""
clover_update_api_token.py - Entry point for updating location API tokens.

CLOVER works on the basis of locations. The solar, wind and weather data for these
locations is fetched from the freely-accessible online renewables.ninja resource. In
order to properly download these data, each user must specify a unique API, which must
be entered as an input to CLOVER in order for it to properly function.

"""

import sys

from .update_api_token import main as update_api_token_main


def main() -> None:
    """
    Main function of the update-api-token entry-point script.

    """

    update_api_token_main(sys.argv[1:])
