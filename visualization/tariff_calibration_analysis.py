import pandas as pd
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import glob
import time
import csv

# loop if multiple scenarios are analyzed ----------------------------------------------------------
# scenarios_to_aggregate = ["tariff_calibration\\RH_explore_tariff_calibration_1984_BY_DEVICE", ] #"tariff_calibration\\RH_explore_tariff_calibration_2007_BY_DEVICE"
# # target_dir = "tariff_calibration/RH_explore_tariff_calibration_BY_DEVICE"
# for target_dir in scenarios_to_aggregate:
#     print(f"\n\n{40*'='} \n ***agg and visualize scenario: {target_dir}*** \n{40*'='}")


# for analysis of single scenario ----------------------------------------------------------

# ---------------------------------------------------------------------------------------------------------
# SETTINGS to visualize OUTPUT VARIABLES ------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------


# STRICTLY REQUIRED inputs---------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------
# Switch: if True, the script is used for calibration analysis, if False, the script is used for final results of a scenario
calibration_analysis = True 

# list of folders where the output of the scenario is stored--------------
# if calibration_analysis is False: folders of several scenarios in output folder
scenario_name_list = [
    # "wy1984_T_wlimit_na",
    "wy1984_T_wlimit5tw",
]

if calibration_analysis: # NOTE: we need to loop over all scenarios in scenario_name_list
    consumer_output_dir = "tariff_calibration/" + scenario_name_list[0]  # for calibration analysis
else:
    consumer_output_dir = [f"output/{scen}" for scen in scenario_name_list]       # not for calibration analysis

# if calibration_analysis is True: folder of the one scenario in the tariff_calibration folder

# --------------------------------------
# Switch: if True, the results are stored in NEDELA style (in addition to default style), if False, the output is stored only in the default style
output_style_nedela = False 

# ---------------------------------------
agg_output_dir = ""
if calibration_analysis:
    # if calibration_analysis is True: this must be consumer_output_dir
    agg_output_dir = consumer_output_dir
else:
    # if calibration_analysis is False: can be any folder, potentially one in output/aggregated
    agg_output_dir = "output/aggregated/agg_nedela"  

# ---------------------------------------
# list of all possible IDs to aggregate from, 
# id_file_names_pattern_list =  ["ID299", ] 
id_file_names_pattern_list = [f"ID{i}" for i in range(1, 301)]  # not for calibration analysis
# id_file_names_pattern_list = ["ID270"]
# if saving csv files: CAUTION!, Aggregation only functionable for a small number of IDS, not the full 300 



# SETTINGS THAT MAY WORK FINE WIHT DEFAULT VALUES----------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------
# Switch: if True aggregated all data freshly from CSV files, if False use already aggregated data from parquet file (faster for plot adjustments and debugging)
agg_df_all_data_TF = True 

#  all variable that can be viszualized by ID
variable_file_names_pattern_list = [
    "storage_charge", 
    "infeed", 
    "gen", 
    "imported", 
    "exported",
    "demand",
    ] 
# not strictly required and therefore excluded: "curtailment", "lostload", "tariff_export", "tariff_import"  # cannot visualize: "pmp_max", "obj_value" "gen_max", "gen_energy_max"

# all variable that can be viszualized by TECH: ["demand", "infeed", "exported", "curtailment", "gen", "lostload", "storage_charge"]
agg_variable_file_names_pattern_list = [
    "storage_charge", 
    "infeed", 
    "gen", 
    "imported", 
    "exported",
    "demand",
    ] 

# Only applicable for tariff calibration scenarios -----
round = range(1,7)



# ---------------------------------------------------------------------------------------------------------
# CODE to aggregate output variables ----------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------

# if agg_output_dir does not exist, create it
if not os.path.exists(agg_output_dir): # type: ignore
    os.makedirs(agg_output_dir)  # type: ignore


# ----------------------
# AGG all ID  
# ----------------------
# add time mapping to change t_N to actual DateTime-------------------------------------------------------------------
# mapping_dict saves the time mapping for each scenario, 
    # keys are the name of scenario folders
    # values are dictionaries with keys "t_N" and values "DateTime"
