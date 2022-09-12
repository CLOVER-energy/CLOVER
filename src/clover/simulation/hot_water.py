#!/usr/bin/python3
########################################################################################
# hot_water.py - Energy-system hot-water module for CLOVER.                            #
#                                                                                      #
# Authors: Ben Winchester                                                              #
# Copyright: Ben Winchester, 2022                                                      #
# Date created: 31/08/2022                                                             #
# License: Open source                                                                 #
#                                                                                      #
# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
hot_water.py - The energy-system module for CLOVER.

This module aids the energy-system calculation for CLOVER in carrying out its hot-water
system calculation.

"""

from collections import defaultdict
from logging import Logger
from typing import DefaultDict, Dict, List, Optional, Tuple, Union

import pandas as pd

from ..__utils__ import (
    AuxiliaryHeaterType,
    BColours,
    ColdWaterSupply,
    FlowRateError,
    InputFileError,
    InternalError,
    ProgrammerJudgementFault,
    ResourceType,
    Scenario,
    SolarPanelType,
    WasteProduct,
)
from ..conversion.conversion import Converter
from .__utils__ import Minigrid
from .diesel import DieselWaterHeater
from .solar import calculate_solar_thermal_output

__all__ = ("calculate_renewable_hw_profiles",)


def _check_water_pump(
    logger: Logger,
    minigrid: Minigrid,
    scenario: Scenario,
    solar_thermal_size: float,
    pvt_size: float,
) -> None:
    """
    Checks that the water pump is correctly sized to meet flow-rate requirements.

    Inputs:
        - logger:
            The logger to use for the run.
        - minigrid:
            The minigrid being simulated.
        - scenario:
            The current :class:`Scenario`.
        - solar_thermal_size:
            The size of the solar-thermal system, measured in solar-thermal units.
        - pvt_size:
            The size of the PV-T system, measured in PV-T units.

    Raises:
        - FlowRateError:
            Raised if the pump flow rate does not match up correctly.
        - ProgrammerJudgementFault:
            Raised if no renewable sources which require pumping are included and this
            function was called.

    """

    if minigrid.water_pump is None:
        logger.error(
            "%sNo water pump defined on the minigrid despite PV-T or solar-thermal "
            "modelling being requested via the scenario files.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InternalError(
            "No water pump defined as part of the energy system despite solar-thermal "
            "or PV-T modelling being requested."
        )

    # Determine whether the water pump is capable for supplying the PV-T or
    # solar-thermal collectors with enough throughput.
    if scenario.pv_t:
        if (
            scenario.hot_water_scenario.pvt_scenario.mass_flow_rate * pvt_size
            > minigrid.water_pump.throughput
        ):
            logger.error(
                "%sThe water pump supplied, %s, is incapable of meeting the required "
                "PV-T flow rate of %s litres/hour. Max pump throughput: %s litres/hour."
                "%s",
                BColours.fail,
                minigrid.water_pump.name,
                scenario.hot_water_scenario.pvt_scenario.mass_flow_rate * pvt_size,
                minigrid.water_pump.throughput,
                BColours.endc,
            )
            raise FlowRateError(
                "water pump",
                f"The water pump defined, {minigrid.water_pump.name}, is unable to "
                "meet PV-T flow requirements.",
            )

    elif scenario.solar_thermal:
        if (
            scenario.hot_water_scenario.pvt_scenario.mass_flow_rate * solar_thermal_size
            > minigrid.water_pump.throughput
        ):
            logger.error(
                "%sThe water pump supplied, %s, is incapable of meeting the required "
                "solar-thermal flow rate of %s litres/hour. Max pump throughput: %s "
                "litres/hour.%s",
                BColours.fail,
                minigrid.water_pump.name,
                scenario.hot_water_scenario.solar_thermal_scenario.mass_flow_rate
                * pvt_size,
                minigrid.water_pump.throughput,
                BColours.endc,
            )
            raise FlowRateError(
                "water pump",
                f"The water pump defined, {minigrid.water_pump.name}, is unable to "
                "meet solar-thermal flow requirements.",
            )

    else:
        logger.error(
            "%sA renewable HW profile calculation was called despite neither PV-T nor "
            "solar-thermal panels being present.%s",
            BColours.fail,
            BColours.endc,
        )
        raise ProgrammerJudgementFault(
            "energy_system::calculate_renewable_hw_profiles",
            "Cannot calculate renewable HW profiles if no renewables sources of HW.",
        )


def _determine_auxiliary_heater(
    converters: List[Converter], logger: Logger, minigrid: Minigrid, scenario: Scenario
) -> Optional[Converter]:
    """
    Determine the auxiliary heater associated with the system based on the scenario.

    Inputs:
        - converters:
            The `list` of :class:`Converter` instances available to be used.
        - logger:
            The logger to use for the run.
        - minigrid:
            The minigrid being simulated.
        - scenario:
            The current :class:`Scenario`.

    Outputs:
        The auxiliary heater associated with the system.

    """

    if scenario.hot_water_scenario.auxiliary_heater == AuxiliaryHeaterType.DIESEL:
        auxiliary_heater: Optional[
            Union[Converter, DieselWaterHeater]
        ] = minigrid.diesel_water_heater
        if auxiliary_heater is None:
            logger.error(
                "%sDiesel water heater not defined despite hot-water auxiliary "
                "heating mode being specified as diesel.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "energy system inputs OR hot-water scenario",
                "No diesel hot-water heater defined despite the hot-water "
                "scenario specifying that this is needed.",
            )

    elif scenario.hot_water_scenario.auxiliary_heater == AuxiliaryHeaterType.ELECTRIC:
        try:
            auxiliary_heater = [
                converter
                for converter in converters
                if converter.output_resource_type == ResourceType.HOT_CLEAN_WATER
                and ResourceType.ELECTRIC in converter.input_resource_consumption
                and ResourceType.CLEAN_WATER in converter.input_resource_consumption
            ][0]
        except IndexError:
            logger.error(
                "%sFailed to determine electric water heater despite an electric "
                "auxiliary hot-water type being selected.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "energy system inputs OR hot-water scenario",
                "No electric water heater defined despite the hot-water scenario "
                "specifying that this is needed.",
            ) from None
    elif scenario.hot_water_scenario.auxiliary_heater is None:
        auxiliary_heater = None
    else:
        logger.error(
            "%sAuxiliary water heater scenario was not of valid types. Valid types: %s%s",
            BColours.fail,
            ", ".join({e.value for e in AuxiliaryHeaterType}),
            BColours.endc,
        )
        raise InputFileError(
            "hot-water scenario", "Invalid auxiliary water heater type specified."
        )

    return auxiliary_heater


def calculate_renewable_hw_profiles(  # pylint: disable=too-many-locals, too-many-statements
    converters: List[Converter],
    disable_tqdm: bool,
    end_hour: int,
    irradiance_data: pd.Series,
    logger: Logger,
    minigrid: Minigrid,
    number_of_hw_tanks: int,
    processed_total_hw_load: pd.DataFrame,
    pvt_size: int,
    scenario: Scenario,
    solar_thermal_size: int,
    start_hour: int,
    temperature_data: pd.Series,
    total_waste_produced: Dict[WasteProduct, DefaultDict[int, float]],
    wind_speed_data: Optional[pd.Series],
) -> Tuple[
    Optional[Union[Converter, DieselWaterHeater]],
    pd.DataFrame,
    Dict[SolarPanelType, pd.DataFrame],
    Dict[SolarPanelType, pd.DataFrame],
    pd.DataFrame,
    Optional[pd.DataFrame],
    Optional[pd.DataFrame],
    Optional[pd.DataFrame],
    Optional[pd.DataFrame],
    Optional[pd.DataFrame],
    Dict[WasteProduct, DefaultDict[int, float]],
    Optional[pd.DataFrame],
]:
    """
    Calculates renewable hot-water related profiles for the system.

    Inputs:
        - converters:
            The `list` of :class:`Converter` instances available to be used.
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - end_hour:
            The final hour for which the simulation will be carried out.
        - irradiance_data:
            The total solar irradiance data.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - minigrid:
            The energy system being considered.
        - number_of_hw_tanks:
            The number of hot-water tanks installed.
        - processed_total_hw_load:
            The total hot-water load placed on the system, defined in litres/hour at
            every time step.
        - pvt_size:
            Amount of PV-T in PV-T units.
        - scenario:
            The scenario being considered.
        - solar_thermal_size:
            Amount of solar-thermal in solar-thermal units.
        - start_hour:
            The first hour for which the simulation will be carried out.
        - temperature_data:
            The temperature data series.
        - total_waste_produced:
            A mapping between waste products and the associated waste produced at each
            time step.
        - wind_speed_data:
            The wind-speed data series.

    Outputs:
        - auxiliary_heater:
            The auxiliary heater associated with the system.
        - hot_water_power_consumed:
            The electric power consumed by the hot-water system, including any water
            pumps and electricity that was used meeting unmet hot-water demand.
        - hot_water_collectors_input_temperatures:
            The input temperature of HTF entering the solar-thermal collectors
            associated with the system, keyed by collector.
        - hot_water_collectors_output_temperatures:
            The output temperature of HTF entering the solar-thermal collectors
            associated with the system, keyed by collector.
        - hot_water_pvt_electric_power_per_unit:
            The electric power produced by the PV-T, in kWh, per unit of PV-T installed.
        - hot_water_system_output_temperature:
            The output temperature of the system, measured in degrees Celsius.
        - hot_water_tank_temperature:
            The temperature of the hot-water tank, in degrees Celsius, at each time
            step throughout the simulation period.
        - hot_water_tank_volume_supplied:
            The volume of hot-water supplied by the hot-water tank.
        - hot_water_temperature_gain:
            The temperature gain of water having been heated by the hot-water system.
        - solar_thermal_hw_fraction:
            The fraction of the hot-water demand which was covered using renewables vs
            which was covered using auxiliary means.
        - total_waste_produced:
            The updated total waste produced by the system.
        - volumetric_hw_dc_fraction:
            The fraction of the hot-water demand which was covered by the system
            overall, i.e., the volume of water which the system was able to supply
            divided by the total load.

    """

    if (
        not (scenario.pv_t or scenario.solar_thermal)
        or scenario.hot_water_scenario is None
    ):
        logger.debug("Skipping hot-water profile calculation.")
        return (
            None,
            pd.DataFrame([0] * (end_hour - start_hour)),
            None,
            None,
            pd.DataFrame([0] * (end_hour - start_hour)),
            None,
            None,
            None,
            None,
            None,
            total_waste_produced,
            None,
        )

    logger.info("Calculating hot-water performance profiles.")
    if wind_speed_data is None:
        raise InternalError(
            "Wind speed data required in solar-thermal or PV-T computation and not "
            "passed to the hot-water module."
        )

    if scenario.hot_water_scenario.cold_water_supply != ColdWaterSupply.UNLIMITED:
        logger.error(
            "%sOnly '%s' cold-water supplies for the hot-water system are "
            "currently supported.%s",
            BColours.fail,
            ColdWaterSupply.UNLIMITED.value,
            BColours.endc,
        )

    _check_water_pump(logger, minigrid, scenario, solar_thermal_size, pvt_size)
    auxiliary_heater = _determine_auxiliary_heater(converters, logger, minigrid, scenario)

    logger.debug("Auxiliary heater successfully determined.")
    logger.debug("Auxiliary heater: %s", str(auxiliary_heater))

    # Compute the output of the renewable solar hot-water system.
    hot_water_collectors_input_temperatures: Dict[SolarPanelType, pd.DataFrame]
    hot_water_collectors_output_temperatures: Dict[SolarPanelType, pd.DataFrame]
    hot_water_pvt_electric_power_per_unit: pd.DataFrame
    hot_water_system_output_temperature: pd.DataFrame
    hot_water_collector_pump_times: pd.DataFrame
    hot_water_tank_temperature: Optional[pd.DataFrame]
    hot_water_volume_supplied: Optional[pd.DataFrame]
    (
        hot_water_collectors_input_temperatures,
        hot_water_collectors_output_temperatures,
        hot_water_pvt_electric_power_per_unit,
        hot_water_system_output_temperature,
        hot_water_collector_pump_times,
        hot_water_tank_temperature,
        hot_water_volume_supplied,
    ) = calculate_solar_thermal_output(
        {
            SolarPanelType.PV_T: pvt_size,
            SolarPanelType.SOLAR_THERMAL: solar_thermal_size,
        },
        disable_tqdm,
        end_hour,
        irradiance_data[start_hour:end_hour],
        logger,
        minigrid,
        number_of_hw_tanks,
        processed_total_hw_load.iloc[:, 0],
        ResourceType.HOT_CLEAN_WATER,
        scenario,
        {
            SolarPanelType.PV_T: minigrid.pvt_panel,
            SolarPanelType.SOLAR_THERMAL: minigrid.solar_thermal_panel,
        },
        start_hour,
        temperature_data[start_hour:end_hour],
        None,
        wind_speed_data[start_hour:end_hour],
    )
    logger.debug("Hot-water PV-T performance successfully computed.")

    # Compute the electric power consumed by the auxiliary heater.
    if auxiliary_heater is not None:
        # Determine the electric power consumed by the auxiliary heater.
        auxiliary_heater_power_consumption: pd.DataFrame = pd.DataFrame(
            0.001
            * auxiliary_heater.input_resource_consumption[
                ResourceType.ELECTRIC
            ]  # [Wh/degC]
            * (
                hot_water_volume_supplied  # type: ignore [operator]
                / auxiliary_heater.input_resource_consumption[ResourceType.CLEAN_WATER]
            )  # [operating fraction]
            * (hot_water_volume_supplied > 0)  # type: ignore [operator]
            * (  # type: ignore [arg-type]
                scenario.hot_water_scenario.demand_temperature  # type: ignore [operator]
                - hot_water_tank_temperature
            )  # [degC]
        )

        if isinstance(auxiliary_heater, DieselWaterHeater):
            # Compute the heat consumed by the auxiliary heater.
            auxiliary_heater_heat_consumption: pd.DataFrame = pd.DataFrame(  # pylint: disable=unused-variable
                (hot_water_volume_supplied > 0)
                * hot_water_volume_supplied  # type: ignore [operator]
                * minigrid.hot_water_tank.heat_capacity
                * (
                    scenario.hot_water_scenario.demand_temperature  # type: ignore [operator]
                    - hot_water_tank_temperature
                )
            )
        else:
            auxiliary_heater_heat_consumption = pd.DataFrame(
                [0] * (end_hour - start_hour)
            )

        # Update the waste production calculation with the waste that's produced by
        # the auxiliary water heater.
        total_waste_produced.update(
            {
                waste_product: defaultdict(
                    float,
                    pd.DataFrame(  # type: ignore [arg-type]
                        (
                            waste_produced
                            * (
                                hot_water_volume_supplied  # type: ignore [operator]
                                / auxiliary_heater.input_resource_consumption[
                                    ResourceType.CLEAN_WATER
                                ]
                            )
                            * (hot_water_volume_supplied > 0)  # type: ignore [operator]
                            * (  # type: ignore [attr-defined]
                                scenario.hot_water_scenario.demand_temperature  # type: ignore [operator]  # pylint: disable=line-too-long
                                - hot_water_tank_temperature
                            )
                        ).values
                    ).to_dict(),
                )
                for waste_product, waste_produced in auxiliary_heater.waste_production.items()
            }
        )

    else:
        auxiliary_heater_power_consumption = pd.DataFrame([0] * (end_hour - start_hour))
        auxiliary_heater_heat_consumption = pd.DataFrame([0] * (end_hour - start_hour))

    # Compute the power consumed by the thermal desalination plant.
    hot_water_power_consumed: pd.DataFrame = pd.DataFrame(
        auxiliary_heater_power_consumption
        + 0.001
        * (hot_water_collector_pump_times > 0)  # type: ignore
        * minigrid.water_pump.consumption
    )
    if auxiliary_heater_power_consumption is not None:
        hot_water_power_consumed += auxiliary_heater_power_consumption  # type: ignore [operator]

    # Determine the volume of hot-water demand that was met by the system overall.
    volumetric_hw_dc_fraction: pd.DataFrame = pd.DataFrame(
        [
            ((supplied / load) if load is not None and load > 0 else None)
            for supplied, load in zip(
                hot_water_volume_supplied[0],  # type: ignore [call-overload]
                processed_total_hw_load[0],  # type: ignore [call-overload]
            )
        ]
    )

    # Determine the temperature gain of the hot-water as compared with the mains
    # supply temperature.
    hot_water_temperature_gain: Optional[pd.DataFrame] = (
        hot_water_system_output_temperature
        - scenario.hot_water_scenario.cold_water_supply_temperature
    )

    # Determine the fraction of the output which was met renewably.
    solar_thermal_hw_fraction: pd.DataFrame = (
        # The fraction of the supply that was met volumetrically.
        volumetric_hw_dc_fraction
        # The fraction of the total demand temperature that was covered using
        # renewables.
        * hot_water_temperature_gain.values  # type: ignore  [union-attr]
        / (
            scenario.hot_water_scenario.demand_temperature
            - scenario.hot_water_scenario.cold_water_supply_temperature
        )
    )

    hot_water_power_consumed = hot_water_power_consumed.reset_index(drop=True)
    hot_water_temperature_gain = hot_water_temperature_gain.reset_index(  # type: ignore  [union-attr]  # pylint: disable=line-too-long
        drop=True
    )
    solar_thermal_hw_fraction = solar_thermal_hw_fraction.reset_index(drop=True)
    logger.debug("Hot-water PV-T performance profiles determined.")

    return (
        auxiliary_heater,
        hot_water_power_consumed,
        hot_water_collectors_input_temperatures,
        hot_water_collectors_output_temperatures,
        hot_water_pvt_electric_power_per_unit,
        hot_water_system_output_temperature,
        hot_water_tank_temperature,
        hot_water_volume_supplied,
        hot_water_temperature_gain,
        solar_thermal_hw_fraction,
        total_waste_produced,
        volumetric_hw_dc_fraction,
    )
