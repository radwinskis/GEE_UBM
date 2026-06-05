## GEE_UBM: Utah Soil Water Balance Model
GEE_UBM is a Python package for performing spatially distributed Soil Water Balance Utah Basin Model (UBM) calculations entirely within Google Earth Engine (GEE). It provides a standardized workflow to fetch and pre-process hydrological datasets (Precipitation, Snow-melt, Irrigation Inputs, ET, Soil Properties), harmonize them to a common grid, and run various "Bucket Model" scenarios to estimate Recharge, Runoff, and Soil Moisture dynamics.

By utilizing Google Earth Engine via the Python API, all heavy spatial processing, resampling, and iterative math are handled on Google's cloud servers. This means you do not need a powerful local computer to run statewide, high-resolution hydrological models.

## 📦 Installation
Since this is currently a private repository, install it directly from GitHub:

```bash
pip install git+[https://github.com/radwinskis/GEE_UBM.git](https://github.com/radwinskis/GEE_UBM.git)
```

**Pip installation options will be available soon**

## Dependencies 
- `earthengine-api`
- `RadGEEToolbox` 
- `numpy`
- `pandas`
- `google-auth`

## Inputs for UBM model:

If you are unfamiliar with hydrological "bucket" models, it helps to imagine the soil column as a physical bucket filled with a sponge. Water enters the top, gets pulled out by the sun and plants, and whatever is left either drains out the bottom (recharge) or spills over the top (runoff). 

Here are the core physical constraints that define our bucket:

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

*(Note: `soil_thickness` is defined here as the depth of soil in the active root-zone. Any water infiltrating below this zone cannot be evaporated and is counted as potential regional recharge.)*

![soil_water_diagram.png](soil_water_diagram.png)

## Workflow notes

**Model Spin-Up and State Resumption**
If you are initiating a brand-new model from scratch (e.g., starting in 2004), the model needs about a year of spin-up time to allow the soil moisture conditions to equilibrate with the climate forcings. 

Traditionally, this would mean the model can not be iteratively run and has to process the entire timeframe in one massive continuous loop. **However, you can split computations or perform incremental updates using the `resume_state_image` parameter, if desired**. 

* By passing the final output image of a previous run into the model initialization, the script automatically extracts the `Soil_Water_End_Of_Previous_Timestep` (along with Runoff and Recharge states) to perfectly seed the next computation. 
* The automated `ubm_updater_script.py` handles this dynamically: it queries your target GEE asset folder for the latest completed month and uses that image as the `resume_state_image` to seamlessly pick up exactly where it left off without needing a new spin-up period.

**Computational Best Practices**
Even with state resumption, performing the entire sequence of complex hydrological processing (like snowmelt partitioning) on-the-fly can cause GEE memory errors. 
**Best practice is to process heavy model intermediate inputs separately, then store those collections as GEE assets before the main UBM step.** This breaks the computational chain, ensuring the actual iterative UBM calculations run flawlessly and rapidly. 

> **⚠️IMPORTANT: It is recommended to export model results to a GEE asset, or else calling a single image from the model will cause GEE to redo a large computation chain just for a single image and will be VERY SLOW⚠️** Computation chains for this model can be very large (for example, GEE has to keep track of all previous results for every calculation unless a boundary condition is met to reset conditions)

**Updating the Pre-Calculated Snowmelt + Precipitation Asset**
The combined snowmelt + precipitation dataset must be pre-calculated because there is no publicly available GEE asset that merges these dynamics. 
* **Do not use the outdated manual scripts to update this data.** * Instead, this is now handled entirely by `snowmelt_and_precip_asset_updater.py`. 
* In a production environment, `daily_ubm_orchestrator.py` automatically acts as a sensor and triggers this updater script the moment new PRISM and SNODAS data are published. 
* If you need to backfill data or process a custom timeframe, you can trigger the script manually by supplying `override_start_date` and `override_end_date` arguments (See the *Scripts & Modules Overview* section below).

---

### The "Orchestrated" Workflow: Why & How We Automated

The model is run using highly optimized, automated updater scripts designed for daily cron jobs or Cloud Run execution, and allowing for local usage. It processes data "on-the-fly" where possible, relies on pre-calculated intermediate assets to break up massive computation chains, and merges inputs and outputs into single assets to drastically reduce quota usage.

#### The Temporal Schedule
The `daily_ubm_orchestrator.py` operates on a dual-branch schedule:

