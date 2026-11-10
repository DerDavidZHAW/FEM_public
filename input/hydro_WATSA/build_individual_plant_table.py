"""
Build the final per-plant table: every Swiss hydro plant with an index,
name, type, power capacity and allocated storage energy.

Inputs (same folder):
  WASTA_2026_plants.csv           <- extract_wasta.py
  storage_lakes_energy_2026.csv   <- estimate_storage_energy.py

Storage allocation: each lake's calibrated energy is split among the
turbine plants of its cascade chain that lie BELOW the lake level,
proportionally to each stage's own head (energy per m3 at a stage scales
with that stage's head). Plant totals are then rescaled per region
(Wallis, Graubuenden, Tessin, UebrigCH) so the regional sums match the
BFE maximum usable content exactly, which also redistributes the energy
of the few small lakes that have no plant match.

Output (same folder):
  hydro_plants_individual.csv
      idx, name, type (ror/dam/psp_open/psp_close, the WASTA physical
      classification -- never overwritten), category (the MODEL
      treatment: equal to type, except storage-capable plants with
      turbines but E/P < MIN_STORAGE_HOURS -- zero OR near-zero
      storage relative to size -- are set to "ror" = fixed infeed;
      e.g. Hopflauenen Trift, Innertkirchen 2, Isenthal Bolzbach,
      Engeweiher: daily basins, no seasonal storage; their few MW of
      pumps are dropped with the reclassification, reported below),
      power_capacity_MW (turbines), storage_capacity_GWh (0 for
      non-storage plants), pump_capacity_MW, wasta_id, canton.
      Pump-ONLY stations (no turbine) keep their psp category so the
      national pump capacity stays complete.

Run from anywhere:  python input/hydro_WATSA/build_individual_plant_table.py
"""

from pathlib import Path

import pandas as pd

FOLDER = Path(__file__).parent
PLANTS_FILE = FOLDER / "WASTA_2026_plants.csv"
LAKES_FILE = FOLDER / "storage_lakes_energy_2026.csv"
OUT_FILE = FOLDER / "hydro_plants_individual.csv"

CANTON_REGION = {"VS": "Wallis", "GR": "Graubuenden", "TI": "Tessin"}

# storage-capable plants (dam/psp) with turbines but less than this
# many hours of storage (E/P) are treated as run-of-river in the model;
# the RELATIVE threshold also catches near-zero cases, not just E = 0
MIN_STORAGE_HOURS = 24.0