if output_style_nedela:
    mapping_dict = {}

    for output_dir in consumer_output_dir: 

        mapping_dict[output_dir] = {}
        # Read the CSV file directly into the dictionary

        with open(f"{output_dir}//time_steps_mapping.csv", newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                mapping_dict[output_dir][row['0']] = row['']    

# Switch: if True aggregated all data freshly from CSV files, if False use already aggregated data from parquet file (faster for plot adjustments and debugging)
if agg_df_all_data_TF:  
    print(f'\n\naggregate specified variables, IDs and rounds \n{40*"-"}')

    # import output variables by variable (e.g. curtailment, demand), ID and round  -------------------------------------   
    df_agg_list = []

    variable_file_path_list = []

    # loop over all combinations of specified variables and store the paths to the CVS files in a list
    for v in variable_file_names_pattern_list: 
        print(f"*looking up > {v} ")
        if calibration_analysis:
            for r in round:
                print (f"look up > {v} | {r} ")
                for i in id_file_names_pattern_list:
                    dev_path = glob.glob(f"{consumer_output_dir}//*{i}_*{v}*_{r}.csv")
                    variable_file_path_list = variable_file_path_list + dev_path
        else:
            for scen in consumer_output_dir:
                # a list of all files that contain the variable name
                dev_path = glob.glob(f"{scen}//*{v}*.csv")

                # keep only the files that any consumer ID in id_file_names_pattern_list
                dev_path = [f for f in dev_path if any(id in f for id in id_file_names_pattern_list)]

                # remove the files that contain "max" in the name, because they are not needed for the analysis (gen_max, gen_energy_max, pmp_max, etc.)
                dev_path_no_max_in_name = [f for f in dev_path if "max" not in f]

                # add the files to the list of all files
                variable_file_path_list = variable_file_path_list + dev_path_no_max_in_name 
    
    # remove some variagles from variable_file_path_list because it does not have a time series
    excluded_variables = ["gen_energy_max", "gen_max", ]
    variable_file_path_list = [f for f in variable_file_path_list if not any(exc_var in f for exc_var in excluded_variables)]


    print(f'{40*"-"} \nfound all specified file paths*\n\n')   


    # import all files in lookup list and aggregate them into one dataframe
    df_agg = pd.DataFrame()

    ## for debugging, can be deleted
    # prev_variable_name = ""
    # f = variable_file_path_list[0]
    
    print(f'import all files in lookup list \n{40*"-"}')
    for n, f in enumerate(variable_file_path_list):   

        # to get the round number and variables with underscore properly (e.g. "storage_charge") are split into two parts, the variable name and the round number
        underscore_names = ["storage_charge", "tariff_export", "tariff_import"]
        found = any(u in f for u in underscore_names)
        if calibration_analysis:
            if found:
                variable_name = f'{f.split("_")[-3]}_{f.split("_")[-2]}'
            else:
                variable_name = f.split("_")[-2] # the other variable names are just copy pasted from the splitted string extraction

            round_number = f.split("_")[-1].split(".")[0]

        else:
            if found:
                variable_name = f'{f.split("_")[-2]}_{f.split("_")[-1].split(".")[0]}'
            else:
                variable_name = f.split("_")[-1].split(".")[0]
            round_number = f.split("/")[1].split("\\")[0]

        ## debugging
        # print statement to better understand the loop
        # if n == 0:
        #     prev_variable_name = variable_name
        # else: 
        #     if prev_variable_name != variable_name:
        #         # print(f'import > {variable_name} | round: {round_number} ')
        #         prev_variable_name = variable_name


        # look at the content of all csv files and identify "t" columns, "ID" columns (incl. "hp_ID290", "v1g_ID290", etc and the actual value)
        df_pd = pd.read_csv(f, index_col=None)
        for c in df_pd.columns:
            # select column with "t_" string values
            if df_pd[c].str.startswith("t_").all():
                t_column = df_pd[c]
                break

            # select ID (maybe with device tag, e.g. "vtg_ID1") for df_agg
            if any("ID" in value for value in  df_pd[c]):
                id_column = df_pd[c]
            
            # "lostload" does not feature a combined ID + tech columns so we need to create it (otherwise later problems with aggregation plotting)
            if "lostload" in f:
                if any("ID" in value for value in  df_pd[c]):
                    id_only_column = df_pd[c]
                tech_only_column = df_pd.iloc[:,1]

                id_column = [f"{id_only_column[i]}_{tech_only_column[i]}" for i in range(len(id_only_column))]

        # create the aggregated dataframe out of the selected columns in a uniform format, so that all fit in one dataframe
        t_series = t_column
        id_series = id_column
        value_series = df_pd.iloc[:,-1] # the values are alewas in the last column

        df_selected = pd.DataFrame({"t": t_series, "id": id_series, "value": value_series})
        df_selected['variable'] = variable_name
        df_selected['round'] = round_number
        df_selected['tech'] = "-"

        # get the technology for the variable to add to column "tech", not given for all variables which is why we need to get through if statemnet
        no_tech_in_variable = any(string in f for string in ["demand", "exported", "imported", "infeed"])
        tech_in_variable = any(string in f for string in ["soc", "storage_charge", "gen"])
        # if no_tech_in_variable:
        #     # print("")
        #     continue

        if tech_in_variable:
            tech_column = df_selected['id'].str.split("_").str[0]
            df_selected["tech"] = tech_column
        
        # store the aggregated dataframe in uniform format in a list to later be concatenated to one dataframe
        # print("timer: ", time.time() - start_time)
        # print(f"file name is {f}")

        # add time mapping to change t_N to actual DateTime-------------------------
        if output_style_nedela:
            # read time mapping from csv
            dir_time_maps = f[:f.rfind('\\') + 1]
            dir_time_maps = f"{dir_time_maps}"[0:-1]

            df_selected["t"] = df_selected['t'].map(mapping_dict[dir_time_maps])


        df_agg_list = df_agg_list + [df_selected]

        ## debugging
        # print('attached df_selected as LIST')
        # time_current = timer_print(time_current)

        # print statement to see the progress of the loop
        # print(f'imported {v} for IDs: {id_file_names_pattern_list} for rounds: {round} ')

        # if len(variable_file_path_list) < 100:
        #     if n%10 ==0:
        #         print(f'*imported {n} of {len(variable_file_path_list)} files')
        # elif len(variable_file_path_list) < 17000:
        #     if n%1000 ==0:
        #         print(f'*imported {n} of {len(variable_file_path_list)} files')

        if n % (len(variable_file_path_list)/20) == 0:
            print(f'*imported {n} of {len(variable_file_path_list)} files')
    
    print(f"starting concatenation of all dataframes in df_agg_list")
    df_agg_all_variables = pd.concat(df_agg_list)
    print(f"finished concatenation of all dataframes in df_agg_list")
    # df_agg_all_variables.to_csv(f"{target_dir[0]}/0_df_agg_all_variables_all_ID.csv")

    # export all ID aggregated data  ----------------------------------------------------------
    # export one file per variable (t vs scenario), and export---------
    df_agg_all_variables_tsteps_scen_tech = df_agg_all_variables.groupby(['t', 'tech', 'round', 'variable'], as_index=False)['value'].sum()
    order_of_t = df_selected['t'].unique()
    # pivot the dataframe, rounds as columns
    variable_list = df_agg_all_variables_tsteps_scen_tech['variable'].unique()
    print(f"export one file per variable (t vs scenario), and export")
    for variable in variable_list:
        print(f"export {variable}")
        df_agg_target_variable = df_agg_all_variables_tsteps_scen_tech.loc[df_agg_all_variables_tsteps_scen_tech['variable'] == variable]

        df_agg_all_variables_pivot = pd.pivot_table(df_agg_target_variable, values='value', index=['t'], columns='round', aggfunc='sum', fill_value=0)
        
        # df_agg_all_variables_pivot column t should follow order_of_t
        df_agg_all_variables_pivot = df_agg_all_variables_pivot.reindex(order_of_t)
        df_agg_all_variables_pivot.to_csv(f"{agg_output_dir}/variables_pivot_{variable}.csv")
    
    # if output_style_nedela, export the aggregated data in NEDELA style (in addition to default style)
        # one file per scenario, within which, one column per (consumer_name, consumption_type)       
    if output_style_nedela:
        print(f"export the aggregated data in NEDELA style")
        # export the aggregated data in NEDELA style
        for scenario in scenario_name_list:
            print(f"export NEDELA style for scenario: {scenario}")

            results_scenario = df_agg_all_variables.loc[df_agg_all_variables['round'] == scenario].copy()

            # if both "infeed" and "storage_charge" are not in data (results_scenario.vairable.unique()), skip the scenario
            if not all(elem in results_scenario.variable.unique() for elem in ["infeed", "storage_charge"]):
                print(f"skipping NEDELA style output, no infeed or storage_charge for {scenario}")
                continue


            # if column id has "_", split it and remove the first part, e.g. "hp_ID1" -> "ID1"
            results_scenario['id'] = results_scenario['id'].str.split("_").str[-1]

            # create list of consumers ----------------------------------------
            consumer_list = results_scenario['id'].unique()

            results_pivot = pd.pivot_table(results_scenario, values='value', index=['t'], columns=['variable', "tech", "id", "round"], aggfunc='sum', fill_value=0)
            #             
            # adjust values for bt (calculate net demand) and pv
            for consumer in consumer_list:

                # to calculate net demand of batteries, and save in "storage_charge"  net_demand = demand ("storage_charge") - gen
                try:
                    # results_pivot["storage_charge", "bt", consumer] = results_pivot["storage_charge", "bt", consumer] + results_pivot["gen", "bt", consumer]
                    results_pivot["storage_charge", "bt", consumer] = results_pivot["storage_charge", "bt", consumer] - results_pivot["gen", "bt", consumer]

                    # remove results_pivot_copy["gen", "bt", consumer] from results_pivot_copy
                    results_pivot.drop(columns=[("gen", "bt", consumer)], inplace=True)
                except KeyError:
                    # print(f"no battery for {consumer}")
                    pass

                # save the infeed as negative value in the "infeed" column
                results_pivot["infeed", "-", consumer] = - results_pivot["infeed", "-", consumer]
                infeed_sum = results_pivot[("infeed", "-", consumer)].sum().iloc[0]
                # if sum of values in "infeed" column is 0, remove the column
                if infeed_sum == 0:
                    results_pivot.drop(columns=[("infeed", "-", consumer)], inplace=True)
                    # print(f"no pv for {consumer}")

            # exporting and renaming --------------------------------------------------------
            # in results_pivot_copy, only keep the columns whose variable is in ["storage_charge", "infeed"]
            filtered_df = results_pivot.loc(axis=1)[['storage_charge', 'infeed', 'demand']]

            # for columns of variable "storag_charge", rename the column name to id + "_type201_" + tech
            # for columns of variable "infeed", rename the column name to id + "_type201_" + "pv"

            # Create a new DataFrame for storing copied and renamed columns
            output_df = pd.DataFrame()

            # Get the columns of variable "storage_charge", to iterate over them
            storage_charge_columns = filtered_df.columns[filtered_df.columns.get_level_values('variable') == 'storage_charge']

            # Create a list to store the concatenated columns
            concatenated_columns = []   

            # Reset index to remove MultiIndex (eases up data handling)
            filtered_df_copy = filtered_df.copy()
            df_reset = filtered_df_copy.reset_index()

            # Iterate over columns, copy and rename ----------------------------------
            # new_cols is defined based on pandas recommendation to avoid PerformanceWarning
            # first create a dictionary with the new column names and then concatenate the columns
            new_cols = {}

            for col in storage_charge_columns:
                if isinstance(col, tuple):
                    new_col_name = col[2] + "_type201_" + col[1]
                    new_cols[new_col_name] = df_reset[col]
                    # del output_df[col]
                # concatenated_columns.append(filtered_df_col_renamed)
                    
            infeed_columns = filtered_df_copy.columns[filtered_df_copy.columns.get_level_values('variable') == 'infeed']
            for col in infeed_columns:     
                new_col_name = col[2] + "_type201_pv"       

                # Rename the column
                new_cols[new_col_name] = df_reset[col]

            demand_columns = filtered_df_copy.columns[filtered_df_copy.columns.get_level_values('variable') == 'demand']
            for col in demand_columns:
                new_col_name = col[2] + "_type201_hh"       

                # Rename the column
                new_cols[new_col_name] = df_reset[col]
            
            # Concatenate all new columns at once
            output_df = pd.concat([output_df, pd.DataFrame(new_cols)], axis=1)    

            # if column name contains "ID", replace that part with hh
            output_df.columns = output_df.columns.str.replace("ID", "hh")

            # assign values of filtered_df.index as index to output_df
            output_df.index = filtered_df.index

            output_df.to_csv(f"{agg_output_dir}/nedela_{scenario}.csv")

    #NOTE: maybe Raul want to activate line below to save the csv and parquet files
    ## df_agg_all_variables.to_parquet(f"{agg_output_dir}/0_df_agg_all_variables_all_ID.parquet")
    ## df_agg_all_variables.to_csv(f"{agg_output_dir}/0_df_agg_all_variables_all_ID.csv")
    df_agg_all_variables_tsteps_scen_tech.to_csv(f"{agg_output_dir}/0_df_agg_all_variables_tsteps_scen_tech.csv")
    print(f'{40*"-"} \nimported all specified files*\n\n')                       
        

# ----------------------
# AGG by TECH  
# ----------------------

# agg_df_all_data_TF is replaced by False
if False:
    Map_subrate_time = pd.read_csv(f"{target_dir}/df_Map_subrate_time_end_1.csv")
    df_agg_all_variables["subrate_name"] = "-"

    # append aggregated variables to df_agg_all_variables, also specific to each round.
    # agg_variable_file_names_pattern_list_all

    variable_file_path_list = []
    df_agg_AGG_list = []
    for v in agg_variable_file_names_pattern_list:
        print(f'*looking up AGG > {v}')
        for r in round:
            dev_path = glob.glob(f"{target_dir}//{v}_{r}.csv")
            variable_file_path_list = variable_file_path_list + dev_path

    for f_agg in variable_file_path_list:
        df_pd = pd.read_csv(f_agg, index_col=None)

        # select id for the agg data frames
        if "demand" in f_agg:
            df_pd_sub = df_pd.loc[df_pd["Consumer"].str.contains("CH")]
            id_column = df_pd_sub["Consumer"]
        elif "Export" in f_agg:
            df_pd_sub = df_pd.loc[df_pd["lineATC"].str.contains("HVAC_CH")]
            id_column = df_pd_sub["lineATC"]
        elif "curtailment" in f_agg:
            df_pd_sub = df_pd.loc[df_pd["Consumer_with_infeed"].str.contains("CH")]
            id_column = df_pd_sub["Consumer_with_infeed"]
        elif "gen" in f_agg:
            df_pd_sub = df_pd.loc[df_pd["P_gen"].str.contains("CH")]
            id_column = df_pd_sub["P_gen"]
        elif "lostload" in f_agg:
            df_pd_sub = df_pd.loc[df_pd["Consumer"].str.contains("CH")]
            id_column = df_pd_sub["Consumer"]
        elif "storage_charge" in f_agg:
            df_pd_sub = df_pd.loc[df_pd["P_pumping"].str.contains("CH")]
            id_column = df_pd_sub["P_pumping"]


        for c in df_pd.columns:
        # select column with "t_" string values
            if df_pd_sub[c].str.startswith("t_").all():
                t_column = df_pd[c]
                break



        value_column = df_pd_sub['value']
        variable_column =  f_agg.split("//")[-1].split(".")[0][0:-2]
        round_column = f_agg.split("//")[-1].split(".")[0][-1]




        df_selected = pd.DataFrame({"t": t_column, 
                                    "id": id_column, 
                                    "value": value_column, 
                                    "variable": f'agg_{variable_column}',
                                    "round": round_column, 
                                    "tech": "-"})
        
        df_agg_AGG_list = df_agg_AGG_list + [df_selected]
    
    df_agg_AGG = pd.concat(df_agg_AGG_list)
    df_agg_all_variables = pd.concat([df_agg_all_variables, df_agg_AGG], ignore_index=True)
    # add subrate name to df_agg_all_variables
    for c in Map_subrate_time.columns:
        df_agg_all_variables.loc[df_agg_all_variables["t"].isin(Map_subrate_time[c]), "subrate_name"] = c

    # Pivot the DataFrame, rounds as columns
    df_agg_all_variables_pivot = pd.pivot_table(df_agg_all_variables, 
                                                values='value', 
                                                index=['variable', 'subrate_name'], 
                                                columns='round', 
                                                # aggfunc='sum', 
                                                fill_value=0)
    df_agg_all_variables_grouped = df_agg_all_variables.groupby(['variable', 'subrate_name', 'round'], as_index=False)['value'].sum()


    # df_agg_all_variables_grouped = df_agg_all_variables.groupby(['t', 'variable', 'tech', 'round'], as_index=False)['value'].sum()
    df_agg_all_variables_pivot.to_csv(f"{target_dir}/0_df_agg_all_variables_pivot.csv") 
    df_agg_all_variables_grouped.to_csv(f"{target_dir}/0_df_agg_all_variables_grouped.csv")

    # debugging
    df_agg_demand = df_agg_all_variables.loc[df_agg_all_variables["variable"] == "agg_demand"]
    df_agg_all_variables.loc[df_agg_all_variables["variable"] == "agg_demand"].to_csv(f"{target_dir}/0_df_agg_all_variables_agg_demand.csv")

    df_agg_demand




elif not agg_df_all_data_TF:
    print(f'use ALREADY AGGREGATED DATA from: \n>> {agg_output_dir}/0_df_agg_all_variables_all_ID.parquet')
    df_agg_all_variables = pd.read_parquet(f"{agg_output_dir}/0_df_agg_all_variables_all_ID.parquet")
    df_agg_all_variables_tsteps_scen_tech = pd.read_csv(f"{agg_output_dir}/0_df_agg_all_variables_tsteps_scen_tech.csv")


# ----------------------
# PLOTS  
# ----------------------
def reorder_df(df, order_dict):
    def get_order(row):
        return order_dict.get(row['t'], len(order_dict))  # Handle missing values

    df['order'] = df.apply(get_order, axis=1)  # Create temporary order column
    df = df.sort_values('order').drop('order', axis=1)  # Sort, then drop 'order' 
    return df
# visualize OUTPUT VARIABLES by INDIVIDUAL ----------------------------------------------------------
group_color_by_var_TF = False
if False:
    print("\n\n visualize OUTPUT VARIABLES by INDIVIDUAL \n")
    fig = go.Figure()
    t_order = [f"t_{i}" for i in range(6553, 8761)] + [f"t_{i}" for i in range(1, 6553)]
    legend_names = []
    group_color_ticker = 0
    gct_red, gct_blue, gct_green = 10, 10, 10

    # plote variable for SINGLE IDs and rounds
    for n, variable_name in enumerate(variable_file_names_pattern_list):
        print(f"plot: {variable_name}")
        unique_combinations = df_agg_all_variables[['id', 'variable', 'round']].drop_duplicates()
        gct_green += 30

        for index, row in unique_combinations.iterrows():
            id_value = row['id']
            variable_value = row['variable']
            round_value = row['round']
            group_color_ticker += 1
            gct_red += 1
            gct_blue += 7
            

            if variable_value == variable_name:  # Filter data for the current variable
                legend_name = f'{variable_value}_{id_value}_{round_value}'
                legend_names.append(legend_name)

                df_selected = df_agg_all_variables.loc[(df_agg_all_variables['id'] == id_value) & 
                                                    (df_agg_all_variables['variable'] == variable_value) & 
                                                    (df_agg_all_variables['round'] == round_value)]
                
                # additional sorting to prevent faulty vertical line from last to first time step in plot  
                # -- edit: commented out again, because it caused warnings of wrongly copy pasting values to df_selected
                # df_selected.loc[:,'t'] = pd.Categorical(df_selected['t'], categories=t_order, ordered=True)
                # df_selected.loc[:,'t'] = pd.Categorical(df_selected['t'], categories=t_order, ordered=True)
                # df_selected = df_selected.sort_values(by=['id', 'round','t'], ascending=[True, True, True])
                
                trace = go.Scatter(
                    x=df_selected['t'],
                    y=df_selected['value'],
                    legendgroup= variable_name, 
                    mode='lines',
                    name=legend_name,
                    line=dict(color=f'rgb({gct_red}, {gct_green}, {gct_blue})') if group_color_by_var_TF else None    

                )

                # Add the trace to the figure
                fig.add_trace(trace)

    # Create a layout for the plot
    layout = go.Layout(
        title='Values Over Time for Device, ID, Round Combinations',
        xaxis=dict(title='Time (t)', categoryorder='array', categoryarray=t_order),
        yaxis=dict(title='Value'),
        legend=dict(groupclick='toggleitem') ,  
    )

    # # Manually sort the legend items alphabetically
    # sorted_legend_names = sorted(legend_names)

    # # Update the names of the traces with the sorted legend names
    # for i, trace in enumerate(fig.data):
    #     trace.name = sorted_legend_names[i]

    # Set the layout for the entire figure
    fig.update_layout(layout)

    # Show the plot
    fig.show()
    fig.write_html(f"{target_dir}/df_agg_variables_BY_ID.html")
    print("\n end OUTPUT VARIABLES by INDIVIDUAL \n")


# visualize OUTPUT VARIABLES AGGREGATED by round ----------------------------------------------------------
if True:
    print("\n\n visualize OUTPUT VARIABLES in AGGREGATE \n")

    # import all tariff definitions to be able to plot them -------------------------------------
    # stored in df_tariff_dict, df_tariff_dict[scen]["kw"] is dataframe with tariff per kW, df_tariff_dict[scen]["kwh"] is dataframe with tariff per kWh
    df_tariff_dict = {}
    for scen in scenario_name_list:
        df_tariff_dict[scen] = {}
        if calibration_analysis:
            # find the file in f"output/{scen}" ending in "taiff_per_kW.csv"
            try:
                tariff_kw_file_path = glob.glob(f"output/{scen}//*tariff_per_kW.csv")
                tariff_kwh_file_path = glob.glob(f"output/{scen}//*tariff_per_kWh.csv")
                df_tariff_dict[scen]["kw"] = pd.read_csv(tariff_kw_file_path[0], index_col=0)
                df_tariff_dict[scen]["kwh"] = pd.read_csv(tariff_kwh_file_path[0], index_col=0)
            except:
                df_tariff_dict[scen]["kw"] = pd.DataFrame()
                df_tariff_dict[scen]["kwh"] = pd.DataFrame()
                print(f"no tariff file found for {scen}")
        else:
            # find the file in f"tariff_calibration/{scen}" ending in "taiff_per_kW.csv"
            try:
                # injection tariff for one consumer (first unique consumer)
                tariff_injection_kwh_file_path = glob.glob(f"tariff_calibration/{scen}//*current_injection_tariff_df_end_*.csv")
                tariff_all_consumers = pd.read_csv(tariff_injection_kwh_file_path[-1], index_col=0)
                injection_all_consumers = tariff_all_consumers.index.unique()
                injection_one_consumers = tariff_all_consumers.loc[tariff_all_consumers.index == injection_all_consumers[0], :].set_index("Time")
                injection_one_consumers.rename(columns={"Value": "injection.total"}, inplace=True)

                # withdrawal tariff for one consumer (first unique consumer)
                tariff_withdrawal_kwh_file_path = glob.glob(f"tariff_calibration/{scen}//*current_demand_tariff_df_end_*.csv")
                tariff_all_consumers = pd.read_csv(tariff_withdrawal_kwh_file_path[-1], index_col=0)
                withdrawal_all_consumers = tariff_all_consumers.index.unique()
                withdrawal_one_consumers = tariff_all_consumers.loc[tariff_all_consumers.index == withdrawal_all_consumers[0], :].set_index("Time")
                withdrawal_one_consumers.rename(columns={"Value": "withdrawal.total"}, inplace=True)

                # combine the two tariffs
                df_tariff_dict[scen]["kw"] = pd.DataFrame()
                df_tariff_dict[scen]["kwh"] = pd.concat([injection_one_consumers, withdrawal_one_consumers], axis=1)
                

            except:
                df_tariff_dict[scen]["kw"] = pd.DataFrame()
                df_tariff_dict[scen]["kwh"] = pd.DataFrame()
                print(f"no tariff file found for {scen}")


    # create the figure and subplots -------------------------------------------------------------    
    # fig = go.Figure()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True)

    t_order = [f"t_{i}" for i in range(6553, 8761)] + [f"t_{i}" for i in range(1, 6553)]
    order_dict = {val: i for i, val in enumerate(t_order)}


    # this is just for pretty colors and legends
    legend_names = []
    group_color_ticker = 0
    gct_red, gct_blue, gct_green = 230, 230, 230

    # plot variable for SINGLE IDs and rounds  ------------------------------
    for n, variable_name in enumerate(variable_file_names_pattern_list):
        print(f"plot: {variable_name}")

        df_grouped = df_agg_all_variables_tsteps_scen_tech.loc[df_agg_all_variables_tsteps_scen_tech['variable'] == variable_name].copy()

        # df_grouped = df_agg_all_variables[['t','variable', 'round', ]].drop_duplicates()
        # df_grouped = df_select.groupby(['t', 'variable', 'round'], as_index=False)['value'].sum()

        # re-order groupedby-dataframe by t_order, if df_grouped contains "t_" (vs DateTime)
        if not output_style_nedela:
            if "t_" in df_grouped['t'].iloc[0]:
                df_grouped = reorder_df(df_grouped.copy(), order_dict)

        unique_combinations = df_grouped[['variable', 'round']].drop_duplicates()
    
        # this is just for pretty colors and legends
        legend_label_counter = 0
        group_color_ticker += 1         
        if (group_color_ticker % 2) == 0:
            gct_red -= 40
        else:
            gct_green -= 10

        for index, row in unique_combinations.iterrows():
            round_value = row['round']

            legend_label_counter += 1
            gct_blue -= 10

            # filtered_data = df_grouped[(df_grouped['variable'] == variable_value) & (df_grouped['round'] == round_value)]
            filtered_data = df_grouped[(df_grouped['variable'] == variable_name) & (df_grouped['round'] == round_value)]
            
            # to plot storage_charge or gen time sereis per technology (e.g. "bt", "hp", "v1g")	
            items_to_plot = filtered_data['tech'].unique()

            for item in items_to_plot:
                data_to_plot = filtered_data.loc[filtered_data['tech'] == item]
                prefix = "" if item == "-"  else f"{item}_"
                trace = go.Scatter(
                    x=data_to_plot['t'],
                    y=data_to_plot['value'],
                    legendgroup= variable_name, 
                    legendgrouptitle=dict(text=f'group: {variable_name}') if legend_label_counter == 1 else None,
                    mode='lines',
                    name=f'{prefix}{round_value}',
                    line=dict(color=f'rgb({gct_red}, {gct_green}, {gct_blue})') if group_color_by_var_TF else None     
                    )
                fig.add_trace(trace, row=1, col=1)


    # plot tariff time series for each scenario -------------------------------------
    for scen in scenario_name_list:
        for kw_or_kwh in ["kwh", "kw"]:
            for inj_or_wit in ["injection", "withdrawal"]:
                if not df_tariff_dict[scen][kw_or_kwh].empty:
                    trace = go.Scatter(
                        x=df_tariff_dict[scen][kw_or_kwh].index,
                        y=df_tariff_dict[scen][kw_or_kwh][f"{inj_or_wit}.total"],
                        legendgroup= "tariffs",
                        legendgrouptitle=dict(text=f'group: tariffs'),
                        mode='lines',
                        name=f'{scen.split("_")[-1]}_{kw_or_kwh}_{inj_or_wit}',
                        line=dict(color=f'rgb({gct_red}, {gct_green}, {gct_blue})') if group_color_by_var_TF else None,
                        # row=2, 
                        # col=1       
                        )
                    fig.add_trace(trace, row=2, col=1)
                    # update the y-axis title to "CHF/KWh"

    layout = go.Layout(
        title=f'Aggregated generation/consumption values (top) and tariff of the last round (bottom)', # type: ignore
        xaxis=dict(title='Time (t)', categoryorder='array'),
        yaxis=dict(title='MWh'),
        legend=dict(groupclick='toggleitem') ,
    )

    layout['yaxis2'] = dict(title='Rp/KWh')

    fig.update_layout(layout)

    fig.show()
    fig.write_html(f"{agg_output_dir}/0_df_agg_variables_BY_ROUND.html")
    print("\n end OUTPUT VARIABLES in AGGREGATE \n")


print(f'\n\n{40*"-"} \n ***end*** \n{40*"-"}')






# -----------------------------------------------------------------------------------------------------------------------------------------------------
# TO BE DELETED ----------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------------------


# target_file_names_pattern_list = [
#     "constituents_newrate_end_",
#     "demand_all_consumer_t_df_end_",
#     "injection_all_consumer_t_df_end_",
#     "price_df_end_",
# ]


# def plot_summary_calibration():
#     """
#     Plot the summary of the calibration steps based on constituents_newrate_end_ files.
#     It plots tariff rates, balances etc. for each round.     

#     """
#     # for every element in first element of the df_agg index, select the part of the data
#     for index_target in df_agg.index.unique():
#         # find all values in df_agg that have index_target as index
#         df_plot = df_agg.loc[df_agg.index == index_target, :]
#         # set column as the index
#         df_plot['round'] = df_plot['round'].astype(int)
#         df_plot = df_plot.sort_values(by="round")
#         df_plot.index = df_plot["round"]

#         fig = go.Figure()
#         for column in df_plot.columns:
#             if column != "round":
#                 fig.add_trace(go.Bar(x=df_plot.index, y=df_plot[column], name=column))
#         fig.update_layout(
#             title=index_target,
#             xaxis_title="round",
#             # yaxis_title="CHF",
#             legend_title="Legend Title",
#             font=dict(family="Courier New, monospace", size=18, color="RebeccaPurple"),
#         )
#         fig.show()

# def extract_id_number(index):
#     """
#     Function to extract the numeric part from the index
#     """
#     return int(index[2:])

# def custom_sort(index):
#     """
#     Custom sorting function
#     """
#     id_num = extract_id_number(index)
#     if id_num <= 3:
#         return (0, id_num)
#     else:
#         return (1, id_num)

# def timer_print(time_start):
#     """
#     Function to print the time in a nice format
#     """
#     print(f'time: {(time.time() - time_start)} sec')
#     time_current = time.time()
#     return time_current



# # -----------------------------------------------------------------------------------------------------------------------------------------------------
# # visualize AGGREGATED constituents (rates, balance, demand, injection, price etc.) BY ROUND ----------------------------------------------------------
# # -----------------------------------------------------------------------------------------------------------------------------------------------------
# if False:
#     target_file_names_list = []

#     for target_file_names_pattern in target_file_names_pattern_list:
#         print(f"target_file_names_pattern: {target_file_names_pattern} {30*'-'}")
#         # find all the files that include the target_file_names_pattern
#         # and store them in a list
#         target_file_names_list = []
#         for file_name in os.listdir(target_dir):
#             if target_file_names_pattern in file_name:
#                 target_file_names_list.append(file_name)
#         first_round_number = target_file_names_list[0].split("_")[-1].split(".")[0]
#         # merge all the files in the list into one dataframe

#         # initialize the aggregate dataframe ----------------------------------------
#         df_agg = pd.DataFrame()
#         for file_name in target_file_names_list:
#             print("file_name: ", file_name)

#             # append the dataframe to the aggregate dataframe
#             if target_file_names_pattern == "constituents_newrate_end_":
#                 df_single = pd.read_csv(target_dir + "/" + file_name, index_col=0)

#                 # add the round counter to the dataframe
#                 df_single["round"] = file_name.split("_")[-1].split(".")[0]

#                 # aggregate the dataframes
#                 df_agg = pd.concat([df_agg, df_single])
#             else:
#                 # read the csv file and set the index to the first two columns
#                 df_single = pd.read_csv(target_dir + "/" + file_name, index_col=[0, 1])
#                 round_number = file_name.split("_")[-1].split(".")[0]

#                 # rename the column to round_number
#                 df_single = df_single.rename(columns={"Value": round_number})

#                 # aggregate the dataframes and name the column after the file name
#                 df_agg = pd.concat([df_agg, df_single], axis=1)

#                 # rearange columns so that 1,2,3 come first and 10,11,12 come later
#                 df_agg = df_agg[sorted(df_agg.columns, key=lambda x: int(x))]

#         # import tarif time maps (subrates) -----------------------------------------
#         df_tariff_time_map = pd.read_csv(f"tariff_calibration/temp_csv/df_Map_subrate_time_end_{first_round_number}.csv")
#         # plot the dataframe --------------------------------------------------------
#         print("Start plotting...")
#         if target_file_names_pattern == "constituents_newrate_end_":
#             plot_summary_calibration()
#         else:
#             for level in [0, 1]:
#                 # group the dataframe by the first index and order the rows
#                 df_agg_selected = df_agg.groupby(level=level).sum().sort_index()

#                 # sort in a way that ID1 is first, then ID2, then ID3, and ID10, ID11, ID12 come later
#                 sorted_indices = sorted(df_agg_selected.index, key=custom_sort)

#                 if level == 1:
#                     df_agg_selected = df_agg_selected.reindex(sorted_indices, level=level)

#                 # sort the dataframe by the sorted indices
#                 # df_agg_selected = df_agg_selected.loc[sorted_indices, :]


#                 # df_agg_selected = df_agg.groupby(level=level).sum().sort_index()

#                 # # sort in a way that ID1 is first, then ID2, then ID3, and ID10, ID11, ID12 come later
#                 # sorted_indices = sorted(df_agg_selected.index, key=custom_sort)

#                 # # sort the dataframe by the sorted indices
#                 # df_agg_selected = df_agg_selected.loc[sorted_indices, :]


#                 if level == 0:
                    

#                     # plot the dataframe by IDs
#                     fig = go.Figure()
#                     for column in df_agg_selected.columns:
#                         fig.add_trace(
#                             go.Bar(
#                                 x=df_agg_selected.index,
#                                 y=df_agg_selected[column],
#                                 name=column,
#                             )
#                         )
#                         fig.update_layout(
#                         title=target_file_names_pattern,
#                         xaxis_title=f"level {level}, by ID",
#                         # yaxis_title="CHF",
#                         # legend_title="Legend Title",
#                         font=dict(
#                             family="Courier New, monospace", size=18, color="RebeccaPurple"
#                         ),
#                     )
#                     fig.show()

#                 elif level == 1:


#                     # plot the dataframe as a line
#                     fig = go.Figure()
#                     for column in df_agg_selected.columns:
#                         fig.add_trace(
#                             go.Scatter(
#                                 x=df_agg_selected.index,
#                                 y=df_agg_selected[column],
#                                 name=column,
#                             )
#                         )
#                     fig.update_layout(
#                         title=target_file_names_pattern,
#                         xaxis_title=f"level {level}, by time steps",
#                         # yaxis_title="CHF",
#                         # legend_title="Legend Title",
#                         font=dict(
#                             family="Courier New, monospace", size=18, color="RebeccaPurple"
#                         ),
#                     )
#                     fig.show()
                    
                    
#                     # plot by subrate periods
#                     fig = go.Figure()                
#                     for round_number in df_agg_selected.columns:
#                         for subrate_periods in df_tariff_time_map.columns:
#                             # keep only the non-nan values of the dataframe df_tariff_time_map.loc[:,subrate_periods]
#                             time_steps = df_tariff_time_map.loc[:,subrate_periods].dropna()
                            
#                             fig.add_trace(
#                                 go.Bar(
#                                     x=[subrate_periods],
#                                     y=[df_agg_selected[round_number][time_steps].sum()],
#                                     name=round_number,
#                                 )
#                             )
#                         fig.update_layout(
#                         title=target_file_names_pattern,
#                         xaxis_title=f"level {level}, by subrate periods",
#                         # yaxis_title="CHF",
#                         # legend_title="Legend Title",
#                         font=dict(
#                             family="Courier New, monospace", size=18, color="RebeccaPurple"
#                         ),
#                     )
#                     fig.show()

#                     # for subrate_periods in df_tariff_time_map.columns:
#                     #     df_agg_selected[column][df_tariff_time_map.iloc[:,0]].sum()

#             # plot the dataframe by IDs with subrate periods backround
#             fig = go.Figure()

#             for i, first_index in enumerate(df_agg.index.get_level_values(0).unique()):
#                 subset_df = df_agg.loc[first_index]
#                 for round_number in subset_df.columns:
#                     fig.add_trace(
#                         go.Scatter(
#                             x=subset_df.index,
#                             y=subset_df[round_number],
#                             name=f'{first_index}, rnd: {round_number}', 
#                             # line=dict(color = i)
#                         ))
#                     fig.update_layout(
#                         title = target_file_names_pattern
#                     )
#             fig.show()
