import utils.dic_list_expansion as dle
from data_prep.definitions_TYNDP import *
from data_prep.definitions_common import (
    Consumer_list,
    Map_consumer_node,
    Infeed_consumers,
    Plant_list,
    Map_consumer_plant,
    Map_plant_tech,
    Map_plant_node,
    Plant_capacity_gen,
    Plant_capacity_pmp,
    Plant_capacity_strg,
    Map_eff_in_plant,
    Map_eff_out_plant,
    Map_plant_startcondition,
    Data_plant_flex_d_within_window,
    Plant_investment_RES_CH_list,
    cost_data_inv_gen_int,
    cost_data_inv_gen_slp,
    cost_data_opr_int,
    cost_data_opr_slp,
    op_cost_n_tech_calibration,
    gen_max_RES_pre_existing_no_NETFLEX,
    Map_infeedplant_tech,
    Map_infeedplant_node,
    Infeedplant_list,
    Plant_investment_RES_CH_data,
    Plant_investment_non_RES_CH_list,
    P_list_fuelswitching_plants,
    cost_data_inv_e_slp,
    PlantDH_list,
    Map_plantDH_nodeEl,
    Map_plantDH_nodeDH,
    Map_plantDH_tech,
    PlantDH_capacity,
    PlantDH_data_remaining,
    Map_nodeDH_plantDH,
    EV_weekly_energy_consumption_data,
    EV_charging_power_rate,
    Fuel_limits_data,
    BA_el_con,
    BA_th_con,
    BA_th_lim,
    COP,
    BA_names,
    PlantDH_investment_STES_list,
    Plant_investment_data_STES,
    BA_max_heating_capacity,
    cost_data_inv_fuel_storage_slp, 
    Outflow_data,
    V2G_charging_power_rate,
    V2G_storage_capacity,
    Plant_outflow_list,
    storage_to_charge_ratio,
    cost_data_inv_discharge_slp,
    flexible_household_heatpump_share,
    KVAinfeed,
    emission_factor_per_MWh,
)

from data_prep.definitions_common import (
    scenario_name,
    Inflow_data,
    Plant_inflow_list,
    LineATC_list,
    Map_line_node,
    ATC_exportlimit,
    ATC_importlimit,
    Demand_data,
    Map_node_plant,
    Map_node_consumer,
    Map_node_exportinglineATC,
    Map_node_importinglineATC,
    Avail_plant,
    Demand_data_TYNDP,
    Infeed_RES_TYNDP,
    Data_plant_energy_limited,
    DemandDH_data,
    lost_load_cost,
    Line_trade_price,
    EV_inflexible_demand_data,
    HP_inflexible_demand_data,
    Electrolyzer_inflexible_demand_data,
    DH_inflexible_demand_data,
    Biomass_inflexible_generation_data,
)
from model.mappings import (
    Map_TYNDPscenario_short_longspaced,
    Map_TYNDPscenario_short_long,
    Map_node_country,
    Map_Prognosscenario_short_long,
)
from model.structural_parameters import (
    tech_infeed_all_list,
    tech_limited_energy_list,
    Map_tech_startcondition,
    tech_limited_energy_CH_list,
)
from model.data_import_fcns import *
from model.read_settings import read_scenario_settings
import utils.data_import_costs as data_costs
import input.cost_operation_invest_data as operation_data
import pandas as pd
import os

# Pre-patch the cost-component lookup tables so the auto-import in
# data_import_costs.create_tech_cost_dict() can process the synthetic
# "storage_replacement" tech (declared in structural_parameters.py) without
# error. The plant is not investable, so 0 everywhere is a no-op; the actual
# 300 CHF/MWh operation cost is injected later in the switch_storage=False
# branch. We populate every cost_component subdict with a year→0 mapping so
# the buggy default-to-{} fallback in get_cost_component (which would do
# {} / efficiency at line ~51) never fires.
operation_data.amortization_years_all.setdefault("storage_replacement", 0)
_STORAGE_REPL_YEAR_ZEROS = {y: 0 for y in range(2020, 2070)}
for _cost_key in operation_data.cost_component:
    operation_data.cost_component[_cost_key].setdefault(
        "storage_replacement", dict(_STORAGE_REPL_YEAR_ZEROS)
    )


# Capacity-tier schedule for the switch_flexible_electrolyzer=False valley-fill.
# Each entry = (hours_at_full_year, fraction_of_max_demand). The sum
# Σ hours × fraction must equal full_load_hour_target (3000) so total energy
# placed = annual. Tiers are applied in order: deepest-residual hours get the
# first (typically highest) tier, then the next slice gets the next, etc.
# For partial-year runs, the per-tier hour counts scale by len(T_list)/8760.
# Edit this to retune the peakiness without touching the algorithm below.
ELECTROLYZER_OFF_TIERS = [
    (1500, 1.00),
    (1000, 0.75),
    (900,  0.50),
    (700,  0.25),
    (625,  0.20),
]
assert abs(sum(h * f for h, f in ELECTROLYZER_OFF_TIERS) - 3000) < 1e-6, \
    "ELECTROLYZER_OFF_TIERS must sum to full_load_hour_target = 3000 to conserve energy."


def add_ev_plants(rep_plant_name, Plant_list_TYNDP, Plant_outflow_list, Map_plant_node, Map_plant_tech, add_v2g=True):
    """
    Adds the flexible-EV plant CH00_EV_flex and, if add_v2g, the V2G plant rep_plant_name to the plant lists and maps.
    data_import_TYNDP_fcn runs once per sub-scenario; a plant already in a list is not added again.
    add_v2g=False (switch_V2G off) adds CH00_EV_flex only, the V2G fleet is then part of CH00_EV_flex.
    """
    dle.extend_list_with_new_elements(["CH00_EV_flex"], Plant_list_TYNDP)
    Map_plant_node.update({"CH00_EV_flex": "CH00"})
    Map_plant_tech.update({"CH00_EV_flex": "ev_flex"})
    if add_v2g:
        dle.extend_list_with_new_elements([rep_plant_name], Plant_list_TYNDP)
        Map_plant_node.update({rep_plant_name: "CH00"})
        Map_plant_tech.update({rep_plant_name: "v2g"})
        dle.extend_list_with_new_elements([rep_plant_name], Plant_outflow_list)


