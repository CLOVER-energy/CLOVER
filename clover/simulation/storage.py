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

from ..__utils__ import InternalError, ResourceType

__all__ = ("Battery",)


class _BaseStorage:
    """
    Repsesents an abstract base storage unit.

    .. attribute:: cycle_lifetime
        The number of cycles for which the :class:`_BaseStorage` can perform.

    .. attribute:: label
        The label given to the :class:`_BaseStorage` instance.

    .. attribute:: leakage
        The rate of level leakage from the :class:`_BaseStorage`.

    .. attribute:: maximum_charge
        The maximum level of the :class:`_BaseStorage`, defined between 0 (able to hold
        no charge) and 1 (able to fully charge).

    .. attribute:: minimum_charge
        The minimum level of the :class:`_BaseStorage`, defined between 0 (able to fully
        discharge) and 1 (unable to discharge any amount).

    .. attribute:: name
        A unique name for identifying the :class:`_BaseStorage`.

    .. attribute:: resource_type
        The type of resource being stored by the :class:`_BaseStorage` instance.

    """

    def __init__(
        self,
        cycle_lifetime: int,
        leakage: float,
        maximum_charge: float,
        minimum_charge: float,
        name: str,
    ) -> None:
        """
        Instantiate a :class:`Storage` instance.

        Inputs:
            - cycle_lifetime:
                The number of cycles for which the :class:`Storage` instance can
                perform.
            - leakage:
                The rate of leakage from the storage.
            - maximum_charge:
                The maximum level that can be held by the :class:`_BaseStorage`.
            - minimum_charge:
                The minimum level to which the :class:`_BaseStorage` instance can
                discharge.
            - name:
                The name to assign to the :class:`Storage` instance.

        """

        self.cycle_lifetime: int = cycle_lifetime
        self.label: Optional[str] = None
        self.leakage: float = leakage
        self.maximum_charge: float = maximum_charge
        self.minimum_charge: float = minimum_charge
        self.name: str = name
        self.resource_type: Optional[ResourceType] = None

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

    .. attribute:: charge_rate
        The rate of charge of the :class:`Battery`.

    .. attribute:: conversion_in
        The input conversion efficiency of the :class:`Battery`.

    .. attribute:: conversion_out
        The output conversion efficiency of the :class:`Battery`.

    .. attribute:: discharge_rate
        The rate of discharge of the :class:`Battery`.

    .. attribute:: lifetime_loss
        The overall loss in capacity of the :class:`Battery` over its lifetime.

    """

    def __init__(
        self,
        cycle_lifetime: int,
        leakage: float,
        maximum_charge: float,
        minimum_charge: float,
        name: str,
        charge_rate: float,
        conversion_in: float,
        conversion_out: float,
        discharge_rate: float,
        lifetime_loss: float,
    ) -> None:
        """
        Instantiate a :class:`Battery` instance.

        Inputs:
            - cycle_lifetime:
                The number of cycles for which the :class:`Battery` instance can
                perform.
            - leakage:
                The rate of leakage from the storage.
            - maximum_charge:
                The maximum level that can be held by the :class:`Battery`.
            - minimum_charge:
                The minimum level to which the :class:`Battery` instance can
                discharge.
            - name:
                The name to assign to the :class:`Battery` instance.
            - charge_rate:
                The rate of charge of the :class:`Battery`.
            - conversion_in:
                The efficiency of conversion of energy into the :class:`Battery`.
            - conversion_out:
                The efficiency of conversion of energy out of the :class:`Battery`.
            - discharge_rate:
                The rate of discharge of the :class:`Battery`.
            - lifetime_loss:
                The loss in capacity of the :class:`Battery` over its lifetime.

        """

        super().__init__(cycle_lifetime, leakage, maximum_charge, minimum_charge, name)
        self.charge_rate: float = charge_rate
        self.conversion_in: float = conversion_in
        self.conversion_out: float = conversion_out
        self.discharge_rate: float = discharge_rate
        self.lifetime_loss: float = lifetime_loss

    def __str__(self) -> str:
        """
        Returns a nice-looking string describing the :class:`_BaseStorage` instance.

        Outputs:
            - A `str` giving information about the :class:`_BaseStorage` instance.

        """

        return (
            "Battery("
            + f"{self.label} storing {self.resource_type.value} loads, "  # type: ignore
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

    def __init__(
        self,
        cycle_lifetime: int,
        leakage: float,
        maximum_charge: float,
        minimum_charge: float,
        name: str,
        mass: float,
    ) -> None:
        """
        Instantiate a :class:`CleanWaterTank`.

        Inputs:
            - cycle_lifetime:
                The number of cycles for which the :class:`Battery` instance can
                perform.
            - leakage:
                The rate of leakage from the storage.
            - maximum_charge:
                The maximum level that can be held by the :class:`Battery`.
            - minimum_charge:
                The minimum level to which the :class:`Battery` instance can
                discharge.
            - name:
                The name to assign to the :class:`Battery` instance.
            - mass:
                The mass of water that can be held in the clean-water tank.

        """

        super().__init__(cycle_lifetime, leakage, maximum_charge, minimum_charge, name)
        self.mass: float = mass

    def __str__(self) -> str:
        """
        Returns a nice-looking string describing the :class:`_BaseStorage` instance.

        Outputs:
            - A `str` giving information about the :class:`_BaseStorage` instance.

        """

        return (
            "CleanWaterTank("
            + f"{self.label} storing {self.resource_type.value} loads, "  # type: ignore
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
