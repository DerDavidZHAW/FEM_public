"""Run every meta-scenario of the scenario CSV named in scenarios/scenarios.py, one process each."""
from scenarios.scenarios import meta_scenarios_list
from model.scenario_runner import run_meta_scenarios

run_meta_scenarios(list(meta_scenarios_list))
