"""
Estimate the electric energy content [GWh] of Swiss storage lakes and
allocate it to WASTA plant chains.

Method (see source.txt):
  E_lake = volume * energy density,  density = rho*g*eta/3.6e6 per m head
         = 0.0023 kWh per m3 per m of head (eta = 0.85 assumed, absorbed
           by the regional calibration below)
  head   = lake surface level  -  turbine axis of the LOWEST plant in the
           cascade chain fed by the lake (captures multi-stage cascades
           without needing the full hydraulic topology)

Chains are found by matching lake names against the water bodies
("genutztes Gewaesser") of all WASTA plants, then expanding over plants
that share a scheme (WKA) name token (e.g. "Grimsel" links the high
Grimsel plants with WKA "Innertkirchen Grimsel" at 640 m a.s.l.).

The raw estimates are calibrated regionally (Wallis, Graubuenden, Tessin,
rest of CH) to the maximum usable energy content that the BFE publishes
weekly ("Fuellungsgrad der Speicherseen", open data ogd17), so the totals
match the official ~8.9 TWh by construction and the physics only decides
the split WITHIN each region.

Inputs (same folder):
  wiki_speicherseen.csv                      <- scrape_wiki_speicherseen.py
  manual_lakes.csv (optional)                <- lakes missing from the wiki
      list (e.g. Lago di Lei on Italian territory), columns:
      lake_name, canton, volume_Mm3, lake_level_masl
  2025 Statistik der Wasserkraftanlagen der Schweiz_v2_1.1.2026.xlsx
  ogd17_fuellungsgrad_speicherseen.csv       <- downloaded if missing
  lake_plant_overrides.csv (optional)        <- manual outlet fixes,
      columns: lake_name, outlet_plant_name (WASTA "Name Zentrale (ZE)").
      Overrides are applied BEFORE the cascade expansion, so the full
      chain of the override plant's scheme is still found (fixes e.g.
      Tseuzier -> Croix + St-Léonard instead of St-Léonard alone)

Output (same folder):
  storage_lakes_energy_2026.csv   one row per lake with matched chain,
                                  head, raw and calibrated energy [GWh]

Run from anywhere:  python input/hydro_WATSA/estimate_storage_energy.py
"""

import unicodedata
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

FOLDER = Path(__file__).parent
XLSX_FILE = FOLDER / "2025 Statistik der Wasserkraftanlagen der Schweiz_v2_1.1.2026.xlsx"
LAKES_FILE = FOLDER / "wiki_speicherseen.csv"
BFE_FILE = FOLDER / "ogd17_fuellungsgrad_speicherseen.csv"
BFE_URL = "https://www.uvek-gis.admin.ch/BFE/ogd/17/ogd17_fuellungsgrad_speicherseen.csv"
OVERRIDES_FILE = FOLDER / "lake_plant_overrides.csv"
MANUAL_LAKES_FILE = FOLDER / "manual_lakes.csv"
OUT_FILE = FOLDER / "storage_lakes_energy_2026.csv"

DENSITY_KWH_PER_M3_M = 0.0023  # rho*g*eta/3.6e6 with eta = 0.85
MIN_HEAD_M = 20.0  # below this a "match" is treated as implausible

# words that carry no identity when matching lake <-> water body names
NAME_STOPWORDS = {
    "lac", "lago", "lai", "lej", "lek", "stausee", "see", "bacino",
    "de", "des", "du", "di", "del", "della", "da", "d", "la", "le", "les",
    "il", "val", "valle", "mit", "zubringer", "ausgleichsbecken",
}
# words that carry no identity when linking plants via scheme (WKA) names
# (incl. railway operators: "SBB"/"CFF" would link the Etzelwerk to
# every other SBB plant, e.g. Rupperswil-Auenstein on the Aare)
WKA_STOPWORDS = {
    "kraftwerk", "kraftwerke", "centrale", "centrali", "usine", "usines",
    "forces", "motrices", "kw", "ag", "sa", "oberstufe", "unterstufe",
    "sbb", "cff", "ffs",
}
CANTON_REGION = {"Wallis": "Wallis", "Graubünden": "Graubuenden", "Tessin": "Tessin"}


def normalize(text):
    """lowercase, strip accents and stopwords -> set of identity tokens."""
    # split on apostrophes/hyphens BEFORE the ascii fold, which would
    # silently delete curly apostrophes and glue tokens together
    t = str(text).replace("’", " ").replace("'", " ").replace("-", " ")
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    tokens = set()
    for tok in t.split():
        if tok in NAME_STOPWORDS or len(tok) < 3:
            continue
        # Grimselsee -> grimsel, Wägitalersee -> waegitaler(see)
        if tok.endswith("see") and len(tok) > 6:
            tok = tok[:-3]
        tokens.add(tok)
    return tokens


