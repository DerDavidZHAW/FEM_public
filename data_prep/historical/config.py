"""Zones, border directions, source endpoints and paths for the historical CH data pipeline.

All timestamps in processed files are UTC. Periods are given as local (Europe/Zurich) calendar
days, inclusive at both ends, e.g. 2023-10-01 .. 2026-09-30 for three hydrological years.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "input" / "historical" / "raw"
PROCESSED_DIR = REPO_ROOT / "input" / "historical" / "processed"
PLOTS_DIR = REPO_ROOT / "plots"

LOCAL_TZ = "Europe/Zurich"

# FEM node -> bidding zone code per source. CH and its four neighbours as used in CH_only mode.
ZONES = {
    "CH00": {"energy_charts": "CH", "entsoe": "10YCH-SWISSGRIDZ", "label": "CH"},
    "DE00": {"energy_charts": "DE-LU", "entsoe": "10Y1001A1001A82H", "label": "DE-LU"},
    "FR00": {"energy_charts": "FR", "entsoe": "10YFR-RTE------C", "label": "FR"},
    "IT00": {"energy_charts": "IT-North", "entsoe": "10Y1001A1001A73I", "label": "IT-North"},
    "AT00": {"energy_charts": "AT", "entsoe": "10YAT-APG------L", "label": "AT"},
}
NEIGHBOURS = ["DE00", "FR00", "IT00", "AT00"]

# Border directions, named <exporting>_to_<importing> with two-letter country codes.
# These match the TimeSeriesIdentification in Swissgrid's D-2 NTC files.
COUNTRY_OF_NODE = {"CH00": "CH", "DE00": "DE", "FR00": "FR", "IT00": "IT", "AT00": "AT"}
DIRECTIONS = [
    f"{a}_to_{b}"
    for n in NEIGHBOURS
    for a, b in (("CH", COUNTRY_OF_NODE[n]), (COUNTRY_OF_NODE[n], "CH"))
]

# Rule for turning sub-hourly transfer capacities (NTC) into one hourly limit:
#   "min"  - FEM has one constant flow per hour, so it must respect every quarter-hour limit
#            (also matches hourly capacity products); the matching price rule is the hourly mean.
#   "mean" - the hourly value is an energy total and flows may differ between quarter-hours.
# Prices and power are always averaged. With hourly source limits both rules give the same value.
CAPACITY_HOURLY_RULE = "min"

# Local days on which the ENTSO-E web copy replaces Swissgrid D-2 NTC in all eight directions, because
# Swissgrid's public file for the day is an early revision (2026-09-24: version 1 with "n.y.d."). Chosen by
# the user on 2026-10-09; the data is in raw/entsoe_web/part_2026-09-24.txt.
NTC_ENTSOE_WEB_PREFERRED_DAYS = ("2026-09-24",)

ENERGY_CHARTS_API ="https://api.energy-charts.info/v2"
# Energy-Charts allows 2 requests per minute (HTTP 429 above that).
ENERGY_CHARTS_MIN_INTERVAL_S = 31

SWISSGRID_PAGES = {
    "energy_overview": "https://www.swissgrid.ch/en/home/operation/grid-data/transmission.html",
    "cross_border_flows": "https://www.swissgrid.ch/en/home/operation/grid-data/cross-border-load-flows.html",
    "ntc_d2": "https://www.swissgrid.ch/en/home/customers/topics/congestion-mgmt/ntc/d-2-ntc.html",
}

# BFE's own open-data host. The uvek-gis.admin.ch mirror used before 2026-10-09 lagged: on 9 Oct 2026 it
# lacked the 5 Oct 2026 reading that bfe-ogd.ch already served (identical values otherwise).
BFE_RESERVOIR_URL = "https://www.bfe-ogd.ch/ogd17/ogd17_fuellungsgrad_speicherseen.csv"
# Share of on-site consumption (BFE Endverbrauch minus Swissgrid end-user consumption) that is placed in
# the hours like PV output; the rest is spread flat over the month. ASSUMPTION, not an observation: the
# split between self-consumed PV and other on-site generation is not published. 0.5 is the midpoint
# between the two extremes 0 (all flat) and 1 (all PV-shaped); chosen by the user on 2026-10-09 to avoid
# running both extremes. See demand.py.
ONSITE_SOLAR_SHARE = 0.5

# Monthly national electricity balance (GWh): production by type, storage pumping, imports/exports,
# Endverbrauch (end use), Verluste (grid losses), Landesverbrauch = Endverbrauch + Verluste.
BFE_BALANCE_URL = "https://www.bfe-ogd.ch/ogd35/ogd35_schweizerische_elektrizitaetsbilanz_monatswerte.csv"

ENTSOE_API = "https://web-api.tp.entsoe.eu/api"
ENTSOE_TOKEN_ENV = "ENTSOE_API_KEY"

# Net electrical capacity of the Swiss nuclear units (MW), unchanged since Muehleberg shut down
# in Dec 2019. Only the total is used; process.py checks it against Energy-Charts installed_power
# for every year Energy-Charts publishes and raises on a mismatch.
NUCLEAR_UNITS_NET_MW = {
    "Beznau 1": 365.0,
    "Beznau 2": 365.0,
    "Goesgen": 1010.0,
    "Leibstadt": 1233.0,
}

USER_AGENT = "FEM-historical-data/1.0 (research use; Future Markets model)"
