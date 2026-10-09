# DH demand adjustment files

Per-scenario overlays that add signed MW deltas to the assembled district-heating
demand, for scenario testing over chosen periods.

## How to activate

Set the scenario setting `DH_demand_adjustment_file` to a filename in this folder
(or `False` to disable, the default):

```
DH_demand_adjustment_file,False,week1_jan_cut.csv
```

Working example: `scenarios/scen_to_run_dh_ab.csv` with `week1_jan_cut.csv` in this folder.
A filename that does not exist here raises `FileNotFoundError`.

## File format

A **wide** CSV, same shape as the `DH_*_profiles_*` demand inputs:

- **Rows** — final `NodeDH` names: `DH_*`, `ILLT_*`, `ILHT_*`.
- **Columns** — hour labels `t_1 … t_8760` (weather-year calendar, `t_1` = Jan 1).
- **Cells** — a signed MW delta added directly to that `(NodeDH, hour)`:
  negative reduces demand, positive adds it. `0`/blank means no change.

Partial files are allowed: include only the rows/columns you change; everything
absent is left as the original profile. A window that wraps the calendar year
(e.g. late Dec → early Jan) is just the union of the relevant `t_x` columns —
for example `t_8655 … t_8760` plus `t_1 … t_182`.

```
NodeDH,t_1,...,t_8700,...,t_8760
DH_medium,0,...,-50,...,0
DH_Mittelland,0,...,-120,...,0
```

## Validation

The run stops with a `ValueError` naming the problem when:

- a row label is not a district-heating node of the run, or a column label is not an hour
  `t_1 … t_8760`;
- a delta would make demand negative in any hour;
- the scenario also sets `reduce_DH_demand_by_[MWh]` to a non-zero value (use one of the two).

## Generator

Build files from compact `(node, start-hour, end-hour, amount)` instructions with
`utils/make_dh_adjustment.py`; it writes into this folder:

```bash
# one node, one window
python utils/make_dh_adjustment.py --out jan_cut.csv --add DH_medium t_223 t_510 -50
# a window wrapping over New Year, two nodes
python utils/make_dh_adjustment.py --out dec_cut.csv --add DH_medium t_8655 t_182 -50 --add DH_Mittelland t_8655 t_182 -120
# many instructions from a CSV with columns node,t_start,t_end,amount
python utils/make_dh_adjustment.py --out exp.csv --instructions instr.csv
```

Tests: `tests/test_dh_demand_adjustment.py`, `tests/test_make_dh_adjustment.py`.
