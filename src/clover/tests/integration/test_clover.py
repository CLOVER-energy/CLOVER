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
import shutil

from distutils.dir_util import copy_tree
from typing import Any, Dict, List, Optional, Union

import yaml

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


def _recursive_updater(
    dictionary: Dict[Any, Any], update_key: List[Any], value: Any
) -> None:
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
    _recursive_updater(dictionary[this_key], update_key, value)
    return


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
            + f"{time.ctime().replace(' ', '_').replace(':', '_').replace('__', '_')}"
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
        self.args.extend(["--simulation", "--analyse", "--skip-plots"])

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
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            True, True, True, True, pv_size=20, storage_size=25
        )

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.1,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            32249.869,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            91620.383,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            1.124,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            0.571,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            0.018,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            1.65,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.12
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 3.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            7.196,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average grid availability / hours/day"
            ],
            67939.0,
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            4.262,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            36685.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 19.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 20.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            7.52,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 21.34)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 25.0)

    def test_diesel_grid_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP.

        """

        info_file_data = self._run_clover_simulation(
            True, True, True, False, pv_size=20
        )

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.1,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            26343.181,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            100650.761,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            0.934,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            0.21,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            0.016,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            8.821,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.394
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 3.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            7.196,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average grid availability / hours/day"
            ],
            67939.0,
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            4.262,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            36685.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 19.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 20.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 0.0)

    def test_diesel_grid_no_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            True, True, False, True, storage_size=25
        )

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.099,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            15841.411,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            42714.989,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            0.628,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            0.026,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            11.149,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.511
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 3.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            7.196,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average grid availability / hours/day"
            ],
            67939.0,
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 0.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            0.005,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 24.997)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 25.0)

    def test_diesel_grid_no_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses no PV or storage.

        """

        info_file_data = self._run_clover_simulation(True, True, False, False)

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.1,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            9916.962,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            39335.849,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            0.393,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            0.026,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            11.153,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.511
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 3.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            7.196,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average grid availability / hours/day"
            ],
            67939.0,
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 0.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 0.0)

    def test_diesel_no_grid_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP;
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            True, False, True, True, pv_size=20, storage_size=25
        )

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.099,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            32209.939,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            91493.592,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            1.179,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            0.717,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            0.011,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            5.548,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.356
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 3.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            0.0,
        )
        self.assertNotIn(
            "Average grid availability / hours/day",
            info_file_data["simulation_1"]["analysis_results"],
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            4.271,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            36685.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 19.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 20.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            9.807,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 20.227)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 25.0)

    def test_diesel_no_grid_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20.

        """

        info_file_data = self._run_clover_simulation(
            True, False, True, False, pv_size=20
        )

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.1,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            29025.727,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            104115.842,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            1.092,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            0.223,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            0.011,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            14.879,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.726
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 3.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            0.0,
        )
        self.assertNotIn(
            "Average grid availability / hours/day",
            info_file_data["simulation_1"]["analysis_results"],
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            4.271,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            36685.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 19.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 20.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 0.0)

    def test_diesel_no_grid_no_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            True, False, False, True, storage_size=25
        )

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.098,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            15694.76,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            48238.701,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            0.621,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            0.021,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            18.43,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.901
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 3.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            0.0,
        )
        self.assertNotIn(
            "Average grid availability / hours/day",
            info_file_data["simulation_1"]["analysis_results"],
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 0.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            0.006,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 24.997)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 25.0)

    def test_diesel_no_grid_no_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses no PV or storage.

        """

        info_file_data = self._run_clover_simulation(True, False, False, False)

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.098,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            12580.977,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            44878.006,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            0.498,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            0.021,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            18.435,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.902
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 3.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            0.0,
        )
        self.assertNotIn(
            "Average grid availability / hours/day",
            info_file_data["simulation_1"]["analysis_results"],
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 0.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 0.0)

    def test_no_diesel_grid_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP;
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            False, True, True, True, pv_size=20, storage_size=25
        )

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.22,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            31728.191,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            85650.33,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            1.172,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            0.621,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            0.105,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.0
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 0.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            7.196,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average grid availability / hours/day"
            ],
            67939.0,
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            4.262,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            36685.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 19.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 20.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            7.52,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 21.34)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 25.0)

    def test_no_diesel_grid_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP.

        """

        info_file_data = self._run_clover_simulation(
            False, True, True, False, pv_size=20
        )

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.493,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            33980.723,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            196112.02,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            1.256,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            0.372,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            0.485,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.0
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 0.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            7.196,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average grid availability / hours/day"
            ],
            67939.0,
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            4.262,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            36685.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 19.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 20.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 0.0)

    def test_no_diesel_grid_no_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            False, True, False, True, storage_size=25
        )

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.61,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            28565.669,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            133907.16,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            1.492,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            0.001,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            0.618,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.0
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 0.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            7.196,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average grid availability / hours/day"
            ],
            67939.0,
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 0.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            0.005,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 24.997)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 25.0)

    def test_no_diesel_grid_no_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses no PV or storage.

        """

        info_file_data = self._run_clover_simulation(False, True, False, False)

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.611,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            17585.402,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            130629.73,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            0.383,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            0.618,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.0
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 0.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            7.196,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average grid availability / hours/day"
            ],
            67939.0,
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 0.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 0.0)

    def test_no_diesel_no_grid_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP;
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            False, False, True, True, pv_size=20, storage_size=25
        )

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.454,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            34386.293,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            102913.66,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            1.534,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            1.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            0.306,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.0
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 0.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            0.0,
        )
        self.assertNotIn(
            "Average grid availability / hours/day",
            info_file_data["simulation_1"]["analysis_results"],
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            4.271,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            36685.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 19.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 20.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            9.807,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 20.227)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 25.0)

    def test_no_diesel_no_grid_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP.

        """

        info_file_data = self._run_clover_simulation(
            False, False, True, False, pv_size=20
        )

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.826,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            41931.345,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            256032.195,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            3.249,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            1.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            0.801,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.0
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 0.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            0.0,
        )
        self.assertNotIn(
            "Average grid availability / hours/day",
            info_file_data["simulation_1"]["analysis_results"],
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            4.271,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            36685.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 19.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 20.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 0.0)

    def test_no_diesel_no_grid_no_pv_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            False, False, False, True, storage_size=25
        )

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            0.999,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            36512.623,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            193802.42,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            1377.525,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            1.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            1.0,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"], 0.0
        )
        self.assertEqual(info_file_data["simulation_1"]["diesel_capacity"], 0.0)

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            0.0,
        )
        self.assertNotIn(
            "Average grid availability / hours/day",
            info_file_data["simulation_1"]["analysis_results"],
        )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            0.0,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_pv_size"], 0.0)

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            0.0,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_storage_size"], 0.0)
        self.assertEqual(info_file_data["simulation_1"]["initial_storage_size"], 0.0)

    @unittest.skip("No need to test scenario with no power generation sources.")
    def test_no_diesel_no_grid_no_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses no PV or storage.

        """

        _ = self._run_clover_simulation(False, False, False, False)