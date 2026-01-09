#!/usr/bin/python3.10
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
import functools
import math

from collections import defaultdict
from logging import Logger
from typing import Any

import json
import numpy as np  # pylint: disable=import-error
import pandas as pd  # pylint: disable=import-error

from tqdm import tqdm

from ..simulation.__utils__ import determine_available_converters
from ..simulation import energy_system

from ..__utils__ import (
    BColours,
    DONE,
    InternalError,
    Location,
    RenewableEnergySource,
    ResourceType,
    Simulation,
)
from ..conversion.conversion import Converter, WaterSource
from ..impact.finance import ImpactingComponent
from .appraisal import appraise_system, SystemAppraisal
from .single_line_simulation import single_line_simulation
from .__utils__ import (
    converters_from_sizing,
    ConverterSize,
    Criterion,
    CriterionMode,
    get_sufficient_appraisals,
    Optimisation,
    OptimisationParameters,
    recursive_iteration,
    SolarSystemSize,
    StorageSystemSize,
    TankSize,
)

__all__ = ("multiple_optimisation_step",)


# SYSTEM_APPRAISALS:
#   Object capable of storing optimum appraisal information.
SYSTEM_APPRAISALS: defaultdict[tuple[int, Criterion], list[SystemAppraisal]] = (
    defaultdict(list)
)


def _fetch_optimum_system(
    optimisation: Optimisation, sufficient_systems: list[SystemAppraisal]
) -> dict[Criterion, SystemAppraisal]:
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

    optimum_systems: dict[Criterion, SystemAppraisal] = {}

    # Run through the various optimisation criteria.
    for criterion, criterion_mode in optimisation.optimisation_criteria.items():
        # Sort by the optimisation criterion.
        sufficient_systems.sort(
            key=lambda appraisal, crit=criterion: appraisal.criteria[crit],  # type: ignore
            reverse=(criterion_mode == CriterionMode.MAXIMISE),
        )

        # Add the optimum system, keyed by the optimisation criterion.
        optimum_systems[criterion] = sufficient_systems[0]

    return optimum_systems


def _find_optimum_system(  # pylint: disable=too-many-locals
    conventional_cw_source_profiles: dict[WaterSource, pd.DataFrame] | None,
    converters: dict[str, Converter],
    disable_tqdm: bool,
    end_year: int,
    finance_inputs: dict[str, Any],
    ghg_inputs: dict[str, Any],
    grid_profile: pd.DataFrame | None,
    irradiance_data: dict[str, pd.Series],
    kerosene_usage: pd.DataFrame,
    largest_converter_sizes: dict[Converter, ConverterSize],
    largest_cw_pvt_system_size: SolarSystemSize,
    largest_cw_st_system_size: SolarSystemSize,
    largest_cw_tank_size: TankSize,
    largest_hw_pvt_system_size: SolarSystemSize,
    largest_hw_st_system_size: SolarSystemSize,
    largest_hw_tank_size: TankSize,
    largest_pv_system_size: SolarSystemSize,
    largest_storage_system_size: StorageSystemSize,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    optimisation: Optimisation,
    previous_system: SystemAppraisal | None,
    start_year: int,
    system_appraisals: list[SystemAppraisal],
    temperature_data: dict[str, pd.Series],
    total_loads: dict[ResourceType, pd.DataFrame | None],
    total_solar_pv_power_produced: dict[str, pd.Series],
    wind_speed_data: pd.Series | None,
    yearly_electric_load_statistics: pd.DataFrame,
) -> dict[Criterion, SystemAppraisal]:
    """
    Finds the optimum system from a group of sufficient systems.

    This function determines the optimum system from s group of sufficient systems. It
    contains functionality that enables it to increase the system size if necessary if
    the simulation is an edge case

    Inputs:
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - end_year:
            The end year of the simulation run currently being considered.
        - largest_converter_sizes:
            The maximum size of each converter that was installed.
        - largest_cw_pvt_system_size:
            The maximum size of clean-water PV-T system installed.
        - largest_cw_st_system_size:
            The maximum size of clean-water solar-thermal system installed.
        - largest_cw_tank_size:
            The maximum size of clean-water tanks installed.
        - largest_hw_pvt_system_size:
            The maximum size of hot-water PV-T system installed.
        - largest_hw_st_system_size:
            The maximum size of hot-water solar-thermal system installed.
        - largest_hw_tank_size:
            The maximum size of hot-water tanks installed.
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
        - A mapping between optimisation criteria and the optimum system corresponding
          to each criterion.

    """

    # Check to find optimum system
    logger.info("Determining optimum system from %s systems.", len(system_appraisals))
    optimum_systems = _fetch_optimum_system(optimisation, system_appraisals)
    if any(system.criteria is None for system in optimum_systems.values()):
        logger.error(
            "%sNot all systems passed to `find_optimum_system` function contained "
            "optimisation criteria.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InternalError("Threshold criteria not set on system appraisal.")

    logger.info(
        "Optimum system(s) determined: %s",
        "\n".join(
            [
                f"criterion: {criterion}, "
                + f"value: {system.criteria[criterion]}\n"  # type: ignore
                + f"system_details: {system.system_details}"
                for criterion, system in optimum_systems.items()
            ]
        ),
    )

    for optimisation_criterion, optimum_system in tqdm(
        optimum_systems.items(),
        desc="checking upper bound",
        disable=disable_tqdm,
        leave=False,
        unit="system",
    ):
        # Check if optimum system was the largest system simulated
        while (
            any(
                optimum_system.system_details.initial_converter_sizes[  # type: ignore
                    converter.name
                ]
                == sizes.max
                for converter, sizes in largest_converter_sizes.items()
            )
            or (
                optimum_system.system_details.initial_cw_pvt_sizes
                == largest_cw_pvt_system_size.max
                and optimisation.scenario.desalination_scenario is not None
                and optimisation.scenario.pv_t
            )
            or (
                optimum_system.system_details.initial_cw_st_sizes
                == largest_cw_st_system_size.max
                and optimisation.scenario.desalination_scenario is not None
                and optimisation.scenario.solar_thermal
            )
            or (
                optimum_system.system_details.initial_num_clean_water_tanks
                == largest_cw_tank_size.max
                and optimisation.scenario.desalination_scenario is not None
            )
            or (
                optimum_system.system_details.initial_hw_pvt_sizes
                == largest_hw_pvt_system_size.max
                and optimisation.scenario.hot_water_scenario is not None
                and optimisation.scenario.pv_t
            )
            or (
                optimum_system.system_details.initial_hw_st_sizes
                == largest_hw_st_system_size.max
                and optimisation.scenario.hot_water_scenario is not None
                and optimisation.scenario.solar_thermal
            )
            or (
                optimum_system.system_details.initial_num_hot_water_tanks
                == largest_hw_tank_size.max
                and optimisation.scenario.hot_water_scenario is not None
            )
            or (
                optimum_system.system_details.initial_pv_size
                == largest_pv_system_size.max
                and optimisation.scenario.pv
            )
            or (
                optimum_system.system_details.initial_storage_size
                == largest_storage_system_size.max
                and optimisation.scenario.battery
            )
        ):
            # Do single line optimisation to see if larger system is superior
            (
                largest_converter_sizes,
                largest_cw_pvt_system_size,
                largest_cw_st_system_size,
                largest_cw_tank_size,
                largest_hw_pvt_system_size,
                largest_hw_st_system_size,
                largest_hw_tank_size,
                largest_pv_system_size,
                largest_storage_system_size,
                new_system_appraisals,
            ) = single_line_simulation(
                conventional_cw_source_profiles,
                largest_converter_sizes,
                largest_cw_pvt_system_size,
                largest_cw_st_system_size,
                largest_cw_tank_size,
                converters,
                disable_tqdm,
                end_year,
                finance_inputs,
                ghg_inputs,
                grid_profile,
                largest_hw_pvt_system_size,
                largest_hw_st_system_size,
                largest_hw_tank_size,
                irradiance_data,
                kerosene_usage,
                location,
                logger,
                minigrid,
                optimisation,
                optimum_system,
                previous_system,
                largest_pv_system_size,
                start_year,
                largest_storage_system_size,
                temperature_data,
                total_loads,
                total_solar_pv_power_produced,
                wind_speed_data,
                yearly_electric_load_statistics,
            )

            # Determine the optimum system from the new systems simulated.
            if len(new_system_appraisals) > 0:
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
                    "Determining optimum system from %s systems.",
                    len(system_comparison),
                )
                optimum_system = _fetch_optimum_system(optimisation, system_comparison)[
                    optimisation_criterion
                ]
            else:
                logger.info(
                    "None of the additional systems considered were sufficient."
                )

        optimum_systems[optimisation_criterion] = optimum_system

    # Return the confirmed optimum system
    return optimum_systems


