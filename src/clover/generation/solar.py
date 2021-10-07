#!/usr/bin/python3
########################################################################################
# solar.py - Solar generation module  .                                                #
#                                                                                      #
# Author: Phil Sandwell                                                                #
# Copyright: Phil Sandwell, 2021                                                       #
# License: Open source                                                                 #
# Most recent update: 14/07/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
solar.py - The solar-profile-generation module for CLOVER.

This module fetches solar profiles from renewables.ninja, parses them and saves them
for use locally within CLOVER.

"""

import dataclasses
import enum

from logging import Logger
from typing import Any, Dict, List, Optional, Tuple

import numpy as np  # type: ignore  # pylint: disable=import-error
import pandas as pd  # type: ignore  # pylint: disable=import-error

from ..__utils__ import HEAT_CAPACITY_OF_WATER, InputFileError, Location
from ..conversion.conversion import ThermalDesalinationPlant
from .__utils__ import BaseRenewablesNinjaThread, SolarDataType, total_profile_output

__all__ = (
    "HybridPVTPanel",
    "PVPanel",
    "SolarDataThread",
    "SolarDataType",
    "solar_degradation",
    "SOLAR_LOGGER_NAME",
    "total_solar_output",
)


# Default PV unit:
#   The default PV unit size to use, measured in kWp.
DEFAULT_PV_UNIT = 1  # [kWp]

# Solar logger name:
#   The name to use for the solar logger.
SOLAR_LOGGER_NAME = "solar_generation"


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

    .. attribute:: pv_unit
        The unit of PV power being considered, defaulting to 1 kWp.

    .. attribute:: pv_unit_overrided
        Whether the default PV unit was overrided (True) or not (False).

    .. attribute:: reference_efficiency
        The efficiency of the PV layer under standard test conditions.

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
    pv_unit: float
    pv_unit_overrided: bool
    reference_efficiency: Optional[float]
    reference_temperature: Optional[float]
    thermal_coefficient: Optional[float]
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

        if "pv_unit" in solar_inputs:
            pv_unit: float = solar_inputs["pv_unit"]
            pv_unit_overrided: bool = True
            logger.info(
                "`pv_unit` variable specified, using a pv unit of %s kWp", pv_unit
            )
        else:
            pv_unit = DEFAULT_PV_UNIT
            pv_unit_overrided = False
            logger.info("No `pv_unit` keyword specified, defaulting to %s kWp", pv_unit)

        return cls(
            solar_inputs["azimuthal_orientation"],
            solar_inputs["lifetime"],
            solar_inputs["name"],
            pv_unit,
            pv_unit_overrided,
            solar_inputs["reference_efficiency"]
            if "reference_efficiency" in solar_inputs
            else None,
            solar_inputs["reference_temperature"]
            if "reference_temperature" in solar_inputs
            else None,
            solar_inputs["thermal_coefficient"]
            if "thermal_coefficient" in solar_inputs
            else None,
            solar_inputs["tilt"],
        )


class HybridPVTPanel(SolarPanel, panel_type=SolarPanelType.PV_T):
    """
    Represents a PV-T panel.

    .. attribute:: max_mass_flow_rate
        The maximum mass-flow rate of heat-transfer fluid through the PV-T collector.

    .. attribute:: min_mass_flow_rate
        The minimum mass-flow rate of heat-transfer fluid through the PV-T collector.

    .. attribute:: thermal_unit
        The unit of thermal panel that the panel can output which is being considered,
        measured in kWth.

    """

    def __init__(
        self,
        logger: Logger,
        solar_inputs: Dict[str, Any],
        solar_panels: List[SolarPanel],
    ) -> None:
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

        if pv_layer.reference_efficiency is None:
            logger.error("PV reference efficiency must be defined if using PV-T.")
            raise InputFileError(
                "solar generation inputs",
                "PV reference efficiency must be defined if using PV-T",
            )
        if pv_layer.reference_temperature is None:
            logger.error("PV reference temperature must be defined if using PV-T.")
            raise InputFileError(
                "solar generation inputs",
                "PV reference temperature must be defined if using PV-T",
            )
        if pv_layer.thermal_coefficient is None:
            logger.error("PV thermal coefficient must be defined if using PV-T.")
            raise InputFileError(
                "solar generation inputs",
                "PV thermal coefficient must be defined if using PV-T",
            )

        if "pv_unit" not in solar_inputs:
            logger.error("PV unit size must be specified for PV-T panels.")
            raise InputFileError(
                "solar generation inputs",
                "PV unit size must be specified when considering PV-T panels.",
            )

        super().__init__(
            solar_inputs["azimuthal_orientation"],
            solar_inputs["lifetime"],
            solar_inputs["name"],
            solar_inputs["pv_unit"],
            True,
            pv_layer.reference_efficiency,
            pv_layer.reference_temperature,
            pv_layer.thermal_coefficient,
            solar_inputs["tilt"],
        )

        self.max_mass_flow_rate = solar_inputs["max_mass_flow_rate"]
        self.min_mass_flow_rate = solar_inputs["min_mass_flow_rate"]
        self.thermal_unit = solar_inputs["thermal_unit"]

    def __repr__(self) -> str:
        """
        Return a nice-looking representation of the panel.

        Outputs:
            - A nice-looking representation of the panel.

        """

        return (
            "HybridPVTPanel("
            + f"azimuthal_orientation={self.azimuthal_orientation}"
            + f", lifetime={self.lifetime}"
            + f", max_mass_flow_rate={self.max_mass_flow_rate}"
            + f", min_mass_flow_rate={self.min_mass_flow_rate}"
            + f", name={self.name}"
            + f", pv_unit={self.pv_unit}"
            + f", reference_efficiency={self.reference_efficiency}"
            + f", reference_temperature={self.reference_temperature}"
            + f", thermal_coefficient={self.thermal_coefficient}"
            + f", thermal_unit={self.thermal_unit}"
            + f", tilt={self.tilt}"
            + ")"
        )

    def fractional_performance(
        self,
        ambient_temperature: float,
        collector_input_temperature: float,
        irradiance: float,
        mass_flow_rate: float,
        wind_speed: float,
    ) -> Tuple[float, float]:
        """
        Computes the fractional performance of the :class:`HybridPVTPanel`.

        Additional Credits:
            The PV-T collector model used here was developed in-house by
            Benedict Winchester, benedict.winchester@gmail.com

        Inputs:
            - ambient_temperature:
                The ambient temperature surrounding the collector, measured in degrees
                Celcius.
            - collector_input_temperature:
                The input temperature of HTF entering the collector, measured in degrees
                Celcius.
            - irradiance:
                The total irradiance incident on the collector, both direct and diffuse,
                measured in W/m^2.
            - mass_flow_rate:
                The mass flow rate through the collector, measured in litres per hour.
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
        # collector_temperature = ambient_temperature + 0.035 * irradiance

        if self.thermal_coefficient is None:
            raise InputFileError(
                "solar generation inputs",
                "A thermal coefficient must be defined when specifying PV-T instances. "
                "This needs to be specified on the appropriate PV layer.",
            )
        if self.reference_temperature is None:
            raise InputFileError(
                "solar generation inputs",
                "A reference temperature must be defined when specifying PV-T "
                "instances. This needs to be specified on the appropriate PV layer.",
            )

        # Compute the thermal efficiency of the collector.
        collector_output_temperature = (
            29.741604978319252  # a_0
            - 18.591187817656692 * np.log(irradiance)  # a_1
            + 2.7665886796936974 * (np.log(irradiance)) ** 2  # a_2
            + 21.26326604925854 * np.log(mass_flow_rate)  # a_3
            + 2.369750239298799 * (np.log(mass_flow_rate)) ** 2  # a_4
            - 5.682352509862814 * np.log(mass_flow_rate) * np.log(irradiance)  # a_5
            + ambient_temperature
            * (
                -0.44273532578369784  # a_6
                + 0.2028008441771341 * np.log(irradiance)  # a_7
                - 0.011119875548502111 * (np.log(irradiance)) ** 2  # a_8
                + 0.055071111041432544 * np.log(mass_flow_rate)  # a_9
                + 0.08158562860833476 * (np.log(mass_flow_rate)) ** 2  # a_10
                - 0.06020468104160886
                * np.log(mass_flow_rate)
                * np.log(irradiance)  # a_11
            )
            + wind_speed ** 0.16
            * (
                -5.781350419589919  # a_12
                + 2.1957501679949383 * np.log(irradiance)  # a_13
                - 0.29053071799402297 * (np.log(irradiance)) ** 2  # a_14
                - 1.8642000928076754 * np.log(mass_flow_rate)  # a_15
                - 0.2168704193965011 * (np.log(mass_flow_rate)) ** 2  # a_16
                + 0.6040946267503874
                * np.log(mass_flow_rate)
                * np.log(irradiance)  # a_17
            )
            + ambient_temperature
            * wind_speed ** 0.16
            * (
                0.3503231839458856  # a_18
                - 0.09602338634428392 * np.log(irradiance)  # a_19
                + 0.007427401892109994 * (np.log(irradiance)) ** 2  # a_20
                - 0.0376976418177416 * np.log(mass_flow_rate)  # a_21
                - 0.0069869817616982095 * (np.log(mass_flow_rate)) ** 2  # a_22
                + 0.005502093603775405
                * np.log(mass_flow_rate)
                * np.log(irradiance)  # a_23
            )
            + collector_input_temperature
            * (
                0.5260015449448561  # a_24
                + 0.008404945236477125 * np.log(irradiance)  # a_25
                - 0.0009232365144613755 * (np.log(irradiance)) ** 2  # a_26
                + 0.29551049432336596 * np.log(mass_flow_rate)  # a_27
                - 0.06977464822399262 * (np.log(mass_flow_rate)) ** 2  # a_28
                + 0.0054089335282716255
                * np.log(mass_flow_rate)
                * np.log(irradiance)  # a_29
            )
        )

        # Compute the fractional electrical performance of the collector.
        electrical_efficiency = (
            0.11639738048249704  # a_0
            + 0.013316120967158817 * np.log(irradiance)  # a_1
            - 0.0017275968821738896 * (np.log(irradiance)) ** 2  # a_2
            - 0.007118345534937452 * np.log(mass_flow_rate)  # a_3
            - 0.0009603753775774027 * (np.log(mass_flow_rate)) ** 2  # a_4
            + 0.001963935108755282 * np.log(mass_flow_rate) * np.log(irradiance)  # a_5
            + ambient_temperature
            * (
                0.00013088241772800534  # a_6
                - 8.21290503977136e-05 * np.log(irradiance)  # a_7
                + 4.953260935491807e-06 * (np.log(irradiance)) ** 2  # a_8
                - 2.4716212339190652e-05 * np.log(mass_flow_rate)  # a_9
                - 3.254925000717009e-05 * (np.log(mass_flow_rate)) ** 2  # a_10
                + 2.2966026636676483e-05
                * np.log(mass_flow_rate)
                * np.log(irradiance)  # a_11
            )
            + wind_speed ** 0.16
            * (
                0.0039941028007474885  # a_12
                - 0.0013675551372885565 * np.log(irradiance)  # a_13
                + 0.00016088723949178542 * (np.log(irradiance)) ** 2  # a_14
                + 0.0005934066665735958 * np.log(mass_flow_rate)  # a_15
                + 0.00011959274164597139 * (np.log(mass_flow_rate)) ** 2  # a_16
                - 0.00021214131631117
                * np.log(mass_flow_rate)
                * np.log(irradiance)  # a_17
            )
            + ambient_temperature
            * wind_speed ** 0.16
            * (
                -0.00018182934054386044  # a_18
                + 5.080180915525177e-05 * np.log(irradiance)  # a_19
                - 4.0790614401728095e-06 * (np.log(irradiance)) ** 2  # a_20
                + 1.5313147039884785e-05 * np.log(mass_flow_rate)  # a_21
                + 1.4287639500124582e-06 * (np.log(mass_flow_rate)) ** 2  # a_22
                - 2.007075139853903e-06
                * np.log(mass_flow_rate)
                * np.log(irradiance)  # a_23
            )
            + collector_input_temperature
            * (
                -0.0004418125413464358  # a_24
                + 3.6827017656719075e-06 * np.log(irradiance)  # a_25
                - 6.512317845834291e-07 * (np.log(irradiance)) ** 2  # a_26
                - 0.00011076377100134386 * np.log(mass_flow_rate)  # a_27
                + 2.8315159160794437e-05 * (np.log(mass_flow_rate)) ** 2  # a_28
                - 1.5880243199525098e-06
                * np.log(mass_flow_rate)
                * np.log(irradiance)  # a_29
            )
        )

        fractional_electrical_performance = (
            electrical_efficiency / self.reference_efficiency
        ) * (irradiance / 1000)

        # Return this, along with the output temperature of HTF leaving the collector.
        return collector_output_temperature, fractional_electrical_performance


