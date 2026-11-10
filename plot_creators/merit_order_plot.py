"""Draw the hourly merit order (supply asks + demand bids) for one hour.

Rebuilds EVERY plant's bid offline from the files in output/<scenario>/ --
no solved model needed -- using the same formulas as
model/price_setting_tech.py::build_candidate_plants_pool (see
price_setting_description/FEM_price_setting_logic.md):

    thermal / biomass  (gen)  bid = operation_slp (+ mu_V energy-budget dual)
    storage discharge  (gen)  bid = operation_slp + watervalue / eta_out
    CHP                (gen)  bid = operation_slp - (lambda_heat + delta) / r
    DSR reduce         (gen)  bid = nu + S + operation_slp
    storage charge     (con)  bid = watervalue * eta_out
    DH heater          (con)  bid = eta * (lambda_heat + delta) - o_th
    household HP       (con)  bid = COP * lambda_building
    electrolyser       (con)  bid = mu_H2 - operation_slp
    DSR add load       (con)  bid = nu - S

Unlike the price_setting_plant_pool CSV (interior candidates only), this
script prices ALL plants of the price-coupled node pool -- including units at
full load (inframarginal) and idle units (out of merit) -- so the full supply
and demand curves can be drawn. Renewable infeed enters as zero-bid supply,
inelastic demand as a block at the lost-load price, and congested
cross-boundary trade as fixed import (supply, bid 0) / export (demand, VOLL)
blocks.

Requires the three exports added for offline reconstruction (runs after the
1001-hour test run of July 2026): energy_limit_dual.csv,
consume_tot_limit_dual.csv, PlantDH_data_remaining.csv.

Usage: set the defaults in the CONFIG block below and simply run the script
(e.g. from the IDE), or override them on the command line (from the repo root):
    python plot_creators/merit_order_plot.py
    python plot_creators/merit_order_plot.py test test_wy2008 t_6553
    python plot_creators/merit_order_plot.py test test_wy2008 6600 --node CH00 --table
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

pio.renderers.default = "browser"

# ---------------------------------------------------------------------------
# CONFIG — defaults used when the script is run without command-line arguments
# ---------------------------------------------------------------------------
SCENARIO = "test"               # scenario folder under output/
SUB_SCENARIO = "test_wy2008"    # sub-scenario name
HOUR = "t_4792"                 # hour, e.g. "t_7000" or just "7000"
NODE = "CH00"                   # reference node whose price pool is drawn
YMAX = None                     # upper y-axis limit [CHF/MWh]; None = auto
PRINT_TABLE = False             # print the full per-plant bid table
SAVE_HTML = None                # e.g. r"output/merit_order_t7000.html"; None = don't save
SHOW = True                     # open the figure in the browser
VALIDATE = False                # cross-check bids against the run's pool CSV

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Static tech -> cost-component map (plain module, no model required).
from model.structural_parameters import Map_plant_tech_cost_component  # noqa: E402
# Role classifier + tier order of the price-setting algorithm (for colours /
# labels). price_setting_tech only needs empty data_prep containers at import.
from model.price_setting_tech import _role_of, _ROLE_TIER  # noqa: E402

EPS = 1e-3          # same interior tolerance as the pool builder
VOLL_FALLBACK = 10000.0
POSTER_FONT_SCALE = 2.0   # --poster: font / line-width multiplier (A1, ~25 cm wide print)
POSTER_SIZE = dict(width=1500, height=820)    # px of the poster PNG/SVG (scale 2)
POSTER_KEY = "caption"    # poster mode: number key 'below' the plot or in the 'caption'
                          # (written to merit_captions_<t>.txt, figure stays compact)

# Colour system shared by every figure of the paper / poster (ZHAW poster
# palette): the four neighbours carry the saturated palette colours,
# identical in the merit order and in the border decomposition figures of
# border_shapley.py; the domestic supply tiers are neutral (sand and greys)
# so that the trade blocks stand out.
PALETTE = {
    "sand": "#EDDBAB", "gold": "#F0B600", "green": "#83B819",
    "brown": "#583119", "darkgreen": "#006633",
}
NEIGHBOUR_COLORS = {
    "DE00": PALETTE["gold"],
    "FR00": PALETTE["darkgreen"],
    "IT00": PALETTE["green"],
    "AT00": PALETTE["brown"],
}
_EXTRA_NEIGHBOUR_COLORS = ["#4a3aa7", "#e87ba4", "#2a78d6", "#7f7f7f"]
INK, INK2, GRID = "#1a1a1a", "#595959", "#e0e0e0"


def neighbour_color(nb, index=0):
    """Colour of neighbour node nb (fallback ramp for nodes not in the map)."""
    return NEIGHBOUR_COLORS.get(nb, _EXTRA_NEIGHBOUR_COLORS[index % len(_EXTRA_NEIGHBOUR_COLORS)])


def node_label(node):
    """Short label for a node id: DE00 -> DE (used in legends/labels)."""
    return node[:-2] if len(node) == 4 and node.endswith("00") else node


TIER_COLORS = {
    "hydro": PALETTE["sand"],
    "electric storage": "#C9B27F",
    "conventional thermal": "#8C8C8C",
    "nuclear": "#4D4D4D",
    "chp": "#B3A58C",
    "biomass": "#A6947A",
    "renewables": "#D9D9D9",
    "sector coupling": "#B0B0B0",
    "trade": "#7f7f7f",
    "lost load": "#5A5A5A",
    "inelastic demand": "#17becf",
    "unclassified": "#333333",
}


RES_KEYWORDS = ("windon", "windoff", "wind", "pv", "solar", "ror")


def role_tier(p):
    """(role, tier) of plant p from the price-setting classifier, with a
    fallback for renewable 'gen' plants the classifier does not know
    (e.g. CH01_windon) -> tier 'renewables'."""
    role = _role_of(p)
    if role == "Nuclear":            # own legend entry: 'thermal' would be misread as gas
        return role, "nuclear"
    if role:
        return role, _ROLE_TIER.get(role, "unclassified")
    name = p.split("_", 1)[1].lower() if "_" in p else p.lower()
    if any(k in name for k in RES_KEYWORDS):
        return "Renewables (plant)", "renewables"
    return "?", "unclassified"


def clear(s_bid, s_cap, d_bid, d_cap):
    """Clearing price of two step curves (numpy arrays): the lowest bid level
    p at which the supply offered at <= p covers the demand bidding STRICTLY
    above p. Handles a supply-side marginal unit (partially dispatched supply
    step at p) as well as a demand-side one (partially served demand step at
    p, e.g. an electrolyser or a storage charging exactly at the price)."""
    import numpy as np
    s_bid, s_cap = np.asarray(s_bid, float), np.asarray(s_cap, float)
    d_bid, d_cap = np.asarray(d_bid, float), np.asarray(d_cap, float)
    if len(d_bid) == 0 or d_cap.sum() <= EPS:
        return float(s_bid.min()) if len(s_bid) else 0.0
    order_s = np.argsort(s_bid, kind="stable")
    sb, sc = s_bid[order_s], np.cumsum(s_cap[order_s])
    order_d = np.argsort(d_bid, kind="stable")
    db, dc = d_bid[order_d], np.cumsum(d_cap[order_d])   # ascending bids
    d_total = dc[-1]
    for p in np.unique(np.concatenate([sb, db])):
        supply_at = sc[np.searchsorted(sb, p, side="right") - 1] if p >= sb[0] else 0.0
        upto = np.searchsorted(db, p, side="right")           # demand bids <= p
        demand_above = d_total - (dc[upto - 1] if upto > 0 else 0.0)
        if supply_at >= demand_above - EPS:
            return float(p)
    return float(db[-1])  # supply never covers demand: VOLL-type price


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="Merit order (supply asks + demand bids) of one hour, "
                    "rebuilt from the output folder. Without arguments the "
                    "CONFIG defaults at the top of the script are used.")
    parser.add_argument("scenario", nargs="?", default=SCENARIO,
                        help=f"Scenario folder under output/ (default {SCENARIO})")
    parser.add_argument("sub_scenario", nargs="?", default=SUB_SCENARIO,
                        help=f"Sub-scenario name (default {SUB_SCENARIO})")
    parser.add_argument("hour", nargs="?", default=HOUR,
                        help=f"Hour, e.g. t_6564 or just 6564 (default {HOUR})")
    parser.add_argument("--node", default=NODE,
                        help=f"Reference node whose price pool is drawn (default {NODE})")
    parser.add_argument("--view", choices=("node", "pool", "autarky"), default="node",
                        help="'node': only the reference node's own plants, with "
                             "per-border trade blocks (full NTC at the neighbour's "
                             "price — approximation, see hover). 'autarky': the same "
                             "without any trade block, cleared on its own (the price "
                             "line is the autarky clearing price, not the model's). "
                             "'pool': all plants of the price-coupled node pool, trade "
                             "blocks only at the congested pool boundary. (default node)")
    parser.add_argument("--save-png", default=None,
                        help="Also write a title-less PNG to this path (needs kaleido)")
    parser.add_argument("--poster", action="store_true",
                        help="Poster styling: larger fonts and line widths, legends "
                             f"outside the plot ({POSTER_SIZE['width']}x{POSTER_SIZE['height']} px)")
    parser.add_argument("--font-scale", type=float, default=None,
                        help="Font / line-width multiplier (overrides --poster's "
                             f"{POSTER_FONT_SCALE}; rule of thumb for a 25 cm wide print: "
                             "14 px * scale should be ~0.024 * figure width in px)")
    parser.add_argument("--no-marginal", action="store_true",
                        help="Poster mode: do not label the marginal unit(s) at the crossing")
    parser.add_argument("--from-blocks", default=None, metavar="CSV",
                        help="Do not rebuild the hour from the run: render the figure "
                             "pair (with / without trade) from a saved block table "
                             "(merit_blocks_<t>.csv written by border_shapley.py); "
                             "PNG/SVG next to the CSV when --save-png is given")
    parser.add_argument("--ymax", type=float, default=YMAX,
                        help="Upper y-axis limit [CHF/MWh]; inelastic/VOLL blocks are "
                             "clipped visually (default: auto from flexible bids)")
    parser.add_argument("--table", action="store_true", default=PRINT_TABLE,
                        help="Print the full per-plant bid table to the console")
    parser.add_argument("--save-html", default=SAVE_HTML,
                        help="Also write the figure to this HTML path")
    parser.add_argument("--no-show", action="store_true", default=not SHOW,
                        help="Do not open the browser (useful with --save-html)")
    parser.add_argument("--validate", action="store_true", default=VALIDATE,
                        help="Cross-check bids against price_setting_plant_pool_<sub>.csv")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------
def read(folder: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(folder / f"{name}.csv")


def sub_only(df: pd.DataFrame, sub: str) -> pd.DataFrame:
    for col in ("Scenarios", "Scenario"):
        if col in df.columns:
            return df.loc[df[col] == sub]
    return df


def wide_map(df: pd.DataFrame) -> dict:
    """Invert a wide 'Node,value,1,2,...' map file to {member: node}."""
    out = {}
    for _, row in df.iterrows():
        key = row.iloc[0]
        for member in row.iloc[1:]:
            if pd.notna(member) and member != "":
                out[member] = key
    return out


def kv(df: pd.DataFrame, key_cols, val_col="value") -> dict:
    """DataFrame -> {key or key-tuple: value}."""
    if isinstance(key_cols, str):
        return dict(zip(df[key_cols], df[val_col]))
    keys = list(zip(*(df[c] for c in key_cols)))
    return dict(zip(keys, df[val_col]))


def day_of(hour: str) -> int:
    return (int(hour.split("_")[1]) - 1) // 24 + 1


# ---------------------------------------------------------------------------
# Bid reconstruction
# ---------------------------------------------------------------------------
def load_ingredients(folder: Path, sub: str, t: str):
    """Read every file once and reduce it to the dictionaries the bid
    formulas need for hour t (mirrors determine_hourly_price_setter)."""
    ing = {}

    sf = kv(read(folder, "constraint_scaling"), "ConstraintNames")
    weight = kv(sub_only(read(folder, "weight_in_objective_fcn"), sub), "Scenarios")[sub]
    ing["weight"] = weight

    # Electricity prices of ALL nodes at t -> price pool of the reference node.
    elp = sub_only(read(folder, "energy_balance_dual"), sub)
    elp = elp.loc[elp["T"] == t]
    ing["price"] = {n: v * sf["energy_balance"] / weight
                    for n, v in zip(elp["Node"], elp["value"])}

    # Plant -> electricity node (wide map covers thermal, storage, DH, BA, DSR).
    ing["plant_node"] = wide_map(read(folder, "Map_node_plant"))
    ing["plant_tech"] = kv(read(folder, "Map_plant_tech"), "P")

    # Quantities and capacities at t.
    g = sub_only(read(folder, "gen"), sub)
    ing["gen"] = kv(g.loc[g["T"] == t], "P_gen")
    c = sub_only(read(folder, "storage_charge"), sub)
    ing["charge"] = kv(c.loc[c["T"] == t], "P_pumping")
    ing["gen_max"] = kv(sub_only(read(folder, "gen_max"), sub), "P_gen")
    ing["pmp_max"] = kv(sub_only(read(folder, "pmp_max"), sub), "P_pumping")
    av = sub_only(read(folder, "avail_plant"), sub)
    ing["avail"] = kv(av.loc[av["T"] == t], "avail_plant_index_0")
    v2g = sub_only(read(folder, "V2G_charging_power_rate"), sub)
    ing["v2g_cap"] = kv(v2g.loc[v2g["T"] == t], "P_evV2G")
    flex = sub_only(read(folder, "Data_plant_flex_d_within_window"), sub)
    ing["flex_max_demand"] = kv(flex, "P_flex_d_within_window", "max_demand")

    # Costs and efficiencies.
    ing["op_slp"] = kv(sub_only(read(folder, "operation_slp"), sub), "P_gen")
    ing["op_slpTh"] = kv(sub_only(read(folder, "operation_slpTh"), sub),
                         "PDH_costExclusivelyOnThermalSide")
    ing["eff_out"] = kv(sub_only(read(folder, "storage_charge_eff_out"), sub),
                        "storage_charge_eff_out_index_0")
    ing["eff_in"] = kv(sub_only(read(folder, "storage_charge_eff_in"), sub),
                       "storage_charge_eff_in_index_0")

    # Storage water value nu = -dual * sf / weight (storage SOC balance).
    wv = sub_only(read(folder, "storage_soc_dual"), sub)
    wv = wv.loc[wv["T"] == t]
    watervalue = {p: -v * sf["storage_soc"] / weight
                  for p, v in zip(wv["P_storage"], wv["value"])}

    # DSR: nu (daily balance midpoint, negated) and S (shift premium, negated),
    # both constant within the day of t; merged like in the pool builder.
    d = day_of(t)
    nu = sub_only(read(folder, "dsr_daily_balance_dual"), sub)
    for p, dd, v in zip(nu["P_dsr"], nu["Days"], nu["value"]):
        if dd == d and v:
            watervalue[p] = -v * sf["dsr_daily_balance"] / weight
    ing["watervalue"] = watervalue
    sh = sub_only(read(folder, "energy_shift_limit_dsr_daily_dual"), sub)
    ing["dsr_shift"] = {p: -v * sf["energy_shift_limit_dsr_daily"] / weight
                        for p, dd, v in zip(sh["P_dsr"], sh["Days"], sh["value"])
                        if dd == d and v}

    # Biomass fuel-scarcity premium mu_V = |dual| * sf / weight (annual budget).
    mu = sub_only(read(folder, "energy_limit_dual"), sub)
    ing["mu_v"] = {p: abs(v) * sf["energy_limit"] / weight
                   for p, v in zip(mu["P_energylim"], mu["value"]) if v}

    # Electrolyser hydrogen value mu_H2 per node: consume_tot_limit_<node>_...
    h2 = read(folder, "consume_tot_limit_dual")
    # abs(): the consume_tot_limit dual comes out NEGATIVE when the must-serve energy is 0 (h2_fixed_price runs, 2026-10-14) and positive otherwise; the hydrogen value is its magnitude
    ing["h2_value"] = {name.split("_")[3]: abs(v) * sf["consume_tot_limit"] / weight
                       for name, v in zip(h2["constraint"], h2["value"])
                       if pd.notna(v)}

    # District heating: lambda_heat + delta per DH node, plant efficiencies.
    hp = sub_only(read(folder, "energy_balancethermal_dual"), sub)
    hp = hp.loc[hp["T"] == t]
    heat_price = {n: v * sf["energy_balancethermal"] / weight
                  for n, v in zip(hp["NodeDH"], hp["value"])}
    de = sub_only(read(folder, "inflexble_demandTh_share_dual"), sub)
    de = de.loc[de["T"] == t]
    for n, v in zip(de["NodeDH"], de["value"]):
        if v:
            heat_price[n] = heat_price.get(n, 0.0) + v * sf["inflexble_demandTh_share"] / weight
    ing["heat_value_dh"] = heat_price  # lambda_heat + delta, per DH node
    ing["nodeDH"] = kv(read(folder, "Map_plantDH_nodeDH"), "PDH")

    dhd = sub_only(read(folder, "PlantDH_data_remaining"), sub)
    piv = dhd.pivot_table(index="PlantDH", columns="Feature", values="value",
                          aggfunc="first")
    is_chp = piv.get("CHPDH", pd.Series(dtype=object)).astype(str) == "True"
    ing["chp_p2h"] = {p: float(v) for p, v in piv.loc[is_chp, "power_to_heat_ratio"].items()
                      if pd.notna(v)}
    eff = piv.loc[~is_chp, "efficiency"] if "efficiency" in piv else pd.Series(dtype=object)
    ing["consumer_eff"] = {p: float(v) for p, v in eff.items() if pd.notna(v)}

    # Household heat pumps (building archetypes): lambda_building, COP, cap.
    bh = sub_only(read(folder, "building_heat_demand_dual"), sub)
    bh = bh.loc[bh["T"] == t]
    ing["ba_heat_value"] = {ba: -v * sf["building_heat_demand"] / weight
                            for ba, v in zip(bh["BA_names"], bh["value"])}
    cop = sub_only(read(folder, "COP"), sub)
    ing["ba_cop"] = kv(cop.loc[cop["T"] == t], "BA_names")
    ing["ba_cap"] = kv(sub_only(read(folder, "BA_max_heating_capacity"), sub), "BA_names")

    return ing


def bid_supply(p, ing):
    """Ask of one generation-side plant (mirrors the pool builder gen loop).
    Returns (bid, ingredients-dict)."""
    op = ing["op_slp"].get(p, 0.0) or 0.0
    tech = ing["plant_tech"].get(p)
    if Map_plant_tech_cost_component.get(tech) in ("cap_op", "cap_op_energy"):
        mc = op
    else:
        mc = 0.0
    mc += ing["mu_v"].get(p, 0.0)

    eff = ing["eff_out"].get(p, 1.0) or 1.0
    wv = ing["watervalue"].get(p, 0.0)
    shift = ing["dsr_shift"].get(p, 0.0)
    parts = {"Marginal Cost": mc, "Watervalue": wv, "DSR Shift Value": shift,
             "Heat Value": 0.0, "Heat COP": 0.0, "H2 Value": 0.0, "Eff_out": eff}

    r = ing["chp_p2h"].get(p)
    if r:
        hv = ing["heat_value_dh"].get(ing["nodeDH"].get(p), 0.0)
        parts["Heat Value"], parts["Heat COP"] = hv, 1.0 / r
        return mc - hv / r, parts
    if shift:
        return wv / eff + mc + shift, parts
    return max(mc, wv / eff + mc), parts


def bid_demand(p, ing):
    """Willingness to pay of one consumption-side plant (mirrors the pool
    builder con loop). Returns (bid, ingredients-dict)."""
    eff = ing["eff_out"].get(p, 1.0) or 1.0
    wv = ing["watervalue"].get(p, 0.0)
    shift = ing["dsr_shift"].get(p, 0.0)
    parts = {"Marginal Cost": 0.0, "Watervalue": wv, "DSR Shift Value": shift,
             "Heat Value": 0.0, "Heat COP": 0.0, "H2 Value": 0.0, "Eff_out": eff}

    eta = ing["consumer_eff"].get(p)
    if eta is not None:                              # DH / industrial heater
        hv = ing["heat_value_dh"].get(ing["nodeDH"].get(p), 0.0)
        op = ing["op_slpTh"].get(p, 0.0) or 0.0
        parts.update({"Heat Value": hv, "Heat COP": eta, "Marginal Cost": op,
                      "Watervalue": 0.0})
        return eta * hv - op, parts
    if p in ing["ba_cap"]:                           # household heat pump
        hv = ing["ba_heat_value"].get(p, 0.0)
        copv = ing["ba_cop"].get(p, 0.0)
        parts.update({"Heat Value": hv, "Heat COP": copv, "Watervalue": 0.0})
        return copv * hv, parts
    if "electrolyzer" in p:
        h2 = ing["h2_value"].get(ing["plant_node"].get(p), 0.0)
        op = ing["op_slp"].get(p, 0.0) or 0.0
        parts.update({"H2 Value": h2, "Marginal Cost": op})
        return h2 - op, parts
    if shift:                                        # DSR adding load
        return wv - shift, parts
    eff_in = ing.get("eff_in", {}).get(p, eff) or eff   # charging uses eta_in
    parts["Eff_in"] = eff_in
    return wv * eff_in, parts                        # storage / V2G charging


def demand_cap(p, ing):
    """Consumption capacity of one consumer at hour t (mirrors pool builder)."""
    if "electrolyzer" in p:
        return ing["flex_max_demand"].get(p, 0.0)
    if "V2G_CH" in p:
        return ing["v2g_cap"].get(p, 0.0) or 0.0
    if p in ing["ba_cap"]:
        return ing["ba_cap"][p]
    return (ing["pmp_max"].get(p, 0.0) or 0.0) * ing["avail"].get(p, 1.0)


# ---------------------------------------------------------------------------
# Fixed blocks: renewables, inelastic demand, lost load, boundary trade
# ---------------------------------------------------------------------------
def fixed_blocks(folder, sub, t, pool, voll):
    """Zero-bid renewable supply, inelastic demand, dispatched lost load and
    congested cross-boundary trade of the price pool at hour t."""
    rows_sup, rows_dem = [], []
    consumer_node = wide_map(read(folder, "Map_node_consumer"))

    inf = sub_only(read(folder, "infeed"), sub)
    inf = inf.loc[inf["T"] == t]
    cur = sub_only(read(folder, "curtailment"), sub)
    cur = cur.loc[cur["T"] == t].groupby("Consumer_with_infeed")["value"].sum()
    inf = inf.loc[inf["Consumer_with_infeed"].map(consumer_node).isin(pool)]
    infeed_avail = inf["value"].sum()
    curtailed = cur.loc[cur.index.map(consumer_node).isin(pool)].sum()
    if infeed_avail > EPS:
        rows_sup.append(dict(
            plant="Renewables (pool)", tier="renewables", bid=0.0,
            capacity=infeed_avail, dispatch=infeed_avail - curtailed))

    # Must-run biomass enters the balance as a fixed profile -> zero-bid block.
    bio = sub_only(read(folder, "Biomass_inflexible_generation"), sub)
    bio = bio.loc[(bio["T"] == t) & bio["Node"].isin(pool), "value"].sum()
    if bio > EPS:
        rows_sup.append(dict(plant="Biomass must-run (pool)", tier="renewables",
                             bid=0.0, capacity=bio, dispatch=bio))

    # Inelastic demand: fixed load + inflexible HP / EV / electrolyser / DH.
    dem = sub_only(read(folder, "demand"), sub)
    dem = dem.loc[(dem["T"] == t)
                  & dem["Consumer"].map(consumer_node).isin(pool), "value"].sum()
    for name in ("HP_inflexible_demand", "EV_inflexible_demand",
                 "Electrolyzer_inflexible_demand", "DH_inflexible_demand"):
        df = sub_only(read(folder, name), sub)
        dem += df.loc[(df["T"] == t) & df["Node"].isin(pool), "value"].sum()
    rows_dem.append(dict(plant="Inelastic demand (pool)", tier="inelastic demand",
                         bid=voll, capacity=dem, dispatch=dem))

    # Dispatched lost load = supply at the lost-load price steps.
    ll = sub_only(read(folder, "lostload"), sub)
    ll = ll.loc[(ll["T"] == t) & ll["Consumer"].map(consumer_node).isin(pool)]
    ll_cost = kv(sub_only(read(folder, "lostload_cost_per_step"), sub), "lostLoad_step")
    for step, val in ll.groupby("lostLoad_step")["value"].sum().items():
        if val > EPS:
            rows_sup.append(dict(plant=f"Lost load (step {step})", tier="lost load",
                                 bid=ll_cost.get(step, voll), capacity=val,
                                 dispatch=val))

    return rows_sup, rows_dem


def trade_blocks(folder, sub, t, pool, prices):
    """Per-border trade blocks for every line with exactly ONE endpoint in the
    pool. Import (supply side) and export (demand side) blocks per neighbour:
    width = full NTC at hour t, bid = the NEIGHBOUR'S clearing price, dispatch
    = the actual flow. APPROXIMATION: the neighbour's price is taken as given
    for the whole NTC width — in reality its price would move once the traded
    volume changes its own merit order (noted in the hover)."""
    line_start = wide_map(read(folder, "Map_node_exportinglineATC"))
    line_end = wide_map(read(folder, "Map_node_importinglineATC"))
    atc_exp = sub_only(read(folder, "ATC_exportlimit"), sub)
    atc_exp = kv(atc_exp.loc[atc_exp["T"] == t], "lineATC")
    atc_imp = sub_only(read(folder, "ATC_importlimit"), sub)
    atc_imp = kv(atc_imp.loc[atc_imp["T"] == t], "lineATC")
    exp = sub_only(read(folder, "Export"), sub)
    flow = kv(exp.loc[exp["T"] == t], "lineATC")

    # neighbour -> [import capacity, import flow, export capacity, export flow]
    agg = {}
    for line in set(line_start) | set(line_end):
        s, e = line_start.get(line), line_end.get(line)
        if s is None or e is None or (s in pool) == (e in pool):
            continue  # pool-internal or fully external
        nb = e if s in pool else s
        f = flow.get(line, 0.0) or 0.0
        if s in pool:   # forward direction leaves the pool
            cap_out, cap_in = atc_exp.get(line, 0.0), atc_imp.get(line, 0.0)
            f_out, f_in = max(f, 0.0), max(-f, 0.0)
        else:           # forward direction enters the pool
            cap_in, cap_out = atc_exp.get(line, 0.0), atc_imp.get(line, 0.0)
            f_in, f_out = max(f, 0.0), max(-f, 0.0)
        a = agg.setdefault(nb, [0.0, 0.0, 0.0, 0.0])
        a[0] += cap_in or 0.0
        a[1] += f_in
        a[2] += cap_out or 0.0
        a[3] += f_out

    rows_sup, rows_dem = [], []
    for nb, (cap_in, f_in, cap_out, f_out) in sorted(agg.items()):
        p_nb = prices.get(nb)
        if p_nb is None:
            continue
        rows_sup_nb, rows_dem_nb = trade_rows(nb, cap_in, f_in, cap_out, f_out, p_nb)
        rows_sup += rows_sup_nb
        rows_dem += rows_dem_nb
    return rows_sup, rows_dem


def trade_rows(nb, cap_in, f_in, cap_out, f_out, p_nb):
    """Import (supply) and export (demand) block rows of ONE neighbour. Shared
    with border_shapley.py so that both scripts label trade identically:
    role 'import from <nb>' / 'export to <nb>', tier 'trade', node id in
    'neighbour'."""
    note = (f"neighbour price {p_nb:.2f} CHF/MWh — approximation: full NTC "
            f"priced at the neighbour's current price")
    rows_sup, rows_dem = [], []
    if cap_in > EPS:
        rows_sup.append(dict(plant=f"Import from {nb} ({note})",
                             role=f"import from {nb}", tier="trade", neighbour=nb,
                             bid=p_nb, capacity=cap_in, dispatch=f_in))
    if cap_out > EPS:
        rows_dem.append(dict(plant=f"Export to {nb} ({note})",
                             role=f"export to {nb}", tier="trade", neighbour=nb,
                             bid=p_nb, capacity=cap_out, dispatch=f_out))
    return rows_sup, rows_dem


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def build_merit_order(folder, sub, t, ref_node, view="node"):
    ing = load_ingredients(folder, sub, t)
    price = ing["price"].get(ref_node)
    if price is None:
        raise SystemExit(f"No price for node {ref_node} at {t} — is the hour "
                         f"inside the modelled window?")
    if view in ("node", "autarky"):
        pool = {ref_node}
    else:
        pool = {n for n, v in ing["price"].items() if abs(v - price) <= 1e-3}

    ll_cost = kv(sub_only(read(folder, "lostload_cost_per_step"), sub), "lostLoad_step")
    voll = ll_cost.get(0, VOLL_FALLBACK)

    rows = []
    for p, dispatch in ing["gen"].items():
        if ing["plant_node"].get(p) not in pool:
            continue
        cap = (ing["gen_max"].get(p, 0.0) or 0.0) * ing["avail"].get(p, 1.0)
        if cap <= EPS:
            continue
        bid, parts = bid_supply(p, ing)
        role, tier = role_tier(p)
        rows.append(dict(side="supply", plant=p, role=role, tier=tier, bid=bid,
                         capacity=cap, dispatch=dispatch or 0.0, **parts))

    unpriced_fixed = 0.0
    for p, dispatch in ing["charge"].items():
        if ing["plant_node"].get(p) not in pool:
            continue
        priced = (p in ing["watervalue"] or p in ing["ba_cap"] or p in ing["consumer_eff"]
                  or "electrolyzer" in p or p in ing["dsr_shift"])
        if not priced:
            # e.g. EV_flex: willingness not reconstructable (weekly EV dual not
            # exported) -> its dispatched charging is shown as inelastic demand
            unpriced_fixed += dispatch or 0.0
            continue
        cap = demand_cap(p, ing)
        if cap <= EPS:
            continue
        bid, parts = bid_demand(p, ing)
        role, tier = role_tier(p)
        rows.append(dict(side="demand", plant=p, role=role, tier=tier, bid=bid,
                         capacity=cap, dispatch=dispatch or 0.0, **parts))
    if unpriced_fixed > EPS:
        rows.append(dict(side="demand", plant="Flexible EV charging (dispatched, unpriced)",
                         role="inelastic demand", tier="inelastic demand", bid=voll,
                         capacity=unpriced_fixed, dispatch=unpriced_fixed))

    sup_fix, dem_fix = fixed_blocks(folder, sub, t, pool, voll)
    if view == "autarky":
        sup_tr, dem_tr = [], []
    else:
        sup_tr, dem_tr = trade_blocks(folder, sub, t, pool, ing["price"])
    for r in sup_fix + sup_tr:
        rows.append(dict(side="supply", **{"role": r.get("role", r["tier"]), **r}))
    for r in dem_fix + dem_tr:
        rows.append(dict(side="demand", **{"role": r.get("role", r["tier"]), **r}))

    df = pd.DataFrame(rows)
    if view == "autarky":
        # no trade: the node clears on its own -> price line = autarky price
        price = clearing_price(df)
    return df, price, pool, voll


def clearing_price(df):
    """Clearing price of a block table (columns side, bid, capacity)."""
    s = df.loc[df["side"] == "supply"]
    d = df.loc[df["side"] == "demand"]
    return clear(s["bid"].values, s["capacity"].values, d["bid"].values, d["capacity"].values)


def curve(df_side, ascending):
    d = df_side.sort_values(["bid", "tier", "plant"], ascending=ascending).copy()
    d["cum_end"] = d["capacity"].cumsum()
    d["cum_start"] = d["cum_end"] - d["capacity"]
    return d


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
def hover(row):
    lines = [f"<b>{row['plant']}</b>", f"tier: {row['tier']}",
             f"bid: {row['bid']:.4f} CHF/MWh",
             f"capacity: {row['capacity']:.1f} MWh",
             f"dispatch: {row['dispatch']:.1f} MWh"]
    for key, label in (("Marginal Cost", "marginal cost"), ("Watervalue", "watervalue"),
                       ("Heat Value", "heat value [CHF/MWh_th]"),
                       ("Heat COP", "heat COP [MWh_th/MWh_el]"),
                       ("H2 Value", "H2 value"), ("DSR Shift Value", "DSR shift value")):
        v = row.get(key)
        if v is not None and pd.notna(v) and abs(v) > 1e-9:
            lines.append(f"{label}: {v:.4f}")
    return "<br>".join(lines)


def _shade(hexcolor, frac):
    """Lighten (frac>0, towards white) or darken (frac<0) a hex colour."""
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if frac >= 0:
        r, g, b = (round(v + (255 - v) * frac) for v in (r, g, b))
    else:
        r, g, b = (round(v * (1 + frac)) for v in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _neighbour_of(row):
    nb = row.get("neighbour")
    if isinstance(nb, str) and nb:
        return nb
    return str(row["role"]).split()[-1]


def _rect(row, y_top, y_bot):
    x = [v / 1e3 for v in (row["cum_start"], row["cum_end"],
                           row["cum_end"], row["cum_start"], row["cum_start"])]
    return x, [y_top, y_top, y_bot, y_bot, y_top]


TRADE_LEGEND_TITLE = "Trade<br>(bar: import,<br>thick step: export)"
TRADE_LEGEND_TITLE_SHORT = "Trade"   # poster with key in the caption: explained there
TIER_LEGEND_LABEL = {"conventional thermal": "gas, other", "electric storage": "storage"}


def supply_bar_traces(sup, ymax, font_scale=1.0, seen=None, trade_title=TRADE_LEGEND_TITLE):
    """Filled bars per supply plant, coloured by tier; one legend entry per
    tier ('Supply' legend group). Import blocks carry the neighbour's colour
    (NEIGHBOUR_COLORS, shared with the decomposition figures) and appear in a
    'Trade' legend group with ONE entry per neighbour (shared with the export
    bars through `seen`). Zero-bid blocks get a thin strip below the zero
    line so they stay visible and hoverable."""
    traces = []
    seen = set() if seen is None else seen
    for _, row in sup.iterrows():
        y_top = min(row["bid"], ymax)
        y_bot = 0.0
        if row["bid"] <= EPS:
            y_top, y_bot = 0.0, -0.012 * ymax
        if row["tier"] == "trade":
            nb = _neighbour_of(row)
            key, color, group = node_label(nb), neighbour_color(nb), "trade"
        else:
            key = TIER_LEGEND_LABEL.get(row["tier"], row["tier"])
            color, group = TIER_COLORS.get(row["tier"], "#333333"), "supply"
        show = key not in seen
        seen.add(key)
        x, y = _rect(row, y_top, y_bot)
        traces.append(go.Scatter(
            x=x, y=y, fill="toself", fillcolor=color, opacity=0.9,
            line=dict(color="white", width=0.5),
            mode="lines", name=key, legendgroup=group,
            legendgrouptitle_text=("Supply" if group == "supply" else trade_title)
            if show else None,
            legendrank=(2000 if group == "trade" else 1000),
            showlegend=show,
            hovertext=hover(row), hoverinfo="text", hoveron="fills"))
    return traces


def export_step_traces(dem, ymax, font_scale=1.0, seen=None, trade_title=TRADE_LEGEND_TITLE):
    """Export blocks on the demand side: drawn as a THICK coloured segment of
    the demand step (the block's width at the neighbour's price) with short
    end ticks, in the neighbour's colour. Nothing is filled below the step,
    so the marking never overlaps the supply bars. Legend entry only for a
    neighbour without import block (the import bar covers it otherwise)."""
    traces = []
    seen = set() if seen is None else seen
    tick = 0.025 * ymax
    for _, row in dem.iterrows():
        if row["tier"] != "trade":
            continue
        nb = _neighbour_of(row)
        key, color = node_label(nb), neighbour_color(nb)
        show = key not in seen
        seen.add(key)
        y = min(row["bid"], 0.985 * ymax)
        x0, x1 = row["cum_start"] / 1e3, row["cum_end"] / 1e3
        traces.append(go.Scatter(
            x=[x0, x0, x1, x1], y=[y - tick, y, y, y - tick], mode="lines",
            line=dict(color=color, width=5 * font_scale),
            name=key, legendgroup="trade", legendrank=2000, showlegend=show,
            legendgrouptitle_text=trade_title if show else None,
            hovertext=hover(row), hoverinfo="text"))
    return traces


DEMAND_LABEL = {
    "inelastic demand": "regular demand",
    "trade": "export over congested lines",
}


def demand_label(row):
    if row["tier"] == "trade":
        return f"export to {node_label(_neighbour_of(row))}"
    return DEMAND_LABEL.get(row["role"], row["role"])


def demand_segments(dem, min_share=0.01):
    """Merge the demand curve into numbered segments: consecutive blocks of
    the same role become one segment; segments narrower than min_share of the
    total demand volume are merged into the neighbour with the closer bid."""
    segs = []
    for _, row in dem.iterrows():
        label = demand_label(row)
        if segs and segs[-1]["label"] == label:
            segs[-1]["x1"] = row["cum_end"]
            segs[-1]["bid_top"] = max(segs[-1]["bid_top"], row["bid"])
        else:
            segs.append(dict(label=label, x0=row["cum_start"], x1=row["cum_end"],
                             bid_top=row["bid"]))
    w_min = min_share * dem["cum_end"].iloc[-1]
    merged = True
    while merged and len(segs) > 1:
        merged = False
        for i, s in enumerate(segs):
            if s["x1"] - s["x0"] >= w_min:
                continue
            j = i - 1 if i > 0 else i + 1
            if 0 < i < len(segs) - 1:  # pick the neighbour with the closer bid
                j = i - 1 if abs(segs[i - 1]["bid_top"] - s["bid_top"]) <= \
                             abs(segs[i + 1]["bid_top"] - s["bid_top"]) else i + 1
            tgt = segs[j]
            keep = tgt if (tgt["x1"] - tgt["x0"]) >= (s["x1"] - s["x0"]) else s
            # the wider block keeps label AND label height (a sliver with an
            # outlier bid must not push the number to the top of the axis)
            tgt.update(label=keep["label"], bid_top=keep["bid_top"],
                       x0=min(tgt["x0"], s["x0"]), x1=max(tgt["x1"], s["x1"]))
            segs.pop(i)
            merged = True
            break
    # a merge can leave two neighbouring segments with the same label
    # (e.g. pumped hydro | tiny V2G merged into it | pumped hydro): join them
    joined = []
    for sg in segs:
        if joined and joined[-1]["label"] == sg["label"]:
            joined[-1]["x1"] = max(joined[-1]["x1"], sg["x1"])
            joined[-1]["bid_top"] = max(joined[-1]["bid_top"], sg["bid_top"])
        else:
            joined.append(sg)
    return joined


def auto_ymax(df, price):
    """Robust y-axis limit: a few small expensive units must not stretch the
    axis — clip at the CAPACITY-weighted 98th percentile of the flexible
    bids (supply without lost load, demand without the inelastic block)."""
    flexible = pd.concat([
        df.loc[(df["side"] == "supply") & (df["tier"] != "lost load"), ["bid", "capacity"]],
        df.loc[(df["side"] == "demand")
               & ~df["tier"].isin(["inelastic demand"]), ["bid", "capacity"]]])
    flexible = flexible.sort_values("bid")
    share = flexible["capacity"].cumsum() / max(flexible["capacity"].sum(), EPS)
    q98 = float(flexible.loc[share >= 0.98, "bid"].iloc[0]) if (share >= 0.98).any() \
        else float(flexible["bid"].max())
    return max(1.25 * q98, 1.5 * price, 20.0)


def make_figure(df, price, pool, t, args=None, voll=VOLL_FALLBACK, *, node=None,
                scenario="", ymax=None, xmax=None, font_scale=1.0, view=None,
                price_label=None, key=None, mark_marginal=False):
    """Merit-order figure of one block table.

    df: rows with side, plant, role, tier, bid, capacity, dispatch (+ optional
    neighbour for trade rows); price: the price to draw as the clearing line;
    ymax / xmax: axis limits (pass the same values to both figures of a
    with/without-trade pair so the blocks visibly disappear); font_scale:
    poster scaling of fonts, line widths and hatches; view: 'node' | 'autarky'
    | 'pool' (title only); key: where the demand number key goes, 'inside'
    (box in the plot, default for screen), 'below' the plot or 'caption'
    (not drawn; the entries are stored in fig.layout.meta['demand_key'])."""
    if args is not None:
        node = node or getattr(args, "node", None)
        scenario = scenario or getattr(args, "scenario", "")
        ymax = ymax or getattr(args, "ymax", None)
        font_scale = POSTER_FONT_SCALE if getattr(args, "poster", False) else font_scale
        font_scale = getattr(args, "font_scale", None) or font_scale
        view = view or getattr(args, "view", None)
    fs = font_scale
    sup = curve(df.loc[df["side"] == "supply"], ascending=True)
    dem = curve(df.loc[df["side"] == "demand"], ascending=False)
    ymax = ymax or auto_ymax(df, price)

    fig = go.Figure()
    outside = fs > 1.2   # poster: legend and demand key outside the plot area
    key = key or (POSTER_KEY if outside else "inside")

    # Supply: coloured filled bars, legend per tier; imports per neighbour.
    seen = set()
    trade_title = TRADE_LEGEND_TITLE_SHORT if key == "caption" else TRADE_LEGEND_TITLE
    for tr in supply_bar_traces(sup, ymax, fs, seen, trade_title):
        fig.add_trace(tr)
    export_traces = export_step_traces(dem, ymax, fs, seen, trade_title)

    # Demand: black dashed step curve over ALL blocks, hoverable.
    x, y, texts = [], [], []
    for _, row in dem.iterrows():
        y_clip = min(row["bid"], 0.985 * ymax)
        x += [row["cum_start"] / 1e3, row["cum_end"] / 1e3]
        y += [y_clip, y_clip]
        texts += [hover(row), hover(row)]
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name="Demand (bids)",
                             line=dict(color="black", width=2 * fs, dash="dash"),
                             showlegend=False,
                             hovertext=texts, hoverinfo="text"))
    # Exports: thick coloured segments ON the demand curve (on top of it).
    for tr in export_traces:
        fig.add_trace(tr)

    x_end = max(sup["cum_end"].iloc[-1], dem["cum_end"].iloc[-1]) / 1e3
    x_axis_end = xmax or 1.03 * x_end

    # Numbered demand segments + the number -> technology mapping as a box
    # (top LEFT — the demand curve starts there; supply legend sits right).
    segs = demand_segments(dem, min_share=0.03 if outside else 0.01)
    label_numbers, last_x, level = {}, -1e9, 0
    for n, s in enumerate(segs, start=1):
        x_mid = (s["x0"] + s["x1"]) / 2e3
        # alternate the label height whenever the previous number is close by
        level = 1 - level if (x_mid - last_x) < 0.04 * x_axis_end * fs else 0
        last_x = x_mid
        y_off = 0.022 * ymax * fs + level * 0.035 * ymax * fs
        fig.add_annotation(x=x_mid,
                           y=min(s["bid_top"], 0.985 * ymax) + y_off,
                           text=f"<b>{n}</b>", showarrow=False,
                           font=dict(size=(13 if outside else 16) * fs, color="black"))
        label_numbers.setdefault(s["label"], []).append(str(n))
    entries = [f"{','.join(nums)}: {label}" for label, nums in label_numbers.items()]
    if key == "caption":
        n_lines_below = 0
    elif outside:
        # poster: the number key runs BELOW the plot in three columns, so the
        # right margin only has to hold the supply / trade legend
        ncol = 3
        per_col = -(-len(entries) // ncol)
        cols = [entries[i * per_col:(i + 1) * per_col] for i in range(ncol)]
        # column positions in paper units; the third column runs into the
        # right margin below the supply legend (paper x > 1 is allowed)
        col_x = [0.0, 0.62, 1.24]
        fig.add_annotation(xref="paper", yref="paper", x=0, y=-0.15, xanchor="left",
                           yanchor="top", align="left", text="<b>Demand</b>",
                           showarrow=False, font=dict(size=14 * fs))
        for i, col in enumerate(cols):
            if col:
                fig.add_annotation(xref="paper", yref="paper", x=col_x[i], y=-0.205,
                                   xanchor="left", yanchor="top", align="left",
                                   text="<br>".join(col), showarrow=False,
                                   font=dict(size=14 * fs))
        n_lines_below = per_col + 2
    else:
        fig.add_annotation(xref="paper", yref="paper", x=0.01, y=0.99, xanchor="left",
                           yanchor="top", align="left",
                           text="<br>".join(["<b>Demand</b>"] + entries), showarrow=False,
                           font=dict(size=14 * fs), bordercolor="#999999",
                           borderwidth=1, bgcolor="rgba(255,255,255,0.85)")
        n_lines_below = 0

    # Clearing price line (no marker — the curves' crossing shows it).
    fig.add_hline(y=price, line_dash="dot", line_color="#444444", line_width=1.2 * fs,
                  annotation_text=price_label or (f"{price:.1f}" if outside
                                                  else f"{price:.2f} CHF/MWh"),
                  annotation_position="top left",
                  annotation_font=dict(size=14 * fs, color="#444444"))

    # Marginal unit(s): the blocks whose bid equals the clearing price. Named
    # with an arrow at the crossing, so a sliver (e.g. 0.14 GW of 'other'
    # thermal between nuclear and the first hydro cluster) is not overlooked.
    if mark_marginal:
        tol = 0.05
        m_sup = sup.loc[(sup["bid"] - price).abs() <= tol]
        m_dem = dem.loc[(dem["bid"] - price).abs() <= tol]

        def _name(rows):
            agg = rows.groupby("role")["capacity"].sum().sort_values(ascending=False)
            r, c = next(iter(agg.items()))
            lab = (node_label(r.split()[-1]) if r.startswith(("import from", "export to"))
                   else r.lower())
            more = f" +{len(agg) - 1}" if len(agg) > 1 else ""
            return f"{lab} {c / 1e3:.1f} GW{more}"

        lines = []
        if len(m_sup):
            lines.append(f"{_name(m_sup)} (supply)")
        if len(m_dem):
            lines.append(f"{_name(m_dem)} (demand)")
        if lines:
            x_cross = (float(m_sup["cum_start"].min()) if len(m_sup)
                       else float(m_dem["cum_end"].max())) / 1e3
            fig.add_annotation(x=x_cross, y=price, ax=0.98 * x_axis_end, ay=1.03 * ymax,
                               axref="x", ayref="y", xanchor="right", yanchor="top",
                               text="marginal: " + "<br>".join(lines), showarrow=True,
                               arrowhead=2, arrowwidth=1.2 * fs, arrowcolor="#444444",
                               font=dict(size=11 * fs, color="#444444"), align="right",
                               bgcolor="rgba(255,255,255,0.9)", bordercolor="#999999",
                               borderwidth=1)

    if view == "autarky":
        view_txt = "node view, no trade"
        note = "no trade blocks: the node clears on its own (autarky price)"
    else:
        view_txt = "node view" if len(pool) == 1 else f"pool of {len(pool)} nodes"
        note = "trade blocks: full NTC at the neighbour's current price (approximation)"
    fig.update_layout(
        title=(f"Market clearing for electricity: {t}, {node} ({view_txt})"
               f"{' — ' + scenario if scenario else ''}"
               f"<br><sup>bids above {ymax:.0f} CHF/MWh (regular demand at "
               f"VOLL {voll:.0f}) are clipped to the top edge; {note}</sup>"),
        xaxis_title="volume [GW]" if outside else "bid and ask volume [GW]",
        yaxis_title="price [CHF/MWh]" if outside else "bid and ask price [CHF/MWh]",
        xaxis_range=[0, x_axis_end],
        yaxis_range=[-0.02 * ymax, ymax * 1.06],
        plot_bgcolor="white",
        font=dict(size=15 * fs),
        title_font=dict(size=20),
        xaxis=dict(gridcolor="#dddddd", title_font=dict(size=18 * fs), automargin=True,
                   tickfont=dict(size=14 * fs)),
        yaxis=dict(gridcolor="#dddddd", title_font=dict(size=18 * fs), automargin=True,
                   tickfont=dict(size=14 * fs)),
        legend=dict(font=dict(size=(11.5 if outside else 14) * fs), bordercolor="#999999",
                    borderwidth=1, bgcolor="rgba(255,255,255,0.85)",
                    grouptitlefont=dict(size=(11.5 if outside else 14) * fs),
                    tracegroupgap=(4 * fs if outside else 10),
                    **(dict(x=1.02, y=1.0, xanchor="left", yanchor="top") if outside
                       else dict(x=0.99, y=0.99, xanchor="right", yanchor="top"))),
        template="plotly_white",
    )
    fig.update_layout(meta=dict(demand_key=entries, price=price))
    if outside:
        fig.update_layout(margin=dict(r=int(170 * fs),
                                      b=int((n_lines_below * 1.45 * 14 + 60) * fs)))
    return fig, sup, dem


def figure_pair(df, t, node, scenario="", voll=VOLL_FALLBACK, poster=False, font_scale=None,
                key=None, mark_marginal=None):
    """Merit-order figures of one block table WITH the trade blocks and
    WITHOUT them (autarky), on identical axes and colours. Returns
    (fig_with, fig_without, price_with, price_without); both prices come from
    clearing the block table (price_with reproduces the model's dual)."""
    fs = font_scale or (POSTER_FONT_SCALE if poster else 1.0)
    mark_marginal = poster if mark_marginal is None else mark_marginal
    df_aut = df.loc[df["tier"] != "trade"].reset_index(drop=True)
    p_all, p_aut = clearing_price(df), clearing_price(df_aut)
    ymax = auto_ymax(df, max(p_all, p_aut))
    xmax = 1.03 * max(df.loc[df["side"] == "supply", "capacity"].sum(),
                      df.loc[df["side"] == "demand", "capacity"].sum()) / 1e3
    fig_all, _, _ = make_figure(df, p_all, {node}, t, voll=voll, node=node, scenario=scenario,
                                ymax=ymax, xmax=xmax, font_scale=fs, view="node", key=key,
                                mark_marginal=mark_marginal)
    fig_aut, _, _ = make_figure(df_aut, p_aut, {node}, t, voll=voll, node=node,
                                scenario=scenario, ymax=ymax, xmax=xmax, font_scale=fs,
                                view="autarky", key=key, mark_marginal=mark_marginal)
    return fig_all, fig_aut, p_all, p_aut


def caption_lines(fig_all, fig_aut, t):
    """Caption text for a figure pair (used when the number key is not drawn
    in the figure): one block per figure with price and demand key."""
    out = []
    for label, fig in (("with neighbours", fig_all), ("without neighbours", fig_aut)):
        meta = fig.layout.meta or {}
        key = ", ".join(e.replace(":", "") for e in meta.get("demand_key", []))
        out.append(f"[{label}] {t}, clearing price {meta.get('price', float('nan')):.1f} "
                   f"CHF/MWh. Demand bids: {key}.")
    return out


def write_captions(fig_all, fig_aut, t, folder):
    path = Path(folder) / f"merit_captions_{t}.txt"
    path.write_text("\n".join(caption_lines(fig_all, fig_aut, t)) + "\n", encoding="utf-8")
    return path


def write_image_variants(fig, path_png, width=1300, height=780, scale=2, svg=True):
    """Title-less PNG (+ SVG next to it) for the paper / poster; needs kaleido."""
    png_fig = go.Figure(fig)
    png_fig.update_layout(title=None, margin=dict(t=30))
    try:
        png_fig.write_image(path_png, width=width, height=height, scale=scale)
        if svg:
            png_fig.write_image(str(Path(path_png).with_suffix(".svg")),
                                width=width, height=height)
        return True
    except Exception as exc:  # kaleido missing or similar
        global _IMAGE_EXPORT_WARNED
        if not _IMAGE_EXPORT_WARNED:
            _IMAGE_EXPORT_WARNED = True
            print(f"Image export failed ({str(exc).strip().splitlines()[0]}); install "
                  f"kaleido (pip install kaleido) for PNG/SVG output. HTML is written anyway.")
        return False


_IMAGE_EXPORT_WARNED = False


# ---------------------------------------------------------------------------
# Validation against the pool CSV written during the run
# ---------------------------------------------------------------------------
def validate(df, folder, sub, t):
    path = folder / f"price_setting_plant_pool_{sub}.csv"
    if not path.exists():
        print(f"[validate] {path.name} not found — skipped.")
        return
    ref = pd.read_csv(path)
    ref = ref.loc[ref["Hour"] == t]
    merged = ref.merge(df, left_on=["Technology", "Sign"],
                       right_on=["plant", "side_short"], how="left")
    missing = merged.loc[merged["bid"].isna(), "Technology"].tolist()
    if missing:
        print(f"[validate] WARNING — {len(missing)} pool candidates not "
              f"reconstructed: {missing}")
    diff = (merged["Bidding price"] - merged["bid"]).abs()
    print(f"[validate] {len(merged)} interior candidates at {t}: "
          f"max |bid difference| = {diff.max():.3e} CHF/MWh"
          + ("  <-- MISMATCH" if diff.max() > 1e-6 else "  (OK)"))


# ---------------------------------------------------------------------------
def render_pair_from_blocks(csv_path, node, scenario, poster, save_png, show, font_scale=None,
                            mark_marginal=None):
    """Figure pair from a saved block table (see --from-blocks)."""
    path = Path(csv_path)
    df = pd.read_csv(path)
    df.loc[df["role"] == "Nuclear", "tier"] = "nuclear"   # tables written before the split
    t = path.stem.replace("merit_blocks_", "")
    voll = float(df.loc[df["role"] == "inelastic demand", "bid"].max()) \
        if (df["role"] == "inelastic demand").any() else VOLL_FALLBACK
    fig_all, fig_aut, p_all, p_aut = figure_pair(df, t, node, scenario, voll, poster, font_scale,
                                                 mark_marginal=mark_marginal)
    print(f"{t}: price with trade {p_all:.2f}, without trade {p_aut:.2f} CHF/MWh")
    size = POSTER_SIZE if poster else dict(width=1300, height=780)
    for fig, name in ((fig_all, f"merit_with_trade_{t}"), (fig_aut, f"merit_without_trade_{t}")):
        fig.write_html(path.parent / f"{name}.html")
        if save_png:
            write_image_variants(fig, str(path.parent / f"{name}.png"), **size)
    if poster:
        write_captions(fig_all, fig_aut, t, path.parent)
    print(f"Figures written next to {path}")
    if show:
        fig_all.show()
        fig_aut.show()


def main():
    args = parse_args()
    if args.from_blocks:
        render_pair_from_blocks(args.from_blocks, args.node, args.scenario, args.poster,
                                save_png=bool(args.save_png), show=not args.no_show,
                                font_scale=args.font_scale,
                                mark_marginal=False if args.no_marginal else None)
        return
    t = args.hour if str(args.hour).startswith("t_") else f"t_{args.hour}"
    folder = REPO_ROOT / "output" / args.scenario
    if not folder.exists():
        raise SystemExit(f"Output folder not found: {folder}")

    df, price, pool, voll = build_merit_order(folder, args.sub_scenario, t,
                                              args.node, view=args.view)
    df["side_short"] = df["side"].map({"supply": "gen", "demand": "con"})

    print(f"Hour {t}  |  clearing price {price:.4f} CHF/MWh  |  "
          f"pool ({len(pool)} nodes): {', '.join(sorted(pool))}")

    sup_d = df.loc[df["side"] == "supply", "dispatch"].sum()
    dem_d = df.loc[df["side"] == "demand", "dispatch"].sum()
    print(f"Balance check: supply dispatch {sup_d:,.0f} MWh vs demand dispatch "
          f"{dem_d:,.0f} MWh (mismatch {sup_d - dem_d:+,.0f} MWh)")

    if args.validate:
        validate(df, folder, args.sub_scenario, t)

    if args.table:
        cols = ["side", "plant", "tier", "bid", "capacity", "dispatch",
                "Marginal Cost", "Watervalue", "Heat Value", "Heat COP",
                "H2 Value", "DSR Shift Value"]
        with pd.option_context("display.max_rows", None, "display.width", 250):
            print(df.sort_values(["side", "bid"], ascending=[True, False])[cols]
                  .to_string(index=False))
    else:
        summary = (df.groupby(["side", "tier"])
                   .agg(plants=("plant", "count"), capacity=("capacity", "sum"),
                        dispatch=("dispatch", "sum"), bid_min=("bid", "min"),
                        bid_max=("bid", "max")).round(2))
        print(summary.to_string())

    fig, _, _ = make_figure(df, price, pool, t, args, voll)
    if args.save_html:
        fig.write_html(args.save_html)
        print(f"Figure written to {args.save_html}")
    if args.save_png and write_image_variants(fig, args.save_png):
        print(f"PNG/SVG (title-less) written to {args.save_png}")
    if not args.no_show:
        fig.show()


if __name__ == "__main__":
    main()
