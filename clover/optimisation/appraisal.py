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
from typing import Any, Dict

import numpy as np
import pandas as pd

from ..__utils__ import hourly_profile_to_daily_sum, Location
from ..impact.finance import (
    connections_expenditure,
    discounted_energy_total,
    discounted_equipment_cost,
    independent_expenditure,
    total_om,
)


def _simulation_financial_appraisal(
    finance_inputs: Dict[str, Any],
    location: Location,
    logger: Logger,
    simulation,
    yearly_load_statistics: pd.DataFrame,
    previous_systems: pd.DataFrame = pd.DataFrame([]),
) -> pd.DataFrame:
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

    # Initialise
    simulation_results = simulation[0]
    simulation_details = simulation[1]
    start_year = int(simulation_details.loc["System details"]["Start year"])
    end_year = int(simulation_details.loc["System details"]["End year"])
    installation_year = start_year
    system_outputs = pd.DataFrame(index=["System results"])

    # Check to see if a system was previously installed
    if previous_systems.empty:
        previous_system = pd.DataFrame(
            {
                "Final PV size": 0.0,
                "Final storage size": 0.0,
                "Diesel capacity": 0.0,
                "Total system cost ($)": 0.0,
                "Discounted energy (kWh)": 0.0,
            },
            index=["System details"],
        )
    else:
        previous_system = previous_systems.tail(1).reset_index(drop=True)
        previous_system = previous_system.rename({0: "System details"}, axis="index")

    # Calculate new PV, storage and diesel installations
    pv_addition = (
        simulation_details.loc["System details"]["Initial PV size"]
        - previous_system.loc["System details"]["Final PV size"]
    )
    storage_addition = (
        simulation_details.loc["System details"]["Initial storage size"]
        - previous_system.loc["System details"]["Final storage size"]
    )
    diesel_addition = (
        simulation_details.loc["System details"]["Diesel capacity"]
        - previous_system.loc["System details"]["Diesel capacity"]
    )
    #   Calculate new equipment costs (discounted)
    equipment_costs = discounted_equipment_cost(
        diesel_addition,
        finance_inputs,
        pv_addition,
        storage_addition,
        installation_year,
    ) + independent_expenditure(
        finance_inputs,
        location,
        yearly_load_statistics,
        start_year=start_year,
        end_year=end_year,
    )

    # Calculate costs of connecting new households (discounted)
    connections_cost = connections_expenditure(finance_inputs, simulation_results["Households"], installation_year)

    # Calculate operating costs of the system during this simulation (discounted)
    om_costs = total_om(system_details[DIESEL_CAPACITY], )
    OM_costs = Finance().get_total_OM(
        PV_array_size=simulation_details.loc["System details"]["Initial PV size"],
        storage_size=simulation_details.loc["System details"]["Initial storage size"],
        diesel_size=simulation_details.loc["System details"]["Diesel capacity"],
        start_year=start_year,
        end_year=end_year,
    )
    #   Calculate running costs of the system (discounted)
    diesel_costs = Finance().get_diesel_fuel_expenditure(
        diesel_fuel_usage_hourly=simulation_results["Diesel fuel usage (l)"],
        start_year=start_year,
        end_year=end_year,
    )
    grid_costs = Finance().get_grid_expenditure(
        grid_energy_hourly=simulation_results["Grid energy (kWh)"],
        start_year=start_year,
        end_year=end_year,
    )
    kerosene_costs = Finance().get_kerosene_expenditure(
        kerosene_lamps_in_use_hourly=simulation_results["Kerosene lamps"],
        start_year=start_year,
        end_year=end_year,
    )
    kerosene_costs_mitigated = Finance().get_kerosene_expenditure_mitigated(
        kerosene_lamps_mitigated_hourly=simulation_results["Kerosene mitigation"],
        start_year=start_year,
        end_year=end_year,
    )
    #   Total cost incurred during simulation period (discounted)
    total_cost = (
        equipment_costs
        + connections_cost
        + OM_costs
        + diesel_costs
        + grid_costs
        + kerosene_costs
    )
    total_system_cost = (
        equipment_costs + connections_cost + OM_costs + diesel_costs + grid_costs
    )
    #   Return outputs
    system_outputs["Total cost ($)"] = total_cost
    system_outputs["Total system cost ($)"] = total_system_cost
    system_outputs["New equipment cost ($)"] = equipment_costs
    system_outputs["New connection cost ($)"] = connections_cost
    system_outputs["O&M cost ($)"] = OM_costs
    system_outputs["Diesel cost ($)"] = diesel_costs
    system_outputs["Grid cost ($)"] = grid_costs
    system_outputs["Kerosene cost ($)"] = kerosene_costs
    system_outputs["Kerosene cost mitigated ($)"] = kerosene_costs_mitigated
    return system_outputs.round(2)


def _simulation_technical_appraisal(
    finance_inputs: Dict[str, Any], logger: Logger, simulation
):
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

    # Initialise
    simulation_results = simulation[0]
    simulation_details = simulation[1]
    start_year = simulation_details.loc["System details"]["Start year"]
    end_year = simulation_details.loc["System details"]["End year"]
    system_outputs = pd.DataFrame(index=["System results"])

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
    discounted_energy = discounted_energy_total(
        finance_inputs,
        logger,
        total_energy_daily,
        start_year=start_year,
        end_year=end_year,
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
    system_outputs["Blackouts"] = system_blackouts
    system_outputs["Unmet energy fraction"] = unmet_fraction
    system_outputs["Renewables fraction"] = renewables_fraction
    system_outputs["Total energy (kWh)"] = total_energy
    system_outputs["Unmet energy (kWh)"] = total_unmet_energy
    system_outputs["Renewable energy (kWh)"] = total_renewables_used
    system_outputs["Storage energy (kWh)"] = total_storage_used
    system_outputs["Grid energy (kWh)"] = total_grid_used
    system_outputs["Diesel energy (kWh)"] = total_diesel_used
    system_outputs["Discounted energy (kWh)"] = discounted_energy
    system_outputs["Kerosene displacement"] = kerosene_displacement
    system_outputs["Diesel fuel usage (l)"] = total_diesel_fuel

    return system_outputs.round(3)


def appraise_system(
    finance_inputs: Dict[str, Any],
    location: Location,
    logger: Logger,
    simulation,
    yearly_load_statistics: pd.DataFrame,
    previous_systems: pd.DataFrame = pd.DataFrame([]),
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
    else:
        previous_system = previous_systems.tail(1).reset_index(drop=True)
        previous_system = previous_system.rename({0: "System results"}, axis="index")

    combined_outputs = pd.DataFrame(index=["System results"])

    # Get results which will be carried forward into optimisation process
    system_details = simulation[1].rename(
        {"System details": "System results"}, axis="index"
    )
    technical_results = _simulation_technical_appraisal(
        finance_inputs, logger, simulation
    )
    financial_results = _simulation_financial_appraisal(
        finance_inputs,
        location,
        logger,
        simulation,
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