def tokens_match(lake_tokens, gew_tokens):
    """True if any identity token of the lake appears in the water body
    name (exact or as prefix, so 'grimsel' matches 'grimselsee')."""
    for lt in lake_tokens:
        for gt in gew_tokens:
            if lt == gt or (len(lt) >= 5 and gt.startswith(lt)) or (
                len(gt) >= 5 and lt.startswith(gt)
            ):
                return True
            # spelling variants like Limmeren(see) vs Limmern
            if (
                min(len(lt), len(gt)) >= 6
                and SequenceMatcher(None, lt, gt).ratio() >= 0.85
            ):
                return True
    return False


def main():
    lakes = pd.read_csv(LAKES_FILE)
    if MANUAL_LAKES_FILE.exists():
        manual = pd.read_csv(MANUAL_LAKES_FILE)
        dupes = set(manual["lake_name"]) & set(lakes["lake_name"])
        if dupes:
            raise ValueError(f"manual_lakes.csv duplicates wiki lakes: {dupes}")
        lakes = pd.concat([lakes, manual], ignore_index=True)
        print(f"Added {len(manual)} manual lake(s): "
              + ", ".join(manual["lake_name"]))

    wasta = pd.read_excel(XLSX_FILE, sheet_name="WASTA_01.01.2026_v2")
    wasta = wasta[wasta["Betriebsstatus Zentrale"] != "ausser Betrieb"]
    gew_cols = [c for c in wasta.columns if c.startswith("genutztes Gew")]
    wasta["gew_tokens"] = wasta[gew_cols].apply(
        lambda row: [normalize(v) for v in row if pd.notna(v)], axis=1
    )
    wasta["wka_tokens"] = wasta["Name Wasserkraftanlage (WKA)"].map(
        lambda s: {t for t in normalize(s) if t not in WKA_STOPWORDS}
    )

    if not BFE_FILE.exists():
        print(f"Downloading BFE filling-level data to {BFE_FILE.name} ...")
        urllib.request.urlretrieve(BFE_URL, BFE_FILE)
    bfe = pd.read_csv(BFE_FILE)
    bfe_max = {
        region: bfe[f"{region}_max_speicherinhalt_gwh"].iloc[-1]
        for region in ["Wallis", "Graubuenden", "Tessin", "UebrigCH"]
    }

    # override syntax (lake_plant_overrides.csv, one row per rule):
    #   <lake>,<plant>   pin the lake's chain seed to this plant
    #   <lake>,DROP      remove the lake entirely (e.g. the historical
    #                    Lac de Barberine, submerged by Emosson 1975)
    #   <lake>,+<plant>  ADD this plant to the lake's chain after the
    #                    normal matching (for members the name/scheme
    #                    matching cannot find, e.g. Vernayaz CFF below
    #                    Emosson, whose water body is named "Pesseux")
    overrides, chain_adds = {}, {}
    if OVERRIDES_FILE.exists():
        ov = pd.read_csv(OVERRIDES_FILE)
        for _, r in ov.iterrows():
            v = str(r["outlet_plant_name"]).strip()
            if v.startswith("+"):
                chain_adds.setdefault(r["lake_name"], []).append(v[1:].strip())
            else:
                overrides[r["lake_name"]] = v
    drop = {k for k, v in overrides.items() if v == "DROP"}
    if drop:
        n0 = len(lakes)
        lakes = lakes[~lakes["lake_name"].isin(drop)].copy()
        print(f"Dropped {n0 - len(lakes)} lake(s) via DROP override: "
              + ", ".join(sorted(drop)))
    overrides = {k: v for k, v in overrides.items() if v != "DROP"}

    # ---- match every lake to a plant chain and compute head ----
    axis_col = "Kote Turbinenachse [m.ü.M]"
    records = []
    for _, lake in lakes.iterrows():
        lake_tokens = normalize(lake["lake_name"])
        # an override pins the lake to a plant; it seeds the chain BEFORE
        # the cascade expansion so the plant's whole scheme is picked up
        if lake["lake_name"] in overrides:
            direct = wasta[wasta["Name Zentrale (ZE)"] == overrides[lake["lake_name"]]]
            if direct.empty:
                raise KeyError(f"override plant not found: {overrides[lake['lake_name']]}")
        else:
            direct = wasta[
                wasta["gew_tokens"].map(
                    lambda gews: any(tokens_match(lake_tokens, g) for g in gews)
                )
            ]

        # expand over shared scheme-name tokens to capture full cascades
        chain = direct
        if len(direct):
            chain_tokens = set().union(*direct["wka_tokens"])
            if chain_tokens:
                chain = wasta[
                    wasta["wka_tokens"].map(lambda w: bool(w & chain_tokens))
                ]

        # additive overrides: append chain members matching cannot find
        if lake["lake_name"] in chain_adds:
            add = wasta[wasta["Name Zentrale (ZE)"].str.strip().isin(
                chain_adds[lake["lake_name"]])]
            if len(add) < len(chain_adds[lake["lake_name"]]):
                missing = set(chain_adds[lake["lake_name"]]) - set(
                    add["Name Zentrale (ZE)"].str.strip())
                raise KeyError(f"chain-add plant(s) not found: {missing}")
            chain = pd.concat([chain, add]).drop_duplicates(subset="WASTA")

        outlet_name, outlet_axis, head = None, float("nan"), float("nan")
        turb = chain[chain["Funktion Turbinieren"].eq("T") & chain[axis_col].notna()]
        if len(turb):
            outlet = turb.loc[turb[axis_col].idxmin()]
            outlet_name = outlet["Name Zentrale (ZE)"]
            outlet_axis = outlet[axis_col]
            head = lake["lake_level_masl"] - outlet_axis

        matched = pd.notna(head) and head >= MIN_HEAD_M
        records.append(
            {
                "lake_name": lake["lake_name"],
                "canton": lake["canton"],
                "region": CANTON_REGION.get(lake["canton"], "UebrigCH"),
                "volume_Mm3": lake["volume_Mm3"],
                "lake_level_masl": lake["lake_level_masl"],
                "matched": matched,
                "outlet_plant": outlet_name if matched else None,
                "outlet_axis_masl": outlet_axis if matched else float("nan"),
                "head_m": head if matched else float("nan"),
                "chain_plants": "; ".join(sorted(chain["Name Zentrale (ZE)"])) if matched else "",
                "chain_wka": "; ".join(sorted(chain["Name Wasserkraftanlage (WKA)"].dropna().unique())) if matched else "",
            }
        )

    df = pd.DataFrame(records)

    # ---- energy: physics estimate, regional fallback density, calibration ----
    df["density_kWh_m3"] = DENSITY_KWH_PER_M3_M * df["head_m"]
    df["E_raw_GWh"] = df["volume_Mm3"] * df["density_kWh_m3"]

    regional_density = (
        df[df["matched"]].groupby("region")
        .apply(lambda g: g["E_raw_GWh"].sum() / g["volume_Mm3"].sum())
    )
    fallback = ~df["matched"] & df["volume_Mm3"].notna()
    df.loc[fallback, "density_kWh_m3"] = df.loc[fallback, "region"].map(regional_density)
    df.loc[fallback, "E_raw_GWh"] = (
        df.loc[fallback, "volume_Mm3"] * df.loc[fallback, "density_kWh_m3"]
    )

    scale = {
        region: bfe_max[region] / df.loc[df["region"] == region, "E_raw_GWh"].sum()
        for region in bfe_max
    }
    df["calibration_factor"] = df["region"].map(scale)
    df["E_cal_GWh"] = df["E_raw_GWh"] * df["calibration_factor"]

    df = df.sort_values("E_cal_GWh", ascending=False)
    df.round(3).to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

    # ---- report ----
    print(f"Wrote {len(df)} lakes to {OUT_FILE.name}")
    print(f"matched via WASTA chain: {df['matched'].sum()}, "
          f"fallback (regional density): {fallback.sum()}")
    print("\nRegional calibration (raw physics estimate vs BFE max content):")
    for region in bfe_max:
        raw = df.loc[df["region"] == region, "E_raw_GWh"].sum()
        print(f"  {region:12s} raw {raw:7.0f} GWh -> BFE max {bfe_max[region]:6.0f} GWh"
              f"  (factor {scale[region]:.2f})")
    print(f"\nTotal calibrated: {df['E_cal_GWh'].sum():,.0f} GWh")
    print("\nTop 15 lakes:")
    cols = ["lake_name", "volume_Mm3", "head_m", "outlet_plant", "E_raw_GWh", "E_cal_GWh"]
    print(df.head(15)[cols].round(1).to_string(index=False))
    print("\nValidation anchors:")
    for name, expect in [
        ("Lac des Dix", "1500 GWh (SWV factsheet)"),
        ("Lac de Mauvoisin", "~630 GWh (order: 2nd largest, lit.)"),
        ("Muttsee", "35 GWh PSP loop only (SWV); full cascade to the "
                    "Linth valley is larger by design"),
    ]:
        row = df[df["lake_name"].str.contains(name.split()[-1], case=False)]
        if len(row):
            r = row.iloc[0]
            print(f"  {r['lake_name']:22s} est. {r['E_cal_GWh']:7.1f} GWh   vs {expect}")
    print("\nLargest unmatched lakes (fallback density used):")
    print(df[~df["matched"]].head(8)[["lake_name", "canton", "volume_Mm3", "E_cal_GWh"]]
          .round(1).to_string(index=False))


if __name__ == "__main__":
    main()
