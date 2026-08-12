import ee
import os
import sys
import time
import pandas as pd
import gcsfs
import google.auth
from datetime import date, datetime, timedelta, timezone
from RadGEEToolbox import GenericCollection
import warnings
import argparse

# Suppress pandas FutureWarnings for clean console output during long runs
warnings.simplefilter(action='ignore', category=FutureWarning)

# ---------------------------------------------------------
# AUTHENTICATION & ENVIRONMENT SETUP
# ---------------------------------------------------------
def initialize_gee():
    """Initializes Earth Engine & GCS for either Cloud Run or Local environments."""
    if os.environ.get('CLOUD_RUN_JOB'):
        print("Orchestrator: Cloud Run environment detected.")
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/earthengine', 
                    'https://www.googleapis.com/auth/cloud-platform']
        )
        ee.Initialize(credentials, project='ut-gee-ugs-uswb-dev')
    else:
        print("Orchestrator: Local environment detected.")
        service_account_path = 'C:\\Users\\mradwin\\ut-gee-ugs-uswb-dev-77ffc61a8874.json'
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = service_account_path
        
        service_account = 'ubm-swb@ut-gee-ugs-uswb-dev.iam.gserviceaccount.com'
        credentials = ee.ServiceAccountCredentials(service_account, service_account_path)
        ee.Initialize(credentials=credentials)

initialize_gee()

# ---------------------------------------------------------
#  DEFINITIONS & DICTIONARIES
# ---------------------------------------------------------
GCS_BASE_URI = "gs://ugs-uswb-dev-serving/ubm_zonal_stats"
ASSET_FOLDER = "projects/ut-gee-ugs-uswb-dev/assets/ModifiedUBM1Runs_v2/"

UT_boundary = ee.FeatureCollection("projects/ut-gee-ugs-uswb-dev/assets/Utah_Regional_Boundary").geometry()
GSL_basin = ee.FeatureCollection("projects/ut-gee-ugs-uswb-dev/assets/Utah_Watersheds/Merged_GSL_Basin_Watershed").geometry()
all_utah_watersheds = ee.FeatureCollection("projects/ut-gee-ugs-uswb-dev/assets/Utah_Watersheds/Utah_Regional_Watersheds")
all_utah_basins = ee.FeatureCollection("projects/ut-gee-ugs-uswb-dev/assets/UT_HUC6_Basin_Boundaries")

### HUC8 Watersheds
all_utah_watershed_names = all_utah_watersheds.aggregate_array('HU_8_NAME').distinct().getInfo()
watersheds_dict = {
    name.replace(',', '').replace("'", "").replace(" ", "_").replace("-", "_").replace("__", "_"): 
    ee.FeatureCollection("projects/ut-gee-ugs-uswb-dev/assets/Utah_Watersheds/Utah_Regional_Watersheds").filter(ee.Filter.eq('HU_8_NAME', name)).geometry() 
    for name in all_utah_watershed_names
}

### HUC6 Basins
all_utah_basin_names = all_utah_basins.aggregate_array('Name').distinct().getInfo()
basins_dict = {
    name.replace(',', '').replace("'", "").replace(" ", "_").replace("-", "_").replace("__", "_"): 
    ee.FeatureCollection("projects/ut-gee-ugs-uswb-dev/assets/UT_HUC6_Basin_Boundaries").filter(ee.Filter.eq('Name', name)).geometry() 
    for name in all_utah_basin_names
}

custom_regions_dict = {
    'GSL_Basin': GSL_basin,
    'UT_Statewide': UT_boundary
}

