#!/usr/bin/python3
########################################################################################
# minigrid.py - Energy-system main module for CLOVER.                                  #
#                                                                                      #
# Authors: Phil Sandwell, Ben Winchester                                               #
# Copyright: Phil Sandwell, 2018                                                       #
# Date created: 13/07/2021                                                             #
# License: Open source                                                                 #
#                                                                                      #
# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
minigrid.py - The energy-system module for CLOVER.

This module carries out a simulation for an energy system based on the various inputs
and profile files that have been parsed/generated.

"""

import datetime
import math

from logging import Logger
from typing import Dict, List, Optional, Tuple, Union

import numpy as np  # pylint: disable=import-error
import pandas as pd  # pylint: disable=import-error

from tqdm import tqdm

from ..__utils__ import (
    AuxiliaryHeaterType,
    BColours,
    CleanWaterMode,
    ColdWaterSupply,
    ColumnHeader,
    DieselMode,
    HOURS_PER_YEAR,
    HTFMode,
    InputFileError,
    InternalError,
    ProgrammerJudgementFault,
    RenewableEnergySource,
    ResourceType,
    Location,
    Scenario,
    Simulation,
    SystemDetails,
    dict_to_dataframe,
)
from ..conversion.conversion import Converter, ThermalDesalinationPlant, WaterSource
from ..generation.solar import solar_degradation
from ..load.load import compute_processed_load_profile, population_hourly
from .__utils__ import determine_available_converters, Minigrid
from .diesel import (
    DieselWaterHeater,
    get_diesel_energy_and_times,
    get_diesel_fuel_usage,
)
from .solar import calculate_pvt_output
from .storage import (
    battery_iteration_step,
    cw_tank_iteration_step,
    get_electric_battery_storage_profile,
    get_water_storage_profile,
)
from .storage_utils import CleanWaterTank

__all__ = (
    "Minigrid",
    "run_simulation",
)


def _calculate_backup_diesel_generator_usage(
    blackout_times: pd.DataFrame,
    minigrid: Minigrid,
    scenario: Scenario,
    total_electric_load: float,
    unmet_energy: pd.DataFrame,
) -> Tuple[float, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Calculates the backup diesel generator usage based on the scenario.

    Inputs:
        - blackout_times:
            The times for which the system experienced a blackout.
        - minigrid:
            The :class:`Minigrid` being considered.
        - scenario:
            The :class:`Scenario` being used for the run.
        - unmet_energy:
            Load profile of currently unment energy
        - total_electric_load:
            The total electric load placed on the system (kWh).

    Outputs:
        - diesel_capacity:
            The capacity of diesel that needed to be installed to meet the demand.
        - diesel_energy:
            The total energy that was supplied by the diesel system.
        - diesel_fuel_usage:
            The total amount of fuel that was consumed byt he diesel generators.
        - diesel_times:
            The times forw hich the diesel generator was operating.
        - unmet_energy:
            The remaining energy demand which went uynmet after the diesel generator
            fulfilled demand to the :class:`Scenario`'s specification.

    """

    if scenario.diesel_scenario.backup_threshold is None:
        raise InputFileError(
            "diesel inputs",
            "Diesel mode `backup` was selected but no backup threshold was "
            "specified.",
        )
    if minigrid.diesel_generator is None:
        raise InputFileError(
            "energy system inputs",
            "No backup diesel generato was provided on the energy system despite "
            "the diesel mode `backup` being selected.",
        )
    diesel_energy, diesel_times = get_diesel_energy_and_times(
        unmet_energy,
        blackout_times,
        float(scenario.diesel_scenario.backup_threshold),
        total_electric_load,
        scenario.diesel_scenario.mode,
    )
    diesel_capacity: float = float(math.ceil(np.max(diesel_energy, axis=0)))
    diesel_fuel_usage = pd.DataFrame(
        get_diesel_fuel_usage(
            int(diesel_capacity),
            minigrid.diesel_generator,
            diesel_energy,
            diesel_times,
        ).values
    )
    unmet_energy = pd.DataFrame(unmet_energy.values - diesel_energy.values)
    diesel_energy = diesel_energy.abs()  # type: ignore

    return diesel_capacity, diesel_energy, diesel_fuel_usage, diesel_times, unmet_energy


def _calculate_electric_desalination_parameters(
    converters: List[Converter],
    feedwater_sources: List[Converter],
    logger: Logger,
    scenario: Scenario,
) -> Tuple[List[Converter], float, float]:
    """
    Calculates parameters needed for computing electric desalination.

    Inputs:
        - converters:
            The `list` of :class:`Converter` instances defined for the system.
        - feedwater_sources:
            The `list` of :class:`WaterSource` instances that produce feedwater as their
            outputs.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - scenario:
            The :class:`Scenario` for the run.

    Outputs:
        - The `list` of electric desalinators :class:`Converter` instances defined on
          the system.
        - The electric energy consumed per desalinated litre of water produced.
        - The maximum throughput of the electric desalination system.

    """

    # If the mode is backup or prioritise.
    if (
        scenario.desalination_scenario is not None
        and scenario.desalination_scenario.clean_water_scenario.mode
        in {CleanWaterMode.BACKUP, CleanWaterMode.PRIORITISE}
    ):
        # Initialise deslination converters.
        electric_desalinators: List[Converter] = sorted(
            [
                converter
                for converter in converters
                if list(converter.input_resource_consumption)
                == [ResourceType.ELECTRIC, ResourceType.UNCLEAN_WATER]
                and converter.output_resource_type == ResourceType.CLEAN_WATER
            ]
        )

        # Raise an error if there were no electric desalinators defined.
        if len(electric_desalinators) == 0:
            logger.error(
                "%sNo electric desalinators defined despite the desalination mode "
                "being %s%s",
                BColours.fail,
                scenario.desalination_scenario.clean_water_scenario.mode.value,
                BColours.endc,
            )
            raise InputFileError(
                "desalination scenario",
                "No electric desalination devices defined but are required by the "
                "scenario.",
            )
        logger.debug(
            "Electric desalinators: %s",
            ", ".join(str(entry) for entry in electric_desalinators),
        )

        # Compute the amount of energy required per litre desalinated.
        energy_per_desalinated_litre: float = 0.001 * float(
            np.mean(
                [
                    desalinator.input_resource_consumption[ResourceType.ELECTRIC]
                    / desalinator.maximum_output_capacity
                    + desalinator.input_resource_consumption[ResourceType.UNCLEAN_WATER]
                    * feedwater_sources[0].input_resource_consumption[
                        ResourceType.ELECTRIC
                    ]
                    / desalinator.maximum_output_capacity
                    for desalinator in electric_desalinators
                ]
            )
        )

        # Compute the maximum throughput
        maximum_water_throughput: float = min(
            sum(
                desalinator.maximum_output_capacity
                for desalinator in electric_desalinators
            ),
            sum(source.maximum_output_capacity for source in feedwater_sources),
        )
    else:
        electric_desalinators = []
        energy_per_desalinated_litre = 0
        maximum_water_throughput = 0

    return electric_desalinators, energy_per_desalinated_litre, maximum_water_throughput


