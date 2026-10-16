"""Unit tests for run_scenarios.py: each meta-scenario runs in its own Python process, and a failure stops
the batch.

The tests replace the single-scenario runner with a small script that records its process id (no
model, no solver), so they prove that real separate processes are started, in order.
"""
import importlib
import os
import sys
from pathlib import Path

import pytest

import scenarios.scenarios

FAKE_RUNNER = """
import os
import sys

scenario = sys.argv[sys.argv.index("--scenario") + 1]
with open(os.environ["FAKE_RUNNER_LOG"], "a") as log:
    log.write(f"{os.getpid()} {scenario}\\n")
sys.exit(3 if scenario == "any_broken" else 0)
"""


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The run_scenarios module with the child script swapped for the fake, plus the fake's log file."""
    # With no meta-scenarios listed, importing the module runs nothing.
    monkeypatch.setattr(scenarios.scenarios, "meta_scenarios_list", {})
    monkeypatch.delitem(sys.modules, "run_scenarios", raising=False)
    module = importlib.import_module("run_scenarios")
    fake_script = tmp_path / "fake_runner.py"
    fake_script.write_text(FAKE_RUNNER)
    monkeypatch.setattr(module, "SINGLE_SCENARIO_RUNNER", fake_script)
    log = tmp_path / "calls.txt"
    monkeypatch.setenv("FAKE_RUNNER_LOG", str(log))
    return module, log


def _calls(log: Path) -> list[list[str]]:
    """The (process id, scenario) pairs the fake runner recorded, in order."""
    return [line.split() for line in log.read_text().splitlines()]


class TestRunAll:
    def test_each_meta_scenario_runs_in_its_own_process_in_order(self, runner) -> None:
        # Arrange
        module, log = runner

        # Act
        module.run_all(["any_first", "any_second"])

        # Assert
        calls = _calls(log)
        assert [scenario for _, scenario in calls] == ["any_first", "any_second"]
        process_ids = {pid for pid, _ in calls}
        assert len(process_ids) == 2                      # two different processes
        assert str(os.getpid()) not in process_ids        # neither of them is the test's own

    def test_failing_meta_scenario_stops_the_batch(self, runner) -> None:
        # Arrange: the fake exits with code 3 for "any_broken"
        module, log = runner

        # Act & Assert
        with pytest.raises(SystemExit) as stop:
            module.run_all(["any_first", "any_broken", "any_never_started"])
        assert stop.value.code == (
            "Meta-scenario any_broken failed with exit code 3; the remaining meta-scenarios were not run."
        )
        assert [scenario for _, scenario in _calls(log)] == ["any_first", "any_broken"]

    def test_empty_scenario_list_starts_no_process(self, runner) -> None:
        # Arrange
        module, log = runner

        # Act
        module.run_all([])

        # Assert
        assert not log.exists()
