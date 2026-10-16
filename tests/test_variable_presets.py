"""Unit tests for apply_variable_presets (model/variable_presets.py).

A preset that cannot be applied must stop the run: otherwise the scenario is solved without the
fixed value its author asked for. Each test writes a small presets file (format in the header of
input/model_variable_presets.csv) and applies it to a model with one variable. No solver is used.
"""
import pyomo.environ as pyo
import pytest

from model.variable_presets import apply_variable_presets


def _model():
    m = pyo.ConcreteModel()
    m.P = pyo.Set(initialize=["CH01_pvrf", "CH00_nuclear"])
    m.Scenarios = pyo.Set(initialize=["2050_x_wy1995", "2050_x_wy2008"])
    m.gen_max = pyo.Var(m.P, m.Scenarios)
    m.weight_in_objective_fcn = pyo.Param(m.Scenarios, initialize=0.5)
    return m


def _presets_file(tmp_path, row):
    path = tmp_path / "model_variable_presets.csv"
    path.write_text("# variable_name,scenario_name,index1,index2,...,value\n" + row + "\n")
    return str(path)


def test_preset_fixes_the_variable_in_every_sub_scenario(tmp_path):
    m = _model()
    apply_variable_presets(m, "2050_x", _presets_file(tmp_path, "gen_max,2050_x,CH01_pvrf,,100"), verbose=False)
    for s in m.Scenarios:
        assert m.gen_max["CH01_pvrf", s].fixed
        assert m.gen_max["CH01_pvrf", s].value == 100
        assert not m.gen_max["CH00_nuclear", s].fixed


@pytest.mark.parametrize("row, culprit", [
    ("gen_maxx,2050_x,CH01_pvrf,,100", "gen_maxx"),                    # variable not in the model
    ("weight_in_objective_fcn,2050_x,,100", "weight_in_objective_fcn"),  # not a variable
    ("gen_max,2050_x,CH09_pvrf,,100", "CH09_pvrf"),                    # index not in the model
])
def test_preset_that_cannot_be_applied_raises(tmp_path, row, culprit):
    with pytest.raises(ValueError, match=culprit):
        apply_variable_presets(_model(), "2050_x", _presets_file(tmp_path, row), verbose=False)
