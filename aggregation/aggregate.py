import os
import pandas as pd
import time
import utils.reverse_mapping as rev_map
import numpy as np
import plotly.graph_objects as go
import utils.price_weighting_multi_scen as multiscen_adj


def aggregate_params_vars(scenarios_to_agg, item, agg_type_dict, output_dir, map_scen_subscen):
    """
    This function aggregates the results of several scenarios, and saves the aggregated results in a csv file.
    Input arguments:
        scenarios_to_agg: set of scenarios to aggregate
        item: parameter to aggregate
        agg_type_dict: dictionary with the type of aggregation (sum, mean, min, max, or several of them) and the temporal and spatial aggregation levels
        e.g., {"type": "sum", "temporal": ["day", "week", "month", "season", "year"], "spatial": True}
        output_dir: output directory to save the aggregated results
    """
    # subscen_list is the list of all subscenarios for the scenarios to aggregate
    subscen_list = [subscen for scen in map_scen_subscen.values() for subscen in scen]

    # how datapoints should be aggregated: sum, mean, min, max
    agg_type = agg_type_dict["type"]

    temporal_agg_levels = agg_type_dict["temporal"]

    mappings_list = agg_type_dict["mappings"]

    # Map_file_name = agg_type_dict["other_mapping"]

    # create output_dir if it does not exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # create a dictionary of filenames and paths for the scenarios to aggregate
    filenames_paths_dict = {
        scenario_name: ["output/" + scenario_name + "/" + item + ".csv"]
        for scenario_name in scenarios_to_agg
    }

    # a dictionary that keeps track of whether the a file is central or tariff based: if the file does not include files with IDXXX_item, it is central
    track_if_central_dict = {}
    for scenario_name in scenarios_to_agg:  
        track_if_central_dict["output/" + scenario_name + "/" + item + ".csv"] = True  
        for consumer_id in range(1, 300+1):
            file_path = "output/" + scenario_name + "/ID" + str(consumer_id) + "_" + item +".csv"
            # if file file_path exists, read it and append it to generation_all
            if os.path.isfile(file_path):
                filenames_paths_dict[scenario_name].extend([file_path])
                track_if_central_dict[file_path] = False
            # else:
            #     track_if_central_dict[file_path] = True


    # Initialize an empty dictionary to store the extracted values
    data_dict = {}

    # Loop through each file in the directory
    header_line = []
    for scenario_name, file_path_list in filenames_paths_dict.items():
        # print("Reading " + scenario_name + "...")
        # Read the CSV file and extract the rows
        for file_path in file_path_list:
            print(file_path)
            # check if file file_path exists
            if os.path.isfile(file_path):
                with open(file_path, "r") as file:
                    lines = file.readlines()
                    if not header_line:
                        header_line = lines[0].strip().split(",")
                        if "Scenarios" in header_line:
                            header_line.remove("Scenarios")
                            subscen_exists = True
                        else:
                            subscen_exists = False
                    
                    for line in lines[1:]:  # Skip the header line
                        parts = line.strip().split(",")
                        indices_len = len(parts) - 1

                        if subscen_exists:
                            scenario_name = parts[-2]
                            if track_if_central_dict[file_path]:
                                value = parts[indices_len]
                            else:
                                value = 8230 * float(parts[indices_len])
                            key = tuple(parts[i] for i in range(indices_len-1))

                        else:
                            indices_len = len(parts) - 1
                            if track_if_central_dict[file_path]:
                                value = parts[indices_len]
                            else:
                                value = 8230 * float(parts[indices_len])
                            key = tuple(parts[i] for i in range(indices_len))

                        data_dict[key] = data_dict.get(key, {})
                        data_dict[key][scenario_name] = value
            else:
                print("File " + file_path + " does not exist" + 40 * "-x")
                print("Skipping " + file_path + "...")
                # return
            
    agg_df = pd.DataFrame.from_dict(data_dict, orient="index")
    list_ind_name = [item for item in header_line[:-1]]
    agg_df = agg_df.rename_axis(index=list_ind_name)

    # Save the DataFrame as a CSV file
    agg_df.to_csv(output_dir + item + ".csv")

    if subscen_exists:
        scenarios_to_agg = subscen_list
    else:
        scenarios_to_agg = scenarios_to_agg

    # if the aggregated parameter is a time series, create daily, weekly, monthly, seasonal, and annual aggregations of the results
    if temporal_agg_levels:
        agg_df = agg_df.astype(float)
        agg_df = agg_df.reset_index()
        time_maps = pd.read_csv("input/timemaps_hydro_year.csv", index_col=0)

        # show which columns in agg_df are time series
        # Select columns from the third column onwards
        first_row = agg_df.iloc[:1, :]
        all_col_names = [
            col for col in first_row.columns.tolist() if col not in scenarios_to_agg
        ]
        t_col_name = "T"
        non_t_col_names = [col for col in all_col_names if col != t_col_name]

        for other_mapping in mappings_list:
            print("Aggregating " + item + " by " +
                agg_type + " for " + other_mapping + "...")
            if other_mapping != "temporal":
                geo_maps_rev = pd.read_csv(
                    "aggregation//" + other_mapping + ".csv", index_col=0)
                geo_map = rev_map.reverse_mapping(geo_maps_rev)

                # Find the name of the column with the indices of geo_map (e.g., node, plant, etc.): output: "level_0"
                # NOTE: lines below can possibly be improved by using other_mapping directly, now that columns in output csvs have set name as the header
                geomap_col_name = []
                for column in non_t_col_names:
                    # if any of the values of geo_map.index.to_list() is in agg_df[column].values:
                    if any(agg_df[column].isin(geo_map.index.to_list())):
                        geomap_col_name = column
                        break

            for agg_period in temporal_agg_levels:
                # look at the column in time_maps corresponding to the agg_period
                time_map = time_maps[agg_period]

                # Merge the dataframes on the timestamp 't' (adds column "agg_period" to match "t")
                merged_df = agg_df.merge(
                    time_map, left_on=t_col_name, right_on="t")

                if other_mapping != "temporal":
                    # Merge the dataframes on geolocation (adds column "region" to merged_df to match elements in geomap_col_name. e.g., adds "CH00" at column "region" to the row with item CH00_dam)
                    merged_df = merged_df.merge(
                        geo_map, left_on=geomap_col_name, right_on="item_asset")
                    # Group by e.g., 'day' and 'region'
                    grouping_criteria = [
                        item for item in [agg_period] + ["Node"]]
                elif other_mapping == "temporal":
                    # Group by e.g., 'level_0' (plant) and 'day'
                    grouping_criteria = [
                        item for item in non_t_col_names + [agg_period]]

                if agg_type == "sum":
                    grouped_df = merged_df.groupby(grouping_criteria)[
                        scenarios_to_agg].sum()
                elif agg_type == "mean":
                    grouped_df = merged_df.groupby(grouping_criteria)[
                        scenarios_to_agg].mean()
                elif agg_type == "min":
                    grouped_df = merged_df.groupby(grouping_criteria)[
                        scenarios_to_agg].min()
                elif agg_type == "max":
                    grouped_df = merged_df.groupby(grouping_criteria)[
                        scenarios_to_agg].max()
                else:
                    print("agg_type not recognized")
                    break

                # Reset the index to have 'day' as a column instead of an index
                grouped_df.reset_index(inplace=True)

                # order the column agg_period based on values in time_map
                # Convert the 'day' column to a categorical datatype with the custom order based on time_map.unique()
                grouped_df[agg_period] = pd.Categorical(
                    grouped_df[agg_period], categories=time_map.unique(), ordered=True
                )

                # Sort the dataframe based on the custom order of the 'day' column
                grouped_df.sort_values(by=agg_period, inplace=True)

                if other_mapping:
                    output_file = output_dir + item + "_" + agg_period + \
                        "_" + agg_type + "_" + other_mapping + ".csv"
                else:
                    output_file = output_dir + item + "_" + \
                        agg_period + "_" + agg_type + "_" + ".csv"

                grouped_df.to_csv(output_file, index=False)

def grouped_weighted_avg(values, weights, by):
    sum_cost_hourly = (values * weights).values
    sum_cost = sum_cost_hourly.sum() 
    sum_weights = weights.sum()
    weighted_avg = sum_cost / sum_weights
    return sum_cost, weighted_avg, sum_cost_hourly

