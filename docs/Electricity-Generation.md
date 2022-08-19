This section provides an overview of how to set up the electricity
generation in CLOVER using its three modules solar, diesel and the
national grid network. Further modules with new technologies could be
added in the future to increase its functionality.

Solar
=====

Preparation
-----------

The *Solar* module allows the user to get solar generation data for
their location using the *Renewables.ninja* interface. Because this
module relies on this external source of data it acts differently from
other CLOVER modules, but ultimately returns the format of data that we
expect from all of the generation files. This module sits within the
*Generation* component. We will be completing several of the files
within that component.

First, complete the `generation_inputs.yaml` file in the generation
folder. Let's take a look at the inputs:

```yaml
---
################################################################################
# generation_inputs.yaml - General profile-generation parameters.              #
#                                                                              #
# Author: Phil Sandwell, Ben Winchester                                        #
# Copyright: Phil Sandwell & Ben Winchester, 2021                              #
# Date created: 14/07/2021                                                     #
# License: Open source                                                         #
################################################################################

# NOTE: The renewables.ninja API token must be entered under the `token` field.
# For more information, consult the User Guide, available within the repository
# and online.
#

end_year: 2016 # The absolute end year for gathering solar data.
start_year: 2007 # The absolute start year for gathering solar data.
token: "YOUR API TOKEN HERE" # renewables.ninja API token
```

The `start_year` and `end_year` parameters determine the bounds for the
environmental data which will be fetched from *Renwables.ninja*. In
general, it is safe to leave this as they are, unless there is a
particular data range that you are interested in. The important part of
this file to complete is your *Renewables.ninja* API token. You should
have set this up already. If not, follow the steps in the [General
Setup](General-Setup.md) section.

You can either enter your token into this file directly if you are
comfortable doing so. Or, you can run the helper script from the
command-line interface:

```bash
python -m src.clover.scripts.update_api_token --location <location_name> --token <your_renewables_ninja_api_token>
```

if you have downloaded the source code from Github, or

```bash
update-api-token --location <location_name> --token <your_renewables_ninja_api_token>
```

if you have installed the CLOVER package using Python\'s package
manager.

The other file to complete is the `solar_generation_inputs.yaml` file:

```yaml
---
################################################################################
# solar_generation_inputs.yaml - PV-data-generation parameters.                #
#                                                                              #
# Author: Phil Sandwell, Ben Winchester                                        #
# Copyright: Phil Sandwell & Ben Winchester, 2021                              #
# Date created: 14/07/2021                                                     #
# License: Open source                                                         #
################################################################################

panels:
  - name: default_pv
    azimuthal_orientation: 180 # [degrees from North]
    lifetime: 20 # [years] - Lifetime of the PV system.
    # reference_efficiency: 0.125 # [%] defined between 0 and 1
    # reference_temperature: 25 # [degrees Celcius]
    # thermal_coefficient: 0.0053 # [1 / degrees Celcius]
    tilt: 29 # [degrees above horizontal]
    type: pv # Panel type, either 'pv' or 'pv_t'
    costs:
      cost: 500 # [$/PV unit], [$/kWp] by default
      cost_decrease: 5 # [% p.a.]
      installation_cost: 100 # [$/PV unit], [$/kWp] by default
      installation_cost_decrease: 0 # [% p.a.]
      o&m: 5 # [$/kWp p.a.]
    emissions:
      ghgs: 3000 # [kgCO2/kWp]
      ghg_decrease: 5 # [% p.a.]
      installation_ghgs: 50 # [kgCO2/kW]
      installation_ghg_decrease: 0 # [% p.a.]
      o&m: 5 #[kgCO2/kWp p.a.]
```

Most of this information should be straightforward: we assume our panels
are south-facing (180° from North) and have a lifetime of 20 years,
typical for a solar panel and used by CLOVER to account for module
degradation. We also have stated that our panels will have a tilt (or
elevation) of 29° above the horizontal, or make a 29°\` angle compared
to flat ground (which would be 0°). This angle could (for example) be
the tilt of a roof that the panels are assumed to be located on, or it
could be the optimum angle that maximises total energy generation over
the course of a year (which can be found using the *Renewables.ninja*
web interface, or many other programmes).

The impact information for each panel needs to be entered here as well.
This consists of two main aspects: *economic impacts*, contained under
the `costs` header, and *environmental impacts*, specifically greenhouse
gas emissions, contained under the `emissions` header. For each of
these, the upfront *cost* and its decrease, installation *cost* and its
decrease, and operation and maintenance costs, denoted by `o&m`, need to
be filled out in order for any analysis or optimisations to be carried
out.

The `solar_generation_inputs.yaml` file is able to cope with multiple
designs of solar panel. These can then be selected later throughout the
code flow and are identified uniquely by the `name` field, so take care
to not create two panels with the same name to avoid errors occurring
when running CLOVER.

Visualising solar generation
\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~

The fetching of solar data from *Renewables.ninja* automatically saves a
CSV file for us, and we can look at the first day's worth of entries:

```python
$ python3
Python 3.7.11 (default, Jul 27 2021, 09:42:29) [MSC v.1916 64 bit (AMD64)] :: Anaconda, Inc. on <<OS>>
Type "help", "copyright", "credits" or "license" for more information.

