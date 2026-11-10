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

# ============ SWISS HEAT-PROVIDING TECHNOLOGIES ============
# Plants in CH that are part of the heating system: heat-producing plants
# (CHP, EGS, HP, resistive heaters, thermalNew/boiler) and heat storage
# (PTES pit thermal storage, TTES tank thermal storage).
# Excluded: demand-side response (dsrTh) — this is a demand-side resource, not an asset.
# Used to extend cost/emissions/generation aggregations so they cover Swiss heating tech.
# Tech availability by network level (from cost_inv_thermal_dict.csv inventory):
#   DH   → CHPNew, EGSNew, HPNew, resistiveNew, thermalNew, PTES_large, TTES_medium
#   ILLT → CHPNew, HPNew, resistiveNew, thermalNew, PTES_large, TTES_medium (no EGS)
#   ILHT → CHPNew, HPNew, resistiveNew, thermalNew, TTES_medium           (no EGS, no PTES)

_CH_HEAT_DH_REGIONS = ["Alpen", "Jura", "Mittelland", "Voralpen", "medium"]
_CH_HEAT_IL_REGIONS = ["Alpen", "Alpensuedseite", "Jura", "Mittelland", "Voralpen"]
_CH_HEAT_DH_TECHS = ["CHPNew", "EGSNew", "HPNew", "resistiveNew", "thermalNew",
                     "PTES_large", "TTES_medium"]
_CH_HEAT_ILLT_TECHS = ["CHPNew", "HPNew", "resistiveNew", "thermalNew",
                       "PTES_large", "TTES_medium"]
_CH_HEAT_ILHT_TECHS = ["CHPNew", "HPNew", "resistiveNew", "thermalNew", "TTES_medium"]

CH_HEAT_PROVIDING_PLANTS: List[str] = (
    [f"DH_{r}_{t}" for r in _CH_HEAT_DH_REGIONS for t in _CH_HEAT_DH_TECHS]
    + [f"ILLT_{r}_{t}" for r in _CH_HEAT_IL_REGIONS for t in _CH_HEAT_ILLT_TECHS]
    + [f"ILHT_{r}_{t}" for r in _CH_HEAT_IL_REGIONS for t in _CH_HEAT_ILHT_TECHS]
)


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
# Includes Swiss heat-providing technologies (CHP, EGS, HP, resistive, thermalNew).
INV_COST_PLANTS: List[str] = [
    "CH01_pvrf", "CH01_windon",
    "CH02_pvrf", "CH02_windon",
    "CH03_pvrf", "CH03_windon",
    "CH04_pvrf", "CH04_windon",
    "CH05_pvrf", "CH05_windon",
    "CH06_pvrf", "CH06_windon",
    "CH07_pvrf", "CH07_windon",
    "CH00_pvalpine",  # Alpine PV - investment candidate only
    "CH00_CCGTresmethane", "CH00_SCGTresmethane",
    "CH00_CCGTCCS", "CH00_SCGTfossil",
    "CH00_battery", "CH00_hydrogen",
    "CH00_oil", "CH00_nuclear",
] + CH_HEAT_PROVIDING_PLANTS

# Electricity-only set: pure CH electricity-providing plants.
# Used for the "Operational costs per unit of generated energy" metric, whose
# definition is strictly op-cost(electricity) / generated-electricity. Mixing
# heat-providing assets into either side of that ratio would distort it.
OP_COST_PLANTS_ELECTRICITY_ONLY: List[str] = [
    "CH00_battery", "CH00_CCGTCCS", "CH00_CCGTresmethane", "CH00_dam",
    "CH00_hydrogen", "CH00_nuclear", "CH00_oil", "CH00_psp_close",
    "CH00_SCGTfossil", "CH00_SCGTresmethane", "CH00_pvalpine",
    "CH01_battery", "CH01_biomass", "CH01_CCGTCCS", "CH01_other", "CH01_pvrf", "CH01_windon",
    "CH02_battery", "CH02_biomass", "CH02_CCGTCCS", "CH02_other", "CH02_pvrf", "CH02_windon",
    "CH03_battery", "CH03_biomass", "CH03_CCGTCCS", "CH03_nuclear", "CH03_other", "CH03_pvrf", "CH03_windon",
    "CH04_battery", "CH04_biomass", "CH04_CCGTCCS", "CH04_other", "CH04_pvrf", "CH04_windon",
    "CH05_battery", "CH05_biomass", "CH05_CCGTCCS", "CH05_other", "CH05_pvrf", "CH05_windon",
    "CH06_battery", "CH06_biomass", "CH06_CCGTCCS", "CH06_other", "CH06_pvrf", "CH06_windon",
    "CH07_battery", "CH07_biomass", "CH07_CCGTCCS", "CH07_other", "CH07_pvrf", "CH07_windon",
    "large_psp", "medium_reservior",
]

