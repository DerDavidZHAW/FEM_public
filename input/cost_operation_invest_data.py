import numpy as np
import pandas as pd
from pathlib import Path

"""
Data source for this file:
- All technology cost and efficiency parameters are read from: input/cost_assumptions.xlsx
- Sheet: 03_Calculated_Costs
- This approach centralizes cost assumptions in a single, user-friendly Excel file
- Original sources (embedded in the Excel file)
"""

# Read cost assumptions from Excel file
_excel_file = Path(__file__).parent / "cost_assumptions.xlsx"
_df_costs = pd.read_excel(_excel_file, sheet_name="03_Calculated_Costs")

# Add fuel storage amortization years (these are not in the Excel file but are used in the code)
_fuel_storage_amortization = {
    "biomass_fuel_storage": 50,
    "resmethane_fuel_storage": 50,
    "fossilmethane_fuel_storage": 50,
    "oil_fuel_storage": 50,
}

# Currency conversion rates
# USD2017toCHF2017 = 0.9843 # 1 USD = 0.9843 CHF
# USD2024toCHF2017 = 0.8148 # 1 USD = 0.8148 CHF
# EUR2017toCHF2017 = 1.1119 # 1 EUR = 1.1119 CHF
# EUR2024toCHF2017 = 0.8889 # 1 EUR = 0.8889 CHF

# o_m_share = 1.025 # share of fixed operation and maintanance costs (expressed as Euro/kw/year) as percentage of investment cost.

# NEXUS-E assumed fixed operation costs which were essentially 2.5% of the investment costs.

# ============================================================================
# BUILD AMORTIZATION_YEARS_ALL FROM EXCEL
# ============================================================================
amortization_years_all = {}
for _, row in _df_costs.iterrows():
    tech = row["technology"]
    amort_years = row["amortization_years"]
    if tech not in amortization_years_all:
        if not pd.isna(amort_years):
            # Preserve the original value (float if it has decimals, int if it doesn't)
            if amort_years == int(amort_years):
                amortization_years_all[tech] = int(amort_years)
            else:
                amortization_years_all[tech] = amort_years
        else:
            amortization_years_all[tech] = 0

amortization_years_all.update(_fuel_storage_amortization)

# ============================================================================
# HELPER FUNCTIONS TO BUILD DICTIONARIES FROM EXCEL
# ============================================================================
def _build_dict_from_excel(column_name, years_list=None):
    """
    Build a dictionary from Excel data where keys are technologies.
    If years_list is provided, creates nested dict {tech: {year: value}}.
    Otherwise creates simple dict {tech: value}.
    """
    if years_list is None:
        # Simple dictionary (no year dimension)
        result = {}
        for _, row in _df_costs.iterrows():
            tech = row["technology"]
            value = row[column_name]
            if not pd.isna(value) and tech not in result:
                result[tech] = value
        return result
    else:
        # Nested dictionary with years
        result = {}
        for tech in _df_costs["technology"].unique():
            result[tech] = {}
            tech_data = _df_costs[_df_costs["technology"] == tech]
            for year in years_list:
                year_data = tech_data[tech_data["year"] == year]
                if len(year_data) > 0:
                    value = year_data[column_name].iloc[0]
                    if not pd.isna(value):
                        result[tech][year] = value
                    else:
                        result[tech][year] = 0
                else:
                    result[tech][year] = 0
        return result

# Get available years from the Excel file
_available_years = sorted(_df_costs["year"].unique().tolist())

# ============================================================================
# BUILD COST_COMPONENT DICTIONARIES FROM EXCEL
# ============================================================================
cost_component = {
    'investment_cost_chfMW': _build_dict_from_excel('investment_cost_chfMW', _available_years),
    
    'investment_cost_charge_chfMW': _build_dict_from_excel('investment_cost_charge_chfMW', _available_years),
    
    'fixed_op_cost_chfMW': _build_dict_from_excel('fixed_op_cost_chfMW', _available_years),
    
    'input_cost_scenario_ZERO': _build_dict_from_excel('input_cost_scenario_ZERO', _available_years),
    
    'investment_energy_cost_chfMWh': _build_dict_from_excel('investment_energy_cost_chfMWh', _available_years),
    
    'investment_fuel_energy_cost_chfMWh': _build_dict_from_excel('investment_fuel_energy_cost_chfMWh', _available_years),
    
    'om_cost_eurMWH': _build_dict_from_excel('om_cost_eurMWH', _available_years),
    
    'efficiency': _build_dict_from_excel('efficiency', _available_years),
    
    'efficiency_into_storage': _build_dict_from_excel('efficiency_into_storage', _available_years),
    
    'emission_factor': _build_dict_from_excel('emission_factor', _available_years),
}

# Clean up temporary variables
del _excel_file, _df_costs, _available_years
