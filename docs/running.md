# Running the model

Checked against: `main` @ 54d6be28 (2026-10-09).

Installation, Gurobi and the Euler and SciCORE setup are in the [main README](../README.md).
This guide covers what to run once the environment works.

## Environment in one paragraph

Install with `poetry install --no-root` (plain `poetry install` fails: the repo is not an
installable package). Run scripts with `poetry run python <script>`, or activate the environment
with the command printed by `poetry env activate`. Pyomo calls Gurobi through Gurobi's own
command-line launcher (`gurobi.bat` on Windows, `gurobi.sh` on Linux), so a full Gurobi
installation on `PATH` and a licence are required; the Python package `gurobipy` is not.

## Scenario CSVs

The CSV named on the `target_csv =` line of `scenarios/scenarios.py` defines what
`run_scenarios.py` runs. Rows are settings, columns are sub-scenarios.

- **`sub_secn` row (required).** Without it, no scenario is created and `run_scenarios.py`
  finishes without running anything. Each sub-scenario is named `<column name>_<sub_secn>`, and
  that name appears in the `Scenarios` column of every output file.
- **Meta-scenarios.** Columns with the same header form one meta-scenario: one optimisation with
  shared investment (`docs/multi_weather_year.md`). pandas renames repeated headers to
  `name.1`, `name.2`, and `scenarios.py` groups every column that starts with the meta name and
  ends in `.<number>`. Give meta-scenarios names that do not start with another meta-scenario's
  name (`2035_base` and `2035_base_high` would collide).
- **`weight_in_objective_fcn` row (required, no default).** The weights of a meta-scenario must
  sum to 1 (checked to 6 decimals); a single-column meta-scenario has weight 1.
- **Other settings.** Any setting missing from the CSV takes its value from
  `scenarios/settings_default.py`. Values are parsed with `eval`, so `True`, `0.5`, lists and
  dictionaries work; anything that fails to parse stays a string. An empty cell becomes the
  string `"nan"`, not the default: to use the default for one column, give it the default value
  explicitly.
- **Time window.** `t_start` and `t_end` are hour numbers of the weather-year calendar (`t_1` is
  1 January, 00:00). If `t_start > t_end` the window wraps over New Year. The default,
  `t_start = 6553` and `t_end = 6552`, is the full hydrological year from 1 October.
- **Weather years.** District-heating demand exists for 1995, 2008 and 2009 (run years 2035 and
  2050).

`scenarios/scen_to_run_STORSUPPORT.csv` is the default and a full example of a three-weather-year
setup; `scenarios/scen_to_run_dh_ab.csv` is a one-week A/B example for the DH demand overlay.

## Test run

A **test run** is the end-to-end check after model changes.

1. In `scenarios/scenarios.py`, note the current `target_csv` value, then set it to
   `"scenarios/scen_to_run_test.csv"`.
2. Run `poetry run python run_scenarios.py`.
3. Restore `target_csv` to the value from step 1.

The test scenario is one meta-scenario `2050_st` with one sub-scenario (`wy1995_aa`, weight 1):
run year 2050, weather year 1995, 25 hours from 1 October (`t_6553` to `t_6577`). It finishes in
a few minutes, mostly data import; the solve itself takes seconds. Results go to
`output/2050_st/` and overwrite the previous test run. `output/2050_st/statistics.csv` should
report `Termination_Condition` `optimal`.

The test scenario has a single sub-scenario and does not use the DH demand overlay, so it does
not exercise multi-weather-year logic. To check such a change, put a temporary copy of the test
column, repeated with different `sub_secn` values and weights summing to 1, in a CSV outside
the repo and point `target_csv` at it.

## Unit tests

```bash
poetry run pytest
```

`pyproject.toml` puts the repo root on the import path. The tests cover helpers that need no
solver: the DH demand overlay, its generator, and the dual export. Nothing tests building or
solving the model, which is what the test run is for.

Every new or changed function gets unit tests in `tests/` that fail on the old code. Prefer
small inputs built in the test over files from `input/` or `output/`. A model change also needs
a test run.

## Aggregation and plots

Both scripts start with a hard-coded list of run folders under `output/`; edit it first.

- `aggregate_results.py`: set `scenarios_to_agg` and `agg_name`. Writes
  `output/aggregated/<agg_name>/`.
- `visualization_class.py`: set `scenarios_to_plot`, `target_node` and the `PLOT_*` switches.
  Writes HTML to `plots/`.

## HPC runs

The Euler setup is in the main README. Facts the script does not make obvious:

- `cluster_runs/parallel_runs_Euler.sh` runs one array task per **meta-scenario** of the CSV in
  `target_csv`. Set `#SBATCH --array=0-<N-1>` to the count printed by
  `python cluster_runs/get_scenario_names.py`.
- The script loads the Euler modules and expects the repo at `~/repos/Future_Markets`. There is
  no SciCORE job script in the repo.
- A meta-scenario with three full-year sub-scenarios needs well over 32 GB of RAM, with the peak
  when results are read back into Pyomo after the solve; run it on Euler (8 CPUs × 16 GB in the
  job script). For such runs, `method=2` (barrier only) in `solver_parameters` in
  `model/core.py` lowers solver memory. It can return a different one of several optimal dual
  solutions than the default method (`docs/duals.md`).
- Euler scratch is purged after 15 days without access (per the README); copy results off it.
