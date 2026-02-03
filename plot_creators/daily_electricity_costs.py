"""
Script to calculate total electricity consumption costs per day for heat pumps and resistive heaters.
Uses the same scenarios as rh_hp_comparison.py.
"""

import pandas as pd
from pathlib import Path

year = "2050"  # Choose: "2035" or "2050"

# Define scenarios to compare (same as rh_hp_comparison.py)
scenarios = {
    f"{year}_aa": rf"C:\Models\Future_Markets\output\20260119\{year}_aa",
    f"{year}_aa_rh_1000": rf"C:\Models\Future_Markets\output\20260119\{year}_aa_rh_1000",
    f"{year}_aa_rh_500": rf"C:\Models\Future_Markets\output\20260119\{year}_aa_rh_500",
    f"{year}_aa_rh_250": rf"C:\Models\Future_Markets\output\20260119\{year}_aa_rh_250",
    f"{year}_aa_rh_0": rf"C:\Models\Future_Markets\output\20260119\{year}_aa_rh_0",
}

# Read time mapping (hour to day)
base_dir = Path(__file__).parent.parent
timemap_path = base_dir / "input" / "timemaps_hydro_year.csv"
timemap_df = pd.read_csv(timemap_path)

# Create mapping from t to day
t_to_day = dict(zip(timemap_df['t'], timemap_df['day']))

print(f"Loaded time mapping with {len(t_to_day)} hours")

# Read COP data from plants_DH_invest_candidates.csv
cop_data_path = base_dir / "input" / "plants_DH_invest_candidates.csv"
cop_df = pd.read_csv(cop_data_path)

# Create COP dictionary for heat pumps
cop_dict = {}
for _, row in cop_df.iterrows():
    if row['tech'] == 'heat_pump' and pd.notna(row['efficiency']):
        cop_dict[row['index']] = row['efficiency']

# Also read features file for HPG plants
features_path = base_dir / "input" / "plants_DH_CH_features.csv"
features_df = pd.read_csv(features_path)
for _, row in features_df.iterrows():
    if row['tech'] == 'heat_pump' and '_HPG' in row['index']:
        cop_dict[row['index']] = row['efficiency']

print(f"COP dictionary: {cop_dict}")

# Store all results
all_results = []

for scenario_name, scenario_path in scenarios.items():
    print(f"\nProcessing scenario: {scenario_name}")
    
    # Read thermal generation data
    genTh_path = f"{scenario_path}\\genTh.csv"
    genTh_df = pd.read_csv(genTh_path)
    
    # Read electricity prices
    price_path = f"{scenario_path}\\energy_balance_dual.csv"
    price_df = pd.read_csv(price_path)
    
    # Filter electricity prices for CH00 only
    price_ch00 = price_df[price_df['Node'] == 'CH00'][['T', 'Scenarios', 'value']].copy()
    price_ch00.rename(columns={'value': 'price_CHF_per_MWh'}, inplace=True)
    
    # Read scenario weights
    weights_path = f"{scenario_path}\\weight_in_objective_fcn.csv"
    weights_df = pd.read_csv(weights_path)
    weights_dict = dict(zip(weights_df['Scenarios'], weights_df['value']))
    
    print(f"  Scenario weights: {weights_dict}")
    
    # Merge genTh with electricity prices
    genTh_with_price = genTh_df.merge(price_ch00, on=['T', 'Scenarios'], how='left')
    
    # Add day mapping
    genTh_with_price['day'] = genTh_with_price['T'].map(t_to_day)
    
    # Calculate electricity costs for each row
    daily_costs = []
    
    for plant in genTh_with_price['PDH'].unique():
        plant_data = genTh_with_price[genTh_with_price['PDH'] == plant].copy()
        
        # Determine technology type
        is_hp = ('_HPNew' in plant or '_HPG' in plant)
        is_resistive = '_resistiveNew' in plant or 'resistive' in plant.lower()
        
        if is_hp:
            # Get COP for this plant
            cop = cop_dict.get(plant, 4.26)  # Default COP if not found
            # Electricity consumption = thermal generation / COP
            plant_data['elec_consumption_MWh'] = plant_data['value'] / cop
            plant_data['elec_cost_CHF'] = plant_data['elec_consumption_MWh'] * plant_data['price_CHF_per_MWh']
            plant_data['technology'] = 'HP'
            daily_costs.append(plant_data[['T', 'Scenarios', 'day', 'elec_cost_CHF', 'technology']])
        
        elif is_resistive:
            # Resistive heater: electricity consumption = thermal generation (COP ~1)
            plant_data['elec_consumption_MWh'] = plant_data['value']
            plant_data['elec_cost_CHF'] = plant_data['elec_consumption_MWh'] * plant_data['price_CHF_per_MWh']
            plant_data['technology'] = 'resistive'
            daily_costs.append(plant_data[['T', 'Scenarios', 'day', 'elec_cost_CHF', 'technology']])
    
    if daily_costs:
        # Combine all daily costs
        daily_costs_df = pd.concat(daily_costs, ignore_index=True)
        
        # Group by day, scenario, and technology
        daily_totals = daily_costs_df.groupby(['day', 'Scenarios', 'technology'])['elec_cost_CHF'].sum().reset_index()
        
        # Add scenario name
        daily_totals['scenario'] = scenario_name
        
        all_results.append(daily_totals)
        
        print(f"  Processed {len(daily_totals)} day/scenario/technology combinations")
    else:
        print(f"  No HP or resistive heater data found")

