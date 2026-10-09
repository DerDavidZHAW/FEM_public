"""Unit tests for the historical CH data pipeline (data_prep/historical). No network access:
every parser is fed a small hand-written fixture in the publisher's format."""
import json

import numpy as np
import openpyxl
import pandas as pd
import pytest

from data_prep.historical import energy_charts, entsoe_ntc, process, swissgrid
from data_prep.historical.timeutils import (
    hourly_index, localize_local_wall_clock, to_hourly, year_chunks,
)


# --- time handling ---------------------------------------------------------------------------

def test_year_chunks_split_hydro_years_and_keep_partial_tail():
    assert year_chunks("2023-10-01", "2026-09-30") == [
        ("2023-10-01", "2024-09-30"), ("2024-10-01", "2025-09-30"), ("2025-10-01", "2026-09-30")]
    assert year_chunks("2025-10-01", "2025-12-31") == [("2025-10-01", "2025-12-31")]


def test_hourly_index_counts_leap_year_and_dst():
    assert len(hourly_index("2024-01-01", "2024-12-31")) == 8784
    idx = hourly_index("2025-03-30", "2025-03-30")  # spring forward: 23 local hours
    assert len(idx) == 23 and str(idx.tz) == "UTC" and idx[0] == pd.Timestamp("2025-03-29 23:00", tz="UTC")


def test_autumn_repeated_hour_is_resolved_by_row_order():
    stamps = pd.Series(["2025-10-26 01:45", "2025-10-26 02:00", "2025-10-26 02:00", "2025-10-26 03:00"])
    utc = localize_local_wall_clock(pd.to_datetime(stamps))
    assert list(utc.strftime("%H:%M")) == ["23:45", "00:00", "01:00", "02:00"]


def test_nonexistent_spring_stamp_raises():
    with pytest.raises(Exception):
        localize_local_wall_clock(pd.to_datetime(pd.Series(["2025-03-30 02:30"])))


def test_quarter_hours_average_and_incomplete_hours_become_nan():
    idx = pd.DatetimeIndex(
        ["2025-10-01 00:00", "2025-10-01 00:15", "2025-10-01 00:30", "2025-10-01 00:45",
         "2025-10-01 01:00", "2025-10-01 01:15", "2025-10-01 01:45",  # 01:30 missing
         "2025-10-01 02:00"], tz="UTC")  # hourly-stamped hour is valid
    frame = pd.DataFrame({"p": [10.0, 20.0, 30.0, 40.0, 1.0, 1.0, 1.0, 7.0]}, index=idx)
    hourly, irregular = to_hourly(frame, "mean")
    assert hourly["p"].tolist()[0] == 25.0 and np.isnan(hourly["p"].iloc[1]) and hourly["p"].iloc[2] == 7.0
    assert list(irregular) == [pd.Timestamp("2025-10-01 01:00", tz="UTC")]


def test_nan_quarter_is_not_averaged_away():
    idx = pd.date_range("2025-10-01", periods=4, freq="15min", tz="UTC")
    hourly, _ = to_hourly(pd.DataFrame({"p": [1.0, np.nan, 1.0, 1.0]}, index=idx), "mean")
    assert np.isnan(hourly["p"].iloc[0])


def test_capacity_rule_min_takes_tightest_quarter_and_mean_averages():
    idx = pd.date_range("2026-09-10", periods=4, freq="15min", tz="UTC")
    limits = pd.DataFrame({"DE_to_CH": [1000.0, 1000.0, 1000.0, 500.0]}, index=idx)
    assert to_hourly(limits, "min")[0]["DE_to_CH"].iloc[0] == 500.0
    assert to_hourly(limits, "mean")[0]["DE_to_CH"].iloc[0] == 875.0


def test_unknown_hourly_rule_raises():
    idx = pd.date_range("2026-09-10", periods=1, freq="h", tz="UTC")
    with pytest.raises(ValueError, match="unknown hourly rule"):
        to_hourly(pd.DataFrame({"x": [1.0]}, index=idx), "max")


def test_capacity_hourly_rule_default_is_min():
    from data_prep.historical.config import CAPACITY_HOURLY_RULE
    assert CAPACITY_HOURLY_RULE == "min"


