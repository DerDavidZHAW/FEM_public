import pandas as pd
from copy import deepcopy
import plotly.graph_objects as go




def hour_to_timestamp(t_list, year=2050):
    """
    Maps conventional time indices (e.g., t_1, t_2, etc.) to timestamps (e.g., 2050-01-01 00:00:00, 2050-01-01 01:00:00, etc.).
    
    t_list: list of time indices (e.g., t_1, t_2, etc.)
    year: year of the time indices (default is 2050)
    return: dictionary mapping time indices to timestamps (e.g., t_1 -> 2050-01-01 00:00:00, t_2 -> 2050-01-01 01:00:00, etc.)

    """
    t_timestamp_Map = {}
    start_of_year_minus1 = pd.Timestamp(year=year-1, month=1, day=1, hour=0)
    start_of_year = pd.Timestamp(year=year, month=1, day=1, hour=0)

    for t in t_list:
        t_integer = int(t[2:])
        if t_integer >= 6553:
            t_timestamp_Map[t] = start_of_year_minus1 + pd.Timedelta(hours=t_integer - 1)
        else:
            t_timestamp_Map[t] = start_of_year + pd.Timedelta(hours=t_integer- 1)
        
    return t_timestamp_Map

def aggregate_figure_by_time(
    original_fig: go.Figure,
    mode_agg: str = "hour_in_day",   # one of: ["hour_in_day", "hour_in_week", "monthly", "weekly"]
    agg_func: str = "sum",       # e.g. "sum", "mean", "max", etc.
    weekly_anchor: str = "W-SUN", # used only if mode=="weekly": can be "W-SUN", "W-MON", etc.
    scenario_name: str = "",      # e.g. "Scenario 1", "Scenario 2", etc.
) -> go.Figure:
    """
    Based on a original_fig (including hourly traces), returns a new go.Figure 
    where each trace in original_fig is aggregated 
    according to 'mode_agg' using the specified 'agg_func'.
    
    This function turns hourly data into daily, weekly, monthly, or yearly data.
    To be located in the main code
    after all traces are created but 
    before the plot detaled info is introduced.
    
    Modes:
      - "hour_in_day"  => Group by x.dt.hour (0..23)
      - "hour_in_week" => Group by x.dt.dayofweek*24 + x.dt.hour (0..167)
      - "monthly"      => Group by x.dt.month (1..12) 
      - "weekly"       => Group by weekly period (7 days = 168 hours),
                          using Pandas 'to_period(weekly_anchor)'

    Parameters
    ----------
    original_fig : go.Figure
        The Plotly figure whose traces will be aggregated.
    mode_agg : str
        One of: ["hour_in_day", "hour_in_week", "monthly", "weekly"].
    agg_func : str
        Pandas aggregation method: 'sum', 'mean', 'max', 'min', etc.
    weekly_anchor : str
        Only used if mode_agg=="weekly", e.g. "W-SUN" or "W-MON".
    scenario_name : str
        A descriptive name for the scenario, e.g. "Scenario 1", "Scenario 2", etc.

    Returns
    -------
    go.Figure
        A new figure, preserving the original layout and trace styles, 
        but with x,y replaced by aggregated values.

    Example usage:
    --------------------
    new_fig_monthly = aggregate_figure_by_time(
        original_fig=self.fig_dispatch, 
        mode_agg="monthly",      
        agg_func="sum"
    )
    new_fig_monthly.show()
    """
    

    # A small dictionary to describe each mode_agg in the figure title
    mode_titles = {
        "hour_in_day":  "Data Aggregated by Hour of Day (0..23)",
        "hour_in_week": "Data Aggregated by Hour of Week (0..167)",
        "monthly":      "Data Aggregated by Month (1..12)",
        "weekly":       f"Data Aggregated by Weeks (168 hours, anchor={weekly_anchor})",
    }

    if mode_agg not in mode_titles:
        raise ValueError(
            f"Invalid mode='{mode_agg}'. Must be one of "
            "['hour_in_day', 'hour_in_week', 'monthly', 'weekly']."
        )
    
    # Create a new figure (so we don't mutate the original)
    new_fig = go.Figure()
    
    # Copy the original layout (titles, stacked mode_agg, etc.)
    new_fig.update_layout(deepcopy(original_fig.layout))
    
    # Build a title that includes the aggregation function
    agg_func_title = agg_func.capitalize()
    new_fig.update_layout(
        title_text=f"Dispatch {scenario_name}<br>{mode_titles[mode_agg]} — {agg_func_title}"
    )
    
    # Loop through each trace in the original figure
    for trace in original_fig.data:
        # Skip if the trace has no x or y
        if not hasattr(trace, 'x') or not hasattr(trace, 'y'):
            continue
        
        # Convert x->datetime, y->numeric
        x_vals = pd.to_datetime(trace.x, errors='coerce')
        y_vals = pd.to_numeric(trace.y, errors='coerce')
        
        # Build a temporary DataFrame
        df_temp = pd.DataFrame({'x': x_vals, 'y': y_vals}).dropna(subset=['x'])
        
        # Depending on 'mode', compute the grouping column
        if mode_agg == "hour_in_day":
            # 0..23
            df_temp['aggregator'] = df_temp['x'].dt.hour
        
        elif mode_agg == "hour_in_week":
            # Monday=0..Sunday=6 => 0..167
            df_temp['aggregator'] = df_temp['x'].dt.dayofweek * 24 + df_temp['x'].dt.hour
        
        elif mode_agg == "monthly":
            # 1..12
            df_temp['aggregator'] = df_temp['x'].dt.month
        
        elif mode_agg == "weekly":
            # E.g. "W-SUN", "W-MON"
            df_temp['aggregator'] = df_temp['x'].dt.to_period(weekly_anchor)
        
        # Group & aggregate
        grouped = getattr(df_temp.groupby('aggregator')['y'], agg_func)().reset_index()
        
        # If weekly, convert the Period to a datetime (start of each period) for x-axis
        if mode_agg == "weekly":
            grouped['aggregator'] = grouped['aggregator'].apply(lambda p: p.start_time)
        
        # If monthly, reorder so that the earliest month in the data is first
        if mode_agg == "monthly":
            if df_temp.empty: # backward compatibility with older versions of the model
                # If df_temp is empty, we can't find the earliest month, so we skip this step
                grouped['aggregator'] = pd.Series(name="aggregator")
            else:
            # 1) Find the earliest month present in the dataset
                earliest_month = df_temp['aggregator'][0]  # e.g. 10
                # 2) Create a custom month order, e.g. 10..12, 1..9
                month_order = list(range(earliest_month, 13)) + list(range(1, earliest_month))
                
                # 3) Convert aggregator to categorical with that custom order
                cat_type = pd.CategoricalDtype(categories=month_order, ordered=True)
                grouped['aggregator'] = grouped['aggregator'].astype(cat_type)
                
                # 4) Sort the grouped rows so they appear in that order
                grouped.sort_values('aggregator', inplace=True)
                
                # (Optionally) convert aggregator to string, so it shows up nicely on the x-axis
                grouped['aggregator'] = grouped['aggregator'].astype(str)
        
        # Create a deep copy of the original trace, preserving style and type
        new_trace = deepcopy(trace)
        
        # Replace X and Y with the aggregated data
        new_trace.x = grouped['aggregator']
        new_trace.y = grouped['y']
        
        # Add the new trace to the new figure
        new_fig.add_trace(new_trace)
    
    return new_fig

