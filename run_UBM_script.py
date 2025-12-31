import ee 
from RadGEEToolbox import GenericCollection, LandsatCollection, get_palette
from GEE_UBM import InputCollections, build_model_ready_collection, OriginalUBMRun, ModifiedUBM1Run, ModifiedUBM2Run, check_merged_collection
import geemap
import numpy as np
#------------------------------#
###### PRIMARY USER INPUT ######
#------------------------------#
input_collection_asset_id = 'projects/ut-gee-ugs-bsf-dev/assets/Aggregated_Modified1_UBM_Input_Collections/UT_RF1kmST_POLARISPor_OLMFC_HHSWP_POLARISKsatM_GRIDMETSNODASM_OPENETEEMETRIC_M'

##### RUN EXPORT LOOP OR NOT #####
run_loop = True  # Set to True to run the loop and export collections for each year. Set to False to skip exports and inspect dummy variables.

convert_to_volume = True  # Set to True to convert depth (mm) to volume (m^3) in the final output collection.

#------------------------------------------------------#
############## INITIALIZE EARTH ENGINE #################
#------------------------------------------------------#
service_account = 'localpythonscripts@ut-gee-ugs-bsf-dev.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'C:\\Users\\mradwin\\ut-gee-ugs-bsf-dev-53dcc5d729e0.json')
ee.Initialize(credentials=credentials)

#------------------------------------------#
############ HELPER FUNCTIONS ##############
#------------------------------------------#
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

