"""
Reads the aggregated data from the aggregated folder targte_aggregate_dir and exports the data to the edge format, as:
         excel file in targte_edge_dir/MIP_reporting_FEM_{timestamp}.xlsx
"""

import pandas as pd
import numpy as np
import os
import datetime
import export_edge_parameters as params

targte_aggregate_dir = r"output\aggregated\aggregation_edge_3"
targte_edge_dir = r"output\aggregated\edge"

scenario_list = [
    "GA_CY95_RNT_N100_WNC" ,
    "GA_CY95_RNT_N100_W05" ,
    "GA_CY95_RNT_N030_WNC" ,
    "GA_CY95_RNT_N030_W05" ,
    "GA_CY95_R45_N100_WNC" ,
    "GA_CY95_R45_N100_W05" ,
    "GA_CY95_R45_N030_WNC" ,
    "GA_CY95_R45_N030_W05" ,
    "DE_CY95_RNT_N100_WNC" ,
    "DE_CY95_RNT_N100_W05" ,
    "DE_CY95_RNT_N030_WNC" ,
    "DE_CY95_RNT_N030_W05" ,
    "DE_CY95_R45_N100_WNC" ,
    "DE_CY95_R45_N100_W05" ,
    "DE_CY95_R45_N030_WNC" ,
    "DE_CY95_R45_N030_W05" ,
]
# scenario_renames_dict is a dictionary with the key being the name of the scenario as in scenario_list and the values being the new names of the scenarios
# new names for a scenario of A_B_C_D are D_CY95_A_B_C
# Assuming scenario_list is your list of scenarios
# scenario_renames_dict = {scenario: '_'.join([scenario.split('_')[-1], 'CY95'] + scenario.split('_')[:-1]) for scenario in scenario_list}    
    
winter_defintion = [f"t_{i}" for i in range(6553, 8760+1)] + [f"t_{i}" for i in range(1, 2184+1)]
export_time_steps = [f"t_{i}" for i in range(1, 8760+1)]

investment_cost_preexisting = 2672 # in Mio EUR
# def export_edge(targte_aggregate_dir, targte_edge_dir):
# create target_edge_dir
if not os.path.exists(targte_edge_dir):
    os.makedirs(targte_edge_dir)



#------------------------------------------------------------------------------------------------
# create sheets ---------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------
# create "Output_Sys" sheet
multi_index = pd.MultiIndex.from_product([["FEM"], scenario_list, params.Output_Sys_parameter_list], names=["Model", "Scenario", "Output-Parameter"])
output_sys = pd.DataFrame(index=multi_index, columns=params.Output_Sys_columns_names)

# create "Output_Temp" sheet ---------------------------------------------------------------------
multi_index = pd.MultiIndex.from_product([["FEM"], scenario_list, params.Output_Temp_parameter_list], names=["Model", "Scenario", "Output-Parameter"])
output_temp = pd.DataFrame(index=multi_index, columns=params.Output_Temp_columns_names)


# read import, export, export_net data (all time steps and scnearios in one file) ----------------
# 
import_df = pd.read_csv(f"{targte_aggregate_dir}\\Import_CH.csv")
export_df = pd.read_csv(f"{targte_aggregate_dir}\\Export_CH.csv")
export_net_df = pd.read_csv(f"{targte_aggregate_dir}\\Export_net_CH.csv")
lostload_df = pd.read_csv(f"{targte_aggregate_dir}\\lostload_hour_sum_temporal.csv")
curtailment_df = pd.read_csv(f"{targte_aggregate_dir}\\curtailment_hour_sum_temporal.csv", index_col=[0,1])
price_weighted_avg = pd.read_csv(f"{targte_aggregate_dir}\\price_weighted_avg.csv", index_col=[0,1])


# 
infeed = pd.read_csv(f"{targte_aggregate_dir}\\infeed_hour_sum_temporal.csv", index_col=[0,1,2])
gen  = pd.read_csv(f"{targte_aggregate_dir}\\gen_hour_sum_temporal.csv", index_col=[0,1]) # time series of generation, and infeed from invested RES
storage_charge = pd.read_csv(f"{targte_aggregate_dir}\\storage_charge_hour_sum_temporal.csv", index_col=[0,1])
lostload = pd.read_csv(f"{targte_aggregate_dir}\\lostload_hour_sum_temporal.csv", index_col=[0,1,2])
import_ts_df = pd.read_csv(f"{targte_aggregate_dir}\\Import_CH_per_line.csv", index_col=[0,1])
export_ts_df = pd.read_csv(f"{targte_aggregate_dir}\\Export_CH_per_line.csv", index_col=[0,1])
gen_max = pd.read_csv(f"{targte_aggregate_dir}\\gen_max.csv", index_col=[0])
# pmp_max = pd.read_csv(f"{targte_aggregate_dir}\\pmp_max.csv", index_col=[0])

# 
price_hourly = pd.read_csv(f"{targte_aggregate_dir}\\energy_balance_dual_hour_mean_temporal.csv", index_col=[0,1])

# costs and gains
op_inv_exp_imp_cost = pd.read_csv(f"{targte_aggregate_dir}\\op_inv_exp_imp_cost.csv", index_col=[0])

#infeed/res capacities
gen_max_infeedp = pd.read_csv(f"{targte_aggregate_dir}\\gen_max_infeedp.csv", index_col=[0])

# temporal data
gen_dem_timeseries = pd.read_csv(f"{targte_aggregate_dir}\\Annual_balance_ch_hourly.csv", index_col=[0,1,2])

# costs for consumers
sum_cost_for_consumers_hourly = pd.read_csv(f"{targte_aggregate_dir}\\sum_cost_for_consumers_hourly.csv", index_col=[0,1]).loc["CH00"]
sum_cost_for_consumers = pd.read_csv(f"{targte_aggregate_dir}\\sum_cost_for_consumers.csv", index_col=[0,1]).loc["CH00"]

