#!/usr/bin/python3
########################################################################################
# hpc.py - Wrapper script around CLOVER when run on Imperial College's HPC.            #
#                                                                                      #
# Authors: Phil Sandwell, Ben Winchester                                               #
# Copyright: Phil Sandwell, 2022                                                       #
# Date created: 29/03/2022                                                             #
# License: Open source                                                                 #
#                                                                                      #
# For more information, please email:                                                  #
#   benedict.winchester@gmail.com                                                      #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
hpc.py - The wrapper script for running CLOVER on the HPC.

Imperial College London owns a series of high-performance computers. This module
provides a wrapper around the main functionality of CLOVER to enable it to be run on
the HPC.

"""

import os


__all__ = ("main")

# HPC Job Number:
#   Name of the environment variable for the HPC job number.
HPC_JOB_NUMBER: str = "PBS_ARRAY_INDEX"


def main(args) -> None:
    """
    Wrapper around CLOVER when run on the HPC.

    """

    # Call the utility module to parse the HPC run information.
    # Determine the run that is to be carried out.
    hpc_job_number = os.getenv(HPC_JOB_NUMBER)

    # Call CLOVER with this information.



if __name__ == "__main__":
    main(sys.argv[1:])
