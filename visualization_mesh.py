"""
This is the main script to run the visualization for the mesh plots (used e.g. for cheap robust papers).
It defines the path to the aggregated results folder and then calls the specific plotting scripts.
"""

# Define the path to the aggregated results folder
# This is the only line you should need to change.
directory_path = "output/aggregated/cheap_rob_all/"

# --- Run the plotting scripts ---
# You can comment or uncomment the scripts you want to run.

print("Running generation difference visualization...")
from visualization.visualization_mesh_generation import plot_generation_diff
plot_generation_diff(directory_path)

print("Running capacity visualization...")
from visualization.visualization_mesh_capacities import plot_capacities_mesh
plot_capacities_mesh(directory_path)

print("Visualizations complete.")
