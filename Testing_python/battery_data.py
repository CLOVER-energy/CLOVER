# -*- coding: utf-8 -*-
"""
Created on Mon May 30 19:39:14 2022

@author: pahar
"""

name=float(input("Battery name:"))
print("")
print("Battery technical data:")
print("")
maximum_charge=float(input("Maximum charge [0-1]:"))
maximum_discharge=float(input("Maximum discharge [0-1]:"))
leakage=float(input("Fractional leakage per hour:"))
conversion_in=float(input("Conversion efficiency (IN) [0-1]:"))
conversion_out=float(input("Conversion efficiency (OUT) [0-1]:"))
cycle_lifetime=float(input("Expected number of cycles over lifetime:"))
lifetime_loss=float(input("Fractional loss over lifetime [0-1]:"))
c_rate_discharging=float(input("Discharge rate:"))
c_rate_charging=float(input("Charge rate:"))
print("")
print("Battery Economical data:")
print("")
cost=float(input("Battery cost [$/kWh]:"))
cost_decrease=float(input("Yearly Battery cost decrease [% p.a]:"))
om=float(input("Yearly O&M [$/kWh]:"))
print("")
print("Battery Emissions data:")
print("")
ghg=float(input("Battery GHG [kgCO2/kWh]"))
om_ghg=float(input("Battery O&M GHG [kgCO2/kWh p.a]:"))
ghg_decrease=float(input("Yearly Battery GHG decrease [% p.a]:"))
