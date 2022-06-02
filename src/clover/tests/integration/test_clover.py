#!/usr/bin/python3
########################################################################################
# test_clover.py - Integration tests for CLOVER.                                       #
#                                                                                      #
# Author: Ben Winchester, Phil Sandwell                                                #
# Copyright: Ben Winchester, 2022                                                      #
# Date created: 08/03/2022                                                             #
# License: Open source                                                                 #
########################################################################################
"""
test_clover.py - Integration tests for the CLOVER Python package.

CLOVER is constantly under development by researchers, NGOs, and private companies. To
ensure reproducibility across different branches and versions of CLOVER, the integration
tests below are run as part of the enforcement which is carried out when contributing to
CLOVER. They also provide a useful tool for ensuring that any changes made locally do
not affect the overall running of the code.

"""

import unittest

import pytest

from unittest import mock

from ...__main__ import main as clover_main
