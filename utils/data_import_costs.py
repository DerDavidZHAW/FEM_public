from input.cost_operation_invest_data import cost_component
from model.mappings import Map_node_country
from model.read_settings import read_scenario_settings
import numpy as np
from model.structural_parameters import Map_plant_tech_cost_component, fuel_limited_CH_list
import input.cost_operation_invest_data as cost_params


def get_cost_component(tech, year, cost_type, scenario_name):
    """
    Returns a certain cost component for a given technology and year
    tech: technology  (should be plant, but later mapped with Mapplanttech)
    year: year
    cost_type: can be "investment", "fixed_op", "fixed", "variable", "investment_energy", "investment_discharge"
    """
    #NOTE: the function can be improved
    
    discount_rate = 0.05   # 5% discount rate

    if cost_type == "investment_fuel_energy_cost_chfMWh": 
        amortization_years = cost_params.amortization_years_all[tech + "_fuel_storage"] # years
        investment_fuel_energy_cost = cost_component["investment_fuel_energy_cost_chfMWh"].get(tech, {}).get(year)
        if amortization_years > 0 and investment_fuel_energy_cost:
            investment_fuel_energy_cost_discounted = investment_fuel_energy_cost * (discount_rate / (1 - (1 + discount_rate) ** (-amortization_years)))
        else:
            investment_fuel_energy_cost_discounted = investment_fuel_energy_cost if investment_fuel_energy_cost else 0
        if tech=="oil":
            return investment_fuel_energy_cost
        else:
            return investment_fuel_energy_cost_discounted
    else:
        amortization_years = cost_params.amortization_years_all[tech] # years
        battery_cost_factor = read_scenario_settings(scenario_name)["battery_cost_factor"]
        cost_op_match_nexuse = read_scenario_settings(scenario_name)["cost_op_match_nexuse"]
        investment_cost = cost_component["investment_cost_chfMW"].get(tech, {}).get(year)

        if tech == "battery":
            investment_cost *= battery_cost_factor

        # write this equation : Yearly Cost = inv_cost * ( Social Interest Rate / (1 - (1 + Social Interest Rate)^(-Amortization Period) ) )
        if amortization_years > 0 and investment_cost:
            investment_cost_discounted = investment_cost * (discount_rate / (1 - (1 + discount_rate) ** (-amortization_years)))
        else:
            investment_cost_discounted = investment_cost if investment_cost else 0

        fixed_op_cost = cost_component["fixed_op_cost_chfMW"].get(tech, {}).get(year)
        om_cost = cost_component["om_cost_eurMWH"].get(tech, {}).get(year, 0)
        efficiency = cost_component["efficiency"].get(tech, {}).get(year, 1) if isinstance(cost_component["efficiency"].get(tech, {}), dict) else cost_component["efficiency"].get(tech, 1)
        emission_factor = cost_component["emission_factor"].get(tech, {}).get(year, 0) if isinstance(cost_component["emission_factor"].get(tech, {}), dict) else cost_component["emission_factor"].get(tech, 0)
        
        fuel_cost = cost_component["input_cost_scenario_ZERO"].get(tech, {}).get(year, {})/efficiency if efficiency != 0 else 0
        emission_per_mwh = emission_factor / efficiency if efficiency != 0 else 0
        co2_cost = emission_per_mwh * cost_component["input_cost_scenario_ZERO"].get("co2", {}).get(year, {})
        var_cost = om_cost + co2_cost +  fuel_cost 

        # NOTE: implied assumption below is that gas generation in CH and EU are CCS and CCGT based
        if tech in ["CCGTCCS", "gas"] :
            co2_transport_and_storage_cost = (62+98)/2 # the cost taken from https://ccuszen.eu/sites/default/files/CCUS_Network_Webinar_6_Slide_Pack.pdf#page=35.00 
            captured_to_emitted_ratio = 9 # given that capture rate is 90% and the emission rate is 10% of the captured CO2
            var_cost = var_cost + emission_per_mwh * captured_to_emitted_ratio * co2_transport_and_storage_cost


        # overwrite costs with nexuse costs (cost_op_nexuse), if cost_op_match_nexuse is True
        if cost_op_match_nexuse:
            cost_op_nexuse = { # from Table 24, Nexus-e: Interconnected Energy Systems Modelling Platform, Input Data and System Setup, Status: August 2022
                "nuclear" : 16,
                "hardcoal": 243.2,
                "lignite": 195.2,
                "gas": 112.7,
                "biomass": 8.1,
                "oil": 383.6,	
            }
            if tech in cost_op_nexuse:
                var_cost = cost_op_nexuse[tech]
            # if a technology is not in cost_op_nexuse, the original var_cost is used.

        # NOTE to Raul: in the original formulation, the var_cost was calculated as follows:
        # old = cost_component["om_cost_eurMWH"].get(tech, {}) + (
        #     cost_component["input_cost_scenario_ZERO"].get("co2", {}).get(year, {})
        #     * cost_component["emission_factor"].get(tech, {})
        #     / cost_component["efficiency"].get(tech, {})
        # )
        # which is not correct.

        if cost_type == "investment":
            return investment_cost_discounted
        elif cost_type == "fixed_op":
            return fixed_op_cost
        elif cost_type == "om":
            return om_cost
        elif cost_type == "var":
            return var_cost
        elif cost_type == "emission_factor_per_MWh":
            # Returns emission factor in tCO2/MWh of output (already divided by efficiency)
            return emission_per_mwh
        elif cost_type in ("investment_energy", "investment_discharge"):
            if cost_type == "investment_energy":
                investment_energy_cost = cost_component["investment_energy_cost_chfMWh"].get(tech, {}).get(year, 0)
            else:  # investment_discharge
                investment_energy_cost = cost_component["investment_cost_charge_chfMW"].get(tech, {}).get(year, 0)

            if tech == "battery":
                investment_energy_cost *= battery_cost_factor

            if amortization_years > 0 and investment_energy_cost:
                investment_energy_cost_discounted = investment_energy_cost * (discount_rate / (1 - (1 + discount_rate) ** (-amortization_years)))
            else:
                investment_energy_cost_discounted = investment_energy_cost if investment_energy_cost else 0

            # NOTE: the lines below should not be used in the model because now fuel tracking is added. Equivalent lines should be added to fuel tracking.
            if tech == "oil": # NOTE: this needs to be automated (detecting the technologies that have pre-installed capacity and annual operation costs are already calculated)
                return investment_energy_cost
            else:
                return investment_energy_cost_discounted
        else:
            return np.nan


