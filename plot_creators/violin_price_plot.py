import argparse
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

# Plotly im Browser öffnen
pio.renderers.default = "browser"


def parse_args():
    parser = argparse.ArgumentParser(description="Violin plot of electricity prices.")
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
    parser.add_argument(
        "--weather-year", default=None,
        help="Weather year to filter (defaults to DEFAULT_WEATHER_YEAR).",
    )
    parser.add_argument(
        "--node", default=None,
        help="Node to filter (defaults to DEFAULT_NODE).",
    )
    return parser.parse_args()


# ========== DEFAULT CONFIGURATION (for standalone execution) ==========
DEFAULT_OUTPUT_FOLDER = "20260311"
DEFAULT_WEATHER_YEAR = "wy2008"
DEFAULT_NODE = "CH00"

year = "2035"  # Choose: "2035" or "2050"

DEFAULT_SCENARIOS = [
    f"{year}_100_inv_EUbat",
    f"{year}_090_inv_EUbat",
    f"{year}_080_inv_EUbat",
    f"{year}_070_inv_EUbat",
    f"{year}_060_inv_EUbat",
    f"{year}_050_inv_EUbat",
    f"{year}_040_inv_EUbat",
    f"{year}_030_inv_EUbat",
]
DEFAULT_DISPLAY_NAMES = [
    "NTC 100", "NTC 90", "NTC 80", "NTC 70",
    "NTC 60", "NTC 50", "NTC 40", "NTC 30",
]
# ======================================================================

# Y-Achsen-Bereich für den Plot (None = automatisch)
Y_MIN = None
Y_MAX = None
PLOT_FONT_FAMILY = "Times New Roman"
FONT_SIZE_BASE = 28
TITLE_FONT_SIZE = FONT_SIZE_BASE + 4
SUBPLOT_TITLE_FONT_SIZE = FONT_SIZE_BASE + 2
TICK_FONT_SIZE = FONT_SIZE_BASE - 2
SUBPLOT_VERTICAL_GAP = 0.24


