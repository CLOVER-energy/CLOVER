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
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np  # pylint: disable=import-error
import pandas as pd  # pylint: disable=import-error

from tqdm import tqdm  # pylint: disable=import-error

from ..simulation import energy_system

from ..__utils__ import (
    BColours,
    # ColumnHeader,
    DONE,
    InternalError,
    Location,
    RenewableEnergySource,
    ResourceType,
    Scenario,
    Simulation,
)
from ..conversion.conversion import Convertor, WaterSource
from ..impact.finance import ImpactingComponent
from .appraisal import appraise_system, SystemAppraisal
from .__utils__ import (
    ConvertorSize,
    Criterion,
    CriterionMode,
    Optimisation,
    OptimisationParameters,
    SolarSystemSize,
    StorageSystemSize,
    TankSize,
    ThresholdMode,
)

__all__ = ("multiple_optimisation_step",)


# Threshold-criterion-to-mode mapping:
#   Maps the threshold criteria to the modes, i.e., whether they are maximisable or
#   minimisable.
THRESHOLD_CRITERION_TO_MODE: Dict[Criterion, ThresholdMode] = {
    Criterion.BLACKOUTS: ThresholdMode.MAXIMUM,
    Criterion.CLEAN_WATER_BLACKOUTS: ThresholdMode.MAXIMUM,
    Criterion.CUMULATIVE_COST: ThresholdMode.MAXIMUM,
    Criterion.CUMULATIVE_GHGS: ThresholdMode.MAXIMUM,
    Criterion.CUMULATIVE_SYSTEM_COST: ThresholdMode.MAXIMUM,
    Criterion.CUMULATIVE_SYSTEM_COST: ThresholdMode.MAXIMUM,
    Criterion.EMISSIONS_INTENSITY: ThresholdMode.MAXIMUM,
    Criterion.KEROSENE_COST_MITIGATED: ThresholdMode.MINIMUM,
    Criterion.KEROSENE_DISPLACEMENT: ThresholdMode.MINIMUM,
    Criterion.KEROSENE_GHGS_MITIGATED: ThresholdMode.MINIMUM,
    Criterion.LCUE: ThresholdMode.MAXIMUM,
    Criterion.RENEWABLES_FRACTION: ThresholdMode.MINIMUM,
    Criterion.TOTAL_COST: ThresholdMode.MAXIMUM,
    Criterion.TOTAL_GHGS: ThresholdMode.MAXIMUM,
    Criterion.TOTAL_SYSTEM_COST: ThresholdMode.MAXIMUM,
    Criterion.TOTAL_SYSTEM_GHGS: ThresholdMode.MAXIMUM,
    Criterion.UNMET_ENERGY_FRACTION: ThresholdMode.MAXIMUM,
}


def _convertors_from_sizing(convertor_sizes: Dict[Convertor, int]) -> List[Convertor]:
    """
    Generates a `list` of available convertors based on the number of each available.

    As the system is optimised, it becomes necessary to generate a `list` containing the
    available convertors, with duplicates allowed to indiciate multiple instances of a
    single type present, from the various values.

    Inputs:
        - convertor_sizes:
            A `dict` mapping :class:`Convertor` instances to the number of each type
            present during the iteration.

    Outputs:
        - A `list` of :class:`Convertor` instances present based on the mapping passed
        in.

    """

    convertors: List[Convertor] = []

    for convertor, size in convertor_sizes.items():
        convertors.extend([convertor] * size)

    return convertors


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

    optimum_systems: Dict[Criterion, SystemAppraisal] = {}

    # Run through the various optimisation criteria.
    for (criterion, criterion_mode) in optimisation.optimisation_criteria.items():
        # Sort by the optimisation criterion.
        sufficient_systems.sort(
            key=lambda appraisal, crit=criterion: appraisal.criteria[crit],
            reverse=(criterion_mode == CriterionMode.MAXIMISE),
        )

        # Add the optimum system, keyed by the optimisation criterion.
        optimum_systems[criterion] = sufficient_systems[0]

    return optimum_systems


