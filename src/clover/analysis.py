#!/usr/bin/python3
# type: ignore
########################################################################################
# analysis.py - In-built analysis module for CLOVER.                                   #
#                                                                                      #
# Authors: Phil Sandwell, Ben Winchester                                               #
# Copyright: Phil Sandwell, 2021                                                       #
# Date created: 13/07/2021                                                             #
# License: Open source                                                                 #
########################################################################################
"""
analysis.py - The analysis module for CLOVER.

In order to best check and validate the results produced by CLOVER simulations and
optimisations, an in-built analysis module is provied which generates plots and figures
corresponding to the sugetsed analysis within the user guide.

"""

import os

from typing import Dict, Optional

import numpy as np  # pylint: disable=import-error
import pandas as pd  # pylint: disable=import-error
import seaborn as sns  # pylint: disable=import-error

import matplotlib.pyplot as plt  # pylint: disable=import-error
from tqdm import tqdm  # pylint: disable=import-error

from .__utils__ import (
    ColumnHeader,
    CUT_OFF_TIME,
    DemandType,
    HOURS_PER_YEAR,
    KeyResults,
    ResourceType,
)

__all__ = (
    "get_key_results",
    "plot_outputs",
)


# Colour map:
#   The preferred sns colourmap to use.
COLOUR_MAP: str = "Blues"

# Hours until July:
#   The number of hours until March.
HOURS_UNTIL_JULY: int = 4344

# Hours until March:
#   The number of hours until March.
HOURS_UNTIL_MARCH: int = 1416

# Hours until May:
#   The number of hours until May.
HOURS_UNTIL_MAY: int = 2880

# Plot resolution:
#   The resolution, in dpi, to use for plotting figures.
PLOT_RESOLUTION: int = 600

# Simulation plots directory:
#   The directory in which simulation plots should be saved.
SIMULATION_PLOTS_DIRECTORY: str = "simulation_{simulation_number}_plots"


