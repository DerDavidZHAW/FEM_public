"""Two channels of the neighbours' influence on the Swiss price.

The Shapley border decomposition (border_shapley.py) attributes the gap
between the model price and the isolated clearing of the SAME bids to the
four borders. Because the water values, hydrogen values and storage bids of
that clearing were formed with trade, the gap is only the hourly DISPATCH
channel. A real rerun with closed borders and the investments fixed to the
base run (input/model_variable_presets.csv, made by
scenarios/make_investment_presets.py) gives the second, ADAPTATION channel:

    p_all      model price of the base run (open borders)
    p_iso      isolated clearing of the base run's bids (Shapley baseline)
    p_rerun    price of the closed-border rerun (bids re-optimised)

    dispatch   = p_all - p_iso        (attributed to the borders by Shapley)
    adaptation = p_iso - p_rerun      (water values etc. re-optimised)
    total      = p_all - p_rerun      (full effect of trade on the price)

Two sub-commands:

    extract <scenario> [--node CH00]
        compact hourly tables of one run in output/<scenario>/channels/:
        hourly_<node>.csv (price, lost load, generation by technology,
        charging, imports, exports, curtailment, spill, inflow, dam SoC) and
        watervalues_<node>.csv (water value per hydro storage cluster).
        Reads the big result files once, so 1-2 minutes per run.

    compare --base <base scenario> --rerun <closed-border scenario>
            [--ntc50 <half-NTC scenario>] [--poster] [--font-scale 2]
        merges the base run's border_shapley/shapley_hourly.csv with the
        extracts, writes channels_hourly.csv, channels_monthly.csv,
        channels_summary.csv and figures into
        output/<base>/border_shapley/channels/.

Usage (repo root, David's machine for extract, any machine with the
extracts for compare):
    python plot_creators/border_channels.py extract autarky_2035_wy2008_12hydro
    python plot_creators/border_channels.py extract base_2035_wy2008_12hydro
    python plot_creators/border_channels.py compare --base base_2035_wy2008_12hydro \
        --rerun autarky_2035_wy2008_12hydro --ntc50 ntc50_2035_wy2008_12hydro
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "output"
CHUNK = 2_000_000
EPS = 1e-6

TECH_GROUP = {
    "dam": "hydro dam", "psp_open": "pumped hydro", "psp_close": "pumped hydro",
    "psp": "pumped hydro", "ror": "run of river", "nuclear": "nuclear",
    "CCGTCCS": "gas", "CCGTresmethane": "gas", "SCGTresmethane": "gas",
    "SCGTfossil": "gas", "CCGT": "gas", "SCGT": "gas", "oil": "oil",
    "hydrogen": "hydrogen turbine", "battery": "battery", "biomass": "biomass",
    "pvrf": "pv", "pv": "pv", "windon": "wind", "windoff": "wind", "other": "other",
    "electrolyzer": "electrolyzer", "EV_flex": "ev flex", "V2G": "v2g",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def kv(df, key, val="value"):
    return dict(zip(df[key], df[val]))


def wide_map(df):
    """Map_node_plant style: first column = node, remaining cells = plants."""
    out = {}
    for _, row in df.iterrows():
        node = row.iloc[0]
        for cell in row.iloc[1:]:
            if isinstance(cell, str) and cell:
                out[cell] = node
    return out


def t_int(t):
    return int(str(t).split("_")[1])


def read_filtered(path, sub, key_col=None, keys=None, usecols=None):
    parts = []
    for chunk in pd.read_csv(path, chunksize=CHUNK, usecols=usecols):
        scol = "Scenarios" if "Scenarios" in chunk.columns else (
            "Scenario" if "Scenario" in chunk.columns else None)
        if scol is not None:
            chunk = chunk.loc[chunk[scol] == sub]
        if key_col is not None and keys is not None:
            chunk = chunk.loc[chunk[key_col].isin(keys)]
        if len(chunk):
            parts.append(chunk)
    if not parts:
        return pd.DataFrame(columns=usecols or [])
    return pd.concat(parts, ignore_index=True)


def group_of(plant, plant_tech):
    tech = str(plant_tech.get(plant, ""))
    if tech in TECH_GROUP:
        return TECH_GROUP[tech]
    for key, grp in TECH_GROUP.items():
        if key in tech or key in plant:
            return grp
    return "other"


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------
def extract(scenario, node="CH00", sub=None):
    folder = OUT / scenario
    sub = sub or f"{scenario}_wy2008"
    out_dir = folder / "channels"
    out_dir.mkdir(exist_ok=True)
    sf = kv(pd.read_csv(folder / "constraint_scaling.csv"), "ConstraintNames")
    wdf = pd.read_csv(folder / "weight_in_objective_fcn.csv")
    w = float(wdf.loc[wdf["Scenarios"] == sub, "value"].iloc[0])
    plant_node = wide_map(pd.read_csv(folder / "Map_node_plant.csv"))
    plant_tech = kv(pd.read_csv(folder / "Map_plant_tech.csv"), "P")
    node_plants = {p for p, n in plant_node.items() if n == node}
    consumer_node = wide_map(pd.read_csv(folder / "Map_node_consumer.csv"))
    node_consumers = {c for c, n in consumer_node.items() if n == node}
    hydro = {p for p in node_plants if group_of(p, plant_tech) in ("hydro dam", "pumped hydro")}
    print(f"{scenario}: {len(node_plants)} plants at {node}, hydro storages {sorted(hydro)}")

    # price
    elp = read_filtered(folder / "energy_balance_dual.csv", sub, "Node", {node})
    hourly = pd.DataFrame({"T": elp["T"], "price": elp["value"] * sf["energy_balance"] / w})
    hourly = hourly.set_index("T")

    def add_sum(name, path, key_col, keys, sign=1.0):
        if not path.exists():
            hourly[name] = np.nan
            return
        df = read_filtered(path, sub, key_col, keys)
        s = df.groupby("T")["value"].sum() * sign if len(df) else pd.Series(dtype=float)
        hourly[name] = s.reindex(hourly.index).fillna(0.0)

    # generation by technology group
    gen = read_filtered(folder / "gen.csv", sub, "P_gen", node_plants)
    gen["group"] = gen["P_gen"].map(lambda p: group_of(p, plant_tech))
    piv = gen.pivot_table(index="T", columns="group", values="value", aggfunc="sum").fillna(0.0)
    for g in piv.columns:
        hourly[f"gen_{g.replace(' ', '_')}"] = piv[g].reindex(hourly.index).fillna(0.0)
    chg = read_filtered(folder / "storage_charge.csv", sub, "P_pumping", node_plants)
    chg["group"] = chg["P_pumping"].map(lambda p: group_of(p, plant_tech))
    piv = chg.pivot_table(index="T", columns="group", values="value", aggfunc="sum").fillna(0.0)
    for g in piv.columns:
        hourly[f"charge_{g.replace(' ', '_')}"] = piv[g].reindex(hourly.index).fillna(0.0)

    add_sum("lostload", folder / "lostload.csv", "Consumer", node_consumers)
    add_sum("curtailment", folder / "curtailment.csv", "Consumer_with_infeed", node_consumers)
    add_sum("spill", folder / "spill_water.csv", "P_hydro", hydro)
    add_sum("inflow", folder / "inflow.csv", "P_inflow", hydro)
    add_sum("soc_hydro", folder / "soc.csv", "P_storage", hydro)
    add_sum("infeed", folder / "infeed.csv", "Consumer_with_infeed", node_consumers)

    # trade: lines with exactly one endpoint at the node; Export.csv is the
    # flow in the line's direction (start -> end)
    line_start = wide_map(pd.read_csv(folder / "Map_node_exportinglineATC.csv"))
    line_end = wide_map(pd.read_csv(folder / "Map_node_importinglineATC.csv"))
    border = {}
    for line in set(line_start) | set(line_end):
        s, e = line_start.get(line), line_end.get(line)
        if s is None or e is None or (s == node) == (e == node):
            continue
        border[line] = (s, e)
    hourly["import"] = 0.0
    hourly["export"] = 0.0
    if border:
        flow = read_filtered(folder / "Export.csv", sub, "lineATC", set(border))
        for line, grp in flow.groupby("lineATC"):
            s, e = border[line]
            v = grp.set_index("T")["value"].reindex(hourly.index).fillna(0.0)
            if s == node:            # node -> abroad
                hourly["export"] += v.clip(lower=0)
                hourly["import"] += (-v).clip(lower=0)
            else:                    # abroad -> node
                hourly["import"] += v.clip(lower=0)
                hourly["export"] += (-v).clip(lower=0)

    # water values (positive = value of a stored MWh)
    wv = read_filtered(folder / "storage_soc_dual.csv", sub, "P_storage", hydro)
    wv["value"] = -wv["value"] * sf["storage_soc"] / w
    wvp = wv.pivot_table(index="T", columns="P_storage", values="value", aggfunc="first")

    order = sorted(hourly.index, key=t_int)
    hourly = hourly.loc[order]
    hourly["t"] = [t_int(t) for t in hourly.index]
    hourly = hourly.reset_index().set_index("t").sort_index()
    wvp = wvp.reindex(order)
    wvp.index = [t_int(t) for t in wvp.index]
    wvp.index.name = "t" # type: ignore
    hourly.to_csv(out_dir / f"hourly_{node}.csv")
    wvp.sort_index().to_csv(out_dir / f"watervalues_{node}.csv")
    summary = {
        "scenario": scenario, "sub": sub, "node": node, "hours": int(len(hourly)),
        "price_mean": float(hourly["price"].mean()),
        "lostload_MWh": float(hourly["lostload"].sum()),
        "lostload_hours": int((hourly["lostload"] > EPS).sum()),
        "curtailment_GWh": float(hourly["curtailment"].sum() / 1e3),
        "spill_GWh": float(hourly["spill"].sum() / 1e3),
        "import_GWh": float(hourly["import"].sum() / 1e3),
        "export_GWh": float(hourly["export"].sum() / 1e3),
        "generation_GWh": {c[4:]: float(hourly[c].sum() / 1e3) for c in hourly if c.startswith("gen_")},
        "charge_GWh": {c[7:]: float(hourly[c].sum() / 1e3) for c in hourly if c.startswith("charge_")},
    }
    (out_dir / f"summary_{node}.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    return hourly, wvp


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------
def load_extract(scenario, node):
    d = OUT / scenario / "channels"
    h = pd.read_csv(d / f"hourly_{node}.csv", index_col="t")
    wv = pd.read_csv(d / f"watervalues_{node}.csv", index_col="t")
    return h, wv


def compare(base, rerun, ntc50=None, node="CH00", poster=False, font_scale=None):
    bs_dir = OUT / base / "border_shapley"
    out_dir = bs_dir / "channels"
    out_dir.mkdir(exist_ok=True)
    sh = pd.read_csv(bs_dir / "shapley_hourly.csv")
    sh["t"] = sh["T"].map(t_int)
    sh = sh.set_index("t").sort_index()
    hb, wvb = load_extract(base, node)
    hr, wvr = load_extract(rerun, node)
    neighbours = sorted(c[4:] for c in sh.columns if c.startswith("phi_"))

    df = pd.DataFrame(index=sh.index)
    df["month"] = sh["month"]
    df["hour"] = sh["hour"]
    df["p_all"] = sh["price_all"]
    df["p_iso"] = sh["price_autarky"]
    df["p_rerun"] = hr["price"].reindex(df.index)
    df["dispatch"] = df["p_all"] - df["p_iso"]
    df["adaptation"] = df["p_iso"] - df["p_rerun"]
    df["total"] = df["p_all"] - df["p_rerun"]
    for n in neighbours:
        df[f"phi_{n}"] = sh[f"phi_{n}"]
    df["lostload_rerun"] = hr["lostload"].reindex(df.index)
    df["lostload_base"] = hb["lostload"].reindex(df.index)
    if ntc50:
        h5, _ = load_extract(ntc50, node)
        df["p_ntc50"] = h5["price"].reindex(df.index)
    # water values: mean over the storage clusters (capacity weights unknown here)
    common = [c for c in wvb.columns if c in wvr.columns]
    df["wv_base_mean"] = wvb[common].mean(axis=1).reindex(df.index)
    df["wv_rerun_mean"] = wvr[common].mean(axis=1).reindex(df.index)
    df.to_csv(out_dir / "channels_hourly.csv")

    cols = ["p_all", "p_iso", "p_rerun", "dispatch", "adaptation", "total"] + \
           [f"phi_{n}" for n in neighbours] + (["p_ntc50"] if ntc50 else []) + \
           ["wv_base_mean", "wv_rerun_mean"]
    monthly = df.groupby("month")[cols].mean()
    monthly.to_csv(out_dir / "channels_monthly.csv")
    hod = df.groupby("hour")[cols].mean()
    hod.to_csv(out_dir / "channels_hour_of_day.csv")

    def stats(s):
        return dict(mean=s.mean(), median=s.median(), std=s.std(), q05=s.quantile(.05),
                    q95=s.quantile(.95), abs_mean=s.abs().mean(), min=s.min(), max=s.max())
    summ = pd.DataFrame({c: stats(df[c]) for c in cols}).T
    summ.to_csv(out_dir / "channels_summary.csv")
    same_sign = (np.sign(df["dispatch"]) == np.sign(df["adaptation"])) & (df["dispatch"].abs() > EPS)
    winter = df["month"].isin([10, 11, 12, 1, 2, 3])
    seasons = pd.DataFrame({"winter": df.loc[winter, cols].mean(), "summer": df.loc[~winter, cols].mean(),
                            "winter_std": df.loc[winter, cols].std(), "summer_std": df.loc[~winter, cols].std()})
    seasons.to_csv(out_dir / "channels_seasons.csv")
    day = (df.index - 1) // 24
    amp = {c: float((df[c].groupby(day).max() - df[c].groupby(day).min()).mean())
           for c in ("p_all", "p_iso", "p_rerun") + (("p_ntc50",) if ntc50 else ())}
    extra = {
        "daily_amplitude_mean": amp,
        "hours": len(df),
        "share_adaptation_dominates": float((df["adaptation"].abs() > df["dispatch"].abs()).mean()),
        "share_same_sign": float(same_sign.mean()),
        "corr_dispatch_adaptation": float(df["dispatch"].corr(df["adaptation"])),
        "corr_dispatch_total": float(df["dispatch"].corr(df["total"])),
        "lostload_rerun_MWh": float(df["lostload_rerun"].sum()),
        "lostload_rerun_hours": int((df["lostload_rerun"] > EPS).sum()),
        "lostload_base_MWh": float(df["lostload_base"].sum()),
        "price_std_all": float(df["p_all"].std()), "price_std_iso": float(df["p_iso"].std()),
        "price_std_rerun": float(df["p_rerun"].std()),
    }
    (out_dir / "channels_extra.json").write_text(json.dumps(extra, indent=1))
    print(summ.round(2).to_string())
    print(json.dumps(extra, indent=1))
    try:
        make_figures(df, monthly, hod, wvb, wvr, common, neighbours, out_dir, base, rerun,
                     poster, font_scale)
    except Exception as exc:  # figures are optional (kaleido / plotly may be missing)
        print(f"figures skipped: {exc!r}")
    return df, monthly, summ, extra


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------
def make_figures(df, monthly, hod, wvb, wvr, common, neighbours, out_dir, base, rerun,
                 poster, font_scale):
    import plotly.graph_objects as go
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from merit_order_plot import NEIGHBOUR_COLORS, PALETTE  # noqa: E402 # type: ignore
    from border_shapley import save_figure  # noqa: E402

    fs = font_scale or (2.0 if poster else 1.0)
    C_DISP, C_ADAPT, C_TOT = "#F0B600", "#583119", "#006633"
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    base_font = dict(family="Arial", size=13 * fs, color="#222")

    # 1 monthly channels (stacked bars) + total line
    fig = go.Figure()
    fig.add_bar(x=months, y=monthly["dispatch"], name="dispatch channel (Shapley, fixed bids)",
                marker_color=C_DISP)
    fig.add_bar(x=months, y=monthly["adaptation"], name="adaptation channel (bids re-optimised)",
                marker_color=C_ADAPT)
    fig.add_scatter(x=months, y=monthly["total"], mode="lines+markers", name="total (open minus closed borders)",
                    line=dict(color=C_TOT, width=3 * fs), marker=dict(size=8 * fs))
    fig.update_layout(barmode="relative", font=base_font, template="plotly_white",
                      yaxis_title="CHF/MWh", legend=dict(orientation="h", y=1.12, x=0),
                      margin=dict(l=70, r=20, t=40, b=50))
    fig.add_hline(y=0, line_color="#888", line_width=1)
    save_figure(fig, out_dir, "fig_channels_monthly", width=1400, height=700)

    # 2 monthly prices: open, isolated (fixed bids), closed rerun
    fig = go.Figure()
    fig.add_scatter(x=months, y=monthly["p_all"], name="open borders (model price)",
                    line=dict(color=C_TOT, width=3 * fs))
    fig.add_scatter(x=months, y=monthly["p_iso"], name="isolated clearing of the same bids",
                    line=dict(color=C_DISP, width=3 * fs, dash="dash"))
    fig.add_scatter(x=months, y=monthly["p_rerun"], name="closed borders, bids re-optimised",
                    line=dict(color=C_ADAPT, width=3 * fs, dash="dot"))
    if "p_ntc50" in monthly:
        fig.add_scatter(x=months, y=monthly["p_ntc50"], name="NTC halved, bids re-optimised",
                        line=dict(color="#83B819", width=3 * fs, dash="dashdot"))
    fig.update_layout(font=base_font, template="plotly_white", yaxis_title="CHF/MWh",
                      legend=dict(orientation="h", y=1.12, x=0), margin=dict(l=70, r=20, t=40, b=50))
    save_figure(fig, out_dir, "fig_channels_prices_monthly", width=1400, height=700)

    # 3 hour of day
    fig = go.Figure()
    fig.add_bar(x=hod.index, y=hod["dispatch"], name="dispatch channel", marker_color=C_DISP)
    fig.add_bar(x=hod.index, y=hod["adaptation"], name="adaptation channel", marker_color=C_ADAPT)
    fig.add_scatter(x=hod.index, y=hod["total"], mode="lines+markers", name="total",
                    line=dict(color=C_TOT, width=3 * fs))
    fig.update_layout(barmode="relative", font=base_font, template="plotly_white",
                      xaxis_title="hour of day", yaxis_title="CHF/MWh",
                      legend=dict(orientation="h", y=1.12, x=0), margin=dict(l=70, r=20, t=40, b=50))
    save_figure(fig, out_dir, "fig_channels_hour_of_day", width=1400, height=700)

    # 4 water values through the year, base vs rerun, per cluster (weekly means)
    fig = go.Figure()
    week = ((wvb.index - 1) // 168) + 1
    wb = wvb[common].groupby(week).mean()
    wr = wvr[common].reindex(wvb.index).groupby(week).mean()
    palette = list(PALETTE.values()) if isinstance(PALETTE, dict) else list(PALETTE)
    for i, c in enumerate(common):
        col = palette[i % len(palette)]
        fig.add_scatter(x=wb.index, y=wb[c], name=f"{c} open", line=dict(color=col, width=2 * fs),
                        legendgroup=c)
        fig.add_scatter(x=wr.index, y=wr[c], name=f"{c} closed", line=dict(color=col, width=2 * fs, dash="dot"),
                        legendgroup=c)
    fig.update_layout(font=dict(family="Arial", size=11 * fs, color="#222"), template="plotly_white",
                      xaxis_title="week", yaxis_title="water value [CHF/MWh]",
                      margin=dict(l=70, r=20, t=40, b=50))
    save_figure(fig, out_dir, "fig_watervalues_open_vs_closed", width=1500, height=800)

    # 5 price duration curves
    fig = go.Figure()
    x = np.arange(1, len(df) + 1)
    series = [("p_all", "open borders (model price)", C_TOT, "solid"),
              ("p_iso", "isolated clearing of the same bids", C_DISP, "dash"),
              ("p_rerun", "closed borders, bids re-optimised", C_ADAPT, "dot")]
    if "p_ntc50" in df:
        series.append(("p_ntc50", "NTC halved, bids re-optimised", "#83B819", "dashdot"))
    for col, name, colour, dash in series:
        fig.add_scatter(x=x, y=np.sort(df[col].values)[::-1], name=name,
                        line=dict(color=colour, width=3 * fs, dash=dash))
    fig.update_layout(font=base_font, template="plotly_white", xaxis_title="hours of the year",
                      yaxis_title="CHF/MWh", legend=dict(orientation="h", y=1.12, x=0),
                      margin=dict(l=70, r=20, t=40, b=60))
    save_figure(fig, out_dir, "fig_channels_duration", width=1400, height=700)

    # 6 hour of day by season (winter Oct-Mar, summer Apr-Sep)
    from plotly.subplots import make_subplots
    winter = df["month"].isin([10, 11, 12, 1, 2, 3])
    fig = make_subplots(rows=1, cols=2, subplot_titles=("winter (Oct-Mar)", "summer (Apr-Sep)"),
                        shared_yaxes=True, horizontal_spacing=0.05)
    for j, mask in enumerate((winter, ~winter), start=1):
        g = df.loc[mask].groupby("hour")[[c for c, *_ in series]].mean()
        for col, name, colour, dash in series:
            fig.add_scatter(x=g.index, y=g[col], name=name, showlegend=(j == 1),
                            line=dict(color=colour, width=3 * fs, dash=dash), row=1, col=j)
        fig.update_xaxes(title_text="hour of day", row=1, col=j)
    fig.update_yaxes(title_text="CHF/MWh", row=1, col=1)
    fig.update_layout(font=base_font, template="plotly_white",
                      legend=dict(orientation="h", y=1.15, x=0), margin=dict(l=70, r=20, t=70, b=60))
    fig.update_annotations(font_size=14 * fs)
    save_figure(fig, out_dir, "fig_channels_hour_of_day_seasons", width=1500, height=650)

    # 7 scatter dispatch vs adaptation
    fig = go.Figure()
    fig.add_scatter(x=df["dispatch"], y=df["adaptation"], mode="markers",
                    marker=dict(size=4, color=C_TOT, opacity=0.35), name="hours")
    lim = float(np.nanmax(np.abs(df[["dispatch", "adaptation"]].values)))
    fig.add_scatter(x=[-lim, lim], y=[lim, -lim], mode="lines", line=dict(color="#888", dash="dash"),
                    name="total = 0")
    fig.update_layout(font=base_font, template="plotly_white",
                      xaxis_title="dispatch channel [CHF/MWh]", yaxis_title="adaptation channel [CHF/MWh]",
                      margin=dict(l=70, r=20, t=40, b=60))
    save_figure(fig, out_dir, "fig_channels_scatter", width=900, height=800)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]) # type: ignore
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("scenario")
    e.add_argument("--node", default="CH00")
    e.add_argument("--sub", default=None, help="sub-scenario (default <scenario>_wy2008)")
    c = sub.add_parser("compare")
    c.add_argument("--base", required=True)
    c.add_argument("--rerun", required=True)
    c.add_argument("--ntc50", default=None)
    c.add_argument("--node", default="CH00")
    c.add_argument("--poster", action="store_true")
    c.add_argument("--font-scale", type=float, default=None)
    a = ap.parse_args()
    if a.cmd == "extract":
        extract(a.scenario, a.node, a.sub)
    else:
        compare(a.base, a.rerun, a.ntc50, a.node, a.poster, a.font_scale)


if __name__ == "__main__":
    main()
