"""Shapley decomposition of one hour: all 16 border coalitions and the waterfall.

    python plot_creators/paper_figures/fig_shapley_waterfall.py h2fix78_2035_wy2008_12hydro --hour t_1234 [--out DIR]

Same clearing as plot_creators/border_shapley.py: the Swiss bids of the hour
plus, for every OPEN border, one import block (NTC import capacity at the
neighbour's price) and one export block (NTC export capacity at the
neighbour's price). The Swiss market is cleared for all 2^4 = 16 subsets of
open borders; the Shapley value of a border is its marginal effect averaged
over all orders in which the borders can be opened. The values add up
exactly to price(all open) - price(all closed).

Needs the hour cache of fig_merit_order.py (run its extract step for a range
containing the hour). Writes shapley_coalitions_<year>_<t>.csv,
fig_shapley_waterfall_<year>_<t>.png/.pdf and fig_shapley_grid_<year>_<t>.png/.pdf
(the 16 coalition prices as a 4 x 4 table: rows = France/Germany, columns =
Italy/Austria, both in Gray-code order so that neighbouring cells differ by
exactly one border), shapley_paths_<year>_<t>.csv and
fig_shapley_paths_<border>_<year>_<t>.png/.pdf (for each border every order in
which the other borders can be opened before it, the price step it causes and
how many of the 4! = 24 full orders that path stands for). Money in the currency of
paper_style (EUR by default).
"""
import argparse
import itertools
import math
from pathlib import Path

import numpy as np
import pandas as pd

import paper_style as S
import fig_merit_order as M          # cache location, loader, NODE

S.apply()
import matplotlib.pyplot as plt  # noqa: E402

NB = {"FR00": "FR", "DE00": "DE", "IT00": "IT", "AT00": "AT"}


def coalitions(D, plants, t):
    BS = M.BS
    s_bid, s_cap, d_bid, d_cap = BS.domestic_blocks(D, plants, t)
    trade = BS.trade_blocks_at(D, M.NODE, t)
    nbs = [n for n in NB if n in trade]
    rows, price = [], {}
    for r in range(len(nbs) + 1):
        for S_ in itertools.combinations(range(len(nbs)), r):
            sb, sc, db, dc = [s_bid], [s_cap], [d_bid], [d_cap]
            for i in S_:
                ci, _, co, _, pn = trade[nbs[i]]
                if ci > M.EPS:
                    sb.append(np.array([pn])); sc.append(np.array([ci]))
                if co > M.EPS:
                    db.append(np.array([pn])); dc.append(np.array([co]))
            p = M.clear(np.concatenate(sb), np.concatenate(sc), np.concatenate(db), np.concatenate(dc))
            price[S_] = p
            rows.append({**{NB[n]: ("open" if k in S_ else "closed") for k, n in enumerate(nbs)},
                         "open borders": len(S_), "price": S.money(p)})
    n = len(nbs)
    phi = {}
    for i in range(n):
        others = [j for j in range(n) if j != i]
        v = 0.0
        for r in range(n):
            w = math.factorial(r) * math.factorial(n - r - 1) / math.factorial(n)
            for S_ in itertools.combinations(others, r):
                v += w * (price[tuple(sorted(S_ + (i,)))] - price[S_])
        phi[NB[nbs[i]]] = S.money(v)
    info = {NB[n]: dict(price_nb=S.money(trade[n][4]), ntc_in=trade[n][0], ntc_out=trade[n][2])
            for n in nbs}
    return pd.DataFrame(rows), phi, S.money(price[()]), S.money(price[tuple(range(n))]), info


