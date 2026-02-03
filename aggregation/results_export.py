import pandas as pd
from pathlib import Path


def par_var(var_list, scenario_name):
    for variable in var_list:
        # extract data
        extracted_info = variable.extract_values()

        # build output path
        output_path = Path("output") / scenario_name / f"{variable.name}.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # if not empty, export file with data
        if extracted_info != {}:
            # convert to DataFrame
            result_values = pd.DataFrame(
                index=extracted_info.keys(), data=extracted_info.values()
            )

            if len(result_values.columns) > 0:
                result_values.columns = ["value"] + result_values.columns.tolist()[1:]
            else:
                # Handle case where DataFrame has no columns (scalar values or empty mappings)
                result_values = pd.DataFrame(
                    index=extracted_info.keys(), 
                    data={"value": list(extracted_info.values())}
                )
            # extract names of the domain sets
            if variable.index_set()._implicit_subsets is None:
                header_list = [
                    variable.index_set().name,
                ]
            else:
                header_list = [
                    variable.__dict__["_implicit_subsets"][domain_counter].name
                    for domain_counter in range(
                        len(variable.__dict__["_implicit_subsets"])
                    )
                ]

            # Convert DataFrame to include the set names as the first row
            result_values.index.names = header_list

            result_values.to_csv(output_path)

        # export empty file
        else:
            result_values = pd.DataFrame()
            result_values.to_csv(output_path)


def constraints(constraint_list, scenario_name, model, write_csv=True):
    print("Exporting duals...")
    result_duals_dict = {}
    for constraint in constraint_list:
        data = {}
        counter = 0
        try:
            for index in constraint:
                if constraint.dim() == 0:
                    data[counter] = [constraint.name] + [
                        model.dual[constraint[index]]
                    ]  # NOTE: there will be so may constraints for limited energy plants, because every duration has its own constraint
                elif constraint.dim() != 1:
                    data[counter] = [i for i in index] + [model.dual[constraint[index]]]
                else:
                    data[counter] = [index] + [model.dual[constraint[index]]]
                counter += 1

            result_duals = pd.DataFrame.from_dict(data, orient="index")

            if constraint._implicit_subsets is None:
                header_list = [
                    constraint.name,
                ]
            else:
                header_list = [
                    constraint.__dict__["_implicit_subsets"][domain_counter].name
                    for domain_counter in range(
                        len(constraint.__dict__["_implicit_subsets"])
                    )
                ]

            result_duals.columns = header_list + ["value"]

            if write_csv:
                output_path = Path("output") / scenario_name / f"{constraint.name}_dual.csv"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                result_duals.to_csv(output_path, index=False)

            result_duals_dict[constraint.name] = result_duals

        except Exception as e:
            print(f"Error in exporting duals for {constraint.name}: {e}")
    return result_duals_dict


from input.cost_operation_invest_data import amortization_years_all
from data_prep.definitions_common import Map_plant_tech, Map_plantDH_tech


def _get_deannualization_factor(tech, discount_rate=0.05):
    """
    Calculate the factor to convert annualized costs back to overnight costs.
    
    Annualized = Overnight * (r / (1 - (1+r)^(-n)))
    Therefore: Overnight = Annualized * ((1 - (1+r)^(-n)) / r)
    
    Returns the factor ((1 - (1+r)^(-n)) / r)
    """
    amort_years = amortization_years_all.get(tech, 0)
    if amort_years <= 0:
        return 1.0  # No annualization, return as-is
    
    factor = (1 - (1 + discount_rate) ** (-amort_years)) / discount_rate
    return factor


