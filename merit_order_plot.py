"""
Merit-order visualization for a given (scenario, sub_scenario, hour, node).

Draws the hourly zonal market cross at the target node:

* SUPPLY curve (ascending step curve of filled blocks):
    - must-take RES infeed (bid 0) and must-run biomass schedule (bid 0)
    - dispatchable generators at operation_slp (+ biomass fuel-scarcity
      premium mu_V from energy_limit_dual where it binds)
    - storage discharge (dam / psp / battery / hydrogen / V2G) at its
      opportunity cost: water value / eta_out  (water value = -storage_soc dual)
    - one import block per neighbour at the neighbour's clearing price,
      width = ATC into the node
* DEMAND curve (descending step curve of filled blocks):
    - inflexible load (base + inflex EV/HP/DH/electrolyzer - lost load)
      at the lost-load cost (VOLL)
    - electrolyzer at its hourly willingness to pay = consume_tot_limit dual
      (in h2_steps mode this is pinned by the elastic step values; the hover
      shows the annual step structure)
    - storage / EV / V2G charging at water value x eta_in
    - flexible heat: household heat-pump archetypes at heat value x COP,
      district-heating HPs / heaters at DH heat value x COP(eff)
    - one export block per neighbour at the neighbour's price, width = ATC
    - curtailment as a zero-price sink (only if curtailment.csv is present)
* Envelope step lines for both curves, the model's dual price as a dashed
  line, and the supply=demand crossing marked with a dot. If the merit-order
  picture is consistent, the crossing sits on the dual price.

All duals are rescaled with constraint_scaling.csv and divided by the
sub-scenario weight, mirroring price_setting_tech.py.

Usage:
    Edit the CONFIGURATION block below, then run:  python merit_order_plot.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


# ============================================================================
# CONFIGURATION — edit these before running
# ============================================================================
SCENARIO = "2050_Chbat_wy2008_12hydro_h2steps_7steps"
SUB_SCENARIO = "2050_Chbat_wy2008_12hydro_h2steps_7steps_wy2008"
HOUR = "t_1219"   # e.g. "t_6700"
NODE = "CH00"     # e.g. "CH00"
# ============================================================================

TOL = 0.001  # MW tolerance

# --- family -> base colour (validated palette; neutrals for context).
# Individual members of a family (hydro clusters, storages, countries,
# electrolyzer steps, heat groups, thermal techs) are distinguished as
# lightness shades of the family hue, each with its own legend entry.
FAMILY_BASE = {
    # supply
    "Must-take RES":        "#1baf7a",  # aqua
    "Reservoir hydro":      "#2a78d6",  # blue
    "Storage discharge":    "#eda100",  # yellow
    "Thermal & other gen":  "#eb6834",  # orange
    "Import":               "#8a8985",  # neutral
    # demand
    "Inflexible load":      "#52514e",  # dark neutral
    "Electrolyzer":         "#e87ba4",  # magenta
    "Storage & EV charging": "#4a3aa7",  # violet
    "Flexible heat":        "#008300",  # green
    "Export":               "#e34948",  # red
    "Curtailment":          "#c9c8c2",  # light neutral
}


def _shade(hexcolor: str, frac: float) -> str:
    """Lighten (frac>0, towards white) or darken (frac<0) a hex colour."""
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if frac >= 0:
        r, g, b = (round(v + (255 - v) * frac) for v in (r, g, b))
    else:
        r, g, b = (round(v * (1 + frac)) for v in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def build_item_colors(blocks: list[dict]) -> dict[str, str]:
    """One colour per legend item: family hue, members spread over shades."""
    fam_items: dict[str, list[str]] = {}
    for b in blocks:
        fam_items.setdefault(b["group"], [])
        if b["item"] not in fam_items[b["group"]]:
            fam_items[b["group"]].append(b["item"])
    colors: dict[str, str] = {}
    for fam, items in fam_items.items():
        base = FAMILY_BASE[fam]
        n = len(items)
        if n == 1:
            colors[items[0]] = base
            continue
        for i, it in enumerate(items):
            frac = -0.32 + 0.72 * i / (n - 1)   # dark -> light across members
            colors[it] = _shade(base, frac)
    return colors
SURFACE = "#fcfcfb"
GRID = "#e8e7e3"
INK = "#0b0b0b"
INK2 = "#52514e"

STORE_TECHS = {"dam", "psp_open", "psp_close", "battery", "hydrogen",
               "v2g", "ev_flex", "TES", "PTES_large", "TTES_medium"}
RESERVOIR_TECHS = {"dam"}


def read_filtered(path: Path,
                  sub: str | None = None,
                  t: str | None = None) -> pd.DataFrame:
    """Read CSV; filter by Scenarios and (optionally) T column."""
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()
    if df.empty:
        return df
    if sub is not None and "Scenarios" in df.columns:
        df = df[df["Scenarios"] == sub]
    if t is not None and "T" in df.columns:
        df = df[df["T"] == t]
    return df.copy()


def parse_wide_node_csv(path: Path) -> dict[str, list[str]]:
    """For Map_node_plant.csv / Map_node_*ingLineATC.csv style files
    (Node, value, 1, 2, ... layout)."""
    result: dict[str, list[str]] = {}
    if not path.exists() or path.stat().st_size == 0:
        return result
    df = pd.read_csv(path)
    for _, row in df.iterrows():
        node = str(row.iloc[0])
        vals = [str(v) for v in row.iloc[1:].tolist()
                if pd.notna(v) and str(v).strip() != ""]
        result[node] = vals
    return result


def first_col_dict(df: pd.DataFrame, value_col: str = "value") -> dict:
    if df.empty:
        return {}
    return dict(zip(df.iloc[:, 0].astype(str), df[value_col]))


def main(scenario: str = SCENARIO,
         sub_scenario: str = SUB_SCENARIO,
         hour: str = HOUR,
         node: str = NODE) -> None:
    scen, sub = scenario, sub_scenario
    out_dir = Path("output") / scen
    if not out_dir.exists():
        print(f"ERROR: output dir not found: {out_dir}", file=sys.stderr)
        sys.exit(1)

    # Weight, scaling factors, prices -------------------------------------
    settings = pd.read_csv(out_dir / "settings.csv", index_col=0)
    if sub not in settings.columns:
        print(f"ERROR: sub_scenario {sub} not in settings.csv", file=sys.stderr)
        sys.exit(1)
    weight = float(settings.loc["weight_in_objective_fcn", sub])  # type: ignore

    sf_df = pd.read_csv(out_dir / "constraint_scaling.csv")
    sf = dict(zip(sf_df.iloc[:, 0].astype(str), sf_df["value"]))

    eb = read_filtered(out_dir / "energy_balance_dual.csv", sub, hour)
    if eb.empty:
        print(f"ERROR: no energy_balance_dual at {sub}/{hour}", file=sys.stderr)
        sys.exit(1)
    eb["price"] = eb["value"] * sf.get("energy_balance", 1.0) / weight # type: ignore
    price_at_node = dict(zip(eb["Node"].astype(str), eb["price"]))
    if node not in price_at_node:
        print(f"ERROR: node {node} not in energy_balance_dual at {hour}",
              file=sys.stderr)
        sys.exit(1)
    target_price = float(price_at_node[node])

    # Maps and per-plant data ---------------------------------------------
    plants_by_node = parse_wide_node_csv(out_dir / "Map_node_plant.csv")
    local_plants = plants_by_node.get(node, [])

    mpt = pd.read_csv(out_dir / "Map_plant_tech.csv")
    map_plant_tech = dict(zip(mpt.iloc[:, 0].astype(str),
                              mpt.iloc[:, -1].astype(str)))

    op_slp_dict = first_col_dict(read_filtered(out_dir / "operation_slp.csv", sub))
    gen_max_dict = first_col_dict(read_filtered(out_dir / "gen_max.csv", sub))
    pmp_max_dict = first_col_dict(read_filtered(out_dir / "pmp_max.csv", sub))
    avail_dict = first_col_dict(read_filtered(out_dir / "avail_plant.csv", sub, hour))
    gen_dict = first_col_dict(read_filtered(out_dir / "gen.csv", sub, hour))
    charge_dict = first_col_dict(read_filtered(out_dir / "storage_charge.csv", sub, hour))
    eff_in_dict = first_col_dict(read_filtered(out_dir / "storage_charge_eff_in.csv", sub))
    eff_out_dict = first_col_dict(read_filtered(out_dir / "storage_charge_eff_out.csv", sub))

    # Water values: WV = -dual * sf / weight  (price_setting convention)
    soc_df = read_filtered(out_dir / "storage_soc_dual.csv", sub, hour)
    wv = {str(p): -float(v) * sf.get("storage_soc", 1.0) / weight
          for p, v in zip(soc_df.iloc[:, 0], soc_df["value"])} if not soc_df.empty else {}

    # Biomass fuel-scarcity premium mu_V
    el_dual_df = read_filtered(out_dir / "energy_limit_dual.csv", sub)
    mu_v = {str(p): abs(float(v)) * sf.get("energy_limit", 1.0) / weight
            for p, v in zip(el_dual_df.iloc[:, 0], el_dual_df["value"])} if not el_dual_df.empty else {}

    # Electrolyzer: hourly capacity + hourly willingness (= consume dual)
    win_df = read_filtered(out_dir / "Data_plant_flex_d_within_window.csv", sub)
    elz_cap, elz_steps, elz_must = {}, {}, {}
    if not win_df.empty:
        for _, r in win_df.iterrows():
            p = str(r.iloc[0])
            elz_cap[p] = float(r.get("max_demand", 0.0) or 0.0)
            raw_e = r.get("value")  # the "energy" list, e.g. "[1028375.7]"
            if isinstance(raw_e, str) and raw_e.strip().startswith("["):
                try:
                    elz_must[p] = float(ast.literal_eval(raw_e)[0])
                except (ValueError, SyntaxError, IndexError):
                    pass
            raw = r.get("elastic_steps")
            if isinstance(raw, str) and raw.strip().startswith("{"):
                try:
                    elz_steps[p] = ast.literal_eval(raw)
                except (ValueError, SyntaxError):
                    pass
    cons_df = pd.read_csv(out_dir / "consume_tot_limit_dual.csv") \
        if (out_dir / "consume_tot_limit_dual.csv").exists() else pd.DataFrame()
    elz_dual = {}
    if not cons_df.empty:
        for _, r in cons_df.iterrows():
            name = str(r["constraint"])
            if not name.endswith("_" + sub):
                continue
            n = name.replace("consume_tot_limit_", "").split("_electrolyzer")[0]
            # abs(): the consume_tot_limit dual comes out NEGATIVE when the must-serve energy is 0 (h2_fixed_price runs, 2026-10-14) and positive otherwise; the hydrogen value is its magnitude
            elz_dual[n] = abs(float(r["value"])) * sf.get("consume_tot_limit", 1.0) / weight

    h2res = pd.read_csv(out_dir / "h2_steps_result.csv") \
        if (out_dir / "h2_steps_result.csv").exists() else pd.DataFrame()

    # ----------------------------------------------------------------------
    # SUPPLY blocks
    # ----------------------------------------------------------------------
    supply: list[dict] = []

    # Must-take RES infeed (per tech, bid 0)
    infeed_df = read_filtered(out_dir / "infeed.csv", sub, hour)
    if not infeed_df.empty:
        c0 = infeed_df.columns[0]
        node_rows = infeed_df[infeed_df[c0].astype(str).str.startswith(node + "_")]
        tech_col = infeed_df.columns[1]
        for tech, grp in node_rows.groupby(tech_col):
            capv = float(grp["value"].sum())
            if capv > TOL:
                supply.append({"group": "Must-take RES", "label": f"RES {tech}",
                               "item": f"RES {tech}",
                               "bid": 0.0, "cap": capv, "disp": capv,
                               "note": "must-take infeed"})

    # Must-run biomass schedule (only non-zero when switch_biomass=False)
    bio_df = read_filtered(out_dir / "Biomass_inflexible_generation.csv", sub, hour)
    if not bio_df.empty:
        v = float(bio_df[bio_df.iloc[:, 0].astype(str) == node]["value"].sum())
        if v > TOL:
            supply.append({"group": "Must-take RES", "label": "Biomass (fixed schedule)",
                           "item": "Biomass (fixed schedule)",
                           "bid": 0.0, "cap": v, "disp": v, "note": "must-run"})

    # Local plants: dispatchable generators and storage discharge
    for plant in local_plants:
        tech = map_plant_tech.get(plant, "")
        gm = float(gen_max_dict.get(plant, 0.0))
        av = float(avail_dict.get(plant, 1.0))
        cap = gm * av
        if cap <= TOL:
            continue
        g = float(gen_dict.get(plant, 0.0))
        if plant in wv:  # storage discharge at opportunity cost
            eff_o = float(eff_out_dict.get(plant, 1.0)) or 1.0
            bid = wv[plant] / eff_o
            group = "Reservoir hydro" if tech in RESERVOIR_TECHS else "Storage discharge"
            supply.append({"group": group, "label": plant, "item": plant,
                           "bid": bid, "cap": cap, "disp": g,
                           "note": f"water value {wv[plant]:.2f} / eta_out {eff_o:.2f}"})
        elif plant in op_slp_dict:
            bid = float(op_slp_dict[plant]) + mu_v.get(plant, 0.0)
            note = f"marginal cost {float(op_slp_dict[plant]):.2f}"
            if mu_v.get(plant, 0.0) > 0.005:
                note += f" + fuel-scarcity mu {mu_v[plant]:.2f}"
            supply.append({"group": "Thermal & other gen", "label": plant,
                           "item": tech or "other gen",
                           "bid": bid, "cap": cap, "disp": g, "note": note})
        # plants with neither op_slp nor a water value (electrolyzer, EV, HP
        # archetypes) are demand-side and handled below

    # Imports per neighbour at the neighbour's price
    exp_lines = parse_wide_node_csv(out_dir / "Map_node_exportinglineATC.csv")
    imp_lines = parse_wide_node_csv(out_dir / "Map_node_importinglineATC.csv")
    line_start = {ln: n for n, ls in exp_lines.items() for ln in ls}
    line_end = {ln: n for n, ls in imp_lines.items() for ln in ls}
    atc_exp = first_col_dict(read_filtered(out_dir / "ATC_exportlimit.csv", sub, hour))
    atc_imp = first_col_dict(read_filtered(out_dir / "ATC_importlimit.csv", sub, hour))

    exports: list[dict] = []
    for ln in exp_lines.get(node, []):        # node is START of line
        nb = line_end.get(ln)
        if nb is None or nb not in price_at_node:
            continue
        p_nb = float(price_at_node[nb])
        if float(atc_imp.get(ln, 0.0)) > TOL:  # reverse flow = import
            supply.append({"group": "Import", "label": f"Import from {nb}",
                           "item": f"Import \u2190 {nb}",
                           "bid": p_nb, "cap": float(atc_imp[ln]), "disp": None,
                           "note": f"line {ln}, NTC {float(atc_imp[ln]):.0f} MW"})
        if float(atc_exp.get(ln, 0.0)) > TOL:
            exports.append({"group": "Export", "label": f"Export to {nb}",
                            "item": f"Export \u2192 {nb}",
                            "bid": p_nb, "cap": float(atc_exp[ln]), "disp": None,
                            "note": f"line {ln}, NTC {float(atc_exp[ln]):.0f} MW"})
    for ln in imp_lines.get(node, []):        # node is END of line
        nb = line_start.get(ln)
        if nb is None or nb not in price_at_node:
            continue
        p_nb = float(price_at_node[nb])
        if float(atc_exp.get(ln, 0.0)) > TOL:  # forward flow = import
            supply.append({"group": "Import", "label": f"Import from {nb}",
                           "item": f"Import \u2190 {nb}",
                           "bid": p_nb, "cap": float(atc_exp[ln]), "disp": None,
                           "note": f"line {ln}, NTC {float(atc_exp[ln]):.0f} MW"})
        if float(atc_imp.get(ln, 0.0)) > TOL:
            exports.append({"group": "Export", "label": f"Export to {nb}",
                            "item": f"Export \u2192 {nb}",
                            "bid": p_nb, "cap": float(atc_imp[ln]), "disp": None,
                            "note": f"line {ln}, NTC {float(atc_imp[ln]):.0f} MW"})

    # ----------------------------------------------------------------------
    # DEMAND blocks
    # ----------------------------------------------------------------------
    demand: list[dict] = []

    def sum_node_param(filename: str) -> float:
        df = read_filtered(out_dir / filename, sub, hour)
        if df.empty:
            return 0.0
        d = df[df.iloc[:, 0].astype(str) == node]
        return float(d["value"].sum()) if not d.empty else 0.0

    dem_df = read_filtered(out_dir / "demand.csv", sub, hour)
    base_demand = 0.0
    if not dem_df.empty:
        c0 = dem_df.columns[0]
        base_demand = float(
            dem_df[dem_df[c0].astype(str).str.startswith(node + "_")]["value"].sum())
    ev_i = sum_node_param("EV_inflexible_demand.csv")
    hp_i = sum_node_param("HP_inflexible_demand.csv")
    dh_i = sum_node_param("DH_inflexible_demand.csv")
    el_i = sum_node_param("Electrolyzer_inflexible_demand.csv")
    ll_df = read_filtered(out_dir / "lostload.csv", sub, hour)
    lost = 0.0
    if not ll_df.empty:
        c0 = ll_df.columns[0]
        lost = float(
            ll_df[ll_df[c0].astype(str).str.startswith(node + "_")]["value"].sum())

    voll_df = read_filtered(out_dir / "lostload_cost_per_step.csv", sub)
    voll = float(voll_df["value"].max()) if not voll_df.empty else 10000.0

    inflex = base_demand + ev_i + hp_i + dh_i + el_i - lost
    demand.append({"group": "Inflexible load", "label": "Inflexible load",
                   "item": "Inflexible load",
                   "bid": voll, "cap": inflex, "disp": inflex,
                   "note": (f"base {base_demand:.0f} + EV {ev_i:.0f} + HP {hp_i:.0f}"
                            f" + DH {dh_i:.0f} + ELZ-inflex {el_i:.0f}"
                            f" - lost load {lost:.0f}; drawn at VOLL {voll:.0f}")})

    # Electrolyzer (flexible): hourly willingness = consume_tot_limit dual.
    # In h2_steps mode the hourly capacity is split into sub-blocks by the
    # ANNUAL demand structure (must-serve / elastic steps) so the steps stay
    # distinguishable. All sub-blocks sit at the SAME hourly bid — intra-year
    # arbitrage equalises the marginal value across the year at the annual
    # shadow price; the step WTPs are annual quantities (shown in the hover).
    for plant in local_plants:
        if map_plant_tech.get(plant) != "electrolyzer":
            continue
        cap = elz_cap.get(plant, 0.0) * float(avail_dict.get(plant, 1.0))
        if cap <= TOL:
            continue
        bid = elz_dual.get(node)
        if bid is None:
            continue
        disp_tot = float(charge_dict.get(plant, 0.0))
        steps = elz_steps.get(plant)
        must_e = float(elz_must.get(plant, 0.0))
        if steps:
            widths = {"must": must_e}
            widths.update({f"s{sid}": float(s["width"])
                           for sid, s in sorted(steps.items())})
            tot_w = sum(widths.values()) or 1.0
            for key, w_ann in widths.items():
                if w_ann <= 0:
                    continue
                share = w_ann / tot_w
                if key == "must":
                    item = "Electrolyzer must-serve"
                    note = (f"forced annual offtake {w_ann/1e6:.2f} TWh_el"
                            f" ({share*100:.0f}% of annual structure)<br>"
                            f"hourly willingness = annual shadow {bid:.2f}")
                else:
                    sid = int(key[1:]);  s = steps[sid]
                    served = ""
                    if not h2res.empty:
                        row = h2res[(h2res["plant"] == plant)
                                    & (h2res["step_id"] == sid)]
                        if not row.empty and float(row["width_MWh"].iloc[0]) > 0:
                            served = (f", {100*float(row['E_served_MWh'].iloc[0])/float(row['width_MWh'].iloc[0]):.0f}% served")
                    item = (f"Electrolyzer step {sid}"
                            f" ({s['wtp_CHF_per_MWh_H2']:.0f}/MWh_H2)")
                    note = (f"annual width {w_ann/1e6:.2f} TWh_el"
                            f" ({share*100:.0f}%), value_el {s['value_el']:.1f}"
                            f"{served}<br>segment: {s.get('segment','')}<br>"
                            f"hourly willingness = annual shadow {bid:.2f}")
                demand.append({"group": "Electrolyzer",
                               "label": f"{plant} [{item}]", "item": item,
                               "bid": float(bid), "cap": cap * share,
                               "disp": disp_tot * share, "note": note})
        else:
            demand.append({"group": "Electrolyzer", "label": plant,
                           "item": "Electrolyzer",
                           "bid": float(bid), "cap": cap, "disp": disp_tot,
                           "note": "hourly willingness = annual-constraint shadow price"})

    # Storage / EV / V2G charging at water value x eta_in
    v2g_rate_df = read_filtered(out_dir / "V2G_charging_power_rate.csv", sub, hour)
    v2g_rate = first_col_dict(v2g_rate_df) if not v2g_rate_df.empty else {}
    unpriced_flex: list[str] = []
    for plant in local_plants:
        if map_plant_tech.get(plant) == "electrolyzer":
            continue
        pm = float(pmp_max_dict.get(plant, 0.0))
        if plant in v2g_rate:
            pm = min(pm, float(v2g_rate[plant])) if pm > TOL else float(v2g_rate[plant])
        cap = pm * float(avail_dict.get(plant, 1.0))
        if cap <= TOL:
            continue
        if plant not in wv:
            # flexible consumer without an exported hourly value (e.g. EV_flex,
            # whose willingness lives in the weekly EV constraints) — cannot be
            # placed on the bid axis; report it so a curve mismatch is explicable.
            # (candidates covered by the heat blocks below are filtered out
            # before printing.)
            ch = float(charge_dict.get(plant, 0.0))
            if ch > TOL:
                unpriced_flex.append((plant, ch))
            continue
        eff_i = float(eff_in_dict.get(plant, 1.0)) or 1.0
        bid = wv[plant] * eff_i
        demand.append({"group": "Storage & EV charging", "label": f"{plant} (charging)",
                       "item": f"{plant} (charging)",
                       "bid": bid, "cap": cap,
                       "disp": float(charge_dict.get(plant, 0.0)),
                       "note": f"water value {wv[plant]:.2f} x eta_in {eff_i:.2f}"})

    # Flexible heat 1: household heat-pump archetypes (heat value x COP)
    hv_df = read_filtered(out_dir / "building_heat_demand_dual.csv", sub, hour)
    cop_df = read_filtered(out_dir / "COP.csv", sub, hour)
    cap_df = read_filtered(out_dir / "BA_max_heating_capacity.csv", sub)
    if node == "CH00" and not hv_df.empty and not cop_df.empty and not cap_df.empty:
        hv = dict(zip(hv_df["BA_names"].astype(str), hv_df["value"]))
        cop = dict(zip(cop_df["BA_names"].astype(str), cop_df["value"]))
        bcap = dict(zip(cap_df.iloc[:, 0].astype(str), cap_df["value"]))
        sf_h = sf.get("building_heat_demand", 1.0)
        for ba, cth in bcap.items():
            c = float(cop.get(ba, 0.0) or 0.0)
            if c <= 0 or float(cth) <= TOL:
                continue
            heat_val = abs(float(hv.get(ba, 0.0))) * sf_h / weight
            bid = heat_val * c
            cap_el = float(cth) / c
            if cap_el <= TOL:
                continue
            ba_l = str(ba).lower()
            hp_item = ("Household HP (new/minergie)"
                       if ba_l.startswith(("new_", "minergie"))
                       else "Household HP (old buildings)")
            demand.append({"group": "Flexible heat", "label": f"HP {ba}",
                           "item": hp_item,
                           "bid": bid, "cap": cap_el, "disp": None,
                           "note": f"heat value {heat_val:.2f} CHF/MWh_th x COP {c:.2f}"})

    # Flexible heat 2: district-heating HPs / resistive heaters at this node
    dhval_df = read_filtered(out_dir / "energy_balancethermal_dual.csv", sub, hour)
    pdh_df = pd.read_csv(out_dir / "PlantDH_data_remaining.csv") \
        if (out_dir / "PlantDH_data_remaining.csv").exists() else pd.DataFrame()
    genth_max = first_col_dict(read_filtered(out_dir / "genTh_max.csv", sub))
    pdh_node_map = parse_wide_node_csv(out_dir / "Map_plantDH_nodeEl.csv")
    if not dhval_df.empty and not pdh_df.empty:
        dh_heat_val = {str(r["NodeDH"]): float(r["value"])
                       * sf.get("energy_balancethermal", 1.0) / weight
                       for _, r in dhval_df.iterrows()}
        pdh_df = pdh_df[pdh_df["Scenario"] == sub] if "Scenario" in pdh_df.columns else pdh_df
        feat = {(str(r["PlantDH"]), str(r["Feature"])): r["value"]
                for _, r in pdh_df.iterrows()}
        pdh_plants = sorted({p for (p, _) in feat})
        pdh_to_nodedh = parse_wide_node_csv(out_dir / "Map_plantDH_nodeDH.csv") \
            if (out_dir / "Map_plantDH_nodeDH.csv").exists() else {}
        pdh_tech = {}
        if (out_dir / "Map_plantDH_tech.csv").exists():
            mdt = pd.read_csv(out_dir / "Map_plantDH_tech.csv")
            pdh_tech = dict(zip(mdt.iloc[:, 0].astype(str),
                                mdt.iloc[:, -1].astype(str)))
        for p in pdh_plants:
            # electricity-consuming DH assets: heat pumps + resistive heaters.
            # market feature is blank for investment candidates (heaters), so
            # gate on tech + the single-electric-node convention (all DH at CH00).
            tech_dh = pdh_tech.get(p, "")
            is_el_consumer = tech_dh in ("heat_pump", "resistive_heater")
            market_val = str(feat.get((p, "market"), "") or "")
            if not is_el_consumer:
                continue
            if market_val not in (node, "", "nan") or node != "CH00":
                continue
            effv = feat.get((p, "efficiency"))
            try:
                effv = float(effv)
            except (TypeError, ValueError):
                continue
            if effv <= 0:
                continue
            cth = float(genth_max.get(p, 0.0))
            if cth <= TOL:
                continue
            nodedh = (pdh_to_nodedh.get(p, [None]) or [None])[0]
            hv_th = dh_heat_val.get(str(nodedh), None) if nodedh else None
            if hv_th is None:
                continue  # no heat value known for this DH node this hour
            bid = abs(hv_th) * effv if tech_dh == "resistive_heater" \
                else abs(hv_th) * effv  # HP: heat value x COP
            cap_el = cth / effv
            kind = "COP" if tech_dh == "heat_pump" else "eff"
            if tech_dh == "resistive_heater":
                dh_item = "Resistive heaters (DH/industry)"
            elif p.startswith(("ILLT", "ILHT")):
                dh_item = "Industrial HP (ILLT/ILHT)"
            else:
                dh_item = "District heating HP"
            demand.append({"group": "Flexible heat", "label": f"DH {p}",
                           "item": dh_item,
                           "bid": bid, "cap": cap_el, "disp": None,
                           "note": (f"DH heat value {abs(hv_th):.2f} CHF/MWh_th"
                                    f" x {kind} {effv:.2f}")})

    # Exports (built above alongside imports)
    demand.extend(exports)

    # Curtailment as zero-price sink (only if the per-hour file is present)
    cur_df = read_filtered(out_dir / "curtailment.csv", sub, hour)
    if not cur_df.empty:
        c0 = cur_df.columns[0]
        cur = float(
            cur_df[cur_df[c0].astype(str).str.startswith(node)]["value"].sum())
        if cur > TOL:
            demand.append({"group": "Curtailment", "label": "Curtailment",
                           "item": "Curtailment",
                           "bid": 0.0, "cap": cur, "disp": cur,
                           "note": "surplus RES absorbed at price 0"})

    # ----------------------------------------------------------------------
    # Sort, cumulate, envelopes, crossing
    # ----------------------------------------------------------------------
    supply.sort(key=lambda b: b["bid"])
    demand.sort(key=lambda b: -b["bid"])

    def envelope(blocks):
        xs, ys, c = [0.0], [blocks[0]["bid"]] if blocks else [0.0], 0.0
        for b in blocks:
            xs += [c, c + b["cap"]]
            ys += [b["bid"], b["bid"]]
            c += b["cap"]
        return xs[1:], ys[1:], c

    sx, sy, s_tot = envelope(supply)
    dx, dy, d_tot = envelope(demand)

    def curve_q_at_price(blocks, p, side):
        """Cumulative width with bid <= p (supply) or bid >= p (demand)."""
        q = 0.0
        for b in blocks:
            if (side == "s" and b["bid"] <= p + 1e-6) or \
               (side == "d" and b["bid"] >= p - 1e-6):
                q += b["cap"]
        return q

    s_at = curve_q_at_price(supply, target_price, "s")
    s_below = curve_q_at_price(supply, target_price - 0.01, "s")
    d_at = curve_q_at_price(demand, target_price, "d")
    d_above = curve_q_at_price(demand, target_price + 0.01, "d")
    # consistent iff the curves overlap at the dual price:
    crossing_ok = (s_below <= d_at + TOL) and (d_above <= s_at + TOL)
    q_cross = 0.5 * (max(s_below, d_above) + min(s_at, d_at))

    # ----------------------------------------------------------------------
    # Figure
    # ----------------------------------------------------------------------
    fig = go.Figure()
    item_colors = build_item_colors(supply + demand)
    seen_items: set[str] = set()
    first_supply_item = supply[0]["item"] if supply else None
    first_demand_item = demand[0]["item"] if demand else None

    ymax = 1.15 * max([b["bid"] for b in supply]
                      + [b["bid"] for b in demand if b["bid"] < voll]
                      + [target_price, 80.0])

    def hover_text(b):
        disp = "" if b["disp"] is None else f"<br>dispatched: {b['disp']:.1f} MW"
        return (f"<b>{b['label']}</b> ({b['group']})<br>"
                f"bid: {b['bid']:.2f} CHF/MWh<br>"
                f"capacity: {b['cap']:.1f} MW{disp}<br>{b['note']}")

    # SUPPLY: classic filled merit-order rectangles. Zero-bid blocks (must-take
    # RES) get a thin strip just below the zero line so they stay visible and
    # hoverable instead of collapsing to zero height.
    c = 0.0
    for b in supply:
        x0, x1 = c, c + b["cap"]
        color = item_colors[b["item"]]
        show = b["item"] not in seen_items
        seen_items.add(b["item"])
        y_top, y_bot = b["bid"], 0.0
        if b["bid"] <= TOL:
            y_top, y_bot = 0.0, -1.8
        fig.add_trace(go.Scatter(
            x=[x0, x1, x1, x0, x0],
            y=[y_top, y_top, y_bot, y_bot, y_top],
            fill="toself", fillcolor=color, opacity=0.8,
            line=dict(color=SURFACE, width=1),
            mode="lines",
            name=b["item"],
            legendgroup="s",
            legendgrouptitle_text="Supply" if b["item"] == first_supply_item else None,
            showlegend=show,
            text=hover_text(b), hoverinfo="text",
        ))
        c = x1

    # DEMAND: bold coloured step segments riding on the dashed envelope, so
    # the two curves stay readable where they overlap the supply fills.
    c = 0.0
    for b in demand:
        x0, x1 = c, c + b["cap"]
        y = min(b["bid"], ymax * 0.985)  # inflexible block clips at the top
        color = item_colors[b["item"]]
        show = b["item"] not in seen_items
        seen_items.add(b["item"])
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y, y],
            mode="lines",
            line=dict(color=color, width=6),
            name=b["item"],
            legendgroup="d",
            legendgrouptitle_text="Demand" if b["item"] == first_demand_item else None,
            showlegend=show,
            text=hover_text(b), hoverinfo="text",
        ))
        c = x1

    fig.add_trace(go.Scatter(x=sx, y=sy, mode="lines",
                             line=dict(color=INK, width=2),
                             name="Supply curve", legendgroup="s",
                             hoverinfo="skip"))
    dy_clip = [min(v, ymax * 0.985) for v in dy]
    fig.add_trace(go.Scatter(x=dx, y=dy_clip, mode="lines",
                             line=dict(color=INK, width=1.5, dash="dash"),
                             name="Demand curve", legendgroup="d",
                             hoverinfo="skip"))

    fig.add_hline(y=target_price,
                  line=dict(color=INK2, dash="dot", width=1.5),
                  annotation_text=f"model price = {target_price:.2f} CHF/MWh",
                  annotation_position="top left",
                  annotation_font_color=INK2)
    fig.add_trace(go.Scatter(
        x=[q_cross], y=[target_price], mode="markers",
        marker=dict(size=11, color=INK,
                    line=dict(color=SURFACE, width=2)),
        name="Supply = demand",
        showlegend=False,
        text=(f"crossing at {q_cross:.0f} MW / {target_price:.2f} CHF/MWh"
              f"<br>consistency: {'OK' if crossing_ok else 'MISMATCH'}"),
        hoverinfo="text"))

    check = "consistent" if crossing_ok else "MISMATCH — inspect console output"
    fig.update_layout(
        title=dict(
            text=(f"Merit order — {node} @ {hour}<br>"
                  f"<sup>{scen} / {sub} · dual price {target_price:.2f} CHF/MWh · "
                  f"curves {check}</sup>"),
            font=dict(color=INK, size=18)),
        xaxis=dict(title="Cumulative capacity [MW]", gridcolor=GRID,
                   zeroline=False, color=INK2),
        yaxis=dict(title="Bid / willingness to pay [CHF/MWh]", gridcolor=GRID,
                   zeroline=False, color=INK2,
                   range=[-3, ymax]),
        plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
        hovermode="closest", height=760, width=1240,
        legend=dict(orientation="v", x=1.02, y=1, groupclick="toggleitem",
                    font=dict(color=INK2)),
        font=dict(family="Helvetica, Arial, sans-serif"),
    )
    # note: y-axis clipped below VOLL on purpose — the inflexible block runs to
    # VOLL; a small annotation explains instead of scaling the axis to 10'000.
    fig.add_annotation(x=inflex / 2, y=ymax * 0.94,
                       text=f"inflexible load (willingness = VOLL {voll:.0f})",
                       showarrow=False, font=dict(color=INK2, size=11))

    out_path = out_dir / f"merit_order_{sub}_{node}_{hour}.html"
    fig.write_html(out_path)

    # Console summary ------------------------------------------------------
    print(f"Saved merit order plot to {out_path}")
    print(f"  dual price: {target_price:.2f} CHF/MWh | crossing q = {q_cross:.0f} MW"
          f" | curves {'consistent' if crossing_ok else 'MISMATCH'}")
    print(f"  supply: {len(supply)} blocks, {s_tot:.0f} MW total"
          f" | demand: {len(demand)} blocks, {d_tot:.0f} MW total")
    print(f"  S(p-): {s_below:.0f}  S(p): {s_at:.0f}  D(p+): {d_above:.0f}  D(p): {d_at:.0f}")
    heat_block_names = {b["label"].replace("HP ", "").replace("DH ", "")
                        for b in demand if b["group"] == "Flexible heat"}
    remaining = [f"{p} (charging {c:.0f} MW)" for p, c in unpriced_flex
                 if p not in heat_block_names]
    if remaining:
        print("  NOTE unpriced flexible consumers (not on the demand curve): "
              + "; ".join(remaining))
    for name, blocks in (("SUPPLY", supply), ("DEMAND", demand)):
        print(f"  --- {name} (sorted) ---")
        for b in blocks:
            disp = "" if b["disp"] is None else f" disp={b['disp']:.0f}"
            print(f"    {b['bid']:9.2f}  {b['cap']:9.0f} MW{disp}  "
                  f"[{b['group']}] {b['label']}")


if __name__ == "__main__":
    main()
