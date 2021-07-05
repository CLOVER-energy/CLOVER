# -*- coding: utf-8 -*-
"""
===============================================================================
                      GREENHOUSE GAS EMISSIONS IMPACT FILE
===============================================================================
                            Most recent update:
                              1 February 2019
===============================================================================
Made by:
    Philip Sandwell
Copyright:
    Philip Sandwell, 2019
For more information, please email:
    philip.sandwell@googlemail.com
===============================================================================
"""

import numpy as np
import pandas as pd

import sys
from ..conversion.conversion import Conversion

class GHGs():
    def __init__(self):
        self.location = "Bahraich"
        self.CLOVER_filepath = os.getcwd()
<<<<<<< Updated upstream:clover/impact/ghgs.py
        self.location_filepath = os.path.join(self.CLOVER_filepath, 'Locations', self.location)
=======
        self.location_filepath = os.path.join(self.CLOVER_filepath, 'locations', self.location)
>>>>>>> Stashed changes:clover/impact/ghgs.py
        self.location_inputs = pd.read_csv(self.location_filepath + '/Location Data/Location inputs.csv',header=None,index_col=0)[1]
        self.GHG_filepath = os.path.join(self.location_filepath, 'Impact', 'GHG inputs.csv')
        self.GHG_inputs  = pd.read_csv(self.GHG_filepath,header=None,index_col=0).round(decimals=3)[1]
        self.finance_filepath = os.path.join(self.location_filepath, 'Impact', 'Finance inputs.csv')
        self.finance_inputs  = pd.read_csv(self.finance_filepath,header=None,index_col=0).round(decimals=3)[1]
        self.inverter_inputs = pd.read_csv(os.path.join(self.location_filepath, 'Load', 'Device load', 'yearly_load_statistics.csv'),index_col=0)

#%%
#==============================================================================
#   EQUIPMENT GHGs
#       Installation GHGs for new equipment installations
#==============================================================================
#   PV array GHGs
    def get_PV_GHGs(self,PV_array_size,year=0):
        '''
        Function:
            Calculates GHGs of PV
        Inputs:
            PV_array_size       Capacity of PV being installed
            year                Installation year
        Outputs:
            GHGs 
        '''  
        PV_GHGs = PV_array_size * self.GHG_inputs.loc['PV GHGs']
        annual_reduction = 0.01 * self.GHG_inputs.loc['PV GHG decrease']
        return PV_GHGs * (1.0 - annual_reduction)**year
#   PV balance of systems GHGs
    def get_BOS_GHGs(self,PV_array_size,year=0):
        '''
        Function:
            Calculates GHGs of PV BOS
        Inputs:
            PV_array_size       Capacity of PV being installed
            year                Installation year
        Outputs:
            GHGs
        '''          
        BOS_GHGs = PV_array_size * self.GHG_inputs.loc['BOS GHGs']
        annual_reduction = 0.01 * self.GHG_inputs.loc['BOS GHG decrease']
        return BOS_GHGs * (1.0 - annual_reduction)**year
#   Battery storage GHGs
    def get_storage_GHGs(self,storage_size,year=0):
        '''
        Function:
            Calculates GHGs of battery storage
        Inputs:
            storage_size        Capacity of battery storage being installed
            year                Installation year
        Outputs:
            GHGs 
        '''  
        storage_GHGs = storage_size * self.GHG_inputs.loc['Storage GHGs']
        annual_reduction = 0.01 * self.GHG_inputs.loc['Storage GHG decrease']
        return storage_GHGs * (1.0 - annual_reduction)**year
#   Diesel generator GHGs
    def get_diesel_GHGs(self,diesel_size,year=0):
        '''
        Function:
            Calculates GHGs of diesel generator
        Inputs:
            diesel_size         Capacity of diesel generator being installed
            year                Installation year
        Outputs:
            GHGs 
        '''
        diesel_GHGs = diesel_size * self.GHG_inputs.loc['Diesel generator GHGs']
        annual_reduction = 0.01 * self.GHG_inputs.loc['Diesel generator GHG decrease']
        return diesel_GHGs * (1.0 - annual_reduction)**year
