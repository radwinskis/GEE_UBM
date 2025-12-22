import ee 
from RadGEEToolbox import GenericCollection, LandsatCollection, get_palette
# import GEE_UBM
from GEE_UBM import InputCollections, SnowMeltCollection, build_model_ready_collection, OriginalUBMRun, ModifiedUBM1Run
import geemap
import numpy as np

service_account = 'localpythonscripts@ut-gee-ugs-bsf-dev.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'C:\\Users\\mradwin\\ut-gee-ugs-bsf-dev-53dcc5d729e0.json')
ee.Initialize(credentials=credentials)

############### USER INPUTS #################
precip_data_type = 'GRIDMET_daily_precip'  # Options: 'PRISM_daily_precip', 'DAYMET_daily_precip', or 'GRIDMET_daily_precip'
start_year = 2004
end_year = 2025 # NOTE: This is exclusive; the last year processed will be end_year - 1. i.e for end_year = 2025, the last year processed will be 2024.
boundary = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Regional_Boundary").geometry()
############### CHECKING USER INPUTS #################
if precip_data_type not in ['PRISM_daily_precip', 'DAYMET_daily_precip', 'GRIDMET_daily_precip']:
    raise ValueError("Invalid precip_data_type. Choose from 'PRISM_daily_precip', 'DAYMET_daily_precip', or 'GRIDMET_daily_precip'.")
if end_year <= start_year:
    raise ValueError("end_year must be greater than start_year.")\
############### CHECK EXISTING ASSET #################

if precip_data_type == 'PRISM_daily_precip':
    asset_name = 'projects/ut-gee-ugs-bsf-dev/assets/UT_Precip_and_Snowmelt_Image_Collections/UT_SNODAS_PRISM_PRECIP_PLUS_SNOWMELT_5KM_UBM_INPUT'
elif precip_data_type == 'DAYMET_daily_precip':
    asset_name = 'projects/ut-gee-ugs-bsf-dev/assets/UT_Precip_and_Snowmelt_Image_Collections/UT_SNODAS_DAYMET_PRECIP_PLUS_SNOWMELT_1KM_UBM_INPUT'
elif precip_data_type == 'GRIDMET_daily_precip':
    asset_name = 'projects/ut-gee-ugs-bsf-dev/assets/UT_Precip_and_Snowmelt_Image_Collections/UT_SNODAS_GRIDMET_PRECIP_PLUS_SNOWMELT_5KM_UBM_INPUT'

print(f"Using asset: {asset_name}")

# exists = ee.data.getInfo(asset_name) is not None
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

############### MAIN SCRIPT #################
if change_start:
    years = np.arange(new_start_year, end_year, 1)
else:
    years = np.arange(start_year, end_year, 1)
if len(years) == 0:
    print("No new years to process. Asset is up to date.")
    exit()
for year in years:
    print(f"\nProcessing year {year}...")
    if change_start and year == new_start_year:
        base = SnowMeltCollection(start_date=new_start, end_date=f'{year}-12-31', geometry=boundary)
        base_class = InputCollections(start_date=new_start, end_date=f'{year}-12-31', soil_thickness_raster='Random_Forest_Utah_Model_1km')
    else:
        base = SnowMeltCollection(start_date=f'{year}-01-01', end_date=f'{year}-12-31', geometry=boundary)
        base_class = InputCollections(start_date=f'{year}-01-01', end_date=f'{year}-12-31', soil_thickness_raster='Random_Forest_Utah_Model_1km')
    delta_swe = base.calculate_daily_delta_swe()
    # swe_dates = delta_swe.dates
    precip = base_class.get_precip(precip_data_type)
    # precip_dates = precip.dates
    precip_scale = ee.Number(precip.image_grab(0).projection().nominalScale())
    soil_water_input = base.calculate_daily_soil_input(precip_collection=precip, delta_swe_collection=delta_swe)
    # soil_water_input_dates = soil_water_input.dates
    soil_water_input_scale = ee.Number(soil_water_input.image_grab(0).projection().nominalScale())
    monthly_soil_water_input = soil_water_input.monthly_sum_collection
    monthly_soil_water_input_dates = monthly_soil_water_input.dates

    export = monthly_soil_water_input.export_to_asset_collection(asset_collection_path=asset_name,
                                                                region=boundary,
                                                                scale=soil_water_input_scale.getInfo(),
                                                                crs='EPSG:32612',
                                                                dates=monthly_soil_water_input_dates)
    print(f"Export task for {year} started.")