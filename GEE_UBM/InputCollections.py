import ee
from RadGEEToolbox import LandsatCollection, GetPalette, GenericCollection

### --- Shapefiles --- ###
GSL_basin = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Watersheds/Merged_GSL_Basin_Watershed")
Castle_valley =  ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Watersheds/Castle_Valley_Watershed")
Milford = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Watersheds/Milford_Watershed")
Sanpete = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Watersheds/Sanpete_Watershed")
Utah_Regional_Boundary = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Regional_Boundary")

### --- Helper Functions --- ###

def add_day(image):
    return image.set('day_of_month', image.date().get('day'))

def meters_to_mm_conversion(image):
    return image.multiply(ee.Image(1000)).copyProperties(image).set('system:time_start', image.get('system:time_start'), 'Date_Filter', image.get('Date_Filter'))

# https://data.isric.org/geonetwork/srv/api/records/f36117ea-9be5-4afd-bb7d-7a3e77bf392a
# https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0169748
# Units = cm originaly, converted to mm depth
### ISRIC has best coverage of Utah, but there is disagreement with gNATSGO in some areas - ISRIC generally shows deeper soils
UT_DepthToBedrock = ee.Image("projects/ut-gee-ugs-bsf-dev/assets/UT_regional_soil_depth_to_bedrock_cm_ISRIC").multiply(ee.Image(10)).clip(Utah_Regional_Boundary).rename('soil_thickness')

gNATSGO_tk0_999a = ee.ImageCollection('projects/sat-io/open-datasets/gNATSGO/raster/tk0_999a').mosaic().multiply(ee.Image(10)).clip(Utah_Regional_Boundary).rename('soil_thickness')

# Setting a notebook wide variable for which raster to use as `soil_thickness`
# this will allow for easily changing over to a new soil_thickness raster for conversions down the line
soil_thickness_raster = UT_DepthToBedrock

def volume_fraction_to_mm_water(image):
    return image.multiply(soil_thickness_raster).copyProperties(image).set('system:time_start', image.get('system:time_start'))

def ERA5_soil_moisture_mean(image):
    expression = '(b("volumetric_soil_water_layer_1")+b("volumetric_soil_water_layer_2")+b("volumetric_soil_water_layer_3")+b("volumetric_soil_water_layer_4"))/4'
    return ee.Image(image.expression(expression).copyProperties(image).set('system:time_start', image.get('system:time_start'))).rename('Soil_Water_End_of_Previous_Timestep')

def ECMWF_soil_moisture_mean(image):
    expression = '(b("volumetric_soil_moisture_sol1")+b("volumetric_soil_moisture_sol2")+b("volumetric_soil_moisture_sol3")+b("volumetric_soil_moisture_sol4"))/4'
    return ee.Image(image.expression(expression).copyProperties(image).set('system:time_start', image.get('system:time_start'))).rename('Soil_Water_End_of_Previous_Timestep')

### --- Input Collections Module Class --- ###

