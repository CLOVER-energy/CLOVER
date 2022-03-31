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
import sys
from typing import Any, List

from ..__main__ import main as clover_main
from ..__utils__ import BColours, get_logger
from .hpc_utils import (
    HpcOptimisation,
    HpcSimulation,
    parse_args_and_hpc_input_file,
)


__all__ = "main"

# HPC Job Number:
#   Name of the environment variable for the HPC job number.
HPC_JOB_NUMBER: str = "PBS_ARRAY_INDEX"


# Logger name:
#   The name to use for the logger for this script.
LOGGER_NAME: str = "hpc_run_{}"


def main(args: List[Any]) -> None:
    """
    Wrapper around CLOVER when run on the HPC.

    """

    # Determine the run that is to be carried out.
    hpc_job_number = int(os.getenv(HPC_JOB_NUMBER))
    logger = get_logger(LOGGER_NAME.format(hpc_job_number), False)

    # Call the utility module to parse the HPC run information.
    logger.info("Parsing HPC input file.")
    _, runs = parse_args_and_hpc_input_file(args, logger)
    logger.info("HPC input file successfully parsed.")

    # Determine the run.
    try:
        run = runs[hpc_job_number]
    except IndexError:
        logger.error(
            "%sRun number %s out of bounds. Only %s runs submitted.%s",
            BColours.fail,
            hpc_job_number,
            len(runs),
            BColours.endc,
        )
    logger.info("Run successfully determined: %s", str(run))

    # Setup the arguments to pass to CLOVER.
    clover_arguments = [
        "--location",
        run.location,
    ]

    if isinstance(run, HpcOptimisation):
        logger.info("Run %s is an optimisation.", hpc_job_number)
        clover_arguments.append("--optimisation")
    elif isinstance(run, HpcSimulation):
        logger.info("Run %s is a simulation.", hpc_job_number)
        clover_arguments.extend(
            [
                "--simulation",
                "--pv-system-size",
                run.pv_system_size,
                "--storage-size",
                run.storage_size,
            ]
        )

    if run.total_load:
        clover_arguments.extend(["--electric-load-profile", run.total_load_file])

    # Call CLOVER with this information.
    clover_main(clover_arguments, True, hpc_job_number)


if __name__ == "__main__":
    main(sys.argv[1:])
