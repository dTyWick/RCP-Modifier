# Import statements 
import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re
import geopandas as gpd
import geodatasets as gds
import folium
import pymagicc as pm
import matplotlib.pyplot as plt
import scmdata
from scmdata import run_append
from tqdm import tqdm 
from scmdata import ScmRun
from pymagicc.io import MAGICCData
from pymagicc.scenarios import rcp26, rcp45, rcp60, rcp85

# Manipulate the scenario
# \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

def modify_scenario(scenario, r_factors, target_years):
    """
    Modifies the given scenario based on the provided R factors and target years.    

    Parameters:    
    - scenario: A MAGICCData scenario from the rcp list given in the import statements above
    - r_factors: List of R factors for each region.
    - List of **total** implementation years for these r_factors
    - NOTE: The r_factors list must be in the same order as the regions in the MAGICCData scenario, namely:
    {World|R5LAM, 'World|R5MAF', 'World|R5ASIA', 'World|R5REF', 'World|R5OECD'}    
    
    Returns:
    - modified_scenario: The modified MAGICCData scenario -> AFTER ran through pymagicc.
    - original_scenario: The original RCP scenario -> AFTER ran through pymagicc
    - scen_t: The original RCP scenario -> BEFORE ran through pymagicc
    - new_run: The modified RCP scenario -> BEFORE ran through pymagicc
    -

    """

    # First define the regions we are working with 
    regions_to_modify = ['World|R5OECD','World|R5LAM','World|R5MAF','World|R5REF','World|R5ASIA']
    regions_to_replace = ['World'] + regions_to_modify

    # define the variables we care about 
    var = "Emissions|CO2|MAGICC Fossil and Industrial"
    sTemp = "Surface Temperature"

    # get the target years based on the r_factors

    # This code assumes the target years are defined for defined r values. we are changing this.
    # # Define the dictionary for mapping r to year
    # r_to_year = {
    #     0: 2025,
    #     1/3: 2050,
    #     2/3: 2075,
    #     1: 2100
    # }

    # # Map r_factors to target_years
    # target_years = [r_to_year[r] for r in r_factors]


    # Calculate the reduction factor
    
    start_index = 25
    years_numeric = np.arange(2000, 2101)
    R_phase = np.zeros(shape=(len(r_factors), len(years_numeric)), dtype=float)
    target_index = [i - 2000 for i in target_years]
    ramp_duration = [i - start_index + 1 for i in target_index]

    scale_factor = [np.linspace(start=0,stop=r_factors[i],num=ramp_duration[i]) for i in range(len(r_factors))]

    for i in range(len(r_factors)):
        R_phase[i, start_index : target_index[i] + 1] = scale_factor[i]
        R_phase[i, target_index[i] + 1 :] = r_factors[i]

    # Now that R_phase[i] is the phase sensitive reduction factor for each region, we can now modify the rcp45 scenario region by region. 

    # Interpolate the RCP4.5 scenario 
    tgrid = pd.date_range(start="2000-01-01", end="2100-12-31", freq='YS-JAN')
    scen_t = scenario.interpolate(target_times=tgrid, interpolation_type="linear", extrapolation_type='constant')


    # Assuming that we go with the first scenario (rcp26) for the rest of the code
    new_df = scen_t.timeseries()

    # Select all regions except for "World|Bunkers" and "World" 
    idx = pd.IndexSlice
    reg_C02 = new_df.loc[
        idx[:,                              # any climate_model
            :,                              # any model
            ~new_df.index.get_level_values("region").isin(["World|Bunkers", "World"]),
            :,                              # any scenario
            :,                              # any todo
            "Gt C / yr",                    # unit for fossil CO2
            "Emissions|CO2|MAGICC Fossil and Industrial"
        ],
        :                                   # all time‐columns
    ]

    # update regional values 
    reg_C02 *= (1 - R_phase)


    # Add updated values back into MAGICCData object:

    # get world co2 series as the sum of the regional co2 data
    world_co2_series = reg_C02.sum()
    # 2) Drop the old series from the existing MAGICCData object
#    base_run now contains everything EXCEPT Fossil CO2 for World + R5 regions
    base_run = scen_t.filter(
        variable=var,
        region=regions_to_replace,
        keep=False, # Crucially, keep everything *else*
    )

    # 3) Prepare the replacement data DataFrame (Wide Format)
    #    We need the metadata MultiIndex for the rows we are replacing.
    #    Filter the *original* interpolated object to get these rows' metadata.
    replacement_meta_template = scen_t.filter(variable=var, region=regions_to_replace)
    #    Ensure the R5 regions are ordered correctly in the metadata index
    r5_meta_ordered = replacement_meta_template.filter(region=regions_to_modify).meta.set_index('region').loc[regions_to_modify].reset_index()
    world_meta = replacement_meta_template.filter(region='World').meta
    #    Combine metadata, ensuring World is first, then R5 regions in specified order
    combined_meta = pd.concat([world_meta, r5_meta_ordered]).set_index(['model', 'scenario', 'region', 'variable', 'unit', 'climate_model', 'todo']) # Adjust index levels if needed

    #    Combine the data values: world first, then regions
    #    Make sure world_co2_series index matches tgrid
    world_co2_values_aligned = world_co2_series.reindex(tgrid).values
    #    Stack world values on top of regional values
    combined_values = np.vstack([world_co2_values_aligned, reg_C02.values]) # Should be 6 x 101

    #    Create the replacement DataFrame in wide format
    replacement_df_wide = pd.DataFrame(
        data=combined_values,
        index=combined_meta.index, # Use the combined, ordered metadata index
        columns=tgrid              # Use the annual datetime index as columns
    )

    # 4) Build a ScmRun/MAGICCData object containing ONLY the 6 replacement series
    #    The constructor can often handle the wide format if the index is metadata
    rep_run = MAGICCData(replacement_df_wide) # Or use ScmRun(...)

    # 5) Append the replacement data back onto the base run
    new_run = base_run.append(rep_run)

    # Run scenarios through pymagicc, and return the results 
    modified_scenario = pm.run(new_run)
    

    # return modified scenario BEFORE it was ran through pymagicc
    return(modified_scenario)
