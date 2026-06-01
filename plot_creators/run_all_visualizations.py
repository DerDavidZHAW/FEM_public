"""
Orchestrator script that runs all visualization scripts with the scenario
constellations defined in instructions.csv.

Adjustable settings:
  - OUTPUT_FOLDER: the date-stamped subfolder under output/ (e.g. "20260311")

All plots are saved as PDF and HTML (plus markdown descriptions) in:
  output/{OUTPUT_FOLDER}/plots/
"""

import subprocess
import sys
from pathlib import Path

# ============================================================================
# SETTINGS — adjust these
# ============================================================================
OUTPUT_FOLDER = "20260311"
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
PLOTS_DIR = BASE_DIR / "output" / OUTPUT_FOLDER / "plots"
SCRIPTS_DIR = Path(__file__).parent

# Display names re-used across Block 1
BLOCK1_DISPLAY_NAMES = [
    "NTC 100%", "NTC 90%", "NTC 80%", "NTC 70%",
    "NTC 60%", "NTC 50%", "NTC 40%", "NTC 30%",
]

# Display names re-used across Block 2
BLOCK2_DISPLAY_NAMES = [
    "NTC 100%", "NTC 90%", "NTC 80%", "NTC 70%",
    "NTC 60%", "NTC 50%", "NTC 40%", "NTC 30%",
]

# Display names re-used across Block 3 (RH sensitivity)
BLOCK3_DISPLAY_NAMES = [
    "Unconstrained", "RH 1000 MW", "RH 500 MW", "RH 250 MW", "RH 0 MW",
]

# Display names re-used across Block 4 (summer price and heating demand)
BLOCK4_DISPLAY_NAMES = [
    "2050 NTC 100%", "2035 NTC 30%", "2035 NTC 100%", "2050 NTC 30%",
]

# Weather years for scripts that produce weather-year-specific outputs
WEATHER_YEARS = ["wy1995", "wy2008", "wy2009"]

# Weather year for Block 4 (easy to change)
BLOCK4_WEATHER_YEAR = "wy2008"

