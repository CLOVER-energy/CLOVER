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
    HpcRunType,
    HpcSimulation,
    InvalidRunError,
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
    _, runs, verbose = parse_args_and_hpc_input_file(args, logger)
    logger.info("HPC input file successfully parsed.")

    # Determine the run.
    try:
        hpc_run = runs[hpc_job_number - 1]
    except IndexError:
        logger.error(
            "%sRun number %s out of bounds. Only %s runs submitted.%s",
            BColours.fail,
            hpc_job_number,
            len(runs),
            BColours.endc,
        )
        raise
    logger.info("Run successfully determined: %s", str(hpc_run))

    # Setup the arguments to pass to CLOVER.
    clover_arguments = [
        "--location",
        hpc_run.location,
    ]

    if hpc_run.type == HpcRunType.OPTIMISATION:
        logger.info("Run %s is an optimisation.", hpc_job_number)
        clover_arguments.append("--optimisation")
    elif hpc_run.type == HpcRunType.SIMULATION:
        logger.info("Run %s is a simulation.", hpc_job_number)
        clover_arguments.extend(
            [
                "--simulation",
                "--pv-system-size",
                str(hpc_run.pv_system_size),
                "--storage-size",
                str(hpc_run.storage_size),
            ]
        )
    else:
        logger.error(
            "%sRun %s was not a supported run type. Supported run types are %s.%s",
            BColours.fail,
            hpc_job_number,
            ", ".join(str(e.value) for e in HpcRunType),
            BColours.endc,
        )
        raise InvalidRunError(f"Run {hpc_job_number} was not of a supported run type.")

    if hpc_run.total_load:
        clover_arguments.extend(["--electric-load-profile", hpc_run.total_load_file])

    if verbose:
        clover_arguments.append("--verbose")

    # Call CLOVER with this information.
    logger.info("Calling CLOVER with arguments: %s", " ".join(clover_arguments))
    clover_main(clover_arguments, True, hpc_job_number)


if __name__ == "__main__":
    main(sys.argv[1:])
