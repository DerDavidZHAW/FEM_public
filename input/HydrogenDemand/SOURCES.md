# Hydrogen demand steps — sources and derivations

Created 2026-08-08 for the W8 electrolyzer redesign (stepwise annual offtake demand
replacing the fixed `consume_tot_limit` equality). Status: **design data, not yet
wired into the model.** Every number below is either (a) anchored to a named source,
(b) derived from a FEM-internal input (file + value cited), or (c) an explicitly
marked placeholder awaiting one of the two extraction tasks at the bottom.

## 1. Design (agreed 2026-08-08)

- Steps are **annual** energy variables `E_s ∈ [0, width_s]`, valued at `wtp_s` in the
  objective; total electrolyzer consumption = Σ E_s / (unit basis: MWh_H2 × η → MWh_el).
- **No hourly H2 balance, no storage assets**: intra-year flexibility is unchanged vs.
  today's annual equality (both imply free intra-year H2 buffering — state as a
  limitation; a monthly-window variant is a cheap sensitivity if requested).
- The electrolyzer's hourly opportunity value becomes `η × wtp` of the marginal step:
  an **exogenous merit-order step** (solver-invariant band for the price attribution),
  and volumes self-regulate between "too much and too little".
- Same step structure and European base WTP levels for **all 22 electrolyzer nodes**,
  plus a per-node **delivery premium** (`hydrogen_demand_node_premium.csv`; currently
  CH00 only, see 2b). This removes the current cross-country inconsistency (equality
  duals of 12.3 vs 86.1 CHF/MWh_el in the same run) — an integrated H2 market cannot
  sustain such spreads, but it CAN sustain delivery-cost differentials, which is
  exactly what the premium represents.
- Merger with the P2P "hydrogen" storage tech: **postponed to future work** (it would
  force an hourly balance; Swiss literature finds H2-to-power marginal anyway [W1,A4,R5]).

## 2. WTP anchors (steps CSV, column `wtp_CHF_per_MWh_H2`) — v2 curve (2026-08-12)

Unit note: 1 kg H2 = 33.33 kWh (LHV) → 1 CHF/kg = 30 CHF/MWh_H2.

**v2 design (decision trigger: A/B test results 2026-08-12).** The v1 curve
(4 steps, Σwidth = 1.00, must-serve 0.35) put the whole 2050 continent on one
25%-wide marginal step (45), producing a single price plateau at 30.6 CHF/MWh_el
and capping the demand curve exactly at the TYNDP-22 total. v2 makes the
TYNDP-22 quantity an INTERIOR point of the demand curve: Σwidth = 1.40 (the
corrected TYNDP-24 GA multiplier, 1.30, is the citable upper range — sec. 4),
must-serve = 0.50 (numerically equal to the old ad-hoc 2035 reduction
coefficient, now segment-derived — the tight-year floor reproduces the old
calibration by construction), and the elastic range is a 4-step parity ladder
75/60/45/30 so no single step dominates. Serving steps 1–5 = exactly 1.00 ×
TYNDP-22. Must-serve widths follow the TYNDP-24 sectoral structure of final H2
demand (EU27, workbook extraction: industry 62–77%, transport 16–24%,
buildings+households 3–16%); elastic widths are cross-sector parity tranches
(price-based, not sector quotas).

| # | segment | WTP | width | must | anchor |
|---|---|---|---|---|---|
| 1 | captive_transport_synfuel | 150 | 0.10 | 1 | FEM-internal ceiling: resmethane 220 × η_meth 0.8 ≈ 176; diesel/e-fuel parity band below it |
| 2 | industry_feedstock_existing | 100 | 0.25 | 1 | Lux & Pfluger (2020): EU marginal production cost >110 at EC-vision volumes (DOI: 10.1016/j.apenergy.2020.115011); blue-H2 parity |
| 3 | industry_process_contracted | 85 | 0.15 | 1 | first-mover DRI/HT-heat under take-or-pay; blue-H2 parity lower band (WTP is a label — volume is forced) |
| 4 | industry_fuel_switching | 75 | 0.25 | 0 | gas+CO2 switching parity band; import parity central ≈2.5 CHF/kg; Brown-school fixed WTP ~78; FEM 2050 equality-duals 49–86 bracket it |
| 5 | bulk_backbone | 60 | 0.25 | 0 | backbone pipeline-import parity ≈2 CHF/kg |
| 6 | power_sector_storage | 45 | 0.20 | 0 | H2-to-power firming/storage refill; TYNDP-24 shows P2G + imports ≈1'150 TWh ABOVE final demand (EU 2050) — the power/conversion sink is real; WTP ≈ expected captured power price × turbine η |
| 7 | export_optionality | 30 | 0.20 | 0 | export/ammonia low parity ≈1–1.5 CHF/kg; Ahang et al. (2025) abundant-supply equilibrium ≈30 (DOI: 10.1016/j.apenergy.2024.124656) |

