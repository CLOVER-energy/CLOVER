#!/usr/bin/python3
########################################################################################
# optimisation.py - Optimisation module.                                               #
#                                                                                      #
# Authors: Phil Sandwell                                                               #
# Copyright: Phil Sandwell, 2018                                                       #
# License: Open source                                                                 #
# Most recent update: 14/07/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
optimisation.py - The optimisation module of CLOVER.

This module carries out an optimisation of an energy system and exposes several
functions which can be used to carry out an optimisation:
    - simulation_iteration(...):
        Scans the defined range of systems and returns sufficient systems;
    - optimisation_step(...)
        Takes the sufficient systems and returns the optimum system;
    - single_line_simulation(...)
        An additional row of simulations if the optimum is an edge case;
    - find_optimum_system(...)
        Locates the optimum system including edge case considerations;
    - multiple_optimisation_step(...)
        Sequential optimisaiton steps over the entire optimisation period;
    - changing_parameter_optimisation(...)
        Allows a parameter to be changed to perform many optimisations.

"""

import datetime

from logging import Logger
from typing import Any, Dict, List, Optional, Tuple

import numpy as np  # type: ignore  # pylint: disable=import-error
import pandas as pd  # type: ignore  # pylint: disable=import-error

from tqdm import tqdm  # type: ignore  # pylint: disable=import-error

from ..simulation import energy_system

from ..__utils__ import (
    DONE,
    InternalError,
    Scenario,
    Location,
    OptimisationParameters,
    Simulation,
)
from ..conversion.conversion import Convertor
from .appraisal import appraise_system, SystemAppraisal
from .__utils__ import (
    Criterion,
    CriterionMode,
    Optimisation,
    PVSystemSize,
    StorageSystemSize,
    ThresholdMode,
)

__all__ = ("multiple_optimisation_step",)


# Threshold-criterion-to-mode mapping:
#   Maps the threshold criteria to the modes, i.e., whether they are maximisable or
#   minimisable.
THRESHOLD_CRITERION_TO_MODE: Dict[Criterion, ThresholdMode] = {
    Criterion.BLACKOUTS: ThresholdMode.MAXIMUM,
    Criterion.EMISSIONS_INTENSITY: ThresholdMode.MAXIMUM,
    Criterion.UNMET_ENERGY_FRACTION: ThresholdMode.MAXIMUM,
}


def _fetch_optimum_system(
    optimisation: Optimisation, sufficient_systems: List[SystemAppraisal]
) -> Dict[Criterion, SystemAppraisal]:
    """
    Identifies the optimum system from a group of sufficient systems

    Inputs:
        - optimisation:
            The optimisation currently being carried out.
        - sufficient_systems:
            A `list` of sufficient system appraisals

    Outputs:
        - A mapping between the optimisation criterion and the corresponding optimum
          system as a :class:`SystemAppraisal`.

    """

    optimum_systems: Dict[Criterion, SystemAppraisal] = dict()

    # Run through the various optimisation criteria.
    for (criterion, criterion_mode) in optimisation.optimisation_criteria.items():
        # Sort by the optimisation criterion.
        sufficient_systems.sort(
            key=lambda appraisal, crit=criterion: appraisal.criteria[crit],  # type: ignore
            reverse=(criterion_mode == CriterionMode.MAXIMISE),
        )

        # Add the optimum system, keyed by the optimisation criterion.
        optimum_systems[criterion] = sufficient_systems[0]

    return optimum_systems


def _single_line_simulation(
    convertors: List[Convertor],
    end_year: int,
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    grid_profile: pd.DataFrame,
    kerosene_usage: pd.DataFrame,
    pv_system_size: PVSystemSize,
    storage_size: StorageSystemSize,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    num_clean_water_tanks: int,
    optimisation: Optimisation,
    potential_system: SystemAppraisal,
    previous_system: Optional[SystemAppraisal],
    scenario: Scenario,
    start_year: int,
    total_clean_water_load: Optional[pd.DataFrame],
    total_electric_load: pd.DataFrame,
    total_solar_power_produced: pd.DataFrame,
    yearly_electric_load_statistics: pd.DataFrame,
) -> Tuple[PVSystemSize, StorageSystemSize, List[SystemAppraisal]]:
    """
    Preforms an additional round of simulations.

    If the potential optimum system was found to be an edge case (either maximum PV
    capacity, storage capacity or both) then this function can be called to carry out an
    additional simulation.

    Inputs:
        - largest_pv_size:
            The largest PV size that was simulated.
        - storage_size:
            The largest storage size that was simulated.
        - logger:
            The logger to use for the run.
        - potential_system:
            The system assumed to be the optimum, before this process
        - previous_system:
            The system that was previously installed

    Outputs:
        - pv_system_size:
            The pv system size of the largest system considered.
        - storage_size:
            The storage size of the largest system considered.
        - system_appraisals:
            The set of system appraisals considered.

    """

    # Instantiate
    logger.info("Single-line optimisation to be carried out.")
    system_appraisals: List[SystemAppraisal] = []

    # Check to see if storage size was an integer number of steps, and increase
    # accordingly.
    if (
        np.ceil(storage_size.max / storage_size.step) * storage_size.step
        == storage_size.max
    ):
        test_storage_size = float(storage_size.max + storage_size.step)
    else:
        test_storage_size = float(
            np.ceil(storage_size.max / storage_size.step) * storage_size.step
        )

    # If storage was maxed out:
    if potential_system.system_details.initial_storage_size == storage_size.max:
        logger.info("Increasing storage size.")

        # Increase and iterate over PV size
        for iteration_pv_size in tqdm(
            sorted(
                range(
                    int(pv_system_size.min),
                    int(np.ceil(pv_system_size.max + pv_system_size.step)),
                    int(pv_system_size.step),
                ),
                reverse=True,
            ),
            desc="probing pv sizes",
            leave=False,
            unit="simulation",
        ):
            # Run a simulation.
            _, simulation_results, system_details = energy_system.run_simulation(
                convertors,
                minigrid,
                grid_profile,
                kerosene_usage,
                location,
                logger,
                num_clean_water_tanks,
                iteration_pv_size,
                scenario,
                Simulation(end_year, start_year),
                test_storage_size,
                total_clean_water_load,
                total_electric_load,
                total_solar_power_produced,
            )

            # Appraise the system.
            new_appraisal = appraise_system(
                yearly_electric_load_statistics,
                end_year,
                finance_inputs,
                ghg_inputs,
                location,
                logger,
                previous_system,
                simulation_results,
                start_year,
                system_details,
            )

            if _get_sufficient_appraisals(optimisation, [new_appraisal]) == []:
                break
            system_appraisals.append(new_appraisal)

        # If the maximum PV system size isn't a round number of steps, carry out a
        # simulation at this size..
        if (
            np.ceil(pv_system_size.max / pv_system_size.step) * pv_system_size.step
            != pv_system_size.max
        ):
            _, simulation_results, system_details = energy_system.run_simulation(
                convertors,
                minigrid,
                grid_profile,
                kerosene_usage,
                location,
                logger,
                num_clean_water_tanks,
                pv_system_size.max,
                scenario,
                Simulation(end_year, start_year),
                test_storage_size,
                total_clean_water_load,
                total_electric_load,
                total_solar_power_produced,
            )

            # Appraise the system.
            new_appraisal = appraise_system(
                yearly_electric_load_statistics,
                end_year,
                finance_inputs,
                ghg_inputs,
                location,
                logger,
                previous_system,
                simulation_results,
                start_year,
                system_details,
            )

            if _get_sufficient_appraisals(optimisation, [new_appraisal]) != []:
                system_appraisals.append(new_appraisal)

        # Update the system details.
        storage_size.max = test_storage_size

    # Check to see if PV size was an integer number of steps, and increase accordingly
    if (
        np.ceil(pv_system_size.max / pv_system_size.step) * pv_system_size.step
        == pv_system_size.max
    ):
        test_pv_size = float(pv_system_size.max + pv_system_size.step)
    else:
        test_pv_size = float(
            np.ceil(pv_system_size.max / pv_system_size.step) * pv_system_size.step
        )

    #   If PV was maxed out:
    if potential_system.system_details.initial_pv_size == pv_system_size.max:
        logger.info("Increasing PV size.")

        # Increase  and iterate over storage size
        for iteration_storage_size in tqdm(
            sorted(
                range(
                    int(storage_size.min),
                    int(np.ceil(storage_size.max + storage_size.step)),
                    int(storage_size.step),
                ),
                reverse=True,
            ),
            desc="probing storage sizes",
            leave=False,
            unit="simulation",
        ):
            # Run a simulation.
            _, simulation_results, system_details = energy_system.run_simulation(
                convertors,
                minigrid,
                grid_profile,
                kerosene_usage,
                location,
                logger,
                num_clean_water_tanks,
                test_pv_size,
                scenario,
                Simulation(end_year, start_year),
                iteration_storage_size,
                total_clean_water_load,
                total_electric_load,
                total_solar_power_produced,
            )

            # Appraise the system.
            new_appraisal = appraise_system(
                yearly_electric_load_statistics,
                end_year,
                finance_inputs,
                ghg_inputs,
                location,
                logger,
                previous_system,
                simulation_results,
                start_year,
                system_details,
            )

            if _get_sufficient_appraisals(optimisation, [new_appraisal]) == []:
                break

            system_appraisals.append(new_appraisal)

        # If the maximum storage size wasn't a round number of steps, then carry out a
        # simulation run at this storage size.
        if (
            np.ceil(storage_size.max / storage_size.step) * storage_size.step
            != storage_size.max
        ):
            # Run a simulation.
            _, simulation_results, system_details = energy_system.run_simulation(
                convertors,
                minigrid,
                grid_profile,
                kerosene_usage,
                location,
                logger,
                num_clean_water_tanks,
                test_pv_size,
                scenario,
                Simulation(end_year, start_year),
                storage_size.max,
                total_clean_water_load,
                total_electric_load,
                total_solar_power_produced,
            )

            # Appraise the system.
            new_appraisal = appraise_system(
                yearly_electric_load_statistics,
                end_year,
                finance_inputs,
                ghg_inputs,
                location,
                logger,
                previous_system,
                simulation_results,
                start_year,
                system_details,
            )

            if _get_sufficient_appraisals(optimisation, [new_appraisal]) != []:
                system_appraisals.append(new_appraisal)

        # Update the maximum PV size.
        pv_system_size.max = test_pv_size

    return (
        pv_system_size,
        storage_size,
        system_appraisals,
    )


def _find_optimum_system(
    convertors: List[Convertor],
    end_year: int,
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    grid_profile: pd.DataFrame,
    kerosene_usage: pd.DataFrame,
    largest_pv_system_size: PVSystemSize,
    largest_storage_system_size: StorageSystemSize,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    num_clean_water_tanks: int,
    optimisation: Optimisation,
    previous_system: Optional[SystemAppraisal],
    scenario: Scenario,
    start_year: int,
    system_appraisals: List[SystemAppraisal],
    total_clean_water_load: Optional[pd.DataFrame],
    total_electric_load: pd.DataFrame,
    total_solar_power_produced: pd.DataFrame,
    yearly_electric_load_statistics: pd.DataFrame,
):
    """
    Finds the optimum system from a group of sufficient systems.

    This function determines the optimum system from s group of sufficient systems. It
    contains functionality that enables it to increase the system size if necessary if
    the simulation is an edge case

    Inputs:
        - end_year:
            The end year of the simulation run currently being considered.
        - largest_pv_system_size:
            The maximum size of PV system installed.
        - largest_storage_system_size:
            The maximum size of storage installed.
        - previous_system:
            The previous system that was considered.
        - start_year:
            The start year for the simulation run.
        - system_appraisals:
            A `list` of :class:`SystemAppraisals` of sufficient systems.

    Outputs:
        optimum_system      Optimum system for the simulation period

    """

    # Check to find optimum system
    logger.info("Determining optimum system from %s systems.", len(system_appraisals))
    optimum_systems = _fetch_optimum_system(optimisation, system_appraisals)
    logger.info(
        "Optimum system(s) determined:%s",
        "\n".join(
            [
                f"criterion: {criterion}\nsystem_details: {system.system_details}"
                for criterion, system in optimum_systems.items()
            ]
        ),
    )

    for optimisation_criterion, optimum_system in tqdm(
        optimum_systems.items(), desc="checking upper bound", leave=False, unit="system"
    ):
        # Check if optimum system was the largest system simulated
        while (
            optimum_system.system_details.initial_pv_size == largest_pv_system_size.max
        ) or (
            optimum_system.system_details.initial_storage_size
            == largest_storage_system_size.max
        ):
            # Do single line optimisation to see if larger system is superior
            (
                largest_pv_system_size,
                largest_storage_system_size,
                new_system_appraisals,
            ) = _single_line_simulation(
                convertors,
                end_year,
                finance_inputs,
                ghg_inputs,
                grid_profile,
                kerosene_usage,
                largest_pv_system_size,
                largest_storage_system_size,
                location,
                logger,
                minigrid,
                num_clean_water_tanks,
                optimisation,
                optimum_system,
                previous_system,
                scenario,
                start_year,
                total_clean_water_load,
                total_electric_load,
                total_solar_power_produced,
                yearly_electric_load_statistics,
            )

            # Determine the optimum system from the new systems simulated.
            logger.info(
                "Determining optimum system from %s systems.",
                len(new_system_appraisals),
            )
            potential_optimum_system = _fetch_optimum_system(
                optimisation, new_system_appraisals
            )

            # Compare previous optimum system and new potential
            system_comparison = [
                optimum_system,
                list(potential_optimum_system.values())[0],
            ]
            logger.info(
                "Determining optimum system from %s systems.", len(system_comparison)
            )
            optimum_system = _fetch_optimum_system(optimisation, system_comparison)[
                optimisation_criterion
            ]

        optimum_systems[optimisation_criterion] = optimum_system

    # Return the confirmed optimum system
    return optimum_systems


def _get_sufficient_appraisals(
    optimisation: Optimisation, system_appraisals: List[SystemAppraisal]
) -> List[SystemAppraisal]:
    """
    Checks whether any of the system appraisals fulfill the threshold criterion

    Inputs:
        - optimisation:
            The optimisation currently being considered.
        - system_appraisals:
            Appraisals of the systems which have been simulated

    Outputs:
        - sufficient_systems:
            Appraisals of the systems which meet the threshold criterion (sufficient systems)

    """

    sufficient_appraisals: List[SystemAppraisal] = []

    # Cycle through the provided appraisals.
    for appraisal in system_appraisals:
        if appraisal.criteria is None:
            raise InternalError(
                "A system appraisal was returned which does not have criteria defined."
            )
        criteria_met = set()
        for (
            threshold_criterion,
            threshold_value,
        ) in optimisation.threshold_criteria.items():
            # Add a `True` marker if the threshold criteria are met, otherwise add
            # False.
            if (
                THRESHOLD_CRITERION_TO_MODE[threshold_criterion]
                == ThresholdMode.MAXIMUM
            ):
                if appraisal.criteria[threshold_criterion] <= threshold_value:
                    criteria_met.add(True)
                else:
                    criteria_met.add(False)
            if (
                THRESHOLD_CRITERION_TO_MODE[threshold_criterion]
                == ThresholdMode.MINIMUM
            ):
                if appraisal.criteria[threshold_criterion] >= threshold_value:
                    criteria_met.add(True)
                else:
                    criteria_met.add(False)

        # Store the system to return provided it is sufficient.
        if all(criteria_met):
            sufficient_appraisals.append(appraisal)

    return sufficient_appraisals


def _simulation_iteration(
    convertors: List[Convertor],
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    grid_profile: pd.DataFrame,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    num_clean_water_tanks: int,
    optimisation: Optimisation,
    optimisation_parameters: OptimisationParameters,
    previous_system: Optional[SystemAppraisal],
    pv_sizes: PVSystemSize,
    scenario: Scenario,
    start_year: int,
    storage_sizes: StorageSystemSize,
    total_clean_water_load: Optional[pd.DataFrame],
    total_electric_load: pd.DataFrame,
    total_solar_power_produced: pd.DataFrame,
    yearly_electric_load_statistics: pd.DataFrame,
) -> Tuple[
    int,
    PVSystemSize,
    StorageSystemSize,
    SystemAppraisal,
    Optional[SystemAppraisal],
    int,
    List[SystemAppraisal],
]:
    """
    Carries out a simulation iteration.

    New simulation iteration i.e. checks sufficiency and stops when criteria is not met,
    increases system size when no sufficient system exists.

    Inputs:
        - grid_profile:
            The grid-availability profile.
        - kerosene_usage:
            The kerosene-usage profile.
        - location:
            The location being considered.
        - logger:
            The logger to use for the run.
        - minigrid:
            The energy system being considered.
        - num_clean_water_tanks:
            The number of clean-water tanks being considered.
        - optimisation:
            The :class:`Optimisation` currently being run.
        - optimisation_parameters:
            A :class:`OptimisationParameters` instance outlining the optimisation bounds.
        - previous_system:
            Appraisal of the system already in place before this simulation period.
        - pv_sizes:
            Range of PV sizes.
        - scenario:
            The scenatio being considered.
        - solar_lifetime:
            The lifetime of the solar setup.
        - start_year:
            Start year of the initial optimisation step.
        - storage_sizes:
            Range of storage sizes.
        - total_clean_water_load:
            The total clean-water load on the system.
        - total_electric_load:
            The total load on the system.
        - total_solar_power_produced:
            The total solar power output over the time period.

    Outputs:
        - end_year:
            The end year of this step, used in the simulations;
        - pv_system_size:
            The pv-system size of the largest system simulated;
        - storage_system_size:
            The storage-system size of the largest system simulated;
        - largest_system_appraisal:
            The largest system that was considered;
        - previous_system:
            The previous system that was simulated;
        - start_year:
            The start year of this step, used in the simulations;
        - system_appraisals:
            The `list` of :class:`SystemAppraisal` instances which satisfied the
            threshold conditions for the systems simulated.

    """

    # Initialise
    system_appraisals: List[SystemAppraisal] = []
    end_year: int = start_year + int(optimisation_parameters.iteration_length)

    # Check if largest system is sufficient
    logger.info("Checking whether the largest system is sufficient.")
    tqdm.write(
        "Determining largest suitable system {}    ".format(
            "." * 27,
        ),
        end="\n",
    )
    _, simulation_results, system_details = energy_system.run_simulation(
        convertors,
        minigrid,
        grid_profile,
        kerosene_usage,
        location,
        logger,
        num_clean_water_tanks,
        pv_sizes.max,
        scenario,
        Simulation(end_year, start_year),
        storage_sizes.max,
        total_clean_water_load,
        total_electric_load,
        total_solar_power_produced,
    )

    largest_system_appraisal: SystemAppraisal = appraise_system(
        yearly_electric_load_statistics,
        end_year,
        finance_inputs,
        ghg_inputs,
        location,
        logger,
        previous_system,
        simulation_results,
        start_year,
        system_details,
    )

    # Instantiate in preparation of the while loop.
    pv_size_max = pv_sizes.max
    storage_size_max = storage_sizes.max

    # Increase system size until largest system is sufficient (if necessary)
    while _get_sufficient_appraisals(optimisation, [largest_system_appraisal]) == []:
        # Round out the various variables.
        pv_size_max = float(np.ceil(pv_size_max / pv_sizes.step) * pv_sizes.step)
        storage_size_max = float(
            np.ceil(storage_size_max / storage_sizes.step) * storage_sizes.step
        )
        logger.info(
            "Probing system upper bounds: pv_size: %s, storage_size: %s",
            pv_size_max,
            storage_size_max,
        )

        # Run a simulation and appraise it.
        _, simulation_results, system_details = energy_system.run_simulation(
            convertors,
            minigrid,
            grid_profile,
            kerosene_usage,
            location,
            logger,
            num_clean_water_tanks,
            pv_size_max,
            scenario,
            Simulation(end_year, start_year),
            storage_size_max,
            total_clean_water_load,
            total_electric_load,
            total_solar_power_produced,
        )

        largest_system_appraisal = appraise_system(
            yearly_electric_load_statistics,
            end_year,
            finance_inputs,
            ghg_inputs,
            location,
            logger,
            previous_system,
            simulation_results,
            start_year,
            system_details,
        )

        logger.info(
            "System was found to be insufficient. Threshold criteria: %s",
            largest_system_appraisal.criteria,
        )

        # Increment the system sizes.
        pv_size_max += pv_sizes.step
        storage_size_max += storage_sizes.step

    tqdm.write(
        "Determining largest suitable system {}    {}".format("." * 27, DONE),
        end="\n",
    )
    system_appraisals.append(largest_system_appraisal)

    # Round the maximum PV and storage sizes to be increments of the steps involved.
    pv_size_max = float(np.ceil(pv_size_max / pv_sizes.step)) * pv_sizes.step
    storage_size_max = float(
        np.ceil(storage_size_max / storage_sizes.step) * storage_sizes.step
    )
    logger.info(
        "Largest system size determined: pv_size: %s, storage_size: %s",
        pv_size_max,
        storage_size_max,
    )

    simulation_pv_sizes = sorted(
        range(int(pv_sizes.min), int(pv_size_max + pv_sizes.step), int(pv_sizes.step)),
        reverse=True,
    )

    simulation_storage_sizes = sorted(
        range(
            int(storage_sizes.min),
            int(storage_size_max + storage_sizes.step),
            int(storage_sizes.step),
        ),
        reverse=True,
    )

    # Move down system sizes
    for pv_size in tqdm(
        simulation_pv_sizes, desc="pv size options", leave=False, unit="pv size"
    ):
        for storage_size in tqdm(
            simulation_storage_sizes,
            desc="storage size options",
            leave=False,
            unit="simulation",
        ):
            logger.info(
                "Probing system: pv_size: %s, storage_size: %s", pv_size, storage_size
            )
            # Run a simulation and appraise it.
            _, simulation_results, system_details = energy_system.run_simulation(
                convertors,
                minigrid,
                grid_profile,
                kerosene_usage,
                location,
                logger,
                num_clean_water_tanks,
                pv_size,
                scenario,
                Simulation(end_year, start_year),
                storage_size,
                total_clean_water_load,
                total_electric_load,
                total_solar_power_produced,
            )

            new_appraisal = appraise_system(
                yearly_electric_load_statistics,
                end_year,
                finance_inputs,
                ghg_inputs,
                location,
                logger,
                previous_system,
                simulation_results,
                start_year,
                system_details,
            )

            if _get_sufficient_appraisals(optimisation, [new_appraisal]) == []:
                logger.info("No sufficient systems at this resolution.")
                break

            # Store the new appraisal if it is sufficient.
            logger.info("Sufficient system found, storing.")
            system_appraisals.append(new_appraisal)

    logger.info("Optimisation bounds explored.")
    return (
        end_year,
        PVSystemSize(pv_size_max, pv_sizes.min, pv_sizes.step),
        StorageSystemSize(storage_size_max, storage_sizes.min, storage_sizes.step),
        largest_system_appraisal,
        previous_system,
        start_year,
        system_appraisals,
    )


def _optimisation_step(
    convertors: List[Convertor],
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    grid_profile: pd.DataFrame,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    num_clean_water_tanks: int,
    optimisation: Optimisation,
    optimisation_parameters: OptimisationParameters,
    previous_system: Optional[SystemAppraisal],
    pv_sizes: PVSystemSize,
    scenario: Scenario,
    start_year: int,
    storage_sizes: StorageSystemSize,
    total_clean_water_load: Optional[pd.DataFrame],
    total_electric_load: pd.DataFrame,
    total_solar_power_produced: pd.DataFrame,
    yearly_electric_load_statistics: pd.DataFrame,
) -> SystemAppraisal:
    """
    One optimisation step of the continuous lifetime optimisation

    Inputs:
        - convertors:
            The `list` of convertors available to the system.
        - finance_inputs:
            The finance input information.
        - grid_profile:
            The grid-availability profile.
        - kerosene_usage:
            The kerosene-usage profile.
        - location:
            The location being considered.
        - minigrid:
            The energy system being considered.
        - num_clean_water_tanks:
            The number of clean water tanks being considered.
        - optimisation:
            The optimisation currently being considered.
        - optimisation_parameters:
            A :class:`OptimisationParameters` instance outlining the optimisation bounds.
        - previous_system:
            Appraisal of the system already in place before this simulation period.
        - pv_sizes:
            Range of PV sizes.
        - scenario:
            The scenatio being considered.
        - solar_lifetime:
            The lifetime of the solar setup.
        - start_year:
            Start year of the initial optimisation step.
        - storage_sizes:
            Range of storage sizes.
        - total_clean_water_load:
            The total clean-water load placed on the system.
        - total_electric_load:
            The total electric load on the system.
        - total_solar_power_produced:
            The total solar power output over the time period.
        - yearly_electric_load_statistics:
            The yearly electric load statistic information.

    Outputs:
        - optimum_system:
            The optimum systems for the group of simulated systems

    """

    # Run a simulation iteration to probe the various systems available.
    logger.info("Optimisation step called.")
    (
        end_year,
        pv_system_size,
        storage_system_size,
        _,
        previous_system,
        start_year,
        sufficient_systems,
    ) = _simulation_iteration(
        convertors,
        finance_inputs,
        ghg_inputs,
        grid_profile,
        kerosene_usage,
        location,
        logger,
        minigrid,
        num_clean_water_tanks,
        optimisation,
        optimisation_parameters,
        previous_system,
        pv_sizes,
        scenario,
        start_year,
        storage_sizes,
        total_clean_water_load,
        total_electric_load,
        total_solar_power_produced,
        yearly_electric_load_statistics,
    )
    logger.info("Simulation iterations executed successfully.")

    # Determine the optimum systems that fulfil each of the optimisation criteria.
    optimum_systems = _find_optimum_system(
        convertors,
        end_year,
        finance_inputs,
        ghg_inputs,
        grid_profile,
        kerosene_usage,
        pv_system_size,
        storage_system_size,
        location,
        logger,
        minigrid,
        num_clean_water_tanks,
        optimisation,
        previous_system,
        scenario,
        start_year,
        sufficient_systems,
        total_clean_water_load,
        total_electric_load,
        total_solar_power_produced,
        yearly_electric_load_statistics,
    )
    logger.info("Optimum systems determined.")

    # @@@ For now, the optimum system for a single threshold criterion will be returned.
    return list(optimum_systems.values())[0]


def multiple_optimisation_step(
    convertors: List[Convertor],
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    grid_profile: pd.DataFrame,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    num_clean_water_tanks: int,
    optimisation: Optimisation,
    optimisation_parameters: OptimisationParameters,
    scenario: Scenario,
    total_clean_water_load: Optional[pd.DataFrame],
    total_electric_load: pd.DataFrame,
    total_solar_power_produced: pd.DataFrame,
    yearly_electric_load_statistics: pd.DataFrame,
    *,
    input_pv_sizes: Optional[PVSystemSize] = None,
    input_storage_sizes: Optional[StorageSystemSize] = None,
    previous_system: Optional[SystemAppraisal] = None,
    start_year: int = 0,
) -> Tuple[datetime.timedelta, List[SystemAppraisal]]:
    """
    Carries out multiple optimisation steps of the continuous lifetime optimisation.

    Inputs:
        - convertors:
            The `list` of convertors available to the system.
        - grid_profile:
            The grid-availability profile.
        - kerosene_usage:
            The kerosene-usage profile.
        - location:
            The location being considered.
        - minigrid:
            The energy system being considered.
        - num_clean_water_tanks:
            The number of clean water tanks being considered.
        - optimisation:
            The optimisation currently being carried out.
        - optimisation_parameters:
            A :class:`OptimisationParameters` instance outlining the optimisation bounds.
        - scenario:
            The scenatio being considered.
        - solar_lifetime:
            The lifetime of the solar setup.
        - total_load:
            The total load on the system.
        - total_solar_power_produced:
            The total solar power output over the time period.
        - yearly_electric_load_statistics:
            The yearly electric load statistic information.
        - input_pv_sizes:
            Range of PV sizes in the form [minimum, maximum, step size];
        - input_storage_sizes:
            Range of storage sizes in the form [minimum, maximum, step size];
        - previous_system:
            Appraisal of the system already in place before this simulation period;
        - start_year:
            Start year of the initial optimisation step.

    Outputs:
        - time_delta:
            The time taken for the optimisation run.
        - results:
            The results of each Optimisation().optimisation_step(...)

    """

    # Start timer to see how long simulation will take
    timer_start = datetime.datetime.now()
    logger.info("Multiple optimisation step process begun.")

    # Initialise
    results: List[SystemAppraisal] = []

    # Use the optimisation-parameter values for the first loop.
    if input_pv_sizes is None:
        logger.info("No pv sizes passed in, using default optimisation parameters.")
        input_pv_sizes = PVSystemSize(
            optimisation_parameters.pv_size_max,
            optimisation_parameters.pv_size_min,
            optimisation_parameters.pv_size_step,
        )
    if input_storage_sizes is None:
        logger.info(
            "No storage sizes passed in, using default optimisation parameters."
        )
        input_storage_sizes = StorageSystemSize(
            optimisation_parameters.storage_size_max,
            optimisation_parameters.storage_size_min,
            optimisation_parameters.storage_size_step,
        )

    #   Iterate over each optimisation step
    for _ in tqdm(
        range(int(optimisation_parameters.number_of_iterations)),
        desc="optimisation steps",
        leave=True,
        unit="step",
    ):
        logger.info("Beginning optimisation step.")
        # Fetch the optimum systems for this step.
        optimum_system = _optimisation_step(
            convertors,
            finance_inputs,
            ghg_inputs,
            grid_profile,
            kerosene_usage,
            location,
            logger,
            minigrid,
            num_clean_water_tanks,
            optimisation,
            optimisation_parameters,
            previous_system,
            PVSystemSize(input_pv_sizes.max, input_pv_sizes.min, input_pv_sizes.step),
            scenario,
            start_year,
            StorageSystemSize(
                input_storage_sizes.max,
                input_storage_sizes.min,
                input_storage_sizes.step,
            ),
            total_clean_water_load,
            total_electric_load,
            total_solar_power_produced,
            yearly_electric_load_statistics,
        )

        logger.info(
            "Optimisation step complete, optimum system determined: %s",
            optimum_system.system_details,
        )

        results.append(optimum_system)

        # Prepare inputs for next optimisation step
        start_year += optimisation_parameters.iteration_length
        previous_system = optimum_system
        pv_size_min = optimum_system.system_details.final_pv_size
        storage_size_min = optimum_system.system_details.final_storage_size
        pv_size_max = float(
            optimisation_parameters.pv_size_max
            + optimum_system.system_details.final_pv_size
        )
        storage_size_max = float(
            optimisation_parameters.storage_size_max
            + optimum_system.system_details.final_storage_size
        )
        input_pv_sizes = PVSystemSize(
            int(pv_size_max),
            int(pv_size_min),
            int(optimisation_parameters.pv_size_step),
        )
        input_storage_sizes = StorageSystemSize(
            int(storage_size_max),
            int(storage_size_min),
            int(optimisation_parameters.storage_size_step),
        )

    # End simulation timer
    timer_end = datetime.datetime.now()
    time_delta = timer_end - timer_start

    # Return the results along with the time taken.
    return time_delta, results


# #%%
# class OptimisationOld:
#     def __init__(self):
#         self.location = "Bahraich"
#         self.CLOVER_filepath = os.getcwd()
#         self.location_filepath = os.path.join(
#             self.CLOVER_filepath, LOCATIONS_FOLDER_NAME, self.location
#         )
#         self.optimisation_filepath = os.path.join(
#             self.location_filepath, "Optimisation", "Optimisation inputs.csv"
#         )
#         self.optimisation_inputs = pd.read_csv(
#             self.optimisation_filepath, header=None, index_col=0
#         ).round(decimals=3)
#         self.maximum_criteria = [
#             "Blackouts",
#             "LCUE ($/kWh)",
#             "Emissions intensity (gCO2/kWh)",
#             "Unmet energy fraction",
#             "Cumulative cost ($)",
#             "Cumulative system cost ($)",
#             "Total cost ($)",
#             "Total system cost ($)",
#             "Cumulative GHGs (kgCO2eq)",
#             "Cumulative system GHGs (kgCO2eq)",
#             "Total GHGs (kgCO2eq)",
#             "Total system GHGs (kgCO2eq)",
#         ]
#         self.minimum_criteria = [
#             "Renewables fraction",
#             "Kerosene displacement",
#             "Kerosene cost mitigated ($)",
#             "Kerosene GHGs mitigated (kgCO2eq)",
#         ]
#         self.optimum_criterion = str(
#             self.optimisation_inputs[1]["Optimisation criterion"]
#         )
#         self.optimisation_storage = os.path.join(
#             self.location_filepath, "Optimisation", "Saved optimisations"
#         )

#     #%%

#     def changing_parameter_optimisation(
#         self, parameter: str, parameter_values=[], results_folder_name=[]
#     ):
#         """
#         Allows the user to change a parameter in the output file.

