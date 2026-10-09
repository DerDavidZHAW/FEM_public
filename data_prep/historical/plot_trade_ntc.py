"""Day-ahead NTC limits and cross-border trade per Swiss border: interactive HTML, static PNG and a stats CSV.

Usage (from the repo root, after process.py for a period that contains the plotted days):
    python -m data_prep.historical.plot_trade_ntc --start 2025-10-01 --end 2026-09-30 \
        --processed 2023-10-01 2026-09-30 [--out-dir DIR]

--processed names the processed folder (default: the plotted period); --out-dir defaults to plots/ (gitignored).
NTC: ntc_dayahead_combined_hourly.csv (Swissgrid D-2, ENTSO-E web copy where marked). Trade: Energy-Charts
scheduled commercial exchange (cbet, all horizons) and physical flow, Swissgrid metered (ends with Swissgrid's
latest published month). Sign: + = import into CH.
The table checks the schedule against the day-ahead NTC and, where Swissgrid publishes it, the intraday NTC.
"""
import argparse
import html
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from data_prep.historical.config import COUNTRY_OF_NODE, LOCAL_TZ, NEIGHBOURS, PLOTS_DIR, ZONES
from data_prep.historical.process import output_dir
from data_prep.historical.timeutils import hourly_index

SCHEDULE, PHYSICAL, LIMIT, BAND = "#2a78d6", "#1baf7a", "#52514e", "#eda100"
INK, INK2, MUTED, GRID, AXIS, SURFACE, PAGE = (
    "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb", "#f9f9f7")
# A flow counts as "at" the limit within this distance, and "above" it beyond (MW; the data are rounded to 1 MW).
TOL_MW = 1.0
RESOLUTIONS = ("daily", "hourly")
TRACES_PER_VIEW = 4  # NTC import, NTC export, schedule, physical flow


def read(src, name):
    return pd.read_csv(src / f"{name}_hourly.csv", index_col="time_utc", parse_dates=["time_utc"])


def period_rows(frame: pd.DataFrame, index: pd.DatetimeIndex, name: str) -> pd.DataFrame:
    """Rows of `frame` for every hour of `index`; raises if the processed table lacks any of them."""
    missing = index.difference(frame.index)
    if len(missing):
        raise ValueError(f"{name}: {len(missing)} hours of the plotted period are missing from the processed "
                         f"table (first {missing[0]}); pass --processed with a folder that covers the period")
    return frame.loc[index]


def daily_mean(frame: pd.DataFrame) -> pd.DataFrame:
    """Mean per local day; a day with any missing hour is NaN."""
    local = frame.tz_convert(LOCAL_TZ)
    complete = local.isna().resample("D").sum().eq(0)
    return local.resample("D").mean().where(complete)


