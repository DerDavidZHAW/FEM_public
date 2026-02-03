"""
Electricity Prices Analysis
Plots hourly electricity prices across different NTC scenarios for multiple countries.
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path

pio.renderers.default = "browser"

# ============================================
# CONFIGURATION - Choose the run year here
# ============================================
year = "2050"  # Options: "2035", "2050", etc.

# Define scenarios in descending NTC order
ntc_values = [100, 30] #90, 80, 70, 60, 50, 40, 30]
base_path = Path(r"C:\Models\Future_Markets\output\20260122")

# Countries to analyze
countries = ['CH00', 'DE00', 'FR00', 'IT00', 'AT00']
country_names = {'CH00': 'Switzerland', 'DE00': 'Germany', 'FR00': 'France', 'IT00': 'Italy', 'AT00': 'Austria'}

# Storage for all data
all_data = {}

print(f"Loading data for year {year}...")
print("=" * 50)

for ntc in ntc_values:
    scenario_name = f"{year}_sens_{ntc}_fixed_inv"
    scenario_path = base_path / scenario_name
    
    if not scenario_path.exists():
        print(f"Warning: {scenario_name} not found, skipping...")
        continue
    
    print(f"Processing {scenario_name}...")
    
    try:
        # Read settings to get weights
        settings_file = scenario_path / "settings.csv"
        settings = pd.read_csv(settings_file)
        
        # Extract weather years and weights
        wy_row = settings[settings['Item'] == 'sub_secn'].iloc[0]
        weight_row = settings[settings['Item'] == 'weight_in_objective_fcn'].iloc[0]
        
        weather_years = {}
        for col in settings.columns[1:]:  # Skip 'Item' column
            wy = wy_row[col]
            weight = float(weight_row[col])
            weather_years[col] = {'wy': wy, 'weight': weight}
        
        # Read prices
        prices_file = scenario_path / "energy_balance_dual.csv"
        prices = pd.read_csv(prices_file)
        
        # Filter for countries of interest
        prices = prices[prices['Node'].isin(countries)].copy()
        
        # Adjust prices by weight to get real prices
        for subscenario, info in weather_years.items():
            mask = prices['Scenarios'] == subscenario
            prices.loc[mask, 'adjusted_price'] = prices.loc[mask, 'value'] / info['weight']
        
        # Add time index
        prices['time_index'] = prices['T'].str.replace('t_', '').astype(int)
        prices['ntc'] = ntc
        
        # Store data
        all_data[ntc] = prices
        print(f"  Loaded {len(prices)} rows for {len(countries)} countries")
        
    except Exception as e:
        print(f"  Error processing {scenario_name}: {e}")
        continue

if len(all_data) == 0:
    print("No data loaded. Exiting.")
    exit()

print("\n" + "=" * 50)
print("Creating Plot: Hourly Electricity Prices")
print("=" * 50)

# Define colors for countries
country_colors = {
    'CH00': '#e41a1c',  # Red
    'DE00': '#000000',  # Black
    'FR00': '#377eb8',  # Blue
    'IT00': '#4daf4a',  # Green
    'AT00': '#984ea3'   # Purple
}

# Create figure
fig = go.Figure()

for ntc in sorted(all_data.keys(), reverse=True):
    data = all_data[ntc]
    
    for country in countries:
        country_data = data[data['Node'] == country]
        
        for subscenario in sorted(country_data['Scenarios'].unique()):
            sub_data = country_data[country_data['Scenarios'] == subscenario].sort_values('time_index')
            wy = subscenario.split('_wy')[-1]
            
            fig.add_trace(go.Scatter(
                x=sub_data['time_index'],
                y=sub_data['adjusted_price'],
                mode='lines',
                name=f'NTC {ntc}% - {country_names[country]} - WY{wy}',
                line=dict(width=1, color=country_colors[country]),
                legendgroup=country,
                legendgrouptitle_text=country_names[country],
                hovertemplate=f'{country_names[country]}<br>NTC {ntc}% - WY{wy}<br>Hour: %{{x}}<br>Price: %{{y:.2f}} €/MWh<extra></extra>'
            ))

fig.update_layout(
    title=f'Hourly Electricity Prices ({year})<br><sub>Across NTC Scenarios and Weather Years</sub>',
    xaxis_title='Time Step (t)',
    yaxis_title='Price (€/MWh)',
    hovermode='x unified',
    height=800,
    legend=dict(
        orientation="v",
        yanchor="top",
        y=1,
        xanchor="left",
        x=1.02,
        groupclick="toggleitem"
    ),
    template='plotly_white'
)

fig.show()

print("\n" + "=" * 50)
print("Creating Plot: Average Prices by NTC and Country")
print("=" * 50)

# Calculate average prices per NTC and country
avg_prices = []

for ntc in sorted(all_data.keys(), reverse=True):
    data = all_data[ntc]
    
    for country in countries:
        country_data = data[data['Node'] == country]
        
        for subscenario in sorted(country_data['Scenarios'].unique()):
            sub_data = country_data[country_data['Scenarios'] == subscenario]
            wy = subscenario.split('_wy')[-1]
            avg_price = sub_data['adjusted_price'].mean()
            
            avg_prices.append({
                'NTC': ntc,
                'Country': country,
                'Country_Name': country_names[country],
                'Weather_Year': wy,
                'Avg_Price': avg_price
            })

avg_df = pd.DataFrame(avg_prices)

# Create bar chart for average prices
fig2 = go.Figure()

ntc_order = sorted(avg_df['NTC'].unique(), reverse=True)
weather_years = sorted(avg_df['Weather_Year'].unique())

for country in countries:
    for wy in weather_years:
        filtered = avg_df[(avg_df['Country'] == country) & (avg_df['Weather_Year'] == wy)].sort_values('NTC', ascending=False)
        
        fig2.add_trace(go.Bar(
            x=filtered['NTC'],
            y=filtered['Avg_Price'],
            name=f'{country_names[country]} - WY{wy}',
            legendgroup=country,
            legendgrouptitle_text=country_names[country],
            marker_color=country_colors[country],
            opacity=0.5 + 0.15 * weather_years.index(wy),
            hovertemplate=f'{country_names[country]} - WY{wy}<br>NTC: %{{x}}%<br>Avg Price: %{{y:.2f}} €/MWh<extra></extra>'
        ))

fig2.update_layout(
    title=f'Average Electricity Prices by NTC Level ({year})<br><sub>Comparison across Countries and Weather Years</sub>',
    xaxis_title='NTC Availability (%)',
    yaxis_title='Average Price (€/MWh)',
    barmode='group',
    height=700,
    xaxis=dict(
        tickmode='array',
        tickvals=ntc_order,
        type='category'
    ),
    legend=dict(
        orientation="v",
        yanchor="top",
        y=1,
        xanchor="left",
        x=1.02,
        groupclick="toggleitem"
    ),
    template='plotly_white'
)

fig2.show()

print("\n" + "=" * 50)
print("Summary Statistics")
print("=" * 50)
print("\nAverage Price Summary (€/MWh):")
print(avg_df.pivot_table(
    index=['NTC', 'Weather_Year'],
    columns='Country_Name',
    values='Avg_Price',
    aggfunc='mean'
).round(2))

print("\nScript completed successfully!")
