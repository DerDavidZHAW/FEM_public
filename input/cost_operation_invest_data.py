import numpy as np
"""
These sources show where all our assumptions for operation data are stored. Sources: 
- investment_cost, fixed_op_cost, input_cost_scenario_ZERO, input_cost_scenario_WWB: Energieperspektive 2050+ (EP2050+), BFE, https://pubdb.bfe.admin.ch/de/publication/download/10783
- co2_factor: Umweltbilanz Strommixe Schweiz 2018, Treeze / BAFU, https://www.bafu.admin.ch/dam/bafu/de/dokumente/klima/fachinfo-daten/Umweltbilanz-Strommix-Schweiz-2018-v2.01.pdf.download.pdf/Umweltbilanz-Strommix-Schweiz-2018-v2.01.pdf
- factor efficiency1: https://pubdb.bfe.admin.ch/de/publication/download/11112
- factor efficiency2 page 16: https://pubdb.bfe.admin.ch/de/publication/download/1533; read more
"""

amortization_years_all = {
    'pv': 25,
    'pvrf': 25,
    'windon': 25,
    'windof': 25,
    'gas' : 25,
    'CCGTresmethane' : 25,
    'SCGTresmethane' : 25,
    'CCGTCCS' : 25,
    'SCGTfossil' : 25,
    'battery' : 10,
    'hydrogen' : 25,
    'oil' : 25,
    'nuclear' : 50,	
    'biomass' : 25,
    'bt' : 25,
    'v1g' : 25,
    "ev_flex": 25,
    'v2g' : 25,
    'hp' : 25,
    'chp' : 25,
    'dsr' : 25,
    'hardcoal' : 25,
    'lignite' : 25,
    'dam' : 55,
    'psp_open' : 55,
    'psp_close' : 55,
    "other": 25,
    "electrolyzer": 25,
    "heat_pump_households": 25,
    "dsrTh": 50,

    # district heating # 
    "resistive_heater": 15, # Source: Moretti table 8S
    "heat_pump": 20,
    "TES": 37.5,
    "TTES_small": 37.5, # Source: Richard From HSLU 
    "TTES_medium": 37.5, # Source: Richard From HSLU
    "TTES_large": 37.5, # Source: Richard From HSLU
    "PTES_small": 25,   # Source: Richard From HSLU
    "PTES_medium": 25,  # Source: Richard From HSLU
    "PTES_large": 25,   # Source: Richard From HSLU

    "gas_boiler": 20, # Source: Moretti table 8S, Industry Methane Boiler


    # life time of fuel storage assets # TODO: to be updated 
    "biomass_fuel_storage":	50,
    "resmethane_fuel_storage":	50,
    "fossilmethane_fuel_storage":	50,
    "oil_fuel_storage":	50,
    # "hydrogen_fuel_storage":	50,
}

USD2017toCHF2017 = 0.9843 # 1 USD = 0.9843 CHF
USD2024toCHF2017 = 0.8148 # 1 USD = 0.8148 CHF
EUR2017toCHF2017 = 1.1119 # 1 EUR = 1.1119 CHF
EUR2024toCHF2017 = 0.8889 # 1 EUR = 0.8889 CHF

