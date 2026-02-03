"""
Battery Storage Net Revenue Analysis
Analyzes hourly net revenues and seasonal revenues for battery storage across different NTC scenarios.
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path

pio.renderers.default = "browser"

# Define scenarios in descending NTC order
ntc_values = [100, 90, 80, 70, 60, 50, 40, 30]
base_path = Path(r"C:\Models\Future_Markets\output\20260122")
year = "2050"

# Storage for all data
all_data = {}

print("Loading data from scenarios...")

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
        prices_ch = prices[prices['Node'] == 'CH00'].copy()
        
        # Adjust prices by weight to get real prices
        for subscenario, info in weather_years.items():
            mask = prices_ch['Scenarios'] == subscenario
            prices_ch.loc[mask, 'adjusted_price'] = prices_ch.loc[mask, 'value'] / info['weight']
        
        # Read generation (discharge)
        gen_file = scenario_path / "gen.csv"
        gen = pd.read_csv(gen_file)
        gen_battery = gen[gen['P_gen'] == 'CH00_battery'].copy()
        gen_battery.rename(columns={'value': 'discharge_power'}, inplace=True)
        
        # Read charging
        charge_file = scenario_path / "storage_charge.csv"
        charge = pd.read_csv(charge_file)
        charge_battery = charge[charge['P_pumping'] == 'CH00_battery'].copy()
        charge_battery.rename(columns={'value': 'charge_power'}, inplace=True)
        
        # Read installed capacity
        gen_max_file = scenario_path / "gen_max.csv"
        gen_max = pd.read_csv(gen_max_file)
        gen_max_battery = gen_max[gen_max['P_gen'] == 'CH00_battery']
        
        if len(gen_max_battery) == 0:
            print(f"  Warning: No CH00_battery found in gen_max.csv for {scenario_name}")
            continue
        
        # Get installed capacity (should be same for all subscenarios)
        installed_capacity = gen_max_battery['value'].iloc[0]
        print(f"  Installed capacity: {installed_capacity:.2f} MW")
        
        # Merge data
        data = prices_ch[['T', 'Scenarios', 'adjusted_price']].merge(
            gen_battery[['T', 'Scenarios', 'discharge_power']], 
            on=['T', 'Scenarios'], 
            how='outer'
        )
        data = data.merge(
            charge_battery[['T', 'Scenarios', 'charge_power']], 
            on=['T', 'Scenarios'], 
            how='outer'
        )
        
        # Fill NaN values with 0 for power (in case battery doesn't operate in all hours)
        data['discharge_power'] = data['discharge_power'].fillna(0)
        data['charge_power'] = data['charge_power'].fillna(0)
        
        # Calculate normalized power (per 1 MW)
        data['discharge_per_mw'] = data['discharge_power'] / installed_capacity
        data['charge_per_mw'] = data['charge_power'] / installed_capacity
        
        # Calculate revenues and costs (efficiency already in model)
        data['revenue'] = data['discharge_per_mw'] * data['adjusted_price']
        data['cost'] = data['charge_per_mw'] * data['adjusted_price']
        data['net_revenue'] = data['revenue'] - data['cost']
        
        # Add time index
        data['time_index'] = data['T'].str.replace('t_', '').astype(int)
        data['ntc'] = ntc
        
        # Store data
        all_data[ntc] = data
        print(f"  Loaded {len(data)} rows")
        
    except Exception as e:
        print(f"  Error processing {scenario_name}: {e}")
        continue

if len(all_data) == 0:
    print("No data loaded. Exiting.")
    exit()

print("\n" + "="*50)
print("Creating Plot 1: Hourly Net Revenue")
print("="*50)

# Plot 1: Hourly net revenue for each subscenario
fig1 = go.Figure()

colors = {
    '1995': '#1f77b4',
    '2008': '#ff7f0e', 
    '2009': '#2ca02c'
}

for ntc in sorted(all_data.keys(), reverse=True):
    data = all_data[ntc]
    for subscenario in sorted(data['Scenarios'].unique()):
        sub_data = data[data['Scenarios'] == subscenario].sort_values('time_index')
        wy = subscenario.split('_wy')[-1]
        
        fig1.add_trace(go.Scatter(
            x=sub_data['time_index'],
            y=sub_data['net_revenue'],
            mode='lines',
            name=f'NTC {ntc}% - WY{wy}',
            line=dict(width=1.5)
        ))

fig1.update_layout(
    title='Hourly Net Revenue for 1 MW Battery Storage<br><sub>Across NTC Scenarios and Weather Years</sub>',
    xaxis_title='Time Step (t)',
    yaxis_title='Net Revenue (€/h per MW)',
    hovermode='x unified',
    height=700,
    legend=dict(
        orientation="v",
        yanchor="top",
        y=1,
        xanchor="left",
        x=1.02
    ),
    template='plotly_white'
)

fig1.show()

print("\n" + "="*50)
print("Creating Plot 2: Seasonal Net Revenue")
print("="*50)

# Plot 2: Sum of net revenues by season
# Winter: t_1-t_2184 and t_6553-t_8760
# Summer: t_2185-t_6552
winter_periods = set(range(1, 2185)) | set(range(6553, 8761))
summer_periods = set(range(2185, 6553))

seasonal_data = []

for ntc in sorted(all_data.keys(), reverse=True):
    data = all_data[ntc]
    for subscenario in sorted(data['Scenarios'].unique()):
        sub_data = data[data['Scenarios'] == subscenario]
        wy = subscenario.split('_wy')[-1]
        
        winter_revenue = sub_data[sub_data['time_index'].isin(winter_periods)]['net_revenue'].sum()
        summer_revenue = sub_data[sub_data['time_index'].isin(summer_periods)]['net_revenue'].sum()
        total_revenue = winter_revenue + summer_revenue
        
        seasonal_data.append({
            'NTC': ntc,
            'Weather_Year': wy,
            'Winter': winter_revenue,
            'Summer': summer_revenue,
            'Total': total_revenue
        })
        
        print(f"NTC {ntc}%, WY{wy}: Winter={winter_revenue:.2f} €, Summer={summer_revenue:.2f} €, Total={total_revenue:.2f} €")

seasonal_df = pd.DataFrame(seasonal_data)

fig2 = go.Figure()

# Sort by NTC descending for x-axis
ntc_order = sorted(seasonal_df['NTC'].unique(), reverse=True)
weather_years = sorted(seasonal_df['Weather_Year'].unique())

# Individual subscenario traces (NTC + Weather Year combinations)
for ntc in ntc_order:
    ntc_data = seasonal_df[seasonal_df['NTC'] == ntc].sort_values('Weather_Year')
    
    for _, row in ntc_data.iterrows():
        wy = row['Weather_Year']
        
        # Winter trace
        fig2.add_trace(go.Bar(
            x=[row['NTC']],
            y=[row['Winter']],
            name=f'NTC {row["NTC"]}% - WY{wy} - Winter',
            marker_pattern_shape="/",
            legendgroup='Winter',
            legendgrouptitle_text='Winter',
            hovertemplate='Winter Revenue: %{y:.2f} €<extra></extra>'
        ))
        
        # Summer trace
        fig2.add_trace(go.Bar(
            x=[row['NTC']],
            y=[row['Summer']],
            name=f'NTC {row["NTC"]}% - WY{wy} - Summer',
            legendgroup='Summer',
            legendgrouptitle_text='Summer',
            hovertemplate='Summer Revenue: %{y:.2f} €<extra></extra>'
        ))
        
        # Total trace
        fig2.add_trace(go.Bar(
            x=[row['NTC']],
            y=[row['Total']],
            name=f'NTC {row["NTC"]}% - WY{wy} - Total',
            marker_line_width=2,
            marker_line_color='darkgray',
            legendgroup='Total',
            legendgrouptitle_text='Total',
            hovertemplate='Total Revenue: %{y:.2f} €<extra></extra>'
        ))

# Sum over all NTC for each weather year
for wy in weather_years:
    wy_data = seasonal_df[seasonal_df['Weather_Year'] == wy]
    sum_winter = wy_data['Winter'].sum()
    sum_summer = wy_data['Summer'].sum()
    sum_total = wy_data['Total'].sum()
    
    fig2.add_trace(go.Bar(
        x=['All NTC'],
        y=[sum_winter],
        name=f'All NTC - WY{wy} - Winter',
        marker_pattern_shape="/",
        legendgroup='Winter',
        hovertemplate=f'WY{wy} Sum Winter: %{{y:.2f}} €<extra></extra>'
    ))
    
    fig2.add_trace(go.Bar(
        x=['All NTC'],
        y=[sum_summer],
        name=f'All NTC - WY{wy} - Summer',
        legendgroup='Summer',
        hovertemplate=f'WY{wy} Sum Summer: %{{y:.2f}} €<extra></extra>'
    ))
    
    fig2.add_trace(go.Bar(
        x=['All NTC'],
        y=[sum_total],
        name=f'All NTC - WY{wy} - Total',
        marker_line_width=2,
        marker_line_color='darkgray',
        legendgroup='Total',
        hovertemplate=f'WY{wy} Sum Total: %{{y:.2f}} €<extra></extra>'
    ))

# Sum over all weather years for each NTC
for ntc in ntc_order:
    ntc_data = seasonal_df[seasonal_df['NTC'] == ntc]
    sum_winter = ntc_data['Winter'].sum()
    sum_summer = ntc_data['Summer'].sum()
    sum_total = ntc_data['Total'].sum()
    
    fig2.add_trace(go.Bar(
        x=[ntc],
        y=[sum_winter],
        name=f'NTC {ntc}% - All WY - Winter',
        marker_pattern_shape="/",
        marker_color='rgba(100, 100, 100, 0.7)',
        legendgroup='Winter',
        hovertemplate=f'NTC {ntc}% All WY Winter: %{{y:.2f}} €<extra></extra>'
    ))
    
    fig2.add_trace(go.Bar(
        x=[ntc],
        y=[sum_summer],
        name=f'NTC {ntc}% - All WY - Summer',
        marker_color='rgba(150, 150, 150, 0.7)',
        legendgroup='Summer',
        hovertemplate=f'NTC {ntc}% All WY Summer: %{{y:.2f}} €<extra></extra>'
    ))
    
    fig2.add_trace(go.Bar(
        x=[ntc],
        y=[sum_total],
        name=f'NTC {ntc}% - All WY - Total',
        marker_line_width=2,
        marker_line_color='black',
        marker_color='rgba(200, 200, 200, 0.7)',
        legendgroup='Total',
        hovertemplate=f'NTC {ntc}% All WY Total: %{{y:.2f}} €<extra></extra>'
    ))

# X-axis categories including 'All NTC'
x_categories = [str(ntc) for ntc in ntc_order] + ['All NTC']

fig2.update_layout(
    title='Total Net Revenue by Season for 1 MW Battery Storage<br><sub>Comparison across NTC Scenarios and Weather Years</sub>',
    xaxis_title='NTC Availability (%)',
    yaxis_title='Total Net Revenue (€ per MW)',
    barmode='group',
    height=700,
    xaxis=dict(
        tickmode='array', 
        tickvals=x_categories,
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

print("\n" + "="*50)
print("Summary Statistics")
print("="*50)
print("\nSeasonal Revenue Summary:")
print(seasonal_df.pivot_table(
    index='NTC', 
    columns='Weather_Year', 
    values=['Winter', 'Summer', 'Total'],
    aggfunc='sum'
))

print("\nScript completed successfully!")
