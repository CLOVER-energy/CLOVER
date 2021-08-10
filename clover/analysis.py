#!/usr/bin/python3
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

import dataclasses
import os

from typing import Dict, Optional

import numpy as np
import pandas as pd
import seaborn as sns

import matplotlib.pyplot as plt

from .__utils__ import CUT_OFF_TIME, DemandType, KeyResults

__all__ = (
    "get_key_results",
    "plot_outputs",
)


# Colour map:
#   The preferred sns colourmap to use.
COLOUR_MAP = "Blues"

# Hours per year:
#   The number of hours in a year, used for reshaping arrays.
HOURS_PER_YEAR = 8760

# Plot resolution:
#   The resolution, in dpi, to use for plotting figures.
PLOT_RESOLUTION = 300


def get_key_results(
    grid_input_profile: pd.DataFrame, total_solar_output: pd.DataFrame
) -> KeyResults:
    """
    Computes the key results of the simulation.

        Inputs:
            - grid_input_profile:
            The relevant grid input profile for the simulation that was run.
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

    return key_results


def plot_outputs(
    grid_input_profile: pd.DataFrame,
    grid_profile: pd.DataFrame,
    initial_clean_water_hourly_loads: Optional[Dict[str, pd.DataFrame]],
    initial_electric_hourly_loads: Dict[str, pd.DataFrame],
    output_directory: str,
    simulation_filename: str,
    total_clean_water_load: pd.DataFrame,
    total_electric_load: pd.DataFrame,
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
        - output_directory:
            The directory into which to save the output information.
        - simulation_filename:
            The filename used when saving the simulation.
        - total_clean_water_load:
            The total clean water load placed on the system.
        - total_electric_load:
            The total electric load placed on the system.
        - total_solar_output:
            The total solar power produced by the PV installation.

    """

    # Create an output directory for the various plots to be saved in.
    figures_directory = os.path.join(output_directory, simulation_filename)
    os.makedirs(figures_directory, exist_ok=True)

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
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(
        os.path.join(figures_directory, "solar_output_hetamap.png"), transparent=True
    )
    plt.close()

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
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(
        os.path.join(figures_directory, "grid_availability_heatmap.png"),
        transparent=True,
    )
    plt.close()

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

    # Plot the initial electric load of each device.
    for device, load in initial_electric_hourly_loads.items():
        plt.plot(range(CUT_OFF_TIME), load, label=device)
        plt.xticks(range(0, CUT_OFF_TIME - 1, 6))
        plt.yticks(range(0, 1000, 50))
        plt.xlabel("Hour of simulation")
        plt.ylabel("Device load / W")
        plt.title("Load demand of each device")
        plt.tight_layout()
    plt.legend()
    plt.savefig(
        os.path.join(figures_directory, "electric_device_loads.png"), transparent=True,
    )
    plt.close()

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
        label="total",
    )
    plt.legend(loc="upper right")
    plt.xticks(list(range(0, CUT_OFF_TIME - 1, 4)))
    plt.yticks(list(range(0, 4501, 500)))
    plt.xlabel("Hour of simulation")
    plt.ylabel("Electric power demand / W")
    plt.title(f"Load profile of the community for the first {CUT_OFF_TIME} hours")
    plt.savefig(
        os.path.join(figures_directory, "electric_demands.png"), transparent=True,
    )
    plt.close()

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
            total_electric_load[0:HOURS_PER_YEAR][DemandType.COMMERCIAL.value].values,
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
            np.sum(total_electric_load[0:HOURS_PER_YEAR].values, axis=1), (365, 24),
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
        label="Total",
        color="red",
    )
    axis[1].plot(range(365), total_demand, alpha=0.5, color="red")
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

    # Plot the initial clean-water load of each device.
    if initial_clean_water_hourly_loads is not None:
        for device, load in initial_clean_water_hourly_loads.items():
            plt.plot(range(CUT_OFF_TIME), load, label=device)
            # labels.append(device)
            plt.xticks(range(0, CUT_OFF_TIME - 1, 6))
            plt.yticks(range(0, 1000, 50))
            plt.xlabel("Hour of simulation")
            plt.ylabel("Device load / litres/hour")
            plt.title("Load demand of each device")
            plt.tight_layout()
        plt.legend()
        plt.savefig(
            os.path.join(figures_directory, "clean_water_device_loads.png"),
            transparent=True,
        )
        plt.close()

        # Plot the electric load breakdown by load type.
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
            label="total",
        )
        plt.legend(loc="upper right")
        plt.xticks(list(range(0, CUT_OFF_TIME - 1, 4)))
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

        # Plot the annual variation of the electricity demand.
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
            yticks=range(0, 26, 5),
            xlabel="Day of simulation period",
            ylabel="Load / litres/hour",
            title="Clean-water demand of each load type",
        )
        axis[1].plot(
            range(365),
            pd.DataFrame(total_demand).rolling(5).mean(),
            label="Total",
            color="red",
        )
        axis[1].plot(range(365), total_demand, alpha=0.5, color="red")
        axis[1].legend(loc="best")
        axis[1].set(
            xticks=(range(0, 366, 60)),
            yticks=range(15, 41, 5),
            xlabel="Day of simulation period",
            ylabel="Load / litres/hour",
            title="Clean-water demand of each load type",
        )
        plt.tight_layout()
        plt.savefig(
            os.path.join(figures_directory, "clean_water_demand_annual_variation.png"),
            transparent=True,
        )
