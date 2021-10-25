#!/usr/bin/python3
########################################################################################
# solar.py - Solar panel modelling code for CLOVER.                                    #
#                                                                                      #
# Authors: Ben Winchester                                                              #
# Copyright: Phil Sandwell, 2021                                                       #
# Date created: 12/08/2021                                                             #
# License: Open source                                                                 #

# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
solar.py - Solar-panel modelling code for CLOVER.

In order to accurately model a solar panel within CLOVER, various information about its
performance under environmental conditions needs to be calculated.

"""

# Bodged import
import collections
import pickle

from logging import Logger
from typing import Dict, List, Tuple

import pandas as pd  # type: ignore  # pylint: disable=import-error

from scipy import linalg
from tqdm import tqdm

from ..__utils__ import (
    BColours,
    HTFMode,
    InputFileError,
    ResourceType,
    Scenario,
    ZERO_CELCIUS_OFFSET,
)
from ..conversion.conversion import ThermalDesalinationPlant
from ..generation.solar import HybridPVTPanel
from .__utils__ import Minigrid


__all__ = ("calculate_pvt_output",)


class MassFlowRateTooLargeError(Exception):
    """
    Raise when the mass-flow rate being specified is too large for the system to cope.

    """

    def __init__(self, msg: str) -> None:
        """
        Instantiate a :class:`MassFlowRateTooLargeError` instance.

        Inputs:
            - msg:
                The message to append.

        """

        super().__init__(
            f"The mass-flow rate was too large for the system to cope with: {msg}"
        )


class MassFlowRateTooSmallError(Exception):
    """
    Raise when the mass-flow rate being specified is too small for the system to cope.

    """

    def __init__(self, msg: str) -> None:
        """
        Instantiate a :class:`MassFlowRateTooSmallError` instance.

        Inputs:
            - msg:
                The message to append.

        """

        super().__init__(
            f"The mass-flow rate was too small for the system to operate: {msg}"
        )


def _pvt_mass_flow_rate(
    logger: Logger,
    pvt_panel: HybridPVTPanel,
    pvt_system_size: int,
    thermal_desalination_plant: ThermalDesalinationPlant,
) -> float:
    """
    Determines the mass-flow rate through the PV-T panels.

    Inputs:
        - logger:
            The :class:`logging.Logger` to use for the run.
        - pvt_panel:
            The :class:`HybridPVTPanel` being considered.
        - pvt_system_size:
            The size of the PV-T system being considered, measured in PV-T units.
        - thermal_desalination_plant:
            The :class:`ThermalDesalinationPlant` being considered.

    Outputs:
        The mass-flow rate of HTF through a single PV-T panel.

    Raises:
        - InputFileError:
            Raised if there is a mismatch between the parameters that means that the
            mass-flow rate cannot be determined.

    """

    if (
        pvt_system_size * pvt_panel.max_mass_flow_rate
        < thermal_desalination_plant.input_resource_consumption[
            ResourceType.HOT_UNCLEAN_WATER
        ]
        * (
            thermal_desalination_plant.minimum_output_capacity
            / thermal_desalination_plant.maximum_output_capacity
        )
    ):
        logger.error(
            "The PV-T system is not able to supply enough water to operate the thermal "
            "desalination plant: max PV-T output: %s litres/hour, min desalination "
            "plant input: %s litres/hour",
            pvt_system_size * pvt_panel.max_mass_flow_rate,
            thermal_desalination_plant.input_resource_consumption[
                ResourceType.HOT_UNCLEAN_WATER
            ]
            * (
                thermal_desalination_plant.minimum_output_capacity
                / thermal_desalination_plant.maximum_output_capacity
            ),
        )
        raise MassFlowRateTooSmallError(
            "Mismatch between PV-T and desalination-plant sizing.",
        )
    if (
        pvt_system_size * pvt_panel.min_mass_flow_rate
        > thermal_desalination_plant.input_resource_consumption[
            ResourceType.HOT_UNCLEAN_WATER
        ]
    ):
        logger.error(
            "The thermal desalination plant is unable to cope with the minimum "
            "throughput from the PV-T system: minimum PV-T output: %s litres/hour, "
            "max desalination plant input: %s lirres/hour",
            pvt_system_size * pvt_panel.min_mass_flow_rate,
            thermal_desalination_plant.input_resource_consumption[
                ResourceType.HOT_UNCLEAN_WATER
            ],
        )
        raise MassFlowRateTooLargeError(
            "conversion/solar inputs",
            "Mismatch between PV-T and desalination-plant sizing.",
        )

    return min(
        pvt_panel.max_mass_flow_rate,
        thermal_desalination_plant.input_resource_consumption[
            ResourceType.HOT_UNCLEAN_WATER
        ]
        / pvt_system_size,
    )


def calculate_pvt_output(
    end_hour: int,
    irradiances: pd.Series,
    logger: Logger,
    minigrid: Minigrid,
    pvt_system_size: int,
    scenario: Scenario,
    start_hour: int,
    temperatures: pd.Series,
    thermal_desalination_plant: ThermalDesalinationPlant,
    wind_speeds: pd.Series,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Computes the output of a PV-T system.

    Inputs:
        - end_hour:
            The end hour for the simulation being carried out.
        - irradiances:
            The :class:`pd.Series` containing irradiance information for the time
            period being modelled.
        - logger:
            The logger to use for the run.
        - minigrid:
            The minigrid being modelled currently.
        - pvt_system_size:
            The size of the PV-T system being modelled.
        - scenario:
            The :class:`Scenario` being considered.
        - start_hour:
            The start hour for the simulation being carried out.
        - temperatures:
            The :class:`pd.Series` containing temperature information for the time
            period being modelled.
        - thermal_desalination_plant:
            The thermal desalination plant being considered.
        - wind_speeds:
            The :class:`pd.Series` containing wind-speed information for the time period
            being modelled.

    Outputs:
        - pvt_collector_output_temperature:
            The output temperature of the PV-T collectors at each time step.
        - pvt_electric_power_per_unit:
            The electric power, per unit PV-T, delivered by the PV-T system.
        - tank_temperature:
            The tank temperatures throughout the simulation, measured in degrees C.
        - tank_volume_supplied:
            The amount of hot water supplied by the hot-water tanks to the desalination
            system.

    """

    if minigrid.pvt_panel is None:
        logger.error(
            "The energy system does not contain a PV-T panel despite the PV-T output "
            "computation function being called."
        )
        raise InputFileError(
            "energy system inputs",
            "The energy system specified does not contain a PV-T panel but PV-T "
            "modelling was requested.",
        )

    # @@@
    # FIXME
    mass_flow_rate = 4

    # Instantiate loop parameters.
    best_guess_collector_input_temperature = (
        scenario.desalination_scenario.feedwater_supply_temperature
    )
    base_a_00 = 0
    base_a_01 = (
        mass_flow_rate
        * scenario.desalination_scenario.pvt_scenario.htf_heat_capacity
        * minigrid.heat_exchanger.efficiency
        + minigrid.hot_water_tank.mass * minigrid.hot_water_tank.heat_capacity / 3600
        + minigrid.hot_water_tank.heat_transfer_coefficient
    )
    base_a_10 = 1
    base_a_11 = -minigrid.heat_exchanger.efficiency

    # Instantiate maps for easy PV-T power lookups.
    pvt_collector_output_temperature_map: Dict[int, float] = {}
    pvt_electric_power_per_unit_map: Dict[int, float] = {}
    tank_temperature_map: Dict[int, float] = collections.defaultdict(float)
    tank_volume_supplied_map: Dict[int, float] = collections.defaultdict(float)

    if scenario.desalination_scenario.pvt_scenario.heats != HTFMode.CLOSED_HTF:
        logger.error(
            "%sCurrently, closed HTF PV-T modelling is supported only.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "desalination scenario", "The PV-T heating mode requested is not supported."
        )

    for index in tqdm(
        range(start_hour, end_hour),
        desc="pv-t performance",
        leave=False,
        unit="hour",
    ):
        # Only compute outputs if there is input irradiance.
        if irradiances[index] > 0:
            solution_found: bool = False
            # Keep processing until the temperatures are consistent.
            while not solution_found:
                # Run the AI reduced model.
                (
                    fractional_electric_performance,
                    collector_output_temperature,
                ) = minigrid.pvt_panel.calculate_performance(
                    temperatures[index],
                    best_guess_collector_input_temperature,
                    logger,
                    mass_flow_rate,  # [kg/s]
                    1000 * irradiances[index],
                    wind_speeds[index],
                )

                # Construct the matrix equation to solve for AX = B.
                b_0 = minigrid.hot_water_tank.heat_transfer_coefficient * (
                    temperatures[index] + ZERO_CELCIUS_OFFSET
                ) + mass_flow_rate * scenario.desalination_scenario.pvt_scenario.htf_heat_capacity * minigrid.heat_exchanger.efficiency * (
                    collector_output_temperature + ZERO_CELCIUS_OFFSET
                )
                b_1 = (1 - minigrid.heat_exchanger.efficiency) * (
                    collector_output_temperature + ZERO_CELCIUS_OFFSET
                )

                # Supply heat if the tank temperature was hot enough at the previous
                # time step.
                if index > 0:
                    if (
                        tank_temperature_map[index - 1]
                        > thermal_desalination_plant.minimum_htf_temperature
                    ):
                        # The tank should supply temperature at this time step.
                        volume_supplied = (
                            thermal_desalination_plant.input_resource_consumption[
                                ResourceType.HOT_UNCLEAN_WATER
                            ]
                        )

                        # The supply of this water will reduce the tank temperature.
                        b_0 += (
                            volume_supplied
                            * minigrid.hot_water_tank.heat_capacity
                            * (
                                scenario.desalination_scenario.feedwater_supply_temperature
                                - tank_temperature_map[index - 1]
                            )
                        )
                    else:
                        volume_supplied = 0

                    # The previous tank temperature will affect the current temperature.
                    b_0 += (
                        minigrid.hot_water_tank.mass
                        * minigrid.hot_water_tank.heat_capacity
                        * (tank_temperature_map[index - 1] + ZERO_CELCIUS_OFFSET)
                        / 3600
                    )

                else:
                    # The initial tank temperature will affect the current temperature.
                    b_0 += (
                        minigrid.hot_water_tank.mass
                        * minigrid.hot_water_tank.heat_capacity
                        * (
                            scenario.desalination_scenario.feedwater_supply_temperature
                            + ZERO_CELCIUS_OFFSET
                        )
                        / 3600
                    )

                # Solve the matrix equation to compute the new best-guess collector
                # input temperature.
                collector_input_temperature, tank_temperature = linalg.solve(
                    a=[[base_a_00, base_a_01], [base_a_10, base_a_11]], b=[b_0, b_1]
                )
                collector_input_temperature -= ZERO_CELCIUS_OFFSET
                tank_temperature -= ZERO_CELCIUS_OFFSET

                if (
                    abs(
                        collector_input_temperature
                        - best_guess_collector_input_temperature
                    )
                    < 0.1
                ):
                    solution_found = True

                best_guess_collector_input_temperature = collector_input_temperature

        else:
            collector_output_temperature = best_guess_collector_input_temperature
            fractional_electric_performance = 0
            tank_temperature = 0
            volume_supplied = 0

        # Save the fractional electrical performance and output temp.
        pvt_collector_output_temperature_map[index] = collector_output_temperature
        pvt_electric_power_per_unit_map[index] = fractional_electric_performance
        tank_temperature_map[index] = tank_temperature
        tank_volume_supplied_map[index] = volume_supplied

    # Convert these outputs to dataframes and return.
    pvt_collector_output_temperature: pd.DataFrame = pd.DataFrame(  # type: ignore
        list(pvt_collector_output_temperature_map.values()),
        index=list(pvt_collector_output_temperature_map.keys()),
    ).sort_index()
    pvt_electric_power_per_unit: pd.DataFrame = (
        pd.DataFrame(  # type: ignore
            list(pvt_electric_power_per_unit_map.values()),
            index=list(pvt_electric_power_per_unit_map.keys()),
        ).sort_index()
        * minigrid.pvt_panel.pv_unit
    )
    tank_temperature: pd.DataFrame = pd.DataFrame(
        list(tank_temperature_map.values()),
        index=list(tank_temperature_map.keys()),
    ).sort_index()
    tnak_volume_output_supplied_per_unit: pd.DataFrame = pd.DataFrame(
        list(tank_volume_supplied_map.values()),
        index=list(tank_volume_supplied_map.keys()),
    ).sort_index()

    return (
        pvt_collector_output_temperature,
        pvt_electric_power_per_unit,
        tank_temperature,
        tank_volume_supplied_map,
    )