def test_d2_ntc_quarter_hour_limits_use_capacity_rule(tmp_path, monkeypatch):
    from data_prep.historical.config import DIRECTIONS

    def series(name, values):
        quarters = "".join(f'<Interval><Pos v="{i}"/><Qty v="{q}"/></Interval>' for i, q in enumerate(values, start=1))
        return (f'<CapacityTimeSeries><TimeSeriesIdentification v="{name}"/><MeasurementUnit v="MAW"/>'
                f'<Period><TimeInterval v="2025-12-31T23:00Z/2026-01-01T00:00Z"/><Resolution v="PT15M"/>'
                f'{quarters}</Period></CapacityTimeSeries>')
    body = "".join(series(d, [1200, 1000, 1200, 400] if d == "CH_to_AT" else [900] * 4) for d in DIRECTIONS)
    xml = f"<CapacityDocument>{body}</CapacityDocument>"
    (tmp_path / "ntc_d2").mkdir()
    (tmp_path / "ntc_d2" / "NTC-20260101.xml").write_text(xml, encoding="utf-8")
    monkeypatch.setattr(swissgrid, "RAW", tmp_path)
    frame, _ = process.build_ntc_swissgrid_d2("2026-01-01", "2026-01-01", hourly_index("2026-01-01", "2026-01-01"))
    assert frame["CH_to_AT"].iloc[0] == 400.0  # quarters 1200, 1000, 1200, 400


def test_cross_border_intraday_ntc_uses_min_and_flows_use_mean(tmp_path, monkeypatch):
    header = ("﻿Date Time;B:Intraday NTC Schweiz > Österreich [MW];"
              "J:Kommerzielle Lastflüsse Österreich Netto (Total) [MW]")
    rows = "".join(f"\n01.01.2026 00:{m:02d};{ntc};{flow}" for m, ntc, flow in
                   [(0, 1200, 100), (15, 1200, 200), (30, 800, 300), (45, 1200, 400)])
    (tmp_path / "cross_border_flows").mkdir()
    (tmp_path / "cross_border_flows" / "Grenzfluesse-2026.csv").write_text(header + rows + "\n", encoding="utf-8")
    monkeypatch.setattr(swissgrid, "RAW", tmp_path)
    frame, _ = process.build_swissgrid_cross_border("2026-01-01", "2026-01-01", hourly_index("2026-01-01", "2026-01-01"))
    assert frame["ntc_id_CH_to_AT"].iloc[0] == 800.0
    assert frame["comm_net_AT"].iloc[0] == 250.0


def test_assemble_rejects_overlapping_pieces_and_leaves_gaps_nan():
    index = hourly_index("2024-01-01", "2024-01-01")
    a = pd.DataFrame({"v": [1.0, 2.0]}, index=index[:2])
    with pytest.raises(ValueError, match="overlapping"):
        process.assemble_hourly([a, a], index, "mean")
    out, _ = process.assemble_hourly([a], index, "mean")
    assert out["v"].iloc[:2].tolist() == [1.0, 2.0] and out["v"].iloc[2:].isna().all()


# --- Energy-Charts -------------------------------------------------------------------------

def _ec_payload(unit="GW", values=(0.5, -1.2)):
    return {
        "endpoint": "cbet", "unit": unit,
        "series": [{"id": "germany", "name": "Germany"}, {"id": "share", "name": "x", "unit": "%"}],
        "data": [{"timestamp": "2025-10-26T02:00:00+02:00", "values": {"germany": values[0], "share": 5}},
                 {"timestamp": "2025-10-26T02:00:00+01:00", "values": {"germany": values[1], "share": 5}}],
    }


def test_energy_charts_converts_gw_to_mw_utc_and_drops_percent():
    frame = energy_charts.parse_timeseries(_ec_payload())
    assert list(frame.columns) == ["germany"]
    assert frame["germany"].tolist() == [500.0, -1200.0]
    assert list(frame.index) == [pd.Timestamp("2025-10-26 00:00", tz="UTC"), pd.Timestamp("2025-10-26 01:00", tz="UTC")]


def test_energy_charts_unknown_unit_raises():
    with pytest.raises(ValueError, match="unexpected unit"):
        energy_charts.parse_timeseries(_ec_payload(unit="TW"))


def test_installed_power_is_in_mw_by_reporting_year():
    payload = {"series": [{"id": "nuclear", "unit": "GW"}],
               "data": [{"timestamp": "2024-01-01T00:00:00+01:00", "values": {"nuclear": 2.973}}]}
    assert energy_charts.parse_installed_power(payload).loc[2024, "nuclear"] == pytest.approx(2973.0)


