import pyomo.environ as pyo
from pyomo.environ import Set, Param, Var, Constraint
from model.structural_parameters import (
    Map_plant_tech_cost_component,
    tech_p_no_gen,
    tech_hydro_list,
    tech_store_list,
    tech_store_pump_list,
    tech_store_equal_pump_max_gen_max_list,
    tech_limited_energy_and_require_storage_inv_no_soc,
    techDH_connected_to_electric_grid_list,
    Map_fuel_tech,
    Map_tech_fuel,
    fuel_limited_CH_list,
    TES_techs_list,
)
from model.structural_parameters import (
    tech_demand_assets_shiftable_netflex_list,
    tech_demand_assets_shiftable,
    Map_tech_startcondition,
    cost_data_opr_qdr,
    tech_infeed_all_list,
)

# from settings_run import T_list, Node_list, Consumer_list_netflex, opt_mode
from data_prep.definitions_common import (
    lost_load_cost,
    Data_plant_energy_limited,
    LineATC_list,
    Demand_data,
    Map_plant_tech,
    Map_plant_node,
    Plant_inflow_list,
    Plant_outflow_list,
    cost_data_opr_slp,
    cost_data_inv_gen_slp,
    cost_data_inv_e_slp,
    op_cost_n_tech_calibration,
    gen_max_RES_pre_existing_no_NETFLEX,
    Map_infeedplant_tech,
    Map_infeedplant_node,
    Infeedplant_list,
    Plant_investment_RES_CH_list,
    Plant_investment_non_RES_CH_list,
    Plant_investment_RES_CH_data,
    DemandDH_data, 
    Map_plantDH_nodeEl,
    Map_plantDH_nodeDH,
    Map_plantDH_tech,
    Map_nodeDH_plantDH,
    PlantDH_data_remaining,
    Plant_capacity_gen,
    Plant_capacity_pmp,
    Plant_capacity_strg,
    PlantDH_capacity,
    EV_weekly_energy_consumption_data,
    EV_charging_power_rate,
    EV_inflexible_demand_data,
    HP_inflexible_demand_data,
    Fuel_limits_data,    
    BA_th_con,
    BA_th_lim,
    COP,
    BA_names,
    PlantDH_investment_STES_list,
    Plant_investment_data_STES,
    BA_max_heating_capacity,
    cost_data_inv_fuel_storage_slp,
    V2G_charging_power_rate,
    V2G_storage_capacity,
    storage_to_charge_ratio,
    cost_data_inv_discharge_slp,
    flexible_household_heatpump_share,
    KVAinfeed,
    emission_factor_per_MWh,
)
from data_prep.definitions_common import (
    Map_eff_in_plant,
    Map_eff_out_plant,
    Plant_list,
    Map_plant_startcondition,
    Outflow_data,
    Avail_plant,
    Map_consumer_optimization,
    Infeed_consumers,
    Map_node_plant,
    Map_node_consumer,
    P_list_fuelswitching_plants
)
from data_prep.definitions_common import (
    Map_node_exportinglineATC,
    Map_node_importinglineATC,
    Data_plant_flex_d_within_window,
    ATC_importlimit,
    ATC_exportlimit,
)

# needed for core.py
from data_prep.definitions_common import (
    scenario_name,
    Map_line_node,
    Map_eff_in_plant,
    Map_eff_out_plant,
    Inflow_data,
    Line_trade_price,
)

from model.data_import_fcns import map_tech_to_plant
import time
import numpy as np
import input.cost_operation_invest_data as operational_data
import model.mappings as mappings
import pandas as pd
import math


# -----------------------------------------------------------------------------------------------------------
# --------------------------------------- define objective function -----------------------------------------
# -----------------------------------------------------------------------------------------------------------


def obj_expression(model):
    #NOTE: divided into 2 parts, electric and thermal side
    # investment cost to be defined over plants - stored as model attributes for export
    model.cost_inv_dict = {}
    # operation cost to be defined over plants
    model.cost_op_dict = {}
    # lost load cost to be defined over consumers and scenarios
    model.lostload_cost_dict = {}
    # slack cost
    model.slack_cost_dict = {}
    # operation cost on the thermal side
    model.cost_op_thermal_dict = {}
    # investment cost on the thermal side
    model.cost_inv_thermal_dict = {}
    # investment cost of the fuel storage 
    model.cost_inv_fuel_storage_dict = {}
    # trade cost for CH_only mode (neighbor electricity trade)
    model.trade_cost_dict = {}
    # CO2 emissions per plant and scenario (for reporting, not in objective)
    model.emissions_dict = {}

    for scen in model.Scenarios:
        # part 1: -------------------------------------------------------------------------------------------------------------------------------------
        for p in model.P: #these are Ps that have a electric side
            if p in model.P_gen:
                tech_typ_gen_e = Map_plant_tech_cost_component[Map_plant_tech[p]]
                if tech_typ_gen_e == "cap_op":
                    
                    # investment cost ----------------------------------------------------
                    # currently, model.investment_genmax_slp[p]/10000  is arbitrary, it should be replaced by the quadratic cost of the plant
                    if p in model.P_allinv | model.PDH_allinvTh:
                        model.cost_inv_dict[p,scen] = model.weight_in_objective_fcn[scen] * model.investment_genmax_slp[p,scen] * model.gen_max[p,scen] #+ \
                                        #model.weight_in_objective_fcn[scen] * model.investment_genmax_slp[p,scen]/100000/10/1/1 *  model.gen_max[p,scen] *  model.gen_max[p,scen]
                        # investment cost is divided by the number of scenarios because given that run_year is identical for all scenarios (so far) ...
                        # without this coefficient, one investment will be counted twice. Note that later we fix gen_max to be the same among scenarios.
                        # This is not the case for operation cost, lost load cost, and slack cost
                    # operation cost ----------------------------------------------------
                    model.cost_op_dict[p,scen] = model.weight_in_objective_fcn[scen] * sum(
                        [
                            # slope cost
                            model.operation_slp[p, scen] * model.gen[p, t, scen]
                            # quadratic cost
                            #+ model.operation_qdr[p, scen] * model.gen[p, t, scen] ** 2
                            for t in model.T
                            if p in model.P_gen
                        ]
                    )
                    # CO2 emissions (tCO2) - for reporting only, not in objective
                    model.emissions_dict[p, scen] = sum(
                        [
                            model.emission_factor_per_MWh[p, scen] * model.gen[p, t, scen]
                            for t in model.T
                        ]
                    )
                elif tech_typ_gen_e == "cap_op_energy":

                    # investment cost 
                    if p in model.P_allinv:
                        if p in model.P_fuellimCH: # in case of fuel limited plants (e.g., biomass), investment in energy storage is taken care of in fuel storage investment now
                            model.cost_inv_dict[p,scen] = model.weight_in_objective_fcn[scen] * (
                                model.investment_genmax_slp[p, scen] * model.gen_max[p, scen]
                            )
                        if p not in model.P_fuellimCH:
                            model.cost_inv_dict[p,scen] = model.weight_in_objective_fcn[scen] * (
                                model.investment_genmax_slp[p, scen] * model.gen_max[p, scen]
                                + model.investment_emax_slp[p, scen] * model.gen_energy_max[p, scen]
                            )
                        if p == "CH00_hydrogen": # Hydrogen has distinct facilities for the charging and discharging and that's why it is treated seperately.
                            model.cost_inv_dict[p,scen] = model.weight_in_objective_fcn[scen] * (
                            model.investment_genmax_slp[p, scen] * model.gen_max[p, scen]
                            + model.investment_emax_slp[p, scen] * model.gen_energy_max[p, scen]
                            + model.cost_data_inv_discharge_slp[p, scen] * model.pmp_max[p, scen] # for now, always 0 except for hydrogen.
                            )
                    # operation cost
                    model.cost_op_dict[p,scen] = model.weight_in_objective_fcn[scen] * sum(
                        [
                            model.operation_slp[p, scen] * model.gen[p, t, scen]
                            for t in model.T
                            if p in model.P_gen
                        ]
                    )
                    # CO2 emissions (tCO2) - for reporting only, not in objective
                    model.emissions_dict[p, scen] = sum(
                        [
                            model.emission_factor_per_MWh[p, scen] * model.gen[p, t, scen]
                            for t in model.T
                        ]
                    )

        # lost load cost
        model.lostload_cost_dict[scen] = model.weight_in_objective_fcn[scen] * sum(
            [
                model.lostload[c, t, lostload_step, scen] * model.lostload_cost_per_step[lostload_step, scen]
                for c in model.Consumer
                for t in model.T
                for lostload_step in model.lostLoad_step
            ]
        )

        # slack cost
        if hasattr(model, "slack_soc") and model.slack_soc:
            slack_cost_coeff = 1000000
            model.slack_cost_dict[scen] = model.weight_in_objective_fcn[scen] * slack_cost_coeff * sum(
                model.slackSOC_POS[p, t, scen] + model.slackSOC_NEG[p, t, scen]
                for p in model.P_storage
                for t in model.T
            )
        else:
            model.slack_cost_dict[scen] = 0
        
        # add a small cost for storage_charge in plants with limmited energy (to avoid using charging of the fuel storage (e.g., hydrogen) instead of electric curtailment)
        # NOTE: if eventually an actual operation cost of charging storage is meant to be implemented, the value of penalty_storage_charge should be read from cost data of the technology
        penalty_storage_charge = 0.1
        # for plants that are in both model.P_allinv and model.P_fuellimCH, add a penalty for using the storage_charge
        for p in model.P_fuellimCH & model.P_pumping: # possibly only hydrogen
            print(p)
            model.cost_op_dict[p, scen] = model.cost_op_dict[p, scen] + model.weight_in_objective_fcn[scen] * sum(
                [
                    penalty_storage_charge * model.storage_charge[p, t, scen]
                    for t in model.T
                ]
            )
        # part 2: Thermal side (if they didn't have a electric side ------------------------------------------------------------------------------------------------------------------------------------
        # thermal side investment cost
        # for p_thermal in model.PDH_costExclusivelyOnThermalSide: 
        for p_thermal in model.PDH_allinvTh:
            tech_typ_gen_e = Map_plant_tech_cost_component[Map_plant_tech[p_thermal]]
            if tech_typ_gen_e == "cap_op":
                model.cost_inv_thermal_dict[p_thermal, scen] = model.weight_in_objective_fcn[scen] * model.investment_genmax_slpTh[p_thermal,scen] * model.genTh_max[p_thermal,scen]
            elif tech_typ_gen_e == "cap_op_energy":
                model.cost_inv_thermal_dict[p_thermal, scen] = model.weight_in_objective_fcn[scen] * (
                    model.investment_genmax_slpTh[p_thermal, scen] * model.genTh_max[p_thermal, scen]
                    + model.investment_emax_slpTh[p_thermal, scen] * model.gen_energyTh_max[p_thermal, scen]
                )
            
        # thermal side operation cost 
        for p_thermal in model.PDH_costExclusivelyOnThermalSide:
            model.cost_op_thermal_dict[p_thermal, scen] = model.weight_in_objective_fcn[scen] * sum(
                [
                    model.operation_slpTh[p_thermal, scen] * model.genTh[p_thermal, t, scen]
                    for t in model.T
                ]
            )
        # part 3: fuel side ----------------------------------------------------------------------------------------------------------------------------------
        for f in model.Fuels_limited:
            model.cost_inv_fuel_storage_dict[f,scen] = model.weight_in_objective_fcn[scen] * model.fuel_storage_capacity_annual[f, scen] * model.investment_fuel_storage_slp[f,scen]

        # part 4: trade cost for CH_only mode (neighbor electricity trade) ----------------------------------------------------------------------
        # Trade cost calculation considering line direction relative to CH00
        # Only calculate if Line_trade_price has non-zero values (i.e., we're in CH_only mode)
        if Line_trade_price:
            # Import to CH00 (CH00 as ending node): positive Export = CH imports (cost, positive cost)  
            import_cost = sum(
                [
                    model.line_trade_price[line, t, scen] * model.Export[line, t, scen]
                    for line in model.lineATC & set(Map_node_importinglineATC.get("CH00", []))
                    for t in model.T
                ]
            )
            # Export from CH00 (CH00 as starting node): positive Export = CH exports (revenue, negative cost)
            export_gain = sum(
                [
                    model.line_trade_price[line, t, scen] * model.Export[line, t, scen]
                    for line in model.lineATC & set(Map_node_exportinglineATC.get("CH00", []))
                    for t in model.T
                ]
            )

            model.trade_cost_dict[scen] = model.weight_in_objective_fcn[scen] * (import_cost - export_gain)
        else:
            model.trade_cost_dict[scen] = 0

    # add thermal curtailment penalty, to avoid curtailment of thermal energy in district heating plants if not necessary
    thermal_curtailment_penalty_rate = 1.1 # non-zero to avoid curtailment of thermal energy in district heating  which eventually may distor RES curtailment / should be higher than operational cost[s] of STES 
    # # add thermal curtailment penalty, to avoid curtailment of thermal energy in district heating plants if not necessary
    thermal_curtailment_penalty = thermal_curtailment_penalty_rate * sum(
        [
            model.curtailmentTh[n, t, scen] 
            for n in model.NodeDH
            for t in model.T
        ]
    )        
    return sum(model.cost_inv_dict.values()) + sum(model.cost_op_dict.values()) + sum(model.lostload_cost_dict.values()) + sum(model.slack_cost_dict.values()) + sum(model.cost_inv_thermal_dict.values()) + sum(model.cost_op_thermal_dict.values()) + sum(model.cost_inv_fuel_storage_dict.values()) + sum(model.trade_cost_dict.values()) + thermal_curtailment_penalty  #+ thermal_curtailment_penalty


# -----------------------------------------------------------------------------------------------------------
# ----------------------------------------- define sets ----------------------------------------------------
# -----------------------------------------------------------------------------------------------------------


