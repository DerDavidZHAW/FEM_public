RES_tech_mapping_ERA5_ours = {'LFSolarPV': 'pvrf',
                              'Offshore': 'windof',
                              'Onshore':  'windon',
                              "pumped_open": "psp_open",
                              "pumped_closed": "psp_close",
                              "reservoir": "dam"}

Map_planttech_SM_ours = {
    "Battery": "battery",
    "Biomass": "biomass",
    "CHP": "chp",
    "Gas": "gas",
    "Oil": "oil",
    "DSR": "dsr",
    "HardCoal": "hardcoal",
    "Nuclear": "nuclear",
    "Lignite": "lignite",
    "Dam": "dam",
    "RoR": "ror",
    "PSP_Open": "psp_open",
    "PSP_Closed": "psp_close",
    "Solar PV": "pvrf",
    "Onshore Wind": "windon",
    "Offshore Wind": "windof",
}

Map_planttech_ours_SM = {v: k for k, v in Map_planttech_SM_ours.items()}


region_list = ['CH00', 'ITCN', 'ITCS', 'ITN1', 'ITS1', 'ITSA', 'ITSI', 'DE00', 'DEKF', 'FR00', 'AT00', 'DKE1', 'DKW1', 'DKKF', 'BE00', 'CZ00', 'ES00', 'UK00', 'HU00',
               'LU00', 'NL00', 'PL00', 'PT00', 'SI00', 'SK00', 'HR00', 'SE01', 'SE02', 'SE03', 'SE04', 'NON1', 'NOM1', 'NOS0']

Map_node_country = {
    'CH00':	"CH",
    "CH01":	"CH",
    "CH02":	"CH",
    "CH03":	"CH",
    "CH04":	"CH",
    "CH05":	"CH",
    "CH06":	"CH",
    "CH07":	"CH",
    "ITCN":	"IT",
    "ITCS":	"IT",
    "ITN1":	"IT",
    "ITS1":	"IT",
    "ITSA":	"IT",
    "ITSI":	"IT",
    "IT00": "IT",
    "DKE1":	"DK",
    "DKW1":	"DK",
    "DKKF":	"DK",
    "AT00":	"AT",
    "BE00":	"BE",
    "CZ00":	"CZ",
    "DE00":	"DE",
    "DEKF":	"DE",
    "ES00":	"ES",
    "FR00":	"FR",
    "UK00":	"UK",
    "HU00":	"HU",
    "LU00":	"LU",
    "LUB1":	"LU",
    "LUF1":	"LU",
    "LUG1":	"LU",
    "LUV1":	"LU",
    "NL00":	"NL",
    "PL00":	"PL",
    "PT00":	"PT",
    "SI00":	"SI",
    "SK00":	"SK",
    "HR00":	"HR",
    "SE01":	"SE",
    "SE02":	"SE",
    "SE03":	"SE",
    "SE04":	"SE",
    "NON1":	"NO",
    "NOM1":	"NO",
    "NOS0":	"NO",
}
# reverse the dictionary Map_node_country, taking into account that the same country can have multiple nodes
# for the key "country", the value is a list of nodes in that country. eg. Map_country_node["CH"]: ['CH00', 'CH01', 'CH02', 'CH03', 'CH04', 'CH05', 'CH06', 'CH07']
Map_country_node = {}
for key, value in Map_node_country.items():
    if value not in Map_country_node.keys():
        Map_country_node[value] = [key]
    else:
        Map_country_node[value].append(key)

tech_list_data_import = ['hardcoal', 'limited_energy', 'battery', 'gas', 'ror', 'pvrf',
                         'psp_open', 'windof', 'nuclear', 'oil', 'dam', 'windon', 'psp_close', 'lignite', 'dsr', 'chp']

# day-hour mapping
# for the key "day", the value is the index of the day in the year. eg. Map_day_hour[1]: 'day_1': ['h_1', 'h_2', 'h_3', 'h_4', 'h_5', 'h_6', 'h_7', 'h_8', 'h_9', 'h_10', 'h_11', 'h_12', 'h_13', 'h_14', 'h_15', 'h_16', 'h_17', 'h_18', 'h_19', 'h_20', 'h_21', 'h_22', 'h_23', 'h_24']
Map_day_hour = {}
for day in range(1, 366):
    Map_day_hour["day_" + str(day)] = ["t_"+str(day)
                                       for day in range((day-1) * 24 + 1, day * 24+1)]


# # write a function that can map the day-hour to the index of the time series. The input is a dictionary and the dimension at which the day keys are located. The output is a dictionary with the same structure but the day-hour keys are replaced by the index of the time series. Use Map_day_hour for mappig.
def map_day_hour_to_index(dict, dim):
    for key in dict.keys():
        if key in Map_day_hour.keys():
            dict[key] = Map_day_hour[key]
        else:
            map_day_hour_to_index(dict[key], dim)
    return dict


Map_TYNDPscenario_long_short = {
    "National Trends": "NT",
    "Global Ambition": "GA",
    "Distributed Energy": "DE"
}
Map_TYNDPscenario_short_long = {
    "NT": "NationalTrends",
    "GA": "GlobalAmbition",
    "DE": "DistributedEnergy"
}

Map_TYNDPscenario_short_longspaced = {
    "NT": "National Trends",
    "GA": "Global Ambition",
    "DE": "Distributed Energy"
}

Map_Prognosscenario_short_long = {
    "WWB": "WWB",
    "ZVA": "ZEROvarA",
    "ZVB": "ZEROvarB",
    "ZBA": "ZEROBasis"
}

nodes_without_offshore_wind = ['CH00', 'CH01', 'CH02', 'CH03', 'CH04', 'CH05', 'CH06', 'CH07', 'AT00', 'CZ00', 'HU00', 'LU00', 'SI00', 'SK00']