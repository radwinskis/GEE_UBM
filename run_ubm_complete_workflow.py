import ee 
from RadGEEToolbox import GenericCollection
from GEE_UBM import OriginalUBMRun, ModifiedUBM1Run, ModifiedUBM2Run, check_merged_collection
# IMPORT THE NEW GENERATOR FUNCTION
from generate_ubm_inputs import get_ubm_input_collection, get_abbreviation_dicts

#------------------------------------------------------#
############## INITIALIZE EARTH ENGINE #################
#------------------------------------------------------#
service_account = 'localpythonscripts@ut-gee-ugs-bsf-dev.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'C:\\Users\\mradwin\\ut-gee-ugs-bsf-dev-53dcc5d729e0.json')
ee.Initialize(credentials=credentials)

#-----------------------------------------------------------#
################### AVAILABLE OPTIONS #######################
#-----------------------------------------------------------#
# Copy these strings into the configuration section below or use list indexing

soil_thickness_options = [
    'Random_Forest_Utah_Model_30m', 'Random_Forest_Utah_Model_1km', 'ISRIC', 'gNATSGO', 
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

snowmelt_and_precip_options = [
    'DAYMET_SNODAS_combined_inputs_monthly', 'PRISM_SNODAS_combined_inputs_monthly', 
    'GRIDMET_SNODAS_combined_inputs_monthly'
]

irrigation_options = [
    'UT_UDWR_irrigation_inputs_monthly_scaled_30m'
]

PET_options = ['GRIDMET_daily_PET', 'GRIDMET_monthly_PET', 'ERA5_daily_PET', 'ERA5_monthly_PET']

AET_options = [
    'ERA5_daily_ET', 'ERA5_monthly_ET', 'MODIS_ET', 'MODIS_monthly_ET',
    'OPEN_ET_DisALEXI', 'OPEN_ET_ensemble', 'OPEN_ET_PTJPL', 'OPEN_ET_SIMS',
    'OPEN_ET_SSEBOP', 'OPEN_ET_EEMETRIC', 'OPEN_ET_GEESEBAL'
]

soil_moisture_options = [
    'SMAP_daily_soil', 'SMAP_monthly_soil', 'SMAP_daily_soil_aggregate', 
    'SMAP_monthly_soil_aggregate', 'ERA5_daily_soil_moisture', 
    'ERA5_monthly_soil_moisture', 'GLDAS_daily_soil_moisture', 
    'GLDAS_monthly_soil_moisture'
]

UBM_model_options = ['Original_UBM', 'Modified_UBM_1', 'Modified_UBM_2', 'Modified_UBM_1_Testing_Updates']
resampling_options = ['bilinear', 'focal_mean', 'reduceResolution']

#-----------------------------------------------------------#
################### USER CONFIGURATION ######################
#-----------------------------------------------------------#

# --- Time Range ---
start_year = 2004
end_year = 2025 # Exclusive (runs through end_year - 1)

# --- Model Selection ---
UBM_model_to_use = UBM_model_options[1] # 'Modified_UBM_1' ⚠️⚠️

# --- Processing Options ---
monthly_time_step = True  # True for monthly, False for daily
convert_to_volume = False  # True to export volume (m^3), False for depth (mm)
resampling_method = resampling_options[1] # 'focal_mean'

# --- Static Raster Selection ---
soil_thickness_raster = soil_thickness_options[1] #1 is calibrated
porosity_raster = porosity_options[1] #1 is calibrated
field_capacity_raster = field_capacity_options[2] #2 is calibrated
wilting_point_raster = wilting_point_options[1] #1 is calibrated
Geo_K_raster = Geo_K_options[-1] #-1 is calibrated

# --- Dynamic Input Selection ---
# Select inputs based on your chosen UBM_model_to_use
snowmelt_and_precip = snowmelt_and_precip_options[0]
irrigation = irrigation_options[0]  
PET_input = PET_options[0]            # Used for Original_UBM
AET_input = AET_options[9]            # Used for Modified_UBM_1 & 2 
soil_moisture_input = soil_moisture_options[0] # Used for Modified_UBM_2

print(f'Using the following configuration: {UBM_model_to_use}, {resampling_method}, Monthly Time Step: {monthly_time_step}')
print(f'Static Rasters: {{Soil Thickness: {soil_thickness_raster}, Porosity: {porosity_raster}, Field Capacity: {field_capacity_raster}, Wilting Point: {wilting_point_raster}, Geo K: {Geo_K_raster}}}')
print(f'Dynamic Inputs: {{Snowmelt+Precip: {snowmelt_and_precip}, Irrigation: {irrigation}, PET: {PET_input}, AET: {AET_input}, Soil Moisture: {soil_moisture_input}}}')

#------------------------------------------#
############ HELPER FUNCTIONS ##############
#------------------------------------------#
def convert_depth_to_volume(image):
    """Converts pixel values from depth (mm) to volume (m^3)."""
    pixel_area = ee.Image.pixelArea()
    outputs_for_conversion = image.select(['Runoff', 'Recharge', 'Soil_Water_End_Of_Previous_Timestep'])
    outputs_not_for_conversion = image.select(['Soil_Saturation_Percent_End_Of_Timestep'])
    # depth_in_meters = image.multiply(0.001)
    depth_in_meters = outputs_for_conversion.multiply(0.001)
    volume_m3 = pixel_area.multiply(depth_in_meters)
    return volume_m3.addBands(outputs_not_for_conversion).copyProperties(image, image.propertyNames())

### Original version of join_collections using time-based join
# def join_collections(inputs, outputs):
#     """
#     Joins the input collection (drivers) with the output collection (model results).
#     Assumes both collections have matching 'system:time_start'.
#     """
#     # Use an inner join to match images by time
#     filter_time = ee.Filter.equals(leftField='system:time_start', rightField='system:time_start')
#     inner_join = ee.Join.inner()
    
#     # Apply the join
#     joined = inner_join.apply(inputs, outputs, filter_time)
    
#     def merge_bands(feature):
#         # 'primary' is the input image, 'secondary' is the model output
#         input_img = ee.Image(feature.get('primary'))
#         output_img = ee.Image(feature.get('secondary'))
#         # Return merged image
#         return input_img.addBands(output_img)
    
#     return ee.ImageCollection(joined.map(merge_bands))

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

def delete_collection_contents(asset_id):
    """Deletes all images inside an ImageCollection."""
    print(f"Scanning {asset_id}...")
    try:
        children = ee.data.listAssets({'parent': asset_id})
        files = children.get('assets', [])
        if not files:
            print("Collection is already empty.")
            return
        print(f"Deleting {len(files)} images...")
        for child in files:
            ee.data.deleteAsset(child['id'])
        print(f"✅ Successfully deleted {len(files)} images.")
    except Exception as e:
        print(f"❌ Error deleting contents: {e}")

#-------------------------------------------#
########## GENERATE INPUTS IN MEMORY #######
#-------------------------------------------#
print("--- Generating Input Collection (In-Memory) ---")

# Call the generator function using the configuration above
input_collection_wrapper = get_ubm_input_collection(
    start_year=start_year,
    end_year=end_year,
    UBM_model_to_use=UBM_model_to_use,
    monthly_time_step=monthly_time_step,
    resampling_method=resampling_method,
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
print(f"Input collection generated with {input_col.size().getInfo()} images.")

# Check required bands (using the logic from your original script)
# check_merged_collection(input_collection_wrapper)

# Scale is needed for export
scale = input_col.first().select('soil_thickness').projection().nominalScale().getInfo()
UT_boundary = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Regional_Boundary").geometry()

#------------------------------------#
############# RUN MODEL ##############
#------------------------------------#
print(f"--- Running {UBM_model_to_use} ---")

if UBM_model_to_use == 'Original_UBM':
    ubm_run = OriginalUBMRun(input_collection_wrapper)
    asset_folder = 'projects/ut-gee-ugs-bsf-dev/assets/Original_UBM_Runs/'
    model_prefix = 'Orig_UBM_'
elif UBM_model_to_use == 'Modified_UBM_1':
    ubm_run = ModifiedUBM1Run(input_collection_wrapper)
    asset_folder = 'projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1Runs/'
    model_prefix = 'Mod_UBM_1_'
elif UBM_model_to_use == 'Modified_UBM_2':
    ubm_run = ModifiedUBM2Run(input_collection_wrapper)
    asset_folder = 'projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM2Runs/'
    model_prefix = 'Mod_UBM_2_'
elif UBM_model_to_use == 'Modified_UBM_1_Testing_Updates':
    ubm_run = ModifiedUBM1Run(input_collection_wrapper)
    asset_folder = 'projects/ut-gee-ugs-bsf-dev/assets/ModifiedUBM1TestingRuns/'
    model_prefix = 'Mod_UBM_1_Testing_'

# Get output collection
output_col = ubm_run.collection

# Convert output to volume if requested
if convert_to_volume:
    print("Converting model outputs to volume (m^3)...")
    # input_col = input_col.map(convert_depth_to_volume)
    output_col = output_col.map(convert_depth_to_volume)
    model_suffix = '_m3'
else:
    model_suffix = '_mm'

#-------------------------------------------#
########## MERGE INPUTS AND OUTPUTS ########
#-------------------------------------------#
print("--- Merging Inputs and Outputs ---")
final_collection = join_collections(input_col, output_col)

# Re-wrap in GenericCollection for export convenience
final_wrapper = GenericCollection(final_collection)

#-------------------------------------------#
############# ASSET NAMING & EXPORT ########
#-------------------------------------------#
# Reconstruct the name based on inputs (using helper dicts imported from generator)
st_dict, dyn_dict = get_abbreviation_dicts()

# Helper to safely get abbrev
def get_abbr(d, key):
    return d.get(key, 'Unknown')

static_part = f"{get_abbr(st_dict, soil_thickness_raster)}_{get_abbr(st_dict, porosity_raster)}_{get_abbr(st_dict, field_capacity_raster)}_{get_abbr(st_dict, wilting_point_raster)}_{get_abbr(st_dict, Geo_K_raster)}"

# Construct dynamic part of name
if UBM_model_to_use == 'Original_UBM':
    dyn_part = f"{get_abbr(dyn_dict, snowmelt_and_precip)}_{get_abbr(dyn_dict, PET_input)}_{get_abbr(dyn_dict, irrigation)}"
elif UBM_model_to_use == 'Modified_UBM_1':
    dyn_part = f"{get_abbr(dyn_dict, snowmelt_and_precip)}_{get_abbr(dyn_dict, AET_input)}_{get_abbr(dyn_dict, irrigation)}"
elif UBM_model_to_use == 'Modified_UBM_1_Testing_Updates':
    dyn_part = f"{get_abbr(dyn_dict, snowmelt_and_precip)}_{get_abbr(dyn_dict, AET_input)}_{get_abbr(dyn_dict, irrigation)}_T"
elif UBM_model_to_use == 'Modified_UBM_2':
    dyn_part = f"{get_abbr(dyn_dict, snowmelt_and_precip)}_{get_abbr(dyn_dict, AET_input)}_{get_abbr(dyn_dict, soil_moisture_input)}_{get_abbr(dyn_dict, irrigation)}"
suffix = '_M' if monthly_time_step else '_D'

asset_name = f"{asset_folder}{model_prefix}{static_part}_{dyn_part}{suffix}{model_suffix}"

print(f"Output asset will be named: {asset_name}")

# Check existence
try:
    ee.data.getAsset(asset_name)
    print("Asset exists. Deleting contents to overwrite...")
    delete_collection_contents(asset_name)
except Exception:
    print("Asset does not exist. It will be created.")

# Export
print("Starting export task...")
# Using the toolbox export method
final_wrapper.export_to_asset_collection(
    asset_collection_path=asset_name,
    region=UT_boundary,
    crs='EPSG:32612',
    scale=scale
)
print("Export task submitted. Monitor progress in Task Manager.")