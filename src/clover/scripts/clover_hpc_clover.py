#!/usr/bin/env python
########################################################################################
# clover_hpc_clover.py - Entry point for running CLOVER on Imperial College's HPC.     #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 08/03/2022                                                             #
# License: Open source                                                                 #
########################################################################################
"""
clover_hpc_clover.py - Entry point for running CLOVER on the HPC.

CLOVER can be run on Imperial College London's high-performance computers (HPC)s. In
order to do so as an installed piece of software, this wrapper provides an entry point
for the code once installed.

"""

import sys

from .hpc_clover import main as hpc_clover_main


def main() -> None:
    """
    Main function of the CLOVER-HPC entry-point script.

    """

    hpc_clover_main(sys.argv[1:])
