#!/bin/bash
########################################################################################
# hpc-setup.sh - HPC setup script for CLOVER.                                          #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2022                                                      #
# Date created: 02/04/2022                                                             #
#                                                                                      #
# For more information, please email:                                                  #
#   benedict.winchester@gmail.com                                                      #
########################################################################################

# Load the anaconda program
module load anaconda3/personal

# Create the required environment
echo -e "Creating anaconda virtual environment .........................    "
if source create -n "py37" python=3.7.10 ipython ; then
    echo -e "Creating anaconda virtual environment .........................    [   DONE   ]"
else
    echo -e "Creating anaconda virtual environment .........................    [  FAILED  ]"
fi
source activate py37

# Install the necessary packages.
echo -e "Installing necessary packages .................................    "
if python -u -m pip install -r requirements.txt ; then
    echo -e "Installing necessary packages .................................    [   DONE   ]"
else
    echo -e "Installing necessary packages .................................    [  FAILED  ]"
fi