# Operation cost / emissions / gen plants (from respective CSVs where True).
# Includes Swiss heat-providing technologies (CHP, EGS, HP, resistive, thermalNew,
# PTES, TTES) for headline op-cost / emissions / generation totals.
OP_COST_PLANTS: List[str] = OP_COST_PLANTS_ELECTRICITY_ONLY + CH_HEAT_PROVIDING_PLANTS

# Emissions plants (same as OP_COST_PLANTS for CH)
EMISSIONS_PLANTS: List[str] = OP_COST_PLANTS.copy()

# Generation plants for total gen calculation (same as OP_COST_PLANTS for CH)
GEN_PLANTS: List[str] = OP_COST_PLANTS.copy()
GEN_PLANTS_ELECTRICITY_ONLY: List[str] = OP_COST_PLANTS_ELECTRICITY_ONLY.copy()


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


def _read_settings(scenario_name: str) -> pd.DataFrame:
    settings_path = PROJECT_ROOT / "output" / scenario_name / "settings.csv"
    return pd.read_csv(settings_path, index_col=0)


def _setting_value(scenario_name: str, key: str, subscenario: str = None):  # type: ignore
    """Return a setting value, choosing the column for `subscenario` if given.

    When subscenario is None, fall back to the first column (preserves prior behaviour
    for runs with a single subscenario).
    """
    df = _read_settings(scenario_name)
    row = df.loc[key]
    if subscenario is None:
        return row.iloc[0]
    if subscenario not in row.index:
        raise KeyError(
            f"Subscenario '{subscenario}' not found in settings.csv columns for '{scenario_name}'. "
            f"Available: {list(row.index)}"
        )
    return row[subscenario]


def get_run_year(scenario_name: str, subscenario: str = None) -> int:  # type: ignore
    """Get run_year from scenario settings.csv."""
    return int(_setting_value(scenario_name, "run_year", subscenario))


def get_flexible_household_heatpump_share(scenario_name: str, subscenario: str = None) -> float:  # type: ignore
    """Get flexible_household_heatpump_share from scenario settings.csv."""
    return float(_setting_value(scenario_name, "flexible_household_heatpump_share", subscenario))


def get_eu_policy(scenario_name: str, subscenario: str = None) -> str:  # type: ignore
    """Get eu_policy from scenario settings.csv."""
    return str(_setting_value(scenario_name, "eu_policy", subscenario))


def get_weather_year(scenario_name: str, subscenario: str = None) -> int:  # type: ignore
    """Get weather_year from scenario settings.csv."""
    return int(_setting_value(scenario_name, "weather_year", subscenario))


def get_subscenario_weight(scenario_name: str, subscenario: str) -> float:
    """Return the weight_in_objective_fcn for a specific subscenario."""
    return float(_setting_value(scenario_name, "weight_in_objective_fcn", subscenario))


def list_subscenarios(scenario_name: str) -> List[str]:
    """Return the subscenario names recorded in settings.csv (one per column)."""
    df = _read_settings(scenario_name)
    return list(df.columns)


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
    
    # Hourly columns are all columns except the descriptive and capacity columns.
    # Columns are: age_construction_group, heating_system_group, climate_zone_group,
    # TS_Type, then the hourly columns, then negative_capacity, positive_capacity, power_of_HP.
    # The 1995 files label the hours like '01.01.1995 00:00' (8760 hours), the 2008 files like
    # '2008-01-01 00:00:00' (8784 hours, leap year). As in the model import
    # (data_import_fcns), the hours are numbered t_1, t_2, ... in file order, so the
    # model period t_1 ... t_8760 uses the first 8760 hours.
    non_hourly_cols = {"age_construction_group", "heating_system_group", "climate_zone_group",
                       "TS_Type", "negative_capacity [MJ]", "positive_capacity [MJ]",
                       "power_of_HP [kW]"}
    hourly_cols = [c for c in el_data.columns if c not in non_hourly_cols]
    
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


