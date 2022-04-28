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

import math
import os
import subprocess
import sys
import tempfile

from logging import Logger
from typing import Union

from ..__main__ import __version__
from ..__utils__ import (
    DONE,
    FAILED,
    LOCATIONS_FOLDER_NAME,
    BColours,
    ProgrammerJudgementFault,
    get_logger,
)
from ..fileparser import INPUTS_DIRECTORY, LOAD_INPUTS_DIRECTORY, parse_scenario_inputs
from .hpc_utils import (
    HpcOptimisation,
    HpcRunType,
    HpcSimulation,
    InvalidRunError,
    parse_args_and_hpc_input_file,
)

__all__ = ("main",)


# Clover hpc header string:
#   The ascii text to display when starting CLOVER on the HPC.
CLOVER_HPC_HEADER_STRING = """

        (((((*    /(((
        ((((((( ((((((((
   (((((((((((( ((((((((((((
   ((((((((((((*(((((((((((((       _____ _      ______      ________ _____
     *((((((((( ((((((((((((       / ____| |    / __ \\ \\    / /  ____|  __ \\
   (((((((. /((((((((((/          | |    | |   | |  | \\ \\  / /| |__  | |__) |
 ((((((((((((((((((((((((((,      | |    | |   | |  | |\\ \\/ / |  __| |  _  /
 (((((((((((*  (((((((((((((      | |____| |___| |__| | \\  /  | |____| | \\ \\
   ,(((((((. (  (((((((((((/       \\_____|______\\____/   \\/   |______|_|  \\_\\
   .((((((   (   ((((((((
             /     (((((
             ,
              ,
               (
                 (
                   (

                ___                     _      _   _  _ ___  ___
               |_ _|_ __  _ __  ___ _ _(_)__ _| | | || | _ \\/ __|
                | || '  \\| '_ \\/ -_) '_| / _` | | | __ |  _/ (__
               |___|_|_|_| .__/\\___|_| |_\\__,_|_| |_||_|_|  \\___|
                         |_|

       Continuous Lifetime Optimisation of Variable Electricity Resources
                         Copyright Phil Sandwell, 2018
{version_line}

   This version of CLOVER has been adapted for Imperial College London's HPC
  See the user guide for more information on how to use this version of CLOVER

                         For more information, contact
                   Phil Sandwell (philip.sandwell@gmail.com),
                    Hamish Beath (hamishbeath@outlook.com),
               or Ben Winchester (benedict.winchester@gmail.com)

"""

# Hpc submission script filename:
#   The name of the HPC script submission file.
HPC_SUBMISSION_SCRIPT_FILENAME: str = "hpc.sh"

# Hpc submission script filepath:
#   The path to the HPC script submission file.
HPC_SUBMISSION_SCRIPT_FILEPATH: str = os.path.join(
    "bin", HPC_SUBMISSION_SCRIPT_FILENAME
)

# Logger name:
#   The name to use for the logger for this script.
LOGGER_NAME: str = "hpc_clover"


def _check_run(logger: Logger, hpc_run: Union[HpcOptimisation, HpcSimulation]) -> bool:
    """
    Checks that the HPC run is valid.

    Inputs:
        - logger:
            The logger to use for the run.
        - hpc_run:
            The HPC run to carry out.

    Outputs:
        - Whether the run is valid or not.

    """

    # Check that the locations folder exists.
    if not os.path.isdir(os.path.join(LOCATIONS_FOLDER_NAME, hpc_run.location)):
        logger.error(
            "%sLocation '%s' does not exist.%s",
            BColours.fail,
            hpc_run.location,
            BColours.endc,
        )
        return False

    # Check that the total load file exists if specified.
    if hpc_run.total_load_file is not None and not os.path.isfile(
        os.path.join(
            LOCATIONS_FOLDER_NAME,
            hpc_run.location,
            INPUTS_DIRECTORY,
            LOAD_INPUTS_DIRECTORY,
            hpc_run.total_load_file,
        )
    ):
        logger.error(
            "%sThe total run file '%s' could not be found in the load inputs directory."
            "%s",
            BColours.fail,
            hpc_run.total_load_file,
            BColours.endc,
        )
        return False

    # Check that the scenario exists as a scenario.
    if hpc_run.type == HpcRunType.SIMULATION:
        if not isinstance(hpc_run, HpcSimulation):
            logger.error(
                "%sRun marked as simulation but was processed as an optimisation.%s",
                BColours.fail,
                BColours.endc,
            )
            raise ProgrammerJudgementFault(
                "hpc_clover.py", "Failure processing run as a simulation."
            )

        # Parse the scenario files for the location.
        logger.info("%sParsing scenario input file.%s", BColours.fail, BColours.endc)
        _, _, scenarios, _ = parse_scenario_inputs(
            os.path.join(LOCATIONS_FOLDER_NAME, hpc_run.location, INPUTS_DIRECTORY),
            logger,
        )

        if hpc_run.scenario not in {scenario.name for scenario in scenarios}:
            logger.error(
                "%sScenario '%s' not in the scenarios file.%s",
                BColours.fail,
                hpc_run.scenario,
                BColours.endc,
            )
            return False

    # Returns false if not.
    return True


