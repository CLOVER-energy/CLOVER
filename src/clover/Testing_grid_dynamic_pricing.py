# -*- coding: utf-8 -*-
"""
Created on Wed Jun  8 15:50:56 2022

@author: pahar
"""
# import time 
# import fileparser 
# fileparser._parse_grid_inputs()

# print(fileparser._parse_grid_inputs())
# time.sleep(4)
# def _parse_grid_inputs(
#     inputs_directory_relative_path: str,
#     logger: Logger,
#     scenarios: List[Scenario],
# ) -> Tuple [
#     float,
#     Dict[str, float],
# ]:

#     grid_inputs_filepath c= os.path.join(
#         inputs_directory_relative_path, GRID_INPUTS_FILE
#     )
#     grid_inputs = read_yaml(grid_inputs_filepath, logger)
#     if not isinstance(grid_inputs, dict):
#         raise InputFileError(
#             "Grid inputs", "Grid input file is not of type `list`."
#         )
#     logger.info("Grid inputs successfully parsed.")

#     exchange_rate=grid_inputs["exchange_rate"] #why if we ADD [0] this doesn't work

#     # Determine the emissions
#     grid_emissions = grid_inputs["emissions"]
#     # Determine costs
#     diesel_5A_costs= grid_inputs["grid"][0]["costs"]
#     diesel_10A_costs= grid_inputs["grid"][1]["costs"]
#     edl_threshold_1=grid_inputs["grid"][2]["costs"]
#     edl_threshold_2=grid_inputs["grid"][3]["costs"]
#     edl_threshold_3=grid_inputs["grid"][4]["costs"]
#     edl_threshold_4=grid_inputs["grid"][5]["costs"]
#     edl_threshold_5=grid_inputs["grid"][6]["costs"]
#     thresholds=[]
#     for i in range (2,7):
#         thresholds.append(grid_inputs["grid"][i]["lower_bound"])    
#     return (
#         exchange_rate,
#         grid_emissions,
#         diesel_5A_costs,
#         diesel_10A_costs,
#         edl_threshold_1,
#         edl_threshold_2,
#         edl_threshold_3,
#         edl_threshold_4,
#         edl_threshold_5,
#         thresholds,
#     )

# def dynamic_pricing(
#     _parse_grid_inputs()
#     grid_inputs: Dict[str, Any],
#     logger: Logger,
#     *,
#     start_year: int = 0,
#     end_year: int = 20
# ) -> float: #after float they are all indented
#     daily_consumption_edl=availability_edl*grid_inputs[cost]

df = pd.read_csv ("load_household_lebanon.csv",header=0)
df.columns=["Hour","domestic","commercial","public"]
f = pd.DataFrame()
print(f)
for i in range (0,20):
    for j in range (0,365):
          for k in range (0,24)
              if load_household_lebanon(k+24) <1.
