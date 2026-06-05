import ee 
import os
import google.auth
from RadGEEToolbox import GenericCollection
from GEE_UBM import OriginalUBMRun, ModifiedUBM1Run, ModifiedUBM2Run, check_merged_collection
from generate_ubm_inputs_for_update import get_ubm_input_collection, get_abbreviation_dicts
from datetime import datetime, date, timedelta, timezone
import calendar
import argparse


#-----------------------------------------------------------#
################### AVAILABLE OPTIONS #######################
#-----------------------------------------------------------#
# Copy these strings into the configuration section below or use list indexing

soil_thickness_options = [
    'Random_Forest_Utah_Model_30m', 'Random_Forest_Utah_Model_800m', 'Random_Forest_Utah_Model_1km', 'ISRIC', 'gNATSGO', 
    'gNATSGO_filled', 'gNATSGO_filled_2_meter_cap'
]
porosity_options = ['HiHydroSoilPorosity', 'POLARIS_porosity', 'UGS_porosity']
field_capacity_options = ['UGS_fieldCap', 'HiHydroSoilFieldCap', 'OpenLandMapFieldCap']
wilting_point_options = ['UGS_wiltingPoint', 'HiHydroSoilWiltPoint']
Geo_K_options = [
    'POLARIS_K_Sat_monthly', 'POLARIS_K_Sat_monthly_scaled', 'POLARIS_K_Sat_daily', 'POLARIS_K_Sat_daily_scaled', 'HiHydroSoil_K_Sat_monthly', 
    'HiHydroSoil_K_Sat_monthly_scaled', 'HiHydroSoil_K_Sat_daily', 'HiHydroSoil_K_Sat_daily_scaled', 'UGS_Geo_K_monthly', 'UGS_Geo_K_daily', 
    'USGS_Geo_K_monthly', 'USGS_Geo_K_daily', 'USGS_NGMD_GeoK_Scaled_Monthly'
]
PET_options = ['GRIDMET_daily_PET', 'GRIDMET_monthly_PET', 'ERA5_daily_PET', 'ERA5_monthly_PET']
soil_moisture_options = [
    'SMAP_daily_soil', 'SMAP_monthly_soil', 'SMAP_daily_soil_aggregate', 
    'SMAP_monthly_soil_aggregate', 'ERA5_daily_soil_moisture', 
    'ERA5_monthly_soil_moisture', 'GLDAS_daily_soil_moisture', 
    'GLDAS_monthly_soil_moisture'
]
# --- Static Raster Selection ---

porosity_raster = porosity_options[1] #1 (POLARIS) is calibrated
field_capacity_raster = field_capacity_options[2] #2 (OpenLandMap) is calibrated
wilting_point_raster = wilting_point_options[1] #1 (HiHydroSoil) is calibrated
Geo_K_raster = Geo_K_options[-1] #-1 (USGS_NGMD_GeoK_Scaled_Monthly) is calibrated


snowmelt_and_precip_options = [
    'DAYMET_SNODAS_combined_inputs_monthly', 'PRISM_SNODAS_combined_inputs_monthly', 'PRISM800m_SNODAS_combined_inputs_monthly',
    'GRIDMET_SNODAS_combined_inputs_monthly'
]
irrigation_options = [
    'UT_UDWR_irrigation_inputs_monthly_scaled_30m', 'UT_UDWR_irrigation_inputs_monthly_scaled_30m_v2'
]
AET_options = ['OPEN_ET_DisALEXI','OPEN_ET_PTJPL', 'OPEN_ET_SSEBOP', 'OPEN_ET_EEMETRIC', 'OPEN_ET_GEESEBAL']


UBM_model_options = ['Original_UBM', 'Modified_UBM_1', 'Modified_UBM_2', 'Modified_UBM_1_Testing_Updates']
resampling_options = ['bilinear', 'focal_mean', 'reduceResolution']