# --- Swissgrid -----------------------------------------------------------------------------

D2_XML = """<?xml version="1.0" encoding="UTF-8"?>
<CapacityDocument>
  <CapacityTimeSeries>
    <TimeSeriesIdentification v="CH_to_AT"/>
    <MeasurementUnit v="MAW"/>
    <Period><TimeInterval v="2025-12-31T23:00Z/2026-01-01T01:00Z"/><Resolution v="PT1H"/>
      <Interval><Pos v="1"/><Qty v="1200"/></Interval><Interval><Pos v="2"/><Qty v="1000"/></Interval>
    </Period>
  </CapacityTimeSeries>
  <CapacityTimeSeries>
    <TimeSeriesIdentification v="AT_to_CH"/>
    <MeasurementUnit v="MAW"/>
    <Period><TimeInterval v="2025-12-31T23:00Z/2026-01-01T01:00Z"/><Resolution v="PT1H"/>
      <Interval><Pos v="1"/><Qty v="900"/></Interval><Interval><Pos v="2"/><Qty v="800"/></Interval>
    </Period>
  </CapacityTimeSeries>
</CapacityDocument>"""


def test_d2_ntc_xml_gives_one_column_per_direction_in_utc(tmp_path):
    path = tmp_path / "NTC-20260101.xml"
    path.write_text(D2_XML, encoding="utf-8")
    frame = swissgrid.read_ntc_d2(path)
    assert frame.loc[pd.Timestamp("2026-01-01 00:00", tz="UTC"), "CH_to_AT"] == 1000.0
    assert frame["AT_to_CH"].tolist() == [900.0, 800.0]


def test_d2_ntc_not_yet_defined_is_nan(tmp_path):
    path = tmp_path / "NTC-20260924.xml"
    path.write_text(D2_XML.replace('<Qty v="800"/>', '<Qty v="n.y.d."/>'), encoding="utf-8")
    frame = swissgrid.read_ntc_d2(path)
    assert frame["AT_to_CH"].iloc[0] == 900.0 and np.isnan(frame["AT_to_CH"].iloc[1])


def _flows_csv(at_to_ch="-900"):
    header = ("﻿Date Time;B:Intraday NTC Schweiz > Österreich [MW];C:Intraday NTC Österreich > Schweiz [MW];"
              "J:Kommerzielle Lastflüsse Österreich Netto (Total) [MW];"
              "N:Kommerzielle Lastflüsse Summe alle Grenzen Netto (Total) [MW];"
              "R:Preisdifferenz Spot Italien Nord-Schweiz [EUR/MWh]")
    return f"{header}\n01.01.2026 00:00;1200;{at_to_ch};-900;-4012;4.01\n01.01.2026 00:15;1200;{at_to_ch};-800;-4000;.01\n"


def test_cross_border_flows_make_ntc_positive_and_keep_spreads(tmp_path):
    path = tmp_path / "Grenzfluesse-2026.csv"
    path.write_text(_flows_csv(), encoding="utf-8")
    frame = swissgrid.read_cross_border_flows(path)
    assert frame["ntc_id_AT_to_CH"].tolist() == [900, 900]
    assert frame["ntc_id_CH_to_AT"].tolist() == [1200, 1200]
    assert frame["spread_IT_minus_CH"].tolist() == [4.01, 0.01]
    assert frame.index[0] == pd.Timestamp("2025-12-31 23:00", tz="UTC")


@pytest.mark.parametrize("at_to_ch", ["900", "99999"])
def test_cross_border_flows_wrong_sign_or_placeholder_ntc_is_nan_and_counted(tmp_path, at_to_ch):
    path = tmp_path / "Grenzfluesse-2026.csv"
    path.write_text(_flows_csv(at_to_ch=at_to_ch), encoding="utf-8")
    frame = swissgrid.read_cross_border_flows(path)
    assert frame["ntc_id_AT_to_CH"].isna().all()
    assert frame.attrs["invalid_values"] == {"ntc_id_CH_to_AT": 0, "ntc_id_AT_to_CH": 2}


