#!/usr/bin/env bash
########################################################################################
# test-clover.sh - Runs a series of tests across the system.                           #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
#                                                                                      #
# For more information, please email:                                                  #
#   benedict.winchester@gmail.com                                                      #
########################################################################################

echo "Running test suite: black, mypy, pylint and pytest."
echo -e "\e[1mRunning black...\e[0m"
black clover
echo -e "\e[1mBlack formatter done, see above for details...\e[0m"
echo -e "\e[1mRunning mypy...\e[0m"
mypy clover
echo -e "\e[1mMypy done, see above for details...\e[0m"
echo -e "\e[1mRunning pylint...\e[0m"
pylint clover
echo -e "\e[1mPylint done, see above for details...\e[0m"
echo -e "\e[1mRunning yamllint...\e[0m"
yamllint -c .yamllint-config.yaml locations/
echo -e "\e[1mYamllint done, see above for details...\e[0m"
echo -e "\e[1mRunning pytest...\e[0m"
pytest clover
echo -e "\e[1mTest suite complete: see above stdout for details.\e[0m"