#         Allows the user to change a parameter in the "Optimisation inputs.csv" file
#         automatically and run many optimisation runs, saving each one.

#         Inputs:
#             - parameter:
#                 Parameter to be changed
#             - parameter_values:
#                 Values for the threshold criterion in the form [min, max, step]
#             - results_folder_name:
#                 Folder where the results will be saved

#         Outputs:
#             Saved outputs of the optimisations for each parameter value, and a separate
#             saved summary of all outputs for comparison.

#         """

#         # Initialise
#         summarised_results = pd.DataFrame()
#         if results_folder_name != None:
#             results_folder = str(results_folder_name)
#         else:
#             results_folder = self.optimisation_storage + str(
#                 datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
#             )

#         # Iterate over the range of threshold steps
#         value_counter = 1
#         for parameter_value in parameter_values:
#             print(
#                 "\nParameter value "
#                 + str(value_counter)
#                 + " of "
#                 + str(len(parameter_values))
#             )
#             value_counter += 1
#             #   Set the threshold value for this step
#             self.change_parameter(parameter, parameter_value)
#             #   Perform optimisation
#             optimisation_results = self.multiple_optimisation_step()
#             #   Save optimisation
#             optimisation_filename = os.path.join(
#                 results_folder, parameter + " = {:.2f}".format(parameter_value)
#             )
#             self.save_optimisation(
#                 optimisation_name=optimisation_results, filename=optimisation_filename
#             )
#             new_results = self.summarise_optimisation_results(optimisation_results)
#             summarised_results = pd.concat([summarised_results, new_results], axis=0)

