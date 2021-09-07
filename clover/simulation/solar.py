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
from typing import Any, Dict, List, Tuple

import pandas as pd  # type: ignore  # pylint: disable=missing-import


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

    .. attribute:: area
        The area of panel per unit step. E.G., for PV systems, this corresponds to the
        area of the panel that produces 1kWp of electrical output.

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

    area: Optional[float]
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
            - logger:
                The logger to use for the run.
            - solar_inputs:
                The solar input data for the panel.

        Outputs:
            A :class:`PVPanel` instance.

        """

        logger.info("Attempting to create PVPanel from solar input data.")

        return cls(
            solar_inputs["area"] if "area" in solar_inputs else None,
            solar_inputs["azimuthal_orientation"],
            solar_inputs["lifetime"],
            solar_inputs["name"],
            solar_inputs["reference_temperature"],
            solar_inputs["thermal_coefficient"],
            solar_inputs["tilt"],
        )


class HybridPVTPanel(SolarPanel, panel_type=SolarPanelType.PV_T):
    """
    Represents a PV-T panel.

    .. attribute:: mass_flow_rate
        The mass-flow rate of heat-transfer fluid through the PV-T collector.

    """

    def __init__(
        self,
        logger: Logger,
        solar_inputs: Dict[str, Any],
        solar_panels: List[SolarPanel],
    ) -> Any:
        """
        Instantiate a :class:`HybridPVTPanel` instance based on the input data.

        Inputs:
            - logger:
                The logger to use for the run.
            - solar_inputs:
                The solar input data specific to this panel.
            - solar_panels:
                The full set of solar generation data.

        """

        # Attempt to extract information about the corresponding PV layer.
        try:
            pv_layer = [
                panel for panel in solar_panels if panel.name == solar_inputs["pv"]
            ][0]
        except IndexError:
            logger.error(
                "Could not find corresponding PV-layer data for layer %s for panel %s.",
                solar_inputs["pv"],
                solar_inputs["name"],
            )

        super().__init__(
            solar_inputs["azimuthal_orientation"],
            solar_inputs["lifetime"],
            solar_inputs["name"],
            pv_layer.reference_temperature,
            pv_layer.thermal_coefficient,
            solar_inputs["tilt"],
        )

        self.mass_flow_rate = solar_inputs["mass_flow_rate"]

    def fractional_performance(
        self,
        ambient_temperature: pd.Series,
        irradiance: pd.Series,
        wind_speed: pd.Series,
    ) -> Tuple[None, pd.Series]:
        """
        Computes the fractional performance of the :class:`HybridPVTPanel`.

        Additional Credits:
            The PV-T collector model used here was developed in-house by
            Benedict Winchester, benedict.winchester@gmail.com

        Inputs:
            - ambient_temperature:
                The ambient temperature surrounding the collector, measured in degrees
                Celcius.
            - irradiance:
                The total irradiance incident on the collector, both direct and diffuse,
                measured in W/m^2.
            - wind_speed:
                The wind speed at the collector location, measured in meters per second.

        Outputs:
            - collector_output_temperature:
                The output temperature of the HTF leaving the collector.
            - fractional_electrical_performance:
                The fractional electrical performance of the collector, where 1
                corresponds to the rated performance under standard test conditions.

        """

        # Compute the temperature of the collector using the reduced PV-T model.
        collector_temperature = ambient_temperature + 0.035 * irradiance

        # Compute the fractional electrical performance of the collector.
        fractional_electrical_performance = 1 - self.thermal_coefficient * (
            collector_temperature - self.reference_temperature
        )

        # Return this, along with the output temperature of HTF leaving the collector.
        return None, fractional_electrical_performance
