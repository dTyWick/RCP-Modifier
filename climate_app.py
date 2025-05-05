import os
import warnings
import webbrowser
from pathlib import Path

import folium
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import simpledialog, messagebox
from tkinter.scrolledtext import ScrolledText

from pymagicc.scenarios import rcp26, rcp45, rcp60, rcp85
from modify_scenario import modify_scenario

# Suppress known future warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="scmdata.run")

# --- Configuration ---
SCRIPT_DIR = Path(__file__).resolve().parent
MAP_FILENAME = "regional_input_map.html"
BASELINE_SCENARIOS = {
    1: ("rcp26", rcp26),
    2: ("rcp45", rcp45),
    3: ("rcp60", rcp60),
    4: ("rcp85", rcp85),
}
REGIONS = [
    'World|R5LAM', 'World|R5MAF', 'World|R5ASIA',
    'World|R5REF', 'World|R5OECD'
]
REGION_COLORS = {
    'World|R5LAM': '#1f77b4', 'World|R5MAF': '#ff7f0e',
    'World|R5ASIA': '#2ca02c', 'World|R5REF': '#d62728',
    'World|R5OECD': '#9467bd', 'Other': '#e377c2'
}
START_YEAR = 2025
END_YEAR = 2100


def show_welcome():
    """
    Display a welcome window with introductory text about RCPs, target years, and R factors.
    User closes when ready to proceed.
    """
    win = tk.Tk()
    win.title("Welcome to MAGICC Scenario Modifier")
    win.geometry("600x400")

    intro_text = (
        "Welcome!\n\n"
        "In this program you will make small modifications to the amount of CO2 produced by fossil fuels in different regions of the world, and you will see what happens to global surface temperatures by 2100.\n\n"
        "You will be modifying your choice of 4 representative consitutive pathways (RCP) by a multiplicative scaling factor (r), along with a phase factor (target year). \n\n"
        "What are RCP's? They are climate emissions scenarios that the IPCC uses for their simulations. They are listed in order of least to most detrimental. That is, RCP26 is the most aggresive climate mitigation future, while RCP85 is a future where we do essentially nothing to combat climate change.\n\n"
        "Scale factor? The scale factor is your tool to mitigate fossil fuel emissions. We take the RCP you choose (baseline), and calculate the new scenario by the equation\n\n"
        "New = baseline*(1 - r)\n\n"
        "Phase factor? This lets you control at what point in time your r factor will go into effect in totality. It takes time to make drastic changes to the energy economy, so we let you choose a date (2025 - 2100) by which r will equal its full amount. Before this, it starts at 0 and scales linearly in time from 2025 until your 'target year' \n\n"
        "Good luck!"
    )

    sc = ScrolledText(win, wrap='word')
    sc.insert(tk.END, intro_text)
    sc.configure(state='disabled')
    sc.pack(expand=True, fill='both', padx=10, pady=10)

    btn = tk.Button(win, text="Continue", command=win.destroy)
    btn.pack(pady=5)

    win.mainloop()


def load_and_map_geodata():
    """
    Load world boundaries and assign each country to a MAGICC R5 region.
    """
    try:
        url = (
            "https://naciscdn.org/naturalearth/110m/cultural/"
            "ne_110m_admin_0_countries.zip"
        )
        world = gpd.read_file(url)

        if 'name' in world.columns:
            world = world[world.name != 'Antarctica']
        elif 'ADMIN' in world.columns:
            world = world[world.ADMIN != 'Antarctica']

        def map_to_r5(row):
            iso = row.get('ADM0_A3', '')
            name = row.get('ADMIN', row.get('name', ''))
            continent = row.get('CONTINENT', '')
            subregion = row.get('SUBREGION', '')

            if iso in {'JPN','KOR','AUS','NZL','CAN','USA','CHE','ISL','NOR','TUR'}:
                return 'World|R5OECD'
            if name == 'Greenland':
                return 'World|R5OECD'
            if continent == 'Europe' and iso != 'RUS':
                return 'World|R5OECD'
            if iso == 'RUS' or subregion in {'Central Asia','Eastern Europe'}:
                return 'World|R5REF'
            if continent == 'Asia' and iso not in {'JPN','KOR'}:
                return 'World|R5ASIA'
            if continent == 'Africa' or subregion == 'Western Asia':
                return 'World|R5MAF'
            if continent in {'South America','North America'} and iso not in {'USA','CAN'}:
                return 'World|R5LAM'
            if continent == 'Oceania' and iso not in {'AUS','NZL'}:
                return 'World|R5LAM'
            return 'Other'

        world['magicc_region'] = world.apply(map_to_r5, axis=1)
        return world

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load geodata: {e}")
        return None


