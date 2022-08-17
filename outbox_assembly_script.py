#!/usr/bin/python3
########################################################################################
# outbox_assembly_script.py - CLOVER optimisation outbox assembly script.              #
#                                                                                      #
# Authors: Ben Winchester                                                              #
# Copyright: Ben Winchester, 2022                                                      #
# Date created: 13/07/2021                                                             #
# License: Open source                                                                 #
#                                                                                      #
# For more information, please email:                                                  #
#   benedict.winchester@gmail.com                                                      #
########################################################################################
"""
outbox_assembly_script.py - CLOVER optimisation outbox assembly script.

This script assembles output files from optimisations that were carried out on Imperial
College London's High-Performance Computer(s) (HPC) into a single "outbox directory",
from where they can be easily copied from the HPC for futher analysis.

"""

import os
import shutil
import subprocess

DESTINATION_DIRECTORY: str = "optimisation_outbox"
OPTIMISATION_NAME: str = "optimisation_output_*.json"


def main() -> None:
    """Script to prepare files for scp from hpc."""

    filenames = subprocess.run(
        ["find", "locations", "-name", OPTIMISATION_NAME],
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.decode()
    filenames = filenames.split("\n")
    filenames.remove("")

    for source_filename in filenames:
        destination_filename = os.path.join(DESTINATION_DIRECTORY, source_filename)

        # Make the directory structure within the outbox if it doesn't already exist
        if not os.path.isdir(os.path.dirname(destination_filename)):
            os.makedirs(os.path.dirname(destination_filename))

        # Copy across our file
        shutil.copy2(source_filename, destination_filename)


if __name__ == "__main__":
    main()
