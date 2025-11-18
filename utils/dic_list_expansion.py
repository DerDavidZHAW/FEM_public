from typing import Dict, Any

def update_dict_with_add_dim(dictionary_org, dictionary_with_added_dim, dimension_name):
    """
    This function adds a dimension to the keys of a dictionary.
    Input:
        dictionary_org: original dictionary (with key e.g., ('CH00_fixedconsumer', 'pvrf', 't_6672'))
        dictionary_with_added_dim: dictionary to be updated
        dimension_name: name of the dimension to be added
    Output:
        Updated dictionary_with_added_dim with key e.g., ('CH00_fixedconsumer', 'pvrf', 't_6672', sub_scenario)
    """

    for key, value in dictionary_org.items():
        if type(key) == str:
            key = (key,)
        # Create the new key by adding the sub_scenario to the original key
        new_key = (*key, dimension_name)
        # Add the new key-value pair to the Infeed_RES_TYNDP dictionary
        dictionary_with_added_dim[new_key] = value

def extend_list_with_new_elements(list_new, list_extended):
    for element in list_new:
        if element not in list_extended:
            list_extended.append(element)


def merge_dictionaries_in_place(original_dict: Dict[str, Dict[str, Any]], new_dict: Dict[str, Dict[str, Any]]) -> None:

    """
    This function merges two dictionaries and returns a new dictionary.
    Input:
        original_dict: original dictionary
        new_dict: dictionary to be merged with the original dictionary
    Output:
        original_dict that is updated in place merging content of the original and new dictionaries

    Example:
    original_dict = {
        'gen_max_limit': {'CH01_pvrf': 10000, 'CH01_windon': 600},
        'energy_max_limit': {'CH01_pvrf': 10000, 'CH01_windon': 600}
        }

    new_dict = {
        'gen_max_limit': {'DH01_InvSTES': 10},
        'energy_max_limit': {'DH01_InvSTES': 100}
        }

    # in place created dictionary    
    original_dict = {
        'gen_max_limit': {'CH01_pvrf': 10000, 'CH01_windon': 600, 'DH01_InvSTES': 10}, 
        'energy_max_limit': {'CH01_pvrf': 10000, 'CH01_windon': 600, 'energy_max_limit': 'DH01_InvSTES': 100}
        }

    """
    for key, new_values in new_dict.items():
        if key in original_dict:
            original_dict[key].update(new_values)
        else:
            original_dict[key] = new_values