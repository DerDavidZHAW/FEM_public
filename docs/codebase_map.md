# Codebase map

Checked against: `main` @ 54d6be28 (2026-10-09).

How one run moves through the code, and which file to change for which task. For folder
contents, list the folder; this guide records what a listing does not tell you.

## How a run flows

1. **`run_scenarios.py`** loops over `meta_scenarios_list` and calls `model.core.core_main` once
   per meta-scenario. `run_scenarios_hpc.py --scenario <name>` runs a single one (SLURM).
2. **`scenarios/scenarios.py`** reads the CSV named on its `target_csv =` line and groups its
   columns into meta-scenarios and sub-scenarios (rules in `docs/running.md`).
3. **`model/core.py`, `core_main`** (about 390 lines, orchestration only):
   - imports data per sub-scenario (`data_prep/data_import_TYNDP.py`, `data_import_TYNDP_fcn`,
     which uses `model/data_import_fcns.py`);
   - reads settings per sub-scenario (`model/read_settings.py`: scenario CSV values override
     `scenarios/settings_default.py`) and writes `output/<meta>/settings.csv`;
   - builds the model from `model/components_common.py`: `define_sets`, `define_params_inv`,
     `define_params_op`, `define_vars_op`, `define_vars_inv`, `obj_expression`,
     `define_constraints`, then `define_constraints_central` (`model/components_central.py`:
     electrolyzer energy, winter import limit, Swiss RES target) and `fixing_capacities_central`
     (fixes pre-existing capacities);
   - applies presets from `input/model_variable_presets.csv` (`model/variable_presets.py`);
   - solves with `pyo.SolverFactory(solver_name)` and the options string `solver_parameters`,
     hard-coded in `core.py`;
   - exports results (see "Exports" below).

## Where to change what

| Task | Where |
|---|---|
| New or changed constraint | A rule function plus `model.<name> = Constraint(...)` inside `define_constraints` in `model/components_common.py`. The electrolyzer energy limits, the winter import limit and the Swiss RES target are in `model/components_central.py`. |
| Scale a constraint for numerics | Multiply both sides by `model.constraint_scaling['<name>']` in the rule and add `'<name>': <factor>` to `model/constraint_scaling.py`. The dual export converts the dual back to unscaled units (`docs/duals.md`). |
| Export a constraint's dual by default | Add its name to `constraint_names_to_export` in `model/core.py`. With the setting `DUALS_EXPORT_ALL` set to `True`, the duals of all active constraints are exported. |
| New variable | `define_vars_op` (dispatch) or `define_vars_inv` (capacities) in `model/components_common.py`. All variables are exported automatically. |
| Cost term | `obj_expression` in `model/components_common.py`. Multiply every term by `model.weight_in_objective_fcn[scen]` inside the loop over `model.Scenarios` (`docs/multi_weather_year.md`). |
| New setting | Default in `scenarios/settings_default.py`; read as `settings_scen["<name>"]` in `model/core.py` or the data import. A row in the scenario CSV overrides the default; values are parsed with `eval`, so `True`, `0.5` and lists work. |
| Input data | Files in `input/`, read by `model/data_import_fcns.py` and `data_prep/`. District-heating plants: `input/plants_DH_CH_features.csv` (existing, incl. `efficiency` = COP for heat pumps) and `input/plants_DH_invest_candidates.csv`. Cost data: `input/cost_operation_invest_data.py`. |
| Technology cost category | `Map_plant_tech_cost_component` in `model/structural_parameters.py` (`cap_op` or `cap_op_energy`). |
| Fix or start values for one scenario | `input/model_variable_presets.csv` (format in its header). |
| Solver options | `solver_parameters` in `model/core.py` (e.g. append `method=2` for barrier only on large runs). |

## Exports

Results are written during the run, right after the solve, by `model/core.py` together with
`aggregation/results_export.py`. That module sits in `aggregation/` but has nothing to do with
combining scenarios: `par_var` writes every variable and indexed parameter, `constraints` writes
the duals, `reduced_costs` the reduced costs. `model/investment_summary.py` writes
`investment_summary.csv`. File conventions: `docs/outputs.md`.

## After the run

| Step | Code |
|---|---|
| Combine several runs | `aggregate_results.py`, which calls `aggregation/aggregate_new.py` |
| Plots of one or several runs | `visualization_class.py` (writes to `plots/`); standalone scripts in `plot_creators/` |
| Browser dashboard of one run | `tools/prepare_viewer.py` and `viewer.html` (main README) |
| Detailed reports from saved CSVs | `python -m detailed_reporting.run_detailed_reporting_posthoc`; the in-run call in `core.py` is commented out |

`aggregate_results.py`, `visualization_class.py` and the post-hoc runner each start with a
hard-coded list of run folders; edit it to your runs first (`docs/running.md`).

## Tests

`tests/` holds unit tests for helpers with no solver: the DH demand overlay
(`model/dh_demand_adjustment.py`), its generator (`utils/make_dh_adjustment.py`) and the dual
export. How to run them and what new code needs: `docs/running.md`.