#   Installation GHGs
    def get_installation_GHGs(self,PV_array_size,diesel_size,year=0):
        '''
        Function:
            Calculates GHGs of installation
        Inputs:
            PV_array_size       Capacity of PV being installed
            diesel_size         Capacity of diesel generator being installed
            year                Installation year
        Outputs:
            GHGs 
        '''  
        PV_installation = PV_array_size * self.GHG_inputs.loc['PV installation GHGs']
        annual_reduction_PV = 0.01 * self.GHG_inputs.loc['PV installation GHG decrease']
        diesel_installation = diesel_size * self.GHG_inputs.loc['Diesel installation GHGs']
        annual_reduction_diesel = 0.01 * self.GHG_inputs.loc['Diesel installation GHG decrease']
        return PV_installation * (1.0 - annual_reduction_PV)**year + diesel_installation * (1.0 - annual_reduction_diesel)**year

#   Miscellaneous GHGs
    def get_misc_GHGs(self,PV_array_size,diesel_size):
        '''
        Function:
            Calculates GHGs of miscellaneous capacity-related equipment
        Inputs:
            PV_array_size       Capacity of PV being installed
            diesel_size         Capacity of diesel generator being installed
        Outputs:
            GHGs 
        '''  
        misc_GHGs = (PV_array_size + diesel_size) * self.GHG_inputs.loc['Misc. GHGs']
        return misc_GHGs

#   Total GHGs of newly installed equipment
    def get_total_equipment_GHGs(self,PV_array_size,storage_size,diesel_size,year=0):
        '''
        Function:
            Calculates GHGs of all newly installed equipment
        Inputs:
            PV_array_size       Capacity of PV being installed
            storage_size        Capacity of battery storage being installed
            diesel_size         Capacity of diesel generator being installed
            year                Installation year
        Outputs:
            GHGs 
        '''  
        PV_GHGs = self.get_PV_GHGs(PV_array_size,year)
        BOS_GHGs = self.get_BOS_GHGs(PV_array_size,year)
        storage_GHGs = self.get_storage_GHGs(storage_size,year)
        diesel_GHGs = self.get_diesel_GHGs(diesel_size,year)
        installation_GHGs = self.get_installation_GHGs(PV_array_size,diesel_size,year)
        misc_GHGs = self.get_misc_GHGs(PV_array_size,diesel_size)
        return PV_GHGs + BOS_GHGs + storage_GHGs + diesel_GHGs + installation_GHGs + misc_GHGs
#%%
##==============================================================================
##   EQUIPMENT GHGS
##       Find system equipment GHGs for new equipment
##==============================================================================
#
    def get_connections_GHGs(self,households,year=0):
        '''
        Function:
            Calculates GHGs of connecting households to the system
        Inputs:
            households          DataFrame of households from Energy_System().simulation(...)
            year                Installation year
        Outputs:
            GHGs 
        '''  
        households = pd.DataFrame(households)
        connection_GHGs = self.GHG_inputs.loc['Connection GHGs']
        new_connections = np.max(households) - np.min(households)
        connections_GHGs = float(connection_GHGs * new_connections)
        return connections_GHGs
    
#   Grid extension components
    def get_grid_extension_GHGs(self,grid_extension_distance,year):
        '''
        Function:
            Calculates GHGs of extending the grid network to a community
        Inputs:
            grid_extension_distance     Distance to the existing grid network
            year                        Installation year
        Outputs:
            GHGs 
        '''         
        grid_extension_GHGs = self.GHG_inputs.loc['Grid extension GHGs']    # per km
        grid_infrastructure_GHGs = self.GHG_inputs.loc['Grid infrastructure GHGs']
        return grid_extension_distance * grid_extension_GHGs + grid_infrastructure_GHGs
#%%
# =============================================================================
#   EQUIPMENT GHGs ON INDEPENDENT EQUIPMENT
#       Find GHGs on items independent of simulation periods
# =============================================================================

    def get_independent_GHGs(self,start_year,end_year):
        '''
        Function:
            Calculates GHGs of equipment which is independent of simulation periods
        Inputs:
            start_year        Start year of simulation period
            end_year          End year of simulation period
        Outputs:
            GHGs
        ''' 
        inverter_GHGs = self.get_inverter_GHGs(start_year,end_year)
        total_GHGs = inverter_GHGs # ... + other components as required
        return total_GHGs
#
    def get_inverter_GHGs(self,start_year,end_year):
        '''
        Function:
            Calculates GHGs of inverters based on load calculations
        Inputs:
            start_year        Start year of simulation period
            end_year          End year of simulation period
        Outputs:
            GHGs 
        '''
#   Initialise inverter replacement periods
        replacement_period = int(self.finance_inputs.loc['Inverter lifetime'])
        system_lifetime = int(self.location_inputs['Years'])
        replacement_intervals = pd.DataFrame(np.arange(0,system_lifetime,replacement_period))
        replacement_intervals.columns = ['Installation year']
