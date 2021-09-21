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

from logging import Logger
from typing import Dict, List

import pandas as pd  # type: ignore  # pylint: disable=missing-import

from tqdm import tqdm  # type: ignore  # pylint: disable=missing-import

from ..__utils__ import BColours, InputFileError, ResourceType
from ..conversion.conversion import Convertor, ThermalDesalinationPlant
from .__utils__ import Minigrid


__all__ = (
    "calculate_pvt_output",
    "SolarPanel",
    "SolarPanelType",
)


def calculate_pvt_output(
    convertors: List[Convertor],
    irradiances: pd.Series,
    logger: Logger,
    minigrid: Minigrid,
    temperatures: pd.Series,
    wind_speeds: pd.Series,
) -> pd.DataFrame:
    """
    Computes the output of a PV-T system.

    Inputs:
        - convertors:
            The set of :class:`Convertor` instances available to the energy system.
        - irradiances:
            The :class:`pd.Series` containing irradiance information for the time
            period being modelled.
        - logger:
            The logger to use for the run.
        - minigrid:
            The minigrid being modelled currently.
        - temperatures:
            The :class:`pd.Series` containing temperature information for the time
            period being modelled.
        - wind_speeds:
            The :class:`pd.Series` containing wind-speed information for the time period
            being modelled.

    Outputs:
        - clean_water_produced_per_unit:
            The amount of clean water produced per unit PV-T, delivered by the PV-T
            system in conjunction with any desalination plants present.
        - pvt_electric_power_per_unit:
            The electric power, per unit PV-T, delivered by the PV-T system.

    """

    if minigrid.pvt_panel is None:
        raise InputFileError(
            "energy system inputs",
            "The energy system specified does not contain a PV-T panel but PV-T "
            "modelling was requested.",
        )

    # Determine the thermal desalination plant being used.
    try:
        thermal_desalination_plant: ThermalDesalinationPlant = [
            convertor
            for convertor in convertors
            if isinstance(convertor, ThermalDesalinationPlant)
        ][0]
    except IndexError:
        logger.error(
            "%sNo valid thermal desalination plants specified despite PV-T being "
            "specified.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "conversion inputs", "No valid thermal desalination plants specified."
        ) from None

    # Instantiate maps for easy PV-T power lookups.
    pvt_electric_power_per_unit_map: Dict[int, float] = {}
    pvt_volume_output_supplied_map: Dict[int, float] = {}
    try:
        for index in tqdm(
            range(len(temperatures)),
            desc="pv-t performance",
            leave=False,
            unit="hour",
        ):
            # Compute the fractional PV-T performance and thermal PV-T outputs.
            (
                _,
                fractional_electric_performance,
                volume_supplied,
            ) = minigrid.pvt_panel.fractional_performance(
                temperatures[index],
                thermal_desalination_plant,
                1000 * irradiances[index],
                wind_speeds[index],
            )
            pvt_electric_power_per_unit_map[index] = fractional_electric_performance
            pvt_volume_output_supplied_map[index] = volume_supplied
    except TypeError:
        logger.error(
            "The PV-T system size must be specified explicitly on the command line."
        )
        raise Exception("Missing command-line argument: --pvt-system-size.") from None

    # Convert these outputs to dataframes and return.
    pvt_electric_power_per_unit: pd.DataFrame = (
        pd.DataFrame(  # type: ignore
            list(pvt_electric_power_per_unit_map.values()),
            index=list(pvt_electric_power_per_unit_map.keys()),
        ).sort_index()
        * minigrid.pvt_panel.pv_unit
    )
    # @@@ Fix thermal unit stuff here...

    return pd.DataFrame([0] * temperatures.size), pvt_electric_power_per_unit
