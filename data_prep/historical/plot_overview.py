"""One-page HTML overview of the processed historical data (plots/ is gitignored).

Usage (from the repo root, after process.py for the same period):
    python -m data_prep.historical.plot_overview --start 2023-10-01 --end 2026-09-30
"""
import argparse
import html

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_prep.historical.config import COUNTRY_OF_NODE, NEIGHBOURS, PLOTS_DIR, ZONES
from data_prep.historical.process import output_dir

# Reference categorical palette (light), fixed order; chart ink and chrome.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, INK_2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
ZONE_COLOR = {node: SERIES[i] for i, node in enumerate(ZONES)}
GEN_SERIES = {  # Energy-Charts id -> label, stacked bottom to top
    "nuclear": "Nuclear", "hydro_run_of_river": "Run-of-river", "hydro_water_reservoir": "Reservoir hydro",
    "hydro_pumped_storage": "Pumped-storage generation", "solar": "Solar", "wind_onshore": "Wind",
    "others": "Other",
}


def _layout(fig: go.Figure, title: str, height: int, y_title: str = "") -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, font=dict(size=16, color=INK)), height=height,
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, hovermode="x unified",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", size=12, color=INK_2),
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(color=INK_2)),
        margin=dict(l=60, r=20, t=70, b=40),
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS, tickfont=dict(color=MUTED),
                     title=dict(text=y_title, font=dict(color=MUTED)))
    return fig


def _line(x, y, name, color, width=2, dash=None, **kw):
    return go.Scatter(x=x, y=y, name=name, mode="lines", line=dict(color=color, width=width, dash=dash), **kw)