def aggregate_indicators(scenarios_to_agg, item, agg_type, output_dir,map_scen_subscen):
    """
    This function aggregates the results of several scenarios from csv files created by aggregate_params_vars, and saves the aggregated results in a csv file.
    The code is supposed to work for any number of dimensions of the scenarios (e.g., if later weather_year is added as a dimension to the model).
    Input arguments:
        scenarios_to_agg: set of scenarios to aggregate
        item: parameter to aggregate
        agg_type: type of aggregation (sum, mean, min, max, or several of them)
        output_dir: output directory to save the aggregated results
    Output: csv file(s) with the aggregated results (follow to_csv method in the code to see the name of the csv file)
    """
    subcescen_list = [subscen for scen in map_scen_subscen.values() for subscen in scen]
    # separate ifs for different item types ---------------------------------------------------------------------
    if item == "price_weighted":

        # read the hourly price, hourly demand, and hourly storage charge (flexible demand) for each scenario.
        price_hourly = pd.read_csv(
            output_dir + "energy_balance_dual_hour_mean_temporal.csv")
        price_hourly = multiscen_adj.price_weighting_multi_scen(price_hourly, output_dir)
        d_inflex_hourly = pd.read_csv(
            output_dir + "demand_hour_sum_Map_node_consumer.csv")
        d_flex_hourly = pd.read_csv(
            output_dir + "storage_charge_hour_sum_Map_node_plant.csv")

        # NOTE: lines below were aded just to check if extra dimensions are introduced 
        # price_hourly["weather_year"] = "1984"
        # d_flex_hourly["weather_year"] = "1984"
        # d_inflex_hourly["weather_year"] = "1984"

        # obtain dimension of the dataset ---------------------------------------------------------------------
        #  all dimensions of the dataset (e.g., Nodes, run years, hour). Used in indexing the dataframe.
        dimension_list_all = [dimension for dimension in price_hourly.columns.to_list(
        ) if dimension not in subcescen_list]

        # find all dimensions of the dataset except hour
        # Use in indexing the dataframe and in creating a mesh of all unique combinations of dimensions.
        dimension_list = [dimension for dimension in price_hourly.columns.to_list(
        ) if dimension not in subcescen_list + ["hour",]]

        # find unique values in the dimension_list
        dimension_unique_elements = {}
        for dimension in dimension_list:
            dimension_unique_elements[dimension] = price_hourly[dimension].unique(
            ).tolist()

        # dataframe manipulation: redefine dataframes multiindex dataframe with the dimension_list as indices
        price_hourly = price_hourly.set_index(dimension_list_all)
        d_inflex_hourly = d_inflex_hourly.set_index(dimension_list_all)
        d_flex_hourly = d_flex_hourly.set_index(dimension_list_all)

        # create a mesh of all unique combinations of dimensions. ---------------------------------------------
        # Used in indexing the dataframe. This approach allows for flexible number of dimensions.
        mesh = np.array(np.meshgrid(*dimension_unique_elements.values())).T.reshape(
            -1, len(dimension_unique_elements))

        # loop over the mesh elements -------------------------------------------------------------------------
        # to calculate the weighted average price for each unique combination of dimensions
        price_weighted_avg = {}
        sum_cost = {}
        sum_cost_hourly = {}
        for mesh_element in mesh:
            print("Calculating average price over ")
            print(mesh_element)

            # create copies of original data and summing up the demand
            price_subset = price_hourly.copy()
            d_hourly_subset = d_flex_hourly + d_inflex_hourly

            # create a subset of dataframes that has the same indices as the mesh_element.---------------------
            # Dimensions are narrowed down selected one by one.
            for dimension_counter in range(len(dimension_list)):
                # dimension_name is the name of the dimension (e.g., "Node")
                dimension_name = dimension_list[dimension_counter]

                # dimension_value is the value of the dimension (e.g., "CH00")
                dimension_value = mesh_element[dimension_counter]

                # price_subset is equal to part of the price_subset dataframe where at column price_hourly[dimension] the value of the row is equal to mesh_element[dimension]
                price_subset = price_subset.loc[price_subset.index.get_level_values(
                    dimension_name) == dimension_value]
                d_hourly_subset = d_hourly_subset.loc[d_hourly_subset.index.get_level_values(
                    dimension_name) == dimension_value]

            # calculate the weighted average price for the subset of dataframes for each scenario--------------
            for scenario in subcescen_list:
                key = tuple([dim for dim in mesh_element]+ [scenario])
                if agg_type == ["mean"]:
                    sum_cost[key], price_weighted_avg[key], sum_cost_hourly[key] = grouped_weighted_avg(price_subset[scenario], d_hourly_subset[scenario], dimension_list)
                else:
                    print("agg_type not recognized")
                    break
        
        # export the results to a csv file ---------------------------------------------------------------------
        # convert the dictionary to a dataframe
        price_weighted_avg_df = pd.DataFrame.from_dict(price_weighted_avg, orient="index")
        sum_cost_df = pd.DataFrame.from_dict(sum_cost, orient="index")
        sum_cost_hourly_df = pd.DataFrame.from_dict(sum_cost_hourly, orient="index")

        # dataframe manipulations to make the dataframe look nice before exporting ------------- 

        # rename the column
        price_weighted_avg_df.columns = ["price_weighted_avg"]
        sum_cost_df.columns = ["sum_price_multiplied_by_demand"]
        # get values of index in multiindex dataframe of price_subset, at index name hour
        sum_cost_hourly_df.columns = price_subset.index.get_level_values('hour')

        # reset the index
        price_weighted_avg_df = price_weighted_avg_df.reset_index()
        sum_cost_df = sum_cost_df.reset_index()
        sum_cost_hourly_df = sum_cost_hourly_df.reset_index()
        
        # rename the columns to name of dimensions + scenario name
        price_weighted_avg_df[dimension_list + ["scenario"]] = pd.DataFrame(price_weighted_avg_df['index'].tolist(), index=price_weighted_avg_df.index)
        sum_cost_df[dimension_list + ["scenario"]] = pd.DataFrame(sum_cost_df['index'].tolist(), index=sum_cost_df.index)
        sum_cost_hourly_df[dimension_list + ["scenario"]] = pd.DataFrame(sum_cost_hourly_df['index'].tolist(), index=sum_cost_hourly_df.index)
        
        # drop indices which are now columns
        price_weighted_avg_df.drop(columns=['index'], inplace=True)
        sum_cost_df.drop(columns=['index'], inplace=True)
        sum_cost_hourly_df.drop(columns=['index'], inplace=True)

        # put the scenario column at the end
        price_weighted_avg_df = price_weighted_avg_df[dimension_list + ["scenario"] + ["price_weighted_avg"]]
        sum_cost_df = sum_cost_df[dimension_list + ["scenario"] + ["sum_price_multiplied_by_demand"]]
        sum_cost_hourly_df = sum_cost_hourly_df[dimension_list + ["scenario"] + list(sum_cost_hourly_df.columns[:-2])]

        # export the results to a csv file
        price_weighted_avg_df.to_csv(output_dir + "price_weighted_avg.csv", index=False)
        sum_cost_df.to_csv(output_dir + "sum_cost_for_consumers.csv", index=False)
        sum_cost_hourly_df.to_csv(output_dir + "sum_cost_for_consumers_hourly.csv", index=False)

    return

