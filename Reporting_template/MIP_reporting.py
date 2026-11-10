# Python script to report MIP data 
# Author : Selina Kerscher (original template generation)
# Modified: Data filling implementation for FEM model
# Date   : 260223 / 260305
# ============================================================================
import time
import os
import pandas as pd
import numpy as np
import math
from typing import List, Tuple, Dict
from openpyxl import load_workbook

# ============================================================================
def get_configuration() -> Dict:
    """
    Central configuration section.
    Modify ONLY here to adjust models, scenarios, parameters, years, etc.
    """
    config = {
        # ----------------------------------------------------
        # File name
        "output_filename": "20261006_MIP3_Reporting_FEM_v7.xlsx",
        # ----------------------------------------------------
        # Models
        "models": ["EXPANSE", "FEM", "OREES", "Nexus-e"],
        "selected_model": "FEM",    # Write your model name here
        # ----------------------------------------------------
        # Path to combined CSV results
        "csv_dir": os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..",
            "output", "20261005_MIP3_v7"
        )),
        # Workbook in the new template format whose Input sheets (Input_Spatial,
        # Spatial_Mapping, Input_Sys, Input_Temp, Input_Comments) are copied as they are.
        # Used instead of old_fem_workbook when it exists.
        "input_workbook": os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            "FEM_reporting_input_sheets_v7.xlsx"
        )),
        # Path to old FEM reporting workbook (for input data)
        "old_fem_workbook": os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            "20260305_MIP3_Reporting_FEM_v2.xlsx"
        )),
        # ----------------------------------------------------
        # Scenarios (used in Output sheets)
        "scenarios": [
            "2035_GA_NRT_NF",
            "2035_GA_NRT_WF",
            "2035_GA_WRT_NF",
            "2035_GA_WRT_WF",
            "2050_GA_NRT_NN_NF",
            "2050_GA_NRT_NN_WF",
            "2050_GA_NRT_WN_NF",
            "2050_GA_NRT_WN_WF",
            "2050_GA_WRT_NN_NF",
            "2050_GA_WRT_NN_WF",
            "2050_GA_WRT_WN_NF",
            "2050_GA_WRT_WN_WF"
        ],
        # ----------------------------------------------------
        # Years (used in Input sheets)
        "years": [2035, 2050],
        # ----------------------------------------------------
        # Spatial resolution
        # FEM has 7 greater regions (CH01-CH07) in columns 1-7
        # plus column 8 for 'Location independent' data.
        "n_spatial_low": 8,
        "n_spatial_high": 8,
        "n_fem_regions": 8,  # 7 geographic regions + 1 location independent
        # ----------------------------------------------------
        # Temporal resolution
        "n_hours": 8760,
        # ----------------------------------------------------
        "output_spatial_parameters": [
            ("Capacity_PV_roof", "GWp"),
            ("Capacity_PV_agri", "GWp"),
            ("Capacity_PV_alpine", "GWp"),
            ("Capacity_wind", "GW"),
            ("Capacity_bioenergy", "GW"),
            ("Capacity_geothermal", "GW"),
            ("Capacity_waste_incineration", "GW"),
            ("Capacity_gas", "GW"),
            ("Capacity_nuclear", "GW"),
            ("Capacity_hydro_dam", "GW"),
            ("Capacity_hydro_ror", "GW"),
            ("Capacity_pumped_hydro", "GW"),
            ("Capacity_battery", "GW"),
            ("Generation_PV_roof", "GWh/yr"),
            ("Generation_PV_agri", "GWh/yr"),
            ("Generation_PV_alpine", "GWh/yr"),
            ("Generation_wind", "GWh/yr"),
            ("Generation_bioenergy", "GWh/yr"),
            ("Generation_geothermal", "GWh/yr"),
            ("Generation_waste_incineration", "GWh/yr"),
            ("Generation_gas", "GWh/yr"),
            ("Generation_nuclear", "GWh/yr"),
            ("Generation_hydro_dam", "GWh/yr"),
            ("Generation_hydro_ror", "GWh/yr"),
            ("Charge_pumped_hydro", "GWh/yr"),
            ("Discharge_pumped_hydro", "GWh/yr"),
            ("Charge_battery", "GWh/yr"),
            ("Discharge_battery", "GWh/yr"),
            ("Load_shedding", "GWh/yr"),
            ("Charge_pumped_hydro_winter", "GWh/yr"),
            ("Charge_pumped_hydro_summer", "GWh/yr"),
            ("Curtailment_PV_roof", "GWh/yr"),
            ("Curtailment_PV_agri", "GWh/yr"),
            ("Curtailment_PV_alpine", "GWh/yr"),
            ("Curtailment_wind", "GWh/yr"),
            ("Curtailment_solar-wind_optional", "GWh/yr"),
            ("Average_netload_winter", "GWh"),
            ("Average_netload_summer", "GWh")
        ],
        # ----------------------------------------------------
        "output_sys_parameters": [
            ("Import_to_CH", "TWh/yr"),
            ("Export_from_CH", "TWh/yr"),
            ("Net_import_CH", "TWh/yr"),
            ("Import_winter", "TWh"),
            ("Export_winter", "TWh"),
            ("Net_import_winter", "TWh"),
            ("Import_summer", "TWh"),
            ("Export_summer", "TWh"),
            ("Net_import_summer", "TWh"),
            ("Energy_shifted_EV_winter", "MWh"),
            ("Energy_shifted_EV_summer", "MWh"),
            ("Energy_shifted_HP_winter", "MWh"),
            ("Energy_shifted_HP_summer", "MWh"),
            ("Load_shedding_CH", "TWh/yr"),
            ("Load_shedding_CH_winter", "TWh"),
            ("Load_shedding_CH_summer", "TWh"),
            ("Generation_curtailment_CH", "TWh/yr"),
            ("Generation_curtailment_abroad", "TWh/yr"),
            ("Import_cost", "Mio-EUR/yr"),
            ("Export_revenue", "Mio-EUR/yr"),
            ("Trading_cost", "Mio-EUR/yr"), # cost - revenue
            ("Import_cost_winter", "Mio-EUR"),
            ("Export_revenue_winter", "Mio-EUR"),
            ("Import_cost_summer", "Mio-EUR"),
            ("Export_revenue_summer", "Mio-EUR"),
            ("Electricity_price_CH", "EUR/MWh"),
            ("Price_electricity_import_from_AT", "EUR/MWh"),
            ("Price_electricity_import_from_DE", "EUR/MWh"),
            ("Price_electricity_import_from_FR", "EUR/MWh"),
            ("Price_electricity_import_from_IT", "EUR/MWh"),
            ("Price_electricity_export_from_AT", "EUR/MWh"),
            ("Price_electricity_export_from_DE", "EUR/MWh"),
            ("Price_electricity_export_from_FR", "EUR/MWh"),
            ("Price_electricity_export_from_IT", "EUR/MWh"),
            ("Annualised_investment_costs", "Mio-EUR"),
            ("Annualised_operation_costs", "Mio-EUR"),
            ("Annualised_costs_all", "Mio-EUR"),
            ("Operational_costs_per_unit", "EUR-TWh"),
            ("Transmission_grid_expansion_investment_costs", "Mio-EUR"),
            ("Capacity_grid_expansion_CH", "GW"),
            ("Capacity_grid_expansion_interconnectors", "GW"),
            ("Total_emissions", "tonCO2/yr"),
            ("Time_to_solve_model", "min"),
            ("Memory_requirements", "GB")
        ],
        # ----------------------------------------------------
        "output_temp_parameters": [
            ("Hourly_generation_PV_roof", "GWh"),
            ("Hourly_generation_PV_agri", "GWh"),
            ("Hourly_generation_PV_alpine", "GWh"),
            ("Hourly_generation_wind", "GWh"),
            ("Hourly_generation_bioenergy", "GWh"),
            ("Hourly_generation_geothermal", "GWh"),
            ("Hourly_generation_waste_incineration", "GWh"),
            ("Hourly_generation_gas", "GWh"),
            ("Hourly_generation_nuclear", "GWh"),
            ("Hourly_generation_hydro_dam", "GWh"),
            ("Hourly_generation_hydro_ror", "GWh"),            
            ("Hourly_generation_pumped_hydro", "GWh"),
            ("Hourly_demand_pumped_hydro", "GWh"),
            ("Hourly_generation_battery", "GWh"),
            ("Hourly_demand_battery", "GWh"),
            ("Hourly_EV-DSM_up", "GWh"),
            ("Hourly_EV-DSM_down", "GWh"),
            ("Hourly_HP-DSM_up", "GWh"),
            ("Hourly_HP-DSM_down", "GWh"),
            ("Hourly_generation_curtailment-CH", "GWh"),
            ("Hourly_generation_curtailment-abroad", "GWh"),
            ("Hourly_load_shedding", "GWh"),
            ("Hourly_exchange_CH-DE", "GWh"),
            ("Hourly_exchange_DE-CH", "GWh"),
            ("Hourly_exchange_CH-FR", "GWh"),
            ("Hourly_exchange_FR-CH", "GWh"),
            ("Hourly_exchange_CH-IT", "GWh"),
            ("Hourly_exchange_IT-CH", "GWh"),
            ("Hourly_exchange_CH-AT", "GWh"),
            ("Hourly_exchange_AT-CH", "GWh"),
            ("Hourly_import_to_CH", "GWh"),
            ("Hourly_export_from_CH", "GWh"),
            ("Hourly_net_import", "GWh"),   # import-export
            ("Hourly_net_load", "GWh"),
            ("Hourly_electricity_price_CH", "EUR/MWh"),
            ("Hourly_electricity_price_DE", "EUR/MWh"),
            ("Hourly_electricity_price_FR", "EUR/MWh"),
            ("Hourly_electricity_price_IT", "EUR/MWh"),
            ("Hourly_electricity_price_AT", "EUR/MWh"),
            ("Average_line_loading_CH-lines", "%"),
            ("Average_line_loading_interconnectors", "%"),
            ("Average_line_loading_all_lines", "%")
        ],
        # ----------------------------------------------------
        "input_spatial_parameters": [
            ("Potential_PV_roof", "GW"),
            ("Potential_PV_agri", "GW"),
            ("Potential_PV_alpine", "GW"),
            ("Potential_bioenergy", "GW"),
            ("Potential_geothermal", "GW"),
            ("Potential_new_hydro", "GW"),
            ("Potential_DSM", "GWh/yr"),
            ("Fixed_capacity_pumped_hydro", "GW"),
            ("Fixed_capacity_hydro_dam", "GW"),
            ("Fixed_capacity_hydro_ror", "GW"),
            ("Fixed_capacity_nuclear", "GW"),
            ("Fixed_capacity_bioenergy", "GW"),
            ("Fixed_capacity_geothermal", "GW"),
            ("Fixed_capacity_waste_incineration", "GW"),
            ("Capacity_factor_PV_roof_average", "0-1"),
            ("Capacity_factor_PV_roof_5th", "0-1"),
            ("Capacity_factor_PV_roof_95th", "0-1"),
            ("Capacity_factor_PV_agri_average", "0-1"),
            ("Capacity_factor_PV_agri_5th", "0-1"),
            ("Capacity_factor_PV_agri_95th", "0-1"),
            ("Capacity_factor_PV_alpine_average", "0-1"),
            ("Capacity_factor_PV_alpine_5th", "0-1"),
            ("Capacity_factor_PV_alpine_95th", "0-1"),
            ("Capacity_factor_wind_average", "0-1"),
            ("Capacity_factor_wind_5th", "0-1"),
            ("Capacity_factor_wind_95th", "0-1"),
            ("Electricity_demand", "GWh/yr")
        ],
        # ----------------------------------------------------
        "input_sys_parameters": [
            ("Investment_costs_PV_roof", "EUR/kWp"),
            ("Investment_costs_PV_agri", "EUR/kWp"),
            ("Investment_costs_PV_alpine", "EUR/kWp"),
            ("Investment_costs_wind", "EUR/kW"),
            ("Investment_costs_bioenergy", "EUR/kW"),
            ("Investment_costs_geothermal", "EUR/kW"),
            ("Investment_costs_waste_incineration", "EUR/kW"),
            ("Investment_costs_gas", "EUR/kW"),
            ("Investment_costs_batteries", "EUR/kW"),
            ("Investment_costs_P2X", "EUR/kW"),
            ("Fuel_price_gas", "EUR/MWh"),
            ("Fuel_price_waste", "EUR/MWh"),
            ("Fuel_price_bioenergy", "EUR/MWh"),
            ("Fuel_price_uranium", "EUR/MWh"),
            ("Transmission_grid_expansion_investment_costs", "EUR/GW"),
            ("Discount_rate", "%"),
            ("Roundtrip_efficiency_batteries", "%"),
            ("Capacity_factor_PV_roof", "0-1"),
            ("Capacity_factor_PV_agri", "0-1"),
            ("Capacity_factor_PV_alpine", "0-1"),
            ("Capacity_factor_wind", "0-1"),
            ("Emission_factor_gas", "tonCO2/MWhel"),
            ("Emission_factor_waste", "tonCO2/MWhel"),
            ("Emission_factor_bioenergy", "tonCO2/MWhel"),
            ("Min_load_bioenergy", "0-1"),
            ("Min_load_gas", "0-1"),
            ("Min_load_waste", "0-1"),
            ("Min_load_geothermal", "0-1"),
            ("Ramp_up_bioenergy", "0-1"),
            ("Ramp_up_gas", "0-1"),
            ("Ramp_up_waste", "0-1"),
            ("Ramp_up_geothermal", "0-1"),
            ("Ramp_down_bioenergy", "0-1"),
            ("Ramp_down_gas", "0-1"),
            ("Ramp_down_waste", "0-1"),
            ("Ramp_down_geothermal", "0-1"),
            ("Max_hourly_output_hydro_dam", "GWh/h"),
            ("Max_hourly_output_hydro_ror", "GWh/h"),
            ("Max_hourly_output_pumped_hydro", "GWh/h"),
            ("Nr_power_system_nodes_CH", "-"),
            ("Installation_of_power_lines_in_CH", "yes/no"),
            ("Price_electricity_import_from_AT", "EUR/MWh"),
            ("Price_electricity_import_from_DE", "EUR/MWh"),
            ("Price_electricity_import_from_FR", "EUR/MWh"),
            ("Price_electricity_import_from_IT", "EUR/MWh"),
            ("Price_electricity_export_from_AT", "EUR/MWh"),
            ("Price_electricity_export_from_DE", "EUR/MWh"),
            ("Price_electricity_export_from_FR", "EUR/MWh"),
            ("Price_electricity_export_from_IT", "EUR/MWh"),
            ("Net_transfer_capacity_AT", "MW"),
            ("Net_transfer_capacity_DE", "MW"),
            ("Net_transfer_capacity_FR", "MW"),
            ("Net_transfer_capacity_IT", "MW"),
            ("Electricity_demand_HP", "TWh/yr"),
            ("Electricity_demand_EV", "TWh/yr"),
            ("Electricity_demand_other", "TWh/yr"),
            ("Electricity_demand_total", "TWh/yr")
        ],
        # ----------------------------------------------------
        "input_temp_parameters": [
            ("Hourly_electricity_demand_HP", "GWh"),
            ("Hourly_electricity_demand_EV", "GWh"),
            ("Hourly_electricity_demand_other", "GWh"),
            ("Hourly_electricity_demand_total", "GWh")
        ]
    }
    return config