#         # Format and save output summary
#         parameter_values = pd.DataFrame({"Parameter value": parameter_values})
#         summary_output = pd.concat(
#             [
#                 parameter_values.reset_index(drop=True),
#                 summarised_results.reset_index(drop=True),
#             ],
#             axis=1,
#         )
#         summary_filename = os.path.join(
#             results_folder, parameter + " lifetime summary of results"
#         )
#         self.save_optimisation(summary_output, filename=summary_filename)

#     #%%
#     # =============================================================================
#     # SYSTEM APPRAISALS
#     #       These system appraisal functions evaluate the technical, financial and
#     #       overall performance of the energy systems that have been simulated.
#     # =============================================================================

#     #%%
#     # =============================================================================
#     # GENERAL FUNCTIONS
#     #       These functions perform various general processes for the optimisation
#     #       functions including checking thresholds, saving optimisations as .csv
#     #       files and summarising results.
#     # =============================================================================
#     def change_parameter(self, parameter, new_parameter_value):
#         """
#         Function:
#             Edits .csv file to change parameter value in "Optimisation inputs.csv"
#         Inputs:
#             parameter               Name of the parameter to be changed
#             new_parameter_value     Value for the parameter to be changed
#         Outputs:
#             Updated "Optimisation inputs.csv" file with the new parameter
#         """
#         parameter = str(parameter)
#         new_optimisation_inputs = self.optimisation_inputs
#         new_optimisation_inputs[1][parameter] = float(new_parameter_value)
#         new_optimisation_inputs.to_csv(
#             self.location_filepath + "/Optimisation/Optimisation inputs.csv",
#             header=None,
#         )

