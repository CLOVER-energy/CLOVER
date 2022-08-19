This section provides guidance on how to simulate an energy system. This will allow us to model the technical performance of an energy system of a given size and its ability to meet the load demanded by the community. At this stage we consider only the technical performance, rather than the financial or environmental considerations, which will come later in [Impact](Impact.md).

Before we can simulate a system we must first provide inputs for its technical performance and the conditions of the scenario under which we want it to operate.

## Energy system inputs
The inputs for the technical performance of the system are included in the `energy_system.yaml` file, which is located in the `inputs/simulation` directory of your location folder.

Let’s look at the inputs included for the Bahraich case study:
```yaml
---
################################################################################
# energy_system.yaml - Parameters for specifying a CLOVER energy system.       #
#                                                                              #
# Author: Phil Sandwell, Ben Winchester                                        #
# Copyright: Phil Sandwell & Ben Winchester, 2021                              #
# Date created: 14/07/2021                                                     #
# License: Open source                                                         #
################################################################################

ac_transmission_efficiency: 0.95 # Efficiency of AC distribution network
dc_transmission_efficiency: 0.95 # Efficiency of DC distribution network
battery: default_battery
# clean_water_tank: cold_water_tank
conversion:
  dc_to_ac: 0.95 # Conversion efficiency (0.0-1.0)
  dc_to_dc: 0.95 # Conversion efficiency (0.0-1.0)
  ac_to_dc: 0.8 # Conversion efficiency (0.0-1.0)
  ac_to_ac: 0.98 # Conversion efficiency (0.0-1.0)
diesel_generator: default_diesel
# heat_exchanger: default_heat_exchanger
# hot_water_tank: hot_water_tank
pv_panel: default_pv
# pvt_panel: default_pvt
# solar_thermal: default_solar_thermal
# water_pump: default_water_pump
```

**NOTE:** This file contains a series of new features which are currently under development, such as `heat_exchanger` or `clean_water_tank`. Whilst these lines __do__ work in CLOVER, they have not undergone the level of testing that has been carried out on the code which is publicly available and, as such, should be used with caution.

These variables control how the electricity system performs, in particular, which components to include from other files, and the various conversion efficiencies of the system. The table below describes in more
detail what each variable means:

Variable | Explanation
--- | ---
`ac_transmission_efficiency` | Transmission efficiency of an AC distribution network
`dc_transmission_efficiency` | Transmission efficiency of a DC distribution network
`battery` | The name of the battery that is being used. This battery must exist in the `battery_inputs.yaml` file
`conversion: dc_to_ac` | Conversion efficiency from DC power to an AC distribution network
`conversion: dc_to_dc` | Conversion efficiency from DC power to a DC distribution network
`conversion: ac_to_dc` | Conversion efficiency from AC power to an DC distribution network
`conversion: ac_to_ac` | Conversion efficiency from AC power to an AC distribution network
`diesel_generator` | The name of the diesel generator that is being used. This diesel generator must exist in the `diesel_inputs.yaml` file
`pv_panel` | The name of the PV panel being included. This must be defined in the `solar_generation_inputs.yaml` file

The various commented-out components correspond, as per the `battery`, `diesel_generator` and `pv_panel` variables, to components that must be defined in their respective files. In this way, the nature of the energy system can be constructed. Should you wish to change these parameters across simulations, it is recommended that you either use multiple locations, with duplicated input files, or contact the CLOVER development team to see what can be arranged.

