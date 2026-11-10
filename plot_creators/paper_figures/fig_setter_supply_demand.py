"""Price-setting technology per hour, split into supply and demand side.

    python plot_creators/paper_figures/fig_setter_supply_demand.py \
        h2fix78_2035_wy2008_12hydro h2fix78_2050_wy2008_12hydro [--out DIR]

One stacked bar per run (share of hours, location-free). Bottom: zero-price
hours, then the supply side (setter generates or discharges), a bold line,
then the demand side (setter consumes or charges) with electrolysis at its
bottom. Ribbons trace each category from the first to the second run.
A thin rail on the left of the electrolysis segment shows where the tied
electrolysers sit (setter_location.py): teal = Swiss units, grey = abroad,
hours split by the capacity of the tied units; the share abroad is printed
inside the segment.
Reads output/<run>/price_setting_plants.csv and the candidate pool.
Writes fig_setter_supply_demand.png/.pdf and setter_supply_demand.csv.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.patches import Polygon, Rectangle

import paper_style as S
import setter_location as L

S.apply()
import matplotlib.pyplot as plt  # noqa: E402

# (key, label, side, colour, hatch) from bottom to top
CATS = [
    ("zero", "Zero price (surplus)", "zero", S.TECH_COLOR["Zero price"], None),
    ("Reservoir hydro|gen", "Reservoir hydro", "supply", S.TECH_COLOR["Reservoir hydro"], None),
    ("Pumped hydro|gen", "Pumped hydro, generating", "supply", S.TECH_COLOR["Pumped hydro"], None),
    ("Biomass|gen", "Biomass", "supply", S.TECH_COLOR["Biomass"], None),
    ("Nuclear|gen", "Nuclear", "supply", S.TECH_COLOR["Nuclear"], None),
    ("other_supply", "Other supply", "supply", S.TECH_COLOR["Other"], None),
    ("Electrolyzer|con", "Electrolysis", "demand", S.TECH_COLOR["Electrolyzer"], None),
    ("Pumped hydro|con", "Pumped hydro, pumping", "demand", S.TECH_COLOR["Pumped hydro"], "//"),
    ("Battery|con", "Battery, charging", "demand", S.TECH_COLOR["Battery"], None),
    ("V2G|con", "Vehicle-to-grid, charging", "demand", S.TECH_COLOR["V2G"], None),
    ("Heat pump|con", "Heat pumps", "demand", S.TECH_COLOR["Heat pump"], None),
    ("other_demand", "Other demand", "demand", S.TECH_COLOR["Other"], "//"),
]
KEYS = [c[0] for c in CATS]


def composition(run, root):
    d = pd.read_csv(root / "output" / run / "price_setting_plants.csv").drop_duplicates("Hour")
    role = d["Technology"].astype(str).str.replace(r" (CH|abroad)$", "", regex=True)
    sign = d["Sign"].astype(str)
    key = (role + "|" + sign).where(role != "Zero price", "zero")
    key = np.where(key.isin(KEYS), key, np.where(sign == "gen", "other_supply", "other_demand"))
    key = pd.Series(key, index=d.index)
    share = key.value_counts(normalize=True) * 100
    members = {k: ", ".join(role[key == k].value_counts().index) for k in ("other_supply", "other_demand")}
    return share.reindex(KEYS).fillna(0.0), members


def spread(ys, gap, lo, hi):
    """Move label positions apart (order kept, at least `gap`) inside [lo, hi]."""
    ys = list(ys)
    n = len(ys)
    for _ in range(100):
        for i in range(n):
            ys[i] = max(ys[i], lo if i == 0 else ys[i - 1] + gap)
        for i in reversed(range(n)):
            ys[i] = min(ys[i], hi if i == n - 1 else ys[i + 1] - gap)
    return ys


def fmt(v):
    if v < 0.05:
        return "0"
    return f"{v:.0f}" if v >= 9.5 else f"{v:.1f}"


def plot(shares, outdir, formats, el_loc=None):
    years = list(shares)
    T = pd.DataFrame(shares)
    xs = [0.0, 1.25][: len(years)]
    w = 0.34
    fig, ax = plt.subplots(figsize=(11.5, 5.9))
    bottoms = {yr: np.concatenate([[0], np.cumsum(T[yr].to_numpy())[:-1]]) for yr in years}

    for i, (key, label, side, col, hatch) in enumerate(CATS):
        for x, yr in zip(xs, years):
            h = T.loc[key, yr]
            if h > 0:
                ax.add_patch(Rectangle((x - w / 2, bottoms[yr][i]), w, h, fc=col, ec=S.SURFACE,
                                       lw=1.5, hatch=hatch, zorder=3))
        if len(years) == 2:
            y0b, y1b = bottoms[years[0]][i], bottoms[years[1]][i]
            y0t, y1t = y0b + T.loc[key, years[0]], y1b + T.loc[key, years[1]]
            if max(y0t - y0b, y1t - y1b) > 0:
                ax.add_patch(Polygon([(xs[0] + w / 2, y0b), (xs[1] - w / 2, y1b),
                                      (xs[1] - w / 2, y1t), (xs[0] + w / 2, y0t)],
                                     closed=True, fc=col, ec="none", alpha=0.2, zorder=1))

    # where the electrolysers on the margin sit: rail + share abroad
    k_el = KEYS.index("Electrolyzer|con")
    for x, yr in zip(xs, years):
        if not el_loc or yr not in el_loc:
            continue
        ch_frac = el_loc[yr]
        b0, h = bottoms[yr][k_el], T.loc["Electrolyzer|con", yr]
        xr = x - w / 2 - 0.022
        ax.plot([xr, xr], [b0, b0 + h * ch_frac], color=S.COUNTRY_COLOR["CH"], lw=5,
                solid_capstyle="butt", zorder=5)
        ax.plot([xr, xr], [b0 + h * ch_frac, b0 + h], color=S.INK_2, lw=5, solid_capstyle="butt",
                zorder=5)
        ab = 100 * (1 - ch_frac)
        ax.text(x, b0 + h * 0.55, (f"{ab:.1f}" if ab >= 99.5 else f"{ab:.0f}") + " %\nabroad",
                ha="center", va="center", color=S.text_on(S.TECH_COLOR["Electrolyzer"]),
                linespacing=1.15, zorder=6)

    # supply | demand boundary
    k_dem = KEYS.index("Electrolyzer|con")
    bnd = [bottoms[yr][k_dem] for yr in years]
    side_sum = {s: [T.loc[[c[0] for c in CATS if c[2] == s], yr].sum() for yr in years]
                for s in ("supply", "demand")}
    for x, b in zip(xs, bnd):
        ax.plot([x - w / 2 - 0.03, x + w / 2 + 0.03], [b, b], color=S.INK, lw=3, zorder=6,
                solid_capstyle="butt")
    if len(years) == 2:
        ax.plot([xs[0] + w / 2, xs[1] - w / 2], bnd, color=S.INK_2, lw=1.0, ls=(0, (4, 3)), zorder=6)
        ym = sum(bnd) / 2
        box = dict(boxstyle="round,pad=0.25", fc=S.SURFACE, ec="none", alpha=0.85)
        arrow = "→"
        xm = (xs[0] + xs[1]) / 2
        ax.text(xm, ym + 3, f"Demand sets the price\n{side_sum['demand'][0]:.0f} %  {arrow}  "
                f"{side_sum['demand'][1]:.0f} %", ha="center", va="bottom", color=S.INK,
                linespacing=1.25, zorder=7, bbox=box)
        ax.text(xm, ym - 3, f"Supply sets the price\n{side_sum['supply'][0]:.0f} %  {arrow}  "
                f"{side_sum['supply'][1]:.0f} %", ha="center", va="top", color=S.INK,
                linespacing=1.25, zorder=7, bbox=box)

    # right-hand labels: category, 2035 -> 2050
    last = years[-1]
    mids = [bottoms[last][i] + T.loc[k, last] / 2 for i, k in enumerate(KEYS)]
    keep = [i for i, k in enumerate(KEYS) if T.loc[k].max() >= 0.05]
    ys = spread([mids[i] for i in keep], gap=6.6, lo=2.5, hi=99)
    xl = xs[-1] + w / 2
    for i, y in zip(keep, ys):
        key, label, side, col, hatch = CATS[i]
        vals = " \u2192 ".join(fmt(T.loc[key, yr]) for yr in years)
        ax.plot([xl + 0.01, xl + 0.06, xl + 0.10], [mids[i], y, y], color=S.MUTED, lw=0.8, zorder=2)
        ax.text(xl + 0.12, y, f"{label}  {vals} %", va="center", ha="left", color=S.INK)

    ax.set_xlim(-0.25, 2.95)
    ax.set_ylim(0, 100)
    ax.set_xticks(xs)
    ax.set_xticklabels(years)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("Share of hours (%)")
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="x", length=0, pad=8)
    fig.subplots_adjust(left=0.085, right=0.995, top=0.97, bottom=0.08)
    S.save(fig, outdir, "fig_setter_supply_demand", formats)
    out = T.copy()
    out.index = [c[1] for c in CATS]
    out.insert(0, "side", [c[2] for c in CATS])
    out.round(3).to_csv(Path(outdir) / "setter_supply_demand.csv")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="output/paper_figures")
    ap.add_argument("--formats", default="png,pdf")
    a = ap.parse_args()
    root = Path(a.root)
    shares, members, el_loc = {}, {}, {}
    for r in a.runs:
        s, m = composition(r, root)
        shares[S.year_of(r)] = s
        el, n = L.electrolysis_location(root / "output" / r)
        el_loc[S.year_of(r)] = float(el["ch_share"].sum() / len(el))
        print(S.year_of(r), "electrolysis hours by location class (% of all hours):",
              (el["class"].value_counts() / n * 100).round(2).to_dict(),
              "| Swiss capacity share on average %.3f" % el_loc[S.year_of(r)])
        for k, v in m.items():
            members.setdefault(k, set()).update(filter(None, v.split(", ")))
    out = plot(shares, a.out, a.formats.split(","), el_loc)
    print(out.round(1).to_string())
    print("other supply:", sorted(members.get("other_supply", [])))
    print("other demand:", sorted(members.get("other_demand", [])))


if __name__ == "__main__":
    main()
