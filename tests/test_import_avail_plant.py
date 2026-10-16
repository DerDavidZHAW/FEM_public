"""Unit tests for the conventional availability factors read by import_avail_plant (model/data_import_fcns.py).

The function reads input/availability_factor_conventional.csv relative to the working directory;
the tests write a small version of it into a temporary folder. Country rows override the
"Default" rows for their technology.
"""
import pytest

import model.data_import_fcns as data_import_fcns
from model.data_import_fcns import import_avail_plant

PLANTS = ["CH00_nuclear", "CH00_oil", "CH00_gas"]
MAP_PLANT_NODE = {p: "CH00" for p in PLANTS}
MAP_PLANT_TECH = {"CH00_nuclear": "nuclear", "CH00_oil": "oil", "CH00_gas": "gas"}


def _availability(tmp_path, monkeypatch, csv_rows):
    (tmp_path / "input").mkdir()
    (tmp_path / "input" / "availability_factor_conventional.csv").write_text(
        "country,technology,jan\n" + "".join(row + "\n" for row in csv_rows)
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(data_import_fcns, "timemapping_creator", lambda originP, targetP: {"t_1": "jan"})
    return import_avail_plant(PLANTS, [], [], ["t_1"], MAP_PLANT_NODE, MAP_PLANT_TECH, {"CH00": "CH"}, {})


def test_every_row_of_a_country_overrides_the_default(tmp_path, monkeypatch):
    avail = _availability(tmp_path, monkeypatch, [
        "CH,nuclear,0.5",
        "CH,oil,0.7",
        "Default,nuclear,0.9",
        "Default,oil,0.9",
        "Default,gas,0.8",
    ])
    assert avail["CH00_nuclear", "t_1"] == pytest.approx(0.5)
    assert avail["CH00_oil", "t_1"] == pytest.approx(0.7)
    assert avail["CH00_gas", "t_1"] == pytest.approx(0.8)


def test_two_rows_for_the_same_country_and_technology_raise(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="CH.*nuclear"):
        _availability(tmp_path, monkeypatch, [
            "CH,nuclear,0.5",
            "CH,nuclear,0.6",
            "Default,nuclear,0.9",
            "Default,oil,0.9",
            "Default,gas,0.8",
        ])
