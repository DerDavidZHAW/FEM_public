import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.offline as pyo

# Read the input data
input_file = "input/neighbour_prices_for_CH_only_mode/data_code_to_generate_neighbour_prices/SESETH.csv"
df_input = pd.read_csv(input_file)

print(f"Input data shape: {df_input.shape}")
print(f"Time steps range: {df_input['time_step'].iloc[0]} to {df_input['time_step'].iloc[-1]}")

# Extract time step numbers (remove 't_' prefix)
time_steps = df_input['time_step'].str.replace('t_', '').astype(int)
prices = np.array(df_input['price'].values, dtype=float)

print(f"Original time steps: {time_steps.min()} to {time_steps.max()}")
print(f"Number of original data points: {len(time_steps)}")

# Use seasonal approach based on first 9 days (216 hours)
# Extract patterns for each season from the first 864 hours
hours_per_day = 24
days_per_season = 9
hours_per_season_pattern = days_per_season * hours_per_day  # 216 hours

print(f"\nSeasonal approach:")
print(f"Using first {days_per_season} days ({hours_per_season_pattern} hours) as seasonal patterns")

# Define seasonal patterns from the first 864 hours
# Assume the data represents different seasonal patterns in sequence
winter_pattern = prices[0:216]                    # First 9 days (t_1 to t_216)
spring_pattern = prices[216:432]                  # Next 9 days (t_217 to t_432)
summer_pattern = prices[432:648]                  # Next 9 days (t_433 to t_648)
autumn_pattern = prices[648:864] if len(prices) >= 864 else prices[648:]  # Last part

print(f"Winter pattern: {len(winter_pattern)} hours, price range: {winter_pattern.min():.2f} - {winter_pattern.max():.2f}")
print(f"Spring pattern: {len(spring_pattern)} hours, price range: {spring_pattern.min():.2f} - {spring_pattern.max():.2f}")
print(f"Summer pattern: {len(summer_pattern)} hours, price range: {summer_pattern.min():.2f} - {summer_pattern.max():.2f}")
print(f"Autumn pattern: {len(autumn_pattern)} hours, price range: {autumn_pattern.min():.2f} - {autumn_pattern.max():.2f}")

# Define seasonal lengths (from PSI data structure)
# Winter: 91 days = 2184 hours
# Spring: 91 days = 2184 hours  
# Summer: 92 days = 2208 hours
# Fall: 91 days = 2184 hours
seasonal_hours = {
    'Winter': 2184,
    'Spring': 2184, 
    'Summer': 2208,
    'Fall': 2184
}

print(f"\nSeasonal distribution (from PSI structure):")
for season, hours in seasonal_hours.items():
    print(f"{season}: {hours} hours ({hours/24:.0f} days)")

total_hours = sum(seasonal_hours.values())
print(f"Total: {total_hours} hours")

# Generate full year time series by repeating seasonal patterns
full_prices = []
season_labels = []
time_step_labels = []

current_time_step = 1

# Winter
winter_cycles = seasonal_hours['Winter'] // len(winter_pattern)
winter_remainder = seasonal_hours['Winter'] % len(winter_pattern)
print(f"\nWinter: {winter_cycles} complete cycles + {winter_remainder} additional hours")

for cycle in range(winter_cycles):
    full_prices.extend(winter_pattern)
    season_labels.extend(['Winter'] * len(winter_pattern))
    time_step_labels.extend([f't_{i}' for i in range(current_time_step, current_time_step + len(winter_pattern))])
    current_time_step += len(winter_pattern)

if winter_remainder > 0:
    full_prices.extend(winter_pattern[:winter_remainder])
    season_labels.extend(['Winter'] * winter_remainder)
    time_step_labels.extend([f't_{i}' for i in range(current_time_step, current_time_step + winter_remainder)])
    current_time_step += winter_remainder

# Spring
spring_cycles = seasonal_hours['Spring'] // len(spring_pattern)
spring_remainder = seasonal_hours['Spring'] % len(spring_pattern)
print(f"Spring: {spring_cycles} complete cycles + {spring_remainder} additional hours")

for cycle in range(spring_cycles):
    full_prices.extend(spring_pattern)
    season_labels.extend(['Spring'] * len(spring_pattern))
    time_step_labels.extend([f't_{i}' for i in range(current_time_step, current_time_step + len(spring_pattern))])
    current_time_step += len(spring_pattern)