1.  **Branch 1: 6-Month Rolling Rewind (The 28th of every month)**
    * *Why?* Scientific data providers often revise their datasets months after the initial release to improve accuracy. To capture these revisions, the orchestrator triggers a deep 6-month historical backfill on the 28th of each month.
    * This forces updates to the intermediate assets (irrigation, snowmelt/precipitation) and the main UBM calculations over a 6-month window.

2.  **Branch 2: Daily Sensor Mode (All other days)**
    * The orchestrator acts as an automated sensor, pinging external GEE catalogs (like PRISM or OpenET) to see if the previous month's data has been published yet.
    * If the required data is missing, the pipeline safely halts and tries again tomorrow.
    * If the data is ready, it triggers the UBM updaters to process just that newest month of data, keeping the model perpetually up-to-date.

#### The Step-by-Step Processing Pipeline (What Actually Happens)
For every timestep processed, the automated scripts follow a strict computational pipeline to ensure stability and efficiency:

1.  **Step 1: Intermediate Export of Precip + Snowmelt (Breaking the Chain)**
    * Calculating Snow Water Equivalent (SWE) deltas and temperature-partitioning rain vs. snow is incredibly computationally expensive. To prevent Earth Engine from timing out during the final UBM calculation, we pre-calculate this combined water input. 
    * The updater scripts calculate the combined input and export it as an intermediate GEE asset. This "breaks the computational chain," providing the main UBM model with a lightweight, flattened image to read from.
2.  **Step 2: Generation of Irrigation Data**
    * Anthropogenic water inputs are a critical component of the Utah water balance. The pipeline relies on irrigation rasters generated from the Utah Division of Water Resources (UDWR) shapefiles and tabular water budget datasets. 
    * *Note: The baseline processing for transforming these UDWR polygons and tables into distributed gridded data is documented in the `UT_Irrigation_Raster_Creation.ipynb` file*. The pipeline dynamically forward-fills this data for current timesteps.
3.  **Step 3: Harmonization (The Data Factory)**
    * The `generate_ubm_inputs_for_update.py` script takes the pre-calculated intermediate assets, alongside external data like OpenET, and passes them to `helpers.py`.
    * This step identifies the coarsest spatial resolution among the inputs, aligns all pixel grids (`EPSG:32612`), standardizes units to millimeters, and bundles the static soil properties (like porosity and hydraulic conductivity) into the time-series.
4.  **Step 4: The UBM Calculation & Zipping**
    * The harmonized data is passed to `ModifiedUBM1.py`, which iterates through time, running the bucket math (detailed below) pixel-by-pixel.
    * *Optimization:* To save memory, the output results (Recharge, Runoff, Soil Moisture) are attached back to the input bands by **INDEX (Zipping)** rather than by evaluating deep timestamp matches. 
5.  **Step 5: Targeted Upsert Export**
    * Finally, the script saves the fully combined Input + Output image via a targeted `Upsert` export task to the GEE catalog, cleanly overwriting outdated timesteps and keeping asset limits low.

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

---

Following extensive calibration and validation, the model specifically targets the following datasets for production runs:

| Parameter | Calibrated Asset Source |
| :--- | :--- |
| **Soil Thickness** | Random_Forest_Utah_Model_1km (Custom ML map derived from gNATSGO) |
| **Porosity** | POLARIS_porosity |
| **Field Capacity** | OpenLandMapFieldCap |
| **Wilting Point** | HiHydroSoilWiltPoint |
| **Geo_K (Hydraulic Cond.)** | USGS_NGMD_GeoK_Scaled_Monthly |
| **Water Inputs** | PRISM_SNODAS_combined_inputs_monthly (Intermediate Pre-calculated Asset) |
| **Irrigation** | UT_UDWR_irrigation_inputs_monthly_scaled_30m_v2 (Derived from UDWR) |
| **Actual ET (AET)** | OPEN_ET_EEMETRIC (and other OpenET ensemble members) |

---

---

### 🛠 Scripts & Modules Overview

#### Core Processing Modules (The Logic)
* **`InputCollections.py`:** The "Data Factory". Allows string-based access to complex GEE collections (PRISM, OpenET, etc.) without memorizing asset IDs. It resamples and standardizes all inputs into unified metric units (mm).
* **`helpers.py`:** Contains spatial harmonization logic (`harmonize_to_target()`). It orchestrates a robust server-side loop that matches all time-series imagery to the coarsest grid found, ensuring pixels perfectly align before math is applied.
* **`ModifiedUBM1.py`:** Contains the core `ee.Image.iterate()` logic. This is where the actual water balance math is executed pixel-by-pixel.
* **`SnowMelt.py`:** Handles the complex physics of snowpack changes, partitioning daily soil inputs based on temperature thresholds.

