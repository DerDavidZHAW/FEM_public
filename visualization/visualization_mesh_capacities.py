"""
This script will visualize installed capacities.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import os
from .config import *

def collapse_ntc_variants(df: pd.DataFrame) -> pd.DataFrame:
    pattern = re.compile(r'^(.*)_NTC(full|0|10|25|30)$')
    priority = {'full': 1, '0': 2, '10': 2, '25': 2, '30': 2}  # prefer numeric over 'full'

    keep_as_is = []           # columns kept unchanged (basecase_ or no NTC suffix)
    chosen_by_base = {}       # base -> (original_col, priority_score)

    for col in df.columns:
        if 'basecase_' in col:
            keep_as_is.append(col)
            continue

        m = pattern.match(col)
        if not m:
            # no trailing _NTC... -> keep unchanged
            keep_as_is.append(col)
            continue

        base, suff = m.group(1), m.group(2)
        score = priority[suff]
        if base not in chosen_by_base or score > chosen_by_base[base][1]:
            chosen_by_base[base] = (col, score)

    # Build final column list
    selected = keep_as_is + [orig for (orig, _) in chosen_by_base.values()]

    out = df[selected].copy()

    # Rename the chosen NTC-variant columns to their base form (strip trailing _NTC...)
    rename_map = {orig: base for base, (orig, _) in chosen_by_base.items()}
    out.rename(columns=rename_map, inplace=True)

    return out

def plot_capacities_mesh(directory_path):
    """
    Build a grid of stacked bar charts:
    - One subplot per scenario
    - X-axis = single bar (scenario), stacked by technology
    - Y-axis = installed capacity (converted by capacity_divisor), e.g. GW
    Includes only plants belonging to CH00 row(s) from Map_node_plant.csv.
    """

    # ---------- Load inputs ----------
    gen_max_path = os.path.join(directory_path, "gen_max.csv")
    map_node_plant_path = os.path.join("aggregation", "Map_node_plant.csv")
    map_plant_tech_path = os.path.join("aggregation", "Map_plant_tech.csv")

    gen_capacities = pd.read_csv(gen_max_path, index_col=0)
    swiss_plants = pd.read_csv(map_node_plant_path, index_col=0).loc["CH00"].to_list() # type: ignore
    Map_plant_to_tech = pd.read_csv(map_plant_tech_path, index_col=0)

    if gen_capacities.empty:
        raise ValueError("gen_max.csv is empty or not readable.")
    
    # Remove columns that essentially belong to the same scenario (e.g. from NTC0_P0001_RTN_GASN_NTCfull, NTC0_P0001_RTN_GASN_NTC0, keep only one)
    gen_capacities = collapse_ntc_variants(gen_capacities)
    scenario_cols = list(gen_capacities.columns)


    # Keep only Swiss plants
    if swiss_plants:
        gen_capacities = gen_capacities[gen_capacities.index.isin(swiss_plants)]
    else:
        raise ValueError("No Swiss plants detected from Map_node_plant.csv. Check your CH00 mapping.")

    if gen_capacities.empty:
        raise ValueError("After filtering to Swiss plants, no plants remain. Check your CH00 mapping.")

    # Attach technology
    gen_capacities["technology"] = gen_capacities.index.map(Map_plant_to_tech.iloc[:, 0]).fillna("other")

    # Convert values to numeric and scale to desired unit
    gen_capacities[scenario_cols] = gen_capacities[scenario_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    # Convert to GW
    gen_capacities[scenario_cols] = gen_capacities[scenario_cols] / 1000

    # Aggregate by technology for each scenario
    tech_by_scen = gen_capacities.groupby("technology")[scenario_cols].sum().sort_index()
    # ---------------- GROUP SCENARIOS LIKE IN plot_generation_diff ----------------
    basecases = [col for col in scenario_cols if col.startswith("basecase_")]

    # drop "normal years" (NTCfull) that are not basecases
    normalyears = [col for col in scenario_cols if "NTCfull" in col and col not in basecases]
    scenario_cols = [c for c in scenario_cols if c not in normalyears]

    # identify groups (columns between successive basecases)
    scenario_groups = {}
    ordered_cols = list(tech_by_scen.columns)  # keep original order
    base_idx = [ordered_cols.index(b) for b in basecases]
    base_idx.sort()
    for i, _ in enumerate(base_idx):
        start = base_idx[i]
        end = base_idx[i + 1] if i + 1 < len(base_idx) else len(ordered_cols)
        base = ordered_cols[start]
        scenario_groups[base] = ordered_cols[start:end]

    # Optional legend threshold in GW (if defined in config; else 0)
    try:
        threshold = plot_threshold_GW  # e.g. 0.1
    except NameError:
        threshold = 0.0

    # Optional y-axis bounds for capacity (if defined in config)
    try:
        y_min_cap = y_min_capacity
    except NameError:
        y_min_cap = 0
    try:
        y_max_cap = y_max_capacity
    except NameError:
        y_max_cap = None

    # ---------------- PER-BASECASE FIGURE ----------------
    for basecase, scenarios in scenario_groups.items():
        # create subplot figure
        fig = make_subplots(
            rows=num_rows,
            cols=num_cols,
            horizontal_spacing=0.001,
            vertical_spacing=0.001
        )

        legend_shown = set()

        col_idx = 0
        # precompute tech totals across this group for legend gating
        tech_totals = (tech_by_scen[scenarios]
                       .abs()
                       .sum(axis=1))

        for scenario in scenarios:
            if scenario == basecase:
                continue  # no subplot for the basecase itself

            row, col = divmod(col_idx, num_cols)

            row += 1
            col += 1

            # plot stacks for this scenario
            for tech in tech_by_scen.index:
                val = tech_by_scen.at[tech, scenario]
                if val < plot_treshold_GW:
                    continue

                label = tech_rename.get(tech, tech)
                color = tech_colors.get(tech, "#808080")

                # show legend once per tech if it passes threshold
                show_legend = (tech not in legend_shown) and (tech_totals.get(tech, 0) >= threshold)
                if show_legend:
                    legend_shown.add(tech)

                fig.add_trace(
                    go.Bar(
                        name=label,
                        x=[scenario],
                        y=[val],
                        marker_color=color,
                        showlegend=bool(show_legend),
                        legendgroup=label,
                        offsetgroup="cap",
                        # hovertemplate=f"{label}<br>{scenario}: %{y:.3f} {capacity_unit_label}<extra></extra>"
                    ),
                    row=row, col=col
                )

            col_idx += 1

        # ---- layout like your diff plot ----
        # y-axis ranges on all subplots
        if y_max_cap is not None:
            y_axis_updates = {
                f"yaxis{r * num_cols + c + 1}": dict(range=[y_min_cap, y_max_cap])
                for r in range(num_rows) for c in range(num_cols)
            }
        else:
            y_axis_updates = {}

        fig.update_layout(
            title_text=f"Installed Capacity by Technology — {basecase}",
            title_font=dict(size=24),
            legend=dict(font=dict(size=16)),
            barmode="stack",
            height=1000,
            width=1500,
            plot_bgcolor="white",
            bargap=0.01,
            bargroupgap=0.01,
            **y_axis_updates,  # type: ignore
        )

        # hide x ticks everywhere
        for i in range(1, num_rows * num_cols + 1):
            fig.update_xaxes(showticklabels=False, row=(i - 1) // num_cols + 1, col=(i - 1) % num_cols + 1)

        # y ticks: only first and last columns
        for i in range(1, num_rows * num_cols + 1):
            if i % num_cols != 1 and i % num_cols != 0:
                fig.update_yaxes(showticklabels=False, row=(i - 1) // num_cols + 1, col=(i - 1) % num_cols + 1)
            if i % num_cols == 0:
                fig.update_yaxes(showticklabels=True, row=(i - 1) // num_cols + 1, col=(i - 1) % num_cols + 1, side="right")

        # borders
        shapes = []
        for r in range(num_rows):
            for c in range(num_cols):
                shapes.append({
                    "type": "rect",
                    "xref": "paper",
                    "yref": "paper",
                    "x0": c / num_cols, "x1": (c + 1) / num_cols,
                    "y0": 1 - (r + 1) / num_rows, "y1": 1 - r / num_rows,
                    "line": {"color": "black", "width": 2},
                    "layer": "below"
                })
        fig.update_layout(shapes=shapes)

        # zero lines (not really needed for capacities but keeping for parity)
        for r in range(1, num_rows + 1):
            for c in range(1, num_cols + 1):
                fig.add_hline(y=0, line=dict(color="black", width=1, dash="solid"), row=r, col=c)

        fig.show()
