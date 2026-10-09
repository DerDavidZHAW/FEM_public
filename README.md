# Future Markets Energy System Model

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

A comprehensive energy system optimization model for analyzing future European electricity and heat markets, with detailed focus on Switzerland and neighboring countries.

## Overview

This model optimizes energy system operations and investments across multiple scenarios, integrating:

- **Electricity markets** with renewable energy sources (solar, wind, hydro)
- **Heat markets** with district heating and thermal storage
- **Energy storage** systems (batteries, pumped hydro, thermal storage)
- **Electrolyzers** and Power-to-X technologies
- **Cross-border electricity trading** and transmission constraints
- **Scenario analysis** for different policy and technology pathways

The model uses **Pyomo** for mathematical optimization and **Gurobi** as the default solver.

## Key Features

- **Multi-temporal optimization** with hourly resolution
- **Investment planning** for generation and storage technologies
- **Detailed Swiss energy system** representation with cantonal resolution
- **TYNDP data integration** for European context
- **Parallel scenario execution** support for HPC clusters
- **Interactive visualizations** with Plotly
- **Comprehensive result analysis** and export capabilities

## Documentation

- [docs/README.md](docs/README.md): guides on running the model, scenario files, output files,
  duals and multi-weather-year runs.
- [AGENTS.md](AGENTS.md): rules and entry point for coding agents (Claude Code reads it through
  `CLAUDE.md`).

## Installation

### Prerequisites

- **Python 3.10–3.12**
- **Poetry** for dependency management
- **Gurobi license** (academic license available)

### Local Installation

1. **Clone the repository:**

   ```bash
   git clone <link>
   cd Future_Markets
   ```

2. **Install dependencies with Poetry:**

   ```bash
   poetry install --no-root
   ```

   `--no-root` is required: the repository is not an installable package.

3. **Run scripts in the environment:** prefix commands with `poetry run` (e.g.
   `poetry run python run_scenarios.py`), or activate the environment with the command that
   `poetry env activate` prints. (`poetry shell` is a plugin since Poetry 2.)

4. **Install Gurobi and its license:**
   - Pyomo calls Gurobi through Gurobi's command-line launcher (`gurobi.bat` on Windows,
     `gurobi.sh` on Linux), so install the full Gurobi distribution and make sure its `bin`
     folder is on `PATH`. The Python package `gurobipy` is not needed for local runs.
   - Place your `gurobi.lic` file in the appropriate directory, or set the `GRB_LICENSE_FILE`
     environment variable.

### Installation on HPC Clusters

Two clusters are supported. Pick the one you use:

#### ETH Euler (from scratch)

This walkthrough assumes you have an ETH nethz account and SSH access to `euler.ethz.ch`. Read every step; the Poetry-on-Euler setup has a few non-obvious quirks and skipping any of them will cost you hours later.

1. **Clone the repository into `~/repos/Future_Markets`:**

   ```bash
   mkdir -p ~/repos && cd ~/repos
   git clone https://github.com/alidrd/Future_Markets.git
   cd Future_Markets
   ```

2. **Set up `~/.bashrc` once.** Use this to configure your interactive Euler shell with the modules and environment variables needed for this project. Batch jobs should still load required modules and re-declare needed environment variables explicitly, because non-login SLURM shells may not source `~/.bashrc` automatically. Append the following block:

   ```bash
   # ---- FEM model: Euler setup ----
   # Cluster modules
   module load stack/2024-06
   module load python/3.11.6
   module load gurobi/10.0.3
   # Make user-local binaries (Poetry, etc.) findable
   export PATH="$HOME/.local/bin:$PATH"
   # Poetry storage — venv on $HOME (persistent, ~45 GB quota), cache on
   # scratch (re-downloadable, fine to purge). Without these, Poetry's
   # default location ends up on scratch and gets wiped after 15 days.
   export POETRY_VIRTUALENVS_PATH="$HOME/.poetry_venvs"
   export POETRY_CACHE_DIR="/cluster/scratch/$USER/.poetry_cache"
   export POETRY_VIRTUALENVS_IN_PROJECT=false
   export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
   ```

   Then reload:

   ```bash
   source ~/.bashrc
   ```

