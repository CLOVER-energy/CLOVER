#!/usr/bin/python3
########################################################################################
# test_finance.py - Tests for CLOVER's finance module.                                 #
#                                                                                      #
# Author: Ben Winchester, Phil Sandwell                                                #
# Copyright: Ben Winchester, 2022                                                      #
# Date created: 08/03/2022                                                             #
# License: Open source                                                                 #
########################################################################################
"""
test_finance.py - Tests for the finance module for CLOVER's impact component.

"""

import unittest

from unittest import mock

import pandas as pd

from ...finance import _inverter_expenditure


class _BaseFinanceTest(unittest.TestCase):
    """Contains mocks in common across all test cases."""

    def setUp(self) -> None:
        """Sets up mocks in common across all test cases."""

        super().setUp()

        self.finance_inputs = {
            "discount_rate": 0.1,
            "general_o&m": 500,
            "misc": {"cost": 0},
            "bos": {"cost": 200, "cost_decrease": 2},
            "diesel_fuel": {"cost": 0.9, "cost_decrease": -1},
            "grid": {"cost": 0.01, "extension cost": 5000, "infrastructure_cost": 2000},
            "households": {"connection_cost": 100},
            "inverter": {
                "cost": 200,
                "cost_decrease": 2,
                "lifetime": 4,
                "size_increment": 1,
            },
            "kerosene": {"cost": 0.008},
            "pv": {
                "cost": 500,
                "cost_decrease": 5,
                "installation_cost": 100,
                "installation_cost_decrease": 0,
                "o&m": 5,
            },
            "diesel_generator": {
                "cost": 200,
                "installation_cost": 50,
                "installation_cost_decrease": 0,
                "o&m": 20,
                "cost_decrease": 0,
            },
            "storage": {"cost": 400, "cost_decrease": 5, "o&m": 10},
        }
        self.location = mock.Mock(max_years=20)
        self.logger = mock.MagicMock()
        self.yearly_load_statistics = pd.DataFrame(
            {
                "Maximum": {
                    0: 4644.0,
                    1: 4577.0,
                    2: 4513.0,
                    3: 5366.0,
                    4: 5968.0,
                    5: 6288.0,
                    6: 7583.0,
                    7: 7806.0,
                    8: 9182.0,
                    9: 9798.0,
                    10: 10184.0,
                    11: 11106.0,
                    12: 11653.0,
                    13: 11907.0,
                    14: 12887.0,
                    15: 13638.0,
                    16: 14121.0,
                    17: 14564.0,
                    18: 15613.0,
                    19: 15102.0,
                },
                "Mean": {
                    0: 1231.0,
                    1: 1372.0,
                    2: 1524.0,
                    3: 1791.0,
                    4: 2184.0,
                    5: 2472.0,
                    6: 2946.0,
                    7: 3295.0,
                    8: 3766.0,
                    9: 4147.0,
                    10: 4540.0,
                    11: 4968.0,
                    12: 5319.0,
                    13: 5653.0,
                    14: 6028.0,
                    15: 6274.0,
                    16: 6612.0,
                    17: 6757.0,
                    18: 7129.0,
                    19: 7263.0,
                },
                "Median": {
                    0: 1129.0,
                    1: 1245.0,
                    2: 1395.0,
                    3: 1605.0,
                    4: 2022.5,
                    5: 2270.0,
                    6: 2749.5,
                    7: 3065.0,
                    8: 3520.0,
                    9: 3875.0,
                    10: 4258.0,
                    11: 4680.0,
                    12: 5027.5,
                    13: 5335.0,
                    14: 5710.0,
                    15: 5940.5,
                    16: 6289.0,
                    17: 6450.0,
                    18: 6874.5,
                    19: 6945.0,
                },
            }
        )


class TestInverterExpenditure(_BaseFinanceTest):
    """Tests the calculation for the inverter expenditure."""

    def test_dynamic_inverter_size(self) -> None:
        """Tests the case with dynamically-sized inverters."""

        # Create a scenario with dynamic inverter sizing.
        scenario = mock.Mock(fixed_inverter_size=False)

        # Test the case when the inverter needs to be replaced.
        self.assertEqual(
            4096.95,
            _inverter_expenditure(
                self.finance_inputs,
                self.location,
                self.logger,
                scenario,
                self.yearly_load_statistics,
                start_year=0,
                end_year=20,
            ),
        )

        # Test the case when the inverter does not need replacing.
        self.assertEqual(
            0,
            _inverter_expenditure(
                self.finance_inputs,
                self.location,
                self.logger,
                scenario,
                self.yearly_load_statistics,
                start_year=1,
                end_year=3,
            ),
        )

    def test_static_inverter_size(self) -> None:
        """Tests the case with dynamically-sized inverters."""

        # Create a scenario with a fixed inverter size of 6 kw.
        scenario = mock.Mock(fixed_inverter_size=6)

        # Test the case(s) when the inverter needs to be replaced.
        self.assertEqual(
            1200.0,
            _inverter_expenditure(
                self.finance_inputs,
                self.location,
                self.logger,
                scenario,
                self.yearly_load_statistics,
                start_year=0,
                end_year=2,
            ),
        )
        self.assertEqual(
            2792.57,
            _inverter_expenditure(
                self.finance_inputs,
                self.location,
                self.logger,
                scenario,
                self.yearly_load_statistics,
                start_year=0,
                end_year=20,
            ),
        )

        # Test the case when the inverter does not need replacing.
        self.assertEqual(
            0,
            _inverter_expenditure(
                self.finance_inputs,
                self.location,
                self.logger,
                scenario,
                self.yearly_load_statistics,
                start_year=1,
                end_year=3,
            ),
        )
