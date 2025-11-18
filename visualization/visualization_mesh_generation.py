""""
This script can be used for robust power planning, showing increased investment compared to the basecase scenario.
The script reads the output of the robust power planning model (Annual_balance_ch.csv) and ...
... creates a series of stacked bar charts to visualize the differences in generation between the basecase and corresponding scenarios.

Inputs:
- Annual_balance_ch3.csv (output of the robust power planning model, aggregated already)
    - base cases should be named as "basecase_"
    - normal years should be named as "NTCfull"

Outputs:
- Stacked bar charts showing the differences in generation between the basecase and corresponding scenarios
"""


import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import os
from .config import *

def plot_generation_diff(directory_path):
    file_path = os.path.join(directory_path, "Annual_balance_ch.csv")
    df = pd.read_csv(file_path, encoding="utf-8")  # Replaces unrecognized characters
    df = df.replace("-", 0) # replace all "-" with 0
    df.iloc[:, 2:] = df.iloc[:, 2:].apply(pd.to_numeric)/1000000  # Convert to TWh and all columns except the first two are of type float
    df = df[~df["tech/type"].str.contains("curtailment|household|commercial|flex electrolyzer")] # remove the row with "curtailment" and "household" and "commercial" and "flex electrolyzer"

    basecases = [col for col in df.columns if col.startswith("basecase_")] # Identify basecase scenarios

    # remove normal years from the data
    df_normalyears = [col for col in df.columns if "NTCfull" in col]
    df_normalyears = [col for col in df_normalyears if col not in basecases]
    df = df.drop(columns=df_normalyears)

    # Identify groups of scenarios for each basecase
    scenario_groups = {}
    for i, base in enumerate(basecases):
        start_idx = df.columns.get_loc(base)
        end_idx = (df.columns.get_loc(basecases[i+1]) if i+1 < len(basecases) else len(df.columns))
        scenario_groups[base] = df.columns[start_idx:end_idx]

    # Process each basecase scenario (i.e., create a separate figure for each basecase) ----------------
    for basecase, scenarios in scenario_groups.items():
        # Create subplot figure
        fig = make_subplots(
            rows=num_rows, 
            cols=num_cols,
            horizontal_spacing=0.001,  # Reduce horizontal gap (default is 0.2)
            vertical_spacing=0.001      # Reduce vertical gap (default is 0.3)
        )

        base_df = df[["gen/con", "tech/type", basecase]] # Extract basecase data
        
        legend_shown = set()  # Track technologies that have been added to the legend (later used to plot only once)

        col_idx = 0
        for scenario in scenarios:
            if scenario == basecase: # no subplot for the basecase
                continue
    
            # Step 1: Compute differences (apply some exceptions later) -----------------------------------------
            scenario_df = df[["tech/type", "gen/con", scenario]]
            merged_df = base_df.merge(scenario_df, on=["tech/type", "gen/con"], suffixes=("_base", "_scen"))
            merged_df["diff"] = merged_df[scenario] - merged_df[basecase]
            
            # Handle exceptions ----------------------------------------------------
            # Remove import values
            merged_df = merged_df[~merged_df["tech/type"].str.startswith("import_")]
            
            special_techs = ["psp_open", "psp_close", "battery", "hydrogen", "PH2P", ]
            special_rows_gen = merged_df[merged_df["tech/type"].isin(special_techs)]
            flex_damnd_row_names = ["flex " + tech for tech in special_techs]
            special_rows_demand = merged_df[merged_df["tech/type"].isin(flex_damnd_row_names)]
            
            # Handle exceptions ----------------------------------------------------
            # Storage technologies: Show only the generation effects (not the demand effects)
            for tech in special_techs:
                gen_val = special_rows_gen[(special_rows_gen["tech/type"] == tech) & (special_rows_gen["gen/con"] == "gen")]["diff"].sum()
                # demand_val = special_rows_demand[(special_rows_demand["tech/type"] == "flex " + tech) & (special_rows_demand["gen/con"] == "demand")]["diff"].sum()
                demand_val = 0 # keep this 0 if the plot wants to focus on the generation effects of storage technologies #NOTE
                # update the value in the merged_df for the tech with the difference between the generation and demand
                merged_df = merged_df[merged_df["tech/type"] != tech]  # Remove old rows
                merged_df = merged_df[merged_df["tech/type"] != "flex " + tech]  # Remove old rows
                merged_df = pd.concat([merged_df, pd.DataFrame({"gen/con": "net gen", "tech/type": [tech], "diff": [gen_val - demand_val]})])
            
            # remove flex tech from the name of the row
            merged_df["tech/type"] = merged_df["tech/type"].str.replace("flex ", "")

            # sum values in row psp_open in the row psp_close and then remove the row psp_open
            merged_df.loc[merged_df["tech/type"] == "psp_close", "diff"] = merged_df[merged_df["tech/type"] == "psp_close"]["diff"] + merged_df[merged_df["tech/type"] == "psp_open"]["diff"]
            merged_df = merged_df[merged_df["tech/type"] != "psp_open"]

            # Create stacked bar chart
            row, col = divmod(col_idx, 5)


            # Compute total absolute value for each technology across all scenarios
            tech_total_abs_values = merged_df.groupby("tech/type")["diff"].apply(lambda x: abs(x).sum())

            # Step 2: Plotting per technology ---------------------------------------------------------------
            for tech in merged_df["tech/type"].unique():
                tech_data = merged_df[merged_df["tech/type"] == tech] # Extract data for the current technology
                renamed_tech = tech_rename.get(tech, tech) # Rename technology if found in the dictionary
                color = tech_colors.get(tech, "#808080")  # Default color to gray if not found

                # Determine whether to show legend based on total absolute diff
                total_abs_value = tech_total_abs_values.get(tech, 0)
                show_legend = total_abs_value >= plot_treshold_TWh and tech not in legend_shown  # Only show legend for significant values
                
                if show_legend:
                    legend_shown.add(tech)  # Track which technologies are in the legend

                # Separate positive and negative values (for stacked bar chart, with negative values plotted below zero)
                positive_values = tech_data["diff"].apply(lambda x: x if x >= 0 else 0)
                negative_values = tech_data["diff"].apply(lambda x: x if x < 0 else 0)

                # Add positive values
                fig.add_trace(go.Bar(
                    name=renamed_tech, 
                    x=[scenario], 
                    y=positive_values.values,  
                    marker_color=color,
                    showlegend=bool(show_legend),  # Hide legend if total abs value is below threshold
                    offsetgroup="Positive",
                ), row=row+1, col=col+1)

                if show_negative_below_zero:
                    #Add negative values separately (plotted below zero)
                    fig.add_trace(go.Bar(
                        name=renamed_tech,  
                        x=[scenario], 
                        y=negative_values.values,  
                        marker_color=color,
                        showlegend=False,  # Keep legend hidden for negative part
                        offsetgroup="Negative",
                    ), row=row+1, col=col+1)
            
            col_idx += 1
        

        # ---------------------- Update layout for the entire figure -------------------------------------
        # Generate correct y-axis labels for all subplots
        y_axis_updates = {f"yaxis{r * num_cols + c + 1}": dict(range=[y_min, y_max]) 
                        for r in range(num_rows) for c in range(num_cols)}

        # Apply the update
        fig.update_layout(
            title_text=f"Differences for {basecase}",
            
            title_font=dict(size=24),  # Increase title font size

            # xaxis=dict(
            #     title="X-Axis Label",
            #     title_font=dict(size=18),  # X-axis title font size
            #     tickfont=dict(size=16)  # X-axis tick labels font size
            # ),
            
            # yaxis=dict(
            #     title="Y-Axis Label",
            #     title_font=dict(size=18),  # Y-axis title font size
            #     tickfont=dict(size=16)  # Y-axis tick labels font size
            # ),
            
            legend=dict(
                font=dict(size=16)  # Increase legend font size
            ),

            barmode='relative',
            height=1000,
            width=1500,
            **y_axis_updates,  # Apply to all subplots # type: ignore
            plot_bgcolor="white",
            # Reduce space between bars to make them fill the subplot better
            bargap=0.01,  # Space between bars inside a single stack (default is 0.2)
            bargroupgap=0.01,  # Space between different bar groups (default is 0.3)

        )


        # Hide x-axis tick labels for all subplots ---------------------------------------------------
        for i in range(1, num_rows * num_cols + 1):  
            fig.update_xaxes(showticklabels=False, row=(i-1)//num_cols + 1, col=(i-1) % num_cols + 1)

        # Hide y-axis tick labels for all subplots (except first coloumns and last column) ---------------------------------------------------
        for i in range(1, num_rows * num_cols + 1):
            if i % num_cols != 1 and i % num_cols != 0:
                fig.update_yaxes(showticklabels=False, row=(i-1)//num_cols + 1, col=(i-1) % num_cols + 1)
            if i % num_cols == 0: # if last column, show y-axis tick labels on the right
                fig.update_yaxes(showticklabels=True, row=(i-1)//num_cols + 1, col=(i-1) % num_cols + 1, side="right")
            
        # Add borders around subplots --------------------------------------------------------------
        # Define subplot borders
        shapes = []
        for r in range(num_rows):
            for c in range(num_cols):
                shapes.append({
                    "type": "rect",
                    "xref": f"paper",
                    "yref": f"paper",
                    "x0": c / num_cols, "x1": (c + 1) / num_cols,
                    "y0": 1 - (r + 1) / num_rows, "y1": 1 - r / num_rows,
                    "line": {"color": "black", "width": 2},  # Black border with thickness
                    "layer": "below"  # Ensures the border is behind the plots
                })
        fig.update_layout(
            shapes=shapes  # Add rectangular borders around subplots
        )   
        
        # Set font size for y-axis tick labels ---------------------------------------------------
        fig.update_yaxes(tickfont=dict(size=16))

        # # In all subplots, plot a line at every 20 TWh ---------------------------------------------------
        # for r in range(1, num_rows + 1):  # Loop through rows
        #     for c in range(1, num_cols + 1):  # Loop through columns
        #         for y_tick in range(0, y_max, 20):
        #             fig.add_hline(
        #                 y=y_tick,  # Horizontal line at y = 10
        #                 line=dict(color="black", width=0.5, dash="dash"),  # Black dashed line
        #                 row=r, col=c  # Apply to each subplot # type: ignore
        #             )

        # Add horizontal zero lines to all subplots ------------------------------------------------
        for r in range(1, num_rows + 1):  # Loop through rows
            for c in range(1, num_cols + 1):  # Loop through columns
                fig.add_hline(
                    y=0,  # Vertical line at x = 0
                    line=dict(color="black", width=1, dash="solid"),  # Black dashed line
                    row=r, col=c  # Apply to each subplot # type: ignore
                )

        fig.show()
