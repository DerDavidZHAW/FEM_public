"""Loader for high-resolution per-plant PV data (Nexus-E format).

Single source of truth for where the data comes from. Both
read_RES_avail_data() and read_plant_non_hydro_data() call this helper
from inside an `if high_resolution_PV:` branch at the existing
PV read sites.
"""
import os
import functools
import pandas as pd

PV_DIR = os.path.join("input", "RES_nexuse", "PV")


def _sanitize(name: str) -> str:
    return name.replace("-", "_")


def plant_id(gen_name: str) -> str:
    return f"CH00_{_sanitize(gen_name)}_pvrf"


def _resolve_weather_folder(weather_year):
    """Return the folder for `weather_year`, or raise if not present."""
    folder = os.path.join(PV_DIR, str(weather_year))
    if not os.path.isdir(folder):
        if os.path.isdir(PV_DIR):
            available = sorted(
                d for d in os.listdir(PV_DIR)
                if os.path.isdir(os.path.join(PV_DIR, d))
            )
        else:
            available = []
        raise FileNotFoundError(
            f"[high_res_PV] No data folder for weather_year={weather_year} "
            f"under {PV_DIR}. Available: {available}. "
            f"Either provide the data or turn high_resolution_PV off."
        )
    return folder


def _resolve_run_year(profiles: pd.DataFrame, run_year):
    """Return the closest available profile-year to `run_year`.

    If `run_year` is present in the CSV, return it unchanged. Otherwise pick
    the year minimising absolute difference (ties broken by smaller year) and
    print a substitution-notice log line.
    """
    available = sorted(int(y) for y in profiles["year"].unique())
    if int(run_year) in available:
        return int(run_year)
    closest = min(available, key=lambda y: (abs(y - int(run_year)), y))
    print(
        f"[high_res_PV] requested run_year={run_year} not present in profile CSV; "
        f"using closest available year={closest} (available: {available})"
    )
    return closest


@functools.lru_cache(maxsize=8)
def load_high_res_PV(weather_year, run_year):
    """
    Load per-plant PV data for the given weather and run year.

    Returns
    -------
    plant_records : pd.DataFrame
        Indexed by plant_id, columns matching plants_invest_candidates_res_CH.csv
        schema (node, market, plant_type, tech, upperwn, lowerwn, eta, eta_pump,
        n_redispatch, gen_max_limit, energy_max_limit, fuel_switching).
    avail : dict
        {(plant_id, "t_<h>"): availability_factor in [0, 1]}
    """
    folder = _resolve_weather_folder(weather_year)

    # --- units --------------------------------------------------------------
    units = pd.read_excel(os.path.join(folder, "NewUnits.xlsx"))
    units = units[units["Technology"] == "PV-roof"].copy()
    units = units[units["Pmax"] > 0][["GenName", "Pmax"]]
    units["plant_id"] = units["GenName"].map(plant_id)

    # --- profiles -----------------------------------------------------------
    profiles = pd.read_csv(os.path.join(folder, "NexusInput_profiles_newPV_mv.csv"))
    resolved_year = _resolve_run_year(profiles, run_year)
    profiles = profiles[profiles["year"] == resolved_year]

    hour_cols = [str(h) for h in range(1, 8761)]
    profiles = profiles[["Name"] + hour_cols]

    # --- inner-join ---------------------------------------------------------
    merged = units.merge(profiles, left_on="GenName", right_on="Name", how="inner")
    dropped_units = len(units) - len(merged)
    dropped_profiles = len(profiles) - len(merged)
    if dropped_units or dropped_profiles:
        print(
            f"[high_res_PV] dropped {dropped_units} unit(s) without profile, "
            f"{dropped_profiles} profile(s) without unit"
        )

    # --- scale to availability factor ---------------------------------------
    af = merged[hour_cols].div(merged["Pmax"].values, axis=0).clip(lower=0.0, upper=1.0)
    af.index = merged["plant_id"].values

    # --- build avail dict ---------------------------------------------------
    avail = {
        (pid, f"t_{int(h)}"): float(af.at[pid, h])
        for pid in af.index
        for h in hour_cols
    }

    # --- build plant_records ------------------------------------------------
    n = len(merged)
    plant_records = pd.DataFrame({
        "node":             ["CH00"] * n,
        "market":           ["CH00"] * n,
        "plant_type":       ["RES"] * n,
        "tech":             ["pvrf"] * n,
        "upperwn":          [float("nan")] * n,
        "lowerwn":          [float("nan")] * n,
        "eta":              [float("nan")] * n,
        "eta_pump":         [float("nan")] * n,
        "n_redispatch":     ["CH00"] * n,
        "gen_max_limit":    merged["Pmax"].astype(float).values,
        "energy_max_limit": [float("inf")] * n,
        "fuel_switching":   [float("nan")] * n,
    }, index=merged["plant_id"].values)
    plant_records.index.name = "index"

    total_pmax_gw = merged["Pmax"].sum() / 1000.0
    print(
        f"[high_res_PV] loaded {len(merged)} PV-roof units, "
        f"sum Pmax = {total_pmax_gw:.2f} GW "
        f"(weather_year={weather_year}, profile_year={resolved_year})"
    )

    return plant_records, avail
