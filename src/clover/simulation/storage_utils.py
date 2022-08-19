#!/usr/bin/python3
########################################################################################
# storage_utils.py - Storage utility module.                                           #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2022                                                      #
# Date created: 18/01/2022                                                             #
# License: Open source                                                                 #
# Most recent update: 18/01/2022                                                       #
########################################################################################
"""
storage_utils.py - The storage utility module for CLOVER.

CLOVER considers several storage media for various forms of energy. These are all
contained and considered within this module.

"""

import dataclasses

from typing import Any, Dict

from ..__utils__ import (
    HEAT_CAPACITY_OF_WATER,
    NAME,
    ResourceType,
)

__all__ = (
    "Battery",
    "CleanWaterTank",
    "HotWaterTank",
)


# Default storage unit:
#   The default unit size, in kWh, of the batteries being considered.
DEFAULT_STORAGE_UNIT = 1  # [kWh]


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

    label: str
    resource_type: ResourceType

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
        self.leakage: float = leakage
        self.maximum_charge: float = maximum_charge
        self.minimum_charge: float = minimum_charge
        self.name: str = name

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
            storage_data[NAME],
        )


@dataclasses.dataclass
class Battery(_BaseStorage, label="battery", resource_type=ResourceType.ELECTRIC):
    """
    Represents a battery within CLOVER.

    .. attribute:: capacity
        The capacity of the battery in kWh.

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

    .. attribute:: storage_unit
        The storage_unit of the :class:`Battery`, measured in kWh.

    """

    def __init__(
        self,
        capacity: float,
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
        storage_unit: float,
        storage_unit_overrided: bool,
    ) -> None:
        """
        Instantiate a :class:`Battery` instance.

        Inputs:
            - capacity:
                The capacity of the battery in kWh.
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
            - storage_unit:
                The storage_unit of the :class:`Battery` in kWh.
            - storage_unit_overrided:
                Whether the default storage unit has been overrided (True) or not
                (False).

        """

        super().__init__(cycle_lifetime, leakage, maximum_charge, minimum_charge, name)
        self.capacity: float = capacity
        self.charge_rate: float = charge_rate
        self.conversion_in: float = conversion_in
        self.conversion_out: float = conversion_out
        self.discharge_rate: float = discharge_rate
        self.lifetime_loss: float = lifetime_loss
        self.storage_unit = storage_unit
        self.storage_unit_overrided = storage_unit_overrided

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
            + f"capacity={self.capacity}, "
            + f"cycle_lifetime={self.cycle_lifetime} cycles, "
            + f"leakage={self.leakage}, "
            + f"maximum_charge={self.maximum_charge}, "
            + f"minimum_charge={self.minimum_charge}, "
            + f"charge_rate={self.charge_rate}, "
            + f"discharge_rate={self.discharge_rate}, "
            + f"conversion_in={self.conversion_in}, "
            + f"conversion_out={self.conversion_out}, "
            + f"lifetime_loss={self.lifetime_loss}, "
            + f"size={self.storage_unit} kWh"
            + ")"
        )

    def __repr__(self) -> str:
        """
        Defines the default representation of the :class:`Battery` instance.

        Outputs:
            - A `str` giving the default representation of the :class:`Battery`
              instance.

        """

        return (
            "Battery("
            + f"{self.label} storing {self.resource_type.value} loads, "
            + f"name={self.name}, capacity={self.capacity}"
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
            storage_data["capacity"] if "capacity" in storage_data else 1,
            storage_data["cycle_lifetime"],
            storage_data["leakage"],
            storage_data["maximum_charge"],
            storage_data["minimum_charge"],
            storage_data[NAME],
            storage_data["c_rate_charging"],
            storage_data["conversion_in"],
            storage_data["conversion_out"],
            storage_data["c_rate_discharging"],
            storage_data["lifetime_loss"],
            storage_data["storage_unit"]
            if "storage_unit" in storage_data
            else DEFAULT_STORAGE_UNIT,
            "storage_unit" in storage_data,
        )


@dataclasses.dataclass
class CleanWaterTank(
    _BaseStorage, label="clean_water_tank", resource_type=ResourceType.CLEAN_WATER
):
    """
    Represents a clean-water tank within CLOVER.

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
                The number of cycles for which the :class:`CleanWaterTank` instance can
                perform.
            - leakage:
                The rate of leakage from the storage.
            - maximum_charge:
                The maximum level that can be held by the :class:`CleanWaterTank`.
            - minimum_charge:
                The minimum level to which the :class:`CleanWaterTank` instance can
                discharge.
            - name:
                The name to assign to the :class:`CleanWaterTank` instance.
            - mass:
                The mass of water that can be held in the clean-water tank.

        """

        super().__init__(cycle_lifetime, leakage, maximum_charge, minimum_charge, name)
        self.mass: float = mass

    def __str__(self) -> str:
        """
        Returns a nice-looking string describing the :class:`CleanWaterTank` instance.

        Outputs:
            - A `str` giving information about the :class:`CleanWaterTank` instance.

        """

        return (
            "CleanWaterTank("
            + f"{self.label} storing {self.resource_type.value} loads, "
            + f"name={self.name}, "
            + f"capacity={self.mass} litres, "
            + f"cycle_lifetime={self.cycle_lifetime} cycles, "
            + f"leakage={self.leakage}, "
            + f"maximum_charge={self.maximum_charge}, "
            + f"minimum_charge={self.minimum_charge}"
            + ")"
        )

    def __repr__(self) -> str:
        """
        Defines the default representation of the :class:`CleanWaterTank` instance.

        Outputs:
            - A `str` giving the default representation of the :class:`CleanWaterTank`
              instance.

        """

        return (
            "CleanWaterTank("
            + f"{self.label} storing {self.resource_type.value} loads, "
            + f"name={self.name}"
            + ")"
        )

    @classmethod
    def from_dict(cls, storage_data: Dict[str, Any]) -> Any:
        """
        Create a :class:`CleanWaterTank` instance based on the file data passed in.

        Inputs:
            - storage_data:
                The tank data, extracted from the relevant input file.

        Outputs:
            - A :class:`CleanWaterTank` instance.

        """

        return cls(
            storage_data["cycle_lifetime"],
            storage_data["leakage"],
            storage_data["maximum_charge"],
            storage_data["minimum_charge"],
            storage_data[NAME],
            storage_data["mass"],
        )


