"""BFE open data: ogd17 weekly filling of Swiss storage lakes (GWh) by region, 2000 to today, and
ogd35 monthly national electricity balance (GWh)."""
from pathlib import Path

import pandas as pd

from data_prep.historical import http_get
from data_prep.historical.config import BFE_BALANCE_URL, BFE_RESERVOIR_URL, RAW_DIR

RAW_FILE = RAW_DIR / "bfe" / "ogd17_fuellungsgrad_speicherseen.csv"
BALANCE_FILE = RAW_DIR / "bfe" / "ogd35_schweizerische_elektrizitaetsbilanz_monatswerte.csv"
REGIONS = ["Wallis", "Graubuenden", "Tessin", "UebrigCH", "TotalCH"]
BALANCE_COLUMNS = ["Definitiv", "Endverbrauch_GWh", "Verluste_GWh", "Landesverbrauch_GWh",
                   "Verbrauch_Speicherpumpen_GWh", "Erzeugung_Photovoltaik_GWh"]


def download(force: bool) -> list[Path]:
    return [http_get.download(BFE_RESERVOIR_URL, RAW_FILE, force),
            http_get.download(BFE_BALANCE_URL, BALANCE_FILE, force)]


def read(path: Path) -> pd.DataFrame:
    """-> frame indexed by date, columns <region>_GWh and <region>_max_GWh."""
    raw = pd.read_csv(path, parse_dates=["Datum"])
    out = pd.DataFrame(index=pd.DatetimeIndex(raw["Datum"], name="date"))
    for region in REGIONS:
        out[f"{region}_GWh"] = pd.to_numeric(raw[f"{region}_speicherinhalt_gwh"], errors="raise").to_numpy()
        out[f"{region}_max_GWh"] = pd.to_numeric(raw[f"{region}_max_speicherinhalt_gwh"], errors="raise").to_numpy()
    if not out.index.is_unique:
        raise ValueError(f"{path.name}: duplicate dates")
    return out.sort_index()


def read_balance(path: Path) -> pd.DataFrame:
    """ogd35 -> frame indexed by month start (naive local date), all columns of the file.

    Raises if a month appears twice or if Landesverbrauch differs from Endverbrauch + Verluste,
    the identity the demand construction relies on.
    """
    raw = pd.read_csv(path)
    missing = [c for c in ["Jahr", "Monat", *BALANCE_COLUMNS] if c not in raw.columns]
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}")
    raw.index = pd.DatetimeIndex(pd.to_datetime(dict(year=raw.Jahr, month=raw.Monat, day=1)), name="month")
    if not raw.index.is_unique:
        raise ValueError(f"{path.name}: duplicate months")
    gap = (raw.Endverbrauch_GWh + raw.Verluste_GWh - raw.Landesverbrauch_GWh).abs()
    if (gap > 1.0).any():
        raise ValueError(f"{path.name}: Landesverbrauch != Endverbrauch + Verluste in {list(raw.index[gap > 1.0].date)}")
    return raw.sort_index()