def define_sets(
    model,
    Plant_list_included,
    consumer_sel,
    consumer_infeed_sel,
    tech_infeed_selected,
    T_list,
    Node_list,
    Consumer_list_netflex,
    tech_demand_modeled,
    tech_demand_inflex_selected,
    sub_scenarios_list,
    NodeDH_list,
    PlantDH_list,
):
    """
    Define sets for the model (used in both for consumer runs and central runs).
    Inputs:
        model: pyomo model
        Plant_list_included: list of plants that are included in the model
        consumer_sel: list of consumers that are included in the model
        consumer_infeed_sel: list of consumers that are included in the model and have infeed
        - in central opt with direct load control: NETFLEX + TYNDP consumers
        - in consumer's individual opt: the consumer itself
        - in central run after consumer's individual opt: TYNDP consumers
        tech_infeed_selected: list of infeed technologies of consumers ("pv")
        T_list: list of time steps in the model
        Node_list: list of nodes in the model
        Consumer_list_netflex: list of consumers in NETFLEX
        tech_demand_modeled: list of demand side technologies that are included in the model (e.g., ["fixed", "hp", "v1g", "v2g"])
        tech_demand_inflex_selected: list of demand side technologies that are included in the model and are inflexible (e.g., ["fixed"])
    """
    model.T = Set(initialize=T_list, ordered=True, doc="time steps in the model")

    # set of days (as day of the year) in the model, e.g., 274, 275,...,365, 1, 2, 3, 4,...,273
    starting_day = int(str(list(model.T)[0]).split("_")[1]) // 24 + 1
    ending_day = int(str(list(model.T)[-1]).split("_")[1]) // 24

    if ending_day > starting_day:
        model.Days = Set(
            initialize=range(starting_day, ending_day + 1),
            ordered=True,
            doc="days in the model, e.g., 274, 275,...,365, 1, 2, 3, 4,...,273",
        )
    elif ending_day < starting_day:
        model.Days = Set(
            initialize=list(range(starting_day, 365 + 1))
            + list(range(1, ending_day + 1)),
            ordered=True,
            doc="days in the model, e.g., 274, 275,...,365, 1, 2, 3, 4,...,273",
        )
    elif ending_day == starting_day:
        model.Days = Set(
            initialize=[starting_day],
            ordered=True,
            doc="days in the model, e.g., 274, 275,...,365, 1, 2, 3, 4,...,273",
        )

    # define model.Week for the given time steps, and match it using timemaps_hydro_year.csv
    # read the csv file
    time_maps_hydro_full = pd.read_csv("input/timemaps_hydro_year.csv")
    # in time_maps_hydro, only keep the rows if the time step (column hour) is in model.T 
    time_maps_hydro = time_maps_hydro_full[time_maps_hydro_full["t"].isin(model.T)]
    # model.Week is equal to the unique values in the column "week" in time_maps_hydro, initialize it with the unique values in the column "week" in time_maps_hydro
    model.Week = Set(
        initialize=list(time_maps_hydro["week"].unique()),
        ordered=True,
        doc="weeks in the model",
    )

    # store a mapping of week to corresponding time steps (model.T) in model.Map_week_t
    model.Map_week_t = Param(
        model.Week,
        initialize={week: list(time_maps_hydro[time_maps_hydro["week"] == week]["hour"]) for week in model.Week},
        within=pyo.Any,
        doc="mapping of week to corresponding time steps",
    )
    
    # store a mapping of week to ALL time steps in that week (not filtered by model.T)
    # This is needed for calculating the fraction of a week that is being modeled (for partial week runs)
    model.Map_week_t_full = Param(
        model.Week,
        initialize={week: list(time_maps_hydro_full[time_maps_hydro_full["week"] == week]["hour"]) for week in model.Week},
        within=pyo.Any,
        doc="mapping of week to ALL time steps in that week (unfiltered, for partial week calculations)",
    )

    model.Map_t_week = Param(
        model.T,
        initialize={t: time_maps_hydro[time_maps_hydro["hour"] == t]["week"].values[0] for t in model.T},
        within=pyo.Any,
        doc="mapping of time steps to corresponding week",
    )

    # node set
    model.Node = Set(initialize=Node_list, doc="set of nodes")

    model.Consumer = Set(initialize=consumer_sel, doc=" set of consumers")

    # model.Consumer_NETFLEX = Set(
    #     initialize=Consumer_list_netflex, doc=" set of <all> consumers in NETFLEX"
    # )

    model.Consumer_with_infeed = Set(
        initialize=consumer_infeed_sel,
        within=model.Consumer,
        doc="set of consumers whose infeed is directly considered modeled in energy balance",
    )

    model.lineATC = Set(
        initialize=LineATC_list,
        doc="set of interconnections of ATC between regions",
    )

    model.P = Set(
        initialize= [p for p in Plant_list_included if Map_plant_node[p] in model.Node],
        doc="set of plants (including district heating plants connected to the electric grid)",
    )

    model.P_gen = Set(
        initialize=[p for p in model.P if Map_plant_tech[p] not in tech_p_no_gen],
        doc="set of plants that can generate",
    )
    model.P_hydro = Set(
        initialize=[p for p in model.P if Map_plant_tech[p] in tech_hydro_list],
        doc="set of hydro plants",
    )

    model.P_fuellimCH = Set( # set of plants whose fuel availability is limited (thier fuel in fuel_limited_CH_list) and are in CH (Map_node_country[Map_plant_node[p]] == "CH")
        initialize=[p for p in model.P if Map_plant_tech[p] in Map_tech_fuel and Map_tech_fuel[Map_plant_tech[p]] in fuel_limited_CH_list and mappings.Map_node_country[Map_plant_node[p]] == "CH"],
        within=model.P,
        doc="set of plants with limited fuel availability that are located in CH",
    )
    
    model.P_ev = Set(
            initialize=[p for p in model.P if Map_plant_tech[p] in ["v2g"]],
            within=model.P,
            doc="set of EV plants",
        )

    model.P_evV2G = Set(
        initialize=[p for p in model.P if Map_plant_tech[p] == "v2g"],
        within=model.P_ev,
        doc="set of V2G EV plants",
    )

    model.P_energymax = Set(
        initialize=[
            p
            for p in model.P
            if Map_plant_tech_cost_component[Map_plant_tech[p]] == "cap_op_energy"
            if p not in model.P_fuellimCH
        ],
        within=model.P,
        doc="plants with some limit on energy (but not fuel storage), e.g., batteries",
    )

    model.P_energylim = Set(
        initialize=[p for p in model.P if p in {key[0] for key in Data_plant_energy_limited.keys()}],
        within=model.P,
        doc="plants with a limit on total production in a given period, e.g., some biofuels",
    )


    model.P_storage = Set(
        initialize=[p for p in model.P if Map_plant_tech[p] in tech_store_list],
        within=model.P,
        doc="set of storage plants (it does not include plants that turn electricity into fuel, e.g., excludes hydrogen storage)",
    )

    model.P_storage_noSOC = Set(
        initialize=[p for p in model.P if Map_plant_tech[p] in tech_limited_energy_and_require_storage_inv_no_soc],
        within=model.P,
        doc="set of liquid fuel plants (need investment in storage capcity, but no need to follow its state of the charge)",
    )

    model.P_pumping = Set(
        initialize=[p for p in model.P if Map_plant_tech[p] in tech_store_pump_list],
        within=model.P,
        doc="set of storage plants that can pump, i.e., can use energy directly (e.g., heat pumps, EVs) or indirectly for storing (e.g., batteries, hydroge storage)",
    )

    model.P_dsr = Set(
        initialize=[p for p in model.P if Map_plant_tech[p] == "dsr"],
        doc="set of demand side response assets",
        within=model.P,
    )

    model.P_inflow = Set(
        initialize=[p for p in model.P if p in Plant_inflow_list],
        within=model.P_storage,
        doc="set of storage plants with inflow/outflow, e.g., of type hydro or EV",
    )

    model.P_outflow = Set(
        initialize=[p for p in model.P if p in Plant_outflow_list],
        within=model.P_storage,
        doc="set of storage plants with outflow, e.g., V2G EV",
    )

    model.P_equal_p_g_max = Set(
        initialize=[
            p
            for p in model.P
            if Map_plant_tech[p] in tech_store_equal_pump_max_gen_max_list
        ],
        within=model.P_storage,
        doc="set of storage plants that will have equal pumping and generating capacity",
    )

    model.P_flex_d_within_window = Set(
        initialize=[
            p for p in model.P if Map_plant_tech[p] in tech_demand_assets_shiftable
        ],
        within=model.P_pumping,
        doc="set of storage plants that can flexibly discharge within a given time window",
    )

    model.P_allinv = Set(
        initialize=[p for p in model.P if p in Plant_investment_RES_CH_list+Plant_investment_non_RES_CH_list+PlantDH_investment_STES_list],
        within=model.P,
        doc="set of all candidate power plants that can be invested in CH, connected to the electric grid",
    )

    model.P_allinvnotinPfuellimCH = Set(
        initialize=[p for p in model.P if p in model.P_allinv and p not in model.P_fuellimCH],
        within=model.P,
        doc="set of all candidate power plants that can be invested in CH, excluding fuel limited plants (e.g., batteries, pv, wind, nuclear)",
    )
    
    model.P_fuelswitching = Set(
        initialize=[p for p in model.P if p in P_list_fuelswitching_plants],
        within=model.P,
        doc="set of fuel switching plants",
    )


    model.P_RESinv = Set(
        initialize=[p for p in model.P if p in Plant_investment_RES_CH_list],
        within=model.P,
        doc="set of RES candidate power plants that can be invested in CH",
    )

    model.P_convinv = Set(
        initialize=[p for p in model.P if p in Plant_investment_non_RES_CH_list],
        within=model.P,
        doc="set of conventional candidate power plants (non-RES) that can be invested in CH",
    )
    # defined as a list of unique values in the dictionary Map_plant_tech for the keys 'p' in model.P
    model.Tech_gen = Set(
        initialize=list(
            set(Map_plant_tech[key] for key in model.P if key in Map_plant_tech)
        ),
        doc="set of technologies that are in the model and can generate (no infeed technology)",
    )

    model.Tech_hydro = Set(
        initialize=tech_hydro_list, doc="set of technologies that are hydro"
    )
    model.Tech_infeed = Set(
        initialize=tech_infeed_selected,
        doc="set of technologies that can be used for infeed to consumers",
    )

    # model.Consumption_times_series_types = Set(
    #     initialize=tech_demand_time_series,
    #     doc="set of consuming technologies/types that have time series and will be saved in model.demand (not always used in the model)",
    # )
    model.Consumption_types = Set(
        initialize=tech_demand_modeled,
        doc="set of consuming technologies/types (e.g., in NETFLEX mode, fixed and ev etc. and in core, fixed country demand)",
    )

    model.Consumption_types_inflex = Set(
        initialize=tech_demand_inflex_selected,
        within=model.Consumption_types,
        doc="set of consuming technologies/types whose demand are fixed to input data",
    )

    model.Infeedp = Set(
        initialize=[p for p in Infeedplant_list if Map_infeedplant_node[p] in model.Node],
        doc="set of plants",
    )

    model.Fuels_limited = Set(
        initialize=[f for f in fuel_limited_CH_list],
        doc="set of fuels",
    )
    # multi scenario constraints
    model.Scenarios = Set(
        initialize=sub_scenarios_list, doc="scenarios that are run in the model"
    )
    
    model.lostLoad_step = Set(
        initialize=lost_load_cost[sub_scenarios_list[0]].keys(),
        ordered=True,
        doc="steps for lost load cost",
    )
    # ------------------------------------ district heating modelling -------------------------------------
    model.NodeDH = Set(
        initialize=[ndh for ndh in NodeDH_list],
        doc="set of district heating nodes",
    )

    model.PDH = Set(
        initialize=[pdh for pdh in PlantDH_list if Map_plantDH_nodeDH[pdh] in model.NodeDH],
        doc = "set of district heating plants - including only the plants that are in the modelled district heating nodes",
    )

    model.PDH_resistive = Set(
        initialize=[pdh for pdh in model.PDH if Map_plantDH_tech[pdh] in ["resistive_heater"]],
        doc="set of resistive district heating plants",
        within=model.PDH,
    )

    model.PDH_heatpump = Set(
        initialize=[pdh for pdh in model.PDH if Map_plantDH_tech[pdh] in ["heat_pump"]],
        doc="set of heat pump district heating plants",
        within=model.PDH,
    )

    model.PDH_TES = Set(
        initialize=[pdh for pdh in model.PDH if Map_plantDH_tech[pdh] in TES_techs_list],
        doc="set of thermal energy storage assets in district heating plants",
        within=model.PDH,
    )

    model.PDH_storage = Set(
        initialize=[pdh for pdh in model.PDH if Map_plantDH_tech[pdh] in tech_store_list],
        doc="set of storage district heating plants",
        within=model.PDH,
    )

    model.PDH_CHP = Set(
        initialize=[pdh for pdh in model.PDH if PlantDH_data_remaining[pdh,"CHPDH", list(model.Scenarios)[0]]==True],	
        doc="set of CHP plants in district heating",
        within=model.PDH,
    )

    model.PDH_dsr = Set(
        initialize=[p for p in model.PDH if Map_plant_tech[p] == "dsrTh"],
        doc="set of demand side response assets",
        within=model.PDH,
    )

    model.P_fuellimCH_DH = Set(
        initialize=[p for p in model.PDH if Map_plantDH_tech[p] in Map_tech_fuel and Map_tech_fuel[Map_plantDH_tech[p]] in fuel_limited_CH_list if p not in model.P_fuellimCH],
        within=model.PDH,
        doc="set of district heating plants with limited fuel availability",
    )

    model.PDH_costExclusivelyOnThermalSide = Set( #check if dsr is in
        initialize=[p for p in model.PDH if Map_plantDH_nodeEl[p] == "na"],
        doc="set of district heating plants that have costs exclusively on the thermal side, e.g., STES, thermal plant (Important: other plants'investment cost is calculated on their electric side)",
        within=model.PDH,
    )

    # define model.PDH_storage_charge as the union of model.PDH_storage and model.PDH_dsr
    model.PDH_storagecharge = Set(
        initialize=[p for p in (model.PDH_storage)] + [p for p in (model.PDH_dsr)],
        doc="set of storage district heating plants that can charge",
    )

    model.PDH_allinvTh = Set(
        initialize=[p for p in model.PDH if p in PlantDH_investment_STES_list],
        within=model.PDH,
        doc="set of all candidate power plants that can be invested in CH",
    )


    # ------------------------------------ heat pump modeling -------------------------------------
    # ------------------------------------ David's attempt ----------------------------------------

    model.BA_names = Set(
        initialize=[ba for ba in BA_names],
        doc = "set of Building Archetypes for the heat pump modeling of the households",
    )
        
    return model
    # model.Consumption_types_flex = Set(
    #     initialize=[
    #         tech
    #         for tech in model.Consumption_types
    #         if tech not in model.Consumption_types_inflex
    #     ],
    #     within=model.Consumption_types,
    #     doc="set of consuming technologies/types whose demand are flexible",
    # )


