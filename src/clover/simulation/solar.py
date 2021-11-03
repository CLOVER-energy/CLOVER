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

import collections

from logging import Logger
from typing import Dict, Tuple

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


# Temperature precision:
#   The precision required when solving the differential equation for the system
#   temperatures.
TEMPERATURE_PRECISION: float = 1.44


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
    best_guess_tank_temperature: float,
    buffer_tank: HotWaterTank,
    thermal_desalination_plant: ThermalDesalinationPlant,
) -> float:
    """
    Computes the mass-flow rate of HTF from the buffer tanks to the desalination plant.

    Inputs:
        - ambient_temperature:
            The ambient temperature, used as the base against which heat is being
            supplied. This is realistic as the final stage of desalination plants can be
            no less than the ambient temprature. This is measured in degrees Celcius.
        - best_guess_tank_temperature:
            The best guess at the tank temperature at the current time step, measured in
            degrees Celcius. This is the temperature at which HTF is removed from the
            tank to supply the desalination plant.
        - buffer_tank:
            The HTF hot-water tank.
        - thermal_desalination_plant:
            The thermal desalination plant being modelled.

    Outputs:
        - The mass-flow rate of HTF from the bugger tanks to the desalination plant,
          measured in litres per hour.

    Raises:
        - InputFileError:
            Raised if the thermal desalination plant does not use heat from the HTF.

    """

    return (
        thermal_desalination_plant.input_resource_consumption[ResourceType.HEAT]
        * 3600  # [s/h]
        / (  # [Wth]
            buffer_tank.heat_capacity  # [J/kg*K]
            * (best_guess_tank_temperature - ambient_temperature)  # [K]
        )
    )  # [kg/hour]


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
            "%sThe energy system does not contain a PV-T panel despite the PV-T output "
            "computation function being called.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "energy system inputs",
            "The energy system specified does not contain a PV-T panel but PV-T "
            "modelling was requested.",
        )

    if minigrid.buffer_tank is None:
        logger.error(
            "%sThe energy system does not contain a buffer tank despite the PV-T "
            "output computation function being called.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "energy system inputs",
            "The energy system specified does not contain a buffer tank but PV-T "
            "modelling was requested.",
        )

    # Instantiate debugging variables
    runs: int = 0

    # Instantiate maps for easy PV-T power lookups.
    pvt_collector_output_temperature_map: Dict[int, float] = collections.defaultdict(
        lambda: scenario.desalination_scenario.feedwater_supply_temperature
    )
    pvt_electric_power_per_unit_map: Dict[int, float] = {}
    tank_temperature_map: Dict[int, float] = collections.defaultdict(
        lambda: scenario.desalination_scenario.feedwater_supply_temperature
    )
    tank_volume_supplied_map: Dict[int, float] = collections.defaultdict(float)

    # Instantiate other variables required in the loop
    best_guess_collector_input_temperature: float = (
        scenario.desalination_scenario.feedwater_supply_temperature
    )
    best_guess_tank_temperature: float = (
        scenario.desalination_scenario.feedwater_supply_temperature
    )

    # Compute the various terms which remain common across all time steps.
    pvt_heat_transfer = (
        scenario.desalination_scenario.pvt_scenario.mass_flow_rate  # [kg/hour]
        * scenario.desalination_scenario.pvt_scenario.htf_heat_capacity  # [J/kg*K]
        * minigrid.heat_exchanger.efficiency
        / 3600  # [s/hour]
    )  # [W/K]
    tank_environment_heat_transfer = (
        minigrid.buffer_tank.heat_transfer_coefficient
    )  # [W/K]
    tank_internal_energy = (
        minigrid.buffer_tank.mass  # [kg]
        * minigrid.buffer_tank.heat_capacity  # [J/kg*K]
        / 3600  # [s/hour]
    )

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
        # Determine whether the PV-T is flowing.
        desalination_plant_on: bool = (
            tank_temperature_map[index - 1]
            > thermal_desalination_plant.minimum_htf_temperature
        )
        pvt_flow_on: bool = (
            pvt_collector_output_temperature_map[index - 1]
            > tank_temperature_map[index - 1]
        ) and irradiances[index] > 0

        # Only compute outputs if there is input irradiance.
        solution_found: bool = False
        # Keep processing until the temperatures are consistent.
        while not solution_found:
            # Use the AI to determine the output temperature of the collector, based on
            # the best guess of the collector input temperature.
            if irradiances[index] > 0:
                (
                    fractional_electric_performance,
                    collector_output_temperature,
                ) = minigrid.pvt_panel.calculate_performance(
                    temperatures[index],
                    best_guess_collector_input_temperature,
                    logger,
                    scenario.desalination_scenario.pvt_scenario.mass_flow_rate,
                    1000 * irradiances[index],
                    wind_speeds[index],
                )
            else:
                fractional_electric_performance = 0
                collector_output_temperature = (
                    scenario.desalination_scenario.feedwater_supply_temperature
                )

            # Determine the volume withdrawn from the buffer tanks
            volume_supplied = (
                _buffer_tank_mass_flow_rate(
                    temperatures[index],
                    best_guess_tank_temperature,
                    minigrid.buffer_tank,
                    thermal_desalination_plant,
                )
                * desalination_plant_on
            )

            tank_load_enthalpy_transfer = (
                volume_supplied  # [kg/hour]
                * minigrid.buffer_tank.heat_capacity  # [J/kg*K]
                / 3600  # [s/hour]
            )  # [W/K]

            # Determine the tank temperature and collector input temperature that match.
            resultant_vector = [
                (
                    pvt_heat_transfer
                    * (collector_output_temperature + ZERO_CELCIUS_OFFSET)
                    if pvt_flow_on
                    else 0
                )
                + tank_environment_heat_transfer
                * (temperatures[index] + ZERO_CELCIUS_OFFSET)
                + tank_internal_energy
                * (tank_temperature_map[index - 1] + ZERO_CELCIUS_OFFSET)
                + (
                    tank_load_enthalpy_transfer
                    * (
                        scenario.desalination_scenario.feedwater_supply_temperature
                        + ZERO_CELCIUS_OFFSET
                    )
                    if desalination_plant_on
                    else 0
                ),
                (
                    (1 - minigrid.heat_exchanger.efficiency)
                    * (collector_output_temperature + ZERO_CELCIUS_OFFSET)
                ),
            ]

            matrix = [
                [
                    0,
                    (
                        (pvt_heat_transfer if pvt_flow_on else 0)
                        + tank_environment_heat_transfer
                        + tank_internal_energy
                        + (tank_load_enthalpy_transfer if desalination_plant_on else 0)
                    ),
                ],
                [-minigrid.heat_exchanger.efficiency, 1],
            ]

            collector_input_temperature, tank_temperature = linalg.solve(
                a=matrix, b=resultant_vector
            )

            # Convert into Celcius.
            collector_input_temperature -= ZERO_CELCIUS_OFFSET
            tank_temperature -= ZERO_CELCIUS_OFFSET

            # If a solution has been found, then break the loop.
            if (
                abs(
                    collector_input_temperature - best_guess_collector_input_temperature
                )
                < TEMPERATURE_PRECISION
            ) and (
                abs(tank_temperature - best_guess_tank_temperature)
                < TEMPERATURE_PRECISION
            ):
                runs = 0
                solution_found = True

            runs += 1
            if runs > 10:
                logger.debug(
                    "Index: %s: Run # %s: PV-T=%s, Plant=%s: Solution not yet found, "
                    "re-iterating: T_c,in=%s degC, best-guess T_c,in=%s degC, "
                    "T_tank=%s degC, best-guess T_tank=%s",
                    index,
                    runs,
                    "on" if pvt_flow_on else "off",
                    "on" if desalination_plant_on else "off",
                    round(collector_input_temperature, 3),
                    round(best_guess_collector_input_temperature, 3),
                    round(tank_temperature, 3),
                    round(best_guess_tank_temperature, 3),
                )
            # best_guess_collector_input_temperature += (TEMPERATURE_PRECISION / 2) * (
            #     2
            #     * (collector_input_temperature > best_guess_collector_input_temperature)
            #     - 1
            # )
            # best_guess_tank_temperature += (TEMPERATURE_PRECISION / 2) * (
            #     2 * (tank_temperature > best_guess_tank_temperature) - 1
            # )

            best_guess_collector_input_temperature = collector_input_temperature
            best_guess_tank_temperature = tank_temperature

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

    # with open("tmp.csv", "w") as f:
    #     f.write(
    #         pd.concat(
    #             [
    #                 pvt_collector_output_temperature,
    #                 pvt_electric_power_per_unit,
    #                 tank_temperature,
    #                 tank_volume_output_supplied,
    #             ],
    #             axis=1,
    #         ).to_csv()
    #     )

    # logger.warn(
    #     "%sUsing saved PV-T profile: this should be used for debugging only.%s",
    #     BColours.warning,
    #     BColours.endc,
    # )

    # with open("tmp.csv", "r") as f:
    #     filedata = pd.read_csv(f, header=None, index_col=0)
    #     pvt_collector_output_temperature = pd.DataFrame(filedata[1].values)
    #     pvt_electric_power_per_unit = pd.DataFrame(filedata[2].values)
    #     tank_temperature = pd.DataFrame(filedata[3].values)
    #     tank_volume_output_supplied = pd.DataFrame(filedata[4].values)

    #     # Bodge to fix units.
    #     pvt_electric_power_per_unit = pd.DataFrame(
    #         pvt_electric_power_per_unit
    #         * pd.DataFrame(irradiances.values)
    #         / (minigrid.pvt_panel.reference_efficiency)
    #     )

    return (
        pvt_collector_output_temperature,
        pvt_electric_power_per_unit,
        tank_temperature,
        tank_volume_output_supplied,
    )
