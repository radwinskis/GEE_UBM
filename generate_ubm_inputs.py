import ee 
from RadGEEToolbox import GenericCollection
from GEE_UBM import InputCollections, build_model_ready_collection, check_merged_collection
import numpy as np

# Initialize EE if not already initialized
service_account = 'localpythonscripts@ut-gee-ugs-bsf-dev.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'C:\\Users\\mradwin\\ut-gee-ugs-bsf-dev-53dcc5d729e0.json')
ee.Initialize(credentials=credentials)

def get_ubm_input_collection(
    start_year=2004,
    end_year=2025,
    UBM_model_to_use='Modified_UBM_1',
    monthly_time_step=True,
    resampling_method='focal_mean',
    soil_thickness_raster='Random_Forest_Utah_Model_1km',
    porosity_raster='POLARIS_porosity',
    field_capacity_raster='OpenLandMapFieldCap',
    wilting_point_raster='HiHydroSoilWiltPoint',
    Geo_K_raster='POLARIS_K_Sat_monthly',
    snowmelt_and_precip_collection='PRISM_SNODAS_combined_inputs_monthly',
    irrigation_collection='UT_UDWR_irrigation_inputs_monthly_scaled_30m',
    PET_collection='GRIDMET_daily_PET',
    AET_collection='GLDAS_monthly_soil_moisture',
    soil_moisture_collection='SMAP_daily_soil',
    check_overlap=True,
    asset_folder_override=None
):
    """
    Generates the UBM Input Collection for the specified parameters.
    Args:
        start_year (int): The starting year for the input collection.
        end_year (int): The ending year for the input collection.
        UBM_model_to_use (str): The UBM model variant to use ('Original_UBM', 'Modified_UBM_1', 'Modified_UBM_2').
        monthly_time_step (bool): Whether to use a monthly time step.
        resampling_method (str): The resampling method for raster data.
        soil_thickness_raster (str): The soil thickness raster to use.
        porosity_raster (str): The porosity raster to use.
        field_capacity_raster (str): The field capacity raster to use.
        wilting_point_raster (str): The wilting point raster to use.
        Geo_K_raster (str): The Geo K raster to use.
        snowmelt_and_precip_collection (str): The snowmelt and precipitation collection to use.
        irrigation_collection (str): The irrigation collection to use.
        PET_collection (str): The potential evapotranspiration collection to use.
        AET_collection (str): The actual evapotranspiration collection to use.
        soil_moisture_collection (str): The soil moisture collection to use.
        check_overlap (bool): Whether to check for spatial overlap with Utah boundary.
        asset_folder_override (str or None): Optional override for asset folder paths.
    Returns:
        GenericCollection: An object containing the merged ee.ImageCollection of inputs.
    """
    
    #--------------------------------------------#
    ############# STATIC VARIABLES ###############
    #--------------------------------------------#
    UT_boundary = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Regional_Boundary").geometry()

    print(f"Processing years: {start_year} through {end_year - 1}")
    print(f"Organizing input collection for UBM model: {UBM_model_to_use}")
    
    #---------------------------#
    ### Raster/Collection Setup #
    #---------------------------#
    static_rasters_to_use = [porosity_raster, field_capacity_raster, wilting_point_raster, Geo_K_raster]
    
    if UBM_model_to_use == 'Original_UBM':
        dynamic_collections_to_use = [snowmelt_and_precip_collection, irrigation_collection, PET_collection]
    elif UBM_model_to_use == 'Modified_UBM_1':
        dynamic_collections_to_use = [snowmelt_and_precip_collection, irrigation_collection, AET_collection]
    elif UBM_model_to_use == 'Modified_UBM_2':
        dynamic_collections_to_use = [snowmelt_and_precip_collection, irrigation_collection, AET_collection, soil_moisture_collection]
    else:
        raise ValueError(f"Invalid UBM Model: {UBM_model_to_use}")

    print(f"Using dynamic collections: {dynamic_collections_to_use}")

    #------------------------------------#
    ############# RUN LOOP ###############
    #------------------------------------#
    years = np.arange(start_year, end_year, 1)
    yearly_collections = []

    for year in years:
        print(f"Generating inputs for year {year}...")
        
        # Initialize InputCollections for the specific year
        base_class = InputCollections(
            start_date=f'{year}-01-01', 
            end_date=f'{year}-12-31', 
            soil_thickness_raster=soil_thickness_raster, 
            resampling_method=resampling_method
        )

        st_raster = base_class.soil_thickness_raster
        porosity = base_class.get_static_raster(porosity_raster)
        field_capacity = base_class.get_static_raster(field_capacity_raster) 
        wilting_point = base_class.get_static_raster(wilting_point_raster) 
        Geo_K = base_class.get_static_raster(Geo_K_raster)
        snowmelt_and_precip = base_class.get_precip_and_snowmelt(snowmelt_and_precip_collection)
        irrigation = base_class.get_irrigation(irrigation_collection)

        static_rasters_list = [st_raster, porosity, field_capacity, wilting_point, Geo_K]

        if UBM_model_to_use == 'Original_UBM':
            pet = base_class.get_PET(PET_collection)
            timeseries_collections_list = [snowmelt_and_precip, irrigation, pet]
        elif UBM_model_to_use == 'Modified_UBM_1':
            aet = base_class.get_AET(AET_collection) 
            timeseries_collections_list = [snowmelt_and_precip, irrigation, aet]
        elif UBM_model_to_use == 'Modified_UBM_2':
            aet = base_class.get_AET(AET_collection)
            soil_moisture = base_class.get_soil_moisture(soil_moisture_collection) 
            timeseries_collections_list = [snowmelt_and_precip, irrigation, aet, soil_moisture]

        model_ready_wrapper = build_model_ready_collection(
            timeseries_collections_list=timeseries_collections_list, 
            static_images_list=static_rasters_list
        )
        
        if hasattr(model_ready_wrapper, 'collection'):
            yearly_collections.append(model_ready_wrapper.collection)
        else:
            yearly_collections.append(model_ready_wrapper)

    if not yearly_collections:
        raise ValueError("No collections generated.")

    print("Merging yearly collections...")
    # merged_collection = ee.ImageCollection(yearly_collections).flatten()
    merged_collection = yearly_collections[0]
    for col in yearly_collections[1:]:
        merged_collection = merged_collection.merge(col)  
    check_merged_collection(GenericCollection(yearly_collections[0]))
    return GenericCollection(merged_collection)

