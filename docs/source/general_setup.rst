General setup
=============

Setting up CLOVER
-----------------

Once you have downloaded CLOVER you will need to set up the code to run on your machine. You may need to install Anaconda and/or Spyder (`available here <https://www.anaconda.com/distribution/>`__) in order to run the code if you have not used Python in the past.

Dependencies
~~~~~~~~~~~~

CLOVER relies on a series of Python packages in order to run. These can be installed using one of two methods:

Anaconda method
""""""""""""
To install using conda, from the root of the repository, run:

.. code-block:: bash

    conda install --file requirements.txt

Note, on some systems, Anaconda is unable to find the requirements.txt file. In these cases, it is necessary to use the full and absolute path to the file. E.G.,

.. code-block:: bash

    conda install --file C:\\Users\<User>\...\requirements.txt

Pip method
""""""""""""
To install using the in-build python package manager, from the root of the repository, run:

.. code-block:: bash

    python -m pip install -r requirements.txt

Setting up a location
---------------------

Make a new location
~~~~~~~~~~~~~~~~~~~

Every location will require its own input files for the local generation, load demand and other factors. Locations can be set up in one of two ways:

* By creating a new location from scratch and inputting all necessary information. To do this, call the new_location helper script with just the name of your new location:

  .. code:: bash

      python -m src.clover.scripts.new_location <new_location_name>

  or, if on a Linux machine,

  .. code:: bash

    ./bin/new_location.sh <new_location_name>

  or, if you have installed the clover-energy package:

  .. code:: bash

    new-clover-location <new_location_name>

* By basing the location on an existing location. To do this, call the new_location helper script with the --from-existing flag:

  .. code:: bash

    python -m src.clover.scripts.new_location <new_location_name> --from-existing <existing_location>

  or, if on a Linux machine,

  .. code:: bash

    ./bin/new_location.sh <new_location_name> --from-existing <existing_location>

  or, if you have installed the clover-energy package:

  .. code:: bash

    new-clover-location <new_location_name> --from-existing <existing_location>

If you have an existing location, you can base your new location on this one. An example location, “Bahraich,” is provided. To use this, simply append the :code:`--from-existing` flag when calling the new-location helper scripts.

Get a *Renewables.ninja* API token
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The *Generation* component gets solar generation data from another model developed at Imperial College London called *Renewables.ninja* which can provide renewables generation data for any location in the world at an hourly resolution and over several years. CLOVER automatically interfaces with the *Renewables.ninja* web interface but to do so you will need to `register for an account at https://www.renewables.ninja/register <https://www.renewables.ninja/register>`__\ **, and use the API token in your version of CLOVER.** This is found in the “Profile” section of your *Renewables.ninja* account. More information about the API is available in the “Documentation” page on the website.

Establish your location
~~~~~~~~~~~~~~~~~~~~~~~

First you will need to provide details of the geographic location being investigated. These are contained in the *location_inputs.yaml* file in the *inputs/location_data* folder. You can edit these in the CSV file directly, but here we will import the data and print it to the screen to see the input data for Bahraich:

.. code:: yaml

    ---
    ################################################################################
    # location_inputs.yaml - Location-specific parameters.                         #
    #                                                                              #
    # Author: Phil Sandwell, Ben Winchester                                        #
    # Copyright: Phil Sandwell & Ben Winchester, 2021                              #
    # Date created: 14/07/2021                                                     #
    # License: Open source                                                         #
    ################################################################################

    location: Bahraich # The name of the location
    country: India # Location country
    time_difference: 5.5 # Time difference, in hours, vs. UTC
    community_size: 100 # Initial number of households in community
    community_growth_rate: 0.01 # Fractional growth rate per year
    max_years: 20 # The maximum number of years of simulation
    latitude: 27.6 # Degrees of latitude (North +ve)
    longitude: 81.6 # Degrees of longitude (East +ve)


Some of these variables should be self-explanatory: the location *Bahraich* is located in *India*. Others are less obvious: the time period under consideration has a maximum of 20 years (it can be less than this, but not more without modifying the code, so it is best to leave this as it is). Here we assume there are 100 households in the community with a household growth rate of 1% per year (0.01, expressed as a fraction). This is also where the *Renewables.ninja* API token should be copied so that other parts CLOVER can use it later - as this is private I have not displayed mine in the table above.

Some are sensitive to positive or negative values, for example the time difference of India compared to UTC is +5:30 and so the input is 5.5, but countries west of UTC should use negative time differences (e.g. Honduras would be -6). Latitude and longitude are defined as North and East being positive and expressed as decimals; these are easily obtainable from Google Maps, for example.