#     def save_optimisation(self, optimisation_name, filename=None):
#         """
#         Saves optimisation outputs to a .csv file

#         Inputs:
#             - optimisation_name:
#                 DataFrame output from Optimisation().multiple_optimisation_step(...)
#             - filename:
#                 Name of .csv file to be saved as (defaults to timestamp)

#         Outputs:
#             Optimisation saved to .csv file

#         """

#         if filename != None:
#             optimisation_name.to_csv(
#                 os.path.join(self.optimisation_storage, str(filename) + ".csv")
#             )
#         else:
#             filename = str(datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S"))
#             optimisation_name.to_csv(
#                 os.path.join(self.optimisation_storage, filename + ".csv")
#             )
#         print("\nOptimisation saved as " + filename + ".csv")

#     def open_optimisation(self, filename):
#         """
#         Opens a previously saved optimisation from a .csv file

#         Inputs:
#             - filename:
#                 Name of the .csv file to be opened (not including .csv)

#         Outputs:
#             - DataFrame of previously performed optimisation

#         """

#         output = pd.read_csv(
#             os.path.join(self.optimisation_storage, str(filename) + ".csv", index_col=0)
#         )

#         return output

#     def summarise_optimisation_results(self, optimisation_results):
#         """
#         Summarises the optimisation step results into a output for the system lifetime

