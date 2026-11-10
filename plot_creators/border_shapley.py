"""Decompose the hourly Swiss electricity price into per-border trade
contributions (Shapley decomposition over the merit order) for a whole run.

For every hour the script rebuilds the node's own merit order (all Swiss
supply asks and demand bids, same formulas as plot_creators/merit_order_plot.py)
plus one import block (supply) and one export block (demand) per border:
width = NTC of the hour, price = the neighbour's clearing price. It then clears
the Swiss market for EVERY subset of open borders (2^n coalitions) and
attributes the difference between the autarky price and the full-trade price
to the borders with the Shapley value:

    phi_i = sum over S not containing i of  |S|!(n-|S|-1)!/n!  * [p(S+i) - p(S)]

Properties used downstream: the phi_i sum exactly to p(all) - p(autarky) in
every hour (efficiency) and are additive across hours, so seasonal, monthly
and hour-of-day averages and the daily peak/off-peak SPREAD decomposition are
plain averages/differences of the hourly values.

Approximations (state in the paper): all bids are held at their equilibrium
values (short-run, water values fixed) and the neighbour's price is taken as
given for the whole NTC width (price-taker approximation for a small country).
The full-coalition price is compared with the model's dual price as a
consistency check (column price_gap).

Outputs (output/<scenario>/border_shapley/):
    shapley_hourly.csv          per hour: model price, p_all, p_autarky, phi per border,
                                NTC + flow per border, price_gap, month, hour, season
    shapley_monthly.csv         mean phi per border and month (+ total, mean price)
    shapley_hour_of_day.csv     mean phi per border, season and hour of day
    shapley_spread_daily.csv    daily peak-minus-trough price and its border decomposition
    shapley_summary.csv         annual means and hours in which each border matters
    figures: monthly stacked bars, 24 h profiles per season, spread decomposition (HTML,
             PNG + SVG if kaleido is installed)
    merit_blocks_<t>.csv, merit_with_trade_<t>.*, merit_without_trade_<t>.*
                                (--merit-hours): block table and merit-order figure pair
                                of single hours, same axes and neighbour colours

Neighbour colours are shared with merit_order_plot.py (NEIGHBOUR_COLORS).

Usage (from the repo root):
    python plot_creators/border_shapley.py <scenario> <sub_scenario> [--node CH00]
        [--hours t_6553:t_6600] [--no-figures] [--merit-hours t_2143,t_1209]
        [--skip-decomposition] [--poster] [--font-scale 2.0] [--period t_1177:t_1344]
        [--waterfall t_2143] [--compare-with <scenario2>]
"""

import argparse
import itertools
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from plot_creators.merit_order_plot import (  # noqa: E402
    EPS, GRID, INK, INK2, POSTER_FONT_SCALE, POSTER_SIZE, VOLL_FALLBACK, bid_demand,
    bid_supply, clear, demand_cap, figure_pair, kv, neighbour_color, node_label, role_tier,
    sub_only, trade_rows, wide_map, write_captions, write_image_variants,
)

CHUNK = 400_000
SEASON_OF_MONTH = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring",
                   5: "spring", 6: "summer", 7: "summer", 8: "summer",
                   9: "autumn", 10: "autumn", 11: "autumn"}
DAYS_BEFORE_MONTH = np.cumsum([0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]) # type: ignore
    p.add_argument("scenario")
    p.add_argument("sub_scenario")
    p.add_argument("--node", default="CH00")
    p.add_argument("--hours", default=None,
                   help="optional range t_a:t_b (inclusive, in model hour ids) "
                        "to restrict the computation; default all hours of the run")
    p.add_argument("--no-figures", action="store_true",
                   help="skip the monthly / hour-of-day / spread figures")
    p.add_argument("--merit-hours", default=None,
                   help="comma-separated hours (t_2143,t_1209) for which a merit-order "
                        "figure pair (with trade / without trade) and the block table "
                        "are written to the border_shapley folder")
    p.add_argument("--skip-decomposition", action="store_true",
                   help="do not recompute the hourly decomposition (only --merit-hours "
                        "figures; the summary figures are then rebuilt from the CSVs)")
    p.add_argument("--poster", action="store_true",
                   help="poster styling of all figures: larger fonts and line widths")
    p.add_argument("--period", default=None, metavar="t_a:t_b",
                   help="hourly decomposition figure of one period, e.g. one week "
                        "t_1177:t_1344 (price with / without trade + stacked border "
                        "contributions); read from shapley_hourly.csv, no run needed")
    p.add_argument("--waterfall", default=None, metavar="t_x",
                   help="waterfall figure of ONE hour: autarky price -> border "
                        "contributions -> price with trade (from shapley_hourly.csv)")
    p.add_argument("--font-scale", type=float, default=None,
                   help=f"font / line-width multiplier (overrides --poster's {POSTER_FONT_SCALE})")
    p.add_argument("--compare-with", default=None, metavar="SCENARIO",
                   help="second scenario (with a finished border_shapley folder) for a "
                        "side-by-side monthly figure, labelled by run_year of both runs")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Loading — every hourly file is read ONCE, filtered to the node, and turned
# into {hour: {key: value}} dictionaries.
# ---------------------------------------------------------------------------
def read_filtered(path, sub, keep_col=None, keep_set=None, t_col="T"):
    """Read a large hourly CSV in chunks, keep rows of the sub-scenario (and
    optionally of keys in keep_set), return the concatenated DataFrame."""
    parts = []
    for chunk in pd.read_csv(path, chunksize=CHUNK):
        scol = "Scenarios" if "Scenarios" in chunk.columns else (
            "Scenario" if "Scenario" in chunk.columns else None)
        if scol is not None:
            chunk = chunk.loc[chunk[scol] == sub]
        if keep_col is not None and keep_set is not None:
            chunk = chunk.loc[chunk[keep_col].isin(keep_set)]
        if len(chunk):
            parts.append(chunk)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def by_hour(df, key_col, t_col="T", val_col="value"):
    """DataFrame -> {t: {key: value}}"""
    out = {}
    if df.empty:
        return out
    for t, grp in df.groupby(t_col, sort=False):
        out[t] = dict(zip(grp[key_col], grp[val_col]))
    return out


