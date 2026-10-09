"""Energy-Charts API (Fraunhofer ISE): day-ahead prices, CH generation/load, CH border exchanges.

Data licence: CC BY 4.0, attribution energy-charts.info (prices for CH, DE-LU, FR, IT-North and
AT: CC BY 4.0 from Bundesnetzagentur | SMARD.de). Each response states its licence; it is kept
in the raw JSON.
"""
import json
import urllib.parse
from pathlib import Path

import pandas as pd

from data_prep.historical import http_get
from data_prep.historical.config import ENERGY_CHARTS_API, ENERGY_CHARTS_MIN_INTERVAL_S, RAW_DIR

RAW = RAW_DIR / "energy_charts"

# endpoint -> unit the parser expects in the response, and factor to MW (or EUR/MWh)
UNIT_TO_MW = {"MW": 1.0, "GW": 1000.0, "EUR / MWh": 1.0}


def raw_path(endpoint: str, key: str, start_day: str, end_day: str) -> Path:
    return RAW / endpoint / f"{endpoint}_{key}_{start_day}_{end_day}.json"


def fetch(endpoint: str, params: dict, dest: Path, force: bool) -> Path:
    url = f"{ENERGY_CHARTS_API}/{endpoint}?{urllib.parse.urlencode(params)}"
    return http_get.download(
        url, dest, force, min_interval_s=ENERGY_CHARTS_MIN_INTERVAL_S, host_key="energy_charts"
    )


def download_price(bzn: str, start_day: str, end_day: str, force: bool) -> Path:
    return fetch("price", {"bzn": bzn, "start": start_day, "end": end_day},
                 raw_path("price", bzn, start_day, end_day), force)


def download_country(endpoint: str, country: str, start_day: str, end_day: str, force: bool) -> Path:
    """endpoint: public_power, cbet (scheduled exchanges) or cbpf (physical flows)."""
    return fetch(endpoint, {"country": country, "start": start_day, "end": end_day},
                 raw_path(endpoint, country, start_day, end_day), force)


def download_installed_power(country: str, force: bool) -> Path:
    return fetch("installed_power", {"country": country, "time_step": "yearly"},
                 RAW / "installed_power" / f"installed_power_{country}_yearly.json", force)


def parse_timeseries(payload: dict) -> pd.DataFrame:
    """v2 time-series response -> frame indexed by UTC interval start, one column per series id,
    converted to MW (power, exchanges) or kept in EUR/MWh (prices). Percent series are dropped."""
    series_units = {s["id"]: s.get("unit", payload["unit"]) for s in payload["series"]}
    rows = [{"time_utc": r["timestamp"], **r["values"]} for r in payload["data"]]
    if not rows:
        raise ValueError(f"{payload['endpoint']}: response has no data")
    frame = pd.DataFrame(rows)
    frame["time_utc"] = pd.to_datetime(frame["time_utc"], utc=True)
    frame = frame.set_index("time_utc").sort_index()
    out = {}
    for sid, unit in series_units.items():
        if unit == "%":
            continue
        if unit not in UNIT_TO_MW:
            raise ValueError(f"{payload['endpoint']}: unexpected unit {unit!r} for series {sid}")
        if sid not in frame.columns:
            raise ValueError(f"{payload['endpoint']}: series {sid} is listed but has no values")
        out[sid] = pd.to_numeric(frame[sid], errors="raise") * UNIT_TO_MW[unit]
    return pd.DataFrame(out, index=frame.index)


def read_raw(path: Path) -> pd.DataFrame:
    return parse_timeseries(json.loads(path.read_text(encoding="utf-8")))


def parse_installed_power(payload: dict) -> pd.DataFrame:
    """installed_power response -> frame indexed by reporting year, values in MW.

    Energy-Charts labels each row with the reporting year; the value is the capacity at its end.
    """
    units = {s["id"]: s["unit"] for s in payload["series"]}
    rows = {}
    for r in payload["data"]:
        year = pd.Timestamp(r["timestamp"]).year
        rows[year] = {}
        for sid, value in r["values"].items():
            if units[sid] != "GW":
                continue
            rows[year][sid] = None if value is None else value * 1000.0
    return pd.DataFrame.from_dict(rows, orient="index").sort_index()