def data_import_TYNDP_fcn(scenario_name):
    """
    This function imports the data from TYNDP files.
    Input:
        scenario_name: name of the scenario
    Output:
        Updated values for several global variables both lists (shown by .extend()) and dictionaries (shown by .update()).
        Example: Map_plant_tech.update(Map_plant_tech_nonhydro)
    """
    settings_scen = read_scenario_settings(scenario_name)
    Node_list = settings_scen["Node_list_setting"]
    CH_only = settings_scen["CH_only"]
    if CH_only:     # Override Node_list for single country mode
        print("CH_only mode activated: filtering to CH00 only")
        Node_list = ["CH00",]
    weather_year = settings_scen["weather_year"]
    run_year = settings_scen["run_year"]
    eu_policy = settings_scen["eu_policy"]
    ch_policy = settings_scen["ch_policy"]
    T_list = settings_scen["T_list"]
    rep_hydro_plants = settings_scen["rep_hydro_plants"]
    allow_investment = settings_scen["allow_investment"]
    NTC_CH_ratio = settings_scen["NTC_CH_ratio"]
    merge_some_countries = settings_scen["merge_some_countries"]
    target_merge_countries = settings_scen["target_merge_countries"]
    RES_EU_coefficient = settings_scen["RES_EU_coefficient"]
    electrolyzer_demand_reduction_coefficient = settings_scen["electrolyzer_demand_reduction_coefficient"]
    RES_CH_coefficient = settings_scen["RES_CH_coefficient"]
    PVRF_CH_coefficient = settings_scen["PVRF_CH_coefficient"]
    Windon_CH_coefficient = settings_scen["Windon_CH_coefficient"]
    limit_fuel_import_CH = settings_scen["limit_fuel_import_CH"]
    limited_fuels_import_CH_list = settings_scen["limited_fuels_import_CH_list"]
    NodeDH_list = settings_scen["NodeDH_list"]
    flexible_household_heatpump_share_raw = settings_scen["flexible_household_heatpump_share"]
    share_of_flexibly_charging_EV = settings_scen["share_of_flexibly_charging_EV"]
    V2G_share_of_flexibly_charging_EV = settings_scen["V2G_share_of_flexibly_charging_EV"]
    switch_V2G = settings_scen["switch_V2G"]
    switch_flexible_EV = settings_scen["switch_flexible_EV"]
    switch_flexible_HP = settings_scen["switch_flexible_HP"]
    switch_electric_DSR = settings_scen["switch_electric_DSR"]
    switch_flexible_electrolyzer = settings_scen["switch_flexible_electrolyzer"]
    switch_DH = settings_scen["switch_DH"]
    switch_storage = settings_scen["switch_storage"]
    switch_biomass = settings_scen["switch_biomass"]
    reduce_inflex_demand_by = settings_scen["reduce_inflex_demand_by_[MWh]"]
    reduce_DH_demand_by = settings_scen["reduce_DH_demand_by_[MWh]"]
    DH_demand_adjustment_file = settings_scen["DH_demand_adjustment_file"]
    ror_annual_TWh = settings_scen["ror_annual_TWh"]
    hydro_inflow_TWh = settings_scen["hydro_inflow_TWh"]
    pump_capacity_GW = settings_scen["pump_capacity_GW"]
    adding_hydro_storage_cap_TWh = settings_scen["adding_hydro_storage_cap_TWh"]
    hydro_clusters = settings_scen.get("hydro_clusters", "legacy")  # "legacy" or int 4..20 (WASTA clusters)
    h2_steps = settings_scen.get("h2_steps", False)  # W8: hybrid stepwise hydrogen offtake demand (input/HydrogenDemand/)
    h2_demand_scenario = settings_scen.get("h2_demand_scenario", "central")  # rung role or "<DEFAULT_rung>+<CH00_rung>"
    electrolyzer_flh_target = settings_scen.get("electrolyzer_flh_target", 3000)  # FLH sizing convention for electrolyzer capacity
    # 2026-10-13: uniform fixed hydrogen price (CHF/MWh_H2); None/""/nan = off.
    h2_fixed_price = settings_scen.get("h2_fixed_price", None)
    if isinstance(h2_fixed_price, str) and h2_fixed_price.strip().lower() in ("", "nan", "none"):
        h2_fixed_price = None
    if isinstance(h2_fixed_price, float) and h2_fixed_price != h2_fixed_price:  # NaN from csv
        h2_fixed_price = None
    h2_fixed_price_eta = settings_scen.get("h2_fixed_price_eta", 0.68)
    heat_flexibility_Kelvin = settings_scen["heat_flexibility_Kelvin"]
    storage_to_charge_ratio_days = [settings_scen["storage_to_charge_ratio_days"]]
    battery_investment_nodes_in_addition_to_CH = settings_scen["battery_investment_nodes_in_addition_to_CH"]
    reduce_BE_FR_day_nine_and_ten_demand_to_percent = settings_scen["reduce_BE_FR_day_nine_and_ten_demand_to_percent"]
    lost_load_cost_mode = settings_scen["lost_load_cost_mode"]
    share_of_available_charging_capacity_for_V2G = settings_scen["share_of_available_charging_capacity_for_V2G"]
    neighbor_countries_for_CH_only_mode = settings_scen["neighbor_countries_for_CH_only_mode"]
    neighbor_price_scenario_for_CH_only_mode = settings_scen["neighbor_price_scenario_for_CH_only_mode"]
    high_resolution_PV = settings_scen["high_resolution_PV"]

    # --- Read multi-step lost load cost data ---
    lost_load_cost_filename = f"lostLoadCost_{lost_load_cost_mode}.csv"
    lost_load_cost_filepath = os.path.join("input", "LostLoadCost", lost_load_cost_filename) # NOTE: sub-optimal, that input is hard coded
    df_lost_load_cost = pd.read_csv(lost_load_cost_filepath, comment='#')
    lost_load_cost[scenario_name] = df_lost_load_cost.to_dict('index')


    dle.extend_list_with_new_elements([node + "_fixedconsumer" for node in Node_list], Consumer_list_TYNDP)
    # Consumer_list_TYNDP.extend([node + "_fixedconsumer" for node in Node_list])
    dle.extend_list_with_new_elements(Consumer_list_TYNDP, Consumer_list)
    # Consumer_list.extend(Consumer_list_TYNDP)

    dle.extend_list_with_new_elements(storage_to_charge_ratio_days, storage_to_charge_ratio)

    # Consumer to node mapping
    Map_consumer_node_TYNDP = {node + "_fixedconsumer": node for node in Node_list}
    Map_consumer_node.update(Map_consumer_node_TYNDP)

    print("Importing investment and operation costs...") 
    (cost_data_inv_gen_slp_EP2050,
    cost_data_opr_int_EP2050, 
    cost_data_opr_slp_EP2050, 
    op_cost_n_tech_calibration_EP2050,
    cost_data_inv_e_slp_scne,
    cost_data_inv_fuel_storage_slp_scne,
    cost_data_inv_discharge_slp_scne,
    emission_factor_per_MWh_scne) = data_costs.data_import_costs_fcn(scenario_name)

    dle.update_dict_with_add_dim(cost_data_inv_gen_slp_EP2050, cost_data_inv_gen_slp, scenario_name)
    # cost_data_inv_gen_slp.update(cost_data_inv_gen_slp_EP2050)
    dle.update_dict_with_add_dim(cost_data_opr_int_EP2050, cost_data_opr_int, scenario_name)
    # cost_data_opr_int.update(cost_data_opr_int_EP2050)
    dle.update_dict_with_add_dim(cost_data_opr_slp_EP2050, cost_data_opr_slp, scenario_name)
    # cost_data_opr_slp.update(cost_data_opr_slp_EP2050)
    dle.update_dict_with_add_dim(op_cost_n_tech_calibration_EP2050, op_cost_n_tech_calibration, scenario_name)
    # op_cost_n_tech_calibration.update(op_cost_n_tech_calibration_EP2050)
    dle.update_dict_with_add_dim(cost_data_inv_e_slp_scne, cost_data_inv_e_slp, scenario_name)
    dle.update_dict_with_add_dim(cost_data_inv_fuel_storage_slp_scne, cost_data_inv_fuel_storage_slp, scenario_name)
    dle.update_dict_with_add_dim(cost_data_inv_discharge_slp_scne, cost_data_inv_discharge_slp, scenario_name)
    dle.update_dict_with_add_dim(emission_factor_per_MWh_scne, emission_factor_per_MWh, scenario_name)

    # RES availability data
    print("Reading RES availability and capacity data and calculate infeed...")
    Avail_plant_RES_year_scenario = read_RES_avail_data(
        weather_year, Node_list, run_year=run_year, high_resolution_PV=high_resolution_PV,
    )
    # Avail_plant.update(Avail_plant_RES_year_scenario)

    # RES capacities
    (
        Infedplant_list_instance,
        Map_infeedplant_tech_instance,
        gen_max_RES_pre_existing_instance,
        Map_infeedplant_node_instance,
    ) = read_RES_capacities(
        Map_TYNDPscenario_short_longspaced[eu_policy],
        ch_policy,
        run_year,
        Node_list,
        RES_EU_coefficient,
        RES_CH_coefficient,
        PVRF_CH_coefficient,
        Windon_CH_coefficient,
    )
    
    dle.extend_list_with_new_elements(Infedplant_list_instance, Infeedplant_list) #NOTE: Infedplant_list_instance not used at all elsewhere
    dle.update_dict_with_add_dim(gen_max_RES_pre_existing_instance, gen_max_RES_pre_existing_no_NETFLEX, scenario_name)
    # gen_max_RES_pre_existing_no_NETFLEX.update(gen_max_RES_pre_existing_instance)
    Map_infeedplant_tech.update(Map_infeedplant_tech_instance)  #NOTE: it is assumed that Map_infeedplant_tech (where infeed plants are) is fixed (between sub-scenarios)
    Map_infeedplant_node.update(Map_infeedplant_node_instance)  #NOTE: it is assumed that Map_infeedplant_node (where infeed plants are) is fixed (between sub-scenarios)


    # Plant_list_TYNDP.extend(Plant_list_RES)             # when they are treated as infeed, they are not included in the plant list
    # Map_plant_tech.update(Map_plant_tech_res)     # when they are treated as infeed, they are not included in the plant list
    # Map_plant_node.update(Map_plant_node_RES)     # when they are treated as infeed, they are not included in the plant list

    Infeed_RES_TYNDP_instance = calculate_infeed_TYNDP(
        Node_list,
        tech_infeed_all_list,
        gen_max_RES_pre_existing_instance,
        Avail_plant_RES_year_scenario,
        T_list,
        Map_infeedplant_tech_instance,
        Map_infeedplant_node_instance,
    )

    # add values of dictionary Infeed_RES_TYNDP_instance to Infeed_RES_TYNDP
    # if key in Infeed_RES_TYNDP_instance is ('CH00_fixedconsumer', 'pvrf', 't_6672'), equivalent key in Infeed_RES_TYNDP is ('CH00_fixedconsumer', 'pvrf', 't_6672', sub_scenario)
    # Infeed_consumers.update(Infeed_RES_TYNDP_instance)



    dle.update_dict_with_add_dim(Infeed_RES_TYNDP_instance, Infeed_RES_TYNDP, scenario_name)
    dle.update_dict_with_add_dim(Infeed_RES_TYNDP_instance, Infeed_consumers, scenario_name)

    # infeed data - ror
    (
        Infeed_ROR_TYNDP,
        Plant_list_ror,
        Map_plant_tech_ror,
        Map_plant_node_ror,
    ) = read_ror_Infeed_data(
        weather_year, Node_list, merge_some_countries, target_merge_countries, ror_annual_TWh,
    )
    # Infeed_consumers.update(Infeed_ROR_TYNDP)
    dle.update_dict_with_add_dim(Infeed_ROR_TYNDP, Infeed_consumers, scenario_name)
    
    # Infeedplant_list.extend(Plant_list_ror)
    dle.extend_list_with_new_elements(Plant_list_ror, Infeedplant_list)

    Map_infeedplant_tech.update(Map_plant_tech_ror)
    Map_infeedplant_node.update(Map_plant_node_ror)

    # # hydro plant data
    print("Reading hydro plant data...")
    (
        Plant_list_rsrvr,
        Map_plant_tech_rsrvr,
        Map_plant_node_rsrvr,
        gen_max_MW_rsrvr,
        hydro_storage_MWh_rsrvr,
        hydro_capacities_pumping_MW_rsrvr,
        Map_consumer_plant_rsrvr,
    ) = read_hydro_capacities(
        Node_list, rep_hydro_plants, merge_some_countries, target_merge_countries, pump_capacity_GW, adding_hydro_storage_cap_TWh,
        hydro_clusters=hydro_clusters,
    )
    dle.extend_list_with_new_elements(Plant_list_rsrvr, Plant_list_TYNDP)
    # Plant_list_TYNDP.extend(Plant_list_rsrvr)

    Map_consumer_plant.update(Map_consumer_plant_rsrvr)
    Map_plant_tech.update(Map_plant_tech_rsrvr)
    Map_plant_node.update(Map_plant_node_rsrvr)

    dle.update_dict_with_add_dim(gen_max_MW_rsrvr, Plant_capacity_gen, scenario_name)
    # Plant_capacity_gen.update(gen_max_MW_rsrvr)

    dle.update_dict_with_add_dim(hydro_capacities_pumping_MW_rsrvr, Plant_capacity_pmp, scenario_name)
    # Plant_capacity_pmp.update(hydro_capacities_pumping_MW_rsrvr)

    dle.update_dict_with_add_dim(hydro_storage_MWh_rsrvr, Plant_capacity_strg, scenario_name)
    # Plant_capacity_strg.update(hydro_storage_MWh_rsrvr)

    # inflow data
    Inflow_data_pecd, Plant_inflow_list_TYNDP = read_inflow_data_hourly(
        weather_year,
        Node_list,
        rep_hydro_plants,
        merge_some_countries,
        target_merge_countries,
        hydro_inflow_TWh,
        pump_capacity_GW,
        adding_hydro_storage_cap_TWh,
        hydro_clusters=hydro_clusters,
    )
    #     Inflow_data_pecd[('IT00_psp_open', 't_20')]
    #       216.71428571428572
    # Not exist, Inflow_data_pecd[('CH00_psp_open', 't_20')], Inflow_data_pecd[('CH04_psp_open', 't_20')]

    dle.update_dict_with_add_dim(Inflow_data_pecd, Inflow_data, scenario_name)
    # Inflow_data.update(Inflow_data_pecd)

    dle.extend_list_with_new_elements(Plant_inflow_list_TYNDP, Plant_inflow_list)
    # Plant_inflow_list.extend(Plant_inflow_list_TYNDP)

    # non-hydro plant capacities
    print("Reading non-hydro plant capacities...")
    (
        Plant_list_nonhydro_capacity_gen,
        Plant_capacity_nonhydro,
        Plant_capacity_CH,
    ) = read_plant_non_hydro_capacities(
        Map_TYNDPscenario_short_long[eu_policy], ch_policy, run_year
    )

    # switch_electric_DSR=False: also strip DSR rows from the capacity inputs so
    # they don't trigger the "in capacities_*.csv but not in plants_*.csv"
    # warning from cross_match_plant_list, and don't leave stale entries in
    # Plant_capacity_gen. Identified by name suffix because Map_plant_tech for
    # non-hydro plants isn't available yet at this point.
    if not switch_electric_DSR:
        dsr_in_caps = {p for p in Plant_list_nonhydro_capacity_gen if p.endswith("_dsr")}
        Plant_list_nonhydro_capacity_gen = [p for p in Plant_list_nonhydro_capacity_gen if p not in dsr_in_caps]
        Plant_capacity_nonhydro = {p: v for p, v in Plant_capacity_nonhydro.items() if p not in dsr_in_caps}
        Plant_capacity_CH = {p: v for p, v in Plant_capacity_CH.items() if p not in dsr_in_caps}

    dle.update_dict_with_add_dim(Plant_capacity_nonhydro, Plant_capacity_gen, scenario_name)
    dle.update_dict_with_add_dim(Plant_capacity_CH, Plant_capacity_gen, scenario_name)

    # non-hydro plant other data
    (
        Plant_list_nonhydro,
        Plant_investment_RES_CH_list_instance,
        Plant_investment_non_RES_CH_list_instance,
        Plant_investment_RES_CH_data_instance,
        Map_plant_node_nonhydro,
        Map_plant_tech_nonhydro,
        Map_consumer_plant_nonhydro,
        P_list_fuelswitching_plants_instance,
    ) = read_plant_non_hydro_data(allow_investment, Node_list, battery_investment_nodes_in_addition_to_CH, CH_only, weather_year=weather_year, run_year=run_year, high_resolution_PV=high_resolution_PV)

    # switch_electric_DSR=False: drop every "*_dsr" (tech == "dsr") plant before
    # it enters the global Plant_list / Map_plant_tech. With no DSR plants in
    # model.P, model.P_dsr is empty and the energy_shift_limit_dsr_daily /
    # dsr_daily_balance constraints (gated in define_constraints) aren't built.
    # No demand fallback needed: DSR is additive virtual capacity with daily
    # neutrality, not a carved-out share of inflexible demand.
    if not switch_electric_DSR:
        dsr_plants = {p for p, tech in Map_plant_tech_nonhydro.items() if tech == "dsr"}
        Plant_list_nonhydro = [p for p in Plant_list_nonhydro if p not in dsr_plants]
        Map_plant_node_nonhydro = {p: v for p, v in Map_plant_node_nonhydro.items() if p not in dsr_plants}
        Map_plant_tech_nonhydro = {p: v for p, v in Map_plant_tech_nonhydro.items() if p not in dsr_plants}
        Plant_investment_non_RES_CH_list_instance = [p for p in Plant_investment_non_RES_CH_list_instance if p not in dsr_plants]
        Map_consumer_plant_nonhydro = {
            c: [p for p in plants if p not in dsr_plants]
            for c, plants in Map_consumer_plant_nonhydro.items()
        }
        print(f"[{scenario_name}] switch_electric_DSR=False: dropped {len(dsr_plants)} DSR plants from the non-hydro plant import.")

    dle.extend_list_with_new_elements(Plant_investment_RES_CH_list_instance, Plant_investment_RES_CH_list)
    dle.extend_list_with_new_elements(Plant_investment_non_RES_CH_list_instance, Plant_investment_non_RES_CH_list)
    dle.extend_list_with_new_elements(P_list_fuelswitching_plants_instance, P_list_fuelswitching_plants)
    Plant_investment_RES_CH_data.update(Plant_investment_RES_CH_data_instance) #type: ignore

    dle.extend_list_with_new_elements(Plant_list_nonhydro, Plant_list_TYNDP)
    Map_plant_node.update(Map_plant_node_nonhydro)
    Map_plant_tech.update(Map_plant_tech_nonhydro)
    Map_consumer_plant.update(Map_consumer_plant_nonhydro)

    # electrolyzer data
    print("Reading electrolyzer data...")
    if h2_fixed_price is not None and not switch_flexible_electrolyzer:
        raise ValueError(
            "h2_fixed_price requires switch_flexible_electrolyzer=True "
            "(the fixed price is an elastic annual step on the flexible electrolyzer)."
        )
    if h2_steps and not switch_flexible_electrolyzer:
        raise ValueError(
            "h2_steps=True requires switch_flexible_electrolyzer=True "
            "(the steps are annual FLEXIBLE offtake; the inflexible valley-fill "
            "path has no step machinery)."
        )
    (
        Plant_list_electrolyzer,
        Map_plant_tech_electrolyzer,
        Map_plant_node_electrolyzer,
        Data_plant_flex_d_within_window_electrolyzer,
    ) = read_electrolyzer_data(
        Map_TYNDPscenario_short_long[eu_policy],
        ch_policy,
        run_year,
        Node_list,
        T_list,
        weather_year,
        electrolyzer_demand_reduction_coefficient,
        h2_steps=h2_steps,
        h2_demand_scenario=h2_demand_scenario,
        electrolyzer_flh_target=electrolyzer_flh_target,
        h2_fixed_price=h2_fixed_price,
        h2_fixed_price_eta=h2_fixed_price_eta,
    )

    if switch_flexible_electrolyzer:
        # ---- Flexible electrolyzer ON: register as plants with their flex window
        dle.extend_list_with_new_elements(Plant_list_electrolyzer, Plant_list_TYNDP)
        dle.extend_list_with_new_elements(Plant_list_electrolyzer, Plant_list)
        Map_plant_tech.update(Map_plant_tech_electrolyzer)
        Map_plant_node.update(Map_plant_node_electrolyzer)
        dle.update_dict_with_add_dim(Data_plant_flex_d_within_window_electrolyzer, Data_plant_flex_d_within_window, scenario_name)
        electrolyzer_inflex_pending = None
    else:
        # ---- Flexible electrolyzer OFF: don't register as plants — instead,
        # carry the per-plant (node, energy_target, max_demand) info forward
        # to the demand stage and place a fixed schedule on the lowest-
        # inflex-demand hours per node (valley-fill).
        # read_electrolyzer_data already applied electrolyzer_demand_reduction
        # to non-CH plants, so the values below are post-coefficient.
        electrolyzer_inflex_pending = {
            p: {
                "node": Map_plant_node_electrolyzer[p],
                "energy_target": Data_plant_flex_d_within_window_electrolyzer[p]["energy"][0],
                "max_demand": Data_plant_flex_d_within_window_electrolyzer[p]["max_demand"],
            }
            for p in Plant_list_electrolyzer
        }
        print(f"[{scenario_name}] switch_flexible_electrolyzer=False: {len(electrolyzer_inflex_pending)} electrolyzer plants withheld; will valley-fill after demand is read.")


    # transmission lines data
    print("Reading transmission lines data...")

    NTC_data_year = run_year
    (
        Line_list_TYNDP,
        Map_line_node_TYNDP,
        ATC_exportlimit_TYNDP,
        ATC_importlimit_TYNDP,
        Line_trade_price_TYNDP,
    ) = read_line_data(
        NTC_data_year,
        Node_list,
        T_list,
        NTC_CH_ratio,
        Map_TYNDPscenario_short_long[eu_policy],
        CH_only,
        scenario_name,
        neighbor_countries_for_CH_only_mode,
        neighbor_price_scenario_for_CH_only_mode,
    )

    dle.extend_list_with_new_elements(Line_list_TYNDP, LineATC_list)
    # LineATC_list.extend(Line_list_TYNDP)
    Map_line_node.update(Map_line_node_TYNDP)

    dle.update_dict_with_add_dim(ATC_exportlimit_TYNDP, ATC_exportlimit, scenario_name)
    # ATC_exportlimit.update(ATC_exportlimit_TYNDP)
    dle.update_dict_with_add_dim(ATC_importlimit_TYNDP, ATC_importlimit, scenario_name)
    # ATC_importlimit.update(ATC_importlimit_TYNDP)
    dle.update_dict_with_add_dim(Line_trade_price_TYNDP, Line_trade_price, scenario_name)

    # ----------------------------------- EV + V2G data -------------------------------------------

    rep_plant_name = "V2G_CH"

    # Two layered switches:
    #  - switch_flexible_EV=False forces ALL EV consumption to be inflexible
    #    (share_flex_effective=0). The CH00_EV_flex plant is not created and
    #    the ev_consumption_weekly_sum / ev_consumption_hourly_rate constraints
    #    are skipped in define_constraints(). V2G is implicitly off too
    #    (V2G is a subset of flexible EV).
    #  - switch_V2G=False (with flex EV on) folds the V2G fleet's share into
    #    the non-V2G flexible plant by zeroing the V2G share at read time —
    #    the read_EV_* helpers scale the non-V2G plant by (1 - V2G_share), so
    #    V2G_share=0 absorbs the full flexible portion.
    share_flex_effective = share_of_flexibly_charging_EV if switch_flexible_EV else 0.0
    switch_V2G_effective = switch_V2G and switch_flexible_EV
    V2G_share_effective = V2G_share_of_flexibly_charging_EV if switch_V2G_effective else 0.0

    # Inflexible EV demand is ALWAYS populated. When switch_flexible_EV=False,
    # share_flex_effective=0 so 100% of EV consumption becomes inflexible.
    EV_inflexible_demand_TYNDP = read_EV_inflexible_demand_data(run_year, share_flex_effective, node="CH00")
    dle.update_dict_with_add_dim(EV_inflexible_demand_TYNDP, EV_inflexible_demand_data, scenario_name)

    if switch_flexible_EV:
        # ---- Flexible EV ON: read flex/V2G data, add CH00_EV_flex (and V2G_CH) --
        EV_weekly_energy_consumption_data_TYNDP = read_EV_weekly_energy_consumption_data(run_year, share_of_flexibly_charging_EV, V2G_share_effective)
        EV_charging_power_rate_TYNDP, V2G_charge_power_rate_TYNDP = read_EV_and_V2G_charging_power_rate(run_year, rep_plant_name, share_of_flexibly_charging_EV, V2G_share_effective, share_of_available_charging_capacity_for_V2G)

        dle.update_dict_with_add_dim(EV_weekly_energy_consumption_data_TYNDP, EV_weekly_energy_consumption_data, scenario_name)
        dle.update_dict_with_add_dim(EV_charging_power_rate_TYNDP, EV_charging_power_rate, scenario_name)

        if switch_V2G_effective:
            # ---- V2G ON: populate V2G-specific data ---
            V2G_outflow_TYNDP = read_V2G_data_outflow(run_year, rep_plant_name, share_of_flexibly_charging_EV, V2G_share_of_flexibly_charging_EV)
            V2G_storage_capacity_scen = read_V2G_storage_capacity(run_year, ch_policy, rep_plant_name, share_of_flexibly_charging_EV, V2G_share_of_flexibly_charging_EV)

            dle.update_dict_with_add_dim(V2G_outflow_TYNDP, Outflow_data, scenario_name)
            dle.update_dict_with_add_dim(V2G_charge_power_rate_TYNDP, V2G_charging_power_rate, scenario_name)
            dle.update_dict_with_add_dim(V2G_storage_capacity_scen, V2G_storage_capacity, scenario_name)
        else:
            # V2G off (or implicitly off via switch_flexible_EV=False): V2G_CH
            # plant + V2G data dicts are not created. P_evV2G / P_outflow stay
            # empty for v2g so the V2G constraints iterate over an empty set.
            # The V2G fleet's flexible-charging energy was already rolled into
            # CH00_EV_flex via V2G_share_effective=0 above.
            print(f"[{scenario_name}] switch_V2G=False: V2G fleet folded into CH00_EV_flex (flexible non-V2G).")

        # Add CH00_EV_flex and, with V2G on, V2G_CH. add_ev_plants lists each plant once,
        # although data_import_TYNDP_fcn runs once per sub-scenario.
        add_ev_plants(rep_plant_name, Plant_list_TYNDP, Plant_outflow_list, Map_plant_node, Map_plant_tech, add_v2g=switch_V2G_effective)
    else:
        # ---- Flexible EV OFF: all EV demand is inflexible (handled above).
        # No CH00_EV_flex plant, no V2G_CH plant, no flexible EV / V2G data
        # reads. The ev_consumption_* and v2g_* constraints are gated in
        # define_constraints() so they aren't built at all.
        print(f"[{scenario_name}] switch_flexible_EV=False: all EV demand routed to inflexible; V2G implicitly off.")
    
    # ----------------------------------- fuel tracking data -------------------------------------
    Fuel_limits_CH_data_year_scenario = read_fuel_limit_data(
        ch_policy,
        run_year,
        limit_fuel_import_CH,
        limited_fuels_import_CH_list,
    )

    dle.update_dict_with_add_dim(Fuel_limits_CH_data_year_scenario, Fuel_limits_data, scenario_name)

    # ----------------------------------- heat pumps ----------------------------------------------

    # switch_flexible_HP=False forces 100% of household HP demand to be inflexible:
    #   - flex_HP_share_effective=0 → read_HP_inflexible_demand_data returns full HP demand
    #   - BA archetype plants / Params / Vars / constraints are NOT created
    # Note: flexible_household_heatpump_share[0] is also used in two DH-side
    # places (dsrThDev_max scaling and inflexble_demandTh_share constraint).
    # We keep the RAW share in the global list so DH semantics are unaffected
    # by this toggle — switch_flexible_HP only governs the BA system.
    flex_HP_share_effective = flexible_household_heatpump_share_raw if switch_flexible_HP else 0.0

    # BA_el_con (100% of household HP electricity demand) is needed for the
    # inflexible-HP calculation in BOTH branches, so we always call this. The
    # other returns (BA_th_con etc.) are scaled by flex_HP_share_effective —
    # they would be all-zeros when off, but we also skip publishing them.
    BA_el_con, BA_th_con_TYNDP, BA_th_lim_TYNDP, COP_TYNDP, BA_names_TYNDP, BA_max_heating_capacity_TYNDP = read_building_archetypes(run_year, weather_year, flex_HP_share_effective, heat_flexibility_Kelvin, heating_system="HP")

    # DH-side reuse of the share — always RAW, independent of switch_flexible_HP.
    dle.extend_list_with_new_elements([flexible_household_heatpump_share_raw], flexible_household_heatpump_share)

    if switch_flexible_HP:
        # ---- Flexible HP ON: add BA archetypes as plants + populate BA Params data
        dle.update_dict_with_add_dim(BA_th_con_TYNDP, BA_th_con, scenario_name)
        dle.update_dict_with_add_dim(BA_th_lim_TYNDP, BA_th_lim, scenario_name)
        dle.update_dict_with_add_dim(COP_TYNDP, COP, scenario_name)
        dle.extend_list_with_new_elements(BA_names_TYNDP, BA_names)
        dle.extend_list_with_new_elements(BA_names_TYNDP, Plant_list_TYNDP)
        dle.update_dict_with_add_dim(BA_max_heating_capacity_TYNDP, BA_max_heating_capacity, scenario_name)

        # Add the right maps to the newly added heat pump building archetypes
        Map_plant_node.update({name: "CH00" for name in BA_names})
        Map_plant_tech.update({name: "heat_pump_households" for name in BA_names})
    else:
        # ---- Flexible HP OFF: BA plants + BA Params data are not created.
        # model.BA_names / model.BA_th_* / model.COP / model.th_sl are all
        # initialized over the (now empty) BA_names list → empty containers.
        # The building_heat_demand / building_weekly_average /
        # max_heating_capacity constraints are gated in define_constraints()
        # so they aren't built at all.
        print(f"[{scenario_name}] switch_flexible_HP=False: all household HP demand routed to inflexible.")

    # Inflexible HP demand — uses effective share so 100% becomes inflexible when off.
    HP_inflexible_demand_TYNDP = read_HP_inflexible_demand_data(BA_el_con, flex_HP_share_effective, node="CH00")
    dle.update_dict_with_add_dim(HP_inflexible_demand_TYNDP, HP_inflexible_demand_data, scenario_name)

    # ----------------------------------- demand data ----------------------------------------------
    print("Reading demand data...")
    # Note: We now subtract both the flexible HP demand AND the inflexible HP demand from the general demand
    # The flexible HP demand is modeled separately as optimizable plants
    # The inflexible HP demand is added to the energy balance as a fixed demand parameter (HP_inflexible_demand)
    # This allows distinguishing between: (1) general inflexible demand, (2) inflexible HP demand, (3) flexible HP demand
    Demand_data_year_scenario = read_demand_data(
        Map_TYNDPscenario_short_long[eu_policy],
        ch_policy,
        Node_list,
        run_year,
        weather_year,
        reduce_inflex_demand_by,
        BA_el_con,  # Now we subtract the ENTIRE HP consumption, not just the flexible portion
        float(reduce_BE_FR_day_nine_and_ten_demand_to_percent),
    )

    dle.update_dict_with_add_dim(Demand_data_year_scenario, Demand_data, scenario_name)
    # Demand_data.update(Demand_data_year_scenario)
    dle.update_dict_with_add_dim(Demand_data_year_scenario, Demand_data_TYNDP, scenario_name)
    # Demand_data_TYNDP.update(Demand_data_year_scenario)

    # ----------------------------------- electrolyzer valley-fill (when off) ----------------------
    # When switch_flexible_electrolyzer=False, the electrolyzers are still
    # consuming their (post-coefficient) annual energy — they just aren't
    # flexible. We model that by placing max_demand MWh on the lowest-inflex-
    # demand hours at each electrolyzer's node, until the per-period energy
    # target is met. The per-period target = annual_MWh * (len(T_list)/8760)
    # (this matches how energy[0] is already scaled in read_electrolyzer_data),
    # so short simulations naturally fill a proportionally smaller number of
    # hours: n_full = round_down(energy_target / max_demand). Any leftover
    # (< max_demand) is placed in the next-lowest hour.
    if electrolyzer_inflex_pending:
        for plant, info in electrolyzer_inflex_pending.items():
            node = info["node"]
            energy_target = info["energy_target"]
            max_demand = info["max_demand"]
            if max_demand <= 0 or energy_target <= 0:
                continue

            # Rank modeled hours at this node by RESIDUAL LOAD:
            #   residual = inflex_base + EV_inflex + HP_inflex
            #            - pvrf_infeed - windon_infeed - windof_infeed
            # i.e. the load the dispatchable system still has to serve after
            # absorbing pre-existing must-take RES. Negative residuals mark
            # genuine RES-surplus hours — the best places to put extra fixed
            # load without inducing lost load. EV/HP inflex are kept on the
            # demand side because they are actual loads competing with the
            # electrolyzer at that node.
            # Previously-placed electrolyzer load at this node is added so
            # multiple electrolyzers (rare — usually one per node) spread out
            # into different valley hours instead of stacking.
            consumer = f"{node}_fixedconsumer"
            hour_demand = []
            for t in T_list:
                base = Demand_data_year_scenario.get((consumer, "fixed", t), 0.0)
                ev = EV_inflexible_demand_data.get((node, t, scenario_name), 0.0)
                hp = HP_inflexible_demand_data.get((node, t, scenario_name), 0.0)
                pvrf = Infeed_RES_TYNDP.get((consumer, "pvrf", t, scenario_name), 0.0)
                windon = Infeed_RES_TYNDP.get((consumer, "windon", t, scenario_name), 0.0)
                windof = Infeed_RES_TYNDP.get((consumer, "windof", t, scenario_name), 0.0)
                already = Electrolyzer_inflexible_demand_data.get((node, t, scenario_name), 0.0)
                residual = base + ev + hp - pvrf - windon - windof + already
                hour_demand.append((residual, t))
            hour_demand.sort(key=lambda x: x[0])

            # Multi-tier valley-fill driven by ELECTROLYZER_OFF_TIERS.
            # For each tier (hours_at_full_year, fraction):
            #   - take the next slice of int(hours_at_full_year * T/8760) hours
            #     from the residual-sorted list,
            #   - assign fraction*max_demand MW to each.
            # Energy total over all tiers = full_load_hour_target × max_demand
            # × (T/8760) = annual × (T/8760) = energy_target.
            placed = 0.0
            idx = 0
            for full_year_hours, frac in ELECTROLYZER_OFF_TIERS:
                n = int(full_year_hours * len(T_list) / 8760)
                if n <= 0:
                    continue
                per_hour = max_demand * frac
                for _, t in hour_demand[idx:idx + n]:
                    key = (node, t, scenario_name)
                    Electrolyzer_inflexible_demand_data[key] = Electrolyzer_inflexible_demand_data.get(key, 0.0) + per_hour
                placed += n * per_hour
                idx += n

            # Spread any leftover energy (rounding remainder from int() floors
            # of partial-year hour counts) onto additional hours. We cap each
            # remainder hour at the LAST tier's fraction (not at max_demand),
            # because the remainder hours come AFTER the tier-tail in the
            # residual-sorted list — i.e. they sit at higher residual than the
            # 20% tier. Putting them at 100% would create new local peaks
            # exactly where we wanted soft fill, so we keep the same "very
            # low marginal power" as the last tier.
            remainder = energy_target - placed
            remainder_cap = max_demand * ELECTROLYZER_OFF_TIERS[-1][1]
            while remainder > 1e-9 and idx < len(hour_demand):
                add = min(remainder, remainder_cap)
                _, t = hour_demand[idx]
                key = (node, t, scenario_name)
                Electrolyzer_inflexible_demand_data[key] = Electrolyzer_inflexible_demand_data.get(key, 0.0) + add
                remainder -= add
                idx += 1

    # ----------------------------------- district heating data -----------------------------------
    if switch_DH:
        # ---- DH ON: full sector — load thermal demand, plants, capacities, maps -----------------
        DemandDH_data_year_scenario = read_demandDH_data(run_year, weather_year, reduce_DH_demand_by, DH_demand_adjustment_file)
        dle.update_dict_with_add_dim(DemandDH_data_year_scenario, DemandDH_data, scenario_name)
        # district heating plant data and capacities
        (
            PlantDH_list_scenario,
            Map_plantDH_nodeEl_scenario,
            Map_plantDH_nodeDH_scenario,
            Map_nodeDH_plantDH_scenario,
            Map_plantDH_tech_scenario,
            Map_nodeDH_country,
            PlantDH_data_remaining_scenario,
            PlantDH_capacity_CH_scenario,
            Plant_capacity_CH_scenario,
            PlantDH_investment_STES_list_scenario,
            Plant_investment_data_STES_scenario,
        ) = read_plantDH_data_and_capacities(NodeDH_list, Node_list, run_year)

        dle.extend_list_with_new_elements(PlantDH_list_scenario, PlantDH_list)
        dle.extend_list_with_new_elements(PlantDH_list_scenario, Plant_list_TYNDP)

        Map_plantDH_nodeEl.update(Map_plantDH_nodeEl_scenario)
        Map_plant_node.update(Map_plantDH_nodeEl_scenario)                  #NOTE: stored in two dictionaries, Map_plant_node and Map_plantDH_nodeDH, maybe Map_plantDH_nodeEl not necessary

        Map_plantDH_nodeDH.update(Map_plantDH_nodeDH_scenario)

        Map_node_plant.update(Map_nodeDH_plantDH_scenario)
        Map_nodeDH_plantDH.update(Map_nodeDH_plantDH_scenario)

        Map_plantDH_tech.update(Map_plantDH_tech_scenario)
        Map_plant_tech.update(Map_plantDH_tech_scenario)                    #NOTE: stored in two dictionaries, Map_plant_tech and Map_plantDH_tech, maybe Map_plantDH_technot necessary

        Map_node_country.update(Map_nodeDH_country)

        dle.update_dict_with_add_dim(PlantDH_data_remaining_scenario, PlantDH_data_remaining, scenario_name)
        dle.update_dict_with_add_dim(PlantDH_capacity_CH_scenario, PlantDH_capacity, scenario_name)
        dle.update_dict_with_add_dim(Plant_capacity_CH_scenario, Plant_capacity_gen, scenario_name)
        dle.extend_list_with_new_elements(PlantDH_investment_STES_list_scenario, PlantDH_investment_STES_list) #NOTE: should I keep it like this, or add to Plant_investment_RES_CH_list?
        Plant_investment_data_STES.update(Plant_investment_data_STES_scenario) #type: ignore

        for keys in Plant_investment_RES_CH_data.keys():
            Plant_investment_RES_CH_data[keys].update(Plant_investment_data_STES_scenario[keys])
    else:
        # ---- DH OFF: aggregate thermal demand, convert to electric (COP=3), store in
        # DH_inflexible_demand_data as a separate node-indexed Param. The energy balance
        # picks it up via model.DH_inflexible_demand (parallel to EV_inflexible_demand /
        # HP_inflexible_demand / Electrolyzer_inflexible_demand). No DH plants / sets /
        # Params / Vars / constraints are populated; the DH-side of the model collapses
        # entirely. core.py also forces NodeDH_list=[] in this branch so model.NodeDH is
        # empty too.
        DemandDH_data_year_scenario = read_demandDH_data(run_year, weather_year, reduce_DH_demand_by, DH_demand_adjustment_file)
        COP_DH_OFF = 3.0  # air heat pump assumption (per user spec)
        # Sum the DH thermal demand across all DH regions per hour.
        thermal_per_hour = {}
        for (dh_node, t), v in DemandDH_data_year_scenario.items():
            thermal_per_hour[t] = thermal_per_hour.get(t, 0.0) + v
        # Convert and store at CH00 in the dedicated dict (NOT in Demand_data, so the
        # contribution is visible separately in the dispatch plot).
        added = 0.0
        for t in T_list:
            electric_eq = thermal_per_hour.get(t, 0.0) / COP_DH_OFF
            if electric_eq == 0:
                continue
            DH_inflexible_demand_data[("CH00", t, scenario_name)] = electric_eq
            added += electric_eq
        thermal_in_T = sum(thermal_per_hour.get(t, 0.0) for t in T_list)
        print(f"[{scenario_name}] switch_DH=False: {thermal_in_T/1e6:.3f} TWh thermal DH demand → +{added/1e6:.3f} TWh electric inflex at CH00 (COP=3).")
    
    KVAinfeed_raw = read_KVA_infeed_data()
    dle.update_dict_with_add_dim(KVAinfeed_raw, KVAinfeed, scenario_name)

    # ----------------------------------- storage replacement -----------------------------------
    # switch_storage=False: drop every ELECTRIC plant whose tech is in tech_store_list
    # (battery, hydrogen, psp_open, psp_close, v2g, dam, TES, TTES_medium, PTES_large)
    # and add a {node}_storage_replacement virtual generator at each electric node.
    # P_storage and the storage_soc/storage_*_limit constraint families auto-empty.
    # The replacement plant is non-investable (capacity fixed via Plant_capacity_gen).
    #
    # DH thermal storage (TTES/PTES/TES) shares those tech names but belongs to the
    # district-heating subsystem (governed by switch_DH, not switch_storage). DH
    # plants are registered in both Plant_list_TYNDP and Map_plant_tech (see the DH
    # import above), so they would otherwise be caught here and removed from the
    # electric maps while PlantDH_list / Map_plantDH_tech still reference them,
    # breaking PDH_storage parameter builds. Exclude DH plants from the drop.
    if not switch_storage:
        from model.structural_parameters import tech_store_list
        storage_plants = [
            p for p in Plant_list_TYNDP
            if Map_plant_tech.get(p) in tech_store_list and p not in PlantDH_list
        ]
        for p in storage_plants:
            Plant_list_TYNDP.remove(p)
            Map_plant_tech.pop(p, None)
            Map_plant_node.pop(p, None)

        REPLACEMENT_COST = 300.0  # CHF/MWh — between thermal op cost and lost load
        REPLACEMENT_CAP = 1.0e6   # MW per node, effectively unlimited
        added_replacements = []
        for node in Node_list:
            plant_name = f"{node}_storage_replacement"
            Plant_list_TYNDP.append(plant_name)
            Map_plant_node[plant_name] = node
            Map_plant_tech[plant_name] = "storage_replacement"
            Plant_capacity_gen[(plant_name, scenario_name)] = REPLACEMENT_CAP
            added_replacements.append(plant_name)

        # Override the auto-imported (zero) cost data for storage_replacement.
        # cost_data_opr_slp is the only one that matters for the objective; the
        # rest are populated with 0 because storage_replacement isn't investable.
        cost_data_opr_slp[("storage_replacement", scenario_name)] = REPLACEMENT_COST

        print(f"[{scenario_name}] switch_storage=False: removed {len(storage_plants)} storage plants; added {len(added_replacements)} {{node}}_storage_replacement generators at {REPLACEMENT_COST} CHF/MWh.")

    # # ----------------------------------- Industrial load heating -----------------------------------

    # read availabilities of plants - has to be done after all plants are read -------------------------
    print("Reading availabilities...")
    # calculate avail plant for non-hydro plants
    Avail_plant_TYNDP = import_avail_plant(
        Plant_list_TYNDP,
        Plant_investment_RES_CH_list_instance,
        Plant_investment_non_RES_CH_list_instance,
        T_list,
        Map_plant_node,
        Map_plant_tech,
        Map_node_country,
        Avail_plant_RES_year_scenario,
    )

    dle.update_dict_with_add_dim(Avail_plant_TYNDP, Avail_plant, scenario_name)

    # -----------------------------------------------------------------------------------------------
    # cross matching of plants and updating Plant_list

    # check if there is any cross-mismatch issue (raises an error for a plant without capacity, unless it is an investment candidate)
    cross_match_plant_list(
        Plant_list_nonhydro_capacity_gen,
        Plant_list_nonhydro,
        Plant_investment_RES_CH_list_instance + Plant_investment_non_RES_CH_list_instance,
    )

    dle.extend_list_with_new_elements(Plant_list_TYNDP, Plant_list)

    # -----------------------------------------------------------------------------------------------
    # --------------------------------------- update Mappings ---------------------------------------
    # -----------------------------------------------------------------------------------------------
    # part 1: mappings that might have duplicates: conditions such as "if p not in Map_node_plant[node]" is 
    for node in Node_list:
        # Map_node_plant
        # Coding approach below updates Map_node_plant (extend), instead of overwriting it (assign).
        # setdefault() checks if the node key already exists in Map_node_plant. If it does, it returns the list associated with it. If it doesn't, it creates a new key with an empty list.
        Map_node_plant.setdefault(node, []).extend(
            p
            for p in Plant_list_TYNDP
            if Map_plant_node[p] == node
            if p not in Map_node_plant[node]
        )

        # Map_node_consumer
        Map_node_consumer.setdefault(node, []).extend(
            c for c in Consumer_list_TYNDP if Map_consumer_node_TYNDP[c] == node if c not in Map_node_consumer[node]
        )

        # Map_node_exportinglineATC
        Map_node_exportinglineATC.setdefault(node, []).extend(
            l for l in Line_list_TYNDP if node == Map_line_node_TYNDP[l]["start_node"] if l not in Map_node_exportinglineATC[node]
        )

        # Map_node_importinglineATC
        Map_node_importinglineATC.setdefault(node, []).extend(
            l for l in Line_list_TYNDP if node == Map_line_node_TYNDP[l]["end_node"] if l not in Map_node_importinglineATC[node]
        )

    # part 2: maapings that do not have duplicates, because of using map_tech_to_plant function 
    # Updating Map_eff_in_plant and Map_eff_out_plant
    # Extract year-specific values from efficiency dicts (they now include both 2035 and 2050)
    efficiency_into_storage_for_year = {}
    efficiency_for_year = {}
    for tech, val in operation_data.cost_component["efficiency_into_storage"].items():
        if isinstance(val, dict):
            efficiency_into_storage_for_year[tech] = val.get(run_year, 0)
        else:
            efficiency_into_storage_for_year[tech] = val
    
    for tech, val in operation_data.cost_component["efficiency"].items():
        if isinstance(val, dict):
            efficiency_for_year[tech] = val.get(run_year, 1)
        else:
            efficiency_for_year[tech] = val
    
    Map_eff_in_plant_TYNDP = map_tech_to_plant(
        Plant_list_TYNDP, {}, efficiency_into_storage_for_year, Map_plant_tech
    )

    Map_eff_in_plant.update(Map_eff_in_plant_TYNDP)

    Map_eff_out_plant_TYNDP = map_tech_to_plant(
        Plant_list_TYNDP, {}, efficiency_for_year, Map_plant_tech
    )

    Map_eff_out_plant.update(Map_eff_out_plant_TYNDP)

    # Updating start condition
    Map_plant_startcondition_TYNDP = map_tech_to_plant(
        Plant_list_TYNDP, {}, Map_tech_startcondition, Map_plant_tech
    )

    Map_plant_startcondition.update(Map_plant_startcondition_TYNDP)

    Data_plant_energy_limited_TYNDP = {}
    Data_plant_energy_limited_TYNDP = read_plant_energy_limited_data(
        Map_TYNDPscenario_short_long[eu_policy],
        ch_policy,
        Plant_list_TYNDP,
        Plant_investment_non_RES_CH_list_instance,
        Plant_investment_RES_CH_data_instance,
        Map_plant_tech,
        Map_plant_node,
        tech_limited_energy_list,
        tech_limited_energy_CH_list,
        weather_year,
        run_year,
        T_list,
        PlantDH_investment_STES_list
    )
    dle.update_dict_with_add_dim(Data_plant_energy_limited_TYNDP, Data_plant_energy_limited, scenario_name)
    # Data_plant_energy_limited.update(Data_plant_energy_limited_TYNDP)

    # ----------------------------------- biomass fixed schedule -----------------------------------
    # switch_biomass=False: filter every "biomass" plant out of Plant_list / Plant_list_TYNDP
    # and place its annual energy budget as a FIXED generation schedule on the highest-
    # residual-demand hours at the plant's node. Energy is preserved (no artificial relaxation).
    #
    # Residual demand (same shape as the electrolyzer valley-fill, extended to include
    # Electrolyzer_inflex and DH_inflex since biomass placement runs AFTER both branches):
    #   residual = base + EV_inflex + HP_inflex + Electrolyzer_inflex + DH_inflex
    #            - pvrf_infeed - windon_infeed - windof_infeed
    # When electrolyzers / DH are ON, their inflex dicts are empty (zeros), so the formula
    # still works either way. Sorted DESCENDING — biomass plugs the worst-case gaps.
    # No tiering: biomass annual quantities are smaller than electrolyzer's so a clean
    # gen_max-or-remainder fill at full power doesn't induce lost load.
    # Placed at the END of the function so Data_plant_energy_limited is populated (EU
    # biomass energy budgets come from there) and all the inflex dicts are finalized.
    if not switch_biomass:
        biomass_plants = [p for p in Plant_list_TYNDP if Map_plant_tech.get(p) == "biomass"]

        # Pre-compute the COLLECTIVE CH biomass annual budget from the fuel cap × efficiency.
        # This is the actual binding constraint that fuel_limit_annual_Constraint enforces in
        # the ON case — the model burns the entire fuel cap because biomass op-cost is near
        # zero. (Earlier attempts at using generation_CH.csv under-supplied; that file holds
        # a lower TYNDP projection, not the binding cap.)
        #
        # CH has multiple subnode biomass plants (CH01_biomass...CH07_biomass) sharing one
        # fuel pool, so we distribute the total by installed-capacity weight. Without the
        # weighting the full fuel cap gets applied to EACH plant → ~7× over-supply.
        #
        # CH demand also lives entirely at CH00_fixedconsumer (subnode consumers carry zero
        # demand), so we rank residuals at CH00 for all CH biomass plants — ranking at the
        # subnode would only see the negative RES infeed and give a near-meaningless order.
        ch_biomass_plants = [p for p in biomass_plants if Map_plant_node[p].startswith("CH")]
        ch_biomass_total_annual = 0.0
        ch_biomass_weights = {}
        if ch_biomass_plants:
            fuel_caps = Fuel_limits_data.get(("biomass", scenario_name), {})
            annual_fuel = (
                fuel_caps.get("import_capacity_annual", 0.0)
                + fuel_caps.get("production_capacity_CH", 0.0)
                + fuel_caps.get("storage_potential_capacity", 0.0)
            )
            efficiency_year = operation_data.cost_component["efficiency"].get("biomass", {}).get(run_year, 1.0) or 1.0
            ch_biomass_total_annual = annual_fuel * efficiency_year
            _ch_caps = {p: Plant_capacity_gen.get((p, scenario_name), 0.0) for p in ch_biomass_plants}
            _total_ch_cap = sum(_ch_caps.values())
            if _total_ch_cap > 0:
                ch_biomass_weights = {p: cap / _total_ch_cap for p, cap in _ch_caps.items()}

        total_placed = 0.0
        for plant in biomass_plants:
            node = Map_plant_node[plant]
            # CH subnode plants share aggregate demand at CH00; everywhere else use the
            # plant's own node for the residual lookup.
            consumer = "CH00_fixedconsumer" if node.startswith("CH") else f"{node}_fixedconsumer"
            gen_max_p = Plant_capacity_gen.get((plant, scenario_name), 0.0)

            # Per-plant annual energy budget in the modeled period.
            if (plant, scenario_name) in Data_plant_energy_limited:
                # EU biomass — energy already time-scaled (* len(T_list)/8760).
                energy_budget = Data_plant_energy_limited[(plant, scenario_name)]
            elif node.startswith("CH") and plant in ch_biomass_weights:
                # CH biomass — capacity-weighted share of the CH-wide fuel × efficiency
                # cap, then time-scaled to the modeled period.
                energy_budget = ch_biomass_total_annual * ch_biomass_weights[plant] * (len(T_list) / 8760)
            else:
                # Fallback — should not normally trigger; leaves the plant un-placed.
                energy_budget = 0.0

            if energy_budget <= 0 or gen_max_p <= 0:
                continue

            # Residual demand at this node for each modeled hour.
            hour_residual = []
            for t in T_list:
                base = Demand_data_year_scenario.get((consumer, "fixed", t), 0.0)
                ev = EV_inflexible_demand_data.get((node, t, scenario_name), 0.0)
                hp = HP_inflexible_demand_data.get((node, t, scenario_name), 0.0)
                el = Electrolyzer_inflexible_demand_data.get((node, t, scenario_name), 0.0)
                dh = DH_inflexible_demand_data.get((node, t, scenario_name), 0.0)
                pvrf = Infeed_RES_TYNDP.get((consumer, "pvrf", t, scenario_name), 0.0)
                won = Infeed_RES_TYNDP.get((consumer, "windon", t, scenario_name), 0.0)
                wof = Infeed_RES_TYNDP.get((consumer, "windof", t, scenario_name), 0.0)
                # Subtract biomass already placed at this node by earlier plants (defensive
                # against the unlikely case of multiple biomass plants per node).
                already = Biomass_inflexible_generation_data.get((node, t, scenario_name), 0.0)
                hour_residual.append((base + ev + hp + el + dh - pvrf - won - wof - already, t))

            # DESCENDING — biomass fills the highest-residual hours first.
            hour_residual.sort(key=lambda x: x[0], reverse=True)

            # Fill at full gen_max until budget runs out, then place the leftover on the next.
            n_full = int(energy_budget // gen_max_p)
            remainder = energy_budget - n_full * gen_max_p
            for _, t in hour_residual[:n_full]:
                key = (node, t, scenario_name)
                Biomass_inflexible_generation_data[key] = Biomass_inflexible_generation_data.get(key, 0.0) + gen_max_p
                total_placed += gen_max_p
            if remainder > 1e-9 and n_full < len(hour_residual):
                _, t = hour_residual[n_full]
                key = (node, t, scenario_name)
                Biomass_inflexible_generation_data[key] = Biomass_inflexible_generation_data.get(key, 0.0) + remainder
                total_placed += remainder

        # Remove biomass plants from BOTH Plant_list_TYNDP and Plant_list (the latter has
        # already been extended by line ~944). P_fuellimCH and P_energylim auto-empty their
        # biomass entries because both sets are filtered over model.P; fuel_limit_annual
        # for the "biomass" fuel becomes Constraint.Skip when relevant_plants is empty.
        for plant in biomass_plants:
            if plant in Plant_list_TYNDP:
                Plant_list_TYNDP.remove(plant)
            if plant in Plant_list:
                Plant_list.remove(plant)
            Map_plant_tech.pop(plant, None)
            Map_plant_node.pop(plant, None)

        print(f"[{scenario_name}] switch_biomass=False: removed {len(biomass_plants)} biomass plants; placed {total_placed/1e6:.3f} TWh as fixed generation on highest-residual hours per node.")


