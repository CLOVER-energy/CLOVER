#!/usr/bin/env bash
########################################################################################
# test-clover.sh - Runs a series of tests across the system.                           #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
########################################################################################

echo "Running test suite: black, mypy, pylint and pytest."
echo -e "\e[1mIf a test requirement fails on python3.7, it will be re-run with 3.9."
echo -e "Running black...\e[0m"
python3.7 -m black src/clover || python3.9 -m black src/clover
echo -e "\e[1mBlack formatter done, see above for details.\e[0m"
echo -e "\e[1mRunning mypy...\e[0m"
python3.7 -m mypy src/clover || python3.9 -m mypy src/clover
echo -e "\e[1mMypy done, see above for details.\e[0m"
echo -e "\e[1mRunning pylint...\e[0m"
python3.7 -m pylint src/clover || python3.9 -m pylint src/clover
echo -e "\e[1mPylint done, see above for details.\e[0m"
echo -e "\e[1mRunning yamllint...\e[0m"
yamllint -c .yamllint-config.yaml locations/Bahraich
yamllint -c .yamllint-config.yaml src/
echo -e "\e[1mYamllint done, see above for details.\e[0m"
echo -e "\e[1mRunning pytest...\e[0m"
python3.7 -m pytest src/clover || python3.9 -m pytest src/clover
echo -e "\e[1mTest suite complete: see above stdout for details.\e[0m"
