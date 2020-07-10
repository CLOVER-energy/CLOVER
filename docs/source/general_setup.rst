General setup
=============

Setting up CLOVER
-----------------

Once you have downloaded CLOVER you will need to set up the code to run
on your machine. You may need to install Anaconda and/or Spyder
(`available here <https://www.anaconda.com/distribution/>`__) in order
to run the code if you have not used Python in the past.

After the initial download, each script will need to be updated to match
your file path. This means that the modules that use other modules know
where to look when accessing them, otherwise they will give an error.
The scripts will also need to be updated to match the location you are
investigating, although throughout this guide we will use Bahraich as
the example location as all of the input data is provided in the CLOVER
download.

Dependencies
~~~~~~~~~~~~

CLOVER relies on the following packages so please ensure you have them
installed:

- pandas
- numpy
- scipy
- math
- requests
- json
- random
- datetime

Updating the file path and location
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each module (Python file, with a ``.py`` appendix) in the *Scripts*
branch has a line in the initial definition function which sets the
filepath of your CLOVER software and the location you are investigating.
It looks something like this:

::

   def __init__(self):
       self.location = 'Bahraich'
       self.CLOVER_filepath = '/***YOUR LOCAL FILE PATH***/CLOVER 4.0'


Our chosen location is Bahraich, so we do not need to update
*self.location*, but we do need to input our file path. In my case this
is saved in my documents (``Users/prs09``) in a folder called *CLOVER*,
so the entire file path (``Users/prs09/CLOVER``) needs to be inserted
here:

::

   self.CLOVER_filepath = '/Users/prs09/CLOVER'

Some modules contain the filepath in several places so make sure to
update all of them in each file. **Repeat this for all of the modules in
the scripts folder so that they are all ready to use.**

Troubleshooting
~~~~~~~~~~~~~~~

If you have issues when updating the file paths or locations, check the
following:

- Your file path contains a complete list of the folders where your CLOVER folder is saved
- You use the correct syntax for your operating system (e.g. “/” vs. “\\” when stating the file path)
- You have not added or removed slashes from the end of the file path
- You have used the correct quotation marks, and they match (e.g. “double” or ‘single’ quotation marks, not \`grave accent`)

Setting up a location
---------------------

Make a new location
~~~~~~~~~~~~~~~~~~~

Every location will require its own input files for the local
generation, load demand and other factors. The easiest way to make a new
location is to **copy the New_Location folder in the Locations folder
and rename it as your chosen location**. This ensures that your folder
structure is correctly set up, and maintains a copy of the generic
folder in case you want to add a new location in the future.

In this guide we will use the default example location, *Bahraich*,
which is a rural district in the state of Uttar Pradesh in northern
India.

Get a *Renewables.ninja* API token
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The *Solar* module gets solar generation data from another model
developed at Imperial College London called *Renewables.ninja* which can
provide renewables generation data for any location in the world at an
hourly resolution and over several years. CLOVER automatically
interfaces with the *Renewables.ninja* web interface but to do so you
will need to `register for an account at
https://www.renewables.ninja/register <https://www.renewables.ninja/register>`__\ **, and
use the API token in your version of CLOVER.** This is found in the
“Profile” section of your *Renewables.ninja* account. More information
about the API is available in the “Documentation” page on the website.

Establish your location
~~~~~~~~~~~~~~~~~~~~~~~

First you will need to provide details of the geographic location being
investigated. These are contained in the *Location inputs* file in the
*Location data* folder. You can edit these in the CSV file directly, but
here we will import the data and print it to the screen to see the input
data for Bahraich:

.. code:: ipython3

    import pandas as pd
    location_inputs = pd.read_csv("/Users/prs09/Documents/CLOVER/Locations/Bahraich/Location Data/Location inputs.csv")
    location_inputs.head(len(location_inputs)-1)




.. raw:: html

    <div>
    <style scoped>
        .dataframe tbody tr th:only-of-type {
            vertical-align: middle;
        }

        .dataframe tbody tr th {
            vertical-align: top;
        }

        .dataframe thead th {
            text-align: right;
        }
    </style>
    <table border="1" class="dataframe">
      <thead>
        <tr style="text-align: right;">
          <th></th>
          <th>Location</th>
          <th>Bahraich</th>
          <th>Location name</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>0</th>
          <td>Country</td>
          <td>India</td>
          <td>Location country</td>
        </tr>
        <tr>
          <th>1</th>
          <td>Time difference</td>
          <td>5.5</td>
          <td>Time difference vs. UTC</td>
        </tr>
        <tr>
          <th>2</th>
          <td>Community size</td>
          <td>100</td>
          <td>Number of households in community</td>
        </tr>
        <tr>
          <th>3</th>
          <td>Community growth rate</td>
          <td>0.01</td>
          <td>Fractional growth rate per year</td>
        </tr>
        <tr>
          <th>4</th>
          <td>Years</td>
          <td>20</td>
          <td>years of simulation</td>
        </tr>
        <tr>
          <th>5</th>
          <td>Latitude</td>
          <td>27.6</td>
          <td>degrees of latitude (North +ve)</td>
        </tr>
        <tr>
          <th>6</th>
          <td>Longitude</td>
          <td>81.6</td>
          <td>degrees of longitude (East +ve)</td>
        </tr>
      </tbody>
    </table>
    </div>


|

Some of these variables should be self-explanatory: the location
*Bahraich* is located in *India*. Others are less obvious: the time
period under consideration has a maximum of 20 years (it can be less
than this, but not more without modifying the code, so it is best to
leave this as it is). Here we assume there are 100 households in the
community with a household growth rate of 1% per year (0.01, expressed
as a fraction). This is also where the *Renewables.ninja* API token
should be copied so that other parts CLOVER can use it later - as this
is private I have not displayed mine in the table above.

Some are sensitive to positive or negative values, for example the time
difference of India compared to UTC is +5:30 and so the input is 5.5,
but countries west of UTC should use negative time differences
(e.g. Honduras would be -6). Latitude and longitude are defined as North
and East being positive and expressed as decimals; these are easily
obtainable from Google Maps, for example.
