"""
Export system-level model outputs for Swiss model intercomparison.

This module provides functions to export aggregated system-wide output metrics
from the energy system model, including imports/exports, costs, emissions,
and energy balances.
"""

from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np
import pandas as pd

from model.version import MODEL_VERSION
from detailed_reporting.constants import (
    CHF_TO_EUR, is_winter_t, is_summer_t, get_run_year, get_flexible_household_heatpump_share,
    HP_PLANTS, INV_COST_PLANTS, OP_COST_PLANTS, EMISSIONS_PLANTS, GEN_PLANTS,
    get_subscenario_weight
)


# Cost files whose value column must be divided by the subscenario weight to
# recover the unweighted per-subscenario value (see user spec).
_WEIGHT_DIVIDE_COST_FILES = {
    "cost_inv_dict.csv": "cost_CHF",
    "cost_op_dict.csv": "cost_CHF",
}


# Swiss cross-border lines
CH_LINES = ["HVAC_AT00_CH00", "HVAC_DE00_CH00", "HVAC_FR00_CH00", "HVAC_IT00_CH00"]

# Map line to neighbor node for price lookup
LINE_TO_NEIGHBOR = {
    "HVAC_AT00_CH00": "AT00",
    "HVAC_DE00_CH00": "DE00",
    "HVAC_FR00_CH00": "FR00",
    "HVAC_IT00_CH00": "IT00",
}


def _parse_t_index(t: str) -> int:
    """Extract integer from time index like 't_123'."""
    if isinstance(t, str) and t.startswith("t_"):
        return int(t[2:])
    return int(t) if isinstance(t, (int, float)) else 0


def _is_winter_t(t: str) -> bool:
    """Wrapper for reporting_main.is_winter_t."""
    return is_winter_t(t)


def _is_summer_t(t: str) -> bool:
    """Wrapper for reporting_main.is_summer_t."""
    return is_summer_t(t)


def _get_run_year(scenario_name: str, subscenario: str = None) -> int:  # type: ignore
    """Get run_year from settings.csv or fallback to parsing scenario name."""
    return get_run_year(scenario_name, subscenario)


def _scenario_or_test_path(scenario_name: str, filename: str) -> Path:
    """Return path to output file, falling back to test folder."""
    primary = Path("output") / scenario_name / filename
    if primary.exists():
        return primary
    fallback = Path("output") / "test" / filename
    return fallback if fallback.exists() else primary


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
    # Skip the model path when slicing for a specific subscenario; the Pyomo
    # object can't be filtered by subscenario here.
    if subscenario is None and model is not None and hasattr(model, attr_name):
        df = _pyomo_to_dataframe(getattr(model, attr_name), expected_cols)
        if not df.empty:
            return df
    return _read_csv(scenario_name, csv_name, subscenario=subscenario)


def _sum_values(df: pd.DataFrame, value_col: str = "value") -> float:
    if df.empty or value_col not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[value_col], errors="coerce").fillna(0.0).sum())


