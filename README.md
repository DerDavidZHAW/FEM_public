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
   poetry install
   ```

3. **Activate the environment:**

   ```bash
   poetry shell
   ```

4. **Configure Gurobi license:**
   - Place your `gurobi.lic` file in the appropriate directory
   - Or set the `GRB_LICENSE_FILE` environment variable

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
   poetry --version   # should print something like "Poetry (version 1.x.x)"
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
   poetry install
   poetry shell
   ```

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

## Usage

### Basic Scenario Execution

**Run all scenarios sequentially:**

```bash
python run_scenarios.py
```

**Aggregate the results of various scenarios to one folder:**

```bash
python aggregate_results.py
```

**Visualize the results of one or various scenarios in different plots:**

```bash
python visualization_class.py
```

**Modify scenarios:**

- Edit `scenarios/scen_to_run_STORSUPPORT.csv` to define your scenarios
- Each column represents a scenario with different parameter combinations
- Parameters include weather years, policy settings, technology costs, etc.

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

Results are saved in the `output/` directory:

- **CSV files** with detailed time series data
- **Investment results** and capacity additions
- **Energy balances** and dispatch schedules
- **Economic indicators** (costs, prices, revenues)
- **Interactive HTML plots** for visualization

## Project Structure

```
├── scenarios/                 # Scenario definitions and settings
│   ├── scenarios.py          # Main scenario processing logic
│   ├── scen_to_run_*.csv    # Scenario parameter files
│   └── settings_default.py   # Default parameter values
├── data_prep/                # Data import and preprocessing
├── input/                    # Input data files
├── core.py                   # Main optimization model
├── run_scenarios.py          # Sequential scenario runner
├── cluster_runs/             # Parallel execution scripts for Euler
├── visualization/            # Plotting and analysis tools
├── aggregation/              # Result aggregation utilities
├── utils/                    # Helper functions
└── output/                   # Results and outputs
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

## Contributing

1. Create feature branches for new developments
2. Follow existing code structure and naming conventions
3. Update documentation for new features
4. Test changes with small scenarios before large-scale runs

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
