"""
Read aggregated results from an aggregated results folder and merge them into a single aggregated results file.
If a scenario is seen in multiple multiple aggregated results folders, use the result mentioned first in the list of aggregated results folders.
Focus only on these three files:
- Annual_balance_ch.csv
- total_system_cost_summary.csv
- statistics.csv
"""


aggregated_folders = [
    "output/aggregated/robust_potentialLL_reruns_2/",
    "output/aggregated/robust_potentialLL_reruns/",
    "output/aggregated/cheap_robust_10_11_2025/",
    # "output/aggregated/Robust_sens/",
]

aggregate_new_name = "output/aggregated/merged_aggregated_results/"

# Files to merge
target_files = [
    "Annual_balance_ch.csv",
    "total_system_cost_summary.csv",
    "statistics.csv"
]

# --------------------------------------------------------------------------------
# Merge aggregated results from multiple folders
import os
import pandas as pd
from pathlib import Path

def get_scenarios_from_file(file_path, file_type):
    """Extract scenario names from a CSV file based on its type."""
    if not os.path.exists(file_path):
        return set()

    df = pd.read_csv(file_path)

    if file_type == "Annual_balance_ch.csv":
        # Scenarios are in the column headers (all columns except first two)
        return set(df.columns[2:])
    elif file_type == "total_system_cost_summary.csv":
        # Scenarios are in the main_scenario column
        return set(df['main_scenario'].unique())
    elif file_type == "statistics.csv":
        # Scenarios are in the column headers (all columns except first)
        return set(df.columns[1:])

    return set()


def merge_annual_balance(dfs_list):
    """Merge Annual_balance_ch.csv files, keeping first occurrence of each scenario."""
    if not dfs_list:
        return None

    # Start with the first dataframe's index columns
    base_cols = dfs_list[0][['gen/con', 'tech/type']].copy()

    # Track which scenarios we've already added
    added_scenarios = set()
    scenario_dfs = []

    # Iterate through each dataframe and collect scenarios
    for df in dfs_list:
        scenarios_in_this_df = [col for col in df.columns[2:] if col not in added_scenarios]

        if scenarios_in_this_df:
            scenario_dfs.append(df[scenarios_in_this_df])
            added_scenarios.update(scenarios_in_this_df)

    # Concatenate all at once for better performance
    if scenario_dfs:
        merged_df = pd.concat([base_cols] + scenario_dfs, axis=1)
    else:
        merged_df = base_cols

    return merged_df


def merge_total_cost_summary(dfs_list):
    """Merge total_system_cost_summary.csv files, keeping first occurrence of each scenario."""
    if not dfs_list:
        return None

    merged_rows = []
    added_scenarios = set()

    # Iterate through each dataframe
    for df in dfs_list:
        # Get scenarios in this dataframe that haven't been added yet
        for _, row in df.iterrows():
            scenario = row['main_scenario']
            if scenario not in added_scenarios:
                merged_rows.append(row)
                added_scenarios.add(scenario)

    if merged_rows:
        return pd.DataFrame(merged_rows).reset_index(drop=True)
    return None


def merge_statistics(dfs_list):
    """Merge statistics.csv files, keeping first occurrence of each scenario."""
    if not dfs_list:
        return None

    # Start with the first column (index/row labels)
    base_cols = dfs_list[0].iloc[:, [0]].copy()

    # Track which scenarios we've already added
    added_scenarios = set()
    scenario_dfs = []

    # Iterate through each dataframe and collect scenarios
    for df in dfs_list:
        scenarios_in_this_df = [col for col in df.columns[1:] if col not in added_scenarios]

        if scenarios_in_this_df:
            scenario_dfs.append(df[scenarios_in_this_df])
            added_scenarios.update(scenarios_in_this_df)

    # Concatenate all at once for better performance
    if scenario_dfs:
        merged_df = pd.concat([base_cols] + scenario_dfs, axis=1)
    else:
        merged_df = base_cols

    return merged_df


# Main merging logic
print("=" * 80)
print("Merging aggregated results from multiple folders")
print("=" * 80)

# Create output directory
output_dir = Path(aggregate_new_name)
output_dir.mkdir(parents=True, exist_ok=True)
print(f"\nOutput directory: {output_dir.absolute()}")

# Process each target file
for target_file in target_files:
    print(f"\n{'=' * 80}")
    print(f"Processing: {target_file}")
    print(f"{'=' * 80}")

    dfs_list = []
    folder_scenarios = {}

    # Read file from each folder
    for folder in aggregated_folders:
        file_path = Path(folder) / target_file

        if file_path.exists():
            print(f"\n[+] Found in: {folder}")
            try:
                df = pd.read_csv(file_path)
                dfs_list.append(df)

                # Get scenarios from this file
                scenarios = get_scenarios_from_file(file_path, target_file)
                folder_scenarios[folder] = scenarios
                print(f"  Scenarios found: {len(scenarios)}")

            except Exception as e:
                print(f"  [-] Error reading file: {e}")
        else:
            print(f"\n[-] Not found in: {folder}")

    # Merge the dataframes
    if dfs_list:
        print(f"\nMerging {len(dfs_list)} files...")

        # Show scenario overlap info
        print("\nScenario distribution:")
        all_scenarios = set()
        for folder, scenarios in folder_scenarios.items():
            all_scenarios.update(scenarios)
            print(f"  {folder}: {len(scenarios)} scenarios")

        print(f"\nTotal unique scenarios: {len(all_scenarios)}")

        # Merge based on file type
        merged_df = None
        if target_file == "Annual_balance_ch.csv":
            merged_df = merge_annual_balance(dfs_list)
        elif target_file == "total_system_cost_summary.csv":
            merged_df = merge_total_cost_summary(dfs_list)
        elif target_file == "statistics.csv":
            merged_df = merge_statistics(dfs_list)

        # Save merged file
        if merged_df is not None:
            output_file = output_dir / target_file
            merged_df.to_csv(output_file, index=False)
            print(f"\n[+] Saved merged file: {output_file}")
            print(f"  Shape: {merged_df.shape}")
        else:
            print(f"\n[-] Failed to merge {target_file}")
    else:
        print(f"\n[-] No files found to merge for {target_file}")

print(f"\n{'=' * 80}")
print("Merging complete!")
print(f"{'=' * 80}")
print(f"\nMerged files saved to: {output_dir.absolute()}")
