import pyomo.environ as pyo
import pandas as pd
from pathlib import Path
from data_prep.definitions_common import Map_plant_node, Map_plant_tech
from pyomo.core import Constraint
from model.structural_parameters import Map_plant_tech_cost_component

def determine_hourly_price_setter(
    scenario,
    sub_scenarios,
    model,
    el_prices,
    node='CH00',
    plant_node=Map_plant_node
):
    """
    Determine the hourly price-setting technology for a given node and scenario.
    Returns both the full list of price setters and a count by technology.
    """

    # Extract required sets and parameters from the model
    weight = model.weight_in_objective_fcn[sub_scenarios]

    # Duals and parameters
    electrolyzers_dual_dict = extract_all_electrolyzer_duals(model, list(model.Map_node_country), sub_scenarios)
    duals_dsr = extract_duals_dsr_daily_balance(model, "test_two")  # Optional, currently unused
    op_qdr_dict = get_operation_qdr_dict(model)
    watervalues = determine_duals_p_t_s(model, model.storage_soc)

    # Determine which nodes are price-relevant ("in the pool")
    pool_nodes = build_pool_same_price(el_prices, node)

    # Build plant-level data used for bidding price comparison
    pool_plants = build_candidate_plants_pool(
        scenario,
        pool_nodes,
        plant_node,
        model.gen,
        model.storage_charge,
        model.Data_plant_flex_d_within_window,
        model.pmp_max,
        model.avail_plant,
        model.V2G_charging_power_rate,
        model.storage_charge_eff_out,
        model.gen_max,
        model.operation_slp,
        model.operation_slpTh,
        watervalues,
        electrolyzers_dual_dict,
        duals_dsr,
        op_qdr_dict,
        model.BA_names,
    )

    # Run price-setting logic and return both raw plant list and counted technologies
    price_setting_plants, counted_technologies = pick_plants(
        pool_plants, el_prices, sub_scenarios, scenario, weight, node
    )

    return price_setting_plants, counted_technologies

def build_meta_data_list(ntc_meta_data, line_node):
    """
    Constructs a DataFrame mapping each interconnection to its start and end nodes.

    Parameters:
    - ntc_meta_data (iterable): List or iterable of interconnection IDs.
    - line_node (dict): Dictionary mapping each interconnection ID to a dict with 'start_node' and 'end_node'.

    Returns:
    - pd.DataFrame: DataFrame indexed by 'Interconnection' with columns 'Start_Node' and 'End_Node'.
    """
    # Use list comprehension for cleaner and faster construction
    interconnection_data = [
        {
            "Interconnection": l,
            "Start_Node": line_node[l]["start_node"],
            "End_Node": line_node[l]["end_node"]
        }
        for l in ntc_meta_data
    ]

    # Convert list to DataFrame and set index
    return pd.DataFrame(interconnection_data).set_index("Interconnection")


def create_ntc_list(scenario, hours, ntc_hourly_data, interconnection_meta_data):
    """
    Builds a DataFrame of hourly export values for all interconnections in a scenario.

    Parameters:
    - scenario (str): Name of the scenario.
    - hours (iterable): List or iterable of time periods (e.g., 't_0001').
    - ntc_hourly_data (dict-like): Pyomo results dict with keys (line, hour, scenario).
    - interconnection_meta_data (pd.DataFrame): DataFrame indexed by interconnection name.

    Returns:
    - pd.DataFrame: Contains columns ['Line', 'Hour', 'Export_MWh'].
    """
    # Use list comprehension for better performance and cleaner code
    export_data = [
        {
            "Line": l,
            "Hour": t,
            "Export_MWh": pyo.value(ntc_hourly_data[l, t, scenario])
        }
        for l in interconnection_meta_data.index
        for t in hours
    ]

    return pd.DataFrame(export_data)

from collections import defaultdict, deque

def build_pool_same_price(el_prices: pd.DataFrame, node: str) -> dict:
    """
    For each hour t, find all nodes with the same value as the given node.

    Parameters:
    - el_prices (pd.DataFrame): Must contain columns ['T', 'Node', 'Scenarios', 'value'].
    - node (str): Reference node.

    Returns:
    - dict: {t: set(nodes with same price as 'node' at time t)}
    """

    # Ensure required columns are present
    required_cols = {'T', 'Node', 'value'}
    if not required_cols.issubset(el_prices.columns):
        raise ValueError(f"el_prices must contain columns: {required_cols}")

    pool = {}

    # Loop over each hour
    for t in el_prices['T'].unique():
        # Value of the given node at t
        ref_val = el_prices.loc[(el_prices['T'] == t) & (el_prices['Node'] == node), 'value']

        ref_val = ref_val.iloc[0] # type: ignore

        # Find all nodes at t with same value
        same_nodes = el_prices.loc[
            (el_prices['T'] == t) & (abs(el_prices['value'] - ref_val) <= 1e-3),  # Allow small tolerance
            'Node'
        ].unique() # type: ignore

        pool[t] = set(same_nodes)

    return pool


