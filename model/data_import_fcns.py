import pandas as pd
import csv
import os
from model.mappings import (
    RES_tech_mapping_ERA5_ours,
    Map_planttech_SM_ours,
    Map_day_hour,
    Map_planttech_ours_SM,
    nodes_without_offshore_wind,
)
from model.structural_parameters import ch_subnode_list, add_additional_batteries, reduce_fr_be_demand
import re
import json
from pathlib import Path

def hydro_merge_country_regions_capacities(
    data_df, merge_some_countries, target_merge_countries
):
    """
    Merge the data for several regions in countries included in target_merge_countries.
    """

    if merge_some_countries:
        for country in target_merge_countries:
            # find regions that start with country
            regions = data_df[data_df.area.str.startswith(country)].area.unique()

            # sum the capacities of the regions:
            df_temp = (
                data_df[data_df.area.isin(regions)]
                .groupby(["technology", "variable"])
                .sum()
                .reset_index()
            )

            # change zone name from regionregion to country00
            df_temp["area"] = country + "00"

            # remvoe the regions from the data_df
            data_df = data_df[~data_df.area.isin(regions)]

            # add df_temp to data_df
            data_df = pd.concat([data_df, df_temp])

    return data_df

def merge_country_regions_inflow(
    data_df, target_variable, merge_some_countries, target_merge_countries
):
    """
    Merge the data for several regions in countries included in target_merge_countries.
    """
    if merge_some_countries:
        for country in target_merge_countries:
            # find regions that start with country
            regions = data_df[
                data_df.area_name.str.startswith(country)
            ].area_name.unique()

            if target_variable == "reservoir_inflow":
                # sum the inflows of the regions:
                df_temp = (
                    data_df[data_df.area_name.isin(regions)]
                    .groupby(["technology", "Week", "year"])
                    .sum()
                    .reset_index()
                )
            elif target_variable == "ror_inflow":
                # sum the inflows of the regions:
                df_temp = (
                    data_df[data_df.area_name.isin(regions)]
                    .groupby(["year", "Day"])
                    .sum()
                    .reset_index()
                )

            # change zone name from regionregion to country00
            df_temp["area_name"] = country + "00"

            # remvoe the regions from the data_df
            data_df = data_df[~data_df.area_name.isin(regions)]

            # add df_temp to data_df
            data_df = pd.concat([data_df, df_temp])

    return data_df


def read_hydro_capacities(
    Node_list, rep_hydro_plants, merge_some_countries, target_merge_countries, pump_capacity_GW_target_CH, adding_hydro_storage_cap_TWh_CH
):
    """
    Read the hydro capacities from the csv file input/hydro_PECD/PECD_EERA2021_reservoir_pumping_2030_country_table.csv and save them in a dictionary.
    The values are fixed throughout the years and scenarios, so there are no year/scenario required as arguments to the function.
    Input:
        Node_list: list of nodes
        rep_hydro_plants: boolean, if True, the Swiss psp open hydro plants are represented by three representative generators, instead of one.
    Output:
        Plant_list: list of plant names
        Map_plant_tech: dictionary with keys in the form of "region_RES_tech" (plant names) and values in the form of "tech" (technology names)
        Map_plant_node: dictionary with keys in the form of "region_RES_tech" (plant names) and values in the form of "node" (node names)
        hydro_capacities_MW: dictionary with keys in the form of "region_RES_tech" (plant names) and values in MW
        hydro_storage_MWh: dictionary with keys in the form of "region_RES_tech" (plant names) and values in MWh
        hydro_capacities_pumping_MW: dictionary with keys in the form of "region_RES_tech" (plant names) and values in MW

    """
    # read the csv file input/hydro_PECD/PECD_EERA2021_reservoir_pumping_2030_country_table.csv and save it in a dataframe
    hydro_capacities_data = pd.read_csv(
        "input/hydro_PECD/PECD_EERA2021_reservoir_pumping_2030_table.csv",
        header=0,
        dtype={
            "name": str,
            "varialbe": str,
            "area": str,
            "technology": str,
            "value": float,
            "inflow_share": float,
        },
    )
    # hydro_capacities_data['value'] = hydro_capacities_data['value'].round(1)

    hydro_capacities_data = hydro_merge_country_regions_capacities(
        hydro_capacities_data, merge_some_countries, target_merge_countries
    )

    # if hydro_capacities_data has any keys of RES_tech_mapping_ERA5_ours in the column "technology", replace them with the values of RES_tech_mapping_ERA5_ours
    hydro_capacities_data["technology"] = hydro_capacities_data["technology"].replace(
        RES_tech_mapping_ERA5_ours
    )

    # create a name column in hydro_capacities_data that is the sum of the columns "area" and "technology"
    hydro_capacities_data["name"] = (
        hydro_capacities_data["area"] + "_" + hydro_capacities_data["technology"]
    )

    rep_hydro_plants_data = pd.DataFrame()
    if rep_hydro_plants:
        rep_hydro_plants_data = pd.read_csv(
            "input/hydro_PECD/PECD_EERA2021_reservoir_pumping_2030_table_representative_plants.csv",
            header=0,
            dtype={"value": float, "inflow_share": float},
        )
        rep_hydro_plants_data["value"] = rep_hydro_plants_data["value"].round(1)

        # if rep_hydro_plants_data has any keys of RES_tech_mapping_ERA5_ours in the column "technology", replace them with the values of RES_tech_mapping_ERA5_ours
        rep_hydro_plants_data["technology"] = rep_hydro_plants_data[
            "technology"
        ].replace(RES_tech_mapping_ERA5_ours)

        # from hydro_capacities_data, remove the rows that "CH00" is in the column "area" and "pumped_open" is in the column "technology"
        hydro_capacities_data = hydro_capacities_data[
            ~(
                (hydro_capacities_data["area"] == "CH00")
                & (hydro_capacities_data["technology"] == "psp_open")
            )
        ]

        # cancat rep_hydro_plants_data to hydro_capacities_data
        hydro_capacities_data = pd.concat(
            [hydro_capacities_data, rep_hydro_plants_data]
        )

    plant_names_all_PECD = hydro_capacities_data.name.unique().tolist()

    # set column "value" and "name" as index
    hydro_capacities_data = hydro_capacities_data.set_index(["name", "variable"])

    # print(hydro_capacities_data)
    # for regions in Node_list, for the row in hydro_capacities_data that has region in column 'area' and "gen_cap_MW" in column variable, read the value in column value and save it in a dictionary
    # if there is a KeyError, do not save the value in the dictionary
    Plant_list = []
    Map_plant_tech = {}
    Map_plant_node = {}
    hydro_capacities_MW = {}
    hydro_storage_MWh = {}
    hydro_capacities_pumping_MW = {}
    Map_consumer_plant = {}

    plants_in_target_region = [
        plant
        for plant in plant_names_all_PECD
        if hydro_capacities_data.loc[(plant, "gen_cap_MW"), "area"] in Node_list
    ]

    for plant_name in plants_in_target_region:
        region = hydro_capacities_data.loc[(plant_name, "gen_cap_MW"), "area"]
        tech = hydro_capacities_data.loc[(plant_name, "gen_cap_MW"), "technology"]
        try:
            hydro_capacities_MW[plant_name] = hydro_capacities_data.loc[
                (plant_name, "gen_cap_MW"), "value"
            ]
            hydro_storage_MWh[plant_name] = hydro_capacities_data.loc[
                (plant_name, "sto_GWh"), "value"
            ]
            hydro_storage_MWh[plant_name] = (
                hydro_storage_MWh[plant_name] * 1000
            )  # convert GWh to MWh

            # add the plant to the list of plants
            Plant_list.append(plant_name)
            Map_plant_tech[plant_name] = tech
            Map_plant_node[plant_name] = region
            # if key [region + "_fixedconsumer"] exists in Map_consumer_plant, add to the key region + "_fixedconsumer" add the plant name, otherwise create the key and add the plant name
            if str(region) + "_fixedconsumer" in Map_consumer_plant:
                Map_consumer_plant[str(region) + "_fixedconsumer"].append(plant_name)
            else:
                Map_consumer_plant[str(region) + "_fixedconsumer"] = [plant_name]

        except IndexError:
            print(
                f"IndexError for region {region} and tech {tech} for gen_cap_MW or sto_GWh"
            )
            pass

        if tech in ["psp_open", "psp_close"]:
            try:
                hydro_capacities_pumping_MW[plant_name] = hydro_capacities_data.loc[
                    (plant_name, "pumping_cap_MW"), "value"
                ]
                hydro_capacities_pumping_MW[plant_name] = -hydro_capacities_pumping_MW[
                    plant_name
                ]  # convert to negative value

            except IndexError:
                print(
                    f"IndexError for region {region} and tech {tech} for pumping_cap_MW"
                )
                pass

        
    # if BFE asked a taget pumping capacity for CH00 -------------------------------------
    if pump_capacity_GW_target_CH:
        pumping_plants_CH = ["large_psp","CH00_psp_close"]
        # total pumping capacity in GW is equal to sume of values in hydro_capacities_pumping_MW with any of the keys pumping_plants_CH
        total_pumping_capacity_CH = sum(
            [
                hydro_capacities_pumping_MW[plant]
                for plant in hydro_capacities_pumping_MW
                if plant in pumping_plants_CH
            ]
        )
        sclaing_factor = pump_capacity_GW_target_CH / (total_pumping_capacity_CH/1000)
    
        # scale the values of pumping_plants_CH in hydro_capacities_pumping_MW
        for plant in pumping_plants_CH:
            hydro_capacities_pumping_MW[plant] = hydro_capacities_pumping_MW[plant] * sclaing_factor
    
    # if BFE asked to add hydro storage capacity in CH00 -------------------------------------
    if adding_hydro_storage_cap_TWh_CH:
        print("Adding hydro storage capacity in CH00")
        plants_with_hydro_storage_no_psp_close = ["large_psp", "medium_reservior", "small_reservior", "CH00_psp_close"]
        # total storage capacity in TWh is equal to sume of values in hydro_storage_MWh with any of the keys plants_with_hydro_storage_no_psp_close
        storage_capacity_CH = sum(
            [
                hydro_storage_MWh[plant]
                for plant in hydro_storage_MWh
                if plant in plants_with_hydro_storage_no_psp_close
            ]
        )/1000/1000
        sclaing_factor = (storage_capacity_CH + adding_hydro_storage_cap_TWh_CH) / storage_capacity_CH

        # scale the values of plants_with_hydro_storage_no_psp_close in hydro_storage_MWh
        for plant in plants_with_hydro_storage_no_psp_close:
            hydro_storage_MWh[plant] = hydro_storage_MWh[plant] * sclaing_factor

    return (
        Plant_list,
        Map_plant_tech,
        Map_plant_node,
        hydro_capacities_MW,
        hydro_storage_MWh,
        hydro_capacities_pumping_MW,
        Map_consumer_plant,
    )


def read_ror_Infeed_data(
    weather_year, Node_list, merge_some_countries, target_merge_countries, ror_annual_TWh_CH
):
    """
    Read the ROR Infeed data from the parquet file input/hydro_PECD/PECD_EERA2021_ROR_2030_gen.parquet and save them in a dictionary.
    The values are fixed throughout the scenarios, so there are no scenario required as arguments to the function.
    Output:
        ror_Infeed_data: dictionary with keys in the form of "region_ror" (plant names) and day_N with final values in MWh (e.g., ('CH00', 'day_305') 31796.0)
        for hourly generation, values should be divided by 24
    """

    hydro_inflow_data = pd.read_parquet(
        "input/hydro_PECD/PECD_EERA2021_ROR_2030_gen.parquet"
    )

    # in case BFE has asked to achieve an annual ROR generation in TWh for CH00 (to be specified in settings by having the value in ror_annual_TWh_CH setting)
    if ror_annual_TWh_CH: 
        # calculate total annual generation in TWh for area_name CH00
        annual_gen_CH00 = hydro_inflow_data[
            (hydro_inflow_data["area_name"] == "CH00")
            & (hydro_inflow_data["year"] == str(weather_year))
        ]["gen_GWh"].sum() / 1000

        # scale the generation in CH00 to match the annual generation in ror_annual_TWh_CH
        scale_to_BFE = ror_annual_TWh_CH / annual_gen_CH00

        hydro_inflow_data.loc[
            (hydro_inflow_data["area_name"] == "CH00")
            & (hydro_inflow_data["year"] == str(weather_year)),
            "gen_GWh"
        ] *= scale_to_BFE
    #-------------------------------------------------------------------------------

    hydro_inflow_data = merge_country_regions_inflow(
        hydro_inflow_data, "ror_inflow", merge_some_countries, target_merge_countries
    )

    hydro_inflow_data["Day"] = hydro_inflow_data["Day"].astype(int)
    hydro_inflow_data["year"] = hydro_inflow_data["year"].astype(int)
    # hydro_inflow_data[(hydro_inflow_data.area_name=="CH00")&(hydro_inflow_data.year==1982)].sum()

    ror_Infeed_daily_data = {}
    ror_Infeed_hourly_data = {}
    Plant_list = []
    Map_plant_tech = {}
    Map_plant_node = {}

    for region in Node_list:
        # print(region)
        data_subset = hydro_inflow_data[
            (hydro_inflow_data["area_name"] == region)
            & (hydro_inflow_data["year"] == weather_year)
        ]
        grouped_data = data_subset.groupby("Day").first()["gen_GWh"]
        if (
            not grouped_data.isnull().all()
        ):  # if there is at least one value for the region
            plant_name = region + "_ror"
            Plant_list.append(plant_name)
            Map_plant_tech[plant_name] = "ror"
            Map_plant_node[plant_name] = region
            for day in range(1, 366):
                key = (region + "_fixedconsumer", "ror", "day_" + str(day))
                ror_Infeed_daily_data[key] = round(1000 * grouped_data.get(day, 0), 0)
    mapping_day_to_t = timemapping_creator("day", "t")
    for key in ror_Infeed_daily_data.keys():
        for new_time in mapping_day_to_t[key[2]]:
            # 168 has changed to len(mapping_day_to_t[key[2]], which is 24
            ror_Infeed_hourly_data[(key[0], key[1], new_time)] = (
                ror_Infeed_daily_data[key] / len(mapping_day_to_t[key[2]])
            )
    # export inflow_data_weekly_hourly with 7 digits after the comma
    return ror_Infeed_hourly_data, Plant_list, Map_plant_tech, Map_plant_node


