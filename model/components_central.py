from pyomo.environ import Constraint, Set
from model.components_common import intersection
from data_prep.definitions_common import Plant_investment_RES_CH_list


def define_constraints_central(
    model,
    consumer_based_on_tariff,
    winter_limit,
    minimum_RES_target_CH
):
    # if consumers ARE based on tariff, their consumption is already planned, no need to model here.
    # if not consumer_based_on_tariff: #NOTE: this is always False in the current implementation
    # for s in model.Secnarios:
    for (p,s), data in model.Data_plant_flex_d_within_window.items():
        for i, time_range in enumerate(data["time_horizon"]):
            n = i + 1
            start, end = time_range
            if "t_" + str(start) in model.T and "t_" + str(end) in model.T:
                # NOTE: what happens in the line above if only one of the t_start and t_end is in model.T?
                # Initialize energy_limit with a default value
                energy_limit = data["energy"][i]
                if start < end:
                    range_T = list(range(start, end + 1))
                else:
                    # if the time window passes over the end of the year, we need to consider the range from start to 8760 and from 1 to end
                    # range_T is equal to sum of range(start, 8760) and range(1, end + 1)
                    range_T = list(range(start, 8760 + 1)) + list(range(1, end + 1))
                model.add_component(
                    f"consume_tot_limit_{p}_{n}_{s}",
                    Constraint(
                        expr=sum(
                            model.storage_charge[p, "t_" + str(t), s]
                            for t in range_T
                        )
                        == energy_limit
                    ),
                )
    for scen in model.Scenarios:
        if winter_limit[scen]["mode"]:
            # limit the sum of import to CH00 in the given time window winter_limit[scen]["window"] to the given value winter_limit[scen]["energy_MWh"]
            n="CH00"

            t_start = winter_limit[scen]["window"][0] 
            t_end = winter_limit[scen]["window"][1]
            if t_start > t_end:
                T_winter_list = ["t_" + str(t) for t in range(t_start, 8760 + 1)] + [
                    "t_" + str(t) for t in range(1, t_end + 1)
                ]  
            else:
                T_winter_list = ["t_" + str(t) for t in range(t_start, t_end + 1)]  

            model.T_winter = Set(within=model.T, initialize=T_winter_list) 

            export_as_starting_node = sum(
                model.Export[l, t, scen] for l in model.lineATC & model.Map_node_exportinglineATC[n] for t in model.T_winter
            )   
            # positive means import, negative means export
            import_as_ending_node = sum(
                model.Export[l, t, scen] for l in model.lineATC & model.Map_node_importinglineATC[n] for t in model.T_winter
            )

            model.Constraint_winter_limit = Constraint(
                expr=import_as_ending_node - export_as_starting_node <= winter_limit[scen]["energy_MWh"] 
            )

        if minimum_RES_target_CH[scen]:
            # limit infeed and generatino from pvrf and wind generation in CH00 to the given value minimum_RES_target_CH
            # sum value of infeeds for all nodes in CH, i.e., CH00, CH01, CH02, ..., CH07 and all techs, i.e., pvrf, windon, pv
            infeed_CH = sum(
                model.infeed[n, tech, t, scen] for n in model.Map_node_consumer["CH00"] for t in model.T for tech in model.Tech_infeed if tech != "ror"
            )
            
            # keep only the plants that are in market CH00
            plants_res_investable_ch = intersection(Plant_investment_RES_CH_list, model.Map_node_plant["CH00"])
            infeed_investment_res_CH = sum(
                model.gen_max[plant, scen]*model.avail_plant[plant,t, scen] for plant in plants_res_investable_ch for t in model.T
            )

            # create a constraint to ensure sume of infeed_CH and infeed_investment_res_CH is greater than or equal to minimum_RES_target_CH
            model.Constraint_investment_res_CH = Constraint(
                expr=infeed_CH + infeed_investment_res_CH >= minimum_RES_target_CH[scen]
            )
    return model