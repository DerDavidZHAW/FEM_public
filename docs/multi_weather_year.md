# Multi-weather-year runs

Checked against: `main` @ 54d6be28 (2026-10-09).

One meta-scenario can hold several sub-scenarios, usually one per weather year, solved as a
single optimisation: dispatch is separate per sub-scenario, investment is shared, and the
objective is the weighted sum of the sub-scenario costs.

## Setup

Repeat the meta-scenario's column in the scenario CSV, once per sub-scenario (general CSV rules:
`docs/running.md`):

```
Item,2035_base,2035_base,2035_base
sub_secn,wy1995,wy2008,wy2009
weight_in_objective_fcn,0.333333,0.333333,0.333334
weather_year,1995,2008,2009
```

- **`sub_secn`** values must differ within the meta-scenario; they become the sub-scenario
  names `2035_base_wy1995` etc.
- **Weights** must sum to 1, checked to 6 decimals: thirds are written `0.333333, 0.333333,
  0.333334`. `scenarios/scen_to_run_STORSUPPORT.csv` uses `0.33, 0.33, 0.34`.
- **Settings that must be identical** across the sub-scenarios: `t_start`, `t_end`, `CH_only`,
  `Node_list_setting`, `NodeDH_list`, `slack_soc` and `solver_name`. The model takes them from the
  last sub-scenario without checking the others. `resistive_heater_investment_cap_MW_total` is
  checked and raises an error if it differs. The winter import limit and the Swiss RES target are
  switched per sub-scenario, but whether their duals are exported follows the last sub-scenario.
- District-heating demand exists for weather years 1995, 2008 and 2009.

## Shared investment

Capacities have a `Scenarios` index but are tied to the first sub-scenario by equality
constraints in `model/components_common.py`:

| Constraint | Ties |
|---|---|
| `gen_max_equal` | `gen_max` of all generators |
| `pmp_max_equal` | `pmp_max` of hydrogen plants only |
| `gen_energy_max_equal`, `gen_energy_max_equal2` | Storage energy `gen_energy_max` |
| `fuel_storage_capacity_annual_equal` | Fuel storage investment |
| `genTh_max_equal` | `genTh_max` of all district-heating plants |
| `gen_energyTh_max_equal` | Thermal storage energy `gen_energyTh_max` |

Output files therefore repeat the same capacity for every sub-scenario; read any one.
Investment cost is charged per sub-scenario times its weight, which sums to the full annuity
because the weights sum to 1.

## Outputs

- One folder per meta-scenario, `output/<meta>/`. `settings.csv` has one column per sub-scenario.
- Every file's `Scenarios` column distinguishes the sub-scenarios. `T` repeats for each, and
  `t_k` is the hour of that sub-scenario's own weather year.

## Duals and rents

- Every cost term is multiplied by the weight `w_s`, so a within-year price is the exported dual
  divided by `w_s` (`docs/duals.md`).
- Take a plant whose capacity the optimisation chooses freely (not at an investment limit, not
  fixed by a preset or as pre-existing capacity) and that appears only in its hourly capacity
  constraint. Its hourly rents (for `generation_limit`: −dual × availability) summed over all
  hours **and** sub-scenarios, without dividing by the weights, equal its annualised investment
  cost. The sum within one sub-scenario need not equal `w_s ×` annuity: one weather year can
  carry most of the rent.

## Dashboard

`tools/prepare_viewer.py` converts one sub-scenario. Without `--sub-scenario <Scenarios value>`
it takes the first and prints a warning. It shows exported duals as they are, so prices from a
multi-weather-year run appear multiplied by `w_s`.

## Memory

A meta-scenario with three full-year sub-scenarios needs well over 32 GB of RAM; run it on
Euler (`docs/running.md`, "HPC runs").
