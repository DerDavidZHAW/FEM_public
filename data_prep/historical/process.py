"""Turn raw downloads into hourly UTC tables under input/historical/processed/<start>_<end>/.

Usage (from the repo root, after download.py for the same period):
    python -m data_prep.historical.process --start 2023-10-01 --end 2026-09-30

Missing hours stay NaN and are listed in coverage_report.csv; nothing is filled or interpolated.
Every table has the index column time_utc (interval start, UTC). Sign convention for exchanges:
positive = import into CH.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from data_prep.historical import bfe, checks, demand, energy_charts, entsoe_ntc, entsoe_web, provenance, swissgrid
from data_prep.historical.config import (
    CAPACITY_HOURLY_RULE, ONSITE_SOLAR_SHARE, DIRECTIONS, LOCAL_TZ, NEIGHBOURS, NTC_ENTSOE_WEB_PREFERRED_DAYS, NUCLEAR_UNITS_NET_MW,
    PROCESSED_DIR, RAW_DIR, ZONES, COUNTRY_OF_NODE,
)
from data_prep.historical.timeutils import hourly_index, period_bounds_utc, to_hourly, year_chunks


# Energy-Charts cbet/cbpf series id -> FEM node
EXCHANGE_SERIES = {"germany": "DE00", "france": "FR00", "italy": "IT00", "austria": "AT00", "sum": "sum"}


def output_dir(start_day: str, end_day: str) -> Path:
    return PROCESSED_DIR / f"{start_day}_{end_day}"


def assemble_hourly(frames: list[pd.DataFrame], index: pd.DatetimeIndex, rule: str) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    """Concatenate native-resolution pieces, aggregate to hours with rule ("mean" or "min"), and
    align to the period index.

    Pieces may not overlap. Hours without data stay NaN. Returns the frame and the hours whose
    native stamps were incomplete or irregular.
    """
    full = pd.concat(frames).sort_index()
    if not full.index.is_unique:
        raise ValueError(f"overlapping pieces, duplicate stamps e.g. {full.index[full.index.duplicated()][:3].tolist()}")
    full = full[(full.index >= index[0]) & (full.index < index[-1] + pd.Timedelta(hours=1))]
    hourly, irregular = to_hourly(full, rule)
    return hourly.reindex(index), irregular


def energy_charts_table(endpoint: str, key: str, start_day: str, end_day: str, index) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    paths = [energy_charts.raw_path(endpoint, key, a, b) for a, b in year_chunks(start_day, end_day)]
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"run download.py first, missing: {[str(p) for p in missing]}")
    return assemble_hourly([energy_charts.read_raw(p) for p in paths], index, "mean")


def build_prices(start_day, end_day, index) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    """Day-ahead price per FEM node (EUR/MWh); quarter-hour prices are averaged to the hour."""
    columns, irregular = {}, []
    for node, zone in ZONES.items():
        frame, bad = energy_charts_table("price", zone["energy_charts"], start_day, end_day, index)
        columns[node] = frame["day_ahead_price"]
        irregular.extend(bad)
    return pd.DataFrame(columns, index=index), pd.DatetimeIndex(sorted(set(irregular)))


def build_exchanges(endpoint: str, start_day, end_day, index) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    """cbet / cbpf for CH: one column per neighbour (FEM node name) plus 'sum', MW, + = import."""
    frame, bad = energy_charts_table(endpoint, "ch", start_day, end_day, index)
    if sorted(frame.columns) != sorted(EXCHANGE_SERIES):
        raise ValueError(f"{endpoint}: expected series {sorted(EXCHANGE_SERIES)}, got {sorted(frame.columns)}")
    return frame.rename(columns=EXCHANGE_SERIES)[list(EXCHANGE_SERIES.values())], bad


def build_swissgrid_overview(start_day, end_day, index) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    years = range(pd.Timestamp(start_day).year, pd.Timestamp(end_day).year + 1)
    paths = [swissgrid.RAW / "energy_overview" / f"EnergieUebersichtCH-{y}.xlsx" for y in years]
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"run download.py first, missing: {[str(p) for p in missing]}")
    frame, bad = assemble_hourly([swissgrid.read_energy_overview(p) for p in paths], index, "mean")
    for node in NEIGHBOURS:
        c = COUNTRY_OF_NODE[node]
        frame[f"phys_net_import_{node}"] = frame[f"phys_{c}_to_CH"] - frame[f"phys_CH_to_{c}"]
    return frame, bad


def build_physical_metered(overview: pd.DataFrame) -> pd.DataFrame:
    """Physical flow per border from Swissgrid's metered exchanges, MW, + = import into CH; columns as cbpf.

    Used instead of Energy-Charts cbpf: on the FR border Energy-Charts shows about 15% more flow than
    Swissgrid metering, in both directions and in every month since Oct 2023. BFE monthly imports agree with
    Swissgrid within 13-64 GWh per month. The Swissgrid workbook lags about one month.
    """
    out = pd.DataFrame({node: overview[f"phys_net_import_{node}"] for node in NEIGHBOURS}, index=overview.index)
    out["sum"] = out[NEIGHBOURS].sum(axis=1, min_count=len(NEIGHBOURS))
    return out


def build_swissgrid_cross_border(start_day, end_day, index) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    years = range(pd.Timestamp(start_day).year, pd.Timestamp(end_day).year + 1)
    paths = [swissgrid.RAW / "cross_border_flows" / f"Grenzfluesse-{y}.csv" for y in years]
    present = [p for p in paths if p.exists()]
    if not present:
        raise FileNotFoundError("no Swissgrid cross-border flow file for this period")
    frames = [swissgrid.read_cross_border_flows(p) for p in present]
    for path, frame in zip(present, frames):
        flagged = {k: v for k, v in frame.attrs["invalid_values"].items() if v}
        if flagged:
            print(f"  {path.name}: invalid intraday NTC quarter-hours set to NaN: {flagged}")
    # Intraday NTC columns are limits (CAPACITY_HOURLY_RULE); flows and spreads are averaged.
    limits = [c for c in frames[0].columns if c.startswith("ntc_id_")]
    caps, _ = assemble_hourly([f[limits] for f in frames], index, CAPACITY_HOURLY_RULE)
    rest, bad = assemble_hourly([f.drop(columns=limits) for f in frames], index, "mean")
    return pd.concat([caps, rest], axis=1)[list(frames[0].columns)], bad


def build_ntc_swissgrid_d2(start_day, end_day, index) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    days = pd.date_range(start_day, end_day, freq="D")
    paths = [swissgrid.RAW / "ntc_d2" / f"NTC-{d:%Y%m%d}.xml" for d in days]
    frames = [swissgrid.read_ntc_d2(p) for p in paths if p.exists()]
    if not frames:
        raise FileNotFoundError("no Swissgrid D-2 NTC file for this period")
    frame, bad = assemble_hourly(frames, index, CAPACITY_HOURLY_RULE)
    unknown = [c for c in frame.columns if c not in DIRECTIONS]
    absent = [d for d in DIRECTIONS if d not in frame.columns]
    if unknown or absent:
        raise ValueError(f"D-2 NTC: unexpected directions {unknown}, directions in no file {absent}")
    return frame[DIRECTIONS], bad


def build_ntc_entsoe_web(index) -> pd.DataFrame | None:
    """Day-ahead NTC copied from the ENTSO-E web table (raw/entsoe_web/*.txt), or None if absent."""
    if not entsoe_web.RAW.exists() or not any(entsoe_web.RAW.glob("*.txt")):
        return None
    frame = entsoe_web.read_all()
    return frame.reindex(index)[DIRECTIONS]


def combine_dayahead_ntc(d2: pd.DataFrame, web: pd.DataFrame | None, preferred_days: tuple[str, ...]) -> pd.DataFrame:
    """One day-ahead NTC table: Swissgrid D-2 where it has a value, else the ENTSO-E web copy; on
    preferred_days (local dates) the ENTSO-E web copy is used in every direction.

    The two are the same product (identical on every compared 2026 day, see
    validation_report.csv). The column source_<direction> names the source of each value.
    """
    local_day = pd.Index(d2.index.tz_convert(LOCAL_TZ).strftime("%Y-%m-%d"))
    preferred = local_day.isin(preferred_days)
    for day in set(preferred_days) & set(local_day):
        rows = local_day == day
        if web is None or web.loc[rows, DIRECTIONS].isna().any().any():
            raise ValueError(f"preferred day {day} needs a complete ENTSO-E web copy in raw/entsoe_web/")
    out = d2.copy()
    for d in DIRECTIONS:
        source = pd.Series("swissgrid_d2", index=d2.index).where(d2[d].notna(), "")
        if web is not None:
            use_web = (d2[d].isna() | preferred) & web[d].notna()
            out[d] = d2[d].where(~use_web, web[d])
            source = source.where(~use_web, "entsoe_web")
        out[f"source_{d}"] = source
    return out


def build_ntc_entsoe(start_day, end_day, index) -> tuple[pd.DataFrame, pd.DatetimeIndex] | None:
    """Day-ahead NTC from ENTSO-E A61, or None when nothing was downloaded yet."""
    chunks = year_chunks(start_day, end_day)
    paths = {d: [entsoe_ntc.RAW / f"A61_{d}_{a}_{b}.xml" for a, b in chunks] for d in DIRECTIONS}
    if not any(p.exists() for ps in paths.values() for p in ps):
        return None
    columns, bad_all = {}, []
    for direction, ps in paths.items():
        missing = [p for p in ps if not p.exists()]
        if missing:
            raise FileNotFoundError(f"ENTSO-E NTC incomplete, missing: {[str(p) for p in missing]}")
        pieces = [entsoe_ntc.parse(p.read_text(encoding="utf-8")).to_frame(direction) for p in ps]
        frame, bad = assemble_hourly(pieces, index, CAPACITY_HOURLY_RULE)
        columns[direction] = frame[direction]
        bad_all.extend(bad)
    return pd.DataFrame(columns, index=index), pd.DatetimeIndex(sorted(set(bad_all)))


def build_nuclear(public_power: pd.DataFrame, start_day, end_day) -> pd.DataFrame:
    """Hourly nuclear availability estimated from the generation profile.

    available_MW is the observed net generation; outage_MW = net capacity - generation, which
    covers planned and forced outages and derating (e.g. Beznau's river-temperature limits).
    """
    capacity = sum(NUCLEAR_UNITS_NET_MW.values())
    raw = RAW_DIR / "energy_charts" / "installed_power" / "installed_power_ch_yearly.json"
    installed = energy_charts.parse_installed_power(json.loads(raw.read_text(encoding="utf-8")))["nuclear"]
    for year in range(pd.Timestamp(start_day).year, pd.Timestamp(end_day).year + 1):
        if year in installed.index and abs(installed[year] - capacity) > 1.0:
            raise ValueError(f"nuclear capacity {capacity} MW in config differs from Energy-Charts "
                             f"{installed[year]} MW for {year}; update NUCLEAR_UNITS_NET_MW")
    gen = public_power["nuclear"]
    out = pd.DataFrame({"generation_MW": gen, "net_capacity_MW": capacity}, index=public_power.index)
    out["outage_MW"] = capacity - gen
    out["availability"] = gen / capacity
    return out


def build_reservoir(start_day, end_day) -> pd.DataFrame:
    weekly = bfe.read(bfe.RAW_FILE)
    first, last = pd.Timestamp(start_day), pd.Timestamp(end_day)
    before = weekly.index[weekly.index < first]
    if len(before) == 0:
        raise ValueError(f"BFE reservoir data starts {weekly.index[0].date()}, after {start_day}")
    # Keep the last reading before the period so the starting level is known.
    return weekly[(weekly.index >= before[-1]) & (weekly.index <= last + pd.Timedelta(days=7))]


def coverage(tables: dict[str, pd.DataFrame], irregular: dict[str, pd.DatetimeIndex]) -> pd.DataFrame:
    rows = []
    for name, frame in tables.items():
        for col in frame.columns:
            s = frame[col]
            miss = s.isna()
            runs = miss.ne(miss.shift()).cumsum()[miss]
            longest = int(runs.value_counts().max()) if miss.any() else 0
            rows.append({
                "table": name, "column": col, "hours": len(s), "missing_hours": int(miss.sum()),
                "longest_gap_hours": longest,
                "first_valid_utc": s.first_valid_index(), "last_valid_utc": s.last_valid_index(),
                "irregular_hours_in_table": len(irregular.get(name, [])),
            })
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", required=True, help="first local day, YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="last local day (inclusive), YYYY-MM-DD")
    args = parser.parse_args(argv)
    start_day, end_day = args.start, args.end
    period_bounds_utc(start_day, end_day)
    index = hourly_index(start_day, end_day)
    out = output_dir(start_day, end_day)
    out.mkdir(parents=True, exist_ok=True)

    tables, irregular = {}, {}
    print("prices"); tables["prices_day_ahead"], irregular["prices_day_ahead"] = build_prices(start_day, end_day, index)
    print("CH generation and load"); tables["ch_public_power"], irregular["ch_public_power"] = energy_charts_table(
        "public_power", "ch", start_day, end_day, index)
    print("scheduled exchanges"); tables["ch_exchanges_scheduled"], irregular["ch_exchanges_scheduled"] = build_exchanges(
        "cbet", start_day, end_day, index)
    # Energy-Charts physical flows are kept for reference only; the FR border is inflated (build_physical_metered).
    print("physical flows, Energy-Charts (reference only)")
    tables["ch_exchanges_physical_energy_charts"], irregular["ch_exchanges_physical_energy_charts"] = build_exchanges(
        "cbpf", start_day, end_day, index)
    print("Swissgrid energy overview (slow: large xlsx)")
    tables["swissgrid_overview"], irregular["swissgrid_overview"] = build_swissgrid_overview(start_day, end_day, index)
    print("physical flows, Swissgrid metered (used)")
    tables["ch_exchanges_physical"] = build_physical_metered(tables["swissgrid_overview"])
    irregular["ch_exchanges_physical"] = irregular["swissgrid_overview"]
    print("Swissgrid cross-border flows")
    tables["swissgrid_cross_border"], irregular["swissgrid_cross_border"] = build_swissgrid_cross_border(
        start_day, end_day, index)
    print("Swissgrid D-2 NTC"); tables["ntc_swissgrid_d2"], irregular["ntc_swissgrid_d2"] = build_ntc_swissgrid_d2(
        start_day, end_day, index)
    web = build_ntc_entsoe_web(index)
    if web is None:
        print("ENTSO-E web copy: none in raw/entsoe_web, table skipped")
    else:
        print("ENTSO-E web copy of day-ahead NTC"); tables["ntc_entsoe_web"] = web
    tables["ntc_dayahead_combined"] = combine_dayahead_ntc(tables["ntc_swissgrid_d2"], web,
                                                           NTC_ENTSOE_WEB_PREFERRED_DAYS)
    entsoe = build_ntc_entsoe(start_day, end_day, index)
    if entsoe is None:
        print("ENTSO-E NTC: not downloaded yet (needs ENTSOE_API_KEY), table skipped")
    else:
        tables["ntc_entsoe_a61"], irregular["ntc_entsoe_a61"] = entsoe
    print("nuclear"); tables["nuclear_availability"] = build_nuclear(tables["ch_public_power"], start_day, end_day)
    print("demand, option A")
    if not bfe.BALANCE_FILE.exists():
        raise FileNotFoundError(f"run download.py --sources bfe first, missing: {bfe.BALANCE_FILE}")
    tables["ch_demand_option_a"] = demand.build_demand_option_a(
        tables["swissgrid_overview"]["consumption_end_users"], tables["ch_public_power"]["solar"],
        bfe.read_balance(bfe.BALANCE_FILE), ONSITE_SOLAR_SHARE)

    for name, frame in tables.items():
        frame.to_csv(out / f"{name}_hourly.csv", float_format="%.3f")
    build_reservoir(start_day, end_day).to_csv(out / "reservoir_weekly_bfe.csv")
    validation = checks.run_all(tables)
    validation.to_csv(out / "validation_report.csv", index=False, float_format="%.3f")
    print(validation.to_string(max_colwidth=40))
    report = coverage(tables, irregular)
    report.to_csv(out / "coverage_report.csv", index=False)
    print(report.groupby("table")[["hours", "missing_hours", "irregular_hours_in_table"]].max().to_string())
    start_utc, end_utc = period_bounds_utc(start_day, end_day)
    provenance.write(out, {"start_local_day": start_day, "end_local_day_inclusive": end_day, "timezone": LOCAL_TZ,
                           "start_utc": start_utc.isoformat(), "end_utc_exclusive": end_utc.isoformat(),
                           "hours": len(index)})
    print(f"written to {out} (with provenance.json)")


if __name__ == "__main__":
    main()
