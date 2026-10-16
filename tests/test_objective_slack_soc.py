"""Unit test for the cost of the state-of-charge slacks in obj_expression (model/components_common.py).

With the setting slack_soc, slackSOC_POS and slackSOC_NEG enter the balance of every electric
(P_storage) and thermal (PDH_storage) store. The objective is built on a model that has no
plants, consumers or fuels, so the slack cost is its only term. No solver is used.
"""
import pyomo.environ as pyo
import pytest
from pyomo.repn import generate_standard_repn

from model.components_common import obj_expression


def _model():
    m = pyo.ConcreteModel()
    m.Scenarios = pyo.Set(initialize=["2050_x_wy1995"])
    m.weight_in_objective_fcn = pyo.Param(m.Scenarios, initialize={"2050_x_wy1995": 1.0})
    m.T = pyo.Set(initialize=["t_1", "t_2"])
    for name in ["P", "Consumer", "lostLoad_step", "P_fuellimCH", "P_pumping", "PDH_allinvTh",
                 "PDH_costExclusivelyOnThermalSide", "Fuels_limited", "NodeDH"]:
        m.add_component(name, pyo.Set(initialize=[]))
    m.slack_soc = True
    m.P_storage = pyo.Set(initialize=["CH00_battery"])
    m.PDH_storage = pyo.Set(initialize=["DH_medium_TTES_medium"])
    m.slackSOC_POS = pyo.Var(m.P_storage | m.PDH_storage, m.T, m.Scenarios, domain=pyo.NonNegativeReals)
    m.slackSOC_NEG = pyo.Var(m.P_storage | m.PDH_storage, m.T, m.Scenarios, domain=pyo.NonNegativeReals)
    return m


def test_thermal_storage_slacks_cost_as_much_as_electric_storage_slacks():
    repn = generate_standard_repn(obj_expression(_model()))
    coefficients = {var.name: coef for var, coef in zip(repn.linear_vars, repn.linear_coefs)}
    for slack in ["slackSOC_POS", "slackSOC_NEG"]:
        electric = coefficients[f"{slack}[CH00_battery,t_1,2050_x_wy1995]"]
        thermal = coefficients.get(f"{slack}[DH_medium_TTES_medium,t_1,2050_x_wy1995]", 0.0)
        assert electric > 0
        assert thermal == pytest.approx(electric)
