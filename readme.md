## GEE_UBM: Utah Soil Water Balance Model
GEE_UBM is a Python package for performing spatially distributed Soil Water Balance Utah Basin Model (UBM) calculations entirely within Google Earth Engine (GEE). It provides a standardized workflow to fetch and pre-process hydrological datasets (Precipitation, Snow-melt, Irrigation Inputs, ET, Soil Properties), harmonize them to a common grid, and run various "Bucket Model" scenarios to estimate Recharge, Runoff, and Soil Moisture dynamics.

> This is a work-in-progress. The module provides the necessary tools for running the UBM model but does not 
> contain any working files for the actual calculation of the UBM model. I will be adding this soon.

## 📦 Installation
Since this is currently a private repository, install it directly from GitHub:

```bash
pip install git+[https://github.com/radwinskis/GEE_UBM.git](https://github.com/radwinskis/GEE_UBM.git)
```

## Dependencies 
- `earthengine-api`
- `RadGEEToolbox` 
- `numpy`
- `pandas`

## Inputs for UBM model:

1) Max soil moisture (saturation volume)
    - Determined by soil porosity and thickness (available storage for water)
2) Wilting point
    - dryness level at which no more water is available to plants
3) Field capacity
    - amount of water retained by adhesion to grains and surface tension after gravity draining
4) Total soil moisture (T_soil_water)
    - instantaneous amount of water trapped in porous space of soil (?)
5) Hydraulic conductivity (K) of soil
    - rate at which fluid will flow through connected porous space
6) Available water (as input)
    - Combination of precipitation, snow-melt, and irrigation inputs
7) Evapotranspiration
    - Water lost from evaporation of soil moisture and vegetated transpiration

![soil_water_diagram.png](soil_water_diagram.png)

## Workflow notes

As the model needs spin-up time to equilibrate, models should be ran for a year prior to the timeframe of interest. 
For this reason, the model can not be iteratively ran along a continous period - the model must be ran continously for the entire timeframe of interest.
For example, do not run loops for 2005-2010, 2011-2015, etc. 
**However, this approach may cause GEE memory errors if the entire sequence of processing is done on GEE servers**

**Best practice will be processing the input collections separately, then storing those collections as assets. This way the actual UBM calculations will run flawlessly and rapidly. Export of the input collections to assets should take no longer than 30 minutes, but likely under 15 minutes.**

> The combined snowmelt + precipitation dataset is processed manually for this project, as there is no publicly available GEE asset for this dataset. **Ensure the dates that you are running the model have corresponding snowmelt + precipitation data in the asset. If new dates are needed, run the `update_snowmelt_and_precip_asset.py` script. Currently the assets have monthly images from 2004 through 2024.**

## Workflow process
**FINAL, MOST EFFICIENT AND GEE FRIENDLY WORKFLOW:**
**1)** Use `run_ubm_complete_workflow.py`, which imports `generate_ubm_inputs.py`, to select the inputs to use for the UBM input collection, select the timeframe, select the UBM model to run, choose other available settings, automatically run the UBM model, and automatically export the UBM results (including the input data) as a GEE asset. 
**2)** Run zonal statistics on the model output for timeseries analysis (`UBM_zonal_stats_script.py` or `UBM_zonal_stats_script_resume_safe.py`)
**3)** Explore data (`zonal_stats_plotting.ipynb` & `UBM_output_viewer.ipynb`)

> The workflow was changed due to GEE asset quota limitations. Exporting the input collection in addition to the output collection as separate assets was reaching GEE limits for the number of available assets (exported images). The updated workflow computes the input collection on-the-fly and exports the input images with the output images as a single asset, reducing total asset numbers. Additionally, this workflow requires less user intervention and has more automation built-in. However, the scripts for this workflow are slightly more complex and will require the user to pay close attention to any changes to the script (although many checks are implemented to prevent issues).

**Legacy alternative (not used for final workflow):**
1) Define the input image collection (`update_snowmelt_and_precip_asset.py` & `define_and_export_input_collection.py`)
2) Export the input collection to a GEE asset (`define_and_export_input_collection.py`)
3) Import the input collection asset (`run_UBM_script.py`)
4) Run the chosen UBM model (`run_UBM_script.py`)
5) Export the UBM model output as an asset (`run_UBM_script.py`)
6) Run zonal statistics on the model output for timeseries analysis (`UBM_zonal_stats_script.py`)
7) Explore data (`zonal_stats_plotting.ipynb` & `UBM_output_viewer.ipynb`)

