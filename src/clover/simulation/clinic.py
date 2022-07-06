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
    56.49, 56.49, 86.8, 15.13, 2.5, 5, 1, 0.7, 23, 28, 1.5, 6.5, 2.5, 0.22, 82, 67.4, 9, 4, 3, 7, 120, 12, 40, 162.69, 2.2, 6.5)


def transmission_load_walls(building: Clinic):
    """
    Computes the transmission load of the walls in kWh/day for a building.

    """

    return (
        building.surface_area_walls
        * building.u_value_walls
        * (building.outside_temperature - building.inside_ideal_temperature)
        * 24
        / 1000
    )

# t1 = print(transmission_load_walls(MY_CLINIC))

def transmission_load_doors_windows(building: Clinic):
    """
    Computes the transmission load of the doors and windows in kWh/day for a building.

    """

    return (
        building.surface_area_doors_windows
        * building.u_value_windows_doors
        * (building.outside_temperature - building.inside_ideal_temperature)
        * 24
        / 1000
    )
# t2 = print(transmission_load_doors_windows(MY_CLINIC))

def transmission_load_floor(building: Clinic):
    """
    Computes the transmission load of the floor in kWh/day for a building.

    """

    return (
        building.floor_area
        * building.u_value_floor
        * (building.outside_temperature - building.inside_ideal_temperature)
        * 24
        / 1000
    )

# t3 = print(transmission_load_floor(MY_CLINIC))

def transmission_load_roof(building: Clinic):
    """
    Computes the transmission load of the roof in kWh/day for a building.

    """

    return (
        building.roof_area
        * building.u_value_roof
        * (building.outside_temperature - building.inside_ideal_temperature)
        * 24
        / 1000
    )

# t4 = print(transmission_load_roof(MY_CLINIC))

def calculate_transmission_load(building:Clinic) -> float:
    """
    Computes the total transmission heat load in kWh/day for a building.

    """
    t1 = transmission_load_walls(MY_CLINIC)
    t2 = transmission_load_doors_windows(MY_CLINIC)
    t3 = transmission_load_floor(MY_CLINIC)
    t4 = transmission_load_roof(MY_CLINIC)

    return (t1 + t2 + t3 + t4)



def internal_load_people_1(building: Clinic):
    """
    Computes the internal heat load of the nurses in kWh/day for a building.

    """

    return building.people_1 * building.time_people_1 * building.heat_loss_people_1 / 1000


def internal_load_people_2(building: Clinic):
    """
    Computes the internal heat load of the patients and accompainers in kWh/day for a building.

    """

    return building.people_2 * building.time_people_2 * building.heat_loss_people_2 / 1000


def calculate_internal_load_people(building: Clinic) -> float:
    """
    Computes the internal heat load of the total people in kWh/day for a building.

    """
    p1 = internal_load_people_1(MY_CLINIC)
    p2 = internal_load_people_2(MY_CLINIC)

    return p1 + p2


def internal_load_lighting(building: Clinic):
    """
    Computes the internal heat load of the lamps in kWh/day for a building.

    """

    return building.lamps_internal * building.time_lamps_internal * building.wattage_lamps / 1000


def equipment_load(building: Clinic):
    """
    Computes the internal heat load of the fridge in kWh/day for a building.

    """

    return building.fridge_wattage * building.time_fridge / 1000


def infiltration_load(building: Clinic):
    """
    Computes the infiltration load in kWh/day for a building.

    """

    return (
        building.changes
        * building.volume_cold_store
        * building.energy_new_air
        * (building.outside_temperature - building.inside_ideal_temperature)
        / 3600
    )


def calculate_cooling_load(building: Clinic) -> float:
    """
    Computes the total cooling load in kWh/day for a building.

    """
    q1 = calculate_transmission_load(MY_CLINIC)
    q2 = calculate_internal_load_people(MY_CLINIC)
    q3 = internal_load_lighting(MY_CLINIC)
    q4 = equipment_load(MY_CLINIC)
    q5 = infiltration_load(MY_CLINIC)

    return q1 + q2 + q3 + q4 + q5



def safety_factor_load(building: Clinic) -> float:
    """
    Adds a 20% safety factor to the calculation to account for errors and variations from design.

    """

    cooling_load = calculate_cooling_load(MY_CLINIC)

    return cooling_load * 0.2 + cooling_load



def refrigeration_cooling_capacity_sizing(building: Clinic):
    """
    calculating the cooling capacity in kW from the cooling load and the run hours in a day
    """
    system_load_factor = safety_factor_load(building)
    return system_load_factor / building.run_hours

if __name__ == "__main__":
    # Hours for testing
    hours = list(range(24))
    temperatures = [23, 24, 25, 26, 27, 28] * 4

    print("Total cooling load in kWh/day = ", (safety_factor_load(MY_CLINIC)))
    print("RUNNING CLINIC.PY TO TEST :)")
    print("Refrigeration cooling capacity sizing in kW = ", refrigeration_cooling_capacity_sizing(MY_CLINIC))
