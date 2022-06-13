def _parse_grid_inputs (
    grid_inputs: Dict[str, Any],
    inputs_directory_relative_path:str,
    logger: Logger,
    scenarios: List[Scenario],
) -> Tuple[
    Dict[]
]

# Parse the grid inputs file.
    grid_inputs_filepath = os.path.join(
        inputs_directory_relative_path,
        GRID_INPUTS_FILE,
    )
    grid_inputs = read_yaml(
        grid_inputs_filepath,
        logger,
    )