def read_RES_avail_data(weather_year, Node_list, run_year=None, high_resolution_PV=False):
    """
    Read renewable availability factors of a given technology data from csv file and store in dictionary Avail_plant_region.

    Arguments:
    weather_year -- integer, year of the weather data

    Returns:
    Avail_plant_RES_region -- dictionary, keys are the names of the regions (country/regions), values are lists of the renewable availability factors.
    e.g. ('NOS0_windof', 't_207'): 0.514291
    Avail_plant_RES_region[region_tech,t_N] -- float, renewable availability factor of RES plant of type "tech" region "region" in time step t

    """

    Avail_plant_RES_region = {}

    # Step 1: create list of file names and tech names for RES availability factors
    # read data for nodes except for internal CH subnodes, if applicable --------------------------------------------------------------------
    res_tech_list = ["windon", "windof", "pv"]
    file_names = {
        tech: "input/RES_PECD/"
        + tech
        + "_2030_"
        + str(weather_year)
        + ".csv"
        for tech in res_tech_list
    }
    res_name_mapping = {tech: tech for tech in res_tech_list}
    res_name_mapping = {
        "windon": "windon",
        "windof": "windof",
        "pv": "pvrf",
    }
    # CH has several subnodes, so we need to analyzed separately
    Res_capacity_node_list = [node for node in Node_list if node != "CH00"]

    # Step 2: read files of RES availability factors and store in Avail_plant_RES_region

    for RES_tech in res_tech_list:
        with open(
            file_names[RES_tech],
            newline="",
        ) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                for region in Res_capacity_node_list:
                    plant_name = region + "_" + res_name_mapping[RES_tech]
                    try:
                        Avail_plant_RES_region[plant_name, row["t"]] = round(
                            float(row[region]), 7
                        )
                    except KeyError:
                        if row["t"] == "t_1":
                            print(
                                "No values found for ",
                                plant_name,
                                " in ",
                                row["t"],
                                " in file ",
                                file_names[RES_tech],
                            )
                    except ValueError:
                        if row["t"] == "t_1":
                            print(
                                "ValueError for ",
                                plant_name,
                                " in ",
                                row["t"],
                                " in file ",
                                file_names[RES_tech],
                            )

    # Step 3: read data for internal CH subnodes and apply correcting coefficients ----------
    # Step 3.1: create list of file names and tech names for RES availability factors
    pv_tech_list = ["pvrf", "pvap"] # pvrf indicates the data from pv plants (mostly actually no rooftop), pvap indicates alpine pv (data not complete yet)
    file_names = {
        tech: "input/RES_EMHIRES/" + tech + "_" + str(weather_year) + ".csv"

        for tech in pv_tech_list
    }
    res_name_mapping = {
        "pvrf": "pvrf",
        "pvap": "pvap",
        # "windon": "windon",
    }
    #NOTE: in the case of NexusE, the data already includes performance_ratio and inverter_efficiency included in calculation of availability factors, therefore set to 1
    performance_ratio = 1    # Table 26: Additional parameters of the PV and PVB system. Source Nexus-E
    inverter_efficiency = 1


    # Step 3.2: reading data and applying coeffients of correction, if needed ------------------------------------------------------------------
    # PV technologies --------------------------------------------------------------
    if high_resolution_PV:
        from model.high_res_PV import load_high_res_PV
        _, hires_avail = load_high_res_PV(weather_year, run_year)
        Avail_plant_RES_region.update(hires_avail)
        # Per-plant CH00_*_pvrf availability is loaded ADDITIONALLY here.
        # The EMHIRES pvrf loop below still runs because preexisting installed
        # PV at CH01..CH07 (from TYNDP) is keyed by CHxx_pvrf and still needs
        # availability factors — only the *investment candidates* are switched
        # to per-plant in read_plant_non_hydro_data.
    pv_tech_list_to_load = pv_tech_list

    for RES_tech in pv_tech_list_to_load:
        # if the file does not exist, skip the loop
        if not os.path.exists(file_names[RES_tech]):
            print("File not found: ", file_names[RES_tech])
        else:
            # read the file
            af_df = pd.read_csv(file_names[RES_tech], header=0, index_col=0)
            # # read file for OREES style
            # # af_df = pd.read_csv(file_names[RES_tech], header=None, index_col=None)

            # consider performance_ratio and inverter_efficiency
            af_df = af_df * performance_ratio * inverter_efficiency

            # set availability of the plant for each region
            for region in ch_subnode_list:
                plnat_name = region + "_" + res_name_mapping[RES_tech]
                column_order = int(region[2:]) - 1
                for t in range(af_df.shape[0]):
                    Avail_plant_RES_region[plnat_name, "t_" + str(t + 1)] = af_df.iloc[
                        t, column_order
                    ]
                    # Avail_plant_RES_region["CH01_pvnu", "t_7760"]
                    # Avail_plant_RES_region["CH01_pvrf", "t_18"]

    # wind data from ninja --------------------------------------------------
    wind_tech_list = [
        "windon",
    ]
    file_names = {
        tech: "input/RES_EMHIRES/" + tech + "_w" + str(weather_year) + ".csv"
        for tech in wind_tech_list
    }

    #NOTE: find another source for wind data in CH
    # current source, ninja, has wind availability factors that are too low, averaging 0.11
    # to get to average values in PECD, in wind_ch_avg_avail_target, we need to scale up af_df            
    # wind_ch_avg_avail_target = { 
    #     1995: 0.267146007,
    #     2007: 0.271899222,
    #     2008: 0.247289221,
    # }
    
    for RES_tech in wind_tech_list:
        af_df = pd.read_csv(file_names[RES_tech], header=0, index_col=0)

        # caluculate annual average availability factor for columns "CH01" to "CH07"
        # wind_ch_avg_avail_ninja = af_df[ch_subnode_list].mean(axis=1).mean()

        # coeff = wind_ch_avg_avail_target[weather_year] / wind_ch_avg_avail_ninja
        coeff = 1

        # multiply the values in af_df by coeff
        af_df = af_df * coeff

        for region in ch_subnode_list:
            plnat_name = region + "_" + RES_tech
            # column_order = int(region[2:])
            for t in af_df.index:
                Avail_plant_RES_region[plnat_name, t] = af_df.loc[t, region]

    return Avail_plant_RES_region


def read_RES_capacities(
    eu_policy, ch_policy, year, Node_list, RES_EU_coefficient, RES_CH_coefficient, PVRF_CH_coefficient, Windon_CH_coefficient,
):
    """
    Read RES capacity data from TYNDP-2022 files and store in dictionary Res_capacity_dict.
    Input:
    scenario: string, scenario name (long name with space, e.g., "National Trends)
    year: integer, year of the weather data

    Output:
    Plant_list: list of plants. e.g. 'BE00_pvrf', 'BE00_windon', 'BE00_windof'
    Res_capacity_dict: dictionary with the values in the index as keys and the values in the column "Value" as values.
    e.g 'MK00_windon': 100.0
    """

    from model.mappings import Map_planttech_SM_ours

    Plant_list = []
    Map_plant_tech = {}
    Map_plant_node = {}
    
    Res_capacity_data = pd.read_csv(
        r"input/res_capacities_TYNDP22.csv", header=0, index_col=False
    )
    Res_capacity_CH_data = pd.read_csv(
        r"input/res_capacities_CH.csv", header=0, index_col=False
    )

    # add CH data to EU data
    Res_capacity_data = pd.concat([Res_capacity_data, Res_capacity_CH_data])

    # find unique values in the column "node" and save them as a list
    Res_capacity_node_list = Res_capacity_data["node"].unique().tolist()

    # from Res_capacity_node_list, remove values that are not in Node_list
    # Res_capacity_node_list is equal to values that are in both Res_capacity_node_list and  Node_list, plus ch_subnode_list
    Res_capacity_node_list = [
        x for x in Res_capacity_node_list if x in Node_list
    ] + ch_subnode_list

    # for every element in Res_capacity_node_list, read the value in in the column "Value" if in that row there is "Capacity" in the column "Parameter"
    Res_capacity_dict = {}

    for node in Res_capacity_node_list:
        for tech in ["pvrf", "windon", "windof"]:
            # add node+ "_" + Map_planttech_SM_ours[tech] to list Plant_list
            plant_name = node + "_" + tech
            if node.startswith("CH"):
                scenario = ch_policy
                assigned_node = "CH00"
                if tech == "pvrf":
                    increase_coef = RES_CH_coefficient * PVRF_CH_coefficient
                elif tech == "windon":
                    increase_coef = RES_CH_coefficient * Windon_CH_coefficient
                else:
                    increase_coef = RES_CH_coefficient
            else:
                scenario = eu_policy.replace(" ", "")
                assigned_node = node
                increase_coef = RES_EU_coefficient

            try:
                Res_capacity_dict[plant_name] = (
                    Res_capacity_data.loc[
                        (Res_capacity_data["name"] == plant_name)
                        & (Res_capacity_data["node"] == node)
                        & (Res_capacity_data["scenario"] == scenario)
                        # & (Res_capacity_data["year"] == year),
                        # "value",
                    ]
                    .loc[:, str(year)]
                    .values[0]
                    * increase_coef
                )  # type: ignore
                Plant_list.append(plant_name)
                Map_plant_node[plant_name] = assigned_node
                Map_plant_tech[plant_name] = tech
            except IndexError:
                if not (tech == "windof" and node in nodes_without_offshore_wind):
                    print("No data for " + plant_name)

    return Plant_list, Map_plant_tech, Res_capacity_dict, Map_plant_node

def cross_match_plant_list(Plant_capacity_gen_list, Plant_non_hydro_list):
    """ "
    This function checks if the plants in Plant_capacity_gen_list and Plant_non_hydro_list are the same.
    If not, it prints the plants that are in Plant_capacity_gen_list, but not in Plant_non_hydro_list and vice versa.
    """
    Plant_capacity_gen_common_list = list(
        set(Plant_capacity_gen_list) & set(Plant_non_hydro_list)
    )  # find values that are only in Plant_capacity_gen_list and Plant_non_hydro_list, not both
    # find values that are in Plant_capacity_gen_list, but not Plant_capacity_gen_common_list
    Plant_capacity_gen_diff_list = list(
        set(Plant_capacity_gen_list) - set(Plant_capacity_gen_common_list)
    )
    # find values that are in Plant_non_hydro_list, but not Plant_capacity_gen_common_list
    Plant_non_hydro_diff_list = list(
        set(Plant_non_hydro_list) - set(Plant_capacity_gen_common_list)
    )
    # if Plant_capacity_gen_diff_list is not empty, print the values in Plant_capacity_gen_diff_list
    if Plant_capacity_gen_diff_list != []:
        print(
            "The following plants are in capacities_....csv, but not in plants_....csv:"
        )
        print(Plant_capacity_gen_diff_list)
        # abort running the program and print the message in the brackets
        # Exception("Some plants cross-mismatch issue (1), see above")

    if (
        Plant_non_hydro_diff_list != []
    ):  # if Plant_non_hydro_diff_list is not empty, print the values in Plant_non_hydro_diff_list
        print(
            "The following plants are in plants_....csv, but not in capacities_...csv:"
        )
        # sort Plant_non_hydro_diff_list alphabetically
        print(Plant_non_hydro_diff_list)

        # Exception("Some plants cross-mismatch issue (2), see above")
    return Plant_non_hydro_diff_list