def delete_collection_contents(asset_id, dry_run=False):
    """
    Deletes all images inside an ImageCollection.
    
    Args:
        asset_id (str): The full path to the collection.
        dry_run (bool): If True, only PRINTS what would be deleted. 
                        If False, ACTUALLY deletes files.
    """
    print(f"Scanning {asset_id}...")
    
    try:
        # List all children
        children = ee.data.listAssets({'parent': asset_id})
        files = children.get('assets', [])
        
        if not files:
            print("Collection is already empty.")
            return

        print(f"Found {len(files)} images.")

        if dry_run:
            print("\n--- DRY RUN MODE (Nothing deleted) ---")
            print(f"I WOULD delete the following {len(files)} images:")
            for child in files[:5]: # Print first 5 as a sample
                print(f" [WOULD DELETE]: {child['id']}")
            if len(files) > 5:
                print(f" ... and {len(files)-5} more.")
            print("\nTo actually delete, call this function again with dry_run=False")
            
        else:
            print("\n--- DELETING FILES ---")
            for child in files:
                path = child['id']
                ee.data.deleteAsset(path)
                # print(f"Deleted: {path}") # Uncomment if you want a log of every file
            print(f"✅ Successfully deleted {len(files)} images.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

#--------------------------------------------#
############# STATIC VARIABLES ###############
#--------------------------------------------#
UT_boundary = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Regional_Boundary").geometry()

asset_collection_name = input_collection_asset_id.split('/')[-1]

model_ready_collection_asset = ee.ImageCollection(input_collection_asset_id)
model_ready_collection_asset = GenericCollection(model_ready_collection_asset)

scale = model_ready_collection_asset.collection.first().select('soil_thickness').projection().nominalScale().getInfo()


#---------------------------#
### UBM model type to use ###
#---------------------------#
UBM_model_options = ['Original_UBM', 'Modified_UBM_1', 'Modified_UBM_2']

UBM_model_to_use = UBM_model_options[1]  # 'Original_UBM', 'Modified_UBM_1', or 'Modified_UBM_2'


if UBM_model_to_use not in UBM_model_options:
    raise ValueError(f"Invalid UBM_model_to_use: {UBM_model_to_use}. Choose from 'Original_UBM', 'Modified_UBM_1', or 'Modified_UBM_2'.")
elif UBM_model_to_use == 'Original_UBM':
    print("Organizing input collection for UBM model: Original_UBM. Checks will be performed to ensure required inputs are provided.")
    bands = model_ready_collection_asset.collection.first().bandNames().getInfo()
    required_bands = ['soil_thickness', 'soil_porosity', 'field_capacity', 'wilting_point', 'Geo_K', 'precip_and_snowmelt_input', 'PET']
    check_merged_collection(model_ready_collection_asset)
    if not all(band in bands for band in required_bands):
        missing_bands = [band for band in required_bands if band not in bands]
        raise ValueError(f"Input collection is missing required bands for Original_UBM: {missing_bands}")
elif UBM_model_to_use == 'Modified_UBM_1':
    print("Organizing input collection for UBM model: Modified_UBM_1. Checks will be performed to ensure required inputs are provided.")
    bands = model_ready_collection_asset.collection.first().bandNames().getInfo()
    required_bands = ['soil_thickness', 'soil_porosity', 'field_capacity', 'wilting_point', 'Geo_K', 'precip_and_snowmelt_input', 'AET']
    check_merged_collection(model_ready_collection_asset)
    if not all(band in bands for band in required_bands):
        missing_bands = [band for band in required_bands if band not in bands]
        raise ValueError(f"Input collection is missing required bands for Modified_UBM_1: {missing_bands}")
elif UBM_model_to_use == 'Modified_UBM_2':
    print("Organizing input collection for UBM model: Modified_UBM_2. Checks will be performed to ensure required inputs are provided.")
    bands = model_ready_collection_asset.collection.first().bandNames().getInfo()
    required_bands = ['soil_thickness', 'soil_porosity', 'field_capacity', 'wilting_point', 'Geo_K', 'precip_and_snowmelt_input', 'AET', 
                                                                                                'Soil_Water_Beginning_of_Current_Timestep']
    check_merged_collection(model_ready_collection_asset)
    if not all(band in bands for band in required_bands):
        missing_bands = [band for band in required_bands if band not in bands]
        raise ValueError(f"Input collection is missing required bands for Modified_UBM_2: {missing_bands}")
else:
    pass

#----------------------#
### Time step option ###
#----------------------#
monthly_time_step = True  # Set to True for monthly time step, False for daily time step
print(f"Using {'monthly' if monthly_time_step else 'daily'} time step.")

if UBM_model_to_use == 'Original_UBM':
    asset_folder = 'projects/ut-gee-ugs-bsf-dev/assets/Original_UBM_Runs/'
    model_prefix = 'Original_UBM_'
elif UBM_model_to_use == 'Modified_UBM_1':
    asset_folder = 'projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/'
    model_prefix = 'Modified_UBM_1_'
elif UBM_model_to_use == 'Modified_UBM_2':
    asset_folder = 'projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM2Runs/'
    model_prefix = 'Modified_UBM_2_'

if convert_to_volume:
    model_suffix = '_m3'
else:
    model_suffix = '_mm'
asset_name = asset_folder + f'{model_prefix}' + asset_collection_name + model_suffix

print(f"Output asset will be named: {asset_name}")

#--------------------------------------------------------------------------------#
###### CHECK FOR EXISTING ASSET #######
#--------------------------------------------------------------------------------#
try:
    ee.data.getAsset(asset_name)
    exists = True
except Exception:
    exists = False

if not exists:
    print(f"Asset {asset_name} does not exist. A new asset will be created.")
else:
    print(f"Asset {asset_name} already exists. Export will overwrite the existing asset.")
    # delete existing asset
    delete_collection_contents(asset_name) 


#------#
#---------------#
#-----------------------------#
#------------------------------------#
############# RUN LOOP ###############
#------------------------------------#
if run_loop:
    if UBM_model_to_use == 'Original_UBM':
        ubm_run = OriginalUBMRun(model_ready_collection_asset)
    elif UBM_model_to_use == 'Modified_UBM_1':
        ubm_run = ModifiedUBM1Run(model_ready_collection_asset)
    elif UBM_model_to_use == 'Modified_UBM_2':
        ubm_run = ModifiedUBM2Run(model_ready_collection_asset)
    dates = ubm_run.dates
    if convert_to_volume:
        ubm_run = GenericCollection(collection=ubm_run.collection.map(convert_depth_to_volume))
    print(f"Export task started.")
    export = ubm_run.export_to_asset_collection(asset_collection_path=asset_name, 
                                                        region=UT_boundary, scale=scale)
    print("Export task started. Monitor progress in the GEE Task Manager.")