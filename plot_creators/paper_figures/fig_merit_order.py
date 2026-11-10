"""Swiss merit order of one hour, with and without the neighbours, where every
foreign offer is a single foreign unit (not one block per border).

    # 1) cut the hourly result files down to the hours of interest (repeat the
    #    call until it reports "complete"; each call stops after --budget s)
    python plot_creators/paper_figures/fig_merit_order.py extract h2fix78_2035_wy2008_12hydro --hours t_1177:t_1344
    # 2) screen the hours: model price, reconstructed prices, setter
    python plot_creators/paper_figures/fig_merit_order.py screen  h2fix78_2035_wy2008_12hydro --hours t_1177:t_1344
    # 3) draw the pair
    python plot_creators/paper_figures/fig_merit_order.py plot    h2fix78_2035_wy2008_12hydro --hour t_1213 [--out DIR]

How the neighbours enter. For every neighbour X the script rebuilds all bids
of X (same formulas as for Switzerland, plot_creators/border_shapley.py) and
holds X's exchanges with third countries at their model values. X's net
supply to Switzerland at a price p is then

    NS_X(p) = imports of X from third countries
              + capacity of every supply unit of X bidding below p
              - consumption of every demand unit of X bidding above p.

Read upwards from NS_X = 0, the units of X form the import offer to
Switzerland (one block per foreign unit, up to the import NTC). Read
downwards, they form the export demand (a foreign unit that would back off or
consume more if Swiss power were cheaper), down to the export NTC. At the
model solution NS_X equals the actual flow, so the clearing with these
curves reproduces the model price (the screen step checks this hour by hour).
The fixed-bid Shapley attribution keeps the simpler price-taker blocks; this
figure only replaces them by the units behind them.

Bids and prices are drawn in the currency of paper_style (EUR by default,
converted from the model's CHF2017); the screen step reports model CHF.
Writes fig_merit_with_neighbours_<year>_<t>.png/.pdf,
fig_merit_without_neighbours_<year>_<t>.png/.pdf and merit_blocks_<year>_<t>.csv.
"""
import argparse
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

import paper_style as S

S.apply()
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from plot_creators import border_shapley as BS  # noqa: E402
from plot_creators.merit_order_plot import EPS, clear  # noqa: E402

NODE = "CH00"
NB = {"FR00": "FR", "IT00": "IT", "DE00": "DE", "AT00": "AT"}
HOURLY = {
    "energy_balance_dual", "gen", "storage_charge", "avail_plant", "V2G_charging_power_rate",
    "soc", "inflow", "storage_soc_dual", "energy_balancethermal_dual",
    "inflexble_demandTh_share_dual", "building_heat_demand_dual", "COP", "infeed",
    "curtailment", "Biomass_inflexible_generation", "demand", "HP_inflexible_demand",
    "EV_inflexible_demand", "Electrolyzer_inflexible_demand", "DH_inflexible_demand",
    "lostload", "ATC_exportlimit", "ATC_importlimit", "Export",
}
INELASTIC = "Inelastic demand"
HATCH = {"FR": "///", "DE": "\\\\\\", "IT": "xxx", "AT": "..."}
TOL = 0.01


# --------------------------------------------------------------------------- data
def hours_of(spec):
    if ":" in spec:
        a, b = (int(s.split("_")[1]) for s in spec.split(":"))
        return list(range(a, b + 1))
    return [int(s.split("_")[1]) for s in spec.split(",")]


def cache_dir(root, run, hours):
    return root / "output" / run / "paper_fig_cache" / f"t{min(hours)}_t{max(hours)}"