def create_and_save_map(gdf):
    """
    Build and save a Folium map colored by MAGICC R5 regions (no automatic browser open).
    """
    m = folium.Map(location=[20, 0], zoom_start=2, tiles='CartoDB positron')

    style = lambda feat: {
        'fillColor': REGION_COLORS.get(
            feat['properties']['magicc_region'], '#808080'
        ),
        'color': 'black', 'weight': 0.5, 'fillOpacity': 0.7
    }

    tooltip = folium.features.GeoJsonTooltip(
        fields=['ADMIN', 'magicc_region'],
        aliases=['Country:', 'MAGICC Region:']
    )

    folium.GeoJson(
        gdf,
        name='Regions',
        style_function=style,
        tooltip=tooltip
    ).add_to(m)

    legend = (
        '<div style="position: fixed; bottom: 50px; left: 50px; '
        'width: 180px; border:2px solid grey; z-index:9999; '
        'font-size:14px; background:white; padding:10px;">'
        '<b>MAGICC R5 Regions</b><br>'
    )
    for region, col in REGION_COLORS.items():
        if region != 'Other':
            legend += (
                f'<i style="background:{col}; width:15px; height:15px; '
                'display:inline-block; border:1px solid grey;"></i> '
                f'{region.split("|")[-1]}<br>'
            )
    legend += '</div>'
    m.get_root().html.add_child(folium.Element(legend))

    m.save(MAP_FILENAME)


def get_inputs_via_gui(regions):
    """
    Use tkinter dialogs to collect baseline scenario and regional inputs.
    """
    root = tk.Tk()
    root.withdraw()

    while True:
        choice = simpledialog.askinteger(
            "Baseline RCP", 
            "Select baseline RCP scenario (1-rcp26, 2-rcp45, 3-rcp60, 4-rcp85):"
        )
        if choice in BASELINE_SCENARIOS:
            baseline = BASELINE_SCENARIOS[choice]
            break
        messagebox.showerror("Invalid", "Please enter a number between 1 and 4.")

    targets = {}
    for region in regions:
        label = region.split('|')[-1]
        while True:
            r = simpledialog.askfloat(
                "R Factor", f"Enter R factor for {label} (0.0-1.0):"
            )
            if r is not None and 0.0 <= r <= 1.0:
                break
            messagebox.showerror("Invalid", "R must be between 0.0 and 1.0.")

        while True:
            yr = simpledialog.askinteger(
                "Target Year", f"Enter year for {label} ({START_YEAR}-{END_YEAR}):"
            )
            if yr and START_YEAR <= yr <= END_YEAR:
                break
            messagebox.showerror(
                "Invalid", f"Year must be between {START_YEAR} and {END_YEAR}."
            )

        targets[region] = {'R': r, 'Year': yr}

    return baseline[1], targets


if __name__ == "__main__":
    # Pre-generate map file (fast to save)
    gdf = load_and_map_geodata()
    if gdf is None:
        exit(1)
    create_and_save_map(gdf)

    # Welcome dialog; waits until user closes
    show_welcome()

    # Open map instantly after dialog closes
    path = os.path.abspath(MAP_FILENAME)
    webbrowser.open(f"file://{path}")

    # Collect user inputs
    baseline_obj, regional_targets = get_inputs_via_gui(REGIONS)

    # Scenario modification
    r_vals = [regional_targets[r]['R'] for r in REGIONS]
    y_vals = [regional_targets[r]['Year'] for r in REGIONS]
    mod_sc = modify_scenario(baseline_obj, r_vals, y_vals)

    # Plotting
    if mod_sc is not None:
        years = np.arange(1764, 2100)
        labels = ["rcp26", "rcp45", "rcp60", "rcp85"]

        co2 = np.load(SCRIPT_DIR / "rcp_data" \
                        / "Fossil_Fuel_CO2_Emissions_For_RCP_Scenarios.npy")
        mod_co2 = np.squeeze(
            mod_sc.filter(variable="Emissions|CO2|MAGICC Fossil and Industrial", 
                          region="World").timeseries().values
        )
        plt.figure(figsize=(16, 9))
        for i, arr in enumerate(co2):
            plt.plot(years, arr, label=labels[i])
        plt.plot(years, mod_co2, label=f"Modified {mod_sc['scenario'][0]}", color='black')
        # vertical line at x=2
        plt.axvline(x=2025, color='black', linestyle='--', linewidth=1)
        plt.legend(); plt.grid(); plt.xlim(2000, 2100)
        plt.xlabel("Year"); plt.ylabel("Gt/yr")
        plt.title("Fossil Fuel CO2 Emissions")
        plt.show()

        st = np.load(SCRIPT_DIR / "rcp_data" \
                       / "Surface_Temperaure_Anomalies_For_RCP_Scenarios.npy")
        mod_st = np.squeeze(
            mod_sc.filter(variable="Surface Temperature", region="World").timeseries().values
        )
        plt.figure(figsize=(16, 9))
        for i, arr in enumerate(st):
            plt.plot(years, arr, label=labels[i])
        plt.plot(years, mod_st, label=f"Modified {mod_sc['scenario'][0]}", color='black')
        plt.axhline(y=1.5, color='black',  linewidth=1, linestyle = '--')
        plt.axhline(y=2.0, color='black', linewidth=1, linestyle = '--')
        plt.legend(); plt.grid(); plt.xlim(2000, 2100)
        plt.xlabel("Year"); plt.ylabel("°C")
        plt.title("Surface Temperature Anomaly")
        plt.show()
