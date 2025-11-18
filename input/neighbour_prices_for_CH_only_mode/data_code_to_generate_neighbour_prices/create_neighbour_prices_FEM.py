import pandas as pd
import numpy as np
import os
import sys
import plotly.graph_objects as go
import plotly.offline as pyo

# ========================================
# Scenarios CONFIGURATION
# ========================================
# Enter your Scenarios name here:
Scenarios_name = "base_zeroPV"

def create_neighbor_prices_from_fem_output(Scenarios_name):
    """
    Create neighbor prices from FEM model output
    
    Args:
        Scenarios_name (str): Name of the Scenarios folder
    """
    
    # Define paths
    input_file = f"output/{Scenarios_name}/energy_balance_dual.csv"
    output_dir = "input/neighbour_prices_for_CH_only_mode"
    output_file = f"{output_dir}/neighbor_prices_FEM{Scenarios_name}.csv"
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file {input_file} not found!")
        return False
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Reading FEM output from: {input_file}")
    
    # Read the CSV file
    try:
        df = pd.read_csv(input_file)
        print(f"Input data shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        
        # Show sample data
        print("\nSample data:")
        print(df.head())
        
        # Check required columns
        required_cols = ['T', 'Node', 'Scenarios', 'value']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"Error: Missing required columns: {missing_cols}")
            return False
        
        print(f"\nUnique Scenarioss: {df['Scenarios'].unique()}")
        print(f"Unique nodes: {sorted(df['Node'].unique())}")
        print(f"Time steps range: {df['T'].min()} to {df['T'].max()}")
        print(f"Total time steps: {df['T'].nunique()}")
        
        # Use first Scenarios instance
        first_Scenarios = df['Scenarios'].iloc[0]
        df_filtered = df[df['Scenarios'] == first_Scenarios].copy()
        print(f"\nFiltered to Scenarios '{first_Scenarios}', shape: {df_filtered.shape}")
        
        # Check if we have the required neighbor countries
        required_countries = ['DE00', 'AT00', 'FR00', 'IT00']
        available_countries = [country for country in required_countries if country in df_filtered['Node'].unique()]
        missing_countries = [country for country in required_countries if country not in df_filtered['Node'].unique()]
        
        print(f"\nAvailable neighbor countries: {available_countries}")
        if missing_countries:
            print(f"Warning: Missing neighbor countries: {missing_countries}")
            print("Available nodes that might be alternatives:")
            for node in sorted(df_filtered['Node'].unique()):
                if any(country[:2] in node for country in missing_countries):
                    print(f"  - {node}")
        
        # Pivot the data from long to wide format
        print("\nPivoting data to wide format...")
        df_pivot = df_filtered.pivot_table(
            index='T', 
            columns='Node', 
            values='value', 
            aggfunc='first'  # In case of duplicates, take first value
        ).reset_index()
        
        print(f"Pivoted data shape: {df_pivot.shape}")
        print(f"Pivoted columns: {list(df_pivot.columns)}")
        
        # Rename time column to match expected format
        df_pivot = df_pivot.rename(columns={'T': 'time_step'})
        
        # Create output dataframe with required structure
        output_df = pd.DataFrame()
        output_df['time_step'] = df_pivot['time_step']
        
        # Map neighbor countries
        for country in required_countries:
            if country in df_pivot.columns:
                output_df[country] = df_pivot[country]
                print(f"✓ Mapped {country}: price range {df_pivot[country].min():.2f} - {df_pivot[country].max():.2f}")
            else:
                # Try to find alternative mapping
                alternative = None
                for col in df_pivot.columns:
                    if country[:2] in col:  # Match first 2 letters (DE, AT, FR, IT)
                        alternative = col
                        break
                
                if alternative:
                    output_df[country] = df_pivot[alternative]
                    print(f"✓ Mapped {country} -> {alternative}: price range {df_pivot[alternative].min():.2f} - {df_pivot[alternative].max():.2f}")
                else:
                    print(f"✗ Could not find data for {country}, setting to NaN")
                    output_df[country] = np.nan
        
        # Check for missing values
        missing_count = output_df.isnull().sum().sum()
        if missing_count > 0:
            print(f"\nWarning: {missing_count} missing values in output data")
            print("Missing values by column:")
            for col in output_df.columns:
                if output_df[col].isnull().sum() > 0:
                    print(f"  {col}: {output_df[col].isnull().sum()} missing")
        
        # Check for negative price values and replace with 0
        negative_count = 0
        all_negative_values = []
        
        for col in ['DE00', 'AT00', 'FR00', 'IT00']:
            if col in output_df.columns:
                negative_values = output_df[col] < 0
                if negative_values.any():
                    negative_count += negative_values.sum()
                    min_negative = output_df[col][negative_values].min()
                    all_negative_values.extend(output_df[col][negative_values].values)
                    print(f"\nWarning: {col} has {negative_values.sum()} negative price values (min: {min_negative:.2f} EUR/MWh)")
                    
                    # Replace negative values with 0
                    output_df.loc[negative_values, col] = 0
                    print(f"  → Replaced {negative_values.sum()} negative values in {col} with 0")
        
        if negative_count > 0:
            overall_min_negative = min(all_negative_values)
            print(f"\nTotal negative price values found: {negative_count}")
            print(f"Overall minimum negative value: {overall_min_negative:.2f} EUR/MWh")
            print("All negative values have been replaced with 0 EUR/MWh")
        
        # Verify we have 8760 time steps
        if len(output_df) != 8760:
            print(f"Warning: Expected 8760 time steps, got {len(output_df)}")
        
        # Sort by time_step to ensure correct chronological order
        # Extract numeric part from time_step (e.g., 't_1' -> 1) for proper sorting
        if output_df['time_step'].dtype == object and output_df['time_step'].iloc[0].startswith('t_'):
            output_df['_sort_key'] = output_df['time_step'].str.extract(r't_(\d+)')[0].astype(int)
            output_df = output_df.sort_values('_sort_key').drop('_sort_key', axis=1).reset_index(drop=True)
            print(f"Sorted output by time_step (t_1, t_2, ..., t_{len(output_df)})")
        else:
            # If time_step is already numeric, sort directly
            output_df = output_df.sort_values('time_step').reset_index(drop=True)
            print(f"Sorted output by time_step")
        
        # Save the output file
        output_df.to_csv(output_file, index=False)
        print(f"\nFile saved to: {output_file}")
        
        # Show summary statistics
        print(f"\nOutput data shape: {output_df.shape}")
        print(f"Columns: {list(output_df.columns)}")
        
        print("\nSample output:")
        print(output_df.head(10))
        print("...")
        print(output_df.tail(10))
        
        print("\nPrice statistics:")
        for col in ['DE00', 'AT00', 'FR00', 'IT00']:
            if col in output_df.columns and not output_df[col].isnull().all():
                prices = output_df[col].dropna()
                print(f"{col}: min={prices.min():.2f}, max={prices.max():.2f}, mean={prices.mean():.2f}, std={prices.std():.2f}")
        
        # Create Plotly visualization
        print(f"\nCreating price time series plot...")
        
        # Extract time step numbers for x-axis
        time_step_numbers = np.arange(1, len(output_df) + 1)
        
        # Calculate hour of the day (0-23) for each time step
        hours_of_day = [(t-1) % 24 for t in time_step_numbers]
        
        # Calculate day of year for additional context
        days_of_year = [((t-1) // 24) + 1 for t in time_step_numbers]
        
        # Define seasonal information (same structure as PSI)
        seasonal_hours = {'Winter': 2184, 'Spring': 2184, 'Summer': 2208, 'Fall': 2184}
        season_labels = []
        current_hour = 0
        for season, hours in seasonal_hours.items():
            season_labels.extend([season] * hours)
            current_hour += hours
        
        # Create the plot
        fig = go.Figure()
        
        # Country colors
        country_colors = {
            'DE00': 'blue',
            'AT00': 'green', 
            'FR00': 'red',
            'IT00': 'orange'
        }
        
        # Add price lines for each country
        for country in ['DE00', 'AT00', 'FR00', 'IT00']:
            if country in output_df.columns and not output_df[country].isnull().all():
                prices = output_df[country].values
                
                # Create custom hover text
                hover_text = []
                for i, (ts, price, hour, day, season) in enumerate(zip(time_step_numbers, prices, hours_of_day, days_of_year, season_labels)):
                    if not np.isnan(price):
                        hover_text.append(f"Time Step: {ts}<br>Hour of Day: {hour:02d}:00<br>Day of Year: {day}<br>Season: {season}<br>Country: {country}<br>Price: {price:.2f} EUR/MWh")
                    else:
                        hover_text.append(f"Time Step: {ts}<br>Hour of Day: {hour:02d}:00<br>Day of Year: {day}<br>Season: {season}<br>Country: {country}<br>Price: No data")
                
                fig.add_trace(go.Scatter(
                    x=time_step_numbers,
                    y=prices,
                    mode='lines',
                    name=f'{country} Price',
                    line=dict(color=country_colors[country], width=1.5),
                    hovertemplate='%{text}<extra></extra>',
                    text=hover_text
                ))
        
        # Add seasonal background colors
        colors = {'Winter': 'lightblue', 'Spring': 'lightgreen', 'Summer': 'yellow', 'Fall': 'orange'}
        current_hour = 0
        
        for season, hours in seasonal_hours.items():
            fig.add_vrect(
                x0=current_hour + 1,
                x1=current_hour + hours,
                fillcolor=colors[season],
                opacity=0.1,
                layer="below",
                line_width=0,
                annotation_text=season,
                annotation_position="top left"
            )
            current_hour += hours
        
        # Add hour of day pattern as secondary y-axis
        fig.add_trace(go.Scatter(
            x=time_step_numbers,
            y=hours_of_day,
            mode='lines',
            name='Hour of Day',
            line=dict(color='gray', width=0.5, dash='dot'),
            yaxis='y2',
            opacity=0.5,
            hovertemplate='Time Step: %{x}<br>Hour: %{y:02.0f}:00<extra></extra>'
        ))
        
        # Calculate price range for y-axis
        all_prices = []
        for country in ['DE00', 'AT00', 'FR00', 'IT00']:
            if country in output_df.columns and not output_df[country].isnull().all():
                all_prices.extend(output_df[country].dropna().values)
        
        if all_prices:
            price_min = np.min(all_prices)
            price_max = np.max(all_prices)
            price_range = price_max - price_min
            y_min = max(0, price_min - price_range * 0.1)
            y_max = price_max + price_range * 0.1
        else:
            y_min, y_max = 0, 100
        
        # Update layout with multiple y-axes
        fig.update_layout(
            title=f'FEM Neighbor Prices - Scenario: {Scenarios_name}<br><sub>Solid lines: Country prices (EUR/MWh) | Gray dotted: Hour of Day (0-23)</sub>',
            xaxis_title='Time Step',
            yaxis_title='Price (EUR/MWh)',
            yaxis=dict(range=[y_min, y_max]),
            yaxis2=dict(
                title='Hour of Day (0-23)',
                titlefont=dict(color='gray'),
                tickfont=dict(color='gray'),
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
        plot_file = f"input/neighbour_prices_for_CH_only_mode/FEM_{Scenarios_name}_price_timeseries.html"
        pyo.plot(fig, filename=plot_file, auto_open=False)
        print(f"Plot saved to: {plot_file}")
        
        # Print summary of country price differences
        print(f"\nCountry price comparison:")
        country_data = {}
        for country in ['DE00', 'AT00', 'FR00', 'IT00']:
            if country in output_df.columns and not output_df[country].isnull().all():
                prices = output_df[country].dropna()
                country_data[country] = {
                    'mean': prices.mean(),
                    'min': prices.min(),
                    'max': prices.max(),
                    'std': prices.std()
                }
        
        if len(country_data) > 1:
            print("Price differences between countries:")
            countries = list(country_data.keys())
            for i, country1 in enumerate(countries):
                for country2 in countries[i+1:]:
                    mean_diff = abs(country_data[country1]['mean'] - country_data[country2]['mean'])
                    print(f"  {country1} vs {country2}: Avg difference = {mean_diff:.2f} EUR/MWh")
        
        print(f"\n✓ Successfully created neighbor prices from FEM output!")
        return True
        
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        return False

if __name__ == "__main__":
    print(f"=== FEM Neighbor Prices Generator ===")
    print(f"Processing Scenarios: {Scenarios_name}")
    print()
    
    success = create_neighbor_prices_from_fem_output(Scenarios_name)
    
    if not success:
        print("\nFailed to create neighbor prices!")
        sys.exit(1)
