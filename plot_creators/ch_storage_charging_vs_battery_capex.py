"""Battery charging and hydro pumping across battery CAPEX levels (bcf sensitivity).

Companion figure to the CAPEX robustness check (appendix table): both target years
run at NTC 70% in the scenario where neighbors can also invest, sweeping battery
CAPEX over a common absolute grid. Shows whether hydro pumping behaves the same
in 2035 and 2050 once the battery cost assumption is equal.

Data: raw scenario outputs in output/20260513_bcf_sensitivity/<scenario>/storage_charge.csv
(long format: plant, hour, scenario_weatheryear, value in MWh).
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

pio.renderers.default = "browser"

# Settings: ------------------------------------------------------------------------------------------------------------
base_dir = Path(__file__).parent.parent
run_dir = base_dir / "output" / "20260513_bcf_sensitivity"

# Both sweeps cover the same absolute CAPEX grid (appendix table, CHF/MW, CHF2017):
# 35,302 ... 45,682 in steps of 1,038. The bcf suffix is the rounded factor
# relative to each year's baseline (2035: 43,606; 2050: 37,378).
CAPEX_GRID = [35302 + i * 1038 for i in range(11)]
BCF_ORDER = {
    "2035": ["081", "083", "086", "088", "090", "093", "095", "098", "100", "102", "105"],
    "2050": ["094", "097", "100", "103", "106", "108", "111", "114", "117", "119", "122"],
}
BASELINE_CAPEX = {"2035": 43606, "2050": 37378}

# Swiss open-loop pumped storage is modeled as the unprefixed plant "large_psp"
# (Switzerland's hydro fleet is represented in detail, without the CH00_ prefix).
PLANTS = {
    "battery_charging": ["CH00_battery"],
    "hydro_pumping": ["CH00_psp_open", "CH00_psp_close", "large_psp"],
}

output_base_path = base_dir / "plots" / "CH_storage_charging_vs_battery_capex"
output_base_path.parent.mkdir(parents=True, exist_ok=True)

# --- Visualization Parameters ---
FONT_SIZE = 18
FONT_FAMILY = "Times New Roman"

PLOT_WIDTH = 800
PLOT_HEIGHT = 400

SERIES_STYLE = {
    "battery_charging": dict(name="Battery charging", color="rgb(0,102,51)", symbol="circle"),
    "hydro_pumping": dict(name="Hydro pumping", color="rgb(120,120,120)", symbol="square"),
}


def annual_charging_twh(scenario_folder):
    """Mean annual charging over the weather years, in TWh, per series key."""
    wanted = [p for plants in PLANTS.values() for p in plants]
    sums = None
    for chunk in pd.read_csv(
        scenario_folder / "storage_charge.csv",
        usecols=["P_pumping", "Scenarios", "value"],
        chunksize=1_000_000,
    ):
        part = chunk[chunk["P_pumping"].isin(wanted)]
        grouped = part.groupby(["P_pumping", "Scenarios"])["value"].sum()
        sums = grouped if sums is None else sums.add(grouped, fill_value=0)
    per_plant_mean = sums.groupby("P_pumping").mean() / 1e6  # mean over weather years, MWh -> TWh
    return {key: sum(per_plant_mean.get(p, 0.0) for p in plants) for key, plants in PLANTS.items()}


results = {}
for year, bcfs in BCF_ORDER.items():
    rows = []
    for bcf, capex in zip(bcfs, CAPEX_GRID):
        folder = run_dir / f"{year}_070_inv_EUbat_bcf{bcf}"
        values = annual_charging_twh(folder)
        rows.append({"capex": capex, **values})
        print(f"{year} bcf{bcf} (CAPEX {capex}): {values}")
    results[year] = pd.DataFrame(rows).set_index("capex")

# --------------------------- starting the plot ---------------------------------------------------

fig = make_subplots(
    rows=1,
    cols=2,
    shared_yaxes=True,
    column_titles=list(BCF_ORDER),
    horizontal_spacing=0.05,
)

for col_idx, year in enumerate(BCF_ORDER, start=1):
    for key, style in SERIES_STYLE.items():
        series = results[year][key]
        fig.add_trace(
            go.Scatter(
                x=series.index / 1000,  # CHF/MW -> kCHF/MW
                y=series.values,
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
    fig.add_vline(
        x=BASELINE_CAPEX[year] / 1000,
        line_dash="dot",
        line_color="black",
        line_width=1,
        row=1,
        col=col_idx,
        annotation_text="baseline",
        annotation_position="top",
        annotation_font=dict(family=FONT_FAMILY, size=FONT_SIZE - 4, color="black"),
    )
    fig.update_xaxes(title_text="Battery CAPEX [kCHF/MW]", row=1, col=col_idx)

flex_max = max(results[y][k].max() for y in results for k in SERIES_STYLE)
fig.update_yaxes(range=[0, flex_max * 1.15])
fig.update_yaxes(title_text="Charging [TWh]", row=1, col=1)

for annotation in fig.layout.annotations:
    if annotation.text in BCF_ORDER:
        annotation.font = dict(family=FONT_FAMILY, size=FONT_SIZE + 6, color="black")

fig.update_layout(
    height=PLOT_HEIGHT,
    width=PLOT_WIDTH,
    font=dict(family=FONT_FAMILY, size=FONT_SIZE, color="black"),
    plot_bgcolor="white",
    margin=dict(t=45, b=65, l=20, r=10),
    legend=dict(orientation="h", yanchor="top", y=-0.28, xanchor="center", x=0.5, font=dict(size=FONT_SIZE - 2)),
)
fig.update_xaxes(showline=True, linecolor="black", ticks="outside")
fig.update_yaxes(showline=True, linecolor="black", ticks="outside", gridcolor="rgb(230,230,230)")

fig.show()

for year in BCF_ORDER:
    print(f"\n=== {year} (TWh, mean over weather years, NTC 70%, neighbors may invest) ===")
    print(results[year].round(2).to_string())

# Export PDF and PNG (high resolution)
for fmt in ("pdf", "png"):
    out_path = f"{output_base_path}.{fmt}"
    try:
        pio.write_image(fig, out_path, format=fmt, width=PLOT_WIDTH, height=PLOT_HEIGHT, scale=300 / (96 / 2))
        print(f"Exported {fmt.upper()} to {out_path}")
    except Exception as e:
        print(f"Warning: {fmt.upper()} export failed ({e}).")