# --------------------------------------------------------------------------------------------------------------
# ----------------------------------------- define parameters -------------------------------------------------
# --------------------------------------------------------------------------------------------------------------


def define_params_op(model, resistive_heater_investment_cap_MW_total):
    """
    Define parameters for the model as attributes (used in both for consumer runs and central runs).
    Inputs:
        model: pyomo model
    """
    # Import per-constraint scaling factors and expose as a mutable Param
    try:
        from model.constraint_scaling import constraint_scaling as _constraint_scaling
    except Exception:
        # Fallback for relative import if package layout differs
        from .constraint_scaling import constraint_scaling as _constraint_scaling

    model.ConstraintNames = pyo.Set(
        initialize=list(_constraint_scaling.keys()),
        doc="Names of constraints for row scaling"
    )
    model.constraint_scaling = Param(
        model.ConstraintNames,
        initialize=_constraint_scaling,
        mutable=True,
        within=pyo.PositiveReals,
        doc="Row scaling factor per constraint (applied symmetrically to both sides)",
    )
    model.demand = Param(
        model.Consumer,
        model.Consumption_types_inflex,
        model.T,
        model.Scenarios,
        initialize=lambda model, consumer, tech, t, scen : Demand_data[(consumer, tech, t, scen)],
        doc="demand time series per consumer and time step",
    )

    # EV inflexible demand parameter - stored separately for visualization purposes
    # This represents the portion of EV consumption that follows a fixed charging profile (not optimizable)
    # Keys are (Node, T, Scenario) tuples
    model.EV_inflexible_demand = Param(
        model.Node,
        model.T,
        model.Scenarios,
        initialize=lambda model, node, t, scen: EV_inflexible_demand_data.get((node, t, scen), 0),
        default=0,
        doc="Inflexible EV demand time series per node and time step [MWh]. This is the portion of EV consumption that charges according to a fixed profile.",
    )

    # HP inflexible demand parameter - stored separately for visualization purposes
    # This represents the portion of household heat pump consumption that operates according to a fixed profile (not participating in flexibility)
    # Keys are (Node, T, Scenario) tuples
    model.HP_inflexible_demand = Param(
        model.Node,
        model.T,
        model.Scenarios,
        initialize=lambda model, node, t, scen: HP_inflexible_demand_data.get((node, t, scen), 0),
        default=0,
        doc="Inflexible household heat pump demand time series per node and time step [MWh]. This is the portion of HP consumption that follows a fixed profile.",
    )

    model.operation_slp = Param(
        model.P_gen,
        model.Scenarios,
        initialize={
            (p,scen) : cost_data_opr_slp[Map_plant_tech[p],scen]
            * (
                op_cost_n_tech_calibration.get(
                    (Map_plant_node[p], Map_plant_tech[p], scen), 1  # Default to 1 if the no cost calibration is available in op_cost_calibration.csv
                )
            )
            for p in model.P_gen
            for scen in model.Scenarios
        },
    )

    model.operation_slpTh = Param(
        model.PDH_costExclusivelyOnThermalSide,
        model.Scenarios,
        initialize={
            (p,scen) : cost_data_opr_slp[Map_plantDH_tech[p],scen]
            * (
                op_cost_n_tech_calibration.get(
                    (Map_plantDH_nodeDH[p], Map_plantDH_tech[p], scen), 1  # Default to 1 if the no cost calibration is available in op_cost_calibration.csv
                )
            )
            for p in model.PDH_costExclusivelyOnThermalSide
            for scen in model.Scenarios
        },
        doc = "operation costs on the thermal side of assets with thermal consumption capability - mainly to be used in the objective function to avoid unwanted dsrTh and TES operation",
    )

    model.operation_qdr = Param(
        model.P_gen,
        model.Scenarios,
        initialize={(p,scen): cost_data_opr_qdr[Map_plant_tech[p]] for p in model.P_gen for scen in model.Scenarios},
    )
    # in reading parameter above, scen is not used as it is the same for all scenarios

    # Emission factor per MWh of electricity output (tCO2/MWh_elec)
    # This accounts for plant efficiency: emission_factor_input / efficiency
    model.emission_factor_per_MWh = Param(
        model.P_gen,
        model.Scenarios,
        initialize={
            (p, scen): emission_factor_per_MWh.get((Map_plant_tech[p], scen), 0)
            for p in model.P_gen
            for scen in model.Scenarios
        },
        default=0,
        doc="CO2 emission factor per MWh of electricity output (tCO2/MWh_elec), already accounting for efficiency",
    )

    model.storage_charge_eff_in = Param(
        model.P_storage | model.PDH_storage,
        model.Scenarios,
        initialize={(p,scen): Map_eff_in_plant[p] for p in model.P_storage | model.PDH_storage for scen in model.Scenarios},
        doc="efficiency while charging ([0,1])",
    )
    # in reading parameter above, scen is not used as it is the same for all scenarios

    model.storage_charge_eff_out = Param(
        model.P_storage | model.PDH_storage,
        model.Scenarios,
        initialize={(p,scen): Map_eff_out_plant[p] for p in model.P_storage | model.PDH_storage for scen in model.Scenarios},
        doc="efficiency while discharging ([0,1])",
    )
    # in reading parameter above, scen is not used as it is the same for all scenarios

    # NOTE: lines below are commented out because the decay rate is modelled only for TES in model.TES_decayrate
    # model.storage_charge_decay_rate = Param(
    #     model.P_storage | model.PDH_storage,
    #     model.Scenarios,
    #     initialize={(p,scen): 1 for p in model.P_storage | model.PDH_storage for scen in model.Scenarios},
    #     doc="storage charge decay rate ([0,1])",
    # )

    model.storage_start_cond = Param(
        model.P_storage, #  | model.PDH_storage is taken out, because it is not considered as a constraint anymore (only start and end condition of thermal storage needs to be equal)
        model.Scenarios,
        initialize={(p, scen): Map_plant_startcondition[p] for p in model.P_storage for scen in model.Scenarios},
        doc="initial/end state of charge ([0,1])",
    )
    # in reading parameter above, scen is not used as it is the same for all scenarios

    model.inflow = Param(
        model.P_inflow,
        model.T,
        model.Scenarios,
        initialize={(p, t, scen): Inflow_data[p, t, scen] for p in model.P_inflow for t in model.T for scen in model.Scenarios},
        doc="inflows from storage plants (MWh",
    )

    model.outflow = Param(
        model.P_outflow,
        model.T,
        model.Scenarios,
        initialize={(p, t, scen): Outflow_data[p, t, scen] for p in model.P_outflow for t in model.T for scen in model.Scenarios},
        doc="outflows from storage plants (MWh",
    )  # adjust set to analyze only EVs and similar

    model.avail_plant = Param(
        model.P | model.PDH,
        model.T,
        model.Scenarios,
        initialize={(p, t, scen): Avail_plant[p, t, scen] for p in model.P | model.PDH for t in model.T for scen in model.Scenarios},
        doc="availability of plants ([0,1])]",
    )

    model.infeed = Param(
        model.Consumer_with_infeed,
        model.Tech_infeed,
        model.T,
        model.Scenarios,
        initialize=lambda model, n, tech, t, scen: Infeed_consumers.get((n, tech, t, scen), 0)
        if (n, tech, t, scen) in Infeed_consumers
        else 0,
        doc="fixed sum of infeed from e.g. PVs (MWh), 0 infeed if a consumer has no value in Infeed_consumers",
    )

    model.lostload_cost_per_step = Param(
        model.lostLoad_step,
        model.Scenarios,
        initialize={(step, scen): lost_load_cost[scen][step]['cost_EUR_per_MWh'] for step in model.lostLoad_step for scen in model.Scenarios},
        doc="cost of lost load for each step (EUR/MWh)",
    )

    model.lostload_capacity_per_step = Param(
        model.lostLoad_step,
        model.Scenarios,
        initialize={(step, scen): lost_load_cost[scen][step]['capacity_MWh'] for step in model.lostLoad_step for scen in model.Scenarios},
        doc="capacity of lost load for each step (MWh)",
    )

    model.Map_node_plant = Param(
        model.Node,
        initialize={n: Map_node_plant[n] for n in model.Node},
        within=pyo.Any,
        doc="map of plants to nodes (including district heating plants)",
    )

    model.Map_node_consumer = Param(
        model.Node,
        initialize={n: Map_node_consumer[n] for n in model.Node},
        within=pyo.Any,
        doc="map of consumers to nodes",
    )

    model.Map_node_exportinglineATC = Param(
        model.Node,
        initialize={n: Map_node_exportinglineATC[n] for n in model.Node},
        within=pyo.Any,
        doc="map of nodes to exporting lines",
    )

    model.Map_node_importinglineATC = Param(
        model.Node,
        initialize={n: Map_node_importinglineATC[n] for n in model.Node},
        within=pyo.Any,
        doc="map of nodes to importing lines",
    )

    model.Map_plant_tech = Param(
        model.P,
        initialize={p: Map_plant_tech[p] for p in model.P},
        doc="map of plants",
        within=pyo.Any,
    )

    model.P_fuellimCH_plus_P_fuellimCH_DH = Set(
        initialize=[p for p in model.P_fuellimCH | model.P_fuellimCH_DH],
        doc="set of plants with limited fuel availability in CH",
    )

    model.Map_plant_fuel = Param(
        model.P_fuellimCH_plus_P_fuellimCH_DH,
        initialize={p: Map_tech_fuel[Map_plant_tech[p]] for p in model.P_fuellimCH_plus_P_fuellimCH_DH},
        doc="map of plants to fuels",
        within=pyo.Any,
    )

    # model.Map_fuel_plant is the inverse of model.Map_plant_fuel
    model.Map_fuel_plant = Param(
        model.Fuels_limited,
        initialize={f: [p for p in model.P_fuellimCH_plus_P_fuellimCH_DH if Map_tech_fuel[Map_plant_tech[p]] == f] for f in model.Fuels_limited},
        doc="map of fuels to plants located in CH",
        within=pyo.Any,
    )

    model.Map_plant_efficiency_gen = Param(
        model.P_fuellimCH_plus_P_fuellimCH_DH,
        model.Scenarios,
        initialize={(p, scen): Map_eff_out_plant[p] for p in model.P_fuellimCH_plus_P_fuellimCH_DH for scen in model.Scenarios},
        within=pyo.NonNegativeReals,
        doc="generation efficiency of power plants ([0,1]), only tracked for plants that require fuel tracking (for reporting purposes)",
    )
    
    model.fuel_import_capacity_annual = Param(
        model.Fuels_limited,
        model.Scenarios,
        initialize={(f,s): Fuel_limits_data[(f,s)]["import_capacity_annual"] for f in model.Fuels_limited for s in model.Scenarios},
        within=pyo.NonNegativeReals,
        doc="annual fuel import capacity (MWh)",
    )

    model.fuel_production_capacity_CH_annual = Param(
        model.Fuels_limited,
        model.Scenarios,
        initialize={(f, s): Fuel_limits_data.get((f, s), {}).get("production_capacity_CH", 0) for f in model.Fuels_limited for s in model.Scenarios},
        within=pyo.NonNegativeReals,
        doc="annual fuel import capacity (MWh)",
    )

    model.Map_node_country = Param(
        model.Node,
        initialize={n: mappings.Map_node_country[n] for n in model.Node},
        within=pyo.Any,
        doc="map of nodes to countries",
    )

    model.Data_plant_flex_d_within_window = Param(
        model.P_flex_d_within_window,
        model.Scenarios,
        initialize={
            (p, scen): Data_plant_flex_d_within_window[p, scen] for p in model.P_flex_d_within_window for scen in model.Scenarios
        },
        within=pyo.Any,
        doc="flexibility of plants within a given time window (MWh)",
    )

    model.sum_generation_plant_energy_limited = Param(
        model.P_energylim,
        model.Scenarios,
        initialize={(p, scen): Data_plant_energy_limited[p,scen] for p in model.P_energylim for scen in model.Scenarios},
        doc="sum of energy limited generation (MWh)",
    )

    model.resplant = Set(
        initialize=[p for p in model.P if Map_plant_tech[p] in ["pv", "wind"]],
        doc="set of RES plants",
    )

    # creating data related to infeeds, later to be reported, to be used in reporting/aggregating the results
    model.gen_max_infeedp = Param(
        model.Infeedp,
        model.Scenarios,
        # the value is defined over infeed plants defined in Map_plant_tech_res, and the 
        initialize={(p, scen): gen_max_RES_pre_existing_no_NETFLEX[p,scen] for p in model.Infeedp for scen in model.Scenarios if (p,scen) in gen_max_RES_pre_existing_no_NETFLEX},
        # Map_infeedplant_tech
        # Map_infeedplant_node
        # initialize={
        #     p: gen_max_RES_pre_existing_no_NETFLEX[p] if model.Map_plant_tech[p] in tech_infeed_all_list else 0
        #     for p in gen_max_RES_pre_existing_no_NETFLEX
        # },
        doc="maximum generation capacity of pre-existing RES plants (MWh) - ROR missing because the dataset does not mention capacity",
    )

    model.Map_infeedplant_tech = Param(
        model.Infeedp,
        initialize={p: Map_infeedplant_tech[p] for p in model.Infeedp},
        within=pyo.Any,
        doc="map of infeed plants to technologies",
    )

    model.Map_infeedplant_node = Param(
        model.Infeedp,
        initialize={p: Map_infeedplant_node[p] for p in model.Infeedp},
        within=pyo.Any,
        doc="map of infeed plants to nodes",
    )

    model.gen_max_limit = Param(
        model.P_allinv,
        initialize={p: float(Plant_investment_RES_CH_data["gen_max_limit"][p]) for p in model.P_allinv},
        doc="maximum generation capacity of RES plants that can be invested in CH (MW)",
    )

    model.energy_max_limit = Param(
        model.P_allinv,
        initialize={p: float(Plant_investment_RES_CH_data["energy_max_limit"][p]) for p in model.P_allinv},
        doc="maximum energy capacity of RES plants that can be invested in CH (MWh)",
    )

    model.dsrThDev_max = Param(
        model.PDH_dsr,
        model.Scenarios,
        initialize={(p, scen): PlantDH_capacity[p, scen]*flexible_household_heatpump_share[0] for p in model.PDH_dsr for scen in model.Scenarios},
        doc="maximum capacity of dsrTh (MWh)",
    )
    
    # Resistive heater investment cap per node (MW)
    model.resistive_heater_cap_MW_total = Param(
        within=pyo.Any,
        initialize=resistive_heater_investment_cap_MW_total,
        doc="Maximum total investment capacity in resistive heaters across all nodes (MW)",
    )
    model.demandDH = Param(
        model.NodeDH,
        model.T,
        model.Scenarios,
        initialize=lambda model, dhnodes, t, scen : DemandDH_data[(dhnodes, t, scen)],
        doc=" demnad time series per district heating node and time step",
    )

    model.Map_plantDH_nodeEl = Param(
        model.PDH,
        initialize={pdh: Map_plantDH_nodeEl[pdh] for pdh in model.PDH},
        within=pyo.Any,
        doc="map of district heating plants to electricity nodes",
    )

    model.Map_plantDH_nodeDH = Param(
        model.PDH,
        initialize={pdh: Map_plantDH_nodeDH[pdh] for pdh in model.PDH},
        within=pyo.Any,
        doc="map of district heating plants to district heating nodes",
    )

    model.Map_plantDH_tech = Param(
        model.PDH,
        initialize={pdh: Map_plantDH_tech[pdh] for pdh in model.PDH},
        within=pyo.Any,
        doc="map of district heating plants to technologies",
    )

    model.Map_nodeDH_plantDH = Param(
        model.NodeDH,
        initialize={ndh: Map_nodeDH_plantDH[ndh] for ndh in model.NodeDH},
        within=pyo.Any,
        doc="map of district heating nodes to district heating plants",
    )

    # define model.Map_plantTES_tech on model.PDH_TES and initialize it with PlantDH_data_remaining[pdh,"TES_type", scen] where scen does not matter (use any element in model.Scenarios)
    model.Map_plantTES_tech = Param(
        model.PDH_TES,
        initialize={pdh: PlantDH_data_remaining[pdh,"TES_type", list(model.Scenarios)[0]] for pdh in model.PDH_TES},
        within=pyo.Any,
        doc="map of thermal energy storage assets in district heating plants to TES technologies",
    )

    model.TES_decayrate = Param(
        model.PDH_TES,
        initialize={pdh: 1-(1-PlantDH_data_remaining[pdh,"self_discharge_per_day_percent", list(model.Scenarios)[0]]/100)**(1/24) for pdh in model.PDH_TES},
        within=pyo.Any,
        doc="TES decay rate ([0,1])",
    )

    model.genTh_max_limit = Param(
        model.PDH_allinvTh, #NOTE: is the right set?
        initialize={p: float(Plant_investment_data_STES["gen_max_limit"][p]) for p in model.PDH_allinvTh},
        doc="maximum generation capacity of thermal energy storage assets that can be invested in CH (MWh thermal)",
    )

    model.energyTh_max_limit = Param(
        model.PDH_allinvTh,
        initialize={p: float(Plant_investment_data_STES["energy_max_limit"][p]) for p in model.PDH_allinvTh},
        doc="maximum energy capacity of thermal energy storage assets that can be invested in CH (MWh thermal)",
    )

    # model.TES_charge_eff = Param(
    #     model.PDH_TES,
    #     initialize={pdh: PlantDH_data_remaining[pdh,"TES_charge_efficiecy", list(model.Scenarios)[0]] for pdh in model.PDH_TES},
    #     within=pyo.Any,
    #     doc="TES charge efficiency ([0,1])",
    # )

    # model.TES_discharge_eff = Param(
    #     model.PDH_TES,
    #     initialize={pdh: PlantDH_data_remaining[pdh,"TES_discharge_efficiecy", list(model.Scenarios)[0]] for pdh in model.PDH_TES},
    #     within=pyo.Any,
    #     doc="TES discharge efficiency ([0,1])",
    # )

    # ------------------------------------ heat pump modeling -------------------------------------

    model.BA_th_lim = Param(
        model.BA_names,
        model.Scenarios,
        initialize={(ba, scen): BA_th_lim[(ba,scen)] for ba in model.BA_names for scen in model.Scenarios},
        within=pyo.Any,
        doc="minimum and maximal thermal energy levels that the individual building archetypes can reach",
    )

    model.COP = Param(
        model.T,
        model.BA_names,
        model.Scenarios,
        initialize={
            (t, ba, scen): 0 if BA_th_con[(ba, scen)][t] == 0 else COP[(ba, scen)][t] # It is set to zero because if BA_th_con != 0 while COP = 0, there can be infeasibility in the execution
            for t in model.T
            for ba in model.BA_names
            for scen in model.Scenarios
        },
        within=pyo.Any,
        doc="coefficient of Performance of the heat pumps for each hour",
    )

    model.BA_max_heating_capacity = Param(
        model.BA_names,
        model.Scenarios,
        initialize={(ba, scen): BA_max_heating_capacity[(ba,scen)] for ba in model.BA_names for scen in model.Scenarios},
        within=pyo.Any,
        doc="maximum heating capacity of the individual building archetypes",
    )

    model.BA_th_con = Param(
        model.T,
        model.BA_names,
        model.Scenarios,
        initialize={(t, ba, scen): BA_th_con[(ba,scen)][t] for t in model.T for ba in model.BA_names for scen in model.Scenarios},
        within=pyo.Any,
        doc="thermal consumption of the individual building archetypes",
    )

    # ------------------------------------  V2G modeling -------------------------------------
    model.V2G_charging_power_rate = Param(
        model.P_evV2G,
        model.T,
        model.Scenarios,
        initialize={(p, t, scen): V2G_charging_power_rate[p,t, scen] for p in model.P_evV2G for t in model.T for scen in model.Scenarios},
        within=pyo.NonNegativeReals,
        doc="charging power rate of V2G EVs (MW)",
    )

    model.V2G_storage_capacity = Param(
        model.P_evV2G,
        model.Scenarios,
        initialize={(p, scen): V2G_storage_capacity[p, scen] for p in model.P_evV2G for scen in model.Scenarios},
        within=pyo.NonNegativeReals,
        doc="battery capacity of V2G EVs (MWh)",
    )

    # Line trade prices for CH_only mode (empty if not in CH_only mode)
    model.line_trade_price = Param(
        model.lineATC,
        model.T,
        model.Scenarios,
        initialize={(line, t, scen): Line_trade_price.get((line, t, scen), 0) for line in model.lineATC for t in model.T for scen in model.Scenarios},
        within=pyo.NonNegativeReals,
        doc="neighbor electricity prices for trade lines in CH_only mode (EUR/MWh)",
    )

    return model