# ============================================================================
def build_instructions_df() -> pd.DataFrame:
    # Proposed format: Section | Description
    data = [
        ("General", "Fill only data cells. Do not modify headers."),
        ("Output_Spatial_low", "Provide spatial results at aggregated 26 cantons (else use spatial " 
        "mapping to assign numbers, e.g. 1-7, to greater regions)."),
        ("Output_Spatial_high", "Provide spatial results at full 2136 municipalities if available."),
        ("Output_Sys", "Provide system-wide data."),
        ("Output_Temp", "Provide hourly model outputs."),
        ("Input_Spatial", "Provide spatial input data."),
        ("Input_Sys", "Provide system input assumptions."),
        ("Input_Temp", "Provide hourly input data."),
        ("Spatial_Mapping", "Define area mapping and coverage, e.g. if region 1 covers the "
        "cantons VD, VS, and GE, write: (1, VD); (1, VS); (1, GE); (2, ...); ..."),
        ("Input_Comments", "Add additional explanations if required.")
    ]
    return pd.DataFrame(data, columns=["Section", "Description"])
# ============================================================================
def build_spatial_output_df(
    model: str,
    scenarios: List[str],
    parameters: List[Tuple[str, str]],
    n_regions: int
) -> pd.DataFrame:
    # Structure: Model | Scenario | Parameter | Unit | Sum | 1 | 2 | ... | n
    numbered_columns = [str(i) for i in range(1, n_regions + 1)]
    columns = ["Model", "Scenario", "Parameter", "Unit", "Sum"] + numbered_columns
    rows = []
    for scenario in scenarios:
        for param_name, unit in parameters:
            values = [math.nan] * n_regions
            row_sum = sum(values)
            row = [model, scenario, param_name, unit, row_sum] + values
            rows.append(row)
    df = pd.DataFrame(rows, columns=columns)
    return df
