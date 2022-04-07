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

from argparse import Namespace
import dataclasses
from logging import Logger

from typing import Any, Dict, List, Optional, Union

from ..__utils__ import (
    AuxiliaryHeaterType,
    BColours,
    CleanWaterMode,
    EXCHANGER,
    InputFileError,
    NAME,
    RESOURCE_NAME_TO_RESOURCE_TYPE_MAPPING,
    OperatingMode,
    ResourceType,
    Scenario,
)

from ..conversion.conversion import Converter
from ..generation.solar import HybridPVTPanel, PVPanel
from .diesel import DieselGenerator, DieselWaterHeater
from .exchanger import Exchanger
from .storage_utils import Battery, CleanWaterTank, HotWaterTank
from .transmission import Transmitter

__all__ = (
    "check_scenario",
    "determine_available_converters",
    "Minigrid",
)

# AC-to-AC:
#   Keyword used for parsing ac-to-ac conversion parameters.
AC_TO_AC: str = "ac_to_ac"

# AC-to-DC:
#   Keyword used for parsing ac-to-dc conversion parameters.
AC_TO_DC: str = "ac_to_dc"

# Conversion:
#   Keyword used for parsing grid AC-DC conversion parameters.
CONVERSION: str = "conversion"

# DC-to-AC:
#   Keyword used for parsing dc-to-ac conversion parameters.
DC_TO_AC: str = "dc_to_ac"

# DC-to-DC:
#   Keyword used for parsing dc-to-dc conversion parameters.
DC_TO_DC: str = "dc_to_dc"