def define_params_inv(model, weight_in_objective_fcn, resistive_heater_investment_cap_MW_total):
    """
    Define investment cost parameters for the model as attributes.
    """
    model.investment_genmax_slp = Param(
        model.P, # NOTE add  | model.PDH if district heating plants are included
        model.Scenarios,
        initialize={(p,scen): cost_data_inv_gen_slp[Map_plant_tech[p], scen] for p in model.P for scen in model.Scenarios},
    )

    model.investment_emax_slp = Param(
        model.P_energymax, # NOTE add  | model.PDH if district heating plants are included
        model.Scenarios,
        initialize={
            (p, scen): cost_data_inv_e_slp[Map_plant_tech[p], scen] for p in model.P_energymax for scen in model.Scenarios
        },
    )

    model.weight_in_objective_fcn = Param(
        model.Scenarios,
        initialize=weight_in_objective_fcn,
        doc="weight of each scenario in the objective function",
    )

    # ------------------------------------ district heating modelling -------------------------------------
    model.investment_genmax_slpTh = Param(
        model.PDH,
        model.Scenarios,
        initialize={
            (p, scen): cost_data_inv_gen_slp[Map_plantDH_tech[p], scen] for p in model.PDH for scen in model.Scenarios
        },
    )

    model.investment_emax_slpTh = Param(
        model.PDH,
        model.Scenarios,
        initialize={
            (p, scen): cost_data_inv_e_slp[Map_plantDH_tech[p], scen] for p in model.PDH for scen in model.Scenarios
        },
    )

    # ------------------------------------ fuel storage modelling -------------------------------------
    # initialize the investment cost of fuel storage capacity, if Fuel_limits_data[("f","scen")]["storage_potential_capacity"] exists, use it, if not, 0
    model.fuel_storage_investment_annual_limit = Param(
        model.Fuels_limited,
        model.Scenarios,
        initialize={(f, scen): Fuel_limits_data.get((f, scen), {}).get("storage_potential_capacity", 0) for f in model.Fuels_limited for scen in model.Scenarios},
        within=pyo.NonNegativeReals,
        doc="maximum investment allowed in fuel storage capacity (MWh)",    #NOTE: in the input files, make sure about the units
        
    )

    model.investment_fuel_storage_slp = Param(
        model.Fuels_limited,
        model.Scenarios,
        initialize={(f, scen): cost_data_inv_fuel_storage_slp[f, scen] for f in model.Fuels_limited for scen in model.Scenarios},
        doc = "investment cost of fuel storage capacity (EUR/MWh) in CH",
    )

    model.cost_data_inv_discharge_slp = Param(
        model.P,
        model.Scenarios,
        initialize={(p, scen): cost_data_inv_discharge_slp.get((Map_plant_tech[p], scen), 0) for p in model.P for scen in model.Scenarios},
        doc = "investment cost of fuel discharge capacity (CHF/MWh) in CH. Only relevant for fuel storages that have a discharge capacity that is considered differently from the charging capacity (now only hydrogen)",
    )
    return model


# ----------------------------------------------------------------------------------------------------------------
# ------------------------------------------ define variables ---------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------


def define_vars_op(model):
    """
    Define variables for the model as attributes (used in both for consumer runs and central runs).
    Inputs:
        model: pyomo model
    """
    model.gen = Var(
        model.P_gen,
        model.T,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="generation (discharge of storage plant) (MWh)",
    )

    model.soc = Var(
        model.P_storage,
        model.T,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="state of the charge (MWh)",
    )

    model.storage_charge = Var(
        model.P_pumping,
        model.T,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="energy used to charge storage plant p in t (MWh) - charging or pumping",
    )

    model.exported = Var(
        model.Consumer,
        model.T,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="consumer's exported value (MWh)",
    )

    model.imported = Var(
        model.Consumer,
        model.T,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="consumer's imported value (MWh)",
    )

    model.lostload = Var(
        model.Consumer,
        model.T,
        model.lostLoad_step,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="lost load (MWh)",
    )

    model.curtailment = Var(
        model.Consumer_with_infeed,
        model.T,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="consumers' curtailment of RES generation (MWh) - used in consumer optimization",
    )

    if hasattr(model, "slack_soc") and model.slack_soc:
        print("slack_soc is True ...................... defining SOC slack variables")
        model.slackSOC_POS = Var(
            model.P_storage | model.PDH_storage,
            model.T,
            model.Scenarios,
            initialize=0,
            domain=pyo.NonNegativeReals,
            doc="positive slack variable for storeBalance_Constraint",
        )

        model.slackSOC_NEG = Var(
            model.P_storage | model.PDH_storage,
            model.T,
            model.Scenarios,
            initialize=0,
            domain=pyo.NonNegativeReals,
            doc="negative slack variable for storeBalance_Constraint",
        )

    model.spill_water = Var(
        model.P_hydro,
        model.T,
        model.Scenarios,
        initialize=0,
        domain=pyo.NonNegativeReals,
        doc="slack variable allowing for spilling water in hydro plants to avoid infeasibility caused by storage capacity limit",
    )

    model.Export = Var(
        model.lineATC,
        model.T,
        model.Scenarios,
        domain=pyo.Reals,
        initialize=0,
        doc="exported value on a line (ATC) from start node to end node - negative values specify imports - (MWh)",
    ) 

    model.fuel_consumption_of_plant = Var(
        model.P_fuellimCH_plus_P_fuellimCH_DH,
        model.T,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="fuel consumption of fuel limited plants (MWh)",
    )

    model.fuel_consumption_of_fuel = Var(
        model.Fuels_limited,
        model.T,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="fuel consumption of fuels (MWh)",
    )
    # ------------------------------------ district heating modelling -------------------------------------
    model.genTh = Var(
        model.PDH,
        model.T,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="thermal generation / supply of thermal assets (MWh)",
    )

    model.storage_chargeTh = Var(
        model.PDH_storagecharge,
        model.T,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="energy used to charge storage plant p in t (MWh) - charging or pumping",
    )

    model.socTh = Var(
        model.PDH_TES,
        model.T,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="state of the charge (MWh thermal)",
    )

    model.curtailmentTh = Var(
        model.NodeDH,
        model.T,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="curtailed thermal energy, i.e., thermal energy supplied by a CHP that is not delivered to a consumer (e.g., when electricity energy is needed, but the thermal generation is not to be used) (MWh)",
    )

    model.dsrThDev = Var(
        model.PDH_dsr,
        model.T,
        model.Scenarios,
        domain=pyo.Reals,
        initialize=0,
        doc= "records the deviation of the representative building's thermal energy level from the target level (that is needed for the comfort temperature) [MWh thermal]",
    )

    # ------------------------------------ heat pumps modeling -------------------------------------

    model.th_sl = Var(
        model.T,
        model.BA_names,
        model.Scenarios,
        domain=pyo.Reals,
        initialize=0,
        # The bounds are set automatically to the thermal storage limits
        bounds=lambda model, t, ba, scen: (model.BA_th_lim[ba, scen]['negative_capacity_[MWh]'], model.BA_th_lim[ba, scen]['positive_capacity_[MWh]']),
        doc="THermal STorage level representing energywise the temperatur of the building respective to the inside comfort temperature [MWh]",
    )

    return model
    # model.curtail_node      = Var(model.Node,       model.T, domain=pyo.NonNegativeReals, initialize=0, doc= "nodes' curtailment of RES generation (MWh) - used for neighbours' nodes that have no consumer")


