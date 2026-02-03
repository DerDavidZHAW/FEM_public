import aggregation.aggregate_new as agg
# aggregate_new is a new version of aggregate by David which he created to fix a bug but he introduced lots of ugly code
# import aggregation.aggregate as agg
import utils.trade_curtailment_adjustment
import os
import plotly.io as pio
import pandas as pd
pio.renderers.default = "browser"

# Aggregation scenarios --------------------------------------------------------------------------------
scenarios_to_agg =[
    "2035_aa",
    "2035_ar",
    "2035_st",
    "2050_aa",
    "2050_ar",
    "2050_st",
    ]


agg_name = "20251031_robust_results"

# Check if all scenarios have non-empty NodeDH_list --------------------------------------------------------------------------------

def check_nodedh_availability(scenarios_to_agg, results_to_agg_dir="output/"):
    """Check if all scenarios have non-empty NodeDH_list in their settings."""
    all_have_nodedh = True
    for scenario in scenarios_to_agg:
        settings_path = os.path.join(results_to_agg_dir, scenario, "settings.csv")
        if os.path.exists(settings_path):
            settings_df = pd.read_csv(settings_path)
            settings_df.set_index("Item", inplace=True)
            nodedh_value = str(settings_df.loc["NodeDH_list"].iloc[0])
            # Check if it's an empty list (either "[]" or empty string)
            if nodedh_value == "[]" or nodedh_value == "" or nodedh_value == "nan":
                all_have_nodedh = False
                print(f"Scenario '{scenario}' has empty NodeDH_list")
                break
        else:
            print(f"Warning: settings.csv not found for scenario '{scenario}'")
            all_have_nodedh = False
            break
    return all_have_nodedh

all_scenarios_have_dh = check_nodedh_availability(scenarios_to_agg)
print(f"All scenarios have district heating data: {all_scenarios_have_dh}")

# Aggergation items --------------------------------------------------------------------------------
# params and vars to aggregate across scenarios as keys, and the type of aggregation as values (sum, mean, min, max, or several of them)
temporal_all = ["hour", "day", "week", "month", "season", "year"]
temporal_ym = ["month", "year"]
temporal_hy = ["hour", "year"]
temporal_hw = ["hour", "week"]
temporal_hmy = ["hour", "month", "year"]
temporal_hsy = ["hour", "season", "year"]

params_vars_to_agg = {
    "statistics": {"type": "none", "temporal": False, "mappings": False},
    "settings": {"type": "none", "temporal": False, "mappings": False},
    "gen_max": {"type": "sum", "temporal": False, "mappings": False},
    "pmp_max": {"type": "sum", "temporal": False, "mappings": False},
    "gen_max_infeedp": {"type": "sum", "temporal": False, "mappings": False},
    "gen_energy_max": {"type": "sum", "temporal": False, "mappings": False},
    # investment costs ---------------------
    "investment_genmax_slp": {"type": "sum", "temporal": False, "mappings": False},
    "investment_emax_slp": {"type": "sum", "temporal": False, "mappings": False},
    "operation_slp": {"type": "sum", "temporal": False, "mappings": False},
    "investment_fuel_storage_slp": {"type": "sum", "temporal": False, "mappings": False},
    # --------------------------------------

    "fuel_consumption_of_plant": {
        "type": "sum", 
        "temporal": temporal_ym,
         "mappings":  [
            "temporal",
        ],
    },
    "fuel_consumption_of_fuel":
    {
        "type": "sum",
        "temporal": temporal_ym,
        "mappings": [
            "temporal",
        ],
    },
    "lostload": {
        "type": "sum",
        "temporal": temporal_hmy,
        "mappings": [
            "temporal",
        ],
    },
    "Export": {
        "type": "sum",
        "temporal": temporal_hsy,
        "mappings": [
            "temporal",
        ],
    },

    "demand": {
        "type": "sum",
        "temporal": temporal_hy,
        "mappings": ["temporal", "Map_node_consumer", "Map_type_consumer"],
    },
    "gen": {
        "type": "sum",
        "temporal": temporal_hy,
        "mappings": ["temporal", "Map_node_plant"],
    },
    "energy_balance_dual": {
        "type": "mean",
        "temporal": temporal_hy,
        "mappings": [
            "temporal",
        ],
    }, 
    "storage_charge": { 
        "type": "sum",
        "temporal": temporal_hy,
        "mappings": ["temporal", "Map_node_plant"],
    },
    "EV_inflexible_demand": {
        "type": "sum",
        "temporal": temporal_hy,
        "mappings": ["temporal"],
    },
    "HP_inflexible_demand": {
        "type": "sum",
        "temporal": temporal_hy,
        "mappings": ["temporal"],
    },

    # "Constraint_winter_limit_dual": {"type": "none", "temporal": False, "mappings": False},
    "curtailment": {
        "type": "sum",
        "temporal": temporal_hy,
        "mappings": [
            "temporal",
        ],
    },

    "infeed": {
        "type": "sum",
        "temporal": temporal_hy,
        "mappings": [
            "temporal",
        ],
    },
    "soc": {
        "type": "sum",
        "temporal": temporal_hw,
        "mappings": ["temporal", "Map_node_plant"],
    },
}

