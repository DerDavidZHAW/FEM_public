"""ENTSO-E Transparency Platform: forecasted day-ahead transfer capacity (NTC, document type A61)
for the eight CH border directions.

Needs a personal API token in the environment variable ENTSOE_API_KEY (request it from
transparency@entsoe.eu with subject "Restful API access" after registering on the platform).
Not yet run against the live API: the CH-border coverage of A61 is unconfirmed.
"""
import os
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from data_prep.historical import http_get
from data_prep.historical.config import (
    COUNTRY_OF_NODE, DIRECTIONS, ENTSOE_API, ENTSOE_TOKEN_ENV, RAW_DIR, ZONES,
)
from data_prep.historical.timeutils import period_bounds_utc

RAW = RAW_DIR / "entsoe" / "ntc_dayahead_A61"
_EIC = {COUNTRY_OF_NODE[node]: z["entsoe"] for node, z in ZONES.items()}


def token() -> str:
    value = os.environ.get(ENTSOE_TOKEN_ENV, "").strip()
    if not value:
        raise RuntimeError(
            f"ENTSO-E NTC download needs an API token in the environment variable {ENTSOE_TOKEN_ENV}. "
            "Register on transparency.entsoe.eu and email transparency@entsoe.eu "
            "(subject 'Restful API access') to get one."
        )
    return value


def download(direction: str, start_day: str, end_day: str, force: bool) -> Path:
    """One direction (e.g. 'DE_to_CH'), local days start_day..end_day, at most one year."""
    if direction not in DIRECTIONS:
        raise ValueError(f"unknown direction {direction}; expected one of {DIRECTIONS}")
    exporter, importer = direction.split("_to_")
    start, end = period_bounds_utc(start_day, end_day)
    params = {
        "documentType": "A61",
        "contract_MarketAgreement.Type": "A01",  # day-ahead
        "out_Domain": _EIC[exporter],
        "in_Domain": _EIC[importer],
        "periodStart": start.strftime("%Y%m%d%H%M"),
        "periodEnd": end.strftime("%Y%m%d%H%M"),
    }
    dest = RAW / f"A61_{direction}_{start_day}_{end_day}.xml"
    url = f"{ENTSOE_API}?{urllib.parse.urlencode({**params, 'securityToken': token()})}"
    return http_get.download(url, dest, force, min_interval_s=1.0, host_key="entsoe")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse(xml_text: str) -> pd.Series:
    """Publication_MarketDocument -> MW series at the published resolution, UTC interval start.

    An Acknowledgement_MarketDocument (ENTSO-E's 'no data' reply) raises with its reason text.
    """
    root = ET.fromstring(xml_text)
    if _local(root.tag) == "Acknowledgement_MarketDocument":
        reason = " ".join(e.text or "" for e in root.iter() if _local(e.tag) == "text")
        raise ValueError(f"ENTSO-E returned no data: {reason.strip()}")
    points = {}
    for series_el in (e for e in root.iter() if _local(e.tag) == "TimeSeries"):
        curve = next((c.text for c in series_el if _local(c.tag) == "curveType"), "A01")
        if curve not in ("A01", "A03"):
            raise ValueError(f"unsupported curveType {curve}")
        for period in (e for e in series_el if _local(e.tag) == "Period"):
            children = {_local(c.tag): c for c in period}
            bounds = {_local(c.tag): pd.Timestamp(c.text) for c in children["timeInterval"]}
            step = pd.Timedelta(children["resolution"].text)
            n_steps = int((bounds["end"] - bounds["start"]) / step)
            values = {}
            for point in (c for c in period if _local(c.tag) == "Point"):
                fields = {_local(c.tag): c.text for c in point}
                values[int(fields["position"])] = float(fields["quantity"])
            # A03 (variable-sized blocks): a position holds until the next listed position.
            positions = range(1, n_steps + 1) if curve == "A03" else sorted(values)
            current = None
            for pos in positions:
                current = values.get(pos, current)
                if current is None:
                    raise ValueError(f"A03 period starting {bounds['start']} has no value at position 1")
                stamp = bounds["start"] + (pos - 1) * step
                if stamp in points:
                    raise ValueError(f"two values for {stamp}")
                points[stamp] = current
    if not points:
        raise ValueError("ENTSO-E document has no points")
    series = pd.Series(points).sort_index()
    series.index.name = "time_utc"
    return series
