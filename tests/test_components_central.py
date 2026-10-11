"""Unit tests for the winter import limit and the Swiss RES target (model/components_central.py).

Both are switched per sub-scenario. Each test builds a two-sub-scenario model with only the
components define_constraints_central reads: one line into and one out of CH00, one Swiss RES
candidate. No solver is used.
"""
import pyomo.environ as pyo
from pyomo.core.expr.visitor import identify_variables

import model.components_central as components_central
from model.components_central import define_constraints_central

SCENARIOS = ["2050_x_wy1995", "2050_x_wy2008"]


def _model():
    m = pyo.ConcreteModel()
    m.Scenarios = pyo.Set(initialize=SCENARIOS)
    m.T = pyo.Set(initialize=["t_1", "t_2", "t_3"], ordered=True)
    m.Node = pyo.Set(initialize=["CH00"])
    m.lineATC = pyo.Set(initialize=["HVAC_AT00_CH00", "HVAC_CH00_DE00"])
    m.Map_node_importinglineATC = pyo.Param(m.Node, initialize={"CH00": ["HVAC_AT00_CH00"]}, within=pyo.Any)
    m.Map_node_exportinglineATC = pyo.Param(m.Node, initialize={"CH00": ["HVAC_CH00_DE00"]}, within=pyo.Any)
    m.Export = pyo.Var(m.lineATC, m.T, m.Scenarios)
    m.P_flex_d_within_window = pyo.Set(initialize=[])
    m.Data_plant_flex_d_within_window = pyo.Param(m.P_flex_d_within_window, m.Scenarios, within=pyo.Any)
    m.Consumer = pyo.Set(initialize=["CH00_fixedconsumer"])
    m.Map_node_consumer = pyo.Param(m.Node, initialize={"CH00": ["CH00_fixedconsumer"]}, within=pyo.Any)
    m.Tech_infeed = pyo.Set(initialize=["pvrf", "ror"])
    m.infeed = pyo.Param(m.Consumer, m.Tech_infeed, m.T, m.Scenarios, initialize=1.0)
    m.P = pyo.Set(initialize=["CH01_pvrf"])
    m.Map_node_plant = pyo.Param(m.Node, initialize={"CH00": ["CH01_pvrf"]}, within=pyo.Any)
    m.gen_max = pyo.Var(m.P, m.Scenarios)
    m.avail_plant = pyo.Param(m.P, m.T, m.Scenarios, initialize=0.5)
    return m


def _winter_limit(mode, window, energy_MWh):
    return {"mode": mode, "window": window, "energy_MWh": energy_MWh}


def _indices_of_variables(constraint):
    return [var.index() for var in identify_variables(constraint.body)]


def test_each_sub_scenario_keeps_its_own_winter_import_limit():
    m = _model()
    winter_limit = {
        "2050_x_wy1995": _winter_limit(True, [1, 3], 0),
        "2050_x_wy2008": _winter_limit(True, [2, 3], 5000),
    }
    define_constraints_central(m, False, winter_limit, {s: False for s in SCENARIOS})
    for s in SCENARIOS:
        t_start, t_end = winter_limit[s]["window"]
        assert pyo.value(m.Constraint_winter_limit[s].upper) == winter_limit[s]["energy_MWh"]
        assert {index[2] for index in _indices_of_variables(m.Constraint_winter_limit[s])} == {s}
        assert {index[1] for index in _indices_of_variables(m.Constraint_winter_limit[s])} == {
            f"t_{t}" for t in range(t_start, t_end + 1)
        }


def test_winter_import_limit_exists_only_for_sub_scenarios_that_switch_it_on():
    m = _model()
    winter_limit = {
        "2050_x_wy1995": _winter_limit(True, [1, 3], 0),
        "2050_x_wy2008": _winter_limit(False, [1, 3], 0),
    }
    define_constraints_central(m, False, winter_limit, {s: False for s in SCENARIOS})
    assert list(m.Constraint_winter_limit.keys()) == ["2050_x_wy1995"]


def test_each_sub_scenario_keeps_its_own_swiss_res_target(monkeypatch):
    monkeypatch.setattr(components_central, "Plant_investment_RES_CH_list", ["CH01_pvrf"])
    m = _model()
    target = {"2050_x_wy1995": 100, "2050_x_wy2008": 200}
    define_constraints_central(m, False, {s: _winter_limit(False, [1, 3], 0) for s in SCENARIOS}, target)
    for s in SCENARIOS:
        assert pyo.value(m.Constraint_investment_res_CH[s].lower) == target[s]
        assert _indices_of_variables(m.Constraint_investment_res_CH[s]) == [("CH01_pvrf", s)]
