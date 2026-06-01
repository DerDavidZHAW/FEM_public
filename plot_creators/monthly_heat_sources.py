"""
Script to create monthly stacked bar charts showing provided heat
(Heat Pumps, Resistive Heaters, CHP) across scenarios.

genTh.csv contains thermal generation (MWh_th).
For heat pumps, genTh already represents the heat output (= electricity * COP),
so the values are used directly as heat provision.
For resistive heaters, COP = 1, so heat = electricity consumption.
For CHP, genTh is also the thermal output.
"""

import argparse
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
from pathlib import Path

pio.renderers.default = "browser"


def parse_args():
    parser = argparse.ArgumentParser(description="Monthly heat provision stacked bar charts.")
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
DEFAULT_SCENARIOS = [
    "2050_100_inv_EUbat",
    "2050_090_inv_EUbat",
    "2050_080_inv_EUbat",
    "2050_070_inv_EUbat",
    "2050_060_inv_EUbat",
    "2050_050_inv_EUbat",
    "2050_040_inv_EUbat",
    "2050_030_inv_EUbat",
]
DEFAULT_DISPLAY_NAMES = [
    "NTC 100%",
    "NTC 90%",
    "NTC 80%",
    "NTC 70%",
    "NTC 60%",
    "NTC 50%",
    "NTC 40%",
    "NTC 30%",
]
# ======================================================================


