"""
Plot electricity price and heating electricity demand (HP and resistive) in a
summer window for selected scenarios.

Outputs: HTML, PNG, PDF, and Markdown.
"""

import argparse
from pathlib import Path
import sys

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

# Ensure project-root imports work when running this script directly.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import utils.utilities_visualization as util_vis

pio.renderers.default = "browser"


# ========== DEFAULT CONFIGURATION (for standalone execution) ==========
DEFAULT_OUTPUT_FOLDER = "20260311"
DEFAULT_WEATHER_YEAR = "wy2008"
DEFAULT_TARGET_NODE = "CH00"
DEFAULT_START_MONTH_DAY = "07-01"
DEFAULT_END_MONTH_DAY = "07-14"
DEFAULT_SCENARIOS = [
    "2050_100_inv_EUbat",
    "2035_030_inv_EUbat",
    "2035_100_inv_EUbat",
    "2050_030_inv_EUbat",
]
DEFAULT_DISPLAY_NAMES = [
    "2050 NTC 100%",
    "2035 NTC 30%",
    "2035 NTC 100%",
    "2050 NTC 30%",
]
DEFAULT_OUTPUT_STEM = "summer_price_heat_window_core_scenarios"

# Plot style controls
PLOT_FONT_FAMILY = "Times New Roman"
# Change this one value to scale plot text up/down globally.
FONT_SIZE_BASE = 18
FONT_SIZE_SUBPLOT_TITLE = FONT_SIZE_BASE + 2
FONT_SIZE_AXIS_TITLE = FONT_SIZE_BASE
FONT_SIZE_TICK = FONT_SIZE_BASE - 2
FONT_SIZE_LEGEND = FONT_SIZE_BASE - 1

PLOT_MARGIN_LEFT = 80
PLOT_MARGIN_RIGHT = 45
PLOT_MARGIN_TOP = 55
PLOT_MARGIN_BOTTOM = 65
# ======================================================================


def parse_args():
    parser = argparse.ArgumentParser(
        description="Plot electricity price and HP/resistive demand in a summer window."
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        help="Scenario folder names under output/{output-folder} (defaults to core scenarios).",
    )
    parser.add_argument(
        "--display-names",
        nargs="+",
        help="Display names matching scenarios order (defaults to core scenario labels).",
    )
    parser.add_argument(
        "--output-base",
        help="Output path without extension for HTML/PNG/PDF/MD (defaults to local plot_creators output).",
    )
    parser.add_argument(
        "--output-folder",
        default=DEFAULT_OUTPUT_FOLDER,
        help=f"Date folder under output/ (default: {DEFAULT_OUTPUT_FOLDER}).",
    )
    parser.add_argument(
        "--weather-year",
        default=DEFAULT_WEATHER_YEAR,
        help=f"Weather-year suffix, e.g. wy2008 or 2008 (default: {DEFAULT_WEATHER_YEAR}).",
    )
    parser.add_argument(
        "--target-node",
        default=DEFAULT_TARGET_NODE,
        help=f"Node used for electricity price series (default: {DEFAULT_TARGET_NODE}).",
    )
    parser.add_argument(
        "--start-month-day",
        default=DEFAULT_START_MONTH_DAY,
        help=f"Window start in MM-DD format (default: {DEFAULT_START_MONTH_DAY}).",
    )
    parser.add_argument(
        "--end-month-day",
        default=DEFAULT_END_MONTH_DAY,
        help=f"Window end in MM-DD format (default: {DEFAULT_END_MONTH_DAY}).",
    )
    return parser.parse_args()


def normalize_weather_year(weather_year: str) -> str:
    token = weather_year.strip()
    if token.lower().startswith("wy"):
        return token
    return f"wy{token}"


def get_timestamp_map(t_values):
    # Keep consistency with existing visualization utilities.
    return util_vis.hour_to_timestamp(t_values, year=2035)


def build_time_window(start_month_day: str, end_month_day: str):
    start = pd.Timestamp(year=2035, month=int(start_month_day[:2]), day=int(start_month_day[3:]), hour=0)
    end = pd.Timestamp(year=2035, month=int(end_month_day[:2]), day=int(end_month_day[3:]), hour=23)
    if end < start:
        raise ValueError("end-month-day must be >= start-month-day in this script")
    return start, end


