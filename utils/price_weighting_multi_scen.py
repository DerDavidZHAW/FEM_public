
import pandas as pd

def price_weighting_multi_scen(price_hourly, output_dir):
    """
    Adjust the price for the scenarios that have a weight in the objective function.
    The price that was originally exported (automatically) have an issue: 
        given that the objective function is a weighted sum of the scenarios, 
        effect of the energy balance constraint is also weighted. 
        Therefore, the price should be adjusted to reflect the actual price of the energy balance constraint.
    The price is adjusted by dividing the price by the weight of the scenario in the objective function.
    The weight of the shock scenario in the objective function is read from the settings.csv file.
    The weight of the full NTC scenario in the objective function is calculated as 1 - weight of the shock scenario.
    :param price_hourly: hourly price data for all scenarios
    :param output_dir: path to the output directory
    :return: None
    """
    # read the settings.csv
    settings = pd.read_csv(output_dir + "settings.csv", index_col=0, header=0)

    # extract the sub_secn_name row
    subscen_names = list(settings.loc["sub_secn_name", :])
    
    # replace the column names in the settings
    settings.columns = subscen_names

    # NOTE: for whatever reason, settings.csv only have values for the shock scenarios, not the full NTC scenarios
    # Therefore, the price for the full NTC scenarios should be adjusted differently

    for subscen in price_hourly.columns.to_list():
        try:
            # to get the scenario name, and remove the last part after last "_"
            # overhead_scen = subscen.rsplit("_", 1)[0]
            weight_shock = settings.loc["weight_in_objective_fcn", subscen]
            weight_shock = float(weight_shock) # type: ignore


            if subscen in settings.loc["sub_secn_name", :].values:
                weight = weight_shock
                print(f"Scenario {subscen} has a weight of {weight} in the objective function, price adjusted")
            # else:
            #     weight = 1 - weight_shock
            #     print(f"Scenario {subscen} has a weight of {weight} in the objective function, price adjusted")
            
            price_hourly[subscen] = price_hourly[subscen] * (1/weight)      
        except:
            print(f"Scenario {subscen} not found in settings.csv, price not adjusted")

    return price_hourly
