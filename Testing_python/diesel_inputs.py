# -*- coding: utf-8 -*-
"""
Created on Mon May 30 17:49:21 2022

@author: pahar
"""

print("DIESEL GENERATOR INPUTS, SET THE TECHNICAL INPUTS OF THE SYSTEM")
name=input('Diesel generator name:')
diesel_consumption=float(input('Diesel consumption to generate 1 kW of capacity per hour [L/kWp]:'))
minimum_load=float(input("Minimum Capacity Factor [0.0-1.0]:"))

print("")
print("DIESEL GENERATOR INPUTS, SET THE ECONOMICAL INPUTS OF THE SYSTEM")
print("DIESEL GENERATOR COSTS:")
print ("")
cost=float(input("PV system CAPEX [$/kWp]:")) #or we can put the per panel and then make it per kwp if we ask capacity of 1 solar panel
cost_decrease=float(input('Yearly cost decrease [% p.a]:'))
installation_cost=float(input('System Installation Cost [$/kWp]:'))
installation_cost_decrease=float(input('System yearly installation cost decrease [% p.a]:'))
om=float(input('Yearly O&M costs of the system [$/kWp p.a]:'))

print("")
print("DIESEL GENERATOR INPUTS, SET THE EMISSIONS INPUTS OF THE SYSTEM")
print("DIESEL GENERATOR EMISSIONS:")
print ("")
ghg=float(input("PV system Embodied GHG [kgCO2/kWp]:")) 
ghg_decrease=float(input('Yearly GHG decrease [% p.a]:'))
installation_ghg=float(input('System Installation GHG [kgCO2/kWp]:'))
installation_ghg_decrease=float(input('System yearly installation GHG decrease [% p.a]:'))