3. **Install Poetry (one-time).** Skip if `poetry --version` already prints a version.

   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   poetry --version   # should print something like "Poetry (version 2.x.x)"
   ```

4. **Tell Poetry not to inherit system-site-packages.** Without this, Poetry's `install` step on Euler will try to uninstall numpy from the read-only `python/3.11.6` module directory and crash with `PermissionError`. Run from inside the repo:

   ```bash
   cd ~/repos/Future_Markets
   poetry config virtualenvs.options.system-site-packages false --local
   ```

   This writes a small `poetry.toml` file in the repo. It is gitignored on purpose — the setting is per-user (it only matters on Euler, where the cluster's Python module is read-only), so each user re-runs this step on a fresh clone instead of inheriting a committed file.

5. **Install project dependencies (one-time, interactive only).** Takes 5–10 minutes the first time as wheels are downloaded and compiled.

   ```bash
   poetry install --no-interaction --no-root
   ```

   **Do this interactively, not from inside a SLURM array job.** Array tasks all race to create the venv simultaneously and corrupt it. See the [troubleshooting note](#troubleshooting-on-euler) at the end of this section if you ever need to recover.

6. **Verify the environment.** Both lines should succeed:

   ```bash
   poetry run python -c "import gurobipy; print('gurobipy', gurobipy.gurobi.version(), 'OK')"
   du -sh $HOME/.poetry_venvs/  # expect ~500 MB
   lquota                        # confirm you're well under the 45 GB home quota
   ```

   If the `gurobipy` line prints a version tuple followed by `OK`, you're done. SLURM jobs will inherit the same modules and Poetry env vars and use this venv automatically.

7. **(Required for parallel runs) Redirect outputs to scratch and logs to a dedicated home folder.** Run once:

   ```bash
   bash cluster_runs/setup_euler_scratch.sh
   ```

   This idempotent script:

   - Creates `~/logs_FEM/` for SLURM `.out`/`.err` files (small, on home — kept across runs)
   - Creates `/cluster/scratch/$USER/FEM/output/` for model outputs (large, on scratch — purged every 15 days)
   - Replaces `<repo>/output/` with a symlink to the scratch location

   If `<repo>/output/` already has content, the script prompts before moving it. Use `-y` to auto-accept.

   After this, every model script (`run_scenarios.py`, `aggregate_results.py`, `visualization_class.py`, etc.) writes to `output/<scenario>/` transparently — the OS follows the symlink so writes land on scratch and your home quota stays flat.

   > **Note:** The symlink is fully transparent to Python's file operations — reads work exactly like writes. `aggregate_results.py` and `visualization_class.py` can be used as normal since they discover and read results from `output/` as in a local run; no additional changes or path adjustments are needed.

   **Caveat:** scratch is purged after 15 days of file inactivity. Pull important results off `/cluster/scratch/$USER/FEM/output/` to your laptop, ETH Polybox, or a group `/cluster/project/...` space before then. SLURM logs in `~/logs_FEM/` are never purged.

   The parallel-execution script (`cluster_runs/parallel_runs_Euler.sh`) refuses to submit unless this setup has been done, so a forgetful user gets a clear error instead of writing outputs back onto home.

#### SciCORE (University of Basel)

1. **Clone the repository:**

   ```bash
   git clone https://github.com/alidrd/Future_Markets.git
   cd Future_Markets
   ```

2. **Install Poetry (one-time):**

   ```bash
   # Check available Python modules first:
   module avail python
   # Then load the appropriate version, e.g.:
   module load Python/3.11.3-GCCcore-12.3.0
   curl -sSL https://install.python-poetry.org | python3 -

   # Verify Poetry installation:
   ls -la ~/.local/bin/poetry
   poetry --version
   ```

3. **Install project dependencies:**

   ```bash
   poetry install --no-root
   ```

   The lock file is written by Poetry 2. If `poetry install` rejects it, use the Poetry
   installed in step 2 rather than an older `poetry` module.

4. **Ensure required modules in `~/.bashrc`:**

   For SLURM jobs to work properly, make sure your `~/.bashrc` contains all necessary modules:

   ```bash
   # Required lines in ~/.bashrc:
   module purge # Perhaps not necessary
   module load Python/3.11.3-GCCcore-12.3.0
   module load poetry/1.5.1-GCCcore-12.3.0
   module load Gurobi/11.0.0-GCCcore-12.3.0
   source /scicore/soft/easybuild/apps/Gurobi/11.0.0-GCCcore-12.3.0/bin/gurobi.sh
   export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
   ```

   **Note:** SLURM jobs inherit your `.bashrc` environment, so modules loaded there will be available in parallel jobs automatically.

   The repository has no SciCORE job script: `cluster_runs/parallel_runs_Euler.sh` loads Euler
   modules and expects the repository at `~/repos/Future_Markets`, so adapt a copy of it.

## Usage

### Basic Scenario Execution

**Run all scenarios sequentially:**

```bash
python run_scenarios.py
```

**Aggregate the results of various scenarios to one folder** (first set `scenarios_to_agg`
and `agg_name` at the top of the script; writes `output/aggregated/<agg_name>/`):

```bash
python aggregate_results.py
```

**Visualize the results of one or various scenarios in different plots** (first set
`scenarios_to_plot` at the top of the script; writes to `plots/`):

```bash
python visualization_class.py
```

**Modify scenarios:**

- The `target_csv =` line in `scenarios/scenarios.py` selects the scenario file
  (default `scenarios/scen_to_run_STORSUPPORT.csv`)
- Rows are settings, columns are sub-scenarios; a `sub_secn` row is required, and columns with
  the same name form one optimisation (e.g. several weather years with shared investment)
- Settings not in the file take their value from `scenarios/settings_default.py`
- Details, the quick test run and the unit tests: [docs/running.md](docs/running.md)

### Parallel Execution on HPC Clusters

For running multiple scenarios in parallel:

**Prerequisite (Euler only):** if you haven't already, run `bash cluster_runs/setup_euler_scratch.sh` once. The job script will refuse to submit otherwise.

1. **Confirm the scenario count:**

   ```bash
   python cluster_runs/get_scenario_names.py
   ```

   Note the total number of scenarios printed.

2. **Update the SLURM array bounds.** Edit `cluster_runs/parallel_runs_Euler.sh` and set `#SBATCH --array=0-N` where `N = (total scenarios − 1)`. No other paths in the script need editing — it points at `~/repos/Future_Markets` by default.