def main():
    args = parse_args()

    output_folder = args.output_folder or DEFAULT_OUTPUT_FOLDER
    WEATHER_YEAR = args.weather_year or DEFAULT_WEATHER_YEAR
    NODE = args.node or DEFAULT_NODE
    scenarios_list = args.scenarios or DEFAULT_SCENARIOS
    display_names = args.display_names or DEFAULT_DISPLAY_NAMES

    if len(scenarios_list) != len(display_names):
        raise ValueError("scenarios and display names must have the same length")

    base_dir = Path(__file__).parent.parent
    BASE_PATH = base_dir / "output" / output_folder

    scenario_labels = dict(zip(scenarios_list, display_names))

    if args.output_base:
        output_base_path = Path(args.output_base)
    else:
        output_base_path = base_dir / "plots" / f"violin_plot_{NODE}_{WEATHER_YEAR}"
    output_base_path.parent.mkdir(parents=True, exist_ok=True)

    all_data = []

    for scenario in scenarios_list:
        file_path = BASE_PATH / scenario / "energy_balance_dual.csv"
        settings_path = BASE_PATH / scenario / "settings.csv"

        if file_path.exists():
            df = pd.read_csv(file_path)

            weight = 1.0
            if settings_path.exists():
                settings_df = pd.read_csv(settings_path)
                weight_row = settings_df[settings_df["Item"] == "weight_in_objective_fcn"]
                if not weight_row.empty:
                    for col in settings_df.columns:
                        if WEATHER_YEAR in col:
                            weight = float(weight_row[col].values[0])
                            break

            df_filtered = df[
                (df["Node"] == NODE) &
                (df["Scenarios"].str.contains(WEATHER_YEAR))
            ].copy()

            df_filtered["value"] = df_filtered["value"] / weight
            df_filtered["Scenario"] = scenario
            all_data.append(df_filtered[["Scenario", "T", "value"]])
            print(f"{scenario}: weight for {WEATHER_YEAR} = {weight}")
        else:
            print(f"Warning: {file_path} not found!")

    df_combined = pd.concat(all_data, ignore_index=True)
    df_combined["T_num"] = df_combined["T"].str.extract(r"t_(\d+)").astype(int)
    df_combined["Season"] = df_combined["T_num"].apply(
        lambda t: "Winter" if (1 <= t <= 2184) or (6553 <= t <= 8760) else "Sommer"
    )

    df_winter = df_combined[df_combined["Season"] == "Winter"]
    df_summer = df_combined[df_combined["Season"] == "Sommer"]

    data_min = df_combined["value"].min()
    data_max = df_combined["value"].max()
    data_range = data_max - data_min
    plot_min = data_min - 0.05 * data_range
    plot_max = data_max + 0.05 * data_range

    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Winter', 'Summer'),
        vertical_spacing=SUBPLOT_VERTICAL_GAP,
        row_heights=[0.5, 0.5]
    )

    for scenario in scenarios_list:
        scenario_data = df_winter[df_winter["Scenario"] == scenario]["value"]
        fig.add_trace(
            go.Violin(
                y=scenario_data,
                name=scenario_labels[scenario],
                x=[scenario_labels[scenario]] * len(scenario_data),
                box_visible=True,
                meanline_visible=True,
                showlegend=False,
                scalemode="width",
                width=0.8,
                legendgroup=scenario,
            ),
            row=1,
            col=1,
        )

    for scenario in scenarios_list:
        scenario_data = df_summer[df_summer["Scenario"] == scenario]["value"]
        fig.add_trace(
            go.Violin(
                y=scenario_data,
                name=scenario_labels[scenario],
                x=[scenario_labels[scenario]] * len(scenario_data),
                box_visible=True,
                meanline_visible=True,
                showlegend=False,
                scalemode="width",
                width=0.8,
                legendgroup=scenario,
            ),
            row=2,
            col=1,
        )

    layout_size = 24

    fig.update_layout(
        width=1400, height=800,
        hovermode='closest', violinmode='overlay',
        showlegend=False,
        font=dict(family=PLOT_FONT_FAMILY, size=FONT_SIZE_BASE),
        title_font=dict(family=PLOT_FONT_FAMILY, size=TITLE_FONT_SIZE)
    )

    fig.update_annotations(font=dict(family=PLOT_FONT_FAMILY, size=SUBPLOT_TITLE_FONT_SIZE))

    fig.update_xaxes(title_text="Scenario", row=2, col=1, tickangle=-45,
                     title_font=dict(family=PLOT_FONT_FAMILY, size=FONT_SIZE_BASE),
                     tickfont=dict(family=PLOT_FONT_FAMILY, size=TICK_FONT_SIZE))
    fig.update_xaxes(tickangle=-45, row=1, col=1,
                     tickfont=dict(family=PLOT_FONT_FAMILY, size=TICK_FONT_SIZE))

    for row in [1, 2]:
        fig.update_yaxes(title_text="Price [CHF/MWh]", row=row, col=1,
                         title_font=dict(family=PLOT_FONT_FAMILY, size=FONT_SIZE_BASE),
                         tickfont=dict(family=PLOT_FONT_FAMILY, size=TICK_FONT_SIZE))
        if Y_MIN is not None or Y_MAX is not None:
            fig.update_yaxes(
                range=[
                    Y_MIN if Y_MIN is not None else plot_min,
                    Y_MAX if Y_MAX is not None else plot_max,
                ],
                row=row,
                col=1,
            )
        else:
            fig.update_yaxes(range=[plot_min, plot_max], row=row, col=1)

    fig.show()

    md_path = f"{output_base_path}.md"
    percentile_specs = [
        (0.05, "P5"),
        (0.10, "P10"),
        (0.20, "P20"),
        (0.30, "P30"),
        (0.40, "P40"),
        (0.50, "P50"),
        (0.60, "P60"),
        (0.70, "P70"),
        (0.80, "P80"),
        (0.90, "P90"),
        (0.95, "P95"),
    ]
    md_lines = [
        f"# Violin Plot of Electricity Prices at {NODE} ({WEATHER_YEAR})",
        "",
        "This plot shows the distribution of electricity prices (CHF/MWh) "
        "for different scenarios, split by season (Winter: Oct-Mar + Jul-Sep, "
        "Summer: Apr-Jun).",
        "",
        "## Winter Statistics",
        "",
        "| Scenario | Mean | Median | Std | P5 | P10 | P20 | P30 | P40 | P50 | P60 | P70 | P80 | P90 | P95 | Min | Max |",
        "|----------|------|--------|-----|----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|",
    ]
    for scenario in scenarios_list:
        s_data = df_winter[df_winter["Scenario"] == scenario]["value"]
        if len(s_data) > 0:
            percentile_values = " | ".join(
                f"{s_data.quantile(q):.1f}" for q, _ in percentile_specs
            )
            md_lines.append(
                f"| {scenario_labels[scenario]} | {s_data.mean():.1f} | {s_data.median():.1f} "
                f"| {s_data.std():.1f} | {percentile_values} | {s_data.min():.1f} | {s_data.max():.1f} |"
            )
    md_lines += [
        "",
        "## Summer Statistics",
        "",
        "| Scenario | Mean | Median | Std | P5 | P10 | P20 | P30 | P40 | P50 | P60 | P70 | P80 | P90 | P95 | Min | Max |",
        "|----------|------|--------|-----|----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|",
    ]
    for scenario in scenarios_list:
        s_data = df_summer[df_summer["Scenario"] == scenario]["value"]
        if len(s_data) > 0:
            percentile_values = " | ".join(
                f"{s_data.quantile(q):.1f}" for q, _ in percentile_specs
            )
            md_lines.append(
                f"| {scenario_labels[scenario]} | {s_data.mean():.1f} | {s_data.median():.1f} "
                f"| {s_data.std():.1f} | {percentile_values} | {s_data.min():.1f} | {s_data.max():.1f} |"
            )
    md_lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"Markdown exported to {md_path}")

    pdf_path = f"{output_base_path}.pdf"
    html_path = f"{output_base_path}.html"
    png_path = f"{output_base_path}.png"

    fig.write_html(html_path)
    print(f"Plot exported to {html_path}")
    try:
        fig.write_image(pdf_path, format="pdf", width=1400, height=880)
        print(f"Plot exported to {pdf_path}")
    except Exception as e:
        print(f"Warning: PDF export failed ({e}).")
    try:
        fig.write_image(png_path, width=1400, height=880, scale=3)
        from PIL import Image

        img = Image.open(png_path)
        crop_top = 200
        cropped_img = img.crop((0, crop_top, img.width, img.height))
        cropped_img.save(png_path)
        print(f"Plot exported to {png_path} (cropped top {crop_top}px)")
    except Exception as e:
        print(f"Warning: PNG export failed ({e}).")

    print(f"\n=== Statistiken für {NODE} - {WEATHER_YEAR} ===")
    print("\n--- WINTER ---")
    print(df_winter.groupby("Scenario")["value"].describe())
    print("\n--- SOMMER ---")
    print(df_summer.groupby("Scenario")["value"].describe())


if __name__ == '__main__':
    main()