# ── Block 1 ──────────────────────────────────────────────────────────────────
# Scripts: violin_price_plot.py, summary_for_presentation_NTC_affects_storage_paper.py
# 10 groups, 8 scenarios each
BLOCK1_GROUPS = [
    {
        "name": "2035_inv_EUbat",
        "scenarios": [
            "2035_100_inv_EUbat", "2035_090_inv_EUbat", "2035_080_inv_EUbat",
            "2035_070_inv_EUbat", "2035_060_inv_EUbat", "2035_050_inv_EUbat",
            "2035_040_inv_EUbat", "2035_030_inv_EUbat",
        ],
    },
    {
        "name": "2050_inv_EUbat",
        "scenarios": [
            "2050_100_inv_EUbat", "2050_090_inv_EUbat", "2050_080_inv_EUbat",
            "2050_070_inv_EUbat", "2050_060_inv_EUbat", "2050_050_inv_EUbat",
            "2050_040_inv_EUbat", "2050_030_inv_EUbat",
        ],
    },
    {
        "name": "2035_xNTC100_EUbat",
        "scenarios": [
            "2035_100_inv_EUbat", "2035_090_100_EUbat", "2035_080_100_EUbat",
            "2035_070_100_EUbat", "2035_060_100_EUbat", "2035_050_100_EUbat",
            "2035_040_100_EUbat", "2035_030_100_EUbat",
        ],
    },
    {
        "name": "2050_xNTC100_EUbat",
        "scenarios": [
            "2050_100_inv_EUbat", "2050_090_100_EUbat", "2050_080_100_EUbat",
            "2050_070_100_EUbat", "2050_060_100_EUbat", "2050_050_100_EUbat",
            "2050_040_100_EUbat", "2050_030_100_EUbat",
        ],
    },
    {
        "name": "2035_xNTC070_EUbat",
        "scenarios": [
            "2035_100_070_EUbat", "2035_090_070_EUbat", "2035_080_070_EUbat",
            "2035_070_inv_EUbat", "2035_060_070_EUbat", "2035_050_070_EUbat",
            "2035_040_070_EUbat", "2035_030_070_EUbat",
        ],
    },
    {
        "name": "2050_xNTC070_EUbat",
        "scenarios": [
            "2050_100_070_EUbat", "2050_090_070_EUbat", "2050_080_070_EUbat",
            "2050_070_inv_EUbat", "2050_060_070_EUbat", "2050_050_070_EUbat",
            "2050_040_070_EUbat", "2050_030_070_EUbat",
        ],
    },
    {
        "name": "2035_xNTC030_EUbat",
        "scenarios": [
            "2035_100_030_EUbat", "2035_090_030_EUbat", "2035_080_030_EUbat",
            "2035_070_030_EUbat", "2035_060_030_EUbat", "2035_050_030_EUbat",
            "2035_040_030_EUbat", "2035_030_inv_EUbat",
        ],
    },
    {
        "name": "2050_xNTC030_EUbat",
        "scenarios": [
            "2050_100_030_EUbat", "2050_090_030_EUbat", "2050_080_030_EUbat",
            "2050_070_030_EUbat", "2050_060_030_EUbat", "2050_050_030_EUbat",
            "2050_040_030_EUbat", "2050_030_inv_EUbat",
        ],
    },
    {
        "name": "2035_inv_CHbat",
        "scenarios": [
            "2035_100_inv_CHbat", "2035_090_inv_CHbat", "2035_080_inv_CHbat",
            "2035_070_inv_CHbat", "2035_060_inv_CHbat", "2035_050_inv_CHbat",
            "2035_040_inv_CHbat", "2035_030_inv_CHbat",
        ],
    },
    {
        "name": "2050_inv_CHbat",
        "scenarios": [
            "2050_100_inv_CHbat", "2050_090_inv_CHbat", "2050_080_inv_CHbat",
            "2050_070_inv_CHbat", "2050_060_inv_CHbat", "2050_050_inv_CHbat",
            "2050_040_inv_CHbat", "2050_030_inv_CHbat",
        ],
    },
    # {
    #     "name": "2035_070_EUbat_rh",
    #     "scenarios": [
    #         "2035_070_inv_EUbat", "2035_070_inv_EUbat_rh_1000", "2035_070_inv_EUbat_rh_500",
    #         "2035_070_inv_EUbat_rh_250", "2035_070_inv_EUbat_rh_0", "2035_070_inv_EUbat_rh_0",
    #         "2035_070_inv_EUbat_rh_0", "2035_070_inv_EUbat_rh_0",
    #     ], 
    # },
]

# ── Block 2 ──────────────────────────────────────────────────────────────────
# Scripts: monthly_heat_sources.py (December & June)
# 2 groups, 8 scenarios each
BLOCK2_GROUPS = [
    {
        "name": "2035_inv_EUbat",
        "scenarios": [
            "2035_100_inv_EUbat", "2035_090_inv_EUbat", "2035_080_inv_EUbat",
            "2035_070_inv_EUbat", "2035_060_inv_EUbat", "2035_050_inv_EUbat",
            "2035_040_inv_EUbat", "2035_030_inv_EUbat",
        ],
    },
    {
        "name": "2050_inv_EUbat",
        "scenarios": [
            "2050_100_inv_EUbat", "2050_090_inv_EUbat", "2050_080_inv_EUbat",
            "2050_070_inv_EUbat", "2050_060_inv_EUbat", "2050_050_inv_EUbat",
            "2050_040_inv_EUbat", "2050_030_inv_EUbat",
        ],
    },
]