### Battery inputs
The `battery_inputs.yaml` file contains information about the various batteries that you may wish to consider as part of your system. To select a specific battery for modelling, name it in the above `energy_system.yaml` [Energy System Inputs](#Energy-System-Inputs) section. Let's take a look at the file:

```yaml
---
################################################################################
# battery.yaml - Parameters for specifying a battery within CLOVER.            #
#                                                                              #
# Author: Phil Sandwell, Ben Winchester                                        #
# Copyright: Phil Sandwell & Ben Winchester, 2021                              #
# Date created: 12/08/2021                                                     #
# License: Open source                                                         #
################################################################################

- name: default_battery
  maximum_charge: 0.9 # State of charge (0.0 - 1.0)
  minimum_charge: 0.4 # State of charge (0.0 - 1.0)
  leakage: 0.004 # Fractional leakage per hour
  conversion_in: 0.95 # Conversion efficiency (0.0 - 1.0)
  conversion_out: 0.95 # Conversion efficiency (0.0 - 1.0)
  cycle_lifetime: 1500 # Expected number of cycles over lifetime
  lifetime_loss: 0.2 # Fractional loss over lifetime (0.0 - 1.0)
  c_rate_discharging: 0.33 # Discharge rate
  c_rate_charging: 0.33 # Charge rate
  costs:
    cost: 400 # [$/storage unit], [$/kWh] by default
    cost_decrease: 5 # [% p.a.]
    o&m: 10 # [$/storage unit], [$/kWh] by default
  emissions:
    ghgs: 110 # [kgCO2/kWh]
    o&m_ghgs: 5 # [kgCO2/kWh p.a.]
    ghg_decrease: 5 # [% p.a.]
```

The variables `maximum_charge` and `minimum_charge` refer to the maximum and minimum permitted states of charge of the battery: in this case the battery is allowed to cycle between 90% and 40% of its total capacity, resulting in a depth of discharge (DOD) of 50%, and meaning that 50% of the total installed battery capacity is actually usable by the system.

`Leakage` is the fraction of energy that leaks out of the battery every hour, in this case 0.004 or 0.4% of the energy presently stored in it per hour. `conversion_in` and `conversion_out` are the conversion efficiencies of energy being supplied to and from the battery respectively; when multiplied together these give the battery round-trip efficiency.

The `cycle_lifetime` refers to the number of charging and discharging cycles that the battery can be expected to perform over its lifetime, with the lifetime defined to be over when the battery has degraded by the `lifetime_loss` variable; in this case, the `lifetime_loss` is set to `0.2` (as is typical for this definition) and so the lifetime is over when the battery provides just 80% of its original capacity. The battery degradation is calculated by multiplying the `lifetime_loss` parameter by the energy throughput of the battery (at a given point in time) and then dividing by the expected cumulative energy throughput over the lifetime of the battery (the cycle lifetime multiplied by the depth of discharge and total capacity). This simplified method does not account for the effects of temperature or reduced cycling which may affect the lifetime of a battery in practice.

Finally for the battery parameters, `c_rate_discharging` and `c_rate_charging` are the C-rates for discharging and charging the batteries, measured as the maximum permitted fraction of the battery capacity that can be stored or supplied in one hour. These battery parameters can be taken from a datasheet provided by a battery manufacturer or used as indicative values in more general investigations. They are also agnostic to the type of battery technology being investigated, for example lead acid or lithium ion batteries. Some of these parameters will be dependent on one another: for example, a given battery being used with a higher DOD will likely have a lower cycle lifetime. These relationships are often available on battery datasheets (for example as performance curves) but need to be input manually and individually here. Similarly, higher C-rates will also likely result in lower cycle lifetimes.

### Simulation inputs
The simulation-inputs file specifies which simulations you wish to run:

```yaml
---
################################################################################
# simulations.yaml - Parameters for running a CLOVER simulations.              #
#                                                                              #
# Author: Phil Sandwell, Ben Winchester                                        #
# Copyright: Phil Sandwell & Ben Winchester, 2021                              #
# Date created: 14/07/2021                                                     #
# License: Open source                                                         #
################################################################################

- start_year: 0 # The start year for the simulation run.
  end_year: 20 # The end year for the simulation.
- start_year: 1
  end_year: 2
- start_year: 2
  end_year: 3
```

The file is structured as a long `YAML` list, where every entry in the list lays out the start and end years that you want to run for the simulations. In the above example, CLOVER would run three simulations: one for twenty years, starting at year 0, and two for one year each, beginning at the second (remember, Python begins indexing from zero) and third years respectively. These would be saved in the same output directory and distinguished by the names `simulation_1`, `simulation_2` and `simulation_3` respectively.

### Other simulation files
The other files contained within the folder are not used for simulating electricity systems, but they provide functionality for modelling hot- and clean-water systems. They are as follows:

File | Purpose
--- | ---
`heat_exchangers.yaml` | Defines a series of heat exchangers used within hot-water tanks
`tank_inputs.yaml` | Defines a series of water tanks, both hot- and clean-water-holding
`transmission_inputs.yaml` | Defines a series of components which, at an abstract level, are concerned with the transmission of some resource from some location to another. Currently, water pumps are the primary use of this file, though it is anticipated that transmission systems such as Pylons could be included here

## Scenario inputs
The inputs which describe the situation we are investigating are provided in the `scenario_inputs.yaml` file in the `inputs/scenario` directory of your location folder. These describe parameters such as the types of technologies that are being used in the system and the loads that are being met. Let’s take a look at the default inputs for Bahraich:

```yaml
---
################################################################################
# scenario_inputs.yaml - Parameters for specifying a scenario.                 #
#                                                                              #
# Author: Phil Sandwell, Ben Winchester                                        #
# Copyright: Phil Sandwell & Ben Winchester, 2021                              #
# Date created: 14/07/2021                                                     #
# License: Open source                                                         #
################################################################################

scenarios:
  - name: default
    pv: true # "true" or "false"
    battery: true # "true" or "false"
    diesel:
      mode: backup # "backup" or "disabled" currently supported
      backup:
        threshold: 0.1 # Maximum acceptible blackouts (0.0-1.0)
    grid: true # "true" or "false"
    grid_type: bahraich # The grid profile to use
    prioritise_self_generation: true # "true" or "false"
    demands:
      domestic: true # "true" or "false"
      commercial: true # "true" or "false"
      public: true # "true" or "false"
    distribution_network: dc # DC ("dc") or AC ("ac") distribution network
    resource_types:
      - electric_power
```

Many of these variables are straightforward, but the table below describes them explicitly.

Variable | Explanation
--- | ---
`name` | The unique name of the scenario. You can define multiple scenarios in this file, but each must have a unique name
`pv` | Whether solar PV is available (`true`, `on` or `yes`) or not (`false`, `off` or `no`)
`battery` | Whether battery storage is available (`true`, `on` or `yes`) or not (`false`, `off` or `no`)
`diesel` | Defines a diesel generator:
`diesel: mode` | The mode of operation of the generator, can be `backup`, where the generator is used to supplement blackouts in electricity supply, or `disabled` if you do not wish to look at diesel
`diesel: backup: threshold` | The blackout threshold which the diesel generator is used to achieve
`grid` | Whether the national grid is available (`true`, `on` or `yes`) or not (`false`, `off` or `no`)
`grid_type` | The name of the grid to use. These grids should be defined, as per the [Electricity generation](Electricity-Generation.md) chapter, within the grid-inputs csv file. The name selected here must match a name within that file
`prioritise_self_generation` | Whether to prioritise local generation (`true`, `on` or `yes`) or energy from the grid (`false`, `off` or `no`)
`demands` | Which demands to consider
`demands: domestic` | Whether Domestic loads are included in the load profile (`true`, `on` or `yes`) or not (`false`, `off` or `no`)
`demands: commercial` | Whether Commercial loads are included in the load profile (`true`, `on` or `yes`) or not (`false`, `off` or `no`)
`demands: public` | Whether Public loads are included in the load profile (`true`, `on` or `yes`) or not (`false`, `off` or `no`)
`distribution_network` | Whether an AC or DC distribtion network is used to transmit electricity
`resource_types` | Which resource types to consider. This can be `electric_power`, `cooling`, `hot_water` or `clean_water`. **NOTE:** If you are looking at other resource types, you will need to ensure that each of the input files are setup correctly for these.

## Running a simulation
To run a simulation, we can use the `-sim` or `--simulation` option on the command-line. When doing so, we will need to tell CLOVER what sizes of components we are looking at, namely, the installed capacity of PV panels and batteries. The other components, such as the diesel generator and grid, are sized automatically by CLOVER:

* If you have run a git clone to download CLOVER, you will run the code as before:
  ```bash
  python -m src.clover -sim <location_name> -pv <pv_system_size> -b <battery_system_size>
  ```
* or, on a linux machine,
  ```bash
  ./bin/clover.sh -sim <location_name> -pv <pv_system_size> -b <battery_system_size>
  ```
* or, if you have installed the `clover-energy` package:
  ```bash
  clover -sim <location_name> -pv <pv_system_size> -b <battery_system_size>
  ```

Provided all of your input files have been setup correctly, you will see a similar output to this displayed:

```bash
$ python -u -m src.clover -l debug -sim -pv 20 -b 5


        (((((*    /(((
        ((((((( ((((((((
   (((((((((((( ((((((((((((
   ((((((((((((*(((((((((((((       _____ _      ______      ________ _____
     *((((((((( ((((((((((((       / ____| |    / __ \ \    / /  ____|  __ \
   (((((((. /((((((((((/          | |    | |   | |  | \ \  / /| |__  | |__) |
 ((((((((((((((((((((((((((,      | |    | |   | |  | |\ \/ / |  __| |  _  /
 (((((((((((*  (((((((((((((      | |____| |___| |__| | \  /  | |____| | \ \
   ,(((((((. (  (((((((((((/       \_____|______\____/   \/   |______|_|  \_\
   .((((((   (   ((((((((
             /     (((((
             ,
              ,
               (
                 (
                   (



       Continuous Lifetime Optimisation of Variable Electricity Resources
                         Copyright Phil Sandwell, 2018
                                 Version 5.1.0                                 

                         For more information, contact
                   Phil Sandwell (philip.sandwell@gmail.com),
                    Hamish Beath (hamishbeath@outlook.com),
               or Ben Winchester (benedict.winchester@gmail.com)


A single CLOVER simulation will be run for debug
Verifying location information ................................    [   DONE   ]
Parsing input files ...........................................    [   DONE   ]
Generating necessary profiles
solar profiles: 100%|██████████████████████| 10/10 [00:00<00:00, 4767.88year/s]
electric load profiles: 100%|██████████████| 20/20 [00:02<00:00,  9.11device/s]
total load profile: 100%|████████████████| 20/20 [00:00<00:00, 1749.89device/s]
grid profiles: 100%|███████████████████████████| 5/5 [00:00<00:00, 17.39grid/s]
Generating necessary profiles .................................    [   DONE   ]
Beginning CLOVER simulation runs ..............................    
Running a simulation with:
- 20.0 kWp of PV
- 5.0 kWh of storage
simulations: 100%|███████████████████████| 3/3 [00:10<00:00, 10.15s/simulation]
Beginning CLOVER simulation runs ..............................    [   DONE   ]                                                         
Time taken for simulations: 0.331 s/year
Finished. See locations/debug/outputs for output files.
```

What CLOVER has done is mostly written here:
* CLOVER has checked that your location contains all of the files needed and that your command-line parameters match up correctly,
* The input files within your location have been parsed,
* If you haven't already downloaded your solar profiles by running CLOVER without the `-sim` flag, CLOVER will now go and fetch these from the renewables.ninja web interface. Otherwise, they will simply be read in and verified that they contain the correct information,
* The electric load profiles for your location will be generated and checked,
* along with the total load profile for the electric load of your system,
* CLOVER then runs simulations as per the `simulations.yaml` file. In our example, we set up three simulations to run, one for 20 years, and two for one-year each. Each of these will be shown as it runs with a progress bar as CLOVER iterates through the system performing an hourly calcultion,.
* CLOVER then displays the average time taken for each year of simulation time.

### Output files
When running a simulation, CLOVER will typically output two files: `simulation_output_{number}.csv` and `info_file.json`. We'll take a look at these files.

#### Simulation outputs CSV
This file gives the performance of the system at an hourly resolution, with the first 24 hours of the simulation shown here and rounded to three decimal places for convenience. The first 24 hours of the file:
```csv
,Load energy (kWh),Total energy used (kWh),Power consumed providing electricity (kWh),Unmet energy (kWh),Blackouts,Renewables energy used (kWh),Storage energy supplied (kWh),Grid energy (kWh),Diesel energy (kWh),Diesel times,Diesel fuel usage (l),Storage profile (kWh),PV energy supplied (kWh),Renewables energy supplied (kWh),Hourly storage (kWh),Electricity deficit (kWh),Dumped energy (kWh),Battery health,Households,Kerosene lamps,Kerosene mitigation
0,0.9073684210526316,0.9073684210526316,0.9073684210526316,0.0,0.0,0.0,0.9073684210526316,0.0,0.0,0.0,0.0,-0.9073684210526316,0.0,0.0,3.592631578947368,0.0,0.0,0.9999758035087719,100,0.0,78.0
1,0.9336842105263159,0.9336842105263159,0.9336842105263159,0.0,0.0,0.0,0.0,0.9336842105263159,0.0,0.0,0.0,0.0,0.0,0.0,3.5782610526315786,0.0,0.0,0.9999758035087719,100,0.0,83.0
2,0.9610526315789475,0.8684000398891967,0.8684000398891967,0.09265259168975082,1.0,0.0,0.8684000398891967,0.0,0.0,0.0,0.0,-0.9610526315789475,0.0,0.0,2.6955479685318555,0.0,0.0,0.9999526461743748,100,73.0,0.0
3,0.36631578947368426,0.36631578947368426,0.36631578947368426,0.0,0.0,0.0,0.0,0.36631578947368426,0.0,0.0,0.0,0.0,0.0,0.0,2.684765776657728,0.0,0.0,0.9999526461743748,100,0.0,75.0
4,0.37894736842105264,0.3988919667590025,0.3988919667590025,0.0,0.0,0.0,0.3988919667590025,0.0,0.0,0.0,0.0,-0.37894736842105264,0.0,0.0,2.2751347467920944,0.0,0.0,0.9999420090552613,100,0.0,77.0
5,0.40210526315789474,0.40210526315789474,0.40210526315789474,0.0,0.0,0.0,0.0,0.40210526315789474,0.0,0.0,0.0,0.0,0.0,0.0,2.266034207804926,0.0,0.0,0.9999420090552613,100,0.0,87.0
6,0.49578947368421056,0.49578947368421056,0.49578947368421056,0.0,0.0,0.0,0.0,0.49578947368421056,0.0,0.0,0.0,0.0,0.0,0.0,2.2569700709737064,0.0,0.0,0.9999420090552613,100,0.0,64.0
7,0.09473684210526316,0.09473684210526316,0.09473684210526316,0.0,0.0,0.09473684210526316,0.0,-0.0,0.0,0.0,0.0,0.06771185977829845,0.1624487018835616,0.1624487018835616,2.312268457479195,0.0,0.0,0.9999420090552613,100,0.0,0.0
8,2.605263157894737,2.605263157894737,2.605263157894737,0.0,0.0,2.605263157894737,0.0,-0.0,0.0,0.0,0.0,0.7159065115116547,3.321169669406392,3.321169669406392,2.98313056958535,0.0,0.0,0.9999420090552613,100,0.0,0.0
9,1.5526315789473686,1.5526315789473686,1.5526315789473686,0.0,0.0,1.5526315789473686,0.0,-0.0,0.0,0.0,0.0,6.010240719511533,7.562872298458902,7.562872298458902,3.75490259690407,0.0,0.0,0.9999420090552613,100,0.0,0.0
10,2.9473684210526314,2.9473684210526314,2.9473684210526314,0.0,0.0,2.9473684210526314,0.0,-0.0,0.0,0.0,0.0,7.720059803262435,10.667428224315067,10.667428224315067,4.499739040748676,0.0,0.023848495364839017,0.9999420090552613,100,0.0,0.0
11,3.242105263157895,3.242105263157895,3.242105263157895,0.0,0.0,3.242105263157895,0.0,-0.0,0.0,0.0,0.0,9.158089024684571,12.400194287842467,12.400194287842467,4.499739040748676,0.0,0.7657055934340669,0.9999420090552613,100,0.0,0.0
12,0.7842105263157896,0.7842105263157896,0.7842105263157896,0.0,0.0,0.7842105263157896,0.0,-0.0,0.0,0.0,0.0,12.44625823190339,13.230468758219178,13.230468758219178,4.499739040748676,0.0,0.7657055934340669,0.9999420090552613,100,0.0,0.0
13,1.8157894736842106,1.8157894736842106,1.8157894736842106,0.0,0.0,1.8157894736842106,0.0,-0.0,0.0,0.0,0.0,10.764873824203915,12.580663297888126,12.580663297888126,4.499739040748676,0.0,0.7657055934340669,0.9999420090552613,100,0.0,0.0
14,2.2315789473684213,2.2315789473684213,2.2315789473684213,0.0,0.0,2.2315789473684213,0.0,-0.0,0.0,0.0,0.0,8.489949701261715,10.721528648630136,10.721528648630136,4.499739040748676,0.0,0.7657055934340669,0.9999420090552613,100,0.0,0.0
15,1.936842105263158,1.936842105263158,1.936842105263158,0.0,0.0,1.936842105263158,0.0,-0.0,0.0,0.0,0.0,5.589879010319034,7.526721115582192,7.526721115582192,4.499739040748676,0.0,0.7657055934340669,0.9999420090552613,100,0.0,0.0
16,1.5157894736842108,1.5157894736842108,1.5157894736842108,0.0,0.0,1.5157894736842108,0.0,-0.0,0.0,0.0,0.0,1.9497472276856516,3.4655367013698624,3.4655367013698624,4.499739040748676,0.0,0.7657055934340669,0.9999420090552613,100,0.0,0.0
17,2.641052631578948,2.641052631578948,2.641052631578948,0.0,0.0,0.30684404514840186,0.0,2.334208586430546,0.0,0.0,0.0,0.0,0.30684404514840186,0.30684404514840186,4.481740084585682,0.0,0.0,0.9999420090552613,100,0.0,105.0
18,4.636842105263159,4.636842105263159,4.636842105263159,0.0,0.0,0.0,0.868370692074306,0.0,3.768471413188853,1.0,2.52,-4.636842105263159,0.0,0.0,3.5954424321730327,0.0,0.0,0.9999188525034727,100,0.0,339.0
19,2.385263157894737,0.868350582437226,0.868350582437226,1.516912575457511,1.0,0.0,0.868350582437226,0.0,0.0,0.0,0.0,-2.385263157894737,0.0,0.0,2.7127100800071147,0.0,0.0,0.999895696487941,100,336.0,0.0
20,2.88,2.88,2.88,0.0,0.0,0.0,0.7020678467112043,0.0,2.1779321532887956,1.0,2.52,-2.88,0.0,0.0,1.9997913929758822,0.16626262655463897,0.0,0.9998769746786954,100,0.0,339.0
21,3.215789473684211,3.215789473684211,3.215789473684211,0.0,0.0,0.0,0.0,3.215789473684211,0.0,0.0,0.0,0.0,0.0,0.0,1.9997539493573908,0.00796172195341227,0.0,0.9998769746786954,100,0.0,284.0
22,1.6947368421052633,0.0,0.0,1.6947368421052633,1.0,0.0,0.0,0.0,0.0,0.0,0.0,-1.6947368421052633,0.0,0.0,1.9997539493573908,0.8763132306499808,0.0,0.9998769746786954,100,146.0,0.0
23,1.2442105263157894,1.2442105263157894,1.2442105263157894,0.0,0.0,0.0,0.0,1.2442105263157894,0.0,0.0,0.0,0.0,0.0,0.0,1.9997539493573908,0.007999015797429676,0.0,0.9998769746786954,100,0.0,97.0
```

This file may look daunting if opened like this in a text editor! We'll open it in a spreadsheet editor of our choice.

| |Load energy (kWh) |Total energy used (kWh)|Power consumed providing electricity (kWh)|Unmet energy (kWh)|Blackouts|Renewables energy used (kWh)|Storage energy supplied (kWh)|Grid energy (kWh) |Diesel energy (kWh)|Diesel times|Diesel fuel usage (l)|Storage profile (kWh)|PV energy supplied (kWh)|Renewables energy supplied (kWh)|Hourly storage (kWh)|Electricity deficit (kWh)|Dumped energy (kWh)|Battery health    |Households|Kerosene lamps|Kerosene mitigation|
|------|------------------|-----------------------|------------------------------------------|------------------|---------|----------------------------|-----------------------------|------------------|-------------------|------------|---------------------|---------------------|------------------------|--------------------------------|--------------------|-------------------------|-------------------|------------------|----------|--------------|-------------------|
|0     |0.9073684210526316|0.9073684210526316     |0.9073684210526316                        |0.0               |0.0      |0.0                         |0.9073684210526316           |0.0               |0.0                |0.0         |0.0                  |-0.9073684210526316  |0.0                     |0.0                             |3.592631578947368   |0.0                      |0.0                |0.9999758035087719|100       |0.0           |78.0               |
|1     |0.9336842105263159|0.9336842105263159     |0.9336842105263159                        |0.0               |0.0      |0.0                         |0.0                          |0.9336842105263159|0.0                |0.0         |0.0                  |0.0                  |0.0                     |0.0                             |3.5782610526315786  |0.0                      |0.0                |0.9999758035087719|100       |0.0           |83.0               |
|2     |0.9610526315789475|0.8684000398891967     |0.8684000398891967                        |0.09265259168975082|1.0      |0.0                         |0.8684000398891967           |0.0               |0.0                |0.0         |0.0                  |-0.9610526315789475  |0.0                     |0.0                             |2.6955479685318555  |0.0                      |0.0                |0.9999526461743748|100       |73.0          |0.0                |
|3     |0.36631578947368426|0.36631578947368426    |0.36631578947368426                       |0.0               |0.0      |0.0                         |0.0                          |0.36631578947368426|0.0                |0.0         |0.0                  |0.0                  |0.0                     |0.0                             |2.684765776657728   |0.0                      |0.0                |0.9999526461743748|100       |0.0           |75.0               |
|4     |0.37894736842105264|0.3988919667590025     |0.3988919667590025                        |0.0               |0.0      |0.0                         |0.3988919667590025           |0.0               |0.0                |0.0         |0.0                  |-0.37894736842105264 |0.0                     |0.0                             |2.2751347467920944  |0.0                      |0.0                |0.9999420090552613|100       |0.0           |77.0               |
|5     |0.40210526315789474|0.40210526315789474    |0.40210526315789474                       |0.0               |0.0      |0.0                         |0.0                          |0.40210526315789474|0.0                |0.0         |0.0                  |0.0                  |0.0                     |0.0                             |2.266034207804926   |0.0                      |0.0                |0.9999420090552613|100       |0.0           |87.0               |
|6     |0.49578947368421056|0.49578947368421056    |0.49578947368421056                       |0.0               |0.0      |0.0                         |0.0                          |0.49578947368421056|0.0                |0.0         |0.0                  |0.0                  |0.0                     |0.0                             |2.2569700709737064  |0.0                      |0.0                |0.9999420090552613|100       |0.0           |64.0               |
|7     |0.09473684210526316|0.09473684210526316    |0.09473684210526316                       |0.0               |0.0      |0.09473684210526316         |0.0                          |-0.0              |0.0                |0.0         |0.0                  |0.06771185977829845  |0.1624487018835616      |0.1624487018835616              |2.312268457479195   |0.0                      |0.0                |0.9999420090552613|100       |0.0           |0.0                |
|8     |2.605263157894737 |2.605263157894737      |2.605263157894737                         |0.0               |0.0      |2.605263157894737           |0.0                          |-0.0              |0.0                |0.0         |0.0                  |0.7159065115116547   |3.321169669406392       |3.321169669406392               |2.98313056958535    |0.0                      |0.0                |0.9999420090552613|100       |0.0           |0.0                |
|9     |1.5526315789473686|1.5526315789473686     |1.5526315789473686                        |0.0               |0.0      |1.5526315789473686          |0.0                          |-0.0              |0.0                |0.0         |0.0                  |6.010240719511533    |7.562872298458902       |7.562872298458902               |3.75490259690407    |0.0                      |0.0                |0.9999420090552613|100       |0.0           |0.0                |
|10    |2.9473684210526314|2.9473684210526314     |2.9473684210526314                        |0.0               |0.0      |2.9473684210526314          |0.0                          |-0.0              |0.0                |0.0         |0.0                  |7.720059803262435    |10.667428224315067      |10.667428224315067              |4.499739040748676   |0.0                      |0.023848495364839017|0.9999420090552613|100       |0.0           |0.0                |
|11    |3.242105263157895 |3.242105263157895      |3.242105263157895                         |0.0               |0.0      |3.242105263157895           |0.0                          |-0.0              |0.0                |0.0         |0.0                  |9.158089024684571    |12.400194287842467      |12.400194287842467              |4.499739040748676   |0.0                      |0.7657055934340669 |0.9999420090552613|100       |0.0           |0.0                |
|12    |0.7842105263157896|0.7842105263157896     |0.7842105263157896                        |0.0               |0.0      |0.7842105263157896          |0.0                          |-0.0              |0.0                |0.0         |0.0                  |12.44625823190339    |13.230468758219178      |13.230468758219178              |4.499739040748676   |0.0                      |0.7657055934340669 |0.9999420090552613|100       |0.0           |0.0                |
|13    |1.8157894736842106|1.8157894736842106     |1.8157894736842106                        |0.0               |0.0      |1.8157894736842106          |0.0                          |-0.0              |0.0                |0.0         |0.0                  |10.764873824203915   |12.580663297888126      |12.580663297888126              |4.499739040748676   |0.0                      |0.7657055934340669 |0.9999420090552613|100       |0.0           |0.0                |
|14    |2.2315789473684213|2.2315789473684213     |2.2315789473684213                        |0.0               |0.0      |2.2315789473684213          |0.0                          |-0.0              |0.0                |0.0         |0.0                  |8.489949701261715    |10.721528648630136      |10.721528648630136              |4.499739040748676   |0.0                      |0.7657055934340669 |0.9999420090552613|100       |0.0           |0.0                |
|15    |1.936842105263158 |1.936842105263158      |1.936842105263158                         |0.0               |0.0      |1.936842105263158           |0.0                          |-0.0              |0.0                |0.0         |0.0                  |5.589879010319034    |7.526721115582192       |7.526721115582192               |4.499739040748676   |0.0                      |0.7657055934340669 |0.9999420090552613|100       |0.0           |0.0                |
|16    |1.5157894736842108|1.5157894736842108     |1.5157894736842108                        |0.0               |0.0      |1.5157894736842108          |0.0                          |-0.0              |0.0                |0.0         |0.0                  |1.9497472276856516   |3.4655367013698624      |3.4655367013698624              |4.499739040748676   |0.0                      |0.7657055934340669 |0.9999420090552613|100       |0.0           |0.0                |
|17    |2.641052631578948 |2.641052631578948      |2.641052631578948                         |0.0               |0.0      |0.30684404514840186         |0.0                          |2.334208586430546 |0.0                |0.0         |0.0                  |0.0                  |0.30684404514840186     |0.30684404514840186             |4.481740084585682   |0.0                      |0.0                |0.9999420090552613|100       |0.0           |105.0              |
|18    |4.636842105263159 |4.636842105263159      |4.636842105263159                         |0.0               |0.0      |0.0                         |0.868370692074306            |0.0               |3.768471413188853  |1.0         |2.52                 |-4.636842105263159   |0.0                     |0.0                             |3.5954424321730327  |0.0                      |0.0                |0.9999188525034727|100       |0.0           |339.0              |
|19    |2.385263157894737 |0.868350582437226      |0.868350582437226                         |1.516912575457511 |1.0      |0.0                         |0.868350582437226            |0.0               |0.0                |0.0         |0.0                  |-2.385263157894737   |0.0                     |0.0                             |2.7127100800071147  |0.0                      |0.0                |0.999895696487941 |100       |336.0         |0.0                |
|20    |2.88              |2.88                   |2.88                                      |0.0               |0.0      |0.0                         |0.7020678467112043           |0.0               |2.1779321532887956 |1.0         |2.52                 |-2.88                |0.0                     |0.0                             |1.9997913929758822  |0.16626262655463897      |0.0                |0.9998769746786954|100       |0.0           |339.0              |
|21    |3.215789473684211 |3.215789473684211      |3.215789473684211                         |0.0               |0.0      |0.0                         |0.0                          |3.215789473684211 |0.0                |0.0         |0.0                  |0.0                  |0.0                     |0.0                             |1.9997539493573908  |0.00796172195341227      |0.0                |0.9998769746786954|100       |0.0           |284.0              |
|22    |1.6947368421052633|0.0                    |0.0                                       |1.6947368421052633|1.0      |0.0                         |0.0                          |0.0               |0.0                |0.0         |0.0                  |-1.6947368421052633  |0.0                     |0.0                             |1.9997539493573908  |0.8763132306499808       |0.0                |0.9998769746786954|100       |146.0         |0.0                |
|23    |1.2442105263157894|1.2442105263157894     |1.2442105263157894                        |0.0               |0.0      |0.0                         |0.0                          |1.2442105263157894|0.0                |0.0         |0.0                  |0.0                  |0.0                     |0.0                             |1.9997539493573908  |0.007999015797429676     |0.0                |0.9998769746786954|100       |0.0           |97.0               |


Each column represents a variable which we may be interested in, while each row represents an hour of our simulation. In this way, we can either read the data directly from the file, or we can plot it using our chosen plotting tool. The column headers, and hence the various variables saved to this file, are explained here in more detail:

Variable | Explanation
--- | ---
Load energy (kWh) | Load energy demanded by the community
Total energy used (kWh) | Total energy used by the community
Unmet energy (kWh) | Energy that would have been needed to meet energy demand
Blackouts | Whether there was a blackout period (1) or not (0)
Renewables energy used (kWh) | Renewable energy used directly by the community
Storage energy supplied (kWh) | Energy supplied by battery storage
Grid energy (kWh) | Energy supplied by the grid network
Diesel energy (kWh) | Energy supplied by the diesel generator
Diesel times | Whether the diesel generator was on (1) or off (0)
Diesel fuel usage (l) | Litres of diesel fuel used
Storage profile (kWh) | Dummy profile of energy into (+) or out of (-) the battery
Renewables energy supplied (kWh) | Total renewable energy generation supplied to the system
Hourly storage (kWh) | Total energy currently stored in the battery
Dumped energy (kWh) | Energy dumped due to overgeneration when storage is full
Battery health | Measure of the relative health of the battery
Households | Number of households currently in the community
Kerosene lamps | Number of kerosene lamps used
Kerosene mitigation | Number of kerosene lamps mitigated through power availability

The majority of these variables describe the energy flows within the system, the sources that they come from and the amount of load energy that is being met. Others describe a binary characteristic of whether or not an hour experiences a blackout (defined as any shortfall in service availability during that hour) or if a diesel generator is being used, and others (such as the number of households, kerosene usage and mitigation, and storage profile) are used either in the computation of this function or later functions that rely on this output.

#### Info JSON file

This file provides details of the system that was simulated, including several of the input variables such as the time period being investigated and the solar and storage capacities we used. It also describes three new variables: Final PV size and Final storage size describe the relative capacities of the solar and battery components at the end of the simulation period after accounting for degradation, and Diesel capacity is the minimum diesel generator capacity (in 45  kW) necessary to supply power as a backup system:

```json
{
    "simulation_1": {
        "diesel_capacity": 18.0,
        "end_year": 20,
        "final_pv_size": 16.0,
        "final_storage_size": 3.182,
        "initial_pv_size": 20.0,
        "initial_storage_size": 5.0,
        "input_files": {
            "batteries": "locations/debug/inputs/simulation/battery_inputs.yaml",
            "converters": "locations/debug/inputs/generation/conversion_inputs.yaml",
            "devices": "locations/debug/inputs/load/devices.yaml",
            "diesel_inputs": "locations/debug/inputs/generation/diesel_inputs.yaml",
            "energy_system": "locations/debug/inputs/simulation/energy_system.yaml",
            "finance_inputs": "locations/debug/inputs/impact/finance_inputs.yaml",
            "generation_inputs": "locations/debug/inputs/generation/generation_inputs.yaml",
            "ghg_inputs": "locations/debug/inputs/impact/ghg_inputs.yaml",
            "grid_times": "locations/debug/inputs/generation/grid_times.csv",
            "location_inputs": "locations/debug/inputs/location_data/location_inputs.yaml",
            "optimisation_inputs": "locations/debug/inputs/optimisation/optimisation_inputs.yaml",
            "scenarios": "locations/debug/inputs/scenario/scenario_inputs.yaml",
            "simularion": "locations/debug/inputs/simulation/simulations.yaml",
            "solar_inputs": "locations/debug/inputs/generation/solar_generation_inputs.yaml",
            "transmission_inputs": "locations/debug/inputs/simulation/transmission_inputs.yaml"
        },
        "start_year": 0,
        "analysis_results": {
            "Average daily diesel energy supplied / kWh": 37.984,
            "Average daily dumped energy / kWh": 2.699,
            "Average daily energy consumption / kWh": 112.032,
            "Average daily grid energy supplied / kWh": 27.337,
            "Average daily renewables energy suppied / kWh": 81.651,
            "Average daily renewables energy used / kWh": 44.843,
            "Average daily stored energy supplied / kWh": 1.867,
            "Average daily unmet energy / kWh": 2.806,
            "Average pv generation / kWh/day": 5.0,
            "Blackouts": 0.1,
            "Cumulative pv generation / kWh/kWp": 36685.0,
            "Diesel times": 0.291,
            "Average grid availability / hours/day": 9.346
        }
    },
    "simulation_2": {
        "diesel_capacity": 6.0,
        "end_year": 2,
        "final_pv_size": 19.8,
        "final_storage_size": 4.883,
        "initial_pv_size": 20.0,
        "initial_storage_size": 5.0,
        "input_files": {
            "batteries": "locations/debug/inputs/simulation/battery_inputs.yaml",
            "converters": "locations/debug/inputs/generation/conversion_inputs.yaml",
            "devices": "locations/debug/inputs/load/devices.yaml",
            "diesel_inputs": "locations/debug/inputs/generation/diesel_inputs.yaml",
            "energy_system": "locations/debug/inputs/simulation/energy_system.yaml",
            "finance_inputs": "locations/debug/inputs/impact/finance_inputs.yaml",
            "generation_inputs": "locations/debug/inputs/generation/generation_inputs.yaml",
            "ghg_inputs": "locations/debug/inputs/impact/ghg_inputs.yaml",
            "grid_times": "locations/debug/inputs/generation/grid_times.csv",
            "location_inputs": "locations/debug/inputs/location_data/location_inputs.yaml",
            "optimisation_inputs": "locations/debug/inputs/optimisation/optimisation_inputs.yaml",
            "scenarios": "locations/debug/inputs/scenario/scenario_inputs.yaml",
            "simularion": "locations/debug/inputs/simulation/simulations.yaml",
            "solar_inputs": "locations/debug/inputs/generation/solar_generation_inputs.yaml",
            "transmission_inputs": "locations/debug/inputs/simulation/transmission_inputs.yaml"
        },
        "start_year": 1,
        "analysis_results": {
            "Average daily diesel energy supplied / kWh": 9.779,
            "Average daily dumped energy / kWh": 5.124,
            "Average daily energy consumption / kWh": 39.678,
            "Average daily grid energy supplied / kWh": 8.96,
            "Average daily renewables energy suppied / kWh": 86.608,
            "Average daily renewables energy used / kWh": 18.529,
            "Average daily stored energy supplied / kWh": 2.409,
            "Average daily unmet energy / kWh": 1.412,
            "Average pv generation / kWh/day": 5.0,
            "Blackouts": 0.1,
            "Cumulative pv generation / kWh/kWp": 36685.0,
            "Diesel times": 0.206,
            "Average grid availability / hours/day": 9.389
        }
    },
    "simulation_3": {
        "diesel_capacity": 6.0,
        "end_year": 3,
        "final_pv_size": 19.8,
        "final_storage_size": 4.883,
        "initial_pv_size": 20.0,
        "initial_storage_size": 5.0,
        "input_files": {
            "batteries": "locations/debug/inputs/simulation/battery_inputs.yaml",
            "converters": "locations/debug/inputs/generation/conversion_inputs.yaml",
            "devices": "locations/debug/inputs/load/devices.yaml",
            "diesel_inputs": "locations/debug/inputs/generation/diesel_inputs.yaml",
            "energy_system": "locations/debug/inputs/simulation/energy_system.yaml",
            "finance_inputs": "locations/debug/inputs/impact/finance_inputs.yaml",
            "generation_inputs": "locations/debug/inputs/generation/generation_inputs.yaml",
            "ghg_inputs": "locations/debug/inputs/impact/ghg_inputs.yaml",
            "grid_times": "locations/debug/inputs/generation/grid_times.csv",
            "location_inputs": "locations/debug/inputs/location_data/location_inputs.yaml",
            "optimisation_inputs": "locations/debug/inputs/optimisation/optimisation_inputs.yaml",
            "scenarios": "locations/debug/inputs/scenario/scenario_inputs.yaml",
            "simularion": "locations/debug/inputs/simulation/simulations.yaml",
            "solar_inputs": "locations/debug/inputs/generation/solar_generation_inputs.yaml",
            "transmission_inputs": "locations/debug/inputs/simulation/transmission_inputs.yaml"
        },
        "start_year": 2,
        "analysis_results": {
            "Average daily diesel energy supplied / kWh": 11.153,
            "Average daily dumped energy / kWh": 5.137,
            "Average daily energy consumption / kWh": 43.268,
            "Average daily grid energy supplied / kWh": 9.745,
            "Average daily renewables energy suppied / kWh": 90.618,
            "Average daily renewables energy used / kWh": 19.96,
            "Average daily stored energy supplied / kWh": 2.411,
            "Average daily unmet energy / kWh": 1.7,
            "Average pv generation / kWh/day": 5.0,
            "Blackouts": 0.1,
            "Cumulative pv generation / kWh/kWp": 36685.0,
            "Diesel times": 0.215,
            "Average grid availability / hours/day": 9.389
        }
    }
}
```

Here is the info file that has been outputted by our simulations. `.json` files are structured similar to a python dictionary. If you're not familiar with JSON files, it's recommended that you learn about how they, and Python dictionaries, are structured before running simulations.

Here, we can see that we have three top-level entries: `simulation_1`, `simulation_2` and `simulation_3` for each of the simulations that we ran. These then contain information about the system that was simulated. The information contained within this file has been calculated from the larger [Simulation outputs CSV](#Simulation-outputs-CSV) file and it's primary purpose is to allow you to quickly view your system, its performance, and to see whether the numbers are reasonable and what you expected. If the numbers seem wrong, then it is recommended that you check your input files. For instance, if the `Diesel times` variable seems too high, then your load may be too large, or your renewable capacity undersized.

### Understanding CLOVER's logs
CLOVER outputs a series of log files as it runs, which can be found in the automatically-generated `logs` directory. If you have downloaded the CLOVER source, or carried out a git clone, then this directory will already exist for you. If you have installed the `clover-energy` package, then, the first time you run a CLOVER script, this directory will be created for you.

CLOVER's logs are not meant to be the main source of information about your energy system, nor are they meant to supplement your outputs. Rather, they provide a useful tool for analysing where CLOVER may have encountered errors or problems along the way. If everything is working correctly, then you shouldn't need to read the logs on a regular basis.

#### Logging levels
CLOVER utilises several logging levels which you will encounter in the logs:
* `INFO` - Provides information about how CLOVER is operating, the decisions that have been made based on your various inputs, and generally documents the flow through CLOVER;
* `WARNING` - If you have set up your input files in such a way that CLOVER will be carrying out non-standard calculations, e.g., you have chosen to simulate a diesel generator connected to a grid only, then CLOVER will warn you. Why would it warn you? Well, in this instance, you would not be using CLOVER as originally intended: CLOVER is primarily a tool for optimising and simulating minigrids, and a diesel-and-grid scenario, where no PV panels or batteries are present, would not follow this main flow;
* `ERROR` - If CLOVER encounters an error, it will generally save as much helpful information as possible into the log files.

Let's take a brief look into one of CLOVER's log files:
```log
11/08/2022 05:40:14 PM: phil_clover: INFO: CLOVER run initiated. Options specified: --location debug -sim -pv 20 -b 5
11/08/2022 05:40:14 PM: phil_clover: INFO: Command-line arguments successfully parsed.
11/08/2022 05:40:14 PM: phil_clover: INFO: Command-line arguments successfully validated.
11/08/2022 05:40:14 PM: phil_clover: INFO: A single CLOVER simulation will be run for locatation 'debug'
11/08/2022 05:40:14 PM: phil_clover: INFO: Checking location debug.
11/08/2022 05:40:14 PM: phil_clover: INFO: Parsing input files.
11/08/2022 05:40:14 PM: phil_clover: INFO: No conversion file, skipping converter parsing.
11/08/2022 05:40:14 PM: phil_clover: INFO: Conversion inputs successfully parsed.
11/08/2022 05:40:14 PM: phil_clover: INFO: Kerosene device information found, using in-file information.
11/08/2022 05:40:14 PM: phil_clover: INFO: Device inputs successfully parsed.
11/08/2022 05:40:14 PM: phil_clover: INFO: No desalination scenarios files provided, skipping.
11/08/2022 05:40:14 PM: phil_clover: INFO: No hot-water scenario file provided, skipping.
11/08/2022 05:40:14 PM: phil_clover: INFO: Scenario inputs successfully parsed.
11/08/2022 05:40:14 PM: phil_clover: INFO: Optimisation inputs successfully parsed.
11/08/2022 05:40:14 PM: phil_clover: INFO: Optimisations file successfully parsed.
11/08/2022 05:40:14 PM: phil_clover: INFO: Energy system inputs successfully parsed.
...
```

Here, we can see some of the internal flow of CLOVER: it acknowledges the command-line arguments and checks that they are valid. It then checks the input files and begins parsing them, skipping the conversion inputs file, desalination and hot-water files as we are only looking at electrical systems here. This particular log file continues for over 300 lines, and yours is likely to be a similar length. For the most part, you will not need to access the logs on a regular basis, but they are useful for understanding how CLOVER operates.