def define_vars_inv(model):
    """
    Define investment (generation and energy capacities) variables for the model as attributes (used in both for consumer runs and central runs).
    """
    model.gen_max = Var(
        model.P_gen,
        model.Scenarios, # if run_year of the sub_scenarios are the same, additional contraint should make sure that the same value is used for all sub_scenarios
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="maximum generation capacity (MW)",
    )

    model.pmp_max = Var(
        model.P_pumping,
        model.Scenarios, # if run_year of the sub_scenarios are the same, additional contraint should make sure that the same value is used for all sub_scenarios
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="maximum pumping capacity (MW)",
    )

    model.gen_energy_max = Var(
        model.P_energymax,
        model.Scenarios, # if run_year of the sub_scenarios are the same, additional contraint should make sure that the same value is used for all sub_scenarios
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="maximum storable energy (MWh) in a period/at each time step, for batteries it gives max soc, for biofuels it gives maximum energy avilable",
    )
    
    # ------------------------------------ district heating modelling -------------------------------------
    model.genTh_max = Var(
        model.PDH,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="maximum thermal generation capacity (MW thermal)",
    )

    model.pumpTh_max = Var(
        model.PDH,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="maximum pumping/consumption capacity (MW thermal)",
    )

    model.gen_energyTh_max = Var(
        model.PDH_TES,
        model.Scenarios,
        domain=pyo.NonNegativeReals,
        initialize=0,
        doc="maximum storable thermal energy (MWh) in a period/at each time step, for thermal storage it gives max storable thermal energy",
    )

    model.fuel_storage_capacity_annual = Var(
        model.Fuels_limited,
        model.Scenarios,
        initialize=0,
        within=pyo.NonNegativeReals,
        doc = "invested storage capacity of fuel storage (MWh of thermal energy)"
    )

    return model


# ---------------------------------------------------------------------------------------------------------------
# ---------------------------------------------- define constraints --------------------------------------------
# ---------------------------------------------------------------------------------------------------------------


def define_constraints(model):
    """
    Define constraints for the model as attributes (used in both for consumer runs and central runs).
    Inputs:
        model: pyomo model
    """

    print("defining constraints")

    # energy balance
    model.energy_balance = Constraint(
        model.T, model.Node, model.Scenarios, rule=energy_balance_Constraint
    )

    # Generation limit
    model.generation_limit = Constraint(
        model.P_gen, model.T, model.Scenarios, rule=generation_limit_Constraint
    )
    # print("generation_limit took:", time.time() - start, "seconds") if print_progress else None

    # Storage (battery/closed pump storage/hydrogen)
    model.storage_soc = Constraint(
        model.P_storage, model.T, model.Scenarios, rule=storeBalance_Constraint
    )
    # print("storage_soc took: ", time.time() - start, " seconds")

    # Storage start condition
    model.storage_start_condition = Constraint(
        model.P_storage, model.Scenarios, rule=storage_start_condition_Constraint
    )

    # Charge power limit (discharg/generation power is taken care of in generation_limit_Constraint)
    model.storage_rate_limit = Constraint(
        model.P_pumping, model.T, model.Scenarios, rule=storage_charge_Constraint
    )

    # equalizing the maximum generation capacity and the maximum charging rate
    model.p_max_limit = Constraint(model.P_equal_p_g_max, model.Scenarios, rule=p_max_limit_Constraint)
    # print("p_max_limit took: ", time.time() - start, " seconds")

    # energy limit of a storage plant  --- for limited energy technologies, we have energy_limit_Constraint
    model.storage_soc_limit = Constraint(
        model.P_storage, model.T, model.Scenarios, rule=storage_soc_Constraint
    )

    model.storage_total_fuel_limit = Constraint(
        model.P_storage_noSOC, model.Scenarios, rule=storage_total_fuel_limit_Constraint
    )

    model.lostload_limit = Constraint(
        model.Consumer,
        model.T,
        model.lostLoad_step,
        model.Scenarios,
        rule=lostload_limit_Constraint,
    )

    # Curtailment limit
    model.curtailment_limit = Constraint(
        model.Consumer_with_infeed, model.T, model.Scenarios, rule=curtailment_limit_Constraint
    )

    # Energy limit for limited_energy techs
    model.energy_limit = Constraint(model.P_energylim, model.Scenarios, rule=energy_limit_Constraint)

    model.energy_shift_limit_dsr_daily = Constraint(
        model.P_dsr, model.Days, model.Scenarios, rule=energy_shift_limit_dsr_daily_Constraint
    )

    model.dsr_daily_balance = Constraint(
        model.P_dsr, model.Days, model.Scenarios, rule=dsr_daily_balance_Constraint
    )
    # energy investment limits ---------------------------------------------------------------------
    model.gen_energy_max_limit_constraint = Constraint(
        model.P_allinvnotinPfuellimCH, model.Scenarios, rule=gen_energy_max_limit_Constraint #NOTE: depending on the candidate plants' features, this constraint could be empty
    )

    # investment in switching fuel plant ------------------------------------------------------------
    # # for all plants in P_fuelswitching, for all plants in model.P_fuelswitching, set gen_max[plants, scen] equal to each other
    # model.gen_max_fuelswitching_equal = Constraint(
    #     model.P_fuelswitching, model.Scenarios, rule=lambda model, p, scen: model.gen_max[p, scen] == model.gen_max[model.P_fuelswitching.first(), scen]
    # ) #NOTE: this approach is not the most parsimonious, but it is the most straightforward

    #NOTE: fuel switching plant investment cost - deactivated now
    # # set the value for capacity investment cost (in MW) of the second technology in the switching fuel plant to 0.1 of its investment cost from scratch (i.e., turning a plant to switching fuel plant costs 10% more than a single fuel plant)
    # for scen in model.Scenarios:
    #     model.investment_genmax_slp[model.P_fuelswitching.first(), scen] = 0.1 * model.investment_genmax_slp[model.P_fuelswitching.last(), scen] 
    #     #NOTE: this approach assumes only tow plants in P_fuelswitching
    #     # 0.1 is implying that investment in switching fuel plant is 1.1 times of a single fuel plant 

    # capacity investment limits -------------------------------------------------------------------
    model.gen_max_limit_constraint = Constraint(
        model.P_allinv, model.Scenarios, rule=gen_max_limit_Constraint
    )

    # line limits -----------------------------------------------------------------------------------
    model.lineATClimit = Constraint(
        model.lineATC, model.T, model.Scenarios, rule=ATCbound_Constraint
    )

    # fixing generation from new RES plants to maximum possible generation (gen_max * RES availability)
    # needed so that curtailment is calculated correctly
    Plant_to_fix_generation = [
        plant
        for plant in model.P
        if plant in Plant_investment_RES_CH_list and Map_plant_tech[plant] in tech_infeed_all_list
    ]

    model.infeedgen_fix = Constraint(
        Plant_to_fix_generation, model.T, model.Scenarios,
        rule=lambda model, p, t, s: (
            model.constraint_scaling['infeedgen_fix'] * model.gen[p, t, s]
            == model.constraint_scaling['infeedgen_fix'] * (model.gen_max[p, s] * model.avail_plant[p, t, s])
        ),
        doc="fixing generation from new RES plants to maximum possible generation (gen_max * RES availability), so that curtailment is calculated correctly",
    )

    # tracking fuel consumption 
    model.fuel_consumption_tracking = Constraint(
        model.Fuels_limited, model.T, model.Scenarios, rule=fuel_consumption_tracking_Constraint
    )

    model.plant_fuel_consumption_tracking_CH = Constraint(
        model.P_fuellimCH, model.T, model.Scenarios, rule=plant_fuel_consumption_tracking_CH_Constraint
    )

    model.plant_fuel_consumption_tracking_CH_DH = Constraint(
        model.P_fuellimCH_DH, model.T, model.Scenarios, rule=plant_fuel_consumption_tracking_CH_DH_Constraint
    )

    model.fuel_limit_annual = Constraint(
        model.Fuels_limited, model.Scenarios, rule=fuel_limit_annual_Constraint,
        doc = "limits annual fule consumption in CH to sum of annual import limit and storage limit"
    )

    # -------------------------------------------- multi scenario constraints -------------------------------------------

    #subcategory multi-year constraints (they are similar in fixing capacities of plants between subscearios - if later multi-year constraints are added, they should be changed so that capacities of later years are higher than capacities of earlier years)
    # add a constraint to the model that forces gen_max[p,scen] to be equal for all scnes in model.Scenarios, for all plants in set model.P
    model.gen_max_equal = Constraint(
        model.P_gen, model.Scenarios,
        rule=lambda model, p, scen: (
            model.constraint_scaling['gen_max_equal'] * model.gen_max[p, scen]
            == model.constraint_scaling['gen_max_equal'] * model.gen_max[p, model.Scenarios.first()]
        )
    ) 

    model.pmp_max_equal = Constraint(
        model.P_pumping, model.Scenarios, 
        rule=lambda model, p, scen: (
            (model.constraint_scaling['pmp_max_equal'] * model.pmp_max[p, scen]
             == model.constraint_scaling['pmp_max_equal'] * model.pmp_max[p, model.Scenarios.first()])
            if "hydrogen" in p else Constraint.Skip
        )
    )


    #NOTE :maybe more techs should be added to the list of techs that are equal in all scenarios
    #NOTE: move all multi-year constraints to a separate file
    model.gen_energy_max_equal = Constraint(
        model.P_storage_noSOC, model.Scenarios,
        rule=lambda model, p, scen: (
            model.constraint_scaling['gen_energy_max_equal'] * model.gen_energy_max[p, scen]
            == model.constraint_scaling['gen_energy_max_equal'] * model.gen_energy_max[p, model.Scenarios.first()]
        )
    ) 

    model.gen_energy_max_equal2 = Constraint(
        model.P_storage, model.Scenarios,
        rule=lambda model, p, scen: (
            model.constraint_scaling['gen_energy_max_equal2'] * model.gen_energy_max[p, scen]
            == model.constraint_scaling['gen_energy_max_equal2'] * model.gen_energy_max[p, model.Scenarios.first()]
        )
    )

    model.fuel_storage_capacity_annual_equal = Constraint(
        model.Fuels_limited, model.Scenarios,
        rule=lambda model, f, scen: (
            model.constraint_scaling['fuel_storage_capacity_annual_equal'] * model.fuel_storage_capacity_annual[f, scen]
            == model.constraint_scaling['fuel_storage_capacity_annual_equal'] * model.fuel_storage_capacity_annual[f, model.Scenarios.first()]
        )
    )

    # fix genTh_max to be equal for all scenarios
    model.genTh_max_equal = Constraint(
        model.PDH, model.Scenarios,
        rule=lambda model, p, scen: (
            model.constraint_scaling['genTh_max_equal'] * model.genTh_max[p, scen]
            == model.constraint_scaling['genTh_max_equal'] * model.genTh_max[p, model.Scenarios.first()]
        )
    )

    # fix gen_energyTh_max to be equal for all scenarios
    model.gen_energyTh_max_equal = Constraint(
        model.PDH_TES, model.Scenarios,
        rule=lambda model, p, scen: (
            model.constraint_scaling['gen_energyTh_max_equal'] * model.gen_energyTh_max[p, scen]
            == model.constraint_scaling['gen_energyTh_max_equal'] * model.gen_energyTh_max[p, model.Scenarios.first()]
        )
    )

    # ----------------------------------- district heating -----------------------------------
    # Generation limit
    model.generationTh_limit = Constraint(
        model.PDH, model.T, model.Scenarios, # model.genTh < model.genTh_max
        rule=generationTh_limit_Constraint
    )
    # # resistive heating capacity limit
    # model.storage_rate_limit_DH = Constraint(
    #     model.PDH, model.T, model.Scenarios, rule=storage_rate_limit_DH_Constraint
    # )

    # define the characteristics (the relationship between electric and thermal generation and consumption) of the all types of district heating plants
    # resisitve heating plants 
    model.heat_electric_profile_resistiveheater = Constraint(
        model.PDH_resistive, model.T, model.Scenarios, rule=heat_electric_profile_resistiveheater_Constraint
    )
    # heat pump plants - currently at fixed COP
    model.heat_electric_profile_heatpump = Constraint(
        model.PDH_heatpump, model.T, model.Scenarios, rule=heat_electric_profile_heatpump_Constraint
    )

    # CHP plants
    model.heat_electric_profile_CHP = Constraint(
        model.PDH_CHP, model.T, model.Scenarios, rule=heat_electric_profile_CHP_Constraint
    )

    # thermal energy balance (thermal balance) for district heating systems
    model.energy_balancethermal = Constraint(
        model.NodeDH, model.T, model.Scenarios, rule=energy_balancethermal_Constraint
    )

    # model.storageTh_start_condition = Constraint(
    #     model.PDH_storage, model.Scenarios, rule=storage_start_condition_Constraint
    # )

    model.storageTh_soc = Constraint(
        model.PDH_storage, model.T, model.Scenarios, rule=storeBalance_Constraint
    )

    model.storageTh_soc_limit = Constraint(
        model.PDH_storage, model.T, model.Scenarios, rule= storage_soc_Constraint
    )

    model.storageTh_rate_limit = Constraint(
        model.PDH_storage, model.T, model.Scenarios, rule=storage_charge_Constraint
    )

    model.pumpTh_max_leq_genTh_max = Constraint(
        model.PDH,
        model.Scenarios,
        rule=pump_less_than_gen_constraint,
        doc="For PTES or TTES: Pumping capacity must be ≤ thermal generation capacity."
    )

    # constraints for building flexibility in district heating -----------
    model.dsrth_thermal_energy_dev_tracking = Constraint(
        model.PDH_dsr, model.T, model.Scenarios, rule=dsrth_thermal_energy_dev_tracking
    )

    model.dsrTh_dev_limit = Constraint(
        model.PDH_dsr, model.T, model.Scenarios, rule=dsrTh_dev_limit_Constraint
    )

    model.dsrTh_dev_week_start_zero = Constraint(
        model.PDH_dsr, model.Week, model.Scenarios, rule=dsrTh_dev_week_start_zero_Constraint
    )

    model.dsrTh_dev_week_end_zero = Constraint(
        model.PDH_dsr, model.Week, model.Scenarios, rule=dsrTh_dev_week_end_zero_Constraint
    )

    model.dsrTh_dev_weekly_average_temp = Constraint(
        model.PDH_dsr, model.Week, model.Scenarios, rule=dsrTh_dev_weekly_average_temp_Constraint
    )

    model.inflexble_demandTh_share = Constraint(
        model.NodeDH, model.T, model.Scenarios, rule=inflexble_demandTh_share_Constraint
    )
    # thermal storage investment -----------------------------------------
    model.gen_energyTh_max_limit_constraint = Constraint(
        model.PDH_allinvTh, model.Scenarios, rule=gen_energyTh_max_limit_Constraint
    )

    model.genTh_max_limit_constraint = Constraint(
        model.PDH_allinvTh, model.Scenarios, rule=genTh_max_limit_Constraint
    )
    
    model.fix_storage_to_charge_ratio_PTES = Constraint(
        model.PDH_TES,
        model.Scenarios,
        rule=fix_storage_to_charge_ratio_PTES_Constraint,
    )
    # -------------------------------------------- EV modelling -------------------------------------------
    # Model the charging of flexible EVs (CH00_EV_flex)
    model.ev_consumption_weekly_sum = Constraint(
        model.Week, model.Scenarios, rule=ev_consumption_weekly_sum_Constraint 
    ) 

    model.ev_consumption_hourly_rate = Constraint(
        model.T, model.Scenarios, rule=ev_consumption_hourly_rate_Constraint
    )

    # --------------------------------------------  V2G modeling -------------------------------------------
    model.v2g_consumption_hourly_rate = Constraint(
        model.P_evV2G, model.T, model.Scenarios, rule=v2g_consumption_hourly_rate_Constraint
    )

    model.v2g_generation_hourly_rate = Constraint(
        model.P_evV2G, model.T, model.Scenarios, rule=v2g_generation_hourly_rate_Constraint
    )

    # -------------------------------------------- heat pump modeling -------------------------------------------
    # define the thermal storage (temperature) regulation of the building archetypes
    model.building_heat_demand = Constraint(
        model.T, model.BA_names, model.Scenarios, rule=building_heat_demand_Constraint
    )

    model.building_weekly_average = Constraint(
        model.Week, model.BA_names, model.Scenarios, rule=building_weekly_average_Constraint
    )

    model.max_heating_capacity = Constraint(
        model.T, model.BA_names, model.Scenarios, rule=max_heating_capacity_Constraint
    )

    # -------------------------------------------- fuel storage investment modeling -------------------------------------------
    # Add a constraint to limit investment capacity to values to model.fuel_storage_capacity_annual_investment_limit = Param(
        # model.Fuels_limited,
        # model.Scenarios,
    model.fuel_storage_capacity_annual_investment_limit = Constraint(
        model.Fuels_limited, model.Scenarios, rule=fuel_storage_capacity_annual_investment_limit_Constraint
    )
    
    # -------------------------------------------- resistive heater investment cap constraint -------------------------------------------
    # Limit total investment capacity of resistive heaters per node
    model.resistive_heater_investment_cap = Constraint(
        model.Scenarios,
        rule=resistive_heater_investment_cap_Constraint,
    )
        

    return model