def _overview_xlsx(path, unit="kWh", stamps=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Zeitreihen0h15"
    names = [None] + [f"{german}\nEnglish" for german in swissgrid.OVERVIEW_COLUMNS]
    ws.append(names)
    ws.append(["Zeitstempel"] + [unit] * len(swissgrid.OVERVIEW_COLUMNS))
    rows = stamps or [("01.01.2025 00:00", 0), ("26.10.2025 02:00", 250_000), ("26.10.2025 02:15", 500_000),
                      ("26.10.2025 02:00", 750_000)]
    for stamp, kwh in rows:
        ws.append([stamp] + [kwh] * len(swissgrid.OVERVIEW_COLUMNS))
    wb.save(path)


def test_energy_overview_converts_quarter_hour_kwh_to_mw_with_dst(tmp_path):
    path = tmp_path / "EnergieUebersichtCH-2025.xlsx"
    _overview_xlsx(path)
    frame = swissgrid.read_energy_overview(path)
    assert frame["production"].tolist()[1:] == [1000.0, 2000.0, 3000.0]  # 250 MWh per 15 min = 1000 MW
    assert frame.index[3] - frame.index[1] == pd.Timedelta(hours=1)
    assert frame.index[0] == pd.Timestamp("2024-12-31 23:00", tz="UTC")


def test_energy_overview_end_stamped_files_shift_to_interval_start(tmp_path):
    path = tmp_path / "EnergieUebersichtCH-2024.xlsx"
    _overview_xlsx(path, stamps=[("01.01.2024 00:15", 250_000), ("01.01.2024 00:30", 250_000),
                                 ("31.03.2024 01:45", 250_000), ("31.03.2024 03:00", 250_000),
                                 ("31.03.2024 03:15", 250_000)])
    index = swissgrid.read_energy_overview(path).index
    assert index[0] == pd.Timestamp("2023-12-31 23:00", tz="UTC")
    # spring forward: the quarter ending 02:00 CET is stamped 03:00 CEST; quarters stay contiguous
    assert list(index[2:].strftime("%H:%M")) == ["00:30", "00:45", "01:00"]


def test_energy_overview_unknown_first_stamp_raises(tmp_path):
    path = tmp_path / "EnergieUebersichtCH-2024.xlsx"
    _overview_xlsx(path, stamps=[("01.01.2024 01:00", 0)])
    with pytest.raises(ValueError, match="neither"):
        swissgrid.read_energy_overview(path)


def test_energy_overview_wrong_unit_raises(tmp_path):
    path = tmp_path / "EnergieUebersichtCH-2025.xlsx"
    _overview_xlsx(path, unit="MWh")
    with pytest.raises(ValueError, match="expected kWh"):
        swissgrid.read_energy_overview(path)


# --- ENTSO-E -------------------------------------------------------------------------------

def _a61(curve, points):
    pts = "".join(f"<Point><position>{p}</position><quantity>{q}</quantity></Point>" for p, q in points)
    return f"""<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:0">
  <TimeSeries><curveType>{curve}</curveType>
    <Period><timeInterval><start>2025-10-01T22:00Z</start><end>2025-10-02T02:00Z</end></timeInterval>
      <resolution>PT1H</resolution>{pts}</Period></TimeSeries></Publication_MarketDocument>"""


def test_entsoe_a01_points_map_to_utc_hours():
    s = entsoe_ntc.parse(_a61("A01", [(1, 4000), (2, 3800), (3, 3800), (4, 3500)]))
    assert s.tolist() == [4000, 3800, 3800, 3500]
    assert s.index[0] == pd.Timestamp("2025-10-01 22:00", tz="UTC")


def test_entsoe_a03_blocks_hold_until_next_position():
    s = entsoe_ntc.parse(_a61("A03", [(1, 4000), (3, 3500)]))
    assert s.tolist() == [4000, 4000, 3500, 3500]


def test_entsoe_no_data_acknowledgement_raises():
    ack = """<Acknowledgement_MarketDocument xmlns="urn:x"><Reason><code>999</code>
             <text>No matching data found</text></Reason></Acknowledgement_MarketDocument>"""
    with pytest.raises(ValueError, match="No matching data"):
        entsoe_ntc.parse(ack)


def test_entsoe_token_missing_raises(monkeypatch):
    monkeypatch.delenv("ENTSOE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ENTSOE_API_KEY"):
        entsoe_ntc.token()


# --- nuclear ---------------------------------------------------------------------------------

def _installed(tmp_path, monkeypatch, gw):
    target = tmp_path / "energy_charts" / "installed_power" / "installed_power_ch_yearly.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"series": [{"id": "nuclear", "unit": "GW"}],
                                  "data": [{"timestamp": "2025-01-01T00:00:00+01:00", "values": {"nuclear": gw}}]}))
    monkeypatch.setattr(process, "RAW_DIR", tmp_path)