>>> import pandas as pd  # The pandas module, used for processing CSV files throughout CLOVER
>>> solar_generation_2007 = pd.read_csv("/Users/prs09/Documents/CLOVER/Locations/Bahraich/Generation/PV/solar_generation_2007.csv",header=None)
>>> solar_generation_2007.columns = ['Hour','kW']
>>> print(solar_generation_2007[0:24])
```

:::parsed-literal
Hour kW 0 0 0.000 1 1 0.000 2 2 0.000 3 3 0.000 4 4 0.000 5 5 0.000 6 6
0.000 7 7 0.009 8 8 0.184 9 9 0.419 10 10 0.591 11 11 0.687 12 12 0.733
13 13 0.697 14 14 0.594 15 15 0.417 16 16 0.192 17 17 0.017 18 18 0.000
19 19 0.000 20 20 0.000 21 21 0.000 22 22 0.000 23 23 0.000
:::

As expected, we start getting solar generation from 6:00 (note that
Python begins counting from 0, so the hours of the day run from 0 to 23)
which peaks in the middle of the day and finishes by 17:00.

Extension and visualisation
---------------------------

For interest, let's see its cumulative generation over its lifetime,
rounded to the nearest kWh:

```python
>>> import numpy as np  # Numerical module used throughout CLOVER for processing data
>>> solar_generation_lifetime = pd.read_csv("/Users/prs09/Documents/CLOVER/Locations/Bahraich/Generation/PV/solar_generation_20_years.csv")
>>> total_generation = np.round(np.sum(solar_generation_lifetime['0.0']))
>>> print('Cumulative generation: ' + str(total_generation)+' kWh')
Cumulative generation: 36655.0 kWh
>>> print('Average generation: '+str(round(total_generation/(20*365)))+' kWh per day')
Average generation: 5.0 kWh per day
```

This panel is expected to produce 36.7 MWh of energy over its lifetime,
or around 5.0 kWh of energy per day - this is reasonable given the
location of the panel in a relatively sunny location in India.

We can quickly visualise its generation over the course of the first
year of its lifetime by taking the first 8760 hours (24 hours times 365
days) and plotting this as a heatmap. CLOVER\'s in-built analysis
generates this for you once you have run a simulation, but we can do it
here as well for practice:

```python
>>> solar_gen_year = solar_generation_lifetime.iloc[0:8760]['0.0']
>>> solar_gen_year = np.reshape(solar_gen_year.values,(365,24))
>>> import seaborn as sns
>>> import matplotlib.pyplot as plt
>>> import matplotlib as mpl
>>> mpl.rcParams['figure.dpi'] = 300
>>> g = sns.heatmap(
...     solar_gen_year,
...     vmin = 0.0,
...     vmax = 1.0,
...     cmap = 'Blues',
...     cbar_kws = {'label':'Power output (kW)'}
... )
>>> g.set(
...     xticks = range(0,24,2), xticklabels = range(0,24,2),
...     yticks = range(0,365,30), yticklabels = range(0,365,30),
...     xlabel = 'Hour of day', ylabel = 'Day of year',
...     title = 'Output of 1 kWp of solar capacity'
... )
>>> plt.xticks(rotation = 0)
>>> plt.tight_layout()
>>> plt.show()
```

![image](https://user-images.githubusercontent.com/8342509/168129257-dc6af2f0-1055-4a0e-81b9-25929a38a4ba.png)

As we might expect, the solar output varies throughout the year with
longer periods of generation during the summer months. Some days have
far less generation, potentially due to cloudy conditions. We can also
see the total daily generation over the course of the year by taking the
sum of the reshaped `solar_gen_year` object and plotting the result:

```python
>>> solar_daily_sums = pd.DataFrame(np.sum(solar_gen_year,axis=1))
>>> plt.plot(range(365),solar_daily_sums)
>>> plt.xticks(range(0,365,30))
>>> plt.yticks(range(0,9,2))
>>> plt.xlabel('Day of year')
>>> plt.ylabel('Energy generation (kWh per day)')
>>> plt.title('Daily energy generation of 1 kWp of solar capacity')
>>> plt.show()
```

![image](https://user-images.githubusercontent.com/8342509/168130421-78e64ce0-596f-4643-9751-4cf945f632ac.png)

Grid
====

Preparation
-----------

The *Grid* module simulates the availability of the national grid
network at the location, particularly when the grid is unreliable or has
variable availability throughout the day. CLOVER assumes that when the
grid is available it can provide an unlimited amount of power to satisfy
the needs of the community for the entire hour in question or, if
unavailable, no power can be drawn from it. The goal of the *Grid*
module is to provide an hourly profile of whether the grid is available
or not by using a user-specified availability profile (or several of
them, if many are to be investigated).

First, complete the `grid_times.csv` file in the `generation` folder.
Let's take a look at the inputs:

```python
>>> grid_times = pd.read_csv("locations/Bahraich/generation/grid_times.csv", header=0)
>>> print(grid_times)
    Name  none  all  daytime  eight_hours  bahraich