### **Physical / Lithology Assets**

Versions of:
- Soil Thickness
    - ISRIC asset
    - gNATSGO
    - gNATSGO filled with ISRIC
    - Predicted soil thickness from machine learning trained on gNATSGO data (**primary**)
- Porosity
    - UGS asset
    - HiHydroSoil (**primary**)
    - POLARIS
- Field Capacity
    - UGS asset
    - HiHydroSoil
    - OpenLandMap (**primary**)
- Wilting point
    - UGS asset
    - HiHydroSoil (**primary**)
- Hydraulic Conductivity
    - UGS BMC asset
    - UGS Geo K asset
    - POLARIS Ksat Geo K (**primary**)
    - HiHydroSoil Ksat Geo K

### **Precipitation Collections (See Note Below)**
- Dataset sources
    - PRISM (daily and monthly) **best coverage & accuracy**
    - DAYMET (daily and monthly) **best resolution**
    - GRIDMET (daily and monthly)
    - CHIIRPS (daily and monthly)

> NOTE: The precipitation collections should be considered depreciated as we have moved to using combined snowmelt + precipitation data, combining daily snowmelt delta_SWE data with precip data to produce more accurate monthly aggregations of water inputs

### **Snow-melt Collections (See Note Below)**

Snowmelt datasets:
- ERA5 (daily and monthly)
- SMAP (daily and monthly aggregated)

Since SMAP snow melt data is ingested in three hour increments, the collection is MASSIVE. To handle this, I am exporting a daily aggregated version of the collection to an asset image collection to make future use of the data more managable and efficient. Only 3000 tasks are allowed at a time, so the export happens in two batches: 1) 2015-04-01 to 2022-12-31, and 2) 2023-01-01 to 2025-10-24 (last available SMAP date). The exported asset should already be masked to the Utah region but will need to double check.

> NOTE: The snow-melt collections should be considered depreciated as we have moved to using combined snowmelt + precipitation data, combining daily snowmelt delta_SWE data with precip data to produce more accurate monthly aggregations of water inputs

### **SNODAS + Precipitation Collections (Merged Water Inputs)**
*Depending on the value of Delta_SWE, calculation of water input varies such that `Input = Precip - Delta_SWE` for accumulation days (Delta_SWE > 0) and `Input = Precip + |Delta_SWE| * 0.9` for ablation days (Delta_SWE <= 0). The 0.9 factor accounts for sublimation losses during melt, assuming roughly 10% sublimation. The expression `Input = Precip - Delta_SWE` accounts for precipitation as rain or snow, such that there is no need to account for phase changes separately.*

SNODAS + Precipitation data sources:
- SNODAS + DAYMET (monthly)
- SNODAS + PRISM (monthly)
- SNODAS + GRIDMET (monthly) 

### **Irrigation Collection**
- Irrigation Rasters Derived From UDWR Data (monthly)
> Created by merging UDWR active and passive irrgiation water budget data for each Utah subregion (basin) and available UDWR Water Related Land Use (WRLU) shapefiles. UDWR water budget data is yearly, so assumptions were made that irrigation occurs only between april-october and the yearly values are distributed among the irrigation months and ONLY at pixels that align with WRLU data indicating locations that are irrigated. Scaling factors are applied between april-october to account for mid-summer being the peak of irrigation amounts.

### **Potential Evapotranspiration (PET) Collections**

PET data sources:
- GRIDMET (daily and monthly) **primary**
- ERA5 (daily and monthly)

### **Evapotranspiration (ET) Collections**

AET data sources:
- ERA5 (daily and monthly)
- MODIS (8-day and monthly)
- OpenET (monthly) **primary**
    - DisALEXI
    - Ensemble
    - PTJPL
    - SIMS
    - SSEBOP
    - EEMETRIC
    - GEESEBAL

### **Soil Moisture**

Soil moisture data sources:
- SMAP direct observations (daily and monthly)
- SMAP L4 model (daily and monthly)
- ERA5 (daily and monthly)
- GLDAS (daily and monthly)
- ECMWF (daily and monthly) **Forecast only - will only use if we do forecast models in the future**

