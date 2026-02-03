import numpy as np
import math

Map_plant_tech_cost_component = {  # cap_op (only generation capacity and operation costs) or cap_op_energy (additional energy capacity)
    
    # non-district heating technologies - investment and operation
    "pvrf": "cap_op",
    "windon": "cap_op",
    "battery": "cap_op_energy",
    "oil": "cap_op",
    "nuclear": "cap_op",

    "CCGTresmethane": "cap_op",
    "SCGTresmethane": "cap_op",
    "CCGTCCS": "cap_op",
    "SCGTfossil": "cap_op",
    "hydrogen": "cap_op_energy",

    # non-district heating technologies - only operation
    "dsr": "cap_op",
    "other": "cap_op",
    "dam": "cap_op_energy",
    "windof": "cap_op",
    "ev_flex": "cap_op",
    "gas": "cap_op",
    "electrolyzer" : "cap_op",
    "psp_open": "cap_op_energy",
    "biomass": "cap_op_energy",
    "psp_close": "cap_op_energy",
    "hardcoal": "cap_op",
    "heat_pump_households": "cap_op",
    "v2g": "cap_op_energy",

    # district heating technologies - investment and operation
    "resistive_heater": "cap_op",
    "heat_pump": "cap_op",
    "TTES_medium": "cap_op_energy",
    "PTES_large": "cap_op_energy",
    "gas_boiler": "cap_op",

    # district heating technologies - only operation
    "dsrTh": "cap_op",
}
tech_list = list(dict.keys(Map_plant_tech_cost_component))

TES_techs_list = ["TES", "TTES_medium", "PTES_large"]

Map_fuel_tech = {
    "resdiesel": ["resdiesel",],
    "resmethane": [ "CCGTresmethane" , "SCGTresmethane", "gas_boiler"], 
    "fossilmethane": ["CCGTCCS", "SCGTfossil", "gas_boiler"],
    "oil": ["oil"],
    "hydrogen": ["hydrogen"],
    "biomass": ["biomass",],
}

# Map_tech_fuel is reverse of Map_fuel_tech
Map_tech_fuel = {}
for fuel, tech_list in Map_fuel_tech.items():
    for tech in tech_list:
        Map_tech_fuel[tech] = fuel

# if a technology needs to track state of the storage 
tech_store_list = [
    "battery",
    "hydrogen",
    "psp_open",
    "psp_close",
    "v2g",
    "dam",
    "TES",
    "TTES_medium",
    "PTES_large",
]
#NOTE: if a tech is mentioned here, it should also be in Map_eff_in_tech, Map_eff_out_tech, Map_decaycoef_tech, Map_tech_startcondition, Map_plant_tech_cost_component


# distrcit heating technologies that are connected to the electric grid
techDH_connected_to_electric_grid_list = ["resistive_heater", "heat_pump", "combined_heatpower"]

# if a technology has pumping capability, i.e., if energy can be added/consumed
tech_store_pump_list = [
    "battery",
    "hydrogen",
    "psp_open",
    "psp_close",
    "ev_flex",
    "v2g",
    "dsr",
    "electrolyzer",
    "resistive_heater",
    "heat_pump",
    "heat_pump_households",
    "TTES_medium",
    "PTES_large",
]
# if one wants to force pump capacity= gen capacity (mostly simplifying investment decisions)
tech_store_equal_pump_max_gen_max_list = ["battery", "v2g", "hydrogen", "TES", "TTES_medium", "PTES_large",]
# if a technology has no electric generation capability (e.g. EVs)]
tech_p_no_gen = ["ev_flex", "electrolyzer", "resistive_heater", "heat_pump", "TES", "TTES_medium", "PTES_large", "heat_pump_households", "dsrTh", "gas_boiler"]
# if a technology has an infeed for utility scale plants (e.g. pvrf) #NOTE: add technologies here, if needed, eg. pvap (PV Alpine ...)
tech_infeed_all_list = ["pvrf", "windon", "windof", "ror", "pv"]
# if a technology has an infeed only for consumers  (e.g. pv)
tech_infeed_consumers_list = [
    "pv",
]
# # if a technology has an infeed only for core run (e.g. pvrf)
# tech_infeed_core_run_list = ["pvrf", "windon", "windof", "ror"]


# if a technology is a hydro plant
tech_hydro_list = ["dam", "psp_open", "psp_close"]

