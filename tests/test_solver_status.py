"""Unit tests for require_optimal_solve (model/solver_status.py).

After a solve that did not end optimal, Pyomo only logs a warning; the model then holds no
solution (or a non-optimal one), so results must not be exported. The tests build solver
results by hand; no solver is used.
"""
import pytest
from pyomo.opt import SolverResults, SolverStatus, TerminationCondition

from model.solver_status import require_optimal_solve


def _result(status, termination_condition):
    result = SolverResults()
    result.solver.status = status
    result.solver.termination_condition = termination_condition
    return result


def test_optimal_solve_passes():
    require_optimal_solve(_result(SolverStatus.ok, TerminationCondition.optimal), "output/x/solver_log.log")


@pytest.mark.parametrize("status, termination_condition", [
    (SolverStatus.warning, TerminationCondition.infeasible),            # as Gurobi reports an infeasible LP
    (SolverStatus.warning, TerminationCondition.infeasibleOrUnbounded),
    (SolverStatus.aborted, TerminationCondition.maxTimeLimit),
    (SolverStatus.warning, TerminationCondition.optimal),
])
def test_solve_that_did_not_end_optimal_raises(status, termination_condition):
    with pytest.raises(RuntimeError, match="output/x/solver_log.log"):
        require_optimal_solve(_result(status, termination_condition), "output/x/solver_log.log")