3. **Submit the job:**

   ```bash
   sbatch cluster_runs/parallel_runs_Euler.sh
   ```

4. **Monitor execution:**

   ```bash
   squeue -u $USER                       # queue + per-task status
   tail -f ~/logs_FEM/myrun_<jobid>_0.out # live log of array task 0
   ```

   On Euler, log files will be stored in `~/logs_FEM` (as set in `cluster_runs/parallel_runs_Euler.sh`) `myrun_<jobid>_<arrayid>.out` and `.err`.

See `cluster_runs/parallel_runs_Euler.sh` for the full SLURM configuration. The script does **not** run `poetry install` — it relies on the venv prepared during initial setup. If the venv is missing or broken, the job will fail fast with a clear error message pointing to the recovery steps below.

#### Troubleshooting on Euler

**Symptom:** the job fails immediately with `ModuleNotFoundError: No module named 'gurobipy'`, or with `[Errno 17] File exists: '.../future-markets-*/bin'`.

**Cause:** the Poetry venv is partially corrupted — typically from an interrupted install, or from a previous attempt to run `poetry install` inside an array job (which races across tasks).

**Recovery:** nuke and rebuild interactively.

```bash
rm -rf ~/.poetry_venvs/future-markets-*
cd ~/repos/Future_Markets
poetry install --no-interaction --no-root
poetry run python -c "import gurobipy; print(gurobipy.gurobi.version())"
```