# if a store technology has inflow or outflow
tech_inflow_list = ["dam", "psp_open"]
# if a store technology has inflow or outflow
tech_outflow_list = ["psp_open", "v2g"]
tech_limited_energy_list = ["biomass", "other", "CCGTresmethane", "SCGTresmethane", "CCGTCCS", "SCGTfossil"]
tech_limited_energy_CH_list = ["other", ] #NOTE: update the list, maybe list can be empty # list of technologies which will have limitted energy in CH, but their fuel consumption is not directly limitted (fuel_limited_CH_list tracks the fuel limited technologies)
fuel_limited_CH_list = ["biomass", "resmethane", "fossilmethane", "oil"]
tech_limited_energy_and_require_storage_inv_no_soc = [] #NOTE: removed "liquidfuel", because now the fuel tracking is taking care of this. technologies that have limited energy and require storage investment (excluding biomass), 
                                                                       # but do not need to keep track of the state of charge (excl. batteries)

# list of asset technolgies owned by the consuemrs in NETFLEX that are to be imported to  demand time series.
# Note that batteries are not included here, because they have no consumption time series.
tech_demand_with_timeseries_netflex_list = ["fixed"]

# allowing v2g to exist, for later expansions
tech_demand_with_timeseries_netflex_model_list = ["fixed", "v2g"]

# all consuming technologies that are owned by the consumers in NETFLEX.
tech_demand_assets_netflex_list = ["fixed", "v2g"]

tech_demand_assets_shiftable_netflex_list = [] # v2g is not flexible in the way that EVs are (EVs are flexible within some time window, v2g is modelled more like a battery now)

tech_demand_assets_shiftable = tech_demand_assets_shiftable_netflex_list + ["electrolyzer"] # we didn't add ev_flex here, because its equations are defined separately


# consuming technologies that remain as inflexible demand (e.g. fixed fixed household demand) in the setting case of flex_dem_active_for_consumer = True
tech_demand_inflex_in_flex_dem_active_for_consumer = [
    "fixed",
]

# tariff data -------------------------------------------------------------------------------------
tariff_export_definitions = {
    "tariff_1": {
        "type": "TOU",
        "rates": {
            "section_1": {
                "h_in_day": [1, 7],
                "price": 0.10,
            },
            "section_2": {
                "h_in_day": [8, 20],
                "price": 0.15,
            },
            "section_3": {
                "h_in_day": [21, 24],
                "price": 0.10,
            },
        },
    },
    "tariff_AEW": {
        "type": "TOU",
        "rates": {
            "section_1": {
                "h_in_day": [1, 7],
                "price": 0.0323,
            },
            "section_2": {
                "h_in_day": [8, 20],
                "price": 0.0323,
            },
            "section_3": {
                "h_in_day": [21, 24],
                "price": 0.03,
            },
        },  # NOTE: these values appear highly suspicious, but are taken from the AEW website; https://www.aew.ch/sites/default/files/2022-08/AEW_Ruecklieferung_Herkunftsnachweis_2023.pdf
    },
    "tariff_AEW2": {
        "type": "TOU",
        "rates": {
            "flat_infeed_compensation": {
                "weeks": list(range(1, 53 + 1)),
                "day_in_week": {
                    "mon": list(range(1, 24 + 1)),
                    "tue": list(range(1, 24 + 1)),
                    "wed": list(range(1, 24 + 1)),
                    "thu": list(range(1, 24 + 1)),
                    "fri": list(range(1, 24 + 1)),
                    "sat": list(range(1, 24 + 1)),
                    "sun": list(range(1, 24 + 1)),
                },
                "price": 3.23
                * 10,  # target unit: CHF/MWh. input is rappen/kWh * 10 (rappen = 0.01, MWh = 1000 kWh)
            },
        },
    },
}


