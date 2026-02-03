import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path

# Plotly im Browser öffnen
pio.renderers.default = "browser"

# ========== EINSTELLUNGEN ==========
WEATHER_YEAR = "wy1995"  # Wähle: "wy1995", "wy2008", oder "wy2009"
NODE = "CH00"
BASE_PATH = Path(__file__).parent.parent / 'output' / '20260122'

year = "2050"  # Wähle: "2035" oder "2050"

# Y-Achsen-Bereich für den Plot (None = automatisch)
Y_MIN = None  # z.B. 0 oder None für automatisch
Y_MAX = None  # z.B. 100 oder None für automatisch
# ===================================

# Alle Szenarien definieren (umgekehrte Reihenfolge)
scenarios = [
    f"{year}_sens_100_fixed_inv",
    f"{year}_sens_90_fixed_inv",
    f"{year}_sens_80_fixed_inv",
    f"{year}_sens_70_fixed_inv",
    f"{year}_sens_60_fixed_inv",
    f"{year}_sens_50_fixed_inv",
    f"{year}_sens_40_fixed_inv",
    f"{year}_sens_30_fixed_inv"
]

# Mapping für schönere Szenario-Namen
scenario_labels = {
    f"{year}_sens_100_fixed_inv": "NTC 100",
    f"{year}_sens_90_fixed_inv": "NTC 90",
    f"{year}_sens_80_fixed_inv": "NTC 80",
    f"{year}_sens_70_fixed_inv": "NTC 70",
    f"{year}_sens_60_fixed_inv": "NTC 60",
    f"{year}_sens_50_fixed_inv": "NTC 50",
    f"{year}_sens_40_fixed_inv": "NTC 40",
    f"{year}_sens_30_fixed_inv": "NTC 30"
}

# Daten einlesen und filtern
all_data = []

for scenario in scenarios:
    file_path = BASE_PATH / scenario / "energy_balance_dual.csv"
    settings_path = BASE_PATH / scenario / "settings.csv"
    
    if file_path.exists():
        df = pd.read_csv(file_path)
        
        # Read settings to get weight for the weather year
        weight = 1.0  # default fallback
        if settings_path.exists():
            settings_df = pd.read_csv(settings_path)
            # Find the weight_in_objective_fcn row
            weight_row = settings_df[settings_df['Item'] == 'weight_in_objective_fcn']
            if not weight_row.empty:
                # Find the column that contains the selected weather year
                for col in settings_df.columns:
                    if WEATHER_YEAR in col:
                        weight = float(weight_row[col].values[0])
                        break
        
        # Filtern: nur CH00 Node und gewähltes Weather Year
        df_filtered = df[
            (df['Node'] == NODE) & 
            (df['Scenarios'].str.contains(WEATHER_YEAR))
        ].copy()
        
        # Divide dual values by weight to get actual prices
        df_filtered['value'] = df_filtered['value'] / weight
        
        # Szenario-Namen extrahieren (ohne weather year)
        df_filtered['Scenario'] = scenario
        
        all_data.append(df_filtered[['Scenario', 'T', 'value']])
        print(f"{scenario}: weight for {WEATHER_YEAR} = {weight}")
    else:
        print(f"Warnung: {file_path} nicht gefunden!")

# Alle Daten kombinieren
df_combined = pd.concat(all_data, ignore_index=True)

# Zeitschritt-Nummer aus T-Spalte extrahieren
df_combined['T_num'] = df_combined['T'].str.extract(r't_(\d+)').astype(int)

# Winter und Sommer unterscheiden
# Winter: t_1-t_2184 und t_6553-t_8760
# Sommer: t_2185-t_6552
df_combined['Season'] = df_combined['T_num'].apply(
    lambda t: 'Winter' if (1 <= t <= 2184) or (6553 <= t <= 8760) else 'Sommer'
)

# Separate DataFrames für Winter und Sommer
df_winter = df_combined[df_combined['Season'] == 'Winter']
df_summer = df_combined[df_combined['Season'] == 'Sommer']