def solar_degradation(lifetime: int) -> pd.DataFrame:
    """
    Calculates the solar degredation.

    Inputs:
        - lifetime:
            The lifetime of the solar setup in years.

    Outputs:
        - The lifetime degredation of the solar setup.

    """

    # lifetime = self.input_data.loc["lifetime"]
    hourly_degradation = 0.20 / (lifetime * 365 * 24)
    lifetime_degradation = []

    for i in range((20 * 365 * 24) + 1):
        equiv = 1.0 - i * hourly_degradation
        lifetime_degradation.append(equiv)

    return pd.DataFrame(lifetime_degradation)


class SolarDataThread(
    BaseRenewablesNinjaThread, profile_name="solar", profile_key="pv"
):
    """
    Class to use when calling the solar data thread.

    """

    def __init__(
        self,
        auto_generated_files_directory: str,
        generation_inputs: Dict[str, Any],
        location: Location,
        logger_name: str,
        regenerate: bool,
        pv_panel: PVPanel,
        sleep_multiplier: int = 1,
    ):
        """
        Instantiate a :class:`SolarDataThread` instance.

        """

        # Add the additional parameters which are need when calling the solar data.
        renewables_ninja_params = {
            "dataset": "merra2",
            "lat": float(location.latitude),
            "lon": float(location.longitude),
            "local_time": "false",
            "capacity": 1.0,
            "system_loss": 0,
            "tracking": 0,
            "tilt": pv_panel.tilt,
            "azim": pv_panel.azimuthal_orientation,
            "raw": "true",
        }
        super().__init__(
            auto_generated_files_directory,
            generation_inputs,
            location,
            logger_name,
            regenerate,
            sleep_multiplier,
            renewables_ninja_params=renewables_ninja_params,
        )


def total_solar_output(*args, **kwargs) -> pd.DataFrame:
    """
    Wrapper function to wrap the total solar output.

    """

    return total_profile_output(*args, **kwargs, profile_name="solar")
