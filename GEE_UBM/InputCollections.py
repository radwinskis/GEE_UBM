import ee
from RadGEEToolbox import LandsatCollection, GetPalette, GenericCollection

class InputCollections: 
    """
    Class to retrieve defined static rasters and time-varying collections for hydrological modeling.

    All units are converted to mm where applicable. Collections are either daily or monthly, depending on source data.

    All rasters with a resolution less than 1 km have been downsampled to 1 km resolution to match the coarsest temporally varying input data.

        Output collections include:
        - Soil Thickness Rasters:
            - Random_Forest_Utah_Model_30m Soil Thickness (rootzone, trained on gNATSGO)
            - Random_Forest_Utah_Model_1km Soil Thickness (rootzone, trained on gNATSGO)
            - ISRIC Soil Thickness to Bedrock
            - gNATSGO Soil Thickness (rootzone)
            - gNATSGO_filled Soil Thickness (rootzone) (gNATSGO gaps filled with ISRIC values where the ISRIC fill values are divided by 10)
            - gNATSGO_filled_2_meter_cap Soil Thickness (rootzone) (gNATSGO gaps filled with ISRIC values capped at 2 meters)

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

        - Precip & Snowmelt Collections:
            - SNODAS + DAYMET Monthly Precip + Snowmelt
            - SNODAS + PRISM Monthly Precip + Snowmelt

        - Irrigation Collections:
            - UT UDWR Monthly Irrigation Depth

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
    # target_proj = ee.Projection('EPSG:32612').atScale(1000)

    @classmethod
    def _to_1km_focal(cls, img, work_proj=None, radius=500):
        target_proj = ee.Projection('EPSG:32612').atScale(1000)
        # work_proj: fine-scale metric grid to run the kernel on
        # if work_proj is None:
        #     # Force UTM 12N at the image's native scale
        #     native_scale = img.projection().nominalScale()
        #     wp = ee.Projection('EPSG:32612').atScale(native_scale)
        # else: 
        #     native_scale = work_proj.nominalScale()
        #     wp = ee.Projection('EPSG:32612').atScale(native_scale)
        # img_fine = img.reproject(wp)
        wp = work_proj or img.projection()
        img_fine = img.setDefaultProjection(wp)
        agg = img_fine.focal_mean(radius=radius, kernelType='square', units='meters')
        return agg.reproject(target_proj).set('system:time_start', img.get('system:time_start'))
    @classmethod
    def _to_1km_reduceResolution(cls, img, work_proj=None):
        target_proj = ee.Projection('EPSG:32612').atScale(1000)
        # work_proj: fine-scale metric grid to run the kernel on
        wp = work_proj or img.projection()
        # img_fine = img.reproject(wp)
        img_fine = img.setDefaultProjection(wp)
        agg = img_fine.reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)
        return agg.reproject(target_proj).set('system:time_start', img.get('system:time_start'))
    @classmethod
    def _to_1km_bilinear(cls, img, work_proj=None):
        target_proj = ee.Projection('EPSG:32612').atScale(1000)
        # work_proj: fine-scale metric grid to run the kernel on
        wp = work_proj or img.projection()
        # img_fine = img.reproject(wp)
        img_fine = img.setDefaultProjection(wp)
        agg = img_fine.resample('bilinear')
        return agg.reproject(target_proj).set('system:time_start', img.get('system:time_start'))
   
    _shapefiles = None
    
    @classmethod
    def _get_shapefiles(cls):
        """Lazy load shapefiles only when needed."""
        if cls._shapefiles is None:
            cls._shapefiles = {
                'GSL_basin': ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Watersheds/Merged_GSL_Basin_Watershed"),
                'Castle_valley': ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Watersheds/Castle_Valley_Watershed"),
                'Milford': ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Watersheds/Milford_Watershed"),
                'Sanpete': ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Watersheds/Sanpete_Watershed"),
                'Utah_Regional_Boundary': ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Regional_Boundary"),
            }
        return cls._shapefiles

    @classmethod
    def _get_soil_thickness_raster(cls, name):
        """Retrieve the soil thickness raster. Each soil thickness raster is downsampled to 1 km resolution."""
        Utah_Regional_Boundary = cls._get_shapefiles()['Utah_Regional_Boundary']
        target_proj = ee.Projection('EPSG:32612').atScale(1000)
        if name == 'ISRIC':
            image = ee.Image("projects/ut-gee-ugs-bsf-dev/assets/UT_regional_soil_depth_to_bedrock_cm_ISRIC")
            native_proj = image.projection()
            # image = image.setDefaultProjection(native_proj).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #                     .reproject(crs=native_proj, scale=1000)
            image = image.reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
                                .reproject(target_proj)
            return image.multiply(ee.Image(10)).clip(Utah_Regional_Boundary).rename('soil_thickness')
        elif name == 'gNATSGO':
            col = ee.ImageCollection('projects/sat-io/open-datasets/gNATSGO/raster/tk0_999a')
            native_proj = col.first().projection()
            # col = col.mosaic().setDefaultProjection(native_proj).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #                     .reproject(crs=native_proj, scale=1000)
            # col = col.mosaic().setDefaultProjection(native_proj).resample('bilinear')\
            #                     .reproject(crs=native_proj, scale=1000)
            col = col.mosaic()
            col = cls._to_1km_focal(col, work_proj=native_proj)
            return col.multiply(ee.Image(10)).clip(Utah_Regional_Boundary).rename('soil_thickness')
        elif name == 'gNATSGO_filled':
            # Fill gNATSGO gaps with ISRIC values
            isric_image = cls._get_soil_thickness_raster('ISRIC').divide(ee.Image(10)) 
            gNATSGO_image = cls._get_soil_thickness_raster('gNATSGO')
            filled_image = gNATSGO_image.unmask(isric_image)
            return filled_image.rename('soil_thickness')
        elif name == 'gNATSGO_filled_2_meter_cap':
            # Fill gNATSGO gaps with ISRIC values
            isric_image = cls._get_soil_thickness_raster('ISRIC').min(2000)
            gNATSGO_image = cls._get_soil_thickness_raster('gNATSGO')
            # isric_image = isric_image.reproject(gNATSGO_image.projection())
            filled_image = gNATSGO_image.unmask(isric_image)
            return filled_image.rename('soil_thickness')
        elif name == 'Random_Forest_Utah_Model_30m':
            return ee.Image('projects/ut-gee-ugs-bsf-dev/assets/UT_RandomForest_30m_gNATSGO_soil_thickness_imperviousIncluded_prediction_raster_final').rename('soil_thickness')
        elif name == 'Random_Forest_Utah_Model_1km':
            return ee.Image('projects/ut-gee-ugs-bsf-dev/assets/UT_RandomForest_1km_gNATSGO_soil_thickness_imperviousIncluded_prediction_raster_final').rename('soil_thickness')
        else:
            raise ValueError(f"Soil thickness raster '{name}' not found. Available options are: 'Random_Forest_Utah_Model_30m', 'Random_Forest_Utah_Model_1km', 'ISRIC', 'gNATSGO', 'gNATSGO_filled', 'gNATSGO_filled_2_meter_cap'.")
    
    def __init__(self, start_date, end_date, soil_thickness_raster=None, resampling_method='focal_mean'):
        self.start_date = start_date
        self.end_date = end_date
        self.Utah_Regional_Boundary = self._get_shapefiles()['Utah_Regional_Boundary']
        self.target_proj = ee.Projection('EPSG:32612').atScale(1000)
        if soil_thickness_raster is None:
            self.soil_thickness_raster = self._get_soil_thickness_raster('Random_Forest_Utah_Model_1km')
        elif isinstance(soil_thickness_raster, str):
            if soil_thickness_raster in ['Random_Forest_Utah_Model_30m', 'Random_Forest_Utah_Model_1km', 'ISRIC', 'gNATSGO', 'gNATSGO_filled', 'gNATSGO_filled_2_meter_cap']:
                self.soil_thickness_raster = self._get_soil_thickness_raster(soil_thickness_raster)
            else:
                raise ValueError(f"Soil thickness raster '{soil_thickness_raster}' not found. Available options are: 'Random_Forest_Utah_Model_30m', 'Random_Forest_Utah_Model_1km', 'ISRIC', 'gNATSGO', 'gNATSGO_filled', 'gNATSGO_filled_2_meter_cap'.")
        else:
            self.soil_thickness_raster = soil_thickness_raster
        
        if isinstance(resampling_method, str):
            if resampling_method in ['focal_mean', 'bilinear', 'reduceResolution']:
                self.resampling_method = resampling_method
            else:
                raise ValueError(f"Resampling method '{resampling_method}' not recognized. Available options are: 'focal_mean', 'bilinear', 'reduceResolution'.")
        else:
            raise ValueError(f"Resampling method must be a string. Received type {type(resampling_method)}.")

    def _add_day(self, image):
        return image.set('day_of_month', image.date().get('day'))

    def _meters_to_mm_conversion(self, image):
        return image.multiply(ee.Image(1000)).copyProperties(image).set('system:time_start', image.get('system:time_start'), 'Date_Filter', image.get('Date_Filter'))

    def _volume_fraction_to_mm_water(self, image):
        return image.multiply(self.soil_thickness_raster).copyProperties(image).set('system:time_start', image.get('system:time_start'))

    def _ERA5_soil_moisture_mean(self, image):
        expression = '(b("volumetric_soil_water_layer_1")+b("volumetric_soil_water_layer_2")+b("volumetric_soil_water_layer_3")+b("volumetric_soil_water_layer_4"))/4'
        return ee.Image(image.expression(expression).copyProperties(image).set('system:time_start', image.get('system:time_start'))).rename('Soil_Water_End_of_Previous_Timestep')

    def _ECMWF_soil_moisture_mean(self, image):
        expression = '(b("volumetric_soil_moisture_sol1")+b("volumetric_soil_moisture_sol2")+b("volumetric_soil_moisture_sol3")+b("volumetric_soil_moisture_sol4"))/4'
        return ee.Image(image.expression(expression).copyProperties(image).set('system:time_start', image.get('system:time_start'))).rename('Soil_Water_End_of_Previous_Timestep')

    @staticmethod
    def _unmask(img):
        return img.unmask(0)

    def get_static_raster(self, name):
        """
        Retrieves a static raster image by name. All static rasters are resampled to 1 km resolution.
        Options: 'UGS_porosity', 'HiHydroSoilPorosity', 'POLARIS_porosity', 'UGS_fieldCap', 
                 'HiHydroSoilFieldCap', 'OpenLandMapFieldCap', 'UGS_BMC_K', 
                 'UGS_Geo_K', 'UGS_wiltingPoint', 'HiHydroSoilWiltPoint', 'POLARIS_K_Sat_monthly', 'POLARIS_K_Sat_daily', 'HiHydroSoil_K_Sat_monthly', 'HiHydroSoil_K_Sat_daily', 'USGS_Geo_K_monthly'
        Args:
            name (str): Name of the static raster to retrieve.
        Returns:
            ee.Image: The requested static raster image.
        """
        if name == 'UGS_porosity':
            image = ee.Image("users/paulinkenbrandt/porosity")
            native_proj = image.projection()
            # if self.resampling_method == 'bilinear':
            #     image = self._to_1km_bilinear(image, work_proj=native_proj)
            # elif self.resampling_method == 'focal_mean':
            #     image = self._to_1km_focal(image, work_proj=native_proj)
            # elif self.resampling_method == 'reduceResolution':
            #     image = self._to_1km_reduceResolution(image, work_proj=native_proj)

            # image = image.setDefaultProjection(native_proj)\
            #          .reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #          .reproject(crs=native_proj, scale=1000)

            if self.resampling_method == 'bilinear':
                image = self._to_1km_bilinear(image, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                image = self._to_1km_focal(image, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                image = self._to_1km_reduceResolution(image, work_proj=native_proj)

            UGS_porosity = image.clip(self.Utah_Regional_Boundary).rename('soil_porosity')
            return UGS_porosity
        elif name == 'HiHydroSoilPorosity':
            # https://gee-community-catalog.org/projects/hihydro_soil/
            # Different images for different depths
            # Units = % or m3/m3
            col = HiHydroSoilPorosity = ee.ImageCollection("projects/sat-io/open-datasets/HiHydroSoilv2_0/wcsat")
            native_proj = col.first().projection()
            HiHydroSoilPorosity = col.mean().multiply(0.0001)
            # if self.resampling_method == 'bilinear':
            #     HiHydroSoilPorosity = self._to_1km_bilinear(HiHydroSoilPorosity, work_proj=native_proj)
            # elif self.resampling_method == 'focal_mean':
            #     HiHydroSoilPorosity = self._to_1km_focal(HiHydroSoilPorosity, work_proj=native_proj)
            # elif self.resampling_method == 'reduceResolution':
            #     HiHydroSoilPorosity = self._to_1km_reduceResolution(HiHydroSoilPorosity, work_proj=native_proj)
            if self.resampling_method == 'bilinear':
                HiHydroSoilPorosity = self._to_1km_bilinear(HiHydroSoilPorosity, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                HiHydroSoilPorosity = self._to_1km_focal(HiHydroSoilPorosity, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                HiHydroSoilPorosity = self._to_1km_reduceResolution(HiHydroSoilPorosity, work_proj=native_proj)
            HiHydroSoilPorosity = HiHydroSoilPorosity.unmask(0.5).clip(self.Utah_Regional_Boundary).rename('soil_porosity')
            # HiHydroSoilPorosity = col.mean().multiply(0.0001).setDefaultProjection(native_proj).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #                         .reproject(crs=native_proj, scale=1000).unmask(0.5).clip(self.Utah_Regional_Boundary).rename('soil_porosity')
            return HiHydroSoilPorosity
        elif name == 'POLARIS_porosity':
            # https://gee-community-catalog.org/projects/polaris/
            # Different images for different depths? Need to examine more closely
            # Units = m3/m3 or %
            col = ee.ImageCollection('projects/sat-io/open-datasets/polaris/theta_s_mean')
            native_proj = col.first().projection()
            # POLARIS_porosity = col.mean().setDefaultProjection(native_proj).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #                     .reproject(crs=native_proj, scale=1000).clip(self.Utah_Regional_Boundary).rename('soil_porosity')
            # if self.resampling_method == 'bilinear':
            #     POLARIS_porosity = self._to_1km_bilinear(col.mean(), work_proj=native_proj)
            # elif self.resampling_method == 'focal_mean':
            #     POLARIS_porosity = self._to_1km_focal(col.mean(), work_proj=native_proj)
            # elif self.resampling_method == 'reduceResolution':
            #     POLARIS_porosity = self._to_1km_reduceResolution(col.mean(), work_proj=native_proj)
            if self.resampling_method == 'bilinear':
                POLARIS_porosity = self._to_1km_bilinear(col.mean(), work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                POLARIS_porosity = self._to_1km_focal(col.mean(), work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                POLARIS_porosity = self._to_1km_reduceResolution(col.mean(), work_proj=native_proj)
            POLARIS_porosity = POLARIS_porosity.clip(self.Utah_Regional_Boundary).rename('soil_porosity')
            return POLARIS_porosity
        elif name == 'UGS_fieldCap':
            # Likely in volumetric percentage, multiply by soil thickness for mm of water
            # Converted to mm of water
            image = ee.Image("users/paulinkenbrandt/fieldCap")
            native_proj = image.projection()
            # UGS_fieldCap = image.setDefaultProjection(native_proj).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #                     .reproject(crs=native_proj, scale=1000).clip(self.Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('field_capacity')
            if self.resampling_method == 'bilinear':
                UGS_fieldCap = self._to_1km_bilinear(image, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                UGS_fieldCap = self._to_1km_focal(image, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                UGS_fieldCap = self._to_1km_reduceResolution(image, work_proj=native_proj)
            UGS_fieldCap = UGS_fieldCap.clip(self.Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('field_capacity')
            return UGS_fieldCap
        elif name == 'HiHydroSoilFieldCap':
            # https://gee-community-catalog.org/projects/hihydro_soil/
            # Different images for different depths
            # original Units = % or m3/m3
            # Using mean of profile, since a profile option is not provided
            # Converted to mm of water by multipying against soil thickness
            col = ee.ImageCollection("projects/sat-io/open-datasets/HiHydroSoilv2_0/wcpf2")
            native_proj = col.first().projection()
            # HiHydroSoilFieldCap = col.mean().multiply(0.0001).setDefaultProjection(native_proj).setDefaultProjection(native_proj).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #                     .reproject(crs=native_proj, scale=1000).clip(self.Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('field_capacity')
            HiHydroSoilFieldCap = col.mean().multiply(0.0001)
            if self.resampling_method == 'bilinear':
                HiHydroSoilFieldCap = self._to_1km_bilinear(HiHydroSoilFieldCap, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                HiHydroSoilFieldCap = self._to_1km_focal(HiHydroSoilFieldCap, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                HiHydroSoilFieldCap = self._to_1km_reduceResolution(HiHydroSoilFieldCap, work_proj=native_proj)
            HiHydroSoilFieldCap = HiHydroSoilFieldCap.clip(self.Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('field_capacity')
            return HiHydroSoilFieldCap
        elif name == 'OpenLandMapFieldCap':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenLandMap_SOL_SOL_WATERCONTENT-33KPA_USDA-4B1C_M_v01
            # different bands for different depths
            # calculating the mean for different depths
            # original units = %
            # converting to mm of water by multiplying against soil thickness
            col = ee.Image('OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01')
            native_proj = col.projection()
            # OpenLandMapFieldCap = col.expression('(b("b0")+b("b10")+b("b30")+b("b60")+b("b100")+b("b200"))/6').divide(100)\
            #     .setDefaultProjection(native_proj).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #                     .reproject(crs=native_proj, scale=1000).clip(self.Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('field_capacity')
            OpenLandMapFieldCap = col.expression('(b("b0")+b("b10")+b("b30")+b("b60")+b("b100")+b("b200"))/6').divide(100)
            if self.resampling_method == 'bilinear':
                OpenLandMapFieldCap = self._to_1km_bilinear(OpenLandMapFieldCap, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                OpenLandMapFieldCap = self._to_1km_focal(OpenLandMapFieldCap, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                OpenLandMapFieldCap = self._to_1km_reduceResolution(OpenLandMapFieldCap, work_proj=native_proj)
            OpenLandMapFieldCap = OpenLandMapFieldCap.clip(self.Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('field_capacity')
            return OpenLandMapFieldCap
        elif name == 'UGS_BMC_K':
            # Assuming original units of m/day, converted to mm/day
            image = ee.Image("users/paulinkenbrandt/BMC_K")
            native_proj = image.projection()
            # UGS_BMC_K = image.setDefaultProjection(native_proj).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #                     .reproject(crs=native_proj, scale=1000).clip(self.Utah_Regional_Boundary).multiply(ee.Image(1000)).max(ee.Image(0)).rename('Geo_K')
            if self.resampling_method == 'bilinear':
                UGS_BMC_K = self._to_1km_bilinear(image, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                UGS_BMC_K = self._to_1km_focal(image, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                UGS_BMC_K = self._to_1km_reduceResolution(image, work_proj=native_proj)
            UGS_BMC_K = UGS_BMC_K.clip(self.Utah_Regional_Boundary).multiply(ee.Image(1000)).max(ee.Image(0)).rename('BMC_K')
            return UGS_BMC_K
        elif name == 'UGS_Geo_K':
            # Assuming original units of m/day, converted to mm/day
            image = ee.Image("users/paulinkenbrandt/Geol_K")
            native_proj = image.projection()
            # UGS_Geo_K = image.setDefaultProjection(native_proj).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #                     .reproject(crs=native_proj, scale=1000).clip(self.Utah_Regional_Boundary).multiply(ee.Image(1000)).max(ee.Image(0)).rename('Geo_K')
            if self.resampling_method == 'bilinear':
                UGS_Geo_K = self._to_1km_bilinear(image, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                UGS_Geo_K = self._to_1km_focal(image, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                UGS_Geo_K = self._to_1km_reduceResolution(image, work_proj=native_proj)
            UGS_Geo_K = UGS_Geo_K.clip(self.Utah_Regional_Boundary).multiply(ee.Image(1000)).max(ee.Image(0)).rename('Geo_K')
            return UGS_Geo_K
        elif name == 'UGS_Geo_K_daily':
            # Assuming original units of m/day, converted to mm/day
            image = ee.Image("users/paulinkenbrandt/Geol_K")
            native_proj = image.projection()
            # UGS_Geo_K = image.setDefaultProjection(native_proj).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #                     .reproject(crs=native_proj, scale=1000).clip(self.Utah_Regional_Boundary).multiply(ee.Image(1000)).max(ee.Image(0)).rename('Geo_K')
            if self.resampling_method == 'bilinear':
                UGS_Geo_K = self._to_1km_bilinear(image, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                UGS_Geo_K = self._to_1km_focal(image, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                UGS_Geo_K = self._to_1km_reduceResolution(image, work_proj=native_proj)
            UGS_Geo_K = UGS_Geo_K.clip(self.Utah_Regional_Boundary).multiply(ee.Image(1000)).max(ee.Image(0)).rename('Geo_K')
            return UGS_Geo_K
        elif name == 'UGS_Geo_K_monthly':
            # Assuming original units of m/day, converted to mm/day
            image = ee.Image("users/paulinkenbrandt/Geol_K")
            native_proj = image.projection()
            # UGS_Geo_K = image.setDefaultProjection(native_proj).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #                     .reproject(crs=native_proj, scale=1000).clip(self.Utah_Regional_Boundary).multiply(ee.Image(1000)).multiply(ee.Image(30.4375)).max(ee.Image(0)).rename('Geo_K')
            if self.resampling_method == 'bilinear':
                UGS_Geo_K = self._to_1km_bilinear(image, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                UGS_Geo_K = self._to_1km_focal(image, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                UGS_Geo_K = self._to_1km_reduceResolution(image, work_proj=native_proj)
            UGS_Geo_K = UGS_Geo_K.clip(self.Utah_Regional_Boundary).multiply(ee.Image(1000)).multiply(ee.Image(30.4375)).max(ee.Image(0)).rename('Geo_K')
            return UGS_Geo_K
        elif name == 'USGS_Geo_K_monthly':
            # converted to mm/day ahead of time
            # from https://www.sciencebase.gov/catalog/item/552c4877e4b0b22a157f5061
            image = ee.Image("projects/ut-gee-ugs-bsf-dev/assets/USGS_GeoK_Utah_Clipped_mm_month")
            native_proj = image.projection()
            # USGS_Geo_K = image.setDefaultProjection(native_proj).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #                     .reproject(crs=native_proj, scale=1000).clip(self.Utah_Regional_Boundary).max(ee.Image(0)).rename('Geo_K')
            if self.resampling_method == 'bilinear':
                USGS_Geo_K = self._to_1km_bilinear(image, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                USGS_Geo_K = self._to_1km_focal(image, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                USGS_Geo_K = self._to_1km_reduceResolution(image, work_proj=native_proj)
            USGS_Geo_K = USGS_Geo_K.clip(self.Utah_Regional_Boundary).max(ee.Image(0)).rename('Geo_K')
            return USGS_Geo_K
        elif name == 'POLARIS_K_Sat_daily':
            # log10(cm/hr)
            # Using the minimum of the profile for conservative estimate of infiltration rate
            col = ee.ImageCollection('projects/sat-io/open-datasets/polaris/ksat_mean')
            native_proj = col.first().projection()
            def unlog_and_convert(img):
                return ee.Image(10).pow(img).multiply(10).multiply(24) #.multiply(30.4375)

            converted_col = col.map(unlog_and_convert)

            # 2. Reduce the collection to find the minimum pixel value across all depths
            # POLARIS_ksat = converted_col.min().setDefaultProjection(native_proj).resample('bilinear')\
            #                     .reproject(crs=native_proj, scale=1000).clip(self.Utah_Regional_Boundary).rename('Geo_K')
            POLARIS_ksat = converted_col.min()
            if self.resampling_method == 'bilinear':
                POLARIS_ksat = self._to_1km_bilinear(POLARIS_ksat, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                POLARIS_ksat = self._to_1km_focal(POLARIS_ksat, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                POLARIS_ksat = self._to_1km_reduceResolution(POLARIS_ksat, work_proj=native_proj)
            POLARIS_ksat = POLARIS_ksat.clip(self.Utah_Regional_Boundary).rename('Geo_K')
            return POLARIS_ksat
        elif name == 'POLARIS_K_Sat_monthly':
            # log10(cm/hr)
            # Using the minimum of the profile for conservative estimate of infiltration rate
            col = ee.ImageCollection('projects/sat-io/open-datasets/polaris/ksat_mean')
            native_proj = col.first().projection()
            def unlog_and_convert(img):
                return ee.Image(10).pow(img).multiply(10).multiply(24).multiply(30.4375)

            converted_col = col.map(unlog_and_convert)

            # 2. Reduce the collection to find the minimum pixel value across all depths
            # POLARIS_ksat = converted_col.min().setDefaultProjection(native_proj).resample('bilinear')\
            #                     .reproject(crs=native_proj, scale=1000).clip(self.Utah_Regional_Boundary).rename('Geo_K')
            POLARIS_ksat = converted_col.min()
            if self.resampling_method == 'bilinear':
                POLARIS_ksat = self._to_1km_bilinear(POLARIS_ksat, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                POLARIS_ksat = self._to_1km_focal(POLARIS_ksat, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                POLARIS_ksat = self._to_1km_reduceResolution(POLARIS_ksat, work_proj=native_proj)
            POLARIS_ksat = POLARIS_ksat.clip(self.Utah_Regional_Boundary).rename('Geo_K')
            return POLARIS_ksat
        elif name == 'HiHydroSoil_K_Sat_daily':
            col = ee.ImageCollection("projects/sat-io/open-datasets/HiHydroSoilv2_0/ksat")
            native_proj = col.first().projection()
            ksat = col.min().multiply(10) # convert from cm/day to mm/day
            if self.resampling_method == 'bilinear':
                ksat = self._to_1km_bilinear(ksat, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                ksat = self._to_1km_focal(ksat, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                ksat = self._to_1km_reduceResolution(ksat, work_proj=native_proj)
            ksat = ksat.clip(self.Utah_Regional_Boundary).rename('Geo_K')
            return ksat
        elif name == 'HiHydroSoil_K_Sat_monthly':
            col = ee.ImageCollection("projects/sat-io/open-datasets/HiHydroSoilv2_0/ksat")
            native_proj = col.first().projection()
            ksat = col.min().multiply(10).multiply(30.4375) # convert from cm/day to mm/month
            if self.resampling_method == 'bilinear':
                ksat = self._to_1km_bilinear(ksat, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                ksat = self._to_1km_focal(ksat, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                ksat = self._to_1km_reduceResolution(ksat, work_proj=native_proj)
            ksat = ksat.clip(self.Utah_Regional_Boundary).rename('Geo_K')
            return ksat
        elif name == 'UGS_wiltingPoint':
            # Assuming original units of %, multiplying by soil thickness to get mm of water equivalent
            image = ee.Image("users/paulinkenbrandt/WiltPoint")
            native_proj = image.projection()
            # UGS_wiltingPoint = image.setDefaultProjection(native_proj).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #                     .reproject(crs=native_proj, scale=1000).clip(self.Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('wilting_point')
            if self.resampling_method == 'bilinear':
                UGS_wiltingPoint = self._to_1km_bilinear(image, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                UGS_wiltingPoint = self._to_1km_focal(image, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                UGS_wiltingPoint = self._to_1km_reduceResolution(image, work_proj=native_proj)
            UGS_wiltingPoint = UGS_wiltingPoint.clip(self.Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('wilting_point')
            return UGS_wiltingPoint
        elif name == 'HiHydroSoilWiltPoint':
            # https://gee-community-catalog.org/projects/hihydro_soil/
            # Different images for different depths
            # Units = % or m3/m3
            # Using mean of profile, since a profile option is not provided
            # Converted to mm of water by multipying against soil thickness
            col = ee.ImageCollection("projects/sat-io/open-datasets/HiHydroSoilv2_0/wcpf4-2")
            native_proj = col.first().projection()
            # HiHydroSoilWiltPoint = col.mean().multiply(0.0001).setDefaultProjection(native_proj).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)\
            #                     .reproject(crs=native_proj, scale=1000).clip(self.Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('wilting_point')
            HiHydroSoilWiltPoint = col.mean().multiply(0.0001)
            if self.resampling_method == 'bilinear':
                HiHydroSoilWiltPoint = self._to_1km_bilinear(HiHydroSoilWiltPoint, work_proj=native_proj)
            elif self.resampling_method == 'focal_mean':
                HiHydroSoilWiltPoint = self._to_1km_focal(HiHydroSoilWiltPoint, work_proj=native_proj)
            elif self.resampling_method == 'reduceResolution':
                HiHydroSoilWiltPoint = self._to_1km_reduceResolution(HiHydroSoilWiltPoint, work_proj=native_proj)
            HiHydroSoilWiltPoint = HiHydroSoilWiltPoint.clip(self.Utah_Regional_Boundary).multiply(self.soil_thickness_raster).rename('wilting_point')
            return HiHydroSoilWiltPoint
        else:
            raise ValueError(f"Static raster '{name}' not found. Available options are: 'UGS_porosity', 'HiHydroSoilPorosity', 'POLARIS_porosity', 'UGS_fieldCap', 'HiHydroSoilFieldCap', 'OpenLandMapFieldCap', 'UGS_BMC_K', 'UGS_Geo_K_daily', 'UGS_Geo_K_monthly', 'POLARIS_K_Sat_daily', 'POLARIS_K_Sat_monthly', 'HiHydroSoil_K_Sat_daily', 'HiHydroSoil_K_Sat_monthly', 'UGS_wiltingPoint', 'HiHydroSoilWiltPoint'.")
        
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
                                                                                            .mask_to_polygon(self.Utah_Regional_Boundary).band_rename('ppt', 'precipitation')
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
                                    .mask_to_polygon(self.Utah_Regional_Boundary).band_rename('prcp', 'precipitation')
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
                                    .mask_to_polygon(self.Utah_Regional_Boundary).band_rename('pr', 'precipitation')
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
                                    .mask_to_polygon(self.Utah_Regional_Boundary)
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
                                                                                            .mask_to_polygon(self.Utah_Regional_Boundary)
            ERA5_SnowMelt = GenericCollection(collection=ERA5_SnowMelt.collection.map(self._meters_to_mm_conversion), start_date=self.start_date, end_date=self.end_date).band_rename('snowmelt_sum', 'snowmelt')
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
        
    def get_precip_and_snowmelt(self, name):
        """
        Retrieves combined snowmelt and precipitation collection by name, with a band named 'precip_and_snowmelt_input'.
        Options: 'DAYMET_SNODAS_combined_inputs_monthly', 'PRISM_SNODAS_combined_inputs_monthly', 'GRIDMET_SNODAS_combined_inputs_monthly'

        Args:
            name (str): Name of the combined collection to retrieve.
        Returns:
            Image Collection (GenericCollection): The requested combined collection as RadGEEToolbox GenericCollection object.
        """
        if name == 'DAYMET_SNODAS_combined_inputs_monthly':
            # Combining DAYMET monthly precipitation with SNODAS monthly snowmelt
            DAYMET_SNODAS_water_inputs = GenericCollection(collection=ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/UT_Precip_and_Snowmelt_Image_Collections/UT_SNODAS_DAYMET_PRECIP_PLUS_SNOWMELT_1KM_UBM_INPUT'),
                                                           start_date=self.start_date, end_date=self.end_date).mask_to_polygon(self.Utah_Regional_Boundary)
            return DAYMET_SNODAS_water_inputs
        elif name == 'PRISM_SNODAS_combined_inputs_monthly':
            PRISM_SNODAS_water_inputs = GenericCollection(collection=ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/UT_Precip_and_Snowmelt_Image_Collections/UT_SNODAS_PRISM_PRECIP_PLUS_SNOWMELT_5KM_UBM_INPUT'),
                                                           start_date=self.start_date, end_date=self.end_date).mask_to_polygon(self.Utah_Regional_Boundary)
            return PRISM_SNODAS_water_inputs
        elif name == 'GRIDMET_SNODAS_combined_inputs_monthly':
            GRIDMET_SNODAS_water_inputs = GenericCollection(collection=ee.ImageCollection('projects/ut-gee-ugs-bsf-dev/assets/UT_Precip_and_Snowmelt_Image_Collections/UT_SNODAS_GRIDMET_PRECIP_PLUS_SNOWMELT_5KM_UBM_INPUT'),
                                                           start_date=self.start_date, end_date=self.end_date).mask_to_polygon(self.Utah_Regional_Boundary)
            return GRIDMET_SNODAS_water_inputs
        else:
            raise ValueError(f"Combined Precipitation and Snowmelt collection '{name}' not found. Available options are: 'DAYMET_SNODAS_combined_inputs_monthly', 'PRISM_SNODAS_combined_inputs_monthly', 'GRIDMET_SNODAS_combined_inputs_monthly'.")
        
    def get_irrigation(self, name):
        """
        Retrives an irrigation input collection by name, where irrigation inputs are provided as mm/month of water equivalent.
        This is critical for running the UBM in agricultural areas. The data is derived from the Utah Department of Water Resources (UDWR), 
        using the state water budget data (https://dwre-utahdnr.opendata.arcgis.com/pages/water-budget) 
        and distributed spatially based on UDWR agricultural land use data (https://utahdnr.hub.arcgis.com/datasets/utahDNR::wrlu-4326-lu-group/about).

        Yearly irrigation volumes are distributed across the irrigation season (April through September) to create a monthly time series, and each month 
        is weighted based on alfalfa irrigation practices (min in spring max during July).

        Options: 'UT_UDWR_irrigation_inputs_monthly_scaled_30m'

        Args:
            name (str): Name of the irrigation input collection to retrieve.
        Returns:
            Image Collection (GenericCollection): The requested irrigation input collection as RadGEEToolbox GenericCollection object.
        """
        def unpack_multiband_to_collection(image):
            # 1. Get all band names (e.g., "20040401_depth", "20040501_depth"...)
            band_names = image.bandNames()
            
            # 2. Map over the list of bands to create a list of Images
            def band_to_image(b_name):
                # Extract the single band
                band = image.select([b_name])
                
                # Parse date from the band name
                # Assumption: Bands are named "YYYYMM01_..." by the export
                # We slice the first 8 characters to get the date string
                date_str = ee.String(b_name).slice(2, 10) 
                date = ee.Date.parse('YYYYMMdd', date_str)
                
                # Rename back to a common name (so all images match)
                # and set the crucial time property
                return band.unmask(0).clip(self.Utah_Regional_Boundary).rename('irrigation_depth_mm').set({
                    'system:time_start': date.millis(),
                    'year': date.get('year'),
                    'month': date.get('month'),
                    'Date_Filter': date.format('YYYY-MM-dd')
                })
            
            # 3. Convert list of images to ImageCollection
            images = band_names.map(band_to_image)
            return ee.ImageCollection(images)
        def unmask_img(img):
            return img.unmask(0)
        if name == 'UT_UDWR_irrigation_inputs_monthly_scaled_30m':
            img = ee.Image('projects/ut-gee-ugs-bsf-dev/assets/UT_Monthly_Scaled_Irrigation_Depth_Collection_mm_30m') #.select(['irrigation_depth_mm'])
            col = unpack_multiband_to_collection(img).select(['irrigation_depth_mm'])
            native_proj = col.first().projection()
            UT_UDWR_irrigation_inputs = GenericCollection(col, start_date=self.start_date, end_date=self.end_date)
            if self.resampling_method == 'bilinear':
                UT_UDWR_irrigation_inputs = UT_UDWR_irrigation_inputs.collection.map(lambda img: self._to_1km_bilinear(img, work_proj=native_proj)).map(unmask_img)
                UT_UDWR_irrigation_inputs = GenericCollection(UT_UDWR_irrigation_inputs, start_date=self.start_date, end_date=self.end_date).mask_to_polygon(self.Utah_Regional_Boundary).band_rename('irrigation_depth_mm', 'irrigation')
            elif self.resampling_method == 'focal_mean':
                UT_UDWR_irrigation_inputs = UT_UDWR_irrigation_inputs.collection.map(lambda img: self._to_1km_focal(img, work_proj=native_proj)).map(unmask_img)
                UT_UDWR_irrigation_inputs = GenericCollection(UT_UDWR_irrigation_inputs, start_date=self.start_date, end_date=self.end_date).mask_to_polygon(self.Utah_Regional_Boundary).band_rename('irrigation_depth_mm', 'irrigation')
            elif self.resampling_method == 'reduceResolution':
                UT_UDWR_irrigation_inputs = UT_UDWR_irrigation_inputs.collection.map(lambda img: self._to_1km_reduceResolution(img, work_proj=native_proj)).map(unmask_img)
                UT_UDWR_irrigation_inputs = GenericCollection(UT_UDWR_irrigation_inputs, start_date=self.start_date, end_date=self.end_date).mask_to_polygon(self.Utah_Regional_Boundary).band_rename('irrigation_depth_mm', 'irrigation')
            return UT_UDWR_irrigation_inputs
        else:
            raise ValueError(f"Irrigation input collection '{name}' not found. Available option is: 'UT_UDWR_irrigation_inputs_monthly_scaled_30m'.")

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
            GRIDMET_daily_PET = GenericCollection(collection=ee.ImageCollection("IDAHO_EPSCOR/GRIDMET").select(['etr']).map(self._unmask), start_date=self.start_date, end_date=self.end_date)\
                                                                                            .mask_to_polygon(self.Utah_Regional_Boundary).band_rename('etr', 'PET')
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
            ERA5_PET = GenericCollection(ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").select(['potential_evaporation_sum']).map(self._unmask), start_date=self.start_date, end_date=self.end_date)\
                                                                                            .mask_to_polygon(self.Utah_Regional_Boundary).band_rename('potential_evaporation_sum', 'PET')
            ERA5_PET = GenericCollection(collection=ERA5_PET.collection.map(self._meters_to_mm_conversion), start_date=self.start_date, end_date=self.end_date)
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
    #### I WILL WANT TO REDUCE THE RESOLUTION TO 1KM IF THIS FIXED ###
    def get_AET(self, name):
        """
        Retrieves an Actual Evapotranspiration (AET) collection by name. All Open_ET collections are resampled to 1 km resolution.
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
            ERA5_ET = GenericCollection(ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").select(['total_evaporation_sum']).map(self._unmask), start_date=self.start_date, end_date=self.end_date)\
                                                                                            .mask_to_polygon(self.Utah_Regional_Boundary).band_rename('total_evaporation_sum', 'AET')
            ERA5_ET = GenericCollection(collection=ERA5_ET.collection.map(self._meters_to_mm_conversion), start_date=self.start_date, end_date=self.end_date)
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
            # https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD16A2GF
            # 500 m pixel size
            # Units of mm/day
            MODIS_ET = GenericCollection(ee.ImageCollection("MODIS/061/MOD16A2GF").select(['ET']).filterBounds(self.Utah_Regional_Boundary).map(self._unmask), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(self.Utah_Regional_Boundary).band_rename('ET', 'AET')
            return MODIS_ET
        elif name == 'MODIS_monthly_ET':
            # https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD16A2GF
            # 500 m pixel size
            # Units of mm/month
            MODIS_ET = self.get_AET('MODIS_ET')
            MODIS_monthly_ET = MODIS_ET.monthly_mean_collection.collection.map(lambda img: img.divide(8).multiply(ee.Image(30.4375)).set('system:time_start', img.get('system:time_start'))) #Converting 8-day total to monthly total
            MODIS_monthly_ET = GenericCollection(collection=MODIS_monthly_ET, start_date=self.start_date, end_date=self.end_date)
            return MODIS_monthly_ET
        elif name == 'OPEN_ET_DisALEXI':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenET_DisALEXI_CONUS_GRIDMET_MONTHLY_v2_0
            # 30 m pixel size
            # Units of mm/month
            col = ee.ImageCollection("OpenET/DISALEXI/CONUS/GRIDMET/MONTHLY/v2_0")
            native_proj = col.filterBounds(self.Utah_Regional_Boundary).first().projection()
            OPEN_ET_DisALEXI = GenericCollection(col.select(['et']).filterBounds(self.Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(self.Utah_Regional_Boundary).mosaicByDate.band_rename('et', 'AET')
            OPEN_ET_DisALEXI = GenericCollection(collection=OPEN_ET_DisALEXI.collection.map(lambda img: self._unmask(img))).mask_to_polygon(self.Utah_Regional_Boundary)
            # OPEN_ET_DisALEXI = GenericCollection(collection=OPEN_ET_DisALEXI.collection.map(lambda img: img.setDefaultProjection(native_proj).resample('bilinear')\
            #                                 .reproject(crs=native_proj, scale=1000)), start_date=self.start_date, end_date=self.end_date)
            if self.resampling_method == 'bilinear':
                OPEN_ET_DisALEXI = OPEN_ET_DisALEXI.collection.map(lambda img: self._to_1km_bilinear(img, work_proj=native_proj))
                OPEN_ET_DisALEXI = GenericCollection(collection=OPEN_ET_DisALEXI, start_date=self.start_date, end_date=self.end_date)
            elif self.resampling_method == 'focal_mean':
                OPEN_ET_DisALEXI = OPEN_ET_DisALEXI.collection.map(lambda img: self._to_1km_focal(img, work_proj=native_proj))
                OPEN_ET_DisALEXI = GenericCollection(collection=OPEN_ET_DisALEXI, start_date=self.start_date, end_date=self.end_date)
            elif self.resampling_method == 'reduceResolution':
                OPEN_ET_DisALEXI = OPEN_ET_DisALEXI.collection.map(lambda img: self._to_1km_reduceResolution(img, work_proj=native_proj))
                OPEN_ET_DisALEXI = GenericCollection(collection=OPEN_ET_DisALEXI, start_date=self.start_date, end_date=self.end_date)
            return OPEN_ET_DisALEXI
        elif name == 'OPEN_ET_ensemble':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenET_Ensemble_CONUS_GRIDMET_MONTHLY_v2_0
            # 30 m pixel size
            # Units of mm/month
            col = ee.ImageCollection("OpenET/Ensemble/CONUS/GRIDMET/MONTHLY/v2_0")
            native_proj = col.filterBounds(self.Utah_Regional_Boundary).first().projection()
            OPEN_ET_ensemble = GenericCollection(col.select(['et_ensemble_mad']).filterBounds(self.Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(self.Utah_Regional_Boundary).mosaicByDate.band_rename('et_ensemble_mad', 'AET')
            OPEN_ET_ensemble = GenericCollection(collection=OPEN_ET_ensemble.collection.map(lambda img: self._unmask(img))).mask_to_polygon(self.Utah_Regional_Boundary)
            # OPEN_ET_ensemble = GenericCollection(collection=OPEN_ET_ensemble.collection.map(lambda img: img.setDefaultProjection(native_proj).resample('bilinear')\
            #                                 .reproject(crs=native_proj, scale=1000)), start_date=self.start_date, end_date=self.end_date)
            if self.resampling_method == 'bilinear':
                OPEN_ET_ensemble = OPEN_ET_ensemble.collection.map(lambda img: self._to_1km_bilinear(img, work_proj=native_proj))
                OPEN_ET_ensemble = GenericCollection(collection=OPEN_ET_ensemble, start_date=self.start_date, end_date=self.end_date)
            elif self.resampling_method == 'focal_mean':
                OPEN_ET_ensemble = OPEN_ET_ensemble.collection.map(lambda img: self._to_1km_focal(img, work_proj=native_proj))
                OPEN_ET_ensemble = GenericCollection(collection=OPEN_ET_ensemble, start_date=self.start_date, end_date=self.end_date)
            elif self.resampling_method == 'reduceResolution':
                OPEN_ET_ensemble =OPEN_ET_ensemble.collection.map(lambda img: self._to_1km_reduceResolution(img, work_proj=native_proj))
                OPEN_ET_ensemble = GenericCollection(collection=OPEN_ET_ensemble, start_date=self.start_date, end_date=self.end_date)
            return OPEN_ET_ensemble
        elif name == 'OPEN_ET_PTJPL':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenET_PTJPL_CONUS_GRIDMET_MONTHLY_v2_0
            # 30 m pixel size
            # Units of mm/month
            col = ee.ImageCollection("OpenET/PTJPL/CONUS/GRIDMET/MONTHLY/v2_0")
            native_proj = col.filterBounds(self.Utah_Regional_Boundary).first().projection()
            OPEN_ET_PTJPL = GenericCollection(col.select(['et']).filterBounds(self.Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(self.Utah_Regional_Boundary).mosaicByDate.band_rename('et', 'AET')
            # OPEN_ET_PTJPL = GenericCollection(collection=OPEN_ET_PTJPL.collection.map(lambda img: img.setDefaultProjection(native_proj).resample('bilinear')\
            #                                 .reproject(crs=native_proj, scale=1000)), start_date=self.start_date, end_date=self.end_date)
            OPEN_ET_PTJPL = GenericCollection(collection=OPEN_ET_PTJPL.collection.map(lambda img: self._unmask(img))).mask_to_polygon(self.Utah_Regional_Boundary)
            if self.resampling_method == 'bilinear':
                OPEN_ET_PTJPL = OPEN_ET_PTJPL.collection.map(lambda img: self._to_1km_bilinear(img, work_proj=native_proj))
                OPEN_ET_PTJPL = GenericCollection(collection=OPEN_ET_PTJPL, start_date=self.start_date, end_date=self.end_date)
            elif self.resampling_method == 'focal_mean':
                OPEN_ET_PTJPL = OPEN_ET_PTJPL.collection.map(lambda img: self._to_1km_focal(img, work_proj=native_proj))
                OPEN_ET_PTJPL = GenericCollection(collection=OPEN_ET_PTJPL, start_date=self.start_date, end_date=self.end_date)
            elif self.resampling_method == 'reduceResolution':
                OPEN_ET_PTJPL = OPEN_ET_PTJPL.collection.map(lambda img: self._to_1km_reduceResolution(img, work_proj=native_proj))
                OPEN_ET_PTJPL = GenericCollection(collection=OPEN_ET_PTJPL, start_date=self.start_date, end_date=self.end_date)
            return OPEN_ET_PTJPL
        elif name == 'OPEN_ET_SIMS':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenET_SIMS_CONUS_GRIDMET_MONTHLY_v2_0
            # 30 m pixel size
            # Units of mm/month
            col = ee.ImageCollection("OpenET/SIMS/CONUS/GRIDMET/MONTHLY/v2_0")
            native_proj = col.filterBounds(self.Utah_Regional_Boundary).first().projection()
            OPEN_ET_SIMS = GenericCollection(col.select(['et']).filterBounds(self.Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(self.Utah_Regional_Boundary).mosaicByDate.band_rename('et', 'AET')
            # OPEN_ET_SIMS = GenericCollection(collection=OPEN_ET_SIMS.collection.map(lambda img: img.setDefaultProjection(native_proj).resample('bilinear')\
            #                                 .reproject(crs=native_proj, scale=1000)), start_date=self.start_date, end_date=self.end_date)
            OPEN_ET_SIMS = GenericCollection(collection=OPEN_ET_SIMS.collection.map(lambda img: self._unmask(img))).mask_to_polygon(self.Utah_Regional_Boundary)
            if self.resampling_method == 'bilinear':
                OPEN_ET_SIMS = OPEN_ET_SIMS.collection.map(lambda img: self._to_1km_bilinear(img, work_proj=native_proj))
                OPEN_ET_SIMS = GenericCollection(collection=OPEN_ET_SIMS, start_date=self.start_date, end_date=self.end_date)
            elif self.resampling_method == 'focal_mean':
                OPEN_ET_SIMS = OPEN_ET_SIMS.collection.map(lambda img: self._to_1km_focal(img, work_proj=native_proj))
                OPEN_ET_SIMS = GenericCollection(collection=OPEN_ET_SIMS, start_date=self.start_date, end_date=self.end_date)
            elif self.resampling_method == 'reduceResolution':
                OPEN_ET_SIMS = OPEN_ET_SIMS.collection.map(lambda img: self._to_1km_reduceResolution(img, work_proj=native_proj))
                OPEN_ET_SIMS = GenericCollection(collection=OPEN_ET_SIMS, start_date=self.start_date, end_date=self.end_date)
            return OPEN_ET_SIMS
        elif name == 'OPEN_ET_SSEBOP':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenET_SSEBOP_CONUS_GRIDMET_MONTHLY_v2_0
            # 30 m pixel size
            # Units of mm/month
            col = ee.ImageCollection("OpenET/SSEBOP/CONUS/GRIDMET/MONTHLY/v2_0")
            native_proj = col.filterBounds(self.Utah_Regional_Boundary).first().projection()
            OPEN_ET_SSEBOP = GenericCollection(col.select(['et']).filterBounds(self.Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(self.Utah_Regional_Boundary).mosaicByDate.band_rename('et', 'AET')
            # OPEN_ET_SSEBOP = GenericCollection(collection=OPEN_ET_SSEBOP.collection.map(lambda img: img.setDefaultProjection(native_proj).resample('bilinear')\
            #                                 .reproject(crs=native_proj, scale=1000)), start_date=self.start_date, end_date=self.end_date)
            OPEN_ET_SSEBOP = GenericCollection(collection=OPEN_ET_SSEBOP.collection.map(lambda img: self._unmask(img))).mask_to_polygon(self.Utah_Regional_Boundary)
            if self.resampling_method == 'bilinear':
                OPEN_ET_SSEBOP = OPEN_ET_SSEBOP.collection.map(lambda img: self._to_1km_bilinear(img, work_proj=native_proj))
                OPEN_ET_SSEBOP = GenericCollection(collection=OPEN_ET_SSEBOP, start_date=self.start_date, end_date=self.end_date)
            elif self.resampling_method == 'focal_mean':
                OPEN_ET_SSEBOP = OPEN_ET_SSEBOP.collection.map(lambda img: self._to_1km_focal(img, work_proj=native_proj))
                OPEN_ET_SSEBOP = GenericCollection(collection=OPEN_ET_SSEBOP, start_date=self.start_date, end_date=self.end_date)
            elif self.resampling_method == 'reduceResolution':
                OPEN_ET_SSEBOP = OPEN_ET_SSEBOP.collection.map(lambda img: self._to_1km_reduceResolution(img, work_proj=native_proj))
                OPEN_ET_SSEBOP = GenericCollection(collection=OPEN_ET_SSEBOP, start_date=self.start_date, end_date=self.end_date)
            return OPEN_ET_SSEBOP
        elif name == 'OPEN_ET_EEMETRIC':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenET_EEMETRIC_CONUS_GRIDMET_MONTHLY_v2_0
            # 30 m pixel size
            # Units of mm/month
            col = ee.ImageCollection("OpenET/EEMETRIC/CONUS/GRIDMET/MONTHLY/v2_0")
            native_proj = col.filterBounds(self.Utah_Regional_Boundary).first().projection()
            OPEN_ET_EEMETRIC = GenericCollection(col.select(['et']).filterBounds(self.Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(self.Utah_Regional_Boundary).mosaicByDate.band_rename('et', 'AET')
            # OPEN_ET_EEMETRIC = GenericCollection(collection=OPEN_ET_EEMETRIC.collection.map(lambda img: img.setDefaultProjection(native_proj).resample('bilinear')\
            #                                 .reproject(crs=native_proj, scale=1000)), start_date=self.start_date, end_date=self.end_date)
            OPEN_ET_EEMETRIC = GenericCollection(collection=OPEN_ET_EEMETRIC.collection.map(lambda img: self._unmask(img))).mask_to_polygon(self.Utah_Regional_Boundary)
            if self.resampling_method == 'bilinear':
                OPEN_ET_EEMETRIC = OPEN_ET_EEMETRIC.collection.map(lambda img: self._to_1km_bilinear(img, work_proj=native_proj))
                OPEN_ET_EEMETRIC = GenericCollection(collection=OPEN_ET_EEMETRIC, start_date=self.start_date, end_date=self.end_date)
            elif self.resampling_method == 'focal_mean':
                OPEN_ET_EEMETRIC = OPEN_ET_EEMETRIC.collection.map(lambda img: self._to_1km_focal(img, work_proj=native_proj))
                OPEN_ET_EEMETRIC = GenericCollection(collection=OPEN_ET_EEMETRIC, start_date=self.start_date, end_date=self.end_date)
            elif self.resampling_method == 'reduceResolution':
                OPEN_ET_EEMETRIC = OPEN_ET_EEMETRIC.collection.map(lambda img: self._to_1km_reduceResolution(img, work_proj=native_proj))
                OPEN_ET_EEMETRIC = GenericCollection(collection=OPEN_ET_EEMETRIC, start_date=self.start_date, end_date=self.end_date)
            return OPEN_ET_EEMETRIC
        elif name == 'OPEN_ET_GEESEBAL':
            # https://developers.google.com/earth-engine/datasets/catalog/OpenET_GEESEBAL_CONUS_GRIDMET_MONTHLY_v2_0
            # 30 m pixel size
            # Units of mm/month
            col = ee.ImageCollection("OpenET/GEESEBAL/CONUS/GRIDMET/MONTHLY/v2_0")
            native_proj = col.filterBounds(self.Utah_Regional_Boundary).first().projection()
            OPEN_ET_GEESEBAL = GenericCollection(col.select(['et']).filterBounds(self.Utah_Regional_Boundary), 
                                                                                start_date=self.start_date, end_date=self.end_date)\
                                                                                    .mask_to_polygon(self.Utah_Regional_Boundary).mosaicByDate.band_rename('et', 'AET')
            # OPEN_ET_GEESEBAL = GenericCollection(collection=OPEN_ET_GEESEBAL.collection.map(lambda img: img.setDefaultProjection(native_proj).resample('bilinear')\
            #                                 .reproject(crs=native_proj, scale=1000)), start_date=self.start_date, end_date=self.end_date)
            OPEN_ET_GEESEBAL = GenericCollection(collection=OPEN_ET_GEESEBAL.collection.map(lambda img: self._unmask(img))).mask_to_polygon(self.Utah_Regional_Boundary)
            if self.resampling_method == 'bilinear':
                OPEN_ET_GEESEBAL = OPEN_ET_GEESEBAL.collection.map(lambda img: self._to_1km_bilinear(img, work_proj=native_proj))
                OPEN_ET_GEESEBAL = GenericCollection(collection=OPEN_ET_GEESEBAL, start_date=self.start_date, end_date=self.end_date)
            elif self.resampling_method == 'focal_mean':
                OPEN_ET_GEESEBAL = OPEN_ET_GEESEBAL.collection.map(lambda img: self._to_1km_focal(img, work_proj=native_proj))
                OPEN_ET_GEESEBAL = GenericCollection(collection=OPEN_ET_GEESEBAL, start_date=self.start_date, end_date=self.end_date)
            elif self.resampling_method == 'reduceResolution':
                OPEN_ET_GEESEBAL = OPEN_ET_GEESEBAL.collection.map(lambda img: self._to_1km_reduceResolution(img, work_proj=native_proj))
                OPEN_ET_GEESEBAL = GenericCollection(collection=OPEN_ET_GEESEBAL, start_date=self.start_date, end_date=self.end_date)
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
                SMAP_soil_first_img = GenericCollection(ee.ImageCollection("NASA/SMAP/SPL3SMP_E/006").select('soil_moisture_am'), start_date='2023-12-25', end_date='2023-12-31').mask_to_polygon(self.Utah_Regional_Boundary).image_grab(-1)\
                            .set('Date_Filter', '2024-01-01', 'system:time_start', ee.Date('2024-01-01').millis(), 'day_of_month', 1)
                SMAP_soil_daily = GenericCollection(ee.ImageCollection("NASA/SMAP/SPL3SMP_E/006").select('soil_moisture_am'), start_date=self.start_date, end_date=self.end_date).mask_to_polygon(self.Utah_Regional_Boundary)
                SMAP_soil_daily = GenericCollection(ee.ImageCollection(ee.ImageCollection([SMAP_soil_first_img]).merge(SMAP_soil_daily.collection)))

            else: 
                SMAP_soil_daily = GenericCollection(ee.ImageCollection("NASA/SMAP/SPL3SMP_E/006").select('soil_moisture_am'), start_date=self.start_date, end_date=self.end_date).mask_to_polygon(self.Utah_Regional_Boundary)
            SMAP_soil_daily = GenericCollection(collection=SMAP_soil_daily.collection.map(self._volume_fraction_to_mm_water).map(self._add_day)).band_rename('soil_moisture_am', 'Soil_Water_End_of_Previous_Timestep')
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
            SMAP_soil_daily_aggregate = GenericCollection(ee.ImageCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_SMAP_Daily_Soil_Moisture_Profile_Collection_v1").select('sm_profile').map(self._volume_fraction_to_mm_water).map(self._add_day), start_date=self.start_date, end_date=self.end_date)\
                                                                        .mask_to_polygon(self.Utah_Regional_Boundary).band_rename('sm_profile', 'Soil_Water_End_of_Previous_Timestep')

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
                                                                start_date=self.start_date, end_date=self.end_date).mask_to_polygon(self.Utah_Regional_Boundary)
            ERA5_soil_moisture_daily = GenericCollection(collection=ERA5_soil_moisture_daily.collection.map(self._ERA5_soil_moisture_mean).map(self._volume_fraction_to_mm_water).map(self._add_day), start_date=self.start_date, end_date=self.end_date)
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
                                                            start_date=self.start_date, end_date=self.end_date).mask_to_polygon(self.Utah_Regional_Boundary)\
                                                                .band_rename('SoilMoist_P_tavg', 'Soil_Water_End_of_Previous_Timestep')
            GLDAS_soil_moisture_daily = GenericCollection(collection=GLDAS_soil_moisture_daily.collection.map(self._add_day), start_date=self.start_date, end_date=self.end_date)
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