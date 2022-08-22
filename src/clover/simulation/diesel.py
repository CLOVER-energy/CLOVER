#!/usr/bin/python3
########################################################################################
# diesel.py - Energy-system diesel module                                              #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# License: Open source                                                                 #
# Most recent update: 12/11/2021                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################
"""
diesel.py - The energy-system's diesel module.

This module represents diesel generators within the energy system containing
functionality to model diesel generators.

"""

import dataclasses
import logging

from typing import Any, Dict, Optional, Tuple

import numpy as np  # pylint: disable=import-error
import pandas as pd

from ..__utils__ import (
    BColours,
    ELECTRIC_POWER,
    DieselMode,
    InputFileError,
    NAME,
    ProgrammerJudgementFault,
    ResourceType,
)
from ..conversion.conversion import MAXIMUM_OUTPUT, Converter


__all__ = (
    "DIESEL_CONSUMPTION",
    "DieselGenerator",
    "DieselWaterHeater",
    "get_diesel_energy_and_times",
    "get_diesel_fuel_usage",
)


# Diesel consumption:
#   Used to parse diesel fuel consumption information.
DIESEL_CONSUMPTION: str = "diesel_consumption"

# Minimum load:
#   The minimum load that needs to be placed on a diesel-consuming device.
MINIMUM_LOAD: str = "minimum_load"


@dataclasses.dataclass
class DieselGenerator:
    """
    Represents a diesel backup generator.

    .. attribute:: diesel_consumption
        The diesel consumption of the generator, measured in litres per kW produced.

    .. attribute:: minimum_load
        The minimum capacity of the generator, defined between 0 (able to operate with
        any load) and 1 (only able to operate at maximum load).

    .. attribute:: name
        The name of the generator.

    """

    diesel_consumption: float
    minimum_load: float
    name: str


@dataclasses.dataclass
class DieselWaterHeater(Converter):
    """
    Represents a diesel water heater.

    .. attribute:: diesel_consumption
        The diesel consumption of the heater, measured in litres per kWth produced.

    .. attribute:: minimum_load
        The minimum capacity of the heater, defined between 0 (able to operate with any
        load) and 1 (only able to operate at maximum load).

    """

    def __init__(
        self,
        input_resource_consumption: Dict[ResourceType, float],
        maximum_output_capacity: float,
        minimum_load: float,
        name: str,
        output_resource_type: ResourceType,
    ) -> None:
        """
        Instnatiate a :class:`DieselWaterHeater` instance.

        Inputs:
            - input_resource_types:
                The types of load inputted to the d:class:`DieselWaterHeater`evice.
            - maximum_output_capcity:
                The maximum output capacity of the :class:`DieselWaterHeater`.
            - minimum_load:
                The minimum load that must be placed on the :class:`DieselWaterHeater`.
            - name:
                The name of the :class:`DieselWaterHeater`.
            - output_resource_type:
                The type of output produced by the :class:`DieselWaterHeater`.

        """

        # @BenWinchester - Waste consumption needed in this diesel water heater.
        super().__init__(
            input_resource_consumption,
            maximum_output_capacity,
            name,
            output_resource_type,
        )
        self.minimum_load = minimum_load

    @classmethod
    def from_dict(cls, input_data: Dict[str, Any], logger: logging.Logger) -> Any:
        """
        Instantiates a :class:`DieselWaterHeater` instance based on the input data.

        Inputs:
            - input_data:
                The input information, extracted from the diesel inputs YAML file.
            - logger:
                The :class:`logging.Logger` to use for the run.

        Outputs:
            - An instantiated :class:`DieselWaterHeater` based on the input information.

        """

        try:
            input_resource_consumption: Dict[ResourceType, float] = {
                ResourceType.DIESEL: input_data[DIESEL_CONSUMPTION],
                ResourceType.ELECTRIC: input_data[ELECTRIC_POWER]
                if ELECTRIC_POWER in input_data
                else 0,
            }
        except KeyError as e:
            logger.error(
                "%sMissing or invalid information for diesel water heater concerning "
                "its fuel and/or electricity consumption: %s%s",
                BColours.fail,
                str(e),
                BColours.endc,
            )
            raise InputFileError(
                "diesel inputs", "Missing diesel water heater resource inputs."
            ) from None

        return cls(
            input_resource_consumption,
            input_data[MAXIMUM_OUTPUT],
            input_data[MINIMUM_LOAD],
            input_data[NAME],
            ResourceType.HEAT,
        )

    @property
    def diesel_consumption(self) -> float:
        """
        Returns the diesel-fuel consumption of the :class:`DieselWaterHeater`.

        Outputs:
            - The diesel fuel consumption of the :class:`DieselWaterHeater`.

        """

        return self.input_resource_consumption[ResourceType.DIESEL]


def _find_deficit_threshold_blackout(
    unmet_energy: pd.DataFrame, blackouts: pd.DataFrame, backup_threshold: float
) -> Optional[float]:
    """
    Identifies the threshold energy level at which the diesel backup generator turns on
    when the threshold criterion is blackouts.

    Inputs:
        - backup_threshold:
            Desired level of reliability after diesel backup
        - blackouts:
            Current blackout profile before diesel backup
        - unmet_energy:
            Load profile of currently unment energy

    Outputs:
        - energy_threshold:
            The energy threshold (kWh) at which the diesel backup switches on.

    """

    # Find the blackout percentage
    blackout_percentage = float(blackouts.mean(axis=0))  # type: ignore

    # Find the difference in reliability
    reliability_difference = blackout_percentage - backup_threshold
    percentile_threshold = 100.0 * (1.0 - reliability_difference)

    if reliability_difference <= 0.0:
        return None

    return float(np.percentile(unmet_energy, percentile_threshold))


