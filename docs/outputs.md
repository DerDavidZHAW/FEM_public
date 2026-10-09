# Output files

Checked against: `main` @ 54d6be28 (2026-10-09).

What a run writes to `output/<meta-scenario>/` and how to read it. Prices and every other dual:
`docs/duals.md`. A rerun of the same meta-scenario overwrites its folder.

## Format

- **Every variable and every indexed parameter** is written as `<name>.csv` in long format: one
  column per index set, then `Scenarios`, then `value` (e.g. `gen.csv`:
  `P_gen,T,Scenarios,value`). Index-set names are the Pyomo set names.
- **`Scenarios`** holds the sub-scenario name `<meta>_<sub_secn>`, e.g. `2050_st_wy1995_aa`.
- **Wide maps.** `Map_node_plant`, `Map_node_importinglineATC`, `Map_node_exportinglineATC`,
  `Map_nodeDH_plantDH`, `Map_fuel_plant`, `Map_week_t` and `Map_week_t_full` have one row per
  key and the members in columns `value,1,2,…`. The other `Map_*` files are two columns.

## Run-level files

| File | Content |
|---|---|
| `settings.csv` | All settings, one column per sub-scenario, plus `model_version` |
| `statistics.csv` | Termination condition, solver status, objective value, solve time, numbers of variables and constraints |
| `solver_log.log` | Gurobi log |
| `weight_in_objective_fcn.csv` | Weight of each sub-scenario in the objective |
| `constraint_scaling.csv` | Row-scaling factor per constraint name (`docs/duals.md`) |
| `cost_inv_dict.csv`, `cost_op_dict.csv`, `cost_inv_thermal_dict.csv`, `cost_op_thermal_dict.csv`, `cost_inv_fuel_storage_dict.csv`, `lostload_cost_dict.csv`, `trade_cost_dict.csv`, `emissions_dict.csv` | Objective terms per plant and sub-scenario (CHF, already multiplied by the sub-scenario weight); emissions in tCO2 |
| `investment_summary.csv` | Swiss plants only: existing and added power, limits, storage, investment cost |
| `*_dual.csv`, `*_reduced_cost.csv` | `docs/duals.md` |
| `large_objective_coefficients.csv` | Only written when an objective coefficient exceeds 1e6 |

## Time

- `T` values `t_1` … `t_8760` are hours of the sub-scenario's **weather-year calendar**:
  `t_1` is 1 January, 00:00.
- A full run covers the **hydrological year**: it starts at `t_6553` (1 October) and wraps to
  `t_6552`. Rows are written in run order, so files start at `t_6553`.
- Weeks, months, seasons (winter = October to March) and day types per hour:
  `input/timemaps_hydro_year.csv`. Annual plots follow the hydrological year.

## Nodes

- **Electric nodes:** 26 (`Node_list_setting` in `scenarios/settings_default.py`). All Swiss
  plants, including the regional ones named `CH01` to `CH07`, belong to node `CH00`.
- **District-heating nodes:** 15 (`NodeDH_list`): `DH_*` networks, `ILLT_*` and `ILHT_*`
  (industrial low and high temperature). Each DH plant's electric connection is in
  `Map_plantDH_nodeEl.csv` (`na` for plants without one).

## Dispatch

- **Electric balance** per node and hour: generation + infeed + imports + lost load = fixed
  demand + inflexible EV and heat-pump demand + charging (`storage_charge`) + exports +
  curtailment.
- **`gen.csv` vs `infeed.csv`.** `gen` is dispatch of plants (incl. storage discharge and Swiss
  RES investment candidates, which are fixed to their availability). `infeed` is exogenous
  renewable infeed per consumer and technology (`pv`, `pvrf`, `ror`, `windon`, `windof`).
- **`storage_charge.csv`** is all flexible electricity consumption (set `P_pumping`): pumped
  hydro and batteries, electrolyzers, EV charging and V2G, demand response, district-heating
  heat pumps and resistive heaters, and building heat-pump archetypes (`minergie_*`, `old_*`,
  `new_*`).
- **`curtailment.csv`** is per consumer zone with no technology split; **`curtailmentTh.csv`**
  per DH node.
- **`lostload.csv`** has a `lostLoad_step` index; step sizes and costs come from
  `input/LostLoadCost/` according to the setting `lost_load_cost_mode`.
- **District heat:** `genTh.csv` (all DH plants), `storage_chargeTh.csv` and `socTh.csv`
  (thermal storage), `demandDH.csv`.

## Capacities

- **`gen_max.csv`** (electric, MW) and **`genTh_max.csv`** (district heat, MW) hold the
  capacity of every plant, existing or new. Storage energy: `gen_energy_max.csv`,
  `gen_energyTh_max.csv` (MWh). Charging power: `pmp_max.csv`.
- **New-build candidates** are the plants in `P_allinv.csv`; their whole capacity is new. The
  district-heating candidates there (`*HPNew`, `*resistiveNew`, `*CHPNew`) have their heat
  capacity in `genTh_max.csv`. Thermal storage (`*_TTES_*`, `*_PTES_*`) is not listed in
  `P_allinv.csv`; its capacities are in `genTh_max.csv` and `gen_energyTh_max.csv`.
- **`investment_*_slp*.csv` are annualised cost slopes** (CHF per MW or MWh and year), not
  capacities.
- In multi-weather-year runs, capacities are equal across sub-scenarios and repeated in each.
- **Representative Swiss hydro** (setting `rep_hydro_plants`, default `True`): `large_psp`,
  `medium_reservior` and `small_reservior` all carry technology `psp_open` in
  `Map_plant_tech.csv`, although the latter two are reservoirs; `CH00_dam` has zero capacity.

## Trade

- **`Export.csv`** is the signed flow per line `HVAC_<from>_<to>`: positive from the first node
  to the second.
- **NTC limits are not exported.** They are in `input/NTC/`. With `DUALS_EXPORT_ALL = True`,
  `lineATClimit_dual.csv` shows when a line is at its limit.
