"""
Utility module for applying model variable presets from CSV file.

This module reads presets from model_variable_presets.csv and applies them to the Pyomo model,
allowing users to fix or initialize variable values for specific scenarios.
"""

import pandas as pd
import os
import logging
import pyomo.environ as pyo

logger = logging.getLogger(__name__)


def read_variable_presets(preset_file_path="input/model_variable_presets.csv"):
    """
    Read variable presets from CSV file.
    
    Parameters:
    -----------
    preset_file_path : str
        Path to the CSV file containing variable presets
        
    Returns:
    --------
    list of dict
        List of preset specifications, each with keys:
        - 'variable_name': name of the variable
        - 'scenario_name': name of the scenario (empty string if applies to all)
        - 'indices': list of index values (can be empty strings for "all")
        - 'value': the value to set
    """
    if not os.path.exists(preset_file_path):
        logger.info(f"Preset file {preset_file_path} not found. Skipping variable presets.")
        return []
    
    # Read CSV, skip comment lines and empty lines, no header row
    try:
        df = pd.read_csv(preset_file_path, comment='#', skipinitialspace=True, header=None)
    except pd.errors.EmptyDataError:
        logger.info(f"Preset file {preset_file_path} is empty. Skipping variable presets.")
        return []
    
    # Remove completely empty rows
    df = df.dropna(how='all')
    
    # If all rows were empty after dropping NAs, return empty list
    if df.empty:
        logger.info(f"Preset file {preset_file_path} contains no data rows. Skipping variable presets.")
        return []
    
    presets = []
    for idx, row in df.iterrows():
        # First column is variable name, second is scenario_name, last column is value, middle columns are indices
        # Don't use dropna() - we need to preserve empty cells for proper column positioning
        cols = [str(c) if pd.notna(c) else '' for c in row.tolist()]
        
        # Remove trailing empty strings
        while cols and cols[-1] == '':
            cols.pop()
        
        if len(cols) < 3:
            logger.warning(f"Row {int(idx) + 2} has insufficient columns. Skipping.")
            continue
        
        variable_name = cols[0].strip()
        scenario_name = cols[1].strip()
        value = float(cols[-1])
        indices = [c.strip() for c in cols[2:-1]]
        
        presets.append({
            'variable_name': variable_name,
            'scenario_name': scenario_name,
            'indices': indices,
            'value': value
        })
    
    return presets


