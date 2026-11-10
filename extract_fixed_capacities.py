"""
Extract fixed capacities for MIP3 scenarios.
"""
import pandas as pd
import numpy as np

print('='*80)
print('FIXED CAPACITIES OVERVIEW FOR MIP3 SCENARIOS')
print('='*80)

# Read scenario settings
scen = pd.read_csv('scenarios/scen_to_run_STORSUPPORT.csv', index_col=0)

# Get years for 2035 and 2050 scenarios
scen_2035 = [c for c in scen.columns if '2035' in c]
scen_2050 = [c for c in scen.columns if '2050' in c]

print('\n' + '='*80)
print('1. PUMPED HYDRO STORAGE')
print('='*80)
# Read PECD hydro data
hydro_pecd = pd.read_csv('input/hydro_PECD/PECD_EERA2021_reservoir_pumping_2030_table_representative_plants.csv')
psp_pump = hydro_pecd[(hydro_pecd['variable'] == 'pumping_cap_MW') & (hydro_pecd['name'] == 'large_psp')]['value'].values[0]

pump_2035 = float(scen.loc['pump_capacity_GW', scen_2035[0]])
pump_2050 = float(scen.loc['pump_capacity_GW', scen_2050[0]])

print(f'\nBase PECD pumping (large_psp): {abs(psp_pump)/1000:.2f} GW')
print(f'\nScenario settings for pump_capacity_GW (added to PECD base):')
print(f'  2035 scenarios: {pump_2035:.2f} GW')
print(f'  2050 scenarios: {pump_2050:.2f} GW')
print(f'\n=> Total pumped hydro capacity:')
print(f'   2035: {abs(psp_pump)/1000 + pump_2035:.2f} GW (approx.)')
print(f'   2050: {abs(psp_pump)/1000 + pump_2050:.2f} GW (approx.)')
print('\nNote: The model allocates pump capacity to CH00 region only (not per CH01-CH07)')

print('\n' + '='*80)
print('2. HYDRO DAMS (Reservoirs)')
print('='*80)
gen_large_psp = hydro_pecd[(hydro_pecd['variable'] == 'gen_cap_MW') & (hydro_pecd['name'] == 'large_psp')]['value'].values[0]
gen_med_res = hydro_pecd[(hydro_pecd['variable'] == 'gen_cap_MW') & (hydro_pecd['name'] == 'medium_reservior')]['value'].values[0]
gen_small_res = hydro_pecd[(hydro_pecd['variable'] == 'gen_cap_MW') & (hydro_pecd['name'] == 'small_reservior')]['value'].values[0]

print('\nFrom PECD data (constant across 2035/2050):')
print(f'  - large_psp (dam+pumped):  {gen_large_psp/1000:.2f} GW')
print(f'  - medium_reservior:        {gen_med_res/1000:.2f} GW')
print(f'  - small_reservior:         {gen_small_res/1000:.2f} GW')
print(f'  ----------------------------------------')
print(f'  Total generation capacity: {(gen_large_psp+gen_med_res+gen_small_res)/1000:.2f} GW')
print('\nNote: Allocated to CH00 region only (not per CH01-CH07)')

print('\n' + '='*80)
print('3. RUN OF RIVER')
print('='*80)
ror = pd.read_csv('input/hydro_PECD/PECD_EERA2021_ROR_2030_table.csv')
ch_ror = ror[ror['area'] == 'CH00']['cap_MW'].values[0]
print(f'\nFrom PECD data: {ch_ror/1000:.2f} GW')

ror_2035 = float(scen.loc['ror_annual_TWh', scen_2035[0]])
ror_2050 = float(scen.loc['ror_annual_TWh', scen_2050[0]])
print(f'\nAnnual generation target (from scenario settings):')
print(f'  2035: {ror_2035:.2f} TWh')
print(f'  2050: {ror_2050:.2f} TWh')
print('\nNote: Allocated to CH00 region only (not per CH01-CH07)')

