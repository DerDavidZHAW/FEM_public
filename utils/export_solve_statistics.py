import pyomo.environ as pyo
import pandas as pd
from pathlib import Path
import csv
from pyomo.core import Constraint, value
import gurobipy as gp
from pyomo.repn import generate_standard_repn

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

def export_all_variables(model, scenario, filename='all_variables.csv'):
    """
    Export all variables with their bounds and values to CSV.
    Works with variables of any dimension.
    """

    # where to store the file
    output_dir = Path("output") / scenario
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / filename

    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['variable_name', 'index', 'lower_bound', 'value', 'upper_bound', 'domain', 'fixed'])
        
        for var in model.component_objects(pyo.Var, active=True):
            var_name = var.name
            
            if var.is_indexed():
                for index in var:
                    v = var[index]
                    lb = v.lb if v.lb is not None else ''
                    ub = v.ub if v.ub is not None else ''
                    val = v.value if v.value is not None else ''
                    domain = str(v.domain) if hasattr(v, 'domain') else ''
                    fixed = v.fixed if hasattr(v, 'fixed') else False
                    
                    if isinstance(index, tuple):
                        index_str = ','.join(str(i) for i in index)
                    else:
                        index_str = str(index)
                    writer.writerow([var_name, index_str, lb, val, ub, domain, fixed])
            else:
                lb = var.lb if var.lb is not None else ''
                ub = var.ub if var.ub is not None else ''
                val = var.value if var.value is not None else ''
                domain = str(var.domain) if hasattr(var, 'domain') else ''
                fixed = var.fixed if hasattr(var, 'fixed') else False
                
                writer.writerow([var_name, '', lb, val, ub, domain, fixed])
    
    print(f"Variables exported to: {output_file}")

def export_all_parameters(model, scenario, filename='all_parameters.csv'):
    """
    Export all parameters with numeric values to CSV.
    Works with parameters of any dimension.
    """

    # where to store the file
    output_dir = Path("output") / scenario
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / filename

    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['parameter_name', 'index', 'value'])
        
        for param in model.component_objects(pyo.Param, active=True):
            param_name = param.name
            
            if param.is_indexed():
                for index in param:
                    value = param[index]
                    if isinstance(value, (int, float)):
                        if isinstance(index, tuple):
                            index_str = ','.join(str(i) for i in index)
                        else:
                            index_str = str(index)
                        writer.writerow([param_name, index_str, value])
            else:
                value = param.value
                if isinstance(value, (int, float)):
                    writer.writerow([param_name, '', value])

def export_all_constraints(model, scenario, filename='all_constraints.csv'):
    """
    Export all constraints to CSV including the actual RHS that Gurobi sees.
    
    Pyomo restructures constraints: e.g. 'soc <= gen_energy_max' becomes 
    'soc - gen_energy_max <= 0'. This function computes the canonical form
    to show the actual RHS values sent to the solver.
    """

    # where to store the file
    output_dir = Path("output") / scenario
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / filename

    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            'constraint_name', 'index', 
            'pyomo_lower', 'pyomo_body', 'pyomo_upper',  # Original Pyomo view
            'rhs_lower', 'rhs_upper', 'constant_term',   # Canonical form (what solver sees)
            'max_abs_coef', 'dual'
        ])
        
        for con in model.component_objects(Constraint, active=True):
            con_name = con.name
            
            indices = [None] if not con.is_indexed() else list(con)
            
            for index in indices:
                c = con if index is None else con[index]
                if not c.active:
                    continue
                    
                # Original Pyomo view
                pyomo_lower = value(c.lower) if c.lower is not None else ''
                pyomo_body = value(c.body)
                pyomo_upper = value(c.upper) if c.upper is not None else ''
                
                # Get the canonical representation (what solver sees)
                # body = sum(coef * var) + constant
                # constraint: lower <= body <= upper
                # canonical:  lower - constant <= sum(coef * var) <= upper - constant
                try:
                    repn = generate_standard_repn(c.body, compute_values=True)
                    constant = repn.constant if repn.constant is not None else 0.0
                    
                    # RHS values that solver sees
                    rhs_lower = (value(c.lower) - constant) if c.lower is not None else ''
                    rhs_upper = (value(c.upper) - constant) if c.upper is not None else ''
                    
                    # Get max absolute coefficient
                    if repn.linear_coefs:
                        max_abs_coef = max(abs(coef) for coef in repn.linear_coefs)
                    else:
                        max_abs_coef = 0.0
                        
                except Exception as e:
                    constant = ''
                    rhs_lower = ''
                    rhs_upper = ''
                    max_abs_coef = ''
                
                try:
                    dual = model.dual[c]
                except (KeyError, AttributeError):
                    dual = ''
                
                if index is None:
                    index_str = ''
                elif isinstance(index, tuple):
                    index_str = ','.join(str(i) for i in index)
                else:
                    index_str = str(index)
                    
                writer.writerow([
                    con_name, index_str,
                    pyomo_lower, pyomo_body, pyomo_upper,
                    rhs_lower, rhs_upper, constant,
                    max_abs_coef, dual
                ])
    
    print(f"Constraints exported to: {output_file}")

def _check_objective_coefficients(model, output_dir, threshold=1e6):
    """
    Analyze objective function to find variables with large coefficients.
    Saves problematic coefficients to a CSV file for debugging.
    
    Returns list of (variable_name, index, coefficient) tuples for coefficients > threshold.
    """
    large_coefficients = []
    
    # Get the objective expression
    obj = model.OBJ
    if obj is None:
        return large_coefficients
    
    try:
        # Repn = representation of the objective in standard form
        from pyomo.repn import generate_standard_repn
        repn = generate_standard_repn(obj.expr, compute_values=True)
        
        if repn is None:
            return large_coefficients
        
        # Check linear terms
        if repn.linear_vars is not None:
            for var, coef in zip(repn.linear_vars, repn.linear_coefs):
                if abs(coef) > threshold:
                    var_name = var.name if hasattr(var, 'name') else str(var)
                    large_coefficients.append({
                        'variable': var_name,
                        'coefficient': coef,
                        'abs_coefficient': abs(coef),
                        'type': 'linear'
                    })
        
        # Check quadratic terms (if any)
        quad_vars = getattr(repn, 'quadratic_vars', None)
        quad_coefs = getattr(repn, 'quadratic_coefs', None)
        if quad_vars is not None and quad_coefs is not None:
            for (var1, var2), coef in zip(quad_vars, quad_coefs):
                if abs(coef) > threshold:
                    var_name = f"{var1.name}*{var2.name}" if hasattr(var1, 'name') else str(var1)
                    large_coefficients.append({
                        'variable': var_name,
                        'coefficient': coef,
                        'abs_coefficient': abs(coef),
                        'type': 'quadratic'
                    })
    
    except Exception as e:
        print(f"  Warning: Could not fully analyze objective function: {e}")
        # Fallback: try to get info from model structure
        return large_coefficients
    
    # Save to CSV if any large coefficients found
    if large_coefficients:
        import pandas as pd
        df = pd.DataFrame(large_coefficients)
        df = df.sort_values('abs_coefficient', ascending=False)
        
        output_path = Path(output_dir) / "large_objective_coefficients.csv"
        df.to_csv(output_path, index=False)
        
        # Also print top 10 to console
        print("  Top 10 largest coefficients:")
        for i, row in df.head(10).iterrows():
            print(f"    {row['variable']}: {row['coefficient']:.2e}")
    
    return large_coefficients