def entsoe_bands(sources: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Contiguous spans (start, end of last hour) in which the value comes from the ENTSO-E web copy."""
    is_web = sources.eq("entsoe_web")
    runs = is_web.ne(is_web.shift()).cumsum()
    return [(g.index[0], g.index[-1] + pd.Timedelta(hours=1)) for _, g in is_web[is_web].groupby(runs[is_web])]


def limit_stats(flow: pd.Series, limit: pd.Series, intraday: pd.Series) -> dict:
    """Hours a directional flow sits at or above its day-ahead limit, and how many of the latter the
    intraday limit covers. `flow` is positive in the limit's direction; hours lacking flow or limit are skipped."""
    ok = flow.notna() & limit.notna()
    above = ok & (flow > limit + TOL_MW)
    published = above & intraday.notna()
    return {"compared": int(ok.sum()), "at": int((ok & (flow - limit).abs().le(TOL_MW)).sum()),
            "above": int(above.sum()), "intraday_published": int(published.sum()),
            "within_intraday": int((published & (flow <= intraday + TOL_MW)).sum())}


def limit_table(ntc: pd.DataFrame, sched: pd.DataFrame, intraday: pd.DataFrame) -> pd.DataFrame:
    """One row per border: mean limits and schedule, then limit_stats for each direction."""
    rows = {}
    for node in NEIGHBOURS:
        c = COUNTRY_OF_NODE[node]
        col = {"Mean import limit (MW)": ntc[f"{c}_to_CH"].mean(), "Mean export limit (MW)": ntc[f"CH_to_{c}"].mean(),
               "Mean schedule (MW, + = import)": sched[node].mean()}
        for word, flow, direction in (("Import", sched[node], f"{c}_to_CH"), ("Export", -sched[node], f"CH_to_{c}")):
            s = limit_stats(flow, ntc[direction], intraday[f"ntc_id_{direction}"])
            col |= {f"{word}: hours compared": s["compared"], f"{word}: hours at the limit": s["at"],
                    f"{word}: hours above the limit": s["above"],
                    f"{word}: above, intraday NTC published": s["intraday_published"],
                    f"{word}: above, within intraday NTC": s["within_intraday"]}
        rows[f"CH-{ZONES[node]['label']}"] = col
    table = pd.DataFrame.from_dict(rows, orient="index")
    table.index.name = "border"
    return table


def load(start_day: str, end_day: str, processed: tuple[str, str]) -> dict:
    """Hourly tables for the plotted local days, the ENTSO-E spans, and the end of the metered physical flow."""
    src = output_dir(*processed)
    index = hourly_index(start_day, end_day)
    ntc = period_rows(read(src, "ntc_dayahead_combined"), index, "ntc_dayahead_combined")
    limits = ntc[[c for c in ntc.columns if not c.startswith("source_")]]
    sources = ntc[[f"source_{d}" for d in limits.columns]]
    if not sources.eq(sources.iloc[:, 0], axis=0).all().all():
        raise ValueError("NTC sources differ between directions; shade them per direction")
    phys = period_rows(read(src, "ch_exchanges_physical"), index, "ch_exchanges_physical")
    published = phys[NEIGHBOURS].dropna(how="all").index
    return {"ntc": ntc, "limits": limits, "phys": phys,
            "sched": period_rows(read(src, "ch_exchanges_scheduled"), index, "ch_exchanges_scheduled"),
            # Swissgrid publishes intraday NTC for the running year only; earlier hours are NaN and counted as such.
            "intraday": period_rows(read(src, "swissgrid_cross_border"), index, "swissgrid_cross_border"),
            "bands": entsoe_bands(sources.iloc[:, 0]), "n_web": int(sources.iloc[:, 0].eq("entsoe_web").sum()),
            "phys_end": published.max().tz_convert(LOCAL_TZ) + pd.Timedelta(hours=1) if len(published) else None}


def interactive_html(d: dict, table: pd.DataFrame, start_day: str, end_day: str) -> str:
    limits, sched, phys, intraday = d["limits"], d["sched"], d["phys"], d["intraday"]
    views = {"hourly": (limits.tz_convert(LOCAL_TZ), sched.tz_convert(LOCAL_TZ), phys.tz_convert(LOCAL_TZ)),
             "daily": (daily_mean(limits), daily_mean(sched), daily_mean(phys))}

    fig = go.Figure()
    for b, node in enumerate(NEIGHBOURS):
        c = COUNTRY_OF_NODE[node]
        for res in RESOLUTIONS:
            lim, sch, phy = views[res]
            first = b == 0 and res == RESOLUTIONS[0]
            when = "%{x|%a %d %b %Y}" if res == "daily" else "%{x|%a %d %b %Y %H:%M}"
            group = f"ntc_{c}_{res}"
            fig.add_trace(go.Scatter(x=lim.index, y=lim[f"{c}_to_CH"], name="Day-ahead NTC (import +, export −)",
                                     legendgroup=group, mode="lines", line=dict(color=LIMIT, width=1.5, shape="hv"),
                                     visible=first, hovertemplate=when + "<br>import NTC %{y:,.0f} MW<extra></extra>"))
            fig.add_trace(go.Scatter(x=lim.index, y=-lim[f"CH_to_{c}"], name="NTC export", showlegend=False,
                                     legendgroup=group, mode="lines", line=dict(color=LIMIT, width=1.5, shape="hv"),
                                     visible=first, hovertemplate="export NTC %{y:,.0f} MW<extra></extra>"))
            fig.add_trace(go.Scatter(x=sch.index, y=sch[node], name="Scheduled commercial exchange", mode="lines",
                                     line=dict(color=SCHEDULE, width=1.2, shape="hv"), visible=first,
                                     hovertemplate="schedule %{y:,.0f} MW<extra></extra>"))
            fig.add_trace(go.Scatter(x=phy.index, y=phy[node], name="Physical flow (Swissgrid metered)", mode="lines",
                                     line=dict(color=PHYSICAL, width=1.2, shape="hv"),
                                     visible="legendonly" if first else False,
                                     hovertemplate="physical %{y:,.0f} MW<extra></extra>"))
    # Legend key for the shaded spans; the spans themselves are layout shapes.
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name="NTC from ENTSO-E web copy (shaded)",
                             marker=dict(symbol="square", size=12, color=BAND, opacity=0.35), hoverinfo="skip"))
    for a, z in d["bands"]:
        fig.add_vrect(x0=a.tz_convert(LOCAL_TZ), x1=z.tz_convert(LOCAL_TZ), fillcolor=BAND, opacity=0.12,
                      line_width=0, layer="below")

    fig.update_layout(
        height=560, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, hovermode="x unified",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", size=12, color=INK2),
        legend=dict(orientation="h", x=0, xanchor="left", y=1.01, yanchor="bottom", font=dict(color=INK2)),
        margin=dict(l=56, r=12, t=48, b=24),
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, tickfont=dict(color=MUTED),
                     rangeslider=dict(visible=True, thickness=0.07, bgcolor=PAGE))
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=AXIS, zerolinewidth=1.5, tickfont=dict(color=MUTED),
                     tickformat=",.0f", title=dict(text="MW", font=dict(color=MUTED)))

    head = "<th></th>" + "".join(f"<th>{html.escape(b)}</th>" for b in table.index)
    body = "".join(f"<tr><td>{html.escape(metric)}</td>" + "".join(f"<td>{v:,.0f}</td>" for v in table[metric])
                   + "</tr>" for metric in table.columns)
    n_intraday = int(intraday[[c for c in intraday.columns if c.startswith("ntc_id_")]].notna().any(axis=1).sum())
    phys_note = (f"Swissgrid metered, published up to {d['phys_end']:%d %b %Y %H:%M}" if d["phys_end"] is not None
                 else "no Swissgrid metered data published for this period")
    border_buttons = "".join(
        f'<button type="button" data-border="{b}" aria-pressed="{str(b == 0).lower()}">CH-{ZONES[n]["label"]}</button>'
        for b, n in enumerate(NEIGHBOURS))
    res_buttons = "".join(
        f'<button type="button" data-res="{r}" aria-pressed="{str(r == RESOLUTIONS[0]).lower()}">'
        f'{"Daily mean" if r == "daily" else "Hourly"}</button>' for r in RESOLUTIONS)
    window_buttons = "".join(f'<button type="button" data-days="{n}">{label}</button>'
                             for n, label in (("7", "Last 7 days"), ("30", "Last 30 days"), ("", "Full period")))
    chart = fig.to_html(full_html=False, include_plotlyjs=True, div_id="chart",
                        config={"displaylogo": False, "responsive": True})
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Swiss Trade And NTC</title>
<style>
:root {{ color-scheme: light; }}
body {{ margin:0; background:{PAGE}; color:{INK}; font-family:system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1300px; margin:0 auto; padding:20px 16px 48px; }}
h1 {{ font-size:20px; font-weight:600; margin:0 0 4px; }}
.sub {{ color:{INK2}; font-size:13px; margin:0 0 12px; }}
.card {{ background:{SURFACE}; border:1px solid rgba(11,11,11,.1); border-radius:8px; padding:12px 16px; margin:12px 0; }}
.controls {{ display:flex; flex-wrap:wrap; gap:12px; align-items:center; }}
.seg {{ display:inline-flex; border:1px solid {AXIS}; border-radius:6px; overflow:hidden; }}
.seg button {{ font:inherit; font-size:13px; color:{INK2}; background:{SURFACE}; border:0; padding:6px 12px;
  cursor:pointer; border-left:1px solid {AXIS}; }}
