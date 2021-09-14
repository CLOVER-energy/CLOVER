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

import numpy as np  # type: ignore  # pylint: disable=import-error
import pandas as pd  # type: ignore  # pylint: disable=import-error

from ..impact import finance, ghgs

from ..__utils__ import (
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
from ..impact.__utils__ import ImpactingComponent

__all__ = ("appraise_system",)


def _simulation_environmental_appraisal(
    electric_yearly_load_statistics: pd.DataFrame,
    end_year: int,
    ghg_inputs: Dict[str, Any],
    location: Location,
    previous_system_details: SystemDetails,
    simulation_results: pd.DataFrame,
    start_year: int,
    system_details: SystemDetails,
) -> EnvironmentalAppraisal:
    """
    Appraises the environmental impact of a minigrid system

    Inputs:
        - electric_yearly_load_statistics:
            The yearly electric load statistics.
        - end_year:
            The end year of the simulation period.
        - ghg_inputs:
            The GHG input information.
        - location:
            The location being considered.
        - previous_system_details:
            The system details of the previous system simulated.
        - simulation_results:
            The system that was just simulated.
        - start_year:
            The start year for the simulation period.
        - system_details:
            The deatils of the system that was just simulated.

    Outputs:
        An :class:`EnvironmentalAppraisal` containing the key environmental results.

    """

    # Calculate new PV, storage and diesel installations
    pv_addition = system_details.initial_pv_size - previous_system_details.final_pv_size
    storage_addition = (
        system_details.initial_storage_size - previous_system_details.diesel_capacity
    )
    diesel_addition = (
        system_details.diesel_capacity - previous_system_details.diesel_capacity
    )

    # Calculate new equipment GHGs
    equipment_ghgs = ghgs.calculate_total_equipment_ghgs(
        diesel_addition, ghg_inputs, pv_addition, storage_addition
    ) + ghgs.calculate_independent_ghgs(
        electric_yearly_load_statistics, end_year, ghg_inputs, location, start_year
    )

    # Calculate GHGs of connecting new households
    connections_ghgs = ghgs.calculate_connections_ghgs(
        ghg_inputs, simulation_results["Households"]
    )

    # Calculate operating GHGs of the system during this simulation
    om_ghgs = ghgs.calculate_total_om(
        system_details.diesel_capacity,
        ghg_inputs,
        system_details.initial_pv_size,
        system_details.initial_storage_size,
        start_year,
        end_year,
    )

    # Calculate running GHGs of the system
    diesel_fuel_ghgs = ghgs.calculate_diesel_fuel_ghgs(
        simulation_results["Diesel fuel usage (l)"], ghg_inputs
    )
    grid_ghgs = ghgs.calculate_grid_ghgs(
        ghg_inputs,
        simulation_results["Grid energy (kWh)"],
        location,
        start_year,
        end_year,
    )
    kerosene_ghgs = ghgs.calculate_kerosene_ghgs(
        ghg_inputs, simulation_results["Kerosene lamps"]
    )
    kerosene_ghgs_mitigated = ghgs.calculate_kerosene_ghgs_mitigated(
        ghg_inputs, simulation_results["Kerosene mitigation"]
    )

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
        round(total_ghgs, 3),
        round(total_system_ghgs, 3),
    )


