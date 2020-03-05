# -*- coding: utf-8 -*-
"""
===============================================================================
                            DIESEL GENERATION FILE
===============================================================================
                            Most recent update:
                                19 February 2020
===============================================================================
Made by:
    Philip Sandwell
Copyright:
    Philip Sandwell, 2018
For more information, please email:
    philip.sandwell@googlemail.com
===============================================================================
"""
import pandas as pd
import numpy as np

class Diesel():
    def __init__(self): 
        self.size = 1
        self.location = 'Bahraich'
        self.CLOVER_filepath = '/***YOUR LOCAL FILE PATH***/CLOVER 4.0'
        self.location_filepath = self.CLOVER_filepath + '/Locations/' + self.location
        self.generation_filepath = self.location_filepath + '/Generation/'
        self.diesel_filepath = self.generation_filepath + 'Diesel/Diesel inputs.csv'
        self.diesel_inputs = pd.read_csv(self.diesel_filepath,header=None,index_col=0).round(decimals=3)
        self.scenario_inputs = pd.read_csv(self.location_filepath + '/Scenario/Scenario inputs.csv', header=None,
                                           index_col=0).round(decimals=3)

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
            diesel_energy       Profile of energy supplied by diesel backup
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
        return fuel_usage  # in litres

#   Get dispatched diesel hours
    def get_dispatchable_diesel_times(self):
        '''
        Added by Hamish Beath February 2020
        Function:
            Gets the diesel energy times for dispatchable diesel if applies
        Inputs:
            'scenario inputs.csv' from Scenario folder to detect dispatchable diesel settings
        Outputs:
            Returns profile of times diesel on if dispatchable diesel selected, or empty profile
        '''
        if self.scenario_inputs[1]['Dispatchable diesel'] == 'Y':
            if self.scenario_inputs[1]['Dispatchable diesel time'] == '00:00 - 00:00':
                return pd.DataFrame(np.zeros((24 * 365 * 20, 1)))
            else:
                on_time = self.scenario_inputs[1]['Dispatchable diesel time']
                start_hour, end_hour = int(on_time[0:2]), int(on_time[8:10])
                if end_hour > start_hour or end_hour == 0:
                    if end_hour == 0:
                        end_hour = 24
                    else:
                        pass
                    hours_on = end_hour - start_hour
                    day_profile = np.array([])
                    count = 0
                    while count < 24:
                        if count != start_hour:
                            day_profile = np.append(day_profile, 0)
                            count += 1
                        elif count == start_hour:
                            for i in range(0, hours_on):
                                day_profile = np.append(day_profile, 1)
                                count += 1
                # If the end time goes across the day boundary
                if end_hour < start_hour:
                    if end_hour == 0:    # Exclude if the end is midnight
                        pass
                    else:
                        day_profile = np.array([])
                        for i in range(0, end_hour):
                            day_profile = np.append(day_profile, 1)
                        for i in range(0, (start_hour - end_hour)):
                            day_profile = np.append(day_profile, 0)

                        for i in range(0, (24-start_hour)):
                            day_profile = np.append(day_profile, 1)
                whole_profile = np.array([])
                for i in range(0, (20 * 365)):
                    whole_profile = np.append(whole_profile, day_profile)
                return pd.DataFrame(whole_profile)
        if self.scenario_inputs[1]['Dispatchable diesel'] == 'N':
            return pd.DataFrame(np.zeros((24 * 365 * 20, 1)))


