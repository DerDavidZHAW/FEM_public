"""Generator for DH demand adjustment files (PRD #43, see also model/dh_demand_adjustment.py).

Turns compact ``(node, start-hour, end-hour, amount)`` instructions into the
wide signed-MW-delta CSV consumed by the overlay, so you never hand-edit a
15 x 8760 grid.

The pure core ``build_adjustment_frame`` does the expansion (incl. hydro-year
wrap-around) and is unit-tested in isolation; the ``main`` CLI is a thin wrapper
that reads instructions and writes the file into input/demand/adjustments/.

Examples
--------
    # one node, one in-year window
    python utils/make_dh_adjustment.py --out jan_cut.csv \
        --add DH_medium t_223 t_510 -50

    # a wrap-around window (late Dec -> early Jan) + a second node
    python utils/make_dh_adjustment.py --out dec_cut.csv \
        --add DH_medium t_8655 t_182 -50 \
        --add DH_Mittelland t_8655 t_182 -120

    # many instructions from a tidy CSV (columns: node,t_start,t_end,amount)
    python utils/make_dh_adjustment.py --out exp.csv --instructions instr.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def all_hour_labels(n_hours=8760):
    """Ordered hour labels t_1 .. t_n (the weather-year calendar; t_1 = Jan 1)."""
    return [f"t_{i}" for i in range(1, n_hours + 1)]


def build_adjustment_frame(instructions, all_hours):
    """Expand instructions into a wide adjustment DataFrame.

    Parameters
    ----------
    instructions : iterable of (node, start_hour, end_hour, amount)
        Inclusive window [start_hour, end_hour]. If the start label is *after*
        the end label in `all_hours`, the window wraps the year boundary
        (e.g. t_8655 -> t_182 covers t_8655..t_8760 then t_1..t_182).
    all_hours : list[str]
        Ordered hour labels (e.g. all_hour_labels(8760)).

    Returns a DataFrame indexed by node (first-seen order), columns = all_hours,
    values = summed signed MW deltas (0 where untouched). Overlapping
    instructions on the same node accumulate. Raises ValueError if a start/end
    label is not in `all_hours`.
    """
    pos = {h: i for i, h in enumerate(all_hours)}
    nodes = []
    for node, *_ in instructions:
        if node not in nodes:
            nodes.append(node)

    arr = np.zeros((len(nodes), len(all_hours)), dtype=float)
    row_of = {n: i for i, n in enumerate(nodes)}
    for node, start, end, amount in instructions:
        if start not in pos:
            raise ValueError(f"unknown start hour label '{start}' (expected t_1..t_{len(all_hours)})")
        if end not in pos:
            raise ValueError(f"unknown end hour label '{end}' (expected t_1..t_{len(all_hours)})")
        i0, i1 = pos[start], pos[end]
        if i0 <= i1:
            cols = range(i0, i1 + 1)
        else:  # wrap the year boundary
            cols = list(range(i0, len(all_hours))) + list(range(0, i1 + 1))
        r = row_of[node]
        for c in cols:
            arr[r, c] += float(amount)

    df = pd.DataFrame(arr, index=nodes, columns=all_hours)
    df.index.name = "NodeDH"
    return df


def _read_instructions_csv(path):
    """Tidy CSV with columns node, t_start, t_end, amount -> list of tuples."""
    df = pd.read_csv(path)
    needed = {"node", "t_start", "t_end", "amount"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"instructions CSV '{path}' missing column(s): {sorted(missing)}")
    return [(str(r.node), str(r.t_start), str(r.t_end), float(r.amount))
            for r in df.itertuples(index=False)]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a wide DH demand adjustment CSV.")
    ap.add_argument("--out", required=True, help="output filename (written into the adjustments dir)")
    ap.add_argument("--add", nargs=4, action="append", metavar=("NODE", "T_START", "T_END", "AMOUNT"),
                    help="one instruction; repeatable")
    ap.add_argument("--instructions", help="tidy CSV with columns node,t_start,t_end,amount")
    ap.add_argument("--hours", type=int, default=8760, help="number of hours (default 8760)")
    ap.add_argument("--out-dir", default=None, help="override the output directory")
    args = ap.parse_args(argv)

    instructions = []
    if args.instructions:
        instructions += _read_instructions_csv(args.instructions)
    for node, t0, t1, amount in (args.add or []):
        instructions.append((node, t0, t1, float(amount)))
    if not instructions:
        ap.error("no instructions given (use --add and/or --instructions)")

    df = build_adjustment_frame(instructions, all_hour_labels(args.hours))

    if args.out_dir is not None:
        out_dir = Path(args.out_dir)
    else:
        # reuse the overlay's directory constant so the two never drift
        from model.dh_demand_adjustment import ADJUSTMENTS_DIR
        out_dir = ADJUSTMENTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / args.out
    df.to_csv(out_path)
    touched = int((df != 0).any(axis=0).sum())
    print(f"wrote {out_path}  ({df.shape[0]} node(s), {touched} non-zero hour(s))")
    return out_path


if __name__ == "__main__":
    main()
