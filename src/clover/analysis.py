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

# Hours until month:
#   Mapping between month number and the hours until the start of the month.
HOURS_UNTIL: Dict[int, int] = {
    1: 0,
    2: 744,
    3: 1416,
    4: 2160,
    5: 2880,
    6: 3624,
    7: 4344,
    8: 5088,
    9: 5832,
    10: 6552,
    11: 7296,
    12: 8016,
}

# Plot resolution:
#   The resolution, in dpi, to use for plotting figures.
PLOT_RESOLUTION: int = 600

# Simulation plots directory:
#   The directory in which simulation plots should be saved.
SIMULATION_PLOTS_DIRECTORY: str = "simulation_{simulation_number}_plots"

# Style sheet:
#   The preferred matplotlib stylesheet to use.
STYLE_SHEET: str = "tableau-colorblind10"
# Options available:
#   _classic_test_patch
#   bmh
#   classic
#   dark_background
#   fast
#   fivethirtyeight
#   ggplot
#   grayscale
#   seaborn
#   seaborn-bright
#   seaborn-colorblind
#   seaborn-dark
#   seaborn-dark-palette
#   seaborn-darkgrid
#   seaborn-deep
#   seaborn-muted
#   seaborn-notebook
#   seaborn-paper
#   seaborn-pastel
#   seaborn-poster
#   seaborn-talk
#   seaborn-ticks
#   seaborn-white
#   seaborn-whitegrid
#   tableau-colorblind10


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
    key_results.average_renewable_generation = float(
        round(total_solar_generation / (20 * 365))
    )

    # Compute the grid results.
    key_results.grid_daily_hours = np.sum(grid_input_profile, axis=0)

    # Compute the simulation related averages and sums.
    key_results.average_daily_diesel_energy_supplied = simulation_results[
        ColumnHeader.DIESEL_ENERGY_SUPPLIED.value
    ].sum() / (365 * num_years)

    key_results.average_daily_dumped_energy = simulation_results[
        ColumnHeader.DUMPED_ELECTRICITY.value
    ].sum() / (365 * num_years)

    key_results.average_daily_electricity_consumption = simulation_results[
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
        np.nanmean(simulation_results[ColumnHeader.DIESEL_GENERATOR_TIMES.value]), 3
    )
    key_results.blackouts = round(
        np.nanmean(simulation_results[ColumnHeader.BLACKOUTS.value]), 3
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
            np.nanmean(simulation_results[ColumnHeader.CLEAN_WATER_BLACKOUTS.value]), 3
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
            np.nanmean(simulation_results[ColumnHeader.BUFFER_TANK_TEMPERATURE.value]),
            3,
        )
        key_results.mean_cw_pvt_output_temperature = round(
            np.nanmean(
                simulation_results[ColumnHeader.CW_PVT_OUTPUT_TEMPERATURE.value]
            ),
            3,
        )
        key_results.min_buffer_tank_temperature = round(
            min(simulation_results[ColumnHeader.BUFFER_TANK_TEMPERATURE.value]), 3
        )
        key_results.min_cw_pvt_output_temperature = round(
            min(simulation_results[ColumnHeader.CW_PVT_OUTPUT_TEMPERATURE.value]), 3
        )

    # Compute the hot-water key results.
    if ColumnHeader.TOTAL_HW_LOAD.value in simulation_results:
        key_results.average_daily_hw_renewable_fraction = round(
            np.nanmean(
                simulation_results[ColumnHeader.HW_SOLAR_THERMAL_FRACTION.value]
            ),
            3,
        )
        key_results.average_daily_hw_pvt_generation = round(
            np.nanmean(
                simulation_results[
                    ColumnHeader.HW_PVT_ELECTRICITY_SUPPLIED_PER_KWP.value
                ]
            ),
            3,
        )
        key_results.average_daily_hw_supplied = round(
            simulation_results[ColumnHeader.HW_TANK_OUTPUT.value].sum()
            / (365 * num_years),
            3,
        )
        key_results.average_daily_hw_demand_covered = round(
            np.nanmean(simulation_results[ColumnHeader.HW_VOL_DEMAND_COVERED.value]),
            3,
        )

    # Compute the waste-product key results.
    if ColumnHeader.BRINE.value in simulation_results:
        key_results.cumulative_brine = round(
            simulation_results[ColumnHeader.BRINE.value].sum(), 3
        )

    return key_results


