"""Plot hourly CH exports per neighbor and the corresponding neighbor prices.

Opens one figure per scenario in the default browser. Left y-axis: export from
CH per HVAC line (MWh, positive = CH selling). Right y-axis: hourly electricity
price at the neighbor node (CHF/MWh).
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

pio.renderers.default = "browser"


SCENARIOS = [
    "20260331_MIP3_v6/2035_GA_NRT_NF",
    "20260331_MIP3_v6/2050_GA_NRT_NN_NF",
]

LINE_TO_NEIGHBOR = {
    "HVAC_AT00_CH00": "AT00",
    "HVAC_DE00_CH00": "DE00",
    "HVAC_FR00_CH00": "FR00",
    "HVAC_IT00_CH00": "IT00",
}

NEIGHBOR_COLOR = {
    "AT00": "#1f77b4",
    "DE00": "#d62728",
    "FR00": "#2ca02c",
    "IT00": "#ff7f0e",
}

OUTPUT_ROOT = Path("output")


def _hour_index(series: pd.Series) -> pd.Series:
    """Convert 't_<n>' strings to integer hour-of-year."""
    return series.astype(str).str.extract(r"t_(\d+)", expand=False).astype(int)


def build_figure(scenario: str) -> go.Figure:
    scen_dir = OUTPUT_ROOT / scenario
    exp = pd.read_csv(scen_dir / "Export.csv")
    dual = pd.read_csv(scen_dir / "energy_balance_dual.csv")

    exp = exp[exp["lineATC"].isin(LINE_TO_NEIGHBOR)].copy()
    exp["value"] = pd.to_numeric(exp["value"], errors="coerce").fillna(0.0)
    # Convention: positive Export = import to CH, negative = export from CH.
    # Show exports from CH as positive MWh, zero otherwise.
    exp["export_from_ch"] = (-exp["value"]).clip(lower=0.0)
    exp["hour"] = _hour_index(exp["T"])

    dual = dual[dual["Node"].isin(LINE_TO_NEIGHBOR.values())].copy()
    dual["value"] = pd.to_numeric(dual["value"], errors="coerce").fillna(0.0)
    dual["hour"] = _hour_index(dual["T"])

    fig = go.Figure()

    for line, neighbor in LINE_TO_NEIGHBOR.items():
        color = NEIGHBOR_COLOR[neighbor]
        df_l = exp[exp["lineATC"] == line].sort_values("hour")
        fig.add_trace(go.Scatter(
            x=df_l["hour"],
            y=df_l["export_from_ch"],
            name=f"Export to {neighbor} [MWh]",
            mode="lines",
            line=dict(color=color, width=1),
            legendgroup=neighbor,
            yaxis="y",
        ))
        df_p = dual[dual["Node"] == neighbor].sort_values("hour")
        fig.add_trace(go.Scatter(
            x=df_p["hour"],
            y=df_p["value"],
            name=f"Price {neighbor} [CHF/MWh]",
            mode="lines",
            line=dict(color=color, width=1, dash="dash"),
            legendgroup=neighbor,
            yaxis="y2",
            opacity=0.7,
        ))

    fig.update_layout(
        title=f"CH exports and neighbor prices — {scenario}",
        xaxis=dict(title="Hour of year"),
        yaxis=dict(title="Export from CH [MWh]", side="left"),
        yaxis2=dict(title="Neighbor price [CHF/MWh]",
                    overlaying="y", side="right", showgrid=False),
        hovermode="x unified",
        legend=dict(orientation="v"),
        template="plotly_white",
    )
    return fig


def main() -> None:
    for scen in SCENARIOS:
        fig = build_figure(scen)
        fig.show()


if __name__ == "__main__":
    main()
