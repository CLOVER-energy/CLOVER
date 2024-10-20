#!/usr/bin/env bash
########################################################################################
# test-clover.sh - Runs a series of tests across the system.                           #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
########################################################################################

echo "Running test suite: black, mypy, pylint and pytest."
echo -e "Running black...\e[0m"
python -m black src/clover --check --diff
echo -e "\e[1mBlack formatter done, see above for details.\e[0m"
echo -e "\e[1mRunning mypy...\e[0m"
python -m mypy src/clover
echo -e "\e[1mMypy done, see above for details.\e[0m"
echo -e "\e[1mRunning pylint...\e[0m"
python -m pylint src/clover
echo -e "\e[1mPylint done, see above for details.\e[0m"
echo -e "\e[1mRunning yamllint...\e[0m"
yamllint -c .yamllint-config.yaml locations/Bahraich
yamllint -c .yamllint-config.yaml src/
echo -e "\e[1mYamllint done, see above for details.\e[0m"
echo -e "\e[1mRunning pytest...\e[0m"
python -m pytest src/clover
echo -e "\e[1mTest suite complete: see above stdout for details.\e[0m"
