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

from collections import defaultdict
import dataclasses
import logging

from typing import Any, Dict, List, Optional, Tuple

import numpy as np  # pylint: disable=import-error
import pandas as pd

from ..__utils__ import (
    BColours,
    DieselMode,
    DieselSetting,
    ELECTRIC_POWER,
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
    "find_cycle_charging_threshold",
    "get_cycle_charging_energy",
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
        The diesel consumption of the generator, measured in litres per kWh produced.

    .. attribute:: minimum_load
        The minimum capacity of the generator, defined between 0 (able to operate with
        any load) and 1 (only able to operate at maximum load).

    .. attribute:: name
        The name of the generator.

    """

    diesel_consumption: float
    minimum_load: float
    name: str

    capacity: Optional[float] = None
    _setting_map: Optional[Dict[int, DieselSetting]] = None

    def get_setting(
        self, hour: int, diesel_settings: List[DieselSetting]
    ) -> DieselSetting:
        """
        Gets the diesel setting for the current hour and computes the mapping first time

        Inputs:
            - hour:
                The hour of the simulation.
            - diesel_settings:
                The `list` of valid diesel settings.

        Outputs:
            The diesel setting for this hour.

        Raises:
            InputFileError:
                If there are any invalid inputs in the diesel scenario file.

        """

        # If the diesel setting map has been computed, use the value from the map.
        if self._setting_map is not None:
            return self._setting_map[hour % 24]

        # If there are no diesel settings, raise an error.
        if len(diesel_settings) == 0:
            raise InputFileError(
                "diesel scenario",
                "No diesel settings were specified despite cycle charging being "
                "requested.",
            )

        # Compute the map
        valid_settings: Dict[int, List[DieselSetting]] = defaultdict(list)

        for hour in range(24):
            for diesel_setting in diesel_settings:
                # If the diesel settings don't run overnight.
                if diesel_setting.start_hour < diesel_setting.end_hour:
                    if diesel_setting.start_hour <= hour < diesel_setting.end_hour:
                        valid_settings[hour].append(diesel_setting)
                # If the diesel settings run across the day boundary.
                else:
                    if (
                        hour < diesel_setting.end_hour
                        or hour >= diesel_setting.start_hour
                    ):
                        valid_settings[hour].append(diesel_setting)

        # Raise an error if there are overlapping settings.
        if any(len(settings) > 1 for settings in valid_settings.values()):
            raise InputFileError(
                "diesel scenario", "Diesel settings should not be overlapping."
            )

        # Save the map
        self._setting_map = {key: value[0] for key, value in valid_settings.items()}

        # Return the current value from the map
        return self._setting_map[hour % 24]


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


def find_cycle_charging_threshold(
    previous_hour_operational: bool, setting: DieselSetting
) -> float:
    """
    Calcualtes the threshold for the cycle charging for the respective hour.

    Inputs:
        - previous_hour_operational:
            Whether the diesel generator was operating at the previous hour.
        - setting:
            The thresholds for the given hour, stored as a :class:`DieselSetting`
            instance.

    Outputs:
        - The threshold value in fraction of battery charge (0.0 - 1.0).

    """

    if previous_hour_operational:
        return setting.max_soc
    return setting.min_soc


def get_cycle_charging_energy(
    empty_capacity: float,
    max_diesel_energy_into_battery: float,
    max_diesel_output: float,
    min_diesel_energy_into_battery: float,
) -> Tuple[float, float, float]:
    """
    Calculate cycle-charging storage parameters.

    This function takes the empty capacity and the battery in-and-out C-rates, and it
    uses the diesel minimum capacity factor, and it uses a variable which determines the
    maximum energy that the diesel generators can put into the batteries.

    1.  Based on the empty capacity:
        SWITCH:
        - empty_capacity < diesel_minimum:
            Fill to the empty
            WHERE you check for the input c-rate etc.
            and, as a result, we waste some diesel
        - diesel_minimum < empty_capacity < diesel_maximum:
            Fill to the empty, where no diesel is wasted and you *may* have surplus
            diesel to meet demand
        - diesel_maximum < empty_capacity:
            Fill to the diesel maximum
    2.  Return the variables required:
        - surplus = maximum_output of the diesel generator
          WHICH *might* be different from the maximum ammount of power that can go from
          the diesel generator into the batteries
          SUBTRACTING what was used

    Inputs:
        - empty_capacity:
            The empty capacity remaining in the batteries (kWh).
        - max_diesel_energy_into_battery:
            The maximum diesel energy into the battery.
        - max_diesel_output:
            The maximum power that the diesel generators can output.
        - min_diesel_energy_into_battery:
            The minimum diesel energy into the battery.

    Outputs:
        - diesel_total_output:
            The total power supplied by the diesel generator.
        - diesel_to_battery:
            The total power used by the diesel generator supplying the batteries.
        - surplus:
            Remaining energy that *could* have come from the diesel generator in this
            time step. I.E., if the diesel generator was not running at the maximum
            capacity, but it could have been, then this power is returned in case it can
            be utilised elsewhere in the system.

    """

    # If empty is less than minimum, the minimum limits the charging capability.
    if empty_capacity <= min_diesel_energy_into_battery:
        diesel_to_battery: float = empty_capacity  # [kW]
        diesel_total_output: float = min_diesel_energy_into_battery  # [kW]
    # If empty is in the range of diesel operation, fill to the empty.
    elif (
        min_diesel_energy_into_battery
        < empty_capacity
        <= max_diesel_energy_into_battery
    ):
        diesel_to_battery: float = empty_capacity  # [kW]
        diesel_total_output = diesel_to_battery
    # If empty is more than can be supplied, the diesel generator/c rate limits the
    # capability.
    else:
        diesel_to_battery = max_diesel_energy_into_battery
        diesel_total_output = diesel_to_battery

    # Calculate the surplus diesel energy that could have been supplied.
    surplus = max_diesel_output - diesel_to_battery

    return (diesel_total_output, diesel_to_battery, surplus)


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