def add_one_month(current_date):
    """Safely increments a date object by exactly one calendar month."""
    new_month = current_date.month % 12 + 1
    new_year = current_date.year + (current_date.month // 12)
    return date(new_year, new_month, 1)


def get_processing_dates(override_start=None, override_end=None):
    """
    Determines the dynamic start and end dates based on the current day of the month.
    - On the 28th: 4-month rolling rewind.
    - Any other day (e.g., the 8th): 1-month update.
    """
    # 1. Local Testing Override
    if override_start and override_end:
        print("🟡 USING MANUAL DATE OVERRIDE")
        end_obj = datetime.strptime(override_end, '%Y-%m-%d').date() + timedelta(days=1)
        end_date = end_obj.strftime('%Y-%m-%d')
        return override_start, end_date
        
    today = date.today()
    
    # 2. End date is ALWAYS the last day of the previous calendar month
    last_day_prev_month = today.replace(day=1) - timedelta(days=1)
    end_date_str = last_day_prev_month.strftime('%Y-%m-%d')
    
    # 3. Start date changes depending on the execution day
    if today.day == 28:
        print("🔄 28TH DETECTED: Executing 4-Month Rolling Rewind")
        # Subtract 4 months from current month to get the starting month
        new_month = today.month - 4
        new_year = today.year
        
        # Handle year wrap-around (e.g., if we run this in Feb, go back to Oct of previous year)
        if new_month <= 0:
            new_month += 12
            new_year -= 1
            
        start_date_str = date(new_year, new_month, 1).strftime('%Y-%m-%d')
    else:
        print("⏩ STANDARD RUN DETECTED: Executing 1-Month Update")
        start_date_str = last_day_prev_month.replace(day=1).strftime('%Y-%m-%d')
        
    return start_date_str, end_date_str

def main(high_res_implementation=False, start_date=None, end_date=None, aet_subset=None, precip_subset=None):
    """
    Main function to generate UBM inputs, run the model, and export results.
    This script is designed to be flexible for different configurations of the UBM model in a cloud environment.
    """
    #------------------------------------------------------#
    ############## INITIALIZE EARTH ENGINE #################
    #------------------------------------------------------#
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

    global_start_date, global_end_date = get_processing_dates(start_date, end_date)

    print(f"Processing Window: {global_start_date} to {global_end_date}")

    # --- Model Selection ---
    UBM_model_to_use = UBM_model_options[1] # 'Modified_UBM_1' ⚠️⚠️

    # --- Processing Options ---
    monthly_time_step = True  # True for monthly, False for daily
    convert_to_volume = False  # True to export volume (m^3), False for depth (mm)
    high_res_30m_implementation = high_res_implementation  # True to use 30m as global model resolution
    resampling_method = resampling_options[1] # 'focal_mean'

    # Filter loop options based on command line subset arguments
    precip_loop_list = [p.strip() for p in precip_subset.split(',')] if precip_subset else snowmelt_and_precip_options
    aet_loop_list = [a.strip() for a in aet_subset.split(',')] if aet_subset else AET_options

    # Loop through the available precip datasets
    for precip_dataset in precip_loop_list:
        snowmelt_and_precip = precip_dataset

        if high_res_30m_implementation:
            target_scale = 30
        else:
            if snowmelt_and_precip == 'DAYMET_SNODAS_combined_inputs_monthly':
                target_scale = 1000
            elif snowmelt_and_precip == 'PRISM_SNODAS_combined_inputs_monthly':
                target_scale = 4000
            elif snowmelt_and_precip == 'GRIDMET_SNODAS_combined_inputs_monthly':
                target_scale = 4000
            elif snowmelt_and_precip == 'PRISM800m_SNODAS_combined_inputs_monthly':
                target_scale = 800

        if target_scale == 30:
            soil_thickness_raster = soil_thickness_options[0] # 30m
        elif target_scale == 800:
            soil_thickness_raster = soil_thickness_options[1] # 800m
        elif target_scale == 1000:
            soil_thickness_raster = soil_thickness_options[2] # 1km
        elif target_scale == 4000:
            soil_thickness_raster = soil_thickness_options[2] # 1km
        else:
            soil_thickness_raster = soil_thickness_options[2] # Default to 1km if scale is unrecognized

        irrigation = irrigation_options[1] #v2  
        PET_input = PET_options[0]            # Used for Original_UBM
        for aet_dataset in aet_loop_list:
            AET_input = aet_dataset
            # AET_input = AET_options[9]            # Used for Modified_UBM_1 & 2 
            soil_moisture_input = soil_moisture_options[0] # Used for Modified_UBM_2

            # print(f'Using the following configuration: {UBM_model_to_use}, {resampling_method}, Monthly Time Step: {monthly_time_step}')
            # print(f'Static Rasters: {{Soil Thickness: {soil_thickness_raster}, Porosity: {porosity_raster}, Field Capacity: {field_capacity_raster}, Wilting Point: {wilting_point_raster}, Geo K: {Geo_K_raster}}}')
            # print(f'Dynamic Inputs: {{Snowmelt+Precip: {snowmelt_and_precip}, Irrigation: {irrigation}, PET: {PET_input}, AET: {AET_input}, Soil Moisture: {soil_moisture_input}}}')

            print(f"\n{'='*60}")
            print(f"EVALUATING MODEL: {snowmelt_and_precip} | {AET_input}")
            print(f"{'='*60}")

            st_dict, dyn_dict = get_abbreviation_dicts()
            # Helper to safely get abbrev
            def get_abbr(d, key):
                return d.get(key, 'Unknown')

            static_part = f"{get_abbr(st_dict, soil_thickness_raster)}_{get_abbr(st_dict, porosity_raster)}_{get_abbr(st_dict, field_capacity_raster)}_{get_abbr(st_dict, wilting_point_raster)}_{get_abbr(st_dict, Geo_K_raster)}"

            if UBM_model_to_use == 'Original_UBM':
                asset_folder = 'projects/ut-gee-ugs-bsf-dev/assets/Original_UBM_Runs_v2/'
                dyn_part = f"{get_abbr(dyn_dict, snowmelt_and_precip)}_{get_abbr(dyn_dict, PET_input)}_{get_abbr(dyn_dict, irrigation)}"
                model_prefix = 'Orig_UBM_'
            elif UBM_model_to_use == 'Modified_UBM_1':
                asset_folder = 'projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs_v2/'
                dyn_part = f"{get_abbr(dyn_dict, snowmelt_and_precip)}_{get_abbr(dyn_dict, AET_input)}_{get_abbr(dyn_dict, irrigation)}"
                model_prefix = 'Mod_UBM_1_'
            elif UBM_model_to_use == 'Modified_UBM_2':
                asset_folder = 'projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM2Runs_v2/'
                dyn_part = f"{get_abbr(dyn_dict, snowmelt_and_precip)}_{get_abbr(dyn_dict, AET_input)}_{get_abbr(dyn_dict, soil_moisture_input)}_{get_abbr(dyn_dict, irrigation)}"
                model_prefix = 'Mod_UBM_2_'
                
            suffix = '_M' if monthly_time_step else '_D'
            model_suffix = '_m3' if convert_to_volume else '_mm'
            asset_name = f"{asset_folder}{model_prefix}{static_part}_{dyn_part}{suffix}{model_suffix}"

            # Create the parent collection if it doesn't exist
            try:
                ee.data.createAsset({'type': 'ImageCollection'}, asset_name)
                print(f"Verified/Created ImageCollection: {asset_name}")
            except Exception:
                pass # Already exists

            # Check history and fetch resume state
            resume_state_image = None
            actual_start_date = global_start_date

            try:
                existing_col = ee.ImageCollection(asset_name)
                size = existing_col.size().getInfo()
                
                if size > 0:
                    # Find the absolute latest image in the collection
                    latest_image = existing_col.sort('system:time_start', False).first()
                    latest_millis = latest_image.get('system:time_start').getInfo()
                    latest_date = datetime.fromtimestamp(latest_millis / 1000.0, tz=timezone.utc).date()
                    
                    # Calculate the month immediately following the latest image
                    next_needed_month = add_one_month(latest_date)
                    
                    # Convert global_start_date to a date object for comparison
                    target_start_obj = datetime.strptime(global_start_date, '%Y-%m-%d').date()
                    
                    # Compare dates to determine the action
                    if next_needed_month < target_start_obj:
                        print(f" -> MASSIVE GAP DETECTED: Asset is stuck at {latest_date.strftime('%Y-%m')}.")
                        print(f"    Overriding scheduled start date to catch up from {next_needed_month.strftime('%Y-%m')}.")
                        actual_start_date = next_needed_month.strftime('%Y-%m-%d')
                        resume_state_image = latest_image
                    else:
                        print(" -> Asset is up-to-date. Executing scheduled rewind logic.")
                        # Fetch the image strictly BEFORE the scheduled rewind date
                        resume_state_image = existing_col.filterDate('1900-01-01', actual_start_date).sort('system:time_start', False).first()
                else:
                    raise ValueError("Empty Collection")
                    
            except Exception:
                print(f" -> Collection missing or empty. Overriding start date to initialize from scratch (2004-01-01).")
                actual_start_date = '2004-01-01'
                resume_state_image = None

            UT_boundary = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Regional_Boundary").geometry()

            # --------------------------------------------------------- #
            # 3. GENERATE INPUTS & RUN MODEL
            # --------------------------------------------------------- #
            print(f" -> Generating inputs from {actual_start_date} to {global_end_date}...")

            input_collection_wrapper = get_ubm_input_collection(
                start_date=actual_start_date,
                end_date=global_end_date,
                UBM_model_to_use=UBM_model_to_use,
                monthly_time_step=monthly_time_step,
                resampling_method=resampling_method,
                target_scale=target_scale,
                soil_thickness_raster=soil_thickness_raster,
                porosity_raster=porosity_raster,
                field_capacity_raster=field_capacity_raster,
                wilting_point_raster=wilting_point_raster,
                Geo_K_raster=Geo_K_raster,
                snowmelt_and_precip_collection=snowmelt_and_precip,
                irrigation_collection=irrigation,
                PET_collection=PET_input,
                AET_collection=AET_input,
                soil_moisture_collection=soil_moisture_input
            )

            input_col = input_collection_wrapper.collection
            
            try:
                # Find the actual latest available image in the input data
                latest_input_image = input_col.sort('system:time_start', False).first()
                latest_input_millis = latest_input_image.get('system:time_start').getInfo()
                latest_input_date = datetime.fromtimestamp(latest_input_millis / 1000.0, tz=timezone.utc).date()
                
                # We add one month (and then set day=1) to create an exclusive end date boundary for the filters
                max_available_end_date_obj = add_one_month(latest_input_date)
                max_available_end_str = max_available_end_date_obj.strftime('%Y-%m-%d')
                
                target_end_obj = datetime.strptime(global_end_date, '%Y-%m-%d').date()
                
                if max_available_end_date_obj <= target_end_obj:
                    print(f" -> 🛑 PROVIDER BOUNDARY DETECTED: {snowmelt_and_precip} only has data through {latest_input_date.strftime('%Y-%m')}.")
                    print(f"    Bounding processing window. Will not process past {latest_input_date.strftime('%Y-%m')}.")
                    # Safely clip the global end date to match reality
                    global_end_date = max_available_end_str
                
                # Check if the start date is now pushed past the available end date
                start_check_obj = datetime.strptime(actual_start_date, '%Y-%m-%d').date()
                if start_check_obj >= max_available_end_date_obj:
                     print(f" -> ⏭️ Model is completely up-to-date with available provider data. Skipping UBM run.")
                     continue # Skips to the next ensemble member!
                     
            except Exception as e:
                 print(f" -> ⚠️ Warning: Could not verify input data boundary. Proceeding with scheduled dates. Details: {e}")


            if UBM_model_to_use == 'Modified_UBM_1':
                ubm_run = ModifiedUBM1Run(
                    model_ready_collection=input_collection_wrapper, 
                    resume_state_image=resume_state_image, 
                    start_date=actual_start_date, 
                    end_date=global_end_date
                )
            elif UBM_model_to_use == 'Modified_UBM_2':
                ubm_run = ModifiedUBM2Run(
                    model_ready_collection=input_collection_wrapper, 
                    resume_state_image=resume_state_image
                )
            elif UBM_model_to_use == 'Original_UBM':
                ubm_run = OriginalUBMRun(
                    model_ready_collection=input_collection_wrapper, 
                    resume_state_image=resume_state_image
                )
            else:
                raise ValueError(f"Invalid UBM Model Selected: {UBM_model_to_use}")
            
            output_col = ubm_run.collection

            if convert_to_volume:
                def convert_depth_to_volume(image):
                    """Converts pixel values from depth (mm) to volume (m^3)."""
                    pixel_area = ee.Image.pixelArea()
                    outputs_for_conversion = image.select(['Runoff', 'Recharge', 'Soil_Water_End_Of_Previous_Timestep'])
                    outputs_not_for_conversion = image.select(['Soil_Saturation_Percent_End_Of_Timestep'])
                    depth_in_meters = outputs_for_conversion.multiply(0.001)
                    volume_m3 = pixel_area.multiply(depth_in_meters)
                    return volume_m3.addBands(outputs_not_for_conversion).copyProperties(image, image.propertyNames())
                output_col = output_col.map(convert_depth_to_volume)

            ### zipping version of join_collections - MUCH faster
            def join_collections(inputs, outputs):
                """
                Joins input and output collections by INDEX (Zipping) instead of TIME (Joining).
                This avoids the massive overhead of scanning timestamps in a deep dependency chain.
                """
                # 1. Convert both collections to Lists
                # This locks them into their current order.
                # Since 'outputs' came from iterating 'inputs', they are guaranteed aligned.
                list_inputs = inputs.toList(inputs.size())
                list_outputs = outputs.toList(outputs.size())
                
                # 2. Zip them together
                # Creates a list of pairs: [[In1, Out1], [In2, Out2], ...]
                zipped = list_inputs.zip(list_outputs)
                
                # 3. Merge bands for each pair
                def merge_pair(pair):
                    pair = ee.List(pair)
                    input_img = ee.Image(pair.get(0))
                    output_img = ee.Image(pair.get(1))
                    
                    # Merge and copy properties from the input (which has the safe/clean metadata)
                    return input_img.addBands(output_img).copyProperties(input_img, input_img.propertyNames())
                
                return ee.ImageCollection(zipped.map(merge_pair))
            
            final_collection = join_collections(input_col, output_col).filterDate(actual_start_date, global_end_date)
            image_list = final_collection.toList(final_collection.size())
            num_images = image_list.size().getInfo()
            
            print(f" -> Queueing {num_images} targeted Upsert export tasks...")

            filtered_input_col = input_col.filterDate(actual_start_date, global_end_date)
            filtered_dates_list = filtered_input_col.aggregate_array('Date_Filter').getInfo()

            for i in range(num_images):
                img = ee.Image(image_list.get(i))
                img_date_str = filtered_dates_list[i]
                asset_id = f"{asset_name}/{model_prefix}{img_date_str}"
                print(f"    - Queueing export for {img_date_str} to {asset_id}...")
                try:
                    ee.data.deleteAsset(asset_id)
                    print(f"    - Deleting outdated timestep {img_date_str} for clean overwrite.")
                except Exception:
                    pass 
                
                task = ee.batch.Export.image.toAsset(
                    image=img,
                    description=f"UBM_{dyn_part}_{img_date_str}",
                    assetId=asset_id,
                    region=UT_boundary,
                    crs='EPSG:32612',
                    scale=target_scale,
                    maxPixels=1e13
                )
                task.start()
                print(f"    - Export task started for {img_date_str}.")
            print(f" -> Tasks submitted successfully for {AET_input}!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the UBM Automated Updater.")
    parser.add_argument('--high-res', action='store_true', help="Flag to run the 30m high-resolution version of the model. Options: True or False")
    parser.add_argument('--start-date', type=str, help="Manual override for start date (YYYY-MM-DD).")
    parser.add_argument('--end-date', type=str, help="Manual override for end date (YYYY-MM-DD).")
    
    # New Batching Overrides
    parser.add_argument('--precip-subset', type=str, help="Comma-separated list of Precip datasets to process. Options: DAYMET_SNODAS_combined_inputs_monthly, PRISM_SNODAS_combined_inputs_monthly, PRISM800m_SNODAS_combined_inputs_monthly, GRIDMET_SNODAS_combined_inputs_monthly")
    parser.add_argument('--aet-subset', type=str, help="Comma-separated list of AET datasets to process. Options: OPEN_ET_DisALEXI, OPEN_ET_PTJPL, OPEN_ET_SSEBOP, OPEN_ET_EEMETRIC, OPEN_ET_GEESEBAL")
    
    args = parser.parse_args()
    
    main(
        high_res_implementation=args.high_res, 
        start_date=args.start_date, 
        end_date=args.end_date,
        precip_subset=args.precip_subset,
        aet_subset=args.aet_subset
    )