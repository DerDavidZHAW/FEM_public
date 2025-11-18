import pyomo.environ as pyo
import pandas as pd
from pathlib import Path
import csv
from pyomo.core import Constraint, value

def export_fcn(scenario_name, result, model, solve_time):
    termination_condition = str(result.solver.termination_condition)
    solve_status = str(result.solver.status)
    obj_value = pyo.value(model.OBJ)
    num_vars = len(list(model.component_data_objects(pyo.Var, active=True)))
    num_constraints = len(
        list(model.component_data_objects(pyo.Constraint, active=True))
    )

    # Creating a dictionary to hold the variables
    data = {
        "Variable": [
            "Termination_Condition",
            "Solver_Status",
            "Objective_Value",
            "solve_time",
            "NO_Variables",
            "NO_Constraints",
        ],
        "Value": [
            termination_condition,
            solve_status,
            obj_value,
            solve_time,
            num_vars,
            num_constraints,
        ],
    }

    # Creating a DataFrame from the dictionary
    df = pd.DataFrame(data)

    # Build output path
    output_path = Path("output") / scenario_name / "statistics.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Exporting the DataFrame to a CSV file
    df.to_csv(output_path, index=False)


def export_duals(model, scenario):

    # where to store the file
    output_dir = Path("output") / scenario
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "dual_report.csv"

    # tolerance for binding check
    BINDING_TOL = 1e-6

    with open(output_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Constraint_Name', 'Index', 'Dual_Value', 'Lower_Bound', 'Upper_Bound', 'Body_Value', 'Binding', 'Hour'])

        for constr in model.component_objects(Constraint, active=True):
            constr_name = constr.name
            for index in constr:
                c = constr[index]
                dual_val = model.dual.get(c, float('nan'))
                body_val = value(c.body)
                lb = value(c.lower) if c.has_lb() else float('-inf')
                ub = value(c.upper) if c.has_ub() else float('inf')

                # Check binding condition
                binding = False
                if c.has_ub() and abs(body_val - ub) <= BINDING_TOL:
                    binding = True
                if c.has_lb() and abs(body_val - lb) <= BINDING_TOL:
                    binding = True

                # Try to extract hour if index includes it
                hour = None
                try:
                    # if index is tuple
                    if isinstance(index, tuple):
                        for idx in index:
                            if idx in model.T:
                                hour = idx
                                break
                    else:
                        if index in model.T:
                            hour = index
                except:
                    hour = None

                writer.writerow([constr_name, index, dual_val, lb, ub, body_val, binding, hour])

    print(f"Duals exported to: {output_file}")