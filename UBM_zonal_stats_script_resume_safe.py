import ee 
from RadGEEToolbox import GenericCollection, LandsatCollection, get_palette
from GEE_UBM import InputCollections, build_model_ready_collection, OriginalUBMRun, ModifiedUBM1Run, ModifiedUBM2Run, check_merged_collection
import geemap
import numpy as np
import pandas as pd
import os
#------------------------------------------------------#

include_separate_meteoric_inputs = False
include_combined_meteoric_inputs = True

convert_meteoric_depth_to_volume = True

# Resume options: skip regions with existing output files
resume_skip_existing = True

manually_set_region_for_zonal_stats = False

if include_separate_meteoric_inputs:
    print("Including meteoric inputs (AET and Precipitation + Snowmelt) in zonal statistics.")
elif include_combined_meteoric_inputs:
    print("Including combined meteoric inputs (Precipitation + Snowmelt) in zonal statistics.")
else:
    print("Excluding meteoric inputs from zonal statistics.")

if convert_meteoric_depth_to_volume:
    print("User set `convert_meteoric_depth_to_volume = True`. Converting meteoric inputs (AET, precipitation + snowmelt, and irrigation) from depth (mm) to volume (m^3).")
else:
    print("Keeping meteoric inputs (AET, precipitation + snowmelt, and irrigation) in depth (mm).")

start_date = '2004-12-31'
end_date = '2024-12-31'

def convert_depth_to_volume(image):
    """
    Converts pixel values from depth (mm) to volume (cubic meters).
    
    Formula: Area (m^2) * Depth (mm) / 1000 (mm/m) = Volume (m^3)
    """
    # 1. Calculate area of each pixel in square meters
    pixel_area = ee.Image.pixelArea()
    
    # 2. Convert depth to meters (mm / 1000)
    depth_in_meters = image.multiply(0.001)
    
    # 3. Calculate volume
    volume_m3 = pixel_area.multiply(depth_in_meters)
    
    return volume_m3.copyProperties(image, image.propertyNames()).set(
        'system:time_start', image.get('system:time_start'),
        'Date_Filter', image.get('Date_Filter')
    )

#------------------------------------------------------#
############## INITIALIZE EARTH ENGINE #################
#------------------------------------------------------#
service_account = 'localpythonscripts@ut-gee-ugs-bsf-dev.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'C:\\Users\\mradwin\\ut-gee-ugs-bsf-dev-53dcc5d729e0.json')
ee.Initialize(credentials=credentials)

####### STATIC DEFINITIONS #######
UT_boundary = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Regional_Boundary").geometry()
GSL_basin = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Watersheds/Merged_GSL_Basin_Watershed").geometry()
castle_valley_watershed = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Watersheds/Castle_Valley_Watershed").geometry()
milford_watershed = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Watersheds/Milford_Watershed").geometry()
sanpete_watershed = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Watersheds/Sanpete_Watershed").geometry()

all_utah_watersheds = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Watersheds/Utah_Regional_Watersheds")
all_utah_watershed_names = all_utah_watersheds.aggregate_array('HU_8_NAME').distinct().getInfo()
all_utah_watershed_names_cleaned = [
        name.replace(',', '').replace("'", "").replace(" ", "_").replace("-", "_") .replace("__", "_") 
        for name in all_utah_watershed_names
    ]

regions_dict = {
    'UT': UT_boundary,
    'GSL_Basin_Watershed': GSL_basin,
    'Castle_Valley_Watershed': castle_valley_watershed,
    'Milford_Watershed': milford_watershed,
    'Sanpete_Watershed': sanpete_watershed
}

# ⚠️⚠️⚠️🌐🌐🌐 USER INPUT: Select the region for zonal statistics ⚠️⚠️⚠️
zonal_stats_region = 'GSL_Basin_Watershed' # Change this to the desired region for zonal statistics ⚠️⚠️⚠️
# ⚠️⚠️⚠️🌐🌐🌐

if zonal_stats_region not in regions_dict and manually_set_region_for_zonal_stats:
    raise ValueError(f"Region '{zonal_stats_region}' not found in regions_dict. Please add it before proceeding.")
if manually_set_region_for_zonal_stats:
    print(f"Calculating zonal statistics for region: {zonal_stats_region}")

if zonal_stats_region == 'UT':
    folder_id = 'Utah_Statewide'
elif zonal_stats_region == 'GSL_Basin_Watershed':
    folder_id = 'GSL_Basin'
elif zonal_stats_region == 'Castle_Valley_Watershed':
    folder_id = 'Castle_Valley'
elif zonal_stats_region == 'Milford_Watershed':
    folder_id = 'Milford'
elif zonal_stats_region == 'Sanpete_Watershed':
    folder_id = 'Sanpete'