@dataclasses.dataclass
class HotWaterTank(
    CleanWaterTank, label="hot_water_tank", resource_type=ResourceType.HOT_CLEAN_WATER
):
    """
    Represents a hot-water tank within CLOVER.

    .. attribute:: area
        The area of the hot-water tank, measured in meters squared.

    .. attribute:: heat_capacity
        The specific heat capacity of the contents of the tank, measured in Joules per
        kilogram Kelvin, defaults to that of water at stp.

    .. attribute:: heat_loss_coefficient
        The heat loss from the tank, measured in Watts per meter squared per Kelvin.

    .. attribute:: heat_transfer_coefficient
        The heat transfer coefficient from the tank to its surroundings, measured in
        Watts per Kelvin.

    """

    def __init__(
        self,
        cycle_lifetime: int,
        leakage: float,
        maximum_charge: float,
        minimum_charge: float,
        name: str,
        mass: float,
        area: float,
        heat_capacity: float,
        heat_loss_coefficient: float,
    ) -> None:
        """
        Instantiate a :class:`CleanWaterTank`.

        Inputs:
            - cycle_lifetime:
                The number of cycles for which the :class:`HotWaterTank` instance can
                perform.
            - leakage:
                The rate of leakage from the storage.
            - maximum_charge:
                The maximum level that can be held by the :class:`HotWaterTank`.
            - minimum_charge:
                The minimum level to which the :class:`HotWaterTank` instance can
                discharge.
            - name:
                The name to assign to the :class:`HotWaterTank` instance.
            - mass:
                The mass of water that can be held in the clean-water tank.
            - area:
                The surface area of the tank.
            - heat_capacity:
                The specific heat capacity of the contents of the :class:`HotWaterTank`.
            - heta_loss_coefficient:
                The heat-loss coefficient for the :class:`HotWaterTank`.

        """

        super().__init__(
            cycle_lifetime, leakage, maximum_charge, minimum_charge, name, mass
        )
        self.area = area
        self.heat_capacity = heat_capacity
        self.heat_loss_coefficient = heat_loss_coefficient

    @property
    def heat_transfer_coefficient(self) -> float:
        """
        Return the heat-transfer coefficient from the :class:`HotWaterTank`.

        Outputs:
            - The heat-transfer coefficient from the :class:`HotWaterTank` to its
              surroundings, measured in Watts per Kelvin.

        """

        return self.heat_loss_coefficient * self.area

    def __str__(self) -> str:
        """
        Returns a nice-looking string describing the :class:`HotWaterTank` instance.

        Outputs:
            - A `str` giving information about the :class:`HotWaterTank` instance.

        """

        return (
            "HotWaterTank("
            + f"{self.label} storing {self.resource_type.value} loads, "
            + f"name={self.name}, "
            + f"area={self.area} m^2, "
            + f"capacity={self.mass} litres, "
            + f"cycle_lifetime={self.cycle_lifetime} cycles, "
            + f"heat_capacity={self.heat_capacity} J/kg*K, "
            + f"heat_loss_coefficient={self.heat_loss_coefficient} W/m^2K, "
            + f"heat_transfer_coefficient={self.heat_transfer_coefficient} W/K, "
            + f"leakage={self.leakage}, "
            + f"maximum_charge={self.maximum_charge}, "
            + f"minimum_charge={self.minimum_charge}"
            + ")"
        )

    def __repr__(self) -> str:
        """
        Defines the default representation of the :class:`HotWaterTank` instance.

        Outputs:
            - A `str` giving the default representation of the :class:`HotWaterTank`
              instance.

        """

        return (
            "HotWaterTank("
            + f"{self.label} storing {self.resource_type.value} loads, "
            + f"name={self.name}"
            + ")"
        )

    @classmethod
    def from_dict(cls, storage_data: Dict[str, Any]) -> Any:
        """
        Create a :class:`HotWaterTank` instance based on the file data passed in.

        Inputs:
            - storage_data:
                The tank data, extracted from the relevant input file.

        Outputs:
            - A :class:`HotWaterTank` instance.

        """

        return cls(
            storage_data["cycle_lifetime"],
            storage_data["leakage"],
            storage_data["maximum_charge"],
            storage_data["minimum_charge"],
            storage_data[NAME],
            storage_data["mass"],
            storage_data["area"],
            storage_data["heat_capacity"]
            if "heat_capacity" in storage_data
            else HEAT_CAPACITY_OF_WATER,
            storage_data["heat_loss_coefficient"],
        )