def main():
    args = parse_args()

    output_folder = args.output_folder or DEFAULT_OUTPUT_FOLDER
    scenario_names_list = args.scenarios or DEFAULT_SCENARIOS
    display_names = args.display_names or DEFAULT_DISPLAY_NAMES

    if len(scenario_names_list) != len(display_names):
        raise ValueError("scenarios and display names must have the same length")

    base_dir = Path(__file__).parent.parent
    output_base_dir = base_dir / "output" / output_folder

    # Build scenarios dict: display_name -> full path
    scenarios = {}
    for scen, disp in zip(scenario_names_list, display_names):
        scenarios[disp] = str(output_base_dir / scen)

    if args.output_base:
        output_base_path = Path(args.output_base)
    else:
        output_base_path = Path(__file__).parent / "monthly_heat_sources"
    output_base_path.parent.mkdir(parents=True, exist_ok=True)

    # Colors matching rh_hp_comparison.py pie charts
    colors = {
        'Heat Pumps': 'rgb(237,219,171)',       # beige (HP)
        'Resistive Heaters': 'rgb(150,150,150)', # grey
        'CHP': 'rgb(88,49,25)',                  # brown
    }
    plot_font_family = "Times New Roman"
    plot_font_size = 15

    # Month order (hydro year starts in October) - now only December and June
    month_order = ['dec', 'jun']
    all_months_for_table = ['oct', 'nov', 'dec', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep']

    # Read time mapping
    timemap_path = base_dir / "input" / "timemaps_hydro_year.csv"
    timemap_df = pd.read_csv(timemap_path)
    t_to_month = dict(zip(timemap_df['t'], timemap_df['month']))

    # Initialize storage for results
    results = {}

    for scenario_display, scenario_path in scenarios.items():
        print(f"\nProcessing scenario: {scenario_display}")

        genTh_df = pd.read_csv(f"{scenario_path}/genTh.csv")

        weights_df = pd.read_csv(f"{scenario_path}/weight_in_objective_fcn.csv")
        weights_dict = dict(zip(weights_df['Scenarios'], weights_df['value']))
        print(f"  Scenario weights: {weights_dict}")

        genTh_df['month'] = genTh_df['T'].map(t_to_month)

        # Initialize monthly results for all months (for table output)
        monthly_results = {month: {'HP': 0, 'resistive': 0, 'CHP': 0} for month in all_months_for_table}

        for plant in genTh_df['PDH'].unique():
            plant_data = genTh_df[genTh_df['PDH'] == plant].copy()

            # Check CHP BEFORE HP to avoid '_CHPNew' matching '_HPNew' substring
            is_chp = '_CHPNew' in plant or '_CHP' in plant
            is_hp = not is_chp and ('_HPNew' in plant or '_HPG' in plant)
            is_resistive = '_resistiveNew' in plant or 'resistive' in plant.lower()

            if is_chp:
                cat = 'CHP'
            elif is_hp:
                cat = 'HP'
            elif is_resistive:
                cat = 'resistive'
            else:
                continue

            # Normalize weights over the sub-scenarios available in this plant data
            # so monthly results are weighted averages across weather years.
            subscen_list = list(plant_data['Scenarios'].unique())
            raw_weights = {sub: weights_dict.get(sub, 0.0) for sub in subscen_list}
            raw_sum = sum(raw_weights.values())
            if raw_sum <= 0:
                norm_weights = {sub: 1.0 / len(subscen_list) for sub in subscen_list}
            else:
                norm_weights = {sub: w / raw_sum for sub, w in raw_weights.items()}

            for subscen in subscen_list:
                subscen_data = plant_data[plant_data['Scenarios'] == subscen]
                weight = norm_weights[subscen]
                # genTh values are thermal generation (heat provision) in MWh_th
                monthly_gen = subscen_data.groupby('month')['value'].sum() * weight
                for month, gen_value in monthly_gen.items():
                    if month in monthly_results:
                        monthly_results[month][cat] += gen_value

        results[scenario_display] = monthly_results

        print(f"\n  Monthly heat provision summary for {scenario_display} (GWh):")
        for month in all_months_for_table:
            hp = monthly_results[month]['HP'] / 1000
            rh = monthly_results[month]['resistive'] / 1000
            chp = monthly_results[month]['CHP'] / 1000
            print(f"    {month.upper()}: HP={hp:.1f}, RH={rh:.1f}, CHP={chp:.1f}")

    # ---- Build stacked bar chart figure ----
    scenario_keys = list(scenarios.keys())
    scenario_tick_labels = [label.replace("NTC ", "") for label in scenario_keys]

    # Two panels: all scenarios in December on the left, all scenarios in June on the right.
    fig = make_subplots(
        rows=1,
        cols=2,
        specs=[[{"type": "bar"}, {"type": "bar"}]],
        subplot_titles=["December", "June"],
        horizontal_spacing=0.1,
    )

    dec_hp = [results[sc]['dec']['HP'] / 1000 for sc in scenario_keys]
    dec_rh = [results[sc]['dec']['resistive'] / 1000 for sc in scenario_keys]
    dec_chp = [results[sc]['dec']['CHP'] / 1000 for sc in scenario_keys]

    jun_hp = [results[sc]['jun']['HP'] / 1000 for sc in scenario_keys]
    jun_rh = [results[sc]['jun']['resistive'] / 1000 for sc in scenario_keys]
    jun_chp = [results[sc]['jun']['CHP'] / 1000 for sc in scenario_keys]

    # Left panel: December (all scenarios)
    fig.add_trace(
        go.Bar(
            x=scenario_keys,
            y=dec_hp,
            name='Heat Pumps',
            marker_color=colors['Heat Pumps'],
            hovertemplate='Heat Pumps: %{y:.1f} GWh<sub>th</sub><extra></extra>',
            legendgroup='Heat Pumps',
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=scenario_keys,
            y=dec_rh,
            name='Resistive Heaters',
            marker_color=colors['Resistive Heaters'],
            hovertemplate='Resistive Heaters: %{y:.1f} GWh<sub>th</sub><extra></extra>',
            legendgroup='Resistive Heaters',
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=scenario_keys,
            y=dec_chp,
            name='CHP',
            marker_color=colors['CHP'],
            hovertemplate='CHP: %{y:.1f} GWh<sub>th</sub><extra></extra>',
            legendgroup='CHP',
        ),
        row=1,
        col=1,
    )

    # Right panel: June (all scenarios)
    fig.add_trace(
        go.Bar(
            x=scenario_keys,
            y=jun_hp,
            name='Heat Pumps',
            marker_color=colors['Heat Pumps'],
            hovertemplate='Heat Pumps: %{y:.1f} GWh<sub>th</sub><extra></extra>',
            legendgroup='Heat Pumps',
            showlegend=False,
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Bar(
            x=scenario_keys,
            y=jun_rh,
            name='Resistive Heaters',
            marker_color=colors['Resistive Heaters'],
            hovertemplate='Resistive Heaters: %{y:.1f} GWh<sub>th</sub><extra></extra>',
            legendgroup='Resistive Heaters',
            showlegend=False,
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Bar(
            x=scenario_keys,
            y=jun_chp,
            name='CHP',
            marker_color=colors['CHP'],
            hovertemplate='CHP: %{y:.1f} GWh<sub>th</sub><extra></extra>',
            legendgroup='CHP',
            showlegend=False,
        ),
        row=1,
        col=2,
    )

    fig.update_yaxes(title_text="Provided heat (GWh<sub>th</sub>)", range=[0, 900], row=1, col=1)
    fig.update_yaxes(title_text="Provided heat (GWh<sub>th</sub>)", range=[0, 900], row=1, col=2)
    fig.update_xaxes(
        title_text="NTC",
        tickvals=scenario_keys,
        ticktext=scenario_tick_labels,
        tickangle=-35,
        row=1,
        col=1,
    )
    fig.update_xaxes(
        title_text="NTC",
        tickvals=scenario_keys,
        ticktext=scenario_tick_labels,
        tickangle=-35,
        row=1,
        col=2,
    )
    fig.update_annotations(font=dict(size=plot_font_size + 2))

    fig.update_layout(
        height=720,
        width=1890,
        template='plotly_white',
        barmode='stack',
        font=dict(family=plot_font_family, size=plot_font_size),
        legend=dict(
            orientation="h", yanchor="top", y=-0.25,
            xanchor="center", x=0.5, font=dict(size=plot_font_size),
        ),
        margin=dict(l=80, r=20, t=45, b=120),
    )

    # Show plot (only when running standalone / in browser)
    fig.show()

    # ---- Write markdown description (before image export to ensure it's always produced) ----
    md_path = f"{output_base_path}.md"
    md_lines = [
        "# Monthly Heat Provision (December & June)",
        "",
        "This plot shows the monthly heat provision breakdown (GWh<sub>th</sub>) by source: "
        "Heat Pumps, Resistive Heaters, and CHP (combined heat and power) for December and June.",
        "",
        "Only December and June are shown in the plots.",
        "Any interpretation and narrative should focus on these two months.",
        "",
        "Heat pump values represent thermal output (electricity × COP).",
        "Resistive heater values equal electricity consumption (COP = 1).",
        "CHP values represent thermal co-generation output.",
        "",
    ]
    for scenario_display, monthly_data in results.items():
        md_lines.append(f"## {scenario_display}")
        md_lines.append("")
        md_lines.append("| Month | Heat Pumps (GWh<sub>th</sub>) | Resistive Heaters (GWh<sub>th</sub>) | CHP (GWh<sub>th</sub>) | Total (GWh<sub>th</sub>) |")
        md_lines.append("|-------|-----------------|------------------------|-----------|-------------|")
        annual_hp, annual_rh, annual_chp = 0, 0, 0
        for month in all_months_for_table:
            hp = monthly_data[month]['HP'] / 1000
            rh = monthly_data[month]['resistive'] / 1000
            chp = monthly_data[month]['CHP'] / 1000
            total = hp + rh + chp
            annual_hp += hp
            annual_rh += rh
            annual_chp += chp
            md_lines.append(f"| {month.upper()} | {hp:.1f} | {rh:.1f} | {chp:.1f} | {total:.1f} |")
        annual_total = annual_hp + annual_rh + annual_chp
        md_lines.append(f"| **Annual** | **{annual_hp:.1f}** | **{annual_rh:.1f}** | **{annual_chp:.1f}** | **{annual_total:.1f}** |")
        md_lines.append("")

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))
    print(f"Markdown exported to {md_path}")

    # Export HTML and PDF
    html_path = f"{output_base_path}.html"
    pdf_path = f"{output_base_path}.pdf"
    fig.write_html(html_path)
    print(f"Plot exported to {html_path}")
    try:
        fig.write_image(pdf_path, format="pdf")
        print(f"Plot exported to {pdf_path}")
    except Exception as e:
        print(f"Warning: PDF export failed ({e}). HTML was exported successfully.")


if __name__ == '__main__':
    main()