# NOTE: activate lines below, only if for energy limited technologies, you want to limit sum of generation for multiple periods within a year
# # Generation limit for limited_energy techs ---------------------------------------------------------------
# # for every plant in P_energylim, and for every duration in form of tupple stored in Map_plant_duration[plant]["time_horizon"], we have a constraint that limits the energy stored in the plant
# # assuming you have already created your Pyomo model as 'model'
# for p, data in Data_plant_energy_limited.items():
#     if p in model.P_energylim:
#         for i, time_range in enumerate(data["time_horizon"]):
#             start, end = time_range
#             energy_limit = data["energy"][i]
#             # create the constraint
#             model.add_component(
#                 f"energy_limit_{p}_{i}",
#                 Constraint(
#                     expr=sum(model.gen[p, "t_" + str(t)] for t in range(
#                         start, end+1)) <= model.gen_energy_max[p]*energy_limit
#                 )
#             )


# ---------------------------------------------------------------------------------------------------------------
# ---------------------------------------------- constraints equations -----------------------------------------
# ---------------------------------------------------------------------------------------------------------------


# find the intersectino of a and b
def intersection(a, b):
    return list(set(a) & set(b))


# define a function that gets a list with several elements that are all strings, and returns the input if the input has multiple elements and returns [element] if the input has only one element


def list_to_list(input):
    if type(input) == list:
        return input
    else:
        return [input]



def fix_storage_to_charge_ratio_PTES_Constraint(model, p, s):
    """
    PTES plants have a fixed ratio of storage to charge capacity, i.e., it should take one month to fill up the sotage (at full capacity)
    Assumption given by HSLU.
    """	
    if "PTES" in model.Map_plantDH_tech[p]:
        return 24 * storage_to_charge_ratio[0] * model.genTh_max[p, s]  <=  model.gen_energyTh_max[p, s] 
    else:
        return pyo.Constraint.Skip

# energy balance


def energy_balance_Constraint(model, t, n, s):
    sf = model.constraint_scaling['energy_balance']
    # generatin from all technologies
    gen = sum(model.gen[p, t, s] for p in model.P_gen & model.Map_node_plant[n])
    # infeed from RES infeed technologies
    infeed = sum(
        model.infeed[c, tech, t, s]
        for c in model.Consumer_with_infeed & model.Map_node_consumer[n]
        for tech in model.Tech_infeed
    )
    demand_fixed = sum(
        model.demand[c, tech, t, s]
        for c in model.Consumer & model.Map_node_consumer[n]
        for tech in model.Consumption_types_inflex
    )
    # inflexible EV demand (added as fixed demand, not as storage_charge)
    demand_ev_inflexible = model.EV_inflexible_demand[n, t, s]
    # inflexible household heat pump demand (added as fixed demand, separate from flexible HP)
    demand_hp_inflexible = model.HP_inflexible_demand[n, t, s]
    # demand from all storage technologies, which includes pumping and charging etc.
    demand_storage = sum(
        model.storage_charge[p, t, s] for p in model.P_pumping & model.Map_node_plant[n]
    )
    lostload = sum(
        model.lostload[c, t, lostload_step, s]
        for c in model.Consumer & model.Map_node_consumer[n]
        for lostload_step in model.lostLoad_step
    )
    # positive means export, negative means import
    export_as_starting_node = sum(
        model.Export[l, t, s] for l in model.lineATC & model.Map_node_exportinglineATC[n]
    )
    # positive means import, negative means export
    import_as_ending_node = sum(
        model.Export[l, t, s] for l in model.lineATC & model.Map_node_importinglineATC[n]
    )
    # curtailment from all curtailment technologies
    curtailment = sum(
        model.curtailment[c, t, s]
        for c in model.Consumer_with_infeed & model.Map_node_consumer[n]
    )
        
    return (
        sf * (gen + infeed + import_as_ending_node + lostload)
        == sf * (demand_fixed + demand_ev_inflexible + demand_hp_inflexible + demand_storage + export_as_starting_node + curtailment)
    )


# Generation limit


def generation_limit_Constraint(model, p, t, s):
    sf = model.constraint_scaling['generation_limit']
    return sf * model.gen[p, t, s] <= sf * (model.gen_max[p, s] * model.avail_plant[p, t, s])


# Storage (battery/closed pump storage/hydrogen)


def storeBalance_Constraint(model, p, t, s):
    if p in model.P: # electricity side of the system
        sf = model.constraint_scaling['storage_soc']
        # state of charge at t
        soc_t = model.soc[p, t, s]

        # state of charge at t-1
        soc_t_1 = model.soc[p, model.T.prevw(t), s]

        # energy charged to the plant via pumping (only for specific plants model.P_pumping)
        charged = sum(
            [
                model.storage_charge[p, t, s] * model.storage_charge_eff_in[p, s]
                if p in model.P_pumping
                else 0
            ]
        )

        # energy discharged from the plant (plants with no generation are exluded, e.g., v1g EVs)
        discharged = sum(
            [model.gen[p, t, s] / model.storage_charge_eff_out[p, s] if p in model.P_gen else 0]
        )

        # inflow
        inflow = sum([model.inflow[p, t, s] if p in model.P_inflow else 0])

        # outflows
        outflow = sum([model.outflow[p, t, s] if p in model.P_outflow else 0])
        # if model.slack_soc exists and is True
        if hasattr(model, "slack_soc") and model.slack_soc:
            slack_pos = model.slackSOC_POS[p, t, s]
            slack_neg = model.slackSOC_NEG[p, t, s]
        else:
            slack_pos = 0
            slack_neg = 0

        # allow for spilling water
        spill_energy = sum([model.spill_water[p, t, s] if p in model.P_hydro else 0])
        
        return (
            sf * (soc_t + slack_neg)
            == sf * (soc_t_1 + charged - discharged + inflow - outflow + slack_pos - spill_energy)
        )
    
    elif p in model.PDH: # thermal side of the system
        sf = model.constraint_scaling['storageTh_soc']
        soc_t = model.socTh[p, t, s]
        soc_t_1 = model.socTh[p, model.T.prevw(t), s]
        charged = sum([model.storage_chargeTh[p, t, s] * model.storage_charge_eff_in[p, s]])
        discharged = sum([model.genTh[p, t, s] / model.storage_charge_eff_out[p, s]])

        if hasattr(model, "slack_soc") and model.slack_soc:
            slack_pos = model.slackSOC_POS[p, t, s]
            slack_neg = model.slackSOC_NEG[p, t, s]
        else:
            slack_pos = 0
            slack_neg = 0

        return (
            sf * (soc_t + slack_neg)
            == sf * ((1-model.TES_decayrate[p])*soc_t_1 + charged - discharged + slack_pos)
        )




def storage_start_condition_Constraint(model, p, s):
    sf = model.constraint_scaling['storage_start_condition']
    # if p in model.P:  # electricity side of the system
        # Generally, initial conditions of storage plants are equality constraints to a percentage of their maximum energy. This ensures, e.g., hydro plants reservior follows actual patterns.
        # Except for EVs: to avoid unnecessary constraints (and infeasilbity), initial condition is defined as inequality.
    if p in model.P_ev:
        return (
            sf * model.soc[p, model.T.at(1), s]
            <= sf * (model.storage_start_cond[p,s] * model.gen_energy_max[p,s])
        )
    else:
        return (
            sf * model.soc[p, model.T.at(1), s]
            == sf * (model.storage_start_cond[p,s] * model.gen_energy_max[p,s])
        )
    # elif p in model.PDH: # thermal side of the system
    #     # do not create a constraint
    #     return Constraint.Skip
    #     # return (
    #     #     model.socTh[p, model.T.at(1), s]
    #     #     == model.storage_start_cond[p, s] * model.gen_energyTh_max[p, s]
    #     # )


# Storage end condition


# def storage_end_condition_Constraint(model, p):
#     return (
#         model.soc[p, model.T.at(-1)]
#         == model.storage_end_cond[p] * model.gen_energy_max[p]
#     )


# charge power limit (discharg/generation power is taken care of in generation_limit_Constraint)


def storage_charge_Constraint(model, p, t, s):
    if p in model.P: # electricity side of the system
        sf = model.constraint_scaling['storage_rate_limit']
        if Map_plant_tech[p] in tech_demand_assets_shiftable:
            pmp_max_fixed = Data_plant_flex_d_within_window[p,s]["max_demand"]
            return sf * model.storage_charge[p, t, s] <= sf * (pmp_max_fixed * model.avail_plant[p, t, s])
        else:
            return sf * model.storage_charge[p, t, s] <= (
                sf * (model.pmp_max[p, s] * model.avail_plant[p, t, s])
        )
    elif p in model.PDH: # thermal side of the system
        sf = model.constraint_scaling['storageTh_rate_limit']
        return sf * model.storage_chargeTh[p, t, s] <= (
            sf * (model.pumpTh_max[p, s] * model.avail_plant[p, t, s])
        )


# equalizing the maximum generation capacity and the maximum charging rate


def p_max_limit_Constraint(model, p, s):
    sf = model.constraint_scaling['p_max_limit']
    if p == "CH00_hydrogen":
        # skip the constraint for hydrogen plant, so that electrolyzers and power plants burning hydrogen can have different capacities
        return Constraint.Skip
    else:
        return sf * model.pmp_max[p, s] <= sf * model.gen_max[p, s]


# energy limit of a storage plant  --- for limited energy technologies, we have energy_limit_Constraint


def storage_soc_Constraint(model, p, t, s):
    if p in model.P: # electricity side of the system

        if p in model.P_evV2G: # V2G EVs are singled out, because their availability for charging is time dependent.
            sf = model.constraint_scaling['storage_soc_limit']
            return sf * model.soc[p, t, s] <= sf * model.V2G_storage_capacity[p, s]
        else:
            sf = model.constraint_scaling['storage_soc_limit']
            return sf * model.soc[p, t, s] <= sf * model.gen_energy_max[p, s]
    
    elif p in model.PDH: # thermal side of the system
        sf = model.constraint_scaling['storageTh_soc_limit']
        return sf * model.socTh[p, t, s] <= sf * model.gen_energyTh_max[p, s]


# Generation limit for limited_energy techs --- for storage technologies, we have storage_soc_Constraint


def energy_limit_Constraint(model, p, s):
    sf = model.constraint_scaling['energy_limit']
    return (
        sf * sum([model.gen[p, t, s] for t in model.T])
        <= sf * model.sum_generation_plant_energy_limited[p,s]
    )

