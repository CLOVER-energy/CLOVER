#!/usr/bin/python3
########################################################################################
# clinic.py - Health-centre clinic module                                              #
#                                                                                      #
# Author: Ilaria Del Frate                                                             #
# Copyright: Ilaria Del Frate, 2022                                                    #
# License: Open source                                                                 #
# Most recent update: 26/07/2022                                                       #
#                                                                                      #
# For more information, please email:                                                  #
#     philip.sandwell@gmail.com                                                        #
########################################################################################

"""
clinic.py - Works out the health centre load.

"""

import dataclasses
import os

from logging import Logger

from typing import Any, Dict, List

import numpy as np
import pandas as pd

import matplotlib.pyplot as plt


from ..__utils__ import (
    HOURS_PER_YEAR,
    BColours,
    DemandType,
    FAILED,
    InputFileError,
    Location,
    LOGGER_DIRECTORY,
)
from ..load.load import Device, process_load_profiles, ResourceType


__all__ = (
    "calculate_clinic_cooling_load",
    "Clinic",
)


@dataclasses.dataclass
class Clinic:
    """
    Represents a clinic.

    .. attribute:: name
        The name of the clinic
    .. attribute:: floor_area
        The name of the clinic
    .. attribute:: name
        The name of the clinic
    .. attribute:: name
        The name of the clinic
    .. attribute:: name
        The name of the clinic


    """

    name: str
    demand_type: DemandType

    # Transmission Load
    floor_area: float  # Tells python that a clinic has an area, and it's a number
    roof_area: float
    surface_area_walls: float
    surface_area_doors_windows: float
    u_value_walls: float
    u_value_windows_doors: float
    u_value_floor: float
    u_value_roof: float
    inside_ideal_temperature: float
    # outside_temperature: float

    # Internal heat load - people
    staff: float
    patients: float
    heat_loss_staff: float
    heat_loss_patients: float
    start_time_staff: List[int]
    end_time_staff: List[int]
    start_time_patients: List[int]
    end_time_patients: List[int]

    # Internal heat load - Lighting
    lamps_internal: float
    lamps_external: float
    start_time_lamps: List[int]
    end_time_lamps: List[int]
    time_lamps_external: float
    wattage_lamps: float

    # Fridge heat load
    fridge_wattage: float
    time_fridge: float

    # Infiltration loads
    changes: float
    volume_cold_store: float
    energy_new_air: float
    start_time_infiltration: List[int]
    end_time_infiltration: List[int]

    # run_hours: float

    cooling_device: str

    devices: List[Device]

    @classmethod
    def from_dict(cls, inputs: Dict[str, Any]) -> Any:
        """
        Instantiate a clinic based on the inputs.

        """

        # Create a list of devices.
        devices = [
            Device.from_dict(device_inputs) for device_inputs in inputs["devices"]
        ]

        # Create a clinic
        return cls(
            inputs["name"],
            DemandType(inputs["demand_type"]),
            inputs["floor_area"],
            inputs["roof_area"],
            inputs["surface_area_walls"],
            inputs["surface_area_doors_windows"],
            inputs["u_value_walls"],
            inputs["u_value_windows_doors"],
            inputs["u_value_floor"],
            inputs["u_value_roof"],
            inputs["inside_ideal_temperature"],
            inputs["staff"],
            inputs["patients"],
            inputs["heat_loss_staff"],
            inputs["heat_loss_patients"],
            inputs["start_time_staff"],
            inputs["end_time_staff"],
            inputs["start_time_patients"],
            inputs["end_time_patients"],
            inputs["lamps_internal"],
            inputs["lamps_external"],
            inputs["start_time_lamps"],
            inputs["end_time_lamps"],
            inputs["time_lamps_external"],
            inputs["wattage_lamps"],
            inputs["fridge_wattage"],
            inputs["time_fridge"],
            inputs["changes"],
            inputs["volume_cold_store"],
            inputs["energy_new_air"],
            inputs["start_time_infiltration"],
            inputs["end_time_infiltration"],
            inputs["cooling_device"],
            devices,
        )


# MY_PATH = "C:/Users/Ilaria/CLOVER/locations/Bahraich/inputs/simulation/"
# with open(MY_PATH + "clinic.yaml") as f:
# data_clinic = yaml.load(f, Loader=yaml.FullLoader)
#  print(data_clinic)


# MY_CLINIC: Clinic = Clinic(**data_clinic["clinics"][0])


# def import_weather_data(building: Clinic):

#     data = pd.read_csv("C:/Users/Ilaria/Desktop/weatherdata.csv")
#     temperature = data["temperature"]
#     # print(temperature)
#     return temperature.to_numpy()


