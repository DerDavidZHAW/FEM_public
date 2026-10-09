"""Period handling and resampling. Processed data is hourly, UTC, interval-start stamped."""
import pandas as pd

from data_prep.historical.config import LOCAL_TZ


def period_bounds_utc(start_day: str, end_day: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Local days start_day..end_day (inclusive) -> [start, end) in UTC."""
    start = pd.Timestamp(start_day).tz_localize(LOCAL_TZ)
    end = (pd.Timestamp(end_day) + pd.Timedelta(days=1)).tz_localize(LOCAL_TZ)
    if end <= start:
        raise ValueError(f"end day {end_day} is before start day {start_day}")
    return start.tz_convert("UTC"), end.tz_convert("UTC")


def hourly_index(start_day: str, end_day: str) -> pd.DatetimeIndex:
    start, end = period_bounds_utc(start_day, end_day)
    return pd.date_range(start, end, freq="h", inclusive="left", name="time_utc")


def year_chunks(start_day: str, end_day: str) -> list[tuple[str, str]]:
    """Split local days start_day..end_day into consecutive pieces of at most one year."""
    chunks = []
    first = pd.Timestamp(start_day)
    last = pd.Timestamp(end_day)
    while first <= last:
        piece_end = min(first + pd.DateOffset(years=1) - pd.Timedelta(days=1), last)
        chunks.append((first.strftime("%Y-%m-%d"), piece_end.strftime("%Y-%m-%d")))
        first = piece_end + pd.Timedelta(days=1)
    return chunks


def localize_local_wall_clock(stamps: pd.Series) -> pd.DatetimeIndex:
    """Naive Swiss wall-clock stamps (repeated 02:00-02:59 in autumn) -> UTC.

    The repeated hour is resolved from row order; a missing spring hour is fine, any stamp that
    cannot exist raises.
    """
    local = pd.DatetimeIndex(stamps).tz_localize(LOCAL_TZ, ambiguous="infer", nonexistent="raise")
    return local.tz_convert("UTC")


HOURLY_RULES = ("mean", "min")


def to_hourly(frame: pd.DataFrame, rule: str) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    """Aggregate a UTC-indexed frame to hours with rule "mean" (power, prices) or "min" (limits).

    An hour is valid if its stamps are exactly :00 (hourly data) or exactly :00/:15/:30/:45
    (quarter-hourly data). Invalid hours become NaN and are returned as the second value.
    A NaN in any quarter of a valid hour gives NaN for that column (no partial aggregates).
    """
    if rule not in HOURLY_RULES:
        raise ValueError(f"unknown hourly rule {rule!r}; expected one of {HOURLY_RULES}")
    if not frame.index.is_unique:
        raise ValueError(f"duplicate timestamps: {frame.index[frame.index.duplicated()][:5].tolist()}")
    if not frame.index.is_monotonic_increasing:
        raise ValueError("timestamps are not sorted")
    hour = frame.index.floor("h")
    minutes = pd.Series(frame.index.minute, index=frame.index)
    pattern = minutes.groupby(hour).agg(lambda m: tuple(m))
    valid = pattern.isin([(0,), (0, 15, 30, 45)])
    hourly = frame.groupby(hour).agg(rule)
    hourly = hourly.mask(frame.isna().groupby(hour).any())
    hourly.index.name = "time_utc"
    invalid_hours = pattern.index[~valid.values]
    hourly.loc[invalid_hours] = float("nan")
    return hourly, pd.DatetimeIndex(invalid_hours, name="time_utc")
