"""Convert one (or all) solved FEM runs into a compact viewer JSON for viewer.html.

Usage:
    python tools/prepare_viewer.py output/<run_name>
    python tools/prepare_viewer.py output --all
    python tools/prepare_viewer.py output/<run_name> --out-dir plots
    python tools/prepare_viewer.py output/<run_name> --sub-scenario <Scenarios value>

Reads the long-format CSVs the model exports into output/<run>/ and writes
plots/<run>_viewer.json.gz  (one file per run; plots/ is gitignored).

The JSON is what viewer.html consumes:
  meta   - scenario identity, zones, tech palette, lines, DH nodes, units, settings
  kpis   - headline numbers (system cost, CH prices, net imports, RES share, ...)
  H      - hourly arrays (8760, calendar order t_1..t_8760): price, load, gen/chg
           by zone x tech group, curtailment, lost load, net imports, line flows,
           NTC-binding flags, storage SoC
  dh     - district heating block: heat price, demand, dispatch, TES SoC per node
  ann    - annual tables: capacity existing/added, line summary, storage sizes

Missing output files are warned about and skipped - the viewer hides those panels.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import gzip
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

N_HOURS = 8760
ZERO_TOL = 1e-6

# ----------------------------------------------------------------------------
# Tech grouping (model tech -> viewer group) and display metadata.
# Stack order is bottom -> top in the dispatch chart.
# ----------------------------------------------------------------------------

SUPPLY_GROUPS = {
    # key: (label, color)
    "nuclear": ("Nuclear", "#9b8ec4"),
    "ror":     ("Run-of-river", "#9ec9e8"),
    "dam":     ("Reservoir hydro", "#2e6fad"),
    "psp":     ("Pumped storage", "#5a9bd5"),
    "battery": ("Battery", "#4dbd9a"),
    "h2":      ("H₂ power", "#b07aa1"),
    "chp":     ("CHP (district heat)", "#d9836a"),
    "biomass": ("Biomass", "#8aa353"),
    "gasccs":  ("Gas CCS", "#8d7b6c"),
    "gasres":  ("Gas (res-methane)", "#c9b380"),
    "gas":     ("Gas (fossil)", "#b08968"),
    "coal":    ("Hard coal", "#665c54"),
    "oil":     ("Oil", "#7a7a7a"),
    "other":   ("Other", "#c8c2b8"),
    "windon":  ("Wind onshore", "#58b6c0"),
    "windof":  ("Wind offshore", "#2f8e99"),
    "pv":      ("Solar PV", "#f2c14e"),
    "dsr":     ("DSR (release)", "#e0a8b9"),
    "v2g":     ("V2G (discharge)", "#76c4e2"),
}

CHARGE_GROUPS = {
    "psp_c":     ("PSP pumping", "#5a9bd5"),
    "battery_c": ("Battery charging", "#4dbd9a"),
    "h2_c":      ("Electrolysis / H₂", "#b07aa1"),
    "ev_c":      ("EV charging (flex)", "#76c4e2"),
    "dsr_c":     ("DSR (shift)", "#e0a8b9"),
    "p2h":       ("Power-to-heat (DH)", "#e2906e"),
    "hpb":       ("Building HP (flex)", "#d98ca6"),
}

SOC_GROUPS = {
    "dam":     ("Reservoir hydro", "#2e6fad"),
    "psp":     ("Pumped storage", "#5a9bd5"),
    "battery": ("Battery", "#4dbd9a"),
    "h2":      ("H₂ storage", "#b07aa1"),
    "ev":      ("EV / V2G", "#76c4e2"),
}

DH_GROUPS = {
    "hp":    ("Heat pump", "#d9836a"),
    "rh":    ("Resistive heater", "#e8b04b"),
    "chp":   ("CHP", "#b07aa1"),
    "gasb":  ("Gas boiler", "#b08968"),
    "tes":   ("TES discharge", "#5a9bd5"),
    "dsrth": ("Heat DSR (release)", "#e0a8b9"),
}

DH_CHARGE_GROUPS = {
    "tes_c":   ("TES charging", "#5a9bd5"),
    "dsrth_c": ("Heat DSR (shift)", "#e0a8b9"),
}

# model tech -> supply group (gen.csv);  CHP override is by plant name (see below)
GEN_TECH_TO_GROUP = {
    "nuclear": "nuclear",
    "dam": "dam",
    "psp_open": "psp",
    "psp_close": "psp",
    "battery": "battery",
    "hydrogen": "h2",
    "biomass": "biomass",
    "CCGTCCS": "gasccs",
    "CCGTresmethane": "gasres",
    "SCGTresmethane": "gasres",
    "gas": "gas",
    "SCGTfossil": "gas",
    "hardcoal": "coal",
    "oil": "oil",
    "other": "other",
    "windon": "windon",
    "windof": "windof",
    "pvrf": "pv",
    "pv": "pv",
    "ror": "ror",
    "dsr": "dsr",
    "v2g": "v2g",
    "ev_flex": "ev_gen",       # should be ~0; kept visible if it is not
}

INFEED_TECH_TO_GROUP = {
    "pv": "pv",
    "pvrf": "pv",
    "ror": "ror",
    "windon": "windon",
    "windof": "windof",
}

CHARGE_TECH_TO_GROUP = {
    "psp_open": "psp_c",
    "psp_close": "psp_c",
    "battery": "battery_c",
    "electrolyzer": "h2_c",
    "hydrogen": "h2_c",
    "ev_flex": "ev_c",
    "v2g": "ev_c",
    "dsr": "dsr_c",
    "heat_pump": "p2h",
    "resistive_heater": "p2h",
    "heat_pump_households": "hpb",
}

SOC_TECH_TO_GROUP = {
    "dam": "dam",
    "psp_open": "psp",
    "psp_close": "psp",
    "battery": "battery",
    "hydrogen": "h2",
    "v2g": "ev",
    "ev_flex": "ev",
}

DH_TECH_TO_GROUP = {
    "heat_pump": "hp",
    "resistive_heater": "rh",
    "CCGTCCS": "chp",
    "gas_boiler": "gasb",
    "PTES_large": "tes",
    "TTES_medium": "tes",
    "dsrTh": "dsrth",
}

DH_CHARGE_TECH_TO_GROUP = {
    "PTES_large": "tes_c",
    "TTES_medium": "tes_c",
    "dsrTh": "dsrth_c",
}

# groups counted as renewable / as primary (non-cycling) generation for the
# RES-share KPI
RES_GROUPS = {"pv", "windon", "windof", "ror", "dam", "biomass"}
CYCLING_GROUPS = {"battery", "psp", "h2", "v2g", "dsr", "ev_gen"}


def effective_tech(plant: str, tech: str | None) -> str | None:
    """Display-level override: the CH representative hydro reservoirs
    (medium_reservior / small_reservior, rep_hydro_plants mode) carry tech
    'psp_open' in Map_plant_tech but are reservoirs - show them as 'dam'."""
    if tech == "psp_open" and "reservi" in plant.lower():
        return "dam"
    return tech


def warn(msg: str) -> None:
    print(f"  [warn] {msg}")


class RunConverter:
    def __init__(self, run_dir: Path, sub_scenario: str | None = None):
        self.dir = run_dir
        self.name = run_dir.name
        self.sub = sub_scenario
        self.missing: list[str] = []

    # ---------------------------------------------------------------- I/O --

    def read(self, name: str, usecols=None) -> pd.DataFrame | None:
        """Read one long-format CSV; warn and return None if absent."""
        p = self.dir / f"{name}.csv"
        if not p.exists():
            self.missing.append(name)
            warn(f"{name}.csv not found - dependent panels will be skipped")
            return None
        df = pd.read_csv(p, usecols=usecols)
        if "Scenarios" in df.columns:
            subs = df["Scenarios"].unique()
            if self.sub is None and len(subs) > 1:
                self.sub = subs[0]
                warn(f"multiple sub-scenarios {list(subs)} - using '{self.sub}'")
            if self.sub is not None and len(subs) > 1:
                df = df[df["Scenarios"] == self.sub]
            df = df.drop(columns=["Scenarios"])
        return df

    @staticmethod
    def t_to_idx(df: pd.DataFrame) -> pd.DataFrame:
        """Replace T ('t_1'..'t_8760') with calendar hour index 0..8759."""
        df = df.copy()
        df["ti"] = df["T"].str.slice(2).astype(np.int32) - 1
        return df.drop(columns=["T"])

    def hourly(self, df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
        """Group long df to a (keys) x 8760 matrix, calendar order, zeros filled."""
        df = self.t_to_idx(df)
        g = df.groupby(keys + ["ti"], observed=True)["value"].sum()
        m = g.unstack("ti", fill_value=0.0)
        return m.reindex(columns=range(N_HOURS), fill_value=0.0)

    # ------------------------------------------------------------ helpers --

    @staticmethod
    def pack(values, nd: int) -> list:
        """Round to nd decimals; whole numbers become ints (smaller JSON)."""
        a = np.round(np.asarray(values, dtype=float), nd)
        a = a + 0.0  # normalize -0.0
        out = []
        for x in a.tolist():
            if math.isnan(x) or math.isinf(x):
                out.append(None)
            elif x.is_integer():
                out.append(int(x))
            else:
                out.append(round(x, nd))
        return out

    def pack_matrix(self, m: pd.DataFrame, nd: int) -> dict:
        """Matrix (index -> 8760 cols) to {key: [..]}, dropping all-zero rows.

        Tuple indices become nested dicts {k1: {k2: [..]}}.
        """
        out: dict = {}
        if m is None:
            return out
        keep = m.abs().to_numpy().max(axis=1) > ZERO_TOL
        m = m.loc[keep]
        for idx, row in zip(m.index, m.to_numpy()):
            packed = self.pack(row, nd)
            if isinstance(idx, tuple):
                d = out
                for k in idx[:-1]:
                    d = d.setdefault(k, {})
                d[idx[-1]] = packed
            else:
                out[idx] = packed
        return out

    @staticmethod
    def num(x, nd=3):
        if x is None:
            return None
        x = float(x)
        if math.isnan(x) or math.isinf(x):
            return None
        return int(x) if float(x).is_integer() else round(x, nd)

    # ------------------------------------------------------------ mappings --

    def load_mappings(self) -> bool:
        mpt = self.read("Map_plant_tech")
        if mpt is None:
            warn("Map_plant_tech.csv is required - aborting this run")
            return False
        self.plant_tech = dict(zip(mpt["P"], mpt["value"]))

        # Map_node_plant is wide: Node, value, 1, 2, ... each cell a plant name
        self.plant_node: dict[str, str] = {}
        p = self.dir / "Map_node_plant.csv"
        if p.exists():
            wide = pd.read_csv(p)
            for _, row in wide.iterrows():
                node = row.iloc[0]
                for plant in row.iloc[1:]:
                    if isinstance(plant, str) and plant:
                        self.plant_node[plant] = node
        else:
            warn("Map_node_plant.csv not found - plant->zone mapping unavailable")

        mnc = self.read("Map_node_consumer")
        self.consumer_node = (
            dict(zip(mnc["value"], mnc["Node"])) if mnc is not None else {}
        )

        mdt = self.read("Map_plantDH_tech")
        self.dhplant_tech = dict(zip(mdt["PDH"], mdt["value"])) if mdt is not None else {}
        mdn = self.read("Map_plantDH_nodeDH")
        self.dhplant_node = dict(zip(mdn["PDH"], mdn["value"])) if mdn is not None else {}

        pall = self.read("P_allinv")
        self.invest_plants = set(pall["Dimension_0"]) if pall is not None else set()

        self.zones = sorted(self.consumer_node.values()) if self.consumer_node else []
        if "CH00" in self.zones:  # focus zone first
            self.zones = ["CH00"] + [z for z in self.zones if z != "CH00"]
        return True

    def tech_of(self, plant: str) -> str | None:
        return effective_tech(plant, self.plant_tech.get(plant))

    def gen_group(self, plant: str) -> str:
        tech = self.tech_of(plant)
        if tech is None:
            warn(f"plant '{plant}' missing from Map_plant_tech - grouped as 'other'")
            return "other"
        if tech == "CCGTCCS" and "CHP" in plant:
            return "chp"
        return GEN_TECH_TO_GROUP.get(tech, "other")

    def zone_of(self, plant: str) -> str | None:
        z = self.plant_node.get(plant)
        if z is None:
            warn(f"plant '{plant}' missing from Map_node_plant - skipped")
        return z

    # ------------------------------------------------------------ settings --

    def load_settings(self) -> dict:
        p = self.dir / "settings.csv"
        if not p.exists():
            warn("settings.csv not found")
            return {}
        df = pd.read_csv(p)
        col = df.columns[1]
        if self.sub is None:
            self.sub = col
        return dict(zip(df["Item"], df[col].astype(str)))

    # -------------------------------------------------------------- build --

    def build(self) -> dict | None:
        t0 = time.time()
        if not self.load_mappings():
            return None
        settings = self.load_settings()

        H: dict = {}
        ann: dict = {}
        dh: dict = {}

        # ---- prices ------------------------------------------------------
        df = self.read("energy_balance_dual")
        if df is not None:
            H["price"] = self.pack_matrix(self.hourly(df, ["Node"]), 2)

        # ---- inflexible load ----------------------------------------------
        df = self.read("demand")
        if df is not None:
            H["loadf"] = self.pack_matrix(
                self.hourly(df.assign(z=df["Consumer"].map(self.consumer_node)), ["z"]), 1
            )
        for fname, key in [("EV_inflexible_demand", "loadev"),
                           ("HP_inflexible_demand", "loadhp")]:
            df = self.read(fname)
            if df is not None:
                H[key] = self.pack_matrix(self.hourly(df, ["Node"]), 1)

        # ---- generation by zone x group (gen + RES infeed) ----------------
        gen_m = None
        df = self.read("gen")
        if df is not None:
            df["z"] = df["P_gen"].map(self.plant_node)
            df["g"] = df["P_gen"].map(self.gen_group)
            df = df.dropna(subset=["z"])
            gen_m = self.hourly(df, ["z", "g"])
        df = self.read("infeed")
        if df is not None:
            df["z"] = df["Consumer_with_infeed"].map(self.consumer_node)
            df["g"] = df["Tech_infeed"].map(INFEED_TECH_TO_GROUP)
            df = df.dropna(subset=["z", "g"])
            inf_m = self.hourly(df, ["z", "g"])
            gen_m = inf_m if gen_m is None else gen_m.add(inf_m, fill_value=0.0)
        if gen_m is not None:
            H["gen"] = self.pack_matrix(gen_m, 1)

        # ---- consumption side: storage charging / P2X / P2H / DSR ---------
        chg_m = None
        df = self.read("storage_charge")
        if df is not None:
            df["z"] = df["P_pumping"].map(self.plant_node)
            df["g"] = df["P_pumping"].map(
                lambda p: CHARGE_TECH_TO_GROUP.get(self.tech_of(p), "other_c")
            )
            df = df.dropna(subset=["z"])
            chg_m = self.hourly(df, ["z", "g"])
            H["chg"] = self.pack_matrix(chg_m, 1)

        # ---- curtailment / lost load --------------------------------------
        df = self.read("curtailment")
        curt_m = None
        if df is not None:
            df["z"] = df["Consumer_with_infeed"].map(self.consumer_node)
            curt_m = self.hourly(df, ["z"])
            H["curt"] = self.pack_matrix(curt_m, 1)
        df = self.read("lostload")
        ll_m = None
        if df is not None:
            df["z"] = df["Consumer"].map(self.consumer_node)
            ll_m = self.hourly(df, ["z"])
            H["ll"] = self.pack_matrix(ll_m, 1)

        # ---- line flows, net imports, NTC binding -------------------------
        flow_m = None
        df = self.read("Export")
        if df is not None:
            flow_m = self.hourly(df, ["lineATC"])
            H["flow"] = self.pack_matrix(flow_m, 1)

            lines = []
            for lid in flow_m.index:
                parts = lid.split("_")
                frm, to = (parts[-2], parts[-1]) if len(parts) >= 3 else ("?", "?")
                lines.append({"id": lid, "frm": frm, "to": to})
            self.lines = lines

            # net import per zone (positive = net importer this hour)
            nimp = {z: np.zeros(N_HOURS) for z in self.zones}
            for line in lines:
                f = flow_m.loc[line["id"]].to_numpy()
                if line["to"] in nimp:
                    nimp[line["to"]] += f
                if line["frm"] in nimp:
                    nimp[line["frm"]] -= f
            H["nimp"] = {
                z: self.pack(v, 1) for z, v in nimp.items() if np.abs(v).max() > ZERO_TOL
            }
            self.nimp = nimp
        else:
            self.lines = []
            self.nimp = {}

        dual = self.read("lineATClimit_dual")
        if dual is not None and flow_m is not None:
            dual_m = self.hourly(dual, ["lineATC"]).reindex(flow_m.index, fill_value=0.0)
            bind = {}
            line_summary = []
            for line in self.lines:
                lid = line["id"]
                f = flow_m.loc[lid].to_numpy()
                d = dual_m.loc[lid].to_numpy()
                b = np.zeros(N_HOURS, dtype=np.int8)
                binding = np.abs(d) > ZERO_TOL
                b[binding & (f > 0.5)] = 1     # export-direction limit
                b[binding & (f < -0.5)] = -1   # import-direction limit
                b[binding & (np.abs(f) <= 0.5)] = 2  # binding at ~zero capacity
                if b.any():
                    bind[lid] = [int(x) for x in b]
                exp_b = f[b == 1]
                imp_b = f[b == -1]
                line_summary.append({
                    "id": lid, "frm": line["frm"], "to": line["to"],
                    "exp_twh": self.num(f[f > 0].sum() / 1e6),
                    "imp_twh": self.num(-f[f < 0].sum() / 1e6),
                    "bh_e": int((b == 1).sum()),
                    "bh_i": int((b == -1).sum()),
                    "bh_z": int((b == 2).sum()),
                    "ntc_e": self.num(exp_b.max(), 1) if exp_b.size else None,
                    "ntc_i": self.num(-imp_b.min(), 1) if imp_b.size else None,
                    "max_f": self.num(f.max(), 1),
                    "min_f": self.num(f.min(), 1),
                })
            H["bind"] = bind
            ann["lines"] = line_summary
        elif flow_m is not None:
            # No NTC duals in this run: per user guidance, fall back to the max
            # observed flow per direction as the NTC value (flagged with est=1).
            warn("lineATClimit_dual missing - using max observed flow as NTC (est)")
            line_summary = []
            for l in self.lines:
                f = flow_m.loc[l["id"]].to_numpy()
                mx, mn = float(f.max()), float(f.min())
                line_summary.append({
                    "id": l["id"], "frm": l["frm"], "to": l["to"],
                    "exp_twh": self.num(f[f > 0].sum() / 1e6),
                    "imp_twh": self.num(-f[f < 0].sum() / 1e6),
                    "ntc_e": self.num(mx, 1) if mx > 0.5 else None,
                    "ntc_i": self.num(-mn, 1) if mn < -0.5 else None,
                    "max_f": self.num(mx, 1), "min_f": self.num(mn, 1),
                    "est": 1,
                })
            ann["lines"] = line_summary

        # ---- storage SoC ---------------------------------------------------
        df = self.read("soc")
        if df is not None:
            df["z"] = df["P_storage"].map(self.plant_node)
            df["g"] = df["P_storage"].map(
                lambda p: SOC_TECH_TO_GROUP.get(self.tech_of(p), None)
            )
            df = df.dropna(subset=["z", "g"])
            H["soc"] = self.pack_matrix(self.hourly(df, ["z", "g"]), 0)

        socmax: dict = {}
        df = self.read("gen_energy_max")
        if df is not None:
            for plant, val in zip(df["P_energymax"], df["value"]):
                z = self.plant_node.get(plant)
                g = SOC_TECH_TO_GROUP.get(self.tech_of(plant))
                if z and g and np.isfinite(val):
                    socmax.setdefault(z, {})
                    socmax[z][g] = socmax[z].get(g, 0.0) + float(val)
        df = self.read("V2G_storage_capacity")
        if df is not None:
            cap_col = [c for c in df.columns if c != "value"]
            for _, row in df.iterrows():
                plant = row[cap_col[0]] if cap_col else "V2G_CH"
                z = self.plant_node.get(plant, "CH00")
                socmax.setdefault(z, {})
                socmax[z]["ev"] = socmax[z].get("ev", 0.0) + float(row["value"])
        ann["socmax"] = {
            z: {g: self.num(v, 0) for g, v in d.items()} for z, d in socmax.items()
        }

        # ---- capacity: existing vs added by zone x group -------------------
        cap: dict = {}

        def cap_add(z, g, kind, mw):
            if z is None or g is None or mw is None or not np.isfinite(mw) or mw <= 0:
                return
            cap.setdefault((z, g), {"ex": 0.0, "add": 0.0})
            cap[(z, g)][kind] += float(mw)

        df = self.read("gen_max")
        if df is not None:
            for plant, val in zip(df["P_gen"], df["value"]):
                kind = "add" if plant in self.invest_plants else "ex"
                cap_add(self.plant_node.get(plant), self.gen_group(plant), kind, val)
        df = self.read("gen_max_infeedp")
        if df is not None:
            mit = self.read("Map_infeedplant_tech")
            min_ = self.read("Map_infeedplant_node")
            if mit is not None and min_ is not None:
                itech = dict(zip(mit["Infeedp"], mit["value"]))
                inode = dict(zip(min_["Infeedp"], min_["value"]))
                for plant, val in zip(df["Infeedp"], df["value"]):
                    g = INFEED_TECH_TO_GROUP.get(itech.get(plant))
                    cap_add(inode.get(plant), g, "ex", val)
        if cap:
            ann["cap"] = [
                {"z": z, "g": g, "ex": self.num(v["ex"], 1), "add": self.num(v["add"], 1)}
                for (z, g), v in sorted(cap.items())
            ]

        # ---- costs / emissions ---------------------------------------------
        costs: dict[str, float] = {}

        def cost_sum(fname, key):
            p = self.dir / f"{fname}.csv"
            if not p.exists():
                return
            df = pd.read_csv(p)
            costs[key] = costs.get(key, 0.0) + float(df["cost_CHF"].sum())

        cost_sum("cost_inv_dict", "inv")
        cost_sum("cost_inv_thermal_dict", "inv")
        cost_sum("cost_inv_fuel_storage_dict", "inv")
        cost_sum("cost_op_dict", "op")
        cost_sum("cost_op_thermal_dict", "op")
        cost_sum("lostload_cost_dict", "ll")
        cost_sum("trade_cost_dict", "trade")
        ann["costs"] = {k: self.num(v, 0) for k, v in costs.items()}

        co2 = None
        p = self.dir / "emissions_dict.csv"
        if p.exists():
            co2 = float(pd.read_csv(p)["emissions_tCO2"].sum())

        stats = {}
        p = self.dir / "statistics.csv"
        if p.exists():
            sdf = pd.read_csv(p)
            stats = dict(zip(sdf["Variable"], sdf["Value"]))

        # ---- district heating ----------------------------------------------
        dh_nodes: list[str] = []
        df = self.read("energy_balancethermal_dual")
        if df is not None:
            m = self.hourly(df, ["NodeDH"])
            dh["price"] = self.pack_matrix(m, 2)
            dh_nodes = sorted(m.index)
        df = self.read("demandDH")
        dem_th_m = None
        if df is not None:
            dem_th_m = self.hourly(df, ["NodeDH"])
            dh["dem"] = self.pack_matrix(dem_th_m, 1)
            if not dh_nodes:
                dh_nodes = sorted(dem_th_m.index)
        df = self.read("genTh")
        if df is not None:
            df["n"] = df["PDH"].map(self.dhplant_node)
            df["g"] = df["PDH"].map(lambda p: DH_TECH_TO_GROUP.get(self.dhplant_tech.get(p)))
            df = df.dropna(subset=["n", "g"])
            dh["gen"] = self.pack_matrix(self.hourly(df, ["n", "g"]), 1)
        df = self.read("storage_chargeTh")
        if df is not None:
            df["n"] = df["PDH_storagecharge"].map(self.dhplant_node)
            df["g"] = df["PDH_storagecharge"].map(
                lambda p: DH_CHARGE_TECH_TO_GROUP.get(self.dhplant_tech.get(p))
            )
            df = df.dropna(subset=["n", "g"])
            dh["chg"] = self.pack_matrix(self.hourly(df, ["n", "g"]), 1)
        df = self.read("socTh")
        if df is not None:
            df["n"] = df["PDH_TES"].map(self.dhplant_node)
            df = df.dropna(subset=["n"])
            dh["soc"] = self.pack_matrix(self.hourly(df, ["n"]), 0)
        df = self.read("curtailmentTh")
        if df is not None:
            dh["curt"] = self.pack_matrix(self.hourly(df, ["NodeDH"]), 1)
        df = self.read("gen_energyTh_max")
        if df is not None:
            sm: dict[str, float] = {}
            for plant, val in zip(df["PDH_TES"], df["value"]):
                n = self.dhplant_node.get(plant)
                if n and np.isfinite(val):
                    sm[n] = sm.get(n, 0.0) + float(val)
            dh["socmax"] = {n: self.num(v, 0) for n, v in sm.items()}
        df = self.read("genTh_max")
        if df is not None:
            capth: dict = {}
            for plant, val in zip(df["PDH"], df["value"]):
                n = self.dhplant_node.get(plant)
                g = DH_TECH_TO_GROUP.get(self.dhplant_tech.get(plant))
                if n and g and np.isfinite(val) and val > ZERO_TOL:
                    capth.setdefault((n, g), 0.0)
                    capth[(n, g)] += float(val)
            dh["cap"] = [
                {"n": n, "g": g, "mw": self.num(v, 1)} for (n, g), v in sorted(capth.items())
            ]

        # ---- KPIs ------------------------------------------------------------
        kpis: dict = {"obj": self.num(stats.get("Objective_Value"), 0)}
        if co2 is not None:
            kpis["co2_mt"] = self.num(co2 / 1e6, 2)
        kpis["costs"] = ann["costs"]
        if curt_m is not None:
            kpis["curt_twh_sys"] = self.num(curt_m.to_numpy().sum() / 1e6, 2)
        if ll_m is not None:
            kpis["ll_gwh_sys"] = self.num(ll_m.to_numpy().sum() / 1e3, 2)

        fz = "CH00"
        focus: dict = {"z": fz}
        if gen_m is not None and fz in gen_m.index.get_level_values(0):
            zg = gen_m.loc[fz]
            total = zg.to_numpy().sum()
            primary = sum(
                zg.loc[g].sum() for g in zg.index if g not in CYCLING_GROUPS
            )
            res = sum(zg.loc[g].sum() for g in zg.index if g in RES_GROUPS)
            focus["gen_twh"] = self.num(total / 1e6, 2)
            focus["res_share"] = self.num(res / primary, 4) if primary > 0 else None
        load_total = np.zeros(N_HOURS)
        for key in ["loadf", "loadev", "loadhp"]:
            if key in H and fz in H[key]:
                load_total += np.asarray(H[key][fz], dtype=float)
        if load_total.max() > 0:
            focus["peak_load"] = self.num(load_total.max(), 0)
            focus["demand_twh"] = self.num(load_total.sum() / 1e6, 2)
        if "price" in H and fz in H["price"]:
            pr = np.asarray(H["price"][fz], dtype=float)
            focus["price_avg"] = self.num(pr.mean(), 2)
            focus["price_max"] = self.num(pr.max(), 2)
            focus["price_min"] = self.num(pr.min(), 2)
            if load_total.sum() > 0:
                focus["price_w"] = self.num((pr * load_total).sum() / load_total.sum(), 2)
        if fz in self.nimp:
            focus["nimp_twh"] = self.num(self.nimp[fz].sum() / 1e6, 2)
        if curt_m is not None and fz in curt_m.index:
            focus["curt_twh"] = self.num(curt_m.loc[fz].sum() / 1e6, 3)
        added = [
            r for r in ann.get("cap", [])
            if r["z"] == fz and r["add"] and r["add"] > 0
        ]
        if added:
            focus["added_gw"] = self.num(sum(r["add"] for r in added) / 1e3, 2)
        kpis["focus"] = focus

        if dem_th_m is not None:
            dh_kpi = {"demand_twh": self.num(dem_th_m.to_numpy().sum() / 1e6, 2)}
            if "price" in dh:
                wsum, w = 0.0, 0.0
                for n in dh["price"]:
                    if n in dh.get("dem", {}):
                        pn = np.asarray(dh["price"][n], dtype=float)
                        dn = np.asarray(dh["dem"][n], dtype=float)
                        wsum += float((pn * dn).sum())
                        w += float(dn.sum())
                if w > 0:
                    dh_kpi["price_avg_w"] = self.num(wsum / w, 2)
            if "socmax" in dh:
                dh_kpi["tes_gwh"] = self.num(
                    sum(v for v in dh["socmax"].values() if v) / 1e3, 2
                )
            kpis["dh"] = dh_kpi

        # ---- balance validation (grouping correctness check) ----------------
        if gen_m is not None and chg_m is not None and "price" in H:
            for z in [fz]:
                supply = np.zeros(N_HOURS)
                if z in gen_m.index.get_level_values(0):
                    supply += gen_m.loc[z].to_numpy().sum(axis=0)
                supply += self.nimp.get(z, 0)
                if ll_m is not None and z in ll_m.index:
                    supply += ll_m.loc[z].to_numpy()
                use = load_total.copy()
                if z in chg_m.index.get_level_values(0):
                    use += chg_m.loc[z].to_numpy().sum(axis=0)
                if curt_m is not None and z in curt_m.index:
                    use += curt_m.loc[z].to_numpy()
                resid = np.abs(supply - use).max()
                if resid > 1.0:
                    warn(f"energy balance residual for {z}: max {resid:.2f} MW - check grouping")
                else:
                    print(f"  [ok] energy balance closes for {z} (max residual {resid:.4f} MW)")

        # ---- meta ------------------------------------------------------------
        wy = int(float(settings.get("weather_year", 0))) or None
        meta = {
            "schema": 1,
            "scenario": self.name,
            "sub_scenario": self.sub,
            "run_year": int(float(settings.get("run_year", 0))) or None,
            "weather_year": wy,
            "branch": settings.get("branch"),
            "model_version": settings.get("model_version"),
            "currency": "CHF",
            "units": {
                "power": "MW", "energy": "MWh", "price": "CHF/MWh",
                "heat": "MW th", "cost": "CHF", "co2": "tCO2",
            },
            "zones": self.zones,
            "focus": fz,
            "lines": self.lines,
            "dh_nodes": dh_nodes,
            "groups": {
                "supply": [{"k": k, "label": l, "color": c} for k, (l, c) in SUPPLY_GROUPS.items()],
                "charge": [{"k": k, "label": l, "color": c} for k, (l, c) in CHARGE_GROUPS.items()],
                "soc": [{"k": k, "label": l, "color": c} for k, (l, c) in SOC_GROUPS.items()],
                "dh": [{"k": k, "label": l, "color": c} for k, (l, c) in DH_GROUPS.items()],
                "dh_charge": [{"k": k, "label": l, "color": c} for k, (l, c) in DH_CHARGE_GROUPS.items()],
            },
            "settings": settings,
            "stats": {k: str(v) for k, v in stats.items()},
            "missing_files": self.missing,
            "created": _dt.datetime.now().isoformat(timespec="seconds"),
        }

        print(f"  converted in {time.time() - t0:.1f}s "
              f"({len(self.missing)} files missing)")
        return {"meta": meta, "kpis": kpis, "H": H, "dh": dh, "ann": ann}


def convert_run(run_dir: Path, out_dir: Path, sub_scenario: str | None) -> bool:
    print(f"converting {run_dir.name} ...")
    conv = RunConverter(run_dir, sub_scenario)
    payload = conv.build()
    if payload is None:
        return False
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_dir.name}_viewer.json.gz"
    raw = json.dumps(payload, separators=(",", ":"), allow_nan=False)
    with gzip.open(out_path, "wt", encoding="utf-8", compresslevel=9) as f:
        f.write(raw)
    print(f"  wrote {out_path}  ({out_path.stat().st_size / 1e6:.2f} MB gzipped, "
          f"{len(raw) / 1e6:.1f} MB raw)")
    return True


def looks_like_run(d: Path) -> bool:
    return d.is_dir() and (d / "settings.csv").exists() and (d / "gen.csv").exists()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="one run folder (output/<run>) or, with --all, "
                                 "the output/ folder containing many runs")
    ap.add_argument("--all", action="store_true",
                    help="convert every run folder found under PATH")
    ap.add_argument("--out-dir", default="plots",
                    help="where to write <run>_viewer.json.gz (default: plots)")
    ap.add_argument("--sub-scenario", default=None,
                    help="Scenarios column value to extract when a run holds several")
    args = ap.parse_args()

    path = Path(args.path)
    out_dir = Path(args.out_dir)
    if not path.exists():
        print(f"error: {path} does not exist")
        return 1

    if args.all:
        runs = [d for d in sorted(path.iterdir()) if looks_like_run(d)]
        if not runs:
            print(f"error: no run folders (with settings.csv + gen.csv) under {path}")
            return 1
        print(f"found {len(runs)} runs under {path}")
        ok = sum(convert_run(r, out_dir, args.sub_scenario) for r in runs)
        print(f"done: {ok}/{len(runs)} converted")
        return 0 if ok else 1

    if not looks_like_run(path):
        print(f"error: {path} does not look like a solved run "
              f"(needs settings.csv and gen.csv); use --all for a folder of runs")
        return 1
    return 0 if convert_run(path, out_dir, args.sub_scenario) else 1


if __name__ == "__main__":
    sys.exit(main())