def main():
    plants = pd.read_csv(PLANTS_FILE)
    plants = plants[
        (plants["country"] == "CH") & (plants["status"] != "ausser Betrieb")
    ].copy()
    plants["name_key"] = plants["plant_name"].str.strip()
    plants["stage_head_m"] = plants["max_net_head_m"].fillna(plants["max_gross_head_m"])
    plants = plants.set_index("name_key")

    lakes = pd.read_csv(LAKES_FILE)

    # ---- split each lake's energy over its cascade chain ----
    storage_GWh = pd.Series(0.0, index=plants.index)
    for _, lake in lakes[lakes["matched"] & lakes["E_cal_GWh"].notna()].iterrows():
        chain = [p.strip() for p in str(lake["chain_plants"]).split(";") if p.strip()]
        chain = [p for p in chain if p in plants.index]
        stages = plants.loc[chain]
        # only turbine stages below the lake surface can use its water
        stages = stages[
            stages["has_turbine"]
            & stages["stage_head_m"].notna()
            & (stages["turbine_axis_masl"] < lake["lake_level_masl"])
        ]
        # storage belongs to the storage-type plants of the chain; cascade
        # stages classified as run-of-river keep 0 (the model treats them
        # as fixed infeed). Fall back to all stages only if the chain has
        # no storage-type plant at all.
        storage_stages = stages[stages["model_tech"] != "ror"]
        if len(storage_stages):
            stages = storage_stages
        if stages.empty:
            continue
        shares = stages["stage_head_m"] / stages["stage_head_m"].sum()
        storage_GWh.loc[shares.index] += lake["E_cal_GWh"] * shares

    plants["storage_capacity_GWh"] = storage_GWh

    # ---- rescale regionally so plant totals match the BFE maxima ----
    plants["region"] = plants["canton"].map(CANTON_REGION).fillna("UebrigCH")
    region_target = (
        lakes.assign(region=lakes["region"]).groupby("region")["E_cal_GWh"].sum()
    )
    for region, target in region_target.items():
        allocated = plants.loc[plants["region"] == region, "storage_capacity_GWh"].sum()
        if allocated > 0:
            plants.loc[plants["region"] == region, "storage_capacity_GWh"] *= (
                target / allocated
            )

    # ---- final table ----
    out = plants.reset_index(drop=True)[
        [
            "plant_name",
            "model_tech",
            "turbine_capacity_MW",
            "storage_capacity_GWh",
            "pump_capacity_MW",
            "wasta_id",
            "canton",
        ]
    ].rename(
        columns={
            "plant_name": "name",
            "model_tech": "type",
            "turbine_capacity_MW": "power_capacity_MW",
        }
    )
    out["name"] = out["name"].str.strip()

    # ---- model category: zero or NEAR-zero storage plants act as ror ----
    size = out[["power_capacity_MW", "pump_capacity_MW"]].max(axis=1)
    storage_hours = (
        1000 * out["storage_capacity_GWh"] / size.replace(0, pd.NA)
    ).fillna(0)
    out["category"] = out["type"]
    reclass = (
        out["type"].isin(["dam", "psp_open", "psp_close"])
        & (out["power_capacity_MW"] > 0)
        & (storage_hours < MIN_STORAGE_HOURS)
    )
    out.loc[reclass, "category"] = "ror"
    # pump-ONLY stations (WASTA type P: no turbine, intra-cascade
    # transfer pumps like Cleuson -> Dix): excluded from the clusters.
    # Their lifted water is already contained in the downstream plants'
    # WASTA production expectations; modelling their pumps as market
    # pumping would misrepresent scheduled transfers as price arbitrage.
    pump_only = (out["power_capacity_MW"] <= 0) & (out["pump_capacity_MW"] > 0)
    out.loc[pump_only, "category"] = "pump_station"

    out = out[
        ["name", "type", "category", "power_capacity_MW",
         "storage_capacity_GWh", "pump_capacity_MW", "wasta_id", "canton"]
    ]
    out = out.sort_values(
        ["storage_capacity_GWh", "power_capacity_MW"], ascending=False
    ).reset_index(drop=True)
    out.insert(0, "idx", out.index + 1)
    out["storage_capacity_GWh"] = out["storage_capacity_GWh"].round(2)
    out.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

    print(f"Wrote {len(out)} plants to {OUT_FILE.name}")
    print(f"Total storage: {out['storage_capacity_GWh'].sum():,.0f} GWh")
    print(f"Total turbine capacity: {out['power_capacity_MW'].sum():,.0f} MW")
    ps = out[out["category"] == "pump_station"]
    if len(ps):
        print(f"\nPump-only transfer stations (excluded from clusters): "
              f"{len(ps)} stations, {ps.pump_capacity_MW.sum():,.0f} MW pumps")
    rc = out[(out["type"] != out["category"])
             & (out["category"] != "pump_station")]
    if len(rc):
        print(f"\nReclassified to category 'ror' "
              f"(E/P < {MIN_STORAGE_HOURS} h, incl. near-zero):")
        print(rc[["name", "type", "power_capacity_MW", "storage_capacity_GWh",
                  "pump_capacity_MW"]].to_string(index=False))
        print(f"  -> {rc.power_capacity_MW.sum():,.1f} MW turbines become "
              f"fixed infeed; {rc.pump_capacity_MW.sum():,.1f} MW pumps are "
              "dropped from the storage clusters (negligible nationally)")
    print("\nBy category:")
    print(
        out.groupby("category").agg(
            n=("idx", "count"),
            power_MW=("power_capacity_MW", "sum"),
            pump_MW=("pump_capacity_MW", "sum"),
            storage_GWh=("storage_capacity_GWh", "sum"),
        ).round(0).to_string()
    )
    print("\nTop 15 by storage:")
    print(out.head(15).drop(columns="wasta_id").to_string(index=False))


if __name__ == "__main__":
    main()
