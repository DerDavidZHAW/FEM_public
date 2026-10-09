"""Swiss demand for a CH_only model run, option A (decided 2026-10-09).

FEM treats storage pumping as a decision, so demand excludes pumping. FEM's solar infeed is total PV
production, so demand includes the consumption that on-site generation covers (option A, "gross"):

    demand(t) = Swissgrid end-user consumption(t) + grid losses(t) + on-site consumption(t)

- Swissgrid end-user consumption: metered, hourly. It contains no pumping and no grid losses, and none of
  the consumption covered by on-site generation (that generation is not metered by Swissgrid either).
- Grid losses: BFE monthly Verluste, spread over the month in proportion to end-user consumption.
- On-site consumption: BFE monthly Endverbrauch minus the month's Swissgrid end-user energy.

Monthly demand therefore equals BFE Landesverbrauch (Endverbrauch + Verluste) by construction.

The on-site part is self-consumed PV (midday only) plus other on-site generation (around the clock); the
split is NOT published. It is set by the assumption `onsite_solar_share` (s, config ONSITE_SOLAR_SHARE =
0.5, the midpoint chosen by the user on 2026-10-09):

    onsite(t) = s * onsite_solar_shaped(t) + (1 - s) * onsite_flat(t)
    demand_MW(t) = end_user(t) + losses(t) + onsite(t)          <- the series to use

The two extremes are kept as columns (`demand_solar_shaped_MW`: s = 1, `demand_flat_MW`: s = 0) so the
size of the assumption stays visible; in July 2026 they differ by about 1.6 GW at noon.
"""
import numpy as np
import pandas as pd

from data_prep.historical.config import LOCAL_TZ


def local_month(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(index.tz_convert(LOCAL_TZ).tz_localize(None).to_period("M").to_timestamp())


def build_demand_option_a(end_user_mw: pd.Series, solar_mw: pd.Series, balance: pd.DataFrame,
                          onsite_solar_share: float) -> pd.DataFrame:
    """Hourly demand components in MW on the UTC index of end_user_mw.

    A month gets values only if every hour has end-user and solar data and BFE has published it;
    otherwise the whole month stays NaN. Raises if Swissgrid end-user energy exceeds BFE end use in a
    month (the definitions would contradict each other) or if a month has no PV output to shape by.
    """
    if not 0.0 <= onsite_solar_share <= 1.0:
        raise ValueError(f"onsite_solar_share must lie in [0, 1], got {onsite_solar_share}")
    if not end_user_mw.index.equals(solar_mw.index):
        raise ValueError("end-user and solar series must share one hourly index")
    month = local_month(end_user_mw.index)
    hours = end_user_mw.groupby(month).size()
    complete = (end_user_mw.notna() & solar_mw.notna()).groupby(month).sum().eq(hours)
    bfe = balance.reindex(hours.index)
    usable = complete & bfe.Endverbrauch_GWh.notna() & bfe.Verluste_GWh.notna()

    end_user_gwh = end_user_mw.groupby(month).sum() / 1000
    solar_gwh = solar_mw.groupby(month).sum() / 1000
    onsite_gwh = (bfe.Endverbrauch_GWh - end_user_gwh).where(usable)
    negative = onsite_gwh[onsite_gwh < 0]
    if len(negative):
        raise ValueError(f"Swissgrid end-user energy exceeds BFE Endverbrauch in {list(negative.index.date)}")
    no_sun = usable & solar_gwh.le(0)
    if no_sun.any():
        raise ValueError(f"no PV output to shape on-site consumption in {list(no_sun.index[no_sun].date)}")

    def per_hour(monthly: pd.Series) -> np.ndarray:
        return monthly.reindex(month).to_numpy()

    ok = per_hour(usable.astype(float)) == 1.0
    end_user = end_user_mw.where(ok)
    losses = per_hour(bfe.Verluste_GWh / end_user_gwh) * end_user
    onsite_solar = per_hour(onsite_gwh / solar_gwh) * solar_mw.where(ok)
    onsite_flat = pd.Series(per_hour(onsite_gwh * 1000 / hours), index=end_user_mw.index).where(ok)
    out = pd.DataFrame({
        "swissgrid_end_user_MW": end_user,
        "grid_losses_MW": losses,
        "onsite_solar_shaped_MW": onsite_solar,
        "onsite_flat_MW": onsite_flat,
    }, index=end_user_mw.index)
    out["onsite_MW"] = onsite_solar_share * out.onsite_solar_shaped_MW + (1 - onsite_solar_share) * out.onsite_flat_MW
    out["onsite_solar_share_assumed"] = onsite_solar_share
    out["demand_MW"] = out.swissgrid_end_user_MW + out.grid_losses_MW + out.onsite_MW
    out["demand_solar_shaped_MW"] = out.swissgrid_end_user_MW + out.grid_losses_MW + out.onsite_solar_shaped_MW
    out["demand_flat_MW"] = out.swissgrid_end_user_MW + out.grid_losses_MW + out.onsite_flat_MW
    out["bfe_month_definitive"] = per_hour(bfe.Definitiv.where(usable))
    return out
