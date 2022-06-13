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

import pytest
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

    Several of the input files that CLOVER uses are parsed into Python dictionaries. In
    order to update fields within these files whilst generating new locations, this
    helper function takes in the dictionary, the value that needs to be updated, and a
    list of keys, each at a successively deeper level, that specify the path to the
    key-value pair that needs updating.

    E.G., if we want to update
    {
        "fruits": {
            "apples": 5
        }
    }
    with a new value of 10, this function would take in
    - dictionary: {"fruits": {"apples": 5}},
    - update_key: ["fruits", "apples"]
    - value: 10
    where the `update_key` variables has provided the path to the variable.

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

    .. attribute:: args
        Command-line arguments to be passed to CLOVER.

    .. attribute:: output_name
        The name of the output directory into which CLOVER should save its outputs.

    .. attribute:: temp_location_name
        The name of the temporary location.

    .. attribute:: temp_location_path
        The path to the temporary location.

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

        This function adds arguments which are specific to running simulations.

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
                    "Cannot run a CLOVER test simulation with PV but no pv size "
                    "specified."
                )
            clover_args.extend(["--pv-system-size", str(pv_size)])

        if storage:
            if storage_size is None:
                raise Exception(
                    "Cannot run a CLOVER test simulation with PV but no pv size "
                    "specified."
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

    def _check_output(  # pylint: disable=too-many-locals
        self,
        info_file_data: Dict[str, Any],
        *,
        average_daily_diesel: float,
        average_daily_grid_energy: float,
        average_daily_grid_times: float,
        average_daily_renewables_energy: float,
        average_daily_storage_energy: float,
        blackouts: float,
        cumulative_cost: float,
        cumulative_ghgs: float,
        cumulative_pv_generation: float,
        diesel_capacity: float,
        diesel_times: float,
        final_pv_size: float,
        final_storage_size: float,
        initial_pv_size: float,
        initial_storage_size: float,
        lcue: float,
        renewables_fraction: float,
        unmet_energy_fraction: float,
    ) -> None:
        """
        Checks the output file produced by the CLOVER simulation.

        Inputs:
            - info_file_Data:
                The data as parsed by the output input-file generated by CLOVER.
            - average_daily_diesel:
                The average energy that was supplied, per day, by the backup diesel
                generators.
            - average_daily_grid_energy:
                The average energy that was supplied, per day, by the grid.
            - average_daily_grid_times:
                The average portion of the time, per day, for which the grid was
                available and supplying poiwer.
            - average_daily_renewables_energy:
                The average energy that was supplied, per day, by renewables.
            - average_daily_storage_energy:
                The average energy that was supplied, per day, by the energy storage
                system.
            - balckouts:
                The fraction of the time for which the system experienced a blackout.
            - cumulative_cost:
                The cumulative cost of the system, measured in USD.
            - cumulative_ghgs:
                The total GHGs that were generated.
            - cumulative_pv_generation:
                The total amount of energy, in kWh, that the PV system generated.
            - diesel_capacity:
                The capacity of the backup diesel generator installed, in kW.
            - diesel_times:
                The fraction of the time for which the diesel generator was running.
            - initial_storage_size:
                The final size, in PV units, of the PV system installed.
            - finalal_storage_size:
                The final size, in kWh, of the storage system installed.
            - initial_pv_size:
                The initial size, in PV units, of the PV system installed.
            - initial_storage_size:
                The initial size, in kWh, of the storage system installed.
            - lcue:
                The levilised cost of energy that was used by the system.
            - renewables_fraction:
                The fraction of used energy that was generated by renewables.
            - unmet_energy_fraction:
                The fraction of all energy demand which went unmet.

        """

        # Check appraisal criteria
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["blackouts"],
            blackouts,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_cost"
            ],
            cumulative_cost,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "cumulative_ghgs"
            ],
            cumulative_ghgs,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"]["lcue"],
            lcue,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "renewables_fraction"
            ],
            renewables_fraction,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["system_appraisal"]["criteria"][
                "unmet_energy_fraction"
            ],
            unmet_energy_fraction,
        )

        # Check diesel parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily diesel energy supplied / kWh"
            ],
            average_daily_diesel,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"]["Diesel times"],
            diesel_times,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["diesel_capacity"], diesel_capacity
        )

        # Check grid parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily grid energy supplied / kWh"
            ],
            average_daily_grid_energy,
        )
        # Check that the grid times are not included if no grid is present.
        if average_daily_grid_times == 0:
            self.assertNotIn(
                "Average grid availability / hours/day",
                info_file_data["simulation_1"]["analysis_results"],
            )
        else:
            self.assertEqual(
                info_file_data["simulation_1"]["analysis_results"][
                    "Average grid availability / hours/day"
                ],
                average_daily_grid_times,
            )

        # Check PV parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily renewables energy used / kWh"
            ],
            average_daily_renewables_energy,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Cumulative pv generation / kWh/kWp"
            ],
            cumulative_pv_generation,
        )
        self.assertEqual(info_file_data["simulation_1"]["final_pv_size"], final_pv_size)
        self.assertEqual(
            info_file_data["simulation_1"]["initial_pv_size"], initial_pv_size
        )

        # Check storage parameters
        self.assertEqual(
            info_file_data["simulation_1"]["analysis_results"][
                "Average daily stored energy supplied / kWh"
            ],
            average_daily_storage_energy,
        )
        self.assertEqual(
            info_file_data["simulation_1"]["final_storage_size"], final_storage_size
        )
        self.assertEqual(
            info_file_data["simulation_1"]["initial_storage_size"], initial_storage_size
        )

    @pytest.mark.integrest
    def test_diesel_grid_pv_and_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP;
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            True, True, True, True, pv_size=20, storage_size=25
        )
        self._check_output(
            info_file_data,
            average_daily_diesel=1.65,
            average_daily_grid_energy=7.196,
            average_daily_grid_times=9.338,
            average_daily_renewables_energy=4.262,
            average_daily_storage_energy=7.52,
            blackouts=0.1,
            cumulative_cost=32249.869,
            cumulative_ghgs=91620.383,
            cumulative_pv_generation=36685.0,
            diesel_capacity=3.0,
            diesel_times=0.12,
            final_pv_size=19.0,
            final_storage_size=21.34,
            initial_pv_size=20.0,
            initial_storage_size=25.0,
            lcue=1.124,
            renewables_fraction=0.571,
            unmet_energy_fraction=0.018,
        )

    @pytest.mark.integrest
    def test_diesel_grid_and_pv(self):
        """
        Tests the case with diesel, grid and PV.

        The test simulation uses:
            - a PV system size of 20 kWP.

        """

        info_file_data = self._run_clover_simulation(
            True, True, True, False, pv_size=20
        )
        self._check_output(
            info_file_data,
            average_daily_diesel=8.821,
            average_daily_grid_energy=7.196,
            average_daily_grid_times=9.338,
            average_daily_renewables_energy=4.262,
            average_daily_storage_energy=0.0,
            blackouts=0.1,
            cumulative_cost=26343.181,
            cumulative_ghgs=100650.761,
            cumulative_pv_generation=36685.0,
            diesel_capacity=3.0,
            diesel_times=0.394,
            final_pv_size=19.0,
            final_storage_size=0.0,
            initial_pv_size=20.0,
            initial_storage_size=0.0,
            lcue=0.934,
            renewables_fraction=0.21,
            unmet_energy_fraction=0.016,
        )

    @pytest.mark.integrest
    def test_diesel_grid_and_storage(self):
        """
        Tests the case with diesel, grid and storage.

        The test simulation uses:
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            True, True, False, True, storage_size=25
        )
        self._check_output(
            info_file_data,
            average_daily_diesel=11.149,
            average_daily_grid_energy=7.196,
            average_daily_grid_times=9.338,
            average_daily_renewables_energy=0.0,
            average_daily_storage_energy=0.005,
            blackouts=0.099,
            cumulative_cost=15841.411,
            cumulative_ghgs=42714.989,
            cumulative_pv_generation=0.0,
            diesel_capacity=3.0,
            diesel_times=0.511,
            final_pv_size=0.0,
            final_storage_size=24.997,
            initial_pv_size=0.0,
            initial_storage_size=25.0,
            lcue=0.628,
            renewables_fraction=0.0,
            unmet_energy_fraction=0.026,
        )

    @pytest.mark.integrest
    def test_diesel_and_grid(self):
        """
        Tests the case with diesel and grid.

        The test simulation uses no PV or storage.

        """

        info_file_data = self._run_clover_simulation(True, True, False, False)
        self._check_output(
            info_file_data,
            average_daily_diesel=11.153,
            average_daily_grid_energy=7.196,
            average_daily_grid_times=9.338,
            average_daily_renewables_energy=0.0,
            average_daily_storage_energy=0.0,
            blackouts=0.1,
            cumulative_cost=9916.962,
            cumulative_ghgs=39335.849,
            cumulative_pv_generation=0.0,
            diesel_capacity=3.0,
            diesel_times=0.511,
            final_pv_size=0.0,
            final_storage_size=0.0,
            initial_pv_size=0.0,
            initial_storage_size=0.0,
            lcue=0.393,
            renewables_fraction=0.0,
            unmet_energy_fraction=0.026,
        )

    @pytest.mark.integrest
    def test_diesel_pv_and_storage(self):
        """
        Tests the case with diesel, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP;
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            True, False, True, True, pv_size=20, storage_size=25
        )
        self._check_output(
            info_file_data,
            average_daily_diesel=5.548,
            average_daily_grid_energy=0.0,
            average_daily_grid_times=0.0,
            average_daily_renewables_energy=4.271,
            average_daily_storage_energy=9.807,
            blackouts=0.099,
            cumulative_cost=32209.939,
            cumulative_ghgs=91493.592,
            cumulative_pv_generation=36685.0,
            diesel_capacity=3.0,
            diesel_times=0.356,
            final_pv_size=19.0,
            final_storage_size=20.227,
            initial_pv_size=20.0,
            initial_storage_size=25.0,
            lcue=1.179,
            renewables_fraction=0.717,
            unmet_energy_fraction=0.011,
        )

    @pytest.mark.integrest
    def test_diesel_and_pv(self):
        """
        Tests the case with diesel and PV.

        The test simulation uses:
            - a PV system size of 20.

        """

        info_file_data = self._run_clover_simulation(
            True, False, True, False, pv_size=20
        )
        self._check_output(
            info_file_data,
            average_daily_diesel=14.879,
            average_daily_grid_energy=0.0,
            average_daily_grid_times=0.0,
            average_daily_renewables_energy=4.271,
            average_daily_storage_energy=0.0,
            blackouts=0.1,
            cumulative_cost=29025.727,
            cumulative_ghgs=104115.842,
            cumulative_pv_generation=36685.0,
            diesel_capacity=3.0,
            diesel_times=0.726,
            final_pv_size=19.0,
            final_storage_size=0.0,
            initial_pv_size=20.0,
            initial_storage_size=0.0,
            lcue=1.092,
            renewables_fraction=0.223,
            unmet_energy_fraction=0.011,
        )

    @pytest.mark.integrest
    def test_diesel_and_storage(self):
        """
        Tests the case with diesel and storage.

        The test simulation uses:
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            True, False, False, True, storage_size=25
        )
        self._check_output(
            info_file_data,
            average_daily_diesel=18.43,
            average_daily_grid_energy=0.0,
            average_daily_grid_times=0.0,
            average_daily_renewables_energy=0.0,
            average_daily_storage_energy=0.006,
            blackouts=0.098,
            cumulative_cost=15694.76,
            cumulative_ghgs=48238.701,
            cumulative_pv_generation=0.0,
            diesel_capacity=3.0,
            diesel_times=0.901,
            final_pv_size=0.0,
            final_storage_size=24.997,
            initial_pv_size=0.0,
            initial_storage_size=25.0,
            lcue=0.621,
            renewables_fraction=0.0,
            unmet_energy_fraction=0.021,
        )

    @pytest.mark.integrest
    def test_diesel_only(self):
        """
        Tests the case with diesel only.

        The test simulation uses no PV or storage.

        """

        info_file_data = self._run_clover_simulation(True, False, False, False)
        self._check_output(
            info_file_data,
            average_daily_diesel=18.435,
            average_daily_grid_energy=0.0,
            average_daily_grid_times=0.0,
            average_daily_renewables_energy=0.0,
            average_daily_storage_energy=0.0,
            blackouts=0.098,
            cumulative_cost=12580.977,
            cumulative_ghgs=44878.006,
            cumulative_pv_generation=0.0,
            diesel_capacity=3.0,
            diesel_times=0.902,
            final_pv_size=0.0,
            final_storage_size=0.0,
            initial_pv_size=0.0,
            initial_storage_size=0.0,
            lcue=0.498,
            renewables_fraction=0.0,
            unmet_energy_fraction=0.021,
        )

    @pytest.mark.integrest
    def test_grid_pv_and_storage(self):
        """
        Tests the case with grid, PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP;
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            False, True, True, True, pv_size=20, storage_size=25
        )
        self._check_output(
            info_file_data,
            average_daily_diesel=0.0,
            average_daily_grid_energy=7.196,
            average_daily_grid_times=9.338,
            average_daily_renewables_energy=4.262,
            average_daily_storage_energy=7.52,
            blackouts=0.22,
            cumulative_cost=31728.191,
            cumulative_ghgs=85650.33,
            cumulative_pv_generation=36685.0,
            diesel_capacity=0.0,
            diesel_times=0.0,
            final_pv_size=19.0,
            final_storage_size=21.34,
            initial_pv_size=20.0,
            initial_storage_size=25.0,
            lcue=1.172,
            renewables_fraction=0.621,
            unmet_energy_fraction=0.105,
        )

    @pytest.mark.integrest
    def test_grid_and_pv(self):
        """
        Tests the case with grid and PV.

        The test simulation uses:
            - a PV system size of 20 kWP.

        """

        info_file_data = self._run_clover_simulation(
            False, True, True, False, pv_size=20
        )
        self._check_output(
            info_file_data,
            average_daily_diesel=0.0,
            average_daily_grid_energy=7.196,
            average_daily_grid_times=9.338,
            average_daily_renewables_energy=4.262,
            average_daily_storage_energy=0.0,
            blackouts=0.493,
            cumulative_cost=33980.723,
            cumulative_ghgs=196112.02,
            cumulative_pv_generation=36685.0,
            diesel_capacity=0.0,
            diesel_times=0.0,
            final_pv_size=19.0,
            final_storage_size=0.0,
            initial_pv_size=20.0,
            initial_storage_size=0.0,
            lcue=1.256,
            renewables_fraction=0.372,
            unmet_energy_fraction=0.485,
        )

    @pytest.mark.integrest
    def test_grid_and_storage(self):
        """
        Tests the case with grid and storage.

        The test simulation uses:
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            False, True, False, True, storage_size=25
        )
        self._check_output(
            info_file_data,
            average_daily_diesel=0.0,
            average_daily_grid_energy=7.196,
            average_daily_grid_times=9.338,
            average_daily_renewables_energy=0.0,
            average_daily_storage_energy=0.005,
            blackouts=0.61,
            cumulative_cost=28565.669,
            cumulative_ghgs=133907.16,
            cumulative_pv_generation=0.0,
            diesel_capacity=0.0,
            diesel_times=0.0,
            final_pv_size=0.0,
            final_storage_size=24.997,
            initial_pv_size=0.0,
            initial_storage_size=25.0,
            lcue=1.492,
            renewables_fraction=0.001,
            unmet_energy_fraction=0.618,
        )

    @pytest.mark.integrest
    def test_grid_only(self):
        """
        Tests the case with only grid.

        The test simulation uses no PV or storage.

        """

        info_file_data = self._run_clover_simulation(False, True, False, False)
        self._check_output(
            info_file_data,
            average_daily_diesel=0.0,
            average_daily_grid_energy=7.196,
            average_daily_grid_times=9.338,
            average_daily_renewables_energy=0.0,
            average_daily_storage_energy=0.0,
            blackouts=0.611,
            cumulative_cost=17585.402,
            cumulative_ghgs=130629.73,
            cumulative_pv_generation=0.0,
            diesel_capacity=0.0,
            diesel_times=0.0,
            final_pv_size=0.0,
            final_storage_size=0.0,
            initial_pv_size=0.0,
            initial_storage_size=0.0,
            lcue=0.383,
            renewables_fraction=0.0,
            unmet_energy_fraction=0.618,
        )

    @pytest.mark.integrest
    def test_pv_and_storage(self):
        """
        Tests the case with PV and storage.

        The test simulation uses:
            - a PV system size of 20 kWP;
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            False, False, True, True, pv_size=20, storage_size=25
        )

        self._check_output(
            info_file_data,
            average_daily_diesel=0.0,
            average_daily_grid_energy=0.0,
            average_daily_grid_times=0.0,
            average_daily_renewables_energy=4.271,
            average_daily_storage_energy=9.807,
            blackouts=0.454,
            cumulative_cost=34386.293,
            cumulative_ghgs=102913.66,
            cumulative_pv_generation=36685.0,
            diesel_capacity=0.0,
            diesel_times=0.0,
            final_pv_size=19.0,
            final_storage_size=20.227,
            initial_pv_size=20.0,
            initial_storage_size=25.0,
            lcue=1.534,
            renewables_fraction=1.0,
            unmet_energy_fraction=0.306,
        )

    @pytest.mark.integrest
    def test_pv_only(self):
        """
        Tests the case with only PV.

        The test simulation uses:
            - a PV system size of 20 kWP.

        """

        info_file_data = self._run_clover_simulation(
            False, False, True, False, pv_size=20
        )
        self._check_output(
            info_file_data,
            average_daily_diesel=0.0,
            average_daily_grid_energy=0.0,
            average_daily_grid_times=0.0,
            average_daily_renewables_energy=4.271,
            average_daily_storage_energy=0.0,
            blackouts=0.826,
            cumulative_cost=41931.345,
            cumulative_ghgs=256032.195,
            cumulative_pv_generation=36685.0,
            diesel_capacity=0.0,
            diesel_times=0.0,
            final_pv_size=19.0,
            final_storage_size=0.0,
            initial_pv_size=20.0,
            initial_storage_size=0.0,
            lcue=3.249,
            renewables_fraction=1.0,
            unmet_energy_fraction=0.801,
        )

    @pytest.mark.integtest
    def test_storage_only(self):
        """
        Tests the case with only storage.

        The test simulation uses:
            - a storage system size of 25 kWh.

        """

        info_file_data = self._run_clover_simulation(
            False, False, False, True, storage_size=25
        )
        self._check_output(
            info_file_data,
            average_daily_diesel=0.0,
            average_daily_grid_energy=0.0,
            average_daily_grid_times=0.0,
            average_daily_renewables_energy=0.0,
            average_daily_storage_energy=0.006,
            blackouts=0.999,
            cumulative_cost=36512.623,
            cumulative_ghgs=193802.42,
            cumulative_pv_generation=0.0,
            diesel_capacity=0.0,
            diesel_times=0.0,
            final_pv_size=0.0,
            final_storage_size=24.997,
            initial_pv_size=0.0,
            initial_storage_size=25.0,
            lcue=1377.525,
            renewables_fraction=1.0,
            unmet_energy_fraction=1.0,
        )

    @unittest.skip("No need to test scenario with no power generation sources.")
    # @pytest.mark.integrest
    def test_no_diesel_no_grid_no_pv_no_storage(self):
        """
        Tests the case with diesel, grid, PV and storage.

        The test simulation uses no PV or storage.

        """

        _ = self._run_clover_simulation(False, False, False, False)