.seg button:first-child {{ border-left:0; }}
.seg button[aria-pressed="true"] {{ background:{INK}; color:{SURFACE}; }}
.seg button:focus-visible {{ outline:2px solid {SCHEDULE}; outline-offset:-2px; }}
p {{ color:{INK2}; font-size:13px; line-height:1.55; margin:6px 0 10px; }}
table {{ border-collapse:collapse; font-size:12.5px; font-variant-numeric:tabular-nums; }}
th, td {{ padding:4px 12px; border-bottom:1px solid {GRID}; text-align:right; white-space:nowrap; }}
th {{ color:{INK2}; font-weight:600; }} td:first-child {{ text-align:left; color:{INK2}; }}
.tbl {{ overflow-x:auto; }}
</style></head><body><main>
<h1>Swiss border trade and day-ahead NTC</h1>
<p class="sub">{start_day} to {end_day}, MW; + = import into CH, − = export from CH</p>
<div class="card">
<div class="controls"><div class="seg" role="group" aria-label="Border">{border_buttons}</div>
<div class="seg" role="group" aria-label="Resolution">{res_buttons}</div>
<div class="seg" role="group" aria-label="Time window (ends at the right edge of the current view)">{window_buttons}</div></div>
{chart}
</div>
<div class="card">
<p>Grey steps: day-ahead NTC, import limit above zero and export limit below. Values come from the Swissgrid D-2
files, except in the shaded spans ({d['n_web']:,} hours), which use the ENTSO-E web copy of the same product. Blue:
the final scheduled commercial exchange (Energy-Charts cbet). It covers all horizons, including intraday, so it can
exceed the day-ahead NTC. Green (off by default; click it in the legend): physical flow, {phys_note}. Use the daily
view for the year, and the hourly view with a 7- or 30-day window (move it with the slider) for single hours.</p>
<p>"At the limit" means within {TOL_MW:.0f} MW. For hours above the day-ahead limit, the table shows how many have
a Swissgrid intraday NTC (published for {n_intraday:,} of the {len(limits):,} hours) and how many stay within it.</p>
<div class="tbl"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></div>
</main>
<script>
(function () {{
  const gd = document.getElementById("chart");
  const nBorders = {len(NEIGHBOURS)}, resolutions = {json.dumps(list(RESOLUTIONS))}, per = {TRACES_PER_VIEW};
  const state = {{ border: 0, res: 0 }};
  const base = (b, r) => (b * resolutions.length + r) * per;
  function apply(next) {{
    const physOn = gd.data[base(state.border, state.res) + per - 1].visible === true;
    Object.assign(state, next);
    const vis = [];
    for (let b = 0; b < nBorders; b++) for (let r = 0; r < resolutions.length; r++) {{
      const on = b === state.border && r === state.res;
      vis.push(on, on, on, on ? (physOn ? true : "legendonly") : false);
    }}
    vis.push(true);
    Plotly.restyle(gd, {{ visible: vis }});
  }}
  document.querySelectorAll("button[data-border]").forEach(btn => btn.addEventListener("click", () => {{
    document.querySelectorAll("button[data-border]").forEach(o => o.setAttribute("aria-pressed", o === btn));
    apply({{ border: Number(btn.dataset.border) }});
  }}));
  document.querySelectorAll("button[data-res]").forEach(btn => btn.addEventListener("click", () => {{
    document.querySelectorAll("button[data-res]").forEach(o => o.setAttribute("aria-pressed", o === btn));
    apply({{ res: resolutions.indexOf(btn.dataset.res) }});
  }}));
  // Axis range strings are naive wall-clock times; Plotly reads millisecond ranges as UTC, so parse them as UTC.
  const toMs = s => Date.parse(String(s).replace(" ", "T") + (String(s).length === 10 ? "T00:00Z" : "Z"));
  document.querySelectorAll("button[data-days]").forEach(btn => btn.addEventListener("click", () => {{
    if (!btn.dataset.days) {{ Plotly.relayout(gd, {{ "xaxis.autorange": true }}); return; }}
    const end = toMs(gd._fullLayout.xaxis.range[1]);
    Plotly.relayout(gd, {{ "xaxis.range": [end - Number(btn.dataset.days) * 864e5, end] }});
  }}));
}})();
</script>
</body></html>"""


def overview_png(d: dict, start_day: str, end_day: str, path: Path) -> None:
    """Static small multiples, one panel per border: daily mean NTC limits and scheduled exchange."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.ticker import FuncFormatter

    lim, sch = daily_mean(d["limits"]), daily_mean(d["sched"])
    x = lim.index.tz_localize(None)  # local wall-clock days
    wall = lambda t: t.tz_convert(LOCAL_TZ).tz_localize(None)
    fig, axes = plt.subplots(len(NEIGHBOURS), 1, figsize=(11, 2.5 * len(NEIGHBOURS) + 1), sharex=True)
    for ax, node in zip(axes, NEIGHBOURS):
        c = COUNTRY_OF_NODE[node]
        for a, z in d["bands"]:
            ax.axvspan(wall(a), wall(z), color=BAND, alpha=0.15, lw=0)
        ax.axhline(0, color=AXIS, lw=0.8)
        ax.step(x, lim[f"{c}_to_CH"], where="post", color=LIMIT, lw=1.1)
        ax.step(x, -lim[f"CH_to_{c}"], where="post", color=LIMIT, lw=1.1)
        ax.step(x, sch[node], where="post", color=SCHEDULE, lw=1.1)
        ax.set_title(f"CH-{ZONES[node]['label']}", loc="left", fontsize=11, color=INK)
        ax.set_ylabel("MW", color=MUTED)
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.tick_params(colors=MUTED, labelsize=9)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(AXIS)
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator())
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    handles = [Line2D([], [], color=LIMIT, lw=1.5, label="Day-ahead NTC (import +, export −)"),
               Line2D([], [], color=SCHEDULE, lw=1.5, label="Scheduled commercial exchange"),
               Patch(color=BAND, alpha=0.3, label="NTC from ENTSO-E web copy")]
    fig.suptitle(f"Swiss border trade and day-ahead NTC, daily mean, {start_day} to {end_day} (+ = import into CH)",
                 x=0.01, ha="left", fontsize=12, color=INK)
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.01, 0.975), ncol=3, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--processed", nargs=2, metavar=("START", "END"),
                        help="period of the processed folder to read (default: --start/--end)")
    parser.add_argument("--out-dir", type=Path, default=PLOTS_DIR)
    args = parser.parse_args(argv)
    d = load(args.start, args.end, tuple(args.processed or (args.start, args.end)))
    table = limit_table(d["limits"], d["sched"], d["intraday"])
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.out_dir / f"trade_vs_ntc_{args.start}_{args.end}"
    Path(f"{stem}.html").write_text(interactive_html(d, table, args.start, args.end), encoding="utf-8")
    overview_png(d, args.start, args.end, Path(f"{stem}.png"))
    table.to_csv(f"{stem}_limit_stats.csv", float_format="%.1f")
    print(f"written {stem}.html, .png, _limit_stats.csv")


if __name__ == "__main__":
    main()