# ============================================================================
def build_sys_output_df(
    model: str,
    scenarios: List[str],
    parameters: List[Tuple[str, str]]
) -> pd.DataFrame:
    columns = [
        "Model", "Scenario", "Parameter", "Unit",
        "Total", "Average", "5th", "95th", "Min", "Max"
    ]
    rows = []
    for scenario in scenarios:
        for param_name, unit in parameters:
            stats = [math.nan] * 6
            row = [model, scenario, param_name, unit] + stats
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)
# ============================================================================
def build_temp_output_df(
    model: str,
    scenarios: List[str],
    parameters: List[Tuple[str, str]],
    n_hours: int
) -> pd.DataFrame:
    # Structure: Model | Scenario | Parameter | Unit | 1 | ... | 8760
    hour_columns = [str(i) for i in range(1, n_hours + 1)]
    columns = ["Model", "Scenario", "Parameter", "Unit"] + hour_columns
    rows = []
    for scenario in scenarios:
        for param_name, unit in parameters:
            values = [math.nan] * n_hours
            row = [model, scenario, param_name, unit] + values
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)
# ============================================================================
def build_input_spatial_df(
    model: str,
    years: List[int],
    parameters: List[Tuple[str, str]],
    n_regions: int
) -> pd.DataFrame:
    # Structure: Model | Year | Parameter | Unit | Sum | Source | 1 | ... | 26
    numbered_columns = [str(i) for i in range(1, n_regions + 1)]
    columns = ["Model", "Year", "Parameter", "Unit", "Sum", "Source"] + numbered_columns
    rows = []
    for year in years:
        for param_name, unit in parameters:
            values = [math.nan] * n_regions
            row_sum = sum(values)
            row = [model, year, param_name, unit, row_sum, ""] + values
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)
# ============================================================================
def build_input_sys_df(
    model: str,
    years: List[int],
    parameters: List[Tuple[str, str]]
) -> pd.DataFrame:
    columns = [
        "Model", "Year", "Parameter", "Unit",
        "Total", "Average", "5th", "95th", "Min", "Max", "Source"
    ]
    rows = []
    for year in years:
        for param_name, unit in parameters:
            stats = [math.nan] * 6
            row = [model, year, param_name, unit] + stats + [""]
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)
# ============================================================================
def build_input_temp_df(
    model: str,
    years: List[int],
    parameters: List[Tuple[str, str]],
    n_hours: int
) -> pd.DataFrame:
    # Structure: Model | Year | Parameter | Unit | 1 | ... | 8760
    hour_columns = [str(i) for i in range(1, n_hours + 1)]
    columns = ["Model", "Year", "Parameter", "Unit"] + hour_columns
    rows = []
    for year in years:
        for param_name, unit in parameters:
            values = [math.nan] * n_hours
            row = [model, year, param_name, unit] + values
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)
# ============================================================================
def build_spatial_mapping_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["Area_ID", "Coverage"])
# ============================================================================
def build_definitions_df() -> pd.DataFrame:
    # Proposed format: Term | Definition
    data = [
        ("Capacity_{{}}, technology", "Installed capacity of given technology (always check respective units!)."),
        ("Generation_{{}}, technology", "Annual electricity generation from given technology."),
        ("Charge_{{}}, technology", "Charge is equivalent to demand from a given technology."),
        ("Discharge_{{}}, technology", "Discharge is equivalent to generation from a given technology."),
        ("Curtailment_{{}}, technology", "Annual curtailed generation from given technology."),
        ("Average_netload_{{}}, season", "The netload is the difference between demand and generation at a given hour. "
        "Indicate the average netload per season (winter: 01.10.-31.03.; summer: 01.04.-31.09.)."),
        ("Import_to_CH", "Sum of annual imports from all neighbouring countries to Switzerland."),
        ("Export_from_CH", "Sum of annual export from Switzerland to all neighbouring countries."),
        ("Net_import_CH", "The difference of annual imports to Switzerland and annual exports from Switzerland."),
        ("Import_{{}}, season", "Sum of annual imports from all neighbouring countries to Switzerland for a given season."),
        ("Export_{{}}, season", "Sum of annual imports from all neighbouring countries to Switzerland for a given season."),
        ("Energy_shifted_{{}}_{{}}, technology, season", "Sum of the absolute value of energy shifted "
        "(up or down for a given technology and season)"),
        ("Generation_curtailment_CH", "Curtailed generation in Switzerland."),
        ("Generation_curtailment_abroad", "Curtailed generation abroad."),
        ("Import_cost", "Annual cost for importing electricity to Switzerland."),
        ("Export_revenue", "Annual revenue for exporting electricity from Switzerland."),
        ("Trading_cost", "The difference between the annual import cost and export revenue."),
        ("Annualised_investment_costs", "Annualised investment costs for generation expansion."),
        ("Annualised_operation_costs", "Annualised operational costs (fixed + variable)."),
        ("Annualised_costs_all", "Annualised costs, including generator investment, operational, and trading costs."),
        ("Operational_costs_per_unit", "The division of the annual operational costs by the annual electricity generated."),
        ("Transmission_grid_expansion_investment_costs (Output_Sys)", "Costs for expanding the transmission grid."),
        ("Potential_{{}}, technology", "Maximum potential capacity for a given technology."),
        ("Potential_DSM", "Maximum potential electricity that can be shifted per year for all flexible demand."),
        ("Fixed_capacity_{{}}, technology", "Already installed and existing capacity of a given technology."),
        ("Transmission_grid_expansion_investment_costs (Input_Sys)", "Costs per unit for expanding the transmission "
        "grid within Switzerland and to neighbouring countries."),
        ("Roundtrip_efficiency_batteries", "Roundtrip efficiency of stationary battery systems."),
    ]
    return pd.DataFrame(data, columns=["Term", "Definition"])