def extract(root, run, hours, budget):
    src, dst = root / "output" / run, cache_dir(root, run, hours)
    dst.mkdir(parents=True, exist_ok=True)
    keep = set()
    for h in hours:
        keep |= {f"t_{h}", f"t_{h - 1 if h > 1 else 8760}"}
    t0 = time.time()
    for f in sorted(src.glob("*.csv")):
        out = dst / f.name
        if out.exists() or f.name.startswith("price_setting_plant_pool"):
            continue
        cols = pd.read_csv(f, nrows=0).columns
        hourly = "T" in cols
        if (hourly and f.stem not in HOURLY) or (not hourly and f.stat().st_size > 30e6):
            continue
        if time.time() - t0 > budget:
            print("time budget used up, call extract again")
            return False
        tmp = dst / (f.name + ".part")
        if hourly:
            parts = [c[c["T"].isin(keep)] for c in pd.read_csv(f, chunksize=500_000)]
            pd.concat(parts, ignore_index=True).to_csv(tmp, index=False)
        else:
            shutil.copy(f, tmp)
        tmp.replace(out)
        print(f"  {f.name}")
    print("complete:", dst)
    return True


def sub_of(root, run):
    s = pd.read_csv(root / "output" / run / "price_setting_plants.csv", nrows=1)
    return s["SubScenario"].iloc[0]


def load(root, run, hours):
    mini = cache_dir(root, run, hours)
    sub = sub_of(root, run)
    D = {n: BS.load_run(mini, sub, n) for n in [NODE] + list(NB)}
    return D


# ------------------------------------------------------------------ the curves
def colour_role(r):
    p = str(r["plant"])
    if p.startswith("Inelastic") or p.startswith("Flexible EV charging"):
        return INELASTIC
    if p.startswith("Biomass must-run"):
        return "Biomass"
    if r.get("tier") == "renewables":
        return "Renewables"
    if p.startswith("Lost load"):
        return "Other"
    return S.role_of(p)


def third_country_import(Dx, x, t):
    fl = Dx["flow"].get(t, {})
    net = 0.0
    for line, (s, e) in Dx["border_lines"].items():
        if (e if s == x else s) == NODE:
            continue
        f = fl.get(line, 0.0) or 0.0
        net += f if e == x else -f
    return net


def residual_blocks(Dx, x_plants, x, t, cap_in, cap_out):
    rows = BS.domestic_rows(Dx, x_plants, t)
    imp3 = third_country_import(Dx, x, t)
    ns = imp3 - sum(r["capacity"] for r in rows if r["side"] == "demand")
    levels = []
    for r in sorted(rows, key=lambda r: r["bid"]):
        levels.append((r, ns, ns + r["capacity"]))
        ns += r["capacity"]
    flow_model = imp3 + sum(r["dispatch"] for r in rows if r["side"] == "supply") \
        - sum(r["dispatch"] for r in rows if r["side"] == "demand")
    imports, exports = [], []
    for r, a, b in levels:
        lo, hi = max(a, 0.0), min(b, cap_in)
        if hi > lo + EPS:
            imports.append(dict(r, side="supply", capacity=hi - lo, cap_full=r["capacity"], country=NB[x]))
    for r, a, b in reversed(levels):
        lo, hi = max(a, -cap_out), min(b, 0.0)
        if hi > lo + EPS:
            exports.append(dict(r, side="demand", capacity=hi - lo, cap_full=r["capacity"], country=NB[x]))
    return imports, exports, flow_model


def curves(D, t):
    Dch, ch_plants = D[NODE]
    rows = [dict(r, country="CH") for r in BS.domestic_rows(Dch, ch_plants, t)]
    sup = [r for r in rows if r["side"] == "supply"]
    dem = [r for r in rows if r["side"] == "demand"]
    tb = BS.trade_blocks_at(Dch, NODE, t)
    imp, exp, check = [], [], {}
    for x in NB:
        if x not in tb:
            continue
        ci, fi, co, fo, pn = tb[x]
        Dx, xp = D[x]
        i, e, fm = residual_blocks(Dx, xp, x, t, ci, co)
        imp += i
        exp += e
        check[NB[x]] = dict(price=pn, flow_in=fi - fo, flow_rebuilt=fm, ntc_in=ci, ntc_out=co)
    return sup, dem, imp, exp, check