def merge_dispatch(dispatch_fig: go.Figure, color_mapping: dict, trace_dataframes: pd.DataFrame) -> go.Figure:
    """
    Merges several technologies to one trace in the dispatch figure, to simplyfy the visualization.
    Input:
    - dispatch_fig: the original dispatch figure (go.Figure)
    - color_mapping: a dictionary mapping technology names to colors
    Output:
    - new_fig: a new figure (go.Figure) with merged technologies
    """
    # Mapping of technologies to be merged 
    # the keys are the new names, and the values are lists of old names
    # e.g. {"PSP demand": ["psp_close demand", "psp_open demand"]}
    tech_merge_mapping = { 
        "PSP demand": [ "psp_close demand", "psp_open demand"],
        # "PSP gen": ["psp_close gen",], # "psp_open gen", ],
        # "PSP gen": ["psp_open gen",], # "psp_open gen", ],

        "Other gen": ["other gen", "biomass gen", "CCGTCCS gen"],
        "Battery gen": ["battery gen", "v2g gen"],
        "RES gen": ["Infeed preexisting PV", "Infeed preexisting Wind", "Infeed preexisting RoR", "windon gen", "pvrf gen", ],
        "Heating demand": ["heat_pump demand", "resistive_heater demand", "heat_pump_households demand"],
        "EV flexible demand": ["ev_flex demand", "v2g demand"],
        "Electrolyzer demand": ["hydrogen demand", "electrolyzer demand"],
    }


    # Create a new figure (so we don't mutate the original)
    new_fig = go.Figure()

    # Copy the original layout (titles, stacked mode_agg, etc.)
    new_fig.update_layout(deepcopy(dispatch_fig.layout))

    # keep track of the traces that are already added to the new figure
    traces_added = set()
    
    # Loop through each trace in the original figure
    for trace in dispatch_fig.data:
        
        # if trace is already added to the new figure, skip it
        if trace.name in traces_added:
            continue
        
        else:
            # if the trace name is not in values of tech_merge_mapping, copy it to the new figure as is
            if trace.name not in [old_tech for old_techs in tech_merge_mapping.values() for old_tech in old_techs]:
                new_trace = deepcopy(trace)
                new_fig.add_trace(new_trace)
                # color_to_use is color_mapping[trace.name] if it exists, otherwise use the default color
                trace.marker.color = color_mapping.get(trace.name, trace.marker.color)  # apply the color to the new trace
                
                # add the trace name to the set of traces added
                traces_added.add(trace.name)

    # print("Traces added to new figure:", traces_added)        
            # if the trace name is in values of tech_merge_mapping, create a new trace that is equal to 
            # the sum of the old traces as values of tech_merge_mapping[trace.name]
            # the name of the new trace is the key of tech_merge_mapping
            # the color of the new trace is the color of the first old trace in tech_merge_mapping[trace.name][0]
            else:
                # get the name of the new trace
                new_trace_name = [new_tech for new_tech, old_techs in tech_merge_mapping.items() if trace.name in old_techs][0]
                # get the color of the new trace
                color_to_use = color_mapping.get(new_trace_name, color_mapping[tech_merge_mapping[new_trace_name][0]])
                
                # technologies to sum up are tech_merge_mapping[new_trace_name]
                techs_to_sum = tech_merge_mapping[new_trace_name]

                # techs that exist in the dataframe
                existing_techs = [tech for tech in techs_to_sum if tech in trace_dataframes.index]

                # summed up dataframe
                techs_sum_df = - trace_dataframes.loc[existing_techs,:].sum(axis=0)

                # plot techs_sum_df as a new trace in the new figure
                # stackgroup is equal to the stackgroup of techs_to_sum[0] in the original figure
                stackgroup = trace.stackgroup if hasattr(trace, 'stackgroup') else None

                new_fig.add_trace(
                    go.Scatter(
                        x=techs_sum_df.index,
                        y=techs_sum_df.values if stackgroup =="two" else -techs_sum_df.values, #type: ignore
                        name=new_trace_name,
                        line=dict(color=color_to_use),
                        stackgroup=stackgroup,  # This will stack the traces
                        mode="lines",
                    )
                )
                # add techs_to_sum to the set of traces added
                traces_added.update(techs_to_sum)
           
    # new_fig.show()
    return new_fig

