"""
This script extracts the cost data from the input file 'cost_operation_invest_data.py' and restructures it into a CSV file.
It also adds additional information such as the plant technology category, fuel type, efficiency parameters, storage start condition, etc.
The output CSV file is saved as 'output/echnology_costs_reconstructed_from_model_inputs.csv'.

"""


import pandas as pd
from input.cost_operation_invest_data import cost_component, amortization_years_all
from structural_parameters import (
    Map_plant_tech_cost_component,
    Map_fuel_tech,
    Map_tech_fuel,
    Map_tech_startcondition,
    tech_store_list,
    tech_store_pump_list,
    tech_store_equal_pump_max_gen_max_list,
    tech_p_no_gen,
    tech_infeed_all_list,
    tech_hydro_list,
    tech_inflow_list,
    tech_outflow_list,
    tech_limited_energy_list,
    tech_limited_energy_CH_list,
    fuel_limited_CH_list,
    tech_limited_energy_and_require_storage_inv_no_soc,
    tech_demand_assets_shiftable,
    TES_techs_list,
    )

# Extract amortization years into a dataframe
amortization_df = pd.DataFrame.from_dict(amortization_years_all, orient='index', columns=['amortization_years'])

# Flatten cost_component dictionary
cost_data = []
for cost_type, technologies in cost_component.items():
    for tech, years in technologies.items():
        try:
            for year, value in years.items():
                cost_data.append([tech, cost_type, year, value])
        except AttributeError:
            cost_data.append([tech, cost_type, None, years])

# Convert to dataframe
cost_df = pd.DataFrame(cost_data, columns=['technology', 'cost_type', 'year', 'value'])

# Keep only relevant years (2035 and 2050) or empty years
cost_df = cost_df[cost_df['year'].isnull() | cost_df['year'].isin([2035, 2050])]

# Pivot table to have separate columns for each cost type
cost_df = cost_df.pivot(index=['technology', 'year'], columns='cost_type', values='value').reset_index()

# Merge with amortization years
final_df = cost_df.merge(amortization_df, left_on='technology', right_index=True, how='left')

# Convert technology-related dictionaries to DataFrames and merge them
def dict_to_dataframe(dictionary, column_name):
    """ Convert a dictionary into a DataFrame with 'technology' as index """
    return pd.DataFrame.from_dict(dictionary, orient='index', columns=[column_name]).reset_index().rename(columns={'index': 'technology'})

# Add plant technology category (cap_op / cap_op_energy)
final_df = final_df.merge(dict_to_dataframe(Map_plant_tech_cost_component, "plant_tech_category"), on="technology", how="left")

# Add fuel type mapping
final_df = final_df.merge(dict_to_dataframe(Map_tech_fuel, "fuel_type"), on="technology", how="left")

# Add storage start condition
final_df = final_df.merge(dict_to_dataframe(Map_tech_startcondition, "storage_start_condition"), on="technology", how="left")

# for every technology in final_df, go through the following lists,
    # tech_store_list,
    # tech_store_pump_list,
    # tech_store_equal_pump_max_gen_max_list,
    # tech_p_no_gen,
    # tech_infeed_all_list,
    # tech_hydro_list,
    # tech_inflow_list,
    # tech_outflow_list,
    # tech_limited_energy_list,
    # tech_limited_energy_CH_list,
    # fuel_limited_CH_list,
    # tech_limited_energy_and_require_storage_inv_no_soc,
    # tech_demand_assets_shiftable,
# for the technology in the list, add the corresponding tech_category to the final_df
final_df['tech_category'] = None


for tech in final_df['technology']:
    lists_that_tech_is_in = {}
    for list, list_name in [
        (tech_store_list, "storage"),
        (tech_store_pump_list, "storage_pump"),
        (tech_store_equal_pump_max_gen_max_list, "storage_equal_pump_max_gen_max"),
        (tech_p_no_gen, "p_no_gen"),
        (tech_infeed_all_list, "infeed_all"),
        (tech_hydro_list, "hydro"),
        (tech_inflow_list, "inflow"),
        (tech_outflow_list, "outflow"),
        (tech_limited_energy_list, "limited_energy"),
        (tech_limited_energy_CH_list, "limited_energy_CH"),
        (fuel_limited_CH_list, "fuel_limited_CH"),
        (tech_limited_energy_and_require_storage_inv_no_soc, "limited_energy_and_require_storage_inv_no_soc"),
        (tech_demand_assets_shiftable, "demand_assets_shiftable"),
        (TES_techs_list, "TES"),
    ]:
        if tech in list:
            # add the list_name to dictionary lists_that_tech_is_in
            lists_that_tech_is_in[list_name] = True
    # add lists_that_tech_is_in to the final_df, assign the values to the tech_category column
    final_df.loc[final_df['technology'] == tech, 'tech_category'] = ", ".join(lists_that_tech_is_in.keys())

# Save to CSV
final_df.to_csv('output/technology_costs_reconstructed_from_model_inputs.csv', index=False)

print("CSV file 'output/technology_costs_reconstructed_from_model_inputs.csv' has been generated successfully.")