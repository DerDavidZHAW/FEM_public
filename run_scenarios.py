"""Run every meta-scenario of the scenario CSV named in scenarios/scenarios.py, one process each.

The data import fills module-level lists and dicts that nothing clears, so a second meta-scenario
in the same process would inherit the first one's plants. Each meta-scenario therefore runs in a
fresh interpreter through run_scenarios_hpc.py, as the Euler array does; a failure stops the batch.
"""
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

from scenarios.scenarios import meta_scenarios_list

SINGLE_SCENARIO_RUNNER = Path(__file__).resolve().parent / "run_scenarios_hpc.py"


def run_all(scenario_names: Iterable[str]) -> None:
    """Run the meta-scenarios in order, each in its own process; exit with a message at the first failure."""
    for scenario_name in scenario_names:
        exit_code = subprocess.run(
            [sys.executable, "-u", str(SINGLE_SCENARIO_RUNNER), "--scenario", scenario_name]
        ).returncode
        if exit_code != 0:
            sys.exit(
                f"Meta-scenario {scenario_name} failed with exit code {exit_code}; "
                "the remaining meta-scenarios were not run."
            )


if __name__ == "__main__":
    run_all(list(meta_scenarios_list))