def read_plant_non_hydro_data(allow_res_investment, Node_list, battery_investment_nodes_in_addition_to_CH, CH_only=False, weather_year=None, run_year=None, high_resolution_PV=False):
    """
    Read plant data from plants_non_hydro.csv file and store data in:
    Plant_non_hydro_list: list of plants
    Map_plant_node: dictionary with the values in the index as keys and the values in the column "node" as values
    Map_plant_tech: dictionary with the values in the index as keys and the values in the column "plant_type" as values
    CH_only: boolean, if True, filter out investment candidates from non-CH countries
    """
    from model.mappings import Map_planttech_SM_ours

    Plant_non_hydro_data_EU = pd.read_csv(
        r"input/plants_non_hydro.csv", header=0, index_col=0
    )

    # only keep the rows who has any elements of Node_list in column node
    Plant_non_hydro_data_EU = Plant_non_hydro_data_EU[
        Plant_non_hydro_data_EU["node"].isin(Node_list)
    ]

    Plant_non_hydro_data_CH = pd.read_csv(
        r"input/plants_non_hydro_CH.csv", header=0, index_col=0
    )

    # add CH data to EU data
    Plant_non_hydro_data = pd.concat(
        [Plant_non_hydro_data_EU, Plant_non_hydro_data_CH]
    )

    # if the option allow_investment is activated, read the data from plants_res_CH.csv. Otherwise, create an empty dataframe and an empty list
    if allow_res_investment:
        Plant_res_ch_data = pd.read_csv(
            r"input/plants_invest_candidates_res_CH.csv",
            header=0,
            index_col=0,
        )
        
        # In CH_only mode, filter out investment candidates from non-CH countries
        if CH_only:
            # Keep only plants where the market/node is in Node_list (which should be ['CH00'] in CH_only mode)
            Plant_res_ch_data = Plant_res_ch_data[
                Plant_res_ch_data["market"].isin(Node_list)
            ]
            print(f"CH_only mode: filtered investment candidates to only CH markets")

        if high_resolution_PV:
            from model.high_res_PV import load_high_res_PV
            hires_plants, _ = load_high_res_PV(weather_year, run_year)

            # drop the 7 aggregated CHxx_pvrf rows
            idx_match = pd.Series(
                Plant_res_ch_data.index.str.match(r"^CH0[1-7]_pvrf$"),
                index=Plant_res_ch_data.index,
            )
            mask_old_pvrf = Plant_res_ch_data["tech"].eq("pvrf") & idx_match
            n_removed = int(mask_old_pvrf.sum())
            Plant_res_ch_data = Plant_res_ch_data[~mask_old_pvrf]

            # append per-plant candidates
            Plant_res_ch_data = pd.concat([Plant_res_ch_data, hires_plants])
            print(
                f"[high_res_PV] removed {n_removed} aggregated CHxx_pvrf candidates, "
                f"added {len(hires_plants)} per-plant candidates"
            )

        # create the list P_list_fuelswitching_plants, which is the list of plants in which column fuel_switching in Plant_res_ch_data has value of TRUE
        P_list_fuelswitching_plants = Plant_res_ch_data[
            Plant_res_ch_data["fuel_switching"] == True
        ].index.tolist()

        # Plant_investment_RES_CH_list is the list of plants in Plant_res_ch_data, if the value of plant_type column is "RES"
        Plant_investment_RES_CH_list = Plant_res_ch_data[
            Plant_res_ch_data["plant_type"] == "RES"
        ].index.tolist()

        Plant_investment_non_RES_CH_list = Plant_res_ch_data[
            Plant_res_ch_data["plant_type"] != "RES"
        ].index.tolist()

    else:
        Plant_res_ch_data = pd.DataFrame()
        Plant_investment_RES_CH_list = []
        Plant_investment_non_RES_CH_list = []
        P_list_fuelswitching_plants = []
    # Plant_hydro_EU = pd.read_csv(r'input/plants_hydro_EU.csv', header=0, index_col=0)  # NOTE: hydro data are being imported from PECD database for 2030 (no extra expansion was observed in TYNDP dataset anyways)
    # Plant_hydro_CH = pd.read_csv(r'input/plants_hydro_CH.csv', header=0, index_col=0)  # NOTE: hydro data are being imported from PECD database for 2030 (no extra expansion is currently modelled in CH)
    # Plant_all_data = pd.concat([Plant_non_hydro_data, Plant_hydro_EU, Plant_hydro_CH])
    Plant_all_data = pd.concat(
        [Plant_non_hydro_data, Plant_res_ch_data], ignore_index=False
    )  # + Plant_res_ch_data  Plant_non_hydro_data
    # if any of the keys of Map_planttech_SM_ours is mentioned as part of index of Plant_all_data, replace it with the value of Map_planttech_SM_ours
    Plant_all_data.index = Plant_all_data.index.str.replace(
        "|".join(Map_planttech_SM_ours.keys()),
        lambda x: Map_planttech_SM_ours[x.group()],
        regex=True,
    )
    Plant_all_data["tech"] = Plant_all_data["tech"].replace(Map_planttech_SM_ours)
    # save values in index as a list
    Plant_list = Plant_all_data.index.tolist()
    # save a dictionary with the values in the index as keys and the values in the column "node" as values
    Map_plant_node = Plant_all_data["market"].to_dict()
    # NOTE: if multiple nodes within CH, "node" should be used instead of "market", then several regions within CH should be connected
    # save a dictionary with the values in the index as keys and the values in the column "plant_type" as values
    Map_plant_tech = Plant_all_data["tech"].to_dict()
    Map_consumer_plant = {}
    # save a dictionary with the values in the index as keys and the values in the column "consumer" as values
    Map_plant_consumer = Plant_all_data["market"].to_dict()
    # Store numerical info for the candidate RES investments in CH: save columns gen_max_limit and energy_max_limit into a dictionary
    if allow_res_investment:
        Plant_investment_data = Plant_res_ch_data[["gen_max_limit", "energy_max_limit"]].to_dict()
    else:
        Plant_investment_data = {"gen_max_limit": {}, "energy_max_limit": {}}

    # for every unique value in values of Map_plant_consumer, find all keys that have that value and save them as the dictionary Map_consumer_plant
    for consumer in set(Map_plant_consumer.values()):
        Map_consumer_plant[consumer] = [
            k for k, v in Map_plant_consumer.items() if v == consumer
        ]

    # This enabled additional nodes to be able to invest in battery capacities.
    # Please note that this is still possible by adding the respective information to plants_invest_candidates_res_CH.csv
    # but here it was also possible to do it via the settings.

    # Turns the additional battery investment nodes from a string into a list, e.g. "node1, node2" -> ["node1", "node2"].
    # Skip gracefully if the setting is None/empty/whitespace.
    if battery_investment_nodes_in_addition_to_CH is None or pd.isna(battery_investment_nodes_in_addition_to_CH):
        additional_battery_nodes = []
    else:
        nodes_raw = str(battery_investment_nodes_in_addition_to_CH).strip()
        if nodes_raw == "" or nodes_raw.lower() == "nan":
            additional_battery_nodes = []
        else:
            additional_battery_nodes = [item.strip() for item in nodes_raw.split(',') if item.strip()]

    if additional_battery_nodes and allow_res_investment:
        from model.structural_parameters import add_additional_batteries
        Plant_res_ch_data = add_additional_batteries(
            additional_battery_nodes,
            Plant_list,
            Plant_investment_non_RES_CH_list,
            Plant_investment_RES_CH_data=Plant_res_ch_data,
            Map_plant_node=Map_plant_node,
            Map_plant_tech=Map_plant_tech,
            Map_consumer_plant=Map_consumer_plant
        )

        # Recompute investment limits to include newly added candidates
        Plant_investment_data = Plant_res_ch_data[["gen_max_limit", "energy_max_limit"]].to_dict()

    return (
        Plant_list,
        Plant_investment_RES_CH_list,
        Plant_investment_non_RES_CH_list,
        Plant_investment_data,
        Map_plant_node,
        Map_plant_tech,
        Map_consumer_plant,
        P_list_fuelswitching_plants
    )


def read_plant_non_hydro_capacities(scenario_EU, scenario_CH, year):
    """
    Read plant capacity data from nonhydro_capacities_gen.csv file and store data in:
    Plant_capacity_dict: dictionary with the values in the index as keys and the values in the column "year" and the given scenario as values
    """
    Plant_capacity_nonhydro_data = pd.read_csv(
        r"input/nonhydro_capacities_gen.csv", header=0, index_col=0, comment='#',
    ).fillna(0)

    Plant_capacity_nonhydro_data_CH = pd.read_csv(
        r"input/nonhydro_capacities_gen_CH.csv", header=0, index_col=0
    ).fillna(0)

    # add CH data to EU data
    Plant_capacity_nonhydro_data = pd.concat(
        [Plant_capacity_nonhydro_data, Plant_capacity_nonhydro_data_CH]
    )

    # Plant_capacity_nonhydro_list = Plant_capacity_nonhydro_data.index.tolist()
    Plant_capacity_EU = Plant_capacity_nonhydro_data[str(year)][
        Plant_capacity_nonhydro_data["scenario"] == scenario_EU
    ].to_dict()

    # increase generation capacity in edge-of-the-model regions, to avoid unreasonbale lost load
    # values taken from dividing lost load in the base case (GA 2050, 2 1995) and divide it by 8760 h
    capacities_to_be_added = {
        "HU00": 1 * 10000,  # 4373
        "SK00": 1 * 10000,  # 2710,
        "HR00": 1 * 5000,  # 1219
        "PL00": 1 * 5000,  # 1212,
        "SE04": 1 * 5000 / 4,  # 74,
        "SE03": 1 * 5000 / 4,  # 73,
        "SE02": 1 * 5000 / 4,  # 66,
        "SE01": 1 * 5000 / 4,  # 62,
        "UK00": 1 * 5000,  # 28,
    }
    for country in capacities_to_be_added:
        plant = country + "_gas"
        # print(f"for {plant}, capacity changed from {Plant_capacity_EU[plant]} to {Plant_capacity_EU[plant] + capacities_to_be_added[country]}")
        Plant_capacity_EU[plant] = (
            Plant_capacity_EU[plant] + capacities_to_be_added[country]
        )
    print('Since TYNDP22 data is used and to avoid unreasonable lost load, the generation capacities of gas plants in edge-of-the-model regions have been increased.')

    Plant_capacity_CH = Plant_capacity_nonhydro_data[str(year)][
        Plant_capacity_nonhydro_data["scenario"] == scenario_CH
    ].to_dict()
    Plant_capacity_nonhydro_list = list(Plant_capacity_EU.keys()) + list(
        Plant_capacity_CH.keys()
    )

    return Plant_capacity_nonhydro_list, Plant_capacity_EU, Plant_capacity_CH