def align_yaxes_zero(fig, yaxis_name="yaxis", yaxis2_name="yaxis2"):
    """
    Aligns the zero of the left and right y-axes in a Plotly figure,
    while allowing their min/max to be set independently as much as possible.
    """
    y1_values = []
    y2_values = []

    for trace in fig.data:
        axis = getattr(trace, "yaxis", "y")
        if axis == "y2":
            y2_values.extend(trace.y)
        else:
            y1_values.extend(trace.y)

    def get_axis_range(y_values):
        if not y_values:
            return [-1, 1]
        y_min = min(y_values)
        y_max = max(y_values)
        # Ensure zero is included
        return [min(y_min, 0), max(y_max, 0)]

    y1_range = get_axis_range(y1_values)
    y2_range = get_axis_range(y2_values)

    # Calculate the zero position ratio for y1 (reference axis)
    neg1 = abs(y1_range[0])
    pos1 = y1_range[1]
    total1 = neg1 + pos1 if (neg1 + pos1) != 0 else 1
    zero_ratio1 = neg1 / total1

    # Now adjust y2 so its zero is at the same relative position
    neg2 = abs(y2_range[0])
    pos2 = y2_range[1]
    total2 = neg2 + pos2 if (neg2 + pos2) != 0 else 1

    # Compute the span needed for y2 to align zero with y1
    y2_span = y2_range[1] - y2_range[0]
    y2_zero_pixel = abs(y2_range[0]) / (abs(y2_range[0]) + y2_range[1]) if (abs(y2_range[0]) + y2_range[1]) != 0 else 0.5

    # The desired zero pixel position is zero_ratio1
    # Adjust y2_range so that zero is at zero_ratio1
    # Keep the span as large as needed to include all data
    min_y2 = y2_range[0]
    max_y2 = y2_range[1]

    # Calculate the span needed so that zero is at the same relative position
    data_span = max_y2 - min_y2
    # The new span must satisfy: abs(new_min) / (abs(new_min) + new_max) = zero_ratio1
    # and new_min <= min_y2, new_max >= max_y2 (to not cut data)
    # Solve for new_min and new_max:
    # Let S = new_max - new_min
    # Then: abs(new_min) = zero_ratio1 * S
    #       new_max = (1 - zero_ratio1) * S
    #       new_min = -zero_ratio1 * S

    # Find the minimal S such that new_min <= min_y2 and new_max >= max_y2
    S_min = max(
        abs(min_y2) / zero_ratio1 if zero_ratio1 > 0 else 0,
        max_y2 / (1 - zero_ratio1) if (1 - zero_ratio1) > 0 else 0,
        data_span
    )
    new_min = -zero_ratio1 * S_min
    new_max = (1 - zero_ratio1) * S_min

    # Ensure zero is visible and all data is visible
    y2_range_aligned = [min(new_min, min_y2, 0), max(new_max, max_y2, 0)]

    fig.update_layout(
        **{
            yaxis_name: dict(range=y1_range),
            yaxis2_name: dict(range=y2_range_aligned)
        }
    )