# Resource Type:
#   Used for parsing resource-type information.
RESOURCE_TYPE: str = "resource_type"


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

    .. attribute:: buffer_tank
        The buffer tank being modelled, if applicable. This tank contains the buffer
        solution, be it HTF or feedwater, which is heated by PV-T before being fed into
        the desalination plant.

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

    .. attribute:: diesel_water_heater
        The diesel water heater associated with the minigrid system.

    .. attribute:: electric_water_heater
        The electric water heater associated with the minigrid system.

    .. attribute:: heat_exchanger
        The heat exchanger associated with the minigrid system.

    .. attribute:: hot_water_tank
        The hot-water tank being modelled, if applicable.

    .. attribute:: pv_panel
        The PV panel being considered.

    .. attribute:: pvt_panel
        The PV-T panel being considered, if applicable.

    .. attribute:: water_pump
        The water pump associated with the energy system, as a :class:`Transmitter`
        instance.

    """

    ac_to_ac_conversion_efficiency: Optional[float]
    ac_to_dc_conversion_efficiency: Optional[float]
    ac_transmission_efficiency: Optional[float]
    battery: Optional[Battery]
    buffer_tank: Optional[HotWaterTank]
    clean_water_tank: Optional[CleanWaterTank]
    dc_to_ac_conversion_efficiency: Optional[float]
    dc_to_dc_conversion_efficiency: Optional[float]
    dc_transmission_efficiency: Optional[float]
    diesel_generator: Optional[DieselGenerator]
    diesel_water_heater: Optional[DieselWaterHeater]
    electric_water_heater: Optional[Converter]
    heat_exchanger: Optional[Exchanger]
    hot_water_tank: Optional[HotWaterTank]
    pv_panel: PVPanel
    pvt_panel: Optional[HybridPVTPanel]
    water_pump: Optional[Transmitter]

    @classmethod
    def from_dict(  # pylint: disable=too-many-locals
        cls,
        diesel_generator: DieselGenerator,
        diesel_water_heater: Optional[DieselWaterHeater],
        electric_water_heater: Optional[Converter],
        minigrid_inputs: Dict[str, Any],
        pv_panel: PVPanel,
        pvt_panel: Optional[HybridPVTPanel],
        battery_inputs: Optional[List[Dict[str, Any]]] = None,
        exchanger_inputs: Optional[List[Dict[str, Any]]] = None,
        tank_inputs: Optional[List[Dict[str, Any]]] = None,
        water_pump: Optional[Transmitter] = None,
    ) -> Any:
        """
        Returns a :class:`Minigrid` instance based on the inputs provided.

        Inputs:
            - diesel_generator:
                The diesel backup generator to use for the run.
            - diesel_water_heater:
                The diesel water heater associated with the minigrid system, if
                appropriate.
            - electric_water_heater:
                The electric water heater associated with the minigrid system, if
                appropriate.
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
            - water_pump:
                The :class`Transmitter` corresponding to the water pump associated with
                the system.

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
                        ) from None
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
                        ) from None
                else:
                    raise InputFileError(
                        "tank inputs",
                        f"The tank '{entry['name']}' uses an unknown resource type: "
                        + f"{entry[RESOURCE_TYPE]}",
                    )
        else:
            tanks = {}

        # Determine the various tanks being considered.
        if "buffer_tank" in minigrid_inputs:
            buffer_tank: Optional[Union[CleanWaterTank, HotWaterTank]] = tanks[
                minigrid_inputs["buffer_tank"]
            ]
            if not isinstance(buffer_tank, HotWaterTank):
                raise InputFileError(
                    "energy system inputs",
                    "The buffer tank selected must be a hot-water tank.",
                )
        else:
            buffer_tank = None

        if "clean_water_tank" in minigrid_inputs:
            clean_water_tank: Optional[Union[CleanWaterTank, HotWaterTank]] = tanks[
                minigrid_inputs["clean_water_tank"]
            ]
            if not isinstance(clean_water_tank, CleanWaterTank):
                raise InputFileError(
                    "energy system inputs",
                    "The clean-water tank selected must be a clean-water tank.",
                )
        else:
            clean_water_tank = None

        if "hot_water_tank" in minigrid_inputs:
            hot_water_tank: Optional[Union[CleanWaterTank, HotWaterTank]] = tanks[
                minigrid_inputs["hot_water_tank"]
            ]
            if not isinstance(hot_water_tank, HotWaterTank):
                raise InputFileError(
                    "energy system inputs",
                    "The hot-water tank selected must be a hot-water tank.",
                )
        else:
            hot_water_tank = None

        # Return the minigrid instance.
        return cls(
            minigrid_inputs[CONVERSION][AC_TO_AC]
            if AC_TO_AC in minigrid_inputs[CONVERSION]
            else None,
            minigrid_inputs[CONVERSION][AC_TO_DC]
            if AC_TO_DC in minigrid_inputs[CONVERSION]
            else None,
            minigrid_inputs["ac_transmission_efficiency"]
            if "ac_transmission_efficiency" in minigrid_inputs
            else None,
            batteries[minigrid_inputs["battery"]]
            if "battery" in minigrid_inputs
            else None,
            buffer_tank,
            clean_water_tank,
            minigrid_inputs[CONVERSION][DC_TO_AC]
            if DC_TO_AC in minigrid_inputs[CONVERSION]
            else None,
            minigrid_inputs[CONVERSION][DC_TO_DC]
            if DC_TO_DC in minigrid_inputs[CONVERSION]
            else None,
            minigrid_inputs["dc_transmission_efficiency"]
            if "dc_transmission_efficiency" in minigrid_inputs
            else None,
            diesel_generator,
            diesel_water_heater,
            electric_water_heater,
            exchangers[minigrid_inputs[EXCHANGER]]
            if EXCHANGER in minigrid_inputs
            else None,
            hot_water_tank,
            pv_panel,
            pvt_panel,
            water_pump,
        )


def check_scenario(
    logger: Logger,
    minigrid: Minigrid,
    operating_mode: OperatingMode,
    parsed_args: Namespace,
    scenario: Scenario,
) -> None:
    """
    Check that the scenario inputs match up correctly.

    Inputs:
        - logger:
            The logger to use for the run.
        - minigrid:
            The minigrid being simulated.
        - operating_mode:
            The operating mode being carried out.
        - parsed_args:
            The parsed command-line arguments.
        - scenario:
            The current scenario beign modelled.

    """

    if scenario.desalination_scenario is not None and minigrid.clean_water_tank is None:
        raise InputFileError(
            "energy system inputs",
            "No clean-water tank was provided despite there needing to be a tank "
            "specified for dealing with clean-water demands.",
        )

    if operating_mode == OperatingMode.SIMULATION:
        if (scenario.pv and parsed_args.pv_system_size is None) or (
            not scenario.pv and parsed_args.pv_system_size is not None
        ):
            raise InputFileError(
                "scenario",
                "PV mode in the scenario file must match the command-line usage.",
            )
        if (
            parsed_args.clean_water_pvt_system_size is not None
            and (scenario.desalination_scenario is None)
        ) or (
            parsed_args.clean_water_pvt_system_size is None
            and (
                scenario.desalination_scenario is not None
                and scenario.desalination_scenario.clean_water_scenario.mode
                == CleanWaterMode.THERMAL_ONLY
            )
        ):
            logger.error(
                "%sPV-T mode and available resources in the scenario file must match "
                "the command-line usage. Check the clean-water and PV-T scenario "
                "specification.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "scenario",
                "Mismatch between command-line usage and in-file usage.",
            )
        if (
            parsed_args.hot_water_pvt_system_size is not None
            and (scenario.hot_water_scenario is None)
        ) or (
            parsed_args.hot_water_pvt_system_size is None
            and (scenario.hot_water_scenario is not None)
        ):
            logger.error(
                "%sPV-T mode in the scenario file must match the command-line usage. "
                "Check the hot-water and PV-T scenario specification.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "scenario",
                "Mismatch between command-line usage and in-file usage.",
            )
        if (
            scenario.pv_t
            and scenario.desalination_scenario is None
            and scenario.hot_water_scenario is None
        ) or (
            not scenario.pv_t
            and scenario.desalination_scenario is not None
            and scenario.hot_water_scenario is not None
        ):
            logger.error(
                "%sDesalination or hot-water scenario usage does not match the "
                "system's PV-T panel inclusion.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "scenario",
                "The PV-T mode does not match the hot-water or desalination scenarios.",
            )
        if (scenario.battery and parsed_args.storage_size is None) or (
            not scenario.battery and parsed_args.storage_size is not None
        ):
            raise InputFileError(
                "scenario",
                "Battery mode in the scenario file must match the command-line usage.",
            )


