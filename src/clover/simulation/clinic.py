#
#
#
# Author: Ilaria
#
#

"""
clinic.py - Works out the health centre load.

"""

import dataclasses


@dataclasses.dataclass
class Clinic:
    """
    Represents a clinic.
    """

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
    outside_temperature: float

    # Internal heat load - people
    people_1: float
    time_people_1: float
    people_2: float
    time_people_2: float
    heat_loss_people_1: float
    heat_loss_people_2: float

    # Internal heat load - Lighting
    lamps_internal: float
    lamps_external: float
    time_lamps_internal: float
    time_lamps_internal: float
    wattage_lamps: float

    # Equipment heat load
    fridge_wattage: float
    time_fridge: float

    # Infiltration loads
    changes: float
    volume_cold_store: float
    energy_new_air: float

    run_hours: float


MY_CLINIC: Clinic = Clinic(
    56.49, 56.49, 86.8, 15.13, 2.5, 5, 1, 8.7, 23, 28,
)


def transmission_load_walls(building: Clinic, outside_temperature):
    """
    Computes the transmission load of the walls in kWh/day for a building.

    """

    return (
        building.surface_area_walls
        * building.u_value_walls
        * (outside_temperature - building.inside_ideal_temperature)
        * 24
        / 1000
    )


def transmission_load_doors_windows(
    building: Clinic,
    inside_ideal_temperature,
    outside_temperature,
    surface_area_doors_windows,
    u_value_doors_windows,
):
    """
    Computes the transmission load of the doors and windows in kWh/day for a building.

    """

    return (
        surface_area_doors_windows
        * u_value_doors_windows
        * (outside_temperature - inside_ideal_temperature)
        * 24
        / 1000
    )


def transmission_load_floor(
    building: Clinic,
    inside_ideal_temperature,
    outside_temperature,
    surface_area_floor,
    u_value_floor,
):
    """
    Computes the transmission load of the floor in kWh/day for a building.

    """

    return (
        surface_area_floor
        * u_value_floor
        * (outside_temperature - inside_ideal_temperature)
        * 24
        / 1000
    )


def transmission_load_roof(
    building: Clinic,
    inside_ideal_temperature,
    outside_temperature,
    surface_area_roof,
    u_value_roof,
):
    """
    Computes the transmission load of the roof in kWh/day for a building.

    """

    return (
        surface_area_roof
        * u_value_roof
        * (outside_temperature - inside_ideal_temperature)
        * 24
        / 1000
    )


def calculate_transmission_load():
    """
    Computes the total transmission heat load in kWh/day for a building.

    """

    t1 = transmission_load_walls(
        Clinic,
        inside_ideal_temperature,
        outside_temperature,
        surface_area_walls,
        u_value_walls,
    )
    t2 = transmission_load_doors_windows(
        Clinic,
        inside_ideal_temperature,
        outside_temperature,
        surface_area_doors_windows,
        u_value_doors_windows,
    )
    t3 = transmission_load_floor(
        Clinic,
        inside_ideal_temperature,
        outside_temperature,
        surface_area_floor,
        u_value_floor,
    )
    t4 = transmission_load_roof(
        Clinic,
        inside_ideal_temperature,
        outside_temperature,
        surface_area_roof,
        u_value_roof,
    )

    return (t1, t2, t3, t4)


def internal_load_people_1(
    building: Clinic, people_1, time_people_1, heat_loss_people_1
):
    """
    Computes the internal heat load of the nurses in kWh/day for a building.

    """

    return people_1 * time_people_1 * heat_loss_people_1 / 1000


def internal_load_people_2(
    building: Clinic, people_2, time_people_2, heat_loss_people_2
):
    """
    Computes the internal heat load of the patients and accompainers in kWh/day for a building.

    """

    return people_2 * time_people_2 * heat_loss_people_2 / 1000


def calculate_internal_load_people():
    """
    Computes the internal heat load of the total people in kWh/day for a building.

    """
    p1 = internal_load_people_1(Clinic, people_1, time_people_1, heat_loss_people_1)
    p2 = internal_load_people_2(Clinic, people_2, time_people_2, heat_loss_people_2)

    return p1 + p2


def internal_load_lighting(
    building: Clinic, lamps_internal, time_lamps_internal, wattage_lamps
):
    """
    Computes the internal heat load of the lamps in kWh/day for a building.

    """

    return lamps_internal * time_lamps_internal * wattage_lamps / 1000


def equipment_load(building: Clinic, fridge_wattage, time_fridge):
    """
    Computes the internal heat load of the fridge in kWh/day for a building.

    """

    return fridge_wattage * time_fridge / 1000


def infiltration_load(building: Clinic, changes, volume_cold_store, energy_new_air):
    """
    Computes the infiltration load in kWh/day for a building.

    """

    return (
        changes
        * volume_cold_store
        * energy_new_air
        * (outside_temperature - inside_ideal_temperature)
        / 3600
    )


def calculate_cooling_load(building) -> float:
    """
    Computes the total cooling load in kWh/day for a building.

    """
    q1 = calculate_transmission_load(t1, t2, t3, t4)
    t1, t2, t3, t4 = q1
    q2 = calculate_internal_load_people(p1, p2)
    q3 = internal_load_lighting(
        Clinic, lamps_internal, time_lamps_internal, wattage_lamps
    )
    q4 = equipment_load(Clinic, fridge_wattage, time_fridge)
    q5 = infiltration_load(Clinic, changes, volume_cold_store, energy_new_air)

    return q1 + q2 + q3 + q4 + q5


def safety_factor_load():
    """
    Adds a 20% safety factor to the calculation to account for errors and variations from design.

    """
    cooling_load = calculate_cooling_load(q1, q2, q3, q4, q5)

    return cooling_load * 0.2 + cooling_load



def refrigeration_cooling_capacity_sizing(building: Clinic, run_hours):
    """
    calculating the cooling capacity in kW from the cooling load and the run hours in a day
    """
    system_load_factor = safety_factor_load(calculating_cooling_load)
    return system_load_factor * run_hours

if __name__ == "__main__":
    # Hours for testing
    hours = list(range(24))
    temperatures = [23, 24, 25, 26, 27, 28] * 4

    print("RUNNING CLINIC.PY TO TEST :)")
    print(refrigeration_cooling_capacity_sizing(MY_CLINIC))