def create_binary_list_for_ntc_utilisation(ntcs, export_limits, import_limits, t, sub_scenarios):
    """
    Adds a 'running_at_limit' column to the given DataFrame of NTCs,
    indicating (1 or 0) whether each interconnection is operating near its export or import limit.

    Parameters:
    - ntcs (pd.DataFrame): Must have 'Export_MWh' as column and index as interconnection lines.
    - export_limits (dict): Export limits indexed by (line, hour, scenario).
    - import_limits (dict): Import limits indexed by (line, hour, scenario).
    - t (str): Current time step.
    - sub_scenarios (str): Name of the scenario.

    Returns:
    - pd.DataFrame: Same as input `ntcs`, with added column 'running_at_limit'.
    """
    at_limit_flags = []

    for line, export_val in ntcs["Export_MWh"].items():
        # Try to get export and import limits; fallback logic for missing keys
        export_limit = export_limits.get((line, t, sub_scenarios), None)
        import_limit = import_limits.get((line, t, sub_scenarios), -export_limit if export_limit is not None else None)

        # Check if at limit within tolerance
        is_at_limit = (
            export_limit is not None and abs(abs(export_val) - export_limit) <= 1
        ) or (
            import_limit is not None and abs(abs(export_val) - import_limit) <= 1
        )

        at_limit_flags.append(int(is_at_limit))

    ntcs = ntcs.copy()  # avoid modifying original DataFrame
    ntcs["running_at_limit"] = at_limit_flags
    return ntcs

def build_candidate_plants_pool(
    scenario,
    pool,
    plant_node,
    gen,
    storage_charge,
    storage_charge_limit,
    pmp_max,
    avail_plant,
    V2G_charging_power_rate,
    storage_charge_eff_out,
    gen_max,
    operation_slp,
    operation_slpTh,
    watervalue,
    electrolyzers_dual_dict,
    duals_dsr,
    op_qdr_dict,
    BA_names,
):
    """
    Constructs a pool of candidate plants (generators and consumers) for price setting,
    considering operation and water value information. Results are exported as a CSV.

    Parameters:
    - scenario (str): Name of the scenario.
    - pool (dict): Time-indexed mapping of included countries/nodes.
    - plant_node (dict): Maps plant ID to its node.
    - gen (pyo.Var): Generation variable (3D).
    - storage_charge (pyo.Var): Charging variable (3D).
    - storage_charge_limit (dict): Charging limits for electrolyzers.
    - pmp_max (pyo.Var): Max capacity for other charging technologies.
    - avail_plant (dict): Availability factors by (plant, time, scenario).
    - V2G_charging_power_rate (dict): Rate for V2G.
    - storage_charge_eff_out (pyo.Param): Charging efficiency.
    - gen_max (pyo.Var): Installed capacity.
    - operation_slp / operation_slpTh: Operating costs (electrical / thermal).
    - watervalue (dict): Water value by (plant, time, scenario).
    - electrolyzers_dual_dict (dict): Watervalue-like duals for electrolyzers.
    - duals_dsr (dict): DSR duals by (plant, day), currently unused.
    - op_qdr_dict (dict): Quadratic coefficients (default to 0 if not present).
    - BA_names (list): List of Building Archetypes. They are skipped in the pool because it is unclear how they should be treated.

    Returns:
    - pd.DataFrame: Candidate plant pool with all marginal values.
    """

    gen_data = []

    # -------- GENERATION SIDE --------
    for (p, t, s) in gen:
        gen_val = pyo.value(gen[p, t, s])
        max_gen_val = pyo.value(gen_max[p, s]) * avail_plant[p, t, s]
        op_slp = pyo.value(operation_slp[p, s])

        # Determine marginal cost depending on cost type
        cost_type = Map_plant_tech_cost_component[Map_plant_tech[p]]
        if cost_type == "cap_op":
            marginal_cost = op_slp + 2 * gen_val * op_qdr_dict.get((p, s), 0.0) # type: ignore
        elif cost_type == "cap_op_energy":
            marginal_cost = op_slp
        else:
            marginal_cost = 0.0

        # Handle potential missing charging efficiency
        try:
            eff_out = pyo.value(storage_charge_eff_out[p, s])
        except (KeyError, AttributeError, ValueError):
            eff_out = 1.0  # Default fallback value

        eff_out = pyo.value(eff_out) if hasattr(eff_out, 'value') else eff_out

        # Filter for eligible plant and partial loading
        if gen_val > 1e-3 and (max_gen_val - gen_val) > 1e-3 and plant_node[p] in pool[t]: # type: ignore
            watervalue_val = pyo.value(watervalue.get((p, t, s), 0.0))

            # # DSR fallback, currently unused
            # if "dsr" in p:
            #     d = get_day_of_year_from_timestamp(t)
            #     watervalue_val = duals_dsr.get((p, d), 0)

            gen_data.append({
                "Technology": p,
                "Hour": t,
                "Scenario": s,
                "Sign": "gen",
                "Generation_MWh": gen_val,
                "Eff_out": eff_out,
                "Max Generation_MWh": max_gen_val,
                "Marginal Cost": marginal_cost,
                "Watervalue": watervalue_val,
            })

    # -------- CONSUMPTION SIDE --------
    for (p, t, s) in storage_charge:
        if p in BA_names:
            continue # Skip Building Archetypes because it is not clear what they can set the price to. There is room for improvement here.

        charge_val = pyo.value(storage_charge[p, t, s])

        # Determine max consumption capacity
        if "electrolyzer" in p:
            charge_max = storage_charge_limit[p, s]['max_demand']
        elif "V2G_CH" in p:
            charge_max = V2G_charging_power_rate[p, t, s]
        else:
            charge_max = pyo.value(pmp_max[p, s]) * avail_plant[p, t, s]

        # Filter for eligible and partially used plant
        if charge_val > 1e-3 and (charge_max - charge_val) > 1e-3 and plant_node[p] in pool[t]: # type: ignore
            # Try get watervalue and eff_out
            watervalue_val = 0.0
            eff_out = 1.0

            # Slope cost: prefer electrical, fallback to dual for electrolyzer
            try:
                op_slp_val = pyo.value(operation_slp[p, s])
            except (KeyError, ValueError):
                if "electrolyzer" in p:
                    # If it's an electrolyzer, use the dual value
                    op_slp_val = electrolyzers_dual_dict.get(plant_node[p], 0.0)
                else:
                    # Default to 0 for other technologies
                    op_slp_val = 0.0

            # Try getting watervalue
            if (p, t, s) in watervalue:
                watervalue_val = pyo.value(watervalue[p, t, s])
                try:
                    eff_out_obj = pyo.value(storage_charge_eff_out[p,s])
                except (KeyError, AttributeError, ValueError):
                    eff_out_obj = 1.0  # Default fallback value

                eff_out = pyo.value(eff_out_obj) if hasattr(eff_out_obj, "value") else eff_out_obj

            # # DSR fallback, currently unused
            # if "dsr" in p:
            #     d = get_day_of_year_from_timestamp(t)
            #     watervalue_val = duals_dsr.get((p, d), 0)

            gen_data.append({
                "Technology": p,
                "Hour": t,
                "Scenario": s,
                "Sign": "con",
                "Generation_MWh": charge_val,
                "Eff_out": eff_out,
                "Max Generation_MWh": charge_max,
                "Marginal Cost": op_slp_val,
                "Watervalue": watervalue_val,
            })

    # -------- EXPORT TO CSV --------
    df_gen = pd.DataFrame(gen_data)
    output_path = Path("output") / scenario / "price_setting_plant_pool.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_gen.to_csv(output_path, index=False)

    return df_gen

