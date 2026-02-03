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
    reduce_inflex_demand_by = settings_scen["reduce_inflex_demand_by_[MWh]"]
    reduce_DH_demand_by = settings_scen["reduce_DH_demand_by_[MWh]"]
    ror_annual_TWh = settings_scen["ror_annual_TWh"]
    hydro_inflow_TWh = settings_scen["hydro_inflow_TWh"]
    pump_capacity_GW = settings_scen["pump_capacity_GW"]
    adding_hydro_storage_cap_TWh = settings_scen["adding_hydro_storage_cap_TWh"]
    heat_flexibility_Kelvin = settings_scen["heat_flexibility_Kelvin"]
    storage_to_charge_ratio_days = [settings_scen["storage_to_charge_ratio_days"]]
    battery_investment_nodes_in_addition_to_CH = settings_scen["battery_investment_nodes_in_addition_to_CH"]
    reduce_BE_FR_day_nine_and_ten_demand_to_percent = settings_scen["reduce_BE_FR_day_nine_and_ten_demand_to_percent"]
    lost_load_cost_mode = settings_scen["lost_load_cost_mode"]
    share_of_available_charging_capacity_for_V2G = settings_scen["share_of_available_charging_capacity_for_V2G"]
    neighbor_countries_for_CH_only_mode = settings_scen["neighbor_countries_for_CH_only_mode"]
    neighbor_price_scenario_for_CH_only_mode = settings_scen["neighbor_price_scenario_for_CH_only_mode"]

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
        weather_year, Node_list
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
        Node_list, rep_hydro_plants, merge_some_countries, target_merge_countries, pump_capacity_GW, adding_hydro_storage_cap_TWh
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
    # Plant_list_TYNDP.extend(Plant_list_nonhydro_capacity_gen)
    dle.update_dict_with_add_dim(Plant_capacity_nonhydro, Plant_capacity_gen, scenario_name)
    # Plant_capacity_gen.update(Plant_capacity_nonhydro)
    dle.update_dict_with_add_dim(Plant_capacity_CH, Plant_capacity_gen, scenario_name)
    # Plant_capacity_gen.update(Plant_capacity_CH)

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
    ) = read_plant_non_hydro_data(allow_investment, Node_list, battery_investment_nodes_in_addition_to_CH, CH_only)

    dle.extend_list_with_new_elements(Plant_investment_RES_CH_list_instance, Plant_investment_RES_CH_list)
    dle.extend_list_with_new_elements(Plant_investment_non_RES_CH_list_instance, Plant_investment_non_RES_CH_list)
    dle.extend_list_with_new_elements(P_list_fuelswitching_plants_instance, P_list_fuelswitching_plants)
    Plant_investment_RES_CH_data.update(Plant_investment_RES_CH_data_instance) #type: ignore
    # Plant_investment_RES_CH_list.extend(Plant_investment_RES_CH_list_TYNDP)
    # techs_to_be_excluded = [
    #     "dsr",
    # ]
    # for plant in Plant_list_nonhydro:
    #     # if a plant constains strings in techs_to_be_excluded, remove the plant from the list
    #     if any(tech in plant for tech in techs_to_be_excluded):
    #         Plant_list_nonhydro.remove(plant)

    dle.extend_list_with_new_elements(Plant_list_nonhydro, Plant_list_TYNDP)
    # Plant_list_TYNDP.extend(Plant_list_nonhydro)
    Map_plant_node.update(Map_plant_node_nonhydro)
    Map_plant_tech.update(Map_plant_tech_nonhydro)
    Map_consumer_plant.update(Map_consumer_plant_nonhydro)

    # electrolyzer data
    print("Reading electrolyzer data...")
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
        electrolyzer_demand_reduction_coefficient
    )

    dle.extend_list_with_new_elements(Plant_list_electrolyzer, Plant_list_TYNDP)
    dle.extend_list_with_new_elements(Plant_list_electrolyzer, Plant_list)
    Map_plant_tech.update(Map_plant_tech_electrolyzer)
    Map_plant_node.update(Map_plant_node_electrolyzer)
    dle.update_dict_with_add_dim(Data_plant_flex_d_within_window_electrolyzer, Data_plant_flex_d_within_window, scenario_name)


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

    # ----------------------------------- EV data--------------------------------------------------

    rep_plant_name = "V2G_CH"

    # Read the EV data
    # The new data structure: EV_demand_weekly contains 100% of EV consumption
    # share_of_flexibly_charging_EV determines inflexible vs flexible split
    # V2G_share_of_flexibly_charging_EV determines V2G vs non-V2G split within flexible
    EV_weekly_energy_consumption_data_TYNDP = read_EV_weekly_energy_consumption_data(run_year, share_of_flexibly_charging_EV, V2G_share_of_flexibly_charging_EV)
    EV_charging_power_rate_TYNDP, V2G_charge_power_rate_TYNDP = read_EV_and_V2G_charging_power_rate(run_year, rep_plant_name, share_of_flexibly_charging_EV, V2G_share_of_flexibly_charging_EV, share_of_available_charging_capacity_for_V2G)
    
    # Read inflexible EV demand (portion of EVs that charge according to fixed profile)
    # This is added to the energy balance as a fixed demand, not as a storage_charge plant
    EV_inflexible_demand_TYNDP = read_EV_inflexible_demand_data(run_year, share_of_flexibly_charging_EV, node="CH00")
    
    # Add flexible EV plant (optimizable within weekly sum constraint)
    # Inflexible EV is handled as a parameter in the energy balance, not as a plant
    Plant_list_TYNDP.append("CH00_EV_flex")
    Map_plant_node.update({"CH00_EV_flex": "CH00"})
    Map_plant_tech.update({"CH00_EV_flex": "ev_flex"})

    # Add the raw imported data to the global dictionaries
    dle.update_dict_with_add_dim(EV_weekly_energy_consumption_data_TYNDP, EV_weekly_energy_consumption_data, scenario_name)
    dle.update_dict_with_add_dim(EV_charging_power_rate_TYNDP, EV_charging_power_rate, scenario_name)
    dle.update_dict_with_add_dim(EV_inflexible_demand_TYNDP, EV_inflexible_demand_data, scenario_name)
    
    # -----------------------------------  V2G data ------------------------------------------------

    # Read the V2G data
    # V2G_outflow represents the consumption pattern of V2G fleet (scaled to V2G portion only)
    V2G_outflow_TYNDP = read_V2G_data_outflow(run_year, rep_plant_name, share_of_flexibly_charging_EV, V2G_share_of_flexibly_charging_EV)
    # V2G_charge_power_rate_TYNDP = read_V2G_charge_power_rate(run_year, rep_plant_name)
    V2G_storage_capacity_scen = read_V2G_storage_capacity(run_year, ch_policy, rep_plant_name, share_of_flexibly_charging_EV, V2G_share_of_flexibly_charging_EV)
    # add "V2G_CH" to Plant_list
    Plant_list_TYNDP.extend([rep_plant_name,])
    Map_plant_node.update({rep_plant_name: "CH00"})
    Map_plant_tech.update({rep_plant_name: "v2g"})
    Plant_outflow_list.extend([rep_plant_name])
    
    # Add the raw imported data to the global dictionaries
    dle.update_dict_with_add_dim(V2G_outflow_TYNDP, Outflow_data, scenario_name) # add V2G to dimension Outflow_data?
    dle.update_dict_with_add_dim(V2G_charge_power_rate_TYNDP, V2G_charging_power_rate, scenario_name)
    dle.update_dict_with_add_dim(V2G_storage_capacity_scen, V2G_storage_capacity, scenario_name)
    
    # ----------------------------------- fuel tracking data -------------------------------------
    Fuel_limits_CH_data_year_scenario = read_fuel_limit_data(
        ch_policy,
        run_year,
        limit_fuel_import_CH,
        limited_fuels_import_CH_list,
    )

    dle.update_dict_with_add_dim(Fuel_limits_CH_data_year_scenario, Fuel_limits_data, scenario_name)

    # ----------------------------------- heat pumps ----------------------------------------------

    # Read the archetype building data for the heat pumps of housholds
    BA_el_con, BA_th_con_TYNDP, BA_th_lim_TYNDP, COP_TYNDP, BA_names_TYNDP, BA_max_heating_capacity_TYNDP = read_building_archetypes(run_year, weather_year, flexible_household_heatpump_share_raw, heat_flexibility_Kelvin, heating_system="HP")
    # Please note that BA_el_con is not returned as a dict but as a pandas DataFrame

    dle.update_dict_with_add_dim(BA_th_con_TYNDP, BA_th_con, scenario_name)
    dle.update_dict_with_add_dim(BA_th_lim_TYNDP, BA_th_lim, scenario_name)
    dle.update_dict_with_add_dim(COP_TYNDP, COP, scenario_name)
    dle.extend_list_with_new_elements(BA_names_TYNDP, BA_names)
    dle.extend_list_with_new_elements(BA_names_TYNDP, Plant_list_TYNDP)
    dle.update_dict_with_add_dim(BA_max_heating_capacity_TYNDP, BA_max_heating_capacity, scenario_name)
    dle.extend_list_with_new_elements([flexible_household_heatpump_share_raw], flexible_household_heatpump_share)

    # Add the right maps to the newly added heat pump building archetypes
    Map_plant_node.update({name: "CH00" for name in BA_names})
    Map_plant_tech.update({name: "heat_pump_households" for name in BA_names})

    # Read inflexible household heat pump demand (portion of HPs that operate according to fixed profile)
    # This is added to the energy balance as a fixed demand, separate from flexible HP consumption
    HP_inflexible_demand_TYNDP = read_HP_inflexible_demand_data(BA_el_con, flexible_household_heatpump_share_raw, node="CH00")
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

    # ----------------------------------- district heating data -----------------------------------
    # disrict heating demand data
    DemandDH_data_year_scenario = read_demandDH_data(run_year, weather_year, reduce_DH_demand_by)

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
    
    KVAinfeed_raw = read_KVA_infeed_data()
    dle.update_dict_with_add_dim(KVAinfeed_raw, KVAinfeed, scenario_name)

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

    # check if there is any cross-mismatch issue
    Plant_capacity_missing = cross_match_plant_list(Plant_list_nonhydro_capacity_gen, Plant_list_nonhydro)
    # remove all elements of  Plant_capacity_missing from Plant_list_TYNDP
    print("Plants with no reported capacity in input data are assigned capacity of 0 as default ... \n", Plant_capacity_missing) if Plant_capacity_missing else None
    for plant in Plant_capacity_missing:
        Plant_capacity_gen[plant] = 0

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


