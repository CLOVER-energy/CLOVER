# -*- coding: utf-8 -*-
"""
Created on Mon May 30 18:17:32 2022

@author: pahar
"""
import time

print ("CLOVER 5.0.2 LOADING, PLEASE HAVE YOUR INPUT READY...")
time.sleep (1) 
print ("")
print ("")

a=str(input("Do you want to override previous entered data? [Y for YES, N for NO]: "))
if a in ['y','Y','Yes','YES']:
    print ("")
    print ("The world is big... tell me where is your analysis!")
    print ("")
    g=str(input("Do you want to change the location of your analysis? [Y for Yes, N for No]:"))
    if g in ['y','Y','Yes','YES']:
        print("")
        import location
    else:
        print("")
        print("Keeping data used from previous simulation...")
    print("")
    print("What products are we using? tell me more...")
    print("")
    b=str(input("Do you want to override SOLAR GENERATION data? [Y for YES, N for NO]: "))
    if b in ['y','Y','Yes','YES']:
        print ("")
        import solar_generation_inputs
    else:
        print ("")
        print("Keeping data used from previous simulation...")
    print ("")
    c=str(input("Do you want to override the Battery data? [Y for YES, N for NO]: "))
    if c in ['y','Y','Yes','YES']:
        print ("")
        import battery_data
    else:
        print ("")
        print("Keeping data used from previous simulation...")
    print ("")
    d=str(input("Are you using a Diesel generator in your analysis? [Y for YES, N for NO]: "))
    if d in ['y','Y','Yes','YES']:
        print ("")
        e=str(input("Do you want to override DIESEL GENERATOR data? [Y for YES, N for NO]: "))
        if e in ['y','Y','Yes','YES']:
            print ("")
            import diesel_inputs
        else:
            print ("")
            print("Keeping data used from previous simulation...")
    else:
        print ("")
        import diesel_inputs_empty
        print("Diesel generator data not included in our analysis...") #0 diesel data
    print ("")
    f=str(input("Do you want to override the financial inputs? [Y for YES, N for NO]:"))
    if f in ['y','Y','Yes','YES']:
        print ("")
        import finance_inputs
    else:
        print ("")
        print("Keeping data used from previous simulation...")
        print ("")
    print("***DATA COLLECTED***")
    time.sleep (2) 
    print("")
    j=str(input("Do you want to change the scenario? [Y for Yes, N for No]:"))
    if j in ['y','Y','Yes','YES']:
        print ("")
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
            mode=str('disabled')
            backup=0
            time.sleep(1)
        print("")
        grid_EDL=str(input("Are you relying on NEM EDL? [true or false]:")) 
        grid_DG=str(input("Are you relying on NEM Diesel Generator? [true or false]:"))
        #grid_types=location.location
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
    else:
        print("")
        print("***SCENARIO NOT CHANGED***")
        time.sleep(2)
else:
    print("Keeping data used from previous simulation...")
    j=str(input("Do you want to change the scenario? [Y for Yes, N for No]:"))
    if j in ['y','Y','Yes','YES']:
        print ("")
        name=str(input("Scenario name:"))
        print("")
        print("***Renewable system:***")
        print("")
        pv=str(input("Do you want to use PV? [true or false]:"))
        battery=str(input("Do you want to use Battery? [true or false]:"))
        print("")
        print("***Diesel Backup:***")
        # if d in ['y','Y','Yes','YES']:# d was never initialised here so...
        mode=str(input("What mode are you looking for? [backup or disabled]:"))
        backup=str(input("Threshold: [0-1]:"))
        # # else:
        #     print("No Diesel generator used for this scenario!")
        print("")
        grid_EDL=str(input("Are you relying on NEM EDL? [true or false]:")) 
        grid_DG=str(input("Are you relying on NEM Diesel Generator? [true or false]:"))
        #grid_types=location.location #already established in previous iteration
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
        print("")
        print("***SCENARIO SAVED***")
    else:
        print("")
        print("***SCENARIO NOT CHANGED***")
print("")
print('ALL INFORMATION COLLECTED...')
print("")
print("*****CLOVER WILL START RUNNING IN 2 seconds*****")

time.sleep (2) 

    
        
            