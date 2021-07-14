#!/bin/bash
########################################################################################
# clover - Wrapper script for CLOVER.                                                  #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 13/07/2021                                                             #
#                                                                                      #
# For more information, please email:                                                  #
#   philip.sandwell@gmail.com                                                          #
########################################################################################

export PYTHONPATH=$PYTHONPATH:clover
python3 -m clover $@ \
    && echo "CLOVER successfully executed." \
    || echo "CLOVER failed, see /logs for details. For more in-depth analysis, run \
    with python."