dispatch_color_mapping = {
    # Heating-related demand
    'heat_pump demand': '#e6550d',           # Warm reddish-orange (heating)
    'heat_pump_households demand': '#fd8d3c',
    'resistive_heater demand': '#fdae6b',

    # Hydrogen
    'hydrogen demand': '#238b45',            # Dark green
    'hydrogen gen':    '#74c476',            # Light green

    # Nuclear - now gray-purple tones (not green)
    'nuclear demand': '#6a51a3',             # Dark gray-purple
    'nuclear gen':    '#bcbddc',             # Light gray-lavender

    # PSP - hydro storage (shades of blue)
    'psp_close demand': '#08306b',           # Deep navy
    'psp_close gen':    '#4292c6',           # Light blue
    'psp_open demand': '#08519c',            # Medium-dark blue
    'psp_open gen':    '#a6cee3',

    # V2G
    'v2g demand': '#ff7f00',
    'v2g gen':    '#ffb84d',

    'ev_flex demand': '#ffa733',

    # Curtailment and net flows
    'Curtailment Market': '#d95f5f',         # Muted red
    'Net_Export': '#888888',                 # Light gray
    'Net Import': '#525252',                 # Dark gray

    # Thermal generation
    'CCGTCCS gen': '#999999',
    'CCGTresmethane gen': '#b15928',
    'SCGTfossil gen': '#8d8d8d',
    'SCGTresmethane gen': '#c49c94',

    # Battery - pinkish/red tone
    'battery gen': '#e377c2',                # Rose pink (distinct from others)
    'battery demand': '#a04382',               #  Dark magenta
    

    # Hydro generation (classic hydro)
    'dam gen': '#3182bd',

    # Other generation
    'biomass gen': '#8c564b',
    'oil gen': '#7f7f7f',
    'other gen': '#5fb3b3',

    # Renewables
    'pvrf gen': '#ffdd57',                   # Solar - yellow
    'windon gen': '#1f78b4',                 # Wind - blue

    # Fixed consumer or inflow
    'CH00_fixedconsumer': 'black',
    'Infeed preexisting Wind': '#a1dab4',
    'Infeed preexisting RoR':  '#41b6c4',
    'Infeed preexisting PV':   '#fec44f'
}