#   Check if inverter should be replaced in the specified time interval
        if replacement_intervals.loc[replacement_intervals['Installation year'].isin(
                range(start_year,end_year))].empty == True:
            inverter_GHGs = float(0.0)
            return inverter_GHGs
#   Initialise inverter sizing calculation
        max_power = []
        inverter_step = float(self.finance_inputs.loc['Inverter size increment'])
        inverter_size = []
        for i in range(len(replacement_intervals)):
#   Calculate maximum power in interval years
            start = replacement_intervals['Installation year'].iloc[i]
            end = start + replacement_period
            max_power_interval = self.inverter_inputs['Maximum'].iloc[start:end].max()
            max_power.append(max_power_interval)
#   Calculate resulting inverter size
            inverter_size_interval = np.ceil(0.001*max_power_interval / inverter_step) * inverter_step
            inverter_size.append(inverter_size_interval)
        inverter_size = pd.DataFrame(inverter_size)
        inverter_size.columns = ['Inverter size (kW)']
        inverter_info = pd.concat([replacement_intervals,inverter_size],axis=1)
#   Calculate 
        inverter_info['Inverter GHGs (kgCO2/kW)'] = [self.GHG_inputs.loc['Inverter GHGs'] * 
                      (1 - 0.01*self.GHG_inputs.loc['Inverter GHG decrease'])
                      **inverter_info['Installation year'].iloc[i] for i in range(len(inverter_info))]
        inverter_info['Total GHGs (kgCO2)'] = [inverter_info['Inverter size (kW)'].iloc[i] *
                      inverter_info['Inverter GHGs (kgCO2/kW)'].iloc[i] 
                      for i in range(len(inverter_info))]
        inverter_GHGs = np.sum(inverter_info.loc[inverter_info['Installation year'].
                                 isin(np.array(range(start_year,end_year)))
                                 ]['Total GHGs (kgCO2)']).round(2)
        return inverter_GHGs

#%%
#==============================================================================
#   GHGs ON OPERATIONS
#       Find GHGs incurred during the simulation period
#==============================================================================
    def get_kerosene_GHGs(self,kerosene_lamps_in_use_hourly,start_year=0,end_year=20):
        '''
        Function:
            Calculates GHGs of kerosene usage. NB start_year and end_year are not necessary
                but are included for comparability to Finance().get_kerosene_expenditure(...)
        Inputs:
            kerosene_lamps_in_use_hourly        Output from Energy_System().simulation(...)
            start_year                          Start year of simulation period
            end_year                            End year of simulation period
        Outputs:
            GHGs 
        '''
        kerosene_GHGs = kerosene_lamps_in_use_hourly * self.GHG_inputs.loc['Kerosene GHGs']
#        total_daily_GHGs = Conversion().hourly_profile_to_daily_sum(kerosene_GHGs)
#        return total_daily_GHGs#.replace(np.nan,0.0)
        return np.sum(kerosene_GHGs)
    
    def get_kerosene_GHGs_mitigated(self,kerosene_lamps_mitigated_hourly,start_year=0,end_year=20):
        '''
        Function:
            Calculates GHGs of kerosene usage that has been avoided by using the system,
                NB start_year and end_year are not necessary but are included for comparability
                to Finance().get_kerosene_expenditure(...)
        Inputs:
            kerosene_lamps_mitigated_hourly     Output from Energy_System().simulation(...)
            start_year                          Start year of simulation period
            end_year                            End year of simulation period
        Outputs:
            GHGs 
        '''
        kerosene_GHGs = kerosene_lamps_mitigated_hourly * self.GHG_inputs.loc['Kerosene GHGs']
#        total_daily_GHGs = Conversion().hourly_profile_to_daily_sum(kerosene_GHGs)
        return np.sum(kerosene_GHGs)

    def get_grid_GHGs(self,grid_energy_hourly,start_year=0,end_year=20):
        '''
        Function:
            Calculates GHGs of grid electricity used by the system
        Inputs:
            grid_energy_hourly                  Output from Energy_System().simulation(...)
            start_year                          Start year of simulation period
            end_year                            End year of simulation period
        Outputs:
            GHGs 
        '''       