def read_demand_data(
    eu_policy, ch_policy, Node_list, year, weather_year, reduce_inflex_demand_by, BA_el_con, reduce_BE_FR_day_nine_and_ten_demand_to_percent
):
    """
    Read demand data from csv file and store in dictionary demand_data.

    Arguments:
    scenario -- string, name of the scenario
    year -- integer, year of the scenario
    weather_year -- integer, year of the weather data
    reduce_inflex_demand_by -- float, an amount in MWh by which the inflexible demand is reduced. Each hour is reduced by a certain percentage to reach to total desired reduction.

    Returns:
    demand_data -- dictionary, keys are the names of the consumers with fixed demand (country/regions), values are lists of the demand in MW

    """

    Demand_data = {}

    file_name_tyndp = (
        "input/demand/demand_"
        + eu_policy
        + "_"
        + str(year)
        + "_"
        + str(weather_year)
        + ".csv"
    )

        # read demand data for all nodes except CH00 ---------------------------------
        # source: TYNDP

    with open(
        file_name_tyndp,
        newline="",
    ) as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            # taret_zone_list is Node_list minus CH00
            target_zone_list = [zone for zone in Node_list if "CH0" not in zone]
            for consumer in target_zone_list:
                # read values in row[consumer] with only 1 decimal
                Demand_data[
                    consumer + "_fixedconsumer", "fixed", "t_" + row["t"]
                ] = round(float(row[consumer]), 1)

    # read demand data for Switzerland --------------------------------------------------
    # source data for CH00 comes from TYNDP 2022
    # prognos do not provide time series for weather years (also 2050), therefore tyndp 2022 data is used, and scaled to match the total demand in the CH scenario

    # read profile of demand ------------------------------------------------
    file_name_tyndp_ch = (
        "input/demand/demand_"
        + ch_policy + "_"
        + str(year)
        + ".csv"
    )

    # TYNDP scenario is fixed (DistributedEnergy is used, but GlobalAmbition was also a valid option) so that the comparison of results is possible more uniformly
    demand_ch = pd.read_csv(file_name_tyndp_ch, header=0, index_col=0).loc[:, "CH00"]

    demand_ch_corrected = pd.concat([demand_ch.iloc[0:24], 
                    demand_ch.iloc[48:1344], 
                    demand_ch.iloc[1320:1344],
                    demand_ch.iloc[1344:]])
    
    # add index to demand_ch, starting from t_6553 to t_8760 and then continue from t_1 to t_6552
    # important: Prognos data follow hydro year. TYNDP data follow calendar year.
    demand_ch_corrected.index = pd.Index(["t_" + str(i) for i in range(1, 8761)])

    # Reduce the inflexible demand by the amount given in the settings
    current = sum(demand_ch_corrected)
    target = current - reduce_inflex_demand_by
    demand_ch_corrected = demand_ch_corrected * target / current

    # subtract the electricity demand from the heatpump operation from the demand here because it is not supposed to be considered twice
    # (Once seperately but also included in the overall demand here already)
    demand_ch_corrected -= BA_el_con.sum(axis=1)

    # export to Demand_data
    for t in demand_ch_corrected.index:
        Demand_data["CH00_fixedconsumer", "fixed", t] = round(demand_ch_corrected[t], 1)

    # The snippet below allowed for relaxing the French and Belgian demand of a particular difficult time period. Those couple of hours are driving up prices and investments in 2009.

    # if reduce_BE_FR_day_nine_and_ten_demand_to_percent != 1.0:
    #     reduce_fr_be_demand(Demand_data, reduce_BE_FR_day_nine_and_ten_demand_to_percent)

    return Demand_data

def read_fuel_limit_data(ch_policy, run_year, limit_fuel_import_CH, limited_fuels_import_CH_list):
    """
    Read fuel data from csv file and store in dictionary fuel_data.

    Arguments:
    ch_policy -- string, name of the CH policy
    run_year -- integer, year of the run (e.g., 2050)
    limit_fuel_import_CH -- indicating whether fuel import to CH is allowed, False if not allowed, a float if allowed (float indicating the limit as percentage of total allowable import)
    limited_fuels_import_CH_list -- list of fuels that are limited in import to CH

    Returns:
    fuel_capacity_annual -- dictionary, indicating import, storage, production capacities for each fuel type
            keys fuel types and values are themselves dictionaries with one of the following keys, namely "import_capacity_annual", "production_capacity_CH", "storage_potential_capacity", and value read from the csv file
    
    """

    # read input/fuel_limit.csv, with first three columns as index
    read_fuel_limit_data = pd.read_csv(
        "input/fuel_limits.csv", header=0, index_col=[0, 1, 2], comment='#',
    )
    
    fuel_capacity_annual = {}
    for fuel in read_fuel_limit_data.index.get_level_values(0).unique():
        fuel_capacity_annual[fuel] = {}
        for feature in read_fuel_limit_data.index.get_level_values(1).unique():

            # assign the features, but first apply import limits to CH if limit_fuel_import_CH is False (fuel import to CH is not allowed)
            if fuel in limited_fuels_import_CH_list and limit_fuel_import_CH != False and feature == "import_capacity_annual":
                fuel_capacity_annual[fuel][feature] = limit_fuel_import_CH * read_fuel_limit_data.loc[
                        (fuel, feature, ch_policy), str(run_year)
                    ] # type: ignore
            else:
                # if the value read_fuel_limit_data.loc[(fuel, feature, ch_policy), str(run_year)], asssign it to fuel_capacity_annual[fuel][feature]
                try:
                    fuel_capacity_annual[fuel][feature] = read_fuel_limit_data.loc[
                        (fuel, feature, ch_policy), str(run_year)
                    ]
                except KeyError:
                    #skip if the value is not found
                    pass

    return fuel_capacity_annual

def read_demandDH_data(run_year, weather_year, reduce_DH_demand_by):
    """	
    Read district heating demand data from csv file and store in dictionary demandDH_data.

    Arguments:
    ch_policy -- string, name of the CH policy
    NodeDH_list -- list of district heating nodes (e.g., ['DH01', 'DH02'])
    run_year -- integer, year of the run (e.g., 2050)
    weather_year -- integer, year of the weather data (e.g., 1995)
    reduce_DH_demand_by -- float, an amount in MWh by which the inflexible demand is reduced. Each hour is reduced by a certain percentage to reach to total desired reduction.

    Returns:
    demandDH_data -- dictionary, keys are pairs of (district heating nodes, time steps) and values are corresponding thermal demand in MW

    """
    demandDH_data = {}

    # reading district heating data ---------------------------------------------------------------------------------------   
    # find the csv file ---------------------------------
    file_name = (
        "input/demand/DH_large_profiles_"
        + str(run_year)
        + "_"
        + str(weather_year)
        + "_agg.csv"
    )

    # read the file using pandas
    demandDH_data_df = pd.read_csv(file_name, header=0, index_col=0)

    for region in demandDH_data_df.index:
        for t in range(1, 8761):
            demandDH_data["DH_" + region, "t_" + str(t)] = demandDH_data_df.loc[region].iloc[t-1] # type: ignore

    # reading demand data for medium size DH (there is only one aggregate for the whole country) ---------------------------------------------------------------------------------------
    demandDH_data_df = pd.read_csv("input/demand/DH_medium_profiles_"
        + str(run_year)
        + "_"
        + str(weather_year)
        + "_agg.csv", header=0, index_col=0).T
    # name it DH_medium
    region = "DH_medium"
    for t in range(1, 8761):
        demandDH_data["DH_medium", "t_" + str(t)] = demandDH_data_df.iloc[0,t-1]

    # reading low temperature industrial load ---------------------------------------------------------------------------------------
    demandIDL_data_df = pd.read_csv("input/demand/Industrie_Endenergieverbrauch_"
        + str(run_year)
        + "_0-100_agg.csv", header=0, index_col=0).T
     
    
    for region in demandIDL_data_df.index:
        region_normal_spelling = region.replace("ü", "ue").replace("ä", "ae").replace("ö", "oe")
        for t in range(1, 8761):
            demandDH_data["ILLT_" + region_normal_spelling, "t_" + str(t)] = demandIDL_data_df.loc[region].iloc[t-1]

    # reading high temperature industrial load ---------------------------------------------------------------------------------------
    demandIDH_data_df = pd.read_csv("input/demand/Industrie_Endenergieverbrauch_"
        + str(run_year)
        + "_100-200_agg.csv", header=0, index_col=0).T
    
    for region in demandIDH_data_df.index:
        region_normal_spelling = region.replace("ü", "ue").replace("ä", "ae").replace("ö", "oe")
        for t in range(1, 8761):
            demandDH_data["ILHT_" + region_normal_spelling, "t_" + str(t)] = demandIDH_data_df.loc[region].iloc[t-1]

    # adjusting the demand for DH demand according to the settings
    factor = (sum(demandDH_data.values()) - reduce_DH_demand_by) / sum(demandDH_data.values())
    demandDH_data = {k: v * factor for k, v in demandDH_data.items()}

    return demandDH_data


def read_plantDH_data_and_capacities(NodeDH_list, Node_list, run_year):
    """
    Read district heating plant data from csv files and store in dictionaries.
    The data includes plant characteristics and capacities.
    Also imports investment candidates for STES.

    Input:
        NodeDH_list -- list of district heating nodes (e.g., ['DH01', 'DH02'])
        Node_list -- list of all electric nodes
        run_year -- integer, year of the run (e.g., 2050)
        input\\plants_DH_CH_features.csv
        input\\plants_DH_CH_capacities.csv
        input\\plants_STES_invest_candidates.csv


    Output:
        PlantDH_list -- list of district heating plants
        Map_plantDH_nodeEl -- dictionary with the values in the index (plant names) as keys and the values in the column "node" as values
        Map_plantDH_nodeDH -- dictionary with the values in the index (plant names)as keys and the values in the column "node_DH" as values
        Map_nodeDH_plantDH -- the reverse of Map_plantDH_nodeDH
        Map_plantDH_tech -- dictionary with the values in the index (plant names)as keys and the values in the column "tech" as values
        Map_nodeDH_country -- assigning nodes to CH (the country they are in)
        PlantDH_capacity_CH -- dictionary with the values in the index (plant names) as keys and the values in the column "value" as values 
        PlantDH_data_dict -- dictionary to store remaining columns in PlantDH_data. They keys are (plant names, feature) and the values are the corresponding values in the csv file
        Plant_STES_investment_list -- list of plants of seasonal storage type in which investment is possible 
        Plant_investment_data_STES --  dictionary with the values in the index (plant names) as keys and the values in the columns "gen_max_limit" and "energy_max_limit" as values
    """
    # features of district heating plants ---------------------------------
    PlantDH_data = pd.read_csv(
        "input/plants_DH_CH_features.csv", header=0, index_col=0
    )

    # read the csv file STES_invest_candidates.csv ------------------------
    Plant_STES_data = pd.read_csv(
        "input/plants_DH_invest_candidates.csv", header=0, index_col=0
    )

    # merge PlantDH_data and Plant_STES_data
    PlantDH_data = pd.concat([PlantDH_data, Plant_STES_data])


    # keep rows in PlantDH_data if either one of these two conditions are met:
    # 1. the value in the column "nodeElec" is in Node_list
    # 2. the value in the column "nodeDH" is in NodeDH_list
    PlantDH_data = PlantDH_data[
        PlantDH_data["nodeElec"].isin(Node_list)
        | PlantDH_data["nodeDH"].isin(NodeDH_list)
    ]

    # list the values in column index as PlantDH_list
    PlantDH_list = PlantDH_data.index.tolist()
    PlantDH_invetment_list = Plant_STES_data.index.tolist()

    # save the values in column nodeDH as Map_plantDH_nodeDH, where keys are the values in PlantDH_list (index) ...
    Map_plantDH_nodeDH = PlantDH_data["nodeDH"].to_dict()
    Map_plantDH_nodeEl = PlantDH_data["nodeElec"].to_dict()
    Map_plantDH_tech = PlantDH_data["tech"].to_dict()


    # reverse the dictionary Map_plantDH_nodeDH to create a dictionary Map_nodeDH_plantDH where the keys are the values in Map_plantDH_nodeDH and the values are the keys in Map_plantDH_nodeDH. If there are similar keys in Map_plantDH_nodeDH, include all of them in the value list of the new reversed dictionary.
    Map_nodeDH_plantDH = {}
    for key, value in Map_plantDH_nodeDH.items():
        Map_nodeDH_plantDH.setdefault(value, []).append(key)
        
    # Map_nodeDH_country is a dictionary where the keys are the values in index and value is "CH"
    Map_nodeDH_country  = {node: "CH" for node in PlantDH_data["nodeDH"].unique()}

    # for all remaining columns in PlantDH_data, save the values in a dictionary named PlantDH_data_dict where the keys are pairs of the values in PlantDH_list (index) and column name  and the dictinoary value is the value in that column
    PlantDH_data_dict = {}
    for feature in PlantDH_data.columns:
        if feature not in ["nodeDH", "nodeElec", "tech"]:
            for PlantDH in PlantDH_list:
                PlantDH_data_dict[PlantDH, feature] = PlantDH_data.loc[PlantDH, feature]

    # capacities of district heating plants ---------------------------------
    # read the csv file plants_DH_CH_capacities.csv
    # if a row index is in PlantDH_list, save the value in column "run_year" as the value in PlantDH_capacity_CH with the row index as key
    PlantDH_capacity_data = pd.read_csv(
        "input/plants_DH_CH_capacities.csv", header=0, index_col=0 
    )

    PlantDH_capacity_CH = PlantDH_capacity_data[str(run_year)][
        PlantDH_capacity_data.index.isin(PlantDH_list)
    ].to_dict()

    # Plant_capacity_gen is the electrical electricity generation capacity. It is defined only over the plants that have electrical generation capability, i.e., if the plant is a CHP plant.
    # CHP plants are indicated by having a value of True in column "CHPDH" in PlantDH_data
    Plant_capacity_gen = {
        plant: PlantDH_capacity_CH[plant]
        for plant in PlantDH_list
        if PlantDH_data.loc[plant, "CHPDH"] == True
        if plant not in PlantDH_invetment_list
    }

    # investment data for STES plants ---------------------------------
    Plant_investment_data_STES = Plant_STES_data[
            ["gen_max_limit", "energy_max_limit"]
        ].to_dict()

    return PlantDH_list, Map_plantDH_nodeEl, Map_plantDH_nodeDH, Map_nodeDH_plantDH, Map_plantDH_tech, Map_nodeDH_country, PlantDH_data_dict, PlantDH_capacity_CH, Plant_capacity_gen, PlantDH_invetment_list, Plant_investment_data_STES

