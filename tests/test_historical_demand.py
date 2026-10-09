"""Unit tests for demand option A (data_prep/historical/demand.py) and the BFE balance reader."""
import numpy as np
import pandas as pd
import pytest

from data_prep.historical import bfe
from data_prep.historical.demand import build_demand_option_a
from data_prep.historical.timeutils import hourly_index


def _inputs(end_user=1000.0, night_solar=0.0, day_solar=500.0):
    """One local month (Feb 2026, 672 h): flat end-user load, solar only 10:00-15:59 local."""
    idx = hourly_index("2026-02-01", "2026-02-28")
    local_hour = idx.tz_convert("Europe/Zurich").hour
    solar = pd.Series(np.where((local_hour >= 10) & (local_hour < 16), day_solar, night_solar), index=idx)
    load = pd.Series(end_user, index=idx)
    # BFE: end use 800 GWh, losses 60 GWh; Swissgrid end-user energy = 672 GWh -> on-site 128 GWh.
    balance = pd.DataFrame({"Endverbrauch_GWh": [800.0], "Verluste_GWh": [60.0], "Definitiv": [0]},
                           index=pd.DatetimeIndex(["2026-02-01"]))
    return load, solar, balance


def test_monthly_demand_equals_bfe_end_use_plus_losses_for_both_shapes():
    load, solar, balance = _inputs()
    out = build_demand_option_a(load, solar, balance, 0.5)
    assert out.demand_solar_shaped_MW.sum() / 1000 == pytest.approx(860.0)
    assert out.demand_flat_MW.sum() / 1000 == pytest.approx(860.0)
    assert out.grid_losses_MW.sum() / 1000 == pytest.approx(60.0)
    assert out.onsite_flat_MW.sum() / 1000 == pytest.approx(128.0)


def test_losses_follow_end_user_and_onsite_shapes_follow_pv_or_are_flat():
    load, solar, balance = _inputs()
    load.iloc[:24] = 2000.0  # first day twice the load
    out = build_demand_option_a(load, solar, balance, 0.5)
    assert out.grid_losses_MW.iloc[0] == pytest.approx(2 * out.grid_losses_MW.iloc[100])
    night = out.index.tz_convert("Europe/Zurich").hour < 6
    assert (out.onsite_solar_shaped_MW[night] == 0).all()
    assert out.onsite_flat_MW.nunique() == 1


def test_demand_is_the_share_weighted_mix_of_the_two_extremes():
    load, solar, balance = _inputs()
    out = build_demand_option_a(load, solar, balance, 0.3)
    expected = 0.3 * out.demand_solar_shaped_MW + 0.7 * out.demand_flat_MW
    assert np.allclose(out.demand_MW, expected)
    assert out.demand_MW.sum() / 1000 == pytest.approx(860.0)
    noon = out.index.tz_convert("Europe/Zurich").hour == 12
    assert (out.demand_flat_MW[noon] < out.demand_MW[noon]).all()
    assert (out.demand_MW[noon] < out.demand_solar_shaped_MW[noon]).all()


@pytest.mark.parametrize("share", [-0.1, 1.5])
def test_share_outside_zero_one_raises(share):
    load, solar, balance = _inputs()
    with pytest.raises(ValueError, match="onsite_solar_share"):
        build_demand_option_a(load, solar, balance, share)


def test_configured_share_is_the_documented_midpoint():
    from data_prep.historical.config import ONSITE_SOLAR_SHARE
    assert ONSITE_SOLAR_SHARE == 0.5


def test_month_with_a_missing_hour_stays_nan():
    load, solar, balance = _inputs()
    load.iloc[5] = np.nan
    out = build_demand_option_a(load, solar, balance, 0.5)
    assert out.drop(columns=["bfe_month_definitive", "onsite_solar_share_assumed"]).isna().all().all()


def test_month_not_yet_published_by_bfe_stays_nan():
    load, solar, balance = _inputs()
    out = build_demand_option_a(load, solar, balance.iloc[0:0], 0.5)
    assert out.demand_flat_MW.isna().all()


def test_end_user_above_bfe_end_use_raises():
    load, solar, balance = _inputs(end_user=1500.0)  # 1,008 GWh > 800 GWh end use
    with pytest.raises(ValueError, match="exceeds BFE Endverbrauch"):
        build_demand_option_a(load, solar, balance, 0.5)


def test_month_without_pv_raises():
    load, solar, balance = _inputs(day_solar=0.0)
    with pytest.raises(ValueError, match="no PV output"):
        build_demand_option_a(load, solar, balance, 0.5)


def _balance_csv(tmp_path, losses=60):
    path = tmp_path / "ogd35.csv"
    path.write_text("Jahr,Monat,Definitiv,Endverbrauch_GWh,Verluste_GWh,Landesverbrauch_GWh,"
                    "Verbrauch_Speicherpumpen_GWh,Erzeugung_Photovoltaik_GWh\n"
                    f"2026,2,0,800,{losses},860,284,358\n", encoding="utf-8")
    return path


def test_read_balance_indexes_by_month(tmp_path):
    frame = bfe.read_balance(_balance_csv(tmp_path))
    assert frame.index[0] == pd.Timestamp("2026-02-01") and frame.Landesverbrauch_GWh.iloc[0] == 860


def test_read_balance_raises_when_national_consumption_is_not_end_use_plus_losses(tmp_path):
    with pytest.raises(ValueError, match="Landesverbrauch"):
        bfe.read_balance(_balance_csv(tmp_path, losses=10))
