"""Hourly and monthly effect of each Swiss border on the Swiss price
(fixed-bid Shapley attribution, plot_creators/border_shapley.py).

    python plot_creators/paper_figures/fig_border_effects.py \
        h2fix78_2035_wy2008_12hydro h2fix78_2050_wy2008_12hydro \
        [--week t_1177:t_1344] [--out DIR]

Writes
    fig_border_week_<year>.png/.pdf  one week, hourly: price with and without
                                     neighbours (lines) and the border effects
                                     (stacked bars, they fill the gap exactly)
    fig_border_week_flows_<year>     same week, border effects (top) against the net
                                     export over each border (bottom, GW, up = export
                                     from Switzerland, so that up raises the price in
                                     both panels)
    fig_border_monthly.png/.pdf      monthly means of the border effects, one
                                     panel per run, dot = sum of all borders
    border_effects_monthly.csv, border_effects_week.csv
Reads output/<run>/border_shapley/shapley_hourly.csv. Money in the
currency of paper_style (EUR by default, converted from the model's CHF2017).
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import paper_style as S

S.apply()
import matplotlib.pyplot as plt  # noqa: E402

NODE = {"FR": "FR00", "IT": "IT00", "DE": "DE00", "AT": "AT00"}
MONTHS = "JFMAMJJASOND"
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load(run, root):
    d = pd.read_csv(root / "output" / run / "border_shapley" / "shapley_hourly.csv")
    d["h"] = d["T"].str[2:].astype(int)
    money = [c for c in d.columns if c.startswith(("price_", "phi_")) or c in ("trade_effect",)]
    d[money] = d[money].apply(S.money)          # model CHF2017 -> figure currency
    return d.sort_values("h").reset_index(drop=True)


def stacked(ax, x, vals, width, **kw):
    """Diverging stacked bars: positives up, negatives down, order kept."""
    pos = np.zeros(len(x))
    neg = np.zeros(len(x))
    for c in S.NEIGHBOURS:
        v = vals[c]
        up, dn = np.clip(v, 0, None), np.clip(v, None, 0)
        ax.bar(x, up, bottom=pos, width=width, color=S.COUNTRY_COLOR[c], zorder=2, **kw)
        ax.bar(x, dn, bottom=neg, width=width, color=S.COUNTRY_COLOR[c], zorder=2, **kw)
        pos += up
        neg += dn
    return pos, neg


def legend_items(with_lines):
    h = [Patch(fc=S.COUNTRY_COLOR[c], label=S.COUNTRY_LABEL[c]) for c in S.NEIGHBOURS]
    if with_lines:
        h += [Line2D([], [], color=S.INK, lw=2.4, label="with neighbours"),
              Line2D([], [], color=S.INK, lw=2.0, ls=(0, (3, 2)), label="without")]
    else:
        h += [Line2D([], [], color=S.INK, marker="o", ls="none", ms=9, mec=S.SURFACE, mew=1.5,
                     label="sum of borders")]
    return h


def week_figure(d, year, t_a, t_b, ylim, outdir, formats):
    w = d[(d["h"] >= t_a) & (d["h"] <= t_b)].reset_index(drop=True)
    x = np.arange(len(w))
    vals = {c: w[f"phi_{NODE[c]}"].to_numpy() for c in S.NEIGHBOURS}
    fig, ax = plt.subplots(figsize=(12.3, 5.6))
    S.grid(ax, "y")
    stacked(ax, x, vals, width=1.0, linewidth=0)
    ax.step(x, w["price_model"], where="mid", color=S.INK, lw=2.4, zorder=4)
    ax.step(x, w["price_autarky"], where="mid", color=S.INK, lw=2.0, ls=(0, (3, 2)), zorder=4)
    ax.axhline(0, color=S.INK_2, lw=0.9, zorder=3)
    days = w.index[w["hour"] == 12]
    ax.set_xticks(days)
    ax.set_xticklabels([f"{int(dd) - 31} Feb" if m == 2 else f"day {int(dd)}"
                        for dd, m in zip(w.loc[days, "day"], w.loc[days, "month"])])
    for k in w.index[w["hour"] == 0][1:]:
        ax.axvline(k - 0.5, color=S.GRID, lw=0.8, zorder=1)
    ax.tick_params(axis="x", length=0, pad=6)
    ax.set_xlim(-0.5, len(w) - 0.5)
    ax.set_ylim(*ylim)
    ax.set_ylabel(S.PRICE_UNIT)
    ax.legend(handles=legend_items(True), loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=6,
              handlelength=1.4, columnspacing=1.3, borderaxespad=0.2)
    fig.subplots_adjust(left=0.075, right=0.995, top=0.9, bottom=0.08)
    S.save(fig, outdir, f"fig_border_week_{year}", formats)
    return w


def week_flow_figure(d, year, t_a, t_b, ylim_phi, ylim_flow, outdir, formats):
    w = d[(d["h"] >= t_a) & (d["h"] <= t_b)].reset_index(drop=True)
    x = np.arange(len(w))
    phi = {c: w[f"phi_{NODE[c]}"].to_numpy() for c in S.NEIGHBOURS}
    nex = {c: ((w[f"flow_out_{NODE[c]}"] - w[f"flow_in_{NODE[c]}"]) / 1000).to_numpy() for c in S.NEIGHBOURS}
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(12.3, 6.2), sharex=True,
                                 gridspec_kw=dict(hspace=0.12))
    for ax, vals, lim, lab in ((a1, phi, ylim_phi, f"Effect on price\n({S.PRICE_UNIT})"),
                               (a2, nex, ylim_flow, "Net export\n(GW)")):
        S.grid(ax, "y")
        stacked(ax, x, vals, width=1.0, linewidth=0)
        ax.axhline(0, color=S.INK_2, lw=0.9, zorder=3)
        for k in w.index[w["hour"] == 0][1:]:
            ax.axvline(k - 0.5, color=S.GRID, lw=0.8, zorder=1)
        ax.set_ylim(*lim)
        ax.set_ylabel(lab)
    days = w.index[w["hour"] == 12]
    a2.set_xticks(days)
    a2.set_xticklabels([f"{int(dd) - 31} Feb" if m == 2 else f"day {int(dd)}"
                        for dd, m in zip(w.loc[days, "day"], w.loc[days, "month"])])
    a2.tick_params(axis="x", length=0, pad=6)
    a1.tick_params(axis="x", length=0)
    a2.set_xlim(-0.5, len(w) - 0.5)
    handles = [Patch(fc=S.COUNTRY_COLOR[c], label=S.COUNTRY_LABEL[c]) for c in S.NEIGHBOURS]
    fig.legend(handles=handles, loc="upper center", ncol=4, bbox_to_anchor=(0.54, 1.0),
               handlelength=1.4, columnspacing=1.5)
    fig.subplots_adjust(left=0.1, right=0.995, top=0.9, bottom=0.07)
    S.save(fig, outdir, f"fig_border_week_flows_{year}", formats)
    stats = {}
    for c in S.NEIGHBOURS:
        f, v = pd.Series(nex[c]), pd.Series(phi[c])
        stats[c] = dict(corr=round(float(f.corr(v)), 2),
                        h_flow_but_no_effect=int(((f.abs() > 0.5) & (v.abs() < 0.5)).sum()),
                        h_effect_against_flow=int(((f * v) < 0).sum() if True else 0),
                        mean_abs_phi=round(float(v.abs().mean()), 1), mean_abs_flow=round(float(f.abs().mean()), 2))
    return stats


def monthly_figure(tabs, outdir, formats):
    lim = max(max(t[S.NEIGHBOURS].clip(lower=0).sum(axis=1).max(),
                  -t[S.NEIGHBOURS].clip(upper=0).sum(axis=1).min()) for t in tabs.values()) * 1.12
    fig, axes = plt.subplots(1, len(tabs), figsize=(12.3, 5.6), sharey=True, squeeze=False)
    for ax, (yr, t) in zip(axes[0], tabs.items()):
        S.grid(ax, "y")
        x = np.arange(1, 13)
        stacked(ax, x, {c: t[c].to_numpy() for c in S.NEIGHBOURS}, width=0.72,
                edgecolor=S.SURFACE, linewidth=1.0)
        ax.scatter(x, t["net"], s=70, color=S.INK, edgecolor=S.SURFACE, linewidth=1.5, zorder=4)
        ax.axhline(0, color=S.INK_2, lw=0.9, zorder=3)
        ax.set_xticks(x)
        ax.set_xticklabels(list(MONTHS))
        ax.tick_params(axis="x", length=0)
        ax.set_xlim(0.4, 12.6)
        ax.set_ylim(-lim, lim)
        ax.text(0.02, 0.98, f"{yr}, annual mean {t.attrs['annual_net']:+.1f}".replace("-", "−"),
                transform=ax.transAxes, ha="left", va="top", color=S.INK)
    axes[0, 0].set_ylabel(S.PRICE_UNIT)
    fig.legend(handles=legend_items(False), loc="upper center", ncol=5, handlelength=1.4,
               columnspacing=1.3, bbox_to_anchor=(0.53, 1.0))
    fig.subplots_adjust(left=0.075, right=0.995, top=0.88, bottom=0.07, wspace=0.06)
    S.save(fig, outdir, "fig_border_monthly", formats)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="output/paper_figures")
    ap.add_argument("--week", default="t_1177:t_1344", help="first:last hour (19-25 Feb)")
    ap.add_argument("--formats", default="png,pdf")
    a = ap.parse_args()
    root, out, formats = Path(a.root), Path(a.out), a.formats.split(",")
    t_a, t_b = (int(s.split("_")[1]) for s in a.week.split(":"))
    data = {S.year_of(r): load(r, root) for r in a.runs}

    # common y range for the week figures
    lo, hi = 0.0, 0.0
    for d in data.values():
        w = d[(d["h"] >= t_a) & (d["h"] <= t_b)]
        ph = w[[f"phi_{NODE[c]}" for c in S.NEIGHBOURS]]
        lo = min(lo, ph.clip(upper=0).sum(axis=1).min())
        hi = max(hi, ph.clip(lower=0).sum(axis=1).max(), w["price_model"].max(), w["price_autarky"].max())
    ylim = (np.floor(lo / 20) * 20, np.ceil(hi * 1.05 / 20) * 20)

    # common ranges for the flow figures
    lo_f, hi_f, lo_p, hi_p = 0.0, 0.0, 0.0, 0.0
    for d in data.values():
        w = d[(d["h"] >= t_a) & (d["h"] <= t_b)]
        ph = w[[f"phi_{NODE[c]}" for c in S.NEIGHBOURS]]
        nx = pd.DataFrame({c: (w[f"flow_out_{NODE[c]}"] - w[f"flow_in_{NODE[c]}"]) / 1000 for c in S.NEIGHBOURS})
        lo_p, hi_p = min(lo_p, ph.clip(upper=0).sum(axis=1).min()), max(hi_p, ph.clip(lower=0).sum(axis=1).max())
        lo_f, hi_f = min(lo_f, nx.clip(upper=0).sum(axis=1).min()), max(hi_f, nx.clip(lower=0).sum(axis=1).max())
    ylim_phi = (np.floor(lo_p * 1.08 / 10) * 10, np.ceil(hi_p * 1.08 / 10) * 10)
    ylim_flow = (np.floor(lo_f * 1.08 / 2) * 2, np.ceil(hi_f * 1.08 / 2) * 2)

    weeks, tabs = [], {}
    for yr, d in data.items():
        st = week_flow_figure(d, yr, t_a, t_b, ylim_phi, ylim_flow, out, formats)
        print(f"{yr} week, effect vs net export per border:", st)
        w = week_figure(d, yr, t_a, t_b, ylim, out, formats)
        weeks.append(w.assign(year=yr))
        m = d.groupby("month")[[f"phi_{NODE[c]}" for c in S.NEIGHBOURS]].mean()
        m.columns = S.NEIGHBOURS
        m["net"] = m.sum(axis=1)
        m["price_with"] = d.groupby("month")["price_model"].mean()
        m["price_without"] = d.groupby("month")["price_autarky"].mean()
        m.attrs["annual_net"] = float(d[[f"phi_{NODE[c]}" for c in S.NEIGHBOURS]].sum(axis=1).mean())
        tabs[yr] = m
        ww = w[[f"phi_{NODE[c]}" for c in S.NEIGHBOURS]]
        print(f"{yr} week: price with {w['price_model'].mean():.1f}, without {w['price_autarky'].mean():.1f}, "
              f"mean effect {ww.sum(axis=1).mean():+.1f}, by border {ww.mean().round(1).to_dict()}")
        print(f"{yr} annual: {m.attrs['annual_net']:+.2f}, by border "
              f"{d[[f'phi_{NODE[c]}' for c in S.NEIGHBOURS]].mean().round(2).to_dict()}")
    monthly_figure(tabs, out, formats)
    pd.concat(tabs, names=["year", "month"]).round(3).to_csv(out / "border_effects_monthly.csv")
    pd.concat(weeks).drop(columns=["h"]).round(3).to_csv(out / "border_effects_week.csv", index=False)


if __name__ == "__main__":
    main()