def plot_outputs(
    grid_input_profile: pd.DataFrame,
    grid_profile: pd.DataFrame,
    initial_cw_hourly_loads: Optional[Dict[str, pd.DataFrame]],
    initial_electric_hourly_loads: Dict[str, pd.DataFrame],
    initial_hw_hourly_loads: Dict[str, pd.DataFrame],
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

    # Set plotting parameters.
    plt.rcParams["axes.labelsize"] = "20"
    plt.rcParams["figure.figsize"] = (6.8, 6.8)
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Arial"]
    plt.rcParams["font.size"] = "20"
    plt.rcParams["xtick.labelsize"] = "20"
    plt.rcParams["ytick.labelsize"] = "20"
    plt.style.use(STYLE_SHEET)

    # Create an output directory for the various plots to be saved in.
    figures_directory = os.path.join(
        output_directory,
        simulation_name,
        SIMULATION_PLOTS_DIRECTORY.format(simulation_number=simulation_number),
    )
    os.makedirs(os.path.join(output_directory, simulation_name), exist_ok=True)
    os.makedirs(figures_directory, exist_ok=True)

    total_cw_load = total_loads[ResourceType.CLEAN_WATER]
    total_electric_load = total_loads[ResourceType.ELECTRIC]
    total_hw_load = total_loads[ResourceType.HOT_CLEAN_WATER]

    # Determine which aspects of the system need plotting.
    cw_pvt: bool = ColumnHeader.CW_PVT_ELECTRICITY_SUPPLIED.value in simulation_output
    hw_pvt: bool = ColumnHeader.HW_PVT_ELECTRICITY_SUPPLIED.value in simulation_output

    with tqdm(
        total=16
        + (17 if initial_cw_hourly_loads is not None else 0)
        + (4 if cw_pvt else 0)
        + (15 if initial_hw_hourly_loads is not None else 0),
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
            bbox_inches='tight',
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
        # plt.title("Daily energy generation of 1 kWp of solar capacity")
        plt.savefig(
            os.path.join(figures_directory, "solar_output_yearly.png"),
            bbox_inches='tight',
            transparent=True
        )
        plt.close()
        pbar.update(1)

        # Plot the grid availablity profile.
        reshaped_data = np.reshape(
            grid_profile.iloc[0:HOURS_PER_YEAR].values, (365, 24)
        )
        heatmap = sns.heatmap(reshaped_data, vmin=0, vmax=1, cmap="Greys_r", cbar=False)
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
            bbox_inches='tight',
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        # Plot the input vs. randomised grid avialability profiles.
        plt.plot(range(24), grid_input_profile, color="k", label="Input")
        plt.plot(
            range(24), np.nanmean(reshaped_data, axis=0), color="r", label="Output"
        )
        plt.legend()
        plt.xticks(range(0, 24, 2))
        plt.yticks(np.arange(0, 1.1, 0.2))
        plt.xlabel("Hour of day")
        plt.ylabel("Probability")
        # plt.title("Probability of grid electricity being available")
        plt.savefig(
            os.path.join(
                figures_directory, "grid_availability_randomisation_comparison.png"
            ),
            bbox_inches='tight',
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        # Plot the initial electric load of each device.
        fig, ax = plt.subplots()
        cumulative_load = 0
        for device, load in sorted(initial_electric_hourly_loads.items()):
            ax.bar(range(len(load)), load[0], label=device, bottom=cumulative_load)
            if isinstance(cumulative_load, int) and cumulative_load == 0:
                cumulative_load = load[0]
                continue
            cumulative_load += load[0]

        ax.set_xlabel("Hour of simulation")
        ax.set_ylabel("Device load / W")
        # ax.set_title("Electric load of each device")
        ax.legend()
        plt.savefig(
            os.path.join(figures_directory, "electric_device_loads.png"),
            bbox_inches='tight',
            transparent=True,
        )
        plt.close(fig)
        pbar.update(1)

        # Plot the average electric load of each device for the first year.
        cumulative_load = 0
        fig, ax = plt.subplots()
        for device, load in sorted(initial_electric_hourly_loads.items()):
            average_load = np.nanmean(
                np.asarray(load[0:CUT_OFF_TIME]).reshape(
                    (CUT_OFF_TIME // 24, 24),
                ),
                axis=0,
            )

            if np.sum(average_load) > 0:
                ax.bar(range(24), average_load, label=device, bottom=cumulative_load)
            if isinstance(cumulative_load, int) and cumulative_load == 0:
                cumulative_load = average_load
                continue
            cumulative_load += average_load

        ax.set_xlabel("Hour of simulation")
        ax.set_ylabel("Device load / W")
        # ax.set_title(
        #     "Average electric load demand of each device over the first {} days.".format(
        #         CUT_OFF_TIME // 24
        #     )
        # )
        ax.legend()
        plt.savefig(
            os.path.join(figures_directory, "electric_device_loads_average.png"),
            bbox_inches='tight',
            transparent=True,
        )
        plt.close(fig)
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
        plt.xticks(
            [entry for entry in (range(0, CUT_OFF_TIME - 1, min(4, CUT_OFF_TIME - 1)))]
        )
        plt.xlabel("Hour of simulation")
        plt.ylabel("Electric power demand / kW")
        # plt.title(f"Load profile of the community for the first {CUT_OFF_TIME} hours")
        plt.savefig(
            os.path.join(figures_directory, "electric_demands.png"),
            bbox_inches='tight',
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        # Plot the average electric load breakdown by load type.
        domestic_demand = np.nanmean(
            np.asarray(
                total_electric_load[0:HOURS_PER_YEAR][DemandType.DOMESTIC.value]
            ).reshape(
                (365, 24),
            ),
            axis=0,
        )
        commercial_demand = np.nanmean(
            np.asarray(
                total_electric_load[0:HOURS_PER_YEAR][DemandType.COMMERCIAL.value]
            ).reshape(
                (365, 24),
            ),
            axis=0,
        )
        public_demand = np.nanmean(
            np.asarray(
                total_electric_load[0:HOURS_PER_YEAR][DemandType.PUBLIC.value]
            ).reshape(
                (365, 24),
            ),
            axis=0,
        )
        total_demand = np.nanmean(
            np.asarray(np.sum(total_electric_load[0:HOURS_PER_YEAR], axis=1)).reshape(
                (365, 24),
            ),
            axis=0,
        )

        # Plot as a line plot
        plt.plot(
            domestic_demand,
            label=DemandType.DOMESTIC.value,
        )
        plt.plot(
            commercial_demand,
            label=DemandType.COMMERCIAL.value,
        )
        plt.plot(
            public_demand,
            label=DemandType.PUBLIC.value,
        )
        plt.plot(
            total_demand,
            "--",
            label="total",
        )
        plt.legend(loc="upper right")
        plt.xticks([entry for entry in (range(0, 23, 4))])
        plt.xlabel("Hour of simulation")
        plt.ylabel("Electric power demand / kW")
        # plt.title(
        #     "Average load profile of the community during the first simulation year"
        # )
        plt.savefig(
            os.path.join(figures_directory, "electric_demands_yearly.png"),
            bbox_inches='tight',
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        # Plot as a bar plot
        fig, ax = plt.subplots()
        ax.bar(range(len(domestic_demand)), domestic_demand, label="Domestic")
        ax.bar(
            range(len(commercial_demand)),
            commercial_demand,
            label="Commercial",
            bottom=domestic_demand,
        )
        ax.bar(
            range(len(public_demand)),
            public_demand,
            label="Public",
            bottom=domestic_demand + commercial_demand,
        )
        ax.set_xlabel("Hour of simulation")
        ax.set_ylabel("Electric power demand / kW")
        # ax.set_title(
        #     "Average load profile of the community during the first simulation year"
        # )
        ax.legend()
        plt.savefig(
            os.path.join(figures_directory, "electric_device_loads_average_bar.png"),
            bbox_inches='tight',
            transparent=True,
        )
        plt.close(fig)
        pbar.update(1)

        # Plot the annual variation of the electricity demand.
        fig, axis = plt.subplots(1, 2, figsize=(8, 4))
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
            bbox_inches='tight',
            transparent=True,
        )
        plt.close(fig)
        pbar.update(1)

        # Plot the total seasonal variation as a stand-alone figure.
        plt.plot(
            range(365),
            pd.DataFrame(total_demand).rolling(5).mean(),
            "--",
            label="Total",
            color="red",
        )
        plt.plot(range(365), total_demand, "--", alpha=0.5, color="red")
        plt.legend(loc="best")
        plt.xticks(range(0, 366, 60))
        plt.xlabel("Day of simulation period")
        plt.ylabel("Load / kWh/day")
        # plt.title("Total community energy demand")
        plt.tight_layout()
        plt.savefig(
            os.path.join(
                figures_directory, "electric_demand_total_annual_variation.png"
            ),
            bbox_inches='tight',
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
        # plt.title("Load growth of the community")
        plt.savefig(
            os.path.join(figures_directory, "electric_load_growth.png"),
            bbox_inches='tight',
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        total_used = np.nanmean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.TOTAL_ELECTRICITY_CONSUMED.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        diesel_energy = np.nanmean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.DIESEL_ENERGY_SUPPLIED.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        dumped = np.nanmean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.DUMPED_ELECTRICITY.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        grid_energy = np.nanmean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.GRID_ENERGY.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        renewable_energy = np.nanmean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.RENEWABLE_ELECTRICITY_USED_DIRECTLY.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        pv_supplied = np.nanmean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.RENEWABLE_ELECTRICITY_SUPPLIED.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        clean_water_pvt_supplied = (
            np.nanmean(
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
            np.nanmean(
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
        storage_energy = np.nanmean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.ELECTRICITY_FROM_STORAGE.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        unmet_energy = np.nanmean(
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
                np.nanmean(
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
                np.nanmean(
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
                np.nanmean(
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
        # plt.title("Energy supply and demand on an average day")
        plt.savefig(
            os.path.join(figures_directory, "electricity_use_on_average_day.png"),
            bbox_inches='tight',
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        blackouts = np.nanmean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.BLACKOUTS.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        storage_energy = np.nanmean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.ELECTRICITY_FROM_STORAGE.value
                ].values
                > 0,
                (365, 24),
            ),
            axis=0,
        )
        solar_usage = np.nanmean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.RENEWABLE_ELECTRICITY_USED_DIRECTLY.value
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        diesel_times = np.nanmean(
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
        # plt.title("Energy availability on an average day")
        plt.savefig(
            os.path.join(
                figures_directory, "electricity_avilability_on_average_day.png"
            ),
            bbox_inches='tight',
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
            bbox_inches='tight',
            transparent=True,
        )
        plt.close(fig)
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
        # plt.title("Energy supply and demand on the frist day")
        plt.savefig(
            os.path.join(figures_directory, "electricity_use_on_first_day.png"),
            bbox_inches='tight',
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        if initial_cw_hourly_loads is not None:
            # Plot the initial clean-water load of each device.
            fig, ax = plt.subplots()
            cumulative_load = 0
            for device, load in sorted(initial_cw_hourly_loads.items()):
                ax.bar(range(len(load)), load[0], label=device, bottom=cumulative_load)

                if isinstance(cumulative_load, int) and cumulative_load == 0:
                    cumulative_load = load[0]
                    continue
                cumulative_load += load[0]

            ax.set_xlabel("Hour of simulation")
            ax.set_ylabel("Device load / litres/hour")
            # ax.set_title("Clean water demand of each device")
            ax.legend()
            plt.savefig(
                os.path.join(figures_directory, "clean_water_device_loads.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close(fig)
            pbar.update(1)

            # Plot the average clean-water load of each device for the first year.
            fig, ax = plt.subplots()
            cumulative_load = 0
            for device, load in sorted(initial_cw_hourly_loads.items()):
                average_load = np.nanmean(
                    np.asarray(load[0:CUT_OFF_TIME]).reshape(
                        (CUT_OFF_TIME // 24, 24),
                    ),
                    axis=0,
                )
                ax.bar(range(24), average_load, label=device, bottom=cumulative_load)

                if isinstance(cumulative_load, int) and cumulative_load == 0:
                    cumulative_load = average_load
                    continue
                cumulative_load += average_load

            ax.set_xlabel("Hour of simulation")
            ax.set_ylabel("Device load / litres/hour")
            ax.legend()
            # ax.set_title(
            #     "Average clean water demand of each device over the first {} days.".format(
            #         CUT_OFF_TIME // 24
            #     )
            # )
            plt.legend()
            plt.savefig(
                os.path.join(figures_directory, "clean_water_device_loads_average.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close(fig)
            pbar.update(1)

            # Plot the clean-water load breakdown by load type.
            plt.plot(
                range(CUT_OFF_TIME),
                total_cw_load[0:CUT_OFF_TIME][DemandType.DOMESTIC.value],
                label=DemandType.DOMESTIC.value,
            )
            plt.plot(
                range(CUT_OFF_TIME),
                total_cw_load[0:CUT_OFF_TIME][DemandType.COMMERCIAL.value],
                label=DemandType.COMMERCIAL.value,
            )
            plt.plot(
                range(CUT_OFF_TIME),
                total_cw_load[0:CUT_OFF_TIME][DemandType.PUBLIC.value],
                label=DemandType.PUBLIC.value,
            )
            plt.plot(
                range(CUT_OFF_TIME),
                np.sum(total_cw_load[0:CUT_OFF_TIME], axis=1),
                "--",
                label="total",
            )
            plt.legend(loc="upper right")
            plt.xticks(
                [
                    entry
                    for entry in range(0, CUT_OFF_TIME - 1, min(4, CUT_OFF_TIME - 2))
                ]
            )
            plt.xlabel("Hour of simulation")
            plt.ylabel("Clean water demand / litres/hour")
            # plt.title(
            #     f"Clean-water load profile of the community for the first {CUT_OFF_TIME} hours"
            # )
            plt.savefig(
                os.path.join(figures_directory, "clean_water_demands.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the annual variation of the clean-water demand.
            fig, axis = plt.subplots(1, 2, figsize=(8, 4))
            domestic_demand = 0.001 * np.sum(
                np.reshape(
                    total_cw_load[0:HOURS_PER_YEAR][DemandType.DOMESTIC.value].values,
                    (365, 24),
                ),
                axis=1,
            )
            commercial_demand = 0.001 * np.sum(
                np.reshape(
                    total_cw_load[0:HOURS_PER_YEAR][DemandType.COMMERCIAL.value].values,
                    (365, 24),
                ),
                axis=1,
            )
            public_demand = 0.001 * np.sum(
                np.reshape(
                    total_cw_load[0:HOURS_PER_YEAR][DemandType.PUBLIC.value].values,
                    (365, 24),
                ),
                axis=1,
            )
            total_demand = 0.001 * np.sum(
                np.reshape(
                    np.sum(total_cw_load[0:HOURS_PER_YEAR].values, axis=1),
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
                xlabel="Day of simulation period",
                ylabel="Load / m^3/day",
                title="Clean-water demand of each load type",
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
                xlabel="Day of simulation period",
                ylabel="Load / m^3/day",
                title="Total community clean-water demand",
            )
            plt.tight_layout()
            plt.savefig(
                os.path.join(
                    figures_directory, "clean_water_demand_annual_variation.png"
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close(fig)
            pbar.update(1)

            # Plot the total seasonal variation as a stand-alone figure.
            plt.plot(
                range(365),
                pd.DataFrame(total_demand).rolling(5).mean(),
                "--",
                label="Total",
                color="red",
            )
            plt.plot(range(365), total_demand, "--", alpha=0.5, color="red")
            plt.legend(loc="best")
            plt.xticks(range(0, 366, 60))
            plt.xlabel("Day of simulation period")
            plt.ylabel("Load / m^3/day")
            # plt.title("Total community clean-water demand")
            plt.tight_layout()
            plt.savefig(
                os.path.join(
                    figures_directory, "clean_water_demand_total_annual_variation.png"
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the clean-water demand load growth.
            # Plot the demand growth over the simulation period.
            domestic_demand = np.sum(
                np.reshape(
                    0.001
                    * total_cw_load[0 : num_years * HOURS_PER_YEAR][
                        DemandType.DOMESTIC.value
                    ].values,
                    (num_years, HOURS_PER_YEAR),
                ),
                axis=1,
            )
            commercial_demand = np.sum(
                np.reshape(
                    0.001
                    * total_cw_load[0 : num_years * HOURS_PER_YEAR][
                        DemandType.COMMERCIAL.value
                    ].values,
                    (num_years, HOURS_PER_YEAR),
                ),
                axis=1,
            )
            public_demand = np.sum(
                np.reshape(
                    0.001
                    * total_cw_load[0 : num_years * HOURS_PER_YEAR][
                        DemandType.PUBLIC.value
                    ].values,
                    (num_years, HOURS_PER_YEAR),
                ),
                axis=1,
            )
            total_demand = np.sum(
                np.reshape(
                    np.sum(
                        0.001 * total_cw_load[0 : num_years * HOURS_PER_YEAR].values,
                        axis=1,
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
            plt.ylabel("Clean-water demand / Cubic meters/year")
            # plt.title("Load growth of the community")
            plt.savefig(
                os.path.join(figures_directory, "clean_water_load_growth.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the average clean-water load breakdown by load type over the first
            # year.
            domestic_demand = np.nanmean(
                np.asarray(
                    total_cw_load[0:HOURS_PER_YEAR][DemandType.DOMESTIC.value]
                ).reshape(
                    (365, 24),
                ),
                axis=0,
            )
            commercial_demand = np.nanmean(
                np.asarray(
                    total_cw_load[0:HOURS_PER_YEAR][DemandType.COMMERCIAL.value]
                ).reshape(
                    (365, 24),
                ),
                axis=0,
            )
            public_demand = np.nanmean(
                np.asarray(
                    total_cw_load[0:HOURS_PER_YEAR][DemandType.PUBLIC.value]
                ).reshape(
                    (365, 24),
                ),
                axis=0,
            )
            total_demand = np.nanmean(
                np.asarray(np.sum(total_cw_load[0:HOURS_PER_YEAR], axis=1)).reshape(
                    (365, 24),
                ),
                axis=0,
            )

            plt.plot(
                domestic_demand,
                label=DemandType.DOMESTIC.value,
            )
            plt.plot(
                commercial_demand,
                label=DemandType.COMMERCIAL.value,
            )
            plt.plot(
                public_demand,
                label=DemandType.PUBLIC.value,
            )
            plt.plot(
                total_demand,
                "--",
                label="total",
            )
            plt.legend(loc="upper right")
            plt.xticks([entry for entry in (range(0, 23, 4))])
            plt.xlabel("Hour of simulation")
            plt.ylabel("Clean-water demand / litres/hour")
            # plt.title(
            #     f"Average drinking water load profile of the community during the first year"
            # )
            plt.savefig(
                os.path.join(figures_directory, "clean_water_demands_yearly.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Water supply and demand on an average day.
            total_supplied = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.TOTAL_CW_SUPPLIED.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            total_used = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.TOTAL_CW_CONSUMED.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            backup_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.CLEAN_WATER_FROM_PRIORITISATION.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            conventional_drinking_water = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.CLEAN_WATER_FROM_CONVENTIONAL_SOURCES.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            excess_power_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.CLEAN_WATER_FROM_EXCESS_ELECTRICITY.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            renewable_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.RENEWABLE_CW_USED_DIRECTLY
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            renewable_cw_produced = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            storage_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.CLEAN_WATER_FROM_STORAGE.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            tank_storage = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.CW_TANK_STORAGE_PROFILE.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            total_cw_load = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.TOTAL_CW_LOAD.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            unmet_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.UNMET_CLEAN_WATER
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )

            plt.plot(total_used, "--", label="Total used", zorder=1)
            plt.plot(backup_clean_water, label="Backup desalination", zorder=2)
            plt.plot(
                conventional_drinking_water, label="Conventional sources", zorder=3
            )
            plt.plot(
                excess_power_clean_water, label="Excess power desalination", zorder=4
            )
            plt.plot(renewable_clean_water, label="PV-D direct use", zorder=5)
            plt.plot(renewable_cw_produced, "--", label="PV-D output", zorder=6)
            plt.plot(storage_clean_water, label="Storage", zorder=7)
            plt.plot(tank_storage, "--", label="Water held in tanks", zorder=8)
            plt.plot(unmet_clean_water, label="Unmet", zorder=9)
            plt.plot(total_cw_load, "--", label="Total load", zorder=10)
            plt.plot(total_supplied, "--", label="Total supplied", zorder=11)
            plt.legend()
            plt.xlim(0, 23)
            plt.xticks(range(0, 24, 1))
            plt.xlabel("Hour of day")
            plt.ylabel("Clean-water usage / litres/hour")
            # plt.title("Water supply and demand on an average day")
            plt.savefig(
                os.path.join(figures_directory, "clean_water_use_on_average_day.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Water supply and demand on an average July day.
            total_supplied = np.nanmean(
                np.reshape(
                    simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                        ColumnHeader.TOTAL_CW_SUPPLIED.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            total_used = np.nanmean(
                np.reshape(
                    simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                        ColumnHeader.TOTAL_CW_CONSUMED.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            backup_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                        ColumnHeader.CLEAN_WATER_FROM_PRIORITISATION.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            conventional_drinking_water = np.nanmean(
                np.reshape(
                    simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                        ColumnHeader.CLEAN_WATER_FROM_CONVENTIONAL_SOURCES.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            excess_power_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                        ColumnHeader.CLEAN_WATER_FROM_EXCESS_ELECTRICITY.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            renewable_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                        ColumnHeader.RENEWABLE_CW_USED_DIRECTLY
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            renewable_cw_produced = np.nanmean(
                np.reshape(
                    simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                        ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            storage_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                        ColumnHeader.CLEAN_WATER_FROM_STORAGE.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            tank_storage = np.nanmean(
                np.reshape(
                    simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                        ColumnHeader.CW_TANK_STORAGE_PROFILE.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            total_cw_load = np.nanmean(
                np.reshape(
                    simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                        ColumnHeader.TOTAL_CW_LOAD.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            unmet_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                        ColumnHeader.UNMET_CLEAN_WATER
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )

            plt.plot(total_used, "--", label="Total used", zorder=1)
            plt.plot(backup_clean_water, label="Backup desalination", zorder=2)
            plt.plot(
                conventional_drinking_water, label="Conventional sources", zorder=3
            )
            plt.plot(
                excess_power_clean_water, label="Excess power desalination", zorder=4
            )
            plt.plot(renewable_clean_water, label="PV-D direct use", zorder=5)
            plt.plot(renewable_cw_produced, "--", label="PV-D output", zorder=6)
            plt.plot(storage_clean_water, label="Storage", zorder=7)
            plt.plot(tank_storage, "--", label="Water held in tanks", zorder=8)
            plt.plot(unmet_clean_water, label="Unmet", zorder=9)
            plt.plot(total_cw_load, "--", label="Total load", zorder=10)
            plt.plot(total_supplied, "--", label="Total supplied", zorder=11)
            plt.legend()
            plt.xlim(0, 23)
            plt.xticks(range(0, 24, 1))
            plt.xlabel("Hour of day")
            plt.ylabel("Clean-water usage / litres/hour")
            # plt.title("Water supply and demand on an average July day")
            plt.savefig(
                os.path.join(
                    figures_directory, "clean_water_use_on_average_july_day.png"
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            plt.plot(excess_power_clean_water, label="PV-RO using excess PV", zorder=1)
            plt.plot(renewable_clean_water, label="PV-D direct use", zorder=2)
            plt.plot(storage_clean_water, label="Storage", zorder=3)
            plt.plot(tank_storage, "--", label="Water held in tanks", zorder=4)
            plt.plot(unmet_clean_water, label="Unmet", zorder=5)
            plt.plot(total_cw_load, "--", label="Total load", zorder=6)
            plt.legend()
            plt.xlim(0, 23)
            plt.xticks(range(0, 24, 1))
            plt.xlabel("Hour of day")
            plt.ylabel("Clean-water usage / litres/hour")
            # plt.title("Water supply and demand on an average July day")
            plt.savefig(
                os.path.join(
                    figures_directory,
                    "clean_water_use_on_average_july_day_reduced_plot.png",
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            plt.plot(renewable_clean_water, label="PV-D direct use", zorder=1)
            plt.plot(renewable_cw_produced, "--", label="PV-D output", zorder=2)
            plt.plot(tank_storage, "--", label="Water held in tanks", zorder=3)
            plt.plot(unmet_clean_water, label="Unmet", zorder=9)
            plt.plot(total_cw_load, "--", label="Total load", zorder=4)
            plt.legend()
            plt.xlim(0, 23)
            plt.xticks(range(0, 24, 1))
            plt.xlabel("Hour of day")
            plt.ylabel("Clean-water usage / litres/hour")
            # plt.title(
            #     "Output from the thermal desalination plant on an average July day"
            # )
            plt.savefig(
                os.path.join(
                    figures_directory,
                    "thermal_desal_cw_on_average_july_day.png",
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Water supply and demand on an average January day.
            total_supplied = np.nanmean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        ColumnHeader.TOTAL_CW_SUPPLIED.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            total_used = np.nanmean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        ColumnHeader.TOTAL_CW_CONSUMED.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            backup_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        ColumnHeader.CLEAN_WATER_FROM_PRIORITISATION.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            conventional_drinking_water = np.nanmean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        ColumnHeader.CLEAN_WATER_FROM_CONVENTIONAL_SOURCES.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            excess_power_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        ColumnHeader.CLEAN_WATER_FROM_EXCESS_ELECTRICITY.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            renewable_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        ColumnHeader.RENEWABLE_CW_USED_DIRECTLY
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            renewable_cw_produced = np.nanmean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            storage_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        ColumnHeader.CLEAN_WATER_FROM_STORAGE.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            tank_storage = np.nanmean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        ColumnHeader.CW_TANK_STORAGE_PROFILE.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            total_cw_load = np.nanmean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        ColumnHeader.TOTAL_CW_LOAD.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            unmet_clean_water = np.nanmean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        ColumnHeader.UNMET_CLEAN_WATER
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )

            plt.plot(total_used, "--", label="Total used", zorder=1)
            plt.plot(backup_clean_water, label="Backup desalination", zorder=2)
            plt.plot(
                conventional_drinking_water, label="Conventional sources", zorder=2
            )
            plt.plot(
                excess_power_clean_water, label="Excess power desalination", zorder=3
            )
            plt.plot(renewable_clean_water, label="PV-D direct use", zorder=4)
            plt.plot(renewable_cw_produced, "--", label="PV-D output", zorder=5)
            plt.plot(storage_clean_water, label="Storage", zorder=6)
            plt.plot(tank_storage, "--", label="Water held in tanks", zorder=7)
            plt.plot(unmet_clean_water, label="Unmet", zorder=8)
            plt.plot(total_cw_load, "--", label="Total load", zorder=9)
            plt.plot(total_supplied, "--", label="Total supplied", zorder=10)
            plt.legend()
            plt.xlim(0, 23)
            plt.xticks(range(0, 24, 1))
            plt.xlabel("Hour of day")
            plt.ylabel("Clean-water usage / litres/hour")
            # plt.title("Water supply and demand on an January average day")
            plt.savefig(
                os.path.join(
                    figures_directory, "clean_water_use_on_average_january_day.png"
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Water supply and demand on the first day.
            backup = simulation_output.iloc[0:24][
                ColumnHeader.CLEAN_WATER_FROM_PRIORITISATION.value
            ]
            conventional = simulation_output.iloc[0:24][
                ColumnHeader.CLEAN_WATER_FROM_CONVENTIONAL_SOURCES.value
            ]
            excess = simulation_output.iloc[0:24][
                ColumnHeader.CLEAN_WATER_FROM_EXCESS_ELECTRICITY.value
            ]
            renewable = simulation_output.iloc[0:24][
                ColumnHeader.RENEWABLE_CW_USED_DIRECTLY
            ]
            renewable_produced = simulation_output.iloc[0:24][
                ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value
            ]
            storage = simulation_output.iloc[0:24][
                ColumnHeader.CLEAN_WATER_FROM_STORAGE.value
            ]
            tank_storage = simulation_output.iloc[0:24][
                ColumnHeader.CW_TANK_STORAGE_PROFILE.value
            ]
            total_load = simulation_output.iloc[0:24][ColumnHeader.TOTAL_CW_LOAD.value]
            total_used = simulation_output.iloc[0:24][
                ColumnHeader.TOTAL_CW_SUPPLIED.value
            ]
            unmet_clean_water = simulation_output.iloc[0:24][
                ColumnHeader.UNMET_CLEAN_WATER
            ]

            plt.plot(total_used, "--", label="Total used", zorder=1)
            plt.plot(backup, label="Backup desalination", zorder=2)
            plt.plot(conventional, label="Conventional sources", zorder=3)
            plt.plot(excess, label="Excess minigrid power", zorder=4)
            plt.plot(renewable, label="PV-D direct use", zorder=5)
            plt.plot(renewable_produced, "--", label="PV-D output", zorder=6)
            plt.plot(storage, label="Storage", zorder=7)
            plt.plot(tank_storage, "--", label="Water held in tanks", zorder=8)
            plt.plot(unmet_clean_water, label="Unmet", zorder=9)
            plt.plot(total_load, "--", label="Total load", zorder=10)
            plt.legend()
            plt.xlim(0, 23)
            plt.xticks(range(0, 24, 1))
            plt.xlabel("Hour of day")
            plt.ylabel("Clean-water usage / litres/hour")
            # plt.title("Water supply and demand on the first day")
            plt.savefig(
                os.path.join(figures_directory, "clean_water_use_on_first_day.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            backup = simulation_output.iloc[0:48][
                ColumnHeader.CLEAN_WATER_FROM_PRIORITISATION.value
            ]
            excess = simulation_output.iloc[0:48][
                ColumnHeader.CLEAN_WATER_FROM_EXCESS_ELECTRICITY.value
            ]
            renewable = simulation_output.iloc[0:48][
                ColumnHeader.RENEWABLE_CW_USED_DIRECTLY
            ]
            renewable_produced = simulation_output.iloc[0:48][
                ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value
            ]
            storage = simulation_output.iloc[0:48][
                ColumnHeader.CLEAN_WATER_FROM_STORAGE.value
            ]
            tank_storage = simulation_output.iloc[0:48][
                ColumnHeader.CW_TANK_STORAGE_PROFILE.value
            ]
            total_load = simulation_output.iloc[0:48][ColumnHeader.TOTAL_CW_LOAD.value]
            total_used = simulation_output.iloc[0:48][
                ColumnHeader.TOTAL_CW_SUPPLIED.value
            ]
            unmet_clean_water = simulation_output.iloc[0:48][
                ColumnHeader.UNMET_CLEAN_WATER
            ]

            plt.plot(total_used, "--", label="Total used", zorder=1)
            plt.plot(backup, label="Backup desalination", zorder=2)
            plt.plot(excess, label="Excess minigrid power", zorder=3)
            plt.plot(renewable, label="PV-D direct use", zorder=4)
            plt.plot(renewable_produced, label="PV-D output", zorder=4)
            plt.plot(storage, label="Storage", zorder=5)
            plt.plot(tank_storage, "--", label="Water held in tanks", zorder=6)
            plt.plot(unmet_clean_water, label="Unmet", zorder=7)
            plt.plot(total_load, "--", label="Total load", zorder=8)
            plt.legend()
            plt.xlim(0, 47)
            plt.xticks(range(0, 48, 1))
            plt.xlabel("Hour of day")
            plt.ylabel("Clean-water usage / litres/hour")
            # plt.title("Water supply and demand in the first 48 hours")
            plt.savefig(
                os.path.join(
                    figures_directory, "clean_water_use_in_first_48_hours.png"
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # blackouts = np.nanmean(
            #     np.reshape(
            #         simulation_output[0:HOURS_PER_YEAR][
            #             "Water supply blackouts"
            #         ].values,
            #         (365, 24),
            #     ),
            #     axis=0,
            # )
            # direct_electric_supply = np.nanmean(
            #     np.reshape(
            #         simulation_output[0:HOURS_PER_YEAR][
            #             "Water supplied by direct electricity (l)"
            #         ].values
            #         > 0,
            #         (365, 24),
            #     ),
            #     axis=0,
            # )

            # plt.plot(blackouts, label=ColumnHeader.BLACKOUTS.value)
            # plt.plot(direct_electric_supply, label="Direct electric")
            # plt.legend()
            # plt.xlim(0, 23)
            # plt.xticks(range(0, 24, 1))
            # plt.ylim(0, 1)
            # plt.yticks(np.arange(0, 1.1, 0.25))
            # plt.xlabel("Hour of day")
            # plt.ylabel("Probability")
            # # plt.title("Clean-water availability on an average day")
            # plt.savefig(
            #     os.path.join(
            #         figures_directory, "clean_water_avilability_on_average_day.png"
            #     ),
            #     transparent=True,
            # )
            # plt.close()
            # pbar.update(1)

            clean_water_power_consumed = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.POWER_CONSUMED_BY_DESALINATION.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            dumped_power = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.DUMPED_ELECTRICITY.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            electric_power_supplied = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.POWER_CONSUMED_BY_ELECTRIC_DEVICES.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            surplus_power_consumed = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.EXCESS_POWER_CONSUMED_BY_DESALINATION.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            total_power_supplied = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.TOTAL_ELECTRICITY_CONSUMED.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )

            plt.plot(clean_water_power_consumed, label="Clean-water via conversion")
            plt.plot(dumped_power, label="Unused dumped energy")
            plt.plot(electric_power_supplied, label="Electric devices")
            plt.plot(
                surplus_power_consumed,
                label="Clean water via dumped energy",
            )
            if cw_pvt:
                thermal_desalination_energy = np.nanmean(
                    np.reshape(
                        simulation_output[0:HOURS_PER_YEAR][
                            ColumnHeader.POWER_CONSUMED_BY_THERMAL_DESALINATION.value
                        ].values,
                        (365, 24),
                    ),
                    axis=0,
                )
                plt.plot(
                    thermal_desalination_energy,
                    label="Thermal desaln electricity consumption",
                )

            plt.plot(total_power_supplied, "--", label="Total load")
            plt.legend()
            plt.xlim(0, 23)
            plt.xticks(range(0, 24, 1))
            plt.xlabel("Hour of day")
            plt.ylabel("Power consumption / kWh")
            # plt.title("Electriciy use by supply/device type on an average day")
            plt.savefig(
                os.path.join(
                    figures_directory, "cw_electricity_use_by_supply_type.png"
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the seasonal variation in clean-water supply sources.
            backup_water = np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.CLEAN_WATER_FROM_PRIORITISATION.value
                ].values
                / 1000,
                (365, 24),
            )
            conventional_water = np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.CLEAN_WATER_FROM_CONVENTIONAL_SOURCES.value
                ].values
                / 1000,
                (365, 24),
            )
            excess_pv_water = np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.CLEAN_WATER_FROM_EXCESS_ELECTRICITY.value
                ].values
                / 1000,
                (365, 24),
            )
            storage_water = np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.CLEAN_WATER_FROM_STORAGE.value
                ].values
                / 1000,
                (365, 24),
            )
            renewable_water = np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.RENEWABLE_CW_USED_DIRECTLY
                ].values
                / 1000,
                (365, 24),
            )
            unmet_water = np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.UNMET_CLEAN_WATER
                ].values
                / 1000,
                (365, 24),
            )

            fig, ([ax1, ax2, ax3], [ax4, ax5, ax6]) = plt.subplots(
                2, 3
            )  # ,sharex=True, sharey=True)

            # Renewably-produced clean-water heatmap.
            sns.heatmap(
                renewable_water,
                vmin=0.0,
                vmax=renewable_water.max(),
                cmap="Blues",
                cbar=True,
                ax=ax1,
            )
            ax1.set(
                xticks=range(0, 25, 6),
                xticklabels=range(0, 25, 6),
                yticks=range(0, 365, 60),
                yticklabels=range(0, 365, 60),
                xlabel="Hour of day",
                ylabel="Day of year",
                title="PV-D/T",
            )

            # Heatmap of water produced through excess renewable electricity.
            sns.heatmap(
                excess_pv_water,
                vmin=0.0,
                vmax=excess_pv_water.max(),
                cmap="Reds",
                cbar=True,
                ax=ax2,
            )
            ax2.set(
                xticks=range(0, 25, 6),
                xticklabels=range(0, 25, 6),
                yticks=range(0, 365, 60),
                yticklabels=range(0, 365, 60),
                xlabel="Hour of day",
                ylabel="Day of year",
                title="Excess PV",
            )

            # Heatmap of demand met through storage.
            sns.heatmap(
                storage_water,
                vmin=0.0,
                vmax=storage_water.max(),
                cmap="Greens",
                cbar=True,
                ax=ax3,
            )
            ax3.set(
                xticks=range(0, 25, 6),
                xticklabels=range(0, 25, 6),
                yticks=range(0, 365, 60),
                yticklabels=range(0, 365, 60),
                xlabel="Hour of day",
                ylabel="Day of year",
                title="Storage",
            )

            # Heatmap of water produced through meeting the demand by running diesel
            # etc.
            sns.heatmap(
                backup_water,
                vmin=0.0,
                vmax=backup_water.max(),
                cmap="Oranges",
                cbar=True,
                ax=ax4,
            )
            ax4.set(
                xticks=range(0, 25, 6),
                xticklabels=range(0, 25, 6),
                yticks=range(0, 365, 60),
                yticklabels=range(0, 365, 60),
                xlabel="Hour of day",
                ylabel="Day of year",
                title="Backup",
            )

            # Heatmap of demand met through conventional means.
            sns.heatmap(
                conventional_water,
                vmin=0.0,
                vmax=conventional_water.max(),
                cmap="Purples",
                cbar=True,
                ax=ax5,
            )
            ax5.set(
                xticks=range(0, 25, 6),
                xticklabels=range(0, 25, 6),
                yticks=range(0, 365, 60),
                yticklabels=range(0, 365, 60),
                xlabel="Hour of day",
                ylabel="Day of year",
                title="Conventional",
            )

            # Heatmap of unmet clean-water demand.
            sns.heatmap(
                unmet_water,
                vmin=0.0,
                vmax=unmet_water.max(),
                cmap="Greys",
                cbar=True,
                ax=ax6,
            )
            ax6.set(
                xticks=range(0, 25, 6),
                xticklabels=range(0, 25, 6),
                yticks=range(0, 365, 60),
                yticklabels=range(0, 365, 60),
                xlabel="Hour of day",
                ylabel="Day of year",
                title="Unmet",
            )

            # Adjust the positioning of the plots
            # ax4.set_position([0.24, 0.125, 0.228, 0.343])
            # ax5.set_position([0.55, 0.125, 0.228, 0.343])

            plt.tight_layout()
            fig.suptitle("Water from different sources (tonnes)")
            fig.subplots_adjust(top=0.87)
            plt.xticks(rotation=0)
            plt.savefig(
                os.path.join(figures_directory, "seasonal_water_supply_variations.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close(fig)
            pbar.update(1)

            if cw_pvt:
                # Plot the first year of PV-T generation as a heatmap.
                pvt_electricity_supplied_per_unit = simulation_output[0:HOURS_PER_YEAR][
                    ColumnHeader.CW_PVT_ELECTRICITY_SUPPLIED_PER_KWP.value
                ]
                reshaped_data = np.reshape(
                    pvt_electricity_supplied_per_unit.values, (365, 24)
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
                    title="Electric output per kWp of PV-T capacity",
                )
                plt.xticks(rotation=0)
                plt.tight_layout()
                plt.savefig(
                    os.path.join(figures_directory, "pv_t_electric_output_hetamap.png"),
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
                # plt.title("Daily electric energy generation of 1 kWp of PV-T capacity")
                plt.savefig(
                    os.path.join(figures_directory, "pv_t_electric_output_yearly.png"),
                    transparent=True,
                )
                plt.close()
                pbar.update(1)

                # Plot the daily collector output temperature
                fig, ax1 = plt.subplots()
                collector_output_temperature_january = simulation_output.iloc[0:24][
                    ColumnHeader.CW_PVT_OUTPUT_TEMPERATURE.value
                ]
                # collector_output_temperature_march = simulation_output.iloc[
                #     HOURS_UNTIL[3] : HOURS_UNTIL[3] + 24
                # ][ColumnHeader.CW_PVT_OUTPUT_TEMPERATURE.value]
                # collector_output_temperature_may = simulation_output.iloc[
                #     HOURS_UNTIL[5] : HOURS_UNTIL[5] + 24
                # ][ColumnHeader.CW_PVT_OUTPUT_TEMPERATURE.value]
                collector_output_temperature_july = simulation_output.iloc[
                    HOURS_UNTIL[7] : HOURS_UNTIL[7] + 24
                ][ColumnHeader.CW_PVT_OUTPUT_TEMPERATURE.value]

                buffer_tank_temperature_january = simulation_output.iloc[0:24][
                    ColumnHeader.BUFFER_TANK_TEMPERATURE.value
                ]
                # buffer_tank_temperature_march = simulation_output.iloc[
                #     HOURS_UNTIL[3] : HOURS_UNTIL[3] + 24
                # ][ColumnHeader.BUFFER_TANK_TEMPERATURE.value]
                # buffer_tank_temperature_may = simulation_output.iloc[
                #     HOURS_UNTIL[5] : HOURS_UNTIL[5] + 24
                # ][ColumnHeader.BUFFER_TANK_TEMPERATURE.value]
                buffer_tank_temperature_july = simulation_output.iloc[
                    HOURS_UNTIL[7] : HOURS_UNTIL[7] + 24
                ][ColumnHeader.BUFFER_TANK_TEMPERATURE.value]

                volume_supplied_january = simulation_output.iloc[0:24][
                    ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value
                ]
                # volume_supplied_march = simulation_output.iloc[
                #     HOURS_UNTIL[3] : HOURS_UNTIL[3] + 24
                # ][ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value]
                # volume_supplied_may = simulation_output.iloc[
                #     HOURS_UNTIL[5] : HOURS_UNTIL[5] + 24
                # ][ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value]
                volume_supplied_july = simulation_output.iloc[
                    HOURS_UNTIL[7] : HOURS_UNTIL[7] + 24
                ][ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value]

                ax1.plot(
                    collector_output_temperature_january.values,
                    label="january pv-t output temp.",
                )
                # ax1.plot(collector_output_temperature_march.values, label="march pv-t output temp.")
                # ax1.plot(collector_output_temperature_may.values, label="may pv-t output temp.")
                ax1.plot(
                    collector_output_temperature_july.values,
                    label="july pv-t output temp.",
                )

                ax1.plot(
                    buffer_tank_temperature_january.values,
                    ":",
                    label="january tank temp.",
                    color="C0",
                )
                # ax1.plot(buffer_tank_temperature_march.values, label="march tank temp.")
                # ax1.plot(buffer_tank_temperature_may.values, label="may tank temp.")
                ax1.plot(
                    buffer_tank_temperature_july.values,
                    ":",
                    label="july tank temp.",
                    color="C1",
                )

                ax1.legend(loc="upper left")

                ax2 = ax1.twinx()
                ax2.plot(volume_supplied_january.values, "--", label="january output")
                # ax2.plot(volume_supplied_march.values, "--", label="march output")
                # ax2.plot(volume_supplied_may.values, "--", label="may output")
                ax2.plot(volume_supplied_july.values, "--", label="july output")
                ax2.legend(loc="upper right")

                plt.xlim(0, 23)
                plt.xlabel("Hour of day")
                ax1.set_ylabel("Collector output temperature / degC")
                ax2.set_ylabel("Volume thermally desalinated / litres")
                # plt.title(
                #     "Collector output temprature on the first day of select months"
                # )
                plt.savefig(
                    os.path.join(
                        figures_directory,
                        "clean_water_collector_output_temperature_on_first_month_days.png",
                    ),
                    transparent=True,
                )
                plt.close(fig)
                pbar.update(1)

                # Plot the average collector output temperature
                fig, ax1 = plt.subplots()
                collector_output_temperature_january = np.nanmean(
                    np.reshape(
                        simulation_output[0 : 31 * 24][
                            ColumnHeader.CW_PVT_OUTPUT_TEMPERATURE.value
                        ].values,
                        (31, 24),
                    ),
                    axis=0,
                )
                collector_output_temperature_march = np.nanmean(
                    np.reshape(
                        simulation_output[HOURS_UNTIL[3] : HOURS_UNTIL[3] + 31 * 24][
                            ColumnHeader.CW_PVT_OUTPUT_TEMPERATURE.value
                        ].values,
                        (31, 24),
                    ),
                    axis=0,
                )
                collector_output_temperature_may = np.nanmean(
                    np.reshape(
                        simulation_output[HOURS_UNTIL[5] : HOURS_UNTIL[5] + 31 * 24][
                            ColumnHeader.CW_PVT_OUTPUT_TEMPERATURE.value
                        ].values,
                        (31, 24),
                    ),
                    axis=0,
                )
                collector_output_temperature_july = np.nanmean(
                    np.reshape(
                        simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                            ColumnHeader.CW_PVT_OUTPUT_TEMPERATURE.value
                        ].values,
                        (31, 24),
                    ),
                    axis=0,
                )

                buffer_tank_temperature_january = np.nanmean(
                    np.reshape(
                        simulation_output[0 : 31 * 24][
                            ColumnHeader.BUFFER_TANK_TEMPERATURE.value
                        ].values,
                        (31, 24),
                    ),
                    axis=0,
                )
                buffer_tank_temperature_march = np.nanmean(
                    np.reshape(
                        simulation_output[HOURS_UNTIL[3] : HOURS_UNTIL[3] + 31 * 24][
                            ColumnHeader.BUFFER_TANK_TEMPERATURE.value
                        ].values,
                        (31, 24),
                    ),
                    axis=0,
                )
                buffer_tank_temperature_may = np.nanmean(
                    np.reshape(
                        simulation_output[HOURS_UNTIL[5] : HOURS_UNTIL[5] + 31 * 24][
                            ColumnHeader.BUFFER_TANK_TEMPERATURE.value
                        ].values,
                        (31, 24),
                    ),
                    axis=0,
                )
                buffer_tank_temperature_july = np.nanmean(
                    np.reshape(
                        simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                            ColumnHeader.BUFFER_TANK_TEMPERATURE.value
                        ].values,
                        (31, 24),
                    ),
                    axis=0,
                )

                # Plot the average collector output temperature
                volume_supplied_january = np.nanmean(
                    np.reshape(
                        simulation_output[0 : 31 * 24][
                            ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value
                        ].values,
                        (31, 24),
                    ),
                    axis=0,
                )
                volume_supplied_march = np.nanmean(
                    np.reshape(
                        simulation_output[HOURS_UNTIL[3] : HOURS_UNTIL[3] + 31 * 24][
                            ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value
                        ].values,
                        (31, 24),
                    ),
                    axis=0,
                )
                volume_supplied_may = np.nanmean(
                    np.reshape(
                        simulation_output[HOURS_UNTIL[5] : HOURS_UNTIL[5] + 31 * 24][
                            ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value
                        ].values,
                        (31, 24),
                    ),
                    axis=0,
                )
                volume_supplied_july = np.nanmean(
                    np.reshape(
                        simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                            ColumnHeader.CLEAN_WATER_FROM_THERMAL_RENEWABLES.value
                        ].values,
                        (31, 24),
                    ),
                    axis=0,
                )

                ax1.plot(
                    collector_output_temperature_january,
                    label="january collector output temp.",
                )
                # ax1.plot(collector_output_temperature_march, label="march collector output temp.")
                # ax1.plot(collector_output_temperature_may, label="may collector output temp.")
                ax1.plot(
                    collector_output_temperature_july,
                    label="july collector output temp.",
                )
                ax1.plot(
                    buffer_tank_temperature_january,
                    ":",
                    label="january tank temp.",
                    color="C0",
                )
                # ax1.plot(buffer_tank_temperature_march, ":", label="march tank temp.", color="C2")
                # ax1.plot(buffer_tank_temperature_may, ":", label="may tank temp.", color="C3")
                ax1.plot(
                    buffer_tank_temperature_july,
                    ":",
                    label="july tank temp.",
                    color="C1",
                )
                ax1.legend(loc="upper left")

                ax2 = ax1.twinx()
                ax2.plot(volume_supplied_january, "--", label="january output")
                # ax2.plot(volume_supplied_march, "--", label="march output")
                # ax2.plot(volume_supplied_may, "--", label="may output")
                ax2.plot(volume_supplied_july, "--", label="july output")
                ax2.legend(loc="upper right")

                plt.xlim(0, 23)
                plt.xlabel("Hour of day")
                ax1.set_ylabel("Collector output temperature / degC")
                ax2.set_ylabel("Volume thermally desalinated / litres")
                # plt.title("Collector output temprature on an average seasonal days")
                plt.savefig(
                    os.path.join(
                        figures_directory,
                        "clean_water_collector_output_temperature_on_average_month_days.png",
                    ),
                    transparent=True,
                )
                plt.close(fig)
                pbar.update(1)

        if initial_hw_hourly_loads is not None:
            # Plot the initial hot-water load of each device.
            fig, ax = plt.subplots()
            cumulative_load = 0
            for device, load in sorted(initial_hw_hourly_loads.items()):
                ax.bar(range(len(load)), load[0], label=device, bottom=cumulative_load)

                if isinstance(cumulative_load, int) and cumulative_load == 0:
                    cumulative_load = load[0]
                    continue
                cumulative_load += load[0]

            ax.set_xlabel("Hour of simulation")
            ax.set_ylabel("Device load / litres/hour")
            # ax.set_title("Hot water demand of each device")
            ax.legend()
            plt.savefig(
                os.path.join(figures_directory, "hot_water_device_loads.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close(fig)
            pbar.update(1)

            # Plot the average hot-water load of each device for the cut off period.
            fig, ax = plt.subplots()
            cumulative_load = 0
            for device, load in sorted(initial_hw_hourly_loads.items()):
                average_load = np.nanmean(
                    np.asarray(load[0:CUT_OFF_TIME]).reshape(
                        (CUT_OFF_TIME // 24, 24),
                    ),
                    axis=0,
                )
                ax.bar(range(24), average_load, label=device, bottom=cumulative_load)

                if isinstance(cumulative_load, int) and cumulative_load == 0:
                    cumulative_load = average_load
                    continue
                cumulative_load += average_load

            ax.set_xlabel("Hour of simulation")
            ax.set_ylabel("Device load / litres/hour")
            # ax.set_title(
            #     "Average hot water demand of each device over the first {} days.".format(
            #         CUT_OFF_TIME // 24
            #     )
            # )
            ax.legend()
            plt.savefig(
                os.path.join(figures_directory, "hot_water_device_loads_average.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close(fig)
            pbar.update(1)

            # Plot the clean-water load breakdown by load type.
            plt.plot(
                range(CUT_OFF_TIME),
                total_hw_load[0:CUT_OFF_TIME][DemandType.DOMESTIC.value],
                label=DemandType.DOMESTIC.value,
            )
            plt.plot(
                range(CUT_OFF_TIME),
                total_hw_load[0:CUT_OFF_TIME][DemandType.COMMERCIAL.value],
                label=DemandType.COMMERCIAL.value,
            )
            plt.plot(
                range(CUT_OFF_TIME),
                total_hw_load[0:CUT_OFF_TIME][DemandType.PUBLIC.value],
                label=DemandType.PUBLIC.value,
            )
            plt.plot(
                range(CUT_OFF_TIME),
                np.sum(total_hw_load[0:CUT_OFF_TIME], axis=1),
                "--",
                label="total",
            )
            plt.legend(loc="upper right")
            plt.xticks(
                [
                    entry
                    for entry in range(0, CUT_OFF_TIME - 1, min(4, CUT_OFF_TIME - 2))
                ]
            )
            plt.xlabel("Hour of simulation")
            plt.ylabel("Hot water demand / litres/hour")
            # plt.title(
            #     f"Hot-water load profile of the community for the first {CUT_OFF_TIME} hours"
            # )
            plt.savefig(
                os.path.join(figures_directory, "hot_water_demands.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close(fig)
            pbar.update(1)

            # Plot the annual variation of the clean-water demand.
            fig, axis = plt.subplots(1, 2, figsize=(8, 4))
            domestic_demand = 0.001 * np.sum(
                np.reshape(
                    total_hw_load[0:HOURS_PER_YEAR][DemandType.DOMESTIC.value].values,
                    (365, 24),
                ),
                axis=1,
            )
            commercial_demand = 0.001 * np.sum(
                np.reshape(
                    total_hw_load[0:HOURS_PER_YEAR][DemandType.COMMERCIAL.value].values,
                    (365, 24),
                ),
                axis=1,
            )
            public_demand = 0.001 * np.sum(
                np.reshape(
                    total_hw_load[0:HOURS_PER_YEAR][DemandType.PUBLIC.value].values,
                    (365, 24),
                ),
                axis=1,
            )
            total_demand = 0.001 * np.sum(
                np.reshape(
                    np.sum(total_hw_load[0:HOURS_PER_YEAR].values, axis=1),
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
                xlabel="Day of simulation period",
                ylabel="Load / m^3/day",
                title="Hot-water demand of each load type",
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
                xlabel="Day of simulation period",
                ylabel="Load / m^3/day",
                title="Total community hot-water demand",
            )
            plt.tight_layout()
            plt.savefig(
                os.path.join(
                    figures_directory, "hot_water_demand_annual_variation.png"
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close(fig)
            plt.clf()
            plt.close()
            pbar.update(1)

            # Plot the total seasonal variation as a stand-alone figure.
            plt.plot(
                range(365),
                pd.DataFrame(total_demand).rolling(5).mean(),
                "--",
                label="Total",
                color="red",
            )
            plt.plot(range(365), total_demand, "--", alpha=0.5, color="red")
            plt.legend(loc="best")
            plt.xticks(range(0, 366, 60))
            plt.xlabel("Day of simulation period")
            plt.ylabel("Load / m^3/day")
            # plt.title("Total community hot-water demand")
            plt.tight_layout()
            plt.savefig(
                os.path.join(
                    figures_directory, "hot_water_demand_total_annual_variation.png"
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the average hot-water load breakdown by load type over the first year
            domestic_demand = np.nanmean(
                np.asarray(
                    total_hw_load[0:HOURS_PER_YEAR][DemandType.DOMESTIC.value]
                ).reshape(
                    (365, 24),
                ),
                axis=0,
            )
            commercial_demand = np.nanmean(
                np.asarray(
                    total_hw_load[0:HOURS_PER_YEAR][DemandType.COMMERCIAL.value]
                ).reshape(
                    (365, 24),
                ),
                axis=0,
            )
            public_demand = np.nanmean(
                np.asarray(
                    total_hw_load[0:HOURS_PER_YEAR][DemandType.PUBLIC.value]
                ).reshape(
                    (365, 24),
                ),
                axis=0,
            )
            total_demand = np.nanmean(
                np.asarray(np.sum(total_hw_load[0:HOURS_PER_YEAR], axis=1)).reshape(
                    (365, 24),
                ),
                axis=0,
            )

            plt.plot(
                domestic_demand,
                label=DemandType.DOMESTIC.value,
            )
            plt.plot(
                commercial_demand,
                label=DemandType.COMMERCIAL.value,
            )
            plt.plot(
                public_demand,
                label=DemandType.PUBLIC.value,
            )
            plt.plot(
                total_demand,
                "--",
                label="total",
            )
            plt.legend(loc="upper right")
            plt.xticks([entry for entry in (range(0, 23, 4))])
            plt.xlabel("Hour of simulation")
            plt.ylabel("Hot-water demand / litres/hour")
            # plt.title(
            #     "Average DHW load profile of the community during the first simulation year"
            # )
            plt.savefig(
                os.path.join(figures_directory, "hot_water_demands_yearly.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the hot-water demand load growth over the simulation period.
            domestic_demand = np.sum(
                np.reshape(
                    0.001
                    * total_hw_load[0 : num_years * HOURS_PER_YEAR][
                        DemandType.DOMESTIC.value
                    ].values,
                    (num_years, HOURS_PER_YEAR),
                ),
                axis=1,
            )
            commercial_demand = np.sum(
                np.reshape(
                    0.001
                    * total_hw_load[0 : num_years * HOURS_PER_YEAR][
                        DemandType.COMMERCIAL.value
                    ].values,
                    (num_years, HOURS_PER_YEAR),
                ),
                axis=1,
            )
            public_demand = np.sum(
                np.reshape(
                    0.001
                    * total_hw_load[0 : num_years * HOURS_PER_YEAR][
                        DemandType.PUBLIC.value
                    ].values,
                    (num_years, HOURS_PER_YEAR),
                ),
                axis=1,
            )
            total_demand = np.sum(
                np.reshape(
                    np.sum(
                        0.001 * total_hw_load[0 : num_years * HOURS_PER_YEAR].values,
                        axis=1,
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
            plt.ylabel("Hot-water demand / Cubic meters/year")
            # plt.title("Load growth of the community")
            plt.savefig(
                os.path.join(figures_directory, "hot_water_load_growth.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the daily collector output temperature
            fig, ax1 = plt.subplots()
            collector_output_temperature_january = simulation_output.iloc[0:24][
                ColumnHeader.HW_PVT_OUTPUT_TEMPERATURE.value
            ]
            collector_output_temperature_march = simulation_output.iloc[
                HOURS_UNTIL[3] : HOURS_UNTIL[3] + 24
            ][ColumnHeader.HW_PVT_OUTPUT_TEMPERATURE.value]
            collector_output_temperature_may = simulation_output.iloc[
                HOURS_UNTIL[5] : HOURS_UNTIL[5] + 24
            ][ColumnHeader.HW_PVT_OUTPUT_TEMPERATURE.value]
            collector_output_temperature_july = simulation_output.iloc[
                HOURS_UNTIL[7] : HOURS_UNTIL[7] + 24
            ][ColumnHeader.HW_PVT_OUTPUT_TEMPERATURE.value]

            hot_water_tank_temperature_january = simulation_output.iloc[0:24][
                ColumnHeader.HW_TANK_TEMPERATURE.value
            ]
            hot_water_tank_temperature_march = simulation_output.iloc[
                HOURS_UNTIL[3] : HOURS_UNTIL[3] + 24
            ][ColumnHeader.HW_TANK_TEMPERATURE.value]
            hot_water_tank_temperature_may = simulation_output.iloc[
                HOURS_UNTIL[5] : HOURS_UNTIL[5] + 24
            ][ColumnHeader.HW_TANK_TEMPERATURE.value]
            hot_water_tank_temperature_july = simulation_output.iloc[
                HOURS_UNTIL[7] : HOURS_UNTIL[7] + 24
            ][ColumnHeader.HW_TANK_TEMPERATURE.value]

            renewable_fraction_january = simulation_output.iloc[0:24][
                ColumnHeader.HW_SOLAR_THERMAL_FRACTION.value
            ]
            renewable_fraction_march = simulation_output.iloc[
                HOURS_UNTIL[3] : HOURS_UNTIL[3] + 24
            ][ColumnHeader.HW_SOLAR_THERMAL_FRACTION.value]
            renewable_fraction_may = simulation_output.iloc[
                HOURS_UNTIL[5] : HOURS_UNTIL[5] + 24
            ][ColumnHeader.HW_SOLAR_THERMAL_FRACTION.value]
            renewable_fraction_july = simulation_output.iloc[
                HOURS_UNTIL[7] : HOURS_UNTIL[7] + 24
            ][ColumnHeader.HW_SOLAR_THERMAL_FRACTION.value]

            ax1.plot(
                collector_output_temperature_january.values,
                label="january pv-t output temp.",
            )
            # ax1.plot(collector_output_temperature_march.values, label="march pv-t output temp.")
            # ax1.plot(collector_output_temperature_may.values, label="may pv-t output temp.")
            ax1.plot(
                collector_output_temperature_july.values, label="july pv-t output temp."
            )

            ax1.plot(
                hot_water_tank_temperature_january.values,
                ":",
                label="january tank temp.",
                color="C0",
            )
            # ax1.plot(hot_water_tank_temperature_march.values, label="march tank temp.")
            # ax1.plot(hot_water_tank_temperature_may.values, label="may tank temp.")
            ax1.plot(
                hot_water_tank_temperature_july.values,
                ":",
                label="july tank temp.",
                color="C1",
            )

            ax1.legend(loc="upper left")

            # ax2 = ax1.twinx()
            # ax2.plot(
            #     renewable_fraction_january.values,
            #     "--",
            #     label="january renewables fraction",
            # )
            # # ax2.plot(
            # #     renewable_fraction_march.values, "--", label="march renewables fraction"
            # # )
            # # ax2.plot(
            # #     renewable_fraction_may.values, "--", label="may renewables fraction"
            # # )
            # ax2.plot(
            #     renewable_fraction_july.values, "--", label="july renewables fraction"
            # )
            # ax2.legend(loc="upper right")

            plt.xlim(0, 23)
            plt.xlabel("Hour of day")
            ax1.set_ylabel("Collector output temperature / degC")
            # ax2.set_ylabel("Fraction of demand covered renewably")
            # plt.title("Collector output temp. on the first day of select months")
            plt.savefig(
                os.path.join(
                    figures_directory,
                    "hot_water_collector_output_temperature_on_first_month_days.png",
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close(fig)
            pbar.update(1)

            fig, ax1 = plt.subplots()
            ax1.plot(
                collector_output_temperature_january.values,
                label="january pv-t output temp.",
            )
            # ax1.plot(collector_output_temperature_march.values, label="march pv-t output temp.")
            # ax1.plot(collector_output_temperature_may.values, label="may pv-t output temp.")
            ax1.plot(
                collector_output_temperature_july.values, label="july pv-t output temp."
            )

            ax1.plot(
                hot_water_tank_temperature_january.values,
                ":",
                label="january tank temp.",
                color="C0",
            )
            # ax1.plot(hot_water_tank_temperature_march.values, label="march tank temp.")
            # ax1.plot(hot_water_tank_temperature_may.values, label="may tank temp.")
            ax1.plot(
                hot_water_tank_temperature_july.values,
                ":",
                label="july tank temp.",
                color="C1",
            )

            ax1.legend(loc="upper left")

            ax2 = ax1.twinx()
            ax2.plot(
                renewable_fraction_january.values,
                "--",
                label="january renewables fraction",
            )
            # ax2.plot(
            #     renewable_fraction_march.values, "--", label="march renewables fraction"
            # )
            # ax2.plot(
            #     renewable_fraction_may.values, "--", label="may renewables fraction"
            # )
            ax2.plot(
                renewable_fraction_july.values, "--", label="july renewables fraction"
            )
            ax2.legend(loc="upper right")

            plt.xlim(0, 23)
            plt.xlabel("Hour of day")
            ax1.set_ylabel("Collector output temperature / degC")
            # ax2.set_ylabel("Fraction of demand covered renewably")
            # plt.title(
            #     "Collector output temp. on the first day of select months and "
            #     "renewable demand covered"
            # )
            plt.savefig(
                os.path.join(
                    figures_directory,
                    "hot_water_collector_output_temperature_on_first_month_days_with_renewable_fraction.png",
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close(fig)
            pbar.update(1)

            # Plot the average collector output temperature
            fig, ax1 = plt.subplots()
            collector_output_temperature_january = np.nanmean(
                np.reshape(
                    simulation_output[0 : 31 * 24][
                        ColumnHeader.HW_PVT_OUTPUT_TEMPERATURE.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            # collector_output_temperature_march = np.nanmean(
            #     np.reshape(
            #         simulation_output[HOURS_UNTIL[3] : HOURS_UNTIL[3] + 31 * 24][
            #             ColumnHeader.HW_PVT_OUTPUT_TEMPERATURE.value
            #         ].values,
            #         (31, 24),
            #     ),
            #     axis=0,
            # )
            # collector_output_temperature_may = np.nanmean(
            #     np.reshape(
            #         simulation_output[HOURS_UNTIL[5] : HOURS_UNTIL[5] + 31 * 24][
            #             ColumnHeader.HW_PVT_OUTPUT_TEMPERATURE.value
            #         ].values,
            #         (31, 24),
            #     ),
            #     axis=0,
            # )
            collector_output_temperature_july = np.nanmean(
                np.reshape(
                    simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                        ColumnHeader.HW_PVT_OUTPUT_TEMPERATURE.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )

            hot_water_tank_temperature_january = np.nanmean(
                np.reshape(
                    simulation_output[0 : 31 * 24][
                        ColumnHeader.HW_TANK_TEMPERATURE.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            # hot_water_tank_temperature_march = np.nanmean(
            #     np.reshape(
            #         simulation_output[HOURS_UNTIL[3] : HOURS_UNTIL[3] + 31 * 24][
            #             ColumnHeader.HW_TANK_TEMPERATURE.value
            #         ].values,
            #         (31, 24),
            #     ),
            #     axis=0,
            # )
            # hot_water_tank_temperature_may = np.nanmean(
            #     np.reshape(
            #         simulation_output[HOURS_UNTIL[5] : HOURS_UNTIL[5] + 31 * 24][
            #             ColumnHeader.HW_TANK_TEMPERATURE.value
            #         ].values,
            #         (31, 24),
            #     ),
            #     axis=0,
            # )
            hot_water_tank_temperature_july = np.nanmean(
                np.reshape(
                    simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                        ColumnHeader.HW_TANK_TEMPERATURE.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )

            # Plot the average collector output temperature
            renewable_fraction_january = np.nanmean(
                np.reshape(
                    simulation_output[0 : 31 * 24][
                        ColumnHeader.HW_SOLAR_THERMAL_FRACTION.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            # renewable_fraction_march = np.nanmean(
            #     np.reshape(
            #         simulation_output[HOURS_UNTIL[3] : HOURS_UNTIL[3] + 31 * 24][
            #             ColumnHeader.HW_SOLAR_THERMAL_FRACTION.value
            #         ].values,
            #         (31, 24),
            #     ),
            #     axis=0,
            # )
            # renewable_fraction_may = np.nanmean(
            #     np.reshape(
            #         simulation_output[HOURS_UNTIL[5] : HOURS_UNTIL[5] + 31 * 24][
            #             ColumnHeader.HW_SOLAR_THERMAL_FRACTION.value
            #         ].values,
            #         (31, 24),
            #     ),
            #     axis=0,
            # )
            renewable_fraction_july = np.nanmean(
                np.reshape(
                    simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                        ColumnHeader.HW_SOLAR_THERMAL_FRACTION.value
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )

            ax1.plot(
                collector_output_temperature_january,
                label="january collector output temp.",
            )
            # ax1.plot(collector_output_temperature_march, label="march collector output temp.")
            # ax1.plot(collector_output_temperature_may, label="may collector output temp.")
            ax1.plot(
                collector_output_temperature_july, label="july collector output temp."
            )
            ax1.plot(
                hot_water_tank_temperature_january,
                ":",
                label="january tank temp.",
                color="C0",
            )
            # ax1.plot(hot_water_tank_temperature_march, ":", label="march tank temp.", color="C2")
            # ax1.plot(hot_water_tank_temperature_may, ":", label="may tank temp.", color="C3")
            ax1.plot(
                hot_water_tank_temperature_july,
                ":",
                label="july tank temp.",
                color="C1",
            )
            ax1.legend(loc="upper left")

            plt.xlim(0, 23)
            plt.xlabel("Hour of day")
            ax1.set_ylabel("Collector output temperature / degC")
            # ax2.set_ylabel("Demand covered fraction through renewables.")
            # plt.title("Collector output temprature on an average seasonal days.")
            plt.savefig(
                os.path.join(
                    figures_directory,
                    "hot_water_collector_output_temperature_on_average_month_days.png",
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close(fig)
            pbar.update(1)

            fig, ax1 = plt.subplots()
            ax1.plot(
                collector_output_temperature_january,
                label="january collector output temp.",
            )
            # ax1.plot(collector_output_temperature_march, label="march collector output temp.")
            # ax1.plot(collector_output_temperature_may, label="may collector output temp.")
            ax1.plot(
                collector_output_temperature_july, label="july collector output temp."
            )
            ax1.plot(
                hot_water_tank_temperature_january,
                ":",
                label="january tank temp.",
                color="C0",
            )
            # ax1.plot(hot_water_tank_temperature_march, ":", label="march tank temp.", color="C2")
            # ax1.plot(hot_water_tank_temperature_may, ":", label="may tank temp.", color="C3")
            ax1.plot(
                hot_water_tank_temperature_july,
                ":",
                label="july tank temp.",
                color="C1",
            )
            ax1.legend(loc="upper left")

            ax2 = ax1.twinx()
            ax2.plot(
                renewable_fraction_january, "--", label="january renewables fraction"
            )
            # ax2.plot(renewable_fraction_march, "--", label="march renewables fraction")
            # ax2.plot(renewable_fraction_may, "--", label="may renewables fraction")
            ax2.plot(renewable_fraction_july, "--", label="july renewables fraction")
            ax2.legend(loc="upper right")

            plt.xlim(0, 23)
            plt.xlabel("Hour of day")
            ax1.set_ylabel("Collector output temperature / degC")
            # ax2.set_ylabel("Demand covered fraction through renewables.")
            # plt.title(
            #     "Collector output temprature on an average seasonal days and the demand covered."
            # )
            plt.savefig(
                os.path.join(
                    figures_directory,
                    "hot_water_collector_output_temperature_on_average_days_with_renewables_fraction.png",
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close(fig)
            pbar.update(1)

            hot_water_power_consumed = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.POWER_CONSUMED_BY_HOT_WATER.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            dumped_power = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.DUMPED_ELECTRICITY.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            electric_power_supplied = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.POWER_CONSUMED_BY_ELECTRIC_DEVICES.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            total_power_supplied = np.nanmean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        ColumnHeader.TOTAL_ELECTRICITY_CONSUMED.value
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )

            plt.plot(hot_water_power_consumed, label="Hot-water system")
            plt.plot(dumped_power, label="Unused dumped energy")
            plt.plot(electric_power_supplied, label="Electric devices")
            plt.plot(total_power_supplied, "--", label="Total load")
            plt.legend()
            plt.xlim(0, 23)
            plt.xticks(range(0, 24, 1))
            plt.xlabel("Hour of day")
            plt.ylabel("Power consumption / kWh")
            # plt.title("Electriciy use by supply/device type on an average day")
            plt.savefig(
                os.path.join(
                    figures_directory, "hot_water_electricity_use_by_supply_type.png"
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot key temperatures that characterise the PV-T system.
            collector_temperature_gain_july = np.nanmean(
                np.reshape(
                    (
                        simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                            ColumnHeader.HW_PVT_OUTPUT_TEMPERATURE.value
                        ]
                        - simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                            ColumnHeader.HW_PVT_INPUT_TEMPERATURE.value
                        ]
                    ).values,
                    (31, 24),
                ),
                axis=0,
            )
            collector_minus_tank_july = np.nanmean(
                np.reshape(
                    (
                        simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                            ColumnHeader.HW_PVT_OUTPUT_TEMPERATURE.value
                        ]
                        - simulation_output[HOURS_UNTIL[7] : HOURS_UNTIL[7] + 31 * 24][
                            ColumnHeader.HW_TANK_TEMPERATURE.value
                        ]
                    ).values,
                    (31, 24),
                ),
                axis=0,
            )

            fig, ax1 = plt.subplots()
            ax1.plot(collector_temperature_gain_july, label="T_c,out - T_c,in")
            ax1.plot(collector_minus_tank_july, label="T_c,out - T_tank")
            ax1.set_ylabel("Temperature / degC")
            ax1.legend(loc="upper left")

            ax2 = ax1.twinx()

            plt.xlim(0, 23)
            plt.xticks(range(0, 24, 1))
            plt.xlabel("Hour of day")
            # plt.title("PV-T in/out temperatures for an average July day")
            plt.savefig(
                os.path.join(
                    figures_directory, "hot_water_pvt_tank_temperature_july.png"
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close(fig)
            pbar.update(1)

            # Plot monthly renewable DHW fraction
            dhw_renewable_fraction: Dict[int:float] = {}
            dhw_renewable_fraction_daily: Dict[int : np.ndarray] = {}
            dhw_dc_fraction: Dict[int:float] = {}
            dhw_dc_fraction_daily: Dict[int : np.ndarray] = {}
            for month in range(1, 13):
                dhw_renewable_fraction[month] = np.nansum(
                    (
                        simulation_output[
                            HOURS_UNTIL[month] : HOURS_UNTIL[month] + 30 * 24
                        ][ColumnHeader.HW_SOLAR_THERMAL_FRACTION.value].values
                    )
                    * (
                        simulation_output[
                            HOURS_UNTIL[month] : HOURS_UNTIL[month] + 30 * 24
                        ][ColumnHeader.HW_TANK_OUTPUT.value].values
                    )
                ) / np.sum(
                    simulation_output[
                        HOURS_UNTIL[month] : HOURS_UNTIL[month] + 30 * 24
                    ][ColumnHeader.HW_TANK_OUTPUT.value].values
                )
                dhw_renewable_fraction_daily[month] = np.nansum(
                    np.reshape(
                        (
                            simulation_output[
                                HOURS_UNTIL[month] : HOURS_UNTIL[month] + 30 * 24
                            ][ColumnHeader.HW_SOLAR_THERMAL_FRACTION.value].values
                            * (
                                simulation_output[
                                    HOURS_UNTIL[month] : HOURS_UNTIL[month] + 30 * 24
                                ][ColumnHeader.HW_TANK_OUTPUT.value].values
                            )
                        )
                        / np.sum(
                            (
                                simulation_output[
                                    HOURS_UNTIL[month] : HOURS_UNTIL[month] + 30 * 24
                                ][ColumnHeader.HW_TANK_OUTPUT.value].values
                            )
                        ),
                        (30, 24),
                    ),
                    axis=0,
                )
                dhw_dc_fraction[month] = np.nanmean(
                    simulation_output[
                        HOURS_UNTIL[month] : HOURS_UNTIL[month] + 30 * 24
                    ][ColumnHeader.HW_VOL_DEMAND_COVERED.value].values
                )
                dhw_dc_fraction_daily[month] = np.nanmean(
                    np.reshape(
                        simulation_output[
                            HOURS_UNTIL[month] : HOURS_UNTIL[month] + 30 * 24
                        ][ColumnHeader.HW_VOL_DEMAND_COVERED.value].values,
                        (30, 24),
                    ),
                    axis=0,
                )

            # Plot the daily varying demand covered profiles.
            fig, ax1 = plt.subplots()
            ax2 = ax1.twinx()
            for key, value in dhw_renewable_fraction_daily.items():
                ax1.plot(range(24), value, label=f"month #{key}")

            for key, value in dhw_dc_fraction_daily.items():
                ax2.plot(range(24), value, "--", label=f"month #{key}")

            plt.xlim(0, 23)
            plt.xlabel("Hour of day")
            ax1.set_ylabel("Renewable DHW demand covered fraction")
            ax2.set_ylabel("Volumetric DHW demand covered fraction")
            # plt.title("Monthly averages of domestic demand covered fractions")
            plt.savefig(
                os.path.join(
                    figures_directory,
                    "hot_water_monthly_average_dc_fraction_daily.png",
                ),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close(fig)
            pbar.update(1)

            # Plot the monthly averages.
            plt.bar(
                [entry + 0.3 for entry in dhw_renewable_fraction.keys()],
                dhw_renewable_fraction.values(),
                width=0.35,
                align="center",
                label="CLOVER modelling",
            )
            plt.bar(
                [entry + 0.7 for entry in dhw_renewable_fraction.keys()],
                [
                    0.123,
                    0.22,
                    0.36,
                    0.488,
                    0.567,
                    0.589,
                    0.611,
                    0.648,
                    0.466,
                    0.34,
                    0.188,
                    0.123,
                ],
                width=0.35,
                align="center",
                label="Guarracino et al.",
            )

            plt.xlim(1, 13)
            plt.ylim(0, 1.0)
            plt.xlabel(
                "Month of year",
            )
            plt.ylabel("Demand covered fraction")
            plt.legend()
            # plt.title("Renewable DHW demand covered throughout the year")
            plt.savefig(
                os.path.join(figures_directory, "hot_water_renewable_dc_fraction_with_guarracino.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the monthly averages.
            plt.bar(
                dhw_renewable_fraction.keys(),
                dhw_renewable_fraction.values(),
                width=0.7,
                align="center",
            )

            plt.xlim(0, 13)
            plt.ylim(0, 1.0)
            plt.xlabel(
                "Month of year",
            )
            plt.ylabel("Demand covered fraction")
            # plt.title("Renewable DHW demand covered throughout the year")
            plt.savefig(
                os.path.join(figures_directory, "hot_water_renewable_dc_fraction.png"),
                bbox_inches='tight',
                transparent=True,
            )
            plt.close()
            pbar.update(1)
