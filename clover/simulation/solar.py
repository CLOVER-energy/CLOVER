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
from typing import Any, Dict

from ..__utils__ import BColours, InputFileError


__all__ = ("PV",)


class PV:
    """
    Represents a PV panel being modelled.

    .. attribute:: reference_efficiency
        The reference efficiency of the panel.

    .. attribute:: reference_temperature
        The reference temperature of the panel, measured in Celcius.

    .. attribute:: thermal_coefficient
        The thermal coefficient of the panel, measured in Kelvin^(-1).

    """

    def __init__(
        self,
        reference_temperature: float,
        thermal_coefficient: float,
        *,
        reference_efficiency: float = 1,
    ) -> None:
        """
        Instnatiate a :class:`PV` instance based on the information provided.

        Inputs:
            - reference_efficiency:
                The reference efficiency of the panel.
            - reference_temperature:
                The reference temperature of the panel, measured in Celcius.
            - thermal_coefficient:
                The thermal coefficient of the panel, measured in Kelvin^(-1).

        """

        self.reference_efficiency = reference_efficiency
        self.reference_temperature = reference_temperature
        self.thermal_coefficient = thermal_coefficient

    @classmethod
    def from_data(cls, logger: Logger, solar_inputs: Dict[str, Any]) -> Any:
        """
        Returns a :class:`PV` instance based on the input data provided.

        Inputs:
            - logger:
                The logger to use for the run.
            - solar_inputs:
                The solar input data relevant to this instance.

        Outputs:
            - A :class:`PV` instance based on the data provided.

        """

        try:
            return cls(
                solar_inputs["reference_temperature"],
                solar_inputs["thermal_coefficient"],
                reference_efficiency=solar_inputs["reference_efficiency"],
            )
        except KeyError as e:
            logger.error("Solar inputs file is missing information: %s", str(e))
            raise InputFileError(
                "solar inputs",
                f"{BColours.fail}Missing data in the solar inputs file: {str(e)}"
                + f"{BColours.endc}",
            ) from None

    def electrical_efficiency(self, pv_temperature: float) -> float:
        """
        Returns the electrical efficiency of the PV panel based on its temperature.

        :param pv_temperature:
            The temperature of the PV layer, measured in Kelvin.

        :return:
            A decimal giving the percentage efficiency of the PV panel between 0 (0%
            efficiency), and 1 (100% efficiency).

        """

        return self.reference_efficiency * (  # [unitless]
            1
            - self.thermal_coefficient  # [1/K]
            * (pv_temperature - self.reference_temperature)  # [K]
        )
