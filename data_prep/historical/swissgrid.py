"""Swissgrid public data: energy overview (15-min CH load/production/physical exchanges, one
xlsx per year), cross-border flows (15-min intraday NTC, commercial flows, price spreads; only the
current year is published) and D-2 NTC (hourly day-ahead NTC per direction, one XML per day;
only the current year is published).

File URLs carry random repository ids, so they are read from the listing pages.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from data_prep.historical import http_get
from data_prep.historical.config import RAW_DIR, SWISSGRID_PAGES
from data_prep.historical.timeutils import localize_local_wall_clock

RAW = RAW_DIR / "swissgrid"
_LINK = re.compile(r'href="(https://www\.swissgrid\.ch/dam/jcr:[0-9a-f-]+/([^"/]+))"')

# Energy overview columns kept, by the German part of the two-line header -> output name.
OVERVIEW_COLUMNS = {
    "Summe endverbrauchte Energie Regelblock Schweiz": "consumption_end_users",
    "Summe produzierte Energie Regelblock Schweiz": "production",
    "Summe verbrauchte Energie Regelblock Schweiz": "consumption_control_block",
    "Verbundaustausch CH->AT": "phys_CH_to_AT",
    "Verbundaustausch AT->CH": "phys_AT_to_CH",
    "Verbundaustausch CH->DE": "phys_CH_to_DE",
    "Verbundaustausch DE->CH": "phys_DE_to_CH",
    "Verbundaustausch CH->FR": "phys_CH_to_FR",
    "Verbundaustausch FR->CH": "phys_FR_to_CH",
    "Verbundaustausch CH->IT": "phys_CH_to_IT",
    "Verbundaustausch IT->CH": "phys_IT_to_CH",
}

NOT_YET_DEFINED = "n.y.d."  # D-2 NTC marker for an hour without a defined NTC
NTC_PLACEHOLDER = 99999  # Swissgrid's "no value" marker in the intraday NTC columns

# Cross-border flows CSV: German country name in the header -> two-letter code.
_COUNTRY = {"Österreich": "AT", "Deutschland": "DE", "Frankreich": "FR", "Italien": "IT", "Italien Nord": "IT"}


def list_files(page_key: str) -> dict[str, str]:
    """File name -> download URL for every repository file linked on a Swissgrid listing page.

    The listing is fetched fresh on every run and saved under raw/swissgrid/listings.
    """
    page = http_get.download(SWISSGRID_PAGES[page_key], RAW / "listings" / f"{page_key}.html", force=True)
    files: dict[str, str] = {}
    for url, name in _LINK.findall(page.read_text(encoding="utf-8")):
        if name in files and files[name] != url:
            raise ValueError(f"{page_key}: two different files named {name}: {files[name]} and {url}")
        files[name] = url
    return files


def download_listed(page_key: str, wanted: list[str], force: bool) -> dict[str, Path | None]:
    """Download the wanted file names from a listing page. Names not listed map to None."""
    listed = list_files(page_key)
    out: dict[str, Path | None] = {}
    for name in wanted:
        if name not in listed:
            out[name] = None
            continue
        out[name] = http_get.download(listed[name], RAW / page_key / name, force, min_interval_s=0.5,
                                      host_key="swissgrid")
    missing = [name for name, path in out.items() if path is None]
    if missing:
        print(f"  {len(missing)} of {len(wanted)} files not published by Swissgrid "
              f"(first: {missing[0]}, last: {missing[-1]})")
    return out


def read_energy_overview(path: Path) -> pd.DataFrame:
    """EnergieUebersichtCH-<year>.xlsx -> 15-min frame in MW (average power), UTC interval start.

    Swissgrid changed its stamp convention: up to the 2024 file each row is stamped with the END of
    its quarter-hour (first row 1 Jan 00:15), from 2025 with the START (first row 1 Jan 00:00).
    The convention is read from the first row; any other first stamp raises.
    """
    raw = pd.read_excel(path, sheet_name="Zeitreihen0h15", header=None, engine="openpyxl")
    header = raw.iloc[0].astype(str).str.split("\n").str[0].str.strip()
    units = raw.iloc[1]
    keep = {}
    for german, name in OVERVIEW_COLUMNS.items():
        hits = header.index[header == german].tolist()
        if len(hits) != 1:
            raise ValueError(f"{path.name}: expected one column '{german}', found {len(hits)}")
        if units[hits[0]] != "kWh":
            raise ValueError(f"{path.name}: column '{german}' has unit {units[hits[0]]!r}, expected kWh")
        keep[name] = hits[0]
    body = raw.iloc[2:]
    stamps = pd.to_datetime(body[0], format="%d.%m.%Y %H:%M")
    first = stamps.iloc[0]
    if (first.month, first.day, first.hour) != (1, 1, 0) or first.minute not in (0, 15):
        raise ValueError(f"{path.name}: first stamp {first} is neither 1 Jan 00:00 nor 00:15")
    index = localize_local_wall_clock(stamps)
    if first.minute == 15:  # end-stamped: shift in UTC so DST transitions stay exact
        index = index - pd.Timedelta(minutes=15)
    frame = pd.DataFrame(
        {name: pd.to_numeric(body[col], errors="raise").to_numpy() for name, col in keep.items()},
        index=index,
    )
    frame.index.name = "time_utc"
    return frame / 250.0  # kWh per 15 min -> MW


def read_cross_border_flows(path: Path) -> pd.DataFrame:
    """Grenzfluesse-<year>.csv -> 15-min frame, UTC interval start.

    Columns: ntc_id_<X>_to_<Y> (MW, positive), comm_net_<C> (MW, as published),
    spread_<C>_minus_CH (EUR/MWh, neighbour minus CH as published).

    Intraday NTC is published with a sign (export from CH positive, import negative). Values with
    the other sign or the 99999 placeholder are invalid: they become NaN and their count per
    column is kept in frame.attrs["invalid_values"].
    """
    raw = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    out, invalid = {}, {}
    for col in raw.columns[1:]:
        title = col.split(":", 1)[1]
        if m := re.match(r"Intraday NTC (\S+) > (\S+) \[MW\]", title):
            a, b = ("CH" if x == "Schweiz" else _COUNTRY[x] for x in m.groups())
            values = pd.to_numeric(raw[col], errors="raise") * (1 if a == "CH" else -1)
            bad = (values < 0) | (values.abs() >= NTC_PLACEHOLDER)
            name = f"ntc_id_{a}_to_{b}"
            invalid[name] = int(bad.sum())
            out[name] = values.mask(bad)
        elif m := re.match(r"Kommerzielle Lastflüsse (.+) Netto \(Total\) \[MW\]", title):
            key = "sum" if m.group(1).startswith("Summe") else _COUNTRY[m.group(1)]
            out[f"comm_net_{key}"] = pd.to_numeric(raw[col], errors="raise")
        elif m := re.match(r"Preisdifferenz Spot (.+)-Schweiz \[EUR/MWh\]", title):
            out[f"spread_{_COUNTRY[m.group(1)]}_minus_CH"] = pd.to_numeric(raw[col], errors="raise")
        else:
            raise ValueError(f"{path.name}: unknown column '{col}'")
    frame = pd.DataFrame(out)
    frame.index = localize_local_wall_clock(pd.to_datetime(raw.iloc[:, 0], format="%d.%m.%Y %H:%M"))
    frame.index.name = "time_utc"
    frame.attrs["invalid_values"] = invalid
    return frame


def read_ntc_d2(path: Path) -> pd.DataFrame:
    """NTC-<yyyymmdd>.xml (D-2 NTC, ETSO capacity document) -> frame in MW, one column per
    direction (e.g. CH_to_AT), UTC interval start at the published resolution.

    Swissgrid writes "n.y.d." (not yet defined) where no NTC was set; those become NaN.
    """
    root = ET.parse(path).getroot()
    columns = {}
    for ts in root.iter("CapacityTimeSeries"):
        name = ts.find("TimeSeriesIdentification").get("v")
        if ts.find("MeasurementUnit").get("v") != "MAW":
            raise ValueError(f"{path.name}: {name} is not in MW")
        points = {}
        for period in ts.iter("Period"):
            start = pd.Timestamp(period.find("TimeInterval").get("v").split("/")[0])
            step = pd.Timedelta(period.find("Resolution").get("v"))
            for interval in period.iter("Interval"):
                pos = int(interval.find("Pos").get("v"))
                qty = interval.find("Qty").get("v")
                points[start + (pos - 1) * step] = float("nan") if qty == NOT_YET_DEFINED else float(qty)
        if name in columns:
            raise ValueError(f"{path.name}: time series {name} appears twice")
        columns[name] = pd.Series(points)
    frame = pd.DataFrame(columns).sort_index()
    frame.index.name = "time_utc"
    return frame
