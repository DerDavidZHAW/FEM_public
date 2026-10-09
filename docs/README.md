# FEM documentation

Guides for people and coding agents working with the Future Markets model. Installation and
HPC setup are in the [main README](../README.md); rules for coding agents are in
[AGENTS.md](../AGENTS.md).

| Guide | What it covers | Read it when |
|---|---|---|
| [codebase_map.md](codebase_map.md) | How a run flows through the code; which file to change for which task | Changing the model, its settings, inputs or exports |
| [running.md](running.md) | Scenario CSVs, test run, unit tests, aggregation and plots, HPC notes | Running anything |
| [outputs.md](outputs.md) | The files in `output/<run>/`: time index, nodes, dispatch, capacities, trade | Reading results |
| [duals.md](duals.md) | Which duals are exported, their units, signs and weights; reduced costs | Using prices, rents or any `*_dual.csv` |
| [multi_weather_year.md](multi_weather_year.md) | Meta-scenarios with several sub-scenarios: setup, shared investment, outputs, memory | Running or reading a multi-weather-year optimisation |
| [../input/demand/adjustments/README.md](../input/demand/adjustments/README.md) | Overlay files that change district-heating demand per scenario | Perturbing DH demand |
| [../data_prep/historical/README.md](../data_prep/historical/README.md) | Downloading observed CH and neighbour prices, border NTC, CH generation, load and reservoirs; index of the analyses of that data (e.g. trade versus NTC) | Back-casting a historical year in `CH_only` mode |

Every guide starts with a "Checked against" line: the commit of `main` its statements were
verified on. A statement about code changed after that commit may be stale; check the code.
