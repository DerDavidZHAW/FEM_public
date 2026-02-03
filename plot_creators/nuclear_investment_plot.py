import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path
import re

# Set renderer to browser
pio.renderers.default = "browser"

# ========== CONFIGURATION ==========
run_date = '20260122'
year = '2050'  # Choose: '2035' or '2050'
# ===================================

base_path = Path(__file__).parent.parent / 'output' / run_date

# Define scenarios based on selected year
if year == '2035':
    scenarios = ['2035_sens_100', '2035_sens_90', '2035_sens_80', '2035_sens_70', 
                 '2035_sens_60', '2035_sens_50', '2035_sens_40', '2035_sens_30']
else:  # 2050
    scenarios = ['2050_sens_100_no_CHP', '2050_sens_90_no_CHP', '2050_sens_80_no_CHP', '2050_sens_70_no_CHP', 
                 '2050_sens_60_no_CHP', '2050_sens_50_no_CHP', '2050_sens_40_no_CHP', '2050_sens_30_no_CHP']

def extract_nuclear_breakeven(scenario_list):
    """Extract break_even_overnight and reduction_needed_overnight values for CH00_nuclear from each scenario"""
    sensitivity_values = []
    breakeven_values = []
    reduction_values = []
    
    for scenario in scenario_list:
        # Extract sensitivity percentage from scenario name using regex
        # Pattern: look for 'sens_XX' where XX is the percentage
        match = re.search(r'sens_(\d+)', scenario)
        if match:
            sens_pct = int(match.group(1))
        else:
            print(f"Warning: Could not extract sensitivity from scenario name: {scenario}")
            continue
        
        # Read CSV file
        csv_path = base_path / scenario / 'gen_max_reduced_cost.csv'
        try:
            df = pd.read_csv(csv_path)
            # Filter for CH00_nuclear
            nuclear_row = df[df['P_gen'] == 'CH00_nuclear']
            
            if not nuclear_row.empty:
                breakeven = nuclear_row['break_even_overnight'].values[0]
                reduction = nuclear_row['reduction_needed_overnight'].values[0]
                sensitivity_values.append(sens_pct)
                breakeven_values.append(breakeven)
                reduction_values.append(reduction)
        except FileNotFoundError:
            print(f"Warning: File not found - {csv_path}")
    
    return sensitivity_values, breakeven_values, reduction_values

# Extract data for the selected year
sens_values, breakeven_values, reduction_values = extract_nuclear_breakeven(scenarios)

# Create plot
fig = go.Figure()

# Add line for selected year
fig.add_trace(go.Scatter(
    x=sens_values,
    y=breakeven_values,
    mode='lines+markers',
    name=year,
    line=dict(width=2),
    marker=dict(size=8)
))

# Update layout
fig.update_layout(
    #title=f'Nuclear Break-Even Overnight Cost by Sensitivity Scenario ({year})',
    xaxis_title='Sensitivity (%)',
    yaxis_title='Break-Even Overnight Cost',
    xaxis=dict(autorange='reversed'),
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
    'Scenario': [year] * len(sens_values),
    'Sensitivity (%)': sens_values,
    'Break-Even Overnight Cost': breakeven_values,
    'Reduction Needed Overnight': reduction_values
}

results_df = pd.DataFrame(results_data)
results_df = results_df.sort_values(['Scenario', 'Sensitivity (%)'], ascending=[True, False])

csv_output_path = Path(__file__).parent / f'nuclear_breakeven_results_{year}_{run_date}.csv'
results_df.to_csv(csv_output_path, index=False)
print(f"Results table exported to {csv_output_path}")