#### Operational Scripts (The Automation)
* **`daily_ubm_orchestrator.py`:** The main entry point. Manages the dual-branch schedule and acts as the data-sensor trigger.
* **`ubm_updater_script.py`:** Initializes Earth Engine, handles the targeted export batching, manages the zipping of input/output collections, and pushes the final UBM arrays to your GEE asset folder.
* **`generate_ubm_inputs_for_update.py`:** Helper script that wraps the Data Factory modules to pre-process the model-ready input collection before passing it to the math functions.

#### Post-Processing Scripts
* **`ubm_zonal_stats_script_resume_safe.py`:** Script that loops through ROI's and exports zonal statistics tables to designated folders. Adapted to safeuly handle computation interruptions and resume where exports left off. 



### Command Line Execution & Overrides

While the `daily_ubm_orchestrator.py` is designed to run automatically, you can manually trigger the individual updater scripts from the terminal. This is useful for testing, backfilling specific temporal gaps, or targeting specific dataset combinations.

The `ubm_updater_script.py` accepts command-line arguments to override the automated date sensing and isolate specific Precipitation or Actual Evapotranspiration (AET) datasets. 

Below are examples of how to format these terminal commands:

```bash
# Example 1: Run the UBM Updater for a specific year using single precip and AET datasets
python Cloud_Job_Scripts/ubm_updater_script.py \
  --start-date "2023-01-01" \
  --end-date "2023-12-31" \
  --precip-subset "PRISM_SNODAS_combined_inputs_monthly" \
  --aet-subset "OPEN_ET_EEMETRIC"

# Example 2: Run the UBM Updater to process an ensemble of AET datasets simultaneously (comma-separated)
python Cloud_Job_Scripts/ubm_updater_script.py \
  --start-date "2023-01-01" \
  --end-date "2023-12-31" \
  --precip-subset "DAYMET_SNODAS_combined_inputs_monthly" \
  --aet-subset "OPEN_ET_PTJPL, OPEN_ET_SSEBOP, OPEN_ET_DisALEXI"

# Example 3: Run the high-resolution (30m) flag alongside date overrides
python Cloud_Job_Scripts/ubm_updater_script.py \
  --high-res \
  --start-date "2023-01-01" \
  --end-date "2023-12-31"

# Example 4: Manually trigger the Snowmelt & Precip intermediate asset updater for a specific timeframe
python snowmelt_and_precip_asset_updater.py \
  --start-date "2023-01-01" \
  --end-date "2023-12-31"
```

---

## Notebooks Overview (for development and testing purposes)

### `gNATSGO_machine_learning_gap_filling_update.ipynb`
Jupyter Notebook used as the working-space for setting up, training, validating, and exporting a machine learning derived (random forest) map of root zone soil thickness throughout utah, based on gNATSGO data. 

### `UT_Irrigation_Raster_Creation.ipynb`
>Beware: This is a jumbled 'playground' notebook and is not the cleanest or easiest to read through.

Notebook used as the working-space for establishing a way to create irrigation rasters for irrigation months of 2005-2024, utilizing data from the most recent UDWR Water Budget and Water Related Land Use (WRLU) shapefiles. Creates and exports irrigation rasters to be used to account for anthropogenic introduction of water as part of the UBM model.


### `asset_deletion_helper.ipynb`
Notebook to use for when an asset needs its children deleted so the asset itself can be deleted. Useful for when updates are necessary, as GEE does not allow overwriting of existing assets. 

## ⚠️ Data Units & Conventions
- **Height/Depth:** All units are standardized to millimeters (mm) (e.g., Precip, Soil Thickness, SWE).

- **Time:** Models can run on Daily or Monthly time steps, provided the input collection is aggregated correctly via the Factory.

- **Projection:** The build_model_ready_collection function automatically detects the coarsest resolution among your inputs and projects all finer datasets to match that grid. The CRS is always forced to `EPSG:32612` (AKA WGS84 UTM Zone 12N). Scale can be provided as an argument to override this behavior and export at your desired resolution. 

> IMPORTANT NOTE: `soil_thickness` is defined here as the paramaterized depth of soil in the active root-zone, where any water infiltrating below the root-zone cannot be evaporated and will eventually be incorporated into regional aquifers. All recharge is considered `potential recharge` as we are not currently tracking the transport of water between the bottom of the root-zone and any downgradient aquifer. Furthermore, `soil_thickness` is a parameterized value based on gNATSGO data and does not represent the true thickness of soil, rather the necessary thickness of soil for the model results to best match the calibration datasets. 

