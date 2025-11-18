"""
Created on the 26/11/2024 by David Holmer (home@zhaw.ch) with the purpose of aggregating the
electricity demand data for the energy perspective zero basis.

PLEASE NOTE, that all files need to be sorted internally in the same way.
"""

#----------------------------------------------------------------------------------------------
# Settings:

# directory of the folder containing the data
dir = "C:/Models/Future_Markets/input/EPCH_ZEROBasis_Normal_2007"

# starting string of the files that are supposed to be included
start_with = "EPCH_ZEROBasis"

year = 2040

# choose the regions from the 7 Grossregionen
region = ["CH01", "CH02", "CH03", "CH04", "CH05", "CH06", "CH07"]

# should the data be aggregated by the Grossregionen?
aggregate = True

# set the naming of the columns of the files
# please note that this will be used as a global variable througout the script without being
# explicitly passed to the functions
naming = ["region", "jahr", "stunde", "wert"]

# files to exclude
#exclude = ["EPCH_ZEROBasis_Normal_Stromnachfrage_Total_Netzverluste_MWh.csv"]
exclude = []
#----------------------------------------------------------------------------------------------

import os
import numpy as np
import pandas as pd

def fetch_file_names(dir, start_with):
    """
    This fetches all the files in dir that start with the string start_with

    Parameters
    ----------
    dir : string
        the directory to the files that should be considered
    second : string
        all files that start with this string will be considered

    Returns
    -------
    list
        names of all the files that should be considered
    """

    files = []
    for file in os.listdir(dir):
        if file.startswith("EPCH_ZEROBasis"):
            files.append(file)
    return files

def import_data(file_names):
    """
    This function imports the first file and entirely and adds the remaining files to it

    Parameters
    ----------
    file_names : list
        a list containing the names of all relevant files

    Returns
    -------
    pd.DataFrame
        a pd.DataFrame with all the relevant data imported
    """

    # rename for readability
    region_column = naming[0]
    year_column = naming[1]
    hour_column = naming[2]

    # copy the first file and keep only the info (region, year, ...) the copy the rest into it in the end
    info = pd.read_csv(dir + "/" + file_names[0], sep=",", usecols=[0, 1, 2])

    # create the array with the correct shape to store all the data
    data = np.zeros((info.shape[0], len(file_names)))

    # iterate over all files and import data into the array
    for i in range(len(file_names)):

        recently_imported = np.genfromtxt(dir + "/" + file_names[i], delimiter=",", skip_header=1, dtype=float)
        data[:, i] = recently_imported[:, 3]

        print(f"{file_names[i]} imported..")

    # Convert the numpy array 'data' to a pandas DataFrame, using 'file_names' as column names
    data_df = pd.DataFrame(data, columns=file_names)

    # Concatenate the 'info' DataFrame with 'data_df'
    combined_df = pd.concat([info, data_df], axis=1)

    return combined_df

def filter_data(data, region, year):
    """
    This function filters the data for the given region and year

    Parameters
    ----------
    data : pd.DataFrame
        the data that should be filtered
    region : string
        the region that should be filtered
    year : int
        the year that should be filtered

    Returns
    -------
    pd.DataFrame
        the filtered data
    """

    # filter the data for the given region
    filtered_data = data[data['region'].isin(region)]

    # filter the data for the given year
    filtered_data = filtered_data[filtered_data['jahr'] == year]

    return filtered_data

def aggregate_regions(data):
    """
    This function aggregates the data for the Grossregionen

    Parameters
    ----------
    data : pd.DataFrame
        the data that should be aggregated

    Returns
    -------
    pd.DataFrame
        the aggregated data
    """

    # rename for readability
    region_column = naming[0]

    # list of all Grossregionen
    grossregionen = data[region_column].unique()

    # shape as if there was only one grossregion
    shape = data[data[region_column] == grossregionen[0]].shape

    # create an array that keeps track of the aggregation (-3 because of the region, year and hour)
    aggregated = np.zeros((shape[0], shape[1]-3))

    # iterate over all grossregionen and save sorted values in aggregated
    for r in grossregionen:
        aggregated += data[data[region_column] == r].iloc[:,3:].values

    # keep only one region to replace the values with the aggregated ones later
    result = data[data[region_column] == grossregionen[0]].copy()

    # set all values to 0 except for the region, year and hour (that's why it is 3:)
    result.iloc[:,3:] = aggregated

    # rename the region to indicate that it is aggregated
    result[region_column] = str(grossregionen)

    return result

def sum_up(data, start_with):
    """
    This sum adds up the electricity demand coming from the individual files

    Parameters
    ----------
    data : pd.DataFrame
        the data containing the electricity demands of the individual files
    start_with : string
        the string that the files start with and that the respective column names also
        start with after the import and aggregation
    
    Returns
    -------
    pd.DataFrame
        the DataFrame that was passed to the function with an additional column "sum"
    """

    # get the columns that should be summed up
    columns = [col for col in data.columns if col.startswith(start_with)]

    # sum up the columns
    data["sum"] = data[columns].sum(axis=1)

# create a list containing the names of all relevant files
file_names = fetch_file_names(dir, start_with)

# remove the files that should be excluded
file_names = [f for f in file_names if f not in exclude]

# import the data
data = import_data(file_names)

# keep only the desired regions and year
filtered_data = filter_data(data, region, year)

# aggregate the data
if aggregate:
    aggregated_by_region = aggregate_regions(filtered_data)
else:
    aggregated_by_region = filtered_data

# sum up the electricity demands
sum_up(aggregated_by_region, start_with)

