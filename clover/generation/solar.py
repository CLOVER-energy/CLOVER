# -*- coding: utf-8 -*-
"""
===============================================================================
                            SOLAR GENERATION FILE
===============================================================================
                            Most recent update:
                             19 November 2019
===============================================================================
Made by:
    Philip Sandwell
Additional credits:
    Iain Staffell, Stefan Pfenninger & Scot Wheeler
For more information, please email:
    philip.sandwell@googlemail.com
===============================================================================
"""
import json
import os
import numpy as np
import pandas as pd
import requests

class Solar():
    def __init__(self):
        self.location = 'Bahraich'
        self.CLOVER_filepath = os.getcwd()
        self.location_filepath = os.path.join(self.CLOVER_filepath, 'Locations', self.location)
        self.generation_filepath = os.path.join(self.location_filepath, 'Generation', 'PV')
        self.input_data = pd.read_csv(os.path.join(self.generation_filepath, 'PV generation inputs.csv'),header=None,index_col=0)[1]
        self.location_data_filepath = os.path.join(self.location_filepath, 'Location Data')
        self.location_input_data = pd.read_csv(os.path.join(self.location_data_filepath, 'Location inputs.csv'),header=None,index_col=0)[1]
#%%
    def total_solar_output(self,start_year=2007):
        """
        Function:
            Generates 20 years of solar output data by taking 10 consecutive years
                and repeating them
        Inputs:
            .csv files of ten years (e.g. 2007-2016)
            start_year              (float, e.g. 2007)
        Outputs:
            .csv file for twenty years of PV output data
        """
        output = pd.DataFrame([])
#   Get data for each year using iteration, and add that data to the output file 
        for i in np.arange(10):
            iteration_year= start_year + i
            iteration_year_data = pd.read_csv(self.generation_filepath + 'solar_generation_' + str(iteration_year) + '.csv',header=None,index_col=0)
            output = pd.concat([output, iteration_year_data],ignore_index = True)
#   Repeat the initial 10 years in two consecutive periods 
        output = pd.concat([output, output],ignore_index = True)
        output.to_csv(self.generation_filepath + 'solar_generation_20_years.csv',header=None)
        
    def solar_degradation(self):
        lifetime = self.input_data.loc['lifetime']
        hourly_degradation = 0.20/(lifetime * 365 * 24)
        lifetime_degradation = []
        for i in range((20*365*24)+1):
            equiv = 1.0 - i * hourly_degradation
            lifetime_degradation.append(equiv)
        return pd.DataFrame(lifetime_degradation)
            
    def save_solar_output(self,gen_year = 2014):
        """
        Function:
            Saves PV generation data as a named .csv file in the location generation file
        Inputs:
            gen_year            (float or int)
        Outputs:
            .csv file of PV generation (kW/kWp) for the given year
        """
#   Get input data from "Location data" file
        time_dif = float(self.location_input_data.loc['Time difference'])
#   Get solar output in local time for the given year 
        solar_output = self.get_solar_local_time(
                self.get_solar_generation_from_RN(gen_year),time_difference = time_dif)
#   Write the data to file
        solar_output.to_csv(self.generation_filepath
                            + 'solar_generation_' + str(gen_year) + '.csv',header=None)

    def get_solar_local_time(self,solar_data_UTC, time_difference = 0):
        """
        Function:
            Converts data from Renewables.ninja (kW/kWp in UTC time)
                to local time (user defined)
        Inputs:
            solar_data_UTC      (Dataframe)
            time_difference     (Number, does not need to be integer)
        Outputs:
            PV output data (kW/kWp) in local time
        """
#   Round time difference to nearest hour (NB India, Nepal etc. do not do this)
        time_difference = round(time_difference)     
#   East of Greenwich
        if time_difference > 0:
            splits = np.split(solar_data_UTC,[len(solar_data_UTC)-time_difference])
            solar_data_local = pd.concat([splits[1],splits[0]],ignore_index=True)
#   West of Greenwich 
        elif time_difference < 0:
            splits = np.split(solar_data_UTC,[abs(time_difference)])
            solar_data_local = pd.concat([splits[1],splits[0]],ignore_index=True)
#   No time difference, included for completeness
        else:
            solar_data_local = solar_data_UTC
        return solar_data_local
    
    def get_solar_generation_from_RN(self,year=2014):
        '''
        Credit:
            Renewables.ninja, API interface and all data accessed by this function
                by Iain Staffell & Stefan Pfenninger
            Python code from 
                https://www.renewables.ninja/documentation/api/python-example
            Cite these papers in your documents! 
                S. Pfenninger and I. Staffell, 2016. Long-term patterns of European 
                    PV output using 30 years of validated hourly reanalysis and 
                        satellite data. Energy, 114, 1251–1265.
                I. Staffell and S. Pfenninger, 2016. Using Bias-Corrected Reanalysis
                    to Simulate Current and Future Wind Power Output. Energy, 
                        114, 1224–1239.
            Adapted from code by Scot Wheeler
        Function:
            Gets data from Renewables.ninja for a given year (kW/kWp) in UTC time
        Inputs:
            year                        (integer, from 2000-2016 inclusive)
            'PV generation inputs.csv'     (input file with location latitude, longitude,
                                             tilt angle and azimuth)
            token                       (API token )
        Outputs:
            PV output data in kW/kWp in UTC time
        Notes:
            Need to convert to local time from UTC using self.get_solar_local_time(...)
        '''
#   Access information
        api_base = 'https://www.renewables.ninja/api/'
        s = requests.session()
        url = api_base + 'data/pv'
        token = str(self.location_input_data.loc['token'])
        s.headers = {'Authorization': 'Token ' + token}

#   Gets some data from input file
        args = {
            'lat': float(self.location_input_data.loc['Latitude']),
            'lon': float(self.location_input_data.loc['Longitude']),
            'date_from': str(year)+'-01-01',
            'date_to': str(year)+'-12-31',
            'dataset': 'merra2',
            'capacity': 1.0,
            'system_loss': 0,
            'tracking': 0,          
            'tilt': float(self.input_data.loc['tilt']),
            'azim': float(self.input_data.loc['azim']),
            'format': 'json',
#   Metadata and raw data now supported by different function in API
#            'metadata': False,
#            'raw': False
        }        
        r = s.get(url, params=args)
        
#   Parse JSON to get a pandas.DataFrame
        parsed_response = json.loads(r.text)
        df = pd.read_json(json.dumps(parsed_response['data']), orient='index')
        df = df.reset_index(drop=True)
       
##   Remove leap days
        if year in {2004,2008,2012,2016,2020}:
            feb_29 = (31+28)*24
            df = df.drop(range(feb_29,feb_29+24))
            df = df.reset_index(drop=True)
        return df
