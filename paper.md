---
title: 'CLOVER: A modelling framework for sustainable community-scale energy systems'
tags:
  - energy access
  - minigrid
  - Python
  - renewable energy
  - sustainable development
authors:
  - name: Philip Sandwell
    orcid: 0000-0003-1117-5095
    affiliation: "1, 2"
    corresponding: true
  - name: Benedict Winchester
    orcid: 0000-0002-2880-1243
    affiliation: "2, 3"
  - name: Hamish Beath
    orcid: 0000-0002-5124-9143
    affiliation: "1, 2"
  - name: Jenny Nelson
    orcid: 0000-0003-1048-1330
    affiliation: "1, 2"
affiliations:
 - name: Department of Physics, Blackett Laboratory, Imperial College London, SW7 2AZ, United Kingdom
   index: 1
 - name: Grantham Institute - Climate Change and the Environment, Imperial College London, SW7 2AZ, United Kingdom
   index: 2
 - name: Department of Chemical Engineering, Imperial College London, SW7 2AZ, United Kingdom
   index: 3
date: 19 August 2022
bibliography: paper.bib
---

# Summary

Sustainable Development Goal 7 aims to provide sustainable, affordable, reliable and modern energy access to all by 2030 [@UN:2015]. In order for this goal to be achieved, sustainable energy interventions in developing countries must be supported with design tools which can evaluate the technical performance of energy systems as well as their economic and climate impacts.

CLOVER (Continuous Lifetime Optimisation of Variable Electricity Resources) is a software tool for simulating and optimising community-scale energy systems, typically minigrids, to support energy access in developing countries [@CLOVER]. CLOVER can be used to model electricity demand and supply at an hourly resolution, for example allowing users to investigate how an electricity system might perform at a given location. CLOVER can also identify an optimally-sized energy system to meet the needs of the community under specified constraints. For example, a user could define an optimum system as one which provides a desired level of reliability at the lowest cost of electricity. CLOVER can provide an insight into the technical performance, costs, and climate change impact of a system, and allow the user to evaluate many different scenarios to decide on the best way to provide sustainable, affordable and reliable electricity to a community.

CLOVER can be used on both personal computers and high-performance computing facilities. Its design separates its general framework (code, contained in a source `src` directory) from user inputs (data, contained in a directory entitled `locations`) which are specific to their investigations. The user inputs these data via a combination of `.csv` and `.yaml` files. CLOVER's straightforward command-line interface provides simple operation for both experienced Python users and those with little prior exposure to coding. An installable package, [clover-energy](https://pypi.org/project/clover-energy/), is available for users to download without needing to become familiar with GitHub's interface. Information about CLOVER and how to use it is available on the [CLOVER wiki pages](https://github.com/CLOVER-energy/CLOVER/wiki).

# Statement of need

CLOVER was developed to provide a robust techno-economic and climate impact analysis tool to support academics, practitioners and policymakers in evaluating sustainable energy interventions in developing countries. By providing an open-source alternative to proprietary minigrid design tools such as HOMER [@HOMER], CLOVER offers a more comprehensive analysis tool than common spreadsheet-based alternatives. CLOVER was designed to provide a fast, flexible and user-friendly software to assess energy systems at both short-term (hourly) and multi-year timescales under a wide variety of user-defined scenarios, constraints and optimisation conditions.

CLOVER can provide an insight into the technical performance, costs, and greenhouse gas emissions of a system, and allow the user to evaluate many different options to decide on the best way to provide sustainable, affordable and reliable electricity to the community. Its simulation functionality offers the user an insight into the hourly, daily, seasonal and multi-year technical performance of a system in response to changing electricity demands and varying renewable resources. Its optimisation process replicates the design process common in sustainable development settings by identifying optimum system design over short-term time horizons, but allowing the system to increase in capacity over its lifetime as the demand of the community grows in response to its economic development [@Sandwell:2017a].

# Main features

## Electricity supply
CLOVER can simulate a variety of electricity supply technologies:
- Solar generation is sourced from the Renewables.ninja API [@Renewables_Ninja] with the synthesis of the data described in @Pfenninger:2016;
- Battery storage, charged from solar, with user-defined characteristics for battery performance and lifetime to emulate many kinds of technologies;
- Diesel generation can be included as a source of power when no other source is available;
- Grid power can be treated as a primary or backup source of electricity with a user-defined availability profile.
These electricity sources can be included as the single source of electricity or in any combination as part of a hybrid system.

## Electricity demand
Users can generate electricity load profiles based on appliance ownership, usage patterns, power demands, and other device-specific information. Load profiles are based on the probability that individual user-specified appliances are in use, which can vary throughout the day and year, using processes described in @Sandwell:2016 and applied in @Chambon:2020. Any kind of electrical appliance and usage pattern can be defined by the user and ownership of appliances can be set to increase over time. Demands can be segregated into `domestic`, `commercial`, `public`, or other demand categories and included independently within the system. Alternatively users can provide their own hourly load profile, for example taken from monitored data.

## Simulation
CLOVER assesses the balance of energy sources and demands at an hourly resolution over a user-specified lifetime period. During this process data, including energy flows, battery state of charge, demand satisfaction, and times at which electricity is (un)available, are recorded.

The simulation functionality of CLOVER can be used to explore the technical performance of existing or theoretical case study systems. Data from the simulation process can be processed to give insight into how a system might perform over an average day, year, or over its lifetime. These could be used explore opportunities to maximise electricity utilisation by integrating additional user loads or investigating the impact of incremental increases in storage capacity for more efficient system design [@Sandwell:2017b].

## Optimisation
CLOVER can identify the optimum energy system, defined by a selected optimisation criterion, subject to any number of user-specified constraints (threshold criteria). Potential optimisation criteria include lowest cost, lowest greenhouse gas emissions, or others depending on the goals of the system; potential threshold criteria could set minimum allowable levels for the reliability of electricity supply, energy demand satisfaction, renewable energy penetration, or many more.

Users can specify the types of technologies available to include in the system and CLOVER uses an iterative heuristic search algorithm to identify the optimum combination and capacities to meet the needs of the community over its lifetime. A diagrammatic overview of this process is shown in @Beath:2021. The optimisation process has been used to explore the economic and greenhouse gas emissions impact of off-grid and grid-connected minigrids in India [@Sandwell:2017a] and the potential to offset diesel generation using solar energy in refugee camps in Rwanda [@BarandaAlonso:2021].

# Ongoing research and future development
CLOVER is being used as part of several ongoing research projects. These include:
- An assessment of the cost and climate impacts of optimally-sized grid-connected solar-battery systems in India under different levels of grid availability;
- A comparison of solar-battery minigrid sizing strategies for energy access in rural India;
- An evaluation of the costs and climate impacts of achieving energy access at the global scale.
CLOVER has previously been used for studies focusing on the impact of rurality and climate on minigrid design [@Few:2022] and as part of interdisciplinary frameworks for designing energy access interventions in displacement situations [@MattheyJunod:2022]. To date, CLOVER has been used as part of five PhD projects and by more than 10 MSc students. 

CLOVER remains under continuous development to increase its functionality and to address new and emerging research questions. Future releases are planned to include the ability to model thermal energy for heating and cooling, variable grid pricing, advanced diesel generator modelling, and more.

# Acknowledgements
The authors would like to gratefully acknowledge the support of the Grantham Institute - Climate Change and the Environment for PhD scholarships, the Engineering and Physical Sciences Research Council (EP/R511547/1, EP/R030235/1, EP/P003605/1, EP/P032591/1), the ClimateWorks Foundation, and Research England GCRF QR Funding.

# References