def ev_avail_discharge_calculator(base_consumption_pattern, plant_name, T_list):
    """ "
    For a given time series of base consumption, calculate the availability of EVs and discharge patterns.
    EVs are unavailable in an hour if their consumption is positive in the next hour.
    Discharge pattern is just the base_consumption_pattern.

    Input:
        base_consumption_pattern: time series of base consumption in form of a dictionary with keys 't_1', 't_2', ..., 't_8760'
        plant_name: string, name of the plant
    Return:
        ev_avail: time series of availability of EVs, a dictionary with plant name and time steps as keys (as a tuple) and of 0s and 1s as values. eg. ('ev_ID67', 't_1'): 1
        discharge_pattern: time series of EV discharge, a dictionary with plant name and time steps as keys (as a tuple). eg. ('ev_ID67', 't_1'): 0.4
    """
    ev_avail = {}

    # hours in which EVs are forced to be available, to avoid infesibility
    T_available_forced_list = [T_list[0]] + [T_list[1]] + T_list[-24:]

    # EVs are unavailable only in the hour before consumption moves from 0 to something positive

    for t in T_list:
        t_plus_1 = "t_" + str(int(t.split("_")[1]) + 1)
        if t in T_available_forced_list:
            # Forcing EVs to be available in the first two hours and last 24 hours of the simulation
            ev_avail[plant_name, t] = 1
        elif base_consumption_pattern[t_plus_1] > 0:
            ev_avail[plant_name, t] = 0
        else:
            ev_avail[plant_name, t] = 1

    discharge_pattern = {}
    for t in T_list:
        # if t in T_available_forced_list:
        #     # Forcing EVs to be not consuming  in the first two hours and last 24 hours of the simulation
        #     discharge_pattern[plant_name, t] = 0
        # else:
        t_int = int(t.split("_")[1])
        discharge_pattern[plant_name, t] = base_consumption_pattern["t_" + str(t_int)]

    return ev_avail, discharge_pattern


def timemapping_creator(originP, targetP):
    """
    Create a dictionary with the mapping between the originP and targetP time periods.
    Input:
        originP: string with the name of the origin time period (e.g., "week")
        targetP: string with the name of the target time period (e.g., "t")
    Output:
        map_originP_targetP: dictionary with keys in the form of "originP_x" (e.g., "week_1") and values in the form of "targetP_y" (e.g., map_originP_targetP['week_38']: array(['t_6217', 't_6218', 't_6219'...])
    """

    map_originP_targetP = {}
    if originP != "t":
        timemap = pd.read_csv("input/timemaps_hydro_year.csv")
        unique_x = timemap[originP].unique()
        for x_val in unique_x:
            map_originP_targetP[x_val] = timemap[timemap[originP] == x_val][
                targetP
            ].values
    else:  # to make the code more efficient, if the originP is already "t", just read the timemap file and save it in the dictionary
        timemap = pd.read_csv("input/timemaps_hydro_year.csv", index_col=0, header=0)
        unique_x = timemap.index.to_list()
        for x_val in unique_x:
            map_originP_targetP[x_val] = timemap.loc[x_val, targetP]

    return map_originP_targetP


# read inflow data for dam and psp_open


def read_inflow_data_hourly(
    weather_year,
    Node_list,
    rep_hydro_plants,
    merge_some_countries,
    target_merge_countries,
    hydro_inflow_TWh,
    pump_capacity_GW,
    adding_hydro_storage_cap_TWh,
):
    """
    Read the inflow data from the parquet file input/hydro_PECD/PECD_EERA2021_reservoir_pumping_2030_inflow.parquet and save them in a dictionary.
    The values are fixed throughout the scenarios, so there are no scenario required as arguments to the function.
    input:
        weather_year: integer, year of the weather data
        Node_list: list of nodes
        rep_hydro_plants: if True, the inflow data is read for representative hydro plants, otherwise for all hydro plants
    Output:
        inflow_data_hourly: dictionary with keys in the form of "region_RES_tech" (plant names) and week_1 with final values in MWh (e.g., ('NOS0_pumped_open', 't_1'): 977722.0)
    """
    Plant_inflow_list_TYNDP = []
    hydro_inflow_data_weekly = pd.read_parquet(
        "input/hydro_PECD/PECD_EERA2021_reservoir_pumping_2030_inflow.parquet"
    )

    # in case BFE asked to achieve an annual hydro generation
    if hydro_inflow_TWh:
        annual_CH_in_data = hydro_inflow_data_weekly[
            (hydro_inflow_data_weekly["area_name"] == "CH00")
            & (hydro_inflow_data_weekly["technology"] == "pumped_open")
            & (hydro_inflow_data_weekly["year"] == str(weather_year))
        ]["inflow_GWh"].sum()/1000
        scale = hydro_inflow_TWh / annual_CH_in_data

        # scale the inflow data, for CH00 and pumped_open and year
        hydro_inflow_data_weekly.loc[
            (hydro_inflow_data_weekly["area_name"] == "CH00")
            & (hydro_inflow_data_weekly["technology"] == "pumped_open")
            & (hydro_inflow_data_weekly["year"] == str(weather_year)),
            "inflow_GWh",
        ] = hydro_inflow_data_weekly.loc[
            (hydro_inflow_data_weekly["area_name"] == "CH00")
            & (hydro_inflow_data_weekly["technology"] == "pumped_open")
            & (hydro_inflow_data_weekly["year"] == str(weather_year)),
            "inflow_GWh",
        ] * scale
    # --------------------------------------------------------------------------------------------

    hydro_inflow_data_weekly = merge_country_regions_inflow(
        hydro_inflow_data_weekly,
        "reservoir_inflow",
        merge_some_countries,
        target_merge_countries,
    )

    hydro_inflow_data_weekly["Week"] = hydro_inflow_data_weekly["Week"].astype(int)
    hydro_inflow_data_weekly["year"] = hydro_inflow_data_weekly["year"].astype(int)

    inflow_data_weekly = {}
    for region in Node_list:
        for tech in ["reservoir", "pumped_open"]:
            data_subset = hydro_inflow_data_weekly[
                (hydro_inflow_data_weekly["area_name"] == region)
                & (hydro_inflow_data_weekly["technology"] == tech)
                & (hydro_inflow_data_weekly["year"] == weather_year)
            ]
            grouped_data = data_subset.groupby("Week").first()["inflow_GWh"]
            # renaming the technology to match the plant names in the model (reservior -> dam, pumped_open -> psp_open)
            # write a if statement to check if grouped_data is all nans
            if not grouped_data.isnull().all():
                plant_name = region + "_" + RES_tech_mapping_ERA5_ours[tech]

                # write a conditional statement that is True if rep_hydro_plants is True or if plant_name is not equal to "CH_psp_open"
                if (rep_hydro_plants == True) and (plant_name == "CH00_psp_open"):
                    rep_hydro_plants_data = pd.read_csv(
                        "input/hydro_PECD/PECD_EERA2021_reservoir_pumping_2030_table_representative_plants.csv",
                        header=0,
                    )

                    plant_names_list = rep_hydro_plants_data["name"].unique().tolist()
                    for plant_name in plant_names_list:
                        for N in range(1, 54):
                            key = (plant_name, "week_" + str(N))
                            # share is qual to value in the column "inflow_share" of the row where the column "name" is equal to plant_name
                            share = rep_hydro_plants_data.loc[
                                rep_hydro_plants_data["name"] == plant_name,
                                "inflow_share",
                            ].values[0]  # type: ignore
                            inflow_data_weekly[key] = (
                                1000 * round(grouped_data[N], 3) * share
                            )
                        Plant_inflow_list_TYNDP.append(plant_name)

                else:
                    for N in range(1, 54):
                        key = (plant_name, "week_" + str(N))
                        inflow_data_weekly[key] = 1000 * round(grouped_data[N], 3)
                    Plant_inflow_list_TYNDP.append(plant_name)

    inflow_data_hourly = {}
    mapping_week_to_t = timemapping_creator("week", "t")

    for key in inflow_data_weekly.keys():
        for new_time in mapping_week_to_t[key[1]]:
            # 168 used to be len(mapping_week_to_t[key[1]]), but this is not correct, because appearently the dataset reported values as if last week was a full week.
            inflow_data_hourly[(key[0], new_time)] = inflow_data_weekly[key] / 168
    # export inflow_data_weekly_hourly with 7 digits after the comma

    return inflow_data_hourly, Plant_inflow_list_TYNDP


def tou_tariff(Tariff_def, tariff_name, Consumer_list, T):
    """Returns the price of the tariff at time steps included in the list T.
    Input:
        Tarrif_def, in the tarrif named tarrif_No, there are keys "rates", has several sections (section_N) that includes hours in day (1 to 24) as a list of two elements and corresponding price in "price"
        Consumer_list: list of consumers to which the tariff_No applies
        T: list of time steps included in the tariff
    Output:
        tariff: dictionary with time steps as keys and corresponding price as values.
    """

    timemap = pd.read_csv("input/timemaps_hydro_year.csv")

    timemap["rate"] = "NA"
    timemap["tariff_name"] = "NA"

    # Iterate over the tariff definitions in the dictionary
    for sub_rate_name, sub_rate_definition in Tariff_def[tariff_name]["rates"].items():
        # Iterate over the weeks in the dictionary
        for week in sub_rate_definition["weeks"]:
            # Filter the DataFrame for rows where the week number matches the current week
            week_rows = timemap[timemap["week"] == "week_" + str(week)]

            # Iterate over the days in the "day_in_week" dictionary
            for day, hours in sub_rate_definition["day_in_week"].items():
                # Filter the DataFrame for rows where the day of the week matches the current day and the hour is within the range specified in the dictionary
                day_rows = week_rows[
                    (week_rows["day_in_week"] == day)
                    & (week_rows["hour_in_day"].isin(["hid_" + str(h) for h in hours]))
                ]

                # If the "rate" column has even one row with a value other than "NA", raise an error
                if not day_rows["rate"].isin(["NA"]).all():
                    raise ValueError(
                        "The tariff definition for "
                        + sub_rate_name
                        + " has overlapping hours with another tariff definition"
                    )

                # For these filtered rows, set the "rate" column to the "price" value from the dictionary
                timemap.loc[day_rows.index, "rate"] = sub_rate_definition["price"]

                timemap.loc[day_rows.index, "tariff_name"] = sub_rate_name

    # If any of the rows in the "rate" column are still "NA", raise an error
    if timemap["rate"].isin(["NA"]).any():
        raise ValueError(
            "The tariff definition for "
            + tariff_name
            + " is missing hours for some days."
        )

    tariff = {}

    # set column t in timemap as index
    timemap = timemap.set_index("t")
    # loop over consumers and time steps
    # NOTE: write this better
    for consumer in Consumer_list:
        for t in timemap.index:
            tariff[consumer, t] = timemap.loc[t, "rate"]

    Map_subrates_time = {}
    for subrate_name in timemap.tariff_name.unique():
        # Map_subrates_time[tariff_names_list] is equal to all values in colum t of timemap where the value in column tariff_name is equal to subrate_name
        Map_subrates_time[subrate_name] = timemap.loc[
            timemap.tariff_name == subrate_name, :
        ].index.to_list()
    return tariff, Map_subrates_time


def map_tech_to_plant(Plant_list, Data_per_plant, Data_per_tech, Map_plant_tech):
    """
    This function maps technology data to plants, only if already not assigned, and only if the tech is mentioned in Data_per_tech.
    If the technology of a plant matches the technology in the Data_per_tech, Data_per_plant[plant] will be equal to corresponding value in Data_per_tech.
    Input:
        Plant_list: list of plants
        Data_per_tech: data per technology (e.g., start condition of plants per technology)
    Output:
        Data_per_plant: dictionary with mapped values to plants start condition per plant, e.g., {Map_eff_in_plant["battery_1"] = 0.8}
    """
    Data_per_plant = {}
    for plant in Plant_list:
        # if Data_per_plant[plant] does not already have a value
        if plant not in Data_per_plant.keys():
            if Map_plant_tech[plant] in Data_per_tech.keys():
                Data_per_plant[plant] = Data_per_tech[Map_plant_tech[plant]]
    return Data_per_plant


