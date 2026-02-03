#NOTE: the definitions are not yet adjusted for the fact that now the stochastic version is the main version.
# in the stochastic version, some dictinoaries may have a new dimenstion in their keys (scneario name).
# for instance, DemandDH_data has a new dimension in the keys, which is the scenario name, e.g., {('DH01', "t_6553", "NTC30"): 4000.0}
# ------------------------------------------------------------------------------------------------------------------------
# ------------------------------------ define lists and dictionaries etc. ------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------
# list of time steps (e.g. [t_6553, t_6554, ..., t_8760, t_1, t_2, ..., t_6552])
T_list = []

# # list of nodes to be included in the model (TYNDP data will be read only for the given region_list).
# Node_list = [] # for some reason, do not activate this, believe me!

# Change region_list in mappings.py to include more/less nodes.
# ---------------------------------------------------------------------------
# all plants' lists and dictionaries (central and consumers') ---------------
# ---------------------------------------------------------------------------
# list of all plants (e.g. ['hp_ID300', 'ev_ID300'])
Plant_list = []

# list of all plants with inflow (e.g. ['dam_CH_01', 'psp_open_CH_01'])
Plant_inflow_list = []

# list of all plants with outflow (e.g. ['dam_CH_01', 'psp_open_CH_01'])
Plant_outflow_list = []

# list of all technologies (e.g. ['psp_open', 'hp', 'ev', 'pv'])
Tech_list = []

# dictionary of plant technologies (e.g. {'hp_ID300': 'hp', 'ev_ID300': 'ev'})
Map_plant_tech = {}

# dictionary of technologies and their plants (e.g. {'hp': ['hp_ID300'], 'ev': ['ev_ID300'], 'pv': ['pv_ID300']})
Map_tech_plant = {}

# dictionary of plant nodes (e.g. {'hp_ID300': 'CH_01', 'ev_ID300': 'CH_01'})
Map_plant_node = {}

Avail_plant = {}  # dictionary of available capacities for all plants

# dictionary of inflow data for all related plants, i.e. hydro plants (e.g. Inflow_data['dam_CH00', "t_1"]: 2]}), im MWh
Inflow_data = {}

Outflow_data = {}  # dictionary of inflow data for all related plants, e.g., EVs

# Infeed = {} # dictionary of Infeed data for all related plants. e.g., Infeed[node, tech, t] = 123.2 where node is nodes in the model, tech is in tech_infeed_list, t is the time step

# dictionary of Infeed data for all related consumers. Infeed_consumers[c,t]
Infeed_consumers = {}

# dictionary of line trade prices for CH_only mode. Line_trade_price[(line, t)] = price (EUR/MWh)
Line_trade_price = {}

# dictionary that assigns a    charging efficiency to each plant. This matters for plants with some sort of inflow to a storage (dam, PSP, battery, EV etc.) (e.g. {'ev_ID300': 0.9})
Map_eff_in_plant = {}

# dictionary that assigns a discharging efficiency to each plant. This matters for plants with some sort of outflow from a storage (dam, PSP, battery, EV etc.) (e.g. {'ev_ID300': 0.9})
Map_eff_out_plant = {}

Map_node_plant = {}
# determines for each node, the plants that are connected to it. Calculated based on Node_list Plant_list Map_plant_node. useful for constraints
# sample output Map_node_plant = {'CH_01': ['p_pv_1', 'p_gas_1', 'p_limited_energy_1'], 'EU_01': ['battery_1']}

# for each node, which plants are connected to that node - needs Node_list Plant_list Map_plant_node - useful for constraints - e.g., {'CH_01': ['consumer_01'], 'EU_01': ['consumer_02']}
Map_node_consumer = {}

# list of all plants that are not owned by active consumers (e.g. ['gas_AT00',...])
Plant_list_no_consumer = []

# dictionary that describes energy limited plants. The keys are plant (asset) names and values are generation within the time window (e.g. {'p_limited_energy_1': 0.0}). Later, more details should be included, e.g., several time windows (e.g. seasons) with given generation values.
Data_plant_energy_limited = {}

# dictionary that describes the start condition (between 0 1) of each (storage) plant. The keys are plant (asset) names and values are the start condition (e.g. {'AT00_dam': 0.05}). Later, more details should be included, e.g., several time windows (e.g. seasons) with given start conditions.
Map_plant_startcondition = {}
# Map_plant_startcondition and Plant_end_condotion will be the same in an annual run.

# dictionary that describes the end   condition (between 0 1) of each (storage) plant. The keys are plant (asset) names and values are the end condition (e.g. {'AT00_dam': 0.95}). Later, more details should be included, e.g., several time windows (e.g. seasons) with given end conditions.
Map_plant_endcondition = {}
# Map_plant_startcondition and Plant_end_condotion will be the same in an annual run.
# ---------------------------------------------------------------------------
# lists and dictionaries related to lines -----------------------------------
# ---------------------------------------------------------------------------
LineATC_list = []  # list of all lines (NTC and DC lines)

