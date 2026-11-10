"""Where does the Swiss price-setting unit sit? Shared logic for the figures.

1. Coupled region. Two nodes share one price when the line between them is
   not congested (equal prices at both ends). The coupled region of hour t is
   the set of nodes reachable from CH00 over such lines (connected component).
   Units outside it cannot set the Swiss price even if their bid happens to be
   equal (e.g. electrolysers at 53.04 behind a congested border).
2. Tied units. Interior candidates of the coupled region whose bid is within
   0.01 CHF/MWh of the highest bid and whose technology is the one chosen by
   the setter rule (model/price_setting_tech.py). Units below 1 MW are
   dropped (residual capacities such as the 0.01 MW CH00_nuclear in 2050).
3. Split. The hour is divided between the tied units in proportion to their
   capacity ("capacity", default) or equally between the countries that hold
   one ("equal").
4. Through which neighbour. A share held by a unit beyond the neighbours
   (rest of Europe) is passed on, in equal parts, to the coupled neighbours
   from which the unit's node can be reached without passing Switzerland.
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

import paper_style as S

NB = {"FR00": "FR", "IT00": "IT", "DE00": "DE", "AT00": "AT"}
TIE_TOL = 0.01
MIN_CAP_MW = 1.0
PRICE_TOL = 1e-3


def _graph(folder):
    ep = pd.read_csv(folder / "energy_balance_dual.csv")
    if "Scenarios" in ep.columns:
        ep = ep[ep["Scenarios"] == ep["Scenarios"].iloc[0]]
    P = ep.pivot_table(index="T", columns="Node", values="value")
    nodes = set(P.columns)
    ex = pd.read_csv(folder / "Map_node_exportinglineATC.csv")
    edges = set()
    for row in ex.itertuples(index=False):
        for v in row[1:]:
            if isinstance(v, str) and v:
                toks = [t for t in v.split("_") if t in nodes]
                if len(toks) >= 2:
                    edges.add((toks[0], toks[1]))
    return P, sorted(edges)


def coupled_regions(folder):
    """{hour: (region set, {neighbour: nodes reachable from it without CH})}"""
    P, edges = _graph(folder)
    col = {c: i for i, c in enumerate(P.columns)}
    a = np.array([col[e[0]] for e in edges])
    b = np.array([col[e[1]] for e in edges])
    V = P.to_numpy()
    out = {}
    for k, t in enumerate(P.index):
        ok = np.abs(V[k, a] - V[k, b]) <= PRICE_TOL
        adj = {}
        for (i, j), o in zip(edges, ok):
            if o:
                adj.setdefault(i, []).append(j)
                adj.setdefault(j, []).append(i)

        def bfs(start, blocked=()):
            seen = {start}
            st = [start]
            while st:
                u = st.pop()
                for v in adj.get(u, []):
                    if v not in seen and v not in blocked:
                        seen.add(v)
                        st.append(v)
            return seen
        region = bfs("CH00")
        reach = {NB[n]: bfs(n, blocked={"CH00"}) for n in NB if n in region}
        out[t] = (region, reach)
    return out


def _node_of(plant, nodes):
    n = str(plant).split("_")[0]
    return n if n in nodes else "CH00"


def tied_units(folder):
    """Tied units of the setting technology inside the coupled region, per hour."""
    folder = Path(folder)
    setter = pd.read_csv(folder / "price_setting_plants.csv").drop_duplicates("Hour")
    setter["role"] = setter["Technology_Raw"].map(S.role_of)
    setter.loc[setter["Technology"] == "Zero price", "role"] = "Zero price"
    regions = coupled_regions(folder)
    nodes = set().union(*(r for r, _ in regions.values()))
    nc = pd.read_csv(folder / "Map_node_country.csv")
    node_country = dict(zip(nc["Node"], nc["value"]))
    pool = pd.read_csv(glob.glob(str(folder / "price_setting_plant_pool_*.csv"))[0],
                       usecols=["Technology", "Hour", "Sign", "Max Generation_MWh", "Bidding price"])
    pool["node"] = [_node_of(p, nodes | set(node_country)) for p in pool["Technology"]]
    pool = pool[[n in regions.get(h, ({"CH00"}, {}))[0] for n, h in zip(pool["node"], pool["Hour"])]]
    top = pool.groupby("Hour")["Bidding price"].transform("max")
    tied = pool[pool["Bidding price"] >= top - TIE_TOL].copy()
    tied["role"] = tied["Technology"].map(S.role_of)
    tied["country"] = [S.country_of(p, node_country) for p in tied["Technology"]]
    tied = tied.merge(setter[["Hour", "role"]].rename(columns={"role": "setter_role"}), on="Hour")
    tied = tied[(tied["role"] == tied["setter_role"]) & (tied["Max Generation_MWh"] >= MIN_CAP_MW)]
    return setter.set_index("Hour"), tied, regions, node_country


def split(folder, rule="capacity"):
    """Per-hour shares. Returns (own, via): own has columns CH FR DE IT AT Rest
    Zero price (where the unit sits), via has FR DE IT AT (rest-of-Europe
    shares passed on to the neighbour they reach Switzerland through)."""
    setter, tied, regions, node_country = tied_units(folder)
    cols = ["CH", "FR", "DE", "IT", "AT", "Rest", "Zero price"]
    own = pd.DataFrame(0.0, index=setter.index, columns=cols)
    via = pd.DataFrame(0.0, index=setter.index, columns=["FR", "DE", "IT", "AT", "unreached"])
    own.loc[setter["role"] == "Zero price", "Zero price"] = 1.0
    for h, g in tied.groupby("Hour"):
        if setter.at[h, "role"] == "Zero price":
            continue
        if rule == "equal":
            cs = sorted(set(g["country"]))
            w = pd.Series(1.0 / len(cs), index=cs)
            units = [(c, 1.0 / len(cs) / (g["country"] == c).sum(), n)
                     for c, n in zip(g["country"], g["node"])]
        else:
            cap = g["Max Generation_MWh"].to_numpy()
            units = [(c, x / cap.sum(), n) for c, x, n in zip(g["country"], cap, g["node"])]
        for c, x, n in units:
            own.at[h, c] += x
            if c == "Rest":
                reach = regions[h][1]
                via_nb = [nb for nb, nodes in reach.items() if n in nodes]
                if via_nb:
                    for nb in via_nb:
                        via.at[h, nb] += x / len(via_nb)
                else:
                    via.at[h, "unreached"] += x
    missing = own.sum(axis=1) < 1e-9          # no tied unit of the setter technology left
    for h in own.index[missing]:
        own.at[h, S.country_of(setter.at[h, "Technology_Raw"], node_country)] = 1.0
    return own, via, setter


def electrolysis_location(folder):
    """Per electrolysis hour: who holds the tied electrolysers. Returns a
    DataFrame with ch_share (capacity share of Swiss units) and the class
    'CH only' / 'both' / 'abroad only'."""
    setter, tied, _, _ = tied_units(folder)
    el = tied[tied["setter_role"] == "Electrolyzer"]
    g = el.groupby(["Hour", "country"])["Max Generation_MWh"].sum().unstack(fill_value=0.0)
    if "CH" not in g:
        g["CH"] = 0.0
    tot = g.sum(axis=1)
    ch = g["CH"]
    cls = np.where(ch == tot, "CH only", np.where(ch > 0, "both", "abroad only"))
    return pd.DataFrame({"ch_share": ch / tot, "class": cls}), len(setter)