# ============================================================================
def build_input_comments_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["Sheet", "Parameter", "Comment"])
# ============================================================================
# PARAMETER NAME MAPPINGS: Template name -> CSV name
# These map the standardized template parameter names to the names used
# in FEM's combined CSV output files.
# ============================================================================
SPATIAL_PARAM_CSV_MAP = {
    "Capacity_PV_roof": "Total capacity solar PV - Roof",
    "Capacity_PV_agri": "Total capacity solar PV - Agri",
    "Capacity_PV_alpine": "Total capacity solar PV - Alpine",
    "Capacity_wind": "Total capacity wind power",
    "Capacity_bioenergy": "Total capacity bioenergy",
    "Capacity_geothermal": "Total capacity geothermal",
    "Capacity_waste_incineration": "Total capacity waste incineration",
    "Capacity_gas": "Total capacity gas",
    "Capacity_nuclear": "Total capacity nuclear",
    "Capacity_hydro_dam": "Total capacity hydro dams",
    "Capacity_hydro_ror": "Total capacity run of river",
    "Capacity_pumped_hydro": "Total capacity pumped hydro",
    "Capacity_battery": "Total capacity battery",
    "Generation_PV_roof": "Annual generation solar PV - Roof",
    "Generation_PV_agri": "Annual generation solar PV - Agri",
    "Generation_PV_alpine": "Annual generation solar PV - Alpine",
    "Generation_wind": "Annual generation wind power",
    "Generation_bioenergy": "Annual generation bioenergy",
    "Generation_geothermal": "Annual generation geothermal",
    "Generation_waste_incineration": "Annual generation waste incineration",
    "Generation_gas": "Annual generation gas",
    "Generation_nuclear": "Annual generation nuclear",
    "Generation_hydro_dam": "Annual generation hydro dam",
    "Generation_hydro_ror": "Annual generation hydro run of river",
    "Charge_pumped_hydro": "Annual charge pumped hydro",
    "Discharge_pumped_hydro": "Annual discharge pumped hydro",
    "Charge_battery": "Annual battery charge",
    "Discharge_battery": "Annual battery discharge",
    "Load_shedding": "Annual load shedding",
    "Charge_pumped_hydro_winter": "Charge pumped hydro WINTER",
    "Charge_pumped_hydro_summer": "Charge pumped hydro SUMMER",
    "Curtailment_PV_roof": "Curtailment solar PV - Roof",
    "Curtailment_PV_agri": "Curtailment solar PV - Agri",
    "Curtailment_PV_alpine": "Curtailment solar PV - Alpine",
    "Curtailment_wind": "Curtailment wind power",
    "Curtailment_solar-wind_optional": "Curtailment solar PV + wind (optional)",
    "Average_netload_winter": "Average netload WINTER",
    "Average_netload_summer": "Average netload SUMMER",
}

SYS_PARAM_CSV_MAP = {
    "Import_to_CH": "Import to CH Annual",
    "Export_from_CH": "Export from CH Annual",
    "Net_import_CH": "Net import CH Annual (Import-Export)",
    "Import_winter": "Import WINTER",
    "Export_winter": "Export WINTER",
    "Net_import_winter": "Net import WINTER (Import-Export)",
    "Import_summer": "Import SUMMER",
    "Export_summer": "Export SUMMER",
    "Net_import_summer": "Net import SUMMER (Import-Export)",
    "Energy_shifted_EV_winter": "Total energy shifted EVs WINTER",
    "Energy_shifted_EV_summer": "Total energy shifted EVs SUMMER",
    "Energy_shifted_HP_winter": "Total energy shifted HPs WINTER",
    "Energy_shifted_HP_summer": "Total energy shifted HPs SUMMER",
    "Load_shedding_CH": "Load shedding Annual (Winter+Summer)",
    "Load_shedding_CH_winter": "Load shedding WINTER",
    "Load_shedding_CH_summer": "Load shedding SUMMER",
    "Generation_curtailment_CH": "Generation curtailment Annual - CH",
    "Generation_curtailment_abroad": "Generation curtailment Annual - Abroad",
    "Import_cost": "Import Cost Annual",
    "Export_revenue": "Export Revenue Annual",
    "Trading_cost": "Trading Costs Annual (Cost - Revenue)",
    "Import_cost_winter": "Import Cost WINTER",
    "Export_revenue_winter": "Export Revenue WINTER",
    "Import_cost_summer": "Import cost SUMMER",
    "Export_revenue_summer": "Export Revenue SUMMER",
    "Electricity_price_CH": "Electricity price in CH",
    "Price_electricity_import_from_AT": "Price for electricity import from AT",
    "Price_electricity_import_from_DE": "Price for electricity import from DE",
    "Price_electricity_import_from_FR": "Price for electricity import from FR",
    "Price_electricity_import_from_IT": "Price for electricity import from IT",
    "Price_electricity_export_from_AT": "Price for electricity export to AT",
    "Price_electricity_export_from_DE": "Price for electricity export to DE",
    "Price_electricity_export_from_FR": "Price for electricity export to FR",
    "Price_electricity_export_from_IT": "Price for electricity export to IT",
    "Annualised_investment_costs": "Investment costs annualised All",
    "Annualised_operation_costs": "Operation costs anualised All",
    "Annualised_costs_all": "Total annualised costs All (with trading costs)",
    "Operational_costs_per_unit": "Operational costs per unit of generated energy",
    "Transmission_grid_expansion_investment_costs": "Transmission grid expansion investment costs",
    "Capacity_grid_expansion_CH": "Grid Expansion within CH",
    "Capacity_grid_expansion_interconnectors": "Grid Expansion to neighbours",
    "Total_emissions": "Total emissions",
    "Time_to_solve_model": "Time to solve model",
    "Memory_requirements": "Memory requirements",
}