Electricity-side values (η 0.68, before the CH premium): 102 / 68 / 57.8 (labels,
forced) and 51.0 / 40.8 / 30.6 / 20.4 (elastic grid — 10.2-CHF spacing, so the
2050 price distribution spreads over four levels instead of parking on one).
Interaction with the scenario ladder (sec. 4): the rung multiplier scales the
WHOLE curve; central 1.00 keeps the v2 geometry as designed — applying a
tyndp24 rung on top of the extended curve double-scales and should be read as
a pure sensitivity. Model wiring handles Σwidth ≠ 1 without change; capacity
sizing was updated to the full offered curve (total × Σwidth / FLH-target).

CHF≈EUR treated as 1:1, consistent with the rest of the FEM cost inputs.

## 2b. Swiss delivery premium (hydrogen_demand_node_premium.csv)

Switzerland pays MORE than the European anchor for delivered hydrogen, for two
structural reasons: (i) it is not part of the initial European Hydrogen Backbone
wave (connection planned ~2040), so the pipeline leg from the backbone core must be
added; (ii) it has **no salt caverns**, so seasonal buffering happens abroad (with
re-transport) or in costlier local storage — Wallinger et al. find compressed-tank
storage not cost-effective in CH and model truck-based buffering, and frame Swiss
competitiveness "under conservative assumptions of hydrogen import costs".

Derivation (additive, 1 CHF/kg = 30 CHF/MWh_H2):

| Component | Range | Source |
|---|---|---|
| Pipeline leg backbone core → CH (~300–800 km) | 0.2–0.5 CHF/kg = 6–15 | Wolf et al. 2024: 0.08–1.34 €/kg for pipeline routes to DE (DOI: 10.1016/j.ecmx.2024.100682); Solomon et al. 2023: 0.3–3.44 €/kg for 25–500 km, low end at high volume (DOI: 10.1002/ente.202300785); Di Lullo et al. 2022: 0.66 $/kg per 1000 km (DOI: 10.1016/j.ijhydene.2022.08.131) |
| Storage/buffering gap (no CH caverns) | 0.2–0.35 CHF/kg = 6–10 | Revinova et al. 2024: cavern storage ~0.35 $/kg (DOI: 10.3390/resources13070092); Sens et al. 2022: caverns cut supply cost up to 50% for seasonal profiles — an advantage CH cannot access domestically (DOI: 10.1016/j.enconman.2022.115742) |