ensemble_assets = [
    'Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_NGMDGKSdM_DAYMETSNOM_ETDALEXI_IRRIm_M_mm', 
    'Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_NGMDGKSdM_DAYMETSNOM_ETEMTRIC_IRRIm_M_mm', 
    'Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_NGMDGKSdM_DAYMETSNOM_ETGSEBAL_IRRIm_M_mm', 
    'Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_NGMDGKSdM_DAYMETSNOM_ETPTJPL_IRRIm_M_mm', 
    'Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_NGMDGKSdM_DAYMETSNOM_ETSBOP_IRRIm_M_mm', 
    'Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_NGMDGKSdM_GRIDMETSNOM_ETDALEXI_IRRIm_M_mm', 
    'Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_NGMDGKSdM_GRIDMETSNOM_ETEMTRIC_IRRIm_M_mm', 
    'Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_NGMDGKSdM_GRIDMETSNOM_ETGSEBAL_IRRIm_M_mm', 
    'Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_NGMDGKSdM_GRIDMETSNOM_ETPTJPL_IRRIm_M_mm', 
    'Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_NGMDGKSdM_GRIDMETSNOM_ETSBOP_IRRIm_M_mm', 
    'Mod_UBM_1_RF800mST_POLPor_OLMFC_HHSWP_NGMDGKSdM_PRISM800mSNOM_ETDALEXI_IRRIm_M_mm', 
    'Mod_UBM_1_RF800mST_POLPor_OLMFC_HHSWP_NGMDGKSdM_PRISM800mSNOM_ETEMTRIC_IRRIm_M_mm', 
    'Mod_UBM_1_RF800mST_POLPor_OLMFC_HHSWP_NGMDGKSdM_PRISM800mSNOM_ETGSEBAL_IRRIm_M_mm', 
    'Mod_UBM_1_RF800mST_POLPor_OLMFC_HHSWP_NGMDGKSdM_PRISM800mSNOM_ETPTJPL_IRRIm_M_mm', 
    'Mod_UBM_1_RF800mST_POLPor_OLMFC_HHSWP_NGMDGKSdM_PRISM800mSNOM_ETSBOP_IRRIm_M_mm'
]

ensemble_asset_names = []
for asset in ensemble_assets:
    if 'DAYMET' in asset: precip_source = 'DAYMET'
    elif 'GRIDMET' in asset: precip_source = 'GRIDMET'
    elif 'PRISM800' in asset: precip_source = 'PRISM800m'
    else: precip_source = 'PRISM'
    
    if 'ETDALEXI' in asset: et_source = 'DISALEXI'
    elif 'ETEMTRIC' in asset: et_source = 'EEMETRIC'
    elif 'ETGSEBAL' in asset: et_source = 'GEESEBAL'
    elif 'ETPTJPL' in asset: et_source = 'PTJPL'
    elif 'ETSBOP' in asset: et_source = 'SSEBOP'
    
    ensemble_asset_names.append(f"{precip_source}_{et_source}")

ensemble_asset_dict = dict(zip(ensemble_asset_names, [ASSET_FOLDER + a for a in ensemble_assets]))

ANOMALY_TARGET_COLS = [
    'Recharge', 'Runoff', 'Soil_Water_End_Of_Previous_Timestep', 
    'Soil_Saturation_Percent_End_Of_Timestep', 'Runoff_m3', 
    'Recharge_m3', 'Soil_Water_End_Of_Previous_Timestep_m3'
]

