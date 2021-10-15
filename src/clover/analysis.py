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

import numpy as np  # type: ignore  # pylint: disable=import-error
import pandas as pd  # type: ignore  # pylint: disable=import-error
import seaborn as sns  # type: ignore  # pylint: disable=import-error

import matplotlib.pyplot as plt  # type: ignore  # pylint: disable=import-error
from tqdm import tqdm  # type: ignore  # pylint: disable=import-error

from .__utils__ import CUT_OFF_TIME, DemandType, KeyResults, ResourceType

__all__ = (
    "get_key_results",
    "plot_outputs",
)


# Colour map:
#   The preferred sns colourmap to use.
COLOUR_MAP: str = "Blues"

# Hours per year:
#   The number of hours in a year, used for reshaping arrays.
HOURS_PER_YEAR: int = 8760

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
    key_results.grid_daily_hours = np.sum(grid_input_profile, axis=0)

    # Compute the simulation related averages and sums.
    key_results.average_daily_diesel_energy_supplied = simulation_results[
        "Diesel energy (kWh)"
    ].sum() / (365 * num_years)

    key_results.average_daily_dumped_energy = simulation_results[
        "Dumped energy (kWh)"
    ].sum() / (365 * num_years)

    key_results.average_daily_energy_consumption = simulation_results[
        "Total energy used (kWh)"
    ].sum() / (365 * num_years)

    key_results.average_daily_grid_energy_supplied = simulation_results[
        "Grid energy (kWh)"
    ].sum() / (365 * num_years)

    key_results.average_daily_renewables_energy_supplied = simulation_results[
        "Renewables energy supplied (kWh)"
    ].sum() / (365 * num_years)

    key_results.average_daily_renewables_energy_used = simulation_results[
        "Renewables energy used (kWh)"
    ].sum() / (365 * num_years)

    key_results.average_daily_stored_energy_supplied = simulation_results[
        "Storage energy supplied (kWh)"
    ].sum() / (365 * num_years)

    key_results.average_daily_unmet_energy = simulation_results[
        "Unmet energy (kWh)"
    ].sum() / (365 * num_years)

    key_results.diesel_times = round(simulation_results["Diesel times"].mean(), 3)
    key_results.blackouts = round(simulation_results["Blackouts"].mean(), 3)

    # Compute the clean-water key results.
    if "Clean water blackouts" in simulation_results:
        key_results.clean_water_blackouts = round(
            simulation_results["Clean water blackouts"].mean(), 3
        )

    # Compute the PV-T key results.
    if "PV-T electric energy supplied (kWh)" in simulation_results:
        key_results.average_pvt_electric_generation = round(
            simulation_results["PV-T electric energy supplied (kWh)"].mean(), 3
        )

    return key_results


