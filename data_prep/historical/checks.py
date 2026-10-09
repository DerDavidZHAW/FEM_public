"""Cross-checks between independent sources, written to validation_report.csv by process.py.

Each check compares two publishers' numbers for the same quantity over the hours both have.
They report; they do not change data.
"""
import numpy as np
import pandas as pd

from data_prep.historical.config import COUNTRY_OF_NODE, NEIGHBOURS


def _compare(check: str, item: str, a: pd.Series, b: pd.Series, unit: str) -> dict:
    both = pd.concat([a, b], axis=1).dropna()
    diff = both.iloc[:, 0] - both.iloc[:, 1]
    return {
        "check": check, "item": item, "unit": unit, "hours_compared": len(both),
        "mean_a": both.iloc[:, 0].mean(), "mean_b": both.iloc[:, 1].mean(),
        "mean_abs_diff": diff.abs().mean(), "max_abs_diff": diff.abs().max(),
        "correlation": both.iloc[:, 0].corr(both.iloc[:, 1]) if len(both) > 1 else np.nan,
    }


def price_spreads(prices: pd.DataFrame, sg_flows: pd.DataFrame) -> list[dict]:
    """a = Energy-Charts (neighbour - CH), b = Swissgrid published spot spread (neighbour - CH)."""
    rows = []
    for node in NEIGHBOURS:
        c = COUNTRY_OF_NODE[node]
        rows.append(_compare("price spread vs Swissgrid", f"{c} - CH", prices[node] - prices["CH00"],
                             sg_flows[f"spread_{c}_minus_CH"], "EUR/MWh"))
    return rows


def load(public_power: pd.DataFrame, overview: pd.DataFrame) -> list[dict]:
    """a = Energy-Charts CH load, b = Swissgrid consumption of the control block."""
    return [
        _compare("load vs Swissgrid", "control-block consumption", public_power["load"],
                 overview["consumption_control_block"], "MW"),
        _compare("load vs Swissgrid", "end-user consumption", public_power["load"],
                 overview["consumption_end_users"], "MW"),
    ]


def physical_flows(physical: pd.DataFrame, overview: pd.DataFrame) -> list[dict]:
    """a = Energy-Charts physical flow (+ import), b = Swissgrid metered exchange (+ import)."""
    return [_compare("physical flow vs Swissgrid", COUNTRY_OF_NODE[n], physical[n],
                     overview[f"phys_net_import_{n}"], "MW") for n in NEIGHBOURS]


def commercial_flows(scheduled: pd.DataFrame, sg_flows: pd.DataFrame) -> list[dict]:
    """a = Energy-Charts scheduled exchange (+ import), b = Swissgrid net commercial flow as
    published; the correlation sign tells Swissgrid's sign convention."""
    return [_compare("scheduled exchange vs Swissgrid", COUNTRY_OF_NODE[n], scheduled[n],
                     sg_flows[f"comm_net_{COUNTRY_OF_NODE[n]}"], "MW") for n in NEIGHBOURS]


def schedules_within_ntc(scheduled: pd.DataFrame, ntc: pd.DataFrame, source: str) -> list[dict]:
    """Hours where the scheduled exchange exceeds the NTC of its direction by more than 1 MW."""
    rows = []
    for n in NEIGHBOURS:
        c = COUNTRY_OF_NODE[n]
        both = pd.concat([scheduled[n], ntc[f"{c}_to_CH"], ntc[f"CH_to_{c}"]], axis=1).dropna()
        flow, imp, exp = both.iloc[:, 0], both.iloc[:, 1], both.iloc[:, 2]
        rows.append({
            "check": f"scheduled exchange within NTC ({source})", "item": c, "unit": "hours",
            "hours_compared": len(both),
            "hours_import_above_ntc": int((flow > imp + 1).sum()),
            "hours_export_above_ntc": int((-flow > exp + 1).sum()),
            "hours_import_at_ntc": int(((flow - imp).abs() <= 1).sum()),
            "hours_export_at_ntc": int(((-flow - exp).abs() <= 1).sum()),
        })
    return rows


def entsoe_web_vs_d2(d2: pd.DataFrame, web_main: pd.DataFrame | None) -> list[dict]:
    """ENTSO-E web copy vs Swissgrid D-2 files, hour by hour: the 2026 check days and the preferred days
    (on which the web copy replaces D-2, so their difference stays on record)."""
    from data_prep.historical import entsoe_web
    from data_prep.historical.config import LOCAL_TZ, NTC_ENTSOE_WEB_PREFERRED_DAYS
    days = []
    folder = entsoe_web.RAW / "validation_2026"
    for path in sorted(folder.glob("*.txt")) if folder.exists() else []:
        days += [(line[:10], "check day", entsoe_web.parse_line(line))
                 for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    if web_main is not None:
        local_day = web_main.index.tz_convert(LOCAL_TZ).strftime("%Y-%m-%d")
        days += [(d, "preferred day (web copy used)", web_main[local_day == d])
                 for d in NTC_ENTSOE_WEB_PREFERRED_DAYS if (local_day == d).any()]
    rows = []
    for day, kind, web in days:
        sg = d2.reindex(web.index)[web.columns]
        both = web.notna() & sg.notna()
        diff = (web - sg).abs()[both]
        rows.append({"check": f"ENTSO-E web day-ahead NTC vs Swissgrid D-2, {kind}", "item": day, "unit": "values",
                     "hours_compared": int(both.sum().sum()),
                     "values_equal": int((diff < 0.5).sum().sum()),
                     "max_abs_diff": float(diff.max().max()) if both.any().any() else float("nan"),
                     "values_entsoe_only": int((web.notna() & sg.isna()).sum().sum())})
    return rows


def nuclear(nuclear_table: pd.DataFrame) -> list[dict]:
    above = nuclear_table["generation_MW"] > nuclear_table["net_capacity_MW"]
    return [{"check": "nuclear generation within net capacity", "item": "CH", "unit": "hours",
             "hours_compared": int(nuclear_table["generation_MW"].notna().sum()),
             "hours_above_capacity": int(above.sum()),
             "max_abs_diff": float((nuclear_table["generation_MW"] - nuclear_table["net_capacity_MW"]).max())}]


def run_all(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    rows += price_spreads(tables["prices_day_ahead"], tables["swissgrid_cross_border"])
    rows += load(tables["ch_public_power"], tables["swissgrid_overview"])
    rows += physical_flows(tables["ch_exchanges_physical_energy_charts"], tables["swissgrid_overview"])
    rows += commercial_flows(tables["ch_exchanges_scheduled"], tables["swissgrid_cross_border"])
    rows += schedules_within_ntc(tables["ch_exchanges_scheduled"], tables["ntc_swissgrid_d2"], "Swissgrid D-2")
    if "ntc_entsoe_a61" in tables:
        rows += schedules_within_ntc(tables["ch_exchanges_scheduled"], tables["ntc_entsoe_a61"], "ENTSO-E A61")
    rows += entsoe_web_vs_d2(tables["ntc_swissgrid_d2"], tables.get("ntc_entsoe_web"))
    rows += nuclear(tables["nuclear_availability"])
    return pd.DataFrame(rows)
