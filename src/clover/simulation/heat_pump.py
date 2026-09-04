#!/usr/bin/python3.10
########################################################################################
# heat_pump.py - The heat-pump module for CLOVER.                                      #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2022                                                      #
# Date created: 03/11/2022                                                             #
# License: MIT, Open-source                                                            #
# For more information, contact: benedict.winchester@gmail.com                         #
########################################################################################

"""
heat_pump.py - The heat-pump module for CLOVER.

The heat-pump module contains functionality for modelling a heat pump's performance.

This code was reproduced with permission from:
    Winchestser, B., Nelson, J., and Markides, C.N., 'HeatDesalination',
    [Computer software],
    Available from: https://github.com/BenWinchester/HEATDesalination

"""

import dataclasses

from typing import Tuple

from scipy import interpolate

__all__ = (
    "calculate_heat_pump_electricity_consumption_and_cost_and_emissions",
    "HeatPump",
)

# HEAT_PUMP_SPECIFIC_EMISSIONS:
#   The specific emissions of the heat pumps installed.
#   Reference:
#       Moret, S. Strategic energy planning under uncertainty. Ph.D. thesis, EPFL (2017)
#       https://infoscience.epfl.ch/record/231814?ln=en
#
HEAT_PUMP_SPECIFIC_EMISSIONS: float = 174.8


@dataclasses.dataclass
class HeatPump:
    """
    Represents a heat pump.

    .. attribute:: cop_data
        The data points for interpolation for COP.

    .. attribute:: name
        The name of the heat pump.

    .. attribute:: specific_cost_data
        The data points for interpolation for specific cost in USD per kW.

    """

    # Private attributes:
    # .. attribute:: _interpolator
    #   Used for storing the scipy interpolator created.
    #

    cop_data: list[float]
    name: str
    specific_costs_data: str
    _interpolator: interpolate.PchipInterpolator | None = None

    def get_cost(self, cop: float, thermal_power: float) -> float:
        """
        Calculate the cost of the heat pump given its COP and thermal power.

        Inputs:
            - cop:
                The COP of the heat pump.
            - thermal_power:
                The thermal power rating of the heat pump, i.e., its maximum thermal
                power output in kWh_th.

        Outputs:
            The cost of the heat pump in USD.

        """

        # Set the interpolator if not already calculated.
        if self._interpolator is None:
            self._interpolator = interpolate.PchipInterpolator(
                self.cop_data, self.specific_costs_data
            )

        # Determine the cost
        return float(self._interpolator(cop)) * thermal_power

    def get_emissions(self, thermal_power: float) -> float:
        """
        Calculate the emissions associated with the heat pump given its thermal power.

        Inputs:
            - thermal_power:
                The thermal power rating of the heat pump, i.e., its maximum thermal
                power output in kWh_th.

        Outputs:
            The emissions associated with the heat pump in USD.

        """

        # Determine the emissions
        return HEAT_PUMP_SPECIFIC_EMISSIONS * thermal_power


def _coefficient_of_performance(
    condensation_temperature: float,
    evaporation_temperature: float,
    pinch_point_temperature_difference: float,  # pylint: disable=unused-argument
) -> float:
    """
    Calculate the coefficient of performance of the heat pump.

    The coefficient of performance of the heat pump can be calculated based on the
    difference between the temperatures of the condensation and evaporation resevoirs:

        COP_Carnot = T_condensation / (T_condensation - T_evaporation)

    in such a way that, as the two temperatures appraoch one another, the COP increases
    as there is less of a temperature range to span. The system efficiency is the
    fraction of this ideal Carnot efficiency which can be achieved.

    The above COP is the Carnot COP, that is, the COP of an ideal heat pump operating a
    Carnot cycle between the two temperature resevoirs. In reality, the COP of the heat
    pump will differ from the ideal Carnot COP. Here, we use an empirically-derived
    relationship from
        Gangar N, Macchietto S, Markides CN (2020)
        Recovery and Utilization of Low-Grade Waste Heat in the Oil-Refining Industry
        Using Heat Engines and Heat Pumps: An International Technoeconomic Comparison.
        Energies 13:2560
    which gives the COP as:

        COP_real = 1 / (
            (1.79 / COP_Carnot)
            + 0.11
        )

    Inputs:
        - condensation_temperature:
            The temperature at which condensation within the heat pump occurs. This is
            the temperature at which heat is transferred from the heat pump to the
            surroundings and is hence the desired temperature for the environment,
            measured in degrees Kelvin.
        - evaporation_temperature:
            The temperature at which evaporation within the heat pump occurs. This is
            the temperature at which heat is absorbed from the environment in order to
            evaporate the heat-transfer fluid (refrigerant) within the heat pump,
            measured in degrees Kelvin.
        - pinch_point_temperature_difference:
            The temperature difference between the desired condensation and evaporation
            temperatures and the real temperatures achieved, dictated by the effective
            possible rate of heat transfer across the heat exchangers in the system.
        - system_efficiency:
            The efficiency of the heat pump system given as a fraction of its efficiency
            against the Carnot efficiency.

    Outputs:
        The coefficient of performance of the heat pump.

    """

    _cop_carnot = (
        condensation_temperature
        # + pinch_point_temperature_difference
    ) / (condensation_temperature - evaporation_temperature)

    _cop_real = 1 / ((1.79 / _cop_carnot) + 0.11)

    return _cop_real


def calculate_heat_pump_electricity_consumption_and_cost_and_emissions(
    condensation_temperature: float,
    evaporation_temperature: float,
    heat_demand: float,
    heat_pump: HeatPump,
    pinch_point_temperature_difference,
) -> Tuple[float, float, float]:
    """
    Calculate the electricity comsumption and the cost and emissions of the heat pump.

    The coefficient of performance of a heat pump gives the ratio between the heat
    demand which can be achieved and the electricity input which is required to achieve
    it:

        COP = q_th / q_el,

    where q_th and q_el give the heat and electricity powers/energies respectively.
    Hence, this equation can be reversed to give:

        q_el = q_th / COP.

    The heat pump has an associated specific emissions based on its thermal power
    delivered which is calculated here also.

    Inputs:
        - condensation_temperature:
            The temperature at which condensation within the heat pump occurs. This is
            the temperature at which heat is transferred from the heat pump to the
            surroundings and is hence the desired temperature for the environment,
            measured in degrees Kelvin.
        - evaporation_temperature:
            The temperature at which evaporation within the heat pump occurs. This is
            the temperature at which heat is absorbed from the environment in order to
            evaporate the heat-transfer fluid (refrigerant) within the heat pump,
            measured in degrees Kelvin.
        - heat_demand:
            The heat demand flux, measured in kiloWatts.
        - heat_pump:
            The heat pump currently being considered.
        - pinch_point_temperature_difference:
            The temperature difference between the desired condensation and evaporation
            temperatures and the real temperatures achieved, dictated by the effective
            possible rate of heat transfer across the heat exchangers in the system.

    Outputs:
        - The cost of the heat pump in USD,
        - The associated emissions, measured in kg CO2-eq,
        - The electricity consumption, measured in kiloWatts.

    """

    power_consumption = heat_demand / (
        cop := _coefficient_of_performance(
            condensation_temperature,
            evaporation_temperature,
            pinch_point_temperature_difference,
        )
    )
    cost = heat_pump.get_cost(cop, heat_demand)
    emissions = heat_pump.get_emissions(heat_demand)

    return (cost, emissions, power_consumption)