def determine_duals_p_t_s(model, constraint):
    """
    Extracts dual values for a constraint indexed by (p, t, s), storing them in a dictionary.
    Duals are negated (often required for economic interpretation).

    Parameters:
    - model: A Pyomo model that has been solved with duals extracted.
    - constraint: A Pyomo Constraint object indexed by (p, t, s)

    Returns:
    - dict: {(p, t, s): dual value (negated)}
    """
    if not hasattr(model, "dual"):
        raise AttributeError("Model is missing 'dual' suffix. Ensure the solver is configured to return duals.")

    watervalue_dict = {
        (p, t, s): -dual
        for (p, t, s), con in constraint.items()
        if (dual := model.dual.get(con, None)) is not None
    }

    return watervalue_dict

def determine_energy_limit_marginal_costs(model):
    """
    Extracts the dual values (shadow prices) for the 'energy_limit' constraints
    from the given Pyomo model and constructs a DataFrame.

    These duals can be interpreted as marginal costs associated with
    the energy limit of each technology in each scenario.

    Parameters:
    - model: A Pyomo ConcreteModel instance with a 'dual' suffix attached 
             and a 'energy_limit' constraint indexed by (plant, scenario).

    Returns:
    - pd.DataFrame with columns ['Technology', 'Scenario', 'MarginalCost']
    """

    if not hasattr(model, "dual"):
        raise AttributeError("Dual values are not attached. Solve the model with duals enabled.")

    if not hasattr(model, "energy_limit"):
        raise AttributeError("The model does not contain a 'energy_limit' constraint.")

    energy_limit_duals = []

    for (p, s), con in model.energy_limit.items():
        if (dual := model.dual.get(con, None)) is not None:
            energy_limit_duals.append({
                "Technology": p,
                "Scenario": s,
                "MarginalCost": dual
            })

    return pd.DataFrame(energy_limit_duals)

def duals_electrolyzers(model, sub_scenarios):
    """
    Extracts dual values from constraints of the form:
    consume_tot_limit_{plant}_{n}_{scenario}

    Parameters:
    - model: Pyomo model with 'dual' suffix attached.
    - sub_scenarios (str): Sub-scenario name to tag the results.

    Returns:
    - pd.DataFrame with columns ['Technology', 'Scenario', 'MarginalCost']
    """

    if not hasattr(model, "dual"):
        raise AttributeError("Dual values are not attached to the model. Solve with duals enabled.")

    consume_duals = []

    for comp_name in model.component_map(Constraint):
        if comp_name.startswith("consume_tot_limit_"):
            con = getattr(model, comp_name)
            dual = model.dual.get(con, None)

            if dual is not None:
                # Example: consume_tot_limit_CH00_electrolyzer_1_test_two
                parts = comp_name.split("_")
                p = "_".join(parts[3:-2])  # captures everything between 'limit' and '1'

                consume_duals.append({
                    "Technology": p,
                    "Scenario": sub_scenarios,
                    "MarginalCost": dual
                })

    return pd.DataFrame(consume_duals)