# def import_weather_dataframe():
#     data = pd.read_csv("C:/Users/Ilaria/Desktop/weatherdata.csv", dtype={"local_time"})
#     return data


# temperatura = import_weather_data(building=Clinic)


# TESTED - WORKING
def transmission_load_walls(building: Clinic, temperature: float) -> float:
    """
    Computes the transmission load of the walls in kW for a building.

    """

    return (
        building.surface_area_walls  # [m^2]
        * building.u_value_walls  # [W/m^2*K]
        * (temperature - building.inside_ideal_temperature)  # [K]
        / 1000  # [W/kW]
    )  # [kW]


# TESTED - WORKING
def transmission_load_doors_windows(building: Clinic, temperature) -> float:
    """
    Computes the transmission load of the doors and windows in kW for a building.

    """

    return (
        building.surface_area_doors_windows  # [m^2]
        * building.u_value_windows_doors  # [W/m^2*K]
        * (temperature - building.inside_ideal_temperature)  # [K]
        / 1000  # [W/kW]
    )  # [kW]


# TESTED - WORKING
def transmission_load_floor(building: Clinic, temperature) -> float:
    """
    Computes the transmission load of the floor in kW for a building.

    """

    return (
        building.floor_area  # [m^2]
        * building.u_value_floor  # [W/m^2*K]
        * (temperature - building.inside_ideal_temperature)  # [K]
        / 1000  # [W/kW]
    )


# TESTED - WORKING
def transmission_load_roof(building: Clinic, temperature) -> float:
    """
    Computes the transmission load of the roof in kW for a building.

    """

    return (
        building.roof_area  # [m^2]
        * building.u_value_roof  # [W/m^2*K]
        * (temperature - building.inside_ideal_temperature)  # [K]
        / 1000  # [W/kW]
    )  # [kW]


# TESTED - WORKING
def calculate_transmission_load(building: Clinic, temperature) -> float:
    """
    Computes the total transmission heat load in kW for a building.

    """

    t1 = transmission_load_walls(building, temperature)
    t2 = transmission_load_doors_windows(building, temperature)
    t3 = transmission_load_floor(building, temperature)
    t4 = transmission_load_roof(building, temperature)

    return t1 + t2 + t3 + t4


