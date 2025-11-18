#!/bin/bash
#SBATCH --job-name=FM_short
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=16G
#SBATCH --time=24:00:00
#SBATCH --qos=1day
#SBATCH --output=myrun_%A_%a.out
#SBATCH --error=myrun_%A_%a.err
#SBATCH --array=0-23   # Update this based on your CSV file


export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
# Change to your project directory - UPDATE THIS PATH!
cd ~/repos/Future_Markets

# Dynamically get scenario names from CSV using existing scenarios.py logic
mapfile -t SCENARIOS < <(python cluster_runs/get_scenario_names.py --names-only)

# Print scenario info for debugging
echo "Total scenarios: ${#SCENARIOS[@]}"
echo "Running scenario ${SLURM_ARRAY_TASK_ID}: ${SCENARIOS[$SLURM_ARRAY_TASK_ID]}"

SCENARIO=${SCENARIOS[$SLURM_ARRAY_TASK_ID]}

# Force unbuffered Python output and add timestamps
export PYTHONUNBUFFERED=1
echo "$(date): Starting scenario $SCENARIO"
poetry run python -u run_scenarios_hpc.py --scenario "$SCENARIO"
echo "$(date): Finished scenario $SCENARIO"