def sums_by_hour(df, t_col="T", val_col="value"):
    if df.empty:
        return {}
    return df.groupby(t_col)[val_col].sum().to_dict()


def load_run(folder: Path, sub: str, node: str):
    print("Loading static data ...")
    D = {}
    sf = kv(pd.read_csv(folder / "constraint_scaling.csv"), "ConstraintNames")
    D["sf"] = sf
    D["weight"] = kv(sub_only(pd.read_csv(folder / "weight_in_objective_fcn.csv"), sub),
                     "Scenarios")[sub]
    w = D["weight"]

    plant_node = wide_map(pd.read_csv(folder / "Map_node_plant.csv"))
    D["plant_node"] = plant_node
    D["plant_tech"] = kv(pd.read_csv(folder / "Map_plant_tech.csv"), "P")
    node_plants = {p for p, n in plant_node.items() if n == node}
    consumer_node = wide_map(pd.read_csv(folder / "Map_node_consumer.csv"))
    node_consumers = {c for c, n in consumer_node.items() if n == node}

    D["gen_max"] = kv(sub_only(pd.read_csv(folder / "gen_max.csv"), sub), "P_gen")
    D["pmp_max"] = kv(sub_only(pd.read_csv(folder / "pmp_max.csv"), sub), "P_pumping")
    D["op_slp"] = kv(sub_only(pd.read_csv(folder / "operation_slp.csv"), sub), "P_gen")
    D["op_slpTh"] = kv(sub_only(pd.read_csv(folder / "operation_slpTh.csv"), sub),
                       "PDH_costExclusivelyOnThermalSide")
    D["eff_out"] = kv(sub_only(pd.read_csv(folder / "storage_charge_eff_out.csv"), sub),
                      "storage_charge_eff_out_index_0")
    D["eff_in"] = kv(sub_only(pd.read_csv(folder / "storage_charge_eff_in.csv"), sub),
                     "storage_charge_eff_in_index_0")
    D["energy_max"] = kv(sub_only(pd.read_csv(folder / "gen_energy_max.csv"), sub), "P_energymax")
    flex = sub_only(pd.read_csv(folder / "Data_plant_flex_d_within_window.csv"), sub)
    D["flex_max_demand"] = kv(flex, "P_flex_d_within_window", "max_demand")
    mu = sub_only(pd.read_csv(folder / "energy_limit_dual.csv"), sub)
    D["mu_v"] = {p: abs(v) * sf["energy_limit"] / w
                 for p, v in zip(mu["P_energylim"], mu["value"]) if v}
    h2 = pd.read_csv(folder / "consume_tot_limit_dual.csv")
    # abs(): the consume_tot_limit dual comes out NEGATIVE when the must-serve energy is 0 (h2_fixed_price runs, 2026-10-14) and positive otherwise; the hydrogen value is its magnitude
    D["h2_value"] = {name.split("_")[3]: abs(v) * sf["consume_tot_limit"] / w
                     for name, v in zip(h2["constraint"], h2["value"]) if pd.notna(v)}
    D["nodeDH"] = kv(pd.read_csv(folder / "Map_plantDH_nodeDH.csv"), "PDH")
    dhd = sub_only(pd.read_csv(folder / "PlantDH_data_remaining.csv"), sub)
    piv = dhd.pivot_table(index="PlantDH", columns="Feature", values="value", aggfunc="first")
    is_chp = piv.get("CHPDH", pd.Series(dtype=object)).astype(str) == "True"
    D["chp_p2h"] = {p: float(v) for p, v in piv.loc[is_chp, "power_to_heat_ratio"].items()
                    if pd.notna(v)}
    eff = piv.loc[~is_chp, "efficiency"] if "efficiency" in piv else pd.Series(dtype=object)
    D["consumer_eff"] = {p: float(v) for p, v in eff.items() if pd.notna(v)}
    D["ba_cap"] = kv(sub_only(pd.read_csv(folder / "BA_max_heating_capacity.csv"), sub),
                     "BA_names")
    llc = kv(sub_only(pd.read_csv(folder / "lostload_cost_per_step.csv"), sub), "lostLoad_step")
    D["voll"] = llc.get(0, VOLL_FALLBACK)
    D["ll_cost"] = llc

    # borders: lines with exactly one endpoint at the node
    line_start = wide_map(pd.read_csv(folder / "Map_node_exportinglineATC.csv"))
    line_end = wide_map(pd.read_csv(folder / "Map_node_importinglineATC.csv"))
    border_lines = {}
    for line in set(line_start) | set(line_end):
        s, e = line_start.get(line), line_end.get(line)
        if s is None or e is None or (s == node) == (e == node):
            continue
        border_lines[line] = (s, e)
    D["border_lines"] = border_lines
    D["neighbours"] = sorted({e if s == node else s for s, e in border_lines.values()})
    print(f"  node {node}: {len(node_plants)} plants, {len(node_consumers)} consumers, "
          f"borders {D['neighbours']}")

    print("Loading hourly data (filtered to the node) ...")
    elp = read_filtered(folder / "energy_balance_dual.csv", sub)
    elp["value"] = elp["value"] * sf["energy_balance"] / w
    D["price"] = by_hour(elp, "Node")
    D["hours"] = sorted(D["price"], key=lambda t: int(t.split("_")[1]))

    D["gen"] = by_hour(read_filtered(folder / "gen.csv", sub, "P_gen", node_plants), "P_gen")
    D["charge"] = by_hour(read_filtered(folder / "storage_charge.csv", sub, "P_pumping",
                                        node_plants), "P_pumping")
    D["avail"] = by_hour(read_filtered(folder / "avail_plant.csv", sub, "avail_plant_index_0",
                                       node_plants), "avail_plant_index_0")
    v2g = read_filtered(folder / "V2G_charging_power_rate.csv", sub)
    D["v2g_cap"] = by_hour(v2g, "P_evV2G")
    # state of charge (previous hour) and inflow: storage capacities are
    # energy-limited (Geis et al. Eqs. 30-31) -- a store can only offer what it
    # holds and only absorb what fits
    D["soc"] = by_hour(read_filtered(folder / "soc.csv", sub, "P_storage", node_plants),
                       "P_storage")
    inflow_path = folder / "inflow.csv"
    D["inflow"] = by_hour(read_filtered(inflow_path, sub, "P_inflow", node_plants),
                          "P_inflow") if inflow_path.exists() else {}
    wv = read_filtered(folder / "storage_soc_dual.csv", sub, "P_storage", node_plants)
    wv["value"] = -wv["value"] * sf["storage_soc"] / w
    D["watervalue"] = by_hour(wv, "P_storage")
    nu = read_filtered(folder / "dsr_daily_balance_dual.csv", sub, "P_dsr", node_plants)
    D["dsr_nu"] = {}
    for p, dd, v in zip(nu.get("P_dsr", []), nu.get("Days", []), nu.get("value", [])):
        if v:
            D["dsr_nu"].setdefault(dd, {})[p] = -v * sf["dsr_daily_balance"] / w
    sh = read_filtered(folder / "energy_shift_limit_dsr_daily_dual.csv", sub, "P_dsr", node_plants)
    D["dsr_shift"] = {}
    for p, dd, v in zip(sh.get("P_dsr", []), sh.get("Days", []), sh.get("value", [])):
        if v:
            D["dsr_shift"].setdefault(dd, {})[p] = -v * sf["energy_shift_limit_dsr_daily"] / w

    hp = read_filtered(folder / "energy_balancethermal_dual.csv", sub)
    hp["value"] = hp["value"] * sf["energy_balancethermal"] / w
    heat = by_hour(hp, "NodeDH")
    de = read_filtered(folder / "inflexble_demandTh_share_dual.csv", sub)
    for t, grp in de.groupby("T", sort=False):
        for n, v in zip(grp["NodeDH"], grp["value"]):
            if v:
                heat.setdefault(t, {})[n] = heat.get(t, {}).get(n, 0.0) \
                    + v * sf["inflexble_demandTh_share"] / w
    D["heat_value_dh"] = heat
    bh = read_filtered(folder / "building_heat_demand_dual.csv", sub)
    bh["value"] = -bh["value"] * sf["building_heat_demand"] / w
    D["ba_heat_value"] = by_hour(bh, "BA_names")
    D["ba_cop"] = by_hour(read_filtered(folder / "COP.csv", sub), "BA_names")

    # fixed blocks
    inf = read_filtered(folder / "infeed.csv", sub, "Consumer_with_infeed", node_consumers)
    D["infeed"] = sums_by_hour(inf)
    cur = read_filtered(folder / "curtailment.csv", sub, "Consumer_with_infeed", node_consumers)
    D["curtail"] = sums_by_hour(cur)
    bio = read_filtered(folder / "Biomass_inflexible_generation.csv", sub, "Node", {node})
    D["bio_fixed"] = sums_by_hour(bio)
    dem = read_filtered(folder / "demand.csv", sub, "Consumer", node_consumers)
    D["demand_fixed"] = sums_by_hour(dem)
    for name in ("HP_inflexible_demand", "EV_inflexible_demand",
                 "Electrolyzer_inflexible_demand", "DH_inflexible_demand"):
        df = read_filtered(folder / f"{name}.csv", sub, "Node", {node})
        for t, v in sums_by_hour(df).items():
            D["demand_fixed"][t] = D["demand_fixed"].get(t, 0.0) + v
    ll = read_filtered(folder / "lostload.csv", sub, "Consumer", node_consumers)
    D["lostload"] = {}
    if not ll.empty:
        for (t, step), v in ll.groupby(["T", "lostLoad_step"])["value"].sum().items(): # type: ignore
            if v > EPS:
                D["lostload"].setdefault(t, {})[step] = v

    # trade
    lines = set(border_lines)
    D["atc_exp"] = by_hour(read_filtered(folder / "ATC_exportlimit.csv", sub, "lineATC", lines),
                           "lineATC")
    D["atc_imp"] = by_hour(read_filtered(folder / "ATC_importlimit.csv", sub, "lineATC", lines),
                           "lineATC")
    D["flow"] = by_hour(read_filtered(folder / "Export.csv", sub, "lineATC", lines), "lineATC")
    print(f"  {len(D['hours'])} hours loaded.")
    return D, node_plants


