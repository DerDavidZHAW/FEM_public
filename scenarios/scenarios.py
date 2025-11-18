"""
This file contains the scenarios that are used in the analysis.
Scenarios can be defined manually or generated automatically from a csv file.

Eventually, scenarios are defined in a dictionary with the following structure:
scenarios_list = {
    "scenario_name_1": {
        "parameter_1": value_1,
        "parameter_2": value_2,
        ...
    },
    "scenario_name_2": {
        "parameter_1": value_1,
        "parameter_2": value_2,
        ...
    },
    ...
}
Settings, parameters, that are not defined in the scenarios_list are taken from the default_settings.py file.
"""
import pandas as pd
import re

## Define scenarios from csv file -----------------------------------------------------------------
# read the csv file
target_csv = "scenarios/scen_to_run_STORSUPPORT.csv"

# columns in the csv file are scenario names and rows are parameters
scenarios_data_df = pd.read_csv(target_csv, index_col=0)
# if there is a column including "Unnamed", drop it
scenarios_data_df = scenarios_data_df.loc[:, ~scenarios_data_df.columns.str.contains('Unnamed')]

meta_scenarios_list = {}
# finding scenario names (storing in scenarios_all_names)
if "sub_secn" in scenarios_data_df.index: # making sure the scenario is defined in the csv file based on sub-scenarios
    # find column names, if multiple columns had the same name (e.g., Scen, Scen.1), store only one name
    # the line below is replace with next few lines, because the order of scenarios is meant to be the same as the order of columns in the csv file 
    # meta_scenarios_all_names = list(set(re.sub(r'\.\d+$', '', col) for col in scenarios_data_df.columns))

    # Initialize a list to keep track of unique names while preserving order
    seen = set()
    meta_scenarios_all_names = []

    # Iterate through columns in order, remove the suffix, and keep track of seen names
    for col in scenarios_data_df.columns:
        clean_name = re.sub(r'\.\d+$', '', col)
        if clean_name not in seen:
            seen.add(clean_name)
            meta_scenarios_all_names.append(clean_name)

    # create a dictionary to store the sub-scenarios of each scenario
    for scenario_name in meta_scenarios_all_names:
        columns_of_this_scen = [scenario_name] + [col for col in scenarios_data_df.columns if col.startswith(scenario_name) and re.search(r'\.\d+$', col)]
        meta_scenarios_list[scenario_name] = [scenario_name + "_" + sub_scen for sub_scen in scenarios_data_df.loc["sub_secn", columns_of_this_scen]] # type: ignore

        for col in columns_of_this_scen:
            scenarios_data_df.loc["sub_secn_name", col] = scenario_name + "_" + scenarios_data_df.loc["sub_secn", col] # type: ignore

    # set the values in row "sub_secn" to be equal to column names
    scenarios_data_df.columns = scenarios_data_df.loc["sub_secn_name"] # type: ignore


scenarios_all_names = scenarios_data_df.columns.to_list()

# # keep only the scenarios that are based on the tariff, i.e. for index consumer_based_on_tariff = "True"
# coloumns_with_tariff = scenarios_data_df.loc["consumer_based_on_tariff"]== "True"
# scenarios_data_df = scenarios_data_df.loc[:, coloumns_with_tariff]

# # keep columns whose name starts with GAE
# coloumns_with_GAE = scenarios_data_df.columns.str.startswith("GAE")
# scenarios_data_df = scenarios_data_df.loc[:, coloumns_with_GAE]
# # columns consists of the list of scenarios
# scenarios_all_names = scenarios_data_df.columns.to_list()

# # reverse the order of the list scenarios_all_names
# scenarios_all_names = scenarios_all_names[0]

# scenarios_all_names = [
#     "NTC25_P0001_2",
# #     "DE_CY95_R45_N030_WNC",
#     # 'NTE_ZBA_W84_CCP_WNC_INA',
#     # 'NTE_ZBA_W84_CTB_WNC_INA',

#     # 'NTE_ZBA_W84_CCP_W05_INA',
#     # 'NTE_ZBA_W84_CTB_W05_INA',

#     # 'NTE_ZBA_W84_CCP_WNC_IAL',
#     # 'NTE_ZBA_W84_CTB_WNC_IAL',

#     # 'NTE_ZBA_W84_CCP_W05_IAL',
#     # 'NTE_ZBA_W84_CTB_W05_IAL',

#  ]

# # create scenarios_list dictionary
# scenarios_list = {}    

# # if a scenario includes multiple sub-scenarios, store them in the dictionary: scenarios_list[scenario_name]["sub_secn"] = [sub_scenario_1, sub_scenario_2, ...]

# # # if "sub_secn" is in index of scenarios_data_df (i.e, if the scenario includes multiple sub-scenarios)
# # if "sub_secn" in scenarios_data_df.index:


scenarios_list = {}
# store the parameters of the scenarios in the dictionary: scenarios_list[scenario_name][parameter_name] = value
for scenario_name in scenarios_all_names:
    scenarios_list[scenario_name] = {}
    for parameter_name in scenarios_data_df.index:
        value_str = str(scenarios_data_df.loc[parameter_name, scenario_name])

        # Try to evaluate value_str (as a dictionary, bolean, integer, or list), if it fails keep it as a string (e.g., for "gorubi" as solver_name)
        try:
            value = eval(value_str)
        except (SyntaxError, NameError):
            value = value_str

        # convert the value to the correct type, if the string can be deduced as a dictionary
        scenarios_list[scenario_name][parameter_name] = value
    
    # # Mannually overwrite a parameter
    # scenarios_list[scenario_name]["t_end"] = 6553 + 24
        # scenarios_list[scenario_name]["consumer_start"] = 299


print(f"Scenarios loaded from {target_csv} file.")