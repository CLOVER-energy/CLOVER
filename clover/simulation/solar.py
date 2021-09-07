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

import dataclasses
import enum

from logging import Logger
from typing import Any, Dict


__all__ = (
    "HybridPVTPanel",
    "PVPanel",
    "SolarPanel",
    "SolarPanelType",
)


class SolarPanelType(enum.Enum):
    """
    Specifies the type of solar panel being considered.

    - PV:
        Denotes that a PV panel is being considered.
    - PV_T:
        Denotes that a PV-T panel is being considered.

    """

    PV = "pv"
    PV_T = "pv_t"


@dataclasses.dataclass
class SolarPanel:
    """
    Represents a solar panel being considered.

    .. attribute:: azimuthal_orientation
        The azimuthal orientation of the panel, defined in degrees from North.

    .. attribute:: lifetime
        The lifetime of the panel in years.

    .. attribute:: name
        The name of the panel being considered.

    .. attribite:: panel_type
        The type of panel being considered.

    .. attribute:: reference_temperature
        The reference temperature of the PV layer of the panel, measured in degrees
        Celcius.

    .. attribute:: thermal_coefficient
        The thermal coefficient of performance of the PV layer of the panel, measured in
        kelvin^(-1).

    .. attribute:: tilt
        The angle between the panel and the horizontal.

    """

    azimuthal_orientation: float
    lifetime: int
    name: str
    reference_temperature: float
    thermal_coefficient: float
    tilt: float

    def __init_subclass__(cls, panel_type: SolarPanelType) -> None:
        """
        The init_subclass hook, run on instantiation of the :class:`SolarPanel`.

        Inputs:
            - panel_type:
                The type of panel being considered.

        Outputs:
            An instantiated :class:`SolarPanel` instance.

        """

        cls.panel_type = panel_type  # type: ignore

        return super().__init_subclass__()


class PVPanel(SolarPanel, panel_type=SolarPanelType.PV):
    """
    Represents a photovoltaic panel.

    """

    @classmethod
    def from_dict(cls, logger: Logger, solar_inputs: Dict[str, Any]) -> Any:
        """
        Instantiate a :class:`PVPanel` instance based on the input data.

        Inputs:
            - solar_inputs:
                The solar input data for the panel.

        Outputs:
            A :class:`PVPanel` instance.

        """

        logger.info("Attempting to create PVPanel from solar input data.")

        return cls(
            solar_inputs["azimuthal_orientation"],
            solar_inputs["lifetime"],
            solar_inputs["name"],
            solar_inputs["reference_temperature"],
            solar_inputs["thermal_coefficient"],
            solar_inputs["tilt"],
        )


class HybridPVTPanel(PVPanel, panel_type=SolarPanelType.PV_T):
    """
    Represents a PV-T panel.

    """
