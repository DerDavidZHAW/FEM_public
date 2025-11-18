"""
This script creates a stacked bar chart showing the annual generation/consumption balance for different scenarios.

The data is read from a csv file containing the annual generation/consumption balance for different scenarios.
The data is filtered to select the relevant columns and rows for plotting.
The data is then grouped by "tech/type" and plotted as a stacked bar chart.

The plot is customized with colors, labels, and layout settings to improve readability and visual appeal.

The final plot is displayed using Plotly, a Python graphing library, and saved as an image file for further use.

Input:
- csv_file: Path to the CSV file containing the annual generation/consumption balance data (created by the results aggregation script).

Parameters:
- scenario_names_dic: A dictionary mapping scenario names in the CSV file to more descriptive names for the plot legend.
- output_directory

Output:
- Graphs illustrated on the screen and saved files in output\\visualization\\Annual_Generation_Consumption_Balance*.*
"""


import plotly.graph_objects as go
import pandas as pd

#%% Define the input data and parameters -------------------------------------------------------------
# Read the data from the CSV file
csv_file = r'output\aggregated\robust_07\Annual_balance_ch.csv'

# Select relevant columns for stacking - key is the name of the scenario in the CSV file and value is the descriptive name for the plot legend
scenario_names_dic = {
    # 'basecase_RTN_GASN_2050_NTCfull', 
    'basecase_RTN_GASY_2050_NTCfull': "Reference case",
    # 'basecase_R45_GASN_2050_NTCfull', 
    'basecase_R45_GASY_2050_NTCfull': "Reference case with 45 TWh RES"
}

output_directory = r'output\visualization'

#%% process data --------------------------------------------------------------------------------
df = pd.read_csv(csv_file, index_col=1, header=0, encoding='ISO-8859-1')

# Get the columns for stacking -----------------
stacked_columns = scenario_names_dic.keys()

# --- generation values ---
# Filter data for "gen" or "infeed" in the "gen/con" column, but do not include "import" rows
filtered_gen = df[df['gen/con'].isin(['infeed', 'gen'])][stacked_columns]
filtered_gen = filtered_gen[~filtered_gen.index.str.startswith("import")]

# rename the index of filtered_gen according to the following dictionary
filtered_gen.rename(index={
    "pv_all": 	 "PV",
	"wind_all": 	 "Wind",
	"ror": 	 "Hydro - RoR",
	"psp_open": 	 "Hydro - dam & open pump storage",
	"psp_close": 	 "Hydro - closed pump storage",
	"battery": 	 "Battery",
	"biomass": 	 "Biomass",
	"nuclear": 	 "Nuclear",
	"other": 	 "Other",
	"CCGTresmethane": 	 "CCGT RES methane",
	"SCGTresmethane": 	 "SCGT RES methane",
	"CCGTCCS": 	 "CCGT with CCS",
	"SCGTfossil": 	 "SCGT fossil",
	"hydrogen": 	 "Hydrogen",
	"lostload": 	 "Energy not served",
}, inplace=True)

# Handle "import" rows: sum, negate, and create a new row "Import Net"
import_rows = df[df.index.str.startswith("import")][stacked_columns]
import_net = import_rows.sum()

# add the import_net to the filtered_gen
filtered_gen.loc["Import Net"] = import_net


# --- demand values ---
# filtered_dem is the consumption data, "demand" the "gen/con" column of df, but not "fixed" rows
filtered_dem = df[df['gen/con'] == 'demand'][stacked_columns]

# remove all rows that have "fixed" in their name, or "flex electrolyzer" or "flex psp"
filtered_dem = filtered_dem[~filtered_dem.index.str.contains("fixed")]
filtered_dem = filtered_dem[~filtered_dem.index.str.contains("flex electrolyzer")]
filtered_dem = filtered_dem[~filtered_dem.index.str.contains("flex psp")]

# sum all values that have "fixed" or "flex electrolyzer" in their name - fixed consumption (e.g., fixed modelled houshold and fixed modelled commercial)
fixed = df[df.index.str.contains("fixed")][stacked_columns].sum()
fixed_electrolyzer = df[df.index.str.contains("flex electrolyzer")][stacked_columns].sum()
flex_psp_ = df[df.index.str.contains("flex psp")][stacked_columns].sum() 

