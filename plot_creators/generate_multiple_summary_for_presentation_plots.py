"""
Helper script to run summary_for_presentation_NTC_affects_storage_paper.py 
with different configurations.

To enable/disable a configuration, set the corresponding variable to True/False.
"""

import subprocess
import sys
from pathlib import Path

# ============================================================================
# SETTINGS - MODIFY THESE
# ============================================================================

# Output folder (subfolder under output/)
OUTPUT_FOLDER = "20260119"

# Enable/disable configurations
first = False   # 1. Stochastic results 2035
second = False  # 2. Stochastic results 2050
third = True    # 3. Sensitivity analysis 2035
fourth = True   # 4. Sensitivity analysis 2050
fifth = True    # 5. Sensitivity analysis 2050 with battery investments
sixth = False    # 6. Limited RH investments in 2035
seventh = False  # 7. Limited RH investments in 2050
eighth = False  # 8. Sensitivity analysis 2050 between 40% and 30%
ninth = False   # 9. 2050 30% NTC with forced PV investments

# ============================================================================

# Define all configurations
CONFIGURATIONS = [
    {
        'name': '1. Stochastic results 2035',
        'active': first,
        'scenarios_to_summarize': [
            f'{OUTPUT_FOLDER}/2035_aa',
            f'{OUTPUT_FOLDER}/2035_ar',
            f'{OUTPUT_FOLDER}/2035_st',
        ],
        'scenarios_display_names': [
            'accepted',
            'rejected',
            'stochastic',
        ],
        'output_filename': 'results_2035.pdf',
    },
    {
        'name': '2. Stochastic results 2050',
        'active': second,
        'scenarios_to_summarize': [
            f'{OUTPUT_FOLDER}/2050_aa',
            f'{OUTPUT_FOLDER}/2050_ar',
            f'{OUTPUT_FOLDER}/2050_st',
        ],
        'scenarios_display_names': [
            'accepted',
            'rejected',
            'stochastic',
        ],
        'output_filename': 'results_2050.pdf',
    },
    {
        'name': '3. Sensitivity analysis 2035',
        'active': third,
        'scenarios_to_summarize': [
            f'{OUTPUT_FOLDER}/2035_sens_100',
            f'{OUTPUT_FOLDER}/2035_sens_90',
            f'{OUTPUT_FOLDER}/2035_sens_80',
            f'{OUTPUT_FOLDER}/2035_sens_70',
            f'{OUTPUT_FOLDER}/2035_sens_60',
            f'{OUTPUT_FOLDER}/2035_sens_50',
            f'{OUTPUT_FOLDER}/2035_sens_40',
            f'{OUTPUT_FOLDER}/2035_sens_30',
        ],
        'scenarios_display_names': [
            'NTC 100%',
            'NTC 90%',
            'NTC 80%',
            'NTC 70%',
            'NTC 60%',
            'NTC 50%',
            'NTC 40%',
            'NTC 30%',
        ],
        'output_filename': 'Sensitivity_Analysis_in_2035.pdf',
    },
    {
        'name': '4. Sensitivity analysis 2050',
        'active': fourth,
        'scenarios_to_summarize': [
            f'{OUTPUT_FOLDER}/2050_sens_100',
            f'{OUTPUT_FOLDER}/2050_sens_90',
            f'{OUTPUT_FOLDER}/2050_sens_80',
            f'{OUTPUT_FOLDER}/2050_sens_70',
            f'{OUTPUT_FOLDER}/2050_sens_60',
            f'{OUTPUT_FOLDER}/2050_sens_50',
            f'{OUTPUT_FOLDER}/2050_sens_40',
            f'{OUTPUT_FOLDER}/2050_sens_30',
        ],
        'scenarios_display_names': [
            'NTC 100%',
            'NTC 90%',
            'NTC 80%',
            'NTC 70%',
            'NTC 60%',
            'NTC 50%',
            'NTC 40%',
            'NTC 30%',
        ],
        'output_filename': 'Sensitivity_Analysis_in_2050.pdf',
    },
    {
        'name': '5. Sensitivity analysis 2050 with battery investments',
        'active': fifth,
        'scenarios_to_summarize': [
            f'{OUTPUT_FOLDER}/2050_sens_100_bat',
            f'{OUTPUT_FOLDER}/2050_sens_90_bat',
            f'{OUTPUT_FOLDER}/2050_sens_80_bat',
            f'{OUTPUT_FOLDER}/2050_sens_70_bat',
            f'{OUTPUT_FOLDER}/2050_sens_60_bat',
            f'{OUTPUT_FOLDER}/2050_sens_50_bat',
            f'{OUTPUT_FOLDER}/2050_sens_40_bat',
            f'{OUTPUT_FOLDER}/2050_sens_30_bat',
        ],
        'scenarios_display_names': [
            'NTC 100%',
            'NTC 90%',
            'NTC 80%',
            'NTC 70%',
            'NTC 60%',
            'NTC 50%',
            'NTC 40%',
            'NTC 30%',
        ],
        'output_filename': 'Sensitivity_Analysis_in_2050_with_batteries.pdf',
    },
    {
        'name': '6. Limited RH investments in 2035',
        'active': sixth,
        'scenarios_to_summarize': [
            f'{OUTPUT_FOLDER}/2035_aa',
            f'{OUTPUT_FOLDER}/2035_aa_rh_1000',
            f'{OUTPUT_FOLDER}/2035_aa_rh_500',
            f'{OUTPUT_FOLDER}/2035_aa_rh_250',
            f'{OUTPUT_FOLDER}/2035_aa_rh_0',
        ],
        'scenarios_display_names': [
            'no limit',
            '1000 MW limit',
            '500 MW limit',
            '250 MW limit',
            '0 MW limit',
        ],
        'output_filename': '2035_with_limited_rh.pdf',
    },
    {
        'name': '7. Limited RH investments in 2050',
        'active': seventh,
        'scenarios_to_summarize': [
            f'{OUTPUT_FOLDER}/2050_aa',
            f'{OUTPUT_FOLDER}/2050_aa_rh_1000',
            f'{OUTPUT_FOLDER}/2050_aa_rh_500',
            f'{OUTPUT_FOLDER}/2050_aa_rh_250',
            f'{OUTPUT_FOLDER}/2050_aa_rh_0',
        ],
        'scenarios_display_names': [
            'no limit',
            '1000 MW limit',
            '500 MW limit',
            '250 MW limit',
            '0 MW limit',
        ],
        'output_filename': '2050_with_limited_rh.pdf',
    },
    {
        'name': '8. Sensitivity analysis 2050 between 40% and 30%',
        'active': eighth,
        'scenarios_to_summarize': [
            f'{OUTPUT_FOLDER}/2050_sens_40',
            f'{OUTPUT_FOLDER}/2050_sens_39',
            f'{OUTPUT_FOLDER}/2050_sens_38',
            f'{OUTPUT_FOLDER}/2050_sens_37',
            f'{OUTPUT_FOLDER}/2050_sens_36',
            f'{OUTPUT_FOLDER}/2050_sens_35',
            f'{OUTPUT_FOLDER}/2050_sens_34',
            f'{OUTPUT_FOLDER}/2050_sens_33',
            f'{OUTPUT_FOLDER}/2050_sens_32',
            f'{OUTPUT_FOLDER}/2050_sens_31',
            f'{OUTPUT_FOLDER}/2050_sens_30',
        ],
        'scenarios_display_names': [
            'NTC 40%',
            'NTC 39%',
            'NTC 38%',
            'NTC 37%',
            'NTC 36%',
            'NTC 35%',
            'NTC 34%',
            'NTC 33%',
            'NTC 32%',
            'NTC 31%',
            'NTC 30%',
        ],
        'output_filename': 'Sensitivity_Analysis_in_2050_40_to_30.pdf',
    },
    {
        'name': '9. 2050 30% NTC with forced PV investments',
        'active': ninth,
        'scenarios_to_summarize': [
            f'{OUTPUT_FOLDER}/2050_sens_30_PV_360',
            f'{OUTPUT_FOLDER}/2050_sens_30',
            f'{OUTPUT_FOLDER}/2050_sens_30_PV_420',
        ],
        'scenarios_display_names': [
            '360 MW PV',
            'normal (392 MW PV)',
            '420 MW PV',
        ],
        'output_filename': '2050_30_NTC_with_fixed_PV.pdf',
    },
]
def run_script(config):
    """Run the summary script with the given configuration via CLI overrides."""
    base_dir = Path(__file__).parent.parent
    output_base = base_dir / "plots" / Path(config["output_filename"]).with_suffix("")
    output_base.parent.mkdir(parents=True, exist_ok=True)
    pdf_path = output_base.with_suffix(".pdf")
    png_path = output_base.with_suffix(".png")

    script_path = Path(__file__).parent / 'summary_for_presentation_NTC_affects_storage_paper.py'
    args = [
        sys.executable,
        str(script_path),
        '--scenarios', *config['scenarios_to_summarize'],
        '--display-names', *config['scenarios_display_names'],
        '--output-base', str(output_base),
    ]

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        print("  ❌ Error while running summary script")
        return False

    if result.stdout:
        print(result.stdout)

    print(f"  → Exported: {pdf_path}")
    print(f"  → Exported: {png_path}")
    return True


def main():
    print("=" * 80)
    print("Running multiple scenario configurations")
    print("=" * 80)
    
    # Count active configurations
    active_configs = [c for c in CONFIGURATIONS if c['active']]
    print(f"\nFound {len(active_configs)} active configuration(s) out of {len(CONFIGURATIONS)} total.\n")
    
    if not active_configs:
        print("No active configurations found. Set 'active': True in the script to enable configurations.")
        return
    
    # Run each active configuration
    for idx, config in enumerate(active_configs, 1):
        print(f"\n[{idx}/{len(active_configs)}] Running: {config['name']}")
        print(f"  Scenarios: {', '.join(config['scenarios_to_summarize'])}")
        print(f"  Output: {config['output_filename']}")
        
        try:
            success = run_script(config)
            
            if success:
                print(f"  ✓ Successfully generated {config['output_filename']}")
            else:
                print(f"  ✗ Failed to generate {config['output_filename']}")
                
        except Exception as e:
            print(f"  ❌ Exception occurred: {str(e)}")
    
    print("\n" + "=" * 80)
    print("All active configurations completed!")
    print("=" * 80)


if __name__ == '__main__':
    main()
