# -*- coding: utf-8 -*-

########################################################################################
# optimisation_graphs.py - In-built optimisation graph module for CLOVER.              #                      #
#                                                                                      #
# Author: Paul Harfouche                                                               #
# Copyright: Paul Harfouche, 2022                                                      #
# Date created: 09/06/22                                                               #
# License: Open source                                                                 #
########################################################################################
"""
optimisation_graphs.py - The optimisation graphs module for CLOVER.

In order to compare the results of multiple scenarios, this file will read the optimisation json
files and build graphs helping the user understand the outputs in a clearer way, in order
to make an accurate decision.
"""

import json
import pandas as pd
import matplotlib.pyplot as plt


# Cumulative_dataframe=pd.DataFrame(columns=["Scenario","Cumulative_cost","Cumulative_discount_energy","Cumulative_energy","Cumulative_ghgs","Cumulative_system_cost","cumulative_system_ghgs"])
# Environmental_appraisal_dataframe=pd.DataFrame(columns=["Scenario","Total_ghgs","Total_system_Ghgs"])
# Financial_appraisal_dataframe=pd.DataFrame(columns=["Scenario","New_equipment_cost","O&M_costs","Total_cost","Total_system_cost"])
# System_details_dataframe=pd.DataFrame(columns=(["Scenario","Final_PV_Size","Final_Storage_size"]))
# Technical_appraisal_dataframe=pd.DataFrame(columns=["Scenario","Blackouts","Discounted_Energy","Renewable_Energy","Renewable_Energy_Fraction","Storage_Energy","Total_Energy","Unmet_Energy","Unmet_Energy_Fraction"])

Criteria_dataframe = pd.DataFrame(
    columns=[
        "Cumulative_cost",
        "Cumulative_ghgs",
        "Cumulative_system_cost",
        "Cumulative_system_ghgs",
        "Emissions_intensity",
        "LCUE",
        "Renewable_fraction",
        "Total_cost",
        "Total_GHG",
        "Total_system_cost",
        "Total_system_GHGs",
        "Unmet_energy_fraction",
    ],
    index=["Offgrid", "Ongrid", "Hybrid_NEM_EDL", "Hybrid_NEM_DG", "Hybrid_NEM_DG_EDL"],
)
Criteria_dataframe.index.name = "Scenario"

# Opening JSON file
s1 = open("optimisation_output_1.json")
s2 = open("optimisation_output_2.json")
s3 = open("optimisation_output_3.json")
s4 = open("optimisation_output_4.json")
s5 = open("optimisation_output_5.json")

# returns JSON object as
# a dictionary
data_s1 = json.load(s1)
data_s2 = json.load(s2)
data_s3 = json.load(s3)
data_s4 = json.load(s4)
data_s5 = json.load(s5)

