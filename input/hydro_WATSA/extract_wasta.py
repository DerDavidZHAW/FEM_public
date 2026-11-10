"""
Extract a tidy plant-level CSV from the BFE WASTA Excel file.

Reads the sheet "WASTA_01.01.2026_v2" of
"2025 Statistik der Wasserkraftanlagen der Schweiz_v2_1.1.2026.xlsx"
(one row per Zentrale, i.e. power house) and writes
"WASTA_2026_plants.csv" into the same folder, keeping the columns
needed to cluster Swiss hydro plants into representative model plants
(capacities, expected generation, pumping, heads, location, type).

See source.txt in this folder for the data source and the approach.

Run from anywhere:  python input/hydro_WATSA/extract_wasta.py
"""

from pathlib import Path

import pandas as pd

FOLDER = Path(__file__).parent
XLSX_FILE = FOLDER / "2025 Statistik der Wasserkraftanlagen der Schweiz_v2_1.1.2026.xlsx"
SHEET = "WASTA_01.01.2026_v2"
CSV_FILE = FOLDER / "WASTA_2026_plants.csv"

# WASTA column -> output column (English, snake_case, units kept in the name)
COLUMN_MAP = {
    "WASTA": "wasta_id",
    "Name Zentrale (ZE)": "plant_name",
    "Name Wasserkraftanlage (WKA)": "scheme_name",
    "Name Standort Zentrale": "location",
    "WKA Typ": "wka_type",
    "Kanton Standort Zentrale": "canton",
    "Staat Standort Zentrale": "country",
    # despite the [%] in the header, values are fractions 0-1 (1.0 = fully Swiss)
    "Anteil CH [%]": "ch_share",
    "Betriebsstatus Zentrale": "status",
    "Funktion Turbinieren": "has_turbine",
    "Funktion Pumpen": "has_pump",
    "installierte Leistung Turbinen [MW]": "turbine_capacity_MW",
    "Anteil CH Turbinen [MW] berechnet": "turbine_capacity_CH_MW",
    "maximale Leistung ab Generatoren [MW]": "generator_max_MW",
    "mittlere Produktionserwartung im Jahr [GWh]": "expected_gen_year_GWh",
    "davon im Winter [GWh]": "expected_gen_winter_GWh",
    "davon im Sommer [GWh]": "expected_gen_summer_GWh",
    "Anteil CH Produktion [GWh] berechnet": "expected_gen_year_CH_GWh",
    "installierte Leistung Pumpen [MW]": "pump_capacity_MW",
    "maximale Leistungsaufnahme der Motoren [MW]": "pump_motor_max_MW",
    "mittlerer Pumpenbedarf im Jahr [GWh]": "pump_demand_year_GWh",
    "davon im Winter [GWh].1": "pump_demand_winter_GWh",
    "davon im Sommer [GWh].1": "pump_demand_summer_GWh",
    "erste Inbetriebnahme [a]": "first_commissioning_year",
    "letzte Inbetriebnahme [a]": "last_commissioning_year",
    "Kote Turbinenachse [m.ü.M]": "turbine_axis_masl",
    "maximale Bruttofallhöhe [m]": "max_gross_head_m",
    "maximale Nettofallhöhe [m]": "max_net_head_m",
    "genutztes Gewässer 1": "main_water_body",
    "ZE-Koordinaten (E)": "coord_E",
    "ZE-Koordinaten (N)": "coord_N",
}

# WASTA plant type -> technology name used in the Future_Markets model.
# L  = Laufkraftwerk (run-of-river)                     -> ror
# S  = Speicherkraftwerk (storage/reservoir)            -> dam
# P  = Pumpzentrale (pump-only station, no turbine)     -> psp_open (pumping side)
# PS = Pumpspeicherkraftwerk (pump + turbine, open)     -> psp_open
# U  = Umwälzwerk (closed-loop pumped storage)          -> psp_close
TECH_MAP = {
    "L": "ror",
    "S": "dam",
    "P": "psp_open",
    "PS": "psp_open",
    "U": "psp_close",
}


def main():
    df = pd.read_excel(XLSX_FILE, sheet_name=SHEET)

    missing = [c for c in COLUMN_MAP if c not in df.columns]
    if missing:
        raise KeyError(f"Columns not found in {XLSX_FILE.name}: {missing}")

    out = df[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)

    out["model_tech"] = out["wka_type"].map(TECH_MAP)
    out["has_turbine"] = out["has_turbine"].eq("T")
    out["has_pump"] = out["has_pump"].eq("P")

    # keep all rows, but sort so the plants that matter most come first
    out = out.sort_values("turbine_capacity_MW", ascending=False)

    out.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")

    ch = out[out["country"] == "CH"]
    print(f"Wrote {len(out)} plants to {CSV_FILE.name}")
    print(f"  of which in CH: {len(ch)}")
    print(f"  CH turbine capacity: {ch['turbine_capacity_MW'].sum():,.0f} MW")
    print(f"  CH pump capacity:    {ch['pump_capacity_MW'].sum():,.0f} MW")
    print(f"  CH expected generation: {ch['expected_gen_year_GWh'].sum():,.0f} GWh/a")
    print("\nPlants by type (all rows):")
    print(out.groupby(["wka_type", "model_tech"], dropna=False).agg(
        n=("plant_name", "count"),
        turbine_MW=("turbine_capacity_MW", "sum"),
        pump_MW=("pump_capacity_MW", "sum"),
        gen_GWh=("expected_gen_year_GWh", "sum"),
    ).round(0).to_string())


if __name__ == "__main__":
    main()
