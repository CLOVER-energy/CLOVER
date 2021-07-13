# -*- coding: utf-8 -*-
"""
===============================================================================
                      	      OPTIMISATION FILE
===============================================================================
                            Most recent update:
                                3 May 2019
===============================================================================
Made by:
    Philip Sandwell
Copyright:
    Philip Sandwell, 2018
For more information, please email:
    philip.sandwell@googlemail.com
===============================================================================
"""

import datetime
import os

import numpy as np
import pandas as pd

from ..impact.finance import Finance
from ..impact.ghgs import GHGs
from ..simulation.energy_system import Energy_System
from ...__utils__ import hourly_profile_to_daily_sum, LOCATIONS_FOLDER_NAME

#%%
class Optimisation():
    def __init__(self):
        self.location = "Bahraich"
        self.CLOVER_filepath = os.getcwd()
        self.location_filepath = os.path.join(self.CLOVER_filepath, LOCATIONS_FOLDER_NAME, self.location)
        self.optimisation_filepath = os.path.join(self.location_filepath, 'Optimisation', 'Optimisation inputs.csv')
        self.optimisation_inputs  = pd.read_csv(self.optimisation_filepath,header=None,index_col=0).round(decimals=3)
        self.maximum_criteria = ['Blackouts','LCUE ($/kWh)','Emissions intensity (gCO2/kWh)','Unmet energy fraction',
                                 'Cumulative cost ($)','Cumulative system cost ($)',
                                 'Total cost ($)','Total system cost ($)',
                                 'Cumulative GHGs (kgCO2eq)','Cumulative system GHGs (kgCO2eq)',
                                 'Total GHGs (kgCO2eq)','Total system GHGs (kgCO2eq)']
        self.minimum_criteria = ['Renewables fraction','Kerosene displacement',
                                 'Kerosene cost mitigated ($)','Kerosene GHGs mitigated (kgCO2eq)']
        self.optimum_criterion = str(self.optimisation_inputs[1]['Optimisation criterion'])
        self.optimisation_storage = os.path.join(self.location_filepath, 'Optimisation' ,'Saved optimisations')
#%%
# =============================================================================
# OPTIMISATION FUNCTIONS
#       These functions control the optimisation process. Use multiple_optimisation_step()
#       to find optimise a system over its lifetime, or changing_parameter_optimisation() to
#       perform many optimisations with different parameters. 
#           * simulation_iteration(...)
#               Scans the defined range of systems and returns sufficient systems
#           * optimisation_step(...)
#               Takes the sufficient systems and returns the optimum system
#           * single_line_simulation(...)
#               An additional row of simulations if the optimum is an edge case
#           * find_optimum_system(...)
#               Locates the optimum system including edge case considerations
#           * multiple_optimisation_step(...)
#               Sequential optimisaiton steps over the entire optimisation period
#           * changing_parameter_optimisation(...) 
#               Allows a parameter to be changed to perform many optimisations
# =============================================================================

    def multiple_optimisation_step(self,PV_sizes=[],storage_sizes=[],previous_systems = pd.DataFrame([]),
                                   start_year = 0):
        '''
        Function:
            Multiple optimisation steps of the continuous lifetime optimisation
        Inputs:
            PV_sizes            Range of PV sizes in the form [minimum, maximum, step size]
            storage_sizes       Range of storage sizes in the form [minimum, maximum, step size]
            previous_system     Appraisal of the system already in place before this simulation period
            start_year          Start year of the initial optimisation step
        Outputs:
            results             Results of each Optimisation().optimisation_step(...) 
        '''   
#   Start timer to see how long simulation will take
        timer_start = datetime.datetime.now()
#   Initialise        
        scenario_length = int(self.optimisation_inputs[1]['Scenario length'])
        iteration_length = int(self.optimisation_inputs[1]['Iteration length'])
        steps = int(scenario_length/iteration_length)
        results = pd.DataFrame([])
        PV_size_step = float(self.optimisation_inputs[1]['PV size (step)'])
        storage_size_step = float(self.optimisation_inputs[1]['Storage size (step)'])
        PV_increase = float(self.optimisation_inputs[1]['PV size (increase)'])
        storage_increase = float(self.optimisation_inputs[1]['Storage size (increase)'])
#   Iterate over each optimisation step
        for step in range(steps):
            print('\nStep '+str(step+1)+' of '+str(steps))
            step_results = self.optimisation_step(PV_sizes,storage_sizes,previous_systems,
                          start_year)
            results = pd.concat([results,step_results],axis=0)
#   Prepare inputs for next optimisation step
            start_year += iteration_length
            previous_systems = step_results
            PV_size_min = float(step_results['Final PV size'])
            storage_size_min = float(step_results['Final storage size'])
            PV_size_max = float(step_results['Final PV size'] + PV_increase)
            storage_size_max = float(step_results['Final storage size'] + storage_increase)
            PV_sizes = [PV_size_min,PV_size_max,PV_size_step]
            storage_sizes = [storage_size_min,storage_size_max,storage_size_step]    
#   End simulation timer
        timer_end = datetime.datetime.now()
        time_delta = timer_end - timer_start
        minutes, seconds = divmod(time_delta.seconds,60)
        print("\nTime taken for optimisation: {}:{} minutes".format(minutes,seconds))
        return results

    def changing_parameter_optimisation(self,parameter,parameter_values = [],results_folder_name = []):
        """
        Function:
            Allows the user to change a parameter in the "Optimisation inputs.csv" file automatically
                and run many optimisation runs, saving each one. 
        Inputs:
            parameter               Parameter to be changed
            parameter_values        Values for the threshold criterion in the form [min, max, step]
            results_folder_name     Folder where the results will be saved
        Outputs:
            Saved outputs of the optimisations for each parameter value, and a separate saved 
            summary of all outputs for comparison. 
        """  
