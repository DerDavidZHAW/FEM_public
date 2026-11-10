"""
Validate hydro_plants_individual.csv -- internal invariants plus
external cross-checks against the JRC hydro-power database,
GloHydroRes v1, and a national water mass balance built from official
BFE statistics.

A. INTERNAL INVARIANTS (must all PASS; violations break the pipeline
   contract, not just plausibility):
   1. no duplicate wasta_id, no negative capacities/storage
   2. every plant exists in WASTA, country CH, not 'ausser Betrieb'
   3. type totals reproduce the WASTA sanity anchors
      (~17.1 GW turbines, ~4.0 GW pumps, ~37 TWh/a expected gen)
   4. total storage = BFE ogd17 maximum (8,895 GWh) and regional sums
      match storage_lakes_energy_2026.csv by construction
   5. ror storage ~ 0; no plant with E/P > 2 years (flag list)

B. EXTERNAL CROSS-CHECK vs JRC hydro-power database
   (https://github.com/energy-modelling-toolkit/hydro-power-database,
   file data/jrc-hydro-power-plant-database.csv, retrieved 2026-07-31,
   copy stored in validation/ for reproducibility).
   The 18 Swiss storage entries mix ACCOUNTING CONVENTIONS
   (full-cascade vs PSP-loop-only vs single-basin) and contain entity
   errors (e.g. 'Grimsel 3', never built), so three separate
   comparisons are made, from strong to weak:
   b1 CAPACITY  per plant, automated name matching (strong: both
      sources ultimately describe the same physical units)
   b2 VOLUME    JRC volume_Mm3 vs our lake volumes (strong where JRC
      has real values: validates the wiki/manual lake inputs)
   b3 STORAGE   energy vs our lake/cascade energies (weak: only
      comparable where conventions align; ratio + convention note)

C. EXTERNAL CROSS-CHECK vs GloHydroRes v1 (Sadlier et al. 2025,
   global hydropower-reservoir dataset, validation/GloHydroRes_vs1.csv,
   downloaded by the user 2026-08-03). Filter country == "Switzerland"
   (NOT a "CH" substring -- that also matches Chile). 249 Swiss plants.
   c1 CAPACITY per plant for the 40 largest STO/PS entries, automated
      token matching as in b1 (outliers are scheme-level multi-matches)
   c2 VOLUME   GloHydroRes res_vol_km3 x 1000 vs our lake volumes for
      all rows >= 10 Mio m3; 4 curated join fixes where the automated
      matcher hits a compensation basin of the same scheme (Albigna,
      Barberine->Emosson, Fionnay->Lac des Dix, Zervreila). Remaining
      misses are usable-vs-total-volume conventions (Poschiavo,
      Lungerersee) or attribution differences, listed in the CSV.

D. MASS BALANCE vs official BFE statistics (independent of WASTA):
   monthly natural inflow of the storage fleet estimated as
     ~ Delta SOC (ogd17, weekly filling levels interpolated to month
       starts) + Erzeugung_Speicherwerk (ogd35 monthly balance)
       - 0.7569 x Verbrauch_Speicherpumpen (ogd35),
   compared to the PECD CH00 weekly inflow spread to months, for 2008
   and 2009 (ogd17 starts in 2000, so 1995 cannot be checked). This
   validates the PECD LEVEL anchor and the pump-correction formula
   used for the inflow SPLIT with data the pipeline never touches.

Outputs (validation/):
  validation_summary.txt      PASS/FAIL list + cross-check tables
  jrc_capacity_check.csv      matched plants, MW ours vs JRC
  jrc_volume_storage_check.csv  the 18 JRC storage rows annotated
  jrc_capacity_scatter.png    log-log scatter ours vs JRC
  glohydrores_capacity_check.csv  matched plants, MW ours vs GloHydroRes
  glohydrores_volume_check.csv    reservoir volumes ours vs GloHydroRes
  mass_balance_check.csv      year, month, mass-balance vs PECD GWh
  mass_balance.png            monthly comparison figure 2008/2009

Usage:  python input/hydro_WATSA/validate_hydro_plants.py
"""

import re
import unicodedata
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

FOLDER = Path(__file__).parent
VAL = FOLDER / "validation"
JRC_FILE = VAL / "jrc-hydro-power-plant-database.csv"
PECD_FILE = (FOLDER.parent / "hydro_PECD"
             / "PECD_EERA2021_reservoir_pumping_2030_inflow.parquet")