def mappings_merge(scenarios_to_agg, original_results_dir):
    """
    This function merges all the Mapping csv files of the scenarios to aggregate, and saves the merged csv file in a csv file.
    These files are located in the original_results_dir/scenario folder. The files start with "Map_". The first column is the index. The rest of the columns are items mapped to the index. 
    The code goes through all the files with similar names in the scenarios in scenarios_to_agg, for each file, it creates a file with the same name in the "aggregation" folder and 
    this new file contains all the items in the original files. If an index has different values in corresponding files, it takes the union of the values and saves it in the new file in a new column.
    Input arguments:
        scenarios_to_agg: set of scenarios to aggregate
        original_results_dir: directory where the original results are located
    Output: csv file(s) with the aggregated results (follow to_csv method in the code to see the name of the csv file)
    """

    # find all files that start with "Map_" and are in the original_results_dir/scenario, where scenario is all keys in scenarios_to_agg
    # these files are the ones that need to be merged
    files_to_merge = []
    for scenario_name in scenarios_to_agg:
        files_to_merge.extend(
            [original_results_dir + scenario_name + "/" + file_name for file_name in os.listdir(original_results_dir + scenario_name) if file_name.startswith("Map_")])
        


    # create a dictionary where the keys are unique names of the files to merge (e.g., Map_node_consumer) and the values are the list of files to merge
    files_to_merge_dict = {}
    for file_to_merge in files_to_merge:
        file_name = file_to_merge.split("\\")[-1]
        file_name = file_name.split("/")[-1]
        files_to_merge_dict[file_name] = files_to_merge_dict.get(
            file_name, []) + [file_to_merge]

    # loop over the files to merge
    for file_name, file_path_list in files_to_merge_dict.items():
        # create an empty dataframe
        merged_df = pd.DataFrame()

        # loop over the files to merge
        for file_path in file_path_list:
            # read the file
            file_df = pd.read_csv(file_path, index_col=0)

        # Merge the indices from file_df with merged_df
            merged_df = merged_df.combine_first(file_df)    

        # withing each row of merged_df, sort values alphabetically (ignore column names)
        merged_df = merged_df.apply(lambda row: sorted(row, key=lambda x: str(x)), axis=1, result_type='expand')

        # if Map_node_plant, add a column with the plant type
        if file_name == "Map_node_plant.csv":
            # read the mapping of plants to technologies
            map_plant_tech_bt_manually_added = pd.read_csv("aggregation/Map_node_plant_bt_manually_added.csv", index_col=0)
            merged_df = pd.concat([merged_df, map_plant_tech_bt_manually_added], axis=1)
        elif file_name == "Map_plant_tech.csv":
            # read the mapping of plants to technologies
            map_plant_tech_bt_manually_added = pd.read_csv("aggregation/Map_plant_tech_bt_manually_added.csv", index_col=0)

            # name the column in map_plant_tech_bt_manually_added as column name of merged_df
            map_plant_tech_bt_manually_added.columns = merged_df.columns

            # add the manually added plants at the end of the merged_df, keep values in the same column as merged_df
            merged_df = pd.concat([merged_df, map_plant_tech_bt_manually_added], axis=0)

        elif file_name == "Map_consumertype_plant.csv":
            # read the mapping of plants to technologies
            map_plant_tech_bt_manually_added = pd.read_csv("aggregation/Map_consumertype_plant_bt_manually_added.csv", index_col=0)
            # add the manually added plants at the end of the merged_df, keep values in the same column as merged_df
            merged_df = pd.concat([merged_df, map_plant_tech_bt_manually_added], axis=1)


        # save the merged_df to a csv file
        merged_df.to_csv("aggregation/" + file_name)


