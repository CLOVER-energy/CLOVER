import re
import subprocess
from pathlib import Path
from tqdm import tqdm

ENERGY_SYSTEM = Path("src/clover/simulation/energy_system.py")
BASE_CMD = [
    "python", "-m", "src.clover",
    "-l", "test_1.2",
    "-sim",
    "-pv", "2",
    "-s", "default",
    "-b", "0.0000001",
    "-a",
]

# read energy_system file
original_text = ENERGY_SYSTEM.read_text(encoding="utf-8")


pattern = re.compile(
    r"""
    weights\s*=\s*\[\s*
    scenario\.shifting_scenario\.renewables_weight\s*,\s*
    scenario\.shifting_scenario\.priority_weight\s*,\s*
    scenario\.shifting_scenario\.penalty_weight\s*,\s*
    scenario\.shifting_scenario\.device_count_weight\s*,?\s*
    \]
    """,
    re.VERBOSE | re.MULTILINE,
)

def replace_weights(text: str, new_weights: tuple[float, float, float, float]) -> str:
    if len(new_weights) != 4:
        raise ValueError("new_weights must have exactly 4 values")

    a, b, c, d = new_weights

    replacement = (
        "weights = [\n"
        f"{a},\n"
        f"{b},\n"
        f"{c},\n"
        f"{d},\n"
        "        ]"
    )

    new_text, n = pattern.subn(replacement, text, count=1)
    if n != 1:
        raise RuntimeError(
            f"Expected to replace 1 weights block, replaced {n}. "
            "Check pattern against energy_system.py."
        )
    return new_text

# test cases
cases = [
    ("all_even", (0.25, 0.25, 0.25, 0.25)),
    ("renewables_only", (1.0, 0.0, 0.0, 0.0)),
    ("renewables_prioritised", (0.4, 0.2, 0.2, 0.2)),
    ("priority_prioritised", (0.2, 0.4, 0.2, 0.2)),
    ("penalty_prioritised", (0.2, 0.2, 0.4, 0.2)),
    ("device_count_prioritised", (0.2, 0.2, 0.2, 0.4)),
    ("custom_1", (0.35, 0.25, 0.15, 0.25)),
]


try:
    for name, weights in cases:
        print(f"\n=== Running case: {name} | weights={weights} ===")


        patched = replace_weights(original_text, weights)
        ENERGY_SYSTEM.write_text(patched, encoding="utf-8")

        # run simulation
        result = subprocess.run(BASE_CMD, check=False)

        if result.returncode != 0:
            print(f"[WARN] Case {name} failed with code {result.returncode}")
            continue

finally:
    # restore original file
    ENERGY_SYSTEM.write_text(original_text, encoding="utf-8")
    print("\nRestored original load_shifting.py")
