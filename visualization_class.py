import plotly.graph_objects as go
import pandas as pd
from visualization.get_mappings import get_mappings
from visualization.import_gen_dem_ts import import_gen_demand_timeseries
from visualization.map_ts import map_gen_dem_timeseries
import os
import utils.utilities_visualization as util_vis
import plotly.io as pio
pio.renderers.default = "browser"

# Define the scenario name ---------------------------------------------------------------
target_node = "CH00"  # a node name ("CH_00"), or "all"


scenarios_to_plot =[
    "20260311/2035_100_070_EUbat",
    "20260311/2035_090_070_EUbat",
    "20260311/2035_080_070_EUbat",
    "20260311/2035_070_inv_EUbat",
    "20260311/2035_060_070_EUbat",
    "20260311/2035_050_070_EUbat",
    "20260311/2035_040_070_EUbat",
    "20260311/2035_030_070_EUbat",
]

# ========== PLOT SWITCHES ==========
# Set to True to enable each plot, False to disable
PLOT_PRICE = True
PLOT_DISPATCH = True
PLOT_MERGED_DISPATCH = False  # Merged dispatch figure (combines similar technologies) - works only if PLOT_DISPATCH is True
PLOT_THERMAL_DISPATCH = True  # Plot thermal dispatch for each NodeDH individually
PLOT_THERMAL_DISPATCH_DUALS = False  # Plot shadow prices of thermal capacity constraints (HP, PTES, RH)
PLOT_DUALS_ALL_NODES = False        # If False, only plot duals for DH_NODE_DEFAULT; set True for all DH nodes
PLOT_DISPATCH_ALL_NODES = False  # If False, only plot dispatch for DH_NODE_DEFAULT; set True for all thermal nodes
DH_NODE_DEFAULT = "DH_medium"      # Default DH node for dual plot (substring match)
PLOT_INVESTMENTS = False
PLOT_EXPORT_IMPORT = False
PLOT_SOC = False  # State of charge (electrical storage)
PLOT_SOC_THERMAL = True  # State of charge for thermal storage - works only if PLOT_THERMAL_DISPATCH is True
PLOT_SOC_DUAL = False  # Opportunity cost of storage
PLOT_SOC_THERMAL_DUAL = False  # Opportunity cost of thermal storage - works only if PLOT_THERMAL_DISPATCH_DUALS is True
PLOT_THERMAL_STORAGE_LEVEL = False  # Thermal storage level
PLOT_THERMAL_STORAGE_LEVEL_REL = False  # Thermal storage level (relative)
PLOT_V2G = False  # Vehicle-to-grid
PLOT_SUM_GEN = False  # Total generation
PLOT_SUM_DEM = False  # Total demand
PLOT_AGG_GEN = False  # Aggregated generation per technology
PLOT_AGG_DEM = False  # Aggregated demand per technology
PLOT_IND_GEN = False  # Individual generation
PLOT_IND_DEM = False  # Individual demand
# ===================================

# output_dir = "output/" + scenario_name + "/"

