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

import dataclasses

from logging import Logger
from typing import Any, Dict, List, Optional, Tuple

import numpy as np  # type: ignore
import pandas as pd  # type: ignore

from ..__utils__ import hourly_profile_to_daily_sum, Location, SystemDetails
from ..impact.finance import (
    ImpactingComponent,
    connections_expenditure,
    diesel_fuel_expenditure,
    discounted_equipment_cost,
    discounted_total,
    expenditure,
    independent_expenditure,
    total_om,
)


@dataclasses.dataclass
class FinancialAppraisal:
    """
    Contains financial-appraisal information.

    .. attribute:: diesel_cost
        The cost of diesel fuel used, measured in USD.

    .. attribute:: grid_cost
        The cost of grid energy used, measured in USD.

    .. attribute:: kerosene_cost
        The cost of kerosene used, measured in USD.

    .. attribute:: kerosene_cost_mitigated
        The value of the kerosene which was not used, measured in USD.

    .. attribute:: new_connection_cost
        <<description needed>>, measured in USD

    .. attribute:: new_equipment_cost
        <<description needed>>, measured in USD

    .. attribute:: om_cost
        The O&M cost, measured in USD.

    .. attribute:: total_cost
        <<description needed>>, measured in USD

    .. attribute:: total_system_cost
        <<description needed>>, measured in USD

    """

    diesel_cost: float
    grid_cost: float
    kerosene_cost: float
    kerosene_cost_mitigated: float
    new_connection_cost: float
    new_equipment_cost: float
    om_cost: float
    total_cost: float
    total_system_cost: float