# ---------------------------------------------------------------------------
# Per-hour merit order (node view) + trade blocks
# ---------------------------------------------------------------------------
def ingredients_at(D, t):
    day = (int(t.split("_")[1]) - 1) // 24 + 1
    ing = {
        "weight": D["weight"], "price": D["price"].get(t, {}),
        "plant_node": D["plant_node"], "plant_tech": D["plant_tech"],
        "gen": D["gen"].get(t, {}), "charge": D["charge"].get(t, {}),
        "gen_max": D["gen_max"], "pmp_max": D["pmp_max"], "avail": D["avail"].get(t, {}),
        "v2g_cap": D["v2g_cap"].get(t, {}), "flex_max_demand": D["flex_max_demand"],
        "op_slp": D["op_slp"], "op_slpTh": D["op_slpTh"], "eff_out": D["eff_out"],
        "eff_in": D["eff_in"],
        "watervalue": dict(D["watervalue"].get(t, {})),
        "dsr_shift": D["dsr_shift"].get(day, {}),
        "mu_v": D["mu_v"], "h2_value": D["h2_value"],
        "heat_value_dh": D["heat_value_dh"].get(t, {}), "nodeDH": D["nodeDH"],
        "chp_p2h": D["chp_p2h"], "consumer_eff": D["consumer_eff"],
        "ba_heat_value": D["ba_heat_value"].get(t, {}), "ba_cop": D["ba_cop"].get(t, {}),
        "ba_cap": D["ba_cap"],
    }
    ing["watervalue"].update(D["dsr_nu"].get(day, {}))
    return ing


