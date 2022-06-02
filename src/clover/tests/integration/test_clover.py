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
import time
import unittest

import json
import pytest
import shutil
import yaml

from distutils.dir_util import copy_tree
from typing import Any, Dict, List, Optional, Union
from unittest import mock

from clover.fileparser import INPUTS_DIRECTORY, SCENARIO_INPUTS_FILE

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
    TEMP_LOCATION_FOLDER_NAME,
)


def _recursive_updater(dictionary: Dict[Any, Any], update_key: List[Any], value: Any):
    """
    Helper function for recusively nested dictionaries.

    Inputs:
        - dictionary:
            The dictionary to update.
        - update_key:
            The `list` of keys specifying what to update at each level.
        - value:
            The value to update.

    """

    # Update the value if there are no more levels of depth to go to.
    if len(update_key) == 1:
        dictionary[update_key[0]] = value
        return

    # Otherwise, go one level deeper.
    this_key = update_key.pop(0)
    return _recursive_updater(dictionary[this_key], update_key, value)


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

        self.temp_location_name: str = (
            f"{TEMP_LOCATION_FOLDER_NAME}_"
            + f"{time.ctime().replace(' ', '_').replace(':', '_')}"
        )
        self.temp_location_path: str = os.path.join(
            LOCATIONS_FOLDER_NAME, self.temp_location_name
        )
        self.output_name: str = "test_output"

        if os.path.isdir(self.temp_location_path):
            raise Exception(
                f"Temporary location, {self.temp_location_name}, already exists."
            )

        # Copy the temporary location to CLOVER's locations folder, saving the name.
        os.makedirs(LOCATIONS_FOLDER_NAME, exist_ok=True)
        os.makedirs(self.temp_location_path, exist_ok=True)
        copy_tree(TEMP_LOCATION_PATH, self.temp_location_path)

        # Store these arguments for use when calling CLOVER.
        self.args = [
            "--location",
            self.temp_location_name,
            "--output",
            self.output_name,
        ]

    def tearDown(self) -> None:
        """
        Teardown function for the base test case.

        This function cleans up the temporary location.

        """

        if os.path.isdir(self.temp_location_path):
            shutil.rmtree(self.temp_location_path)


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

    def _update_scenario_file(
        self, key: Union[str, List[str]], value: Union[bool, str]
    ) -> None:
        """
        Updates the scenario file within the temporary location.

        Inputs:
            - key:
                The key to update within the file.
            - value:
                The value to update it with.

        """

        scenario_inputs_filepath = os.path.join(
            self.temp_location_path, INPUTS_DIRECTORY, SCENARIO_INPUTS_FILE
        )
        with open(scenario_inputs_filepath, "r") as f:
            scenario_inputs = yaml.safe_load(f)

        # If just one level of depth is needed, update the variable.
        if isinstance(key, str):
            scenario_inputs["scenarios"][0][key] = value
        # Otherwise, recursively update the depth.
        else:
            _recursive_updater(scenario_inputs["scenarios"][0], key, value)

        with open(scenario_inputs_filepath, "w") as f:
            yaml.dump(scenario_inputs, f)

    def _run_clover_simulation(
        self,
        diesel: bool,
        grid: bool,
        pv: bool,
        storage: bool,
        *,
        pv_size: Optional[float] = None,
        storage_size: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Wrapper to run a CLOVER simulation.

        """

        clover_args = self.args

        # Update the scenario file accordingly.
        self._update_scenario_file(
            ["diesel", "mode"], "backup" if diesel else "disabled"
        )
        self._update_scenario_file("grid", grid)
        self._update_scenario_file("pv", pv)
        # self._update_scenario_file("storage", storage) # < Will be enabled under #70.

        # Append CLI arguments as necessary for the simulation.
        if pv:
            if pv_size is None:
                raise Exception(
                    "Cannot run a CLOVER test simulation with PV but no pv size specified."
                )
            clover_args.extend(["--pv-system-size", str(pv_size)])

        if storage:
            if storage_size is None:
                raise Exception(
                    "Cannot run a CLOVER test simulation with PV but no pv size specified."
                )
            clover_args.extend(["--storage-size", str(storage_size)])
        # This else block will be removed under #70.
        else:
            clover_args.extend(["--storage-size", "0"])

        # Call CLOVER with these arguments.
        clover_main(clover_args)

        # Return the parsed output info file information.
        output_file_name: str = os.path.join(
            self.temp_location_path,
            "outputs",
            "simulation_outputs",
            self.output_name,
            "info_file.json",
        )
        if not os.path.isfile(output_file_name):
            self.fail("CLOVER simulation failed to produce an output info_file.json.")

        with open(os.path.join(output_file_name), "r") as f:
            info_file_data: Dict[str, Any] = json.load(f)

        return info_file_data

    def test_diesel_grid_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP;
            - a storage system size of 5 kWh.

        """

        info_file_data = self._run_clover_simulation(
            True, True, True, True, pv_size=20, storage_size=5
        )

    def test_diesel_grid_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP.

        """

        info_file_data = self._run_clover_simulation(
            True, True, True, False, pv_size=20
        )

    def test_diesel_grid_no_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a storage system size of 5 kWh.

        """

        info_file_data = self._run_clover_simulation(
            True, True, False, True, storage_size=5
        )

    def test_diesel_grid_no_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses no PV or storage.

        """

        info_file_data = self._run_clover_simulation(
            True, True, False, False
        )

    def test_diesel_no_grid_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP;
            - a storage system size of 5 kWh.

        """

        info_file_data = self._run_clover_simulation(
            True, False, True, True, pv_size=20, storage_size=5
        )

    def test_diesel_no_grid_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20.

        """

        info_file_data = self._run_clover_simulation(
            True, False, True, False, pv_size=20
        )

    def test_diesel_no_grid_no_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a storage system size of 5 kWh.

        """

        info_file_data = self._run_clover_simulation(
            True, False, False, True, storage_size=5
        )

    def test_diesel_no_grid_no_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses no PV or storage.

        """

        info_file_data = self._run_clover_simulation(
            True, False, False, False
        )

    def test_no_diesel_grid_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP;
            - a storage system size of 5 kWh.

        """

        info_file_data = self._run_clover_simulation(
            False, True, True, True, pv_size=20, storage_size=5
        )

    def test_no_diesel_grid_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP.

        """

        info_file_data = self._run_clover_simulation(
            False, True, True, False, pv_size=20
        )

    def test_no_diesel_grid_no_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a storage system size of 5 kWh.

        """

        info_file_data = self._run_clover_simulation(
            False, True, False, True, storage_size=5
        )

    def test_no_diesel_grid_no_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses no PV or storage.

        """

        info_file_data = self._run_clover_simulation(
            False, True, False, False
        )

    def test_no_diesel_no_grid_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP;
            - a storage system size of 5 kWh.

        """

        info_file_data = self._run_clover_simulation(
            False, False, True, True, pv_size=20, storage_size=5
        )

    def test_no_diesel_no_grid_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP.

        """

        info_file_data = self._run_clover_simulation(
            False, False, True, False, pv_size=20
        )

    def test_no_diesel_no_grid_no_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a storage system size of 5 kWh.

        """

        info_file_data = self._run_clover_simulation(
            False, False, False, True, storage_size=5
        )

    @unittest.skip("No need to test scenario with no power generation sources.")
    def test_no_diesel_no_grid_no_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses no PV or storage.

        """

        info_file_data = self._run_clover_simulation(
            False, False, False, False
        )