tariff_import_definitions = {
    "tariff_1": {
        "type": "TOU",
        "rates": {
            "section_1": {
                "h_in_day": [1, 7],
                "price": 0.20,
            },
            "section_2": {
                "h_in_day": [8, 20],
                "price": 0.30,
            },
            "section_3": {
                "h_in_day": [21, 24],
                "price": 0.20,
            },
        },
    },
    "tariff_AEW": {
        "type": "TOU",
        "rates": {
            "section_1": {
                "h_in_day": [1, 7],
                "price": 0.2117,
            },
            "section_2": {
                "h_in_day": [8, 19],
                "price": 0.264,
            },
            "section_3": {
                "h_in_day": [20, 24],
                "price": 0.2117,
            },
        },
    },  # source: "Classic" tariff from https://www.aew.ch/sites/default/files/2022-08/AEW_Classic_2023.pdf
    "tariff_AEW2": {
        "type": "TOU",
        "rates": {
            "low_winter": {
                "weeks": list(range(40, 53 + 1)) + list(range(1, 13 + 1)),
                "day_in_week": {
                    "mon": list(range(1, 7 + 1)) + list(range(21, 24 + 1)),
                    "tue": list(range(1, 7 + 1)) + list(range(21, 24 + 1)),
                    "wed": list(range(1, 7 + 1)) + list(range(21, 24 + 1)),
                    "thu": list(range(1, 7 + 1)) + list(range(21, 24 + 1)),
                    "fri": list(range(1, 7 + 1)) + list(range(21, 24 + 1)),
                    "sat": list(range(1, 7 + 1)) + list(range(21, 24 + 1)),
                    "sun": list(range(1, 24 + 1)),
                },
                "price": 21.17
                * 10,  # target unit: CHF/MWh. input is rappen/kWh * 10 (rappen = 0.01 CHF and MWh = 1000 kWh)
            },
            "high_winter": {
                "weeks": list(range(40, 53 + 1)) + list(range(1, 13 + 1)),
                "day_in_week": {
                    "mon": list(range(8, 20 + 1)),
                    "tue": list(range(8, 20 + 1)),
                    "wed": list(range(8, 20 + 1)),
                    "thu": list(range(8, 20 + 1)),
                    "fri": list(range(8, 20 + 1)),
                    "sat": list(range(8, 20 + 1)),
                    "sun": [],
                },
                "price": 26.40
                * 10,  # target unit: CHF/MWh. input is rappen/kWh * 10 (rappen = 0.01
            },
            "low_summer": {
                "weeks": list(range(14, 39 + 1)),
                "day_in_week": {
                    "mon": list(range(1, 7 + 1)) + list(range(21, 24 + 1)),
                    "tue": list(range(1, 7 + 1)) + list(range(21, 24 + 1)),
                    "wed": list(range(1, 7 + 1)) + list(range(21, 24 + 1)),
                    "thu": list(range(1, 7 + 1)) + list(range(21, 24 + 1)),
                    "fri": list(range(1, 7 + 1)) + list(range(21, 24 + 1)),
                    "sat": list(range(1, 7 + 1)) + list(range(21, 24 + 1)),
                    "sun": list(range(1, 24 + 1)),
                },
                "price": 21.17
                * 10,  # target unit: CHF/MWh. input is rappen/kWh * 10 (rappen = 0.01, MWh = 1000 kWh)
            },
            "high_summer": {
                "weeks": list(range(14, 39 + 1)),
                "day_in_week": {
                    "mon": list(range(8, 20 + 1)),
                    "tue": list(range(8, 20 + 1)),
                    "wed": list(range(8, 20 + 1)),
                    "thu": list(range(8, 20 + 1)),
                    "fri": list(range(8, 20 + 1)),
                    "sat": list(range(8, 20 + 1)),
                    "sun": [],
                },
                "price": 26.40
                * 10,  # target unit: CHF/MWh. input is rappen/kWh * 10 (rappen = 0.01, MWh = 1000 kWh)
            },
        },
    },
}

# commented out, because uncalled data ---------------------
# # costs - investment in energy capacity
# cost_data_inv_e_int = {
#     "biomass": 0,
#     "battery": 0,
#     "bt": 0,
#     "dam": 0,
#     "psp_open": 0,
#     "psp_close": 0,
#     "v1g": 0,
#     "v2g": 0,
#     "hp": 0,

#     "CCGTresmethane": 0,
#     "SCGTresmethane": 0,
#     "CCGTCCS": 0,
#     "SCGTfossil": 0,
#     "hydrogen": 0,   # Moretti paper, table 5S #: should it be 0?
#     "liquidfuel": 0, # There is per-existing liquid fuel storage capacity in CH.
# } 

