"""Unit tests for the pure DH demand adjustment apply function (M1).

These exercise external behaviour only — given a demand mapping and a wide
delta table, what comes out — with no files, settings, or solver. Slice 1 (#44)
covers the additive happy path and partial-file semantics; the strict-error
cases are added with #45.
"""
import pandas as pd
import pytest

from model.dh_demand_adjustment import apply_dh_demand_adjustment, load_dh_adjustment_file

NODES = {"DH_medium", "DH_Jura"}
HOURS = {"t_1", "t_2"}


def _demand():
    return {
        ("DH_medium", "t_1"): 100.0, ("DH_medium", "t_2"): 100.0,
        ("DH_Jura", "t_1"): 50.0, ("DH_Jura", "t_2"): 50.0,
    }


def test_none_table_is_noop():
    d = _demand()
    assert apply_dh_demand_adjustment(d, None, NODES, HOURS) == d


def test_additive_negative_and_positive_deltas():
    adj = pd.DataFrame({"t_1": [-30.0], "t_2": [10.0]}, index=["DH_medium"])
    out = apply_dh_demand_adjustment(_demand(), adj, NODES, HOURS)
    assert out[("DH_medium", "t_1")] == 70.0      # reduced
    assert out[("DH_medium", "t_2")] == 110.0     # increased
    assert out[("DH_Jura", "t_1")] == 50.0        # untouched node


def test_absent_rows_and_hours_unchanged():
    # only DH_medium / t_1 specified -> DH_Jura and t_2 must be unchanged
    adj = pd.DataFrame({"t_1": [-20.0]}, index=["DH_medium"])
    out = apply_dh_demand_adjustment(_demand(), adj, NODES, HOURS)
    assert out[("DH_medium", "t_1")] == 80.0
    assert out[("DH_medium", "t_2")] == 100.0
    assert out[("DH_Jura", "t_1")] == 50.0
    assert out[("DH_Jura", "t_2")] == 50.0


def test_zero_and_blank_cells_are_noop():
    adj = pd.DataFrame({"t_1": [0.0], "t_2": [float("nan")]}, index=["DH_medium"])
    assert apply_dh_demand_adjustment(_demand(), adj, NODES, HOURS) == _demand()


def test_multiple_nodes_applied_independently():
    adj = pd.DataFrame({"t_1": [-30.0, 5.0], "t_2": [0.0, -5.0]},
                       index=["DH_medium", "DH_Jura"])
    out = apply_dh_demand_adjustment(_demand(), adj, NODES, HOURS)
    assert out[("DH_medium", "t_1")] == 70.0
    assert out[("DH_Jura", "t_1")] == 55.0
    assert out[("DH_Jura", "t_2")] == 45.0


def test_input_demand_not_mutated():
    d = _demand()
    adj = pd.DataFrame({"t_1": [-30.0]}, index=["DH_medium"])
    apply_dh_demand_adjustment(d, adj, NODES, HOURS)
    assert d[("DH_medium", "t_1")] == 100.0


# --- strict validation (#45) --------------------------------------------------

def test_unknown_node_row_raises_naming_it():
    adj = pd.DataFrame({"t_1": [-10.0]}, index=["DH_typo"])
    with pytest.raises(ValueError, match="DH_typo"):
        apply_dh_demand_adjustment(_demand(), adj, NODES, HOURS)


def test_unknown_hour_column_raises_naming_it():
    adj = pd.DataFrame({"t_9999": [-10.0]}, index=["DH_medium"])
    with pytest.raises(ValueError, match="t_9999"):
        apply_dh_demand_adjustment(_demand(), adj, NODES, HOURS)


def test_negative_demand_raises_naming_node_hour():
    adj = pd.DataFrame({"t_1": [-150.0]}, index=["DH_medium"])  # 100 - 150 < 0
    with pytest.raises(ValueError, match=r"DH_medium t_1.*negative|negative.*DH_medium"):
        apply_dh_demand_adjustment(_demand(), adj, NODES, HOURS)


def test_reduction_to_exactly_zero_is_allowed():
    adj = pd.DataFrame({"t_1": [-100.0]}, index=["DH_medium"])  # 100 - 100 = 0
    out = apply_dh_demand_adjustment(_demand(), adj, NODES, HOURS)
    assert out[("DH_medium", "t_1")] == 0.0


def test_both_mechanisms_active_raises():
    adj = pd.DataFrame({"t_1": [-10.0]}, index=["DH_medium"])
    with pytest.raises(ValueError, match="mutually exclusive"):
        apply_dh_demand_adjustment(_demand(), adj, NODES, HOURS, reduce_DH_demand_by=5000)


def test_false_setting_returns_none():
    assert load_dh_adjustment_file(False) is None


def test_missing_named_file_raises():
    with pytest.raises(FileNotFoundError, match="no_such_adjustment_file"):
        load_dh_adjustment_file("no_such_adjustment_file.csv")
