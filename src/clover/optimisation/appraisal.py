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

from logging import Logger
from typing import Any, Dict, Optional

import numpy as np  # pylint: disable=import-error
import pandas as pd

from ..impact import finance, ghgs

from ..__utils__ import (
    ColumnHeader,
    Criterion,
    CumulativeResults,
    EnvironmentalAppraisal,
    FinancialAppraisal,
    hourly_profile_to_daily_sum,
    Location,
    SystemAppraisal,
    SystemDetails,
    TechnicalAppraisal,
)
from ..conversion.conversion import Converter
from ..impact.__utils__ import ImpactingComponent

__all__ = ("appraise_system",)


def _simulation_environmental_appraisal(
    buffer_tank_addition: int,
    clean_water_tank_addition: int,
    converter_addition: Dict[str, int],
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
    simulation_results: pd.DataFrame,
    start_year: int,
    storage_addition: float,
    system_details: SystemDetails,
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
        - simulation_results:
            The system that was just simulated.
        - start_year:
            The start year for the simulation period.
        - storage_addition:
            The additional number of electric storage devices (batteries) added this
            iteration.
        - system_details:
            The deatils of the system that was just simulated.

    Outputs:
        An :class:`EnvironmentalAppraisal` containing the key environmental results.

    """

    # Calculate the total brine produced.
    total_brine = round(simulation_results[ColumnHeader.BRINE.value].sum(), 3)

    # Calculate new equipment GHGs
    try:
        equipment_ghgs = ghgs.calculate_total_equipment_ghgs(
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
            storage_addition,
        ) + ghgs.calculate_independent_ghgs(
            electric_yearly_load_statistics, end_year, ghg_inputs, location, start_year
        )
    except KeyError as e:
        logger.error("Missing system equipment GHG input information: %s", str(e))
        raise

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
        om_ghgs = ghgs.calculate_total_om(
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
            system_details.initial_storage_size,
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

    # Total GHGs incurred during simulation period
    total_ghgs = (
        equipment_ghgs
        + connections_ghgs
        + om_ghgs
        + diesel_fuel_ghgs
        + grid_ghgs
        + kerosene_ghgs
    )
    total_system_ghgs = (
        equipment_ghgs + connections_ghgs + om_ghgs + diesel_fuel_ghgs + grid_ghgs
    )

    # Return outputs
    return EnvironmentalAppraisal(
        round(diesel_fuel_ghgs, 3),
        round(grid_ghgs, 3),
        round(kerosene_ghgs, 3),
        round(kerosene_ghgs_mitigated, 3),
        round(connections_ghgs, 3),
        round(equipment_ghgs, 3),
        round(om_ghgs, 3),
        round(total_brine, 3),
        round(total_ghgs, 3),
        round(total_system_ghgs, 3),
    )


def _simulation_financial_appraisal(
    buffer_tank_addition: int,
    clean_water_tank_addition: int,
    converter_addition: Dict[str, int],
    diesel_addition: float,
    finance_inputs: Dict[str, Any],
    heat_exchanger_addition: int,
    hot_water_tank_addition: int,
    location: Location,
    logger: Logger,
    pv_addition: float,
    pvt_addition: float,
    simulation_results: pd.DataFrame,
    storage_addition: float,
    system_details: SystemDetails,
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
        - simulation_results:
            Outputs of Energy_System().simulation(...)
        - storage_addition:
            The additional number of electric storage devices (batteries) added this
            iteration.
        - system_details:
            The details of this system.
        - yearly_load_statistics:
            The yearly electric load statistics for the system.

    Outputs:
        The financial appraisal of the system.

    """

    # Calculate new equipment costs (discounted)
    equipment_costs = finance.discounted_equipment_cost(
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
        storage_addition,
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
    equipment_costs += independent_expenditure

    # Calculate costs of connecting new households (discounted)
    connections_cost = finance.connections_expenditure(
        finance_inputs,
        simulation_results[ColumnHeader.HOUSEHOLDS.value],
        system_details.start_year,
    )

    # Calculate operating costs of the system during this simulation (discounted)
    om_costs = finance.total_om(
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
        system_details.initial_storage_size,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )

    # Calculate running costs of the system (discounted)
    diesel_costs = finance.diesel_fuel_expenditure(
        simulation_results[ColumnHeader.DIESEL_FUEL_USAGE.value],
        finance_inputs,
        logger,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )
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

    # Total cost incurred during simulation period (discounted)
    total_cost = (
        equipment_costs
        + connections_cost
        + om_costs
        + diesel_costs
        + grid_costs
        + kerosene_costs
    )
    total_system_cost = (
        equipment_costs + connections_cost + om_costs + diesel_costs + grid_costs
    )

    # Return outputs
    return FinancialAppraisal(
        round(diesel_costs, 3),
        round(grid_costs, 3),
        round(kerosene_costs, 3),
        round(kerosene_costs_mitigated, 3),
        round(connections_cost, 3),
        round(equipment_costs, 3),
        round(om_costs, 3),
        round(total_cost, 3),
        round(total_system_cost, 3),
    )


def _simulation_technical_appraisal(
    finance_inputs: Dict[str, Any],
    logger: Logger,
    simulation_results: pd.DataFrame,
    system_details: SystemDetails,
) -> TechnicalAppraisal:
    """
    Appraises the technical performance of a minigrid system

    Inputs:
        - simulation:
            Outputs of Energy_System().simulation(...).
        - start_year:
            Start year of this simulation period.
        - end_year:
            End year of this simulation period.

    Outputs:
        - system_outputs:
            A :class:`pd.DataFrame` containing key technical data e.g. energy used,
            unmet energy, blackout percentage, discounted energy.

    """

    # Calculate system blackouts
    system_blackouts: float = float(
        np.mean(simulation_results[ColumnHeader.BLACKOUTS.value].values)
    )

    # Energy system.
    total_energy = np.sum(
        simulation_results[ColumnHeader.TOTAL_ELECTRICITY_CONSUMED.value]
    )
    total_load_energy = np.sum(simulation_results[ColumnHeader.LOAD_ENERGY.value])
    total_renewables_used = np.sum(
        simulation_results[ColumnHeader.RENEWABLE_ELECTRICITY_USED_DIRECTLY.value]
    )
    total_pv_energy = np.sum(
        simulation_results[ColumnHeader.PV_ELECTRICITY_SUPPLIED.value]
    )
    total_pvt_energy = (
        np.sum(simulation_results[ColumnHeader.TOTAL_PVT_ELECTRICITY_SUPPLIED.value])
        if ColumnHeader.TOTAL_PVT_ELECTRICITY_SUPPLIED.value in simulation_results
        else None
    )
    total_storage_used = np.sum(
        simulation_results[ColumnHeader.ELECTRICITY_FROM_STORAGE.value]
    )
    total_grid_used = np.sum(simulation_results[ColumnHeader.GRID_ENERGY.value])
    total_diesel_used = np.sum(
        simulation_results[ColumnHeader.DIESEL_ENERGY_SUPPLIED.value]
    )
    total_unmet_energy = np.sum(
        simulation_results[ColumnHeader.UNMET_ELECTRICITY.value]
    )
    renewables_fraction = (total_renewables_used + total_storage_used) / total_energy
    unmet_fraction = total_unmet_energy / total_load_energy

    # Calculate total discounted energy
    total_energy_daily = hourly_profile_to_daily_sum(
        pd.DataFrame(simulation_results[ColumnHeader.TOTAL_ELECTRICITY_CONSUMED.value])
    )
    discounted_energy = finance.discounted_energy_total(
        finance_inputs,
        logger,
        total_energy_daily,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )

    # Calculate proportion of kerosene displaced (defaults to zero if kerosene is not
    # originally used
    if np.sum(simulation_results[ColumnHeader.KEROSENE_LAMPS.value]) > 0.0:
        kerosene_displacement = (
            np.sum(simulation_results[ColumnHeader.KEROSENE_MITIGATION.value])
        ) / (
            np.sum(simulation_results[ColumnHeader.KEROSENE_MITIGATION.value])
            + np.sum(simulation_results[ColumnHeader.KEROSENE_LAMPS.value])
        )
    else:
        kerosene_displacement = 0.0

    # Calculate diesel fuel usage
    total_diesel_fuel = np.sum(simulation_results[ColumnHeader.DIESEL_FUEL_USAGE.value])

    # Clean-water system.
    clean_water_blackouts: Optional[float] = (
        round(
            float(
                np.mean(
                    simulation_results[ColumnHeader.CLEAN_WATER_BLACKOUTS.value].values
                )
            ),
            3,
        )
        if ColumnHeader.CLEAN_WATER_BLACKOUTS.value in simulation_results
        else None
    )
    renewable_clean_water_fraction: float = (
        (
            (
                (
                    # Clean water taken from the thermal desalination plant(s) directly.
                    np.sum(
                        simulation_results[
                            ColumnHeader.CLEAN_WATER_FROM_RENEWABLES.value
                        ]
                        * simulation_results[
                            ColumnHeader.DESALINATION_PLANT_RENEWABLE_FRACTION.value
                        ]
                    )
                    if ColumnHeader.CLEAN_WATER_FROM_RENEWABLES.value
                    in simulation_results
                    else 0
                )
                # Clean water taken from tank storage.
                + np.sum(
                    simulation_results[ColumnHeader.CLEAN_WATER_FROM_STORAGE.value]
                )
                # Clean water generated using excess power in the minigrid.
                + np.sum(
                    simulation_results[
                        ColumnHeader.CLEAN_WATER_FROM_EXCESS_ELECTRICITY.value
                    ]
                )
                # Clean water generated using a prioritisation approach. This will be as
                # renewable as the electricity mix of the minigrid (on average).
                + (
                    renewables_fraction
                    * np.sum(
                        simulation_results[
                            ColumnHeader.CLEAN_WATER_FROM_PRIORITISATION.value
                        ]
                    )
                    if ColumnHeader.CLEAN_WATER_FROM_PRIORITISATION.value
                    in simulation_results
                    else 0
                )
            )
        )
        / (np.sum(simulation_results[ColumnHeader.TOTAL_CW_CONSUMED.value]))
        if ColumnHeader.TOTAL_CW_CONSUMED.value in simulation_results
        else 0
    )
    total_clean_water: float = (
        np.sum(simulation_results[ColumnHeader.TOTAL_CW_SUPPLIED.value])
        if ColumnHeader.TOTAL_CW_SUPPLIED.value in simulation_results
        else 0
    )

    # Hot-water system.
    hot_water_demand_covered: Optional[float] = (
        round(
            float(
                np.mean(
                    simulation_results[ColumnHeader.HW_RENEWABLES_FRACTION.value].values
                )
            ),
            3,
        )
        if ColumnHeader.HW_RENEWABLES_FRACTION.value in simulation_results
        else None
    )
    total_hot_water: float = (
        np.sum(simulation_results[ColumnHeader.HW_RENEWABLES_FRACTION.value])
        if ColumnHeader.HW_RENEWABLES_FRACTION.value in simulation_results
        else 0
    )

    # Return outputs
    return TechnicalAppraisal(
        round(system_blackouts, 3),
        clean_water_blackouts,
        round(total_diesel_used, 3),
        round(total_diesel_fuel, 3),
        round(discounted_energy, 3),
        round(total_grid_used, 3),
        hot_water_demand_covered,
        round(kerosene_displacement, 3),
        round(total_pv_energy, 3),
        round(total_pvt_energy, 3) if total_pvt_energy is not None else None,
        round(renewable_clean_water_fraction, 3),
        round(total_renewables_used, 3),
        round(renewables_fraction, 3),
        round(total_storage_used, 3),
        round(total_clean_water, 3),
        round(total_hot_water, 3),
        round(total_energy, 3),
        round(total_unmet_energy, 3),
        round(unmet_fraction, 3),
    )


def appraise_system(
    electric_yearly_load_statistics: pd.DataFrame,
    end_year: int,
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    location: Location,
    logger: Logger,
    previous_system: Optional[SystemAppraisal],
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
    converter_addition: Dict[str, int] = {
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
        finance_inputs, logger, simulation_results, system_details
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
        simulation_results,
        storage_addition,
        system_details,
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
        simulation_results,
        start_year,
        storage_addition,
        system_details,
    )

    # Get results that rely on metrics of different kinds and several different iteration periods
    cumulative_brine = (
        environmental_appraisal.total_brine + previous_system.cumulative_results.brine
    )
    if (
        technical_appraisal.total_clean_water > 0
        and previous_system.cumulative_results.clean_water is not None
    ):
        cumulative_clean_water: float = (
            technical_appraisal.total_clean_water
            + previous_system.cumulative_results.clean_water
        )
    else:
        logger.debug("No clean water produced.")
        cumulative_clean_water = 0
    cumulative_costs = (
        financial_appraisal.total_cost + previous_system.cumulative_results.cost
    )
    cumulative_discounted_energy = (
        technical_appraisal.discounted_energy
        + previous_system.cumulative_results.discounted_energy
    )
    cumulative_energy = (
        technical_appraisal.total_energy + previous_system.cumulative_results.energy
    )
    cumulative_ghgs = (
        environmental_appraisal.total_ghgs + previous_system.cumulative_results.ghgs
    )
    cumulative_system_costs = (
        financial_appraisal.total_system_cost
        + previous_system.cumulative_results.system_cost
    )
    cumulative_system_ghgs = (
        environmental_appraisal.total_system_ghgs
        + previous_system.cumulative_results.system_ghgs
    )

    # Combined metrics
    lcue = float(cumulative_system_costs / cumulative_discounted_energy)
    # lcuw = float(cumulative_system_costs / cumulative_discounted_clean_water)
    emissions_intensity = 1000.0 * float(cumulative_system_ghgs / cumulative_energy)

    #   Format outputs
    cumulative_results = CumulativeResults(
        cumulative_brine,
        cumulative_clean_water,
        cumulative_costs,
        cumulative_discounted_energy,
        cumulative_energy,
        cumulative_ghgs,
        cumulative_system_costs,
        cumulative_system_ghgs,
    )

    criteria = {
        Criterion.BLACKOUTS: round(technical_appraisal.blackouts, 3),
        Criterion.CLEAN_WATER_BLACKOUTS: round(
            technical_appraisal.clean_water_blackouts, 3
        ),
        Criterion.CUMULATIVE_BRINE: round(cumulative_results.brine, 3),
        Criterion.CUMULATIVE_COST: round(cumulative_results.cost, 3),
        Criterion.CUMULATIVE_GHGS: round(cumulative_results.ghgs, 3),
        Criterion.CUMULATIVE_SYSTEM_COST: round(cumulative_results.system_cost, 3),
        Criterion.CUMULATIVE_SYSTEM_GHGS: round(cumulative_results.system_ghgs, 3),
        Criterion.EMISSIONS_INTENSITY: round(emissions_intensity, 3),
        Criterion.HW_RENEWABLES_FRACTION: round(
            technical_appraisal.hw_demand_covered, 3
        ),
        Criterion.KEROSENE_COST_MITIGATED: round(
            financial_appraisal.kerosene_cost_mitigated, 3
        ),
        Criterion.KEROSENE_DISPLACEMENT: round(
            technical_appraisal.kerosene_displacement, 3
        ),
        Criterion.KEROSENE_GHGS_MITIGATED: round(
            environmental_appraisal.kerosene_ghgs_mitigated, 3
        ),
        Criterion.LCOW: round(lcow, 3),
        Criterion.LCUE: round(lcue, 3),
        Criterion.RENEWABLES_CLEAN_WATER_FRACTION: round(
            technical_appraisal.renewable_clean_water_fraction, 3
        ),
        Criterion.RENEWABLES_ELECTRICITY_FRACTION: round(
            technical_appraisal.renewable_energy_fraction, 3
        ),
        Criterion.RENEWABLES_HOT_WATER_FRACTION: round(
            technical_appraisal.renewable_hot_water_fraction, 3
        ),
        Criterion.SOLAR_THERMAL_CLEAN_WATER_FRACTION: round(
            technical_appraisal.solar_thermal_cw_fraction, 3
        ),
        Criterion.SOLAR_THERMAL_HOT_WATER_FRACTION: round(
            technical_appraisal.solar_thermal_hw_fraction, 3
        ),
        Criterion.TOTAL_BRINE: round(environmental_appraisal.total_brine, 3),
        Criterion.TOTAL_COST: round(financial_appraisal.total_cost, 3),
        Criterion.TOTAL_GHGS: round(environmental_appraisal.total_ghgs, 3),
        Criterion.TOTAL_SYSTEM_COST: round(financial_appraisal.total_system_cost, 3),
        Criterion.TOTAL_SYSTEM_GHGS: round(
            environmental_appraisal.total_system_ghgs, 3
        ),
        Criterion.UNMET_CLEAN_WATER_FRACTION: round(
            technical_appraisal.unmet_cw_fraction, 3
        ),
        Criterion.UNMET_ENERGY_FRACTION: round(
            technical_appraisal.unmet_energy_fraction, 3
        ),
        Criterion.SOLAR_THERMAL_HOT_WATER_FRACTION: round(
            technical_appraisal.solar_thermal_hw_fraction, 3
        ),
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