def op_inv_exp_imp_cost_calc(scenarios_to_agg, output_dir, map_scen_subscen):
    """
    This function calculates the operational costs, investment costs, export gains for each scenario, and exports the results to a csv file.
    Input arguments:
        scenarios_to_agg: set of scenarios to aggregate
        output_dir: output directory to save the aggregated results	
    Output: csv file(s) with the aggregated results (follow to_csv method in the code to see the name of the csv file)
    """
    subcescen_list = [subscen for scen in map_scen_subscen.values() for subscen in scen] 
    timemap = pd.read_csv("input/timemaps_hydro_year.csv", index_col=0)
    # winter_defintion is the index values whose column "season" has "winter" as its value
    winter_defintion = timemap.loc[timemap["season"] == "winter"].index.to_list()

    # operational costs - CH ---------------------------------------------------------------------
    #plants_invested are plants listed in P_allinv.csv
    plants_invested = list()
    for scen in scenarios_to_agg:
        plants_invested_scen = pd.read_csv(f"output/{scen}/P_allinv.csv", index_col=0).index.to_list()
        plants_invested.extend(plants_invested_scen)
    # only keep unique values
    plants_invested = list(set(plants_invested))

    # read mapping of plants to nodes
    map_node_plant = pd.read_csv(
        "aggregation/Map_node_plant.csv", index_col=0)
    
    # read mapping of plants to techs
    map_plant_tech_dict = pd.read_csv(
        "aggregation/Map_plant_tech.csv", index_col=0).to_dict()["0"]
    
    # read the annual generations for each scenario
    annual_gen = pd.read_csv(
        output_dir + "gen_year_sum_temporal.csv", index_col=0).drop(columns=["year"])

    # read costs for each technology
    costs_op_perMWh = pd.read_csv(
        f"output/{scenarios_to_agg[0]}/operation_slp.csv", index_col=0) #NOTE: right now only one scenario is considered, costs could be different for different scenarios
    
    #NOTE: right now only one subscenario is considered, costs could be different for different subscenarios
    # in costs_op_perMWh, only keep the values for the first unique value in the column Scenarios and then remove the column Scenarios
    sub_scenarios_first_scen = costs_op_perMWh["Scenarios"].unique()
    costs_op_perMWh = costs_op_perMWh.loc[costs_op_perMWh["Scenarios"] == sub_scenarios_first_scen[0]].drop(columns=["Scenarios"])

    # calculate the operational costs for each scenario, multiply each element in costs_op with the corresponding element in annual_gen
    annual_op_costs_plants = pd.DataFrame(columns=subcescen_list)

    for plant in annual_gen.index:
        try:
            annual_op_costs_plants.loc[plant,:] = costs_op_perMWh.loc[plant, "value"] * annual_gen.loc[plant,:]
        except:
            print(f"{plant} not found in costs_op_perMWh, excluding from the sum operation costs")
    
    # for every node in map_node_plant, sum the operational costs of all plants in the node
    annual_op_costs_nodes = pd.DataFrame(columns=subcescen_list)
    for node in map_node_plant.index:
        plants_in_node = map_node_plant.loc[node, :]
        # sum only over plants that are in the intersection of plants_in_node and annual_op_costs_plants.index
        # practically only removing electrolyzers
        plants_in_node = list(set(plants_in_node) & set(annual_op_costs_plants.index))
  
        annual_op_costs_nodes.loc[node,:] = annual_op_costs_plants.loc[plants_in_node,:].sum()

    annual_op_costs_nodes.to_csv(output_dir + "annual_op_costs_nodes.csv")
    #HERE

    # investment costs - CH  ---------------------------------------------------------------------
    # NOTE: only on top of pre-existing PV and Wind

    # read the gen_max values
    gen_max = pd.read_csv(
        output_dir + "gen_max.csv", index_col=0)
    
    # read the investment costs for each technology
    costs_inv_perMW = pd.read_csv(
        f"output/{scenarios_to_agg[0]}/investment_genmax_slp.csv", index_col=0) #NOTE: right now only one scenario is considered, costs could be different for different scenarios
    
    sub_scenarios_first_scen = costs_inv_perMW["Scenarios"].unique()
    costs_inv_perMW = costs_inv_perMW.loc[costs_inv_perMW["Scenarios"] == sub_scenarios_first_scen[0]].drop(columns=["Scenarios"])

    # for every node in map_node_plant, sum the operational costs of all plants in the node
    annual_inv_costs_plants = pd.DataFrame(columns=subcescen_list)

    # find a list of plants in CH00 that are in techs_to_include
    # plants_in_ch = map_node_plant.loc["CH00", :]
    for plant in plants_invested:
        try:
            annual_inv_costs_plants.loc[plant,:] = costs_inv_perMW.loc[plant, "value"] * gen_max.loc[plant,:] # type: ignore
        except:
            print(f"{plant} not found in costs_inv_perMW, excluding from the sum investment costs")

    annual_inv_costs_plants.to_csv(output_dir + "annual_inv_costs_plants.csv")
    annual_inv_costs_plants.sum().to_csv(output_dir + "annual_inv_costs_CH.csv")

    #HERE

    # export gains - CH  ---------------------------------------------------------------------
    # read prices
    price_hourly = pd.read_csv(
        output_dir + "energy_balance_dual_hour_mean_temporal.csv")
    
    price_hourly = multiscen_adj.price_weighting_multi_scen(price_hourly, output_dir)

    # read export values
    export_values = pd.read_csv(
        output_dir + "Export.csv", index_col=0)
    
    # get import export mappings -------------
    # Map_node_exportinglineATC gives for each node the nodes it is exporting to (should be empty for CH00)
    Map_node_exportinglineATC = pd.read_csv(
        "aggregation/Map_node_exportinglineATC.csv", index_col=0, header=0
    ).T.to_dict("list")

    # removing nan values from the dictionary
    Map_node_exportinglineATC = {
        key: [x for x in value if str(x) != "nan"]
        for key, value in Map_node_exportinglineATC.items()
    }

    # Map_node_exportinglineATC gives for each node the nodes it is importing from
    #Map_node_importinglineATC["CH00"] = ['HVAC_AT00_CH00', 'HVAC_DE00_CH00', 'HVAC_FR00_CH00', 'HVAC_IT00_CH00'] 
    Map_node_importinglineATC = pd.read_csv(
        "aggregation/Map_node_importinglineATC.csv", index_col=0, header=0
    ).T.to_dict("list")

    # removing nan values from the dictionary
    Map_node_importinglineATC = {
        key: [x for x in value if str(x) != "nan"]
        for key, value in Map_node_importinglineATC.items()
    }

    t_steps_list = export_values["T"].unique()
    # create a multiindex dataframe to store the export net for each scenario, indexed by status, line and columns are the scenarios
    # Create a MultiIndex from the defined levels
    status = ["gain during export", "payment during export", "payment during import", "winter limit certificate gain"]
    lines = Map_node_importinglineATC["CH00"] + Map_node_exportinglineATC["CH00"]
    multi_index = pd.MultiIndex.from_product([status, lines], names=['Status', 'Line'])
    gain_loss_lines_ch = pd.DataFrame(index=multi_index, columns=subcescen_list)

    # create multiindex dataframes to store the export and import each scenario, indexed by line and T, and columns are the scenarios
    multi_index_expimp = pd.MultiIndex.from_product([lines, t_steps_list], names=['Line', 'T'])
    export_per_lines = pd.DataFrame(index=multi_index_expimp, columns=subcescen_list)
    import_per_lines = pd.DataFrame(index=multi_index_expimp, columns=subcescen_list)

    # export_sum and import_sum are the sum of the export and import values for each time step, indexed by T, and columns are the scenarios
    # they are not net export values
    export_sum = pd.DataFrame(index=t_steps_list, columns=subcescen_list)
    import_sum = pd.DataFrame(index=t_steps_list, columns=subcescen_list)

    # export_net is the net export value for each time step, indexed by T, and columns are the scenarios
    # negative values mean that CH00 is imoprting, positive values mean that CH00 is exporting
    export_net = pd.DataFrame(index=t_steps_list, columns=subcescen_list)


    for line in Map_node_importinglineATC["CH00"]:
        for scenario in subcescen_list:
            print("Calculating export net for node ", line)
            # select rows in export_values where T is equal to t_step and index is in Map_node_importinglineATC["CH00"]
            # sum the values in the "value" column
            df_subset_export = - export_values.loc[(export_values.index == line), ["T", scenario]].set_index("T")
            # for line HVAC_AT00_CH00, direction AT00 to CH00, a positive value means that CH00 is importing from AT00
            # negative sign is added to keep CH00 as the refrerence node

            # export_only is equal to df_subset_export, if the value is positive, else it is equal to 0
            price_ch = price_hourly.loc[(price_hourly.Node == "CH00"), ["hour", scenario]].set_index("hour")

            target_node = line.split("_")[1]

            price_other = price_hourly.loc[(price_hourly.Node == target_node), ["hour", scenario]].set_index("hour")

            # calculate export gain -------------------------------------
            # define a mask that is True in hours that CH00 is exporting to other node, that is when df_subset_export is positive
            mask_export = df_subset_export > 0

            # turn value in import hours to 0
            exports = df_subset_export.where(mask_export, 0)

            # store in export_lines
            export_per_lines.loc[(line, slice(None)), scenario] = exports.values

            # calculate price difference (it is negative, price_ch<price_other, when CH is exporting to other node (mask_export is True) 
            P_ch_minus_p_other = price_ch - price_other

            # when CH export is positive, CH gains the price difference to the other node
            export_gain_hourly = - P_ch_minus_p_other * exports
            
            # sum values in export_gain_hourly, only the positive values 
            gain_during_export_timeseries = export_gain_hourly[export_gain_hourly>0][scenario]/2 #NOTE: maybe adjust the sign
            # gain_during_export = export_gain_hourly[export_gain_hourly>0].sum()[scenario]
            payment_during_export_timeseries = - export_gain_hourly[export_gain_hourly<0][scenario]/2 #NOTE: maybe adjust the sign
            # payment_during_export = export_gain_hourly[export_gain_hourly<0].sum()[scenario]

            gain_loss_lines_ch.loc[("gain during export", line), scenario] = gain_during_export_timeseries.sum()
            gain_loss_lines_ch.loc[("gain during export - summer", line), scenario] = gain_during_export_timeseries.loc[~gain_during_export_timeseries.index.isin(winter_defintion)].sum()
            gain_loss_lines_ch.loc[("gain during export - winter", line), scenario] = gain_during_export_timeseries.loc[gain_during_export_timeseries.index.isin(winter_defintion)].sum()

            gain_loss_lines_ch.loc[("payment during export", line), scenario] = payment_during_export_timeseries.sum()
            gain_loss_lines_ch.loc[("payment during export - summer", line), scenario] = payment_during_export_timeseries.loc[~payment_during_export_timeseries.index.isin(winter_defintion)].sum()
            gain_loss_lines_ch.loc[("payment during export - winter", line), scenario] = payment_during_export_timeseries.loc[payment_during_export_timeseries.index.isin(winter_defintion)].sum()

            # calculate import gain -------------------------------------
            # define a mask that is True in hours that CH00 is importing from other node, that is when df_subset_export is negative
            mask_import = df_subset_export < 0

            # turn value in export hours to 0
            imports = df_subset_export.where(mask_import, 0)

            # store in import_lines
            import_per_lines.loc[(line, slice(None)), scenario] = - imports.values

            # # calculate price difference (it is positive, price_ch>price_other, when CH is importing from other node (mask_import is True)
            # P_ch_minus_p_other = price_ch - price_other

            # when CH import is negative, CH pays the price difference to the other node #NOTE: adjust the explianation
            import_cost_timeseries = P_ch_minus_p_other * imports/2 #NOTE: maybe adjust the sign

            # # sum values in import_cost_hourly
            # payment_during_import = (import_cost_hourly).sum().values[0]
            
            gain_loss_lines_ch.loc[("payment during import", line), scenario] = import_cost_timeseries.sum().values[0]
            gain_loss_lines_ch.loc[("payment during import - summer", line), scenario] = import_cost_timeseries.loc[~import_cost_timeseries.index.isin(winter_defintion)].sum().values[0]
            gain_loss_lines_ch.loc[("payment during import - winter", line), scenario] = import_cost_timeseries.loc[import_cost_timeseries.index.isin(winter_defintion)].sum().values[0]


    gain_loss_lines_ch.to_csv(output_dir + "export_gain_loss_lines_ch.csv")
    export_per_lines.to_csv(output_dir + "Export_CH_per_line.csv")
    import_per_lines.to_csv(output_dir + "Import_CH_per_line.csv")

    # sum the export values for each time step in export_per_lines for each scenario
    export_sum = export_per_lines.groupby(level=1).sum()
    import_sum = import_per_lines.groupby(level=1).sum()

    # reorder the rows in export_sum and import_sum to match t_steps_list
    export_sum = export_sum.reindex(t_steps_list)
    import_sum = import_sum.reindex(t_steps_list)

    export_sum.to_csv(output_dir + "Export_CH.csv")
    import_sum.to_csv(output_dir + "Import_CH.csv")

    # export_net
    export_net = export_sum - import_sum
    export_net.to_csv(output_dir + "Export_net_CH.csv")

    # for each column (scenario), sum all values with Status of gain and cost separately
    gain_loss_lines_ch_sum = pd.DataFrame(columns=subcescen_list)
    gain_loss_lines_ch_sum.loc["gain during export",:] = gain_loss_lines_ch.xs("gain during export", level='Status').sum()
    gain_loss_lines_ch_sum.loc["payment during export",:] = gain_loss_lines_ch.xs("payment during export", level='Status').sum()
    gain_loss_lines_ch_sum.loc["payment during import",:] = gain_loss_lines_ch.xs("payment during import", level='Status').sum()

    # read winter limit dual values -------------------------------------
    winter_limit_file = output_dir + "Constraint_winter_limit_dual.csv"
    # check if the file exists
    if os.path.isfile(winter_limit_file):
        winter_limit_dual = pd.read_csv(winter_limit_file, index_col=0)
    else:
        winter_limit_dual = pd.DataFrame()

    
    for scenario in subcescen_list:
        if scenario in winter_limit_dual.columns:
             dual_value = winter_limit_dual.loc[ "Constraint_winter_limit", scenario] * 5 * 1000 * 1000  #NOTE if 5 TWh limit changes, this should change # type: ignore
        else:
            dual_value = 0

        gain_loss_lines_ch_sum.loc["winter limit certificate gain", scenario] = dual_value
      
    gain_loss_lines_ch_sum.to_csv(output_dir + "export_gain_loss_lines_ch_sum.csv")
    #HERE
    
    # create a dataframe with the data to plot
    data_to_plot = pd.DataFrame(columns=subcescen_list)
    data_to_plot.loc["investment costs",:] = annual_inv_costs_plants.sum()
    data_to_plot.loc["operational costs",:] = annual_op_costs_nodes.loc["CH00",:]   
    data_to_plot.loc["gain during export",:] =  - gain_loss_lines_ch.xs("gain during export", level='Status').sum()
    data_to_plot.loc["payment during export",:] = - gain_loss_lines_ch.xs("payment during export", level='Status').sum()
    data_to_plot.loc["payment during import",:] = gain_loss_lines_ch.xs("payment during import", level='Status').sum()
    data_to_plot.loc["winter certificate gain",:] = gain_loss_lines_ch_sum.loc["winter limit certificate gain",:]

    data_to_plot.loc["total", :] = data_to_plot.sum()

    # winter - summer part
    data_to_plot.loc["gain during export - summer",:] = gain_loss_lines_ch.xs("gain during export - summer", level='Status').sum() 
    data_to_plot.loc["gain during export - winter",:] = gain_loss_lines_ch.xs("gain during export - winter", level='Status').sum() 

    data_to_plot.loc["payment during export - summer",:] = gain_loss_lines_ch.xs("payment during export - summer", level='Status').sum() 
    data_to_plot.loc["payment during export - winter",:] = gain_loss_lines_ch.xs("payment during export - winter", level='Status').sum() 

    data_to_plot.loc["payment during import - summer",:] = gain_loss_lines_ch.xs("payment during import - summer", level='Status').sum()
    data_to_plot.loc["payment during import - winter",:] = gain_loss_lines_ch.xs("payment during import - winter", level='Status').sum()


    data_to_plot.to_csv(output_dir + "op_inv_exp_imp_cost.csv")


