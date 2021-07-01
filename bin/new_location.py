#!/usr/bin/python3
########################################################################################
# new_location.py - Script for generating a new location folder.
#
# Author: Ben Winchester
# Date created: 01/07/2021
# License: Open source
########################################################################################
"""
new_location.py - Script for generating a new location folder.

This script, when run, generates a new location for the user, copying files from an
existing location if asked for.

"""


import argparse
import sys


from typing import Any, List


def _parse_args(args: List[Any]) -> argparse.Namespace:
    """
    Parse the CLI arguments to determine the flow of the script.

    """

    parser = argparse.ArgumentParser()

    parser.add_argument("location", help="The name of the new location to be created.")
    parser.add_argument(
        "--from-existing",
        type=str,
        help="The name of an existing location off which to model the new location.",
    )

    return parser.parse_args(args)


if __name__ == "__main__":
    pass
    # Parse the arguments.

    # Generate files as per the hard-coded directory structure.

    # Copy across files from the existing structure if they exist, otherwise, generate
    # them afresh.