def read_line_data(year, Node_list, T_list, NTC_CH_ratio, eu_policy, CH_only=False, scenario_name=None, neighbor_countries=None, neighbor_price_scenario=None):
    """
    Reads the line data from TYNDP 2022 NTC files.
    Input:
        year: year of the data (2025 or 2030)
        CH_only: if True, only keep lines connected to CH00 (for single country mode)

    Output:
        List_line: list of lines
            e.g., ['HVAC_AT00_CH00', 'HVAC_AT00_CZ00', 'HVAC_AT00_DE00', 'HVAC_AT00_HU00',...
        Map_line_node: dictionary with the values in the index as keys and the values in the column "node" as values
            e.g., {'HVAC_AT00_CH00': {'start_node': 'AT00', 'end_node': 'CH00'},
        ATC_exportlimit: dictionary with the values in the index as keys and the values in the column "value" as values
            e.g., {('HVAC_AT00_CH00', 't_1'): 1200.0, ('HVAC_AT00_CH00', 't_2'): 1200.0, ...
        ATC_importlimit: dictionary with the values in the index as keys and the values in the column "value" as values
            e.g., {('HVAC_AT00_CH00', 't_1'): 1200.0, ('HVAC_AT00_CH00', 't_2'): 1200.0, ...
    """
    import time

    ntc_year = 2050
    if year != ntc_year:
        print("--- WARNING! --- The NTC import and export data is only available for 2050. Therefore, 2050 is used for the NTC data.")

    start = time.time()
    
    List_line = []
    Map_line_node = {}
    ATC_importlimit = {}
    ATC_exportlimit = {}

    NTC_import_df = pd.read_csv(
        f"input/NTC/NTC_import_{eu_policy}_{ntc_year}.csv",
        header=0,
        index_col=0,
    )

    NTC_import_df.loc[NTC_import_df.index.str.contains("CH00"), "Import Capacity (MW)"] = (
        NTC_import_df.loc[NTC_import_df.index.str.contains("CH00"), "Import Capacity (MW)"]
        * NTC_CH_ratio
    )

    for line in NTC_import_df.index:
        start_node = line.split("-")[0]
        end_node = line.split("-")[1]

        # Different filtering logic for CH_only mode
        if CH_only:
            # In CH_only mode, keep lines where either node is CH00 (i.e., CH's border lines)
            keep_line = (start_node == "CH00" or end_node == "CH00")
        else:
            # Normal mode: both nodes must be in Node_list
            keep_line = (start_node in Node_list and end_node in Node_list)
            
        if keep_line:
            line_name = "HVAC_" + start_node + "_" + end_node
            List_line.append(line_name)
            Map_line_node[line_name] = {
                "start_node": start_node,
                "end_node": end_node,
            }
            for t in T_list:
                ATC_importlimit[(line_name, t)] = NTC_import_df.loc[
                    line, "Import Capacity (MW)"
                ]

    NTC_export_df = pd.read_csv(
        f"input/NTC/NTC_export_{eu_policy}_{ntc_year}.csv",
        header=0,
        index_col=0,
    )

    NTC_export_df.loc[NTC_export_df.index.str.contains("CH00"), "Export Capacity (MW)"] = (
        NTC_export_df.loc[NTC_export_df.index.str.contains("CH00"), "Export Capacity (MW)"]
        * NTC_CH_ratio
    )

    for line in NTC_export_df.index:
        start_node = line.split("-")[0]
        end_node = line.split("-")[1]

        # Different filtering logic for CH_only mode
        if CH_only:
            # In CH_only mode, keep lines where either node is CH00 (i.e., CH's border lines)
            keep_line = (start_node == "CH00" or end_node == "CH00")
        else:
            # Normal mode: both nodes must be in Node_list
            keep_line = (start_node in Node_list and end_node in Node_list)
            
        if keep_line:
            line_name = "HVAC_" + start_node + "_" + end_node
            line_reverse_name = "HVAC_" + start_node + "_" + end_node

            if line_name not in List_line:
                if line_reverse_name not in List_line:
                    List_line.append(line_name)
                    Map_line_node[line_name] = {
                        "start_node": start_node,
                        "end_node": end_node,
                    }
                else:
                    raise ValueError(
                        f"Line {line_name} and {line_reverse_name} are both in List_line"
                    )

            for t in T_list:
                ATC_exportlimit[(line_name, t)] = NTC_export_df.loc[
                    line, "Export Capacity (MW)"
                ]

    # ----------------------------------- neighbor prices for CH_only mode -----------------------------------
    # Load neighbor prices if CH_only mode is activated
    Line_trade_price = {}
    if CH_only and scenario_name and neighbor_countries and neighbor_price_scenario:
        
        print(f"Loading neighbor prices for countries: {neighbor_countries}")
        print(f"Using price scenario: {neighbor_price_scenario}")
        
        # Load neighbor prices CSV
        neighbor_prices_file = f"input/neighbour_prices_for_CH_only_mode/neighbor_prices_{neighbor_price_scenario}.csv"
        
        try:
            df_neighbor_prices = pd.read_csv(neighbor_prices_file)
            print(f"Loaded neighbor prices from: {neighbor_prices_file}")
            
            # Set time_step as index for efficient lookup
            df_neighbor_prices = df_neighbor_prices.set_index('time_step')
            
            # Create Line_trade_price dictionary: map each line and time step to corresponding neighbor price
            for line_name in List_line:
                # Find neighbor country connected to CH00 using Map_line_node
                start_node = Map_line_node[line_name]["start_node"]
                end_node = Map_line_node[line_name]["end_node"]
                
                if start_node == "CH00":
                    neighbor_country = end_node
                elif end_node == "CH00":
                    neighbor_country = start_node
                else:
                    continue  # Skip lines not connected to CH00
                
                # Store price for each time step in T_list
                for time_step in T_list:
                    if neighbor_country in df_neighbor_prices.columns:
                        price = df_neighbor_prices.loc[time_step, neighbor_country]
                        Line_trade_price[(line_name, time_step)] = price
            
            print(f"Created Line_trade_price mapping for {len(Line_trade_price)} line-time combinations")
            
        except FileNotFoundError:
            print(f"Warning: Neighbor prices file not found: {neighbor_prices_file}")
            print("CH_only mode will fail without neighbor prices!")
        except Exception as e:
            print(f"Error loading neighbor prices: {e}")
            print("CH_only mode will fail without neighbor prices!")

    return List_line, Map_line_node, ATC_exportlimit, ATC_importlimit, Line_trade_price


def calculate_infeed_TYNDP(
    Node_list,
    tech_infeed_all_list,
    gen_max_RES,
    Avail_plant_RES_year_scenario,
    T_list,
    Map_plant_tech_res,
    Map_plant_node_RES,
):
    """
    Calculates the infeed of RES for each node, RES infeed technology and time step.
    Input:
        Node_list: list of nodes to calculate the infeed for
        tech_infeed_all_list: list of technologies that are considered as infeed RES
        gen_max_RES: dictionary with maximum generation of RES per technology and node, e.g., gen_max_RES["AT00_windon"] = 1000
        Avail_plant_RES_year_scenario: dictionary with available capacity of RES per technology and node, e.g., dictionary key: (AT00_windon, t_1): 0.5
        T_list: list of time steps. e.g., [t_1, t_2, t_3...]
    Output:
        Infeed_fcn: dictionary with infeed of RES per node, technology and time step, e.g., Infeed_fcn["AT00_fixedconsumer", "windon", t_1] = 500

    """
    Infeed_fcn = {}  # defined over c,tech,t
    # for all c in Node_list, for all tech in tech_list_data_import, for all t in T_list: Infeed_TYNDP[c,tech,t] = Avail_plant[c,tech,t] * gen_max_RES[c,tech] for c in Node_list for tech in tech_list_data_import for t in T_list
    for node in Node_list:
        # find plants in the node
        plants_in_node = [
            plant for plant in Map_plant_node_RES if Map_plant_node_RES[plant] == node
        ]

        # find techs in the node, that is unique values of Map_plant_tech_res for plants in plants_in_node
        techs_in_node = list(
            set([Map_plant_tech_res[plant] for plant in plants_in_node])
        )

        for tech in techs_in_node:
            # Infeed_fcn[node + "_fixedconsumer", tech, t] is equal to sum of all Avail_plant_RES_year_scenario[plant, t] * gen_max_RES[plant] for all plants in plants_in_node of tech tech
            for t in T_list:
                Infeed_fcn[node + "_fixedconsumer", tech, t] = sum(
                    Avail_plant_RES_year_scenario[plant, t] * gen_max_RES[plant]
                    for plant in plants_in_node
                    if Map_plant_tech_res[plant] == tech
                )

        # plants_in_node = [plant for plant in Map_plant_node_RES if Map_plant_node_RES[plant] == n]
        # for tech in tech_infeed_all_list:
        #     for plant in plants_in_node:
        #         for t in T_list:
        #             for tech in tech_infeed_all_list:
        #                 Infeed_fcn[n + "_fixedconsumer", tech, t] = (
        #                     Avail_plant_RES_year_scenario[plant, t] * gen_max_RES[plant]
        #                 )

        # for tech in tech_infeed_all_list:
        #     # if gen_max_RES[c +"_" + tech] exists, then gen_max = gen_max_RES[c +"_" + tech]
        #     if n + "_" + tech in gen_max_RES:
        #         gen_max = gen_max_RES[n + "_" + tech]
        #         for t in T_list:
        #             Infeed_fcn[n + "_fixedconsumer", tech, t] = (
        #                 Avail_plant_RES_year_scenario[n + "_" + tech, t] * gen_max
        #             )
    return Infeed_fcn


def import_avail_plant(
    Plant_list,
    Plant_RES_CH_list,
    Plant_investment_RES_CH_list,
    T_list,
    Map_plant_node,
    Map_plant_tech,
    Map_node_country,
    Avail_plant_RES_year_scenario,
):
    """
    Imports the availability of capacity [0,1] of plants per technology, node and time step.
    Input:
        Plant_list: list of plants
        T_list: list of time steps
        Map_plant_node: dictionary with mapping of plants to nodes, e.g., Map_plant_node["battery_1"] = "AT00"
        Map_plant_tech: dictionary with mapping of plants to technologies, e.g., Map_plant_tech["AT00_battery"] = "battery"
        Map_node_country: dictionary with mapping of nodes to countries, e.g., Map_node_country["AT00"] = "AT"
    Output:
        Avail_plant: dictionary with available capacity of plants per technology, node and time step, e.g., Avail_plant["AT00_battery", t_1] = 0.95
    """

    import csv

    Avail_plant = {}

    data_dict = {}
    default_data = {}

    # read default data
    with open(r"input/availability_factor_conventional.csv", "r") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=",")
        fieldnames = reader.fieldnames
        # ensure that fieldnames is not None before trying to access its elements.
        if fieldnames is not None:
            for row in reader:
                country = row["country"]
                tech = row["technology"]
                month_value = {}
                for month in fieldnames[2:]:
                    month_value[month] = float(row[month])

                if country == "Default":
                    default_data[tech] = month_value
        else:
            print("fieldnames is None!")

    # read data per country
    with open(r"input/availability_factor_conventional.csv", "r") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=",")
        fieldnames = reader.fieldnames
        # ensure that fieldnames is not None before trying to access its elements.
        if fieldnames is not None:
            for row in reader:
                country = row["country"]
                tech = row["technology"]
                data_dict[country] = {}
                month_value = {}
                if country != "Default":
                    for month in fieldnames[2:]:
                        month_value[month] = float(row[month])

                data_dict[country][tech] = month_value

    # if a country does not have a technology, use the default value
    for country in data_dict:
        for tech in default_data:
            if tech not in data_dict[country]:
                data_dict[country][tech] = default_data[tech]

    # if a country is values of Map_node_country, but not in data_dict, use the default value
    for node in Map_node_country:
        country = Map_node_country[node]
        if country not in data_dict:
            data_dict[country] = default_data

    map_t_month = timemapping_creator("t", "month")
    for plant in Plant_list:
        if plant in Plant_RES_CH_list:

            try:
                # First try with original plant name
                _ = Avail_plant_RES_year_scenario[(plant, t)]
                plant2 = plant

            except KeyError:
                # Try replacing "01" with "00" in the plant name
                plant_alt = plant.replace("01", "00", 1)
                try:
                    _ = Avail_plant_RES_year_scenario[(plant_alt, t)]
                    plant2 = plant_alt
                except KeyError:
                    raise KeyError(f"Neither {plant} nor {plant_alt} found for t={t}")

            for t in T_list:
                Avail_plant[plant, t] = Avail_plant_RES_year_scenario[plant2, t]
        else:
            node = Map_plant_node[plant]
            if node== "na": # NOTE: this is a temporary fix, we need to find a better way to handle this
                node = "CH00"
            country = Map_node_country[node]
            tech = Map_plant_tech[plant]
            for t in T_list:
                # if a new technology does not exist in the source availability file, assume the technology is always available
                # if data_dict[country][tech] exists, then Avail_plant[plant, t] = data_dict[country][tech][map_t_month[t]] else, it is 1
                if country in data_dict and tech in data_dict[country]:
                    Avail_plant[plant, t] = data_dict[country][tech][map_t_month[t]]
                else:
                    Avail_plant[plant, t] = 1

    return Avail_plant


