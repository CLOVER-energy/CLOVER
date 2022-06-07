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
if ! ( conda env list | grep "clover" ) ; then
    echo -e "Creating anaconda virtual environment .........................    "
    if conda create -n "clover" python=3.7.12 ipython --yes ; then
        echo -e "Creating anaconda virtual environment .........................    [   DONE   ]"
    else
        echo -e "Creating anaconda virtual environment .........................    [  FAILED  ]"
	exit 1
    fi
else
    echo -e "Anaconda environment clover already exists, skipping."
fi

source activate clover

# Install the necessary packages.
echo -e "Installing necessary packages .................................    "
if python -u -m pip install -r requirements.txt ; then
    echo -e "Installing necessary packages .................................    [   DONE   ]"
else
    echo -e "Installing necessary packages .................................    [  FAILED  ]"
    exit 1
fi