def op_inv_exp_imp_cost_plot(scenarios_to_agg, map_scen_subscen, output_dir, file_name="op_inv_exp_imp_cost_plot"):
    """
    This function creates a bar chart of the investment costs, operational costs, export gains, and import costs, for CH00, for each scenario
    Input arguments:
        scenarios_to_agg: set of scenarios to aggregate
        output_dir: output directory to save the aggregated results
        file_name: name of the output file
        also relies on csv files created by op_inv_exp_imp_cost_calc
    Output: html file with the bar chart
    """
    subcescen_list = [subscen for scen in map_scen_subscen.values() for subscen in scen]

    data_to_plot = pd.read_csv(output_dir + "op_inv_exp_imp_cost.csv", index_col=0)
    sum_cost_consumers = pd.read_csv(output_dir + "sum_cost_for_consumers.csv", index_col=[0,1]).loc["CH00"].T # Price*Demand(flex+inflex)
    # merge sum_cost_consumers to data_to_plot
    data_to_plot = pd.concat([data_to_plot, sum_cost_consumers], axis=0)


    # create a bar chart of the investment costs, operational costs, export gains, and import costs, for CH00, for each scenario
    # on x-axis: scenario names
    # on y-axis: investment costs, operational costs, export gains, and import costs
    # stack the data in two groups: investment costs and operational costs and import costs versus export gains

    # read total model costs, from statistis.csv
    total_model_costs = pd.read_csv(output_dir + "statistics.csv", index_col=0).loc["Objective_Value", scenarios_to_agg].astype(float) # type: ignore

    # create a bar chart (gemini wrote the code after 10 tries)
    fig = go.Figure()

    # Positive (costs) Group (Stacking)
    positive_group = ["sum_price_multiplied_by_demand","investment costs"]
    for variable in positive_group:  # "investment costs", "operational costs", "payment during import", "payment during export", 
        fig.add_trace(go.Bar(x=subcescen_list,
                            y=data_to_plot.loc[variable,:], 
                            name=variable,
                            yaxis="y1"
                            )) # stackgroup removed 

    # Negative (gains) Grou
    negative_group = ["payment during import", "payment during export", "gain during export", "winter certificate gain"]
    for variable in negative_group:
        fig.add_trace(go.Bar(x=subcescen_list,
                            y=data_to_plot.loc[variable,:],
                            name=variable,
                            yaxis="y1"
                            )
                    )

    # add total costs (defined as positive_group + negative_group ), and connect the points with a line
    total_pos_neg = data_to_plot.loc[positive_group + negative_group, :].sum()
    fig.add_trace(go.Scatter(x=subcescen_list, 
                             y=total_pos_neg.values.astype(str), 
                             mode='lines+markers+text', 
                             name="Total CH costs",
                             yaxis="y1"
                             )
                )
    # Add text annotations for each point
    for i, txt in enumerate(total_pos_neg):
        value_to_plot = (txt) # type: ignore /total_pos_neg.iloc[1]
        # round the value to 2 decimal places
        value_to_plot = round(value_to_plot/1000/1000/1000, 1)
        fig.add_annotation(
            x=subcescen_list[i],
            y=total_pos_neg.iloc[i],
            text=str(value_to_plot), # 
            showarrow=True,
            arrowhead=0,
            ax=0,
            ay=-40
        )

    # add values in total_model_costs to the figure, in a separate y axis
    # values should be scaled to the first value
    total_model_costs_scaled = total_model_costs / total_model_costs.iloc[0]

    fig.add_trace(go.Scatter(x=subcescen_list, 
                             y=total_model_costs_scaled.values, 
                             mode='lines+markers+text', 
                             name="Total model costs (right y-axis)",
                             yaxis="y2",
                             )
                )

    fig.update_layout(
        yaxis2=dict(
            overlaying="y",
            side="right", 
            showgrid=False,  # Optional: Remove gridlines for cleaner look
            zeroline=False,   # Optional: Remove zero line
        )
    )

    fig.update_layout(barmode='relative')
    fig.update_layout(title_text="Annual costs for consumers - CH")
    fig.show()

    # save the figure
    fig.write_html(output_dir + file_name + ".html")

    # utilities costs and revenue ---------------------------------------------------
    
    # create a bar chart (gemini wrote the code after 10 tries)
    fig = go.Figure()

    # Positive (costs) Group (Stacking)
    positive_group = ["investment costs", "operational costs"]
    for variable in positive_group:  # "investment costs", "operational costs", "payment during import", "payment during export", 
        fig.add_trace(go.Bar(x=subcescen_list,
                            y=data_to_plot.loc[variable,:], 
                            name=variable,
                            yaxis="y1"
                            )) # stackgroup removed 

    # # Negative (gains) Grou
    # negative_group = ["payment during import", "payment during export", "gain during export", "winter certificate gain"]
    # for variable in negative_group:
    #     fig.add_trace(go.Bar(x=scenarios_to_agg,
    #                         y=data_to_plot.loc[variable,:],
    #                         name=variable,
    #                         yaxis="y1"
    #                         )
    #                 )

    # # add total costs (defined as positive_group + negative_group ), and connect the points with a line
    # total_pos_neg = data_to_plot.loc[positive_group + negative_group, :].sum()
    # fig.add_trace(go.Scatter(x=scenarios_to_agg, 
    #                          y=total_pos_neg.values.astype(str), 
    #                          mode='lines+markers+text', 
    #                          name="Total CH costs",
    #                          yaxis="y1"
    #                          )
    #             )
    # # Add text annotations for each point
    # for i, txt in enumerate(total_pos_neg):
    #     value_to_plot = (txt) # type: ignore /total_pos_neg.iloc[1]
    #     # round the value to 2 decimal places
    #     value_to_plot = round(value_to_plot/1000/1000/1000, 1)
    #     fig.add_annotation(
    #         x=scenarios_to_agg[i],
    #         y=total_pos_neg.iloc[i],
    #         text=str(value_to_plot), # 
    #         showarrow=True,
    #         arrowhead=0,
    #         ax=0,
    #         ay=-40
    #     )

    # # add values in total_model_costs to the figure, in a separate y axis
    # # values should be scaled to the first value
    # total_model_costs_scaled = total_model_costs / total_model_costs.iloc[0]

    # fig.add_trace(go.Scatter(x=scenarios_to_agg, 
    #                          y=total_model_costs_scaled.values, 
    #                          mode='lines+markers+text', 
    #                          name="Total model costs (right y-axis)",
    #                          yaxis="y2",
    #                          )
    #             )

    fig.update_layout(
        yaxis2=dict(
            overlaying="y",
            side="right", 
            showgrid=False,  # Optional: Remove gridlines for cleaner look
            zeroline=False,   # Optional: Remove zero line
        )
    )

    fig.update_layout(barmode='relative')
    fig.update_layout(title_text="Annual OPEX CAPEX - CH")
    fig.show()
    fig.write_html(output_dir + file_name + "OPEX_CAPEX.html")


