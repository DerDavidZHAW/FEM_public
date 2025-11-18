"""
Creates a plot that shows annual generation values per technology for different scenarios.
Output is a mesh plot with the x-axis representing the different probabilities and the y-axis representing the different NTC shock.
Each cube in the mesh plot represents the annual generatino sources for a specific probability and NTC shock.
The visuals are weak.
The plot is not fully tested (particularly with regard to storage technologies).
"""


import pandas as pd
import plotly.graph_objects as go

# Define the patterns to be used in the column names. For each pattern, a separate mesh plot will be created.
pattern_list = ["RTN_GASN", "RTN_GASY", "R45_GASN", "R45_GASY"]



# Step 1: Read the CSV file
df = pd.read_csv(r'output\aggregated\robust_07\Annual_balance_ch.csv', index_col=1, header=0, encoding='ISO-8859-1')


for pattern in pattern_list:
    print(f"Processing {pattern}...")
    # Step 2: Filter columns
    df_filtered = df.loc[:, df.columns.str.contains(pattern) & ~df.columns.str.contains("NTCfull")]/1e6

    # Step 3: Extract x-axis and y-axis values
    x_values = df_filtered.columns.str.split("_").str[1].unique()

    y_values = df_filtered.columns.str.split("_").str[0].unique()
    # reverse the order of itmes in y_values
    y_values = y_values[::-1]

    # Step 3: Prepare the data for plotting
    plot_data = []
    annotations = []
    items = ["lostload", "hydrogen", "SCGTfossil", "CCGTCCS", "pv_all", "wind_all", "nuclear", "curtailment"]


    for y in y_values:
        for x in x_values:
            column_name = f"{y}_{x}_{pattern}_{y}"
            if column_name in df_filtered.columns:
                # Initialize an empty list to collect text for all items for this x-y coordinate
                texts_for_xy = []
                for item in items:
                    if item in df_filtered.index:
                        value = df_filtered.loc[item, column_name]
                        # Append the text for this item to the list
                        texts_for_xy.append(f"{item}: {round(value, 1)}")
                # Join all texts with a newline character to create a single annotation for this x-y coordinate
                if texts_for_xy:  # Check if there are any texts to add
                    annotation_text ="<br>".join(texts_for_xy)
                    annotations.append(dict(x=x, y=y, text=annotation_text, showarrow=False))
            else:
                print(f"the intended column name {column_name} not found in the dataframe")

    # Step 4: Plot the graph
    fig = go.Figure()
    # fig.write_image("your_figure2.pdf", format='pdf')

    # Add dummy scatter for the layout
    fig.add_trace(go.Scatter(x=x_values, y=y_values, mode='markers', marker=dict(color='rgba(0,0,0,0)')))

    # When adding annotations, explicitly set properties to support multiline text
    for annotation in annotations:
        fig.add_annotation(
            x=annotation['x'],
            y=annotation['y'],
            text=annotation['text'],  # This text now uses <br> for line breaks
            showarrow=False,
            align='left',
            # Additional properties for better text formatting
        )

    # Explicitly set the range of the x-axis to include all x_values
    # This step assumes you can determine the appropriate range. Adjust as necessary.
    fig.update_xaxes(range=[-0.5, len(x_values)+4 - 0.5])
    # Update x-axis with tickvals and ticktext for explicit labeling
    fig.update_xaxes(tickvals=list(range(len(x_values))), ticktext=x_values)

    fig.update_layout(title=f"Values Visualization for {pattern}", xaxis_title="X-axis", yaxis_title="Y-axis")

    # update background color to be white
    fig.update_layout(plot_bgcolor='white')

    # increase the resolution of the plot
    fig.update_layout(
        autosize=False,
        width=1.3*1200,
        height=1*800,
    )

        

    fig.show()

    # print(f"Saving the plot for {pattern}...")
    # fig.write_image("output\\visualization\\your_figure.pdf", format='pdf')
    # print(f"Plot for {pattern} saved successfully!")