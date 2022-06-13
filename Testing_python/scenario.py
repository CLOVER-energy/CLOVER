# -*- coding: utf-8 -*-
"""
Created on Mon May 30 21:27:57 2022

@author: pahar
"""

# do the scenarios
name=str(input("Scenario name:"))
print("")
print("***Renewable system:***")
print("")
pv=str(input("Do you want to use PV? [true or false]:"))
battery=str(input("Do you want to use Battery? [true or false]:"))
print("")
print("***Diesel Backup:***")
# if answered no previously then we don't use this in main
if d in ['y','Y','Yes','YES']:
    mode=str(input("What mode are you looking for? [backup or disabled]:"))
    backup=str(input("Threshold: [0-1]:"))
else:
    print("No Diesel generator used for this scenario!")
print("")

grid_EDL=str(input("Are you relying on NEM EDL? [true or false]:")) 
grid_DG=str(input("Are you relying on NEM Diesel Generator? [true or false]:"))
grid_types=location.location
priortise_self_generation=str(input("Are you prioritising self generation? [true or false]:"))
print("")
print("***Demand coverage***")
print("")
domestic=str(input("Are you covering domestic demand? [true or false]:"))
commercial=str(input("Are you covering commercial demand? [true or false]:"))
public=str(input("Are you covering public demand? [true or false]:"))          
print("")
distributiion_network=str(input("Distribution network type [dc or ac]:"))
#resource_types=str(electric_power)