# ============ SWISS CURTAILMENT ============

# Swiss cross-border lines and the neighbour at the other end.
# Flows are positive for imports into CH (HVAC_AT00_CH00 > 0 means AT00 -> CH00).
CH_LINE_NEIGHBOR = {
    "HVAC_AT00_CH00": "AT00",
    "HVAC_DE00_CH00": "DE00",
    "HVAC_FR00_CH00": "FR00",
    "HVAC_IT00_CH00": "IT00",
}

# Prices at or below this value (CHF/MWh) count as zero. Curtailment has no cost in FEM,
# so every curtailment hour has a Swiss price of zero up to the solver tolerance.
ZERO_PRICE_TOL = 0.01


def swiss_curtailment_hourly(df_curtailment: pd.DataFrame, df_dual: pd.DataFrame,
                             df_export: pd.DataFrame, tol: float = ZERO_PRICE_TOL) -> pd.DataFrame:
    """Hourly Swiss curtailment in MWh with a unique allocation in zero-price hours.

    FEM curtails only the exogenous infeed of CH00 (curtailment of CH00_fixedconsumer,
    i.e. run-of-river). Invested PV and wind always generate their full potential.

    If the Swiss price and the price of a neighbour are both zero, the model can move surplus
    across that border at no cost, so the split of curtailment between Switzerland and that
    neighbour is arbitrary. The Swiss value is made unique by letting Switzerland use its own
    generation first. In an hour with a zero Swiss price

        Swiss curtailment = max(0, raw curtailment + net export to neighbours at zero price)

    Net imports from neighbours at zero price lower the value, net exports to them raise it.
    Exports to neighbours with a positive price are used there and do not count. In hours
    with a positive Swiss price the raw curtailment is kept.

    Returns a DataFrame with the columns T, Scenarios, value (MWh).
    """
    cols = ["T", "Scenarios", "value"]
    if df_curtailment is None or df_curtailment.empty:
        return pd.DataFrame(columns=cols)
    cur = df_curtailment[df_curtailment["Consumer_with_infeed"] == "CH00_fixedconsumer"].copy()
    if cur.empty:
        return pd.DataFrame(columns=cols)
    cur["value"] = pd.to_numeric(cur["value"], errors="coerce").fillna(0.0)
    out = cur.groupby(["T", "Scenarios"])["value"].sum().rename("raw").to_frame()

    if df_dual is None or df_dual.empty or df_export is None or df_export.empty:
        out["value"] = out["raw"]
        return out.reset_index()[cols]

    nodes = ["CH00"] + list(CH_LINE_NEIGHBOR.values())
    du = df_dual[df_dual["Node"].isin(nodes)].copy()
    du["value"] = pd.to_numeric(du["value"], errors="coerce")
    prices = du.pivot_table(index=["T", "Scenarios"], columns="Node", values="value", aggfunc="mean")
    ex = df_export[df_export["lineATC"].isin(list(CH_LINE_NEIGHBOR))].copy()
    ex["value"] = pd.to_numeric(ex["value"], errors="coerce").fillna(0.0)
    flows = ex.pivot_table(index=["T", "Scenarios"], columns="lineATC", values="value", aggfunc="sum")

    # All hours with a price, so that zero-price exports also count where raw curtailment is missing
    out = prices.join(out, how="outer").join(flows, how="left")
    out["raw"] = out["raw"].fillna(0.0)
    if "CH00" in out.columns:
        zero_ch = out["CH00"].le(tol)
    else:
        zero_ch = pd.Series(False, index=out.index)
    net_export_zero = pd.Series(0.0, index=out.index)
    for line, node in CH_LINE_NEIGHBOR.items():
        if line in out.columns and node in out.columns:
            net_export_zero = net_export_zero - out[line].fillna(0.0).where(out[node].le(tol), 0.0)
    out["value"] = out["raw"].where(~zero_ch, (out["raw"] + net_export_zero).clip(lower=0.0))
    return out.reset_index()[cols]