if spring_remainder > 0:
    full_prices.extend(spring_pattern[:spring_remainder])
    season_labels.extend(['Spring'] * spring_remainder)
    time_step_labels.extend([f't_{i}' for i in range(current_time_step, current_time_step + spring_remainder)])
    current_time_step += spring_remainder

# Summer
summer_cycles = seasonal_hours['Summer'] // len(summer_pattern)
summer_remainder = seasonal_hours['Summer'] % len(summer_pattern)
print(f"Summer: {summer_cycles} complete cycles + {summer_remainder} additional hours")

for cycle in range(summer_cycles):
    full_prices.extend(summer_pattern)
    season_labels.extend(['Summer'] * len(summer_pattern))
    time_step_labels.extend([f't_{i}' for i in range(current_time_step, current_time_step + len(summer_pattern))])
    current_time_step += len(summer_pattern)

if summer_remainder > 0:
    full_prices.extend(summer_pattern[:summer_remainder])
    season_labels.extend(['Summer'] * summer_remainder)
    time_step_labels.extend([f't_{i}' for i in range(current_time_step, current_time_step + summer_remainder)])
    current_time_step += summer_remainder

# Fall/Autumn
fall_cycles = seasonal_hours['Fall'] // len(autumn_pattern)
fall_remainder = seasonal_hours['Fall'] % len(autumn_pattern)
print(f"Fall: {fall_cycles} complete cycles + {fall_remainder} additional hours")

for cycle in range(fall_cycles):
    full_prices.extend(autumn_pattern)
    season_labels.extend(['Fall'] * len(autumn_pattern))
    time_step_labels.extend([f't_{i}' for i in range(current_time_step, current_time_step + len(autumn_pattern))])
    current_time_step += len(autumn_pattern)

if fall_remainder > 0:
    full_prices.extend(autumn_pattern[:fall_remainder])
    season_labels.extend(['Fall'] * fall_remainder)
    time_step_labels.extend([f't_{i}' for i in range(current_time_step, current_time_step + fall_remainder)])

full_prices = np.array(full_prices)
print(f"\nGenerated {len(full_prices)} total hours")
print(f"Price range: {full_prices.min():.2f} - {full_prices.max():.2f} EUR/MWh")

# Define neighbor countries for CH_only mode
neighbor_countries = ["DE00", "AT00", "FR00", "IT00"]

# Create the output DataFrame with time_step as rows and countries as columns
output_data = {
    'time_step': time_step_labels
}

# Add each country as a column with the same seasonal prices
for country in neighbor_countries:
    output_data[country] = full_prices.tolist()

df_output = pd.DataFrame(output_data)

print(f"\nOutput data shape: {df_output.shape}")
print(f"Columns: {list(df_output.columns)}")
print(f"Number of time steps: {len(df_output)}")

# Save to CSV
output_file = "input/neighbour_prices_for_CH_only_mode/neighbor_prices_SESETH.csv"
df_output.to_csv(output_file, index=False)

print(f"\nFile saved to: {output_file}")

# Show sample of the output
print("\nSample output:")
print(df_output.head(10))
print("...")
print(df_output.tail(10))

print(f"\nPrice verification across countries:")
print(f"t_1: DE00={df_output.loc[0, 'DE00']:.2f}, AT00={df_output.loc[0, 'AT00']:.2f}, FR00={df_output.loc[0, 'FR00']:.2f}, IT00={df_output.loc[0, 'IT00']:.2f}")
print(f"t_4380: DE00={df_output.loc[4379, 'DE00']:.2f}, AT00={df_output.loc[4379, 'AT00']:.2f}, FR00={df_output.loc[4379, 'FR00']:.2f}, IT00={df_output.loc[4379, 'IT00']:.2f}")

# Verify seasonal patterns worked correctly
print(f"\nVerification of seasonal patterns:")
print(f"Original Winter t_1 price: {winter_pattern[0]:.6f}")
print(f"Generated t_1 price: {full_prices[0]:.6f} (should match)")
print(f"Original Spring t_1 price: {spring_pattern[0]:.6f}")
spring_start_idx = seasonal_hours['Winter']
print(f"Generated Spring start price: {full_prices[spring_start_idx]:.6f} (should match)")

# Show seasonal transitions
print(f"\nSeasonal transitions:")
winter_end = seasonal_hours['Winter'] - 1
spring_start = seasonal_hours['Winter']
summer_start = seasonal_hours['Winter'] + seasonal_hours['Spring']
fall_start = seasonal_hours['Winter'] + seasonal_hours['Spring'] + seasonal_hours['Summer']