def clear_rows(sup, dem):
    return clear(np.array([r["bid"] for r in sup]), np.array([r["capacity"] for r in sup]),
                 np.array([r["bid"] for r in dem]), np.array([r["capacity"] for r in dem]))


def quantity(sup, dem, p):
    s = sum(r["capacity"] for r in sup if r["bid"] <= p + 1e-9)
    d = sum(r["capacity"] for r in dem if r["bid"] >= p - 1e-9)
    return min(s, d)


def marginal_units(sup, dem, p, q, interior=False):
    """All units bidding the clearing price (either side). With equal bids the
    order inside the flat segment is arbitrary, so every one of them is tied.
    interior=True (clearing with neighbours = the model solution) keeps only
    units the model runs between 0.5 % and 99.5 % of their capacity, as the
    setter identification does."""
    out = []
    for side, rows in (("supply", sup), ("demand", dem)):
        for r in rows:
            if abs(r["bid"] - p) > TOL or r["capacity"] <= EPS:
                continue
            if interior:
                full = r.get("cap_full", r["capacity"]) or 0.0
                lf = (r.get("dispatch", 0.0) or 0.0) / full if full > EPS else 0.0
                if not 0.005 < lf < 0.995:
                    continue
            out.append((side, colour_role(r), r["country"], r["capacity"], str(r["plant"])))
    return out


RANK_KEYS = [("nuclear",), ("hardcoal", "oil", "CCGTCCS"), ("other",), ("electrolyzer",), ("EV",),
             ("_gas",), ("biomass",), ("CHP",), ("dam", "reservoir", "reservior"), ("psp",),
             ("battery",), ("V2G",), ("dsr",), ("HPNew", "HPG", "[MWh]"), ("resistive",)]


def rank_of(plant):
    """Tie-break rank of the setter rule (least flexible first, as in
    model/price_setting_tech.PRICE_SETTER_ORDER)."""
    for k, keys in enumerate(RANK_KEYS):
        if any(key in plant for key in keys):
            return k
    return len(RANK_KEYS)


def select(units):
    """Setter rule on the marginal units: supply first (electrolysis counts
    as supply at a fixed hydrogen price), then the least flexible technology.
    Returns (technology, [countries by tied capacity])."""
    if not units:
        return None, []
    sup = [u for u in units if u[0] == "supply" or u[1] == "Electrolyzer"]
    pool = sup or units
    best = min(rank_of(u[4]) for u in pool)
    chosen = [u for u in pool if rank_of(u[4]) == best]
    role, side = chosen[0][1], chosen[0][0]
    caps = {}
    for u in chosen:
        if u[1] == role:
            caps[u[2]] = caps.get(u[2], 0.0) + u[3]
    return (role, side), sorted(caps, key=lambda c: -caps[c])


SIDE_LABEL = {("Pumped hydro", "supply"): "pumped hydro, generating",
              ("Pumped hydro", "demand"): "pumped hydro, pumping",
              ("Battery", "supply"): "battery, discharging", ("Battery", "demand"): "battery, charging",
              ("V2G", "supply"): "vehicle-to-grid, discharging",
              ("V2G", "demand"): "vehicle-to-grid, charging"}


def describe(units):
    key, countries = select(units)
    if key is None:
        return "?"
    role = key[0]
    lab = SIDE_LABEL.get(key) or ("electrolysis" if role == "Electrolyzer"
                                  else S.TECH_LABEL.get(role, role))
    if not lab[:2].isupper():
        lab = lab[0].lower() + lab[1:]
    names = [S.COUNTRY_LABEL[c] for c in countries][:4]
    where = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return f"{lab} in {where}"


