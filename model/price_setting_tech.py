"""Hourly price-setting attribution.

Reconstructs every plant's electricity bid from the KKT/dual conditions of the
solved LP and identifies, for each hour, the plant whose bid equals the
clearing price (method of Geis et al. 2026, Energy Economics 157, 109213).

Entry point: ``aggregate_price_setting_data`` (called from core.py after the
solve). Full derivation of every bid formula:
price_setting_description/FEM_price_setting_logic.md — keep it in sync.

Unit convention: every value reconstructed from a constraint dual is converted
to CHF/MWh as ``raw_dual * sf / weight``, where sf is the constraint's row
scaling (model/constraint_scaling.py) and weight the sub-scenario's objective
weight. Forgetting sf caused the electrolyser x1000 bug.
"""

from pathlib import Path

import pandas as pd

from data_prep.definitions_common import Map_plant_node, Map_plant_tech, PlantDH_data_remaining
from model.structural_parameters import Map_plant_tech_cost_component
from model.constraint_scaling import constraint_scaling


# ===========================================================================
# 1. Driver
# ===========================================================================

def determine_hourly_price_setter(
    scenario,
    sub_scenarios,
    model,
    el_prices,
    heat_prices=None,
    node='CH00',
    plant_node=Map_plant_node,
):
    """Determine the hourly price-setting plant for one sub-scenario.

    Returns (per-hour setter DataFrame, technology count DataFrame).
    """
    weight = model.weight_in_objective_fcn[sub_scenarios]

    # Filter to this sub-scenario up front: the dual table holds every
    # sub-scenario, and mixing them corrupts the pool and the price lookup.
    if 'Scenarios' in el_prices.columns:
        el_prices_sub = el_prices.loc[el_prices['Scenarios'] == sub_scenarios].copy()
    else:
        el_prices_sub = el_prices

    # One dict per opportunity-cost mechanism (all scaled by sf / weight).
    sf_consume = constraint_scaling.get("consume_tot_limit", 1.0)
    electrolyzers_dual_dict = {
        # abs(): the consume_tot_limit dual comes out NEGATIVE when the must-serve energy is 0 (h2_fixed_price runs, 2026-10-14) and positive otherwise; the hydrogen value is its magnitude
        n: (abs(d) * sf_consume / weight if d else 0.0)
        for n, d in extract_all_electrolyzer_duals(
            model, list(model.Map_node_country), sub_scenarios).items()
    }
    duals_dsr = extract_duals_dsr_daily_balance(model, sub_scenarios)
    energy_limit_dual_dict = get_energy_limit_dual_dict(model, sub_scenarios, weight)
    dh_info = build_dh_pricing_info(model, sub_scenarios, heat_prices, weight)
    hp_info = build_building_hp_info(model, sub_scenarios, weight)
    watervalues = determine_duals_p_t_s(
        model, model.storage_soc, constraint_scaling["storage_soc"], weight
    )
    watervalues.update(build_dsr_watervalues(model, sub_scenarios, duals_dsr, weight))
    dsr_shift = build_dsr_shift_values(model, sub_scenarios, weight)

    # Nodes price-coupled to the reference node compete in one candidate pool.
    pool_nodes = build_pool_same_price(el_prices_sub, node)

    pool_plants = build_candidate_plants_pool(
        scenario,
        sub_scenarios,
        pool_nodes,
        plant_node,
        model.gen,
        model.storage_charge,
        model.Data_plant_flex_d_within_window,
        model.pmp_max,
        model.avail_plant,
        model.V2G_charging_power_rate,
        model.storage_charge_eff_out,
        model.storage_charge_eff_in,
        model.gen_max,
        model.operation_slp,
        model.operation_slpTh,
        watervalues,
        electrolyzers_dual_dict,
        energy_limit_dual_dict,
        dh_info,
        hp_info,
        dsr_shift,
        model.BA_names,
    )

    # 2026-10-14: with a fixed hydrogen price (h2_fixed_price) the electrolyzer
    # bids an exogenous value (eta x H2 price) and is treated like a supplier in
    # the supply-first tie-break. Detected from the data: the fixed-price import
    # writes one elastic step with segment "fixed_price".
    electrolyzer_as_supply = any(
        isinstance(d, dict)
        and any(st.get("segment") == "fixed_price" for st in (d.get("elastic_steps") or {}).values())
        for (_p, _s), d in model.Data_plant_flex_d_within_window.items()
        if _s == sub_scenarios
    )

    return pick_plants(pool_plants, el_prices_sub, sub_scenarios, scenario, weight, node,
                       electrolyzer_as_supply=electrolyzer_as_supply)


# ===========================================================================
# 2. Pool of price-coupled nodes
# ===========================================================================

def build_pool_same_price(el_prices: pd.DataFrame, node: str) -> dict:
    """{t: set of nodes whose price equals the reference node's within 1e-3}.

    An uncongested interconnector forces equal prices on its two ends (its KKT
    condition), so a foreign plant can set the reference node's price whenever
    its node is in this pool. `el_prices` must already be filtered to one
    sub-scenario and contain columns ['T', 'Node', 'value'].
    """
    required_cols = {'T', 'Node', 'value'}
    if not required_cols.issubset(el_prices.columns):
        raise ValueError(f"el_prices must contain columns: {required_cols}")

    ref_series = (
        el_prices.loc[el_prices['Node'] == node, ['T', 'value']]
        .drop_duplicates(subset='T')
        .set_index('T')['value']
    )

    pool = {}
    for t, group in el_prices.groupby('T', sort=False):
        if t not in ref_series.index:
            continue
        ref_val = ref_series.loc[t]
        pool[t] = set(group.loc[(group['value'] - ref_val).abs() <= 1e-3, 'Node'].unique())

    return pool


# ===========================================================================
# 3. Dual extraction — one helper per opportunity-cost mechanism
# ===========================================================================

