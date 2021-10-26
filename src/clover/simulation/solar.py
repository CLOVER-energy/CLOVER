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
from .__utils__ import Minigrid
from .storage import HotWaterTank


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


def _buffer_tank_mass_flow_rate(
    ambient_temperature: float,
    buffer_hot_water_tank: HotWaterTank,
    thermal_desalination_plant: ThermalDesalinationPlant,
    previous_tank_temperature: float,
) -> float:
    """
    Computes the mass-flow rate of HTF from the buffer tanks to the desalination plant.

    Inputs:
        - ambient_temperature:
            The ambient temperature, used as the base against which heat is being
            supplied. This is realistic as the final stage of desalination plants can be
            no less than the ambient temprature. This is measured in degrees Celcius.
        - buffer_hot_water_tank:
            The HTF hot-water tank.
        - thermal_desalination_plant:
            The thermal desalination plant being modelled.
        - previous_tank_tempearture:
            The temperature of the tank at the previous time step, measured in degrees
            Celcius. This is the temperature at which HTF is removed from the tank to
            supply the desalination plant.

    Outputs:
        - The mass-flow rate of HTF from the bugger tanks to the desalination plant,
          measured in litres per hour.

    Raises:
        - InputFileError:
            Raised if the thermal desalination plant does not use heat from the HTF.

    """

    return (
        thermal_desalination_plant.input_resource_consumption[ResourceType.HEAT]
        / (  # [Wth]
            buffer_hot_water_tank.heat_capacity  # [J/kg*K]
            * (previous_tank_temperature - ambient_temperature)  # [K]
        )
        * 3600
    )  # [s/h]


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
    collector_mass_flow_rate = 4

    # Instantiate loop parameters.
    best_guess_collector_input_temperature = (
        scenario.desalination_scenario.feedwater_supply_temperature
    )
    base_a_00 = 0
    base_a_01 = (
        pvt_system_size
        * collector_mass_flow_rate  # [kg/hour]
        * scenario.desalination_scenario.pvt_scenario.htf_heat_capacity  # [J/kg*K]
        * minigrid.heat_exchanger.efficiency
        / 3600  # [s/hour]
        + minigrid.hot_water_tank.mass  # [kg]
        * minigrid.hot_water_tank.heat_capacity  # [J/kg*K]
        / 3600  # [s/hour]
        + minigrid.hot_water_tank.heat_transfer_coefficient  # [W/K]
    )  # [W/K]
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
                collector_mass_flow_rate,  # [kg/s]
                1000 * irradiances[index],
                wind_speeds[index],
            )

            # Construct the matrix equation to solve for AX = B.
            b_0 = minigrid.hot_water_tank.heat_transfer_coefficient * (
                temperatures[index] + ZERO_CELCIUS_OFFSET
            ) + (  # [W]
                pvt_system_size
                * collector_mass_flow_rate  # [kg/s]
                * scenario.desalination_scenario.pvt_scenario.htf_heat_capacity  # [J/kg*K]
                * minigrid.heat_exchanger.efficiency
                * (collector_output_temperature + ZERO_CELCIUS_OFFSET)  # [K]
                / 3600  # [s/hour]
            )
            b_1 = (1 - minigrid.heat_exchanger.efficiency) * (
                collector_output_temperature + ZERO_CELCIUS_OFFSET
            )  # [K]

            # Supply heat if the tank temperature was hot enough at the previous
            # time step.
            if index > 0:
                if (
                    tank_temperature_map[index - 1]
                    > thermal_desalination_plant.minimum_htf_temperature
                ):
                    # The tank should supply temperature at this time step.
                    volume_supplied = _buffer_tank_mass_flow_rate(
                        temperatures[index],
                        minigrid.hot_water_tank,
                        thermal_desalination_plant,
                        tank_temperature_map[index - 1],
                    )  # []

                    # The supply of this water will reduce the tank temperature.
                    b_0 += (
                        volume_supplied  # [kg/hour]
                        * minigrid.hot_water_tank.heat_capacity  # [J/kg*K]
                        * (
                            scenario.desalination_scenario.feedwater_supply_temperature
                            - tank_temperature_map[index - 1]
                        )  # [K]
                        / 3600  # [s/hour]
                    )
                else:
                    volume_supplied = 0

                # The previous tank temperature will affect the current temperature.
                b_0 += (
                    minigrid.hot_water_tank.mass  # [kg]
                    * minigrid.hot_water_tank.heat_capacity  # [J/kg*K]
                    * (tank_temperature_map[index - 1] + ZERO_CELCIUS_OFFSET)  # [K]
                    / 3600  # [s/hour]
                )

            else:
                # The initial tank temperature will affect the current temperature.
                b_0 += (
                    minigrid.hot_water_tank.mass  # [kg]
                    * minigrid.hot_water_tank.heat_capacity  # [J/kg*K]
                    * (
                        scenario.desalination_scenario.feedwater_supply_temperature
                        + ZERO_CELCIUS_OFFSET
                    )  # [K]
                    / 3600  # [s/hour]
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
                    collector_input_temperature - best_guess_collector_input_temperature
                )
                < 0.1
            ):
                solution_found = True

            best_guess_collector_input_temperature = collector_input_temperature

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
    tank_volume_output_supplied: pd.DataFrame = pd.DataFrame(
        list(tank_volume_supplied_map.values()),
        index=list(tank_volume_supplied_map.keys()),
    ).sort_index()

    import pdb

    pdb.set_trace()

    return (
        pvt_collector_output_temperature,
        pvt_electric_power_per_unit,
        tank_temperature,
        tank_volume_output_supplied,
    )
