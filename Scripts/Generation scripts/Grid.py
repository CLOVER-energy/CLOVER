# -*- coding: utf-8 -*-
"""
===============================================================================
                            GRID GENERATION FILE
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
import pandas as pd
import random

class Grid():
    def __init__(self):
        self.location = 'Bahraich'
        self.CLOVER_filepath = '/***YOUR LOCAL FILE PATH***/CLOVER 4.0'
        self.location_filepath = self.CLOVER_filepath + '/Locations/' + self.location
        self.location_inputs = pd.read_csv(self.location_filepath + '/Location Data/Location inputs.csv',header=None,index_col=0)[1]
        self.generation_filepath = self.location_filepath + '/Generation/Grid/'
        self.grid_inputs = pd.read_csv(self.generation_filepath + 'Grid inputs.csv',index_col=0)
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