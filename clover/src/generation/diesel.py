# -*- coding: utf-8 -*-
"""
===============================================================================
                            DIESEL GENERATION FILE
===============================================================================
                            Most recent update:
                                23 April 2018
===============================================================================
Made by:
    Philip Sandwell
Copyright:
    Philip Sandwell, 2018
For more information, please email:
    philip.sandwell@googlemail.com
===============================================================================
"""
import os

import numpy as np
import pandas as pd

from ...__utils__ import LOCATIONS_FOLDER_NAME

class Diesel():
    def __init__(self): 
        self.size = 1
        self.location = 'Bahraich'
        self.CLOVER_filepath = os.getcwd()
        self.location_filepath = os.path.join(self.CLOVER_filepath, LOCATIONS_FOLDER_NAME, self.location)
        self.generation_filepath = os.path.join(self.location_filepath, 'Generation')
        self.diesel_filepath = os.path.join(self.generation_filepath, 'Diesel', 'Diesel inputs.csv')
        self.diesel_inputs = pd.read_csv(self.diesel_filepath,header=None,index_col=0).round(decimals=3)

#%%       
#   Energy threshold, above which the generator should switch on
    def find_deficit_threshold(self,unmet_energy,blackouts,backup_threshold):
        """
        Function:
            Identifies the threshold level of energy at which the diesel backup 
            generator switches on
        Inputs:
            unmet_energy        Load profile of currently unment energy
            blackouts           Current blackout profile before diesel backup
            backup_threshold    Desired level of reliability after diesel backup
        Outputs:
            energy_threshold    Energy threshold (kWh) at which the diesel backup
                                switches on
        """
        blackout_percentage = np.mean(blackouts)[0]                         # Find blackout percentage
        reliability_difference = blackout_percentage - backup_threshold     # Find difference in reliability
        percentile_threshold = 100.0 * (1.0 - reliability_difference)
        if reliability_difference > 0.0:
            energy_threshold = np.percentile(unmet_energy,percentile_threshold)
        else:
            energy_threshold = np.max(unmet_energy)[0] + 1.0
        return energy_threshold
    
#   Find times when load > energy threshold
    def get_diesel_energy_and_times(self,unmet_energy,blackouts,backup_threshold):
        """
        Function:
            Calculates the times at which the diesel backup generator is used, and
            the energy output during those times
        Inputs:
            unmet_energy        Load profile of currently unment energy
            blackouts           Current blackout profile before diesel backup
            backup_threshold    Desired level of reliability after diesel backup
        Outputs:
            diesel_energy       Profile of energy supplued by diesel backup
            diesel_times        Profile of times when generator is on (1) or off (0)
        """
        energy_threshold = self.find_deficit_threshold(unmet_energy,blackouts,backup_threshold)
        diesel_energy = (unmet_energy >= energy_threshold) * unmet_energy
        diesel_times = (unmet_energy >= energy_threshold) * 1
        diesel_times = diesel_times.astype(float)
        return diesel_energy, diesel_times  
    
#   Find diesel fuel consumption
    def get_diesel_fuel_usage(self,capacity,diesel_energy,diesel_times):
        """
        Function:
            Calculates the fuel usage of the diesel backup generator
        Inputs:
            capacity        Capacity (kW) of the diesel generator
            diesel_energy   Profile of energy supplued by diesel backup
            diesel_times    Profile of times when generator is on (1) or off (0)
        Outputs:
            fuel_usage      Hourly profile of diesel fuel usage (litres)
        """
        diesel_consumption = float(self.diesel_inputs[1]['Diesel consumption'])
        diesel_minimum_load = float(self.diesel_inputs[1]['Diesel minimum load'])
        capacity = float(capacity)
        load_factor = diesel_energy / capacity
        above_minimum = load_factor * (load_factor > diesel_minimum_load)
        below_minimum = diesel_minimum_load * (load_factor <= diesel_minimum_load)
        load_factor = pd.DataFrame(above_minimum.values + below_minimum.values) * diesel_times
        fuel_usage = load_factor * capacity * diesel_consumption
        fuel_usage = fuel_usage.astype(float)
        return fuel_usage # in litres