#   Initialise
        parameter = str(parameter)
        summarised_results = pd.DataFrame()
        if results_folder_name != None:
            results_folder = str(results_folder_name)
        else:
            results_folder = self.optimisation_storage + str(datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S"))
#   Iterate over the range of threshold steps
        value_counter = 1
        for parameter_value in parameter_values:
            print('\nParameter value '+str(value_counter)+' of '+str(len(parameter_values)))
            value_counter += 1
#   Set the threshold value for this step
            self.change_parameter(parameter,parameter_value)
#   Perform optimisation
            optimisation_results = self.multiple_optimisation_step()
#   Save optimisation
            optimisation_filename = os.path.join(results_folder, parameter + ' = {:.2f}'.format(parameter_value))
            self.save_optimisation(optimisation_name = optimisation_results, filename = optimisation_filename)
            new_results = self.summarise_optimisation_results(optimisation_results)
            summarised_results = pd.concat([summarised_results,new_results],axis=0)
#   Format and save output summary
        parameter_values = pd.DataFrame({'Parameter value':parameter_values})
        summary_output = pd.concat([parameter_values.reset_index(drop=True),summarised_results.reset_index(drop=True)],axis=1)
        summary_filename = os.path.join(results_folder, parameter + ' lifetime summary of results')
        self.save_optimisation(summary_output,filename = summary_filename)
        
    def optimisation_step(self,PV_sizes=[],storage_sizes=[],previous_systems = pd.DataFrame([]),
                          start_year = 0):
        '''
        Function:
            One optimisation step of the continuous lifetime optimisation
        Inputs:
            PV_sizes            Range of PV sizes in the form [minimum, maximum, step size]
            storage_sizes       Range of storage sizes in the form [minimum, maximum, step size]
            previous_system     Appraisal of the system already in place before this simulation period
            start_year          Start year of the optimisation step
        Outputs:
            optimum_system      The optimum system for the group of simulated systems
        '''
        iteration_results = self.simulation_iteration(PV_sizes,storage_sizes,previous_systems,start_year)
        optimum_system = self.find_optimum_system(iteration_results)
        return optimum_system
        
    def find_optimum_system(self,iteration_results):
        '''
        Function:
            Finds the optimum system from a group of sufficient systems with the ability to
                increase the system size if necessary, if the simulation is an edge case
        Inputs:
            iteration_results   Output of Optimisation().simulation_iteration(...)
        Outputs:
            optimum_system      Optimum system for the simulation period
        '''
#   Initialise
        sufficient_systems = iteration_results[0]
        largest_system = iteration_results[1]
        previous_systems = iteration_results[2]
#   Check to find optimum system
        optimum_system = self.identify_optimum_system(sufficient_systems)
#   Check if optimum system was the largest system simulated
        while (float(optimum_system['Initial PV size']) == float(largest_system['PV size (max)'])) or (
                float(optimum_system['Initial storage size']) == float(largest_system['Storage size (max)'])):
#   Do single line optimisation to see if larger system is superior
            new_iteration_results = self.single_line_simulation(
                    optimum_system,largest_system,previous_systems)
            new_sufficient_systems = new_iteration_results[0]
            largest_system = new_iteration_results[1]
            potential_optimum_system = self.identify_optimum_system(new_sufficient_systems)
#   Compare previous optimum system and new potential 
            system_comparison = pd.concat([optimum_system,potential_optimum_system])
            optimum_system = self.identify_optimum_system(system_comparison)
#   Return the confirmed optimum system
        return optimum_system

    def identify_optimum_system(self,sufficient_systems):
        '''
        Function:
            Identifies the optimum system from a group of sufficient systems
        Inputs:
            sufficient_systems      DataFrame of sufficient systems and their appraisals
        Outputs:
            optimum_system          DataFrame of the optimum system
        '''
        sufficient_systems = sufficient_systems.reset_index(drop=True)
        if self.optimum_criterion in self.minimum_criteria:
            optimum_index = sufficient_systems[self.optimum_criterion].idxmax(axis=0)
        if self.optimum_criterion in self.maximum_criteria:
            optimum_index = sufficient_systems[self.optimum_criterion].idxmin(axis=0)
        optimum_system = pd.DataFrame(sufficient_systems.iloc[optimum_index]).T.reset_index(drop=True)
        return optimum_system

    def single_line_simulation(self,potential_system,largest_system,previous_systems):
        '''
        Function:
            Performs an additional round of simulations, if the potential optimum system was found to be
                an edge case (either maximum PV capacity, storage capacity or both)
        Inputs:
            potential_system    The system assumed to be the optimum, before this process
            largest_system      The largest system that was simulated previously
            previous_systems    The system that was previously installed
        Outputs:
            iteration_results   Three components which include:
                                    0. The system appraisals for all of the systems that meet the threshold
                                    1. The largest system that was simulated
                                    2. The previous system that was installed
        '''
#   Initialise
        print('\nUsing single line optimisation')
        system_appraisals = pd.DataFrame([])
        start_year = int(largest_system['Start year'])
        end_year = int(largest_system['End year'])
        PV_size_max = float(largest_system['PV size (max)'])
        PV_size_step = float(largest_system['PV size (step)'])
        PV_size_min = float(largest_system['PV size (min)'])
        storage_size_max = float(largest_system['Storage size (max)'])
        storage_size_step = float(largest_system['Storage size (step)'])
        storage_size_min = float(largest_system['Storage size (min)'])
#   Check to see if storage size was an integer number of steps, and increase accordingly
        if np.ceil(storage_size_max/storage_size_step)*storage_size_step == storage_size_max:
            test_storage_size = float(storage_size_max + storage_size_step)
        else:
            test_storage_size = np.ceil(storage_size_max/storage_size_step)*storage_size_step      
#   If storage was maxed out:
        if float(potential_system['Initial storage size']) == storage_size_max:
            print('\nIncreasing storage size')
#   Increase  and iterate over PV size
            iteration_PV_size = np.ceil(PV_size_max + PV_size_step)
            while iteration_PV_size >= PV_size_min:
                simulation = Energy_System().simulation(start_year = start_year, end_year = end_year, 
                                          PV_size = iteration_PV_size, 
                                          storage_size = test_storage_size)
                new_appraisal = self.system_appraisal(simulation,previous_systems)
                if self.check_threshold(new_appraisal).empty == False:
                    system_appraisals = pd.concat([system_appraisals,new_appraisal],axis=0)
                else:
                    break
                iteration_PV_size -= PV_size_step
                if iteration_PV_size < 0:
                    break
            if np.ceil(PV_size_max/PV_size_step)*PV_size_step != PV_size_max:
                simulation = Energy_System().simulation(start_year = start_year, end_year = end_year, 
                                          PV_size = PV_size_max, 
                                          storage_size = test_storage_size)
                new_appraisal = self.system_appraisal(simulation,previous_systems)
                if self.check_threshold(new_appraisal).empty == False:
                    system_appraisals = pd.concat([system_appraisals,new_appraisal],axis=0)
            largest_system['Storage size (max)'] = test_storage_size
#   Check to see if PV size was an integer number of steps, and increase accordingly
        if np.ceil(PV_size_max/PV_size_step)*PV_size_step == PV_size_max:
            test_PV_size = float(PV_size_max + PV_size_step)
        else:
            test_PV_size = np.ceil(PV_size_max/PV_size_step)*PV_size_step     
#   If PV was maxed out:
        if float(potential_system['Initial PV size']) == PV_size_max:
            print('\nIncreasing PV size')
#   Increase  and iterate over storage size
            iteration_storage_size = np.ceil(storage_size_max + storage_size_step)
            while iteration_storage_size >= storage_size_min:
                simulation = Energy_System().simulation(start_year = start_year, end_year = end_year, 
                                          PV_size = test_PV_size, 
                                          storage_size = iteration_storage_size)
                new_appraisal = self.system_appraisal(simulation,previous_systems)
                if self.check_threshold(new_appraisal).empty == False:
                    system_appraisals = pd.concat([system_appraisals,new_appraisal],axis=0)
                else:
                    break
                iteration_storage_size -= storage_size_step
                if iteration_storage_size < 0:
                    break
            if np.ceil(storage_size_max/storage_size_step)*storage_size_step != storage_size_max:
                simulation = Energy_System().simulation(start_year = start_year, end_year = end_year, 
                                          PV_size = test_PV_size, 
                                          storage_size = storage_size_max)
                new_appraisal = self.system_appraisal(simulation,previous_systems)
                if self.check_threshold(new_appraisal).empty == False:
                    system_appraisals = pd.concat([system_appraisals,new_appraisal],axis=0)
            largest_system['PV size (max)'] = test_PV_size
        iteration_results = tuple([system_appraisals,largest_system,previous_systems])
        return iteration_results
      
    def simulation_iteration(self,PV_sizes=[],storage_sizes=[],previous_systems = pd.DataFrame([]),
                             start_year = 0):
        '''
        Function:
            New simulation iteration i.e. checks sufficiency and stops when criteria is not met, increases
                system size when no sufficient system exists
        Inputs:
            PV_sizes            Range of PV sizes in the form [minimum, maximum, step size]
            storage_sizes       Range of storage sizes in the form [minimum, maximum, step size]
            previous_system     Appraisal of the system already in place before this simulation period
            start_year          Start year of the optimisation step
        Outputs:
            iteration_results   Three components which include:
                                    0. The system appraisals for all of the systems that meet the threshold
                                    1. The largest system that was simulated
                                    2. The previous system that was installed
        '''
#   Initialise
        PV_sizes = pd.DataFrame(PV_sizes)
        storage_sizes = pd.DataFrame(storage_sizes)
        system_appraisals = pd.DataFrame([])
#        simulation_number = 0
        end_year = start_year + int(self.optimisation_inputs[1]['Iteration length'])
#   Check to see if PV sizes have been set
        if PV_sizes.empty == True:
            PV_size_min = float(self.optimisation_inputs[1]['PV size (min)'])
            PV_size_max = float(self.optimisation_inputs[1]['PV size (max)'])
            PV_size_step = float(self.optimisation_inputs[1]['PV size (step)'])
        else:
            PV_size_min = float(PV_sizes[0][0])
            PV_size_max = float(PV_sizes[0][1])
            PV_size_step = float(PV_sizes[0][2])
#   Check to see if storage sizes have been set
        if storage_sizes.empty == True:
            storage_size_min = float(self.optimisation_inputs[1]['Storage size (min)'])
            storage_size_max = float(self.optimisation_inputs[1]['Storage size (max)'])
            storage_size_step = float(self.optimisation_inputs[1]['Storage size (step)'])
        else:
            storage_size_min = float(storage_sizes[0][0])
            storage_size_max = float(storage_sizes[0][1])
            storage_size_step = float(storage_sizes[0][2])            
#   Check if largest system is sufficient
        simulation = Energy_System().simulation(start_year = start_year, end_year = end_year, 
                                          PV_size = PV_size_max, storage_size = storage_size_max)
        new_appraisal = self.system_appraisal(simulation,previous_systems)
#   Increase system size until largest system is sufficient (if necessary)
        while self.check_threshold(new_appraisal).empty == True:
            PV_size_max = np.ceil(PV_size_max/PV_size_step)*PV_size_step
            storage_size_max = np.ceil(storage_size_max/storage_size_step)*storage_size_step
            simulation = Energy_System().simulation(start_year = start_year, end_year = end_year, 
                                          PV_size = PV_size_max, storage_size = storage_size_max)
            new_appraisal = self.system_appraisal(simulation,previous_systems)
            
            PV_size_max += PV_size_step
            storage_size_max += storage_size_step
#   Create an output for the largest system considered               
        largest_system = pd.DataFrame({'PV size (max)':PV_size_max,
                                       'PV size (step)':PV_size_step,
                                       'PV size (min)':PV_size_min,
                                       'Storage size (max)':storage_size_max,
                                       'Storage size (step)':storage_size_step,
                                       'Storage size (min)':storage_size_min,
                                       'Start year':start_year,
                                       'End year':end_year,
                                       },index=['System details'])
#   Return simulated systems to the step size increments (rounding up)
        PV_size_max = np.ceil(PV_size_max/PV_size_step)*PV_size_step
        storage_size_max = np.ceil(storage_size_max/storage_size_step)*storage_size_step
#   Move down system sizes
        while PV_size_max >= PV_size_min:
            iteration_storage_size = storage_size_max
            while iteration_storage_size >= storage_size_min:
                simulation = Energy_System().simulation(start_year = start_year, end_year = end_year, 
                                              PV_size = PV_size_max, 
                                              storage_size = iteration_storage_size)
                new_appraisal = self.system_appraisal(simulation,previous_systems)
                if self.check_threshold(new_appraisal).empty == False:
                    system_appraisals = pd.concat([system_appraisals,new_appraisal],axis=0)
                else:
                    break
                iteration_storage_size -= storage_size_step
                if iteration_storage_size < 0:
                    break
#   Check minimum case where no extra storage is required
            if iteration_storage_size < storage_size_min:
                simulation = Energy_System().simulation(start_year = start_year, end_year = end_year,
                                          PV_size = PV_size_max, 
                                          storage_size = storage_size_min)
                new_appraisal = self.system_appraisal(simulation,previous_systems)
                if self.check_threshold(new_appraisal).empty == False:
                    system_appraisals = pd.concat([system_appraisals,new_appraisal],axis=0)    
            PV_size_max -= PV_size_step
#   Check minimum case where no extra PV is required
            if (PV_size_max < PV_size_min) & (PV_size_max >= 0):
                iteration_storage_size = storage_size_max
                while iteration_storage_size >= storage_size_min:
                    simulation = Energy_System().simulation(start_year = start_year, end_year = end_year, 
                                                  PV_size = PV_size_min, 
                                                  storage_size = iteration_storage_size)
                    new_appraisal = self.system_appraisal(simulation,previous_systems)
                    if self.check_threshold(new_appraisal).empty == False:
                        system_appraisals = pd.concat([system_appraisals,new_appraisal],axis=0)
                    else:
                        break
                    iteration_storage_size -= storage_size_step
#   Check minimum case where no extra storage is required
                if (iteration_storage_size < storage_size_min) & (iteration_storage_size >= 0):
                    simulation = Energy_System().simulation(start_year = start_year, end_year = end_year,
                                              PV_size = PV_size_max, 
                                              storage_size = storage_size_min)
                    new_appraisal = self.system_appraisal(simulation,previous_systems)
                    if self.check_threshold(new_appraisal).empty == False:
                        system_appraisals = pd.concat([system_appraisals,new_appraisal],axis=0)                    
        iteration_results = tuple([system_appraisals,largest_system,previous_systems])
        return iteration_results

#%%
# =============================================================================
# SYSTEM APPRAISALS
#       These system appraisal functions evaluate the technical, financial and
#       overall performance of the energy systems that have been simulated.  
# =============================================================================
    def simulation_technical_appraisal(self,simulation):
        '''
        Function:
            Appraises the technical performance of a minigrid system
        Inputs:
            simulation          Outputs of Energy_System().simulation(...)
            start_year          Start year of this simulation period
            end_year            End year of this simulation period
            
        Outputs:
            system_outputs      DataFrame of key technical data e.g. energy used,
                                    unmet energy, blackout percentage, discounted energy
        '''
#   Initialise
        simulation_results = simulation[0]
        simulation_details = simulation[1]
        start_year = simulation_details.loc['System details']['Start year']
        end_year = simulation_details.loc['System details']['End year']
        system_outputs = pd.DataFrame(index=['System results'])
#   Calculate system blackouts
        system_blackouts = np.mean(simulation_results['Blackouts'])
#   Total energy used
        total_energy = np.sum(simulation_results['Total energy used (kWh)'])
        total_load_energy = np.sum(simulation_results['Load energy (kWh)'])
        total_renewables_used = np.sum(simulation_results['Renewables energy used (kWh)'])
        total_storage_used = np.sum(simulation_results['Storage energy supplied (kWh)'])
        total_grid_used = np.sum(simulation_results['Grid energy (kWh)'])
        total_diesel_used = np.sum(simulation_results['Diesel energy (kWh)'])
        total_unmet_energy = np.sum(simulation_results['Unmet energy (kWh)'])
        renewables_fraction = (total_renewables_used+total_storage_used)/total_energy
        unmet_fraction = total_unmet_energy/total_load_energy
#   Calculate total discounted energy
        total_energy_daily = hourly_profile_to_daily_sum(simulation_results['Total energy used (kWh)'])
        discounted_energy = Finance().discounted_energy_total(total_energy_daily,start_year,end_year)       
#   Calculate proportion of kerosene displaced (defaults to zero if kerosene is not originally used)
        if np.sum(simulation_results['Kerosene lamps']) > 0.0:
            kerosene_displacement = ((np.sum(simulation_results['Kerosene mitigation']))/
                                     (np.sum(simulation_results['Kerosene mitigation']) + 
                                      np.sum(simulation_results['Kerosene lamps'])))
        else:
            kerosene_displacement = 0.0
#   Calculate diesel fuel usage
        total_diesel_fuel = np.sum(simulation_results['Diesel fuel usage (l)'])
#   Return outputs        
        system_outputs['Blackouts'] = system_blackouts
        system_outputs['Unmet energy fraction'] = unmet_fraction
        system_outputs['Renewables fraction'] = renewables_fraction
        system_outputs['Total energy (kWh)'] = total_energy
        system_outputs['Unmet energy (kWh)'] = total_unmet_energy
        system_outputs['Renewable energy (kWh)'] = total_renewables_used
        system_outputs['Storage energy (kWh)'] = total_storage_used
        system_outputs['Grid energy (kWh)'] = total_grid_used
        system_outputs['Diesel energy (kWh)'] = total_diesel_used
        system_outputs['Discounted energy (kWh)'] = discounted_energy
        system_outputs['Kerosene displacement'] = kerosene_displacement
        system_outputs['Diesel fuel usage (l)'] = total_diesel_fuel
#   Return outputs
        return system_outputs.round(3)
    
    def simulation_financial_appraisal(self,simulation,previous_systems = pd.DataFrame([])):
        '''
        Function:
            Appraises the financial performance of a minigrid system
        Inputs:
            simulation          Outputs of Energy_System().simulation(...)
            previous_systems    Report from previously installed system (not require
                                    if no system was previously deployed)
        Outputs:
            system_outputs      DataFrame of key financial data e.g. costs for equipment,
                                    O&M and running costs, kerosene spending and mitigation
        '''
#   Initialise
        simulation_results = simulation[0]
        simulation_details = simulation[1]
        start_year = int(simulation_details.loc['System details']['Start year'])
        end_year = int(simulation_details.loc['System details']['End year'])
        intallation_year = start_year
        system_outputs = pd.DataFrame(index=['System results'])
#   Check to see if a system was previously installed     
        if previous_systems.empty == True:
            previous_system = pd.DataFrame({'Final PV size':0.0,
                                            'Final storage size':0.0,
                                            'Diesel capacity':0.0,
                                            'Total system cost ($)':0.0,
                                            'Discounted energy (kWh)':0.0
                                            },index=['System details'])
        else:
            previous_system = previous_systems.tail(1).reset_index(drop=True)
            previous_system = previous_system.rename({0:'System details'},axis='index')           
#   Calculate new PV, storage and diesel installations
        PV_addition = (simulation_details.loc['System details']['Initial PV size']-
                       previous_system.loc['System details']['Final PV size'])
        storage_addition = (simulation_details.loc['System details']['Initial storage size']-
                       previous_system.loc['System details']['Final storage size'])
        diesel_addition = (simulation_details.loc['System details']['Diesel capacity']-
                       previous_system.loc['System details']['Diesel capacity'])
#   Calculate new equipment costs (discounted)
        equipment_costs = Finance().discounted_equipment_cost(
                PV_array_size = PV_addition,
                storage_size = storage_addition,diesel_size = diesel_addition,
                year=intallation_year) + Finance().get_independent_expenditure(
                        start_year,end_year)
#   Calculate costs of connecting new households (discounted)
        connections_cost = Finance().get_connections_expenditure(
                households = simulation_results['Households'],
                year = intallation_year)
#   Calculate operating costs of the system during this simulation (discounted)
        OM_costs = Finance().get_total_OM(
                PV_array_size = simulation_details.loc['System details']['Initial PV size'],
                storage_size = simulation_details.loc['System details']['Initial storage size'],
                diesel_size = simulation_details.loc['System details']['Diesel capacity'],
                start_year = start_year,end_year = end_year)
#   Calculate running costs of the system (discounted)
        diesel_costs = Finance().get_diesel_fuel_expenditure(
                diesel_fuel_usage_hourly = simulation_results['Diesel fuel usage (l)'],
                start_year=start_year,end_year=end_year)
        grid_costs = Finance().get_grid_expenditure(
                grid_energy_hourly = simulation_results['Grid energy (kWh)'],
                start_year=start_year,end_year=end_year)
        kerosene_costs = Finance().get_kerosene_expenditure(
                kerosene_lamps_in_use_hourly = simulation_results['Kerosene lamps'],
                start_year=start_year,end_year=end_year)
        kerosene_costs_mitigated = Finance().get_kerosene_expenditure_mitigated(
                kerosene_lamps_mitigated_hourly = simulation_results['Kerosene mitigation'],
                start_year=start_year,end_year=end_year)
#   Total cost incurred during simulation period (discounted)
        total_cost = equipment_costs + connections_cost + OM_costs + diesel_costs + grid_costs + kerosene_costs
        total_system_cost = equipment_costs + connections_cost + OM_costs + diesel_costs + grid_costs
#   Return outputs        
        system_outputs['Total cost ($)'] = total_cost
        system_outputs['Total system cost ($)'] = total_system_cost
        system_outputs['New equipment cost ($)'] = equipment_costs
        system_outputs['New connection cost ($)'] = connections_cost
        system_outputs['O&M cost ($)'] = OM_costs
        system_outputs['Diesel cost ($)'] = diesel_costs
        system_outputs['Grid cost ($)'] = grid_costs
        system_outputs['Kerosene cost ($)'] = kerosene_costs
        system_outputs['Kerosene cost mitigated ($)'] = kerosene_costs_mitigated
        return system_outputs.round(2)
    
    def simulation_environmental_appraisal(self,simulation,previous_systems = pd.DataFrame([])):
        '''
        Function:
            Appraises the environmental impact of a minigrid system
        Inputs:
            simulation          Outputs of Energy_System().simulation(...)
            previous_systems    Report from previously installed system (not require
                                    if no system was previously deployed)
        Outputs:
            system_outputs      DataFrame of key environmental data e.g. GHGs from equipment,
                                    O&M, kerosene spending and mitigation
        '''
#   Initialise
        simulation_results = simulation[0]
        simulation_details = simulation[1]
        start_year = int(simulation_details.loc['System details']['Start year'])
        end_year = int(simulation_details.loc['System details']['End year'])
        intallation_year = start_year
        system_outputs = pd.DataFrame(index=['System results'])
#   Check to see if a system was previously installed     
        if previous_systems.empty == True:
            previous_system = pd.DataFrame({'Final PV size':0.0,
                                            'Final storage size':0.0,
                                            'Diesel capacity':0.0,
                                            'Total system cost ($)':0.0,
                                            'Discounted energy (kWh)':0.0
                                            },index=['System details'])
        else:
            previous_system = previous_systems.tail(1).reset_index(drop=True)
            previous_system = previous_system.rename({0:'System details'},axis='index')           
#   Calculate new PV, storage and diesel installations
        PV_addition = (simulation_details.loc['System details']['Initial PV size']-
                       previous_system.loc['System details']['Final PV size'])
        storage_addition = (simulation_details.loc['System details']['Initial storage size']-
                       previous_system.loc['System details']['Final storage size'])
        diesel_addition = (simulation_details.loc['System details']['Diesel capacity']-
                       previous_system.loc['System details']['Diesel capacity'])
#   Calculate new equipment GHGs
        equipment_GHGs = GHGs().get_total_equipment_GHGs(
                PV_array_size = PV_addition,
                storage_size = storage_addition,diesel_size = diesel_addition,
                year=intallation_year) + GHGs().get_independent_GHGs(
                        start_year,end_year)
#   Calculate GHGs of connecting new households
        connections_GHGs = GHGs().get_connections_GHGs(
                households = simulation_results['Households'],
                year = intallation_year)
#   Calculate operating GHGs of the system during this simulation
        OM_GHGs = GHGs().get_total_OM(
                PV_array_size = simulation_details.loc['System details']['Initial PV size'],
                storage_size = simulation_details.loc['System details']['Initial storage size'],
                diesel_size = simulation_details.loc['System details']['Diesel capacity'],
                start_year = start_year,end_year = end_year)
#   Calculate running GHGs of the system
        diesel_GHGs = GHGs().get_diesel_fuel_GHGs(
                diesel_fuel_usage_hourly = simulation_results['Diesel fuel usage (l)'],
                start_year=start_year,end_year=end_year)
        grid_GHGs = GHGs().get_grid_GHGs(
                grid_energy_hourly = simulation_results['Grid energy (kWh)'],
                start_year=start_year,end_year=end_year)
        kerosene_GHGs = GHGs().get_kerosene_GHGs(
                kerosene_lamps_in_use_hourly = simulation_results['Kerosene lamps'],
                start_year=start_year,end_year=end_year)
        kerosene_GHGs_mitigated = GHGs().get_kerosene_GHGs_mitigated(
                kerosene_lamps_mitigated_hourly = simulation_results['Kerosene mitigation'],
                start_year=start_year,end_year=end_year)
#   Total GHGs incurred during simulation period
        total_GHGs = equipment_GHGs + connections_GHGs + OM_GHGs + diesel_GHGs + grid_GHGs + kerosene_GHGs
        total_system_GHGs = equipment_GHGs + connections_GHGs + OM_GHGs + diesel_GHGs + grid_GHGs
#   Return outputs        
        system_outputs['Total GHGs (kgCO2eq)'] = total_GHGs
        system_outputs['Total system GHGs (kgCO2eq)'] = total_system_GHGs
        system_outputs['New equipment GHGs (kgCO2eq)'] = equipment_GHGs
        system_outputs['New connection GHGs (kgCO2eq)'] = connections_GHGs
        system_outputs['O&M GHGs (kgCO2eq)'] = OM_GHGs
        system_outputs['Diesel GHGs (kgCO2eq)'] = diesel_GHGs
        system_outputs['Grid GHGs (kgCO2eq)'] = grid_GHGs
        system_outputs['Kerosene GHGs (kgCO2eq)'] = kerosene_GHGs
        system_outputs['Kerosene GHGs mitigated (kgCO2eq)'] = kerosene_GHGs_mitigated
        return system_outputs.round(2)
    
    def system_appraisal(self,simulation,previous_systems = pd.DataFrame([])):
        '''
        Function:
            Appraises the total performance of a minigrid system for all performance metrics
        Inputs:
            simulation          Outputs of Energy_System().simulation(...)
            previous_systems    Report from previously installed system (not required
                                    if no system was previously deployed)
        Outputs:
            system_outputs      DataFrame of key all key technical, performance,
                                    financial and environmental information
        '''
#   Initialisation
#   Check to see if a system was previously installed     
        if previous_systems.empty == True:
            previous_system = pd.DataFrame({'Final PV size':0.0,
                                            'Final storage size':0.0,
                                            'Diesel capacity':0.0,
                                            'Total system cost ($)':0.0,
                                            'Total system GHGs (kgCO2eq)':0.0,
                                            'Discounted energy (kWh)':0.0,
                                            'Cumulative cost ($)':0.0,
                                            'Cumulative system cost ($)':0.0,
                                            'Cumulative GHGs (kgCO2eq)':0.0,
                                            'Cumulative system GHGs (kgCO2eq)':0.0,
                                            'Cumulative energy (kWh)':0.0,
                                            'Cumulative discounted energy (kWh)':0.0,
                                            },index=['System results'])
        else:
            previous_system = previous_systems.tail(1).reset_index(drop=True)
            previous_system = previous_system.rename({0:'System results'},axis='index') 
        combined_outputs = pd.DataFrame(index=['System results'])
#   Get results which will be carried forward into optimisation process
        system_details = simulation[1].rename({'System details':'System results'},axis='index')
        technical_results = self.simulation_technical_appraisal(simulation)
        financial_results = self.simulation_financial_appraisal(simulation,previous_systems = previous_systems)
        environmental_results = self.simulation_environmental_appraisal(simulation,previous_systems = previous_systems)

#   Get results that rely on metrics of different kinds and several different iteration periods
        cumulative_costs = (financial_results['Total cost ($)'] + 
                                              previous_system['Cumulative cost ($)'])
        cumulative_system_costs = (financial_results['Total system cost ($)'] + 
                                              previous_system['Cumulative system cost ($)'])
        cumulative_GHGs = (environmental_results['Total GHGs (kgCO2eq)'] +
                                              previous_system['Cumulative GHGs (kgCO2eq)'])
        cumulative_system_GHGs = (environmental_results['Total system GHGs (kgCO2eq)'] +
                                              previous_system['Cumulative system GHGs (kgCO2eq)'])
        cumulative_energy = (technical_results['Total energy (kWh)'] + 
                                              previous_system['Cumulative energy (kWh)'])
        cumulative_discounted_energy = (technical_results['Discounted energy (kWh)'] + 
                                              previous_system['Cumulative discounted energy (kWh)'])
#   Combined metrics        
        LCUE = float(cumulative_system_costs / cumulative_discounted_energy)
        emissions_intensity = 1000.0 * float(cumulative_system_GHGs / cumulative_energy) # in grams
#   Format outputs
        combined_outputs['Cumulative cost ($)'] = cumulative_costs
        combined_outputs['Cumulative system cost ($)'] = cumulative_system_costs
        combined_outputs['Cumulative GHGs (kgCO2eq)'] = cumulative_GHGs
        combined_outputs['Cumulative system GHGs (kgCO2eq)'] = cumulative_system_GHGs
        combined_outputs['Cumulative energy (kWh)'] = cumulative_energy
        combined_outputs['Cumulative discounted energy (kWh)'] = cumulative_discounted_energy
        combined_outputs['LCUE ($/kWh)'] = np.round(LCUE,3)
        combined_outputs['Emissions intensity (gCO2/kWh)'] = np.round(emissions_intensity,3)
#   Return results
        system_outputs = pd.concat([system_details,combined_outputs,technical_results,
                                    financial_results,environmental_results],axis=1)
        return system_outputs
#%%
# =============================================================================
# GENERAL FUNCTIONS
#       These functions perform various general processes for the optimisation
#       functions including checking thresholds, saving optimisations as .csv 
#       files and summarising results.  
# =============================================================================       
    def change_parameter(self,parameter,new_parameter_value):
        """
        Function:
            Edits .csv file to change parameter value in "Optimisation inputs.csv"
        Inputs:
            parameter               Name of the parameter to be changed
            new_parameter_value     Value for the parameter to be changed
        Outputs:
            Updated "Optimisation inputs.csv" file with the new parameter
        """        
        parameter = str(parameter)
        new_optimisation_inputs = self.optimisation_inputs
        new_optimisation_inputs[1][parameter] = float(new_parameter_value)
        new_optimisation_inputs.to_csv(self.location_filepath + 
                                       '/Optimisation/Optimisation inputs.csv',header=None)

    def save_optimisation(self,optimisation_name,filename=None):
        """
        Function:
            Saves optimisation outputs to a .csv file
        Inputs:
            optimisation_name     DataFrame output from Optimisation().multiple_optimisation_step(...)
            filename              Name of .csv file to be saved as (defaults to timestamp)
        Outputs:
            Optimisation saved to .csv file
        """
        if filename != None:
            optimisation_name.to_csv(os.path.join(self.optimisation_storage, str(filename) + '.csv'))
        else:
            filename = str(datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S"))
            optimisation_name.to_csv(os.path.join(self.optimisation_storage, filename + '.csv'))
        print('\nOptimisation saved as '+ filename + '.csv')
            
    def open_optimisation(self,filename):
        """
        Function:
            Opens a previously saved optimisation from a .csv file
        Inputs:
            filename            Name of the .csv file to be opened (not including .csv)
        Outputs:
            DataFrame of previously performed optimisation
        """
        output = pd.read_csv(os.path.join(self.optimisation_storage, str(filename) + '.csv',index_col=0))
        return output

    def summarise_optimisation_results(self,optimisation_results):
        '''
        Function:
            Summarise the steps of the optimisation results into a output for the 
                lifetime of the system
        Inputs:
            optimisation_results    Results of Optimisation().multiple_optimisation_step(...)
        Outputs:
            result                  Aggregated results for the lifetime of the system
        ''' 
#   Data where the inital and/or final entries are most relevant
        start_year = int(optimisation_results['Start year'].iloc[0])
        end_year  = int(optimisation_results['End year'].iloc[-1])
        step_length = int(optimisation_results['End year'].iloc[0] -
                          optimisation_results['Start year'].iloc[0])
        optimisation_length = end_year - start_year
        max_PV = optimisation_results['Initial PV size'].iloc[-1]
        max_storage = optimisation_results['Initial storage size'].iloc[-1]
        max_diesel = optimisation_results['Diesel capacity'].iloc[-1]
        LCUE = optimisation_results['LCUE ($/kWh)'].iloc[-1]
        emissions_intensity = optimisation_results['Emissions intensity (gCO2/kWh)'].iloc[-1]
        total_GHGs = optimisation_results['Cumulative GHGs (kgCO2eq)'].iloc[-1]
        total_system_GHGs = optimisation_results['Cumulative system GHGs (kgCO2eq)'].iloc[-1]
#   Data where the mean is most relevant
        blackouts = np.mean(optimisation_results['Blackouts'])
        kerosene_displacement = np.mean(optimisation_results['Kerosene displacement'])        
#   Data where the sum is most relevant
        total_energy = np.sum(optimisation_results['Total energy (kWh)'])
        unmet_energy = np.sum(optimisation_results['Unmet energy (kWh)'])
        renewable_energy = np.sum(optimisation_results['Renewable energy (kWh)'])
        storage_energy = np.sum(optimisation_results['Storage energy (kWh)'])
        grid_energy = np.sum(optimisation_results['Grid energy (kWh)'])
        diesel_energy = np.sum(optimisation_results['Diesel energy (kWh)'])
        discounted_energy = np.sum(optimisation_results['Discounted energy (kWh)'])
        diesel_fuel_usage = np.sum(optimisation_results['Diesel fuel usage (l)'])
        total_cost = np.sum(optimisation_results['Total cost ($)'])
        total_system_cost = np.sum(optimisation_results['Total system cost ($)'])
        new_equipment_cost = np.sum(optimisation_results['New equipment cost ($)'])
        new_connection_cost = np.sum(optimisation_results['New connection cost ($)'])
        OM_cost = np.sum(optimisation_results['O&M cost ($)'])
        diesel_cost = np.sum(optimisation_results['Diesel cost ($)'])
        grid_cost = np.sum(optimisation_results['Grid cost ($)'])
        kerosene_cost = np.sum(optimisation_results['Kerosene cost ($)'])
        kerosene_cost_mitigated = np.sum(optimisation_results['Kerosene cost mitigated ($)'])  
        OM_GHGs = np.sum(optimisation_results['O&M GHGs (kgCO2eq)'])
        diesel_GHGs = np.sum(optimisation_results['Diesel GHGs (kgCO2eq)'])
        grid_GHGs = np.sum(optimisation_results['Grid GHGs (kgCO2eq)'])
        kerosene_GHGs = np.sum(optimisation_results['Kerosene GHGs (kgCO2eq)'])
        kerosene_mitigated_GHGs = np.sum(optimisation_results['Kerosene GHGs mitigated (kgCO2eq)'])

#   Data which requires combinations of summary results
        unmet_fraction = round(unmet_energy/total_energy,3)
        renewables_fraction = round(renewable_energy/total_energy,3)  
        storage_fraction = round(storage_energy/total_energy,3)
        diesel_fraction = round(diesel_energy/total_energy,3)
        grid_fraction = round(grid_energy/total_energy,3)
#   Combine results into output
        results = pd.DataFrame({'Start year':start_year,
                                'End year':end_year,
                                'Step length':step_length,
                                'Optimisation length':optimisation_length,
                                'Maximum PV size':max_PV,
                                'Maximum storage size':max_storage,
                                'Maximum diesel capacity':max_diesel,
                                'LCUE ($/kWh)':LCUE,
                                'Emissions intensity (gCO2/kWh)':emissions_intensity,
                                'Blackouts':blackouts,
                                'Unmet fraction':unmet_fraction,
                                'Renewables fraction':renewables_fraction,
                                'Storage fraction':storage_fraction,
                                'Diesel fraction':diesel_fraction,
                                'Grid fraction':grid_fraction,                                
                                'Total energy (kWh)':total_energy,
                                'Unmet energy (kWh)':unmet_energy,
                                'Renewable energy (kWh)':renewable_energy,
                                'Storage energy (kWh)':storage_energy,
                                'Grid energy (kWh)':grid_energy,
                                'Diesel energy (kWh)':diesel_energy,
                                'Discounted energy (kWh)':discounted_energy,
                                'Total cost ($)':total_cost,
                                'Total system cost ($)':total_system_cost,
                                'New equipment cost ($)':new_equipment_cost,
                                'New connection cost ($)':new_connection_cost,
                                'O&M cost ($)':OM_cost,
                                'Diesel cost ($)':diesel_cost,
                                'Grid cost ($)':grid_cost,
                                'Kerosene cost ($)':kerosene_cost,
                                'Kerosene cost mitigated ($)':kerosene_cost_mitigated,
                                'Kerosene displacement':kerosene_displacement,
                                'Diesel fuel usage (l)':diesel_fuel_usage,
                                'Total GHGs (kgCO2eq)':total_GHGs,
                                'Total system GHGs (kgCO2eq)':total_system_GHGs,
                                'Total GHGs (kgCO2eq)':total_GHGs,
                                'O&M GHGs (kgCO2eq)':OM_GHGs,
                                'Diesel GHGs (kgCO2eq)':diesel_GHGs,
                                'Grid GHGs (kgCO2eq)':grid_GHGs,
                                'Kerosene GHGs (kgCO2eq)':kerosene_GHGs,
                                'Kerosene GHGs mitigated (kgCO2eq)':kerosene_mitigated_GHGs,
                                },index=['Lifetime results'])
        return results

    def check_threshold(self,system_appraisals):
        '''
        Function:
            Checks whether any of the system appraisals fulfill the threshold criterion
        Inputs:
            system_appraisals       Appraisals of the systems which have been simulated
        Outputs:
            sufficient_systems      Appraisals of the systems which meet the threshold criterion (sufficient systems)
        '''
#   Initialise
        threshold_criterion = str(self.optimisation_inputs[1]['Threshold criterion'])
        threshold_value = float(self.optimisation_inputs[1]['Threshold value'])
#   Check whether value should be a maximum permitted value or a minimum permitted value        
        if threshold_criterion in self.maximum_criteria:
            sufficient_systems = system_appraisals[system_appraisals[threshold_criterion] <= threshold_value]
        elif threshold_criterion in self.minimum_criteria:
            sufficient_systems = system_appraisals[system_appraisals[threshold_criterion] >= threshold_value]
        return sufficient_systems
   
 #%%
# =============================================================================
# UNSUPPORTED FUNCTIONS
#       This process is similar to the optimisation process used by previous
#       versions of CLOVER. It has been replaced by the new optimisation process
#       and will no longer be updated.
# ============================================================================= 
    def complete_simulation_iteration(self,PV_sizes=[],storage_sizes=[],previous_systems = pd.DataFrame([]),
                             start_year = 0):
        '''
        Function:
            *** THIS FUNCTION IS OUTDATED AND HAS BEEN REPLACED BY Opimisation().find_optimum_system(...) ***
            *** THIS FUNCTION IS INCLUDED FOR INTEREST AND WILL NO LONGER BE UPDATED ***
            
            Iterates simulations over a range of PV and storage sizes to give appraisals of each system.
                Identical to the previous CLOVER method of simulation i.e. every system within a given range
        Inputs:
            PV_sizes            Range of PV sizes in the form [minimum, maximum, step size]
            storage_sizes       Range of storage sizes in the form [minimum, maximum, step size]
            previous_system     Appraisal of the system already in place before this simulation period
            start_year          Start year of this simulation period
        Outputs:
            appraisals          DataFrame of system results
        '''
#   Initialise
        PV_sizes = pd.DataFrame(PV_sizes)
        storage_sizes = pd.DataFrame(storage_sizes)
        system_appraisals = pd.DataFrame([])
        simulation_number = 0
        end_year = start_year + int(self.optimisation_inputs[1]['Iteration length'])
#   Check to see if PV sizes have been set
        if PV_sizes.empty == True:
            PV_size_min = float(self.optimisation_inputs[1]['PV size (min)'])
            PV_size_max = float(self.optimisation_inputs[1]['PV size (max)'])
            PV_size_step = float(self.optimisation_inputs[1]['PV size (step)'])
#   Check to see if storage sizes have been set
        if storage_sizes.empty == True:
            storage_size_min = float(self.optimisation_inputs[1]['Storage size (min)'])
            storage_size_max = float(self.optimisation_inputs[1]['Storage size (max)'])
            storage_size_step = float(self.optimisation_inputs[1]['Storage size (step)'])
            
#   Iterate over PV sizes
        for PV in np.arange(PV_size_min,PV_size_max+PV_size_step,PV_size_step):
#   Iterate over storage sizes
            for storage in np.arange(storage_size_min,storage_size_max+storage_size_step,storage_size_step):
#   Run simulation
                simulation_number += 1
                simulation = Energy_System().simulation(start_year = start_year, end_year = end_year, 
                                          PV_size = PV, storage_size = storage)
                new_appraisal = self.system_appraisal(simulation,previous_systems)
                system_appraisals = pd.concat([system_appraisals,new_appraisal.rename({
                        'System results':simulation_number},axis='index')],axis=0)
        return system_appraisals