def read_plant_energy_limited_data(
    eu_policy,
    ch_policy,
    Plant_list_TYNDP,
    Plant_investment_non_RES_CH_list,
    Plant_investment_RES_CH_data,
    Map_plant_tech,
    Map_plant_node,
    tech_limited_energy_list,
    tech_limited_energy_CH_list,
    weather_year,
    run_year,
    T_list,
    PlantDH_investment_STES_list,
    # limit_fuel_import_CH,
):
    generation_annual = {}  # defined over plants (annual generation in MWh)

    time_scaling = (
        len(T_list) / 8760
    )  # scaling factor to convert annual generation to generation per the simulation period (linearly scaled). 1 if the simulation period is 8760 hours, 0.5 if it is 4380 hours, etc.

    # Use TYNDP 2022 data format for energy limited plants
    gen_df_EU = pd.read_csv("input/generation.csv", sep=",", header=0)
    gen_df_CH = pd.read_csv("input/generation_CH.csv", sep=",", header=0)
    cap_df_CH = pd.read_csv(
        "input/nonhydro_capacities_gen_CH.csv", sep=",", header=0
    )

    # calculate weights_gen_to_regions_ch, some weighting to assign aggregated CH00 generations to sub regions. --------------------------------
    # in weights_gen_to_regions_ch, for each technology, the sum of the weights is 1.
    # the weighting is calculated based on intalled capacity
    # only applies to CH (as several nodes exist in CH market region)
    weights_gen_to_regions_ch = {}  

    for tech in tech_limited_energy_CH_list: 
        # select the subset of the capacity data for the given technology
        plant_tech_data = cap_df_CH.loc[
            (cap_df_CH["scenario"] == ch_policy)
            & (cap_df_CH["name"].str.contains(tech)),
            ["name", str(run_year)],
        ].set_index("name")

        # total generation capacity for the given technology
        sum_ch_gen_cap = plant_tech_data.loc[:, str(run_year)].sum()

        weights_gen_to_regions_ch.update(
            {
                plant: plant_tech_data.loc[plant, str(run_year)] / sum_ch_gen_cap
                for plant in plant_tech_data.index
            }
        )

    # assign generation values to the plants --------------------------------------
    for p in Plant_list_TYNDP:
        if Map_plant_tech[p] in tech_limited_energy_list:
            if not Map_plant_node[p].startswith("CH0"):
                if p not in Plant_investment_non_RES_CH_list:  
                    if p not in PlantDH_investment_STES_list:      
                        generation_annual[p] = time_scaling * (
                            gen_df_EU.loc[
                                (gen_df_EU["scenario"] == eu_policy)
                                & (gen_df_EU["zone"] == Map_plant_node[p])
                                & (gen_df_EU["tech"] == Map_plant_tech[p])
                                & (gen_df_EU["weather_year"] == weather_year),
                                str(run_year),
                            ].item()  # type: ignore
                            * 1000
                )
                # generation values in EU are in GWh, we needed to convert them to MWh
            else:
                #CH plants
                if p not in Plant_investment_non_RES_CH_list:
                    if Map_plant_tech[p] in tech_limited_energy_CH_list:
                        generation_annual[p] = (
                            time_scaling
                            * weights_gen_to_regions_ch[p]
                            * gen_df_CH.loc[
                                (gen_df_CH["scenario"] == ch_policy)
                                & (gen_df_CH["zone"] == "CH00")
                                & (gen_df_CH["tech"] == Map_plant_tech[p])
                                & (gen_df_CH["weather_year"] == "all"),
                                str(run_year),
                            ].item() # type: ignore
                    )

    return generation_annual


def read_electrolyzer_data(
    eu_policy, ch_policy, run_year, Node_list, T_list, weather_year, electrolyzer_demand_reduction
):
    """
    Reads the electrolyzer data from the file input/electrolyzer.csv.
    Input:
        eu_policy: string, name of the EU policy scenario
        ch_policy: string, name of the CH policy scenario
        run_year: integer, year of the run
        Node_list: list of nodes
    Output:
        electrolyzer_capacities: dictionary with the values in the index as keys and the values in the column "value" as values
            e.g., {('AT00_electrolyzer', 't_1'): 1200.0, ('AT00_electrolyzer', 't_2'): 1200.0, ...
    """
    full_load_hour_target = 3000

    Plant_list = []
    Map_plant_tech = {}
    Map_plant_node = {}
    Data_plant_flex_d_within_window_electrolyzer = {}

    plant_list_data = pd.read_csv(
        "input/plants_electrolyzer.csv", sep=",", header=0
    )
    # remove row with market CH00 (CH data is in a separate file)
    plant_list_data = plant_list_data[~plant_list_data["node"].str.contains("CH00")]
    # remove rows with market value that is not in Node_list
    plant_list_data = plant_list_data[plant_list_data["node"].isin(Node_list)]
    # add CH data -  "input/plants_electrolyzer_CH00.csv" to plant_list_data
    plant_list_data = pd.concat(
        [
            plant_list_data,
            pd.read_csv(
                "input/plants_electrolyzer_CH00.csv", sep=",", header=0
            ),
        ],
        ignore_index=True,
    )

    # Plant_list is equalt to all unique values in the column "index" of plant_list_data, if the column node is in Node_list
    Plant_list = (
        plant_list_data.loc[plant_list_data["node"].isin(Node_list), "index"]
        .unique()
        .tolist()
    )

    # Map_plant_tech is equal to all unique values in the column "tech" of plant_list_data, if the column index is in Plant_list
    Map_plant_tech = dict(zip(plant_list_data["index"], plant_list_data["tech"]))

    # Map_plant_node is equal to all unique values in the column "node" of plant_list_data, if the column index is in Plant_list
    Map_plant_node = dict(zip(plant_list_data["index"], plant_list_data["node"]))

    # read data for electrolyzer capacities -------------------------------------
    # read electrolyzer demand data, EU
    electrolyzer_demand_data = pd.read_csv(
        "input/electrolyzer_net_demand.csv", sep=",", header=0
    )
    # read electrolyzer demand data, CH
    electrolyzer_demand_data_CH = pd.read_csv(
        "input/electrolyzer_net_demand_CH.csv", sep=",", header=0
    )
    # concattenate the two dataframes
    electrolyzer_demand_data = pd.concat(
        [electrolyzer_demand_data, electrolyzer_demand_data_CH], ignore_index=True
    )

    for plant in Plant_list:
        Data_plant_flex_d_within_window_electrolyzer[plant] = {}

        if Map_plant_node[plant] == "CH00":
            scenario_policy = ch_policy
            electrolyzer_demand_annual = electrolyzer_demand_data.loc[
                (electrolyzer_demand_data["plant_name"] == plant)
                & (electrolyzer_demand_data["scenario"] == scenario_policy)
                & (electrolyzer_demand_data["weather_year"] == "all"),
                str(run_year),
            ].item()  # type: ignore
        else:
            scenario_policy = eu_policy
            electrolyzer_demand_annual = electrolyzer_demand_data.loc[
                (electrolyzer_demand_data["plant_name"] == plant)
                & (electrolyzer_demand_data["scenario"] == scenario_policy)
                & (electrolyzer_demand_data["weather_year"] == weather_year),
                str(run_year),
            ].item() * electrolyzer_demand_reduction  # type: ignore

        Data_plant_flex_d_within_window_electrolyzer[plant]["energy"] = [
            electrolyzer_demand_annual * (len(T_list) / 8760)
        ]

        Data_plant_flex_d_within_window_electrolyzer[plant]["max_demand"] = (
            electrolyzer_demand_annual / full_load_hour_target
        )

        Data_plant_flex_d_within_window_electrolyzer[plant]["time_horizon"] = [
            [int(T_list[0][2:]), int(T_list[-1][2:])]
        ]

    return (
        Plant_list,
        Map_plant_tech,
        Map_plant_node,
        Data_plant_flex_d_within_window_electrolyzer,
    )

def read_EV_weekly_energy_consumption_data(run_year, share_of_flexibly_charging_EV, V2G_share_of_flexibly_charging_EV):
    """
    Read the weekly energy consumption data of electric vehicles from the file input/demand/EV_demand_weekly_XXXX.csv with XXXX representing the year.
    
    The input file contains 100% of total EV consumption. This function scales it to get the
    consumption for flexibly charging EVs that do NOT participate in V2G (i.e., EV_CH plant).
    
    Scaling: Total EV * share_of_flexibly_charging_EV * (1 - V2G_share_of_flexibly_charging_EV)
    
    Input:
        run_year: int, the year which the model runs for (e.g. 2035, 2050)
        share_of_flexibly_charging_EV: float, share of total EVs that charge flexibly (0-1)
        V2G_share_of_flexibly_charging_EV: float, share of flexibly charging EVs that do V2G (0-1)
    Output:
        EV_weekly_energy_consumption: dictionary with the index of the week in "week" and the energy consumption in MWh
    """

    # import the energy consumption data of all EVs (100%)
    path = f"input/demand/EV_demand_weekly_{run_year}.csv"
    EV_weekly_energy_consumption = pd.read_csv(path, index_col="week")
    
    # Scale to get only flexibly charging EVs that do NOT participate in V2G
    # These are the EVs represented by the EV_CH plant (ev_flex technology)
    EV_weekly_energy_consumption *= share_of_flexibly_charging_EV * (1 - V2G_share_of_flexibly_charging_EV)

    # convert the pd.DataFrame to a dictionary, use the index as keys and the values in the column as values
    EV_weekly_energy_consumption = EV_weekly_energy_consumption.to_dict()['energy_consumption_[MWh]']

    return EV_weekly_energy_consumption

def read_EV_and_V2G_charging_power_rate(run_year, rep_plant_name, share_of_flexibly_charging_EV, V2G_share_of_flexibly_charging_EV, share_of_available_charging_capacity_for_V2G):
    """
    Read the charging power rate of electric vehicles from the file input/demand/EV_chargingpowerrate_XXXX.csv.
    
    The input file contains charging power rate for 100% of all EVs. This function scales it to get:
    - EV_charging_power_rate: for flexibly charging EVs that do NOT participate in V2G (EV_CH plant)
    - V2G_charge_power_rate: for flexibly charging EVs that DO participate in V2G (V2G_CH plant)
    
    Input:
        run_year: int, the year which the model runs for (e.g. 2035, 2050)
        rep_plant_name: string, the name of the representative V2G plant
        share_of_flexibly_charging_EV: float, share of total EVs that charge flexibly (0-1)
        V2G_share_of_flexibly_charging_EV: float, share of flexibly charging EVs that do V2G (0-1)
        share_of_available_charging_capacity_for_V2G: float, fraction of V2G charging capacity actually available
    Output:
        EV_charging_power_rate: dictionary for EV_CH plant (non-V2G flexible EVs)
        V2G_charge_power_rate_dict: dictionary for V2G_CH plant
    """

    # import the charging power rate for all EVs (100%)
    path = f"input/demand/EV_chargingpowerrate_{run_year}.csv"
    EV_charging_power_rate_raw = pd.read_csv(path, index_col='t')
    
    # Scale for flexibly charging EVs that do NOT participate in V2G (EV_CH plant)
    EV_charging_power_rate = EV_charging_power_rate_raw * share_of_flexibly_charging_EV * (1 - V2G_share_of_flexibly_charging_EV)
    
    # Scale for flexibly charging EVs that DO participate in V2G (V2G_CH plant)
    # Also apply share_of_available_charging_capacity_for_V2G (e.g., 70% to take it easy on the battery)
    V2G_charge_power_rate = EV_charging_power_rate_raw * share_of_flexibly_charging_EV * V2G_share_of_flexibly_charging_EV * share_of_available_charging_capacity_for_V2G

    # convert the pd.DataFrame to a dictionary
    EV_charging_power_rate = EV_charging_power_rate.to_dict()['charging_power_rate_[MWh]']

    # convert the pd.DataFrame to a dictionary with plant name as key
    V2G_charge_power_rate_dict = {}
    for ind in V2G_charge_power_rate.index:
        V2G_charge_power_rate_dict[rep_plant_name, ind] = V2G_charge_power_rate.loc[ind].values[0]

    return EV_charging_power_rate, V2G_charge_power_rate_dict

