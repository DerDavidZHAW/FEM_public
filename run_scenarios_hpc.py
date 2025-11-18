import argparse
from scenarios.scenarios import meta_scenarios_list
import model.core as core

# Parse the scenario name from the command line
parser = argparse.ArgumentParser()
parser.add_argument("--scenario", required=True, help="Scenario key from meta_scenarios_list")
args = parser.parse_args()

# Get the sub-scenario list for this scenario
sub_scenarios_list = meta_scenarios_list[args.scenario]

# Run just this one
print(70 * "-")
print(f"Running scenario: {args.scenario}")
print(70 * "-")
core.core_main(args.scenario, sub_scenarios_list)