Map_line_node = {}  # dictionary of line nodes

# dictionary of export limits for all lines (trade from starting to end node) - must be non-negative
ATC_exportlimit = {}

# dictionary of import limits for all lines (trade from end to starting node) - must be non-negative
ATC_importlimit = {}

# determines for each node, the lines(ATC) are connected to it that are start node  - needs Map_line_node Node_list - useful for constraints
Map_node_exportinglineATC = {}
# sample output  for Map_line_node ={"line_01_CH01_EU01" : {"start_node": "CH_01", "end_node": "EU_01"}} - Map_node_exportinglineATC={'CH_01': ['line_01_CH01_EU01'], 'EU_01': []} - Map_node_importinglineATC = {'CH_01': [], 'EU_01': ['line_01_CH01_EU01']}

# determines for each node, the lines(ATC) are connected to it that are end node  - needs Map_line_node Node_list - useful for constraints
Map_node_importinglineATC = {}

# ---------------------------------------------------------------------------
# consumers' lists and dictionaries -----------------------------------------
# ---------------------------------------------------------------------------
# update all below with them=+netflex
Consumer_list = []  # list of all consumers (e.g. ['ID1', 'ID300'])

# dictionary for each consumer lists its assets (e.g. {'ID300': ['hp_ID300', 'ev_ID300', 'pv_ID300']})
Map_consumer_plant = {}

# dictionary for each consumer lists the node it is connected to (e.g. {'ID300': 'CH_01'})
Map_consumer_node = {}

# dictionary that assigns an optimization type to each consumer (either "maximize_utility" or "minimize_cost")
Map_consumer_optimization = {}

# dictionary that assigns a maximum import limit to each consumer (e.g. {'ID300': 20})
Consumer_import_max = {}

# dictionary that assigns a maximum export limit to each consumer (e.g. {'ID300': 20})
Consumer_export_max = {}

# dictionary that assigns a utility coefficient to each consumer's flexible demand.
Map_consumer_utilitycoeff = {}
# NOTE: The data abot Map_consumer_utilitycoeff should be added to consumer json files, and then read from them in the model.
# should be defined only if the Map_consumer_optimization[consumer]=="maximize_utility"
# utility[consumer][plant] = c0 + c1*(avg_plantconsumption) + c2*(avg_plantconsumption)^2
# the keys are consumer names. The values for every consumer are are dictionaries where the keys are plant names.
# The values for every plant are dictionaries where the keys are "constant", "a" and "b".
# The values for "constant", "a" and "b" are lists, where the length of the list is the number of time horizons defined for the plant (in Data_plant_flex_d_within_window[plant]["time_horizon"]).
# example Map_consumer_utilityfunction["consumer_01"]["hp_11"]["constant"][0] is the constant term of the utility function for the first time horizon of the heat pump "hp_11"  of the consumer "consumer_01"
# Map_consumer_utilitycoeff = {
#     "consumer_01" :
#         {"hp_11" :
#             {"c0": [0, 0, 0],
#             "c1": [10.1, 1.2, 10.3],
#             "c2": [-1, -1, -1]
#             },
#         "hp_12" :
#             {"c0": [0, 0],
#             "c1": [1.4, 1.5],
#             "c2": [-1, -1]
#             },

# dictionary that describes flexibility characteristics of flexible assets. The keys are plant (asset) names.
Data_plant_flex_d_within_window = {}
# The value will be another dictionary with keys "time_horizon" "energy" and "max_demand".
# this is useful for example for a heat pump that can only consume a certain amount of energy per day
# The values for "time_horizon" are lists of tuples (start, end) where start and end are integers between 1 and T.
# The values for "energy" and "max_demand" are lists of floats >= 0.

# dictionary consisting of consumers fixed demand for time steps (e.g. ["ID300","t_1"] = 1.1) in MW
Demand_data = {}

# original data set of demand from TYNDP (no correction applied)
Demand_data_TYNDP = {}

# dictionary consisting of consumers export (feed-in to the grid) tariff for time steps (e.g. ["ID300","t_1"] = 10) in EUR/MWh
tariff_export_hourly = {}

# dictionary consisting of consumers import (consumption) tariff for time steps (e.g. ["ID300","t_1"] = 20) in EUR/MWh
tariff_import_hourly = {}

# list of all consumers that have at least one plant (e.g. ['ID300'])
Consumer_list_with_plants = []

# totoal flex demand in each duration for each consumer (used in central model)
flex_demand_in_durations = {}

