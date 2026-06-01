"""
Export spatial distribution summary table for Swiss reporting.

This module generates a CSV table following the template in
`detailed_reporting/details_on_Output_Spatial.csv` with the columns:
"Output-Parameter, Unit, Given, Added".

Given represents exogenously provided assets (brownfield), typically read from
infeed potentials or pre-installed capacities. Added represents endogenously
added assets from the optimization, typically read from investable generators.

The function reads model output CSVs from `output/<scenario_name>/` and, if
unavailable, falls back to `output/test/` to match expected structures.
"""

from pathlib import Path
from typing import List, Tuple, Optional, Union

import pandas as pd

from model.version import MODEL_VERSION
from detailed_reporting.constants import (
    is_winter_t, is_summer_t, CHF_TO_EUR, get_run_year, get_weather_year,
    read_full_ev_demand, read_full_hp_demand, get_subscenario_weight
)


# Cost files whose value column must be divided by the subscenario weight to
# recover the unweighted per-subscenario value (see user spec).
_WEIGHT_DIVIDE_COST_FILES = {
    "cost_inv_dict.csv": "cost_CHF",
    "cost_op_dict.csv": "cost_CHF",
}


CH_ZONES: List[str] = [f"CH0{i}" for i in range(1, 8)]

# Plants from storage_charge that represent flexible demand (not arbitrage/storage)
STORAGE_CHARGE_DEMAND_PLANTS = [
    'CH00_electrolyzer',
    'DH_Alpen_HPG', 'DH_Alpen_HPNew', 'DH_Alpen_resistiveNew',
    'DH_Jura_HPG', 'DH_Jura_HPNew', 'DH_Jura_resistiveNew',
    'DH_medium_HPNew', 'DH_medium_resistiveNew',
    'DH_Mittelland_HPG', 'DH_Mittelland_HPNew', 'DH_Mittelland_resistiveNew',
    'DH_Voralpen_HPG', 'DH_Voralpen_HPNew', 'DH_Voralpen_resistiveNew',
    'EV_CH',
    'ILHT_Alpen_HPNew', 'ILHT_Alpen_resistiveNew',
    'ILHT_Alpensuedseite_HPNew', 'ILHT_Alpensuedseite_resistiveNew',
    'ILHT_Jura_HPNew', 'ILHT_Jura_resistiveNew',
    'ILHT_Mittelland_HPNew', 'ILHT_Mittelland_resistiveNew',
    'ILHT_Voralpen_HPNew', 'ILHT_Voralpen_resistiveNew',
    'ILLT_Alpen_HPNew', 'ILLT_Alpen_resistiveNew',
    'ILLT_Alpensuedseite_HPNew', 'ILLT_Alpensuedseite_resistiveNew',
    'ILLT_Jura_HPNew', 'ILLT_Jura_resistiveNew',
    'ILLT_Mittelland_HPNew', 'ILLT_Mittelland_resistiveNew',
    'ILLT_Voralpen_HPNew', 'ILLT_Voralpen_resistiveNew',
    'minergie_Alpen_[MWh]', 'minergie_Alpensuedseite_[MWh]', 'minergie_Jura_[MWh]',
    'minergie_Mittelland_[MWh]', 'minergie_Voralpen_[MWh]',
    'new_heavy_Alpen_[MWh]', 'new_heavy_Alpensuedseite_[MWh]', 'new_heavy_Jura_[MWh]',
    'new_heavy_Mittelland_[MWh]', 'new_heavy_Voralpen_[MWh]',
    'new_light_Alpen_[MWh]', 'new_light_Alpensuedseite_[MWh]', 'new_light_Jura_[MWh]',
    'new_light_Mittelland_[MWh]', 'new_light_Voralpen_[MWh]',
    'new_medium_Alpen_[MWh]', 'new_medium_Alpensuedseite_[MWh]', 'new_medium_Jura_[MWh]',
    'new_medium_Mittelland_[MWh]', 'new_medium_Voralpen_[MWh]',
    'old_heavy_Alpen_[MWh]', 'old_heavy_Alpensuedseite_[MWh]', 'old_heavy_Jura_[MWh]',
    'old_heavy_Mittelland_[MWh]', 'old_heavy_Voralpen_[MWh]',
    'old_light_Alpen_[MWh]', 'old_light_Alpensuedseite_[MWh]', 'old_light_Jura_[MWh]',
    'old_light_Mittelland_[MWh]', 'old_light_Voralpen_[MWh]',
    'old_medium_Alpen_[MWh]', 'old_medium_Alpensuedseite_[MWh]', 'old_medium_Jura_[MWh]',
    'old_medium_Mittelland_[MWh]', 'old_medium_Voralpen_[MWh]',
    'V2G_CH'
]

