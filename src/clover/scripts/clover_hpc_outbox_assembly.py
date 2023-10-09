#!/usr/bin/env python
########################################################################################
# clover_hpc_outbox_assembly.py - Entry point for running CLOVER's HPC outbox assembly #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 08/03/2022                                                             #
# License: Open source                                                                 #
########################################################################################
"""
clover_hpc_outbox_assembly.py - Entry point for running CLOVER's HPC outbox script.

CLOVER can be run on Imperial College London's high-performance computers (HPC)s. In
order to do so as an installed piece of software, this wrapper provides an entry point
for the code once installed in order to assembly the optimisation output files.

"""

import sys

from .hpc_outbox_assembly import main as hpc_outbox_assembly_main


def main() -> None:
    """
    Main function of the CLOVER-HPC entry-point script.

    """

    hpc_outbox_assembly_main(sys.argv[1:])