# Datenbereich ermitteln für realistische Violin-Darstellung
data_min = df_combined['value'].min()
data_max = df_combined['value'].max()
data_range = data_max - data_min
# Etwas Puffer hinzufügen (5% auf jeder Seite)
plot_min = data_min - 0.05 * data_range
plot_max = data_max + 0.05 * data_range

# Plotly Violin Plot erstellen mit Subplots
from plotly.subplots import make_subplots

fig = make_subplots(
    rows=2, cols=1,
    subplot_titles=('Winter', 'Summer'),
    vertical_spacing=0.12,
    row_heights=[0.5, 0.5]
)

# Winter Violins (obere Reihe)
for i, scenario in enumerate(scenarios):
    scenario_data = df_winter[df_winter['Scenario'] == scenario]['value']
    
    fig.add_trace(go.Violin(
        y=scenario_data,
        name=scenario_labels[scenario],
        x=[scenario_labels[scenario]] * len(scenario_data),
        box_visible=True,
        meanline_visible=True,
        showlegend=False,
        scalemode='width',
        width=0.8,
        legendgroup=scenario
    ), row=1, col=1)

# Sommer Violins (untere Reihe)
for i, scenario in enumerate(scenarios):
    scenario_data = df_summer[df_summer['Scenario'] == scenario]['value']
    
    fig.add_trace(go.Violin(
        y=scenario_data,
        name=scenario_labels[scenario],
        x=[scenario_labels[scenario]] * len(scenario_data),
        box_visible=True,
        meanline_visible=True,
        showlegend=False,
        scalemode='width',
        width=0.8,
        legendgroup=scenario
    ), row=2, col=1)

# Layout anpassen
fig.update_layout(
    width=1400,
    height=800,
    hovermode='closest',
    violinmode='overlay',
    showlegend=False,
    font=dict(size=16),
    title_font=dict(size=20)
)

# Subplot titles größer machen
for annotation in fig['layout']['annotations']:
    annotation['font'] = dict(size=18)

# X-Achsen beschriften
fig.update_xaxes(title_text="Scenario", row=2, col=1, tickangle=-45, title_font=dict(size=16), tickfont=dict(size=14))
fig.update_xaxes(tickangle=-45, row=1, col=1, tickfont=dict(size=14))

# Y-Achsen beschriften und Bereich setzen
for row in [1, 2]:
    fig.update_yaxes(title_text="Price [CHF/MWh]", row=row, col=1, title_font=dict(size=16), tickfont=dict(size=14))
    
    if Y_MIN is not None or Y_MAX is not None:
        fig.update_yaxes(range=[Y_MIN if Y_MIN is not None else plot_min, 
                                 Y_MAX if Y_MAX is not None else plot_max], 
                         row=row, col=1)
    else:
        fig.update_yaxes(range=[plot_min, plot_max], row=row, col=1)

# Plot im Browser anzeigen
fig.show()

# Als hochauflösendes PNG exportieren
output_filename = Path(__file__).parent / f"violin_plot_{year}_{NODE}_{WEATHER_YEAR}.png"
fig.write_image(output_filename, width=1400, height=800, scale=3)

# Crop top 200 pixels (scaled by 3) from the image
from PIL import Image
img = Image.open(output_filename)
# scale=3, so 200 pixels in display = 600 pixels in the actual image
crop_top = 200 # * 3  # 600 pixels
cropped_img = img.crop((0, crop_top, img.width, img.height))
cropped_img.save(output_filename)
print(f"\nPlot exportiert als: {output_filename} (cropped top 200px)")

# Optionale Statistiken ausgeben
print(f"\n=== Statistiken für {NODE} - {WEATHER_YEAR} ===")
print("\n--- WINTER ---")
print(df_winter.groupby('Scenario')['value'].describe())
print("\n--- SOMMER ---")
print(df_summer.groupby('Scenario')['value'].describe())