def screen(root, run, hours):
    D = load(root, run, hours)
    Dch = D[NODE][0]
    sh = pd.read_csv(root / "output" / run / "border_shapley" / "shapley_hourly.csv").set_index("T")
    rows = []
    for h in hours:
        t = f"t_{h}"
        sup, dem, imp, exp, check = curves(D, t)
        p_model = Dch["price"][t][NODE]
        p_with = clear_rows(sup + imp, dem + exp)
        p_wo = clear_rows(sup, dem)
        q_with, q_wo = quantity(sup + imp, dem + exp, p_with), quantity(sup, dem, p_wo)
        rows.append(dict(
            T=t, day=int(sh.loc[t, "day"]), hour=int(sh.loc[t, "hour"]), p_model=round(p_model, 2),
            p_with=round(p_with, 2), p_without=round(p_wo, 2),
            p_without_shapley=round(sh.loc[t, "price_autarky"], 2),
            max_flow_err=round(max(abs(c["flow_in"] - c["flow_rebuilt"]) for c in check.values()), 1),
            n_imp=len(imp), n_exp=len(exp),
            setter_with=describe(marginal_units(sup + imp, dem + exp, p_with, q_with, interior=True)),
            setter_without=describe(marginal_units(sup, dem, p_wo, q_wo)),
            prices_nb=" ".join(f"{k}{v['price']:.1f}" for k, v in check.items())))
    T = pd.DataFrame(rows)
    T["ok"] = (T["p_with"] - T["p_model"]).abs() < TOL
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 60):
        print(T.to_string(index=False))
    out = root / "output" / run / "paper_fig_cache" / f"screen_t{min(hours)}_t{max(hours)}.csv"
    T.to_csv(out, index=False)
    print("written", out)


