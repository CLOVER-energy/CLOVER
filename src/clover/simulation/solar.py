#!/usr/bin/python3
########################################################################################
# solar.py - Solar panel modelling code for CLOVER.                                    #
#                                                                                      #
# Authors: Ben Winchester                                                              #
# Copyright: Phil Sandwell, 2021                                                       #
# Date created: 12/08/2021                                                             #
# License: Open source                                                                 #

# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################
"""
solar.py - Solar-panel modelling code for CLOVER.

In order to accurately model a solar panel within CLOVER, various information about its
performance under environmental conditions needs to be calculated.

"""

# Bodged import
import pickle

from logging import Logger
from typing import Dict, List, Tuple

import pandas as pd  # type: ignore  # pylint: disable=import-error

from sklearn.linear_model import Lasso
from tqdm import tqdm

from ..__utils__ import BColours, InputFileError, ResourceType, Scenario
from ..conversion.conversion import Convertor, ThermalDesalinationPlant
from ..generation.solar import HybridPVTPanel
from .__utils__ import Minigrid


__all__ = ("calculate_pvt_output",)


def _pvt_mass_flow_rate(
    logger: Logger,
    pvt_panel: HybridPVTPanel,
    pvt_system_size: int,
    thermal_desalination_plant: ThermalDesalinationPlant,
) -> float:
    """
    Determines the mass-flow rate through the PV-T panels.

    Inputs:
        - logger:
            The :class:`logging.Logger` to use for the run.
        - pvt_panel:
            The :class:`HybridPVTPanel` being considered.
        - pvt_system_size:
            The size of the PV-T system being considered, measured in PV-T units.
        - thermal_desalination_plant:
            The :class:`ThermalDesalinationPlant` being considered.

    Outputs:
        The mass-flow rate of HTF through a single PV-T panel.

    Raises:
        - InputFileError:
            Raised if there is a mismatch between the parameters that means that the
            mass-flow rate cannot be determined.

    """

    if (
        pvt_system_size * pvt_panel.max_mass_flow_rate
        < thermal_desalination_plant.input_resource_consumption[
            ResourceType.HOT_UNCLEAN_WATER
        ]
        * (
            thermal_desalination_plant.minimum_output_capacity
            / thermal_desalination_plant.maximum_output_capacity
        )
    ):
        logger.error(
            "The PV-T system is not able to supply enough water to operate the thermal "
            "desalination plant: max PV-T output: %s litres/hour, min desalination "
            "plant input: %s litres/hour",
            pvt_system_size * pvt_panel.max_mass_flow_rate,
            thermal_desalination_plant.input_resource_consumption[
                ResourceType.HOT_UNCLEAN_WATER
            ]
            * (
                thermal_desalination_plant.minimum_output_capacity
                / thermal_desalination_plant.maximum_output_capacity
            ),
        )
        raise InputFileError(
            "conversion/solar inputs",
            "Mismatch between PV-T and desalination-plant sizing.",
        )
    if (
        pvt_system_size * pvt_panel.min_mass_flow_rate
        > thermal_desalination_plant.input_resource_consumption[
            ResourceType.HOT_UNCLEAN_WATER
        ]
    ):
        logger.error(
            "The thermal desalination plant is unable to cope with the minimum "
            "throughput from the PV-T system: minimum PV-T output: %s litres/hour, max desalination plant input: %s lirres/hour",
            pvt_system_size * pvt_panel.min_mass_flow_rate,
            thermal_desalination_plant.input_resource_consumption[
                ResourceType.HOT_UNCLEAN_WATER
            ],
        )
        raise InputFileError(
            "conversion/solar inputs",
            "Mismatch between PV-T and desalination-plant sizing.",
        )

    return min(
        pvt_panel.max_mass_flow_rate,
        thermal_desalination_plant.input_resource_consumption[
            ResourceType.HOT_UNCLEAN_WATER
        ]
        / pvt_system_size,
    )


