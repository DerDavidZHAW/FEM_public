import pandas as pd
from model.components_common import intersection



def map_gen_dem_timeseries(
    target_node,
    generation_all,
    demand_inflx_all,
    demand_flxbl_all,
    export_all,
    soc_all,
    Map_node_plant,
    Map_node_consumer,
    Map_node_exportinglineATC,
    Map_node_importinglineATC,
):
    (
        plant_list,
        demand_inflx_list,
        demand_flxbl_list,
        exportATC_list,
        importATC_list,
        plant_with_soc,
    ) = ([], [], [], [], [], [])

    if target_node == "all":
        plant_list = list(generation_all.index)
        demand_inflx_list = list(demand_inflx_all.index)
        demand_flxbl_list = list(demand_flxbl_all.index)
        exportATC_list = list(export_all.index)
        importATC_list = list(export_all.index)
        plant_with_soc = list(soc_all.index)
    else:
        plant_list = intersection(
            Map_node_plant[target_node], list(generation_all.index)
        )

        # demand_inflx_list is equal to intersection of Map_node_consumer[target_node] and first element of demand_inflx_all.index
        demand_inflx_list = intersection(
            Map_node_consumer[target_node], list(demand_inflx_all.index.get_level_values(0))
        )

        demand_flxbl_list = intersection(
            Map_node_plant[target_node], list(demand_flxbl_all.index)
        )
        exportATC_list = intersection(
            Map_node_exportinglineATC[target_node], list(export_all.index)
        )
        importATC_list = intersection(
            Map_node_importinglineATC[target_node], list(export_all.index)
        )
        plant_with_soc = intersection(plant_list, list(soc_all.index))
    return (
        plant_list,
        demand_inflx_list,
        demand_flxbl_list,
        exportATC_list,
        importATC_list,
        plant_with_soc,
    )
