# Duals and reduced costs

Checked against: `main` @ 54d6be28 (2026-10-09).

Which duals a run exports, and how to turn a value in a `*_dual.csv` into a price or rent.

## Units: exported duals are already unscaled

Many constraints are multiplied by a factor `sf` on both sides for numerical conditioning
(`model/constraint_scaling.py`; each run copies the factors to `constraint_scaling.csv`). The
solver's dual of a scaled row is `1/sf` times the dual of the original constraint.

**Since commit `fb1ee3b3` (PR #55, 9 October 2026), the export multiplies every dual by its
`sf` before writing.** Values in `*_dual.csv` from runs made with that code are in the units of
the original constraint; apply no further scaling. A constraint without an entry in the scaling
map is not scaled by the model and is exported unchanged.

**Runs made before that commit** hold the solver's raw duals. For those, multiply by the factor in
the run's own `constraint_scaling.csv` (for `consume_tot_limit_*` files use the
`consume_tot_limit` factor). A run folder does not record the commit it was made with
(`model_version` in `settings.csv` was not changed), so tell old from new runs by date. The
seven duals exported by default all have factor 1 and are the same under both conventions.

Factors other than 1 on `main`: `generation_limit` and `energy_limit` 0.1;
`storage_rate_limit` 0.01; `storage_soc_limit`, `storage_start_condition`, `curtailment_limit`,
`fuel_limit_annual`, `gen_max_limit_constraint`, `genTh_max_limit_constraint`,
`gen_energyTh_max_limit_constraint` and `consume_tot_limit` 0.001; `building_heat_demand` 100.
Read them from the run's `constraint_scaling.csv` rather than from this list.

## Which duals are exported

Written during the run by `constraints` in `aggregation/results_export.py`, called from
`model/core.py`.

**By default**, from the list `constraint_names_to_export` in `model/core.py`:

| File | Meaning | Index |
|---|---|---|
| `energy_balance_dual.csv` | Electricity price, CHF/MWh | `T, Node, Scenarios` |
| `energy_balancethermal_dual.csv` | District-heat price, CHF/MWh | `NodeDH, T, Scenarios` |
| `storage_soc_dual.csv` | Value of stored electric energy | `P_storage, T, Scenarios` |
| `generationTh_limit_dual.csv` | Thermal generation capacity (incl. heat pumps and resistive heaters) | `PDH, T, Scenarios` |
| `storageTh_rate_limit_dual.csv` | Thermal storage charging rate | `PDH_storage, T, Scenarios` |
| `storageTh_soc_limit_dual.csv` | Thermal storage energy capacity | `PDH_storage, T, Scenarios` |
| `storageTh_soc_dual.csv` | Value of stored heat | `PDH_storage, T, Scenarios` |

`Constraint_winter_limit_dual.csv` and `Constraint_investment_res_CH_dual.csv` are added when the
winter import limit or the Swiss RES target is switched on. Note the different index order of
the two price files.

**With the setting `DUALS_EXPORT_ALL = True`**, the duals of all active constraints are written,
e.g. `generation_limit`, `storage_rate_limit` (electric charging, incl. DH heat pumps and
resistive heaters), `lineATClimit` (transmission limits), `building_heat_demand`. The
electrolyzer limits are scalar constraints, one file each:
`consume_tot_limit_<plant>_<n>_<sub-scenario>_dual.csv`. A few constraints print
`Error in exporting duals for <name>` and produce no file (empty constraints, or rows the solver
never received); the rest of the export continues.

## Signs

The model minimises cost. For a `<=` constraint the exported dual is `<= 0`, for a `>=`
constraint `>= 0`; an equality's dual has either sign. The balance duals are prices: positive
when more demand raises cost. A **capacity rent** is the negative of the capacity constraint's
dual, e.g. rent = `-generation_limit` dual.

## Weights (multi-weather-year runs)

Every cost term is multiplied by the sub-scenario weight `w_s` (`weight_in_objective_fcn.csv`),
so the dual of an hourly constraint in sub-scenario `s` is `w_s` times its within-year value:

$$
\text{within-year value}_{s,t} \;=\; \frac{\text{exported dual}_{s,t}}{w_s}
$$

With one sub-scenario, `w = 1` and nothing changes. Duals of the constraints that tie investment
across sub-scenarios (`*_equal`) have no within-year meaning. Details:
`docs/multi_weather_year.md`.

## Checking a dual

For a single-sub-scenario run, pick a plant running strictly between zero and its capacity in
some hour: the electricity price at its node equals its operating cost (`operation_slp.csv`).
For a plant at full capacity: `-generation_limit` dual = price − operating cost. In the test run
(`docs/running.md`) with `DUALS_EXPORT_ALL = True`, `CZ00_nuclear` at `t_6553` has a
`generation_limit` dual of −85.43, and price − operating cost = 97.78 − 12.35 = 85.43.

## Non-unique duals

An LP can have several optimal dual solutions with the same objective. Then the exported duals
depend on the solver path: in the test scenario, switching Gurobi to barrier only (`method=2`)
changed some industrial heat prices (`ILHT_*`, `ILLT_*`) by up to about 490 CHF/MWh while the
objective and the electricity prices stayed identical. Compare duals between runs only when
they used the same solver settings, and treat a single hour's price at such nodes with care.

## Reduced costs

Written for the investment variables `gen_max`, `genTh_max`, `gen_energy_max` and
`gen_energyTh_max` as `<variable>_reduced_cost.csv`, one row per plant:

| Column | Meaning |
|---|---|
| `technology` | Plant technology |
| `rc_total_annualized` | Reduced cost summed over sub-scenarios (CHF per MW or MWh and year) |
| `annuity` | Annualised investment cost |
| `overnight_cost` | Overnight investment cost |
| `break_even_overnight` | Overnight cost at which the option would just be built: `overnight_cost × (annuity − rc) / annuity` |
| `reduction_needed_overnight` | `overnight_cost − break_even_overnight` |

Reduced costs do not depend on constraint scaling. When a run covers less than a full year, they
compare a full-year annuity with the value earned in the modelled hours only.
