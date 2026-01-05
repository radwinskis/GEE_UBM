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

st.set_page_config(layout="wide", page_title="Utah Watersheds Viewer", page_icon="🌊") # Use full screen width

# --- CSS HACK: Remove Top Margins & Footer ---
st.markdown("""
    <style>
           /* Remove top padding */
           .block-container {
                padding-top: 1rem;
                padding-bottom: 0rem;
            }
           /* Make the plot container full width */
           .element-container {
                width: 100%;
           }
    </style>
    """, unsafe_allow_html=True)


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
if 'selected_id' not in st.session_state:
    st.session_state['selected_id'] = None
if 'last_map_clicked' not in st.session_state:
    st.session_state['last_map_clicked'] = None


# # --- MAP SECTION ---
col_map, col_plot = st.columns([1, 2])

with col_map:
    st.subheader("Select Region")
    btn_col1, btn_col2, _ = st.columns([5, 5, 8])


    with btn_col1:
        if st.button("UT Statewide"):
            st.session_state['selected_id'] = "Utah_Statewide"

    with btn_col2:
        if st.button("Entire GSL Basin"):
            st.session_state['selected_id'] = "GSL_Basin_Watershed"

    
    # Render Map
    map_output = st_folium(m, width=None, height=650, returned_objects=["last_active_drawing"])

    # --- LOGIC: HANDLE MAP CLICKS ---
    # We only update if the map click is NEW (different from the last run)
    current_click = map_output["last_active_drawing"]
    
    if current_click is not None:
        # Get the ID from the click
        clicked_id = current_click["properties"].get("HU_8_NAME")
        
        # Check if this is a *new* interaction
        # We compare the whole object or ID to what we saw last time
        if clicked_id != st.session_state['last_map_clicked']:
            st.session_state['selected_id'] = clicked_id
            st.session_state['last_map_clicked'] = clicked_id

# --- PLOTTING SECTION ---
with col_plot:
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
        st.plotly_chart(fig, use_container_width=True, theme=None)
        # print(recharge_df.head())
    else:
        st.info("👈 Select a watershed from the map OR click a button above.")

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