def main(args) -> None:
    """
    Wrapper around CLOVER when run on the HPC.

    """

    version_string = f"Version {__version__}"
    print(
        CLOVER_HPC_HEADER_STRING.format(
            version_line=(
                " " * (40 - math.ceil(len(version_string) / 2))
                + version_string
                + " " * (40 - math.floor(len(version_string) / 2))
            )
        )
    )

    logger = get_logger(LOGGER_NAME, False)
    logger.info("HPC-CLOVER script called.")
    logger.info("Arguments: %s", ", ".join(args))

    # Call the utility module to parse the HPC run information.
    run_file, runs, verbose, walltime = parse_args_and_hpc_input_file(args, logger)
    logger.info("Command-line arguments successfully parsed. Run file: %s", run_file)
    logger.debug("Runs:\n%s- ", "\n- ".join(str(run) for run in runs))

    # Check that all of the runs are valid.
    print("Checking HPC runs .............................................    ", end="")
    logger.info("Checking all run files are valid.")
    if not all(_check_run(logger, run) for run in runs):
        logger.error(
            "%sNot all HPC runs were valid, exiting.%s", BColours.fail, BColours.endc
        )
        print(FAILED)
        raise InvalidRunError("Not all HPC runs were valid, see logs for details.")

    print(DONE)
    logger.info("All HPC runs valid.")

    # Parse the default HPC job submission script.
    print("Processing HPC job submission script ..........................    ", end="")
    logger.info("Parsing base HPC job submission script.")
    try:
        with open(HPC_SUBMISSION_SCRIPT_FILEPATH, "r") as f:
            hpc_submission_script_file_contents = f.read()
    except FileNotFoundError:
        logger.error(
            "%sHPC job submission file not found. Check that the file, '%s', has not "
            "been removed.%s",
            BColours.fail,
            HPC_SUBMISSION_SCRIPT_FILEPATH,
            BColours.endc,
        )
        print(FAILED)
        raise

    print(DONE)
    logger.info("HPC job submission file successfully parsed.")

    hpc_submission_script_file_contents = hpc_submission_script_file_contents.format(
        NUM_RUNS=len(runs),
        RUNS_FILE=run_file,
        VERBOSE=("--verbose" if verbose else ""),
        WALLTIME=walltime,
    )
    logger.info(
        "HPC job submission script updated with %s runs, %s walltime.",
        len(runs),
        walltime,
    )

    # Setup the HPC job submission script.
    with tempfile.TemporaryDirectory() as tmpdirname:
        hpc_submission_script_filepath = os.path.join(
            tmpdirname, HPC_SUBMISSION_SCRIPT_FILENAME
        )

        # Write the submission script file.
        logger.info("Writing temporary HPC submission script.")
        with open(hpc_submission_script_filepath, "w") as f:
            f.write(hpc_submission_script_file_contents)

        logger.info("HPC job submission script successfully submitted.")

        # Update permissions on the file.
        os.chmod(hpc_submission_script_filepath, 0o775)
        logger.info("HPC job submission script permissions successfully updated.")

        # Submit the script to the HPC.
        logger.info("Submitting CLOVER jobs to the HPC.")
        print("Sending jobs to the HPC:")
        try:
            subprocess.run(["qsub", hpc_submission_script_filepath], check=False)
        except Exception:  # pylint: disable=broad-except
            logger.error("Failed. See logs for details.")
            print(
                "Sending jobs to the HPC .......................................    "
                f"{FAILED}"
            )
            raise
        print(
            f"Sending jobs to the HPC .......................................    {DONE}"
        )
        logger.info("HPC runs submitted. Exiting.")


if __name__ == "__main__":
    main(sys.argv[1:])
