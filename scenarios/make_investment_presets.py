"""Fix the investment decisions of a finished run for new (dispatch-only) runs.

Reads the invested capacities of a BASE run from its output folder and writes
them as variable presets for one or more TARGET scenarios into
input/model_variable_presets.csv (the file core.py applies before solving).
Typical use: a counterfactual run with the same capacities but other NTCs
(border decomposition: dispatch channel vs. water-value channel).

Fixed variables (only the investable subsets, the rest is fixed by the data
already): gen_max / pmp_max / gen_energy_max for P_allinv,
genTh_max / pumpTh_max / gen_energyTh_max for PDH_allinvTh,
fuel_storage_capacity_annual for Fuels_limited.

Barrier solutions (crossover=0) carry residues of ~1e-6 and can sit a hair
above a limit; fixing such a value verbatim makes the model infeasible. So the
values are CLIPPED into the constraints that involve fixed variables only:
    gen_max <= gen_max_limit, gen_energy_max <= energy_max_limit,
    pmp_max <= gen_max, genTh_max <= genTh_max_limit, pumpTh_max <= genTh_max,
    24 * ratio_days * genTh_max <= gen_energyTh_max (PTES),
    sum(resistive genTh_max) <= resistive_heater_investment_cap_MW_total,
    fuel_storage_capacity_annual <= its annual limit,
    values below `zero_tol` -> 0 (CH00_nuclear keeps its 1e-2 lower bound).
A check table with every clip is written to output/<base>/investment_presets_check.csv.

Usage (repo root):
    python scenarios/make_investment_presets.py --base base_2035_wy2008_12hydro \
        --target autarky_2035_wy2008_12hydro --target ntc50_2035_wy2008_12hydro [--dry-run]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
PRESETS = REPO / "input" / "model_variable_presets.csv"
ZERO_TOL = 1e-4          # MW / MWh: barrier residues below this are set to 0
NUCLEAR_LB = 1e-2        # core.py sets this lower bound on gen_max[CH00_nuclear]


def kv(df, key, val="value"):
    return dict(zip(df[key], df[val]))


def load_base(folder):
    o = {}
    o["P_allinv"] = pd.read_csv(folder / "P_allinv.csv").iloc[:, 0].astype(str).tolist()
    o["gen_max"] = kv(pd.read_csv(folder / "gen_max.csv"), "P_gen")
    o["gen_max_limit"] = kv(pd.read_csv(folder / "gen_max_limit.csv"), "P_allinv")
    o["pmp_max"] = kv(pd.read_csv(folder / "pmp_max.csv"), "P_pumping")
    o["gen_energy_max"] = kv(pd.read_csv(folder / "gen_energy_max.csv"), "P_energymax")
    o["energy_max_limit"] = kv(pd.read_csv(folder / "energy_max_limit.csv"), "P_allinv")
    o["genTh_max_limit"] = kv(pd.read_csv(folder / "genTh_max_limit.csv"), "PDH_allinvTh")
    o["genTh_max"] = kv(pd.read_csv(folder / "genTh_max.csv"), "PDH")
    o["pumpTh_max"] = kv(pd.read_csv(folder / "pumpTh_max.csv"), "PDH")
    o["gen_energyTh_max"] = kv(pd.read_csv(folder / "gen_energyTh_max.csv"), "PDH_TES")
    o["energyTh_max_limit"] = kv(pd.read_csv(folder / "energyTh_max_limit.csv"), "PDH_allinvTh")
    o["fuel_storage"] = kv(pd.read_csv(folder / "fuel_storage_capacity_annual.csv"), "Fuels_limited")
    o["fuel_storage_limit"] = kv(pd.read_csv(folder / "fuel_storage_investment_annual_limit.csv"),
                                 "Fuels_limited")
    settings = pd.read_csv(folder / "settings.csv", header=None, index_col=0).iloc[:, 0]
    o["ratio_days"] = float(settings.get("storage_to_charge_ratio_days", 7))
    cap = settings.get("resistive_heater_investment_cap_MW_total", "False")
    o["resistive_cap"] = None if str(cap) in ("False", "nan", "") else float(cap)
    techs = pd.read_csv(folder / "Map_plantDH_tech.csv")
    o["plantDH_tech"] = kv(techs, techs.columns[0], techs.columns[1])
    return o


def build_rows(o):
    """Return (rows, checks): rows = [(var, idx, value)], checks = list of dicts."""
    rows, checks = [], []

    def clip(var, idx, value, lo=None, hi=None, why=""):
        v = float(value)
        new = v
        if abs(new) < ZERO_TOL:
            new = 0.0
        if lo is not None and new < lo:
            new = lo
        if hi is not None and np.isfinite(hi) and new > hi:
            new = hi
        if new != v:
            checks.append(dict(variable=var, index=idx, base_value=v, fixed_value=new,
                               change=new - v, reason=why or "clip"))
        rows.append((var, idx, new))
        return new

    # electricity side ---------------------------------------------------------
    gen_fixed = {}
    for p in o["P_allinv"]:
        if p not in o["gen_max"]:
            continue
        lo = NUCLEAR_LB if p == "CH00_nuclear" else None
        gen_fixed[p] = clip("gen_max", p, o["gen_max"][p], lo=lo,
                            hi=o["gen_max_limit"].get(p, np.inf), why="gen_max <= gen_max_limit")
    for p in o["P_allinv"]:
        if p in o["pmp_max"]:
            clip("pmp_max", p, o["pmp_max"][p], hi=gen_fixed.get(p, np.inf), why="pmp_max <= gen_max")
        if p in o["gen_energy_max"]:
            clip("gen_energy_max", p, o["gen_energy_max"][p],
                 hi=o["energy_max_limit"].get(p, np.inf), why="gen_energy_max <= energy_max_limit")

    # district heating side ---------------------------------------------------
    inv_th = [p for p in o["genTh_max_limit"] if p in o["genTh_max"]]
    th_fixed = {}
    # resistive heaters share one global cap: scale down if the barrier sum exceeds it
    resistive = [p for p in inv_th if o["plantDH_tech"].get(p) == "resistive_heater"]
    scale = 1.0
    if o["resistive_cap"] is not None and resistive:
        s = sum(o["genTh_max"][p] for p in resistive)
        if s > o["resistive_cap"]:
            scale = o["resistive_cap"] / s
            checks.append(dict(variable="genTh_max", index="(sum resistive)", base_value=s,
                               fixed_value=o["resistive_cap"], change=o["resistive_cap"] - s,
                               reason="sum(resistive) <= resistive_heater_investment_cap"))
    for p in inv_th:
        v = o["genTh_max"][p] * (scale if p in resistive else 1.0)
        th_fixed[p] = clip("genTh_max", p, v, hi=o["genTh_max_limit"].get(p, np.inf),
                           why="genTh_max <= genTh_max_limit")
    for p in inv_th:
        if p in o["pumpTh_max"]:
            clip("pumpTh_max", p, o["pumpTh_max"][p], hi=th_fixed[p], why="pumpTh_max <= genTh_max")
        if p in o["gen_energyTh_max"]:
            lo = None
            if "PTES" in str(o["plantDH_tech"].get(p, "")):
                lo = 24.0 * o["ratio_days"] * th_fixed[p]      # 24*ratio*genTh <= energyTh
            clip("gen_energyTh_max", p, o["gen_energyTh_max"][p], lo=lo,
                 hi=o["energyTh_max_limit"].get(p, np.inf),
                 why="24*ratio*genTh <= gen_energyTh <= energyTh_max_limit")

    # fuel storage ------------------------------------------------------------
    for f, v in o["fuel_storage"].items():
        clip("fuel_storage_capacity_annual", f, v, hi=o["fuel_storage_limit"].get(f, np.inf),
             why="fuel_storage <= annual limit")
    return rows, checks


def write_presets(rows, targets, dry_run):
    text = PRESETS.read_text(encoding="utf-8") if PRESETS.exists() else ""
    lines = text.splitlines()
    # drop earlier rows of the same targets (idempotent)
    kept = [ln for ln in lines
            if not any(ln.split(",")[1:2] == [t] for t in targets)]
    new = []
    for t in targets:
        new.append(f"# --- investments fixed to the base run for scenario {t} "
                   f"(scenarios/make_investment_presets.py) ---,,,,")
        for var, idx, val in rows:
            new.append(f"{var},{t},{idx},,{val!r}")
    out = "\n".join(kept + new) + "\n"
    if dry_run:
        print(f"[dry run] would write {len(new)} lines for {targets} to {PRESETS}")
    else:
        PRESETS.write_text(out, encoding="utf-8")
        print(f"wrote {len(new)} preset lines for {targets} to {PRESETS} "
              f"({len(kept)} existing lines kept)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", required=True, help="finished scenario folder under output/")
    ap.add_argument("--target", action="append", required=True,
                    help="scenario name(s) in scen_to_run that get the fixed investments")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    folder = REPO / "output" / args.base
    o = load_base(folder)
    rows, checks = build_rows(o)
    chk = pd.DataFrame(checks)
    chk_path = folder / "investment_presets_check.csv"
    if not args.dry_run:
        chk.to_csv(chk_path, index=False)
    n_nonzero = sum(1 for _, _, v in rows if v > 0)
    print(f"{len(rows)} investment variables from {args.base}: {n_nonzero} non-zero, "
          f"{len(chk)} values clipped or zeroed (see {chk_path.name})")
    if len(chk):
        big = chk.loc[chk["change"].abs() > 1e-3]
        print(f"  clips larger than 1e-3: {len(big)}")
        if len(big):
            print(big.to_string(index=False))
    write_presets(rows, args.target, args.dry_run)


if __name__ == "__main__":
    main()
