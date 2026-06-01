import argparse
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from PIL import Image
import os
pio.renderers.default = "browser"

def read_index_as_list_safe(path, index_col=0, usecols=None):
    if not os.path.isfile(path):
        return []

    try:
        df_full = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return []

    if df_full.empty:
        return []

    col_names = df_full.columns.tolist()

    if isinstance(index_col, int):
        if index_col >= len(col_names):
            return []
        index_col_name = col_names[index_col]
    else:
        index_col_name = index_col

    df_full.set_index(index_col_name, inplace=True)

    if usecols is not None:
        resolved_cols = []
        for col in usecols:
            if isinstance(col, int):
                if col >= len(col_names):
                    continue
                resolved_cols.append(col_names[col])
            else:
                resolved_cols.append(col)
        resolved_cols = [col for col in resolved_cols if col != index_col_name]
        df_full = df_full[resolved_cols]

    return list(set(df_full.index.astype(str)))

def lighten_rgb(rgb_string, factor):
    """Lightens the given RGB string by mixing it with white. Factor between 0 and 1."""
    r, g, b = [int(x) for x in rgb_string.strip("rgb()").split(",")]
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f'rgb({r},{g},{b})'

def parse_args():
    parser = argparse.ArgumentParser(description="Create battery-only investment summary plot.")
    parser.add_argument(
        "--scenarios",
        nargs="+",
        help="Scenarios to summarize (e.g. 20260119/2050_sens_100 ...)",
    )
    parser.add_argument(
        "--display-names",
        nargs="+",
        help="Display names matching the scenarios order.",
    )
    parser.add_argument(
        "--output-base",
        help="Output path without extension for PDF/PNG (e.g. output/20260119/Battery_Investments_in_2035)",
    )
    return parser.parse_args()

# Settings: ------------------------------------------------------------------------------------------------------------
default_year = "2035"

DEFAULT_SCENARIOS = [
    f"20260311/{default_year}_030_inv_CHbat",
    f"20260311/{default_year}_040_inv_CHbat",
    f"20260311/{default_year}_050_inv_CHbat",
    f"20260311/{default_year}_060_inv_CHbat",
    f"20260311/{default_year}_070_inv_CHbat",
    f"20260311/{default_year}_080_inv_CHbat",
    f"20260311/{default_year}_090_inv_CHbat",
    f"20260311/{default_year}_100_inv_CHbat",
]
DEFAULT_DISPLAY_NAMES = [
    'NTC 30%',
    'NTC 40%',
    'NTC 50%',
    'NTC 60%',
    'NTC 70%',
    'NTC 80%',
    'NTC 90%',
    'NTC 100%',
]

args = parse_args()
scenarios_to_summarize = args.scenarios or DEFAULT_SCENARIOS
scenarios_display_names = args.display_names or DEFAULT_DISPLAY_NAMES

if len(scenarios_to_summarize) != len(scenarios_display_names):
    raise ValueError("scenarios and display names must have the same length")

base_dir = Path(__file__).parent.parent
if args.output_base:
    output_base = args.output_base
else:
    output_base = str(base_dir / "plots" / f"Battery_Investments_in_{default_year}")
output_base_path = Path(output_base)
output_base_path.parent.mkdir(parents=True, exist_ok=True)

# --- Visualization Parameters ---
FONT_SIZE = 18
FONT_FAMILY = "Times New Roman"

# Recommended for A4 paper (landscape, high quality export)
PLOT_WIDTH = 800
PLOT_HEIGHT = 400

# y-axis limit for battery added power (GW)
battery_power_max = 5.5

rows = ["battery"]
row_renaming = {"battery": "Battery"}

columns_to_look_at = ["Added Power (MW)", "Storage level (MWh)"]
columns_to_print = [scen + " " + column for scen in scenarios_to_summarize for column in columns_to_look_at]

df = pd.DataFrame(columns=columns_to_print, index=rows)

for scen in scenarios_to_summarize:
    data = pd.read_csv(base_dir / "output" / scen / "investment_summary.csv", index_col=0)
    P_allinv_raw = pd.read_csv(base_dir / "output" / scen / "P_allinv.csv", index_col=0)
    P_allinv = [tech for tech in P_allinv_raw.index]
    heating_techs = read_index_as_list_safe(str(base_dir / "output" / scen / "genTh_max.csv"), index_col=0, usecols=[0, 2])
    tech_to_consider_bool = [t in P_allinv + heating_techs for t in data.index]
    data = data[tech_to_consider_bool]

    for col_to_look in columns_to_look_at:
        temp = data[col_to_look]

        for row in rows:
            bool_mask = [row in cell for cell in temp.index]
            sum_of_values = sum(temp[bool_mask])
            df.at[row, scen + " " + col_to_look] = sum_of_values

df = df.rename(index=row_renaming)

# turn NaN values into 0, convert MW -> GW (and MWh -> GWh), and round
df = (df.fillna(0) / 1000).round(5)

categories = ['Added Power (MW)', 'Storage level (MWh)']

# Rename columns for easier plotting
for category in categories:
    for idx, scen in enumerate(scenarios_to_summarize):
        df.rename(columns={f'{scen} {category}': f'{scenarios_display_names[idx]} {category}'}, inplace=True)

