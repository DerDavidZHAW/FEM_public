# Historical CH-only runs: code changes needed (plan)

Prepared 2026-10-09 for `feature/historical-backcast-data`. **Plan only; nothing below is implemented.**
**Input:** the processed tables of this repository's pipeline, `data_prep/historical`
(`input/historical/processed/<period>/`, `time_utc` index, UTC interval start). These include
`ntc_dayahead_combined_hourly.csv` (section 4.2) and Swiss demand option A, `ch_demand_option_a_hourly.csv`
(section 4.3).

**Codex's format** (`input/historical_market/<label>/processed/`, `timestamp_utc` index) comes from a
separate pipeline that is not in this repository. The source map below can read it too. File names in some
sections (e.g. `prices_hourly.csv`, `generation_hourly.csv`) are Codex's; `data_prep/historical` writes
`prices_day_ahead_hourly.csv` and `ch_public_power_hourly.csv`.

**Gap:** PECD weekly inflow (section 4.6) exists only in Codex's data set. This repository's pipeline does not
download it yet.

First target: 1 Oct 2025 - 31 Aug 2026 (`hy_2025_2026`).

## 1. Design rules

- **One master switch.** A new setting `historical_data_dir` (default `False`). When it is `False`,
  nothing runs differently; existing scenarios must give identical results (checked by a regression
  test, section 9).
- **Existing readers stay untouched.** They keep loading the future-scenario data with the structural
  values `run_year=2050`, `weather_year=1995`; cost tables and file names need those. Two new
  functions then overwrite or zero what a historical run must not use.
- **Two hook calls**, each one line:
  - data side: `apply_historical_inputs(scenario_name, settings_scen)` at the end of
    `data_import_TYNDP_fcn` (`data_prep/data_import_TYNDP.py`);
  - model side: `apply_historical_constraints(model, ...)` in `model/core.py`, right after
    `fixing_capacities_central` (about line 171).
- **All new logic lives in two new modules.** Each replacement is its own function, so you can switch
  pieces on and off and test them separately:
  - `data_prep/historical_inputs.py` (data side);
  - `model/components_historical.py` (model side).
- **Other years need no code change.** Only the data folder and the `t_start` / `t_end` window change.
  Column names come from one source map, so Codex's or Claude's processed format can be used.
- **Errors over fallbacks.** Any missing hour, missing column or NaN inside the run window raises,
  naming the series and hours.

## 2. New settings (`scenarios/settings_default.py`)

| Setting | Default | Meaning |
|---|---|---|
| `historical_data_dir` | `False` | Folder with `processed/`, e.g. `"input/historical_market/hy_2025_2026"`. Requires `CH_only=True` and `allow_investment=False`; otherwise it raises. |
| `historical_replace` | all items | Which inputs to replace: `["prices", "ntc", "demand", "res", "nuclear", "hydro_inflow", "hydro_boundary", "exclude_future_modules"]`. Remove an item to keep the model's own input for that part (sensitivity tests). |
| `historical_demand` | none, must be set | Column of `ch_demand_option_a_hourly.csv` to use (section 4.3): `"demand_MW"` for the decided run (50/50 split). The extremes `"demand_solar_shaped_MW"` and `"demand_flat_MW"` are for sensitivity runs only. |
| `historical_hydro_end` | `"equal"` | Reservoir level at the last hour: `"equal"`, `"at_least"` or `"free"` the observed level |
| `historical_hydro_spill` | `"zero"` | `"zero"` (agreed assumption) or `"allowed"` |
| `historical_time_offset` | derived | Not a setting: computed from the data's first local date (section 3) |

**Settings that must be `False`/`0` with the master switch** (raise otherwise, because they would
rescale the fleet or inflow behind the historical data): `hydro_inflow_TWh`, `ror_annual_TWh`,
`pump_capacity_GW`, `adding_hydro_storage_cap_TWh`, `reduce_inflex_demand_by_[MWh]`, `NodeDH_list` (must
be `[]`).

`NTC_CH_ratio` keeps its meaning as an explicit multiplier on the historical limits.

## 3. Time mapping (`historical_time_map`)

**Rule.** The k-th UTC hour of the data is assigned to model step
`t_((offset + k - 1) mod 8760) + 1`, where `offset` is the hour-of-year of the first local hour in a
365-day calendar. 1 October gives `offset` = 6552, so 1 Oct 00:00 local is `t_6553`. This is the hour at
which every hydrological-year run already starts, so the existing week, day and month maps remain valid.