#   Initialise        
        system_lifetime = int(self.location_inputs['Years'])
        grid_GHGs_initial = self.GHG_inputs.loc['Grid GHGs (initial)']
        grid_GHGs_final = self.GHG_inputs.loc['Grid GHGs (final)']
        days = int(365 * (end_year - start_year))
        total_daily_energy = Conversion().hourly_profile_to_daily_sum(grid_energy_hourly)
#   Account for reduction in grid GHG intensity
        yearly_decrease = (grid_GHGs_initial - grid_GHGs_final) / system_lifetime
#        daily_decrease = yearly_decrease / days
        grid_GHGs_start = grid_GHGs_initial - start_year * yearly_decrease
        grid_GHGs_end = grid_GHGs_initial - end_year * yearly_decrease
        daily_emissions_intensity = pd.DataFrame(
                np.linspace(grid_GHGs_start,grid_GHGs_end,days))
#   Calculate daily emissions
        daily_emissions = total_daily_energy * daily_emissions_intensity
        return float(np.sum(daily_emissions,axis=0))
    

    def get_diesel_fuel_GHGs(self,diesel_fuel_usage_hourly,start_year=0,end_year=20):
        '''
        Function:
            Calculates GHGs of diesel fuel used by the system
        Inputs:
            diesel_fuel_usage_hourly            Output from Energy_System().simulation(...)
            start_year                          Start year of simulation period
            end_year                            End year of simulation period
        Outputs:
            GHGs 
        '''    
        diesel_fuel_GHGs = self.GHG_inputs.loc['Diesel fuel GHGs']       
        return float(np.sum(diesel_fuel_usage_hourly) * diesel_fuel_GHGs)

#%%  
#==============================================================================
#   OPERATION AND MAINTENANCE GHGS
#      Find O&M GHGs incurred during simulation  
#==============================================================================
#   PV O&M for entire PV array
    def get_PV_OM(self,PV_array_size,start_year=0,end_year=20):
        '''
        Function:
            Calculates O&M GHGs of PV the simulation period
        Inputs:
            PV_array_size           Capacity of PV installed
            start_year              Start year of simulation period
            end_year                End year of simulation period
        Outputs:
            GHGs 
        ''' 
        return PV_array_size * self.GHG_inputs.loc['PV O&M GHGs'] * (end_year - start_year)

#   Storage O&M for entire storage system
    def get_storage_OM(self,storage_size,start_year=0,end_year=20):
        '''
        Function:
            Calculates O&M GHGs of storage the simulation period
        Inputs:
            storage_size            Capacity of battery storage installed
            start_year              Start year of simulation period
            end_year                End year of simulation period
        Outputs:
            GHGs 
        ''' 
        return storage_size * self.GHG_inputs.loc['Storage O&M GHGs'] * (end_year - start_year)

#   Diesel O&M for entire diesel genset
    def get_diesel_OM(self,diesel_size,start_year=0,end_year=20):
        '''
        Function:
            Calculates O&M GHGs of diesel generation the simulation period
        Inputs:
            diesel_size             Capacity of diesel generator installed
            start_year              Start year of simulation period
            end_year                End year of simulation period
        Outputs:
            GHGs 
        '''         
        return diesel_size * self.GHG_inputs.loc['Diesel O&M GHGs'] * (end_year - start_year)

#   General O&M for entire energy system (e.g. general maintenance of wiring, etc.)
    def get_general_OM(self,start_year=0,end_year=20):
        '''
        Function:
            Calculates O&M GHGs of general components the simulation period
        Inputs:
            start_year              Start year of simulation period
            end_year                End year of simulation period
        Outputs:
            GHGs 
        ''' 
        return self.GHG_inputs.loc['General O&M GHGs'] * (end_year - start_year)

#   Total O&M for entire system
    def get_total_OM(self,PV_array_size,storage_size,diesel_size,start_year=0,end_year=20):
        '''
        Function:
            Calculates total O&M GHGs over the simulation period
        Inputs:
            PV_array_size           Capacity of PV installed
            storage_size            Capacity of battery storage installed
            diesel_size             Capacity of diesel generator installed            
            start_year              Start year of simulation period
            end_year                End year of simulation period
        Outputs:
            GHGs
        ''' 
        PV_OM = self.get_PV_OM(PV_array_size,start_year,end_year)
        storage_OM = self.get_storage_OM(storage_size,start_year,end_year)
        diesel_OM = self.get_diesel_OM(diesel_size,start_year,end_year)
        general_OM = self.get_general_OM(start_year,end_year)
        return PV_OM + storage_OM + diesel_OM + general_OM 