# main code ------------------------------------------------------------------------------------------------
# 
class DemandTimeSeriesPlotter:
    def __init__(self, target_node):
        os.makedirs("plots", exist_ok=True)
        self.output_dir = ""
        self.scenario_name = ""
        self.target_node = target_node
        self.generation_all = pd.DataFrame()
        self.demand_inflx_all = pd.DataFrame()
        self.demand_flxbl_all = pd.DataFrame()
        self.export_all = pd.DataFrame()
        self.soc_all = pd.DataFrame()
        self.sum_assets = True
        self.fig_price = go.Figure()
        self.fig_sum_gen = go.Figure()
        self.fig_ind_gen = go.Figure()
        self.fig_agg_gen = go.Figure()
        self.fig_sum_dem = go.Figure()
        self.fig_agg_dem = go.Figure()
        self.fig_ind_dem = go.Figure()
        self.fig_export_import = go.Figure()
        self.fig_soc = go.Figure()
        self.fig_socTH = go.Figure()
        self.fig_socTH_pit = go.Figure()
        self.fig_socTH_tank = go.Figure()
        self.fig_th_sl = go.Figure()
        self.fig_th_sl_rel = go.Figure() # the same as fig_th_sl but the demands are normalized
        self.fig_soc_dual = go.Figure()
        self.fig_socth_dual = go.Figure()
        self.fig_dispatch = go.Figure()
        self.fig_dispatchDH_duals = go.Figure()
        self.plot_range_int_list = [0, 168]
        self.plot_range = []
        self.Map_plant_tech = {}
        self.Map_node_plant = {}
        self.Map_node_consumer = {}
        self.fig_v2g = go.Figure()
        self.fig_investments = go.Figure()
        
        # Define a fixed color mapping for technologies
        self.invest_color_mapping = util_vis.invest_color_mapping
        self.dispatch_color_mapping = util_vis.dispatch_color_mapping
        self.dispatch_legend_labels = util_vis.dispatch_legend_labels
        self.dispatchDH_legend_labels = util_vis.dispatchDH_legend_labels
        self.dispatchDH_color_mapping = util_vis.dispatchDH_color_mapping

    # NOTE: add a graph for state of charge. possibly copy the code from visualization.py

    def load_data(self):
        # Assuming you have functions to load the data, update the instance variables here
        (
            self.generation_all,
            self.demand_inflx_all,
            self.demand_flxbl_all,
            self.export_all,
            self.soc_all,
            self.price_all,
            self.soc_dual_all,
            self.socth_dual_all,
            self.lostload_all,
            self.infeed_all,
            self.curtailment_all,
            self.withdrawal_all,
            self.injection_all,
            self.supplyTH_all,
            self.consumptionDH_all,
            self.curtailmentTH_all,
            self.storageTH_all,
            self.socTH_all,
            self.th_sl_all,
            self.BA_th_lim,
            self.v2g_outflow_all,
            self.priceTh_all,
            self.EV_inflexible_demand_all,
            self.HP_inflexible_demand_all,
        ) = import_gen_demand_timeseries(self.output_dir, self.scenario_name)
        
        start_date = self.generation_all.columns[self.plot_range_int_list[0]]
        # end_date is equal to  self.generation_all.columns[self.plot_range_int_list[1]] if it exists, otherwise it is equal to self.generation_all.columns[-1]
        end_date = self.generation_all.columns[self.plot_range_int_list[1]] if self.plot_range_int_list[1] < len(self.generation_all.columns) else self.generation_all.columns[-1]
        self.plot_range = [start_date, end_date]

        (
            self.Map_node_plant,
            self.Map_node_consumer,
            Map_node_exportinglineATC,
            Map_node_importinglineATC,
            self.Map_plant_tech,
            self.Map_nodeDH_plantDH,
            self.Map_plantDH_tech,
        ) = get_mappings(self.output_dir)

        (
            self.plant_list,
            self.demand_inflx_list,
            self.demand_flxbl_list,
            self.exportATC_list,
            self.importATC_list,
            plant_with_soc,
        ) = map_gen_dem_timeseries(
            self.target_node,
            self.generation_all,
            self.demand_inflx_all,
            self.demand_flxbl_all,
            self.export_all,
            self.soc_all,
            self.Map_node_plant,
            self.Map_node_consumer,
            Map_node_exportinglineATC,
            Map_node_importinglineATC,
        )
        settings = pd.read_csv(f"{self.output_dir}settings.csv", index_col=0)
        self.heat_flexibility_Kelvin = float(settings.loc["heat_flexibility_Kelvin"].iloc[0]) # type: ignore

    def plot_dispatch(self, mode):
        # Dispatch figure object is treated differently than other figure objects. per scenario, one figure is created and shown.
        self.fig_dispatch = go.Figure()

        # Initialize a dataframe to store all trace data
        trace_dataframes = pd.DataFrame()

        # Plot demand aggregated-------------------------------------------------------------------------------------
        # Plot flexible demand aggregated ------------------
        # create list of techs (even the ones without flexible demand)
        all_tech = list(set([tech[0] for tech in self.Map_plant_tech.values()]))
        
        # order the list all_tech alphabetically
        all_tech.sort()   

        aggregated_data = pd.DataFrame(columns=all_tech)
        #NOTE: check what happens with electrolyzers, when they exist
        for tech in all_tech:
            aggregated_data[tech] = self.demand_flxbl_all.loc[
                [
                    plant
                    for plant in self.demand_flxbl_list
                    if tech in self.Map_plant_tech.get(plant, [])  # keeping the plants that are of the technology
                ],
                :,
            ].sum(axis=0)

        # plot columns in aggregated_data, if the sum of the column is greater than 0.5
        for tech, data in aggregated_data.items():
            if sum(data) > 0.5:
                trace_name = f"{tech} demand"
                self.fig_dispatch.add_trace(
                    go.Scatter(
                        x=data.index,
                        y=-data,
                        mode=mode,
                        stackgroup='two',  # this line enables stacking
                        name=trace_name,
                    )
                )
                # Add data to the trace_dataframes dataframe, first rename the column to trace_name
                data.name = trace_name
                trace_dataframes = pd.concat([trace_dataframes, data.to_frame().T], axis=0)
        
        # Plot inflexible EV demand (not in storage_charge, tracked separately as a parameter)
        if hasattr(self, 'EV_inflexible_demand_all') and not self.EV_inflexible_demand_all.empty:
            # Check if target node has inflexible EV demand
            if self.target_node in self.EV_inflexible_demand_all.index:
                ev_inflex_data = self.EV_inflexible_demand_all.loc[self.target_node, :]
                if ev_inflex_data.sum() > 0.5: # type: ignore
                    trace_name = "ev_inflex demand"
                    self.fig_dispatch.add_trace(
                        go.Scatter(
                            x=ev_inflex_data.index,
                            y=-ev_inflex_data,
                            mode=mode,
                            stackgroup='two',  # this line enables stacking
                            name=trace_name,
                        )
                    )
                    # Add data to the trace_dataframes dataframe
                    ev_inflex_data.name = trace_name
                    trace_dataframes = pd.concat([trace_dataframes, ev_inflex_data.to_frame().T], axis=0) # type: ignore

        # Plot inflexible household heat pump demand (not in flexible HP, tracked separately as a parameter)
        if hasattr(self, 'HP_inflexible_demand_all') and not self.HP_inflexible_demand_all.empty:
            # Check if target node has inflexible HP demand
            if self.target_node in self.HP_inflexible_demand_all.index:
                hp_inflex_data = self.HP_inflexible_demand_all.loc[self.target_node, :]
                if hp_inflex_data.sum() > 0.5: # type: ignore
                    trace_name = "hp_household_inflex demand"
                    self.fig_dispatch.add_trace(
                        go.Scatter(
                            x=hp_inflex_data.index,
                            y=-hp_inflex_data,
                            mode=mode,
                            stackgroup='two',  # this line enables stacking
                            name=trace_name,
                        )
                    )
                    # Add data to the trace_dataframes dataframe
                    hp_inflex_data.name = trace_name
                    trace_dataframes = pd.concat([trace_dataframes, hp_inflex_data.to_frame().T], axis=0) # type: ignore

        # Plot curtailement aggregated --------------------------------------------------------------------------------
        # curtailment of households ----------------------------------
        if "CH0" in self.target_node: #TODO: mannually defined
            if self.curtailment_all.loc["IDs",:].sum(): # TODO: currently, in the case of tariff based dispatch, curtailment is not reported in curtialment.csv (not allowed in the model) # type: ignore
                trace_name = "Curtailment Households"
                self.fig_dispatch.add_trace(
                    go.Scatter(
                        x=self.curtailment_all.loc["IDs",:].index,
                        y=-self.curtailment_all.loc["IDs",:],
                        mode=mode,
                        stackgroup='two',  # this line enables stacking
                        name=trace_name,
                    )
                )
                # Add data to the trace_dataframes dataframe, first rename the column to trace_name
                new_df = -self.curtailment_all.loc["IDs",:].T.copy()
                # rename the column to trace_name
                new_df.columns = [trace_name]

                self.curtailment_all.loc["IDs",:].name = trace_name
                trace_dataframes = pd.concat([trace_dataframes, -self.curtailment_all.loc["IDs",:].T], axis=0)

        # curtailment of fixed consumers ----------------------------------
        all_fixedconsumers_in_curtailment = self.curtailment_all.loc[self.curtailment_all.index.str.contains("fixedconsumer")].index
        all_fixedconsumers_in_region = self.Map_node_consumer[self.target_node]

        # fixedconsumers to plot, are intersection of all_fixedconsumers_in_curtailment and all_fixedconsumers_in_region
        fixedconsumers_to_plot = list(set(all_fixedconsumers_in_curtailment).intersection(all_fixedconsumers_in_region))

        if self.curtailment_all.loc[fixedconsumers_to_plot, :].sum().sum() > 0.5:
            trace_name = "Curtailment Market"
            self.fig_dispatch.add_trace(
                go.Scatter(
                    x=self.curtailment_all.loc[fixedconsumers_to_plot, :].sum().index,
                    y=-self.curtailment_all.loc[fixedconsumers_to_plot, :].sum(),
                    mode=mode,
                    stackgroup='two',  # this line enables stacking
                    name=trace_name,
                )
            )
            # Add data to the trace_dataframes dataframe, first rename the column to trace_name
            new_df = -self.curtailment_all.loc[fixedconsumers_to_plot, :].sum().to_frame()
            # rename the column to trace_name
            new_df.columns = [trace_name]
            trace_dataframes = pd.concat([trace_dataframes, new_df.T], axis=0)

        # Plot export and import ---------------------------------------------------------------------------------------
        # Plot export - all
        # export_sum is equal to sum of exports minus sum of imports,
        # that is sum of values for lines in exportATC_list minus sum of values for lines in importATC_list
        export_net = (
            -self.export_all.loc[self.exportATC_list, :].sum()
            + self.export_all.loc[self.importATC_list, :].sum()
        )
        # for every time step, export_net_positive is equal to export_net if export_net is greater than 0, otherwise it is equal to 0
        export_net_positive = export_net.where(export_net >= 0, 0)

        export_net_negative = export_net.where(export_net < 0, 0)      

        trace_name = "Net_Export"
        self.fig_dispatch.add_trace(
            go.Scatter(
                x=export_net_negative.index,
                y=export_net_negative,
                mode=mode,
                stackgroup='two',  # this line enables stacking
                name=trace_name,
            )
        )
        # Add data to the trace_dataframes dataframe, first rename the column to trace_name
        export_net_negative.name = trace_name

        trace_dataframes = pd.concat([trace_dataframes, export_net_negative.to_frame().T], axis=0)

        # Plot generation (aggregated per technoloyg) --------------------------------------------------------------------
        aggregated_data = {}
        self.plant_list.sort()
        for plant in self.plant_list:
            tech = tuple(self.Map_plant_tech.get(plant, []))  # Convert list to tuple
            if tech:
                if tech in aggregated_data:
                    aggregated_data[tech] = aggregated_data[tech].add(
                        self.generation_all.loc[plant, :], fill_value=0
                    )
                else:
                    aggregated_data[tech] = self.generation_all.loc[plant, :]
        
        for tech, data in aggregated_data.items():
            if sum(data) > 0.5:
                trace_name = f"{tech[0]} gen"
                self.fig_dispatch.add_trace(
                    go.Scatter(
                        x=data.index,
                        y=data,
                        mode=mode,
                        stackgroup='one',  # this line enables stacking
                        name=trace_name,
                    )
                )
                # Add data to the trace_dataframes dataframe, first rename the column to trace_name
                data.name = trace_name
                trace_dataframes = pd.concat([trace_dataframes, data.to_frame().T], axis=0)

        # Plot lost load -----------------------------------------------------------------------------------------------
        # lost load of households ----------------------------------
        if "CH0" in self.target_node: #TODO: mannually defined
            if self.lostload_all.loc["IDs",:].sum(): # type: ignore
                trace_name = "Lost Load households"
                self.fig_dispatch.add_trace(
                    go.Scatter(
                        x=self.lostload_all.loc["IDs",:].index,
                        y=self.lostload_all.loc["IDs",:],
                        mode=mode,
                        stackgroup='one',  # this line enables stacking
                        name=trace_name,
                    )
                )
                # Add data to the trace_dataframes dataframe, first rename the column to trace_name
                self.lostload_all.loc["IDs",:].name = trace_name
                trace_dataframes = pd.concat([trace_dataframes, self.lostload_all.loc["IDs",:].to_frame().T], axis=0) # type: ignore

        # lost load of fixed conumers ----------------------------------
        if sum(self.lostload_all.loc[self.target_node + "_fixedconsumer"]) > 0.5:        
            trace_name = "Lost Load"
            self.fig_dispatch.add_trace(
                go.Scatter(
                    x=self.lostload_all.loc[self.target_node + "_fixedconsumer"].index,
                    y=self.lostload_all.loc[self.target_node + "_fixedconsumer"],
                    mode=mode,
                    stackgroup='one',  # this line enables stacking
                    name=trace_name,
                )
            )
            # Add data to the trace_dataframes dataframe, first rename the column to trace_name
            self.lostload_all.loc[self.target_node + "_fixedconsumer"].name = trace_name
            trace_dataframes = pd.concat([trace_dataframes, self.lostload_all.loc[self.target_node + "_fixedconsumer"].to_frame().T], axis=0)

        # Plot infeed -----------------------------------------------------------------------------------------------
        infeed_tech = self.infeed_all.index.get_level_values(1).unique()
        consumer_type_dict = { 
            "fixed": [item for item in self.demand_inflx_list if "fixedconsumer" in item], 
            "households": [item for item in self.demand_inflx_list if "ID" in item],
        }

        tech_mapping = {
            "Wind" : [item for item in infeed_tech if "windon" in item],
            "Wind offshore" : [item for item in infeed_tech if "windof" in item],
            "RoR": [item for item in infeed_tech if "ror" in item],
            "PV" : [item for item in infeed_tech if "pv" in item],
        }

        for tech, tech_subs in tech_mapping.items():
            infeed_sub_df = self.infeed_all.loc[(self.target_node + "_fixedconsumer", tech_subs), :].sum() # type: ignore
            if "CH0" in self.target_node: #TODO: mannually defined
                if any(sub in self.infeed_all.loc["IDs", :].index.get_level_values(0) for sub in tech_subs):
                    if self.infeed_all.loc[("IDs", "pv"), :].sum().sum() > 0:
                        infeed_sub_df = infeed_sub_df + self.infeed_all.loc[("IDs", "pv"), :] # type: ignore
                    else:
                        item_list = set(self.infeed_all.index.get_level_values(0))
                        item_list = [item for item in item_list if "ID" in item and item != "IDs"]
                        infeed_sub_df = infeed_sub_df + self.infeed_all.loc[(item_list, "pv"), :].sum() # type: ignore
            trace_name = f"Infeed preexisting {tech}"
            if (infeed_sub_df != 0).any(): # type: ignore
                self.fig_dispatch.add_trace(
                    go.Scatter(
                        x=infeed_sub_df.index,
                        y=infeed_sub_df,
                        mode=mode,
                        stackgroup='one',  # this line enables stacking
                        name=trace_name,
                    )
                )
                # Add data to the trace_dataframes dataframe, first rename the column to trace_name
                infeed_sub_df.name = trace_name
                trace_dataframes = pd.concat([trace_dataframes, infeed_sub_df.to_frame().T], axis=0) # type: ignore

        # Plot export and import ---------------------------------------------------------------------------------------
        self.fig_dispatch.add_trace(
            go.Scatter(
                x=export_net_positive.index,
                y=export_net_positive,
                mode=mode,
                stackgroup='one',  # this line enables stacking
                name="Net Import",
            )
        )          
        # Add data to the trace_dataframes dataframe, first rename the column to trace_name
        export_net_positive.name = "Net Import"
        trace_dataframes = pd.concat([trace_dataframes, export_net_positive.to_frame().T], axis=0)
        # Plot inflexible demand-------------------------------------------------------------------------------------
        demand_fixed_df = self.demand_inflx_all.loc[self.demand_inflx_list, "fixed", :].sum() # type: ignore
        demand_fixed_df2 = self.demand_inflx_all.loc[[self.target_node + "_fixedconsumer"], "fixed", :].sum() # type: ignore
        demand_fixed_df3 = demand_fixed_df - self.withdrawal_all + self.injection_all

        self.fig_dispatch.add_trace(
            go.Scatter(
                x=demand_fixed_df2.index,
                y=demand_fixed_df2,
                mode=mode,
                name="Consumption - Inflexible",
            )
        )

        # Add price on secondary y-axis (right side)
        self.fig_dispatch.add_trace(
            go.Scatter(
                x=self.price_all.loc[self.target_node, :].index,
                y=self.price_all.loc[self.target_node, :],
                mode=mode,
                name="Price (CHF/MWh)",
                yaxis="y2",
                line=dict(color="black", width=1.5),
            )
        )
        
        # Configure secondary y-axis for price
        self.fig_dispatch.update_layout(
            yaxis2=dict(
                title="Price [CHF/MWh]",
                overlaying="y",
                side="right",
                showgrid=False,
            )
        )

        # self.fig_dispatch.add_trace(
        #     go.Scatter(
        #         x=demand_fixed_df3.index,
        #         y=demand_fixed_df3,
        #         mode=mode,
        #         name="Consumption fixed part - CH00 and HHs",
        #     )
        # )
        # add demand_fixed_df2 and demand_fixed_df3 to trace_dataframes, first rename the columns to the trace names
        demand_fixed_df2.name = "Consumption - CH00"
        # demand_fixed_df3.name = "Consumption fixed part - CH00 and HHs"
        trace_dataframes = pd.concat([trace_dataframes, demand_fixed_df2.to_frame().T, demand_fixed_df3.to_frame().T], axis=0)


        # ---------------
        # apply color mapping to the figure following color_map, if a trace with the name of the key exists in the figure
        for trace in self.fig_dispatch.data:
            if trace.name in self.dispatch_color_mapping: # type: ignore
                trace.line.color = self.dispatch_color_mapping[trace.name] # type: ignore

        # save trace_dataframes to csv
        trace_dataframes.to_csv(f"plots/Dispatch_{self.scenario_name}_trace_dataframes.csv")


        # ------------------------------------------------------------------------------------------------------------------------
        # create hour-of-day, hour-of-week, weekly, monthly graphs ---------------------------------------------------------------
        # ------------------------------------------------------------------------------------------------------------------------
        # new_fig_1 = util_vis.aggregate_figure_by_time(self.fig_dispatch, mode_agg="hour_in_day", agg_func="mean", scenario_name = self.scenario_name)
        # new_fig_1.show()
        
        # new_fig_2 = util_vis.aggregate_figure_by_time(self.fig_dispatch, mode_agg="hour_in_week", agg_func="mean", scenario_name = self.scenario_name)
        # new_fig_2.show()
        
        # new_fig_3 = util_vis.aggregate_figure_by_time(self.fig_dispatch, mode_agg="monthly", agg_func="mean", scenario_name = self.scenario_name)
        # new_fig_3.show()
        
        # new_fig_4 = util_vis.aggregate_figure_by_time(self.fig_dispatch, mode_agg="weekly", agg_func="mean", weekly_anchor="W-SUN", scenario_name = self.scenario_name)
        # new_fig_4.show()

        if PLOT_MERGED_DISPATCH:
            # ------------------------------------------------------------------------------------------------------------------------
            # combining several technologies, for smaller figures ---------------------------------------------------------------------
            # ------------------------------------------------------------------------------------------------------------------------
            self.fig_merged = util_vis.merge_dispatch(
                self.fig_dispatch, 
                self.dispatch_color_mapping,
                trace_dataframes,
            )

            # Renaming the traces ---------
            # for every trace in self.fig_merged, rename the name to self.dispatch_legend_labels[trace.name]['de'] or 'en'
            for trace in self.fig_merged.data:
                if trace.name in self.dispatch_legend_labels: # type: ignore
                    trace.name = self.dispatch_legend_labels[trace.name]['en'] # type: ignore
            # increase all font sizes
            self.fig_merged.update_layout(
                font=dict(size=20),
                legend=dict(font=dict(size=20),),
            )
            # style the figure
            self.fig_merged.update_xaxes(range=self.plot_range)
            self.fig_merged.update_layout(title=f"Dispatch {self.scenario_name}", xaxis_title="Time", yaxis_title="Power (MW)")
            self.fig_merged.update_layout(
                barmode='group',
                xaxis_tickangle=-45,
                height=800,
                width=1200,
                # plot_bgcolor="white",
                # paper_bgcolor="white",
                font=dict(color="black"),
                legend=dict(font=dict(size=18, color="black"),),
                margin=dict(l=0, r=0, t=50, b=0),
            )
            self.fig_merged.show()

        # ----------------
        self.fig_dispatch.update_xaxes(range=self.plot_range)
        self.fig_dispatch.update_layout(title=f"Dispatch {self.scenario_name}")
        self.fig_dispatch.update_layout(
            barmode='group',
            xaxis_tickangle=-45,
            height=800,
            width=1200,
            legend=dict(
                x=1.15,  # Move legend further to the right
                y=1,
                xanchor='left',
                yanchor='top'
            ),
        )
        self.fig_dispatch.show()
        # save to html
        self.fig_dispatch.update_xaxes(range=self.plot_range)
        self.fig_dispatch.update_layout(title=f"Dispatch {self.scenario_name}")
        self.fig_dispatch.write_html(f"plots/Dispatch_{self.scenario_name}.html")

        # -------------------------------------------------------------------------------------------------------------------------


        # Return the dataframe containing all trace data
        return trace_dataframes

    def plot_dispatchDH(self, mode, NodeDH):
        """
        Plot district heating dispatch for the whole CH

        NodeDH : list
            Nodes that are relevant for the plot
        """

        # Combine NodeDH into a regex pattern
        pattern = "|".join(NodeDH)  # e.g. "DH01|DH02|DH03"

        # keep only the supplyth, storageth and consumptiondh that are required for the plot
        supplyTH = self.supplyTH_all[self.supplyTH_all.index.str.contains(pattern)]
        storageTH = self.storageTH_all[self.storageTH_all.index.str.contains(pattern)]
        consumptionDH = self.consumptionDH_all[self.consumptionDH_all.index.str.contains(pattern)]
        curtialmentTH = self.curtailmentTH_all[self.curtailmentTH_all.index.str.contains(pattern)]

        # Dispatch figure object is treated differently than other figure objects. per scenario, one figure is created and shown.
        self.fig_dispatchDH = go.Figure()

        # plot all values in supplyTH in a stacked line plot
        for plant in supplyTH.index:
            # if the sum of the values is greater than 0.5
            if supplyTH.loc[plant, :].sum() > 0.5: # type: ignore   
                self.fig_dispatchDH.add_trace(
                    go.Scatter(
                        x=supplyTH.columns,
                        y=supplyTH.loc[plant, :],
                        mode=mode,
                        stackgroup='one',  # this line enables stacking
                        name=plant,
                    )
                )

        # plot values in self.storageTH_all in a stacked line plot
        for plant in storageTH.index:
            # if the sum of the values is greater than 0.5
            if storageTH.loc[plant, :].sum() > 0.5: # type: ignore
                self.fig_dispatchDH.add_trace(
                    go.Scatter(
                        x=storageTH.columns,
                        y=-storageTH.loc[plant, :],
                        mode=mode,
                        stackgroup='two',  # this line enables stacking
                        name=plant+"_demand",
                    )
                )

        # add value of self.curtailmentTH_all to stackgroup='two', if the sum of the values is greater than 0.5
        if curtialmentTH.sum().sum() > 0.5:
            self.fig_dispatchDH.add_trace(
                go.Scatter(
                    x=curtialmentTH.columns,
                    y=-curtialmentTH.sum(),
                    mode=mode,
                    stackgroup='two',  # this line enables stacking
                    name="Curtailment",
                )
            )

        # plot sum of the values in self.consumptionDH_all as a single black line 
        self.fig_dispatchDH.add_trace(
            go.Scatter(
                x=consumptionDH.columns,
                y=consumptionDH.sum(axis=0),
                mode=mode,
                name="_Consumption", # Thermal load
            )
        )
        
        # plot thermal price
        for node in NodeDH:
            try: # backwards compatibility
                self.fig_dispatchDH.add_trace(
                    go.Scatter(
                        x=self.priceTh_all.loc[node, :].index,
                        y=self.priceTh_all.loc[node, :],
                        mode=mode,
                        name=f"_Price - Heat", # Preis - Thermisch   / Price - Thermal 
                        yaxis="y2",  # <-- Add this line
                    )
                )
            except KeyError:
                pass
        # plot electricity prices, but scale it so that it is visible on the same graph
        self.fig_dispatchDH.add_trace(
            go.Scatter(
                x=self.price_all.loc[self.target_node, :].index,
                y=self.price_all.loc[self.target_node, :],
                mode=mode,
                name="_Price - Electricity",
                yaxis="y2",
            )
        )

        # apply color mapping to the figure following color_map, if a trace with the name of the key exists in the figure
        for trace in self.fig_dispatchDH.data:
            # if part of trace.name is in any of the keys of self.dispatchDH_color_mapping
            if any("_" + key in trace.name for key in self.dispatchDH_color_mapping.keys()): # type: ignore
                # get the key that is in trace.name
                key = next(key for key in self.dispatchDH_color_mapping.keys() if key in trace.name) # type: ignore
                trace.line.color = self.dispatchDH_color_mapping[key] # type: ignore

        # Renaming the traces ---------
        # for every trace in self.fig_merged, rename the name to self.dispatchDH_legend_labels[trace.name]['de']
        for trace in self.fig_dispatchDH.data:
            if any("_" + key in trace.name for key in self.dispatchDH_legend_labels.keys()): # type: ignore
                # get the key that is in trace.name
                key = next(key for key in self.dispatchDH_legend_labels.keys() if "_" + key in trace.name) # type: ignore
                trace.name = self.dispatchDH_legend_labels[key]['de'] # type: ignore
        
        # add title and show the figure
        self.fig_dispatchDH.update_xaxes(range=self.plot_range)
        self.fig_dispatchDH.update_layout(title=f"Aggregate Swiss district heating dispatch {self.scenario_name}") # Thermische Dispatch
        
        # style the figure -------------------------------------------------
        self.fig_dispatchDH.update_xaxes(range=self.plot_range)
        self.fig_dispatchDH.update_layout(title=f"Thermal Dispatch {self.scenario_name} - {NodeDH[0]}") # Thermische Dispatch
        self.fig_dispatchDH.update_layout(
            barmode='group',
            xaxis_tickangle=-45,
            height=800,
            width=1200,
            # plot_bgcolor="white",
            # paper_bgcolor="white",
            font=dict(color="black"),
            legend=dict(
                font=dict(size=18, color="black"),
                x=1.15,           # Move legend to the right outside the plot
                y=1,
                xanchor='left',   # Anchor legend box to the left
                yanchor='top'
            ),            margin=dict(l=0, r=0, t=50, b=0),
        )

        util_vis.align_yaxes_zero(self.fig_dispatchDH, "yaxis", "yaxis2")

        # Adjust yaxis and yaxis2 properties
        # assign names to yaxis and yaxis2
        # align the yaxis2 with yaxis, i.e., make sure their 0 values are aligned
        self.fig_dispatchDH.update_layout(
            yaxis=dict(
                title="Leistung (MW)",
                showgrid=False,
                zeroline=True,
                zerolinecolor='black',
                anchor="x",          # Anchor yaxis to x
                position=0.0,        # Left side
            ),
            yaxis2=dict(
                title="Preis (CHF/MWh)",
                overlaying="y",
                side="right",
                showgrid=False,
                zeroline=True,
                zerolinecolor='black',
                anchor="x",          # Anchor yaxis2 to x
                position=1.0,        # Right side
                # matches='y',         # <-- This aligns the zero points!
            )
        )
        self.fig_dispatchDH.show()
        return

    def plot_dispatchDH_duals(self, mode, NodeDH):
        """
        Plot shadow prices (duals) of thermal capacity constraints for HP, PTES, and RH.

        Mirrors the layout of plot_dispatchDH. One line per plant, all three constraints
        overlaid with different line styles:
          - generationTh_limit   : solid   (MW_th generation capacity)
          - storageTh_rate_limit : dashed  (MW pump/charge rate capacity)
          - storageTh_soc_limit  : dotted  (MWh_th energy storage capacity — PTES only)

        Left y-axis : dual value (CHF/MW or CHF/MWh per hour)
        Right y-axis: thermal heat price (CHF/MWh), for reference
        """
        pattern = "|".join(NodeDH)

        # --- Load and pivot each dual CSV into plant x timestep DataFrame ---
        dual_constraints = {
            "generationTh_limit":   {"dash": "solid",  "label_suffix": " [gen cap — CHF/MW]"},
            "storageTh_rate_limit": {"dash": "dash",   "label_suffix": " [pump cap — CHF/MW]"},
            "storageTh_soc_limit":  {"dash": "dot",    "label_suffix": " [soc cap — CHF/MWh]"},
            "storageTh_soc":        {"dash": "solid",  "label_suffix": " [soc value — CHF/MWh]"},
        }

        # Build t_XXXX -> timestamp mapping from supplyTH_all, which is already converted
        # by import_gen_demand_timeseries using util.hour_to_timestamp().
        # Use the first available dual CSV instead of assuming generationTh_limit_dual.csv
        # is always present.
        t_to_timestamp = {}
        for constraint_name in dual_constraints:
            mapping_csv_path = os.path.join(self.output_dir, f"{constraint_name}_dual.csv")
            if not os.path.exists(mapping_csv_path):
                continue
            df_t = pd.read_csv(mapping_csv_path, usecols=["T"])
            t_index_raw = df_t["T"].unique()
            t_to_timestamp = dict(zip(t_index_raw, self.supplyTH_all.columns[:len(t_index_raw)]))
            break

        settings = pd.read_csv(os.path.join(self.output_dir, "settings.csv"), index_col=0, header=0)
        weight_shock = float(settings.loc["weight_in_objective_fcn", self.scenario_name])  # type: ignore

        dual_dfs = {}
        for constraint_name in dual_constraints:
            csv_path = os.path.join(self.output_dir, f"{constraint_name}_dual.csv")
            if not os.path.exists(csv_path):
                continue
            df_raw = pd.read_csv(csv_path)
            # Structure: [plant_col, T, Scenarios, value]
            plant_col = df_raw.columns[0]   # e.g. "PDH" or "PDH_storage"
            if "T" not in df_raw.columns:
                continue
            # Filter to the current scenario before pivoting (mirrors read_filtered_csv)
            if "Scenarios" in df_raw.columns:
                df_raw = df_raw[df_raw["Scenarios"] == self.scenario_name]
            df_pivot = df_raw.groupby([plant_col, "T"])["value"].mean().reset_index().pivot(index=plant_col, columns="T", values="value")
            df_pivot = df_pivot / weight_shock
            # Map t_XXXX columns to timestamps to align x-axis with dispatch plot
            df_pivot = df_pivot.rename(columns=t_to_timestamp)
            # Filter to relevant DH nodes
            df_pivot = df_pivot[df_pivot.index.str.contains(pattern)]
            dual_dfs[constraint_name] = df_pivot

        if not dual_dfs:
            print("No dual CSV files found. Run the model first.")
            return

        # Load capacity to filter out near-zero (non-invested) plants
        cap_gen    = pd.read_csv(os.path.join(self.output_dir, "genTh_max.csv"))
        cap_energy = pd.read_csv(os.path.join(self.output_dir, "gen_energyTh_max.csv"))
        cap_gen_series    = cap_gen.groupby("PDH")["value"].mean()
        cap_energy_series = cap_energy.groupby("PDH_TES")["value"].mean()
        CAP_MIN_MW = 1.0  # skip plants with capacity below this (numerical noise)

        self.fig_dispatchDH_duals = go.Figure()

        for constraint_name, df in dual_dfs.items():
            dash_style   = dual_constraints[constraint_name]["dash"]
            label_suffix = dual_constraints[constraint_name]["label_suffix"]

            for plant in df.index:
                # Skip non-invested plants (numerical noise from solver)
                cap = cap_gen_series.get(plant, cap_energy_series.get(plant, 0.0))
                if cap < CAP_MIN_MW:
                    continue

                # storageTh_soc is an equality constraint: dual non-zero every hour.
                # Negate (same Pyomo convention as inequality duals: -dual = value in
                # CHF/MWh). Resample to daily mean to avoid a dense 8760-point band.
                # Inequality duals: filter to binding hours only, negate, plot as markers.
                DUAL_THRESHOLD = 1e-4
                series = df.loc[plant, :]
                is_equality = (constraint_name == "storageTh_soc")
                if is_equality:
                    # Negate here so plot_series is already in display sign convention
                    plot_series = (-series).resample("D").mean().dropna()
                    plot_mode   = "lines"
                else:
                    # Negate here too — LP inequality duals are negative for ≤ constraints
                    plot_series = -series[series.abs() > DUAL_THRESHOLD]
                    plot_mode   = "markers"
                if plot_series.empty:
                    continue

                trace_name = plant + label_suffix

                # Determine color using same keyword matching as dispatch plot
                color = None
                if any("_" + key in plant for key in self.dispatchDH_color_mapping.keys()):
                    key = next(k for k in self.dispatchDH_color_mapping.keys() if "_" + k in plant)
                    color = self.dispatchDH_color_mapping[key]

                y_values = plot_series.values
                self.fig_dispatchDH_duals.add_trace(
                    go.Scatter(
                        x=plot_series.index,
                        y=y_values,
                        mode=plot_mode,
                        name=trace_name,
                        marker=dict(size=5, symbol={
                            "generationTh_limit":   "circle",
                            "storageTh_rate_limit": "diamond",
                            "storageTh_soc_limit":  "square",
                            "storageTh_soc":        "triangle-up",
                        }.get(constraint_name, "circle"), color=color),
                        line=dict(color=color) if is_equality else None,
                    )
                )

        # Thermal price on the same axis as duals (both in CHF/MWh)
        for node in NodeDH:
            try:
                self.fig_dispatchDH_duals.add_trace(
                    go.Scatter(
                        x=self.priceTh_all.loc[node, :].index,
                        y=self.priceTh_all.loc[node, :],
                        mode=mode,
                        name="Price - Heat",
                        line=dict(dash="solid"),
                    )
                )
            except KeyError:
                pass

        self.fig_dispatchDH_duals.update_xaxes(range=self.plot_range)
        self.fig_dispatchDH_duals.update_layout(
            title=f"Thermal Capacity Duals {self.scenario_name} - {NodeDH[0]}",
            height=800,
            width=1200,
            font=dict(color="black"),
            legend=dict(
                font=dict(size=18, color="black"),
                x=1.15,
                y=1,
                xanchor='left',
                yanchor='top',
            ),
            margin=dict(l=0, r=0, t=50, b=0),
            xaxis_tickangle=-45,
            yaxis=dict(
                title="CHF/MWh",
                showgrid=False,
                zeroline=True,
                zerolinecolor='black',
            ),
        )
        self.fig_dispatchDH_duals.show()
        return

    def plot_sum_gen(self, mode):
        df_to_plot = self.generation_all.loc[self.generation_all.index.isin(self.Map_node_plant[self.target_node]),:]
        self.fig_sum_gen.add_trace(
            go.Scatter(
                x=df_to_plot.columns,
                y=df_to_plot.sum(axis=0)/1,
                mode=mode,
                name=f"{self.scenario_name}_generation",
            )
        )

    def plot_ind_gen(self, mode):
        for plant in self.plant_list:
            self.fig_ind_gen.add_trace(
                go.Scatter(
                    x=self.generation_all.loc[plant, :].index,
                    y=self.generation_all.loc[plant, :],
                    mode=mode,
                    name=plant,
                )
            )

    def plot_agg_gen(self, mode):
        aggregated_data = {}
        for plant in self.plant_list:
            tech = tuple(self.Map_plant_tech.get(plant, []))  # Convert list to tuple
            if tech:
                if tech in aggregated_data:
                    aggregated_data[tech] = aggregated_data[tech].add(
                        self.generation_all.loc[plant, :], fill_value=0
                    )
                else:
                    aggregated_data[tech] = self.generation_all.loc[plant, :]

        for tech, data in aggregated_data.items():
            self.fig_agg_gen.add_trace(
                go.Scatter(
                    x=data.index,
                    y=data,
                    mode=mode,
                    name=f"{self.scenario_name}_{tech[0]}",
                )
            )

        self.fig_agg_gen.add_trace(
            go.Scatter(
                x=self.lostload_all.loc[self.target_node + "_fixedconsumer"].index,
                y=self.lostload_all.loc[self.target_node + "_fixedconsumer"],
                mode=mode,
                name=f"{self.scenario_name}_lostload",
            )
        )

    def plot_sum_dem(self, mode):
        df_inflx_to_plot = self.demand_inflx_all[self.demand_inflx_all.index.get_level_values(0).isin(self.demand_inflx_list) & (self.demand_inflx_all.index.get_level_values(1) == "fixed")]

        self.fig_sum_dem.add_trace(
            go.Scatter(
                x=df_inflx_to_plot.sum(axis=0).index,
                y=df_inflx_to_plot.sum(axis=0),
                mode=mode,
                name=f"{self.scenario_name}_inflexible",
            )
        )

        df_flxbl_to_plot = self.demand_flxbl_all[self.demand_flxbl_all.index.isin(self.demand_flxbl_list)]
        
        self.fig_sum_dem.add_trace(
            go.Scatter(
                x=df_flxbl_to_plot.sum(axis=0).index,
                y=df_flxbl_to_plot.sum(axis=0),
                mode=mode,
                name=f"{self.scenario_name}_flexible",
            )
        )

        self.fig_sum_dem.add_trace(
            go.Scatter(
                x=df_flxbl_to_plot.sum(axis=0).index,
                y=df_inflx_to_plot.sum(axis=0) + df_flxbl_to_plot.sum(axis=0),
                mode=mode,
                name=f"{self.scenario_name}_total",
            )
        )

        df_ll_to_plot = self.lostload_all.loc[self.lostload_all.index.get_level_values(0).isin(self.demand_inflx_list), :]
        # sum values in df_ll_to_plot if the sum of the values is greater than 0.5
        if df_ll_to_plot.sum().sum() > 0.5:
            self.fig_sum_dem.add_trace(
                go.Scatter(
                    x=self.lostload_all.sum(axis=0).index,
                    y=self.lostload_all.sum(axis=0)/1,
                    mode=mode,
                    name=f"{self.scenario_name}_lostload",
                )
            )

    def plot_ind_dem(self, mode):
        # Plot flexible demand individually
        for demand_name in self.demand_flxbl_list:
            self.fig_ind_dem.add_trace(
                go.Scatter(
                    x=self.demand_flxbl_all.loc[demand_name, :].index,
                    y=self.demand_flxbl_all.loc[demand_name, :],
                    mode=mode,
                    name=demand_name,
                )
            )

        # Plot inflexible demand
        for demand_name in self.demand_inflx_list:
            self.fig_ind_dem.add_trace(
                go.Scatter(
                    x=self.demand_inflx_all.loc[demand_name, :].index,
                    y=self.demand_inflx_all.loc[demand_name, :],
                    mode=mode,
                    name=demand_name,
                )
            )

    def plot_agg_dem(self, mode):
        aggregated_data = {}
        for plant in self.demand_flxbl_list:
            # self.Map_plant_tech[plant] is a list with one element
            tech = self.Map_plant_tech[plant][0]
            if tech in aggregated_data:
                aggregated_data[tech] = aggregated_data[tech].add(
                    self.demand_flxbl_all.loc[plant, :], fill_value=0
                )
            else:
                aggregated_data[tech] = self.demand_flxbl_all.loc[plant, :]

        for tech, data in aggregated_data.items():
            self.fig_agg_dem.add_trace(
                go.Scatter(
                    x=data.index,
                    y=data,
                    mode=mode,
                    name=f"{self.scenario_name}_{tech}",
                )
            )

    def plot_export_import(self, mode):
        for line in self.exportATC_list:
            self.fig_export_import.add_trace(
                go.Scatter(
                    x=self.export_all.loc[line, :].index,
                    y=-self.export_all.loc[line, :],
                    mode=mode,
                    name=f"{self.scenario_name}_Import_{line}",
                )
            )
        for line in self.importATC_list:
            self.fig_export_import.add_trace(
                go.Scatter(
                    x=self.export_all.loc[line, :].index,
                    y=self.export_all.loc[line, :],
                    mode=mode,
                    name=f"{self.scenario_name}_Export_{line}",
                )
            )

        # Plot export - all
        # export_sum is equal to sum of exports minus sum of imports,
        # that is sum of values for lines in exportATC_list minus sum of values for lines in importATC_list
        export_sum = (
            -self.export_all.loc[self.exportATC_list, :].sum()
            + self.export_all.loc[self.importATC_list, :].sum()
        )

        self.fig_export_import.add_trace(
            go.Scatter(
                x=export_sum.index,
                y=export_sum,
                mode=mode,
                name=f"{self.scenario_name}_Export_all",
            )
        )

    def plot_price(self, mode):
        for node in [
            self.target_node,
        ]:
            self.fig_price.add_trace(
                go.Scatter(
                    x=self.price_all.loc[node, :].index,
                    y=self.price_all.loc[node, :],
                    mode=mode,
                    name=f"{self.scenario_name}_{node}",
                )
            )

    def plot_soc(self, mode):
        # plants with soc are defined as plants that are in self.plant_list and self.soc_all.index
        plants_with_soc = [
            plant for plant in self.plant_list if plant in self.soc_all.index
        ]

        for plant in plants_with_soc:
            if plant in self.soc_all.index:
                self.fig_soc.add_trace(
                    go.Scatter(
                        x=self.soc_all.loc[plant, :].index,
                        y=self.soc_all.loc[plant, :]/(1000*1000),
                        mode=mode,
                        name=f"{self.scenario_name}_{plant}",
                    )
                )
        # add a trace that sums up the soc of all plants that are in self.plant_list and self.soc_all.index
        self.fig_soc.add_trace(
            go.Scatter(
                x=self.soc_all.loc[plants_with_soc, :].sum(axis=0).index,
                y=self.soc_all.loc[plants_with_soc, :].sum(axis=0)/(1000*1000),
                mode=mode,
                name=f"{self.scenario_name}_SOC_all",
            )
        )

    def plot_socTH(self, mode, NodeDH=[]):    
        # district heating ----------------------------------
        # soc of the thermal sotrage assets

        if NodeDH == []:
        # plants with socTH are defined as plants that have values in self.socTH_all
            plants_with_socth = [
                plant for plant in self.socTH_all.index
            ]
        else:
            plants_with_socth = [
                plant for plant in self.socTH_all.index if plant in self.Map_nodeDH_plantDH[NodeDH[0]]
            ]

        for plant in plants_with_socth:
            if plant in self.socTH_all.index:
                self.fig_socTH.add_trace(
                    go.Scatter(
                        x=self.socTH_all.loc[plant, :].index,
                        y=self.socTH_all.loc[plant, :] / 1000,  # GWh
                        mode=mode,
                        name=f"{self.scenario_name}_{plant}",
                    )
                )

        # # add a trace that sums up the soc of all plants that are in self.plant_list and self.soc_all.index
        # self.fig_socTH.add_trace(
        #     go.Scatter(
        #         x=self.socTH_all.loc[plants_with_socth, :].sum(axis=0).index,
        #         y=self.socTH_all.loc[plants_with_socth, :].sum(axis=0)/1000, # GWh
        #         mode=mode,
        #         name=f"{self.scenario_name} All",
        #     )
        # )

        # plot soc plot for assets that are of technology pit
        plants_with_socpit = [
            plant for plant in self.socTH_all.index if "PTES" in self.Map_plantDH_tech[plant][0]
        ]

        self.fig_socTH_pit.add_trace(
            go.Scatter(
                x=self.socTH_all.loc[plants_with_socpit, :].sum(axis=0).index,
                y=self.socTH_all.loc[plants_with_socpit, :].sum(axis=0)/1000, # GWh
                mode=mode,
                name=f"{self.scenario_name}",
            )
        )

        # plot soc plot for assets that are of technology tank
        plants_with_soctank = [
            plant for plant in self.socTH_all.index if "TTES" in self.Map_plantDH_tech[plant][0]
        ]

        self.fig_socTH_tank.add_trace(
            go.Scatter(
                x=self.socTH_all.loc[plants_with_soctank, :].sum(axis=0).index,
                y=self.socTH_all.loc[plants_with_soctank, :].sum(axis=0)/1000, # GWh
                mode=mode,
                name=f"{self.scenario_name}",
            )
        )
        
         
    def plot_soc_dual(self, mode):
        # plants with soc are defined as plants that are in self.plant_list and self.soc_all.index
        soc_data = self.soc_dual_all
        plants_with_soc = [
            plant for plant in self.plant_list if plant in soc_data.index
        ]

        for plant in plants_with_soc:
            if plant in soc_data.index:
                self.fig_soc_dual.add_trace(
                    go.Scatter(
                        x=soc_data.loc[plant, :].index,
                        y=soc_data.loc[plant, :],
                        mode=mode,
                        name=f"{self.scenario_name}_{plant}",
                    )
                )

    def plot_socth_dual(self, mode, NodeDH):
        socth_data = self.socth_dual_all

        for plant in socth_data.index:
            if plant in self.Map_nodeDH_plantDH[NodeDH[0]]:
                self.fig_socth_dual.add_trace( # type: ignore
                    go.Scatter(
                    x=socth_data.loc[plant, :].index,
                    y=socth_data.loc[plant, :],
                    mode=mode,
                    name=f"{self.scenario_name}_{plant}",
                )
            )

    def plot_thermal_storage_level(self, mode):
        for building_archetype in self.th_sl_all.index:
            self.fig_th_sl.add_trace(go.Scatter(
            x=self.th_sl_all.loc[building_archetype, :].index, 
            y=self.th_sl_all.loc[building_archetype, :],
            mode=mode,
            name=building_archetype
    ))
        
        new_fig_weekly = util_vis.aggregate_figure_by_time(self.fig_th_sl, mode_agg="weekly", agg_func="mean", weekly_anchor="W-SUN", scenario_name = self.scenario_name)
        new_fig_weekly.show()

        self.fig_th_sl.update_xaxes(range=self.plot_range)
        self.fig_th_sl.update_layout(title="Thermal storage level")
        self.fig_th_sl.update_layout(yaxis_title="MWh")
        self.fig_th_sl.update_layout(xaxis_title="Time [hour in year]")
        self.fig_th_sl.update_layout(yaxis=dict(tickformat=".0f"))
        self.fig_th_sl.show()
           
            
    def plot_thermal_storage_level_rel(self, mode):
        for building_archetype in self.th_sl_all.index:
            # in the case of multiple scenarios, the time series detection has a problem, as a quick fix, added the lines below
            try:
                y_values = self.th_sl_all.loc[building_archetype, :]/self.BA_th_lim.loc[building_archetype]['positive_capacity_[MWh]'] * self.heat_flexibility_Kelvin +22 #type: ignore
            except:
                y_values = self.th_sl_all.loc[building_archetype, :]/self.BA_th_lim.loc[building_archetype]['positive_capacity_[MWh]'].iloc[0] * self.heat_flexibility_Kelvin +22 #type: ignore

            self.fig_th_sl_rel.add_trace(go.Scatter(
            x=self.th_sl_all.loc[building_archetype, :].index, 
            y= y_values, # normilize the values and shift to have 22°C as mean
            mode=mode,
            name=building_archetype
    ))
        new_fig_weekly = util_vis.aggregate_figure_by_time(self.fig_th_sl_rel, mode_agg="weekly", agg_func="mean", weekly_anchor="W-SUN", scenario_name = self.scenario_name)
        new_fig_weekly.show()
        
        self.fig_th_sl_rel.update_xaxes(range=self.plot_range)
        self.fig_th_sl_rel.update_layout(title="Thermal storage level")
        self.fig_th_sl_rel.update_layout(yaxis_title="°C")
        self.fig_th_sl_rel.update_layout(xaxis_title="Time [hour in year]")
        self.fig_th_sl_rel.update_layout(yaxis=dict(tickformat=".1f"))
        self.fig_th_sl_rel.show() 
        
    def plot_v2g(self, mode):
        self.fig_v2g = go.Figure()
        v2g_vehicle = "V2G_CH"
        # plot outflow of v2g vehicles
        self.fig_v2g.add_trace(go.Scatter(
        x=self.v2g_outflow_all.loc[v2g_vehicle, :].index,
        y=self.v2g_outflow_all.loc[v2g_vehicle, :],
        mode=mode,
        name="outflow" + v2g_vehicle
        ))

        # plot generation of v2g vehicle
        self.fig_v2g.add_trace(go.Scatter(
            x=self.generation_all.loc[v2g_vehicle, :].index,
            y=self.generation_all.loc[v2g_vehicle, :],
            mode=mode,
            name="generation"
        ))

        # plot consumption of v2g vehicle
        self.fig_v2g.add_trace(go.Scatter(
            x=self.demand_flxbl_all.loc[v2g_vehicle, :].index,
            y=self.demand_flxbl_all.loc[v2g_vehicle, :],
            mode=mode,
            name="consumption"
        ))

        # plot soc of v2g vehicle
        self.fig_v2g.add_trace(go.Scatter(
            x=self.soc_all.loc[v2g_vehicle, :].index,
            y=self.soc_all.loc[v2g_vehicle, :],
            mode=mode,
            name="soc"
        ))

        # update the layout of the figure
        self.fig_v2g.update_layout(title=f"V2G - {self.scenario_name}")
        self.fig_v2g.update_layout(yaxis_title="MWh")
        self.fig_v2g.update_layout(xaxis_title="Time")

        self.fig_v2g.show()
        self.fig_v2g.write_html(f"plots/V2G_{self.scenario_name}.html")

    def plot_investments(self, mode):
        # plot investments
        # get the list of investable plants from self.output_dir/P_allinv.csv into a list
        investable_plants_list = pd.read_csv(f"{ self.output_dir}/P_allinv.csv", index_col=0).index.tolist()

        # read invested generation capacities from self.output_dir/gen_max.csv, drop the 2nd column
        gen_max = pd.read_csv(f"{ self.output_dir}/gen_max.csv", index_col=[0]).drop(columns="Scenarios")

        # keep only the investable plants
        gen_max = gen_max[gen_max.index.isin(investable_plants_list)]

        # remove duplicates from the index, keep the first occurrence (the values should be the same anyways)
        gen_max = gen_max[~gen_max.index.duplicated(keep='first')]

        # use self.Map_node_plant to separate plants in CH00, that is if gen_max.index is in self.Map_node_plant["CH00"]
        # then the plant is in CH00
        gen_max_CH00 = gen_max[gen_max.index.isin(self.Map_node_plant["CH00"])]
        gen_max = gen_max[~gen_max.index.isin(self.Map_node_plant["CH00"])]

        # Aggregate similar technologies in CH00
        for tech, label in [("pvrf", "PV CH"), ("windon", "Wind CH"), ("battery", "Battery CH")]:
            index_mask = gen_max_CH00.index.str.contains(tech)
            tech_sum = gen_max_CH00.loc[index_mask, :].sum()
            gen_max_CH00 = gen_max_CH00[~index_mask]
            gen_max_CH00.loc[label, :] = tech_sum

        # merge back gen_max_CH00 into gen_max
        gen_max = pd.concat([gen_max_CH00, gen_max])

        x_label = self.scenario_name
        # plot the generation capacities of the investable plants as a stacked bar plot
        for plant in gen_max.index:
            if gen_max.loc[plant, :].values[0] > 0.5:	
                color = self.invest_color_mapping.get(plant, "gray")  # Default color if not found in mapping
                self.fig_investments.add_trace(
                    go.Bar(
                        x=[x_label] * len(gen_max.columns),  # Assign the unique x-label
                        y=gen_max.loc[plant, :],
                        name=plant,
                        marker_color=color,  # Assign fixed color   
                    )
                )
        # Set layout to stacked mode
        self.fig_investments.update_layout(
            barmode="stack",  # This ensures bars are stacked
        )

    def plot_all(self, mode):
        if PLOT_PRICE:
            print("Plotting price time series...")
            self.plot_price(mode)

        if PLOT_SUM_GEN:
            print("Plotting total generation time series...")
            self.plot_sum_gen(mode)
        
        if PLOT_SUM_DEM:
            print("Plotting total demand time series...")
            self.plot_sum_dem(mode)

        if not self.sum_assets:
            if PLOT_IND_GEN:
                print("Plotting individual generation time series...")
                self.plot_ind_gen(mode)
            if PLOT_IND_DEM:
                print("Plotting individual demand time series...")
                self.plot_ind_dem(mode)
        else:
            if PLOT_AGG_GEN:
                print("Plotting aggregated generation per technology...")
                self.plot_agg_gen(mode)
            if PLOT_AGG_DEM:
                print("Plotting aggregated demand per technology...")
                self.plot_agg_dem(mode)

        if PLOT_EXPORT_IMPORT:
            print("Plotting export and import time series...")
            self.plot_export_import(mode)
        
        if PLOT_SOC:
            self.plot_soc(mode)
        
        if PLOT_SOC_DUAL:
            self.plot_soc_dual(mode)
        
        # self.plot_socth_dual(mode)

        print("All plots successfully created...")

    def show_all_plots(self):
        if PLOT_PRICE:
            self.fig_price.update_xaxes(range=self.plot_range)
            self.fig_price.update_layout(title="Price")
            self.fig_price.update_layout(yaxis_title="CHF/MWh")
            self.fig_price.update_layout(xaxis_title="Time [hour in year]")
            self.fig_price.show()

        if PLOT_SUM_GEN:
            self.fig_sum_gen.update_xaxes(range=self.plot_range)
            self.fig_sum_gen.update_layout(title="Generation (total)")
            self.fig_sum_gen.update_layout(yaxis_title="MWh")
            self.fig_sum_gen.update_layout(xaxis_title="Time [hour in year]")
            self.fig_sum_gen.update_layout(yaxis=dict(tickformat=".0f"))
            self.fig_sum_gen.show()

        if PLOT_SUM_DEM:
            self.fig_sum_dem.update_xaxes(range=self.plot_range)
            self.fig_sum_dem.update_layout(title="Demand")
            self.fig_sum_dem.update_layout(yaxis_title="MWh")
            self.fig_sum_dem.update_layout(xaxis_title="Time [hour in year]")
            self.fig_sum_dem.update_layout(yaxis=dict(tickformat=".0f"))
            self.fig_sum_dem.show()

        if not self.sum_assets:
            if PLOT_IND_GEN:
                self.fig_ind_gen.update_xaxes(range=self.plot_range)
                self.fig_ind_gen.update_layout(title="Individual generation")
                self.fig_ind_gen.update_layout(yaxis_title="MWh")
                self.fig_ind_gen.update_layout(xaxis_title="Time [hour in year]")
                self.fig_ind_gen.update_layout(yaxis=dict(tickformat=".0f"))
                self.fig_ind_gen.show()

            if PLOT_IND_DEM:
                self.fig_ind_dem.update_xaxes(range=self.plot_range)
                self.fig_ind_dem.update_layout(title="Individual demand")
                self.fig_ind_dem.update_layout(yaxis_title="MWh")
                self.fig_ind_dem.update_layout(xaxis_title="Time [hour in year]")
                self.fig_ind_dem.update_layout(yaxis=dict(tickformat=".0f"))
                self.fig_ind_dem.show()

        else:
            if PLOT_AGG_GEN:
                self.fig_agg_gen.update_xaxes(range=self.plot_range)
                self.fig_agg_gen.update_layout(title="Aggregated generation per technology")
                self.fig_agg_gen.update_layout(yaxis_title="MWh")
                self.fig_agg_gen.update_layout(xaxis_title="Time [hour in year]")
                self.fig_agg_gen.update_layout(yaxis=dict(tickformat=".0f"))
                self.fig_agg_gen.show()

            if PLOT_AGG_DEM:
                self.fig_agg_dem.update_xaxes(range=self.plot_range)
                self.fig_agg_dem.update_layout(title="Aggregated demand per technology")
                self.fig_agg_dem.update_layout(yaxis_title="MWh")
                self.fig_agg_dem.update_layout(xaxis_title="Time [hour in year]")
                self.fig_agg_dem.update_layout(yaxis=dict(tickformat=".0f"))
                self.fig_agg_dem.show()

        if PLOT_EXPORT_IMPORT:
            self.fig_export_import.update_xaxes(range=self.plot_range)
            self.fig_export_import.update_layout(title="Import (export is negative)")
            self.fig_export_import.update_layout(yaxis_title="MWh")
            self.fig_export_import.update_layout(xaxis_title="Time [hour in year]")
            self.fig_export_import.update_layout(yaxis=dict(tickformat=".0f"))
            self.fig_export_import.show()

        if PLOT_SOC:
            self.fig_soc.update_xaxes(range=self.plot_range)
            self.fig_soc.update_layout(title="State of charge")
            self.fig_soc.update_layout(yaxis_title="TWh")
            self.fig_soc.update_layout(xaxis_title="Time [hour in year]")
            self.fig_soc.update_layout(yaxis=dict(tickformat=".0f"))
            self.fig_soc.show()

        if PLOT_SOC_THERMAL:
            self.fig_socTH.update_xaxes(range=self.plot_range)
            self.fig_socTH.update_layout(title="State of charge - Thermal storage")
            self.fig_socTH.update_layout(yaxis_title="GWh")
            self.fig_socTH.update_layout(xaxis_title="Time [hour in year]")
            self.fig_socTH.update_layout(yaxis=dict(tickformat=".0f"))
            self.fig_socTH.show()

            self.fig_socTH_pit.update_xaxes(range=self.plot_range)
            self.fig_socTH_pit.update_layout(title="State of charge - All Pit Storage - Aggregated")
            self.fig_socTH_pit.update_layout(yaxis_title="GWh")
            self.fig_socTH_pit.update_layout(xaxis_title="Time [hour in year]")
            self.fig_socTH_pit.update_layout(yaxis=dict(tickformat=".0f"))
            self.fig_socTH_pit.show()

            self.fig_socTH_tank.update_xaxes(range=self.plot_range)
            self.fig_socTH_tank.update_layout(title="State of charge - All Tank Storage - Aggregated")
            self.fig_socTH_tank.update_layout(yaxis_title="GWh")
            self.fig_socTH_tank.update_layout(xaxis_title="Time [hour in year]")
            self.fig_socTH_tank.update_layout(yaxis=dict(tickformat=".0f"))
            self.fig_socTH_tank.show()

        if PLOT_SOC_DUAL:
            self.fig_soc_dual.update_xaxes(range=self.plot_range)
            self.fig_soc_dual.update_layout(title="Opp. cost of storage")
            self.fig_soc_dual.update_layout(yaxis_title="CHF/MWh")
            self.fig_soc_dual.update_layout(xaxis_title="Time [hour in year]")
            self.fig_soc_dual.update_layout(yaxis=dict(tickformat=".0f"))
            self.fig_soc_dual.show()

        if PLOT_SOC_THERMAL_DUAL:
            self.fig_socth_dual.update_xaxes(range=self.plot_range)
            self.fig_socth_dual.update_layout(title="Opp. cost of thermal storage")
            self.fig_socth_dual.update_layout(yaxis_title="CHF/MWh")
            self.fig_socth_dual.update_layout(xaxis_title="Time [hour in year]")
            self.fig_socth_dual.update_layout(yaxis=dict(tickformat=".0f"))
            self.fig_socth_dual.show()

        if PLOT_INVESTMENTS:
            self.fig_investments.update_layout(title=f"Investments")
            self.fig_investments.update_layout(yaxis_title="MW")
            self.fig_investments.update_layout(xaxis_title="Plant")
            self.fig_investments.show()
            self.fig_investments.to_html(f"plots/Investments_{self.scenario_name}.html")


    def export_all_plots_to_html(self):  # 8760
        # if the folder plots do not exist, create it
        if not os.path.exists("plots"):
            os.makedirs("plots")

        if PLOT_DISPATCH:
            self.fig_dispatch.update_xaxes(range=self.plot_range)
            self.fig_dispatch.update_layout(title="Dispatch")
            self.fig_dispatch.write_html(f"plots/Dispatch_{self.scenario_name}.html")

        if PLOT_PRICE:
            self.fig_price.update_xaxes(range=self.plot_range)
            self.fig_price.update_layout(title="Price")
            self.fig_price.write_html(f"plots/Price_{self.scenario_name}.html")

        if PLOT_SUM_GEN:
            self.fig_sum_gen.update_xaxes(range=self.plot_range)
            self.fig_sum_gen.update_layout(title="Generation")
            self.fig_sum_gen.write_html(f"plots/Gen_{self.scenario_name}.html")

        if PLOT_SUM_DEM:
            self.fig_sum_dem.update_xaxes(range=self.plot_range)
            self.fig_sum_dem.update_layout(title="Demand")
            self.fig_sum_dem.write_html(f"plots/Dem_{self.scenario_name}.html")

        if not self.sum_assets:
            if PLOT_IND_GEN:
                self.fig_ind_gen.update_xaxes(range=self.plot_range)
                self.fig_ind_gen.update_layout(title="Individual generation")
                self.fig_ind_gen.write_html(f"plots/Ind_gen_{self.scenario_name}.html")

            if PLOT_IND_DEM:
                self.fig_ind_dem.update_xaxes(range=self.plot_range)
                self.fig_ind_dem.update_layout(title="Individual demand")
                self.fig_ind_dem.write_html(f"plots/Ind_dem_{self.scenario_name}.html")

        else:
            if PLOT_AGG_GEN:
                self.fig_agg_gen.update_xaxes(range=self.plot_range)
                self.fig_agg_gen.update_layout(title="Aggregated generation")
                self.fig_agg_gen.write_html(f"plots/Agg_gen_{self.scenario_name}.html")

            if PLOT_AGG_DEM:
                self.fig_agg_dem.update_xaxes(range=self.plot_range)
                self.fig_agg_dem.update_layout(title="Aggregated demand")
                self.fig_agg_dem.write_html(f"plots/Agg_dem_{self.scenario_name}.html")

        if PLOT_EXPORT_IMPORT:
            self.fig_export_import.update_xaxes(range=self.plot_range)
            self.fig_export_import.update_layout(title="Export and import")
            self.fig_export_import.write_html(f"plots/Exp_imp_{self.scenario_name}.html")

        if PLOT_SOC:
            self.fig_soc.update_xaxes(range=self.plot_range)
            self.fig_soc.update_layout(title="State of charge")
            self.fig_soc.write_html(f"plots/SOC_{self.scenario_name}.html")

        if PLOT_SOC_THERMAL:
            self.fig_socTH.update_xaxes(range=self.plot_range)
            self.fig_socTH.update_layout(title="State of charge - Thermal")
            self.fig_socTH.write_html(f"plots/SOC_thermal_{self.scenario_name}.html")

        if PLOT_SOC_DUAL:
            self.fig_soc_dual.update_xaxes(range=self.plot_range)
            self.fig_soc_dual.update_layout(title="Opp. cost of storage")
            self.fig_soc_dual.write_html(f"plots/SOC_dual_{self.scenario_name}.html")

        if PLOT_SOC_THERMAL_DUAL:
            self.fig_socth_dual.update_xaxes(range=self.plot_range)
            self.fig_socth_dual.update_layout(title="Opp. cost of thermal storage")
            self.fig_socth_dual.write_html(f"plots/SOC_thermal_dual_{self.scenario_name}.html")

        if PLOT_THERMAL_STORAGE_LEVEL:
            self.fig_th_sl.update_xaxes(range=self.plot_range)
            self.fig_th_sl.update_layout(title="Thermal storage level")
            self.fig_th_sl.write_html(f"plots/Th_sl_{self.scenario_name}.html")

        if PLOT_THERMAL_STORAGE_LEVEL_REL:
            self.fig_th_sl_rel.update_xaxes(range=self.plot_range)
            self.fig_th_sl_rel.update_layout(title="Thermal storage level (relative)")
            self.fig_th_sl_rel.write_html(f"plots/Th_sl_rel_{self.scenario_name}.html")

        if PLOT_INVESTMENTS:
            self.fig_investments.write_html(f"plots/Investments_{self.scenario_name}.html")

        print("All plots sucessfully exported...")