print(f"Winter end (t_{winter_end+1}): {full_prices[winter_end]:.2f}")
print(f"Spring start (t_{spring_start+1}): {full_prices[spring_start]:.2f}")
print(f"Summer start (t_{summer_start+1}): {full_prices[summer_start]:.2f}")
print(f"Fall start (t_{fall_start+1}): {full_prices[fall_start]:.2f}")

print(f"\nSeasonal price statistics:")
winter_prices = full_prices[:seasonal_hours['Winter']]
spring_prices = full_prices[seasonal_hours['Winter']:seasonal_hours['Winter']+seasonal_hours['Spring']]
summer_prices = full_prices[summer_start:summer_start+seasonal_hours['Summer']]
fall_prices = full_prices[fall_start:]

print(f"Winter: min={winter_prices.min():.2f}, max={winter_prices.max():.2f}, mean={winter_prices.mean():.2f}")
print(f"Spring: min={spring_prices.min():.2f}, max={spring_prices.max():.2f}, mean={spring_prices.mean():.2f}")
print(f"Summer: min={summer_prices.min():.2f}, max={summer_prices.max():.2f}, mean={summer_prices.mean():.2f}")
print(f"Fall: min={fall_prices.min():.2f}, max={fall_prices.max():.2f}, mean={fall_prices.mean():.2f}")

# Create Plotly visualization
print(f"\nCreating price time series plot...")

# Create time step numbers for x-axis
time_step_numbers = np.arange(1, len(full_prices) + 1)

# Calculate hour of the day (0-23) for each time step
hours_of_day = [(t-1) % 24 for t in time_step_numbers]

# Calculate day of year for additional context
days_of_year = [((t-1) // 24) + 1 for t in time_step_numbers]

# Create custom hover text with hour of day
hover_text = []
for i, (ts, price, hour, day, season) in enumerate(zip(time_step_numbers, full_prices, hours_of_day, days_of_year, season_labels)):
    hover_text.append(f"Time Step: {ts}<br>Hour of Day: {hour:02d}:00<br>Day of Year: {day}<br>Season: {season}<br>Price: {price:.2f} EUR/MWh")

# Create the plot
fig = go.Figure()

# Add the main price line with hour information
fig.add_trace(go.Scatter(
    x=time_step_numbers,
    y=full_prices,
    mode='lines',
    name='Price',
    line=dict(color='blue', width=1),
    hovertemplate='%{text}<extra></extra>',
    text=hover_text,
    customdata=hours_of_day
))

# Add seasonal background colors
colors = {'Winter': 'lightblue', 'Spring': 'lightgreen', 'Summer': 'yellow', 'Fall': 'orange'}
current_hour = 0

for season, hours in seasonal_hours.items():
    fig.add_vrect(
        x0=current_hour + 1,
        x1=current_hour + hours,
        fillcolor=colors[season],
        opacity=0.2,
        layer="below",
        line_width=0,
        annotation_text=season,
        annotation_position="top left"
    )
    current_hour += hours

# Add a secondary y-axis showing hour of day pattern
fig.add_trace(go.Scatter(
    x=time_step_numbers,
    y=hours_of_day,
    mode='lines',
    name='Hour of Day',
    line=dict(color='red', width=0.5, dash='dot'),
    yaxis='y2',
    opacity=0.7,
    hovertemplate='Time Step: %{x}<br>Hour: %{y:02.0f}:00<extra></extra>'
))

# Update layout with secondary y-axis
fig.update_layout(
    title='SESETH Neighbor Prices - Seasonal Pattern Approach<br><sub>Blue line: Price (EUR/MWh) | Red dotted line: Hour of Day (0-23)</sub>',
    xaxis_title='Time Step',
    yaxis_title='Price (EUR/MWh)',
    yaxis2=dict(
        title='Hour of Day (0-23)',
        titlefont=dict(color='red'),
        tickfont=dict(color='red'),
        overlaying='y',
        side='right',
        range=[0, 23]
    ),
    width=1400,
    height=700,
    showlegend=True,
    hovermode='x unified'
)

# Save the plot
plot_file = "input/neighbour_prices_for_CH_only_mode/SESETH_price_timeseries.html"
pyo.plot(fig, filename=plot_file, auto_open=False)
print(f"Plot saved to: {plot_file}")

print(f"\n✓ Successfully created seasonal neighbor prices from SESETH data!")