TEMP_PARAM_CSV_MAP = {
    "Hourly_generation_PV_roof": "Hourly generation solar PV - Rooftop",
    "Hourly_generation_PV_agri": "Hourly generation solar PV - Agri",
    "Hourly_generation_PV_alpine": "Hourly generation solar PV - Alpine",
    "Hourly_generation_wind": "Hourly generation wind power",
    "Hourly_generation_bioenergy": "Hourly generation bioenergy",
    "Hourly_generation_geothermal": "Hourly generation geothermal",
    "Hourly_generation_waste_incineration": "Hourly generation waste incineration",
    "Hourly_generation_gas": "Hourly generation gas",
    "Hourly_generation_nuclear": "Hourly generation nuclear",
    "Hourly_generation_hydro_dam": "Hourly generation hydro dam",
    "Hourly_generation_hydro_ror": "Hourly generation hydro run of river",
    "Hourly_generation_pumped_hydro": "Hourly generation hydro pumped storage",
    "Hourly_demand_pumped_hydro": "Hourly demand hydro pumped storage",
    "Hourly_generation_battery": "Hourly generation battery",
    "Hourly_demand_battery": "Hourly charge battery",
    "Hourly_EV-DSM_up": "Hourly EV-DSM up",
    "Hourly_EV-DSM_down": "Hourly EV-DSM down",
    "Hourly_HP-DSM_up": "Hourly HP-DSM up",
    "Hourly_HP-DSM_down": "Hourly HP-DSM down",
    "Hourly_generation_curtailment-CH": "Hourly generation curtailment - CH",
    "Hourly_generation_curtailment-abroad": "Hourly generation curtailment - Abroad",
    "Hourly_load_shedding": "Hourly load shedded",
    "Hourly_exchange_CH-DE": "Hourly exchange CH-DE",
    "Hourly_exchange_DE-CH": "Hourly exchange DE-CH",
    "Hourly_exchange_CH-FR": "Hourly exchange CH-FR",
    "Hourly_exchange_FR-CH": "Hourly exchange FR-CH",
    "Hourly_exchange_CH-IT": "Hourly exchange CH-IT",
    "Hourly_exchange_IT-CH": "Hourly exchange IT-CH",
    "Hourly_exchange_CH-AT": "Hourly exchange CH-AT",
    "Hourly_exchange_AT-CH": "Hourly exchange AT-CH",
    "Hourly_import_to_CH": "Hourly import to CH (total)",
    "Hourly_export_from_CH": "Hourly export from CH (total)",
    "Hourly_net_import": "Hourly net import (import-export)",
    "Hourly_net_load": "Hourly net load",
    "Hourly_electricity_price_CH": "Hourly electricity price CH",
    "Hourly_electricity_price_DE": "Hourly electricity price DE",
    "Hourly_electricity_price_FR": "Hourly electricity price FR",
    "Hourly_electricity_price_IT": "Hourly electricity price IT",
    "Hourly_electricity_price_AT": "Hourly electricity price AT",
    "Average_line_loading_CH-lines": "Average line loading - internal lines",
    "Average_line_loading_interconnectors": "Average line loading - interconnectors",
    "Average_line_loading_all_lines": "Average line loading - all lines",
}

# Mapping from new template Input_Spatial names to old FEM workbook names
INPUT_SPATIAL_WB_MAP = {
    "Potential_PV_roof": "Potential solar PV",
    # Potential_PV_agri: not in old workbook
    # Potential_PV_alpine: not in old workbook
    "Potential_bioenergy": "Potential bioenergy",
    "Potential_geothermal": "Potential for geothermal",
    "Potential_new_hydro": "Potential for new hydro",
    "Potential_DSM": "Maximum potential for DSM",
    "Fixed_capacity_pumped_hydro": "Fixed capacity pumped hydro",
    "Fixed_capacity_hydro_dam": "Fixed capacity hydro dams",
    "Fixed_capacity_hydro_ror": "Fixed capacity run of river",
    "Fixed_capacity_nuclear": "Fixed capacity nuclear power",
    "Fixed_capacity_bioenergy": "Fixed capacity solid biomass",
    "Fixed_capacity_geothermal": "Fixed capacity geothermal",
    "Fixed_capacity_waste_incineration": "Fixed capacity waste incineration",
    "Capacity_factor_PV_roof_average": "Capacity factor solar PV, average",
    "Capacity_factor_PV_roof_5th": "Capacity factor solar PV, 5th",
    "Capacity_factor_PV_roof_95th": "Capacity factor solar PV, 95th",
    "Capacity_factor_wind_average": "Capacity factor wind power, average",
    "Capacity_factor_wind_5th": "Capacity factor wind power, 5th",
    "Capacity_factor_wind_95th": "Capacity factor wind power, 95th",
    "Electricity_demand": "Electricity demand",
}

# Mapping from new template Input_Sys names to old FEM workbook names
INPUT_SYS_WB_MAP = {
    "Investment_costs_PV_roof": "Investment costs solar PV",
    "Investment_costs_wind": "Investment costs wind power",
    "Investment_costs_gas": "Investment costs natural gas no CCS",
    "Investment_costs_bioenergy": "Investment costs solid biomass",
    "Investment_costs_geothermal": "Investment costs enhanced geothermal systems",
    "Investment_costs_waste_incineration": "Investment costs waste incineration",
    "Investment_costs_batteries": "Investment costs batteries",
    "Investment_costs_P2X": "Investment costs power-to-X",
    "Fuel_price_gas": "Fuel price for natural gas",
    "Fuel_price_waste": "Fuel price for waste",
    "Fuel_price_bioenergy": "Fuel price for solid biomass",
    "Fuel_price_uranium": "Fuel price for uranium",
    "Transmission_grid_expansion_investment_costs": "Costs for transmission grid expansion",
    "Discount_rate": "Discout rate",
    "Roundtrip_efficiency_batteries": "Roundtrip efficiency batteries",
    "Capacity_factor_PV_roof": "Capacity factor solar PV",
    "Capacity_factor_wind": "Capacity factor wind power",
    "Emission_factor_gas": "Emission factor natural gas (Simple Cycle)",
    "Emission_factor_waste": "Emission factor waste incineration",
    "Emission_factor_bioenergy": "Emission factor solid biomass",
    "Min_load_bioenergy": "Min load solid biomass",
    "Min_load_gas": "Min load biogas",
    "Min_load_waste": "Min load waste incineration",
    "Ramp_up_bioenergy": "Ramp-up solid biomass",
    "Ramp_up_gas": "Ramp-up biogas",
    "Ramp_up_waste": "Ramp-up waste incineration",
    "Ramp_down_bioenergy": "Ramp-down solid biomass",
    "Ramp_down_gas": "Ramp-down biogas",
    "Ramp_down_waste": "Ramp-down waste incineration",
    "Max_hourly_output_hydro_dam": "Max hourly output hydro dams",
    "Max_hourly_output_hydro_ror": "Max hourly output run of river",
    "Max_hourly_output_pumped_hydro": "Max hourly output pumped hydro",
    "Nr_power_system_nodes_CH": "Nb of power system nodes within CH",
    "Installation_of_power_lines_in_CH": "Installation of new power lines in CH",
    "Price_electricity_import_from_AT": "Price for electricity import from AT",
    "Price_electricity_import_from_DE": "Price for electricity import from DE",
    "Price_electricity_import_from_FR": "Price for electricity import from  FR",
    "Price_electricity_import_from_IT": "Price for electricity import from IT",
    "Price_electricity_export_from_AT": "Price for electricity export to AT",
    "Price_electricity_export_from_DE": "Price for electricity export to DE",
    "Price_electricity_export_from_FR": "Price for electricity export to FR",
    "Price_electricity_export_from_IT": "Price for electricity export to IT",
    "Net_transfer_capacity_AT": "Net transfer capacity AT",
    "Net_transfer_capacity_DE": "Net transfer capacity DE",
    "Net_transfer_capacity_FR": "Net transfer capacity FR",
    "Net_transfer_capacity_IT": "Net transfer capacity IT",
    "Electricity_demand_HP": "Yearly electricity demand - heat pump demand",
    "Electricity_demand_EV": "Yearly electricity demand - EV demand",
    "Electricity_demand_other": "Yearly electricity demand - conventional demand",
    "Electricity_demand_total": "Yearly electricity demand - total",
}