def _simulation_iteration(  # pylint: disable=too-many-locals, too-many-statements
    conventional_cw_source_profiles: dict[WaterSource, pd.DataFrame] | None,
    converter_sizes: dict[Converter, ConverterSize],
    cw_buffer_tanks: TankSize,
    cw_pvt_system_size: SolarSystemSize,
    cw_st_system_size: SolarSystemSize,
    cw_tanks: TankSize,
    converters: dict[str, Converter],
    disable_tqdm: bool,
    finance_inputs: dict[str, Any],
    ghg_inputs: dict[str, Any],
    grid_profile: pd.DataFrame | None,
    hw_buffer_tanks: TankSize,
    hw_pvt_system_size: SolarSystemSize,
    hw_st_system_size: SolarSystemSize,
    hw_tanks: TankSize,
    irradiance_data: dict[str, pd.Series],
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    optimisation: Optimisation,
    optimisation_parameters: OptimisationParameters,
    previous_system: SystemAppraisal | None,
    pv_sizes: SolarSystemSize,
    start_year: int,
    storage_sizes: StorageSystemSize,
    temperature_data: dict[str, pd.Series],
    total_loads: dict[ResourceType, pd.DataFrame | None],
    total_solar_pv_power_produced: dict[str, pd.Series],
    wind_speed_data: pd.Series | None,
    yearly_electric_load_statistics: pd.DataFrame,
) -> tuple[
    int,
    dict[Converter, ConverterSize],
    SolarSystemSize,
    TankSize,
    SolarSystemSize,
    TankSize,
    SolarSystemSize,
    StorageSystemSize,
    SystemAppraisal,
    SystemAppraisal | None,
    int,
    list[SystemAppraisal],
]:
    """
    Carries out a simulation iteration.

    New simulation iteration i.e. checks sufficiency and stops when criteria is not met,
    increases system size when no sufficient system exists.

    Inputs:
        - conventional_cw_source_profiles:
            A mapping between conventional water sources and their availability
            profiles.
        - cw_pvt_system_size:
            The range of clean-water PV-T sizes.
        - cw_st_system_size:
            The range of clean-water solar-thermal sizes.
        - cw_tanks:
            Range of clean-water tanks.
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - finance_inputs:
            The financial input information.
        - ghg_inputs:
            The green-house-gas input information.
        - grid_profile:
            The grid-availability profile.
        - hw_pvt_system_size:
            The range of hot-water PV-T sizes.
        - hw_st_system_size:
            The range of hot-water solar-thermal sizes.
        - hw_tanks:
            Range of hot-water tanks.
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
        - largest_converter_size:
            A mapping between :class:`Converter` instances and the size associated with
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
    system_appraisals: list[SystemAppraisal] = []
    end_year: int = start_year + int(optimisation_parameters.iteration_length)

    # Check if largest system is sufficient
    logger.info("Checking whether the largest system is sufficient.")
    tqdm.write(
        f"Determining largest suitable system {'.' * 27}    ",
        end="\n",
    )

    # Determine the maximum sizes of each converter defined.
    max_converter_sizes: dict[Converter, int] = {
        converter: size.max for converter, size in converter_sizes.items()
    }

    # Append converters defined elsewhere.
    available_converters: list[Converter] = determine_available_converters(
        converters, logger, minigrid, optimisation.scenario
    )
    static_converter_sizes: dict[Converter, int] = {
        converter: available_converters.count(converter)
        for converter in available_converters
        if converter not in max_converter_sizes
    }
    simulation_converter_sizes: dict[Converter, int] = {
        **max_converter_sizes,
        **static_converter_sizes,
    }

    _, simulation_results, system_details = energy_system.run_simulation(
        int(cw_pvt_system_size.max),
        int(cw_st_system_size.max),
        conventional_cw_source_profiles,
        converters_from_sizing(simulation_converter_sizes),
        disable_tqdm,
        storage_sizes.max,
        grid_profile,
        int(hw_pvt_system_size.max),
        int(hw_st_system_size.max),
        irradiance_data,
        kerosene_usage,
        location,
        logger,
        minigrid,
        cw_buffer_tanks.max,
        cw_tanks.max,
        hw_buffer_tanks.max,
        hw_tanks.max,
        total_solar_pv_power_produced,
        {minigrid.pv_panel.name: pv_sizes.max},
        optimisation.scenario,
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
        minigrid.inverter,
        location,
        logger,
        previous_system,
        optimisation.scenario,
        simulation_results,
        start_year,
        system_details,
    )

    # Instantiate in preparation of the while loop.
    cw_pvt_size_max = cw_pvt_system_size.max
    cw_st_size_max = cw_st_system_size.max
    cw_tanks_max = cw_tanks.max
    hw_pvt_size_max = hw_pvt_system_size.max
    hw_st_size_max = hw_st_system_size.max
    hw_tanks_max = hw_tanks.max
    pv_size_max = pv_sizes.max
    storage_size_max = storage_sizes.max

    # Increase system size until largest system is sufficient (if necessary)
    while not get_sufficient_appraisals(optimisation, [largest_system_appraisal]):
        if largest_system_appraisal.criteria is None:
            logger.error(
                "%sOptimisation failed to return threshold criteria.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError("Threshold criteria not set on system appraisal.")

        logger.info(
            "The largest system was found to be insufficient. Threshold criteria: %s",
            json.dumps(
                {
                    str(key.value): value
                    for key, value in largest_system_appraisal.criteria.items()
                },
                indent=4,
            ),
        )

        # Round out the various variables.
        cw_pvt_size_max = float(
            np.ceil(cw_pvt_size_max / cw_pvt_system_size.step) * cw_pvt_system_size.step
        )
        cw_st_size_max = float(
            np.ceil(cw_st_size_max / cw_st_system_size.step) * cw_st_system_size.step
        )
        hw_pvt_size_max = float(
            np.ceil(hw_pvt_size_max / hw_pvt_system_size.step) * hw_pvt_system_size.step
        )
        hw_st_size_max = float(
            np.ceil(hw_st_size_max / hw_st_system_size.step) * hw_st_system_size.step
        )
        pv_size_max = float(np.ceil(pv_size_max / pv_sizes.step) * pv_sizes.step)
        storage_size_max = float(
            np.ceil(storage_size_max / storage_sizes.step) * storage_sizes.step
        )

        logger.info(
            "Probing system upper bounds: pv_size: %s, storage_size: %s%s%s%s%s%s",
            pv_size_max,
            storage_size_max,
            (
                f", clean-water PV-T size: {cw_pvt_size_max}"
                if optimisation.scenario.desalination_scenario is not None
                and optimisation.scenario.pv_t
                else ""
            ),
            (
                f", num clean-water tanks: {cw_tanks_max}"
                if optimisation.scenario.desalination_scenario is not None
                else ""
            ),
            (
                f", hot-water PV-T size: {hw_pvt_size_max}"
                if optimisation.scenario.hot_water_scenario is not None
                and optimisation.scenario.pv_t
                else ""
            ),
            (
                f", num hot-water tanks: {hw_tanks_max}"
                if optimisation.scenario.hot_water_scenario is not None
                else ""
            ),
            ", ".join(
                [
                    f"{converter.name} size: {size}"
                    for converter, size in max_converter_sizes.items()
                ]
            ),
        )

        # Run a simulation and appraise it.
        _, simulation_results, system_details = energy_system.run_simulation(
            int(cw_pvt_size_max),
            int(hw_st_size_max),
            conventional_cw_source_profiles,
            converters_from_sizing(simulation_converter_sizes),
            disable_tqdm,
            storage_size_max,
            grid_profile,
            int(hw_pvt_size_max),
            int(hw_st_size_max),
            irradiance_data,
            kerosene_usage,
            location,
            logger,
            minigrid,
            cw_tanks_max,
            hw_tanks_max,
            total_solar_pv_power_produced,
            {minigrid.pv_panel.name: pv_size_max},
            optimisation.scenario,
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
            minigrid.inverter,
            location,
            logger,
            previous_system,
            optimisation.scenario,
            simulation_results,
            start_year,
            system_details,
        )

        if largest_system_appraisal.criteria is None:
            logger.error(
                "%sOptimisation failed to return threshold criteria.%s",
                BColours.fail,
                BColours.endc,
            )
            raise InternalError("Threshold criteria not set on system appraisal.")

        # Increment the system sizes.
        cw_pvt_size_max += (
            cw_pvt_system_size.step
            if optimisation.scenario.desalination_scenario is not None
            and optimisation.scenario.pv_t
            else 0
        )
        cw_tanks_max += (
            cw_tanks.step
            if optimisation.scenario.desalination_scenario is not None
            else 0
        )
        hw_pvt_size_max += (
            hw_pvt_system_size.step
            if optimisation.scenario.hot_water_scenario is not None
            and optimisation.scenario.pv_t
            else 0
        )
        hw_tanks_max += (
            hw_tanks.step if optimisation.scenario.hot_water_scenario is not None else 0
        )
        max_converter_sizes = {
            converter: max_converter_sizes[converter] + size.step
            for converter, size in converter_sizes.items()
        }
        simulation_converter_sizes = {**max_converter_sizes, **static_converter_sizes}
        pv_size_max += pv_sizes.step if optimisation.scenario.pv else 0
        storage_size_max += storage_sizes.step if optimisation.scenario.battery else 0

    # Output that the search for the largest suitable system was successful.
    tqdm.write(
        f"Determining largest suitable system {'.' * 27}    {DONE}",
        end="\n",
    )
    if largest_system_appraisal.criteria is None:
        logger.error(
            "%sOptimisation failed to return threshold criteria.%s",
            BColours.fail,
            BColours.endc,
        )
        raise InternalError("Threshold criteria not set on system appraisal.")

    logger.info(
        "System was found to be sufficient. Threshold criteria: %s",
        json.dumps(
            {
                str(key.value): value
                for key, value in largest_system_appraisal.criteria.items()
            },
            indent=4,
        ),
    )
    system_appraisals.append(largest_system_appraisal)

    # Round the maximum PV and storage sizes to be increments of the steps involved.
    cw_pvt_size_max = (
        float(np.ceil(cw_pvt_size_max / cw_pvt_system_size.step))
        * cw_pvt_system_size.step
    )
    hw_pvt_size_max = (
        float(np.ceil(hw_pvt_size_max / hw_pvt_system_size.step))
        * hw_pvt_system_size.step
    )
    pv_size_max = float(np.ceil(pv_size_max / pv_sizes.step)) * pv_sizes.step
    storage_size_max = float(
        np.ceil(storage_size_max / storage_sizes.step) * storage_sizes.step
    )
    logger.info(
        "Largest system size determined:\n- pv_size: %s\n%s%s%s%s- storage_size: %s",
        pv_size_max,
        (
            f"- clean-water pvt-size: {cw_pvt_size_max}\n"
            if minigrid.pvt_panel is not None
            and optimisation.scenario.desalination_scenario is not None
            else ""
        ),
        (
            f"- num clean-water tanks: {cw_tanks_max}\n"
            if minigrid.clean_water_tank is not None
            and optimisation.scenario.desalination_scenario is not None
            else ""
        ),
        (
            f"- hot-water pvt-size: {hw_pvt_size_max}\n"
            if minigrid.pvt_panel is not None
            and optimisation.scenario.hot_water_scenario is not None
            else ""
        ),
        (
            f"- num hot-water tanks: {hw_tanks_max}\n"
            if minigrid.hot_water_tank is not None
            and optimisation.scenario.hot_water_scenario is not None
            else ""
        ),
        storage_size_max,
    )

    # set up the various variables ready for recursive iteration.
    component_sizes: dict[
        Converter | ImpactingComponent | RenewableEnergySource, float
    ] = {}
    parameter_space: list[
        tuple[
            Converter | ImpactingComponent | RenewableEnergySource,
            str,
            list[float] | list[int],
        ]
    ] = []

    # Check that a valid set of sizes were passed in and warn the user if not.
    if not isinstance(pv_sizes.step, int) and minigrid.pv_panel.pv_unit_overrided:
        logger.warning(
            "The pv-panel unit size of %s is not an integer, and a non-integer pv step "
            "size of %s has also been selected.",
            round(minigrid.pv_panel.pv_unit, 2),
            round(pv_sizes.step, 2),
        )
    if minigrid.battery is not None:
        if not isinstance(storage_sizes.step, int) and not isinstance(
            minigrid.battery.capacity, int
        ):
            logger.warning(
                "The battery capacity of %s is not an integer capacity, and a non-integer "
                "storage step size of %s has also been selected.",
                round(minigrid.battery.capacity, 2),
                round(storage_sizes.step, 2),
            )

    simulation_cw_pvt_system_size: list[int] = sorted(
        range(
            int(cw_pvt_system_size.min),
            int(cw_pvt_size_max + cw_pvt_system_size.step),
            int(cw_pvt_system_size.step),
        ),
        reverse=True,
    )
    simulation_cw_tanks: list[int] = sorted(
        range(
            cw_tanks.min,
            cw_tanks_max + cw_tanks.step,
            cw_tanks.step,
        ),
        reverse=True,
    )
    simulation_hw_pvt_system_size: list[int] = sorted(
        range(
            int(hw_pvt_system_size.min),
            int(hw_pvt_size_max + hw_pvt_system_size.step),
            int(hw_pvt_system_size.step),
        ),
        reverse=True,
    )
    simulation_hw_tanks: list[int] = sorted(
        range(
            hw_tanks.min,
            hw_tanks_max + hw_tanks.step,
            hw_tanks.step,
        ),
        reverse=True,
    )
    simulation_pv_sizes: list[int] = sorted(
        np.arange(pv_sizes.min, pv_size_max + pv_sizes.step, pv_sizes.step),
        reverse=True,
    )
    simulation_storage_sizes: list[int] = sorted(
        np.arange(
            storage_sizes.min,
            storage_size_max + storage_sizes.step,
            storage_sizes.step,
        ),
        reverse=True,
    )

    # set up the various iteration variables accordingly.
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

    # Add the iterable clean-water PV-T sizes if appropriate.
    if len(simulation_cw_pvt_system_size) > 1:
        parameter_space.append(
            (
                RenewableEnergySource.CLEAN_WATER_PVT,
                "simulation" if len(parameter_space) == 0 else "cw pv-t size",
                simulation_cw_pvt_system_size,
            )
        )
    else:
        component_sizes[RenewableEnergySource.CLEAN_WATER_PVT] = (
            simulation_cw_pvt_system_size[0]
        )

    # Add the iterable converter sizes.
    for converter, sizes in converter_sizes.items():
        # Construct the list of available sizes for the given converter.
        simulation_converter_size_list: list[int] = sorted(
            range(
                int(sizes.min),
                int(max_converter_sizes[converter] + sizes.step),
                int(sizes.step),
            ),
            reverse=True,
        )

        if len(simulation_converter_size_list) > 1:
            parameter_space.append(
                (
                    converter,
                    (
                        "simulation"
                        if len(parameter_space) == 0
                        else f"{converter.name} size"
                    ),
                    simulation_converter_size_list,
                )
            )
        else:
            component_sizes[converter] = float(simulation_converter_sizes[0])  # type: ignore

    # Add the static converter sizes.
    for converter, size in static_converter_sizes.items():
        component_sizes[converter] = size

    # Add the iterable hot-water tank sizes if appropriate.
    if len(simulation_hw_tanks) > 1:
        parameter_space.append(
            (
                ImpactingComponent.HOT_WATER_TANK,
                "simulation" if len(parameter_space) == 0 else "hw tank size",
                simulation_hw_tanks,
            )
        )
    else:
        component_sizes[ImpactingComponent.HOT_WATER_TANK] = simulation_hw_tanks[0]

    # Add the iterable hot-water PV-T sizes if appropriate.
    if len(simulation_hw_pvt_system_size) > 1:
        parameter_space.append(
            (
                RenewableEnergySource.HOT_WATER_PVT,
                "simulation" if len(parameter_space) == 0 else "hw pv-t size",
                simulation_hw_pvt_system_size,
            )
        )
    else:
        component_sizes[RenewableEnergySource.HOT_WATER_PVT] = (
            simulation_hw_pvt_system_size[0]
        )

    # Add the iterable PV sizes if appropriate.
    if len(simulation_pv_sizes) > 1:
        parameter_space.append(
            (
                RenewableEnergySource.PV,
                "simulation" if len(parameter_space) == 0 else "pv size",
                simulation_pv_sizes,
            )
        )
    else:
        component_sizes[RenewableEnergySource.PV] = simulation_pv_sizes[0]

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
    _ = recursive_iteration(
        conventional_cw_source_profiles,
        disable_tqdm,
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
            converter: ConverterSize(
                max_size,
                converter_sizes[converter].min,
                converter_sizes[converter].step,
            )
            for converter, max_size in max_converter_sizes.items()
        },
        SolarSystemSize(
            cw_pvt_size_max, cw_pvt_system_size.min, cw_pvt_system_size.step
        ),
        TankSize(cw_tanks_max, cw_tanks.min, cw_tanks.step),
        SolarSystemSize(
            hw_pvt_size_max, hw_pvt_system_size.min, hw_pvt_system_size.step
        ),
        TankSize(hw_tanks_max, hw_tanks.min, hw_tanks.step),
        SolarSystemSize(pv_size_max, pv_sizes.min, pv_sizes.step),
        StorageSystemSize(storage_size_max, storage_sizes.min, storage_sizes.step),
        largest_system_appraisal,
        previous_system,
        start_year,
        system_appraisals,
    )


def _optimisation_step(  # pylint: disable=too-many-locals
    conventional_cw_source_profiles: dict[WaterSource, pd.DataFrame] | None,
    converter_sizes: dict[Converter, ConverterSize],
    cw_buffer_tanks: TankSize,
    cw_pvt_system_size: SolarSystemSize,
    cw_st_system_size: SolarSystemSize,
    cw_tanks: TankSize,
    converters: dict[str, Converter],
    disable_tqdm: bool,
    finance_inputs: dict[str, Any],
    ghg_inputs: dict[str, Any],
    grid_profile: pd.DataFrame | None,
    hw_buffer_tanks: TankSize,
    hw_pvt_system_size: SolarSystemSize,
    hw_st_system_size: SolarSystemSize,
    hw_tanks: TankSize,
    irradiance_data: dict[str, pd.Series],
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    optimisation: Optimisation,
    optimisation_parameters: OptimisationParameters,
    previous_system: SystemAppraisal | None,
    pv_sizes: SolarSystemSize,
    start_year: int,
    storage_sizes: StorageSystemSize,
    temperature_data: dict[str, pd.Series],
    total_loads: dict[ResourceType, pd.DataFrame | None],
    total_solar_pv_power_produced: dict[str, pd.Series],
    wind_speed_data: pd.Series | None,
    yearly_electric_load_statistics: pd.DataFrame,
) -> SystemAppraisal:
    """
    One optimisation step of the continuous lifetime optimisation

    Inputs:
        - conventional_cw_source_profiles:
            Mapping between :class:`WaterSource` instances and their availability
            proviles.
        - converter_sizes:
            Mapping between :class:`Converter` instances and the range of associated
            sizes.
        - cw_pvt_system_size:
            Range of clean-water PV-T sizes.
        - cw_st_system_size:
            Range of clean-water solar-thermal sizes.
        - cw_tanks:
            Range of clean-water tank sizes.
        - converters:
            The `list` of converters available to the system.
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - finance_inputs:
            The finance input information.
        - grid_profile:
            The grid-availability profile.
        - irradiance_data:
            The total irradiance throughout the period of the simulation.
        - hw_pvt_system_size:
            Range of hot-water PV-T sizes.
        - hw_st_system_size:
            Range of hot-water solar-thermal sizes.
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
        converter_sizes,
        cw_pvt_system_size,
        cw_tanks,
        hw_pvt_system_size,
        hw_tanks,
        pv_system_size,
        storage_system_size,
        _,
        previous_system,
        start_year,
        sufficient_systems,
    ) = _simulation_iteration(
        conventional_cw_source_profiles,
        converter_sizes,
        cw_buffer_tanks,
        cw_pvt_system_size,
        cw_st_system_size,
        cw_tanks,
        converters,
        disable_tqdm,
        finance_inputs,
        ghg_inputs,
        grid_profile,
        hw_buffer_tanks,
        hw_pvt_system_size,
        hw_st_system_size,
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
        conventional_cw_source_profiles,
        converters,
        disable_tqdm,
        end_year,
        finance_inputs,
        ghg_inputs,
        grid_profile,
        irradiance_data,
        kerosene_usage,
        converter_sizes,
        cw_pvt_system_size,
        cw_st_system_size,
        cw_tanks,
        hw_pvt_system_size,
        hw_st_system_size,
        hw_tanks,
        pv_system_size,
        storage_system_size,
        location,
        logger,
        minigrid,
        optimisation,
        previous_system,
        start_year,
        sufficient_systems,
        temperature_data,
        total_loads,
        total_solar_pv_power_produced,
        wind_speed_data,
        yearly_electric_load_statistics,
    )
    logger.info("Optimum systems determined.")

    # For now, the optimum system for a single threshold criterion will be returned.
    optimum_system_appraisal: SystemAppraisal = list(optimum_systems.values())[0]
    return optimum_system_appraisal