def merge_gen_dem_ch(scenarios_to_agg, output_dir, map_scen_subscen):
    """
    This function merges the generation and demand for CH00, and saves the merged results in a csv file.
    """
    subcescen_list = [subscen for scen in map_scen_subscen.values() for subscen in scen]

    index = pd.MultiIndex.from_tuples([], names=('gen/con', 'tech/type'))
    annual_values_region = pd.DataFrame(index=index, columns=subcescen_list)


    seasonal_values_region = pd.DataFrame()
    timeseries_values_region = pd.DataFrame()
    # ## mappings:
    # hydro_dam_psp_open_ch = ["large_psp", "medium_reservior", "small_reservior", "CH00_dam"] 
    # psp_close_ch = ["CH00_psp_close", ] 
    # psp_all_ch = ["large_psp", "CH00_psp_close", ]

    # 
    Map_plant_tech = pd.read_csv("aggregation/Map_plant_tech.csv", index_col=0)
    Map_node_plant = pd.read_csv("aggregation/Map_node_plant.csv", index_col=0)

    # mergee annual generation and demand --------------------------------------------------------
    files_to_merge = [
        "gen_year_sum_temporal.csv", #
        "infeed_year_sum_temporal.csv", #
        "lostload_year_sum_temporal.csv", #
        "Import_CH_per_line.csv", #
        "Export_CH_per_line.csv", #
        "Export_net_CH.csv", #
        "demand_year_sum_Map_type_consumer.csv", 
        "storage_charge_year_sum_temporal.csv"

    ]
    import_export_timeseries = [
        "Import_CH_per_line.csv",
        "Export_CH_per_line.csv",
        "Export_net_CH.csv",
    ]


    # preparation for the merge ----------------------------------------------------------------------
    # read csvs ----------------------------
    gen_df = pd.read_csv(output_dir + "gen_year_sum_temporal.csv", index_col=0)
    infeed_df = pd.read_csv(output_dir + "infeed_year_sum_temporal.csv", index_col=0)

    # preparing list of techs to report ----
    techs_infeed_gen = list(set(list(infeed_df.Tech_infeed.unique()) + list(Map_plant_tech.iloc[:,0].unique())))
    tech_pv = [tech for tech in techs_infeed_gen  if "pv" in tech]
    tech_wind = [tech for tech in techs_infeed_gen if "wind" in tech]
    
    # tech_gen_report is equal to all values in Map_plant_tech that are not in tech_pv or tech_wind
    tech_gen_report = [tech for tech in Map_plant_tech.iloc[:,0].unique() if tech not in tech_pv + tech_wind]
    tech_infeed_report = [tech for tech in infeed_df.Tech_infeed.unique() if tech not in tech_pv + tech_wind]
    
    
    # read pv values (gen and infeed) --------------------------------------------------------
    #
    pv_invested = gen_df.loc[gen_df.index.isin(Map_plant_tech.loc[Map_plant_tech["0"].isin(tech_pv)].index)][subcescen_list].sum()

    # pv_infeed is equal to all values in infeed_df that have tech_infeed in tech_pv and index includes either CH0 or ID
    pv_infeed = infeed_df.loc[infeed_df['Tech_infeed'].isin(tech_pv) & (infeed_df.index.str.contains("CH0") | infeed_df.index.str.contains("ID"))][subcescen_list].sum()

    pv_total = pv_invested + pv_infeed

    annual_values_region.loc[("infeed", "pv_all"), :] = pv_total

    # read wind values (gen and infeed) --------------------------------------------------------
    wind_invested = gen_df.loc[gen_df.index.isin(Map_plant_tech.loc[Map_plant_tech["0"].isin(tech_wind)].index)][subcescen_list].sum()

    # wind_infeed is equal to all values in infeed_df that have tech_infeed in tech_wind and index includes either CH0 or ID
    wind_infeed = infeed_df.loc[infeed_df['Tech_infeed'].isin(tech_wind) & (infeed_df.index.str.contains("CH0") | infeed_df.index.str.contains("ID"))][subcescen_list].sum()

    wind_total = wind_invested + wind_infeed

    annual_values_region.loc[("infeed", "wind_all"), :] = wind_total

    # read infeed values (except pv and wind, i.e., ror)  ------------------
    # keep values for plants in CH00, that is if index includes CH0 or ID
    infeed_df = infeed_df.loc[infeed_df.index.str.contains("CH0") | infeed_df.index.str.contains("ID")]

    # sum values for ID and CH0 separately
    for tech in tech_infeed_report:
        # subselect the rows with index including either ID or CH0, and tech_infeed equal to tech
        infeed_tech_ch = infeed_df.loc[infeed_df['Tech_infeed'] == tech][subcescen_list].sum()
        
        if infeed_tech_ch.sum() != 0:
            annual_values_region.loc[("infeed", tech), :] = infeed_tech_ch


    # read gen values ---------------------------------------------------
    # keep values for plants in CH00
    gen_ch_df = gen_df.loc[gen_df.index.isin(Map_node_plant.loc["CH00", :])]

    # sum values for each tech in tech_gen_report
    for tech in tech_gen_report:
        value = gen_ch_df.loc[gen_ch_df.index.isin(Map_plant_tech.loc[Map_plant_tech["0"] == tech].index)][subcescen_list].sum()
        if sum(value) != 0:
            annual_values_region.loc[("gen", tech), :] = value

    # sum values for each prefix in ["bt", "v1g", "hp"]
    for prefix in ["bt", "v1g", "hp"]:
        value = gen_ch_df.loc[gen_ch_df.index.str.contains(prefix)][subcescen_list].sum()
        if sum(value) != 0:
            annual_values_region.loc[("gen", prefix), :] = value

    # read lostload values --------------------------------------------------------
    lostload_df = pd.read_csv(output_dir + "lostload_year_sum_temporal.csv", index_col=0)

    # keep values if index includes CH0 or ID
    lostload_ch0 = lostload_df.loc[lostload_df.index.str.contains("CH0")][subcescen_list].sum()
    lostload_ID = lostload_df.loc[lostload_df.index.str.contains("ID")][subcescen_list].sum()

    lostload_all = lostload_ch0 + lostload_ID

    annual_values_region.loc[("gen", "lostload"), :] = lostload_all

    # read imports --------------------------------------------------------
    export_df = pd.read_csv(output_dir + "Export_year_sum_temporal.csv", index_col=0) 

    # only keep values for CH0
    export_ch0 = export_df.loc[export_df.index.str.contains("CH0")][subcescen_list]

    for country in ["AT", "DE", "FR", "IT"]:
        # find the index that has the country in the name
        index_with_country = export_ch0.index[export_ch0.index.str.contains(country)][0]

        # check if country is before CH0 in the index, that is, if CH is exporting to the country
        if index_with_country.find(country) > index_with_country.find("CH0"):
            annual_values_region.loc[("gen", f"import_{country}"), :] = - export_ch0.loc[index_with_country]
        else:
            annual_values_region.loc[("gen", f"import_{country}"), :] = export_ch0.loc[index_with_country]

    # fixed demand --------------------------------------------------------
    demand_df = pd.read_csv(output_dir + "demand_year_sum_Map_type_consumer.csv", index_col=1)

    annual_values_region.loc[("demand", "fixed modelled household"), :] = demand_df.loc[demand_df.index.str.contains("ID")][subcescen_list].sum()
    annual_values_region.loc[("demand", "fixed modelled commercial"), :] = demand_df.loc[demand_df.index.str.contains("CH0")][subcescen_list].sum()

    # storage charge --------------------------------------------------------
    storage_charge_df = pd.read_csv(output_dir + "storage_charge_year_sum_temporal.csv", index_col=0)

    # keep values for plants in CH00
    storage_charge_ch_df = storage_charge_df.loc[storage_charge_df.index.isin(Map_node_plant.loc["CH00", :])]

    # sum values for each tech in tech_gen_report
    for tech in tech_gen_report: 
        value = storage_charge_ch_df.loc[storage_charge_ch_df.index.isin(Map_plant_tech.loc[Map_plant_tech["0"] == tech].index)][subcescen_list].sum()
        if sum(value) != 0:
            annual_values_region.loc[("demand", f"flex {tech}"), :] = value

    for prefix in ["bt", "v1g", "hp"]:
        value = storage_charge_ch_df.loc[storage_charge_ch_df.index.str.contains(prefix)][subcescen_list].sum()
        if sum(value) != 0:
            annual_values_region.loc[("demand", f"flex {prefix}"), :] = value

    # curtailment --------------------------------------------------------
    curtailment_df = pd.read_csv(output_dir + "curtailment_year_sum_temporal.csv", index_col=0)

    curtailment_ch0 = curtailment_df.loc[curtailment_df.index.str.contains("CH0")][subcescen_list].sum()
    curtailment_ID = curtailment_df.loc[curtailment_df.index.str.contains("ID")][subcescen_list].sum()

    curtailment_all = curtailment_ch0 + curtailment_ID

    annual_values_region.loc[("demand", "curtailment"), :] = curtailment_all

    # export to csv file --------------------------------------------------------
    annual_values_region.to_csv(output_dir + "Annual_balance_ch.csv")

    return


