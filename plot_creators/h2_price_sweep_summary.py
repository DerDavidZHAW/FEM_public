"""Summary of the fixed hydrogen price sweep (scenarios/scen_to_run_H2PRICE.csv).

For every run it reports the Swiss mean price, the electrolyzer volume served
(Europe and CH) against the legacy TYNDP volume, the electrolyzer full-load
hours, how often the Swiss price sits exactly on the electrolyzer bid
(eta x H2 price), a check that the electrolyzer dual equals that bid, and the
price-setter shares from price_setting_plants_count.csv. The legacy base runs
are added as reference rows.

Usage (from the repo root):
    python plot_creators/h2_price_sweep_summary.py
    python plot_creators/h2_price_sweep_summary.py --runs h2fix78_2035_wy2008_12hydro base_2035_wy2008_12hydro

Writes output/h2_price_sweep/h2_price_sweep_summary.csv and
fig_h2_price_sweep.png/.pdf. Needs numpy, pandas, matplotlib.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

GROUPS = ["CH hydro", "CH flexible demand and storage", "CH other", "Abroad", "Zero price"]
GROUP_COLOR = {"CH hydro": "#EDDBAB", "CH flexible demand and storage": "#B08D57",
               "CH other": "#9e9e9e", "Abroad": "#006633", "Zero price": "#d9d9d9"}
INK, MUTED, GRID = "#1f1f1f", "#6b6b6b", "#e4e4e4"


def group_of(tech: str) -> str:
    t = str(tech)
    if t == "Zero price":
        return "Zero price"
    if t.endswith("abroad"):
        return "Abroad"
    if t.startswith(("Reservoir hydro", "Pumped hydro", "Run-of-river")):
        return "CH hydro"
    if t.startswith(("Heat pump", "V2G", "Battery", "Resistive heater", "EV", "DSR", "Electrolyzer")):
        return "CH flexible demand and storage"
    return "CH other"


def read_settings(folder: Path) -> dict:
    s = pd.read_csv(folder / "settings.csv", index_col=0)
    return s.iloc[:, 0].to_dict()


def legacy_volumes(year: int, reduction: float, flh: float) -> tuple:
    """Legacy annual electrolyzer energy (MWh_el) Europe and CH, same inputs as the base runs."""
    from model.data_import_fcns import read_electrolyzer_data
    from model.mappings import Map_TYNDPscenario_short_long
    from scenarios.settings_default import seetings_default_param as S
    T = [f"t_{t}" for t in list(range(6553, 8761)) + list(range(1, 6553))]
    _, _, _, leg = read_electrolyzer_data(
        Map_TYNDPscenario_short_long[S["eu_policy"]], S["ch_policy"], year, S["Node_list_setting"],
        T, 2008, reduction, electrolyzer_flh_target=flh)
    tot = sum(v["energy"][0] for v in leg.values())
    return tot, leg.get("CH00_electrolyzer", {"energy": [np.nan]})["energy"][0]


def summarise(run: str, root: Path) -> dict:
    f = root / "output" / run
    st = read_settings(f)
    year = int(st.get("run_year"))
    price_h2 = st.get("h2_fixed_price", None)
    try:
        price_h2 = float(price_h2)
    except (TypeError, ValueError):
        price_h2 = np.nan
    eta = float(st.get("h2_fixed_price_eta", 0.68) or 0.68)
    reduction = float(st.get("electrolyzer_demand_reduction_coefficient", 1))
    flh = float(st.get("electrolyzer_flh_target", 3000))
    bid = eta * price_h2 if np.isfinite(price_h2) else np.nan

    ps = pd.read_csv(f / "price_setting_plants.csv")
    ps = ps.drop_duplicates("Hour")
    p_ch = ps["Actual Price"]
    row = dict(run=run, year=year, h2_price_CHF_per_MWh_H2=price_h2, bid_CHF_per_MWh_el=bid,
               CH_mean_price=p_ch.mean(), CH_price_std=p_ch.std(),
               share_hours_CH_price_at_bid=float((p_ch.sub(bid).abs() < 0.05).mean()) if np.isfinite(bid) else np.nan)

    leg_tot, leg_ch = legacy_volumes(year, reduction, flh)
    row["legacy_volume_EU_TWh_el"] = leg_tot / 1e6
    row["legacy_volume_CH_TWh_el"] = leg_ch / 1e6
    h2 = f / "h2_steps_result.csv"
    if h2.exists():
        r = pd.read_csv(h2)
        served = r.groupby("plant")["E_served_MWh"].sum()
        row["served_EU_TWh_el"] = served.sum() / 1e6
        row["served_CH_TWh_el"] = served.get("CH00_electrolyzer", np.nan) / 1e6
        row["served_vs_legacy_EU"] = row["served_EU_TWh_el"] / row["legacy_volume_EU_TWh_el"]
        row["served_vs_legacy_CH"] = row["served_CH_TWh_el"] / row["legacy_volume_CH_TWh_el"]
        # capacity = legacy annual energy / FLH target (identical sizing in fixed-price mode)
        row["FLH_EU"] = row["served_EU_TWh_el"] * 1e6 / (leg_tot / flh)
        row["FLH_CH"] = row["served_CH_TWh_el"] * 1e6 / (leg_ch / flh)
    else:  # legacy: the annual volume is fixed
        row.update(served_EU_TWh_el=leg_tot / 1e6, served_CH_TWh_el=leg_ch / 1e6,
                   served_vs_legacy_EU=1.0, served_vs_legacy_CH=1.0, FLH_EU=flh, FLH_CH=flh)

    # electrolyzer dual check (dual x scaling / weight should equal the bid)
    cd = f / "consume_tot_limit_dual.csv"
    if cd.exists() and np.isfinite(bid):
        sc = pd.read_csv(f / "constraint_scaling.csv", index_col=0)["value"].get("consume_tot_limit", 1.0)
        w = pd.read_csv(f / "weight_in_objective_fcn.csv")["value"].iloc[0]
        d = pd.read_csv(cd)
        d = d[d["constraint"].str.contains("_electrolyzer_")]
        h2v = d["value"].astype(float).abs() * sc / w  # dual is negative when must-serve energy is 0
        row["max_abs_dual_minus_bid"] = float((h2v - bid).abs().max())

    cnt = pd.read_csv(f / "price_setting_plants_count.csv")
    cnt["group"] = cnt["Technology"].map(group_of)
    tot = cnt["Count"].sum()
    for g in GROUPS:
        row[f"setter_{g}"] = cnt.loc[cnt["group"] == g, "Count"].sum() / tot
    row["setter_Electrolyzer_any"] = cnt.loc[cnt["Technology"].str.startswith("Electrolyzer"), "Count"].sum() / tot
    return row


def figure(S: pd.DataFrame, outdir: Path):
    fixed = S[np.isfinite(S["h2_price_CHF_per_MWh_H2"])]
    years = sorted(S["year"].unique())
    fig, axes = plt.subplots(2, len(years), figsize=(5.2 * len(years), 7.2), squeeze=False)
    for j, y in enumerate(years):
        fy = fixed[fixed["year"] == y].sort_values("h2_price_CHF_per_MWh_H2")
        base = S[(S["year"] == y) & ~np.isfinite(S["h2_price_CHF_per_MWh_H2"])]
        ax = axes[0, j]
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.grid(True, color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        x = fy["h2_price_CHF_per_MWh_H2"]
        ax.plot(x, fy["CH_mean_price"], marker="o", color=INK, lw=2, ms=6, label="CH mean price")
        ax.plot(x, fy["bid_CHF_per_MWh_el"], ls="-", color=MUTED, lw=1, label="electrolyzer bid (eta x price)")
        if len(base):
            ax.axhline(base["CH_mean_price"].iloc[0], color="#C99700", lw=1.2, label="legacy base run")
        for xi, yi, v in zip(x, fy["CH_mean_price"], fy["served_vs_legacy_EU"]):
            ax.annotate(f"H2 vol. {v:.2f}x", (xi, yi), textcoords="offset points", xytext=(0, 8),
                        ha="center", fontsize=7.5, color=MUTED)
        ax.set_title(f"{y}: Swiss mean price", loc="left", fontsize=10, color=INK)
        ax.set_xlabel("H2 price (CHF/MWh_H2)", fontsize=9)
        ax.set_ylabel("CHF/MWh_el", fontsize=9)
        ax.legend(fontsize=7.5, frameon=False, loc="upper left")
        ax = axes[1, j]
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        labels = [f"{int(v)}" for v in fy["h2_price_CHF_per_MWh_H2"]] + (["legacy"] if len(base) else [])
        rows = pd.concat([fy, base])
        bottom = np.zeros(len(rows))
        for g in GROUPS:
            vals = rows[f"setter_{g}"].to_numpy() * 100
            ax.bar(labels, vals, bottom=bottom, color=GROUP_COLOR[g], edgecolor="white", linewidth=1.5,
                   width=0.6, label=g)
            bottom += vals
        ax.set_ylim(0, 100)
        ax.set_title(f"{y}: price setter shares (% of hours)", loc="left", fontsize=10, color=INK)
        ax.set_xlabel("H2 price (CHF/MWh_H2)", fontsize=9)
        if j == len(years) - 1:
            ax.legend(fontsize=7.5, frameon=False, loc="center left", bbox_to_anchor=(1.0, 0.5))
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(outdir / f"fig_h2_price_sweep.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=None)
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = Path(a.root)
    runs = a.runs or sorted(p.name for p in (root / "output").glob("h2fix*_wy2008_12hydro")) + \
        ["base_2035_wy2008_12hydro", "base_2050_wy2008_12hydro"]
    rows = []
    for r in runs:
        if not (root / "output" / r / "price_setting_plants.csv").exists():
            print(f"skip {r}: no price_setting_plants.csv (run missing or unfinished)")
            continue
        rows.append(summarise(r, root))
    S = pd.DataFrame(rows).sort_values(["year", "h2_price_CHF_per_MWh_H2"], na_position="last")
    outdir = root / "output" / "h2_price_sweep"
    outdir.mkdir(parents=True, exist_ok=True)
    S.to_csv(outdir / "h2_price_sweep_summary.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        print(S.round(3).to_string(index=False))
    figure(S, outdir)
    print(f"written to {outdir}")


if __name__ == "__main__":
    main()