# Combine all results
if all_results:
    final_df = pd.concat(all_results, ignore_index=True)
    
    # Pivot to get a cleaner format: one row per day/subscenario, columns for each scenario+technology
    pivot_df = final_df.pivot_table(
        index=['day', 'Scenarios'],
        columns=['scenario', 'technology'],
        values='elec_cost_CHF',
        fill_value=0
    )
    
    # Flatten column names
    pivot_df.columns = [f'{scenario}_{tech}' for scenario, tech in pivot_df.columns]
    pivot_df = pivot_df.reset_index()
    
    # Add total columns for each scenario and reorder columns to match scenarios order
    ordered_cols = ['day', 'Scenarios']
    for scenario_name in scenarios.keys():
        hp_col = f'{scenario_name}_HP'
        res_col = f'{scenario_name}_resistive'
        total_col = f'{scenario_name}_total'
        
        # Ensure columns exist (fill with 0 if not)
        if hp_col not in pivot_df.columns:
            pivot_df[hp_col] = 0
        if res_col not in pivot_df.columns:
            pivot_df[res_col] = 0
        
        # Calculate total
        pivot_df[total_col] = pivot_df[hp_col] + pivot_df[res_col]
        
        ordered_cols.extend([hp_col, res_col, total_col])
    
    # Reorder columns
    pivot_df = pivot_df[ordered_cols]
    
    # Sort by day number (extract numeric part)
    pivot_df['day_num'] = pivot_df['day'].str.extract(r'day_(\d+)').astype(int)
    pivot_df = pivot_df.sort_values(['Scenarios', 'day_num']).drop(columns=['day_num'])
    
    # Save to CSV
    output_path = base_dir / "plot_creators" / f"daily_electricity_costs_{year}.csv"
    pivot_df.to_csv(output_path, index=False)
    
    print(f"\nResults saved to: {output_path}")
    print(f"  Total rows: {len(pivot_df)}")
    print(f"  Columns: {list(pivot_df.columns)}")
    
    # Also create a summary with total per day (summed across subscenarios with weights)
    # Re-process to apply weights
    summary_results = []
    
    for scenario_name, scenario_path in scenarios.items():
        # Read scenario weights
        weights_path = f"{scenario_path}\\weight_in_objective_fcn.csv"
        weights_df = pd.read_csv(weights_path)
        weights_dict = dict(zip(weights_df['Scenarios'], weights_df['value']))
        
        scenario_data = final_df[final_df['scenario'] == scenario_name].copy()
        scenario_data['weight'] = scenario_data['Scenarios'].map(weights_dict)
        scenario_data['weighted_cost'] = scenario_data['elec_cost_CHF'] * scenario_data['weight']
        
        # Group by day and technology, sum weighted costs
        weighted_totals = scenario_data.groupby(['day', 'technology'])['weighted_cost'].sum().reset_index()
        weighted_totals['scenario'] = scenario_name
        summary_results.append(weighted_totals)
    
    summary_df = pd.concat(summary_results, ignore_index=True)
    
    # Pivot for cleaner format
    summary_pivot = summary_df.pivot_table(
        index='day',
        columns=['scenario', 'technology'],
        values='weighted_cost',
        fill_value=0
    )
    summary_pivot.columns = [f'{scenario}_{tech}' for scenario, tech in summary_pivot.columns]
    summary_pivot = summary_pivot.reset_index()
    
    # Add total columns for each scenario and reorder columns to match scenarios order
    ordered_summary_cols = ['day']
    for scenario_name in scenarios.keys():
        hp_col = f'{scenario_name}_HP'
        res_col = f'{scenario_name}_resistive'
        total_col = f'{scenario_name}_total'
        
        # Ensure columns exist (fill with 0 if not)
        if hp_col not in summary_pivot.columns:
            summary_pivot[hp_col] = 0
        if res_col not in summary_pivot.columns:
            summary_pivot[res_col] = 0
        
        # Calculate total
        summary_pivot[total_col] = summary_pivot[hp_col] + summary_pivot[res_col]
        
        ordered_summary_cols.extend([hp_col, res_col, total_col])
    
    # Reorder columns
    summary_pivot = summary_pivot[ordered_summary_cols]
    
    # Sort by day number
    summary_pivot['day_num'] = summary_pivot['day'].str.extract(r'day_(\d+)').astype(int)
    summary_pivot = summary_pivot.sort_values('day_num').drop(columns=['day_num'])
    
    # Save summary
    summary_path = base_dir / "plot_creators" / f"daily_electricity_costs_{year}_weighted_summary.csv"
    summary_pivot.to_csv(summary_path, index=False)
    
    print(f"\nWeighted summary saved to: {summary_path}")
    print(f"  Total rows: {len(summary_pivot)}")
else:
    print("\nNo data found to process.")
