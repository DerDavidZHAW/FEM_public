# Known data issues by period

**Read this before choosing a historical period or an input source for a CH_only back-cast.** Each entry
names the period and source it affects and the condition under which it applies. If a planned run meets that
condition, stop and decide explicitly how to handle the issue before building model inputs.

| ID | Affects | Source | Status |
|---|---|---|---|
| KDI-1 | Any run whose period includes **December 2023 - February 2024** (e.g. hydrological year 2023/24, calendar year 2024) **and** uses PECD v4.2 as Swiss reservoir inflow | Copernicus PECD v4.2, CH00, HRI | Open; logged 2026-10-09 |

## KDI-1: PECD v4.2 Swiss reservoir inflow is near zero in January 2024

**Applies if both hold:**
- the period includes December 2023 to February 2024;
- Swiss reservoir inflow comes from PECD v4.2 (series HRI, zone CH00).

It does **not** apply to hydrological year 2025/26, and not if inflow comes from the BFE storage balance.

**Symptom.** CH00 HRI is exactly 0 in the weeks starting 1 and 8 January 2024, and 2.0 and 6.7 GWh in the
next two weeks. The first four weeks of 2024 add up to 8.7 GWh, against 192-496 GWh in 2023, 2025 and 2026.
The zeros are in the raw file
`H_ERA5_ECMW_T639_HRI_0000m_Pecd_SZON_S202401010000_E202412230000_NRG_TIM_07d_COM_noc_org_NA_NA---_NA---_StRnF_PECD4.2_fv1.csv`
(published 17 June 2025).

**Why it is very likely an artefact:**
- Austria, France and northern Italy show no dip in the same weeks.
- BFE run-of-river output in December 2023 and January 2024 was the highest of those months in 2017-2025.
- The BFE storage balance gives 583 GWh (534-632) of natural inflow for January 2024; PECD has 78 GWh.
- In PECD 2021.3 (1982-2017) the lowest total for the same weeks is 177 GWh.

The data provider has not confirmed it.

**Size.** About 500 GWh too little inflow in January 2024, roughly 2% of a year's reservoir inflow, concentrated
in one winter month when water value is high.

**What to decide before such a run:**
- whether to use the BFE storage-balance residual instead of PECD for that winter;
- or to keep PECD and report the run as affected by KDI-1;
- or to check first whether a newer PECD file version corrects it.

Any replacement must be explicit and documented; never fill or scale values silently.

**Evidence:** the figures above. The analysis script and plot (section G of a local investigation,
2026-10-09) are kept outside the repository.

**Related.** The 2026 PECD values come from interim ("ITE") files. Copernicus may revise them, so record the
file versions used in any run.
