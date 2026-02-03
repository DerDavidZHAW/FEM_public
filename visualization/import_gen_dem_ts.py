import pandas as pd
import os
import utils.utilities_visualization as util
import utils.price_weighting_multi_scen as util_price

def read_filtered_csv(file_path, scenario_name):
    # Read the CSV file
    df = pd.read_csv(file_path)
    
    # Check if 'Scenarios' column exists and filter by 'scenario_name' if it does
    if 'Scenarios' in df.columns:
        # Filter by scenario_name and remove the 'Scenarios' column
        df = df[df['Scenarios'] == scenario_name].drop(columns=['Scenarios'])

    
    return df

def safe_pivot_csv(output_dir, filename, scenario_name, index, columns, values, time_indices):
    """
    Safely read, filter, pivot and reindex a CSV file with comprehensive error handling.
    
    Parameters:
    -----------
    output_dir : str
        Directory containing the CSV file
    filename : str
        Name of the CSV file (e.g., "genTh.csv")
    scenario_name : str
        Scenario name to filter by
    index : str or list
        Column(s) to use as index in pivot
    columns : str
        Column to use for pivot columns
    values : str
        Column to use for pivot values
    time_indices : list
        Time indices to reindex to
        
    Returns:
    --------
    pd.DataFrame
        Pivoted and reindexed dataframe, or empty dataframe if any error occurs
    """
    try:
        file_path = output_dir + filename
        
        # Check if file exists
        if not os.path.isfile(file_path):
            return pd.DataFrame()
        
        # Read and filter the CSV
        df = read_filtered_csv(file_path, scenario_name)
        
        # Check if dataframe is empty after filtering
        if df.empty:
            return pd.DataFrame()
        
        # Check if required columns exist
        required_cols = [columns, values]
        if isinstance(index, list):
            required_cols.extend(index)
        else:
            required_cols.append(index)
        
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"Warning: {filename} is missing required columns: {missing_cols}")
            return pd.DataFrame()
        
        # Perform pivot and reindex
        pivoted = df.pivot(index=index, columns=columns, values=values).reindex(columns=time_indices)
        
        return pivoted
        
    except (FileNotFoundError, KeyError, ValueError, pd.errors.DataError) as e:
        print(f"Warning: Could not process {filename}: {str(e)}")
        return pd.DataFrame()