dispatch_legend_labels = {
    "PSP demand": {"en": "Pumped Storage Demand", "de": "Pumpspeicherverbrauch"},
    "PSP gen": {"en": "Hydrogeneration", "de": "Wasserkraft"},
    "Other gen": {"en": "Other Generation", "de": "Sonstige Erzeugung"},
    "Battery gen": {"en": "Battery Generation", "de": "Batterieerzeugung"},
    "RES gen": {"en": "Renewable Generation", "de": "Erneuerbare Erzeugung"},
    "Heating demand": {"en": "Heating Demand", "de": "Wärmeverbrauch"},
    "EV flexible demand": {"en": "EV Flexible Demand", "de": "Flexibler EV-Verbrauch"},
    "heat_pump demand": {"en": "Heat Pump Demand", "de": "Wärmepumpenverbrauch"},
    "heat_pump_households demand": {"en": "Household Heat Pump Demand", "de": "Haushalts-Wärmepumpenverbrauch"},
    "hydrogen demand": {"en": "Hydrogen Demand", "de": "Wasserstoffverbrauch"},
    "nuclear demand": {"en": "Nuclear Demand", "de": "Kernenergieverbrauch"},
    "psp_close demand": {"en": "Closed PSP Demand", "de": "Pumpspeicherkraftwerken-Verbrauch"},
    "psp_open demand": {"en": "Open PSP Demand", "de": "Wasserkraftwerk"},
    "resistive_heater demand": {"en": "Resistive Heater Demand", "de": "Widerstandsheizungsverbrauch"},
    "v2g demand": {"en": "V2G Charging Demand", "de": "V2G-Ladeverbrauch"},
    "ev_flex demand": {"en": "EV Flex Demand", "de": "EV-Flexverbrauch"},
    "Curtailment Market": {"en": "Curtailment", "de": "Abregelung"},
    "Net_Export": {"en": "Net Export", "de": "Nettoexport"},
    "CCGTCCS gen": {"en": "CCGT with CCS", "de": "GuD mit CCS"},
    "CCGTresmethane gen": {"en": "CCGT (Renewable Methane)", "de": "GuD (erneuerbares Methan)"},
    "SCGTfossil gen": {"en": "SCGT (Fossil)", "de": "SGT (fossil)"},
    "SCGTresmethane gen": {"en": "SCGT (Renewable Methane)", "de": "SGT (erneuerbares Methan)"},
    "battery gen": {"en": "Battery Generation", "de": "Batterieerzeugung"},
    "dam gen": {"en": "Reservoir Hydro", "de": "Speicherkraftwerk"},
    "hydrogen gen": {"en": "Hydrogen Generation", "de": "Wasserstofferzeugung"},
    "nuclear gen": {"en": "Nuclear Generation", "de": "Kernenergieerzeugung"},
    "oil gen": {"en": "Oil Generation", "de": "Ölerzeugung"},
    "psp_close gen": {"en": "Closed PSP Generation", "de": "Pumpspeichererzeugung"},
    "biomass gen": {"en": "Biomass Generation", "de": "Biomasseerzeugung"},
    "other gen": {"en": "Other Generation", "de": "Sonstige Erzeugung"},
    "pvrf gen": {"en": "Photovoltaic (Rooftop)", "de": "PV (Dach)"},
    "windon gen": {"en": "Onshore Wind", "de": "Wind Onshore"},
    "v2g gen": {"en": "V2G Discharge", "de": "V2G-Einspeisung"},
    "psp_open gen": {"en": "Open PSP Generation", "de": "Wasserkraft"},
    "CH00_fixedconsumer": {"en": "Fixed Consumer Load", "de": "Feste Verbrauchslast"},
    "Consumption - Inflexible": {"en": "Inflexible Consumption", "de": "Verbrauch (unflexibler)"},
    "Infeed preexisting Wind": {"en": "Existing Wind Infeed", "de": "Bestandswind-Einspeisung"},
    "Infeed preexisting RoR": {"en": "Existing RoR Infeed", "de": "Bestandsflusskraft-Einspeisung"},
    "Infeed preexisting PV": {"en": "Existing PV Infeed", "de": "Bestands-PV-Einspeisung"},
    "Net Import": {"en": "Net Import", "de": "Nettoimport"},
    "battery demand": {"en": "Battery Demand", "de": "Batterieverbrauch"},
    "Electrolyzer demand": {"en": "Electrolyzer Demand", "de": "Elektrolyseur-Verbrauch"},
}

