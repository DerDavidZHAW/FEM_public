import pandas as pd
import subprocess

# Custom function to replace "," with ";" if cell is a list or dictionary
def replace_comma_with_semicolon(x):
    if isinstance(x, (list, dict)):
        if isinstance(x, list):
            return str(x).replace(",", ";")
        # elif isinstance(x, dict):
        #     return ';'.join([f'{key}:{value}' for key, value in x.items()])
    else:
        return x

def get_current_branch():
    result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                            capture_output=True, text=True)
    return result.stdout.strip()
    
def settings_to_df_fcn(settings_dict) -> pd.DataFrame:
    settings_reordered = {}

    for item in settings_dict:
        if item not in ["T_list", "Consumer_list_netflex", "Node_list_setting"]:
            if item!= "winter_limit":
                settings_reordered[item] = settings_dict[item]
            else:
                settings_reordered["winter_limit"] = settings_dict[item]["mode"]
                settings_reordered["winter_limit_window"] = settings_dict[item]["window"]
                settings_reordered["energy_MWh"] = settings_dict[item]["energy_MWh"]

    settings_df = pd.DataFrame(list(settings_reordered.items()), columns=['Item', 'Value'])

    settings_df = settings_df.map(replace_comma_with_semicolon) # type: ignore

    # set column item as index
    settings_df.set_index('Item', inplace=True)

    # add branch name to the settings
    branch = get_current_branch()
    settings_df.loc["branch"] = branch

    return settings_df