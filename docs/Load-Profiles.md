This section provides information on the load profiles used within CLOVER, how to use them, and how they are processed.

## Process overview
CLOVER has the functionality to build load profiles from the bottom-up, summarised in the following steps:
1. Input the devices or appliances available in the community
2. Input the usage profile of each device throughout the day and year
3. Calculate the number of devices in use throughout the lifetime of the system
4. Calculate the daily utilisation profile of each device
5. Calculate the number of devices in use in every hour
6. Calculate the load profile of each device
7. Calculate the total load profile of the community.
This process is performed by the Load module, described in this section. The terms device and appliance are used interchangeably, meaning any piece of equipment that uses electricity, and specific meanings of other similar terms (for example usage and utilisation) will be made explicit where relevant.

CLOVER is also capable of using a pre-built load profile, though this must be in the correct format for CLOVER to correctly process it. If you have your own load data, or the stochastic generation that CLOVER carries out is not applicable to your use case, skip to the [Bringing your own load](#Bringing-your-own-load) section.

## Input files
### Devices YAML
CLOVER allows the user to include as many devices as desired in their load profile. These are inputted using the `devices.yaml` in the `inputs/load` directory for the given location, which can be edited directly to add and remove devices, or to change their properties. Let’s look at a device that has been included for Bahraich:
```yaml
---
################################################################################
# devices.yaml - Device input information.                                     #
#                                                                              #
# Author: Phil Sandwell, Ben Winchester                                        #
# Copyright: Phil Sandwell & Ben Winchester, 2021                              #
# Date created: 14/07/2021                                                     #
# License: Open source                                                         #
################################################################################

# A template device is provided below:
# - device: light
#   available: true
#   electric_power: 3
#   initial_ownership: 2
#   final_ownership: 4
#   innovation: 0.04
#   imitation: 0.5
#   type: domestic
#

- device: light
  available: true
  electric_power: 3
  initial_ownership: 2
  final_ownership: 4
  innovation: 0.04
  imitation: 0.5
  type: domestic
```

Each device contains a few parameters, some of which are more obvious than others, which are summarised here:
Variable | Explanation
--- | ---
`device` | Unique name of the device
`available` | Device is included (`true`, `yes` or `on`) or not (`false`, `no` or `off`) in the community load
`electric_power` | Device power consumption in Watts
`initial_ownership` | Average ownership of the device per household at the start of the time period
`final_ownership` | Average ownership of the device per household at the end of the time period
`innovation` | Parameter governing new households acquiring device
`imitation` | Parameter governing households copying others
`type` | Classification of the device as a `domestic`, `commercial` or `public` device

Take the example of the device `light` given above, which represents an LED bulb. It is available in the load profile (`available: true`), has a power rating of 3 W (`electric_power: 3`), and is classified as a Domestic load (`type: domestic`). At the start of the simulation period there is an average two LED bulbs per household (`initial_ownership: 2`) which, over time, increases to four bulbs per household (Final = 4.00) by the end of the considered time period - which we defined to be to 20 years in our `location.yaml` file.

The two remaining variables describe how quickly the average ownership per household increases: to generalise,
* Innovation describes how likely a household is to get a new appliance based on how much they like new things
* and Imitation describes how much a household is influenced by others already having the device.

#### Innovation and Imitation
These are inputs into a model of how quickly devices diffuse throughout the community (described in more detail later) but, simply put, the larger these numbers the quicker households will acquire them. These should be treated almost as qualitative measures: the values for a more desirable appliance like a television should be higher than (for example) a radio. You can use later outputs from the Load module to check that your appliance diffusion seems viable. If you do not want to include any demand growth over time by keeping the number of appliances the same throughout the simulation, it is possible to turn off this feature simply by setting the
values for Initial and Final to be the same, which will negate the Innovation and Imitation parameters (for example streetlight does this). Bear in mind that an increase in the number of households, defined when establishing the location, will result in an increase in the number of devices as the latter is calculated on the basis of the number of devices per household.

#### Kerosene
One of the devices, `kerosene`, is different from the others and is the only device which must remain present in the `devices.yaml` file. If you remove it, don't worry, you won't break CLOVER, but, if you wish to use `kerosene` again at a later stage, you're best simply keeping it in the file and settings its availability to `false`. The reason for the inclusion of this `kerosene` device in CLOVER is that CLOVER has the functionality to account for the usage of backup nonelectric lighting devices, such as kerosene lamps, which are used during periods when electricity is unavailable. This is useful when investigating electricity systems with less than 100% reliability, for example. This device is therefore necessary as an input for later functions and must be
present here, and have corresponding utilisation profiles, described later. If backup sources of non-electric lighting are not relevant to your investigation, set Initial = 0 and Final = 0 in the `devices.yaml` file to not consider it whilst still allowing the other functions to operate as expected. If a different non-electric lighting source is relevant, such as candles, complete the input data for that source but the name must remain as kerosene in the `devices.yaml` file.

With the above information in mind, simply complete your `devices.yaml` file for your chosen location.

### Device utilisations
CLOVER first considers the service that appliances provide as a necessary step in understanding the electricity demand of the community, rather than jumping directly to the latter. This is because two devices may provide 
very similar services, and the times of using those devices may be very similar, but the electricity requirements could be very different: LED and incandescent light bulbs, for example. By considering the demand for the service as a first step it is possible to more easily consider issues such as the usage of efficient, low-power devices which are becoming more common.

The utilisation of a device is defined to be the probability that a device is being used, given that it is present in the community. Utilisation values can vary hourly (throughout the day) and monthly (throughout the year) and must be between 0 (the device is never used in a specific hour) to 1 (it is always used). Utilisation profiles for each device are found in the `device_utilisation` folder within the `inputs/load` directory. Every device listed in the Devices input CSV **must** have a utilisation profile associated with it for CLOVER to calculate the load demand correctly and be named [device]_times. Even if a device has its availability set to `false` in the `devices.yaml` file, CLOVER will still use the utilisation profile but not eventually include the load in the final total community demand. If you do not want to include a device at all it is much easier to delete, or comment out (by inserting the `#` symbol at the start of every line, similar to the default example included), the device.

#### Device times input files
Each utilisation profile is a 24 x 12 matrix of utilisation values, corresponding to the hour of the
day for each month of the year. Let’s take a look at the example of light:
```bash
$ cat locations/Bahraich/inputs/load/device_utilisation/light_times.csv
0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39
0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39
0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39
0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39,0.39
0.39,0.39,0.39,0.39,0.48,0.56,0.46,0.39,0.39,0.39,0.39,0.39
0.39,0.39,0.47,0.48,0.23,0.12,0.28,0.45,0.53,0.57,0.40,0.39
0.58,0.48,0.22,0.00,0.00,0.00,0.00,0.00,0.00,0.05,0.37,0.53
0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00
0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00
0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00
0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00
0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00
0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00
0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00
0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00
0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00
0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00
0.47,0.08,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.39,0.74,0.76
0.93,0.93,0.54,0.51,0.23,0.03,0.00,0.26,0.79,0.93,0.93,0.93
0.93,0.93,0.93,0.93,0.93,0.93,0.90,0.93,0.93,0.93,0.93,0.93
0.93,0.93,0.93,0.93,0.93,0.93,0.93,0.93,0.93,0.93,0.93,0.93
0.93,0.93,0.93,0.93,0.93,0.93,0.93,0.93,0.93,0.93,0.93,0.93
0.88,0.88,0.88,0.88,0.88,0.88,0.88,0.88,0.88,0.88,0.88,0.88
0.83,0.83,0.83,0.83,0.83,0.83,0.83,0.83,0.83,0.83,0.83,0.83
```

This device utilisation profile, corresponding to our same LED bulb that we looked at in the [Devices YAML](#Devices-YAML) section, has a changing utilisation profile throughout the day: it is never used during the middle of the day (utilisation is 0.00), is very likely to be used in the evenings (up to 0.93), and some lights in the community are likely to be left on overnight (0.39). The utilisation of this device also changes throughout the year: in January (month 0) the utilisation at 18:00 is 0.93, but is 0.00 in July (month 6), owing to the changing times of sunset.

Making a representative utilisation profile will depend significantly on the specifics of your own investigation. These could come from primary data collection (indeed, the utilisation profile shown above did) or from your best estimate of what the demand for service is likely to be. Bear in mind that the probability that a device being used is an average over the entire community, so this should represent the utilisation of an “average” household without considering inter-household variations. To model device utilisation as the same throughout the year, use the same 24-value column for each of the 12 months.

For every device you have listed in the Devices input CSV, complete a corresponding utilisation profile matrix and ensure that is is called [device]_times.

## Generating load profiles
CLOVER contains in-built functionality for generating load profiles based on the information you have inputted in the above [Devices YAML](#Devices-YAML) and [Device utilisation](#Device-utilisations) input files. Every time you ask CLOVER to run a simulation or an optimisation, it will check to see whether all of the automated profiles that it needs have been generated and, if there are any missing, it will attempt to generate these for you.

### Profile-generation mode
CLOVER allows for load profiles to be generated without running a simulation or an optimisation. Sometimes this is useful in order to check load profiles before running potentially time-consuming operations. To do so, simply call CLOVER from the command-line interface without a simulation or optimisation argument given:
* ```bash
  python -m src.clover -l <location_name>
  ```
* or, if on a Linux machine,
  ```bash
  ./bin/clover.sh -l <location_name>
  ```
* or, if you have installed the clover-energy package:
  ```bash
  clover -l <location_name>
  ```
where you replace `<location_name>` with the name of your location.

## Bringing your own load
If you have your own pre-built load profile, you can use this in CLOVER. However, it will need to conform to the standard `.csv` profile which CLOVER is expecting:
* It will need to cover the entire length of your simulation period. If you are planning on simulating, e.g., 1 year, but you may cover 2 years at some point, it is recommended to generate and use a two-year profile in order to avoid errors;
* It will need to have headings that match up to what CLOVER is expecting, namely, the device types: `domestic`, `commercial` and `public`.

The first few lines of an example `total_load.csv` file, to which your load file will need to conform, are given below:

```csv
,domestic,commercial,public
0,389.0,0.0,500.0
1,340.0,0.0,500.0
2,644.0,0.0,500.0
3,385.0,0.0,0.0
4,381.0,200.0,0.0
5,370.0,0.0,0.0
6,740.0,200.0,0.0
7,80.0,700.0,0.0
8,320.0,1300.0,0.0
9,640.0,200.0,0.0
10,355.0,1300.0,0.0
11,1630.0,1300.0,0.0
12,1400.0,550.0,0.0
13,890.0,1850.0,0.0
14,365.0,1450.0,0.0
15,610.0,1150.0,0.0
16,375.0,2050.0,0.0
17,1074.0,1150.0,0.0
18,1734.0,350.0,500.0
```

If you encounter errors in generating your own profile, you can, as a first port of call, get CLOVER to auto-generate a profile based on your `device` information, and look for discrepancies. If you still encounter issues, and the standard error messages are unable to help you diagnose the issue, it is recommended that you contact the CLOVER development team.

## Troubleshooting
Most of the processes for generating load profile are automated but there are ample opportunities for simple mistakes when inputting the data which will cause errors. Solving the issues is normally simple but finding where they appear can be much harder, so if they come up:
* Check that you have used consistent spelling and capitalisation for your devices throughout as these are case sensitive, e.g. radio and Radio will be treated as two completely different devices;
* Check that your file names correspond to the correct devices and are in the correct formats, e.g. radio has a utilisation profile named radio_times
* Ensure that your input variables are in the correct format, for example `type` is either `domestic`, `commercial` or `public`;
* Ensure that your utilisation profiles are the correct size and format, and have the correct naming convention including the `.csv` suffix;
* And ensure that your device power is input in Watts (W), not kilowatts (kW).

CLOVER will attempt to give you as much useful information as possible, and so is likely to inform you of typos such as these, but, being aware of the potential errors may increase your chances of correctly diagnosing and addressing your problem. If you believe you have encountered an issue, please contact the CLOVER development team or raise an issue.