def domestic_rows(D, node_plants, t):
    """Block table of the node at t WITHOUT trade: one row per supply ask and
    demand bid (side, plant, role, tier, bid, capacity, dispatch + the bid
    components). Same schema as merit_order_plot.build_merit_order, but with
    the state-of-charge limits on storage capacities."""
    ing = ingredients_at(D, t)
    h = int(t.split("_")[1])
    t_prev = f"t_{h - 1 if h > 1 else 8760}"
    soc_prev = D["soc"].get(t_prev, {})
    inflow_t = D["inflow"].get(t, {})
    rows = []
    for p, dispatch in ing["gen"].items():
        if p not in node_plants:
            continue
        cap = (ing["gen_max"].get(p, 0.0) or 0.0) * ing["avail"].get(p, 1.0)
        if p in soc_prev:  # energy-limited store: cannot deliver more than it holds
            energy = max(soc_prev[p] + inflow_t.get(p, 0.0), 0.0)
            cap = min(cap, energy * (ing["eff_out"].get(p, 1.0) or 1.0))
        if cap <= EPS:
            continue
        bid, parts = bid_supply(p, ing)
        role, tier = role_tier(p)
        rows.append(dict(side="supply", plant=p, role=role, tier=tier, bid=bid,
                         capacity=cap, dispatch=dispatch or 0.0, **parts))
    unpriced_fixed = 0.0
    for p in ing["charge"]:
        if p not in node_plants:
            continue
        priced = (p in ing["watervalue"] or p in ing["ba_cap"] or p in ing["consumer_eff"]
                  or "electrolyzer" in p or p in ing["dsr_shift"])
        if not priced:
            # flexible consumer whose willingness is not reconstructable (EV_flex:
            # its dual lives in the weekly EV constraints, not exported) -> carry
            # the DISPATCHED charging as must-serve demand (exact for the full
            # coalition, approximation for the counterfactual coalitions)
            unpriced_fixed += ing["charge"].get(p, 0.0) or 0.0
            continue
        cap = demand_cap(p, ing)
        e_max = D["energy_max"].get(p, 0.0) or 0.0
        if p in soc_prev and e_max > 1.0:  # cannot absorb more than fits
            # (V2G/EV energy lives in separate params -> e_max ~ 0 -> skipped)
            headroom = max(e_max - soc_prev[p], 0.0)
            cap = min(cap, headroom / (D["eff_in"].get(p, 1.0) or 1.0))
        if cap <= EPS:
            continue
        bid, parts = bid_demand(p, ing)
        role, tier = role_tier(p)
        rows.append(dict(side="demand", plant=p, role=role, tier=tier, bid=bid,
                         capacity=cap, dispatch=ing["charge"].get(p, 0.0) or 0.0, **parts))
    if unpriced_fixed > EPS:
        rows.append(dict(side="demand", plant="Flexible EV charging (dispatched, unpriced)",
                         role="inelastic demand", tier="inelastic demand", bid=D["voll"],
                         capacity=unpriced_fixed, dispatch=unpriced_fixed))
    # fixed blocks
    res = D["infeed"].get(t, 0.0)
    if res > EPS:
        rows.append(dict(side="supply", plant="Renewables (node)", role="renewables",
                         tier="renewables", bid=0.0, capacity=res,
                         dispatch=res - D["curtail"].get(t, 0.0)))
    bio = D["bio_fixed"].get(t, 0.0)
    if bio > EPS:
        rows.append(dict(side="supply", plant="Biomass must-run (node)", role="renewables",
                         tier="renewables", bid=0.0, capacity=bio, dispatch=bio))
    fixed = D["demand_fixed"].get(t, 0.0)
    rows.append(dict(side="demand", plant="Inelastic demand (node)", role="inelastic demand",
                     tier="inelastic demand", bid=D["voll"], capacity=fixed, dispatch=fixed))
    for step, v in D["lostload"].get(t, {}).items():
        rows.append(dict(side="supply", plant=f"Lost load (step {step})", role="lost load",
                         tier="lost load", bid=D["ll_cost"].get(step, D["voll"]),
                         capacity=v, dispatch=v))
    return rows


def domestic_blocks(D, node_plants, t):
    """(supply bids, supply caps, demand bids, demand caps) of the node at t,
    excluding trade."""
    rows = domestic_rows(D, node_plants, t)
    s = [(r["bid"], r["capacity"]) for r in rows if r["side"] == "supply"]
    d = [(r["bid"], r["capacity"]) for r in rows if r["side"] == "demand"]
    s_bid, s_cap = (np.array([v[0] for v in s]), np.array([v[1] for v in s]))
    d_bid, d_cap = (np.array([v[0] for v in d]), np.array([v[1] for v in d]))
    return s_bid, s_cap, d_bid, d_cap


def merit_order_table(D, node_plants, node, t):
    """Full block table of hour t (domestic rows + import/export block per
    neighbour) as a DataFrame in the merit_order_plot schema."""
    rows = domestic_rows(D, node_plants, t)
    for nb, (ci, fi, co, fo, pn) in sorted(trade_blocks_at(D, node, t).items()):
        rs, rd = trade_rows(nb, ci, fi, co, fo, pn)
        rows += [dict(side="supply", **r) for r in rs]
        rows += [dict(side="demand", **r) for r in rd]
    return pd.DataFrame(rows)


def trade_blocks_at(D, node, t):
    """{neighbour: (cap_in, flow_in, cap_out, flow_out, price_nb)}"""
    prices = D["price"].get(t, {})
    ae, ai, fl = D["atc_exp"].get(t, {}), D["atc_imp"].get(t, {}), D["flow"].get(t, {})
    agg = {}
    for line, (s, e) in D["border_lines"].items():
        nb = e if s == node else s
        f = fl.get(line, 0.0) or 0.0
        if s == node:
            cap_out, cap_in = ae.get(line, 0.0) or 0.0, ai.get(line, 0.0) or 0.0
            f_out, f_in = max(f, 0.0), max(-f, 0.0)
        else:
            cap_in, cap_out = ae.get(line, 0.0) or 0.0, ai.get(line, 0.0) or 0.0
            f_in, f_out = max(f, 0.0), max(-f, 0.0)
        a = agg.setdefault(nb, [0.0, 0.0, 0.0, 0.0])
        a[0] += cap_in; a[1] += f_in; a[2] += cap_out; a[3] += f_out
    out = {}
    for nb, (ci, fi, co, fo) in agg.items():
        if nb in prices:
            out[nb] = (ci, fi, co, fo, prices[nb])
    return out


# ---------------------------------------------------------------------------
# Market clearing and Shapley
# ---------------------------------------------------------------------------
# clear() (market clearing of two step curves) is shared with merit_order_plot.py


