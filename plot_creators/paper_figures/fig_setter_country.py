"""Where is the unit that sets the Swiss price?

    python plot_creators/paper_figures/fig_setter_country.py \
        h2fix78_2035_wy2008_12hydro h2fix78_2050_wy2008_12hydro \
        [--beyond merge|separate] [--rule capacity|equal] [--out DIR]

Rules in setter_location.py. Only units in the coupled region count (nodes
linked to Switzerland by uncongested lines). The hour is split between the
tied units of the setting technology by capacity (or equally between the
countries holding one with --rule equal).

--beyond merge (default): a unit beyond the four neighbours is counted for
the neighbour(s) its price reaches Switzerland through, in equal parts when
several coupled neighbours lead to it. Bars: Switzerland, the four
neighbours, zero price.
--beyond separate: every share stays with the country where the unit sits;
units beyond the neighbours form a "Rest of Europe" bar.

Light bars = first run (2035), dark = second (2050).
Writes fig_setter_country.png/.pdf, setter_country.csv and
setter_country_by_technology.csv.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.patches import Patch

import paper_style as S
import setter_location as L

S.apply()
import matplotlib.pyplot as plt  # noqa: E402

CATS = ["CH", "FR", "DE", "IT", "AT", "Rest", "Zero price"]
LABEL = {"CH": "Switzerland", "FR": "France", "DE": "Germany", "IT": "Italy", "AT": "Austria",
         "Rest": "Rest of\nEurope", "Zero price": "Zero price"}


def shares(run, root, rule, beyond):
    own, via, setter = L.split(root / "output" / run, rule)
    n = len(own)
    if beyond == "merge":
        tot = own.drop(columns=["Rest"]).add(via.reindex(columns=own.columns.drop("Rest"),
                                                         fill_value=0.0), fill_value=0.0)
        tot["Rest"] = via["unreached"]          # zero when every unit is reachable
    else:
        tot = own
    share = tot.reindex(columns=CATS, fill_value=0.0).sum() / n * 100
    tech = tot.join(setter["role"]).groupby("role").sum().T / n * 100
    return share, tech


def plot(tabs, outdir, formats):
    years = list(tabs)
    T = pd.DataFrame(tabs).reindex(CATS)
    if (T.loc["Rest"] < 0.05).all():          # merged: no rest-of-Europe bar
        T = T.drop(index="Rest")
    cats = list(T.index)
    fig, ax = plt.subplots(figsize=(11.5, 5.6))
    S.grid(ax, "y")
    x = np.arange(len(cats))
    w = 0.38
    for k, yr in enumerate(years):
        off = (k - (len(years) - 1) / 2) * (w + 0.03)
        for xi, c in zip(x, cats):
            base = S.COUNTRY_COLOR.get(c, S.TECH_COLOR["Zero price"])
            col = S.tint(base, 0.55) if k == 0 and len(years) == 2 else base
            v = T.loc[c, yr]
            ax.bar(xi + off, v, width=w, color=col, linewidth=0, zorder=2)
            ax.text(xi + off, v + 0.8, f"{v:.0f}" if v >= 9.5 else f"{v:.1f}",
                    ha="center", va="bottom", color=S.INK)
    ax.set_xticks(x)
    ax.set_xticklabels([LABEL[c] for c in cats])
    ax.tick_params(axis="x", length=0, pad=6)
    ax.set_ylabel("Share of hours (%)")
    ax.set_ylim(0, T.to_numpy().max() * 1.15)
    if len(years) == 2:
        handles = [Patch(fc=S.tint(S.INK_2, 0.55), label=years[0]), Patch(fc=S.INK_2, label=years[1])]
        ax.legend(handles=handles, loc="upper center", ncol=2, handlelength=1.2, columnspacing=1.2)
    fig.subplots_adjust(left=0.085, right=0.995, top=0.97, bottom=0.16)
    S.save(fig, outdir, "fig_setter_country", formats)
    return T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="output/paper_figures")
    ap.add_argument("--rule", default="capacity", choices=["capacity", "equal"])
    ap.add_argument("--beyond", default="merge", choices=["merge", "separate"])
    ap.add_argument("--formats", default="png,pdf")
    a = ap.parse_args()
    root, out = Path(a.root), Path(a.out)
    tabs, techs = {}, {}
    for r in a.runs:
        share, tech = shares(r, root, a.rule, a.beyond)
        yr = S.year_of(r)
        tabs[yr], techs[yr] = share, tech
    T = plot(tabs, out, a.formats.split(","))
    print(f"rule {a.rule}, beyond {a.beyond}")
    print(T.round(1).to_string())
    T.round(2).to_csv(out / "setter_country.csv")
    pd.concat(techs, names=["year", "country"]).round(2).to_csv(out / "setter_country_by_technology.csv")


if __name__ == "__main__":
    main()
