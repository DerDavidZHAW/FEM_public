"""
Central coordinator for detailed reporting of model inputs and outputs.

This module provides the main reporting function that generates standardized
reports for the Swiss model intercomparison (Round 3) and other analysis needs.
"""

from pathlib import Path

from detailed_reporting.constants import CHF_TO_EUR, is_winter_t, is_summer_t, get_run_year
from detailed_reporting.Output_Spatial import export_output_spatial
from detailed_reporting.Output_Sys import export_output_system
from detailed_reporting.Output_Temp import export_output_temporal

# Re-export shared constants and functions for backward compatibility
__all__ = ['CHF_TO_EUR', 'is_winter_t', 'is_summer_t', 'get_run_year', 'generate_detailed_reports']


def generate_detailed_reports(model, scenario_name, total_time_seconds=None, subscenario=None):
    """
    Generate all detailed reports for the solved model.
    
    This function orchestrates the generation of three standardized report files
    following the Swiss model intercomparison format. Reports are generated in
    the following order:
    1. Output_Spatial - Spatial distribution of model outputs
    2. Output_Sys - System-level output metrics
    3. Output_Temp - Temporal patterns in outputs
    
    Parameters
    ----------
    model : pyomo.ConcreteModel
        The solved Pyomo model instance containing all variables, parameters,
        and constraints.
    scenario_name : str
        Name of the scenario being analyzed. Used to create the output directory
        structure.
    total_time_seconds : float, optional
        Total runtime from model start to this point in seconds.
    
    Returns
    -------
    None
        Reports are written directly to CSV files in the detailed_reporting
        subdirectory of the scenario output folder.
    
    Notes
    -----
    All report functions are designed to handle missing data gracefully and will
    create empty CSV files with appropriate headers if no data is available.
    
    Examples
    --------
    >>> generate_detailed_reports(solved_model, "2035_basecase")
    """
    label = f"{scenario_name} / {subscenario}" if subscenario else scenario_name
    print(f"Generating detailed reports for Swiss model intercomparison ({label})...")

    # Create output directory for detailed reports
    report_dir = Path("output") / scenario_name / "detailed_reporting"
    if subscenario is not None:
        report_dir = report_dir / subscenario
    report_dir.mkdir(parents=True, exist_ok=True)

    # Generate reports in the specified order
    print("  - Exporting Output_Spatial...")
    export_output_spatial(model, scenario_name, subscenario=subscenario)

    print("  - Exporting Output_Sys...")
    export_output_system(model, scenario_name,
                        total_time_seconds=total_time_seconds,
                        subscenario=subscenario)  # type: ignore

    print("  - Exporting Output_Temp...")
    export_output_temporal(model, scenario_name, subscenario=subscenario)

    print("Detailed reporting complete.")
