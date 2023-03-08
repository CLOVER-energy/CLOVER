import copy
import pandas as pd
from .. import load
from typing import Dict
from datetime import date

'''
Per Bag
knapsack problem is used here
T[i,c] := max(T[i-1,c], T[i-1, c-w[i]] + p[i])
with p[i] the probability, and w[i] the consumption needed
T contains the optimal values, l contains the devices used for a given bag
bag can be anything : a minute, an hour; its flexible


prob_devices (n x 1) : the probability for each device for a given bag (minute or hour or...), n is the number of devices
cons_devices (n x 1) : the consumption for each device for a given bag, n is the number of devices
prod_pv : the quantity of the bag (production of pv for this given bag)

=> Complexity is O(n*prod_pv)
'''
def knapsack1d_for_given_unit(prob_devices: pd.Series, cons_devices: pd.Series, prod_pv):
      assert (prob_devices.size == cons_devices.size)

      #we clean inputs for the algorithm
      n = prob_devices.size + 1 
      prod_pv = prod_pv + 1
      prob_devices_copy = [0] + prob_devices.tolist()
      cons_devices_copy = [0] + cons_devices.tolist()

      #we create the data structure
      T = [[0 for i in range(prod_pv)] for j in range(n)]
      l = [[[] for i in range(prod_pv)] for j in range(n)]
      r = [[0 for i in range(prod_pv)] for j in range(n)]
      
      #dynamic programming
      for i in range(1, n):
            for c in range(prod_pv):
                  if(c >= cons_devices_copy[i] and prob_devices_copy[i] > 0):
                        if(T[i-1][c-cons_devices_copy[i]] + prob_devices_copy[i] >= T[i-1][c]):
                              T[i][c] = T[i][c-cons_devices_copy[i]] + prob_devices_copy[i]
                              l[i][c] = copy.copy(l[i-1][c-cons_devices_copy[i]])
                              r[i][c] = r[i-1][c-cons_devices_copy[i]] + cons_devices_copy[i]
                              l[i][c].append(i - 1)
                        else:
                              l[i][c] = copy.deepcopy(l[i-1][c])
                              r[i][c] = r[i - 1][c]
                              T[i][c] = T[i-1][c]
                  else:
                        T[i][c] = T[i-1][c]
                        l[i][c] = copy.deepcopy(l[i-1][c])
                        r[i][c] = r[i - 1][c]
      

      return T[-1][-1], r[-1][-1], l[-1][-1]


'''
We update the probability given the nr_units_devices, in fact if a device does not need energy anymore, we just remove it from 
the list of probabilities.
'''
def update_prob(devices, prob_devices: pd.DataFrame, nr_units_devices):
      for device in devices:
            nr_units_devices[device] = nr_units_devices[device] - 1
            if(nr_units_devices[device] == 0):
                  prob_devices.iloc[device] = 0

'''
Per day
We use a greedy algorithm : we compute first knapsack problem for all the bags, and we take the bag with the highest probability, 
then we blacklist this bag and continue until there is no bag anymore. 

prob_devices (n x nr_bag) : the probability for each device for a each bag 
cons_devices (n x 1) : the consumption for each device for a given bag, n is the number of devices, it is constant (not dependent of the bag)
prod_pv (nr_bag x 1) : the quantity for each bag 

=> Complexity is O(n * max(prod_pv) * nr_bag^2)
'''
def knapsack2d_for_given_unit(prob_devices: pd.DataFrame, cons_devices: pd.Series, prod_pv: pd.Series, nr_units_devices):
      assert (prob_devices[0].size == cons_devices.size and prob_devices.iloc[0].size == prod_pv.size and cons_devices.size == len(nr_units_devices))
      
      nr_bag = prod_pv.size

      black_list_bag = [] 
      load = [0 for i in range(nr_bag)]
      rest = [0 for i in range(nr_bag)] 

      for bag in range(nr_bag):
            curr = []
            for i in range(nr_bag):
                  if(i not in black_list_bag):
                        curr.append((knapsack1d_for_given_unit(prob_devices[i], cons_devices, prod_pv[i]), i))
                        
            max_bag = max(curr)
            idx = max_bag[1]
            devices = max_bag[0][2]
            load_used = max_bag[0][1]
            update_prob(devices, prob_devices, nr_units_devices)
            rest[idx] = prod_pv[idx] - load_used
            black_list_bag.append(idx)
            load[idx] = load_used

      #todo : partial_pv

      
      ratios = (prob_devices.transpose()/cons_devices)
      ratios = ratios.transpose()*pd.Series(rest)
      last_ratio = ratios.max().max()
      while(last_ratio > 0):
            idx_0 = ratios.idxmax()
            idx_1 = ratios.max().idxmax()
            ratios[idx_1][idx_0] = 0
            load[idx_1] = load[idx_1] + cons_devices[idx_0]
            last_ratio = ratios.max().max()
      
      return load


def device_management(start_year, device_utilisations: Dict[load.load.Device, pd.DataFrame], renewables_energy: pd.DataFrame) -> pd.DataFrame:
      '''
      device input : CLOVER/locations/Bahraich/inputs/load/device_utilisation/fridge_times.csv

      prob_devices :
      use the devices matrix (called device_utilisations) : https://github.com/CLOVER-energy/CLOVER/blob/fc4e44bf73c0e695b3c11cd20985fe64e2ebedf8/src/clover/fileparser.py

      cons_devices : 
      electric_power of class Device : https://github.com/CLOVER-energy/CLOVER/blob/fc4e44bf73c0e695b3c11cd20985fe64e2ebedf8/src/clover/load/load.py

      comes from survey data : https://github.com/CLOVER-energy/CLOVER/tree/master/locations/Bahraich/inputs/load
      
      return load profile in a form of a dataframe (of one column)

      '''
      load_profile = []
      nr_month = device_utilisations[list(device_utilisations.keys())[0]].iloc[0].size
      nr_bags = device_utilisations[list(device_utilisations.keys())[0]][0].size
      prob_devices_all_months = [[[] for i in range(nr_bags)] for j in range(nr_month)]
      cons_devices = []
      nr_units_devices_all_months = [[] for j in range(nr_month)]
      
      for device, matrix in device_utilisations.items():
            cons_devices.append(device.electric_power)

            for j in range(nr_month):
                  nr_units_devices_all_months.append(matrix[j].sum())
                  for i in range(nr_bags):
                        prob_devices_all_months[j][i].append(matrix[j][i])
      
      cons_devices = pd.Series(cons_devices)
      curr_year = start_year
      curr_month = 1
      curr_day = 1
      
      for i in range(0, renewables_energy.size, nr_bags):
            load_profile = load_profile + (knapsack2d_for_given_unit(pd.DataFrame(prob_devices_all_months[j]),
                                                          cons_devices,
                                                          renewables_energy[i:i+nr_bags],
                                                          copy.copy(nr_units_devices_all_months[j])))
            

            if(curr_month == 12 and curr_day == (date(curr_year + 1, 1, 1) - date(curr_year, 12, 1)).days):
                  curr_year = curr_year + 1
                  curr_month = 1
                  curr_day = 1
            elif(curr_day == (date(curr_year, curr_month + 1, 1) - date(curr_year, curr_month, 1)).days):
                  curr_day = 1
                  curr_month = curr_month + 1
            else:
                  curr_day = curr_day + 1
            

      
      return pd.DataFrame(load_profile)


      
          
      