Criteria_dataframe.loc["Offgrid"] = pd.Series(
    {
        "Cumulative_cost": data_s1["system_appraisals"]["iteration_0"]["criteria"][
            "cumulative_cost"
        ],
        "Cumulative_ghgs": data_s1["system_appraisals"]["iteration_0"]["criteria"][
            "cumulative_ghgs"
        ],
        "Cumulative_system_cost": data_s1["system_appraisals"]["iteration_0"][
            "criteria"
        ]["cumulative_system_cost"],
        "Cumulative_system_ghgs": data_s1["system_appraisals"]["iteration_0"][
            "criteria"
        ]["cumulative_system_ghgs"],
        "Emissions_intensity": data_s1["system_appraisals"]["iteration_0"]["criteria"][
            "emissions_intensity"
        ],
        "LCUE": data_s1["system_appraisals"]["iteration_0"]["criteria"]["lcue"],
        "Renewable_fraction": data_s1["system_appraisals"]["iteration_0"]["criteria"][
            "renewables_fraction"
        ],
        "Total_cost": data_s1["system_appraisals"]["iteration_0"]["criteria"][
            "total_cost"
        ],
        "Total_GHG": data_s1["system_appraisals"]["iteration_0"]["criteria"][
            "total_ghgs"
        ],
        "Total_system_cost": data_s1["system_appraisals"]["iteration_0"]["criteria"][
            "total_system_cost"
        ],
        "Total_system_GHGs": data_s1["system_appraisals"]["iteration_0"]["criteria"][
            "total_system_ghgs"
        ],
        "Unmet_energy_fraction": data_s1["system_appraisals"]["iteration_0"][
            "criteria"
        ]["unmet_energy_fraction"],
    }
)
Criteria_dataframe.loc["Ongrid"] = pd.Series(
    {
        "Cumulative_cost": data_s2["system_appraisals"]["iteration_0"]["criteria"][
            "cumulative_cost"
        ],
        "Cumulative_ghgs": data_s2["system_appraisals"]["iteration_0"]["criteria"][
            "cumulative_ghgs"
        ],
        "Cumulative_system_cost": data_s2["system_appraisals"]["iteration_0"][
            "criteria"
        ]["cumulative_system_cost"],
        "Cumulative_system_ghgs": data_s2["system_appraisals"]["iteration_0"][
            "criteria"
        ]["cumulative_system_ghgs"],
        "Emissions_intensity": data_s2["system_appraisals"]["iteration_0"]["criteria"][
            "emissions_intensity"
        ],
        "LCUE": data_s2["system_appraisals"]["iteration_0"]["criteria"]["lcue"],
        "Renewable_fraction": data_s2["system_appraisals"]["iteration_0"]["criteria"][
            "renewables_fraction"
        ],
        "Total_cost": data_s2["system_appraisals"]["iteration_0"]["criteria"][
            "total_cost"
        ],
        "Total_GHG": data_s2["system_appraisals"]["iteration_0"]["criteria"][
            "total_ghgs"
        ],
        "Total_system_cost": data_s2["system_appraisals"]["iteration_0"]["criteria"][
            "total_system_cost"
        ],
        "Total_system_GHGs": data_s2["system_appraisals"]["iteration_0"]["criteria"][
            "total_system_ghgs"
        ],
        "Unmet_energy_fraction": data_s2["system_appraisals"]["iteration_0"][
            "criteria"
        ]["unmet_energy_fraction"],
    }
)
Criteria_dataframe.loc["Hybrid_NEM_EDL"] = pd.Series(
    {
        "Cumulative_cost": data_s3["system_appraisals"]["iteration_0"]["criteria"][
            "cumulative_cost"
        ],
        "Cumulative_ghgs": data_s3["system_appraisals"]["iteration_0"]["criteria"][
            "cumulative_ghgs"
        ],
        "Cumulative_system_cost": data_s3["system_appraisals"]["iteration_0"][
            "criteria"
        ]["cumulative_system_cost"],
        "Cumulative_system_ghgs": data_s3["system_appraisals"]["iteration_0"][
            "criteria"
        ]["cumulative_system_ghgs"],
        "Emissions_intensity": data_s3["system_appraisals"]["iteration_0"]["criteria"][
            "emissions_intensity"
        ],
        "LCUE": data_s3["system_appraisals"]["iteration_0"]["criteria"]["lcue"],
        "Renewable_fraction": data_s3["system_appraisals"]["iteration_0"]["criteria"][
            "renewables_fraction"
        ],
        "Total_cost": data_s3["system_appraisals"]["iteration_0"]["criteria"][
            "total_cost"
        ],
        "Total_GHG": data_s3["system_appraisals"]["iteration_0"]["criteria"][
            "total_ghgs"
        ],
        "Total_system_cost": data_s3["system_appraisals"]["iteration_0"]["criteria"][
            "total_system_cost"
        ],
        "Total_system_GHGs": data_s3["system_appraisals"]["iteration_0"]["criteria"][
            "total_system_ghgs"
        ],
        "Unmet_energy_fraction": data_s3["system_appraisals"]["iteration_0"][
            "criteria"
        ]["unmet_energy_fraction"],
    }
)
Criteria_dataframe.loc["Hybrid_NEM_DG"] = pd.Series(
    {
        "Cumulative_cost": data_s4["system_appraisals"]["iteration_0"]["criteria"][
            "cumulative_cost"
        ],
        "Cumulative_ghgs": data_s4["system_appraisals"]["iteration_0"]["criteria"][
            "cumulative_ghgs"
        ],
        "Cumulative_system_cost": data_s4["system_appraisals"]["iteration_0"][
            "criteria"
        ]["cumulative_system_cost"],
        "Cumulative_system_ghgs": data_s4["system_appraisals"]["iteration_0"][
            "criteria"
        ]["cumulative_system_ghgs"],
        "Emissions_intensity": data_s4["system_appraisals"]["iteration_0"]["criteria"][
            "emissions_intensity"
        ],
        "LCUE": data_s4["system_appraisals"]["iteration_0"]["criteria"]["lcue"],
        "Renewable_fraction": data_s4["system_appraisals"]["iteration_0"]["criteria"][
            "renewables_fraction"
        ],
        "Total_cost": data_s4["system_appraisals"]["iteration_0"]["criteria"][
            "total_cost"
        ],
        "Total_GHG": data_s4["system_appraisals"]["iteration_0"]["criteria"][
            "total_ghgs"
        ],
        "Total_system_cost": data_s4["system_appraisals"]["iteration_0"]["criteria"][
            "total_system_cost"
        ],
        "Total_system_GHGs": data_s4["system_appraisals"]["iteration_0"]["criteria"][
            "total_system_ghgs"
        ],
        "Unmet_energy_fraction": data_s4["system_appraisals"]["iteration_0"][
            "criteria"
        ]["unmet_energy_fraction"],
    }
)
Criteria_dataframe.loc["Hybrid_NEM_DG_EDL"] = pd.Series(
    {
        "Cumulative_cost": data_s5["system_appraisals"]["iteration_0"]["criteria"][
            "cumulative_cost"
        ],
        "Cumulative_ghgs": data_s5["system_appraisals"]["iteration_0"]["criteria"][
            "cumulative_ghgs"
        ],
        "Cumulative_system_cost": data_s5["system_appraisals"]["iteration_0"][
            "criteria"
        ]["cumulative_system_cost"],
        "Cumulative_system_ghgs": data_s5["system_appraisals"]["iteration_0"][
            "criteria"
        ]["cumulative_system_ghgs"],
        "Emissions_intensity": data_s5["system_appraisals"]["iteration_0"]["criteria"][
            "emissions_intensity"
        ],
        "LCUE": data_s5["system_appraisals"]["iteration_0"]["criteria"]["lcue"],
        "Renewable_fraction": data_s5["system_appraisals"]["iteration_0"]["criteria"][
            "renewables_fraction"
        ],
        "Total_cost": data_s5["system_appraisals"]["iteration_0"]["criteria"][
            "total_cost"
        ],
        "Total_GHG": data_s5["system_appraisals"]["iteration_0"]["criteria"][
            "total_ghgs"
        ],
        "Total_system_cost": data_s5["system_appraisals"]["iteration_0"]["criteria"][
            "total_system_cost"
        ],
        "Total_system_GHGs": data_s5["system_appraisals"]["iteration_0"]["criteria"][
            "total_system_ghgs"
        ],
        "Unmet_energy_fraction": data_s5["system_appraisals"]["iteration_0"][
            "criteria"
        ]["unmet_energy_fraction"],
    }
)
Criteria_dataframe.to_csv("Optimisation_Scenario_Criteria_Comparison.csv")

# PLOTTING:

Criteria_dataframe.plot(
    y=[
        "Cumulative_ghgs",
        "Cumulative_system_ghgs",
        "Total_GHG",
        "Total_system_GHGs",
        "Emissions_intensity",
    ],
    use_index=True,
    kind="bar",
    title="Emissions",
    xlabel="Scenario",
    ylabel="Emissions (kgCO2)",
)
Criteria_dataframe.plot(
    y=["Cumulative_cost", "Cumulative_system_cost", "Total_cost", "Total_system_cost"],
    use_index=True,
    kind="bar",
    title="Cost",
    xlabel="Scenario",
    ylabel="Cost ($)",
)
Criteria_dataframe.plot(
    y=["LCUE"], use_index=True, kind="line", title="LCUE", xlabel="Scenario"
)
Criteria_dataframe.plot(
    y=["Renewable_fraction", "Unmet_energy_fraction"],
    use_index=True,
    kind="line",
    title="Energy Fraction",
    xlabel="Scenario",
    ylabel="Fraction",
)
plt.show()