# calibration of operational costs for every technology
# cost_data_opr_qdr[tech] is the quadratic term of the operational cost (values taken from SA calibration process)
cost_data_opr_qdr = {
    "pv": 0,  # 2 * 0
    "pvrf": 0,  # 2 * 0
    "gas": 2 * 0.001,  # 2 * 0.002
    "biomass": 0,  # 2 * 0.00004
    "battery": 0,  # 2 * 0
    "dam": 0,  # 2 * 0
    "psp_open": 0,  # 2 * 0
    "psp_close": 0,  # 2 * 0
    "v2g": 0,  # 2 * 0
    "oil": 2 * 0.04,  # 2 * 0.04
    "dsr": 0,  # 2 * 0
    "hardcoal": 2 * 0.001,  # 2 * 0.002
    "nuclear": 0,  # 2 * 0.00004
    "lignite": 0,  # 2 * 0.00004
    "windon": 0,  # 2 * 0
    "other": 0,  # 2 * 0
    "electrolyzer": 0,  # 2 * 0

    'CCGTresmethane' : 2 * 0.001,
    'SCGTresmethane' : 2 * 0.001,
    'CCGTCCS' : 2 * 0.001,
    'SCGTfossil' : 2 * 0.001,
    'battery' : 2 * 0.001,
    'hydrogen' : 2 * 0.001,
}
# defining the start condtion of storage technologies (to be assigned to all plants of this type of technology, not alreay having a value)
Map_tech_startcondition = {
    "v2g": 0.5,
    "dam": 0.95,
    "psp_open": 0.95,
    "psp_close": 0.95,
    "battery": 0.95,
    "hydrogen": 0.95, 
    "TTES_medium": 0.99, # NOTE: This number is not used as in the model 
    "PTES_large": 0.99, # NOTE: This number is not used as in the model 
}

# cost of lost load [$/MWh], will be used as default value for all consumers that have no lost load cost defined
lostlost_cost = 10000

ch_subnode_list  = ["CH0" + str(i) for i in range(1, 8)]	 # list of the subnodes/subregions of Switzerland (all to be aggregated to CH00)

def add_additional_batteries(
    additional_battery_nodes,
    Plant_list,
    Plant_investment_non_RES_CH_list,
    Plant_investment_RES_CH_data,
    Map_plant_node,
    Map_plant_tech,
    Map_consumer_plant
):
    """
    Add battery investment candidates for additional nodes.
    Adds entries to Plant_investment_RES_CH_data DataFrame with proper formatting.
    """
    import pandas as pd
    
    for node in additional_battery_nodes:
        # Extract the base node code (e.g., "IT01" -> "IT00", "FR01" -> "FR00")
        base_node = node[:2] + "00"
        plant_name = f"{node}_battery"
        
        # Check if this plant already exists
        if plant_name in Plant_investment_RES_CH_data.index:
            print(f"Battery {plant_name} already exists in investment candidates. Skipping.")
            continue
        
        # Create new row for the battery following the CSV format
        new_battery = pd.DataFrame({
            'node': [base_node],
            'market': [base_node],
            'plant_type': ['cap_op_energy'],
            'tech': ['battery'],
            'upperwn': [''],
            'lowerwn': [''],
            'eta': [''],
            'eta_pump': [''],
            'n_redispatch': [base_node],
            'gen_max_limit': [100000.0],
            'energy_max_limit': [float('inf')],
            'fuel_switching': ['']
        }, index=[plant_name])
        
        # Add to the dataframe
        Plant_investment_RES_CH_data = pd.concat([Plant_investment_RES_CH_data, new_battery])
        
        # Update lists
        Plant_list.append(plant_name)
        Plant_investment_non_RES_CH_list.append(plant_name)
        
        # Update maps
        Map_plant_node[plant_name] = base_node
        Map_plant_tech[plant_name] = "battery"
        
        # Append to consumer plant list
        Map_consumer_plant.setdefault(base_node, []).append(plant_name)
        
        print(f"Added battery investment candidate: {plant_name} at node {base_node}")
    
    return Plant_investment_RES_CH_data

def reduce_fr_be_demand(Demand_data, reduce_BE_FR_day_nine_and_ten_demand_to_percent):
    # Loop over target nodes
    for node in ["FR00_fixedconsumer", "BE00_fixedconsumer"]:
        for t in range(193, 241):  # inclusive 193 to 240 # corresponds to day 9 and 10
            key = (node, "fixed", f"t_{t}")
            if key in Demand_data:  # Only modify if it exists
                Demand_data[key] *= reduce_BE_FR_day_nine_and_ten_demand_to_percent
