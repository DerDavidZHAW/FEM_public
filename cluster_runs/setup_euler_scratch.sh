#!/bin/bash
# One-time per-user setup for running FEM on ETH Euler with outputs on
# scratch and SLURM logs on home.
#
# What this does (all idempotent — safe to re-run):
#   1. Creates ~/logs_FEM/                              (for SLURM .out/.err files)
#   2. Creates /cluster/scratch/$USER/FEM/output/       (for model outputs)
#   3. Replaces <repo>/output/ with a symlink to (2)
#
# Why: home has a 45 GB quota; per-run model outputs can be GBs and fill
# it up fast. Scratch has 2.5 TB but is purged after 15 days of file
# inactivity. SLURM logs are tiny so they stay on home.
#
# Usage:
#   bash cluster_runs/setup_euler_scratch.sh        # interactive (prompts before moving existing files)
#   bash cluster_runs/setup_euler_scratch.sh -y     # non-interactive (auto-accept)

set -e

# --- Resolve paths ---------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOGS_DIR="$HOME/logs_FEM"
SCRATCH_OUTPUT="/cluster/scratch/$USER/FEM/output"
REPO_OUTPUT="$REPO_ROOT/output"

AUTO_YES=0
if [ "${1:-}" = "-y" ]; then
    AUTO_YES=1
fi

echo "=== FEM Euler scratch setup ==="
echo "Repo root:        $REPO_ROOT"
echo "Logs (home):      $LOGS_DIR"
echo "Output (scratch): $SCRATCH_OUTPUT"
echo

# --- 1. Logs directory on home --------------------------------------------
if [ -d "$LOGS_DIR" ]; then
    echo "[ok]      $LOGS_DIR already exists"
else
    mkdir -p "$LOGS_DIR"
    echo "[created] $LOGS_DIR"
fi

# --- 2. Output directory on scratch ---------------------------------------
if [ -d "$SCRATCH_OUTPUT" ]; then
    echo "[ok]      $SCRATCH_OUTPUT already exists"
else
    mkdir -p "$SCRATCH_OUTPUT"
    echo "[created] $SCRATCH_OUTPUT"
fi

# --- 3. Symlink <repo>/output -> scratch ----------------------------------
if [ -L "$REPO_OUTPUT" ]; then
    target="$(readlink -f "$REPO_OUTPUT")"
    if [ "$target" = "$SCRATCH_OUTPUT" ]; then
        echo "[ok]      $REPO_OUTPUT already symlinked to $SCRATCH_OUTPUT"
    else
        echo "[warn]    $REPO_OUTPUT is a symlink, but points to: $target"
        echo "          Expected: $SCRATCH_OUTPUT"
        echo "          Leaving as-is. If you want to re-link, delete the symlink and re-run."
    fi
elif [ -d "$REPO_OUTPUT" ]; then
    if [ -z "$(ls -A "$REPO_OUTPUT" 2>/dev/null)" ]; then
        rmdir "$REPO_OUTPUT"
        ln -s "$SCRATCH_OUTPUT" "$REPO_OUTPUT"
        echo "[linked]  $REPO_OUTPUT -> $SCRATCH_OUTPUT (directory was empty)"
    else
        n_entries=$(find "$REPO_OUTPUT" -mindepth 1 -maxdepth 1 | wc -l)
        size=$(du -sh "$REPO_OUTPUT" | cut -f1)
        echo
        echo "[needs decision] $REPO_OUTPUT contains $n_entries top-level entries ($size total)."
        echo "                 To proceed I will:"
        echo "                   1. Move every entry to $SCRATCH_OUTPUT"
        echo "                   2. Remove the now-empty $REPO_OUTPUT directory"
        echo "                   3. Replace it with a symlink to $SCRATCH_OUTPUT"
        echo "                 Move will fail if a name collides with something already on scratch."
        if [ "$AUTO_YES" -eq 1 ]; then
            answer="y"
            echo "                 -y flag: auto-accepting."
        else
            read -r -p "                 Proceed? [y/N]: " answer
        fi
        case "$answer" in
            y|Y|yes|YES)
                # mv across filesystems = copy + delete, can take a while
                echo "                 moving (this may take a few minutes if there's a lot)..."
                shopt -s dotglob nullglob
                entries=("$REPO_OUTPUT"/*)
                if [ ${#entries[@]} -gt 0 ]; then
                    mv "${entries[@]}" "$SCRATCH_OUTPUT"/
                fi
                shopt -u dotglob nullglob
                rmdir "$REPO_OUTPUT"
                ln -s "$SCRATCH_OUTPUT" "$REPO_OUTPUT"
                echo "[linked]  $REPO_OUTPUT -> $SCRATCH_OUTPUT"
                ;;
            *)
                echo
                echo "Aborted. $REPO_OUTPUT is unchanged. Re-run this script after moving the content yourself."
                exit 1
                ;;
        esac
    fi
else
    ln -s "$SCRATCH_OUTPUT" "$REPO_OUTPUT"
    echo "[linked]  $REPO_OUTPUT -> $SCRATCH_OUTPUT (directory was missing)"
fi

# --- 4. Summary -----------------------------------------------------------
echo
echo "=== Setup complete ==="
ls -ld "$REPO_OUTPUT"
echo "SLURM logs from sbatch will land in: $LOGS_DIR"
echo
echo "Reminder: scratch is purged after 15 days of file inactivity."
echo "          Pull important results off $SCRATCH_OUTPUT before then."