def shapley_hour(base, trade, neighbours):
    """Prices for all coalitions + Shapley values per neighbour."""
    s_bid, s_cap, d_bid, d_cap = base
    n = len(neighbours)
    prices = {}
    for r in range(n + 1):
        for S in itertools.combinations(range(n), r):
            sb, sc, dbb, dcc = [s_bid], [s_cap], [d_bid], [d_cap]
            for i in S:
                ci, _, co, _, pn = trade[neighbours[i]]
                if ci > EPS:
                    sb.append(np.array([pn])); sc.append(np.array([ci]))
                if co > EPS:
                    dbb.append(np.array([pn])); dcc.append(np.array([co]))
            prices[S] = clear(np.concatenate(sb), np.concatenate(sc),
                              np.concatenate(dbb), np.concatenate(dcc))
    phi = {}
    for i in range(n):
        others = [j for j in range(n) if j != i]
        val = 0.0
        for r in range(n):
            wgt = math.factorial(r) * math.factorial(n - r - 1) / math.factorial(n)
            for S in itertools.combinations(others, r):
                S_i = tuple(sorted(S + (i,)))
                val += wgt * (prices[S_i] - prices[tuple(S)])
        phi[neighbours[i]] = val
    full = tuple(range(n))
    return prices[()], prices[full], phi


# ---------------------------------------------------------------------------
# Calendar helpers (t_1 = 1 January 00:00 of a 365-day year)
# ---------------------------------------------------------------------------
def calendar_of(t):
    h = int(t.split("_")[1]) - 1
    day = h // 24
    month = int(np.searchsorted(DAYS_BEFORE_MONTH, day, side="right"))
    return month, h % 24, day + 1



# ---------------------------------------------------------------------------
# Aggregation (monthly, hour-of-day by season, daily spread, summary)
# ---------------------------------------------------------------------------
def aggregate(hourly, neighbours):
    phi_cols = [f"phi_{nb}" for nb in neighbours]
    monthly = (hourly.groupby("month")[phi_cols + ["trade_effect", "price_model",
                                                    "price_autarky"]]
               .mean().reset_index())
    hod = (hourly.groupby(["season", "hour"])[phi_cols + ["trade_effect", "price_model"]]
           .mean().reset_index())
    # daily spread: peak hour minus trough hour of the MODEL price, decomposed
    # with the same hours' Shapley values (additivity of the Shapley value)
    sp_rows = []
    for day, g in hourly.groupby("day"):
        hi, lo = g["price_model"].idxmax(), g["price_model"].idxmin()
        r = dict(day=day, month=int(g["month"].iloc[0]),
                 spread_model=g.loc[hi, "price_model"] - g.loc[lo, "price_model"],
                 spread_autarky=g.loc[hi, "price_autarky"] - g.loc[lo, "price_autarky"])
        for nb in neighbours:
            r[f"spread_phi_{nb}"] = g.loc[hi, f"phi_{nb}"] - g.loc[lo, f"phi_{nb}"]
        sp_rows.append(r)
    spread = pd.DataFrame(sp_rows)
    summary = {"hours": len(hourly), "mean_price_model": hourly["price_model"].mean(),
               "mean_price_autarky": hourly["price_autarky"].mean(),
               "mean_trade_effect": hourly["trade_effect"].mean(),
               "max_abs_price_gap": hourly["price_gap"].abs().max()}
    for nb in neighbours:
        summary[f"mean_phi_{nb}"] = hourly[f"phi_{nb}"].mean()
        summary[f"hours_phi_{nb}_nonzero"] = int((hourly[f"phi_{nb}"].abs() > 0.01).sum())
        summary[f"mean_abs_phi_{nb}"] = hourly[f"phi_{nb}"].abs().mean()
    return monthly, hod, spread, summary

# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def save_figure(fig, out_dir, name, width=1300, height=720, scale=2):
    """HTML always; title-less PNG + SVG when kaleido is available."""
    fig.write_html(out_dir / f"{name}.html")
    write_image_variants(fig, str(out_dir / f"{name}.png"), width=width, height=height,
                         scale=scale)


def _fs(poster, font_scale):
    return font_scale or (POSTER_FONT_SCALE if poster else 1.0)


