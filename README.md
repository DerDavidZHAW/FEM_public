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

- **Python 3.10.5**
- **Poetry** for dependency management
- **Gurobi license** (academic license available)

### Local Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/DerDavidZHAW/FEM_public.git
   cd FEM_public
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

### Installation on HPC Clusters (Euler/SciCORE)

1. **Clone the repository:**

   ```bash
   git clone https://github.com/DerDavidZHAW/FEM_public.git
   cd FEM_public
   ```

2. **Check if Poetry is available, install if needed:**

   **First, try to see if Poetry is already installed:**

   ```bash
   poetry --version
   ```

   **If Poetry is not found, install it (one-time setup):**

   **On Euler (ETH Zurich):**

   ```bash
   # If your .bashrc already has module load commands for stack and python,
   # they're automatically loaded on login - you don't need to run them again.
   # Just install Poetry directly:

   curl -sSL https://install.python-poetry.org | python3 -

   # Poetry will be installed to ~/.local/bin/poetry (as a symbolic link)
   # Your .bashrc already has: export PATH="$HOME/.local/bin:$PATH"
   # So Poetry will be available automatically on next login

   # Verify Poetry installation:
   ls -la ~/.local/bin/poetry
   poetry --version
   ```

   **On SciCORE (University of Basel):**

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

   **Note:**

   - `stack/2024-06` sets up the software environment (base libraries, compilers, etc.)
   - Check your `~/.bashrc` file to see which exact module versions you have loaded
   - Poetry installs as a symbolic link to `~/.local/share/pypoetry/venv/bin/poetry`

3. **Install project dependencies:**

   ```bash
   poetry install
   poetry shell
   ```

4. **Ensure required modules in ~/.bashrc:**

   For SLURM jobs to work properly, make sure your `~/.bashrc` contains all necessary modules:

   **On Euler (ETH Zurich):**

   ```bash
   # Required lines in ~/.bashrc:
   module load stack/2024-06
   module load python/3.11.6
   module load gurobi/10.0.3
   export PATH="$HOME/.local/bin:$PATH"  # For Poetry
   ```

   **On SciCORE (University of Basel):**

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

For running multiple scenarios in parallel on HPC clusters (Euler/SciCORE):

1. **Analyze scenarios:**

   ```bash
   python cluster_runs/get_scenario_names.py
   ```

2. **Update SLURM script paths:**

   Edit `cluster_runs/parallel_runs.sh` and update the project path:

   ```bash
   cd ~/Models/FEM_public  # Change this to your actual project location
   ```

3. **Update SLURM array bounds:**

   Based on the scenario count, update the `#SBATCH --array=0-N` line in your SLURM script (where N = total scenarios - 1)

4. **Submit parallel jobs:**

   ```bash
   cd cluster_runs
   sbatch parallel_runs.sh
   ```

5. **Monitor execution:**
   ```bash
   squeue -u $USER
   ```

See the `cluster_runs/parallel_runs.sh` script for the SLURM job configuration.

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
