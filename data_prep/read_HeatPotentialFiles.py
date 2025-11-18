"""
This script reads the feather files containing the heat potentials for the different regions and sectors.
It plots the time series to visually check that the data is as expected a fix number for each region throughout the year.
It then stores this fixed values to csv format.
Note that as addressed by HSLU, ARA, LAKE, and RIVER are considered for DH, while KVA is considered as Industry heat.
"""


import pandas as pd
import plotly.express as px


target_folder = f'C://Users//daru//OneDrive - ZHAW//BFE Speicher//5 Data transfer//HSLU_to_ZHAW//Heat_potentials_from_ARA_KVA_lake_river'

file_name_to_DH = [
             "Usful-ARA-Heatpotential-MWh.feather",
             "Usful-LAKE-Heatpotential-MWh.feather",
             "Usful-RIVER-Heatpotential-MWh.feather",
             ]

Usful_Heatpotential_MWh_to_DH = {}

# for all files in the list
for file in file_name_to_DH:
    Usful_Heatpotential_MWh_to_DH[file] = {}
    # read the feather file using pandas
    df = pd.read_feather(f"{target_folder}//{file}")
    # plot time series using plotly
    fig = px.line(df)
    fig.show() # expect to see flat time series, if store, just store the first value
    
    # store the value in the first row in the dictionary, using the file name and column as key
    for region in df.columns:
        Usful_Heatpotential_MWh_to_DH[file][region] = df[region].iloc[0]

    # export to the same folder, csv format
    df.to_csv(f"{target_folder}//{file.replace('.feather', '.csv')}", index=False)

# save the dictionary as a csv file, using first key as row, and second key as column
df = pd.DataFrame(Usful_Heatpotential_MWh_to_DH)
# add a column for sum
df['sum'] = df.sum(axis=1)
df.to_csv(f"{target_folder}//Usful_Heatpotential_MWh_to_DH.csv")


# do the same for the file   "Usful-KVA-Heatpotential-MWh.feather",
file_name_to_Industry = [
             "Usful-KVA-Heatpotential-MWh.feather",
             ]

Usful_Heatpotential_MWh_to_Industry = {}

# for all files in the list
for file in file_name_to_Industry:
    Usful_Heatpotential_MWh_to_Industry[file] = {}
    # read the feather file using pandas
    df = pd.read_feather(f"{target_folder}//{file}")
    # plot time series using plotly
    fig = px.line(df)
    fig.show()
    
    # store the value in the first row in the dictionary, using the file name and column as key
    for region in df.columns:
        Usful_Heatpotential_MWh_to_Industry[file][region] = df[region].iloc[0]

    # export to the same folder, csv format
    df.to_csv(f"{target_folder}//{file.replace('.feather', '.csv')}", index=False)

# save the dictionary as a csv file, using first key as row, and second key as column
df = pd.DataFrame(Usful_Heatpotential_MWh_to_Industry)

# add a column for sum
df['sum'] = df.sum(axis=1)

df.to_csv(f"{target_folder}//Usful_Heatpotential_MWh_to_Industry.csv")
