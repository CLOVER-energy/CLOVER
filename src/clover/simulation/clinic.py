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
  
  area: float # Tells python that a clinic has an area, and it's a number
  heat_loss_coefficient: float
  mean_occupancy: float
    
def building_temperature_difference_load(
  building: Clinic,
  inside_ideal_temperature,
  outside_temperature
):
  """
  Computes the load in kW for a building.
  
  """
  
  return building.area * building.heat_loss_coefficient * (
    outside_temperature - inside_ideal_temperature
  )

# .....

def calculate_cooling_load(building):
  q1 = building_temperature_difference_load(
    building,
    inside,
    outside_temp
  )
  q2 = # ...
  q3
  
  
  return q1 + q2 + q3 # + ....
