# -*- coding: utf-8 -*-
"""
===============================================================================
                                LOAD FILE
===============================================================================
                            Most recent update:
                             12 December 2018
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
import pandas as pd
import numpy as np
import math

import sys
from ..conversion.conversion import Conversion

class Load():
    def __init__(self):
        self.location = 'Bahraich'
        self.CLOVER_filepath = os.getcwd()
        self.location_filepath = os.path.join(self.CLOVER_filepath, 'locations', self.location)
        self.location_inputs = pd.read_csv(os.path.join(self.location_filepath, 'Location Data', 'Location inputs.csv'),header=None,index_col=0)[1]
        self.device_filepath = os.path.join(self.location_filepath, 'Load')
        self.device_ownership_filepath = os.path.join(self.device_filepath, 'Device ownership')
        self.device_inputs = pd.read_csv(os.path.join(self.device_filepath, 'Devices.csv'))
        self.device_utilisation_filepath = os.path.join(self.device_filepath, 'Device utilisation')
        self.device_usage_filepath = os.path.join(self.device_filepath, 'Devices in use')
        self.device_load_filepath = os.path.join(self.device_filepath, 'Device load')

# =============================================================================
#       Calculate the load of devices in the community
# =============================================================================

    def total_load_hourly(self):
        """
        Function:
            Calculates the aggregated load of all devices
        Inputs:
            Takes in the .csv files of the loads of all devices
        Outputs:
            Gives a .csv file with columns for the load of domestic and 
            commercial devices to be used in later simulations and a .csv file
            of the load statistics from Load().yearly_load_statistics(...)
        """
        domestic_load = pd.DataFrame(np.zeros((int(self.location_inputs['Years'])*365*24, 1)))
        commercial_load = pd.DataFrame(np.zeros((int(self.location_inputs['Years'])*365*24, 1)))
        public_load = pd.DataFrame(np.zeros((int(self.location_inputs['Years'])*365*24, 1)))
        for i in range(len(self.device_inputs)):
            device_info = self.device_inputs.iloc[i]
            if device_info['Type'] == 'Domestic':
                add_load = pd.read_csv(self.device_load_filepath + device_info['Device'] + '_load.csv', index_col = 0).reset_index(drop=True)
                domestic_load = pd.DataFrame(domestic_load.values + add_load.values)
            elif device_info['Type'] == 'Commercial':
                add_load = pd.read_csv(self.device_load_filepath + device_info['Device'] + '_load.csv', index_col = 0).reset_index(drop=True)
                commercial_load = pd.DataFrame(commercial_load.values + add_load.values)
            elif device_info['Type'] == 'Public':
                add_load = pd.read_csv(self.device_load_filepath + device_info['Device'] + '_load.csv', index_col = 0).reset_index(drop=True)
                public_load = pd.DataFrame(public_load.values + add_load.values)
        total_load = pd.concat([domestic_load,commercial_load,public_load],axis=1)
        total_load.columns = ["Domestic", "Commercial", "Public"]
        total_load.to_csv(self.device_load_filepath + 'total_load.csv')
        
        yearly_load_statistics = self.yearly_load_statistics(total_load)
        yearly_load_statistics.to_csv(self.device_load_filepath + 'yearly_load_statistics.csv')

    def device_load_hourly(self):
        """
        Function:
            Calculates the total power for each device
        Inputs:
            Takes power from "Devices.csv" and uses the .csv files which give the 
            number of devices in use at a given time
        Outputs:
            Gives .csv files of the hourly load for each device
        """
        for i in range(len(self.device_inputs)):
            device_info = self.device_inputs.iloc[i]
            device_load = float(device_info['Power'])*pd.read_csv(self.device_usage_filepath + device_info['Device'] + '_in_use.csv', index_col = 0)
            device_load.to_csv(self.device_load_filepath + device_info['Device'] + '_load.csv')
       
# =============================================================================
#       Calculate the maximum loads for each year
# =============================================================================
    def yearly_load_statistics(self,total_load):
        """
        Function:
            Calculates the load statistics for each year on an hourly basis
        Inputs:
            total_load      Hourly total load of the system
        Outputs:
            Gives dataframe of the maximum, mean and median hourly loads
        """        
        total_load_yearly = pd.DataFrame(np.reshape(pd.DataFrame(total_load.sum(axis=1)).values,
                                                    (int(self.location_inputs['Years']),365*24))) 
        yearly_maximum = pd.DataFrame(total_load_yearly.max(axis=1))
        yearly_maximum.columns = ['Maximum']
        yearly_mean = pd.DataFrame(total_load_yearly.mean(axis=1).round(0))
        yearly_mean.columns = ['Mean']
        yearly_median = pd.DataFrame(np.percentile(total_load_yearly, 50, axis=1))
        yearly_median.columns = ['Median']
        yearly_load_statistics = pd.concat([yearly_maximum,yearly_mean,yearly_median],axis=1)
        return yearly_load_statistics
    
    def get_yearly_load_statistics(self,load_profile_filename):
        """
        Function:
            Outputs the load statistics for a prespecified load profile, which
              must have 'Domestic', 'Commercial' and 'Public' headings
        Inputs:
            load_profile_filename      Filename of load profile CSV
        Outputs:
            CSV file of yearly load statistics
        """        
        
        load_profile = pd.read_csv(self.device_load_filepath + load_profile_filename, index_col = 0).reset_index(drop=True)
        yearly_load_statistics = self.yearly_load_statistics(load_profile)
        yearly_load_statistics.to_csv(self.device_load_filepath + 'yearly_load_statistics.csv')        
   
# =============================================================================
#       Calculate the number of devices in use by the community
# =============================================================================
    def devices_in_use_hourly(self):
        """
        Function:
            Calculates the number of devices in use at each hour of the simulation.
        Inputs:
            Requires .csv files of device utilisation at daily resolution
        Outputs:
            Generates a .csv file for each device with the number in use at any 
            given time
        Notes:
            The number in use will always be less than or equal to the number
            owned by the community. Uses random binomial statistics.
        """                
        for i in range(len(self.device_inputs)):
            device_info = self.device_inputs.iloc[i]
            device_daily_profile = pd.read_csv(self.device_utilisation_filepath + device_info['Device'] + '_daily_times.csv', index_col = 0)
            device_daily_profile = device_daily_profile.reset_index(drop=True)
            daily_devices = pd.read_csv(self.device_ownership_filepath + device_info['Device'] + '_daily_ownership.csv', index_col = 0)
            daily_devices = daily_devices.reset_index(drop=True)
            device_hourlist = pd.DataFrame()
            print('Calculating number of '+device_info['Device']+'s in use\n')
            for day in range(0,365*int(self.location_inputs['Years'])):
                devices = float(daily_devices.iloc[day])
                day_profile = device_daily_profile.iloc[day]
                day_devices_on = pd.DataFrame(np.random.binomial(devices, day_profile))
                device_hourlist = device_hourlist.append(day_devices_on)
            device_hourlist.to_csv(self.device_usage_filepath + device_info['Device'] + '_in_use.csv')
        print('\nAll devices in use calculated')
        
    def get_device_daily_profile(self):
        """
        Function:
            Converts the monthly utilisation profiles to daily utilisation profiles.
        Inputs:
            Uses monthly utilisation profiles (e.g. "light_times.csv") which are generated
            prior to using the model. 
        Outputs:
            Gives a .csv for each device with the utilisation at a daily resolution
        Notes:
            Gives a daily utilisation for all devices, even those which are not 
            permitted by "Devices.csv"
        """        
        for i in range(len(self.device_inputs)):
            device_info = self.device_inputs.iloc[i]
            monthly_profile = pd.read_csv(self.device_utilisation_filepath + device_info['Device'] + '_times.csv',header = None, index_col = None)
            yearly_profile = Conversion().monthly_profile_to_daily_profile(monthly_profile)
            yearly_profile = pd.DataFrame.transpose(yearly_profile)
            total_profile = yearly_profile
            for j in range(0,int(self.location_inputs['Years']) - 1):
                total_profile = total_profile.append(yearly_profile)
            total_profile.to_csv(self.device_utilisation_filepath + device_info['Device'] + '_daily_times.csv')

# =============================================================================
#      Calculate the total number of each device owned by the community 
# =============================================================================
    def number_of_devices_daily(self):
        """
        Function:
            Calculates the number of devices owned by the community on each day
        Inputs:
            Takes inputs from "Devices.csv" in the "Load" folder
            Use "Devices.csv" to add new devices, permit or deny devices to be used,
            define the device power, and how quickly it is adopted
        Outputs:
            Returns a .csv of the number of devives that are owned by the community
            on a given day. Devices which are not permitted by "Devices.csv" should
            return a list composed entirely of zeroes.
        """
        for i in range(len(self.device_inputs)):
            device_info = self.device_inputs.iloc[i]
            if device_info['Available']=='Y':
                init,fin,inno,imit = device_info[3:7]
                pop = self.population_growth_daily()
                if fin != init:
                    cum_sales = self.cumulative_sales_daily(init,fin,inno,imit)
                    daily_ownership = pd.DataFrame(np.floor(cum_sales * pop))
                else:
                    daily_ownership = pd.DataFrame(np.floor(pop * init))
            elif device_info['Available']=='N':
                daily_ownership = pd.DataFrame(np.zeros((int(self.location_inputs['Years'])*365, 1)))
            daily_ownership.to_csv(self.device_ownership_filepath + device_info['Device'] + '_daily_ownership.csv')
                
    def population_growth_daily(self):
        """
        Function:
            Calculates the growth in the number of households in the community
        Inputs:
            Takes inputs from "Location inputs.csv" in the "Location data" folder
        Outputs:
            Gives a DataFrame of the number of households in the community for each day
        Notes:
            Simple compound interest-style growth rate
        """        
        community_size = float(self.location_inputs['Community size'])
        growth_rate = float(self.location_inputs['Community growth rate'])
        years = int(self.location_inputs['Years'])
        population = []
        growth_rate_daily = (1 + growth_rate)**(1/365.0) - 1
        for t in range(0,365*years):
            population.append(math.floor(community_size * (1 + growth_rate_daily)**t))
        return pd.DataFrame(population)

    def population_hourly(self):
        """
        Function:
            Calculates the growth in the number of households in the community for each hour
        Inputs:
            Takes inputs from "Location inputs.csv" in the "Location data" folder
        Outputs:
            Gives a DataFrame of the number of households in the community for each hour
        Notes:
            Simple compound interest-style growth rate
        """        
        community_size = float(self.location_inputs['Community size'])
        growth_rate = float(self.location_inputs['Community growth rate'])
        years = int(self.location_inputs['Years'])
        population = []
        growth_rate_hourly = (1 + growth_rate)**(1/(24.0 * 365.0)) - 1
        for t in range(0,365*24*years):
            population.append(math.floor(community_size * (1 + growth_rate_hourly)**t))
        return pd.DataFrame(population)

    def cumulative_sales_daily(self, current_market_prop, max_market_prop, innovation, imitation):
        """
        Function:
            Calculates the cumulative sales (ownership) of devices in the community
            over the lifetime of the simulation
        Inputs:
            Takes inputs of average initial and final ownership and coefficients of 
            innovation and imitation from "Domestic devices.csv" in Load folder
        Outputs:
            Gives a dataframe of the ownership of that device type for each day 
        Notes:
            Uses the Bass diffusion model
        """
        c = current_market_prop  
        m = max_market_prop - current_market_prop
        p = innovation/365
        q = imitation/365       
        cum_sales = []
        years = int(self.location_inputs['Years'])
        for t in range(0,365*years):
            num = 1 - math.exp(-1 * (p + q) * t)
            den = 1 + (q / p) * math.exp(-1 * (p+q) * t)  
            cum_sales.append(m * num/ den + c)   
        return pd.DataFrame(cum_sales)
