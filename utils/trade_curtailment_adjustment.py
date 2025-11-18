import pandas as pd
import os
import numpy as np

def trade_curtailment_adjustment(name):

    current_dir = os.path.dirname(__file__)
    # Go one level up (to Future_Markets), then into 'output'
    output_dir = os.path.join(current_dir, '..', 'output/aggregated')

    # Import files
    net_export = pd.read_csv(f'{output_dir}/{name}/Export_net_CH.csv', index_col=0)
    prices = pd.read_csv(f'{output_dir}/{name}/prices_hourly.csv', index_col=1)
    prices = prices.loc['CH00']
    prices.reset_index(drop=True, inplace=True)
    prices = prices.drop(columns=["Unnamed: 0"])
    prices.set_index("hour", inplace=True)
    curtailment = pd.read_csv(f'{output_dir}/{name}/curtailment.csv', index_col=[0,1])

    # Turn files into dictionaries
    net_export_dict = net_export.to_dict()
    prices_dict = prices.to_dict()

    print("Start algorithm to adjust curtailment.")
    # iterate through all the hours
    for t in prices.index:
        
        # iterate through all the scenarios
        for s in prices.columns:
                
            # if the price is non-zero, the curtailment is assumed to be zero
            if prices_dict[s][t] > 0.01:
                #curtailment[(t,s)] = 0
                curtailment[s][('CH00_fixedconsumer', t)] = 0
            else:
                # Add the curtailment that the model determined (which could also be shifter curtailment from neighboring countries) and add net exports
                curtailment[s][('CH00_fixedconsumer', t)] = max(0, net_export_dict[s][t] + curtailment[s][('CH00_fixedconsumer', t)])

    print("Finished algorithm to adjust curtailment.")
    
    # Save the adjusted curtailment
    curtailment.to_csv(f'{output_dir}/{name}/curtailment.csv')
    curtailment.to_csv(f'{output_dir}/{name}/curtailment_hour_sum_temporal.csv')

    # Adjust the values for the year
    curtailment_year = curtailment.loc['CH00_fixedconsumer'].sum(axis=0)

    curtailment_year_sum_temporal = pd.read_csv(f'{output_dir}/{name}/curtailment_year_sum_temporal.csv', index_col=[0,1])
    curtailment_year_sum_temporal.loc[('CH00_fixedconsumer', 'year_1')] = curtailment_year
    curtailment_year_sum_temporal.to_csv(f'{output_dir}/{name}/curtailment_year_sum_temporal.csv')

    Annual_balance_ch = pd.read_csv(f'{output_dir}/{name}/Annual_balance_ch.csv', index_col=[0,1])
    Annual_balance_ch.loc[('demand', 'curtailment')] = curtailment_year
    Annual_balance_ch.to_csv(f'{output_dir}/{name}/Annual_balance_ch.csv')

    Annual_balance_ch_hourly = pd.read_csv(f'{output_dir}/{name}/Annual_balance_ch_hourly.csv', index_col=[0,1,2])
    
    for s in prices.columns:
        Annual_balance_ch_hourly.loc[(s, 'demand', 'curtailment')] = curtailment[s].loc['CH00_fixedconsumer']

    Annual_balance_ch_hourly.to_csv(f'{output_dir}/{name}/Annual_balance_ch_hourly.csv')

# name = '20250312_aggregation_sensitivity_analysis'
# trade_curtailment_adjustment(name)