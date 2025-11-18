import csv


def dict_3dim_to_csv(dict_to_export, exported_file_name):
    """
    export dictionary dict_to_export to a csv file
    """
    # # Sample 3-dimensional dictionary
    # demand_data = {
    #     ("ID250", "fixed", "t_6553"): 0.0003977736,
    #     ("ID250", "fixed", "t_6554"): 0.0001891081,
    #     ("ID250", "fixed", "t_6555"): 7.76742e-05,
    #     ("ID250", "fixed", "t_6556"): 0.0001516605
    #     # Add more data here...
    # }

    # CSV file path
    csv_file_path = exported_file_name + ".csv"

    # Writing data to CSV file
    with open(csv_file_path, "w", newline="") as csv_file:
        csv_writer = csv.writer(csv_file)
        # Writing header
        csv_writer.writerow(["ID", "Category", "T", "Value"])
        # Writing flattened data
        for key, value in dict_to_export.items():
            csv_writer.writerow([key[0], key[1], key[2], value])

    print("CSV file created:", csv_file_path)
