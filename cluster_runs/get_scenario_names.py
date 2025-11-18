#!/usr/bin/env python3
"""
Extract scenario names from CSV using the same logic as scenarios.py
This allows SLURM scripts to dynamically get scenario names without hardcoding.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scenarios.scenarios import meta_scenarios_list

if __name__ == "__main__":
    # Get meta scenario names (keys from meta_scenarios_list)
    meta_scenario_names = list(meta_scenarios_list.keys())
    
    # Check if called with --names-only flag for SLURM usage
    if len(sys.argv) > 1 and sys.argv[1] == "--names-only":
        # Only print meta scenario names, one per line (for SLURM mapfile)
        for scenario in meta_scenario_names:
            print(scenario)
    else:
        # Print total number of meta scenarios first (for interactive use)
        print(f"Total meta scenarios: {len(meta_scenario_names)}")
        
        # Print meta scenario names, one per line
        for scenario in meta_scenario_names:
            print(scenario)