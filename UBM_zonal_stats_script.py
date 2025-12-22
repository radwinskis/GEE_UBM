import ee 
from RadGEEToolbox import GenericCollection, LandsatCollection, get_palette
from GEE_UBM import InputCollections, build_model_ready_collection, OriginalUBMRun, ModifiedUBM1Run, ModifiedUBM2Run, check_merged_collection
import geemap
import numpy as np
import pandas as pd
#------------------------------------------------------#

include_meteoric_inputs = True

if include_meteoric_inputs:
    print("Including meteoric inputs (AET and Precipitation + Snowmelt) in zonal statistics.")
else:
    print("Excluding meteoric inputs from zonal statistics.")

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

regions_dict = {
    'UT': UT_boundary,
    'GSL_Basin_Watershed': GSL_basin,
    'Castle_Valley_Watershed': castle_valley_watershed,
    'Milford_Watershed': milford_watershed,
    'Sanpete_Watershed': sanpete_watershed
}

zonal_stats_region = 'GSL_Basin_Watershed' # Change this to the desired region for zonal statistics ⚠️⚠️⚠️

if zonal_stats_region not in regions_dict:
    raise ValueError(f"Region '{zonal_stats_region}' not found in regions_dict. Please add it before proceeding.")

print(f"Calculating zonal statistics for region: {zonal_stats_region}")

#------------------------------#
###### PRIMARY USER INPUT ######
#------------------------------#
input_UBM_collection_asset_id = 'projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/Modified_UBM_1_UT_RF1kmST_POLARISPor_OLMFC_HHSWP_POLARISKsatM_DAYMETSNODASM_OPENETEEMETRIC_M_m3'

asset_name = input_UBM_collection_asset_id.split('/')[-1]

asset_id_of_input_col_used_for_UBM_run = 'projects/ut-gee-ugs-bsf-dev/assets/Aggregated_Modified1_UBM_Input_Collections/UT_RF1kmST_POLARISPor_OLMFC_HHSWP_POLARISKsatM_DAYMETSNODASM_OPENETEEMETRIC_M'

output_path_for_csv = f'C:\\Users\\mradwin\\Documents\\Utah Soil Water Balance\\Zonal_Stats_Timeseries\\GSL_Basin\\{asset_name}_Zonal_Stats_{zonal_stats_region}.csv'

print(f"Output CSV will be saved to: {output_path_for_csv}")

######## DYNAMIC DEFINITIONS ########
UBM_collection = GenericCollection(collection=ee.ImageCollection(input_UBM_collection_asset_id), start_date=start_date, end_date=end_date)

scale = UBM_collection.image_grab(0).projection().nominalScale().getInfo()

print(f"Using scale of {scale} meters for zonal statistics.")

model_ready_collection_asset = ee.ImageCollection(asset_id_of_input_col_used_for_UBM_run).map(convert_depth_to_volume) if include_meteoric_inputs else None
model_ready_collection_asset = GenericCollection(collection=model_ready_collection_asset, start_date=start_date, end_date=end_date) if include_meteoric_inputs else None

######## ZONAL STATISTICS ##########
print("Starting zonal statistics calculations...")
recharge = UBM_collection.iterate_zonal_stats(geometries=regions_dict[zonal_stats_region], band='Recharge', scale=scale, reducer_type='sum', geometry_names=[f'{zonal_stats_region}'])

runoff = UBM_collection.iterate_zonal_stats(geometries=regions_dict[zonal_stats_region], band='Runoff', scale=scale, reducer_type='sum', geometry_names=[f'{zonal_stats_region}'])

soil_water = UBM_collection.iterate_zonal_stats(geometries=regions_dict[zonal_stats_region], band='Soil_Water_End_Of_Previous_Timestep', scale=scale, reducer_type='sum', geometry_names=[f'{zonal_stats_region}'])

if include_meteoric_inputs:
    AET = model_ready_collection_asset.iterate_zonal_stats(geometries=regions_dict[zonal_stats_region], band='AET', scale=scale, reducer_type='sum', geometry_names=[f'{zonal_stats_region}'])
    precip_and_snowmelt = model_ready_collection_asset.iterate_zonal_stats(geometries=regions_dict[zonal_stats_region], band='precip_and_snowmelt_input', scale=scale, reducer_type='sum', geometry_names=[f'{zonal_stats_region}'])
print("Zonal statistics calculations completed.")
######## HANDLING OUTPUT DATAFRAMES ##########
print("Compiling zonal statistics into DataFrame...")
if include_meteoric_inputs:
    zonal_stats_df = pd.concat([recharge, runoff[f'{zonal_stats_region}'+'_sum'], soil_water[f'{zonal_stats_region}'+'_sum'], AET[f'{zonal_stats_region}'+'_sum'], precip_and_snowmelt[f'{zonal_stats_region}'+'_sum']], axis=1)
    zonal_stats_df.columns = ['Date', 'Recharge_m3', 'Runoff_m3', 'Soil_Water_End_m3', 'AET_m3', 'Precip_and_Snowmelt_m3']
    zonal_stats_df['Date'] = pd.to_datetime(zonal_stats_df['Date'])
    zonal_stats_df = zonal_stats_df.reset_index(drop=True)
else:
    zonal_stats_df = pd.concat([recharge, runoff[f'{zonal_stats_region}'+'_sum'], soil_water[f'{zonal_stats_region}'+'_sum']], axis=1)
    zonal_stats_df.columns = ['Date', 'Recharge_m3', 'Runoff_m3', 'Soil_Water_End_m3']
    zonal_stats_df['Date'] = pd.to_datetime(zonal_stats_df['Date'])
    zonal_stats_df = zonal_stats_df.reset_index(drop=True)
print("DataFrame compilation completed. Saving to CSV...")
zonal_stats_df.to_csv(output_path_for_csv, index=False)
print(f"Zonal statistics saved to {output_path_for_csv}")