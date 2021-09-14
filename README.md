# CLOVER

CLOVER minigrid simulation and optimisation for supporting rural electrification in developing countries.

## CLOVER Quick Start Guide

This guide provides a very brief introduction to get your CLOVER installation up and running as quickly as possible following the initial download. The file structure has two main branches: 
* a python branch, `scripts`, which contains CLOVER's source code which is used to perform simulations and generate outputs,
* and a data branch, `locations`, which contains informaiton describing the locations being modelled and contains parameters to outline the simulations and optimisations that should be run.

An example location, "Bahraich," in India, is included in the initial download for reference.

### Setting up your Python environment

CLOVER is a scientific package and, as such, uses Python packages that may not have come installed by default on your system. These packages can be easily installed, provided that you are connected to the internet, either using `pip`, the python package manager, or `conda`, a virtual-environment-based system. Instructions for `conda` are provided below:

#### Anaconda method

To install using `conda`, from the root of the repository, run:
```
conda install --file requirements.txt
```
Note, on some systems, Anaconda is unable to find the requirements.txt file. In these cases, it is necessary to use the full and absolute path to the file. E.G.,
```
conda install --file C:\\Users\<User>\...\requirements.txt
```

### Setting up a new location

New locations can be set up in one of two ways:
* By creating a new location from scratch and inputting all necessary information. To do this, call the `new_location` helper script with just the name of your new location:
  ```
  python -m clover.scripts.new_location <new_location_name>
  ```
  or, if on a Linux machine,
  ```
  ./bin/new_location.sh <new_location_name>
  ```
* By basing the location on an existing location. To do this, call the `new_location` helper script with the `--from-existing` flag:
  ```
  python -m clover.scripts.new_location <new_location_name> --from-existing <existing_location>
  ```
  or, if on a Linux machine,
  ```
  ./bin/new_location.sh <new_location_name> --from-existing <existing_location>
  ```
  
#### Updating an existing location

As part of the ongoing development of CLOVER, new features will be introduced. In order to incorporate these into existing CLOVER locations on your system, you can use the `new_location` script provided to update these locations:
```
python -m clover.scripts.new_location <location_name> --update
```
CLOVER will search through your location and attempt to replace missing files and include new files that have been brought in by an update.

### Renewables.ninja

Go to https://www.renewables.ninja/register to register a free account to gain your API token. This will be needed in order for CLOVER to correctly fetch and utilise solar profiles.

### Completing input files

Within your location folder you will find a subfolder named `inputs`. This contains the various input files which are used by CLOVER. These need to be completed in order for CLOVER to run. Some files are needed only for optimisations while some are needed for both optimisations and simulations.

#### Simulation and optimisation files

* Ensure that `inputs/generation/generation_inputs.yaml` contains your renewables.ninja API token and that the other parameters within the file are set correctly;
* Complete `inputs/location_data/location_inputs.yaml` with the details of your location;
* Complete the `inputs/generation/grid/grid_inputs.csv` template with the details of your location:
  * Grid profiles are a 1x24 matrix of hourly probabilities (0-1) that the grid is available,
  * Input all grid profiles at the same time;
* Complete `inputs/generation/diesel/diesel_inputs.yaml` with information about your diesel generator;
* Complete `inputs/load/devices.yaml`	with the devices that your location needs and the parameters as appropriate. **NOTE:** CLOVER considers kerosene as a mitigated source. The best practice for leaving kerosene out of your location is to set the `initial_ownership` and `final_ownership` of the kerosene device included by default to `0`.
* In the `inputs/load/device_utilisation` folder, complete the utilisation profiles for each device e.g. `light_times.csv`:
  * Utilisation profiles are a 12x24 (monthly x hourly) matrix of probabilities that the specified device is in use in that hour,
  * Each device in  “Devices.csv” must have a corresponding utilisation profile;
* In the `inputs/simulation` folder, complete the `energy_system.yaml` file with the details of your location's energy system;
* In the `inputs/simulation` folder, complete the `simulations.yaml` file with the details of the simulation bounds that you wish to run.

#### Optimisation-only files

* Complete the `inputs/impact/finance_inputs.yaml` with the financial details of your location;
* Complete the `inputs/impact/ghg_inpus.yaml` with the GHG-emission details of your location;
* Complete the `inputs/optimisation/optimisation_inputs.yaml` with the various parameters used to define the scope of the optimisations;

See the user guide, available within the repository, for more information on these input files.

### Running CLOVER

The operation of CLOVER can be broken down into two steps:
1. Fetching and generating profiles
2. Carrying out simulations and optimisations as appropriate.

When running a CLOVER simulation or optimisation, profiles will be generated if they are not present. However, these can also be generated on their own, without running a simultaion.

#### Profile generation

To generate the profiles on their own, run CLOVER with the name of the location only:
```
python -m clover --location <location_name>
```
or, on a Linux machine:
```
./bin/clover.sh --location <location_name>
```

#### Running a simulation

When running a CLOVER simulation, the size of the PV and storage systems needs to be specified on the comand-line:
```
python -m clover --location <location_name> --simulation --pv-system-size <float> --storage-size <float>
```
or, on a Linux machine:
```
./bin/clover.sh --location <location_name> --simulation --pv-system-size <float> --storage-size <float>
```
where `<float>` indicates that a floating point object, i.e., a number, is an acceptable input. The number should not have quotation marks around it.

##### Analysis

When running CLOVER simulations, in-built graph plotting can be carried out by CLOVER. To activate this functionality, simply use the `--analyse` flag when initialising a CLOVER simulation from the command-line interface.

***

For more information, contact Phil Sandwell (philip.sandwell@gmail.com) or Ben Winchester (benedict.winchester@gmail.com).
