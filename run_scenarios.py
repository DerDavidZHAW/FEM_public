# import model.monkey_patch # Activate this to have all imported files printed in the end
from scenarios.scenarios import meta_scenarios_list
import model.core as core

for scenario_name, sub_scenarios_list in meta_scenarios_list.items():
    print(70 * "-")
    print(f"Running scenario: {scenario_name}")
    print(70 * "-")
    core.core_main(scenario_name, sub_scenarios_list)
