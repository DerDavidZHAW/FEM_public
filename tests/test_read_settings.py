"""Unit tests for read_scenario_settings (model/read_settings.py).

Settings come from the scenario CSV named in scenarios/scenarios.py, with defaults from
scenarios/settings_default.py for rows the CSV lacks. A sub-scenario name the CSV does not
define must raise instead of running on defaults alone.
"""
import pytest

import model.read_settings as read_settings
from model.read_settings import read_scenario_settings


def test_scenario_not_in_the_scenario_csv_raises(monkeypatch):
    monkeypatch.setattr(read_settings, "scenarios_list", {"2050_x_wy1995": {"t_start": 1, "t_end": 3}})
    with pytest.raises(KeyError, match="2050_x_wy2008"):
        read_scenario_settings("2050_x_wy2008")


def test_scenario_csv_values_override_the_defaults(monkeypatch):
    monkeypatch.setattr(
        read_settings, "scenarios_list", {"2050_x_wy1995": {"t_start": 1, "t_end": 3, "run_year": 2035}}
    )
    settings = read_scenario_settings("2050_x_wy1995")
    assert settings["run_year"] == 2035
    assert settings["T_list"] == ["t_1", "t_2", "t_3"]
    assert settings["CH_only"] is False  # not in the CSV: default from settings_default.py