def load_scenario_series(scenario_dir: Path, subscenario: str, target_node: str):
    storage_charge = pd.read_csv(scenario_dir / "storage_charge.csv")
    prices = pd.read_csv(scenario_dir / "energy_balance_dual.csv")

    storage_charge = storage_charge[storage_charge["Scenarios"] == subscenario].copy()
    prices = prices[(prices["Scenarios"] == subscenario) & (prices["Node"] == target_node)].copy()

    if storage_charge.empty:
        raise ValueError(f"No storage_charge data for subscenario {subscenario}")
    if prices.empty:
        raise ValueError(f"No price data for node {target_node} and subscenario {subscenario}")

    hp_mask = storage_charge["P_pumping"].str.contains(r"_HPNew|_HPG|heat_pump", case=False, regex=True)
    rh_mask = storage_charge["P_pumping"].str.contains(r"resistive", case=False, regex=True)

    hp_series = storage_charge[hp_mask].groupby("T")["value"].sum()
    rh_series = storage_charge[rh_mask].groupby("T")["value"].sum()
    price_series = prices.groupby("T")["value"].mean()

    t_values = sorted(set(hp_series.index).union(set(rh_series.index)).union(set(price_series.index)))
    t_map = get_timestamp_map(t_values)

    hp_series.index = [t_map[t] for t in hp_series.index]
    rh_series.index = [t_map[t] for t in rh_series.index]
    price_series.index = [t_map[t] for t in price_series.index]

    hp_series = hp_series.sort_index()
    rh_series = rh_series.sort_index()
    price_series = price_series.sort_index()

    return hp_series, rh_series, price_series


def build_figure_for_year(year_label: str, items, window_start, window_end, hp_color, rh_color, price_color):
    fig = make_subplots(
        rows=len(items),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.09,
        subplot_titles=[item["display"] for item in items],
        specs=[[{"secondary_y": True}] for _ in items],
    )

    max_demand = 0.0
    max_price = 0.0
    for item in items:
        if not item["hp"].empty:
            max_demand = max(max_demand, float(item["hp"].max()))
        if not item["rh"].empty:
            max_demand = max(max_demand, float(item["rh"].max()))
        if not item["price"].empty:
            max_price = max(max_price, float(item["price"].max()))

    demand_range = [0, max(1.0, max_demand * 1.08)]
    price_range = [0, max(1.0, max_price * 1.08)]

    for idx, item in enumerate(items, start=1):
        hp = item["hp"]
        rh = item["rh"]
        price = item["price"]

        fig.add_trace(
            go.Scatter(
                x=hp.index,
                y=hp.values,
                mode="lines",
                name="Heat pump demand",
                line=dict(color=hp_color, width=2),
                showlegend=(idx == 1),
            ),
            row=idx,
            col=1,
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=rh.index,
                y=rh.values,
                mode="lines",
                name="Resistive heater demand",
                line=dict(color=rh_color, width=2),
                showlegend=(idx == 1),
            ),
            row=idx,
            col=1,
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=price.index,
                y=price.values,
                mode="lines",
                name="Electricity price",
                line=dict(color=price_color, width=2, dash="dot"),
                showlegend=(idx == 1),
            ),
            row=idx,
            col=1,
            secondary_y=True,
        )

        # Keep both subplots in each figure on identical scales.
        fig.update_yaxes(
            title_text="Demand<br>[MW]",
            range=demand_range,
            nticks=5,
            title_font=dict(family=PLOT_FONT_FAMILY, size=FONT_SIZE_AXIS_TITLE),
            tickfont=dict(family=PLOT_FONT_FAMILY, size=FONT_SIZE_TICK),
            row=idx,
            col=1,
            secondary_y=False,
        )
        fig.update_yaxes(
            title_text="Price<br>[CHF/MWh]",
            range=price_range,
            nticks=5,
            title_font=dict(family=PLOT_FONT_FAMILY, size=FONT_SIZE_AXIS_TITLE),
            tickfont=dict(family=PLOT_FONT_FAMILY, size=FONT_SIZE_TICK),
            row=idx,
            col=1,
            secondary_y=True,
        )

    fig.update_xaxes(
        range=[window_start, window_end],
        tickfont=dict(family=PLOT_FONT_FAMILY, size=FONT_SIZE_TICK),
        title_font=dict(family=PLOT_FONT_FAMILY, size=FONT_SIZE_AXIS_TITLE),
    )
    fig.update_layout(
        # title=f"Price and Heating Demand ({year_label})",
        template="plotly_white",
        height=max(700, 320 * len(items)),
        width=1650,
        font=dict(family=PLOT_FONT_FAMILY, size=FONT_SIZE_BASE),
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=1.07,
            yanchor="bottom",
            font=dict(family=PLOT_FONT_FAMILY, size=FONT_SIZE_LEGEND),
        ),
        margin=dict(
            l=PLOT_MARGIN_LEFT,
            r=PLOT_MARGIN_RIGHT,
            t=PLOT_MARGIN_TOP,
            b=PLOT_MARGIN_BOTTOM,
        ),
    )
    fig.update_annotations(font=dict(family=PLOT_FONT_FAMILY, size=FONT_SIZE_SUBPLOT_TITLE))
    return fig


