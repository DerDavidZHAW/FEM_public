"""
Read time series of district heating demand, aggreates values within a region, and store the aggregated values in csv files.
After the script is run, copy the files in the target directory to the input\demand folder.
dsrTh value are directly updated in the input\plants_DH_CH_capacities.csv file.
"""

import pandas as pd
import plotly.express as px
import os

flexible_share = 0.5   # share of households that are flexible in district heatings 
temprature_range = 0.4 # the temprature range that the flexible households can tolerate (max 1 degree celcius)

# define the folder where the files are stored
directory_with_files = f"C://Models//Future_Markets//input//demand"
target_directory = directory_with_files + "//new_aggregated"

# create the target directory if it does not exist
if not os.path.exists(target_directory):
    os.makedirs(target_directory)


# part 1/2: Large district heating profiles -----------------------------------------------------
#define the files to read
files_to_read = [
    # "DH_large_profiles_2050_1995.csv",
    # "DH_large_profiles_2035_1995.csv",
    "DH_large_profiles_2050_2008.csv",
    "DH_large_profiles_2035_2008.csv",
    "DH_large_profiles_2050_2009.csv",
    "DH_large_profiles_2035_2009.csv",
]


df_agg = {}
dsrTH_region = {}


df_dsrValsInModel = pd.read_csv("input//plants_DH_CH_capacities.csv", index_col=0)

# read the files
for file in files_to_read:
    # read teh csv file
    df = pd.read_csv(f"{directory_with_files}//{file}", index_col=[1,2,3])
    df = df.drop(columns=["Unnamed: 0"])        # drop the first column, "Unnamed: 0"
    df = df[df.index.get_level_values(2) == "heating demand kWh"]     # under index TS_Type, only keep the row if the name is "heating demand kwh"
    # drop rows that have "sonstige" in the column "DH_source"
    df = df[df.index.get_level_values(1) != "sonstige"]
    
    # regions are stored in the level 0 of the index
    region_list = df.index.get_level_values(0).unique()

    # for every region, aggregate the values and store in a new dataframe
    for region in region_list:
        dsrTH_region[region] = df.loc[region, "positive_capacity [MJ]"].mean() / 3600 # type: ignore
        # aggregate the values of df.loc[region] in the first 8760 columns, store it in the new dataframe
        df_agg[region] = df.loc[region].iloc[:, 0:8760].sum() / 1000

    # store the aggregated values in a new csv file
    df_agg_df = pd.DataFrame(df_agg)
    
    # plot the aggregated values - sanity check
    fig = px.line(df_agg_df)
    fig.show()

    # replace ü with ue, ä with ae, ö with oe
    df_agg_df.columns = df_agg_df.columns.str.replace("ü", "ue")

    df_agg_df.T.to_csv(f"{target_directory}//{file.replace('.csv', '_agg.csv')}")

    # # store dsrTH_region in a csv file
    # dsrTH_region_df = pd.DataFrame(dsrTH_region, index=[0])
    # dsrTH_region_df.columns = dsrTH_region_df.columns.str.replace("ü", "ue")
    # dsrTH_region_df.T.to_csv(f"{target_directory}//{file.replace('.csv', '_dsrTH_region.csv')}")

    # copy dsrTh values to input files of the model -----------------------------------------------------
    # read input\plants_DH_CH_capacities.csv
    run_year = file.split("_")[3].split(".")[0]

    for region in dsrTH_region.keys():
        region_corrected = region.replace("ü", "ue")
        # find the row with the region name and update the value of dsrTh
        df_dsrValsInModel.loc[f"DH_{region_corrected}_dsrTh", run_year] = round(dsrTH_region[region] * flexible_share * temprature_range, 2)
# replace "input//plants_DH_CH_capacities.csv" with the updated df
df_dsrValsInModel.to_csv("input//plants_DH_CH_capacities.csv")

# part 2/2: Medium district heating profiles ----------------------------------------------------- one aggregate for the whole country
# define the files to read
files_to_read = [
    # "DH_medium_profiles_2050_1995.csv",
    # "DH_medium_profiles_2035_1995.csv",
    # "DH_small_profiles_2050_1995.csv",
    # "DH_small_profiles_2035_1995.csv",
    "DH_medium_profiles_2050_2008.csv",
    "DH_medium_profiles_2035_2008.csv",
    "DH_small_profiles_2050_2008.csv",
    "DH_small_profiles_2035_2008.csv",
    "DH_medium_profiles_2050_2009.csv",
    "DH_medium_profiles_2035_2009.csv",
    "DH_small_profiles_2050_2009.csv",
    "DH_small_profiles_2035_2009.csv",
]

df_agg = {}
dsrTH_country = {}
df_dsrValsInModel = pd.read_csv("input//plants_DH_CH_capacities.csv", index_col=0)

# read the files
for file in files_to_read:
    # read teh csv file
    df = pd.read_csv(f"{directory_with_files}//{file}", index_col=[1,2,3])
    df = df.drop(columns=["Unnamed: 0"])        # drop the first column, "Unnamed: 0"
    df = df[df.index.get_level_values(2) == "heating demand kWh"]     # under index TS_Type, only keep the row if the name is "heating demand kwh"
    # drop rows that have "sonstige" in the column "DH_source"
    df = df[df.index.get_level_values(1) != "sonstige"]

    # sum values of all rows and store in df_agg 
    df_agg[file] = df.iloc[:, 0:8760].sum() / 1000
    # name the columns as "DHmedium_CH"
    df_agg[file].columns = ["DHmedium_CH"]

    # store the aggregated values in a new csv file
    df_agg[file].to_csv(f"{target_directory}//{file.replace('.csv', '_agg.csv')}")

    # plot the aggregated values - sanity check
    fig = px.line(df_agg[file])
    fig.show()

    # calculate dsrTH_country-------------------------------------
    dsrTH_country[file] = df.loc[:, "positive_capacity [MJ]"].mean() / 3600 # type: ignore # Ali: sum was just crazy high! I changed it to mean
    # export the values of dsrTH_country in "input//plants_DH_CH_capacities.csv"
    run_year = file.split("_")[3].split(".")[0]
    df_dsrValsInModel.loc["DH_medium_dsrTh", run_year] = round(dsrTH_country[file] * flexible_share * temprature_range, 2)
# replace "input//plants_DH_CH_capacities.csv" with the updated df
df_dsrValsInModel.to_csv("input//plants_DH_CH_capacities.csv")

# # store dsrTH_country in a csv file
# dsrTH_country_df = pd.DataFrame(dsrTH_country, index=[0])
# dsrTH_country_df.columns = dsrTH_country_df.columns.str.replace("ü", "ue")
# dsrTH_country_df.T.to_csv(f"{target_directory}//dsrTH_country.csv")



