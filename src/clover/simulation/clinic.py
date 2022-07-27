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

from typing import List

import yaml

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


@dataclasses.dataclass
class Clinic:
    """
    Represents a clinic.

    .. attribute:: name
        The name of the clinic.

    """

    name: str

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
    people_1: float
    people_2: float
    heat_loss_people_1: float
    heat_loss_people_2: float
    start_time_people_1: List[int]
    end_time_people_1: List[int]
    start_time_people_2: List[int]
    end_time_people_2: List[int]

    # Internal heat load - Lighting
    lamps_internal: float
    lamps_external: float
    start_time_lamps: List[int]
    end_time_lamps: List[int]
    time_lamps_external: float
    wattage_lamps: float

    # Equipment heat load
    fridge_wattage: float
    time_fridge: float

    # Infiltration loads
    changes: float
    volume_cold_store: float
    energy_new_air: float
    start_time_infiltration: List[int]
    end_time_infiltration: List[int]

    run_hours: float


MY_PATH = "C:/Users/Ilaria/CLOVER/locations/Bahraich/inputs/simulation/"
with open(MY_PATH + "clinic.yaml") as f:
    data_clinic = yaml.load(f, Loader=yaml.FullLoader)
#  print(data_clinic)


MY_CLINIC: Clinic = Clinic(**data_clinic["clinics"][0])


def import_weather_data(building: Clinic):

    data = pd.read_csv("C:/Users/Ilaria/Desktop/weatherdata.csv")
    temperature = data["temperature"]
    # print(temperature)
    return temperature.to_numpy()


def import_weather_dataframe():
    data = pd.read_csv("C:/Users/Ilaria/Desktop/weatherdata.csv", dtype={"local_time"})
    return data


temperatura = import_weather_data(building=Clinic)


def transmission_load_walls(building: Clinic, temperature):
    """
    Computes the transmission load of the walls in kWh for a building.

    """

    return (
        building.surface_area_walls
        * building.u_value_walls
        * (temperature - building.inside_ideal_temperature)
        / 1000
    )


def transmission_load_doors_windows(building: Clinic, temperature):
    """
    Computes the transmission load of the doors and windows in kWh for a building.

    """

    return (
        building.surface_area_doors_windows
        * building.u_value_windows_doors
        * (temperature - building.inside_ideal_temperature)
        / 1000
    )


def transmission_load_floor(building: Clinic, temperature):
    """
    Computes the transmission load of the floor in kWh for a building.

    """

    return (
        building.floor_area
        * building.u_value_floor
        * (temperature - building.inside_ideal_temperature)
        / 1000
    )


def transmission_load_roof(building: Clinic, temperature):
    """
    Computes the transmission load of the roof in kWh for a building.

    """

    return (
        building.roof_area
        * building.u_value_roof
        * (temperature - building.inside_ideal_temperature)
        / 1000
    )


def calculate_transmission_load(building: Clinic, temperature):
    """
    Computes the total transmission heat load in kWh for a building.

    """
    t1 = transmission_load_walls(MY_CLINIC, temperature)
    t2 = transmission_load_doors_windows(MY_CLINIC, temperature)
    t3 = transmission_load_floor(MY_CLINIC, temperature)
    t4 = transmission_load_roof(MY_CLINIC, temperature)

    return t1 + t2 + t3 + t4


def internal_load_people_1(building: Clinic):
    """
    Computes the internal heat load of the nurses in kWh for a building.

    """
    # load_p = np.where((time_people>=11)&(time_people<18), building.people_1 * 1 * building.heat_loss_people_1 / 1000., 0.)
    people_at_times = [
        [
            [0, building.people_1 * building.heat_loss_people_1][t > start and t < end]
            for t in range(24)
        ]
        for start, end in zip(building.start_time_people_1, building.end_time_people_1)
    ]
    return people_at_times


def internal_load_people_2(building: Clinic):
    """
    Computes the internal heat load of the patients and accompainers in kWh for a building.

    """
    people_at_times = [
        [
            [0, building.people_2 * building.heat_loss_people_2][t > start and t < end]
            for t in range(24)
        ]
        for start, end in zip(building.start_time_people_2, building.end_time_people_2)
    ]
    return people_at_times


def calculate_internal_load_people(building: Clinic):
    """
    Computes the internal heat load of the total people in kWh for a building.

    """
    p1 = internal_load_people_1(MY_CLINIC)
    p2 = internal_load_people_2(MY_CLINIC)

    print(p1[i] + p2[i] for i in range(len(p1[0])))


calculate_internal_load_people(MY_CLINIC)


def internal_load_lighting(building: Clinic):
    """
    Computes the internal heat load of the lamps in kWh for a building.

    """
    lamps_at_times = [
        [
            [0, building.lamps_internal * building.wattage_lamps][t > start and t < end]
            for t in range(24)
        ]
        for start, end in zip(building.start_time_lamps, building.end_time_lamps)
    ]
    return lamps_at_times


def equipment_load(building: Clinic):
    """
    Computes the internal heat load of the fridge in kWh for a building.

    """

    return building.fridge_wattage * building.time_fridge / 1000


def infiltration_load(building: Clinic, temperature):
    """
    Computes the infiltration load in kWh for a building.

    """
    infiltration_at_times = [
        [
            [
                0,
                building.changes
                * building.volume_cold_store
                * building.energy_new_air
                * (temperature - building.inside_ideal_temperature),
            ][t > start and t < end]
            for t in range(24)
        ]
        for start, end in zip(
            building.start_time_infiltration, building.end_time_infiltration
        )
    ]
    return infiltration_at_times


# infiltration_load(MY_CLINIC)


def calculate_cooling_load(building: Clinic, temperature):
    """
    Computes the total cooling load in kWh for a building.

    """

    q1 = calculate_transmission_load(MY_CLINIC, temperature)
    q2 = calculate_internal_load_people(
        MY_CLINIC,
    )
    q3 = internal_load_lighting(MY_CLINIC)
    q4 = equipment_load(MY_CLINIC)
    q5 = infiltration_load(MY_CLINIC, temperature)

    print(q1, type(q1))
    print(q2, type(q2))
    print(q3, type(q3))
    print(q4, type(q4))
    print(q5, type(q5))
    return (q1 + q2[i] + q3[i] + q4 + q5[i] for i in range(len(q2[0])))


def safety_factor_load(building: Clinic, temperature):
    """
    Adds a 20% safety factor to the calculation to account for errors and variations from design.

    """

    cooling_load = calculate_cooling_load(MY_CLINIC, temperature)

    return cooling_load * 0.2 + cooling_load


def refrigeration_cooling_capacity_sizing(building: Clinic, temperature):
    """
    calculating the cooling capacity in kW from the cooling load and the run hours in a day

    """

    system_load_factor = safety_factor_load(building, temperature)
    system_load_factor = safety_factor_load(building, temperature)
    return system_load_factor / building.run_hours


if __name__ == "__main__":
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