def _target_function(
    *,
    available_converters: list[Converter],
    conventional_cw_source_profiles: dict[WaterSource, pd.DataFrame] | None,
    disable_tqdm: bool,
    finance_inputs: dict[str, Any],
    ghg_inputs: dict[str, Any],
    grid_profile: pd.DataFrame | None,
    irradiance_data: dict[str, pd.Series],
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    optimisation: Optimisation,
    optimisation_criterion: Criterion,
    optimisation_parameters: OptimisationParameters,
    previous_system,
    start_year: SystemAppraisal | None,
    static_converter_sizes: dict[str, float],
    temperature_data: dict[str, pd.Series],
    total_loads: dict[ResourceType, pd.DataFrame | None],
    total_solar_pv_power_produced: dict[str, pd.Series],
    wind_speed_data: pd.Series | None,
    yearly_electric_load_statistics: pd.DataFrame,
    cw_buffer_tanks: float = 0,
    cw_pvt_size: float = 0,
    cw_st_size: float = 0,
    clean_water_tanks: float = 0,
    hw_buffer_tanks: float = 0,
    hw_pvt_size: float = 0,
    hw_st_size: float = 0,
    hot_water_tanks: float = 0,
    pv_size: float = 0,
    storage_size: float = 0,
    **kwargs,
) -> float:
    """
    Target function for running a CLOVER simulation and returning the result.

    A CLOVER simulation is run, based on the information provided, and the
    target criterion is then determined. This is then returned.

    If a system doesn't meet the threshold criteria, then the system is rejected
    by a large negative value being returned.

    :param: kwargs
        Used for any and all converter sizes.

    """

    # Determine the inputs required for the system.
    end_year: int = start_year + int(optimisation_parameters.iteration_length)

    # Append converters defined elsewhere.
    dynamic_converter_sizes: dict[Converter, int] = {
        {converter.name: converter for converter in available_converters}[
            converter_name
        ]: math.floor(size)
        for converter_name, size in kwargs.items()
    }
    simulation_converter_sizes: dict[Converter, int] = {
        **dynamic_converter_sizes,
        **static_converter_sizes,
    }

    def _simulation_run() -> float:
        """Run a simulation and return the appraised result."""
        _, simulation_results, system_details = energy_system.run_simulation(
            math.floor(cw_pvt_size),
            math.floor(cw_st_size),
            conventional_cw_source_profiles,
            converters_from_sizing(simulation_converter_sizes),
            disable_tqdm,
            math.floor(storage_size),
            grid_profile,
            math.floor(hw_pvt_size),
            math.floor(hw_st_size),
            irradiance_data,
            kerosene_usage,
            location,
            logger,
            minigrid,
            math.floor(cw_buffer_tanks),
            math.floor(clean_water_tanks),
            math.floor(hw_buffer_tanks),
            math.floor(hot_water_tanks),
            total_solar_pv_power_produced,
            {minigrid.pv_panel.name: pv_size},
            optimisation.scenario,
            Simulation(end_year, start_year),
            temperature_data,
            total_loads,
            wind_speed_data,
        )

        system_appraisal = appraise_system(
            yearly_electric_load_statistics,
            end_year,
            finance_inputs,
            ghg_inputs,
            minigrid.inverter,
            location,
            logger,
            previous_system,
            optimisation.scenario,
            simulation_results,
            start_year,
            system_details,
        )

        sufficient_system_appraisals = get_sufficient_appraisals(
            optimisation, [system_appraisal]
        )

        # Throw off systens that don't meet the threshold criteria
        if len(sufficient_system_appraisals) == 0:
            try:
                return (
                    -1
                    / system_appraisal.criteria[
                        list(optimisation.optimisation_criteria.keys())[0]
                    ]
                )
            except TypeError:
                print("Invalid appraisl carried out, returning 0.")
                return 0

        # Determine the simulated system's criterion and return this value.
        optimum_systems = _fetch_optimum_system(
            optimisation, sufficient_system_appraisals
        )
        criterion_value = optimum_systems[optimisation_criterion].criteria[
            optimisation_criterion
        ]

        if (
            optimisation.optimisation_criteria[optimisation_criterion]
            == CriterionMode.MAXIMISE
        ):
            return criterion_value

        return 1 / criterion_value

    result = _simulation_run()

    return result if result is not None else 0


