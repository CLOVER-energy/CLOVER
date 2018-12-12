# -*- coding: utf-8 -*-
"""
===============================================================================
                           FINANCIAL IMPACT FILE
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
import numpy as np
import pandas as pd

import sys
sys.path.insert(0, '/***YOUR LOCAL FILE PATH***/CLOVER 4.0/Scripts/Conversion scripts')
from Conversion import Conversion

class Finance():
    def __init__(self):
        self.location = 'Bahraich'
        self.CLOVER_filepath = '/***YOUR LOCAL FILE PATH***/CLOVER 4.0'
        self.location_filepath = self.CLOVER_filepath + '/Locations/' + self.location
        self.location_inputs = pd.read_csv(self.location_filepath + '/Location Data/Location inputs.csv',header=None,index_col=0)[1]
        self.finance_filepath = self.location_filepath + '/Impact/Finance inputs.csv'
        self.finance_inputs  = pd.read_csv(self.finance_filepath,header=None,index_col=0).round(decimals=3)[1]
        self.inverter_inputs = pd.read_csv(self.location_filepath + '/Load/Device load/yearly_load_statistics.csv',index_col=0)

#%%
#==============================================================================
#   EQUIPMENT EXPENDITURE (NOT DISCOUNTED)
#       Installation costs (not discounted) for new equipment installations
#==============================================================================
#   PV array costs
    def get_PV_cost(self,PV_array_size,year=0):
        '''
        Function:
            Calculates cost of PV
        Inputs:
            PV_array_size       Capacity of PV being installed
            year                Installation year
        Outputs:
            Undiscounted cost 
        '''  
        PV_cost = PV_array_size * self.finance_inputs[1]['PV cost']
        annual_reduction = 0.01 * self.finance_inputs[1]['PV cost decrease']
        return PV_cost * (1.0 - annual_reduction)**year
#   PV balance of systems costs
    def get_BOS_cost(self,PV_array_size,year=0):
        '''
        Function:
            Calculates cost of PV BOS
        Inputs:
            PV_array_size       Capacity of PV being installed
            year                Installation year
        Outputs:
            Undiscounted cost 
        '''          
        BOS_cost = PV_array_size * self.finance_inputs[1]['BOS cost']
        annual_reduction = 0.01 * self.finance_inputs[1]['BOS cost decrease']
        return BOS_cost * (1.0 - annual_reduction)**year
#   Battery storage costs
    def get_storage_cost(self,storage_size,year=0):
        '''
        Function:
            Calculates cost of battery storage
        Inputs:
            storage_size        Capacity of battery storage being installed
            year                Installation year
        Outputs:
            Undiscounted cost 
        '''  
        storage_cost = storage_size * self.finance_inputs[1]['Storage cost']
        annual_reduction = 0.01 * self.finance_inputs[1]['Storage cost decrease']
        return storage_cost * (1.0 - annual_reduction)**year
#   Diesel generator costs
    def get_diesel_cost(self,diesel_size,year=0):
        '''
        Function:
            Calculates cost of diesel generator
        Inputs:
            diesel_size         Capacity of diesel generator being installed
            year                Installation year
        Outputs:
            Undiscounted cost 
        '''
        diesel_cost = diesel_size * self.finance_inputs[1]['Diesel generator cost']
        annual_reduction = 0.01 * self.finance_inputs[1]['Diesel generator cost decrease']
        return diesel_cost * (1.0 - annual_reduction)**year
#   Installation costs
    def get_installation_cost(self,PV_array_size,diesel_size,year=0):
        '''
        Function:
            Calculates cost of installation
        Inputs:
            PV_array_size       Capacity of PV being installed
            diesel_size         Capacity of diesel generator being installed
            year                Installation year
        Outputs:
            Undiscounted cost 
        '''  
        PV_installation = PV_array_size * self.finance_inputs[1]['PV installation cost']
        annual_reduction_PV = 0.01 * self.finance_inputs[1]['PV installation cost decrease']
        diesel_installation = diesel_size * self.finance_inputs[1]['Diesel installation cost']
        annual_reduction_diesel = 0.01 * self.finance_inputs[1]['Diesel installation cost decrease']
        return PV_installation * (1.0 - annual_reduction_PV)**year + diesel_installation * (1.0 - annual_reduction_diesel)**year

#   Miscellaneous costs
    def get_misc_costs(self,PV_array_size,diesel_size):
        '''
        Function:
            Calculates cost of miscellaneous capacity-related costs
        Inputs:
            PV_array_size       Capacity of PV being installed
            diesel_size         Capacity of diesel generator being installed
        Outputs:
            Undiscounted cost 
        '''  
        misc_costs = (PV_array_size + diesel_size) * self.finance_inputs[1]['Misc. costs']
        return misc_costs

#   Total cost of newly installed equipment
    def get_total_equipment_cost(self,PV_array_size,storage_size,diesel_size,year=0):
        '''
        Function:
            Calculates cost of all equipment costs
        Inputs:
            PV_array_size       Capacity of PV being installed
            storage_size        Capacity of battery storage being installed
            diesel_size         Capacity of diesel generator being installed
            year                Installation year
        Outputs:
            Undiscounted cost 
        '''  
        PV_cost = self.get_PV_cost(PV_array_size,year)
        BOS_cost = self.get_BOS_cost(PV_array_size,year)
        storage_cost = self.get_storage_cost(storage_size,year)
        diesel_cost = self.get_diesel_cost(diesel_size,year)
        installation_cost = self.get_installation_cost(PV_array_size,diesel_size,year)
        misc_costs = self.get_misc_costs(PV_array_size,diesel_size)
        return PV_cost + BOS_cost + storage_cost + diesel_cost + installation_cost + misc_costs
#%%
#==============================================================================
#   EQUIPMENT EXPENDITURE (DISCOUNTED)
#       Find system equipment capital expenditure (discounted) for new equipment
#==============================================================================
    def discounted_equipment_cost(self,PV_array_size,storage_size,diesel_size,year=0):
        '''
        Function:
            Calculates cost of all equipment costs
        Inputs:
            PV_array_size       Capacity of PV being installed
            storage_size        Capacity of battery storage being installed
            diesel_size         Capacity of diesel generator being installed
            year                Installation year
        Outputs:
            Discounted cost 
        '''  
        undiscounted_cost = self.get_total_equipment_cost(PV_array_size,storage_size,diesel_size,year)
        discount_fraction = (1.0 - self.finance_inputs[1]['Discount rate'])**year
        return undiscounted_cost * discount_fraction

    def get_connections_expenditure(self,households,year=0):
        '''
        Function:
            Calculates cost of connecting households to the system
        Inputs:
            households          DataFrame of households from Energy_System().simulation(...)
            year                Installation year
        Outputs:
            Discounted cost 
        '''  
        households = pd.DataFrame(households)
        connection_cost = self.finance_inputs[1]['Connection cost']
        new_connections = np.max(households) - np.min(households)
        undiscounted_cost = float(connection_cost * new_connections)
        discount_fraction = (1.0 - self.finance_inputs[1]['Discount rate'])**year
        total_discounted_cost = undiscounted_cost * discount_fraction
#   Section in comments allows a more accurate consideration of the discounted 
#        cost for new connections, but substantially increases the processing time. 
        
#        new_connections = [0]
#        for t in range(int(households.shape[0])-1):
#            new_connections.append(households['Households'][t+1] - households['Households'][t])
#        new_connections = pd.DataFrame(new_connections)
#        new_connections_daily = Conversion().hourly_profile_to_daily_sum(new_connections)
#        total_daily_cost = connection_cost * new_connections_daily
#        total_discounted_cost = self.discounted_cost_total(total_daily_cost,start_year,end_year)
        return total_discounted_cost
    
#   Grid extension components
    def get_grid_extension_cost(self,grid_extension_distance,year):
        '''
        Function:
            Calculates cost of extending the grid network to a community
        Inputs:
            grid_extension_distance     Distance to the existing grid network
            year                        Installation year
        Outputs:
            Discounted cost 
        '''         
        grid_extension_cost = self.finance_inputs[1]['Grid extension cost']    # per km
        grid_infrastructure_cost = self.finance_inputs[1]['Grid infrastructure cost']
        discount_fraction = (1.0 - self.finance_inputs[1]['Discount rate'])**year
        return grid_extension_distance * grid_extension_cost * discount_fraction + grid_infrastructure_cost
#%%
# =============================================================================
#   EQUIPMENT EXPENDITURE (DISCOUNTED) ON INDEPENDENT EXPENDITURE
#       Find expenditure (discounted) on items independent of simulation periods
# =============================================================================

    def get_independent_expenditure(self,start_year,end_year):
        '''
        Function:
            Calculates cost of equipment which is independent of simulation periods
        Inputs:
            start_year        Start year of simulation period
            end_year          End year of simulation period
        Outputs:
            Discounted cost 
        ''' 
        inverter_expenditure = self.get_inverter_expenditure(start_year,end_year)
        total_expenditure = inverter_expenditure # ... + other components as required
        return total_expenditure

    def get_inverter_expenditure(self,start_year,end_year):
        '''
        Function:
            Calculates cost of inverters based on load calculations
        Inputs:
            start_year        Start year of simulation period
            end_year          End year of simulation period
        Outputs:
            Discounted cost 
        '''
#   Initialise inverter replacement periods
        replacement_period = int(self.finance_inputs[1]['Inverter lifetime'])
        system_lifetime = int(self.location_inputs['Years'])
        replacement_intervals = pd.DataFrame(np.arange(0,system_lifetime,replacement_period))
        replacement_intervals.columns = ['Installation year']
#   Check if inverter should be replaced in the specified time interval
        if replacement_intervals.loc[replacement_intervals['Installation year'].isin(
                range(start_year,end_year))].empty == True:
            inverter_discounted_cost = float(0.0)
            return inverter_discounted_cost
#   Initialise inverter sizing calculation
        max_power = []
        inverter_step = float(self.finance_inputs[1]['Inverter size increment'])
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
        inverter_info['Discount rate'] = [(1 - self.finance_inputs[1]['Discount rate']) ** 
                     inverter_info['Installation year'].iloc[i] for i in range(len(inverter_info))]
        inverter_info['Inverter cost ($/kW)'] = [self.finance_inputs[1]['Inverter cost'] * 
                      (1 - 0.01*self.finance_inputs[1]['Inverter cost decrease'])
                      **inverter_info['Installation year'].iloc[i] for i in range(len(inverter_info))]
        inverter_info['Discounted expenditure ($)'] = [inverter_info['Discount rate'].iloc[i] * 
                      inverter_info['Inverter size (kW)'].iloc[i] * inverter_info['Inverter cost ($/kW)'].iloc[i] 
                      for i in range(len(inverter_info))]
        inverter_discounted_cost = np.sum(inverter_info.loc[inverter_info['Installation year'].
                                 isin(np.array(range(start_year,end_year)))
                                 ]['Discounted expenditure ($)']).round(2)
        return inverter_discounted_cost
#%%
#==============================================================================
#   EXPENDITURE (DISCOUNTED) ON RUNNING COSTS
#       Find expenditure (discounted) incurred during the simulation period
#==============================================================================
    def get_kerosene_expenditure(self,kerosene_lamps_in_use_hourly,start_year=0,end_year=20):
        '''
        Function:
            Calculates cost of kerosene usage
        Inputs:
            kerosene_lamps_in_use_hourly        Output from Energy_System().simulation(...)
            start_year                          Start year of simulation period
            end_year                            End year of simulation period
        Outputs:
            Discounted cost 
        '''
        kerosene_cost = kerosene_lamps_in_use_hourly * self.finance_inputs[1]['Kerosene cost']
        total_daily_cost = Conversion().hourly_profile_to_daily_sum(kerosene_cost)
        total_discounted_cost = self.discounted_cost_total(total_daily_cost,start_year,end_year)
        return total_discounted_cost
    
    def get_kerosene_expenditure_mitigated(self,kerosene_lamps_mitigated_hourly,start_year=0,end_year=20):
        '''
        Function:
            Calculates cost of kerosene usage that has been avoided by using the system
        Inputs:
            kerosene_lamps_mitigated_hourly     Output from Energy_System().simulation(...)
            start_year                          Start year of simulation period
            end_year                            End year of simulation period
        Outputs:
            Discounted cost 
        '''
        kerosene_cost = kerosene_lamps_mitigated_hourly * self.finance_inputs[1]['Kerosene cost']
        total_daily_cost = Conversion().hourly_profile_to_daily_sum(kerosene_cost)
        total_discounted_cost = self.discounted_cost_total(total_daily_cost,start_year,end_year)
        return total_discounted_cost

    def get_grid_expenditure(self,grid_energy_hourly,start_year=0,end_year=20):
        '''
        Function:
            Calculates cost of grid electricity used by the system
        Inputs:
            grid_energy_hourly                  Output from Energy_System().simulation(...)
            start_year                          Start year of simulation period
            end_year                            End year of simulation period
        Outputs:
            Discounted cost 
        '''        
        grid_cost = grid_energy_hourly * self.finance_inputs[1]['Grid cost']
        total_daily_cost = Conversion().hourly_profile_to_daily_sum(grid_cost)
        total_discounted_cost = self.discounted_cost_total(total_daily_cost,start_year,end_year)
        return total_discounted_cost

    def get_diesel_fuel_expenditure(self,diesel_fuel_usage_hourly,start_year=0,end_year=20):
        '''
        Function:
            Calculates cost of diesel fuel used by the system
        Inputs:
            diesel_fuel_usage_hourly            Output from Energy_System().simulation(...)
            start_year                          Start year of simulation period
            end_year                            End year of simulation period
        Outputs:
            Discounted cost 
        '''    
        diesel_fuel_usage_daily = Conversion().hourly_profile_to_daily_sum(diesel_fuel_usage_hourly)
        start_day = start_year * 365
        end_day = end_year * 365
        diesel_price_daily = []
        original_diesel_price = self.finance_inputs[1]['Diesel fuel cost']
        r_y = 0.01 * self.finance_inputs[1]['Diesel fuel cost decrease']
        r_d = ((1.0 + r_y) ** (1.0/365.0)) - 1.0
        for t in range(start_day,end_day):
            diesel_price = original_diesel_price * (1.0 - r_d)**t
            diesel_price_daily.append(diesel_price)
        diesel_price_daily =  pd.DataFrame(diesel_price_daily)
        total_daily_cost = pd.DataFrame(diesel_fuel_usage_daily.values * diesel_price_daily.values)
        total_discounted_cost = self.discounted_cost_total(total_daily_cost,start_year,end_year)
        return total_discounted_cost
#%%  
#==============================================================================
#   OPERATION AND MAINTENANCE EXPENDITURE (DISCOUNTED)
#      Find O&M costs (discounted) incurred during simulation  
#==============================================================================
#   PV O&M for entire PV array
    def get_PV_OM(self,PV_array_size,start_year=0,end_year=20):
        '''
        Function:
            Calculates O&M cost of PV the simulation period
        Inputs:
            PV_array_size           Capacity of PV installed
            start_year              Start year of simulation period
            end_year                End year of simulation period
        Outputs:
            Discounted cost 
        ''' 
        PV_OM_cost = PV_array_size * self.finance_inputs[1]['PV O&M']             # $ per year
        PV_OM_cost_daily = PV_OM_cost / 365.0                                     # $ per day 
        total_daily_cost = pd.DataFrame([PV_OM_cost_daily]*(end_year-start_year)*365)
        return self.discounted_cost_total(total_daily_cost,start_year,end_year)

#   Storage O&M for entire storage system
    def get_storage_OM(self,storage_size,start_year=0,end_year=20):
        '''
        Function:
            Calculates O&M cost of storage the simulation period
        Inputs:
            storage_size            Capacity of battery storage installed
            start_year              Start year of simulation period
            end_year                End year of simulation period
        Outputs:
            Discounted cost 
        ''' 
        storage_OM_cost = storage_size * self.finance_inputs[1]['Storage O&M']     # $ per year
        storage_OM_cost_daily = storage_OM_cost / 365.0                            # $ per day 
        total_daily_cost = pd.DataFrame([storage_OM_cost_daily]*(end_year-start_year)*365)
        return self.discounted_cost_total(total_daily_cost,start_year,end_year)
    
#   Diesel O&M for entire diesel genset
    def get_diesel_OM(self,diesel_size,start_year=0,end_year=20):
        '''
        Function:
            Calculates O&M cost of diesel generation the simulation period
        Inputs:
            diesel_size             Capacity of diesel generator installed
            start_year              Start year of simulation period
            end_year                End year of simulation period
        Outputs:
            Discounted cost 
        '''         
        diesel_OM_cost = diesel_size * self.finance_inputs[1]['Diesel O&M']         # $ per year
        diesel_OM_cost_daily = diesel_OM_cost / 365.0                               # $ per day 
        total_daily_cost = pd.DataFrame([diesel_OM_cost_daily]*(end_year-start_year)*365)
        return self.discounted_cost_total(total_daily_cost,start_year,end_year)
    
#   General O&M for entire energy system (e.g. for staff, land hire etc.)
    def get_general_OM(self,start_year=0,end_year=20):
        '''
        Function:
            Calculates O&M cost of general components the simulation period
        Inputs:
            start_year              Start year of simulation period
            end_year                End year of simulation period
        Outputs:
            Discounted cost 
        ''' 
        general_OM_cost = self.finance_inputs[1]['General O&M']                     # $ per year
        general_OM_cost_daily = general_OM_cost / 365.0                             # $ per day 
        total_daily_cost = pd.DataFrame([general_OM_cost_daily]*(end_year-start_year)*365)
        return self.discounted_cost_total(total_daily_cost,start_year,end_year)

#   Total O&M for entire system
    def get_total_OM(self,PV_array_size,storage_size,diesel_size,start_year=0,end_year=20):
        '''
        Function:
            Calculates total O&M cost over the simulation period
        Inputs:
            PV_array_size           Capacity of PV installed
            storage_size            Capacity of battery storage installed
            diesel_size             Capacity of diesel generator installed            
            start_year              Start year of simulation period
            end_year                End year of simulation period
        Outputs:
            Discounted cost 
        ''' 
        PV_OM = self.get_PV_OM(PV_array_size,start_year,end_year)
        storage_OM = self.get_storage_OM(storage_size,start_year,end_year)
        diesel_OM = self.get_diesel_OM(diesel_size,start_year,end_year)
        general_OM = self.get_general_OM(start_year,end_year)
        return PV_OM + storage_OM + diesel_OM + general_OM 
#%%       
#==============================================================================
#   FINANCING CALCULATIONS
#       Functions to calculate discount rates and discounted expenditures
#==============================================================================
    def daily_discount_rate(self):
        '''
        Function:
            Calculates equivalent discount rate at a daily resolution
        '''
        r_y = self.finance_inputs[1]['Discount rate']
        return ((1.0 + r_y) ** (1.0/365.0)) - 1.0
    
    def discounted_fraction(self,start_year = 0, end_year = 20):
        '''
        Function:
            Calculates the discounted fraction at a daily resolution
        Inputs:
            start_year              Start year of simulation period
            end_year                End year of simulation period
        Outputs:
            Discounted fraction for each day of the simulation 
        ''' 
        start_day = int(start_year * 365)
        end_day = int(end_year * 365)
        discounted_fraction_array = []
        r_d = self.daily_discount_rate()
        denominator = (1.0 + r_d)
        for t in range(start_day,end_day):
            discounted_fraction_array.append(denominator ** -t)
        return pd.DataFrame(discounted_fraction_array)
    
    def discounted_cost_total(self,total_cost_daily,start_year=0,end_year=20):
        '''
        Function:
            Calculates the discounted expenditure
        Inputs:
            total_cost_daily        Undiscounted costs at a daily resolution
            start_year              Start year of simulation period
            end_year                End year of simulation period
        Outputs:
            Discounted cost total
        ''' 
        discounted_fraction = self.discounted_fraction(start_year,end_year)
        discounted_cost = discounted_fraction * total_cost_daily
        return np.sum(discounted_cost)[0]
    
    def discounted_energy_total(self,total_energy_daily,start_year=0,end_year=20):
        '''
        Function:
            Calculates the discounted energy
        Inputs:
            total_energy_daily      Undiscounted energy at a daily resolution
            start_year              Start year of simulation period
            end_year                End year of simulation period
        Outputs:
            Discounted energy total
        ''' 
        discounted_fraction = self.discounted_fraction(start_year,end_year)
        discounted_energy = discounted_fraction * total_energy_daily
        return np.sum(discounted_energy)[0]

#   Calculate LCUE using total discounted costs ($) and discounted energy (kWh)
    def get_LCUE(self,total_discounted_costs,total_discounted_energy):
        '''
        Function:
            Calculates the levelised cost of used electricity (LCUE)
        Inputs:
            total_discounted_costs        Discounted costs total
            total_discounted_energy       Discounted energy total  
        Outputs:
            Levelised cost of used electricity
        ''' 
        return total_discounted_costs / total_discounted_energy        