o_m_share = 1.025 # share of fixed operation and maintanance costs (expressed as Euro/kw/year) as percentage of investment cost.
battery_market_recovery_share = 1 # 0.5 # 
# NEXUS-E assumed fixed operation costs which were essentially 2.5% of the investment costs.
cost_component = {

# NEXUS-E data set (except for nulcear plants (lazards) and battery and hydrogen from Moretti)
    'investment_cost_chfMW': {
        'pv':               {2020: o_m_share * 615000, 2025: o_m_share * 615000, 2030: o_m_share * 615000, 2035: o_m_share * 697000, 2040: o_m_share * 615000, 2045: o_m_share * 615000, 2050: o_m_share * 615000, 2055: o_m_share * 615000, 2060: o_m_share * 615000},
        'pvrf':             {2020: o_m_share * 615000, 2025: o_m_share * 615000, 2030: o_m_share * 615000, 2035: o_m_share * 697000, 2040: o_m_share * 615000, 2045: o_m_share * 615000, 2050: o_m_share * 615000, 2055: o_m_share * 615000, 2060: o_m_share * 615000}, # NOTE: copied from pv
        'gas':              {2020: o_m_share * 755000, 2025: o_m_share * 755000, 2030: o_m_share * 755000, 2035: o_m_share * 755000, 2040: o_m_share * 755000, 2045: o_m_share * 755000, 2050: o_m_share * 755000, 2055: o_m_share * 755000, 2060: o_m_share * 755000},
        'dam':              {2020: o_m_share * 6338000, 2025: o_m_share * 6338000, 2030: o_m_share * 6338000, 2035: o_m_share * 6338000, 2040: o_m_share * 6338000, 2045: o_m_share * 6338000, 2050: o_m_share * 6338000, 2055: o_m_share * 6338000, 2060: o_m_share * 6338000},
        'psp_open':         {2020: o_m_share * 1616000, 2025: o_m_share * 1616000, 2030: o_m_share * 1616000, 2035: o_m_share * 1616000, 2040: o_m_share * 1616000, 2045: o_m_share * 1616000, 2050: o_m_share * 1616000, 2055: o_m_share * 1616000, 2060: o_m_share * 1616000},
        'psp_close':        {2020: o_m_share * 1616000, 2025: o_m_share * 1616000, 2030: o_m_share * 1616000, 2035: o_m_share * 1616000, 2040: o_m_share * 1616000, 2045: o_m_share * 1616000, 2050: o_m_share * 1616000, 2055: o_m_share * 1616000, 2060: o_m_share * 1616000},
        # NOTE: this is copied from gas, but should be different
        'biomass':          {2020: o_m_share * 755000, 2025: o_m_share * 755000, 2030: o_m_share * 755000, 2035: o_m_share * 755000, 2040: o_m_share * 755000, 2045: o_m_share * 755000, 2050: o_m_share * 755000, 2055: o_m_share * 755000, 2060: o_m_share * 755000},
        'bt':               {2020:  o_m_share * 7041382, 2025: o_m_share * 704, 2030: o_m_share * 704, 2035: o_m_share * 704, 2040: o_m_share * 704, 2045: o_m_share * 704, 2050: o_m_share * 704, 2055: o_m_share * 704, 2060: o_m_share * 704}, 
        # 'bt':               {2020: o_m_share * 0, 2025: o_m_share * 0, 2030: o_m_share * 0, 2035: o_m_share * 0, 2040: o_m_share * 0, 2045: o_m_share * 0, 2050: o_m_share * 0, 2055: o_m_share * 0, 2060: o_m_share * 0},
        'v1g':              {2020: o_m_share * 0, 2025: o_m_share * 0, 2030: o_m_share * 0, 2035: o_m_share * 0, 2040: o_m_share * 0, 2045: o_m_share * 0, 2050: o_m_share * 0, 2055: o_m_share * 0, 2060: o_m_share * 0},
        'v2g':              {2020: o_m_share * 0, 2025: o_m_share * 0, 2030: o_m_share * 0, 2035: o_m_share * 0, 2040: o_m_share * 0, 2045: o_m_share * 0, 2050: o_m_share * 0, 2055: o_m_share * 0, 2060: o_m_share * 0},
        'ev_flex':          {2020: o_m_share * 0, 2025: o_m_share * 0, 2030: o_m_share * 0, 2035: o_m_share * 0, 2040: o_m_share * 0, 2045: o_m_share * 0, 2050: o_m_share * 0, 2055: o_m_share * 0, 2060: o_m_share * 0},
        'hp':               {2020: o_m_share * 0, 2025: o_m_share * 0, 2030: o_m_share * 0, 2035: o_m_share * 0, 2040: o_m_share * 0, 2045: o_m_share * 0, 2050: o_m_share * 0, 2055: o_m_share * 0, 2060: o_m_share * 0},
        'chp':              {2020: o_m_share * 0, 2025: o_m_share * 0, 2030: o_m_share * 0, 2035: o_m_share * 0, 2040: o_m_share * 0, 2045: o_m_share * 0, 2050: o_m_share * 0, 2055: o_m_share * 0, 2060: o_m_share * 0},
        'dsr':              {2020: o_m_share * 0, 2025: o_m_share * 0, 2030: o_m_share * 0, 2035: o_m_share * 0, 2040: o_m_share * 0, 2045: o_m_share * 0, 2050: o_m_share * 0, 2055: o_m_share * 0, 2060: o_m_share * 0},
        'hardcoal':         {2020: o_m_share * 0, 2025: o_m_share * 0, 2030: o_m_share * 0, 2035: o_m_share * 0, 2040: o_m_share * 0, 2045: o_m_share * 0, 2050: o_m_share * 0, 2055: o_m_share * 0, 2060: o_m_share * 0},
        'lignite':          {2020: o_m_share * 0, 2025: o_m_share * 0, 2030: o_m_share * 0, 2035: o_m_share * 0, 2040: o_m_share * 0, 2045: o_m_share * 0, 2050: o_m_share * 0, 2055: o_m_share * 0, 2060: o_m_share * 0},

        # in source but not in map_plant_tech_cost_component yet
        'hydro_small':  {2020: o_m_share * 9930000, 2025: o_m_share * 9930000, 2030: o_m_share * 9930000, 2035: o_m_share * 9930000, 2040: o_m_share * 9930000, 2045: o_m_share * 9930000, 2050: o_m_share * 9930000, 2055: o_m_share * 9930000, 2060: o_m_share * 9930000},
        'hydro_ror':    {2020: o_m_share * 5694000, 2025: o_m_share * 5694000, 2030: o_m_share * 5694000, 2035: o_m_share * 5694000, 2040: o_m_share * 5694000, 2045: o_m_share * 5694000, 2050: o_m_share * 5694000, 2055: o_m_share * 5694000, 2060: o_m_share * 5694000},
        'wind':         {2020: o_m_share * 1778000, 2025: o_m_share * 1778000, 2030: o_m_share * 1778000, 2035: o_m_share * 1997284, 2040: o_m_share * 1778000, 2045: o_m_share * 1778000, 2050: o_m_share * 1778000, 2055: o_m_share * 1778000, 2060: o_m_share * 1778000},
        'windon':       {2020: o_m_share * 1778000, 2025: o_m_share * 1778000, 2030: o_m_share * 1778000, 2035: o_m_share * 1997284, 2040: o_m_share * 1778000, 2045: o_m_share * 1778000, 2050: o_m_share * 1778000, 2055: o_m_share * 1778000, 2060: o_m_share * 1778000},  # NOTE: copied from wind
        'windof':       {2020: o_m_share * 2533000, 2025: o_m_share * 2533000, 2030: o_m_share * 2533000, 2035: o_m_share * 2533000, 2040: o_m_share * 2533000, 2045: o_m_share * 2533000, 2050: o_m_share * 2533000, 2055: o_m_share * 2533000, 2060: o_m_share * 2533000},  # NOTE: copied from wind
        'geothermal':   {2020: o_m_share * 5190000, 2025: o_m_share * 5190000, 2030: o_m_share * 5190000, 2035: o_m_share * 5190000, 2040: o_m_share * 5190000, 2045: o_m_share * 5190000, 2050: o_m_share * 5190000, 2055: o_m_share * 5190000, 2060: o_m_share * 5190000},
        #NOTE: needs update only if investment is activated
        'other':        {2020: o_m_share * 0, 2025: o_m_share * 0, 2030: o_m_share * 0, 2035: o_m_share * 0, 2040: o_m_share * 0, 2045: o_m_share * 0, 2050: o_m_share * 0, 2055: o_m_share * 0, 2060: o_m_share * 0},
        'electrolyzer': {2020: o_m_share * 0, 2025: o_m_share * 0, 2030: o_m_share * 0, 2035: o_m_share * 0, 2040: o_m_share * 0, 2045: o_m_share * 0, 2050: o_m_share * 0, 2055: o_m_share * 0, 2060: o_m_share * 0},

        # CH specific investments
        # 'nuclear':         {2020: o_m_share * 10600000, 2025: o_m_share * 10600000, 2030: o_m_share * 10600000, 2035: o_m_share * 10600000, 2040: o_m_share * 10600000, 2045: o_m_share * 10600000, 2050: o_m_share * 10600000, 2055: o_m_share * 10600000, 2060: o_m_share * 10600000},
        # We assume capex of 10’600 based on Lazard LCOE+ 2024: https://www.lazard.com/media/xemfey0k/lazards-lcoeplus-june-2024-_vf.pdf . It uses the mean of total capital cost from the table below (11’582.5) converted to Euros.

        # As requested by the SFOE, the costs for nuclear are set to 5500 CHF/kW
        'nuclear':         {2020: o_m_share * 10600000 * USD2024toCHF2017, 2025: o_m_share * 10600000 * USD2024toCHF2017, 2030: o_m_share * 10600000 * USD2024toCHF2017, 2035: o_m_share * 10600000 * USD2024toCHF2017, 2040: o_m_share * 10600000 * USD2024toCHF2017, 2045: o_m_share * 10600000 * USD2024toCHF2017, 2050: o_m_share * 10600000 * USD2024toCHF2017, 2055: o_m_share * 10600000 * USD2024toCHF2017, 2060: o_m_share * 10600000 * USD2024toCHF2017},

        'CCGTresmethane':  {2020: o_m_share * 855000,  2025: o_m_share * 855000, 2030: o_m_share * 855000, 2035: o_m_share * 855000, 2040: o_m_share * 855000, 2045: o_m_share * 855000,      2050: o_m_share * 855000, 2055: o_m_share * 855000, 2060: o_m_share * 855000},
        'SCGTresmethane':  {2020: o_m_share * 700000,  2025: o_m_share * 700000, 2030: o_m_share * 700000, 2035: o_m_share * 700000, 2040: o_m_share * 700000, 2045: o_m_share * 700000,      2050: o_m_share * 700000, 2055: o_m_share * 700000, 2060: o_m_share * 700000},
        'CCGTCCS':         {2020: o_m_share * 1500000, 2025: o_m_share * 1500000, 2030: o_m_share * 1500000, 2035: o_m_share * 1500000, 2040: o_m_share * 1500000, 2045: o_m_share * 1500000, 2050: o_m_share * 1500000, 2055: o_m_share * 1500000, 2060: o_m_share * 1500000},
        'SCGTfossil':      {2020: o_m_share * 700000,  2025: o_m_share * 700000,  2030: o_m_share * 700000, 2035: o_m_share * 700000, 2040: o_m_share * 700000, 2045: o_m_share * 700000,     2050: o_m_share * 700000, 2055: o_m_share * 700000, 2060: o_m_share * 700000},
        'battery':         {2020: battery_market_recovery_share * o_m_share * 85590,   2025: battery_market_recovery_share * o_m_share * 85590, 2030: battery_market_recovery_share * o_m_share * 85590, 2035: battery_market_recovery_share * o_m_share * 43606, 2040: battery_market_recovery_share * o_m_share * 85590, 2045: battery_market_recovery_share * o_m_share * 85590, 2050: battery_market_recovery_share * o_m_share * 37378, 2055: battery_market_recovery_share * o_m_share * 85590, 2060: battery_market_recovery_share * o_m_share * 85590},  # Moretti table 5S
        # 'hydrogen':        {2020: o_m_share * EUR2024toCHF2017 * 1113000, 2025: o_m_share * EUR2024toCHF2017 * 1113000, 2030: o_m_share * EUR2024toCHF2017 * 1113000, 2035: o_m_share * EUR2024toCHF2017 * 1113000, 2040: o_m_share * EUR2024toCHF2017 * 1113000, 2045: o_m_share * EUR2024toCHF2017 * 1113000, 2050: o_m_share * EUR2024toCHF2017 * 1113000, 2055: o_m_share * EUR2024toCHF2017 * 1113000, 2060: o_m_share * EUR2024toCHF2017 * 1113000}, # in practice, this is not used in the objective function anymore
        'hydrogen':        {year: 789243.9829650274 for year in [2020, 2025, 2030, 2035, 2040, 2045, 2050, 2055, 2060]}, # reverse calculated to obtain 55998.8 after the annualization. 50908 is the annualized investment cost of CH00_SCGTfossil as read in investment_genmax_slp.csv, 10% more expensive to burn hydrogen
        #NOTE: values below are copied from SCGTfossil (assuming a gas power plant will could used as dual fuel plant)
        'oil':             {2020: o_m_share * 700000,  2025: o_m_share * 700000,  2030: o_m_share * 700000, 2035: o_m_share * 700000, 2040: o_m_share * 700000, 2045: o_m_share * 700000,     2050: o_m_share * 700000, 2055: o_m_share * 700000, 2060: o_m_share * 700000},
        # 'liquidfuel':      {2020: o_m_share * 700000,  2025: o_m_share * 700000,  2030: o_m_share * 700000, 2035: o_m_share * 700000, 2040: o_m_share * 700000, 2045: o_m_share * 700000,     2050: o_m_share * 700000, 2055: o_m_share * 700000, 2060: o_m_share * 700000},
        "heat_pump_households": {year:0 for year in [2040, 2050, 2030, 2035]}, # Will never need updates because investment is not allowed
        "dsrTh":            {year:0 for year in [2040, 2050, 2030, 2035]}, # Will never need updates because investment is not allowed

        #NOTE: needs definite updates (if investment is activated)
        "resistive_heater":     {year:42700 * EUR2017toCHF2017 for year in [2040, 2050, 2030, 2035]}, # Source: Moretti table 8S
        "heat_pump":            {year:702200 * EUR2017toCHF2017 for year in [2040, 2050, 2030, 2035]},  # Source: Moretti table 8S, (it is in Euro/kW)
        "TES":                  {year:3000 for year in [2040, 2050, 2030, 2035]}, 
        "TTES_small":           {year:3000 for year in [2040, 2050, 2030, 2035]},  # Source Richard From HSLU
        "TTES_medium":          {year:3000 for year in [2040, 2050, 2030, 2035]},  # Source Richard From HSLU
        "TTES_large":           {year:3000 for year in [2040, 2050, 2030, 2035]},  # Source Richard From HSLU
        "PTES_small":           {year:11770 for year in [2040, 2050, 2030, 2035]},    # Source Richard From HSLU
        "PTES_medium":          {year:11770 for year in [2040, 2050, 2030, 2035]},    # Source Richard From HSLU
        "PTES_large":           {year:11770 for year in [2040, 2050, 2030, 2035]},    # Source Richard From HSLU

        "gas_boiler":           {year:171780 * EUR2017toCHF2017 for year in [2040, 2050, 2030, 2035]}, # Moretti table 8S, Industry Methane Boiler

    },

    'investment_cost_discharge_chfMW': { # only for storage technologies where charge and discharge capacity are distinct facilities as for hydrogen
        'hydrogen':        {year:1015334.2497523652 for year in [2040, 2050, 2030, 2035]} # reverse calculated to obtain 72040.46 after the annualization. 72040.46 is the annualized investment cost, calculated based on cost of electrolyzer (1113000(from ingmar)*0.8835(year adjustements)), at lifetime of 25 years, at 5% discount rate
    },

     # operational costs part 1
    'fixed_op_cost_chfMW': {
        # Energieperspektive 2050+, Tabelle 60, CHF / MW
        'pv':           {2020: 58000, 2025: 53000, 2030: 48000, 2035: 43000, 2040: 41000, 2045: 40000, 2050: 38000, 2055: 37000, 2060: 36000},
        'pvrf':         {2020: 58000, 2025: 53000, 2030: 48000, 2035: 43000, 2040: 41000, 2045: 40000, 2050: 38000, 2055: 37000, 2060: 36000}, # NOTE: copied from pv
        'gas':          {2020: 43000, 2025: 43000, 2030: 43000, 2035: 43000, 2040: 43000, 2045: 43000, 2050: 43000, 2055: 43000, 2060: 43000},
        # NOTE: below, Ali changed np.nan to 0s
        'battery':      {2020:  0, 2025:  0, 2030:  0, 2035:  0, 2040:  0, 2045:  0, 2050:  0, 2055:  0, 2060:  0},
        'dam':          {2020: 63000, 2025: 63000, 2030: 63000, 2035: 63000, 2040: 63000, 2045: 63000, 2050: 63000, 2055: 63000, 2060: 63000},
        'psp_open':     {2020: 16000, 2025: 16000, 2030: 16000, 2035: 16000, 2040: 16000, 2045: 16000, 2050: 16000, 2055: 16000, 2060: 16000},
        'psp_close':    {2020: 16000, 2025: 16000, 2030: 16000, 2035: 16000, 2040: 16000, 2045: 16000, 2050: 16000, 2055: 16000, 2060: 16000},

        # map_plant_tech_cost_component - STILL MISSING,
        # NOTE: this is copied from gas, but should be different
        'biomass':      {2020: 43000, 2025: 43000, 2030: 43000, 2035: 43000, 2040: 43000, 2045: 43000, 2050: 43000, 2055: 43000, 2060: 43000},
        # NOTE: copied from battery, but should be different
        # NOTE: activate this line instead of line below. changed values to 0 to calculate
        # 'bt':               {2020: 1382, 2025: 1096, 2030: 910, 2035: 813, 2040: 748, 2045: 726, 2050: 704, 2055: 682, 2060: 660},
        'bt':               {2020: 0, 2025: 0, 2030: 0, 2035: 0, 2040: 0, 2045: 0, 2050: 0, 2055: 0, 2060: 0},
        'v1g':              {2020: 0, 2025: 0, 2030: 0, 2035: 0, 2040: 0, 2045: 0, 2050: 0, 2055: 0, 2060: 0},
        'v2g':              {2020: 0, 2025: 0, 2030: 0, 2035: 0, 2040: 0, 2045: 0, 2050: 0, 2055: 0, 2060: 0},
        'hp':               {2020: 0, 2025: 0, 2030: 0, 2035: 0, 2040: 0, 2045: 0, 2050: 0, 2055: 0, 2060: 0},
        'chp':              {2020: 0, 2025: 0, 2030: 0, 2035: 0, 2040: 0, 2045: 0, 2050: 0, 2055: 0, 2060: 0},
        'dsr':              {2020: 0, 2025: 0, 2030: 0, 2035: 0, 2040: 0, 2045: 0, 2050: 0, 2055: 0, 2060: 0},
        'hardcoal':         {2020: 0, 2025: 0, 2030: 0, 2035: 0, 2040: 0, 2045: 0, 2050: 0, 2055: 0, 2060: 0},
        'lignite':          {2020: 0, 2025: 0, 2030: 0, 2035: 0, 2040: 0, 2045: 0, 2050: 0, 2055: 0, 2060: 0},
        # in source but not in map_plant_tech_cost_component yet
        'hydro_small':  {2020: 102000, 2025: 102000, 2030: 101000, 2035: 100000, 2040: 100000, 2045: 100000, 2050: 99000, 2055: 99000, 2060: 99000},
        'hydro_ror':    {2020: 57000, 2025: 57000, 2030: 57000, 2035: 57000, 2040: 57000, 2045: 57000, 2050: 57000, 2055: 57000, 2060: 57000},
        'wind':         {2020: 75000, 2025: 73000, 2030: 71000, 2035: 69000, 2040: 67000, 2045: 65000, 2050: 63000, 2055: 61000, 2060: 59000},
        'windon':       {2020: 75000, 2025: 73000, 2030: 71000, 2035: 69000, 2040: 67000, 2045: 65000, 2050: 63000, 2055: 61000, 2060: 59000},  # NOTE: copied from wind
        'windof':       {2020: 75000, 2025: 73000, 2030: 71000, 2035: 69000, 2040: 67000, 2045: 65000, 2050: 63000, 2055: 61000, 2060: 59000},  # NOTE: copied from wind
        'geothermal':   {2020: 294000, 2025: 276000, 2030: 258000, 2035: 240000, 2040: 222000, 2045: 215000, 2050: 208000, 2055: 201000, 2060: 194000},
        # NOTE: needs update
        'other':        {2020: 0, 2025: 0, 2030: 0, 2035: 0, 2040: 0, 2045: 0, 2050: 0, 2055: 0, 2060: 0},
        'electrolyzer': {2020: 0, 2025: 0, 2030: 0, 2035: 0, 2040: 0, 2045: 0, 2050: 0, 2055: 0, 2060: 0},

        # CH specific costs - NOTE: they are not imported yet, because fixed cost is not used in the model
        # 'nuclear':          {2020: 0, 2025: 0, 2030: 0, 2035: 0, 2040: 0, 2045: 0, 2050: 0, 2055: 0, 2060: 0},
        # 'CCGTresmethane':  {2020: 650940, 2025: 650940, 2030: 650940, 2035: 650940, 2040: 650940, 2045: 650940, 2050: 650940, 2055: 650940, 2060: 650940},
        # 'SCGTresmethane':  {2020: 759530, 2025: 759530, 2030: 759530, 2035: 759530, 2040: 759530, 2045: 759530, 2050: 759530, 2055: 759530, 2060: 759530},
        # 'CCGTCCS':         {2020: 1410360, 2025: 1410360, 2030: 1410360, 2035: 1410360, 2040: 1410360, 2045: 1410360, 2050: 1410360, 2055: 1410360, 2060: 1410360},
        # 'SCGTfossil':      {2020: 759530,  2025: 759530,  2030: 759530, 2035: 759530, 2040: 759530, 2045: 759530, 2050: 759530, 2055: 759530, 2060: 759530},
        # 'battery':         {2020: 85590,   2025: 85590, 2030: 85590, 2035: 85590, 2040: 85590, 2045: 85590, 2050: 85590, 2055: 85590, 2060: 85590}, 
        # 'hydrogen':        {2020: 1611810, 2025: 1611810, 2030: 1611810, 2035: 1611810, 2040: 1611810, 2045: 1611810, 2050: 1611810, 2055: 1611810, 2060: 1611810},
        # 'oil':              {2020: 0, 2025: 0, 2030: 0, 2035: 0, 2040: 0, 2045: 0, 2050: 0, 2055: 0, 2060: 0},


         },

    # fuel costs
    'input_cost_scenario_ZERO': {
        # NOTE: From here on, values for 2035 were missing and have been added by interpolation by David. There is a note below, when values for 2035 were available again.
        # Energieperspektive 2050+, Abbildung 11, USD / MWh (or Barrel oil)
        # USDpMWh,
        'hardcoal': {2000: 7 * USD2017toCHF2017, 2019: 12 * USD2017toCHF2017, 2030: 9 * USD2017toCHF2017, 2035: 9 * USD2017toCHF2017, 2040: 9 * USD2017toCHF2017, 2050: 6 * USD2017toCHF2017, 2060: 4 * USD2017toCHF2017},

        # 1 barrel of crude oil = 5.8 MMBtu
        # 1 MMBtu = 0.293 MWh
        # 1 barrel of crude oil = 5.8 * 0.293 = 1.7 MWh
        # Energieperspektive 2050+, Abbildung 11, USD / Barrel oil
        # USD / MWh
        'oil':        {2000: 39 * (1/1.7) * USD2017toCHF2017, 2019: 70 * (1/1.7) * USD2017toCHF2017, 2030: 5.2*10 * USD2017toCHF2017, 2035: 4.9*10 * USD2017toCHF2017, 2040: 4.6*10 * USD2017toCHF2017, 2050: 2.9*10 * USD2017toCHF2017, 2060: 1.6*10 * USD2017toCHF2017}, # Source: Energieperspektive 2050+, Tabelle 7: Grenzübergangspreise für Energie ((reale Preise mit Basis 2017; unterer Heizwert Hu))

        # USDpMWh,
        'gas':              {2000: 13 * USD2017toCHF2017, 2019: 24 * USD2017toCHF2017, 2030: 26 * USD2017toCHF2017, 2035: 26 * USD2017toCHF2017, 2040: 26 * USD2017toCHF2017, 2050: 18 * USD2017toCHF2017, 2060: 10 * USD2017toCHF2017},
        'CCGTresmethane' :  {2000: 55.0 * 3.6 * EUR2017toCHF2017, 2019: 24 * EUR2017toCHF2017, 2030: 55.0 * 3.6 * EUR2017toCHF2017, 2035: 55.0 * 3.6 * EUR2017toCHF2017, 2040: 55.0 * 3.6 * EUR2017toCHF2017, 2050: 55.0 * 3.6 * EUR2017toCHF2017, 2060: 55.0 * 3.6 * EUR2017toCHF2017},  # Moretti table 14S, 3.6 is GJ to MWh conversion rate
        'SCGTresmethane' :  {2000: 55.0 * 3.6 * EUR2017toCHF2017, 2019: 24 * EUR2017toCHF2017, 2030: 55.0 * 3.6 * EUR2017toCHF2017, 2035: 55.0 * 3.6 * EUR2017toCHF2017, 2040: 55.0 * 3.6 * EUR2017toCHF2017, 2050: 55.0 * 3.6 * EUR2017toCHF2017, 2060: 55.0 * 3.6 * EUR2017toCHF2017},  # Moretti table 14S, 3.6 is GJ to MWh conversion rate
        'CCGTCCS' :         {2000: 13 * USD2017toCHF2017, 2019: 24 * USD2017toCHF2017, 2030: 26 * USD2017toCHF2017, 2035: 26 * USD2017toCHF2017, 2040: 26 * USD2017toCHF2017, 2050: 18 * USD2017toCHF2017, 2060: 10 * USD2017toCHF2017},  # same as gas
        'SCGTfossil' :      {2000: 13 * USD2017toCHF2017, 2019: 24 * USD2017toCHF2017, 2030: 26 * USD2017toCHF2017, 2035: 26 * USD2017toCHF2017, 2040: 26 * USD2017toCHF2017, 2050: 18 * USD2017toCHF2017, 2060: 10 * USD2017toCHF2017},  # same as gas
        'battery':          {2000: 0, 2019: 0, 2030:0 , 2035:0, 2040: 0, 2050: 0, 2060: 0},
        #'hydrogen':         {2000: 23.0*10, 2019: 23.0*10, 2030:23.0*10 , 2035: 23.0*10, 2040: 21.4*10, 2050: 19.5*10, 2060: 18.5*10},	#NOTE: Source: Energieperspektive 2050+, Tabelle 7: Grenzübergangspreise für Energie ((reale Preise mit Basis 2017; unterer Heizwert Hu))
        'hydrogen':         {2000: 0, 2019: 0, 2030:0 , 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        # USDpT
        'co2': {2000: np.nan, 2019: 28 * USD2017toCHF2017, 2030: 33 * USD2017toCHF2017, 2035: (33 + 140)/2 * USD2017toCHF2017, 2040: 140 * USD2017toCHF2017, 2050: 397 * USD2017toCHF2017, 2060: 397 * USD2017toCHF2017}, 
        'css': {},
        # map_plant_tech_cost_component - STILL MISSING
        'pv':     {2000: 0, 2019: 0, 2030:0 , 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        'pvrf':   {2000: 0, 2019: 0, 2030:0 , 2035: 0, 2040: 0, 2050: 0, 2060: 0}, # NOTE: copied from pv
        'windon': {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        'windof': {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},

        'biomass':          {2015: 2.5*10, 2019: 3.1*10, 2025: 3.3*10, 2030: 3.5*10, 2035: 3.7*10, 2040: 3.9*10, 2045: 4.2*10, 2050: 4.4*10, 2055: 4.6*10, 2060: 4.8*10}, #NOTE: Source: Energieperspektive 2050+, Tabelle 7: Grenzübergangspreise für Energie ((reale Preise mit Basis 2017; unterer Heizwert Hu))
        'battery':          {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        'bt':               {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        'dam':              {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        'psp_open':         {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        'psp_close':        {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        'v1g':              {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        'ev_flex':          {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        'v2g':              {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        'hp':               {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        'chp':              {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        'dsr':              {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        'nuclear':          {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        'lignite':          {2000: 0, 2019: 0, 2030: 0, 2035: 0, 2040: 0, 2050: 0, 2060: 0},
        # NOTE: Until here, values for 2035 were missing and have been added by David
        'other':        {year:20 for year in [2040, 2050, 2030, 2035]}, #NOTE: update this/ current number is placeholder
        'electrolyzer': {2020: 0, 2025: 0, 2030: 0, 2035: 0, 2040: 0, 2045: 0, 2050: 0, 2055: 0, 2060: 0},

        # district heating
        "resistive_heater": {year:0 for year in [2040, 2050, 2030, 2035]}, # I have assumed no direct fuel cost for resistive heater. The cost of electricity is considered while minimizing the total objective function.
        "heat_pump":        {year:0 for year in [2040, 2050, 2030, 2035]}, # I have assumed no direct fuel cost for heat pump. The cost of electricity is considered while minimizing the total objective function.
        "TES":              {year:0 for year in [2040, 2050, 2030, 2035]}, # I have assumed no direct fuel cost for TES. The cost of electricity is considered while minimizing the total objective function.
        "TTES_small":       {year:0 for year in [2040, 2050, 2030, 2035]}, # I have assumed no direct fuel cost for TTES_small. The cost of electricity is considered while minimizing the total objective function.
        "TTES_medium":      {year:0 for year in [2040, 2050, 2030, 2035]}, # I have assumed no direct fuel cost for TTES_medium. The cost of electricity is considered while minimizing the total objective function.
        "TTES_large":       {year:0 for year in [2040, 2050, 2030, 2035]}, # I have assumed no direct fuel cost for TTES_large. The cost of electricity is considered while minimizing the total objective function.
        "PTES_small":       {year:0 for year in [2040, 2050, 2030, 2035]}, # I have assumed no direct fuel cost for PTES_small. The cost of electricity is considered while minimizing the total objective function.
        "PTES_medium":      {year:0 for year in [2040, 2050, 2030, 2035]}, # I have assumed no direct fuel cost for PTES_medium. The cost of electricity is considered while minimizing the total objective function.
        "PTES_large":       {year:0 for year in [2040, 2050, 2030, 2035]}, # I have assumed no direct fuel cost for PTES_large. The cost of electricity is considered while minimizing the total objective function.
        "dsrTh":            {year:0 for year in [2040, 2050, 2030, 2035]}, # I have assumed no direct fuel cost for DSR. The cost of electricity is considered while minimizing the total objective function.
        "gas_boiler":       {2000: 13 * USD2017toCHF2017, 2019: 24 * USD2017toCHF2017, 2030: 26 * USD2017toCHF2017, 2035: 26 * USD2017toCHF2017, 2040: 26 * USD2017toCHF2017, 2050: 18 * USD2017toCHF2017, 2060: 10 * USD2017toCHF2017},  # same as gas
        # heat pumps households
        "heat_pump_households":        {year:0 for year in [2040, 2050, 2030, 2035]}, # Just copied from "heat_pump"
    },

    # # operational costs part 2
    # from here all SwissMod Data
    # second added term is the external cost of fuel (in EURO/MWh) - Calculated from SCAP dataset
    'om_cost_eurMWH': {
        'hardcoal': 3.3 + 0.00367,
        'oil': 3.3 +  0.00546,
        'nuclear': 9,
        'gas': 1.675 +  0.00111,

        'CCGTresmethane' :  1.675 +  0.00111,  # same as gas
        'SCGTresmethane' :  1.675 +  0.00111,  # same as gas
        'CCGTCCS' :         1.675 +  0.00111,  # same as gas
        'SCGTfossil' :      1.675 +  0.00111,  # same as gas

        # adding a small value to storage technologies to avoid unnecessary use of battery (which will affect the reported values for curtailment)
        # In absence of a non-zero value, the model will could generate and consume electricity from battery in the same time step, which is not realistic. 
        # This will happen in hours in which curtailment could have happened (the model sees no difference between curtailing and wasting energy in the battery)
        # This will not have an effect on investment or operation decisions of other technologies. But will affect the reported values for curtailment.
        'battery':  0.001,
        #'hydrogen': 0.001,	
        'hydrogen': 0, #NOTE: set to 0 when the hardcoded hydrogen costs from the objective function were removed. Since before, there was no OM costs for hydrogen, it is kept like this for the time being.
        'dsr': 0.001,     #NOTE: the value is not given in the source. A non-zero value is needed to avoid using DSR for free (and possibly have up/down regulation for no reason)


        'lignite': 3.3 +  0.00337,
        'chp': 200,
        # map_plant_tech_cost_component - STILL MISSING
        'pv': 0,
        'pvrf': 0,
        'biomass': 0.00515,
        # 'battery': 0,
        'bt': 0.001,
        'dam': 0,
        'psp_open': 0.001,
        'psp_close': 0.001,
        'v1g': 0,
        'ev_flex': 0,
        'v2g': 0.1, #NOTE: the value is not given in the source. A non-zero value is needed to avoid using V2G instead of curtailment (to burn energy in the battery).
        'hp': 0,
        # 'chp': 200,
        'lignite': 3.3,
        'windon': 0,
        'windof': 0,
        'other': 0.00515,
        'electrolyzer': 0,
        "resistive_heater": 0,
        "heat_pump": 0.01,
        "heat_pump_households": 0.01,
        "TES": 0.1,       # #NOTE: the value is not given in the source. A non-zero value is needed to avoid TES being charged and discharged in the same time step (which is not realistic). 
        "TTES_small": 0.1, # #NOTE: the value is not given in the source. A non-zero value is needed to avoid TTES being charged and discharged in the same time step (which is not realistic).
        "TTES_medium": 0.1, # #NOTE: the value is not given in the source. A non-zero value is needed to avoid TTES being charged and discharged in the same time step (which is not realistic).
        "TTES_large": 0.1, # #NOTE: the value is not given in the source. A non-zero value is needed to avoid TTES being charged and discharged in the same time step (which is not realistic).
        "PTES_small": 0.1, # #NOTE: the value is not given in the source. A non-zero value is needed to avoid PTES being charged and discharged in the same time step (which is not realistic).
        "PTES_medium": 0.1, # #NOTE: the value is not given in the source. A non-zero value is needed to avoid PTES being charged and discharged in the same time step (which is not realistic).
        "PTES_large": 0.1, # #NOTE: the value is not given in the source. A non-zero value is needed to avoid PTES being charged and discharged in the same time step (which is not realistic).
        "dsrTh": 1,     #NOTE: the value is not given in the source. A non-zero value is needed to avoid using DSR for free (and possibly have up/down regulation for no reason),
        "gas_boiler": 0,

    },
    'efficiency': { # efficiency of turning fuel into electricity (in the case of power plants) or heat (in the case of heating technologies), or unit of stored energy (in the case of storage technologies, e.g. battery and closed-loop hydrogen)
        'hardcoal': 0.4,
        'oil': 0.35, # same as SCGTfossil

        'nuclear': 0.33,
        'gas': 0.44,

        'CCGTresmethane' : 0.53, 
        'SCGTresmethane' : 0.35, 
        'CCGTCCS' :        0.47,
        'SCGTfossil' :     0.35,
        'battery':  0.9,
        'hydrogen':0.53, # Ingamr: us SCGT efficiency for hydrogen-based power plants

        
        'lignite': 0.4,
        'chp': 1,
        # map_plant_tech_cost_component - STILL MISSING
        'pv': 1,
        'pvrf': 1,
        # NOTE: update biomass efficiency, making sure annual generation values will be meaningful (depends on fuel_limits.csv)
        'biomass': 0.4,
        # 'battery': 1,
        'bt': 0.9,
        'dam': 1,
        'psp_open': 0.87,
        'psp_close': 0.87,
        'v1g': 1,
        'ev_flex': 1,
        'v2g': 0.9,
        'hp': 1,
        'chp': 1,
        'dsr': 1,
        'lignite': 1,
        'windon': 1,
        'windof': 1,
        'other': 1,
        'electrolyzer': 1,

        # district heating
        "resistive_heater": 1, # efficiency of consumption is 1, since for every unit of electricity consumed, 1 unit of electricity is consumed. Efficiency of thermal supply will be considered later in the thermal balance equation.
        "heat_pump": 1, # efficiency of consumption is 1, since for every unit of electricity consumed, 1 unit of electricity is consumed. Efficiency of thermal supply will be considered later in the thermal balance equation.
        "heat_pump_households": 1,
        "TES": 0.9, # efficiency of consumption is 1. Actuall thermal efficiency (pipe losses and decay time constant) will be modelled within the constraints (becase they will be very case specific, not technology specific).
        "TTES_small": 0.921954445729289, # Source Richard from HSLU  - #TODO: check if this is being delivered to the model
        "TTES_medium": 0.9219544457292891, # efficiency of consumption is 1. Actuall thermal efficiency (pipe losses and decay time constant) will be modelled within the constraints (becase they will be very case specific, not technology specific).
        "TTES_large": 0.921954445729289, 
        "PTES_small": 0.921954445729289, 
        "PTES_medium": 0.921954445729289,
        "PTES_large": 0.921954445729289, 
        "dsrTh": 1, # shifting of thermal demand is considered to be 100% efficient (no extra thermal consumption later)
        "gas_boiler": 0.927, # thermal efficiency of gas boilers in generating heat. Moretti 8S Industry Methane Boiler.

    },
    'efficiency_into_storage': { 
        # efficiency of turning electricity into stored energy
        "v1g": 1,  # NOTE:adjust later
        "v2g": 0.90,
        "dam": 1,  # NOTE: maybe remove this
        "psp_open": 0.87,
        "psp_close": 0.87,
        "battery": 0.90,
        # NOTE: Important to make sure for the central runs, the correct value is used (for consumers that have "bt", the efficiency may be different from this)
        "bt": 0.90,
        "hydrogen": 0.7, # Ingmar: electrolyzer efficiency
        "TES": 0.9, #   
        "TTES_small": 0.921954445729289, # Source Richard from HSLU  - #TODO: check if this is being delivered to the model
        "TTES_medium": 0.9219544457292891, # efficiency of consumption is 1. Actuall thermal efficiency (pipe losses and decay time constant) will be modelled within the constraints (becase they will be very case specific, not technology specific).
        "TTES_large": 0.921954445729289, 
        "PTES_small": 0.921954445729289, 
        "PTES_medium": 0.921954445729289,
        "PTES_large": 0.921954445729289,  
    },

    'emission_factor': {
        'hardcoal': 0.094 * 3.6, # 3.6 is conversion factor for GJ to MWh
        'oil': 0.0835 * 3.6,
        'liquidfuel': 0.0835 * 3.6, # same as oil
        'nuclear': 0 * 3.6,
        'gas':  0.1 * 0.057 * 3.6,

        'CCGTresmethane' : 0 , 
        'SCGTresmethane' : 0 , 
        'CCGTCCS' : 0.1 * 0.057 * 3.6,  # update with above gas values  0.1 implies a carbon capture rate of 90% for the CCGTCCS - NOTE: while caclulating CO2 transport and storage costs, the caclculated co2 emissions is multiplied by 9 (as 90%/10% = 9).
        'SCGTfossil' :    0.057 * 3.6 , # update with above gas values
        'battery': 0,
        'hydrogen': 0,	

        'lignite': 0.101 * 3.6,
        'chp': 0.057 * 3.6,
        # map_plant_tech_cost_component - STILL MISSING
        'pv': 0,
        'pvrf': 0,
        'biomass': 0,
        # 'battery': 0,
        'bt': 0,
        'dam': 0,
        'psp_open': 0,
        'psp_close': 0,
        'v1g': 0,
        'ev_flex': 0,
        'v2g': 0,
        'hp': 0,
        'chp': 0,
        'dsr': 0,
        'lignite': 0, 
        'windon': 0,
        'windof': 0,
        'other': 0,         # NOTE: needs update
        'electrolyzer': 0,

        # district heating
        "resistive_heater": 0, # no emissions from resistive heater, since it is considered as a direct electric heater
        "heat_pump": 0, # no direct emissions from heat pump
        "heat_pump_households": 0,
        "TES": 0, # no direct emissions from TES
        "TTES_small": 0, # no direct emissions from TTES_small
        "TTES_medium": 0, # no direct emissions from TTES_medium
        "TTES_large": 0, # no direct emissions from TTES_large
        "PTES_small": 0, # no direct emissions from PTES_small
        "PTES_medium": 0, # no direct emissions from PTES_medium
        "PTES_large": 0, # no direct emissions from PTES_large
        "dsrTh": 0, # no direct emissions
        "gas_boiler": 0.057 * 3.6 , # update with above gas values

    },


#NOTE: The cost to invest in power plants' storage capacity for electricity (at this point, this only applies to batteries ...
#           ... because other plants need fuel storage capacity, which is considered in investment_fuel_energy_cost_chfMWh.
'investment_energy_cost_chfMWh': {   # capacity in MWh
        #TODO update to MWh
        "battery":    {2040: battery_market_recovery_share * 101.24 * 1000, 2050: battery_market_recovery_share * 44212, 2030: battery_market_recovery_share * 101.24 * 1000, 2035: battery_market_recovery_share * 51581},   # Moretti paper, table 5S
        "biomass":    {year:0 for year in [2040, 2050, 2030, 2035]},                                        
        # "hydrogen":   {2040: 291 * 0.981 * 3.2,   2050: 291 * 0.981 * 3.2,      2030: 291 * 0.981 * 3.2,      2035: 291 * 0.981 * 3.2},     # not used in the objective function anymore, but Ingmar: 3.2 times methan invest cost, because of volume - We can explain our deviation from our original assumption: We assume salt caverns, not tanks
        "hydrogen":   {year:705.2609860848798 for year in [2040, 2050, 2030, 2035]}, # Reverse calculated so that the costs after the annualization is 50.04. 50.04 is the annualized investment cost calculated based on over night cost of 291 * 0.981 *3.2 (gas storage * 3.2 from Ingmar), at lifetime of 50 years, at 5% discount rate
        "bt":         {year:0 for year in [2040, 2050, 2030, 2035]},
        "dam":        {year:0 for year in [2040, 2050, 2030, 2035]},
        "psp_open":   {year:0 for year in [2040, 2050, 2030, 2035]},
        "psp_close":  {year:0 for year in [2040, 2050, 2030, 2035]},
        "v1g":        {year:0 for year in [2040, 2050, 2030, 2035]},
        "ev_flex":    {year:0 for year in [2040, 2050, 2030, 2035]},
        "v2g":        {year:0 for year in [2040, 2050, 2030, 2035]},
        "hp":         {year:0 for year in [2040, 2050, 2030, 2035]},
        "pv":         {year:0 for year in [2040, 2050, 2030, 2035]},
        "pvrf":       {year:0 for year in [2040, 2050, 2030, 2035]},
        "windon":     {year:0 for year in [2040, 2050, 2030, 2035]},
        "windof":     {year:0 for year in [2040, 2050, 2030, 2035]},
        "gas":        {year:0 for year in [2040, 2050, 2030, 2035]},
        "chp":        {year:0 for year in [2040, 2050, 2030, 2035]},
        "dsr":        {year:0 for year in [2040, 2050, 2030, 2035]},
        "oil":        {year:0 for year in [2040, 2050, 2030, 2035]},
        "hardcoal":   {year:0 for year in [2040, 2050, 2030, 2035]},
        "lignite":    {year:0 for year in [2040, 2050, 2030, 2035]},
        "nuclear":    {year:0 for year in [2040, 2050, 2030, 2035]},
        "other":      {year:0 for year in [2040, 2050, 2030, 2035]},	
        "electrolyzer":{year:0 for year in [2040, 2050, 2030, 2035]},
        # no direct investment cost for these technology, categorizing thie technology as energy limited is to eventually limit generation from this technology            
        "CCGTresmethane": {year:0 for year in [2040, 2050, 2030, 2035]},
        "SCGTresmethane": {year:0 for year in [2040, 2050, 2030, 2035]},
        "CCGTCCS":        {year:0 for year in [2040, 2050, 2030, 2035]},
        "SCGTfossil":     {year:0 for year in [2040, 2050, 2030, 2035]},
        "gas_boiler":     {year:0 for year in [2040, 2050, 2030, 2035]},	

        # district heating
        "resistive_heater": {year:0 for year in [2040, 2050, 2030, 2035]},
        "heat_pump":        {year:0 for year in [2040, 2050, 2030, 2035]},
        "TES":              {year:    1.01 * 12500 for year in [2040, 2050, 2030, 2035]}, 
        "TTES_small":           {year:1.01 * 12500 for year in [2040, 2050, 2030, 2035]},  # Source Richard From HSLU - O&M cost is 1% of investment cost
        "TTES_medium":          {year:1.01 * 12500 for year in [2040, 2050, 2030, 2035]},  # Source Richard From HSLU - numbers of equal for small medium and large, because of noisy nature of data (discussions with Richard)
        "TTES_large":           {year:1.01 * 12500 for year in [2040, 2050, 2030, 2035]},  # Source Richard From HSLU
        "PTES_small":           {year:  1.01 * 550 for year in [2040, 2050, 2030, 2035]},    # Source Richard From HSLU
        "PTES_medium":          {year:  1.01 * 500 for year in [2040, 2050, 2030, 2035]},    # Source Richard From HSLU
        "PTES_large":           {year:  1.01 * 450 for year in [2040, 2050, 2030, 2035]},    # Source Richard From HSLU
        "heat_pump_households":        {year:0 for year in [2040, 2050, 2030, 2035]}, 
        "dsrTh":            {year:0 for year in [2040, 2050, 2030, 2035]}, 
    },

    "investment_fuel_energy_cost_chfMWh": { #NOTE: all units are in MWh thermal energy (not m3 or barrel)
        #NOTE: if multiple fuels can be stored in the same storage, the cost can be shared? e.g., resmethane and fossilmethane in the same storage.
        "biomass":           {year:0 for year in [2040, 2050, 2030, 2035]},                     # 
        "oil":               {year:1.48 for year in [2040, 2050, 2030, 2035]},                  # Source: see input\info_Oil_Storage_Cost_Calculation_15_58.txt
                                                                                                # note that values for oil are yearly maintenance costs, not investment costs. Eventually, invetment costs of other technologies should be annualized, but not for oil.
        "resmethane":        {year:291 * 0.981 for year in [2040, 2050, 2030, 2035]},           # https://doi.org/10.55402/psi:63482 # * conversion rate from CHF2020 to CHF2017
        "fossilmethane":     {year:291 * 0.981 for year in [2040, 2050, 2030, 2035]},           # https://doi.org/10.55402/psi:63482 # * conversion rate from CHF2020 to CHF2017
        "hydrogen":          {year:0 for year in [2040, 2050, 2030, 2035]},                     # TODO: update 2050 and 2035 (Maybe Moretti paper)
    },
}

#NOTE: cost_data_inv_e_slp below was not used in the model in the first place. Values in investment_energy_cost_chfMWh are used in the model.
# cost_data_inv_e_slp = {
#     "biomass": 1000,
#     "battery": 101.24 * 1000,  # Moretti paper, table 5S
#     "hydrogen": 9.22 * 1000,   # Moretti paper, table 5S
#     "liquidfuel": (11.04/18.64)*5.09,        # There is pre-existing liquid fuel storage capacity in CH (0), but a maintainace cost of 5.04 CHF/kW/a is considered (see calculations in OneNote, winter_limit, Cost of storage per MW of electric gen) 
#     "bt": 0,
#     "dam": 0,
#     "psp_open": 0,
#     "psp_close": 0,
#     "v1g": 0,
#     "ev_flex": 0,   
#     "v2g": 0,
#     "hp": 0,

#     "CCGTresmethane": 0, # no direct investment cost for the technology, categorizing thie technology as energy limited is to eventually limit generation from this technology
#     "SCGTresmethane": 0, # no direct investment cost for the technology, categorizing thie technology as energy limited is to eventually limit generation from this technology
#     "CCGTCCS": 0,        # no direct investment cost for the technology, categorizing thie technology as energy limited is to eventually limit generation from this technology
#     "SCGTfossil": 0,     # no direct investment cost for the technology, categorizing thie technology as energy limited is to eventually limit generation from this technology
# } 

"""
STILL OPEN

Tabelle 84: Differenzen in den Unterhalts- und Betriebskosten nach Sektoren und Anwendungen im Szenario ZERO Basis, jährliche Werte und kumuliert 2020 bis 2050/2060, in Mrd. CHF
> probably not the right thing, right? > Für den Industriesektor wurden aufgrund fehlender Grundlagen keine Betriebs- und Unterhaltskosten abgebildet.' page 360
"""