def _simulation_financial_appraisal(
    finance_inputs: Dict[str, Any],
    location: Location,
    logger: Logger,
    simulation_results,
    system_details: SystemDetails,
    yearly_load_statistics: pd.DataFrame,
    previous_system_details: SystemDetails,
) -> FinancialAppraisal:
    """
    Appraises the financial performance of a minigrid system.

    Inputs:
        - finance_inputs:
            The finance input information.
        - logger:
            The logger to use for the run.
        - simulation
            Outputs of Energy_System().simulation(...)
        - previous_systems:
            Report from previously installed system (not required if no system was
            previously deployed)

    Outputs:
        The financial appraisal of the system.

    """

    # Calculate new PV, storage and diesel installations
    pv_addition = system_details.initial_pv_size - previous_system_details.final_pv_size
    storage_addition = (
        system_details.initial_storage_size - previous_system_details.final_storage_size
    )
    diesel_addition = (
        system_details.diesel_capacity - previous_system_details.diesel_capacity
    )
    #   Calculate new equipment costs (discounted)
    equipment_costs = finance.discounted_equipment_cost(
        diesel_addition,
        finance_inputs,
        pv_addition,
        storage_addition,
        system_details.start_year,
    ) + finance.independent_expenditure(
        finance_inputs,
        location,
        yearly_load_statistics,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )

    # Calculate costs of connecting new households (discounted)
    connections_cost = finance.connections_expenditure(
        finance_inputs,
        simulation_results["Households"],
        system_details.start_year,
    )

    # Calculate operating costs of the system during this simulation (discounted)
    om_costs = finance.total_om(
        system_details.diesel_capacity,
        finance_inputs,
        logger,
        system_details.initial_pv_size,
        system_details.initial_storage_size,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )

    # Calculate running costs of the system (discounted)
    diesel_costs = finance.diesel_fuel_expenditure(
        simulation_results["Diesel fuel usage (l)"],
        finance_inputs,
        logger,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )
    grid_costs = finance.expenditure(
        ImpactingComponent.GRID,
        finance_inputs,
        simulation_results["Grid energy (kWh)"],
        logger,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )
    kerosene_costs = finance.expenditure(
        ImpactingComponent.KEROSENE,
        finance_inputs,
        simulation_results["Kerosene lamps"],
        logger,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )
    kerosene_costs_mitigated = finance.expenditure(
        ImpactingComponent.KEROSENE,
        finance_inputs,
        simulation_results["Kerosene mitigation"],
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
    system_blackouts: float = float(np.mean(simulation_results["Blackouts"].values))
    clean_water_blackouts: Optional[float] = (
        round(float(np.mean(simulation_results["Clean water blackouts"].values)), 3)
        if "Clean water blackouts" in simulation_results
        else None
    )

    # Total energy used
    total_energy = np.sum(simulation_results["Total energy used (kWh)"])  # type: ignore
    total_load_energy = np.sum(simulation_results["Load energy (kWh)"])  # type: ignore
    total_renewables_used = np.sum(
        simulation_results["Renewables energy used (kWh)"]  # type: ignore
    )
    total_storage_used = np.sum(
        simulation_results["Storage energy supplied (kWh)"]  # type: ignore
    )
    total_grid_used = np.sum(simulation_results["Grid energy (kWh)"])  # type: ignore
    total_diesel_used = np.sum(
        simulation_results["Diesel energy (kWh)"]  # type: ignore
    )
    total_unmet_energy = np.sum(
        simulation_results["Unmet energy (kWh)"]  # type: ignore
    )
    renewables_fraction = (total_renewables_used + total_storage_used) / total_energy
    unmet_fraction = total_unmet_energy / total_load_energy

    # Calculate total discounted energy
    total_energy_daily = hourly_profile_to_daily_sum(
        pd.DataFrame(simulation_results["Total energy used (kWh)"])
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
    if np.sum(simulation_results["Kerosene lamps"]) > 0.0:  # type: ignore
        kerosene_displacement = (
            np.sum(simulation_results["Kerosene mitigation"])  # type: ignore
        ) / (
            np.sum(simulation_results["Kerosene mitigation"])  # type: ignore
            + np.sum(simulation_results["Kerosene lamps"])  # type: ignore
        )
    else:
        kerosene_displacement = 0.0

    # Calculate diesel fuel usage
    total_diesel_fuel = np.sum(
        simulation_results["Diesel fuel usage (l)"]  # type: ignore
    )

    # Return outputs
    return TechnicalAppraisal(
        round(system_blackouts, 3),
        clean_water_blackouts,
        round(total_diesel_used, 3),
        round(total_diesel_fuel, 3),
        round(discounted_energy, 3),
        round(total_grid_used, 3),
        round(kerosene_displacement, 3),
        round(total_renewables_used, 3),
        round(renewables_fraction, 3),
        round(total_storage_used, 3),
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
            CumulativeResults(0, 0, 0, 0, 0, 0),
            EnvironmentalAppraisal(0, 0, 0, 0, 0, 0, 0, 0, 0),
            FinancialAppraisal(
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ),
            SystemDetails(
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ),
            TechnicalAppraisal(
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ),
        )

    # Get results which will be carried forward into optimisation process
    technical_appraisal = _simulation_technical_appraisal(
        finance_inputs, logger, simulation_results, system_details
    )

    financial_appraisal = _simulation_financial_appraisal(
        finance_inputs,
        location,
        logger,
        simulation_results,
        system_details,
        electric_yearly_load_statistics,
        previous_system_details=previous_system.system_details,
    )
    environmental_appraisal = _simulation_environmental_appraisal(
        electric_yearly_load_statistics,
        end_year,
        ghg_inputs,
        location,
        previous_system.system_details,
        simulation_results,
        start_year,
        system_details,
    )

    # Get results that rely on metrics of different kinds and several different iteration periods
    cumulative_costs = (
        financial_appraisal.total_cost + previous_system.cumulative_results.cost
    )
    cumulative_system_costs = (
        financial_appraisal.total_system_cost
        + previous_system.cumulative_results.system_cost
    )
    cumulative_ghgs = (
        environmental_appraisal.total_ghgs + previous_system.cumulative_results.ghgs
    )
    cumulative_system_ghgs = (
        environmental_appraisal.total_system_ghgs
        + previous_system.cumulative_results.system_ghgs
    )
    cumulative_energy = (
        technical_appraisal.total_energy + previous_system.cumulative_results.energy
    )
    cumulative_discounted_energy = (
        technical_appraisal.discounted_energy
        + previous_system.cumulative_results.discounted_energy
    )

    # Combined metrics
    lcue = float(cumulative_system_costs / cumulative_discounted_energy)
    emissions_intensity = 1000.0 * float(cumulative_system_ghgs / cumulative_energy)

    #   Format outputs
    cumulative_results = CumulativeResults(
        cumulative_costs,
        cumulative_discounted_energy,
        cumulative_energy,
        cumulative_ghgs,
        cumulative_system_costs,
        cumulative_system_ghgs,
    )

    criteria = {
        Criterion.BLACKOUTS: round(technical_appraisal.blackouts, 3),
        Criterion.CUMULATIVE_COST: round(cumulative_results.cost, 3),
        Criterion.CUMULATIVE_GHGS: round(cumulative_results.ghgs, 3),
        Criterion.EMISSIONS_INTENSITY: round(emissions_intensity, 3),
        Criterion.LCUE: round(lcue, 3),
        Criterion.UNMET_ENERGY_FRACTION: round(
            technical_appraisal.unmet_energy_fraction, 3
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
