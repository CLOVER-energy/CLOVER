# -*- coding: utf-8 -*-
"""
Created on Tue Jun  7 18:08:29 2022

@author: pahar
"""

# Parse the grid inputs file.

# Grid inputs file:
#   The relative path to the grid inputs file.
GRID_INPUTS_FILE: str = os.path.join("generation", "grid_inputs.yaml")

def _parse_grid_inputs(
    energy_system_inputs: Dict[str, Any],
    inputs_directory_relative_path: str,
    logger: Logger,
    scenarios: List[Scenario],
) -> Tuple[
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    List[Dict[str, Any]],
    str,
]:

grid_inputs_filepath = os.path.join(
    inputs_directory_relative_path, GRID_INPUTS_FILE
)
grid_inputs = read_yaml(grid_inputs_filepath, logger)
if not isinstance(grid_inputs, list):
    raise InputFileError(
        "Grid inputs", "Grid input file is not of type `list`."
    )
logger.info("Grid inputs successfully parsed.")