def _calculate_renewable_cw_profiles(  # pylint: disable=too-many-locals, too-many-statements
    converters: List[Converter],
    disable_tqdm: bool,
    end_hour: int,
    irradiance_data: pd.Series,
    logger: Logger,
    minigrid: Minigrid,
    number_of_cw_tanks: int,
    pvt_size: int,
    scenario: Scenario,
    start_hour: int,
    temperature_data: pd.Series,
    wind_speed_data: Optional[pd.Series],
) -> Tuple[
    Optional[pd.DataFrame],
    pd.DataFrame,
    List[Converter],
    Optional[pd.DataFrame],
    pd.DataFrame,
    pd.DataFrame,
    List[Converter],
    pd.DataFrame,
]:
    """
    Calculates PV-T related profiles.

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
        - number_of_cw_tanks:
            The number of clean-water tanks installed within the system.
        - pvt_size:
            Amount of PV-T in PV-T units.
        - scenario:
            The scenario being considered.
        - start_hour:
            The first hour for which the simulation will be carried out.
        - temperature_data:
            The temperature data series.
        - wind_speed_data:
            The wind-speed data series.

    Outputs:
        - buffer_tank_temperature:
            The temperature of the buffer tank, measured in degrees Celcius.
        - buffer_tank_volume_supplied:
            The volume of buffer solution outputted by the HTF buffer tanks.
        - feedwater_sources:
            The :class:`Converter` instances which are a source of feedwater to the PV-T
            system.
        - clean_water_pvt_collector_output_temperature:
            The output temperature of HTF from the PV-T collectors, measured in degrees
            Celcius.
        - clean_water_pvt_electric_power_per_unit:
            The electric power produced by the PV-T, in kWh, per unit of PV-T installed.
        - renewable_cw_produced:
            The amount of clean water produced renewably, measured in litres.
        - required_feedwater_sources:
            The `list` of feedwater sources required to supply the needs of the
            desalination system.
        - thermal_desalination_electric_power_consumed:
            The electric power consumed in operating the thermal desalination plant,
            measured in kWh.

    """

    if scenario.desalination_scenario is not None:
        # Determine the list of available feedwater sources.
        logger.info("Determining available feedwater sources.")
        feedwater_sources: List[Converter] = sorted(
            [
                converter
                for converter in converters
                if list(converter.input_resource_consumption) == [ResourceType.ELECTRIC]
                and converter.output_resource_type == ResourceType.UNCLEAN_WATER
            ]
        )
        logger.debug(
            "Available feedwater sources determined: %s",
            ", ".join([str(source) for source in feedwater_sources])
            if len(feedwater_sources) > 0
            else "",
        )
    else:
        feedwater_sources = []

    if scenario.pv_t and scenario.desalination_scenario is not None:
        logger.info("Calculating clean-water PV-T performance profiles.")
        if wind_speed_data is None:
            raise InternalError(
                "Wind speed data required in PV-T computation and not passed to the "
                "energy system module."
            )
        if minigrid.water_pump is None:
            logger.error(
                "%sNo water pump defined on the minigrid despite PV-T modelling being "
                "requested via the scenario files.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "No water pump defined as part of the energy system despite the PV-T "
                "modelling being requested."
            )

        # Determine the thermal desalination plant being used.
        logger.info("Determining desalination plant.")
        try:
            thermal_desalination_plant: ThermalDesalinationPlant = [
                converter
                for converter in converters
                if isinstance(converter, ThermalDesalinationPlant)
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
        logger.info(
            "Desalination plant determined: %s", thermal_desalination_plant.name
        )

        # Determine whether the water pump is capable for supplying the PV-T panels with
        # enough throughput.
        if (
            scenario.desalination_scenario.pvt_scenario.mass_flow_rate * pvt_size
            > minigrid.water_pump.throughput
        ):
            logger.error(
                "%sThe water pump supplied, %s, is incapable of meeting the required "
                "PV-T flow rate of %s litres/hour. Max pump throughput: %s litres/hour."
                "%s",
                BColours.fail,
                minigrid.water_pump.name,
                scenario.desalination_scenario.pvt_scenario.mass_flow_rate * pvt_size,
                minigrid.water_pump.throughput,
                BColours.endc,
            )
            raise InputFileError(
                "transmission inputs",
                "The water pump defined is unable to meet PV-T flow requirements.",
            )

        if thermal_desalination_plant.htf_mode == HTFMode.CLOSED_HTF:
            thermal_desalination_plant_input_type: ResourceType = (
                ResourceType.UNCLEAN_WATER
            )
        if thermal_desalination_plant.htf_mode == HTFMode.FEEDWATER_HEATING:
            thermal_desalination_plant_input_type = ResourceType.HOT_UNCLEAN_WATER
        if thermal_desalination_plant.htf_mode == HTFMode.COLD_WATER_HEATING:
            logger.error(
                "%sCold-water heating thermal desalination plants are not supported.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InputFileError(
                "converter inputs OR desalination scenario",
                f"The htf mode '{HTFMode.COLD_WATER_HEATING.value}' is not currently "
                "supported.",
            )

        thermal_desalination_plant_input_flow_rate = (
            thermal_desalination_plant.input_resource_consumption[
                thermal_desalination_plant_input_type
            ]
        )

        if (
            sum(
                feedwater_source.maximum_output_capacity
                for feedwater_source in feedwater_sources
            )
            < thermal_desalination_plant_input_flow_rate
        ):
            logger.error(
                "%sThe feedwater sources are unable to supply enough throughput to "
                "facilitate the thermal desalination plant. If you are running a "
                "simulation, consider using a smaller desalination plant or a larger "
                "number of feedwater sources. If you are running an optimisation, "
                "consider using a greater number of feedwater sources as your initial "
                "maximum point. Or, it is possible that no feedwater sources have been "
                "defined within your optimisation inputs file.%s",
                BColours.fail,
                BColours.endc,
            )
            logger.info(
                "Feedwater sources: %s",
                ", ".join([str(source) for source in feedwater_sources]),
            )
            logger.info("Desalination plant: %s", thermal_desalination_plant)
            raise InputFileError(
                "desalination scenario",
                "The feedwater sources cannot meet the thermal desalination plant "
                "input demand.",
            )

        logger.info("Determining required feedwater sources.")
        feedwater_capacity: float = 0
        required_feedwater_sources: List[Converter] = []
        while (
            feedwater_capacity
            < thermal_desalination_plant.input_resource_consumption[
                thermal_desalination_plant_input_type
            ]
        ):
            required_feedwater_sources.append(feedwater_sources.pop(0))
            feedwater_capacity += required_feedwater_sources[-1].maximum_output_capacity

        feedwater_sources.extend(required_feedwater_sources)
        logger.info("Required feedwater sources determined.")
        logger.debug(
            "Required feedwater sources: %s",
            ", ".join([str(source) for source in required_feedwater_sources]),
        )

        # Compute the output of the PV-T system.
        clean_water_pvt_collector_output_temperature: Optional[pd.DataFrame]
        buffer_tank_temperature: Optional[pd.DataFrame]
        (
            clean_water_pvt_collector_output_temperature,
            clean_water_pvt_electric_power_per_unit,
            clean_water_pvt_pump_times,
            buffer_tank_temperature,
            buffer_tank_volume_supplied,
        ) = calculate_pvt_output(
            disable_tqdm,
            end_hour,
            irradiance_data[start_hour:end_hour],
            logger,
            minigrid,
            number_of_cw_tanks,
            None,
            pvt_size,
            ResourceType.CLEAN_WATER,
            scenario,
            start_hour,
            temperature_data[start_hour:end_hour],
            thermal_desalination_plant,
            wind_speed_data[start_hour:end_hour],
        )
        logger.info("PV-T performance successfully computed.")

        # Compute the clean water supplied by the desalination unit.
        renewable_cw_produced: pd.DataFrame = (
            buffer_tank_volume_supplied > 0
        ) * thermal_desalination_plant.maximum_output_capacity

        # Compute the power consumed by the thermal desalination plant.
        thermal_desalination_electric_power_consumed: pd.DataFrame = pd.DataFrame(
            (
                (renewable_cw_produced > 0)
                * (
                    0.001
                    * thermal_desalination_plant.input_resource_consumption[
                        ResourceType.ELECTRIC
                    ]
                    + 0.001
                    * sum(
                        source.input_resource_consumption[ResourceType.ELECTRIC]
                        for source in required_feedwater_sources
                    )
                )
            ).values
            + (clean_water_pvt_pump_times > 0) * 0.001 * minigrid.water_pump.consumption
        )

        buffer_tank_temperature = buffer_tank_temperature.reset_index(drop=True)
        clean_water_pvt_collector_output_temperature = (
            clean_water_pvt_collector_output_temperature.reset_index(drop=True)
        )
        clean_water_pvt_electric_power_per_unit = (
            clean_water_pvt_electric_power_per_unit.reset_index(drop=True)
        )
        renewable_cw_produced = renewable_cw_produced.reset_index(drop=True)
        buffer_tank_volume_supplied = buffer_tank_volume_supplied.reset_index(drop=True)
        thermal_desalination_electric_power_consumed = (
            thermal_desalination_electric_power_consumed.reset_index(drop=True)
        )
        logger.info("Clean-water PV-T performance profiles determined.")

    else:
        logger.info("Skipping clean-water PV-T performance-profile calculation.")
        buffer_tank_temperature = None
        buffer_tank_volume_supplied = pd.DataFrame([0] * (end_hour - start_hour))
        clean_water_pvt_collector_output_temperature = None
        clean_water_pvt_electric_power_per_unit = pd.DataFrame(
            [0] * (end_hour - start_hour)
        )
        renewable_cw_produced = pd.DataFrame([0] * (end_hour - start_hour))
        required_feedwater_sources = []
        thermal_desalination_electric_power_consumed = pd.DataFrame(
            [0] * (end_hour - start_hour)
        )

    return (
        buffer_tank_temperature,
        buffer_tank_volume_supplied,
        feedwater_sources,
        clean_water_pvt_collector_output_temperature,
        clean_water_pvt_electric_power_per_unit,
        renewable_cw_produced,
        required_feedwater_sources,
        thermal_desalination_electric_power_consumed,
    )


def _calculate_renewable_hw_profiles(  # pylint: disable=too-many-locals, too-many-statements
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
    start_hour: int,
    temperature_data: pd.Series,
    wind_speed_data: Optional[pd.Series],
) -> Tuple[
    Optional[Union[Converter, DieselWaterHeater]],
    pd.DataFrame,
    Optional[pd.DataFrame],
    pd.DataFrame,
    Optional[pd.DataFrame],
    Optional[pd.DataFrame],
    Optional[pd.DataFrame],
]:
    """
    Calculates PV-T related profiles for the hot-water system.

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
        - start_hour:
            The first hour for which the simulation will be carried out.
        - temperature_data:
            The temperature data series.
        - wind_speed_data:
            The wind-speed data series.

    Outputs:
        - auxiliary_heater:
            The auxiliary heater associated with the system.
        - hot_water_power_consumed:
            The electric power consumed by the hot-water system, including any water
            pumps and electricity that was used meeting unmet hot-water demand.
        - hot_water_pvt_collector_output_temperature:
            The output temperature from the PV-T panels associated with the hot-water
            system.
        - hot_water_pvt_electric_power_per_unit:
            The electric power produced by the PV-T, in kWh, per unit of PV-T installed.
        - hot_water_tank_temperature:
            The temperature of the hot-water tank, in degrees Celcius, at each time
            step throughout the simulation period.
        - hot_water_tank_volume_supplied:
            The volume of hot-water supplied by the hot-water tank.
        - renewable_hw_fraction:
            The fraction of the hot-water demand which was covered using renewables vs
            which was covered using auxiliary means.

    """

    if scenario.pv_t and scenario.hot_water_scenario is not None:
        logger.info("Calculating hot-water PV-T performance profiles.")
        if wind_speed_data is None:
            raise InternalError(
                "Wind speed data required in PV-T computation and not passed to the "
                "energy system module."
            )

        if scenario.hot_water_scenario.cold_water_supply != ColdWaterSupply.UNLIMITED:
            logger.error(
                "%sOnly '%s' cold-water supplies for the hot-water system are "
                "currently supported.%s",
                BColours.fail,
                ColdWaterSupply.UNLIMITED.value,
                BColours.endc,
            )

        if minigrid.hot_water_tank is None:
            logger.error(
                "%sNo hot-water tank was defined for the minigrid despite hot-water"
                "modelling being requested.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "No water pump defined as part of the energy system despite the PV-T "
                "modelling being requested."
            )

        if minigrid.water_pump is None:
            logger.error(
                "%sNo water pump defined on the minigrid despite PV-T modelling being "
                "requested via the scenario files.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "No water pump defined as part of the energy system despite the PV-T "
                "modelling being requested."
            )

        # Determine whether the water pump is capable for supplying the PV-T panels with
        # enough throughput.
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
            raise InputFileError(
                "transmission inputs",
                "The water pump defined is unable to meet PV-T flow requirements.",
            )

        # Determine the auxiliary heater associated with the system.
        if scenario.hot_water_scenario.auxiliary_heater == AuxiliaryHeaterType.DIESEL:
            auxiliary_heater: Optional[
                Union[Converter, DieselWaterHeater]
            ] = minigrid.diesel_water_heater
        if scenario.hot_water_scenario.auxiliary_heater == AuxiliaryHeaterType.ELECTRIC:
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

        logger.info("Auxiliary heater successfully determined.")
        logger.debug("Auxiliary heater: %s", str(auxiliary_heater))

        # Compute the output of the PV-T system.
        hot_water_pvt_collector_output_temperature: Optional[pd.DataFrame]
        hot_water_pvt_electric_power_per_unit: pd.DataFrame
        hot_water_pvt_pump_times: pd.DataFrame
        hot_water_tank_temperature: Optional[pd.DataFrame]
        hot_water_tank_volume_supplied: Optional[pd.DataFrame]
        (
            hot_water_pvt_collector_output_temperature,
            hot_water_pvt_electric_power_per_unit,
            hot_water_pvt_pump_times,
            hot_water_tank_temperature,
            hot_water_tank_volume_supplied,
        ) = calculate_pvt_output(
            disable_tqdm,
            end_hour,
            irradiance_data[start_hour:end_hour],
            logger,
            minigrid,
            number_of_hw_tanks,
            processed_total_hw_load.iloc[:, 0],
            pvt_size,
            ResourceType.HOT_CLEAN_WATER,
            scenario,
            start_hour,
            temperature_data[start_hour:end_hour],
            None,
            wind_speed_data[start_hour:end_hour],
        )
        logger.info("Hot-water PV-T performance successfully computed.")

        # Compute the heat consumed by the auxiliary heater.
        # auxiliary_heater_heat_consumption: pd.DataFrame = pd.DataFrame(
        #     (hot_water_tank_volume_supplied > 0)
        #     * hot_water_tank_volume_supplied  # type: ignore
        #     * minigrid.hot_water_tank.heat_capacity
        #     * (
        #         scenario.hot_water_scenario.demand_temperature  # type: ignore
        #         - hot_water_tank_temperature
        #     )
        # )

        # Compute the electric power consumed by the auxiliary heater.
        auxiliary_heater_power_consumption: pd.DataFrame = pd.DataFrame(
            0.001
            * auxiliary_heater.input_resource_consumption[
                ResourceType.ELECTRIC
            ]  # [Wh/degC]
            * (
                hot_water_tank_volume_supplied  # type: ignore
                / auxiliary_heater.input_resource_consumption[ResourceType.CLEAN_WATER]
            )  # [operating fraction]
            * (hot_water_tank_volume_supplied > 0)  # type: ignore
            * (  # type: ignore
                scenario.hot_water_scenario.demand_temperature  # type: ignore
                - hot_water_tank_temperature
            )
        )

        # Compute the power consumed by the thermal desalination plant.
        hot_water_power_consumed: pd.DataFrame = pd.DataFrame(
            auxiliary_heater_power_consumption
            + 0.001
            * (hot_water_pvt_pump_times > 0)  # type: ignore
            * minigrid.water_pump.consumption
        )

        # Determine the fraction of the output which was met renewably.
        renewable_hw_fraction: Optional[pd.DataFrame] = (  # type: ignore
            hot_water_tank_temperature
            - scenario.hot_water_scenario.cold_water_supply_temperature
        ) / (
            scenario.hot_water_scenario.demand_temperature
            - scenario.hot_water_scenario.cold_water_supply_temperature
        )

        hot_water_power_consumed = hot_water_power_consumed.reset_index(drop=True)
        hot_water_pvt_collector_output_temperature = (
            hot_water_pvt_collector_output_temperature.reset_index(drop=True)
        )
        hot_water_pvt_electric_power_per_unit = (
            hot_water_pvt_electric_power_per_unit.reset_index(drop=True)
        )
        hot_water_tank_temperature = hot_water_tank_temperature.reset_index(drop=True)
        hot_water_tank_volume_supplied = hot_water_tank_volume_supplied.reset_index(
            drop=True
        )
        renewable_hw_fraction = renewable_hw_fraction.reset_index(  # type: ignore
            drop=True
        )
        logger.info("Hot-water PV-T performance profiles determined.")

    else:
        logger.info("Skipping hot-water PV-T performance-profile calculation.")
        auxiliary_heater = None
        hot_water_power_consumed = pd.DataFrame([0] * (end_hour - start_hour))
        hot_water_pvt_collector_output_temperature = None
        hot_water_pvt_electric_power_per_unit = pd.DataFrame(
            [0] * (end_hour - start_hour)
        )
        hot_water_tank_temperature = None
        hot_water_tank_volume_supplied = None
        renewable_hw_fraction = None

    return (
        auxiliary_heater,
        hot_water_power_consumed,
        hot_water_pvt_collector_output_temperature,
        hot_water_pvt_electric_power_per_unit,
        hot_water_tank_temperature,
        hot_water_tank_volume_supplied,
        renewable_hw_fraction,
    )


def _setup_tank_storage_profiles(
    logger: Logger,
    number_of_tanks: int,
    power_consumed: pd.DataFrame,
    resource_type: ResourceType,
    scenario: Scenario,
    tank: Optional[CleanWaterTank],
) -> Tuple[Dict[int, float], float, float, float, Dict[int, float]]:
    """
    Sets up tank storage parameters.

    Inputs:
        - logger:
            The :class:`logging.Logger` to use for the run.
        - number_of_tanks:
            The number of tanks of this type to use for the run.
        - power_consumed:
            The electric power consumed associated with the storage of these
            :class:`ResourceType` tanks.
        - resource_type:
            The :class:`ResourceType` held within the :class:`CleanWaterTank`.
        - scenario:
            The :class:`Scenario` for the run.
        - tank:
            The :class:`CleanWaterTank`, representing either a clean- or hot-water tank,
            to use for the run.

    Outputs:
        - hourly_tank_storage:
            The hourly tank storage.
        - initial_tank_storage:
            The amount of water initially in the tank.
        - minimum_tank_storage:
            The minimum level of the tank permitted.
        - power_consumed_mapping:
            A mapping between time as `int` and the electric power consumed.

    """

    power_consumed_mapping: Dict[int, float] = power_consumed[  # type: ignore
        0
    ].to_dict()

    if (
        resource_type in scenario.resource_types
        and scenario.desalination_scenario is not None
    ):
        if tank is None:
            logger.error(
                "%sNo tank specifeid when attempting to compute %s loads.%s",
                BColours.fail,
                resource_type.value,
                BColours.endc,
            )
            raise InternalError(
                f"No {resource_type.value} tank specified on the energy system despite "
                + f"{resource_type.value} loads being requested.",
            )
        hourly_tank_storage: Dict[int, float] = {}
        initial_tank_storage: float = 0.0

        # Determine the maximum tank storage.
        try:
            maximum_tank_storage: float = (
                number_of_tanks * tank.mass * tank.maximum_charge
            )
        except AttributeError:
            logger.error(
                "%sNo %s water tank provided on the energy system despite associated "
                "demands expected.%s",
                BColours.fail,
                resource_type.value,
                BColours.endc,
            )
            raise InputFileError(
                "energy system OR tank",
                f"No {resource_type.value} water tank was provided on the energy "
                + f"system despite {resource_type.value}-water demands being expected.",
            ) from None

        try:
            minimum_tank_storage: float = (
                number_of_tanks * tank.mass * tank.minimum_charge
            )
        except AttributeError:
            logger.error(
                "%sNo %s water tank provided on the energy system despite associated "
                "demands expected.%s",
                BColours.fail,
                resource_type.value,
                BColours.endc,
            )
            raise InputFileError(
                "energy system OR tank",
                f"No {resource_type.value} water tank was provided on the energy "
                + f"system despite {resource_type.value}-water demands being expected.",
            ) from None

    else:
        hourly_tank_storage = {}
        initial_tank_storage = 0
        maximum_tank_storage = 0
        minimum_tank_storage = 0

    return (
        hourly_tank_storage,
        initial_tank_storage,
        maximum_tank_storage,
        minimum_tank_storage,
        power_consumed_mapping,
    )


def _update_battery_health(
    battery_energy_flow: float,
    battery_health: Dict[int, float],
    cumulative_battery_storage_power: float,
    electric_storage_size: float,
    hourly_battery_storage: Dict[int, float],
    maximum_battery_energy_throughput: float,
    minigrid: Minigrid,
    storage_power_supplied: Dict[int, float],
    *,
    time_index: int,
) -> Tuple[float, float, float]:
    """
    Updates the health of the batteries.

    Inputs:
        - battery_energy_flow:
            The net energy flow, into, or out of, the battery.
        - battery_health:
            The battery health at each time step.
        - cumulative_battery_storage_power: float:
            The cumulative amount of power that has been stored in the batteries,
            measured in kWh.
        - electric_storage_size:
            The size of the electric storage system.
        - hourly_battery_storage:
            The battery storage at each time step.
        - maximum_battery_energy_throughput:
            The maximum energy throughput through the batteries.
        - minigrid:
            The :class:`Minigrid` being modelled.
        - storage_power_supplied:
            The amount of power supplied by the storage system.
        - time_index:
            The current time (hour) being considered.

    Outputs:
        - cumulative_battery_storage_power:
            The cumulative amount of electricity that has been stored in the batteries.
        - maximum_battery_storage:
            The newly calculated maximum amount of energy that can be stored in the
            batteries having acounted for battery degredation.
        - minimum_battery_storage:
            The newly calculated minimum amount of energy that can be stored in the
            batteries having acounted for battery degredation.

    """

    if time_index == 0:
        storage_power_supplied[time_index] = 0.0 - battery_energy_flow
    else:
        storage_power_supplied[time_index] = max(
            hourly_battery_storage[time_index - 1]
            * (1.0 - minigrid.battery.leakage)  # type: ignore
            - hourly_battery_storage[time_index],
            0.0,
        )
    cumulative_battery_storage_power += storage_power_supplied[time_index]

    battery_storage_degradation = (
        1.0
        - minigrid.battery.lifetime_loss  # type: ignore
        * (cumulative_battery_storage_power / maximum_battery_energy_throughput)
    )
    maximum_battery_storage = (
        battery_storage_degradation
        * electric_storage_size
        * minigrid.battery.maximum_charge  # type: ignore
        * minigrid.battery.storage_unit  # type: ignore
    )
    minimum_battery_storage = (
        battery_storage_degradation
        * electric_storage_size
        * minigrid.battery.minimum_charge  # type: ignore
        * minigrid.battery.storage_unit  # type: ignore
    )
    battery_health[time_index] = battery_storage_degradation

    return (
        cumulative_battery_storage_power,
        maximum_battery_storage,
        minimum_battery_storage,
    )


def run_simulation(  # pylint: disable=too-many-locals, too-many-statements
    clean_water_pvt_size: int,
    conventional_cw_source_profiles: Optional[Dict[WaterSource, pd.DataFrame]],
    converters: Union[Dict[str, Converter], List[Converter]],
    disable_tqdm: bool,
    electric_storage_size: float,
    grid_profile: Optional[pd.DataFrame],
    hot_water_pvt_size: int,
    irradiance_data: pd.Series,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: Minigrid,
    number_of_cw_tanks: int,
    number_of_hw_tanks: int,
    pv_power_produced: pd.Series,
    pv_size: float,
    scenario: Scenario,
    simulation: Simulation,
    temperature_data: pd.Series,
    total_loads: Dict[ResourceType, Optional[pd.DataFrame]],
    wind_speed_data: Optional[pd.Series],
) -> Tuple[datetime.timedelta, pd.DataFrame, SystemDetails]:
    """
    Simulates a minigrid system

    This function simulates the energy system of a given capacity and to the parameters
    stated in the input files.

    Inputs:
        - clean_water_pvt_size:
            Amount of PV-T in PV-T units associated with the clean-water system.
        - conventional_cw_source_profiles:
            A mapping between :class:`WaterSource` instances and the associated water
            that can be drawn from the source throughout the duration of the simulation.
        - converters:
            The `list` of :class:`Converter` instances available to be used.
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - electric_storage_size:
            Amount of storage in terms of the number of batteries included.
        - grid_profile:
            The grid-availability profile.
        - hot_water_pvt_size:
            Amount of PV-T in PV-T units associated with the hot-water system.
        - irradiance_data:
            The total solar irradiance data.
        - kerosene_usage:
            The kerosene-usage profile.
        - location:
            The location being considered.
        - logger:
            The :class:`logging.Logger` to use for the run.
        - minigrid:
            The energy system being considered.
        - number_of_cw_tanks:
            The number of clean-water tanks installed in the system.
        - number_of_hw_tanks:
            The number of hot-water tanks installed in the system.
        - pv_size:
            Amount of PV in PV units.
        - pv_power_produced:
            The total energy outputted by the solar system per PV unit.
        - renewable_cw_produced:
            The amount of clean-water produced renewably, mesaured in litres.
        - scenario:
            The scenario being considered.
        - simulation:
            The simulation to run.
        - temperature_data:
            The temperature data series.
        - total_loads:
            A mapping between :class:`ResourceType`s and their associated total loads
            placed on the system.
        - wind_speed_data:
            The wind-speed data series.

    Outputs:
        - The time taken for the simulation.
        - System performance outputs:
            - system_performance_outputs:
                Hourly performance of the simulated system
            - load_energy:
                Amount of energy (kWh) required to satisfy the loads
            - total_energy_used:
                Amount of energy (kWh) used by the system
            - unmet_energy:
                Amount of energy (kWh) unmet by the system
            - blackout_times:
                Times with power is available (0) or unavailable (1)
            - renewables_energy_used_directly:
                Amount of energy (kWh) from renewables used directly to satisfy load
                (kWh)
            - storage_power_supplied:
                Amount of energy (kWh) supplied by battery storage
            - grid_energy:
                Amount of energy (kWh) supplied by the grid
            - diesel_energy:
                Amount of energy (kWh) supplied from diesel generator
            - diesel_times:
                Times when diesel generator is on (1) or off (0)
            - diesel_fuel_usage:
                Amount of diesel (l) used by the generator
            - battery_storage_profile:
                Amount of energy (kWh) into (+ve) and out of (-ve) the battery
            - renewables_energy:
                Amount of energy (kWh) provided by renewables to the system
            - hourly_battery_storage:
                Amount of energy (kWh) in the battery
            - energy_surplus:
                Amount of energy (kWh) dumped owing to overgeneration
            - battery_health:
                Relative capactiy of the battery compared to new (0.0-1.0)
            - households:
                Number of households in the community
            - kerosene_usage:
                Number of kerosene lamps in use (if no power available)
            - kerosene_mitigation:
                Number of kerosene lamps not used (when power is available)
        - System details about the run.

    """

    # Currently, only systems including batteries are supported.
    if minigrid.battery is None:
        logger.error(
            "%sNo battery information available when calling the energy system.%s",
            BColours.fail,
            BColours.endc,
        )
        raise Exception(
            "No battery information available when calling the energy system."
        )

    # Start timer to see how long simulation will take
    timer_start = datetime.datetime.now()

    # Initialise simulation parameters
    start_hour = simulation.start_year * HOURS_PER_YEAR
    end_hour = simulation.end_year * HOURS_PER_YEAR
    simulation_hours = end_hour - start_hour

    if isinstance(converters, dict):
        available_converters = determine_available_converters(
            converters, logger, minigrid, scenario
        )
        logger.info("Subset of available converters determined.")
    elif isinstance(converters, list):
        available_converters = converters
        logger.info("Converter sizes manually passed in, using information provided.")
    else:
        logger.error(
            "Unsupported type '%s' for converters in call to run_simulation.%s",
            BColours.fail,
            str(type(converters)),
            BColours.endc,
        )
        raise ProgrammerJudgementFault(
            "run-simulation function",
            "Misuse of `converters` parameter when calling `run_simulation`.",
        )
    logger.debug(
        "Available converters: %s",
        ", ".join([str(entry) for entry in available_converters]),
    )
    grid_profile = (
        grid_profile
        if grid_profile is not None
        else pd.DataFrame([0] * simulation_hours)
    )
    total_cw_load: Optional[pd.DataFrame] = total_loads[ResourceType.CLEAN_WATER]
    total_electric_load: Optional[pd.DataFrame] = total_loads[ResourceType.ELECTRIC]
    total_hw_load: Optional[pd.DataFrame] = total_loads[ResourceType.HOT_CLEAN_WATER]

    # Calculate PV-T related performance profiles.
    buffer_tank_temperature: Optional[pd.DataFrame]
    feedwater_sources: List[Converter]
    clean_water_pvt_collector_output_temperature: Optional[pd.DataFrame]
    clean_water_pvt_electric_power_per_unit: pd.DataFrame
    renewable_cw_produced: pd.DataFrame
    buffer_tank_volume_supplied: pd.DataFrame
    thermal_desalination_electric_power_consumed: pd.DataFrame

    (
        buffer_tank_temperature,
        buffer_tank_volume_supplied,
        feedwater_sources,
        clean_water_pvt_collector_output_temperature,
        clean_water_pvt_electric_power_per_unit,
        renewable_cw_produced,
        required_cw_feedwater_sources,
        thermal_desalination_electric_power_consumed,
    ) = _calculate_renewable_cw_profiles(
        available_converters,
        disable_tqdm,
        end_hour,
        irradiance_data,
        logger,
        minigrid,
        number_of_cw_tanks,
        clean_water_pvt_size,
        scenario,
        start_hour,
        temperature_data,
        wind_speed_data,
    )
    logger.debug(
        "Mean buffer tank temperature: %s",
        np.mean(buffer_tank_temperature.values)
        if buffer_tank_temperature is not None
        else "N/A",
    )
    logger.debug(
        "Soruces of feedwater: %s",
        ", ".join([str(source) for source in feedwater_sources])
        if len(feedwater_sources) > 0
        else "N/A",
    )
    logger.debug(
        "Mean clean-water PV-T electric power per unit: %s",
        np.mean(clean_water_pvt_electric_power_per_unit.values),
    )
    logger.debug(
        "Maximum thermal desalination plant power consumption: %s",
        np.max(thermal_desalination_electric_power_consumed.values),
    )
    logger.debug(
        "Mean thermal desalination plant power consumption: %s",
        np.mean(thermal_desalination_electric_power_consumed.values),
    )

    # Calculate clean-water-related performance profiles.
    clean_water_power_consumed: pd.DataFrame
    renewable_cw_used_directly: pd.DataFrame
    tank_storage_profile: pd.DataFrame
    total_cw_supplied: Optional[pd.DataFrame] = None

    if scenario.desalination_scenario is not None:
        if total_cw_load is None:
            raise Exception(
                f"{BColours.fail}A simulation was run that specified a clean-water "
                + f"load but no clean-water load was passed in.{BColours.endc}"
            )
        # Process the load profile based on the relevant scenario.
        processed_total_cw_load: Optional[pd.DataFrame] = pd.DataFrame(
            compute_processed_load_profile(scenario, total_cw_load)[  # type: ignore
                start_hour:end_hour
            ].values
        )

        if processed_total_cw_load is None:
            logger.error(
                "%sNo processed clean-water load was calculated.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "Failed to calculate the processed total clean-water load profile."
            )

        # Determine the water-tank storage profile.
        (
            clean_water_power_consumed,
            renewable_cw_used_directly,
            tank_storage_profile,
        ) = get_water_storage_profile(
            processed_total_cw_load,
            renewable_cw_produced,
        )
        number_of_buffer_tanks: int = 1
    else:
        clean_water_power_consumed = pd.DataFrame([0] * simulation_hours)
        number_of_buffer_tanks = 0
        processed_total_cw_load = None
        renewable_cw_used_directly = pd.DataFrame([0] * simulation_hours)
        tank_storage_profile = pd.DataFrame([0] * simulation_hours)

    # Calculate hot-water-related profiles.
    processed_total_hw_load: pd.DataFrame
    if scenario.hot_water_scenario is not None:
        if total_hw_load is None:
            raise Exception(
                f"{BColours.fail}A simulation was run that specified a hot-water load "
                + f"but no hot-water load was passed in.{BColours.endc}"
            )
        # Process the load profile based on the relevant scenario.
        processed_total_hw_load = pd.DataFrame(
            compute_processed_load_profile(scenario, total_hw_load)[  # type: ignore
                start_hour:end_hour
            ]
        )
    else:
        number_of_hw_tanks = 0
        processed_total_hw_load = pd.DataFrame([0] * (end_hour - start_hour))

    # Calculate hot-water PV-T related performance profiles.
    hot_water_pump_electric_power_consumed: pd.DataFrame  # pylint: disable=unused-variable
    hot_water_pvt_collector_output_temperature: pd.DataFrame
    hot_water_pvt_electric_power_per_unit: pd.DataFrame
    hot_water_tank_temperature: pd.DataFrame
    hot_water_tank_volume_supplied: pd.DataFrame
    renewable_hw_fraction: pd.DataFrame

    (
        auxiliary_heater,  # pylint: disable=unused-variable
        hot_water_power_consumed,
        hot_water_pvt_collector_output_temperature,
        hot_water_pvt_electric_power_per_unit,
        hot_water_tank_temperature,
        hot_water_tank_volume_supplied,
        renewable_hw_fraction,
    ) = _calculate_renewable_hw_profiles(  # type: ignore
        available_converters,
        disable_tqdm,
        end_hour,
        irradiance_data,
        logger,
        minigrid,
        number_of_hw_tanks,
        processed_total_hw_load,
        hot_water_pvt_size,
        scenario,
        start_hour,
        temperature_data,
        wind_speed_data,
    )
    logger.debug(
        "Mean hot-water tank temperature: %s",
        np.mean(hot_water_tank_temperature.values)
        if hot_water_tank_temperature is not None
        else "N/A",
    )
    logger.debug(
        "Mean hot-water PV-T electric power per unit: %s",
        np.mean(hot_water_pvt_electric_power_per_unit.values),
    )

    # Calculate electricity-related profiles.
    if total_electric_load is None:
        logger.error(
            "No electric load was supplied to the energy_system.run_simulation method "
            "despite this being necessary for the simulation of energy systems."
        )
        raise InternalError(
            "No electric load was supplied to the energy_system.run_simulation method "
            "despite this being necessary for the simulation of energy systems."
        )
    processed_total_electric_load = pd.DataFrame(
        compute_processed_load_profile(scenario, total_electric_load)[  # type: ignore
            start_hour:end_hour
        ].values
        + clean_water_power_consumed.values
        + hot_water_power_consumed.values
        + thermal_desalination_electric_power_consumed.values
    )

    # Compute the electric input profiles.
    battery_storage_profile: pd.DataFrame
    grid_energy: pd.DataFrame
    kerosene_profile: pd.Series
    load_energy: pd.DataFrame
    renewables_energy: pd.DataFrame
    renewables_energy_map: Dict[RenewableEnergySource, pd.DataFrame] = {
        RenewableEnergySource.PV: pv_power_produced,  # type: ignore
        RenewableEnergySource.CLEAN_WATER_PVT: (
            clean_water_pvt_electric_power_per_unit
        ),
        RenewableEnergySource.HOT_WATER_PVT: hot_water_pvt_electric_power_per_unit,
    }
    renewables_energy_used_directly: pd.DataFrame
    (
        battery_storage_profile,
        grid_energy,
        kerosene_profile,
        load_energy,
        renewables_energy,
        renewables_energy_map,
        renewables_energy_used_directly,
    ) = get_electric_battery_storage_profile(
        clean_water_pvt_size=clean_water_pvt_size,
        grid_profile=grid_profile.iloc[start_hour:end_hour, 0],  # type: ignore
        hot_water_pvt_size=hot_water_pvt_size,
        kerosene_usage=kerosene_usage.iloc[start_hour:end_hour, 0],
        location=location,
        logger=logger,
        minigrid=minigrid,
        processed_total_electric_load=processed_total_electric_load,
        renewables_power_produced=renewables_energy_map,
        scenario=scenario,
        end_hour=end_hour,
        pv_size=pv_size,
        start_hour=start_hour,
    )

    if all(renewables_energy.values == 0):
        logger.warning(
            "%sNo renewable electricity was generated. Continuing with grid and diesel "
            "only.%s",
            BColours.warning,
            BColours.endc,
        )

    # Determine the number of households in the community.
    households = pd.DataFrame(
        population_hourly(location)[  # type: ignore
            simulation.start_year
            * HOURS_PER_YEAR : simulation.end_year
            * HOURS_PER_YEAR
        ].values
    )

    # Initialise battery storage parameters
    maximum_battery_energy_throughput: float = (
        electric_storage_size
        * minigrid.battery.cycle_lifetime
        * minigrid.battery.storage_unit
    )
    initial_battery_storage: float = (
        electric_storage_size
        * minigrid.battery.maximum_charge
        * minigrid.battery.storage_unit
    )
    maximum_battery_storage: float = (
        electric_storage_size
        * minigrid.battery.maximum_charge
        * minigrid.battery.storage_unit
    )
    minimum_battery_storage: float = (
        electric_storage_size
        * minigrid.battery.minimum_charge
        * minigrid.battery.storage_unit
    )
    cumulative_battery_storage_power: float = 0.0
    hourly_battery_storage: Dict[int, float] = {}
    new_hourly_battery_storage: float = 0.0
    battery_health: Dict[int, float] = {}

    # @BenWinchester - Re-order this calculation to use CW and HW power consumed.
    # Initialise tank storage parameters
    (
        hourly_cw_tank_storage,
        initial_cw_tank_storage,
        maximum_cw_tank_storage,
        minimum_cw_tank_storage,
        clean_water_power_consumed_mapping,
    ) = _setup_tank_storage_profiles(
        logger,
        number_of_cw_tanks,
        clean_water_power_consumed,
        ResourceType.CLEAN_WATER,
        scenario,
        minigrid.clean_water_tank,
    )

    (
        hourly_hw_tank_storage,  # pylint: disable=unused-variable
        initial_hw_tank_storage,  # pylint: disable=unused-variable
        maximum_hw_tank_storage,  # pylint: disable=unused-variable
        minimum_hw_tank_storage,  # pylint: disable=unused-variable
        hot_water_power_consumed_mapping,  # pylint: disable=unused-variable
    ) = _setup_tank_storage_profiles(
        logger,
        number_of_hw_tanks,
        hot_water_power_consumed,
        ResourceType.HOT_CLEAN_WATER,
        scenario,
        minigrid.hot_water_tank,
    )

    # Initialise electric desalination paramteters.
    (
        _,
        energy_per_desalinated_litre,
        maximum_water_throughput,
    ) = _calculate_electric_desalination_parameters(
        available_converters, feedwater_sources, logger, scenario
    )

    # Intialise tank accounting parameters
    backup_desalinator_water_supplied: Dict[int, float] = {}
    clean_water_demand_met_by_excess_energy: Dict[int, float] = {}
    clean_water_supplied_by_excess_energy: Dict[int, float] = {}
    conventional_water_supplied: Dict[int, float] = {}
    excess_energy_used_desalinating: Dict[int, float] = {}
    storage_water_supplied: Dict[int, float] = {}
    water_surplus: Dict[int, float] = {}
    # water_deficit: List[float] = []

    # Initialise energy accounting parameters
    energy_surplus: Optional[Dict[int, float]] = {}
    energy_deficit: Optional[Dict[int, float]] = {}
    storage_power_supplied: Dict[int, float] = {}

    # Do not do the itteration if no storage is being used
    if electric_storage_size == 0:
        energy_surplus = None
        energy_deficit = None
    # Carry out the itteration if there is some storage involved in the system.
    else:
        # Begin simulation, iterating over timesteps
        for t in tqdm(
            range(int(battery_storage_profile.size)),
            desc="hourly computation",
            disable=disable_tqdm,
            leave=False,
            unit="hour",
        ):
            # Calculate the electric iteration.
            (
                battery_energy_flow,
                excess_energy,
                new_hourly_battery_storage,
            ) = battery_iteration_step(
                battery_storage_profile,
                hourly_battery_storage,
                initial_battery_storage,
                logger,
                maximum_battery_storage,
                minigrid,
                minimum_battery_storage,
                time_index=t,
            )

            # Calculate the hot-water iteration.

            # Calculate the clean-water iteration.
            excess_energy = cw_tank_iteration_step(
                backup_desalinator_water_supplied,
                clean_water_power_consumed_mapping,
                clean_water_demand_met_by_excess_energy,
                clean_water_supplied_by_excess_energy,
                conventional_cw_source_profiles,
                conventional_water_supplied,
                energy_per_desalinated_litre,
                excess_energy,
                excess_energy_used_desalinating,
                hourly_cw_tank_storage,
                initial_cw_tank_storage,
                logger,
                maximum_battery_storage,
                maximum_cw_tank_storage,
                maximum_water_throughput,
                minigrid,
                minimum_cw_tank_storage,
                new_hourly_battery_storage,
                scenario,
                storage_water_supplied,
                tank_storage_profile,
                time_index=t,
            )

            # Dumped energy and unmet demand
            energy_surplus[t] = excess_energy  # type: ignore
            energy_deficit[t] = max(  # type: ignore
                minimum_battery_storage - new_hourly_battery_storage, 0.0
            )  # Battery too empty

            # Battery capacities and blackouts (if battery is too full or empty)
            new_hourly_battery_storage = min(
                new_hourly_battery_storage, maximum_battery_storage
            )
            new_hourly_battery_storage = max(
                new_hourly_battery_storage, minimum_battery_storage
            )

            # Update hourly_battery_storage
            hourly_battery_storage[t] = new_hourly_battery_storage

            # Update battery health
            (
                cumulative_battery_storage_power,
                maximum_battery_storage,
                minimum_battery_storage,
            ) = _update_battery_health(
                battery_energy_flow,
                battery_health,
                cumulative_battery_storage_power,
                electric_storage_size,
                hourly_battery_storage,
                maximum_battery_energy_throughput,
                minigrid,
                storage_power_supplied,
                time_index=t,
            )
    # Process the various outputs into dataframes.
    # energy_deficit_frame: pd.DataFrame = dict_to_dataframe(energy_deficit)
    if energy_surplus is not None:
        energy_surplus_frame: pd.DataFrame = dict_to_dataframe(energy_surplus, logger)
    else:
        energy_surplus_frame = pd.DataFrame([0] * (end_hour - start_hour))

    if scenario.battery and electric_storage_size > 0:
        battery_health_frame: pd.DataFrame = dict_to_dataframe(battery_health, logger)
        hourly_battery_storage_frame: pd.DataFrame = dict_to_dataframe(
            hourly_battery_storage, logger
        )
        storage_power_supplied_frame: pd.DataFrame = dict_to_dataframe(
            storage_power_supplied, logger
        )
    else:
        battery_health_frame = pd.DataFrame([0] * (end_hour - start_hour))
        hourly_battery_storage_frame = pd.DataFrame([0] * (end_hour - start_hour))
        storage_power_supplied_frame = pd.DataFrame([0] * (end_hour - start_hour))

    if scenario.desalination_scenario is not None:
        backup_desalinator_water_frame: pd.DataFrame = dict_to_dataframe(
            backup_desalinator_water_supplied, logger
        )
        clean_water_demand_met_by_excess_energy_frame: pd.DataFrame = dict_to_dataframe(
            clean_water_demand_met_by_excess_energy, logger
        )
        clean_water_power_consumed = dict_to_dataframe(
            clean_water_power_consumed_mapping, logger
        )
        clean_water_supplied_by_excess_energy_frame: pd.DataFrame = dict_to_dataframe(
            clean_water_supplied_by_excess_energy, logger
        )
        conventional_cw_supplied_frame: pd.DataFrame = dict_to_dataframe(
            conventional_water_supplied, logger
        )
        excess_energy_used_desalinating_frame: pd.DataFrame = dict_to_dataframe(
            excess_energy_used_desalinating, logger
        )
        if hourly_cw_tank_storage is None:
            logger.error(
                "%sNo clean-water tank storage level information was outputted from "
                "the simulation despite non-`None` information being expected.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "Clean-water tank storage information not computed successfully."
            )
        hourly_cw_tank_storage_frame: pd.DataFrame = dict_to_dataframe(
            hourly_cw_tank_storage, logger
        )
        storage_water_supplied_frame: pd.DataFrame = dict_to_dataframe(
            storage_water_supplied, logger
        )
        water_surplus_frame: pd.DataFrame = dict_to_dataframe(water_surplus, logger)

    # Find unmet energy
    unmet_energy = pd.DataFrame(
        (
            load_energy.values
            + thermal_desalination_electric_power_consumed.values
            + -renewables_energy_used_directly.values
            - grid_energy.values
            - storage_power_supplied_frame.values
        )
    )
    if thermal_desalination_electric_power_consumed is not None:
        unmet_energy = pd.DataFrame(
            (unmet_energy.values + thermal_desalination_electric_power_consumed.values)
        )

    # Determine the times for which the system experienced a blackout.
    blackout_times = ((unmet_energy > 0) * 1).astype(float)

    # Use backup diesel generator if present
    diesel_energy: pd.DataFrame
    diesel_fuel_usage: pd.DataFrame
    diesel_times: pd.DataFrame
    if scenario.diesel_scenario.mode in (DieselMode.BACKUP, DieselMode.BACKUP_UNMET):
        (
            diesel_capacity,
            diesel_energy,
            diesel_fuel_usage,
            diesel_times,
            unmet_energy,
        ) = _calculate_backup_diesel_generator_usage(
            blackout_times,
            minigrid,
            scenario,
            float(np.sum(processed_total_electric_load)),
            unmet_energy,
        )
    elif scenario.diesel_scenario.mode == DieselMode.CYCLE_CHARGING:
        logger.error(
            "%sCycle charing is not currently supported.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InputFileError(
            "scenario inputs", "Cycle charing is not currently supported."
        )
    elif scenario.diesel_scenario.mode == DieselMode.DISABLED:
        diesel_energy = pd.DataFrame([0.0] * int(battery_storage_profile.size))
        diesel_times = pd.DataFrame([0.0] * int(battery_storage_profile.size))
        diesel_fuel_usage = pd.DataFrame([0.0] * int(battery_storage_profile.size))
        diesel_capacity = 0.0
    else:
        logger.error(
            "%sDiesel mode must be specified. Valid modes are %s.%s",
            BColours.fail,
            ", ".join({e.value for e in DieselMode}),
            BColours.endc,
        )
        raise InputFileError(
            "scenario inputs", "Diesel mode must be specified in the scenario file."
        )

    # Find new blackout times, according to when there is unmet energy
    blackout_times = ((unmet_energy > 0) * 1).astype(float)
    # Ensure all unmet energy is calculated correctly, removing any negative values
    unmet_energy = ((unmet_energy > 0) * unmet_energy).abs()  # type: ignore
    # Ensure all unmet clean-water energy is considered.
    clean_water_power_consumed = clean_water_power_consumed.mul(  # type: ignore
        1 - blackout_times
    )
    thermal_desalination_electric_power_consumed = (
        thermal_desalination_electric_power_consumed.mul(  # type: ignore
            1 - blackout_times
        )
    )

    # Find how many kerosene lamps are in use
    kerosene_usage = pd.DataFrame(
        blackout_times.loc[:, 0].mul(kerosene_profile.values)  # type: ignore
    )
    kerosene_mitigation = pd.DataFrame(
        (1 - blackout_times).loc[:, 0].mul(kerosene_profile.values)  # type: ignore
    )

    if scenario.desalination_scenario is not None:
        # Compute the amount of time for which the backup water was able to operate.
        backup_desalinator_water_frame = backup_desalinator_water_frame.mul(  # type: ignore
            1 - blackout_times
        )

        # Find total energy used by the system
        total_energy_used = pd.DataFrame(
            renewables_energy_used_directly.values
            + storage_power_supplied_frame.values
            + grid_energy.values
            + diesel_energy.values
            + excess_energy_used_desalinating_frame.values
        )

        power_used_on_electricity = (
            total_energy_used
            - excess_energy_used_desalinating_frame  # type: ignore
            - clean_water_power_consumed  # type: ignore
            - thermal_desalination_electric_power_consumed  # type: ignore
            - hot_water_power_consumed  # type: ignore
        )

        # Compute the outputs from the itteration stage
        total_cw_supplied: pd.DataFrame = pd.DataFrame(  # type: ignore
            renewable_cw_used_directly.values
            + storage_water_supplied_frame.values
            + backup_desalinator_water_frame.values
            + clean_water_supplied_by_excess_energy_frame.values
            + conventional_cw_supplied_frame.values
        ).mul((1 - blackout_times))

        water_surplus_frame = (  # type: ignore
            (total_cw_supplied - processed_total_cw_load) > 0  # type: ignore
        ) * (
            total_cw_supplied - processed_total_cw_load  # type: ignore
        )

        total_cw_used = total_cw_supplied - water_surplus_frame  # type: ignore

        # Compute when the water demand went unmet.
        # NOTE: This is manually handled to be non-`None`.
        if processed_total_cw_load is None:
            raise InternalError("Processed clean-water load was `None` unexpectedly.")
        unmet_clean_water = pd.DataFrame(
            processed_total_cw_load.values - total_cw_supplied.values  # type: ignore
        )
        unmet_clean_water = unmet_clean_water * (unmet_clean_water > 0)  # type: ignore

        # Convert the PV-T units to kWh.
        if minigrid.pvt_panel is None:
            raise InternalError("Minigrid has no PV-T panel present.")
        clean_water_pvt_electric_power_per_kwh: pd.DataFrame = (
            clean_water_pvt_electric_power_per_unit  # type: ignore
            / minigrid.pvt_panel.pv_unit
        )

        # Find the new clean-water blackout times, according to when there is unmet
        # demand
        clean_water_blackout_times = ((unmet_clean_water > 0) * 1).astype(float)

        # Clean-water system performance outputs
        backup_desalinator_water_frame.columns = pd.Index(
            [ColumnHeader.CLEAN_WATER_FROM_PRIORITISATION.value]
        )
        clean_water_blackout_times.columns = pd.Index(
            [ColumnHeader.CLEAN_WATER_BLACKOUTS.value]
        )
        clean_water_demand_met_by_excess_energy_frame.columns = pd.Index(
            [ColumnHeader.CLEAN_WATER_FROM_EXCESS_ELECTRICITY]  # type: ignore
        )
        clean_water_power_consumed.columns = pd.Index(
            [ColumnHeader.POWER_CONSUMED_BY_DESALINATION.value]
        )
        clean_water_supplied_by_excess_energy_frame.columns = pd.Index(
            [ColumnHeader.CLEAN_WATER_FROM_EXCESS_ELECTRICITY.value]
        )
        conventional_cw_supplied_frame.columns = pd.Index(
            [ColumnHeader.CLEAN_WATER_FROM_CONVENTIONAL_SOURCES.value]
        )
        excess_energy_used_desalinating_frame.columns = pd.Index(
            [ColumnHeader.EXCESS_POWER_CONSUMED_BY_DESALINATION.value]
        )
        hourly_cw_tank_storage_frame.columns = pd.Index(
            [ColumnHeader.CW_TANK_STORAGE_PROFILE.value]
        )
        processed_total_cw_load.columns = pd.Index([ColumnHeader.TOTAL_CW_LOAD.value])
        power_used_on_electricity.columns = pd.Index(
            [ColumnHeader.POWER_CONSUMED_BY_ELECTRIC_DEVICES.value]
        )
        renewable_cw_produced.columns = pd.Index(
            [ColumnHeader.CLEAN_WATER_FROM_RENEWABLES.value]
        )
        renewable_cw_used_directly.columns = pd.Index(
            [ColumnHeader.RENEWABLE_CW_USED_DIRECTLY.value]
        )
        storage_water_supplied_frame.columns = pd.Index(
            [ColumnHeader.CLEAN_WATER_FROM_STORAGE.value]
        )
        total_cw_used.columns = pd.Index([ColumnHeader.TOTAL_CW_CONSUMED.value])
        total_cw_supplied.columns = pd.Index(  # type: ignore
            [ColumnHeader.TOTAL_CW_SUPPLIED.value]
        )
        unmet_clean_water.columns = pd.Index([ColumnHeader.UNMET_CLEAN_WATER.value])
        water_surplus_frame.columns = pd.Index([ColumnHeader.WATER_SURPLUS.value])

        if scenario.pv_t:
            if buffer_tank_temperature is None:
                logger.error(
                    "%sInternal error: buffer tank temperature was None despite buffer "
                    "tanks being present.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise InternalError(
                    "Buffer tank temperature was expected but was `None`."
                )
            buffer_tank_temperature.columns = pd.Index(
                [ColumnHeader.BUFFER_TANK_TEMPERATURE.value]
            )
            buffer_tank_volume_supplied.columns = pd.Index(
                [ColumnHeader.BUFFER_TANK_OUTPUT.value]
            )
            if clean_water_pvt_collector_output_temperature is None:
                logger.error(
                    "%sInternal error: PV-T output temperature was None despite PV-T "
                    "being present.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise InternalError(
                    "PV-T output temperature was expected but was `None`."
                )
            clean_water_pvt_collector_output_temperature.columns = pd.Index(
                [ColumnHeader.CW_PVT_OUTPUT_TEMPERATURE.value]
            )
            clean_water_pvt_electric_power_per_kwh.columns = pd.Index(
                [ColumnHeader.CW_PVT_ELECTRICITY_SUPPLIED_PER_KWP.value]
            )
            thermal_desalination_electric_power_consumed.columns = pd.Index(
                [ColumnHeader.POWER_CONSUMED_BY_THERMAL_DESALINATION.value]
            )

    else:
        # Find total energy used by the system
        total_energy_used = pd.DataFrame(
            renewables_energy_used_directly.values
            + storage_power_supplied_frame.values
            + grid_energy.values
            + diesel_energy.values
        )

    if scenario.hot_water_scenario is not None:
        # Process any errors.
        if hot_water_tank_temperature is None:
            raise InternalError("Hot-water tank temperature undefined.")
        if hot_water_pvt_collector_output_temperature is None:
            raise InternalError("Hot-water PV-T output temperature undefined.")
        if minigrid.pvt_panel is None:
            raise InternalError("PV-T panel not defined.")

        # Convert the PV-T units to kWh.
        hot_water_pvt_electric_power_per_kwh: pd.DataFrame = pd.DataFrame(
            hot_water_pvt_electric_power_per_unit  # type: ignore
            / minigrid.pvt_panel.pv_unit
        )
        hot_water_power_consumed.columns = pd.Index(
            [ColumnHeader.POWER_CONSUMED_BY_HOT_WATER.value]
        )

        # Add headers to the columns.
        hot_water_power_consumed.columns = pd.Index(
            [ColumnHeader.POWER_CONSUMED_BY_HOT_WATER.value]
        )
        hot_water_pvt_collector_output_temperature.columns = pd.Index(
            [ColumnHeader.HW_PVT_OUTPUT_TEMPERATURE.value]
        )
        hot_water_pvt_electric_power_per_kwh.columns = pd.Index(
            [ColumnHeader.HW_PVT_ELECTRICITY_SUPPLIED_PER_KWP.value]
        )
        hot_water_tank_temperature.columns = pd.Index(
            [ColumnHeader.HW_TANK_TEMPERATURE.value]
        )
        hot_water_tank_volume_supplied.columns = pd.Index(
            [ColumnHeader.HW_TANK_OUTPUT.value]
        )
        processed_total_hw_load.columns = pd.Index([ColumnHeader.TOTAL_HW_LOAD.value])
        renewable_hw_fraction.columns = pd.Index(
            [ColumnHeader.HW_RENEWABLES_FRACTION.value]
        )

    # System performance outputs
    battery_health_frame.columns = pd.Index([ColumnHeader.BATTERY_HEALTH.value])
    blackout_times.columns = pd.Index([ColumnHeader.BLACKOUTS.value])
    diesel_fuel_usage.columns = pd.Index([ColumnHeader.DIESEL_FUEL_USAGE.value])
    diesel_times.columns = pd.Index([ColumnHeader.DIESEL_GENERATOR_TIMES.value])
    energy_surplus_frame.columns = pd.Index([ColumnHeader.DUMPED_ELECTRICITY.value])
    hourly_battery_storage_frame.columns = pd.Index(
        [ColumnHeader.HOURLY_STORAGE_PROFILE.value]
    )
    households.columns = pd.Index([ColumnHeader.HOUSEHOLDS.value])
    diesel_energy.columns = pd.Index([ColumnHeader.DIESEL_ENERGY_SUPPLIED.value])
    kerosene_mitigation.columns = pd.Index([ColumnHeader.KEROSENE_MITIGATION.value])
    kerosene_usage.columns = pd.Index([ColumnHeader.KEROSENE_LAMPS.value])
    storage_power_supplied_frame.columns = pd.Index(
        [ColumnHeader.ELECTRICITY_FROM_STORAGE.value]
    )
    total_energy_used.columns = pd.Index(
        [ColumnHeader.TOTAL_ELECTRICITY_CONSUMED.value]
    )
    unmet_energy.columns = pd.Index([ColumnHeader.UNMET_ELECTRICITY.value])

    # System details
    system_details = SystemDetails(
        diesel_capacity,
        simulation.end_year,
        {
            converter.name: available_converters.count(converter)
            for converter in available_converters
        },
        clean_water_pvt_size
        * float(
            solar_degradation(minigrid.pvt_panel.lifetime, location.max_years).iloc[
                HOURS_PER_YEAR * (simulation.end_year - simulation.start_year), 0
            ]
        )
        if minigrid.pvt_panel is not None and scenario.desalination_scenario is not None
        else None,
        hot_water_pvt_size
        * float(
            solar_degradation(minigrid.pvt_panel.lifetime, location.max_years).iloc[
                HOURS_PER_YEAR * (simulation.end_year - simulation.start_year), 0
            ]
        )
        if minigrid.pvt_panel is not None and scenario.hot_water_scenario is not None
        else None,
        number_of_buffer_tanks if scenario.desalination_scenario is not None else None,
        number_of_cw_tanks if scenario.desalination_scenario is not None else None,
        number_of_hw_tanks if scenario.hot_water_scenario is not None else None,
        pv_size
        * float(
            solar_degradation(minigrid.pv_panel.lifetime, location.max_years).iloc[
                HOURS_PER_YEAR * (simulation.end_year - simulation.start_year), 0
            ]
        ),
        float(
            electric_storage_size
            * minigrid.battery.storage_unit
            * np.min(battery_health_frame[ColumnHeader.BATTERY_HEALTH.value])
        ),
        {
            converter.name: available_converters.count(converter)
            for converter in available_converters
        },
        clean_water_pvt_size
        if minigrid.pvt_panel is not None and scenario.desalination_scenario is not None
        else None,
        hot_water_pvt_size
        if minigrid.pvt_panel is not None and scenario.hot_water_scenario is not None
        else None,
        number_of_buffer_tanks if scenario.desalination_scenario is not None else None,
        number_of_cw_tanks if scenario.desalination_scenario is not None else None,
        number_of_hw_tanks if scenario.hot_water_scenario is not None else None,
        pv_size,
        float(electric_storage_size * minigrid.battery.storage_unit),
        [source.name for source in required_cw_feedwater_sources]
        if len(required_cw_feedwater_sources) > 0
        else None,
        simulation.start_year,
    )

    # Separate out the various renewable inputs.
    pv_energy = renewables_energy_map[RenewableEnergySource.PV]
    clean_water_pvt_energy = renewables_energy_map[
        RenewableEnergySource.CLEAN_WATER_PVT
    ]
    hot_water_pvt_energy = renewables_energy_map[RenewableEnergySource.HOT_WATER_PVT]
    total_pvt_energy = pd.DataFrame(
        clean_water_pvt_energy.values + hot_water_pvt_energy.values
    )
    total_pvt_energy.columns = pd.Index(
        [ColumnHeader.TOTAL_PVT_ELECTRICITY_SUPPLIED.value]
    )

    # End simulation timer
    timer_end = datetime.datetime.now()
    time_delta = timer_end - timer_start

    # Return all outputs
    system_performance_outputs_list = [
        load_energy,
        total_energy_used,
        unmet_energy,
        blackout_times,
        renewables_energy_used_directly,
        storage_power_supplied_frame,
        grid_energy,
        diesel_energy,
        diesel_times,
        diesel_fuel_usage,
        battery_storage_profile,
        pv_energy,
        renewables_energy,
        hourly_battery_storage_frame,
        energy_surplus_frame,
        battery_health_frame,
        households,
        kerosene_usage,
        kerosene_mitigation,
    ]

    if (
        scenario.desalination_scenario is not None
        or scenario.hot_water_scenario is not None
    ):
        system_performance_outputs_list.append(total_pvt_energy)
    if scenario.desalination_scenario is not None:
        desalination_performance_outputs: List[Optional[pd.DataFrame]] = [
            backup_desalinator_water_frame,
            clean_water_blackout_times,
            clean_water_demand_met_by_excess_energy_frame,
            clean_water_power_consumed,
            clean_water_supplied_by_excess_energy_frame,
            conventional_cw_supplied_frame,
            excess_energy_used_desalinating_frame,
            hourly_cw_tank_storage_frame,
            power_used_on_electricity,
            processed_total_cw_load,
            renewable_cw_produced,
            renewable_cw_used_directly,
            storage_water_supplied_frame,
            total_cw_supplied,
            total_cw_used,
            unmet_clean_water,
            water_surplus_frame,
        ]

        if any(entry is None for entry in desalination_performance_outputs):
            logger.error(
                "%sError saving desalination outputs, simulation returned `None` as "
                "outputs despite non-`None` outputs being expected.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "Some outputs of the simulation were returned as `None` for "
                "desalination related outputs despite non-`None` outputs being "
                "expected."
            )

        system_performance_outputs_list.extend(
            desalination_performance_outputs  # type: ignore
        )

        if scenario.pv_t:
            clean_water_performance_outputs: List[Optional[pd.DataFrame]] = [
                buffer_tank_temperature,
                buffer_tank_volume_supplied,
                clean_water_pvt_collector_output_temperature,
                clean_water_pvt_electric_power_per_kwh,
                clean_water_pvt_energy,
                thermal_desalination_electric_power_consumed,
            ]

            if any(entry is None for entry in clean_water_performance_outputs):
                logger.error(
                    "%sError saving clean-water outputs, simulation returned `None` as "
                    "outputs despite non-`None` outputs being expected.%s",
                    BColours.fail,
                    BColours.endc,
                )
                raise InternalError(
                    "Some outputs of the simulation were returned as `None` for "
                    "clean-water related outputs despite non-`None` outputs being "
                    "expected."
                )

            system_performance_outputs_list.extend(
                clean_water_performance_outputs  # type: ignore
            )

    if scenario.hot_water_scenario is not None:
        hot_water_performance_outputs: List[Optional[pd.DataFrame]] = [
            hot_water_power_consumed,
            hot_water_pvt_collector_output_temperature,
            hot_water_pvt_electric_power_per_kwh,
            hot_water_pvt_electric_power_per_unit,
            hot_water_pvt_energy,
            hot_water_tank_temperature,
            hot_water_tank_volume_supplied,
            processed_total_hw_load,
            renewable_hw_fraction,
        ]

        if any(entry is None for entry in hot_water_performance_outputs):
            logger.error(
                "%sError saving hot-water outputs, simulation returned `None` as "
                "outputs despite non-`None` outputs being expected.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError(
                "Some outputs of the simulation were returned as `None` for hot-water "
                "related outputs despite non-`None` outputs being expected."
            )

        system_performance_outputs_list.extend(
            hot_water_performance_outputs  # type: ignore
        )

    system_performance_outputs = pd.concat(
        system_performance_outputs_list,
        axis=1,
    )

    return time_delta, system_performance_outputs, system_details


#     def lifetime_simulation(self, optimisation_report):
#         """
#         Simulates a minigrid over its lifetime.

#         Simulates a minigrid system over the course of its lifetime to get the complete
#         technical performance of the system

#         Inputs:
#             - optimisation_report:
#                 Report of outputs from Optimisation().multiple_optimisation_step()

#         Outputs:
#             - lifetime_output:
#                 The lifetime technical performance of the system

#         """
#         # Initialise
#         optimisation_report = optimisation_report.reset_index(drop=True)
#         lifetime_output = pd.DataFrame([])
#         simulation_periods = np.size(optimisation_report, 0)
#         # Iterate over all simulation periods
#         for sim in range(simulation_periods):
#             system_performance_outputs = self.simulation(
#                 start_year=int(optimisation_report["Start year"][sim]),
#                 end_year=int(optimisation_report["End year"][sim]),
#                 pv_size=float(optimisation_report["Initial PV size"][sim]),
#                 electric_storage_size=float(
#                     optimisation_report["Initial storage size"][sim]
#                 ),
#             )
#             lifetime_output = pd.concat(
#                 [lifetime_output, system_performance_outputs[0]], axis=0
#             )
#         return lifetime_output.reset_index(drop=True)

#     #%%
#     # =============================================================================
#     # ENERGY BALANCE FUNCTIONS
#     #       These functions identify the sources and uses of energy in the system,
#     #       such as generation, loads and the overall balance
#     # =============================================================================
#     #%% Energy balance

#     #%% Energy usage