def read_V2G_data_outflow(run_year, rep_plant_name, share_of_flexibly_charging_EV, V2G_share_of_flexibly_charging_EV):
    """
    Reads the outflow (consumption/discharging pattern) of the representative V2G fleet from a file.
    
    The input file V2G_consumption_XXXX.csv contains the hourly consumption pattern scaled to 100% of
    total EV consumption. This function scales it to get only the V2G portion.
    
    Scaling: Total EV * share_of_flexibly_charging_EV * V2G_share_of_flexibly_charging_EV
    
    Input:
        run_year: int, the year which the model runs for (e.g. 2035, 2050)
        rep_plant_name: string, the name of the representative plant for the V2G fleet
        share_of_flexibly_charging_EV: float, share of total EVs that charge flexibly (0-1)
        V2G_share_of_flexibly_charging_EV: float, share of flexibly charging EVs that do V2G (0-1)
    Output:
        V2G_outflow_dict: dictionary {(plant_name, t): outflow_MWh}
    """

    path = f"input/demand/V2G_consumption_{run_year}.csv"
    V2G_outflow_df = pd.read_csv(path, index_col='t')
    
    # Scale from 100% EV to only the V2G portion of flexibly charging EVs
    V2G_outflow_df *= share_of_flexibly_charging_EV * V2G_share_of_flexibly_charging_EV

    # convert the pd.DataFrame to a dictionary with (plant_name, t) as keys
    V2G_outflow_dict = {}
    for ind in V2G_outflow_df.index:
        V2G_outflow_dict[rep_plant_name, ind] = V2G_outflow_df.loc[ind].values[0]

    return V2G_outflow_dict

def read_V2G_storage_capacity(run_year, CH_policy, rep_plant_name, share_of_flexibly_charging_EV, V2G_share_of_flexibly_charging_EV):
    """
    Reads the battery capacity of the representative V2G fleet from a file (input/fuel_limits.csv).
    
    The input file contains total EV battery storage capacity (100% of all EVs).
    This function scales it to get only the V2G-participating portion.
    
    Scaling: Total storage * share_of_flexibly_charging_EV * V2G_share_of_flexibly_charging_EV
    
    Input:
        run_year: int, the year which the model runs for (e.g. 2035, 2050)
        CH_policy: string, the Swiss policy scenario
        rep_plant_name: string, the name of the representative V2G plant
        share_of_flexibly_charging_EV: float, share of total EVs that charge flexibly (0-1)
        V2G_share_of_flexibly_charging_EV: float, share of flexibly charging EVs that do V2G (0-1)
    Output:
        V2G_storage_capacity_dict: dictionary {plant_name: storage_capacity_MWh}
    """
    path = f"input/fuel_limits.csv"
    V2G_storage_capacity_df = pd.read_csv(path, comment='#')

    # Get total EV storage capacity from the file
    total_V2G_storage_capacity = V2G_storage_capacity_df[
        (V2G_storage_capacity_df['fuel'] == 'V2G') & 
        (V2G_storage_capacity_df['limit_type'] == 'storage_capacity') & 
        (V2G_storage_capacity_df['scenario'] == CH_policy)
    ][str(run_year)].item()
    
    # Scale to get only the V2G-participating portion
    V2G_storage_capacity = total_V2G_storage_capacity * share_of_flexibly_charging_EV * V2G_share_of_flexibly_charging_EV
    
    V2G_storage_capacity_dict = {rep_plant_name: V2G_storage_capacity}
    return V2G_storage_capacity_dict


def read_EV_inflexible_demand_data(run_year, share_of_flexibly_charging_EV, node="CH00"):
    """
    Read the inflexible EV demand timeseries from EV_demand_hourly_*.csv.
    
    The inflexible EV demand represents the portion of total EV consumption that charges 
    according to a fixed profile (e.g., uncontrolled charging as soon as plugged in).
    
    The input file EV_demand_hourly_*.csv contains 100% of total EV consumption.
    This function scales it by (1 - share_of_flexibly_charging_EV) to get the inflexible portion.
    
    Input:
        run_year: int, the year which the model runs for (e.g. 2035, 2050)
        share_of_flexibly_charging_EV: float, the share of EVs that charge flexibly (between 0 and 1)
            The remaining (1 - share_of_flexibly_charging_EV) are inflexible
        node: str, the node for which to compute EV inflexible demand (default: "CH00")
    
    Output:
        EV_inflexible_demand_data: dictionary with keys (node, t) and values are the inflexible EV demand in MWh
            e.g., {('CH00', 't_1'): 15.5, ('CH00', 't_2'): 18.2, ...}
    """
    # Read the total EV consumption profile (100% of all EVs)
    path = f"input/demand/EV_demand_hourly_{run_year}.csv"
    EV_total_demand_df = pd.read_csv(path, index_col='t')
    
    # Scale to get only the inflexible portion
    EV_inflexible_demand_df = EV_total_demand_df * (1 - share_of_flexibly_charging_EV)
    
    # Convert to dictionary with (node, t) keys
    EV_inflexible_demand_dict = {}
    for t in EV_inflexible_demand_df.index:
        # Ensure t is in the correct format (t_1, t_2, etc.)
        t_str = t if isinstance(t, str) and t.startswith('t_') else f"t_{t}"
        EV_inflexible_demand_dict[(node, t_str)] = EV_inflexible_demand_df.loc[t].values[0]
    
    return EV_inflexible_demand_dict


def read_building_archetypes(run_year, weather_year, flexible_household_heatpump_share, heat_flexibility_Kelvin, heating_system):
    """
    This function imports the categorized profiles from the given path

    Parameters
    ----------
    run_year : int
        the year which the model runs for
    weather_year : int
        the year of the weather data
    flexible_household_heatpump_share : float
        the share of households with a flexible heat pump
    heat_flexibility_Kelvin: float
        the flexibility of the heating system in Kelvin
        E.g. if it is 1, the buildings can be heated 1 degree Kelvin up and down i.e. 2 Kelvin in total
    heating_system : string
        the heating system that should be imported
        possible options: 'DH', 'Fossil', 'HP', 'Other HS'

    Returns
    -------
    BA_el_con: dictionary with hourly values of the electrical demand of the building archetypes
    BA_th_con: dictionary with hourly values of the thermal demand of the building archetypes
    BA_th_lim: dictionary with the thermal limits of the building archetypes
    COP: dictionary with the hourly coefficient of performances of the building archetypes
    BA_names: list of the names of the building archetypes
    """

    name = f"categorized_profiles_{run_year}_{weather_year}.csv"

    # read the data from the given path
    data = pd.read_csv('input/demand/' + name)

    # filter the data for the given heating system
    #data = data[data['heating_system_group'].astype(str).str.contains("heating_system", na=False)]
    for idx, row in enumerate(data['heating_system_group']):
        if heating_system not in row:
            data = data.drop(idx)

    # filter the data for the given TS_Type
    BA_th_con = data[data['TS_Type'] == 'heating demand kWh'].copy()
    BA_el_con = data[data['TS_Type'] == 'electricity demand kWh'].copy()

    # Extract the BA_names
    BA_names = list((BA_el_con['age_construction_group'] + '_' + BA_el_con['climate_zone_group'] + '_[MWh]' ))
    BA_names = [name.replace("ü", "ue") for name in BA_names] # make sure there is no Umlaute (because of Alpensüdseite)

    # Create a new column with the desired name format
    BA_el_con['BA_names'] = BA_names
    BA_th_con['BA_names'] = BA_names

    # Extracting the thermal limits
    BA_th_lim = BA_el_con[['negative_capacity [MJ]','positive_capacity [MJ]']]
    BA_th_lim = BA_th_lim * flexible_household_heatpump_share * heat_flexibility_Kelvin
    BA_th_lim.index = BA_names
    BA_th_lim = BA_th_lim.transpose()
    BA_th_lim = BA_th_lim / 3600 # Convert from MJ to MWh
    BA_th_lim.index = ['negative_capacity_[MWh]', 'positive_capacity_[MWh]'] # Fix the index names after the conversion to a new unit

    # Extract the power of the HP
    BA_max_heating_capacity = BA_el_con['power_of_HP [kW]']
    BA_max_heating_capacity = BA_max_heating_capacity / 1000 # Convert from kW to MW
    BA_max_heating_capacity.name = 'power_of_HP_[MW]'
    BA_max_heating_capacity.index = BA_names # type: ignore

    # Drop unnecessary columns
    BA_el_con = BA_el_con.drop(columns=['heating_system_group', 'TS_Type', 'age_construction_group', 'climate_zone_group', 'negative_capacity [MJ]','positive_capacity [MJ]', 'power_of_HP [kW]'])
    BA_th_con = BA_th_con.drop(columns=['heating_system_group', 'TS_Type', 'age_construction_group', 'climate_zone_group', 'negative_capacity [MJ]','positive_capacity [MJ]', 'power_of_HP [kW]'])

    # Transpose the dataframe for the transformation to a dict later
    BA_el_con = BA_el_con.set_index('BA_names').transpose()
    BA_th_con = BA_th_con.set_index('BA_names').transpose()

    # Rename the index to follow the "t_1", "t_2", ... format
    BA_el_con.index = [f"t_{i+1}" for i in range(len(BA_el_con.index))] # type: ignore
    BA_el_con.index.name = 'timestep' # type: ignore
    BA_th_con.index = [f"t_{i+1}" for i in range(len(BA_th_con.index))] # type: ignore
    BA_th_con.index.name = 'timestep' # type: ignore

    # Convert from kWh to MWh
    BA_el_con = BA_el_con / 1000
    BA_th_con = BA_th_con / 1000

    # Determine the coefficients of performance (COP) for the different building archetypes
    COP = BA_th_con / BA_el_con

    # As both BA_th_con and BA_el_con can contain zeros, missing values and nans in COP are replaced by zeros
    COP = COP.fillna(0).replace([float('inf'), -float('inf')], 0)

    # Consider the share of households with a flexible heat pump
    #BA_el_con *= flexible_household_heatpump_share # In theory, this must be adjusted too, but as it is only required later in the code in its not-adjusted version, it is skipped here.
    BA_th_con *= flexible_household_heatpump_share
    BA_max_heating_capacity *= flexible_household_heatpump_share

    # convert the pd.DataFrame to a dictionary, use the timestamp as keys
    COP = COP.to_dict()
    #BA_el_con = BA_el_con.to_dict()
    # Required to be subtracted from the input data. Therefore, it is kept a DataFrame
    BA_th_con = BA_th_con.to_dict()
    BA_th_lim = BA_th_lim.to_dict()
    BA_max_heating_capacity = BA_max_heating_capacity.to_dict()

    return BA_el_con, BA_th_con, BA_th_lim, COP, BA_names, BA_max_heating_capacity


def read_HP_inflexible_demand_data(BA_el_con_df, flexible_household_heatpump_share, node="CH00"):
    """
    Calculate the inflexible household heat pump demand timeseries.
    
    The inflexible HP demand represents the portion of household heat pump consumption that operates
    according to a fixed profile (i.e., not participating in flexibility/demand response).
    
    The input BA_el_con_df contains 100% of household heat pump electricity consumption.
    This function scales it by (1 - flexible_household_heatpump_share) to get the inflexible portion.
    
    Input:
        BA_el_con_df: pandas DataFrame with hourly values of the electrical demand of the building archetypes [MWh]
                      Index: timestep (t_1, t_2, ...), Columns: building archetype names
        flexible_household_heatpump_share: float, the share of households with flexible heat pumps (between 0 and 1)
            The remaining (1 - flexible_household_heatpump_share) are inflexible
        node: str, the node for which to compute HP inflexible demand (default: "CH00")
    
    Output:
        HP_inflexible_demand_dict: dictionary with keys (node, t) and values are the inflexible HP demand in MWh
            e.g., {('CH00', 't_1'): 25.5, ('CH00', 't_2'): 28.2, ...}
    """
    # Calculate the inflexible portion by summing across all building archetypes and scaling
    # BA_el_con_df has timesteps as index and building archetype names as columns
    HP_total_demand = BA_el_con_df.sum(axis=1)  # Sum across all building archetypes for each timestep
    
    # Scale to get only the inflexible portion
    HP_inflexible_demand = HP_total_demand * (1 - flexible_household_heatpump_share)
    
    # Convert to dictionary with (node, t) keys
    HP_inflexible_demand_dict = {}
    for t in HP_inflexible_demand.index:
        # Ensure t is in the correct format (t_1, t_2, etc.)
        t_str = t if isinstance(t, str) and t.startswith('t_') else f"t_{t}"
        HP_inflexible_demand_dict[(node, t_str)] = HP_inflexible_demand.loc[t]
    
    return HP_inflexible_demand_dict

def read_KVA_infeed_data():
    """
    Reads the KVA infeed data from the file input/KVAinfeed.csv.
    Output: A dictionary mapping region names (str) to their KVA infeed values (float).
    Example: {'ILHT_Alpen': 47.4380137, 'ILHT_Alpensuedenseite': 7.683561644, ...}
    """

    KVA_infeed = {}

    # read the data from the file input/KVAinfeed.csv
    with open(os.path.join("input", "KVAinfeed.csv"), newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            region, value = row
            KVA_infeed[region] = float(value)

    return KVA_infeed