def create_tech_cost_dict(tech_list, cost_type, year, scenario_name):
    tech_cost = {}
    for tech in tech_list:
        cost = get_cost_component(tech, year, cost_type, scenario_name)
        tech_cost[tech] = cost
    return tech_cost


def read_op_cost_calibration(run_year):
    """Reads the op_cost_calibration.csv file and returns a dictionary op_cost_n_tech_calibration[node, tech] with the calibration values"""
    op_cost_country_tech_calibration = {}
    op_cost_n_tech_calibration = {}

    dir = f"input/op_cost_calibration_{run_year}.csv"

    # read the file as a dictionary op_cost_country_tech_calibration[country, tech] = calibration value
    with open(dir, "r") as f:
        lines = f.readlines()
        header = lines[0].strip().split(",")
        for line in lines[1:]:
            line = line.strip().split(",")
            country = line[0]
            for i, tech in enumerate(header[1:]):
                op_cost_country_tech_calibration[(country, tech)] = float(line[i + 1])

    # map op_cost_country_tech_calibration from countries to nodes in dictionary tech_list_in_calibration
    tech_list_in_calibration = list(
        set([key[1] for key in dict.keys(op_cost_country_tech_calibration)])
    )

    for node in Map_node_country:
        for tech in tech_list_in_calibration:
            op_cost_n_tech_calibration[(node, tech)] = op_cost_country_tech_calibration[
                (Map_node_country[node], tech)
            ]

    return op_cost_n_tech_calibration


def data_import_costs_fcn(scenario_name):

    run_year = read_scenario_settings((scenario_name))['run_year']

    # for every technology -------------------------------------------------------
    # cost_data_inv_gen_slp = {"pv": 15,    "gas": 10, "limited_energy": 100000000, "battery": 10, "bt": 0,  "dam":10, "psp_open":10, "psp_close":10, "v1g": 0, "v2g": 0, "hp": 0, "chp": 10000, "oil":1000, "dsr": 10000, "hardcoal":10000, "nuclear": 100000, "lignite": 100000}
    # NOTE: update, if intercept of investment cost is not zero
    cost_data_inv_gen_slp = create_tech_cost_dict(
        list(dict.keys(Map_plant_tech_cost_component)), "investment", run_year, scenario_name
    )

    # costs - operation
    # cost_data_opr_int = {"pv": 0,    "gas": 0, "limited_energy": 10, "battery": 0,  "bt": 0, "dam":0, "psp_open": 0, "psp_close": 0, "v1g": 0, "v2g": 0, "hp": 0, "chp": 10, "oil":100, "dsr": 1, "hardcoal":50, "nuclear": 1, "lignite": 70}
    # cost_data_opr_slp = {"pv": 0,    "gas": 5, "limited_energy": 10, "battery": 0,  "bt": 0, "dam":0, "psp_open": 0, "psp_close": 0, "v1g": 0, "v2g": 0, "hp": 0, "chp": 10, "oil":100, "dsr": 1, "hardcoal":50, "nuclear": 1, "lignite": 70}

    cost_data_opr_int = {tech: 0 for tech in dict.keys(Map_plant_tech_cost_component)}
    cost_data_opr_slp = create_tech_cost_dict(
        list(dict.keys(Map_plant_tech_cost_component)), "var", run_year, scenario_name
    )

    cost_data_inv_e_slp = create_tech_cost_dict(
        list(dict.keys(Map_plant_tech_cost_component)), "investment_energy", run_year, scenario_name
    )

    cost_data_inv_discharge_slp = create_tech_cost_dict(
        list(dict.keys(Map_plant_tech_cost_component)), "investment_discharge", run_year, scenario_name
    )

    # calibration of operational costs for every node and technology
    # op_cost_n_tech_calibration[node, tech] = calibration value (values taken from SA calibration process)
    op_cost_n_tech_calibration = read_op_cost_calibration(run_year)

    cost_data_inv_fuel_storage_slp = create_tech_cost_dict(
        fuel_limited_CH_list, "investment_fuel_energy_cost_chfMWh", run_year, scenario_name
    )

    # emission factor per MWh of output (tCO2/MWh_elec), already divided by efficiency
    emission_factor_per_MWh = create_tech_cost_dict(
        list(dict.keys(Map_plant_tech_cost_component)), "emission_factor_per_MWh", run_year, scenario_name
    )

    return cost_data_inv_gen_slp, cost_data_opr_int, cost_data_opr_slp, op_cost_n_tech_calibration, cost_data_inv_e_slp, cost_data_inv_fuel_storage_slp, cost_data_inv_discharge_slp, emission_factor_per_MWh
