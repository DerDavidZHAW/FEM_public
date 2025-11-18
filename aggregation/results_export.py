import pandas as pd
from pathlib import Path


def par_var(var_list, scenario_name):
    for variable in var_list:
        # extract data
        extracted_info = variable.extract_values()

        # build output path
        output_path = Path("output") / scenario_name / f"{variable.name}.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # if not empty, export file with data
        if extracted_info != {}:
            # convert to DataFrame
            result_values = pd.DataFrame(
                index=extracted_info.keys(), data=extracted_info.values()
            )

            if len(result_values.columns) > 0:
                result_values.columns = ["value"] + result_values.columns.tolist()[1:]
            else:
                # Handle case where DataFrame has no columns (scalar values or empty mappings)
                result_values = pd.DataFrame(
                    index=extracted_info.keys(), 
                    data={"value": list(extracted_info.values())}
                )
            # extract names of the domain sets
            if variable.index_set()._implicit_subsets is None:
                header_list = [
                    variable.index_set().name,
                ]
            else:
                header_list = [
                    variable.__dict__["_implicit_subsets"][domain_counter].name
                    for domain_counter in range(
                        len(variable.__dict__["_implicit_subsets"])
                    )
                ]

            # Convert DataFrame to include the set names as the first row
            result_values.index.names = header_list

            result_values.to_csv(output_path)

        # export empty file
        else:
            result_values = pd.DataFrame()
            result_values.to_csv(output_path)


def constraints(constraint_list, scenario_name, model, write_csv=True):
    print("Exporting duals...")
    result_duals_dict = {}
    for constraint in constraint_list:
        data = {}
        counter = 0
        try:
            for index in constraint:
                if constraint.dim() == 0:
                    data[counter] = [constraint.name] + [
                        model.dual[constraint[index]]
                    ]  # NOTE: there will be so may constraints for limited energy plants, because every duration has its own constraint
                elif constraint.dim() != 1:
                    data[counter] = [i for i in index] + [model.dual[constraint[index]]]
                else:
                    data[counter] = [index] + [model.dual[constraint[index]]]
                counter += 1

            result_duals = pd.DataFrame.from_dict(data, orient="index")

            if constraint._implicit_subsets is None:
                header_list = [
                    constraint.name,
                ]
            else:
                header_list = [
                    constraint.__dict__["_implicit_subsets"][domain_counter].name
                    for domain_counter in range(
                        len(constraint.__dict__["_implicit_subsets"])
                    )
                ]

            result_duals.columns = header_list + ["value"]

            if write_csv:
                output_path = Path("output") / scenario_name / f"{constraint.name}_dual.csv"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                result_duals.to_csv(output_path, index=False)

            result_duals_dict[constraint.name] = result_duals

        except Exception as e:
            print(f"Error in exporting duals for {constraint.name}: {e}")
    return result_duals_dict
