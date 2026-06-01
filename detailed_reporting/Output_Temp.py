"""
Export temporal patterns in model outputs for Swiss model intercomparison.

This module provides functions to export time-resolved output data from the
energy system model, including hourly generation, load, storage operation,
cross-border flows, and prices.
"""

from pathlib import Path
from typing import List, Optional
import numpy as np
import pandas as pd

from model.version import MODEL_VERSION
from detailed_reporting.constants import (
    CHF_TO_EUR, is_winter_t, is_summer_t, get_run_year, get_weather_year,
    get_flexible_household_heatpump_share, get_eu_policy, HP_PLANTS,
    read_full_ev_demand, read_full_hp_demand, PROJECT_ROOT,
    get_subscenario_weight
)


# Cost files whose value column must be divided by the subscenario weight to
# recover the unweighted per-subscenario value (see user spec). Output_Temp
# does not currently read these, but kept in sync with the other modules.
_WEIGHT_DIVIDE_COST_FILES = {
    "cost_inv_dict.csv": "cost_CHF",
    "cost_op_dict.csv": "cost_CHF",
}


# Swiss cross-border lines
CH_LINES = ["HVAC_AT00_CH00", "HVAC_DE00_CH00", "HVAC_FR00_CH00", "HVAC_IT00_CH00"]

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

# Renewable plants for net load calculation (only PV and wind, not biomass)
GEN_RENEWABLE_PLANTS = [
    "CH01_pvrf", "CH02_pvrf", "CH03_pvrf", "CH04_pvrf", "CH05_pvrf", "CH06_pvrf", "CH07_pvrf",
    "CH01_windon", "CH02_windon", "CH03_windon", "CH04_windon", "CH05_windon", "CH06_windon", "CH07_windon",
]

# Technologies to include from infeed for net load (only PV and wind, not ror)
INFEED_VRE_TECHS = ["windon", "pvrf"]


def _parse_t_index(t: str) -> int:
    """Extract integer from time index like 't_123'."""
    if isinstance(t, str) and t.startswith("t_"):
        return int(t[2:])
    return int(t) if isinstance(t, (int, float)) else 0


def _scenario_or_test_path(scenario_name: str, filename: str) -> Path:
    """Return path to output file, falling back to test folder."""
    primary = Path("output") / scenario_name / filename
    if primary.exists():
        return primary
    fallback = Path("output") / "test" / filename
    return fallback if fallback.exists() else primary


def _read_csv(scenario_name: str, filename: str, subscenario: str = None) -> pd.DataFrame:  # type: ignore
    """Read a CSV file from the scenario output directory, optionally filtered to a subscenario."""
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


def _pyomo_to_dataframe(pyomo_obj, expected_cols: Optional[List[str]] = None) -> pd.DataFrame:
    """Convert Pyomo variable or parameter to DataFrame."""
    try:
        if pyomo_obj is None:
            return pd.DataFrame()
        
        if hasattr(pyomo_obj, 'extract_values'):
            data_dict = pyomo_obj.extract_values()
            if not data_dict:
                return pd.DataFrame()
            
            first_key = next(iter(data_dict.keys()))
            if isinstance(first_key, tuple):
                records = []
                for key, value in data_dict.items():
                    if isinstance(key, tuple):
                        row = {f"col_{i}": k for i, k in enumerate(key)}
                    else:
                        row = {"col_0": key}
                    row["value"] = value
                    records.append(row)
                df = pd.DataFrame(records)
                
                if expected_cols and len(expected_cols) == len(df.columns):
                    df.columns = expected_cols
                elif expected_cols and len(expected_cols) == len(df.columns) - 1:
                    rename_map = {f"col_{i}": expected_cols[i] for i in range(len(expected_cols))}
                    df = df.rename(columns=rename_map)
                return df
            else:
                return pd.DataFrame([{"key": k, "value": v} for k, v in data_dict.items()])
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _get_data(model, scenario_name: str, attr_name: str, csv_name: str,
              expected_cols: Optional[List[str]] = None,
              subscenario: str = None) -> pd.DataFrame:  # type: ignore
    """Get data from model attribute or CSV file."""
    if subscenario is None and model is not None and hasattr(model, attr_name):
        df = _pyomo_to_dataframe(getattr(model, attr_name), expected_cols)
        if not df.empty:
            return df
    return _read_csv(scenario_name, csv_name, subscenario=subscenario)


def _detect_hours_from_data(*dataframes: pd.DataFrame) -> List[int]:
    """
    Detect the actual hours present in the model data.
    
    Scans through provided DataFrames to find all unique T values,
    extracts hour numbers, and returns sorted list of hours.
    """
    all_hours = set()
    for df in dataframes:
        if df is not None and not df.empty and "T" in df.columns:
            for t_val in df["T"].unique():
                hour = _parse_t_index(t_val)
                if hour > 0:
                    all_hours.add(hour)
    
    if not all_hours:
        # Fallback to full year if no data found
        return list(range(1, 8761))
    
    return sorted(all_hours)


def _create_hourly_template(hours: List[int] = None) -> pd.DataFrame: # type: ignore
    """
    Create a template DataFrame with T values for specified hours.
    
    Parameters
    ----------
    hours : List[int], optional
        List of hour numbers to include. If None, uses 1-8760.
    
    Returns
    -------
    pd.DataFrame
        DataFrame with 'T' column containing t_1, t_2, etc.
    """
    if hours is None:
        hours = list(range(1, 8761))
    return pd.DataFrame({"T": [f"t_{i}" for i in hours]})


def _sum_hourly_gen_for_plants(df_gen: pd.DataFrame, plants: List[str]) -> pd.Series:
    """Sum generation hourly for specified plants."""
    if df_gen.empty:
        return pd.Series(dtype=float)
    
    filtered = df_gen[df_gen["P_gen"].isin(plants)].copy()
    if filtered.empty:
        return pd.Series(dtype=float)
    
    filtered["value"] = pd.to_numeric(filtered["value"], errors="coerce").fillna(0.0)
    return filtered.groupby("T")["value"].sum()


def _sum_hourly_infeed_for_tech(df_infeed: pd.DataFrame, techs: List[str]) -> pd.Series:
    """Sum infeed hourly for specified technologies."""
    if df_infeed.empty:
        return pd.Series(dtype=float)
    
    filtered = df_infeed[
        (df_infeed["Consumer_with_infeed"] == "CH00_fixedconsumer") &
        (df_infeed["Tech_infeed"].isin(techs))
    ].copy()
    if filtered.empty:
        return pd.Series(dtype=float)
    
    filtered["value"] = pd.to_numeric(filtered["value"], errors="coerce").fillna(0.0)
    return filtered.groupby("T")["value"].sum()


