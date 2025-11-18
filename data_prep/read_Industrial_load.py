"""
Read time series of industrial demand, aggreates values within a region, and store the aggregated values in csv files.
"""

import pandas as pd
import plotly.express as px
import os

# define the folder where the files are stored
directory_with_files = f"C://Users//daru//OneDrive - ZHAW//BFE Speicher//5 Data transfer//HSLU_to_ZHAW//Industrial_profiles"

# create the target directory if it does not exist
target_directory = directory_with_files + "//aggregated"
if not os.path.exists(target_directory):
    os.makedirs(target_directory)

target_years = ["2035", "2050",]

target_temperatures = [
    "<100°C",
    "100°C - 200°C",
]

temperature_rename_dict = {
    "<100°C": "0-100",
    "100°C - 200°C": "100-200",
}

files_to_read = [
    "Industrie_Endenergieverbrauch_(Erdgas)_to_HP_kWh_",
    "Industrie_Endenergieverbrauch_(Heizöl (leicht))_to_HP_kWh_",
    "Industrie_Endenergieverbrauch_(Heizöl (Mittel und Schwer))_to_HP_kWh_",
    # "Industrie_Endenergieverbrauch_(Fernwärme (Bezug))_kWh_",
]

for year in target_years:
    for temperature in target_temperatures:
        df_year_temperature_agg = pd.DataFrame()
        # within each temperature, go through all the files, and sum of values for the first 8760 columns
        for file in files_to_read:
            # read teh csv file
            df = pd.read_csv(f"{directory_with_files}//{file}{year}.csv", index_col=[0,1,2,3])
            # in level 2 of the index, only keep the rows with the target temperature
            df = df[df.index.get_level_values(3) == temperature]
            # in level 1, keep only the rows that have "heating demand kWh"
            df = df[df.index.get_level_values(2) == "heating demand kWh"]/1000

            # drop levels 2 and 3
            df = df.droplevel([0,2,3])
            # flatten df (not multi-index)
            df.reset_index(inplace=True)
            df.set_index("climate_zone_group", inplace=True)

            fig = px.line(df.T, title=f"{file}{year}")
            fig.show()

            # if df_year_temperature_agg has values, sum values of df to df_year_temperature_agg (for the same rows and columns), else, store df in df_year_temperature_agg
            if not df_year_temperature_agg.empty:
                df_year_temperature_agg = df_year_temperature_agg.add(df, fill_value=0)
            else:
                df_year_temperature_agg = df
            
            fig = px.line(df_year_temperature_agg.T, title=f"{file}{year} aggregated mid run")
            fig.show()

        if temperature == "100°C - 200°C":
            # read "Industrie_Endenergieverbrauch_(Fernwärme (Bezug))_kWh_" and add it to df_year_temperature_agg
            df = pd.read_csv(f"{directory_with_files}//Industrie_Endenergieverbrauch_(Fernwärme (Bezug))_kWh_{year}.csv", index_col=[0,1])
            df = df.droplevel([0])
            fig = px.line(df.T, title=f"Industrie_Endenergieverbrauch_(Fernwärme (Bezug))_kWh_{year}")
            fig.show()
            df = df/1000
            df_year_temperature_agg = df_year_temperature_agg.add(df, fill_value=0)
            fig = px.line(df_year_temperature_agg.T, title=f"Aggregated mid run")
            fig.show()

        # store the aggregated values in a new csv file
        df_year_temperature_agg.T.to_csv(f"{target_directory}//Industrie_Endenergieverbrauch_{year}_{temperature_rename_dict[temperature]}_agg.csv")
        print(f"{target_directory}//Industrie_Endenergieverbrauch_{year}_{temperature_rename_dict[temperature]}_agg.csv")

                    