def determine_duals_p_t_s(model, constraint, sf=1.0, weight=1.0):
    """Storage water value: negated dual of the SOC balance, per (p, t, s).

    The value of one extra MWh in the store — the opportunity cost of using
    stored energy now instead of saving it (spec section 2.2).
    """
    if not hasattr(model, "dual"):
        raise AttributeError("Model is missing 'dual' suffix. Ensure the solver is configured to return duals.")

    return {
        (p, t, s): -dual * sf / weight
        for (p, t, s), con in constraint.items()
        if (dual := model.dual.get(con, None)) is not None
    }


def get_energy_limit_dual_dict(model, sub_scenarios, weight):
    """Biomass fuel-scarcity premium mu_V per (p, s): |dual| of the annual
    energy budget (energy_limit). Added on top of OPEX when the budget binds;
    zero (omitted) when slack. |.| because a binding upper energy bound can
    only raise the bid (spec section 2.1).
    """
    if not hasattr(model, "energy_limit") or not hasattr(model, "dual"):
        return {}

    sf = constraint_scaling["energy_limit"]
    adder = {}
    for (p, s), con in model.energy_limit.items():
        if s != sub_scenarios:
            continue
        dual = model.dual.get(con, None)
        if dual:  # skips both None and exact-zero (slack) duals
            adder[(p, s)] = abs(dual) * sf / weight

    return adder


def get_electrolyzer_dual(model, node, scenario):
    """Raw dual of the scalar constraint consume_tot_limit_{node}_electrolyzer_1_{scenario}.

    Raises KeyError if the constraint does not exist on the model.
    """
    cons_name = f"consume_tot_limit_{node}_electrolyzer_1_{scenario}"
    cons = getattr(model, cons_name, None)
    if cons is None:
        raise KeyError(f"Constraint '{cons_name}' not found in the model.")
    if hasattr(cons, 'body'):  # ConstraintData (scalar)
        return model.dual.get(cons, None)
    items = list(cons.values())  # container: assume single index
    if not items:
        raise KeyError(f"No instances found for constraint '{cons_name}'.")
    return model.dual.get(items[0], None)


def extract_all_electrolyzer_duals(model, node_list, scenario):
    """Hydrogen value per node: raw consume_tot_limit dual, 0 where absent.

    The caller applies sf('consume_tot_limit') / weight — the dual is already
    per MWh of electricity, so no efficiency factor is needed (spec 2.4).
    """
    duals = {}
    for node in node_list:
        try:
            duals[node] = get_electrolyzer_dual(model, node, scenario)
        except KeyError:
            duals[node] = 0
    return duals


def _firm_heat_premium(model, sub_scenarios, weight):
    """Firm-heat-mandate dual delta per (DH node, t): the extra value of heat
    from non-DSR sources when the mandate (inflexble_demandTh_share) binds.

    Not negated. Kept separate from lambda_heat so the heat value stays the
    transparent sum lambda + delta: a NEW binding heat-side constraint then
    surfaces as a Bid_Gap instead of being silently absorbed (unlike using the
    bundled coupling dual psi).
    """
    out = {}
    if not hasattr(model, "inflexble_demandTh_share") or not hasattr(model, "dual"):
        return out
    sf = constraint_scaling["inflexble_demandTh_share"]
    for (n, t, sc), con in model.inflexble_demandTh_share.items():
        if sc != sub_scenarios:
            continue
        d = model.dual.get(con, None)
        if d:  # skip None and exact-zero (slack mandate) duals
            out[(n, t)] = d * sf / weight
    return out


def build_dh_pricing_info(model, sub_scenarios, heat_prices, weight):
    """District-heating pricing inputs (spec section 2.3).

    Returns a dict with:
    - 'heat_price'        {(node_DH, t): lambda_heat}  dual of the thermal balance
    - 'firm_heat_premium' {(node_DH, t): delta}        firm-heat mandate dual
    - 'nodeDH'            {p: node_DH}
    - 'consumer_eff'      {p: eta}  resistive heaters + heat pumps (COP)
    - 'chp_p2h'           {p: r}    CHP power-to-heat ratio
    Heaters bid eta*(lambda+delta) - o_th; CHP asks o_elec - (lambda+delta)/r.
    All maps empty when DH is off.
    """
    info = {"heat_price": {}, "firm_heat_premium": {}, "nodeDH": {},
            "consumer_eff": {}, "chp_p2h": {}}

    if not hasattr(model, "PDH") or len(model.PDH) == 0:
        return info

    sf_thermal = constraint_scaling["energy_balancethermal"]
    if heat_prices is not None and len(heat_prices):
        hp = heat_prices
        if "Scenarios" in hp.columns:
            hp = hp.loc[hp["Scenarios"] == sub_scenarios]
        node_col = "NodeDH" if "NodeDH" in hp.columns else hp.columns[0]
        for node_dh, t, val in zip(hp[node_col], hp["T"], hp["value"]):
            info["heat_price"][(node_dh, t)] = val * sf_thermal / weight

    s = sub_scenarios
    for p in model.PDH:
        info["nodeDH"][p] = model.Map_plantDH_nodeDH[p]
    for p in model.PDH_resistive | model.PDH_heatpump:
        info["consumer_eff"][p] = PlantDH_data_remaining[p, "efficiency", s]
    for p in model.PDH_CHP:
        info["chp_p2h"][p] = PlantDH_data_remaining[p, "power_to_heat_ratio", s]

    info["firm_heat_premium"] = _firm_heat_premium(model, sub_scenarios, weight)

    return info


