"""Net cross-border flows and flexibility operation across NTC levels (primary scenario).

Creates the paper figure showing (top row) Swiss net cross-border flows per border
plus their total, and (bottom row) battery discharge and pumped-storage pumping,
for 2035 and 2050, averaged over the three weather years. Data comes from the
aggregated Annual_balance_ch.csv files of the NTC sensitivity runs.
"""

import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

pio.renderers.default = "browser"

# Settings: ------------------------------------------------------------------------------------------------------------
base_dir = Path(__file__).parent.parent

SCENARIO_SETS = {
    "2035": base_dir / "output" / "aggregated" / "20260313_2035_inv_CHbat" / "Annual_balance_ch.csv",
    "2050": base_dir / "output" / "aggregated" / "20260313_2050_inv_CHbat" / "Annual_balance_ch.csv",
}

output_base_path = base_dir / "plots" / "CH_trade_and_flexibility_vs_NTC"
output_base_path.parent.mkdir(parents=True, exist_ok=True)

# --- Visualization Parameters ---
FONT_SIZE = 18
FONT_FAMILY = "Times New Roman"

PLOT_WIDTH = 800
PLOT_HEIGHT = 620

# Colors follow the base palette of the other paper plots; markers act as a
# color-independent secondary encoding for the print/CVD case.
FLOW_SERIES = {
    "import_FR": dict(name="France", color="rgb(45,101,175)", symbol="circle"),
    "import_DE": dict(name="Germany", color="rgb(240,182,0)", symbol="square"),
    "import_IT": dict(name="Italy", color="rgb(131,184,25)", symbol="diamond"),
    "import_AT": dict(name="Austria", color="rgb(88,49,25)", symbol="triangle-up"),
}
TOTAL_SERIES = {
    "total_net_import": dict(name="Total (net import)", color="black", symbol="x"),
}
FLEX_SERIES = {
    "storage_charging": dict(name="Storage charging (batteries + pumped hydro)", color="rgb(0,102,51)", symbol="circle"),
}


def ntc_level(column_name):
    match = re.search(r"_(\d{3})_", column_name)
    return int(match.group(1)) if match else None


def load_annual_balance_means(csv_path):
    """Return a DataFrame indexed by (section, tech) with one column per NTC level,
    holding the mean over the weather years in TWh."""
    df = pd.read_csv(csv_path, encoding="cp1252")
    id_cols = list(df.columns[:2])
    value_cols = [c for c in df.columns if ntc_level(c) is not None]
    for col in value_cols:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace("’", "").str.replace("'", "").str.strip().replace({"-": "0", "": "0"}),
            errors="coerce",
        )
    long = df.melt(id_vars=id_cols, value_vars=value_cols, var_name="scen", value_name="val")
    long["ntc"] = long["scen"].map(ntc_level)
    means = long.groupby(id_cols + ["ntc"])["val"].mean().unstack("ntc") / 1e6  # MWh -> TWh
    means.index = pd.MultiIndex.from_tuples(means.index) if not isinstance(means.index, pd.MultiIndex) else means.index
    return means


def extract_series(means):
    """Pick the plotted rows out of the annual balance."""
    out = {}
    for key in FLOW_SERIES:
        out[key] = means.loc[("gen", key)]
    out["total_net_import"] = sum(out[key] for key in FLOW_SERIES)
    out["storage_charging"] = (
        means.loc[("demand", "flex battery")]
        + means.loc[("demand", "flex psp_open")]
        + means.loc[("demand", "flex psp_close")]
    )
    return out


data = {year: extract_series(load_annual_balance_means(path)) for year, path in SCENARIO_SETS.items()}

# --------------------------- starting the plot ---------------------------------------------------

fig = make_subplots(
    rows=2,
    cols=2,
    shared_xaxes=True,
    column_titles=["2035", "2050"],
    horizontal_spacing=0.08,
    vertical_spacing=0.06,
)

for col_idx, year in enumerate(SCENARIO_SETS, start=1):
    for key, style in FLOW_SERIES.items():
        series = data[year][key].sort_index()
        fig.add_trace(
            go.Scatter(
                x=series.index,
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
    for key, style in TOTAL_SERIES.items():
        series = data[year][key].sort_index()
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                mode="lines+markers",
                name=style["name"],
                legendgroup=style["name"],
                showlegend=(col_idx == 1),
                line=dict(color=style["color"], width=2, dash="dash"),
                marker=dict(symbol=style["symbol"], size=9, color=style["color"]),
            ),
            row=1,
            col=col_idx,
        )
    for key, style in FLEX_SERIES.items():
        series = data[year][key].sort_index()
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                mode="lines+markers",
                name=style["name"],
                legend="legend2",
                legendgroup=style["name"],
                showlegend=(col_idx == 1),
                line=dict(color=style["color"], width=2),
                marker=dict(symbol=style["symbol"], size=8, color=style["color"]),
            ),
            row=2,
            col=col_idx,
        )

flow_min = min(min(data[y][k].min() for k in FLOW_SERIES) for y in data)
flow_max = max(max(data[y][k].max() for k in FLOW_SERIES) for y in data)
flex_max = max(max(data[y][k].max() for k in FLEX_SERIES) for y in data)

for col_idx in (1, 2):
    fig.update_yaxes(
        range=[flow_min * 1.1, flow_max * 1.1],
        zeroline=True,
        zerolinecolor="rgb(120,120,120)",
        zerolinewidth=1,
        row=1,
        col=col_idx,
    )
    fig.update_yaxes(range=[0, flex_max * 1.15], row=2, col=col_idx)
    fig.update_xaxes(tickvals=[30, 40, 50, 60, 70, 80, 90, 100], row=2, col=col_idx)
    fig.update_xaxes(title_text="NTC", row=2, col=col_idx)

fig.update_yaxes(title_text="Net import [TWh]", row=1, col=1)
fig.update_yaxes(title_text="Charging [TWh]", row=2, col=1)

# Enlarge the "2035" / "2050" column titles (created as annotations by make_subplots)
for annotation in fig.layout.annotations:
    if annotation.text in SCENARIO_SETS:
        annotation.font = dict(family=FONT_FAMILY, size=FONT_SIZE + 6, color="black")

fig.update_layout(
    height=PLOT_HEIGHT,
    width=PLOT_WIDTH,
    font=dict(family=FONT_FAMILY, size=FONT_SIZE, color="black"),
    plot_bgcolor="white",
    margin=dict(t=45, b=110, l=20, r=10),
    legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5, font=dict(size=FONT_SIZE - 2)),
    legend2=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5, font=dict(size=FONT_SIZE - 2)),
)
fig.update_xaxes(showline=True, linecolor="black", ticks="outside")
fig.update_yaxes(showline=True, linecolor="black", ticks="outside", gridcolor="rgb(230,230,230)")

fig.show()

# ---- Console table for the running text ----
for year in SCENARIO_SETS:
    print(f"\n=== {year} (TWh, mean over weather years) ===")
    styles = {**FLOW_SERIES, **TOTAL_SERIES, **FLEX_SERIES}
    table = pd.DataFrame({styles[k]["name"]: v for k, v in data[year].items()}).T
    print(table.round(1).to_string())

# Export PDF and PNG (high resolution)
for fmt in ("pdf", "png"):
    out_path = f"{output_base_path}.{fmt}"
    try:
        pio.write_image(fig, out_path, format=fmt, width=PLOT_WIDTH, height=PLOT_HEIGHT, scale=300 / (96 / 2))
        print(f"Exported {fmt.upper()} to {out_path}")
    except Exception as e:
        print(f"Warning: {fmt.upper()} export failed ({e}).")
