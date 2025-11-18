# Neighbor Prices Generator for CH_only Mode

This folder contains scripts to generate neighbor price time series files specifically for **CH_only mode** runs in the Future Markets model.

## Overview

In CH_only mode, Switzerland (CH) is modeled as an isolated country that can trade with neighboring countries at fixed prices. These scripts generate the required neighbor price input files by processing different data sources.

## Scripts Description

### 1. `create_neighbor_prices_SESETH.py`

- **Purpose**: Generates neighbor prices from SESETH hourly price data with seasonal patterns
- **Input**: `SESETH.csv` (864-hour price pattern)
- **Method**: Seasonal pattern approach - extracts 9-day patterns for each season and repeats them within seasonal periods
  - **Winter pattern**: Hours 1-216 (first 9 days) → repeated for 2184 hours (91 days)
  - **Spring pattern**: Hours 217-432 (next 9 days) → repeated for 2184 hours (91 days)
  - **Summer pattern**: Hours 433-648 (next 9 days) → repeated for 2208 hours (92 days)
  - **Fall pattern**: Hours 649-864 (last 9 days) → repeated for 2184 hours (91 days)
- **Output**: `neighbor_prices_SESETH.csv` and interactive `SESETH_price_timeseries.html` plot
- **Features**:
  - Solar-aware pricing (lower prices in winter/non-sunny hours, higher in summer/sunny hours)
  - Plotly visualization with hour-of-day information and seasonal background colors
  - Dual y-axes showing both prices and hourly patterns

### 2. `create_neighbor_prices_PSI.py`

- **Purpose**: Generates neighbor prices from PSI seasonal/day-type price data
- **Input**: `PSI.csv` (seasonal and day-type structured data with 2050 prices)
- **Method**: Seasonal mapping - distributes seasons (Winter/Spring/Summer/Fall) with weekly day-type patterns (Working Day/Saturday/Sunday)
- **Output**: `neighbor_prices_PSI.csv` and interactive `PSI_price_timeseries.html` plot
- **Features**:
  - Triple y-axes visualization showing prices, hour-of-day, and day-type patterns
  - Seasonal background colors and comprehensive hover information

### 3. `create_neighbour_prices_FEM.py`

- **Purpose**: Generates neighbor prices from FEM model output (dual prices)
- **Input**: `output/{SCENARIO_NAME}/energy_balance_dual.csv` (FEM model results)
- **Method**: Pivots long-format dual prices to wide format, maps to neighbor countries
- **Output**: `neighbor_prices_FEM{SCENARIO_NAME}.csv` and interactive `FEM_{SCENARIO_NAME}_price_timeseries.html` plot
- **Features**:
  - Multi-country price visualization with individual country lines
  - Cross-country price comparison and analysis

## Output Format

All scripts generate CSV files with the following structure:

```
time_step,DE00,AT00,FR00,IT00
t_1,price1,price1,price1,price1
t_2,price2,price2,price2,price2
...
t_8760,price8760,price8760,price8760,price8760
```

**Columns:**

- `time_step`: Time identifier (t_1 to t_8760)
- `DE00`: Germany neighbor prices (EUR/MWh)
- `AT00`: Austria neighbor prices (EUR/MWh)
- `FR00`: France neighbor prices (EUR/MWh)
- `IT00`: Italy neighbor prices (EUR/MWh)

**Note**: SESETH and PSI use identical prices for all neighbors, while FEM can provide country-specific pricing based on model output.

## Interactive Visualizations

All scripts generate interactive HTML plots for analysis and validation:

- **SESETH**: `SESETH_price_timeseries.html` - Shows seasonal patterns with hour-of-day information
- **PSI**: `PSI_price_timeseries.html` - Displays day-type patterns with triple y-axes
- **FEM**: `FEM_{SCENARIO_NAME}_price_timeseries.html` - Multi-country price comparison

These plots include seasonal background colors, detailed hover information, and time series analysis capabilities.

## Input Requirements

### For SESETH script:

- File: `SESETH.csv`
- Required columns: `time_step`, `price`
- Expected: 864 hourly data points

### For PSI script:

- File: `PSI.csv`
- Required columns: `Season`, `Type of Day`, `Hour`, `2030`, `2040`, `2050`
- Expected: Seasonal/hourly price data with day-type classifications

### For FEM script:

- File: `output/{SCENARIO_NAME}/energy_balance_dual.csv`
- Required columns: `T`, `Node`, `Scenarios`, `value`
- Expected: Long-format dual prices from FEM model output
- Required nodes: DE00, AT00, FR00, IT00 (or similar country codes)

## Usage

### SESETH and PSI scripts:

Simply run the Python files directly:

```bash
python create_neighbor_prices_SESETH.py
python create_neighbor_prices_PSI.py
```

### FEM script:

Run directly and enter scenario name when prompted:

```bash
python create_neighbour_prices_FEM.py
```

The script will ask: `Enter Scenarios name:` - type your scenario name (e.g., "base")

## Integration with CH_only Mode

The generated neighbor price files should be placed in:

```
input/neighbour_prices_for_CH_only_mode/
```

The CH_only mode will read these files to determine neighbor trading prices for the optimization model. The model uses these prices in the trade cost calculation:

```
Trade Cost = Σ(import_flow * neighbor_price + export_flow * neighbor_price)
```

## File Locations

**Input data:**

- `SESETH.csv` and `PSI.csv` should be in this folder
- FEM output should be in `output/{SCENARIO_NAME}/energy_balance_dual.csv`

**Output files:**

- All generated neighbor price files are saved to `input/neighbour_prices_for_CH_only_mode/`

## Notes

- All times series cover a full year (8760 hours)
- Price units are in EUR/MWh
- Scripts include data validation and detailed logging
- Missing data is handled with appropriate warnings and fallback values
- Only used for CH_only mode runs - not applicable for multi-country modeling