def import_gen_demand_timeseries(output_dir, scenario_name):
    # NOTE: all of consumer data analysis needs to be adjusted (in winter reserve, households are not considered as consumers)
    # NOTE: change all instances of 8230 to the correct number based on "consumers_representing" in scenarios.py First, consumers_representing should be exported to the output folder (possibly in statistics.csv)
    print("Importing data from csvs...")
    gen = pd.read_csv(output_dir + "gen.csv") # to be used both for obtainting the time indices and generation data
    time_indices = gen.loc[:, "T"].unique().tolist()

    # find scenarios in the data
    if "Scenarios" in gen.columns:
        scenarios_list = gen.loc[:, "Scenarios"].unique().tolist()
    print("Scenarios found: ", scenarios_list)
    # generation ------------------------------------------
    # generations per plant and time steps
    generation_all = (
        read_filtered_csv(output_dir + "gen.csv", scenario_name).pivot(index="P_gen", columns="T", values="value")
        .reindex(columns=time_indices)
    )

    for consumer_id in range(1, 300 + 1): #NOTE: should not be set mannually to 300
        file_path = output_dir + "ID" + str(consumer_id) + "_gen.csv"
        # if file file_path exists, read it and append it to generation_all
        if os.path.isfile(file_path):
            data_consumer = pd.read_csv(
                file_path, header=0, names=["P_gen", "T", "value"]
            )
            generation_all_consumer = 8230 * data_consumer.pivot(
                index="P_gen", columns="T", values="value"
            ).reindex(columns=time_indices)
            generation_all = pd.concat([generation_all, generation_all_consumer])

    # demand inflexible ------------------------------------------
    # flexible demand per consumer and time steps
    demand_inflx_all = (
        read_filtered_csv(output_dir + "demand.csv", scenario_name)
        .pivot(
            index=["Consumer", "Consumption_types_inflex"], columns="T", values="value"
        )
        .reindex(columns=time_indices)
    )

    for consumer_id in range(1, 300 + 1):  #NOTE: should not be set mannually to 300
        file_path = output_dir + "ID" + str(consumer_id) + "_demand.csv"
        # if file file_path exists, read it and append it to demand_inflx_all
        if os.path.isfile(file_path):
            data_consumer = pd.read_csv(
                file_path,
                header=0,
                names=["Consumer", "Consumption_types_inflex", "T", "value"],
            )
            demand_inflx_all_consumer = 8230 * data_consumer.pivot(
                index=["Consumer", "Consumption_types_inflex"],
                columns="T",
                values="value",
            ).reindex(columns=time_indices)
            demand_inflx_all = pd.concat([demand_inflx_all, demand_inflx_all_consumer])

    # demand flexible ------------------------------------------
    # inflexible demand, including consumers', battery storage, PSP, per plant and time steps
    demand_flxbl_all = (
        read_filtered_csv(output_dir + "storage_charge.csv", scenario_name)
        .pivot(index="P_pumping", columns="T", values="value")
        .reindex(columns=time_indices)
    )

    for consumer_id in range(1, 300 + 1):  #NOTE: should not be set mannually to 300
        file_path = output_dir + "ID" + str(consumer_id) + "_storage_charge.csv"
        # if file file_path exists, read it and append it to demand_flxbl_all
        if os.path.isfile(file_path):
            data_consumer = pd.read_csv(
                file_path, header=0, names=["P_pumping", "T", "value"]
            )
            demand_flxbl_all_consumer = 8230 * data_consumer.pivot(
                index="P_pumping", columns="T", values="value"
            ).reindex(columns=time_indices)
            demand_flxbl_all = pd.concat([demand_flxbl_all, demand_flxbl_all_consumer])

    # prices ------------------------------------------
    # prices, per node and time steps
    price_all = (
        read_filtered_csv(output_dir + "energy_balance_dual.csv", scenario_name)
        .pivot(index="Node", columns="T", values="value")
        .reindex(columns=time_indices)
    )
    settings = pd.read_csv(output_dir + "settings.csv", index_col=0, header=0)
    weight_shock = settings.loc["weight_in_objective_fcn", scenario_name]
    price_all = price_all/float(weight_shock) # type: ignore
    # soc dual ------------------------------------------
    # marginal value of storage (opportunity cost), per storage plant and time steps
    soc_dual_all = (
        read_filtered_csv(output_dir + "storage_soc_dual.csv", scenario_name)
        .pivot(index="P_storage", columns="T", values="value")
        .reindex(columns=time_indices)
    )
    
    socth_dual_all = safe_pivot_csv(output_dir, "storageTh_soc_dual.csv", scenario_name, "PDH_storage", "T", "value", time_indices)

    # export ------------------------------------------
    # trade over lines, per line and time steps
    # negative value indicates trade to start_node from end_node in Map_line_node
    export_all = (
        read_filtered_csv(output_dir + "Export.csv", scenario_name)
        .pivot(index="lineATC", columns="T", values="value")
        .reindex(columns=time_indices)
    )

    # soc -----------------------------------------------
    # state of charge
    soc_all = (
        read_filtered_csv(output_dir + "soc.csv", scenario_name)
        .pivot(index="P_storage", columns="T", values="value")
        .reindex(columns=time_indices)
    )

    # for variables lost load, infeed, and curtailment, the data is aggregated and stored in one row "IDs"
    # lost load ------------------------------------------
    # lost load, per consumer and time steps (multiple lost load steps per consumer and time step)
    lostload_all = (
        pd.pivot_table(
            read_filtered_csv(output_dir + "lostload.csv", scenario_name), index="Consumer", columns="T", values="value", aggfunc='sum')
        .reindex(columns=time_indices)
    )

    # NOTE: make sure it works for a dataset with lost load from multiple consumers
    lostload_all_consumer = pd.Series(index=time_indices, dtype=float, data=0.0)
    for consumer_id in range(1, 300 + 1):
        file_path = output_dir + "ID" + str(consumer_id) + "_lostload.csv"
        # if file file_path exists, read it and append it to lostload_all
        if os.path.isfile(file_path):
            data_consumer = pd.read_csv(
                file_path, header=0, names=["Consumer", "T", "value"]
            )
            lostload_all_consumer = lostload_all_consumer + 8230 * data_consumer.pivot(
                index="Consumer", columns="T", values="value"
            ).reindex(columns=time_indices).sum(axis=0)
        
    lostload_all.loc["IDs",:] = lostload_all_consumer


    # infeed ------------------------------------------
    # infeed, per node and time steps
    infeed_all = (
        read_filtered_csv(output_dir + "infeed.csv",scenario_name).pivot(index=["Consumer_with_infeed", "Tech_infeed"], columns="T", values="value")
        .reindex(columns=time_indices)
    )

    infeed_all_consumer = pd.Series(index=time_indices, dtype=float, data=0.0)
    for consumer_id in range(1, 300 + 1):
        file_path = output_dir + "ID" + str(consumer_id) + "_infeed.csv"
        # if file file_path exists, read it and append it to infeed_all
        if os.path.isfile(file_path):
            data_consumer = pd.read_csv(
                file_path,
                header=0,
                names=["Consumer_with_infeed", "Tech_infeed", "T", "value"],
            )
            infeed_all_consumer = infeed_all_consumer + 8230 * data_consumer.pivot(
                index=["Consumer_with_infeed", "Tech_infeed"],
                columns="T",
                values="value",
            ).reindex(columns=time_indices).sum(axis=0)

    infeed_all.loc[("IDs", "pv"),:] = infeed_all_consumer  #NOTE: technology to be adjusted, if input data is not pv



    # curtailment ------------------------------------------
    # curtailment, per region and time steps
    curtailment_all = (
        read_filtered_csv(output_dir + "curtailment.csv", scenario_name).pivot(index="Consumer_with_infeed", columns="T", values="value")
        .reindex(columns=time_indices)
    )

    curtailment_all_consumer = pd.Series(index=time_indices, dtype=float, data=0.0)

    for consumer_id in range(1, 300 + 1):
        file_path = output_dir + "ID" + str(consumer_id) + "_curtailment.csv"
        # if file file_path exists, read it and append it to curtailment_all
        if os.path.isfile(file_path):
            data_consumer = pd.read_csv(
                file_path, header=0, names=["Consumer_with_infeed", "T", "value"]
            )
            curtailment_all_consumer = curtailment_all_consumer + 8230 * data_consumer.pivot(
                index="Consumer_with_infeed", columns="T", values="value"
            ).reindex(columns=time_indices).sum(axis=0)

    curtailment_all.loc["IDs",:] = curtailment_all_consumer
    
    # imported exported data, households ------------------------------------------

    withdrawal_all = pd.Series(index=time_indices, dtype=float, data=0.0)

    for consumer_id in range(1, 300 + 1):
        file_path = output_dir + "ID" + str(consumer_id) + "_imported.csv"
        if os.path.isfile(file_path):
            data_consumer = pd.read_csv(
                file_path, header=0, index_col=1, names=["Consumer", "T", "value"]
            ).loc[:, "value"]
            # withdrawal_all is equal to withdrawal_all + data_consumer where 
            withdrawal_all = withdrawal_all +  8230 * data_consumer

    
    injection_all = pd.Series(index=time_indices, dtype=float, data=0.0)

    for consumer_id in range(1, 300 + 1):
        file_path = output_dir + "ID" + str(consumer_id) + "_exported.csv"
        if os.path.isfile(file_path):
            data_consumer = pd.read_csv(
                file_path, header=0, index_col=1, names=["Consumer", "T", "value"]
            ).loc[:, "value"]
            # injection_all is equal to injection_all + data_consumer where 
            injection_all = injection_all +  8230 * data_consumer


    # ------------------------------------------------------------------------------------------------------
    # ------------------------------------------ District heating ------------------------------------------
    # ------------------------------------------------------------------------------------------------------
    # generationTH : generation of district heating, per plant and time steps
    supplyTH_all = safe_pivot_csv(output_dir, "genTh.csv", scenario_name, "PDH", "T", "value", time_indices)

    # consumptionDH : consumption of district heating, per district heating and time steps
    consumptionDH_all = safe_pivot_csv(output_dir, "demandDH.csv", scenario_name, "NodeDH", "T", "value", time_indices)
        
    storageTH_all = safe_pivot_csv(output_dir, "storage_chargeTh.csv", scenario_name, "PDH_storagecharge", "T", "value", time_indices)

    socTH_all = safe_pivot_csv(output_dir, "socTH.csv", scenario_name, "PDH_TES", "T", "value", time_indices)

    # for backward compatibility purpose (some older versions did not allow for curtailment of the thermal supply)
    curtailmentTH_all = safe_pivot_csv(output_dir, "curtailmentTh.csv", scenario_name, "NodeDH", "T", "value", time_indices)
    # If curtailmentTH_all is empty but consumptionDH_all exists, create zero dataframe with same shape
    if curtailmentTH_all.empty and not consumptionDH_all.empty:
        curtailmentTH_all = pd.DataFrame(0, index=consumptionDH_all.index, columns=consumptionDH_all.columns)

    # ------------------------------------------------------------------------------------------------------
    # ------------------------------------------ household heat pumps --------------------------------------
    # ------------------------------------------------------------------------------------------------------

    # for backward compatibility purpose (some older versions did not allow for household heat pumps)
    th_sl_all = safe_pivot_csv(output_dir, "th_sl.csv", scenario_name, "BA_names", "T", "value", time_indices)
    
    # Read BA_th_lim only if th_sl_all was successfully loaded
    if not th_sl_all.empty:
        try:
            BA_th_lim = pd.read_csv(output_dir + "BA_th_lim.csv", index_col=0)
        except (FileNotFoundError, KeyError):
            BA_th_lim = pd.DataFrame()
    else:
        BA_th_lim = pd.DataFrame()
    
    # price thermal ------------------------------------------
    # prices, per node of district heating (including industrial load) and time steps
    # backward compatibility 
    priceTh_all = safe_pivot_csv(output_dir, "energy_balancethermal_dual.csv", scenario_name, "NodeDH", "T", "value", time_indices)
    if not priceTh_all.empty:
        priceTh_all = priceTh_all/float(weight_shock) #type: ignore

    # ------------------------------------------------------------------------------------------------------
    # ------------------------------------------ V2G base load (outflow) -----------------------------------
    # ------------------------------------------------------------------------------------------------------
    # for backward compatibility purpose (some older versions did not allow for V2G)
    v2g_outflow_all = safe_pivot_csv(output_dir, "outflow.csv", scenario_name, "P_outflow", "T", "value", time_indices)

    # ------------------------------------------------------------------------------------------------------
    # ------------------------------------------ EV Inflexible demand --------------------------------------
    # ------------------------------------------------------------------------------------------------------
    # EV inflexible demand: the portion of EV consumption that follows a fixed charging profile
    # This is stored separately from regular demand to enable visualization
    EV_inflexible_demand_all = safe_pivot_csv(output_dir, "EV_inflexible_demand.csv", scenario_name, "Node", "T", "value", time_indices)

    # ------------------------------------------------------------------------------------------------------
    # ------------------------------------------ HP Inflexible demand --------------------------------------
    # ------------------------------------------------------------------------------------------------------
    # HP inflexible demand: the portion of household heat pump consumption that follows a fixed profile
    # This is stored separately from regular demand to enable visualization
    HP_inflexible_demand_all = safe_pivot_csv(output_dir, "HP_inflexible_demand.csv", scenario_name, "Node", "T", "value", time_indices)

    # ------------------------------------------------------------------------------------------------------
    # -------------------------------------- adjusting time stamps------------------------------------------
    # ------------------------------------------------------------------------------------------------------
    #NOTE: do for all *time sereis* that are to be returned should be adjusted

    # before retuning the data, we need to adjust the time stamps in the dataframes
    # wheather in columns or index of the dataframes, replace any (if at all) instances of t_t (t_1, t_2, etc.) with t_date (2050-01-01 00:00:00, 2050-01-01 01:00:00, etc.)
    time_indices_org = generation_all.columns.tolist()

    hour_dict_custom = util.hour_to_timestamp(time_indices_org, year=2035)  # year 2035 is used because it starts on Monday and is not a leap year

    # replace time indices in all dataframes, weathear in columns or index, with the new time indices, i.e., replace keys of hour_dict_custom with values of hour_dict_custom
    generation_all = generation_all.rename(columns=hour_dict_custom)
    demand_inflx_all = demand_inflx_all.rename(columns=hour_dict_custom)
    demand_flxbl_all = demand_flxbl_all.rename(columns=hour_dict_custom)
    price_all = price_all.rename(columns=hour_dict_custom)
    export_all = export_all.rename(columns=hour_dict_custom)
    soc_all = soc_all.rename(columns=hour_dict_custom)
    soc_dual_all = soc_dual_all.rename(columns=hour_dict_custom)
    socth_dual_all = socth_dual_all.rename(columns=hour_dict_custom)
    lostload_all = lostload_all.rename(columns=hour_dict_custom)
    infeed_all = infeed_all.rename(columns=hour_dict_custom)
    curtailment_all = curtailment_all.rename(columns=hour_dict_custom)
    withdrawal_all = withdrawal_all.rename(index=hour_dict_custom)
    injection_all = injection_all.rename(index=hour_dict_custom)
    supplyTH_all = supplyTH_all.rename(columns=hour_dict_custom)
    consumptionDH_all = consumptionDH_all.rename(columns=hour_dict_custom)
    storageTH_all = storageTH_all.rename(columns=hour_dict_custom)
    curtailmentTH_all = curtailmentTH_all.rename(columns=hour_dict_custom)
    socTH_all = socTH_all.rename(columns=hour_dict_custom)
    th_sl_all = th_sl_all.rename(columns=hour_dict_custom)
    BA_th_lim = BA_th_lim.rename(index=hour_dict_custom) # technically BA_th_lim is not a time series, so this is not necessary, but it is done for consistency (this line has no effect on the dataframe)
    v2g_outflow_all = v2g_outflow_all.rename(columns=hour_dict_custom)
    priceTh_all = priceTh_all.rename(columns=hour_dict_custom)
    EV_inflexible_demand_all = EV_inflexible_demand_all.rename(columns=hour_dict_custom)
    HP_inflexible_demand_all = HP_inflexible_demand_all.rename(columns=hour_dict_custom)


    return (
        generation_all,
        demand_inflx_all,
        demand_flxbl_all,
        export_all,
        soc_all,
        price_all,
        soc_dual_all,
        socth_dual_all,
        lostload_all,
        infeed_all,
        curtailment_all,
        withdrawal_all,
        injection_all,
        supplyTH_all,
        consumptionDH_all,
        curtailmentTH_all,
        storageTH_all,
        socTH_all,
        th_sl_all,
        BA_th_lim,
        v2g_outflow_all,
        priceTh_all,
        EV_inflexible_demand_all,
        HP_inflexible_demand_all,
    )