# --------------------------------------------------------------------- drawing
def draw(ax, sup, dem, p, q, ylim, xmax, label_gw=0.6, dem_label_gw=1.0):
    """Supply asks as blocks (colour = technology, hatched + country code =
    unit abroad), demand bids as a step line (black = Swiss, dashed in the
    technology colour + country code = unit abroad)."""
    ylo, yhi = ylim
    dy = yhi - ylo
    strip = dy * 0.012
    x = 0.0
    tops = []
    for r in sorted(sup, key=lambda r: r["bid"]):
        w = r["capacity"]
        if w <= EPS:
            continue
        role = colour_role(r)
        col = S.TECH_COLOR.get(role, S.TECH_COLOR["Other"])
        b = float(np.clip(r["bid"], ylo, yhi))
        y0, h = (0.0, b) if b > 0 else (b, -b)
        if h < strip:
            y0, h = 0.0, strip
        foreign = r["country"] != "CH"
        ax.add_patch(Rectangle((x, y0), w, h, fc=col, ec=S.SURFACE if foreign else "none", lw=0,
                               hatch=HATCH.get(r["country"]) if foreign else None, zorder=2))
        tops.append((x, x + w, b, r["country"], col))
        x += w
    xs, ys = [0.0], [tops[0][2] if tops else 0.0]
    for a, b_, y, _, _ in tops:
        xs += [a, b_]
        ys += [y, y]
    ax.plot(xs, ys, color=S.INK, lw=1.0, zorder=3)
    # country code inside the top of each foreign run that is wide enough
    runs = []
    for a, b_, y, c, col in tops:
        if c == "CH":
            continue
        if runs and runs[-1][3] == c and abs(runs[-1][1] - a) < 1e-6:
            runs[-1] = (runs[-1][0], b_, min(runs[-1][2], y), c, runs[-1][4])
        else:
            runs.append((a, b_, y, c, col))
    for a, b_, y, c, col in runs:
        if b_ - a < label_gw:
            continue
        if b_ - a >= 0.9 and y > dy * 0.075:          # inside the top of the block
            ax.text((a + b_) / 2, y - dy * 0.02, c, ha="center", va="top", color=S.text_on(col),
                    fontweight="bold", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.12", fc=col, ec="none"))
        elif not (0 <= p - y < dy * 0.08):             # narrow or low block: above it
            ax.text((a + b_) / 2, max(y, 0) + dy * 0.015, c, ha="center", va="bottom",
                    color=S.INK, fontweight="bold", zorder=6)

    x = 0.0
    prev_y = None
    druns = []
    for r in sorted(dem, key=lambda r: r["bid"], reverse=True):
        w = r["capacity"]
        if w <= EPS:
            continue
        role = colour_role(r)
        y = float(np.clip(r["bid"], ylo, yhi - dy * 0.04))
        foreign = r["country"] != "CH"
        if prev_y is not None:
            ax.plot([x, x], [prev_y, y], color=S.INK, lw=1.2, zorder=4)
        if foreign:
            col = S.TECH_COLOR.get(role, S.TECH_COLOR["Other"])
            ax.plot([x, x + w], [y, y], color=col, lw=4.5, ls=(0, (1.6, 0.8)), solid_capstyle="butt",
                    zorder=5)
            if druns and druns[-1][3] == r["country"] and abs(druns[-1][1] - x) < 1e-6 \
                    and abs(druns[-1][2] - y) < dy * 0.03:
                druns[-1] = (druns[-1][0], x + w, y, r["country"])
            else:
                druns.append((x, x + w, y, r["country"]))
        else:
            ax.plot([x, x + w], [y, y], color=S.INK, lw=2.4, solid_capstyle="butt", zorder=5)
        prev_y = y
        x += w
    for a, b_, y, c in druns:
        near_dot = a - 1.5 <= q <= b_ + 1.5 and abs(y - p) < dy * 0.08
        if b_ - a >= dem_label_gw and not near_dot:
            ax.text((a + b_) / 2, y + dy * 0.02, c, ha="center", va="bottom", color=S.INK, zorder=6)

    ax.plot([0, q], [p, p], color=S.INK, lw=1.0, ls=(0, (1, 2)), zorder=6)
    ax.scatter([q], [p], s=120, color=S.INK, edgecolor=S.SURFACE, linewidth=2, zorder=8)
    ax.set_xlim(0, xmax)
    ax.set_ylim(ylo, yhi)
    ax.set_xlabel("GW")
    ax.set_ylabel(f"Bid ({S.PRICE_UNIT})")
    S.grid(ax, "y")


def legend_handles(roles):
    order = ["Renewables", "Nuclear", "Biomass", "Gas", "Reservoir hydro", "Pumped hydro", "Battery",
             "V2G", "Electrolyzer", "Heat pump", "Resistive heater", "CHP", "Other"]
    return [Patch(fc=S.TECH_COLOR[k], label=S.TECH_LABEL[k]) for k in order if k in roles]


def country_handles(with_neighbours=True):
    h = [Patch(fc=S.MUTED, ec=S.SURFACE, lw=0, hatch=HATCH[c], label=S.COUNTRY_LABEL[c])
         for c in ("FR", "DE", "IT", "AT")] if with_neighbours else []
    h.append(Line2D([], [], color=S.INK, lw=2.4, label="Swiss demand"))
    if with_neighbours:
        h.append(Line2D([], [], color=S.MUTED, lw=4.5, ls=(0, (1.6, 0.8)), label="demand abroad"))
    return h


def plot(root, run, hour_spec, out, formats):
    h = hours_of(hour_spec)[0]
    hours = None
    for d in sorted((root / "output" / run / "paper_fig_cache").glob("t*_t*")):
        a, b = (int(s[1:]) for s in d.name.split("_"))
        if a <= h <= b:
            hours = list(range(a, b + 1))
    if hours is None:
        raise SystemExit("run extract for a range containing this hour first")
    D = load(root, run, hours)
    t = f"t_{h}"
    sup, dem, imp, exp, check = curves(D, t)
    p_model = D[NODE][0]["price"][t][NODE]
    p_with, p_wo = clear_rows(sup + imp, dem + exp), clear_rows(sup, dem)
    q_with, q_wo = quantity(sup + imp, dem + exp, p_with), quantity(sup, dem, p_wo)
    set_with = describe(marginal_units(sup + imp, dem + exp, p_with, q_with, interior=True))
    set_wo = describe(marginal_units(sup, dem, p_wo, q_wo))
    print(f"{t}: model {p_model:.2f}, with {p_with:.2f} ({set_with}), without {p_wo:.2f} ({set_wo})")
    for k, v in check.items():
        print(f"  {k}: price {v['price']:.2f}, flow into CH {v['flow_in']:.0f} MW, rebuilt "
              f"{v['flow_rebuilt']:.0f} MW, NTC in/out {v['ntc_in']:.0f}/{v['ntc_out']:.0f}")

    MW = 1000.0

    def gw(rows):  # MW -> GW, model CHF2017 -> figure currency
        return [dict(r, capacity=r["capacity"] / MW, bid=S.money(r["bid"])) for r in rows]
    sup, dem, imp, exp = gw(sup), gw(dem), gw(imp), gw(exp)
    q_with, q_wo = q_with / MW, q_wo / MW
    p_with, p_wo = S.money(p_with), S.money(p_wo)
    print(f"  in {S.PRICE_UNIT}: with {p_with:.2f}, without {p_wo:.2f}")
    xmax = max(sum(r["capacity"] for r in sup + imp), sum(r["capacity"] for r in dem + exp)) * 1.02
    bids = [r["bid"] for r in sup + imp + dem + exp if r["bid"] < 1000]
    ylo = min(0.0, np.floor(min(bids) / 10) * 10) if bids else 0.0
    ylo = max(ylo, -40.0)
    yhi = max(130.0, np.ceil(max(p_with, p_wo) * 1.5 / 10) * 10)
    roles = {colour_role(r) for r in sup + imp + exp if r["capacity"] > 0.01}
    year = S.year_of(run)
    blocks = pd.DataFrame([dict(r, figure="with") for r in sup + imp + dem + exp])
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    blocks.to_csv(out / f"merit_blocks_{year}_{t}.csv", index=False)

    for name, s, d, p, q, who in (("with", sup + imp, dem + exp, p_with, q_with, set_with),
                                  ("without", sup, dem, p_wo, q_wo, set_wo)):
        fig = plt.figure(figsize=(12.3, 5.6))
        ax = fig.add_axes([0.075, 0.13, 0.62, 0.74])
        draw(ax, s, d, p, q, (ylo, yhi), xmax)
        ax.annotate(f"{p:.1f} {S.PRICE_UNIT}\nset by {who}", xy=(q, p), xytext=(0.985, 0.955),
                    textcoords="axes fraction", ha="right", va="top", color=S.INK, zorder=9,
                    arrowprops=dict(arrowstyle="-", color=S.INK, lw=1.0, shrinkA=4, shrinkB=7))
        fig.legend(handles=legend_handles(roles), loc="center left", bbox_to_anchor=(0.71, 0.5),
                   handlelength=1.3, labelspacing=0.35)
        fig.legend(handles=country_handles(name == "with"), loc="upper left", bbox_to_anchor=(0.06, 1.0), ncol=6,
                   handlelength=1.4, columnspacing=1.0, handletextpad=0.5)
        S.save(fig, out, f"fig_merit_{name}_neighbours_{year}_{t}", formats)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["extract", "screen", "plot"])
    ap.add_argument("run")
    ap.add_argument("--hours", default="t_1177:t_1344")
    ap.add_argument("--hour", default=None)
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="output/paper_figures")
    ap.add_argument("--budget", type=float, default=140)
    ap.add_argument("--formats", default="png,pdf")
    a = ap.parse_args()
    root = Path(a.root)
    if a.action == "extract":
        extract(root, a.run, hours_of(a.hours), a.budget)
    elif a.action == "screen":
        screen(root, a.run, hours_of(a.hours))
    else:
        plot(root, a.run, a.hour, a.out, a.formats.split(","))


if __name__ == "__main__":
    main()