# ── Block 3 ──────────────────────────────────────────────────────────────────
# Scripts: rh_hp_comparison.py (RH sensitivity analysis)
# 6 groups, 4 scenarios each
BLOCK3_GROUPS = [
    {
        "name": "2035_NTC100_rh_sensitivity",
        "scenarios": [
            "2035_100_inv_EUbat",
            "2035_100_inv_EUbat_rh_1000", "2035_100_inv_EUbat_rh_500",
            "2035_100_inv_EUbat_rh_250", "2035_100_inv_EUbat_rh_0",
        ],
    },
    {
        "name": "2035_NTC070_rh_sensitivity",
        "scenarios": [
            "2035_070_inv_EUbat",
            "2035_070_inv_EUbat_rh_1000", "2035_070_inv_EUbat_rh_500",
            "2035_070_inv_EUbat_rh_250", "2035_070_inv_EUbat_rh_0",
        ],
    },
    {
        "name": "2035_NTC030_rh_sensitivity",
        "scenarios": [
            "2035_030_inv_EUbat",
            "2035_030_inv_EUbat_rh_1000", "2035_030_inv_EUbat_rh_500",
            "2035_030_inv_EUbat_rh_250", "2035_030_inv_EUbat_rh_0",
        ],
    },
    {
        "name": "2050_NTC100_rh_sensitivity",
        "scenarios": [
            "2050_100_inv_EUbat",
            "2050_100_inv_EUbat_rh_1000", "2050_100_inv_EUbat_rh_500",
            "2050_100_inv_EUbat_rh_250", "2050_100_inv_EUbat_rh_0",
        ],
    },
    {
        "name": "2050_NTC070_rh_sensitivity",
        "scenarios": [
            "2050_070_inv_EUbat",
            "2050_070_inv_EUbat_rh_1000", "2050_070_inv_EUbat_rh_500",
            "2050_070_inv_EUbat_rh_250", "2050_070_inv_EUbat_rh_0",
        ],
    },
    {
        "name": "2050_NTC030_rh_sensitivity",
        "scenarios": [
            "2050_030_inv_EUbat",
            "2050_030_inv_EUbat_rh_1000", "2050_030_inv_EUbat_rh_500",
            "2050_030_inv_EUbat_rh_250", "2050_030_inv_EUbat_rh_0",
        ],
    },
]

# ── Block 4 ──────────────────────────────────────────────────────────────────
# Script: summer_price_heat_demand_window.py
# 1 group, 4 scenarios
BLOCK4_GROUPS = [
    {
        "name": "summer_price_heat_window_core_scenarios",
        "scenarios": [
            "2050_100_inv_EUbat",
            "2035_030_inv_EUbat",
            "2035_100_inv_EUbat",
            "2050_030_inv_EUbat",
        ],
    },
]


def run_script(script_name, args_list, group_name):
    """Run a visualization script with the given arguments."""
    script_path = SCRIPTS_DIR / script_name
    cmd = [sys.executable, str(script_path)] + args_list
    print(f"    Running {script_name} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    ✗ FAILED: {script_name} for group {group_name}")
        if result.stdout:
            print(result.stdout[-500:])
        if result.stderr:
            print(result.stderr[-500:])
        return False
    if result.stdout:
        # Print last few lines of stdout
        lines = result.stdout.strip().split('\n')
        for line in lines[-5:]:
            print(f"      {line}")
    return True


