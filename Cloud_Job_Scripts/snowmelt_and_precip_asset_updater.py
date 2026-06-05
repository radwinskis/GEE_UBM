import ee 
import google.auth
import os
from datetime import date, datetime, timedelta, timezone
from GEE_UBM import InputCollections, SnowMeltCollection
import calendar

def get_target_dates():
    """
    Goal: Determines the boundary of the most recently completed calendar month.
    Workflow: Takes today's date, steps back to the last day of the previous month, 
              and then identifies the first day of that same previous month.
    Returns:
        target_month_start (date): The 1st day of the previous month.
        target_month_end (date): The last day of the previous month.
    """
    today = date.today()
    target_month_end = today.replace(day=1) - timedelta(days=1)
    target_month_start = target_month_end.replace(day=1)
    return target_month_start, target_month_end

def add_one_month(current_date):
    """
    Goal: Safely increments a date object by exactly one calendar month.
    Workflow: Uses modular arithmetic to add one month while handling year-end 
              rollovers (December to January) without third-party libraries.
    Args:
        current_date (date): The base date to increment.
    Returns:
        date: A new date object set to the 1st day of the following month.
    """
    new_month = current_date.month % 12 + 1
    new_year = current_date.year + (current_date.month // 12)
    return date(new_year, new_month, 1)

def get_dataset_config(precip_data_type):
    """
    Goal: Maps the requested precipitation dataset to its corresponding GEE asset 
          path and required temperature band.
    Workflow: Uses if/elif logic to route the standard 4km datasets and the new 800m dataset.
    Args:
        precip_data_type (str): The name of the precipitation collection.
    Returns:
        asset_name (str): The full GEE asset path for the export collection.
        temp_band (str): The specific temperature band required to calculate rain/snow partitioning.
    """
    target_scale = None  # Default to native scale
    if precip_data_type == 'PRISM_daily_precip':
        asset_name = 'projects/ut-gee-ugs-bsf-dev/assets/UT_Precip_and_Snowmelt_Image_Collections/UT_SNODAS_PRISM_PRECIP_PLUS_SNOWMELT_5KM_UBM_INPUT'
        temp_band = 'PRISM_daily_temp'
        target_scale = 4000
    elif precip_data_type == 'DAYMET_daily_precip':
        asset_name = 'projects/ut-gee-ugs-bsf-dev/assets/UT_Precip_and_Snowmelt_Image_Collections/UT_SNODAS_DAYMET_PRECIP_PLUS_SNOWMELT_1KM_UBM_INPUT'
        temp_band = 'DAYMET_daily_temp'
        target_scale = 1000
    elif precip_data_type == 'GRIDMET_daily_precip':
        asset_name = 'projects/ut-gee-ugs-bsf-dev/assets/UT_Precip_and_Snowmelt_Image_Collections/UT_SNODAS_GRIDMET_PRECIP_PLUS_SNOWMELT_5KM_UBM_INPUT'
        temp_band = 'GRIDMET_daily_temp'
        target_scale = 4000
    elif precip_data_type == 'PRISM800m_daily_precip':
        asset_name = 'projects/ut-gee-ugs-bsf-dev/assets/UT_Precip_and_Snowmelt_Image_Collections/UT_SNODAS_PRISM_PRECIP_PLUS_SNOWMELT_800M_UBM_INPUT'
        temp_band = 'PRISM800m_daily_temp'
        target_scale = 800  
    else:
        raise ValueError("Invalid precip_data_type provided.")
        
    return asset_name, temp_band, target_scale

def main(override_start_date=None, override_end_date=None):
    """
    Goal: Automatically loops through multiple Precipitation/Snowmelt datasets and updates them.
    Workflow: 
        1. Iterates over GRIDMET, PRISM (4km), DAYMET, and PRISM (800m).
        2. Queries the existing GEE asset. If empty/missing, starts from 2004.
        3. Calculates the gap between the latest asset and the previous calendar month.
        4. If gap > 1 month, generates a multi-month GenericCollection batch export.
        5. If gap == 1 month, generates an optimized single-month ee.ImageCollection sum export.
    """
    if os.environ.get('CLOUD_RUN_JOB'):
        print("Detected Cloud Run environment. Using default credentials.")
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/earthengine', 
                    'https://www.googleapis.com/auth/cloud-platform']
        )
        ee.Initialize(credentials, project='ut-gee-ugs-bsf-dev')
    else:
        print("Detected local environment. Using JSON service account key.")
        service_account = 'localpythonscripts@ut-gee-ugs-bsf-dev.iam.gserviceaccount.com'
        credentials = ee.ServiceAccountCredentials(service_account, 'C:\\Users\\mradwin\\ut-gee-ugs-bsf-dev-53dcc5d729e0.json')
        ee.Initialize(credentials=credentials)

    boundary = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Regional_Boundary").geometry()
    
    # Datasets to process (now includes PRISM 800m)
    datasets_to_process = [
        'PRISM_daily_precip', 
        'DAYMET_daily_precip', 
        'GRIDMET_daily_precip', 
        'PRISM800m_daily_precip'
    ]
    
    # Target Dates (The month that just finished)
    # target_month_start, target_month_end = get_target_dates()
    if override_start_date and override_end_date:
        print(f"\n🟡 MANUAL OVERRIDE DETECTED: Forcing processing from {override_start_date} to {override_end_date}")
        override_start_obj = datetime.strptime(override_start_date, '%Y-%m-%d').date()
        override_end_obj = datetime.strptime(override_end_date, '%Y-%m-%d').date()
        
        # Set the finish line to the 1st of the end month so the while loop behaves correctly
        target_month_start = override_end_obj.replace(day=1) 
        is_override = True
    else:
        # Standard Daily Sensor Mode
        target_month_start, target_month_end = get_target_dates()
        is_override = False

    for precip_data_type in datasets_to_process:
        print(f"\n{'='*50}")
        print(f"EVALUATING DATASET: {precip_data_type}")
        print(f"{'='*50}")
        
        asset_name, temp_band , target_scale = get_dataset_config(precip_data_type)
        
        # Create a clean prefix for task names (e.g., 'PRISM800m' instead of just 'PRISM')
        model_prefix = precip_data_type.replace('_daily_precip', '')

        if is_override:
            # Bypass GEE gap-checking completely and force the start date
            current_fill_date = override_start_obj
            print(f"Bypassing GEE gap-check. Forcing start at: {current_fill_date.strftime('%Y-%m')}")

        else:
            # Check existing collection or default to 2004
            try:
                ee.data.getAsset(asset_name) # Throws exception if missing
                monthly_col = ee.ImageCollection(asset_name)
                
                if monthly_col.size().getInfo() == 0:
                    raise ValueError("Collection exists but is empty.")
                    
                latest_image = monthly_col.sort('system:time_start', False).first()
                latest_millis = latest_image.get('system:time_start').getInfo()
                latest_dt = datetime.fromtimestamp(latest_millis / 1000.0, tz=timezone.utc)
                latest_date = date(latest_dt.year, latest_dt.month, 1)
                print(f"Latest available data is from: {latest_date.strftime('%Y-%m')}")
                
            except Exception as e:
                print(f"Asset missing or empty. Initializing from scratch (2004). Details: {e}")
                # Set to Dec 2003 so add_one_month() pushes process_start to Jan 2004
                latest_date = date(2003, 12, 1) 

            # Define the first month we need to process
            current_fill_date = add_one_month(latest_date)

        ### Execute the loop
        
        if current_fill_date > target_month_start:
            print(f"{model_prefix} collection is completely up to date! Skipping...")
            continue

        # Process exactly ONE month at a time until we catch up to the target date
        while current_fill_date <= target_month_start:
            
            fill_year = current_fill_date.year
            fill_month = current_fill_date.month
            
            # Find the last day of THIS specific month
            last_day = calendar.monthrange(fill_year, fill_month)[1]
            
            start_date_str = f"{fill_year}-{fill_month:02d}-01"
            end_date_str = f"{fill_year}-{fill_month:02d}-{last_day:02d}"
            
            print(f" -> Queueing processing for {start_date_str} to {end_date_str}...")

            # Fetch Base Collections for just this month
            base = SnowMeltCollection(start_date=start_date_str, end_date=end_date_str, geometry=boundary)
            inputs = InputCollections(start_date=start_date_str, end_date=end_date_str, soil_thickness_raster='Random_Forest_Utah_Model_1km')
            
            # temperature = inputs.get_temperature(name=temp_band)
            # precip = inputs.get_precip(name=precip_data_type)

            # EAFP Approach: Try to fetch the data, break the loop if the provider data is exhausted
            try:
                temperature = inputs.get_temperature(name=temp_band)
                precip = inputs.get_precip(name=precip_data_type)
            except ee.ee_exception.EEException as e:
                # Catch the specific GEE "null image" error indicating an empty collection
                if "Parameter 'image' is required and may not be null" in str(e):
                    print(f" -> Halting queue for {model_prefix}: Provider data not yet available for {start_date_str}.")
                    break  # Exits the while loop and safely moves to the next dataset in your for loop
                else:
                    raise e  # Re-raise if it is an unrelated GEE server/quota error


            delta_swe = base.calculate_daily_delta_swe()

            soil_water_input = base.calculate_daily_soil_input(
                precip_collection=precip, 
                temp_collection=temperature, 
                delta_swe_collection=delta_swe,
                target_scale=target_scale
            )

            actual_days = soil_water_input.collection.size().getInfo()
            if actual_days < last_day:
                print(f" -> Halting queue for {model_prefix}: Incomplete data for {start_date_str} "
                      f"(found {actual_days}/{last_day} days). Provider data not fully available yet.")
                break  # Exit the while loop to wait for the next run

            # Because we restricted the bounds to exactly 1 month, we can always use the fast .sum() method!
            soil_water_input_scale = ee.Number(soil_water_input.image_grab(0).projection().nominalScale()).getInfo()
            monthly_sum_image = soil_water_input.collection.sum()
            
            new_timestamp = ee.Date(start_date_str).millis()
            monthly_sum_image = monthly_sum_image.rename('precip_and_snowmelt_input').set({
                'system:time_start': new_timestamp,
                'year': fill_year,
                'month': fill_month,
                'Date_Filter': start_date_str
            })
            
            #check if asset_name exists, if not break the loop
            if not ee.data.getAsset(asset_name):
                print(f" -> Asset {asset_name} does not exist. Halting queue for {model_prefix}.")
                break
            else:
                asset_id = f"{asset_name}/{fill_year}-{fill_month:02d}-01"
                
                try:
                    ee.data.deleteAsset(asset_id)
                except ee.EEException:
                    pass
                    
                task = ee.batch.Export.image.toAsset(
                    image=monthly_sum_image,
                    description=f"export_{model_prefix}_{fill_year}_{fill_month:02d}",
                    assetId=asset_id,
                    region=boundary,
                    scale=soil_water_input_scale,
                    crs='EPSG:32612',
                    maxPixels=1e13
                )
                task.start()
                
                # Step forward one month for the next iteration of the loop
                current_fill_date = add_one_month(current_fill_date)
            
        print(f"All catch-up tasks submitted for {model_prefix}.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the Precip & Snowmelt Updater.")
    parser.add_argument('--start-date', type=str, help="Manual override for start date (YYYY-MM-DD).")
    parser.add_argument('--end-date', type=str, help="Manual override for end date (YYYY-MM-DD).")
    args = parser.parse_args()
    
    main(override_start_date=args.start_date, override_end_date=args.end_date)