def build_building_hp_info(model, sub_scenarios, weight):
    """Flexible household heat pumps = building archetypes (BA) charging the
    building's thermal inertia; priced like DH heat pumps (spec section 2.6).

    Returns a dict with:
    - 'heat_value' {(ba, t): lambda_building}  negated building-SOC dual (sf=100!)
    - 'cop'        {(ba, t): COP}              time-varying
    - 'max_charge' {ba: BA_max_heating_capacity}  charge cap [MWh_el]
    Bid = COP * lambda_building; per-hour SOC, so no shift term needed.
    """
    info = {"heat_value": {}, "cop": {}, "max_charge": {}}
    if not hasattr(model, "BA_names") or len(model.BA_names) == 0:
        return info

    if hasattr(model, "building_heat_demand") and hasattr(model, "dual"):
        sf = constraint_scaling["building_heat_demand"]
        for (t, ba, sc), con in model.building_heat_demand.items():
            if sc != sub_scenarios:
                continue
            d = model.dual.get(con, None)
            if d is not None:
                info["heat_value"][(ba, t)] = -d * sf / weight

    for (t, ba, sc), v in model.COP.extract_values().items():
        if sc == sub_scenarios:
            info["cop"][(ba, t)] = v

    for (ba, sc), v in model.BA_max_heating_capacity.extract_values().items():
        if sc == sub_scenarios:
            info["max_charge"][ba] = v

    return info


def extract_duals_dsr_daily_balance(model, scenario_name):
    """DSR daily-balance dual nu per (p, day), negated: the midpoint of the
    prices the DSR shifts between (spec section 2.5). Raw (unscaled).
    """
    duals_dsr = {}
    if not hasattr(model, 'dsr_daily_balance'):
        return duals_dsr

    for (p, d, s) in model.dsr_daily_balance:
        if s != scenario_name:
            continue
        constraint = model.dsr_daily_balance[p, d, s]
        duals_dsr[(p, d)] = -model.dual.get(constraint, 0.0)

    return duals_dsr


