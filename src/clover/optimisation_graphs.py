# -*- coding: utf-8 -*-

########################################################################################
# optimisation_graphs.py - In-built optimisation graph module for CLOVER.              #                      #
#                                                                                      #
# Author: Paul Harfouche                                                               #
# Copyright: Paul Harfouche, 2022                                                      #
# Date created: 09/06/22                                                               #
# License: Open source                                                                 #
########################################################################################
"""
optimisation_graphs.py - The optimisation graphs module for CLOVER.

In order to compare the results of multiple scenarios, this file will read the optimisation json
files and build graphs helping the user understand the outputs in a clearer way, in order
to make an accurate decision.
"""

import json

# Opening JSON file
f = open('optimisation_output_1.json')

# returns JSON object as
# a dictionary
data = json.load(f)

# Iterating through the json
# list
for i in data['emp_details']:
	print(i)

# Closing file
f.close()
