# Future Markets (FEM): guide for coding agents

FEM is a Pyomo linear program of the European electricity and district-heating system, with
Switzerland in detail, solved with Gurobi at hourly resolution. One **meta-scenario** is one
optimisation; its **sub-scenarios** (usually weather years) are solved jointly and share investment.

Setup, Euler and SciCORE: `README.md`. All guides: `docs/README.md`.

## Rules

- **Errors over fallbacks.** When a required value, file or setting is missing, raise a clear
  error. Substitute a default only where the code states why it is exact (e.g. scaling factor 1
  for a constraint the model does not scale).
- **Derive, never fit.** Get model relationships from the constraint code and the input files.
  Curve fitting or regression on results to recover them is not accepted.
- **Tests with every change.** New or changed functions come with unit tests in `tests/` that
  fail on the old code. Run `poetry run pytest`. The tests do not build or solve the model, so
  also do a **test run** (`docs/running.md`) after model changes.
- **Grep the big files.** `model/components_common.py` (sets, variables, constraints, objective)
  and `model/data_import_fcns.py` are 2,300 to 2,800 lines: search them and read only the
  functions you need.
- **Restore `target_csv`.** A test run edits `target_csv` in `scenarios/scenarios.py`; set it
  back afterwards. The Euler job array reads the same line.
- **Commit source only.** `output/` and `plots/` are gitignored. `paper_*/` folders left over from
  another branch are not, so leave them unstaged.
- **Keep the guides true.** When you change behaviour a guide in `docs/` describes, update that
  guide and its "Checked against" line in the same commit.

## Where to read

| Task | Read |
|---|---|
| Add or change a constraint, variable, cost term, setting or input | `docs/codebase_map.md` |
| Define scenarios, test run, tests, aggregation, HPC runs | `docs/running.md` |
| Interpret files in `output/<run>/` | `docs/outputs.md` |
| Prices, capacity rents, any `*_dual.csv` or `*_reduced_cost.csv` | `docs/duals.md` |
| Several weather years in one optimisation | `docs/multi_weather_year.md` |
| Perturb district-heating demand | `input/demand/adjustments/README.md` |
| Browser dashboard of one run | `README.md`, section "Standalone Results Dashboard" |