def apply_variable_presets(model, scenario_name, preset_file_path="input/model_variable_presets.csv", verbose=True):
    """
    Apply variable presets from CSV file to the Pyomo model for a specific scenario.
    
    This function reads presets and applies them to the model by:
    1. Filtering presets that match the given scenario (or have empty scenario name)
    2. Finding the variable in the model
    3. Matching specified indices to model components
    4. Fixing or initializing variables to the specified values
    
    Parameters:
    -----------
    model : pyomo.environ.ConcreteModel
        The Pyomo model instance
    scenario_name : str
        The name of the scenario being run (from scenarios/scen_to_run_*.csv)
    preset_file_path : str
        Path to the CSV file containing variable presets
    verbose : bool
        If True, print detailed information about applied presets
        
    Returns:
    --------
    dict
        Summary of applied presets with keys:
        - 'total_presets': total number of presets read
        - 'applied': number of successfully applied presets
        - 'failed': number of failed applications
        - 'details': list of (preset, status, message) tuples
    """
    presets = read_variable_presets(preset_file_path)
    
    if not presets:
        if verbose:
            logger.info("No variable presets to apply.")
        return {'total_presets': 0, 'applied': 0, 'failed': 0, 'details': []}
    
    # Filter presets by scenario: only apply if scenario_name is empty (all scenarios) or matches the current scenario
    matching_presets = [
        p for p in presets 
        if p['scenario_name'] == '' or p['scenario_name'] == scenario_name
    ]
    
    if verbose:
        logger.info(f"Scenario: '{scenario_name}' - Found {len(matching_presets)} applicable presets out of {len(presets)} total")
    
    summary = {
        'total_presets': len(presets),
        'applied': 0,
        'failed': 0,
        'details': []
    }
    
    for preset in matching_presets:
        var_name = preset['variable_name']
        indices = preset['indices']
        value = preset['value']
        scen_spec = preset['scenario_name']
        
        try:
            # Check if variable exists in model
            if not hasattr(model, var_name):
                msg = f"Variable '{var_name}' not found in model"
                summary['failed'] += 1
                summary['details'].append((preset, 'FAILED', msg))
                logger.warning(msg)
                continue
            
            var = getattr(model, var_name)
            
            # Apply preset based on number of indices provided
            applied_count = 0
            
            if not isinstance(var, pyo.Var):
                msg = f"'{var_name}' is not a Pyomo Var object"
                summary['failed'] += 1
                summary['details'].append((preset, 'FAILED', msg))
                logger.warning(msg)
                continue
            
            # Get variable dimensions
            var_dim = var.dim()
            
            # If variable has no indices (scalar), apply directly
            if var_dim == 0:
                var.fix(value)
                applied_count = 1
                scenario_info = f" (scenario: {scen_spec})" if scen_spec else " (all scenarios)"
                msg = f"Fixed {var_name}{scenario_info} = {value}"
                summary['applied'] += 1
                summary['details'].append((preset, 'SUCCESS', msg))
                if verbose:
                    logger.info(msg)
                continue
            
            # Handle indexed variables
            # Create index specifications: if index is empty string, it means "all"
            index_specs = []
            for i, idx in enumerate(indices):
                if idx == '' or idx is None:
                    index_specs.append(None)  # None means "all"
                else:
                    index_specs.append(idx)
            
            # Apply to matching indices
            if var_dim == 1:
                # Single-indexed variable
                set1 = list(var.keys())
                for key in set1:
                    if index_specs[0] is None or key == index_specs[0]:
                        var[key].fix(value)
                        applied_count += 1
                        
            elif var_dim == 2:
                # Two-indexed variable (most common case)
                # Build the actual index sets present on the variable
                keys1 = set()
                keys2 = set()
                for k in var.keys():
                    try:
                        k1, k2 = k
                    except Exception:
                        # Defensive: keys() should yield tuples for 2D variables
                        continue
                    keys1.add(k1)
                    keys2.add(k2)

                # Validate specified indices exist if provided
                if index_specs[0] is not None and index_specs[0] not in keys1:
                    raise ValueError(f"Index '{index_specs[0]}' not found for first dimension of '{var_name}'. Available sample: {list(keys1)[:10]}")
                if index_specs[1] is not None and index_specs[1] not in keys2:
                    raise ValueError(f"Index '{index_specs[1]}' not found for second dimension of '{var_name}'. Available sample: {list(keys2)[:10]}")

                for k1 in keys1:
                    for k2 in keys2:
                        # Check if this index matches the specification
                        match_k1 = (index_specs[0] is None or k1 == index_specs[0])
                        match_k2 = (index_specs[1] is None or k2 == index_specs[1])

                        if match_k1 and match_k2:
                            try:
                                var[k1, k2].fix(value)
                                applied_count += 1
                            except KeyError:
                                # Skip silently if key is not valid (shouldn't happen after validation)
                                pass
                                
            elif var_dim == 3:
                # Three-indexed variable
                keys1, keys2, keys3 = set(), set(), set()
                for k in var.keys():
                    try:
                        k1, k2, k3 = k
                    except Exception:
                        continue
                    keys1.add(k1)
                    keys2.add(k2)
                    keys3.add(k3)

                # Validate specified indices exist if provided
                if index_specs[0] is not None and index_specs[0] not in keys1:
                    raise ValueError(f"Index '{index_specs[0]}' not found for first dimension of '{var_name}'. Available sample: {list(keys1)[:10]}")
                if index_specs[1] is not None and index_specs[1] not in keys2:
                    raise ValueError(f"Index '{index_specs[1]}' not found for second dimension of '{var_name}'. Available sample: {list(keys2)[:10]}")
                if index_specs[2] is not None and index_specs[2] not in keys3:
                    raise ValueError(f"Index '{index_specs[2]}' not found for third dimension of '{var_name}'. Available sample: {list(keys3)[:10]}")
                
                for k1 in keys1:
                    for k2 in keys2:
                        for k3 in keys3:
                            match_k1 = (index_specs[0] is None or k1 == index_specs[0])
                            match_k2 = (index_specs[1] is None or k2 == index_specs[1])
                            match_k3 = (index_specs[2] is None or k3 == index_specs[2])
                            
                            if match_k1 and match_k2 and match_k3:
                                try:
                                    var[k1, k2, k3].fix(value)
                                    applied_count += 1
                                except KeyError:
                                    pass
            else:
                msg = f"Variable '{var_name}' has {var_dim} dimensions, which is not yet supported"
                summary['failed'] += 1
                summary['details'].append((preset, 'FAILED', msg))
                logger.warning(msg)
                continue
            
            if applied_count > 0:
                scenario_info = f" (scenario: {scen_spec})" if scen_spec else " (all scenarios)"
                msg = f"Fixed preset for '{var_name}'{scenario_info} with indices {indices}: fixed {applied_count} variable(s) to {value}"
                summary['applied'] += 1
                summary['details'].append((preset, 'SUCCESS', msg))
                if verbose:
                    logger.info(msg)
            else:
                msg = f"No matching indices found for '{var_name}' with specification {indices}. Please check that the indices exist in the model."
                summary['failed'] += 1
                summary['details'].append((preset, 'FAILED', msg))
                logger.error(msg)
                raise ValueError(msg)
                
        except Exception as e:
            msg = f"Error applying preset for '{var_name}': {str(e)}"
            summary['failed'] += 1
            summary['details'].append((preset, 'ERROR', msg))
            logger.error(msg)
    
    if verbose:
        logger.info(f"\nPreset Summary: {summary['applied']} applied, {summary['failed']} failed out of {len(matching_presets)} applicable presets")
    
    return summary
