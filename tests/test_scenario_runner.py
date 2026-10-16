"""Unit tests for model/scenario_runner.py."""
import re

import pytest

from model.scenario_runner import run_meta_scenarios


class TestRunMetaScenarios:
    def test_runs_every_meta_scenario_in_order_and_returns_them(self) -> None:
        # Arrange
        started: list[str] = []

        def run_one(scenario_name: str) -> int:
            started.append(scenario_name)
            return 0

        # Act
        finished = run_meta_scenarios(["any_second", "any_first", "any_third"], run_one=run_one)

        # Assert
        assert started == ["any_second", "any_first", "any_third"]
        assert finished == ["any_second", "any_first", "any_third"]

    def test_stops_at_the_first_failure_and_names_it(self) -> None:
        # Arrange: the second meta-scenario exits with code 3, the others succeed
        started: list[str] = []

        def run_one(scenario_name: str) -> int:
            started.append(scenario_name)
            return 3 if scenario_name == "any_failing" else 0

        expected_message = (
            "meta-scenario 'any_failing' failed with exit code 3; "
            "1 of 3 finished before it: ['any_ok']"
        )

        # Act & Assert
        with pytest.raises(RuntimeError, match=re.escape(expected_message)):
            run_meta_scenarios(["any_ok", "any_failing", "any_never_started"], run_one=run_one)
        assert started == ["any_ok", "any_failing"]

    def test_empty_scenario_list_runs_nothing(self) -> None:
        # Arrange
        def run_one(scenario_name: str) -> int:
            pytest.fail("run_one must not be called for an empty list")

        # Act
        finished = run_meta_scenarios([], run_one=run_one)

        # Assert
        assert finished == []
