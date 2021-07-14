#!/bin/bash
########################################################################################
# new_location.sh - Wrapper script for the new-location generating script.             #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 13/07/2021                                                             #
#                                                                                      #
# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################

export PYTHONPATH=$PYTHONPATH:clover
python3 -m clover.scripts.new_location $@ \
    && echo "New location '$1' successfully created." \
    || echo "New location generation failed, see /logs for details."
