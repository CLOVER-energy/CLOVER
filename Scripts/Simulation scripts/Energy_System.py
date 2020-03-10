# -*- coding: utf-8 -*-
"""
===============================================================================
                        ENERGY SYSTEM SIMULATION FILE
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
import numpy as np
import pandas as pd
import datetime
import math

import sys
sys.path.insert(0, '/***YOUR LOCAL FILE PATH***/CLOVER 4.0/Scripts/Generation scripts/')
from Solar import Solar
from Diesel import Diesel
import sys
sys.path.insert(0, '/***YOUR LOCAL FILE PATH***/CLOVER 4.0/Scripts/Load scripts/')
from Load import Load
#%%
class Energy_System():
    def __init__(self):
        self.location = 'Bahraich'
        self.CLOVER_filepath = '/***YOUR LOCAL FILE PATH***/CLOVER 4.0'
        self.generation_filepath = self.location_filepath + '/Generation/'
        self.diesel_filepath = self.generation_filepath + '/Diesel/'
        self.location_data_filepath = self.location_filepath + '/Location Data/'
        self.energy_system_filepath = self.location_filepath + '/Simulation/Energy system inputs.csv'
        self.energy_system_inputs  = pd.read_csv(self.energy_system_filepath,header=None,index_col=0).round(decimals=3)
        self.scenario_inputs = pd.read_csv(self.location_filepath + '/Scenario/Scenario inputs.csv' ,header=None,index_col=0).round(decimals=3)
        self.diesel_inputs = pd.read_csv(self.diesel_filepath + 'Diesel inputs.csv', header=None, index_col=0)
        self.kerosene_data_filepath = self.location_filepath + '/Load/Devices in use/kerosene_in_use.csv'
        self.kerosene_usage = pd.read_csv(self.kerosene_data_filepath, index_col = 0).reset_index(drop=True)
        self.simulation_storage = self.location_filepath + '/Simulation/Saved simulations/'

#%%
# =============================================================================
# SIMULATION FUNCTIONS
#       This function simulates the energy system of a given capacity and to
#       the parameters stated in the input files.  
# =============================================================================
    def simulation(self, start_year = 0, end_year = 4,
                   PV_size = 10, storage_size = 10, **options):
        '''
        Function:
            Simulates a minigrid system
        Inputs:
            start_year          Start year of this simulation period
            end_year            End year of this simulation period
            PV_size             Amount of PV in kWp
            storage_size        Amount of storage in kWh
            
        Outputs:
            tuple([system_performance_outputs,system_details]):
                system_performance_outputs          Hourly performance of the simulated system
                    load_energy                     Amount of energy (kWh) required to satisfy the loads
                    total_energy_used               Amount of energy (kWh) used by the system
                    unmet_energy                    Amount of energy (kWh) unmet by the system
                    blackout_times                  Times with power is available (0) or unavailable (1)
                    renewables_energy_used_directly Amount of energy (kWh) from renewables used directly to satisfy load (kWh)
                    storage_power_supplied          Amount of energy (kWh) supplied by battery storage
                    grid_energy                     Amount of energy (kWh) supplied by the grid
                    diesel_energy                   Amount of energy (kWh) supplied from diesel generator
                    diesel_times                    Times when diesel generator is on (1) or off (0)
                    diesel_fuel_usage               Amount of diesel (l) used by the generator
                    storage_profile                 Amount of energy (kWh) into (+ve) and out of (-ve) the battery
                    renewables_energy               Amount of energy (kWh) provided by renewables to the system
                    hourly_storage                  Amount of energy (kWh) in the battery
                    energy_surplus                  Amount of energy (kWh) dumped owing to overgeneration
                    battery_health                  Relative capactiy of the battery compared to new (0.0-1.0)
                    households                      Number of households in the community
                    kerosene_usage                  Number of kerosene lamps in use (if no power available)
                    kerosene_mitigation             Number of kerosene lamps not used (when power is available)
                system details                      Information about the installed system     
                    Start year                      Start year of the simulation
                    End year                        End year of the simulation
                    Initial PV size                 Capacity of PV installed (kWp)
                    Initial storage size            Capacity of battery storage installed (kWh)
                    Final PV size                   Equivalent capacity of PV (kWp) after simulation
                    Final storage size              Equivalent capacity of battery storage (kWh) after simulation
                    Diesel capacity                 Capacity of diesel generation installed (kW)
        '''
#   Start timer to see how long simulation will take
        timer_start = datetime.datetime.now()

#   Initialise values for simulation
        PV_size = float(PV_size)
        storage_size= float(storage_size)
        
#   Get input profiles
        input_profiles = self.get_storage_profile(start_year, end_year, PV_size, **options)
        load_energy = pd.DataFrame(input_profiles['Load energy (kWh)'])
        renewables_energy = pd.DataFrame(input_profiles['Renewables energy supplied (kWh)'])
        renewables_energy_used_directly = pd.DataFrame(input_profiles['Renewables energy used (kWh)'])
        grid_energy = pd.DataFrame(input_profiles['Grid energy (kWh)']).abs()
        storage_profile = pd.DataFrame(input_profiles['Storage profile (kWh)'])
        kerosene_profile = pd.DataFrame(input_profiles['Kerosene lamps'])
        dispatched_diesel_profile = pd.DataFrame(input_profiles['Timed dispatchable diesel profile'])
        households = pd.DataFrame(Load().population_hourly()[start_year*8760:end_year*8760].values)
           
#   Initialise battery storage parameters 
        max_energy_throughput = storage_size * self.energy_system_inputs[1]['Battery cycle lifetime']
        initial_storage = storage_size * self.energy_system_inputs[1]['Battery maximum charge']
        max_storage = storage_size * self.energy_system_inputs[1]['Battery maximum charge']
        min_storage = storage_size * self.energy_system_inputs[1]['Battery minimum charge']
        battery_leakage = self.energy_system_inputs[1]['Battery leakage']
        battery_eff_in = self.energy_system_inputs[1]['Battery conversion in']
        battery_eff_out = self.energy_system_inputs[1]['Battery conversion out']
        battery_C_rate_out = self.energy_system_inputs[1]['Battery C rate discharging']
        battery_C_rate_in = self.energy_system_inputs[1]['Battery C rate charging']
        battery_lifetime_loss = self.energy_system_inputs[1]['Battery lifetime loss']
        max_storage_energy_in = storage_size * battery_C_rate_in
        cumulative_storage_power = 0.0
        hourly_storage = []
        new_hourly_storage = []
        battery_health = []
        
#   Initialise simulation parameters
        diesel_backup_status = self.scenario_inputs[1]['Diesel backup']
        diesel_backup_threshold = float(self.scenario_inputs[1]['Diesel backup threshold'])

#   Dispatchable Diesel parameters
        dispatched_diesel_status = self.scenario_inputs[1]['Dispatchable diesel']
        diesel_capacity_dd = float(self.diesel_inputs[1]['Diesel size'])
        diesel_dispatched_timed_minimum_SOC = float(self.scenario_inputs[1]['Dispatchable diesel '
                                                                            'timed minimum battery SOC'])
        diesel_dispatched_universal_minimum_SOC = float(self.scenario_inputs[1]['Dispatchable diesel '
                                                                                'universal minimum battery SOC'])
        diesel_dispatched_timed_switch_off_SOC = float(self.scenario_inputs[1]['Dispatchable diesel '
                                                                               'timed switch off SOC'])
        diesel_dispatched_universal_switch_off_SOC = float(self.scenario_inputs[1]['Dispatchable diesel '
                                                                                   'universal switch off SOC'])
        min_diesel_capacity = diesel_capacity_dd * float(self.diesel_inputs[1]['Diesel minimum load'])
        print(min_diesel_capacity)
        max_diesel_energy_in = min(storage_size * battery_C_rate_in, diesel_capacity_dd)
        print(max_diesel_energy_in)
        if max_storage_energy_in > max_diesel_energy_in:
            max_solar_in = max_storage_energy_in - max_diesel_energy_in
        else:
            max_solar_in = 0

#   Initialise energy accounting parameters 
        energy_surplus = []
        energy_deficit = []
        storage_power_supplied = []

#   Initialise dispatched diesel accounting parameters
        dispatched_diesel_used = []
        dispatched_diesel_supplied = []
        dispatched_diesel_surplus = []
        empty_capacity_list = []
        state_of_charge_list = []
        dd_on = [0]
#   Begin simulation, iterating over time-steps

        for t in range(0,int(storage_profile.size)):

#   Check if any storage is being used
            if storage_size == 0:
                simulation_hours = int(storage_profile.size)
                hourly_storage = pd.DataFrame([0]*simulation_hours)
                storage_power_supplied = pd.DataFrame([0]*simulation_hours)
                energy_surplus = ((storage_profile > 0) * storage_profile).abs()
                energy_deficit = ((storage_profile < 0) * storage_profile).abs()
                battery_health = pd.DataFrame([0]*simulation_hours)
                break
            battery_energy_flow = storage_profile.iloc[t][0]
            dispatched_diesel_energy_used = 0 # Total diesel energy used
            dispatched_diesel_energy_supplied = 0 # Total diesel energy supplied

            if t == 0:
                new_hourly_storage = initial_storage + battery_energy_flow
                empty_capacity = max_storage - new_hourly_storage
                empty_capacity_list.append(empty_capacity)
                dd_on.append(0)
                energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))  # Battery too full
            else:
                state_of_charge = (hourly_storage[t - 1] - min_storage) / (max_storage - min_storage)
                state_of_charge_list.append(state_of_charge)
                new_hourly_storage = hourly_storage[t-1]
#   If no dispatched diesel, run discharging and charging as normal
                if dispatched_diesel_status == 'N':
                    empty_capacity_list.append(0)
                    if battery_energy_flow >= 0.0:  # Battery charging
                        new_hourly_storage = hourly_storage[t - 1] * (1.0 - battery_leakage) + battery_eff_in * min(
                            battery_energy_flow, battery_C_rate_in * (max_storage - min_storage))
                    else:  # Battery discharging
                        new_hourly_storage = hourly_storage[t - 1] * (1.0 - battery_leakage) + (
                                    1.0 / battery_eff_out) * max(battery_energy_flow, (-1.0) * battery_C_rate_out * (
                                    max_storage - min_storage))
#   Dumped energy
                    energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))  # Battery too full
#   Battery capacities and blackouts (if battery is too full or empty)
                    if new_hourly_storage >= max_storage:
                        new_hourly_storage = max_storage
                    elif new_hourly_storage <= min_storage:
                        new_hourly_storage = min_storage

#   If dispatched diesel is in operation, run set of functions
                elif dispatched_diesel_status == 'Y':
                    empty_capacity = max_storage  - new_hourly_storage
                    empty_capacity_list.append(empty_capacity)
                    # if timed is on, then run at specific time
                    timed_on_off = int(dispatched_diesel_profile['Timed dispatchable diesel profile'][t])
                    if timed_on_off == 0:
                        # if the generator wasn't running in the previous hour:
                        if dd_on[t] == 0:
                            # if the state of charge is higher than the minimum universal switch on, then pass
                            if state_of_charge >= diesel_dispatched_universal_minimum_SOC:
                                dd_on.append(0)
                                if battery_energy_flow >= 0.0:  # Battery charging
                                    new_hourly_storage = hourly_storage[t - 1] * (
                                                1.0 - battery_leakage) + battery_eff_in * min(
                                        battery_energy_flow, battery_C_rate_in * (max_storage - min_storage))
                                else:  # Battery discharging
                                    new_hourly_storage = hourly_storage[t - 1] * (1.0 - battery_leakage) + (
                                            1.0 / battery_eff_out) * max(battery_energy_flow,
                                                                         (-1.0) * battery_C_rate_out * (
                                                                                 max_storage - min_storage))
                                #   Dumped energy
                                energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))  # Battery too full
                                #   Battery capacities and blackouts (if battery is too full or empty)
                                if new_hourly_storage >= max_storage:
                                    new_hourly_storage = max_storage
                                elif new_hourly_storage <= min_storage:
                                    new_hourly_storage = min_storage
                            else:
                                dd_on.append(1)
                                if empty_capacity <= min_diesel_capacity:
                                    new_hourly_storage += empty_capacity  # Hourly storage plus the empty capacity remaining
                                    dispatched_diesel_energy_used += empty_capacity  # Diesel used = empty capacity
                                    dispatched_diesel_energy_supplied += min_diesel_capacity  # Diesel supplied is min diesel capacity
                                    # Empty capacity filled by diesel, any remaining solar dumped
                                    if battery_energy_flow > 0:
                                        energy_surplus.append(battery_energy_flow)
                                    else:
                                        energy_surplus.append(0)
                                if empty_capacity >= max_diesel_energy_in:
                                    new_hourly_storage += max_diesel_energy_in  # Hourly storage plus the max diesel in
                                    dispatched_diesel_energy_used += max_diesel_energy_in  # Diesel used = the max diesel input
                                    dispatched_diesel_energy_supplied += max_diesel_energy_in  # Diesel supplied = supplied at max output
                                    # Spare capacity in the battery for solar so if there is remaining solar
                                    if battery_energy_flow > 0:
                                        if max_storage_energy_in < diesel_capacity_dd:
                                            energy_surplus.append(battery_energy_flow)
                                        else:
                                            if battery_energy_flow < max_solar_in:
                                                new_hourly_storage += battery_energy_flow
                                                energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                            if new_hourly_storage >= max_storage:
                                                new_hourly_storage = max_storage
                                            else:
                                                new_hourly_storage += max_solar_in
                                                if new_hourly_storage >= max_storage:
                                                    energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                                    new_hourly_storage = max_storage
                                                else:
                                                    energy_surplus.append(battery_energy_flow - max_solar_in)
                                    else:
                                        energy_surplus.append(0)

                                if min_diesel_capacity < empty_capacity < max_diesel_energy_in:
                                    new_hourly_storage += empty_capacity  # adds in the empty capacity to the hourly storage
                                    dispatched_diesel_energy_used += empty_capacity  # adds empty capacity to used
                                    dispatched_diesel_energy_supplied += empty_capacity
                                    if battery_energy_flow > 0:
                                            max_solar_in = max_storage_energy_in - empty_capacity
                                            if battery_energy_flow < max_solar_in:
                                                new_hourly_storage += battery_energy_flow
                                                energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                                if new_hourly_storage >= max_storage:
                                                    new_hourly_storage = max_storage
                                            else:
                                                new_hourly_storage += max_solar_in
                                                if new_hourly_storage >= max_storage:
                                                    energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                                    new_hourly_storage = max_storage
                                                else:
                                                    energy_surplus.append(battery_energy_flow - max_solar_in)
                                    else:
                                        energy_surplus.append(0)

                        elif dd_on[t] == 1: # If the generator was running in the previous hour:
                            # if the state of charge is higher than the minimum universal switch off, then pass
                            if state_of_charge >= diesel_dispatched_universal_switch_off_SOC:
                                dd_on.append(0)
                                if battery_energy_flow >= 0.0:  # Battery charging
                                    new_hourly_storage = hourly_storage[t - 1] * (
                                                1.0 - battery_leakage) + battery_eff_in * min(
                                        battery_energy_flow, battery_C_rate_in * (max_storage - min_storage))
                                else:  # Battery discharging
                                    new_hourly_storage = hourly_storage[t - 1] * (1.0 - battery_leakage) + (
                                            1.0 / battery_eff_out) * max(battery_energy_flow,
                                                                         (-1.0) * battery_C_rate_out * (
                                                                                 max_storage - min_storage))
                                #   Dumped energy
                                energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))  # Battery too full
                                #   Battery capacities and blackouts (if battery is too full or empty)
                                if new_hourly_storage >= max_storage:
                                    new_hourly_storage = max_storage
                                elif new_hourly_storage <= min_storage:
                                    new_hourly_storage = min_storage
                            else:
                                dd_on.append(1)
                                if empty_capacity <= min_diesel_capacity:
                                    new_hourly_storage += empty_capacity  # Hourly storage plus the empty capacity remaining
                                    dispatched_diesel_energy_used += empty_capacity  # Diesel used = empty capacity
                                    dispatched_diesel_energy_supplied += min_diesel_capacity  # Diesel supplied is min diesel capacity
                                    # Empty capacity filled by diesel, any remaining solar dumped
                                    if battery_energy_flow > 0:
                                        energy_surplus.append(battery_energy_flow)
                                    else:
                                        energy_surplus.append(0)
                                if empty_capacity >= max_diesel_energy_in:
                                    new_hourly_storage += max_diesel_energy_in  # Hourly storage plus the max diesel in
                                    dispatched_diesel_energy_used += max_diesel_energy_in  # Diesel used = the max diesel input
                                    dispatched_diesel_energy_supplied += max_diesel_energy_in  # Diesel supplied = supplied at max output
                                    # Spare capacity in the battery for solar so if there is remaining solar
                                    if battery_energy_flow > 0:
                                        if max_storage_energy_in < diesel_capacity_dd:
                                            energy_surplus.append(battery_energy_flow)
                                        else:
                                            if battery_energy_flow < max_solar_in:
                                                new_hourly_storage += battery_energy_flow
                                                energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                            if new_hourly_storage >= max_storage:
                                                new_hourly_storage = max_storage
                                            else:
                                                new_hourly_storage += max_solar_in
                                                if new_hourly_storage >= max_storage:
                                                    energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                                    new_hourly_storage = max_storage
                                                else:
                                                    energy_surplus.append(battery_energy_flow - max_solar_in)
                                    else:
                                        energy_surplus.append(0)

                                if min_diesel_capacity < empty_capacity < max_diesel_energy_in:
                                    new_hourly_storage += empty_capacity  # adds in the empty capacity to the hourly storage
                                    dispatched_diesel_energy_used += empty_capacity  # adds empty capacity to used
                                    dispatched_diesel_energy_supplied += empty_capacity
                                    if battery_energy_flow > 0:
                                        max_solar_in = max_storage_energy_in - empty_capacity
                                        if battery_energy_flow < max_solar_in:
                                            new_hourly_storage += battery_energy_flow
                                            energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                            if new_hourly_storage >= max_storage:
                                                new_hourly_storage = max_storage
                                        else:
                                            new_hourly_storage += max_solar_in
                                            if new_hourly_storage >= max_storage:
                                                energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                                new_hourly_storage = max_storage
                                            else:
                                                energy_surplus.append(battery_energy_flow - max_solar_in)
                                    else:
                                        energy_surplus.append(0)
                        # if timed generation activated:
                    elif timed_on_off == 1:
                        # If generator not running in previous hour
                        if dd_on[t] == 0:
                            # Check state of charge of the battery first
                            if state_of_charge >= diesel_dispatched_timed_minimum_SOC:
                                dd_on.append(0)
                                if battery_energy_flow >= 0.0:  # Battery charging
                                    new_hourly_storage = hourly_storage[t - 1] * (
                                                1.0 - battery_leakage) + battery_eff_in * min(
                                        battery_energy_flow, battery_C_rate_in * (max_storage - min_storage))
                                else:  # Battery discharging
                                    new_hourly_storage = hourly_storage[t - 1] * (1.0 - battery_leakage) + (
                                            1.0 / battery_eff_out) * max(battery_energy_flow,
                                                                         (-1.0) * battery_C_rate_out * (
                                                                                 max_storage - min_storage))
                                #   Dumped energy
                                energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))  # Battery too full
                                #   Battery capacities and blackouts (if battery is too full or empty)
                                if new_hourly_storage >= max_storage:
                                    new_hourly_storage = max_storage
                                elif new_hourly_storage <= min_storage:
                                    new_hourly_storage = min_storage
                            else:
                                dd_on.append(1)
                                if empty_capacity <= min_diesel_capacity:
                                    new_hourly_storage += empty_capacity  # Hourly storage plus the empty capacity remaining
                                    dispatched_diesel_energy_used += empty_capacity  # Diesel used = empty capacity
                                    dispatched_diesel_energy_supplied += min_diesel_capacity  # Diesel supplied is min diesel capacity
                                    # Empty capacity filled by diesel, any remaining solar dumped
                                    if battery_energy_flow > 0:
                                        energy_surplus.append(battery_energy_flow)
                                    else:
                                        energy_surplus.append(0)
                                if empty_capacity >= max_diesel_energy_in:
                                    new_hourly_storage += max_diesel_energy_in  # Hourly storage plus the max diesel in
                                    dispatched_diesel_energy_used += max_diesel_energy_in  # Diesel used = the max diesel input
                                    dispatched_diesel_energy_supplied += max_diesel_energy_in  # Diesel supplied = supplied at max output
                                    # Spare capacity in the battery for solar so if there is remaining solar
                                    if battery_energy_flow > 0:
                                        if max_storage_energy_in < diesel_capacity_dd:
                                            energy_surplus.append(battery_energy_flow)
                                        else:
                                            if battery_energy_flow < max_solar_in:
                                                new_hourly_storage += battery_energy_flow
                                                energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                            if new_hourly_storage >= max_storage:
                                                new_hourly_storage = max_storage
                                            else:
                                                new_hourly_storage += max_solar_in
                                                if new_hourly_storage >= max_storage:
                                                    energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                                    new_hourly_storage = max_storage
                                                else:
                                                    energy_surplus.append(battery_energy_flow - max_solar_in)
                                    else:
                                        energy_surplus.append(0)

                                if min_diesel_capacity < empty_capacity < max_diesel_energy_in:
                                    new_hourly_storage += empty_capacity  # adds in the empty capacity to the hourly storage
                                    dispatched_diesel_energy_used += empty_capacity  # adds empty capacity to used
                                    dispatched_diesel_energy_supplied += empty_capacity
                                    if battery_energy_flow > 0:
                                        max_solar_in = max_storage_energy_in - empty_capacity
                                        if battery_energy_flow < max_solar_in:
                                            new_hourly_storage += battery_energy_flow
                                            energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                            if new_hourly_storage >= max_storage:
                                                new_hourly_storage = max_storage
                                        else:
                                            new_hourly_storage += max_solar_in
                                            if new_hourly_storage >= max_storage:
                                                energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                                new_hourly_storage = max_storage
                                            else:
                                                energy_surplus.append(battery_energy_flow - max_solar_in)
                                    else:
                                        energy_surplus.append(0)
                        # If generator running in previous hour:
                        elif dd_on[t] == 1:
                            if state_of_charge >= diesel_dispatched_timed_switch_off_SOC:
                                dd_on.append(0)
                                if battery_energy_flow >= 0.0:  # Battery charging
                                    new_hourly_storage = hourly_storage[t - 1] * (
                                                1.0 - battery_leakage) + battery_eff_in * min(
                                        battery_energy_flow, battery_C_rate_in * (max_storage - min_storage))
                                else:  # Battery discharging
                                    new_hourly_storage = hourly_storage[t - 1] * (1.0 - battery_leakage) + (
                                            1.0 / battery_eff_out) * max(battery_energy_flow,
                                                                         (-1.0) * battery_C_rate_out * (
                                                                                 max_storage - min_storage))
                                #   Dumped energy
                                energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))  # Battery too full
                                #   Battery capacities and blackouts (if battery is too full or empty)
                                if new_hourly_storage >= max_storage:
                                    new_hourly_storage = max_storage
                                elif new_hourly_storage <= min_storage:
                                    new_hourly_storage = min_storage
                            else:
                                dd_on.append(1)
                                if empty_capacity <= min_diesel_capacity:
                                    new_hourly_storage += empty_capacity  # Hourly storage plus the empty capacity remaining
                                    dispatched_diesel_energy_used += empty_capacity  # Diesel used = empty capacity
                                    dispatched_diesel_energy_supplied += min_diesel_capacity  # Diesel supplied is min diesel capacity
                                    # Empty capacity filled by diesel, any remaining solar dumped
                                    if battery_energy_flow > 0:
                                        energy_surplus.append(battery_energy_flow)
                                    else:
                                        energy_surplus.append(0)
                                if empty_capacity >= max_diesel_energy_in:
                                    new_hourly_storage += max_diesel_energy_in  # Hourly storage plus the max diesel in
                                    dispatched_diesel_energy_used += max_diesel_energy_in  # Diesel used = the max diesel input
                                    dispatched_diesel_energy_supplied += max_diesel_energy_in  # Diesel supplied = supplied at max output
                                    # Spare capacity in the battery for solar so if there is remaining solar
                                    if battery_energy_flow > 0:
                                        if max_storage_energy_in < diesel_capacity_dd:
                                            energy_surplus.append(battery_energy_flow)
                                        else:
                                            if battery_energy_flow < max_solar_in:
                                                new_hourly_storage += battery_energy_flow
                                                energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                            if new_hourly_storage >= max_storage:
                                                new_hourly_storage = max_storage
                                            else:
                                                new_hourly_storage += max_solar_in
                                                if new_hourly_storage >= max_storage:
                                                    energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                                    new_hourly_storage = max_storage
                                                else:
                                                    energy_surplus.append(battery_energy_flow - max_solar_in)
                                    else:
                                        energy_surplus.append(0)

                                if min_diesel_capacity < empty_capacity < max_diesel_energy_in:
                                    new_hourly_storage += empty_capacity  # adds in the empty capacity to the hourly storage
                                    dispatched_diesel_energy_used += empty_capacity  # adds empty capacity to used
                                    dispatched_diesel_energy_supplied += empty_capacity
                                    if battery_energy_flow > 0:
                                            max_solar_in = max_storage_energy_in - empty_capacity
                                            if battery_energy_flow < max_solar_in:
                                                new_hourly_storage += battery_energy_flow
                                                energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                                if new_hourly_storage >= max_storage:
                                                    new_hourly_storage = max_storage
                                            else:
                                                new_hourly_storage += max_solar_in
                                                if new_hourly_storage >= max_storage:
                                                    energy_surplus.append(max(new_hourly_storage - max_storage, 0.0))
                                                    new_hourly_storage = max_storage
                                                else:
                                                    energy_surplus.append(battery_energy_flow - max_solar_in)
                                    else:
                                        energy_surplus.append(0)

            dispatched_diesel_used.append(dispatched_diesel_energy_used)
            dispatched_diesel_supplied.append(dispatched_diesel_energy_supplied)
            dispatched_diesel_surplus.append(diesel_capacity_dd - dispatched_diesel_energy_used)

#   Update hourly_storage
            hourly_storage.append(new_hourly_storage)

#   Update battery health
            if t == 0:
                storage_power_supplied.append(0.0 - battery_energy_flow)
            else:
                storage_power_supplied.append(max(hourly_storage[t-1] * (1.0 - battery_leakage) - hourly_storage[t], 0.0))
            cumulative_storage_power = cumulative_storage_power + storage_power_supplied[t]
            
            storage_degradation = (1.0 - battery_lifetime_loss * 
                                   (cumulative_storage_power / max_energy_throughput))
            max_storage = (storage_degradation * storage_size * 
                           self.energy_system_inputs[1]['Battery maximum charge'])
            min_storage = (storage_degradation * storage_size * 
                           self.energy_system_inputs[1]['Battery minimum charge'])
            battery_health.append(storage_degradation)
    
#   Consolidate outputs from iteration stage                    0
        storage_power_supplied = pd.DataFrame(storage_power_supplied)

#   Consolidate outputs from dispatched diesel
        dispatched_diesel_surplus = pd.DataFrame(dispatched_diesel_surplus, columns=['Surplus'])
        dispatched_diesel_used = pd.DataFrame(dispatched_diesel_used, columns=['Used'])
        dispatched_diesel_supplied = pd.DataFrame(dispatched_diesel_supplied, columns=['Supplied'])
        state_of_charge = pd.DataFrame(state_of_charge_list, columns=['State of Charge'])

#   Find unmet energy
        unmet_energy = pd.DataFrame((load_energy.values - renewables_energy_used_directly.values - grid_energy.values -
                                     storage_power_supplied.values),columns=['Unmet'])
        if dispatched_diesel_status == 'N':
            dispatched_diesel_stored = pd.DataFrame([0]*simulation_hours)
            dispatched_diesel_used_total = pd.DataFrame([0]*simulation_hours)
            dispatched_diesel_used_demand = pd.DataFrame([0]*simulation_hours)

        elif dispatched_diesel_status == 'Y':
            new_unmet_energy, new_dispatched_diesel_used, new_dispatched_diesel_supplied = \
                Diesel().diesel_surplus_unmet_dispatched(unmet_energy,dispatched_diesel_surplus, dispatched_diesel_used,
                                                         dispatched_diesel_supplied, storage_power_supplied,
                                                         empty_capacity_list, dd_on, state_of_charge_list)

            dispatched_diesel_stored = dispatched_diesel_used
            unmet_energy = new_unmet_energy
            dispatched_diesel_used_total = new_dispatched_diesel_used
            dispatched_diesel_supplied = new_dispatched_diesel_supplied
            dispatched_diesel_used_demand = dispatched_diesel_used_total - dispatched_diesel_stored

        blackout_times = ((unmet_energy > 0) * 1).astype(float)

#   Use backup diesel generator
        if diesel_backup_status == "Y":
            diesel_energy, diesel_times = Diesel().get_diesel_energy_and_times(unmet_energy,blackout_times,diesel_backup_threshold)
            diesel_capacity = math.ceil(np.max(diesel_energy))
            diesel_fuel_usage = pd.DataFrame(Diesel().get_diesel_fuel_usage(
                    diesel_capacity,diesel_energy,diesel_times).values)
            unmet_energy = pd.DataFrame(unmet_energy.values - diesel_energy.values)
            diesel_energy = diesel_energy.abs()
        else:
            if dispatched_diesel_status == 'N':
                diesel_energy = pd.DataFrame([0.0]*int(storage_profile.size))
                diesel_times = pd.DataFrame([0.0]*int(storage_profile.size))
                diesel_fuel_usage = pd.DataFrame([0.0]*int(storage_profile.size))
                diesel_capacity = 0.0
            else:
                diesel_energy = dispatched_diesel_used_total
                diesel_times = pd.DataFrame(dd_on[1:])
                diesel_capacity = diesel_capacity_dd
                diesel_fuel_usage = pd.DataFrame(Diesel().get_diesel_fuel_usage(diesel_capacity,
                                                                                dispatched_diesel_supplied,
                                                                                diesel_times))

#   Find new blackout times, according to when there is unmet energy
        blackout_times = ((unmet_energy > 0) * 1).astype(float)        
#   Ensure all unmet energy is calculated correctly, removing any negative values
        unmet_energy = ((unmet_energy > 0) * unmet_energy).abs()

#   Find how many kerosene lamps are in use
        kerosene_usage = pd.DataFrame(blackout_times.values * kerosene_profile.values)
        kerosene_mitigation = pd.DataFrame((1-blackout_times).values * kerosene_profile.values)

#   System performance outputs
        blackout_times.columns = ['Blackouts']
        hourly_storage = pd.DataFrame(hourly_storage)
        hourly_storage.columns = ['Hourly storage (kWh)']
        energy_surplus = pd.DataFrame(energy_surplus)
        energy_surplus.columns = ['Dumped energy (kWh)']
        unmet_energy.columns = ['Unmet energy (kWh)']
        storage_power_supplied.columns = ['Storage energy supplied (kWh)']
        diesel_energy.columns = ['Diesel energy (kWh)']
        battery_health = pd.DataFrame(battery_health)
        battery_health.columns = ['Battery health']
        diesel_times.columns = ['Diesel times']
        diesel_fuel_usage.columns = ['Diesel fuel usage (l)']
        households.columns = ['Households']
        kerosene_usage.columns = ['Kerosene lamps']
        kerosene_mitigation.columns = ['Kerosene mitigation']
        dispatched_diesel_used_demand.columns = ['Dispatched Diesel Used Meeting Demand (kWh)']
        dispatched_diesel_stored.columns = ['Dispatched Diesel Stored (kWh)']

#   Find total energy used by the system
        total_energy_used = pd.DataFrame(renewables_energy_used_directly.values +
                                         storage_power_supplied.values + 
                                         grid_energy.values +
                                         dispatched_diesel_used_demand.values)
        total_energy_used.columns = ['Total energy used (kWh)']

#   System details
        system_details = pd.DataFrame({'Start year':float(start_year),
                                       'End year':float(end_year),
                                       'Initial PV size':PV_size,
                                       'Initial storage size':storage_size,
                                       'Final PV size':PV_size*Solar().solar_degradation()[0][8760*(end_year-start_year)],
                                       'Final storage size':storage_size*np.min(battery_health['Battery health']),
                                       'Diesel capacity':diesel_capacity
                                       },index=['System details'])
        
#   End simulation timer
        timer_end = datetime.datetime.now()
        time_delta = timer_end - timer_start
        print("\nTime taken for simulation: " + "{0:.2f}".format(
                (time_delta.microseconds*0.000001)/float(end_year-start_year)) + " seconds per year")
        
#   Return all outputs        
        system_performance_outputs = pd.concat([load_energy,
                                                total_energy_used,
                                                unmet_energy,
                                                blackout_times,
                                                renewables_energy_used_directly,
                                                storage_power_supplied,
                                                state_of_charge,
                                                grid_energy,
                                                diesel_energy,
                                                dispatched_diesel_stored,
                                                dispatched_diesel_used_demand,
                                                dispatched_diesel_supplied,
                                                diesel_times,
                                                diesel_fuel_usage,
                                                storage_profile,
                                                renewables_energy,
                                                hourly_storage,
                                                energy_surplus,
                                                battery_health,
                                                households,
                                                kerosene_usage,
                                                kerosene_mitigation,
                                                ],axis=1)
        
        return tuple([system_performance_outputs,system_details])
#%%
# =============================================================================
# GENERAL FUNCTIONS
#       These functions allow users to save simulations and open previous ones,
#       and resimulate the entire lifetime of a previously-optimised system
#       including consideration of increasing capacity. 
# =============================================================================
    def save_simulation(self,simulation_name,filename=None):
        """
        Function:
            Saves simulation outputs to a .csv file
        Inputs:
            simulation_name     DataFrame output from Energy_System().simulation(...)
            filename            Name of .csv file to be saved as (defaults to timestamp)
        Outputs:
            Simulation saved to .csv file
        """
        if filename != None:
            simulation_name.to_csv(self.simulation_storage + str(filename) + '.csv')
        else:
            filename = str(datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S"))
            simulation_name.to_csv(self.simulation_storage + filename + '.csv')
        print('\nSimulation saved as '+ filename + '.csv')
            
    def open_simulation(self,filename):
        """
        Function:
            Opens a previously saved simulation from a .csv file
        Inputs:
            filename            Name of the .csv file to be opened (not including .csv)
        Outputs:
            DataFrame of previously performed simulation
        """
        output = pd.read_csv(self.simulation_storage + str(filename) + '.csv',index_col=0)
        return output        

    def lifetime_simulation(self,optimisation_report):
        '''
        Function:
            Simulates a minigrid system over the course of its lifetime to get the complete technical
                performance of the system
        Inputs:
            optimisation_report     Report of outputs from Optimisation().multiple_optimisation_step()
        Outputs:
            lifetime_output         The lifetime technical performance of the system
        '''
#   Initialise
        optimisation_report = optimisation_report.reset_index(drop=True)
        lifetime_output = pd.DataFrame([])
        simulation_periods = np.size(optimisation_report,0)
#   Iterate over all simulation periods
        for sim in range(simulation_periods):
            system_performance_outputs = self.simulation(start_year = int(optimisation_report['Start year'][sim]),
                                                         end_year = int(optimisation_report['End year'][sim]), 
                                                         PV_size = float(optimisation_report['Initial PV size'][sim]),
                                                         storage_size = float(optimisation_report['Initial storage size'][sim]))
            lifetime_output = pd.concat([lifetime_output,system_performance_outputs[0]],axis=0)
        return lifetime_output.reset_index(drop=True)
#%%
# =============================================================================
# ENERGY BALANCE FUNCTIONS
#       These functions identify the sources and uses of energy in the system, 
#       such as generation, loads and the overall balance
# =============================================================================
#%% Energy balance
    def get_storage_profile(self, start_year = 0, end_year = 4, PV_size = 10, **options):
        '''
        Function:
            Gets the storage profile (energy into/out of battery) for the system and other
                    system energies
        Inputs:
            start_year          Start year of this simulation period
            end_year            End year of this simulation period
            PV_size             Amount of PV in kWp
            
        Outputs:
            load_energy                     Amount of energy (kWh) required to satisfy the loads
            renewables_energy               Amount of energy (kWh) provided by renewables to the system
            renewables_energy_used_directly Amount of energy (kWh) from renewables used directly to satisfy load (kWh)
            grid_energy                     Amount of energy (kWh) supplied by the grid
            storage_profile                 Amount of energy (kWh) into (+ve) and out of (-ve) the battery
            kerosene_usage                  Number of kerosene lamps in use (if no power available)
        '''

#   Initialise simulation parameters
        start_hour = start_year*8760
        end_hour = end_year*8760
        
#   Initialise power generation, including degradation of PV
        PV_generation = PV_size * pd.DataFrame(self.get_PV_generation()[start_hour:end_hour].values
                                               * Solar().solar_degradation()[0:(end_hour-start_hour)].values)
        grid_status = pd.DataFrame(self.get_grid_profile()[start_hour:end_hour].values)
        load_profile = pd.DataFrame(self.get_load_profile()[start_hour:end_hour].values)
        timed_dispatchable_diesel_profile = pd.DataFrame(Diesel().get_dispatchable_diesel_times()[start_hour:end_hour].values)
        #timed_dispatchable_diesel_profile.to_csv('~/desktop/diesel_out.csv')

#   Consider power distribution network
        if self.scenario_inputs[1]['Distribution network'] == 'DC':
            PV_generation = self.energy_system_inputs[1]['DC to DC conversion']*PV_generation
            transmission_eff = self.energy_system_inputs[1]['Transmission efficiency DC']
#            grid_conversion_eff = self.energy_system_inputs[1]['AC to DC conversion']
            
        if self.scenario_inputs[1]['Distribution network'] == 'AC':
            PV_generation = self.energy_system_inputs[1]['DC to AC conversion']*PV_generation
            transmission_eff = self.energy_system_inputs[1]['Transmission efficiency AC']
#            grid_conversion_eff = self.energy_system_inputs[1]['AC to AC conversion']
        
#   Consider transmission efficiency
        load_energy = load_profile / transmission_eff
        PV_energy = PV_generation * transmission_eff
        
#   Combine energy from all renewables sources 
        renewables_energy = PV_energy # + wind_energy + ...
#   Add more renewable sources here as required 
        
#   Check for self-generation prioritisation 
        if self.scenario_inputs[1]['Prioritise self generation'] == 'Y':
#   Take energy from PV first 
            remaining_profile = pd.DataFrame(renewables_energy.values - load_energy.values)
            renewables_energy_used_directly = pd.DataFrame(
                    (remaining_profile > 0) * load_energy.values + 
                    (remaining_profile < 0) * renewables_energy.values)
#   Then take energy from grid
            grid_energy = pd.DataFrame(((remaining_profile < 0) * remaining_profile).values
                                       * -1.0 * grid_status.values)
            storage_profile = pd.DataFrame(remaining_profile.values + grid_energy.values)
            
        if self.scenario_inputs[1]['Prioritise self generation'] == 'N':
#   Take energy from grid first 
            grid_energy = pd.DataFrame(load_energy.values) * pd.DataFrame(grid_status.values) # as needed for load
            remaining_profile = (grid_energy <= 0) * load_energy
#   Then take energy from PV 
            storage_profile = pd.DataFrame(renewables_energy.values - remaining_profile.values)
            renewables_energy_used_directly = pd.DataFrame(
                    (storage_profile > 0) * remaining_profile.values + 
                    (storage_profile < 0) * renewables_energy.values)
#   Get kerosene usage
        kerosene_usage = pd.DataFrame(self.kerosene_usage[start_hour:end_hour].values)
        
        load_energy.columns = ['Load energy (kWh)']
        renewables_energy.columns = ['Renewables energy supplied (kWh)']
        renewables_energy_used_directly.columns = ['Renewables energy used (kWh)']
        grid_energy.columns = ['Grid energy (kWh)']
        storage_profile.columns = ['Storage profile (kWh)']
        kerosene_usage.columns = ['Kerosene lamps']
        timed_dispatchable_diesel_profile.columns = ['Timed dispatchable diesel profile']

        #out_file = pd.concat([load_energy, renewables_energy, renewables_energy_used_directly,
        #                      grid_energy, storage_profile, kerosene_usage], axis=1)
        #out_file.to_csv('/Users/hrb16/Library/Mobile Documents/com~apple~CloudDocs/Mahama Project/Dispatchable Diesel/get_stor_outs.csv')

        return pd.concat([load_energy, renewables_energy, renewables_energy_used_directly,
                          grid_energy, storage_profile, kerosene_usage, timed_dispatchable_diesel_profile], axis=1)

#%% Energy sources
    def get_PV_generation(self, **options):
        '''
        Function:
            Gets the output of 1 kWp of PV over 20 years in kW
        Inputs:
            'PV generation inputs.csv' from PV folder in generation folder
        Outputs:
            PV output in kW per kWp installed
        '''
        return pd.read_csv(self.generation_filepath + '/PV/solar_generation_20_years.csv',header=None,index_col=0)
        
    def get_grid_profile(self,**options):
        '''
        Function:
            Gets the availability of the grid over 20 years
        Inputs:
            'xxxxxx_grid_status.csv' from Grid folder in generation folder
            'Scenario inputs.xlsx' from Scenario folder to select grid type
        Outputs:
            Availabilty of grid (1 = available, 0 = not available)
        '''
        grid_type = self.scenario_inputs[1]['Grid type']
        return pd.read_csv(self.generation_filepath + '/Grid/' + grid_type + '_grid_status.csv',index_col=0)      
#%% Energy usage
    def get_load_profile(self, **options):
        '''
        Function:
            Gets the total community load over 20 years in kW
        Inputs:
            'total_load.csv' from 'Device load' folder in Load folder
        Outputs:
            Gives a dataframe with columns for the load of domestic, commercial and public devices
        '''
        loads = pd.read_csv(self.location_filepath + '/Load/Device load/total_load.csv',index_col=0)*0.001
        total_load = pd.DataFrame(np.zeros(len(loads)))
        if self.scenario_inputs[1]['Domestic'] == 'Y':
            total_load = pd.DataFrame(total_load.values + pd.DataFrame(loads['Domestic']).values)
        if self.scenario_inputs[1]['Commercial'] == 'Y':
            total_load = pd.DataFrame(total_load.values + pd.DataFrame(loads['Commercial']).values)
        if self.scenario_inputs[1]['Public'] == 'Y':
            total_load = pd.DataFrame(total_load.values + pd.DataFrame(loads['Public']).values)
        return total_load