#------------------------------#
###### PRIMARY USER INPUT ###### ⚠️⚠️⚠️
#------------------------------#
input_UBM_collection_asset_id = 'projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Mod_UBM_1_RF1kmST_POLPor_OLMFC_HHSWP_POLKsatM_PRISMSNOM_ETPTJPL_IRRIm_M_m3' 

asset_name = input_UBM_collection_asset_id.split('/')[-1]

asset_id_of_input_col_used_for_UBM_run = 'projects/ut-gee-ugs-bsf-dev/assets/Aggregated_Modified1_UBM_Input_Collections/UT_RF1kmST_POLARISPor_OLMFC_HHSWP_POLARISKsatM_DAYMETSNODASM_OPENETEEMETRIC_M'

if manually_set_region_for_zonal_stats:
    output_folder_for_csv = f'C:\\Users\\mradwin\\Documents\\Utah Soil Water Balance\\Zonal_Stats_Timeseries\\{folder_id}\\'

    output_path_for_csv = f'{output_folder_for_csv}{asset_name}_Zonal_Stats_{zonal_stats_region}.csv'

    print(f"Output CSV will be saved to: {output_path_for_csv}")

    # Check if path folder exists, if not create it
    if not os.path.exists(output_folder_for_csv):
        print(f"Output folder {output_folder_for_csv} does not exist. Creating it.")
        os.makedirs(output_folder_for_csv)


######## DYNAMIC DEFINITIONS ########
UBM_collection = GenericCollection(collection=ee.ImageCollection(input_UBM_collection_asset_id), start_date=start_date, end_date=end_date)

scale = UBM_collection.image_grab(0).projection().nominalScale().getInfo()

print(f"Using scale of {scale} meters for zonal statistics.")

model_ready_collection_asset = ee.ImageCollection(asset_id_of_input_col_used_for_UBM_run).map(convert_depth_to_volume) if include_separate_meteoric_inputs else None
model_ready_collection_asset = GenericCollection(collection=model_ready_collection_asset, start_date=start_date, end_date=end_date) if include_separate_meteoric_inputs else None

######## ZONAL STATISTICS ##########
print("Starting zonal statistics calculations...")
def run_manual_zonal_stats_and_save_to_csv():
    recharge = UBM_collection.iterate_zonal_stats(geometries=regions_dict[zonal_stats_region], band='Recharge', scale=scale, reducer_type='sum', geometry_names=[f'{zonal_stats_region}'])

    runoff = UBM_collection.iterate_zonal_stats(geometries=regions_dict[zonal_stats_region], band='Runoff', scale=scale, reducer_type='sum', geometry_names=[f'{zonal_stats_region}'])

    soil_water = UBM_collection.iterate_zonal_stats(geometries=regions_dict[zonal_stats_region], band='Soil_Water_End_Of_Previous_Timestep', scale=scale, reducer_type='sum', geometry_names=[f'{zonal_stats_region}'])

    if include_separate_meteoric_inputs:
        model_ready_collection_asset = GenericCollection(model_ready_collection_asset.collection\
                                                        .select(['AET', 'precip_and_snowmelt_input', 'irrigation'])\
                                                            .map(convert_depth_to_volume)) if convert_meteoric_depth_to_volume else model_ready_collection_asset
        AET = model_ready_collection_asset.iterate_zonal_stats(geometries=regions_dict[zonal_stats_region], band='AET', scale=scale, reducer_type='sum', geometry_names=[f'{zonal_stats_region}'])
        precip_and_snowmelt = model_ready_collection_asset.iterate_zonal_stats(geometries=regions_dict[zonal_stats_region], band='precip_and_snowmelt_input', scale=scale, reducer_type='sum', geometry_names=[f'{zonal_stats_region}'])
        irrigation = model_ready_collection_asset.iterate_zonal_stats(geometries=regions_dict[zonal_stats_region], band='irrigation', scale=scale, reducer_type='sum', geometry_names=[f'{zonal_stats_region}'])
    elif include_combined_meteoric_inputs:
        UBM_meteoric_inputs = GenericCollection(UBM_collection.collection\
                                                        .select(['AET', 'precip_and_snowmelt_input', 'irrigation'])\
                                                            .map(convert_depth_to_volume)) if convert_meteoric_depth_to_volume else model_ready_collection_asset
        precip_and_snowmelt = UBM_meteoric_inputs.iterate_zonal_stats(geometries=regions_dict[zonal_stats_region], band='precip_and_snowmelt_input', scale=scale, reducer_type='sum', geometry_names=[f'{zonal_stats_region}'])
        AET = UBM_meteoric_inputs.iterate_zonal_stats(geometries=regions_dict[zonal_stats_region], band='AET', scale=scale, reducer_type='sum', geometry_names=[f'{zonal_stats_region}'])
        irrigation = UBM_meteoric_inputs.iterate_zonal_stats(geometries=regions_dict[zonal_stats_region], band='irrigation', scale=scale, reducer_type='sum', geometry_names=[f'{zonal_stats_region}'])
    print("Zonal statistics calculations completed.")
    ######## HANDLING OUTPUT DATAFRAMES ##########
    print("Compiling zonal statistics into DataFrame...")
    if include_separate_meteoric_inputs or include_combined_meteoric_inputs:
        zonal_stats_df = pd.concat([recharge, runoff[f'{zonal_stats_region}'+'_sum'], soil_water[f'{zonal_stats_region}'+'_sum'], AET[f'{zonal_stats_region}'+'_sum'], 
                                            precip_and_snowmelt[f'{zonal_stats_region}'+'_sum'], irrigation[f'{zonal_stats_region}'+'_sum']], axis=1)
        zonal_stats_df.columns = ['Date', 'Recharge_m3', 'Runoff_m3', 'Soil_Water_End_m3', 'AET_m3', 'Precip_and_Snowmelt_m3', 'Irrigation_m3']
        zonal_stats_df['Date'] = pd.to_datetime(zonal_stats_df['Date'])
        zonal_stats_df = zonal_stats_df.reset_index(drop=True)
    else:
        zonal_stats_df = pd.concat([recharge, runoff[f'{zonal_stats_region}'+'_sum'], soil_water[f'{zonal_stats_region}'+'_sum']], axis=1)
        zonal_stats_df.columns = ['Date', 'Recharge_m3', 'Runoff_m3', 'Soil_Water_End_m3']
        zonal_stats_df['Date'] = pd.to_datetime(zonal_stats_df['Date'])
        zonal_stats_df = zonal_stats_df.reset_index(drop=True)
    print("DataFrame compilation completed. Saving to CSV...")
    tmp_path = output_path_for_csv + ".tmp"
    zonal_stats_df.to_csv(tmp_path, index=False)
    os.replace(tmp_path, output_path_for_csv)
    print(f"Zonal statistics saved to {output_path_for_csv}")

