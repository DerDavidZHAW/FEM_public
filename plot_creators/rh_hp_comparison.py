"""
Script to compare investment and operation costs of thermal storages, heat pumps, 
and resistive heaters across different scenarios.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
from pathlib import Path

pio.renderers.default = "browser"

year = "2050"  # Choose: "2035" or "2050"

# Define scenarios to compare
scenarios = {
    # "{year}_sens_100": r"C:\Models\Future_Markets\output\20260119\{year}_sens_100",
    # "{year}_sens_30": r"C:\Models\Future_Markets\output\20260119\{year}_sens_30",
    f"{year}_aa": rf"C:\Models\Future_Markets\output\20260119\{year}_aa",
    f"{year}_aa_rh_1000": rf"C:\Models\Future_Markets\output\20260119\{year}_aa_rh_1000",
    f"{year}_aa_rh_500": rf"C:\Models\Future_Markets\output\20260119\{year}_aa_rh_500",
    f"{year}_aa_rh_250": rf"C:\Models\Future_Markets\output\20260119\{year}_aa_rh_250",
    f"{year}_aa_rh_0": rf"C:\Models\Future_Markets\output\20260119\{year}_aa_rh_0",
}

# Define base colors
base_colors = [
    'rgb(237,219,171)',  # beige
    'rgb(240,182,0)',    # yellow
    'rgb(131,184,25)',   # green
    'rgb(88,49,25)',     # brown
    'rgb(0,102,51)',     # dark green
    'rgb(45,101,175)',   # blue
]

# Define colors for categories using base colors
colors = {
    "HP": base_colors[0],           # beige
    "resistive heaters": 'rgb(150,150,150)',  # grey
    "PTES": base_colors[2],         # green
    "TTES": base_colors[5],         # blue
    "CHP": base_colors[3],          # brown
    "dsrTh": base_colors[4],        # dark green
}

# Read COP data from plants_DH_invest_candidates.csv
base_dir = Path(__file__).parent.parent
cop_data_path = base_dir / "input" / "plants_DH_invest_candidates.csv"
cop_df = pd.read_csv(cop_data_path)

# Create COP dictionary for heat pumps
cop_dict = {}
for _, row in cop_df.iterrows():
    if row['tech'] == 'heat_pump' and pd.notna(row['efficiency']):
        cop_dict[row['index']] = row['efficiency']

# Also read features file for HPG plants
features_path = base_dir / "input" / "plants_DH_CH_features.csv"
features_df = pd.read_csv(features_path)
for _, row in features_df.iterrows():
    if row['tech'] == 'heat_pump' and '_HPG' in row['index']:
        cop_dict[row['index']] = row['efficiency']  # COP of 5 for HPG

print("COP dictionary:", cop_dict)

# Read cost assumptions for CHP fuel costs
# CHP plants use CCGTCCS technology (natural gas with CCS)
cost_assumptions_path = base_dir / "input" / "cost_assumptions.xlsx"
cost_assumptions_df = pd.read_excel(cost_assumptions_path, sheet_name='03_Calculated_Costs')

# Get CCGTCCS fuel price (CHF/MWh_fuel) for the selected year
# CHP plants use CCGTCCS technology - fuel cost is in input_cost_scenario_ZERO column
ccgtccs_fuel_price = cost_assumptions_df[
    (cost_assumptions_df['technology'] == 'CCGTCCS') & 
    (cost_assumptions_df['year'] == int(year))
]['input_cost_scenario_ZERO'].values[0]

# Get CO2 price (CHF/tCO2) for the selected year
co2_price = cost_assumptions_df[
    (cost_assumptions_df['technology'] == 'co2') & 
    (cost_assumptions_df['year'] == int(year))
]['input_cost_scenario_ZERO'].values[0]

# Get emission factor for CCGTCCS (tCO2/MWh_fuel)
ccgtccs_emission_factor = cost_assumptions_df[
    (cost_assumptions_df['technology'] == 'CCGTCCS') & 
    (cost_assumptions_df['year'] == int(year))
]['emission_factor'].values[0]

print(f"\nCHP cost assumptions for {year}:")
print(f"  CCGTCCS fuel price: {ccgtccs_fuel_price:.2f} CHF/MWh_fuel")
print(f"  CO2 price: {co2_price:.2f} CHF/tCO2")
print(f"  CCGTCCS emission factor: {ccgtccs_emission_factor:.4f} tCO2/MWh_fuel")

# Initialize storage for results
results = {}

for scenario_name, scenario_path in scenarios.items():
    print(f"\nProcessing scenario: {scenario_name}")
    
    # Read investment costs
    inv_path = f"{scenario_path}\\cost_inv_dict.csv"
    inv_df = pd.read_csv(inv_path)
    
    # Read thermal investment costs
    inv_thermal_path = f"{scenario_path}\\cost_inv_thermal_dict.csv"
    inv_thermal_df = pd.read_csv(inv_thermal_path)
    
    # Read operation costs
    op_path = f"{scenario_path}\\cost_op_dict.csv"
    op_df = pd.read_csv(op_path)
    
    # Read thermal operation costs
    op_thermal_path = f"{scenario_path}\\cost_op_thermal_dict.csv"
    op_thermal_df = pd.read_csv(op_thermal_path)
    
    # Read thermal generation data
    genTh_path = f"{scenario_path}\\genTh.csv"
    genTh_df = pd.read_csv(genTh_path)
    
    # Read electricity prices
    price_path = f"{scenario_path}\\energy_balance_dual.csv"
    price_df = pd.read_csv(price_path)
    
    # Filter electricity prices for CH00 only
    price_ch00 = price_df[price_df['Node'] == 'CH00'][['T', 'Scenarios', 'value']].copy()
    price_ch00.rename(columns={'value': 'price_CHF_per_MWh'}, inplace=True)
    
    # Read scenario weights
    weights_path = f"{scenario_path}\\weight_in_objective_fcn.csv"
    weights_df = pd.read_csv(weights_path)
    weights_dict = dict(zip(weights_df['Scenarios'], weights_df['value']))
    
    print(f"  Scenario weights: {weights_dict}")
    
    # Initialize category sums
    # NOTE: Investment and operation costs in CSV files are PRE-WEIGHTED by scenario probability
    # So we SUM across subscenarios to get the expected annual cost
    # Electricity prices are PURE (not weighted), so we must weight them when calculating elec costs
    categories = {
        # Investment costs (pre-weighted, so just sum)
        'inv_HP': 0,
        'inv_resistive': 0,
        'inv_PTES': 0,
        'inv_TTES': 0,
        'inv_CHP': 0,
        # Operation costs (pre-weighted, so just sum)
        'op_PTES': 0,
        'op_TTES': 0,
        'op_dsrTh': 0,
        # Consumed electricity costs (will be weighted manually)
        'elec_HP': 0,
        'elec_resistive': 0,
        # CHP fuel and CO2 costs (will be weighted manually)
        'fuel_CHP': 0,
        'co2_CHP': 0,
        # CHP electricity revenue (will be weighted manually)
        'revenue_CHP': 0,
        # Heat generation by source (MWh_th, will be weighted)
        'heat_HP': 0,
        'heat_resistive': 0,
        'heat_CHP': 0,
    }
    
    # Get list of unique subscenarios
    subscenarios = sorted(inv_df['scenario'].unique())
    
    print(f"  Found subscenarios: {subscenarios}")
    
    # Process investment costs (exclude thermalNew as instructed)
    # Costs are pre-weighted, so we just SUM
    for _, row in inv_df.iterrows():
        plant = row['plant']
        cost = row['cost_CHF']  # Already weighted, just sum
        
        if 'thermalNew' in plant:
            continue  # Skip gas boilers
        elif '_CHPNew' in plant:
            categories['inv_CHP'] += cost
        elif '_HPNew' in plant or '_HPG' in plant:
            categories['inv_HP'] += cost
        elif '_resistiveNew' in plant:
            categories['inv_resistive'] += cost
        elif 'TTES' in plant:
            categories['inv_TTES'] += cost
        elif 'PTES' in plant:
            categories['inv_PTES'] += cost
    
    # Process thermal investment costs
    # Costs are pre-weighted, so we just SUM
    for _, row in inv_thermal_df.iterrows():
        plant = row['plant']
        cost = row['cost_CHF']  # Already weighted, just sum
        
        if 'thermalNew' in plant:
            continue  # Skip gas boilers
        elif '_CHPNew' in plant:
            categories['inv_CHP'] += cost
        elif '_HPNew' in plant or '_HPG' in plant:
            categories['inv_HP'] += cost
        elif '_resistiveNew' in plant:
            categories['inv_resistive'] += cost
        elif 'TTES' in plant:
            categories['inv_TTES'] += cost
        elif 'PTES' in plant:
            categories['inv_PTES'] += cost
    
    # Process operation costs (exclude thermalNew)
    # Costs are pre-weighted, so we just SUM
    for _, row in op_df.iterrows():
        plant = row['plant']
        cost = row['cost_CHF']  # Already weighted, just sum
        
        if 'thermalNew' in plant:
            continue  # Skip gas boilers
        elif 'dsrTh' in plant:
            categories['op_dsrTh'] += cost
        elif 'TTES' in plant:
            categories['op_TTES'] += cost
        elif 'PTES' in plant:
            categories['op_PTES'] += cost
    
    # Process thermal operation costs
    # Costs are pre-weighted, so we just SUM
    for _, row in op_thermal_df.iterrows():
        plant = row['plant']
        cost = row['cost_CHF']  # Already weighted, just sum
        
        if 'thermalNew' in plant:
            continue  # Skip gas boilers
        elif 'dsrTh' in plant:
            categories['op_dsrTh'] += cost
        elif 'TTES' in plant:
            categories['op_TTES'] += cost
        elif 'PTES' in plant:
            categories['op_PTES'] += cost
    
    # Process consumed electricity costs and heat generation
    # Prices are PURE (not weighted), so we must weight them when calculating costs
    # genTh values are also PURE (not weighted), so we must weight them
    # Merge genTh with electricity prices
    genTh_with_price = genTh_df.merge(price_ch00, on=['T', 'Scenarios'], how='left')
    
    # Read fuel consumption for CHP plants
    fuel_consumption_path = f"{scenario_path}\\fuel_consumption_of_plant.csv"
    fuel_consumption_df = pd.read_csv(fuel_consumption_path)
    
    # Filter for CHP plants only (same selection as investment costs)
    chp_fuel_consumption = fuel_consumption_df[
        fuel_consumption_df['P_fuellimCH_plus_P_fuellimCH_DH'].str.contains('_CHPNew', na=False)
    ].copy()
    
    # Calculate CHP fuel and CO2 costs
    # Fuel consumption is in MWh_fuel (already accounting for plant efficiency in the model)
    # Cost = fuel_consumption * (fuel_price + emission_factor * CO2_price)
    for plant in chp_fuel_consumption['P_fuellimCH_plus_P_fuellimCH_DH'].unique():
        plant_data = chp_fuel_consumption[chp_fuel_consumption['P_fuellimCH_plus_P_fuellimCH_DH'] == plant]
        
        for subscen in plant_data['Scenarios'].unique():
            subscen_data = plant_data[plant_data['Scenarios'] == subscen]
            weight = weights_dict.get(subscen, 1.0 / len(subscenarios))
            
            total_fuel_consumption = subscen_data['value'].sum()  # MWh_fuel
            
            # Fuel cost = fuel_consumption * fuel_price (CCGTCCS fuel price)
            fuel_cost = total_fuel_consumption * ccgtccs_fuel_price * weight
            categories['fuel_CHP'] += fuel_cost
            
            # CO2 cost = fuel_consumption * emission_factor * CO2_price
            co2_cost = total_fuel_consumption * ccgtccs_emission_factor * co2_price * weight
            categories['co2_CHP'] += co2_cost
    
    # Read electricity generation for CHP plants to calculate revenue
    gen_path = f"{scenario_path}\\gen.csv"
    gen_df = pd.read_csv(gen_path)
    
    # Filter for CHP plants only
    chp_gen = gen_df[gen_df['P_gen'].str.contains('_CHPNew', na=False)].copy()
    
    # Merge with electricity prices
    chp_gen_with_price = chp_gen.merge(price_ch00, on=['T', 'Scenarios'], how='left')
    
    # Calculate CHP electricity revenue
    # NOTE: Prices in energy_balance_dual are already weighted duals from stochastic optimization
    # So we do NOT apply additional weighting - just sum generation * price
    categories['revenue_CHP'] = (chp_gen_with_price['value'] * chp_gen_with_price['price_CHF_per_MWh']).sum()
    
    # Calculate electricity consumption, costs, and heat generation
    for plant in genTh_with_price['PDH'].unique():
        plant_data = genTh_with_price[genTh_with_price['PDH'] == plant].copy()
        
        # Determine technology type
        is_hp = ('_HPNew' in plant or '_HPG' in plant)
        is_resistive = '_resistiveNew' in plant or 'resistive' in plant.lower()
        is_chp = '_CHPNew' in plant
        
        if is_hp:
            # Get COP for this plant
            cop = cop_dict.get(plant, 4.26)  # Default COP if not found
            # Electricity consumption = thermal generation / COP
            plant_data['elec_consumption_MWh'] = plant_data['value'] / cop
            plant_data['elec_cost_CHF'] = plant_data['elec_consumption_MWh'] * plant_data['price_CHF_per_MWh']
            
            # Electricity costs: prices are already weighted duals, so no additional weighting
            # Heat generation: weight to get expected value
            categories['elec_HP'] += plant_data['elec_cost_CHF'].sum()
            for subscen in plant_data['Scenarios'].unique():
                subscen_data = plant_data[plant_data['Scenarios'] == subscen]
                weight = weights_dict.get(subscen, 1.0 / len(subscenarios))
                heat_sum = subscen_data['value'].sum() * weight
                categories['heat_HP'] += heat_sum
        
        elif is_resistive:
            # Resistive heater: electricity consumption = thermal generation (COP ~1)
            plant_data['elec_consumption_MWh'] = plant_data['value']
            plant_data['elec_cost_CHF'] = plant_data['elec_consumption_MWh'] * plant_data['price_CHF_per_MWh']
            
            # Electricity costs: prices are already weighted duals, so no additional weighting
            # Heat generation: weight to get expected value
            categories['elec_resistive'] += plant_data['elec_cost_CHF'].sum()
            for subscen in plant_data['Scenarios'].unique():
                subscen_data = plant_data[plant_data['Scenarios'] == subscen]
                weight = weights_dict.get(subscen, 1.0 / len(subscenarios))
                heat_sum = subscen_data['value'].sum() * weight
                categories['heat_resistive'] += heat_sum
        
        elif is_chp:
            # CHP: just track heat generation (no electricity cost for CHP as it generates electricity)
            for subscen in plant_data['Scenarios'].unique():
                subscen_data = plant_data[plant_data['Scenarios'] == subscen]
                weight = weights_dict.get(subscen, 1.0 / len(subscenarios))
                heat_sum = subscen_data['value'].sum() * weight
                categories['heat_CHP'] += heat_sum
    
    results[scenario_name] = categories
    
    # Print summary
    print(f"\nSummary for {scenario_name}:")
    print(f"  Investment costs (expected annual, sum of weighted subscenarios):")
    print(f"    HP: {categories['inv_HP']:,.0f} CHF")
    print(f"    Resistive heaters: {categories['inv_resistive']:,.0f} CHF")
    print(f"    PTES: {categories['inv_PTES']:,.0f} CHF")
    print(f"    TTES: {categories['inv_TTES']:,.0f} CHF")
    print(f"    CHP: {categories['inv_CHP']:,.0f} CHF")
    print(f"  Operation costs (expected annual, sum of weighted subscenarios):")
    print(f"    PTES: {categories['op_PTES']:,.0f} CHF")
    print(f"    TTES: {categories['op_TTES']:,.0f} CHF")
    print(f"    dsrTh: {categories['op_dsrTh']:,.0f} CHF")
    print(f"  Consumed electricity costs (expected annual, weighted):")
    print(f"    Heat pumps: {categories['elec_HP']:,.0f} CHF")
    print(f"    Resistive heaters: {categories['elec_resistive']:,.0f} CHF")
    print(f"  CHP fuel and CO2 costs (expected annual, weighted):")
    print(f"    Fuel (natural gas): {categories['fuel_CHP']:,.0f} CHF")
    print(f"    CO2 emissions: {categories['co2_CHP']:,.0f} CHF")
    print(f"  CHP electricity revenue (expected annual, weighted):")
    print(f"    Revenue: {categories['revenue_CHP']:,.0f} CHF")
    print(f"    Net fuel cost (fuel - revenue): {categories['fuel_CHP'] - categories['revenue_CHP']:,.0f} CHF")
    print(f"  Heat generation (expected annual, weighted, MWh_th):")
    print(f"    Heat pumps: {categories['heat_HP']:,.0f} MWh")
    print(f"    Resistive heaters: {categories['heat_resistive']:,.0f} MWh")
    print(f"    CHP: {categories['heat_CHP']:,.0f} MWh")

# Scenario display names
scenario_display_names = {
    f"{year}_aa": "No restriction",
    f"{year}_aa_rh_1000": "1000 MW restriction",
    f"{year}_aa_rh_500": "500 MW restriction",
    f"{year}_aa_rh_250": "250 MW restriction",
    f"{year}_aa_rh_0": "0 MW restriction",
}

# Create figure with subplots: bar chart on top, pie charts below
num_scenarios = len(scenarios)
fig = make_subplots(
    rows=2, cols=num_scenarios,
    specs=[[{"type": "bar", "colspan": num_scenarios}] + [None] * (num_scenarios - 1),
           [{"type": "pie"}] * num_scenarios],
    subplot_titles=[''] + [scenario_display_names.get(s, s) for s in scenarios.keys()],
    row_heights=[0.6, 0.4],
    vertical_spacing=0.15,
)

# Define the order of categories (bottom to top)
inv_order = ['inv_HP', 'inv_resistive', 'inv_PTES', 'inv_TTES', 'inv_CHP']
op_order = ['op_PTES', 'op_TTES', 'op_dsrTh']
elec_order = ['elec_HP', 'elec_resistive']

# Create labels mapping
labels = {
    'inv_HP': 'HP',
    'inv_resistive': 'Resistive heaters',
    'inv_PTES': 'PTES',
    'inv_TTES': 'TTES',
    'inv_CHP': 'CHP',
    'op_PTES': 'PTES',
    'op_TTES': 'TTES',
    'op_dsrTh': 'dsrTh',
    'elec_HP': 'Heat pumps',
    'elec_resistive': 'Resistive heaters',
}

# Create list of display names for x-axis
x_labels = [scenario_display_names.get(s, s) for s in scenarios.keys()]

# Calculate CHP net cost (investment + fuel + CO2 - revenue) for each scenario
# Since net fuel is typically negative (revenue > costs), this reduces CHP total cost
chp_net_cost = {}
for s in scenarios.keys():
    net_fuel = results[s]['fuel_CHP'] + results[s]['co2_CHP'] - results[s]['revenue_CHP']
    chp_net_cost[s] = results[s]['inv_CHP'] + net_fuel  # Add negative net_fuel = subtract revenue benefit

# Calculate totals for each scenario (for percentage calculations and annotations)
scenario_totals = {}
for s in scenarios.keys():
    # Use CHP net cost instead of just investment
    total = sum([results[s][cat] for cat in ['inv_HP', 'inv_resistive', 'inv_PTES', 'inv_TTES'] + op_order + elec_order])
    total += chp_net_cost[s]
    scenario_totals[s] = total

# Categories to show percentages for (exclude operation costs and TTES investment)
show_percentage_cats = ['inv_HP', 'inv_resistive', 'inv_PTES', 'inv_CHP', 'elec_HP', 'elec_resistive']

# Add traces for investment costs
for cat in inv_order:
    label_key = cat.replace('inv_', '')
    
    # For CHP, use net cost (investment + fuel + CO2 - revenue)
    if cat == 'inv_CHP':
        values = [chp_net_cost[s] / 1e6 for s in scenarios.keys()]
        legend_label = 'CHP (Inv + Fuel - Elec Rev)'
    else:
        values = [results[s][cat] / 1e6 for s in scenarios.keys()]
        legend_label = labels[cat] + ' (Inv)'
    
    # Create text labels with percentages (only for non-TTES investment costs)
    if cat in show_percentage_cats:
        text_labels = []
        for s in scenarios.keys():
            if cat == 'inv_CHP':
                val = chp_net_cost[s]
            else:
                val = results[s][cat]
            total = scenario_totals[s]
            if total > 0 and val > 0:
                pct = (val / total) * 100
                if pct >= 3:  # Only show if >= 3%
                    text_labels.append(f'{pct:.0f}%')
                else:
                    text_labels.append('')
            else:
                text_labels.append('')
    else:
        text_labels = [''] * len(scenarios)
    
    shadow = '0px 0px 5px black, 0px 0px 5px black'

    fig.add_trace(go.Bar(
        name=legend_label,
        x=x_labels,
        y=values,
        marker_color=colors.get(label_key, '#999999'),
        legendgroup='investment',
        legendgrouptitle_text='Investment Costs',
        text=text_labels,
        textposition='inside',
        insidetextanchor='middle',
        textfont=dict(size=13, color='white', shadow=shadow),
    ), row=1, col=1)

# Add traces for operation costs (no percentages shown)
for cat in op_order:
    label_key = cat.replace('op_', '')
    values = [results[s][cat] / 1e6 for s in scenarios.keys()]
    
    fig.add_trace(go.Bar(
        name=labels[cat] + ' (Op)',
        x=x_labels,
        y=values,
        marker_color=colors.get(label_key, '#999999'),
        marker_pattern_shape="/",  # Pattern to distinguish from investment
        legendgroup='operation',
        legendgrouptitle_text='Operation Costs',
    ), row=1, col=1)

# Add traces for consumed electricity costs
for cat in elec_order:
    label_key = cat.replace('elec_', '')
    if label_key == 'HP':
        pass  # Already correct
    elif label_key == 'resistive':
        label_key = 'resistive heaters'
    values = [results[s][cat] / 1e6 for s in scenarios.keys()]
    
    # Create text labels with percentages
    text_labels = []
    for s in scenarios.keys():
        val = results[s][cat]
        total = scenario_totals[s]
        if total > 0 and val > 0:
            pct = (val / total) * 100
            if pct >= 3:  # Only show if >= 3%
                text_labels.append(f'{pct:.0f}%')
            else:
                text_labels.append('')
        else:
            text_labels.append('')
    
    fig.add_trace(go.Bar(
        name=labels[cat] + ' (Elec)',
        x=x_labels,
        y=values,
        marker_color=colors.get(label_key, '#999999'),
        marker_pattern_shape=".",  # Pattern to distinguish from others
        legendgroup='electricity',
        legendgrouptitle_text='Electricity Consumption Costs',
        text=text_labels,
        textposition='inside',
        insidetextanchor='middle',
        textfont=dict(size=13, color='white', shadow=shadow),
    ), row=1, col=1)

# Add total annotations on top of bars
for idx, s in enumerate(scenarios.keys()):
    total = scenario_totals[s]
    # Calculate positive stack height (for annotation position)
    positive_sum = sum([results[s][cat] for cat in ['inv_HP', 'inv_resistive', 'inv_PTES', 'inv_TTES'] + op_order + elec_order])
    positive_sum += max(0, chp_net_cost[s])  # Only add if positive
    
    fig.add_annotation(
        x=x_labels[idx],
        y=positive_sum / 1e6,
        text=f'{total / 1e6:.1f} M',
        showarrow=False,
        yshift=10,
        font=dict(size=12, color='black', weight='bold'),
        row=1, col=1,
    )

# Add pie charts for heat sources
pie_colors = {
    'Heat Pumps': colors['HP'],
    'Resistive Heaters': colors['resistive heaters'],
    'CHP': colors['CHP'],
}

for idx, (scenario_name, _) in enumerate(scenarios.items()):
    heat_values = [
        results[scenario_name]['heat_HP'] / 1e6,  # Convert to GWh
        results[scenario_name]['heat_resistive'] / 1e6,
        results[scenario_name]['heat_CHP'] / 1e6,
    ]
    heat_labels = ['Heat Pumps', 'Resistive Heaters', 'CHP']
    
    # Filter out zero values
    filtered_labels = [l for l, v in zip(heat_labels, heat_values) if v > 0]
    filtered_values = [v for v in heat_values if v > 0]
    filtered_colors = [pie_colors[l] for l in filtered_labels]
    
    fig.add_trace(go.Pie(
        labels=filtered_labels,
        values=filtered_values,
        name=scenario_name,
        marker_colors=filtered_colors,
        textinfo='label+percent',
        textposition='inside',
        hovertemplate='%{label}: %{value:.1f} GWh<extra></extra>',
        showlegend=False,
    ), row=2, col=idx + 1)

# Update layout
fig.update_layout(
    barmode='stack',
    legend=dict(
        traceorder='grouped',
        groupclick='toggleitem'
    ),
    height=700,
    template='plotly_white',
    margin=dict(t=50, b=50),
    #uniformtext=dict(minsize=13, mode='show'),
)

# Update bar chart axes
fig.update_xaxes(title_text='Scenario', row=1, col=1)
fig.update_yaxes(title_text='Cost (Million CHF)', row=1, col=1)

# Add "Heat provision" label vertically on the left of pie charts
fig.add_annotation(
    text="Heat provision",
    x=-0.0525,
    y=0.1,
    xref="paper",
    yref="paper",
    textangle=-90,
    showarrow=False,
    font=dict(size=14, color='black'),
)

# Show plot
fig.show()