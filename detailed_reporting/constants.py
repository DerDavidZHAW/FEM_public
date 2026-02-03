"""
Shared constants and helper functions for detailed reporting modules.

This module contains constants and utility functions used across multiple
reporting modules to avoid circular imports.
"""

from pathlib import Path
from typing import List
import pandas as pd


# Project root directory (parent of detailed_reporting folder)
PROJECT_ROOT = Path(__file__).parent.parent

# Conversion factor from CHF2017 to EUR2017: 0.899361453368109
# Conversion factor from EUR2017 to EUR2025: 1.3022
CHF_TO_EUR = 0.899361453368109 * 1.3022

# Winter: t_1-t_2184 and t_6553-t_8760
# Summer: t_2185-t_6552

# ============ PLANT LISTS FOR FILTERING ============

# HP plants for energy shifting (building archetypes with heat pumps)
# From to_consider_from_storage_charge.csv where Demand? = True
HP_PLANTS: List[str] = [
    "minergie_Alpen_[MWh]",
    "minergie_Alpensuedseite_[MWh]",
    "minergie_Jura_[MWh]",
    "minergie_Mittelland_[MWh]",
    "minergie_Voralpen_[MWh]",
    "new_heavy_Alpen_[MWh]",
    "new_heavy_Alpensuedseite_[MWh]",
    "new_heavy_Jura_[MWh]",
    "new_heavy_Mittelland_[MWh]",
    "new_heavy_Voralpen_[MWh]",
    "new_light_Alpen_[MWh]",
    "new_light_Alpensuedseite_[MWh]",
    "new_light_Jura_[MWh]",
    "new_light_Mittelland_[MWh]",
    "new_light_Voralpen_[MWh]",
    "new_medium_Alpen_[MWh]",
    "new_medium_Alpensuedseite_[MWh]",
    "new_medium_Jura_[MWh]",
    "new_medium_Mittelland_[MWh]",
    "new_medium_Voralpen_[MWh]",
    "old_heavy_Alpen_[MWh]",
    "old_heavy_Alpensuedseite_[MWh]",
    "old_heavy_Jura_[MWh]",
    "old_heavy_Mittelland_[MWh]",
    "old_heavy_Voralpen_[MWh]",
    "old_light_Alpen_[MWh]",
    "old_light_Alpensuedseite_[MWh]",
    "old_light_Jura_[MWh]",
    "old_light_Mittelland_[MWh]",
    "old_light_Voralpen_[MWh]",
    "old_medium_Alpen_[MWh]",
    "old_medium_Alpensuedseite_[MWh]",
    "old_medium_Jura_[MWh]",
    "old_medium_Mittelland_[MWh]",
    "old_medium_Voralpen_[MWh]",
]

# Investment cost plants (from to_consider_from_cost_inv_dict.csv where Consider? = True)
INV_COST_PLANTS: List[str] = [
    "CH01_pvrf", "CH01_windon",
    "CH02_pvrf", "CH02_windon",
    "CH03_pvrf", "CH03_windon",
    "CH04_pvrf", "CH04_windon",
    "CH05_pvrf", "CH05_windon",
    "CH06_pvrf", "CH06_windon",
    "CH07_pvrf", "CH07_windon",
    "CH00_CCGTresmethane", "CH00_SCGTresmethane",
    "CH00_CCGTCCS", "CH00_SCGTfossil",
    "CH00_battery", "CH00_hydrogen",
    "CH00_oil", "CH00_nuclear",
]

