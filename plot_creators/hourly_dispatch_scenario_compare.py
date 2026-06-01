"""
Compare dispatch composition at one selected hour across multiple scenarios.

The script builds one horizontal bar subplot per scenario, using the same data basis
as visualization_class.py dispatch logic:
- generation by technology (positive)
- infeed (positive)
- imports/exports (positive/negative)
- flexible demand by technology (negative)
- inflexible demand (negative)
- EV/HP inflexible demand (negative)

Ordering around the center (x=0):
1) Near center: non-trade, non-storage technologies.
2) Farther away: storage/trade entries sorted by their costs:
   - trade: foreign nodal prices
   - storage: storage opportunity cost (soc dual)

Swiss electricity price is shown at the center label.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import sys

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from visualization.get_mappings import get_mappings
from visualization.import_gen_dem_ts import import_gen_demand_timeseries
from visualization.map_ts import map_gen_dem_timeseries
from utils.utilities_visualization import hour_to_timestamp

pio.renderers.default = "browser"


DEFAULT_SCENARIO_DIRS = [
    r"C:\Models\Future_Markets\output\20260311\2035_100_070_EUbat",
    r"C:\Models\Future_Markets\output\20260311\2035_080_070_EUbat",
    r"C:\Models\Future_Markets\output\20260311\2035_030_070_EUbat",
]
DEFAULT_DISPLAY_NAMES = [
    "NTC 100 / Inv 70",
    "NTC 80 / Inv 70",
    "NTC 30 / Inv 70",
]
DEFAULT_TARGET_NODE = "CH00"
DEFAULT_DATE = "05.06"
DEFAULT_HOUR = 0
DEFAULT_WEATHER_YEAR = "wy2008"


@dataclass
class ScenarioResult:
    display_name: str
    items: list[dict[str, Any]]
    ch_price: float
    timestep_label: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare one-hour dispatch bars across scenarios."
    )
    parser.add_argument(
        "--scenario-dirs",
        nargs="+",
        default=DEFAULT_SCENARIO_DIRS,
        help="Scenario output directories.",
    )
    parser.add_argument(
        "--display-names",
        nargs="+",
        default=DEFAULT_DISPLAY_NAMES,
        help="Display names for subplots (same order as --scenario-dirs).",
    )
    parser.add_argument(
        "--target-node",
        default=DEFAULT_TARGET_NODE,
        help="Target electricity node (default: CH00).",
    )
    parser.add_argument(
        "--date",
        default=DEFAULT_DATE,
        help="Day and month as DD.MM (default: 05.06).",
    )
    parser.add_argument(
        "--hour",
        type=int,
        default=DEFAULT_HOUR,
        help="Hour in day 0..23 (default: 0).",
    )
    parser.add_argument(
        "--weather-year",
        default=DEFAULT_WEATHER_YEAR,
        help="Subscenario weather year suffix (e.g. wy2008).",
    )
    parser.add_argument(
        "--output-base",
        default=str(Path(__file__).parent / "hourly_dispatch_scenario_compare"),
        help="Output path without extension (html/pdf).",
    )
    return parser.parse_args()


def parse_line_nodes(line_name: str) -> tuple[str | None, str | None]:
    parts = str(line_name).split("_")
    if len(parts) < 3:
        return None, None
    return parts[-2], parts[-1]


def pick_subscenario(scenario_dir: Path, weather_year: str) -> str:
    gen_path = scenario_dir / "gen.csv"
    gen = pd.read_csv(gen_path)
    if "Scenarios" not in gen.columns:
        return scenario_dir.name

    scenarios = sorted(gen["Scenarios"].dropna().unique().tolist())
    if weather_year:
        matches = [s for s in scenarios if weather_year in s]
        if matches:
            return matches[0]

    return scenarios[0]


def timestep_from_timemap(base_dir: Path, day_month: str, hour: int) -> str:
    day_str, month_str = day_month.split(".")
    day = int(day_str)
    month = int(month_str)
    day_of_year = pd.Timestamp(year=2035, month=month, day=day).dayofyear

    month_map = {
        1: "jan",
        2: "feb",
        3: "mar",
        4: "apr",
        5: "may",
        6: "jun",
        7: "jul",
        8: "aug",
        9: "sep",
        10: "oct",
        11: "nov",
        12: "dec",
    }

    timemap = pd.read_csv(base_dir / "input" / "timemaps_hydro_year.csv")
    hit = timemap[
        (timemap["day"] == f"day_{day_of_year}")
        & (timemap["month"] == month_map[month])
        & (timemap["hour_in_day"] == f"hid_{hour + 1}")
    ]
    if hit.empty:
        raise ValueError(f"Could not map {day_month} hour {hour:02d} to model timestep")

    return str(hit.iloc[0]["t"])


def classify_storage_tech(tech: str) -> bool:
    tech_l = tech.lower()
    return any(k in tech_l for k in ["battery", "psp", "dam", "v2g"])


def is_wind_pv_ror_tech(tech: str) -> bool:
    tech_l = tech.lower()
    return any(k in tech_l for k in ["wind", "pv", "pvrf", "ror"])


def weighted_mean(values: list[float], weights: list[float]) -> float | None:
    valid = [(v, w) for v, w in zip(values, weights) if pd.notna(v) and w > 0]
    if not valid:
        return None
    num = sum(v * w for v, w in valid)
    den = sum(w for _, w in valid)
    if den == 0:
        return None
    return num / den


def fmt_with_cost(base: str, cost: float | None) -> str:
    if cost is None or pd.isna(cost):
        return base
    return f"{base} ({cost:.0f})"


def build_scenario_items(
    base_dir: Path,
    scenario_dir: Path,
    display_name: str,
    target_node: str,
    weather_year: str,
    timestep: str,
) -> ScenarioResult:
    output_dir = str(scenario_dir) + "/"
    scenario_name = pick_subscenario(scenario_dir, weather_year)

    (
        generation_all,
        demand_inflx_all,
        demand_flxbl_all,
        export_all,
        soc_all,
        price_all,
        soc_dual_all,
        socth_dual_all,
        lostload_all,
        infeed_all,
        curtailment_all,
        withdrawal_all,
        injection_all,
        supplyTH_all,
        consumptionDH_all,
        curtailmentTH_all,
        storageTH_all,
        socTH_all,
        th_sl_all,
        BA_th_lim,
        v2g_outflow_all,
        priceTh_all,
        EV_inflexible_demand_all,
        HP_inflexible_demand_all,
    ) = import_gen_demand_timeseries(output_dir, scenario_name)

    (
        Map_node_plant,
        Map_node_consumer,
        Map_node_exportinglineATC,
        Map_node_importinglineATC,
        Map_plant_tech,
        Map_nodeDH_plantDH,
        Map_plantDH_tech,
    ) = get_mappings(output_dir)

    (
        plant_list,
        demand_inflx_list,
        demand_flxbl_list,
        exportATC_list,
        importATC_list,
        plant_with_soc,
    ) = map_gen_dem_timeseries(
        target_node,
        generation_all,
        demand_inflx_all,
        demand_flxbl_all,
        export_all,
        soc_all,
        Map_node_plant,
        Map_node_consumer,
        Map_node_exportinglineATC,
        Map_node_importinglineATC,
    )

    ts = hour_to_timestamp([timestep], year=2035)[timestep]

    # Raw price table for per-country labels.
    energy_dual = pd.read_csv(scenario_dir / "energy_balance_dual.csv")
    settings = pd.read_csv(scenario_dir / "settings.csv", index_col=0)
    weight_value = settings.loc["weight_in_objective_fcn", scenario_name]
    weight = float(pd.to_numeric(weight_value))
    energy_dual = energy_dual[energy_dual["Scenarios"] == scenario_name].copy()
    energy_dual["value"] = energy_dual["value"] / weight
    price_by_node_t = energy_dual[energy_dual["T"] == timestep].set_index("Node")["value"].to_dict()

    ch_price = float(price_by_node_t.get(target_node, 0.0))

    items: list[dict[str, Any]] = []
    grouped_inflex_demand = 0.0
    grouped_wind_pv_ror_supply = 0.0

    # Negative demand side from flexible demand by technology.
    demand_by_tech: dict[str, float] = {}
    demand_tech_plants: dict[str, list[str]] = {}
    for plant in demand_flxbl_list:
        if plant not in demand_flxbl_all.index:
            continue
        tech_list = Map_plant_tech.get(plant, [])
        if not tech_list:
            continue
        tech = str(tech_list[0])
        val = float(demand_flxbl_all.loc[plant, ts])
        if abs(val) < 1e-9:
            continue
        demand_by_tech[tech] = demand_by_tech.get(tech, 0.0) + val
        demand_tech_plants.setdefault(tech, []).append(plant)

    # Positive generation side by technology.
    gen_by_tech: dict[str, float] = {}
    gen_tech_plants: dict[str, list[str]] = {}
    for plant in plant_list:
        if plant not in generation_all.index:
            continue
        tech_list = Map_plant_tech.get(plant, [])
        if not tech_list:
            continue
        tech = str(tech_list[0])
        val = float(generation_all.loc[plant, ts])
        if abs(val) < 1e-9:
            continue
        gen_by_tech[tech] = gen_by_tech.get(tech, 0.0) + val
        gen_tech_plants.setdefault(tech, []).append(plant)

    # Inflexible demand (same core variable used in dispatch plot).
    inflex_key = (f"{target_node}_fixedconsumer", "fixed")
    if inflex_key in demand_inflx_all.index:
        inflex_val = float(demand_inflx_all.loc[inflex_key, ts])
        grouped_inflex_demand += inflex_val

    if target_node in EV_inflexible_demand_all.index:
        v = float(EV_inflexible_demand_all.loc[target_node, ts])
        grouped_inflex_demand += v

    if target_node in HP_inflexible_demand_all.index:
        v = float(HP_inflexible_demand_all.loc[target_node, ts])
        grouped_inflex_demand += v

    if abs(grouped_inflex_demand) > 1e-9:
        items.append(
            {
                "label": "Inflex demand (load + EV + HP)",
                "value": -grouped_inflex_demand,
                "kind": "base",
                "cost": None,
                "color": "rgb(146,51,32)",
            }
        )

    # Add flexible demand technologies (negative).
    for tech, val in demand_by_tech.items():
        storage_flag = classify_storage_tech(tech)
        opp_cost = None
        if storage_flag:
            plants = demand_tech_plants.get(tech, [])
            dual_vals = [-float(soc_dual_all.loc[p, ts]) for p in plants if p in soc_dual_all.index]
            flow_weights = [abs(float(demand_flxbl_all.loc[p, ts])) for p in plants if p in soc_dual_all.index]
            opp_cost = weighted_mean(dual_vals, flow_weights)
        items.append(
            {
                "label": fmt_with_cost(f"{tech} demand", opp_cost),
                "value": -val,
                "kind": "priced" if storage_flag else "base",
                "cost": opp_cost,
                "color": "rgb(120,120,120)" if storage_flag else "rgb(177,79,47)",
            }
        )

    # Add generation technologies (positive).
    for tech, val in gen_by_tech.items():
        if is_wind_pv_ror_tech(tech):
            grouped_wind_pv_ror_supply += val
            continue

        storage_flag = classify_storage_tech(tech)
        opp_cost = None
        if storage_flag:
            plants = gen_tech_plants.get(tech, [])
            dual_vals = [-float(soc_dual_all.loc[p, ts]) for p in plants if p in soc_dual_all.index]
            flow_weights = [abs(float(generation_all.loc[p, ts])) for p in plants if p in soc_dual_all.index]
            opp_cost = weighted_mean(dual_vals, flow_weights)
        items.append(
            {
                "label": fmt_with_cost(f"{tech} gen", opp_cost),
                "value": val,
                "kind": "priced" if storage_flag else "base",
                "cost": opp_cost,
                "color": "rgb(120,120,120)" if storage_flag else "rgb(36,122,72)",
            }
        )

    # Infeed preexisting (same categories as dispatch plot).
    infeed_tech = infeed_all.index.get_level_values(1).unique().tolist() if not infeed_all.empty else []
    tech_mapping = {
        "Wind": [item for item in infeed_tech if "windon" in str(item)],
        "Wind offshore": [item for item in infeed_tech if "windof" in str(item)],
        "RoR": [item for item in infeed_tech if "ror" in str(item)],
        "PV": [item for item in infeed_tech if "pv" in str(item)],
    }
    fixed_consumer = f"{target_node}_fixedconsumer"
    for name, subs in tech_mapping.items():
        total = 0.0
        for sub in subs:
            idx = (fixed_consumer, sub)
            if idx in infeed_all.index:
                total += float(infeed_all.loc[idx, ts])
        if target_node.startswith("CH0"):
            idx_ids = ("IDs", "pv")
            if idx_ids in infeed_all.index and name == "PV":
                total += float(infeed_all.loc[idx_ids, ts])
        grouped_wind_pv_ror_supply += total

    if abs(grouped_wind_pv_ror_supply) > 1e-9:
        items.append(
            {
                "label": "Wind/PV/RoR (incl. preexisting)",
                "value": grouped_wind_pv_ror_supply,
                "kind": "base",
                "cost": None,
                "color": "rgb(58,147,96)",
            }
        )

    # Imports / exports per border country at the selected hour.
    flows_by_country: dict[str, float] = {}
    all_trade_lines = list(dict.fromkeys(importATC_list + exportATC_list))
    for line in all_trade_lines:
        if line not in export_all.index:
            continue
        raw = float(export_all.loc[line, ts])
        node_from, node_to = parse_line_nodes(line)
        if not node_from or not node_to:
            continue
        if line in importATC_list:
            flow_ch = raw
            foreign = node_from
        else:
            flow_ch = -raw
            foreign = node_to
        flows_by_country[foreign] = flows_by_country.get(foreign, 0.0) + flow_ch

    for country, flow in flows_by_country.items():
        if abs(flow) < 1e-9:
            continue
        country_price = float(price_by_node_t.get(country, float("nan")))
        if flow > 0:
            items.append(
                {
                    "label": fmt_with_cost(f"Import {country}", country_price),
                    "value": flow,
                    "kind": "priced",
                    "cost": country_price,
                    "color": "rgb(51,112,173)",
                }
            )
        else:
            items.append(
                {
                    "label": fmt_with_cost(f"Export {country}", country_price),
                    "value": flow,
                    "kind": "priced",
                    "cost": country_price,
                    "color": "rgb(112,73,168)",
                }
            )

    # Clean very small values.
    items = [it for it in items if abs(float(it["value"])) > 1e-6]

    positives = [it for it in items if float(it["value"]) > 0]
    negatives = [it for it in items if float(it["value"]) < 0]

    pos_base = [it for it in positives if it["kind"] == "base"]
    pos_priced = [it for it in positives if it["kind"] == "priced"]
    neg_base = [it for it in negatives if it["kind"] == "base"]
    neg_priced = [it for it in negatives if it["kind"] == "priced"]

    pos_base.sort(key=lambda it: abs(float(it["value"])), reverse=True)
    neg_base.sort(key=lambda it: abs(float(it["value"])), reverse=True)

    pos_priced.sort(key=lambda it: float("inf") if it["cost"] is None else float(it["cost"]))
    neg_priced.sort(key=lambda it: float("inf") if it["cost"] is None else float(it["cost"]))

    pos_order = pos_base + pos_priced  # near center -> far
    neg_order = neg_base + neg_priced  # near center -> far

    ordered = list(reversed(pos_order)) + [
        {
            "label": f"CH price {ch_price:.0f}",
            "value": 0.0,
            "kind": "center",
            "cost": ch_price,
            "color": "rgb(20,20,20)",
        }
    ] + neg_order

    return ScenarioResult(
        display_name=display_name,
        items=ordered,
        ch_price=ch_price,
        timestep_label=timestep,
    )


def build_plot(results: list[ScenarioResult], day_month: str, hour: int, weather_year: str) -> go.Figure:
    fig = make_subplots(
        rows=1,
        cols=len(results),
        subplot_titles=[r.display_name for r in results],
        horizontal_spacing=0.12,
    )

    global_max = 0.0
    for res in results:
        if res.items:
            local_max = max(abs(float(it["value"])) for it in res.items)
            global_max = max(global_max, local_max)
    if global_max == 0:
        global_max = 1.0

    for col, res in enumerate(results, start=1):
        y = [it["label"] for it in res.items]
        x = [float(it["value"]) / 1000.0 for it in res.items]  # MW -> GW
        colors = [it["color"] for it in res.items]

        fig.add_trace(
            go.Bar(
                orientation="h",
                y=y,
                x=x,
                marker_color=colors,
                text=[f"{v:+.2f}" if abs(v) > 1e-8 else "" for v in x],
                textposition="outside",
                hovertemplate="%{y}<br>%{x:.3f} GW<extra></extra>",
                showlegend=False,
            ),
            row=1,
            col=col,
        )

        xref = "x" if col == 1 else f"x{col}"
        yref = "y domain" if col == 1 else f"y{col} domain"
        fig.add_shape(
            type="line",
            x0=0.0,
            x1=0.0,
            y0=0.0,
            y1=1.0,
            xref=xref,
            yref=yref,
            line=dict(color="black", width=1.5),
        )
        fig.update_yaxes(autorange="reversed", row=1, col=col, showticklabels=True)

    fig.update_xaxes(
        range=[-1.2 * global_max / 1000.0, 1.2 * global_max / 1000.0],
        title_text="Power (GW)",
    )

    fig.update_layout(
        title=(
            f"Dispatch composition comparison at {day_month} {hour:02d}:00 "
            f"({weather_year})"
        ),
        template="plotly_white",
        bargap=0.12,
        width=max(600 * len(results), 1600),
        height=900,
        margin=dict(l=40, r=20, t=100, b=40),
    )

    return fig


def main() -> None:
    args = parse_args()

    if len(args.scenario_dirs) != len(args.display_names):
        raise ValueError("--scenario-dirs and --display-names must have equal length")

    if not (0 <= args.hour <= 23):
        raise ValueError("--hour must be between 0 and 23")

    base_dir = Path(__file__).resolve().parent.parent
    timestep = timestep_from_timemap(base_dir, args.date, args.hour)

    results: list[ScenarioResult] = []
    for scenario_dir, display_name in zip(args.scenario_dirs, args.display_names):
        results.append(
            build_scenario_items(
                base_dir=base_dir,
                scenario_dir=Path(scenario_dir),
                display_name=display_name,
                target_node=args.target_node,
                weather_year=args.weather_year,
                timestep=timestep,
            )
        )

    fig = build_plot(results, args.date, args.hour, args.weather_year)
    fig.show()

    output_base = Path(args.output_base)
    output_base.parent.mkdir(parents=True, exist_ok=True)

    html_path = Path(f"{output_base}.html")
    pdf_path = Path(f"{output_base}.pdf")
    fig.write_html(str(html_path))
    print(f"Exported: {html_path}")

    try:
        fig.write_image(str(pdf_path), format="pdf")
        print(f"Exported: {pdf_path}")
    except Exception as exc:
        print(f"Warning: PDF export failed ({exc}).")


if __name__ == "__main__":
    main()