def run_all_zonal_stats_and_save_to_csv(region_name, geometry, output_path_for_csv):
    recharge = UBM_collection.iterate_zonal_stats(geometries=geometry, band='Recharge', scale=scale, reducer_type='sum', geometry_names=[f'{region_name}'])

    runoff = UBM_collection.iterate_zonal_stats(geometries=geometry, band='Runoff', scale=scale, reducer_type='sum', geometry_names=[f'{region_name}'])

    soil_water = UBM_collection.iterate_zonal_stats(geometries=geometry, band='Soil_Water_End_Of_Previous_Timestep', scale=scale, reducer_type='sum', geometry_names=[f'{region_name}'])

    if include_separate_meteoric_inputs:
        model_ready_collection_asset = GenericCollection(model_ready_collection_asset.collection\
                                                        .select(['AET', 'precip_and_snowmelt_input', 'irrigation'])\
                                                            .map(convert_depth_to_volume)) if convert_meteoric_depth_to_volume else model_ready_collection_asset
        AET = model_ready_collection_asset.iterate_zonal_stats(geometries=geometry, band='AET', scale=scale, reducer_type='sum', geometry_names=[f'{region_name}'])
        precip_and_snowmelt = model_ready_collection_asset.iterate_zonal_stats(geometries=geometry, band='precip_and_snowmelt_input', scale=scale, reducer_type='sum', geometry_names=[f'{region_name}'])
        irrigation = model_ready_collection_asset.iterate_zonal_stats(geometries=geometry, band='irrigation', scale=scale, reducer_type='sum', geometry_names=[f'{region_name}'])
    elif include_combined_meteoric_inputs:
        UBM_meteoric_inputs = GenericCollection(UBM_collection.collection\
                                                        .select(['AET', 'precip_and_snowmelt_input', 'irrigation'])\
                                                            .map(convert_depth_to_volume)) if convert_meteoric_depth_to_volume else model_ready_collection_asset
        precip_and_snowmelt = UBM_meteoric_inputs.iterate_zonal_stats(geometries=geometry, band='precip_and_snowmelt_input', scale=scale, reducer_type='sum', geometry_names=[f'{region_name}'])
        AET = UBM_meteoric_inputs.iterate_zonal_stats(geometries=geometry, band='AET', scale=scale, reducer_type='sum', geometry_names=[f'{region_name}'])
        irrigation = UBM_meteoric_inputs.iterate_zonal_stats(geometries=geometry, band='irrigation', scale=scale, reducer_type='sum', geometry_names=[f'{region_name}'])
    print("Zonal statistics calculations completed.")
    ######## HANDLING OUTPUT DATAFRAMES ##########
    print("Compiling zonal statistics into DataFrame...")
    if include_separate_meteoric_inputs or include_combined_meteoric_inputs:
        zonal_stats_df = pd.concat([recharge, runoff[f'{region_name}'+'_sum'], soil_water[f'{region_name}'+'_sum'], AET[f'{region_name}'+'_sum'], 
                                            precip_and_snowmelt[f'{region_name}'+'_sum'], irrigation[f'{region_name}'+'_sum']], axis=1)
        zonal_stats_df.columns = ['Date', 'Recharge_m3', 'Runoff_m3', 'Soil_Water_End_m3', 'AET_m3', 'Precip_and_Snowmelt_m3', 'Irrigation_m3']
        zonal_stats_df['Date'] = pd.to_datetime(zonal_stats_df['Date'])
        zonal_stats_df = zonal_stats_df.reset_index(drop=True)
    else:
        zonal_stats_df = pd.concat([recharge, runoff[f'{region_name}'+'_sum'], soil_water[f'{region_name}'+'_sum']], axis=1)
        zonal_stats_df.columns = ['Date', 'Recharge_m3', 'Runoff_m3', 'Soil_Water_End_m3']
        zonal_stats_df['Date'] = pd.to_datetime(zonal_stats_df['Date'])
        zonal_stats_df = zonal_stats_df.reset_index(drop=True)
    print("DataFrame compilation completed. Saving to CSV...")
    # tmp_path = output_path_for_csv + ".tmp"
    # zonal_stats_df.to_csv(tmp_path, index=False)
    # os.replace(tmp_path, output_path_for_csv)
    zonal_stats_df.to_csv(output_path_for_csv, index=False)
    print(f"Zonal statistics saved to {output_path_for_csv}")