#         Inputs:
#             - optimisation_results:
#                 Results of Optimisation().multiple_optimisation_step(...)

#         Outputs:
#             - result:
#                 Aggregated results for the lifetime of the system

#         """

#         # Data where the inital and/or final entries are most relevant
#         start_year = int(optimisation_results["Start year"].iloc[0])
#         end_year = int(optimisation_results["End year"].iloc[-1])
#         step_length = int(
#             optimisation_results["End year"].iloc[0]
#             - optimisation_results["Start year"].iloc[0]
#         )
#         optimisation_length = end_year - start_year
#         max_PV = optimisation_results["Initial PV size"].iloc[-1]
#         max_storage = optimisation_results["Initial storage size"].iloc[-1]
#         max_diesel = optimisation_results["Diesel capacity"].iloc[-1]
#         LCUE = optimisation_results["LCUE ($/kWh)"].iloc[-1]
#         emissions_intensity = optimisation_results[
#             "Emissions intensity (gCO2/kWh)"
#         ].iloc[-1]
#         total_GHGs = optimisation_results["Cumulative GHGs (kgCO2eq)"].iloc[-1]
#         total_system_GHGs = optimisation_results[
#             "Cumulative system GHGs (kgCO2eq)"
#         ].iloc[-1]
#         #   Data where the mean is most relevant
#         blackouts = np.mean(optimisation_results["Blackouts"])
#         kerosene_displacement = np.mean(optimisation_results["Kerosene displacement"])
#         #   Data where the sum is most relevant
#         total_energy = np.sum(optimisation_results["Total energy (kWh)"])
#         unmet_energy = np.sum(optimisation_results["Unmet energy (kWh)"])
#         renewable_energy = np.sum(optimisation_results["Renewable energy (kWh)"])
#         storage_energy = np.sum(optimisation_results["Storage energy (kWh)"])
#         grid_energy = np.sum(optimisation_results["Grid energy (kWh)"])
#         diesel_energy = np.sum(optimisation_results["Diesel energy (kWh)"])
#         discounted_energy = np.sum(optimisation_results["Discounted energy (kWh)"])
#         diesel_fuel_usage = np.sum(optimisation_results["Diesel fuel usage (l)"])
#         total_cost = np.sum(optimisation_results["Total cost ($)"])
#         total_system_cost = np.sum(optimisation_results["Total system cost ($)"])
#         new_equipment_cost = np.sum(optimisation_results["New equipment cost ($)"])
#         new_connection_cost = np.sum(optimisation_results["New connection cost ($)"])
#         OM_cost = np.sum(optimisation_results["O&M cost ($)"])
#         diesel_cost = np.sum(optimisation_results["Diesel cost ($)"])
#         grid_cost = np.sum(optimisation_results["Grid cost ($)"])
#         kerosene_cost = np.sum(optimisation_results["Kerosene cost ($)"])
#         kerosene_cost_mitigated = np.sum(
#             optimisation_results["Kerosene cost mitigated ($)"]
#         )
#         OM_GHGs = np.sum(optimisation_results["O&M GHGs (kgCO2eq)"])
#         diesel_GHGs = np.sum(optimisation_results["Diesel GHGs (kgCO2eq)"])
#         grid_GHGs = np.sum(optimisation_results["Grid GHGs (kgCO2eq)"])
#         kerosene_GHGs = np.sum(optimisation_results["Kerosene GHGs (kgCO2eq)"])
#         kerosene_mitigated_GHGs = np.sum(
#             optimisation_results["Kerosene GHGs mitigated (kgCO2eq)"]
#         )