def main():
    args = parse_args()

    if args.scenarios:
        scenarios = args.scenarios
        display_names = args.display_names or args.scenarios
    else:
        scenarios = DEFAULT_SCENARIOS
        display_names = args.display_names or DEFAULT_DISPLAY_NAMES

    if len(scenarios) != len(display_names):
        raise ValueError("scenarios and display-names must have same length")

    weather_year = normalize_weather_year(args.weather_year)
    window_start, window_end = build_time_window(args.start_month_day, args.end_month_day)

    base_dir = Path(__file__).parent.parent
    output_root = base_dir / "output" / args.output_folder
    if args.output_base:
        output_base = Path(args.output_base)
    else:
        output_base = Path(__file__).parent / DEFAULT_OUTPUT_STEM
    output_base.parent.mkdir(parents=True, exist_ok=True)

    hp_color = util_vis.dispatch_color_mapping["heat_pump demand"]
    rh_color = util_vis.dispatch_color_mapping["resistive_heater demand"]
    price_color = util_vis.dispatchDH_color_mapping["Price - Electricity"]

    scenario_data = []

    for scenario_name, display_name in zip(scenarios, display_names):
        scenario_dir = output_root / scenario_name
        subscenario = f"{scenario_name}_{weather_year}"

        hp_series, rh_series, price_series = load_scenario_series(
            scenario_dir=scenario_dir,
            subscenario=subscenario,
            target_node=args.target_node,
        )

        hp_window = hp_series[(hp_series.index >= window_start) & (hp_series.index <= window_end)]
        rh_window = rh_series[(rh_series.index >= window_start) & (rh_series.index <= window_end)]
        price_window = price_series[(price_series.index >= window_start) & (price_series.index <= window_end)]

        scenario_data.append(
            {
                "scenario": scenario_name,
                "display": display_name,
                "hp": hp_window,
                "rh": rh_window,
                "price": price_window,
            }
        )

    grouped = {}
    for item in scenario_data:
        year = item["scenario"][0:4]
        grouped.setdefault(year, []).append(item)

    exported_files = []
    for year in sorted(grouped.keys()):
        fig = build_figure_for_year(
            year_label=year,
            items=grouped[year],
            window_start=window_start,
            window_end=window_end,
            hp_color=hp_color,
            rh_color=rh_color,
            price_color=price_color,
        )

        fig.show()

        html_path = f"{output_base}_{year}.html"
        png_path = f"{output_base}_{year}.png"
        pdf_path = f"{output_base}_{year}.pdf"

        fig.write_html(html_path)
        print(f"Plot exported to {html_path}")
        exported_files.append(html_path)

        try:
            fig.write_image(png_path, format="png", scale=2)
            print(f"Plot exported to {png_path}")
            exported_files.append(png_path)
        except Exception as exc:
            print(f"Warning: PNG export failed ({exc}).")

        try:
            fig.write_image(pdf_path, format="pdf")
            print(f"Plot exported to {pdf_path}")
            exported_files.append(pdf_path)
        except Exception as exc:
            print(f"Warning: PDF export failed ({exc}).")

    md_path = f"{output_base}.md"

    md_lines = [
        "# Electricity Price and Heating Demand Window",
        "",
        f"Weather year analyzed: **{weather_year}**",
        f"Time window: **{args.start_month_day} to {args.end_month_day}**",
        "Figures are split by year (2035 and 2050), each with two subplots.",
        "Within each year-figure, the two subplots use identical demand and price axis ranges.",
        "",
        "Each subplot overlays:",
        "- Electricity price (CHF/MWh)",
        "- Heat pump electricity demand (MW)",
        "- Resistive heater electricity demand (MW)",
        "",
        "Interpretation goal:",
        "- Compare whether higher summer prices coincide with stronger resistive-heater demand concentrated in low/zero-price hours.",
        "- Compare whether lower summer-price scenarios rely more on continuous heat-pump demand with less need for resistive operation.",
        "",
        "Scenarios shown:",
    ]

    for year in sorted(grouped.keys()):
        md_lines.append("")
        md_lines.append(f"## {year}")
        for item in grouped[year]:
            md_lines.append(f"- {item['display']} ({item['scenario']})")

    md_lines.append("")
    md_lines.append("Generated files:")
    for out_file in exported_files:
        md_lines.append(f"- {out_file}")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"Markdown exported to {md_path}")


if __name__ == "__main__":
    main()