def export_output_system(model, scenario_name: str, model_version: str = None, # type: ignore
                         solve_time_seconds: float = None, total_time_seconds: float = None,  # type: ignore
                         subscenario: str = None):  # type: ignore
    """
    Export system-level aggregated model outputs to CSV.
    
    Parameters
    ----------
    model : pyomo.ConcreteModel
        The solved Pyomo model instance containing output variables.
    scenario_name : str
        Name of the scenario being analyzed.
    model_version : str, optional
        Model version string (default: MODEL_VERSION from model/version.py)
    solve_time_seconds : float, optional
        Time in seconds the solver took (from core.py solve_time)
    total_time_seconds : float, optional
        Total time from start to end including data import/export
    
    Returns
    -------
    None
        Writes Output_Sys.csv to the detailed_reporting subdirectory.
    """
    if model_version is None:
        model_version = MODEL_VERSION
    
    # Create output directory
    report_dir = Path("output") / scenario_name / "detailed_reporting"
    if subscenario is not None:
        report_dir = report_dir / subscenario
    report_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    df_export = _get_data(model, scenario_name, "Export", "Export.csv",
                          ["lineATC", "T", "Scenarios", "value"], subscenario=subscenario)
    df_dual = _get_data(model, scenario_name, "energy_balance_dual", "energy_balance_dual.csv",
                        ["Node", "T", "Scenarios", "value"], subscenario=subscenario)
    df_curtailment = _get_data(model, scenario_name, "curtailment", "curtailment.csv",
                               ["Consumer_with_infeed", "T", "Scenarios", "value"], subscenario=subscenario)
    df_lostload = _get_data(model, scenario_name, "lostload", "lostload.csv",
                            ["Consumer", "T", "lostLoad_step", "Scenarios", "value"], subscenario=subscenario)
    df_gen = _get_data(model, scenario_name, "gen", "gen.csv",
                       ["P_gen", "T", "Scenarios", "value"], subscenario=subscenario)
    df_gen_max = _get_data(model, scenario_name, "gen_max", "gen_max.csv",
                           ["P_gen", "Scenarios", "value"], subscenario=subscenario)
    df_gen_max_infeedp = _get_data(model, scenario_name, "gen_max_infeedp", "gen_max_infeedp.csv",
                                   ["Infeedp", "Scenarios", "value"], subscenario=subscenario)

    # Load cost dictionaries (route through _read_csv so subscenario filter + weight
    # division are applied for cost_inv_dict / cost_op_dict, emissions left unweighted).
    df_cost_inv = _read_csv(scenario_name, "cost_inv_dict.csv", subscenario=subscenario)
    df_cost_op = _read_csv(scenario_name, "cost_op_dict.csv", subscenario=subscenario)
    df_emissions = _read_csv(scenario_name, "emissions_dict.csv", subscenario=subscenario)
    
    # Use hardcoded plant lists from constants
    inv_plants = INV_COST_PLANTS
    op_plants = OP_COST_PLANTS
    emissions_plants = EMISSIONS_PLANTS
    gen_plants = GEN_PLANTS
    
    run_year = _get_run_year(scenario_name, subscenario)
    
    # ========== HELPER FUNCTIONS ==========
    
    def get_ch_import_export(df: pd.DataFrame, season: str = None) -> Tuple[float, float]: # type: ignore
        """Get import (>0) and export (<0) sums for CH lines.
        Returns (import_sum, export_sum) where export_sum is positive (absolute value).
        """
        if df.empty:
            return 0.0, 0.0
        
        ch_df = df[df["lineATC"].isin(CH_LINES)].copy()
        
        if season == "winter":
            ch_df = ch_df[ch_df["T"].astype(str).map(_is_winter_t)]
        elif season == "summer":
            ch_df = ch_df[ch_df["T"].astype(str).map(_is_summer_t)]
        
        if ch_df.empty:
            return 0.0, 0.0
        
        ch_df["value"] = pd.to_numeric(ch_df["value"], errors="coerce").fillna(0.0)
        
        # Positive = import to CH, Negative = export from CH
        import_sum = ch_df.loc[ch_df["value"] > 0, "value"].sum()
        export_sum = -ch_df.loc[ch_df["value"] < 0, "value"].sum()  # Make positive
        
        return float(import_sum), float(export_sum)
    
    def get_ch_prices(df_dual: pd.DataFrame) -> pd.DataFrame:
        """Get Swiss electricity prices by hour."""
        if df_dual.empty:
            return pd.DataFrame()
        ch_prices = df_dual[df_dual["Node"] == "CH00"].copy()
        ch_prices["value"] = pd.to_numeric(ch_prices["value"], errors="coerce").fillna(0.0)
        return ch_prices
    
    def get_neighbor_prices(df_dual: pd.DataFrame, node: str) -> pd.DataFrame:
        """Get electricity prices for a neighbor node by hour."""
        if df_dual.empty:
            return pd.DataFrame()
        prices = df_dual[df_dual["Node"] == node].copy()
        prices["value"] = pd.to_numeric(prices["value"], errors="coerce").fillna(0.0)
        return prices
    
    def calc_import_cost(df_export: pd.DataFrame, df_dual: pd.DataFrame, season: str = None) -> float: # type: ignore
        """Calculate import cost: sum of (import_MWh * neighbor_price)."""
        if df_export.empty or df_dual.empty:
            return 0.0
        
        total_cost = 0.0
        for line in CH_LINES:
            neighbor = LINE_TO_NEIGHBOR[line]
            line_df = df_export[df_export["lineATC"] == line].copy()
            
            if season == "winter":
                line_df = line_df[line_df["T"].astype(str).map(_is_winter_t)]
            elif season == "summer":
                line_df = line_df[line_df["T"].astype(str).map(_is_summer_t)]
            
            if line_df.empty:
                continue
            
            line_df["value"] = pd.to_numeric(line_df["value"], errors="coerce").fillna(0.0)
            # Only imports (positive)
            line_df = line_df[line_df["value"] > 0]
            
            if line_df.empty:
                continue
            
            # Get neighbor prices
            neighbor_prices = get_neighbor_prices(df_dual, neighbor)
            if neighbor_prices.empty:
                continue
            
            # Merge on T and Scenarios
            merged = pd.merge(line_df, neighbor_prices[["T", "Scenarios", "value"]],
                             on=["T", "Scenarios"], suffixes=("_export", "_price"))
            if not merged.empty:
                total_cost += (merged["value_export"] * merged["value_price"]).sum()
        
        return float(total_cost)
    
    def calc_export_revenue(df_export: pd.DataFrame, df_dual: pd.DataFrame, season: str = None) -> float: # type: ignore
        """Calculate export revenue: sum of (export_MWh * CH_price)."""
        if df_export.empty or df_dual.empty:
            return 0.0
        
        ch_prices = get_ch_prices(df_dual)
        if ch_prices.empty:
            return 0.0
        
        ch_df = df_export[df_export["lineATC"].isin(CH_LINES)].copy()
        
        if season == "winter":
            ch_df = ch_df[ch_df["T"].astype(str).map(_is_winter_t)]
        elif season == "summer":
            ch_df = ch_df[ch_df["T"].astype(str).map(_is_summer_t)]
        
        if ch_df.empty:
            return 0.0
        
        ch_df["value"] = pd.to_numeric(ch_df["value"], errors="coerce").fillna(0.0)
        # Only exports (negative), make positive
        ch_df = ch_df[ch_df["value"] < 0].copy()
        ch_df["value"] = -ch_df["value"]
        
        if ch_df.empty:
            return 0.0
        
        # Merge with CH prices
        merged = pd.merge(ch_df, ch_prices[["T", "Scenarios", "value"]],
                         on=["T", "Scenarios"], suffixes=("_export", "_price"))
        if merged.empty:
            return 0.0
        
        return float((merged["value_export"] * merged["value_price"]).sum())
    
    def calc_price_stats(df: pd.DataFrame, value_col: str = "value") -> Dict[str, float]:
        """Calculate price statistics: average, 5th, 95th percentile, min, max."""
        if df.empty or value_col not in df.columns:
            return {"average": 0.0, "p5": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
        
        values = pd.to_numeric(df[value_col], errors="coerce").dropna()
        if len(values) == 0:
            return {"average": 0.0, "p5": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
        
        return {
            "average": float(values.mean()),
            "p5": float(np.percentile(values, 5)),
            "p95": float(np.percentile(values, 95)),
            "min": float(values.min()),
            "max": float(values.max()),
        }
    
    def calc_import_price_stats_for_line(df_export: pd.DataFrame, df_dual: pd.DataFrame,
                                         line: str) -> Dict[str, float]:
        """Calculate import price statistics for a specific line."""
        if df_export.empty or df_dual.empty:
            return {"average": 0.0, "p5": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
        
        neighbor = LINE_TO_NEIGHBOR.get(line)
        if not neighbor:
            return {"average": 0.0, "p5": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
        
        line_df = df_export[(df_export["lineATC"] == line)].copy()
        line_df["value"] = pd.to_numeric(line_df["value"], errors="coerce").fillna(0.0)
        # Only imports (positive)
        line_df = line_df[line_df["value"] > 0]
        
        if line_df.empty:
            return {"average": 0.0, "p5": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
        
        neighbor_prices = get_neighbor_prices(df_dual, neighbor)
        merged = pd.merge(line_df, neighbor_prices[["T", "Scenarios", "value"]],
                         on=["T", "Scenarios"], suffixes=("_export", "_price"))
        
        if merged.empty:
            return {"average": 0.0, "p5": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
        
        return calc_price_stats(merged, "value_price")
    
    def calc_export_price_stats_for_line(df_export: pd.DataFrame, df_dual: pd.DataFrame,
                                         line: str) -> Dict[str, float]:
        """Calculate export price statistics for a specific line (CH price when exporting)."""
        if df_export.empty or df_dual.empty:
            return {"average": 0.0, "p5": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
        
        line_df = df_export[(df_export["lineATC"] == line)].copy()
        line_df["value"] = pd.to_numeric(line_df["value"], errors="coerce").fillna(0.0)
        # Only exports (negative)
        line_df = line_df[line_df["value"] < 0]
        
        if line_df.empty:
            return {"average": 0.0, "p5": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
        
        ch_prices = get_ch_prices(df_dual)
        merged = pd.merge(line_df, ch_prices[["T", "Scenarios", "value"]],
                         on=["T", "Scenarios"], suffixes=("_export", "_price"))
        
        if merged.empty:
            return {"average": 0.0, "p5": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
        
        return calc_price_stats(merged, "value_price")
    
    def calc_load_shedding(df_lostload: pd.DataFrame, season: str = None) -> float: # type: ignore
        """Calculate load shedding for CH00_fixedconsumer."""
        if df_lostload.empty:
            return 0.0
        
        ch_ll = df_lostload[df_lostload["Consumer"] == "CH00_fixedconsumer"].copy()
        
        if season == "winter":
            ch_ll = ch_ll[ch_ll["T"].astype(str).map(_is_winter_t)]
        elif season == "summer":
            ch_ll = ch_ll[ch_ll["T"].astype(str).map(_is_summer_t)]
        
        return _sum_values(ch_ll)
    
    def calc_curtailment_ch(df_curtailment: pd.DataFrame, df_dual: pd.DataFrame,
                            df_export: pd.DataFrame) -> float:
        """Calculate actual curtailment in Switzerland considering exports during zero-price hours."""
        if df_curtailment.empty:
            return 0.0
        
        # Get CH00 curtailment
        ch_curt = df_curtailment[df_curtailment["Consumer_with_infeed"] == "CH00_fixedconsumer"].copy()
        ch_curt["value"] = pd.to_numeric(ch_curt["value"], errors="coerce").fillna(0.0)
        
        if ch_curt.empty:
            return _sum_values(ch_curt)
        
        # Get hours where CH price is near zero
        if not df_dual.empty:
            ch_prices = df_dual[df_dual["Node"] == "CH00"].copy()
            ch_prices["value"] = pd.to_numeric(ch_prices["value"], errors="coerce").fillna(0.0)
            zero_price_hours = ch_prices[ch_prices["value"] < 0.01][["T", "Scenarios"]].drop_duplicates()
            
            # For zero price hours, adjust curtailment by net exports
            # actual_curtailment = reported_curtailment - net_exports (exports - imports)
            if not zero_price_hours.empty and not df_export.empty:
                ch_export = df_export[df_export["lineATC"].isin(CH_LINES)].copy()
                ch_export["value"] = pd.to_numeric(ch_export["value"], errors="coerce").fillna(0.0)
                
                # Sum exports per T, Scenarios (negative = export from CH)
                net_export = ch_export.groupby(["T", "Scenarios"])["value"].sum().reset_index()
                # Negative means export from CH (we want net import)
                net_export["net_export"] = -net_export["value"]  # Make exports positive
                
                # Merge with curtailment for zero-price hours
                merged = pd.merge(ch_curt, zero_price_hours, on=["T", "Scenarios"], how="inner")
                merged = pd.merge(merged, net_export[["T", "Scenarios", "net_export"]],
                                 on=["T", "Scenarios"], how="left")
                merged["net_export"] = merged["net_export"].fillna(0.0)
                
                # Actual curtailment = reported - net_export
                merged["actual_curt"] = merged["value"] - merged["net_export"]
                merged["actual_curt"] = merged["actual_curt"].clip(lower=0)  # Can't be negative
                
                # Non-zero price hours: use reported curtailment
                non_zero = ch_curt[~ch_curt.set_index(["T", "Scenarios"]).index.isin(
                    zero_price_hours.set_index(["T", "Scenarios"]).index)]
                
                return float(merged["actual_curt"].sum() + _sum_values(non_zero))
        
        return _sum_values(ch_curt)
    
    def calc_curtailment_abroad(df_curtailment: pd.DataFrame, ch_curtailment: float) -> float:
        """Calculate total curtailment abroad (all nodes except CH)."""
        if df_curtailment.empty:
            return 0.0
        
        total = _sum_values(df_curtailment)
        return max(0.0, total - ch_curtailment)
    
    def calc_capacity_pv_wind(df_gen_max: pd.DataFrame, df_gen_max_infeedp: pd.DataFrame) -> float:
        """Calculate total PV + Wind capacity in GW."""
        total = 0.0
        ch_zones = [f"CH0{i}" for i in range(1, 8)]
        
        # From gen_max (added)
        if not df_gen_max.empty:
            for zone in ch_zones:
                for tech in ["pvrf", "windon"]:
                    plant = f"{zone}_{tech}"
                    mask = df_gen_max["P_gen"] == plant
                    total += df_gen_max.loc[mask, "value"].sum()
        
        # From gen_max_infeedp (given)
        if not df_gen_max_infeedp.empty:
            col = "Infeedp" if "Infeedp" in df_gen_max_infeedp.columns else df_gen_max_infeedp.columns[0]
            for zone in ch_zones:
                for tech in ["pvrf", "windon"]:
                    plant = f"{zone}_{tech}"
                    mask = df_gen_max_infeedp[col] == plant
                    total += pd.to_numeric(df_gen_max_infeedp.loc[mask, "value"], errors="coerce").fillna(0.0).sum()
        
        return total / 1000.0  # MW to GW
    
    def calc_investment_costs(df_cost_inv: pd.DataFrame, plants: List[str]) -> float:
        """Sum investment costs for specified plants."""
        if df_cost_inv.empty or not plants:
            return 0.0
        
        # Find the plant column
        plant_col = "plant" if "plant" in df_cost_inv.columns else df_cost_inv.columns[0]
        cost_col = [c for c in df_cost_inv.columns if "cost" in c.lower() or "CHF" in c]
        cost_col = cost_col[0] if cost_col else df_cost_inv.columns[-1]
        
        mask = df_cost_inv[plant_col].isin(plants)
        return pd.to_numeric(df_cost_inv.loc[mask, cost_col], errors="coerce").fillna(0.0).sum()
    
    def calc_operation_costs(df_cost_op: pd.DataFrame, plants: List[str]) -> float:
        """Sum operation costs for specified plants."""
        if df_cost_op.empty or not plants:
            return 0.0
        
        plant_col = "plant" if "plant" in df_cost_op.columns else df_cost_op.columns[0]
        cost_col = [c for c in df_cost_op.columns if "cost" in c.lower() or "CHF" in c]
        cost_col = cost_col[0] if cost_col else df_cost_op.columns[-1]
        
        mask = df_cost_op[plant_col].isin(plants)
        return pd.to_numeric(df_cost_op.loc[mask, cost_col], errors="coerce").fillna(0.0).sum()
    
    def calc_total_emissions(df_emissions: pd.DataFrame, plants: List[str]) -> float:
        """Sum emissions for specified plants."""
        if df_emissions.empty or not plants:
            return 0.0
        
        plant_col = "plant" if "plant" in df_emissions.columns else df_emissions.columns[0]
        emissions_col = [c for c in df_emissions.columns if "emission" in c.lower() or "CO2" in c]
        emissions_col = emissions_col[0] if emissions_col else df_emissions.columns[-1]
        
        mask = df_emissions[plant_col].isin(plants)
        return pd.to_numeric(df_emissions.loc[mask, emissions_col], errors="coerce").fillna(0.0).sum()
    
    def calc_total_gen_for_plants(df_gen: pd.DataFrame, plants: List[str]) -> float:
        """Sum generation for specified plants."""
        if df_gen.empty or not plants:
            return 0.0
        mask = df_gen["P_gen"].isin(plants)
        return _sum_values(df_gen.loc[mask])
    
    def calc_ev_energy_shifted(df_storage_charge: pd.DataFrame, df_ev_inflexible: pd.DataFrame,
                                df_gen: pd.DataFrame, run_year: int, season: str = None) -> float: # type: ignore
        """
        Calculate EV energy shifting: energy moved from high-demand to low-demand hours.
        
        Logic:
        1. Baseline = EV_demand_hourly_{run_year}.csv (100% total EV consumption, no flexibility)
        2. Actual = EV_inflexible_demand + storage_charge[CH00_EV_flex] + V2G_charge - V2G_feedin
        3. Energy shifted = Sum of (baseline - actual) where baseline > actual
        
        Returns 0.0 if there's no actual data for the requested season.
        """
        # Load baseline EV demand (100% total, no flexibility)
        baseline_path = Path("input") / "demand" / f"EV_demand_hourly_{run_year}.csv"
        if not baseline_path.exists():
            return 0.0
        
        try:
            df_baseline = pd.read_csv(baseline_path)
            # Map column 't' to 't_X' format
            if 't' in df_baseline.columns:
                df_baseline['T'] = df_baseline['t'].apply(lambda x: f"t_{x}" if not str(x).startswith('t_') else str(x))
            baseline_col = [c for c in df_baseline.columns if 'demand' in c.lower() or 'MWh' in c][0]
        except Exception:
            return 0.0
        
        # Get flexible EV charging (storage_charge for EV_CH or CH00_EV_flex)
        ev_flex_charge = df_storage_charge[
            df_storage_charge["P_pumping"].isin(["CH00_EV_flex", "EV_CH"])
        ].copy() if not df_storage_charge.empty else pd.DataFrame()
        
        if ev_flex_charge.empty:
            return 0.0
        
        ev_flex_charge["value"] = pd.to_numeric(ev_flex_charge["value"], errors="coerce").fillna(0.0)
        
        # Filter by season BEFORE grouping to check if we have data for this season
        if season == "winter":
            ev_flex_charge = ev_flex_charge[ev_flex_charge["T"].astype(str).map(_is_winter_t)]
        elif season == "summer":
            ev_flex_charge = ev_flex_charge[ev_flex_charge["T"].astype(str).map(_is_summer_t)]
        
        # If no data for this season, return 0
        if ev_flex_charge.empty:
            return 0.0
        
        # Sum flexible charging per hour (across scenarios - take mean)
        ev_flex_hourly = ev_flex_charge.groupby("T")["value"].mean().reset_index()
        ev_flex_hourly.columns = ["T", "flex_charge"]
        
        # Get inflexible EV demand for CH00
        if not df_ev_inflexible.empty:
            df_ev_inflex_filtered = df_ev_inflexible[df_ev_inflexible["Node"] == "CH00"].copy()
            if season == "winter":
                df_ev_inflex_filtered = df_ev_inflex_filtered[df_ev_inflex_filtered["T"].astype(str).map(_is_winter_t)]
            elif season == "summer":
                df_ev_inflex_filtered = df_ev_inflex_filtered[df_ev_inflex_filtered["T"].astype(str).map(_is_summer_t)]
            
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
            if season == "winter":
                v2g_charge = v2g_charge[v2g_charge["T"].astype(str).map(_is_winter_t)]
            elif season == "summer":
                v2g_charge = v2g_charge[v2g_charge["T"].astype(str).map(_is_summer_t)]
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
            if season == "winter":
                v2g_feedin = v2g_feedin[v2g_feedin["T"].astype(str).map(_is_winter_t)]
            elif season == "summer":
                v2g_feedin = v2g_feedin[v2g_feedin["T"].astype(str).map(_is_summer_t)]
            v2g_feedin["value"] = pd.to_numeric(v2g_feedin["value"], errors="coerce").fillna(0.0)
            v2g_feedin_hourly = v2g_feedin.groupby("T")["value"].sum().reset_index()
            v2g_feedin_hourly.columns = ["T", "v2g_feedin"]
        else:
            v2g_feedin_hourly = pd.DataFrame(columns=["T", "v2g_feedin"])
        
        # Filter baseline by season
        df_baseline_filtered = df_baseline.copy()
        if season == "winter":
            df_baseline_filtered = df_baseline_filtered[df_baseline_filtered["T"].astype(str).map(_is_winter_t)]
        elif season == "summer":
            df_baseline_filtered = df_baseline_filtered[df_baseline_filtered["T"].astype(str).map(_is_summer_t)]
        
        # Merge all together - use inner join to only include hours with actual data
        merged = pd.merge(df_baseline_filtered[["T", baseline_col]], ev_flex_hourly, on="T", how="inner")
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
        
        if merged.empty:
            return 0.0
        
        # Energy shifted = sum of (baseline - actual) where baseline > actual
        merged["shifted"] = (merged["baseline"] - merged["actual"]).clip(lower=0)
        
        return float(merged["shifted"].sum())
    
    def calc_hp_energy_shifted(df_storage_charge: pd.DataFrame, df_ba_th_con: pd.DataFrame,
                                df_cop: pd.DataFrame, hp_plants: List[str], 
                                flex_hp_share: float, season: str = None) -> float: # type: ignore
        """
        Calculate HP energy shifting: energy moved from high-demand to low-demand hours.
        
        All calculations are converted to electric units (MWh_el) by dividing by COP.
        
        Logic (from documentation):
        1. Baseline (inflexible) = BA_th_con / COP summed hourly (total electric demand if no flexibility)
        2. Actual demand = storage_charge / COP for HP plants (flexible electric consumption)
                          + (BA_th_con / COP) * flex_hp_share (inflexible portion)
        3. Energy shifted = (actual - inflexible), sum all hours where < 0, multiply by -1
        
        Returns 0.0 if there's no actual data for the requested season.
        """
        if df_storage_charge.empty or df_ba_th_con.empty or df_cop.empty:
            return 0.0
        
        # Get flexible HP thermal consumption from storage_charge
        hp_flex_charge = df_storage_charge[df_storage_charge["P_pumping"].isin(hp_plants)].copy()
        if hp_flex_charge.empty:
            return 0.0
        
        hp_flex_charge["value"] = pd.to_numeric(hp_flex_charge["value"], errors="coerce").fillna(0.0)
        
        # Filter by season BEFORE grouping to check if we have data for this season
        if season == "winter":
            hp_flex_charge = hp_flex_charge[hp_flex_charge["T"].astype(str).map(_is_winter_t)]
        elif season == "summer":
            hp_flex_charge = hp_flex_charge[hp_flex_charge["T"].astype(str).map(_is_summer_t)]
        
        # If no data for this season, return 0
        if hp_flex_charge.empty:
            return 0.0
        
        # Prepare BA_th_con and COP data
        df_ba_filtered = df_ba_th_con.copy()
        df_ba_filtered["value"] = pd.to_numeric(df_ba_filtered["value"], errors="coerce").fillna(0.0)
        
        df_cop_filtered = df_cop.copy()
        df_cop_filtered["value"] = pd.to_numeric(df_cop_filtered["value"], errors="coerce").fillna(1.0)
        
        if season == "winter":
            df_ba_filtered = df_ba_filtered[df_ba_filtered["T"].astype(str).map(_is_winter_t)]
            df_cop_filtered = df_cop_filtered[df_cop_filtered["T"].astype(str).map(_is_winter_t)]
        elif season == "summer":
            df_ba_filtered = df_ba_filtered[df_ba_filtered["T"].astype(str).map(_is_summer_t)]
            df_cop_filtered = df_cop_filtered[df_cop_filtered["T"].astype(str).map(_is_summer_t)]
        
        if df_ba_filtered.empty or df_cop_filtered.empty:
            return 0.0
        
        # Merge BA_th_con with COP to convert thermal to electric per BA and hour
        ba_col = "BA_names" if "BA_names" in df_ba_filtered.columns else df_ba_filtered.columns[1]
        merged_ba_cop = pd.merge(df_ba_filtered, df_cop_filtered, 
                                  on=["T", ba_col, "Scenarios"], how="left", 
                                  suffixes=("_th", "_cop"))
        merged_ba_cop["value_cop"] = merged_ba_cop["value_cop"].fillna(1.0).clip(lower=0.1)
        merged_ba_cop["elec_demand"] = merged_ba_cop["value_th"] / merged_ba_cop["value_cop"]
        
        # Sum electric demand hourly = baseline (total electric demand if no flexibility)
        baseline_hourly = merged_ba_cop.groupby("T")["elec_demand"].sum().reset_index()
        baseline_hourly.columns = ["T", "baseline_el"]
        
        # Inflexible portion = baseline * flex_hp_share
        baseline_hourly["inflex_el"] = baseline_hourly["baseline_el"] * flex_hp_share
        
        # For storage_charge, we need to convert thermal to electric
        # Merge storage_charge with average COP per hour to convert
        avg_cop_hourly = merged_ba_cop.groupby("T")["value_cop"].mean().reset_index()
        avg_cop_hourly.columns = ["T", "avg_cop"]
        
        hp_flex_with_cop = pd.merge(hp_flex_charge, avg_cop_hourly, on="T", how="left")
        hp_flex_with_cop["avg_cop"] = hp_flex_with_cop["avg_cop"].fillna(1.0).clip(lower=0.1)
        hp_flex_with_cop["elec_charge"] = hp_flex_with_cop["value"] / hp_flex_with_cop["avg_cop"]
        
        # Sum flexible electric charging per hour
        hp_flex_hourly = hp_flex_with_cop.groupby("T")["elec_charge"].sum().reset_index()
        hp_flex_hourly.columns = ["T", "flex_charge_el"]
        
        # Merge with baseline
        merged = pd.merge(baseline_hourly, hp_flex_hourly, on="T", how="inner")
        
        if merged.empty:
            return 0.0
        
        # Actual demand = flexible electric consumption + inflexible portion
        merged["actual_el"] = merged["flex_charge_el"] + merged["inflex_el"]
        
        # Energy shifted = actual - baseline, sum where < 0, multiply by -1
        merged["diff"] = merged["actual_el"] - merged["baseline_el"]
        
        # Sum only negative differences (where actual < baseline) and flip sign
        shifted = -merged.loc[merged["diff"] < 0, "diff"].sum()
        
        return float(shifted)
    
    # ========== CALCULATE VALUES ==========
    
    # Load additional data for EV/HP energy shifting
    df_storage_charge = _get_data(model, scenario_name, "storage_charge", "storage_charge.csv",
                                   ["P_pumping", "T", "Scenarios", "value"], subscenario=subscenario)
    df_ev_inflexible = _get_data(model, scenario_name, "EV_inflexible_demand", "EV_inflexible_demand.csv",
                                  ["Node", "T", "Scenarios", "value"], subscenario=subscenario)
    df_ba_th_con = _read_csv(scenario_name, "BA_th_con.csv", subscenario=subscenario)
    df_cop = _read_csv(scenario_name, "COP.csv", subscenario=subscenario)
    hp_plants = HP_PLANTS
    flex_hp_share = get_flexible_household_heatpump_share(scenario_name, subscenario)
    
    # Import/Export
    import_annual, export_annual = get_ch_import_export(df_export)
    import_winter, export_winter = get_ch_import_export(df_export, "winter")
    import_summer, export_summer = get_ch_import_export(df_export, "summer")
    
    # Trading costs
    import_cost_annual = calc_import_cost(df_export, df_dual) / 1e6  # to Mio
    export_revenue_annual = calc_export_revenue(df_export, df_dual) / 1e6
    import_cost_winter = calc_import_cost(df_export, df_dual, "winter") / 1e6
    export_revenue_winter = calc_export_revenue(df_export, df_dual, "winter") / 1e6
    import_cost_summer = calc_import_cost(df_export, df_dual, "summer") / 1e6
    export_revenue_summer = calc_export_revenue(df_export, df_dual, "summer") / 1e6
    
    # Load shedding
    ll_winter = calc_load_shedding(df_lostload, "winter") / 1e6  # to TWh
    ll_summer = calc_load_shedding(df_lostload, "summer") / 1e6
    ll_annual = ll_winter + ll_summer
    
    # EV/HP energy shifting
    ev_shifted_winter = calc_ev_energy_shifted(df_storage_charge, df_ev_inflexible, df_gen, run_year, "winter")
    ev_shifted_summer = calc_ev_energy_shifted(df_storage_charge, df_ev_inflexible, df_gen, run_year, "summer")
    hp_shifted_winter = calc_hp_energy_shifted(df_storage_charge, df_ba_th_con, df_cop, hp_plants, flex_hp_share, "winter")
    hp_shifted_summer = calc_hp_energy_shifted(df_storage_charge, df_ba_th_con, df_cop, hp_plants, flex_hp_share, "summer")
    
    # Curtailment
    curt_ch = calc_curtailment_ch(df_curtailment, df_dual, df_export) / 1e6
    curt_abroad = calc_curtailment_abroad(df_curtailment, curt_ch * 1e6) / 1e6
    
    # Prices
    ch_prices = get_ch_prices(df_dual)
    ch_price_stats = calc_price_stats(ch_prices)
    
    # Import/export price stats per country
    at_import_stats = calc_import_price_stats_for_line(df_export, df_dual, "HVAC_AT00_CH00")
    de_import_stats = calc_import_price_stats_for_line(df_export, df_dual, "HVAC_DE00_CH00")
    fr_import_stats = calc_import_price_stats_for_line(df_export, df_dual, "HVAC_FR00_CH00")
    it_import_stats = calc_import_price_stats_for_line(df_export, df_dual, "HVAC_IT00_CH00")
    
    at_export_stats = calc_export_price_stats_for_line(df_export, df_dual, "HVAC_AT00_CH00")
    de_export_stats = calc_export_price_stats_for_line(df_export, df_dual, "HVAC_DE00_CH00")
    fr_export_stats = calc_export_price_stats_for_line(df_export, df_dual, "HVAC_FR00_CH00")
    it_export_stats = calc_export_price_stats_for_line(df_export, df_dual, "HVAC_IT00_CH00")
    
    # Capacity
    capacity_pv_wind = calc_capacity_pv_wind(df_gen_max, df_gen_max_infeedp)
    
    # Costs (in CHF, convert to EUR)
    inv_costs_chf = calc_investment_costs(df_cost_inv, inv_plants)
    op_costs_chf = calc_operation_costs(df_cost_op, op_plants)
    inv_costs_eur = inv_costs_chf * CHF_TO_EUR / 1e6  # to Mio EUR
    op_costs_eur = op_costs_chf * CHF_TO_EUR / 1e6
    
    # Total generation for operational cost per unit
    total_gen = calc_total_gen_for_plants(df_gen, gen_plants) / 1e6  # to TWh
    op_cost_per_twh = (op_costs_eur * 1e6) / total_gen if total_gen > 0 else 0.0  # EUR/TWh
    
    # Emissions
    total_emissions = calc_total_emissions(df_emissions, emissions_plants)
    
    # Time
    solve_time_min = solve_time_seconds / 60.0 if solve_time_seconds else 0.0
    total_time_min = total_time_seconds / 60.0 if total_time_seconds else 0.0
    
    # ========== BUILD OUTPUT ==========
    
    # Define report rows: (Output-Parameter, Unit, total, average, 5th, 95th, min, max)
    rows = [
        ("Import to CH Annual", "TWh/yr", f"{import_annual / 1e6:.3f}", "", "", "", "", ""),
        ("Export from CH Annual", "TWh/yr", f"{export_annual / 1e6:.3f}", "", "", "", "", ""),
        ("Net import CH Annual (Import-Export)", "TWh/yr", f"{(import_annual - export_annual) / 1e6:.3f}", "", "", "", "", ""),
        ("Import WINTER", "TWh", f"{import_winter / 1e6:.3f}", "", "", "", "", ""),
        ("Export WINTER", "TWh", f"{export_winter / 1e6:.3f}", "", "", "", "", ""),
        ("Net import WINTER (Import-Export)", "TWh", f"{(import_winter - export_winter) / 1e6:.3f}", "", "", "", "", ""),
        ("Import SUMMER", "TWh", f"{import_summer / 1e6:.3f}", "", "", "", "", ""),
        ("Export SUMMER", "TWh", f"{export_summer / 1e6:.3f}", "", "", "", "", ""),
        ("Net import SUMMER (Import-Export)", "TWh", f"{(import_summer - export_summer) / 1e6:.3f}", "", "", "", "", ""),
        ("Total energy shifted EVs WINTER", "MWh/yr", f"{ev_shifted_winter:.1f}", "", "", "", "", ""),
        ("Total energy shifted EVs SUMMER", "MWh/yr", f"{ev_shifted_summer:.1f}", "", "", "", "", ""),
        ("Total energy shifted HPs WINTER", "MWh/yr", f"{hp_shifted_winter:.1f}", "", "", "", "", ""),
        ("Total energy shifted HPs SUMMER", "MWh/yr", f"{hp_shifted_summer:.1f}", "", "", "", "", ""),
        ("Load shedding WINTER", "TWh", f"{ll_winter:.3f}", "", "", "", "", ""),
        ("Load shedding SUMMER", "TWh", f"{ll_summer:.3f}", "", "", "", "", ""),
        ("Load shedding Annual (Winter+Summer)", "TWh/yr", f"{ll_annual:.3f}", "", "", "", "", ""),
        ("Generation curtailment Annual - CH", "TWh/yr", f"{curt_ch:.3f}", "", "", "", "", ""),
        ("Generation curtailment Annual - Abroad", "TWh/yr", f"{curt_abroad:.3f}", "", "", "", "", ""),
        ("Import Cost Annual", "Mio EUR", f"{import_cost_annual * CHF_TO_EUR:.3f}", "", "", "", "", ""),
        ("Export Revenue Annual", "Mio EUR", f"{export_revenue_annual * CHF_TO_EUR:.3f}", "", "", "", "", ""),
        ("Trading Costs Annual (Cost - Revenue)", "Mio EUR", f"{(import_cost_annual - export_revenue_annual) * CHF_TO_EUR:.3f}", "", "", "", "", ""),
        ("Import Cost WINTER", "Mio EUR", f"{import_cost_winter * CHF_TO_EUR:.3f}", "", "", "", "", ""),
        ("Export Revenue WINTER", "Mio EUR", f"{export_revenue_winter * CHF_TO_EUR:.3f}", "", "", "", "", ""),
        ("Import cost SUMMER", "Mio EUR", f"{import_cost_summer * CHF_TO_EUR:.3f}", "", "", "", "", ""),
        ("Export Revenue SUMMER", "Mio EUR", f"{export_revenue_summer * CHF_TO_EUR:.3f}", "", "", "", "", ""),
        ("Electricity price in CH", "EUR/MWh", "",
         f"{ch_price_stats['average'] * CHF_TO_EUR:.2f}",
         f"{ch_price_stats['p5'] * CHF_TO_EUR:.2f}",
         f"{ch_price_stats['p95'] * CHF_TO_EUR:.2f}",
         f"{ch_price_stats['min'] * CHF_TO_EUR:.2f}",
         f"{ch_price_stats['max'] * CHF_TO_EUR:.2f}"),
        ("Price for electricity import from AT", "EUR/MWh", "",
         f"{at_import_stats['average'] * CHF_TO_EUR:.2f}",
         f"{at_import_stats['p5'] * CHF_TO_EUR:.2f}",
         f"{at_import_stats['p95'] * CHF_TO_EUR:.2f}",
         f"{at_import_stats['min'] * CHF_TO_EUR:.2f}",
         f"{at_import_stats['max'] * CHF_TO_EUR:.2f}"),
        ("Price for electricity import from DE", "EUR/MWh", "",
         f"{de_import_stats['average'] * CHF_TO_EUR:.2f}",
         f"{de_import_stats['p5'] * CHF_TO_EUR:.2f}",
         f"{de_import_stats['p95'] * CHF_TO_EUR:.2f}",
         f"{de_import_stats['min'] * CHF_TO_EUR:.2f}",
         f"{de_import_stats['max'] * CHF_TO_EUR:.2f}"),
        ("Price for electricity import from FR", "EUR/MWh", "",
         f"{fr_import_stats['average'] * CHF_TO_EUR:.2f}",
         f"{fr_import_stats['p5'] * CHF_TO_EUR:.2f}",
         f"{fr_import_stats['p95'] * CHF_TO_EUR:.2f}",
         f"{fr_import_stats['min'] * CHF_TO_EUR:.2f}",
         f"{fr_import_stats['max'] * CHF_TO_EUR:.2f}"),
        ("Price for electricity import from IT", "EUR/MWh", "",
         f"{it_import_stats['average'] * CHF_TO_EUR:.2f}",
         f"{it_import_stats['p5'] * CHF_TO_EUR:.2f}",
         f"{it_import_stats['p95'] * CHF_TO_EUR:.2f}",
         f"{it_import_stats['min'] * CHF_TO_EUR:.2f}",
         f"{it_import_stats['max'] * CHF_TO_EUR:.2f}"),
        ("Price for electricity export to AT", "EUR/MWh", "",
         f"{at_export_stats['average'] * CHF_TO_EUR:.2f}",
         f"{at_export_stats['p5'] * CHF_TO_EUR:.2f}",
         f"{at_export_stats['p95'] * CHF_TO_EUR:.2f}",
         f"{at_export_stats['min'] * CHF_TO_EUR:.2f}",
         f"{at_export_stats['max'] * CHF_TO_EUR:.2f}"),
        ("Price for electricity export to DE", "EUR/MWh", "",
         f"{de_export_stats['average'] * CHF_TO_EUR:.2f}",
         f"{de_export_stats['p5'] * CHF_TO_EUR:.2f}",
         f"{de_export_stats['p95'] * CHF_TO_EUR:.2f}",
         f"{de_export_stats['min'] * CHF_TO_EUR:.2f}",
         f"{de_export_stats['max'] * CHF_TO_EUR:.2f}"),
        ("Price for electricity export to FR", "EUR/MWh", "",
         f"{fr_export_stats['average'] * CHF_TO_EUR:.2f}",
         f"{fr_export_stats['p5'] * CHF_TO_EUR:.2f}",
         f"{fr_export_stats['p95'] * CHF_TO_EUR:.2f}",
         f"{fr_export_stats['min'] * CHF_TO_EUR:.2f}",
         f"{fr_export_stats['max'] * CHF_TO_EUR:.2f}"),
        ("Price for electricity export to IT", "EUR/MWh", "",
         f"{it_export_stats['average'] * CHF_TO_EUR:.2f}",
         f"{it_export_stats['p5'] * CHF_TO_EUR:.2f}",
         f"{it_export_stats['p95'] * CHF_TO_EUR:.2f}",
         f"{it_export_stats['min'] * CHF_TO_EUR:.2f}",
         f"{it_export_stats['max'] * CHF_TO_EUR:.2f}"),
        ("Capacity PV + Wind", "GW", f"{capacity_pv_wind:.3f}", "", "", "", "", ""),
        ("Investment costs annualised All", "Mio EUR", f"{inv_costs_eur:.3f}", "", "", "", "", ""),
        ("Operation costs anualised All", "Mio EUR", f"{op_costs_eur:.3f}", "", "", "", "", ""),
        ("Total annualised costs All (with trading costs)", "Mio EUR",
         f"{inv_costs_eur + op_costs_eur + import_cost_annual * CHF_TO_EUR}", "", "", "", "", ""),
        ("Operational costs per unit of generated energy", "EUR/TWh", f"{op_cost_per_twh:.3f}", "", "", "", "", ""),
        ("Transmission grid expansion investment costs", "Mio EUR", "FEM does not expand the transmission grid.", "", "", "", "", ""),
        ("Grid Expansion within CH", "GW", "", "", "", "", "", ""),
        ("Grid Expansion to neighbours", "GW", "", "", "", "", "", ""),
        ("Total emissions", "tonCO2/yr", f"{total_emissions:.0f}", "", "", "", "", ""),
        ("Time to solve model", "min", f"{total_time_min:.2f}" if total_time_seconds else "", "", "", "", "", ""),
        ("Memory requirements", "GB", "", "", "", "", "", ""),
    ]
    
    # Build DataFrame
    data = []
    for row in rows:
        data.append({
            "Model": f"FEM v{model_version}",
            "Scenario Name": subscenario if subscenario is not None else scenario_name,
            "Output-Parameter": row[0],
            "Unit": row[1],
            "total": row[2],
            "average": row[3],
            "5th": row[4],
            "95th": row[5],
            "min": row[6],
            "max": row[7],
        })
    
    df = pd.DataFrame(data, columns=[
        "Model", "Scenario Name", "Output-Parameter", "Unit",
        "total", "average", "5th", "95th", "min", "max"
    ])
    
    # Export to CSV
    output_path = report_dir / "Output_Sys.csv"
    df.to_csv(output_path, index=False)
