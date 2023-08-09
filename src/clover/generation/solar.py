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

import enum

from logging import Logger
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd  # pylint: disable=import-error

# from sklearn.linear_model._coordinate_descent import Lasso

from ..__utils__ import (
    BColours,
    InputFileError,
    Location,
    NAME,
    ProgrammerJudgementFault,
    RenewablesNinjaError,
)
from .__utils__ import BaseRenewablesNinjaThread, SolarDataType, total_profile_output

__all__ = (
    "get_profile_prefix",
    "HybridPVTPanel",
    "PVPanel",
    "SolarDataThread",
    "SolarDataType",
    "SolarPanelType",
    "solar_degradation",
    "SOLAR_LOGGER_NAME",
    "total_solar_output",
)


# Default PV unit:
#   The default PV unit size to use, measured in kWp.
DEFAULT_PV_UNIT: float = 1  # [kWp]

# Default tracking:
#   The default keyword to use for fixed-mounted panels.
_DEFAULT_TRACKING: str = "fixed"

# Reference solar irradiance:
#   The reference solar irradiance, used to compute fractional PV-T electric
#   performance values.
REFERENCE_SOLAR_IRRADIANCE: float = 1000  # [W/m^2]

# Solar logger name:
#   The name to use for the solar logger.
SOLAR_LOGGER_NAME = "solar_generation"

# Tracking map:
#   Map used for determining the tracking state of the panels.
_TRACKING_MAP: Dict[str, int] = {
    _DEFAULT_TRACKING: 0,
    "single": 1,
    "single_axis": 1,
    "azimuthal": 1,
    "dual": 2,
    "dual_axis": 2,
}


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


class Tracking(enum.Enum):
    """
    Specifies the tracking state of the panel being considered.

    - FIXED:
        Denotes that the panel is fixed in both its azimuthal orientation and tilt.
    - SINGLE_AXIS:
        Denotes that the panel is single-axis tracking, i.e., has a fixed tilt but its
        azimuthal orietntation can change.
    - DUAL_AXIS:
        Denotes that the panel is dual-axis tracking, i.e., both its azimuthal
        orientation and tilt can change.

    """

    FIXED: int = 0
    SINGLE_AXIS: int = 1
    DUAL_AXIS: int = 2

    @classmethod
    def from_text(cls, logger: Logger, text: str) -> Any:
        """
        Used to instntiate the :class:`Tracking` instance based on the input text.

        Inputs:
            - text:
                The text describing the tracking from the input file.

        """

        try:
            return cls(_TRACKING_MAP[text])
        except KeyError as err:
            logger.error(
                "Input value of %s for tracking type is not valid. Valid tracking modes: %s",
                text,
                ", ".join([f"'{key}'" for key in _TRACKING_MAP]),
            )
            raise InputFileError(
                "solar_generation_inputs", f"Tracking mode '{text}' is not valid."
            ) from err

    @property
    def as_string(self) -> str:
        """
        Return a string representing the class.

        :return:
            A `str` containing the tracking information.

        """

        if self.value == 0:
            return "fixed"
        if self.value == 1:
            return "single_axis"
        return "dual_axis"