# ---------------------------------------------------------
# HELPER FUNCTIONS WITH RETRY LOGIC
# ---------------------------------------------------------
def ee_retry_call(func, *args, max_retries=5, initial_delay=2, **kwargs):
    """Executes an Earth Engine call with exponential backoff to recover from transient API errors."""
    delay = initial_delay
    for attempt in range(1, max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries:
                print(f"      -> 🛑 EE Call failed after {max_retries} attempts.")
                raise e
            print(f"      -> ⚠️ EE API glitch detected ({e}). Retrying in {delay}s (Attempt {attempt}/{max_retries})...")
            time.sleep(delay)
            delay *= 2

def add_one_month(current_date):
    """Safely increments a date object by exactly one calendar month."""
    new_month = current_date.month % 12 + 1
    new_year = current_date.year + (current_date.month // 12)
    return date(new_year, new_month, 1)

def convert_depth_to_volume(image):
    """Calculates volumetric (m^3) bands and appends them to the image."""
    pixel_area = ee.Image.pixelArea()
    depth_bands = ee.List([
        'precip_and_snowmelt_input', 'irrigation', 'AET', 
        'Runoff', 'Recharge', 'Soil_Water_End_Of_Previous_Timestep'
    ])
    
    valid_depth_bands = image.bandNames().filter(ee.Filter.inList('item', depth_bands))
    depth_img = image.select(valid_depth_bands)
    
    volume_img = depth_img.multiply(0.001).multiply(pixel_area)
    volume_band_names = valid_depth_bands.map(lambda b: ee.String(b).cat('_m3'))
    volume_img = volume_img.rename(volume_band_names)
    
    return image.addBands(volume_img).copyProperties(image, image.propertyNames()).set(
        'system:time_start', image.get('system:time_start')
    )

def get_ee_bounds(asset_id):
    """Returns the earliest and latest available dates in an EE ImageCollection using retry logic."""
    def _fetch_bounds():
        col = ee.ImageCollection(asset_id)
        if col.size().getInfo() == 0:
            return None, None
        
        first_img = col.sort('system:time_start', True).first()
        latest_img = col.sort('system:time_start', False).first()
        
        first_date = datetime.fromtimestamp(first_img.get('system:time_start').getInfo()/1000.0, tz=timezone.utc).date()
        latest_date = datetime.fromtimestamp(latest_img.get('system:time_start').getInfo()/1000.0, tz=timezone.utc).date()
        return first_date, latest_date

    return ee_retry_call(_fetch_bounds)

def manage_backups(fs, parquet_path, max_backups=3):
    """Maintains a rolling limit of timestamped backup files."""
    if not fs.exists(parquet_path):
        return
        
    search_path = parquet_path.replace("gs://", "")
    existing_backups = fs.glob(f"{search_path}.backup_*")
    existing_backups.sort()
    
    if len(existing_backups) >= max_backups:
        num_to_delete = len(existing_backups) - max_backups + 1
        for i in range(num_to_delete):
            fs.rm(existing_backups[i])
            print(f"      -> 🗑️ Deleted old backup: {existing_backups[i]}")
            
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_backup_path = f"{parquet_path}.backup_{timestamp}"
    fs.copy(parquet_path, new_backup_path)
    print(f"      -> 💾 Created new backup: {new_backup_path}")

# ---------------------------------------------------------
# CORE PROCESSING LOGIC
# ---------------------------------------------------------
def process_region_dictionary(region_dict, dictionary_name, override_start=None, override_end=None, force_overwrite=False):
    print(f"\n\n{'='*60}\nSTARTING PROCESSING TIER: {dictionary_name}\n{'='*60}")
    
    fs = gcsfs.GCSFileSystem()
    
    bands_to_reduce = {
        'precip_and_snowmelt_input': 'mean', 'irrigation': 'mean', 'AET': 'mean',
        'Runoff': 'mean', 'Recharge': 'mean', 'Soil_Water_End_Of_Previous_Timestep': 'mean',
        'Soil_Saturation_Percent_End_Of_Timestep': 'mean', 'precip_and_snowmelt_input_m3': 'sum',
        'irrigation_m3': 'sum', 'AET_m3': 'sum', 'Runoff_m3': 'sum',
        'Recharge_m3': 'sum', 'Soil_Water_End_Of_Previous_Timestep_m3': 'sum'
    }

    is_override = bool(override_start and override_end)
    if is_override:
        print(f"🟡 MANUAL OVERRIDE DETECTED: Forcing processing from {override_start} to {override_end}")
        rewind_start = None
    else:
        today = date.today()
        if today.day == 28:
            new_month = today.month - 4
            new_year = today.year
            if new_month <= 0:
                new_month += 12; new_year -= 1
            rewind_start = date(new_year, new_month, 1)
            print(f"🔄 28TH DETECTED: Rewind window active from {rewind_start.strftime('%Y-%m')}")
        else:
            rewind_start = None

    for region_name, geometry in region_dict.items():
        print(f"\n{'='*40}\nREGION: {region_name}\n{'='*40}")
        safe_boundary_name = dictionary_name.replace(" ", "_")
        parquet_path = f"{GCS_BASE_URI}/boundary_type={safe_boundary_name}/region_name={region_name}/data.parquet"
        
        existing_pq_dates = {}
        existing_pq_ym = {}
        
        if fs.exists(parquet_path):
            with fs.open(parquet_path, 'rb') as f:
                df_existing = pd.read_parquet(f, engine='pyarrow', columns=['Date', 'Ensemble_Member'])
            
            for ens in df_existing['Ensemble_Member'].unique():
                ens_df_subset = df_existing[df_existing['Ensemble_Member'] == ens]
                existing_pq_dates[ens] = ens_df_subset['Date'].max().date()
                existing_pq_ym[ens] = set(ens_df_subset['Date'].dt.strftime('%Y-%m'))
        
        new_data_frames = []
        
        for ens_name, asset_id in ensemble_asset_dict.items():
            ee_first, ee_latest = get_ee_bounds(asset_id)
            if not ee_first:
                print(f"[{ens_name}] ⚠️ EE Collection empty or missing. Skipping.")
                continue

            operational_start = date(2005, 1, 1)
            if ee_first < operational_start:
                ee_first = operational_start
                
            ens_existing_ym = existing_pq_ym.get(ens_name, set())

            # DYNAMIC GAP DETECTION: Find missing months between ee_first and ee_latest
            all_expected_months = []
            curr = date(ee_first.year, ee_first.month, 1)
            end_boundary = date(ee_latest.year, ee_latest.month, 1)
            while curr <= end_boundary:
                all_expected_months.append(curr)
                curr = add_one_month(curr)

            missing_months = [m for m in all_expected_months if m.strftime('%Y-%m') not in ens_existing_ym]

            if is_override:
                start_obj = datetime.strptime(override_start, '%Y-%m-%d').date()
                end_obj = datetime.strptime(override_end, '%Y-%m-%d').date()
                start_ym = start_obj.strftime('%Y-%m')
                end_ym = end_obj.strftime('%Y-%m')
                
                if start_ym in ens_existing_ym and end_ym in ens_existing_ym and not force_overwrite:
                    print(f"[{ens_name}] 🟢 Override window ({start_ym} to {end_ym}) already in cache. Skipping.")
                    continue

                process_start_str = override_start
                process_end_str = (end_obj + timedelta(days=1)).strftime('%Y-%m-%d')

            elif missing_months:
                # Target the earliest missing month through the latest available date
                earliest_missing = min(missing_months)
                process_start_date = min(earliest_missing, rewind_start) if rewind_start else earliest_missing
                process_start_str = process_start_date.strftime('%Y-%m-%d')
                process_end_str = add_one_month(ee_latest).strftime('%Y-%m-%d')
                print(f"[{ens_name}] 🔍 GAP DETECTED: Missing {len(missing_months)} month(s). Fetching from {process_start_str} to {process_end_str}...")

            else:
                pq_max_date = existing_pq_dates.get(ens_name)
                if pq_max_date:
                    next_needed = add_one_month(pq_max_date)
                    process_start_date = min(next_needed, rewind_start) if rewind_start else next_needed
                else:
                    process_start_date = ee_first
                    
                if process_start_date > ee_latest:
                    print(f"[{ens_name}] 🟢 Fully up to date (Latest: {ee_latest.strftime('%Y-%m')}). Skipping.")
                    continue

                process_start_str = process_start_date.strftime('%Y-%m-%d')
                process_end_str = add_one_month(ee_latest).strftime('%Y-%m-%d')
                print(f"[{ens_name}] 🟡 Fetching Zonal Stats from {process_start_str} to {process_end_str}...")
            
            # Fetch batch stats with retry protection
            def _fetch_zonal_stats():
                ubm_col = GenericCollection(
                    collection=ee.ImageCollection(asset_id), 
                    start_date=process_start_str, 
                    end_date=process_end_str
                )

                if ubm_col.collection.size().getInfo() == 0:
                    return None
                
                ubm_col = GenericCollection(collection=ubm_col.collection.map(convert_depth_to_volume))
                scale = ubm_col.image_grab(0).projection().nominalScale().getInfo()
                actual_ee_bands = ee.Image(ubm_col.collection.first()).bandNames().getInfo()
                
                safe_band_names = []
                safe_reducer_names = []
                for b, r in bands_to_reduce.items():
                    if b in actual_ee_bands:
                        safe_band_names.append(b)
                        safe_reducer_names.append(r)
                
                return ubm_col.batch_zonal_stats(
                    geometries=geometry, 
                    band=safe_band_names, 
                    scale=scale, 
                    reducer_type=safe_reducer_names, 
                    geometry_names=[region_name]
                ), safe_reducer_names

            fetch_result = ee_retry_call(_fetch_zonal_stats)
            if not fetch_result or fetch_result[0] is None:
                print(f"      -> 🛑 No images found in date window. Skipping.")
                continue

            ens_df, safe_reducer_names = fetch_result
            
            clean_cols = {}
            for col in ens_df.columns:
                if col == 'Date': continue
                clean_name = col.replace(f"{region_name}_", "")
                for r in set(safe_reducer_names):
                    if clean_name.endswith(f"_{r}"):
                        clean_name = clean_name[:-(len(r)+1)]
                clean_cols[col] = clean_name
                
            ens_df = ens_df.rename(columns=clean_cols)
            ens_df['Date'] = pd.to_datetime(ens_df['Date'])
            float_cols = ens_df.select_dtypes(include=['float64']).columns
            ens_df[float_cols] = ens_df[float_cols].astype('float32')
            
            ens_df['Ensemble_Member'] = ens_name
            ens_df['Region'] = region_name
            
            new_data_frames.append(ens_df)
            
            # Brief pause between GEE API calls to prevent rate-limiting
            time.sleep(0.5)

        # Synchronize updates with GCS Cache
        if new_data_frames:
            combined_new_df = pd.concat(new_data_frames, ignore_index=True)

            if fs.exists(parquet_path):
                print(f"[{region_name}] 📝 Found existing cache. Fetching to unify datasets...")
                with fs.open(parquet_path, 'rb') as f:
                    existing_df = pd.read_parquet(f, engine='pyarrow')
                unified_df = pd.concat([existing_df, combined_new_df], ignore_index=True)
            else:
                print(f"[{region_name}] 🚀 Initializing entirely new Parquet database...")
                unified_df = combined_new_df

            unified_df = unified_df.drop_duplicates(subset=['Date', 'Ensemble_Member'], keep='last')

            # RECALCULATE ENSEMBLE MEAN
            print(f"[{region_name}] 📊 Recalculating Master Ensemble Mean...")
            unified_df = unified_df[unified_df['Ensemble_Member'] != 'Ensemble_Mean']
            mean_df = unified_df.groupby(['Date', 'Region']).mean(numeric_only=True).reset_index()
            mean_df['Ensemble_Member'] = 'Ensemble_Mean'
            unified_df = pd.concat([unified_df, mean_df], ignore_index=True)

            # CALCULATE CLIMATOLOGICAL ANOMALIES
            print(f"[{region_name}] 🧮 Calculating Monthly Climatological Anomalies (2005-2025)...")
            anomaly_cols = [f"{col}_anomaly" for col in ANOMALY_TARGET_COLS]
            unified_df = unified_df.drop(columns=[col for col in anomaly_cols if col in unified_df.columns], errors='ignore')
            
            unified_df['Month'] = unified_df['Date'].dt.month
            baseline_df = unified_df[(unified_df['Date'].dt.year >= 2005) & (unified_df['Date'].dt.year <= 2025)]
            
            baseline_means = baseline_df.groupby(['Ensemble_Member', 'Month'])[ANOMALY_TARGET_COLS].mean().reset_index()
            mean_cols_mapping = {col: f"{col}_mean" for col in ANOMALY_TARGET_COLS}
            baseline_means = baseline_means.rename(columns=mean_cols_mapping)
            
            unified_df = unified_df.merge(baseline_means, on=['Ensemble_Member', 'Month'], how='left')
            
            for col in ANOMALY_TARGET_COLS:
                unified_df[f"{col}_anomaly"] = (unified_df[col] - unified_df[f"{col}_mean"]).astype('float32')
            
            unified_df = unified_df.drop(columns=['Month'] + list(mean_cols_mapping.values()))

            float_cols_to_downcast = unified_df.select_dtypes(include=['float64']).columns
            unified_df[float_cols_to_downcast] = unified_df[float_cols_to_downcast].astype('float32')
            unified_df['Date_Filter'] = unified_df['Date'].dt.strftime('%Y-%m-%d')
            unified_df = unified_df.sort_values(by=['Ensemble_Member', 'Date']).reset_index(drop=True)
            
            manage_backups(fs, parquet_path, max_backups=3)
            
            with fs.open(parquet_path, 'wb') as f:
                unified_df.to_parquet(f, engine='pyarrow', index=False, compression='snappy')
                
            print(f"[{region_name}] ✅ GCS Sync Complete.")

# ---------------------------------------------------------
# EXECUTE PIPELINE WITH TRUE FAILURE EXIT CODES
# ---------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Zonal Stats Parquet Exporter.")
    parser.add_argument('--start-date', type=str, help="Manual override for start date (YYYY-MM-DD).")
    parser.add_argument('--end-date', type=str, help="Manual override for end date (YYYY-MM-DD).")
    parser.add_argument('--force-overwrite', action='store_true', help="Force recalculation even if data exists in cache.")
    args = parser.parse_args()

    try:
        process_region_dictionary(
            custom_regions_dict, "Custom Boundaries", 
            override_start=args.start_date, override_end=args.end_date,
            force_overwrite=args.force_overwrite
        )
        process_region_dictionary(
            watersheds_dict, "HUC8 Watersheds", 
            override_start=args.start_date, override_end=args.end_date,
            force_overwrite=args.force_overwrite
        )
        process_region_dictionary(
            basins_dict, "HUC6 Basins", 
            override_start=args.start_date, override_end=args.end_date,
            force_overwrite=args.force_overwrite
        )

        print("\n🎉 All processing complete. Exiting cleanly.")
        sys.exit(0)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Process interrupted by user. Safe exit triggered.")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"\n\n🛑 FATAL PIPELINE FAILURE:\n{traceback.format_exc()}")
        sys.exit(1)  # Properly triggers Cloud Run Job failure alerts