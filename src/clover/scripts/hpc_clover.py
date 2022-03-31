#!/usr/bin/python3
########################################################################################
# hpc_clover.py - Entry point for running CLOVER on Imperial College's HPC.            #
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
hpc_clover.py - The entry point for running CLOVER on the HPC.

Imperial College London owns a series of high-performance computers. This module
provides an entry point for running CLOVER across the various HPC computers.

"""

import os
import subprocess
import sys
import tempfile

from logging import Logger
from typing import Union

from ..__utils__ import LOCATIONS_FOLDER_NAME, BColours, get_logger
from ..fileparser import INPUTS_DIRECTORY, LOAD_INPUTS_DIRECTORY, parse_scenario_inputs
from .hpc_utils import (
    HpcOptimisation,
    HpcRunType,
    HpcSimulation,
    InvalidRunError,
    parse_args_and_hpc_input_file,
)


# Hpc submission script file:
#   The path to the HPC script submission file.
HPC_SUBMISSION_SCRIPT_FILE: str = os.path.join("bin", "hpc.sh")

# Logger name:
#   The name to use for the logger for this script.
LOGGER_NAME: str = "hpc_clover"


def _check_run(logger: Logger, run: Union[HpcOptimisation, HpcSimulation]) -> bool:
    """
    Checks that the HPC run is valid.

    Inputs:
        - logger:
            The logger to use for the run.
        - run:
            The HPC run to carry out.

    Outputs:
        - Whether the run is valid or not.

    """

    # Check that the locations folder exists.
    if not os.path.isfile(os.path.join(LOCATIONS_FOLDER_NAME, run.location)):
        logger.error(
            "%sLocation '%s' does not exist.%s",
            BColours.fail,
            run.location,
            BColours.endc,
        )
        return False

    # Check that the total load file exists if specified.
    if run.total_load_file is not None and not os.path.isfile(
        os.path.join(
            LOCATIONS_FOLDER_NAME,
            run.location,
            LOAD_INPUTS_DIRECTORY,
            run.total_load_file,
        )
    ):
        logger.error(
            "%sThe total run file '%s' could not be found in the load inputs directory."
            "%s",
            BColours.fail,
            run.total_load_file,
            BColours.endc,
        )
        return False

    # Check that the scenario exists as a scenario.
    if run.type == HpcRunType.SIMULATION:
        # Parse the scenario files for the location.
        logger.info("%sParsing scenario input file.%s", BColours.fail, BColours.endc)
        _, _, scenarios, _ = parse_scenario_inputs(
            os.path.join(LOCATIONS_FOLDER_NAME, run.location, INPUTS_DIRECTORY), logger
        )

        if run.scenario not in {scenario.name for scenario in scenarios}:
            logger.error(
                "%sScenario '%s' not in the scenarios file.%s",
                BColours.fail,
                run.scenario,
                BColours.endc,
            )
            return False

    # Returns false if not.
    return True


def main(args) -> None:
    """
    Wrapper around CLOVER when run on the HPC.

    """

    logger = get_logger(LOGGER_NAME, False)
    logger.info("HPC-CLOVER script called.")

    # Call the utility module to parse the HPC run information.
    run_file, runs = parse_args_and_hpc_input_file(args, logger)
    logger.info("Command-line arguments successfully parsed. Run file: %s", runs)

    # Check that all of the runs are valid.
    logger.info("Checking all run files are valid.")
    if not all(_check_run(logger, run) for run in runs):
        logger.error(
            "%sNot all HPC runs were valid, exiting.%s", BColours.fail, BColours.endc
        )
        raise InvalidRunError("Not all HPC runs were valid, see logs for details.")

    logger.info("All HPC runs valid.")

    # Parse the default HPC job submission script.
    logger.info("Parsing base HPC job submission script.")
    try:
        with open(HPC_SUBMISSION_SCRIPT_FILE, "r") as f:
            hpc_submission_script_file_contents = f.read()
    except FileNotFoundError:
        logger.error(
            "%sHPC job submission file not found. Check that the file, '%s', has not "
            "been removed.%s",
            BColours.fail,
            HPC_SUBMISSION_SCRIPT_FILE,
            BColours.endc,
        )
        raise

    logger.info("HPC job submission file successfully parsed.")

    hpc_submission_script_file_contents.format(len(runs))
    logger.info("HPC job submission script updated with %s runs.", len(runs))

    # Setup the HPC job submission script.
    with tempfile.TemporaryDirectory() as tmpdirname:
        hpc_submission_script_filepath = os.path.join(
            tmpdirname, HPC_SUBMISSION_SCRIPT_FILE
        )

        # Write the submission script file.
        logger.info("Writing temporary HPC submission script.")
        with open(hpc_submission_script_filepath, "w") as f:
            f.write(hpc_submission_script_file_contents)

        logger.info("HPC job submission script successfully submitted.")

        # Submit the script to the HPC.
        logger.info("Submitting CLOVER jobs to the HPC.")
        subprocess.run(
            [hpc_submission_script_filepath, "--runs", run_file], check=False
        )
        logger.info("HPC runs submitted. Exiting.")


if __name__ == "__main__":
    main(sys.argv[1:])
