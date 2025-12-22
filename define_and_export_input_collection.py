import ee 
from RadGEEToolbox import GenericCollection, LandsatCollection, get_palette
from GEE_UBM import InputCollections, build_model_ready_collection, OriginalUBMRun, ModifiedUBM1Run, check_merged_collection
import geemap
import numpy as np

##### RUN EXPORT LOOP OR NOT #####
run_loop = True  # Set to True to run the loop and export collections for each year. Set to False to skip exports and inspect dummy variables.

#------------------------------------------------------#
############## INITIALIZE EARTH ENGINE #################
#------------------------------------------------------#
service_account = 'localpythonscripts@ut-gee-ugs-bsf-dev.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'C:\\Users\\mradwin\\ut-gee-ugs-bsf-dev-53dcc5d729e0.json')
ee.Initialize(credentials=credentials)

#--------------------------------------------#
############# STATIC VARIABLES ###############
#--------------------------------------------#
UT_boundary = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Regional_Boundary").geometry()

#------------------------------------------------#
############ STATIC RASTER OPTIONS ###############
#------------------------------------------------#
soil_thickness_options = ['Random_Forest_Utah_Model_30m', 'Random_Forest_Utah_Model_1km', 'ISRIC', 'gNATSGO', 
                          'gNATSGO_filled', 'gNATSGO_filled_2_meter_cap']

porosity_options = ['HiHydroSoilPorosity', 'POLARIS_porosity', 'UGS_porosity']

field_capacity_options = ['UGS_fieldCap', 'HiHydroSoilFieldCap', 'OpenLandMapFieldCap']

wilting_point_options = ['UGS_wiltingPoint', 'HiHydroSoilWiltPoint']

Geo_K_options = ['POLARIS_K_Sat_monthly', 'POLARIS_K_Sat_daily', 'HiHydroSoil_K_Sat_monthly', 
                 'HiHydroSoil_K_Sat_daily', 'UGS_Geo_K_monthly', 'UGS_Geo_K_daily', 'USGS_Geo_K_monthly', 
                 'USGS_Geo_K_daily']

#---------------------------------------------------------------#
############# DYNAMIC/TEMPORAL COLLECTION OPTIONS ###############
#---------------------------------------------------------------#
snowmelt_and_precip_options = ['DAYMET_SNODAS_combined_inputs_monthly', 'PRISM_SNODAS_combined_inputs_monthly', 
                               'GRIDMET_SNODAS_combined_inputs_monthly']

PET_options = ['GRIDMET_daily_PET', 'GRIDMET_monthly_PET', 'ERA5_daily_PET', 'ERA5_monthly_PET']

AET_options = ['ERA5_daily_ET', 'ERA5_monthly_ET', 'MODIS_ET', 'MODIS_monthly_ET',
                 'OPEN_ET_DisALEXI', 'OPEN_ET_ensemble', 'OPEN_ET_PTJPL', 'OPEN_ET_SIMS',
                 'OPEN_ET_SSEBOP', 'OPEN_ET_EEMETRIC', 'OPEN_ET_GEESEBAL']

soil_moisture_options = ['SMAP_daily_soil', 'SMAP_monthly_soil', 'SMAP_daily_soil_aggregate', 
                 'SMAP_monthly_soil_aggregate', 'ERA5_daily_soil_moisture', 
                 'ERA5_monthly_soil_moisture', 'GLDAS_daily_soil_moisture', 
                 'GLDAS_monthly_soil_moisture']

UBM_model_options = ['Original_UBM', 'Modified_UBM_1', 'Modified_UBM_2']

#------------------------------------------------------------#
############# DEFINE VARIABLES AND USER INPUTS ###############
#------------------------------------------------------------#
#------------ ⚠️⚠️⚠️ USER INPUT NECESSARY BELOW ⚠️⚠️⚠️------------#

#-------------------------------#
### Time range for processing ###
#-------------------------------#
start_year = 2004
end_year = 2025 # NOTE: This is exclusive; the last year processed will be end_year - 1. i.e for end_year = 2025, the last year processed will be 2024.
print(f"Processing years: {start_year} through {end_year - 1}")