class SolarPanel:  # pylint: disable=too-few-public-methods
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

    panel_type: SolarPanelType

    def __init__(
        self,
        azimuthal_orientation: Optional[float],
        lifetime: int,
        name: str,
        pv_unit: float,
        pv_unit_overrided: bool,
        reference_efficiency: Optional[float],
        reference_temperature: Optional[float],
        thermal_coefficient: Optional[float],
        tilt: Optional[float],
    ) -> None:
        """
        Instantiate a :class:`SolarPanel` instance.

        Inputs:
            - azimuthal_orientation:
                The azimuthal orientation of the :class:`SolarPanel`.
            - lifetime:
                The lifetime of the :class:`SolarPanel` in years.
            - name:
                The name to assign to the :class:`SolarPanel` in order to uniquely
                identify it.
            - pv_unit:
                The output power, in Watts, of the PV layer of the panel per unit panel
                installed.
            - pv_unit_overrided:
                Whether this unit has been overrided from its default value (True) or
                not (False).
            - reference_efficiency:
                The reference efficiency of the panel, if required, otherwise `None`.
            - reference_temperature:
                The temperature, in degrees Celcius, at which the reference efficiency
                is defined, if required, otherwise `None`.
            - thermal_coefficient:
                The thermal coefficient of the PV layer of the panel, if required,
                otherwise `None`.
            - tilt:
                The tilt of the panel in degrees above the horizontal.

        """

        self.azimuthal_orientation: Optional[float] = azimuthal_orientation
        self.lifetime: int = lifetime
        self.name: str = name
        self.pv_unit: float = pv_unit
        self.pv_unit_overrided: bool = pv_unit_overrided
        self.reference_efficiency: Optional[float] = reference_efficiency
        self.reference_temperature: Optional[float] = reference_temperature
        self.thermal_coefficient: Optional[float] = thermal_coefficient
        self.tilt: Optional[float] = tilt

    def __init_subclass__(cls, panel_type: SolarPanelType) -> None:
        """
        The init_subclass hook, run on instantiation of the :class:`SolarPanel`.

        Inputs:
            - panel_type:
                The type of panel being considered.

        Outputs:
            An instantiated :class:`SolarPanel` instance.

        """

        cls.panel_type = panel_type

        return super().__init_subclass__()


class PVPanel(
    SolarPanel, panel_type=SolarPanelType.PV
):  # pylint: disable=too-few-public-methods
    """
    Represents a photovoltaic panel.

    .. attribute:: tracking
        Whether the panel is tracking or not.

    """

    def __init__(
        self,
        azimuthal_orientation: Optional[float],
        lifetime: int,
        name: str,
        pv_unit: float,
        pv_unit_overrided: bool,
        reference_efficiency: Optional[float],
        reference_temperature: Optional[float],
        thermal_coefficient: Optional[float],
        tilt: Optional[float],
        tracking: Tracking,
    ) -> None:
        """
        Instantiate a :class:`PVPanel` instance.

        Inputs:
            - azimuthal_orientation:
                The azimuthal orientation of the :class:`PVPanel` or `None` if the panel
                is either single- or dual-axis tracking.
            - lifetime:
                The lifetime of the :class:`PVPanel` in years.
            - name:
                The name to assign to the :class:`PVPanel` in order to uniquely
                identify it.
            - pv_unit:
                The output power, in Watts, of the PV layer of the panel per unit panel
                installed.
            - pv_unit_overrided:
                Whether this unit has been overrided from its default value (True) or
                not (False).
            - reference_efficiency:
                The reference efficiency of the panel, if required, otherwise `None`.
            - reference_temperature:
                The temperature, in degrees Celcius, at which the reference efficiency
                is defined, if required, otherwise `None`.
            - thermal_coefficient:
                The thermal coefficient of the PV layer of the panel, if required,
                otherwise `None`.
            - tilt:
                The tilt of the panel in degrees above the horizontal, if specified, or
                `None` if the panel is dual-axis tracking..
            - tracking:
                The state of the panel's tracking.

        """

        self.tracking = tracking

        super().__init__(
            azimuthal_orientation,
            lifetime,
            name,
            pv_unit,
            pv_unit_overrided,
            reference_efficiency,
            reference_temperature,
            thermal_coefficient,
            tilt,
        )

    def __hash__(self) -> int:
        """
        Return a unique identifier for the panel.

        Because the solar panel instances are used for fetching weather data, panels
        with unique tilt, azimuthal orientation, and tracking, need to be kept separate.

        These parameters are hence used to determine the "unique" hash for the panel.

        """

        return hash(
            self.tracking.value
            + 3
            * (
                self.azimuthal_orientation
                if self.azimuthal_orientation is not None
                else 0
            )
            + 540 * (self.tilt if self.tilt is not None else 0)
        )

    def __eq__(self, other: Any) -> bool:
        """Used to determine whether to instances are identical for creating a set."""

        return (  # type: ignore[no-any-return]
            self.tracking == other.tracking
            and self.azimuthal_orientation == other.azimuthal_orientation
            and self.tilt == other.tilt
        )

    @property
    def as_dict(self) -> Dict[str, Any]:
        """
        Return a dictionary based on the panel information.

        Outputs:
            - A mapping containing the input information based on the panel.

        """

        return {
            "azimuthal_orientation": self.azimuthal_orientation,
            "lifetime": self.lifetime,
            "name": self.name,
            "pv_unit": self.pv_unit,
            "pv_unit_overrided": self.pv_unit_overrided,
            "reference_efficiency": self.reference_efficiency,
            "reference_temperature": self.reference_temperature,
            "thermal_coefficient": self.thermal_coefficient,
            "tilt": self.tilt,
            "tracking": self.tracking.as_string,
            "type": self.panel_type.value,
        }

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

        tracking: Tracking = Tracking.from_text(
            logger, solar_inputs.get("tracking", _DEFAULT_TRACKING)
        )

        if tracking == Tracking.FIXED:
            azimuthal_orientation: Optional[float] = solar_inputs[
                "azimuthal_orientation"
            ]
        else:
            azimuthal_orientation = None

        if tracking != Tracking.DUAL_AXIS:
            tilt: Optional[float] = solar_inputs["tilt"]
        else:
            tilt = None

        return cls(
            azimuthal_orientation,
            solar_inputs["lifetime"],
            solar_inputs[NAME],
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
            tilt,
            tracking,
        )


