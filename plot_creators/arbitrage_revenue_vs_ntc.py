"""Theoretical maximal day-ahead arbitrage revenue of a generic battery across NTC levels.

Creates the paper figure plot_F_arbitrage_revenue_CHF: for 2035 and 2050 (primary
scenario), the theoretical maximal annual day-ahead arbitrage revenue of a generic
5.5-hour battery (duration = mean E/P ratio of the batteries the model builds),
computed from the modeled Swiss day-ahead prices per NTC level and weather year.
The annualized cost of the same generic battery is printed to the console for
reference but deliberately NOT drawn in the figure: the single-cycle indicator
understates the revenue of the model's batteries (stochastic weather-year
portfolio), so a cost line would invite a misleading profitability reading.

Prices: energy_balance_dual.csv holds duals scaled by the weather-year weight in the
objective function -- they are divided by that weight (read from settings.csv) to
obtain real prices, then converted EUR2017 -> CHF2017 with the 31.12.2022 FX rate,
consistent with the battery CAPEX derivation in the paper appendix.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

pio.renderers.default = "browser"

# Settings: ------------------------------------------------------------------------------------------------------------
base_dir = Path(__file__).parent.parent

SCENARIO_SETS = {
    "2035": base_dir / "output" / "aggregated" / "20260313_2035_inv_CHbat",
    "2050": base_dir / "output" / "aggregated" / "20260313_2050_inv_CHbat",
}

DURATION_H = 5.5  # mean E/P ratio of the batteries the model builds (5.1-5.6 h)
ETA_RT = 0.86  # round-trip efficiency of the generic battery
FX_EUR_CHF = 1.1119  # EUR2017 -> CHF2017, consistent with the CAPEX derivation

# Annualized cost of the same generic battery, kCHF2017/MW/yr:
# (CAPEX_power + D * CAPEX_energy) * CRF(5%, 10y) + fixed O&M
CRF = 0.05 * 1.05**10 / (1.05**10 - 1)
BATTERY_COST = {
    "2035": (43.6 + DURATION_H * 51.6) * CRF + 0.14,
    "2050": (37.4 + DURATION_H * 44.2) * CRF + 0.14,
}

output_base_path = base_dir / "plots" / "plot_F_arbitrage_revenue_CHF"
output_base_path.parent.mkdir(parents=True, exist_ok=True)

# --- Visualization Parameters ---
FONT_SIZE = 18
FONT_FAMILY = "Times New Roman"

PLOT_WIDTH = 800
PLOT_HEIGHT = 450

WY_SERIES = {
    "1995": dict(name="wy 1995", color="rgb(222,196,140)", symbol="circle"),
    "2008": dict(name="wy 2008", color="rgb(240,182,0)", symbol="square"),
    "2009": dict(name="wy 2009", color="rgb(131,184,25)", symbol="triangle-up"),
}
AVG_STYLE = dict(name="Average (weather years)", color="black", symbol="diamond")


def load_weights(folder):
    s = pd.read_csv(folder / "settings.csv", encoding="cp1252")
    s = s.rename(columns={s.columns[0]: "Item"})
    wy_row = s[s["Item"] == "sub_secn"].iloc[0]
    w_row = s[s["Item"] == "weight_in_objective_fcn"].iloc[0]
    return {str(wy_row[c]).replace("wy", ""): float(w_row[c]) for c in s.columns[1:]}


def revenue_kchf_per_mw(prices):
    """Theoretical max annual DA arbitrage revenue of the generic battery, kCHF/MW/yr.

    One cycle per day with perfect foresight within each day: charge in the
    DURATION_H cheapest hours, discharge in the DURATION_H most expensive ones,
    round-trip efficiency applied to the discharge side.
    """
    daily = np.sort(prices.reshape(365, 24), axis=1)
    k = int(DURATION_H)
    frac = DURATION_H - k
    bot = daily[:, :k].sum(axis=1) + frac * daily[:, k]
    top = daily[:, -k:].sum(axis=1) + frac * daily[:, -(k + 1)]
    daily_revenue = ETA_RT * top - bot
    return np.maximum(daily_revenue, 0).sum() * FX_EUR_CHF / 1e3


data = {}
for year, folder in SCENARIO_SETS.items():
    weights = load_weights(folder)
    df = pd.read_csv(folder / "energy_balance_dual.csv", encoding="cp1252")
    df = df[df["Node"] == "CH00"].copy()
    df["t"] = df["T"].str.extract(r"t_(\d+)").astype(int)
    df = df.sort_values("t")
    rows = {}
    for c in df.columns:
        m = re.search(r"_(\d{3})_.*_wy(\d{4})", str(c))
        if not m:
            continue
        ntc, wy = int(m.group(1)), m.group(2)
        prices = (df[c] / weights[wy]).to_numpy()
        rows.setdefault(ntc, {})[wy] = revenue_kchf_per_mw(prices)
    t = pd.DataFrame(rows).T.sort_index()
    t["avg"] = t.mean(axis=1)
    data[year] = t

# --------------------------- starting the plot ---------------------------------------------------

fig = make_subplots(
    rows=1,
    cols=2,
    shared_yaxes=True,
    column_titles=list(SCENARIO_SETS),
    horizontal_spacing=0.04,
)

for col_idx, year in enumerate(SCENARIO_SETS, start=1):
    t = data[year]
    for wy, style in WY_SERIES.items():
        fig.add_trace(
            go.Scatter(
                x=t.index,
                y=t[wy],
                mode="lines+markers",
                name=style["name"],
                legendgroup=style["name"],
                showlegend=(col_idx == 1),
                line=dict(color=style["color"], width=2),
                marker=dict(symbol=style["symbol"], size=8, color=style["color"]),
            ),
            row=1,
            col=col_idx,
        )
    fig.add_trace(
        go.Scatter(
            x=t.index,
            y=t["avg"],
            mode="lines+markers",
            name=AVG_STYLE["name"],
            legendgroup=AVG_STYLE["name"],
            showlegend=(col_idx == 1),
            line=dict(color=AVG_STYLE["color"], width=2.5, dash="dash"),
            marker=dict(symbol=AVG_STYLE["symbol"], size=9, color=AVG_STYLE["color"]),
        ),
        row=1,
        col=col_idx,
    )
y_max = max(t.drop(columns="avg").max().max() for t in data.values())
for col_idx in (1, 2):
    fig.update_xaxes(
        tickvals=[30, 40, 50, 60, 70, 80, 90, 100],
        ticksuffix="%",
        title_text="NTC level",
        range=[26, 104],
        row=1,
        col=col_idx,
    )
    fig.update_yaxes(range=[0, y_max * 1.08], row=1, col=col_idx)

fig.update_yaxes(title_text="Annual revenue [kCHF/MW/yr]", row=1, col=1)

for annotation in fig.layout.annotations:
    if annotation.text in SCENARIO_SETS:
        annotation.font = dict(family=FONT_FAMILY, size=FONT_SIZE + 6, color="black")

fig.update_layout(
    height=PLOT_HEIGHT,
    width=PLOT_WIDTH,
    font=dict(family=FONT_FAMILY, size=FONT_SIZE, color="black"),
    plot_bgcolor="white",
    margin=dict(t=45, b=110, l=20, r=10),
    legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5, font=dict(size=FONT_SIZE - 4)),
)
fig.update_xaxes(showline=True, linecolor="black", ticks="outside")
fig.update_yaxes(showline=True, linecolor="black", ticks="outside", gridcolor="rgb(230,230,230)")

fig.show()

# ---- Console table for the running text ----
for year in SCENARIO_SETS:
    print(f"\n=== {year} (kCHF/MW/yr, generic {DURATION_H} h battery) — cost {BATTERY_COST[year]:.1f} ===")
    print(data[year].round(1).to_string())

# Export PDF and PNG (high resolution)
for fmt in ("pdf", "png"):
    out_path = f"{output_base_path}.{fmt}"
    try:
        pio.write_image(fig, out_path, format=fmt, width=PLOT_WIDTH, height=PLOT_HEIGHT, scale=300 / (96 / 2))
        print(f"Exported {fmt.upper()} to {out_path}")
    except Exception as e:
        print(f"Warning: {fmt.upper()} export failed ({e}).")