**Instead of monthly sum aggregates, monthly soil moisture products grab the first image of each month as the starting condition**

## 🛠 Module Overview
### `InputCollections.py`
The "Data Factory". It allows string-based access to GEE assets without needing to memorize asset IDs.

Methods: `get_precip()`, `get_snowmelt()`, `get_PET()`, `get_AET()`, `get_soil_moisture()`, `get_static_raster()`.

Data Sources: PRISM, DAYMET, GRIDMET, CHIRPS, ERA5, SMAP, MODIS, OpenET, GLDAS.

### `helpers.py`
Contains the heavy-lifting spatial operations.

`harmonize_to_target()`: Intelligently resamples an image to match a target projection/scale.

`build_model_ready_collection()`: A robust, server-side loop that iterates through time-series collections, harmonizes them to the coarsest grid found, and attaches static soil properties to every image.

### `OriginalUBM.py` / `ModifiedUBM1.py` / `ModifiedUBM2.py`
Contain the ee.Image.iterate() logic for the specific model formulations. These models use ee.Image.where() logic to handle conditional branching (e.g., "If saturated, do X, else do Y") entirely on the server.

### `SnowMelt.py`
Module for calculating snowmelt (Delta SWE) from SNODAS data as well as calculating total water inputs (precipitation + snowmelt), accounting for precipitation type (rain or snow). Options for daily and monthly aggregations, exporting, and masking.

## 🛠 Scripts Overview

### `update_snowmelt_and_precip_asset.py`
Script for creating a GEE image collection of snowmelt + precipitation for the chosen precip data types, and exporting of the image collection to a GEE asset. Dynamically adjusts to prevent overwriting duplicate data to the asset and handles image projections to be WGS84 UTM Zone 12N. **-- Part of final workflow --** 

### `generate_ubm_inputs.py`
Helper script to pre-process the input collection to be used for running UBM models, when the input collection is not required to be a GEE asset. **-- Part of final workflow --**

### `run_ubm_complete_workflow.py`
Script that allows user to: 1) define the UBM input collection (**NOT** as an asset), 2) set the timescale of the model, 3) set output format (water height or volume), 4) specify the model to run (original UBM or modified versions), 5) run the UBM of choice (automatic based on user defined settings), 6) automatically export the UBM run to a GEE asset under a pre-defined file organization schema. Checks are performed to ensure no duplicate images are added to a GEE asset and that the user defined settings are valid. **-- Part of final workflow --**

### `define_and_export_input_collection.py`
Script for combining all the input images and image collections necessary for running the UBM model, and will export this "model ready" collection to a GEE asset. 
This script also ensures all the images are resampled/reprojected to the scale of the coarset available input. A variety of inputs exist in the script to allow specifying which version of the UBM model this collection is designed for. **-- Not necessary for final workflow --**
> This was planned to be used as part of the final workflow, but due to GEE asset quota limitations the decision was made to limit the number of GEE assets by pre-processing the UBM input collection on the fly AND incorporate the input bands with the UBM output bands.

### `run_UBM_script.py`
Script for taking the GEE asset exported by `define_and_export_input_collection.py` and running the UBM model of choice, then exports the model results to a GEE asset. **-- Not necessary for final workflow --**
> This was planned to be used as part of the final workflow, but due to GEE asset quota limitations the decision was made to limit the number of GEE assets by pre-processing the UBM input collection on the fly AND incorporate the input bands with the UBM output bands.

### `UBM_zonal_stats_script.py`
Script for extracting zonal statistics from the UBM model and input images/collections, and exports the stats to a csv. Options for calculating zonal stats for an individual watershed geometry or to loop through ALL Utah watersheds (including statewide and integrated GSL basin).
See the `Zonal_Stats_Timeseries` folder for results (**will be updated soon with final results for all watersheds between 2005-2024**).

### `UBM_zonal_stats_script_resume_safe.py`
Script for extracting zonal statistics from the UBM model and input images/collections, and exports the stats to a csv. Options for calculating zonal stats for an individual watershed geometry or to loop through ALL Utah watersheds (including statewide and integrated GSL basin).
See the `Zonal_Stats_Timeseries` folder for results (**will be updated soon with final results for all watersheds between 2005-2024**). This version is essentially identical to `UBM_zonal_stats_script.py` but allows the user to stop the process and resume later by checking which watersheds have already been processed.

