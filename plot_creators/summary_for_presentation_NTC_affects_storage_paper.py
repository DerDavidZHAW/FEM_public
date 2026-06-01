import argparse
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import re
import plotly.express as px
import plotly.io as pio
from PIL import Image
from itertools import combinations
import os
pio.renderers.default = "browser"

def read_index_as_list_safe(path, index_col=0, usecols=None):
    if not os.path.isfile(path):
        return []

    try:
        # Read entire file first (needed to access column names)
        df_full = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return []

    if df_full.empty:
        return []

    # Map index_col and usecols from integer to column names if needed
    col_names = df_full.columns.tolist()

    # Resolve index_col to column name
    if isinstance(index_col, int):
        if index_col >= len(col_names):
            return []
        index_col_name = col_names[index_col]
    else:
        index_col_name = index_col

    # Set index
    df_full.set_index(index_col_name, inplace=True)

    # Apply usecols filtering (ignoring index_col to avoid double inclusion)
    if usecols is not None:
        resolved_cols = []
        for col in usecols:
            if isinstance(col, int):
                if col >= len(col_names):
                    continue
                resolved_cols.append(col_names[col])
            else:
                resolved_cols.append(col)
        # Make sure we don't drop the index
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
    parser = argparse.ArgumentParser(description="Create investment summary plots.")
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
        help="Output path without extension for PDF/PNG (e.g. output/20260119/Sensitivity_Analysis_in_2050)",
    )
    return parser.parse_args()

# Settings: ------------------------------------------------------------------------------------------------------------
default_year = "2035"

