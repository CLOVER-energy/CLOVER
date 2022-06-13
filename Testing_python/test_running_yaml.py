# -*- coding: utf-8 -*-
"""
Created on Tue May 31 12:44:16 2022

@author: pahar
"""

import yaml
with open (r'C:\Users\pahar\anaconda3\Lib\site-packages\clover\Testing_python\yaml_import_data_test.yaml') as file:
    documents= yaml.full_load(file)

for item, doc in documents.items():
    print(item,":",doc)
    