invest_color_mapping = {
    "CH00_CCGTresmethane": "orange",
    "CH00_SCGTresmethane": "brown",
    "CH00_CCGTCCS": "green",
    "CH00_SCGTfossil": "black",
    "CH00_hydrogen": "lightblue",
    "CH00_oil": "darkred",
    "CH00_nuclear": "purple",
    "PV CH": "gold",
    "Wind CH": "blue",
    "Battery CH": "red",
}

dispatchDH_legend_labels = {	
    "TTES_meduim_demand": {"en": "Tank TES Demand", "de": "Tankwärmespeicher  Nachfrage"},
    "PTES_large_demand": {"en": "Pit TES  Demand", "de": "Erdbeckenwärmespeicher Nachfrage"},
    "thermalNew": {"en": "Thermal plant", "de": "Wärmekraftwerk"},
    "resistiveNew": {"en": "Resistive Heating", "de": "Elektro-Heizkessel Nachfrage"},
    "TTES_medium": {"en": "Tank TES generation", "de": "Tankwärmespeicher"},
    "PTES_large": {"en": "Pit TES generation", "de": "Erdbeckenwärmespeicher"},
    "HPG": {"en": "Heat Pump at natural resources", "de": "Wärmepumpe an natürlichen Ressourcen"},
    "HPNew": {"en": "Heat Pump", "de": "Wärmepumpe"},
    "CHPNew": {"en": "CHP", "de": "Kraft-Wärme-Kopplung"},
    "Consumption": {"en": "Demand (Thermal)", "de": "Nachfrage (Thermisch)"},
    "Price - Electricity": {"en": "Price - Electricity", "de": "Preis - Strom"},
    "Price - Heat": {"en": "Price - Heat", "de": "Preis - Wärme"},
}

dispatchDH_color_mapping = {
    "TTES_meduim_demand": "#8a04ac",         # Warm reddish-orange (heating)
    "PTES_large_demand": "#ee1adc",          # Warm reddish-orange (heating)
    "thermalNew": "#3698be",                 # Dark blue
    "resistiveNew": "#0a8d15",               # Light blue
    "TTES_medium": "#f70505",                # Dark gray-purple
    "PTES_large": "#e78607",                 # Light gray-lavender
    "HPG": "#f7b0b0",                        # Light blue
    "HPNew": "#6dd8d3",                      # 
    "CHPNew": "#F01470",                     # 
    "Consumption": "#1b1717",                
    "Price - Electricity": "#851c1c",        
    "Price - Heat": "#989266",               
}