def make_figures(hourly, monthly, hod, spread, neighbours, out_dir, tag, poster=False,
                 font_scale=None):
    """Summary figures of the decomposition. Neighbour colours come from
    merit_order_plot.NEIGHBOUR_COLORS, so they match the merit-order figures."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    fs = _fs(poster, font_scale)
    colors = {nb: neighbour_color(nb, i) for i, nb in enumerate(neighbours)}
    labels = {nb: node_label(nb) for nb in neighbours}
    SURF = "#ffffff"
    lw = 2.2 * fs
    base_layout = dict(plot_bgcolor=SURF, paper_bgcolor=SURF,
                       font=dict(size=15 * fs, color=INK2),
                       legend=dict(orientation="h", x=0, y=1.02, xanchor="left",
                                   yanchor="bottom", font=dict(size=14 * fs)),
                       title_font=dict(size=20), margin=dict(t=80 * fs))
    months = monthly["month"].map(lambda m: MONTH_ABBR[int(m) - 1])

    # 1. monthly stacked bars of border contributions + total
    fig = go.Figure()
    for nb in neighbours:
        fig.add_trace(go.Bar(x=months, y=monthly[f"phi_{nb}"], name=labels[nb],
                             marker_color=colors[nb]))
    fig.add_trace(go.Scatter(x=months, y=monthly["trade_effect"], mode="lines+markers",
                             name="all borders", line=dict(color=INK, width=lw),
                             marker=dict(size=7 * fs)))
    fig.add_hline(y=0, line_color=INK2, line_width=1)
    fig.update_layout(barmode="relative",
                      title=f"Trade contribution to the {tag} price by month",
                      xaxis=dict(title=None if poster else "month", gridcolor=GRID),
                      yaxis=dict(title="CHF/MWh" if poster else
                                 "contribution to the price [CHF/MWh]",
                                 gridcolor=GRID, automargin=True),
                      **base_layout)
    save_figure(fig, out_dir, "fig_monthly_contributions", width=1400, height=800)

    # 2. 24 h profiles per season
    seasons = [s for s in ["winter", "spring", "summer", "autumn"] if s in set(hod["season"])]
    fig = make_subplots(rows=1, cols=len(seasons), shared_yaxes=True, subplot_titles=seasons,
                        horizontal_spacing=0.03)
    for ci, s in enumerate(seasons, start=1):
        d = hod.loc[hod["season"] == s].sort_values("hour")
        for nb in neighbours:
            fig.add_trace(go.Scatter(x=d["hour"], y=d[f"phi_{nb}"], mode="lines", name=labels[nb],
                                     line=dict(color=colors[nb], width=lw), showlegend=(ci == 1)),
                          row=1, col=ci)
        fig.add_trace(go.Scatter(x=d["hour"], y=d["trade_effect"], mode="lines", name="all borders",
                                 line=dict(color=INK, width=lw, dash="dash"), showlegend=(ci == 1)),
                      row=1, col=ci)
        fig.add_hline(y=0, line_color=INK2, line_width=1, row=1, col=ci)
        fig.update_xaxes(title_text="hour of day", dtick=6, gridcolor=GRID, row=1, col=ci)
    fig.update_yaxes(title_text="contribution to the price [CHF/MWh]", gridcolor=GRID, row=1, col=1)
    fig.update_annotations(font=dict(size=16 * fs))
    fig.update_layout(title=f"Average trade contribution to the {tag} price over the day, by season",
                      **{**base_layout,
                         "legend": dict(orientation="h", x=0, y=1.12, xanchor="left",
                                        yanchor="bottom", font=dict(size=14 * fs)),
                         "margin": dict(t=110 * fs)})
    save_figure(fig, out_dir, "fig_hour_of_day_by_season", width=1600)

    # 3. daily spread decomposition by month
    sp = spread.groupby("month").mean(numeric_only=True).reset_index()
    sp_months = sp["month"].map(lambda m: MONTH_ABBR[int(m) - 1])
    fig = go.Figure()
    for nb in neighbours:
        fig.add_trace(go.Bar(x=sp_months, y=sp[f"spread_phi_{nb}"], name=labels[nb],
                             marker_color=colors[nb]))
    fig.add_trace(go.Scatter(x=sp_months, y=sp["spread_autarky"], mode="lines+markers",
                             name="daily spread without trade",
                             line=dict(color=INK2, width=lw, dash="dot"), marker=dict(size=7 * fs)))
    fig.add_trace(go.Scatter(x=sp_months, y=sp["spread_model"], mode="lines+markers",
                             name="daily spread with trade", line=dict(color=INK, width=lw),
                             marker=dict(size=7 * fs)))
    fig.update_layout(barmode="relative",
                      title=f"Daily peak-minus-trough spread of the {tag} price: contribution of each border",
                      xaxis=dict(title="month", gridcolor=GRID),
                      yaxis=dict(title="CHF/MWh", gridcolor=GRID),
                      **base_layout)
    save_figure(fig, out_dir, "fig_daily_spread_decomposition")


def year_comparison_figure(monthly_by_label, neighbours, out_dir, name="fig_monthly_contributions_compare",
                           poster=False, font_scale=None):
    """Monthly border contributions of several runs side by side (e.g. 2035 |
    2050), shared y-axis, same colours. monthly_by_label: {label: monthly df}."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    fs = _fs(poster, font_scale)
    colors = {nb: neighbour_color(nb, i) for i, nb in enumerate(neighbours)}
    labels = list(monthly_by_label)
    fig = make_subplots(rows=1, cols=len(labels), shared_yaxes=True, subplot_titles=labels,
                        horizontal_spacing=0.03)
    for ci, lab in enumerate(labels, start=1):
        m = monthly_by_label[lab]
        months = m["month"].map(lambda k: MONTH_ABBR[int(k) - 1])
        for nb in neighbours:
            fig.add_trace(go.Bar(x=months, y=m[f"phi_{nb}"], name=node_label(nb),
                                 marker_color=colors[nb], showlegend=(ci == 1)), row=1, col=ci)
        fig.add_trace(go.Scatter(x=months, y=m["trade_effect"], mode="lines+markers",
                                 name="all borders", line=dict(color="#0b0b0b", width=2.2 * fs),
                                 marker=dict(size=7 * fs), showlegend=(ci == 1)), row=1, col=ci)
        fig.add_hline(y=0, line_color="#52514e", line_width=1, row=1, col=ci)
        fig.update_xaxes(gridcolor="#e0e0e0", row=1, col=ci)
    fig.update_yaxes(title_text="contribution to the price [CHF/MWh]", gridcolor="#e0e0e0",
                     row=1, col=1)
    fig.update_annotations(font=dict(size=16 * fs))
    fig.update_layout(barmode="relative", plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                      font=dict(size=15 * fs, color="#52514e"),
                      legend=dict(orientation="h", x=0, y=1.08, xanchor="left", yanchor="bottom",
                                  font=dict(size=14 * fs)),
                      margin=dict(t=90 * fs),
                      title="Trade contribution to the price by month")
    save_figure(fig, out_dir, name, width=1800, height=720)
    return fig


def merit_order_figures(D, node_plants, node, t, out_dir, scenario, poster=False, font_scale=None):
    """Merit-order figure pair of hour t: with the neighbours' import/export
    blocks and without them (autarky), same axes, same colours. Also writes
    the block table (merit_blocks_<t>.csv, re-renderable with
    merit_order_plot.py --from-blocks). Returns (p_all, p_autarky)."""
    df = merit_order_table(D, node_plants, node, t)
    df.to_csv(out_dir / f"merit_blocks_{t}.csv", index=False)
    fig_all, fig_aut, p_all, p_aut = figure_pair(df, t, node, scenario, D["voll"], poster,
                                                 font_scale)
    p_model = D["price"][t].get(node, np.nan)
    size = POSTER_SIZE if poster else dict(width=1300, height=780)
    save_figure(fig_all, out_dir, f"merit_with_trade_{t}", **size)
    save_figure(fig_aut, out_dir, f"merit_without_trade_{t}", **size)
    if poster:
        write_captions(fig_all, fig_aut, t, out_dir)
    print(f"  {t}: price with trade {p_all:.2f} (model {p_model:.2f}), "
          f"without trade {p_aut:.2f} CHF/MWh -> merit_*_{t}.html/.png/.svg")
    return p_all, p_aut