#   Calculate the remaining diesel energy
    def diesel_surplus_unmet_dispatched(self, unmet_energy, surplus_diesel, diesel_used, diesel_supplied,
                                        storage_power_supplied, empty_capacity_list, dd_on, state_of_charge):
        """
        Added by Hamish Beath - March 2020

        Function:
            Works out how much additional unmet energy is met by the diesel genset in this hour, and the respective
            quantities of surplus, used and supplied energy
        Inputs:
            unmet_energy           The unmet energy profile not considering dispatched diesel
            surplus_diesel         The profile of the surplus diesel energy available in each hour
            diesel_used            Diesel energy already used profile for charging the batteries
            diesel_supplied        Diesel energy already supplied profile for charging the batteries
        Outputs:
            new_unmet_energy       Hourly profile of unmet energy considering the additional energy met by diesel
            new_diesel_used        Hourly profile of diesel energy used with additional energy meeting unmet demand
            new_diesel_supplied    Hourly profile of diesel energy supplied from dispatchable diesel
        """
        # Creates empty profiles to append to
        dispatched_diesel_used_new = []
        dispatched_diesel_supplied_new = []
        unmet_energy_new = []

        # Gets existing profiles
        surplus_diesel = surplus_diesel['Surplus']
        diesel_used = diesel_used['Used']
        diesel_supplied = diesel_supplied['Supplied']
        unmet_energy = unmet_energy['Unmet']

        # Iterates through the profiles
        for cell in range(0, len(unmet_energy)):

            # Isolates values of the iteration
            surplus_diesel_hour = surplus_diesel[cell]
            unmet_energy_hour = unmet_energy[cell]
            used_diesel_energy_hour = diesel_used[cell]
            supplied_diesel_energy_hour = diesel_supplied[cell]

            if unmet_energy_hour <= 0:
                unmet_energy_new.append(0)
                dispatched_diesel_supplied_new.append(supplied_diesel_energy_hour)
                dispatched_diesel_used_new.append(used_diesel_energy_hour)

            else:
                # Diesel isn't on then do nothing
                if supplied_diesel_energy_hour == 0:
                    unmet_energy_new.append(0)
                    dispatched_diesel_supplied_new.append(supplied_diesel_energy_hour)
                    dispatched_diesel_used_new.append(used_diesel_energy_hour)
                else:
                    # Calculate the difference between the unmet energy and the surplus available in hour
                    remainder_unmet = unmet_energy_hour - surplus_diesel_hour
                    # If amount above zero, do the following

                    if remainder_unmet >= 0:
                        # Calculates new unmet energy
                        new_unmet = remainder_unmet
                        used_addition = unmet_energy[cell] - new_unmet
                        unmet_energy_new.append(new_unmet)

                        # Calculates new used diesel energy
                        used_diesel_energy_hour += used_addition
                        dispatched_diesel_used_new.append(used_diesel_energy_hour)

                        # Calculates the additional supplied energy
                        supplied_difference = supplied_diesel_energy_hour - used_diesel_energy_hour
                        if supplied_difference >= 0:
                            dispatched_diesel_supplied_new.append(supplied_diesel_energy_hour)
                        elif supplied_difference < 0:
                            dispatched_diesel_supplied_new.append(used_diesel_energy_hour)

                    # If amount less than zero, do the following to reset zero value
                    elif remainder_unmet < 0:
                        used_diesel_energy_hour += unmet_energy[cell]
                        dispatched_diesel_used_new.append(used_diesel_energy_hour)
                        # Calculates the additional supplied energy
                        supplied_difference = supplied_diesel_energy_hour - used_diesel_energy_hour
                        if supplied_difference >= 0:
                            dispatched_diesel_supplied_new.append(supplied_diesel_energy_hour)
                        elif supplied_difference < 0:
                            dispatched_diesel_supplied_new.append(used_diesel_energy_hour)
                        unmet_energy_new.append(0)

        # Makes Dataframes from lists of values
        dispatched_diesel_used_new = pd.DataFrame(dispatched_diesel_used_new, columns=['Used'])
        dispatched_diesel_supplied_new = pd.DataFrame(dispatched_diesel_supplied_new,columns=['Dispatched Diesel Supplied (kWh)'])
        unmet_energy_new = pd.DataFrame(unmet_energy_new,columns=['Unmet energy (kWh)'])
        empty_capacity = pd.DataFrame(empty_capacity_list, columns=['Empty Capacity'])
        dd_on = pd.DataFrame(dd_on, columns=['Dispatched Diesel On'])
        state_of_charge = pd.DataFrame(state_of_charge, columns=['state of charge'])

        # test_outputs = pd.concat([unmet_energy, empty_capacity, diesel_used,diesel_supplied, surplus_diesel, unmet_energy_new,
        #                          dispatched_diesel_used_new, dispatched_diesel_supplied_new, storage_power_supplied, dd_on, state_of_charge
        #                           ], axis=1)
        # test_outputs.to_csv('~/Library/Mobile Documents/com~apple~CloudDocs/Mahama Project/Dispatchable Diesel/test_feb20.csv')
        # Returns to energy_system script
        return unmet_energy_new, dispatched_diesel_used_new, dispatched_diesel_supplied_new