# District heating items (separated from main dict)
params_vars_to_agg_DH = {
    "genTh_max": {"type": "sum", "temporal": False, "mappings": False},
    "pumpTh_max": {"type": "sum", "temporal": False, "mappings": False},
    "gen_energyTh_max": {"type": "sum", "temporal": False, "mappings": False},
    # investment costs ---------------------
    "investment_genmax_slpTh": {"type": "sum", "temporal": False, "mappings": False},
    "investment_emax_slpTh": {"type": "sum", "temporal": False, "mappings": False},
    "operation_slpTh": {"type": "sum", "temporal": False, "mappings": False},
    # --------------------------------------
    "genTh": {
        "type": "sum",
        "temporal": temporal_hy,
        "mappings": ["temporal", "Map_node_plant"],
    },

    "demandDH": {
        "type": "sum",
        "temporal": temporal_hy,
        "mappings": ["temporal",],
    },

    "dsrThDev": {
        "type": "sum",
        "temporal": temporal_hy,
        "mappings": ["temporal",],
    },
}

# Merge district heating items if all scenarios have DH data
if all_scenarios_have_dh:
    print("Merging district heating items into main aggregation dictionary...")
    params_vars_to_agg.update(params_vars_to_agg_DH)
else:
    print("Skipping district heating items as not all scenarios have DH data...")


indicators_to_agg = {
    "price_weighted": [
        "mean",
    ],
}

# --------------------------------------------------------------------------------
output_dir = "output/aggregated/" + agg_name + "/"
results_to_agg_dir = f"output/"

# Main code --------------------------------------------------------------------------------
# update mappings based on the given scenarios
agg.mappings_merge(scenarios_to_agg, results_to_agg_dir)

# find subscearios for each scenario
map_scen_subscen = agg.find_subscenarios(scenarios_to_agg, results_to_agg_dir)


for item, agg_type in params_vars_to_agg.items():
    print("Aggregating " + item + 40 * "...")
    print(agg_type)
    agg.aggregate_params_vars(scenarios_to_agg, item, agg_type, output_dir, map_scen_subscen)

for item, agg_type in indicators_to_agg.items():
    print("Aggregating " + item + 40 * "...")
    print(agg_type)
    agg.aggregate_indicators(scenarios_to_agg, item, agg_type, output_dir, map_scen_subscen)

agg.op_inv_exp_imp_cost_calc(scenarios_to_agg, output_dir, map_scen_subscen)
agg.op_inv_exp_imp_cost_plot(scenarios_to_agg, map_scen_subscen, output_dir)
agg.merge_gen_dem_ch(scenarios_to_agg, output_dir, map_scen_subscen)
agg.merge_gen_dem_ch_hourly(scenarios_to_agg, output_dir, map_scen_subscen)

# utils.trade_curtailment_adjustment.trade_curtailment_adjustment(agg_name)

print("Aggregation complete.")