## UBM logic

#### Outline of Bucket Model
Essentially breaking down the cases where inputs > storage or when inputs < storage. Multiple scenarios when inputs < storage

___________________

#### List of inputs for original model
`soil porosity`, `soil thickness`, `field capacity`, `wilting point`, `bedrock hydraulic conductivuty (K; Geo K)`, `precipitation as water`, `snowmelt`, `irrigation`, and `PET`



_________________________

#### **Modifications for updating models**
##### Instead of one model with 4 scenarios, I propose two additional models with three scenarios each to improve runoff and recharge estimates:

1) **Use AET as an input rather than output.** Calculates soil moisture based on the water balance, constrained by observed ET loss. It maintains internal mass consistency.
2) **Use AET and soil moisture as input.** Forces the soil moisture state to match observations at the start/end of each month. Uses observed ET to help calculate the runoff and recharge fluxes between those observed states.

_________________________

### Modified UBM 1

The production model ("Modified UBM 1") uses **Actual Evapotranspiration (AET)** as a forcing *input* rather than calculating it as an output. By using satellite-observed AET, we constrain the soil moisture based on the known water balance, maintaining strict internal mass consistency. 

Here is the exact server-side mathematical logic executed for every single pixel at every timestep within `ModifiedUBM1.py`:

**1. Initial Setup & ET Offset**
* `Available_Water_Initial = precip_and_snowmelt_input + irrigation + Soil_Water_End_Of_Previous_Timestep` 
* `ET_offset = min(AET, Available_Water_Initial)` *(Safety check: If the sun tries to evaporate more water than physically exists in the soil, we cap the evaporation at the available water amount to prevent negative water volumes).*
* `Available_Water = Available_Water_Initial - ET_offset` 
* `Max_Soil_Moisture = soil_porosity * soil_thickness` 

