#!/usr/bin/python3
########################################################################################
# __utils__.py - Profile-generation utility module.                                    #
#                                                                                      #
# Author(s): Phil Sandwell, Ben Winchester                                             #
# Copyright: Phil Sandwell, 2021                                                       #
# Date created: 11/08/2021                                                             #
# License: Open source                                                                 #
# Most recent update: 14/07/2021                                                       #
#                                                                                      #
# Additional credits:                                                                  #
#     Iain Staffell, Stefan Pfenninger & Scot Wheeler                                  #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
__utils__.py - The profile-generation utility module for CLOVER.

This module fetches profiles from renewables.ninja, parses them and saves them for use
locally within CLOVER. The profiles that are fetched are determined by the information
that is passed in to the module.

"""

import dataclasses

from typing import Any, Dict, List, Optional, Set, Union

from ..__utils__ import (
    RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING,
    CleanWaterScenario,
    InputFileError,
    NAME,
    ResourceType,
)

from ..generation.solar import HybridPVTPanel, PVPanel
from .diesel import DieselGenerator
from .exchanger import Exchanger
from .storage import Battery, CleanWaterTank, HotWaterTank

__all__ = ("Minigrid",)

# Resource Type:
#   Used for parsing resource-type information.
RESOURCE_TYPE = "resource_type"


@dataclasses.dataclass
class Minigrid:
    """
    Represents an energy system.

    .. attribute:: ac_to_ac_conversion_efficiency
        The conversion efficiency from AC to AC.

    .. attribute:: ac_to_dc_conversion_efficiency
        The conversion efficiency from AC to DC.

    .. attribute:: ac_transmission_efficiency
        The AC transmission efficiency, if applicable.

    .. attribute:: battery
        The battery being modelled, if applicable.

    .. attribute:: clean_water_tank
        The clean-water tank being modelled, if applicable.

    .. attribute:: dc_to_ac_conversion_efficiency
        The conversion efficiency from DC to AC.

    .. attribute:: dc_to_dc_conversion_efficiency
        The conversion efficiency from DC to DC.

    .. attribute:: dc_transmission_efficiency
        The DC transmission efficiency, if applicable.

    .. attribute:: diesel_generator
        The diesel backup generator associated with the minigrid system.

    .. attribute:: heat_exchanger
        The heat exchanger associated with the minigrid system.

    .. attribute:: hot_water_tank
        The hot-water tank being modelled, if applicable.

    .. attribute:: pv_panel
        The PV panel being considered.

    .. attribute:: pvt_panel
        The PV-T panel being considered, if applicable.

    """

    ac_to_ac_conversion_efficiency: Optional[float]
    ac_to_dc_conversion_efficiency: Optional[float]
    ac_transmission_efficiency: Optional[float]
    battery: Optional[Battery]
    clean_water_tank: Optional[CleanWaterTank]
    dc_to_ac_conversion_efficiency: Optional[float]
    dc_to_dc_conversion_efficiency: Optional[float]
    dc_transmission_efficiency: Optional[float]
    diesel_generator: Optional[DieselGenerator]
    heat_exchanger: Optional[Exchanger]
    hot_water_tank: Optional[HotWaterTank]
    pv_panel: PVPanel
    pvt_panel: Optional[HybridPVTPanel]

    @classmethod
    def from_dict(
        cls,
        diesel_generator: DieselGenerator,
        minigrid_inputs: Dict[Union[int, str], Any],
        pv_panel: PVPanel,
        pvt_panel: Optional[HybridPVTPanel],
        battery_inputs: Optional[List[Dict[Union[int, str], Any]]] = None,
        exchanger_inputs: Optional[List[Dict[Union[int, str], Any]]] = None,
        tank_inputs: Optional[List[Dict[Union[int, str], Any]]] = None,
    ) -> Any:
        """
        Returns a :class:`Minigrid` instance based on the inputs provided.

        Inputs:
            - diesel_generator:
                The diesel backup generator to use for the run.
            - minigrid_inputs:
                The inputs for the minigrid/energy system, extracted from the input
                file.
            - pv_panel:
                The :class:`PVPanel` instance to use for the run.
            - pvt_panel:
                The :class:`HybridPVTPanel` instance to use for the run, if appropriate.
            - battery_inputs:
                The battery input information.
            - exchanger_inputs:
                The heat-exchanger input information.
            - tank_inputs:
                The tank input information.

        Outputs:
            - A :class:`Minigrid` instance based on the inputs provided.

        """

        # Parse the battery information.
        if battery_inputs is not None:
            batteries = {
                entry[NAME]: Battery.from_dict(entry) for entry in battery_inputs
            }
        else:
            batteries = {}

        # Parse the heat-exchanger information.
        if exchanger_inputs is not None:
            exchangers = {
                entry[NAME]: Exchanger.from_dict(entry) for entry in exchanger_inputs
            }
        else:
            exchangers = {}

        tanks: Dict[str, Union[CleanWaterTank, HotWaterTank]] = {}
        # Parse the tank information.
        if tank_inputs is not None:
            for entry in tank_inputs:
                if (
                    RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING[entry[RESOURCE_TYPE]]
                    == ResourceType.CLEAN_WATER
                ):
                    try:
                        tanks[entry[NAME]] = CleanWaterTank.from_dict(entry)
                    except KeyError as e:
                        raise InputFileError(
                            "tank inputs",
                            f"Error parsing clean-water tank {entry['name']}: {str(e)}",
                        )
                elif (
                    RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING[entry[RESOURCE_TYPE]]
                    == ResourceType.HOT_CLEAN_WATER
                ):
                    try:
                        tanks[entry[NAME]] = HotWaterTank.from_dict(entry)
                    except KeyError as e:
                        raise InputFileError(
                            "tank inputs",
                            f"Error parsing hot-water tank {entry['name']}: {str(e)}",
                        )
                else:
                    raise InputFileError(
                        "tank inputs",
                        f"The tank '{entry['name']}' uses an unknown resource type: "
                        + f"{entry[RESOURCE_TYPE]}",
                    )
        else:
            tanks = {}

        # Return the minigrid instance.
        return cls(
            minigrid_inputs["conversion"]["ac_to_ac"]
            if "ac_to_ac" in minigrid_inputs["conversion"]
            else None,
            minigrid_inputs["conversion"]["ac_to_ac"]
            if "ac_to_dc" in minigrid_inputs["conversion"]
            else None,
            minigrid_inputs["ac_transmission_efficiency"]
            if "ac_transmission_efficiency" in minigrid_inputs
            else None,
            batteries[minigrid_inputs["battery"]]
            if "battery" in minigrid_inputs
            else None,
            tanks[minigrid_inputs["clean_water_tank"]]
            if "clean_water_tank" in minigrid_inputs
            else None,
            minigrid_inputs["conversion"]["ac_to_ac"]
            if "dc_to_ac" in minigrid_inputs["conversion"]
            else None,
            minigrid_inputs["conversion"]["ac_to_ac"]
            if "dc_to_dc" in minigrid_inputs["conversion"]
            else None,
            minigrid_inputs["dc_transmission_efficiency"]
            if "dc_transmission_efficiency" in minigrid_inputs
            else None,
            diesel_generator,
            exchangers[minigrid_inputs["heat_exchanger"]]
            if "heat_exchanger" in minigrid_inputs
            else None,
            tanks[minigrid_inputs["hot_water_tank"]]
            if "hot_water_tank" in minigrid_inputs
            else None,
            pv_panel,
            pvt_panel,
        )
