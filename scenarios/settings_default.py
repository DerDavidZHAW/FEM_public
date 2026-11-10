seetings_default_param = {
    "DUALS_EXPORT_ALL": False,
    "consumer_based_on_tariff": False,
    "consumer_connection_limit": False,
    "solver_name": "gurobi",
    "flex_dem_active_for_consumer": True,
    "share_of_flexibly_charging_EV": 0.5,  # Share of total EV consumption that is flexible (0-1). The remaining (1-share) is inflexible.
    "V2G_share_of_flexibly_charging_EV": 0.5,
    "switch_flexible_EV": True,  # If False: all EV demand becomes inflexible, CH00_EV_flex plant is not created, and V2G is implicitly off too.
    "switch_V2G": True,  # If False: V2G_CH plant + V2G constraints are skipped; V2G fleet's energy folds into CH00_EV_flex (flexible non-V2G).
    "switch_flexible_HP": True,  # If False: all household HP demand becomes inflexible; BA archetype plants/sets/constraints are not created.
    "switch_electric_DSR": True,  # If False: all "*_dsr" plants are dropped from Plant_list at import; P_dsr / DSR constraints stay empty. No demand fallback needed (DSR is additive, not a carved-out share).
    "switch_flexible_electrolyzer": True,  # If False: electrolyzer plants + consume_tot_limit constraints are skipped; the same annual energy (post electrolyzer_demand_reduction_coefficient) is added as a FIXED schedule to the inflex side via Electrolyzer_inflexible_demand, valley-filling the lowest-inflex-demand hours per node.
    "switch_DH": True,  # If False: entire DH sector is removed (no NodeDH/PDH sets, no *Th constraints/Vars built). The thermal demand is aggregated over all DH regions, divided by COP=3 (air heat pump assumption), and added hour-by-hour to the inflex base demand at CH00.
    "switch_storage": True,  # If False: every plant with tech in tech_store_list (battery, hydrogen, psp_open, psp_close, v2g, dam, TES, TTES_medium, PTES_large) is filtered out and replaced by a {node}_storage_replacement virtual generator at 300 CHF/MWh, 1 TW per node — keeps the LP feasible while removing all SoC/storage constraints (big speedup for diagnostic runs).
    "switch_biomass": True,  # If False: biomass plants are filtered out; their annual energy budget is preserved as a FIXED generation schedule placed on the highest-residual-demand hours per node (Biomass_inflexible_generation Param on LHS of energy_balance).
    "CH_only": False,
    "neighbor_countries_for_CH_only_mode": ["DE00", "AT00", "FR00", "IT00"],
    "neighbor_price_scenario_for_CH_only_mode": "default",
    "t_start": 6553,
    "t_end": 6552,
    "consumer_start": 1,
    "consumer_end": 300,
    "opt_mode": "core",
    "consumers_representing": 8230,
    "reduce_DH_demand_by_[MWh]": 0.0,
    "DH_demand_adjustment_file": False,  # False (off) or a CSV filename in input/demand/adjustments/ (PRD #43)
    "slack_soc": False,
    "single_large_battery": True,
    "winter_limit": {"mode": False, "window": [6553, 2184], "energy_MWh": 5 * 1000000},
    "rep_hydro_plants": True,
    "allow_investment": True,
    "merge_some_countries": True,
    "target_merge_countries": ["IT", "LU"],
    "minimum_RES_target_CH": False,
    "cost_op_match_nexuse": False,
    "RES_CH_coefficient": 1,
    "PVRF_CH_coefficient": 1,
    "Windon_CH_coefficient": 1,
    "limit_fuel_import_CH": False,
    "limited_fuels_import_CH_list": ["resmethane", "fossilmethane", ],
    "ror_annual_TWh" : False,
    "hydro_inflow_TWh" : False,
    "pump_capacity_GW" : False,
    "adding_hydro_storage_cap_TWh" : False,
    "hydro_clusters": "legacy",  # "legacy" = PECD 3-plant CH representation (default); int 4..20 = WASTA cluster representation from input/hydro_WATSA (see scen CSV row)
    "reduce_inflex_demand_by_[MWh]" : 0,
    "solver_barrier_only": False,  # True -> Gurobi "method=2 crossover=0": pure barrier, central-path duals, no vertex basis. Robust and much faster on degenerate instances where crossover cycles (2050_wy1995_12hydro, 2026-08-05). Keep CONSISTENT across runs that are compared to each other.
    "lost_load_cost_mode": "single_step",  # 'single_step' (default) or 'multi_step_v1' for stepwise lost load cost
    "flexible_household_heatpump_share" : 0.5,
    "heat_flexibility_Kelvin": 0.5,  # Degree of flexibility for heat pumps (in Kelvin)
    "share_of_available_charging_capacity_for_V2G": 0.7,
    "NodeDH_list": ['DH_medium', 'DH_Mittelland', 'DH_Alpen', 'DH_Jura', 'DH_Voralpen', 'ILLT_Mittelland', 'ILLT_Alpen', 'ILLT_Jura', 'ILLT_Voralpen', 'ILLT_Alpensuedseite', 'ILHT_Mittelland', 'ILHT_Alpen', 'ILHT_Jura', 'ILHT_Voralpen', 'ILHT_Alpensuedseite',],
    "storage_to_charge_ratio_days": 7,
    "battery_cost_factor": 1,
    "battery_investment_nodes_in_addition_to_CH": "",
    "reduce_BE_FR_day_nine_and_ten_demand_to_percent": 1.0,
    "resistive_heater_investment_cap_MW_total": False,  # MW limit for total resistive heater investment across all nodes
    "electrolyzer_demand_reduction_coefficient": 1,
    "h2_steps": False,  # W8 (2026-08-11): True -> hybrid stepwise hydrogen offtake demand from input/HydrogenDemand/: consume_tot_limit keeps only the must-serve share (steps with must_serve=1) as forced annual energy; the rest becomes elastic annual steps E_h2step in [0, width] valued at eta x (WTP + node premium) in the objective (self-curtail when power prices exceed the WTP). electrolyzer_demand_reduction_coefficient is IGNORED in steps mode. Requires switch_flexible_electrolyzer=True.
    "h2_demand_scenario": "central",  # rung selector for hydrogen_demand_scenarios.csv: a role name ("central") or an explicit pair "<DEFAULT_rung>+<CH00_rung>", e.g. "tyndp24_ga+ep2050_zba". Only used when h2_steps=True.
    "h2_fixed_price": None,  # 2026-10-13: None = off. Float = uniform fixed hydrogen price in CHF/MWh_H2 (LHV, CHF = EUR 1:1) for ALL electrolyzer nodes: no must-serve energy, electrolyzers bid h2_fixed_price_eta x h2_fixed_price (CHF/MWh_el) in every hour and the served volume is endogenous; hourly capacity sized as in legacy (annual energy after electrolyzer_demand_reduction_coefficient / electrolyzer_flh_target). Results in h2_steps_result.csv. Mutually exclusive with h2_steps; requires switch_flexible_electrolyzer=True.
    "h2_fixed_price_eta": 0.68,  # electrolysis efficiency MWh_H2/MWh_el for h2_fixed_price (same as hydrogen_demand_steps.csv)
    "electrolyzer_flh_target": 3000,  # full-load-hour sizing convention: hourly electrolyzer capacity = annual total (steps: TOTAL width incl. elastic) / this. 3000 = legacy hardcoded value (was in read_electrolyzer_data); TYNDP24 implies ~4700-5800, Wallinger CH ~3300-4800.
    "NTC_CH_ratio": 1,
    "RES_EU_coefficient": 1.1,
    "weather_year": 1995,
    "run_year": 2050,
    "high_resolution_PV": False,   # if True, replace 7 CHxx_pvrf investment candidates with per-plant Nexus-E rooftop PV. Reads input/RES_nexuse/PV/<weather_year>/. EMHIRES pvrf still loaded for preexisting (EP2050+) capacity.
    "eu_policy": "GA",
    "ch_policy": "ZBA",
    "Node_list_setting": [
        "CH00",
        "IT00",
        "DE00",
        # "DEKF",  # ?
        "FR00",
        "AT00",
        "DKE1",  # ?
        "DKW1",  # ?
        # "DKKF", # ?
        "BE00",
        "CZ00",
        "ES00",
        "UK00",
        "HU00",
        "LU00",
        "NL00",
        "PL00",
        "PT00",
        "SI00",
        "SK00",
        "HR00",
        "SE01",
        "SE02",
        "SE03",
        "SE04",
        "NON1",
        "NOM1",
        "NOS0",
    ],
}