def waterfall(phi, p0, p1, outdir, name, formats):
    neg = sorted([c for c in phi if phi[c] < 0], key=lambda c: phi[c])
    pos = sorted([c for c in phi if phi[c] >= 0], key=lambda c: -phi[c])
    order = neg + pos
    fig, ax = plt.subplots(figsize=(11.5, 5.6))
    S.grid(ax, "y")
    x = np.arange(len(order) + 2)
    w = 0.62
    ax.bar(x[0], p0, width=w, color=S.MUTED, zorder=2)
    ax.text(x[0], p0 + 1.2, f"{p0:.1f}", ha="center", va="bottom", color=S.INK)
    level = p0
    for k, c in enumerate(order, start=1):
        v = phi[c]
        lo, hi = sorted((level, level + v))
        ax.bar(x[k], hi - lo, bottom=lo, width=w, color=S.COUNTRY_COLOR[c], zorder=2)
        lab = f"{v:+.1f}".replace("-", "−")
        if v < 0:
            ax.text(x[k], lo - 1.2, lab, ha="center", va="top", color=S.INK)
        else:
            ax.text(x[k], hi + 1.2, lab, ha="center", va="bottom", color=S.INK)
        ax.plot([x[k - 1] + w / 2, x[k] - w / 2], [level, level], color=S.INK_2, lw=1.0,
                ls=(0, (2, 2)), zorder=3)
        level += v
    ax.plot([x[-2] + w / 2, x[-1] - w / 2], [level, level], color=S.INK_2, lw=1.0, ls=(0, (2, 2)),
            zorder=3)
    ax.bar(x[-1], p1, width=w, color=S.INK, zorder=2)
    ax.text(x[-1], p1 + 1.2, f"{p1:.1f}", ha="center", va="bottom", color=S.INK)
    ax.set_xticks(x)
    ax.set_xticklabels(["without\nneighbours"] + [S.COUNTRY_LABEL[c] for c in order] + ["with\nneighbours"])
    ax.tick_params(axis="x", length=0, pad=6)
    ax.set_ylabel(S.PRICE_UNIT)
    ax.set_ylim(0, max(p0, p1, max(np.cumsum([p0] + [phi[c] for c in order]))) * 1.15)
    fig.subplots_adjust(left=0.085, right=0.995, top=0.97, bottom=0.17)
    S.save(fig, outdir, name, formats)
    return order


def grid(table, outdir, name, formats):
    """4 x 4 table of the coalition prices (rows FR/DE, columns IT/AT)."""
    states = [("closed", "closed"), ("open", "closed"), ("open", "open"), ("closed", "open")]
    rlab = ["none", "France", "France +\nGermany", "Germany"]
    clab = ["none", "Italy", "Italy +\nAustria", "Austria"]
    P = np.zeros((4, 4))
    for i, (fr, de) in enumerate(states):
        for j, (it, at) in enumerate(states):
            m = (table["FR"] == fr) & (table["DE"] == de) & (table["IT"] == it) & (table["AT"] == at)
            P[i, j] = table.loc[m, "price"].iloc[0]
    lo, hi = P.min(), P.max()
    ramp = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf"]      # palette sequential blue

    def shade(v):
        k = 0 if hi - lo < 1e-9 else int(round((v - lo) / (hi - lo) * (len(ramp) - 1)))
        return ramp[k]
    fig = plt.figure(figsize=(9.5, 5.6))
    ax = fig.add_axes([0.25, 0.04, 0.73, 0.74])
    for i in range(4):
        for j in range(4):
            col = shade(P[i, j])
            ax.add_patch(plt.Rectangle((j, 3 - i), 1, 1, fc=col, ec=S.SURFACE, lw=3))
            ax.text(j + 0.5, 3 - i + 0.5, f"{P[i, j]:.1f}", ha="center", va="center", color=S.text_on(col))
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 4)
    ax.set_xticks(np.arange(4) + 0.5)
    ax.set_xticklabels(clab)
    ax.xaxis.tick_top()
    ax.set_yticks(np.arange(4) + 0.5)
    ax.set_yticklabels(rlab[::-1])
    ax.tick_params(length=0, pad=8)
    for sp in ax.spines.values():
        sp.set_visible(False)
    fig.text(0.25 + 0.73 / 2, 0.985, "Open borders to Italy and Austria", ha="center", va="top", color=S.INK_2)
    fig.text(0.02, 0.04 + 0.74 / 2, "Open borders to\nFrance and Germany", ha="left", va="center",
             color=S.INK_2, rotation=90, linespacing=1.2)
    S.save(fig, outdir, name, formats)
    return P


def paths(table):
    """Every opening path up to each border: prefix of other borders, price
    before and after opening the border, effect, number of full orders."""
    names = list(NB.values())
    price = {}
    for _, r in table.iterrows():
        price[frozenset(c for c in names if r[c] == "open")] = r["price"]
    n = len(names)
    rows = []
    for b in names:
        others = [c for c in names if c != b]
        for k in range(n):
            for pre in itertools.permutations(others, k):
                before = price[frozenset(pre)]
                after = price[frozenset(pre) | {b}]
                rows.append(dict(border=b, path=" \u2192 ".join(["none", *[S.COUNTRY_LABEL[c] for c in pre],
                                                                    S.COUNTRY_LABEL[b]]),
                                 before=before, after=after, effect=after - before,
                                 orders=math.factorial(n - 1 - k)))
    P = pd.DataFrame(rows)
    P["weighted"] = P["effect"] * P["orders"] / math.factorial(n)
    return P