# Plants from gen that represent VRE generation for net load (only PV and wind, not biomass)
GEN_RENEWABLE_PLANTS = [
    'CH01_pvrf', 'CH01_windon',
    'CH02_pvrf', 'CH02_windon',
    'CH03_pvrf', 'CH03_windon',
    'CH04_pvrf', 'CH04_windon',
    'CH05_pvrf', 'CH05_windon',
    'CH06_pvrf', 'CH06_windon',
    'CH07_pvrf', 'CH07_windon'
]

# Technologies to include from infeed for net load (only PV and wind, not ror)
INFEED_VRE_TECHS = ["windon", "pvrf", "pv"]


def _pyomo_to_dataframe(pyomo_obj, expected_cols: Optional[List[str]] = None) -> pd.DataFrame:
    """Convert Pyomo variable or parameter to DataFrame.
    
    Handles both indexed and simple Pyomo components.
    Returns empty DataFrame if conversion fails.
    """
    try:
        if pyomo_obj is None:
            return pd.DataFrame()
        
        # Check if it's a Pyomo component with extract_values method
        if hasattr(pyomo_obj, 'extract_values'):
            data_dict = pyomo_obj.extract_values()
            if not data_dict:
                return pd.DataFrame()
            
            # Determine structure from first key
            first_key = next(iter(data_dict.keys()))
            if isinstance(first_key, tuple):
                # Multi-indexed: convert to records
                records = []
                for key, value in data_dict.items():
                    if isinstance(key, tuple):
                        row = {f"col_{i}": k for i, k in enumerate(key)}
                    else:
                        row = {"col_0": key}
                    row["value"] = value
                    records.append(row)
                df = pd.DataFrame(records)

                # Rename using expected columns if lengths align
                if expected_cols:
                    # expected_cols includes the intended column names including 'value'
                    if len(expected_cols) == len(df.columns):
                        df.columns = expected_cols
                        return df
                    if len(expected_cols) == len(df.columns) - 1:
                        rename_map = {f"col_{i}": expected_cols[i] for i in range(len(expected_cols) - 1)}
                        df = df.rename(columns=rename_map)
                        return df

                # Fallback heuristics
                if len(df.columns) == 3:  # e.g., (P_gen, T, value)
                    df = df.rename(columns={"col_0": "P_gen", "col_1": "T"})
                elif len(df.columns) == 2:  # e.g., (P_gen, value)
                    df = df.rename(columns={"col_0": "P_gen"})

                return df
            else:
                # Simple index
                df = pd.DataFrame(list(data_dict.items()), columns=["index", "value"])
                if expected_cols and len(expected_cols) == 2:
                    df.columns = expected_cols
                return df
        
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _scenario_or_test_path(scenario_name: str, filename: str) -> Path:
    scen_path = Path("output") / scenario_name / filename
    if scen_path.exists():
        return scen_path
    test_path = Path("output") / "test" / filename
    return test_path


def _read_csv(scenario_name: str, filename: str, subscenario: str = None) -> pd.DataFrame:  # type: ignore
    path = _scenario_or_test_path(scenario_name, filename)
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if subscenario is None or df.empty:
        return df
    if "Scenarios" in df.columns:
        return df[df["Scenarios"] == subscenario].copy()
    if "scenario" in df.columns:
        out = df[df["scenario"] == subscenario].copy()
        value_col = _WEIGHT_DIVIDE_COST_FILES.get(filename)
        if value_col is not None and not out.empty and value_col in out.columns:
            weight = get_subscenario_weight(scenario_name, subscenario)
            if weight != 0:
                out[value_col] = out[value_col] / weight
        return out
    return df


def _get_data(model, scenario_name: str, attr_name: str, csv_name: str,
              subscenario: str = None) -> pd.DataFrame:  # type: ignore
    """Get data from model attribute or CSV file.
    
    Parameters
    ----------
    model : pyomo.ConcreteModel or None
        Model instance to extract from, or None to use CSV
    scenario_name : str
        Scenario name for CSV fallback
    attr_name : str
        Attribute name on model (e.g., 'gen_max')
    csv_name : str
        CSV filename (e.g., 'gen_max.csv')
    
    Returns
    -------
    pd.DataFrame
    """
    # Define expected columns by attribute
    expected_columns_map = {
        "gen": ["P_gen", "T", "Scenarios", "value"],
        "gen_max": ["P_gen", "Scenarios", "value"],
        "gen_max_infeedp": ["Infeedp", "Scenarios", "value"],
        "infeed": ["Consumer_with_infeed", "Tech_infeed", "T", "Scenarios", "value"],
        "storage_charge": ["P_pumping", "T", "Scenarios", "value"],
        "lostload": ["Consumer", "T", "lostLoad_step", "Scenarios", "value"],
        "demand": ["Consumer", "Consumption_types_inflex", "T", "Scenarios", "value"],
        "EV_inflexible_demand": ["Node", "T", "Scenarios", "value"],
        "HP_inflexible_demand": ["Node", "T", "Scenarios", "value"],
    }
    expected_cols = expected_columns_map.get(attr_name)

    # Try model first (only when not filtering for a specific subscenario; the model
    # object would aggregate over subscenarios and can't be sliced here).
    if subscenario is None and model is not None and hasattr(model, attr_name):
        df = _pyomo_to_dataframe(getattr(model, attr_name), expected_cols)
        if not df.empty:
            return df

    # Fall back to CSV
    df = _read_csv(scenario_name, csv_name, subscenario=subscenario)
    # If expected columns provided and csv has same length, align names
    if expected_cols and not df.empty and len(df.columns) == len(expected_cols):
        df.columns = expected_cols
    return df