# dict for curtailment timeseries
curtailment_timeseries_ch ={}
curtailment_timeseries_ch_neighbours = {}
#------------------------------------------------------------------------------------------------
# Fill in dataframes ----------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------
# print(f"Filling in dataframes.{20*'-'}")	
print("Output_Sys")
# Output_Sys 
for scenario in scenario_list:
    # "Import to CH Annual" -------------------------------------------------------------------------
    target_range = import_df.loc[:,scenario]/(1* 1000 * 1000)
    output_sys.loc[("FEM", scenario, "Import to CH Annual"), :] = ["TWh/yr", target_range.sum(), target_range.mean(), target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Export from CH Annual" -------------------------------------------------------------------------
    target_range = - export_df.loc[:,scenario]/(1* 1000 * 1000)
    output_sys.loc[("FEM", scenario, "Export from CH Annual"), :] = ["TWh/yr", target_range.sum(), target_range.mean(), target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Net import CH Annual (Import-Export)" -------------------------------------------------------------------------
    target_range = - export_net_df.loc[:,scenario]/(1* 1000 * 1000)
    output_sys.loc[("FEM", scenario, "Net import CH Annual (Import-Export)"), :] = ["TWh/yr", target_range.sum(), target_range.mean(), target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Import WINTER" -------------------------------------------------------------------------
    # target_range is values in import_df for which the column T has any of the values in winter_defintion
    target_range = import_df.loc[import_df.loc[:,"T"].isin(winter_defintion), scenario]/(1* 1000 * 1000)
    output_sys.loc[("FEM", scenario, "Import WINTER"), :] = ["TWh", target_range.sum(), target_range.mean(), target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Export WINTER" -------------------------------------------------------------------------
    target_range = - export_df.loc[export_df.loc[:,"T"].isin(winter_defintion), scenario]/(1* 1000 * 1000)
    output_sys.loc[("FEM", scenario, "Export WINTER"), :] = ["TWh", target_range.sum(), target_range.mean(), target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Net import WINTER (Import-Export)" -------------------------------------------------------------------------
    target_range = - export_net_df.loc[export_net_df.loc[:,"T"].isin(winter_defintion), scenario]/(1* 1000 * 1000)
    output_sys.loc[("FEM", scenario, "Net import WINTER (Import-Export)"), :] = ["TWh", target_range.sum(), target_range.mean(), target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Import SUMMER" -------------------------------------------------------------------------
    # target_range is values in import_df for which the column T that does not have any of the values in winter_defintion
    target_range = import_df.loc[~import_df.loc[:,"T"].isin(winter_defintion), scenario]/(1* 1000 * 1000)
    output_sys.loc[("FEM", scenario, "Import SUMMER"), :] = ["TWh", target_range.sum(), target_range.mean(), target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Export SUMMER" -------------------------------------------------------------------------
    target_range = - export_df.loc[~export_df.loc[:,"T"].isin(winter_defintion), scenario]/(1* 1000 * 1000)
    output_sys.loc[("FEM", scenario, "Export SUMMER"), :] = ["TWh", target_range.sum(), target_range.mean(), target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Net import SUMMER (Import-Export)" -------------------------------------------------------------------------
    target_range = - export_net_df.loc[~export_net_df.loc[:,"T"].isin(winter_defintion), scenario]/(1* 1000 * 1000)
    output_sys.loc[("FEM", scenario, "Net import SUMMER (Import-Export)"), :] = ["TWh", target_range.sum(), target_range.mean(), target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Load shedding WINTER" -------------------------------------------------------------------------
    target_range = lostload_df.loc[(lostload_df.loc[:,"hour"].isin(winter_defintion)) & (lostload_df.loc[:,"Consumer"] == "CH00_fixedconsumer"), scenario]/(1* 1000 * 1000)
    output_sys.loc[("FEM", scenario, "Load shedding WINTER"), :] = ["TWh", target_range.sum(), target_range.mean(), target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Load shedding SUMMER" -------------------------------------------------------------------------
    target_range = lostload_df.loc[(~lostload_df.loc[:,"hour"].isin(winter_defintion)) & (lostload_df.loc[:,"Consumer"] == "CH00_fixedconsumer"), scenario]/(1* 1000 * 1000)
    output_sys.loc[("FEM", scenario, "Load shedding SUMMER"), :] = ["TWh", target_range.sum(), target_range.mean(), target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Load shedding Annual (Winter+Summer)" -------------------------------------------------------------------------
    target_range = lostload_df.loc[(lostload_df.loc[:,"Consumer"] == "CH00_fixedconsumer"), scenario]/(1* 1000 * 1000)
    output_sys.loc[("FEM", scenario, "Load shedding Annual (Winter+Summer)"), :] = ["TWh/yr", target_range.sum(), target_range.mean(), target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Generation curtailment Annual - CH" -------------------------------------------------------------------------
    curtailment_timeseries_ch[scenario] = curtailment_df.loc["CH00_fixedconsumer", scenario]

    curtailment_timeseries_ch_neighbours[scenario] = curtailment_df.loc["DE00_fixedconsumer", scenario] + \
                                                     curtailment_df.loc["IT00_fixedconsumer", scenario] + \
                                                     curtailment_df.loc["FR00_fixedconsumer", scenario] + \
                                                     curtailment_df.loc["AT00_fixedconsumer", scenario] #type: ignore

    target_range = curtailment_timeseries_ch[scenario]/(1* 1000 * 1000)
    output_sys.loc[("FEM", scenario, "Generation curtailment Annual - CH"), :] = ["TWh/yr", target_range.sum(), target_range.mean(), target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Generation curtailment Annual - Abroad" -------------------------------------------------------------------------
    target_range = curtailment_timeseries_ch_neighbours[scenario]/(1* 1000 * 1000)
    output_sys.loc[("FEM", scenario, "Generation curtailment Annual - Abroad"), :] = ["TWh/yr", target_range.sum(), target_range.mean(), target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # NOTE: items to do, after definitions cleared up:  "Import Cost Annual" , "Export Revenue Annual", "Trading Costs Annual (Cost - Revenue)"-------------------------------------------------------------------------
    output_sys.loc[("FEM", scenario, "Import Cost Annual"), :] = ["Mio EUR", -op_inv_exp_imp_cost.loc["payment during import" , scenario]/1000/1000, np.nan, np.nan, np.nan, np.nan, np.nan]

    output_sys.loc[("FEM", scenario, "Export Revenue Annual"), :] =  ["Mio EUR", -(op_inv_exp_imp_cost.loc["gain during export" , scenario]\
                                                                                 + op_inv_exp_imp_cost.loc["payment during export" , scenario])/1000/1000, \
                                                                      np.nan, np.nan, np.nan, np.nan, np.nan]

    output_sys.loc[("FEM", scenario, "Trading Costs Annual (Cost - Revenue)"), :] = ["Mio EUR", -(op_inv_exp_imp_cost.loc["payment during import" , scenario]\
                                                                                                + op_inv_exp_imp_cost.loc["gain during export" , scenario] \
                                                                                                + op_inv_exp_imp_cost.loc["payment during export" , scenario])/1000/1000, \
                                                                                     np.nan, np.nan, np.nan, np.nan, np.nan] #type: ignore

    output_sys.loc[("FEM", scenario, "Import Cost WINTER"), :] = ["Mio EUR", -op_inv_exp_imp_cost.loc["payment during import - winter" , scenario]/1000/1000, np.nan, np.nan, np.nan, np.nan, np.nan]

    output_sys.loc[("FEM", scenario, "Export Revenue WINTER"), :] = ["Mio EUR", - (op_inv_exp_imp_cost.loc["gain during export - winter" , scenario]
                                                                                 + op_inv_exp_imp_cost.loc["payment during export - winter" , scenario])/1000/1000, \
                                                                     np.nan, np.nan, np.nan, np.nan, np.nan]

    output_sys.loc[("FEM", scenario, "Import cost SUMMER"), :] = ["Mio EUR", -op_inv_exp_imp_cost.loc["payment during import - summer" , scenario]/1000/1000, np.nan, np.nan, np.nan, np.nan, np.nan]

    output_sys.loc[("FEM", scenario, "Export Revenue SUMMER"), :] = ["Mio EUR", op_inv_exp_imp_cost.loc["gain during export - summer" , scenario]/1000/1000, np.nan, np.nan, np.nan, np.nan, np.nan]

    # Congestion rent -------------------------------------------------------------------------------------
    congestion_rent = - (op_inv_exp_imp_cost.loc["payment during import" , scenario] \
                        + op_inv_exp_imp_cost.loc["gain during export" , scenario] \
                        + op_inv_exp_imp_cost.loc["payment during export", scenario]
                        )               

    output_sys.loc[("FEM", scenario, "Congestion rent"), :] = ["Mio EUR", congestion_rent/1000/1000, np.nan, np.nan, np.nan, np.nan, np.nan]
  
    # "Electricity price in CH" -------------------------------------------------------------------------------------
    target_range = price_hourly.loc[(price_hourly.index.get_level_values("Node") == "CH00"), scenario]
    output_sys.loc[("FEM", scenario, "Electricity price in CH"), :] = ["EUR/MWh", np.nan, price_weighted_avg.loc[("CH00", scenario), "price_weighted_avg"], target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Price for electricity import from AT"-------------------------------------------------------------------------
    # target_range is the values in price_hourly for which the index column Node has the value "AT00"
    target_range = price_hourly.loc[(price_hourly.index.get_level_values("Node") == "AT00"), scenario]
    output_sys.loc[("FEM", scenario, "Price for electricity import from AT"), :] = ["EUR/MWh", np.nan,  price_weighted_avg.loc[("AT00", scenario), "price_weighted_avg"], target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]
    output_sys.loc[("FEM", scenario, "Price for electricity export to AT"), :] =   ["EUR/MWh", np.nan,  price_weighted_avg.loc[("AT00", scenario), "price_weighted_avg"], target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Price for electricity import from DE" ------------------------------------------------------------------------
    # target_range is the values in price_hourly for which the index column Node has the value "DE00"
    target_range = price_hourly.loc[(price_hourly.index.get_level_values("Node") == "DE00"), scenario]
    output_sys.loc[("FEM", scenario, "Price for electricity import from DE"), :] = ["EUR/MWh", np.nan,  price_weighted_avg.loc[("DE00", scenario), "price_weighted_avg"], target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]
    output_sys.loc[("FEM", scenario, "Price for electricity export to DE"), :] = ["EUR/MWh", np.nan,  price_weighted_avg.loc[("DE00", scenario), "price_weighted_avg"], target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Price for electricity import from FR" ------------------------------------------------------------------------
    # target_range is the values in price_hourly for which the index column Node has the value "FR00"
    target_range = price_hourly.loc[(price_hourly.index.get_level_values("Node") == "FR00"), scenario]
    output_sys.loc[("FEM", scenario, "Price for electricity import from FR"), :] = ["EUR/MWh", np.nan,  price_weighted_avg.loc[("FR00", scenario), "price_weighted_avg"], target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]
    output_sys.loc[("FEM", scenario, "Price for electricity export to FR"), :] =   ["EUR/MWh", np.nan,  price_weighted_avg.loc[("FR00", scenario), "price_weighted_avg"], target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Price for electricity import from IT" ------------------------------------------------------------------------
    # target_range is the values in price_hourly for which the index column Node has the value "FR00"
    target_range = price_hourly.loc[(price_hourly.index.get_level_values("Node") == "IT00"), scenario]
    output_sys.loc[("FEM", scenario, "Price for electricity import from IT"), :] = ["EUR/MWh", np.nan,  price_weighted_avg.loc[("IT00", scenario), "price_weighted_avg"], target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]
    output_sys.loc[("FEM", scenario, "Price for electricity export to IT"), :] =   ["EUR/MWh", np.nan,  price_weighted_avg.loc[("IT00", scenario), "price_weighted_avg"], target_range.quantile(0.05), target_range.quantile(0.95), target_range.min(), target_range.max()]

    # "Capacity PV + Wind" ------------------------------------------------------------------------
    # create a dataframe storing the capacity of all plants in CH of the type pv and windonin
    #NOTE
    # pv_gen_ch_scen is the values in gen_max at column scen and the index has have "pv" and "CH" in their name #NOTE not robust definitions
    pv_gen_ch_scen = gen_max.loc[gen_max.index.str.contains("pv") & gen_max.index.str.contains("CH"), scenario]/1000
    pv_infeed_ch_scen = gen_max_infeedp.loc[gen_max_infeedp.index.str.contains("pv") & gen_max_infeedp.index.str.contains("CH"), scenario]/1000

    # wind_gen_ch_scen is the values in gen_max at column scen and the index has have "windon" and "CH" in their name #NOTE not robust definitions
    wind_gen_ch_scen = gen_max.loc[gen_max.index.str.contains("windon") & gen_max.index.str.contains("CH"), scenario]/1000
    wind_infeed_ch_scen = gen_max_infeedp.loc[gen_max_infeedp.index.str.contains("windon") & gen_max_infeedp.index.str.contains("CH"), scenario]/1000
    # sum all values in the dataframes,
    output_sys.loc[("FEM", scenario, "Capacity PV + Wind"), :] = ["GW", (pv_gen_ch_scen.sum()+pv_infeed_ch_scen.sum()+wind_gen_ch_scen.sum()+wind_infeed_ch_scen.sum()), np.nan, np.nan, np.nan, np.nan, np.nan]

    # Investment costs annualised All
    output_sys.loc[("FEM", scenario, "Investment costs annualised All"), :] = ["Mio EUR", investment_cost_preexisting + op_inv_exp_imp_cost.loc["investment costs" , scenario]/1000/1000, np.nan, np.nan, np.nan, np.nan, np.nan]

    # Operation costs anualised All
    output_sys.loc[("FEM", scenario, "Operation costs anualised All"), :] = ["Mio EUR", op_inv_exp_imp_cost.loc["operational costs" , scenario]/1000/1000, np.nan, np.nan, np.nan, np.nan, np.nan]

    # Total annualised costs All (with trading costs)
    output_sys.loc[("FEM", scenario, "Total annualised costs All (with trading costs)"), :] = ["Mio EUR", op_inv_exp_imp_cost.loc["total" , scenario]/1000/1000, np.nan, np.nan, np.nan, np.nan, np.nan]

    # Operational costs per unit of generated energy
    output_sys.loc[("FEM", scenario, "Operational costs per unit of generated energy"), :] = ["EUR/MWh", np.nan, np.nan, np.nan, np.nan, np.nan, np.nan]

    # Total costs for consumers -------------------------------------------------------------------------------------
    # currently defined as nodal price * demand (of all flexible and inflxeible consumers)
    output_sys.loc[("FEM", scenario, "Total costs for consumers"), :] = ["EUR/yr", sum_cost_for_consumers.loc[scenario].values[0], np.nan, np.nan, np.nan, np.nan, np.nan]

    # Total revenues for generators -------------------------------------------------------------------------------------
    #NOTE: code duplicated below
    target_range_gen = gen_dem_timeseries.loc[(scenario, "gen", "pv_all"), :]+ \
                        gen_dem_timeseries.loc[(scenario, "gen", "wind_all"), :] + \
                        gen_dem_timeseries.loc[(scenario, "gen", "ror"), :] + \
                        gen_dem_timeseries.loc[(scenario, "gen", "psp_open"), :] + \
                        gen_dem_timeseries.loc[(scenario, "gen", "psp_close"), :] + \
                        gen_dem_timeseries.loc[(scenario, "gen", "battery"), :] + \
                        gen_dem_timeseries.loc[(scenario, "gen", "gas"), :] + \
                        gen_dem_timeseries.loc[(scenario, "gen", "biomass"), :] + \
                        gen_dem_timeseries.loc[(scenario, "gen", "other"), :]
                        
    target_range_gen = target_range_gen.reindex(export_time_steps, level='hour')

    target_range_price = price_hourly.loc[(price_hourly.index.get_level_values("Node") == "CH00"), scenario]
    # remove the index column named Node
    target_range_price.index = target_range_price.index.droplevel("Node") 
    target_range_price = target_range_price.reindex(export_time_steps)

    output_sys.loc[("FEM", scenario, "Total revenues for generators"), :] = ["EUR/yr", target_range_price.dot(target_range_gen).sum(), np.nan, np.nan, np.nan, np.nan, np.nan]
    
    # Transmission grid expansion investment costs -------------------------------------------------------------------------------------
    output_sys.loc[("FEM", scenario, "Transmission grid expansion investment costs"), :] = ["Mio EUR", np.nan, np.nan, np.nan, np.nan, np.nan, np.nan]

    # Grid Expansion within CH -------------------------------------------------------------------------------------
    output_sys.loc[("FEM", scenario, "Grid Expansion within CH"), :] = ["Mio EUR", np.nan, np.nan, np.nan, np.nan, np.nan, np.nan]


    # Grid Expansion within CH -------------------------------------------------------------------------------------
    output_sys.loc[("FEM", scenario, "Grid Expansion within CH"), :] = ["GW", np.nan, np.nan, np.nan, np.nan, np.nan, np.nan]

    # Grid Expansion to neighbours -------------------------------------------------------------------------------------
    output_sys.loc[("FEM", scenario, "Grid Expansion to neighbours"), :] = ["GW", np.nan, np.nan, np.nan, np.nan, np.nan, np.nan]

    # Total emissions -------------------------------------------------------------------------------------
    output_sys.loc[("FEM", scenario, "Total emissions"), :] = ["tCO2/yr", np.nan, np.nan, np.nan, np.nan, np.nan, np.nan]

    # Time to solve model -------------------------------------------------------------------------------------
    output_sys.loc[("FEM", scenario, "Time to solve model"), :] = ["min", np.nan, np.nan, np.nan, np.nan, np.nan, np.nan]

    # Memory requirements -------------------------------------------------------------------------------------
    output_sys.loc[("FEM", scenario, "Memory requirements"), :] = ["GB", np.nan, np.nan, np.nan, np.nan, np.nan, np.nan]


print("Output_Temp")
# Output_Temp

for scenario in scenario_list:
    # "Hourly generation solar PV - Rooftop" -------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "gen", "pv_all"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly generation solar PV - Rooftop"), :] = ["GWh"] + target_range.values.tolist()

    # "Hourly generation solar PV - Alpine" -------------------------------------------------------------------------
    output_temp.loc[("FEM", scenario, "Hourly generation solar PV - Alpine"), :] = ["GWh"] + np.full(8760,np.nan).tolist()

    # "Hourly generation wind power" -------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "gen", "wind_all"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly generation wind power"), :] = ["GWh"] + target_range.values.tolist()

    # "Hourly generation biomass/waste" -------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "gen", "biomass"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly generation biomass/waste"), :] = ["GWh"] + target_range.values.tolist()

    # "Hourly generation Gas CC" -------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "gen", "gas"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly generation Gas CC"), :] = ["GWh"] + target_range.values.tolist()

    # Hourly generation Gas CC-CCS" -------------------------------------------------------------------------
    output_temp.loc[("FEM", scenario, "Hourly generation Gas CC-CCS"), :] = ["GWh"] + np.full(8760,np.nan).tolist()

    # Hourly generation Gas CC-Syn" -------------------------------------------------------------------------
    output_temp.loc[("FEM", scenario, "Hourly generation Gas CC-Syn"), :] = ["GWh"] + np.full(8760,np.nan).tolist()
    
    # "Hourly generation Gas other" -------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "gen", "other"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly generation Gas other"), :] = ["GWh"] + target_range.values.tolist()

    # "Hourly generation nuclear" -------------------------------------------------------------------------
    try: 
        target_range = gen_dem_timeseries.loc[(scenario, "gen", "nuclear"), :]/1000
    except KeyError:
        print(f"Scenario {scenario} does not have nuclear generation")
        target_range = pd.Series(np.zeros(8760), index=export_time_steps)
    
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly generation nuclear"), :] = ["GWh"] + target_range.values.tolist()

    # "Hourly generation hydro dam" -------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "gen", "psp_open"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly generation hydro dam"), :] = ["GWh"] + target_range.values.tolist()
    
    # "Hourly generation hydro run of river" -------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "gen", "ror"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly generation hydro run of river"), :] = ["GWh"] + target_range.values.tolist()


    # Hourly generation hydro pumped storage -------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "gen", "psp_close"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly generation hydro pumped storage"), :] = ["GWh"] + target_range.values.tolist()

    # Hourly demand hydro pumped storage -------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "demand", "flex psp_open"), :]/1000 + gen_dem_timeseries.loc[(scenario, "demand", "flex psp_close"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly demand hydro pumped storage"), :] = ["GWh"] + target_range.values.tolist()

    # Hourly generation battery -------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "gen", "battery"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly generation battery"), :] = ["GWh"] + target_range.values.tolist()

    # Hourly charge battery -------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "demand", "flex battery"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly charge battery"), :] = ["GWh"] + target_range.values.tolist()

    # Hourly DSM up -------------------------------------------------------------------------
    #NOTE: no ch dsr in current data set, test later
    #NOTE: for now, report flex electrolyzer as DSM up
    target_range = gen_dem_timeseries.loc[(scenario, "demand", "flex electrolyzer"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly DSM up"), :] = ["GWh"] + target_range.values.tolist()

    # Hourly DSM down -------------------------------------------------------------------------
    #NOTE: no ch dsr in current data set, test later
    output_temp.loc[("FEM", scenario, "Hourly DSM down"), :] = ["GWh"] + np.full(8760,np.nan).tolist()


    # Hourly generation curtailment - CH ------------------------------------------------------------ #NOTE 
    target_range = gen_dem_timeseries.loc[(scenario, "demand", "curtailment"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly generation curtailment - CH"), :] = ["GWh"] + target_range.values.tolist()

    # Hourly generation curtailment - Abroad -------------------------------------------------------------------------
    #NOTE: no Hourly generation curtailment - Abroad in current data set, test later
    target_range = curtailment_timeseries_ch_neighbours[scenario]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')
    output_temp.loc[("FEM", scenario, "Hourly generation curtailment - Abroad"), :] = ["GWh"] + target_range.values.tolist()

    # Hourly load shedded -------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "gen", "lostload"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly load shedded"), :] = ["GWh"] + target_range.values.tolist()

    # Hourly exchange CH-DE and Hourly exchange DE-CH -------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "gen", "import_DE"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    target_range_negative_only = target_range.clip(upper=0)
    output_temp.loc[("FEM", scenario, "Hourly exchange CH-DE"), :] = ["GWh"] + target_range_negative_only.values.tolist()
    target_range_positive_only = target_range.clip(lower=0)
    output_temp.loc[("FEM", scenario, "Hourly exchange DE-CH"), :] = ["GWh"] + target_range_positive_only.values.tolist()

    # Hourly exchange CH-FR and Hourly exchange FR-CH  -------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "gen", "import_FR"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    target_range_negative_only = target_range.clip(upper=0)
    output_temp.loc[("FEM", scenario, "Hourly exchange CH-FR"), :] = ["GWh"] + target_range_negative_only.values.tolist()
    target_range_positive_only = target_range.clip(lower=0)
    output_temp.loc[("FEM", scenario, "Hourly exchange FR-CH"), :] = ["GWh"] + target_range_positive_only.values.tolist()

    # Hourly exchange CH-IT and Hourly exchange IT-CH-------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "gen", "import_IT"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    target_range_negative_only = target_range.clip(upper=0)
    output_temp.loc[("FEM", scenario, "Hourly exchange CH-IT"), :] = ["GWh"] + target_range_negative_only.values.tolist()
    target_range_positive_only = target_range.clip(lower=0)
    output_temp.loc[("FEM", scenario, "Hourly exchange IT-CH"), :] = ["GWh"] + target_range_positive_only.values.tolist()


    # Hourly exchange CH-AT and Hourly exchange AT-CH-------------------------------------------------------------------------
    target_range = gen_dem_timeseries.loc[(scenario, "gen", "import_AT"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    target_range_negative_only = target_range.clip(upper=0)
    output_temp.loc[("FEM", scenario, "Hourly exchange CH-AT"), :] = ["GWh"] + target_range_negative_only.values.tolist()
    target_range_positive_only = target_range.clip(lower=0)
    output_temp.loc[("FEM", scenario, "Hourly exchange AT-CH"), :] = ["GWh"] + target_range_positive_only.values.tolist()

    # Hourly import to CH (total)  -------------------------------------------------------------------------
    # target_range has index as in column T of import_df and values are in column scenario
    target_range = import_df.set_index('T')[scenario]/(1* 1000)
    target_range.index.name = None
    target_range = target_range.reindex(export_time_steps)

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly import to CH (total)"), :] = ["GWh"] + target_range.values.tolist()

    # Hourly export to CH (total)  -------------------------------------------------------------------------
    # target_range has index as in column T of export_df and values are in column scenario
    target_range = export_df.set_index('T')[scenario]/(1* 1000)
    target_range.index.name = None
    target_range = target_range.reindex(export_time_steps)

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly export to CH (total)"), :] = ["GWh"] + target_range.values.tolist()

    # Hourly net import (import-export)  -------------------------------------------------------------------------
    # target_range has index as in column T of export_net_df and values are in column scenario
    target_range = - export_net_df.set_index('T')[scenario]/(1* 1000)
    target_range.index.name = None
    target_range = target_range.reindex(export_time_steps)

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly net import (import-export)"), :] = ["GWh"] + target_range.values.tolist()

    # Hourly net load --------------------------------------------------------------------------------------------- #NOTE may need to add electrolyzer demand
    target_range = gen_dem_timeseries.loc[(scenario, "demand", "fixed modelled household"), :]/1000 + \
                   gen_dem_timeseries.loc[(scenario, "demand", "fixed modelled commercial"), :]/1000 - \
                   gen_dem_timeseries.loc[(scenario, "gen", "pv_all"), :]/1000 - \
                   gen_dem_timeseries.loc[(scenario, "gen", "wind_all"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly net load"), :] = ["GWh"] + target_range.values.tolist()

    # Hourly electricity price CH ---------------------------------------------------------------------------------
    for country in ["CH00", "DE00", "FR00", "IT00", "AT00"]:
        target_range = price_hourly.loc[(price_hourly.index.get_level_values("Node") == country), scenario]
        # remove the index column named Node
        target_range.index = target_range.index.droplevel("Node") 
        target_range = target_range.reindex(export_time_steps)

        # assign values of target_range to output_temp
        output_temp.loc[("FEM", scenario, f"Hourly electricity price {country[0:2]}"), :] = ["EUR/MWh"] + target_range.values.tolist()

    # Hourly costs for consumers ---------------------------------------------------------------------------------
    target_range = sum_cost_for_consumers_hourly.loc[scenario]
    target_range = target_range.reindex(export_time_steps)

    # assign values of target_range to output_temp
    output_temp.loc[("FEM", scenario, "Hourly costs for consumers"), :] = ["EUR"] + target_range.values.tolist()
    
    # Hourly revenues for generators ---------------------------------------------------------------------------------
    target_range_gen = gen_dem_timeseries.loc[(scenario, "gen", "pv_all"), :]+ \
                        gen_dem_timeseries.loc[(scenario, "gen", "wind_all"), :] + \
                        gen_dem_timeseries.loc[(scenario, "gen", "ror"), :] + \
                        gen_dem_timeseries.loc[(scenario, "gen", "psp_open"), :] + \
                        gen_dem_timeseries.loc[(scenario, "gen", "psp_close"), :] + \
                        gen_dem_timeseries.loc[(scenario, "gen", "battery"), :] + \
                        gen_dem_timeseries.loc[(scenario, "gen", "gas"), :] + \
                        gen_dem_timeseries.loc[(scenario, "gen", "biomass"), :] + \
                        gen_dem_timeseries.loc[(scenario, "gen", "other"), :]
                        
    target_range_gen = target_range_gen.reindex(export_time_steps, level='hour')

    target_range_price = price_hourly.loc[(price_hourly.index.get_level_values("Node") == "CH00"), scenario]
    # remove the index column named Node
    target_range_price.index = target_range_price.index.droplevel("Node") 
    target_range_price = target_range_price.reindex(export_time_steps)

    output_temp.loc[("FEM", scenario, "Hourly revenues for generators"), :] = ["EUR"] + (target_range_gen * target_range_price).values.tolist()
    # Average line loading - all lines ---------------------------------------------------------------------------
    output_temp.loc[("FEM", scenario, "Average line loading - all lines"), :] = ["%"] + np.full(8760,np.nan).tolist()
    # Average line loading - internal lines ----------------------------------------------------------------------
    output_temp.loc[("FEM", scenario, "Average line loading - internal lines"), :] = ["%"] + np.full(8760,np.nan).tolist()
    # Average line loading - interconnectors ---------------------------------------------------------------------
    output_temp.loc[("FEM", scenario, "Average line loading - interconnectors"), :] = ["%"] + np.full(8760,np.nan).tolist()


print("output_spatial")


# ---------------------------------------------------------------------------------------------------
# --------------------------------------- output_spatial --------------------------------------------
# ---------------------------------------------------------------------------------------------------
# create "output_spatial" sheet ---------------------------------------------------------------------
multi_index = pd.MultiIndex.from_product([["FEM"], scenario_list, params.Output_Spatial_parameter_list], names=["Model", "Scenario", "Output-Parameter"])
output_spatial = pd.DataFrame(index=multi_index, columns=params.Output_Spatial_columns_names)

# Total capacities -------------------------------------------------------------------------------------
capacity_pv_tot = pd.DataFrame(index=scenario_list, columns=[f"CH0{i}" for i in range(1,7+1)])
capacity_wind_tot = pd.DataFrame(index=scenario_list, columns=[f"CH0{i}" for i in range(1,7+1)])
capacity_biomass_tot = pd.DataFrame(index=scenario_list, columns=[f"CH0{i}" for i in range(1,7+1)])
capacity_gas_tot = pd.DataFrame(index=scenario_list, columns=[f"CH0{i}" for i in range(1,7+1)])
capacity_other_tot = pd.DataFrame(index=scenario_list, columns=[f"CH0{i}" for i in range(1,7+1)])
capacity_nuclear_tot = pd.DataFrame(index=scenario_list, columns=[f"CH0{i}" for i in range(1,7+1)])
capacity_dams_tot = pd.DataFrame(index=scenario_list, columns=[f"CH0{i}" for i in range(1,7+1)])
capacity_ror_tot = pd.DataFrame(index=scenario_list, columns=[f"CH0{i}" for i in range(1,7+1)])
capacity_pump_tot = pd.DataFrame(index=scenario_list, columns=[f"CH0{i}" for i in range(1,7+1)])
capacity_battery_tot = pd.DataFrame(index=scenario_list, columns=[f"CH0{i}" for i in range(1,7+1)])



mapping_grossregion_canton = pd.read_csv("aggregation/grossregion_mapping_edge.csv")
# create a dictionrary with with keys equal to unique values column number, and values equal to all the values in column region. 
# There might be multile values for a key.
map_CH0N_2_canton_dict = mapping_grossregion_canton.groupby("number")["region"].apply(list).to_dict()
map_CH0N_2_edgenumber_dict = mapping_grossregion_canton.groupby("number")["edge_number"].apply(list).to_dict()

for scenario in scenario_list:
    for region in [f"CH0{i}" for i in range(1,7+1)]:
        # "Total generation solar PV - Roof" -------------------------------------------------------------------------
        installed_capacity_pv = gen_max.loc[gen_max.index.str.contains(f"{region}_pv"), scenario].sum()/1000
        preexisting_capacity_pv = gen_max_infeedp.loc[gen_max_infeedp.index.str.contains(f"{region}_pv"), scenario].sum()/1000
        capacity_pv_tot.loc[scenario, region] = installed_capacity_pv + preexisting_capacity_pv      

        # wind power
        installed_capacity_wind = gen_max.loc[gen_max.index.str.contains(f"{region}_windon"), scenario].sum()/1000
        preexisting_capacity_wind = gen_max_infeedp.loc[gen_max_infeedp.index.str.contains(f"{region}_windon"), scenario].sum()/1000
        capacity_wind_tot.loc[scenario, region] = installed_capacity_wind + preexisting_capacity_wind

        # biomass/waste
        installed_capacity_biomass = gen_max.loc[gen_max.index.str.contains(f"{region}_biomass"), scenario].sum()/1000
        installed_capacity_biomass = installed_capacity_biomass + gen_max.loc[gen_max.index.str.contains(f"{region}_other"), scenario].sum()/1000
        preexisting_capacity_biomass = gen_max_infeedp.loc[gen_max_infeedp.index.str.contains(f"{region}_biomass"), scenario
        ].sum()/1000
        preexisting_capacity_biomass = preexisting_capacity_biomass + gen_max_infeedp.loc[gen_max_infeedp.index.str.contains(f"{region}_other"), scenario].sum()/1000
        capacity_biomass_tot.loc[scenario, region] = installed_capacity_biomass + preexisting_capacity_biomass

        # natural gas
        installed_capacity_gas = gen_max.loc[gen_max.index.str.contains(f"{region}_gas"), scenario].sum()/1000
        preexisting_capacity_gas = gen_max_infeedp.loc[gen_max_infeedp.index.str.contains(f"{region}_gas"), scenario].sum()/1000
        capacity_gas_tot.loc[scenario, region] = installed_capacity_gas + preexisting_capacity_gas 

        # nuclear
        installed_capacity_nuclear = gen_max.loc[gen_max.index.str.contains(f"{region}_nuclear"), scenario].sum()/1000   
        preexisting_capacity_nuclear = gen_max_infeedp.loc[gen_max_infeedp.index.str.contains(f"{region}_nuclear"), scenario].sum()/1000
        capacity_nuclear_tot.loc[scenario, region] = installed_capacity_nuclear + preexisting_capacity_nuclear

        # hydro dams
        # installed_capacity_dams = gen_max.loc[gen_max.index.str.contains(f"{region}_reservior"), scenario].sum()/1000
        #TODO: needs otther datapoints
        # Total capacity hydro dams
        # Total capacity run of river
        # Total capacity pumped hydro 

        # battery
        installed_capacity_battery = gen_max.loc[gen_max.index.str.contains(f"{region}_battery"), scenario].sum()/1000
        preexisting_capacity_battery = gen_max_infeedp.loc[gen_max_infeedp.index.str.contains(f"{region}_battery"), scenario].sum()/1000
        capacity_battery_tot.loc[scenario, region] = installed_capacity_battery + preexisting_capacity_battery

        for edge_number in map_CH0N_2_edgenumber_dict[region]:
            no_regions_within_CH0N = len(map_CH0N_2_canton_dict[region])
            output_spatial.loc[("FEM", scenario, "Total capacity solar PV - Roof"), str(edge_number)] = capacity_pv_tot.loc[scenario, region]/no_regions_within_CH0N
            output_spatial.loc[("FEM", scenario, "Total capacity wind power"), str(edge_number)] = capacity_wind_tot.loc[scenario, region]/no_regions_within_CH0N
            output_spatial.loc[("FEM", scenario, "Total capacity biomass/waste"), str(edge_number)] = capacity_biomass_tot.loc[scenario, region]/no_regions_within_CH0N
            output_spatial.loc[("FEM", scenario, "Total capacity natural gas "), str(edge_number)] = capacity_gas_tot.loc[scenario, region]/no_regions_within_CH0N
            output_spatial.loc[("FEM", scenario, "Total capacity nuclear"), str(edge_number)] = capacity_nuclear_tot.loc[scenario, region]/no_regions_within_CH0N
            # Total capacity hydro dams
            # Total capacity run of river
            # Total capacity pumped hydro 
            output_spatial.loc[("FEM", scenario, "Total capacity battery"), str(edge_number)] = capacity_battery_tot.loc[scenario, region]/no_regions_within_CH0N

    output_spatial.loc[("FEM", scenario, "Total capacity solar PV - Roof"), ("Unit", "Sum")] = ["GWp", capacity_pv_tot.loc[scenario].sum()]
    output_spatial.loc[("FEM", scenario, "Total capacity solar PV - Alpine"), ("Unit", "Sum")] = ["GWp", np.nan]
    output_spatial.loc[("FEM", scenario, "Total capacity wind power"), ("Unit", "Sum")] = ["GW", capacity_wind_tot.loc[scenario].sum()]
    output_spatial.loc[("FEM", scenario, "Total capacity gas other"), ("Unit", "Sum")] = ["GW", np.nan]
    output_spatial.loc[("FEM", scenario, "Total capacity biomass/waste"), ("Unit", "Sum")] = ["GW", capacity_biomass_tot.loc[scenario].sum()]
    output_spatial.loc[("FEM", scenario, "Total capacity natural gas "), ("Unit", "Sum")] = ["GW", capacity_gas_tot.loc[scenario].sum()]
    output_spatial.loc[("FEM", scenario, "Total capacity nuclear"), ("Unit", "Sum")] = ["GW", capacity_nuclear_tot.loc[scenario].sum()]
    # all hydro values should be read based on some Map_plant_tech or Map_tech_plant, rather than mannuel using reserverior, large_psp, etc.
    # Total capacity hydro dams
    installed_capacity_dams = 0
    installed_capacity_dams = installed_capacity_dams + gen_max.loc[gen_max.index.str.contains(f"reservior"), scenario].sum()/1000 # medium_reservior and small_reservior
    installed_capacity_dams = installed_capacity_dams + gen_max.loc[gen_max.index.str.contains(f"large_psp"), scenario].sum()/1000
    output_spatial.loc[("FEM", scenario, "Total capacity hydro dams"), ("Unit", "Sum")] = ["GW", installed_capacity_dams]
    # Total capacity run of river #TODO: missing data, fix the values it later
    output_spatial.loc[("FEM", scenario, "Total capacity run of river"), ("Unit", "Sum")] = ["GW", 4198/1000] # copied from input\hydro_PECD\PECD_EERA2021_ROR_2030_table.csv
    
    # Total capacity pumped hydro 
    # installed_capacity_psp_close = 0
    # installed_capacity_psp_close = installed_capacity_psp_close + gen_max.loc[gen_max.index.str.contains(f"CH00_psp_close"), scenario].sum()/1000
    # installed_capacity_psp_close = installed_capacity_psp_close + gen_max.loc[gen_max.index.str.contains(f"CH01_psp_close"), scenario].sum()/1000

    output_spatial.loc[("FEM", scenario, "Total capacity pumped hydro"), ("Unit", "Sum")] = ["GW", (2054 + 1900)/1000] 
    # TODO: fixed now, but need to read from files later, possibliy need to aggregate pmp_max files too.
    # copied psp_open of 2054  from input\hydro_PECD\PECD_EERA2021_reservoir_pumping_2030_table_representative_plants.csv
    # copied psp_close of 1900 from input\hydro_PECD\PECD_EERA2021_reservoir_pumping_2030_table.csv


    output_spatial.loc[("FEM", scenario, "Total capacity battery"), ("Unit", "Sum")] = ["GW", capacity_battery_tot.loc[scenario].sum()]


# Total generation ---------------------------------------------------------------------------------------------------
annual_balance_ch = pd.read_csv(f"{targte_aggregate_dir}/annual_balance_ch.csv", index_col=[0,1])


# Annual generation/discharge/charge/lostload ---------
# Sum of all regions
for scenario in scenario_list:
    # "Annual generation solar PV - Roof" -------------------------------------------------------------------------
    output_spatial.loc[("FEM", scenario, "Annual generation solar PV - Roof"), ("Unit", "Sum")] = ["GWh/yr", annual_balance_ch.loc[("infeed", "pv_all"), scenario]/1000]

    # Annual generation solar PV - Alpine
    output_spatial.loc[("FEM", scenario, "Annual generation solar PV - Alpine"), ("Unit", "Sum")] = ["GWh/yr", 0] #NOTE manually set to 0, fix it later

    # Annual generation wind power
    output_spatial.loc[("FEM", scenario, "Annual generation wind power"), ("Unit", "Sum")] = ["GWh/yr", annual_balance_ch.loc[("infeed", "wind_all"), scenario]/1000]

    # Annual generation biomass/waste
    output_spatial.loc[("FEM", scenario, "Annual generation biomass/waste"), ("Unit", "Sum")] = ["GWh/yr", annual_balance_ch.loc[("gen", ["biomass", "other"]), scenario].sum()/1000]

    # Annual generation natural gas
    output_spatial.loc[("FEM", scenario, "Annual generation natural gas"), ("Unit", "Sum")] = ["GWh/yr", annual_balance_ch.loc[("gen", "gas"), scenario].sum()/1000]

    # Annual generation gas other
    output_spatial.loc[("FEM", scenario, "Annual generation gas other"), ("Unit", "Sum")] = ["GWh/yr", 0] #NOTE manually set to 0, fix it later

    # Annual generation nuclear
    output_spatial.loc[("FEM", scenario, "Annual generation nuclear"), ("Unit", "Sum")] = ["GWh/yr", 0] #NOTE manually set to 0, fix it later

    # Annual generation hydro dam (psp_open in annual_balance_ch)
    output_spatial.loc[("FEM", scenario, "Annual generation hydro dam"), ("Unit", "Sum")] = ["GWh/yr", annual_balance_ch.loc[("gen", "psp_open"), scenario].sum()/1000]

    # Annual generation hydro run of river
    output_spatial.loc[("FEM", scenario, "Annual generation hydro run of river"), ("Unit", "Sum")] = ["GWh/yr", annual_balance_ch.loc[("infeed", "ror"), scenario].sum()/1000]

    # Annual discharge pumped hydro
    output_spatial.loc[("FEM", scenario, "Annual discharge pumped hydro"), ("Unit", "Sum")] = ["GWh/yr", annual_balance_ch.loc[("gen", "psp_close"), scenario].sum()/1000]

    # Annual charge pumped hydro
    output_spatial.loc[("FEM", scenario, "Annual charge pumped hydro"), ("Unit", "Sum")] = ["GWh/yr", annual_balance_ch.loc[("demand", ["flex psp_close", "flex psp_open"]), scenario].sum()/1000]

    # Annual battery charge
    output_spatial.loc[("FEM", scenario, "Annual battery charge"), ("Unit", "Sum")] = ["GWh/yr", annual_balance_ch.loc[("demand", "flex battery"), scenario].sum()/1000]

    # Annual battery discharge
    output_spatial.loc[("FEM", scenario, "Annual battery discharge"), ("Unit", "Sum")] = ["GWh/yr", annual_balance_ch.loc[("gen", "battery"), scenario].sum()/1000]

    # Annual load shedding
    output_spatial.loc[("FEM", scenario, "Annual load shedding"), ("Unit", "Sum")] = ["GWh/yr", annual_balance_ch.loc[("gen", "lostload"), scenario].sum()/1000]

    # Curtailment solar PV - Roof
    output_spatial.loc[("FEM", scenario, "Curtailment solar PV - Roof"), ("Unit", "Sum")] = ["GWh/yr", annual_balance_ch.loc[("demand", "curtailment"), scenario].sum()/1000]

    # Curtailment solar PV - Alpine
    output_spatial.loc[("FEM", scenario, "Curtailment solar PV - Alpine"), ("Unit", "Sum")] = ["GWh/yr", 0] #NOTE manually set to 0, fix it later

    # Curtailment wind power
    output_spatial.loc[("FEM", scenario, "Curtailment wind power"), ("Unit", "Sum")] = ["GWh/yr", annual_balance_ch.loc[("demand", "curtailment"), scenario].sum()/1000]

gen_year_sum_temporal = pd.read_csv(f"{targte_aggregate_dir}/gen_year_sum_temporal.csv", index_col=0).drop("year", axis=1)
storage_charge_year_sum_temporal = pd.read_csv(f"{targte_aggregate_dir}/storage_charge_year_sum_temporal.csv", index_col=0).drop("year", axis=1)

for scenario in scenario_list:
    for region in [f"CH0{i}" for i in range(1,7+1)]:
        # Annual generation solar PV - Roof
        # Annual generation solar PV - Alpine
        # Annual generation wind power

        #Annual generation biomass/waste
        gen_region = gen_year_sum_temporal.loc[gen_year_sum_temporal.index.str.contains(f"{region}_biomass"), scenario].sum()/1000  
        gen_region = gen_region + gen_year_sum_temporal.loc[gen_year_sum_temporal.index.str.contains(f"{region}_other"), scenario].sum()/1000

        for edge_number in map_CH0N_2_edgenumber_dict[region]:
            no_regions_within_CH0N = len(map_CH0N_2_canton_dict[region])
            output_spatial.loc[("FEM", scenario, "Annual generation biomass/waste"), str(edge_number)] = gen_region/no_regions_within_CH0N
        
        # Annual generation natural gas
        gen_region = gen_year_sum_temporal.loc[gen_year_sum_temporal.index.str.contains(f"{region}_gas"), scenario].sum()/1000
        for edge_number in map_CH0N_2_edgenumber_dict[region]:
            no_regions_within_CH0N = len(map_CH0N_2_canton_dict[region])
            output_spatial.loc[("FEM", scenario, "Annual generation natural gas"), str(edge_number)] = gen_region/no_regions_within_CH0N

        # # Annual generation hydro dam 
        # gen_region = gen_year_sum_temporal.loc[gen_year_sum_temporal.index.str.contains("reservior"), scenario].sum()/1000
        # gen_region = gen_region + gen_year_sum_temporal.loc[gen_year_sum_temporal.index.str.contains("large_psp"), scenario].sum()/1000

        # Annual battery charge
        gen_region = gen_year_sum_temporal.loc[gen_year_sum_temporal.index.str.contains(f"{region}_battery"), scenario].sum()/1000
        for edge_number in map_CH0N_2_edgenumber_dict[region]:
            no_regions_within_CH0N = len(map_CH0N_2_canton_dict[region])
            output_spatial.loc[("FEM", scenario, "Annual battery discharge"), str(edge_number)] = gen_region/no_regions_within_CH0N

        # Annual battery discharge
        gen_region = storage_charge_year_sum_temporal.loc[storage_charge_year_sum_temporal.index.str.contains(f"{region}_battery"), scenario].sum()/1000
        for edge_number in map_CH0N_2_edgenumber_dict[region]:
            no_regions_within_CH0N = len(map_CH0N_2_canton_dict[region])
            output_spatial.loc[("FEM", scenario, "Annual battery charge"), str(edge_number)] = gen_region/no_regions_within_CH0N

# Winter/summer
for scenario in scenario_list:
    # Charge pumped hydro WINTER and Charge pumped hydro SUMMER
    target_range = gen_dem_timeseries.loc[(scenario, "demand", "flex psp_open"), :]/1000 + gen_dem_timeseries.loc[(scenario, "demand", "flex psp_close"), :]/1000
    target_range = target_range.reindex(export_time_steps, level='hour')

    # sum values in target_range when the hour is in winter
    winter_time_steps = [f"t_{i}" for i in range(6553, 8760+1)] + [f"t_{i}" for i in range(1, 2184)]
    summer_time_steps = [f"t_{i}" for i in range(2185, 6552+1)]

    target_range_winter = target_range.loc[target_range.index.isin(winter_time_steps)]

    # assign values to output_spatial
    output_spatial.loc[("FEM", scenario, "Charge pumped hydro WINTER"), ("Unit", "Sum")] = ["GWh", target_range_winter.sum()]

    # Charge pumped hydro SUMMER
    target_range_summer = target_range.loc[target_range.index.isin(summer_time_steps)]

    # assign values to output_spatial
    output_spatial.loc[("FEM", scenario, "Charge pumped hydro SUMMER"), ("Unit", "Sum")] = ["GWh", target_range_summer.sum()]

    # Average netload WINTER and Average netload SUMMER
    target_range = gen_dem_timeseries.loc[(scenario, "demand", "fixed modelled household"), :]/1000 + \
                   gen_dem_timeseries.loc[(scenario, "demand", "fixed modelled commercial"), :]/1000 - \
                   gen_dem_timeseries.loc[(scenario, "gen", "pv_all"), :]/1000 - \
                   gen_dem_timeseries.loc[(scenario, "gen", "wind_all"), :]/1000
    
    target_range_winter = target_range.loc[target_range.index.isin(winter_time_steps)]
    output_spatial.loc[("FEM", scenario, "Average netload WINTER"), ("Unit", "Sum")] = ["GWh", target_range_winter.sum()]

    target_range_summer = target_range.loc[target_range.index.isin(summer_time_steps)]
    output_spatial.loc[("FEM", scenario, "Average netload SUMMER"), ("Unit", "Sum")] = ["GWh", target_range_summer.sum()]



# print("Input_Temp")
# # # Hourly electricity demand - total --------------------------------------------------------------------------------------------- 
# target_range = gen_dem_timeseries.loc[(scenario, "demand", "fixed modelled household"), :]/1000 + \
#                 gen_dem_timeseries.loc[(scenario, "demand", "fixed modelled commercial"), :]/1000 - \

# target_range = target_range.reindex(export_time_steps, level='hour')

# # assign values of target_range to output_temp
# input_temp.loc[("FEM", "All scenarios", "Hourly electricity demand - total"), :] = ["GWh"] + target_range.values.tolist()

print("Exporting to excel file")
# create the excle file 
# current date and time as string
now = datetime.datetime.now().astimezone().strftime("%Y%m%d%H%M")
writer = pd.ExcelWriter(f"{targte_edge_dir}/MIP_reporting_FEM_{now}.xlsx")

# flatten output_sys and output_temp before writing to excel
output_sys.reset_index().to_excel(writer, sheet_name="Output_Sys", index=False)
output_temp.reset_index().to_excel(writer, sheet_name="Output_Temp", index=False)
output_spatial.reset_index().to_excel(writer, sheet_name="output_spatial", index=False)

# # Save the Excel file
writer.close()

print(f"Exported to {targte_edge_dir}/MIP_reporting_FEM_{now}.xlsx")


# output_temp.to_clipboard()
# # Sample data
# data1 = {"Name": ["Alice", "Bob", "Charlie"], "Age": [25, 30, 35]}
# data2 = {"City": ["New York", "London", "Paris"], "Country": ["USA", "UK", "France"]}

# # Create DataFrames
# df1 = pd.DataFrame(data1)
# df2 = pd.DataFrame(data2)


# df1.to_excel(writer, sheet_name="Sheet1", index=False)
# df2.to_excel(writer, sheet_name="Sheet2", index=False)



# # add a sheet "Output_Sys" to the excel file
# output_sys = pd.read_csv(targte_aggregate_dir + "\Output_Sys.csv")

# # # create a sheet "Output_Sys"
# # output_sys = pd.read_csv(targte_aggregate_dir + "\Output_Sys.csv")



# # # call the function
# # export_edge(targte_aggregate_dir, targte_edge_dir)