def storage_total_fuel_limit_Constraint(model, p, s):
    sf = model.constraint_scaling['storage_total_fuel_limit']
    return (
        sf * sum([model.gen[p, t, s] for t in model.T])
        <= sf * model.gen_energy_max[p, s]
    )
# NOTE: if multiple periods within a year is to be considered, then len(model.T)/8760 above should be adjusted.


# line limits


def ATCbound_Constraint(model, l, t, s):
    sf = model.constraint_scaling['lineATClimit']
    # NOTE: rethink if this is ok to simply assume 0, if the line is not in the dictionary
    # check if ATC_exportlimit[l, t] exists, if not, it is 0

    # NOTE temp fix for BE00-LU00 HVDC line
    if l == "HVAC_BE00_LU00":
        ATC_exportlimit[l, t, s] = ATC_exportlimit[l, t, s] + 1000

    upper_bound = ATC_exportlimit.get((l, t, s), 0)

    if (l, t, s) in ATC_importlimit:
        lower_bound = ATC_importlimit[l, t, s]
        if l == "HVAC_BE00_LU00":
            ATC_importlimit[l, t, s] = ATC_importlimit[l, t, s] + 1000
    else:
        if t == "t_1":
            print(
                f"ATC_importlimit has no l .{l}, t .{t}, s .{s}- export value {ATC_exportlimit.get((l, t, s), 0)} is used"
            )
        lower_bound = ATC_exportlimit.get((l, t, s), 0)
    # lower_bound = ATC_importlimit.get((l, t), 0)

    return (sf * -lower_bound, sf * model.Export[l, t, s], sf * upper_bound)

def fuel_consumption_tracking_Constraint(model, f, t, s):
    sf = model.constraint_scaling['fuel_consumption_tracking']
    return sf * model.fuel_consumption_of_fuel[f, t, s] == sf * (sum(
        model.fuel_consumption_of_plant[p, t, s] for p in model.P_fuellimCH if model.Map_plant_fuel[p] == f
    ) + sum(model.fuel_consumption_of_plant[p, t, s] for p in model.P_fuellimCH_DH if model.Map_plant_fuel[p] == f))

def plant_fuel_consumption_tracking_CH_Constraint(model, p, t, s):
    sf = model.constraint_scaling['plant_fuel_consumption_tracking_CH']
    return sf * model.fuel_consumption_of_plant[p, t, s] == sf * (model.gen[p, t, s] / model.Map_plant_efficiency_gen[p,s])

def plant_fuel_consumption_tracking_CH_DH_Constraint(model, p, t, s):
    sf = model.constraint_scaling['plant_fuel_consumption_tracking_CH_DH']
    return sf * model.fuel_consumption_of_plant[p, t, s] == sf * (model.genTh[p, t, s] / model.Map_plant_efficiency_gen[p,s])

def fuel_limit_annual_Constraint(model, f, s):
    sf = model.constraint_scaling['fuel_limit_annual']
    # Check if there are any plants in P_fuellimCH that match the fuel type
    relevant_plants = [p for p in model.P_fuellimCH_plus_P_fuellimCH_DH if model.Map_plant_fuel[p] == f]

    # If no relevant plants using the fuel, skip the constraint
    if not relevant_plants:
        return Constraint.Skip
    
    else:
        # Calculate the fuel consumption limit
        fuel_consumption_limit = (len(model.T) / 8760) * (
            model.fuel_import_capacity_annual[f, s]  +
            model.fuel_production_capacity_CH_annual[f, s] +
            model.fuel_storage_capacity_annual[f, s]   
        )
                    
        # Define the fuel consumption expression
        fuel_consumption = sum(
            model.fuel_consumption_of_fuel[f, t, s]
            for t in model.T
        )

        return sf * fuel_consumption <= sf * fuel_consumption_limit


def consumer_import_Constraint(model, c, t):
    sf = model.constraint_scaling['consumer_import']
    return sf * model.imported[c, t] <= sf * model.consumer_import_max[c, t]


def consumer_export_Constraint(model, c, t):
    sf = model.constraint_scaling['consumer_export']
    return sf * model.exported[c, t] <= sf * model.consumer_export_max[c, t]


def lostload_limit_Constraint(model, c, t, lostload_step, s):
    """
    Lost load is limited by the capacity of each step.
    """
    sf = model.constraint_scaling['lostload_limit']
    return sf * model.lostload[c, t, lostload_step, s] <= sf * model.lostload_capacity_per_step[lostload_step, s]


def curtailment_limit_Constraint(model, c, t, s):
    sf = model.constraint_scaling['curtailment_limit']
    # if sum or RES generation is positive (generating), then curtailment must be less than sum of RES generation.
    # if sum of RES generation is negative (which should not be possible), then max(0,sum(RES generation)) allows crutailment to be 0...
    # ... which is necessary because curtailment is defined as a non-negative variable.
    # NOTE: this should be later be avoided, by making sure that sum of RES generation is always positive, even after substracting consumers' infeed from main infeed.
    # node is equal to the node of the consumer, that is the key in model.Map_node_consumer that leads to c
    # Define node
    node = [k for k, v in model.Map_node_consumer.items() if c in v][0]
    return sf * model.curtailment[c, t, s] <= sf * (max(
        0, sum(model.infeed[c, tech, t, s] for tech in model.Tech_infeed)
        )) + sf * (sum(model.gen[p, t, s] for p in model.P_gen if p in Plant_investment_RES_CH_list if p in model.Map_node_plant[node]))