Then resubmit `sbatch cluster_runs/parallel_runs_Euler.sh`.

### Output and Results

Each run writes `output/<scenario>/`:

- **Every model variable and indexed parameter** as a long-format CSV (dispatch, capacities,
  storage levels, inputs)
- **Duals** (`*_dual.csv`, e.g. electricity and district-heat prices) and **reduced costs** of
  investment variables (`*_reduced_cost.csv`)
- **Cost breakdowns** (`cost_*_dict.csv`), `investment_summary.csv` (Swiss plants),
  `settings.csv`, `statistics.csv` and the solver log

Plots from `visualization_class.py` and the dashboard data go to `plots/`. How to read the files:
[docs/outputs.md](docs/outputs.md) and [docs/duals.md](docs/duals.md).

## Project Structure

```
├── model/                    # The optimization model
│   ├── core.py              # Run orchestration: build, solve, export
│   ├── components_common.py # Sets, parameters, variables, constraints, objective
│   ├── components_central.py # Electrolyzer, winter-import and Swiss RES-target constraints
│   ├── constraint_scaling.py # Row-scaling factors per constraint
│   └── data_import_fcns.py  # Input data readers
├── scenarios/                # Scenario definitions and settings
│   ├── scenarios.py         # Reads the scenario CSV named in target_csv
│   ├── scen_to_run_*.csv    # Scenario parameter files
│   └── settings_default.py  # Default parameter values
├── data_prep/                # Data import and preprocessing
├── input/                    # Input data files
├── run_scenarios.py          # Sequential scenario runner
├── run_scenarios_hpc.py      # Single-scenario runner for SLURM arrays
├── cluster_runs/             # Euler job script and setup
├── aggregation/              # Result export during the run (results_export.py) and aggregation
├── aggregate_results.py      # Combine several runs
├── visualization_class.py    # Plots of one or several runs
├── visualization/            # Further plotting helpers
├── plot_creators/            # Standalone plotting scripts
├── tools/prepare_viewer.py   # Converter for the standalone dashboard
├── viewer.html               # Standalone dashboard
├── detailed_reporting/       # Optional post-hoc reports
├── tests/                    # Unit tests (pytest)
├── utils/                    # Helper functions
├── docs/                     # Guides
└── output/                   # Results (gitignored)
```

## Key Model Components

### Technologies Modeled

- **Renewable**: Solar PV, wind (onshore/offshore), hydro, biomass
- **Conventional**: Natural gas, nuclear, coal, oil
- **Storage**: Batteries, pumped hydro, thermal storage
- **Flexibility**: Demand response, electric vehicles (V2G)
- **Heating**: Heat pumps, district heating, thermal storage, boilers
- **Power-to-X**: Electrolyzers, synthetic fuel production

### Geographic Scope

- **Detailed Swiss model** with large region resolution
- **European context** using TYNDP 2022 data
- **Cross-border trading** with neighboring countries
- **Transmission constraints** and grid limitations

### Time Resolution

- **Hourly optimization** for full years
- **Multiple weather years** (1995, 2008, 2009) for robustness
- **Long-term scenarios** (2035, 2050) for investment planning

## Configuration

### Main Configuration Files

- `scenarios/settings_default.py` - Default model parameters
- `scenarios/scen_to_run_*.csv` - Scenario-specific parameters
- `pyproject.toml` - Python dependencies and project metadata

### Key Parameters

- **Weather years**: Historical weather data for renewable generation
- **Technology costs**: Investment and operational costs by year
- **Policy settings**: RES targets, CO2 constraints, fuel import limits
- **Grid parameters**: Transmission capacities, efficiency factors

## Visualization

The model includes comprehensive visualization capabilities:

- **Dispatch plots**: Hourly generation and demand
- **Investment results**: Technology capacity additions
- **Energy balances**: Annual generation/consumption by technology
- **Price analysis**: Electricity and heat price patterns
- **Interactive HTML plots** with Plotly for detailed analysis

### Standalone Results Dashboard (`viewer.html`)

A self-contained, dependency-free dashboard for exploring a single solved run.
Two parts:

1. **Converter** — packs one run's outputs into a compact gzipped JSON
   (written to `plots/`, gitignored):

   ```bash
   python tools/prepare_viewer.py output/<run_name>      # one run
   python tools/prepare_viewer.py output --all           # every run in output/
   python tools/prepare_viewer.py output/<run> --out-dir plots --sub-scenario <name>
   ```

   Produces `plots/<run_name>_viewer.json.gz` (a few MB for a full-year run). Missing output
   files are warned about and skipped; the converter checks that the zonal
   energy balance closes after its technology grouping.

2. **Viewer** — open `viewer.html` in any modern browser (no server, no
   installation, no internet; the file can be e-mailed) and drag the
   `*_viewer.json.gz` onto it.

The converter expects a full-year run: short test runs convert, but the annual views stay
mostly empty. For a run with several sub-scenarios it takes the first unless
`--sub-scenario <Scenarios value>` is given, and it shows duals as exported, so prices of a
multi-weather-year run appear multiplied by the sub-scenario weight
([docs/duals.md](docs/duals.md)).

Dashboard contents:

- **Headline KPIs**: system cost, CH prices, net imports, RES share,
  curtailment, CO2, new capacity, district-heat price
- **Annual heatmap** (hour × day): price, residual load, net imports, storage
  output, curtailment — click any cell to open the day
- **Dispatch stacks**: daily mean over the year and hourly day detail, with
  load overlay and click-to-toggle legends
- **Day drill-down**: hourly dispatch, zonal prices, border flows with
  NTC-binding markers, storage state of charge, district-heat panel
- **Prices**: duration curves, monthly means, per-zone statistics
- **Cross-border exchange**: CH border schematic, congestion ranking
  (share of hours the NTC binds), full line table. Unless the run used
  `DUALS_EXPORT_ALL = True` (which exports the transmission-limit duals), the
  maximum observed flow is shown as the NTC estimate (`NTC*`)
- **Storage**: seasonal state of charge (absolute or % of capacity), cycling
  statistics
- **Capacity & investment**: pre-existing vs. newly built per zone/technology
- **Curtailment & scarcity**: monthly curtailment by zone, lost-load events
- **District heating**: heat price, dispatch, TES state of charge and
  capacities per DH node

All annual views follow the model's hydrological year (October–September,
see `input/timemaps_hydro_year.csv`).

## Contributing

1. Create feature branches for new developments
2. Follow existing code structure and naming conventions
3. Write unit tests in `tests/` for new or changed code; run them with `poetry run pytest`
4. Check model changes with the quick test run before large-scale runs ([docs/running.md](docs/running.md))
5. Update the guides in `docs/` when you change behaviour they describe

## Citation

If you use this model in your research, please cite:

```
[Add appropriate citation information]
```

## License

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE.txt](LICENSE.txt) file for details.

### Key Points of GPL-3.0:

- ✅ **Freedom to use** the software for any purpose
- ✅ **Freedom to study** and modify the source code
- ✅ **Freedom to share** copies with others
- ✅ **Freedom to distribute** your modified versions
- ⚠️ **Copyleft**: Derivative works must also be licensed under GPL-3.0
- ⚠️ **No warranty**: Software is provided "as is"

For more information about GPL-3.0, visit: https://www.gnu.org/licenses/gpl-3.0.html

## Contact

David Holmer
david.holmer@zhaw.ch
david.holmer@unibas.ch

## Acknowledgments

- **Unibas** for computational resources (SciCore)
- **ETH Zurich** for computational resources (Euler cluster)
- **TYNDP** for European transmission system data
- **Swiss Federal Office of Energy (BFE)** for Swiss energy data
- **Gurobi Optimization** for academic licenses
