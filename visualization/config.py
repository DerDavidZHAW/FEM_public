# Shared configuration for visualization scripts

# Show negative values below zero (True) or not (False)
show_negative_below_zero = False

plot_treshold_TWh = 0.1  # Minimum total absolute value for a technology to be shown in the legend

# Define the y-axis range for generation plots (TWh)
if show_negative_below_zero:
    y_min, y_max = -5, 45  # Custom y-axis range
else:
    y_min, y_max = 0, 45  # Custom y-axis range

# Define the y-axis range for capacity plots (GW)
y_min_capacity, y_max_capacity = 0, 45  # Custom y-axis range
plot_treshold_GW = 0.09  # Minimum total absolute value for a technology to be shown in the legend

# Number of subplots in all mesh plots (rows x columns)
num_rows, num_cols = 4, 5  

# Dictionary to rename technologies to easy names
tech_rename = {
    "pv_all": "Solar PV",
    "wind_all": "Wind",
    "ror": "Run-of-River Hydro",
    "psp_open": "Open PSP",
    "psp_close": "Pumped Storage",
    "battery": "Battery Storage",
    "PH2P": "Closed Loop Hydrogen",
    "biomass": "Biomass",
    "nuclear": "Nuclear",
    "other": "Other",
    "CCGTresmethane": "CCGT Renewable Methane",
    "SCGTresmethane": "SCGT Renewable Methane",
    "CCGTCCS": "CCGT with CCS",
    "SCGTfossil": "SCGT Fossil Fuel",
    "hydrogen": "Hydrogen",
    "oil": "Oil",
    "lostload": "Lost Load"
}

# Dictionary to assign colors (hex color codes)
tech_colors = {
    "pv_all": "#FFD700",  # Yellow (for solar PV)
    "wind_all": "blue",  # Cyan (for wind)
    "ror": "#00CED1",  # DarkTurquoise (for hydro)
    "psp_open": "#4682B4",  # SteelBlue (for pumped storage open-loop)
    "psp_close": "#5F9EA0",  # CadetBlue (for pumped storage closed-loop)
    "battery": "#FF8C00",  # BlueViolet (for battery storage)
    "PH2P": "#FF4500",  # OrangeRed (for closed loop hydrogen)
    "biomass": "#8B4513",  # SaddleBrown (for biomass)
    "nuclear": "#4B0082",  # Dark Purple (for nuclear)
    "other": "#808080",  # Gray (for miscellaneous technologies)
    "CCGTresmethane": "#B8860B",  # Dark Yellow (for CCGT Renewable Methane)
    "SCGTresmethane": "#DAA520",  # GoldenRod (Between Yellow & Brown for SCGT)
    "CCGTCCS": "#B8860B",  # Dark Yellow (for CCGT with CCS)
    "SCGTfossil": "#CD853F",  # Peru
    "hydrogen": "#FF69B4",  # Pink (for hydrogen)
    "oil": "#B7410E",  # rust (for liquid fuel)
    "lostload": "#000000"  # Black (for lost load)
}
