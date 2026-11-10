# Changelog

All notable changes to the FEM model are documented here, grouped by release.
The format follows [Keep a Changelog](https://keepachangelog.com/); minor housekeeping changes are omitted.

---

## [1.0.3] — 2026-08-20

### Added
- **District-heating demand adjustment** (`model/dh_demand_adjustment.py`): per-scenario overlay of signed MW deltas (NodeDH × hour) on top of the assembled DH demand, enabled via the new `DH_demand_adjustment_file` scenario setting. Adjustment files live in `input/demand/adjustments/`; a generator utility is provided in `utils/make_dh_adjustment.py`. Validation is strict — unknown labels, deltas driving demand negative, or combining with the global `reduce_DH_demand_by_[MWh]` knob raise errors.
- **Standalone results dashboard** (`viewer.html`): a self-contained, dependency-free browser dashboard for exploring a single solved run (headline KPIs, annual heatmaps, dispatch stacks, day drill-down, price statistics, cross-border congestion, storage cycling, capacity/investment, curtailment, district heating). Runs are packed into a gzipped JSON and dragged onto the page — no server or internet required.
- New plot creators for NTC sensitivity analysis: `arbitrage_revenue_vs_ntc.py` and `ch_flows_flexibility_vs_ntc.py`.
- New DH A/B scenario run list (`scenarios/scen_to_run_dh_ab.csv`).

### Changed
- **Solver settings**: Gurobi now runs the barrier method with crossover disabled (`method=2 crossover=0`).
- Pre-installed heat pumps' thermal generation capacity is now explicitly fixed to electric capacity × COP, so the heat-pump scarcity rent appears on the thermal-side dual (`generationTh_limit_dual`), consistent with all other DH plants. The optimal objective is unchanged.
- Updated Swiss DH heat-pump capacities (`input/plants_DH_CH_capacities.csv`), including a new `DH_medium_HPG` plant.

### Fixed
- **DSR thermal energy tracking**: hours within a week were compared as raw `t_<n>` strings, which sorts lexicographically (`t_10 <= t_3`) and silently pulled the wrong hours into the running deviation sum for weeks spanning different digit lengths. Comparison is now by numeric hour index.

---

## [1.0.2] — 2026-07-13

### Added
- **High-resolution PV modeling** (`model/high_res_PV.py`).
- **Post-hoc detailed reporting** (`detailed_reporting/run_detailed_reporting_posthoc.py`): run the detailed reporting on already-solved results.
- **Aggregation merging** (`aggregation/merge_aggregateds.py`): merge multiple aggregated result sets.
- **Euler HPC support**: dedicated run and setup scripts (`cluster_runs/parallel_runs_Euler.sh`, `setup_euler_scratch.sh`) plus a step-by-step installation walkthrough in the README.
- New plot creators: battery investments summary, hourly dispatch scenario comparison, summer price / heat demand window, plus a `run_all_visualizations.py` driver.
- Investment extraction utility (`utils/extract_investments.py`).

### Changed
- **Import cost calculation reworked**: import costs are now valued at the Swiss market price (CH dual price) instead of per-line neighbor prices — imports are summed across all CH lines per timestep, then multiplied by the CH price.
- Python requirement relaxed from exactly 3.10.5 to **3.10–3.12**.
- Updated Swiss RES capacities (`input/res_capacities_CH.csv`).
- Major overhaul of several plot creators (monthly heat sources, resistive-heater vs. heat-pump comparison, violin price plot, nuclear investment) and of the visualization class.

### Removed
- Yearly EV energy consumption input files (superseded by the separated EV demand parameters introduced in 1.0.1).
- Generic `cluster_runs/parallel_runs.sh` (replaced by the Euler-specific scripts).

---

## [1.0.1] — 2026-02-03

Development period November 18, 2025 – February 3, 2026.

### Added
- **Reduced costs & break-even analysis**: export of reduced costs for investment variables, enabling analysis of how much investment costs would need to decrease for a technology to become profitable. Quadratic terms in the objective were disabled to allow a proper reduced-cost calculation.
- **Detailed reporting system** (`detailed_reporting/`): spatial (`Output_Spatial`), system-level (`Output_Sys`), and temporal (`Output_Temp`) reporting; runs when there is exactly one sub-scenario.
- **Model variable presets** (`input/model_variable_presets.csv`): fix specific variables to predefined values for sensitivity analysis and scenario comparisons (disabled by default).
- **Battery investment flexibility**: new `battery_investment_nodes_in_addition_to_CH` setting to allow nodes beyond CH00 to invest in batteries.
- **Flexible EV share**: new `share_of_flexibly_charging_EV` scenario setting.
- New `plot_creators/` package (battery net revenue, daily electricity costs, electricity prices, monthly heat sources, nuclear investment, resistive-heater vs. heat-pump comparison, violin price distributions, and more).
- Optional resistive heater investment limit constraint.

### Changed
- **Numerical stability overhaul**: scaling factors added to all constraints and calibrated to reduce coefficient ranges; parameters rounded to at most 4 decimal places; never-binding constraints with extremely large right-hand sides removed; solver settings simplified.
- **EV consumption separation**: inflexible EV consumption is now a separate parameter, no longer merged with general inflexible demand — this changes results when demand scaling is applied.
- **Heat pump demand separation**: inflexible heat-pump demand is distinguished from general demand in reporting.
- Cost assumptions moved to an Excel file with source comments; 2050 gas cost assumptions adjusted.
- Unused technologies removed from the model.

### Fixed
- Flexible EV consumption considered whole weeks even when only partial weeks were modeled.
- Crash when no additional battery investment nodes were provided.
- Feed-in from offshore wind was prevented by a bug.

---

## [1.0.0] — 2025-11-18

Initial public release: Pyomo/Gurobi-based electricity market model for Switzerland and neighboring countries, including data preparation (TYNDP import, district heating, industrial load), the model core with central and common components, aggregation and result export tooling, cluster run scripts, input datasets (demand, RES, hydro, NTC, costs), scenario definitions, and the settings and output documentation.

[1.0.3]: https://github.com/DerDavidZHAW/FEM_public/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/DerDavidZHAW/FEM_public/compare/v1.0.0...v1.0.2
[1.0.1]: https://github.com/DerDavidZHAW/FEM_public/commit/7604f86
[1.0.0]: https://github.com/DerDavidZHAW/FEM_public/releases/tag/v1.0.0