# Operation cost / emissions / gen plants (from respective CSVs where True)
# These are CH plants that we consider for Swiss costs/emissions/generation
OP_COST_PLANTS: List[str] = [
    "CH00_battery", "CH00_CCGTCCS", "CH00_CCGTresmethane", "CH00_dam",
    "CH00_hydrogen", "CH00_nuclear", "CH00_oil", "CH00_psp_close",
    "CH00_SCGTfossil", "CH00_SCGTresmethane",
    "CH01_battery", "CH01_biomass", "CH01_CCGTCCS", "CH01_other", "CH01_pvrf", "CH01_windon",
    "CH02_battery", "CH02_biomass", "CH02_CCGTCCS", "CH02_other", "CH02_pvrf", "CH02_windon",
    "CH03_battery", "CH03_biomass", "CH03_CCGTCCS", "CH03_nuclear", "CH03_other", "CH03_pvrf", "CH03_windon",
    "CH04_battery", "CH04_biomass", "CH04_CCGTCCS", "CH04_other", "CH04_pvrf", "CH04_windon",
    "CH05_battery", "CH05_biomass", "CH05_CCGTCCS", "CH05_other", "CH05_pvrf", "CH05_windon",
    "CH06_battery", "CH06_biomass", "CH06_CCGTCCS", "CH06_other", "CH06_pvrf", "CH06_windon",
    "CH07_battery", "CH07_biomass", "CH07_CCGTCCS", "CH07_other", "CH07_pvrf", "CH07_windon",
    "large_psp", "medium_reservior",
]

# Emissions plants (same as OP_COST_PLANTS for CH)
EMISSIONS_PLANTS: List[str] = OP_COST_PLANTS.copy()

# Generation plants for total gen calculation (same as OP_COST_PLANTS for CH)
GEN_PLANTS: List[str] = OP_COST_PLANTS.copy()


def is_winter_t(t: str) -> bool:
    """Return True if time index t (e.g., 't_6553') falls in winter.

    Winter is defined as t_1..t_2184 and t_6553..t_8760.
    """
    try:
        n = int(str(t).split("_")[-1])
    except Exception:
        return False
    return (1 <= n <= 2184) or (6553 <= n <= 8760)


def is_summer_t(t: str) -> bool:
    """Return True if time index t falls in summer (the complement of winter)."""
    try:
        n = int(str(t).split("_")[-1])
    except Exception:
        return False
    return (2185 <= n <= 6552)


def get_run_year(scenario_name: str) -> int:
    """Get run_year from scenario settings.csv.
    
    The settings.csv is written at the start of each scenario run, so this
    should be available even before the model is solved.
    """
    settings_path = PROJECT_ROOT / "output" / scenario_name / "settings.csv"
    df = pd.read_csv(settings_path, index_col=0)
    return int(df.loc["run_year"].iloc[0]) # type: ignore


def get_flexible_household_heatpump_share(scenario_name: str) -> float:
    """Get flexible_household_heatpump_share from scenario settings.csv.
    
    Returns the fraction of heat pump demand that is flexible.
    """
    settings_path = PROJECT_ROOT / "output" / scenario_name / "settings.csv"
    df = pd.read_csv(settings_path, index_col=0)
    return float(df.loc["flexible_household_heatpump_share"].iloc[0]) # type: ignore


def get_eu_policy(scenario_name: str) -> str:
    """Get eu_policy from scenario settings.csv.
    
    Returns 'GA' (GlobalAmbition) or 'DE' (DistributedEnergy).
    """
    settings_path = PROJECT_ROOT / "output" / scenario_name / "settings.csv"
    df = pd.read_csv(settings_path, index_col=0)
    return str(df.loc["eu_policy"].iloc[0]) # type: ignore


def get_weather_year(scenario_name: str) -> int:
    """Get weather_year from scenario settings.csv.
    
    Returns the weather year used for the scenario.
    """
    settings_path = PROJECT_ROOT / "output" / scenario_name / "settings.csv"
    df = pd.read_csv(settings_path, index_col=0)
    return int(df.loc["weather_year"].iloc[0]) # type: ignore