def _hour_id(t):
    return int(str(t).replace("t_", ""))


def date_label(day_of_year):
    """'19 Feb' for day 50 of the 365-day model year (t_1 = 1 January)."""
    m = int(np.searchsorted(DAYS_BEFORE_MONTH, day_of_year - 1, side="right"))
    return f"{day_of_year - int(DAYS_BEFORE_MONTH[m - 1])} {MONTH_ABBR[m - 1]}"


def period_figure(hourly, neighbours, t_a, t_b, out_dir, poster=False, font_scale=None):
    """Hourly decomposition of one period (e.g. a week): price with trade
    (line), price without trade (dashed) and the border contributions as
    stacked bars (they fill the gap between the two lines exactly)."""
    import plotly.graph_objects as go
    fs = _fs(poster, font_scale)
    ia, ib = _hour_id(t_a), _hour_id(t_b)
    h = hourly.assign(hid=hourly["T"].map(_hour_id))
    h = h.loc[(h["hid"] >= ia) & (h["hid"] <= ib)].sort_values("hid")
    if h.empty:
        print(f"--period: no hours between {t_a} and {t_b} in shapley_hourly.csv")
        return None
    day0 = int(h["day"].iloc[0])
    x = (h["hid"] - (day0 - 1) * 24 - 1) / 24.0 + 1          # day-of-period axis
    colors = {nb: neighbour_color(nb, i) for i, nb in enumerate(neighbours)}
    fig = go.Figure()
    for nb in neighbours:
        fig.add_trace(go.Bar(x=x, y=h[f"phi_{nb}"], name=node_label(nb),
                             marker_color=colors[nb], marker_line_width=0, width=1 / 24.0))
    fig.add_trace(go.Scatter(x=x, y=h["price_autarky"], mode="lines", name="price without trade",
                             line=dict(color=INK2, width=2 * fs, dash="dash")))
    fig.add_trace(go.Scatter(x=x, y=h["price_model"], mode="lines", name="price with trade",
                             line=dict(color=INK, width=2.2 * fs)))
    fig.add_hline(y=0, line_color=INK2, line_width=1)
    n_days = int(np.ceil(len(h) / 24))
    ticktext = [date_label(day0 + i) for i in range(n_days)]
    fig.update_layout(
        barmode="relative", bargap=0,
        title=f"Hourly border contributions, {t_a} to {t_b} ({ticktext[0]} to {ticktext[-1]})",
        xaxis=dict(title=None, tickmode="array",
                   tickvals=[i + 0.5 for i in range(1, n_days + 1)],
                   ticktext=ticktext, gridcolor=GRID, range=[1, n_days + 1]),
        yaxis=dict(title="CHF/MWh", gridcolor=GRID),
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(size=15 * fs, color=INK2),
        legend=dict(orientation="h", x=0, y=1.02, xanchor="left", yanchor="bottom",
                    font=dict(size=14 * fs)),
        title_font=dict(size=20), margin=dict(t=80 * fs))
    save_figure(fig, out_dir, f"fig_period_{t_a}_{t_b}", width=1600, height=800)
    return fig


def waterfall_figure(hourly, neighbours, t, out_dir, poster=False, font_scale=None):
    """One hour as a waterfall: price without trade -> one step per border
    (Shapley contribution, neighbour colour) -> price with trade."""
    import plotly.graph_objects as go
    fs = _fs(poster, font_scale)
    row = hourly.loc[hourly["T"] == t]
    if row.empty:
        print(f"--waterfall: hour {t} not in shapley_hourly.csv")
        return None
    r = row.iloc[0]
    order = sorted(neighbours, key=lambda nb: -abs(r[f"phi_{nb}"]))
    labels = ["without trade"] + [node_label(nb) for nb in order] + ["with trade"]
    fig = go.Figure()
    # invisible base + visible step per border (drawn as bars so colours are free)
    base, xs, bases, heights, cols, texts = r["price_autarky"], [], [], [], [], []
    xs.append(labels[0]); bases.append(0); heights.append(base); cols.append(INK2)
    texts.append(f"{base:.1f}")
    running = base
    for nb in order:
        phi = r[f"phi_{nb}"]
        xs.append(node_label(nb)); bases.append(min(running, running + phi))
        heights.append(abs(phi)); cols.append(neighbour_color(nb))
        texts.append(f"{phi:+.1f}")
        running += phi
    xs.append(labels[-1]); bases.append(0); heights.append(r["price_all"]); cols.append(INK)
    texts.append(f"{r['price_all']:.1f}")
    fig.add_trace(go.Bar(x=xs, y=heights, base=bases, marker_color=cols, text=texts,
                         textposition="outside", textfont=dict(size=14 * fs), showlegend=False))
    # connector lines
    running = base
    for i, nb in enumerate(order):
        fig.add_shape(type="line", x0=i - 0.4 + 0.0, x1=i + 1.4, y0=running, y1=running,
                      line=dict(color=INK2, width=1, dash="dot"))
        running += r[f"phi_{nb}"]
    fig.add_shape(type="line", x0=len(order) + 0.6, x1=len(order) + 1.4, y0=running, y1=running,
                  line=dict(color=INK2, width=1, dash="dot"))
    fig.update_layout(
        title=f"Shapley decomposition of hour {t} (day {int(r['day'])}, {int(r['hour']):02d}:00)",
        yaxis=dict(title="CHF/MWh", gridcolor=GRID, rangemode="tozero"),
        xaxis=dict(gridcolor="#ffffff"),
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(size=15 * fs, color=INK2), title_font=dict(size=20),
        margin=dict(t=60 * fs), bargap=0.35)
    save_figure(fig, out_dir, f"fig_waterfall_{t}", width=1400, height=700)
    return fig


def neighbours_from_hourly(hourly):
    return [c[4:] for c in hourly.columns if c.startswith("phi_")]


def run_year_of(folder):
    """run_year of a scenario folder from its scenario settings file, else the folder name."""
    for name in ("scenario_settings.csv", "settings.csv"):
        path = folder / name
        if path.exists():
            df = pd.read_csv(path)
            hit = df.loc[df.iloc[:, 0].astype(str) == "run_year"]
            if len(hit):
                return str(hit.iloc[0, 1])
    import re
    m = re.search(r"(20\d\d)", folder.name)
    return m.group(1) if m else folder.name


