"""
Script to compare investment and operation costs of thermal storages, heat pumps, 
and resistive heaters across different scenarios.
"""

import argparse
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
from pathlib import Path
import re

pio.renderers.default = "browser"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare costs of thermal storages, heat pumps, and resistive heaters."
    )
    parser.add_argument(
        "--scenarios", nargs="+",
        help="Scenario folder names (relative to output/{output-folder}).",
    )
    parser.add_argument(
        "--display-names", nargs="+",
        help="Display names matching the scenarios order.",
    )
    parser.add_argument(
        "--output-base",
        help="Output path without extension for PDF/HTML/MD.",
    )
    parser.add_argument(
        "--output-folder", default="20260311",
        help="Date folder under output/ (default: 20260311).",
    )
    return parser.parse_args()


# ========== DEFAULT CONFIGURATION (for standalone execution) ==========
DEFAULT_OUTPUT_FOLDER = "20260311"
DEFAULT_YEAR = "2050"

DEFAULT_SCENARIOS = [
    f"{DEFAULT_YEAR}_070_inv_EUbat",
    f"{DEFAULT_YEAR}_070_inv_EUbat_rh_1000",
    f"{DEFAULT_YEAR}_070_inv_EUbat_rh_500",
    f"{DEFAULT_YEAR}_070_inv_EUbat_rh_250",
    f"{DEFAULT_YEAR}_070_inv_EUbat_rh_0",
]
DEFAULT_DISPLAY_NAMES = [
    "No restriction",
    "1000 MW restriction",
    "500 MW restriction",
    "250 MW restriction",
    "0 MW restriction",
]

# CHP cost allocation for a heat-provision cost view.
# "full": allocate full CHP operation cost to heat (recommended if full CHP electricity revenue is subtracted).
# "thermal_share": allocate CHP operation cost by thermal output share = heat / (heat + electricity).
CHP_OP_ALLOCATION_MODE = "full"

# Plot style and sizing (A4 landscape friendly)
PLOT_FONT_FAMILY = "Times New Roman"
PLOT_FONT_SIZE = 20
PLOT_PERCENT_TEXT_SIZE = 20
PLOT_BAR_PERCENT_TEXT_SIZE = PLOT_PERCENT_TEXT_SIZE + 4
PLOT_TITLE_SIZE = PLOT_FONT_SIZE + 4
PLOT_AXES_TITLE_SIZE = PLOT_FONT_SIZE + 2
PLOT_AXES_TICK_SIZE = PLOT_FONT_SIZE
PLOT_LEGEND_SIZE = PLOT_FONT_SIZE
PLOT_PIE_TEXT_SIZE = PLOT_PERCENT_TEXT_SIZE
PLOT_PERCENT_THRESHOLD = 10.0
PLOT_LABEL_COLOR = 'black'
PLOT_INSIDE_LABEL_COLOR = 'white'

FIGURE_WIDTH = 1400
FIGURE_HEIGHT = 990
PLOT_MARGIN_TOP = 35
ROW_VERTICAL_SPACING = 0.15
PIE_HORIZONTAL_SPACING = 0.03
PIE_SCENARIO_LABEL_Y = -0.05
PIE_SCENARIO_LABEL_WRAP_PARENS = True
PIE_SCENARIO_LABEL_MULTILINE_Y_OFFSET = -0.04
HEAT_SHARES_LABEL_Y = -0.125 # location of the "Heat provision shares by source (%)"
LEGEND_TRACEGROUP_GAP = 200
LEGEND_ENTRY_WIDTH = 275
# ======================================================================


