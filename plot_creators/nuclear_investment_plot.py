import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path
import re

# Set renderer to browser
pio.renderers.default = "browser"

# ========== CONFIGURATION ==========
run_date = '20260205_MIP3_v4'
year = '2050'  # Choose: '2035' or '2050'
# ===================================

base_path = Path(__file__).parent.parent / 'output' / run_date

# Define scenarios based on selected year by scanning the selected run_date folder
scenarios = sorted([
    scenario_dir.name
    for scenario_dir in base_path.iterdir()
    if scenario_dir.is_dir() and scenario_dir.name.startswith(f'{year}_')
])

if not scenarios:
    raise FileNotFoundError(f"No scenarios found for year {year} in {base_path}")

def extract_nuclear_breakeven(scenario_list):
    """Extract break_even_overnight and reduction_needed_overnight values for CH00_nuclear from each scenario"""
    x_values = []
    breakeven_values = []
    reduction_values = []
    
    for scenario in scenario_list:
        # Extract numeric sensitivity when available, otherwise use scenario suffix as label
        match = re.search(r'sens_(\d+)', scenario)
        if match:
            x_value = int(match.group(1))
        else:
            x_value = scenario.split('_', 1)[1] if '_' in scenario else scenario
        
        # Read CSV file
        csv_path = base_path / scenario / 'gen_max_reduced_cost.csv'
        try:
            df = pd.read_csv(csv_path)
            # Filter for CH00_nuclear
            nuclear_row = df[df['P_gen'] == 'CH00_nuclear']
            
            if not nuclear_row.empty:
                breakeven = nuclear_row['break_even_overnight'].values[0]
                reduction = nuclear_row['reduction_needed_overnight'].values[0]
                x_values.append(x_value)
                breakeven_values.append(breakeven)
                reduction_values.append(reduction)
            else:
                print(f"Warning: CH00_nuclear not found in {csv_path}")
        except FileNotFoundError:
            print(f"Warning: File not found - {csv_path}")
    
    return x_values, breakeven_values, reduction_values

# Extract data for the selected year
x_values, breakeven_values, reduction_values = extract_nuclear_breakeven(scenarios)
is_numeric_x = all(isinstance(value, (int, float)) for value in x_values)
x_axis_title = 'Sensitivity (%)' if is_numeric_x else 'Scenario'

if not x_values:
    raise ValueError(f"No CH00_nuclear data found for year {year} in scenarios under {base_path}")

# Create plot
fig = go.Figure()

# Add line for selected year
fig.add_trace(go.Scatter(
    x=x_values,
    y=breakeven_values,
    mode='lines+markers',
    name=year,
    line=dict(width=2),
    marker=dict(size=8)
))

# Update layout
fig.update_layout(
    #title=f'Nuclear Break-Even Overnight Cost by Sensitivity Scenario ({year})',
    xaxis_title=x_axis_title,
    yaxis_title='Break-Even Overnight Cost',
    xaxis=dict(autorange='reversed') if is_numeric_x else dict(categoryorder='array', categoryarray=x_values),
    hovermode='x unified',
    template='plotly_white',
    width=1000,
    height=600,
    legend=dict(
        yanchor="top",
        y=0.99,
        xanchor="right",
        x=0.99
    )
)

# Show plot
fig.show()

# Export as PDF
output_path = Path(__file__).parent / f'nuclear_breakeven_analysis_{year}_{run_date}.pdf'
pio.write_image(fig, output_path)
print(f"Plot exported to {output_path}")

# Create and export CSV table with results
results_data = {
    'Scenario': [year] * len(x_values),
    x_axis_title: x_values,
    'Break-Even Overnight Cost': breakeven_values,
    'Reduction Needed Overnight': reduction_values
}

results_df = pd.DataFrame(results_data)
if is_numeric_x:
    results_df = results_df.sort_values([x_axis_title], ascending=[False])

csv_output_path = Path(__file__).parent / f'nuclear_breakeven_results_{year}_{run_date}.csv'
results_df.to_csv(csv_output_path, index=False)
print(f"Results table exported to {csv_output_path}")