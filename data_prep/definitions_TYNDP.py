# # ------------------------------------------------------------------------
# # read the data - from TYNDP sources -------------------------------------
# # ------------------------------------------------------------------------
# definitions
# list of consumers from TYNDP. Every node is assumed to be a consumer and named as node_fixedconsumer, e.g. BE00_fixedconsumer
Consumer_list_TYNDP = []
# dictionary for each consumer lists the node it is connected to (e.g. {'BE00_fixedconsumer': 'BE_00'})
Map_consumer_node_TYNDP = {}
# dictionary of RES plant availability data from TYNDP, dictionary key: (node/consumer_tech, time), dictionary value: availability < 1
Avail_plant_RES_year_scenario = {}
# dictionary of plant availability data from TYNDP, dictionary key: (node/consumer_tech, time), dictionary value: availability < 1
Avail_plant_TYNDP = {}
Plant_list_TYNDP = []  # list of plants from TYNDP, e.g. BE00_gas
Plant_list_RES = []  # list of RES plants from TYNDP, e.g. BE00_pvrf
Plant_list_ror = []  # list of ROR plants from TYNDP, e.g. BE00_ror

# list of reservoir plants from TYNDP, e.g. BE00_dam
Plant_list_rsrvr = []
# list of non-hydro capacity generation plants from TYNDP, e.g. BE00_gas. This one is created based on available generation capacity files.
Plant_list_nonhydro_capacity_gen = []
# list of non-hydro plants from TYNDP, e.g. BE00_gas                    . This one is created based on precalculated plant list
Plant_list_nonhydro = []

# dictionary of RES plant technology from TYNDP, dictionary key: plant, dictionary value: technology, e.g. BE00_pvrf: pvrf
Map_plant_tech_res = {}
# dictionary of RES plant capacities from TYNDP, dictionary key: (node/consumer_tech), dictionary value: capacity in MW, e.g. 'BE00_pvrf':7586.78224974
gen_max_RES = {}

# dictionary of RES plant node from TYNDP, dictionary key: plant, dictionary value: node, e.g. BE00_pvrf: BE00
Map_plant_node_RES = {}
# dictionary of non-hydro plant node from TYNDP, dictionary key: plant, dictionary value: node, e.g. BE00_gas: BE00
Map_plant_node_nonhydro = {}

# dictionary of non-hydro plant technology from TYNDP, dictionary key: plant, dictionary value: technology, e.g. BE00_gas: gas
Map_plant_tech_nonhydro = {}

# dictionary of infeed data from TYNDP (excluding ror), dictionary key: (node/consumer, tech, time step), dictionary value: infeed in MWh. e.g. ('CH00_fixedconsumer', 'pvrf', 't_6848'):78.5844
Infeed_RES_TYNDP_instance = {}
# dictionary of ROR infeed data from TYNDP, dictionary key: (node/consumer, tech, time step), dictionary value: infeed in MWh. e.g. ('CH00_fixedconsumer', 'ror', 't_283'):208.26785714285714
Infeed_ROR_TYNDP = {}
# dictionary of inflow data from TYNDP, dictionary key:(region + "_" + tech, "t_1"), dictionary value: inflow in MWh, e.g. ('NOS0_pumped_open', 't_1'): 977722.0 . tech in ['reservoir', 'pumped_open']:
Inflow_data_pecd = {}
# list of plants with inflow data from TYNDP, e.g. 'NOS0_pumped_open'
Plant_inflow_list_TYNDP = []
# list of plants with outflow data from TYNDP, e.g. 'NOS0_pumped_open'
Plant_outflow_list_TYNDP = []

# dictionary for each consumer lists its assets (e.g. {'BE00_fixedconsumer': ['hp_ID300', 'ev_ID300', 'pv_ID300']})
Map_consumer_plant_TYNDP = {}
# dictionary for each consumer lists its reservoirs (e.g. {'BE00_fixedconsumer': ['reservoir_ID300']})
Map_consumer_plant_rsrvr = {}
# dictionary for each consumer lists its non-hydro assets (e.g. 'ITCS':['ITCS_battery', 'ITCS_limited_energy', 'ITCS_chp', 'ITCS_dsr', 'ITCS_gas', 'ITCS_hardcoal']
Map_consumer_plant_nonhydro = {}

# list of lines from TYNDP, e.g. 'HVDC_SE04_DE00'
Line_list_TYNDP = []
# dictionary for each line lists its nodes (e.g. 'HVDC_SE04_LT00':{'start_node': 'SE04', 'end_node': 'LT00'}
Map_line_node_TYNDP = {}
# dictionary for each line lists its export limit (e.g. ('HVAC_AL00_GR00', 't_286'): 400
ATC_exportlimit_TYNDP = {}
# dictionary for each line lists its import limit (e.g. ('HVAC_AL00_GR00', 't_286'): 400
ATC_importlimit_TYNDP = {}

# dictionary with keys in the form of "region_RES_tech" (plant names) and values in MW
gen_max_MW_rsrvr = {}
# dictionary with keys in the form of "region_RES_tech" (plant names) and values in MWh
hydro_storage_MWh_rsrvr = {}
# dictionary with keys in the form of "region_RES_tech" (plant names) and values in MW
hydro_capacities_pumping_MW_rsrvr = {}
# dictionary for non hydro EU plants (not CH) with keys in the form of "region_tech" (plant names) and capacities in MW
Plant_capacity_nonhydro_EU = {}
# dictionary for non hydro CH plants with keys in the form of "region_tech" (plant names) and capacities in MW
Plant_capacity_nonhydro_CH = {}

# dictionary with RES plant as keys (e.g. 'BE00_pvrf', 'BE00_windon', 'BE00_windof') and capacity as values in MW
gen_max_RES = {}
