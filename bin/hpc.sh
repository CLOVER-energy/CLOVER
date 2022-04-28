########################################################################################
# hpc.sh - Script for executing CLOVER as an array job on the HPC.                     #
#                                                                                      #
# Author: Ben Winchester                                                               #
# Copyright: Ben Winchester, 2021                                                      #
# Date created: 29/03/2022                                                             #
#                                                                                      #
# For more information, please email:                                                  #
#   benedict.winchester@gmail.com                                                      #
########################################################################################
#PBS -J 1-{NUM_RUNS}
#PBS -lwalltime={WALLTIME}:00:00
#PBS -lselect=1:ncpus=8:mem=11800Mb

echo -e "HPC array script executed"

# Load the anaconda environment
module load anaconda3/personal
source activate clover

cd $PBS_O_WORKDIR

echo -e "Running CLOVER HPC python script."
if python -m src.clover.scripts.hpc --runs {RUNS_FILE} --walltime {WALLTIME} {VERBOSE} ; then
    echo -e "CLOVER successfully run."
else
    echo -e "FAILED. See logs for details."
fi