Chosen values (**proposed, additive on every step's WTP for CH00**):
- **2035: +15 CHF/MWh_H2** (0.5 CHF/kg; no backbone connection, upper transport band)
- **2050: +10 CHF/MWh_H2** (0.33 CHF/kg; backbone connection assumed per EHB planning,
  cavern gap remains)

Equivalent ratio on the central 75-step: ~1.20 (2035) / ~1.13 (2050). Additive is the
economically correct form — transport/storage are per-kg costs on the delivered price;
a multiplicative factor would inflate the top steps without physical basis.

Model-effect note: a higher Swiss WTP means CH electrolyzers slightly outbid
neighbours at equal electricity prices. That is the intended economics: domestic
production displaces imports that carry the delivery premium, so the avoided cost —
and hence the willingness to pay for domestic electrolysis — is higher in CH.
Sensitivity option: premium → 0 as a "full backbone integration" case.

## 3. η_electrolysis = 0.68

FEM books the electrolyzer tech at efficiency 1.0 (pure electricity demand; no H2 side
modeled). For the MWh_H2 ↔ MWh_el conversion the steps CSV carries an explicit
η = 0.68 (LHV), the standard 2035–2050 projection band for alkaline/PEM systems
(e.g., DEA Technology Catalogue; 65–71%). **Decision point for David**: confirm or
adjust; it scales all WTPs on the electricity side (bid_el = η × wtp_H2).

## 4. National totals (scenario ladder)

- **LADDER SOURCES (decision 2026-08-11): the model's own scenario producers
  only** — TYNDP for the neighbours, EP2050+ for CH. Wallinger 2025 is
  validation/discussion material, not a rung (keeps one producer per geography).

- **CH00 rungs — EP2050+ (`electrolyzer_net_demand_CH.csv`):**
  - central = ZBA row (2035: 1'613'195 / 2050: 2'938'216 MWh_el). Cross-check:
    equals the 2.94 TWh "flex electrolyzer" in `Annual_balance_ch.csv` of the
    2050 matrix runs (verified 2026-08-08).
  - low = WWB row: multipliers 0.38 (2035: 608'963 MWh_el) / 0.81 (2050:
    2'373'482 MWh_el) vs ZBA.
  - NO upward CH rung (decision; EP2050+ has no variant above ZBA — ZVA/ZVB
    equal ZBA in the file). One-sided CH sensitivity range: state as limitation.
    Wallinger Midway (1.37 / 2.87, see below) is the citable upper anchor if one
    is ever needed.

- **Neighbour rungs — TYNDP 2024, CORRECTED extraction (2026-08-11):**
  - Sources: TYNDP 2024 Scenario-Report Data-Figures — Fig. 23 (electrolysis
    electricity demand, EU27, split network-connected / off-grid), Fig. 34
    (electrolyser capacity, market vs dedicated-RES), Fig. 33 (H2 supply split);
    TYNDP 2024 demand workbook `3_DEMAND_OUTPUT` (per-country final H2 demand).
  - Correction 1 — off-grid EXCLUDED: FEM has no off-grid assets; an off-grid
    electrolyser neither buys at the zonal price nor brings its dedicated RES
    into FEM's fleet. Network-connected electrolysis only: DE 1'124 (2040) /
    2'053 (2050); GA 1'354 / 2'344; NT 204 (2030) TWh_el. (Off-grid would add
    206–425 TWh.)
  - Correction 2 — node coverage: Fig. 23 is EU27; FEM models only 17 of the 27
    members (missing BG, CY, EE, FI, GR, IE, LT, LV, MT, RO). Scaled by the
    FEM-countries' share of EU27 final H2 demand from the workbook, s ≈ 0.89
    (stable across scenarios and years). Bias note: the missing countries (FI,
    IE, …) likely host proportionally MORE electrolysis than final demand, so
    the multipliers below are upper bounds.
  - Base: FEM runs use ONLY the GlobalAmbition column of TYNDP 22 (David
    2026-08-11), so both rungs divide by the GA sums over FEM's EU-member
    nodes, per weather year: 705.1 / 1'040.8 / 1'599.1 TWh_el (2035/2040/2050).
    Multipliers vs the GA-TYNDP22 base:
    **tyndp24_de 0.84 (2035, interp. NT-2030→2040) / 0.96 (2040) / 1.15 (2050);
    tyndp24_ga 0.99 / 1.16 / 1.30.**
    tyndp24_de is a CROSS-family comparison by construction (ENTSO-E's lower
    2024 electrolysis path measured against the GA22 world in the model) — its
    role is "how low does ENTSO-E's own 2024 range go", not a like-for-like
    storyline update. Family-matched for reference (DE24 vs DE22 sums 754.7 /
    1'215.9 / 1'516.9): 0.78 / 0.82 / 1.21.
  - Reading: at 2035 TYNDP 24 IS a downward revision (in the spirit of the old
    ad-hoc 0.5 coefficient); at 2050 it is a moderate upward one (1.15–1.30).
    The first extraction round (same day, superseded) had overstated the 2050
    multipliers as 1.58/1.73 by including off-grid electricity and comparing
    full EU27 against FEM's 17-country node set.
  - Supply context (Fig. 33, EU27): domestic P2G dominates TYNDP-24 H2 supply
    (DE-2050 ≈ 1'795 TWh_H2 P2G vs ≈ 550 TWh imports incl. ammonia) — the
    TYNDP-22 import pillar shrank for cost/energy-security reasons. Total H2
    use fell while EU electrolysis electricity rose; this is why "H2 revised
    down" and 2050 multipliers > 1 coexist.

- **Wallinger et al. 2025 — VALIDATION role** (*Int. J. Hydrogen Energy*
  121:96–110, DOI: 10.1016/j.ijhydene.2025.03.345; EXPANSE, 2'136
  municipalities, three storylines):
  - CH national H2 demand (Section 3 + Fig. 9), TWh_H2/a — net of chemical
    by-production (Cressier/Visp/Pratteln, ~0.5 in 2035 / ~0.3 in 2050, which
    exists without buying grid electricity): niche 0.4 → 2.4, midway 1.5 → 5.7,
    economy 5.8 → 17.5 (2035 → 2050). As multipliers vs ZBA × η 0.68
    (= 1.097 / 1.998 TWh_H2): niche 0.36 / 1.20, midway 1.37 / 2.87,
    economy 5.29 / 8.73.
  - VALIDATION FINDINGS: (i) EP2050+ WWB (0.38 in 2035) lands on Wallinger's
    niche (0.36) — two independent Swiss sources agree on the low case;
    (ii) ZBA sits between niche and midway, i.e. the central case is INSIDE the
    Swiss literature range (use in defense of central); (iii) their CH
    electrolysis production in 2035 (trade disabled: 0.4 / 1.6 / 5.7 TWh_H2)
    matches the net-demand numbers, confirming the by-production netting.
  - Segment shares (transport / feedstock / HT heat) as context for the step
    widths: midway 55/20/25 % (2035), 72/2/27 % (2050); economy 54/6/38,
    54/1/45; niche ≈ 50/50 transport/feedstock in 2035 (HT heat excluded).
  - CH is a net H2 exporter in ALL their 2050 storylines (0.5–6.1 TWh_H2) —
    supports step 4 (`export_backbone_optional`).

- Interaction warning (also in the scenarios CSV header): the current scen CSVs use
  `electrolyzer_demand_reduction_coefficient` = 0.5 (2035) / 1.0 (2050). When the
  steps go live, retire that knob (set 1.0) — otherwise reductions double-count;
  the low rung covers the old halved 2035 case.

## 5. Supporting literature (Consensus search 2026-08-08)

- Wallinger et al. 2025, IJHE, DOI: 10.1016/j.ijhydene.2025.03.345 [W1] — CH segment
  quantities & scenarios; H2 re-conversion marginal in CH.
- Akbari et al. 2024, Energy Conv. Mgmt., DOI: 10.1016/j.enconman.2024.118911 [A4] —
  Swiss integrated power/H2/CH4 with price-elastic H2 demand; +28–76% price →
  −6–10% demand (inelastic ⇒ steps, not smooth curves); storage serves demand, not power.
- Rinaldi et al. 2023, Cleaner Prod. Letters, DOI: 10.1016/j.clpl.2023.100044 [R5] —
  H2 as long-period electricity storage not cost-optimal in CH.
- Rubino et al. 2026, IJHE, DOI: 10.1016/j.ijhydene.2026.153822 — domestic H2 demand
  among the most influential uncertainties for the Swiss H2 system (justifies the ladder).
- Lux & Pfluger 2020, Applied Energy, DOI: 10.1016/j.apenergy.2020.115011 — EU H2
  supply curve; >110 €/MWh_H2 at EC-vision volumes.
- Ahang et al. 2025, Applied Energy, DOI: 10.1016/j.apenergy.2024.124656 — EU
  equilibrium H2 price ≈ 30 €/MWh (abundant supply).
- Ruhnau 2021, Applied Energy, DOI: 10.1016/j.apenergy.2021.118194 — flexible
  electrolyzer WTP creates the renewables price floor (design rationale).
- Odenweller & Ueckerdt (Nature Energy — verify exact reference) — green-H2
  ambition/implementation gap (rationale for the downward-corrected ladder).
- Brown & Reichenberg 2021 (W1 reading) — fixed-WTP hydrogen demand design; verify
  the remembered ~78 €/MWh value.

## 6. Literature positioning: why a reduced-form premium and not an explicit H2 network

Recent adjacent models span four classes for spatial H2 price differentiation:

1. **Fully endogenous coupled networks** (H2 nodes, pipelines, storage; nodal H2
   prices emerge as duals): Koirala et al. 2021 (34 el / 19 H2 / 22 CH4 nodes, NL;
   DOI: 10.1016/j.apenergy.2021.116713); Li et al. 2025 (nodal marginal H2 price
   decomposition into energy/loss/congestion/delay; DOI: 10.3390/en18215681);
   Kountouris et al. 2024 (EU corridors; DOI: 10.1038/s41467-024-49867-w);
   Gils et al. 2021 (REMix, DE; DOI: 10.1016/j.renene.2021.08.016); Akbari et al.
   2024 (CH networks; DOI: 10.1016/j.enconman.2024.118911).
2. **National/zonal equilibrium coupling** (joint el+H2 welfare optimum, country
   granularity): Loschan et al. 2023 (13 CWE countries; DOI: 10.3390/en16145333);
   Densing et al. 2026 (DOI: 10.1016/j.eneco.2026.109221).
3. **Spatially uniform exogenous H2 value**: Ruhnau 2021; Brown-school fixed WTP.
   vom Scheidt et al. 2021 show uniform spatial pricing misallocates electrolyzers
   and understates congestion costs (DOI: 10.5445/ir/1000133739) — evidence that
   SOME spatial differentiation is warranted.
4. **Reduced-form delivered-cost adders / supply-cost curves** (delivered price =
   source price + transport/storage chain): Hampp et al. 2021; Brändle et al. 2021;
   Wolf et al. 2024. **← this file's approach, applied per node.**

Why class 4 and not class 1/2 here: (i) the paper's contribution is Swiss
ELECTRICITY price formation — an H2 infrastructure layer is a second model whose
detail is assumption-hungry (Münster et al. 2025 show H2 results are highly
sensitive to exactly these modelling choices; DOI: 10.1016/j.energy.2025.137092);
(ii) the attribution methodology requires exogenous, solver-invariant bid anchors —
class-1/2 H2 prices are DUALS again, reintroducing the degenerate-face
non-uniqueness the twin experiment exposed; (iii) the premium is calibrated ON the
outputs of class-1 models (transport/storage spreads of ~0.1–0.5 CHF/kg), i.e. we
take their result as our input; (iv) the parked carrier-balance merger is the
upgrade path toward class 1 if ever needed. Class 3 (uniform) is rejected because
Switzerland's missing backbone connection and cavern gap are structural, not noise.

## 6b. Central scenario and ladder sources (decision 2026-08-11, supersedes 2026-08-08)

- **Central = the model's own calibrated quantities** (TYNDP 22 for neighbours,
  EP2050+ ZBA for CH; multiplier 1.00). Rationale: the whole FEM world —
  demands, capacities, fuel and CO2 prices — is calibrated to TYNDP 2022 /
  EP2050+, so keeping the electrolyzer totals in the same vintage preserves
  internal scenario consistency; mixing TYNDP-24 demand into a TYNDP-22 supply
  world would change one block's vintage in isolation. FEM runs use only
  GlobalAmbition (TYNDP 22) and ZBA (EP2050+), so all multipliers are expressed
  against that base. Defense from the corrected extraction (section 4): the
  TYNDP-24 multipliers straddle 1.00 (0.84–0.99 in 2035, 1.15–1.30 in 2050) and
  ZBA lies inside the Wallinger storyline range — central is not an outlier in
  either geography.
