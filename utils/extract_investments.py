"""
Extract optimal investment results from completed model runs and produce
a model_variable_presets-compatible txt file so the same investments can
be imposed on runs with different NTC levels.

Folder naming convention:
    {year}_{ntc}_inv_{suffix}   e.g.  2035_100_inv_EUbat

The "inv" token means the model was free to invest.  The extracted
investments are then written out for every other NTC level as:
    {year}_{target_ntc}_{source_ntc}_{suffix}

Usage:
    python utils/extract_investments.py
"""

import os
import pandas as pd

# ---------- configuration ----------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DATE_DIR = os.path.join(BASE_DIR, "output", "20260311")

# Source scenario folders whose investments we want to extract
SOURCE_FOLDERS = [
    "2035_030_inv_EUbat",
    "2035_070_inv_EUbat",
    "2035_100_inv_EUbat",
    "2050_030_inv_EUbat",
    "2050_070_inv_EUbat",
    "2050_100_inv_EUbat",
]

# All NTC levels to generate target scenarios for
ALL_NTC_LEVELS = ["030", "040", "050", "060", "070", "080", "090", "100"]

# Reference plant lists (index column = plant identifier)
INVEST_CANDIDATES_RES = os.path.join(INPUT_DIR, "plants_invest_candidates_res_CH.csv")
INVEST_CANDIDATES_DH = os.path.join(INPUT_DIR, "plants_DH_invest_candidates.csv")

SPECIAL_BATTERY_TECHS = {
    "AT01_battery",
    "DE01_battery",
    "FR01_battery",
    "IT01_battery",
}

# ---------- helpers ----------


def parse_folder_name(folder_name):
    """Parse e.g. '2035_100_inv_EUbat' -> (year='2035', ntc='100', suffix='EUbat')."""
    parts = folder_name.split("_")
    # Expected: year_ntc_inv_suffix (possibly multi-word suffix)
    year = parts[0]
    ntc = parts[1]
    # parts[2] should be "inv"
    suffix = "_".join(parts[3:])
    return year, ntc, suffix


def build_scenario_name(year, target_ntc, source_ntc, suffix):
    """Build e.g. '2035_030_100_EUbat'."""
    return f"{year}_{target_ntc}_{source_ntc}_{suffix}"


def extract_plants(result_csv, plant_col, reference_plants, extra_allowed_plants=None):
    """
    Read a result CSV, keep only plants that appear in reference_plants and
    optionally in extra_allowed_plants, and return one row per unique plant with
    its value (deduplicated across subscenarios).
    """
    df = pd.read_csv(result_csv)

    allowed_plants = set(reference_plants)
    if extra_allowed_plants is not None:
        allowed_plants.update(extra_allowed_plants)

    # Keep only allowed investment plants
    df = df[df[plant_col].isin(allowed_plants)]
    # Values are the same across subscenarios – take the first occurrence per plant
    df = df.drop_duplicates(subset=[plant_col], keep="first")
    return df[[plant_col, "value"]]


def append_investment_lines(lines, variable_name, extracted_df, plant_col, year, source_ntc, suffix):
    """Append model_variable_presets lines for all target NTC levels."""
    for _, row in extracted_df.iterrows():
        plant = row[plant_col]
        value = row["value"]
        for target_ntc in ALL_NTC_LEVELS:
            if target_ntc == source_ntc:
                continue
            scen = build_scenario_name(year, target_ntc, source_ntc, suffix)
            lines.append(f"{variable_name},{scen},{plant},,{value}")


def main():
    # Load reference plant indices
    res_plants = set(pd.read_csv(INVEST_CANDIDATES_RES)["index"].tolist())
    dh_plants = set(pd.read_csv(INVEST_CANDIDATES_DH)["index"].tolist())

    all_lines = []

    for folder_name in SOURCE_FOLDERS:
        folder_path = os.path.join(OUTPUT_DATE_DIR, folder_name)
        if not os.path.isdir(folder_path):
            print(f"WARNING: folder not found, skipping: {folder_path}")
            continue

        year, source_ntc, suffix = parse_folder_name(folder_name)

        lines = []

        # --- gen_max.csv  (P_gen → plants_invest_candidates_res_CH) ---
        gen_max_path = os.path.join(folder_path, "gen_max.csv")
        if os.path.isfile(gen_max_path):
            gen_df = extract_plants(
                gen_max_path,
                "P_gen",
                res_plants,
                extra_allowed_plants=SPECIAL_BATTERY_TECHS,
            )
            append_investment_lines(lines, "gen_max", gen_df, "P_gen", year, source_ntc, suffix)
        else:
            print(f"WARNING: gen_max.csv not found in {folder_path}")

        # --- gen_energy_max.csv  (P_energymax → plants_invest_candidates_res_CH) ---
        gen_energy_max_path = os.path.join(folder_path, "gen_energy_max.csv")
        if os.path.isfile(gen_energy_max_path):
            gen_energy_df = extract_plants(
                gen_energy_max_path,
                "P_energymax",
                res_plants,
                extra_allowed_plants=SPECIAL_BATTERY_TECHS,
            )
            append_investment_lines(
                lines,
                "gen_energy_max",
                gen_energy_df,
                "P_energymax",
                year,
                source_ntc,
                suffix,
            )
        else:
            print(f"WARNING: gen_energy_max.csv not found in {folder_path}")

        # --- genTh_max.csv  (PDH → plants_DH_invest_candidates) ---
        gen_th_path = os.path.join(folder_path, "genTh_max.csv")
        if os.path.isfile(gen_th_path):
            th_df = extract_plants(gen_th_path, "PDH", dh_plants)
            append_investment_lines(lines, "genTh_max", th_df, "PDH", year, source_ntc, suffix)
        else:
            print(f"WARNING: genTh_max.csv not found in {folder_path}")

        # --- gen_energyTh_max.csv  (PDH_TES → plants_DH_invest_candidates) ---
        gen_energy_th_path = os.path.join(folder_path, "gen_energyTh_max.csv")
        if os.path.isfile(gen_energy_th_path):
            energy_th_df = extract_plants(gen_energy_th_path, "PDH_TES", dh_plants)
            append_investment_lines(
                lines,
                "gen_energyTh_max",
                energy_th_df,
                "PDH_TES",
                year,
                source_ntc,
                suffix,
            )
        else:
            print(f"WARNING: gen_energyTh_max.csv not found in {folder_path}")

        all_lines.extend(lines)
        print(f"Extracted {len(lines)} lines from {folder_name}")

    # --- write combined output ---
    out_path = os.path.join(BASE_DIR, "utils", "extracted_investments.txt")
    with open(out_path, "w", newline="\n") as f:
        f.write("variable,scen,plant,,value\n")
        for line in all_lines:
            f.write(line + "\n")

    print(f"Wrote {len(all_lines)} lines to {out_path}")


if __name__ == "__main__":
    main()
