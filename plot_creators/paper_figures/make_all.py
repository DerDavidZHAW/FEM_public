"""Rebuild all result figures of the SAEE talk / paper in one go.

    python plot_creators/paper_figures/make_all.py [--out DIR] [--formats png,pdf]

Runs (from the repo root) the four figure scripts for the fixed-hydrogen-price
runs. The merit-order step needs the hour cache; it is built on the first
call (several minutes for the large result files, repeat the call if it stops
with "call extract again").
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = ["h2fix78_2035_wy2008_12hydro", "h2fix78_2050_wy2008_12hydro"]
WEEK = "t_1177:t_1344"                       # 19-25 Feb
MERIT = [("h2fix78_2035_wy2008_12hydro", "t_1234"),   # 21 Feb 09:00, electrolysis DE
         ("h2fix78_2035_wy2008_12hydro", "t_1282")]   # 23 Feb 09:00, nuclear FR


def run(*args):
    cmd = [sys.executable, *map(str, args)]
    print(">", " ".join(cmd[1:]))
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output/paper_figures")
    ap.add_argument("--formats", default="png,pdf")
    ap.add_argument("--currency", default="EUR", choices=["EUR", "CHF"],
                    help="money unit of the figures (model works in CHF2017)")
    ap.add_argument("--chf-per-eur", default="1.1119",
                    help="conversion for --currency EUR (default EUR2017toCHF2017 of the cost data)")
    a = ap.parse_args()
    import os
    os.environ["PAPER_CURRENCY"] = a.currency
    os.environ["PAPER_CHF_PER_EUR"] = a.chf_per_eur
    common = ["--out", a.out, "--formats", a.formats]
    run(HERE / "fig_setter_supply_demand.py", *RUNS, *common)
    run(HERE / "fig_setter_country.py", *RUNS, *common)
    run(HERE / "fig_border_effects.py", *RUNS, "--week", WEEK, *common)
    for r, t in MERIT:
        run(HERE / "fig_merit_order.py", "extract", r, "--hours", WEEK, "--budget", "100000")
        run(HERE / "fig_merit_order.py", "plot", r, "--hour", t, *common)
    run(HERE / "fig_shapley_waterfall.py", MERIT[0][0], "--hour", MERIT[0][1], *common)


if __name__ == "__main__":
    main()
