"""Per-scenario district-heating (DH) demand adjustment overlay.

A wide CSV of signed MW deltas — keyed by NodeDH (rows) x hour label t_1..t_8760
(columns) — is added to the assembled DH demand, so a modeller can perturb the
demand of chosen NodeDH over chosen periods for scenario testing (see PRD #43).

Two layers:
  * load_dh_adjustment_file  (M2) — thin I/O: resolve the filename and read it.
  * apply_dh_demand_adjustment (M1) — pure function over plain data structures,
    so every rule is unit-testable without files or settings.

Deltas are added to the matching (NodeDH, hour); rows/columns absent from the
file leave demand unchanged (partial files are allowed). Validation is strict
(no silent fallback): a present row/column label that is not a real NodeDH /
t_1..t_8760, a delta that would drive demand negative, or use together with the
global reduce_DH_demand_by_[MWh] knob, all raise. The compact generator that
writes these wide files is #46.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# Adjustment files live alongside the demand inputs, in their own subfolder.
# Resolved relative to the run's working directory (the repo root), exactly like
# the demand-profile paths in read_demandDH_data.
ADJUSTMENTS_DIR = Path("input/demand/adjustments")

# Tolerance for the "demand must stay >= 0" check, to ignore float noise at an
# intended exact-zero reduction (e.g. demand 50 + delta -50).
_NEG_TOL = 1e-9


def load_dh_adjustment_file(setting):
    """M2 (thin I/O).

    `setting` is either ``False`` (feature off) or an adjustment-CSV filename.
    Returns ``None`` when the feature is off, otherwise the wide adjustment table
    (index = NodeDH, columns = t_1..t_8760, values = signed MW deltas).

    Raises FileNotFoundError if a filename is given but the file is absent.
    """
    if setting is False or setting is None or setting == "":
        return None
    path = ADJUSTMENTS_DIR / str(setting)
    if not path.is_file():
        raise FileNotFoundError(
            f"DH_demand_adjustment_file='{setting}' is set but no such file at "
            f"'{path}'. Put the adjustment CSV in '{ADJUSTMENTS_DIR}/'."
        )
    return pd.read_csv(path, index_col=0)


def apply_dh_demand_adjustment(demand, adjustment_df, valid_nodes, valid_hours,
                               reduce_DH_demand_by=0):
    """M1 (pure). Add the signed MW deltas in `adjustment_df` to `demand`.

    Parameters
    ----------
    demand : dict[(NodeDH, hour_label) -> MW]
        Assembled DH demand. A copy is returned; the input is not mutated.
    adjustment_df : pandas.DataFrame | None
        Wide table of signed MW deltas, or ``None`` when the feature is off
        (in which case `demand` is returned unchanged).
    valid_nodes : set[str]
        NodeDH labels present in `demand`.
    valid_hours : set[str]
        Hour labels present in `demand`.
    reduce_DH_demand_by : float
        Value of the global reduce_DH_demand_by_[MWh] knob. The overlay and that
        knob are mutually exclusive; both active raises.

    Returns the adjusted demand dict. Rows/columns absent from the table leave
    those nodes/hours unchanged.

    Raises ValueError, naming the offender, if: `reduce_DH_demand_by` is active
    together with an adjustment table; a row label is not a known NodeDH; a
    column label is not a valid hour; or a delta drives any demand negative.
    """
    if adjustment_df is None:
        return demand

    # The overlay and the global reduce_DH_demand_by_[MWh] knob are competing
    # ways to change DH demand; refuse to apply both in one scenario.
    if reduce_DH_demand_by:
        raise ValueError(
            "DH demand adjustment file and reduce_DH_demand_by_[MWh] are mutually "
            f"exclusive, but both are active (reduce_DH_demand_by={reduce_DH_demand_by}). "
            "Use one DH-demand mechanism per scenario."
        )

    # Every row/column label that is present must be valid; absent ones are left
    # unchanged (partial files are allowed).
    bad_nodes = [str(n) for n in adjustment_df.index if str(n) not in valid_nodes]
    if bad_nodes:
        raise ValueError(
            f"DH demand adjustment file has unknown NodeDH row(s): {bad_nodes}. "
            "Rows must be existing district-heating nodes (DH_*, ILLT_*, ILHT_*)."
        )
    bad_hours = [str(c) for c in adjustment_df.columns if str(c) not in valid_hours]
    if bad_hours:
        shown = bad_hours[:5] + (["..."] if len(bad_hours) > 5 else [])
        raise ValueError(
            f"DH demand adjustment file has unknown hour column(s): {shown}. "
            "Columns must be hour labels t_1..t_8760."
        )

    adjusted = dict(demand)
    per_node_delta = {}
    touched_hours = set()
    for node, row in adjustment_df.iterrows():
        node = str(node)
        for hour, delta in row.items():
            hour = str(hour)
            if pd.isna(delta) or delta == 0:   # blank / 0 -> no change
                continue
            delta = float(delta)
            new_value = adjusted[(node, hour)] + delta
            if new_value < -_NEG_TOL:
                raise ValueError(
                    f"DH demand adjustment drives {node} {hour} negative: "
                    f"{adjusted[(node, hour)]:.4g} + ({delta:.4g}) = {new_value:.4g}. "
                    "Reduce the magnitude of the cut."
                )
            adjusted[(node, hour)] = new_value
            per_node_delta[node] = per_node_delta.get(node, 0.0) + delta
            touched_hours.add(hour)

    _print_summary(per_node_delta, len(touched_hours))
    return adjusted


def _print_summary(per_node_delta, n_hours):
    """One-line sanity log of what the overlay applied."""
    if not per_node_delta:
        print("[DH demand adjustment] file applied but no matching (NodeDH, hour) "
              "deltas — nothing changed.")
        return
    parts = ", ".join(f"{node} {delta:+,.0f} MWh"
                      for node, delta in sorted(per_node_delta.items()))
    print(f"[DH demand adjustment] applied over {n_hours} h: {parts}")
