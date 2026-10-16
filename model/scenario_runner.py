"""Run the meta-scenarios of a scenario CSV one process each, like the Euler array script.

The data import extends module-level lists and dicts of `data_prep/definitions_common.py` and
`definitions_TYNDP.py` once per sub-scenario, so a second meta-scenario in the same interpreter
would inherit the first one's plants. A fresh interpreter per meta-scenario, through
`run_scenarios_hpc.py --scenario <name>`, starts from an empty import state.
"""
import subprocess
import sys
from collections.abc import Callable, Iterable

SINGLE_SCENARIO_SCRIPT = "run_scenarios_hpc.py"


def run_in_subprocess(scenario_name: str) -> int:
    """Run one meta-scenario through `run_scenarios_hpc.py` in a new interpreter; return its exit code."""
    completed_process = subprocess.run(
        [sys.executable, "-u", SINGLE_SCENARIO_SCRIPT, "--scenario", scenario_name],
        check=False,
    )
    return completed_process.returncode


def run_meta_scenarios(
    scenario_names: Iterable[str],
    run_one: Callable[[str], int] = run_in_subprocess,
) -> list[str]:
    """Run the meta-scenarios in order, each through `run_one`; return the names that finished.

    Raises RuntimeError at the first non-zero exit code, naming the failed meta-scenario, so the
    following ones never run on top of a broken one unnoticed.
    """
    names = list(scenario_names)
    finished: list[str] = []
    for name in names:
        exit_code = run_one(name)
        if exit_code != 0:
            raise RuntimeError(
                f"meta-scenario {name!r} failed with exit code {exit_code}; "
                f"{len(finished)} of {len(names)} finished before it: {finished}"
            )
        finished.append(name)
    return finished