#         #   Data which requires combinations of summary results
#         unmet_fraction = round(unmet_energy / total_energy, 3)
#         renewables_fraction = round(renewable_energy / total_energy, 3)
#         storage_fraction = round(storage_energy / total_energy, 3)
#         diesel_fraction = round(diesel_energy / total_energy, 3)
#         grid_fraction = round(grid_energy / total_energy, 3)
#         #   Combine results into output
#         results = pd.DataFrame(
#             {
#                 "Start year": start_year,
#                 "End year": end_year,
#                 "Step length": step_length,
#                 "Optimisation length": optimisation_length,
#                 "Maximum PV size": max_PV,
#                 "Maximum storage size": max_storage,
#                 "Maximum diesel capacity": max_diesel,
#                 "LCUE ($/kWh)": LCUE,
#                 "Emissions intensity (gCO2/kWh)": emissions_intensity,
#                 "Blackouts": blackouts,
#                 "Unmet fraction": unmet_fraction,
#                 "Renewables fraction": renewables_fraction,
#                 "Storage fraction": storage_fraction,
#                 "Diesel fraction": diesel_fraction,
#                 "Grid fraction": grid_fraction,
#                 "Total energy (kWh)": total_energy,
#                 "Unmet energy (kWh)": unmet_energy,
#                 "Renewable energy (kWh)": renewable_energy,
#                 "Storage energy (kWh)": storage_energy,
#                 "Grid energy (kWh)": grid_energy,
#                 "Diesel energy (kWh)": diesel_energy,
#                 "Discounted energy (kWh)": discounted_energy,
#                 "Total cost ($)": total_cost,
#                 "Total system cost ($)": total_system_cost,
#                 "New equipment cost ($)": new_equipment_cost,
#                 "New connection cost ($)": new_connection_cost,
#                 "O&M cost ($)": OM_cost,
#                 "Diesel cost ($)": diesel_cost,
#                 "Grid cost ($)": grid_cost,
#                 "Kerosene cost ($)": kerosene_cost,
#                 "Kerosene cost mitigated ($)": kerosene_cost_mitigated,
#                 "Kerosene displacement": kerosene_displacement,
#                 "Diesel fuel usage (l)": diesel_fuel_usage,
#                 "Total GHGs (kgCO2eq)": total_GHGs,
#                 "Total system GHGs (kgCO2eq)": total_system_GHGs,
#                 "Total GHGs (kgCO2eq)": total_GHGs,
#                 "O&M GHGs (kgCO2eq)": OM_GHGs,
#                 "Diesel GHGs (kgCO2eq)": diesel_GHGs,
#                 "Grid GHGs (kgCO2eq)": grid_GHGs,
#                 "Kerosene GHGs (kgCO2eq)": kerosene_GHGs,
#                 "Kerosene GHGs mitigated (kgCO2eq)": kerosene_mitigated_GHGs,
#             },
#             index=["Lifetime results"],
#         )
#         return results