def _sum_hourly_storage_charge_for_plants(df_storage_charge: pd.DataFrame, plants: List[str]) -> pd.Series:
    """Sum storage_charge hourly for specified plants."""
    if df_storage_charge.empty:
        return pd.Series(dtype=float)
    
    pumping_col = "P_pumping" if "P_pumping" in df_storage_charge.columns else df_storage_charge.columns[0]
    filtered = df_storage_charge[df_storage_charge[pumping_col].isin(plants)].copy()
    if filtered.empty:
        return pd.Series(dtype=float)
    
    filtered["value"] = pd.to_numeric(filtered["value"], errors="coerce").fillna(0.0)
    return filtered.groupby("T")["value"].sum()


def export_output_temporal(model, scenario_name: str, model_version: str = None,  # type: ignore
                           subscenario: str = None):  # type: ignore
    """
    Export temporally-resolved model outputs to CSV.
    
    Parameters
    ----------
    model : pyomo.ConcreteModel
        The solved Pyomo model instance containing output variables.
    scenario_name : str
        Name of the scenario being analyzed.
    model_version : str, optional
        Model version string (default: MODEL_VERSION from model/version.py)
    
    Returns
    -------
    None
        Writes Output_Temp.csv to the detailed_reporting subdirectory.
    """
    if model_version is None:
        model_version = MODEL_VERSION
    
    # Create output directory
    report_dir = Path("output") / scenario_name / "detailed_reporting"
    if subscenario is not None:
        report_dir = report_dir / subscenario
    report_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    df_gen = _get_data(model, scenario_name, "gen", "gen.csv",
                       ["P_gen", "T", "Scenarios", "value"], subscenario=subscenario)
    df_infeed = _get_data(model, scenario_name, "infeed", "infeed.csv",
                          ["Consumer_with_infeed", "Tech_infeed", "T", "Scenarios", "value"], subscenario=subscenario)
    df_storage_charge = _get_data(model, scenario_name, "storage_charge", "storage_charge.csv",
                                   ["P_pumping", "T", "Scenarios", "value"], subscenario=subscenario)
    df_export = _get_data(model, scenario_name, "Export", "Export.csv",
                          ["lineATC", "T", "Scenarios", "value"], subscenario=subscenario)
    df_dual = _get_data(model, scenario_name, "energy_balance_dual", "energy_balance_dual.csv",
                        ["Node", "T", "Scenarios", "value"], subscenario=subscenario)
    df_curtailment = _get_data(model, scenario_name, "curtailment", "curtailment.csv",
                               ["Consumer_with_infeed", "T", "Scenarios", "value"], subscenario=subscenario)
    df_lostload = _get_data(model, scenario_name, "lostload", "lostload.csv",
                            ["Consumer", "T", "lostLoad_step", "Scenarios", "value"], subscenario=subscenario)
    df_demand = _get_data(model, scenario_name, "demand", "demand.csv",
                          ["Consumer", "Consumption_types_inflex", "T", "Scenarios", "value"], subscenario=subscenario)
    df_ev_inflexible = _get_data(model, scenario_name, "EV_inflexible_demand", "EV_inflexible_demand.csv",
                                  ["Node", "T", "Scenarios", "value"], subscenario=subscenario)
    df_hp_inflexible = _get_data(model, scenario_name, "HP_inflexible_demand", "HP_inflexible_demand.csv",
                                  ["Node", "T", "Scenarios", "value"], subscenario=subscenario)
    df_ba_th_con = _read_csv(scenario_name, "BA_th_con.csv", subscenario=subscenario)
    df_cop = _read_csv(scenario_name, "COP.csv", subscenario=subscenario)

    # Get settings
    run_year = get_run_year(scenario_name, subscenario)
    flex_hp_share = get_flexible_household_heatpump_share(scenario_name, subscenario)
    eu_policy = get_eu_policy(scenario_name, subscenario)
    
    # Use hardcoded HP plants from constants
    hp_plants = HP_PLANTS
    
    # Detect actual hours from model data
    actual_hours = _detect_hours_from_data(
        df_gen, df_infeed, df_storage_charge, df_export, df_dual,
        df_curtailment, df_lostload, df_demand, df_ev_inflexible, df_hp_inflexible
    )
    
    # Create template with actual hours only
    template = _create_hourly_template(actual_hours)
    
    # ========== HOURLY GENERATION ==========
    
    # Solar PV - Rooftop: gen + infeed
    pv_gen = _sum_hourly_gen_for_plants(df_gen, [f"CH0{i}_pvrf" for i in range(1, 8)])
    pv_infeed = _sum_hourly_infeed_for_tech(df_infeed, ["pv", "pvrf"])
    hourly_pv_roof = (pv_gen.add(pv_infeed, fill_value=0) / 1000.0).reindex(template["T"]).fillna(0.0)
    
    # Wind: gen + infeed
    wind_gen = _sum_hourly_gen_for_plants(df_gen, [f"CH0{i}_windon" for i in range(1, 8)])
    wind_infeed = _sum_hourly_infeed_for_tech(df_infeed, ["windon"])
    hourly_wind = (wind_gen.add(wind_infeed, fill_value=0) / 1000.0).reindex(template["T"]).fillna(0.0)
    
    # Bioenergy
    bio_gen = _sum_hourly_gen_for_plants(df_gen, [f"CH0{i}_biomass" for i in range(1, 8)])
    hourly_bio = (bio_gen / 1000.0).reindex(template["T"]).fillna(0.0)
    
    # Gas: CCGTCCS + SCGTfossil + CHP plants
    gas_plants = [f"CH0{i}_CCGTCCS" for i in range(8)] + ["CH00_SCGTfossil"]
    # Add CHP plants (DH, ILLT, ILHT regions)
    chp_plants = [p for p in df_gen["P_gen"].unique() if p.endswith("_CHPNew")] if not df_gen.empty else []
    gas_plants = gas_plants + chp_plants
    gas_gen = _sum_hourly_gen_for_plants(df_gen, gas_plants)
    hourly_gas = (gas_gen / 1000.0).reindex(template["T"]).fillna(0.0)
    
    # Nuclear
    nuclear_gen = _sum_hourly_gen_for_plants(df_gen, ["CH00_nuclear", "CH03_nuclear"])
    hourly_nuclear = (nuclear_gen / 1000.0).reindex(template["T"]).fillna(0.0)
    
    # Hydro dam: medium_reservior + small_reservior + CH00_dam + large_psp + CH00_psp_close (combined)
    dam_plants = ["medium_reservior", "small_reservior", "CH00_dam"]
    psp_plants = ["large_psp", "CH00_psp_close"]
    dam_gen = _sum_hourly_gen_for_plants(df_gen, dam_plants)
    psp_gen = _sum_hourly_gen_for_plants(df_gen, psp_plants)
    # Combined: dam + psp
    combined_hydro_gen = dam_gen.add(psp_gen, fill_value=0)
    hourly_hydro_dam = (combined_hydro_gen / 1000.0).reindex(template["T"]).fillna(0.0)
    
    # Hydro run of river: infeed ror
    ror_infeed = _sum_hourly_infeed_for_tech(df_infeed, ["ror"])
    hourly_hydro_ror = (ror_infeed / 1000.0).reindex(template["T"]).fillna(0.0)
    
    # Hydro pumped storage demand (charge)
    psp_charge = _sum_hourly_storage_charge_for_plants(df_storage_charge, psp_plants)
    hourly_hydro_psp_demand = (psp_charge / 1000.0).reindex(template["T"]).fillna(0.0)
    
    # Battery generation and charge
    battery_plants = [f"CH0{i}_battery" for i in range(8)]
    battery_gen = _sum_hourly_gen_for_plants(df_gen, battery_plants)
    hourly_battery_gen = (battery_gen / 1000.0).reindex(template["T"]).fillna(0.0)
    
    battery_charge = _sum_hourly_storage_charge_for_plants(df_storage_charge, battery_plants)
    hourly_battery_charge = (battery_charge / 1000.0).reindex(template["T"]).fillna(0.0)
    
    # ========== EV DSM ==========

    def calc_ev_dsm_hourly(df_storage_charge: pd.DataFrame, df_ev_inflexible: pd.DataFrame,
                           df_gen: pd.DataFrame, run_year: int) -> pd.DataFrame:
        """Calculate hourly EV DSM (actual - baseline) including V2G.
        
        DSM = actual - baseline
        where actual = flex_charge + inflex_demand + V2G_charge - V2G_feedin
        """
        result = template.copy()
        result["ev_dsm"] = 0.0
        
        # Load baseline EV demand
        baseline_path = Path("input") / "demand" / f"EV_demand_hourly_{run_year}.csv"
        if not baseline_path.exists():
            return result
        
        try:
            df_baseline = pd.read_csv(baseline_path)
            if 't' in df_baseline.columns:
                df_baseline['T'] = df_baseline['t'].apply(lambda x: f"t_{x}" if not str(x).startswith('t_') else str(x))
            baseline_col = [c for c in df_baseline.columns if 'demand' in c.lower() or 'MWh' in c][0]
        except Exception:
            return result
        
        # Get flexible EV charging
        ev_flex_charge = df_storage_charge[
            df_storage_charge["P_pumping"].isin(["CH00_EV_flex", "EV_CH"])
        ].copy() if not df_storage_charge.empty else pd.DataFrame()
        
        if ev_flex_charge.empty:
            return result
        
        ev_flex_charge["value"] = pd.to_numeric(ev_flex_charge["value"], errors="coerce").fillna(0.0)
        ev_flex_hourly = ev_flex_charge.groupby("T")["value"].mean().reset_index()
        ev_flex_hourly.columns = ["T", "flex_charge"]
        
        # Get inflexible EV demand for CH00
        if not df_ev_inflexible.empty:
            df_ev_inflex_filtered = df_ev_inflexible[df_ev_inflexible["Node"] == "CH00"].copy()
            if not df_ev_inflex_filtered.empty:
                ev_inflex_hourly = df_ev_inflex_filtered[["T", "value"]].copy()
                ev_inflex_hourly.columns = ["T", "inflex_demand"]
            else:
                ev_inflex_hourly = pd.DataFrame(columns=["T", "inflex_demand"])
        else:
            ev_inflex_hourly = pd.DataFrame(columns=["T", "inflex_demand"])
        
        # Get V2G charging (storage_charge where P_pumping == V2G_CH)
        v2g_charge = df_storage_charge[
            df_storage_charge["P_pumping"] == "V2G_CH"
        ].copy() if not df_storage_charge.empty else pd.DataFrame()
        
        if not v2g_charge.empty:
            v2g_charge["value"] = pd.to_numeric(v2g_charge["value"], errors="coerce").fillna(0.0)
            v2g_charge_hourly = v2g_charge.groupby("T")["value"].sum().reset_index()
            v2g_charge_hourly.columns = ["T", "v2g_charge"]
        else:
            v2g_charge_hourly = pd.DataFrame(columns=["T", "v2g_charge"])
        
        # Get V2G feed-in (gen where P_gen == V2G_CH)
        v2g_feedin = df_gen[
            df_gen["P_gen"] == "V2G_CH"
        ].copy() if not df_gen.empty else pd.DataFrame()
        
        if not v2g_feedin.empty:
            v2g_feedin["value"] = pd.to_numeric(v2g_feedin["value"], errors="coerce").fillna(0.0)
            v2g_feedin_hourly = v2g_feedin.groupby("T")["value"].sum().reset_index()
            v2g_feedin_hourly.columns = ["T", "v2g_feedin"]
        else:
            v2g_feedin_hourly = pd.DataFrame(columns=["T", "v2g_feedin"])
        
        # Merge all components
        merged = pd.merge(df_baseline[["T", baseline_col]], ev_flex_hourly, on="T", how="left")
        merged = pd.merge(merged, ev_inflex_hourly, on="T", how="left")
        merged = pd.merge(merged, v2g_charge_hourly, on="T", how="left")
        merged = pd.merge(merged, v2g_feedin_hourly, on="T", how="left")
        merged["flex_charge"] = merged["flex_charge"].fillna(0.0)
        merged["inflex_demand"] = merged["inflex_demand"].fillna(0.0)
        merged["v2g_charge"] = merged["v2g_charge"].fillna(0.0)
        merged["v2g_feedin"] = merged["v2g_feedin"].fillna(0.0)
        merged["baseline"] = merged[baseline_col]
        # actual = flex_charge + inflex_demand + V2G_charge - V2G_feedin
        merged["actual"] = merged["flex_charge"] + merged["inflex_demand"] + merged["v2g_charge"] - merged["v2g_feedin"]
        merged["dsm"] = merged["actual"] - merged["baseline"]
        
        result = pd.merge(template, merged[["T", "dsm"]], on="T", how="left")
        result["dsm"] = result["dsm"].fillna(0.0)
        return result[["T", "dsm"]]
    
    ev_dsm_df = calc_ev_dsm_hourly(df_storage_charge, df_ev_inflexible, df_gen, run_year)
    hourly_ev_dsm_up = (ev_dsm_df["dsm"].clip(lower=0) / 1000.0).values  # Positive = DSM up
    hourly_ev_dsm_down = (ev_dsm_df["dsm"].clip(upper=0).abs() / 1000.0).values  # Negative = DSM down (abs)
    
    # ========== HP DSM ==========
    
    def calc_hp_dsm_hourly(df_storage_charge: pd.DataFrame, df_ba_th_con: pd.DataFrame,
                           df_cop: pd.DataFrame, hp_plants: List[str], flex_hp_share: float) -> pd.DataFrame:
        """Calculate hourly HP DSM (actual - baseline) in electric units."""
        result = template.copy()
        result["dsm"] = 0.0
        
        if df_storage_charge.empty or df_ba_th_con.empty or df_cop.empty:
            return result[["T", "dsm"]]
        
        # Get flexible HP charging
        hp_flex_charge = df_storage_charge[df_storage_charge["P_pumping"].isin(hp_plants)].copy()
        if hp_flex_charge.empty:
            return result[["T", "dsm"]]
        
        hp_flex_charge["value"] = pd.to_numeric(hp_flex_charge["value"], errors="coerce").fillna(0.0)
        
        # Prepare BA_th_con and COP
        df_ba = df_ba_th_con.copy()
        df_ba["value"] = pd.to_numeric(df_ba["value"], errors="coerce").fillna(0.0)
        
        df_c = df_cop.copy()
        df_c["value"] = pd.to_numeric(df_c["value"], errors="coerce").fillna(1.0)
        
        # Merge to convert thermal to electric
        ba_col = "BA_names" if "BA_names" in df_ba.columns else df_ba.columns[1]
        merged_ba_cop = pd.merge(df_ba, df_c, on=["T", ba_col, "Scenarios"], how="left", suffixes=("_th", "_cop"))
        merged_ba_cop["value_cop"] = merged_ba_cop["value_cop"].fillna(1.0).clip(lower=0.1)
        merged_ba_cop["elec_demand"] = merged_ba_cop["value_th"] / merged_ba_cop["value_cop"]
        
        # Baseline = sum of electric demand per hour
        baseline_hourly = merged_ba_cop.groupby("T")["elec_demand"].sum().reset_index()
        baseline_hourly.columns = ["T", "baseline_el"]
        
        # Inflexible portion
        baseline_hourly["inflex_el"] = baseline_hourly["baseline_el"] * flex_hp_share
        
        # Average COP per hour for converting storage_charge
        avg_cop_hourly = merged_ba_cop.groupby("T")["value_cop"].mean().reset_index()
        avg_cop_hourly.columns = ["T", "avg_cop"]
        
        hp_flex_with_cop = pd.merge(hp_flex_charge, avg_cop_hourly, on="T", how="left")
        hp_flex_with_cop["avg_cop"] = hp_flex_with_cop["avg_cop"].fillna(1.0).clip(lower=0.1)
        hp_flex_with_cop["elec_charge"] = hp_flex_with_cop["value"] / hp_flex_with_cop["avg_cop"]
        
        hp_flex_hourly = hp_flex_with_cop.groupby("T")["elec_charge"].sum().reset_index()
        hp_flex_hourly.columns = ["T", "flex_charge_el"]
        
        # Merge
        merged = pd.merge(baseline_hourly, hp_flex_hourly, on="T", how="left")
        merged["flex_charge_el"] = merged["flex_charge_el"].fillna(0.0)
        merged["actual_el"] = merged["flex_charge_el"] + merged["inflex_el"]
        merged["dsm"] = merged["actual_el"] - merged["baseline_el"]
        
        result = pd.merge(template, merged[["T", "dsm"]], on="T", how="left")
        result["dsm"] = result["dsm"].fillna(0.0)
        return result[["T", "dsm"]]
    
    hp_dsm_df = calc_hp_dsm_hourly(df_storage_charge, df_ba_th_con, df_cop, hp_plants, flex_hp_share)
    hourly_hp_dsm_up = (hp_dsm_df["dsm"].clip(lower=0) / 1000.0).values
    hourly_hp_dsm_down = (hp_dsm_df["dsm"].clip(upper=0).abs() / 1000.0).values
    
    # ========== CURTAILMENT ==========
    
    def calc_curtailment_ch_hourly(df_curtailment: pd.DataFrame, df_dual: pd.DataFrame,
                                    df_export: pd.DataFrame) -> pd.Series:
        """Calculate hourly actual curtailment in Switzerland."""
        if df_curtailment.empty:
            return pd.Series(0.0, index=template["T"])
        
        ch_curt = df_curtailment[df_curtailment["Consumer_with_infeed"] == "CH00_fixedconsumer"].copy()
        ch_curt["value"] = pd.to_numeric(ch_curt["value"], errors="coerce").fillna(0.0)
        
        if ch_curt.empty:
            return pd.Series(0.0, index=template["T"])
        
        # Get hours where CH price is near zero
        if not df_dual.empty:
            ch_prices = df_dual[df_dual["Node"] == "CH00"].copy()
            ch_prices["value"] = pd.to_numeric(ch_prices["value"], errors="coerce").fillna(0.0)
            zero_price_hours = ch_prices[ch_prices["value"] < 0.01][["T", "Scenarios"]].drop_duplicates()
            
            if not zero_price_hours.empty and not df_export.empty:
                ch_export = df_export[df_export["lineATC"].isin(CH_LINES)].copy()
                ch_export["value"] = pd.to_numeric(ch_export["value"], errors="coerce").fillna(0.0)
                
                # Net export per T, Scenarios
                net_export = ch_export.groupby(["T", "Scenarios"])["value"].sum().reset_index()
                net_export["net_export"] = -net_export["value"]  # Make exports positive
                
                # Merge with curtailment for zero-price hours
                merged = pd.merge(ch_curt, zero_price_hours, on=["T", "Scenarios"], how="inner")
                merged = pd.merge(merged, net_export[["T", "Scenarios", "net_export"]],
                                 on=["T", "Scenarios"], how="left")
                merged["net_export"] = merged["net_export"].fillna(0.0)
                merged["actual_curt"] = (merged["value"] - merged["net_export"]).clip(lower=0)
                
                # Non-zero price hours
                non_zero = ch_curt[~ch_curt.set_index(["T", "Scenarios"]).index.isin(
                    zero_price_hours.set_index(["T", "Scenarios"]).index)].copy()
                non_zero["actual_curt"] = non_zero["value"]
                
                # Combine and sum by T
                combined = pd.concat([merged[["T", "actual_curt"]], non_zero[["T", "actual_curt"]]])
                hourly = combined.groupby("T")["actual_curt"].sum()
                return hourly.reindex(template["T"]).fillna(0.0)
        
        # Fallback: just sum reported curtailment
        hourly = ch_curt.groupby("T")["value"].sum()
        return hourly.reindex(template["T"]).fillna(0.0)
    
    hourly_curt_ch = (calc_curtailment_ch_hourly(df_curtailment, df_dual, df_export) / 1000.0).values
    
    # Curtailment abroad
    if not df_curtailment.empty:
        total_curt = df_curtailment.copy()
        total_curt["value"] = pd.to_numeric(total_curt["value"], errors="coerce").fillna(0.0)
        total_hourly = total_curt.groupby("T")["value"].sum().reindex(template["T"]).fillna(0.0)
        ch_curt_hourly = calc_curtailment_ch_hourly(df_curtailment, df_dual, df_export)
        abroad_hourly = (total_hourly - ch_curt_hourly).clip(lower=0) / 1000.0
    else:
        abroad_hourly = pd.Series(0.0, index=template["T"])
    hourly_curt_abroad = abroad_hourly.values
    
    # ========== LOAD SHEDDING ==========
    
    if not df_lostload.empty:
        ch_ll = df_lostload[df_lostload["Consumer"] == "CH00_fixedconsumer"].copy()
        ch_ll["value"] = pd.to_numeric(ch_ll["value"], errors="coerce").fillna(0.0)
        ll_hourly = ch_ll.groupby("T")["value"].sum().reindex(template["T"]).fillna(0.0) / 1000.0
    else:
        ll_hourly = pd.Series(0.0, index=template["T"])
    hourly_load_shedded = ll_hourly.values
    
    # ========== CROSS-BORDER EXCHANGE ==========
    
    def get_exchange_hourly(df_export: pd.DataFrame, line: str, direction: str) -> pd.Series:
        """Get hourly exchange for a specific line and direction."""
        if df_export.empty:
            return pd.Series(0.0, index=template["T"])
        
        line_data = df_export[df_export["lineATC"] == line].copy()
        if line_data.empty:
            return pd.Series(0.0, index=template["T"])
        
        line_data["value"] = pd.to_numeric(line_data["value"], errors="coerce").fillna(0.0)
        hourly = line_data.groupby("T")["value"].sum()
        
        if direction == "export_from_ch":
            # Export from CH = negative values, make positive
            result = hourly.clip(upper=0).abs()
        else:  # import_to_ch
            # Import to CH = positive values
            result = hourly.clip(lower=0)
        
        return result.reindex(template["T"]).fillna(0.0) / 1000.0
    
    # CH-DE exchange
    hourly_ch_de = get_exchange_hourly(df_export, "HVAC_DE00_CH00", "export_from_ch")
    hourly_de_ch = get_exchange_hourly(df_export, "HVAC_DE00_CH00", "import_to_ch")
    
    # CH-FR exchange
    hourly_ch_fr = get_exchange_hourly(df_export, "HVAC_FR00_CH00", "export_from_ch")
    hourly_fr_ch = get_exchange_hourly(df_export, "HVAC_FR00_CH00", "import_to_ch")
    
    # CH-IT exchange
    hourly_ch_it = get_exchange_hourly(df_export, "HVAC_IT00_CH00", "export_from_ch")
    hourly_it_ch = get_exchange_hourly(df_export, "HVAC_IT00_CH00", "import_to_ch")
    
    # CH-AT exchange
    hourly_ch_at = get_exchange_hourly(df_export, "HVAC_AT00_CH00", "export_from_ch")
    hourly_at_ch = get_exchange_hourly(df_export, "HVAC_AT00_CH00", "import_to_ch")
    
    # Totals
    hourly_import_total = hourly_de_ch + hourly_fr_ch + hourly_it_ch + hourly_at_ch
    hourly_export_total = hourly_ch_de + hourly_ch_fr + hourly_ch_it + hourly_ch_at
    hourly_net_import = hourly_import_total - hourly_export_total
    
    # ========== NET LOAD ==========
    
    # Read full EV and HP demand from source files (100%, before flexibility splitting)
    weather_year = get_weather_year(scenario_name, subscenario)
    df_full_ev = read_full_ev_demand(run_year)
    df_full_hp = read_full_hp_demand(run_year, weather_year)
    
    def calc_netload_hourly(df_demand: pd.DataFrame, df_infeed: pd.DataFrame,
                            df_gen: pd.DataFrame, df_full_ev: pd.DataFrame,
                            df_full_hp: pd.DataFrame) -> pd.Series:
        """Calculate hourly net load = (base demand + full EV + full HP) - VRE generation.
        
        Net load represents the underlying demand minus VRE generation, before any 
        flexibility/shifting/storage is applied.
        
        Components:
        - Base demand from model.demand (CH00_fixedconsumer) - already has BA_el_con subtracted
        - Full EV demand (100% of EV consumption)
        - Full HP demand (100% of household HP consumption) - added back since subtracted from base
        - Given renewables (infeed: wind + PV only)
        - Added renewables (endogenously invested: wind + PV only)
        """
        
        # Base demand for CH00 from model.demand (already has BA_el_con subtracted)
        ch_demand = df_demand[df_demand["Consumer"] == "CH00_fixedconsumer"].copy()
        ch_demand["_value"] = pd.to_numeric(ch_demand["value"], errors="coerce").fillna(0.0)
        d = ch_demand.groupby("T")["_value"].sum()
        
        # Given renewables from infeed (only wind and PV, not ror)
        ch_infeed = df_infeed[
            (df_infeed["Consumer_with_infeed"] == "CH00_fixedconsumer") &
            (df_infeed["Tech_infeed"].isin(INFEED_VRE_TECHS))
        ].copy()
        val_col = ch_infeed["value"]
        ch_infeed["_value"] = pd.to_numeric(val_col, errors="coerce").fillna(0.0)
        i = ch_infeed.groupby("T")["_value"].sum()
        
        # Added renewables from gen
        added_ren = df_gen[df_gen["P_gen"].isin(GEN_RENEWABLE_PLANTS)].copy()
        val_col = added_ren["value"]
        added_ren["_value"] = pd.to_numeric(val_col, errors="coerce").fillna(0.0)
        added_r = added_ren.groupby("T")["_value"].sum()
        
        # Full EV demand (100% of EV consumption) - filter to actual hours
        df_ev_filtered = df_full_ev[df_full_ev["T"].isin(template["T"])].copy()
        ev_series = df_ev_filtered.set_index("T")["value"]
        ev_d = pd.to_numeric(ev_series, errors="coerce").fillna(0.0)
        
        # Full HP demand (100% of household HP consumption) - filter to actual hours
        df_hp_filtered = df_full_hp[df_full_hp["T"].isin(template["T"])].copy()
        hp_series = df_hp_filtered.set_index("T")["value"]
        hp_d = pd.to_numeric(hp_series, errors="coerce").fillna(0.0)
        
        # Net load = (base demand + full EV + full HP) - VRE generation (infeed + added_ren)
        total_demand = d.add(ev_d, fill_value=0).add(hp_d, fill_value=0)
        total_vre = i.add(added_r, fill_value=0)
        netload = total_demand - total_vre
        return netload.reindex(template["T"]).fillna(0.0) / 1000.0  # to GWh
    
    hourly_netload = calc_netload_hourly(df_demand, df_infeed, df_gen, df_full_ev, df_full_hp)
    
    # ========== PRICES ==========
    
    def get_hourly_prices(df_dual: pd.DataFrame, node: str) -> pd.Series:
        """Get hourly prices for a node, converted to EUR."""
        if df_dual.empty:
            return pd.Series(0.0, index=template["T"])
        
        node_prices = df_dual[df_dual["Node"] == node].copy()
        if node_prices.empty:
            return pd.Series(0.0, index=template["T"])
        
        node_prices["value"] = pd.to_numeric(node_prices["value"], errors="coerce").fillna(0.0)
        hourly = node_prices.groupby("T")["value"].mean()  # Mean across scenarios
        return (hourly * CHF_TO_EUR).reindex(template["T"]).fillna(0.0)
    
    hourly_price_ch = get_hourly_prices(df_dual, "CH00")
    hourly_price_de = get_hourly_prices(df_dual, "DE00")
    hourly_price_fr = get_hourly_prices(df_dual, "FR00")
    hourly_price_it = get_hourly_prices(df_dual, "IT00")
    hourly_price_at = get_hourly_prices(df_dual, "AT00")
    
    # ========== CONSUMER COSTS AND GENERATOR REVENUES ==========
    
    def calc_consumer_costs_hourly(df_demand: pd.DataFrame, df_storage_charge: pd.DataFrame,
                                    df_ev_inflexible: pd.DataFrame, df_hp_inflexible: pd.DataFrame,
                                    hourly_price: pd.Series) -> pd.Series:
        """
        Calculate hourly costs for consumers in EUR.
        
        Consumer cost = price × (base demand + inflexible EV + inflexible HP + flexible demand)
        
        - Base demand: model.demand for CH00_fixedconsumer
        - Inflexible EV: EV_inflexible_demand for CH00
        - Inflexible HP: HP_inflexible_demand for CH00
        - Flexible demand: storage_charge for consumption plants (EV, HP, electrolyzer)
          but NOT battery/PSP (those are arbitrage, not final consumption)
        
        Returns hourly costs in EUR (price in EUR/MWh × consumption in MWh).
        """
        # Base demand for CH00
        if not df_demand.empty:
            ch_demand = df_demand[df_demand["Consumer"] == "CH00_fixedconsumer"].copy()
            ch_demand["value"] = pd.to_numeric(ch_demand["value"], errors="coerce").fillna(0.0)
            base_demand = ch_demand.groupby("T")["value"].sum()
        else:
            base_demand = pd.Series(0.0, index=template["T"])
        
        # Inflexible EV demand for CH00
        if not df_ev_inflexible.empty:
            ev_inflex = df_ev_inflexible[df_ev_inflexible["Node"] == "CH00"].copy()
            ev_inflex["value"] = pd.to_numeric(ev_inflex["value"], errors="coerce").fillna(0.0)
            ev_inflex_hourly = ev_inflex.groupby("T")["value"].sum()
        else:
            ev_inflex_hourly = pd.Series(0.0, index=template["T"])
        
        # Inflexible HP demand for CH00
        if not df_hp_inflexible.empty:
            hp_inflex = df_hp_inflexible[df_hp_inflexible["Node"] == "CH00"].copy()
            hp_inflex["value"] = pd.to_numeric(hp_inflex["value"], errors="coerce").fillna(0.0)
            hp_inflex_hourly = hp_inflex.groupby("T")["value"].sum()
        else:
            hp_inflex_hourly = pd.Series(0.0, index=template["T"])
        
        # Flexible demand from storage_charge (only demand-type plants, not arbitrage)
        if not df_storage_charge.empty:
            pumping_col = "P_pumping" if "P_pumping" in df_storage_charge.columns else df_storage_charge.columns[0]
            flex_demand = df_storage_charge[
                df_storage_charge[pumping_col].isin(STORAGE_CHARGE_DEMAND_PLANTS)
            ].copy()
            flex_demand["value"] = pd.to_numeric(flex_demand["value"], errors="coerce").fillna(0.0)
            flex_demand_hourly = flex_demand.groupby("T")["value"].sum()
        else:
            flex_demand_hourly = pd.Series(0.0, index=template["T"])
        
        # Total consumption = base + inflexible EV + inflexible HP + flexible
        total_consumption = (base_demand
                            .add(ev_inflex_hourly, fill_value=0)
                            .add(hp_inflex_hourly, fill_value=0)
                            .add(flex_demand_hourly, fill_value=0))
        total_consumption = total_consumption.reindex(template["T"]).fillna(0.0)
        
        # Cost = price × consumption (both already aligned to template["T"])
        hourly_cost = hourly_price * total_consumption
        return hourly_cost.fillna(0.0)
    
    def calc_generator_revenues_hourly(df_gen: pd.DataFrame, df_infeed: pd.DataFrame,
                                        hourly_price: pd.Series) -> pd.Series:
        """
        Calculate hourly revenues for generators in EUR.
        
        Generator revenue = price × (dispatchable generation + infeed)
        
        - Dispatchable gen: all Swiss generators (CH*, DH_*, ILHT_*, ILLT_*, hydro, V2G)
        - Infeed: given renewables and RoR at CH00
        
        Returns hourly revenues in EUR (price in EUR/MWh × generation in MWh).
        """
        # Swiss generator patterns - all plants that generate electricity in Switzerland
        swiss_gen_prefixes = ("CH", "DH_", "ILHT_", "ILLT_")
        swiss_gen_names = {"large_psp", "medium_reservior", "small_reservior", "V2G_CH"}
        
        def is_swiss_generator(plant_name: str) -> bool:
            """Check if plant is a Swiss generator."""
            if plant_name.startswith(swiss_gen_prefixes):
                return True
            if plant_name in swiss_gen_names:
                return True
            return False
        
        # Dispatchable generation from Swiss plants
        if not df_gen.empty:
            ch_gen = df_gen[df_gen["P_gen"].apply(is_swiss_generator)].copy()
            ch_gen["value"] = pd.to_numeric(ch_gen["value"], errors="coerce").fillna(0.0)
            dispatchable_gen = ch_gen.groupby("T")["value"].sum()
        else:
            dispatchable_gen = pd.Series(0.0, index=template["T"])
        
        # Infeed (given renewables and RoR) at CH00
        if not df_infeed.empty:
            ch_infeed = df_infeed[df_infeed["Consumer_with_infeed"] == "CH00_fixedconsumer"].copy()
            ch_infeed["value"] = pd.to_numeric(ch_infeed["value"], errors="coerce").fillna(0.0)
            infeed_total = ch_infeed.groupby("T")["value"].sum()
        else:
            infeed_total = pd.Series(0.0, index=template["T"])
        
        # Total generation
        total_gen = dispatchable_gen.add(infeed_total, fill_value=0)
        total_gen = total_gen.reindex(template["T"]).fillna(0.0)
        
        # Revenue = price × generation
        hourly_revenue = hourly_price * total_gen
        return hourly_revenue.fillna(0.0)
    
    def calc_generator_revenues_with_trade(df_gen: pd.DataFrame, df_infeed: pd.DataFrame,
                                            hourly_price_ch: pd.Series,
                                            hourly_exports: dict, hourly_prices: dict) -> pd.Series:
        """
        Calculate hourly revenues for generators with accurate export valuation.
        
        Generator revenue = domestic_sales × CH_price + exports × foreign_prices
        
        Exports are valued at the destination country's price, not the Swiss price.
        This gives a more accurate picture of the value generators capture.
        
        Returns hourly revenues in EUR.
        """
        # Swiss generator patterns
        swiss_gen_prefixes = ("CH", "DH_", "ILHT_", "ILLT_")
        swiss_gen_names = {"large_psp", "medium_reservior", "small_reservior", "V2G_CH"}
        
        def is_swiss_generator(plant_name: str) -> bool:
            if plant_name.startswith(swiss_gen_prefixes):
                return True
            return plant_name in swiss_gen_names
        
        # Total Swiss generation
        if not df_gen.empty:
            ch_gen = df_gen[df_gen["P_gen"].apply(is_swiss_generator)].copy()
            ch_gen["value"] = pd.to_numeric(ch_gen["value"], errors="coerce").fillna(0.0)
            dispatchable_gen = ch_gen.groupby("T")["value"].sum()
        else:
            dispatchable_gen = pd.Series(0.0, index=template["T"])
        
        if not df_infeed.empty:
            ch_infeed = df_infeed[df_infeed["Consumer_with_infeed"] == "CH00_fixedconsumer"].copy()
            ch_infeed["value"] = pd.to_numeric(ch_infeed["value"], errors="coerce").fillna(0.0)
            infeed_total = ch_infeed.groupby("T")["value"].sum()
        else:
            infeed_total = pd.Series(0.0, index=template["T"])
        
        total_gen = dispatchable_gen.add(infeed_total, fill_value=0).reindex(template["T"]).fillna(0.0)
        
        # Total exports (in GWh, need to convert back to MWh for price calculation)
        total_exports = (hourly_exports["DE"] + hourly_exports["FR"] + 
                        hourly_exports["IT"] + hourly_exports["AT"])  # Already in GWh
        
        # Domestic sales = generation - exports (convert exports GWh → MWh)
        domestic_sales = total_gen - (total_exports * 1000)  # MWh
        domestic_sales = domestic_sales.clip(lower=0)  # Can't be negative
        
        # Revenue from domestic sales at CH price
        domestic_revenue = domestic_sales * hourly_price_ch
        
        # Revenue from exports at destination prices (exports in GWh, prices in EUR/MWh)
        export_revenue_de = (hourly_exports["DE"] * 1000) * hourly_prices["DE"]  # GWh→MWh × price
        export_revenue_fr = (hourly_exports["FR"] * 1000) * hourly_prices["FR"]
        export_revenue_it = (hourly_exports["IT"] * 1000) * hourly_prices["IT"]
        export_revenue_at = (hourly_exports["AT"] * 1000) * hourly_prices["AT"]
        
        total_export_revenue = export_revenue_de + export_revenue_fr + export_revenue_it + export_revenue_at
        
        # Total revenue
        hourly_revenue = domestic_revenue + total_export_revenue
        return hourly_revenue.fillna(0.0)
    
    # Prepare exports and prices for the trade-aware calculation
    hourly_exports = {
        "DE": hourly_ch_de,  # Already in GWh
        "FR": hourly_ch_fr,
        "IT": hourly_ch_it,
        "AT": hourly_ch_at,
    }
    hourly_prices = {
        "DE": hourly_price_de,
        "FR": hourly_price_fr,
        "IT": hourly_price_it,
        "AT": hourly_price_at,
    }
    
    hourly_consumer_costs = calc_consumer_costs_hourly(
        df_demand, df_storage_charge, df_ev_inflexible, df_hp_inflexible, hourly_price_ch
    )
    # Generators receive CH price for all generation (congestion rents go to TSOs, not generators)
    hourly_generator_revenues = calc_generator_revenues_hourly(
        df_gen, df_infeed, hourly_price_ch
    )
    
    # ========== LINE LOADING ==========
    
    def calc_line_loading_hourly(df_export: pd.DataFrame, scenario_name: str,
                                  run_year: int, eu_policy: str) -> pd.Series:
        """
        Calculate average hourly line loading for interconnectors.
        
        For each hour, determines the utilization of each CH cross-border line
        based on the flow direction and the corresponding NTC limits.
        
        Process:
        1. Get hourly flows from model.Export for each CH interconnector
        2. Load NTC import/export limits based on eu_policy (GA or DE)
        3. For each hour and line:
           - If flow > 0: import direction, utilization = flow / import_limit
           - If flow < 0: export direction, utilization = abs(flow) / export_limit
        4. Average utilization across all 4 lines for each hour
        
        Returns hourly average utilization as percentage (0-100).
        """
        
        # Determine NTC file suffix based on eu_policy
        policy_suffix = "GlobalAmbition" if eu_policy == "GA" else "DistributedEnergy"
        
        # Load NTC limits
        ntc_import_path = PROJECT_ROOT / "input" / "NTC" / f"NTC_import_{policy_suffix}_2050.csv"
        ntc_export_path = PROJECT_ROOT / "input" / "NTC" / f"NTC_export_{policy_suffix}_2050.csv"
        
        if not ntc_import_path.exists() or not ntc_export_path.exists():
            return pd.Series(0.0, index=template["T"])
        
        df_ntc_import = pd.read_csv(ntc_import_path)
        df_ntc_export = pd.read_csv(ntc_export_path)
        
        # CSV structure: index column has "XX00-YY00" format, value in "Export Capacity (MW)" or "Import Capacity (MW)"
        # Convert HVAC_XX00_YY00 to XX00-YY00 format for lookup
        def line_to_csv_key(line: str) -> str:
            """Convert HVAC_AT00_CH00 to AT00-CH00 format."""
            parts = line.replace("HVAC_", "").split("_")
            if len(parts) == 2:
                return f"{parts[0]}-{parts[1]}"
            return line
        
        # Find the capacity column name
        import_cap_col = [c for c in df_ntc_import.columns if "Capacity" in c][0] if any("Capacity" in c for c in df_ntc_import.columns) else df_ntc_import.columns[1]
        export_cap_col = [c for c in df_ntc_export.columns if "Capacity" in c][0] if any("Capacity" in c for c in df_ntc_export.columns) else df_ntc_export.columns[1]
        
        # Set index column as index for lookup
        df_ntc_import = df_ntc_import.set_index(df_ntc_import.columns[0])
        df_ntc_export = df_ntc_export.set_index(df_ntc_export.columns[0])
        
        ntc_import_limits = {}
        ntc_export_limits = {}
        
        for line in CH_LINES:
            csv_key = line_to_csv_key(line)
            # Also try reversed order (CH00-AT00 vs AT00-CH00)
            parts = csv_key.split("-")
            csv_key_reversed = f"{parts[1]}-{parts[0]}" if len(parts) == 2 else csv_key
            
            # Import limits
            ntc_import_limits[line] = float(df_ntc_import.loc[csv_key, import_cap_col]) # type: ignore
            
            # Export limits
            ntc_export_limits[line] = float(df_ntc_export.loc[csv_key, export_cap_col]) # type: ignore
        
        # Calculate hourly utilization per line
        utilizations = []
        for line in CH_LINES:
            line_data = df_export[df_export["lineATC"] == line].copy()
            
            line_data["value"] = pd.to_numeric(line_data["value"], errors="coerce").fillna(0.0)
            hourly_flow = line_data.groupby("T")["value"].sum()
            
            import_limit = ntc_import_limits[line]
            export_limit = ntc_export_limits[line]
            
            # Calculate utilization based on flow direction (vectorized)
            # Positive flow = import direction, negative flow = export direction
            util = np.where(
                hourly_flow <= 0,
                np.abs(hourly_flow) / import_limit if import_limit > 0 else 0,
                np.abs(hourly_flow) / export_limit if export_limit > 0 else 0
            )
            utilizations.append(pd.Series(util, index=hourly_flow.index))
        
        # Average across all lines
        avg_util = pd.concat(utilizations, axis=1).mean(axis=1)
        return avg_util.reindex(template["T"]).fillna(0.0)
    
    hourly_line_loading = calc_line_loading_hourly(df_export, scenario_name, run_year, eu_policy)
    
    # ========== BUILD OUTPUT ==========
    
    # Define output parameters
    output_params = [
        ("Hourly generation solar PV - Rooftop", "GWh", hourly_pv_roof.values),
        ("Hourly generation solar PV - Agri", "GWh", None),  # Placeholder
        ("Hourly generation solar PV - Alpine", "GWh", None),  # Placeholder
        ("Hourly generation wind power", "GWh", hourly_wind.values),
        ("Hourly generation bioenergy", "GWh", hourly_bio.values),
        ("Hourly generation geothermal", "GWh", None),  # Placeholder
        ("Hourly generation waste incineration", "GWh", "Grouped with other technologies and not reported separately."),
        ("Hourly generation gas", "GWh", hourly_gas.values),
        ("Hourly generation nuclear", "GWh", hourly_nuclear.values),
        ("Hourly generation hydro dam", "GWh", hourly_hydro_dam.values),
        ("Hourly generation hydro run of river", "GWh", hourly_hydro_ror.values),
        ("Hourly generation hydro pumped storage", "GWh", "The generation of hydro pumped storage and hydro dam in FEM is considered as one."),
        ("Hourly demand hydro pumped storage", "GWh", hourly_hydro_psp_demand.values),
        ("Hourly generation battery", "GWh", hourly_battery_gen.values),
        ("Hourly charge battery", "GWh", hourly_battery_charge.values),
        ("Hourly EV-DSM up", "GWh", hourly_ev_dsm_up),
        ("Hourly EV-DSM down", "GWh", hourly_ev_dsm_down),
        ("Hourly HP-DSM up", "GWh", hourly_hp_dsm_up),
        ("Hourly HP-DSM down", "GWh", hourly_hp_dsm_down),
        ("Hourly generation curtailment - CH", "GWh", hourly_curt_ch),
        ("Hourly generation curtailment - Abroad", "GWh", hourly_curt_abroad),
        ("Hourly load shedded", "GWh", hourly_load_shedded),
        ("Hourly exchange CH-DE", "GWh", hourly_ch_de.values),
        ("Hourly exchange DE-CH", "GWh", hourly_de_ch.values),
        ("Hourly exchange CH-FR", "GWh", hourly_ch_fr.values),
        ("Hourly exchange FR-CH", "GWh", hourly_fr_ch.values),
        ("Hourly exchange CH-IT", "GWh", hourly_ch_it.values),
        ("Hourly exchange IT-CH", "GWh", hourly_it_ch.values),
        ("Hourly exchange CH-AT", "GWh", hourly_ch_at.values),
        ("Hourly exchange AT-CH", "GWh", hourly_at_ch.values),
        ("Hourly import to CH (total)", "GWh", hourly_import_total.values),
        ("Hourly export from CH (total)", "GWh", hourly_export_total.values),
        ("Hourly net import (import-export)", "GWh", hourly_net_import.values),
        ("Hourly net load", "GWh", hourly_netload.values),
        ("Hourly electricity price CH", "EUR/MWh", hourly_price_ch.values),
        ("Hourly electricity price DE", "EUR/MWh", hourly_price_de.values),
        ("Hourly electricity price FR", "EUR/MWh", hourly_price_fr.values),
        ("Hourly electricity price IT", "EUR/MWh", hourly_price_it.values),
        ("Hourly electricity price AT", "EUR/MWh", hourly_price_at.values),
        ("Hourly costs for consumers", "EUR", hourly_consumer_costs.values),
        ("Hourly revenues for generators", "EUR", hourly_generator_revenues.values),
        ("Average line loading - all lines", "%", None),  # Empty
        ("Average line loading - internal lines", "%", "FEM does not consider internal lines."),
        ("Average line loading - interconnectors", "%", hourly_line_loading.values),
    ]
    
    # Build DataFrame with Model, Scenario Name, Output-Parameter, Unit, then actual hours
    rows = []
    for param, unit, values in output_params:
        row = {
            "Model": f"FEM v{model_version}",
            "Scenario Name": subscenario if subscenario is not None else scenario_name,
            "Output-Parameter": param,
            "Unit": unit,
        }
        
        if values is None:
            # Placeholder - all empty
            for h in actual_hours:
                row[str(h)] = ""
        elif isinstance(values, str):
            # Text message - put in first hour, rest empty
            row[str(actual_hours[0])] = values
            for h in actual_hours[1:]:
                row[str(h)] = ""
        else:
            # Numeric values - values array is indexed by position in actual_hours
            for idx, h in enumerate(actual_hours):
                row[str(h)] = f"{values[idx]:.6f}" if values[idx] != 0 else "0"
        
        rows.append(row)
    
    # Create DataFrame
    columns = ["Model", "Scenario Name", "Output-Parameter", "Unit"] + [str(h) for h in actual_hours]
    df = pd.DataFrame(rows, columns=columns)
    
    # Export to CSV
    output_path = report_dir / "Output_Temp.csv"
    df.to_csv(output_path, index=False)
