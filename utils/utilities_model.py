from io import StringIO
import os
from pyomo.environ import *


# Extract the objective function directly
def get_objective_string(model):
    for obj in model.component_objects(Objective, active=True):
        return f"Objective: {obj.name}\nSense: {obj.sense}\nExpression:\n{obj.expr}"


def export_model_to_txt(suffix, model, scenario_name):
    """Exports the model to a text file"""
    stream = StringIO()
    model.pprint(ostream=stream)
    dir_path = "output\\" + scenario_name

    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    with open(dir_path + "\\model_" + suffix + ".txt", "w") as f:
        f.write(stream.getvalue())


def export_model_obj(suffix, model, scenario_name):
    # Save the extracted objective function to a file
    dir_path = "output\\" + scenario_name
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    with open(dir_path + "\\objective_" + suffix + ".txt", "w") as f:
        f.write(get_objective_string(model)) #type: ignore