# TESTED - WORKING
def internal_load_staff(building: Clinic, current_hour: int) -> float:
    """
    Computes the internal heat load of the nurses in kW for a building at time t.

    """

    weekday: int = (current_hour // 24) % 7
    start_time: int = building.start_time_staff[weekday]
    end_time: int = building.end_time_staff[weekday]

    if start_time <= (current_hour % 24) < end_time:
        return building.staff * building.heat_loss_staff / 1000
    return 0


# TESTED - WORKING
def internal_load_patients(building: Clinic, current_hour: float) -> float:
    """
    Computes the internal heat load of the patients and accompainers in kW for a building.

    """

    weekday: int = (current_hour // 24) % 7
    start_time: int = building.start_time_patients[weekday]
    end_time: int = building.end_time_patients[weekday]

    if start_time <= (current_hour % 24) < end_time:
        return building.patients * building.heat_loss_patients / 1000
    return 0


# TESTED - WORKING
def calculate_internal_load_people(buliding: Clinic, current_hour: int) -> float:
    """
    Computes the internal heat load of the total people in kW for a building.

    """

    staff_load = internal_load_staff(buliding, current_hour)
    patient_load = internal_load_patients(buliding, current_hour)

    return staff_load + patient_load


# calculate_internal_load_people(MY_CLINIC)


# COME BACK TO THIS
def internal_load_lighting(building: Clinic):
    """
    Computes the internal heat load of the lamps in kW for a building,
    the wattage is halved as the dissipation of energy only corresponds to 50% in LEDs.

    """
    lamps_at_times = [
        [
            [0, building.lamps_internal * building.wattage_lamps / 2][
                t > start and t < end
            ]
            for t in range(24)
        ]
        for start, end in zip(building.start_time_lamps, building.end_time_lamps)
    ]
    return lamps_at_times


# COME BACK TO THIS
def fridge_load(building: Clinic):
    """
    Computes the internal heat load of the fridge in kW for a building.

    """

    return building.fridge_wattage * building.time_fridge / 1000


# TESTED - WORKING
def infiltration_load(building: Clinic, current_hour: int, temperature: float) -> float:
    """
    Computes the infiltration load in kW for a building.

    """

    weekday: int = (current_hour // 24) % 7
    start_time: int = building.start_time_infiltration[weekday]
    end_time: int = building.end_time_infiltration[weekday]

    if start_time <= (current_hour % 24) < end_time:
        return (
            building.changes  # [/hour]
            * building.volume_cold_store  # [m^3]
            * building.energy_new_air  # [kJ/m^3*degC]
            * (temperature - building.inside_ideal_temperature)  # [degC]
            / 3600  # [s/hour]
        )  # [kW]
    return 0


# infiltration_load(MY_CLINIC)


def _calculate_cooling_load(
    building: Clinic, current_hour: int, temperature: float
) -> float:
    # TODO:
    # A poential error bar calculation will go here, whereby different maximum and
    # minimum points may be tested in order to check the sensitivity of the calculation.
    #
    # building.patients += 0
    #

    q1 = calculate_transmission_load(building, temperature)
    q2 = calculate_internal_load_people(building, current_hour)
    # q3 = internal_load_lighting(building)
    # q4 = fridge_load(building)
    q5 = infiltration_load(building, current_hour, temperature)

    return q1 + q2 + q5


# TESTED - WORKING
def calculate_clinic_cooling_load(
    auto_generated_files_directory: str,
    building: Clinic,
    device_utilisations: Dict[Device, pd.DataFrame],
    disable_tqdm: bool,
    location: Location,
    logger: Logger,
    logger_name: str,
    regenerate: bool,
    temperatures: pd.Series,
) -> pd.DataFrame:
    """
    Computes the total cooling load in kW for a building.

    Inputs:
        - auto_generated_files_directory:
            Directory containing auto-generated device utilisation profiles.
        - building:
            Clinic being considered.
        - current_hour:
            Current hour of simulation.
        - device_utilisations:
            The processed device utilisation information.
        - disable_tqdm:
            Whether to disable the tqdm progress bars (True) or display them (False).
        - location:
            The location currently being considered.
        - logger:
            The logger to use for the run.
        - logger_name:
            The name of the current logger.
        - regenerate:
            Whether to force-regenerate the various profiles.
        - temperatures:

    """

    # Calculate the waste heat generated by the devices within the clinic.
    clinic_location = Location(
        0,
        1,
        location.country,
        location.latitude,
        location.longitude,
        location.max_years,
        location.name,
        location.time_difference,
    )

    # Calculate the general load of the building excluding waste heat
    clinic_cooling_load = [
        _calculate_cooling_load(
            building,
            hour,
            temperatures[hour],
        )
        for hour in range(0, clinic_location.max_years * HOURS_PER_YEAR)
    ]  # [kW]

    try:
        (_, waste_heat_produced, _,) = process_load_profiles(
            auto_generated_files_directory,
            device_utilisations,
            disable_tqdm,
            clinic_location,
            logger,
            regenerate,
            ResourceType.WASTE_HEAT,
        )
    except InputFileError:
        logger.error(
            "Error determining heat production from clinic devices for clinic %s.",
            building.name,
        )
        print(
            "Generating necessary profiles .................................    "
            + f"{FAILED}"
        )
        raise
    except Exception as e:
        logger.error(
            "Error determining heat production from clinic devices for clinic %s.",
            building.name,
        )
        print(
            "Generating necessary profiles .................................    "
            + f"{FAILED}"
        )
        logger.error(
            "%sAn unexpected error occurred generating the load profiles. See %s for "
            "details: %s%s",
            BColours.fail,
            f"{os.path.join(LOGGER_DIRECTORY, logger_name)}.log",
            str(e),
            BColours.endc,
        )
        raise

    return pd.DataFrame(clinic_cooling_load) + pd.DataFrame(
        waste_heat_produced.sum(axis=1)
    )


# def refrigeration_cooling_capacity_sizing(building: Clinic, temperature):
#     """
#     calculating the cooling capacity in kW from the cooling load and the run hours in a day

#     """

#     system_load_factor = safety_factor_load(building, temperature)
#     system_load_factor = safety_factor_load(building, temperature)
#     return system_load_factor / building.run_hours
#


if __name__ == "__main__":
    import pdb

    pdb.set_trace(header="Start clinic module")

    load: float = 0

    for hour in HOURS:
        load += calculate_load_now(hour)

    # Hours for testing
    hours = list(range(24))
    temperatures = import_weather_data(
        MY_CLINIC
    )  # Renewables Ninja Luweero Temperature data for 2020

    # Calculate the total cooling load per hour
    c_load = safety_factor_load(MY_CLINIC, temperatures)
    times = np.linspace(0, 365, num=len(temperatures))
    plt.plot(times[:168], c_load[:168], "C6")
    plt.xlabel("time")
    plt.ylabel("Cooling load in kWh")
    plt.grid(alpha=0.05)
    plt.show()
    print("RUNNING CLINIC.PY TO TEST :)")
    # print("Refrigeration cooling capacity sizing in kW = ", refrigeration_cooling_capacity_sizing(MY_CLINIC,temperatures, time_week))
