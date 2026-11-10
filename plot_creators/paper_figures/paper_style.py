"""Shared look of the price-setting paper and talk figures.

One palette for the whole deck and the paper:
  * technologies keep one colour everywhere (merit orders, setter shares),
  * countries keep one colour everywhere (setter location, border effects),
  * the two sets are only ever used in separate figures; in the merit order
    with neighbours a foreign unit keeps its technology colour and is marked
    by hatching plus the country code.
Validated with the dataviz palette checker (lightness band, chroma floor,
CVD and normal-vision separation of the stacking orders used here).

Text is Arial 18 pt (Liberation Sans, metric-identical, where Arial is
missing). Figure sizes are the size on a 13.33 x 7.5 in slide, so insert the
PNG at 100 % and the text stays 18 pt. No titles inside the figures.

Money. FEM works in real CHF of 2017 (input/cost_assumptions.xlsx converts
EUR sources with EUR2017toCHF2017 = 1.1119). The figures show EUR: every
price, bid and price effect is divided by CHF_PER_EUR. Override with the
environment variables PAPER_CURRENCY (EUR or CHF) and PAPER_CHF_PER_EUR,
e.g. 1.0 for a 1:1 relabel or 1/1.125 = 0.8889 for EUR in 2024 money.
"""
import os
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FONT_PT = 18

CURRENCY = os.environ.get("PAPER_CURRENCY", "EUR")
CHF_PER_EUR = float(os.environ.get("PAPER_CHF_PER_EUR", "1.1119")) if CURRENCY == "EUR" else 1.0
PRICE_UNIT = f"{CURRENCY}/MWh"


def money(x):
    """Model money (CHF2017) -> figure currency."""
    return x / CHF_PER_EUR

INK = "#1f1f1f"
INK_2 = "#5b5b5b"
MUTED = "#8c8c8c"
GRID = "#e6e6e6"
SURFACE = "#ffffff"

# ---------------------------------------------------------------- countries
COUNTRY_COLOR = {
    "CH": "#00929c",   # teal, a deep relative of the Basel mint
    "FR": "#3a5fc4",
    "DE": "#d9a21b",
    "IT": "#4c9a2a",
    "AT": "#c43c5e",
    "Rest": "#a29e96",  # rest of Europe
}
COUNTRY_LABEL = {"CH": "Switzerland", "FR": "France", "DE": "Germany", "IT": "Italy",
                 "AT": "Austria", "Rest": "Rest of Europe"}
NEIGHBOURS = ["FR", "IT", "DE", "AT"]          # stacking order in border figures

# ------------------------------------------------------------- technologies
TECH_COLOR = {
    "Renewables": "#e3b52e",
    "Reservoir hydro": "#2f6db5",
    "Pumped hydro": "#6fa3dc",
    "Biomass": "#6f9b2e",
    "Nuclear": "#7d5bc4",
    "Gas": "#a0603a",
    "Electrolyzer": "#e46c26",
    "Battery": "#b23a8f",
    "V2G": "#e07bb3",
    "Heat pump": "#d93f3f",
    "Resistive heater": "#ee9a78",
    "CHP": "#a0603a",
    "Other": "#b9b5ad",
    "Zero price": "#dedbd3",
}
TECH_LABEL = {
    "Renewables": "PV, wind, run-of-river",
    "Reservoir hydro": "Reservoir hydro",
    "Pumped hydro": "Pumped hydro",
    "Biomass": "Biomass",
    "Nuclear": "Nuclear",
    "Gas": "Gas and other thermal",
    "Electrolyzer": "Electrolysis",
    "Battery": "Battery",
    "V2G": "Vehicle-to-grid",
    "Heat pump": "Heat pumps",
    "Resistive heater": "Resistive heaters",
    "CHP": "CHP",
    "Other": "Other",
    "Zero price": "Zero price (surplus)",
}

DOMESTIC_SPECIAL = {"large_psp", "medium_reservior", "small_reservior", "EV_CH", "V2G_CH"}


def role_of(plant_id):
    """Raw FEM plant id -> technology class (same rules as
    model/price_setting_tech._role_of; keep in sync)."""
    pid = str(plant_id)
    if "CHP" in pid:
        return "CHP"
    if "resistive" in pid:
        return "Resistive heater"
    if "HPNew" in pid or "HPG" in pid or pid.endswith("[MWh]"):
        return "Heat pump"
    if "nuclear" in pid:
        return "Nuclear"
    if "hardcoal" in pid or "CCGTCCS" in pid or "oil" in pid or "_gas" in pid:
        return "Gas"
    if "biomass" in pid:
        return "Biomass"
    if "electrolyzer" in pid:
        return "Electrolyzer"
    if "psp" in pid:
        return "Pumped hydro"
    if "dam" in pid or "reservior" in pid or "reservoir" in pid:
        return "Reservoir hydro"
    if "V2G" in pid:
        return "V2G"
    if "battery" in pid:
        return "Battery"
    return "Other"


def country_of(plant_id, node_country=None):
    """Raw plant id -> CH / FR / DE / IT / AT / Rest."""
    pid = str(plant_id)
    if pid.startswith("CH0") or pid.startswith(("DH_", "ILHT_", "ILLT_", "minergie_")) \
            or pid.endswith("[MWh]") or pid in DOMESTIC_SPECIAL:
        return "CH"
    node = pid.split("_")[0]
    c = (node_country or {}).get(node, node[:2])
    return c if c in ("CH", "FR", "DE", "IT", "AT") else "Rest"


def tint(hex_color, amount):
    """Mix a colour with white (amount 0 = colour, 1 = white)."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    mix = [round(c + (255 - c) * amount) for c in (r, g, b)]
    return "#" + "".join(f"{c:02x}" for c in mix)


def text_on(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return INK if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.5 else SURFACE


def apply():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
        "font.size": FONT_PT,
        "axes.labelsize": FONT_PT,
        "xtick.labelsize": FONT_PT,
        "ytick.labelsize": FONT_PT,
        "legend.fontsize": FONT_PT,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK,
        "ytick.labelcolor": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
        "legend.frameon": False,
        "hatch.color": SURFACE,
        "hatch.linewidth": 1.6,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.facecolor": SURFACE,
    })


def grid(ax, axis="y"):
    ax.grid(True, axis=axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def save(fig, outdir, name, formats=("png", "pdf"), dpi=300):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in formats:
        p = outdir / f"{name}.{ext}"
        for attempt in range(6):        # a file open in a viewer can be locked for a moment
            try:
                fig.savefig(p, dpi=dpi)
                break
            except OSError:
                if attempt == 5:
                    raise
                time.sleep(1.5)
        paths.append(p)
    plt.close(fig)
    return paths


def year_of(run):
    return "2035" if "2035" in run else ("2050" if "2050" in run else run)
