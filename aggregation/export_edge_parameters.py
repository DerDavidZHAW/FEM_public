"""This file contains the parameters for the export results in EDGE format. """

## mappings:
hydro_dam_psp_open_ch = ["large_psp", "medium_reservior", "small_reservior", "CH00_dam"] 
psp_close_ch = ["CH00_psp_close", ] 
psp_all_ch = ["large_psp", "CH00_psp_close", ]


## ---------------------------------------------------------------------------------------------------------------------
# Output_Sys
## ---------------------------------------------------------------------------------------------------------------------
Output_Sys_parameter_list = [
    "Import to CH Annual", 
    "Export from CH Annual", 
    "Net import CH Annual (Import-Export)", 
    "Import WINTER", 
    "Export WINTER", 
    "Net import WINTER (Import-Export)", 
    "Import SUMMER", 
    "Export SUMMER", 
    "Net import SUMMER (Import-Export)", 
    "Load shedding WINTER", 
    "Load shedding SUMMER", 
    "Load shedding Annual (Winter+Summer)", 
    "Generation curtailment Annual - CH", 
    "Generation curtailment Annual - Abroad", 
    "Import Cost Annual", 
    "Export Revenue Annual", 
    "Trading Costs Annual (Cost - Revenue)", 
    "Import Cost WINTER", 
    "Export Revenue WINTER", 
    "Import cost SUMMER", 
    "Export Revenue SUMMER", 
    "Congestion rent",
    "Electricity price in CH", 
    "Price for electricity import from AT", 
    "Price for electricity import from DE", 
    "Price for electricity import from FR", 
    "Price for electricity import from IT", 
    "Price for electricity export to AT", 
    "Price for electricity export to DE", 
    "Price for electricity export to FR", 
    "Price for electricity export to IT", 
    "Capacity PV + Wind", 
    "Investment costs annualised All", 
    "Operation costs anualised All", 
    "Total annualised costs All (with trading costs)", 
    "Operational costs per unit of generated energy", 
    "Total costs for consumers", 
    "Total revenues for generators", 
    "Transmission grid expansion investment costs",
    "Grid Expansion within CH", 
    "Grid Expansion to neighbours", 
    "Total emissions", 
    "Time to solve model", 
    "Memory requirements", 
]

Output_Sys_columns_names = [
    "Unit",
    "total",
    "average",
    "5th",
    "95th",
    "min",
    "max",
]

# Output_Spatial_columns_names = [


## ---------------------------------------------------------------------------------------------------------------------
# Output_Temp
## ---------------------------------------------------------------------------------------------------------------------

Output_Temp_parameter_list = [
    "Hourly generation solar PV - Rooftop",
    "Hourly generation solar PV - Alpine",
    "Hourly generation wind power",
    "Hourly generation biomass/waste",
    "Hourly generation Gas CC",
    "Hourly generation Gas CC-CCS",
    "Hourly generation Gas CC-Syn",
    "Hourly generation Gas other",
    "Hourly generation nuclear",
    "Hourly generation hydro dam",
    "Hourly generation hydro run of river",
    "Hourly generation hydro pumped storage",
    "Hourly demand hydro pumped storage",
    "Hourly generation battery",
    "Hourly charge battery",
    "Hourly DSM up",
    "Hourly DSM down",
    "Hourly generation curtailment - CH",
    "Hourly generation curtailment - Abroad",
    "Hourly load shedded",
    "Hourly exchange CH-DE",
    "Hourly exchange DE-CH",
    "Hourly exchange CH-FR",
    "Hourly exchange FR-CH",
    "Hourly exchange CH-IT",
    "Hourly exchange IT-CH",
    "Hourly exchange CH-AT",
    "Hourly exchange AT-CH",
    "Hourly import to CH (total)",
    "Hourly export to CH (total)",
    "Hourly net import (import-export)",
    "Hourly net load",
    "Hourly electricity price CH",
    "Hourly electricity price DE",
    "Hourly electricity price FR",
    "Hourly electricity price IT",
    "Hourly electricity price AT",
    "Hourly costs for consumers",
    "Hourly revenues for generators",
    "Average line loading - all lines",
    "Average line loading - internal lines",
    "Average line loading - interconnectors",
]

Output_Temp_columns_names = ["Unit"] + [str(i) for i in range(1, 8760+1)]

## ---------------------------------------------------------------------------------------------------------------------
# Output_Spatial
## ---------------------------------------------------------------------------------------------------------------------

Output_Spatial_parameter_list = [
    "Total capacity solar PV - Roof",
    "Total capacity solar PV - Alpine",
    "Total capacity wind power",
    "Total capacity biomass/waste",
    "Total capacity natural gas ",
    "Total capacity gas other",
    "Total capacity nuclear",
    "Total capacity hydro dams",
    "Total capacity run of river",
    "Total capacity pumped hydro",
    "Total capacity battery",
    "Annual generation solar PV - Roof",
    "Annual generation solar PV - Alpine",
    "Annual generation wind power",
    "Annual generation biomass/waste",
    "Annual generation natural gas",
    "Annual generation gas other",
    "Annual generation nuclear",
    "Annual generation hydro dam",
    "Annual generation hydro run of river",
    "Annual discharge pumped hydro",
    "Annual charge pumped hydro",
    "Annual battery charge",
    "Annual battery discharge",
    "Annual load shedding",
    "Charge pumped hydro WINTER",
    "Charge pumped hydro SUMMER",
    "Curtailment solar PV - Roof",
    "Curtailment solar PV - Alpine",
    "Curtailment wind power",
    "Total capacity battery",
    "Average netload WINTER",
    "Average netload SUMMER",
]    

Output_Spatial_columns_names = ["Unit" , "Sum"] + [str(i) for i in range(1, 26+1)]

import pandas as pd
# read region to canton mapping
mapping_canton_region_df = pd.read_csv(f"input\map_grossregion_cantons.csv", index_col= 0, header=0)

# PV station to grossregion mapping --------------------
# create a dictionary whose keys index and values are the corresponding grossregion
mapping_canton_grossregion_dict = dict(zip(mapping_canton_region_df.index, mapping_canton_region_df['grossregion']))