# rename the index of filtered_dem according to the following dictionary
filtered_dem.rename(index={
	# "flex electrolyzer": "Electrolyzer",
	"flex battery": "Consumption Battery",
	"flex hydrogen": "Consumption Hydrogen Prod.",
	"curtailment": "Curtailment",
	# "transport": "Transport",
	# "other": "Other",
}, inplace=True)

# add the fixed, fixed_electrolyzer and flex_psp_ to the filtered_dem
filtered_dem.loc["Conventional Consumption"] = fixed + fixed_electrolyzer
filtered_dem.loc["Pump Storage"] = flex_psp_



# Extract data for plotting, grouping by "tech/type"
filtered_gen = filtered_gen/1000000  # Convert to TWh
filtered_dem = filtered_dem/1000000  # Convert to TWh
filtered_dem = - filtered_dem  # Negate to make consumption

color_map = {
    'PV': 'rgba(255, 255, 0, 1)',               # Yellow (Solar PV)
    'Wind': 'rgba(135, 206, 250, 1)',           # Light Blue (Wind)
    'Hydro - RoR': 'rgba(0, 191, 255, 1)',      # Deep Sky Blue (Run of River Hydro)
    'Hydro - dam & open pump storage': 'rgba(70, 130, 180, 1)',  # Steel Blue (Hydro Dam & Open Pump Storage)
    'Hydro - closed pump storage': 'rgba(100, 149, 237, 1)',     # Cornflower Blue (Closed Pump Storage)
    'Battery': 'rgba(255, 165, 0, 1)',          # Orange (Battery Storage)
    'Biomass': 'rgba(34, 139, 34, 1)',          # Forest Green (Biomass)
    'Nuclear': 'rgba(128, 0, 128, 1)',          # Purple (Nuclear)
    'Other': 'rgba(128, 128, 128, 1)',          # Gray (Other)
    'CCGT RES methane': 'rgba(255, 215, 0, 1)', # Gold (Combined Cycle Gas Turbine - Renewable Methane)
    'SCGT RES methane': 'rgba(218, 165, 32, 1)',# Goldenrod (Simple Cycle Gas Turbine - Renewable Methane)
    'CCGT with CCS': 'rgba(0, 128, 128, 1)',    # Teal (Combined Cycle Gas Turbine with Carbon Capture and Storage)
    'SCGT fossil': 'rgba(165, 42, 42, 1)',      # Brown (Simple Cycle Gas Turbine - Fossil)
    'Hydrogen': 'rgba(255, 144, 144, 1)',         # Pinkish (Hydrogen)
    'Liquid fuel': 'rgba(165, 42, 42, 1)',      # Brown (Liquid Fuel)
    'Energy not served': 'rgba(0, 0, 0, 1)',    # Black (Energy Not Served)
    'Import Net': 'rgba(128, 128, 128, 1)',     # Grey (Import Net)    # New categories
    'Consumption Battery': 'rgba(255, 69, 0, 1)',       # Orange-Red (Battery Consumption)
    'Consumption Hydrogen Prod.': 'rgba(0, 255, 127, 1)', # Spring Green (Hydrogen Production)
    'Curtailment': 'rgba(255, 99, 71, 1)',               # Tomato (Curtailment of excess energy)
    'Pump Storage': 'rgba(30, 144, 255, 1)',             # Dodger Blue (Pump Storage consumption)
}

color_map_gen = {
    'PV': 'rgba(255, 255, 0, 1)',               # Yellow (Solar PV)
    'Wind': 'rgba(135, 206, 250, 1)',           # Light Blue (Wind)
    'Hydro - RoR': 'rgba(0, 191, 255, 1)',      # Deep Sky Blue (Run of River Hydro)
}

#%% Create the Plotly figure -------------------------------------------------------------------------
# Create the Plotly figure
fig = go.Figure()

# create and stacked bar chart
# the x-axis values are the columns of the filtered_gen and filtered_dem dataframes
# the y-axis values are the values of the filtered_gen and filtered_dem dataframes
# filtered_gen values are stacked on the positive side of the y-axis 
# filtered_dem values are stacked on the negative side of the y-axis