# Mapping for Input_Temp parameters
INPUT_TEMP_WB_MAP = {
    "Hourly_electricity_demand_HP": "Hourly electricity demand - heat pumps",
    "Hourly_electricity_demand_EV": "Hourly electricity demand - EVs",
    "Hourly_electricity_demand_other": "Hourly electricity demand - conventional",
    "Hourly_electricity_demand_total": "Hourly electricity demand - total",
}
# ============================================================================
def _try_numeric(val):
    """Try to convert a value to float. Return NaN if not numeric."""
    if val is None:
        return math.nan
    try:
        return float(val)
    except (ValueError, TypeError):
        return math.nan
# ============================================================================
def fill_spatial_output_from_csv(
    model: str,
    df_csv: pd.DataFrame,
    scenarios: List[str],
    parameters: List[Tuple[str, str]],
    n_regions: int,
    n_fem_regions: int = 7
) -> pd.DataFrame:
    """
    Fill spatial output DataFrame from CSV data.
    FEM uses 7 spatial regions (CH01-CH07) mapped to columns 1-7,
    and column 8 for 'Location independent'.
    """
    numbered_columns = [str(i) for i in range(1, n_regions + 1)]
    columns = ["Model", "Scenario", "Parameter", "Unit", "Sum"] + numbered_columns
    rows = []
    for scenario in scenarios:
        for param_name, unit in parameters:
            csv_name = SPATIAL_PARAM_CSV_MAP.get(param_name)
            if csv_name is None:
                row = [model, scenario, param_name, unit, math.nan] + [math.nan] * n_regions
                rows.append(row)
                continue
            mask = (df_csv['Scenario Name'] == scenario) & (df_csv['Output-Parameter'] == csv_name)
            matches = df_csv[mask]
            if len(matches) == 0:
                row = [model, scenario, param_name, unit, math.nan] + [math.nan] * n_regions
                rows.append(row)
                continue
            csv_row = matches.iloc[0]
            row_sum = _try_numeric(csv_row.get('Sum', math.nan))
            values = []
            for i in range(1, n_regions + 1):
                if i <= 7:
                    col_name = f'CH{i:02d}'
                    val = _try_numeric(csv_row.get(col_name, math.nan))
                    values.append(val)
                elif i == 8:
                    # Column 8 = 'Location independent'
                    val = _try_numeric(csv_row.get('Location independent', math.nan))
                    values.append(val)
                else:
                    values.append(math.nan)
            row = [model, scenario, param_name, unit, row_sum] + values
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)
# ============================================================================
def fill_sys_output_from_csv(
    model: str,
    df_csv: pd.DataFrame,
    scenarios: List[str],
    parameters: List[Tuple[str, str]]
) -> pd.DataFrame:
    """Fill system output DataFrame from CSV data."""
    columns = [
        "Model", "Scenario", "Parameter", "Unit",
        "Total", "Average", "5th", "95th", "Min", "Max"
    ]
    # CSV column names (lowercase in CSV)
    csv_stat_cols = ['total', 'average', '5th', '95th', 'min', 'max']
    rows = []
    for scenario in scenarios:
        for param_name, unit in parameters:
            csv_name = SYS_PARAM_CSV_MAP.get(param_name)
            if csv_name is None:
                row = [model, scenario, param_name, unit] + [math.nan] * 6
                rows.append(row)
                continue
            mask = (df_csv['Scenario Name'] == scenario) & (df_csv['Output-Parameter'] == csv_name)
            matches = df_csv[mask]
            if len(matches) == 0:
                row = [model, scenario, param_name, unit] + [math.nan] * 6
                rows.append(row)
                continue
            csv_row = matches.iloc[0]
            stats = [_try_numeric(csv_row.get(c, math.nan)) for c in csv_stat_cols]
            row = [model, scenario, param_name, unit] + stats
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)
# ============================================================================
def fill_temp_output_from_csv(
    model: str,
    df_csv: pd.DataFrame,
    scenarios: List[str],
    parameters: List[Tuple[str, str]],
    n_hours: int
) -> pd.DataFrame:
    """Fill temporal output DataFrame from CSV data."""
    hour_columns = [str(i) for i in range(1, n_hours + 1)]
    columns = ["Model", "Scenario", "Parameter", "Unit"] + hour_columns
    rows = []
    for scenario in scenarios:
        for param_name, unit in parameters:
            csv_name = TEMP_PARAM_CSV_MAP.get(param_name)
            if csv_name is None:
                row = [model, scenario, param_name, unit] + [math.nan] * n_hours
                rows.append(row)
                continue
            mask = (df_csv['Scenario Name'] == scenario) & (df_csv['Output-Parameter'] == csv_name)
            matches = df_csv[mask]
            if len(matches) == 0:
                row = [model, scenario, param_name, unit] + [math.nan] * n_hours
                rows.append(row)
                continue
            csv_row = matches.iloc[0]
            values = []
            for h in hour_columns:
                values.append(_try_numeric(csv_row.get(h, math.nan)))
            row = [model, scenario, param_name, unit] + values
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)
# ============================================================================
def read_input_spatial_from_old_workbook(
    model: str,
    old_wb_path: str,
    years: List[int],
    parameters: List[Tuple[str, str]],
    n_regions: int,
    n_fem_regions: int = 7
) -> pd.DataFrame:
    """
    Read Input_Spatial data from old FEM workbook and reformat to new template.
    Old workbook has header at row 6 with columns:
    Model, Scenario, Input-Parameter, Unit, Sum, Source, Location independent, CH01-CH07
    Columns 1-7 = CH01-CH07, column 8 = Location independent.
    """
    wb = load_workbook(old_wb_path, read_only=True, data_only=True)
    ws = wb['Input_Spatial']
    # Read all data rows (data starts at row 7, header at row 6)
    old_data = {}
    for row in ws.iter_rows(min_row=7, values_only=True):
        r = list(row)
        param_name = r[2] if len(r) > 2 else None
        if param_name and isinstance(param_name, str):
            key = param_name.strip()
            old_data[key] = {
                'sum': r[4] if len(r) > 4 else None,
                'source': r[5] if len(r) > 5 else None,
                'loc_indep': r[6] if len(r) > 6 else None,
                'regions': [r[i] if i < len(r) else None for i in range(7, 7 + 7)]
            }
    wb.close()
    numbered_columns = [str(i) for i in range(1, n_regions + 1)]
    columns = ["Model", "Year", "Parameter", "Unit", "Sum", "Source"] + numbered_columns
    rows = []
    for year in years:
        for param_name, unit in parameters:
            old_name = INPUT_SPATIAL_WB_MAP.get(param_name)
            if old_name and old_name in old_data:
                d = old_data[old_name]
                source = str(d.get('source') or '')
                sum_val = _try_numeric(d.get('sum'))
                values = []
                for i in range(1, n_regions + 1):
                    if i <= 7 and (i - 1) < len(d['regions']):
                        values.append(_try_numeric(d['regions'][i - 1]))
                    elif i == 8:
                        # Column 8 = Location independent
                        values.append(_try_numeric(d.get('loc_indep')))
                    else:
                        values.append(math.nan)
                row = [model, year, param_name, unit, sum_val, source] + values
            else:
                row = [model, year, param_name, unit, math.nan, ""] + [math.nan] * n_regions
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)
# ============================================================================
def read_input_sys_from_old_workbook(
    model: str,
    old_wb_path: str,
    years: List[int],
    parameters: List[Tuple[str, str]]
) -> pd.DataFrame:
    """
    Read Input_Sys data from old FEM workbook and reformat to new template.
    Old workbook header at row 7:
    Model, Scenario, Input-Parameter, Unit, CH(=Total), average, 5th, 95th, min, max, Source
    """
    wb = load_workbook(old_wb_path, read_only=True, data_only=True)
    ws = wb['Input_Sys']
    old_data = {}
    for row in ws.iter_rows(min_row=8, values_only=True):
        r = list(row)
        param_name = r[2] if len(r) > 2 else None
        if param_name and isinstance(param_name, str):
            key = param_name.strip()
            old_data[key] = {
                'total': r[4] if len(r) > 4 else None,
                'average': r[5] if len(r) > 5 else None,
                'p5': r[6] if len(r) > 6 else None,
                'p95': r[7] if len(r) > 7 else None,
                'min': r[8] if len(r) > 8 else None,
                'max': r[9] if len(r) > 9 else None,
                'source': r[10] if len(r) > 10 else None,
            }
    wb.close()
    columns = [
        "Model", "Year", "Parameter", "Unit",
        "Total", "Average", "5th", "95th", "Min", "Max", "Source"
    ]
    rows = []
    for year in years:
        for param_name, unit in parameters:
            old_name = INPUT_SYS_WB_MAP.get(param_name)
            if old_name and old_name in old_data:
                d = old_data[old_name]
                source = str(d.get('source') or '')
                total = _try_numeric(d.get('total'))
                average = _try_numeric(d.get('average'))
                p5 = _try_numeric(d.get('p5'))
                p95 = _try_numeric(d.get('p95'))
                min_val = _try_numeric(d.get('min'))
                max_val = _try_numeric(d.get('max'))
                row = [model, year, param_name, unit, total, average, p5, p95, min_val, max_val, source]
            else:
                row = [model, year, param_name, unit] + [math.nan] * 6 + [""]
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)
# ============================================================================
def read_input_temp_from_old_workbook(
    model: str,
    old_wb_path: str,
    years: List[int],
    parameters: List[Tuple[str, str]],
    n_hours: int
) -> pd.DataFrame:
    """
    Read Input_Temp data from old FEM workbook.
    Old workbook has two year blocks:
      2035 block: year marker at row 4, header at row 5, data rows 6-9
      2050 block: year marker at row 11, header at row 12, data rows 13-16
    """
    wb = load_workbook(old_wb_path, read_only=True, data_only=True)
    ws = wb['Input_Temp']
    all_rows = list(ws.iter_rows(values_only=True))
    wb.close()
    # Parse year blocks
    year_data: Dict[int, Dict[str, list]] = {y: {} for y in years}
    current_year = None
    for row in all_rows:
        r = list(row)
        # Check if this row is a year marker
        if r[0] in years:
            current_year = r[0]
            continue
        # Check if this is a data row (model name in first col, param in third)
        if r[0] == model and current_year and len(r) > 4:
            param = r[2]
            if param and isinstance(param, str):
                values = r[4:4 + n_hours]
                year_data[current_year][param.strip()] = list(values)
    hour_columns = [str(i) for i in range(1, n_hours + 1)]
    columns = ["Model", "Year", "Parameter", "Unit"] + hour_columns
    rows = []
    for year in years:
        for param_name, unit in parameters:
            old_name = INPUT_TEMP_WB_MAP.get(param_name)
            if old_name and old_name in year_data.get(year, {}):
                values = year_data[year][old_name]
                # Pad/truncate to n_hours
                if len(values) < n_hours:
                    values = values + [None] * (n_hours - len(values))
                values = [_try_numeric(v) for v in values[:n_hours]]
                row = [model, year, param_name, unit] + values
            else:
                row = [model, year, param_name, unit] + [math.nan] * n_hours
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)
# ============================================================================
def read_input_sheets_from_workbook(path: str) -> Dict[str, pd.DataFrame]:
    """Read the Input sheets of a workbook in the new template format.

    Returns Input_Spatial, Spatial_Mapping, Input_Sys, Input_Temp and Input_Comments
    as they are, e.g. from a previous FEM reporting file with curated input data.
    """
    sheets = {}
    for name in ["Input_Spatial", "Spatial_Mapping", "Input_Sys", "Input_Temp", "Input_Comments"]:
        df = pd.read_excel(path, sheet_name=name, engine="openpyxl")
        df.columns = [str(c) for c in df.columns]
        sheets[name] = df
    return sheets