plotter = DemandTimeSeriesPlotter(target_node)
for i_scenario in scenarios_to_plot:
    plotter.output_dir = "output/" + i_scenario + "/"


    sample_df_to_get_parameters = pd.read_csv(plotter.output_dir + "gen.csv")

    if "Scenarios" in sample_df_to_get_parameters.columns:
        scenarios_list = sample_df_to_get_parameters.loc[:, "Scenarios"].unique().tolist()
    else:
        scenarios_list = [i_scenario]
    
    for i_scenario in scenarios_list:
        plotter.scenario_name = i_scenario
        plotter.load_data()
        
        if PLOT_INVESTMENTS:
            plotter.plot_investments(mode="lines")
        
        if PLOT_DISPATCH:
            data_dict = plotter.plot_dispatch(mode="lines")
            data_df = pd.DataFrame(data_dict)
        
        # following items are specific to the CH00 node
        if plotter.target_node == "CH00":
            if PLOT_V2G:
                plotter.plot_v2g(mode="lines")
            if PLOT_THERMAL_STORAGE_LEVEL:
                plotter.plot_thermal_storage_level(mode="lines")
            if PLOT_THERMAL_STORAGE_LEVEL_REL:
                plotter.plot_thermal_storage_level_rel(mode="lines")

            # get the names of all districting heating nodes (NodeDH)
            all_NodeDH = list(plotter.consumptionDH_all.index)

            if PLOT_THERMAL_DISPATCH:
                nodes_for_plotting = all_NodeDH if PLOT_DISPATCH_ALL_NODES else [n for n in all_NodeDH if DH_NODE_DEFAULT in n] 
                for node in nodes_for_plotting:
                    plotter.plot_dispatchDH(mode="lines", NodeDH=[node])
                    if PLOT_SOC_THERMAL:
                        plotter.plot_socTH(mode="lines", NodeDH=[node])

            if PLOT_THERMAL_DISPATCH_DUALS:
                nodes_for_duals = all_NodeDH if PLOT_DUALS_ALL_NODES else [n for n in all_NodeDH if DH_NODE_DEFAULT in n]
                for node in nodes_for_duals:
                    plotter.plot_dispatchDH_duals(mode="lines", NodeDH=[node])
                    if PLOT_SOC_THERMAL_DUAL:
                        plotter.plot_socth_dual(mode="lines", NodeDH=[node])

        plotter.plot_all(mode="lines")
        plotter.export_all_plots_to_html()

plotter.show_all_plots()
plotter.export_all_plots_to_html()