#     #%%
#     # =============================================================================
#     # UNSUPPORTED FUNCTIONS
#     #       This process is similar to the optimisation process used by previous
#     #       versions of CLOVER. It has been replaced by the new optimisation process
#     #       and will no longer be updated.
#     # =============================================================================
#     def complete_simulation_iteration(
#         self,
#         PV_sizes=[],
#         storage_sizes=[],
#         previous_systems=pd.DataFrame([]),
#         start_year=0,
#     ):
#         """
#         @@@ THIS FUNCTION IS OUTDATED AND HAS BEEN REPLACED BY find_optimum_system(...)
#         @@@ THIS FUNCTION IS INCLUDED FOR INTEREST AND WILL NO LONGER BE UPDATED

#         Iterates simulations over a range of PV and storage sizes to give appraisals of
#         each system. Identical to the previous CLOVER method of simulation i.e. every
#         system within a given range

#         Inputs:
#             - PV_sizes:
#                 Range of PV sizes in the form [minimum, maximum, step size]
#             - storage_sizes:
#                 Range of storage sizes in the form [minimum, maximum, step size]
#             - previous_system:
#                 Appraisal of the system already in place before this simulation period
#             - start_year:
#                 Start year of this simulation period

#         Outputs:
#             appraisals          DataFrame of system results

