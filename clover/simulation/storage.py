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

import dataclasses

from typing import Any, Dict, List, Optional

from ..__utils__ import ResourceType

__all__ = ("Battery",)


@dataclasses.dataclass
class _BaseStorage:
    """
    Repsesents an abstract base storage unit.

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

    .. attribute:: name
        A unique name for identifying the battery.

    """

    cycle_lifetime: int
    leakage: float
    maximum_charge: float
    minimum_charge: float
    name: str

    def __hash__(self) -> int:
        """
        Return a unique hash identifying the :class:`_BaseStorage` instance.

        Outputs:
            - Return a unique hash identifying the :class:`_BaseStorage` instance.

        """

        return hash(self.name)

    def __init_subclass__(cls, label: str, resource_type: ResourceType) -> None:
        """
        Method run when a :class:`_BaseStorage` child is instantiated.

        Inputs:
            - label:
                A `str` that identifies the class type.
            - resource_type:
                The type of load being modelled.

        """

        super().__init_subclass__()
        cls.label = label
        cls.resource_type = resource_type

    def __str__(self) -> str:
        """
        Returns a nice-looking string describing the :class:`_BaseStorage` instance.

        Outputs:
            - A `str` giving information about the :class:`_BaseStorage` instance.

        """

        return (
            "Storage("
            + f"{self.label} storing {self.resource_type.value} loads, "
            + f"name={self.name}, "
            + f"cycle_lifetime={self.cycle_lifetime} cycles, "
            + f"leakage={self.leakage}, "
            + f"maximum_charge={self.maximum_charge}, "
            + f"minimum_charge={self.minimum_charge}"
            + ")"
        )

    @classmethod
    def from_dict(cls, storage_data: Dict[str, Any]) -> Any:
        """
        Create a :class:`_BaseStorage` instance based on the file data passed in.

        Inputs:
            - storage_data:
                The storage data, extracted from the relevant input file.

        Outputs:
            - A :class:`_BaseStorage` instance.

        """

        return cls(
            storage_data["cycle_lifetime"],
            storage_data["leakage"],
            storage_data["maximum_charge"],
            storage_data["minimum_charge"],
            storage_data["name"],
        )


@dataclasses.dataclass
class Battery(_BaseStorage, label="battery", resource_type=ResourceType.ELECTRIC):
    """
    Represents a battery within CLOVER.

    """

    charge_rate: float
    conversion_in: float
    conversion_out: float
    discharge_rate: float
    lifetime_loss: float

    def __str__(self) -> str:
        """
        Returns a nice-looking string describing the :class:`_BaseStorage` instance.

        Outputs:
            - A `str` giving information about the :class:`_BaseStorage` instance.

        """

        return (
            "Battery("
            + f"{self.label} storing {self.resource_type.value} loads, "
            + f"name={self.name}, "
            + f"cycle_lifetime={self.cycle_lifetime} cycles, "
            + f"leakage={self.leakage}, "
            + f"maximum_charge={self.maximum_charge}, "
            + f"minimum_charge={self.minimum_charge}, "
            + f"charge_rate={self.charge_rate}, "
            + f"discharge_rate={self.discharge_rate}, "
            + f"conversion_in={self.conversion_in}, "
            + f"conversion_out={self.conversion_out}, "
            + f"lifetime_loss={self.lifetime_loss}"
            + ")"
        )

    @classmethod
    def from_dict(cls, storage_data: Dict[str, Any]) -> Any:
        """
        Create a :class:`Battery` instance based on the file data passed in.

        Inputs:
            - storage_data:
                The battery data, extracted from the relevant input file.

        Outputs:
            - A :class:`Battery` instance.

        """

        return cls(
            storage_data["cycle_lifetime"],
            storage_data["leakage"],
            storage_data["maximum_charge"],
            storage_data["minimum_charge"],
            storage_data["name"],
            storage_data["c_rate_charging"],
            storage_data["conversion_in"],
            storage_data["conversion_out"],
            storage_data["c_rate_discharging"],
            storage_data["lifetime_loss"],
        )


@dataclasses.dataclass
class CleanWaterTank(
    _BaseStorage, label="clean_water_tank", resource_type=ResourceType.CLEAN_WATER
):
    """
    Represents a clean-water tank within CLOVER.

    .. attribute:: mass
        The mass of clean water stored within the tank.

    """

    mass: float

    def __str__(self) -> str:
        """
        Returns a nice-looking string describing the :class:`_BaseStorage` instance.

        Outputs:
            - A `str` giving information about the :class:`_BaseStorage` instance.

        """

        return (
            "CleanWaterTank("
            + f"{self.label} storing {self.resource_type.value} loads, "
            + f"name={self.name}, "
            + f"cycle_lifetime={self.cycle_lifetime} cycles, "
            + f"leakage={self.leakage}, "
            + f"maximum_charge={self.maximum_charge}, "
            + f"minimum_charge={self.minimum_charge}, "
            + f"capacity={self.mass} litres"
            + ")"
        )

    @classmethod
    def from_dict(cls, storage_data: Dict[str, Any]) -> Any:
        """
        Create a :class:`Tank` instance based on the file data passed in.

        Inputs:
            - storage_data:
                The tank data, extracted from the relevant input file.

        Outputs:
            - A :class:`Tank` instance.

        """

        return cls(
            storage_data["cycle_lifetime"],
            storage_data["leakage"],
            storage_data["maximum_charge"],
            storage_data["minimum_charge"],
            storage_data["name"],
            storage_data["mass"],
        )
