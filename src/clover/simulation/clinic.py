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

from typing import Any, Dict, List, Tuple

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
        The floor area of the clinic in m^2
    .. attribute:: roof_area
        The ceiling area of the clinic in m^2
    .. attribute:: surface_area_walls
        The internal surface area of the external walls of the clinic in m^2
    .. attribute:: surface_area_doors_windows
        The sum of the surface areas of the windows and doors of the clinic in m^2
        (only valid if they are made with the same materials,
        otherwise they need to be divided in a different function)
    .. attribute:: u_value_walls
        The thermal transmittance value of the walls of the clinic in W/m^2*K
    .. attribute:: u_value_windows_doors
        The thermal transmittance value of the windows and doors of the clinic in W/m^2*K
        (only valid if they are made with the same materials,
        otherwise they need to be divided)
     .. attribute:: u_value_floor
        The thermal transmittance value of the floor of the clinic in W/m^2*K
     .. attribute:: u_value_roof
        The thermal transmittance value of the roof of the clinic in W/m^2*K
     .. attribute:: inside_ideal_temperature
        The ideal temperature to set inside the clinc             
    .. attribute:: staff
        The number of nurses, cleaners, and guardians averagely present in the clinic at any time
     .. attribute:: patients
        The number of patients and accompaniers averagely present in the clinic at any time
     .. attribute:: heat_loss_staff
        The heat loss of the staff, depending on their activity levels
     .. attribute:: heat_loss_patients
        The heat loss of the patients and accompaniers, depending on their activity levels
     .. attribute:: start_time_staff
        The time at which the staff starts working
     .. attribute:: end_time_staff
        The time at which the staff stops working
     .. attribute:: start_time_patients
        The time at which the clinic is open to the clients   
     .. attribute:: end_time_patients
        The time at which the clinic closes
     .. attribute:: lamps_internal
        The number of lights in the clinic
     .. attribute:: start_time_lamps
        The hour when the lights are turned on
     .. attribute:: end_time_lamps
        The hour when the lights are turned off
     .. attribute:: wattage_lamps
        The power consume of the lights in the clinic
     .. attribute:: fridge_wattage
        The power consume of the fridge of the clinic     
     .. attribute:: x_ray
        The number of x-ray machines in the clinic
     .. attribute:: x_ray_heat_loss
        The nheat loss of the x-ray machines installed
     .. attribute:: start_time_x_ray
        The hour when the x-ray machine starts being used
     .. attribute:: end_time_x_ray
        The time when the x-ray machine stops being used
     .. attribute:: changes
        The number of total volume changes per hour
     .. attribute:: volume_cold_store
        The total volume of the clinic
     .. attribute:: energy_new_air
        The energy per cubic meter per degree Celsius of the outside air 
     .. attribute:: start_time_infiltration
        The hour when the infiltration starts, when people start entering the clinic
     .. attribute:: end_time_infiltration
        The hour when the infiltration ends, when the last person left the clinic


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

    #x-ray load
    x_ray: float
    x_ray_heat_loss: float
    start_time_x_ray: List[int]
    end_time_x_ray: List[int]

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
            inputs["x_ray"],
            inputs["x_ray_heat_loss"],
            inputs["start_time_x_ray"],
            inputs["end_time_x_ray"],
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


# TESTED WORKING
def internal_load_lighting(building: Clinic, current_hour: int) -> float:
    """
    Computes the internal heat load of the lamps in kW for a building,
    the wattage is halved as the dissipation of energy only corresponds to 50% in LEDs.

    """
    weekday: int = (current_hour // 24) % 7
    start_time: int = building.start_time_lamps[weekday]
    end_time: int = building.end_time_lamps[weekday]

    if start_time <= (current_hour % 24) < end_time:
        return building.lamps_internal * building.wattage_lamps / 2000
    return 0

# COME BACK TO THIS
def fridge_load(building: Clinic):
    """
    Computes the internal heat load of the fridge in kW for a building.

    """
    return building.fridge_wattage * building.time_fridge *0.8/ 1000

# TESTED WORKING
def x_ray_load(building: Clinic, current_hour: int) -> float:
    """
    Computes the internal heat load of the x-ray in kW.

    """
    weekday: int = (current_hour // 24) % 7
    start_time: int = building.start_time_x_ray[weekday]
    end_time: int = building.end_time_x_ray[weekday]

    if start_time <= (current_hour % 24) < end_time:
        return building.x_ray * building.x_ray_heat_loss / 1000
    return 0

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
    q3 = internal_load_lighting(building, current_hour)
    q4 = fridge_load(building)
    q5 = x_ray_load(building, current_hour)
    q6 = infiltration_load(building, current_hour, temperature)

    return q1 + q2 + q3 + q4 + q5 + q6


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
) -> Tuple[pd.DataFrame, pd.DataFrame]:
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

    Outputs:
        - The cooling load of the clinic,
        - The electric load of the clinic.

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

    try:
        (_, electricity_consumption, _,) = process_load_profiles(
            auto_generated_files_directory,
            device_utilisations,
            disable_tqdm,
            clinic_location,
            logger,
            regenerate,
            ResourceType.ELECTRIC,
        )
    except InputFileError:
        logger.error(
            "Error determining electricity consumption from clinic devices for clinic "
            "%s.",
            building.name,
        )
        print(
            "Generating necessary profiles .................................    "
            + f"{FAILED}"
        )
        raise
    except Exception as e:
        logger.error(
            "Error determining electricity consumption from clinic devices for clinic "
            "%s.",
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

    return (
        pd.DataFrame(clinic_cooling_load)
        + pd.DataFrame(waste_heat_produced.sum(axis=1)),
        electricity_consumption,
    )