if manually_set_region_for_zonal_stats:
    run_manual_zonal_stats_and_save_to_csv()
else:
    # Utah Statewide
    statewide_folder = 'C:\\Users\\mradwin\\Documents\\Utah Soil Water Balance\\Zonal_Stats_Timeseries\\All_Watersheds\\Utah_Statewide\\'
    if not os.path.exists(statewide_folder):
        print(f"Output folder {statewide_folder} does not exist. Creating it.")
        os.makedirs(statewide_folder)
    statewide_path = f'{statewide_folder}{asset_name}_Zonal_Stats_Utah_Statewide.csv'
    if resume_skip_existing and os.path.exists(statewide_path):
        print(f"Skipping Utah_Statewide (already exists): {statewide_path}")
    else:
        run_all_zonal_stats_and_save_to_csv('Utah_Statewide', UT_boundary, statewide_path)

    # GSL Basin
    gsl_folder = 'C:\\Users\\mradwin\\Documents\\Utah Soil Water Balance\\Zonal_Stats_Timeseries\\All_Watersheds\\GSL_Basin_Watershed\\'
    if not os.path.exists(gsl_folder):
        print(f"Output folder {gsl_folder} does not exist. Creating it.")
        os.makedirs(gsl_folder)
    gsl_path = f'{gsl_folder}{asset_name}_Zonal_Stats_GSL_Basin.csv'
    if resume_skip_existing and os.path.exists(gsl_path):
        print(f"Skipping GSL_Basin_Watershed (already exists): {gsl_path}")
    else:
        run_all_zonal_stats_and_save_to_csv('GSL_Basin_Watershed', GSL_basin, gsl_path)

    # Per-watershed processing with resume support
    try:
        for i, name in enumerate(all_utah_watershed_names_cleaned):
            print(f"Processing zonal statistics for watershed: {name}")
            output_folder_for_csv = f'C:\\Users\\mradwin\\Documents\\Utah Soil Water Balance\\Zonal_Stats_Timeseries\\All_Watersheds\\{name}\\'
            if name == 'Upper_Green_Flaming_Gorge_Reservoir':
                name = 'Uppr_Green_Flmng_Grge_Res'
            elif name == 'Pilot_Thousand_Springs_Nevada_Utah':
                name = 'Pilot_Thsnd_Sprngs_NV_UT'
            output_path_for_csv = f'{output_folder_for_csv}{asset_name}_Zonal_Stats_{name}.csv'

            # Check if path folder exists, if not create it
            if not os.path.exists(output_folder_for_csv):
                print(f"Output folder {output_folder_for_csv} does not exist. Creating it.")
                os.makedirs(output_folder_for_csv)

            if resume_skip_existing and os.path.exists(output_path_for_csv):
                print(f"Skipping {name} (already exists): {output_path_for_csv}")
                continue

            watershed_geometry = all_utah_watersheds.filter(ee.Filter.eq('HU_8_NAME', all_utah_watershed_names[i])).geometry()

            run_all_zonal_stats_and_save_to_csv(name, watershed_geometry, output_path_for_csv)
    except KeyboardInterrupt:
        print("Interrupted by user. Progress has been saved for completed watersheds. You can rerun and it will skip existing outputs.")
    
    
