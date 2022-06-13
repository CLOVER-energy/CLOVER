# -*- coding: utf-8 -*-
"""
Created on Mon May 30 16:32:41 2022

@author: pahar
"""

#writing data 
#do you want to input data if yes do this step if no keep previously entered data for region
print("WELCOME TO CLOVER 5.0.2, PLEASE START BY FILLING THE DATA:")
print("")
print("")
print("SOLAR GENERATION INPUTS, SET THE TECHNICAL INPUTS OF THE SYSTEM")
name=input('Solar Panel name:')
power_per_panel=float(input('Power per unit [Wp]:'))
azimuthal_orientation=float(input("Azimuthal Orientation in [degrees from north]:"))
lifetime=float(input('Lifetime [years]:'))
reference_efficiency=float(input('Reference efficiency [0-1]:'))
reference_temperature=float(input('Reference temperature [degrees Celsius]:'))
thermal_coefficient=float(input('Thermal coefficient:'))
tilt=float(input('Optimal Tilt angle in [degrees above horizontal]:'))
PV_type=str(input('Panel Type [PV or PV-T]:'))

print("")
print("SOLAR GENERATION INPUTS, SET THE ECONOMICAL INPUTS OF THE SYSTEM")
print("SOLAR PV COSTS:")
print ("")
cost=float(input("PV system CAPEX [$/kWp]:")) #or we can put the per panel and then make it per kwp if we ask capacity of 1 solar panel
cost_decrease=float(input('Yearly cost decrease [% p.a]:'))
installation_cost=float(input('System Installation Cost [$/kWp]:'))
installation_cost_decrease=float(input('System yearly installation cost decrease [% p.a]:'))
om=float(input('Yearly O&M costs of the system [$/kWp p.a]:'))

print("")
print("SOLAR GENERATION INPUTS, SET THE EMISSIONS INPUTS OF THE SYSTEM")
print("SOLAR PV EMISSIONS:")
print ("")
ghg=float(input("PV system Embodied GHG [kgCO2/kWp]:")) 
ghg_decrease=float(input('Yearly GHG decrease [% p.a]:'))
installation_ghg=float(input('System Installation GHG [kgCO2/kWp]:'))
installation_ghg_decrease=float(input('System yearly installation GHG decrease [% p.a]:'))
om_emissions=float(input('Yearly O&M GHG of the system [kgCO2/kWp p.a]:'))



