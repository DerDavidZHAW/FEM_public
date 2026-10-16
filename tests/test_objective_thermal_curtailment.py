"""Unit test for the thermal curtailment penalty in obj_expression (model/components_common.py).

The objective is built on a model that has no plants, consumers or fuels, so the penalty on
district-heat curtailment is its only term. No solver is used.
"""
import pyomo.environ as pyo
import pytest
from pyomo.repn import generate_standard_repn

from model.components_common import obj_expression


def _model(weights):
    m = pyo.ConcreteModel()
    m.Scenarios = pyo.Set(initialize=list(weights))
    m.weight_in_objective_fcn = pyo.Param(m.Scenarios, initialize=weights)
    m.T = pyo.Set(initialize=["t_1", "t_2"])
    for name in ["P", "Consumer", "lostLoad_step", "P_fuellimCH", "P_pumping", "PDH_allinvTh",
                 "PDH_costExclusivelyOnThermalSide", "Fuels_limited"]:
        m.add_component(name, pyo.Set(initialize=[]))
    m.NodeDH = pyo.Set(initialize=["DH_medium"])
    m.curtailmentTh = pyo.Var(m.NodeDH, m.T, m.Scenarios, domain=pyo.NonNegativeReals)
    return m


def _objective_coefficients(m):
    repn = generate_standard_repn(obj_expression(m))
    return {var.name: coef for var, coef in zip(repn.linear_vars, repn.linear_coefs)}


def test_thermal_curtailment_is_penalised_in_every_sub_scenario_times_its_weight():
    weights = {"2050_x_wy1995": 0.25, "2050_x_wy2008": 0.75}
    coefficients = _objective_coefficients(_model(weights))
    penalty_per_weight = {
        s: coefficients.get(f"curtailmentTh[DH_medium,t_1,{s}]", 0.0) / w for s, w in weights.items()
    }
    assert penalty_per_weight["2050_x_wy1995"] > 0
    assert penalty_per_weight["2050_x_wy1995"] == pytest.approx(penalty_per_weight["2050_x_wy2008"])
