"""The model runs on a plain Poetry environment: Pyomo calls Gurobi through gurobi.sh, so no module may
import the Python package gurobipy, which the project does not depend on (README, Euler section)."""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_FOLDERS = ("model", "data_prep", "utils", "aggregation", "scenarios", "cluster_runs")


def test_no_source_module_imports_gurobipy() -> None:
    # Arrange
    pattern = re.compile(r"^\s*(import gurobipy|from gurobipy)", re.M)
    sources = [p for folder in SOURCE_FOLDERS for p in (REPO_ROOT / folder).rglob("*.py")]
    sources += [REPO_ROOT / "run_scenarios.py", REPO_ROOT / "run_scenarios_hpc.py"]

    # Act
    offenders = [str(p.relative_to(REPO_ROOT)) for p in sources if pattern.search(p.read_text(encoding="utf-8"))]

    # Assert
    assert offenders == []