## Notebooks Overview (for development and testing purposes)

### `gNATSGO_machine_learning_gap_filling_update.ipynb`
Jupyter Notebook used as the working-space for setting up, training, validating, and exporting a machine learning derived (random forest) map of root zone soil thickness throughout utah, based on gNATSGO data. 

### `UT_Irrigation_Raster_Creation.ipynb`
>Beware: This is a jumbled 'playground' notebook and is not the cleanest or easiest to read through.

Notebook used as the working-space for establishing a way to create irrigation rasters for irrigation months of 2005-2024, utilizing data from the most recent UDWR Water Budget and Water Related Land Use (WRLU) shapefiles. Creates and exports irrigation rasters to be used to account for anthropogenic introduction of water as part of the UBM model.

### `snowmelt_testing.ipynb`
Jupyter Notebook used as the working-space for testing the snowmelt + precipitation datasets, ensuring the approach used is valid.

### `preffered_inputs_model_testing.ipynb`
My own (Mark Radwin) notebook for defining the image collections for the UBM runs, and actually running the UBM models. Includes plots and thoughts.

### `UBM_runs_workspace.ipynb` 
Cleaned notebook for running the UBM models, meant to be inspected or used by anyone else. Similar to `preffered_inputs_model_testing.ipynb` but not as messy.
Probably best to just use `run_UBM_script.py` for cleanliness and consistency. 

### `UBM_output_viewer.ipynb`
Clean and simple notebook for mapping the results produced by `UBM_zonal_stats_script.py`.

### `zonal_stats_plotting.ipynb`
Clean and useful notebook for taking a zonal stats timeseries produced by `UBM_zonal_stats_script.py` and plotting.

### `asset_deletion_helper.ipynb`
Notebook to use for when an asset needs its children deleted so the asset itself can be deleted. Useful for when updates are necessary, as GEE does not allow overwriting of existing assets. 

## ⚠️ Data Units & Conventions
- **Height/Depth:** All units are standardized to millimeters (mm) (e.g., Precip, Soil Thickness, SWE).

- **Time:** Models can run on Daily or Monthly time steps, provided the input collection is aggregated correctly via the Factory.

- **Projection:** The build_model_ready_collection function automatically detects the coarsest resolution among your inputs (usually ERA5 or SMAP) and projects all finer datasets to match that grid. The CRS is always forced to `EPSG:32612` (AKA WGS84 UTM Zone 12N).

> IMPORTANT NOTE: `soil_thickness` is defined here as the depth of soil in the active root-zone, where any water infiltrating below the root-zone cannot be evaporated and will eventually be incorporated into regional aquifers. All recharge is considered `potential recharge` as we are not currently tracking the transport of water between the bottom of the root-zone and any downgradient aquifer.

## UBM logic

#### Outline of Bucket Model
Essentially breaking down the cases where inputs > storage or when inputs < storage. Multiple scenarios when inputs < storage

___________________

#### List of inputs for original model
`soil porosity`, `soil thickness`, `field capacity`, `wilting point`, `bedrock hydraulic conductivuty (K; Geo K)`, `precipitation as water`, `snowmelt`, `irrigation`, and `PET`

### <u> **Original UBM Model Workflow** - PET as Input</u>

1) `Available_Water = Precipitation + Snowmelt + Irrigation + Soil_Water_End_Of_Previous_Timestep`
    - Initial (first timestep) assumption: `Soil_Water_End_Of_Previous_Timestep = Field_Capacity`**

2) `Max_Soil_Moisture = Soil_Porosity * Soil_Thickness = Available_Void_Space`

3) `Availabile_Water_for_Recharge = Max_Soil_Moisture - Field_Capacity`

4) ### **`If (Available_Water > Max_Soil_Moisture)`**:
    - `AET = PET`
    - `Available_Water_for_Recharge = Max_Soil_Moisture - Field_Capacity`
    - `Recharge = min(Available_Water_for_Recharge, Geo_K)` - If the rock can take in all of the available water, it is all counted as recharge. If it can't, only the water it can take is counted as recharge. We will handle the leftover in the coming steps.
    - `Extra_Runoff = max(0, Available_Water_For_Recharge - Geo_K)` - Account for leftover/extra water if the rock can't take in all the available water. Use max() to avoid negative values and determine if there is extra water to be added to runoff, as runoff is determined by the soil properties rather than hydraulic conductivity.
    - `Runoff = Available_Water - Max_Soil_Moisture + Extra_runoff` 
    - `Water_In_Soil_End_of_Timestep = Available_Water - Runoff - Recharge - AET`

