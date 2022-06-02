#!/usr/bin/python3
########################################################################################
# test_clover.py - Integration tests for CLOVER.                                       #
#                                                                                      #
# Author: Ben Winchester, Phil Sandwell                                                #
# Copyright: Ben Winchester, 2022                                                      #
# Date created: 08/03/2022                                                             #
# License: Open source                                                                 #
########################################################################################
"""
test_clover.py - Integration tests for the CLOVER Python package.

CLOVER is constantly under development by researchers, NGOs, and private companies. To
ensure reproducibility across different branches and versions of CLOVER, the integration
tests below are run as part of the enforcement which is carried out when contributing to
CLOVER. They also provide a useful tool for ensuring that any changes made locally do
not affect the overall running of the code.

"""

import os
import shutil
import time
import unittest

import pytest

from typing import Optional
from unittest import mock

from ...__main__ import main as clover_main
from ...__utils__ import LOCATIONS_FOLDER_NAME, RAW_CLOVER_PATH


# Integration folder name:
#   The name of the integration tests folder.
INTEGRATION_FOLDER_NAME: str = "integration"

# Temp location folder name:
#   The name of the temporary location folder.
TEMP_LOCATION_FOLDER_NAME: str = "temp_location"

# Tests folder name:
#   The name of the tests folders.
TESTS_FOLDER_NAME: str = "tests"

# Temp location path:
#   The path to the temporary location folder for the integration tests to use.
TEMP_LOCATION_PATH: str = os.path.join(
    RAW_CLOVER_PATH,
    TESTS_FOLDER_NAME,
    INTEGRATION_FOLDER_NAME,
    TEMP_LOCATION_FOLDER_NAME
)


class _BaseTest(unittest.TestCase):
    """
    Base test class for integration tests.

    .. attribute:: temp_location_name
        The name of the temporary location

    """

    def setUp(self):
        """
        Setup function for the base test case.

        This function copies over the temporary location directory to be used as a
        location by CLOVER.

        """

        self.temp_location_name: str = f"{TEMP_LOCATION_FOLDER_NAME}_{time.ctime().replace(' ', '_')}"
        self.locations_path: str = os.path.join(LOCATIONS_FOLDER_NAME, self.temp_location_name)

        if os.path.isdir(self.locations_path):
            raise Exception(f"Temporary location, {self.temp_location_name}, already exists.")

        # Copy the temporary location to CLOVER's locations folder, saving the name.
        os.makedirs(LOCATIONS_FOLDER_NAME, exist_ok=True)
        os.makedirs(self.locations_path, exist_ok=True)
        shutil.copy2(TEMP_LOCATION_PATH, self.locations_path)

        # Store these arguments for use when calling CLOVER.
        self.args = ["--location", self.temp_location_name]

    def tearDown(self) -> None:
        """
        Teardown function for the base test case.

        This function cleans up the temporary location.

        """

        if os.path.isdir(self.locations_path):
            os.removedirs(self.locations_path)


class SimulationTests(_BaseTest):
    """
    Tests of CLOVER's simulation functionality.

    """

    def setUp(self):
        """
        Setup function containing additional setup for running simulation tests.

        """

        super().setUp()
        self.args.append("--simulation")

    def _run_clover_simulation(self, diesel: bool, grid: bool, pv: bool, storage: bool, *, pv_size: Optional[float] = None, storage_size: Optional[float] = None):
        """
        Wrapper to run a CLOVER simulation.lo

        """

        clover_args = self.args

        # Call CLOVER with these arguments.
        clover_main(clover_args)

    def test_diesel_grid_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        """

        

    def test_existence_of_customer(self):
        customer = self.app.get_customer(id=10)
        self.assertEqual(customer.name, "Org XYZ")
        self.assertEqual(customer.address, "10 Red Road, Reading")
