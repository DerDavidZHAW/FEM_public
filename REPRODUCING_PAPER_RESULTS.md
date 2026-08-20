# Reproducing the Paper Results

This guide walks through every step from a fresh download of the FEM model (release **v1.0.3**) to recreating the model outputs, aggregating and visualizing them, and rebuilding the figures of the paper on how cross-border transmission capacity (NTC) affects storage in Switzerland.

The general model documentation is split across three places. The [README](README.md) covers installation and day-to-day usage. The *FEM model description* (Zenodo, DOI [10.5281/zenodo.21996753](https://doi.org/10.5281/zenodo.21996753)) contains the mathematical formulation. The *Model Settings and Output Files* document explains every setting and output file referenced below.

## 1. Install the model

Follow the [Installation section of the README](README.md#installation). In short, you need Python 3.10 to 3.12, [Poetry](https://python-poetry.org/), and a licensed Gurobi installation (free academic licenses are available). Then:

```bash
git clone https://github.com/DerDavidZHAW/FEM_public.git
cd FEM_public
poetry install
poetry run python -c "import gurobipy; print(gurobipy.gurobi.version(), 'OK')"
```

For runs on an HPC cluster (recommended, see step 3), the README section *Installation on HPC Clusters* describes the setup for ETH Euler and SciCORE.

## 2. Configure the paper runs

The paper's run list ships with the repository as `scenarios/scen_to_run_STORSUPPORT.csv`. Make sure `scenarios/scenarios.py` points at it:

```python
target_csv = "scenarios/scen_to_run_STORSUPPORT.csv"
```

How the run list is organized:

- Each **column block** is one scenario. The row `Item` holds the scenario name, which is also the name of its output folder.
- Scenario names follow the pattern `<run_year>_<NTC level>_inv_<battery configuration>`, for example `2050_070_inv_EUbat` = target year 2050, Swiss NTC scaled to 70 % (`NTC_CH_ratio = 0.7`), battery investments allowed in Switzerland and the neighboring nodes (`EUbat`). In the `CHbat` configuration (`battery_investment_nodes_in_addition_to_CH` empty), battery investments are possible in Switzerland only.
- Each scenario consists of **three subscenarios** (`sub_secn` = `wy1995`, `wy2008`, `wy2009`), the three weather years of the two-stage stochastic optimization, weighted approximately equally (0.33/0.33/0.34) via `weight_in_objective_fcn`.
- Every setting not listed in the CSV takes its default from `scenarios/settings_default.py`. All settings are explained in the *Model Settings and Output Files* document.

## 3. Run the model

**Sequentially on a workstation:**

```bash
poetry run python run_scenarios.py
```

This runs every scenario in the CSV one after the other. Be aware of the problem size: each scenario is a single large linear program (three coupled weather years at hourly resolution) and solves in several hours on 8 cores with considerable memory demand. For the full run list, use a cluster.

**In parallel on an HPC cluster (SLURM):**

```bash
# one-time setup on ETH Euler (output folder on scratch, logs on home)
bash cluster_runs/setup_euler_scratch.sh

# count the scenarios, then set "#SBATCH --array=0-(N-1)" in the job script
python cluster_runs/get_scenario_names.py

sbatch cluster_runs/parallel_runs_Euler.sh
```

Each array task solves one scenario. See the README sections *Parallel Execution on HPC Clusters* and *Troubleshooting on Euler* for details.

**Check the results.** Each scenario writes its outputs to `output/<Item>/`. Two quick checks per scenario:

- `statistics.csv` should report an optimal termination.
- `settings.csv` records every setting used plus the row `model_version` (1.0.3), so you can verify the run matches this release.

If you collect the outputs of a run campaign in a dated subfolder (e.g. `output/20260311/<Item>/`), keep that prefix in mind for the plotting steps below.

## 4. Aggregate the results

The aggregation collects the per-scenario outputs of a series of runs into one folder with comparable summary tables. Open `aggregate_results.py` and set the two variables at the top:

```python
scenarios_to_agg = [
    "2035_100_inv_CHbat",   # or "20260311/2035_100_inv_CHbat" if you used a dated subfolder
    "2035_090_inv_CHbat",
    # ... one entry per NTC level ...
]
agg_name = "20260313_2035_inv_CHbat"   # name of the aggregated output folder
```

Then run:

```bash
poetry run python aggregate_results.py
```

The results land in `output/aggregated/<agg_name>/`, including `Annual_balance_ch.csv` (annual Swiss generation, demand, trade and flexibility balance), `total_system_cost_summary.csv`, aggregated hourly tables such as `energy_balance_dual.csv`, and `statistics.csv`.

For the paper, aggregate one folder per target year and battery configuration, each covering the full NTC series (100 % down to 30 %), i.e. four aggregated folders: 2035/CHbat, 2035/EUbat, 2050/CHbat, 2050/EUbat. If a series is spread over several aggregated folders, `aggregation/merge_aggregateds.py` can merge them.

## 5. General visualization (optional)

For interactive exploration independent of the paper figures:

```bash
poetry run python plot_creators/run_all_visualizations.py   # standard plot collection
poetry run python visualization_class.py                    # configurable plot classes
```

The README section *Visualization* also describes the standalone dashboard `viewer.html`.

## 6. Recreate the paper figures

All figure scripts live in `plot_creators/`. Each script defines its input scenario or aggregation folder names near the top of the file (or accepts them as command-line arguments). Adapt these to the folder names you chose in steps 3 and 4, then run the script with `poetry run python <script>`.

| Paper figure | Script | Input |
|---|---|---|
| Battery investments per NTC level (`Battery_Investments_<year>_inv_<cfg>.pdf`) | `plot_creators/battery_investments_summary_for_presentation.py` | `investment_summary.csv` and `P_allinv.csv` of each scenario |
| Investment sensitivity overview across NTC levels | `plot_creators/summary_for_presentation_NTC_affects_storage_paper.py` | `investment_summary.csv` and `P_allinv.csv` of each scenario |
| Electricity price violin plots (`violin_plot_<year>_<cfg>_wy<wy>.pdf`) | `plot_creators/violin_price_plot.py` | `energy_balance_dual.csv` of each scenario |
| Swiss trade and flexibility vs. NTC (`CH_trade_and_flexibility_vs_NTC.pdf`) | `plot_creators/ch_flows_flexibility_vs_ntc.py` | `Annual_balance_ch.csv` of the aggregated folders (step 4) |
| Battery arbitrage revenue vs. NTC (`plot_F_arbitrage_revenue_CHF.pdf`) | `plot_creators/arbitrage_revenue_vs_ntc.py` | aggregated hourly prices and battery dispatch (step 4) |

The two summary scripts accept explicit arguments, for example:

```bash
poetry run python plot_creators/battery_investments_summary_for_presentation.py \
    --scenarios 20260311/2035_030_inv_CHbat 20260311/2035_050_inv_CHbat 20260311/2035_100_inv_CHbat \
    --display-names "NTC 30 %" "NTC 50 %" "NTC 100 %" \
    --output-base output/20260311/Battery_Investments_in_2035
```

`violin_price_plot.py` takes the scenario folder names as positional arguments plus `--output-folder <dated subfolder>`. For `ch_flows_flexibility_vs_ntc.py` and `arbitrage_revenue_vs_ntc.py`, edit the aggregated folder paths defined at the top of the script.

## 7. Version note

The paper results correspond to release **v1.0.3** of this repository (`model/version.py`). If you work from a later state of `main`, check the changelog of the model description for formulation changes before comparing results.