def _parse_t_index(t: str) -> int:
    try:
        return int(str(t).split("_")[-1])
    except Exception:
        return -1


def _is_winter_t(t: str) -> bool:
    """Wrapper for reporting_main.is_winter_t."""
    return is_winter_t(t)


def _is_summer_t(t: str) -> bool:
    """Wrapper for reporting_main.is_summer_t."""
    return is_summer_t(t)


def _sum_values(df: pd.DataFrame, value_col: str = "value") -> float:
    if df.empty or value_col not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[value_col], errors="coerce").fillna(0.0).sum())


def _sum_gen_max_infeedp_by_prefix(df: pd.DataFrame, tech_suffix: str, zones: List[str]) -> float:
    if df.empty:
        return 0.0
    col_name = "Infeedp" if "Infeedp" in df.columns else df.columns[0]
    mask = df[col_name].isin([f"{z}_{tech_suffix}" for z in zones])
    return _sum_values(df.loc[mask])


def _sum_gen_max_by_prefix(df: pd.DataFrame, tech_suffix: str, zones: List[str]) -> float:
    if df.empty:
        return 0.0
    mask = df["P_gen"].isin([f"{z}_{tech_suffix}" for z in zones])
    return _sum_values(df.loc[mask])


def _sum_gen_by_prefix(df: pd.DataFrame, tech_suffix: str, zones: List[str]) -> float:
    if df.empty:
        return 0.0
    mask = df["P_gen"].isin([f"{z}_{tech_suffix}" for z in zones])
    return _sum_values(df.loc[mask])


def _sum_infeed(df: pd.DataFrame, tech: str, consumer: str = "CH00_fixedconsumer") -> float:
    if df.empty:
        return 0.0
    mask = (df.get("Consumer_with_infeed", "") == consumer) & (df.get("Tech_infeed", "") == tech)
    return _sum_values(df.loc[mask]) # type: ignore


def _sum_gen_max_for_plants(df: pd.DataFrame, plants: List[str]) -> float:
    if df.empty:
        return 0.0
    mask = df["P_gen"].isin(plants)
    return _sum_values(df.loc[mask])


def _sum_storage_charge_for_plants(df: pd.DataFrame, plants: List[str]) -> float:
    if df.empty:
        return 0.0
    mask = df[df.columns[0]].isin(plants)  # first column is typically P_pumping
    return _sum_values(df.loc[mask])


def _sum_storage_charge_season(df: pd.DataFrame, plants: List[str], season: str) -> float:
    if df.empty:
        return 0.0
    plant_col = df.columns[0]
    mask_plants = df[plant_col].isin(plants)
    if "T" in df.columns:
        if season == "winter":
            mask_time = df["T"].astype(str).map(_is_winter_t)
        else:
            mask_time = df["T"].astype(str).map(_is_summer_t)
        return _sum_values(df.loc[mask_plants & mask_time])
    return _sum_values(df.loc[mask_plants])


def _sum_lostload(df: pd.DataFrame, consumer: str = "CH00_fixedconsumer") -> float:
    if df.empty:
        return 0.0
    mask = df.get("Consumer", "") == consumer
    return _sum_values(df.loc[mask]) # type: ignore


