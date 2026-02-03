"""
Script to create monthly pie charts showing heat sources (Heat Pumps, Resistive Heaters, CHP)
for two scenarios: 2035_sens_100_fixed_inv and 2035_sens_30_fixed_inv
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
from pathlib import Path

pio.renderers.default = "browser"

# ========== CONFIGURATION ==========
scenarios = {
    "NTC 100%": r"C:\Models\Future_Markets\output\20260122\2035_sens_100_fixed_inv",
    "NTC 30%": r"C:\Models\Future_Markets\output\20260122\2035_sens_30_fixed_inv",
}
# ===================================

# Define colors for heat sources
colors = {
    'Heat Pumps': '#ff7f0e',  # orange
    'Resistive Heaters': '#1f77b4',  # blue
    'CHP': '#bcbd22',  # olive
}

# Month order (hydro year starts in October)
month_order = ['oct', 'nov', 'dec', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep']
month_labels = ['Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep']

# Read time mapping
base_dir = Path(__file__).parent.parent
timemap_path = base_dir / "input" / "timemaps_hydro_year.csv"
timemap_df = pd.read_csv(timemap_path)

# Create t to month mapping
t_to_month = dict(zip(timemap_df['t'], timemap_df['month']))

# Initialize storage for results
# Structure: results[scenario][month] = {'HP': value, 'resistive': value, 'CHP': value}
results = {}

for scenario_name, scenario_path in scenarios.items():
    print(f"\nProcessing scenario: {scenario_name}")
    
    # Read thermal generation data
    genTh_path = f"{scenario_path}\\genTh.csv"
    genTh_df = pd.read_csv(genTh_path)
    
    # Read scenario weights
    weights_path = f"{scenario_path}\\weight_in_objective_fcn.csv"
    weights_df = pd.read_csv(weights_path)
    weights_dict = dict(zip(weights_df['Scenarios'], weights_df['value']))
    
    print(f"  Scenario weights: {weights_dict}")
    
    # Add month column based on T
    genTh_df['month'] = genTh_df['T'].map(t_to_month)
    
    # Initialize monthly results
    monthly_results = {month: {'HP': 0, 'resistive': 0, 'CHP': 0} for month in month_order}
    
    # Process each plant
    for plant in genTh_df['PDH'].unique():
        plant_data = genTh_df[genTh_df['PDH'] == plant].copy()
        
        # Determine technology type
        is_hp = ('_HPNew' in plant or '_HPG' in plant or 'HP' in plant)
        is_resistive = '_resistiveNew' in plant or 'resistive' in plant.lower()
        is_chp = '_CHPNew' in plant or 'CHP' in plant
        
        if not (is_hp or is_resistive or is_chp):
            continue
        
        # Determine category
        if is_hp:
            cat = 'HP'
        elif is_resistive:
            cat = 'resistive'
        elif is_chp:
            cat = 'CHP'
        else:
            continue
        
        # Apply weights and aggregate by month
        for subscen in plant_data['Scenarios'].unique():
            subscen_data = plant_data[plant_data['Scenarios'] == subscen]
            weight = weights_dict.get(subscen, 1.0 / 3)
            
            # Group by month and sum
            monthly_gen = subscen_data.groupby('month')['value'].sum() * weight
            
            for month, gen_value in monthly_gen.items():
                if month in monthly_results:
                    monthly_results[month][cat] += gen_value
    
    results[scenario_name] = monthly_results
    
    # Print summary
    print(f"\n  Monthly heat generation summary for {scenario_name} (GWh):")
    for month in month_order:
        hp = monthly_results[month]['HP'] / 1000
        rh = monthly_results[month]['resistive'] / 1000
        chp = monthly_results[month]['CHP'] / 1000
        print(f"    {month.upper()}: HP={hp:.1f}, RH={rh:.1f}, CHP={chp:.1f}")

# Create figure with 4 rows (2 per scenario: Oct-Mar, Apr-Sep) and 6 columns
# Row 1: Scenario 1, Oct-Mar
# Row 2: Scenario 1, Apr-Sep
# Row 3: Scenario 2, Oct-Mar
# Row 4: Scenario 2, Apr-Sep
num_cols = 6
num_rows = 4

# Month labels for each half
months_first_half = ['Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']
months_second_half = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep']
months_order_first = ['oct', 'nov', 'dec', 'jan', 'feb', 'mar']
months_order_second = ['apr', 'may', 'jun', 'jul', 'aug', 'sep']

scenario_names = list(scenarios.keys())

# Create subplot titles (month labels only for rows 1 and 3)
subplot_titles = months_first_half + months_second_half + months_first_half + months_second_half

fig = make_subplots(
    rows=num_rows, cols=num_cols,
    specs=[[{"type": "pie"}] * num_cols for _ in range(num_rows)],
    subplot_titles=subplot_titles,
    vertical_spacing=0.08,
    horizontal_spacing=0.02,
)

# Add pie charts
for scen_idx, (scenario_name, monthly_data) in enumerate(results.items()):
    # First half: Oct-Mar (rows 1 and 3)
    row_first = scen_idx * 2 + 1
    for col_idx, month in enumerate(months_order_first):
        heat_values = [
            monthly_data[month]['HP'] / 1000,
            monthly_data[month]['resistive'] / 1000,
            monthly_data[month]['CHP'] / 1000,
        ]
        heat_labels = ['Heat Pumps', 'Resistive Heaters', 'CHP']
        
        filtered_labels = [l for l, v in zip(heat_labels, heat_values) if v > 0.01]
        filtered_values = [v for v in heat_values if v > 0.01]
        filtered_colors = [colors[l] for l in filtered_labels]
        
        if filtered_values:
            fig.add_trace(go.Pie(
                labels=filtered_labels,
                values=filtered_values,
                name=f'{scenario_name} - {month}',
                marker_colors=filtered_colors,
                textinfo='percent',
                textposition='inside',
                hovertemplate='%{label}: %{value:.1f} GWh<extra></extra>',
                showlegend=(scen_idx == 0 and col_idx == 0),
            ), row=row_first, col=col_idx + 1)
    
    # Second half: Apr-Sep (rows 2 and 4)
    row_second = scen_idx * 2 + 2
    for col_idx, month in enumerate(months_order_second):
        heat_values = [
            monthly_data[month]['HP'] / 1000,
            monthly_data[month]['resistive'] / 1000,
            monthly_data[month]['CHP'] / 1000,
        ]
        heat_labels = ['Heat Pumps', 'Resistive Heaters', 'CHP']
        
        filtered_labels = [l for l, v in zip(heat_labels, heat_values) if v > 0.01]
        filtered_values = [v for v in heat_values if v > 0.01]
        filtered_colors = [colors[l] for l in filtered_labels]
        
        if filtered_values:
            fig.add_trace(go.Pie(
                labels=filtered_labels,
                values=filtered_values,
                name=f'{scenario_name} - {month}',
                marker_colors=filtered_colors,
                textinfo='percent',
                textposition='inside',
                hovertemplate='%{label}: %{value:.1f} GWh<extra></extra>',
                showlegend=False,
            ), row=row_second, col=col_idx + 1)

# Update layout
fig.update_layout(
    height=700,
    width=1100,
    template='plotly_white',
    legend=dict(
        orientation="h",
        yanchor="top",
        y=1.18,  # move legend further up
        xanchor="center",
        x=0.5,
        font=dict(size=13),
    ),
    margin=dict(l=140, r=20, t=120, b=20),  # more left and top margin
)

# Add scenario name annotations manually after layout
# NOTE: Static exports (PDF/PNG) may render these differently than the web version.
# To improve alignment, move x further left.
fig.add_annotation(
    text=f"<b>{scenario_names[0]}</b>",
    x=-0.08,  # further left for static export
    y=0.85,
    xref="paper",
    yref="paper",
    showarrow=False,
    font=dict(size=14),
    textangle=-90,
)
fig.add_annotation(
    text=f"<b>{scenario_names[1]}</b>",
    x=-0.08,  # further left for static export
    y=0.15,
    xref="paper",
    yref="paper",
    showarrow=False,
    font=dict(size=14),
    textangle=-90,
)

# Show plot
fig.show()

# Export to HTML
output_path = Path(__file__).parent / "monthly_heat_sources.html"
fig.write_html(output_path)
print(f"\nPlot exported to {output_path}")

# Export to PDF
pdf_path = Path(__file__).parent / "monthly_heat_sources.pdf"
fig.write_image(pdf_path, format="pdf")
print(f"Plot exported to {pdf_path}")

# Export to PNG and crop top and left
from PIL import Image
import io

png_bytes = fig.to_image(format="png", scale=3)
img = Image.open(io.BytesIO(png_bytes))

# Crop 100px from top and 40px from left
crop_top = 150
crop_left = 250
cropped_img = img.crop((crop_left, crop_top, img.width, img.height))

png_path = Path(__file__).parent / "monthly_heat_sources.png"
cropped_img.save(png_path)
print(f"Plot exported to {png_path} (cropped top {crop_top}px, left {crop_left}px)")
