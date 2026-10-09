"""Day-ahead NTC copied by hand from the ENTSO-E Transparency Platform web table (TR 11.1,
Forecast Transfer Capacities, day-ahead, BZN|CH). A stopgap until the API token arrives;
the API (entsoe_ntc.py) is the reproducible route.

File format (raw/entsoe_web/*.txt): lines "<local date>|<hours>|<checksum>|<h1>;<h2>;...", each hour
"CH_to_AT,AT_to_CH,CH_to_DE,DE_to_CH,CH_to_FR,FR_to_CH,CH_to_IT,IT_to_CH" in MW ("n/e" = not expected).
The checksum is the sum of all numeric values of the day, computed in the browser when the page was
read; it is recomputed here so copying errors raise.
"""
from pathlib import Path

import pandas as pd

from data_prep.historical.config import LOCAL_TZ, RAW_DIR

RAW = RAW_DIR / "entsoe_web"
COLUMNS = ["CH_to_AT", "AT_to_CH", "CH_to_DE", "DE_to_CH", "CH_to_FR", "FR_to_CH", "CH_to_IT", "IT_to_CH"]


def parse_line(line: str) -> pd.DataFrame:
    """One day -> frame indexed by UTC hour start; raises on wrong hour count or checksum."""
    day, hours, checksum, body = line.strip().split("|")
    rows = [h.split(",") for h in body.split(";")]
    if len(rows) != int(hours) or any(len(r) != len(COLUMNS) for r in rows):
        raise ValueError(f"{day}: expected {hours} rows of {len(COLUMNS)} values")
    start = pd.Timestamp(day).tz_localize(LOCAL_TZ)
    end = (pd.Timestamp(day) + pd.Timedelta(days=1)).tz_localize(LOCAL_TZ)
    index = pd.date_range(start.tz_convert("UTC"), end.tz_convert("UTC"), freq="h", inclusive="left", name="time_utc")
    if len(index) != len(rows):
        raise ValueError(f"{day}: {len(rows)} rows but the local day has {len(index)} hours")
    frame = pd.DataFrame(rows, columns=COLUMNS, index=index).replace("n/e", float("nan")).astype(float)
    if abs(frame.sum().sum() - float(checksum)) > 0.5:
        raise ValueError(f"{day}: checksum {frame.sum().sum()} != recorded {checksum}")
    return frame


def read_all(folder: Path = RAW) -> pd.DataFrame:
    frames = []
    for path in sorted(folder.glob("*.txt")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                frames.append(parse_line(line))
    frame = pd.concat(frames).sort_index()
    if not frame.index.is_unique:
        raise ValueError(f"days copied twice: {frame.index[frame.index.duplicated()][:3].tolist()}")
    return frame


if __name__ == "__main__":
    f = read_all()
    days = sorted(set(f.index.tz_convert(LOCAL_TZ).date))
    print(f"{len(days)} days, {len(f)} hours, {days[0]} .. {days[-1]}; all checksums and hour counts OK")
