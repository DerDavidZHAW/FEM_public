from pathlib import Path

# Model version - imported from shared module
from model.version import MODEL_VERSION
_MODEL_VERSION = MODEL_VERSION  # Alias for backwards compatibility

#%% import data definitions and vlues -----------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------

import data_prep.definitions_common
import data_prep.definitions_TYNDP

from data_prep.definitions_common import *
from data_prep.definitions_TYNDP import *
from data_prep.definitions_TYNDP import Consumer_list_TYNDP
from data_prep.data_import_TYNDP import data_import_TYNDP_fcn
from model.components_common import *
from model.components_central import *
from model.read_settings import read_scenario_settings
from model.reset_items import get_lists_and_dicts
from pyomo.opt import ProblemFormat
import model.data_import_fcns as data_import_fcns
#import tariff_calibration.tariff_adjustments as tariff_adjustments
from utils.utilities_model import export_model_to_txt, export_model_obj
#from utils.dict_to_csv import dict_3dim_to_csv
import aggregation.results_export as res_export
import utils.settings_to_csv as set_to_df
from detailed_reporting.reporting_main import generate_detailed_reports
from model.structural_parameters import (
    tech_demand_with_timeseries_netflex_model_list,
    tech_infeed_consumers_list,
    tech_infeed_all_list,
    tariff_export_definitions,
    tariff_import_definitions,
)
import utils.export_solve_statistics as export_model_stats
import model.price_setting_tech as price_setting_tech

import model.investment_summary as investment_summary
from model.variable_presets import apply_variable_presets, read_variable_presets

# %% import packages ---------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------
from pydoc import doc
import pyomo.environ as pyo
import pandas as pd
from io import StringIO  # used to export model to txt file
import time
import os

# %% main function -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------

