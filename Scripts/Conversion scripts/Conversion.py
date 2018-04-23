# -*- coding: utf-8 -*-
"""
===============================================================================
                                CONVERSION FILE
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
import numpy as np
import scipy

class Conversion():
    def __init__(self):
        self.month_mid_day = [0, 14, 45, 72, 104, 133, 164, 194, 225, 256, 286, 317, 344, 364]
        self.hours = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23]
        self.month_start_day = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
#%%     
    def monthly_profile_to_daily_profile(self,monthly_profile):  
        """
        Function:
            Converts a DataFrame of representative monthly values to a DataFrame of representative
            daily values
        Inputs:
            monthly_profile     24x12 DataFrame of hourly values for each month of the year
        Outputs:
            daily_profile       24x365 DataFrame of hourly values for each day of the year
        """
        day_one_profile = pd.DataFrame(np.zeros((24,1)))
        for hour in range(0,24):
            day_one_profile[0][hour] = 0.5*(monthly_profile[0][hour] + monthly_profile[11][hour])
        extended_year_profile = pd.DataFrame(np.zeros((24,14)))
        extended_year_profile[0] = day_one_profile[0]
        for month in range(0,12):
            extended_year_profile[month+1] = monthly_profile[month]
            extended_year_profile[13] = day_one_profile[0]
        daily_profile = []
        for hour in range(0,24):
            daily_profile.append(scipy.interp(range(0,365),self.month_mid_day,extended_year_profile.iloc[hour]))       
        return pd.DataFrame(daily_profile)

#%%
    def hourly_profile_to_daily_sum(self, hourly_profile):
        """
        Function:
            Converts an hour-by-hour profile to a sum for each day
        Inputs:
            hourly_profile      Hour-by-hour profile
        Outputs:
            Sum of hourly values per day
        """
        days = int(hourly_profile.shape[0]/(24))
        daily_profile = pd.DataFrame(hourly_profile.values.reshape((days,24)))
        return pd.DataFrame(np.sum(daily_profile,1))