if not PECD_FILE.exists():  # cloud run: staged location
    PECD_FILE = Path("/mnt/user-data/uploads/Future_Markets/input/"
                     "hydro_PECD/PECD_EERA2021_reservoir_pumping_2030_inflow.parquet")
OGD17_TOTAL_GWH = None  # read from ogd17 below

SURFACE, INK, INK_2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE, BLUE = "#e1e0d9", "#c3c2b7", "#2a78d6"

report = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    line = f"[{status}] {name}" + (f" -- {detail}" if detail else "")
    report.append(line)
    print(line)


def norm_tokens(s):
    t = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore")
    t = t.decode().lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    stop = {"de", "la", "le", "les", "des", "du", "di", "da", "im", "kw",
            "khr", "kwo", "ps", "gd", "ag", "sa", "power", "plant",
            "station", "stations", "hydroelectric", "pumped", "storage",
            "switzerland", "centrale", "usine", "produktion", "and",
            "1", "2", "3", "i", "ii"}
    return {w for w in t.split() if len(w) >= 3 and w not in stop}


def main():
    VAL.mkdir(exist_ok=True)
    pl = pd.read_csv(FOLDER / "hydro_plants_individual.csv")
    wa = pd.read_csv(FOLDER / "WASTA_2026_plants.csv")
    lakes = pd.read_csv(FOLDER / "storage_lakes_energy_2026.csv")
    ogd = pd.read_csv(FOLDER / "ogd17_fuellungsgrad_speicherseen.csv")
    target = float(ogd["TotalCH_max_speicherinhalt_gwh"].iloc[-1])

    # ---- A. internal invariants ----
    print("=== A. internal invariants ===")
    check("no duplicate wasta_id", pl.wasta_id.duplicated().sum() == 0)
    num = pl[["power_capacity_MW", "storage_capacity_GWh", "pump_capacity_MW"]]
    check("no negative values", (num.fillna(0) >= 0).all().all())
    w = pl.merge(wa[["wasta_id", "country", "status"]], on="wasta_id",
                 how="left")
    check("all plants found in WASTA", w.country.notna().all())
    check("all plants CH and in operation",
          ((w.country == "CH") & (w.status != "ausser Betrieb")).all())
    cap = pl.power_capacity_MW.sum()
    check("turbine capacity ~ WASTA anchor", abs(cap - 17_150) < 350,
          f"{cap:,.0f} MW (anchor ~17.1 GW)")
    pump = pl.pump_capacity_MW.sum()
    check("pump capacity ~ WASTA anchor", abs(pump - 4_000) < 300,
          f"{pump:,.0f} MW (anchor ~4.0 GW)")
    gen = pl.merge(wa[["wasta_id", "expected_gen_year_GWh"]],
                   on="wasta_id").expected_gen_year_GWh.sum()
    check("expected generation ~ WASTA anchor", abs(gen - 37_000) < 1_500,
          f"{gen:,.0f} GWh/a (anchor ~37 TWh)")
    sto = pl.storage_capacity_GWh.sum()
    check("total storage = BFE ogd17 maximum", abs(sto - target) < 2,
          f"{sto:,.0f} vs {target:,.0f} GWh")
    lk = lakes.E_cal_GWh.sum()
    check("lake energies sum to the same total", abs(lk - target) < 2,
          f"{lk:,.0f} GWh")
    ror_sto = pl.loc[pl.type == "ror", "storage_capacity_GWh"].sum()
    check("ror storage negligible", ror_sto < 40, f"{ror_sto:,.0f} GWh")
    size = pl[["power_capacity_MW", "pump_capacity_MW"]].max(axis=1)
    ep = 1000 * pl.storage_capacity_GWh / size.replace(0, np.nan)
    deep = pl[ep > 2 * 8760]
    check("no plant with E/P > 2 years", len(deep) == 0,
          "; ".join(deep.name) if len(deep) else "")

    # ---- B. external: JRC ----
    print("\n=== B. JRC hydro-power database cross-check ===")
    jrc = pd.read_csv(JRC_FILE)
    ch = jrc[jrc.country_code == "CH"].copy()

    # b1: capacity, automated token matching (JRC entries are often
    # scheme-level, so a JRC row may match SEVERAL of our plants; we
    # compare against the sum of matched plants)
    pl["tok"] = pl.name.map(norm_tokens)
    wa_scheme = wa.set_index("wasta_id").scheme_name
    pl["tok_scheme"] = pl.wasta_id.map(wa_scheme).map(norm_tokens)
    rows = []
    for _, j in ch.nlargest(60, "installed_capacity_MW").iterrows():
        jt = norm_tokens(j["name"])
        hit = pl[pl.apply(lambda r: bool(jt & r["tok"]) or
                          bool(jt & r["tok_scheme"]), axis=1)]
        if hit.empty:
            continue
        ours = hit.power_capacity_MW.sum()
        rows.append({"jrc_name": j["name"][:60],
                     "jrc_MW": j.installed_capacity_MW,
                     "ours_MW": round(ours, 1),
                     "ratio": round(ours / j.installed_capacity_MW, 2),
                     "n_matched": len(hit),
                     "matched": "; ".join(hit.name.head(4))})
    capchk = pd.DataFrame(rows)
    capchk.to_csv(VAL / "jrc_capacity_check.csv", index=False,
                  encoding="utf-8-sig")
    good = capchk[(capchk.ratio > 0.67) & (capchk.ratio < 1.5)]
    check("capacity within +/-50% for matched JRC entries",
          len(good) / len(capchk) > 0.7,
          f"{len(good)}/{len(capchk)} within band (token matching is "
          "scheme-level, mismatches listed in jrc_capacity_check.csv)")

    # b2 + b3: the 18 storage rows -- CURATED mapping. JRC names are
    # scheme-level and its storage energies mix at least three
    # accounting conventions (full-cascade / PSP-loop-only /
    # single-basin) plus entity errors, so each row carries an
    # explicit comparison class:
    #   comparable        same convention, energy ratio is meaningful
    #   convention        JRC uses loop/basin accounting, ours values
    #                     the water to the lowest cascade stage --
    #                     energies differ BY DESIGN, volumes still check
    #   entity_mismatch   JRC row describes a different object
    #   jrc_error         JRC entry is wrong (e.g. 'Grimsel 3', never
    #                     built; Grimselsee with 700 Mio m3)
    CURATED = [  # (jrc substring, [our lakes], class, note)
        ("Grande Dixence", ["Lac des Dix", "Lac de Cleuson"],
         "comparable", "full-cascade in both"),
        ("Bitsch", ["Gibidum Stausee"], "comparable", "single stage"),
        ("Etzelwerk", ["Sihlsee"], "comparable",
         "our value after regional calibration (x0.78); raw physics"
         " estimate ~105 GWh matches JRC"),
        ("Veytaux", ["Lac de l’Hongrin"], "comparable",
         "Hongrin-Leman drop"),
        ("FERRERA", ["Lago di Lei"], "convention",
         "JRC ~loop accounting; ours full cascade to Sils"),
        ("Limmern+Hintersand", ["Muttsee"], "convention",
         "JRC 34 GWh = PSP loop (SWV: 35); ours full cascade"),
        ("Nant drance", ["Lac du Vieux Emosson"], "convention",
         "JRC 20 GWh = PSP loop; ours full drop to the valley"),
        ("Grimsel KWO ProduktionPS - Grimsel 2",
         ["Grimselsee", "Oberaarsee"], "jrc_error",
         "JRC volume 700 Mio m3 is wrong (Grimselsee ~100)"),
        ("Grimsel 3", [], "jrc_error", "plant was never built"),
        ("Tierfehd limmern", ["Limmerensee"], "convention",
         "JRC 0.7 GWh implausible; volume checks (92 vs 93)"),
        ("Innertkirchen 1", ["Räterichs­bodensee"], "convention",
         "KWO cascade share"),
        ("Robiei", ["Lago di Robièi", "Lago del Zött",
                    "Lago dei Cavagnöö"], "entity_mismatch",
         "JRC volume 126 unclear; JRC 6.5 GWh ~ loop"),
        ("Châtelard - Barberine", ["Lac d’Emosson"], "entity_mismatch",
         "Barberine submerged by Emosson 1975 (we DROP the old lake)"),
        ("Mapragg", ["Gigerwaldsee"], "entity_mismatch",
         "JRC 3.34 Mio m3 = Mapragg basin only"),
        ("Mottec", ["Lac de Moiry"], "convention",
         "JRC 0.22 GWh = basin only; volume checks (77 vs 78)"),
        ("Wägital", ["Wägitalersee"], "entity_mismatch",
         "JRC row = Rempen basin (0.5 Mio m3), not the lake"),
        ("Sambuco", ["Lago del Sambuco"], "convention",
         "JRC 0.11 GWh = basin only; volume checks (64 vs 64)"),
        ("Handeck isogyre", [], "convention", "PSP loop basin only"),
    ]
    srows = []
    for _, j in ch[ch.storage_capacity_MWh.notna()].iterrows():
        entry = next((c for c in CURATED if c[0].lower()
                      in str(j["name"]).lower()), None)
        our = lakes[lakes.lake_name.isin(entry[1])] if entry else \
            lakes.iloc[0:0]
        srows.append({
            "jrc_name": j["name"][:55],
            "class": entry[2] if entry else "unmapped",
            "jrc_volume_Mm3": j.volume_Mm3,
            "our_volume_Mm3": round(our.volume_Mm3.sum(), 1)
            if len(our) else "",
            "jrc_storage_GWh": round(j.storage_capacity_MWh / 1000, 1),
            "our_storage_GWh": round(our.E_cal_GWh.sum(), 1)
            if len(our) else "",
            "our_lakes": "; ".join(entry[1]) if entry else "",
            "note": entry[3] if entry else "",
        })
    stochk = pd.DataFrame(srows)
    stochk.to_csv(VAL / "jrc_volume_storage_check.csv", index=False,
                  encoding="utf-8-sig")

    vol = stochk[(stochk["class"] != "jrc_error")
                 & stochk.jrc_volume_Mm3.notna()
                 & (stochk.our_volume_Mm3 != "")
                 & (stochk["class"] != "entity_mismatch")].copy()
    vol["vr"] = vol.our_volume_Mm3.astype(float) / vol.jrc_volume_Mm3
    vgood = vol[(vol.vr > 0.75) & (vol.vr < 1.3)]
    check("reservoir volumes agree with JRC (curated, excl. JRC errors"
          " and entity mismatches)",
          len(vgood) >= 6,
          f"{len(vgood)}/{len(vol)} within +/-25-30%: "
          + ", ".join(f"{r.our_lakes.split(';')[0]} "
                      f"{r.our_volume_Mm3}/{r.jrc_volume_Mm3}"
                      for r in vgood.itertuples()))
    comp = stochk[stochk["class"] == "comparable"].copy()
    comp = comp[comp.our_storage_GWh != ""]
    comp["er"] = comp.our_storage_GWh.astype(float) / comp.jrc_storage_GWh
    egood = comp[(comp.er > 0.6) & (comp.er < 1.4)]
    check("storage energies agree with JRC where conventions align",
          len(egood) == len(comp),
          "; ".join(f"{r.our_lakes.split(';')[0]}: "
                    f"{r.our_storage_GWh} vs {r.jrc_storage_GWh} GWh"
                    for r in comp.itertuples()))

    # ---- C. external: GloHydroRes v1 ----
    print("\n=== C. GloHydroRes v1 cross-check ===")
    glo = pd.read_csv(VAL / "GloHydroRes_vs1.csv")
    # country == "Switzerland" exactly; a "CH" substring also matches Chile
    glo = glo[glo.country == "Switzerland"].copy()

    # c1: per-plant capacity, top-40 STO/PS entries (same token matcher
    # as the JRC check; multi-scheme token hits are expected outliers)
    rows = []
    for _, g in glo[glo.plant_type.isin(["STO", "PS"])] \
            .nlargest(40, "capacity_mw").iterrows():
        gt = norm_tokens(g["name"])
        hit = pl[pl.apply(lambda r: bool(gt & r["tok"]) or
                          bool(gt & r["tok_scheme"]), axis=1)]
        if hit.empty:
            continue
        ours = hit.power_capacity_MW.sum()
        rows.append({"glo_name": g["name"][:60],
                     "glo_MW": g.capacity_mw,
                     "ours_MW": round(ours, 1),
                     "ratio": round(ours / g.capacity_mw, 2),
                     "n_matched": len(hit),
                     "matched": "; ".join(hit.name.head(4))})
    gcap = pd.DataFrame(rows)
    gcap.to_csv(VAL / "glohydrores_capacity_check.csv", index=False,
                encoding="utf-8-sig")
    ggood = gcap[(gcap.ratio > 0.67) & (gcap.ratio < 1.5)]
    check("capacity within +/-50% for matched GloHydroRes entries",
          len(ggood) / len(gcap) > 0.7,
          f"{len(ggood)}/{len(gcap)} within band (outliers are "
          "scheme-level token multi-matches, see CSV)")

    # c2: reservoir volumes, res_vol_km3 >= 0.01 (10 Mio m3). The
    # automated matcher joins via res_name/dam_name/plant tokens; four
    # curated fixes where it lands on a compensation basin of the same
    # scheme instead of the head reservoir:
    GLO_LAKE_FIX = {"albigna": ["Albignasee"],
                    "barberine": ["Lac d’Emosson"],
                    "dixence": ["Lac des Dix"],
                    "zervreila": ["Zervreilasee"]}
    GENERIC = {"lac", "lago", "lagh", "lai", "lej", "lake", "see",
               "stausee", "bacino", "compenso"}   # never match on these
    lake_tok = lambda s: norm_tokens(s) - GENERIC
    lakes["tok"] = lakes.lake_name.map(lake_tok)
    rows = []
    for _, g in glo[glo.res_vol_km3.fillna(0) >= 0.01].iterrows():
        fix = next((v for k, v in GLO_LAKE_FIX.items()
                    if k in str(g["name"]).lower()), None)
        if fix:
            hit = lakes[lakes.lake_name.isin(fix)]
        else:
            gt = (lake_tok(g.res_name) | lake_tok(g.dam_name)
                  | lake_tok(g["name"]))
            hit = lakes[lakes.tok.map(lambda t: bool(gt & t))]
        if hit.empty:
            continue
        ours = hit.volume_Mm3.sum()
        rows.append({"glo_name": g["name"][:45],
                     "glo_res": str(g.res_name)[:30],
                     "glo_Mm3": round(g.res_vol_km3 * 1000, 1),
                     "our_Mm3": round(ours, 1),
                     "ratio": round(ours / (g.res_vol_km3 * 1000), 2),
                     "our_lakes": "; ".join(hit.lake_name.head(3)),
                     "curated_join": bool(fix)})
    gvol = pd.DataFrame(rows)
    gvol.to_csv(VAL / "glohydrores_volume_check.csv", index=False,
                encoding="utf-8-sig")
    vgood2 = gvol[(gvol.ratio > 0.75) & (gvol.ratio < 1.3)]
    check("reservoir volumes agree with GloHydroRes",
          len(vgood2) / len(gvol) > 0.7,
          f"{len(vgood2)}/{len(gvol)} within +/-25-30% (misses are "
          "usable-vs-total conventions or attribution, see CSV)")

    # ---- D. mass balance vs official BFE statistics ----
    print("\n=== D. national mass balance (ogd17 + ogd35 vs PECD) ===")
    PUMP_RT = 0.87 * 0.87
    o17 = pd.read_csv(FOLDER / "ogd17_fuellungsgrad_speicherseen.csv",
                      parse_dates=["Datum"])
    soc = o17.set_index("Datum").TotalCH_speicherinhalt_gwh
    o35 = pd.read_csv(
        VAL / "ogd35_schweizerische_elektrizitaetsbilanz_monatswerte.csv")
    pecd = pd.read_parquet(PECD_FILE)
    pecd["year"] = pecd.year.astype(int)
    mb_rows, mb_res = [], {}
    for y in [2008, 2009]:   # ogd17 starts 2000 -> 1995 not checkable
        idx = pd.date_range(f"{y}-01-01", f"{y + 1}-01-01", freq="MS")
        soc_m = soc.resample("D").interpolate("time").reindex(idx)
        dsoc = soc_m.diff().dropna().to_numpy()
        m35 = o35[o35.Jahr == y].set_index("Monat").sort_index()
        mb = (dsoc + m35.Erzeugung_Speicherwerk_GWh.to_numpy()
              - PUMP_RT * m35.Verbrauch_Speicherpumpen_GWh.to_numpy())
        a = pecd[(pecd.area_name == "CH00")
                 & (pecd.technology == "pumped_open") & (pecd.year == y)]
        a = (a.assign(week=a.Week.astype(int)).set_index("week")
             .inflow_GWh.reindex(range(1, 54)).fillna(0))
        days = pd.date_range(f"{y}-01-01", f"{y}-12-31", freq="D")
        wk = (days.dayofyear - 1) // 7 + 1
        nd = pd.Series(wk).value_counts().sort_index()
        p_m = (pd.Series([a[w] / nd[w] for w in wk], index=days)
               .resample("MS").sum().to_numpy())
        for i in range(12):
            mb_rows.append({"year": y, "month": i + 1,
                            "mass_balance_GWh": round(float(mb[i]), 1),
                            "pecd_GWh": round(float(p_m[i]), 1)})
        ratio = mb.sum() / p_m.sum()
        corr = float(np.corrcoef(mb, p_m)[0, 1])
        mb_res[y] = (mb, p_m)
        check(f"mass-balance annual inflow ~ PECD ({y})",
              0.85 < ratio < 1.15,
              f"{mb.sum():,.0f} vs {p_m.sum():,.0f} GWh (ratio {ratio:.2f})")
        check(f"mass-balance monthly shape ~ PECD ({y})", corr > 0.9,
              f"correlation {corr:.2f}")
    pd.DataFrame(mb_rows).to_csv(VAL / "mass_balance_check.csv",
                                 index=False, encoding="utf-8-sig")

    # mass-balance figure
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), facecolor=SURFACE,
                             constrained_layout=True, sharey=True)
    for ax, y in zip(axes, [2008, 2009]):
        mb, p_m = mb_res[y]
        ax.set_facecolor(SURFACE)
        for s in ax.spines.values():
            s.set_color(BASELINE)
        ax.tick_params(colors=MUTED, labelsize=9)
        ax.grid(True, axis="y", color=GRID, lw=0.8, zorder=0)
        x = np.arange(1, 13)
        ax.plot(x, p_m, color=BLUE, lw=2.2, zorder=3, label="PECD CH00")
        ax.plot(x, mb, color="#eb6834", lw=2.2, ls="--", zorder=3,
                label="BFE mass balance")
        ax.set_xticks(x)
        ax.set_title(str(y), color=INK, fontsize=11, loc="left")
        ax.set_xlabel("month", color=INK_2, fontsize=10)
    axes[0].set_ylabel("natural inflow [GWh/month]", color=INK_2,
                       fontsize=10)
    axes[0].legend(frameon=False, fontsize=9, labelcolor=INK_2)
    fig.suptitle("Storage-fleet natural inflow: BFE mass balance "
                 "(ΔSOC + storage gen − 0.757 × pumping) vs PECD",
                 color=INK, fontsize=12, x=0.01, ha="left")
    fig.savefig(VAL / "mass_balance.png", dpi=150, facecolor=SURFACE,
                bbox_inches="tight")
    plt.close(fig)

    # capacity scatter
    fig, ax = plt.subplots(figsize=(7.6, 7), facecolor=SURFACE,
                           constrained_layout=True)
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.plot([5, 3000], [5, 3000], color=BASELINE, lw=1.2, zorder=2)
    ax.scatter(capchk.jrc_MW, capchk.ours_MW, s=34, c=BLUE, alpha=0.85,
               edgecolors=SURFACE, linewidths=0.8, zorder=3)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.grid(True, which="major", color=GRID, lw=0.8, zorder=0)
    ax.set_xlabel("JRC installed capacity [MW]", color=INK_2, fontsize=10)
    ax.set_ylabel("our matched plant(s) capacity [MW]", color=INK_2,
                  fontsize=10)
    ax.set_title("Capacity cross-check vs JRC hydro-power database\n"
                 "one dot per JRC entry (scheme level, may match several "
                 "of our plants); diagonal = agreement",
                 color=INK, fontsize=12, loc="left", pad=12)
    fig.savefig(VAL / "jrc_capacity_scatter.png", dpi=150,
                facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)

    (VAL / "validation_summary.txt").write_text(
        "validate_hydro_plants.py -- summary\n"
        "====================================\n" + "\n".join(report) + "\n",
        encoding="utf-8-sig")
    n_fail = sum(1 for r in report if r.startswith("[FAIL]"))
    print(f"\n{len(report) - n_fail}/{len(report)} checks passed; "
          f"outputs in {VAL.name}/")


if __name__ == "__main__":
    main()