def test_nuclear_outage_is_capacity_minus_generation(tmp_path, monkeypatch):
    _installed(tmp_path, monkeypatch, 2.973)
    power = pd.DataFrame({"nuclear": [2973.0, 1963.0]}, index=hourly_index("2025-06-01", "2025-06-01")[:2])
    out = process.build_nuclear(power, "2025-06-01", "2025-06-01")
    assert out["outage_MW"].tolist() == [0.0, 1010.0]
    assert out["availability"].iloc[1] == pytest.approx(1963 / 2973)


def test_nuclear_capacity_mismatch_with_energy_charts_raises(tmp_path, monkeypatch):
    _installed(tmp_path, monkeypatch, 3.2)
    power = pd.DataFrame({"nuclear": [2973.0]}, index=hourly_index("2025-06-01", "2025-06-01")[:1])
    with pytest.raises(ValueError, match="differs from Energy-Charts"):
        process.build_nuclear(power, "2025-06-01", "2025-06-01")


# --- ENTSO-E web copy and combined day-ahead NTC --------------------------------------------

from data_prep.historical import entsoe_web  # noqa: E402


def _web_line(day, rows, checksum=None):
    body = ";".join(",".join(str(v) for v in r) for r in rows)
    total = sum(v for r in rows for v in r if v != "n/e") if checksum is None else checksum
    return f"{day}|{len(rows)}|{total}|{body}"


def test_entsoe_web_day_maps_local_hours_to_utc_including_25_hour_day():
    rows = [[1200, 1200, 4000, 800, 1300, 2385, 3000 + i, 1910] for i in range(25)]
    frame = entsoe_web.parse_line(_web_line("2025-10-26", rows))
    assert len(frame) == 25 and frame.index[0] == pd.Timestamp("2025-10-25 22:00", tz="UTC")
    assert frame["CH_to_IT"].iloc[-1] == 3024 and frame.index[-1] == pd.Timestamp("2025-10-26 22:00", tz="UTC")


def test_entsoe_web_wrong_hour_count_raises():
    rows = [[1, 1, 1, 1, 1, 1, 1, 1]] * 24
    with pytest.raises(ValueError, match="local day has 25 hours"):
        entsoe_web.parse_line(_web_line("2025-10-26", rows))


def test_entsoe_web_checksum_mismatch_raises():
    rows = [[1, 1, 1, 1, 1, 1, 1, 1]] * 24
    with pytest.raises(ValueError, match="checksum"):
        entsoe_web.parse_line(_web_line("2025-11-01", rows, checksum=193))


def test_combined_ntc_prefers_d2_and_labels_each_value_with_its_source():
    from data_prep.historical.config import DIRECTIONS
    idx = hourly_index("2025-12-31", "2026-01-01")[22:26]  # hours around the year change
    d2 = pd.DataFrame({d: [np.nan, np.nan, 1000.0, np.nan] for d in DIRECTIONS}, index=idx)
    web = pd.DataFrame({d: [500.0, np.nan, 700.0, 900.0] for d in DIRECTIONS}, index=idx)
    out = process.combine_dayahead_ntc(d2, web, ())
    assert out["DE_to_CH"].tolist()[0] == 500.0 and np.isnan(out["DE_to_CH"].iloc[1])
    assert out["DE_to_CH"].tolist()[2:] == [1000.0, 900.0]
    assert out["source_DE_to_CH"].tolist() == ["entsoe_web", "", "swissgrid_d2", "entsoe_web"]