def get_abbreviation_dicts():
    static_raster_abbreviation_dict = {
        'Random_Forest_Utah_Model_30m': 'RF30mST',
        'Random_Forest_Utah_Model_1km': 'RF1kmST',
        'ISRIC': 'ISRICST',
        'gNATSGO': 'gNATSGOST',
        'gNATSGO_filled': 'gNATSGOfldST',
        'gNATSGO_filled_2_meter_cap': 'gNATSGOfld2mcapST',
        'HiHydroSoilPorosity': 'HHSPor',
        'POLARIS_porosity': 'POLPor',
        'UGS_porosity': 'UGSPor',
        'UGS_fieldCap': 'UGSFC',
        'HiHydroSoilFieldCap': 'HHSFC',
        'OpenLandMapFieldCap': 'OLMFC',
        'UGS_wiltingPoint': 'UGSWP',
        'HiHydroSoilWiltPoint': 'HHSWP',
        'POLARIS_K_Sat_monthly': 'POLKsatM',
        'POLARIS_K_Sat_daily': 'POLKsatD',
        'HiHydroSoil_K_Sat_monthly': 'HSSKsatM',
        'HiHydroSoil_K_Sat_daily': 'HSSKsatD',
        'UGS_Geo_K_monthly': 'UGSGeoKM',
        'UGS_Geo_K_daily': 'UGSGeoKD',
        'USGS_Geo_K_monthly': 'USGSGeoKM',
        'USGS_Geo_K_daily': 'USGSGeoKD'
    }

    dynamic_collection_abbreviation_dict = {
        'DAYMET_SNODAS_combined_inputs_monthly': 'DAYMETSNOM',
        'PRISM_SNODAS_combined_inputs_monthly': 'PRISMSNOM',
        'GRIDMET_SNODAS_combined_inputs_monthly': 'GRIDMETSNOM',
        'UT_UDWR_irrigation_inputs_monthly_scaled_30m': 'IRRIm',
        'GRIDMET_daily_PET': 'GRIDMETPETD',
        'GRIDMET_monthly_PET': 'GRIDMETPETM',
        'ERA5_daily_PET': 'ERA5PETD',
        'ERA5_monthly_PET': 'ERA5PETM',
        'ERA5_daily_ET': 'ERA5ETD',
        'ERA5_monthly_ET': 'ERA5ETM',
        'MODIS_ET': 'MODISETD',
        'MODIS_monthly_ET': 'MODISETM',
        'OPEN_ET_DisALEXI': 'ETDisALEXI',
        'OPEN_ET_ensemble': 'ETEns',
        'OPEN_ET_PTJPL': 'ETPTJPL',
        'OPEN_ET_SIMS': 'ETSIMS',
        'OPEN_ET_SSEBOP': 'ETSSEBOP',
        'OPEN_ET_EEMETRIC': 'ETEEMETRIC',
        'OPEN_ET_GEESEBAL': 'ETGEESEBAL',
        'SMAP_daily_soil': 'SMAPSoilD',
        'SMAP_monthly_soil': 'SMAPSoilM',
        'SMAP_daily_soil_aggregate': 'SMAPSoilDAgg',
        'SMAP_monthly_soil_aggregate': 'SMAPSoilMAgg',
        'ERA5_daily_soil_moisture': 'ERA5SoilMoistD',
        'ERA5_monthly_soil_moisture': 'ERA5SoilMoistM',
        'GLDAS_daily_soil_moisture': 'GLDASSoilMoistD',
        'GLDAS_monthly_soil_moisture': 'GLDASSoilMoistM'
    }
    return static_raster_abbreviation_dict, dynamic_collection_abbreviation_dict