def _find_deficit_threshold_unmet(
    unmet_energy: pd.DataFrame, backup_threshold: float, total_electric_load: float
) -> Optional[float]:
    """
    Identifies the threshold energy level at which the diesel backup generator turns on
    when the threshold criterion is unmet energy.

    Inputs:
        - backup_threshold:
            Desired level of reliability after diesel backup
        - unmet_energy:
            Load profile of currently unment energy
        - total_electric_load:
            The total electric load placed on the system (kWh).

    Outputs:
        - energy_threshold:
            The energy threshold (kWh) at which the diesel backup switches on.

    """

    # Find the blackout percentage
    unmet_energy_percentage = float(np.sum(unmet_energy) / total_electric_load)  # type: ignore

    # Find the difference in reliability
    reliability_difference = unmet_energy_percentage - backup_threshold

    if reliability_difference <= 0:
        return None

    # Sort unmet energy by smallest first
    sorted_unmet_energy = sorted(unmet_energy.values)

    # Loop through hours attributing unmet energy to diesel generator (largest first)
    attributed_unmet_energy: float = 0
    energy_threshold: float

    while attributed_unmet_energy < total_electric_load * reliability_difference:
        energy_threshold = sorted_unmet_energy.pop()
        attributed_unmet_energy += energy_threshold

    return energy_threshold


def _find_deficit_threshold(
    unmet_energy: pd.DataFrame,
    blackouts: pd.DataFrame,
    backup_threshold: float,
    total_electric_load: float,
    diesel_mode: DieselMode,
) -> Optional[float]:
    """
    Identifies the threshold energy level at which the diesel backup generator turns on.

    Inputs:
        - backup_threshold:
            Desired level of reliability after diesel backup
        - blackouts:
            Current blackout profile before diesel backup
        - diesel_mode:
            The diesel mode used in the scenario inputs file
        - unmet_energy:
            Load profile of currently unment energy
        - total_electric_load:
            The total electric load placed on the system (kWh).

    Outputs:
        - energy_threshold:
            The energy threshold (kWh) at which the diesel backup switches on, `None` if
            the diesel generator should not turn on.

    """

    # Find the blackout percentage is mode using blackout criterion
    if diesel_mode == DieselMode.BACKUP:
        return _find_deficit_threshold_blackout(
            unmet_energy, blackouts, backup_threshold
        )

    # Find the blackout percentage is mode using unmet energy criterion
    if diesel_mode == DieselMode.BACKUP_UNMET:
        return _find_deficit_threshold_unmet(
            unmet_energy, backup_threshold, total_electric_load
        )

    raise ProgrammerJudgementFault(
        "src.clover.simulation.diesel::_find_deficit_threshold",
        "Cannot find deficit threshold for non-backup scenarios.",
    )


def get_diesel_energy_and_times(
    unmet_energy: pd.DataFrame,
    blackouts: pd.DataFrame,
    backup_threshold: float,
    total_electric_load: float,
    diesel_mode: DieselMode,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Finds times when the load is greater than the energy threshold.

    Calculates the times at which the diesel backup generator is used, and the energy
    output during those times

    Inputs:
        - backup_threshold:
            Desired level of reliability after diesel backup
        - blackouts:
            Current blackout profile before diesel backup
        - diesel_mode:
            The diesel mode used in the scenario inputs file
        - unmet_energy:
            Load profile of currently unment energy
        - total_electric_load:
            The total electric load placed on the system (kWh).

    Outputs:
        - diesel_energy:
            Profile of energy supplued by diesel backup
        - diesel_times:
            Profile of times when generator is on (1) or off (0)

    """

    energy_threshold = _find_deficit_threshold(
        unmet_energy, blackouts, backup_threshold, total_electric_load, diesel_mode
    )
    if energy_threshold is None:
        return pd.DataFrame([0] * len(unmet_energy)), pd.DataFrame(
            [0] * len(unmet_energy)
        )

    diesel_energy = pd.DataFrame(
        unmet_energy.values * (unmet_energy >= energy_threshold).values
    )
    diesel_times = (unmet_energy >= energy_threshold) * 1
    diesel_times = diesel_times.astype(float)

    return diesel_energy, diesel_times


def get_diesel_fuel_usage(
    capacity: int,
    diesel_generator: DieselGenerator,
    diesel_energy: pd.DataFrame,
    diesel_times: pd.DataFrame,
) -> pd.DataFrame:
    """
    Find diesel fuel consumption.

    Calculates the fuel usage of the diesel backup generator

    Inputs:
        - capacity:
            Capacity (kW) of the diesel generator.
        - diesel_generator:
            The diesel backup generator being modelled.
        - diesel_energy:
            Profile of energy supplued by diesel backup.
        - diesel_times:
            Profile of times when generator is on (1) or off (0).

    Outputs:
        - fuel_usage:
            Hourly profile of diesel fuel usage (litres).

    """

    load_factor: pd.DataFrame = diesel_energy.divide(capacity)  # type: ignore
    above_minimum = pd.DataFrame(
        load_factor.values * (load_factor > diesel_generator.minimum_load).values
    )
    below_minimum = (
        load_factor <= diesel_generator.minimum_load
    ) * diesel_generator.minimum_load
    # @@@ Investigate variable reassignment here.
    load_factor = pd.DataFrame(
        diesel_times.values * (above_minimum.values + below_minimum.values)
    )

    fuel_usage: pd.DataFrame = (
        load_factor * capacity * diesel_generator.diesel_consumption
    )
    fuel_usage = fuel_usage.astype(float)

    return fuel_usage