**Hydrological year 2025/26** (8,760 h, no 29 February):

| Window | `t_start` | `t_end` | Hours | Status |
|---|---|---|---|---|
| 1 Oct 2025 - 30 Sep 2026 | 6553 | 6552 | 8,760 | Swissgrid missing September; NTC complete |
| 1 Oct 2025 - 31 Aug 2026 | 6553 | 5832 | 8,040 | NTC complete (Oct-Dec 2025 from the ENTSO-E web copy, section 4.2) |
| 1 Jan - 31 Aug 2026 | 1 | 5832 | 5,832 | All inputs present today |

Since 2026-10-09 the day-ahead NTC is complete for Oct 2025 - Sep 2026 (section 4.2), so Swissgrid and
BFE, not the NTC, set the August cut. A helper prints `t_start` and `t_end` for given dates, and the importer checks that every hour of
`T_list` has data.

**Known limits:**
- **Day boundaries.** Daily blocks follow UTC, so in winter they run 23:00-23:00 local. Only daily
  constraints are affected (DSR, run-of-river daily split), and both are replaced or excluded here.
- **Leap periods.** A period with 29 February (e.g. Oct 2023 - Sep 2024, 8,784 h) does not fit 8,760
  steps and raises. A later explicit `leap_day_policy` could drop that day by declaration.

## 4. Data-side functions (`data_prep/historical_inputs.py`)

All write into the existing global dicts, keyed `(..., 't_k', scenario)`, only for `t` in `T_list`.

**4.1 `neighbour_prices`** → `Line_trade_price` for `HVAC_{DE,FR,IT,AT}00_CH00`
- Source: `prices_hourly.csv` columns DE00, FR00, IT00, AT00 (EUR/MWh), hourly means of the
  quarter-hours.
- Negative prices are kept.
- The existing CSV loader in `read_line_data` is bypassed, so its silent zero fallback is never reached.

**4.2 `transfer_limits`** → `ATC_exportlimit` and `ATC_importlimit`
- Source: `ntc_dayahead_combined_hourly.csv` from Claude's pipeline, complete for Oct 2025 - Sep 2026.
  - Values: Swissgrid D-2, with the ENTSO-E web copy for Oct-Dec 2025 and for 24 Sep 2026.
  - Codex's `capacity_hourly.csv` lacks Oct-Dec 2025 and holds Swissgrid's early version 1 for 24 Sep.
- Recommended limit: the day-ahead NTC, not the intraday NTC.
  - Most hours in which the observed schedule exceeds the day-ahead NTC are intraday trades that stay
    within the intraday NTC.
  - The day-ahead price did not see those trades (trade versus NTC analysis, `plot_trade_ntc.py`; see
    `data_prep/historical/README.md`, Analyses).
- Line `HVAC_X00_CH00` gets upper bound `X_to_CH` and lower bound `CH_to_X` (the existing direction
  convention, `components_common.py:2166-2189`).
- Hourly values come from the minimum of the quarter-hours.
- Missing hours raise; no constant 2050 value is substituted.

**4.3 `swiss_demand`** → `Demand_data[('CH00_fixedconsumer','fixed',t,s)]`, plus `EV_inflexible_demand`
and `HP_inflexible_demand` set to 0.

**Decided 2026-10-09: option A ("gross").** The series is already built by the data pipeline
(`data_prep/historical/demand.py`). The function only reads the column named in `historical_demand` and
raises on any NaN in the window. Construction:

    demand(t) = Swissgrid end-user consumption(t) + grid losses(t) + on-site consumption(t)

**Why these parts.**
- Pumping is a model decision, so demand excludes it. Swissgrid end-user consumption contains no pumping.
- FEM's solar infeed is total PV production (Energy-Charts solar, equal to BFE). Demand must therefore also
  contain the consumption that on-site generation covers. Swissgrid's meters see neither that generation
  nor that consumption.
- Grid losses are BFE monthly totals, spread in proportion to end-user consumption.
- On-site consumption is BFE monthly end use minus Swissgrid end-user energy (220-650 GWh per month).
- Monthly demand equals BFE Landesverbrauch (end use + losses, excluding pumping), so demand matches the
  BFE-calibrated solar, run-of-river and nuclear series.