def test_preferred_day_uses_web_copy_in_every_direction_even_where_d2_has_values():
    from data_prep.historical.config import DIRECTIONS
    idx = hourly_index("2026-09-23", "2026-09-25")
    d2 = pd.DataFrame({d: 1000.0 for d in DIRECTIONS}, index=idx)
    web = pd.DataFrame({d: 400.0 for d in DIRECTIONS}, index=idx)
    out = process.combine_dayahead_ntc(d2, web, ("2026-09-24",))
    day = idx.tz_convert("Europe/Zurich").strftime("%Y-%m-%d") == "2026-09-24"
    assert (out.loc[day, "IT_to_CH"] == 400.0).all() and (out.loc[~day, "IT_to_CH"] == 1000.0).all()
    assert set(out.loc[day, "source_CH_to_DE"]) == {"entsoe_web"}


def test_preferred_day_without_complete_web_copy_raises():
    from data_prep.historical.config import DIRECTIONS
    idx = hourly_index("2026-09-24", "2026-09-24")
    d2 = pd.DataFrame({d: 1000.0 for d in DIRECTIONS}, index=idx)
    web = pd.DataFrame({d: 400.0 for d in DIRECTIONS}, index=idx)
    web.iloc[5, 0] = np.nan
    with pytest.raises(ValueError, match="preferred day 2026-09-24"):
        process.combine_dayahead_ntc(d2, web, ("2026-09-24",))


from data_prep.historical import plot_trade_ntc  # noqa: E402


def test_limit_stats_counts_at_above_and_intraday_coverage():
    idx = hourly_index("2026-01-15", "2026-01-15")[:5]
    limit = pd.Series([1000.0, 1000.0, 1000.0, 1000.0, np.nan], index=idx)
    flow = pd.Series([1000.5, 1050.0, 1300.0, 1001.5, 2000.0], index=idx)
    intraday = pd.Series([np.nan, 1100.0, 1200.0, np.nan, 3000.0], index=idx)
    s = plot_trade_ntc.limit_stats(flow, limit, intraday)
    # 1000.5 is at the limit (within 1 MW), 1001.5 above it; hour 4 lacks a limit and is skipped
    assert s == {"compared": 4, "at": 1, "above": 3, "intraday_published": 2, "within_intraday": 1}


def test_entsoe_bands_returns_each_run_ending_after_its_last_hour():
    idx = hourly_index("2026-01-15", "2026-01-15")[:6]
    sources = pd.Series(["entsoe_web", "entsoe_web", "swissgrid_d2", "swissgrid_d2", "entsoe_web", ""], index=idx)
    assert plot_trade_ntc.entsoe_bands(sources) == [(idx[0], idx[2]), (idx[4], idx[5])]


def test_daily_mean_is_nan_for_a_day_with_a_missing_hour():
    idx = hourly_index("2026-03-28", "2026-03-29")  # 24 h + the 23-hour DST day
    frame = pd.DataFrame({"x": 1.0}, index=idx)
    frame.iloc[30, 0] = np.nan
    out = plot_trade_ntc.daily_mean(frame)
    assert len(out) == 2 and out["x"].iloc[0] == 1.0 and np.isnan(out["x"].iloc[1])


def test_limit_table_checks_exports_against_the_export_limit():
    from data_prep.historical.config import DIRECTIONS, NEIGHBOURS
    idx = hourly_index("2026-01-15", "2026-01-15")[:2]
    ntc = pd.DataFrame({d: 400.0 for d in DIRECTIONS}, index=idx)
    ntc["DE_to_CH"] = 2000.0
    sched = pd.DataFrame({n: 0.0 for n in NEIGHBOURS}, index=idx)
    sched["DE00"] = [-500.0, -400.0]  # exports of 500 and 400 MW against a 400 MW export limit
    intraday = pd.DataFrame({f"ntc_id_{d}": 450.0 for d in DIRECTIONS}, index=idx)
    t = plot_trade_ntc.limit_table(ntc, sched, intraday).loc["CH-DE-LU"]
    assert t["Export: hours above the limit"] == 1 and t["Export: hours at the limit"] == 1
    assert t["Export: above, within intraday NTC"] == 0
    assert t["Import: hours above the limit"] == 0 and t["Mean import limit (MW)"] == 2000.0


def test_period_rows_raises_when_the_processed_table_misses_hours():
    idx = hourly_index("2026-01-15", "2026-01-16")
    frame = pd.DataFrame({"x": 1.0}, index=idx[:30])
    assert len(plot_trade_ntc.period_rows(frame, idx[:24], "t")) == 24
    with pytest.raises(ValueError, match="18 hours of the plotted period are missing"):
        plot_trade_ntc.period_rows(frame, idx, "t")