def main():
    args = parse_args()

    output_folder = args.output_folder or DEFAULT_OUTPUT_FOLDER
    scenario_names_list = args.scenarios or DEFAULT_SCENARIOS
    display_names_list = args.display_names or DEFAULT_DISPLAY_NAMES

    if display_names_list and len(scenario_names_list) != len(display_names_list):
        print("Warning: scenarios and display names length mismatch. Falling back to auto labels.")
        display_names_list = []

    base_dir = Path(__file__).parent.parent
    output_base_dir = base_dir / "output" / output_folder

    # Build scenarios dict: scenario_key -> full path
    scenarios = {}
    for scen in scenario_names_list:
        scenarios[scen] = str(output_base_dir / scen)

    # Scenario display names (will be completed with auto labels below)
    scenario_display_names = dict(zip(scenario_names_list, display_names_list))

    def get_resistive_invested_mw(scenario_path: str) -> float | None:
        """Return invested resistive-heater power in MW from investment_summary.csv."""
        inv_summary_path = Path(scenario_path) / "investment_summary.csv"
        if not inv_summary_path.exists():
            return None

        try:
            inv_df = pd.read_csv(inv_summary_path, index_col=0)
        except Exception:
            return None

        if "Added Power (MW)" not in inv_df.columns:
            return None

        resistive_rows = [idx for idx in inv_df.index.astype(str) if "resistive" in idx.lower()]
        if not resistive_rows:
            return 0.0

        return float(inv_df.loc[resistive_rows, "Added Power (MW)"].sum())

    # Fill/override labels based on scenario name and invested RH level for unconstrained cases.
    for scen in scenario_names_list:
        match = re.search(r"_rh_(\d+)", scen)
        if match:
            scenario_display_names[scen] = f"RH {match.group(1)} MW"
        else:
            invested_mw = get_resistive_invested_mw(str(output_base_dir / scen))
            if invested_mw is None:
                scenario_display_names[scen] = "Unconstrained"
            else:
                scenario_display_names[scen] = f"RH {invested_mw:.0f} MW<br>(unconstrained)"

    if args.output_base:
        output_base_path = Path(args.output_base)
    else:
        output_base_path = Path(__file__).parent / "rh_hp_comparison"
    output_base_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine year from first scenario name
    year = scenario_names_list[0][:4]

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
            'op_CHP': 0,
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
            # CHP electricity generation (MWh_el, weighted) for optional CHP op-cost allocation
            'elec_CHP': 0,
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
            elif '_CHPNew' in plant:
                categories['op_CHP'] += cost
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

        # Weighted expected CHP electricity generation (MWh_el), used for optional op-cost allocation.
        for subscen in chp_gen_with_price['Scenarios'].unique():
            subscen_data = chp_gen_with_price[chp_gen_with_price['Scenarios'] == subscen]
            weight = weights_dict.get(subscen, 1.0 / len(subscenarios))
            categories['elec_CHP'] += subscen_data['value'].sum() * weight
    
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
        print(f"    CHP: {categories['op_CHP']:,.0f} CHF")
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

    # scenario_display_names is already built from args at the top of main()

    # Create figure with subplots: bar chart on top, pie charts below
    num_scenarios = len(scenarios)

    pie_subplot_label_items = []
    for scenario_name in scenarios.keys():
        label = str(scenario_display_names.get(scenario_name, scenario_name) or scenario_name)
        if PIE_SCENARIO_LABEL_WRAP_PARENS:
            label = label.replace(" (", "<br>(")
        pie_subplot_label_items.append((label, "<br>" in label))

    pie_subplot_labels = [label for label, _ in pie_subplot_label_items]

    fig = make_subplots(
        rows=2, cols=num_scenarios,
        specs=[[{"type": "bar", "colspan": num_scenarios}] + [None] * (num_scenarios - 1),
               [{"type": "pie"}] * num_scenarios],
        subplot_titles=[''] + pie_subplot_labels,
        row_heights=[0.6, 0.4],
        vertical_spacing=ROW_VERTICAL_SPACING,
        horizontal_spacing=PIE_HORIZONTAL_SPACING,
    )

    # Define the order of categories (bottom to top)
    inv_order = ['inv_HP', 'inv_resistive', 'inv_PTES', 'inv_TTES', 'inv_CHP']
    op_order = ['op_PTES', 'op_TTES', 'op_dsrTh', 'op_CHP_net']
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
        'op_CHP_net': 'CHP (Op+Fuel+CO2-Rev)',
        'elec_HP': 'Heat pumps',
        'elec_resistive': 'Resistive heaters',
    }

    op_bar_colors = {
        'op_CHP_net': colors['CHP'],
    }
    op_bar_patterns = {
        'op_PTES': '/',
        'op_TTES': '/',
        'op_dsrTh': '/',
        'op_CHP_net': 'x',
    }

    # Create list of display names for x-axis
    x_labels = [scenario_display_names.get(s, s) for s in scenarios.keys()]

    # Allocate CHP operation cost to the heat-provision cost view.
    chp_op_allocated = {}
    chp_op_alloc_share = {}
    for s in scenarios.keys():
        if CHP_OP_ALLOCATION_MODE == "thermal_share":
            denom = results[s]['heat_CHP'] + results[s]['elec_CHP']
            alloc_share = results[s]['heat_CHP'] / denom if denom > 0 else 1.0
        else:
            alloc_share = 1.0

        chp_op_alloc_share[s] = alloc_share
        chp_op_allocated[s] = results[s]['op_CHP'] * alloc_share

    def get_cat_value(scenario_key, cat):
        if cat == 'op_CHP_net':
            return (
                chp_op_allocated[scenario_key]
                + results[scenario_key]['fuel_CHP']
                + results[scenario_key]['co2_CHP']
                - results[scenario_key]['revenue_CHP']
            )
        return results[scenario_key][cat]

    # Calculate totals for each scenario (for percentage calculations and annotations)
    scenario_totals = {}
    for s in scenarios.keys():
        total = sum(get_cat_value(s, cat) for cat in inv_order + op_order + elec_order)
        scenario_totals[s] = total

    def percentage_text_labels(cat):
        labels_out = []
        for s in scenarios.keys():
            val = get_cat_value(s, cat)
            total = scenario_totals[s]
            if total > 0 and val > 0:
                pct = (val / total) * 100
                if pct > PLOT_PERCENT_THRESHOLD:
                    labels_out.append(f'{pct:.0f}%')
                else:
                    labels_out.append('')
            else:
                labels_out.append('')
        return labels_out

    shadow = '0px 0px 5px black, 0px 0px 5px black'

    # Add traces for investment costs
    for cat in inv_order:
        label_key = cat.replace('inv_', '')

        values = [get_cat_value(s, cat) / 1e6 for s in scenarios.keys()]
        legend_label = labels[cat]
        text_labels = percentage_text_labels(cat)

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
            textfont=dict(size=PLOT_BAR_PERCENT_TEXT_SIZE, color=PLOT_INSIDE_LABEL_COLOR, shadow=shadow, family=PLOT_FONT_FAMILY),
        ), row=1, col=1)

    # Add traces for operation costs
    for cat in op_order:
        label_key = cat.replace('op_', '')
        values = [get_cat_value(s, cat) / 1e6 for s in scenarios.keys()]
        text_labels = percentage_text_labels(cat)
    
        fig.add_trace(go.Bar(
            name=labels[cat],
            x=x_labels,
            y=values,
            marker_color=op_bar_colors.get(cat, colors.get(label_key, '#999999')),
            marker_pattern_shape=op_bar_patterns.get(cat, '/'),
            legendgroup='operation',
            legendgrouptitle_text='Operation Costs',
            text=text_labels,
            textposition='inside',
            insidetextanchor='middle',
            textfont=dict(size=PLOT_BAR_PERCENT_TEXT_SIZE, color=PLOT_INSIDE_LABEL_COLOR, shadow=shadow, family=PLOT_FONT_FAMILY),
        ), row=1, col=1)

    # Add traces for consumed electricity costs
    for cat in elec_order:
        label_key = cat.replace('elec_', '')
        if label_key == 'HP':
            pass  # Already correct
        elif label_key == 'resistive':
            label_key = 'resistive heaters'
        values = [results[s][cat] / 1e6 for s in scenarios.keys()]
        text_labels = percentage_text_labels(cat)
    
        fig.add_trace(go.Bar(
            name=labels[cat],
            x=x_labels,
            y=values,
            marker_color=colors.get(label_key, '#999999'),
            marker_pattern_shape=".",  # Pattern to distinguish from others
            legendgroup='electricity',
            legendgrouptitle_text='Electricity Consumption Costs',
            text=text_labels,
            textposition='inside',
            insidetextanchor='middle',
            textfont=dict(size=PLOT_BAR_PERCENT_TEXT_SIZE, color=PLOT_INSIDE_LABEL_COLOR, shadow=shadow, family=PLOT_FONT_FAMILY),
        ), row=1, col=1)

    # Add total annotations on top of bars
    for idx, s in enumerate(scenarios.keys()):
        total = scenario_totals[s]
        # Calculate positive stack height (for annotation position)
        positive_sum = sum(max(0, get_cat_value(s, cat)) for cat in inv_order + op_order + elec_order)
    
        fig.add_annotation(
            x=x_labels[idx],
            y=positive_sum / 1e6,
            text=f'{total / 1e6:.1f} M',
            showarrow=False,
            yshift=10,
            font=dict(size=PLOT_FONT_SIZE, color=PLOT_LABEL_COLOR, family=PLOT_FONT_FAMILY),
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

        total_heat = sum(filtered_values)
        pie_text = []
        for lbl, val in zip(filtered_labels, filtered_values):
            if lbl == 'Heat Pumps' and total_heat > 0:
                pie_text.append(f"{lbl}<br>{(val / total_heat) * 100:.0f}%")
            else:
                pie_text.append("")
    
        fig.add_trace(go.Pie(
            labels=filtered_labels,
            values=filtered_values,
            name=scenario_name,
            marker_colors=filtered_colors,
            text=pie_text,
            textinfo='text',
            textposition='inside',
            textfont=dict(size=PLOT_PIE_TEXT_SIZE, color=PLOT_LABEL_COLOR, family=PLOT_FONT_FAMILY),
            hovertemplate='%{label}: %{value:.1f} GWh<extra></extra>',
            showlegend=False,
        ), row=2, col=idx + 1)

    # Update layout
    fig.update_layout(
        barmode='stack',
        legend=dict(
            traceorder='grouped',
            groupclick='toggleitem',
            orientation='h',
            x=0.5,
            xanchor='center',
            y=-0.14,
            yanchor='top',
            tracegroupgap=LEGEND_TRACEGROUP_GAP,
            entrywidthmode='pixels',
            entrywidth=LEGEND_ENTRY_WIDTH,
            font=dict(size=PLOT_LEGEND_SIZE, color=PLOT_LABEL_COLOR, family=PLOT_FONT_FAMILY),
        ),
        height=FIGURE_HEIGHT,
        width=FIGURE_WIDTH,
        font=dict(size=PLOT_FONT_SIZE, color=PLOT_LABEL_COLOR, family=PLOT_FONT_FAMILY),
        template='plotly_white',
        margin=dict(t=PLOT_MARGIN_TOP, b=250, l=90, r=90),
        #uniformtext=dict(minsize=13, mode='show'),
    )

    # Make subplot titles and annotations publication-friendly.
    fig.update_annotations(font=dict(size=PLOT_TITLE_SIZE, color=PLOT_LABEL_COLOR, family=PLOT_FONT_FAMILY))

    # Move the pie subplot titles below pies while preserving their original x-centers.
    for label, is_multiline in pie_subplot_label_items:
        y_pos = PIE_SCENARIO_LABEL_Y
        if is_multiline:
            y_pos += PIE_SCENARIO_LABEL_MULTILINE_Y_OFFSET

        fig.update_annotations(
            selector=dict(text=label),
            y=y_pos,
            yref='paper',
            xref='paper',
            showarrow=False,
            align='center',
            font=dict(size=PLOT_AXES_TICK_SIZE, color=PLOT_LABEL_COLOR, family=PLOT_FONT_FAMILY),
        )

    # Update bar chart axes
    fig.update_xaxes(
        title_text='Scenario',
        row=1,
        col=1,
        title_font=dict(size=PLOT_AXES_TITLE_SIZE, color=PLOT_LABEL_COLOR, family=PLOT_FONT_FAMILY),
        tickfont=dict(size=PLOT_AXES_TICK_SIZE, color=PLOT_LABEL_COLOR, family=PLOT_FONT_FAMILY),
    )
    fig.update_yaxes(
        title_text='Cost (Million CHF)',
        row=1,
        col=1,
        title_font=dict(size=PLOT_AXES_TITLE_SIZE, color=PLOT_LABEL_COLOR, family=PLOT_FONT_FAMILY),
        tickfont=dict(size=PLOT_AXES_TICK_SIZE, color=PLOT_LABEL_COLOR, family=PLOT_FONT_FAMILY),
    )

    # Add explicit description for the lower pie-chart row.
    fig.add_annotation(
        text="Heat provision shares by source (%)",
        x=-0.06,
        y=HEAT_SHARES_LABEL_Y,
        xref="paper",
        yref="paper",
        textangle=-90,
        showarrow=False,
        font=dict(size=PLOT_AXES_TITLE_SIZE, color=PLOT_LABEL_COLOR, family=PLOT_FONT_FAMILY),
    )

    # Show plot
    fig.show()

    # ---- Write markdown description (before image export to ensure it's always produced) ----
    md_path = f"{output_base_path}.md"
    md_lines = [
        "# Resistive Heater / Heat Pump Cost Comparison",
        "",
        "This plot shows the cost breakdown (Million CHF) of heat supply technologies "
        "(investment, operation, electricity consumption, CHP investment/operation/fuel/CO2/revenue) "
        "and the heat provision shares (pie charts) across scenarios.",
        f"CHP operation cost allocation mode: **{CHP_OP_ALLOCATION_MODE}**.",
        "CHP operation bar is netted as: allocated CHP op + CHP fuel + CHP CO2 - CHP electricity revenue.",
        "",
        "## Cost Breakdown (Million CHF)",
        "",
    ]
    ordered_display_names = [scenario_display_names.get(s, s) for s in scenario_names_list]
    header = "| Category | " + " | ".join(ordered_display_names) + " |"
    sep = "|----------|" + "|".join(["------"] * len(ordered_display_names)) + "|"
    md_lines.append(header)
    md_lines.append(sep)

    cost_cats = [
        ('HP Investment', 'inv_HP'),
        ('Resistive Heater Inv.', 'inv_resistive'),
        ('PTES Investment', 'inv_PTES'),
        ('TTES Investment', 'inv_TTES'),
        ('CHP Investment', 'inv_CHP'),
        ('PTES Operation', 'op_PTES'),
        ('TTES Operation', 'op_TTES'),
        ('dsrTh Operation', 'op_dsrTh'),
        ('CHP Net Operation (Op+Fuel+CO2-Rev)', 'op_CHP_net'),
        ('HP Electricity', 'elec_HP'),
        ('RH Electricity', 'elec_resistive'),
        ('**Total Heat Provision Cost**', 'total_heat_cost'),
    ]
    for label, key in cost_cats:
        vals = []
        for s in scenario_names_list:
            if key == 'total_heat_cost':
                v = scenario_totals[s] / 1e6
            else:
                v = get_cat_value(s, key) / 1e6
            if key == 'total_heat_cost':
                vals.append(f"**{v:.2f}**")
            else:
                vals.append(f"{v:.2f}")
        md_lines.append(f"| {label} | " + " | ".join(vals) + " |")

    md_lines += [
        "",
        "## Heat Provision (GWh)",
        "",
    ]
    header = "| Source | " + " | ".join(ordered_display_names) + " |"
    md_lines.append(header)
    md_lines.append(sep)
    for label, key in [('Heat Pumps', 'heat_HP'), ('Resistive Heaters', 'heat_resistive'), ('CHP', 'heat_CHP')]:
        vals = [f"{results[s][key] / 1e6:.1f}" for s in scenario_names_list]
        md_lines.append(f"| {label} | " + " | ".join(vals) + " |")
    md_lines.append("")

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))
    print(f"Markdown exported to {md_path}")

    # Export HTML and PDF
    pdf_path = f"{output_base_path}.pdf"
    html_path = f"{output_base_path}.html"
    fig.write_html(html_path)
    print(f"Plot exported to {html_path}")
    try:
        fig.write_image(pdf_path, format="pdf", width=FIGURE_WIDTH, height=FIGURE_HEIGHT)
        print(f"Plot exported to {pdf_path}")
    except Exception as e:
        print(f"Warning: PDF export failed ({e}).")
    print(f"Markdown exported to {md_path}")


if __name__ == '__main__':
    main()