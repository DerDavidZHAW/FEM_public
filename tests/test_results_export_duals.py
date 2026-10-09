"""Unit tests for the dual export in aggregation/results_export.py.

Rows are scaled by sf on both sides in the model, so the solver's dual is 1/sf times the dual of
the original constraint. These tests set solver duals by hand (no solver) and check that the
exported values are in the units of the unscaled constraint.
"""
import pyomo.environ as pyo
import pytest

from aggregation.results_export import constraints

SCALING = {"generation_limit": 0.1, "building_heat_demand": 100.0, "consume_tot_limit": 1e-3}


def _model():
    m = pyo.ConcreteModel()
    m.ConstraintNames = pyo.Set(initialize=list(SCALING))
    m.constraint_scaling = pyo.Param(m.ConstraintNames, initialize=SCALING, mutable=True)
    m.T = pyo.Set(initialize=["t_1", "t_2"])
    m.x = pyo.Var(m.T)
    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    return m


def test_indexed_dual_is_multiplied_by_its_scaling_factor():
    m = _model()
    m.generation_limit = pyo.Constraint(m.T, rule=lambda m, t: 0.1 * m.x[t] <= 0.1 * 5)
    m.dual[m.generation_limit["t_1"]] = -854.28
    m.dual[m.generation_limit["t_2"]] = 0.0
    out = constraints([m.generation_limit], "unused", m, write_csv=False)["generation_limit"]
    assert out["value"].tolist() == pytest.approx([-85.428, 0.0])


def test_factor_above_one_scales_up():
    m = _model()
    m.building_heat_demand = pyo.Constraint(m.T, rule=lambda m, t: 100 * m.x[t] == 100 * 1)
    m.dual[m.building_heat_demand["t_1"]] = 0.5
    m.dual[m.building_heat_demand["t_2"]] = -0.25
    out = constraints([m.building_heat_demand], "unused", m, write_csv=False)["building_heat_demand"]
    assert out["value"].tolist() == pytest.approx([50.0, -25.0])


def test_per_plant_consume_tot_limit_uses_shared_factor():
    m = _model()
    name = "consume_tot_limit_CH00_electrolyzer_1_2050_st_wy1995_aa"
    m.add_component(name, pyo.Constraint(expr=1e-3 * m.x["t_1"] <= 1e-3 * 10))
    con = m.component(name)
    m.dual[con] = 2000.0
    out = constraints([con], "unused", m, write_csv=False)[name]
    assert out["value"].tolist() == pytest.approx([2.0])


def test_constraint_without_scaling_entry_is_exported_unchanged():
    # a constraint missing from the scaling map is not scaled in the model, so its factor is 1
    m = _model()
    m.unlisted_limit = pyo.Constraint(m.T, rule=lambda m, t: m.x[t] <= 1)
    m.dual[m.unlisted_limit["t_1"]] = -3.5
    m.dual[m.unlisted_limit["t_2"]] = 0.0
    out = constraints([m.unlisted_limit], "unused", m, write_csv=False)["unlisted_limit"]
    assert out["value"].tolist() == pytest.approx([-3.5, 0.0])