def get_key_results(
    grid_input_profile: pd.DataFrame,
    num_years: int,
    simulation_results: pd.DataFrame,
    total_solar_output: pd.DataFrame,
) -> KeyResults:
    """
    Computes the key results of the simulation.

        Inputs:
        - grid_input_profile:
            The relevant grid input profile for the simulation that was run.
        - num_years:
            The number of years for which the simulation was run.
        - simulation_results:
            The results of the simulation.
        - total_solar_output:
            The total solar power produced by the PV installation.

    Outputs:
        - key_results:
            The key results of the simulation, wrapped in a :class:`KeyResults`
            instance.

    """

    key_results = KeyResults()

    # Compute the solar-generation results.
    total_solar_generation: float = np.round(np.sum(total_solar_output))
    key_results.cumulative_pv_generation = float(total_solar_generation)
    key_results.average_pv_generation = float(
        round(total_solar_generation / (20 * 365))
    )

    # Compute the grid results.
    if grid_input_profile is not None:
        key_results.grid_daily_hours = np.sum(
            grid_input_profile[: num_years * HOURS_PER_YEAR], axis=0
        ) / (365 * num_years)

    # Compute the simulation related averages and sums.
    key_results.average_daily_diesel_energy_supplied = simulation_results[
        ColumnHeader.DIESEL_ENERGY_SUPPLIED.value
    ].sum() / (365 * num_years)

    key_results.average_daily_dumped_energy = simulation_results[
        ColumnHeader.DUMPED_ELECTRICITY.value
    ].sum() / (365 * num_years)

    key_results.average_daily_energy_consumption = simulation_results[
        ColumnHeader.TOTAL_ELECTRICITY_CONSUMED.value
    ].sum() / (365 * num_years)

    key_results.average_daily_grid_energy_supplied = simulation_results[
        ColumnHeader.GRID_ENERGY.value
    ].sum() / (365 * num_years)

    key_results.average_daily_renewables_energy_supplied = simulation_results[
        ColumnHeader.RENEWABLE_ELECTRICITY_SUPPLIED.value
    ].sum() / (365 * num_years)

    key_results.average_daily_renewables_energy_used = simulation_results[
        ColumnHeader.RENEWABLE_ELECTRICITY_USED_DIRECTLY.value
    ].sum() / (365 * num_years)

    key_results.average_daily_stored_energy_supplied = simulation_results[
        ColumnHeader.ELECTRICITY_FROM_STORAGE.value
    ].sum() / (365 * num_years)

    key_results.average_daily_unmet_energy = simulation_results[
        ColumnHeader.UNMET_ELECTRICITY.value
    ].sum() / (365 * num_years)

    key_results.diesel_times = round(
        np.mean(simulation_results[ColumnHeader.DIESEL_GENERATOR_TIMES.value]), 3
    )
    key_results.blackouts = round(
        np.mean(simulation_results[ColumnHeader.BLACKOUTS.value]), 3
    )

    # Compute the clean-water key results.
    if ColumnHeader.TOTAL_CW_LOAD.value in simulation_results:
        key_results.average_daily_cw_demand_covered = round(
            simulation_results[ColumnHeader.TOTAL_CW_SUPPLIED.value].sum()
            / simulation_results[ColumnHeader.TOTAL_CW_LOAD.value].sum(),
            3,
        )
        key_results.average_daily_cw_supplied = round(
            simulation_results[ColumnHeader.TOTAL_CW_SUPPLIED.value].sum()
            / (365 * num_years),
            3,
        )
        key_results.clean_water_blackouts = round(
            np.mean(simulation_results[ColumnHeader.CLEAN_WATER_BLACKOUTS.value]), 3
        )
        key_results.cumulative_cw_load = round(
            simulation_results[ColumnHeader.TOTAL_CW_LOAD.value].sum(), 3
        )
        key_results.cumulative_cw_supplied = round(
            simulation_results[ColumnHeader.TOTAL_CW_SUPPLIED.value].sum(), 3
        )

    # Compute the clean-water PV-T key results.
    if ColumnHeader.CW_PVT_ELECTRICITY_SUPPLIED_PER_KWP.value in simulation_results:
        key_results.average_daily_cw_pvt_generation = round(
            simulation_results[
                ColumnHeader.CW_PVT_ELECTRICITY_SUPPLIED_PER_KWP.value
            ].sum()
            / (365 * num_years),
            3,
        )
        key_results.cumulative_cw_pvt_generation = round(
            simulation_results[
                ColumnHeader.CW_PVT_ELECTRICITY_SUPPLIED_PER_KWP.value
            ].sum(),
            3,
        )
        key_results.max_buffer_tank_temperature = round(
            max(simulation_results[ColumnHeader.BUFFER_TANK_TEMPERATURE.value]), 3
        )
        key_results.max_cw_pvt_output_temperature = round(
            max(simulation_results[ColumnHeader.CW_PVT_OUTPUT_TEMPERATURE.value]), 3
        )
        key_results.mean_buffer_tank_temperature = round(
            np.mean(simulation_results[ColumnHeader.BUFFER_TANK_TEMPERATURE.value]),
            3,
        )
        key_results.mean_cw_pvt_output_temperature = round(
            np.mean(simulation_results[ColumnHeader.CW_PVT_OUTPUT_TEMPERATURE.value]), 3
        )
        key_results.min_buffer_tank_temperature = round(
            min(simulation_results[ColumnHeader.BUFFER_TANK_TEMPERATURE.value]), 3
        )
        key_results.min_cw_pvt_output_temperature = round(
            min(simulation_results[ColumnHeader.CW_PVT_OUTPUT_TEMPERATURE.value]), 3
        )

    # Compute the hot-water key results.
    if ColumnHeader.TOTAL_HW_LOAD.value in simulation_results:
        key_results.average_daily_hw_demand_covered = round(
            np.mean(simulation_results[ColumnHeader.HW_RENEWABLES_FRACTION.value]), 3
        )
        key_results.average_daily_hw_pvt_generation = round(
            simulation_results[
                ColumnHeader.HW_PVT_ELECTRICITY_SUPPLIED_PER_KWP.value
            ].sum()
            / (365 * num_years),
            3,
        )
        key_results.average_daily_hw_supplied = round(
            simulation_results[ColumnHeader.HW_TANK_OUTPUT.value].sum()
            / (365 * num_years),
            3,
        )

    return key_results


