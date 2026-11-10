"""Composition of the Swiss price setters, split into supply and demand side.

    python plot_creators/setter_supply_demand.py h2fix78_2035_wy2008_12hydro h2fix78_2050_wy2008_12hydro

One stacked bar per run (share of hours). Bottom: zero-price hours, then the
supply side (setter generates or discharges, Sign "gen"), then the demand side
(setter consumes or charges, Sign "con") with electrolysis at its bottom.
Ribbons between the bars trace each category from the first to the second run,
a bold line marks the supply/demand boundary. Location (CH/abroad) is dropped.
Reads output/<run>/price_setting_plants.csv. Writes
output/saee_figures/fig_setter_supply_demand.png/.pdf and setter_supply_demand.csv.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

INK, MUTED, SURFACE = "#1f1f1f", "#6b6b6b", "#ffffff"
plt.rcParams.update({"font.size": 12, "hatch.linewidth": 1.2})

# (key, label, side, colour, hatch) from bottom to top
CATS = [
    ("zero", "Zero price (surplus)", "zero", "#e3e3e3", None),
    ("Reservoir hydro|gen", "Reservoir hydro", "supply", "#2a78d6", None),
    ("Pumped hydro|gen", "Pumped hydro, generating", "supply", "#1baf7a", None),
    ("Biomass|gen", "Biomass", "supply", "#008300", None),
    ("Nuclear|gen", "Nuclear", "supply", "#6250d6", None),
    ("other_supply", "Other supply", "supply", "#8f8f8f", None),
    ("Electrolyzer|con", "Electrolysis", "demand", "#eb6834", None),
    ("Pumped hydro|con", "Pumped hydro, pumping", "demand", "#1baf7a", "///"),
    ("V2G|con", "Vehicle-to-grid, charging", "demand", "#e87ba4", None),
    ("Battery|con", "Battery, charging", "demand", "#eda100", None),
    ("Heat pump|con", "Heat pumps", "demand", "#e34948", None),
    ("other_demand", "Other demand", "demand", "#c9c9c9", None),
]
KEYS = [c[0] for c in CATS]


def year_of(run):
    return "2035" if "2035" in run else ("2050" if "2050" in run else run)


def composition(run, root):
    d = pd.read_csv(root / "output" / run / "price_setting_plants.csv").drop_duplicates("Hour")
    role = d["Technology"].astype(str).str.replace(r" (CH|abroad)$", "", regex=True)
    key = role + "|" + d["Sign"].astype(str)
    key = key.where(role != "Zero price", "zero")
    known = set(KEYS)
    sign = d["Sign"].astype(str)
    key = np.where(key.isin(known), key, np.where(sign == "gen", "other_supply", "other_demand"))
    share = pd.Series(key).value_counts(normalize=True) * 100
    members = {}
    for k in ("other_supply", "other_demand"):
        m = role[pd.Series(key, index=role.index) == k].value_counts()
        members[k] = ", ".join(m.index.tolist())
    return share.reindex(KEYS).fillna(0.0), members


def spread(ys, gap, lo, hi):
    """Push label positions apart (keeps order) within [lo, hi]: a forward
    pass enforces the minimum gap upwards, a backward pass caps at hi."""
    ys = list(ys)
    for i in range(len(ys)):
        ys[i] = max(ys[i], lo if i == 0 else ys[i - 1] + gap)
    for i in range(len(ys) - 1, -1, -1):
        ys[i] = min(ys[i], hi if i == len(ys) - 1 else ys[i + 1] - gap)
    return ys


def text_color(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return INK if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.55 else SURFACE


def plot(shares, members, outdir):
    years = list(shares)
    S = pd.DataFrame(shares)
    xs = [0.0, 1.0][: len(years)]
    w = 0.34
    fig, ax = plt.subplots(figsize=(11, 7.4))
    bottoms = {yr: np.concatenate([[0], np.cumsum(S[yr].to_numpy())[:-1]]) for yr in years}

    for i, (key, label, side, col, hatch) in enumerate(CATS):
        for x, yr in zip(xs, years):
            h = S.loc[key, yr]
            if h <= 0:
                continue
            ax.bar(x, h, bottom=bottoms[yr][i], width=w, color=col, edgecolor=SURFACE,
                   linewidth=1.5, hatch=hatch, zorder=3)
            if h >= 3.0:
                ax.text(x, bottoms[yr][i] + h / 2, f"{h:.0f}", ha="center", va="center",
                        fontsize=11, color=text_color(col), zorder=5,
                        bbox=dict(boxstyle="round,pad=0.15", fc=col, ec="none") if hatch else None)
        if len(years) == 2:
            y0b, y0t = bottoms[years[0]][i], bottoms[years[0]][i] + S.loc[key, years[0]]
            y1b, y1t = bottoms[years[1]][i], bottoms[years[1]][i] + S.loc[key, years[1]]
            if max(y0t - y0b, y1t - y1b) > 0:
                ax.add_patch(Polygon([(xs[0] + w / 2, y0b), (xs[1] - w / 2, y1b),
                                      (xs[1] - w / 2, y1t), (xs[0] + w / 2, y0t)],
                                     closed=True, fc=col, ec="none", alpha=0.18, zorder=1))

    # supply / demand boundary
    k_dem = KEYS.index("Electrolyzer|con")
    bnd = [bottoms[yr][k_dem] for yr in years]
    sup = [S.loc[[k for k, *_ in CATS if _[1] == "supply"], yr].sum() for yr in years]
    dem = [S.loc[[k for k, *_ in CATS if _[1] == "demand"], yr].sum() for yr in years]
    zer = [S.loc["zero", yr] for yr in years]
    px, py = [], []
    for x, b in zip(xs, bnd):
        px += [x - w / 2 - 0.04, x + w / 2]
        py += [b, b]
    if len(years) == 2:
        px = [px[0], px[1], px[2], px[3] + 0.04]
    ax.plot(px, py, color=INK, linewidth=2.6, zorder=6, solid_capstyle="butt")

    if len(years) == 2:
        # region totals inside the ribbons, well away from the sloping boundary
        xm = 0.5
        bnd_mid = (bnd[0] + bnd[1]) / 2
        zero_mid = (zer[0] + zer[1]) / 2
        ax.text(xm, (bnd_mid + 100.0) / 2, f"DEMAND sets the price\n{dem[0]:.0f} %  →  {dem[1]:.0f} %",
                ha="center", va="center", fontsize=12.5, color=INK, fontweight="bold", zorder=7,
                linespacing=1.3)
        ax.text(xm, (bnd_mid + zero_mid) / 2, f"SUPPLY sets the price\n{sup[0]:.0f} %  →  {sup[1]:.0f} %",
                ha="center", va="center", fontsize=12.5, color=INK, fontweight="bold", zorder=7,
                linespacing=1.3)
    # brackets left of the first bar marking the two regions
    xb = xs[0] - w / 2 - 0.08
    for lo_, hi_, name in [(bnd[0], 100.0, "Demand"), (zer[0], bnd[0], "Supply")]:
        ax.plot([xb + 0.03, xb, xb, xb + 0.03], [lo_ + 0.6, lo_ + 0.6, hi_ - 0.6, hi_ - 0.6],
                color=INK, linewidth=1.4, zorder=6)
        ax.text(xb - 0.03, (lo_ + hi_) / 2, name, rotation=90, ha="right", va="center",
                fontsize=13, color=INK, fontweight="bold")

    # right-hand labels with 2035 -> 2050 values
    last = years[-1]
    mids = [bottoms[last][i] + S.loc[k, last] / 2 for i, k in enumerate(KEYS)]
    keep = [i for i, k in enumerate(KEYS) if S.loc[k].max() > 0]
    ys = spread([mids[i] for i in keep], gap=3.6, lo=1.8, hi=99.5)
    for i, y in zip(keep, ys):
        key, label, side, col, hatch = CATS[i]
        vals = " → ".join(f"{S.loc[key, yr]:.1f}" for yr in years)
        xl = xs[-1] + w / 2
        ax.plot([xl + 0.01, xl + 0.07, xl + 0.11], [mids[i], y, y], color=MUTED, linewidth=0.7, zorder=2)
        ax.add_patch(plt.Rectangle((xl + 0.125, y - 1.1), 0.05, 2.2, fc=col,
                                   ec=(MUTED if key == "zero" else SURFACE), hatch=hatch,
                                   linewidth=0.8, zorder=3))
        ax.text(xl + 0.2, y, f"{label}  {vals} %", va="center", ha="left", fontsize=11, color=INK)

    ax.set_xlim(-0.5, 2.15)
    ax.set_ylim(0, 100)
    ax.set_xticks(xs)
    ax.set_xticklabels(years, fontsize=13)
    ax.set_ylabel("Share of hours (%)")
    for s in ("top", "right", "bottom"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.tick_params(axis="x", length=0)
    ax.tick_params(axis="y", colors=MUTED, labelcolor=INK)
    ax.set_title("Who sets the Swiss electricity price: supply or demand?", loc="left", color=INK,
                 fontsize=15, pad=12)
    note = ("Price-setting technology per hour, location-free. FEM, weather year 2008, hydrogen at "
            "78 CHF/MWh_H2. Supply: the setter generates or discharges. Demand: it consumes or charges; "
            "electrolysis bids the fixed hydrogen value. Other supply: " + (members.get("other_supply") or "-")
            + ". Other demand: " + (members.get("other_demand") or "-") + ".")
    fig.text(0.01, 0.01, note, fontsize=8.5, color=MUTED, wrap=True)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    for ext in ("png", "pdf"):
        fig.savefig(outdir / f"fig_setter_supply_demand.{ext}", dpi=300)
    plt.close(fig)
    out = S.copy()
    out.index = [c[1] for c in CATS]
    out.insert(0, "side", [c[2] for c in CATS])
    out.to_csv(outdir / "setter_supply_demand.csv")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = Path(a.root)
    outdir = Path(a.out) if a.out else root / "output" / "saee_figures"
    outdir.mkdir(parents=True, exist_ok=True)
    shares, members = {}, {}
    for r in a.runs:
        s, m = composition(r, root)
        shares[year_of(r)] = s
        for k, v in m.items():
            members[k] = ", ".join(sorted(set(filter(None, (members.get(k, "") + ", " + v).split(", ")))))
    out = plot(shares, members, outdir)
    print(out.round(2).to_string())
    print(f"written to {outdir}")


if __name__ == "__main__":
    main()