def merge_gen_dem_ch_hourly(scenarios_to_agg, output_dir, map_scen_subscen):
    """
    This function merges the generation and demand for CH00 on hourly basis, and saves the merged results in a csv file.
    """
    # 
    subcescen_list = [subscen for scen in map_scen_subscen.values() for subscen in scen]

    if subcescen_list:
        scenarios_to_agg = subcescen_list

    Map_plant_tech = pd.read_csv("aggregation/Map_plant_tech.csv", index_col=0)
    Map_node_plant = pd.read_csv("aggregation/Map_node_plant.csv", index_col=0)


    # preparation for the merge ----------------------------------------------------------------------
    # read csvs ----------------------------
    gen_df = pd.read_csv(output_dir + "gen_hour_sum_temporal.csv", index_col=[0,1])
    infeed_df = pd.read_csv(output_dir + "infeed_hour_sum_temporal.csv", index_col=[0,2])

    t_steps_list = gen_df.index.get_level_values(1).unique()

    index = pd.MultiIndex.from_tuples([], names=("scen_name", 'gen/con', 'tech/type'))
    hourly_values_region = pd.DataFrame(index=index, columns=t_steps_list)

    # preparing list of techs to report ----
    techs_infeed_gen = list(set(list(infeed_df.Tech_infeed.unique()) + list(Map_plant_tech.iloc[:,0].unique())))
    tech_pv = [tech for tech in techs_infeed_gen  if "pv" in tech]
    tech_wind = [tech for tech in techs_infeed_gen if "wind" in tech]
    
    # tech_gen_report is equal to all values in Map_plant_tech that are not in tech_pv or tech_wind
    tech_gen_report = [tech for tech in Map_plant_tech.iloc[:,0].unique() if tech not in tech_pv + tech_wind]
    tech_infeed_report = [tech for tech in infeed_df.Tech_infeed.unique() if tech not in tech_pv + tech_wind]
    
    
    # read pv values (gen and infeed) --------------------------------------------------------
    #
    # pv_invested is equal to subsection of gen_df if its first level index contains either elements of tech_pv
    pv_invested = gen_df[gen_df.index.get_level_values(0).str.contains("|".join(tech_pv))][scenarios_to_agg]

    # pv_invested is equal to all values in pv_invested that have tech_infeed in tech_wind and index includes either CH0 or ID
    pv_invested = pv_invested.groupby(level=1).sum()

    # reorder the index of pv_invested to match time_steps_list
    pv_invested = pv_invested.reindex(t_steps_list).fillna(0)



    # pv_infeed is equal to all values in infeed_df that have tech_infeed in tech_pv and index includes either CH0 or ID
    pv_infeed = infeed_df.loc[infeed_df['Tech_infeed'].isin(tech_pv) & (infeed_df.index.get_level_values(0).str.contains("CH0") | infeed_df.index.get_level_values(0).str.contains("ID"))][scenarios_to_agg]
    
    # create pv_infeed that sums over unique values of get_level_values(1)
    pv_infeed = pv_infeed.groupby(level=1).sum()

    # reorder the index of pv_infeed to match time_steps_list
    pv_infeed = pv_infeed.reindex(t_steps_list).fillna(0)

    pv_total = pv_invested + pv_infeed

    for scen in scenarios_to_agg:
        hourly_values_region.loc[(scen, "gen", "pv_all"), :] = pv_total[scen].values

    # read wind values (gen and infeed) --------------------------------------------------------
    wind_invested = gen_df.loc[gen_df.index.get_level_values(0).str.contains("|".join(tech_wind))][scenarios_to_agg]

    # create wind_invested that sums over unique values of get_level_values(1), which are the time steps
    wind_invested = wind_invested.groupby(level=1).sum()

    # reorder the index of wind_invested to match time_steps_list
    wind_invested = wind_invested.reindex(t_steps_list).fillna(0)


    # wind_infeed is equal to all values in infeed_df that have tech_infeed in tech_wind and index includes either CH0 or ID
    wind_infeed = infeed_df.loc[infeed_df['Tech_infeed'].isin(tech_wind) & infeed_df.index.get_level_values(0).str.contains("CH0")][scenarios_to_agg]

    # create pv_infeed that sums over unique values of get_level_values(1), which are the time steps
    wind_infeed = wind_infeed.groupby(level=1).sum()

    # reorder the index of wind_infeed to match time_steps_list
    wind_infeed = wind_infeed.reindex(t_steps_list).fillna(0)


    wind_total = wind_invested + wind_infeed

    for scen in scenarios_to_agg:
        hourly_values_region.loc[(scen, "gen", "wind_all"), :] = wind_total[scen].values

    # read infeed values (except pv and wind, i.e., ror)  ------------------
    # keep values for plants in CH00, that is if index includes CH0 or ID
    infeed_rest_df = infeed_df.loc[infeed_df.index.get_level_values(0).str.contains("CH0")]

    # sum values for ID and CH0 separately
    for tech in tech_infeed_report:
        # subselect the rows with index including either ID or CH0, and tech_infeed equal to tech
        infeed_tech_ch = infeed_rest_df.loc[infeed_rest_df['Tech_infeed'] == tech][scenarios_to_agg]
        for scen in scenarios_to_agg:
            hourly_values_region.loc[(scen, "gen", tech), :] = infeed_tech_ch[scen].values


    # read gen values ---------------------------------------------------
    # keep values for plants that have "CH0" or "ID" in the name
    gen_ch_df = gen_df.loc[gen_df.index.get_level_values(0).isin(Map_node_plant.loc["CH00", :])]
    # gen_df.index.isin(Map_node_plant.loc["CH00", :])]

    # sum values for each tech in tech_gen_report
    for tech in tech_gen_report:
        gen_tech = gen_ch_df[gen_ch_df.index.get_level_values(0).isin(Map_plant_tech.loc[Map_plant_tech["0"] == tech].index)][scenarios_to_agg]

        # create wind_infeed that sums over unique values of get_level_values(1), which are the time steps
        gen_tech = gen_tech.groupby(level=1).sum()

        # reorder the index of wind_infeed to match time_steps_list
        gen_tech = gen_tech.reindex(t_steps_list)

        # if value_tech is not empty
        if gen_tech.sum().sum() != 0:
            for scen in scenarios_to_agg:
                hourly_values_region.loc[(scen, "gen", tech), :] = gen_tech[scen].values


    # sum values for each prefix in ["bt", "v1g", "hp"]
    for tech in ["bt", "v1g", "hp"]:
        gen_tech = gen_ch_df.loc[gen_ch_df.index.get_level_values(0).str.contains(tech)][scenarios_to_agg]

        # create gen_tech that sums over unique values of get_level_values(1), which are the time steps
        gen_tech = gen_tech.groupby(level=1).sum()

        # reorder the index of gen_tech to match time_steps_list
        gen_tech = gen_tech.reindex(t_steps_list)
        
        # if gen_tech is not empty
        if gen_tech.sum().sum() != 0:
            for scen in scenarios_to_agg:
                hourly_values_region.loc[(scen, "gen", tech), :] = gen_tech[scen].values

    # read lostload values --------------------------------------------------------
    lostload_df = pd.read_csv(output_dir + "lostload_hour_sum_temporal.csv", index_col=[0,2])

    # keep values if index includes CH0 or ID
    lostload_ch0 = lostload_df.loc[lostload_df.index.get_level_values(0).str.contains("CH0")][scenarios_to_agg]

    # create lostload_ch0 that sums over unique values of get_level_values(1), which are the time steps
    lostload_ch0 = lostload_ch0.groupby(level=1).sum()

    # reorder the index of lostload_ch0 to match time_steps_list
    lostload_ch0 = lostload_ch0.reindex(t_steps_list)


    lostload_ID = lostload_df.loc[lostload_df.index.get_level_values(0).str.contains("ID")][scenarios_to_agg]

    # create lostload_ID that sums over unique values of get_level_values(1), which are the time steps
    lostload_ID = lostload_ID.groupby(level=1).sum()

    # reorder the index of lostload_ID to match time_steps_list
    lostload_ID = lostload_ID.reindex(t_steps_list).fillna(0)

    lostload_all = lostload_ch0 + lostload_ID

    for scen in scenarios_to_agg:
        hourly_values_region.loc[(scen, "gen", "lostload"), :] = lostload_all[scen].values

    # read imports --------------------------------------------------------
    export_df = pd.read_csv(output_dir + "Export_hour_sum_temporal.csv", index_col=[0,1]) 

    # only keep values for CH0
    export_ch0 = export_df.loc[export_df.index.get_level_values(0).str.contains("CH0")][scenarios_to_agg]

    
    for country in ["AT", "DE", "FR", "IT"]:
        # find the index that has the country in the name
        index_with_country = export_ch0.index[export_ch0.index.get_level_values(0).str.contains(country)][0][0]

        for scen in scenarios_to_agg:
            # check if country is before CH0 in the index, that is, if CH is exporting to the country
            if index_with_country.find(country) > index_with_country.find("CH0"):
                hourly_values_region.loc[(scen, "gen", f"import_{country}"), :] = - export_ch0.loc[index_with_country][scen].values
            else:
                hourly_values_region.loc[(scen, "gen", f"import_{country}"), :] = export_ch0.loc[index_with_country][scen].values

    # fixed demand --------------------------------------------------------
    demand_df = pd.read_csv(output_dir + "demand_hour_sum_Map_type_consumer.csv", index_col=[1,0])

    for scen in scenarios_to_agg:
        household_demand = demand_df.loc[demand_df.index.get_level_values(0).str.contains("ID")][scen].values
        if sum(household_demand) != 0:
            hourly_values_region.loc[(scen, "demand", "fixed modelled household"), :] = household_demand
        else:
            hourly_values_region.loc[(scen, "demand", "fixed modelled household"), :] = 0
        
        hourly_values_region.loc[(scen, "demand", "fixed modelled commercial"), :] = demand_df.loc[demand_df.index.get_level_values(0).str.contains("CH0")][scen].values

    # storage charge --------------------------------------------------------
    storage_charge_df = pd.read_csv(output_dir + "storage_charge_hour_sum_temporal.csv", index_col=[0,1])

    # in storage_charge_df, keep only rows that have any of elements ofMap_node_plant.loc["CH00", :] in the first level index
    storage_charge_ch_df = storage_charge_df.loc[storage_charge_df.index.get_level_values(0).isin(Map_node_plant.loc["CH00", :])]

    # sum values for each tech in tech_gen_report
    for tech in tech_gen_report: 
        # storage_charge_tech is equal to subsection of storage_charge_ch_df if its first level index contains Map_plant_tech.loc[Map_plant_tech["0"] == tech].index
        storage_charge_tech = storage_charge_ch_df[storage_charge_ch_df.index.get_level_values(0).isin(Map_plant_tech.loc[Map_plant_tech["0"] == tech].index)][scenarios_to_agg]

        # create storage_charge_tech that sums over unique values of get_level_values(1), which are the time steps
        storage_charge_tech = storage_charge_tech.groupby(level=1).sum()

        # reorder the index of storage_charge_tech to match time_steps_list
        storage_charge_tech = storage_charge_tech.reindex(t_steps_list)

        # if storage_charge_tech is not empty
        if storage_charge_tech.sum().sum() != 0:
            for scen in scenarios_to_agg:
                hourly_values_region.loc[(scen, "demand", f"flex {tech}"), :] = storage_charge_tech[scen].values

    for tech in ["bt", "v1g", "hp"]:
        # storage_charge_tech is equal to subsection of storage_charge_ch_df if its first level index contains tech
        storage_charge_tech = storage_charge_ch_df[storage_charge_ch_df.index.get_level_values(0).str.startswith(tech)][scenarios_to_agg]

        # create storage_charge_tech that sums over unique values of get_level_values(1), which are the time steps
        storage_charge_tech = storage_charge_tech.groupby(level=1).sum()

        # reorder the index of storage_charge_tech to match time_steps_list
        storage_charge_tech = storage_charge_tech.reindex(t_steps_list)

        # if storage_charge_tech is not empty
        if storage_charge_tech.sum().sum() != 0:
            for scen in scenarios_to_agg:
                hourly_values_region.loc[(scen, "demand", f"flex {tech}"), :] = storage_charge_tech[scen].values

    # curtailment --------------------------------------------------------
    curtailment_df = pd.read_csv(output_dir + "curtailment_hour_sum_temporal.csv", index_col=[0,1])

    curtailment_ch0 = curtailment_df.loc[curtailment_df.index.get_level_values(0).str.contains("CH0")][scenarios_to_agg]

    # create curtailment_ch0 that sums over unique values of get_level_values(1), which are the time steps
    curtailment_ch0 = curtailment_ch0.groupby(level=1).sum()

    # reorder the index of curtailment_ch0 to match time_steps_list
    curtailment_ch0 = curtailment_ch0.reindex(t_steps_list).fillna(0)



    curtailment_ID = curtailment_df.loc[curtailment_df.index.get_level_values(0).str.contains("ID")][scenarios_to_agg]

    # create curtailment_ID that sums over unique values of get_level_values(1), which are the time steps
    curtailment_ID = curtailment_ID.groupby(level=1).sum()

    # reorder the index of curtailment_ID to match time_steps_list
    curtailment_ID = curtailment_ID.reindex(t_steps_list).fillna(0)



    curtailment_all = curtailment_ch0 + curtailment_ID

    for scen in scenarios_to_agg:
        hourly_values_region.loc[(scen, "demand", "curtailment"), :] = curtailment_all[scen]


    # for every row of hourly_values_region add a column sum
    hourly_values_region["sum"] = hourly_values_region.sum(axis=1)
    # export to csv file --------------------------------------------------------
    hourly_values_region.to_csv(output_dir + "Annual_balance_ch_hourly.csv")

    return

def find_subscenarios(scenarios_list, stored_dir):
    """
    This function finds all subscenarios of a scenario
    Input arguments:
        scenarios: set of scenarios
        scenario_name: name of the scenario
    Output:
        subscenarios: dictionary mapping scenariso to their subscenarios
    """
    subscenarios = {}
    for scenario in scenarios_list:
        # read gen_max.csv, if there is a column Scenarios, find unique values in the column "Scenario" and store them as values to the dictionary
        # read gen_max.csv using pandas
        df = pd.read_csv(f"{stored_dir}/{scenario}/gen_max.csv")
        if "Scenarios" in df.columns:
            subscenarios[scenario] = list(df["Scenarios"].unique())
    return subscenarios