**Assumption, to be stated with every result.** The hourly placement of on-site consumption is not
observed. It mixes self-consumed PV (midday only) with other on-site generation (around the clock), and the
split is not published.
- `demand_MW` places **50% like PV output and 50% flat** (`ONSITE_SOLAR_SHARE = 0.5`, user decision
  2026-10-09, to avoid running both extremes).
- The extremes remain available for sensitivity runs. In July 2026 they differ by about 1.6 GW at noon and
  0.9 GW at night, so the 50/50 series can be off by up to half of that.
- With the ENTSO-E token, a variant without this assumption becomes possible: demand = Swissgrid total
  consumption - hourly pumping (A75), and exogenous generation = Swissgrid metered production - storage
  generation.

**Rejected options:**
- Swissgrid end-user consumption scaled to BFE months stretches the shape, so self-consumed PV is still
  missing at midday.
- Swissgrid total consumption and Energy-Charts load both contain pumping, which the model would count
  twice. Energy-Charts' hourly shape is also unreliable. Generation + metered imports - its load swings by
  up to 2.8 GW over the day in 2023-2025, following solar more than pumping.

**Coverage.** Values end on 31 Aug 2026 (Swissgrid and BFE September not yet published). That fits the
August cut.

Fixed "others" generation (Energy-Charts `others`, monthly flat, about 400 MW thermal, waste and
biomass) is subtracted from demand. This needs no new infeed technology; the function documents and
logs it.

**4.4 `res_infeed`** → `Infeed_consumers[('CH00_fixedconsumer', tech, t, s)]`
- Techs: `pvrf` = solar, `windon` = wind, `ror` = run-of-river, from `generation_hourly.csv`.
- Other CH infeed keys are set to 0.
- Curtailment stays possible (its cap follows infeed).

**4.5 `nuclear`** (agreed assumption: output equals the observed series each hour)
- One CH nuclear plant (the existing `CH03_nuclear`) gets capacity 2,973 MW (net, explicit constant
  with source note).
- `Avail_plant[(p,t,s)]` = observed / 2,973. Raises if observed exceeds capacity.
- The model-side equality (5.2) fixes output.
- Its operating cost then shifts the objective by a constant and does not affect prices.

**4.6 `hydro_inflow`** → `Inflow_data[(p,t,s)]` for `large_psp`, `medium_reservior` and `small_reservior`
- Source: PECD HRI + HOL weekly MWh (`pecd_weekly_ch00.csv`), spread flat over each week's hours, then
  mapped to `t`.
- Split with the existing shares 0.716, 0.245 and 0.039 (a representation assumption kept as is).
- `CH00_psp_close` gets 0.
- Week timing follows Codex's documented UTC-start convention. Codex flags that convention as
  unverified, so the function reads it from the data.

**4.7 `hydro_levels`** (data for 5.1)
- Interpolates the BFE weekly content (Sunday 24:00) to the first and last hour of the window.
- Expresses it as a fraction of the BFE maximum (8,895 GWh). Those fractions × each plant's model
  storage capacity give the start and end levels.
- Raises if the surrounding snapshots are more than 8 days apart.

**4.8 `exclude_future_modules`** sets to 0 the future-only demand inputs that would double count observed
load:
- EV weekly energy, V2G outflow, the CH electrolyzer energy requirement and household heat-pump profiles;
- the cases where the existing settings cannot reach 0 (EV shares, electrolyzer coefficient) are zeroed
  here.

## 5. Model-side functions (`model/components_historical.py`)

**5.1 `hydro_storage_boundary`**
- For the hydro storage plants:
  - deactivate `storeBalance[p, first_t, s]` (the cyclic link via `T.prevw`) and the 0.95
    `storage_start_condition`;
  - add a first-hour balance that uses the observed start level;
  - add the end condition per `historical_hydro_end`.
- With `historical_hydro_spill="zero"`, fix `spill_water[p,t,s]` to 0.
- Batteries and closed-loop pumped storage keep the existing cyclic rule.

**5.2 `nuclear_fixed_output`**: `gen[CH03_nuclear, t, s] == observed[t]` for every t.

**5.3 `exclude_assets`** fixes capacity and dispatch to 0 for assets that did not exist or would act as
free sinks or sources:
- the CH 2050 thermal fleet (biomass, CCGTCCS, `other`), since observed "others" are already in demand;
- district-heating plants attached to CH00, and district-heating investment candidates;
- `ev_flex`, `v2g`, `electrolyzer`, `heat_pump_households`;
- fuel-storage investment;
- any remaining investment variable.