def multiple_optimisation_step(  # pylint: disable=too-many-locals, too-many-statements
    conventional_cw_source_profiles: dict[WaterSource, pd.DataFrame] | None,
    converters: dict[str, Converter],
    disable_tqdm: bool,
    finance_inputs: dict[str, Any],
    ghg_inputs: dict[str, Any],
    grid_profile: pd.DataFrame | None,
    irradiance_data: dict[str, pd.Series],
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    optimisation: Optimisation,
    optimisation_parameters: OptimisationParameters,
    temperature_data: dict[str, pd.Series],
    total_loads: dict[ResourceType, pd.DataFrame | None],
    total_solar_pv_power_produced: dict[str, pd.Series],
    wind_speed_data: pd.Series | None,
    yearly_electric_load_statistics: pd.DataFrame,
    *,
    input_converter_sizes: dict[Converter, ConverterSize] | None = None,
    input_cw_buffer_tanks: TankSize | None = None,
    input_cw_pvt_system_size: SolarSystemSize | None = None,
    input_cw_st_system_size: SolarSystemSize | None = None,
    input_cw_tanks: TankSize | None = None,
    input_hw_buffer_tanks: TankSize | None = None,
    input_hw_pvt_system_size: SolarSystemSize | None = None,
    input_hw_st_system_size: SolarSystemSize | None = None,
    input_hw_tanks: TankSize | None = None,
    input_pv_sizes: SolarSystemSize | None = None,
    input_storage_sizes: StorageSystemSize | None = None,
    optimisation_number: int | None = None,
    previous_system: SystemAppraisal | None = None,
    start_year: int = 0,
) -> tuple[datetime.timedelta, list[SystemAppraisal], list[SystemAppraisal]]:
    """
    Carries out multiple optimisation steps of the continuous lifetime optimisation.

    Inputs:
        - converters:
            The `list` of converters available to the system;
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
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
        - input_converter_sizes:
            Mapping between :class:`Converter` instances and the :class:`ConverterSize`
            range available.
        - input_cw_tanks:
            Range of clean-water tank sizes as a :class:`TankSize` instance;
        - input_cw_pvt_system_size:
            Range of clean-water PV-T sizes as a :class:`SolarSystemSize` instance;
        - input_cw_st_system_size:
            Range of clean-water solar-thermal sizes as a :class:`SolarSystemSize`
            instance;
        - input_hw_tanks:
            Range of hot-water tank sizes as a :class:`TankSize` instance;
        - input_hw_pvt_system_size:
            Range of hot-water PV-T sizes as a :class:`SolarSystemSize` instance;
        - input_hw_st_system_size:
            Range of hot-water solar-thermal sizes as a :class:`SolarSystemSize`
            instance;
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
            The results of each Optimisation().optimisation_step(...);
        - simulated_systems:
            The systems simulated along the way.

    """

    # Start timer to see how long simulation will take
    timer_start = datetime.datetime.now()
    logger.info("Multiple optimisation step process begun.")

    # Initialise
    results: list[SystemAppraisal] = []
    simulated_systems: list[SystemAppraisal] = []

    # set up the input converter sizes for the first loop.
    if (
        input_converter_sizes is None
        and len(converters) > 0
        and len(optimisation_parameters.converter_sizes) > 0
    ):
        logger.info(
            "No converter sizes passed in, using default optimisation parameters."
        )
        input_converter_sizes = optimisation_parameters.converter_sizes.copy()
    else:
        input_converter_sizes = {}

    # set up the clean-water PV-T sizes for the first loop.
    if (
        input_cw_pvt_system_size is None
        and optimisation.scenario.desalination_scenario is not None
        and minigrid.pvt_panel is not None
    ):
        if optimisation_parameters.cw_pvt_size is None:
            raise InternalError(
                f"{BColours.fail}Optimisation parameters do not have clean-water PV-T "
                + "params despite clean-water being specified in the scenario."
                + f"{BColours.endc}"
            )
        logger.info(
            "No clean-water PV-T sizes passed in, using default optimisation "
            "parameters."
        )
        input_cw_pvt_system_size = SolarSystemSize(
            optimisation_parameters.cw_pvt_size.max,
            optimisation_parameters.cw_pvt_size.min,
            optimisation_parameters.cw_pvt_size.step,
        )
    else:
        input_cw_pvt_system_size = SolarSystemSize()

    # Set up the clean-water solar-thermal sizes for the first loop.
    if (
        input_cw_st_system_size is None
        and optimisation.scenario.desalination_scenario is not None
        and minigrid.solar_thermal_panel is not None
    ):
        if optimisation_parameters.cw_st_size is None:
            raise InternalError(
                f"{BColours.fail}Optimisation parameters do not have clean-water "
                + "solar-thermal params despite hot-water being specified in the "
                + f"scenario.{BColours.endc}"
            )
        logger.info(
            "No clean-water solar-thermal sizes passed in, using default optimisation "
            "parameters."
        )
        input_cw_st_system_size = SolarSystemSize(
            optimisation_parameters.cw_st_size.max,
            optimisation_parameters.cw_st_size.min,
            optimisation_parameters.cw_st_size.step,
        )
    else:
        input_cw_st_system_size = SolarSystemSize()

    # Set up the clean-water tank sizes for the first loop.
    if (
        input_cw_tanks is None
        and optimisation.scenario.desalination_scenario is not None
        and minigrid.clean_water_tank is not None
    ):
        if optimisation_parameters.clean_water_tanks is None:
            raise InternalError(
                f"{BColours.fail}Optimisation parameters do not have clean-water tank "
                + "params despite clean-water being specified in the scenario."
                + f"{BColours.endc}"
            )
        logger.info(
            "No clean-water tank sizes passed in, using default optimisation parameters."
        )
        input_cw_tanks = TankSize(
            optimisation_parameters.clean_water_tanks.max,
            optimisation_parameters.clean_water_tanks.min,
            optimisation_parameters.clean_water_tanks.step,
        )
        if minigrid.pvt_panel is not None or minigrid.solar_thermal_panel is not None:
            input_cw_buffer_tanks = TankSize(
                optimisation_parameters.clean_water_buffer_tanks.max,
                optimisation_parameters.clean_water_buffer_tanks.min,
                optimisation_parameters.clean_water_buffer_tanks.step,
            )
        else:
            input_cw_buffer_tanks = TankSize()
    else:
        input_cw_tanks = TankSize()

    # set up the hot-water PV-T sizes for the first loop.
    if (
        input_hw_pvt_system_size is None
        and optimisation.scenario.hot_water_scenario is not None
        and minigrid.pvt_panel is not None
    ):
        if optimisation_parameters.hw_pvt_size is None:
            raise InternalError(
                f"{BColours.fail}Optimisation parameters do not have hot-water PV-T "
                + "params despite hot-water being specified in the scenario."
                + f"{BColours.endc}"
            )
        logger.info(
            "No hot-water PV-T sizes passed in, using default optimisation parameters."
        )
        input_hw_pvt_system_size = SolarSystemSize(
            optimisation_parameters.hw_pvt_size.max,
            optimisation_parameters.hw_pvt_size.min,
            optimisation_parameters.hw_pvt_size.step,
        )
        if minigrid.pvt_panel is not None or minigrid.solar_thermal_panel is not None:
            input_hw_buffer_tanks = TankSize(
                optimisation_parameters.hot_water_buffer_tanks.max,
                optimisation_parameters.hot_water_buffer_tanks.min,
                optimisation_parameters.hot_water_buffer_tanks.step,
            )
        else:
            input_hw_buffer_tanks = TankSize()
    else:
        input_hw_pvt_system_size = SolarSystemSize()

    # Set up the hot-water solar-thermal sizes for the first loop.
    if (
        input_hw_st_system_size is None
        and optimisation.scenario.hot_water_scenario is not None
        and minigrid.solar_thermal_panel is not None
    ):
        if optimisation_parameters.hw_st_size is None:
            raise InternalError(
                f"{BColours.fail}Optimisation parameters do not have hot-water "
                + "solar-thermal params despite hot-water being specified in the "
                + f"scenario.{BColours.endc}"
            )
        logger.info(
            "No hot-water solar-thermal sizes passed in, using default optimisation "
            "parameters."
        )
        input_hw_st_system_size = SolarSystemSize(
            optimisation_parameters.hw_st_size.max,
            optimisation_parameters.hw_st_size.min,
            optimisation_parameters.hw_st_size.step,
        )
    else:
        input_hw_st_system_size = SolarSystemSize()

    # Set up the hot-water tank sizes for the first loop
    if (
        input_hw_tanks is None
        and optimisation.scenario.hot_water_scenario is not None
        and minigrid.hot_water_tank is not None
    ):
        if optimisation_parameters.hot_water_tanks is None:
            raise InternalError(
                f"{BColours.fail}Optimisation parameters do not have hot-water tank "
                + "params despite hot-water being specified in the scenario."
                + f"{BColours.endc}"
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
        if optimisation.scenario.pv:
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
        if optimisation.scenario.battery:
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
    for iteration_number in tqdm(
        range(int(optimisation_parameters.number_of_iterations)),
        desc="optimisation steps",
        disable=disable_tqdm,
        leave=False,
        unit="step",
    ):
        logger.info("Beginning optimisation step.")

        from bayes_opt import BayesianOptimization

        # Setup the parameter bounds and include converter sizes.
        pbounds = optimisation_parameters.as_pbounds
        available_converters: list[Converter] = determine_available_converters(
            converters, logger, minigrid, optimisation.scenario
        )
        static_converter_sizes: dict[Converter, int] = {
            converter: available_converters.count(converter)
            for converter in available_converters
            if converter.name not in pbounds
        }

        # Remove unavailable converters
        unavailable_converters = [
            converter
            for converter in optimisation_parameters.converter_sizes
            if converter not in available_converters
        ]
        for unavailable_converter in unavailable_converters:
            pbounds.pop(unavailable_converter.name)

        criterion_to_optimiser_map: dict[Criterion, BayesianOptimization] = {}
        for optimisation_criterion in optimisation.optimisation_criteria:
            criterion_to_optimiser_map[optimisation_criterion] = (
                bayesian_optimiser := BayesianOptimization(
                    f=functools.partial(
                        _target_function,
                        available_converters=available_converters,
                        conventional_cw_source_profiles=conventional_cw_source_profiles,
                        disable_tqdm=disable_tqdm,
                        finance_inputs=finance_inputs,
                        ghg_inputs=ghg_inputs,
                        grid_profile=grid_profile,
                        irradiance_data=irradiance_data,
                        kerosene_usage=kerosene_usage,
                        location=location,
                        logger=logger,
                        minigrid=minigrid,
                        optimisation=optimisation,
                        optimisation_criterion=optimisation_criterion,
                        optimisation_parameters=optimisation_parameters,
                        previous_system=previous_system,
                        start_year=start_year,
                        static_converter_sizes=static_converter_sizes,
                        temperature_data=temperature_data,
                        total_loads=total_loads,
                        total_solar_pv_power_produced=total_solar_pv_power_produced,
                        wind_speed_data=wind_speed_data,
                        yearly_electric_load_statistics=yearly_electric_load_statistics,
                    ),
                    pbounds=pbounds,
                    verbose=2,
                    random_state=1,
                )
            )
            bayesian_optimiser.set_gp_params(alpha=1e-3, n_restarts_optimizer=5)
            bayesian_optimiser.maximize(
                # init_points=1,
                # n_iter=1,
                init_points=200,
                n_iter=1000,
            )

        bayesian_optimiser = criterion_to_optimiser_map[optimisation_criterion]

        bayesian_reg = pd.DataFrame(
            [
                {"target": entry["target"]} | entry["params"]
                for entry in bayesian_optimiser.res
            ]
        )
        bayesian_reg[optimisation_criterion.value] = 1 / bayesian_reg["target"]

        # Save the output of the optimisation step.
        bayesian_reg.to_csv()

        logger.info(
            "Optimisation step complete, optimum system determined: %s",
            bayesian_optimiser.max,
        )

        results.append(bayesian_reg)

        # Prepare inputs for next optimisation step
        start_year += optimisation_parameters.iteration_length
        # FIXME: Fix when using multiple iteration steps.
        # previous_system = optimum_system

    # End simulation timer
    timer_end = datetime.datetime.now()
    time_delta = timer_end - timer_start

    # Return the results along with the time taken and systems simulated along the way.
    return time_delta, results, simulated_systems