# Base colors matching summary_for_presentation_NTC_affects_storage_paper.py
base_colors = [
    'rgb(237,219,171)',  # beige
    'rgb(240,182,0)',    # yellow
    'rgb(131,184,25)',   # green
    'rgb(88,49,25)',     # brown
    'rgb(0,102,51)',     # dark green
    'rgb(45,101,175)',   # blue
]

light_factors = [0.35, 0.5, 0.65, 0.75, 0.85, 0.9]  # darker to lighter

colors = {}
for idx, scen in enumerate(scenarios_to_summarize):
    base_idx = idx % len(base_colors)
    lighten_idx = idx // len(base_colors)
    base_color = base_colors[base_idx]
    if lighten_idx == 0:
        colors[scen] = base_color
    else:
        factor = light_factors[min(lighten_idx - 1, len(light_factors) - 1)]
        colors[scen] = lighten_rgb(base_color, factor)

# --------------------------- starting the plot ---------------------------------------------------

fig = go.Figure()

tech_label = "Battery"
for idx, scen_display in enumerate(scenarios_display_names):
    value = df[f'{scen_display} {categories[0]}'].loc[tech_label]
    fig.add_trace(
        go.Bar(
            x=[tech_label],
            y=[value],
            name=scen_display,
            marker_color=colors[scenarios_to_summarize[idx]],
            offsetgroup=scen_display,
            showlegend=True,
        )
    )

fig.update_layout(
    title_x=0.5,
    height=PLOT_HEIGHT,
    width=PLOT_WIDTH,
    barmode='group',
    font=dict(
        family=FONT_FAMILY,
        size=FONT_SIZE,
        color="black",
    ),
    legend=dict(
        orientation="h",
        yanchor="top",
        y=-0.15,
        xanchor="center",
        x=0.5,
        title=None,
        font=dict(size=FONT_SIZE, color="black"),
    ),
    margin=dict(t=20, b=75, l=20, r=10),
)

fig.update_yaxes(title_text="Capacity [GW<sub>el</sub>]", range=[0, battery_power_max])

fig.show()

pdf_path = f"{output_base_path}.pdf"
png_path = f"{output_base_path}.png"
html_path = f"{output_base_path}.html"
md_path = f"{output_base_path}.md"

# ---- Write markdown (power displayed, storage hidden in the figures but tabulated here) ----
md_lines = [
    "# Battery Investment Summary",
    "",
    "This document accompanies the battery-only investment plot. "
    "The HTML, PNG and PDF outputs show ONLY the installed power capacity (GW). "
    "The storage capacity table below is provided for completeness and is intentionally "
    "not displayed in the graphics. It is meant to be read by the human author and "
    "summarized in the running text or the appendix (e.g. 'battery storage capacity reaches up to X GWh').",
    "",
    "## Installed Power Capacity (GW) — shown in the figures",
    "",
]
header = "| Technology | " + " | ".join(scenarios_display_names) + " |"
sep = "|------------|" + "|".join(["------"] * len(scenarios_display_names)) + "|"
md_lines.append(header)
md_lines.append(sep)
row_vals = [f"{df[f'{scen} {categories[0]}'].loc[tech_label]:.2f}" for scen in scenarios_display_names]
md_lines.append(f"| {tech_label} | " + " | ".join(row_vals) + " |")

md_lines += [
    "",
    "## Storage Capacity (GWh) — NOT shown in HTML/PNG/PDF",
    "",
    "<!-- Reminder: the values below are for the author's reference only. "
    "They are deliberately excluded from the graphical outputs and should be "
    "described in prose in the main text or appendix, not reproduced as a figure. -->",
    "",
]
md_lines.append(header)
md_lines.append(sep)
row_vals = [f"{df[f'{scen} {categories[1]}'].loc[tech_label]:.2f}" for scen in scenarios_display_names]
md_lines.append(f"| {tech_label} | " + " | ".join(row_vals) + " |")
md_lines.append("")

with open(md_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md_lines))
print(f"Exported markdown to {md_path}")

# Export HTML
fig.write_html(html_path)
print(f"Exported HTML to {html_path}")

# Export PDF and PNG (high resolution)
try:
    pio.write_image(
        fig,
        pdf_path,
        format="pdf",
        width=PLOT_WIDTH,
        height=PLOT_HEIGHT,
        scale=300 / (96 / 2),
    )
    print(f"Exported PDF to {pdf_path}")
except Exception as e:
    print(f"Warning: PDF export failed ({e}).")

try:
    pio.write_image(
        fig,
        png_path,
        format="png",
        width=PLOT_WIDTH,
        height=PLOT_HEIGHT,
        scale=300 / (96 / 2),
    )

    # Crop the top white bar from the exported PNG (matches the paper plot script)
    with Image.open(png_path) as img:
        width, height = img.size
        crop_top = min(400, height)
        cropped = img.crop((0, crop_top, width, height))
        cropped.save(png_path)
    print(f"Exported PNG to {png_path}")
except Exception as e:
    print(f"Warning: PNG export failed ({e}).")
