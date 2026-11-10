"""
Script to combine detailed reporting CSV files from multiple scenarios.

This script looks for specific scenario subdirectories and combines their
Output_Spatial.csv, Output_Sys.csv, and Output_Temp.csv files into
aggregate CSV files.
"""

import os
from pathlib import Path

# ============================================================================
# CONFIGURATION - Set the directory containing the scenario subdirectories
# ============================================================================
BASE_DIR = Path("output/20260331_MIP3_v6")
# ============================================================================

# Define the scenarios in the specified order
SCENARIOS_2035 = [
    "2035_DE_NRT_NF",
    "2035_DE_NRT_WF",
    "2035_DE_WRT_NF",
    "2035_DE_WRT_WF",
    "2035_GA_NRT_NF",
    "2035_GA_NRT_WF",
    "2035_GA_WRT_NF",
    "2035_GA_WRT_WF",
]

SCENARIOS_2050 = [
    "2050_DE_NRT_NN_NF",
    "2050_DE_NRT_NN_WF",
    "2050_DE_NRT_WN_NF",
    "2050_DE_NRT_WN_WF",
    "2050_DE_WRT_NN_NF",
    "2050_DE_WRT_NN_WF",
    "2050_DE_WRT_WN_NF",
    "2050_DE_WRT_WN_WF",
    "2050_GA_NRT_NN_NF",
    "2050_GA_NRT_NN_WF",
    "2050_GA_NRT_WN_NF",
    "2050_GA_NRT_WN_WF",
    "2050_GA_WRT_NN_NF",
    "2050_GA_WRT_NN_WF",
    "2050_GA_WRT_WN_NF",
    "2050_GA_WRT_WN_WF",
]

CSV_FILES = ["Output_Spatial.csv", "Output_Sys.csv", "Output_Temp.csv"]


def get_folder_size_gb(folder_path: Path) -> float:
    """
    Calculate the total size of a folder in GB.
    
    Args:
        folder_path: Path to the folder
        
    Returns:
        Size in GB as a float
    """
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            try:
                total_size += os.path.getsize(file_path)
            except (OSError, FileNotFoundError):
                # Skip files that can't be accessed
                pass
    # Convert bytes to GB
    return total_size / (1024 ** 3)


def read_csv_content(file_path: Path) -> list[str]:
    """
    Read CSV file and return its content as a list of lines.
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        List of lines from the file
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.readlines()


def update_memory_requirements_row(lines: list[str], folder_size_gb: float) -> list[str]:
    """
    Update the Memory requirements row with the folder size.
    
    Args:
        lines: List of lines from Output_Sys.csv
        folder_size_gb: Size of the scenario folder in GB
        
    Returns:
        Updated list of lines
    """
    updated_lines = []
    for line in lines:
        if ",Memory requirements,GB," in line:
            # Remove trailing newline, add the size, then add newline back
            line = line.rstrip(',\n')
            line = f"{line},{folder_size_gb:.2f}\n"
        updated_lines.append(line)
    return updated_lines


def combine_csv_files(base_dir: Path):
    """
    Combine CSV files from all scenarios into aggregate files.
    
    Args:
        base_dir: Base directory containing scenario subdirectories
    """
    base_dir = Path(base_dir)
    
    if not base_dir.exists():
        print(f"Error: Directory '{base_dir}' does not exist.")
        return
    
    # Initialize containers for each CSV file type
    combined_data = {csv_file: [] for csv_file in CSV_FILES}
    
    # Process 2035 scenarios
    found_2035_scenarios = []
    for scenario in SCENARIOS_2035:
        scenario_path = base_dir / scenario
        if scenario_path.exists() and scenario_path.is_dir():
            found_2035_scenarios.append(scenario)
    
    # Process 2050 scenarios
    found_2050_scenarios = []
    for scenario in SCENARIOS_2050:
        scenario_path = base_dir / scenario
        if scenario_path.exists() and scenario_path.is_dir():
            found_2050_scenarios.append(scenario)
    
    print(f"Found {len(found_2035_scenarios)} 2035 scenarios: {found_2035_scenarios}")
    print(f"Found {len(found_2050_scenarios)} 2050 scenarios: {found_2050_scenarios}")
    
    # Process each CSV file type
    for csv_file in CSV_FILES:
        content_lines = []
        is_first_scenario = True
        
        # Combine all scenarios (2035 + 2050) in order
        all_scenarios = found_2035_scenarios + found_2050_scenarios
        
        for i, scenario in enumerate(all_scenarios):
            scenario_path = base_dir / scenario
            csv_path = scenario_path / "detailed_reporting" / csv_file
            
            if csv_path.exists():
                print(f"  Reading {csv_file} from {scenario}...")
                lines = read_csv_content(csv_path)
                
                # For Output_Sys.csv, add folder size to memory requirements row
                if csv_file == "Output_Sys.csv":
                    folder_size = get_folder_size_gb(scenario_path)
                    print(f"    Folder size: {folder_size:.2f} GB")
                    lines = update_memory_requirements_row(lines, folder_size)
                
                # Only include header row for the first scenario
                if is_first_scenario:
                    content_lines.extend(lines)
                    is_first_scenario = False
                else:
                    # Skip the header row (first line) for subsequent scenarios
                    content_lines.extend(['\n'] + lines[1:])
            else:
                print(f"  Warning: {csv_file} not found in {scenario}")
        
        # Write the combined file
        output_path = base_dir / csv_file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(content_lines)
        print(f"Created: {output_path}")
    
    print("\nDone! Combined CSV files have been created.")


# Run the script
combine_csv_files(BASE_DIR)