# DSR constraints
def energy_shift_limit_dsr_daily_Constraint(model, p, d, s):
    sf = model.constraint_scaling['energy_shift_limit_dsr_daily']
    day_hours = [t for t in model.T if (int(t.split("_")[1]) - 1) // 24 + 1 == d]
    sum_gen = sum(model.gen[p, t, s] for t in day_hours)
    sum_dem = sum(model.storage_charge[p, t, s] for t in day_hours)
    return sf * (sum_gen + sum_dem) <= sf * (3 * model.gen_max[p, s])


def dsr_daily_balance_Constraint(model, p, d, s):
    sf = model.constraint_scaling['dsr_daily_balance']
    day_hours = [t for t in model.T if (int(t.split("_")[1]) - 1) // 24 + 1 == d]
    sum_gen = sum(model.gen[p, t, s] for t in day_hours)
    sum_dem = sum(model.storage_charge[p, t, s] for t in day_hours)
    return sf * sum_gen == sf * sum_dem


def gen_energy_max_limit_Constraint(model, p, scen):
    sf = model.constraint_scaling['gen_energy_max_limit_constraint']
    if model.energy_max_limit[p] != float('inf'):
        return sf * model.gen_energy_max[p, scen] <= sf * model.energy_max_limit[p]
    else:
        return Constraint.Skip 


def gen_max_limit_Constraint(model, p, scen):
    sf = model.constraint_scaling['gen_max_limit_constraint']
    if model.gen_max_limit[p] != float('inf'):
        if p in model.P_gen:
            return sf * model.gen_max[p, scen] <= sf * model.gen_max_limit[p]
        else:
            return Constraint.Skip
    else:
        return Constraint.Skip         
# ----------------------------------- district heating -----------------------------------
def generationTh_limit_Constraint(model, p, t, s):
    sf = model.constraint_scaling['generationTh_limit']
    return sf * model.genTh[p, t, s] <= sf * model.genTh_max[p, s]

# define the characteristics (the relationship between electric and thermal generation and consumption) of the all types of district heating plants
def heat_electric_profile_resistiveheater_Constraint(model, p, t, s):
    """
    The heat generation of a resistive heater is equal to the efficiency of the resistive heater times the electric energy consumed (storage_charge).
    """
    sf = model.constraint_scaling['heat_electric_profile_resistiveheater']
    return sf * model.genTh[p, t, s] == sf * (PlantDH_data_remaining[p, "efficiency", s]*model.storage_charge[p, t, s])

def heat_electric_profile_heatpump_Constraint(model, p, t, s):
    """
    The heat generation of a heat pump is equal to the efficiency of the heat pump times the electric energy consumed (storage_charge).
    So far, a fixed COP is assumed for heat pumps.
    """
    sf = model.constraint_scaling['heat_electric_profile_heatpump']
    return sf * model.genTh[p, t, s] == sf * (PlantDH_data_remaining[p, "efficiency", s]*model.storage_charge[p, t, s])

def heat_electric_profile_CHP_Constraint(model, p, t, s):
    """
    The heat generation of a CHP plant is equal to electricical generation divided by power_to_heat_ratio. 
    Reminder: power_to_heat_ratio = (Electricity produced)/(Thermal energy produced)
    """
    sf = model.constraint_scaling['heat_electric_profile_CHP']
    return sf * model.genTh[p, t, s] == sf * (model.gen[p, t, s]/PlantDH_data_remaining[p, "power_to_heat_ratio", s])


# thermal energy balance (thermal balance) for district heating systems
def energy_balancethermal_Constraint(model, n, t, s):
    sf = model.constraint_scaling['energy_balancethermal']
    # thermal generatin from all technologies -----------------------------------------------------------
    # resistive heaters
    gen_thermal_RH = sum(
        model.genTh[p, t, s] for p in model.PDH & model.Map_nodeDH_plantDH[n]
    )

    # thermal demand of the district heating node -------------------------------------------------------
    demand_fixed = model.demandDH[n, t, s]

    # demand from thermal storage technology, TES, which includes pumping and charging etc.
    demand_storage = sum(
        model.storage_chargeTh[p, t, s] for p in model.PDH_storagecharge & model.Map_nodeDH_plantDH[n]
    )
    
    curtailmentTh = model.curtailmentTh[n, t, s]
    
    if (n,s) in KVAinfeed:
        infeedKVA = KVAinfeed[n,s]
    else:
        infeedKVA = 0
            
    return (
        sf * (gen_thermal_RH  + infeedKVA) # + infeed + lostload
        == sf * (demand_fixed + demand_storage + curtailmentTh)# +  curtailment + demand_storage
    )

def dsrth_thermal_energy_dev_tracking(model, p, t, s):
    """
    Note: dsrth_thermal_energy_dev_tracking and dsrTh_dev_week_start_zero_Constraint and dsrTh_dev_week_end_zero_Constraint are closely connected. If the timeframe (weekly) changes in one, it should change in all.
    To calculate the thermal energy deviation of the representative building connected to a district heating area from the building's thermal energy correspoding to the comfortable temperature range.
    The deviation (model.dsrTh_dev[p, t, s]) is equal to sum of the connected dsrTh plant so far in the week, i.e.,
    model.dsrTh_dev[p, t, s] is equal to model.storage_chargeTh[p, t, s] - model.genTh[p, t, s] summed over all hours starting from the beginning of the corresponding week to hour t.
    """
    sf = model.constraint_scaling['dsrth_thermal_energy_dev_tracking']
    week_of_t = model.Map_t_week[t]
    T_of_corresponding_week = model.Map_week_t[week_of_t]
    # first_hour_week =T_of_corresponding_week[0]
    # last_hour_week = T_of_corresponding_week[-1]
    # if t == first_hour_week or t == last_hour_week: # fix the deviation at the beginning and end of the week
    #     return model.dsrThDev[p, t, s] == 0
    # else:
    T_until_now = [t_ for t_ in T_of_corresponding_week if t_ <= t]
    return sf * model.dsrThDev[p, t, s] == sf * sum(
        model.storage_chargeTh[p, t_, s] - model.genTh[p, t_, s] for t_ in T_until_now
    )
    
def dsrTh_dev_limit_Constraint(model, p, t, s):
    """
    The deviation of the thermal energy of the building from the comfortable temperature range should be within the limits of the thermal energy deviation of the building.
    i.e., -5 <= model.dsrTh_dev[p, t, s] <= 5
    """
    sf = model.constraint_scaling['dsrTh_dev_limit']
    return pyo.inequality(-sf * model.dsrThDev_max[p,s], sf * model.dsrThDev[p, t, s], sf * model.dsrThDev_max[p,s]) 


def dsrTh_dev_week_start_zero_Constraint(model, p, w, s):
    """
    Note: dsrth_thermal_energy_dev_tracking and dsrTh_dev_week_start_zero_Constraint and dsrTh_dev_week_end_zero_Constraint are closely connected. If the timeframe (weekly) changes in one, it should change in all.
    Both at the end and beginning of a week, building's thermal energy deviation should be zero. This ensures that the temperature of the building is not too high or too low for a long time.
    """
    first_t_of_week = model.Map_week_t[w][0]
    return model.dsrThDev[p, first_t_of_week, s] == 0

def dsrTh_dev_week_end_zero_Constraint(model, p, w, s):
    """
    Note: dsrth_thermal_energy_dev_tracking and dsrTh_dev_week_start_zero_Constraint and dsrTh_dev_week_end_zero_Constraint are closely connected. If the timeframe (weekly) changes in one, it should change in all.
    Both at the end and beginning of a week, building's thermal energy deviation should be zero. This ensures that the temperature of the building is not too high or too low for a long time.
    """
    last_t_of_week = model.Map_week_t[w][-1]
    return model.dsrThDev[p, last_t_of_week, s] == 0

def dsrTh_dev_weekly_average_temp_Constraint(model, p, w, s):
    """
    The average temperature of the demand should remain at 22 degrees. In other words, the average thermal energy deviation of the building in a week should be zero.
    """
    return sum(model.dsrThDev[p, t, s] for t in model.Map_week_t[w]) == 0

def inflexble_demandTh_share_Constraint(model, n, t, s):
    """
    At every time step, at least ...% of the thermal energy demand of the district heating node should be inflxible. 
    In other words, sum of generationTh from all sources in the node, except for dsrTh, should be at least ...% of the demandDH.
    """
    sf = model.constraint_scaling['inflexble_demandTh_share']
    return sf * sum(
        model.genTh[p, t, s] for p in model.PDH & model.Map_nodeDH_plantDH[n] if p not in model.PDH_dsr
    ) >= sf * np.round((1 - flexible_household_heatpump_share[0]) * model.demandDH[n, t, s])
    
# thermal storage investment -----------------------------------------
def gen_energyTh_max_limit_Constraint(model, p, scen):
    sf = model.constraint_scaling['gen_energyTh_max_limit_constraint']
    if model.energyTh_max_limit[p] == float('inf') or math.isnan(model.energyTh_max_limit[p]):
        return Constraint.Skip
    else:
        return sf * model.gen_energyTh_max[p, scen] <= sf * model.energyTh_max_limit[p]
    
         
    
def genTh_max_limit_Constraint(model, p, scen):
    sf = model.constraint_scaling['genTh_max_limit_constraint']
    if model.genTh_max_limit[p] != float('inf'):
        return sf * model.genTh_max[p, scen] <= sf * model.genTh_max_limit[p]
    else:
        return Constraint.Skip       
# -------------------------------------------- EV modelling -------------------------------------------
def ev_consumption_weekly_sum_Constraint(model, w, s):
    """
    Modelling the flexible EV consumption with the representative plant CH00_EV_flex.
    The EV consumption shifting constraint ensures that 
     - the total energy consumed by flexible EVs equals the given weekly sums and 
     - in every hour the consumption is limited by the availability of the EVs.

    This constraint only covers the FLEXIBLE portion of EV charging (CH00_EV_flex).
    The inflexible portion is added directly to the energy balance as a fixed demand parameter.

    inputs:
    - EV_weekly_energy_consumption_data (flexible portion weekly target)
    - model.Map_week_t
    
    Note: When only a partial week is modeled, the weekly target is scaled proportionally
    to the fraction of hours actually being modeled. This prevents forcing full-week 
    consumption into a shorter time period.
    """
    sf = model.constraint_scaling['ev_consumption_weekly_sum']

    # Weekly target for flexible EVs from EV_weekly_energy_consumption_data
    weekly_target_energy = EV_weekly_energy_consumption_data[w,s]
    
    # Calculate the fraction of the week that is actually being modeled
    # Use Map_week_t_full to get the true number of hours in the full week (168 for a normal week)
    # and Map_week_t to get the hours actually being modeled
    hours_in_full_week = len(model.Map_week_t_full[w])  # Should be 168 for a full week
    hours_modeled_in_week = len(model.Map_week_t[w])  # Hours actually in model.T
    
    # Scale the weekly target proportionally to hours modeled
    if weekly_target_energy > 1 and hours_modeled_in_week < hours_in_full_week:
        fraction_of_week_modeled = hours_modeled_in_week / hours_in_full_week
        weekly_target_energy *= fraction_of_week_modeled

        print(f"Warning: Since {w} is not modeled entirely, the EV demand has been adjusted from {EV_weekly_energy_consumption_data[w,s]:.2f} MWh to {weekly_target_energy:.2f} MWh.")

    # total energy consumed by flexible EVs in a week
    total_energy_consumed = sum(
        model.storage_charge["CH00_EV_flex", t, s] for t in model.Map_week_t[w]
    )
    return sf * total_energy_consumed == sf * weekly_target_energy

def ev_consumption_hourly_rate_Constraint(model, t, s):
    """
    The hourly rate of flexible EV consumption (CH00_EV_flex) is limited by the charging power rate.
    input:
    - EV_charging_power_rate
    """
    sf = model.constraint_scaling['ev_consumption_hourly_rate']
    return sf * model.storage_charge["CH00_EV_flex", t, s] <= sf * EV_charging_power_rate[t,s]

# V2G
def v2g_consumption_hourly_rate_Constraint(model, p, t, s):
    """
    The hourly rate of V2G consumption is limitted by the discharging power rate of the V2G.
    """
    sf = model.constraint_scaling['v2g_consumption_hourly_rate']
    return sf * model.storage_charge[p, t, s] <= sf * model.V2G_charging_power_rate[p,t, s]
def v2g_generation_hourly_rate_Constraint(model, p, t, s):
    """
    The hourly rate of V2G generation is limitted by the charging power rate of the V2G.
    """
    sf = model.constraint_scaling['v2g_generation_hourly_rate']
    return sf * model.gen[p, t, s] <= sf * model.V2G_charging_power_rate[p,t, s]

# -------------------------------------------- heat pump modeling -------------------------------------------

def building_heat_demand_Constraint(model, t, ba, s):
    """
    Ensures that the thermal energy level (i.e. the temperature) in the building is maintained within the comfortable range.
    """
    sf = model.constraint_scaling['building_heat_demand']
    # Regular thermal storage equation for any hour that is neither the first nor the last hour
    if t != model.T.first():
        return sf * model.th_sl[t, ba, s] == sf * (model.th_sl[model.T.prev(t), ba, s] - model.BA_th_con[t, ba, s] + model.storage_charge[ba, t, s] * model.COP[t, ba, s])
    else:
        return sf * model.th_sl[t, ba, s] == 0


def building_weekly_average_Constraint(model, w, ba, s):
    """
    Ensures that the thermal energy level (i.e. the temperature) in the building throughout a week has the mean of the comfortable temperature range as average.
    """
    weekly_average_th_sl = sum(model.th_sl[t, ba, s] for t in model.T if t in model.Map_week_t[w])

    return weekly_average_th_sl == 0

def max_heating_capacity_Constraint(model, t, ba, s):
    """
    Ensures that the heating capacity of the heat pump is not exceeded.
    """
    sf = model.constraint_scaling['max_heating_capacity']
    return sf * model.storage_charge[ba, t, s] <= sf * model.BA_max_heating_capacity[ba, s]

def fuel_storage_capacity_annual_investment_limit_Constraint(model, f, s):
    """
    Ensures that the investment in investment  fuel storage is limited to the fuel storage capacity potential of CH.
    """
    sf = model.constraint_scaling['fuel_storage_capacity_annual_investment_limit']
    return sf * model.fuel_storage_capacity_annual[f, s] <= sf * model.fuel_storage_investment_annual_limit[f, s]

def resistive_heater_investment_cap_Constraint(model, s):
    """
    Limits the total investment capacity of resistive heaters across all district heating nodes.
    Sums the investment capacity across all resistive heater plants globally.
    """
    sf = model.constraint_scaling['resistive_heater_investment_cap']
    # Skip if no limit is provided
    if model.resistive_heater_cap_MW_total.value is False:
        return pyo.Constraint.Skip
    
    resistive_plants = [pdh for pdh in model.PDH_resistive if pdh in model.PDH_allinvTh]
    
    if not resistive_plants:
        return pyo.Constraint.Skip
    
    return sf * sum(model.genTh_max[pdh, s] for pdh in resistive_plants) <= sf * model.resistive_heater_cap_MW_total

def pump_less_than_gen_constraint(model, pdh, scenario):
    if model.Map_plantDH_tech[pdh] in ['PTES_large', 'TTES_medium']:
        return model.pumpTh_max[pdh, scenario] <= model.genTh_max[pdh, scenario]
    return pyo.Constraint.Skip


# ---------------------------------------------------------------------------------------------------------------
# ------------------------------------------------- fixing values ----------------------------------------------
# ---------------------------------------------------------------------------------------------------------------
# write a function that gets a model and target_variable and a subset of target_variable and a list of values for the subset and fixes the values of the target_variable to the values in the list


def fix_variable(model, target_variable, subset, values):
    for i, v in enumerate(subset):
        model.__getattribute__(target_variable)[v] = values[i]


# def fix_variables(model, target_variable, target_subset, target_values):
#     target_variable_within_target_subset = {model.variable_to_be_fixed[element]: element for element in target_subset}  # Example fixed values
#     for var in model.target_variable:
#         if var in target_variable_within_target_subset:
#             var.fix(target_variable_within_target_subset[value])


def fix_variables(target_variable, subset, target_values, *args):
    """
    Fixes the values of a "subset" of a "target_variable" that are exogenously given by values stored in "target_values".
    Inputs:
        target_variable: the variable to be fixed (e.g. model.gen_max)
        subset: the subset of target_variable (e.g., EV cars)
        target_values: the values of the target_variable (e.g., 0.11 MW)
        *args: an optional fourth input that triggers additional behavior, i.e., fixes and values for the sub_scenario mentioned
    :return: the model with fixed target_variable
    """
    if len(args) == 0:
        for element in subset:
            target_variable[element].fix(target_values[element])
    else: # sub_scenario is given
        sub_scenario = args[0]
        for element in subset:
            target_variable[element, sub_scenario].fix(target_values[element, sub_scenario])
    return target_variable


def fixing_capacities_central(model, sub_scenarios_list):
    """	
    Fixing the generation and storage capacities of plants to the values from the TYNDP dataset.
    Inputs:
        model: pyomo model
        sub_scenarios_list: list of sub_scenarios
    """
    #NOTE: check which of the following values can be replced by model.X 
    # Plant_capacity_gen
    # Plant_capacity_pmp
    # Plant_capacity_strg
    # PlantDH_capacity that can be replaced by model.PlantDH_capacity

    

        # fix generation capacity of plants from TYNDP dataset ----------
    tech_to_fix_gen_capacity = "all"
    # find target_techs that are technologies whose generation capacity is to be fixed
    # target_techs in current version. ['psp_close', 'battery', 'limited_energy', 'dam', 'lignite', 'psp_open', 'hardcoal', 'oil', 'nuclear', 'chp', 'dsr', 'gas']
    model_techs_list = [element for element in model.Tech_gen]
    target_techs = [
        element
        for element in model_techs_list
        if element
        not in [
            "pvrf",
            "windon",
            "ev_flex",
            "v2g",
            "electrolyzer",
            "resistive_heater", # district heating
            "heat_pump", # district heating
            "heat_pump_households",
            "dsrTh", # district heating
        ]
    ]

    # Ensure that the thermal storage level of buildings for the modeling of heat pumps for private households is fixed at 0 for both, the beginning and the end of the year.
    for ba in model.BA_names:
        for s in model.Scenarios:
            model.th_sl[model.T.first(), ba, s].fix(0)
            model.th_sl[model.T.last(), ba, s].fix(0)

    if tech_to_fix_gen_capacity == "all":
        for sub_scen in sub_scenarios_list:
            # fixing generation capacity of plants
            Plant_list_to_fix = [
                plant for plant in model.P if Map_plant_tech[plant] in target_techs and plant not in model.P_allinv and plant not in model.PDH_allinvTh
            ]
            # find elements that are in Plant_list_to_fix but not in keys of Plant_capacity_gen
            fix_variables(model.gen_max, Plant_list_to_fix, Plant_capacity_gen, sub_scen)

            # fixing pumping capacity of hyrdo plants (e.g., not batteries)
            Plant_list_to_fix = [
                plant for plant in model.P_hydro if Map_plant_tech[plant] != "dam" and plant not in model.P_allinv
            ]
            fix_variables(model.pmp_max, Plant_list_to_fix, Plant_capacity_pmp, sub_scen)

            # fixing pumping capacity of batteries to their generation capacity (gen_max= pmp_max)
            Plant_list_to_fix = [
                plant for plant in model.P_pumping if Map_plant_tech[plant] == "battery" and plant not in model.P_allinv
            ]
            fix_variables(model.pmp_max, Plant_list_to_fix, Plant_capacity_gen, sub_scen)

            # fixing pumping (dsr as load) capacity of dsr to their generation (dsr as generation) capacity (gen_max= pmp_max)
            Plant_list_to_fix = [plant for plant in model.P_dsr if plant not in model.P_allinv]
            fix_variables(model.pmp_max, Plant_list_to_fix, Plant_capacity_gen, sub_scen)

            # fixing energy capacity of hydro plants (e.g., not batteries)
            Plant_list_to_fix = [plant for plant in model.P_hydro if plant not in model.P_allinv]
            fix_variables(model.gen_energy_max, Plant_list_to_fix, Plant_capacity_strg, sub_scen)

            # fixing energy capacity of batteries
            Plant_list_to_fix = [
                plant for plant in model.P_pumping if Map_plant_tech[plant] == "battery" and plant not in model.P_allinv
            ]
            battery_storage_power_ratio = 4 # number of hours of storage if charging at full power

            Plant_capacity_strg_battery = {
                (plant, sub_scen): battery_storage_power_ratio * Plant_capacity_gen[plant, sub_scen]
                for plant in Plant_list_to_fix
                if plant not in model.P_allinv
            }
            fix_variables(
                model.gen_energy_max, Plant_list_to_fix, Plant_capacity_strg_battery, sub_scen
            )

            # ---- district heating plants ----------------------------------------------------------------
            # NOTE: always adjust this part, as new technologies are added

            # electric side of the system -------------------------
            # fix electric consumption capacity of resistive heating plants and heat pumps
            Plant_list_to_fix = [
                plant
                for plant in model.PDH if Map_plantDH_tech[plant] in ["resistive_heater", "heat_pump"] and plant not in model.P_allinv and plant not in model.PDH_allinvTh
            ]
            fix_variables(model.pmp_max, Plant_list_to_fix, PlantDH_capacity, sub_scen)

            # thermal side of the system -------------------------

            # The following are commented as there is currently no TES
            # fix thermal generation capacity of TES
            # Plant_list_to_fix = [
            #     plant for plant in model.PDH if Map_plantDH_tech[plant] == "TES" and plant not in model.PDH_allinvTh
            # ]
            # fix_variables(model.genTh_max, Plant_list_to_fix, PlantDH_capacity, sub_scen) 

            # # fix thermal consumption capacity TES
            # Plant_list_to_fix = [
            #     plant for plant in model.PDH if Map_plantDH_tech[plant] == "TES" and plant not in model.PDH_allinvTh
            # ]
            # fix_variables(model.pumpTh_max, Plant_list_to_fix, PlantDH_capacity, sub_scen)

            # # fix energy capacity of TES
            # Plant_list_to_fix = [
            #     plant for plant in model.PDH if Map_plantDH_tech[plant] == "TES" and plant not in model.PDH_allinvTh
            # ]

            # Plant_capacity_strg_TES = { #applies to pre existing STES
            #     (plant, sub_scen): 10 * PlantDH_capacity[plant, sub_scen]
            #     for plant in Plant_list_to_fix
            # }
            # fix_variables(model.gen_energyTh_max, Plant_list_to_fix, Plant_capacity_strg_TES, sub_scen) 

            Plant_list_to_fix = [
                plant for plant in model.PDH if Map_plantDH_tech[plant] == "dsrTh" and plant not in model.PDH_allinvTh
            ]
            fix_variables(model.genTh_max, Plant_list_to_fix, PlantDH_capacity, sub_scen)