#---------------------------#
### UBM model type to use ###
#---------------------------#
UBM_model_to_use = UBM_model_options[1]  # 'Original_UBM', 'Modified_UBM_1', or 'Modified_UBM_2'
if UBM_model_to_use not in UBM_model_options:
    raise ValueError(f"Invalid UBM_model_to_use: {UBM_model_to_use}. Choose from 'Original_UBM', 'Modified_UBM_1', or 'Modified_UBM_2'.")
else:
    print(f"Organizing input collection for UBM model: {UBM_model_to_use}. Checks will be performed to ensure required inputs are provided.")

#----------------------#
### Time step option ###
#----------------------#
monthly_time_step = True  # Set to True for monthly time step, False for daily time step
print(f"Using {'monthly' if monthly_time_step else 'daily'} time step.")

#----------------------------------------------------------#
### Resampling method for harmonizing collections/images ###
#----------------------------------------------------------#

# Choose from resampling_options: reduceResolution is best but slowest and may crash for large collections. 
# If crashes, try 'focal_mean' or 'bilinear'. bilinear is last resort.
resampling_options = ['bilinear', 'focal_mean', 'reduceResolution']
resampling_method = resampling_options[1]  ### focal_mean works best for entire state of Utah. reduceResolution crashes because too many pixels
print(f"Using resampling method: {resampling_method}")

#---------------------------#
### Static Raster Choices ###
#---------------------------#
soil_thickness_raster = soil_thickness_options[1]  # Choose from soil_thickness_options
print(f"Using soil thickness raster: {soil_thickness_raster}")

porosity_raster = porosity_options[1]  # Choose from porosity_options
field_capacity_raster = field_capacity_options[2]  # Choose from field_capacity_options
wilting_point_raster = wilting_point_options[1]  # Choose from wilting_point_options
Geo_K_raster = Geo_K_options[0]  # Choose from Geo_K_options

static_rasters_to_use = [porosity_raster, field_capacity_raster, wilting_point_raster, Geo_K_raster]
print(f"Using static rasters: {static_rasters_to_use}")

#--------------------------------#
### Dynamic Collection Choices ###
#--------------------------------#

### If using the original UBM, provide a snowmelt and precip collection and PET collection
### If using the modified UBM 1, provide a snowmelt and precip collection and AET collection
### If using the modified UBM 2, provide a snowmelt and precip collection, AET collection, and soil moisture collection
snowmelt_and_precip_collection = snowmelt_and_precip_options[2]  # Choose from snowmelt_and_precip_options
PET_collection = PET_options[0]  # Choose from PET_options
AET_collection = AET_options[9]  # Choose from AET_options
soil_moisture_collection = soil_moisture_options[0]  # Choose from soil_moisture_options

if UBM_model_to_use == 'Original_UBM':
    dynamic_collections_to_use = [snowmelt_and_precip_collection, PET_collection]
    print(f"Using dynamic collections: {dynamic_collections_to_use}")
elif UBM_model_to_use == 'Modified_UBM_1':
    dynamic_collections_to_use = [snowmelt_and_precip_collection, AET_collection]
    print(f"Using dynamic collections: {dynamic_collections_to_use}")
elif UBM_model_to_use == 'Modified_UBM_2':
    dynamic_collections_to_use = [snowmelt_and_precip_collection, AET_collection, soil_moisture_collection]
    print(f"Using dynamic collections: {dynamic_collections_to_use}")

#---------------------------------------------#
############# CHECK USER INPUTS ###############
#---------------------------------------------#
if end_year <= start_year:
    raise ValueError("end_year must be greater than start_year.")