def plot_outputs(
    grid_input_profile: pd.DataFrame,
    grid_profile: pd.DataFrame,
    initial_clean_water_hourly_loads: Optional[Dict[str, pd.DataFrame]],
    initial_electric_hourly_loads: Dict[str, pd.DataFrame],
    initial_hot_water_hourly_loads: Dict[str, pd.DataFrame],
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
        - initial_clean_water_hourly_loads:
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

    total_clean_water_load = total_loads[ResourceType.CLEAN_WATER]
    total_electric_load = total_loads[ResourceType.ELECTRIC]
    total_hot_water_load = total_loads[ResourceType.HOT_CLEAN_WATER]

    with tqdm(
        total=10
        + (15 if initial_clean_water_hourly_loads is not None else 0)
        + (4 if initial_hot_water_hourly_loads is not None else 0),
        desc="plots",
        leave=False,
        unit="plot",
    ) as pbar:
        # Plot the first year of solar generation as a heatmap.
        rehaped_data = np.reshape(
            total_solar_output.iloc[0:HOURS_PER_YEAR].values, (365, 24)
        )
        heatmap = sns.heatmap(
            rehaped_data,
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
        plt.xticks(rotation=0)  # type: ignore
        plt.tight_layout()  # type: ignore
        plt.savefig(
            os.path.join(figures_directory, "solar_output_hetamap.png"),
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        # Plot the yearly power generated by the solar system.
        solar_daily_sums = pd.DataFrame(np.sum(rehaped_data, axis=1))
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
        rehaped_data = np.reshape(grid_profile.iloc[0:HOURS_PER_YEAR].values, (365, 24))
        heatmap = sns.heatmap(rehaped_data, vmin=0, vmax=1, cmap="Greys_r", cbar=False)
        heatmap.set(
            xticks=range(0, 24, 2),
            xticklabels=range(0, 24, 2),
            yticks=range(0, 365, 30),
            yticklabels=range(0, 365, 30),
            xlabel="Hour of day",
            ylabel="Day of year",
            title="Grid availability of the selected profile.",
        )
        plt.xticks(rotation=0)  # type: ignore
        plt.tight_layout()  # type: ignore
        plt.savefig(
            os.path.join(figures_directory, "grid_availability_heatmap.png"),
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        # Plot the input vs. randomised grid avialability profiles.
        plt.plot(range(24), grid_input_profile, color="k", label="Input")
        plt.plot(range(24), np.mean(rehaped_data, axis=0), color="r", label="Output")
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
            plt.plot(range(CUT_OFF_TIME), load, label=device)
        plt.xticks(range(0, CUT_OFF_TIME - 1, min(6, CUT_OFF_TIME - 1)))
        plt.xlabel("Hour of simulation")
        plt.ylabel("Device load / W")
        plt.title("Electric load demand of each device")
        plt.tight_layout()  # type: ignore
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
        plt.tight_layout()  # type: ignore
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
                simulation_output[0:HOURS_PER_YEAR]["Total energy used (kWh)"].values,
                (365, 24),
            ),
            axis=0,
        )
        diesel_energy = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR]["Diesel energy (kWh)"].values,
                (365, 24),
            ),
            axis=0,
        )
        dumped = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR]["Dumped energy (kWh)"].values,
                (365, 24),
            ),
            axis=0,
        )
        grid_energy = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR]["Grid energy (kWh)"].values,
                (365, 24),
            ),
            axis=0,
        )
        renewable_energy = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    "Renewables energy used (kWh)"
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        pv_supplied = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    "Renewables energy supplied (kWh)"
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        pvt_electricity_supplied = (
            np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "PV-T electric energy supplied (kWh)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            if "PV-T electric energy supplied (kWh)" in simulation_output
            else None
        )
        storage_energy = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    "Storage energy supplied (kWh)"
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        unmet_energy = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR]["Unmet energy (kWh)"].values,
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
        if pvt_electricity_supplied is not None:
            plt.plot(
                pvt_electricity_supplied, label="PV-T electricity generated", zorder=9
            )
            pvt_present: bool = True
        else:
            pvt_present = False
        if initial_clean_water_hourly_loads is not None:
            clean_water_energy_via_excess = (
                np.mean(
                    np.reshape(
                        simulation_output[0:HOURS_PER_YEAR][
                            "Excess power consumed desalinating clean water (kWh)"
                        ].values,
                        (365, 24),
                    ),
                    axis=0,
                )
                if "Excess power consumed desalinating clean water (kWh)"
                in simulation_output
                else None
            )
            clean_water_energy_via_backup = (
                np.mean(
                    np.reshape(
                        simulation_output[0:HOURS_PER_YEAR][
                            "Power consumed providing clean water (kWh)"
                        ].values,
                        (365, 24),
                    ),
                    axis=0,
                )
                if "Power consumed providing clean water (kWh)" in simulation_output
                else None
            )
            thermal_desalination_energy = (
                np.mean(
                    np.reshape(
                        simulation_output[0:HOURS_PER_YEAR][
                            "Power consumed running thermal desalination (kWh)"
                        ].values,
                        (365, 24),
                    ),
                    axis=0,
                )
                if "Power consumed running thermal desalination (kWh)"
                in simulation_output
                else None
            )
            plt.plot(
                clean_water_energy_via_excess,
                label="Excess -> clean water",
                zorder=9 + (1 if pvt_present else 0),
            )
            plt.plot(
                clean_water_energy_via_backup,
                label="Backup -> clean water",
                zorder=10 + (1 if pvt_present else 0),
            )
            plt.plot(
                thermal_desalination_energy,
                label="Thermal desal electric power",
                zorder=11 + (1 if pvt_present else 0),
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
                simulation_output[0:HOURS_PER_YEAR]["Blackouts"].values,
                (365, 24),
            ),
            axis=0,
        )
        storage_energy = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    "Storage energy supplied (kWh)"
                ].values
                > 0,
                (365, 24),
            ),
            axis=0,
        )
        solar_usage = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    "Renewables energy used (kWh)"
                ].values,
                (365, 24),
            ),
            axis=0,
        )
        diesel_times = np.mean(
            np.reshape(
                simulation_output[0:HOURS_PER_YEAR]["Diesel times"].values,
                (365, 24),
            ),
            axis=0,
        )

        plt.plot(blackouts, label="Blackouts")
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
            simulation_output[0:HOURS_PER_YEAR]["Grid energy (kWh)"].values,
            (365, 24),
        )
        storage_energy = np.reshape(
            simulation_output[0:HOURS_PER_YEAR]["Storage energy supplied (kWh)"].values,
            (365, 24),
        )
        renewable_energy = np.reshape(
            simulation_output[0:HOURS_PER_YEAR]["Renewables energy used (kWh)"].values,
            (365, 24),
        )
        diesel_energy = np.reshape(
            simulation_output[0:HOURS_PER_YEAR]["Diesel times"].values,
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
        plt.tight_layout()  # type: ignore
        fig.suptitle("Electricity from different sources (kWh)")
        fig.subplots_adjust(top=0.87)
        plt.xticks(rotation=0)  # type: ignore
        plt.savefig(
            os.path.join(
                figures_directory, "seasonal_electricity_supply_variations.png"
            ),
            transparent=True,
        )
        plt.close()
        pbar.update(1)

        total_used = simulation_output.iloc[0:24]["Total energy used (kWh)"]
        renewable_energy = simulation_output.iloc[0:24]["Renewables energy used (kWh)"]
        storage_energy = simulation_output.iloc[0:24]["Storage energy supplied (kWh)"]
        grid_energy = simulation_output.iloc[0:24]["Grid energy (kWh)"]
        diesel_energy = simulation_output.iloc[0:24]["Diesel energy (kWh)"]
        dumped_energy = simulation_output.iloc[0:24]["Dumped energy (kWh)"]
        unmet_energy = simulation_output.iloc[0:24]["Unmet energy (kWh)"]
        pv_supplied = simulation_output.iloc[0:24]["PV energy supplied (kWh)"]
        pvt_electricity_supplied = (
            simulation_output.iloc[0:24]["PV-T electric energy supplied (kWh)"]
            if "PV-T electric energy supplied (kWh)" in simulation_output
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
        if pvt_present:
            plt.plot(
                pvt_electricity_supplied, label="PV-T electricity generated", zorder=9
            )
        if initial_clean_water_hourly_loads is not None:
            clean_water_energy_via_excess = simulation_output.iloc[0:24][
                "Excess power consumed desalinating clean water (kWh)"
            ]
            clean_water_energy_via_backup = simulation_output.iloc[0:24][
                "Power consumed providing clean water (kWh)"
            ]
            thermal_desalination_energy = simulation_output.iloc[0:24][
                "Power consumed running thermal desalination (kWh)"
            ]
            plt.plot(
                clean_water_energy_via_excess,
                label="Excess -> clean water",
                zorder=9 + (1 if pvt_present else 0),
            )
            plt.plot(
                clean_water_energy_via_backup,
                label="Backup -> clean water",
                zorder=10 + (1 if pvt_present else 0),
            )
            plt.plot(
                thermal_desalination_energy,
                label="Thermal desal electric power",
                zorder=11 + (1 if pvt_present else 0),
            )
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

        if initial_clean_water_hourly_loads is not None:
            # Plot the initial clean-water load of each device.
            for device, load in initial_clean_water_hourly_loads.items():
                plt.plot(range(CUT_OFF_TIME), load, label=device)
                # labels.append(device)
                plt.xticks(range(0, CUT_OFF_TIME - 1, min(6, CUT_OFF_TIME - 2)))
                plt.xlabel("Hour of simulation")
                plt.ylabel("Device load / litres/hour")
                plt.title("Clean water demand of each device")
                plt.tight_layout()  # type: ignore
            plt.legend()
            plt.savefig(
                os.path.join(figures_directory, "clean_water_device_loads.png"),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the clean-water load breakdown by load type.
            plt.plot(
                range(CUT_OFF_TIME),
                total_clean_water_load[0:CUT_OFF_TIME][DemandType.DOMESTIC.value],
                label=DemandType.DOMESTIC.value,
            )
            plt.plot(
                range(CUT_OFF_TIME),
                total_clean_water_load[0:CUT_OFF_TIME][DemandType.COMMERCIAL.value],
                label=DemandType.COMMERCIAL.value,
            )
            plt.plot(
                range(CUT_OFF_TIME),
                total_clean_water_load[0:CUT_OFF_TIME][DemandType.PUBLIC.value],
                label=DemandType.PUBLIC.value,
            )
            plt.plot(
                range(CUT_OFF_TIME),
                np.sum(total_clean_water_load[0:CUT_OFF_TIME], axis=1),
                "--",
                label="total",
            )
            plt.legend(loc="upper right")
            plt.xticks(list(range(0, CUT_OFF_TIME - 1, min(4, CUT_OFF_TIME - 2))))
            plt.xlabel("Hour of simulation")
            plt.ylabel("Clean water demand / litres/hour")
            plt.title(
                f"Clean-water load profile of the community for the first {CUT_OFF_TIME} hours"
            )
            plt.savefig(
                os.path.join(figures_directory, "clean_water_demands.png"),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the annual variation of the clean-water demand.
            _, axis = plt.subplots(1, 2, figsize=(8, 4))
            domestic_demand = np.sum(
                np.reshape(
                    total_clean_water_load[0:HOURS_PER_YEAR][
                        DemandType.DOMESTIC.value
                    ].values,
                    (365, 24),
                ),
                axis=1,
            )
            commercial_demand = np.sum(
                np.reshape(
                    total_clean_water_load[0:HOURS_PER_YEAR][
                        DemandType.COMMERCIAL.value
                    ].values,
                    (365, 24),
                ),
                axis=1,
            )
            public_demand = np.sum(
                np.reshape(
                    total_clean_water_load[0:HOURS_PER_YEAR][
                        DemandType.PUBLIC.value
                    ].values,
                    (365, 24),
                ),
                axis=1,
            )
            total_demand = np.sum(
                np.reshape(
                    np.sum(total_clean_water_load[0:HOURS_PER_YEAR].values, axis=1),
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
                ylabel="Load / litres/hour",
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
                ylabel="Load / litres/hour",
                title="Clean-water demand of each load type",
            )
            plt.tight_layout()  # type: ignore
            plt.savefig(
                os.path.join(
                    figures_directory, "clean_water_demand_annual_variation.png"
                ),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the clean-water demand load growth.
            # Plot the demand growth over the simulation period.
            domestic_demand = np.sum(
                np.reshape(
                    0.001
                    * total_clean_water_load[0 : num_years * HOURS_PER_YEAR][
                        DemandType.DOMESTIC.value
                    ].values,
                    (num_years, HOURS_PER_YEAR),
                ),
                axis=1,
            )
            commercial_demand = np.sum(
                np.reshape(
                    0.001
                    * total_clean_water_load[0 : num_years * HOURS_PER_YEAR][
                        DemandType.COMMERCIAL.value
                    ].values,
                    (num_years, HOURS_PER_YEAR),
                ),
                axis=1,
            )
            public_demand = np.sum(
                np.reshape(
                    0.001
                    * total_clean_water_load[0 : num_years * HOURS_PER_YEAR][
                        DemandType.PUBLIC.value
                    ].values,
                    (num_years, HOURS_PER_YEAR),
                ),
                axis=1,
            )
            total_demand = np.sum(
                np.reshape(
                    np.sum(
                        0.001
                        * total_clean_water_load[0 : num_years * HOURS_PER_YEAR].values,
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
            plt.title("Load growth of the community")
            plt.savefig(
                os.path.join(figures_directory, "clean_water_load_growth.png"),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Water supply and demand on an average day.
            total_supplied = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "Total clean water supplied (l)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            total_used = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "Total clean water consumed (l)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            backup_clean_water = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "Clean water supplied via backup desalination (l)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            excess_power_clean_water = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "Clean water supplied using excess minigrid energy (l)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            renewable_clean_water = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "Renewable clean water used directly (l)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            storage_clean_water = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "Clean water supplied via tank storage (l)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            tank_storage = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "Water held in storage tanks (l)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            total_clean_water_load = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "Total clean water demand (l)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            unmet_clean_water = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "Unmet clean water demand (l)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )

            plt.plot(total_used, "--", label="Total used", zorder=1)
            plt.plot(backup_clean_water, label="Backup desalination", zorder=2)
            plt.plot(
                excess_power_clean_water, label="Excess power desalination", zorder=3
            )
            plt.plot(renewable_clean_water, label="PV-D direct supply", zorder=4)
            plt.plot(storage_clean_water, label="Storage", zorder=5)
            plt.plot(tank_storage, "--", label="Water held in tanks", zorder=6)
            plt.plot(unmet_clean_water, label="Unmet", zorder=7)
            plt.plot(total_clean_water_load, "--", label="Total load", zorder=8)
            plt.plot(total_supplied, "--", label="Total supplied", zorder=9)
            plt.legend()
            plt.xlim(0, 23)
            plt.xticks(range(0, 24, 1))
            plt.xlabel("Hour of day")
            plt.ylabel("Clean-water usage / litres/hour")
            plt.title("Water supply and demand on an average day")
            plt.savefig(
                os.path.join(figures_directory, "clean_water_use_on_average_day.png"),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Water supply and demand on an average July day.
            total_supplied = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_JULY : HOURS_UNTIL_JULY + 31 * 24][
                        "Total clean water supplied (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            total_used = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_JULY : HOURS_UNTIL_JULY + 31 * 24][
                        "Total clean water consumed (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            backup_clean_water = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_JULY : HOURS_UNTIL_JULY + 31 * 24][
                        "Clean water supplied via backup desalination (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            excess_power_clean_water = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_JULY : HOURS_UNTIL_JULY + 31 * 24][
                        "Clean water supplied using excess minigrid energy (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            renewable_clean_water = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_JULY : HOURS_UNTIL_JULY + 31 * 24][
                        "Renewable clean water used directly (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            storage_clean_water = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_JULY : HOURS_UNTIL_JULY + 31 * 24][
                        "Clean water supplied via tank storage (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            tank_storage = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_JULY : HOURS_UNTIL_JULY + 31 * 24][
                        "Water held in storage tanks (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            total_clean_water_load = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_JULY : HOURS_UNTIL_JULY + 31 * 24][
                        "Total clean water demand (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            unmet_clean_water = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_JULY : HOURS_UNTIL_JULY + 31 * 24][
                        "Unmet clean water demand (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )

            plt.plot(total_used, "--", label="Total used", zorder=1)
            plt.plot(backup_clean_water, label="Backup desalination", zorder=2)
            plt.plot(
                excess_power_clean_water, label="Excess power desalination", zorder=3
            )
            plt.plot(renewable_clean_water, label="PV-D direct supply", zorder=4)
            plt.plot(storage_clean_water, label="Storage", zorder=5)
            plt.plot(tank_storage, "--", label="Water held in tanks", zorder=6)
            plt.plot(unmet_clean_water, label="Unmet", zorder=7)
            plt.plot(total_clean_water_load, "--", label="Total load", zorder=8)
            plt.plot(total_supplied, "--", label="Total supplied", zorder=9)
            plt.legend()
            plt.xlim(0, 23)
            plt.xticks(range(0, 24, 1))
            plt.xlabel("Hour of day")
            plt.ylabel("Clean-water usage / litres/hour")
            plt.title("Water supply and demand on an average July day")
            plt.savefig(
                os.path.join(
                    figures_directory, "clean_water_use_on_average_july_day.png"
                ),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Water supply and demand on an average January day.
            total_supplied = np.mean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        "Total clean water supplied (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            total_used = np.mean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        "Total clean water consumed (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            backup_clean_water = np.mean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        "Clean water supplied via backup desalination (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            excess_power_clean_water = np.mean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        "Clean water supplied using excess minigrid energy (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            renewable_clean_water = np.mean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        "Renewable clean water used directly (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            storage_clean_water = np.mean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        "Clean water supplied via tank storage (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            tank_storage = np.mean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        "Water held in storage tanks (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            total_clean_water_load = np.mean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        "Total clean water demand (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            unmet_clean_water = np.mean(
                np.reshape(
                    simulation_output[0 : 24 * 31][
                        "Unmet clean water demand (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )

            plt.plot(total_used, "--", label="Total used", zorder=1)
            plt.plot(backup_clean_water, label="Backup desalination", zorder=2)
            plt.plot(
                excess_power_clean_water, label="Excess power desalination", zorder=3
            )
            plt.plot(renewable_clean_water, label="PV-D direct supply", zorder=4)
            plt.plot(storage_clean_water, label="Storage", zorder=5)
            plt.plot(tank_storage, "--", label="Water held in tanks", zorder=6)
            plt.plot(unmet_clean_water, label="Unmet", zorder=7)
            plt.plot(total_clean_water_load, "--", label="Total load", zorder=8)
            plt.plot(total_supplied, "--", label="Total supplied", zorder=9)
            plt.legend()
            plt.xlim(0, 23)
            plt.xticks(range(0, 24, 1))
            plt.xlabel("Hour of day")
            plt.ylabel("Clean-water usage / litres/hour")
            plt.title("Water supply and demand on an January average day")
            plt.savefig(
                os.path.join(
                    figures_directory, "clean_water_use_on_average_january_day.png"
                ),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Water supply and demand on the first day.
            backup = simulation_output.iloc[0:24][
                "Clean water supplied via backup desalination (l)"
            ]
            excess = simulation_output.iloc[0:24][
                "Clean water supplied using excess minigrid energy (l)"
            ]
            renewable = simulation_output.iloc[0:24][
                "Renewable clean water used directly (l)"
            ]
            storage = simulation_output.iloc[0:24][
                "Clean water supplied via tank storage (l)"
            ]
            tank_storage = simulation_output.iloc[0:24][
                "Water held in storage tanks (l)"
            ]
            total_load = simulation_output.iloc[0:24]["Total clean water demand (l)"]
            total_used = simulation_output.iloc[0:24]["Total clean water supplied (l)"]
            unmet_clean_water = simulation_output.iloc[0:24][
                "Unmet clean water demand (l)"
            ]

            plt.plot(total_used, "--", label="Total used", zorder=1)
            plt.plot(backup, label="Backup desalination", zorder=2)
            plt.plot(excess, label="Excess minigrid power", zorder=3)
            plt.plot(renewable, label="PV-D output", zorder=4)
            plt.plot(storage, label="Storage", zorder=5)
            plt.plot(tank_storage, "--", label="Water held in tanks", zorder=6)
            plt.plot(unmet_clean_water, label="Unmet", zorder=7)
            plt.plot(total_load, "--", label="Total load", zorder=8)
            plt.legend()
            plt.xlim(0, 23)
            plt.xticks(range(0, 24, 1))
            plt.xlabel("Hour of day")
            plt.ylabel("Clean-water usage / litres/hour")
            plt.title("Water supply and demand on the first day")
            plt.savefig(
                os.path.join(figures_directory, "clean_water_use_on_first_day.png"),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            backup = simulation_output.iloc[0:48][
                "Clean water supplied via backup desalination (l)"
            ]
            excess = simulation_output.iloc[0:48][
                "Clean water supplied using excess minigrid energy (l)"
            ]
            renewable = simulation_output.iloc[0:48][
                "Renewable clean water used directly (l)"
            ]
            storage = simulation_output.iloc[0:48][
                "Clean water supplied via tank storage (l)"
            ]
            tank_storage = simulation_output.iloc[0:48][
                "Water held in storage tanks (l)"
            ]
            total_load = simulation_output.iloc[0:48]["Total clean water demand (l)"]
            total_used = simulation_output.iloc[0:48]["Total clean water supplied (l)"]
            unmet_clean_water = simulation_output.iloc[0:48][
                "Unmet clean water demand (l)"
            ]

            plt.plot(total_used, "--", label="Total used", zorder=1)
            plt.plot(backup, label="Backup desalination", zorder=2)
            plt.plot(excess, label="Excess minigrid power", zorder=3)
            plt.plot(renewable, label="PV-D output", zorder=4)
            plt.plot(storage, label="Storage", zorder=5)
            plt.plot(tank_storage, "--", label="Water held in tanks", zorder=6)
            plt.plot(unmet_clean_water, label="Unmet", zorder=7)
            plt.plot(total_load, "--", label="Total load", zorder=8)
            plt.legend()
            plt.xlim(0, 47)
            plt.xticks(range(0, 48, 1))
            plt.xlabel("Hour of day")
            plt.ylabel("Clean-water usage / litres/hour")
            plt.title("Water supply and demand in the first 48 hours")
            plt.savefig(
                os.path.join(
                    figures_directory, "clean_water_use_in_first_48_hours.png"
                ),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # blackouts = np.mean(
            #     np.reshape(
            #         simulation_output[0:HOURS_PER_YEAR][
            #             "Water supply blackouts"
            #         ].values,
            #         (365, 24),
            #     ),
            #     axis=0,
            # )
            # direct_electric_supply = np.mean(
            #     np.reshape(
            #         simulation_output[0:HOURS_PER_YEAR][
            #             "Water supplied by direct electricity (l)"
            #         ].values
            #         > 0,
            #         (365, 24),
            #     ),
            #     axis=0,
            # )

            # plt.plot(blackouts, label="Blackouts")
            # plt.plot(direct_electric_supply, label="Direct electric")
            # plt.legend()
            # plt.xlim(0, 23)
            # plt.xticks(range(0, 24, 1))
            # plt.ylim(0, 1)
            # plt.yticks(np.arange(0, 1.1, 0.25))
            # plt.xlabel("Hour of day")
            # plt.ylabel("Probability")
            # plt.title("Clean-water availability on an average day")
            # plt.savefig(
            #     os.path.join(
            #         figures_directory, "clean_water_avilability_on_average_day.png"
            #     ),
            #     transparent=True,
            # )
            # plt.close()
            # pbar.update(1)

            clean_water_power_supplied = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "Power consumed providing clean water (kWh)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            dumped_power = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR]["Dumped energy (kWh)"].values,
                    (365, 24),
                ),
                axis=0,
            )
            electric_power_supplied = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "Power consumed providing electricity (kWh)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            surplus_power_consumed = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "Excess power consumed desalinating clean water (kWh)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            thermal_desalination_energy = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "Power consumed running thermal desalination (kWh)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )
            total_power_supplied = np.mean(
                np.reshape(
                    simulation_output[0:HOURS_PER_YEAR][
                        "Total energy used (kWh)"
                    ].values,
                    (365, 24),
                ),
                axis=0,
            )

            plt.plot(clean_water_power_supplied, label="Clean-water via conversion")
            plt.plot(dumped_power, label="Unused dumped energy")
            plt.plot(electric_power_supplied, label="Electric devices")
            plt.plot(
                surplus_power_consumed,
                label="Clean water via dumped energy",
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
            plt.title("Electriciy use by supply/device type on an average day")
            plt.savefig(
                os.path.join(figures_directory, "electricity_use_by_supply_type.png"),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the daily collector output temperature
            _, ax1 = plt.subplots()
            collector_output_temperature_january = simulation_output.iloc[0:24][
                "PV-T output temperature (degC)"
            ]
            collector_output_temperature_march = simulation_output.iloc[
                HOURS_UNTIL_MARCH : HOURS_UNTIL_MARCH + 24
            ]["PV-T output temperature (degC)"]
            collector_output_temperature_may = simulation_output.iloc[
                HOURS_UNTIL_MAY : HOURS_UNTIL_MAY + 24
            ]["PV-T output temperature (degC)"]
            collector_output_temperature_july = simulation_output.iloc[
                HOURS_UNTIL_JULY : HOURS_UNTIL_JULY + 24
            ]["PV-T output temperature (degC)"]
            volume_supplied_january = simulation_output.iloc[0:24][
                "Water heated by the PV-T (l)"
            ]
            volume_supplied_march = simulation_output.iloc[
                HOURS_UNTIL_MARCH : HOURS_UNTIL_MARCH + 24
            ]["Water heated by the PV-T (l)"]
            volume_supplied_may = simulation_output.iloc[
                HOURS_UNTIL_MAY : HOURS_UNTIL_MAY + 24
            ]["Water heated by the PV-T (l)"]
            volume_supplied_july = simulation_output.iloc[
                HOURS_UNTIL_JULY : HOURS_UNTIL_JULY + 24
            ]["Water heated by the PV-T (l)"]

            ax1.plot(collector_output_temperature_january.values, label="january temp.")
            # ax1.plot(collector_output_temperature_march.values, label="march temp.")
            # ax1.plot(collector_output_temperature_may.values, label="may temp.")
            ax1.plot(collector_output_temperature_july.values, label="july temp.")
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
            ax2.set_ylabel("Volume heated / litres")
            plt.title("Collector output temprature on the first day of select months")
            plt.savefig(
                os.path.join(
                    figures_directory,
                    "collector_output_temperature_on_first_month_days.png",
                ),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the average collector output temperature
            _, ax1 = plt.subplots()
            collector_output_temperature_january = np.mean(
                np.reshape(
                    simulation_output[0 : 31 * 24][
                        "PV-T output temperature (degC)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            collector_output_temperature_march = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_MARCH : HOURS_UNTIL_MARCH + 31 * 24][
                        "PV-T output temperature (degC)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            collector_output_temperature_may = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_MAY : HOURS_UNTIL_MAY + 31 * 24][
                        "PV-T output temperature (degC)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            collector_output_temperature_july = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_JULY : HOURS_UNTIL_JULY + 31 * 24][
                        "PV-T output temperature (degC)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )

            # Plot the average collector output temperature
            volume_supplied_january = np.mean(
                np.reshape(
                    simulation_output[0 : 31 * 24][
                        "Water heated by the PV-T (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            volume_supplied_march = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_MARCH : HOURS_UNTIL_MARCH + 31 * 24][
                        "Water heated by the PV-T (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            volume_supplied_may = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_MAY : HOURS_UNTIL_MAY + 31 * 24][
                        "Water heated by the PV-T (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )
            volume_supplied_july = np.mean(
                np.reshape(
                    simulation_output[HOURS_UNTIL_JULY : HOURS_UNTIL_JULY + 31 * 24][
                        "Water heated by the PV-T (l)"
                    ].values,
                    (31, 24),
                ),
                axis=0,
            )

            ax1.plot(collector_output_temperature_january, label="january temp.")
            # ax1.plot(collector_output_temperature_march, label="march temp.")
            # ax1.plot(collector_output_temperature_may, label="may temp.")
            ax1.plot(collector_output_temperature_july, label="july temp.")
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
            ax2.set_ylabel("Volume heated / litres")
            plt.title("Collector output temprature on an average seasonal days day")
            plt.savefig(
                os.path.join(
                    figures_directory,
                    "collector_output_temperature_on_average_month_days.png",
                ),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the seasonal variation in clean-water supply sources.
            backup_water = np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    "Clean water supplied via backup desalination (l)"
                ].values
                / 1000,
                (365, 24),
            )
            excess_pv_water = np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    "Clean water supplied using excess minigrid energy (l)"
                ].values
                / 1000,
                (365, 24),
            )
            storage_water = np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    "Clean water supplied via tank storage (l)"
                ].values
                / 1000,
                (365, 24),
            )
            renewable_energy = np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    "Renewable clean water used directly (l)"
                ].values
                / 1000,
                (365, 24),
            )
            unmet_water = np.reshape(
                simulation_output[0:HOURS_PER_YEAR][
                    "Unmet clean water demand (l)"
                ].values
                / 1000,
                (365, 24),
            )

            fig, ([ax1, ax2, unused_ax], [ax3, ax4, ax5]) = plt.subplots(
                2, 3
            )  # ,sharex=True, sharey=True)
            unused_ax.set_visible(False)
            sns.heatmap(
                excess_pv_water,
                vmin=0.0,
                vmax=excess_pv_water.max(),
                cmap="Reds",
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
                title="Excess PV",
            )
            sns.heatmap(
                storage_water,
                vmin=0.0,
                vmax=storage_water.max(),
                cmap="Greens",
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
                title="Storage",
            )
            sns.heatmap(
                renewable_energy,
                vmin=0.0,
                vmax=renewable_energy.max(),
                cmap="Blues",
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
                title="PV-D/T",
            )
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
            sns.heatmap(
                unmet_water,
                vmin=0.0,
                vmax=unmet_water.max(),
                cmap="Greys",
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
                title="Unmet",
            )

            # Adjust the positioning of the plots
            # ax4.set_position([0.24, 0.125, 0.228, 0.343])
            # ax5.set_position([0.55, 0.125, 0.228, 0.343])

            plt.tight_layout()  # type: ignore
            fig.suptitle("Water from different sources (tonnes)")
            fig.subplots_adjust(top=0.87)
            plt.xticks(rotation=0)  # type: ignore
            plt.savefig(
                os.path.join(figures_directory, "seasonal_water_supply_variations.png"),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

        if initial_hot_water_hourly_loads is not None:
            # Plot the initial hot-water load of each device.
            for device, load in initial_hot_water_hourly_loads.items():
                plt.plot(range(CUT_OFF_TIME), load, label=device)
                # labels.append(device)
                plt.xticks(range(0, CUT_OFF_TIME - 1, min(6, CUT_OFF_TIME - 2)))
                plt.xlabel("Hour of simulation")
                plt.ylabel("Device load / litres/hour")
                plt.title("Hot water demand of each device")
                plt.tight_layout()  # type: ignore
            plt.legend()
            plt.savefig(
                os.path.join(figures_directory, "hot_water_device_loads.png"),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the clean-water load breakdown by load type.
            plt.plot(
                range(CUT_OFF_TIME),
                total_hot_water_load[0:CUT_OFF_TIME][DemandType.DOMESTIC.value],
                label=DemandType.DOMESTIC.value,
            )
            plt.plot(
                range(CUT_OFF_TIME),
                total_hot_water_load[0:CUT_OFF_TIME][DemandType.COMMERCIAL.value],
                label=DemandType.COMMERCIAL.value,
            )
            plt.plot(
                range(CUT_OFF_TIME),
                total_hot_water_load[0:CUT_OFF_TIME][DemandType.PUBLIC.value],
                label=DemandType.PUBLIC.value,
            )
            plt.plot(
                range(CUT_OFF_TIME),
                np.sum(total_hot_water_load[0:CUT_OFF_TIME], axis=1),
                "--",
                label="total",
            )
            plt.legend(loc="upper right")
            plt.xticks(list(range(0, CUT_OFF_TIME - 1, min(4, CUT_OFF_TIME - 2))))
            plt.xlabel("Hour of simulation")
            plt.ylabel("Hot water demand / litres/hour")
            plt.title(
                f"Hot-water load profile of the community for the first {CUT_OFF_TIME} hours"
            )
            plt.savefig(
                os.path.join(figures_directory, "hot_water_demands.png"),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the annual variation of the clean-water demand.
            _, axis = plt.subplots(1, 2, figsize=(8, 4))
            domestic_demand = np.sum(
                np.reshape(
                    total_hot_water_load[0:HOURS_PER_YEAR][
                        DemandType.DOMESTIC.value
                    ].values,
                    (365, 24),
                ),
                axis=1,
            )
            commercial_demand = np.sum(
                np.reshape(
                    total_hot_water_load[0:HOURS_PER_YEAR][
                        DemandType.COMMERCIAL.value
                    ].values,
                    (365, 24),
                ),
                axis=1,
            )
            public_demand = np.sum(
                np.reshape(
                    total_hot_water_load[0:HOURS_PER_YEAR][
                        DemandType.PUBLIC.value
                    ].values,
                    (365, 24),
                ),
                axis=1,
            )
            total_demand = np.sum(
                np.reshape(
                    np.sum(total_hot_water_load[0:HOURS_PER_YEAR].values, axis=1),
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
                ylabel="Load / litres/hour",
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
                ylabel="Load / litres/hour",
                title="Hot-water demand of each load type",
            )
            plt.tight_layout()  # type: ignore
            plt.savefig(
                os.path.join(
                    figures_directory, "hot_water_demand_annual_variation.png"
                ),
                transparent=True,
            )
            plt.close()
            pbar.update(1)

            # Plot the hot-water demand load growth over the simulation period.
            domestic_demand = np.sum(
                np.reshape(
                    0.001
                    * total_hot_water_load[0 : num_years * HOURS_PER_YEAR][
                        DemandType.DOMESTIC.value
                    ].values,
                    (num_years, HOURS_PER_YEAR),
                ),
                axis=1,
            )
            commercial_demand = np.sum(
                np.reshape(
                    0.001
                    * total_hot_water_load[0 : num_years * HOURS_PER_YEAR][
                        DemandType.COMMERCIAL.value
                    ].values,
                    (num_years, HOURS_PER_YEAR),
                ),
                axis=1,
            )
            public_demand = np.sum(
                np.reshape(
                    0.001
                    * total_hot_water_load[0 : num_years * HOURS_PER_YEAR][
                        DemandType.PUBLIC.value
                    ].values,
                    (num_years, HOURS_PER_YEAR),
                ),
                axis=1,
            )
            total_demand = np.sum(
                np.reshape(
                    np.sum(
                        0.001
                        * total_hot_water_load[0 : num_years * HOURS_PER_YEAR].values,
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
            plt.title("Load growth of the community")
            plt.savefig(
                os.path.join(figures_directory, "hot_water_load_growth.png"),
                transparent=True,
            )
            plt.close()
            pbar.update(1)