def _average_netload(
    df_demand: pd.DataFrame,
    df_infeed: pd.DataFrame,
    df_gen: pd.DataFrame,
    df_full_ev: pd.DataFrame,
    df_full_hp: pd.DataFrame,
    season: str
) -> float:
    """Calculate average net load for a season.
    
    Net load = (base demand + full EV demand + full HP demand) - (given renewables + added renewables)
    
    This represents the underlying demand minus VRE generation, before any 
    flexibility/shifting/storage is applied.
    
    Components:
    - base demand: from df_demand (CH00_fixedconsumer) - note: this already has BA_el_con subtracted
    - full EV demand: 100% of EV consumption from EV_demand_hourly_*.csv
    - full HP demand: 100% of household HP consumption from categorized_profiles (BA_el_con)
    - given renewables: from df_infeed (exogenous feed-in)
    - added renewables: from df_gen (endogenously invested renewables per GEN_RENEWABLE_PLANTS)
    
    Parameters
    ----------
    df_demand : pd.DataFrame
        Base consumption from model.demand (already has BA_el_con subtracted)
    df_infeed : pd.DataFrame
        Given renewable feed-in from model.infeed
    df_gen : pd.DataFrame
        Endogenous generation from model.gen
    df_full_ev : pd.DataFrame
        Full EV demand (100%) from read_full_ev_demand
    df_full_hp : pd.DataFrame
        Full HP demand (100%) from read_full_hp_demand
    season : str
        "winter" or "summer"
        
    Returns
    -------
    float
        Average netload in GWh per hour
    """
    
    # 1. Base demand for CH00 (note: this already has BA_el_con subtracted in read_demand_data)
    ch_demand = df_demand[(df_demand["Consumer"] == "CH00_fixedconsumer")]
    d = ch_demand[["T", "value"]].rename(columns={"value": "demand"}).copy()
    
    # 2. Given renewables from infeed (only wind and PV, not ror)
    ch_infeed = df_infeed[
        (df_infeed["Consumer_with_infeed"] == "CH00_fixedconsumer") &
        (df_infeed["Tech_infeed"].isin(INFEED_VRE_TECHS))
    ]
    i = ch_infeed.groupby("T", as_index=False)["value"].sum().rename(columns={"value": "infeed"}) # type: ignore
    
    # 3. Added renewables from gen (only wind and PV, not biomass)
    added_ren = df_gen[df_gen["P_gen"].isin(GEN_RENEWABLE_PLANTS)]
    added_r = added_ren.groupby("T", as_index=False)["value"].sum().rename(columns={"value": "added_ren"}) # type: ignore
    
    # 4. Full EV demand (100% of EV consumption)
    if not df_full_ev.empty:
        ev_d = df_full_ev.rename(columns={"value": "ev_full"})
    else:
        ev_d = pd.DataFrame(columns=["T", "ev_full"])
    
    # 5. Full HP demand (100% of household HP consumption)
    if not df_full_hp.empty:
        hp_d = df_full_hp.rename(columns={"value": "hp_full"})
    else:
        hp_d = pd.DataFrame(columns=["T", "hp_full"])
    
    # Merge all components by time index
    merged = d.copy()
    merged = pd.merge(merged, i, on="T", how="left")
    merged = pd.merge(merged, added_r, on="T", how="left")
    merged = pd.merge(merged, ev_d, on="T", how="left")
    merged = pd.merge(merged, hp_d, on="T", how="left")
    merged = merged.fillna({"infeed": 0.0, "added_ren": 0.0, "ev_full": 0.0, "hp_full": 0.0})
    
    # Net load = (base demand + full EV + full HP) - (infeed + added_ren)
    merged["netload"] = (merged["demand"] + merged["ev_full"] + merged["hp_full"]) - (merged["infeed"] + merged["added_ren"])
    
    # Filter by season
    if season == "winter":
        mask_time = merged["T"].astype(str).map(_is_winter_t)
    else:
        mask_time = merged["T"].astype(str).map(_is_summer_t)
    season_df = merged.loc[mask_time]
    
    if season_df.empty:
        return 0.0
    
    # Average per hour, convert MWh to GWh
    return float(season_df["netload"].mean() / 1000.0)



