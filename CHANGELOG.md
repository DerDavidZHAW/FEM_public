# Changelog

All notable changes to the FEM model since the initial public release (v1.0.0, November 18, 2025).

---

## July 13, 2026

### Changed
- **Import cost calculation reworked** (`detailed_reporting/Output_Sys.py`): import costs are now valued at the Swiss market price (CH dual price) instead of per-line neighbor prices. Imports are summed across all CH lines per timestep and scenario, then multiplied by the CH price. (98ff820)

### Visualization
- Violin price plot: winter/summer statistics tables in the Markdown export now include the full percentile spread (P5–P95 in 10-point steps) in addition to mean, median, std, min, and max. (a0e0d46)
- Adjusted the battery investments summary-for-presentation plot. (a0e0d46)

---

## [1.0.2] — June 1, 2026

### Added
- **High-resolution PV modeling** (`model/high_res_PV.py`).
- **Post-hoc detailed reporting**: `detailed_reporting/run_detailed_reporting_posthoc.py` allows running the detailed reporting on already-solved results.
- **Aggregation merging**: `aggregation/merge_aggregateds.py` to merge multiple aggregated result sets.
- **Investment extraction utility**: `utils/extract_investments.py`.
- New plot creators:
  - `battery_investments_summary_for_presentation.py`
  - `hourly_dispatch_scenario_compare.py`
  - `summer_price_heat_demand_window.py`
- **Euler HPC support**: `cluster_runs/parallel_runs_Euler.sh` and `cluster_runs/setup_euler_scratch.sh` (replacing the generic `parallel_runs.sh`), plus a detailed step-by-step Euler installation walkthrough in the README (Poetry setup quirks, module loads, scratch vs. home storage).
- `.gitattributes` added.

### Changed
- Python requirement relaxed from exactly 3.10.5 to **3.10–3.12**.
- Model version bumped to **1.0.2** (`model/version.py`).
- Updated Swiss RES capacities (`input/res_capacities_CH.csv`).
- Major overhaul of several plot creators (`monthly_heat_sources.py`, `rh_hp_comparison.py`, `violin_price_plot.py`, `nuclear_investment_plot.py`) and of `visualization_class.py`.
- Refactoring across the detailed reporting modules (`Output_Spatial.py`, `Output_Sys.py`, `Output_Temp.py`, `constants.py`, `reporting_main.py`).
- Updated STORSUPPORT scenario run list; dependencies refreshed (`poetry.lock`).

### Removed
- `input/demand/EV_energyconsumption_2035.csv` and `EV_energyconsumption_2050.csv`.
- Old `cluster_runs/parallel_runs.sh` and the superseded storage-paper summary script in `visualization/`.

---

## March 17, 2026

- README: updated the suggested citation. (503852a)

---

## [1.0.1] — February 3, 2026

One large release commit (7604f86) covering development from November 18, 2025 to February 3, 2026. Model version bumped to **1.0.1** (December 12, 2025).

### Major features
- **Reduced costs & break-even analysis** (January 2026): export of reduced costs for investment variables to analyze how much investment costs would need to drop for a technology to become profitable. Quadratic terms in the objective were disabled to enable proper reduced-cost calculation.
- **Detailed reporting system** (January 2026): new `detailed_reporting/` package with `Output_Spatial.py` (spatial/geographic), `Output_Sys.py` (system-level), and `Output_Temp.py` (temporal) reporting; runs only when there is exactly one sub-scenario.
- **Model variable presets** (January 6, 2026): new `input/model_variable_presets.csv` and `model/variable_presets.py` let users fix specific variables to predefined values (useful for sensitivity analysis); disabled by default.
- **Battery investment flexibility** (January 6, 2026): new `battery_investment_nodes_in_addition_to_CH` setting to allow nodes beyond CH00 to invest in batteries.

### Numerical stability (December 2025)
- Added scaling factors to all constraints (`model/constraint_scaling.py`) and calibrated them to reduce coefficient ranges.
- Rounded all parameters to at most 4 decimal places.
- Removed never-binding constraints with extremely large right-hand-side values.
- Solver settings: switched back to the barrier algorithm with tuned settings for numerically troublesome scenarios, later simplified to minimal settings letting Gurobi choose defaults.
- Added an optional resistive heater investment limit constraint.

### Bug fixes
- Fixed flexible EV consumption considering whole weeks even when only partial weeks were modeled (January 13, 2026).
- Fixed crash when no additional battery investment nodes were provided (January 6, 2026).
- Fixed a bug preventing feed-in from offshore wind (December 9, 2025).

### Data & input changes
- **EV consumption separation** (January 12, 2026): inflexible EV consumption is now a separate parameter, no longer merged with general inflexible demand — this changes results when demand scaling is applied. New hourly/weekly EV demand input files.
- **Heat pump demand separation** (January 13, 2026): inflexible heat pump demand distinguished from general demand for reporting.
- **Flexible EV share** (January 9, 2026): new `share_of_flexibly_charging_EV` scenario setting.
- **Cost assumptions** (December 8–10, 2025): transitioned to an Excel file (`input/cost_assumptions.xlsx`) with source comments; adjusted 2050 gas cost assumptions.
- Removed unused technologies from the model (December 8, 2025).
- Large-scale regeneration of input time series (RES profiles, demand profiles, neighbor prices, hydro data).

### Visualization & analysis
- New `plot_creators/` package with plots for battery net revenue, daily electricity costs, electricity prices, monthly heat sources, nuclear investment, resistive-heater vs. heat-pump comparison, violin price distributions, and presentation summaries.
- Made the visualization class more user-friendly (February 1, 2026).
- Added annual balances export for other countries during aggregation (December 12, 2025).

### Scenario management
- Multiple scenario reordering, renaming, and run-settings updates throughout January 2026.

---

## November 2025 (documentation)

- Added the settings and output documentation PDF (`FEM_settings_and_output_documentation.pdf`) and linked it from the README. (9ee05ec, November 18, 2025)
- Added a citation section to the README. (c43281c, November 26, 2025)

---

## [1.0.0] — November 18, 2025

Initial public release (48c96b9): Pyomo/Gurobi-based electricity market model for Switzerland and neighboring countries, including data preparation (TYNDP import, district heating, industrial load), model core with central and common components, aggregation and result export tooling, cluster run scripts, input datasets (demand, RES, hydro, NTC, costs), and scenario definitions.