def pick_plants(pool_plants, el_prices, sub_scenarios, scenario, weight, node):
    """
    Determines the price-setting plant for each hour and counts technology occurrences.

    Parameters:
    - pool_plants (pd.DataFrame): Pool of generating/consuming plants with operational info.
    - el_prices (pd.DataFrame): Electricity prices by hour and node.
    - sub_scenarios (str): Sub-scenario label.
    - scenario (str): Main scenario label.
    - weight (float): Weight to adjust actual price.
    - node (str): Node name to filter prices.

    Returns:
    - df_price_setting (pd.DataFrame): Row-wise info on the price-setting plant per hour.
    - counted_technologies (pd.DataFrame): Technology count summary.
    """

    # Filter relevant hours for the node
    all_hours = el_prices.loc[el_prices["Node"] == node, "T"].unique()
    price_setting_plants = []

    for t in all_hours:
        # Extract price for this hour
        hourly_price = el_prices.loc[
            (el_prices["T"] == t) & (el_prices["Node"] == node), "value"
        ].values[0]

        # Prepare fallback row
        new_row = {
            "Technology": "Zero price",
            "Hour": t,
            "Scenario": sub_scenarios,
            "Sign": "gen",
            "Marginal Cost": 0.0,
            "Watervalue": 0.0,
            "Bidding price": 0.0,
            "Actual Price": hourly_price,
        }

        # Filter pool to only those active at hour t
        hour_plants = pool_plants[pool_plants["Hour"] == t].copy()

        if hour_plants.empty:
            price_setting_plants.append(new_row)
            continue

        # Compute bidding prices
        hour_plants["Bidding price"] = 0.0

        # For consumers (e.g. storage charging): max(MC, watervalue * eff_out)
        mask_con = hour_plants["Sign"] == "con"
        hour_plants.loc[mask_con, "Bidding price"] = pd.concat([
            hour_plants.loc[mask_con, "Marginal Cost"],
            hour_plants.loc[mask_con, "Watervalue"] * hour_plants.loc[mask_con, "Eff_out"]
        ], axis=1).max(axis=1)

        # For generators: max(MC, watervalue / eff_out + MC)
        mask_gen = hour_plants["Sign"] == "gen"
        hour_plants.loc[mask_gen, "Bidding price"] = pd.concat([
            hour_plants.loc[mask_gen, "Marginal Cost"],
            hour_plants.loc[mask_gen, "Watervalue"] / hour_plants.loc[mask_gen, "Eff_out"] + hour_plants.loc[mask_gen, "Marginal Cost"]
        ], axis=1).max(axis=1)

        # Select the price-setting plant
        if hourly_price < 1e-3:
            selected = new_row
        else:
            top_row = hour_plants.loc[hour_plants["Bidding price"].idxmax()]
            selected = {
                "Technology": top_row["Technology"],
                "Hour": t,
                "Scenario": sub_scenarios,
                "Sign": top_row["Sign"],
                "Marginal Cost": top_row["Marginal Cost"],
                "Watervalue": top_row["Watervalue"],
                "Bidding price": top_row["Bidding price"],
                "Actual Price": hourly_price / weight,
            }

        price_setting_plants.append(selected)

    # Compile full DataFrame
    df_price_setting = pd.DataFrame(price_setting_plants)

    # Apply technology name cleanup
    df_price_setting["Technology"] = df_price_setting["Technology"].apply(replace_with_dict)

    # Count tech occurrences
    counted_technologies = count_technologies(df_price_setting, scenario, sub_scenarios)

    return df_price_setting, counted_technologies

def get_electrolyzer_dual(model, node, scenario):
    """
    Extract the dual value of the constraint
    consume_tot_limit_{node}_electrolyzer_1_{scenario} from the model.

    Args:
        model: Pyomo model
        node: string, e.g., 'CH00'
        scenario: string, e.g., 'test_two'

    Returns:
        float: the dual value of the specified constraint
    """
    cons_name = f"consume_tot_limit_{node}_electrolyzer_1_{scenario}"
    # Try to fetch the constraint object
    cons = getattr(model, cons_name, None)
    if cons is None:
        raise KeyError(f"Constraint '{cons_name}' not found in the model.")
    # If indexed constraint, retrieve the single data instance
    if hasattr(cons, 'body'):
        # It's a ConstraintData
        return model.dual.get(cons, None)
    else:
        # It's a Constraint container, assume single index
        items = list(cons.values())
        if not items:
            raise KeyError(f"No instances found for constraint '{cons_name}'.")
        return model.dual.get(items[0], None)

def extract_all_electrolyzer_duals(model, node_list, scenario):
    """
    Extract all dual values for electrolyzer constraints in the model.

    Args:
        model: Pyomo model
        node_list: list of nodes, e.g., ['CH00', 'IT00', 'DE00', 'FR00', 'AT00', 'DKE1', 'DKW1', 'BE00', 'CZ00', 'ES00', 'UK00', 'HU00', 'LU00', 'NL00', 'PL00', 'PT00', 'SI00', 'SK00', 'HR00', 'SE01', 'SE02', 'SE03', 'SE04', 'NON1', 'NOM1', 'NOS0']
        scenario: string, e.g., 'test_two'

    Returns:
        dict: mapping of nodes to the respective dual value of the consume_tot_limit electrolyzer constraint
    """

    duals = {}

    for node in node_list:
        try:
            duals[node] = get_electrolyzer_dual(model, node, scenario)
        except KeyError:
            duals[node] = 0

    return duals

def extract_duals_dsr_daily_balance(model, scenario_name):
    """
    Extracts dual values from the 'dsr_daily_balance' constraint for a given scenario.
    
    Parameters:
    - model: Pyomo model that may contain 'dsr_daily_balance' constraint and 'dual' suffix.
    - scenario_name (str): Scenario name to filter relevant constraint tuples.
    
    Returns:
    - dict: Keys are (p, d), values are -dual values. Empty dict if constraint is missing.
    """
    duals_dsr = {}

    # If the constraint does not exist on the model, return empty result
    if not hasattr(model, 'dsr_daily_balance'):
        return duals_dsr

    # Loop through all indexed constraints
    for (p, d, s) in model.dsr_daily_balance:
        if s != scenario_name:
            continue

        constraint = model.dsr_daily_balance[p, d, s]
        dual_value = model.dual.get(constraint, 0.0)  # default to 0 if dual not present

        # Negative sign: convention used in the rest of your model
        duals_dsr[(p, d)] = -dual_value

    return duals_dsr