def paths_figure(P, b, outdir, name, formats):
    d = P[P["border"] == b].reset_index(drop=True)
    phi = d["weighted"].sum()
    lines = len(d) + 3
    fig = plt.figure(figsize=(11.5, 6.3))
    ax = fig.add_axes([0.01, 0.01, 0.98, 0.98])
    ax.set_axis_off()
    step = 1.0 / lines
    cols = [(0.0, "left", "Order of opening"), (0.66, "right", "before"), (0.77, "right", "after"),
            (0.88, "right", "effect"), (0.985, "right", "orders")]
    y = 1 - step / 2
    for x, ha, lab in cols:
        ax.text(x, y, lab, ha=ha, va="center", color=S.INK_2, transform=ax.transAxes)
    ax.plot([0, 1], [1 - step, 1 - step], color=S.MUTED, lw=0.8, transform=ax.transAxes)

    def f(v):
        return f"{v:.1f}".replace("-", "\u2212")
    for i, r in d.iterrows():
        y = 1 - (i + 1.5) * step
        live = abs(r["effect"]) > 0.05
        col, wt = (S.INK, "bold") if live else (S.MUTED, "normal")
        vals = [r["path"], f(r["before"]), f(r["after"]), f(r["effect"]) if live else "0", f"{r['orders']}"]
        for (x, ha, _), v in zip(cols, vals):
            ax.text(x, y, v, ha=ha, va="center", color=col, fontweight=wt, transform=ax.transAxes)
    ysep = 1 - (len(d) + 1.05) * step
    ax.plot([0, 1], [ysep, ysep], color=S.MUTED, lw=0.8, transform=ax.transAxes)
    y = ysep - step * 0.45
    terms = d[d["effect"].abs() > 0.05].groupby("effect")["orders"].sum().sort_index(ascending=False)
    expr = " + ".join(f"{o} \u00d7 {f(e)}" for e, o in terms.items())
    ax.text(0.0, y - step * 0.5, f"Shapley value of {S.COUNTRY_LABEL[b]}  =  ({expr}) / 24  =  {f(phi)} "
            f"{S.PRICE_UNIT}", ha="left", va="center", color=S.INK, transform=ax.transAxes)
    S.save(fig, outdir, name, formats)
    return phi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--hour", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="output/paper_figures")
    ap.add_argument("--formats", default="png,pdf")
    a = ap.parse_args()
    root, out = Path(a.root), Path(a.out)
    h = int(a.hour.split("_")[1])
    hours = None
    for d in sorted((root / "output" / a.run / "paper_fig_cache").glob("t*_t*")):
        lo, hi = (int(s[1:]) for s in d.name.split("_"))
        if lo <= h <= hi:
            hours = list(range(lo, hi + 1))
    if hours is None:
        raise SystemExit("run fig_merit_order.py extract for a range containing this hour first")
    mini = M.cache_dir(root, a.run, hours)
    D, plants = M.BS.load_run(mini, M.sub_of(root, a.run), M.NODE)
    t = f"t_{h}"
    table, phi, p0, p1, info = coalitions(D, plants, t)
    year = S.year_of(a.run)
    table = table.sort_values(["open borders"] + list(NB.values()), ascending=[True] + [False] * 4)
    out.mkdir(parents=True, exist_ok=True)
    table.round(2).to_csv(out / f"shapley_coalitions_{year}_{t}.csv", index=False)
    pd.Series(phi).round(3).to_csv(out / f"shapley_values_{year}_{t}.csv", header=[S.PRICE_UNIT])
    order = waterfall(phi, p0, p1, out, f"fig_shapley_waterfall_{year}_{t}", a.formats.split(","))
    P = paths(table)
    P.round(3).to_csv(out / f"shapley_paths_{year}_{t}.csv", index=False)
    for b in NB.values():
        v = paths_figure(P, b, out, f"fig_shapley_paths_{b}_{year}_{t}", a.formats.split(","))
        assert abs(v - phi[b]) < 1e-6, (b, v, phi[b])
    if set(NB.values()) <= set(table.columns):
        P = grid(table, out, f"fig_shapley_grid_{year}_{t}", a.formats.split(","))
        print("grid (rows none/FR/FR+DE/DE, cols none/IT/IT+AT/AT):")
        print(np.round(P, 1))
    print(f"{t}: without {p0:.2f}, with {p1:.2f} {S.PRICE_UNIT}; sum phi {sum(phi.values()):+.2f}")
    print("Shapley:", {c: round(phi[c], 2) for c in order})
    print("neighbours:", {c: {k: round(v, 1) for k, v in d.items()} for c, d in info.items()})
    with pd.option_context("display.width", 200):
        print(table.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
