# /usr/bin/python3
import os
import shutil
import subprocess

DESTINATION_DIRECTORY: str = "optimisation_outbox"
OPTIMISATION_NAME: str = "optimisation_output_*.json"


def main() -> None:
    """Script to prepare files for scp from hpc."""

    filenames = subprocess.run(
        ["find", "locations", "-name", OPTIMISATION_NAME],
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.decode()
    filenames = filenames.split("\n")
    filenames.remove("")

    for source_filename in filenames:
        destination_filename = os.path.join(DESTINATION_DIRECTORY, source_filename)

        # Make the directory structure within the outbox if it doesn't already exist
        if not os.path.isdir(os.path.dirname(destination_filename)):
            os.makedirs(os.path.dirname(destination_filename))

        # Copy across our file
        shutil.copy2(source_filename, destination_filename)


if __name__ == "__main__":
    main()