# ---------------------------------------------------------------------------
# to be possibly fixed in the model -----------------------------------------
# ---------------------------------------------------------------------------
# dictionary for all plants's names as keys and generation capacity in MW as values (e.g. { 'CH00_psp_open': 4000.0
Plant_capacity_gen = {}
# dictionary for all plants's names as keys and pumping capacity in MW as values (e.g. { 'CH00_psp_open': 4000.0
Plant_capacity_pmp = {}
# dictionary for all plants's names as keys and its direct storage capacity as values in MWh (e.g. { 'CH00_psp_open': 14000.0
Plant_capacity_strg = {}
# EV ----------------------------------------
# dictionary that to each EV plant assigns a maximum charging capacity
gen_max_EV_BT_data = {}
# dictionary that to each EV plant assigns a maximum discharging capacity
pmp_max_EV_BT_data = {}
# dictionary that to each EV plant assigns a maximum charging energy
gen_energy_max_EV_BT_data = {}

# list of infeed technologies used in the core run (e.g. ['pvrf', 'windon', 'windof']). If consumers' are decentrialized, this list should not include pv (that belongs to consuemrs).
tech_infeed_core_run_list = []

imported_all_consumers = {}
exported_all_consumers = {}
scenario_name = ""


Infeed_RES_TYNDP = {}

# The list of battery(ies) that replace a group of batteries owned by NETFLEX customers, only if single_large_battery is activated.
Plant_list_rep_bat = []

# list of RES plants in CH that are considered for investments (on top of the existing ones in the active ch_policy)
# e.g., ['CH01_pvrf', "CH01_windon"]
Plant_investment_RES_CH_list = []

Plant_investment_non_RES_CH_list = []  # list of non-RES plants in CH that are considered for investments


# dictionary that include the intercept value of investment cost (EU/MW),  for each technology, e.g., 
#cost_data_inv_gen_int = {"pv": 0,     "gas": 0,  "limited_energy": 100000000 , "battery": 0,
cost_data_inv_gen_int = {}

# dictionary that include the slope value of investment cost (EU/MW),  for each technology, e.g., 
# cost_data_inv_gen_slp = {"pv": 15,    "gas": 10, "limited_energy": 100000000, "battery": 10,
cost_data_inv_gen_slp = {}

# cost of investing in energy capacity (EU/MWh) for each technology that has a energy storage capacity
cost_data_inv_e_slp = {}

# cost of investing in fuel storage capacity (EU/MWh of storage capacity) for each technology (that has a fuel storage capacity in CH, e.g., biomass, but NOT battery)
cost_data_inv_fuel_storage_slp = {}

# cost of investing in discharge capacity (CHF/MW of discharge capacity) for each technology (that has a discharge capacity, e.g., hydrogen storage). Right now, only hydrogen has this because here, the facilities for generating hydrogen and storing hydrogen are considered separately.
cost_data_inv_discharge_slp = {}

# dictionary that include the intercept value of operation cost (EU/MWh),  for each technology
cost_data_opr_int = {}

# dictionary that include the slope value of operation cost (EU/MWh),  for each technology
cost_data_opr_slp = {}

# dictionary that includes the emission factor (tCO2/MWh_output) for each technology, accounting for efficiency
# This is emission_factor_input / efficiency, so it represents emissions per MWh of electricity generated
emission_factor_per_MWh = {}

# dictionary that assigns a maximum import limit to each consumer (e.g. {'ID300': 20})
# a dictionary defined over nodes and techs (op_cost_n_tech_calibration[(node, tech)]) 
# which is the calibration coefficient for relative costs of operation between regions
# more specifically, used to calibrate model.operation_slp which is defined over power plants
op_cost_n_tech_calibration = {}


Infeedplant_list = []  # list of all infeed plants, excluding NETFLEX (e.g. ['pvrf_CH01', 'windon_CH01'])

# a dictionary that keeps the value of pre-existing RES plants in each region, to be used for 
# -- calculation of infeed and 
# -- to be reported in the results so that total CH RES capacity can be calculted in the reportings/aggregations
gen_max_RES_pre_existing_no_NETFLEX = {}


# a dictionary that maps res plants to their techs, e.g., {"CH01_pvrf": "pvrf"}
# -- to be used eventually for reportings/aggregations
Map_infeedplant_tech = {}

# a dictionary that maps res plants to their nodes, e.g., {"AT00_pvrf": "AT00"}
Map_infeedplant_node = {}

# a dictionary with numerical information about potential investment capacity per candiate plant
# the values for gen_max_limit: the maximum generation capacity that can be installed
# the values for energy_max_limit: the maximum energy capacity that can be installed (for storage plants)
# e.g. {'gen_max_limit': {'CH01_pvrf': inf, 'CH01_windon': 314.2857143, 'CH01_biomassinv': 10.0, ...},
#       'energy_max_limit': {'CH01_pvrf': inf, 'CH01_windon': 314.2857143}, 'CH01_biomassinv': 87600.0, ...}
Plant_investment_RES_CH_data = {}