def _single_line_simulation(
    cw_tanks: TankSize,
    convertors: List[Convertor],
    end_year: int,
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    grid_profile: pd.DataFrame,
    irradiance_data: pd.Series,
    kerosene_usage: pd.DataFrame,
    pv_system_size: SolarSystemSize,
    pvt_system_size: SolarSystemSize,
    storage_size: StorageSystemSize,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    optimisation: Optimisation,
    potential_system: SystemAppraisal,
    previous_system: Optional[SystemAppraisal],
    scenario: Scenario,
    start_year: int,
    temperature_data: pd.Series,
    total_loads: Dict[ResourceType, Optional[pd.DataFrame]],
    total_solar_pv_power_produced: pd.Series,
    wind_speed_data: Optional[pd.Series],
    yearly_electric_load_statistics: pd.DataFrame,
) -> Tuple[
    TankSize, SolarSystemSize, SolarSystemSize, StorageSystemSize, List[SystemAppraisal]
]:
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
        - cw_tanks:
            The clean-water tank size of the largest system considered.
        - pv_system_size:
            The pv system size of the largest system considered.
        - pvt_system_size:
            The pv-t system size of the largest system considered.
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

    # Set up a max clean-water tank variable to use if none were specified.
    test_cw_tanks = cw_tanks.max

    # If storage was maxed out:
    if potential_system.system_details.initial_storage_size == storage_size.max:
        logger.info("Increasing storage size.")

        # Increase and iterate over PV and PV-T sizes
        increased_pv_system_sizes = sorted(
            range(
                int(pv_system_size.min),
                int(np.ceil(pv_system_size.max + pv_system_size.step)),
                int(pv_system_size.step),
            ),
            reverse=True,
        )
        increased_pvt_system_sizes = sorted(
            range(
                int(pvt_system_size.min),
                int(np.ceil(pvt_system_size.max + pvt_system_size.step)),
                int(pvt_system_size.step),
            ),
            reverse=True,
        )

        if len(increased_pv_system_sizes) > 1:
            for iteration_pv_size in tqdm(
                increased_pv_system_sizes,
                desc="probing pv sizes",
                leave=False,
                unit="pv size" if pvt_system_size.max > 0 else "simulation",
            ):
                if len(increased_pvt_system_sizes) > 1:
                    for iteration_pvt_size in tqdm(
                        increased_pvt_system_sizes,
                        desc="probing pv-t sizes",
                        leave=False,
                        unit="simulation",
                    ):
                        # Run a simulation.
                        (
                            _,
                            simulation_results,
                            system_details,
                        ) = energy_system.run_simulation(
                            iteraion_cw_pvt_size,
                            conventional_cw_source_profiles,
                            convertors,
                            test_storage_size,
                            grid_profile,
                            iteration_hw_pvt_size,
                            irradiance_data,
                            kerosene_usage,
                            location,
                            logger,
                            minigrid,
                            test_cw_tanks,
                            test_hw_tanks,
                            total_solar_pv_power_produced,
                            iteration_pv_size,
                            scenario,
                            Simulation(end_year, start_year),
                            temperature_data,
                            total_loads,
                            wind_speed_data,
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

                        if (
                            _get_sufficient_appraisals(optimisation, [new_appraisal])
                            == []
                        ):
                            break
                        system_appraisals.append(new_appraisal)
                else:
                    # Run a simulation.
                    (
                        _,
                        simulation_results,
                        system_details,
                    ) = energy_system.run_simulation(
                        cw_pvt_size_to_redo,
                        conventional_cw_source_profiles,
                        convertors,
                        test_storage_size,
                        grid_profile,
                        hw_pvt_size_to_redo,
                        irradiance_data,
                        kerosene_usage,
                        location,
                        logger,
                        minigrid,
                        test_cw_tanks,
                        test_hw_tanks,
                        total_solar_pv_power_produced,
                        iteration_pv_size,
                        scenario,
                        Simulation(end_year, start_year),
                        temperature_data,
                        total_loads,
                        total_solar_pv_power_produced,
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
        else:
            if len(increased_pvt_system_sizes) > 1:
                for iteration_pvt_size in tqdm(
                    increased_pvt_system_sizes,
                    desc="probing pv-t sizes",
                    leave=False,
                    unit="simulation",
                ):
                    # Run a simulation.
                    (
                        _,
                        simulation_results,
                        system_details,
                    ) = energy_system.run_simulation(
                        cw_pvt_size_to_redo,
                        conventional_cw_source_profiles,
                        convertors,
                        test_storage_size,
                        grid_profile,
                        hw_pvt_size_to_redo,
                        irradiance_data,
                        kerosene_usage,
                        location,
                        logger,
                        minigrid,
                        test_cw_tanks,
                        test_hw_tanks,
                        total_solar_pv_power_produced,
                        pv_system_size.max,
                        scenario,
                        Simulation(end_year, start_year),
                        temperature_data,
                        total_loads,
                        total_solar_pv_power_produced,
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
            else:
                logger.info(
                    "%sNo PV or PV-T system sizes to iterate over.%s",
                    BColours.fail,
                    BColours.endc,
                )

        # If the maximum PV system size isn't a round number of steps, carry out a
        # simulation at this size..
        if (
            np.ceil(pv_system_size.max / pv_system_size.step) * pv_system_size.step
            != pv_system_size.max
        ):
            _, simulation_results, system_details = energy_system.run_simulation(
                cw_pvt_size_to_redo,
                conventional_cw_source_profiles,
                convertors,
                test_storage_size,
                grid_profile,
                hw_pvt_size_to_redo,
                irradiance_data,
                kerosene_usage,
                location,
                logger,
                minigrid,
                test_cw_tanks,
                test_hw_tanks,
                total_solar_pv_power_produced,
                pv_system_size.max,
                scenario,
                Simulation(end_year, start_year),
                temperature_data,
                total_loads,
                wind_speed_data,
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

        # If the maximum PV-T system size isn't a round number of steps, carry out a
        # simulation at this size..
        if (
            np.ceil(pv_system_size.max / pv_system_size.step) * pv_system_size.step
            != pvt_system_size.max
        ):
            _, simulation_results, system_details = energy_system.run_simulation(
                cw_pvt_size_to_redo,
                conventional_cw_source_profiles,
                convertors,
                test_storage_size,
                grid_profile,
                hw_pvt_size_to_redo,
                irradiance_data,
                kerosene_usage,
                location,
                logger,
                minigrid,
                test_cw_tanks,
                test_hw_tanks,
                total_solar_pv_power_produced,
                pv_system_size.max,
                scenario,
                Simulation(end_year, start_year),
                temperature_data,
                total_loads,
                wind_speed_data,
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

    # If PV was maxed out:
    if (
        potential_system.system_details.initial_pv_size == pv_system_size.max
        and pv_system_size.max > 0
    ):
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
                cw_pvt_size_redo,
                conventional_cw_source_profiles,
                convertors,
                iteration_storage_size,
                grid_profile,
                hw_pvt_size_redo,
                irradiance_data,
                kerosene_usage,
                location,
                logger,
                minigrid,
                test_cw_tanks,
                test_hw_tanks,
                total_solar_pv_power_produced,
                test_pv_size,
                scenario,
                Simulation(end_year, start_year),
                temperature_data,
                total_loads,
                wind_speed_data,
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
                cw_pvt_size_redo,
                conventional_cw_source_profiles,
                convertors,
                storage_size.max,
                grid_profile,
                hw_pvt_size_redo,
                irradiance_data,
                kerosene_usage,
                location,
                logger,
                minigrid,
                test_cw_tanks,
                test_hw_tanks,
                total_solar_pv_power_produced,
                test_pv_size,
                scenario,
                Simulation(end_year, start_year),
                temperature_data,
                total_loads,
                wind_speed_data,
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

    # Check to see if PV-T size was an integer number of steps, and increase accordingly
    if (
        np.ceil(pvt_system_size.max / pvt_system_size.step) * pvt_system_size.step
        == pvt_system_size.max
    ):
        test_pvt_size = float(pvt_system_size.max + pvt_system_size.step)
    else:
        test_pvt_size = float(
            np.ceil(pvt_system_size.max / pvt_system_size.step) * pvt_system_size.step
        )

    # If PV-T was maxed out:
    if (
        potential_system.system_details.initial_pvt_size == pvt_system_size.max
        and pvt_system_size.max > 0
    ):
        logger.info("Increasing PV-T size.")

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
                cw_pvt_size_redo,
                conventional_cw_source_profiles,
                convertors,
                iteration_storage_size,
                grid_profile,
                hw_pvt_size_redo,
                irradiance_data,
                kerosene_usage,
                location,
                logger,
                minigrid,
                test_cw_tanks,
                test_hw_tanks,
                total_solar_pv_power_produced,
                test_pv_size,
                scenario,
                Simulation(end_year, start_year),
                temperature_data,
                total_loads,
                wind_speed_data,
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
                cw_pvt_size_redo,
                conventional_cw_source_profiles,
                convertors,
                storage_size.max,
                grid_profile,
                hw_pvt_size_redo,
                irradiance_data,
                kerosene_usage,
                location,
                logger,
                minigrid,
                test_cw_tanks,
                test_hw_tanks,
                total_solar_pv_power_produced,
                test_pv_size,
                scenario,
                Simulation(end_year, start_year),
                temperature_data,
                total_loads,
                wind_speed_data,
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
        pvt_system_size.max = test_pvt_size

    return (
        cw_tanks,
        pv_system_size,
        pvt_system_size,
        storage_size,
        system_appraisals,
    )


def _find_optimum_system(
    convertors: List[Convertor],
    end_year: int,
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    grid_profile: pd.DataFrame,
    irradiance_data: pd.Series,
    kerosene_usage: pd.DataFrame,
    largest_cw_tank_size: TankSize,
    largest_pv_system_size: SolarSystemSize,
    largest_pvt_system_size: SolarSystemSize,
    largest_storage_system_size: StorageSystemSize,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    optimisation: Optimisation,
    previous_system: Optional[SystemAppraisal],
    scenario: Scenario,
    start_year: int,
    system_appraisals: List[SystemAppraisal],
    temperature_data: pd.Series,
    total_loads: Dict[ResourceType, Optional[pd.DataFrame]],
    total_solar_pv_power_produced: pd.Series,
    wind_speed_data: Optional[pd.Series],
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
        - largest_cw_tank_size:
            The maximum size of clean-water tanks installed.
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
        "Optimum system(s) determined: %s",
        "\n".join(
            [
                "criterion: {}, value: {}\nsystem_details: {}".format(
                    criterion,
                    system.criteria[criterion],
                    system.system_details,
                )
                for criterion, system in optimum_systems.items()
            ]
        ),
    )

    for optimisation_criterion, optimum_system in tqdm(
        optimum_systems.items(), desc="checking upper bound", leave=False, unit="system"
    ):
        # Check if optimum system was the largest system simulated
        while (
            (
                optimum_system.system_details.initial_pv_size
                == largest_pv_system_size.max
                and scenario.pv
            )
            or (
                optimum_system.system_details.initial_storage_size
                == largest_storage_system_size.max
                and scenario.battery
            )
            or (
                optimum_system.system_details.initial_pvt_size
                == largest_pvt_system_size.max
                and scenario.pv_t
            )
            # or (
            #     optimum_system.system_details.initial_num_cw_tanks
            #     == largest_cw_tank_size.max
            #     and scenario.desalination_scenario is not None
            # )
        ):
            # Do single line optimisation to see if larger system is superior
            (
                largest_cw_tank_size,
                largest_pv_system_size,
                largest_pvt_system_size,
                largest_storage_system_size,
                new_system_appraisals,
            ) = _single_line_simulation(
                largest_cw_tank_size,
                convertors,
                end_year,
                finance_inputs,
                ghg_inputs,
                grid_profile,
                irradiance_data,
                kerosene_usage,
                largest_pv_system_size,
                largest_pvt_system_size,
                largest_storage_system_size,
                location,
                logger,
                minigrid,
                optimisation,
                optimum_system,
                previous_system,
                scenario,
                start_year,
                temperature_data,
                total_loads,
                total_solar_pv_power_produced,
                wind_speed_data,
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


def _recursive_iteration(
    convertors: List[Convertor],
    end_year: int,
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    grid_profile: pd.DataFrame,
    irradiance_data: pd.Series,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    optimisation: Optimisation,
    previous_system: Optional[SystemAppraisal],
    scenario: Scenario,
    start_year: int,
    temperature_data: pd.Series,
    total_loads: Dict[ResourceType, Optional[pd.DataFrame]],
    total_solar_pv_power_produced: pd.Series,
    wind_speed_data: Optional[pd.Series],
    yearly_electric_load_statistics: pd.DataFrame,
    *,
    component_sizes: Dict[ImpactingComponent, float],
    parameter_space: List[
        Tuple[ImpactingComponent, str, Union[List[int], List[float]]]
    ],
    system_appraisals: List[SystemAppraisal],
) -> List[SystemAppraisal]:
    """
    Recursively look for sufficient systems through a series of parameter spaces.

    Inputs:
        - component_sizes:
            Specific values for the varoius :class:`finance.ImpactingComponent` sizes to
            use for the simulation to be carried out.
        - parameter_spaces:
            A `list` containing `tuple`s as entries that specify:
            - The :class:`finance.ImpactingComponent` that should have its sizes
              iterated through;
            - The unit to display to the user, as a `str`;
            - The `list` of values to iterate through.
        - system_appraisals:
            The `list` containing the :class:`SystemAppraisal` instances that correspond
            to sufficient systems.

    Outputs:
        - A `list` of sufficient systems.

    """

    # If there are no more things to iterate through, then run a simulation and return
    # whether the system was sufficient.
    if len(parameter_space) == 0:
        logger.info(
            "Running simulation with component sizes: %s",
            ", ".join(
                [f"{key.value} size={value}" for key, value in component_sizes.items()]
            ),
        )
        (_, simulation_results, system_details,) = energy_system.run_simulation(
            component_sizes[RenewableEnergySource.CLEAN_WATER_PV_T],
            conventional_cw_source_profiles,
            convertors,
            component_sizes[ImpactingComponent.STORAGE],
            grid_profile,
            component_sizes[RenewableEnergySource.HOT_WATER_PV_T],
            irradiance_data,
            kerosene_usage,
            location,
            logger,
            minigrid,
            int(component_sizes[ImpactingComponent.CLEAN_WATER_TANK]),
            int(component_sizes[ImpactingComponent.HOT_WATER_TANK]),
            total_solar_pv_power_produced,
            component_sizes[RenewableEnergySource.PV],
            scenario,
            Simulation(end_year, start_year),
            temperature_data,
            total_loads,
            wind_speed_data,
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

        return _get_sufficient_appraisals(optimisation, [new_appraisal])

    # If there are things to iterate through, then iterate through these, calling the
    # function recursively.
    component, unit, sizes = parameter_space.pop()

    for size in tqdm(
        sizes,
        desc=f"{component.value} size options",
        leave=False,
        unit=unit,
    ):
        # Update the set of fixed sizes accordingly.
        updated_component_sizes: Dict[
            ImpactingComponent, float
        ] = component_sizes.copy()
        updated_component_sizes[component] = size

        # Call the function recursively.
        sufficient_appraisals = _recursive_iteration(
            convertors,
            end_year,
            finance_inputs,
            ghg_inputs,
            grid_profile,
            irradiance_data,
            kerosene_usage,
            location,
            logger,
            minigrid,
            optimisation,
            previous_system,
            scenario,
            start_year,
            temperature_data,
            total_loads,
            total_solar_pv_power_produced,
            wind_speed_data,
            yearly_electric_load_statistics,
            component_sizes=updated_component_sizes,
            parameter_space=parameter_space.copy(),
            system_appraisals=system_appraisals,
        )
        if sufficient_appraisals == []:
            logger.info("No sufficient systems at this resolution.")
            if len(parameter_space) == 0:
                logger.info("Probing lowest depth - skipping further size options.")
                break
            else:
                logger.info("Probing non-lowest depth - continuing iteration.")
                continue

        # Store the new appraisal if it is sufficient.
        logger.info("Sufficient system found, storing.")
        system_appraisals.extend(sufficient_appraisals)

    # Return the sufficient appraisals that were found at this resolution.
    return sufficient_appraisals


def _simulation_iteration(
    conventional_cw_source_profiles: Optional[Dict[WaterSource, pd.DataFrame]],
    convertor_sizes: Dict[Convertor, ConvertorSize],
    cw_pvt_sizes: SolarSystemSize,
    cw_tanks: TankSize,
    convertors: List[Convertor],
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    grid_profile: pd.DataFrame,
    irradiance_data: pd.Series,
    hw_pvt_sizes: SolarSystemSize,
    hw_tanks: TankSize,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    optimisation: Optimisation,
    optimisation_parameters: OptimisationParameters,
    previous_system: Optional[SystemAppraisal],
    pv_sizes: SolarSystemSize,
    scenario: Scenario,
    start_year: int,
    storage_sizes: StorageSystemSize,
    temperature_data: pd.Series,
    total_loads: Dict[ResourceType, Optional[pd.DataFrame]],
    total_solar_pv_power_produced: pd.Series,
    wind_speed_data: Optional[pd.Series],
    yearly_electric_load_statistics: pd.DataFrame,
) -> Tuple[
    int,
    Dict[Convertor, ConvertorSize],
    SolarSystemSize,
    TankSize,
    SolarSystemSize,
    TankSize,
    SolarSystemSize,
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
        - conventional_cw_source_profiles:
            A mapping between conventional water sources and their availability
            profiles.
        - cw_tanks:
            Range of clean-water tanks.
        - finance_inputs:
            The financial input information.
        - ghg_inputs:
            The green-house-gas input information.
        - grid_profile:
            The grid-availability profile.
        - irradiance_data:
            The irradaince data series.
        - kerosene_usage:
            The kerosene-usage profile.
        - location:
            The location being considered.
        - logger:
            The logger to use for the run.
        - minigrid:
            The energy system being considered.
        - optimisation:
            The :class:`Optimisation` currently being run.
        - optimisation_parameters:
            A :class:`OptimisationParameters` instance outlining the optimisation bounds.
        - previous_system:
            Appraisal of the system already in place before this simulation period.
        - pv_sizes:
            Range of PV sizes.
        - pvt_sizes:
            Range of PV-T sizes.
        - scenario:
            The scenatio being considered.
        - solar_lifetime:
            The lifetime of the solar setup.
        - start_year:
            Start year of the initial optimisation step.
        - storage_sizes:
            Range of storage sizes.
        - temperature_data:
            The temperature data series.
        - total_loads:
            A mapping between the :class:`ResourceType` and its associated total load.
        - total_solar_pv_power_produced:
            The total solar power output over the time period.
        - wind_speed_data:
            The wind-speed data series.

    Outputs:
        - end_year:
            The end year of this step, used in the simulations;
        - largest_convertor_size:
            A mapping between :class:`Convertor` instances and the size associated with
            each for the largest system simulated;
        - largest_cw_pvt_size:
            The clean-water PV-T size of the largest system simulated;
        - largest_cw_tank_size:
            The clean-water tank size of the largest system simulated;
        - largest_hw_pvt_size:
            The hot-water PV-T size of the largest system simulated;
        - largest_hw_tank_size:
            The hot-water tank size of the largest system simulated;
        - largest_pv_system_size:
            The pv-system size of the largest system simulated;
        - largest_storage_system_size:
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
    max_convertor_sizes: Dict[Convertor, int] = {
        convertor: size.max for convertor, size in convertor_sizes.items()
    }
    _, simulation_results, system_details = energy_system.run_simulation(
        cw_pvt_sizes.max,
        conventional_cw_source_profiles,
        _convertors_from_sizing(max_convertor_sizes),
        storage_sizes.max,
        grid_profile,
        hw_pvt_sizes.max,
        irradiance_data,
        kerosene_usage,
        location,
        logger,
        minigrid,
        cw_tanks.max,
        hw_tanks.max,
        total_solar_pv_power_produced,
        pv_sizes.max,
        scenario,
        Simulation(end_year, start_year),
        temperature_data,
        total_loads,
        wind_speed_data,
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
    cw_pvt_sizes_max = cw_pvt_sizes.max
    cw_tanks_max = cw_tanks.max
    hw_pvt_sizes_max = hw_pvt_sizes.max
    hw_tanks_max = hw_tanks.max
    pv_size_max = pv_sizes.max
    storage_size_max = storage_sizes.max

    # Increase system size until largest system is sufficient (if necessary)
    while _get_sufficient_appraisals(optimisation, [largest_system_appraisal]) == []:
        # Round out the various variables.
        cw_pvt_size_max = float(
            np.ceil(cw_pvt_size_max / cw_pvt_sizes.step) * cw_pvt_sizes.step
        )
        hw_pvt_size_max = float(
            np.ceil(hw_pvt_size_max / hw_pvt_sizes.step) * hw_pvt_sizes.step
        )
        pv_size_max = float(np.ceil(pv_size_max / pv_sizes.step) * pv_sizes.step)
        storage_size_max = float(
            np.ceil(storage_size_max / storage_sizes.step) * storage_sizes.step
        )
        logger.info(
            "Probing system upper bounds: pv_size: %s, storage_size: %s%s",
            pv_size_max,
            storage_size_max,
            f", num clean-water tanks: {cw_tanks_max}"
            if scenario.desalination_scenario is not None
            else "",
        )

        # Run a simulation and appraise it.
        _, simulation_results, system_details = energy_system.run_simulation(
            cw_pvt_size_max,
            conventional_cw_source_profiles,
            _convertors_from_sizing(max_convertor_sizes),
            storage_size_max,
            grid_profile,
            hw_pvt_size_max,
            irradiance_data,
            kerosene_usage,
            location,
            logger,
            minigrid,
            cw_tanks_max,
            hw_tanks_max,
            total_solar_pv_power_produced,
            pv_size_max,
            scenario,
            Simulation(end_year, start_year),
            temperature_data,
            total_loads,
            wind_speed_data,
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

        if largest_system_appraisal.criteria is None:
            raise InternalError(
                "{}Threshold criteria not set on system appraisal.{}".format(
                    BColours.fail, BColours.endc
                )
            )
        logger.info(
            "System was found to be insufficient. Threshold criteria: %s",
            {
                str(key): value
                for key, value in largest_system_appraisal.criteria.items()
            },
        )

        # Increment the system sizes.
        cw_pvt_size_max += cw_pvt_sizes.step
        cw_tanks_max += cw_tanks.step
        hw_pvt_size_max += hw_pvt_sizes.step
        hw_tanks_max += hw_tanks.step
        max_convertor_sizes = {
            convertor: max_convertor_sizes[convertor] + size.step
            for convertor, size in convertor_sizes.items()
        }
        pv_size_max += pv_sizes.step
        storage_size_max += storage_sizes.step

    tqdm.write(
        "Determining largest suitable system {}    {}".format("." * 27, DONE),
        end="\n",
    )
    system_appraisals.append(largest_system_appraisal)

    # Round the maximum PV and storage sizes to be increments of the steps involved.
    cw_pvt_size_max = (
        float(np.ceil(cw_pvt_size_max / cw_pvt_sizes.step)) * cw_pvt_sizes.step
    )
    hw_pvt_size_max = (
        float(np.ceil(hw_pvt_size_max / hw_pvt_sizes.step)) * hw_pvt_sizes.step
    )
    pv_size_max = float(np.ceil(pv_size_max / pv_sizes.step)) * pv_sizes.step
    storage_size_max = float(
        np.ceil(storage_size_max / storage_sizes.step) * storage_sizes.step
    )
    logger.info(
        "Largest system size determined:\n- pv_size: %s\n%s%s%s%s%s- storage_size: %s",
        pv_size_max,
        f"- clean-water pvt-size: {cw_pvt_size_max}\n"
        if minigrid.pvt_panel is not None and scenario.desalination_scenario is not None
        else "",
        f"- num clean-water tanks: {cw_tanks_max}\n"
        if minigrid.clean_water_tank is not None
        and scenario.desalination_scenario is not None
        else "",
        f"- hot-water pvt-size: {hw_pvt_size_max}\n"
        if minigrid.pvt_panel is not None and scenario.hot_water_scenario is not None
        else "",
        f"- num hot-water tanks: {hw_tanks_max}\n"
        if minigrid.hot_water_tank is not None
        and scenario.hot_water_scenario is not None
        else "",
        storage_size_max,
    )

    # Set up the various variables ready for recursive iteration.
    component_sizes: Dict[ImpactingComponent, float] = {}
    parameter_space: List[
        Tuple[ImpactingComponent, str, Union[List[float], List[int]]]
    ] = []

    simulation_cw_tanks: List[int] = sorted(
        range(
            cw_tanks.min,
            cw_tanks_max + cw_tanks.step,
            cw_tanks.step,
        ),
        reverse=True,
    )

    simulation_pv_sizes: List[int] = sorted(
        range(int(pv_sizes.min), int(pv_size_max + pv_sizes.step), int(pv_sizes.step)),
        reverse=True,
    )

    simulation_pvt_sizes: List[int] = sorted(
        range(
            int(pvt_sizes.min), int(pvt_size_max + pvt_sizes.step), int(pvt_sizes.step)
        ),
        reverse=True,
    )

    simulation_storage_sizes: List[int] = sorted(
        range(
            int(storage_sizes.min),
            int(storage_size_max + storage_sizes.step),
            int(storage_sizes.step),
        ),
        reverse=True,
    )

    # Set up the various iteration variables accordingly.
    # Add the iterable clean-water tank sizes if appropriate.
    if len(simulation_cw_tanks) > 1:
        parameter_space.append(
            (
                ImpactingComponent.CLEAN_WATER_TANK,
                "simulation",
                simulation_cw_tanks,
            )
        )
    else:
        component_sizes[ImpactingComponent.CLEAN_WATER_TANK] = simulation_cw_tanks[0]

    # Add the iterable PV-T sizes if appropriate.
    if len(simulation_pvt_sizes) > 1:
        parameter_space.append(
            (
                ImpactingComponent.PV_T,
                "simulation" if len(parameter_space) == 0 else "pv-t size",
                simulation_pvt_sizes,
            )
        )
    else:
        component_sizes[ImpactingComponent.PV_T] = simulation_pvt_sizes[0]

    # Add the iterable PV sizes if appropriate.
    if len(simulation_pv_sizes) > 1:
        parameter_space.append(
            (
                ImpactingComponent.PV,
                "simulation" if len(parameter_space) == 0 else "pv size",
                simulation_pv_sizes,
            )
        )
    else:
        component_sizes[ImpactingComponent.PV] = simulation_pv_sizes[0]

    # Add the iterable storage sizes if appropriate.
    if len(simulation_storage_sizes) > 1:
        parameter_space.append(
            (
                ImpactingComponent.STORAGE,
                "simulation" if len(parameter_space) == 0 else "storage size",
                simulation_storage_sizes,
            )
        )
    else:
        component_sizes[ImpactingComponent.STORAGE] = simulation_storage_sizes[0]

    # Call the recursive simulation with these parameter and component sets of
    # information.
    _ = _recursive_iteration(
        convertors,
        end_year,
        finance_inputs,
        ghg_inputs,
        grid_profile,
        irradiance_data,
        kerosene_usage,
        location,
        logger,
        minigrid,
        optimisation,
        previous_system,
        scenario,
        start_year,
        temperature_data,
        total_loads,
        total_solar_pv_power_produced,
        wind_speed_data,
        yearly_electric_load_statistics,
        component_sizes=component_sizes,
        parameter_space=parameter_space,
        system_appraisals=system_appraisals,
    )

    logger.info("Optimisation bounds explored.")
    return (
        end_year,
        {
            convertor: ConvertorSize(size.max, size.min, size.step)
            for convertor, size in convertor_sizes.items()
        },
        SolarSystemSize(cw_pvt_size_max, cw_pvt_sizes.min, cw_pvt_sizes.step),
        TankSize(cw_tanks_max, cw_tanks.min, cw_tanks.step),
        SolarSystemSize(hw_pvt_size_max, hw_pvt_sizes.min, hw_pvt_sizes.step),
        TankSize(hw_tanks_max, hw_tanks.min, hw_tanks.step),
        SolarSystemSize(pv_size_max, pv_sizes.min, pv_sizes.step),
        StorageSystemSize(storage_size_max, storage_sizes.min, storage_sizes.step),
        largest_system_appraisal,
        previous_system,
        start_year,
        system_appraisals,
    )


def _optimisation_step(
    conventional_cw_source_profiles: Optional[Dict[WaterSource, pd.DataFrame]],
    convertor_sizes: Dict[Convertor, ConvertorSize],
    cw_pvt_sizes: SolarSystemSize,
    cw_tanks: TankSize,
    convertors: List[Convertor],
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    grid_profile: pd.DataFrame,
    hw_pvt_sizes: SolarSystemSize,
    hw_tanks: TankSize,
    irradiance_data: pd.Series,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    optimisation: Optimisation,
    optimisation_parameters: OptimisationParameters,
    previous_system: Optional[SystemAppraisal],
    pv_sizes: SolarSystemSize,
    scenario: Scenario,
    start_year: int,
    storage_sizes: StorageSystemSize,
    temperature_data: pd.Series,
    total_loads: Dict[ResourceType, Optional[pd.DataFrame]],
    total_solar_pv_power_produced: pd.Series,
    wind_speed_data: Optional[pd.Series],
    yearly_electric_load_statistics: pd.DataFrame,
) -> SystemAppraisal:
    """
    One optimisation step of the continuous lifetime optimisation

    Inputs:
        - conventional_cw_source_profiles:
            Mapping between :class:`WaterSource` instances and their availability
            proviles.
        - convertor_sizes:
            Mapping between :class:`Convertor` instances and the range of associated
            sizes.
        - cw_pvt_sizes:
            Range of clean-water PV-T sizes.
        - cw_tanks:
            Range of clean-water tank sizes.
        - convertors:
            The `list` of convertors available to the system.
        - finance_inputs:
            The finance input information.
        - grid_profile:
            The grid-availability profile.
        - irradiance_data:
            The total irradiance throughout the period of the simulation.
        - hw_pvt_sizes:
            Range of hot-water PV-T sizes.
        - hw_tanks:
            Range of hot-water tank sizes.
        - kerosene_usage:
            The kerosene-usage profile.
        - location:
            The location being considered.
        - minigrid:
            The energy system being considered.
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
        - temperature_data:
            The temperature data throughout the period of the simulation.
        - total_loads:
            A mapping between the :class:`ResourceType` and its associated total load.
        - total_solar_pv_power_produced:
            The total solar power output over the time period.
        - wind_speed_data:
            The wind-speed data throughout the period of the simulation.
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
        cw_tanks,
        pv_system_size,
        pvt_system_size,
        storage_system_size,
        _,
        previous_system,
        start_year,
        sufficient_systems,
    ) = _simulation_iteration(
        conventional_cw_source_profiles,
        convertor_sizes,
        cw_pvt_sizes,
        cw_tanks,
        convertors,
        finance_inputs,
        ghg_inputs,
        grid_profile,
        hw_pvt_sizes,
        hw_tanks,
        irradiance_data,
        kerosene_usage,
        location,
        logger,
        minigrid,
        optimisation,
        optimisation_parameters,
        previous_system,
        pv_sizes,
        scenario,
        start_year,
        storage_sizes,
        temperature_data,
        total_loads,
        total_solar_pv_power_produced,
        wind_speed_data,
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
        irradiance_data,
        kerosene_usage,
        cw_tanks,
        pv_system_size,
        pvt_system_size,
        storage_system_size,
        location,
        logger,
        minigrid,
        optimisation,
        previous_system,
        scenario,
        start_year,
        sufficient_systems,
        temperature_data,
        total_loads,
        total_solar_pv_power_produced,
        wind_speed_data,
        yearly_electric_load_statistics,
    )
    logger.info("Optimum systems determined.")

    # @@@ For now, the optimum system for a single threshold criterion will be returned.
    return list(optimum_systems.values())[0]


def multiple_optimisation_step(
    conventional_cw_source_profiles: Optional[Dict[WaterSource, pd.DataFrame]],
    convertors: List[Convertor],
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    grid_profile: pd.DataFrame,
    irradiance_data: pd.Series,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    optimisation: Optimisation,
    optimisation_parameters: OptimisationParameters,
    scenario: Scenario,
    temperature_data: pd.Series,
    total_loads: Dict[ResourceType, Optional[pd.DataFrame]],
    total_solar_pv_power_produced: pd.Series,
    wind_speed_data: Optional[pd.Series],
    yearly_electric_load_statistics: pd.DataFrame,
    *,
    input_convertor_sizes: Optional[Dict[Convertor, ConvertorSize]] = None,
    input_cw_pvt_sizes: Optional[SolarSystemSize] = None,
    input_cw_tanks: Optional[TankSize] = None,
    input_hw_pvt_sizes: Optional[SolarSystemSize] = None,
    input_hw_tanks: Optional[TankSize] = None,
    input_pv_sizes: Optional[SolarSystemSize] = None,
    input_storage_sizes: Optional[StorageSystemSize] = None,
    previous_system: Optional[SystemAppraisal] = None,
    start_year: int = 0,
) -> Tuple[datetime.timedelta, List[SystemAppraisal]]:
    """
    Carries out multiple optimisation steps of the continuous lifetime optimisation.

    Inputs:
        - convertors:
            The `list` of convertors available to the system;
        - grid_profile:
            The grid-availability profile;
        - irradiance_data:
            The total irradiance throughout the period of the simulation.
        - kerosene_usage:
            The kerosene-usage profile;
        - location:
            The location being considered;
        - minigrid:
            The energy system being considered;
        - optimisation:
            The optimisation currently being carried out;
        - optimisation_parameters:
            A :class:`OptimisationParameters` instance outlining the optimisation
            bounds;
        - scenario:
            The scenatio being considered;
        - solar_lifetime:
            The lifetime of the solar setup;
        - temperature_data:
            The temperature data throughout the period of the simulation;
        - total_loads:
            A mapping between :class:`ResourceType` and the associated total load placed
            of that resource type on the system;
        - total_solar_pv_power_produced:
            The total solar power output over the time period per unit PV installed;
        - wind_speed_data:
            The wind-speed data throughout the period of the simulation.
        - yearly_electric_load_statistics:
            The yearly electric load statistic information;
        - input_convertor_sizes:
            Mapping between :class:`Convertor` instances and the :class:`ConvertorSize`
            range available.
        - input_cw_tanks:
            Range of clean-water tank sizes as a :class:`TankSize` instance;
        - input_cw_pvt_sizes:
            Range of clean-water PV-T sizes as a :class:`SolarSystemSize` instance;
        - input_hw_tanks:
            Range of hot-water tank sizes as a :class:`TankSize` instance;
        - input_hw_pvt_sizes:
            Range of hot-water PV-T sizes as a :class:`SolarSystemSize` instance;
        - input_pv_sizes:
            Range of PV sizes as a :class:`SolarSystemSize` instance;
        - input_storage_sizes:
            Range of storage sizes as a :class:`StorageSystemSize` instance;
        - previous_system:
            Appraisal of the system already in place before this simulation period;
        - start_year:
            Start year of the initial optimisation step.

    Outputs:
        - time_delta:
            The time taken for the optimisation run;
        - results:
            The results of each Optimisation().optimisation_step(...)

    """

    # Start timer to see how long simulation will take
    timer_start = datetime.datetime.now()
    logger.info("Multiple optimisation step process begun.")

    # Initialise
    results: List[SystemAppraisal] = []

    # Set up the input convertor sizes for the first loop.
    if (
        input_convertor_sizes is None
        and len(convertors) > 0
        and len(optimisation_parameters.convertor_sizes) > 0
    ):
        logger.info(
            "No convertor sizes passed in, using default optimisation parameters."
        )
        input_convertor_sizes: Dict[
            Convertor, ConvertorSize
        ] = optimisation_parameters.convertor_sizes.copy()
    else:
        input_convertor_sizes = {}

    # Set up the clean-water PV-T sizes for the first loop.
    if (
        input_cw_pvt_sizes is None
        and scenario.desalination_scenario is not None
        and minigrid.pvt_panel is not None
    ):
        if optimisation_parameters.cw_pvt_size is None:
            raise InternalError(
                "{}Optimisation parameters do not have hot-water PV-T params ".format(
                    BColours.fail
                )
                + "despite hot-water being specified in the scenario.{}".format(
                    BColours.endc
                )
            )
        logger.info(
            "No hot-water PV-T sizes passed in, using default optimisation parameters."
        )
        input_cw_pvt_sizes = SolarSystemSize(
            optimisation_parameters.cw_pvt_size.max,
            optimisation_parameters.cw_pvt_size.min,
            optimisation_parameters.cw_pvt_size.step,
        )
    else:
        input_cw_pvt_sizes = SolarSystemSize()

    # Set up the clean-water tank sizes for the first loop.
    if (
        input_cw_tanks is None
        and scenario.desalination_scenario is not None
        and minigrid.clean_water_tank is not None
    ):
        if optimisation_parameters.clean_water_tanks is None:
            raise InternalError(
                "{}Optimisation parameters do not have clean-water tank params ".format(
                    BColours.fail
                )
                + "despite clean-water being specified in the scenario.{}".format(
                    BColours.endc
                )
            )
        logger.info(
            "No clean-water tank sizes passed in, using default optimisation parameters."
        )
        input_cw_tanks = TankSize(
            optimisation_parameters.clean_water_tanks.max,
            optimisation_parameters.clean_water_tanks.min,
            optimisation_parameters.clean_water_tanks.step,
        )
    else:
        input_cw_tanks = TankSize()

    # Set up the hot-water PV-T sizes for the first loop.
    if (
        input_hw_pvt_sizes is None
        and scenario.hot_water_scenario is not None
        and minigrid.pvt_panel is not None
    ):
        if optimisation_parameters.hw_pvt_size is None:
            raise InternalError(
                "{}Optimisation parameters do not have hot-water PV-T params ".format(
                    BColours.fail
                )
                + "despite hot-water being specified in the scenario.{}".format(
                    BColours.endc
                )
            )
        logger.info(
            "No hot-water PV-T sizes passed in, using default optimisation parameters."
        )
        input_hw_pvt_sizes = SolarSystemSize(
            optimisation_parameters.hw_pvt_size.max,
            optimisation_parameters.hw_pvt_size.min,
            optimisation_parameters.hw_pvt_size.step,
        )
    else:
        input_hw_pvt_sizes = SolarSystemSize()

    # Set up the hot-water tank sizes for the first loop
    if (
        input_hw_tanks is None
        and scenario.hot_water_scenario is not None
        and minigrid.hot_water_tank is not None
    ):
        if optimisation_parameters.hot_water_tanks is None:
            raise InternalError(
                "{}Optimisation parameters do not have hot-water tank params ".format(
                    BColours.fail
                )
                + "despite hot-water being specified in the scenario.{}".format(
                    BColours.endc
                )
            )
        logger.info(
            "No hot-water tank sizes passed in, using default optimisation parameters."
        )
        input_hw_tanks = TankSize(
            optimisation_parameters.hot_water_tanks.max,
            optimisation_parameters.hot_water_tanks.min,
            optimisation_parameters.hot_water_tanks.step,
        )
    else:
        input_hw_tanks = TankSize()

    if input_pv_sizes is None:
        if scenario.pv:
            logger.info("No pv sizes passed in, using default optimisation parameters.")
            input_pv_sizes = SolarSystemSize(
                optimisation_parameters.pv_size.max,
                optimisation_parameters.pv_size.min,
                optimisation_parameters.pv_size.step,
            )
        else:
            logger.info(
                "No pv sizes passed in, %sPV is disabled%s so no PV sizes will be "
                "considered.",
                BColours.fail,
                BColours.endc,
            )
            input_pv_sizes = SolarSystemSize()

    if input_storage_sizes is None:
        if scenario.battery:
            logger.info(
                "No storage sizes passed in, using default optimisation parameters."
            )
            input_storage_sizes = StorageSystemSize(
                optimisation_parameters.storage_size.max,
                optimisation_parameters.storage_size.min,
                optimisation_parameters.storage_size.step,
            )
        else:
            logger.info(
                "No storage sizes passed in, %sPV is disabled%s so no PV sizes will be "
                "considered.",
                BColours.fail,
                BColours.endc,
            )
            input_storage_sizes = StorageSystemSize()

    # Iterate over each optimisation step
    for _ in tqdm(
        range(int(optimisation_parameters.number_of_iterations)),
        desc="optimisation steps",
        leave=True,
        unit="step",
    ):
        logger.info("Beginning optimisation step.")

        # Fetch the optimum systems for this step.
        optimum_system = _optimisation_step(
            conventional_cw_source_profiles,
            input_convertor_sizes.copy(),
            SolarSystemSize(
                input_cw_pvt_sizes.max,
                input_cw_pvt_sizes.min,
                input_cw_pvt_sizes.step,
            ),
            TankSize(
                input_cw_tanks.max,
                input_cw_tanks.min,
                input_cw_tanks.step,
            ),
            convertors,
            finance_inputs,
            ghg_inputs,
            grid_profile,
            SolarSystemSize(
                input_hw_pvt_sizes.max,
                input_hw_pvt_sizes.min,
                input_hw_pvt_sizes.step,
            ),
            TankSize(
                input_hw_tanks.max,
                input_hw_tanks.min,
                input_hw_tanks.step,
            ),
            irradiance_data,
            kerosene_usage,
            location,
            logger,
            minigrid,
            optimisation,
            optimisation_parameters,
            previous_system,
            SolarSystemSize(
                input_pv_sizes.max, input_pv_sizes.min, input_pv_sizes.step
            ),
            scenario,
            start_year,
            StorageSystemSize(
                input_storage_sizes.max,
                input_storage_sizes.min,
                input_storage_sizes.step,
            ),
            temperature_data,
            total_loads,
            total_solar_pv_power_produced,
            wind_speed_data,
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

        # Prepare the clean-water tank parameters
        cw_tanks_min = optimum_system.system_details.final_num_cw_tanks
        cw_tanks_max = float(
            optimisation_parameters.cw_tanks_max
            + optimum_system.system_details.final_num_cw_tanks
        )
        input_cw_tanks = TankSize(
            int(cw_tanks_min),
            int(cw_tanks_max),
            int(optimisation_parameters.cw_tanks_step),
        )

        # Prepare the pv-size parameters
        pv_size_min = optimum_system.system_details.final_pv_size
        pv_size_max = float(
            optimisation_parameters.pv_size.max
            + optimum_system.system_details.final_pv_size
        )
        input_pv_sizes = SolarSystemSize(
            int(pv_size_max),
            int(pv_size_min),
            int(optimisation_parameters.pv_size.step),
        )

        # Prepare the storage-size parameters
        storage_size_min = optimum_system.system_details.final_storage_size
        storage_size_max = float(
            optimisation_parameters.storage_size.max
            + optimum_system.system_details.final_storage_size
        )
        input_storage_sizes = StorageSystemSize(
            int(storage_size_max),
            int(storage_size_min),
            int(optimisation_parameters.storage_size.step),
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
#             ColumnHeader.BLACKOUTS.value,
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
#         blackouts = np.mean(optimisation_results[ColumnHeader.BLACKOUTS.value])
#         kerosene_displacement = np.mean(optimisation_results["Kerosene displacement"])
#         #   Data where the sum is most relevant
#         total_energy = np.sum(optimisation_results["Total energy (kWh)"])
#         unmet_energy = np.sum(optimisation_results[ColumnHeader.UNMET_ELECTRICITY.value])
#         renewable_energy = np.sum(optimisation_results["Renewable energy (kWh)"])
#         storage_energy = np.sum(optimisation_results["Storage energy (kWh)"])
#         grid_energy = np.sum(optimisation_results[ColumnHeader.GRID_ENERGY.value])
#         diesel_energy = np.sum(optimisation_results[ColumnHeader.DIESEL_ENERGY_SUPPLIED.value])
#         discounted_energy = np.sum(optimisation_results["Discounted energy (kWh)"])
#         diesel_fuel_usage = np.sum(optimisation_results[ColumnHeader.DIESEL_FUEL_USAGE.value])
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
#                 ColumnHeader.BLACKOUTS.value: blackouts,
#                 "Unmet fraction": unmet_fraction,
#                 "Renewables fraction": renewables_fraction,
#                 "Storage fraction": storage_fraction,
#                 "Diesel fraction": diesel_fraction,
#                 "Grid fraction": grid_fraction,
#                 "Total energy (kWh)": total_energy,
#                 ColumnHeader.UNMET_ELECTRICITY.value: unmet_energy,
#                 "Renewable energy (kWh)": renewable_energy,
#                 "Storage energy (kWh)": storage_energy,
#                 ColumnHeader.GRID_ENERGY.value: grid_energy,
#                 ColumnHeader.DIESEL_ENERGY_SUPPLIED.value: diesel_energy,
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
#                 ColumnHeader.DIESEL_FUEL_USAGE.value: diesel_fuel_usage,
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
#                     total_solar_pv_power_produced,
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