def read_full_ev_demand(run_year: int) -> pd.DataFrame:
    """Read the full EV demand from source CSV (100% of EV consumption).
    
    This returns the total EV electricity demand before any splitting into
    flexible/inflexible portions.
    
    Parameters
    ----------
    run_year : int
        Model year (e.g., 2035, 2050)
    
    Returns
    -------
    pd.DataFrame
        DataFrame with 'T' index and 'value' column in MWh
    """
    path = PROJECT_ROOT / "input" / "demand" / f"EV_demand_hourly_{run_year}.csv"
    df = pd.read_csv(path)
    # Convert 't' column (1, 2, 3...) to T format (t_1, t_2, t_3...)
    df["T"] = "t_" + df.iloc[:, 0].astype(str)
    df["value"] = df.iloc[:, 1]  # demand_[MWh] column
    return df[["T", "value"]]


def read_full_hp_demand(run_year: int, weather_year: int) -> pd.DataFrame:
    """Read the full household heat pump demand from building archetypes CSV.
    
    This returns the total HP electricity demand (100%) before any splitting
    into flexible/inflexible portions. Uses the BA_el_con data from the
    categorized_profiles CSV.
    
    Parameters
    ----------
    run_year : int
        Model year (e.g., 2035, 2050)
    weather_year : int
        Weather year (e.g., 1995, 2009)
    
    Returns
    -------
    pd.DataFrame
        DataFrame with 'T' index and 'value' column in MWh
    """
    path = PROJECT_ROOT / "input" / "demand" / f"categorized_profiles_{run_year}_{weather_year}.csv"
    data = pd.read_csv(path)
    
    # Filter for HP heating system and electricity demand
    hp_data = data[data['heating_system_group'].str.contains('HP', na=False)]
    el_data = hp_data[hp_data['TS_Type'] == 'electricity demand kWh']
    
    # Get hourly columns (datetime format like '01.01.1995 00:00')
    # Columns are: age_construction_group, heating_system_group, climate_zone_group, 
    # TS_Type, then 8760 hourly columns, then negative_capacity, positive_capacity, power_of_HP
    hourly_cols = [c for c in el_data.columns if '.' in c and ':' in c]
    
    # Sum across all building archetypes for each hour
    hourly_sums = el_data[hourly_cols].sum(axis=0)
    
    # Convert to DataFrame with T index
    result = pd.DataFrame({
        "T": [f"t_{i+1}" for i in range(len(hourly_sums))],
        "value": hourly_sums.values / 1000.0  # Convert kWh to MWh # type: ignore
    })
    
    return result


def read_base_demand(run_year: int, weather_year: int, eu_policy: str) -> pd.DataFrame:
    """Read the base electricity demand for Switzerland from source CSV.
    
    This returns the hourly base electricity demand for CH00 from the 
    demand input file (demand_{eu_policy}_{run_year}_{weather_year}.csv).
    
    Note: This is the base demand BEFORE adding EV/HP consumption.
    The model subtracts BA_el_con (HP demand) from this in read_demand_data,
    but for net load we need the raw base demand.
    
    Parameters
    ----------
    run_year : int
        Model year (e.g., 2035, 2050)
    weather_year : int
        Weather year (e.g., 1995, 2009)
    eu_policy : str
        EU policy scenario ('GA' for GlobalAmbition, 'DE' for DistributedEnergy)
    
    Returns
    -------
    pd.DataFrame
        DataFrame with 'T' column and 'value' column in MWh
    """
    policy_name = "GlobalAmbition" if eu_policy == "GA" else "DistributedEnergy"
    path = PROJECT_ROOT / "input" / "demand" / f"demand_{policy_name}_{run_year}_{weather_year}.csv"
    df = pd.read_csv(path)
    
    # Create T column from 't' column (1, 2, 3... -> t_1, t_2, t_3...)
    df["T"] = "t_" + df["t"].astype(str)
    
    # CH00 column contains Switzerland's hourly demand in MWh
    df["value"] = df["CH00"]
    
    return df[["T", "value"]]
