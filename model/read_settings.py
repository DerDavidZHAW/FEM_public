from scenarios.settings_default import seetings_default_param
from scenarios.scenarios import scenarios_list


def read_scenario_settings(scenario_name):
    parameters = scenarios_list.get(scenario_name, {})

    # Use default parameters if a parameters as stored in seetings_default_param, if it  is missing in the scenarios_list
    scenario_params = {**seetings_default_param, **parameters}

    # add Consumer_list_netflex and T_list to scenario_pasrams
    t_start = scenario_params["t_start"]
    t_end = scenario_params["t_end"]

    consumer_start = scenario_params["consumer_start"]
    consumer_end = scenario_params["consumer_end"]

    Consumer_list_netflex = [
        "ID" + str(i) for i in range(consumer_start, consumer_end + 1)
    ]
    # to scenario_params, add a new key "Consumer_list_netflex" with value Consumer_list_netflex
    scenario_params["Consumer_list_netflex"] = Consumer_list_netflex

    if t_start > t_end:
        T_list = ["t_" + str(t) for t in range(t_start, 8760 + 1)] + [
            "t_" + str(t) for t in range(1, t_end + 1)
        ]  # time steps
    else:
        T_list = ["t_" + str(t) for t in range(t_start, t_end + 1)]  # time steps

    # to scenario_params, add a new key "T_list" with value T_list
    scenario_params["T_list"] = T_list

    return scenario_params
