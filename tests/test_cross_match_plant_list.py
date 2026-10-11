"""Unit tests for cross_match_plant_list (model/data_import_fcns.py).

Every non-hydro plant needs a capacity from the capacity files, except investment candidates,
whose capacity the optimisation chooses.
"""
import pytest

from model.data_import_fcns import cross_match_plant_list


def test_plant_without_capacity_raises():
    with pytest.raises(ValueError, match="CH00_nuclear"):
        cross_match_plant_list(["CH00_gas"], ["CH00_gas", "CH00_nuclear"], [])


def test_investment_candidate_needs_no_capacity():
    cross_match_plant_list(["CH00_gas"], ["CH00_gas", "AT01_battery"], ["AT01_battery"])
