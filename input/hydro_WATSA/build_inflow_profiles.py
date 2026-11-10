"""
Build weekly natural-inflow profiles per hydro cluster for the FEM
weather years (default 1995, 2008, 2009), for every cluster budget n
produced by cluster_hydro_plants.py.

Method (three layers, decided 2026-07-31)
-----------------------------------------
SHAPE   from observed near-natural donor catchments (CAMELS-CH,
        observation-based daily discharge) in the actual calendar
        weather years. Each dam / psp_open plant is matched to its
        SINGLE most similar donor by |intake altitude - catchment mean
        elevation| and horizontal distance (user decision 2026-08-03:
        one donor keeps the full weather variability of a real
        catchment; --n-donors restores blending if ever wanted). FEM's timemap re-wraps calendar years to the
        hydrological year (Oct-Sep), so profiles are calendar-year.
SPLIT   plant shapes are aggregated to each cluster (any n) weighted
        by the plant's NATURAL annual inflow energy = WASTA expected
        generation minus PUMP_RT * pump demand (pumped-through energy
        is not natural inflow). PUMP_RT = 0.87 x 0.87 = 0.757,
        consistent with FEM's turbine and pump efficiencies.
LEVEL   the national weekly total is NOT taken from the gauges: every
        weekly cluster value is scaled by a common weekly factor f(w)
        so that the sum over clusters reproduces the PECD CH00 weekly
        inflow of that weather year exactly (TYNDP consistency with
        the neighbours). f(w) is reported as a diagnostic: it measures
        how much the gauge-based national shape disagrees with PECD.

Donor selection (near-natural): CAMELS-CH catchments in CH with
hp_count = 0, reservoir_cap = 0, not a lake outlet, excluding gauges
2446/2447/2327 (readme), <= 5% missing discharge in every used
weather year, and a strictly positive annual discharge volume in
every used year (gauge 2079 Le Prese reports 0.0 for all of 1995 --
bad data coded as zeros, caught 2026-08-03).

Inputs:  camels_ch/ (static_attributes + timeseries/observation_based),
         hydro_plants_individual.csv, WASTA_2026_plants.csv,
         cluster_sweep/hydro_plants_clustered_n{N}.csv,
         ../hydro_PECD/PECD_EERA2021_reservoir_pumping_2030_inflow.parquet
Outputs (inflow_profiles/):
         cluster_inflow_weekly.csv   n_total, cluster_name, weather_year,
                                     week, inflow_GWh
         inflow_shares.csv           n_total, cluster_name, inflow_share
         plant_donor_map.csv         plant -> donors, weights, distances
         reconciliation_factors.csv  weather_year, week, f
         inflow_profiles_n{N_FIG}.png, reconciliation.png

Usage:  python input/hydro_WATSA/build_inflow_profiles.py
        [--years 1995 2008 2009] [--n-donors 1] [--pump-rt 0.7569]
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import patheffects

FOLDER = Path(__file__).parent
CAMELS = FOLDER / "camels_ch"
SWEEP = FOLDER / "cluster_sweep"
PECD_FILE = (FOLDER.parent / "hydro_PECD" / "PECD_EERA2021_reservoir_pumping_2030_inflow.parquet")
if not PECD_FILE.exists():  # cloud run: staged location
    PECD_FILE = Path("/mnt/user-data/uploads/Future_Markets/input/hydro_PECD/PECD_EERA2021_reservoir_pumping_2030_inflow.parquet")
OUT_DIR = FOLDER / "inflow_profiles"

EXCLUDE_GAUGES = {2446, 2447, 2327}   # readme.txt recommendations
MAX_MISSING = 0.05                    # per weather year
ELEV_SCALE_M = 300.0                  # matching score scales
DIST_SCALE_M = 50_000.0
N_FIG = 12                            # cluster count shown in the figure

# dataviz reference palette
BLUE_RAMP = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
             "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
COL_PSP_OPEN = "#eb6834"
SURFACE, INK, INK_2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"


def ramp(k):
    if k == 1:
        return ["#2a78d6"]
    idx = np.linspace(0, len(BLUE_RAMP) - 1, k).round().astype(int)
    return [BLUE_RAMP[i] for i in idx]


def week_of_year(dates):
    """Fixed 53-week convention: week = (day_of_year - 1) // 7 + 1,
    matching the 53-week PECD series (week 53 = 1-2 days)."""
    return (dates.dt.dayofyear - 1) // 7 + 1


def load_donors(years):
    att = CAMELS / "static_attributes"
    topo = pd.read_csv(att / "CAMELS_CH_topographic_attributes.csv",
                       encoding="latin-1", skiprows=1)
    hum = pd.read_csv(att / "CAMELS_CH_humaninfluence_attributes.csv",
                      encoding="latin-1", skiprows=1)
    gla = pd.read_csv(att / "CAMELS_CH_glacier_attributes.csv",
                      encoding="latin-1", skiprows=1)
    m = topo.merge(hum, on="gauge_id").merge(gla, on="gauge_id", how="left")
    cand = m[(m.country == "CH")
             & (m.hp_count.fillna(0) == 0)
             & (m.reservoir_cap.fillna(0) == 0)
             & (m.water_body_type != "lake")
             & (~m.gauge_id.isin(EXCLUDE_GAUGES))].copy()

    shapes, kept = {}, []
    for _, g in cand.iterrows():
        f = CAMELS / "timeseries" / "observation_based" / \
            f"CAMELS_CH_obs_based_{int(g.gauge_id)}.csv"
        if not f.exists():
            continue
        ts = pd.read_csv(f, usecols=["date", "discharge_vol(m3/s)"],
                         parse_dates=["date"], encoding="latin-1")
        ts = ts[ts.date.dt.year.isin(years)]
        ok, yearly = True, {}
        for y in years:
            s = ts[ts.date.dt.year == y].copy()
            if (len(s) < 365
                    or s["discharge_vol(m3/s)"].isna().mean() > MAX_MISSING
                    or s["discharge_vol(m3/s)"].fillna(0).sum() <= 0):
                ok = False   # incomplete, or a bogus all-zero year (e.g. 2079 in 1995)
                break
            s["week"] = week_of_year(s.date)
            wk = s.groupby("week")["discharge_vol(m3/s)"].mean()  # mean flow/wk
            wk = wk * np.array([7] * 52 + [len(s) - 364])          # ~volume
            yearly[y] = (wk / wk.sum()).reindex(range(1, 54)).fillna(0.0)
        if ok:
            shapes[int(g.gauge_id)] = yearly
            kept.append(g)
    donors = pd.DataFrame(kept)
    print(f"donor gauges: {len(donors)} of {len(cand)} candidates pass "
          f"completeness in {years}")
    return donors, shapes


def match_plants(donors, pump_rt, n_donors=1):
    plants = pd.read_csv(FOLDER / "hydro_plants_individual.csv")
    wa = pd.read_csv(FOLDER / "WASTA_2026_plants.csv")
    m = plants.merge(
        wa[["wasta_id", "expected_gen_year_GWh", "pump_demand_year_GWh",
            "max_net_head_m", "max_gross_head_m", "turbine_axis_masl",
            "coord_E", "coord_N"]], on="wasta_id", how="left")
    m["size_MW"] = m[["power_capacity_MW", "pump_capacity_MW"]].max(axis=1)
    m = m[m.size_MW > 0].copy()
    if "category" not in m.columns:  # fallback for old plant tables
        m["sh"] = 1000 * m.storage_capacity_GWh / m.size_MW
        m["category"] = np.where(
            m.type.isin(["dam", "psp_open", "psp_close"])
            & (m.power_capacity_MW > 0) & (m.sh < 24), "ror", m.type)
        m.loc[(m.power_capacity_MW <= 0) & (m.pump_capacity_MW > 0),
              "category"] = "pump_station"
    m = m[m.category.isin(["dam", "psp_open"])].copy()

    head = m.max_gross_head_m.fillna(m.max_net_head_m)
    m["intake_alt"] = (m.turbine_axis_masl + head)
    m["intake_alt"] = m.intake_alt.fillna(m.intake_alt.median())
    m["nat_inflow_GWh"] = (m.expected_gen_year_GWh.fillna(0)
                           - pump_rt * m.pump_demand_year_GWh.fillna(0)
                           ).clip(lower=0)

    de = donors.set_index("gauge_id")
    rows = []
    for _, p in m.iterrows():
        delev = (de.elev_mean - p.intake_alt).abs() / ELEV_SCALE_M
        dist = np.sqrt((de.gauge_easting - p.coord_E) ** 2
                       + (de.gauge_northing - p.coord_N) ** 2) / DIST_SCALE_M
        dist = dist.fillna(dist.median())
        score = delev ** 2 + dist ** 2
        best = score.nsmallest(n_donors)
        w = 1.0 / (0.1 + best)
        w = w / w.sum()
        rows.append({"name": p["name"], "wasta_id": p.wasta_id,
                     "category": p.category, "intake_alt": p.intake_alt,
                     "nat_inflow_GWh": p.nat_inflow_GWh,
                     "donors": list(best.index.astype(int)),
                     "donor_weights": list(w.round(3)),
                     "donor_names": list(de.loc[best.index, "gauge_name"]),
                     "donor_elevs": list(de.loc[best.index, "elev_mean"].round(0)),
                     "worst_delev_m": float((de.loc[best.index, "elev_mean"]
                                             - p.intake_alt).abs().max())})
    return m, pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, nargs="+", default=[1995, 2008, 2009])
    parser.add_argument("--pump-rt", type=float, default=0.87 * 0.87)  # FEM: 87% turbine x 87% pump
    parser.add_argument("--n-donors", type=int, default=1)
    args = parser.parse_args()
    OUT_DIR.mkdir(exist_ok=True)

    donors, shapes = load_donors(args.years)
    plants, dmap = match_plants(donors, args.pump_rt, args.n_donors)
    dmap.to_csv(OUT_DIR / "plant_donor_map.csv", index=False, encoding="utf-8-sig")
    print(f"matched {len(dmap)} plants; worst donor elevation mismatch "
          f"{dmap.worst_delev_m.max():.0f} m "
          f"(p90 {dmap.worst_delev_m.quantile(.9):.0f} m)")

    # plant-level weekly shapes (blend of donor shapes), per weather year
    plant_shape = {}   # (wasta_id, year) -> np.array(53)
    for _, r in dmap.iterrows():
        for y in args.years:
            s = sum(w * shapes[g][y].to_numpy()
                    for g, w in zip(r.donors, r.donor_weights))
            if not np.isfinite(s).all() or s.sum() <= 0:
                raise RuntimeError(
                    f"degenerate {y} shape for plant {r['name']} "
                    f"(donors {r.donors}) - check donor completeness gate")
            plant_shape[(r.wasta_id, y)] = s / s.sum()

    # PECD CH00 weekly anchor (all natural inflow sits under pumped_open)
    pecd = pd.read_parquet(PECD_FILE)
    pecd["year"] = pecd.year.astype(int)
    anchor = pecd[(pecd.area_name == "CH00")
                  & (pecd.technology == "pumped_open")
                  & (pecd.year.isin(args.years))]
    anchor = (anchor.assign(week=anchor.Week.astype(int))
              .set_index(["year", "week"]).inflow_GWh)

    # cluster aggregation for every clustered file in the sweep
    weight = dmap.set_index("wasta_id").nat_inflow_GWh
    out, shares_out, recon_out = [], [], {}
    for f in sorted(SWEEP.glob("hydro_plants_clustered_n*.csv"),
                    key=lambda p: int(p.stem.rsplit("n", 1)[1])):
        n_total = int(f.stem.rsplit("n", 1)[1])
        cl = pd.read_csv(f)
        cl = cl[cl.category.isin(["dam", "psp_open"])]
        cl = cl.merge(weight.rename("w"), left_on="wasta_id", right_index=True)
        a_share = cl.groupby("cluster_name").w.sum() / cl.w.sum()
        for c, s in a_share.items():
            shares_out.append({"n_total": n_total, "cluster_name": c,
                               "inflow_share": round(s, 4)})
        for y in args.years:
            ann = anchor.loc[y].sum()
            cs = {}
            for cname, grp in cl.groupby("cluster_name"):
                if grp.w.sum() <= 0:   # pure pump stations: no natural inflow
                    cs[cname] = np.zeros(53)
                    continue
                s = sum(plant_shape[(wid, y)] * w
                        for wid, w in zip(grp.wasta_id, grp.w))
                cs[cname] = s / s.sum()
            # national gauge-implied weekly total vs PECD -> f(w)
            g_nat = sum(cs[c] * a_share[c] for c in cs)
            p_wk = anchor.loc[y].reindex(range(1, 54)).fillna(0).to_numpy()
            f_w = np.divide(p_wk / p_wk.sum(), g_nat,
                            out=np.ones(53), where=g_nat > 0)
            recon_out[(n_total, y)] = f_w
            for cname in cs:
                inGWh = cs[cname] * f_w * a_share[cname] * ann
                for wk in range(53):
                    out.append({"n_total": n_total, "cluster_name": cname,
                                "weather_year": y, "week": wk + 1,
                                "inflow_GWh": round(float(inGWh[wk]), 4)})

    res = pd.DataFrame(out)
    res.to_csv(OUT_DIR / "cluster_inflow_weekly.csv", index=False,
               encoding="utf-8-sig")
    pd.DataFrame(shares_out).to_csv(OUT_DIR / "inflow_shares.csv",
                                    index=False, encoding="utf-8-sig")

    # reconciliation diagnostics (f is n-independent up to weighting; store n=N_FIG)
    rec = pd.DataFrame([
        {"weather_year": y, "week": wk + 1, "f": round(float(v[wk]), 4)}
        for (n, y), v in recon_out.items() if n == N_FIG
        for wk in range(53)])
    rec.to_csv(OUT_DIR / "reconciliation_factors.csv", index=False,
               encoding="utf-8-sig")
    print("\nreconciliation factor f(w) [gauge shape vs PECD], n =", N_FIG)
    for y in args.years:
        v = recon_out[(N_FIG, y)]
        print(f"  {y}: median {np.median(v):.2f}, p10 {np.quantile(v, .1):.2f},"
              f" p90 {np.quantile(v, .9):.2f}")

    # per-cluster winter inflow share check (weeks 40-13 ~ Oct-Mar)
    sub = res[res.n_total == N_FIG].copy()
    sub["wint"] = np.where((sub.week >= 40) | (sub.week <= 13),
                           sub.inflow_GWh, 0.0)
    chk = sub.groupby("cluster_name").agg(total=("inflow_GWh", "sum"),
                                          wint=("wint", "sum"))
    chk["winter_share"] = np.where(chk.total > 0,
                                   (chk.wint / chk.total).round(3), 0.0)
    print(f"\nwinter (Oct-Mar) inflow share per cluster, n={N_FIG}, "
          "all years pooled (0.0 = cluster without natural inflow):")
    print(chk[["winter_share"]].to_string())

    make_profile_figure(res, N_FIG, 2008, OUT_DIR / f"inflow_profiles_n{N_FIG}.png")
    make_recon_figure(recon_out, args.years, OUT_DIR / "reconciliation.png")
    print(f"\nwrote outputs to {OUT_DIR.name}/")


def make_profile_figure(res, n_total, year, path):
    sub = res[(res.n_total == n_total) & (res.weather_year == year)]
    dams = sorted([c for c in sub.cluster_name.unique() if c.startswith("dam")],
                  key=lambda c: int(c.rsplit("_", 1)[1]))
    psp = sorted([c for c in sub.cluster_name.unique() if c.startswith("psp")],
                 key=lambda c: int(c.rsplit("_", 1)[1]))
    cols = dict(zip(dams, ramp(len(dams))))
    fig, ax = plt.subplots(figsize=(11, 6.2), facecolor=SURFACE,
                           constrained_layout=True)
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelsize=9)
    for c in dams + psp:
        g = sub[sub.cluster_name == c].sort_values("week")
        col = cols.get(c, COL_PSP_OPEN)
        ax.plot(g.week, g.inflow_GWh, lw=2, color=col, zorder=3)
        pk = g.loc[g.inflow_GWh.idxmax()]
        ax.annotate(c, (pk.week, pk.inflow_GWh), fontsize=8.5,
                    fontweight="bold", color=INK, ha="center",
                    xytext=(0, 6), textcoords="offset points",
                    path_effects=[patheffects.Stroke(linewidth=3,
                                                     foreground=SURFACE),
                                  patheffects.Normal()])
    ax.set_xlabel("week of calendar year", color=INK_2, fontsize=10)
    ax.set_ylabel("inflow [GWh/week]", color=INK_2, fontsize=10)
    ax.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_title(f"Weekly natural inflow per cluster — weather year {year}, "
                 f"n = {n_total}\nreconciled to the PECD CH00 total; "
                 "labels at each cluster's peak week",
                 color=INK, fontsize=12.5, loc="left", pad=12)
    fig.savefig(path, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def make_recon_figure(recon_out, years, path):
    fig, ax = plt.subplots(figsize=(10.5, 4.6), facecolor=SURFACE,
                           constrained_layout=True)
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelsize=9)
    cols = ["#2a78d6", "#eb6834", "#1baf7a"]
    for y, col in zip(years, cols):
        v = recon_out[(N_FIG, y)]
        ax.plot(range(1, 54), v, lw=2, color=col, zorder=3)
        ax.annotate(str(y), (53, v[-1]), fontsize=9, fontweight="bold",
                    color=INK, ha="left",
                    path_effects=[patheffects.Stroke(linewidth=3,
                                                     foreground=SURFACE),
                                  patheffects.Normal()])
    ax.axhline(1.0, color=BASELINE, lw=1.2, zorder=2)
    ax.set_xlabel("week of calendar year", color=INK_2, fontsize=10)
    ax.set_ylabel("f(w) = PECD share / gauge share", color=INK_2, fontsize=10)
    ax.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_title("Reconciliation factor: PECD CH00 weekly shape vs "
                 "gauge-implied national shape\nf = 1 means the two sources "
                 "agree; the factor is applied uniformly across clusters",
                 color=INK, fontsize=12.5, loc="left", pad=12)
    fig.savefig(path, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