#         """
#         #   Initialise
#         PV_sizes = pd.DataFrame(PV_sizes)
#         storage_sizes = pd.DataFrame(storage_sizes)
#         system_appraisals = pd.DataFrame([])
#         simulation_number = 0
#         end_year = start_year + int(self.optimisation_inputs[1]["Iteration length"])
#         #   Check to see if PV sizes have been set
#         if PV_sizes.empty == True:
#             PV_size_min = float(self.optimisation_inputs[1]["PV size (min)"])
#             pv_size_max = float(self.optimisation_inputs[1]["PV size (max)"])
#             PV_size_step = float(self.optimisation_inputs[1]["PV size (step)"])
#         #   Check to see if storage sizes have been set
#         if storage_sizes.empty == True:
#             storage_size_min = float(self.optimisation_inputs[1]["Storage size (min)"])
#             storage_size_max = float(self.optimisation_inputs[1]["Storage size (max)"])
#             storage_size_step = float(
#                 self.optimisation_inputs[1]["Storage size (step)"]
#             )

#         #   Iterate over PV sizes
#         for PV in np.arange(PV_size_min, pv_size_max + PV_size_step, PV_size_step):
#             #   Iterate over storage sizes
#             for storage in np.arange(
#                 storage_size_min,
#                 storage_size_max + storage_size_step,
#                 storage_size_step,
#             ):
#                 #   Run simulation
#                 simulation_number += 1
#                 simulation = energy_system.run_simulation(
#                     minigrid,
#                     grid_profile,
#                     kerosene_usage,
#                     location,
#                     PV,
#                     scenario,
#                     Simulation(end_year, start_year),
#                     solar_lifetime,
#                     storage,
#                     total_load,
#                     total_solar_power_produced,
#                 )
#                 new_appraisal = self.system_appraisal(
#                     simulation_results, previous_systems
#                 )
#                 system_appraisals = pd.concat(
#                     [
#                         system_appraisals,
#                         new_appraisal.rename(
#                             {"System results": simulation_number}, axis="index"
#                         ),
#                     ],
#                     axis=0,
#                 )
#         return system_appraisals