DEFAULT_SCENARIOS = [
    f"20260311/{default_year}_100_inv_EUbat",
    f"20260311/{default_year}_090_inv_EUbat",
    f"20260311/{default_year}_080_inv_EUbat",
    f"20260311/{default_year}_070_inv_EUbat",
    f"20260311/{default_year}_060_inv_EUbat",
    f"20260311/{default_year}_050_inv_EUbat",
    f"20260311/{default_year}_040_inv_EUbat",
    f"20260311/{default_year}_030_inv_EUbat",
]
DEFAULT_DISPLAY_NAMES = [
    'NTC 100%',
    'NTC 90%',
    'NTC 80%',
    'NTC 70%',
    'NTC 60%',
    'NTC 50%',
    'NTC 40%',
    'NTC 30%',
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
    output_base = str(base_dir / "plots" / f"Sensitivity_Analysis_in_{default_year}")
output_base_path = Path(output_base)
output_base_path.parent.mkdir(parents=True, exist_ok=True)

# --- Visualization Parameters ---
FONT_SIZE = 18
FONT_FAMILY = "Times New Roman"

# Default size (not too big)
# PLOT_WIDTH = 1000
# PLOT_HEIGHT = 600

# Recommended for A4 paper (landscape, high quality export)
PLOT_WIDTH = 800  # ≈ 21.7 cm at 200 DPI
PLOT_HEIGHT = 400  # ≈ 15.4 cm at 200 DPI

# Axes limits
added_power_max = 5.5  # GW
pit_tes_max = 670  # GWh

name_output = "investment_summary_for_presentation.csv"

rows = ["battery", "TTES", "PTES", "pvrf", "windon", "CCGT", "SCGT",  "dam", "electrolyzer", "hydrogen", "nuclear", "oil", "psp_close", "biomass", "other",  "V2G_", "fossilmethane", "resmethane", "_CHPNew", "_HPG", "_HPNew",  "dsrTh", "resistive", "thermal"]
# NOTE: Use "_CHPNew", "_HPG", "_HPNew" with underscore prefix to avoid substring matching issues
# (e.g., "HPNew" would incorrectly match "CHPNew" because "HPNew" is a substring of "CHPNew")
row_renaming = {
     "CCGT" : "CCGT",
     "SCGT" : "SCGT",
     "battery" : "Battery",
     "dam" : "dam",
     "electrolyzer" : "Electrolyzer",
     "hydrogen" : "Hydrogen",
     "nuclear" : "Nuclear",
     "oil" : "Oil",
     "psp_close" : "psp_close",
     "biomass" : "biomass",
     "other" : "other",
     "pvrf" : "Additional PV",
     "windon" : "Additional Wind",
     "V2G_" : "V2G",
     "fossilmethane" : "Fossil Methane",
     "resmethane" : "RES Methane",
     "_CHPNew" : "CHP",
     "_HPG" : "HPG", # HP Large
     "_HPNew" : "Heat pump", # HP Large
     "TTES" : "Tank TES",
     "dsrTh" : "dsr Thermal",
     "resistive" : "Resistive Heater",
     "thermal" : "Thermal plant",
     "PTES" : "Pit TES",
}

columns_to_look_at = ["Added Power (MW)", "Storage level (MWh)"]

columns_to_print = [scen + " " + column for scen in scenarios_to_summarize for column in columns_to_look_at]

df = pd.DataFrame(columns=columns_to_print, index=rows)

for scen in scenarios_to_summarize:
    data = pd.read_csv(base_dir / "output" / scen / "investment_summary.csv", index_col=0)
    P_allinv_raw = pd.read_csv(base_dir / "output" / scen / "P_allinv.csv",index_col=0)
    P_allinv = [tech for tech in P_allinv_raw.index]
    heating_techs = read_index_as_list_safe(str(base_dir / "output" / scen / "genTh_max.csv"), index_col=0, usecols=[0, 2])
    tech_to_consider_bool = [t in P_allinv + heating_techs for t in data.index]
    data = data[tech_to_consider_bool]

    for col_to_look in columns_to_look_at:
        temp = data[col_to_look]

        for row in rows:
            bool = [row in cell for cell in temp.index]
            sum_of_values = sum(temp[bool])
            df.at[row, scen + " " + col_to_look] = sum_of_values
df = df.rename(index=row_renaming)
# df.to_csv(f"output/{name_output}")

# turn NaN values into 0 and round to int
df = (df.fillna(0) / 1000).round(5)

# Technologies to be plotted
# Note: CHP capacity is shown in MW_th (from genTh_max), Wind is in MW_el (from gen_max)
techs_to_plot_power = ["Battery", "Pit TES", "Resistive Heater", "Heat pump", "CHP"]
techs_to_plot_storage = ["Battery", "Pit TES"]
techs_to_document_power = ["Battery", "Additional PV", "Additional Wind", "Tank TES", "Pit TES", "Resistive Heater", "Heat pump", "CHP"]
techs_to_document_storage = ["Battery", "Tank TES", "Pit TES"]
categories = ['Added Power (MW)', 'Storage level (MWh)']

# Rename the columns for easier plotting
for category in categories:
    for idx, scen in enumerate(scenarios_to_summarize):
        df.rename(columns={f'{scen} {category}': f'{scenarios_display_names[idx]} {category}'}, inplace=True)

# turn the hydrogen NTC storage level to zero if the added power is zero
for scen in scenarios_display_names:
    if df[f'{scen} {categories[0]}'].loc['Hydrogen'] == 0:
        df[f'{scen} {categories[1]}'].loc['Hydrogen'] = 0

# Prepare data for of the "Added Power (MW)" plot
columns_installed_power = [f'{scen} {categories[0]}' for scen in scenarios_display_names]
data_installed_power = df[columns_installed_power].loc[techs_to_plot_power]

# Prepare data for the "Storage level (MWh)" plot
columns_storage_level = [f'{scen} {categories[1]}' for scen in scenarios_display_names]
data_storage_level = df[columns_storage_level].loc[techs_to_plot_storage]

# Base colors for 6 scenarios
base_colors = [
    'rgb(237,219,171)',  # beige
    'rgb(240,182,0)',    # yellow
    'rgb(131,184,25)',   # green
    'rgb(88,49,25)',     # brown
    'rgb(0,102,51)',     # dark green
    'rgb(45,101,175)',   # blue (new base)
]

# Generate lighter versions for additional scenarios
max_scenarios = 12
light_factors = [0.35, 0.5, 0.65, 0.75, 0.85, 0.9]  # From darker to lighter

# Fill in the color map
colors = {}
for idx, scen in enumerate(scenarios_to_summarize):
    base_idx = idx % len(base_colors)
    lighten_idx = idx // len(base_colors)
    base_color = base_colors[base_idx]
    if lighten_idx == 0:
        colors[scen] = base_color
    else:
        factor = light_factors[min(lighten_idx - 1, len(light_factors)-1)]
        colors[scen] = lighten_rgb(base_color, factor)

# --------------------------- starting the plot ---------------------------------------------------

# Create subplots with secondary y-axis on second plot (for Pit TES)
fig = make_subplots(
    rows=1, cols=2,
    shared_yaxes=False,
    # subplot_titles=("Installed Power Capacity", "Storage Capacity"),
    specs=[[{}, {}]],  # ⬅ no secondary axis anymore
    horizontal_spacing=0.1,
)

# Ensure subplot titles use the correct font size and family
for annotation in fig['layout']['annotations']: # type: ignore
    annotation['font'] = dict(size=FONT_SIZE, family=FONT_FAMILY) # type: ignore

x_pos = list(data_installed_power.index)

# -------- Installed Power (in GW) --------
for tech in x_pos:
    # Collect values across scenarios
    values_by_scen = {
        scen: data_installed_power[f'{scen} {categories[0]}'].loc[tech]
        for scen in scenarios_display_names
    }

    # Plot all bars for this tech
    for idx, scen in enumerate(scenarios_display_names):
        value = values_by_scen[scen]

        fig.add_trace(
            go.Bar(
                x=[tech],
                y=[value],
                name=scen,
                marker_color=colors[scenarios_to_summarize[idx]],
                offsetgroup=scen,
                showlegend=(tech == x_pos[0])
            ),
            row=1, col=1
        )

# Add vertical line to separate electrical and thermal technologies
separator_tech = "Pit TES"
for line in [[added_power_max, 1], [pit_tes_max, 2]]:
    fig.add_shape(
        type="line",
        x0=separator_tech,
        x1=separator_tech,
        x0shift=-0.5,
        x1shift=-0.5,
        y0=0,
        y1=line[0],
        line=dict(color="black", width=1, dash="solid"),
        row=1, col=line[1]
    )

for annotation in [["el", -45, 1, added_power_max], ["th", -21, 1, added_power_max], ["el", -95, 2, pit_tes_max], ["th", -71, 2, pit_tes_max]]:
    fig.add_annotation(
        text=annotation[0],
        x=separator_tech,
        xshift=annotation[1],
        y=annotation[3] * 0.95,
        showarrow=False,
        font=dict(size=FONT_SIZE, color="black"),
        row=1, col=annotation[2]
    )

# -------- Storage Capacity (in GWh) --------
for tech in techs_to_plot_storage:
    # Collect values across scenarios
    values_by_scen = {
        scen: data_storage_level[f'{scen} {categories[1]}'].loc[tech]
        for scen in scenarios_display_names
    }

    # Plot all bars for this tech
    for idx, scen in enumerate(scenarios_display_names):
        value = values_by_scen[scen]

        fig.add_trace(
            go.Bar(
                x=[tech],
                y=[value],
                name=scen,
                marker_color=colors[scenarios_to_summarize[idx]],
                offsetgroup=scen,
                showlegend=False  # legend shown in left plot only
            ),
            row=1, col=2
        )

# Update layout
fig.update_layout(
    # title_text="Sensitivity Analysis in 2050",
    title_x=0.5,  # centers the title
    height=PLOT_HEIGHT,
    width=PLOT_WIDTH,
    barmode='group',
    font=dict(
        family=FONT_FAMILY,
        size=FONT_SIZE,
        color ="black",
    ),
    legend=dict(
        orientation="h",
        yanchor="top",
        y=-0.35,
        xanchor="center",
        x=0.5,
        title=None,
        font=dict(size=FONT_SIZE,
                  color="black"
                  )
    ),
    margin=dict(t=20, b=75, l=20, r=10)
)

# Axis titles & limits
fig.update_yaxes(title_text="Capacity [GW<sub>el</sub> | GW<sub>th</sub>]", row=1, col=1, range=[0, added_power_max])
fig.update_yaxes(title_text="Capacity [GWh<sub>el</sub> | GWh<sub>th</sub>]", row=1, col=2, range=[0, pit_tes_max])

# Show the figure
fig.show()

# pio.write_image(
#     fig,
#     "Sensitivity_Analysis_in_2035.pdf",  # output filename
#     format="pdf",
#     width=PLOT_WIDTH,
#     height=PLOT_HEIGHT,
#     scale=10 #IMAGE_DPI / 1  # to get high DPI (e.g., 300)
# )

pdf_path = f"{output_base_path}.pdf"
png_path = f"{output_base_path}.png"

# ---- Write markdown description (before image export to ensure it's always produced) ----
md_path = f"{output_base_path}.md"
md_lines = [
    "# Investment Summary",
    "",
    "This plot shows installed power capacity (GW) and storage capacity (GWh) "
    "for different NTC scenarios.",
    "",
    "Note: Additional PV, Additional Wind, and Tank TES are intentionally omitted from the graphics to keep them readable. "
    "They are still listed in the markdown below for completeness and should only be mentioned briefly in the text, "
    "for example: 'there were PV investments of up to 3 GW'.",
    "",
    "## Installed Power Capacity (GW)",
    "",
]
# Build header
header = "| Technology | " + " | ".join(scenarios_display_names) + " |"
sep = "|------------|" + "|".join(["------"] * len(scenarios_display_names)) + "|"
md_lines.append(header)
md_lines.append(sep)
for tech in techs_to_document_power:
    row_vals = []
    for scen in scenarios_display_names:
        val = df[f'{scen} {categories[0]}'].loc[tech]
        row_vals.append(f"{val:.2f}")
    md_lines.append(f"| {tech} | " + " | ".join(row_vals) + " |")

md_lines += [
    "",
    "## Storage Capacity (GWh)",
    "",
]
header = "| Technology | " + " | ".join(scenarios_display_names) + " |"
md_lines.append(header)
md_lines.append(sep)
for tech in techs_to_document_storage:
    row_vals = []
    for scen in scenarios_display_names:
        val = df[f'{scen} {categories[1]}'].loc[tech]
        row_vals.append(f"{val:.2f}")
    md_lines.append(f"| {tech} | " + " | ".join(row_vals) + " |")
md_lines.append("")

with open(md_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md_lines))
print(f"Exported markdown to {md_path}")

# Export HTML
html_path = f"{output_base_path}.html"
fig.write_html(html_path)
print(f"Exported HTML to {html_path}")

# Export PDF and PNG
try:
    pio.write_image(
        fig,
        pdf_path,
        format="pdf",
        width=PLOT_WIDTH,
        height=PLOT_HEIGHT,
        scale=300 / (96/2)
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
        scale=300 / (96/2)
    )

    # Crop the top white bar from the exported PNG
    with Image.open(png_path) as img:
        width, height = img.size
        crop_top = 400
        crop_top = min(crop_top, height)
        cropped = img.crop((0, crop_top, width, height))
        cropped.save(png_path)
    print(f"Exported PNG to {png_path}")
except Exception as e:
    print(f"Warning: PNG export failed ({e}).")