5) ### **`Elif (Available Water > Field Capacity)`**:
    - Enough water to fill porous voids but not force loss due to gravity. Will result in recharge and possibly runoff. 
    - `AET = PET`
    - `Available_Water_for_Recharge = Available_Water - Field_Capacity`
    - `Recharge = min(Available_Water_for_Recharge, Geo_K)` - Recharge is equal to whatever amount of water the rock can accept over the timestep. If the amount of water is smaller than the max amount rock can intake, the rock will intake all of it. If geo_K is smaller, all the rock can intake is geo_K over the timestep and some will be leftover remaining in the soil.
    - `Runoff = 0`
    - `Water_In_Soil_End_of_Timestep = Available_Water - Recharge - AET`

6) ### **`Elif (Available Water > Wilting Point)`**:
    - `AET = PET`
    - `Recharge = 0`
    - `Runoff = 0`
    - `Water_In_Soil_End_of_Timestep = Available_Water - AET`

7) ### **`Elif Available Water < Wilting Point`**:
    - `AET = 0`
    - `Recharge = 0`
    - `Runoff = 0`
    - `Water_In_Soil_End_of_Timestep = Available_Water`

8) ### `Water_In_Soil_End_of_Timestep = max(0, Water_In_Soil_End_of_Timestep)` 
    - This final step is to ensure the `Water_In_Soil_End_of_Timestep` value which will be used for the next timesteps calculation must be 0 or greater - if something wacky happens in the above calculation that makes the value go below zero. Debugging tool?

_________________________

#### **Modifications for updating models**
##### Instead of one model with 4 scenarios, I propose two additional models with three scenarios each to improve runoff and recharge estimates:

1) **Use AET as an input rather than output.** Calculates soil moisture based on the water balance, constrained by observed ET loss. It maintains internal mass consistency.
2) **Use AET and soil moisture as input.** Forces the soil moisture state to match observations at the start/end of each month. Uses observed ET to help calculate the runoff and recharge fluxes between those observed states.

_________________________

### <u>**Modified UBM Model 1 Workflow** - ET as Input</u> 👇👇👇

1) `Available_Water_Initial = Precipitation + Snowmelt + Irrigation + Soil_Water_End_Of_Previous_Timestep` - add up the input sources of water
    - For the first timestep, set the assumption: `Soil_Water_End_Of_Previous_Timestep = Field_Capacity` 

2) `Available_Water = Available_Water_Initial - min(AET, Available_Water_Initial)` - **KEY: subtract `AET` from input sources of water**, unless AET is larger then just say available water is NONE!
    - If AET is smaller than available water, AET will be subtracted from available water amounts. If it is larger, there is no water available and we make sure it is not a negative (physically impossible) value

3) `Max Soil Moisture = Soil Porosity * Soil Thickness = Available Void Space`

Now we bring in the if-else logic for the **three possible scenarios**

4) ### **`If (Available_Water > Max_Soil_Moisture)`**:
    - `Available_Water_For_Recharge = Max_Soil_Moisture - Field_Capacity`
    - `Recharge = min(Available_Water_For_Recharge, Geo_K)` - If the rock can take in all of the available water, it is all counted as recharge. If it can't, only the water it can take is counted as recharge. We will handle the leftover in the coming steps.
    - `Extra_runoff = max(0, Available_Water_For_Recharge - Geo_K)` - Account for leftover/extra water if the rock can't take in all the available water. Use max() to avoid negative values and determine if there is extra water to be added to runoff, as runoff is determined by the soil properties rather than hydraulic conductivity.
    - `Runoff = Available_Water - Max_Soil_Moisture + Extra_runoff` - Runoff is whatever the soil can't store in addition to whatever drainage waters the bedrock can't accept
    - `Water_In_Soil_End_of_Timestep = Field_Capacity` - This is the water stored in the soil following recharge and runoff. **`Water_In_Soil` will be carried over to the next timestep rather than act as an output, but this is a useful output regardless!** In this scenario, the soil is effectively saturated in water but no longer draining.

