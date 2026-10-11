from pyomo.opt import SolverStatus, TerminationCondition


def require_optimal_solve(result, log_path):
    """
    Raises an error unless the solver reports an optimal solution (status ok, termination condition optimal).
    After any other outcome Pyomo only logs a warning, and the model holds no solution or a non-optimal one,
    so exporting its values would write meaningless results.
    """
    status = result.solver.status
    termination_condition = result.solver.termination_condition
    if status != SolverStatus.ok or termination_condition != TerminationCondition.optimal:
        raise RuntimeError(
            f"The solve did not end optimal (solver status: {status}, termination condition: {termination_condition}); "
            f"no results are exported. Solver log: {log_path}"
        )