def determine_available_converters(
    converters: Dict[str, Converter],
    logger: Logger,
    minigrid: Minigrid,
    scenario: Scenario,
) -> List[Converter]:
    """
    Determines the available :class:`Converter` instances based on the :class:`Scenario`

    Inputs:
        - converters:
            The :class:`Converter` instances defined, parsed from the conversion inputs
            file.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - minigrid:
            The :class:`Minigrid` to use for the run.
        - scenario:
            The :class:`Scenario` to use for the run.

    Outputs:
        - A `list` of :class:`Converter` instances available to the system.

    """

    available_converters: List[Converter] = []

    if scenario.desalination_scenario is None and scenario.hot_water_scenario is None:
        return available_converters

    # Determine the available converters from the scenarios file.
    if scenario.desalination_scenario is not None:
        # Process the clean-water converters.
        for entry in scenario.desalination_scenario.clean_water_scenario.sources:
            try:
                available_converters.append(converters[entry])
            except KeyError:
                logger.error(
                    "%sUnknown clean-water source specified in the scenario file: %s%s",
                    BColours.fail,
                    entry,
                    BColours.endc,
                )
                raise InputFileError(
                    "desalination scenario",
                    f"{BColours.fail}Unknown clean-water source(s) in the scenario "
                    + f"file: {entry}{BColours.endc}",
                ) from None

        # Process the feedwater sources.
        for entry in scenario.desalination_scenario.unclean_water_sources:
            try:
                available_converters.append(converters[entry])
            except KeyError:
                logger.error(
                    "%sUnknown unclean-water source specified in the scenario file: %s"
                    "%s",
                    BColours.fail,
                    entry,
                    BColours.endc,
                )
                raise InputFileError(
                    "desalination scenario",
                    f"{BColours.fail}Unknown unclean-water source in the scenario "
                    + f"file: {entry}{BColours.endc}",
                ) from None

    if scenario.hot_water_scenario is not None:
        # Process the hot-water converters.
        for entry in scenario.hot_water_scenario.conventional_sources:
            try:
                available_converters.append(converters[entry])
            except KeyError:
                logger.error(
                    "%sUnknown conventional hot-water source specified in the "
                    "hot-water scenario file: %s%s",
                    BColours.fail,
                    entry,
                    BColours.endc,
                )
                raise InputFileError(
                    "hot-water scenario",
                    f"{BColours.fail}Unknown conventional hot-water source(s) in the "
                    + f"hot-water scenario file: {entry}{BColours.endc}",
                ) from None

        if scenario.hot_water_scenario.auxiliary_heater == AuxiliaryHeaterType.ELECTRIC:
            if minigrid.electric_water_heater is None:
                logger.error(
                    "%sAuxiliary heating method of electric heating specified despite "
                    "no electric water heater being selected in the energy-system "
                    "inputs.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise InputFileError(
                    "energy system inputs OR hot-water scenario",
                    "Mismatch between electric water heating scenario.",
                )
            available_converters.append(converters[minigrid.electric_water_heater.name])

    return available_converters