5) ### **`Else If (Available_Water > Field_Capacity)`**:
    - `Available_Water_for_recharge = Available_Water - Field_Capacity` - same as the first scenario
    - `Recharge = min(Available_Water_for_Recharge, Geo_K)` - Recharge is equal to whatever amount of water the rock can accept over the timestep. If the amount of water is smaller than the max amount rock can intake, the rock will intake all of it. If geo_K is smaller, all the rock can intake is geo_K over the timestep and some will be leftover remaining in the soil.
    - `Runoff = 0`
    - `Water_In_Soil_End_of_Timestep = Available_Water - Recharge` - Whatever water that was in the soil that was unable to get absorbed into the underlying bedrock over this timestep will remain in the soil. **`Water_In_Soil` will be carried over to the next timestep rather than act as an output, but this is a useful output regardless!**

6) ### **`Else If (Available_Water <= Field_Capacity)`**:
    - `Runoff = 0`
    - `Recharge = 0`
    - `Water_In_Soil_End_of_Timestep = Available_Water` - In this scenario, whatever water was available is within the limit of only being accepted by the soil through adhesion and trapping. No runoff or recharge possible.

7) ### `Water_In_Soil_End_of_Timestep = max(0, Water_In_Soil_End_of_Timestep)` 
    - This final step is to ensure the `Water_In_Soil_End_of_Timestep` value which will be used for the next timesteps calculation must be 0 or greater - if something wacky happens in the above calculation that makes the value go below zero. Debugging tool?


______________________________________

### <u>**Modified UBM Model 2 Workflow** - ET & Soil Moisture Data as Inputs</u> 👇👇👇

1) `Available_Water_Initial = Precipitation + Snowmelt + Irrigation + Soil_Water_Profile_Data_From_Beginning_of_Timestep` - add up the input sources of water, **KEY: this time using soil moisture information from observations or other models** instead of a water balance approach

2) `Available_Water = Available_Water_Initial - min(AET, Available_Water_Initial)` - **KEY: subtract `AET` from input sources of water**, unless AET is larger then just say available water is NONE!
    - If AET is smaller than available water, AET will be subtracted from available water amounts. If it is larger, there is no water available and we make sure it is not a negative (physically impossible) value

3) `Max Soil Moisture = Soil Porosity * Soil Thickness = Available Void Space`

Now we bring in the if-else logic for the **three possible scenarios**

4) ### **`If (Available_Water > Max_Soil_Moisture)`**:
    - `Available_Water_for_Recharge = Max_Soil_Moisture - Field_Capacity`
    - `Recharge = min(Available_Water_for_Recharge, Geo_K)` - If the rock can take in all of the available water, it is all counted as recharge. If it can't, only the water it can take is counted as recharge. We will handle the leftover in the coming steps.
    - `Extra_runoff = max(0, Available_Water_For_Recharge - Geo_K)` - Account for leftover/extra water if the rock can't take in all the available water. Use max() to avoid negative values and determine if there is extra water to be added to runoff, as runoff is determined by the soil properties rather than hydraulic conductivity.
    - `Runoff = Available_Water - Max_Soil_Moisture + Extra_runoff` - Runoff is whatever the soil can't store in addition to whatever drainage waters the bedrock can't accept

5) ### **`Else If (Available_Water > Field_Capacity)`**:
    - `Available_Water_for_Recharge = Available_Water - Field_Capacity`
    - `Recharge = min(Available_Water_for_Recharge, Geo_K)` - Recharge is equal to whatever amount of water the rock can accept over the timestep. If the amount of water is smaller than the max amount rock can intake, the rock will intake all of it. If geo_K is smaller, all the rock can intake is geo_K over the timestep and some will be leftover remaining in the soil.
    - `Runoff = 0`

6) ### **`Else If (Available_Water <= Field_Capacity)`**:
    - `Runoff = 0`
    - `Recharge = 0`

- *In this model, `Water_In_Soil_End_of_Timestep` is not reported or utilized. However, it may be useful to still calculate and store `Water_In_Soil_End_of_Timestep` to compare with `Soil_Water_Profile_Data_From_Beginning_of_Timestep` of the following timestep.*