The function raises if an expected asset name is not found, so a renamed plant cannot silently stay
active.

## 6. Unavoidable edits to existing code

1. **Negative prices.** `model.line_trade_price` domain `NonNegativeReals` → `Reals`
   (`components_common.py:1201`). Needed for negative prices; it changes nothing for non-negative inputs.
2. **The two hook calls** (section 1).
3. **New defaults** in `settings_default.py` (section 2).

**Recommended separate fix, not required for this plan:** the existing CSV price loader in
`read_line_data` swallows every error and runs with zero trade cost; `.get(...,0)` in the parameter adds
the same risk. A one-line raise would protect all CH_only runs. I would make that a separate commit.

## 7. Currency

- Neighbour prices and lost-load cost are EUR. Plant costs are CHF2017, with no conversion anywhere.
- In this setup the only Swiss dispatch left is hydro (cost 0.1) and lost load, because nuclear and
  "others" are fixed and the thermal fleet is excluded. The CH price (the energy-balance dual) is
  therefore in EUR/MWh and directly comparable with the observed CH price.
- This holds only while all remaining Swiss costs are in EUR or negligible. The adapter logs the
  remaining non-zero CHF cost terms.

## 8. Scenario file `scenarios/scen_to_run_CH_only_historical.csv`

One column per test, e.g. `hist_2526_janaug` (t_start 1, t_end 5832) and `hist_2526_octaug`
(t_start 6553, t_end 5832). Rows:
- `CH_only=True`, `allow_investment=False`, `NodeDH_list=[]`;
- `historical_data_dir`, `historical_demand`, `historical_hydro_end`;
- the window;
- one sub-scenario with weight 1.

`target_csv` is set for the run and restored afterwards (AGENTS.md).

## 9. Tests and checks

- **Unit tests (no solver)**, each written to fail on wrong code:
  - time map (offsets, wrap, window check, leap period raises);
  - limit direction per line;
  - strict price and limit loading (missing hour raises, negative price kept);
  - demand column selection and NaN check (the construction itself is tested in
    `tests/test_historical_demand.py`);
  - inflow split preserves weekly MWh;
  - reservoir interpolation.
- **Model-side unit test** on a tiny Pyomo model (no solve): the first-hour balance is replaced, the end
  condition and spill fixing are applied, and nuclear output is fixed.
- **Regression:** `scen_to_run_test.csv` before and after the change, with the flag off. The objective
  and every exported CSV must be identical.
- **Pilot runs:** one winter week and one summer week, then Jan-Aug 2026. Check:
  - energy balance closes, flows stay within limits, prices keep their sign;
  - modelled reservoir path vs BFE;
  - modelled border flows vs scheduled commercial exchange (like for like);
  - physical flows as a secondary check only, from **Swissgrid metering**
    (`ch_exchanges_physical_hourly.csv`, or `swissgrid_hourly.csv` in Codex's format), never Energy-Charts
    `cbpf`. Energy-Charts overstates the FR border by about 15% in both directions, in every month since
    Oct 2023. BFE monthly imports agree with Swissgrid;
  - a small demand step changes the CH dual by the expected amount.
- **Price comparison script** `tools/compare_historical_prices.py`. It maps `energy_balance_dual.csv`
  (CH00) back to UTC with the same time map and reports, against the observed CH price:
  - MAE, RMSE, bias and correlation;
  - monthly means and the price duration curve;
  - hours at the border limits, against the observed reference (FR to CH imports at the limit in 69%
    of hours, CH to IT exports in 34%; trade versus NTC analysis, `plot_trade_ntc.py`);
  - a benchmark (mean neighbour price).

## 10. Decisions needed before implementation

1. ~~**Demand definition**~~ **Decided 2026-10-09:** option A with a 50/50 split of on-site consumption,
   column `demand_MW` (section 4.3).
2. **First run window:** Jan-Aug 2026 or Oct 2025 - Aug 2026. Both have day-ahead NTC since 2026-10-09.
3. **Reservoir end condition:** `"equal"` (recommended for a back-cast) or `"at_least"`.
4. **Hydro fleet:** keep the representative 2030 fleet (8.8 TWh, 10.7 GW, 2.05 GW pumping) for the first
   test, or load year-specific BFE capacities. The latter needs a fleet file, which no one has built yet.
5. **Others:** subtract observed "others" from demand (recommended), or keep the 2050 thermal fleet
   dispatchable.
