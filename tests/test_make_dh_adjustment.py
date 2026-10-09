"""Unit tests for the DH adjustment-file generator core (M5).

External behaviour only: given instructions and an hour axis, what wide table
comes out. The wrap-around case and round-trip through the loader/validator are
the ones that matter.
"""
import pandas as pd
import pytest

from utils.make_dh_adjustment import build_adjustment_frame, all_hour_labels
from model.dh_demand_adjustment import apply_dh_demand_adjustment

H6 = all_hour_labels(6)   # t_1 .. t_6


def test_in_year_window_fills_inclusive_range():
    df = build_adjustment_frame([("DH_medium", "t_2", "t_4", -50.0)], H6)
    row = df.loc["DH_medium"]
    assert row["t_1"] == 0 and row["t_5"] == 0 and row["t_6"] == 0
    assert row["t_2"] == -50 and row["t_3"] == -50 and row["t_4"] == -50


def test_wrap_around_window_spans_year_boundary():
    # start (t_5) after end (t_2) -> covers t_5, t_6, t_1, t_2 ; not t_3, t_4
    df = build_adjustment_frame([("DH_medium", "t_5", "t_2", 10.0)], H6)
    row = df.loc["DH_medium"]
    assert list(row[["t_5", "t_6", "t_1", "t_2"]]) == [10, 10, 10, 10]
    assert row["t_3"] == 0 and row["t_4"] == 0


def test_multiple_instructions_same_node_accumulate():
    df = build_adjustment_frame(
        [("DH_medium", "t_1", "t_3", -10.0), ("DH_medium", "t_2", "t_4", -5.0)], H6)
    row = df.loc["DH_medium"]
    assert row["t_1"] == -10            # first only
    assert row["t_2"] == -15 and row["t_3"] == -15   # overlap summed
    assert row["t_4"] == -5            # second only


def test_multiple_nodes_independent_rows():
    df = build_adjustment_frame(
        [("DH_medium", "t_1", "t_2", -30.0), ("DH_Jura", "t_3", "t_3", 5.0)], H6)
    assert df.loc["DH_medium", "t_1"] == -30 and df.loc["DH_medium", "t_3"] == 0
    assert df.loc["DH_Jura", "t_3"] == 5 and df.loc["DH_Jura", "t_1"] == 0
    assert list(df.index) == ["DH_medium", "DH_Jura"]   # first-seen order


def test_unknown_hour_label_raises():
    with pytest.raises(ValueError, match="t_99"):
        build_adjustment_frame([("DH_medium", "t_1", "t_99", -5.0)], H6)


def test_output_roundtrips_through_loader_validator(tmp_path):
    # generator output, written + reloaded, must apply cleanly via the overlay
    df = build_adjustment_frame([("DH_medium", "t_2", "t_3", -10.0)], all_hour_labels(4))
    path = tmp_path / "gen.csv"
    df.to_csv(path)
    loaded = pd.read_csv(path, index_col=0)

    demand = {("DH_medium", f"t_{i}"): 100.0 for i in range(1, 5)}
    nodes = {"DH_medium"}
    hours = {f"t_{i}" for i in range(1, 5)}
    out = apply_dh_demand_adjustment(demand, loaded, nodes, hours)
    assert out[("DH_medium", "t_2")] == 90.0
    assert out[("DH_medium", "t_3")] == 90.0
    assert out[("DH_medium", "t_1")] == 100.0
    assert out[("DH_medium", "t_4")] == 100.0