- **Ladder rungs from the model's scenario producers only** (TYNDP 24 families
  for neighbours; EP2050+ WWB for CH). Wallinger 2025 = validation/discussion
  material, not a rung (David's decision; one producer per geography).
- CAVEATS for the paper: (i) the CH sensitivity is one-sided (downward only);
  (ii) "TYNDP 24 revised electrolysis down" holds at 2035 but NOT at 2050
  (corrected multipliers 1.21/1.30); (iii) the 2035 neighbour multipliers rest
  on a linear NT-2030 → 2040 interpolation; (iv) the coverage scaling (s ≈ 0.89)
  allocates electrolysis by demand shares — the multipliers are upper bounds.
- History: the 2026-08-08 decision (midway-as-central) rested on the premise
  "ENTSO-E revised H2 demand down a lot"; the corrected extraction shows the
  revision is real at 2035 but reverses at 2050, and the first uncorrected
  extraction round (off-grid included, EU27 vs 17-node mismatch) had briefly
  suggested a wholesale upward revision (1.58/1.73 for 2050) — both superseded.
- Consequence for the old 2035 knob: `electrolyzer_demand_reduction_coefficient`
  = 0.5 is retired WITHOUT replacement when the steps go live — central 2035
  then uses the raw TYNDP-22/ZBA totals; the low rung (CH 0.38, neighbours
  0.84) covers the halved case approximately.

## 7. Implementation status (wired 2026-08-11, hybrid design per David's decision)

DESIGN CHANGE vs the original checklist: hybrid demand curve instead of
all-elastic. Steps with `must_serve=1` (1+2, 35% of the total) remain a FORCED
annual equality (take-or-pay segment; scarcity rent possible in tight years);
steps with `must_serve=0` (3+4, 65%) are elastic annual variables E_h2step in
[0, width] valued at η × (WTP + node premium) in the objective. Rationale: some
H2 demand is genuinely price-inelastic (contracted/process-critical), and the
elastic share self-curtails, so high demand rungs can no longer blow up tight
years the way the old full equality did.

Implemented (all behind the `h2_steps` setting, default False = legacy):
1. `read_electrolyzer_data` (model/data_import_fcns.py): reads the three
   HydrogenDemand CSVs; per node total = electrolyzer_net_demand × rung
   multiplier (`h2_demand_scenario`: role name or "<DEFAULT_rung>+<CH00_rung>");
   must-serve share from the steps CSV; elastic widths + value_el per step.
   `electrolyzer_demand_reduction_coefficient` is IGNORED in steps mode
   (warning) — the rung multiplier replaces it. `electrolyzer_flh_target`
   setting replaces the hardcoded 3000 FLH capacity convention (capacity =
   TOTAL width / FLH; source finding: capacities were never TYNDP data —
   TYNDP24 implies ~4'700–5'800 FLH, Wallinger CH ~3'300–4'800).
2. E_h2step Var + Set (components_common define_vars_op); revenue term in
   obj_expression; consume_tot_limit equality now reads
   Σ_h charge == must_serve + Σ_s E_h2step (components_central) — SAME
   constraint name, so the dual export and price_setting_tech keep working.
3. Bid formula: NO change needed — the consume_tot_limit dual is automatically
   pinned to η × (WTP + premium) of the marginal elastic step (verified in a
   4-hour LP smoke test: dual = marginal-hour price, bounded by adjacent step
   values). In tight years (floor binding) it exceeds the top elastic value —
   the take-or-pay scarcity rent, economically intended.
4. Step utilisation exported per run to output/<scen>/h2_steps_result.csv
   (E_served vs width, value_el, wtp, premium per plant/step).
5. A/B test matrix scenarios/scen_to_run_STORSUPPORT.csv (2026-08-11): {2035
   wy2008, 2050 wy1995, 2050 wy2008} × 12hydro × {_ref legacy, _h2steps};
   16-column matrix backed up as scen_to_run_STORSUPPORT_matrix16_backup_*.csv.

6. v2 curve (2026-08-12): steps CSV extended to 7 steps, Σwidth 1.40,
   must-serve 0.50 (see section 2); `read_electrolyzer_data` capacity sizing
   updated to total × Σwidth_share / FLH (backwards compatible: Σ=1 gives the
   old value). A/B results of the v1 curve (Bid_Gap pass, crossing-consistent
   merit orders, duals pinned to step values) are in the 2026-08-12 runs.

Still open: v2 test run + comparison against the v1 A/B results; final WTP
anchor sign-off (steps CSV status 'proposed'); FLH sensitivity (4'500–5'000);
H2-turbine fuel price consistency (currently 0); TYNDP-24 sector-share note:
CH demand is transport-heavy per Wallinger (54–72%) while the EU is
industry-heavy — widths are uniform across nodes (state as limitation).