def calculate_pvt_output(
    end_hour: int,
    irradiances: pd.Series,
    logger: Logger,
    minigrid: Minigrid,
    pvt_system_size: int,
    scenario: Scenario,
    start_hour: int,
    temperatures: pd.Series,
    thermal_desalination_plant: ThermalDesalinationPlant,
    wind_speeds: pd.Series,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Computes the output of a PV-T system.

    Inputs:
        - end_hour:
            The end hour for the simulation being carried out.
        - irradiances:
            The :class:`pd.Series` containing irradiance information for the time
            period being modelled.
        - logger:
            The logger to use for the run.
        - minigrid:
            The minigrid being modelled currently.
        - pvt_system_size:
            The size of the PV-T system being modelled.
        - scenario:
            The :class:`Scenario` being considered.
        - start_hour:
            The start hour for the simulation being carried out.
        - temperatures:
            The :class:`pd.Series` containing temperature information for the time
            period being modelled.
        - thermal_desalination_plant:
            The thermal desalination plant being considered.
        - wind_speeds:
            The :class:`pd.Series` containing wind-speed information for the time period
            being modelled.

    Outputs:
        - pvt_collector_output_temperature:
            The output temperature of the PV-T collectors at each time step.
        - pvt_electric_power_per_unit:
            The electric power, per unit PV-T, delivered by the PV-T system.
        - pvt_volume_supplied_per_unit:
            The amount of hot water produced per unit PV-T, delivered by the PV-T
            system.

    """

    if minigrid.pvt_panel is None:
        logger.error(
            "The energy system does not contain a PV-T panel despite the PV-T output computation function being called."
        )
        raise InputFileError(
            "energy system inputs",
            "The energy system specified does not contain a PV-T panel but PV-T "
            "modelling was requested.",
        )

    # Determine the mass-flow rate through the collector.
    mass_flow_rate = _pvt_mass_flow_rate(
        logger, minigrid.pvt_panel, pvt_system_size, thermal_desalination_plant
    )

    # Instantiate loop parameters.
    collector_input_temperature = scenario.clean_water_scenario.supply_temperature

    # Instantiate maps for easy PV-T power lookups.
    pvt_collector_output_temperature_map: Dict[int, float] = {}
    pvt_electric_power_per_unit_map: Dict[int, float] = {}
    pvt_volume_output_supplied_map: Dict[int, float] = {}

    # Load in the model, bodged for now.
    with open("../PVTModel/electrical_model.sav", "rb") as f:
        electrical_model = pickle.load(f)
    with open("../PVTModel/thermal_model.sav", "rb") as f:
        thermal_model = pickle.load(f)

    try:
        for index in tqdm(
            range(start_hour, end_hour),
            desc="pv-t performance",
            leave=False,
            unit="hour",
        ):
            # Only compute outputs if there is input irradiance.
            if irradiances[index] > 0:
                # Fitted python model.
                # # Compute the fractional PV-T performance and thermal PV-T outputs.
                # (
                #     collector_output_temperature,
                #     fractional_electric_performance,
                # ) = minigrid.pvt_panel.fractional_performance(
                #     temperatures[index],
                #     collector_input_temperature,
                #     1000 * irradiances[index],
                #     mass_flow_rate,
                #     wind_speeds[index],
                # )

                # AI fitted model.
                collector_output_temperature = thermal_model.predict(
                    [
                        [
                            temperatures[index],
                            collector_input_temperature,
                            mass_flow_rate,
                            irradiances[index],
                            wind_speeds[index],
                        ]
                    ]
                )
                fractional_electric_performance = electrical_model.predict(
                    [
                        [
                            temperatures[index],
                            collector_input_temperature,
                            mass_flow_rate,
                            irradiances[index],
                            wind_speeds[index],
                        ]
                    ]
                )

                import pdb

                pdb.set_trace()

                # Sawtooth model.
                # collector_output_temperature = collector_input_temperature + 25
                # fractional_electric_performance = 0.125 * (
                #     1
                #     - minigrid.pvt_panel.thermal_coefficient
                #     *(temperatures[index] - minigrid.pvt_panel.reference_temperature)
                # )

                # If the desalination plant was able to accept this water, then use this.
                if (
                    collector_output_temperature
                    >= thermal_desalination_plant.minimum_water_input_temperature
                ):
                    collector_input_temperature = (
                        scenario.clean_water_scenario.supply_temperature
                    )
                    volume_supplied = mass_flow_rate
                # Otherwise, cycle this water back around.
                else:
                    collector_input_temperature = collector_output_temperature
                    volume_supplied = 0
            else:
                collector_input_temperature = (
                    scenario.clean_water_scenario.supply_temperature
                )
                collector_output_temperature = collector_input_temperature
                fractional_electric_performance = 0
                volume_supplied = 0

            # Save the fractional electrical performance.
            pvt_collector_output_temperature_map[index] = collector_output_temperature
            pvt_electric_power_per_unit_map[index] = fractional_electric_performance
            pvt_volume_output_supplied_map[index] = volume_supplied

    except TypeError:
        logger.error(
            "The PV-T system size must be specified explicitly on the command line."
        )
        raise Exception("Missing command-line argument: --pvt-system-size.") from None

    # Convert these outputs to dataframes and return.
    pvt_collector_output_temperature: pd.DataFrame = pd.DataFrame(  # type: ignore
        list(pvt_collector_output_temperature_map.values()),
        index=list(pvt_collector_output_temperature_map.keys()),
    ).sort_index()
    pvt_electric_power_per_unit: pd.DataFrame = (
        pd.DataFrame(  # type: ignore
            list(pvt_electric_power_per_unit_map.values()),
            index=list(pvt_electric_power_per_unit_map.keys()),
        ).sort_index()
        * minigrid.pvt_panel.pv_unit
    )
    pvt_volume_output_supplied_per_unit: pd.DataFrame = (
        pd.DataFrame(
            list(pvt_volume_output_supplied_map.values()),
            index=list(pvt_volume_output_supplied_map.keys()),
        ).sort_index()
        * minigrid.pvt_panel.thermal_unit
    )
    # @@@ Fix units here between W in PV-T unit and mass-flow rate.

    return (
        pvt_collector_output_temperature,
        pvt_electric_power_per_unit,
        pvt_volume_output_supplied_per_unit,
    )