def prices_figure(prices: pd.DataFrame) -> go.Figure:
    local = prices.tz_convert("Europe/Zurich")
    views = {"Weekly mean": local.resample("W-MON", label="left", closed="left").mean(),
             "Daily mean": local.resample("D").mean(), "Hourly": local}
    fig = go.Figure()
    for k, (view, frame) in enumerate(views.items()):
        for node in ZONES:
            fig.add_trace(_line(frame.index, frame[node], ZONES[node]["label"], ZONE_COLOR[node],
                                width=2.5 if node == "CH00" else 1.5, legendgroup=node,
                                showlegend=k == 0, visible=k == 0, hovertemplate="%{y:.1f}"))
    n = len(ZONES)
    buttons = [dict(label=view, method="restyle",
                    args=[{"visible": [j // n == k for j in range(n * len(views))]}])
               for k, view in enumerate(views)]
    fig.update_layout(updatemenus=[dict(
        type="buttons", direction="right", x=1, xanchor="right", y=1.12, yanchor="bottom",
        bgcolor=SURFACE, bordercolor=AXIS, font=dict(color=INK_2), buttons=buttons)])
    fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.06))
    return _layout(fig, "Day-ahead prices (EUR/MWh), local time", 480, "EUR/MWh")


def convergence_figure(prices: pd.DataFrame) -> go.Figure:
    local = prices.tz_convert("Europe/Zurich")
    fig = go.Figure()
    for node in NEIGHBOURS:
        close = (local[node] - local["CH00"]).abs().le(1.0).where(local[[node, "CH00"]].notna().all(axis=1))
        monthly = close.resample("MS").mean() * 100
        fig.add_trace(go.Scatter(x=monthly.index, y=monthly, name=ZONES[node]["label"], mode="lines+markers",
                                 line=dict(color=ZONE_COLOR[node], width=2), marker=dict(size=8),
                                 hovertemplate="%{y:.0f}%"))
    fig.update_yaxes(rangemode="tozero", ticksuffix="%")
    return _layout(fig, "Share of hours with CH price within 1 EUR/MWh of each neighbour, per month", 380)


def generation_figure(power: pd.DataFrame) -> go.Figure:
    weekly = power.tz_convert("Europe/Zurich").resample("W-MON", label="left", closed="left").mean()
    fig = go.Figure()
    for i, (sid, label) in enumerate(GEN_SERIES.items()):
        fig.add_trace(go.Scatter(x=weekly.index, y=weekly[sid], name=label, mode="lines", stackgroup="gen",
                                 line=dict(width=0, color=SERIES[i]), fillcolor=SERIES[i],
                                 hovertemplate="%{y:.0f}"))
    fig.add_trace(_line(weekly.index, weekly["load"], "Load", INK, width=2, hovertemplate="%{y:.0f}"))
    return _layout(fig, "CH generation by type and load, weekly mean MW (Energy-Charts)", 460, "MW")


def nuclear_figure(nuc: pd.DataFrame) -> go.Figure:
    local = nuc.tz_convert("Europe/Zurich")
    fig = go.Figure()
    fig.add_trace(_line(local.index, local["net_capacity_MW"], "Net capacity", MUTED, width=1.5, dash="dash",
                        hovertemplate="%{y:.0f}"))
    fig.add_trace(_line(local.index, local["generation_MW"], "Generation = estimated available", SERIES[0],
                        width=1, customdata=local["outage_MW"],
                        hovertemplate="%{y:.0f} MW, outage %{customdata:.0f} MW"))
    fig.update_yaxes(rangemode="tozero")
    return _layout(fig, "CH nuclear: hourly generation vs net capacity (gap = outage or derating)", 380, "MW")


def reservoir_figure(res: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(_line(res.index, res["TotalCH_max_GWh"], "Maximum content", MUTED, width=1.5, dash="dash",
                        hovertemplate="%{y:.0f}"))
    fig.add_trace(go.Scatter(x=res.index, y=res["TotalCH_GWh"], name="Stored energy", mode="lines+markers",
                             line=dict(color=SERIES[0], width=2), marker=dict(size=4), hovertemplate="%{y:.0f}"))
    fig.update_yaxes(rangemode="tozero")
    return _layout(fig, "CH storage lakes, weekly content in GWh (BFE)", 360, "GWh")


def ntc_figure(ntc: pd.DataFrame, scheduled: pd.DataFrame, source: str) -> go.Figure:
    have = ntc.dropna(how="all")
    local_ntc = have.tz_convert("Europe/Zurich")
    sched = scheduled.loc[have.index[0]:have.index[-1]].tz_convert("Europe/Zurich")
    labels = [ZONES[n]["label"] for n in NEIGHBOURS]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        subplot_titles=[f"{lab} border" for lab in labels])
    for row, node in enumerate(NEIGHBOURS, start=1):
        c = COUNTRY_OF_NODE[node]
        first = row == 1
        fig.add_trace(_line(local_ntc.index, local_ntc[f"{c}_to_CH"], "NTC limit (import + / export -)", MUTED,
                            width=1.5, legendgroup="ntc", showlegend=first, line_shape="hv",
                            hovertemplate="import NTC %{y:.0f}"), row=row, col=1)
        fig.add_trace(_line(local_ntc.index, -local_ntc[f"CH_to_{c}"], "NTC export", MUTED, width=1.5,
                            legendgroup="ntc", showlegend=False, line_shape="hv",
                            hovertemplate="export NTC %{y:.0f}"), row=row, col=1)
        fig.add_trace(_line(sched.index, sched[node], "Scheduled exchange (+ import to CH)", SERIES[0], width=1,
                            legendgroup="sched", showlegend=first, hovertemplate="schedule %{y:.0f}"),
                      row=row, col=1)
    fig.update_annotations(font=dict(size=12, color=INK_2), x=0, xanchor="left")
    return _layout(fig, f"Border limits ({source}) and scheduled exchanges, hourly MW", 900, "MW")


def table_html(frame: pd.DataFrame, float_digits: int = 1) -> str:
    def fmt(v):
        if isinstance(v, float):
            return "" if pd.isna(v) else f"{v:,.{float_digits}f}"
        return html.escape(str(v))
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in frame.columns)
    body = "".join("<tr>" + "".join(f"<td>{fmt(v)}</td>" for v in row) + "</tr>"
                   for row in frame.itertuples(index=False))
    return f"<div class='tbl'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def build_html(start_day: str, end_day: str) -> str:
    src = output_dir(start_day, end_day)

    def read(name):
        return pd.read_csv(src / f"{name}_hourly.csv", index_col="time_utc", parse_dates=["time_utc"])

    prices, power, nuc = read("prices_day_ahead"), read("ch_public_power"), read("nuclear_availability")
    scheduled, ntc_d2 = read("ch_exchanges_scheduled"), read("ntc_swissgrid_d2")
    reservoir = pd.read_csv(src / "reservoir_weekly_bfe.csv", index_col="date", parse_dates=["date"])
    coverage = pd.read_csv(src / "coverage_report.csv")
    validation = pd.read_csv(src / "validation_report.csv")

    monthly = prices.tz_convert("Europe/Zurich").resample("MS").mean()
    monthly.index = monthly.index.strftime("%Y-%m")
    monthly = monthly.rename(columns={n: ZONES[n]["label"] for n in ZONES}).reset_index(names="month")
    cov = coverage[["table", "column", "hours", "missing_hours", "longest_gap_hours", "first_valid_utc",
                    "last_valid_utc"]]
    val = validation.dropna(axis=1, how="all")

    figures = [prices_figure(prices), convergence_figure(prices), generation_figure(power), nuclear_figure(nuc),
               reservoir_figure(reservoir), ntc_figure(ntc_d2, scheduled, "Swissgrid D-2 NTC")]
    parts = [fig.to_html(full_html=False, include_plotlyjs=(i == 0), config={"displaylogo": False})
             for i, fig in enumerate(figures)]
    sections = [
        ("Day-ahead prices", parts[0] + "<h3>Monthly mean (EUR/MWh)</h3>" + table_html(monthly)),
        ("How close is CH to its neighbours?", parts[1]),
        ("CH generation and load", parts[2]),
        ("Nuclear availability (estimated from hourly generation)", parts[3]),
        ("Storage lakes", parts[4]),
        ("Border transfer limits", "<p class='note'>Swissgrid publishes D-2 NTC only for the current year "
         "(from 2026-01-01). Oct 2023 - Dec 2025 needs the ENTSO-E download (token pending).</p>" + parts[5]),
        ("Cross-checks between sources", table_html(val, 2)),
        ("Coverage (hours missing per series)", table_html(cov, 0)),
    ]
    body = "".join(f"<section><h2>{html.escape(t)}</h2>{c}</section>" for t, c in sections)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Historical CH Data</title>
<style>
:root {{ --page:#f9f9f7; --surface:{SURFACE}; --ink:{INK}; --ink2:{INK_2}; --muted:{MUTED}; --grid:{GRID}; }}
body {{ margin:0; background:var(--page); color:var(--ink); font-family:system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1200px; margin:0 auto; padding:24px 16px 64px; }}
h1 {{ font-size:24px; margin:0 0 4px; }} h2 {{ font-size:18px; margin:0 0 8px; }} h3 {{ font-size:14px; color:var(--ink2); }}
.sub, .note {{ color:var(--ink2); font-size:13px; }}
section {{ background:var(--surface); border:1px solid rgba(11,11,11,.1); border-radius:8px; padding:16px; margin:16px 0; }}
.tbl {{ overflow-x:auto; max-height:520px; }}
table {{ border-collapse:collapse; font-size:12px; font-variant-numeric:tabular-nums; }}
th, td {{ padding:4px 10px; border-bottom:1px solid var(--grid); text-align:right; white-space:nowrap; }}
th {{ position:sticky; top:0; background:var(--surface); color:var(--ink2); }}
td:first-child, th:first-child, td:nth-child(2), th:nth-child(2) {{ text-align:left; }}
</style></head><body><main>
<h1>Historical data for the CH-only back-cast</h1>
<p class="sub">Period {start_day} to {end_day} (local days). Prices, generation, load and exchanges:
Energy-Charts (CC BY 4.0, energy-charts.info; prices from Bundesnetzagentur | SMARD.de). Load, production,
metered exchanges, NTC: Swissgrid. Storage lakes: BFE (ogd17). Generated from
<code>input/historical/processed/{start_day}_{end_day}/</code>.</p>
{body}
</main></body></html>"""


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args(argv)
    PLOTS_DIR.mkdir(exist_ok=True)
    target = PLOTS_DIR / f"historical_overview_{args.start}_{args.end}.html"
    target.write_text(build_html(args.start, args.end), encoding="utf-8")
    print(f"written {target}")


if __name__ == "__main__":
    main()