class HybridPVTPanel(SolarPanel, panel_type=SolarPanelType.PV_T):
    """
    Represents a PV-T panel.

    .. attribute:: electric_model
        The model of the electric performance of the collector.

    .. attribute:: max_mass_flow_rate
        The maximum mass-flow rate of heat-transfer fluid through the PV-T collector,
        measured in litres per hour.

    .. attribute:: min_mass_flow_rate
        The minimum mass-flow rate of heat-transfer fluid through the PV-T collector,
        measured in litres per hour.

    .. attribute:: thermal_model
        The model of the thermal performance of the collector.

    .. attribute:: thermal_unit
        The unit of thermal panel that the panel can output which is being considered,
        measured in kWth.

    """

    def __init__(
        self,
        electric_model: Optional[Any],
        logger: Logger,
        solar_inputs: Dict[str, Any],
        solar_panels: List[SolarPanel],
        thermal_model: Optional[Any],
    ) -> None:
        """
        Instantiate a :class:`HybridPVTPanel` instance based on the input data.

        Inputs:
            - electric_model:
                The reduced electrical-efficiency model to use when generating the
                electric properties of the collector.
            - logger:
                The logger to use for the run.
            - solar_inputs:
                The solar input data specific to this panel.
            - solar_panels:
                The full set of solar generation data.
            - thermal_model:
                The reduced thermal model to use when generating the thermal properties
                of the collector.

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
                solar_inputs[NAME],
            )
            raise InputFileError(
                "solar generation inputs",
                f"PV-layer data for layer {solar_inputs['pv']} could not be found "
                + f"whilst processing PV-T panel {solar_inputs[NAME]}.",
            ) from None

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
            solar_inputs[NAME],
            solar_inputs["pv_unit"],
            True,
            pv_layer.reference_efficiency,
            pv_layer.reference_temperature,
            pv_layer.thermal_coefficient,
            solar_inputs["tilt"],
        )

        self.electric_model = electric_model
        self.max_mass_flow_rate = solar_inputs["max_mass_flow_rate"]
        self.min_mass_flow_rate = solar_inputs["min_mass_flow_rate"]
        self.thermal_model = thermal_model
        self.thermal_unit = solar_inputs.get("thermal_unit", None)

    def __repr__(self) -> str:
        """
        Return a nice-looking representation of the panel.

        Outputs:
            - A nice-looking representation of the panel.

        """

        return (
            "HybridPVTPanel("
            + f"azimuthal_orientation={self.azimuthal_orientation}"
            + f", electric_model={self.electric_model}"
            + f", lifetime={self.lifetime}"
            + f", max_mass_flow_rate={self.max_mass_flow_rate}"
            + f", min_mass_flow_rate={self.min_mass_flow_rate}"
            + f", name={self.name}"
            + f", pv_unit={self.pv_unit}"
            + f", reference_efficiency={self.reference_efficiency}"
            + f", reference_temperature={self.reference_temperature}"
            + f", thermal_coefficient={self.thermal_coefficient}"
            + f", thermal_model={self.thermal_model}"
            + f", thermal_unit={self.thermal_unit}"
            + f", tilt={self.tilt}"
            + ")"
        )

    def __hash__(self) -> int:
        """
        Return a unique identifier for the panel.

        Because the solar panel instances are used for fetching weather data, panels
        with unique tilt, azimuthal orientation, and tracking, need to be kept separate.

        These parameters are hence used to determine the "unique" hash for the panel.

        """

        return hash(
            3
            * (
                self.azimuthal_orientation
                if self.azimuthal_orientation is not None
                else 0
            )
            + 540 * (self.tilt if self.tilt is not None else 0)
        )

    def __eq__(self, other: Any) -> bool:
        """Used to determine whether to instances are identical for creating a set."""

        return (  # type: ignore[no-any-return]
            self.azimuthal_orientation == other.azimuthal_orientation
            and self.tilt == other.tilt
        )

    def calculate_performance(
        self,
        ambient_temperature: float,
        input_temperature: float,
        logger: Logger,
        mass_flow_rate: float,
        solar_irradiance: float,
        wind_speed: float,
    ) -> Tuple[float, float]:
        """
        Calculates the performance characteristics of the hybrid PV-T collector.

        The technical PV-T model developed by Benedict Winchester is reduced to a
        smaller, quick-to-run model which is loaded and utilised here.

        Inputs:
            - ambient_temperature:
                The ambient temperature, measured in degrees Celcius.
            - input_temperature:
                The input temperature of the HTF entering the PV-T collector, measured
                in degrees Celcius.
            - logger:
                The :class:`logging.Logger` to use for the run.
            - mass_flow_rate:
                The mass-flow rate of HTF passing through the collector, measured in
                kilograms per second.
            - solar_irradiance:
                The solar irradiance incident on the surface of the collector, measured
                in Watts per meter squared.
            - wind_speed:
                The wind speed at the collector, measured in meters per second.

        Outputs:
            - fractional_electric_performance:
                The fractional electric performance defined between 0 (panel is not
                operating, i.e., no output) and 1 (panel is operating at full test
                potential of reference efficiency under reference irradiance).
            - output_temperature:
                The temperature of the HTF leaving the collector, measured in degrees
                Celcius.

        """

        if self.electric_model is None or self.thermal_model is None:
            logger.error(
                "%sThe PV-T instance does not have well-defined and loaded models.%s",
                BColours.fail,
                BColours.endc,
            )
            raise ProgrammerJudgementFault(
                "pv-t modelling",
                "The PV-T instance does not have well-defined and loaded models. This "
                "could be due to the files being incorrectly parsed, mishandled, or "
                "dropped inadvertently due to internal code flow.",
            )
        if self.reference_efficiency is None:
            logger.error(
                "%sThe PV-T output function was called without a reference efficiency "
                "being defined for the PV-T panel being considered.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "solar generation inputs",
                "A reference efficiency must be defined for PV-T panels.",
            )

        input_data_frame = pd.DataFrame(
            [
                [
                    ambient_temperature,
                    input_temperature,
                    mass_flow_rate,
                    solar_irradiance,
                    wind_speed,
                ]
            ]
        )

        try:
            electric_efficiency = float(self.electric_model.predict(input_data_frame))
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "Error attempting to predict electric efficiency of the PV-T collector: %s",
                str(e),
            )
            raise

        # Convert the efficiency to a fractional performance.
        fractional_electric_performance: float = (
            electric_efficiency / self.reference_efficiency
        ) * (solar_irradiance / REFERENCE_SOLAR_IRRADIANCE)

        try:
            output_temperature = float(self.thermal_model.predict(input_data_frame))
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "Error attempting to predict electric efficiency of the PV-T collector: %s",
                str(e),
            )
            raise

        return fractional_electric_performance, output_temperature


def get_profile_prefix(panel: Union[PVPanel, HybridPVTPanel]) -> str:
    """
    Determine the prefix to use for profile names based on the tracking and angles.

    Inputs:
        - panel:
            The :class:`PVPanel` to determine the profile prefix for.

    """

    if isinstance(panel, HybridPVTPanel):
        tracking = Tracking.DUAL_AXIS
    else:
        tracking = panel.tracking

    if tracking == Tracking.SINGLE_AXIS:
        return f"single_axis_tilt_{panel.tilt}_"
    if tracking == Tracking.DUAL_AXIS:
        return "dual_axis_"
    if tracking == Tracking.FIXED:
        return f"fixed_tilt_{panel.tilt}_azim_{panel.azimuthal_orientation}_"

    raise ProgrammerJudgementFault(
        "generation.solar::get_profile_prefix",
        f"Code not written for switch for tracking value {tracking.value}",
    )


def solar_degradation(lifetime: int, num_years: int) -> pd.DataFrame:
    """
    Calculates the solar degredation.

    Inputs:
        - lifetime:
            The lifetime of the solar setup in years.
        - num_years:
            The number of years for which the simulation is being carried out.

    Outputs:
        - The lifetime degredation of the solar setup.

    """

    # lifetime = self.input_data.iloc["lifetime"]
    hourly_degradation = 0.20 / (lifetime * 365 * 24)
    lifetime_degradation = []

    for i in range((num_years * 365 * 24) + 1):
        equiv = 1.0 - i * hourly_degradation
        lifetime_degradation.append(equiv)

    return pd.DataFrame(lifetime_degradation)


class SolarDataThread(
    BaseRenewablesNinjaThread, profile_name="solar", profile_key="pv"
):
    """
    Class to use when calling the solar data thread.

    Options which are not immediately obvious are documented here:
    - tracking:
        Used for specifying whether the panels are tracking. Available options:
        - 0 -> The panels do not track the sun;
        - 1 -> The panels are single-axis tracking, i.e., track azimuthally but have a
            fixed tilt angle;
        - 2 -> The panels are dual-axis tracking, i.e., track both azimuthally and with
            their tilt.

    """

    def __init__(
        self,
        auto_generated_files_directory: str,
        global_settings_inputs: Dict[str, str],
        location: Location,
        logger_name: str,
        pause_time: int,
        regenerate: bool,
        pv_panel: PVPanel,
        sleep_multiplier: int = 1,
        verbose: bool = False,
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
            "tracking": pv_panel.tracking.value,
            "raw": "true",
        }

        renewables_ninja_params["azim"] = (
            pv_panel.azimuthal_orientation
            if pv_panel.azimuthal_orientation is not None
            else "false"
        )
        renewables_ninja_params["tilt"] = (
            pv_panel.tilt if pv_panel.tilt is not None else "false"
        )

        # Determine the prefix to use for the solar profiles dependent on tracking.
        profile_prefix = get_profile_prefix(pv_panel)

        super().__init__(
            auto_generated_files_directory,
            global_settings_inputs,
            location,
            logger_name,
            pause_time,
            regenerate,
            sleep_multiplier,
            verbose,
            renewables_ninja_params=renewables_ninja_params,
            profile_prefix=profile_prefix,
        )


def total_solar_output(
    *args, pv_panel: Union[PVPanel, HybridPVTPanel]
) -> pd.DataFrame:  # type: ignore
    """
    Wrapper function to wrap the total solar output.

    """

    try:
        return total_profile_output(
            *args,
            profile_name="solar",
            profile_prefix=get_profile_prefix(pv_panel),
        )
    except FileNotFoundError:
        raise RenewablesNinjaError() from None
