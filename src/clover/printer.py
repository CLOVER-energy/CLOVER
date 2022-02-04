#!/usr/bin/python3
########################################################################################
# printer.py - Pretty printing of CLOVER outputs to the console.                       #
#                                                                                      #
# Authors: Phil Sandwell, Ben Winchester                                               #
# Copyright: Phil Sandwell, 2021                                                       #
# Date created: 25/01/2021                                                             #
# License: Open source                                                                 #
########################################################################################
"""
printer.py - The printing module for CLOVER.

In order to print information to the end user in an easily understandable way, CLOVER
utilises this module which exposes functionality for easilly computing and outputting
strings to the end user.

"""

from typing import List

from .__utils__ import Scenario
from .optimisation.__utils__ import OptimisationParameters
from .simulation.__utils__ import Minigrid

__all__ = ("generate_optimisation_string",)


def generate_optimisation_string(
    minigrid: Minigrid, optimisation_inputs: OptimisationParameters, scenario: Scenario,
) -> str:
    """
    Generate and return the optimisation string.

    Inputs:
        - minigrid:
            The :class:`Minigrid` being considered for this run.
        - optimisation_inputs:
            The input parameters for this optimisation.
        - scenario:
            The :class:`__utils__.Scenario` currently being considered.

    Outputs:
        - A single `str` to display to the user when running a CLOVER optimisation.

    """

    optimisation_string_list: List[str] = []

    # Append the PV panel information if relevant.
    if scenario.pv and optimisation_inputs.pv_size is not None:
        optimisation_string_list.append(
            "- PV resolution of {} units ({} kWp per unit)".format(
                optimisation_inputs.pv_size.step, minigrid.pv_panel.pv_unit
            )
        )

    # Append the battery storage information if relevant.
    if (
        scenario.battery
        and optimisation_inputs.storage_size is not None
        and minigrid.battery is not None
    ):
        optimisation_string_list.append(
            "- Storage resolution of {} units ({} kWh per unit)".format(
                optimisation_inputs.storage_size.step, minigrid.battery.storage_unit,
            )
        )

    # Append the clean-water information if relevant.
    if scenario.desalination_scenario is not None:
        if (
            optimisation_inputs.cw_pvt_size is not None
            and minigrid.pvt_panel is not None
        ):
            optimisation_string_list.append(
                "- Clean-water PV-T resolution of "
                + "{} units ({} kWp and {} kWth per unit)".format(
                    optimisation_inputs.cw_pvt_size.step,
                    minigrid.pvt_panel.pv_unit,
                    minigrid.pvt_panel.thermal_unit,
                )
            )
        if (
            optimisation_inputs.clean_water_tanks is not None
            and minigrid.clean_water_tank is not None
        ):
            optimisation_string_list.append(
                "- Clean-water tank resolution of {} ".format(
                    optimisation_inputs.clean_water_tanks.step
                )
                + "units (1 tank of size {} litres per unit)".format(
                    minigrid.clean_water_tank.mass
                )
            )

    # Append the hot-water information if relevant.
    if scenario.hot_water_scenario is not None:
        if (
            optimisation_inputs.hw_pvt_size is not None
            and minigrid.pvt_panel is not None
        ):
            optimisation_string_list.append(
                "- Hot-water PV-T resolution of "
                + "{} units ({} kWp and {} kWth per unit)".format(
                    optimisation_inputs.hw_pvt_size.step,
                    minigrid.pvt_panel.pv_unit,
                    minigrid.pvt_panel.thermal_unit,
                )
            )
        if (
            optimisation_inputs.hot_water_tanks is not None
            and minigrid.hot_water_tank is not None
        ):
            optimisation_string_list.append(
                "- Hot-water tank resolution of {} ".format(
                    optimisation_inputs.hot_water_tanks.step
                )
                + "units (1 tank of size {} litres per unit)".format(
                    minigrid.hot_water_tank.mass
                )
            )

    # Append the converter information.
    optimisation_string_list.extend(
        [
            "- {} resolution of {} units (1 {} device of {} max output per unit)".format(
                converter.name,
                sizing.step,
                converter.name,
                converter.maximum_output_capacity,
            )
            for converter, sizing in optimisation_inputs.converter_sizes.items()
        ]
    )

    optimisation_string: str = "\n".join(
        [entry for entry in optimisation_string_list if entry != ""]
    )

    return optimisation_string