# ============================================================================
def build_spatial_mapping_fem() -> pd.DataFrame:
    """Build spatial mapping for FEM's 7 greater regions + location independent."""
    data = [
        (1, "VD, VS, GE"),
        (2, "BE, FR, SO, NE, JU"),
        (3, "BS, BL, AG"),
        (4, "ZH"),
        (5, "GL, SH, AR, AI, SG, GR, TG"),
        (6, "LU, UR, SZ, OW, NW, ZG"),
        (7, "TI"),
        (8, "location independent"),
    ]
    return pd.DataFrame(data, columns=["Area_ID", "Coverage"])
# ============================================================================
def write_excel_file(
    filename: str,
    sheets: Dict[str, pd.DataFrame]
) -> None:
    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
# ============================================================================
def make_reportingtemplate(dir_in, dir_out):
    """Generate an empty reporting template (run_mode 101)."""
    config = get_configuration()
    model = config["selected_model"]
    sheets = {
        "Instructions": build_instructions_df(),
        "Definitions": build_definitions_df(),
        "Output_Spatial_low":
            build_spatial_output_df(
                model,
                config["scenarios"],
                config["output_spatial_parameters"],
                config["n_spatial_low"]
            ),
        "Output_Spatial_high":
            build_spatial_output_df(
                model,
                config["scenarios"],
                config["output_spatial_parameters"],
                config["n_spatial_high"]
            ),
        "Output_Sys":
            build_sys_output_df(
                model,
                config["scenarios"],
                config["output_sys_parameters"]
            ),
        "Output_Temp":
            build_temp_output_df(
                model,
                config["scenarios"],
                config["output_temp_parameters"],
                config["n_hours"]
            ),
        "Input_Spatial":
            build_input_spatial_df(
                model,
                config["years"],
                config["input_spatial_parameters"],
                config["n_spatial_low"]
            ),
        "Spatial_Mapping":
            build_spatial_mapping_df(),
        "Input_Sys":
            build_input_sys_df(
                model,
                config["years"],
                config["input_sys_parameters"]
            ),
        "Input_Temp":
            build_input_temp_df(
                model,
                config["years"],
                config["input_temp_parameters"],
                config["n_hours"]
            ),
        "Input_Comments":
            build_input_comments_df()
    }
    output_path = os.path.join(dir_out, config["output_filename"])
    write_excel_file(output_path, sheets)
    print(f"Empty template written to: {output_path}")