def plot_outputs(  # pylint: disable=too-many-locals, too-many-statements
    grid_input_profile: pd.DataFrame,
    grid_profile: Optional[pd.DataFrame],
    initial_cw_hourly_loads: Optional[  # pylint: disable=unused-argument
        Dict[str, pd.DataFrame]
    ],
    initial_electric_hourly_loads: Dict[str, pd.DataFrame],
    initial_hw_hourly_loads: Dict[str, pd.DataFrame],  # pylint: disable=unused-argument
    num_years: int,
    output_directory: str,
    simulation_name: str,
    simulation_number: int,
    simulation_output: pd.DataFrame,
    total_loads: Dict[ResourceType, pd.DataFrame],
    total_solar_output: pd.DataFrame,
) -> None:
    """
    Plots all the outputs given below.

    NOTE: To add an output to be plotted, simply add to this function.

    Inputs:
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - grid_input_profile:
            The relevant grid input profile for the simulation that was run.
        - grid_profile:
            The relevant grid profile for the simulation that was run.
        - initial_cw_hourly_loads:
            The initial clean water hourly load for each device for the initial period
            of the simulation run.
        - initial_electric_hourly_loads:
            The hourly load profiles of each device for the initial period of the
            simulation run.
        - num_years:
            The number of years for which the simulation was run.
        - output_directory:
            The directory into which to save the output information.
        - simulation_name:
            The filename used when saving the simulation.
        - simulation_number:
            The number of the simulation being run.
        - simulation_output:
            The output of the simulation carried out.
        - total_loads:
            The total loads, keyed by :class:`.__utils__.ResourceType`, placed on the
            system.
        - total_solar_output:
            The total solar power produced by the PV installation.

    """

    # Create an output directory for the various plots to be saved in.
    figures_directory = os.path.join(
        output_directory,
        simulation_name,
        SIMULATION_PLOTS_DIRECTORY.format(simulation_number=simulation_number),
    )
    os.makedirs(os.path.join(output_directory, simulation_name), exist_ok=True)
    os.makedirs(figures_directory, exist_ok=True)

    # total_cw_load = total_loads[ResourceType.CLEAN_WATER]
    total_electric_load = total_loads[ResourceType.ELECTRIC]
    # total_hw_load = total_loads[ResourceType.HOT_CLEAN_WATER]

    # Determine which aspects of the system need plotting.
    cw_pvt: bool = ColumnHeader.CW_PVT_ELECTRICITY_SUPPLIED.value in simulation_output
    hw_pvt: bool = ColumnHeader.HW_PVT_ELECTRICITY_SUPPLIED.value in simulation_output

    with tqdm(
        total=(9 + (1 if grid_profile is not None else 0)),
        desc="plots",
        leave=False,
        unit="plot",
    ) as pbar:
        # Plot the first year of solar generation as a heatmap.
        reshaped_data = np.reshape(
            total_solar_output.iloc[0:HOURS_PER_YEAR].values, (365, 24)
        )
        heatmap = sns.heatmap(
            reshaped_data,
            vmin=0,
            vmax=1,
            cmap=COLOUR_MAP,
            cbar_kws={"label": "Power output / kW"},
        )
        heatmap.set(
            xticks=range(0, 24, 2),
            xticklabels=range(0, 24, 2),
            yticks=range(0, 365, 30),
            yticklabels=range(0, 365, 30),
            xlabel="Hour of day",
            ylabel="Day of year",
            title="Output per kWp of solar capacity",
        )
        plt.xticks(rotation=0)
        plt.tight_layout()
        plt.savefig(
            os.path.join(figures_directory, "solar_output_hetamap.png"),
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        # Plot the yearly power generated by the solar system.
        solar_daily_sums = pd.DataFrame(np.sum(reshaped_data, axis=1))
        plt.plot(range(365), solar_daily_sums[0])
        plt.xticks(range(0, 365, 30))
        plt.yticks(range(0, 9, 2))
        plt.xlabel("Day of year")
        plt.ylabel("Energy generation / kWh per day")
        plt.title("Daily energy generation of 1 kWp of solar capacity")
        plt.savefig(
            os.path.join(figures_directory, "solar_output_yearly.png"), transparent=True
        )
        plt.close()
        pbar.update(1)

        # Plot the grid availablity profile.
        if grid_profile is not None:
            reshaped_data = np.reshape(
                grid_profile.iloc[0:HOURS_PER_YEAR].values, (365, 24)
            )
            heatmap = sns.heatmap(
                reshaped_data, vmin=0, vmax=1, cmap="Greys_r", cbar=False
            )
            heatmap.set(
                xticks=range(0, 24, 2),
                xticklabels=range(0, 24, 2),
                yticks=range(0, 365, 30),
                yticklabels=range(0, 365, 30),
                xlabel="Hour of day",
                ylabel="Day of year",
                title="Grid availability of the selected profile.",
            )
            plt.xticks(rotation=0)
            plt.tight_layout()
            plt.savefig(
                os.path.join(figures_directory, "grid_availability_heatmap.png"),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

        # Plot the input vs. randomised grid avialability profiles.
        plt.plot(range(24), grid_input_profile, color="k", label="Input")
        plt.plot(range(24), np.mean(reshaped_data, axis=0), color="r", label="Output")
        plt.legend()
        plt.xticks(range(0, 24, 2))
        plt.yticks(np.arange(0, 1.1, 0.2))
        plt.xlabel("Hour of day")
        plt.ylabel("Probability")
        plt.title("Probability of grid electricity being available")
        plt.savefig(
            os.path.join(
                figures_directory, "grid_availability_randomisation_comparison.png"
            ),
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        # Plot the initial electric load of each device.
        for device, load in initial_electric_hourly_loads.items():
            plt.plot(range(CUT_OFF_TIME), load.values, label=device)
        plt.xticks(range(0, CUT_OFF_TIME - 1, min(6, CUT_OFF_TIME - 1)))
        plt.xlabel("Hour of simulation")
        plt.ylabel("Device load / W")
        plt.title("Electric load demand of each device")
        plt.tight_layout()
        plt.legend()
        plt.savefig(
            os.path.join(figures_directory, "electric_device_loads.png"),
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        # Plot the electric load breakdown by load type.
        plt.plot(
            range(CUT_OFF_TIME),
            total_electric_load[0:CUT_OFF_TIME][DemandType.DOMESTIC.value],
            label=DemandType.DOMESTIC.value,
        )
        plt.plot(
            range(CUT_OFF_TIME),
            total_electric_load[0:CUT_OFF_TIME][DemandType.COMMERCIAL.value],
            label=DemandType.COMMERCIAL.value,
        )
        plt.plot(
            range(CUT_OFF_TIME),
            total_electric_load[0:CUT_OFF_TIME][DemandType.PUBLIC.value],
            label=DemandType.PUBLIC.value,
        )
        plt.plot(
            range(CUT_OFF_TIME),
            np.sum(total_electric_load[0:CUT_OFF_TIME], axis=1),
            "--",
            label="total",
        )
        plt.legend(loc="upper right")
        plt.xticks(list(range(0, CUT_OFF_TIME - 1, min(4, CUT_OFF_TIME - 1))))
        plt.xlabel("Hour of simulation")
        plt.ylabel("Electric power demand / kW")
        plt.title(f"Load profile of the community for the first {CUT_OFF_TIME} hours")
        plt.savefig(
            os.path.join(figures_directory, "electric_demands.png"),
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        # Plot the annual variation of the electricity demand.
        _, axis = plt.subplots(1, 2, figsize=(8, 4))
        domestic_demand = np.sum(
            np.reshape(
                total_electric_load[0:HOURS_PER_YEAR][DemandType.DOMESTIC.value].values,
                (365, 24),
            ),
            axis=1,
        )
        commercial_demand = np.sum(
            np.reshape(
                total_electric_load[0:HOURS_PER_YEAR][
                    DemandType.COMMERCIAL.value
                ].values,
                (365, 24),
            ),
            axis=1,
        )
        public_demand = np.sum(
            np.reshape(
                total_electric_load[0:HOURS_PER_YEAR][DemandType.PUBLIC.value].values,
                (365, 24),
            ),
            axis=1,
        )
        total_demand = np.sum(
            np.reshape(
                np.sum(total_electric_load[0:HOURS_PER_YEAR].values, axis=1),
                (365, 24),
            ),
            axis=1,
        )
        axis[0].plot(
            range(365),
            pd.DataFrame(domestic_demand).rolling(5).mean(),
            label="Domestic",
            color="blue",
        )
        axis[0].plot(
            range(365),
            pd.DataFrame(commercial_demand).rolling(5).mean(),
            label="Commercial",
            color="orange",
        )
        axis[0].plot(
            range(365),
            pd.DataFrame(public_demand).rolling(5).mean(),
            label="Public",
            color="green",
        )
        axis[0].plot(range(365), domestic_demand, alpha=0.5, color="blue")
        axis[0].plot(range(365), commercial_demand, alpha=0.5, color="orange")
        axis[0].plot(range(365), public_demand, alpha=0.5, color="green")
        axis[0].legend(loc="best")
        axis[0].set(
            xticks=(range(0, 366, 60)),
            yticks=range(0, 26, 5),
            xlabel="Day of simulation period",
            ylabel="Load / kWh/day",
            title="Energy demand of each load type",
        )
        axis[1].plot(
            range(365),
            pd.DataFrame(total_demand).rolling(5).mean(),
            "--",
            label="Total",
            color="red",
        )
        axis[1].plot(range(365), total_demand, "--", alpha=0.5, color="red")
        axis[1].legend(loc="best")
        axis[1].set(
            xticks=(range(0, 366, 60)),
            yticks=range(15, 41, 5),
            xlabel="Day of simulation period",
            ylabel="Load / kWh/day",
            title="Total community energy demand",
        )
        plt.tight_layout()
        plt.savefig(
            os.path.join(figures_directory, "electric_demand_annual_variation.png"),
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        # Plot the demand growth over the simulation period.
        domestic_demand = np.sum(
            np.reshape(
                0.001
                * total_electric_load[0 : num_years * HOURS_PER_YEAR][
                    DemandType.DOMESTIC.value
                ].values,
                (num_years, HOURS_PER_YEAR),
            ),
            axis=1,
        )
        commercial_demand = np.sum(
            np.reshape(
                0.001
                * total_electric_load[0 : num_years * HOURS_PER_YEAR][
                    DemandType.COMMERCIAL.value
                ].values,
                (num_years, HOURS_PER_YEAR),
            ),
            axis=1,
        )
        public_demand = np.sum(
            np.reshape(
                0.001
                * total_electric_load[0 : num_years * HOURS_PER_YEAR][
                    DemandType.PUBLIC.value
                ].values,
                (num_years, HOURS_PER_YEAR),
            ),
            axis=1,
        )
        total_demand = np.sum(
            0.001
            * np.reshape(
                np.sum(
                    total_electric_load[0 : num_years * HOURS_PER_YEAR].values, axis=1
                ),
                (num_years, HOURS_PER_YEAR),
            ),
            axis=1,
        )
        plt.plot(
            range(num_years),
            domestic_demand,
            label=DemandType.DOMESTIC.value,
            color="blue",
        )
        plt.plot(
            range(num_years),
            commercial_demand,
            label=DemandType.COMMERCIAL.value,
            color="orange",
        )
        plt.plot(
            range(num_years),
            public_demand,
            label=DemandType.PUBLIC.value,
            color="green",
        )
        plt.plot(range(num_years), total_demand, "--", label="total", color="red")
        plt.legend(loc="upper left")
        plt.xticks(range(0, num_years, 2 if num_years > 2 else 1))
        plt.xlabel("Year of investigation period")
        plt.ylabel("Energy demand / MWh/year")
        plt.title("Load growth of the community")
        plt.savefig(
            os.path.join(figures_directory, "electric_load_growth.png"),
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        total_used = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.TOTAL_ELECTRICITY_CONSUMED.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        diesel_energy = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.DIESEL_ENERGY_SUPPLIED.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        dumped = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.DUMPED_ELECTRICITY.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        grid_energy = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.GRID_ENERGY.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        renewable_energy = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.RENEWABLE_ELECTRICITY_USED_DIRECTLY.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        pv_supplied = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.RENEWABLE_ELECTRICITY_SUPPLIED.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        clean_water_pvt_supplied = (
            np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.CW_PVT_ELECTRICITY_SUPPLIED.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            if ColumnHeader.CW_PVT_ELECTRICITY_SUPPLIED.value in simulation_output
            else None
        )
        hot_water_pvt_supplied = (
            np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.HW_PVT_ELECTRICITY_SUPPLIED.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            if ColumnHeader.HW_PVT_ELECTRICITY_SUPPLIED.value in simulation_output
            else None
        )
        storage_energy = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.ELECTRICITY_FROM_STORAGE.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        unmet_energy = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.UNMET_ELECTRICITY.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )

        plt.plot(total_used, "--", label="Total used", zorder=1)
        plt.plot(unmet_energy, label="Unmet", zorder=2)
        plt.plot(diesel_energy, label="Diesel", zorder=3)
        plt.plot(dumped, label="Dumped", zorder=4)
        plt.plot(grid_energy, label="Grid", zorder=5)
        plt.plot(storage_energy, label="Storage", zorder=6)
        plt.plot(renewable_energy, label="Renewables used directly", zorder=7)
        plt.plot(pv_supplied, label="PV electricity generated", zorder=8)
        if cw_pvt:
            clean_water_energy_via_excess = (
                np.mean(
                    np.reshape(
                        simulation_output[0:HOURS_PER_YEAR][
                            ColumnHeader.EXCESS_POWER_CONSUMED_BY_DESALINATION.value
                        ].values,
                        (365, 24),
                    ),
                    axis=0,
                )
                if ColumnHeader.EXCESS_POWER_CONSUMED_BY_DESALINATION.value
                in simulation_output
                else None
            )
            clean_water_energy_via_backup = (
                np.mean(
                    np.reshape(
                        simulation_output[0:HOURS_PER_YEAR][
                            ColumnHeader.POWER_CONSUMED_BY_DESALINATION.value
                        ].values,
                        (365, 24),
                    ),
                    axis=0,
                )
                if ColumnHeader.POWER_CONSUMED_BY_DESALINATION.value
                in simulation_output
                else None
            )
            thermal_desalination_energy = (
                np.mean(
                    np.reshape(
                        simulation_output[0:HOURS_PER_YEAR][
                            ColumnHeader.POWER_CONSUMED_BY_THERMAL_DESALINATION.value
                        ].values,
                        (365, 24),
                    ),
                    axis=0,
                )
                if ColumnHeader.POWER_CONSUMED_BY_THERMAL_DESALINATION.value
                in simulation_output
                else None
            )
            plt.plot(
                clean_water_energy_via_excess,
                label="Excess -> clean water",
                zorder=int(10 + (2 if cw_pvt else 0) + (1 if hw_pvt else 0)),
            )
            plt.plot(
                clean_water_energy_via_backup,
                label="Backup -> clean water",
                zorder=11 + (2 if cw_pvt else 0) + (1 if hw_pvt else 0),
            )
            plt.plot(
                clean_water_pvt_supplied,
                label="CW PV-T electricity generated",
                zorder=9,
            )
            plt.plot(
                thermal_desalination_energy,
                label="Thermal desal electric power",
                zorder=10,
            )
        if hw_pvt:
            plt.plot(
                hot_water_pvt_supplied,
                label="HW PV-T electricity generated",
                zorder=(10 + (2 if cw_pvt else 0)),
            )
        plt.legend()
        plt.xlim(0, 23)
        plt.xticks(range(0, 24, 1))
        plt.xlabel("Hour of day")
        plt.ylabel("Average energy / kWh/hour")
        plt.title("Energy supply and demand on an average day")
        plt.savefig(
            os.path.join(figures_directory, "electricity_use_on_average_day.png"),
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        blackouts = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.BLACKOUTS.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        storage_energy = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.ELECTRICITY_FROM_STORAGE.value
                ].values
                > 0,
                (365, 24),
            ),
            axis=0,
        )
        solar_usage = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.RENEWABLE_ELECTRICITY_USED_DIRECTLY.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        diesel_times = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.DIESEL_GENERATOR_TIMES.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )

        plt.plot(blackouts, label=ColumnHeader.BLACKOUTS.value)
        plt.plot(solar_usage, label="Renewables")
        plt.plot(storage_energy, label="Storage")
        plt.plot(grid_energy, label="Grid")
        plt.plot(diesel_times, label="Diesel")
        plt.legend()
        plt.xlim(0, 23)
        plt.xticks(range(0, 24, 1))
        plt.ylim(0, 1)
        plt.yticks(np.arange(0, 1.1, 0.25))
        plt.xlabel("Hour of day")
        plt.ylabel("Probability")
        plt.title("Energy availability on an average day")
        plt.savefig(
            os.path.join(
                figures_directory, "electricity_avilability_on_average_day.png"
            ),
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        # Plot the seasonal variation in electricity supply sources.
        grid_energy = np.reshape(
            simulation_output[0:HOURS_PER_YEAR][ColumnHeader.GRID_ENERGY.value].values,
            (365, 24),
        )
        storage_energy = np.reshape(
            simulation_output[0:HOURS_PER_YEAR][
                ColumnHeader.ELECTRICITY_FROM_STORAGE.value
            ].values,
            (365, 24),
        )
        renewable_energy = np.reshape(
            simulation_output[0:HOURS_PER_YEAR][
                ColumnHeader.RENEWABLE_ELECTRICITY_USED_DIRECTLY.value
            ].values,
            (365, 24),
        )
        diesel_energy = np.reshape(
            simulation_output[0:HOURS_PER_YEAR][
                ColumnHeader.DIESEL_GENERATOR_TIMES.value
            ].values,
            (365, 24),
        )

        fig, ([ax1, ax2], [ax3, ax4]) = plt.subplots(2, 2)  # ,sharex=True, sharey=True)
        sns.heatmap(
            renewable_energy, vmin=0.0, vmax=4.0, cmap="Reds", cbar=True, ax=ax1
        )
        ax1.set(
            xticks=range(0, 25, 6),
            xticklabels=range(0, 25, 6),
            yticks=range(0, 365, 60),
            yticklabels=range(0, 365, 60),
            xlabel="Hour of day",
            ylabel="Day of year",
            title="Renewables",
        )
        sns.heatmap(
            storage_energy, vmin=0.0, vmax=4.0, cmap="Greens", cbar=True, ax=ax2
        )
        ax2.set(
            xticks=range(0, 25, 6),
            xticklabels=range(0, 25, 6),
            yticks=range(0, 365, 60),
            yticklabels=range(0, 365, 60),
            xlabel="Hour of day",
            ylabel="Day of year",
            title="Storage",
        )
        sns.heatmap(grid_energy, vmin=0.0, vmax=4.0, cmap="Blues", cbar=True, ax=ax3)
        ax3.set(
            xticks=range(0, 25, 6),
            xticklabels=range(0, 25, 6),
            yticks=range(0, 365, 60),
            yticklabels=range(0, 365, 60),
            xlabel="Hour of day",
            ylabel="Day of year",
            title="Grid",
        )
        sns.heatmap(diesel_energy, vmin=0.0, vmax=4.0, cmap="Greys", cbar=True, ax=ax4)
        ax4.set(
            xticks=range(0, 25, 6),
            xticklabels=range(0, 25, 6),
            yticks=range(0, 365, 60),
            yticklabels=range(0, 365, 60),
            xlabel="Hour of day",
            ylabel="Day of year",
            title="Diesel",
        )
        plt.tight_layout()
        fig.suptitle("Electricity from different sources (kWh)")
        fig.subplots_adjust(top=0.87)
        plt.xticks(rotation=0)
        plt.savefig(
            os.path.join(
                figures_directory, "seasonal_electricity_supply_variations.png"
            ),
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        total_used = simulation_output.iloc[0:24][
            ColumnHeader.TOTAL_ELECTRICITY_CONSUMED.value
        ]
        renewable_energy = simulation_output.iloc[0:24][
            ColumnHeader.RENEWABLE_ELECTRICITY_USED_DIRECTLY.value
        ]
        storage_energy = simulation_output.iloc[0:24][
            ColumnHeader.ELECTRICITY_FROM_STORAGE.value
        ]
        grid_energy = simulation_output.iloc[0:24][ColumnHeader.GRID_ENERGY.value]
        diesel_energy = simulation_output.iloc[0:24][
            ColumnHeader.DIESEL_ENERGY_SUPPLIED.value
        ]
        dumped_energy = simulation_output.iloc[0:24][
            ColumnHeader.DUMPED_ELECTRICITY.value
        ]
        unmet_energy = simulation_output.iloc[0:24][
            ColumnHeader.UNMET_ELECTRICITY.value
        ]
        pv_supplied = simulation_output.iloc[0:24][
            ColumnHeader.PV_ELECTRICITY_SUPPLIED.value
        ]
        clean_water_pvt_supplied = (
            simulation_output.iloc[0:24][ColumnHeader.CW_PVT_ELECTRICITY_SUPPLIED.value]
            if ColumnHeader.CW_PVT_ELECTRICITY_SUPPLIED.value in simulation_output
            else None
        )
        hot_water_pvt_supplied = (
            simulation_output.iloc[0:24][ColumnHeader.HW_PVT_ELECTRICITY_SUPPLIED.value]
            if ColumnHeader.HW_PVT_ELECTRICITY_SUPPLIED.value in simulation_output
            else None
        )

        plt.plot(total_used, "--", label="Total used", zorder=1)
        plt.plot(unmet_energy, label="Unmet", zorder=2)
        plt.plot(diesel_energy, label="Diesel", zorder=3)
        plt.plot(dumped_energy, label="Dumped", zorder=4)
        plt.plot(grid_energy, label="Grid", zorder=5)
        plt.plot(storage_energy, label="Storage", zorder=6)
        plt.plot(renewable_energy, label="Solar used directly", zorder=7)
        plt.plot(pv_supplied, label="PV generated", zorder=8)
        if cw_pvt:
            plt.plot(
                clean_water_pvt_supplied,
                label="CW PV-T electricity generated",
                zorder=9,
            )
            thermal_desalination_energy = simulation_output.iloc[0:24][
                ColumnHeader.POWER_CONSUMED_BY_THERMAL_DESALINATION.value
            ]
            plt.plot(
                thermal_desalination_energy,
                label="Thermal desal electric power",
                zorder=10,
            )
        if hw_pvt:
            plt.plot(
                hot_water_pvt_supplied,
                label="HW PV-T electricity generated",
                zorder=9 + (2 if cw_pvt else 0),
            )
        # if initial_cw_hourly_loads is not None:
        #     clean_water_energy_via_excess = simulation_output.iloc[0:24][
        #         ColumnHeader.EXCESS_POWER_CONSUMED_BY_DESALINATION.value
        #     ]
        #     clean_water_energy_via_backup = simulation_output.iloc[0:24][
        #         ColumnHeader.POWER_CONSUMED_BY_DESALINATION.value
        #     ]
        #     plt.plot(
        #         clean_water_energy_via_excess,
        #         label="Excess -> clean water",
        #         zorder=10 + (2 if cw_pvt else 0) + (1 if hw_pvt else 0),
        #     )
        #     plt.plot(
        #         clean_water_energy_via_backup,
        #         label="Backup -> clean water",
        #         zorder=11 + (2 if cw_pvt else 0) + (1 if hw_pvt else 0),
        #     )
        plt.legend()
        plt.xlim(0, 23)
        plt.xticks(range(0, 24, 1))
        plt.xlabel("Hour of day")
        plt.ylabel("Average energy / kWh/hour")
        plt.title("Energy supply and demand on the frist day")
        plt.savefig(
            os.path.join(figures_directory, "electricity_use_on_first_day.png"),
            transparent=True,
        )
        plt.close()
        pbar.update(1)