def get_day_of_year_from_timestamp(timestamp):
    """'t_6554' -> day of year (24 h per day, starting at t_1)."""
    try:
        hour_of_year = int(timestamp.split("_")[1])
        return ((hour_of_year - 1) // 24) + 1
    except (IndexError, ValueError):
        raise ValueError(f"Invalid timestamp format: {timestamp}")


def build_dsr_watervalues(model, sub_scenarios, duals_dsr, weight):
    """DSR water value nu per (p, t, s), constant within each day.

    Keyed like the storage SOC duals so it merges into the same table and is
    priced by the identical bid formulas. `duals_dsr` is already negated.
    """
    out = {}
    if not hasattr(model, "P_dsr") or len(model.P_dsr) == 0:
        return out

    sf = constraint_scaling["dsr_daily_balance"]
    s = sub_scenarios
    day_of_t = {t: get_day_of_year_from_timestamp(t) for t in model.T}
    for p in model.P_dsr:
        for t, d in day_of_t.items():
            nu = duals_dsr.get((p, d))
            if nu:  # skip None and exact-zero (slack) duals
                out[(p, t, s)] = nu * sf / weight

    return out


def build_dsr_shift_values(model, sub_scenarios, weight):
    """DSR shift-limit premium S per (p, t, s): negated dual of
    energy_shift_limit_dsr_daily, i.e. HALF the price spread when the daily
    shift limit binds. nu is the midpoint, so the true bids are nu - S
    (charging) and nu + S + opex (reducing load); nu alone is off by exactly S.
    """
    out = {}
    if (not hasattr(model, "energy_shift_limit_dsr_daily")
            or not hasattr(model, "dual") or not hasattr(model, "P_dsr")):
        return out

    sf = constraint_scaling["energy_shift_limit_dsr_daily"]
    by_day = {}
    for (p, d, sc), con in model.energy_shift_limit_dsr_daily.items():
        if sc != sub_scenarios:
            continue
        dual = model.dual.get(con, None)
        if dual:  # skip None and exact-zero (slack limit) duals
            by_day[(p, d)] = -dual * sf / weight

    s = sub_scenarios
    day_of_t = {t: get_day_of_year_from_timestamp(t) for t in model.T}
    for p in model.P_dsr:
        for t, d in day_of_t.items():
            v = by_day.get((p, d))
            if v:
                out[(p, t, s)] = v

    return out


# ===========================================================================
# 4. Candidate pool — per-hour bids for every interior plant
# ===========================================================================

def build_candidate_plants_pool(
    scenario,
    sub_scenarios,
    pool,
    plant_node,
    gen,
    storage_charge,
    storage_charge_limit,
    pmp_max,
    avail_plant,
    V2G_charging_power_rate,
    storage_charge_eff_out,
    storage_charge_eff_in,
    gen_max,
    operation_slp,
    operation_slpTh,
    watervalue,
    electrolyzers_dual_dict,
    energy_limit_dual_dict,
    dh_info,
    hp_info,
    dsr_shift,
    BA_names,
):
    """Build the per-hour candidate pool (spec sections 2 and 3).

    A candidate is an INTERIOR plant: running/consuming > 1e-3 and below its
    cap by > 1e-3, AND (2026-10-14) between INTERIOR_REL_TOL and
    1 - INTERIOR_REL_TOL of its hourly capacity. The relative test removes
    barrier residuals (units a few kW above zero or below their cap, e.g. DSR
    at 0.002 of 3575 MW bidding above the price) that otherwise won the
    highest-bid rule. Only interior plants can be marginal. Each row carries the bid
    plus every ingredient in its own column (never bundled), so bids stay
    auditable term by term. Also written to
    output/<scenario>/price_setting_plant_pool_<sub>.csv.

    All Vars/Params are bulk-extracted once (extract_values) — per-tuple
    pyo.value() calls dominated runtime on multi-thousand-hour models.
    """
    gen_vals = gen.extract_values()
    storage_vals = storage_charge.extract_values()
    gen_max_vals = gen_max.extract_values()
    pmp_max_vals = pmp_max.extract_values()
    avail_vals = avail_plant.extract_values()
    op_slp_vals = operation_slp.extract_values()
    op_slpTh_vals = operation_slpTh.extract_values()
    eff_out_vals = storage_charge_eff_out.extract_values()
    eff_in_vals = storage_charge_eff_in.extract_values()
    V2G_vals = V2G_charging_power_rate.extract_values()
    # storage_charge_limit is a Param(within=Any) holding dicts — access directly.
    BA_set = set(BA_names)

    gen_data = []

    # -------- generation side --------
    for (p, t, s), gen_val in gen_vals.items():
        if s != sub_scenarios:
            continue
        if gen_val is None or gen_val <= 1e-3:
            continue
        if plant_node[p] not in pool.get(t, ()):
            continue

        gmax = gen_max_vals.get((p, s)) or 0.0
        max_gen_val = gmax * avail_vals[p, t, s]
        if (max_gen_val - gen_val) <= 1e-3:
            continue  # at the cap, not marginal
        if max_gen_val > 0 and (gen_val <= INTERIOR_REL_TOL * max_gen_val
                                or (max_gen_val - gen_val) <= INTERIOR_REL_TOL * max_gen_val):
            continue  # barrier residual at a bound (relative test, 2026-10-14)

        # Marginal cost = the linear slope operation_slp. The quadratic term
        # operation_qdr is commented out of the objective (components_common),
        # so it must NOT be added here; a phantom quadratic term made the bid
        # systematically exceed the price.
        op_slp = op_slp_vals.get((p, s), 0.0) or 0.0
        cost_type = Map_plant_tech_cost_component[Map_plant_tech[p]]
        marginal_cost = op_slp if cost_type in ("cap_op", "cap_op_energy") else 0.0

        # Energy-limited plants (biomass): OPEX + annual-budget premium mu_V.
        marginal_cost += energy_limit_dual_dict.get((p, s), 0.0)

        eff_out = eff_out_vals.get((p, s), 1.0)
        if eff_out is None:
            eff_out = 1.0
        eff_den = eff_out if eff_out else 1.0

        watervalue_val = watervalue.get((p, t, s), 0.0)
        heat_value = 0.0
        heat_eff = 0.0
        shift_value = dsr_shift.get((p, t, s), 0.0)

        r_p2h = dh_info["chp_p2h"].get(p)
        if r_p2h:
            # CHP: heat revenue lowers the ask, bid = o - (lambda+delta)/r.
            node = dh_info["nodeDH"].get(p)
            heat_value = (dh_info["heat_price"].get((node, t), 0.0)
                          + dh_info["firm_heat_premium"].get((node, t), 0.0))
            heat_eff = 1.0 / r_p2h
            bidding_price = marginal_cost - heat_eff * heat_value
        elif shift_value:
            # DSR reducing load asks the HIGH price of its day: nu + S + opex.
            bidding_price = watervalue_val / eff_den + marginal_cost + shift_value
        else:
            # Thermal / storage discharge: water value raises the ask,
            # floored at the operating cost.
            bidding_price = max(marginal_cost, watervalue_val / eff_den + marginal_cost)

        gen_data.append({
            "Technology": p,
            "Hour": t,
            "Scenario": s,
            "Sign": "gen",
            "Generation_MWh": gen_val,
            "Eff_out": eff_out,
            "Max Generation_MWh": max_gen_val,
            "Load_Factor": gen_val / max_gen_val if max_gen_val > 0 else 0.0,
            "Marginal Cost": marginal_cost,
            "Watervalue": watervalue_val,
            "Heat Value [CHF/MWh_th]": heat_value,
            "Heat COP [MWh_th/MWh_el]": heat_eff,
            "H2 Value": 0.0,
            "DSR Shift Value": shift_value,
            "Bidding price": bidding_price,
        })

    # -------- consumption side --------
    for (p, t, s), charge_val in storage_vals.items():
        if s != sub_scenarios:
            continue
        if charge_val is None or charge_val <= 1e-3:
            continue
        # Building archetypes without pricing info cannot be priced — skip
        # (should not happen when DH/BA switches are on).
        if p in BA_set and p not in hp_info["max_charge"]:
            continue
        if plant_node[p] not in pool.get(t, ()):
            continue

        # Consumption cap, by plant kind.
        if "electrolyzer" in p:
            flex_data = storage_charge_limit[p, s] if (p, s) in storage_charge_limit else None
            if flex_data is None:
                continue
            charge_max = flex_data['max_demand']
        elif "V2G_CH" in p:
            charge_max = V2G_vals.get((p, t, s), 0.0) or 0.0
        elif p in hp_info["max_charge"]:
            # No availability factor on BA charging (max_heating_capacity_Constraint).
            charge_max = hp_info["max_charge"][p]
        else:
            pm = pmp_max_vals.get((p, s)) or 0.0
            charge_max = pm * avail_vals[p, t, s]

        if (charge_max - charge_val) <= 1e-3:
            continue
        if charge_max > 0 and (charge_val <= INTERIOR_REL_TOL * charge_max
                               or (charge_max - charge_val) <= INTERIOR_REL_TOL * charge_max):
            continue  # barrier residual at a bound (relative test, 2026-10-14)

        op_cost = op_slp_vals.get((p, s)) or 0.0

        if (p, t, s) in watervalue:
            watervalue_val = watervalue[p, t, s]
            eff_out = eff_out_vals.get((p, s), 1.0)
            if eff_out is None:
                eff_out = 1.0
            # charging efficiency eta_in (2026-10-15; was eta_out, which differs
            # only for CH00_hydrogen: 0.7547 vs 0.53)
            eff_in = eff_in_vals.get((p, s), 1.0)
            if eff_in is None:
                eff_in = 1.0
        else:
            watervalue_val = 0.0
            eff_out = 1.0
            eff_in = 1.0
        eff_den = eff_out if eff_out else 1.0

        heat_value = 0.0
        heat_eff = 0.0
        h2_value = 0.0
        shift_value = dsr_shift.get((p, t, s), 0.0)

        eta_dh = dh_info["consumer_eff"].get(p)
        if eta_dh is not None:
            # DH heater (resistive / heat pump): WTP = eta*(lambda+delta) - o_th.
            node = dh_info["nodeDH"].get(p)
            heat_value = (dh_info["heat_price"].get((node, t), 0.0)
                          + dh_info["firm_heat_premium"].get((node, t), 0.0))
            heat_eff = eta_dh
            op_cost = op_slpTh_vals.get((p, s), 0.0) or 0.0
            watervalue_val = 0.0
            eff_out = 1.0
            bidding_price = heat_eff * heat_value - op_cost
        elif p in hp_info["heat_value"] or p in hp_info["max_charge"]:
            # Household heat pump (BA): WTP = COP * lambda_building.
            heat_value = hp_info["heat_value"].get((p, t), 0.0)
            heat_eff = hp_info["cop"].get((p, t), 0.0)
            op_cost = 0.0
            watervalue_val = 0.0
            eff_out = 1.0
            bidding_price = heat_eff * heat_value - op_cost
        elif "electrolyzer" in p:
            # WTP = hydrogen value (already per MWh_el) - opex.
            h2_value = electrolyzers_dual_dict.get(plant_node[p], 0.0) or 0.0
            bidding_price = h2_value - op_cost
        elif shift_value:
            # DSR adding load pays the LOW price of its day: nu - S.
            op_cost = 0.0
            bidding_price = watervalue_val - shift_value
        else:
            # Storage / V2G charging: WTP = watervalue * eta_in (one MWh
            # bought adds eta_in MWh to the store). The operating cost sits on
            # the DISCHARGE side, so it is NOT a floor here — flooring wrongly
            # over-bid the true setters in near-zero hours.
            op_cost = 0.0
            bidding_price = watervalue_val * eff_in

        gen_data.append({
            "Technology": p,
            "Hour": t,
            "Scenario": s,
            "Sign": "con",
            "Generation_MWh": charge_val,
            "Eff_out": eff_out,
            "Max Generation_MWh": charge_max,
            "Load_Factor": charge_val / charge_max if charge_max > 0 else 0.0,
            "Marginal Cost": op_cost,
            "Watervalue": watervalue_val,
            "Heat Value [CHF/MWh_th]": heat_value,
            "Heat COP [MWh_th/MWh_el]": heat_eff,
            "H2 Value": h2_value,
            "DSR Shift Value": shift_value,
            "Bidding price": bidding_price,
        })

    df_gen = pd.DataFrame(gen_data)

    output_path = Path("output") / scenario / f"price_setting_plant_pool_{sub_scenarios}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_gen.to_csv(output_path, index=False)

    return df_gen


# ===========================================================================
# 5. Classification and co-marginal tie-break
# ===========================================================================
# Every candidate maps to a ROLE class (what its bid rests on) and a LOCATION
# tag (CH / abroad; descriptive only, never influences the pick).
#
# Tie-break (2026-10-14), following Geis et al. (2026, Energy Economics 157,
# 109213, Sec. 2 and App. A.1.6). The clearing price is NOT used to pick the
# setter; it only validates the pick afterwards (Bid_Gap = price - chosen bid):
#   1. co-marginal = interior candidates whose bid is within TIE_TOL of the
#      highest interior bid (barrier without crossover leaves tied bids up to
#      ~0.007 CHF/MWh apart, so the former 1e-4 split genuine ties); an hour
#      whose highest bid is below ZERO_BID_TOL is a zero-price hour;
#   2. supply first: if any supplier (Sign "gen") is co-marginal, demand
#      candidates (Sign "con") are dropped. Exception: with a fixed hydrogen
#      price the electrolyzer bids an exogenous value and counts as a supplier;
#   3. among the rest, the LEAST FLEXIBLE technology wins, flexibility measured
#      by the standard deviation of the technology's bids. The order below is
#      fixed for all runs; it was derived from the interior candidates of
#      h2fix78_2035 and h2fix78_2050 (std in CHF/MWh in brackets). Technologies
#      without candidates there are placed by the same reasoning.
#   4. within a technology the first (highest-bid) row wins; its location is
#      arbitrary and must not be interpreted.

INTERIOR_REL_TOL = 0.005      # candidate if 0.5 % < output/capacity < 99.5 %
TIE_TOL = 0.01                # CHF/MWh below the highest interior bid
ZERO_BID_TOL = 0.01           # highest interior bid below this -> "Zero price"

PRICE_SETTER_ORDER = [
    ("Nuclear",          "conventional thermal"),  # 0.0
    ("Hardcoal",         "conventional thermal"),  # 0.0 (base runs)
    ("Oil",              "conventional thermal"),  # constant fuel cost, no candidates
    ("CCGTCCS",          "conventional thermal"),  # 0.0
    ("Other",            "conventional thermal"),  # 0.0
    ("Electrolyzer",     "sector coupling"),       # 0.0 with a fixed H2 price
    ("EV",               "sector coupling"),       # 0.0 (bids 0, zero-price hours only)
    ("Gas",              "conventional thermal"),  # 2.0
    ("Biomass",          "biomass"),               # 7.9
    ("CHP",              "chp"),                   # no candidates; heat-credit bids vary (Geis A.1.6)
    ("Reservoir hydro",  "hydro"),                 # 10.5
    ("Pumped hydro",     "hydro"),                 # 12.5
    ("Battery",          "electric storage"),      # 18.0
    ("V2G",              "electric storage"),      # 18.4
    ("DSR",              "sector coupling"),       # 19.6
    ("Heat pump",        "sector coupling"),       # 19.9
    ("Resistive heater", "sector coupling"),       # 21.8
]
_ROLE_RANK = {role: i for i, (role, _tier) in enumerate(PRICE_SETTER_ORDER)}
_ROLE_TIER = {role: tier for role, tier in PRICE_SETTER_ORDER}
_UNCLASSIFIED_RANK = len(PRICE_SETTER_ORDER)

# CH-only assets that do not carry a "CH0x_" node prefix.
_DOMESTIC_SPECIAL = {"large_psp", "medium_reservior", "small_reservior", "EV_CH", "V2G_CH"}


def _role_of(plant_id):
    """Raw plant id -> role class, or None if unknown.

    Substrings are tested most-specific first (e.g. CHP before HP, CCGTCCS
    before gas) so composite names classify correctly.
    """
    pid = str(plant_id)
    if "CHP" in pid:
        return "CHP"
    if "resistive" in pid:
        return "Resistive heater"
    if "HPNew" in pid or "HPG" in pid or pid.endswith("[MWh]"):
        return "Heat pump"          # electric heat pumps: DH, industrial, buildings
    if "nuclear" in pid:
        return "Nuclear"
    if "hardcoal" in pid:
        return "Hardcoal"
    if "CCGTCCS" in pid:
        return "CCGTCCS"
    if "biomass" in pid:
        return "Biomass"
    if "electrolyzer" in pid:
        return "Electrolyzer"
    if "psp" in pid:
        return "Pumped hydro"
    if "dam" in pid or "reservior" in pid or "reservoir" in pid:
        return "Reservoir hydro"
    if "V2G" in pid:
        return "V2G"
    if "battery" in pid:
        return "Battery"
    if "dsr" in pid:
        return "DSR"
    if "oil" in pid:
        return "Oil"
    if "_gas" in pid:
        return "Gas"
    if "other" in pid:
        return "Other"
    if "EV" in pid:
        return "EV"
    return None


def _is_domestic(plant_id):
    """True if the plant belongs to a Swiss (CH) node."""
    pid = str(plant_id)
    if pid.startswith("CH0"):
        return True
    if pid.startswith(("DH_", "ILHT_", "ILLT_", "minergie_")):
        return True
    if pid.endswith("[MWh]"):       # building heating archetypes
        return True
    return pid in _DOMESTIC_SPECIAL


def replace_with_dict(value: str) -> str:
    """Aggregate a raw plant id into a "<role class> <location>" label.
    Unclassified ids are returned unchanged."""
    role = _role_of(value)
    if role is None:
        return value
    location = "CH" if _is_domestic(value) else "abroad"
    return f"{role} {location}"


def _is_supply(sign, plant_id, electrolyzer_as_supply):
    """Supply side for the supply-first rule: generation rows, plus the
    electrolyzer when it bids a fixed (exogenous) hydrogen price."""
    if sign == "gen":
        return True
    return bool(electrolyzer_as_supply) and "electrolyzer" in str(plant_id)


def _select_setter(sorted_plants, electrolyzer_as_supply=False, tie_tol=TIE_TOL):
    """Pick the setter from candidates pre-sorted by descending bid, without
    looking at the clearing price.

    Co-marginal set = candidates whose bid is within `tie_tol` of the highest
    bid. Then supply first (see _is_supply) and, among the remaining, the role
    that ranks earliest in PRICE_SETTER_ORDER (lowest bid variance) wins;
    within it the first, i.e. highest-bid, row.

    Returns (chosen_row, setter_tier, n_co_marginal).
    """
    top_bid = sorted_plants.iloc[0]["Bidding price"]
    co_marginal = sorted_plants[sorted_plants["Bidding price"] >= top_bid - tie_tol]
    n_co = int(len(co_marginal))

    supply = [
        _is_supply(sg, tech, electrolyzer_as_supply)
        for sg, tech in zip(co_marginal["Sign"], co_marginal["Technology"])
    ]
    selectable = co_marginal[supply] if any(supply) else co_marginal

    ranks = selectable["Technology"].map(
        lambda p: _ROLE_RANK.get(_role_of(p), _UNCLASSIFIED_RANK)
    )
    pos = int(ranks.reset_index(drop=True).idxmin())  # first (= highest bid) among min-rank
    chosen = selectable.iloc[pos]
    tier = _ROLE_TIER.get(_role_of(chosen["Technology"]), "unclassified")
    return chosen, tier, n_co


# ===========================================================================
# 6. Hourly selection
# ===========================================================================

def pick_plants(pool_plants, el_prices, sub_scenarios, scenario, weight, node,
                electrolyzer_as_supply=False):
    """Select THE price-setting plant per hour from the candidate pool.

    Highest-bid-wins: among interior candidates the marginal plant is the most
    expensive one still running, so the top bid equals the price. Do NOT snap
    to the closest bid — Bid_Gap = Actual Price - Bidding price is the honest
    diagnostic that flags every missing or mis-scaled mechanism.

    Returns (per-hour setter DataFrame, technology count DataFrame).
    """
    price_lookup = (
        el_prices.loc[el_prices["Node"] == node, ["T", "value"]]
        .drop_duplicates(subset="T")
        .set_index("T")["value"]
        .to_dict()
    )
    all_hours = list(price_lookup.keys())

    if pool_plants.empty:
        pool_by_hour = {}
    else:
        pool_by_hour = {h: g for h, g in pool_plants.groupby("Hour", sort=False)}

    sf_eb = constraint_scaling["energy_balance"]

    price_setting_plants = []

    for t in all_hours:
        economic_price = price_lookup[t] * sf_eb / weight

        # Used when there are no candidates or when the price is ~0.
        fallback = {
            "Technology": "Zero price",
            "Hour": t,
            "Scenario": sub_scenarios,
            "Sign": "gen",
            "Marginal Cost": 0.0,
            "Watervalue": 0.0,
            "Heat Value [CHF/MWh_th]": 0.0,
            "Heat COP [MWh_th/MWh_el]": 0.0,
            "H2 Value": 0.0,
            "DSR Shift Value": 0.0,
            "Eff_out": 1.0,
            "Generation_MWh": 0.0,
            "Max Generation_MWh": 0.0,
            "Load_Factor": 0.0,
            "Bidding price": 0.0,
            "Actual Price": economic_price,
            "N_Candidates": 0,
            "N_CoMarginal": 0,
            "Setter_Basis": "zero price",
        }

        hour_plants = pool_by_hour.get(t)
        if hour_plants is None or hour_plants.empty:
            price_setting_plants.append(fallback)
            continue

        sorted_plants = hour_plants.sort_values("Bidding price", ascending=False)
        n = len(sorted_plants)

        # Price-free selection (2026-10-14): the zero-price test and the pick
        # use the bids only; economic_price is kept for the Bid_Gap check.
        if sorted_plants.iloc[0]["Bidding price"] < ZERO_BID_TOL:
            selected = dict(fallback)
            selected["N_Candidates"] = n
        else:
            top_row, setter_basis, n_co = _select_setter(
                sorted_plants, electrolyzer_as_supply=electrolyzer_as_supply)
            selected = {
                "Technology": top_row["Technology"],
                "Hour": t,
                "Scenario": sub_scenarios,
                "Sign": top_row["Sign"],
                "Marginal Cost": top_row["Marginal Cost"],
                "Watervalue": top_row["Watervalue"],
                "Heat Value [CHF/MWh_th]": top_row.get("Heat Value [CHF/MWh_th]", 0.0),
                "Heat COP [MWh_th/MWh_el]": top_row.get("Heat COP [MWh_th/MWh_el]", 0.0),
                "H2 Value": top_row.get("H2 Value", 0.0),
                "DSR Shift Value": top_row.get("DSR Shift Value", 0.0),
                "Eff_out": top_row["Eff_out"],
                "Generation_MWh": top_row.get("Generation_MWh", 0.0),
                "Max Generation_MWh": top_row.get("Max Generation_MWh", 0.0),
                "Load_Factor": top_row.get("Load_Factor", 0.0),
                "Bidding price": top_row["Bidding price"],
                "Actual Price": economic_price,
                "N_Candidates": n,
                "N_CoMarginal": n_co,
                "Setter_Basis": setter_basis,
            }

        price_setting_plants.append(selected)

    df_price_setting = pd.DataFrame(price_setting_plants)

    # Signed gap; positive = the actual price exceeds every candidate bid
    # (likely mis-attribution). Snap <1e-9 float round-off to exact zero.
    df_price_setting["Bid_Gap"] = (
        df_price_setting["Actual Price"] - df_price_setting["Bidding price"]
    )
    df_price_setting["Bid_Gap"] = df_price_setting["Bid_Gap"].where(
        df_price_setting["Bid_Gap"].abs() > 1e-9, 0.0
    )

    # Keep the raw plant id alongside the aggregated technology label.
    df_price_setting["Technology_Raw"] = df_price_setting["Technology"]
    df_price_setting["Technology"] = df_price_setting["Technology"].apply(replace_with_dict)

    counted_technologies = count_technologies(df_price_setting, scenario, sub_scenarios)

    return df_price_setting, counted_technologies


def count_technologies(df, scenario, subscenario):
    """Count setter occurrences per technology label, excluding hours with
    |Bid_Gap| >= 0.1 (counted separately as 'possibly misassigned')."""
    if "Technology" not in df.columns:
        raise ValueError("The DataFrame must contain a 'Technology' column.")
    if "Actual Price" not in df.columns or "Bidding price" not in df.columns:
        raise ValueError("Missing 'Actual Price' or 'Bidding price' column.")

    mismatch_mask = (df["Actual Price"] - df["Bidding price"]).abs() >= 0.1
    num_misassigned = mismatch_mask.sum()

    vc = df[~mismatch_mask]["Technology"].value_counts()
    result_df = pd.DataFrame({
        "Technology": vc.index.to_list(),
        "Count": vc.to_list(),
        "Scenario": scenario,
        "SubScenario": subscenario,
    })

    if num_misassigned > 0:
        result_df = pd.concat([
            result_df,
            pd.DataFrame([{
                "Technology": "possibly misassigned",
                "Count": num_misassigned,
                "Scenario": scenario,
                "SubScenario": subscenario,
            }]),
        ], ignore_index=True)

    return result_df


def count_technologies_comarginal(df_pool, df_hourly, scenario, subscenario,
                                  co_marginal_tol=1e-4):
    """Co-marginality-aware attribution, companion to count_technologies.

    Winner-takes-all counts hide that in most hours SEVERAL candidates tie
    at the clearing price (duals equalize across every uncongested border);
    the role-rank tie-break then decides, and between same-role candidates
    (e.g. a CH dam and an AT dam) the pick is effectively arbitrary
    (location never enters the tie-break). This function therefore reports,
    per technology label, two robustness metrics alongside the winner count:

      Hours_present     number of hours in which the label appears among the
                        co-marginal candidates (bid within TIE_TOL of the
                        highest bid; same definition as _select_setter)
      Share_frac_role   sum over hours of 1/m, m = number of DISTINCT labels
                        in the co-marginal set: every tied hour is split
                        equally among the role classes present. This is the
                        headline robustness metric -- it is invariant to how
                        many UNITS a role happens to bid with.
      Share_frac_unit   sum over hours of (label's co-marginal candidates/k),
                        k = co-marginal pool size. Unit-count weighted;
                        biased toward roles with many pool units (e.g. the
                        dozens of heat-pump building archetypes), reported
                        for transparency only.

    Both fractional columns sum to the number of hours over all labels.
    Zero-price hours and |Bid_Gap| >= 0.1 hours are attributed to
    'Zero price' / 'possibly misassigned' wholesale, matching
    count_technologies.
    """
    by_hour = df_hourly.drop_duplicates("Hour").set_index("Hour")
    zero_hours = set(by_hour.index[by_hour["Technology"].eq("Zero price")])
    mism_hours = set(by_hour.index[
        (by_hour["Actual Price"] - by_hour["Bidding price"]).abs() >= 0.1
    ]) - zero_hours

    presence, frac_role, frac_unit = {}, {}, {}

    def add(label, pres, f_role, f_unit):
        presence[label] = presence.get(label, 0) + pres
        frac_role[label] = frac_role.get(label, 0.0) + f_role
        frac_unit[label] = frac_unit.get(label, 0.0) + f_unit

    pool_ok = df_pool[~df_pool["Hour"].isin(zero_hours | mism_hours)]
    for _, grp in pool_ok.groupby("Hour", sort=False):
        # same co-marginal definition as _select_setter (price-free)
        top = grp["Bidding price"].max()
        com = grp[grp["Bidding price"] >= top - TIE_TOL]
        k = len(com)
        vc = com["Technology"].map(replace_with_dict).value_counts()
        m = len(vc)
        for label, cnt in vc.items():
            add(label, 1, 1.0 / m, cnt / k)
    for _ in zero_hours:
        add("Zero price", 1, 1.0, 1.0)
    for _ in mism_hours:
        add("possibly misassigned", 1, 1.0, 1.0)

    out = pd.DataFrame({
        "Technology": list(presence.keys()),
        "Hours_present": [presence[k] for k in presence],
        "Share_frac_role": [round(frac_role[k], 2) for k in presence],
        "Share_frac_unit": [round(frac_unit[k], 2) for k in presence],
    }).sort_values("Share_frac_role", ascending=False)
    out["Scenario"] = scenario
    out["SubScenario"] = subscenario
    return out.reset_index(drop=True)


# ===========================================================================
# 7. Aggregation and export (entry point, called from core.py)
# ===========================================================================

def aggregate_price_setting_data(scenario_name, sub_scenarios_list, model, dual_values_dict):
    """Run the attribution for every sub-scenario and write the results.

    Writes per scenario:
    - price_setting_plants.csv        hourly setter (N_Candidates, N_CoMarginal,
                                      Setter_Basis, Bid_Gap, raw plant id, ...)
    - price_setting_plants_count.csv  aggregated technology counts
    - price_setting_plants_count_comarginal.csv  co-marginality-aware counts
      (Hours_present, Share_fractional; see count_technologies_comarginal) --
      the robustness companion to the winner-takes-all count file
    - price_setting_plant_pool_<sub>.csv  full candidate pool per hour, enriched
      with per-hour context (Chosen_Tech, Chosen_Bid, Actual_Price, Bid_Gap,
      Is_Mismatch). Filter on Is_Mismatch to inspect mis-attributed hours —
      this file replaces the former mismatch-diagnostics CSV.
    """
    all_price_setting = []
    all_counts = pd.DataFrame(columns=["Technology", "Count", "Scenario", "SubScenario"])
    all_counts_com = []

    for sub_scen in sub_scenarios_list:
        price_setting_plants, price_setting_plants_counted = determine_hourly_price_setter(
            scenario_name, sub_scen, model, dual_values_dict['energy_balance'],
            heat_prices=dual_values_dict.get('energy_balancethermal'),
        )

        df_hourly = pd.DataFrame(price_setting_plants)
        df_hourly["Scenario"] = scenario_name
        df_hourly["SubScenario"] = sub_scen
        all_price_setting.append(df_hourly)

        all_counts = pd.concat([all_counts, price_setting_plants_counted], ignore_index=True)

        # Enrich the pool CSV written by build_candidate_plants_pool with the
        # per-hour outcome, so it doubles as the mismatch diagnostic.
        pool_path = Path("output") / scenario_name / f"price_setting_plant_pool_{sub_scen}.csv"
        if pool_path.exists() and "Bid_Gap" in df_hourly.columns:
            df_pool = pd.read_csv(pool_path)
            by_hour = df_hourly.drop_duplicates("Hour").set_index("Hour")
            df_pool["Actual_Price"] = df_pool["Hour"].map(by_hour["Actual Price"])
            df_pool["Chosen_Tech"] = df_pool["Hour"].map(by_hour["Technology_Raw"])
            df_pool["Chosen_Bid"] = df_pool["Hour"].map(by_hour["Bidding price"])
            df_pool["Setter_Basis"] = df_pool["Hour"].map(by_hour["Setter_Basis"])
            df_pool["N_CoMarginal"] = df_pool["Hour"].map(by_hour["N_CoMarginal"])
            df_pool["Bid_Gap"] = df_pool["Hour"].map(by_hour["Bid_Gap"])
            df_pool["Is_Mismatch"] = df_pool["Bid_Gap"].abs() >= 0.1
            df_pool.to_csv(pool_path, index=False)

            # Co-marginality-aware counts (presence + fractional attribution)
            all_counts_com.append(count_technologies_comarginal(
                df_pool, df_hourly, scenario_name, sub_scen))

    df_price_setting_all = pd.concat(all_price_setting, ignore_index=True)

    output_dir = Path("output") / scenario_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path_plants = output_dir / "price_setting_plants.csv"
    output_path_plant_count = output_dir / "price_setting_plants_count.csv"

    df_price_setting_all.to_csv(output_path_plants, index=False)
    all_counts.to_csv(output_path_plant_count, index=False)
    print(f"Saved: {output_path_plants}")
    print(f"Saved: {output_path_plant_count}")

    if all_counts_com:
        output_path_com = output_dir / "price_setting_plants_count_comarginal.csv"
        pd.concat(all_counts_com, ignore_index=True).to_csv(
            output_path_com, index=False)
        print(f"Saved: {output_path_com}")

    return df_price_setting_all, all_counts
