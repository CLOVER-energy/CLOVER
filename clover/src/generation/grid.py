# -*- coding: utf-8 -*-
"""
===============================================================================
                            GRID GENERATION FILE
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

import os
import random

import pandas as pd

from ...__utils__ import LOCATIONS_FOLDER_NAME

class Grid():
    def __init__(self):
        self.location = 'Bahraich'
        self.CLOVER_filepath = os.getcwd()
        self.location_filepath = os.path.join(self.CLOVER_filepath, LOCATIONS_FOLDER_NAME, self.location)
        self.location_inputs = pd.read_csv(os.path.join(self.location_filepath, 'Location Data', 'Location inputs.csv'),header=None,index_col=0)[1]
        self.generation_filepath = os.path.join(self.location_filepath, 'Generation')
        self.grid_inputs = pd.read_csv(os.path.join(self.generation_filepath, 'Grid inputs.csv'),index_col=0)
#%%
    def get_lifetime_grid_status(self):
        """
        Function:
            Automatically calculates the grid availability profiles of all input types
        Inputs:
            "Grid inputs.csv"
        Outputs:
            .csv files of the availability of all input grid profiles for the duration
            of the simulation period
        """
        grid_types = list(self.grid_inputs)
        for i in range(Grid().grid_inputs.shape[1]):
            grid_hours = pd.DataFrame(self.grid_inputs[grid_types[i]])
            grid_status = []
            for day in range(365 * int(self.location_inputs['Years'])):
                for hour in range(grid_hours.size):
                    if random.random() < grid_hours.iloc[hour].values:
                        grid_status.append(1)
                    else:
                        grid_status.append(0)
            grid_name = grid_types[i]
            grid_times = pd.DataFrame(grid_status)
            grid_times.to_csv(self.generation_filepath + grid_name + '_grid_status.csv')

    def change_grid_coverage(self,grid_type='bahraich', hours=12):
        grid_profile = self.grid_inputs[grid_type]
        baseline_hours = np.sum(grid_profile)
        new_profile = pd.DataFrame([0]*24)
        for hour in range(24):
            m = interp1d([0,baseline_hours,24],[0,grid_profile[hour],1])
            new_profile.iloc[hour] = m(hours).round(3)
        new_profile.columns = [grid_type+'_'+ str(hours)]
        return new_profile
    
    def save_grid_coverage(self,grid_type='bahraich',hours=12):
        new_profile = self.change_grid_coverage(grid_type,hours)
        new_profile_name = grid_type+'_'+ str(hours)
        output = self.grid_inputs
        if new_profile_name in output.columns:
            output[new_profile_name] = new_profile
        else:
            output = pd.concat([output,new_profile],axis=1)
        output.to_csv(self.generation_filepath + 'Grid inputs.csv')