def comparison_from_folders(folder, other_scenario, neighbours, out_dir, poster, font_scale=None):
    other = REPO_ROOT / "output" / other_scenario
    path_other = other / "border_shapley" / "shapley_monthly.csv"
    if not path_other.exists():
        print(f"--compare-with: {path_other} not found, skipped")
        return
    monthly = {run_year_of(folder): pd.read_csv(out_dir / "shapley_monthly.csv"),
               run_year_of(other): pd.read_csv(path_other)}
    year_comparison_figure(monthly, neighbours, out_dir, poster=poster, font_scale=font_scale)
    print(f"Side-by-side monthly figure written to {out_dir}")


# ---------------------------------------------------------------------------
def main():
    args = parse_args()
    folder = REPO_ROOT / "output" / args.scenario
    if not folder.exists():
        raise SystemExit(f"Output folder not found: {folder}")
    out_dir = folder / "border_shapley"
    out_dir.mkdir(exist_ok=True)

    need_run = bool(args.merit_hours) or not args.skip_decomposition
    hourly_csv = out_dir / "shapley_hourly.csv"
    if need_run:
        D, node_plants = load_run(folder, args.sub_scenario, args.node)
        neighbours = D["neighbours"]
    elif hourly_csv.exists():
        neighbours = neighbours_from_hourly(pd.read_csv(hourly_csv, nrows=1))
    else:
        raise SystemExit(f"{hourly_csv} not found: run the decomposition first")

    if args.merit_hours:
        print("Merit-order figure pairs ...")
        for t in args.merit_hours.split(","):
            t = t.strip()
            t = t if t.startswith("t_") else f"t_{t}"
            merit_order_figures(D, node_plants, args.node, t, out_dir, args.scenario,
                                poster=args.poster, font_scale=args.font_scale)

    def extra_figures(hourly):
        if args.period:
            t_a, t_b = [x.strip() if x.strip().startswith("t_") else f"t_{x.strip()}"
                        for x in args.period.split(":")]
            period_figure(hourly, neighbours, t_a, t_b, out_dir, args.poster, args.font_scale)
            print(f"Period figure fig_period_{t_a}_{t_b} written")
        if args.waterfall:
            t = args.waterfall.strip()
            t = t if t.startswith("t_") else f"t_{t}"
            waterfall_figure(hourly, neighbours, t, out_dir, args.poster, args.font_scale)
            print(f"Waterfall figure fig_waterfall_{t} written")
        if args.compare_with:
            comparison_from_folders(folder, args.compare_with, neighbours, out_dir, args.poster,
                                    args.font_scale)

    if args.skip_decomposition:
        if hourly_csv.exists():
            hourly = pd.read_csv(hourly_csv)
            if not args.no_figures:
                monthly, hod, spread, _ = aggregate(hourly, neighbours)
                make_figures(hourly, monthly, hod, spread, neighbours, out_dir, args.node,
                             poster=args.poster, font_scale=args.font_scale)
                print(f"Summary figures rebuilt from the CSVs in {out_dir}")
            extra_figures(hourly)
        print(f"Done (decomposition skipped). Results in {out_dir}")
        return

    hours = D["hours"]
    if args.hours:
        a, b = args.hours.split(":")
        ia, ib = int(a.replace("t_", "")), int(b.replace("t_", ""))
        hours = [t for t in hours if ia <= int(t.split("_")[1]) <= ib]

    print(f"Decomposing {len(hours)} hours over {len(neighbours)} borders "
          f"({2 ** len(neighbours)} coalitions per hour) ...")
    rows = []
    for k, t in enumerate(hours):
        base = domestic_blocks(D, node_plants, t)
        trade = trade_blocks_at(D, args.node, t)
        nbs = [nb for nb in neighbours if nb in trade]
        p_aut, p_all, phi = shapley_hour(base, trade, nbs)
        month, hour, day = calendar_of(t)
        row = dict(T=t, day=day, month=month, hour=hour, season=SEASON_OF_MONTH[month],
                   price_model=D["price"][t].get(args.node, np.nan),
                   price_all=p_all, price_autarky=p_aut,
                   trade_effect=p_all - p_aut)
        row["price_gap"] = row["price_all"] - row["price_model"] # type: ignore
        for nb in neighbours:
            row[f"phi_{nb}"] = phi.get(nb, 0.0)
            ci, fi, co, fo, pn = trade.get(nb, (0, 0, 0, 0, np.nan))
            row[f"ntc_in_{nb}"], row[f"flow_in_{nb}"] = ci, fi
            row[f"ntc_out_{nb}"], row[f"flow_out_{nb}"] = co, fo
            row[f"price_{nb}"] = pn
        rows.append(row)
        if (k + 1) % 1000 == 0:
            print(f"  {k + 1}/{len(hours)} hours")
    hourly = pd.DataFrame(rows)
    hourly.to_csv(out_dir / "shapley_hourly.csv", index=False)
    monthly, hod, spread, summary = aggregate(hourly, neighbours)
    monthly.to_csv(out_dir / "shapley_monthly.csv", index=False)
    hod.to_csv(out_dir / "shapley_hour_of_day.csv", index=False)
    spread.to_csv(out_dir / "shapley_spread_daily.csv", index=False)
    pd.Series(summary).to_csv(out_dir / "shapley_summary.csv", header=False)
    gap = hourly["price_gap"].abs()
    print(f"Consistency: |p_all - model price| median {gap.median():.3f}, "
          f"95th pct {gap.quantile(0.95):.3f}, max {gap.max():.3f} CHF/MWh "
          f"({(gap > 0.5).mean() * 100:.1f}% of hours above 0.5)")
    print(pd.Series(summary).round(2).to_string())

    if not args.no_figures and len(hourly) > 24:
        make_figures(hourly, monthly, hod, spread, neighbours, out_dir, args.node,
                     poster=args.poster, font_scale=args.font_scale)
        print(f"Figures written to {out_dir}")
    extra_figures(hourly)
    print(f"Done. Results in {out_dir}")


if __name__ == "__main__":
    main()
