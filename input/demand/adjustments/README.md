# DH demand adjustment files

Per-scenario overlays that add signed MW deltas to the assembled district-heating
demand, for scenario testing over chosen periods (PRD #43).

## How to activate

Set the scenario setting `DH_demand_adjustment_file` to a filename in this folder
(or `False` to disable, the default):

```
DH_demand_adjustment_file,False,"dec_cut.csv","jan_cut.csv"
#                 scenario:  base      demand-win   price-win
```

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

Hand-editing the wide grid is impractical; use the generator
(`utils/make_dh_adjustment.py`, see #46) to build these from compact
`(node, start-hour, end-hour, amount)` instructions.
