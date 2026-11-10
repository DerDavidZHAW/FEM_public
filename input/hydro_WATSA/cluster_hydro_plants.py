"""
Cluster the Swiss hydro plants of hydro_plants_individual.csv into N
representative plants across the four categories (ror / dam / psp_open /
psp_close), for one or several cluster budgets (default n = 4 .. 20).

Design (decided 2026-07-30, replaces the size/head/altitude feature set)
------------------------------------------------------------------------
Clustering features are ONLY quantities that map to model parameters or
to the inflow profile a cluster will receive:

  log_storage_hours   E/P [h], the storage speed -> water-value dynamics
  summer_infl_share   inflow-regime seasonality PROXY from intake
                      altitude (piecewise-linear over regime bands,
                      glacial ~0.90 ... pluvial ~0.55). Used ONLY to keep
                      clusters hydrologically coherent; the actual
                      profiles come later from gauge data (CAMELS-CH /
                      BAFU, weather years 1995/2008/2009).
  pump_ratio          pump / (pump + turbine) capacity

Size, head and altitude are NOT features (they already entered via the
storage-energy estimation); capacity remains the k-means sample weight
so clusters reflect where the fleet is.

Cluster budget rule (see allocate_budget): every category gets 1
cluster as a representation floor; the remaining n - 4 clusters are
allocated proportionally to each category's share of STORAGE ENERGY
CONTENT [GWh], largest-remainder rounding. Rationale: clusters buy
water-value resolution and water values attach to stored energy, so
capacity- or generation-proportional rules would spend clusters on
run-of-river, whose fixed infeed enters the model only as a sum.

Reclassification: S-type plants with E/P < --min-storage-hours (default
24 h, e.g. Hopflauenen Trift, Innertkirchen 2) are clustered with ror
(fixed infeed); the original WASTA type is kept in the "type" column,
the clustering category in "category".

Cluster naming: dam_1 .. dam_k ordered by aggregate E/P ascending
(dam_1 = fastest storage, dam_k = deepest seasonal storage).

Outputs (cluster_sweep/, one set per budget N + sweep summary):
  hydro_plants_clustered_n{N}.csv       plant table + category, cluster_name
  representative_hydro_plants_n{N}.csv  one row per representative plant
  cluster_scatter_n{N}.png              scatter: E/P vs regime proxy,
                                        point size = capacity

Usage:  python input/hydro_WATSA/cluster_hydro_plants.py
        [--n-clusters 5 6 ... 20] [--min-storage-hours 24] [--seed 42]
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import patheffects
from matplotlib.lines import Line2D
from sklearn.cluster import KMeans

FOLDER = Path(__file__).parent
PLANTS_FILE = FOLDER / "hydro_plants_individual.csv"
WASTA_FILE = FOLDER / "WASTA_2026_plants.csv"
OUT_DIR = FOLDER / "cluster_sweep"

CATEGORIES = ["dam", "ror", "psp_open", "psp_close"]
FEATURES = ["log_storage_hours", "summer_infl_share", "pump_ratio"]

# Inflow-regime seasonality proxy: summer-half-year (Apr-Sep) inflow
# share as a piecewise-linear function of intake altitude. The curve is
# CALIBRATED AT RUNTIME from the WASTA ror plants: run-of-river has no
# storage, so its expected winter/summer generation split observes the
# inflow seasonality directly (uncontaminated by dispatch). Ordinal
# proxy for clustering only -- replaced by gauge profiles per weather
# year. Altitude bin edges for the calibration:
REGIME_CALIB_BINS = [0, 600, 900, 1200, 1500, 1800, 2200, 4000]

# dataviz reference palette (validated 2026-07-30):
# dam clusters = ordinal blue ramp (ordered by E/P), psp_open = orange,
# psp_close = aqua (first-three-slots all-pairs rule); aqua is sub-3:1
# on the light surface -> relief via direct labels on every cluster.
BLUE_RAMP = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
             "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
COL_PSP_OPEN, COL_PSP_CLOSE = "#eb6834", "#1baf7a"
COL_ROR = ["#2a78d6", "#eb6834"]
SURFACE, INK, INK_2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"


def ramp(k):
    """k evenly spaced steps from the ordinal blue ramp, light->dark."""
    if k == 1:
        return ["#2a78d6"]
    idx = np.linspace(0, len(BLUE_RAMP) - 1, k).round().astype(int)
    return [BLUE_RAMP[i] for i in idx]


def load_plants(min_storage_hours):
    plants = pd.read_csv(PLANTS_FILE)
    extras = pd.read_csv(WASTA_FILE)[
        ["wasta_id", "expected_gen_year_GWh", "expected_gen_winter_GWh",
         "max_net_head_m", "max_gross_head_m", "turbine_axis_masl"]
    ]
    plants = plants.merge(extras, on="wasta_id", how="left")
    plants["size_MW"] = plants[["power_capacity_MW", "pump_capacity_MW"]].max(axis=1)
    plants = plants[plants["size_MW"] > 0].copy()

    plants["storage_hours"] = 1000 * plants["storage_capacity_GWh"] / plants["size_MW"]
    plants["log_storage_hours"] = np.log10(1 + plants["storage_hours"])
    plants["pump_ratio"] = (
        plants["pump_capacity_MW"]
        / (plants["pump_capacity_MW"] + plants["power_capacity_MW"]).replace(0, np.nan)
    ).fillna(0.0)

    # intake altitude ~ turbine axis + gross head (top of the penstock)
    head = plants["max_gross_head_m"].fillna(plants["max_net_head_m"])
    plants["intake_alt_masl"] = plants["turbine_axis_masl"] + head
    plants["intake_alt_masl"] = plants.groupby("type")["intake_alt_masl"].transform(
        lambda s: s.fillna(s.median())
    )

    # calibrate the regime curve on ror plants (generation = inflow)
    obs = plants[
        (plants["type"] == "ror")
        & plants["expected_gen_year_GWh"].gt(0)
        & plants["expected_gen_winter_GWh"].notna()
    ].copy()
    obs["s_obs"] = (
        1 - obs["expected_gen_winter_GWh"] / obs["expected_gen_year_GWh"]
    ).clip(0.05, 0.95)
    grp = obs.groupby(
        pd.cut(obs["intake_alt_masl"], REGIME_CALIB_BINS), observed=True
    ).apply(
        lambda g: pd.Series({
            "alt": np.average(g["intake_alt_masl"], weights=g["size_MW"]),
            "share": np.average(g["s_obs"], weights=g["size_MW"]),
        }),
        include_groups=False,
    ).sort_values("alt")
    nodes_alt = grp["alt"].to_numpy()
    # enforce monotone increase (smooths small-sample dips at high alt)
    nodes_share = np.maximum.accumulate(grp["share"].to_numpy())
    plants["summer_infl_share"] = np.interp(
        plants["intake_alt_masl"], nodes_alt, nodes_share
    )
    print("Regime curve calibrated on ror plants (alt [m] -> summer share): "
          + ", ".join(f"{a:.0f}->{s:.2f}" for a, s in zip(nodes_alt, nodes_share)))

    # model category: single source of truth is the "category" column of
    # hydro_plants_individual.csv (zero/near-zero-storage plants -> ror,
    # see build_individual_plant_table.py). Fallback for old tables:
    if "category" not in plants.columns:
        plants["category"] = plants["type"]
        reclass = ((plants["type"].isin(["dam", "psp_open", "psp_close"]))
                   & (plants["power_capacity_MW"] > 0)
                   & (plants["storage_hours"] < min_storage_hours))
        plants.loc[reclass, "category"] = "ror"
        print("WARNING: no 'category' column in the plant table -- "
              "derived it locally; re-run build_individual_plant_table.py")
    # pump-only transfer stations (category "pump_station") are not
    # clustered, but their pump capacity is added back to the psp_open
    # clusters below (FEM/PECD parity: PECD counts these 227 MW inside
    # its pumped_open aggregate, so dropping them would silently shrink
    # the model's pumping vs today)
    transfer_pump_MW = plants.loc[
        plants["category"] == "pump_station", "pump_capacity_MW"].sum()
    n0 = len(plants)
    plants = plants[plants["category"].isin(CATEGORIES)].copy()
    if n0 - len(plants):
        print(f"Excluded {n0 - len(plants)} pump-only transfer station(s) "
              f"from clustering; their {transfer_pump_MW:,.0f} MW pumps are "
              "re-attributed to the psp_open clusters (storage-weighted)")
    return plants, transfer_pump_MW


def allocate_budget(plants, n_total):
    """Cluster budget rule: every category present gets 1 cluster as a
    representation floor; the remaining clusters are allocated
    proportionally to each category's share of STORAGE ENERGY CONTENT
    [GWh], largest-remainder rounding.

    Rationale: clusters buy water-value resolution, and water values
    attach to stored energy. Capacity or generation shares would
    allocate clusters to run-of-river, whose fixed infeed enters the
    model only as a sum, so extra ror clusters cannot change results.
    """
    E = plants.groupby("category")["storage_capacity_GWh"].sum()
    E = E.reindex([c for c in CATEGORIES if c in E.index])
    if n_total < len(E):
        raise ValueError(f"n_clusters={n_total} < {len(E)} categories")
    rest = n_total - len(E)
    quota = E / E.sum() * rest
    base = np.floor(quota).astype(int)
    rem = quota - base
    while base.sum() < rest:
        i = rem.idxmax()
        base[i] += 1
        rem[i] = -1.0
    return (base + 1).to_dict()


def cluster_category(sub, k, seed, cat):
    """Weighted k-means; returns ranks 1..k ordered by aggregate E/P.

    ror clusters on the regime proxy alone: run-of-river is fixed infeed
    in the model, so only the inflow shape differentiates its clusters
    (an E/P split would separate river impoundments, which the model
    cannot use anyway)."""
    if k <= 1 or len(sub) <= k:
        return np.ones(len(sub), dtype=int)
    pool = ["summer_infl_share"] if cat == "ror" else FEATURES
    feats = [f for f in pool if sub[f].std() > 1e-9]
    X = (sub[feats] - sub[feats].mean()) / sub[feats].std()
    km = KMeans(n_clusters=k, n_init=20, random_state=seed)
    labels = km.fit_predict(X.values, sample_weight=sub["size_MW"].values)
    if cat == "ror":  # _1 = lowland/pluvial, _2 = alpine/melt-driven
        agg = sub.assign(lab=labels).groupby("lab").apply(
            lambda g: np.average(g["summer_infl_share"], weights=g["size_MW"]),
            include_groups=False,
        )
    else:
        agg = sub.assign(lab=labels).groupby("lab").apply(
            lambda g: 1000 * g["storage_capacity_GWh"].sum()
            / max(g["size_MW"].sum(), 1e-9),
            include_groups=False,
        )
    order = agg.sort_values().index  # ascending: _1 = fastest / lowest
    rank = {lab: i + 1 for i, lab in enumerate(order)}
    return np.array([rank[lab] for lab in labels])


def make_scatter(plants, n_total, path):
    storage = plants[plants["category"].isin(["dam", "psp_open", "psp_close"])]
    ror = plants[plants["category"] == "ror"]
    dam_ranks = sorted(storage.loc[storage["category"] == "dam", "cluster_rank"].unique())
    dam_cols = dict(zip(dam_ranks, ramp(len(dam_ranks))))

    fig, (ax, axr) = plt.subplots(
        2, 1, figsize=(11.5, 8.2), height_ratios=[4.4, 1.0],
        facecolor=SURFACE, constrained_layout=True)
    for a in (ax, axr):
        a.set_facecolor(SURFACE)
        for s in a.spines.values():
            s.set_color(BASELINE)
        a.tick_params(colors=MUTED, labelsize=9)

    def color_of(row):
        if row["category"] == "psp_open":
            return COL_PSP_OPEN
        if row["category"] == "psp_close":
            return COL_PSP_CLOSE
        return dam_cols[row["cluster_rank"]]

    x = storage["storage_hours"].clip(lower=8)
    sizes = 14 + storage["size_MW"] / 8
    marker_map = {"dam": "o", "psp_open": "D", "psp_close": "s"}
    for cat, mk in marker_map.items():
        s = storage[storage["category"] == cat]
        ax.scatter(x.loc[s.index], s["summer_infl_share"], s=sizes.loc[s.index],
                   c=[color_of(r) for _, r in s.iterrows()], marker=mk,
                   alpha=0.9, edgecolors=SURFACE, linewidths=1.0, zorder=3)

    # direct label at each cluster's capacity-weighted centroid (relief rule)
    label_dy = {"psp_close": 0.018, "psp_open": -0.018}
    for cname, grp in storage.groupby("cluster_name"):
        w = grp["size_MW"]
        cx = 10 ** np.average(np.log10(grp["storage_hours"].clip(lower=8)), weights=w)
        cy = np.average(grp["summer_infl_share"], weights=w)
        cy += label_dy.get(grp["category"].iloc[0], 0.0)
        ax.annotate(cname, (cx, cy), fontsize=9, fontweight="bold", color=INK,
                    ha="center", va="center", zorder=5,
                    path_effects=[patheffects.Stroke(linewidth=3, foreground=SURFACE),
                                  patheffects.Normal()])

    ax.set_xscale("log")
    ticks = [24, 168, 720, 2190, 8760]
    ax.set_xticks(ticks)
    ax.set_xticklabels(["1 d", "1 w", "1 mo", "3 mo", "1 y"])
    ax.grid(True, which="major", color=GRID, lw=0.8, zorder=0)
    ax.set_xlabel("storage speed E/P (log)", color=INK_2, fontsize=10)
    ax.set_ylabel("summer inflow share (regime proxy)", color=INK_2, fontsize=10)
    ax.set_title(
        f"Swiss hydro fleet clustered into {n_total} representative plants\n"
        "storage plants: position = E/P × inflow regime, area = capacity",
        color=INK, fontsize=12.5, loc="left", pad=12)

    handles = []
    cat_order = {"dam": 0, "psp_open": 1, "psp_close": 2}
    keys = sorted(
        storage.groupby("cluster_name").groups,
        key=lambda c: (cat_order[storage.loc[storage["cluster_name"] == c,
                                             "category"].iloc[0]],
                       int(c.rsplit("_", 1)[1])))
    for cname in keys:
        grp = storage[storage["cluster_name"] == cname]
        cat = grp["category"].iloc[0]
        col = COL_PSP_OPEN if cat == "psp_open" else (
            COL_PSP_CLOSE if cat == "psp_close" else dam_cols[grp["cluster_rank"].iloc[0]])
        agg = 1000 * grp["storage_capacity_GWh"].sum() / grp["size_MW"].sum()
        handles.append(Line2D(
            [], [], linestyle="", marker=marker_map[cat], markersize=8,
            markerfacecolor=col, markeredgecolor=SURFACE,
            label=f"{cname}  ·  {grp['size_MW'].sum():,.0f} MW, "
                  f"{grp['storage_capacity_GWh'].sum():,.0f} GWh, E/P {agg:,.0f} h"))
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5),
              frameon=False, fontsize=8.4, labelcolor=INK_2)

    # ror strip: regime proxy only (E/P is ~0 for run-of-river)
    rng = np.random.default_rng(0)
    jitter = rng.uniform(-0.3, 0.3, len(ror))
    rr = sorted(ror["cluster_rank"].unique())
    rcols = dict(zip(rr, COL_ROR))
    axr.scatter(ror["summer_infl_share"], jitter, s=8 + ror["size_MW"] / 8,
                c=[rcols[r] for r in ror["cluster_rank"]], alpha=0.75,
                edgecolors=SURFACE, linewidths=0.6, zorder=3)
    for cname, grp in ror.groupby("cluster_name"):
        cx = np.average(grp["summer_infl_share"], weights=grp["size_MW"])
        axr.annotate(cname, (cx, 0.42), fontsize=9, fontweight="bold", color=INK,
                     ha="center",
                     path_effects=[patheffects.Stroke(linewidth=3, foreground=SURFACE),
                                   patheffects.Normal()])
    axr.set_ylim(-0.55, 0.55)
    axr.set_yticks([])
    axr.grid(True, axis="x", color=GRID, lw=0.8, zorder=0)
    axr.set_xlabel("summer inflow share (regime proxy) — run-of-river plants, "
                   "area = capacity", color=INK_2, fontsize=10)

    fig.savefig(path, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def representative_table(plants, transfer_pump_MW=0.0):
    reps = []
    for cname, grp in plants.groupby("cluster_name"):
        gen = grp["expected_gen_year_GWh"].sum()
        w = grp["size_MW"]
        reps.append({
            "cluster_name": cname,
            "category": grp["category"].iloc[0],
            "n_plants": len(grp),
            "power_capacity_MW": grp["power_capacity_MW"].sum(),
            "pump_capacity_MW": grp["pump_capacity_MW"].sum(),
            "storage_capacity_GWh": grp["storage_capacity_GWh"].sum(),
            "agg_storage_hours": 1000 * grp["storage_capacity_GWh"].sum() / w.sum(),
            "expected_gen_GWh_a": gen,
            "summer_infl_share_regime": (w * grp["summer_infl_share"]).sum() / w.sum(),
            "mean_intake_alt_masl": (w * grp["intake_alt_masl"]).sum() / w.sum(),
            "largest_plants": "; ".join(grp.nlargest(3, "size_MW")["name"]),
        })
    reps = pd.DataFrame(reps)
    # transfer-station pumps -> psp_open clusters, storage-weighted
    po = reps["category"] == "psp_open"
    if transfer_pump_MW > 0 and po.any():
        w = reps.loc[po, "storage_capacity_GWh"]
        w = w / w.sum() if w.sum() > 0 else 1.0 / po.sum()
        reps.loc[po, "pump_capacity_MW"] += (transfer_pump_MW * w).round(3)
    inflow = reps["category"].isin(["dam", "psp_open"])
    reps["inflow_share_suggestion"] = np.where(
        inflow,
        reps["expected_gen_GWh_a"] / reps.loc[inflow, "expected_gen_GWh_a"].sum(),
        np.nan)
    order = {"dam": 0, "psp_open": 1, "psp_close": 2, "ror": 3}
    reps["o"] = reps["category"].map(order)
    return reps.sort_values(["o", "cluster_name"]).drop(columns="o").round(3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-clusters", type=int, nargs="+",
                        default=list(range(4, 21)))
    parser.add_argument("--min-storage-hours", type=float, default=24.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    base, transfer_pump_MW = load_plants(args.min_storage_hours)

    all_reps = []
    for n_total in args.n_clusters:
        plants = base.copy()
        budget = allocate_budget(base, n_total)
        plants["cluster_rank"] = 0
        for cat in CATEGORIES:
            sub = plants[plants["category"] == cat]
            if sub.empty:
                continue
            plants.loc[sub.index, "cluster_rank"] = cluster_category(
                sub, budget[cat], args.seed, cat)
        plants["cluster_name"] = (
            plants["category"] + "_" + plants["cluster_rank"].astype(str))

        reps = representative_table(plants, transfer_pump_MW)
        all_reps.append(reps.assign(n_total=n_total))
        pl_out = OUT_DIR / f"hydro_plants_clustered_n{n_total}.csv"
        rep_out = OUT_DIR / f"representative_hydro_plants_n{n_total}.csv"
        png_out = OUT_DIR / f"cluster_scatter_n{n_total}.png"
        plants[
            ["idx", "name", "type", "category", "cluster_name",
             "power_capacity_MW", "storage_capacity_GWh", "pump_capacity_MW",
             "storage_hours", "summer_infl_share", "intake_alt_masl",
             "wasta_id", "canton"]
        ].round(3).to_csv(pl_out, index=False, encoding="utf-8-sig")
        reps.to_csv(rep_out, index=False, encoding="utf-8-sig")
        make_scatter(plants, n_total, png_out)

        print(f"\n===== n = {n_total} "
              f"(dam {budget['dam']} / ror {budget['ror']} / "
              f"psp_open {budget['psp_open']} / psp_close {budget['psp_close']}) =====")
        show = reps.drop(columns=["largest_plants", "mean_intake_alt_masl"])
        print(show.to_string(index=False))
        dam = plants[plants["category"] == "dam"]
        spread = dam.groupby("cluster_name")["storage_hours"].agg(
            p10=lambda s: s.quantile(0.1), p90=lambda s: s.quantile(0.9))
        print("dam within-cluster E/P spread [h]:")
        print(spread.round(0).to_string())
        print(f"wrote {pl_out.name}, {rep_out.name}, {png_out.name}")

    sweep = pd.concat(all_reps, ignore_index=True)
    sweep.to_csv(OUT_DIR / "sweep_summary.csv", index=False, encoding="utf-8-sig")
    make_sweep_figure(sweep, OUT_DIR / "sweep_convergence.png")
    print(f"\nwrote sweep_summary.csv, sweep_convergence.png to {OUT_DIR.name}/")


def make_sweep_figure(sweep, path):
    """Dam-class E/P ladder per n: shows where extra clusters stop
    adding distinct storage speeds (the n-selection exhibit)."""
    dams = sweep[sweep["category"] == "dam"]
    ns = sorted(dams["n_total"].unique())
    fig, ax = plt.subplots(figsize=(10.5, 0.42 * len(ns) + 2.2),
                           facecolor=SURFACE, constrained_layout=True)
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelsize=9)
    for n in ns:
        sub = dams[dams["n_total"] == n]
        ax.scatter(sub["agg_storage_hours"].clip(lower=20), [n] * len(sub),
                   s=18 + sub["power_capacity_MW"] / 12, c="#2a78d6",
                   alpha=0.85, edgecolors=SURFACE, linewidths=0.8, zorder=3)
    ax.set_xscale("log")
    ticks = [24, 168, 720, 2190, 8760]
    ax.set_xticks(ticks)
    ax.set_xticklabels(["1 d", "1 w", "1 mo", "3 mo", "1 y"])
    ax.set_yticks(ns)
    ax.grid(True, which="major", color=GRID, lw=0.8, zorder=0)
    ax.set_xlabel("dam-class aggregate E/P (log)", color=INK_2, fontsize=10)
    ax.set_ylabel("total cluster budget n", color=INK_2, fontsize=10)
    ax.set_title("Where extra dam classes land: E/P ladder per cluster budget\n"
                 "one dot per dam class, area = class capacity",
                 color=INK, fontsize=12.5, loc="left", pad=12)
    fig.savefig(path, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
