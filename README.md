# CLOVER
CLOVER minigrid simulation and optimisation for supporting rural electrification in developing countries
CLOVER Quick Start Guide

This guide provides a very brief guide to using CLOVER as quickly as possible following the initial download. The file structure has two branches: 
	▪	a “Scripts” branch which contains Python files that the user runs and uses to generate outputs and perform simulations, 
	▪	a “Locations” branch that the describes individual locations and specifics of a given scenario being investigated. 

An example location, “Bahraich” in India, is included in the initial download for reference. New locations can be set up using the generic “New_Location” folder structure. Functions are stated below without explicit definition of their input arguments for brevity. 

	1.	General Setup
	  a.	In each file in the “Scripts” branch, update:
	    i.	“self.location” to the name of your location
    	ii.	“self.CLOVER_filepath” to the file path of your CLOVER folder
    	iii.	Update the file path syntax as necessary
    	iv.	Do this for all scripts
  	b.	In the “Locations” folder, copy a new version of the “New_Location” file structure and rename it to your chosen location
  	c.	Go to https://www.renewables.ninja/register to register a free account to gain your API token 
	2.	Establish your location
  	a.	In your location folder (e.g. “Bahraich”), open the “Location Data” folder
  	b.	Complete the “Location inputs.csv” template with the details of your location and your API token 
	3.	Get PV generation data
	  a.	In your location folder, open the “Generation” folder and then the “PV” folder
	  b.	Complete the “PV generation inputs.csv” template with the details of your location
	  c.	Run Solar().save_solar_output(gen_year) for each year of ten consecutive years
	    i.	This function requires the internet access to connect to the renewables.ninja site
	    ii.	The renewables.ninja site has a limit on the number of downloads in a given time period, so needs to be done manually for each year
	    iii.	Choose any period of ten years for which renewables.ninja has data
  	d.	Run Solar().total_solar_output(start_year) to combine your yearly solar outputs into a single file of twenty years
	4.	Get grid availability data
  	a.	In your location folder, open the “Generation” folder and then the “Grid” folder
  	b.	Complete the “Grid inputs.csv” template with the details of your location
    	i.	Grid profiles are a 1x24 matrix of hourly probabilities (0-1) that the grid is available
    	ii.	Input all grid profiles at the same time
  	c.	Run Grid().get_lifetime_grid_status() to automatically generate grid availability for all specified profiles
	5.	Get diesel backup generation data
  	a.	In your location folder, open the “Generation” folder and then the “Diesel” folder
  	b.	Complete the “Diesel generation inputs.csv” template with the details of your location
	6.	Get load data
  	a.	In your location folder, open the “Load” folder
  	b.	Complete the “Devices.csv” template with the details of your location
  	c.	In the “Devices utilisation” folder, complete the utilisation profiles for each device e.g. “light_times.csv”
      i.	Utilisation profiles are a 12x24 (monthly x hourly) matrix of probabilities that the specified device is in use in that hour
    	ii.	Each device in  “Devices.csv” must have a corresponding utilisation profile
  	d.	Run Load().number_of_devices_daily() to get the number of each device in the community on a given day
  	e.	Run Load().get_device_daily_profile() to get the daily utilisation profile (365x24 matrix) for each device
  	f.	Run Load().devices_in_use_hourly() to generate the number of devices in use for each hour
  	g.	Run Load().device_load_hourly() to get the load of each device
  	h.	Run Load().total_load_hourly() to get the total community load, segregated into “Domestic”, “Commercial” and “Public” demand types
	7.	Set up the energy system
	a.	In your location folder, open the “Simulation” folder
	b.	Complete the “Energy system inputs.csv” template with the details of your location
	c.	In your location folder, open the “Scenario” folder
	d.	Complete the “Scenario inputs.csv” template with the details of your location
	8.	Perform a simulation
	a.	Run Energy_System().simulation(start_year, end_year, PV_size, storage_size) with your chosen system
	b.	Record the outputs as a variable to investigate the outputs in more detail
	c.	Save the outputs using Energy_System().save_simulation(simulation_name,filename)
	d.	Open a saved simulation using Energy_System().open_simulation(filename)

For more information, contact Phil Sandwell (philip.sandwell@gmail.com)
