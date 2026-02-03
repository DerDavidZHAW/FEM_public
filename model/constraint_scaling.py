# Central per-constraint row scaling map.
# Keys correspond to the Constraint component names defined in the model,
# values are positive scaling factors applied uniformly to both sides of each row.
# Default is 1.0 everywhere; tune selectively to improve numerical conditioning.

constraint_scaling = {
    # Core power system constraints
    'energy_balance': 1.0,
    'generation_limit': 1e-1,
    'storage_soc': 1.0,
    'storage_start_condition': 1e-3,
    'storage_rate_limit': 1e-2,
    'p_max_limit': 1.0,
    'storage_soc_limit': 1e-3,  # Norwegian PSP has ~58 TWh capacity → scaled to ~58 GWh
    'storage_total_fuel_limit': 1.0,
    'lostload_limit': 1.0,
    'curtailment_limit': 1e-3,
    'energy_limit': 1e-1,
    'energy_shift_limit_dsr_daily': 1.0,
    'dsr_daily_balance': 1.0,
    'gen_energy_max_limit_constraint': 1.0,
    'gen_max_limit_constraint': 1e-3,
    'lineATClimit': 1.0,
    'infeedgen_fix': 1.0,

    # Fuel tracking and limits
    'fuel_consumption_tracking': 1.0,
    'plant_fuel_consumption_tracking_CH': 1.0,
    'plant_fuel_consumption_tracking_CH_DH': 1.0,
    'fuel_limit_annual': 1e-3,

    # Multi-scenario equality constraints
    'gen_max_equal': 1.0,
    'pmp_max_equal': 1.0,
    'gen_energy_max_equal': 1.0,
    'gen_energy_max_equal2': 1.0,
    'fuel_storage_capacity_annual_equal': 1.0,
    'genTh_max_equal': 1.0,
    'gen_energyTh_max_equal': 1.0,

    # District heating
    'generationTh_limit': 1.0,
    'heat_electric_profile_resistiveheater': 1.0,
    'heat_electric_profile_heatpump': 1.0,
    'heat_electric_profile_CHP': 1.0,
    'energy_balancethermal': 1.0,
    'storageTh_soc': 1.0,
    'storageTh_soc_limit': 1.0,
    'storageTh_rate_limit': 1.0,
    'pumpTh_max_leq_genTh_max': 1.0,
    'dsrth_thermal_energy_dev_tracking': 1.0,
    'dsrTh_dev_limit': 1.0,
    'dsrTh_dev_week_start_zero': 1.0,
    'dsrTh_dev_week_end_zero': 1.0,
    'dsrTh_dev_weekly_average_temp': 1.0,
    'inflexble_demandTh_share': 1.0,
    'gen_energyTh_max_limit_constraint': 1e-3,
    'genTh_max_limit_constraint': 1e-3,
    'fix_storage_to_charge_ratio_PTES': 1.0,

    # EV and V2G
    'ev_consumption_weekly_sum': 1.0,
    'ev_consumption_hourly_rate': 1.0,
    'ev_inflexible_minimum': 1.0,
    'v2g_consumption_hourly_rate': 1.0,
    'v2g_generation_hourly_rate': 1.0,

    # Buildings
    'building_heat_demand': 1e2,
    'building_weekly_average': 1.0,
    'max_heating_capacity': 1.0,

    # Fuel storage investment
    'fuel_storage_capacity_annual_investment_limit': 1.0,

    # Resistive heater cap
    'resistive_heater_investment_cap': 1.0,

    # Misc
    'pump_less_than_gen_constraint': 1.0,
    'consumer_import': 1.0,
    'consumer_export': 1.0,

    # Central constraints (components_central.py)
    'consume_tot_limit': 1e-3,
}