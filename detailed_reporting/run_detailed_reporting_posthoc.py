"""Post-hoc runner for detailed_reporting.

Applies `generate_detailed_reports` to scenario folders that were modelled
without the in-pipeline call (e.g. multi-subscenario runs under
`output/20260311/`). Reads CSV outputs directly with `model=None`; for each
scenario, one report is produced per subscenario into
`output/<scenario_name>/detailed_reporting/<subscenario>/`.

Run from the repo root:

    python -m detailed_reporting.run_detailed_reporting_posthoc
"""

from typing import List

from detailed_reporting.constants import list_subscenarios
from detailed_reporting.reporting_main import generate_detailed_reports


DEFAULT_SCENARIOS: List[str] = []
for default_year in (2035, 2050):
    DEFAULT_SCENARIOS.extend([
        f"20260311/{default_year}_030_inv_CHbat",
        f"20260311/{default_year}_040_inv_CHbat",
        f"20260311/{default_year}_050_inv_CHbat",
        f"20260311/{default_year}_060_inv_CHbat",
        f"20260311/{default_year}_070_inv_CHbat",
        f"20260311/{default_year}_080_inv_CHbat",
        f"20260311/{default_year}_090_inv_CHbat",
        f"20260311/{default_year}_100_inv_CHbat",
    ])


def run(scenarios: List[str] = None) -> None:  # type: ignore
    scenarios = scenarios or DEFAULT_SCENARIOS
    failures = []
    for scenario_name in scenarios:
        try:
            subscenarios = list_subscenarios(scenario_name)
        except FileNotFoundError as exc:
            print(f"[SKIP] {scenario_name}: settings.csv not found ({exc})")
            failures.append((scenario_name, None, str(exc)))
            continue

        print(f"\n=== {scenario_name}: {len(subscenarios)} subscenario(s) ===")
        for sub in subscenarios:
            try:
                generate_detailed_reports(
                    model=None,
                    scenario_name=scenario_name,
                    subscenario=sub,
                )
            except Exception as exc:  # noqa: BLE001 -- report and continue
                print(f"[FAIL] {scenario_name} / {sub}: {type(exc).__name__}: {exc}")
                failures.append((scenario_name, sub, str(exc)))

    print("\n=== Summary ===")
    if failures:
        for s, sub, err in failures:
            print(f"  FAILED {s} / {sub}: {err}")
    else:
        print("  All reports generated successfully.")


if __name__ == "__main__":
    run()
