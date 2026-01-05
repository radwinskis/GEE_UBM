import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import folium
import geopandas as gpd
from streamlit_folium import st_folium
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from shapely.ops import unary_union
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import geemap.foliumap as geemap
from geemap import basemaps
import ee
from RadGEEToolbox import GenericCollection, get_palette

service_account = 'localpythonscripts@ut-gee-ugs-bsf-dev.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'C:\\Users\\mradwin\\ut-gee-ugs-bsf-dev-53dcc5d729e0.json')
ee.Initialize(credentials=credentials)

st.set_page_config(layout="wide", page_title="UBM App", page_icon="⚖️") # Use full screen width

# --- CSS HACK: Remove Top Margins & Footer ---
# st.markdown("""
#     <style>
#            /* Remove top padding */
#            .block-container {
#                 padding-top: 3rem;
#                 padding-bottom: 0rem;
#             }
#            /* Make the plot container full width */
#            .element-container {
#                 width: 100%;
#            }
#     </style>
#     """, unsafe_allow_html=True)
st.markdown(
    """
    <style>
    /* Target the specific element Streamlit uses for Plotly */
    div[data-testid="stPlotlyChart"] {
        display: flex;
        justify-content: center;
    }
    /* Force st_folium to center itself */
    div[data-testid="stFolium"] {
        margin: auto;
        display: flex;
        justify-content: center;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- SECTION 1: INFO SNIPPET ---
with st.container():
    # st.title("🌊 Utah Watersheds Explorer")
    st.header("⚖️ Utah Basin Model (UBM) Soil Water Balance Demo App (v1.0)", divider='rainbow')
    st.markdown("""
    **Welcome.** This app helps to visualize UBM ensemble runs across Utah. 
    Select a region below to generate the ensemble time series, or scroll down to view spatial distribution maps.
    """)
    # st.header('', divider='rainbow', text_alignment='center')
    # st.divider()

# --- SECTION 2: REGION SELECTOR (Your "Navbar") ---
# Use session state to handle the "Map Mode" vs "Button Mode"
if 'view_mode' not in st.session_state:
    st.session_state['view_mode'] = 'Select from Map'

# --- 1. SETUP MAP ---
# Load your shapefile/GeoJSON of Utah Watersheds
@st.cache_data
def load_geodata():
    # 1. Read the file
    gdf = gpd.read_file("UT_Watersheds_Export.geojson")

    # --- FIX: UNPACK GEOMETRY COLLECTIONS ---
    # Define a function to fix a single geometry
    def fix_geometry(geom):
        # If it's already fine, return it
        if isinstance(geom, (Polygon, MultiPolygon)):
            return geom
        
        # If it's a Collection, grab only the Polygons inside
        if isinstance(geom, GeometryCollection):
            polys = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon))]
            # Merge them into one shape
            return unary_union(polys)
        
        # If it's something weird (Point/Line), return None so we can drop it later
        return None

    # Apply the fix to every row
    gdf['geometry'] = gdf['geometry'].apply(fix_geometry)

    # --- STANDARD CLEANING (Same as before) ---
    gdf = gdf.dropna(subset=['geometry'])   # Drop rows that became None
    gdf = gdf[~gdf.geometry.is_empty]       # Drop empty shapes
    
    # Simplify to keep the map fast (essential for 40MB files)
    gdf['geometry'] = gdf.simplify(tolerance=0.001)

    # Projection check
    if gdf.crs is None:
         gdf.set_crs(epsg=26912, inplace=True)
    if gdf.crs.to_string() != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)

    return gdf

gdf = load_geodata()

# with st.container(width='stretch', horizontal_alignment='center'):
    # A horizontal radio acts like a navbar
selection_mode = st.radio(
    "**Choose Data Source:**",
    ["UT Statewide", "Entire GSL Basin", "Select Watershed from Map"],
    horizontal=True,
    index=2 # Default to Map
)
# Logic to handle the selection
# target_id = None
target_id = 'GSL_Basin_Watershed'  # Default selection

m = folium.Map(location=[39.55, -111.5], zoom_start=7)

folium.GeoJson(
        gdf,
        name="Utah Watersheds",
        style_function=lambda x: {
            'fillColor': '#YlGn', # You can fix this to a hex code like '#00ff00' or use logic
            'color': 'black',
            'weight': 1,
            'fillOpacity': 0.5,
        },
        highlight_function=lambda x: {
            'weight': 3,
            'color': 'black',
            'fillOpacity': 0.7
        },
        # This allows the user to hover and see the name before clicking
        tooltip=folium.GeoJsonTooltip(fields=['HU_8_NAME']) 
    ).add_to(m)

if selection_mode == "UT Statewide":
    target_id = "Utah_Statewide"
elif selection_mode == "Entire GSL Basin":
    target_id = "GSL_Basin_Watershed"
elif selection_mode == "Select Watershed from Map":

    # Create the base Folium map
    m = folium.Map(location=[39.55, -111.5], zoom_start=7)

    # m.addLayer(gdf)

    folium.GeoJson(
        gdf,
        name="Utah Watersheds",
        style_function=lambda x: {
            'fillColor': '#YlGn', # You can fix this to a hex code like '#00ff00' or use logic
            'color': 'black',
            'weight': 1,
            'fillOpacity': 0.5,
        },
        highlight_function=lambda x: {
            'weight': 3,
            'color': 'black',
            'fillOpacity': 0.7
        },
        # This allows the user to hover and see the name before clicking
        tooltip=folium.GeoJsonTooltip(fields=['HU_8_NAME']) 
    ).add_to(m)

    # --- INITIALIZE SESSION STATE ---
    # This "remembers" the selected watershed across re-runs
    # if 'selected_id' not in st.session_state:
    #     st.session_state['selected_id'] = None
    # if 'last_map_clicked' not in st.session_state:
    #     st.session_state['last_map_clicked'] = None


    # # --- MAP SECTION ---
    # col_map, col_plot = st.columns([1, 2])

    # with col_map:
    #     st.subheader("Select Region")
    #     btn_col1, btn_col2, _ = st.columns([5, 5, 8])


    #     with btn_col1:
    #         if st.button("UT Statewide"):
    #             st.session_state['selected_id'] = "Utah_Statewide"

    #     with btn_col2:
    #         if st.button("Entire GSL Basin"):
    #             st.session_state['selected_id'] = "GSL_Basin_Watershed"
        
        
        # Render Map
map_output = st_folium(m, width=None, height=650, returned_objects=["last_active_drawing"])
if map_output["last_active_drawing"]:
    target_id = map_output["last_active_drawing"]["properties"].get("HU_8_NAME")

# Fallback if nothing clicked yet
if not target_id and st.session_state.get('last_map_clicked'):
    target_id = st.session_state['last_map_clicked']

 # Save selection to state
if target_id:
    st.session_state['selected_id'] = target_id
    # If it came from the map, save it so it persists if we toggle modes
    if selection_mode == "Select Watershed from Map":
        st.session_state['last_map_clicked'] = target_id   
    # # --- LOGIC: HANDLE MAP CLICKS ---
    # # We only update if the map click is NEW (different from the last run)
    # current_click = map_output["last_active_drawing"]
    
    # if current_click is not None:
    #     # Get the ID from the click
    #     clicked_id = current_click["properties"].get("HU_8_NAME")
        
    #     # Check if this is a *new* interaction
    #     # We compare the whole object or ID to what we saw last time
    #     if clicked_id != st.session_state['last_map_clicked']:
    #         st.session_state['selected_id'] = clicked_id
    #         st.session_state['last_map_clicked'] = clicked_id

# --- PLOTTING SECTION ---
with st.container(horizontal=False, horizontal_alignment='center',  width='stretch'):

    if st.session_state.get('selected_id'):
    # Now we just look at the Session State, we don't care where it came from
        current_selection = st.session_state['selected_id']
        current_selection_filtered = current_selection.replace(',', '').replace("'", "").replace(" ", "_").replace("-", "_") .replace("__", "_") 
        
        directory = 'C:\\Users\\mradwin\\Documents\\Utah Soil Water Balance\\Zonal_Stats_Timeseries\\All_Watersheds\\'

        if current_selection:
            # st.subheader(f"Data for: {current_selection} AKA {current_selection_filtered}")
            
            directory = 'C:\\Users\\mradwin\\Documents\\Utah Soil Water Balance\\Zonal_Stats_Timeseries\\All_Watersheds\\'
            watershed = current_selection_filtered
            watershed_name = watershed.replace('_', ' ')
            folder_path = directory + watershed + '\\'
            file_list = os.listdir(folder_path)
            # print(file_list)
            # master_df = pd.DataFrame()
            # master_df.columns = ['Date', 'Recharge_m3',  'Runoff_m3', 'Soil_Water_End_m3', 'AET_m3', 'Precip_and_Snowmelt_m3', 'Irrigation_m3']
            recharge_df = pd.DataFrame()
            runoff_df = pd.DataFrame()
            soil_water_df = pd.DataFrame()
            AET_df = pd.DataFrame()
            precipitation_df = pd.DataFrame()
            irrigation_df = pd.DataFrame()

            for file in file_list:
                if file.endswith('.csv'):
                    if 'ETDisALEXI' in file:
                        ET_type = 'OpenET_DisALEXI'
                    elif 'ETEEMETRIC' in file:
                        ET_type = 'OpenET_EEMETRIC'
                    elif 'ETPTJPL' in file:
                        ET_type = 'OpenET_PTJPL'
                    elif 'ETSSEBOP' in file:
                        ET_type = 'OpenET_SSEBOP'
                    elif 'ETGEESEBAL' in file:
                        ET_type = 'OpenET_GEESEBAL'
                    elif 'ETSIMS' in file:
                        ET_type = 'OpenET_SIMS'
                    else:
                        ET_type = 'Unknown_ET_Model'

                    if 'DAYMETSNOM' in file:
                        precip_type = 'DAYMET_Precipitation'
                    elif 'PRISMSNOM' in file:
                        precip_type = 'PRISM_Precipitation'
                    elif 'GRIDMETSNOM' in file:
                        precip_type = 'GRIDMET_Precipitation'
                    else:
                        precip_type = 'Unknown_Precipitation_Model'

                    if ET_type == 'OpenET_SIMS':
                        pass
                    else:
                    
                        file_path = os.path.join(folder_path, file)
                        ws_df = pd.read_csv(file_path)
                        
                        watershed_recharge_df = ws_df[['Date', 'Recharge_m3']].copy()
                        watershed_recharge_df['Date'] = pd.to_datetime(watershed_recharge_df['Date'])
                        watershed_recharge_df.rename(columns={'Recharge_m3': f'Recharge_m3_{ET_type}_{precip_type}'}, inplace=True)
                        recharge_df = pd.merge(recharge_df, watershed_recharge_df, on='Date', how='outer') if not recharge_df.empty else watershed_recharge_df
                        
                        watershed_runoff_df = ws_df[['Date', 'Runoff_m3']].copy()
                        watershed_runoff_df['Date'] = pd.to_datetime(watershed_runoff_df['Date'])
                        watershed_runoff_df.rename(columns={'Runoff_m3': f'Runoff_m3_{ET_type}_{precip_type}'}, inplace=True)
                        runoff_df = pd.merge(runoff_df, watershed_runoff_df, on='Date', how='outer') if not runoff_df.empty else watershed_runoff_df
                        
                        watershed_soil_water_df = ws_df[['Date', 'Soil_Water_End_m3']].copy()
                        watershed_soil_water_df['Date'] = pd.to_datetime(watershed_soil_water_df['Date'])
                        watershed_soil_water_df.rename(columns={'Soil_Water_End_m3': f'Soil_Water_End_m3_{ET_type}_{precip_type}'}, inplace=True)
                        soil_water_df = pd.merge(soil_water_df, watershed_soil_water_df, on='Date', how='outer') if not soil_water_df.empty else watershed_soil_water_df
                        
                        watershed_AET_df = ws_df[['Date', 'AET_m3']].copy()
                        watershed_AET_df['Date'] = pd.to_datetime(watershed_AET_df['Date'])
                        watershed_AET_df.rename(columns={'AET_m3': f'AET_m3_{ET_type}_{precip_type}'}, inplace=True)
                        AET_df = pd.merge(AET_df, watershed_AET_df, on='Date', how='outer') if not AET_df.empty else watershed_AET_df

                        watershed_precipitation_df = ws_df[['Date', 'Precip_and_Snowmelt_m3']].copy()
                        watershed_precipitation_df['Date'] = pd.to_datetime(watershed_precipitation_df['Date'])
                        watershed_precipitation_df.rename(columns={'Precip_and_Snowmelt_m3': f'Precip_and_Snowmelt_m3_{ET_type}_{precip_type}'}, inplace=True)
                        precipitation_df = pd.merge(precipitation_df, watershed_precipitation_df, on='Date', how='outer') if not precipitation_df.empty else watershed_precipitation_df
                    
                        watershed_irrigation_df = ws_df[['Date', 'Irrigation_m3']].copy()
                        watershed_irrigation_df['Date'] = pd.to_datetime(watershed_irrigation_df['Date'])
                        watershed_irrigation_df.rename(columns={'Irrigation_m3': f'Irrigation_m3_{ET_type}_{precip_type}'}, inplace=True)
                        irrigation_df = pd.merge(irrigation_df, watershed_irrigation_df, on='Date', how='outer') if not irrigation_df.empty else watershed_irrigation_df
            M3_TO_ACFT = 0.000810714

            def _ensure_datetime_sorted(df: pd.DataFrame) -> pd.DataFrame:
                if df is None or df.empty:
                    return pd.DataFrame()
                out = df.copy()
                out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
                out = out.dropna(subset=["Date"]).sort_values("Date")
                return out

            def _numeric_cols(df: pd.DataFrame):
                cols = [c for c in df.columns if c != "Date"]
                # coerce to numeric (protects against stray strings)
                for c in cols:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
                return cols

            def _trace_id_from_col(col_name: str) -> str:
                # As requested: split on "_" and take the last two tokens
                parts = str(col_name).split("_")
                return "_".join(parts[-4:]) if len(parts) >= 4 else str(col_name)

            def _select_one_per_precip_model(df: pd.DataFrame):
                """Keep ONE column containing PRISM, ONE containing GRIDMET, ONE containing DAYMET (first match in each)."""
                all_cols = [c for c in df.columns if c != "Date"]
                keep = []
                for key in ("PRISM", "GRIDMET", "DAYMET"):
                    matches = [c for c in all_cols if key.lower() in c.lower()]
                    if matches:
                        keep.append(matches[0])
                return keep

            def _add_ensemble_subplot(fig, df, cols, row, title):
                if df.empty or not cols:
                    return

                x = df["Date"]

                # Ensemble members (no legend; ID on hover)
                for c in cols:
                    tid = _trace_id_from_col(c)
                    fig.add_trace(
                        go.Scatter(
                            x=x,
                            y=df[c] * M3_TO_ACFT,
                            name=tid,
                            showlegend=False,
                            mode="lines",
                            line=dict(color="darkslategrey", width=1),
                            opacity=0.2,
                            hovertemplate=(
                                "%{x|%Y-%m-%d}<br>"
                                "%{y:,.0f} acre-ft<br>"
                                f"{tid}"
                                "<extra></extra>"
                            ),
                        ),
                        row=row,
                        col=1,
                    )

                # Ensemble mean (still no legend; labeled in hover)
                mean_series = df[cols].mean(axis=1, skipna=True)
                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=mean_series * M3_TO_ACFT,
                        name="Ensemble mean",
                        showlegend=False,
                        mode="lines",
                        line=dict(color="salmon", width=2.2),
                        opacity=0.8,
                        hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.0f} acre-ft<br>Ensemble mean<extra></extra>",
                    ),
                    row=row,
                    col=1,
                )

            # --- Prepare dataframes (assumes these already exist in your notebook) ---
            recharge_p = _ensure_datetime_sorted(recharge_df)
            runoff_p = _ensure_datetime_sorted(runoff_df)
            soil_water_p = _ensure_datetime_sorted(soil_water_df)
            AET_p = _ensure_datetime_sorted(AET_df)
            precip_p = _ensure_datetime_sorted(precipitation_df)
            irrig_p = _ensure_datetime_sorted(irrigation_df)

            recharge_cols = _numeric_cols(recharge_p) if not recharge_p.empty else []
            runoff_cols = _numeric_cols(runoff_p) if not runoff_p.empty else []
            soil_cols = _numeric_cols(soil_water_p) if not soil_water_p.empty else []
            AET_cols = _numeric_cols(AET_p) if not AET_p.empty else []

            # Precip: only one each for PRISM/GRIDMET/DAYMET
            if not precip_p.empty:
                _numeric_cols(precip_p)
                precip_cols = _select_one_per_precip_model(precip_p)
            else:
                precip_cols = []

            # Irrigation: only plot the first non-Date column
            if not irrig_p.empty:
                irrig_cols_all = _numeric_cols(irrig_p)
                irrig_col = irrig_cols_all[0] if irrig_cols_all else None
            else:
                irrig_col = None

            titles = (
                "Soil Water Volume",
                "Recharge Volume",
                "Runoff Volume",
                "AET Volume",
                "Precipitation + Snowmelt Volume",
                "Irrigation Volume",
            )

            fig = make_subplots(
                rows=6, cols=1,
                shared_xaxes=False,
                vertical_spacing=0.05,
                subplot_titles=titles,
                row_heights=[2, 2, 2, 2, 2, 1]
            )
            _add_ensemble_subplot(fig, soil_water_p, soil_cols, row=1, title=titles[2])
            _add_ensemble_subplot(fig, recharge_p, recharge_cols, row=2, title=titles[0])
            _add_ensemble_subplot(fig, runoff_p, runoff_cols, row=3, title=titles[1])
            _add_ensemble_subplot(fig, AET_p, AET_cols, row=4, title=titles[3])
            _add_ensemble_subplot(fig, precip_p, precip_cols, row=5, title=titles[4])

            # Irrigation (single column only; no legend)
            if irrig_p is not None and not irrig_p.empty and irrig_col is not None:
                fig.add_trace(
                    go.Scatter(
                        x=irrig_p["Date"],
                        y=irrig_p[irrig_col] * M3_TO_ACFT,
                        name="Irrigation",
                        showlegend=False,
                        mode="lines",
                        line=dict(color="darkslategrey", width=1.6),
                        opacity=1.0,
                        hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.0f} acre-ft<br>Irrigation<extra></extra>",
                    ),
                    row=6, col=1
                )
            fig.add_trace(
                go.Scatter(
                    x=[None], y=[None],
                    mode="lines",
                    line=dict(color="salmon", width=2.2),
                    name="Ensemble mean",
                    showlegend=True,
                    hoverinfo="skip",
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=[None], y=[None],
                    mode="lines",
                    line=dict(color="darkslategrey", width=1.2),
                    opacity=0.8,
                    name="Ensemble runs",
                    showlegend=True,
                    hoverinfo="skip",
                )
            )

            # --- Styling (no legends) ---
            target_font = "Times New Roman"
            fig.update_layout(
                title=dict(
                    text=f"{watershed_name} — UBM Ensemble Time Series (acre-ft)",
                    x=0.5,          # center
                    xanchor="center",
                    y=0.98,
                    yanchor="top",
                    font=dict(family=target_font, size=18, color="black"),
                ),
                height=1200, #*0.65,
                width=1000,
                template="plotly_white",      # optional, but helps ensure white defaults
                paper_bgcolor="white",        # <-- this is the outer background
                plot_bgcolor="white", 
                font=dict(family=target_font, size=14, color="black"),
                margin=dict(t=60, b=50, l=70, r=60),
                showlegend=True,
                legend=dict(
                    x=0.02, y=0.9,              # inside top subplot, near bottom-left-ish (tweak y if needed)
                    xanchor="left", yanchor="top",
                    bgcolor="rgba(255,255,255,0.0)",
                    borderwidth=0,
                    font=dict(family=target_font, size=12, color="black"),
                    orientation="h",
                )
            )

            fig.update_annotations(font=dict(family=target_font, size=15))

            fig.update_xaxes(
                showline=True, linewidth=1.2, linecolor="black", mirror=True,
                showgrid=False,
                ticks="outside", ticklen=6,
                minor=dict(ticklen=4, dtick="M6", showgrid=False),
            )

            fig.update_yaxes(
                showline=True, linewidth=1.2, linecolor="black", mirror=True,
                showgrid=False,
                ticks="outside", ticklen=6,
                title_text="Volume (acre-ft)",
            )


            fig.update_xaxes(title_text="Date", row=6, col=1, dtick="M12")
            for r in range(1, 7):
                fig.update_xaxes(
                    showticklabels=True,
                    row=r, col=1,
                    range=[pd.Timestamp('2005-01-01'), pd.Timestamp('2024-12-31')],
                    dtick="M12"
                )

            # fig.show()
            st.plotly_chart(fig, width=1500, theme=None)
            # print(recharge_df.head())
        else:
            st.info("👈 Select a watershed from the map OR click a button above.")

st.divider()

def convert_depth_to_volume(image, proj):
    """Converts pixel values from depth (mm) to volume (m^3)."""
    image = image.setDefaultProjection(proj)
    pixel_area = ee.Image.pixelArea().reproject(proj)
    depth_in_meters = image.multiply(0.001)
    volume_m3 = pixel_area.multiply(depth_in_meters)
    return volume_m3 #.copyProperties(image, image.propertyNames())
with st.container(width='stretch', horizontal_alignment='center'):
    st.header("🗺️ Spatial Distribution Analysis", divider='rainbow', text_alignment='center')
    st.markdown("""
    #### **Explore spatial distributions** of Soil Water Balance Model outputs and inputs across Utah for selected years and variables. Units are volumetric (m³) totals for each pixel.
                
    Select the year, variable, and model from the dropdowns below to generate the maps. Adjust the min and max sliders to adjust color scaling as needed.
                
    > NOTE: DAYMET derived models have a finer resolution (1km) compared to PRISM and GRIDMET derived models (4.5km). Thus, volumetric values for DAYMET are smaller as there is less volume of water per pixel.
    """, text_alignment='center')
  

    col_controls1, col_controls2, col_controls3, col_controls4 = st.columns([2, 1, 2, 1]) #st.columns(4)
    with col_controls1:
        year_select = st.slider("Select Year", 2005, 2024, 2024)
    with col_controls2:
        variable_select = st.selectbox("Select Variable", ["Soil Water", "Recharge", "Runoff", "AET", "Precipitation + Snowmelt", "Irrigation"])
    with col_controls3:
        # model_select = st.selectbox("Select Model", ["Ensemble Mean", "OpenET DisALEXI & DAYMET Precipitation", "OpenET EEMETRIC & DAYMET Precipitation", 
        #                                              "OpenET PTJPL & DAYMET Precipitation", "OpenET SSEBOP & DAYMET Precipitation", "OpenET GEESEBAL & DAYMET Precipitation", 
        #                                              "OpenET SIMS & DAYMET Precipitation", "OpenET DisALEXI & PRISM Precipitation", "OpenET EEMETRIC & PRISM Precipitation", 
        #                                              "OpenET PTJPL & PRISM Precipitation", "OpenET SSEBOP & PRISM Precipitation", "OpenET GEESEBAL & PRISM Precipitation", 
        #                                              "OpenET SIMS & PRISM Precipitation", "OpenET DisALEXI & GRIDMET Precipitation", "OpenET EEMETRIC & GRIDMET Precipitation", 
        #                                              "OpenET PTJPL & GRIDMET Precipitation", "OpenET SSEBOP & GRIDMET Precipitation", "OpenET GEESEBAL & GRIDMET Precipitation", 
        #                                              "OpenET SIMS & GRIDMET Precipitation",])
        model_select = st.selectbox("Select Model", ["Ensemble Mean", "OpenET DisALEXI & DAYMET Precipitation", "OpenET EEMETRIC & DAYMET Precipitation", 
                                                     "OpenET PTJPL & DAYMET Precipitation", "OpenET SSEBOP & DAYMET Precipitation", "OpenET GEESEBAL & DAYMET Precipitation", 
                                                     "OpenET DisALEXI & PRISM Precipitation", "OpenET EEMETRIC & PRISM Precipitation", 
                                                     "OpenET PTJPL & PRISM Precipitation", "OpenET SSEBOP & PRISM Precipitation", "OpenET GEESEBAL & PRISM Precipitation", 
                                                    "OpenET DisALEXI & GRIDMET Precipitation", "OpenET EEMETRIC & GRIDMET Precipitation", 
                                                     "OpenET PTJPL & GRIDMET Precipitation", "OpenET SSEBOP & GRIDMET Precipitation", "OpenET GEESEBAL & GRIDMET Precipitation", 
                                                     ])
    with col_controls4:
        unit = st.selectbox("Select Unit", [ "Acre-Feet (acre-ft)", "Cubic Meters (m³)"], index=0)
    bands_dict = {"Soil Water": "Soil_Water_End_Of_Previous_Timestep", "Recharge": "Recharge", "Runoff": "Runoff", "AET":"AET", 
                  "Precipitation + Snowmelt":"precip_and_snowmelt_input", "Irrigation":"irrigation"}
    
    if unit == "Acre-Feet (acre-ft)":
        unit_scalar = M3_TO_ACFT
        unit_label = "acre-ft"
    else:
        unit_scalar = 1.0
        unit_label = "m³"
    
    if model_select == "Ensemble Mean":
        model_key = "Ensemble_Mean"
        col1 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_DAYMETSNOM_ETDisALEXI_IRRIm_M_m3')
        col2 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_DAYMETSNOM_ETEEMETRIC_IRRIm_M_m3')
        col3 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_DAYMETSNOM_ETGEESEBAL_IRRIm_M_m3')
        col4 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_DAYMETSNOM_ETPTJPL_IRRIm_M_m3')
        col5 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_DAYMETSNOM_ETSIMS_IRRIm_M_m3')
        col6 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_DAYMETSNOM_ETSSEBOP_IRRIm_M_m3')
        col7 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_GRIDMETSNOM_ETDisALEXI_IRRIm_M_m3')
        col8 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_GRIDMETSNOM_ETEEMETRIC_IRRIm_M_m3')
        col9 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_GRIDMETSNOM_ETGEESEBAL_IRRIm_M_m3')
        col10 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_GRIDMETSNOM_ETPTJPL_IRRIm_M_m3')
        col11 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_GRIDMETSNOM_ETSIMS_IRRIm_M_m3')
        col12 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_GRIDMETSNOM_ETSSEBOP_IRRIm_M_m3')
        col13 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_PRISMSNOM_ETDisALEXI_IRRIm_M_m3')
        col14 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_PRISMSNOM_ETEEMETRIC_IRRIm_M_m3')
        col15 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_PRISMSNOM_ETGEESEBAL_IRRIm_M_m3')
        col16 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_PRISMSNOM_ETPTJPL_IRRIm_M_m3')
        col17 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_PRISMSNOM_ETSIMS_IRRIm_M_m3')
        col18 = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_PRISMSNOM_ETSSEBOP_IRRIm_M_m3')
        def reduceResolution(img, work_proj=None):
            target_proj = col13.first().projection() #ee.Projection('EPSG:32612').atScale(1000)
            # work_proj: fine-scale metric grid to run the kernel on
            wp = work_proj or img.projection()
            # img_fine = img.reproject(wp)
            img_fine = img.setDefaultProjection(wp)
            agg = img_fine.reduceResolution(reducer=ee.Reducer.sum(), maxPixels=65536)
            return agg.reproject(target_proj) #.set('system:time_start', img.get('system:time_start'))
        cols = [col1, col2, col3, col4, col5, col6, col7, col8, col9, col10, col11, col12, col13, col14, col15, col16, col17, col18]
        stacked_collection = []
        for i, col in enumerate(cols):
            col = col.filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
            col = col.select(bands_dict[variable_select])
            native_proj = col.first().projection()
            if variable_select == "Soil Water":
                col = col.mean()
            else:
                col = col.sum()
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                col = convert_depth_to_volume(ee.Image(col), native_proj)
            if i < 5:
                col = reduceResolution(col, col1.first().projection())
            
            stacked_collection.append(col)     
        stacked_collection = ee.ImageCollection(stacked_collection)
        image = stacked_collection.mean()

    elif model_select == "OpenET DisALEXI & DAYMET Precipitation":
        model_key = "ETDisALEXI_DAYMETSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_DAYMETSNOM_ETDisALEXI_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET EEMETRIC & DAYMET Precipitation":
        model_key = "ETEEMETRIC_DAYMETSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_DAYMETSNOM_ETEEMETRIC_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET PTJPL & DAYMET Precipitation":
        model_key = "ETPTJPL_DAYMETSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_DAYMETSNOM_ETPTJPL_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET SSEBOP & DAYMET Precipitation":
        model_key = "ETSSEBOP_DAYMETSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_DAYMETSNOM_ETSSEBOP_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET GEESEBAL & DAYMET Precipitation":
        model_key = "ETGEESEBAL_DAYMETSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_DAYMETSNOM_ETGEESEBAL_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET SIMS & DAYMET Precipitation":
        model_key = "ETSIMS_DAYMETSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_DAYMETSNOM_ETSIMS_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET DisALEXI & PRISM Precipitation":
        model_key = "ETDisALEXI_PRISMSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_PRISMSNOM_ETDisALEXI_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET EEMETRIC & PRISM Precipitation":
        model_key = "ETEEMETRIC_PRISMSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_PRISMSNOM_ETEEMETRIC_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET PTJPL & PRISM Precipitation":
        model_key = "ETPTJPL_PRISMSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_PRISMSNOM_ETPTJPL_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET SSEBOP & PRISM Precipitation":
        model_key = "ETSSEBOP_PRISMSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_PRISMSNOM_ETSSEBOP_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET GEESEBAL & PRISM Precipitation":
        model_key = "ETGEESEBAL_PRISMSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_PRISMSNOM_ETGEESEBAL_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET SIMS & PRISM Precipitation":
        model_key = "ETSIMS_PRISMSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_PRISMSNOM_ETSIMS_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET DisALEXI & GRIDMET Precipitation":
        model_key = "ETDisALEXI_GRIDMETSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_GRIDMETSNOM_ETDisALEXI_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET EEMETRIC & GRIDMET Precipitation":
        model_key = "ETEEMETRIC_GRIDMETSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_GRIDMETSNOM_ETEEMETRIC_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj) 
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET PTJPL & GRIDMET Precipitation":
        model_key = "ETPTJPL_GRIDMETSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_GRIDMETSNOM_ETPTJPL_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET SSEBOP & GRIDMET Precipitation":
        model_key = "ETSSEBOP_GRIDMETSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_GRIDMETSNOM_ETSSEBOP_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET GEESEBAL & GRIDMET Precipitation":
        model_key = "ETGEESEBAL_GRIDMETSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_GRIDMETSNOM_ETGEESEBAL_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
    elif model_select == "OpenET SIMS & GRIDMET Precipitation":
        model_key = "ETSIMS_GRIDMETSNOM"
        collection = ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_GRIDMETSNOM_ETSIMS_IRRIm_M_m3').filterDate(f'{year_select}-01-01', f'{year_select}-12-31')
        native_proj = collection.first().select(bands_dict[variable_select]).projection()
        if variable_select == "Soil Water":
            image = collection.select(bands_dict[variable_select]).mean().setDefaultProjection(native_proj)
        else:
            if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)
                image = convert_depth_to_volume(ee.Image(image), native_proj)
            else:
                image = collection.select(bands_dict[variable_select]).sum().setDefaultProjection(native_proj)



    # if variable_select in ["AET", "Precipitation + Snowmelt", "Irrigation"]:
    #     image = convert_depth_to_volume(ee.Image(image))
    # else:
    #     pass
      
    viz_controls1, viz_controls2 = st.columns(2)
    with viz_controls1:
        if variable_select == "Soil Water":
            min_select = st.slider("Select Min Stretch Value", min_value=0, max_value=int(1E6*unit_scalar), value=int(0*unit_scalar), step=10000)
        if variable_select == "Recharge":
            min_select = st.slider("Select Min Stretch Value", min_value=0, max_value=int(1E6*unit_scalar), value=int(0*unit_scalar), step=10000)
        if variable_select == "Runoff":
            min_select = st.slider("Select Min Stretch Value", min_value=0, max_value=int(1E5*unit_scalar), value=int(0*unit_scalar), step=10000)
        if variable_select == "AET":
            if 'DAYMET' in model_select:
                min_select = st.slider("Select Min Stretch Value", min_value=0, max_value=int(1E5*unit_scalar), value=int(1E4*unit_scalar), step=10000)
            else:
                min_select = st.slider("Select Min Stretch Value", min_value=0, max_value=int(5E6*unit_scalar), value=int(1E6*unit_scalar), step=10000)
        if variable_select == "Precipitation + Snowmelt":
            min_select = st.slider("Select Min Stretch Value", min_value=0, max_value=int(1E6*unit_scalar), value=int(0*unit_scalar), step=10000)
        if variable_select == "Irrigation":
            if 'DAYMET' in model_select:
                min_select = st.slider("Select Min Stretch Value", min_value=0, max_value=int(1E5*unit_scalar), value=int(0*unit_scalar), step=10000)
            else:
                min_select = st.slider("Select Min Stretch Value", min_value=0, max_value=int(1E6*unit_scalar), value=int(0*unit_scalar), step=10000)
    with viz_controls2:
        if variable_select == "Soil Water":
            if 'DAYMET' in model_select:
                max_select = st.slider("Select Max Stretch Value", min_value=0, max_value=int(1E6*unit_scalar), value=int(2.7E5*unit_scalar), step=10000)
            else:
                max_select = st.slider("Select Max Stretch Value", min_value=0, max_value=int(1E7*unit_scalar), value=int(3.5E6*unit_scalar), step=10000)
        if variable_select == "Recharge":
            if 'DAYMET' in model_select:
                max_select = st.slider("Select Max Stretch Value", min_value=0, max_value=int(5E6*unit_scalar), value=int(2E6*unit_scalar), step=10000)
            else:
                max_select = st.slider("Select Max Stretch Value", min_value=0, max_value=int(3E7*unit_scalar), value=int(2E7*unit_scalar), step=10000)
        if variable_select == "Runoff":
            if 'DAYMET' in model_select:
                max_select = st.slider("Select Max Stretch Value", min_value=0, max_value=int(1E6*unit_scalar), value=int(5E5*unit_scalar), step=10000)
            else:
                max_select = st.slider("Select Max Stretch Value", min_value=0, max_value=int(1E7*unit_scalar), value=int(5E6*unit_scalar), step=10000)
        if variable_select == "AET":
            if 'DAYMET' in model_select:
                max_select = st.slider("Select Max Stretch Value", min_value=0, max_value=int(1E7*unit_scalar), value=int(1.5E6*unit_scalar), step=10000)
            else:
                max_select = st.slider("Select Max Stretch Value", min_value=0, max_value=int(2E7*unit_scalar), value=int(1.3E7*unit_scalar), step=10000)
        if variable_select == "Precipitation + Snowmelt":
            if 'DAYMET' in model_select:
                max_select = st.slider("Select Max Stretch Value", min_value=0, max_value=int(1E7*unit_scalar), value=int(2.5E6*unit_scalar), step=10000)
            else:
                max_select = st.slider("Select Max Stretch Value", min_value=0, max_value=int(5E7*unit_scalar), value=int(3E7*unit_scalar), step=10000)
        if variable_select == "Irrigation":
            if 'DAYMET' in model_select:
                max_select = st.slider("Select Max Stretch Value", min_value=0, max_value=int(1E7*unit_scalar), value=int(1E6*unit_scalar), step=10000)
            else:
                max_select = st.slider("Select Max Stretch Value", min_value=0, max_value=int(4E7*unit_scalar), value=int(1.5E7*unit_scalar), step=10000)
        
    # --- SECTION 5: THE SPATIAL MAP (GEE) ---
    # Use geemap for GEE integration
    with st.container(width='stretch', horizontal_alignment='center'):
        try:
            # 1. Initialize State for the GEE Map
            if 'gee_last_click' not in st.session_state:
                st.session_state['gee_last_click'] = None
            # Initialize the map (centered on Utah)
            # Note: ipyleaflet is supported via geemap, but geemap.foliumap is often more stable in Streamlit
            Map = geemap.Map(center=[39.5, -111.5], zoom=7)
            Map.add_basemap('Esri.WorldShadedRelief')

            # 1. Add the Layer (Your existing logic)
            layer_name = f'{variable_select} {model_key} {year_select}'
            
            if variable_select == "Soil Water":
                Map.addLayer(image.multiply(unit_scalar), {'min': min_select, 'max': max_select, 'palette': get_palette('rdylbu')}, f'{variable_select} {model_key} {year_select}')
                palette = get_palette('rdylbu')
                # Map.add_colorbar({'min': min_select, 'max': max_select, 'palette': get_palette('rdylbu')}, label=f'Soil Water Volume ({unit_label})', position='bottomright', background_color='white')
            elif variable_select == "Recharge":
                Map.addLayer(image.multiply(unit_scalar), {'min': min_select, 'max': max_select, 'palette': get_palette('blues')}, f'{variable_select} {model_key} {year_select}')
                tick_labels = [f"{min_select:,.0f}", f"{max_select:,.0f}"]
                palette = get_palette('blues')
                # Map.add_colorbar({'min': min_select, 'max': max_select, 'palette': get_palette('blues')}, label=f'Recharge Volume ({unit_label})', position='bottomright', background_color='white', tick_labels=tick_labels)
            elif variable_select == "Runoff":
                Map.addLayer(image.multiply(unit_scalar), {'min': min_select, 'max': max_select, 'palette': get_palette('blues')}, f'{variable_select} {model_key} {year_select}')
                palette = get_palette('blues')
                # Map.add_colorbar({'min': min_select, 'max': max_select, 'palette': get_palette('blues')}, label=f'Runoff Volume ({unit_label})', position='bottomright', background_color='white')
            elif variable_select == "AET":
                Map.addLayer(image.multiply(unit_scalar), {'min': min_select, 'max': max_select, 'palette': get_palette('evapotranspiration')}, f'{variable_select} {model_key} {year_select}')
                palette = get_palette('evapotranspiration')
                # Map.add_colorbar({'min': min_select, 'max': max_select, 'palette': get_palette('evapotranspiration')}, label=f'AET Volume ({unit_label})', position='bottomright', background_color='white')
            elif variable_select == "Precipitation + Snowmelt":
                Map.addLayer(image.multiply(unit_scalar), {'min': min_select, 'max': max_select, 'palette': get_palette('blues')}, f'{variable_select} {model_key} {year_select}')
                palette = get_palette('blues')
                # Map.add_colorbar({'min': min_select, 'max': max_select, 'palette': get_palette('blues')}, label=f'Precipitation + Snowmelt Volume ({unit_label})', position='bottomright', background_color='white')
            elif variable_select == "Irrigation":
                Map.addLayer(image.multiply(unit_scalar), {'min': min_select, 'max': max_select, 'palette': get_palette('blues')}, f'{variable_select} {model_key} {year_select}')
                palette = get_palette('blues')
                # Map.add_colorbar({'min': min_select, 'max': max_select, 'palette': get_palette('blues')}, label=f'Irrigation Volume ({unit_label})', position='bottomright', background_color='white')
            # Map.add_basemap('ROADMAP')
            label_url = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}{r}.png"

        # ... (After your Map.addLayer calls) ...

            # --- CLEAN LEGEND LOGIC ---
            # 1. Determine Scale Factor (e.g., divide by 1 Million)
            #    This keeps the labels short (e.g., "5.0" instead of "5,000,000")
            if max_select >= 1_000_000:
                scale_factor = 1_000_000
                legend_unit_label = f"(1E6 {unit_label})"
            elif max_select >= 1_000:
                scale_factor = 1_000
                legend_unit_label = f"(1E3 {unit_label})"
            else:
                scale_factor = 1
                legend_unit_label = f"({unit_label})"

            # 2. Create Scaled Min/Max for the Legend ONLY
            legend_min = min_select / scale_factor
            legend_max = max_select / scale_factor

            # 3. Add the Colorbar with Scaled Values
            #    Note: We pass a new 'viz_params' dict just for this legend.
            #    The 'palette' ensures the colors match the map perfectly.
            Map.add_colorbar(
                vis_params={
                    'min': legend_min,
                    'max': legend_max,
                    'palette': palette
                },
                label=f'Per-Pixel {variable_select} Volume {legend_unit_label}',
                ticks=[legend_min, legend_max]
            ) 
        
            folium.TileLayer(
                tiles=label_url,
                attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
                name='Streets & Labels',
                overlay=True,  # <--- CRITICAL: Tells the map this is see-through
                opacity=1.0,
                control=True
            ).add_to(Map)
            # Display the map
            # Map.to_streamlit(height=800, width=1300)
            # 2. Check for Previous Click in Session State (to persist marker across re-runs)
            if st.session_state['gee_last_click']:
                lat = st.session_state['gee_last_click']['lat']
                lng = st.session_state['gee_last_click']['lng']
                # folium.Marker([lat, lng], tooltip="Selected Pixel").add_to(Map)

            # 3. Render the Map with st_folium to capture interaction
            #    We replace Map.to_streamlit() with st_folium() directly
            st.subheader("Interactive Map (Click to Query Pixel Value)", divider='gray', text_alignment='center')

            map_key = f"{model_select}_{variable_select}_{year_select}"
        # Centering Hack: 3 columns. 
            # [1, 10, 1] means small spacers on sides, wide content in middle.
            c1, c2, c3 = st.columns([1, 10, 1])
            with c2:
                # We capture the output here
                map_output = st_folium(Map, height=700, width=1300, returned_objects=["last_clicked"], key=map_key)
            
            # with st.container(width='stretch', horizontal_alignment='center'):
            # map_output = st_folium(Map, height=700, width=800, returned_objects=["last_clicked"], key=map_key)

            # 5. Handle New Clicks (The State Updater)
            if map_output['last_clicked']:
                # If the click is different from what we have stored...
                if st.session_state['gee_last_click'] != map_output['last_clicked']:
                    st.session_state['gee_last_click'] = map_output['last_clicked']
                    # st.rerun() # RELOAD PAGE to draw the marker

            # 6. Display Data (The Result Viewer)
            # This runs on the RELOADED page because it looks at session_state, not map_output
            if st.session_state['gee_last_click']:
                
                # Get coords from state
                click_lat = st.session_state['gee_last_click']['lat']
                click_lng = st.session_state['gee_last_click']['lng']
                
                # Visual separator
                st.divider()
                st.markdown(f"### 🌎 Pixel Analysis: {click_lat:.4f}, {click_lng:.4f}", text_alignment='center')
                
                # Query Earth Engine
                # Use a spinner so the user knows something is happening
                with st.spinner("Querying Earth Engine..."):
                    point = ee.Geometry.Point([click_lng, click_lat])
                    
                    # Sample the image at 1km scale
                    sample = image.reduceRegion(
                        reducer=ee.Reducer.first(), 
                        geometry=point, 
                        scale=1000,  # Match your data resolution
                        bestEffort=True
                    ).getInfo()
                    
                # Display Result

                if sample:
                    val = list(sample.values())[0]
                    if val is None:
                        st.warning("Selected pixel is masked (No Data).")
                    else:
                        # Use a big metric to show the value clearly
                        # st.metric(
                        #     label=f"{variable_select} ({year_select})", 
                        #     value=f"{val:,.0f} {unit_label}"
                        # )
                        st.markdown(f"### Value at pixel for {variable_select} of {year_select} ({model_select} member):", text_alignment='center')
                        # st.markdown(f":large[{val:,.0f} {unit_label}]", text_alignment='center')
                        st.subheader(f'''{val:,.0f} {unit_label} ''', text_alignment='center')
                else:
                    st.warning("Could not retrieve value.")
            
        except Exception as e:
            st.warning("Earth Engine not initialized or geemap not installed.")
            st.error(e)

# # --- 2. DISPLAY MAP & CAPTURE CLICK ---
# col_map, col_plot = st.columns([1, 1.5]) # Map takes 40%, Plot takes 60%

# with col_map:
#     st.subheader("Select a Watershed")
#     # This is the magic component. It renders the map and returns interaction data.
#     map_output = st_folium(m, width=None, height=600, returned_objects=["last_active_drawing"])

# # --- 3. PROCESS THE CLICK ---
# selected_id = None

# # "last_active_drawing" contains the GeoJSON of the polygon specifically clicked by the user
# if map_output["last_active_drawing"]:
#     props = map_output["last_active_drawing"]["properties"]
#     selected_id = props.get("HU_8_NAME") # Get the ID from the clicked shape

# # --- 4. LOAD & PLOT DATA ---
# with col_plot:
#     if selected_id:
#         st.subheader(f"Data for Watershed: {selected_id}")
        
#         # Load the specific optimized file for this watershed
#         # file_path = f"./app_data/{selected_id}.parquet"
        
#         # try:
#         #     df = pd.read_parquet(file_path)
            
#         #     # Create the Ribbon Graph
#         #     fig = go.Figure()
            
#         #     # Area (Ribbon)
#         #     fig.add_trace(go.Scatter(
#         #         x=df['Date'], y=df['soil_p10'],
#         #         mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'
#         #     ))
#         #     fig.add_trace(go.Scatter(
#         #         x=df['Date'], y=df['soil_p90'],
#         #         fill='tonexty', mode='lines', line=dict(width=0),
#         #         fillcolor='rgba(0,100,80,0.2)', name='10th-90th Percentile'
#         #     ))
            
#         #     # Mean Line
#         #     fig.add_trace(go.Scatter(
#         #         x=df['Date'], y=df['soil_mean'],
#         #         mode='lines', line=dict(color='teal'), name='Mean Soil Water'
#         #     ))
            
#         #     st.plotly_chart(fig, use_container_width=True)
            
#         # except FileNotFoundError:
#         #     st.error(f"Data file for {selected_id} not found.")
#     else:
#         st.info("👈 Click on a watershed in the map to view its soil water balance.")