#-----------------------------------------------------------#
############# HANDLING NAMING OF OUTPUT ASSET ###############
#-----------------------------------------------------------#
static_raster_abbreviation_dict = {
    'Random_Forest_Utah_Model_30m': 'RF30mST',
    'Random_Forest_Utah_Model_1km': 'RF1kmST',
    'ISRIC': 'ISRICST',
    'gNATSGO': 'gNATSGOST',
    'gNATSGO_filled': 'gNATSGOfldST',
    'gNATSGO_filled_2_meter_cap': 'gNATSGOfld2mcapST',
    'HiHydroSoilPorosity': 'HHSPor',
    'POLARIS_porosity': 'POLARISPor',
    'UGS_porosity': 'UGSPor',
    'UGS_fieldCap': 'UGSFC',
    'HiHydroSoilFieldCap': 'HHSFC',
    'OpenLandMapFieldCap': 'OLMFC',
    'UGS_wiltingPoint': 'UGSWP',
    'HiHydroSoilWiltPoint': 'HHSWP',
    'POLARIS_K_Sat_monthly': 'POLARISKsatM',
    'POLARIS_K_Sat_daily': 'POLARISKsatD',
    'HiHydroSoil_K_Sat_monthly': 'HSSKsatM',
    'HiHydroSoil_K_Sat_daily': 'HSSKsatD',
    'UGS_Geo_K_monthly': 'UGSGeoKM',
    'UGS_Geo_K_daily': 'UGSGeoKD',
    'USGS_Geo_K_monthly': 'USGSGeoKM',
    'USGS_Geo_K_daily': 'USGSGeoKD'
}

dynamic_collection_abbreviation_dict = {
    'DAYMET_SNODAS_combined_inputs_monthly': 'DAYMETSNODASM',
    'PRISM_SNODAS_combined_inputs_monthly': 'PRISMSNODASM',
    'GRIDMET_SNODAS_combined_inputs_monthly': 'GRIDMETSNODASM',
    'GRIDMET_daily_PET': 'GRIDMETPETD',
    'GRIDMET_monthly_PET': 'GRIDMETPETM',
    'ERA5_daily_PET': 'ERA5PETD',
    'ERA5_monthly_PET': 'ERA5PETM',
    'ERA5_daily_ET': 'ERA5ETD',
    'ERA5_monthly_ET': 'ERA5ETM',
    'MODIS_ET': 'MODISETD',
    'MODIS_monthly_ET': 'MODISETM',
    'OPEN_ET_DisALEXI': 'OPENETDisALEXI',
    'OPEN_ET_ensemble': 'OPENETEns',
    'OPEN_ET_PTJPL': 'OPENETPTJPL',
    'OPEN_ET_SIMS': 'OPENETSIMS',
    'OPEN_ET_SSEBOP': 'OPENETSSEBOP',
    'OPEN_ET_EEMETRIC': 'OPENETEEMETRIC',
    'SMAP_daily_soil': 'SMAPSoilD',
    'SMAP_monthly_soil': 'SMAPSoilM',
    'SMAP_daily_soil_aggregate': 'SMAPSoilDAgg',
    'SMAP_monthly_soil_aggregate': 'SMAPSoilMAgg',
    'ERA5_daily_soil_moisture': 'ERA5SoilMoistD',
    'ERA5_monthly_soil_moisture': 'ERA5SoilMoistM',
    'GLDAS_daily_soil_moisture': 'GLDASSoilMoistD',
    'GLDAS_monthly_soil_moisture': 'GLDASSoilMoistM'
}

if UBM_model_to_use == 'Original_UBM':
    asset_folder = 'projects/ut-gee-ugs-bsf-dev/assets/Aggregated_UBM_Input_Collections/'
elif UBM_model_to_use == 'Modified_UBM_1':
    asset_folder = 'projects/ut-gee-ugs-bsf-dev/assets/Aggregated_Modified1_UBM_Input_Collections/'
elif UBM_model_to_use == 'Modified_UBM_2':
    asset_folder = 'projects/ut-gee-ugs-bsf-dev/assets/Aggregated_Modified2_UBM_Input_Collections/'

if monthly_time_step:
    suffix = '_M'
else:
    suffix = '_D'

asset_name = asset_folder + 'UT_' + f'{static_raster_abbreviation_dict[soil_thickness_raster]}_' + f'{"_".join([static_raster_abbreviation_dict[r] for r in static_rasters_to_use])}_' + \
                f'{"_".join([dynamic_collection_abbreviation_dict[c] for c in dynamic_collections_to_use])}{suffix}'

print(f"Output asset will be named: {asset_name}")