@dataclasses.dataclass
class TechnicalAppraisal:
    """
    Contains financial-appraisal information.

    .. attribute:: blackouts
        <<description needed>>, measured in USD

    .. attribute:: diesel_energy
        <<description needed>>, measured in USD

    .. attribute:: diesel_fuel_usage
        <<description needed>>, measured in USD

    .. attribute:: discounted_energy
        <<description needed>>, measured in USD

    .. attribute:: grid_energy
        <<description needed>>, measured in USD

    .. attribute:: kerosene_displacement
        <<description needed>>, measured in USD

    .. attribute:: new_connection_cost
        <<description needed>>, measured in USD

    .. attribute:: renewable_energy
        <<description needed>>, measured in USD

    .. attribute:: renewable_energy_fraction
        <<description needed>>, measured in USD

    .. attribute:: storage_energy
        <<description needed>>, measured in USD

    .. attribute:: total_energy
        <<description needed>>, measured in USD

    .. attribute:: unmet_energy
        <<description needed>>, measured in USD

    .. attribute:: unmet_energy_fraction
        <<description needed>>, measured in USD

    """

    blackouts: float
    diesel_energy: float
    diesel_fuel_usage: float
    discounted_energy: float
    grid_energy: float
    kerosene_displacement: float
    renewable_energy: float
    renewable_energy_fraction: float
    storage_energy: float
    total_energy: float
    unmet_energy: float
    unmet_energy_fraction: float


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
    pv_addition = (
        system_details.initial_system_size - previous_system_details.final_pv_size
    )
    storage_addition = (
        system_details.initial_storage_size - previous_system_details.final_storage_size
    )
    diesel_addition = (
        system_details.diesel_capacity - previous_system_details.diesel_capacity
    )
    #   Calculate new equipment costs (discounted)
    equipment_costs = discounted_equipment_cost(
        diesel_addition,
        finance_inputs,
        pv_addition,
        storage_addition,
        system_details.start_year,
    ) + independent_expenditure(
        finance_inputs,
        location,
        yearly_load_statistics,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )

    # Calculate costs of connecting new households (discounted)
    connections_cost = connections_expenditure(
        finance_inputs,
        simulation_results["Households"],
        system_details.start_year,
    )

    # Calculate operating costs of the system during this simulation (discounted)
    om_costs = total_om(
        system_details.diesel_capacity,
        finance_inputs,
        logger,
        system_details.initial_pv_size,
        system_details.initial_storage_size,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )

    # Calculate running costs of the system (discounted)
    diesel_costs = diesel_fuel_expenditure(
        simulation_results["Diesel fuel usage (l)"],
        finance_inputs,
        logger,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )
    grid_costs = expenditure(
        ImpactingComponent.GRID,
        finance_inputs,
        simulation_results["Grid energy (kWh)"],
        logger,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )
    kerosene_costs = expenditure(
        ImpactingComponent.KEROSENE,
        finance_inputs,
        simulation_results["Kerosene lamps"],
        logger,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )
    kerosene_costs_mitigated = expenditure(
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
        diesel_costs.round(2),
        grid_costs.round(2),
        kerosene_costs.round(2),
        kerosene_costs_mitigated.round(2),
        connections_cost.round(2),
        equipment_costs.round(2),
        total_cost.round(2),
        total_system_cost.round(2),
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
    system_blackouts = np.mean(simulation_results["Blackouts"])

    # Total energy used
    total_energy = np.sum(simulation_results["Total energy used (kWh)"])
    total_load_energy = np.sum(simulation_results["Load energy (kWh)"])
    total_renewables_used = np.sum(simulation_results["Renewables energy used (kWh)"])
    total_storage_used = np.sum(simulation_results["Storage energy supplied (kWh)"])
    total_grid_used = np.sum(simulation_results["Grid energy (kWh)"])
    total_diesel_used = np.sum(simulation_results["Diesel energy (kWh)"])
    total_unmet_energy = np.sum(simulation_results["Unmet energy (kWh)"])
    renewables_fraction = (total_renewables_used + total_storage_used) / total_energy
    unmet_fraction = total_unmet_energy / total_load_energy

    # Calculate total discounted energy
    total_energy_daily = hourly_profile_to_daily_sum(
        simulation_results["Total energy used (kWh)"]
    )
    discounted_energy = discounted_total(
        finance_inputs,
        logger,
        total_energy_daily,
        start_year=system_details.start_year,
        end_year=system_details.end_year,
    )

    # Calculate proportion of kerosene displaced (defaults to zero if kerosene is not
    # originally used
    if np.sum(simulation_results["Kerosene lamps"]) > 0.0:
        kerosene_displacement = (np.sum(simulation_results["Kerosene mitigation"])) / (
            np.sum(simulation_results["Kerosene mitigation"])
            + np.sum(simulation_results["Kerosene lamps"])
        )
    else:
        kerosene_displacement = 0.0

    # Calculate diesel fuel usage
    total_diesel_fuel = np.sum(simulation_results["Diesel fuel usage (l)"])

    # Return outputs
    return TechnicalAppraisal(
        system_blackouts.round(3),
        total_diesel_used.round(3),
        total_diesel_fuel.round(3),
        discounted_energy.round(3),
        total_grid_used.round(3),
        kerosene_displacement.round(3),
        total_renewables_used.round(3),
        renewables_fraction.round(3),
        total_storage_used.round(3),
        total_energy.round(3),
        total_unmet_energy.round(3),
        unmet_fraction.round(3).round(3),
    )


def appraise_system(
    finance_inputs: Dict[str, Any],
    location: Location,
    logger: Logger,
    simulation: pd.DataFrame,
    system_details: SystemDetails,
    yearly_load_statistics: pd.DataFrame,
    previous_systems: Optional[List[Tuple[pd.DataFrame, SystemDetails]]] = None,
) -> pd.DataFrame:
    """
    Appraises the total performance of a minigrid system for all performance metrics

    Inputs:
        - finance_inputs:
            The finance input information.
        - location:
            The location currently being considered.
        - logger:
            The logger to use for the run.
        - simulation
            Outputs of Energy_System().simulation(...)
        - previous_systems:
            Report from previously installed system (not required if no system was
            previously deployed)

    Outputs:
        - system_outputs:
            :class:`pd.DataFrame` containing all key technical, performance,
            financial and environmental information.

    """

    # Check to see if a system was previously installed
    if previous_systems is None:
        # previous_system = pd.DataFrame(
        #     {
        #         "Final PV size": 0.0,
        #         "Final storage size": 0.0,
        #         "Diesel capacity": 0.0,
        #         "Total system cost ($)": 0.0,
        #         "Discounted energy (kWh)": 0.0,
        #     },
        #     index=["System details"],
        # )
        previous_system_details: SystemDetails = SystemDetails(
            0, None, 0, 0, None, None, None, discounted_energy=0, total_system_cost=None
        )
    else:
        previous_system_details = previous_systems[-1][1]

    if previous_systems.empty:
        previous_system = pd.DataFrame(
            {
                "Final PV size": 0.0,
                "Final storage size": 0.0,
                "Diesel capacity": 0.0,
                "Total system cost ($)": 0.0,
                "Total system GHGs (kgCO2eq)": 0.0,
                "Discounted energy (kWh)": 0.0,
                "Cumulative cost ($)": 0.0,
                "Cumulative system cost ($)": 0.0,
                "Cumulative GHGs (kgCO2eq)": 0.0,
                "Cumulative system GHGs (kgCO2eq)": 0.0,
                "Cumulative energy (kWh)": 0.0,
                "Cumulative discounted energy (kWh)": 0.0,
            },
            index=["System results"],
        )
        previous_system_details = SystemDetails(0, None, 0, 0, None, None, None, None)
    else:
        previous_system = previous_systems.tail(1).reset_index(drop=True)
        previous_system = previous_system.rename({0: "System results"}, axis="index")

    combined_outputs = pd.DataFrame(index=["System results"])

    # Get results which will be carried forward into optimisation process
    system_details = simulation[1].rename(
        {"System details": "System results"}, axis="index"
    )
    technical_results = _simulation_technical_appraisal(
        finance_inputs, logger, simulation, system_details
    )

    financial_results = _simulation_financial_appraisal(
        finance_inputs,
        location,
        logger,
        simulation,
        system_details,
        yearly_load_statistics,
        previous_systems=previous_systems,
    )
    environmental_results = self.simulation_environmental_appraisal(
        simulation, previous_systems=previous_systems
    )

    #   Get results that rely on metrics of different kinds and several different iteration periods
    cumulative_costs = (
        financial_results["Total cost ($)"] + previous_system["Cumulative cost ($)"]
    )
    cumulative_system_costs = (
        financial_results["Total system cost ($)"]
        + previous_system["Cumulative system cost ($)"]
    )
    cumulative_GHGs = (
        environmental_results["Total GHGs (kgCO2eq)"]
        + previous_system["Cumulative GHGs (kgCO2eq)"]
    )
    cumulative_system_GHGs = (
        environmental_results["Total system GHGs (kgCO2eq)"]
        + previous_system["Cumulative system GHGs (kgCO2eq)"]
    )
    cumulative_energy = (
        technical_results["Total energy (kWh)"]
        + previous_system["Cumulative energy (kWh)"]
    )
    cumulative_discounted_energy = (
        technical_results["Discounted energy (kWh)"]
        + previous_system["Cumulative discounted energy (kWh)"]
    )
    #   Combined metrics
    LCUE = float(cumulative_system_costs / cumulative_discounted_energy)
    emissions_intensity = 1000.0 * float(
        cumulative_system_GHGs / cumulative_energy
    )  # in grams
    #   Format outputs
    combined_outputs["Cumulative cost ($)"] = cumulative_costs
    combined_outputs["Cumulative system cost ($)"] = cumulative_system_costs
    combined_outputs["Cumulative GHGs (kgCO2eq)"] = cumulative_GHGs
    combined_outputs["Cumulative system GHGs (kgCO2eq)"] = cumulative_system_GHGs
    combined_outputs["Cumulative energy (kWh)"] = cumulative_energy
    combined_outputs[
        "Cumulative discounted energy (kWh)"
    ] = cumulative_discounted_energy
    combined_outputs["LCUE ($/kWh)"] = np.round(LCUE, 3)
    combined_outputs["Emissions intensity (gCO2/kWh)"] = np.round(
        emissions_intensity, 3
    )
    #   Return results
    system_outputs = pd.concat(
        [
            system_details,
            combined_outputs,
            technical_results,
            financial_results,
            environmental_results,
        ],
        axis=1,
    )
    return system_outputs