def get_day_of_year_from_timestamp(timestamp):
    """
    Convert a time stamp like 't_6554' to the corresponding day of the year,
    assuming 24 hours per day and starting from t_1.

    Returns an integer day in [1, 365] (or more, if the model covers multiple years).
    """
    try:
        hour_of_year = int(timestamp.split("_")[1])
        day_of_year = ((hour_of_year - 1) // 24) + 1
        return day_of_year
    except (IndexError, ValueError):
        raise ValueError(f"Invalid timestamp format: {timestamp}")

def get_operation_qdr_dict(model):
    """
    Retrieves the quadratic operational cost (operation_qdr) values from the model.

    If the parameter is missing, returns a dictionary with 0.0 for all (plant, scenario) combinations.

    Parameters:
    - model: Pyomo ConcreteModel containing operation_qdr or not.

    Returns:
    - dict: Keys are (plant, scenario) tuples, values are the corresponding operation_qdr values.
    """
    op_qdr_dict = {}

    has_op_qdr = hasattr(model, 'operation_qdr')

    for p in model.P_gen:
        for s in model.Scenarios:
            if has_op_qdr:
                op_qdr_dict[(p, s)] = pyo.value(model.operation_qdr[p, s])
            else:
                op_qdr_dict[(p, s)] = 0.0

    return op_qdr_dict

def count_technologies(df, scenario, subscenario):
    """
    Counts the number of occurrences of each unique value in the 'Technology' column,
    excluding rows where the actual and bidding prices differ too much.
    Adds a row for possibly misassigned entries and includes scenario info.

    Parameters:
    - df (pd.DataFrame): The DataFrame containing 'Technology', 'Actual Price', and 'Bidding price'.
    - scenario (str): Name of the main scenario.
    - subscenario (str): Name of the sub-scenario.

    Returns:
    - pd.DataFrame: A DataFrame with columns ['Technology', 'Count', 'Scenario', 'SubScenario']
    """
    if "Technology" not in df.columns:
        raise ValueError("The DataFrame must contain a 'Technology' column.")
    if "Actual Price" not in df.columns or "Bidding price" not in df.columns:
        raise ValueError("Missing 'Actual Price' or 'Bidding price' column.")

    # Identify possibly misassigned rows
    mismatch_mask = (df["Actual Price"] - df["Bidding price"]).abs() >= 0.1
    num_misassigned = mismatch_mask.sum()

    # Keep only well-matched rows
    df_valid = df[~mismatch_mask]

    # Count valid technology occurrences
    tech_counts = df_valid["Technology"].value_counts().reset_index(drop=True)
    tech_names = df_valid["Technology"].value_counts().index.to_list()

    # Create result DataFrame
    result_df = pd.DataFrame({
        "Technology": tech_names,
        "Count": tech_counts,
        "Scenario": scenario,
        "SubScenario": subscenario
    })

    # Add possibly misassigned row if applicable
    if num_misassigned > 0:
        result_df = pd.concat([
            result_df,
            pd.DataFrame.from_dict([{
                "Technology": "possibly misassigned",
                "Count": num_misassigned,
                "Scenario": scenario,
                "SubScenario": subscenario
            }]) # type: ignore
        ], ignore_index=True)

    return result_df

def aggregate_price_setting_data(scenario_name, sub_scenarios_list, model, dual_values_dict):
    """
    Aggregates both the detailed price-setting plants and technology counts across sub-scenarios.

    Parameters:
    - scenario_name (str): Name of the main scenario
    - sub_scenarios_list (list): List of sub-scenario names
    - model (pyomo.ConcreteModel): The solved Pyomo model
    - dual_values_dict (dict): Dictionary of dual values (e.g. from energy_balance)

    Returns:
    - df_price_setting_all (pd.DataFrame): Detailed hourly price-setting records
    - counts_all (pd.DataFrame): Aggregated technology counts
    """
    all_price_setting = []
    all_counts = pd.DataFrame(columns=["Technology", "Count", "Scenario", "SubScenario"])

    for sub_scen in sub_scenarios_list:
        # Get full list and counts per sub-scenario
        price_setting_plants, price_setting_plants_counted = determine_hourly_price_setter(
            scenario_name, sub_scen, model, dual_values_dict['energy_balance']
        )

        # Convert list of hourly plants to DataFrame
        df_hourly = pd.DataFrame(price_setting_plants)
        df_hourly["Scenario"] = scenario_name
        df_hourly["SubScenario"] = sub_scen
        all_price_setting.append(df_hourly)

        # Convert counts to DataFrame
        all_counts = pd.concat([all_counts, price_setting_plants_counted], ignore_index=True)

    # Combine both sets
    df_price_setting_all = pd.concat(all_price_setting, ignore_index=True)

    output_path_plants = Path("output") / scenario_name / "price_setting_plants.csv"
    output_path_plant_count = Path("output") / scenario_name / "price_setting_plants_count.csv"
    output_path_plants.parent.mkdir(parents=True, exist_ok=True)
    output_path_plant_count.parent.mkdir(parents=True, exist_ok=True)

    # Export
    df_price_setting_all.to_csv(output_path_plants, index=False)
    all_counts.to_csv(output_path_plant_count, index=False)
    print(f"Saved: {output_path_plants}")
    print(f"Saved: {output_path_plant_count}")

    return df_price_setting_all, all_counts

def replace_with_dict(value: str) -> str:
    replacement_dict = {
        "AT00_battery": "Battery abroad",
        "AT00_biomass": "Biomass abroad",
        "AT00_dam": "Dam abroad",
        "AT00_dsr": "DSR abroad",
        "AT00_electrolyzer": "Electrolyzer abroad",
        "AT00_gas": "Gas abroad",
        "AT00_oil": "Oil abroad",
        "AT00_psp_close": "Psp close abroad",
        "AT00_psp_open": "Psp open abroad",
        "BE00_battery": "Battery abroad",
        "BE00_biomass": "Biomass abroad",
        "BE00_dam": "Dam abroad",
        "BE00_dsr": "DSR abroad",
        "BE00_electrolyzer": "Electrolyzer abroad",
        "BE00_gas": "Gas abroad",
        "BE00_oil": "Oil abroad",
        "BE00_psp_close": "Psp close abroad",
        "BE00_psp_open": "Psp open abroad",
        "CH00_battery": "Battery CH",
        "CH00_dam": "Dam CH",
        "CH00_electrolyzer": "Electrolyzer CH",
        "CH00_psp_close": "Psp close CH",
        "CH01_battery": "Battery CH",
        "CH01_biomass": "Biomass CH",
        "CH01_CCGTCCS": "CCGTCCS CH",
        "CH01_other": "Other CH",
        "CH02_battery": "Battery CH",
        "CH02_biomass": "Biomass CH",
        "CH02_CCGTCCS": "CCGTCCS CH",
        "CH02_other": "Other CH",
        "CH03_battery": "Battery CH",
        "CH03_biomass": "Biomass CH",
        "CH03_CCGTCCS": "CCGTCCS CH",
        "CH03_nuclear": "Nuclear CH",
        "CH03_other": "Other CH",
        "CH04_battery": "Battery CH",
        "CH04_biomass": "Biomass CH",
        "CH04_CCGTCCS": "CCGTCCS CH",
        "CH04_other": "Other CH",
        "CH05_battery": "Battery CH",
        "CH05_biomass": "Biomass CH",
        "CH05_CCGTCCS": "CCGTCCS CH",
        "CH05_other": "Other CH",
        "CH06_battery": "Battery CH",
        "CH06_biomass": "Biomass CH",
        "CH06_CCGTCCS": "CCGTCCS CH",
        "CH06_other": "Other CH",
        "CH07_battery": "Battery CH",
        "CH07_biomass": "Biomass CH",
        "CH07_CCGTCCS": "CCGTCCS CH",
        "CH07_other": "Other CH",
        "CZ00_battery": "Battery abroad",
        "CZ00_biomass": "Biomass abroad",
        "CZ00_dam": "Dam abroad",
        "CZ00_electrolyzer": "Electrolyzer abroad",
        "CZ00_gas": "Gas abroad",
        "CZ00_hardcoal": "Hardcoal abroad",
        "CZ00_nuclear": "Nuclear abroad",
        "CZ00_psp_close": "Psp close abroad",
        "CZ00_psp_open": "Psp open abroad",
        "DE00_battery": "Battery abroad",
        "DE00_biomass": "Biomass abroad",
        "DE00_dam": "Dam abroad",
        "DE00_dsr": "DSR abroad",
        "DE00_electrolyzer": "Electrolyzer abroad",
        "DE00_gas": "Gas abroad",
        "DE00_hardcoal": "Hardcoal abroad",
        "DE00_oil": "Oil abroad",
        "DE00_psp_close": "Psp close abroad",
        "DE00_psp_open": "Psp open abroad",
        "DH_Alpen_CHPNew": "DH CH",
        "DH_Alpen_HPG": "DH CH",
        "DH_Alpen_HPNew": "DH CH",
        "DH_Alpen_resistiveNew": "DH CH",
        "DH_Jura_CHPNew": "DH CH",
        "DH_Jura_HPG": "DH CH",
        "DH_Jura_HPNew": "DH CH",
        "DH_Jura_resistiveNew": "DH CH",
        "DH_medium_CHPNew": "DH CH",
        "DH_medium_HPNew": "DH CH",
        "DH_medium_resistiveNew": "DH CH",
        "DH_Mittelland_CHPNew": "DH CH",
        "DH_Mittelland_HPG": "DH CH",
        "DH_Mittelland_HPNew": "DH CH",
        "DH_Mittelland_resistiveNew": "DH CH",
        "DH_Voralpen_CHPNew": "DH CH",
        "DH_Voralpen_HPG": "DH CH",
        "DH_Voralpen_HPNew": "DH CH",
        "DH_Voralpen_resistiveNew": "DH CH",
        "DKE1_battery": "Battery abroad",
        "DKE1_biomass": "Biomass abroad",
        "DKE1_electrolyzer": "Electrolyzer abroad",
        "DKE1_gas": "Gas abroad",
        "DKE1_oil": "Oil abroad",
        "DKW1_battery": "Battery abroad",
        "DKW1_biomass": "Biomass abroad",
        "DKW1_electrolyzer": "Electrolyzer abroad",
        "DKW1_gas": "Gas abroad",
        "DKW1_oil": "Oil abroad",
        "ES00_battery": "Battery abroad",
        "ES00_biomass": "Biomass abroad",
        "ES00_dam": "Dam abroad",
        "ES00_dsr": "DSR abroad",
        "ES00_electrolyzer": "Electrolyzer abroad",
        "ES00_gas": "Gas abroad",
        "ES00_nuclear": "Nuclear abroad",
        "ES00_psp_close": "Psp close abroad",
        "ES00_psp_open": "Psp open abroad",
        "EV_CH": "EV CH",
        "FR00_battery": "Battery abroad",
        "FR00_biomass": "Biomass abroad",
        "FR00_dam": "Dam abroad",
        "FR00_dsr": "DSR abroad",
        "FR00_electrolyzer": "Electrolyzer abroad",
        "FR00_gas": "Gas abroad",
        "FR00_nuclear": "Nuclear abroad",
        "FR00_oil": "Oil abroad",
        "FR00_psp_close": "Psp close abroad",
        "FR00_psp_open": "Psp open abroad",
        "HR00_battery": "Battery abroad",
        "HR00_biomass": "Biomass abroad",
        "HR00_dam": "Dam abroad",
        "HR00_dsr": "DSR abroad",
        "HR00_electrolyzer": "Electrolyzer abroad",
        "HR00_gas": "Gas abroad",
        "HR00_psp_close": "Psp close abroad",
        "HR00_psp_open": "Psp open abroad",
        "HU00_battery": "Battery abroad",
        "HU00_biomass": "Biomass abroad",
        "HU00_dam": "Dam abroad",
        "HU00_electrolyzer": "Electrolyzer abroad",
        "HU00_gas": "Gas abroad",
        "HU00_nuclear": "Nuclear abroad",
        "HU00_oil": "Oil abroad",
        "HU00_psp_close": "Psp close abroad",
        "HU00_psp_open": "Psp open abroad",
        "ILHT_Alpen_CHPNew": "ILHT CH",
        "ILHT_Alpen_HPNew": "ILHT CH",
        "ILHT_Alpen_resistiveNew": "ILHT CH",
        "ILHT_Alpensuedseite_CHPNew": "ILHT CH",
        "ILHT_Alpensuedseite_HPNew": "ILHT CH",
        "ILHT_Alpensuedseite_resistiveNew": "ILHT CH",
        "ILHT_Jura_CHPNew": "ILHT CH",
        "ILHT_Jura_HPNew": "ILHT CH",
        "ILHT_Jura_resistiveNew": "ILHT CH",
        "ILHT_Mittelland_CHPNew": "ILHT CH",
        "ILHT_Mittelland_HPNew": "ILHT CH",
        "ILHT_Mittelland_resistiveNew": "ILHT CH",
        "ILHT_Voralpen_CHPNew": "ILHT CH",
        "ILHT_Voralpen_HPNew": "ILHT CH",
        "ILHT_Voralpen_resistiveNew": "ILHT CH",
        "ILLT_Alpen_CHPNew": "ILLT CH",
        "ILLT_Alpen_HPNew": "ILLT CH",
        "ILLT_Alpen_resistiveNew": "ILLT CH",
        "ILLT_Alpensuedseite_CHPNew": "ILLT CH",
        "ILLT_Alpensuedseite_HPNew": "ILLT CH",
        "ILLT_Alpensuedseite_resistiveNew": "ILLT CH",
        "ILLT_Jura_CHPNew": "ILLT CH",
        "ILLT_Jura_HPNew": "ILLT CH",
        "ILLT_Jura_resistiveNew": "ILLT CH",
        "ILLT_Mittelland_CHPNew": "ILLT CH",
        "ILLT_Mittelland_HPNew": "ILLT CH",
        "ILLT_Mittelland_resistiveNew": "ILLT CH",
        "ILLT_Voralpen_CHPNew": "ILLT CH",
        "ILLT_Voralpen_HPNew": "ILLT CH",
        "ILLT_Voralpen_resistiveNew": "ILLT CH",
        "IT00_battery": "Battery abroad",
        "IT00_biomass": "Biomass abroad",
        "IT00_dam": "Dam abroad",
        "IT00_dsr": "DSR abroad",
        "IT00_electrolyzer": "Electrolyzer abroad",
        "IT00_gas": "Gas abroad",
        "IT00_psp_close": "Psp close abroad",
        "IT00_psp_open": "Psp open abroad",
        "large_psp": "Large psp CH",
        "LU00_battery": "Battery abroad",
        "LU00_biomass": "Biomass abroad",
        "LU00_dam": "Dam abroad",
        "LU00_dsr": "DSR abroad",
        "LU00_gas": "Gas abroad",
        "LU00_psp_close": "Psp close abroad",
        "LU00_psp_open": "Psp open abroad",
        "medium_reservior": "Medium RV CH",
        "minergie_Alpen_[MWh]": "Flexible heating CH",
        "minergie_Alpensuedseite_[MWh]": "Flexible heating CH",
        "minergie_Jura_[MWh]": "Flexible heating CH",
        "minergie_Mittelland_[MWh]": "Flexible heating CH",
        "minergie_Voralpen_[MWh]": "Flexible heating CH",
        "new_heavy_Alpen_[MWh]": "Flexible heating CH",
        "new_heavy_Alpensuedseite_[MWh]": "Flexible heating CH",
        "new_heavy_Jura_[MWh]": "Flexible heating CH",
        "new_heavy_Mittelland_[MWh]": "Flexible heating CH",
        "new_heavy_Voralpen_[MWh]": "Flexible heating CH",
        "new_light_Alpen_[MWh]": "Flexible heating CH",
        "new_light_Alpensuedseite_[MWh]": "Flexible heating CH",
        "new_light_Jura_[MWh]": "Flexible heating CH",
        "new_light_Mittelland_[MWh]": "Flexible heating CH",
        "new_light_Voralpen_[MWh]": "Flexible heating CH",
        "new_medium_Alpen_[MWh]": "Flexible heating CH",
        "new_medium_Alpensuedseite_[MWh]": "Flexible heating CH",
        "new_medium_Jura_[MWh]": "Flexible heating CH",
        "new_medium_Mittelland_[MWh]": "Flexible heating CH",
        "new_medium_Voralpen_[MWh]": "Flexible heating CH",
        "NL00_battery": "Battery abroad",
        "NL00_biomass": "Biomass abroad",
        "NL00_dam": "Dam abroad",
        "NL00_dsr": "DSR abroad",
        "NL00_electrolyzer": "Electrolyzer abroad",
        "NL00_gas": "Gas abroad",
        "NL00_nuclear": "Nuclear abroad",
        "NL00_psp_close": "Psp close abroad",
        "NL00_psp_open": "Psp open abroad",
        "NOM1_battery": "Battery abroad",
        "NOM1_dam": "Dam abroad",
        "NOM1_dsr": "DSR abroad",
        "NOM1_electrolyzer": "Electrolyzer abroad",
        "NOM1_gas": "Gas abroad",
        "NOM1_psp_close": "Psp close abroad",
        "NOM1_psp_open": "Psp open abroad",
        "NON1_battery": "Battery abroad",
        "NON1_biomass": "Biomass abroad",
        "NON1_dam": "Dam abroad",
        "NON1_dsr": "DSR abroad",
        "NON1_electrolyzer": "Electrolyzer abroad",
        "NON1_gas": "Gas abroad",
        "NON1_psp_close": "Psp close abroad",
        "NON1_psp_open": "Psp open abroad",
        "NOS0_battery": "Battery abroad",
        "NOS0_dam": "Dam abroad",
        "NOS0_dsr": "DSR abroad",
        "NOS0_electrolyzer": "Electrolyzer abroad",
        "NOS0_gas": "Gas abroad",
        "NOS0_psp_close": "Psp close abroad",
        "NOS0_psp_open": "Psp open abroad",
        "old_heavy_Alpen_[MWh]": "Flexible heating CH",
        "old_heavy_Alpensuedseite_[MWh]": "Flexible heating CH",
        "old_heavy_Jura_[MWh]": "Flexible heating CH",
        "old_heavy_Mittelland_[MWh]": "Flexible heating CH",
        "old_heavy_Voralpen_[MWh]": "Flexible heating CH",
        "old_light_Alpen_[MWh]": "Flexible heating CH",
        "old_light_Alpensuedseite_[MWh]": "Flexible heating CH",
        "old_light_Jura_[MWh]": "Flexible heating CH",
        "old_light_Mittelland_[MWh]": "Flexible heating CH",
        "old_light_Voralpen_[MWh]": "Flexible heating CH",
        "old_medium_Alpen_[MWh]": "Flexible heating CH",
        "old_medium_Alpensuedseite_[MWh]": "Flexible heating CH",
        "old_medium_Jura_[MWh]": "Flexible heating CH",
        "old_medium_Mittelland_[MWh]": "Flexible heating CH",
        "old_medium_Voralpen_[MWh]": "Flexible heating CH",
        "PL00_battery": "Battery abroad",
        "PL00_biomass": "Biomass abroad",
        "PL00_dam": "Dam abroad",
        "PL00_electrolyzer": "Electrolyzer abroad",
        "PL00_gas": "Gas abroad",
        "PL00_hardcoal": "Hardcoal abroad",
        "PL00_nuclear": "Nuclear abroad",
        "PL00_psp_close": "Psp close abroad",
        "PL00_psp_open": "Psp open abroad",
        "PT00_battery": "Battery abroad",
        "PT00_biomass": "Biomass abroad",
        "PT00_dam": "Dam abroad",
        "PT00_electrolyzer": "Electrolyzer abroad",
        "PT00_gas": "Gas abroad",
        "PT00_psp_close": "Psp close abroad",
        "PT00_psp_open": "Psp open abroad",
        "SE01_battery": "Battery abroad",
        "SE01_biomass": "Biomass abroad",
        "SE01_dam": "Dam abroad",
        "SE01_dsr": "DSR abroad",
        "SE01_electrolyzer": "Electrolyzer abroad",
        "SE01_gas": "Gas abroad",
        "SE01_psp_close": "Psp close abroad",
        "SE01_psp_open": "Psp open abroad",
        "SE02_battery": "Battery abroad",
        "SE02_biomass": "Biomass abroad",
        "SE02_dam": "Dam abroad",
        "SE02_dsr": "DSR abroad",
        "SE02_electrolyzer": "Electrolyzer abroad",
        "SE02_gas": "Gas abroad",
        "SE02_psp_close": "Psp close abroad",
        "SE02_psp_open": "Psp open abroad",
        "SE03_battery": "Battery abroad",
        "SE03_biomass": "Biomass abroad",
        "SE03_dam": "Dam abroad",
        "SE03_dsr": "DSR abroad",
        "SE03_electrolyzer": "Electrolyzer abroad",
        "SE03_gas": "Gas abroad",
        "SE03_nuclear": "Nuclear abroad",
        "SE03_psp_close": "Psp close abroad",
        "SE03_psp_open": "Psp open abroad",
        "SE04_battery": "Battery abroad",
        "SE04_biomass": "Biomass abroad",
        "SE04_dam": "Dam abroad",
        "SE04_dsr": "DSR abroad",
        "SE04_electrolyzer": "Electrolyzer abroad",
        "SE04_gas": "Gas abroad",
        "SE04_psp_close": "Psp close abroad",
        "SE04_psp_open": "Psp open abroad",
        "SI00_battery": "Battery abroad",
        "SI00_biomass": "Biomass abroad",
        "SI00_dam": "Dam abroad",
        "SI00_dsr": "DSR abroad",
        "SI00_electrolyzer": "Electrolyzer abroad",
        "SI00_gas": "Gas abroad",
        "SI00_hardcoal": "Hardcoal abroad",
        "SI00_nuclear": "Nuclear abroad",
        "SI00_psp_close": "Psp close abroad",
        "SI00_psp_open": "Psp open abroad",
        "SK00_battery": "Battery abroad",
        "SK00_biomass": "Biomass abroad",
        "SK00_dam": "Dam abroad",
        "SK00_electrolyzer": "Electrolyzer abroad",
        "SK00_gas": "Gas abroad",
        "SK00_hardcoal": "Hardcoal abroad",
        "SK00_nuclear": "Nuclear abroad",
        "SK00_oil": "Oil abroad",
        "SK00_psp_close": "Psp close abroad",
        "SK00_psp_open": "Psp open abroad",
        "small_reservior": "Small RV CH",
        "UK00_battery": "Battery abroad",
        "UK00_biomass": "Biomass abroad",
        "UK00_dam": "Dam abroad",
        "UK00_dsr": "DSR abroad",
        "UK00_electrolyzer": "Electrolyzer abroad",
        "UK00_gas": "Gas abroad",
        "UK00_nuclear": "Nuclear abroad",
        "UK00_oil": "Oil abroad",
        "UK00_psp_close": "Psp close abroad",
        "UK00_psp_open": "Psp open abroad",
        "V2G_CH": "V2G CH",
    }

    return replacement_dict.get(value, value)