0      0     0    1        0         0.33      0.57
1      1     0    1        0         0.33      0.61
2      2     0    1        0         0.33      0.54
3      3     0    1        0         0.33      0.50
4      4     0    1        0         0.33      0.48
5      5     0    1        0         0.33      0.48
6      6     0    1        0         0.33      0.46
7      7     0    1        0         0.33      0.34
8      8     0    1        1         0.33      0.25
9      9     0    1        1         0.33      0.30
10    10     0    1        1         0.33      0.35
11    11     0    1        1         0.33      0.35
12    12     0    1        1         0.33      0.33
13    13     0    1        1         0.33      0.29
14    14     0    1        1         0.33      0.32
15    15     0    1        1         0.33      0.35
16    16     0    1        1         0.33      0.35
17    17     0    1        1         0.33      0.32
18    18     0    1        0         0.33      0.39
19    19     0    1        0         0.33      0.14
20    20     0    1        0         0.33      0.18
21    21     0    1        0         0.33      0.46
22    22     0    1        0         0.33      0.47
23    23     0    1        0         0.33      0.51
```

This file describes five grid availability profiles, with each of the
values corresponding to the probability that the grid will be available
in the hour of the day specified on the left. Taking the sum of those
values will give the average number of hours per day that the grid will
be available. The profiles we have here are:

-   `none` has no grid availability at all throughout the day,
    equivalent to not being connected to the grid
-   `all` has full grid availability at all times
-   `daytime` has grid availability throughout the day (8:00 until
    17:59) but never at night
-   `eight_hours` will provide approximately eight hours of power,
    randomly available throughout the day
-   `bahraich` is an example profile from data gathered from Bahraich
    district, where availability is higher in the early morning and late
    evening but lower during the daty and early evening.

You can add further grid profiles by adding additional columns in the
CSV file; they can have any name and values for grid availability must
be in the range 0-1 as they represent probabilities. Save this file
before moving on.

Diesel
======

Preparation
-----------

The *Diesel* module takes inputs in the same way as the grid and solar
modules, but it does not generate static profiles. Rather, it functions
reactively depending on the loads placed on the system and the
electricity which is available from the grid and various renewbales.
Currently, CLOVER diesel generation is treated as a backup source of
power when the other sources are unable to provide electricity, filling
in periods of blackouts after a simulation is complete to provide
greater levels of reliability. This means it can be used as a backup
source of power in a hybrid system (for example switching on
automatically when renewable generation is not sufficient) but not as
dispatchable generation coming on at user-specified times. This
functionality will be included in the next major update of CLOVER, and
you can follow the progress of this on the [Cycle
Charging](https://github.com/CLOVER-energy/CLOVER/milestone/3) milestone
page.

Most of the information concerning diesel generators is contained within
the `diesel_inputs.yaml` input file:

```yaml
---
################################################################################
# diesel_inputs.yaml - Diesel-generator input parameters.                      #
#                                                                              #
# Author: Phil Sandwell, Ben Winchester                                        #
# Copyright: Phil Sandwell & Ben Winchester, 2021                              #
# Date created: 14/07/2021                                                     #
# License: Open source                                                         #
################################################################################

diesel_generators:
  - name: default_diesel
    diesel_consumption: 0.4 # [litres per kW capacity per hour]
    minimum_load: 0.35 # Minimum capacity factor (0.0 - 1.0)
    costs:
      cost: 200 # [$/kW]
      installation_cost: 50 # [$/kW]
      installation_cost_decrease: 0 # [% p.a.]
      o&m: 20 # [$/kW p.a.]
      cost_decrease: 0 # [% p.a.]
    emissions:
      ghgs: 2000 # [kgCO2/kW]
      ghg_decreasae: 0 # [% p.a.]
      installation_ghgs: 50 # [kgCO2/kW]
      installation_ghg_decrease: 0 # [% p.a.]
```

This input file contains just two variables that are used throughout the
modelling along with other parameters that are used in determining the
impact that each diesel generator has on the system:

-   `diesel_consumption` refers to the hourly fuel consumption of the
    generator per kW of output, for example a generator providing 10 kW
    would use 4.0 litres of fuel per hour. CLOVER assumes that this fuel
    consumption is constant per kW of power being supplied, although in
    real systems diesel generators may have varying efficiencies
    dependent on the load factor;
-   `minimum_load` is the lowest load factor that the generator is
    permitted to operate at (for example to avoid mechanical issues or
    degradation), expressed as a fraction. For example, a 5 kW generator
    would be forced to provide at least 1.75 kW (5.0 kW x 0.35) of power
    to ensure it runs above the minimum load factor even if the load
    were less than this, with the remaining energy being dumped.

You can define multiple generators here, and distinguish them based on
the `name` field. Take care that each diesel generator defined has a
unique name.
