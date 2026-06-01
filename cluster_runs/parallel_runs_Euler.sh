#!/bin/bash
#SBATCH --job-name=FM_short
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=16G
#SBATCH --time=24:00:00
#SBATCH --qos=1day
#SBATCH --output=/cluster/home/%u/logs_FEM/myrun_%A_%a.out
#SBATCH --error=/cluster/home/%u/logs_FEM/myrun_%A_%a.err
#SBATCH --array=0-23   # Update this based on your CSV file
#SBATCH --mail-type=END,FAIL


# Fail fast if the one-time scratch setup wasn't run.
# Note: ~/logs_FEM must exist BEFORE submission too — SLURM opens the .out/.err
# files before the script body runs. If you see this message in stderr only,
# it means logs_FEM exists but output/ isn't symlinked.
if [ ! -d "$HOME/logs_FEM" ] || [ ! -L "$HOME/repos/Future_Markets/output" ]; then
    echo "FATAL: Euler scratch setup is incomplete."
    echo "       Run the one-time setup first:"
    echo "         bash cluster_runs/setup_euler_scratch.sh"
    exit 1
fi

module load stack/2024-06 python/3.11.6 gurobi/10.0.3

# Make Poetry findable on the compute node. Non-login bash doesn't source
# ~/.bashrc, so we can't rely on PATH being set there. Set it here.
export PATH="$HOME/.local/bin:$PATH"

export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
# Venv lives on $HOME (persistent, 45 GB quota) so scratch's 15-day purge
# doesn't wipe it. Cache stays on scratch — it's just downloaded wheels.
export POETRY_VIRTUALENVS_PATH="$HOME/.poetry_venvs"
export POETRY_CACHE_DIR="/cluster/scratch/$USER/.poetry_cache"
export POETRY_VIRTUALENVS_IN_PROJECT=false

cd ~/repos/Future_Markets

# Venv must already exist — do NOT install from inside an array task.
# With --array=0-N, all tasks start simultaneously and race to create the
# same venv directory, corrupting it. Instead, run setup ONCE interactively
# before submitting:
#
#     module load stack/2024-06 python/3.11.6 gurobi/10.0.3
#     export POETRY_VIRTUALENVS_PATH="$HOME/.poetry_venvs"
#     export POETRY_CACHE_DIR="/cluster/scratch/$USER/.poetry_cache"
#     cd ~/repos/Future_Markets
#     poetry install --no-interaction --no-root
#
# Sanity check — fail fast if the venv is missing/broken instead of crashing
# 10 minutes into the model run.
# Fail fast with diagnostic context if something's wrong with poetry/venv/gurobipy.
if ! command -v poetry >/dev/null 2>&1; then
    echo "FATAL: 'poetry' not found on PATH. Compute node PATH was: $PATH"
    echo "       Check that ~/.local/bin/poetry exists, and that this script exports PATH correctly."
    exit 1
fi
if ! poetry run python -c "import gurobipy; gurobipy.gurobi.version()"; then
    echo "FATAL: gurobipy import failed via 'poetry run'."
    echo "       POETRY_VIRTUALENVS_PATH=$POETRY_VIRTUALENVS_PATH"
    echo "       Recover with:"
    echo "         rm -rf ~/.poetry_venvs/future-markets-* && \\"
    echo "         cd ~/repos/Future_Markets && \\"
    echo "         poetry install --no-interaction --no-root"
    echo "       Remember: re-SSH after changing ~/.bashrc so SLURM gets the new env."
    exit 1
fi

# Dynamically get scenario names — redirect stderr to suppress the "Scenarios loaded from..." print
mapfile -t SCENARIOS < <(poetry run python cluster_runs/get_scenario_names.py --names-only 2>/dev/null | grep -v "^Scenarios loaded")

# Print scenario info for debugging
echo "Total scenarios: ${#SCENARIOS[@]}"
echo "Running scenario ${SLURM_ARRAY_TASK_ID}: ${SCENARIOS[$SLURM_ARRAY_TASK_ID]}"

SCENARIO=${SCENARIOS[$SLURM_ARRAY_TASK_ID]}

# Force unbuffered Python output and add timestamps
export PYTHONUNBUFFERED=1
echo "$(date): Starting scenario $SCENARIO"
poetry run python -u run_scenarios_hpc.py --scenario "$SCENARIO"
echo "$(date): Finished scenario $SCENARIO"