#--------------------------------------------------------------------------------#
###### CHECK FOR EXISTING ASSET, TEMPORAL OVERLAP AND DETERMINE START YEAR #######
#--------------------------------------------------------------------------------#
try:
    ee.data.getAsset(asset_name)
    exists = True
except Exception:
    exists = False

if not exists:
    print(f"Asset {asset_name} does not exist. A new asset will be created.")
    change_start = False
else:
    collection = ee.ImageCollection(asset_name)
    if collection.size().getInfo() == 0:
        print(f"Asset {asset_name} exists but is empty. Starting from {start_year}.")
        change_start = False
    else:
        latest_image = collection.sort('system:time_start', False).first()
        latest_date = ee.Date(latest_image.get('system:time_start')).format('YYYY-MM-dd').getInfo()
        print(f"Latest date in asset collection: {latest_date}")
        ############### CHECK TEMPORAL OVERAP #################
        if latest_date >= f"{start_year}-01-01":
            print(f"Asset collection already contains data for year {start_year} or later. "
                "This script will avoid overwriting existing data and only process new data.")
            new_start = ee.Date(latest_date).advance(1, 'month').format('YYYY-MM-dd').getInfo()
            print(f"New start date for processing: {new_start}")
            new_start_year = int(new_start.split('-')[0])
            change_start = True
        else:
            change_start = False

#------#
#---------------#
#-----------------------------#
#------------------------------------#
############# RUN LOOP ###############
#------------------------------------#

run_loop = run_loop # Set to True to run the loop and export collections for each year.
if run_loop:
    if change_start:
        years = np.arange(new_start_year, end_year, 1)
    else:
        years = np.arange(start_year, end_year, 1)
    if len(years) == 0:
        print("No new years to process. Asset is up to date.")
        exit()

    for year in years:
        ### Defining collections that are constant between each UBM model type ###
        print(f"\nProcessing year {year}...")
        if change_start and year == new_start_year:
            base_class = InputCollections(start_date=new_start, end_date=f'{year}-12-31', soil_thickness_raster=soil_thickness_raster, resampling_method=resampling_method)
        else:
            base_class = InputCollections(start_date=f'{year}-01-01', end_date=f'{year}-12-31', soil_thickness_raster=soil_thickness_raster, resampling_method=resampling_method)

        soil_thickness_raster = base_class.soil_thickness_raster
        porosity = base_class.get_static_raster(porosity_raster)
        field_capacity = base_class.get_static_raster(field_capacity_raster) 
        wilting_point = base_class.get_static_raster(wilting_point_raster) 
        Geo_K = base_class.get_static_raster(Geo_K_raster)
        snowmelt_and_precip = base_class.get_precip_and_snowmelt(snowmelt_and_precip_collection)

        static_rasters_list = [soil_thickness_raster, porosity, field_capacity, wilting_point, Geo_K]

        ### Defining collections that vary based on UBM model type ###
        if UBM_model_to_use == 'Original_UBM':
            PET_collection = base_class.get_PET(PET_collection)
            timeseries_collections_list = [snowmelt_and_precip, PET_collection]
        elif UBM_model_to_use == 'Modified_UBM_1':
            AET = base_class.get_AET(AET_collection) 
            timeseries_collections_list = [snowmelt_and_precip, AET]
        elif UBM_model_to_use == 'Modified_UBM_2':
            AET = base_class.get_AET(AET_collection)
            soil_moisture = base_class.get_soil_moisture(soil_moisture_collection) 
            timeseries_collections_list = [snowmelt_and_precip, AET, soil_moisture]


        model_ready_collection = build_model_ready_collection(timeseries_collections_list=timeseries_collections_list, 
                                                              static_images_list=static_rasters_list)
        dates = model_ready_collection.dates
        scale = model_ready_collection.image_grab(0).select('soil_thickness').projection().nominalScale().getInfo()
        print(f"Export task for {year} started.")
        export = model_ready_collection.export_to_asset_collection(asset_collection_path=asset_name, 
                                                        region=UT_boundary, scale=scale)
else:
    print("run_loop is set to False. No exports will be performed. Set run_loop to True to enable exports.")