def export_output_spatial(model, scenario_name, model_version: str = None,  # type: ignore
                          subscenario: str = None):  # type: ignore
    """
    Build Output_Spatial.csv with spatial breakdown per Swiss region.

    Parameters
    ----------
    model : pyomo.ConcreteModel
        The solved Pyomo model instance. Not strictly required for this exporter,
        which reads standardized CSV outputs. Present for API consistency.
    scenario_name : str
        Name of the scenario, used to locate `output/<scenario_name>/` files.
    model_version : str
        Model version string to include in output (default: MODEL_VERSION from model/version.py)
    """
    # Use MODEL_VERSION from model/version.py if not provided
    if model_version is None:
        model_version = MODEL_VERSION
    
    # Ensure output directory exists
    report_dir = Path("output") / scenario_name / "detailed_reporting"
    if subscenario is not None:
        report_dir = report_dir / subscenario
    report_dir.mkdir(parents=True, exist_ok=True)

    # Define report structure: (parameter name, unit, spatial_resolution)
    # spatial_resolution: "CH00" = location independent only, "CH01-CH07" = zones only, "CH00 and CH01-CH07" = both
    REPORT_ROWS = [
        ("Total capacity solar PV - Roof", "GWp", "CH01-CH07"),
        ("Total capacity solar PV - Agri", "GWp", ""),
        ("Total capacity solar PV - Alpine", "GWp", ""),
        ("Total capacity wind power", "GW", "CH01-CH07"),
        ("Total capacity bioenergy", "GW", "CH00 and CH01-CH07"),
        ("Total capacity geothermal", "GW", ""),
        ("Total capacity waste incineration", "GW", ""),
        ("Total capacity gas", "GW", "CH00 and CH01-CH07"),
        ("Total capacity nuclear", "GW", "CH00 and CH01-CH07"),
        ("Total capacity hydro dams", "GW", "CH00"),
        ("Total capacity run of river", "GW", "CH00"),
        ("Total capacity pumped hydro", "GW", "CH00"),
        ("Total capacity battery", "GW", "CH00 and CH01-CH07"),
        ("Annual generation solar PV - Roof", "GWh/yr", "CH00 and CH01-CH07"),
        ("Annual generation solar PV - Agri", "GWh/yr", ""),
        ("Annual generation solar PV - Alpine", "GWh/yr", ""),
        ("Annual generation wind power", "GWh/yr", "CH00 and CH01-CH07"),
        ("Annual generation bioenergy", "GWh/yr", "CH00 and CH01-CH07"),
        ("Annual generation geothermal", "GWh/yr", ""),
        ("Annual generation waste incineration", "GWh/yr", ""),
        ("Annual generation gas", "GWh/yr", "CH00 and CH01-CH07"),
        ("Annual generation nuclear", "GWh/yr", "CH00 and CH01-CH07"),
        ("Annual generation hydro dam", "GWh/yr", "CH00"),
        ("Annual generation hydro run of river", "GWh/yr", "CH00"),
        ("Annual discharge pumped hydro", "GWh/yr", "CH00"),
        ("Annual charge pumped hydro", "GWh/yr", "CH00"),
        ("Annual battery charge", "GWh/yr", "CH00 and CH01-CH07"),
        ("Annual battery discharge", "GWh/yr", "CH00 and CH01-CH07"),
        ("Annual load shedding", "GWh/yr", "CH00"),
        ("Charge pumped hydro WINTER", "GWh", "CH00"),
        ("Charge pumped hydro SUMMER", "GWh", "CH00"),
        ("Curtailment solar PV - Roof", "GWh/yr", ""),
        ("Curtailment solar PV - Agri", "GWh/yr", ""),
        ("Curtailment solar PV - Alpine", "GWh/yr", ""),
        ("Curtailment wind power", "GWh/yr", ""),
        ("Average netload WINTER", "GWh", "CH00"),
        ("Average netload SUMMER", "GWh", "CH00"),
    ]

    # Load commonly used datasets (from model if available, else from CSV)
    df_gen_max = _get_data(model, scenario_name, "gen_max", "gen_max.csv", subscenario=subscenario)
    df_gen_max_infeedp = _get_data(model, scenario_name, "gen_max_infeedp", "gen_max_infeedp.csv", subscenario=subscenario)
    df_gen = _get_data(model, scenario_name, "gen", "gen.csv", subscenario=subscenario)
    df_infeed = _get_data(model, scenario_name, "infeed", "infeed.csv", subscenario=subscenario)
    df_storage_charge = _get_data(model, scenario_name, "storage_charge", "storage_charge.csv", subscenario=subscenario)
    df_lostload = _get_data(model, scenario_name, "lostload", "lostload.csv", subscenario=subscenario)
    df_demand = _get_data(model, scenario_name, "demand", "demand.csv", subscenario=subscenario)

    # Read full EV and HP demand from source files (100%, before flexibility splitting)
    run_year = get_run_year(scenario_name, subscenario)
    weather_year = get_weather_year(scenario_name, subscenario)
    df_full_ev = read_full_ev_demand(run_year)
    df_full_hp = read_full_hp_demand(run_year, weather_year)

    # Helper functions for per-zone calculations
    def _gen_max_for_plant(df: pd.DataFrame, plant: str) -> float:
        if df.empty:
            return 0.0
        mask = df["P_gen"] == plant
        return _sum_values(df.loc[mask])

    def _gen_max_infeedp_for_plant(df: pd.DataFrame, plant: str) -> float:
        if df.empty:
            return 0.0
        col = "Infeedp" if "Infeedp" in df.columns else df.columns[0]
        mask = df[col] == plant
        return _sum_values(df.loc[mask])

    def _gen_for_plant(df: pd.DataFrame, plant: str) -> float:
        if df.empty:
            return 0.0
        mask = df["P_gen"] == plant
        return _sum_values(df.loc[mask])

    def _storage_charge_for_plant(df: pd.DataFrame, plant: str) -> float:
        if df.empty:
            return 0.0
        col = "P_pumping" if "P_pumping" in df.columns else df.columns[0]
        mask = df[col] == plant
        return _sum_values(df.loc[mask])

    def _storage_charge_for_plant_season(df: pd.DataFrame, plant: str, season: str) -> float:
        if df.empty:
            return 0.0
        col = "P_pumping" if "P_pumping" in df.columns else df.columns[0]
        mask_plant = df[col] == plant
        if "T" in df.columns:
            if season == "winter":
                mask_time = df["T"].astype(str).map(_is_winter_t)
            else:
                mask_time = df["T"].astype(str).map(_is_summer_t)
            return _sum_values(df.loc[mask_plant & mask_time])
        return _sum_values(df.loc[mask_plant])

    def _max_infeed_for_tech(df: pd.DataFrame, tech: str) -> float:
        if df.empty:
            return 0.0
        mask = (df.get("Consumer_with_infeed", "") == "CH00_fixedconsumer") & (df.get("Tech_infeed", "") == tech)
        series = pd.to_numeric(df.loc[mask, "value"], errors="coerce").fillna(0.0)  # type: ignore
        return float(series.max()) if len(series) > 0 else 0.0

    def _sum_infeed_for_tech(df: pd.DataFrame, tech: str) -> float:
        if df.empty:
            return 0.0
        mask = (df.get("Consumer_with_infeed", "") == "CH00_fixedconsumer") & (df.get("Tech_infeed", "") == tech)
        return _sum_values(df.loc[mask])  # type: ignore

    # Calculator per Output-Parameter
    # Returns dict with keys: "Location independent", "CH01", ..., "CH07"
    def calc_row(param: str) -> dict:
        result = {"Location independent": "", "CH01": "", "CH02": "", "CH03": "", "CH04": "", "CH05": "", "CH06": "", "CH07": ""}

        # === CAPACITIES ===
        if param == "Total capacity solar PV - Roof":
            # CH01-CH07 only: infeedp (given) + gen_max (added) per zone
            for zone in CH_ZONES:
                infeedp_val = _gen_max_infeedp_for_plant(df_gen_max_infeedp, f"{zone}_pvrf") / 1000.0
                gen_max_val = _gen_max_for_plant(df_gen_max, f"{zone}_pvrf") / 1000.0
                result[zone] = f"{infeedp_val + gen_max_val:.3f}"
            return result

        if param == "Total capacity solar PV - Agri":
            return result  # empty

        if param == "Total capacity solar PV - Alpine":
            return result  # empty

        if param == "Total capacity wind power":
            # CH01-CH07 only
            for zone in CH_ZONES:
                infeedp_val = _gen_max_infeedp_for_plant(df_gen_max_infeedp, f"{zone}_windon") / 1000.0
                gen_max_val = _gen_max_for_plant(df_gen_max, f"{zone}_windon") / 1000.0
                result[zone] = f"{infeedp_val + gen_max_val:.3f}"
            return result

        if param == "Total capacity bioenergy":
            # CH01-CH07: biomass; CH00: CCGTresmethane, SCGTresmethane
            ch00_val = (_gen_max_for_plant(df_gen_max, "CH00_CCGTresmethane") + 
                       _gen_max_for_plant(df_gen_max, "CH00_SCGTresmethane")) / 1000.0
            result["Location independent"] = f"{ch00_val:.3f}"
            for zone in CH_ZONES:
                val = _gen_max_for_plant(df_gen_max, f"{zone}_biomass") / 1000.0
                result[zone] = f"{val:.3f}"
            return result

        if param == "Total capacity geothermal":
            return result  # empty

        if param == "Total capacity waste incineration":
            result["Location independent"] = "Grouped with other technologies in 'other'."
            return result

        if param == "Total capacity gas":
            # CH01-CH07: CCGTCCS; CH00: CCGTCCS + SCGTfossil; plus all CHP plants
            # Sum CHP plants (location independent since they span multiple regions)
            chp_plants = [p for p in df_gen["P_gen"].unique() if p.endswith("_CHPNew")] if not df_gen.empty else []
            chp_total = sum(_gen_max_for_plant(df_gen_max, p) for p in chp_plants) / 1000.0
            ch00_val = (_gen_max_for_plant(df_gen_max, "CH00_CCGTCCS") + 
                       _gen_max_for_plant(df_gen_max, "CH00_SCGTfossil") + chp_total) / 1000.0
            result["Location independent"] = f"{ch00_val:.3f}"
            for zone in CH_ZONES:
                val = _gen_max_for_plant(df_gen_max, f"{zone}_CCGTCCS") / 1000.0
                result[zone] = f"{val:.3f}"
            return result

        if param == "Total capacity nuclear":
            # CH00: CH00_nuclear; CH03: CH03_nuclear
            ch00_val = _gen_max_for_plant(df_gen_max, "CH00_nuclear") / 1000.0
            result["Location independent"] = f"{ch00_val:.3f}"
            ch03_val = _gen_max_for_plant(df_gen_max, "CH03_nuclear") / 1000.0
            result["CH03"] = f"{ch03_val:.3f}"
            return result

        if param == "Total capacity hydro dams":
            # CH00 only: medium_reservior, small_reservior, CH00_dam + large_psp, CH00_psp_close (combined)
            dam_val = (_gen_max_for_plant(df_gen_max, "medium_reservior") +
                       _gen_max_for_plant(df_gen_max, "small_reservior") +
                       _gen_max_for_plant(df_gen_max, "CH00_dam"))
            psp_val = (_gen_max_for_plant(df_gen_max, "large_psp") +
                       _gen_max_for_plant(df_gen_max, "CH00_psp_close"))
            val = (dam_val + psp_val) / 1000.0
            result["Location independent"] = f"{val:.3f}"
            return result

        if param == "Total capacity run of river":
            # CH00 only: max infeed ror
            val = _max_infeed_for_tech(df_infeed, "ror") / 1000.0
            result["Location independent"] = f"{val:.3f}"
            return result

        if param == "Total capacity pumped hydro":
            # Combined with hydro dams in FEM
            result["Location independent"] = "The capacity of hydro pumped storage and hydro dam in FEM is considered as one."
            return result

        if param == "Total capacity battery":
            # CH00: CH00_battery; CH01-CH07: zone_battery
            ch00_val = _gen_max_for_plant(df_gen_max, "CH00_battery") / 1000.0
            result["Location independent"] = f"{ch00_val:.3f}"
            for zone in CH_ZONES:
                val = _gen_max_for_plant(df_gen_max, f"{zone}_battery") / 1000.0
                result[zone] = f"{val:.3f}"
            return result

        # === ANNUAL GENERATION ===
        if param == "Annual generation solar PV - Roof":
            # CH00 (infeed): pvrf; CH01-CH07: gen per zone
            ch00_val = _sum_infeed_for_tech(df_infeed, "pvrf") / 1000.0
            result["Location independent"] = f"{ch00_val:.3f}"
            for zone in CH_ZONES:
                val = _gen_for_plant(df_gen, f"{zone}_pvrf") / 1000.0
                result[zone] = f"{val:.3f}"
            return result

        if param == "Annual generation solar PV - Agri":
            return result  # empty

        if param == "Annual generation solar PV - Alpine":
            return result  # empty

        if param == "Annual generation wind power":
            # CH00 (infeed): windon; CH01-CH07: gen per zone
            ch00_val = _sum_infeed_for_tech(df_infeed, "windon") / 1000.0
            result["Location independent"] = f"{ch00_val:.3f}"
            for zone in CH_ZONES:
                val = _gen_for_plant(df_gen, f"{zone}_windon") / 1000.0
                result[zone] = f"{val:.3f}"
            return result

        if param == "Annual generation bioenergy":
            # CH01-CH07: biomass; CH00: CCGTresmethane, SCGTresmethane
            ch00_val = (_gen_for_plant(df_gen, "CH00_CCGTresmethane") + 
                       _gen_for_plant(df_gen, "CH00_SCGTresmethane")) / 1000.0
            result["Location independent"] = f"{ch00_val:.3f}"
            for zone in CH_ZONES:
                val = _gen_for_plant(df_gen, f"{zone}_biomass") / 1000.0
                result[zone] = f"{val:.3f}"
            return result

        if param == "Annual generation geothermal":
            return result  # empty

        if param == "Annual generation waste incineration":
            result["Location independent"] = "Grouped with other technologies in 'other'."
            return result

        if param == "Annual generation gas":
            # CH01-CH07: CCGTCCS; CH00: CCGTCCS + SCGTfossil; plus all CHP plants
            # Sum CHP plants (location independent since they span multiple regions)
            chp_plants = [p for p in df_gen["P_gen"].unique() if p.endswith("_CHPNew")] if not df_gen.empty else []
            chp_total = sum(_gen_for_plant(df_gen, p) for p in chp_plants) / 1000.0
            ch00_val = (_gen_for_plant(df_gen, "CH00_CCGTCCS") + 
                       _gen_for_plant(df_gen, "CH00_SCGTfossil") + chp_total) / 1000.0
            result["Location independent"] = f"{ch00_val:.3f}"
            for zone in CH_ZONES:
                val = _gen_for_plant(df_gen, f"{zone}_CCGTCCS") / 1000.0
                result[zone] = f"{val:.3f}"
            return result

        if param == "Annual generation nuclear":
            # CH00: CH00_nuclear; CH03: CH03_nuclear
            ch00_val = _gen_for_plant(df_gen, "CH00_nuclear") / 1000.0
            result["Location independent"] = f"{ch00_val:.3f}"
            ch03_val = _gen_for_plant(df_gen, "CH03_nuclear") / 1000.0
            result["CH03"] = f"{ch03_val:.3f}"
            return result

        if param == "Annual generation hydro dam":
            # CH00 only
            val = (_gen_for_plant(df_gen, "medium_reservior") +
                   _gen_for_plant(df_gen, "small_reservior") +
                   _gen_for_plant(df_gen, "CH00_dam")) / 1000.0
            result["Location independent"] = f"{val:.3f}"
            return result

        if param == "Annual generation hydro run of river":
            # CH00 only
            val = _sum_infeed_for_tech(df_infeed, "ror") / 1000.0
            result["Location independent"] = f"{val:.3f}"
            return result

        if param == "Annual discharge pumped hydro":
            # CH00 only
            val = (_gen_for_plant(df_gen, "large_psp") +
                   _gen_for_plant(df_gen, "CH00_psp_close")) / 1000.0
            result["Location independent"] = f"{val:.3f}"
            return result

        if param == "Annual charge pumped hydro":
            # CH00 only
            val = (_storage_charge_for_plant(df_storage_charge, "large_psp") +
                   _storage_charge_for_plant(df_storage_charge, "CH00_psp_close")) / 1000.0
            result["Location independent"] = f"{val:.3f}"
            return result

        if param == "Annual battery charge":
            # CH00: CH00_battery; CH01-CH07: zone_battery
            ch00_val = _storage_charge_for_plant(df_storage_charge, "CH00_battery") / 1000.0
            result["Location independent"] = f"{ch00_val:.3f}"
            for zone in CH_ZONES:
                val = _storage_charge_for_plant(df_storage_charge, f"{zone}_battery") / 1000.0
                result[zone] = f"{val:.3f}"
            return result

        if param == "Annual battery discharge":
            # CH00: CH00_battery; CH01-CH07: zone_battery
            ch00_val = _gen_for_plant(df_gen, "CH00_battery") / 1000.0
            result["Location independent"] = f"{ch00_val:.3f}"
            for zone in CH_ZONES:
                val = _gen_for_plant(df_gen, f"{zone}_battery") / 1000.0
                result[zone] = f"{val:.3f}"
            return result

        if param == "Annual load shedding":
            val = _sum_lostload(df_lostload) / 1000.0
            result["Location independent"] = f"{val:.3f}"
            return result

        if param == "Charge pumped hydro WINTER":
            val = (_storage_charge_for_plant_season(df_storage_charge, "large_psp", "winter") +
                   _storage_charge_for_plant_season(df_storage_charge, "CH00_psp_close", "winter")) / 1000.0
            result["Location independent"] = f"{val:.3f}"
            return result

        if param == "Charge pumped hydro SUMMER":
            val = (_storage_charge_for_plant_season(df_storage_charge, "large_psp", "summer") +
                   _storage_charge_for_plant_season(df_storage_charge, "CH00_psp_close", "summer")) / 1000.0
            result["Location independent"] = f"{val:.3f}"
            return result

        if param.startswith("Curtailment"):
            return result  # empty

        if param == "Average netload WINTER":
            avg = _average_netload(df_demand, df_infeed, df_gen, df_full_ev, df_full_hp, "winter")
            result["Location independent"] = f"{avg:.3f}"
            return result

        if param == "Average netload SUMMER":
            avg = _average_netload(df_demand, df_infeed, df_gen, df_full_ev, df_full_hp, "summer")
            result["Location independent"] = f"{avg:.3f}"
            return result

        # default: return empty
        return result

    # Build output rows with Sum calculation
    rows = []
    for param, unit, spatial_res in REPORT_ROWS:
        values = calc_row(param)
        
        # Calculate Sum from numeric values only
        sum_val = 0.0
        for key in ["Location independent", "CH01", "CH02", "CH03", "CH04", "CH05", "CH06", "CH07"]:
            try:
                if values[key] and values[key] not in ["", "Grouped with other technologies in 'other'."]:
                    sum_val += float(values[key])
            except (ValueError, TypeError):
                pass
        
        sum_str = f"{sum_val:.3f}" if sum_val != 0.0 or any(values[k] for k in values) else ""

        rows.append({
            "Model": f"FEM v{model_version}",
            "Scenario Name": subscenario if subscenario is not None else scenario_name,
            "Output-Parameter": param,
            "Unit": unit,
            "Sum": sum_str,
            "Location independent": values["Location independent"],
            "CH01": values["CH01"],
            "CH02": values["CH02"],
            "CH03": values["CH03"],
            "CH04": values["CH04"],
            "CH05": values["CH05"],
            "CH06": values["CH06"],
            "CH07": values["CH07"],
        })

    out_df = pd.DataFrame(rows, columns=[
        "Model", "Scenario Name", "Output-Parameter", "Unit", "Sum",
        "Location independent", "CH01", "CH02", "CH03", "CH04", "CH05", "CH06", "CH07"
    ])
    out_path = report_dir / "Output_Spatial.csv"
    out_df.to_csv(out_path, index=False)
