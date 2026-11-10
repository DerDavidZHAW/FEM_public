"""
Per-(node, hour) price attribution from post-model CSV outputs.

For each (node, t) in a given (scenario, sub_scenario), identify the cause
and the price-setting plant behind the electricity price in
``energy_balance_dual.csv``:

* ``lost_load``           lostload[c, t, step, s] > TOL at some consumer of node
* ``curtailment``         curtailment[c, t, s] > TOL AND |price| < TOL
* ``marginal_thermal``    a partially-loaded dispatchable plant matches; the
                          tech name (nuclear, gas, ...) is reported
* ``storage_replacement`` special tag when the matched plant is the synthetic
                          backup added by switch_storage=False (300 CHF/MWh)
* ``unresolved``          no partial-load plant matched the price within TOL

Plants in price-coupled neighbour nodes (dual within TOL of the target) are
included in the search, so the price-setter may sit in a neighbour.

Usage:
    Edit the CONFIGURATION block below, then run:  python price_attribution.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================================
# CONFIGURATION
# ============================================================================
SCENARIO = "2050_100_inv_Chbat_wy1995_nothing"
SUB_SCENARIO = "2050_100_inv_Chbat_wy1995_nothing_wy1995"
# ============================================================================

TOL = 0.001  # CHF/MWh tolerance for coupling, curtailment, MC matching


def read_filtered(path: Path, sub_scen: str | None = None) -> pd.DataFrame:
    """Read a CSV; if 'Scenarios' column is present, filter by sub_scen."""
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()
    if df.empty:
        return df
    if sub_scen is not None and "Scenarios" in df.columns:
        df = df[df["Scenarios"] == sub_scen].copy()
    return df


def parse_wide_node_csv(path: Path) -> dict[str, list[str]]:
    """Parse files like Map_node_plant.csv where each row is
    ``Node, value, 1, 2, 3, ...`` with line/plant names spread across cols.
    """
    result: dict[str, list[str]] = {}
    if not path.exists() or path.stat().st_size == 0:
        return result
    df = pd.read_csv(path)
    for _, row in df.iterrows():
        node = row.iloc[0]
        vals = [v for v in row.iloc[1:].tolist()
                if pd.notna(v) and str(v).strip() != ""]
        result[str(node)] = [str(v) for v in vals]
    return result


def main(scenario: str = SCENARIO, sub_scenario: str = SUB_SCENARIO) -> None:
    """Build the price-attribution CSV for one (scenario, sub_scenario).

    Defaults come from the CONFIGURATION block at the top of this file. Can
    also be imported and called with explicit arguments from elsewhere.
    """
    scen, sub = scenario, sub_scenario
    out_dir = Path("output") / scen
    if not out_dir.exists():
        print(f"ERROR: output dir not found: {out_dir}", file=sys.stderr)
        sys.exit(1)

    # Weight in objective function (price = dual / weight)
    settings = pd.read_csv(out_dir / "settings.csv", index_col=0)
    if sub not in settings.columns:
        print(f"ERROR: sub_scenario {sub} not in {out_dir / 'settings.csv'}",
              file=sys.stderr)
        sys.exit(1)
    weight = float(settings.loc["weight_in_objective_fcn", sub])
    print(f"Reading from {out_dir}  (weight = {weight})")

    # Plant maps ------------------------------------------------------------
    plants_by_node = parse_wide_node_csv(out_dir / "Map_node_plant.csv")
    mpt = pd.read_csv(out_dir / "Map_plant_tech.csv")
    map_plant_tech = dict(zip(mpt.iloc[:, 0].astype(str),
                              mpt.iloc[:, -1].astype(str)))

    # Per-plant data --------------------------------------------------------
    op_slp = read_filtered(out_dir / "operation_slp.csv", sub)
    gen_max = read_filtered(out_dir / "gen_max.csv", sub)
    op_slp_dict = dict(zip(op_slp.iloc[:, 0], op_slp["value"]))
    gen_max_dict = dict(zip(gen_max.iloc[:, 0], gen_max["value"]))

    # Per-plant per-hour data ----------------------------------------------
    gen = read_filtered(out_dir / "gen.csv", sub)
    avail = read_filtered(out_dir / "avail_plant.csv", sub)
    plant_col_gen = gen.columns[0]
    plant_col_av = avail.columns[0]
    gen_lookup = {(r[plant_col_gen], r["T"]): r["value"]
                  for _, r in gen.iterrows()}
    avail_lookup = {(r[plant_col_av], r["T"]): r["value"]
                    for _, r in avail.iterrows()}

    # Lost load & curtailment aggregated per (node, t) ---------------------
    def aggregate_by_node_t(df: pd.DataFrame) -> dict[tuple[str, str], float]:
        if df.empty:
            return {}
        consumer_col = df.columns[0]
        df = df.copy()
        df["node"] = df[consumer_col].astype(str).str.split("_").str[0]
        return df.groupby(["node", "T"])["value"].sum().to_dict()

    ll_per_nt = aggregate_by_node_t(
        read_filtered(out_dir / "lostload.csv", sub))
    cur_per_nt = aggregate_by_node_t(
        read_filtered(out_dir / "curtailment.csv", sub))

    # Prices ----------------------------------------------------------------
    eb = read_filtered(out_dir / "energy_balance_dual.csv", sub)
    if eb.empty:
        print(f"ERROR: no energy_balance_dual data for sub_scenario {sub}",
              file=sys.stderr)
        sys.exit(1)
    eb = eb.copy()
    eb["price"] = eb["value"] / weight

    # Coupled-node sets per t (nodes whose price is within TOL of each other)
    coupled_per_t: dict[str, dict[str, list[str]]] = {}
    for t, grp in eb.groupby("T"):
        nodes_t = grp["Node"].tolist()
        prices_t = grp["price"].tolist()
        pool_for_node: dict[str, list[str]] = {}
        for i, n_i in enumerate(nodes_t):
            pool_for_node[n_i] = [
                nodes_t[j] for j in range(len(nodes_t))
                if abs(prices_t[j] - prices_t[i]) < TOL
            ]
        coupled_per_t[t] = pool_for_node

    # Attribution per (node, t) --------------------------------------------
    out_rows: list[dict] = []
    for _, row in eb.iterrows():
        node = str(row["Node"])
        t = str(row["T"])
        try:
            hour = int(t.split("_")[1])
        except (IndexError, ValueError):
            hour = -1
        price = float(row["price"])

        # 1. Lost load -----------------------------------------------------
        ll_val = ll_per_nt.get((node, t), 0.0)
        if ll_val > TOL:
            out_rows.append({
                "Node": node, "T": t, "Hour": hour,
                "Price_CHFperMWh": price,
                "Cause": "lost_load", "Plant": "", "Tech": "",
                "Marginal_Cost": np.nan,
                "Coupled_With": "",
                "Notes": f"sum lostload at node = {ll_val:.2f} MWh",
            })
            continue

        # 2. Curtailment (price ~ 0 AND curtailment > tol) -----------------
        cur_val = cur_per_nt.get((node, t), 0.0)
        if cur_val > TOL and abs(price) < TOL:
            out_rows.append({
                "Node": node, "T": t, "Hour": hour,
                "Price_CHFperMWh": price,
                "Cause": "curtailment", "Plant": "", "Tech": "",
                "Marginal_Cost": np.nan,
                "Coupled_With": "",
                "Notes": f"sum curtailment at node = {cur_val:.2f} MWh",
            })
            continue

        # 3. Marginal-plant search across the price-coupled pool -----------
        pool = coupled_per_t.get(t, {}).get(node, [node])
        candidates: list[dict] = []
        for cn in pool:
            for plant in plants_by_node.get(cn, []):
                # Must be a generator (has an operation_slp entry).
                if plant not in op_slp_dict:
                    continue
                g = gen_lookup.get((plant, t), 0.0)
                gm = gen_max_dict.get(plant, 0.0)
                av = avail_lookup.get((plant, t), 1.0)
                cap = gm * av
                # Partially loaded — neither off nor at the (avail-adjusted) cap.
                if g > TOL and (cap - g) > TOL:
                    candidates.append({
                        "plant": plant, "node": cn,
                        "tech": map_plant_tech.get(plant, ""),
                        "mc": float(op_slp_dict[plant]),
                        "gen": g, "cap": cap,
                    })

        if candidates:
            best = min(candidates, key=lambda c: abs(c["mc"] - price))
            cause = ("storage_replacement"
                     if best["tech"] == "storage_replacement"
                     else "marginal_thermal")
            coupled_other = sorted({c["node"] for c in candidates
                                    if c["node"] != node})
            out_rows.append({
                "Node": node, "T": t, "Hour": hour,
                "Price_CHFperMWh": price,
                "Cause": cause,
                "Plant": best["plant"], "Tech": best["tech"],
                "Marginal_Cost": best["mc"],
                "Coupled_With": ",".join(coupled_other),
                "Notes": (f"gen={best['gen']:.1f}/cap={best['cap']:.1f} MW, "
                          f"|MC-price|={abs(best['mc']-price):.4f}"),
            })
        else:
            out_rows.append({
                "Node": node, "T": t, "Hour": hour,
                "Price_CHFperMWh": price,
                "Cause": "unresolved", "Plant": "", "Tech": "",
                "Marginal_Cost": np.nan,
                "Coupled_With": ",".join(sorted(set(pool) - {node})),
                "Notes": f"no partial-load plant in pool of {len(pool)} nodes",
            })

    out_df = (pd.DataFrame(out_rows)
              .sort_values(["Hour", "Node"])
              .reset_index(drop=True))
    out_path = out_dir / f"price_attribution_{sub}.csv"
    out_df.to_csv(out_path, index=False)
    print(f"\nWrote {len(out_df)} rows to {out_path}")
    print("\nCause distribution:")
    print(out_df["Cause"].value_counts().to_string())

    # Show a quick breakdown of which techs are setting the price (only for
    # marginal_thermal/storage_replacement causes).
    tech_breakdown = (out_df[out_df["Cause"].isin(
        ["marginal_thermal", "storage_replacement"])]
        .groupby("Tech").size().sort_values(ascending=False))
    if not tech_breakdown.empty:
        print("\nPrice-setting tech distribution:")
        print(tech_breakdown.to_string())


if __name__ == "__main__":
    main()