def core_main(scenario_name, sub_scenarios_list, model_version=None):
    # Start timer for total runtime tracking
    total_timer_start = time.time()
    
    # create output folder --------------------
    output_dir = Path("output") / scenario_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # model definition ------------------------
    model = pyo.ConcreteModel(name="core_" + scenario_name + "_" + str(time.time()).split(".")[0])

    # read data for all sub_scenario ----------
    for sub_scen in sub_scenarios_list:
        data_import_TYNDP_fcn(sub_scen)

    tech_infeed_core_run_list = tech_infeed_all_list.copy()

    # import run settings, be defined separately for each sub_scenario ----------------------
    # --------------------------------------------------------------------------------
    winter_limit = {}
    minimum_RES_target_CH = {}
    weight_in_objective_fcn = {}

    # Create an empty dictionary to store the settings data
    settings_dict = {}

    for sub_scen in sub_scenarios_list:
        # Read settings for each sub_scenario
        settings_scen = read_scenario_settings(sub_scen)
        settings_df = set_to_df.settings_to_df_fcn(settings_scen)
    
        # Convert settings_df to a single-column series with index
        settings_dict[sub_scen] = settings_df.iloc[:, 0]  # Assuming first column contains values
    
        # Store specific values independently
        winter_limit[sub_scen] = settings_scen["winter_limit"]
        minimum_RES_target_CH[sub_scen] = settings_scen["minimum_RES_target_CH"]
        weight_in_objective_fcn[sub_scen] = settings_scen["weight_in_objective_fcn"]

        # the settings below are forced to be equal for all sub_scenarios (using the last sub_scenario)
        T_list = settings_scen["T_list"]
        CH_only = settings_scen["CH_only"]
        if CH_only: # If CH_only mode is active, keep only CH nodes
            Node_list = [n for n in settings_scen["Node_list_setting"] if n.startswith("CH")]
        else:
            Node_list = settings_scen["Node_list_setting"]
        slack_soc = settings_scen["slack_soc"]
        NodeDH_list = settings_scen["NodeDH_list"]
        resistive_heater_cap = settings_scen["resistive_heater_investment_cap_MW_total"]
    
    # Validate that resistive heater investment caps are identical across all subscenarios
    for sub_scen in sub_scenarios_list[1:]:  # Check all except the first one
        settings_scen_check = read_scenario_settings(sub_scen)
        if settings_scen_check["resistive_heater_investment_cap_MW_total"] != resistive_heater_cap:
            raise ValueError(
                f"ERROR: Resistive heater investment cap must be identical for all subscenarios in stochastic optimization. "
                f"Found different values: {resistive_heater_cap} vs {settings_scen_check['resistive_heater_investment_cap_MW_total']}"
            )

    merged_settings_df = pd.DataFrame(settings_dict)
    
    # Add model version to settings
    if model_version is None:
        model_version = _MODEL_VERSION
    merged_settings_df.loc['model_version'] = model_version
    
    # Ensure output directory exists
    output_dir = os.path.join("output", scenario_name)
    os.makedirs(output_dir, exist_ok=True)
    
    # Export the merged DataFrame at the end
    merged_settings_df.to_csv(os.path.join(output_dir, "settings.csv"), index=True)  # Keep index for clarity

    if round(sum(weight_in_objective_fcn.values()),6) != 1.000000: # Adjusted because of floating point precision issues
        raise ValueError("The sum of weight_in_objective_fcn should be equal to 1. See the scneario description file as mentioned in scenarios.py, e.g., scenarios/scen_to_run_winter.csv.")

    if slack_soc:
        model.slack_soc = True # type: ignore

    # %% define the model, sets ------------------------------------------------------------------------
    model = define_sets(
        model,
        Plant_list,
        Consumer_list,  # both TYNDP and NETFLEX consumers
        Consumer_list,  # consumer_infeed_sel
        tech_infeed_core_run_list,
        T_list,
        Node_list,
        False, #Consumer_list_netflex
        ["fixed",],  # tech_demand_modeled
        ["fixed",],  # tech_demand_inflex_selected
        sub_scenarios_list,
        NodeDH_list, # district heating nodes
        PlantDH_list, # district heating plants
    )
    # %% Parameters ------------------------------------------------------------------------------------
    model = define_params_inv(model, weight_in_objective_fcn, resistive_heater_cap)
    model = define_params_op(model, resistive_heater_cap)
    model = define_vars_op(model)
    model = define_vars_inv(model)
    # %% Objective function ------------------------------------------------------------------------------
    start = time.time()
    model.OBJ = pyo.Objective(rule=obj_expression)
    print("time to define objective function: ", time.time() - start)
    # %% Constraints -------------------------------------------------------------------------------------
    start_ct = time.time()
    model = define_constraints(model)
    model = define_constraints_central(
        model,
        False, #consumer_based_on_tariff
        winter_limit,
        minimum_RES_target_CH,
    )
    print("time to define constraints: ", time.time() - start_ct)
    # %% fixing values  (pre-existing capacities etc.)----------------------------------------------------
    fixing_capacities_central(model, sub_scenarios_list)
    
    # Apply variable presets from CSV file (if it exists)
    print("Applying variable presets from model_variable_presets.csv...")
    preset_summary = apply_variable_presets(model, scenario_name, preset_file_path="input/model_variable_presets.csv", verbose=True)
    applicable_count = len([p for p in read_variable_presets('input/model_variable_presets.csv') if p['scenario_name'] == '' or p['scenario_name'] == scenario_name])
    print(f"Presets applied: {preset_summary['applied']}, Failed: {preset_summary['failed']}, Total applicable: {applicable_count}")
    if preset_summary['details']:
        print("Preset details:")
        for preset, status, message in preset_summary['details']:
            print(f"  - {status}: {preset.get('variable_name')} | indices={preset.get('indices')} | scen={preset.get('scenario_name')} -> {message}")
    
    # %% solve model -------------------------------------------------------------------------------------
    # export_model_to_txt("before_solve" + scenario_name, model, scenario_name) # Exporting the model (debugging purposes)
    # export_model_obj("OBJbefore_solve" + scenario_name, model, scenario_name) # Exporting the model (debugging purposes)
    print("Solving the model ...")
    solve_timer_start = time.time()
    opt = pyo.SolverFactory(settings_scen["solver_name"])  # Specify the solver

    log_path = Path("output") / scenario_name / "solver_log.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists
    opt.options["LogFile"] = str(log_path)  # Convert Path object to string if needed
    
    model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)     # so that dual values are reported back from the solve
    model.rc = pyo.Suffix(direction=pyo.Suffix.IMPORT)       # so that reduced costs are reported back from the solve
    
    # Diagnostic: Check for large objective coefficients BEFORE solving
    print("Checking objective function coefficients...")
    large_coef_data = export_model_stats._check_objective_coefficients(model, output_dir, threshold=1e6)
    if large_coef_data:
        print(f"  WARNING: Found {len(large_coef_data)} variables with objective coefficients > 1e6")
        print(f"  Details saved to: {output_dir}/large_objective_coefficients.csv")
    else:
        print("  OK: No unusually large objective coefficients found.")
    
    # Solver settings optimized for reliable reduced costs
    # - Crossover=0 disabled: Gurobi will use default crossover (important for basis/reduced costs)
    # - Method=2: Barrier method (good for large LPs)
    # - BarConvTol=1e-10: Tighter barrier convergence for better numerical precision
    # - OptimalityTol=1e-8: Slightly tighter than default (1e-6) for better reduced costs
    # - FeasibilityTol=1e-7: Slightly tighter than default for constraint satisfaction
    # - NumericFocus=1: Mild numeric focus (0=off, 1=mild, 2=moderate, 3=aggressive)
    # Note: We do NOT use ScaleFlag or extreme NumericFocus to avoid slowing down too much
    solver_parameters = "threads=8 Method=2 BarConvTol=1e-10 OptimalityTol=1e-8 FeasibilityTol=1e-7 NumericFocus=1"
    
    result = opt.solve(
        model,
        tee=True,                           # tee: prints solver statements (summary)
        keepfiles=False,
        options_string=solver_parameters,
        symbolic_solver_labels=True,
    )
    solve_time = time.time() - solve_timer_start
    print("time to solve the model: ", solve_time)    
    # %% export result ----------------------------------------------------------------------------------
    print("Exporting the results ...")
    # export statistics and settings ---------------------------------
    export_model_stats.export_fcn(scenario_name, result, model, solve_time)

    # Variables ----------------------------------------------------
    # create a list of all variables in the model
    var_list = [v for v in model.component_objects(ctype=Var, active=True, descend_into=True)]

    # export all variables in var_list
    res_export.par_var(var_list, scenario_name)

    # Parameters ---------------------------------------------------
    # create a list of all indexed parameters in the model (exclude scalars)
    par_list = [v for v in model.component_objects(ctype=Param, active=True, descend_into=True) if v.is_indexed()]

    # export all parameters in par_list
    res_export.par_var(par_list, scenario_name)
    
    # Cost breakdowns (from objective function) -------------------
    print("Exporting cost breakdowns...")
    cost_dict_names = [
        'cost_inv_dict',
        'cost_op_dict', 
        'lostload_cost_dict',
        'cost_op_thermal_dict',
        'cost_inv_thermal_dict',
        'cost_inv_fuel_storage_dict',
        'trade_cost_dict',
        'emissions_dict'
    ]
    
    for cost_name in cost_dict_names:
        if hasattr(model, cost_name):
            cost_dict = getattr(model, cost_name)
            if cost_dict:  # Only export if not empty
                output_path = Path("output") / scenario_name / f"{cost_name}.csv"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Convert dictionary to DataFrame
                data = []
                for key, value in cost_dict.items():
                    if isinstance(key, tuple):
                        row = list(key) + [pyo.value(value)]
                    else:
                        row = [key, pyo.value(value)]
                    data.append(row)
                
                # Determine column names based on key structure
                if data and isinstance(list(cost_dict.keys())[0], tuple):
                    key_length = len(list(cost_dict.keys())[0])
                    if key_length == 2:
                        if cost_name == 'emissions_dict':
                            columns = ['plant', 'scenario', 'emissions_tCO2']
                        else:
                            columns = ['plant', 'scenario', 'cost_CHF']
                    else:
                        if cost_name == 'emissions_dict':
                            columns = [f'key_{i}' for i in range(key_length)] + ['emissions_tCO2']
                        else:
                            columns = [f'key_{i}' for i in range(key_length)] + ['cost_CHF']
                else:
                    if cost_name == 'emissions_dict':
                        columns = ['scenario', 'emissions_tCO2']
                    else:
                        columns = ['scenario', 'cost_CHF']
                
                df = pd.DataFrame(data, columns=columns)
                df.to_csv(output_path, index=False)
                # print(f"  Exported {cost_name}")
    
    # Sets ---------------------------------------------------------
    set_names_to_export = ["P_allinv", ]
    set_list = [v for v in model.component_objects(ctype=Set, active=True, descend_into=True)
                if v.name in set_names_to_export]
    for set_obj in set_list:
        set_name = set_obj.name
        if not set_name.endswith("index"):

            output_path = Path("output") / scenario_name / f"{set_name}.csv"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            element_dict = {}
            counter = 0
            for element in set_obj:
                if element != set_name: # element == set_name happens when set is empty
                    element_dict[counter] = [element]
                    counter += 1

            dimension = len(element_dict[0]) if element_dict else 0 # if set is empty, dimension is 0, then csv file is empty
            if dimension == 0:
                df = pd.DataFrame(columns=["Set is empty"])
            else:
                df = pd.DataFrame(element_dict.values(),
                                  columns=["Dimension_" + str(i) for i in range(dimension)])
            df.to_csv(output_path, index=False)

    # Dual values ------------------------------------------------
    # exports all dual values of constraints automatically in seperate files named after variable's name

    constraint_names_to_export = [
        "energy_balance",
        "storage_soc",
        "energy_balancethermal",
        # "storage_soc_limit",
        # "lineATClimit",
    ]

    if winter_limit[sub_scen]["mode"]:
        constraint_names_to_export.append("Constraint_winter_limit")

    if minimum_RES_target_CH[sub_scen]:
        constraint_names_to_export.append("Constraint_investment_res_CH")
    constraint_list = [v for v in model.component_objects(ctype=Constraint, active=True, descend_into=True)
                       if v.name in constraint_names_to_export]
    
    # export all dual values of constraints in constraint_list
    dual_values_dict = res_export.constraints(constraint_list, scenario_name, model, write_csv=True)

    # Reduced costs for investment variables --------------------------------
    # These tell you how much cheaper a technology would need to be to become competitive
    investment_var_names = [
        "gen_max",           # generation capacity (MW)
        "genTh_max",         # thermal generation capacity (MW thermal)
        "gen_energy_max",    # storage energy capacity (MWh)
        "gen_energyTh_max",  # thermal storage energy capacity (MWh thermal)
    ]
    reduced_costs_dict = res_export.reduced_costs(
        investment_var_names, 
        scenario_name, 
        model, 
        weight_in_objective_fcn, 
        write_csv=True
    )

    # df_plants, df_counts = price_setting_tech.aggregate_price_setting_data(
    #     scenario_name,
    #     sub_scenarios_list,
    #     model,
    #     dual_values_dict,
    # )

    list_of_lists_common, list_of_dicts_common = get_lists_and_dicts(
        data_prep.definitions_common, []
    )
    list_of_lists_tyndp, list_of_dicts_tyndp = get_lists_and_dicts(
        data_prep.definitions_TYNDP, []
    )

    investment_summary.investment_summary(r"output/" + scenario_name + "/")
    
    # Calculate total runtime
    total_time_seconds = time.time() - total_timer_start
    
    # Generate detailed reports for Swiss model intercomparison (only for single subscenario runs)
    if len(sub_scenarios_list) == 1:
        generate_detailed_reports(model, scenario_name, total_time_seconds=total_time_seconds)
    else:
        print(f"Skipping detailed reporting: only supported for single subscenario runs (found {len(sub_scenarios_list)} subscenarios)")