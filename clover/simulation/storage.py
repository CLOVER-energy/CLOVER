#!/usr/bin/python3
########################################################################################
# storage.py - Storage module.                                                         #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2020                                                      #
# Date created: 16/07/2021                                                             #
# License: Open source                                                                 #
# Most recent update: 16/07/2021                                                       #
#                                                                                      #
"""
storage.py - The storage module for CLOVER.

CLOVER considers several storage media for various forms of energy. These are all
contained and considered within this module.

"""

from typing import Any, Dict

__all__ = ("Battery",)


class Battery:
    """
    Represents a battery within CLOVER.

    .. attribute:: charge_rate
        The rate of charge of the battery.

    .. attribute:: conversion_in
        The efficiency of conversion of energy being inputted to the battery, defined
        between 0 (no energy converted) and 1 (all energy converted without losses).

    .. attribute:: conversion_out
        The efficiency of conversion of energy being drawn out from the battery, defined
        between 0 (no energy converted) and 1 (all energy converted without losses).

    .. attribute:: cycle_lifetime
        The number of cycles for which the battery can perform.

    .. attribute:: discharge_rate
        The rate of discharge of the battery.

    .. attribute:: leakage
        The rate of charge leakage from the battery.

    .. attribute:: maximum_charge
        The maximum charge level of the battery, defined between 0 (able to hold no
        charge) and 1 (able to fully charge).

    .. attribute:: minimum_charge
        The minimum charge level of the battery, defined between 0 (able to fully
        discharge) and 1 (unable to discharge any amount).

    """

    def __init__(
        self,
        charge_rate: float,
        conversion_in: float,
        conversion_out: float,
        cycle_lifetime: int,
        discharge_rate: float,
        leakage: float,
        lifetime_loss: float,
        maximum_charge: float,
        minimum_charge: float,
    ) -> None:
        """
        Instantiate a :class:`Battery` instance based on the parameters passed in.

        Inputs:
            - charge_rate
                The rate of charge of the battery.
            - conversion_in
                The efficiency of conversion of energy being inputted to the battery, defined
                between 0 (no energy converted) and 1 (all energy converted without losses).
            - conversion_out
                The efficiency of conversion of energy being drawn out from the battery, defined
                between 0 (no energy converted) and 1 (all energy converted without losses).
            - cycle_lifetime
                The number of cycles for which the battery can perform.
            - discharge_rate
                The rate of discharge of the battery.
            - leakage
                The rate of charge leakage from the battery.
            - lifetime_loss
                The lifetime loss from the battery.
            - maximum_charge
                The maximum charge level of the battery, defined between 0 (able to hold no
                charge) and 1 (able to fully charge).
            - minimum_charge
                The minimum charge level of the battery, defined between 0 (able to fully
                discharge) and 1 (unable to discharge any amount).

        """

        self.charge_rate = charge_rate
        self.conversion_in = conversion_in
        self.conversion_out = conversion_out
        self.cycle_lifetime = cycle_lifetime
        self.discharge_rate = discharge_rate
        self.leakage = leakage
        self.lifetime_loss = lifetime_loss
        self.maximum_charge = maximum_charge
        self.minimum_charge = minimum_charge

    def __str__(self) -> str:
        """
        Returns a nice-looking string describing the :class:`Battery` instance.

        Outputs:
            - A `str` giving information about the :class:`Battery` instance.

        """

        return (
            "Battery("
            + f"charge_rate={self.charge_rate}, "
            + f"discharge_rate={self.discharge_rate}, "
            + f"conversion_in={self.conversion_in}, "
            + f"conversion_out={self.conversion_out}, "
            + f"cycle_lifetime={self.cycle_lifetime} cycles, "
            + f"leakage={self.leakage}, "
            + f"lifetime_loss={self.lifetime_loss}, "
            + f"maximum_charge={self.maximum_charge}, "
            + f"minimum_charge={self.minimum_charge}"
            + ")"
        )

    @classmethod
    def from_dict(cls, battery_data: Dict[str, Any]) -> Any:
        """
        Create a :class:`Battery` instance based on the file data passed in.

        Inputs:
            - battery_data:
                The battery data, extracted from the relevant input file.

        Outputs:
            - A :class:`Battery` instance.

        """

        return cls(
            battery_data["c_rate_charging"],
            battery_data["conversion_in"],
            battery_data["conversion_out"],
            battery_data["cycle_lifetime"],
            battery_data["c_rate_discharging"],
            battery_data["leakage"],
            battery_data["lifetime_loss"],
            battery_data["maximum_charge"],
            battery_data["minimum_charge"],
        )
