#!/usr/bin/python3
########################################################################################
# single_line_simulation.py - Single-line simulation module for optimisation component.#
#                                                                                      #
# Authors: Phil Sandwell                                                               #
# Copyright: Phil Sandwell, 2018                                                       #
# Date created: 01/12/2021                                                             #
# License: Open source                                                                 #
# Most recent update: 01/12/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
single_line_simulation.py - The single-line simulation module for the optimisation comp.

As part of the process of carrying out an optimisation, it is necessary to run
simulations with increased bounds. I.E., should the optimum system for a run involve the
maximum allowed value for any of the parameters, then it may be that an increase in this
parameter will result in a better system.

"""

from logging import Logger
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np  # pylint: disable=import-error
import pandas as pd

from ..simulation import energy_system

from ..__utils__ import (
    BColours,
    Location,
    ProgrammerJudgementFault,
    RenewableEnergySource,
    ResourceType,
    Simulation,
    SystemAppraisal,
)
from ..conversion.conversion import Converter, WaterSource
from ..impact.__utils__ import ImpactingComponent  # pylint: disable=import-error

from .__utils__ import (
    ConverterSize,
    Optimisation,
    get_sufficient_appraisals,
    recursive_iteration,
    SolarSystemSize,
    StorageSystemSize,
    TankSize,
)
from .appraisal import appraise_system


__all__ = ("single_line_simulation",)


def single_line_simulation(  # pylint: disable=too-many-locals, too-many-statements
    conventional_cw_source_profiles: Optional[Dict[WaterSource, pd.DataFrame]],
    converter_sizes: Dict[Converter, ConverterSize],
    cw_pvt_size: SolarSystemSize,
    cw_tanks: TankSize,
    converters: Dict[str, Converter],
    disable_tqdm: bool,
    end_year: int,
    finance_inputs: Dict[str, Any],
    ghg_inputs: Dict[str, Any],
    grid_profile: Optional[pd.DataFrame],
    hw_pvt_size: SolarSystemSize,
    hw_tanks: TankSize,
    irradiance_data: pd.Series,
    kerosene_usage: pd.DataFrame,
    location: Location,
    logger: Logger,
    minigrid: energy_system.Minigrid,
    optimisation: Optimisation,
    potential_system: SystemAppraisal,
    previous_system: Optional[SystemAppraisal],
    pv_system_size: SolarSystemSize,
    start_year: int,
    storage_size: StorageSystemSize,
    temperature_data: pd.Series,
    total_loads: Dict[ResourceType, Optional[pd.DataFrame]],
    total_solar_pv_power_produced: pd.Series,
    wind_speed_data: Optional[pd.Series],
    yearly_electric_load_statistics: pd.DataFrame,
) -> Tuple[
    Dict[Converter, ConverterSize],
    SolarSystemSize,
    TankSize,
    SolarSystemSize,
    TankSize,
    SolarSystemSize,
    StorageSystemSize,
    List[SystemAppraisal],
]:
    """
    Preforms an additional round of simulations.

    If the potential optimum system was found to be an edge case (either maximum PV
    capacity, storage capacity etc.) then this function can be called to carry out
    additional simulation(s).

    Inputs:
        - converter_sizes:
            The largest size of each converter that was simulated.
        - cw_pvt_size:
            The largest clean-water PV-T size that was simulated.
        - cw_pvt_size:
            The largest clean-water tank size that was simulated.
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - hw_pvt_size:
            The largest hot-water PV-T size that was simulated.
        - hw_pvt_size:
            The largest hot-water tank size that was simulated.
        - pv_size:
            The largest pv size that was simulated.
        - storage_size:
            The largest storage size that was simulated.
        - potential_system:
            The system assumed to be the optimum, before this process
        - previous_system:
            The system that was previously installed

    Outputs:
        - cw_pvt_system_size:
            The clean-water PV-T size of the largest system considered.
        - cw_tanks:
            The clean-water tank size of the largest system considered.
        - hw_pvt_system_size:
            The hot-water PV-T size of the largest system considered.
        - hw_tanks:
            The hot-water tank size of the largest system considered.
        - pv_system_size:
            The pv system size of the largest system considered.
        - storage_size:
            The storage size of the largest system considered.
        - system_appraisals:
            The set of system appraisals considered.

    """

    # Instantiate
    logger.info("Single-line optimisation to be carried out.")
    sufficient_appraisals: List[SystemAppraisal] = []
    system_appraisals: List[SystemAppraisal] = []

    _converter_name_to_converter_mapping = {
        converter.name: converter for converter in converter_sizes
    }
    if potential_system.system_details.initial_converter_sizes is None:
        logger.error(
            "%sInitial converter sizes undefined when calling single-line simulation. "
            "%s",
            BColours.fail,
            BColours.endc,
        )
        raise ProgrammerJudgementFault(
            "single line simulation",
            "Misuse of single-line-simulation function: initial converter sizes must "
            "be defined.",
        )
    potential_converter_sizes = {
        _converter_name_to_converter_mapping[name]: value
        for name, value in potential_system.system_details.initial_converter_sizes.items()
    }
    potential_cw_pvt_size = (
        potential_system.system_details.initial_cw_pvt_size
        if potential_system.system_details.initial_cw_pvt_size is not None
        else 0
    )
    potential_hw_pvt_size = (
        potential_system.system_details.initial_hw_pvt_size
        if potential_system.system_details.initial_hw_pvt_size is not None
        else 0
    )
    potential_num_clean_water_tanks = (
        potential_system.system_details.initial_num_clean_water_tanks
        if potential_system.system_details.initial_num_clean_water_tanks is not None
        else 0
    )
    potential_num_hot_water_tanks = (
        potential_system.system_details.initial_num_hot_water_tanks
        if potential_system.system_details.initial_num_hot_water_tanks is not None
        else 0
    )

    # Determine the static converters based on those that were modelled but were not
    # passed in as part of the maximum system size parameters.
    static_converter_sizes: Dict[Converter, int] = {
        converter: potential_converter_sizes[converter]
        for converter in potential_converter_sizes
        if converter not in converter_sizes
    }

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

        # Increase and iterate over the various power-generation sizes.
        increased_cw_pvt_system_sizes = sorted(
            range(
                int(cw_pvt_size.min),
                int(np.ceil(cw_pvt_size.max + cw_pvt_size.step)),
                int(cw_pvt_size.step),
            ),
            reverse=True,
        )
        increased_hw_pvt_system_sizes = sorted(
            range(
                int(hw_pvt_size.min),
                int(np.ceil(hw_pvt_size.max + hw_pvt_size.step)),
                int(hw_pvt_size.step),
            ),
            reverse=True,
        )
        increased_pv_system_sizes: List[int] = sorted(
            np.arange(
                pv_system_size.min,
                np.ceil(pv_system_size.max + pv_system_size.step),
                pv_system_size.step,
            ),
            reverse=True,
        )

        # Prep variables for the iteration process.
        component_sizes: Dict[
            Union[Converter, ImpactingComponent, RenewableEnergySource],
            Union[int, float],
        ] = {
            ImpactingComponent.CLEAN_WATER_TANK: potential_num_clean_water_tanks,
            ImpactingComponent.HOT_WATER_TANK: potential_num_hot_water_tanks,
            ImpactingComponent.STORAGE: storage_size.max + storage_size.step,
        }
        parameter_space: List[
            Tuple[
                Union[Converter, ImpactingComponent, RenewableEnergySource],
                str,
                Union[List[int], List[float]],
            ]
        ] = []

        # Add the iterable converter sizes.
        for converter, sizes in converter_sizes.items():
            # Construct the list of available sizes for the given converter.
            simulation_converter_sizes: List[int] = sorted(
                range(
                    int(sizes.min),
                    int(np.ceil(sizes.max + sizes.step)),
                    int(sizes.step),
                ),
                reverse=True,
            )

            if len(simulation_converter_sizes) > 1:
                parameter_space.append(
                    (
                        converter,
                        "simulation"
                        if len(parameter_space) == 0
                        else f"{converter.name} size",
                        simulation_converter_sizes,
                    )
                )
            else:
                component_sizes[converter] = simulation_converter_sizes[0]

        # Add the static converter sizes.
        for converter, size in static_converter_sizes.items():
            component_sizes[converter] = size

        if len(increased_cw_pvt_system_sizes) <= 1:
            component_sizes[
                RenewableEnergySource.CLEAN_WATER_PVT
            ] = potential_cw_pvt_size
        else:
            parameter_space.append(
                (
                    RenewableEnergySource.CLEAN_WATER_PVT,
                    "simulation",
                    increased_cw_pvt_system_sizes,
                )
            )
        if len(increased_hw_pvt_system_sizes) <= 1:
            component_sizes[RenewableEnergySource.HOT_WATER_PVT] = potential_hw_pvt_size
        else:
            parameter_space.append(
                (
                    RenewableEnergySource.HOT_WATER_PVT,
                    "simulation" if len(parameter_space) <= 1 else "hw pv-t size",
                    increased_hw_pvt_system_sizes,
                )
            )
        if len(increased_pv_system_sizes) <= 1:
            component_sizes[
                RenewableEnergySource.PV
            ] = potential_system.system_details.initial_pv_size
        else:
            parameter_space.append(
                (
                    RenewableEnergySource.PV,
                    "simulation" if len(parameter_space) <= 1 else "pv size",
                    increased_pv_system_sizes,
                )
            )

        system_appraisals.extend(
            recursive_iteration(
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
        )

        # If the maximum PV system size isn't a round number of steps, carry out a
        # simulation at this size.
        if (
            np.ceil(pv_system_size.max / pv_system_size.step) * pv_system_size.step
            != pv_system_size.max
        ):
            _, simulation_results, system_details = energy_system.run_simulation(
                int(potential_cw_pvt_size),
                conventional_cw_source_profiles,
                converters,
                disable_tqdm,
                test_storage_size,
                grid_profile,
                int(potential_hw_pvt_size),
                irradiance_data,
                kerosene_usage,
                location,
                logger,
                minigrid,
                potential_num_clean_water_tanks,
                potential_num_hot_water_tanks,
                total_solar_pv_power_produced,
                pv_system_size.max,
                optimisation.scenario,
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
                optimisation.scenario,
                simulation_results,
                start_year,
                system_details,
            )

            if get_sufficient_appraisals(optimisation, [new_appraisal]):
                sufficient_appraisals.append(new_appraisal)

        # Update the system details.
        storage_size.max = test_storage_size

    # If the number of clean-water tanks was maxed out:
    if (
        potential_num_clean_water_tanks == cw_tanks.max
        and optimisation.scenario.desalination_scenario is not None
    ):
        logger.info("Increasing number of clean-water tanks.")

        # Increase and iterate over the various clean-water generation sizes.
        increased_cw_pvt_system_sizes = sorted(
            range(
                int(cw_pvt_size.min),
                int(np.ceil(cw_pvt_size.max + cw_pvt_size.step)),
                int(cw_pvt_size.step),
            ),
            reverse=True,
        )
        increased_pv_system_sizes = sorted(
            np.arange(
                pv_system_size.min,
                np.ceil(pv_system_size.max + pv_system_size.step),
                pv_system_size.step,
            ),
            reverse=True,
        )
        increased_storage_sizes = sorted(
            np.arange(
                storage_size.min,
                np.ceil(storage_size.max + storage_size.step),
                storage_size.step,
            ),
            reverse=True,
        )

        # Prep variables for the iteration process.
        component_sizes = {
            ImpactingComponent.CLEAN_WATER_TANK: int(cw_tanks.max + cw_tanks.step),
            RenewableEnergySource.HOT_WATER_PVT: potential_hw_pvt_size,
            ImpactingComponent.HOT_WATER_TANK: potential_num_hot_water_tanks,
        }
        parameter_space = []

        # Add the iterable converter sizes.
        for converter, sizes in converter_sizes.items():
            # Construct the list of available sizes for the given converter.
            simulation_converter_sizes = sorted(
                range(
                    int(sizes.min),
                    int(np.ceil(sizes.max + sizes.step)),
                    int(sizes.step),
                ),
                reverse=True,
            )

            if len(simulation_converter_sizes) > 1:
                parameter_space.append(
                    (
                        converter,
                        "simulation"
                        if len(parameter_space) == 0
                        else f"{converter.name} size",
                        simulation_converter_sizes,
                    )
                )
            else:
                component_sizes[converter] = simulation_converter_sizes[0]

        # Add the static converter sizes.
        for converter, size in static_converter_sizes.items():
            component_sizes[converter] = size

        if len(increased_cw_pvt_system_sizes) <= 1:
            component_sizes[
                RenewableEnergySource.CLEAN_WATER_PVT
            ] = potential_cw_pvt_size
        else:
            parameter_space.append(
                (
                    RenewableEnergySource.CLEAN_WATER_PVT,
                    "simulation",
                    increased_cw_pvt_system_sizes,
                )
            )
        if len(increased_pv_system_sizes) <= 1:
            component_sizes[
                RenewableEnergySource.PV
            ] = potential_system.system_details.initial_pv_size
        else:
            parameter_space.append(
                (
                    RenewableEnergySource.PV,
                    "simulation" if len(parameter_space) <= 1 else "pv size",
                    increased_pv_system_sizes,
                )
            )
        if len(increased_storage_sizes) <= 1:
            component_sizes[
                ImpactingComponent.STORAGE
            ] = potential_system.system_details.initial_storage_size
        else:
            parameter_space.append(
                (
                    ImpactingComponent.STORAGE,
                    "simulation" if len(parameter_space) <= 1 else "storage size",
                    increased_storage_sizes,
                )
            )

        system_appraisals.extend(
            recursive_iteration(
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
        )

    # If the number of hot-water tanks was maxed out:
    if (
        potential_num_hot_water_tanks == hw_tanks.max
        and optimisation.scenario.hot_water_scenario is not None
    ):
        logger.info("Increasing number of hot-water tanks.")

        # Increase and iterate over the various hot-water generation sizes.
        increased_hw_pvt_system_sizes = sorted(
            range(
                int(hw_pvt_size.min),
                int(np.ceil(hw_pvt_size.max + hw_pvt_size.step)),
                int(hw_pvt_size.step),
            ),
            reverse=True,
        )
        increased_pv_system_sizes = sorted(
            np.arange(
                pv_system_size.min,
                np.ceil(pv_system_size.max + pv_system_size.step),
                pv_system_size.step,
            ),
            reverse=True,
        )
        increased_storage_sizes = sorted(
            np.arange(
                storage_size.min,
                np.ceil(storage_size.max + storage_size.step),
                storage_size.step,
            ),
            reverse=True,
        )

        # Prep variables for the iteration process.
        component_sizes = {
            RenewableEnergySource.CLEAN_WATER_PVT: potential_cw_pvt_size,
            ImpactingComponent.CLEAN_WATER_TANK: int(cw_tanks.max + cw_tanks.step),
            ImpactingComponent.HOT_WATER_TANK: potential_num_hot_water_tanks,
        }
        parameter_space = []

        # Add the iterable converter sizes.
        for converter, sizes in converter_sizes.items():
            # Construct the list of available sizes for the given converter.
            simulation_converter_sizes = sorted(
                range(
                    int(sizes.min),
                    int(np.ceil(sizes.max + sizes.step)),
                    int(sizes.step),
                ),
                reverse=True,
            )

            if len(simulation_converter_sizes) > 1:
                parameter_space.append(
                    (
                        converter,
                        "simulation"
                        if len(parameter_space) == 0
                        else f"{converter.name} size",
                        simulation_converter_sizes,
                    )
                )
            else:
                component_sizes[converter] = simulation_converter_sizes[0]

        # Add the static converter sizes.
        for converter, size in static_converter_sizes.items():
            component_sizes[converter] = size

        if len(increased_hw_pvt_system_sizes) <= 1:
            component_sizes[RenewableEnergySource.HOT_WATER_PVT] = potential_hw_pvt_size
        else:
            parameter_space.append(
                (
                    RenewableEnergySource.HOT_WATER_PVT,
                    "simulation",
                    increased_hw_pvt_system_sizes,
                )
            )
        if len(increased_pv_system_sizes) <= 1:
            component_sizes[
                RenewableEnergySource.PV
            ] = potential_system.system_details.initial_pv_size
        else:
            parameter_space.append(
                (
                    RenewableEnergySource.PV,
                    "simulation" if len(parameter_space) <= 1 else "pv size",
                    increased_pv_system_sizes,
                )
            )
        if len(increased_storage_sizes) <= 1:
            component_sizes[
                ImpactingComponent.STORAGE
            ] = potential_system.system_details.initial_storage_size
        else:
            parameter_space.append(
                (
                    ImpactingComponent.STORAGE,
                    "simulation" if len(parameter_space) <= 1 else "storage size",
                    increased_storage_sizes,
                )
            )

        system_appraisals.extend(
            recursive_iteration(
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
        )

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
    if potential_system.system_details.initial_pv_size == pv_system_size.max:
        logger.info("Increasing PV size.")

        # Increase and iterate over the various storage sizes and PV-T sizes.
        increased_cw_pvt_system_sizes = sorted(
            range(
                int(cw_pvt_size.min),
                int(np.ceil(cw_pvt_size.max + cw_pvt_size.step)),
                int(cw_pvt_size.step),
            ),
            reverse=True,
        )
        increased_cw_tank_sizes = sorted(
            range(
                int(cw_tanks.min),
                int(np.ceil(cw_tanks.max + cw_tanks.step)),
                int(cw_tanks.step),
            ),
            reverse=True,
        )
        increased_hw_pvt_system_sizes = sorted(
            range(
                int(hw_pvt_size.min),
                int(np.ceil(hw_pvt_size.max + hw_pvt_size.step)),
                int(hw_pvt_size.step),
            ),
            reverse=True,
        )
        increased_hw_tank_sizes = sorted(
            range(
                int(hw_tanks.min),
                int(np.ceil(hw_tanks.max + hw_tanks.step)),
                int(hw_tanks.step),
            ),
            reverse=True,
        )
        increased_storage_sizes = sorted(
            np.arange(
                storage_size.min,
                np.ceil(storage_size.max + storage_size.step),
                storage_size.step,
            ),
            reverse=True,
        )

        # Prep variables for the iteration process.
        component_sizes = {
            RenewableEnergySource.PV: pv_system_size.max + pv_system_size.step,
        }
        parameter_space = []

        # Add the iterable converter sizes.
        for converter, sizes in converter_sizes.items():
            # Construct the list of available sizes for the given converter.
            simulation_converter_sizes = sorted(
                range(
                    int(sizes.min),
                    int(np.ceil(sizes.max + sizes.step)),
                    int(sizes.step),
                ),
                reverse=True,
            )

            if len(simulation_converter_sizes) > 1:
                parameter_space.append(
                    (
                        converter,
                        "simulation"
                        if len(parameter_space) == 0
                        else f"{converter.name} size",
                        simulation_converter_sizes,
                    )
                )
            else:
                component_sizes[converter] = simulation_converter_sizes[0]

        # Add the static converter sizes.
        for converter, size in static_converter_sizes.items():
            component_sizes[converter] = size

        if len(increased_cw_pvt_system_sizes) <= 1:
            component_sizes[
                RenewableEnergySource.CLEAN_WATER_PVT
            ] = potential_cw_pvt_size
        else:
            parameter_space.append(
                (
                    RenewableEnergySource.CLEAN_WATER_PVT,
                    "simulation",
                    increased_cw_pvt_system_sizes,
                )
            )
        if len(increased_cw_tank_sizes) <= 1:
            component_sizes[
                ImpactingComponent.CLEAN_WATER_TANK
            ] = potential_num_clean_water_tanks
        else:
            parameter_space.append(
                (
                    ImpactingComponent.CLEAN_WATER_TANK,
                    "simulation" if len(parameter_space) <= 1 else "cw tanks",
                    increased_cw_tank_sizes,
                )
            )
        if len(increased_hw_pvt_system_sizes) <= 1:
            component_sizes[RenewableEnergySource.HOT_WATER_PVT] = potential_hw_pvt_size
        else:
            parameter_space.append(
                (
                    RenewableEnergySource.HOT_WATER_PVT,
                    "simulation" if len(parameter_space) <= 1 else "hw pv-t size",
                    increased_hw_pvt_system_sizes,
                )
            )
        if len(increased_hw_tank_sizes) <= 1:
            component_sizes[
                ImpactingComponent.HOT_WATER_TANK
            ] = potential_num_hot_water_tanks
        else:
            parameter_space.append(
                (
                    ImpactingComponent.HOT_WATER_TANK,
                    "simulation" if len(parameter_space) <= 1 else "hw tanks",
                    increased_hw_tank_sizes,
                )
            )
        if len(increased_storage_sizes) <= 1:
            component_sizes[
                ImpactingComponent.STORAGE
            ] = potential_system.system_details.initial_storage_size
        else:
            parameter_space.append(
                (
                    ImpactingComponent.STORAGE,
                    "simulation" if len(parameter_space) <= 1 else "storage size",
                    increased_storage_sizes,
                )
            )

        system_appraisals.extend(
            recursive_iteration(
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
        )

        pv_system_size.max = test_pv_size

    # Check to see if clean-water PV-T size was an integer number of steps, and increase
    # accordingly
    if (
        np.ceil(cw_pvt_size.max / cw_pvt_size.step) * cw_pvt_size.step
        == cw_pvt_size.max
    ):
        test_cw_pvt_size = float(cw_pvt_size.max + cw_pvt_size.step)
    else:
        test_cw_pvt_size = float(
            np.ceil(cw_pvt_size.max / cw_pvt_size.step) * cw_pvt_size.step
        )

    # If clean-water PV-T was maxed out:
    if (
        potential_cw_pvt_size == cw_pvt_size.max
        and optimisation.scenario.desalination_scenario
    ):
        logger.info("Increasing clean-water PV size.")

        # Increase and iterate over the various storage sizes and other PV-T sizes.
        increased_cw_tank_sizes = sorted(
            range(
                int(cw_tanks.min),
                int(np.ceil(cw_tanks.max + cw_tanks.step)),
                int(cw_tanks.step),
            ),
            reverse=True,
        )
        increased_hw_pvt_system_sizes = sorted(
            range(
                int(hw_pvt_size.min),
                int(np.ceil(hw_pvt_size.max + hw_pvt_size.step)),
                int(hw_pvt_size.step),
            ),
            reverse=True,
        )
        increased_hw_tank_sizes = sorted(
            range(
                int(hw_tanks.min),
                int(np.ceil(hw_tanks.max + hw_tanks.step)),
                int(hw_tanks.step),
            ),
            reverse=True,
        )
        increased_pv_system_sizes = sorted(
            np.arange(
                pv_system_size.min,
                np.ceil(pv_system_size.max + pv_system_size.step),
                pv_system_size.step,
            ),
            reverse=True,
        )
        increased_storage_sizes = sorted(
            np.arange(
                storage_size.min,
                np.ceil(storage_size.max + storage_size.step),
                storage_size.step,
            ),
            reverse=True,
        )

        # Prep variables for the iteration process.
        component_sizes = {
            RenewableEnergySource.CLEAN_WATER_PVT: int(
                test_cw_pvt_size + cw_pvt_size.step
            )
        }
        parameter_space = []

        # Add the iterable converter sizes.
        for converter, sizes in converter_sizes.items():
            # Construct the list of available sizes for the given converter.
            simulation_converter_sizes = sorted(
                range(
                    int(sizes.min),
                    int(np.ceil(sizes.max + sizes.step)),
                    int(sizes.step),
                ),
                reverse=True,
            )

            if len(simulation_converter_sizes) > 1:
                parameter_space.append(
                    (
                        converter,
                        "simulation"
                        if len(parameter_space) == 0
                        else f"{converter.name} size",
                        simulation_converter_sizes,
                    )
                )
            else:
                component_sizes[converter] = simulation_converter_sizes[0]

        # Add the static converter sizes.
        for converter, size in static_converter_sizes.items():
            component_sizes[converter] = size

        if len(increased_cw_tank_sizes) <= 1:
            component_sizes[
                ImpactingComponent.CLEAN_WATER_TANK
            ] = potential_num_clean_water_tanks
        else:
            parameter_space.append(
                (
                    ImpactingComponent.CLEAN_WATER_TANK,
                    "simulation",
                    increased_cw_tank_sizes,
                )
            )
        if len(increased_hw_pvt_system_sizes) <= 1:
            component_sizes[RenewableEnergySource.HOT_WATER_PVT] = potential_hw_pvt_size
        else:
            parameter_space.append(
                (
                    RenewableEnergySource.HOT_WATER_PVT,
                    "simulation" if len(parameter_space) <= 1 else "hw pv-t size",
                    increased_hw_pvt_system_sizes,
                )
            )
        if len(increased_hw_tank_sizes) <= 1:
            component_sizes[
                ImpactingComponent.HOT_WATER_TANK
            ] = potential_num_hot_water_tanks
        else:
            parameter_space.append(
                (
                    ImpactingComponent.HOT_WATER_TANK,
                    "simulation" if len(parameter_space) <= 1 else "hw tanks",
                    increased_hw_tank_sizes,
                )
            )
        if len(increased_storage_sizes) <= 1:
            component_sizes[
                ImpactingComponent.STORAGE
            ] = potential_system.system_details.initial_storage_size
        else:
            parameter_space.append(
                (
                    ImpactingComponent.STORAGE,
                    "simulation" if len(parameter_space) <= 1 else "storage size",
                    increased_storage_sizes,
                )
            )
        if len(increased_pv_system_sizes) <= 1:
            component_sizes[
                RenewableEnergySource.PV
            ] = potential_system.system_details.initial_pv_size
        else:
            parameter_space.append(
                (
                    RenewableEnergySource.PV,
                    "simulation" if len(parameter_space) <= 1 else "pv size",
                    increased_pv_system_sizes,
                )
            )

        system_appraisals.extend(
            recursive_iteration(
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
        )

        cw_pvt_size.max = test_cw_pvt_size

    # Check to see if hot-water PV-T size was an integer number of steps, and increase
    # accordingly
    if (
        np.ceil(hw_pvt_size.max / hw_pvt_size.step) * hw_pvt_size.step
        == hw_pvt_size.max
    ):
        test_hw_pvt_size = float(hw_pvt_size.max + hw_pvt_size.step)
    else:
        test_hw_pvt_size = float(
            np.ceil(hw_pvt_size.max / hw_pvt_size.step) * hw_pvt_size.step
        )

    # If hot-water PV-T was maxed out:
    if (
        potential_hw_pvt_size == hw_pvt_size.max
        and optimisation.scenario.hot_water_scenario
    ):
        logger.info("Increasing hot-water PV size.")

        # Increase and iterate over the various storage sizes and other PV-T sizes.
        increased_cw_pvt_system_sizes = sorted(
            range(
                int(cw_pvt_size.min),
                int(np.ceil(cw_pvt_size.max + cw_pvt_size.step)),
                int(cw_pvt_size.step),
            ),
            reverse=True,
        )
        increased_cw_tank_sizes = sorted(
            range(
                int(cw_tanks.min),
                int(np.ceil(cw_tanks.max + cw_tanks.step)),
                int(cw_tanks.step),
            ),
            reverse=True,
        )
        increased_hw_tank_sizes = sorted(
            range(
                int(hw_tanks.min),
                int(np.ceil(hw_tanks.max + hw_tanks.step)),
                int(hw_tanks.step),
            ),
            reverse=True,
        )
        increased_pv_system_sizes = sorted(
            np.arange(
                pv_system_size.min,
                np.ceil(pv_system_size.max + pv_system_size.step),
                pv_system_size.step,
            ),
            reverse=True,
        )
        increased_storage_sizes = sorted(
            np.arange(
                storage_size.min,
                np.ceil(storage_size.max + storage_size.step),
                storage_size.step,
            ),
            reverse=True,
        )

        # Prep variables for the iteration process.
        component_sizes = {
            RenewableEnergySource.HOT_WATER_PVT: int(
                test_hw_pvt_size + hw_pvt_size.step
            )
        }
        parameter_space = []

        # Add the iterable converter sizes.
        for converter, sizes in converter_sizes.items():
            # Construct the list of available sizes for the given converter.
            simulation_converter_sizes = sorted(
                range(
                    int(sizes.min),
                    int(np.ceil(sizes.max + sizes.step)),
                    int(sizes.step),
                ),
                reverse=True,
            )

            if len(simulation_converter_sizes) > 1:
                parameter_space.append(
                    (
                        converter,
                        "simulation"
                        if len(parameter_space) == 0
                        else f"{converter.name} size",
                        simulation_converter_sizes,
                    )
                )
            else:
                component_sizes[converter] = simulation_converter_sizes[0]

        # Add the static converter sizes.
        for converter, size in static_converter_sizes.items():
            component_sizes[converter] = size

        if len(increased_cw_pvt_system_sizes) <= 1:
            component_sizes[
                RenewableEnergySource.CLEAN_WATER_PVT
            ] = potential_cw_pvt_size
        else:
            parameter_space.append(
                (
                    RenewableEnergySource.CLEAN_WATER_PVT,
                    "simulation",
                    increased_cw_pvt_system_sizes,
                )
            )
        if len(increased_cw_tank_sizes) <= 1:
            component_sizes[
                ImpactingComponent.CLEAN_WATER_TANK
            ] = potential_num_clean_water_tanks
        else:
            parameter_space.append(
                (
                    ImpactingComponent.CLEAN_WATER_TANK,
                    "simulation",
                    increased_cw_tank_sizes,
                )
            )
        if len(increased_hw_tank_sizes) <= 1:
            component_sizes[
                ImpactingComponent.HOT_WATER_TANK
            ] = potential_num_hot_water_tanks
        else:
            parameter_space.append(
                (
                    ImpactingComponent.HOT_WATER_TANK,
                    "simulation" if len(parameter_space) <= 1 else "hw tanks",
                    increased_hw_tank_sizes,
                )
            )
        if len(increased_storage_sizes) <= 1:
            component_sizes[
                ImpactingComponent.STORAGE
            ] = potential_system.system_details.initial_storage_size
        else:
            parameter_space.append(
                (
                    ImpactingComponent.STORAGE,
                    "simulation" if len(parameter_space) <= 1 else "storage size",
                    increased_storage_sizes,
                )
            )
        if len(increased_pv_system_sizes) <= 1:
            component_sizes[
                RenewableEnergySource.PV
            ] = potential_system.system_details.initial_pv_size
        else:
            parameter_space.append(
                (
                    RenewableEnergySource.PV,
                    "simulation" if len(parameter_space) <= 1 else "pv size",
                    increased_pv_system_sizes,
                )
            )

        system_appraisals.extend(
            recursive_iteration(
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
        )

        hw_pvt_size.max = test_hw_pvt_size

    sufficient_appraisals.extend(
        get_sufficient_appraisals(optimisation, system_appraisals)
    )

    return (
        converter_sizes,
        cw_pvt_size,
        cw_tanks,
        hw_pvt_size,
        hw_tanks,
        pv_system_size,
        storage_size,
        sufficient_appraisals,
    )