print('\n' + '='*80)
print('4. NUCLEAR POWER')
print('='*80)
# Read nonhydro capacities
nonhydro = pd.read_csv('input/nonhydro_capacities_gen_CH.csv')
nuclear = nonhydro[nonhydro['name'].str.contains('nuclear')]
print('\nFrom nonhydro_capacities_gen_CH.csv (all scenarios use same base):')
print(nuclear[['name', 'scenario', '2035', '2050']].to_string(index=False))

print(f'\n=> 2035: {nuclear["2035"].values[0]/1000:.2f} GW (in CH03 = Mittelland region)')
print(f'   2050: {nuclear["2050"].values[0]/1000:.2f} GW (base) + 1.6 GW if WN scenario')

# Read model variable presets
presets = pd.read_csv('input/model_variable_presets.csv', comment='#', header=None, skipinitialspace=True)
presets = presets.dropna(how='all')
print('\nModel variable presets for nuclear (from model_variable_presets.csv):')
for _, row in presets.iterrows():
    if 'nuclear' in str(row[2]):
        print(f'  {row[1]}: {row[4]:.0f} MW = {row[4]/1000:.2f} GW')

print('\n' + '='*80)
print('5. WASTE INCINERATION (KVA) - "other" technology')
print('   ASSUMPTION: "other" is assumed to represent waste incineration (KVA).')
print('   This has NOT been independently verified against original data sources.')
print('='*80)
other = nonhydro[nonhydro['name'].str.contains('_other')]
print('\nASSUMPTION: The "other" technology is assumed to represent waste incineration (KVA/Kehrichtverbrennungsanlagen).')
print('This assumption has not been verified against the original EP2050+ or BFE data sources.')
print('From nonhydro_capacities_gen_CH.csv (ZBA scenario shown):')
other_ZBA = other[other['scenario'] == 'ZBA'][['name', '2035', '2050']]
print(other_ZBA.to_string(index=False))
print(f'\n=> Total CH (2035): {other_ZBA["2035"].sum()/1000:.3f} GW')
print(f'   Total CH (2050): {other_ZBA["2050"].sum()/1000:.3f} GW')

print('\n' + '='*80)
print('6. SOLID BIOMASS')
print('='*80)
biomass = nonhydro[nonhydro['name'].str.contains('_biomass')]
print('\nFrom nonhydro_capacities_gen_CH.csv (ZBA scenario shown):')
biomass_ZBA = biomass[biomass['scenario'] == 'ZBA'][['name', '2035', '2050']]
print(biomass_ZBA.to_string(index=False))
print(f'\n=> Total CH (2035): {biomass_ZBA["2035"].sum()/1000:.3f} GW')
print(f'   Total CH (2050): {biomass_ZBA["2050"].sum()/1000:.3f} GW')

print('\n' + '='*80)
print('7. BIOGAS/SYNGAS')
print('='*80)
print('\nNote: Biogas/syngas is NOT modeled as a separate technology in the current model.')
print('It is implicitly included within the biomass fuel limits.')
print('The fuel_limits.csv controls biomass fuel availability (not capacity):')
fuel_lim = pd.read_csv('input/fuel_limits.csv', comment='#')
biomass_fuel = fuel_lim[fuel_lim['fuel'] == 'biomass']
print(biomass_fuel[['fuel', 'limit_type', '2035', '2050']].to_string(index=False))

print('\n' + '='*80)
print('SUMMARY TABLE')
print('='*80)
print('''
| Technology                  | 2035    | 2050     | Unit | Region      |
|-----------------------------|---------|----------|------|-------------|
| Pumped hydro (pumping)      | 4.71    | 5.54     | GW   | CH00        |
| Hydro dams (generation)     | 10.73   | 10.73    | GW   | CH00        |
| Run of river                | 4.20    | 4.20     | GW   | CH00        |
| Nuclear power               | 2.285   | 0/1.6*   | GW   | CH03        |
| Waste incin.* (other)       | ~0.12   | ~0.12    | GW   | CH01-CH07   |
| Solid biomass               | ~0.18   | ~0.22    | GW   | CH01-CH07   |
| Biogas/syngas               | n/a     | n/a      | GW   | (in fuel)   |

* Nuclear in 2050: 0 GW for NN scenarios, 1.6 GW for WN scenarios
* Waste incin.: ASSUMED that "other" tech = waste incineration (KVA). Not independently verified.
''')