class InputCollections: 
    """
    Class to retrieve defined static rasters and time-varying collections for hydrological modeling.

    All units are converted to mm where applicable. Collections are either daily or monthly, depending on source data.

        Output collections include:
        - Static Rasters:
            - UGS Porosity
            - HiHydroSoil Porosity
            - POLARIS Porosity
            - UGS Field Capacity
            - HiHydroSoil Field Capacity
            - OpenLandMap Field Capacity
            - UGS Bedrock Material Conductivity (BMC K)
            - UGS Geological Material Conductivity (Geo K)
            - UGS Wilting Point
            - HiHydroSoil Wilting Point

        - Precipitation Collections:
            - PRISM Daily Precipitation
            - PRISM Monthly Precipitation
            - DAYMET Daily Precipitation
            - DAYMET Monthly Precipitation
            - GRIDMET Daily Precipitation
            - GRIDMET Monthly Precipitation
            - CHIRPS Daily Precipitation
            - CHIRPS Monthly Precipitation
        
        - Snowmelt Collections:
            - ERA5 Daily Snowmelt
            - ERA5 Monthly Snowmelt
            - SMAP Daily Snowmelt
            - SMAP Monthly Snowmelt

        - Potential Evapotranspiration (PET) Collections:
            - GRIDMET Daily PET
            - GRIDMET Monthly PET
            - ERA5 Daily PET
            - ERA5 Monthly PET

        - Actual Evapotranspiration (AET) Collections:
            - ERA5 Daily AET
            - ERA5 Monthly AET
            - MODIS Daily AET
            - MODIS Monthly AET
            - OPEN ET DisALEXI Monthly AET
            - OPEN ET Ensemble Monthly AET
            - OPEN ET PTJPL Monthly AET
            - OPEN ET SIMS Monthly AET
            - OPEN ET SSEBOP Monthly AET
            - OPEN ET EEMETRIC Monthly AET
            - Open ET GEESEBAL Monthly AET

        - Soil Moisture Collections:
            - SMAP Radiometer Daily Soil Moisture Profile
            - SMAP Radiometer Monthly Soil Moisture Profile
            - SMAP Model Daily Soil Moisture Profile
            - SMAP Model Monthly Soil Moisture Profile
            - ERA5 Daily Soil Moisture Profile
            - ERA5 Monthly Soil Moisture Profile
            - GLDAS Daily Soil Moisture Profile
            - GLDAS Monthly Soil Moisture Profile

    Attributes:
        start_date (str): Start date for time-varying collections in 'YYYY-MM-DD' format.
        end_date (str): End date for time-varying collections in 'YYYY-MM-DD' format.
        soil_thickness_raster (ee.Image): Raster image representing soil thickness in mm.
    
    """
    def __init__(self, start_date, end_date, soil_thickness_raster=soil_thickness_raster):
        self.start_date = start_date
        self.end_date = end_date
        self.soil_thickness_raster = soil_thickness_raster

    def get_static_raster(self, name):
        """
        Retrieves a static raster image by name.
        Options: 'UGS_porosity', 'HiHydroSoilPorosity', 'POLARIS_porosity', 'UGS_fieldCap', 
                 'HiHydroSoilFieldCap', 'OpenLandMapFieldCap', 'UGS_BMC_K', 
                 'UGS_Geo_K', 'UGS_wiltingPoint', 'HiHydroSoilWiltPoint'
        Args:
            name (str): Name of the static raster to retrieve.
        Returns:
            ee.Image: The requested static raster image.
        """
        if name == 'UGS_porosity':
            UGS_porosity = ee.Image("users/paulinkenbrandt/porosity").clip(Utah_Regional_Boundary).rename('soil_porosity')
            return UGS_porosity
        elif name == 'HiHydroSoilPorosity':
            # https://gee-community-catalog.org/projects/hihydro_soil/
            # Different images for different depths
            # Units = % or m3/m3
            HiHydroSoilPorosity = ee.ImageCollection("projects/sat-io/open-datasets/HiHydroSoilv2_0/wcsat").mean().clip(Utah_Regional_Boundary).rename('soil_porosity')
            return HiHydroSoilPorosity
        elif name == 'POLARIS_porosity':
            # https://gee-community-catalog.org/projects/polaris/
            # Different images for different depths? Need to examine more closely
            # Units = m3/m3 or %
            POLARIS_porosity = ee.ImageCollection('projects/sat-io/open-datasets/polaris/theta_s_mean').mean().clip(Utah_Regional_Boundary).rename('soil_porosity')
            return POLARIS_porosity
        elif name == 'UGS_fieldCap':
            # Likely in volumetric percentage, multiply by soil thickness for mm of water
            # Converted to mm of water
            UGS_fieldCap = ee.Image("users/paulinkenbrandt/fieldCap").clip(Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('field_capacity')
            return UGS_fieldCap
        elif name == 'HiHydroSoilFieldCap':
            # https://gee-community-catalog.org/projects/hihydro_soil/
            # Different images for different depths
            # original Units = % or m3/m3
            # Using mean of profile, since a profile option is not provided
            # Converted to mm of water by multipying against soil thickness
            HiHydroSoilFieldCap = ee.ImageCollection("projects/sat-io/open-datasets/HiHydroSoilv2_0/wcpf2").mean().clip(Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('field_capacity')
            return HiHydroSoilFieldCap
        elif name == 'OpenLandMapFieldCap':
            # https://gee-community-catalog.org/projects/polaris/
            # different bands for different depths
            # calculating the mean for different depths
            # original units = %
            # converting to mm of water by multiplying against soil thickness
            OpenLandMapFieldCap = ee.Image('OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01')\
                .expression('(b("b0")+b("b10")+b("b30")+b("b60")+b("b100")+b("b200"))/6').clip(Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('field_capacity')
            return OpenLandMapFieldCap
        elif name == 'UGS_BMC_K':
            # Assuming original units of m/day, converted to mm/day
            UGS_BMC_K = ee.Image("users/paulinkenbrandt/BMC_K").clip(Utah_Regional_Boundary).multiply(ee.Image(1000)).rename('Geo_K')
            return UGS_BMC_K
        elif name == 'UGS_Geo_K':
            # Assuming original units of m/day, converted to mm/day
            UGS_Geo_K = ee.Image("users/paulinkenbrandt/Geol_K").clip(Utah_Regional_Boundary).multiply(ee.Image(1000)).rename('Geo_K')
            return UGS_Geo_K
        elif name == 'UGS_wiltingPoint':
            # Assuming original units of %, multiplying by soil thickness to get mm of water equivalent
            UGS_wiltingPoint = ee.Image("users/paulinkenbrandt/WiltPoint").clip(Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('wilting_point')
            return UGS_wiltingPoint
        elif name == 'HiHydroSoilWiltPoint':
            # https://gee-community-catalog.org/projects/hihydro_soil/
            # Different images for different depths
            # Units = % or m3/m3
            # Using mean of profile, since a profile option is not provided
            # Converted to mm of water by multipying against soil thickness
            HiHydroSoilWiltPoint = ee.ImageCollection("projects/sat-io/open-datasets/HiHydroSoilv2_0/wcpf4-2").mean().clip(Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('wilting_point')
            return HiHydroSoilWiltPoint
        else:
            raise ValueError(f"Static raster '{name}' not found. Available options are: 'UGS_porosity', 'HiHydroSoilPorosity', 'POLARIS_porosity', 'UGS_fieldCap', 'HiHydroSoilFieldCap', 'OpenLandMapFieldCap', 'UGS_BMC_K', 'UGS_Geo_K', 'UGS_wiltingPoint', 'HiHydroSoilWiltPoint'.")
        
    def get_precip(self, name):
        """
        Retrieves a precipitation collection by name.
        Options: 'PRISM_daily_precip', 'PRISM_monthly_precip', 'DAYMET_daily_precip', 
                 'DAYMET_monthly_precip', 'GRIDMET_daily_precip', 'GRIDMET_monthly_precip', 
                 'CHIIRPS_daily_precip', 'CHIIRPS_monthly_precip'
        Args:
            name (str): Name of the precipitation collection to retrieve.
        Returns:
            Image Collection (GenericCollection): The requested precipitation collection as RadGEEToolbox GenericCollection object.
        """
        if name == 'PRISM_daily_precip':
            # https://developers.google.com/earth-engine/datasets/catalog/OREGONSTATE_PRISM_ANd
            # 5.4 km pixel size
            # Units of mm/day
            PRISM_daily_precip = GenericCollection(collection=ee.ImageCollection("OREGONSTATE/PRISM/ANd").select(['ppt']), start_date=self.start_date, end_date=self.end_date)\
                                                                                            .mask_to_polygon(Utah_Regional_Boundary).band_rename('ppt', 'precipitation')
            return PRISM_daily_precip
        elif name == 'PRISM_monthly_precip':
            # https://developers.google.com/earth-engine/datasets/catalog/OREGONSTATE_PRISM_AN81m
            # 5.4 km pixel size
            # Units of mm/month
            # DATA ONLY AVAILABLE UP TO THE END OF 2020
            PRISM_daily_precip = self.get_precip('PRISM_daily_precip')
            PRISM_monthly_precip = PRISM_daily_precip.monthly_sum_collection #Creating monthly aggregation from daily dataset
            return PRISM_monthly_precip
        elif name == 'DAYMET_daily_precip':
            # https://developers.google.com/earth-engine/datasets/catalog/NASA_ORNL_DAYMET_V4
            # 1 km pixel size
            # Units of mm/day
            DAYMET_daily_precip = GenericCollection(collection=ee.ImageCollection("NASA/ORNL/DAYMET_V4").select(['prcp']), start_date=self.start_date, end_date=self.end_date)\
                                    .mask_to_polygon(Utah_Regional_Boundary).band_rename('prcp', 'precipitation')
            return DAYMET_daily_precip
        elif name == 'DAYMET_monthly_precip':
            # https://developers.google.com/earth-engine/datasets/catalog/NASA_ORNL_DAYMET_V4
            # 1 km pixel size
            # Units of mm/month
            DAYMET_daily_precip = self.get_precip('DAYMET_daily_precip')
            DAYMET_monthly_precip = DAYMET_daily_precip.monthly_sum_collection
            return DAYMET_monthly_precip
        elif name == 'GRIDMET_daily_precip':
            # https://developers.google.com/earth-engine/datasets/catalog/IDAHO_EPSCOR_GRIDMET
            # 4.5 km pixel size
            # Units of mm/day
            GRIDMET_daily_precip = GenericCollection(collection=ee.ImageCollection("IDAHO_EPSCOR/GRIDMET").select(['pr']), start_date=self.start_date, end_date=self.end_date)\
                                    .mask_to_polygon(Utah_Regional_Boundary).band_rename('pr', 'precipitation')
            return GRIDMET_daily_precip
        elif name == 'GRIDMET_monthly_precip':
            # https://developers.google.com/earth-engine/datasets/catalog/IDAHO_EPSCOR_GRIDMET
            # 4.5 km pixel size
            # Units of mm/month
            GRIDMET_daily_precip = self.get_precip('GRIDMET_daily_precip')
            GRIDMET_monthly_precip = GRIDMET_daily_precip.monthly_sum_collection
            return GRIDMET_monthly_precip
        elif name == 'CHIIRPS_daily_precip':
            # https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY
            # 5.5 km pixel size
            # Units of mm/day
            CHIIRPS_daily_precip = GenericCollection(collection=ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").select(['precipitation']), start_date=self.start_date, end_date=self.end_date)\
                                    .mask_to_polygon(Utah_Regional_Boundary)
            return CHIIRPS_daily_precip
        elif name == 'CHIIRPS_monthly_precip':
            # https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY
            # 5.5 km pixel size
            # Units of mm/month
            CHIIRPS_daily_precip = self.get_precip('CHIIRPS_daily_precip')
            CHIIRPS_monthly_precip = CHIIRPS_daily_precip.monthly_sum_collection
            return CHIIRPS_monthly_precip
        else:
            raise ValueError(f"Precipitation collection '{name}' not found. Available options are: 'PRISM_daily_precip', 'PRISM_monthly_precip', 'DAYMET_daily_precip', 'DAYMET_monthly_precip', 'GRIDMET_daily_precip', 'GRIDMET_monthly_precip', 'CHIIRPS_daily_precip', 'CHIIRPS_monthly_precip'.")
        
    def get_snowmelt(self, name):
        """
        Retrieves a snowmelt collection by name.
        Options: 'ERA5_daily_SnowMelt', 'ERA5_monthly_SnowMelt', 'SMAP_daily_SnowMelt', 'SMAP_monthly_SnowMelt'
        Args:
            name (str): Name of the snowmelt collection to retrieve.
        Returns:
            Image Collection (GenericCollection): The requested snowmelt collection as RadGEEToolbox GenericCollection object.
        """
        if name == 'ERA5_daily_SnowMelt':
            # https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR
            # 11 km pixel size
            # oroginal units of meters of water equivalent / day
            # Units converted to mm/day
            ERA5_SnowMelt = GenericCollection(collection=ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").select(['snowmelt_sum']), start_date=self.start_date, end_date=self.end_date)\
                                                                                            .mask_to_polygon(Utah_Regional_Boundary)
            ERA5_SnowMelt = GenericCollection(collection=ERA5_SnowMelt.collection.map(meters_to_mm_conversion), start_date=self.start_date, end_date=self.end_date).band_rename('snowmelt_sum', 'snowmelt')
            return ERA5_SnowMelt
        elif name == 'ERA5_monthly_SnowMelt':
            # https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR
            # 11 km pixel size
            # original units of meters of water equivalent / month
            # Units converted to mm/month
            ERA5_SnowMelt = self.get_snowmelt('ERA5_daily_SnowMelt')
            ERA5_monthly_SnowMelt = ERA5_SnowMelt.monthly_sum_collection
            return ERA5_monthly_SnowMelt
        elif name == 'SMAP_daily_SnowMelt':
            # https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008
            # 11 km pixel size
            # units of kg/m^2/s, equivalent to mm of water per second
            SMAP_SnowMelt = GenericCollection(collection=ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/Utah_SMAP_Daily_Snowmelt_Collection_v1').select('snow_melt_flux'), start_date=self.start_date, end_date=self.end_date)\
                                                                    .smap_flux_to_mm().band_rename('snow_melt_flux_mm', 'snowmelt')
            return SMAP_SnowMelt
        elif name == 'SMAP_monthly_SnowMelt':
            # https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008
            # 11 km pixel size
            # units of kg/m^2/s, equivalent to mm of water per second
            SMAP_SnowMelt = self.get_snowmelt('SMAP_daily_SnowMelt')
            SMAP_monthly_SnowMelt = SMAP_SnowMelt.monthly_sum_collection
            return SMAP_monthly_SnowMelt
        else:
            raise ValueError(f"Snowmelt collection '{name}' not found. Available options are: 'ERA5_daily_SnowMelt', 'ERA5_monthly_SnowMelt', 'SMAP_daily_SnowMelt', 'SMAP_monthly_SnowMelt'.")
        
    def get_PET(self, name):
        """
        Retrieves a Potential Evapotranspiration (PET) collection by name.
        Options: 'GRIDMET_daily_PET', 'GRIDMET_monthly_PET', 'ERA5_daily_PET', 'ERA5_monthly_PET'
        Args:
            name (str): Name of the PET collection to retrieve.
        Returns:
            Image Collection (GenericCollection): The requested PET collection as RadGEEToolbox GenericCollection object.
        """
        if name == 'GRIDMET_daily_PET':
            # https://developers.google.com/earth-engine/datasets/catalog/IDAHO_EPSCOR_GRIDMET
            # Daily data with a few days of lag
            # 4.5 km pixel size
            # Units of mm/day
             # Daily alfalfa reference evapotranspiration
            GRIDMET_daily_PET = GenericCollection(collection=ee.ImageCollection("IDAHO_EPSCOR/GRIDMET").select(['etr']), start_date=self.start_date, end_date=self.end_date)\
                                                                                            .mask_to_polygon(Utah_Regional_Boundary).band_rename('etr', 'PET')
            return GRIDMET_daily_PET
        elif name == 'GRIDMET_monthly_PET':
            # https://developers.google.com/earth-engine/datasets/catalog/IDAHO_EPSCOR_GRIDMET
            # Daily data with a few days of lag
            # 4.5 km pixel size
            # Units of mm/month
            GRIDMET_daily_PET = self.get_PET('GRIDMET_daily_PET')
            GRIDMET_monthly_PET = GRIDMET_daily_PET.monthly_sum_collection
            return GRIDMET_monthly_PET
        elif name == 'ERA5_daily_PET':
            # https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR
            # Daily data with one month lag
            # 11 km pixel size
            # units of meters of water equivalent
            # Units converted to mm/day
            ERA5_PET = GenericCollection(ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").select(['potential_evaporation_sum']), start_date=self.start_date, end_date=self.end_date)\
                                                                                            .mask_to_polygon(Utah_Regional_Boundary).band_rename('potential_evaporation_sum', 'PET')
            ERA5_PET = GenericCollection(collection=ERA5_PET.collection.map(meters_to_mm_conversion), start_date=self.start_date, end_date=self.end_date)
            return ERA5_PET
        elif name == 'ERA5_monthly_PET':
            # https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR
            # Daily data with one month lag
            # 11 km pixel size
            # units of meters of water equivalent
            # Units converted to mm/month
            ERA5_daily_PET = self.get_PET('ERA5_daily_PET')
            ERA5_monthly_PET = ERA5_daily_PET.monthly_sum_collection
            return ERA5_monthly_PET
        else:
            raise ValueError(f"PET collection '{name}' not found. Available options are: 'GRIDMET_daily_PET', 'GRIDMET_monthly_PET', 'ERA5_daily_PET', 'ERA5_monthly_PET'.")
        
    def get_AET(self, name):
        """
        Retrieves an Actual Evapotranspiration (AET) collection by name.
        Options: 'ERA5_daily_ET', 'ERA5_monthly_ET', 'MODIS_ET', 'MODIS_monthly_ET',
                 'OPEN_ET_DisALEXI', 'OPEN_ET_ensemble', 'OPEN_ET_PTJPL', 'OPEN_ET_SIMS',
                 'OPEN_ET_SSEBOP', 'OPEN_ET_EEMETRIC', 'OPEN_ET_GEESEBAL'
        Args:
            name (str): Name of the AET collection to retrieve.
        Returns:
            Image Collection (GenericCollection): The requested AET collection as RadGEEToolbox GenericCollection object.
        """
        if name == 'ERA5_daily_ET':
            # https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR
            # 11 km pixel size
            # units of meters of water equivalent
            # Units converted to mm/day
            ERA5_ET = GenericCollection(ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").select(['total_evaporation_sum']), start_date=self.start_date, end_date=self.end_date)\
                                                                                            .mask_to_polygon(Utah_Regional_Boundary).band_rename('total_evaporation_sum', 'AET')
            ERA5_ET = GenericCollection(collection=ERA5_ET.collection.map(meters_to_mm_conversion), start_date=self.start_date, end_date=self.end_date)
            return ERA5_ET
        elif name == 'ERA5_monthly_ET':
            # https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR
            # 11 km pixel size
            # units of meters of water equivalent
            # Units converted to mm/month
            ERA5_daily_ET = self.get_AET('ERA5_daily_ET')
            ERA5_monthly_ET = ERA5_daily_ET.monthly_sum_collection
            return ERA5_monthly_ET
        elif name == 'MODIS_ET':
            # https://developers.google.com/earth-engine/datasets/catalog/MODIS_006_MCD15A3H
            # 500 m pixel size
            # Units of mm/day
            MODIS_ET = GenericCollection(ee.ImageCollection("MODIS/006/MCD15A3H").select(['ET']).filterBounds(Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(Utah_Regional_Boundary).band_rename('ET', 'AET')
            return MODIS_ET
        elif name == 'MODIS_monthly_ET':
            # https://developers.google.com/earth-engine/datasets/catalog/MODIS_006_MCD15A3H
            # 500 m pixel size
            # Units of mm/month
            MODIS_ET = self.get_AET('MODIS_ET')
            MODIS_monthly_ET = MODIS_ET.monthly_sum_collection
            return MODIS_monthly_ET
        elif name == 'OPEN_ET_DisALEXI':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenET_DisALEXI_CONUS_GRIDMET_MONTHLY_v2_0
            # 30 m pixel size
            # Units of mm/month
            OPEN_ET_DisALEXI = GenericCollection(ee.ImageCollection("OpenET/DisALEXI/CONUS/GRIDMET/MONTHLY/v2_0").select(['et']).filterBounds(Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(Utah_Regional_Boundary).MosaicByDate.band_rename('et', 'AET')
            return OPEN_ET_DisALEXI
        elif name == 'OPEN_ET_ensemble':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenET_Ensemble_CONUS_GRIDMET_MONTHLY_v2_0
            # 30 m pixel size
            # Units of mm/month
            OPEN_ET_ensemble = GenericCollection(ee.ImageCollection("OpenET/Ensemble/CONUS/GRIDMET/MONTHLY/v2_0").select(['et_ensemble_mad']).filterBounds(Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(Utah_Regional_Boundary).MosaicByDate.band_rename('et_ensemble_mad', 'AET')
            return OPEN_ET_ensemble
        elif name == 'OPEN_ET_PTJPL':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenET_PTJPL_CONUS_GRIDMET_MONTHLY_v2_0
            # 30 m pixel size
            # Units of mm/month
            OPEN_ET_PTJPL = GenericCollection(ee.ImageCollection("OpenET/PTJPL/CONUS/GRIDMET/MONTHLY/v2_0").select(['et']).filterBounds(Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(Utah_Regional_Boundary).MosaicByDate.band_rename('et', 'AET')
            return OPEN_ET_PTJPL
        elif name == 'OPEN_ET_SIMS':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenET_SIMS_CONUS_GRIDMET_MONTHLY_v2_0
            # 30 m pixel size
            # Units of mm/month
            OPEN_ET_SIMS = GenericCollection(ee.ImageCollection("OpenET/SIMS/CONUS/GRIDMET/MONTHLY/v2_0").select(['et']).filterBounds(Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(Utah_Regional_Boundary).MosaicByDate.band_rename('et', 'AET')
            return OPEN_ET_SIMS
        elif name == 'OPEN_ET_SSEBOP':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenET_SSEBOP_CONUS_GRIDMET_MONTHLY_v2_0
            # 30 m pixel size
            # Units of mm/month
            OPEN_ET_SSEBOP = GenericCollection(ee.ImageCollection("OpenET/SSEBOP/CONUS/GRIDMET/MONTHLY/v2_0").select(['et']).filterBounds(Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(Utah_Regional_Boundary).MosaicByDate.band_rename('et', 'AET')
            return OPEN_ET_SSEBOP
        elif name == 'OPEN_ET_EEMETRIC':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenET_EEMETRIC_CONUS_GRIDMET_MONTHLY_v2_0
            # 30 m pixel size
            # Units of mm/month
            OPEN_ET_EEMETRIC = GenericCollection(ee.ImageCollection("OpenET/EEMETRIC/CONUS/GRIDMET/MONTHLY/v2_0").select(['et']).filterBounds(Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(Utah_Regional_Boundary).MosaicByDate.band_rename('et', 'AET')
            return OPEN_ET_EEMETRIC
        elif name == 'OPEN_ET_GEESEBAL':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenET_GEESEBAL_CONUS_GRIDMET_MONTHLY_v2_0
            # 30 m pixel size
            # Units of mm/month
            OPEN_ET_GEESEBAL = GenericCollection(ee.ImageCollection("OpenET/GEESEBAL/CONUS/GRIDMET/MONTHLY/v2_0").select(['et']).filterBounds(Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(Utah_Regional_Boundary).MosaicByDate.band_rename('et', 'AET')
            return OPEN_ET_GEESEBAL
        else:
            raise ValueError(f"AET collection '{name}' not found. Available options are: 'ERA5_daily_ET', 'ERA5_monthly_ET', 'MODIS_ET', 'MODIS_monthly_ET', 'OPEN_ET_DisALEXI', 'OPEN_ET_ensemble', 'OPEN_ET_PTJPL', 'OPEN_ET_SIMS', 'OPEN_ET_SSEBOP', 'OPEN_ET_EEMETRIC', 'OPEN_ET_GEESEBAL'.")
        
    def get_soil_moisture(self, name):
        """
        Retrieves a soil moisture collection by name.
        Options: 'SMAP_daily_soil', 'SMAP_monthly_soil', 'SMAP_daily_soil_aggregate', 
                 'SMAP_monthly_soil_aggregate', 'ERA5_daily_soil_moisture', 
                 'ERA5_monthly_soil_moisture', 'GLDAS_daily_soil_moisture', 
                 'GLDAS_monthly_soil_moisture'
        SMAP_daily_soil and SMAP_monthly_soil are raw radiometer soil moisture measurements at 9 km resolution
        SMAP_daily_soil_aggregate and SMAP_monthly_soil_aggregate are modelled soil moisture profiles at 11 km resolution

        Args:
            name (str): Name of the soil moisture collection to retrieve.
        Returns:
            Image Collection (GenericCollection): The requested soil moisture collection as RadGEEToolbox GenericCollection object.
        """
        if name == 'SMAP_daily_soil':
            # https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL3SMP_E_006
            # 9km pixel size
            # units of m3/m3 or volume fraction percentage
            # Converted to mm water equivalent
            if self.start_date == '2024-01-01':
                # There is no Jan 1 image for 2024 so I am grabbing the last image from Dec 2023 and setting the date to Jan 1 2024
                SMAP_soil_first_img = GenericCollection(ee.ImageCollection("NASA/SMAP/SPL3SMP_E/006").select('soil_moisture_am'), start_date='2023-12-25', end_date='2023-12-31').mask_to_polygon(Utah_Regional_Boundary).image_grab(-1)\
                            .set('Date_Filter', '2024-01-01', 'system:time_start', ee.Date('2024-01-01').millis(), 'day_of_month', 1)
                SMAP_soil_daily = GenericCollection(ee.ImageCollection("NASA/SMAP/SPL3SMP_E/006").select('soil_moisture_am'), start_date=self.start_date, end_date=self.end_date).mask_to_polygon(Utah_Regional_Boundary)
                SMAP_soil_daily = GenericCollection(ee.ImageCollection(ee.ImageCollection([SMAP_soil_first_img]).merge(SMAP_soil_daily.collection)))

            else: 
                SMAP_soil_daily = GenericCollection(ee.ImageCollection("NASA/SMAP/SPL3SMP_E/006").select('soil_moisture_am'), start_date=self.start_date, end_date=self.end_date).mask_to_polygon(Utah_Regional_Boundary)
            SMAP_soil_daily = GenericCollection(collection=SMAP_soil_daily.collection.map(volume_fraction_to_mm_water).map(add_day)).band_rename('soil_moisture_am', 'Soil_Water_End_of_Previous_Timestep')
            return SMAP_soil_daily
        elif name == 'SMAP_monthly_soil':
            # https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL3SMP_E_006
            # 9km pixel size
            # units of m3/m3 or volume fraction percentage
            # Converted to mm water equivalent
            SMAP_soil_daily = self.get_soil_moisture('SMAP_daily_soil')
            SMAP_soil_monthly = GenericCollection(collection=SMAP_soil_daily.collection.filter(ee.Filter.eq('day_of_month', 1)))
            return SMAP_soil_monthly
        elif name == 'SMAP_daily_soil_aggregate':
            # https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008
            # 11 km pixel size
            # units of m3/m3
            SMAP_soil_daily_aggregate = GenericCollection(ee.ImageCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_SMAP_Daily_Soil_Moisture_Profile_Collection_v1").select('sm_profile').map(volume_fraction_to_mm_water).map(add_day), start_date=self.start_date, end_date=self.end_date)\
                                                                        .mask_to_polygon(Utah_Regional_Boundary).band_rename('sm_profile', 'Soil_Water_End_of_Previous_Timestep')

            return SMAP_soil_daily_aggregate
        elif name == 'SMAP_monthly_soil_aggregate':
            # https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008
            # 11 km pixel size
            # units of m3/m3
            SMAP_soil_daily_aggregate = self.get_soil_moisture('SMAP_daily_soil_aggregate')
            SMAP_soil_monthly_aggregate = GenericCollection(collection=SMAP_soil_daily_aggregate.collection.filter(ee.Filter.eq('day_of_month', 1)), start_date=self.start_date, end_date=self.end_date)
            return SMAP_soil_monthly_aggregate
        elif name == 'ERA5_daily_soil_moisture':
            # https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR
            # 11 km pixel size
            # volumetric fraction of water in depth interval - layer 1 = 0-7 cm, layer 2 = 7-28 cm, layer 3 = 28-100 cm, layer 4 = 100-289 cm
            # Using the average of volumetric fraction for each depth interval for a representative value of volumetric fraction of water in profile
            # Converted to mm water equivalent
            ERA5_soil_moisture_daily = GenericCollection(ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").select(['volumetric_soil_water_layer_1', 'volumetric_soil_water_layer_2', 
                                                        'volumetric_soil_water_layer_3', 'volumetric_soil_water_layer_4']), 
                                                                start_date=self.start_date, end_date=self.end_date).mask_to_polygon(Utah_Regional_Boundary)
            ERA5_soil_moisture_daily = GenericCollection(collection=ERA5_soil_moisture_daily.collection.map(ERA5_soil_moisture_mean).map(volume_fraction_to_mm_water).map(add_day), start_date=self.start_date, end_date=self.end_date)
            return ERA5_soil_moisture_daily
        elif name == 'ERA5_monthly_soil_moisture':
            # https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR
            # 11 km pixel size
            # volumetric fraction of water in depth interval - layer 1 = 0-7 cm, layer 2 = 7-28 cm, layer 3 = 28-100 cm, layer 4 = 100-289 cm
            # Using the average of volumetric fraction for each depth interval for a representative value of volumetric fraction of water in profile
            # Converted to mm water equivalent
            ERA5_soil_moisture_daily = self.get_soil_moisture('ERA5_daily_soil_moisture')
            ERA5_soil_moisture_monthly = GenericCollection(collection=ERA5_soil_moisture_daily.collection.filter(ee.Filter.eq('day_of_month', 1)), start_date=self.start_date, end_date=self.end_date)
            return ERA5_soil_moisture_monthly
        elif name == 'GLDAS_daily_soil_moisture':
            # https://developers.google.com/earth-engine/datasets/catalog/NASA_GLDAS_V022_CLSM_G025_DA1D
            # 27 km pixel size
            # band options of 'SoilMoist_P_tavg', 'SoilMoist_RZ_tavg', 'SoilMoist_S_tavg' - USING SoilMoist_P_tavg
            # units of kg/m^2 - P = profile, RZ = root zone, S = surface
            # Units effectively are of mm height of water. density of water = 1000 kg/m3 -> (kg/m2)*(m3/1000 kg) = meters -> meters * (1000 mm / meter) = mm -> so the units are already in mm of water
            GLDAS_soil_moisture_daily = GenericCollection(ee.ImageCollection("NASA/GLDAS/V022/CLSM/G025/DA1D").select(['SoilMoist_P_tavg']), 
                                                            start_date=self.start_date, end_date=self.end_date).mask_to_polygon(Utah_Regional_Boundary)\
                                                                .band_rename('SoilMoist_P_tavg', 'Soil_Water_End_of_Previous_Timestep')
            GLDAS_soil_moisture_daily = GenericCollection(collection=GLDAS_soil_moisture_daily.collection.map(add_day), start_date=self.start_date, end_date=self.end_date)
            return GLDAS_soil_moisture_daily
        elif name == 'GLDAS_monthly_soil_moisture':
            # https://developers.google.com/earth-engine/datasets/catalog/NASA_GLDAS_V022_CLSM_G025_DA1D
            # 27 km pixel size
            # band options of 'SoilMoist_P_tavg', 'SoilMoist_RZ_tavg', 'SoilMoist_S_tavg' - USING SoilMoist_P_tavg
            # units of kg/m^2 - P = profile, RZ = root zone, S = surface
            # Units effectively are of mm height of water. density of water = 1000 kg/m3 -> (kg/m2)*(m3/1000 kg) = meters -> meters * (1000 mm / meter) = mm -> so the units are already in mm of water
            GLDAS_soil_moisture_daily = self.get_soil_moisture('GLDAS_daily_soil_moisture')
            GLDAS_soil_moisture_monthly = GenericCollection(collection=GLDAS_soil_moisture_daily.collection.filter(ee.Filter.eq('day_of_month', 1)), start_date=self.start_date, end_date=self.end_date)
            return GLDAS_soil_moisture_monthly
        else:
            raise ValueError(f"Soil moisture collection '{name}' not found. Available options are: 'SMAP_daily_soil', 'SMAP_monthly_soil', 'SMAP_daily_soil_aggregate', 'SMAP_monthly_soil_aggregate', 'ERA5_daily_soil_moisture', 'ERA5_monthly_soil_moisture',  'GLDAS_daily_soil_moisture', 'GLDAS_monthly_soil_moisture'.")