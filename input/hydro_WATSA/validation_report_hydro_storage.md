# Validation report — storage allocation of large Swiss hydro plants

Date: 2026-07-30. Scope: every S-type (reservoir) plant in `hydro_plants_individual.csv` with more than 10 MW and less than 24 h of allocated storage (E/P), i.e. plants that would have entered the model as reservoir plants without a reservoir.

## 1. Findings

| Plant | P (MW) | Storage before | Cause |
|---|---|---|---|
| Bitsch (Electra-Massa) | 340 | 0.00 GWh | Spelling mismatch. WASTA calls the reservoir "Stausee Gebidem", the Wikipedia lake list "Gibidum Stausee" (9.2 Mio m³, 1428 m ü.M., which was in the list all along). The fuzzy token match (threshold 0.85) does not bridge Gebidem/Gibidum. |
| Sils KHR | 250 | 0.18 GWh | Missing lakes. The KHR cascade is fed by Lago di Lei (197 Mio m³, 1931 m), Sufnersee (16 Mio m³, 1401 m) and Stausee Bärenburg (1 Mio m³, 1080 m). Lago di Lei lies on Italian territory and is therefore not in the Wikipedia list "Speicherseen in der Schweiz"; Sufnersee and Bärenburg are simply absent. In addition the WASTA water bodies of these plants are "Hinterrhein/Averserrhein", so name matching could never work. |
| Bärenburg | 221 | 0.17 GWh | Same as Sils KHR. |
| Ferrera 1 (psp_open) | 180 | 0.28 GWh | Same, Lago di Lei is its seasonal upper reservoir. |
| Croix (Lienne) | 66 | 0.00 GWh | Code path, not data. The Tseuzier override was applied *after* the cascade expansion, so the chain contained only St-Léonard and the whole 131 GWh went to the lowest stage. Croix, the middle stage, got nothing. |
| Hopflauenen Trift | 82 | 0.00 GWh | Genuine. Daily basins on the Gentalwasser, no seasonal reservoir. |
| Innertkirchen 2 | 54 | 0.00 GWh | Genuine. Gadmerwasser cascade stage, daily basins only. |

## 2. Fixes applied

1. `lake_plant_overrides.csv`: four new override rows (Gibidum → Bitsch; Lago di Lei, Sufnersee, Stausee Bärenburg → Sils KHR as cascade outlet).
2. New file `manual_lakes.csv`: the three KHR lakes with volume and full-supply level from the operator (https://www.khr.ch/de/stauseen). Including Lago di Lei is consistent with the existing treatment of Lago di Livigno, which also lies on Italian territory but is operated from Switzerland and counted in the BFE filling-level statistics.
3. `estimate_storage_energy.py`: (a) reads `manual_lakes.csv` and appends it to the wiki lake list, refusing duplicates; (b) overrides now *seed* the chain before the WKA-token cascade expansion instead of being bolted on afterwards. This fixes Croix and makes future overrides inherit the full cascade automatically.
4. Pipeline re-run end to end (`estimate_storage_energy.py` → `build_individual_plant_table.py` → `cluster_hydro_plants.py`). Totals still calibrate to the BFE 8,895 GWh by construction.

## 3. Results after the fix

| Plant | Storage before | Storage after | E/P after |
|---|---|---|---|
| Bitsch | 0.00 | 13.8 GWh | 40 h (fast dam, plausible for a compensation basin with Aletsch inflow) |
| Ferrera 1 | 0.28 | 228.4 GWh | 1,269 h |
| Sils KHR | 0.18 | 152.8 GWh | 611 h |
| Bärenburg | 0.17 | 141.4 GWh | 639 h |
| Croix | 0.00 | 85.3 GWh | 1,293 h |
| St-Léonard | 131.9 | 46.5 GWh | 1,293 h (now shares Tseuzier with Croix by head) |

Regional calibration factors moved from {Wallis 0.88, Graubünden 1.17, Tessin 1.04, ÜbrigCH 0.78} to {0.88, 0.86, 1.04, 0.78}. Graubünden dropping below 1 is the expected signature of the previously missing Lago di Lei: before, the calibration inflated all other GR lakes to reach the BFE total. Consequently all other GR plants lose ~25% storage (Sedrun 271→199, Pradella 257→189, Tavanasa 214→157 GWh, etc.). Wallis anchors are untouched (Lac des Dix 1,529 vs 1,500 GWh SWV).

Type totals: dam 7,382 → 7,195 GWh, psp_open 858 → 1,060 GWh, psp_close unchanged 619 GWh, total unchanged 8,895 GWh.

## 4. Remaining decisions and caveats

- **Hopflauenen Trift and Innertkirchen 2** are genuinely storage-free peaking stages. Recommendation: treat them as run-of-river-like fixed infeed in the model (in the redesigned clustering they belong in the fast/zero bucket, not in a reservoir class).
- **Trift reservoir (planned)**: KWO's Trift project (~85 Mio m³ dam upstream of Hopflauenen) is approved but delayed and contested. Whether to include it is a 2035/2050 *scenario* decision for the paper, not a data fix.
- **Full-cascade head convention**: under this pipeline's convention Lago di Lei carries 494 GWh (water valued down to Sils at 665 m). Per-lake accountings (SWV type) credit Valle di Lei with roughly 200 GWh at plant-specific heads. This is the same documented convention as for Muttsee and is neutralized in totals by the regional calibration, but state it in the paper's data appendix.
- **Unmatched river impoundments** (Wohlensee, Niederried, Klingnau, ~107 GWh via fallback) are seasonal-storage-irrelevant weirs; their energy is currently smeared over the matched plants of ÜbrigCH by the calibration. Materiality is ~1% of total; consider dropping them from the lake list.
- Small missing lakes serving plants <10 MW (Trübsee, Lac de Tanay, Seealpsee, Rempen, Solis and similar) were left as is, immaterial for the model.

## 5. Files changed

| File | Change |
|---|---|
| `estimate_storage_energy.py` | manual-lakes input, override-before-expansion |
| `lake_plant_overrides.csv` | +4 rows |
| `manual_lakes.csv` | new (3 KHR lakes, sourced) |
| `storage_lakes_energy_2026.csv` | regenerated |
| `hydro_plants_individual.csv` | regenerated |
| `hydro_plants_clustered.csv`, `representative_hydro_plants.csv` | regenerated with the *existing* clustering method for consistency; both are due for replacement by the E/P-based redesign |
| `source.txt` | validation note appended |

Spider PNGs were regenerated locally but not treated as deliverables; re-run `cluster_hydro_plants.py` to refresh them.
