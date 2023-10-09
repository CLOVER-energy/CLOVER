# CLOVER

CLOVER minigrid simulation and optimisation for supporting rural electrification in developing countries.

[![DOI](https://zenodo.org/badge/476703736.svg)](https://zenodo.org/badge/latestdoi/476703736)

The quick start guide below provides step-by-step introductions for downloading, setting up, and using CLOVER. For full documentation containing further information about CLOVER and more detailed descriptions of its functionality, please [visit the Wiki](https://github.com/CLOVER-energy/CLOVER/wiki).

#### Table Of Contents

[Quick start guide](#quick-start-guide)

⏬ [Downloading CLOVER](#downloading-clover)
 * [Stable installation](#stable-installation)
   * [Upgrading](#upgrading)
 * [Downloading as a developer](#downloading-as-a-developer)

🐍 [Setting up your Python environment](#setting-up-your-python-environment)
  * [Anaconda method](#anaconda-method)
  * [Pip install](#pip-install)

⛅ [Setting up a new location](#setting-up-a-new-location)
  * [Updating an existing location](#updating-an-existing-location)

🌦️ [Renewables ninja](#renewables-ninja)

:memo: [Completing input files](#completing-input-files)
* [Simulation and optimisation files](#simulation-and-optimisation-files)
* [Optimisation only files](#optimisation-only-files)

🍀 [Running CLOVER](#running-clover)
* [Profile generation](#profile-generation)
* [Running a simulation](#running-a-simulation)
* [Running an optimisation](#running-an-optimisation)
* [Analysis](#analysis)

🎓 [Running CLOVER on Imperial College London's high-performance computers](#running-clover-on-imperial-college-londons-high-performance-computers)

# 🚤 Quick start guide

This guide provides a very brief introduction to get your CLOVER installation up and running as quickly as possible following the initial download. The file structure has two main branches:
* a python branch, `src`, which contains CLOVER's source code which is used to perform simulations and generate outputs,
* and a data branch, `locations`, which contains informaiton describing the locations being modelled and contains parameters to outline the simulations and optimisations that should be run.

An example location, "Bahraich," in India, is included in the initial download for reference.

## Downloading CLOVER

CLOVER can be downloaded from Github or installed via the Python package manager. If you intend to use CLOVER, but not develop or edit any of its code, then it is recommended that you install CLOVER from the Python package manager as this will guarantee that you install a stable version. If you intend to develop or edit any of the code contained within CLOVER as part of your research, then it is recommended that you download CLOVER directly from Github.

### Stable installation

For a stable version of CLOVER, it is recommended that you directly install the latest version of CLOVER via the `clover-energy` package. This can be installed using the python package manage, `pip`, in the usual way:
```bash
python -m pip install clover-energy
```

This will download and install the latest version of CLOVER into the current virtual environment that you have running. If you are using Anaconda, please note that this will install CLOVER only for the virtual environment that you are currently in, not for your system as a whole. CLOVER can now be run by calling `clover` from a terminal anywhere on your system, though you will need to set up a location in order for it to run successfully. See 'Setting up a new location' below.

This should install all of the relevant dependencies for CLOVER as well as providing four installable executable files: `new-clover-location`, `update-api-token`, `clover-hpc` and `clover`, which are described in more detail below.

Note, installing CLOVER in this way will install the package to your conda environment or local computer and will not provide you with easy access to the source code files. To develop CLOVER and have access to the source code, ensure that you download the code from GitHub.

#### Upgrading

To update the version of CLOVER that you have installed, from anywhere on your system, run:
```bash
python -m pip install clover-energy --upragde
```
This will fetch the latest stable version of CLOVER and install it into your current virtual environment.

### Downloading as a developer

To download the CLOVER source, with a view to editing and helping to develop the code, simply click the green `Code` button near the top of this page, copy the URL, and, in your local terminal, run `git clone <URL>` to get your local copy of CLOVER. From there, check out a new branch for any of your edits:
```
git checkout -b <new_branch_name>
```

### ⚠️ One-time download from Github

To download the CLOVER source code directly from Github, simply click the green `Code` button near the top of this page, and select `Download ZIP`. Once downloaded, unpack the zip file into a directory of your choice. You will now be able to run CLOVER from a terminal in this directory. Use the `cd` command to change the directory of your terminal to the extracted folder in order to run CLOVER.

**Note:** this is not recommended, as the version you will download will not be easily updatable from Github. It is recommended that you either [install as a developer](#downloading-as-a-developer) or [install with the Python package manage](#stable-installation).

## Setting up your Python environment

CLOVER is a scientific package and, as such, uses Python packages that may not have come installed by default on your system. These packages can be easily installed, provided that you are connected to the internet, either using `pip`, the python package manager, or `conda`, a virtual-environment-based system. Instructions for `conda` are provided below.

**Note:** If you have installed CLOVER following the instructions in the [Stable Installation](#stable-installation) section, then you do not need to install any dependencies, and you can skip straight to [Setting up a new location](#setting-up-a-new-location).

### Anaconda method

To install using `conda`, from the root of the repository, run:
```bash
conda install --file requirements.txt
```
Note, on some systems, Anaconda is unable to find the requirements.txt file. In these cases, it is necessary to use the full and absolute path to the file. E.G.,
```bash
conda install --file C:\\Users\<User>\...\requirements.txt
```

### Pip install
Whether you are in an anaconda environment, or are using your native Python, you can use Python's native package manager to install any dependencies. From the root of the repository, run:
```bash
python -m pip install -r requirements.txt
```

## Setting up a new location

New locations can be set up in one of two ways:
* By creating a new location from scratch and inputting all necessary information. To do this, call the `new_location` helper script with just the name of your new location.
  If you have installed CLOVER via a `git clone` command:
  ```bash
  python -m src.clover.scripts.new_location <new_location_name>
  ```

  if you are on a Linux machine, you can use the launch scripts provided:
  ```bash
  ./bin/new_location.sh <new_location_name>
  ```

  or, if you have installed the `clover-energy` package, either
  ```bash
  new-clover-location <new_location_name>
  ```
  or
  ```bash
  python -m new-clover-location <new_location_name>
  ```

* By basing the location on an existing location. To do this, call the `new_location` helper script with the `--from-existing` flag.
  If you have installed CLOVER via a `git clone` command:
  ```bash
  python -m src.clover.scripts.new_location <new_location_name> --from-existing <existing_location>
  ```

  if you are on a Linux machine, you can use the launch scripts provided with the additional `from-existing` flag:
  ```bash
  ./bin/new_location.sh <new_location_name> --from-existing <existing_location>
  ```

  or, if you have installed the `clover-energy` package, either
  ```bash
  new-clover-location <new_location_name> --from-existing <existing_location>
  ```
  or
  ```bash
  python -m new-clover-location <new_location_name> --from-existing <existing_location>
  ```


### Updating an existing location

As part of the ongoing development of CLOVER, new features will be introduced. In order to incorporate these into existing CLOVER locations on your system, you can use the `new_location` script provided to update these locations:
```
python -m src.clover.scripts.new_location <location_name> --update
```
or, if you have installed the `clover-energy` package, either
```
new-clover-location <location_name> --update
```
or
```bash
python -m new-clover-location <location_name> --update
```

CLOVER will search through your location and attempt to replace missing files and include new files that have been brought in by an update. Note, CLOVER will not correct missing or invalid fields within files, these must be corrected manually and the User Guide should be consulted for more information.

## Renewables ninja

Go to https://www.renewables.ninja/register to register a free account to gain your API token. This will be needed in order for CLOVER to correctly fetch and utilise solar profiles.

Once you have created a new location, you can input your API token using a CLOVER helper script.
If you have downloaded CLOVER using the `git clone` command:
```bash
python -m src.clover.scripts.update_api_token --location <location_name> --token <renewables_ninja_api_token>
```

or, if you have installed the `clover-energy` package, either
```bash
update-api-token --location <location_name> --token <renewables_ninja_api_token>
```

or
```bash
python -m update-api-token --location <location_name> --token <renewables_ninja_api_token>
```

## Completing input files

Within your location folder you will find a subfolder named `inputs`. This contains the various input files which are used by CLOVER. These need to be completed in order for CLOVER to run. Some files are needed only for optimisations while some are needed for both optimisations and simulations.

### Simulation and optimisation files

* Ensure that `inputs/generation/generation_inputs.yaml` contains your renewables.ninja API token and that the other parameters within the file are set correctly;
* Complete `inputs/location_data/location_inputs.yaml` with the details of your location;
* Complete the `inputs/generation/grid/grid_times.csv` template with the details of your location:
  * Grid profiles are a 1x24 matrix of hourly probabilities (0-1) that the grid is available,
  * Input all grid profiles at the same time;
* Complete `inputs/generation/diesel/diesel_inputs.yaml` with information about your diesel generator;
* Complete `inputs/load/devices.yaml`	with the devices that your location needs and the parameters as appropriate. **NOTE:** CLOVER considers kerosene as a mitigated source. The best practice for leaving kerosene out of your location is to set the `initial_ownership` and `final_ownership` of the kerosene device included by default to `0`.
* In the `inputs/load/device_utilisation` folder, complete the utilisation profiles for each device e.g. `light_times.csv`:
  * Utilisation profiles are a 12x24 (monthly x hourly) matrix of probabilities that the specified device is in use in that hour,
  * Each device in  “Devices.csv” must have a corresponding utilisation profile;
* In the `inputs/simulation` folder, complete the `energy_system.yaml` file with the details of your location's energy system;
* In the `inputs/simulation` folder, complete the `simulations.yaml` file with the details of the simulation bounds that you wish to run.

### Optimisation-only files

* Complete the `inputs/impact/finance_inputs.yaml` with the financial details of your location;
* Complete the `inputs/impact/ghg_inputs.yaml` with the GHG-emission details of your location;
* Complete the `inputs/optimisation/optimisation_inputs.yaml` with the various parameters used to define the scope of the optimisations;

See the user guide, available within the repository, for more information on these input files.

## Running CLOVER

The operation of CLOVER can be broken down into two steps:
1. Fetching and generating profiles
2. Carrying out simulations and optimisations as appropriate.

When running a CLOVER simulation or optimisation, profiles will be generated if they are not present. However, these can also be generated on their own, without running a simultaion.

### Profile generation

To generate the profiles on their own, run CLOVER with the name of the location only. If you have downloaded CLOVER from GitHub using the `git clone` command:
```bash
python -m src.clover --location <location_name>
```
or, if you are on a Linux machine,
```bash
./bin/clover.sh --location <location_name>
```
If you have installed the `clover-energy` package, run either
```bash
clover --location <location_name>
```
or
```bash
python -m clover --location <location_name>
```

### Running a simulation

When running a CLOVER simulation, the size of the PV and storage systems needs to be specified on the comand-line:
```bash
python -m src.clover --location <location_name> --simulation --pv-system-size <float> --storage-size <float>
```
or, if you are on a Linux machine,
```bash
./bin/clover.sh --location <location_name> --simulation --pv-system-size <float> --storage-size <float>
```
If you have installed the `clover-energy` package, either
```bash
clover --location <location_name> --simulation --pv-system-size <float> --storage-size <float>
```
or
```bash
python -m clover --location <location_name> --simulation --pv-system-size <float> --storage-size <float>
```
where `<float>` indicates that a floating point object, i.e., a number, is an acceptable input. The number should not have quotation marks around it.

### Running an optimisation

When running a CLOVER optimisation, the size of the PV and storage systems are optimised based on the information inputted in the `optimisation_inputs.yaml` file. To run an optimisation, simply call CLOVER from the command line:
```bash
python -m src.clover --location <location_name> --optimisation
```
or, if you are on a Linux machine:
```bash
./bin/clover.sh --location <location_name> --optimisation
```
If you have installed the `clover-energy` package, either
```bash
clover --location <location_name> --optimisation
```
or
```bash
python -m clover --location <location_name> --optimisation
```

### Analysis

When running CLOVER simulations, in-built graph plotting can be carried out by CLOVER. To activate this functionality, simply use the `--analyse` flag when initialising a CLOVER simulation from the command-line interface. You can run the analysis __without__ any plots by including the `--skip-analysis` flag.

## Running CLOVER on Imperial College London's high-performance computers

The operation of CLOVER can be broken down into the same steps as per running CLOVER on a local machine. These are described in [Running CLOVER](#running-clover). On Imperial's high-performance computers (HPCs), this functionality is wrapped up in such a way that a single entry point is provided for launching runs and a single additional input file is required in addition to those described in [Completing input files](#completing-input-files). Consult the user guide or wiki pages for more information on what is required of the input jobs file.

### Launching jobs

Once you have completed your input runs file, jobs are launched to the HPC by calling CLOVER's launch script from the command-line:
```bash
python -m src.clover.scripts.clover_hpc --runs <jobs_file>
```
or, if you have installed the `clover-energy` package, either
```bash
clover-hpc --runs <jobs_file>
```
or
```bash
python -m clover-hpc --runs <jobs_file>
```


***

For more information, contact Phil Sandwell (philip.sandwell@gmail.com) or Ben Winchester (benedict.winchester@gmail.com).
