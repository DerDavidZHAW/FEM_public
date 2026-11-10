"""Shapley border values versus two conventional trade indicators.

Compares, hour by hour, the Shapley value of each Swiss border (phi, CHF/MWh,
from border_shapley.py) with
  (1) the net import over that border (GW, positive = import into CH), and
  (2) the shadow value of the border's NTC constraint (CHF/MWh).

FEM does not write the duals of ATCbound_Constraint. With zero trade cost
(trade_cost_dict = 0) the KKT condition of the Export variable gives
    dual(NTC of border X) = p_X - p_CH
which is > 0 when the CH export limit binds, < 0 when the CH import limit
binds and 0 when the border is not congested (prices coupled). The script
checks this: every hour with |p_X - p_CH| > tol must have the flow at the
matching NTC bound.

Usage (from the repo root):
    python plot_creators/shapley_vs_trade_indicators.py \
        base_2035_wy2008_12hydro base_2050_wy2008_12hydro [--out output/shapley_vs_indicators]

Needs only numpy, pandas, matplotlib. Writes
    fig_shapley_vs_netimport.png/.pdf
    fig_shapley_vs_ntcdual.png/.pdf
    stats_shapley_vs_indicators.csv
    hourly_indicators_<scenario>.csv
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BORDERS = ["AT00", "DE00", "FR00", "IT00"]
LABEL = {"AT00": "Austria", "DE00": "Germany", "FR00": "France", "IT00": "Italy"}
# ZHAW border palette used in the other paper figures; gold darkened one step
# for dots on white (identity is carried by the panel title, not the colour)
COLOR = {"AT00": "#583119", "DE00": "#C99700", "FR00": "#006633", "IT00": "#6E9C12",
         "Total": "#3d3d3d"}
INK, MUTED, GRID = "#1f1f1f", "#6b6b6b", "#e4e4e4"
TOL_PRICE = 0.01   # CHF/MWh, spread below this counts as coupled
TOL_FLOW = 1.0     # MW, flow within this of the NTC counts as at the limit


def load(scen: str, root: Path) -> pd.DataFrame:
    d = pd.read_csv(root / "output" / scen / "border_shapley" / "shapley_hourly.csv")
    out = pd.DataFrame({"T": d["T"], "month": d["month"], "hour": d["hour"],
                        "price_CH": d["price_model"]})
    out["phi_Total"] = 0.0
    out["ni_Total"] = 0.0
    for b in BORDERS:
        out[f"phi_{b}"] = d[f"phi_{b}"]
        out[f"ni_{b}"] = (d[f"flow_in_{b}"] - d[f"flow_out_{b}"]) / 1000.0  # GW
        out[f"dual_{b}"] = d[f"price_{b}"] - d["price_model"]               # CHF/MWh
        at_in = d[f"flow_in_{b}"] >= d[f"ntc_in_{b}"] - TOL_FLOW
        at_out = d[f"flow_out_{b}"] >= d[f"ntc_out_{b}"] - TOL_FLOW
        out[f"atntc_{b}"] = at_in | at_out
        bad = ((out[f"dual_{b}"] > TOL_PRICE) & ~at_out) | ((out[f"dual_{b}"] < -TOL_PRICE) & ~at_in)
        if bad.any():
            print(f"WARNING {scen} {b}: {bad.sum()} hours with a price spread but no binding NTC")
        out["phi_Total"] += out[f"phi_{b}"]
        out["ni_Total"] += out[f"ni_{b}"]
    return out


def spearman(x: pd.Series, y: pd.Series) -> float:
    return float(x.rank().corr(y.rank()))


def stats_for(x: pd.Series, phi: pd.Series, kind: str) -> dict:
    """kind 'ni': expected sign of phi is opposite to x; 'dual': same sign."""
    r = float(np.corrcoef(x, phi)[0, 1])
    slope, icpt = np.polyfit(x, phi, 1)
    m = (phi.abs() > 0.01) & (x.abs() > 1e-3)
    sgn = -1 if kind == "ni" else 1
    res = dict(n=len(x), pearson=r, spearman=spearman(x, phi), R2=r * r, slope=slope,
               intercept=icpt, sign_match=float((np.sign(phi[m]) == sgn * np.sign(x[m])).mean()),
               mean_abs_phi=float(phi.abs().mean()))
    # magnitude within one direction: does a larger |x| go with a larger |phi|?
    if kind == "ni":
        dirs = {"import": x > 1e-3, "export": x < -1e-3}
    else:
        dirs = {"import": x < -TOL_PRICE, "export": x > TOL_PRICE}
    for k, msk in dirs.items():
        res[f"n_{k}"] = int(msk.sum())
        res[f"spearman_abs_{k}"] = spearman(x[msk].abs(), phi[msk].abs()) if msk.sum() > 30 else np.nan
    if kind == "dual":
        coupled = x.abs() <= TOL_PRICE
        res["share_dual_zero"] = float(coupled.mean())
        res["mean_abs_phi_dual_zero"] = float(phi[coupled].abs().mean())
        res["mean_abs_phi_dual_nonzero"] = float(phi[~coupled].abs().mean())
    return res


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
        ax.spines[s].set_linewidth(0.6)
    ax.tick_params(colors=MUTED, labelcolor=INK, width=0.6, length=3)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.axhline(0, color=MUTED, linewidth=0.6, zorder=1)
    ax.axvline(0, color=MUTED, linewidth=0.6, zorder=1)


def fmt(v, nd=2):
    return f"{v:.{nd}f}".replace("-", "−")


def panel(ax, x, phi, color, st, kind, corner):
    ax.scatter(x, phi, s=3, color=color, alpha=0.22, linewidths=0, rasterized=True, zorder=2)
    xs = np.linspace(x.min(), x.max(), 50)
    ax.plot(xs, st["slope"] * xs + st["intercept"], color=INK, linewidth=1.0, zorder=3)
    lines = [f"r = {fmt(st['pearson'])}   ρ = {fmt(st['spearman'])}",
             f"R² = {fmt(st['R2'])}   sign match {st['sign_match'] * 100:.0f} %"]
    if kind == "ni":
        lines.append(f"ρ(|x|,|φ|) imp {fmt(st['spearman_abs_import'])} · exp {fmt(st['spearman_abs_export'])}")
    else:
        lines.append(f"dual = 0 in {st['share_dual_zero'] * 100:.0f} % of hours")
        lines.append(f"mean |φ|: {fmt(st['mean_abs_phi_dual_zero'], 1)} if 0, "
                     f"{fmt(st['mean_abs_phi_dual_nonzero'], 1)} if ≠ 0")
    xa, ha = (0.97, "right") if corner == "right" else (0.03, "left")
    ax.text(xa, 0.97, "\n".join(lines), transform=ax.transAxes, ha=ha, va="top", fontsize=7.2,
            color=INK, linespacing=1.35, zorder=4,
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=GRID, lw=0.6, alpha=0.92))


def figure(data: dict, kind: str, outdir: Path, records: list):
    cols = BORDERS + (["Total"] if kind == "ni" else [])
    scen = list(data)
    fig, axes = plt.subplots(len(scen), len(cols), figsize=(3.0 * len(cols), 3.0 * len(scen) + 0.6),
                             squeeze=False)
    for i, s in enumerate(scen):
        d = data[s]
        year = "2035" if "2035" in s else ("2050" if "2050" in s else s)
        # common y range for the four single borders of one year
        lim = max(d[f"phi_{b}"].abs().max() for b in BORDERS) * 1.05
        for j, c in enumerate(cols):
            ax = axes[i, j]
            style(ax)
            phi = d[f"phi_{c}"]
            x = d[f"ni_{c}"] if kind == "ni" else d[f"dual_{c}"]
            st = stats_for(x, phi, kind)
            records.append(dict(scenario=s, year=year, border=c,
                                indicator="net_import_GW" if kind == "ni" else "ntc_dual_CHF_MWh", **st))
            panel(ax, x, phi, COLOR[c], st, kind, "right" if kind == "ni" else "left")
            if c != "Total":
                ax.set_ylim(-lim, lim)
            title = LABEL.get(c, "All borders (sum)")
            ax.set_title(f"{title}, {year}", fontsize=9.5, color=INK, loc="left", pad=4)
            if i == len(scen) - 1:
                ax.set_xlabel("Net import into CH (GW)" if kind == "ni"
                              else "NTC shadow value  $p_X - p_{CH}$ (CHF/MWh)", fontsize=8.5, color=INK)
            if j == 0:
                ax.set_ylabel("Shapley value φ (CHF/MWh)", fontsize=8.5, color=INK)
            ax.tick_params(labelsize=7.5)
    if kind == "ni":
        sup = ("Shapley value of each border versus net import, hourly, 8760 h per panel. "
               "Line = OLS fit. ρ = Spearman. Sign match = share of hours with φ < 0 when importing "
               "and φ > 0 when exporting.\nρ(|x|,|φ|) = Spearman between the magnitudes within one "
               "flow direction (does a larger flow go with a larger price effect?).")
    else:
        sup = ("Shapley value of each border versus the shadow value of its NTC constraint, hourly. "
               "Dual < 0: import limit binds, > 0: export limit binds, 0: border not congested "
               "(prices coupled).\nThe dual is derived from the node prices (zero trade cost, KKT). "
               "Line = OLS fit. ρ = Spearman. Sign match = share of hours with sign(φ) = sign(dual).")
    fig.text(0.01, 0.005, sup, fontsize=7.5, color=MUTED, ha="left", va="bottom", wrap=True)
    fig.tight_layout(rect=(0, 0.06, 1, 1), w_pad=1.2, h_pad=1.4)
    name = "fig_shapley_vs_netimport" if kind == "ni" else "fig_shapley_vs_ntcdual"
    for ext in ("png", "pdf"):
        fig.savefig(outdir / f"{name}.{ext}", dpi=300)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenarios", nargs="+")
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = Path(a.root)
    outdir = Path(a.out) if a.out else root / "output" / "shapley_vs_indicators"
    outdir.mkdir(parents=True, exist_ok=True)
    data = {s: load(s, root) for s in a.scenarios}
    for s, d in data.items():
        d.to_csv(outdir / f"hourly_indicators_{s}.csv", index=False)
    records = []
    figure(data, "ni", outdir, records)
    figure(data, "dual", outdir, records)
    S = pd.DataFrame(records)
    S.to_csv(outdir / "stats_shapley_vs_indicators.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 40):
        print(S.drop(columns=["scenario"]).round(3).to_string(index=False))
    print(f"written to {outdir}")


if __name__ == "__main__":
    main()