P_list_fuelswitching_plants = []  # list of all plants that are considered as one fuel switching plant (e.g. ['CH00_switchliquidfuel', 'CH00_switchSCGTfossil'])


# --------------------------------- district heating definitions ---------------------------------
# dictionary consisting of district heats' thermal demand time series (e.g. ["DH01","t_6553"] = 101.2) in MW(h) thermal
DemandDH_data = {}

# list of all district heating plants (e.g. ['resistive_DH01', 'resistive_DH02'])
PlantDH_list = []  

# dictionary for all district heating plants's names as keys and generation capacity in MW as values (e.g. { ('CH00_resistive_DH', NTC30): 4000.0})
PlantDH_capacity = {}  

 # a dictionary that maps plants in the district heating system to their ""electric nodes"", e.g., {"CH01_resistive_DH01": "CH01"}
Map_plantDH_nodeEl = {} 

# a dictionary that maps plants in the district heating system to their ""district heating"" nodes, e.g., {"CH01_resistive_DH01": "DH01"}
Map_plantDH_nodeDH = {}  

# a dictionary that maps plants in the district heating system to their techs, e.g., {"CH01_resistive_DH01": "resistive"}
Map_plantDH_tech = {}

# dictionary stores characteristics of the district heating plants, other than ...
# mappings to techs and nodes (values stored in e.g., PlantDH_capacity, Map_plantDH_nodeEl, Map_plantDH_nodeDH, Map_plantDH_tech)
# stored values may include efficiency of the plant, etc. 
# The keys are plant names and the feature. The dictionary values are corresponding values.
# example data: {('resistive_DH01', 'efficiency'):  0.9, ('resistive_DH01', 'cost'):  1000, ...}
PlantDH_data_remaining = {}  

# dictionary that assigns a plant (in district heating) to each node in the district heating system
Map_nodeDH_plantDH = {}  

Fuel_limits_data = {}  # dictionary, indicating import, storage, production capacities for each fuel type (in)
                       # keys fuel types and values are themselves dictionaries with one of the following keys, namely "import_capacity_annual", "production_capacity_CH", "storage_potential_capacity", and value read from the csv file

PlantDH_investment_STES_list = []  # list of all district heating plants that are considered for investments in STES, seasonal thermal storage    

Plant_investment_data_STES = {}  # dictionary that includes data for STES plants candidates for investment

# the days required to charge and discharge PTES
storage_to_charge_ratio = []

# the KVA infeed at the individual nodes
KVAinfeed = {}

# --------------------------------- EV definitions ---------------------------------

# dictionary that allocates the required energy to charge all EVs for each week of the year in MW
EV_weekly_energy_consumption_data = {}

# dictionary that allocates to each hour of the year the maximum possible charging power of all EVs in MW
# I.e. the power with which all EVs could charge that are plugged in (not driving) and not fully charged
EV_charging_power_rate = {}

# dictionary that stores the inflexible EV demand timeseries (hourly consumption in MWh)
# This is the portion of EV consumption that charges according to a fixed profile (not optimizable)
# Keys are (node, timestep, scenario) tuples, values are demand in MWh
# This allows separate tracking and visualization of inflexible EV consumption apart from other inflexible demand
EV_inflexible_demand_data = {}

# dictionary that stores the inflexible household heat pump demand timeseries (hourly consumption in MWh)
# This is the portion of household HP consumption that operates according to a fixed profile (not participating in flexibility)
# Keys are (node, timestep, scenario) tuples, values are demand in MWh
# This allows separate tracking and visualization of inflexible HP consumption apart from other inflexible demand
HP_inflexible_demand_data = {}

# dictionary that allocates to each hour of the year the maximum possible charging and discharging rate for the representative V2G in MW
V2G_charging_power_rate = {}  

# dictionary that allocates to each representative V2G its storage capacity in MWh
V2G_storage_capacity = {}  
# --------------------------------- heat pumps -------------------------------------

# the Building Archetype hourly electric consumption data in MWh
BA_el_con = {}

# the Building Archetype hourly thermal consumption data in MWh
BA_th_con = {}

# the Building Archetype thermal limit in MWh which represents how much the building can be heated up or cooled down stepping away from the
# comfort temperature allowing for the use of the thermal inertia
BA_th_lim = {}

# the hourly Coefficient Of Performance (COP) of the heat pumps for the private housholds. It varies as it depends (among other things) on the outside temperature
COP = {}

# the names of the building archetypes considered
BA_names = []

# the maximum heating capacity of the heat pumps in MW
BA_max_heating_capacity = {}

# Data for multi-step lost load cost
lost_load_cost = {}

# The share of households that heat flexibly
flexible_household_heatpump_share = []