**2. Scenario 1: Saturated Soil (`Available_Water > Max_Soil_Moisture`)**
* *The bucket is overflowing.*
* `Available_Water_for_Recharge_Scenario_1 = Max_Soil_Moisture - field_capacity`
* `Recharge_Scenario_1 = min(Available_Water_for_Recharge_Scenario_1, Geo_K)` *(Water drains into the bedrock, but is bottlenecked by the rock's permeability).*
* `S_intermediate = Available_Water - Recharge_Scenario_1` *(Calculate what is left after the rock drains).*
* `Runoff_Scenario_1 = max(0, S_intermediate - Max_Soil_Moisture)` *(Whatever still doesn't fit in the bucket becomes surface runoff).*
* `Soil_Water_End_Of_Previous_Timestep_Scenario_1 = Max_Soil_Moisture` *(The soil is left completely saturated).*

**3. Scenario 2: Draining Soil (`Available_Water > field_capacity`)**
* *The bucket is full enough to drain, but not overflowing.*
* `Available_Water_for_Recharge_Scenario_2 = Available_Water - field_capacity`
* `Recharge_Scenario_2 = min(Available_Water_for_Recharge_Scenario_2, Geo_K)`
* `Runoff_Scenario_2 = 0` *(No spillover).*
* `Soil_Water_Raw_2 = Available_Water - Recharge_Scenario_2`
* *GEE Memory Optimization:* If the bedrock's drain capacity (`Geo_K`) is strictly greater than the soil's gravity-drainable zone (`Max_Soil_Moisture - field_capacity`), the drain pipe is so large that it is physically impossible for water to remain above field capacity. The model detects this and forces the final soil water to equal the static `field_capacity` map. This immediately breaks the computation chain, saving massive amounts of GEE memory limits.

**4. Scenario 3: Retaining Soil (`Available_Water <= field_capacity`)**
* *The sponge is just damp. Water is held too tightly by surface tension to drain.*
* `Recharge_Scenario_3 = 0` 
* `Runoff_Scenario_3 = 0` 
* `Soil_Water_End_Of_Previous_Timestep_Scenario_3 = Available_Water` *(All water simply stays in the soil for the next timestep).*

---
##### Included in the package are other modules to calculate the original UBM and 2nd modified version. However, these models are not used for our production model but are included regardless for reference. Note, if you would like to adapt the original or 2nd modified version, the available module logic should be updated to closer match the logic and operations performed using the Modified UBM 1 module.

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

---

### <u>**Modified UBM Model 2 Workflow** - ET & Soil Moisture Data as Inputs</u> 

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


---

### 🌍 Adapting GEE_UBM for Other Regions (e.g., Colorado, Nevada)

While GEE_UBM was built and calibrated specifically for Utah, the underlying bucket-model physics and the automated cloud-pipeline architecture are completely agnostic to location. Most of the dynamic meteorological forcing datasets (like PRISM, DAYMET, OpenET, and SMAP) provide full contiguous United States (CONUS) or global coverage. 

However, to run this model in a different region, you will need to update several hardcoded boundaries, custom static assets, and project configurations. Here is a step-by-step guide on how to adapt the codebase for a new area of interest:

#### 1. Earth Engine Initialization & Credentials
The orchestration scripts currently authenticate using a specific Google Cloud Project and service account.
* **Files to modify:** `daily_ubm_orchestrator.py` and `ubm_updater_script.py`.
* **Action:** In the `initialize_gee()` function (or at the top of the updater script), change the `project='ut-gee-ugs-bsf-dev'` string to your own Google Cloud Project ID. If running locally, you must also update the path to your `.json` service account key file.

#### 2. Redefining the Region of Interest (ROI)
The pipeline heavily utilizes a master polygon to mask imagery and reduce computational overhead.
* **Files to modify:** `InputCollections.py` and `generate_ubm_inputs_for_update.py`.
* **Action:** * In `InputCollections.py`, locate the `_get_shapefiles()` class method. Replace the asset ID for `'Utah_Regional_Boundary'` with your own Earth Engine FeatureCollection (e.g., a shapefile of Colorado).
  * The scripts use `.clip(self.Utah_Regional_Boundary)` extensively throughout the data factory to crop rasters. By updating the source shapefile, these clips will automatically apply to your new region.
  * In `generate_ubm_inputs_for_update.py`, update the `UT_boundary` variable to point to your new region's asset ID, as this is used to dictate the bounds of the final export.

#### 3. Swapping Static Soil & Lithology Assets
While precipitation and ET data are drawn from national catalogs, the static maps (like Soil Thickness or Bedrock Hydraulic Conductivity) in this repository are highly customized Utah models.
* **Files to modify:** `InputCollections.py`.
* **Action:** You must supply your own regional rasters for Soil Thickness, Porosity, Field Capacity, Wilting Point, and Geo_K.
  * Look inside `_get_soil_thickness_raster()` and `get_static_raster()`.
  * Replace the GEE asset paths (e.g., `"projects/ut-gee-ugs-bsf-dev/assets/Utah_USGS_NGMD_Geomaterials_GeoK_m_per_month_100m"`) with your own regional data. 
  * Ensure your custom assets are ingested into Earth Engine and scaled appropriately. If your data is in different units, you will need to adjust the mathematical conversions in these functions (e.g., converting porosity to volumetric percentage, or hydraulic conductivity to mm/day).

#### 4. Customizing Irrigation Inputs
Anthropogenic water addition (irrigation) is highly localized. The current repository uses a custom monthly raster stack derived from the Utah Division of Water Resources (UDWR).
* **Files to modify:** `InputCollections.py`.
* **Action:** In the `get_irrigation()` function, you will need to replace the `UT_UDWR_irrigation_inputs_monthly_scaled_30m_v2` asset with a custom dataset representing your region's irrigation patterns. This typically requires taking local state agricultural shapefiles and water budget tabular data, and distributing those volumes across the irrigation season.

#### 5. SnowMelt Module and Intermediate Exports
Because calculating Snow Water Equivalent (SWE) deltas is computationally expensive, the pipeline exports an intermediate asset of combined Rain + Snowmelt before running the main UBM math.
* **Files to modify:** The script you use to trigger the SnowMelt export (e.g., `snowmelt_and_precip_asset_updater.py` or directly interacting with `SnowMelt.py`).
* **Action:** When instantiating the `SnowMeltCollection` class, pass your new regional geometry. When calling the `export_collection()` wrapper, ensure you change the `asset_path` argument so it exports the intermediate dataset to your own GEE project folder instead of the hardcoded Utah directory.

#### 6. Updating the UBM Export Paths
Finally, the model needs to know where to save the completed hydrological arrays.
* **Files to modify:** `ubm_updater_script.py`.
* **Action:** In the `main()` function, locate the `asset_folder` string assignments (e.g., `'projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs_v2/'`). Update these paths to point to an ImageCollection folder you own in Earth Engine.