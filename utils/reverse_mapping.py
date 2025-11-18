import pandas as pd

def reverse_mapping(df):
    """
    Reverse a dataframe Map_X_Y to create a dataframe mapping Ys to a X value.
    e.g., Map_node_plant (read from Map_node_plant.csv) (has node as the first element of the row and all plants ...
    ...of the node in the rest of the row) to create a dataframe plants and nodes:
    # print(Map_rev_df.head())
    Map_rev_df
                Node
    item_asset          
    ev_ID67         CH00


    """
    Map_rev_dict = {}
    for key, values in df.iterrows():
        for value in values:
            Map_rev_dict[value] = key
    # save the dictionary Map_rev_df as Series and name the index as item_asset
    Map_rev_df = pd.DataFrame(list(Map_rev_dict.items()), columns=[
                              "item_asset", "Node"])
    Map_rev_df.set_index("item_asset", inplace=True)

    return Map_rev_df