# ============================================================================
def write_res(dir_in, dir_out):
    """
    Write model results into the reporting template (run_mode 102).
    
    Reads combined CSV files (Output_Spatial.csv, Output_Sys.csv, Output_Temp.csv)
    and transfers data into the standardized Excel reporting template.
    Input data is read from the old FEM reporting workbook if available.
    """
    config = get_configuration()
    model = config["selected_model"]
    csv_dir = config["csv_dir"]
    old_wb_path = config.get("old_fem_workbook")
    n_fem_regions = config["n_fem_regions"]

    # ---- Read CSV data ----
    print("Reading Output_Spatial.csv...")
    df_spatial_csv = pd.read_csv(os.path.join(csv_dir, "Output_Spatial.csv"))
    print("Reading Output_Sys.csv...")
    df_sys_csv = pd.read_csv(os.path.join(csv_dir, "Output_Sys.csv"))
    print("Reading Output_Temp.csv...")
    df_temp_csv = pd.read_csv(os.path.join(csv_dir, "Output_Temp.csv"))

    # Determine available scenarios (intersection of config and CSV data)
    csv_scenarios = set(df_spatial_csv["Scenario Name"].unique())
    available_scenarios = [s for s in config["scenarios"] if s in csv_scenarios]
    missing_scenarios = [s for s in config["scenarios"] if s not in csv_scenarios]
    print(f"Available scenarios ({len(available_scenarios)}): {available_scenarios}")
    if missing_scenarios:
        print(f"Missing scenarios ({len(missing_scenarios)}): {missing_scenarios}")

    # ---- Build Output sheets from CSV data ----
    print("Building Output_Spatial_low...")
    output_spatial_low = fill_spatial_output_from_csv(
        model, df_spatial_csv, available_scenarios,
        config["output_spatial_parameters"], config["n_spatial_low"],
        n_fem_regions
    )

    print("Building Output_Spatial_high (empty - FEM has no municipality data)...")
    output_spatial_high = build_spatial_output_df(
        model, available_scenarios,
        config["output_spatial_parameters"], config["n_spatial_high"]
    )

    print("Building Output_Sys...")
    output_sys = fill_sys_output_from_csv(
        model, df_sys_csv, available_scenarios,
        config["output_sys_parameters"]
    )

    print("Building Output_Temp...")
    output_temp = fill_temp_output_from_csv(
        model, df_temp_csv, available_scenarios,
        config["output_temp_parameters"], config["n_hours"]
    )

    # ---- Build Input sheets ----
    spatial_mapping = build_spatial_mapping_fem()
    input_comments = build_input_comments_df()
    input_wb_path = config.get("input_workbook")
    if input_wb_path and os.path.exists(input_wb_path):
        print(f"Reading input sheets from: {input_wb_path}")
        inp = read_input_sheets_from_workbook(input_wb_path)
        input_spatial = inp["Input_Spatial"]
        input_sys = inp["Input_Sys"]
        input_temp = inp["Input_Temp"]
        spatial_mapping = inp["Spatial_Mapping"]
        input_comments = inp["Input_Comments"]
    elif old_wb_path and os.path.exists(old_wb_path):
        print(f"Reading input data from: {old_wb_path}")
        input_spatial = read_input_spatial_from_old_workbook(
            model, old_wb_path, config["years"],
            config["input_spatial_parameters"], config["n_spatial_low"],
            n_fem_regions
        )
        input_sys = read_input_sys_from_old_workbook(
            model, old_wb_path, config["years"],
            config["input_sys_parameters"]
        )
        input_temp = read_input_temp_from_old_workbook(
            model, old_wb_path, config["years"],
            config["input_temp_parameters"], config["n_hours"]
        )
    else:
        print("Old FEM workbook not found - generating empty input sheets.")
        input_spatial = build_input_spatial_df(
            model, config["years"],
            config["input_spatial_parameters"], config["n_spatial_low"]
        )
        input_sys = build_input_sys_df(
            model, config["years"],
            config["input_sys_parameters"]
        )
        input_temp = build_input_temp_df(
            model, config["years"],
            config["input_temp_parameters"], config["n_hours"]
        )

    # ---- Assemble all sheets ----
    sheets = {
        "Instructions": build_instructions_df(),
        "Definitions": build_definitions_df(),
        "Output_Spatial_low": output_spatial_low,
        "Output_Spatial_high": output_spatial_high,
        "Output_Sys": output_sys,
        "Output_Temp": output_temp,
        "Input_Spatial": input_spatial,
        "Spatial_Mapping": spatial_mapping,
        "Input_Sys": input_sys,
        "Input_Temp": input_temp,
        "Input_Comments": input_comments
    }

    output_path = os.path.join(dir_out, config["output_filename"])
    print(f"Writing Excel file to: {output_path}")
    write_excel_file(output_path, sheets)
    print(f"Done! Output written to: {output_path}")

# ============================================================================
def main(run_mode = 102):
    start_time = time.perf_counter()  
    # Directory
    top_dir = os.path.abspath(os.path.dirname(__file__))
    # The input/output directory relative to the top directory
    dir_in	= os.path.abspath(os.path.join(top_dir, "in_files/"))
    dir_out	= top_dir  # Write output to the Reporting_template folder
    if not os.path.exists(dir_out):
        os.makedirs(dir_out)

    if (run_mode == 101): # make empty reporting template
        make_reportingtemplate(dir_in, dir_out)
    elif (run_mode == 102): # write model results
        write_res(dir_in, dir_out)
    else:
        pass

    run_time = round(time.perf_counter() - start_time, 3)
    msg_str = f"Run time : {run_time:.3f} seconds"
    print(msg_str)
# ============================================================================
# Normal run modes:   101 : make template , 102 : write results
if __name__ == "__main__" : main(102)
# ============================================================================
