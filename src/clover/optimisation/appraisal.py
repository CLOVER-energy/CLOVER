#!/usr/bin/python3
########################################################################################
# appraisal.py - Optimisation appraisal module.                                        #
#                                                                                      #
# Authors: Phil Sandwell, Ben Winchester                                               #
# Copyright: Phil Sandwell, 2018                                                       #
# License: Open source                                                                 #
# Most recent update: 05/08/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
appraisal.py - The optimisation appraisal module of CLOVER.

In order to compare and evaluate energy systems, appraisals of their performance need to
be carried out. This module exposes methods to appraise the results of CLOVER
simulations.

"""

import collections
from logging import Logger
from typing import Any, Dict, Optional, Tuple

import numpy as np  # pylint: disable=import-error
import pandas as pd

from ..impact import finance, ghgs

from ..__utils__ import (
    AuxiliaryHeaterType,
    BColours,
    ColumnHeader,
    Criterion,
    CumulativeResults,
    EnvironmentalAppraisal,
    FinancialAppraisal,
    HEAT_CAPACITY_OF_WATER,
    InternalError,
    ProgrammerJudgementFault,
    ResourceType,
    Scenario,
    hourly_profile_to_daily_sum,
    Location,
    SystemAppraisal,
    SystemDetails,
    TechnicalAppraisal,
    WasteProduct,
)
from ..conversion.conversion import Converter
from ..impact.__utils__ import ImpactingComponent, update_diesel_costs

__all__ = ("appraise_system",)


def _calculate_power_consumed_fraction(
    simulation_results: pd.DataFrame,
    total_electricity_consumed: float,
) -> Dict[ResourceType, float]:
    """
    Calculates the electric power consumed by each resource type.

    Inputs:
        - simulation_results:
            Outputs of Energy_System().simulation(...)
        - total_electricity_consumed:
            The total electricity consumed by the system.

    Outputs:
        - A mapping between :class:`ResourceType` and the electricity consumed by that
          particular subsystem.

    """

    power_consumed_fraction: Dict[ResourceType, float] = collections.defaultdict(float)
    if ColumnHeader.POWER_CONSUMED_BY_DESALINATION.value in simulation_results:
        total_clean_water_power_consumed = np.sum(
            simulation_results[  # type: ignore
                ColumnHeader.POWER_CONSUMED_BY_DESALINATION.value
            ]
        )
        power_consumed_fraction[ResourceType.CLEAN_WATER] = (
            total_clean_water_power_consumed / total_electricity_consumed
        )

    if ColumnHeader.POWER_CONSUMED_BY_HOT_WATER.value in simulation_results:
        total_hot_water_power_consumed_fraction = np.sum(
            simulation_results[  # type: ignore
                ColumnHeader.POWER_CONSUMED_BY_HOT_WATER.value
            ]
        )
        power_consumed_fraction[ResourceType.HOT_CLEAN_WATER] = (
            total_hot_water_power_consumed_fraction / total_electricity_consumed
        )

    if ColumnHeader.POWER_CONSUMED_BY_ELECTRIC_DEVICES.value in simulation_results:
        total_electricity_power_consumed_fraction = np.sum(
            simulation_results[  # type: ignore
                ColumnHeader.POWER_CONSUMED_BY_ELECTRIC_DEVICES.value
            ]
        )
        power_consumed_fraction[ResourceType.ELECTRIC] = (
            total_electricity_power_consumed_fraction / total_electricity_consumed
        )
    # If no other resource types consumed electricity, then all was consumed by electric
    # devices.
    elif (
        ColumnHeader.POWER_CONSUMED_BY_DESALINATION.value not in simulation_results
        and ColumnHeader.POWER_CONSUMED_BY_HOT_WATER.value not in simulation_results
    ):
        power_consumed_fraction[ResourceType.ELECTRIC] = 1

    return power_consumed_fraction


def _simulation_cumulative_results(  # pylint: disable=too-many-locals
    environmental_appraisal: EnvironmentalAppraisal,
    financial_appraisal: FinancialAppraisal,
    logger: Logger,
    previous_system: SystemAppraisal,
    technical_appraisal: TechnicalAppraisal,
) -> CumulativeResults:
    """
    Calculates cumulative results about the system.

    Inputs:
        - environmental_appraisal:
            The :class:`EnvironmentalAppraisal` carried out on the system.
        - financial_appraisal:
            The :class:`FinancialAppraisal` carried out on the system.
        - logger:
            The logger for the run.
        - previous_system:
            Information about the previous system that was simulated.
        - technical_appraisal:
            The :class:`TechnicalAppraisal` carried out on the system.

    Outputs:
        - Cumulative information as a :class:`CumulativeResults` instance.

    """

    # Compute the cumulative waste products.
    cumulative_brine: float = (
        (
            environmental_appraisal.total_brine
            + previous_system.cumulative_results.waste_produced[WasteProduct.BRINE]
        )
        if environmental_appraisal.total_brine is not None
        else 0
    )
    cumulative_waste_produced = {WasteProduct.BRINE: cumulative_brine}

    # Compute the cumulative useful products.
    if (
        previous_system.cumulative_results.clean_water > 0
        and technical_appraisal.total_clean_water is not None
    ):
        cumulative_clean_water: float = (
            technical_appraisal.total_clean_water
            + previous_system.cumulative_results.clean_water
        )
    else:
        logger.debug("No clean water produced.")
        cumulative_clean_water = 0

    cumulative_electricity = (
        technical_appraisal.total_electricity_consumed
        + previous_system.cumulative_results.electricity
    )

    cumulative_energy = (
        technical_appraisal.total_energy_consumed
        + previous_system.cumulative_results.energy
    )

    if (
        previous_system.cumulative_results.hot_water > 0
        and technical_appraisal.total_hot_water is not None
    ):
        cumulative_hot_water: float = (
            technical_appraisal.total_hot_water
            + previous_system.cumulative_results.hot_water
        )
    else:
        logger.debug("No hot water produced.")
        cumulative_hot_water = 0

    if (
        previous_system.cumulative_results.heating > 0
        and technical_appraisal.total_heating_consumed is not None
    ):
        cumulative_heating: float = (
            technical_appraisal.total_heating_consumed
            + previous_system.cumulative_results.heating
        )
    else:
        logger.debug("No hot water produced.")
        cumulative_heating = 0

    # Compute the cumulative financial information.
    cumulative_costs = (
        financial_appraisal.total_cost + previous_system.cumulative_results.cost
    )
    cumulative_discounted_clean_water = (
        technical_appraisal.discounted_clean_water
        if technical_appraisal.discounted_clean_water is not None
        else 0
    ) + previous_system.cumulative_results.discounted_clean_water
    cumulative_discounted_electricity = (
        technical_appraisal.discounted_electricity
        + previous_system.cumulative_results.discounted_electricity
    )
    cumulative_discounted_energy = (
        technical_appraisal.discounted_energy
        + previous_system.cumulative_results.discounted_energy
    )
    cumulative_discounted_heating = (
        technical_appraisal.discounted_heating
        if technical_appraisal.discounted_heating is not None
        else 0
    ) + previous_system.cumulative_results.discounted_heating
    cumulative_discounted_hot_water = (
        technical_appraisal.discounted_hot_water
        if technical_appraisal.discounted_hot_water is not None
        else 0
    ) + previous_system.cumulative_results.discounted_hot_water
    cumulative_subsystem_costs = {
        resource_type: cost
        + (
            previous_system.cumulative_results.subsystem_costs[resource_type]
            if previous_system.cumulative_results.subsystem_costs is not None
            else 0
        )
        for resource_type, cost in financial_appraisal.subsystem_costs.items()
    }
    cumulative_system_costs = (
        financial_appraisal.total_system_cost
        + previous_system.cumulative_results.system_cost
    )

    # Compute the cumulative emissions information.
    cumulative_ghgs = (
        environmental_appraisal.total_ghgs + previous_system.cumulative_results.ghgs
    )
    cumulative_subsystem_ghgs = {
        resource_type: ghgs
        + (
            previous_system.cumulative_results.subsystem_ghgs[resource_type]
            if previous_system.cumulative_results.subsystem_ghgs is not None
            else 0
        )
        for resource_type, ghgs in environmental_appraisal.subsystem_ghgs.items()
    }
    cumulative_system_ghgs = (
        environmental_appraisal.total_system_ghgs
        + previous_system.cumulative_results.system_ghgs
    )

    # Format outputs
    return CumulativeResults(
        cumulative_clean_water,
        cumulative_costs,
        cumulative_discounted_clean_water,
        cumulative_discounted_electricity,
        cumulative_discounted_energy,
        cumulative_discounted_heating,
        cumulative_discounted_hot_water,
        cumulative_electricity,
        cumulative_energy,
        cumulative_ghgs,
        cumulative_heating,
        cumulative_hot_water,
        cumulative_subsystem_costs,
        cumulative_subsystem_ghgs,
        cumulative_system_costs,
        cumulative_system_ghgs,
        cumulative_waste_produced,
    )


def _simulation_environmental_appraisal(  # pylint: disable=too-many-locals
    buffer_tank_addition: int,
    clean_water_tank_addition: int,
    converter_addition: Dict[Converter, int],
    diesel_addition: float,
    electric_yearly_load_statistics: pd.DataFrame,
    end_year: int,
    ghg_inputs: Dict[str, Any],
    heat_exchanger_addition: int,
    hot_water_tank_addition: int,
    location: Location,
    logger: Logger,
    pv_addition: float,
    pvt_addition: float,
    scenario: Scenario,
    simulation_results: pd.DataFrame,
    start_year: int,
    storage_addition: float,
    system_details: SystemDetails,
    technical_appraisal: TechnicalAppraisal,
) -> EnvironmentalAppraisal:
    """
    Appraises the environmental impact of a minigrid system

    Inputs:
        - buffer_tank_addition:
            The additional number of buffer tanks added this iteration.
        - clean_water_tank_addition:
            The additional number of clean-water tanks added this iteration.
        - converter_addition:
            A mapping between converter names and the size of each that was added to the
            system this iteration.
        - diesel_addition:
            The additional diesel capacity added this iteration.
        - electric_yearly_load_statistics:
            The yearly electric load statistics.
        - end_year:
            The end year of the simulation period.
        - ghg_inputs:
            The GHG input information.
        - heat_exchanger_addition:
            The additional number of heat exchangers added this iteration.
        - hot_water_tank_addition:
            The additional number of hot-water tanks added this iteration.
        - location:
            The location being considered.
        - logger:
            The logger to use for the run.
        - pv_addition:
            The additional number of PV panels added this iteration.
        - pvt_addition:
            The additional number of PV-T panels added this iteration.
        - scenario:
            The scenario for the run(s) being carried out.
        - simulation_results:
            The system that was just simulated.
        - start_year:
            The start year for the simulation period.
        - storage_addition:
            The additional number of electric storage devices (batteries) added this
            iteration.
        - system_details:
            The deatils of the system that was just simulated.
        - technical_appraisal:
            The technical appraisal for the system.

    Outputs:
        An :class:`EnvironmentalAppraisal` containing the key environmental results.

    """

    if technical_appraisal.power_consumed_fraction is None:
        logger.error(
            "%sCannot carry out an environmental appraisal with no power-consumed "
            "fraction defined.%s",
            BColours.fail,
            BColours.endc,
        )
        raise ProgrammerJudgementFault(
            "simulation environmental appraisal",
            "The technical apparisal provided did not contain a valid power-consumed "
            "fraction. This is required to carry out an environmental appraisal.",
        )

    # Calculate the total brine produced.
    total_brine = (
        round(simulation_results[ColumnHeader.BRINE.value].sum(), 3)
        if ColumnHeader.BRINE.value in simulation_results
        else None
    )

    # Calculate new equipment GHGs
    try:
        (
            additional_equipment_emissions,
            subsystem_equipment_emissions,
        ) = ghgs.calculate_total_equipment_ghgs(
            buffer_tank_addition,
            clean_water_tank_addition,
            converter_addition,
            diesel_addition,
            ghg_inputs,
            heat_exchanger_addition,
            hot_water_tank_addition,
            logger,
            pv_addition,
            pvt_addition,
            scenario,
            storage_addition,
            technical_appraisal,
        )
    except KeyError as e:
        logger.error("Missing system equipment GHG input information: %s", str(e))
        raise

    # Add the independent GHGs.
    additional_equipment_emissions += ghgs.calculate_independent_ghgs(
        electric_yearly_load_statistics, end_year, ghg_inputs, location, start_year
    )

    # Calculate GHGs of connecting new households
    try:
        connections_ghgs = ghgs.calculate_connections_ghgs(
            ghg_inputs, simulation_results[ColumnHeader.HOUSEHOLDS.value]
        )
    except KeyError as e:
        logger.error("Missing household connection GHG input information: %s", str(e))
        raise

    # Calculate operating GHGs of the system during this simulation
    try:
        additional_om_emissions, subsystem_om_emissions = ghgs.calculate_total_om(
            system_details.initial_num_buffer_tanks
            if system_details.initial_num_buffer_tanks is not None
            else 0,
            system_details.initial_num_clean_water_tanks
            if system_details.initial_num_clean_water_tanks is not None
            else 0,
            system_details.initial_converter_sizes
            if system_details.initial_converter_sizes is not None
            else None,
            system_details.diesel_capacity,
            ghg_inputs,
            system_details.initial_num_buffer_tanks
            if system_details.initial_num_buffer_tanks is not None
            else 0,
            system_details.initial_num_hot_water_tanks
            if system_details.initial_num_hot_water_tanks is not None
            else 0,
            logger,
            system_details.initial_pv_size,
            system_details.initial_pvt_size
            if system_details.initial_pvt_size is not None
            else 0,
            scenario,
            system_details.initial_storage_size,
            technical_appraisal,
            start_year,
            end_year,
        )
    except KeyError as e:
        logger.error("Missing O&M GHG input information: %s", str(e))
        raise

    # Calculate running GHGs of the system
    try:
        diesel_fuel_ghgs = ghgs.calculate_diesel_fuel_ghgs(
            simulation_results[ColumnHeader.DIESEL_FUEL_USAGE.value], ghg_inputs
        )
    except KeyError as e:
        logger.error("Missing diesel-fuel GHG input information: %s", str(e))
        raise

    try:
        grid_ghgs = ghgs.calculate_grid_ghgs(
            ghg_inputs,
            simulation_results[ColumnHeader.GRID_ENERGY.value],
            location,
            start_year,
            end_year,
        )
    except KeyError as e:
        logger.error("Missing grid GHG input information: %s", str(e))
        raise
    try:
        kerosene_ghgs = ghgs.calculate_kerosene_ghgs(
            ghg_inputs, simulation_results[ColumnHeader.KEROSENE_LAMPS.value]
        )
    except KeyError as e:
        logger.error("Missing kerosene GHG input information: %s", str(e))
        raise

    try:
        kerosene_ghgs_mitigated = ghgs.calculate_kerosene_ghgs_mitigated(
            ghg_inputs, simulation_results[ColumnHeader.KEROSENE_MITIGATION.value]
        )
    except KeyError as e:
        logger.error("Missing kerosene GHG input information: %s", str(e))
        raise

    # Apportion the grid emissions by the resource types.
    total_subsystem_emissions: Dict[ResourceType, float] = {
        resource_type: value
        + subsystem_om_emissions[resource_type]
        + (grid_ghgs * technical_appraisal.power_consumed_fraction[resource_type])
        for resource_type, value in subsystem_equipment_emissions.items()
    }

    # Apportion the diesel emissions by the resource types.
    update_diesel_costs(
        diesel_fuel_ghgs, scenario, total_subsystem_emissions, technical_appraisal
    )

    # Apportion the connections emissions.
    total_subsystem_emissions[ResourceType.ELECTRIC] += (
        additional_equipment_emissions + additional_om_emissions + connections_ghgs
    )

    # Total GHGs incurred during simulation period
    total_equipment_emissions = sum(subsystem_equipment_emissions.values())
    total_om_emissions = sum(subsystem_om_emissions.values())
    total_system_ghgs = sum(total_subsystem_emissions.values())
    total_ghgs = total_system_ghgs + kerosene_ghgs

    # Return outputs
    return EnvironmentalAppraisal(
        round(diesel_fuel_ghgs, 3),
        round(grid_ghgs, 3),
        round(kerosene_ghgs, 3),
        round(kerosene_ghgs_mitigated, 3),
        round(connections_ghgs, 3),
        round(total_equipment_emissions, 3),
        round(total_om_emissions, 3),
        {key: round(value, 3) for key, value in total_subsystem_emissions.items()},
        round(total_brine, 3) if total_brine is not None else 0,
        round(total_ghgs, 3),
        round(total_system_ghgs, 3),
    )


def _simulation_financial_appraisal(  # pylint: disable=too-many-locals
    buffer_tank_addition: int,
    clean_water_tank_addition: int,
    converter_addition: Dict[Converter, int],
    diesel_addition: float,
    finance_inputs: Dict[str, Any],
    heat_exchanger_addition: int,
    hot_water_tank_addition: int,
    location: Location,
    logger: Logger,
    pv_addition: float,
    pvt_addition: float,
    scenario: Scenario,
    simulation_results: pd.DataFrame,
    storage_addition: float,
    system_details: SystemDetails,
    technical_appraisal: TechnicalAppraisal,
    yearly_load_statistics: pd.DataFrame,
) -> FinancialAppraisal:
    """
    Appraises the financial performance of a minigrid system.

    Inputs:
        - buffer_tank_addition:
            The additional number of buffer tanks added this iteration.
        - clean_water_tank_addition:
            The additional number of clean-water tanks added this iteration.
        - converter_addition:
            A mapping between converter names and the size of each that was added to the
            system this iteration.
        - diesel_addition:
            The additional diesel capacity added this iteration.
        - finance_inputs:
            The finance input information.
        - heat_exchanger_addition:
            The additional number of heat exchangers added this iteration.
        - hot_water_tank_addition:
            The additional number of hot-water tanks added this iteration.
        - location:
            The :class:`Location` being considered.
        - logger:
            The logger to use for the run.
        - pv_addition:
            The additional number of PV panels added this iteration.
        - pvt_addition:
            The additional number of PV-T panels added this iteration.
        - scenario:
            The scenario currently being considered.
        - simulation_results:
            Outputs of Energy_System().simulation(...)
        - storage_addition:
            The additional number of electric storage devices (batteries) added this
            iteration.
        - system_details:
            The details of this system.
        - technical_appraisal:
            The :class:`TechnicalAppraisal` for the system being considered.
        - yearly_load_statistics:
            The yearly electric load statistics for the system.

    Outputs:
        The financial appraisal of the system.

    """

    if technical_appraisal.power_consumed_fraction is None:
        logger.error(
            "%sCannot carry out a financial appraisal with no power-consumed fraction defined.%s",
            BColours.fail,
            BColours.endc,
        )
        raise ProgrammerJudgementFault(
            "simulation financial appraisal",
            "The technical apparisal provided did not contain a valid power-consumed "
            "fraction. This is required to carry out a financial appraisal.",
        )

    # Calculate new equipment costs (discounted)
    (
        additional_equipment_costs,
        subsystem_equipment_costs,
    ) = finance.discounted_equipment_cost(
        buffer_tank_addition,
        clean_water_tank_addition,
        converter_addition,
        diesel_addition,
        finance_inputs,
        heat_exchanger_addition,
        hot_water_tank_addition,
        logger,
        pv_addition,
        pvt_addition,
        scenario,
        storage_addition,
        technical_appraisal,
        system_details.start_year,
    )

    # Add the inddependent expenditure.
    independent_expenditure = finance.independent_expenditure(
        finance_inputs,
        location,
        yearly_load_statistics,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )

    # Calculate costs of connecting new households (discounted)
    connections_cost = finance.connections_expenditure(
        finance_inputs,
        simulation_results[ColumnHeader.HOUSEHOLDS.value],
        system_details.start_year,
    )

    # Calculate operating costs of the system during this simulation (discounted)
    additional_om_costs, subsystem_om_costs = finance.total_om(
        system_details.initial_num_buffer_tanks
        if system_details.initial_num_buffer_tanks is not None
        else 0,
        system_details.initial_num_clean_water_tanks
        if system_details.initial_num_clean_water_tanks is not None
        else 0,
        system_details.initial_converter_sizes
        if system_details.initial_converter_sizes is not None
        else None,
        system_details.diesel_capacity,
        finance_inputs,
        system_details.initial_num_buffer_tanks
        if system_details.initial_num_buffer_tanks is not None
        else 0,
        system_details.initial_num_hot_water_tanks
        if system_details.initial_num_hot_water_tanks is not None
        else 0,
        logger,
        system_details.initial_pv_size,
        system_details.initial_pvt_size
        if system_details.initial_pvt_size is not None
        else 0,
        scenario,
        system_details.initial_storage_size,
        technical_appraisal,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )

    # Calculate running costs of the system (discounted)
    diesel_fuel_costs = finance.diesel_fuel_expenditure(
        simulation_results[ColumnHeader.DIESEL_FUEL_USAGE.value],
        finance_inputs,
        logger,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )
    # FIXME: The diesel fuel usage of any diesel water heaters should be calcaulted here
    grid_costs = finance.expenditure(
        ImpactingComponent.GRID,
        finance_inputs,
        simulation_results[ColumnHeader.GRID_ENERGY.value],
        logger,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )
    kerosene_costs = finance.expenditure(
        ImpactingComponent.KEROSENE,
        finance_inputs,
        simulation_results[ColumnHeader.KEROSENE_LAMPS.value],
        logger,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )
    kerosene_costs_mitigated = finance.expenditure(
        ImpactingComponent.KEROSENE,
        finance_inputs,
        simulation_results[ColumnHeader.KEROSENE_MITIGATION.value],
        logger,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )

    # Apportion the grid running costs by the resource types.
    total_subsystem_costs: Dict[ResourceType, float] = {
        resource_type: value
        + subsystem_om_costs[resource_type]
        + (
            (grid_costs + independent_expenditure)
            * technical_appraisal.power_consumed_fraction[resource_type]
        )
        for resource_type, value in subsystem_equipment_costs.items()
    }

    # Apportion the diesel running costs by the resource types to the subsystems.
    update_diesel_costs(
        diesel_fuel_costs, scenario, total_subsystem_costs, technical_appraisal
    )

    # Add the connections cost for the electric subsystem and any costs that haven't yet
    # been counted for.
    total_subsystem_costs[ResourceType.ELECTRIC] += connections_cost
    total_subsystem_costs[ResourceType.HOT_CLEAN_WATER] += (
        additional_equipment_costs + additional_om_costs
    )

    # Total cost incurred during simulation period (discounted)
    total_equipment_costs = sum(subsystem_equipment_costs.values())
    total_om_costs = sum(subsystem_om_costs.values())

    total_system_cost = sum(total_subsystem_costs.values())

    total_cost = total_system_cost + kerosene_costs

    # Return outputs
    return FinancialAppraisal(
        round(diesel_fuel_costs, 3),
        round(grid_costs, 3),
        round(kerosene_costs, 3),
        round(kerosene_costs_mitigated, 3),
        round(connections_cost, 3),
        round(total_equipment_costs, 3),
        round(total_om_costs, 3),
        {key: round(value, 3) for key, value in total_subsystem_costs.items()},
        round(total_cost, 3),
        round(total_system_cost, 3),
    )


def _appraise_clean_water_system_tech(  # pylint: disable=too-many-locals
    finance_inputs: Dict[str, Any],
    logger: Logger,
    renewables_fraction: float,
    simulation_results: pd.DataFrame,
    system_details: SystemDetails,
) -> Tuple[
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
]:
    """
    Appraises the clean-water system's technical parameters.

    Inputs:
        - finance_inputs:
            Financial input information.
        - logger:
            The :class:`logging.Logger` for the run.
        - renewables_fraction:
            The fraction of electricity that was generated through renewables.
        - simulation_results:
            Outputs of Energy_System().simulation(...).
        - system_details:
            Information about the system.

    Outputs:
        - clean_water_blackouts:
            The proportion of time for which clean water was not supplied.
        - clean_water_demand_covered:
            The fraction of the clean-water demand that was covered by the system.
        - discounted_clean_water:
            The discounted clean water produced by the system.
        - renewable_clean_water_fraction:
            The fraction of the clean water that was produced by renewables.
        - solar_thermal_cw_fraction:
            The fraction of the clean water that was produced renewably with the input
            heat provided by solar thermal panels.
        - total_clean_water:
            The total clean water consumed within the system, measured in litres.

    """

    if ColumnHeader.TOTAL_CW_CONSUMED.value not in simulation_results:
        return (None, None, None, None, None, None)

    clean_water_blackouts: float = round(
        float(
            np.mean(
                simulation_results[ColumnHeader.CLEAN_WATER_BLACKOUTS.value].values  # type: ignore [arg-type]
            )
        ),
        3,
    )
    clean_water_consumed: pd.Series = simulation_results[
        ColumnHeader.TOTAL_CW_CONSUMED.value
    ]
    renewable_clean_water_fraction: float = (
        (
            # Clean water taken from the thermal desalination plant(s) directly.
            np.sum(
                simulation_results[  # type: ignore
                    ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value
                ]
                * simulation_results[
                    ColumnHeader.DESALINATION_PLANT_RENEWABLE_FRACTION.value
                ]
            )
            if ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value
            in simulation_results
            else 0
        )
        # Clean water taken from tank storage.
        + np.sum(
            simulation_results[  # type: ignore
                ColumnHeader.CLEAN_WATER_FROM_STORAGE.value
            ]
        )
        # Clean water generated using excess power in the minigrid.
        + np.sum(
            simulation_results[  # type: ignore
                ColumnHeader.CLEAN_WATER_FROM_EXCESS_ELECTRICITY.value
            ]
        )
        # Clean water generated using a prioritisation approach. This will be as
        # renewable as the electricity mix of the minigrid (on average).
        + (
            renewables_fraction
            * np.sum(
                simulation_results[  # type: ignore
                    ColumnHeader.CLEAN_WATER_FROM_PRIORITISATION.value
                ]
            )
            if ColumnHeader.CLEAN_WATER_FROM_PRIORITISATION.value in simulation_results
            else 0
        )
    ) / np.sum(
        clean_water_consumed  # type: ignore
    )

    solar_thermal_cw_fraction: float = (
        np.sum(
            simulation_results[  # type: ignore
                ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value
            ]
            * simulation_results[
                ColumnHeader.DESALINATION_PLANT_RENEWABLE_FRACTION.value
            ]
        )
        if ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value in simulation_results
        else 0
    )

    total_clean_water: float = np.sum(
        simulation_results[ColumnHeader.TOTAL_CW_SUPPLIED.value]  # type: ignore
    )

    clean_water_demand_covered: float = total_clean_water / np.sum(
        simulation_results[ColumnHeader.TOTAL_CW_LOAD.value]  # type: ignore
    )

    # Calculate total discounted clean water values
    total_clean_water_consumed_daily: pd.Series = hourly_profile_to_daily_sum(
        pd.DataFrame(clean_water_consumed)
    )
    discounted_clean_water: float = finance.discounted_energy_total(
        finance_inputs,
        logger,
        total_clean_water_consumed_daily,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )

    return (
        clean_water_blackouts,
        clean_water_demand_covered,
        discounted_clean_water,
        renewable_clean_water_fraction,
        solar_thermal_cw_fraction,
        total_clean_water,
    )


def _appraise_electric_system_tech(  # pylint: disable=too-many-locals
    finance_inputs: Dict[str, Any],
    logger: Logger,
    simulation_results: pd.DataFrame,
    system_details: SystemDetails,
) -> Tuple[
    float,
    pd.Series,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    Optional[float],
    float,
    float,
]:
    """
    Calculates electric system technical appraisal parameters.

    Inputs:
        - finance_inputs:
            Financial input information.
        - logger:
            The :class:`logging.Logger` for the run.
        - simulation_results:
            Outputs of Energy_System().simulation(...).
        - system_details:
            Information about the system.

    Outputs:
        - discounted_electricity:
            The discounted electricity produced by the system.
        - electricity_consumed:
            The total electricity consumed by the system.
        - renewable_electricity_used:
            The renewable electricity consumed by the system.
        - renewables_fraction:
            The fraction of electricity consumed by the system that was supplied by
            renewables.
        - storage_electricity_used:
            The total electricity that was supplied by storage contained within the
            system.
        - total_diesel_used:
            The total electricity that was supplied by diesel generators.
        - total_electricity_consumed:
            The total electricity consumed by the system.
        - total_grid_used:
            The total electricity that was supplied by the grid connection to the system.
        - total_pv_energy:
            The total electricity produced by PV panels installed.
        - total_pvt_energy:
            The total electricity produced by PV-T panels installed.
        - unmet_electricity:
            The total unmet electricity demand, measured in kWh.
        - unmet_fraction:
            The fraction of electricity demand that went unmet through the simulation
            period.

    """

    electricity_consumed = simulation_results[
        ColumnHeader.TOTAL_ELECTRICITY_CONSUMED.value
    ]
    total_electricity_consumed: float = np.sum(electricity_consumed)  # type: ignore
    total_load_energy: float = np.sum(
        simulation_results[ColumnHeader.LOAD_ENERGY.value]  # type: ignore
    )
    renewable_electricity_used: float = np.sum(
        simulation_results[ColumnHeader.RENEWABLE_ELECTRICITY_USED_DIRECTLY.value]  # type: ignore
    )
    total_pv_energy: float = np.sum(
        simulation_results[ColumnHeader.PV_ELECTRICITY_SUPPLIED.value]  # type: ignore
    )
    total_pvt_energy: Optional[float] = (
        np.sum(
            simulation_results[ColumnHeader.TOTAL_PVT_ELECTRICITY_SUPPLIED.value]  # type: ignore
        )
        if ColumnHeader.TOTAL_PVT_ELECTRICITY_SUPPLIED.value in simulation_results
        else None
    )
    storage_electricity_used: float = np.sum(
        simulation_results[ColumnHeader.ELECTRICITY_FROM_STORAGE.value]  # type: ignore
    )
    total_grid_used: float = np.sum(
        simulation_results[ColumnHeader.GRID_ENERGY.value]  # type: ignore
    )
    total_diesel_used: float = np.sum(
        simulation_results[ColumnHeader.DIESEL_ENERGY_SUPPLIED.value]  # type: ignore
    )
    unmet_electricity: float = np.sum(
        simulation_results[ColumnHeader.UNMET_ELECTRICITY.value]  # type: ignore
    )
    renewables_fraction: float = (
        renewable_electricity_used + storage_electricity_used
    ) / total_electricity_consumed
    unmet_fraction: float = unmet_electricity / total_load_energy

    # Calculate total discounted electricity values
    total_electricity_consumed_daily = hourly_profile_to_daily_sum(
        pd.DataFrame(electricity_consumed)
    )
    discounted_electricity = finance.discounted_energy_total(
        finance_inputs,
        logger,
        total_electricity_consumed_daily,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )

    return (
        discounted_electricity,
        electricity_consumed,
        renewable_electricity_used,
        renewables_fraction,
        storage_electricity_used,
        total_diesel_used,
        total_electricity_consumed,
        total_grid_used,
        total_pv_energy,
        total_pvt_energy,
        unmet_electricity,
        unmet_fraction,
    )


def _appraise_hot_water_system_tech(
    finance_inputs: Dict[str, Any],
    logger: Logger,
    renewables_fraction: float,
    scenario: Scenario,
    simulation_results: pd.DataFrame,
    system_details: SystemDetails,
) -> Tuple[
    Optional[float],
    Optional[pd.Series],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
]:
    """
    Appraises the hot-water system's technical parameters.

    Inputs:
        - finance_inputs:
            Financial input information.
        - logger:
            The :class:`logging.Logger` for the run.
        - renewables_fraction:
            The fraction of electricity consumed by the system that was supplied by
            renewables.
        - scenario:
            The :class:`Scenario` for the run.
        - simulation_results:
            Outputs of Energy_System().simulation(...).
        - system_details:
            Information about the system.

    Outputs:
        - discounted_hot_water:
            The total discounted hot water produced.
        - hot_water_consumed:
            The :class:`pd.Series` of the hot water consumed at each time step.
        - hot_water_demand_covered:
            The fraction of hot-water demand that was met by the system.
        - renewable_hot_water_fraction:
            The fraction of hot-water demand that was met through renewable sources.
        - solar_thermal_hw_fraction:
            The fraction of hot-water demand that was met renewably using solar-thermal
            energy
        - total_hot_water:
            The total hot water produced by the system, measured in litres.

    """

    if ColumnHeader.HW_SOLAR_THERMAL_FRACTION.value not in simulation_results:
        return (
            None,
            None,
            None,
            None,
            None,
            None,
        )

    solar_thermal_hw_fraction: float = round(
        float(
            np.nansum(
                (
                    simulation_results[  # type: ignore [operator]
                        ColumnHeader.HW_SOLAR_THERMAL_FRACTION.value
                    ].values
                    * simulation_results[ColumnHeader.HW_TANK_OUTPUT.value].values
                )
            )
            / np.nansum(simulation_results[ColumnHeader.HW_TANK_OUTPUT.value].values)
        ),
        3,
    )

    hot_water_demand_covered: float = round(
        float(
            np.mean(
                simulation_results[ColumnHeader.HW_TANK_OUTPUT.value]  # type: ignore
                / simulation_results[ColumnHeader.TOTAL_HW_LOAD.value]
            )
        ),
        3,
    )

    # Compute the renewable fraction based on the scenario.
    if scenario.hot_water_scenario is None:
        logger.error(
            "%sNo hot-water scenario despite hot-water appraisal requetsed.%s",
            BColours.fail,
            BColours.endc,
        )
        raise ProgrammerJudgementFault(
            "hot-water technical appraisal",
            "Cannot appraise a hot-water system if no hot-water scenario defined.",
        )
    if scenario.hot_water_scenario.auxiliary_heater == AuxiliaryHeaterType.ELECTRIC:
        renewable_hot_water_fraction: float = round(
            renewables_fraction * (hot_water_demand_covered - solar_thermal_hw_fraction)
            + solar_thermal_hw_fraction,
            3,
        )
    else:
        renewable_hot_water_fraction = solar_thermal_hw_fraction

    # Calculate the total heating power consumed by the system.
    hot_water_consumed: pd.Series = simulation_results[
        ColumnHeader.HW_TANK_OUTPUT.value
    ]
    total_hot_water: float = np.sum(hot_water_consumed)  # type: ignore

    # Calculate total discounted hot water values.
    total_hot_water_consumed_daily: pd.Series = hourly_profile_to_daily_sum(
        pd.DataFrame(hot_water_consumed)
    )
    discounted_hot_water: Optional[float] = finance.discounted_energy_total(
        finance_inputs,
        logger,
        total_hot_water_consumed_daily,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )

    return (
        discounted_hot_water,
        hot_water_consumed,
        hot_water_demand_covered,
        renewable_hot_water_fraction,
        solar_thermal_hw_fraction,
        total_hot_water,
    )


def _simulation_technical_appraisal(  # pylint: disable=too-many-locals
    finance_inputs: Dict[str, Any],
    logger: Logger,
    scenario: Scenario,
    simulation_results: pd.DataFrame,
    system_details: SystemDetails,
) -> TechnicalAppraisal:
    """
    Appraises the technical performance of a minigrid system

    Inputs:
        - finance_inputs:
            Financial input information.
        - logger:
            The :class:`logging.Logger` for the run.
        - scenario:
            The :class:`Scenario` that was just run.
        - simulation_results:
            Outputs of Energy_System().simulation(...).
        - system_details:
            Details about the simulation outputs.

    Outputs:
        - Technical appraisal:
            A :class:`TechnicalAppraisal` containing key technical data e.g. energy
            used, unmet energy, blackout percentage, discounted energy.

    """

    # Calculate system blackouts
    system_blackouts: float = float(
        np.mean(
            simulation_results[ColumnHeader.BLACKOUTS.value].values  # type: ignore [arg-type]
        )
    )

    # Electricity system.
    (
        discounted_electricity,
        electricity_consumed,
        renewable_electricity_used,
        renewables_fraction,
        storage_electricity_used,
        total_diesel_used,
        total_electricity_consumed,
        total_grid_used,
        total_pv_energy,
        total_pvt_energy,
        unmet_electricity,
        unmet_fraction,
    ) = _appraise_electric_system_tech(
        finance_inputs, logger, simulation_results, system_details
    )

    # Clean-water system.
    (
        clean_water_blackouts,
        clean_water_demand_covered,
        discounted_clean_water,
        renewable_clean_water_fraction,
        solar_thermal_cw_fraction,
        total_clean_water,
    ) = _appraise_clean_water_system_tech(
        finance_inputs, logger, renewables_fraction, simulation_results, system_details
    )

    # Hot-water system.
    (
        discounted_hot_water,
        hot_water_consumed,
        hot_water_demand_covered,
        renewable_hot_water_fraction,
        solar_thermal_hw_fraction,
        total_hot_water,
    ) = _appraise_hot_water_system_tech(
        finance_inputs,
        logger,
        renewables_fraction,
        scenario,
        simulation_results,
        system_details,
    )

    # Calculate the fraction of power used providing each resource.
    power_consumed_fraction = _calculate_power_consumed_fraction(
        simulation_results, total_electricity_consumed
    )

    # Calculate the total energy consumed by the system using the conversion factors
    # defined by the user.
    energy_consumed = electricity_consumed.copy()
    total_energy_consumed: float = total_electricity_consumed

    # Heating system.
    if hot_water_consumed is not None:
        heating_consumed: Optional[pd.Series] = (
            hot_water_consumed  # [kg]
            * HEAT_CAPACITY_OF_WATER  # [J/kg*K]
            * simulation_results[  # type: ignore
                ColumnHeader.HW_TEMPERATURE_GAIN.value
            ]  # [K]
        ) / 1000  # + clean_water_system_heat + ...
        total_heating_consumed: Optional[float] = np.sum(heating_consumed)  # type: ignore

        # Append the energy consumption information.
        energy_consumed += (
            scenario.reference_thermal_efficiency * heating_consumed  # type: ignore
        )
        total_energy_consumed += scenario.reference_thermal_efficiency * (  # type: ignore
            total_heating_consumed
        )

        # Calculate discounted heating information.
        total_heating_consumed_daily: pd.Series = hourly_profile_to_daily_sum(
            pd.DataFrame(heating_consumed)
        )
        discounted_heating: Optional[float] = finance.discounted_energy_total(
            finance_inputs,
            logger,
            total_heating_consumed_daily,
            start_year=system_details.start_year,
            end_year=system_details.end_year,
        )

    else:
        discounted_heating = None
        heating_consumed = None
        total_heating_consumed = None

    # Calculate total discounted energy values
    total_energy_consumed_daily = hourly_profile_to_daily_sum(
        pd.DataFrame(energy_consumed)
    )
    discounted_energy = finance.discounted_energy_total(
        finance_inputs,
        logger,
        total_energy_consumed_daily,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )

    # Calculate proportion of kerosene displaced (defaults to zero if kerosene is not
    # originally used
    if np.sum(simulation_results[ColumnHeader.KEROSENE_LAMPS.value]) > 0.0:  # type: ignore
        kerosene_displacement = (
            np.sum(
                simulation_results[ColumnHeader.KEROSENE_MITIGATION.value]  # type: ignore
            )
        ) / (
            np.sum(
                simulation_results[ColumnHeader.KEROSENE_MITIGATION.value]  # type: ignore
            )
            + np.sum(
                simulation_results[ColumnHeader.KEROSENE_LAMPS.value]  # type: ignore
            )
        )
    else:
        kerosene_displacement = 0.0

    # Calculate diesel fuel usage
    total_diesel_fuel = np.sum(
        simulation_results[ColumnHeader.DIESEL_FUEL_USAGE.value]  # type: ignore
    )

    # Return outputs
    return TechnicalAppraisal(
        round(system_blackouts, 3),
        round(clean_water_blackouts, 3) if clean_water_blackouts is not None else None,
        round(clean_water_demand_covered, 3)
        if clean_water_demand_covered is not None
        else None,
        round(total_diesel_used, 3),
        round(total_diesel_fuel, 3),
        round(discounted_clean_water, 3)
        if discounted_clean_water is not None
        else None,
        round(discounted_electricity, 3),
        round(discounted_energy, 3),
        round(discounted_heating, 3) if discounted_heating is not None else None,
        round(discounted_hot_water, 3) if discounted_hot_water is not None else None,
        round(total_grid_used, 3),
        round(hot_water_demand_covered, 3)
        if hot_water_demand_covered is not None
        else None,
        round(kerosene_displacement, 3),
        power_consumed_fraction,
        round(total_pv_energy, 3),
        round(total_pvt_energy, 3) if total_pvt_energy is not None else None,
        round(renewable_clean_water_fraction, 3)
        if renewable_clean_water_fraction is not None
        else None,
        round(renewables_fraction, 3),
        round(renewable_electricity_used, 3),
        round(renewable_hot_water_fraction, 3)
        if renewable_hot_water_fraction is not None
        else None,
        round(solar_thermal_cw_fraction, 3)
        if solar_thermal_cw_fraction is not None
        else None,
        round(solar_thermal_hw_fraction, 3)
        if solar_thermal_hw_fraction is not None
        else None,
        round(storage_electricity_used, 3),
        round(total_clean_water, 3) if total_clean_water is not None else None,
        round(total_hot_water, 3) if total_hot_water is not None else None,
        round(total_electricity_consumed, 3),
        round(total_energy_consumed, 3),
        round(total_heating_consumed, 3)
        if total_heating_consumed is not None
        else None,
        round(unmet_electricity, 3),
        round(unmet_fraction, 3),
    )


def appraise_system(  # pylint: disable=too-many-locals
    electric_yearly_load_statistics: pd.DataFrame,
    end_year: int,
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    location: Location,
    logger: Logger,
    previous_system: Optional[SystemAppraisal],
    scenario: Scenario,
    simulation_results: pd.DataFrame,
    start_year: int,
    system_details: SystemDetails,
) -> SystemAppraisal:
    """
    Appraises the total performance of a minigrid system for all performance metrics

    Inputs:
        - electric_yearly_load_statistics:
            The yearly electric load statistics.
        - end_year:
            The end year for the simulation that was just run.
        - finance_inputs:
            The finance input information.
        - location:
            The location currently being considered.
        - logger:
            The logger to use for the run.
        - previous_system:
            Report from previously installed system (not required if no system was
            previously deployed)
        - scenario:
            The scenario currently being considered.
        - simulation_results
            Outputs of Energy_System().simulation(...)
        - start_year:
            The start year for the simulation that was just run.
        - system_details:
            The system details about the system that was just simulated.

    Outputs:
        - system_outputs:
            :class:`pd.DataFrame` containing all key technical, performance,
            financial and environmental information.

    """

    if previous_system is None:
        previous_system = SystemAppraisal(
            CumulativeResults(),
            EnvironmentalAppraisal(),
            FinancialAppraisal(),
            SystemDetails(),
            TechnicalAppraisal(),
        )

    # Compute the additions made to the system.
    buffer_tank_addition: int = (
        system_details.initial_num_buffer_tanks
        - previous_system.system_details.final_num_buffer_tanks
        if system_details.initial_num_buffer_tanks is not None
        and previous_system.system_details.final_num_buffer_tanks is not None
        else 0
    )
    clean_water_tank_addition: int = (
        system_details.initial_num_clean_water_tanks
        - previous_system.system_details.final_num_clean_water_tanks
        if system_details.initial_num_clean_water_tanks is not None
        and previous_system.system_details.final_num_clean_water_tanks is not None
        else 0
    )
    if system_details.initial_converter_sizes is None:
        logger.error(
            "%sNo converter sizes on system details when calling system appraisal. "
            "Only systems that have been simulated can be appraised.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InternalError("Misuse of system appraisal function.")
    converter_addition: Dict[Converter, int] = {
        converter: size
        - (
            previous_system.system_details.final_converter_sizes[converter]
            if previous_system.system_details.final_converter_sizes is not None
            else 0
        )
        for converter, size in system_details.initial_converter_sizes.items()
    }
    diesel_addition = (
        system_details.diesel_capacity - previous_system.system_details.diesel_capacity
    )
    heat_exchanger_addition: int = (
        system_details.initial_num_buffer_tanks
        - previous_system.system_details.final_num_buffer_tanks
        if system_details.initial_num_buffer_tanks is not None
        and previous_system.system_details.final_num_buffer_tanks is not None
        else 0
    )
    hot_water_tank_addition: int = (
        system_details.initial_num_hot_water_tanks
        - previous_system.system_details.final_num_hot_water_tanks
        if system_details.initial_num_hot_water_tanks is not None
        and previous_system.system_details.final_num_hot_water_tanks is not None
        else 0
    )
    pv_addition = (
        system_details.initial_pv_size - previous_system.system_details.final_pv_size
    )
    pvt_addition: float = (
        system_details.initial_pvt_size - previous_system.system_details.final_pvt_size
        if system_details.initial_pvt_size is not None
        and previous_system.system_details.final_pvt_size is not None
        else 0
    )
    storage_addition = (
        system_details.initial_storage_size
        - previous_system.system_details.final_storage_size
    )

    # Get results which will be carried forward into optimisation process
    technical_appraisal = _simulation_technical_appraisal(
        finance_inputs, logger, scenario, simulation_results, system_details
    )

    financial_appraisal = _simulation_financial_appraisal(
        buffer_tank_addition,
        clean_water_tank_addition,
        converter_addition,
        diesel_addition,
        finance_inputs,
        heat_exchanger_addition,
        hot_water_tank_addition,
        location,
        logger,
        pv_addition,
        pvt_addition,
        scenario,
        simulation_results,
        storage_addition,
        system_details,
        technical_appraisal,
        electric_yearly_load_statistics,
    )
    environmental_appraisal = _simulation_environmental_appraisal(
        buffer_tank_addition,
        clean_water_tank_addition,
        converter_addition,
        diesel_addition,
        electric_yearly_load_statistics,
        end_year,
        ghg_inputs,
        heat_exchanger_addition,
        hot_water_tank_addition,
        location,
        logger,
        pv_addition,
        pvt_addition,
        scenario,
        simulation_results,
        start_year,
        storage_addition,
        system_details,
        technical_appraisal,
    )

    # Get results that rely on metrics of different kinds and several different
    # iteration periods
    cumulative_results = _simulation_cumulative_results(
        environmental_appraisal,
        financial_appraisal,
        logger,
        previous_system,
        technical_appraisal,
    )

    # Compute the levilised costs of the system.
    if cumulative_results.subsystem_costs is None:
        logger.error(
            "%sSubsystem costs not determined despite this being necessary.%s",
            BColours.fail,
            BColours.endc,
        )
        raise ProgrammerJudgementFault(
            "appraisal::appraise_system",
            "Subsystem costs were not determined, check internal code flows.",
        )
    lcu_electricity = float(
        cumulative_results.subsystem_costs[ResourceType.ELECTRIC]
        / cumulative_results.discounted_electricity
    )
    lcu_energy = float(
        cumulative_results.system_cost / cumulative_results.discounted_energy
    )
    lcu_h: Optional[float] = (
        float(
            cumulative_results.subsystem_costs[ResourceType.HOT_CLEAN_WATER]
            / cumulative_results.discounted_heating
        )
        if cumulative_results.discounted_heating > 0
        else None
    )
    if (
        cumulative_results.discounted_clean_water is not None
        and cumulative_results.discounted_clean_water > 0
    ):
        lcu_w: Optional[float] = float(
            cumulative_results.subsystem_costs[ResourceType.CLEAN_WATER]
            / cumulative_results.discounted_clean_water
        )
    else:
        lcu_w = None

    # Compute the emissions intensity of the system.
    emissions_intensity = 1000.0 * float(
        cumulative_results.system_ghgs / cumulative_results.energy
    )

    # Compute cumulative waste products.
    if cumulative_results.waste_produced is not None:
        cumulative_brine: Optional[float] = (
            cumulative_results.waste_produced[WasteProduct.BRINE]
            if WasteProduct.BRINE in cumulative_results.waste_produced
            else None
        )
    else:
        cumulative_brine = None

    # pylint: disable=line-too-long
    criteria: Dict[Criterion, Optional[float]] = {
        Criterion.BLACKOUTS: technical_appraisal.blackouts,
        Criterion.CLEAN_WATER_BLACKOUTS: technical_appraisal.clean_water_blackouts,
        Criterion.CUMULATIVE_BRINE: cumulative_brine,
        Criterion.CUMULATIVE_COST: cumulative_results.cost,
        Criterion.CUMULATIVE_GHGS: cumulative_results.ghgs,
        Criterion.CUMULATIVE_SYSTEM_COST: cumulative_results.system_cost,
        Criterion.CUMULATIVE_SYSTEM_GHGS: cumulative_results.system_ghgs,
        Criterion.CW_DEMAND_COVERED: technical_appraisal.cw_demand_covered,
        Criterion.CW_RENEWABLES_FRACTION: technical_appraisal.renewable_clean_water_fraction,
        Criterion.CW_SOLAR_THERMAL_FRACTION: technical_appraisal.solar_thermal_cw_fraction,
        Criterion.EMISSIONS_INTENSITY: round(emissions_intensity, 3),
        Criterion.HW_DEMAND_COVERED: technical_appraisal.hw_demand_covered,
        Criterion.HW_RENEWABLES_FRACTION: technical_appraisal.renewable_hot_water_fraction,
        Criterion.HW_SOLAR_THERMAL_FRACTION: technical_appraisal.solar_thermal_hw_fraction,
        Criterion.KEROSENE_COST_MITIGATED: financial_appraisal.kerosene_cost_mitigated,
        Criterion.KEROSENE_DISPLACEMENT: technical_appraisal.kerosene_displacement,
        Criterion.KEROSENE_GHGS_MITIGATED: environmental_appraisal.kerosene_ghgs_mitigated,
        Criterion.LCU_ENERGY: round(lcu_energy, 6),
        Criterion.LCUE: round(lcu_electricity, 3),
        Criterion.LCUH: round(lcu_h, 6) if lcu_h is not None else None,
        Criterion.LCUW: round(lcu_w, 6) if lcu_w is not None else None,
        Criterion.RENEWABLES_ELECTRICITY_FRACTION: technical_appraisal.renewable_electricity_fraction,
        Criterion.TOTAL_BRINE: environmental_appraisal.total_brine,
        Criterion.TOTAL_COST: financial_appraisal.total_cost,
        Criterion.TOTAL_GHGS: environmental_appraisal.total_ghgs,
        Criterion.TOTAL_SYSTEM_COST: financial_appraisal.total_system_cost,
        Criterion.TOTAL_SYSTEM_GHGS: environmental_appraisal.total_system_ghgs,
        Criterion.UNMET_CLEAN_WATER_FRACTION: (
            1 - technical_appraisal.cw_demand_covered
        )
        if technical_appraisal.cw_demand_covered is not None
        else None,
        Criterion.UNMET_ELECTRICITY_FRACTION: technical_appraisal.unmet_energy_fraction,
        Criterion.UNMET_HOT_WATER_FRACTION: (1 - technical_appraisal.hw_demand_covered)
        if technical_appraisal.hw_demand_covered is not None
        else None,
    }

    if technical_appraisal.clean_water_blackouts is not None:
        criteria[Criterion.CLEAN_WATER_BLACKOUTS] = round(
            technical_appraisal.clean_water_blackouts, 3
        )

    # Combine the outputs into a single system appraisal instance.
    system_appraisal = SystemAppraisal(
        cumulative_results,
        environmental_appraisal,
        financial_appraisal,
        system_details,
        technical_appraisal,
        criteria=criteria,
    )

    return system_appraisal