def reduced_costs(variable_names, scenario_name, model, weight_in_objective_fcn, write_csv=True):
    """
    Export reduced costs for specified investment variables.
    
    For investment variables that are constrained to be equal across scenarios,
    the economically meaningful reduced cost is the SUM of rc_weighted across all scenarios.
    This sum tells you how much the total objective would worsen if you forced 1 more unit
    of investment (which affects all scenarios due to the equality constraint).
    
    NOTE: The reduced costs reflect the modeled period only. If the model covers fewer
    than 8760 hours, the investment cost (annualized for full year) is compared against
    operational shadow values from only the modeled hours. This is the correct marginal
    interpretation for the optimization as formulated.
    
    The reduced costs are also converted from annualized to overnight costs using the
    inverse of the annuity factor.
    
    Parameters:
        variable_names: list of variable names to export reduced costs for
        scenario_name: name of the scenario for output path
        model: Pyomo model with 'rc' suffix attached
        weight_in_objective_fcn: dict mapping scenario to its weight
        write_csv: whether to write CSV files
    
    Returns:
        dict mapping variable names to their reduced costs DataFrames
    """
    print("Exporting reduced costs...")
    
    result_rc_dict = {}
    
    # Determine which mapping to use based on variable name
    thermal_vars = {"genTh_max", "gen_energyTh_max", "pumpTh_max"}
    
    for var_name in variable_names:
        try:
            if not hasattr(model, var_name):
                print(f"  Warning: Variable '{var_name}' not found in model. Skipping.")
                continue
            
            # Select appropriate plant-to-tech mapping
            plant_tech_map = Map_plantDH_tech if var_name in thermal_vars else Map_plant_tech
                
            variable = getattr(model, var_name)
            data = {}
            counter = 0
            
            for index in variable:
                if variable[index] in model.rc:
                    rc_value = model.rc[variable[index]]
                    
                    # Extract plant and scenario from index (assumed to be last element if tuple)
                    if isinstance(index, tuple):
                        plant = index[0]  # plant is the first index
                        scen = index[-1]  # scenario is the last index
                        index_list = list(index)
                    else:
                        plant = index
                        scen = index
                        index_list = [index]
                    
                    data[counter] = index_list + [rc_value, plant]
                    counter += 1
            
            if not data:
                print(f"  No reduced costs found for '{var_name}'")
                continue
            
            result_rc = pd.DataFrame.from_dict(data, orient="index")
            
            # Build header from variable's index sets
            if variable._implicit_subsets is None:
                header_list = [variable.index_set().name]
            else:
                header_list = [
                    variable.__dict__["_implicit_subsets"][domain_counter].name
                    for domain_counter in range(len(variable.__dict__["_implicit_subsets"]))
                ]
            
            result_rc.columns = header_list + ["rc_weighted", "_plant"]
            
            # Create summary: sum reduced costs across scenarios for each plant
            # This is the economically meaningful value for investment variables
            # constrained to be equal across scenarios
            plant_columns = header_list[:-1]  # all columns except 'Scenarios'
            if plant_columns:
                rc_summary = result_rc.groupby(plant_columns, as_index=False).agg({
                    "rc_weighted": "sum",
                    "_plant": "first"  # keep plant name for tech lookup
                })
                rc_summary = rc_summary.rename(columns={"rc_weighted": "rc_total_annualized"})
            else:
                # If there's only the scenario index, just sum everything
                rc_summary = pd.DataFrame({
                    "rc_total_annualized": [result_rc["rc_weighted"].sum()],
                    "_plant": [result_rc["_plant"].iloc[0]] if len(result_rc) > 0 else ["unknown"]
                })
            
            # Add technology and calculate break-even overnight cost
            # The break-even point is where annuity - rc = 0, meaning the investment becomes profitable
            # break_even_overnight = overnight_cost × (annuity - rc) / annuity
            # reduction_needed_overnight = overnight_cost × rc / annuity = overnight_cost - break_even_overnight
            
            # Get the appropriate investment cost parameter
            if var_name == "gen_max":
                inv_param = model.investment_genmax_slp
            elif var_name == "genTh_max":
                inv_param = model.investment_genmax_slpTh
            elif var_name == "gen_energy_max":
                inv_param = model.investment_emax_slp
            elif var_name == "gen_energyTh_max":
                inv_param = model.investment_emax_slpTh
            else:
                inv_param = None
            
            def get_break_even_info(row):
                plant = row["_plant"]
                tech = plant_tech_map.get(plant, "unknown")
                deannualization_factor = _get_deannualization_factor(tech)
                
                # Get the annuity (investment cost parameter) for this plant
                # Investment costs are identical across scenarios, so just take the first one
                first_scen = list(model.Scenarios)[0]
                if inv_param is not None:
                    try:
                        val = inv_param[plant, first_scen]
                        annuity = val.value if hasattr(val, 'value') else val
                    except:
                        annuity = 0
                else:
                    annuity = 0
                
                rc_total = row["rc_total_annualized"]
                
                # Calculate break-even overnight cost
                # break_even_overnight = overnight × (annuity - rc) / annuity
                if annuity > 0:
                    overnight_cost = annuity * deannualization_factor
                    break_even_overnight = overnight_cost * (annuity - rc_total) / annuity
                    reduction_needed = overnight_cost - break_even_overnight
                else:
                    overnight_cost = 0
                    break_even_overnight = 0
                    reduction_needed = 0
                
                return tech, annuity, overnight_cost, break_even_overnight, reduction_needed
            
            rc_summary[["technology", "annuity", "overnight_cost", "break_even_overnight", "reduction_needed_overnight"]] = rc_summary.apply(
                lambda row: pd.Series(get_break_even_info(row)), axis=1
            )
            
            # Clean up: remove helper column and reorder
            rc_summary = rc_summary.drop(columns=["_plant"])
            cols = plant_columns + ["technology", "rc_total_annualized", "annuity", "overnight_cost", "break_even_overnight", "reduction_needed_overnight"]
            rc_summary = rc_summary[cols]
            
            if write_csv:
                # Export summary only (summed across scenarios, with overnight costs)
                summary_path = Path("output") / scenario_name / f"{var_name}_reduced_cost.csv"
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                rc_summary.to_csv(summary_path, index=False)
                # print(f"  Exported reduced costs for {var_name}")
            
            result_rc_dict[var_name] = rc_summary
            
        except Exception as e:
            print(f"  Error in exporting reduced costs for {var_name}: {e}")
    
    return result_rc_dict