for tech_type in filtered_gen.index:
	# skip the rows that have all values equal to zero
	if (filtered_gen.loc[tech_type].abs() >= 0.001).any():
		fig.add_trace(go.Bar(
			x=[scenario_names_dic[x] for x in filtered_gen.columns],
			y=filtered_gen.loc[tech_type],
			name=tech_type,
            marker_color=color_map.get(tech_type, 'rgba(128, 128, 128, 1)'),  # Default color: gray
			# marker_color='rgba(255,0,0,1)',
			# text=filtered_gen.loc[tech_type],
			# textposition='auto',
			# texttemplate='%{text:.2f} TWh',
			hoverinfo='text',
		))

for tech_type in filtered_dem.index:
	if tech_type != "Conventional Consumption":
		# skip the rows that have all values equal to zero
		if (filtered_dem.loc[tech_type].abs() >= 0.001).any():
			fig.add_trace(go.Bar(
				x=[scenario_names_dic[x] for x in filtered_dem.columns],
				y=filtered_dem.loc[tech_type],
				name=tech_type,
				marker_color=color_map.get(tech_type, 'rgba(128, 128, 128, 1)'),  # Default color: gray
				# marker_color='rgba(0,0,255,1)',
				# text=filtered_dem.loc[tech_type],
				# textposition='auto',
				# texttemplate='%{text:.2f} TWh',
				hoverinfo='text',
			))

# Add a dots on the top of the bars at value of the "Conventional Consumption" row
fig.add_trace(go.Scatter(
	x=[scenario_names_dic[x] for x in filtered_dem.columns],
	y=-filtered_dem.loc["Conventional Consumption"],
	mode='markers',
	marker=dict(size=10, color='rgba(0,0,255,1)'),
	name="Conventional Consumption",
	hoverinfo='text',
))

# add a grid on the y-axis, specially for the y=0 line
fig.update_yaxes(showgrid=True, gridcolor='gray')
fig.update_layout(yaxis_zeroline=True, yaxis_zerolinecolor='black', yaxis_zerolinewidth=1)


# Update the layout
fig.update_layout(
	barmode='relative',
	# title='Annual Generation/Consumption Balance',
	# xaxis_title='Case',
	# yaxis_title='TWh',
	# plot_bgcolor='white',
	# autosize=False,
	# width=1.3*1200,
	# height=1*800,
)

fig.update_layout(
    # Title font settings
    title={
        'text': 'Annual Generation/Consumption Balance',  # Add a descriptive title
        'y': 0.95,  # Title position
        'x': 0.5,
        'xanchor': 'center',
        'yanchor': 'top',
        'font': {
            'size': 20,   # Increase title size
            'family': 'Arial, sans-serif',  # Set academic font style
        }
    },
    
    # Axis titles
    xaxis_title='Case',  # Set descriptive axis title
    yaxis_title='Generation/Demand Value (TWh)',  # Set y-axis title

    # Font sizes for axis titles and tick labels
    xaxis=dict(
        title_font=dict(size=16, family='Arial, sans-serif'),  # X-axis title font
        tickfont=dict(size=14),  # X-axis tick labels
        showgrid=True,           # Show subtle grid lines
        zeroline=False,          # Hide zero line if not needed
    ),
    yaxis=dict(
        title_font=dict(size=16, family='Arial, sans-serif'),  # Y-axis title font
        tickfont=dict(size=14),  # Y-axis tick labels
        showgrid=True,           # Show grid lines for readability
        zeroline=True,           # Keep zero line for clarity in stacked graph
        zerolinewidth=2,         # Highlight the zero line
        zerolinecolor='black',
    ),

    # Legend settings
    legend=dict(
        font=dict(size=12),  # Adjust legend font size
        orientation="h",  # Horizontal legend (adjust depending on data density)
        yanchor="top",  y=-0.2,  # Place legend at the bottom
        xanchor="center", x=0.5
    ),

    # Adjusting margins
    margin=dict(l=60, r=20, t=60, b=60),  # Adjust margins to prevent text from being cut off

    # Background and grid settings
    plot_bgcolor='white',  # White background
    paper_bgcolor='white',  # White paper background for clean, print-ready look

    # Removing unnecessary mode bar in academic papers
    showlegend=True
)
# Show the figure
fig.show()

#%% export file -------------------------------------------------------------------------------------
# import plotly.io as pio
# Assuming you have a Plotly figure named `fig`
# fig.write_image('output\\visualization\\Annual_Generation_Consumption_Balance.png', format='png')
fig.write_html(f'{output_directory}\\Annual_Generation_Consumption_Balance.html')
# fig.write_image("output\\visualization\\Annual_Generation_Consumption_Balance.svg", format='svg')