def run_block1():
    """Block 1: violin_price_plot.py + summary_for_presentation_NTC_affects_storage_paper.py"""
    print("\n" + "=" * 80)
    print("BLOCK 1: Violin plots + Investment summaries")
    print("=" * 80)

    for group in BLOCK1_GROUPS:
        gname = group["name"]
        scenarios = group["scenarios"]
        display = BLOCK1_DISPLAY_NAMES

        print(f"\n  Group: {gname}")
        print(f"  Scenarios: {scenarios[0]} ... {scenarios[-1]}")

        # --- violin_price_plot.py ---
        # Run once per weather year so each HTML/PDF/PNG/MD gets its own file.
        for weather_year in WEATHER_YEARS:
            output_base = str(PLOTS_DIR / f"violin_{gname}_{weather_year}")
            run_script("violin_price_plot.py", [
                "--scenarios", *scenarios,
                "--display-names", *display,
                "--output-base", output_base,
                "--output-folder", OUTPUT_FOLDER,
                "--weather-year", weather_year,
            ], f"{gname} ({weather_year})")

        # --- summary_for_presentation_NTC_affects_storage_paper.py ---
        # This script expects scenarios in the format {folder}/{scenario}
        summary_scenarios = [f"{OUTPUT_FOLDER}/{s}" for s in scenarios]
        output_base = str(PLOTS_DIR / f"summary_{gname}")
        run_script("summary_for_presentation_NTC_affects_storage_paper.py", [
            "--scenarios", *summary_scenarios,
            "--display-names", *display,
            "--output-base", output_base,
        ], gname)


def run_block2():
    """Block 2: monthly_heat_sources.py (December & June)"""
    print("\n" + "=" * 80)
    print("BLOCK 2: Monthly heat sources (December & June)")
    print("=" * 80)

    for group in BLOCK2_GROUPS:
        gname = group["name"]
        scenarios = group["scenarios"]
        display = BLOCK2_DISPLAY_NAMES

        print(f"\n  Group: {gname}")
        print(f"  Scenarios: {scenarios[0]} ... {scenarios[-1]}")

        # --- monthly_heat_sources.py (December & June only) ---
        output_base = str(PLOTS_DIR / f"monthly_heat_{gname}")
        run_script("monthly_heat_sources.py", [
            "--scenarios", *scenarios,
            "--display-names", *display,
            "--output-base", output_base,
            "--output-folder", OUTPUT_FOLDER,
        ], gname)


def run_block3():
    """Block 3: rh_hp_comparison.py (RH sensitivity analysis)"""
    print("\n" + "=" * 80)
    print("BLOCK 3: RH/HP cost comparison (RH sensitivity)")
    print("=" * 80)

    for group in BLOCK3_GROUPS:
        gname = group["name"]
        scenarios = group["scenarios"]
        display = BLOCK3_DISPLAY_NAMES

        print(f"\n  Group: {gname}")
        print(f"  Scenarios: {scenarios[0]} ... {scenarios[-1]}")

        # --- rh_hp_comparison.py ---
        output_base = str(PLOTS_DIR / f"rh_hp_{gname}")
        run_script("rh_hp_comparison.py", [
            "--scenarios", *scenarios,
            "--display-names", *display,
            "--output-base", output_base,
            "--output-folder", OUTPUT_FOLDER,
        ], gname)


def run_block4():
    """Block 4: Summer price vs HP/resistive demand window"""
    print("\n" + "=" * 80)
    print("BLOCK 4: Summer electricity price and heating demand window")
    print("=" * 80)

    for group in BLOCK4_GROUPS:
        gname = group["name"]
        scenarios = group["scenarios"]
        display = BLOCK4_DISPLAY_NAMES

        print(f"\n  Group: {gname}")
        print(f"  Scenarios: {scenarios[0]} ... {scenarios[-1]}")
        print(f"  Weather year: {BLOCK4_WEATHER_YEAR}")

        output_base = str(PLOTS_DIR / f"summer_price_heat_window_{gname}")
        run_script("summer_price_heat_demand_window.py", [
            "--scenarios", *scenarios,
            "--display-names", *display,
            "--output-base", output_base,
            "--output-folder", OUTPUT_FOLDER,
            "--weather-year", BLOCK4_WEATHER_YEAR,
            "--start-month-day", "07-01",
            "--end-month-day", "07-14",
        ], gname)


def main():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output folder: {PLOTS_DIR}")

    run_block1()
    run_block2()
    run_block3()
    run_block4()

    print("\n" + "=" * 80)
    print("All visualizations completed.")
    print(f"Plots saved in: {PLOTS_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()
