import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.offline as pyo

# Read the input data (PSI_2050.csv with 4 country columns)
input_file = "input/neighbour_prices_for_CH_only_mode/data_code_to_generate_neighbour_prices/PSI_2050.csv"
df_input = pd.read_csv(input_file)

print("Input data (raw):")
print(df_input.head(5))
print(f"Input data shape: {df_input.shape}")
print(f"Columns: {list(df_input.columns)}")

# Skip the first data row which contains metadata ("# of occurences ...")
df_input = df_input.iloc[1:].reset_index(drop=True)
print("\nAfter removing metadata row:")
print(df_input.head(5))

# Expected clean column names
expected_cols = ['Season', 'Type of Day', 'Hour', 'Austria', 'Germany', 'France', 'Italy']
missing = [c for c in expected_cols if c not in df_input.columns]
if missing:
    raise ValueError(f"Missing expected columns: {missing}. Found: {list(df_input.columns)}")

# Define mapping from countries to output codes
country_map = {
    'AT00': 'Austria',
    'DE00': 'Germany',
    'FR00': 'France',
    'IT00': 'Italy'
}

print("\nCountry to column mapping:")
for code, col in country_map.items():
    print(f"  {code} -> {col}")

# Season distribution (8760 hours)
season_hours = {
    'Winter': 2184,  # 91 days × 24 hours
    'Spring': 2184,  # 91 days × 24 hours
    'Summer': 2208,  # 92 days × 24 hours
    'Autumn': 2184   # 91 days × 24 hours
}

print("\nSeason distribution:")
for season, hours in season_hours.items():
    print(f"{season}: {hours} hours ({hours/24:.1f} days)")
print(f"Total: {sum(season_hours.values())} hours")

# Weekly day-type pattern
day_types = ['Working Day', 'Working Day', 'Working Day', 'Working Day', 'Working Day', 'Saturday', 'Sunday']
print(f"\nWeekly day type pattern: {day_types}")

# Build price mappings for each country keyed by (season, daytype, hour)
price_mappings = {code: {} for code in country_map.keys()}
for _, row in df_input.iterrows():
    season = row['Season']
    daytype = row['Type of Day']
    # Skip rows where hour isn't numeric
    try:
        hour = int(row['Hour'])
    except (ValueError, TypeError):
        continue
    for code, col in country_map.items():
        try:
            price = float(row[col])
        except (ValueError, TypeError, KeyError):
            continue
        price_mappings[code][(season, daytype, hour)] = price

print("\nPrice mappings summary:")
for code in price_mappings:
    print(f"  {code}: {len(price_mappings[code])} entries")

# Generate 8760-hour time series with prices for each country
time_data = {code: [] for code in country_map.keys()}
current_hour = 1
day_counter = 0

for season in ['Winter', 'Spring', 'Summer', 'Autumn']:
    season_hour_count = season_hours[season]
    for _ in range(season_hour_count):
        day_type = day_types[day_counter % 7]
        hour_of_day = (current_hour - 1) % 24 + 1
        key = (season, day_type, hour_of_day)
        for code in country_map.keys():
            if key not in price_mappings[code]:
                # Fallbacks for naming variations
                alt_mappings = {
                    'Working Day': ['Working Day', 'Weekday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
                    'Saturday': ['Saturday', 'Weekend'],
                    'Sunday': ['Sunday', 'Weekend']
                }
                found = None
                for alt in alt_mappings.get(day_type, [day_type]):
                    alt_key = (season, alt, hour_of_day)
                    if alt_key in price_mappings[code]:
                        found = price_mappings[code][alt_key]
                        break
                if found is None:
                    # As a last resort, use the mean of available values
                    vals = list(price_mappings[code].values())
                    found = float(np.mean(vals)) if vals else np.nan
                price = found
            else:
                price = price_mappings[code][key]
            time_data[code].append({
                'time_step': f't_{current_hour}',
                'season': season,
                'day_type': day_type,
                'hour_in_day': hour_of_day,
                'price': price
            })
        current_hour += 1
        if (current_hour - 1) % 24 == 0:
            day_counter += 1

# Assemble output dataframe
first_code = next(iter(country_map.keys()))
df_time = pd.DataFrame(time_data[first_code])
output = {'time_step': df_time['time_step'].tolist()}
for code in country_map.keys():
    output[code] = pd.DataFrame(time_data[code])['price'].tolist()
df_output = pd.DataFrame(output)

print(f"\nOutput data shape: {df_output.shape}")
print(f"Columns: {list(df_output.columns)}")

# Save CSV
output_file = "input/neighbour_prices_for_CH_only_mode/neighbor_prices_PSI_2050.csv"
df_output.to_csv(output_file, index=False)
print(f"Saved CSV to: {output_file}")

# Quick stats
print("\nPrice statistics by country:")
for code in country_map.keys():
    series = df_output[code]
    print(f"  {code}: min={series.min():.1f}, max={series.max():.1f}, mean={series.mean():.1f}")

# Plotly visualization with all countries
print("\nCreating price time series plot...")
fig = go.Figure()
time_step_numbers = np.arange(1, len(df_time) + 1)
hours_of_day = [(t-1) % 24 for t in time_step_numbers]
seasons_for_plot = df_time['season'].values
day_types_for_plot = df_time['day_type'].values

colors = {'AT00': 'blue', 'DE00': 'red', 'FR00': 'green', 'IT00': 'orange'}
for code in country_map.keys():
    values = df_output[code].values
    hover_text = []
    for ts, price, hour, season, day_type in zip(time_step_numbers, values, hours_of_day, seasons_for_plot, day_types_for_plot):
        hover_text.append(f"{code}<br>t={ts} | {hour:02d}:00<br>{season} - {day_type}<br>Price: {price:.2f}")
    fig.add_trace(go.Scatter(
        x=time_step_numbers,
        y=values,
        mode='lines',
        name=code,
        line=dict(color=colors.get(code, 'gray'), width=1.3),
        hovertemplate='%{text}<extra></extra>',
        text=hover_text
    ))

# Shade seasons
seasonal_hours_plot = {'Winter': 2184, 'Spring': 2184, 'Summer': 2208, 'Autumn': 2184}
shade_colors = {'Winter': 'lightblue', 'Spring': 'lightgreen', 'Summer': 'yellow', 'Autumn': 'lightyellow'}
cursor = 0
for season, hours in seasonal_hours_plot.items():
    fig.add_vrect(
        x0=cursor + 1,
        x1=cursor + hours,
        fillcolor=shade_colors[season],
        opacity=0.15,
        layer="below",
        line_width=0,
        annotation_text=season,
        annotation_position="top left"
    )
    cursor += hours

fig.update_layout(
    title='PSI 2050 Neighbor Prices (AT/DE/FR/IT)',
    xaxis_title='Hour of Year',
    yaxis_title='Price (EUR/MWh)',
    width=1600,
    height=700,
    plot_bgcolor='white',
    hovermode='x unified',
    showlegend=True
)

plot_file = "input/neighbour_prices_for_CH_only_mode/PSI_2050_price_timeseries.html"
pyo.plot(fig, filename=plot_file, auto_open=False)
print(f"Plot saved to: {plot_file}")

print("\n✓ Successfully created country-specific 2050 neighbor prices from PSI data.")