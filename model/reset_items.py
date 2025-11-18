def get_lists_and_dicts(module, excluded_vars):
    """
    Get all lists and dictionaries in a module.
    Input:
        module: a module object
        excluded_vars: a list of variable names to exclude
    Output:
        list_of_lists: a list of list variable names
        list_of_dicts: a list of dictionary variable names
    """

    # Get all local variable names in the module
    variable_names = dir(module)

    # Create a list to store list and dictionary names
    list_of_lists = []
    list_of_dicts = []

    excluded_vars.extend(["__builtins__"])
    excluded_vars.extend(["__annotations__"])

    # Iterate over the variable names
    for var_name in variable_names:
        # Get the value of the variable
        var_value = getattr(module, var_name)
        # Check if the variable is in the excluded variables
        if var_name in excluded_vars:
            continue
        # Check if the variable is a list
        if isinstance(var_value, list):
            list_of_lists.append(var_name)
        # Check if the variable is a dictionary
        elif isinstance(var_value, dict):
            list_of_dicts.append(var_name)

    # Return the resulting lists and dictionaries
    return list_of_lists, list_of_dicts

