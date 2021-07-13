#!/usr/bin/python3
########################################################################################
# __utils__.py - CLOVER utility module.
#
# Author: Ben Winchester
# Date created: 13/07/2021
# License: Open source
########################################################################################
"""
__utils__.py - Utility module for CLOVER.

The utility module contains functionality which is used by various scripts, modules, and
components across CLOVER, as well as commonly-held variables to prevent dependency
issues and increase the ease of code alterations.

"""

from enum import Enum

__all__ = ("LOCATIONS_FOLDER_NAME",)

# Locations folder name:
#   The name of the locations folder.
LOCATIONS_FOLDER_NAME = "locations"
