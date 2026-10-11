"""Unit test for add_ev_plants (data_prep/data_import_TYNDP.py).

data_import_TYNDP_fcn runs once per sub-scenario and adds the flexible-EV and V2G plants to
shared lists each time; they must be listed once however many sub-scenarios are imported.
"""
from data_prep.data_import_TYNDP import add_ev_plants


def test_ev_plants_are_added_once_however_many_sub_scenarios_are_imported():
    plants, outflow_plants, map_plant_node, map_plant_tech = ["CH00_gas"], [], {}, {}
    for _ in range(3):  # one call per sub-scenario
        add_ev_plants("V2G_CH", plants, outflow_plants, map_plant_node, map_plant_tech)
    assert plants == ["CH00_gas", "CH00_EV_flex", "V2G_CH"]
    assert outflow_plants == ["V2G_CH"]
    assert map_plant_node == {"CH00_EV_flex": "CH00", "V2G_CH": "CH00"}
    assert map_plant_tech == {"CH00_EV_flex": "ev_flex", "V2G_CH": "v2g"}
