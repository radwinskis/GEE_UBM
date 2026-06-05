import ee
from RadGEEToolbox import GenericCollection

class SnowMeltCollection:
    """
    Class for calculating snowmelt (Delta SWE) from SNODAS data as well as calculating total water inputs (precipitation + snowmelt), accounting for precipitation type (rain or snow). Options for daily and monthly aggregations, exporting, and masking.
    
    SNODAS data source: https://gee-community-catalog.org/projects/snodas/

    Attributes:
        start_date (str): Start date 'YYYY-MM-DD'.
        end_date (str): End date 'YYYY-MM-DD'.
        geometry (ee.Geometry): Geometry for masking/filtering.
    """

    # SNODAS Asset ID
    SNODAS_ID = 'projects/earthengine-legacy/assets/projects/climate-engine/snodas/daily'

    def __init__(self, start_date, end_date, geometry=None):
        self.start_date = start_date
        self.end_date = end_date
        self.geometry = geometry
        
        # Initialize raw SNODAS collection and select the SWE band
        self.raw_snodas_col = ee.ImageCollection(self.SNODAS_ID).select('SWE')

    def calculate_daily_delta_swe(self):
        """
        Calculates the daily change in Snow Water Equivalent (Delta SWE) in millimeters. 
        Uses a join to find previous day's SWE for each image, and adds that image as a property.
        
        Returns:
            GenericCollection: A GenericCollection object containing daily Delta SWE images (in mm).
        """
        # 1. Define Dates
        start = ee.Date(self.start_date)
        end = ee.Date(self.end_date)
        
        # We fetch data starting 1 day prior to start_date to calculate the first day's delta.
        # We advance end date by 2 to be inclusive of the final day.
        extended_col = self.raw_snodas_col.filterDate(start.advance(-1, 'day'), end.advance(2, 'day'))

        # Mask the collection to maximize processing efficiency for the following steps
        if self.geometry:
            extended_col = GenericCollection(collection=extended_col).mask_to_polygon(self.geometry).collection

        # 2. Define the Join to find "Yesterday"
        # We look for an image where time_diff is within 25 hours, 
        # AND the match is strictly earlier than the source.
        max_diff_filter = ee.Filter.maxDifference(
            # difference=25 * 60 * 60 * 1000, # 25 hours (in millis)
            difference=72 * 60 * 60 * 1000, # 72 hours (in millis)
            leftField='system:time_start',
            rightField='system:time_start'
        )
        
        # filter to ensure rightField image is before leftField image
        less_than_filter = ee.Filter.lessThan(
            leftField='system:time_start', 
            rightField='system:time_start'
        )
        
        # Combine filters using .And()
        join_condition = ee.Filter.And(max_diff_filter, less_than_filter)

        # Define the Join operation to save the best match (closest previous day)
        save_best_join = ee.Join.saveBest(
            matchKey='prev_img',
            measureKey='time_diff'
        )

        # Apply Join: 'joined_col' is the extended_col with a 'prev_img' property added to each image
        joined_col = ee.ImageCollection(save_best_join.apply(extended_col, extended_col, join_condition))

        # 3. Calculate Delta and Convert Units
        def calc_delta(img):
            # Extract 'yesterday' from the property, cast as an ee.Image()
            prev_img = ee.Image(img.get('prev_img'))
            
            # SNODAS 'SWE' is in Meters. Convert to Millimeters (* 1000).
            
            swe_today_mm = img.select('SWE').multiply(1000)
            swe_prev_mm = prev_img.select('SWE').multiply(1000)
            
            # Delta = SWE_Today - SWE_Yesterday
            # We force unmask(0) on previous image to ensure valid subtraction if data contains absent pixels
            delta_swe = swe_today_mm.subtract(swe_prev_mm).unmask(0).rename('delta_swe')
            
            # Copy system:time_start and Date_Filter (if present)
            return delta_swe.copyProperties(img, ['system:time_start', 'Date_Filter']).set('system:time_start', img.get('system:time_start'))

        # 4. Map logic over collection
        # We use ee.Algorithms.If to check if 'prev_img' exists.
        # If it doesn't (the very first day), we return None.
        # dropNulls=True removes those None results.
        delta_col = joined_col.map(
            lambda img: ee.Algorithms.If(img.get('prev_img'), calc_delta(img), None),
            True 
        )

        # 5. Return as GenericCollection
        # We pass the processed 'delta_col' into GenericCollection.
        # GenericCollection will automatically filter it to [self.start_date, self.end_date]
        # and assign the boundary (geometry) if provided.
        gc = GenericCollection(
            collection=delta_col,
            start_date=self.start_date,
            end_date=self.end_date,
            boundary=self.geometry 
        )
        if self.geometry:
            gc = gc.mask_to_polygon(self.geometry)
        return gc

    def calculate_daily_soil_input(self, precip_collection, temp_collection, delta_swe_collection=None, joinby='date', target_scale=None):
        """
        Calculates Daily Soil Water Input using Temperature Partitioning.
        
        Logic:
        1. Rain = Precip where Mean Temp > 0°C. (Solid precip is ignored/stored).
        2. Melt = |Delta SWE| where Delta SWE < 0. (Snow leaving the pack).
        3. Input = Rain + Melt (with 0.9 sublimation factor on melt).

        Args:
            precip_collection (GenericCollection): Precipitation data (band: 'precipitation').
            temp_collection (GenericCollection): Mean Temperature data (band: 'temperature').
            delta_swe_collection (GenericCollection, optional): Output of calculate_daily_delta_swe().
            joinby (str): 'date' or 'system:time_start'.
            target_scale (int, optional): If provided, resamples all data to this scale (in meters). If None, uses precip_collection's native scale.

        Returns:
            GenericCollection: Collection with band 'precip_and_snowmelt_input' (mm).
        """
        # Get Delta SWE (if not provided)
        if delta_swe_collection is None:
            delta_swe_collection = self.calculate_daily_delta_swe()

        # Extract Collections
        # We assume temp_collection is already processed to 'temperature' band
        delta_col = delta_swe_collection.collection.select('delta_swe')
        precip_col = precip_collection.collection.select('precipitation')
        temp_col = temp_collection.collection.select('temperature')

        # Define Join
        if joinby == 'date':
            filter_join = ee.Filter.equals(leftField='Date_Filter', rightField='Date_Filter')
        elif joinby == 'system:time_start':
            filter_join = ee.Filter.equals(leftField='system:time_start', rightField='system:time_start')
        else:
            raise ValueError("joinby must be 'date' or 'system:time_start'.")
        
        join = ee.Join.inner()

        # Join Precip + Temp (To calculate Rain)
        precip_temp_joined = join.apply(precip_col, temp_col, filter_join)
        
        rain_threshold = 1.5  # Degrees Celsius

        def calc_rain(feature):
            p_img = ee.Image(feature.get('primary'))
            t_img = ee.Image(feature.get('secondary'))
            
            # Rain = Precip where Temp > rain_threshold.
            # If Temp <= rain_threshold, we assume it is snow and ignore it (it will appear as Melt later).
            rain = p_img.where(t_img.lte(rain_threshold), 0)
            
            return rain.rename('rain').copyProperties(p_img, ['system:time_start', 'Date_Filter'])
        
        rain_col = ee.ImageCollection(precip_temp_joined.map(calc_rain))

        # Join Rain + Delta SWE (To add Melt)
        rain_melt_joined = join.apply(rain_col, delta_col, filter_join)

        # Capture Projection for Resampling (From Precip/Rain)
        reference_proj = precip_col.first().projection()
        # reference_scale = reference_proj.nominalScale()
        if target_scale is not None:
            reference_scale = ee.Number(target_scale)
        else:
            reference_scale = reference_proj.nominalScale()
        target_proj = ee.Projection('EPSG:32612').atScale(reference_scale)

        def solve_balance(feature):
            rain_img = ee.Image(feature.get('primary'))
            delta_img_native = ee.Image(feature.get('secondary'))

            # Melt = |Delta| where Delta < 0. Else 0.
            melt_native = delta_img_native.where(delta_img_native.gt(0), 0).abs().multiply(0.9)

            rain_img = rain_img.resample('bilinear').reproject(target_proj)
            
            # native_scale = ee.Number(delta_img_native.projection().nominalScale())
            # is_finer = native_scale.lt(reference_scale)

            # # SNODAS: reduce only if finer than precip scale; else upsample
            # delta_img = ee.Image(ee.Algorithms.If(
            #     is_finer,
            #     delta_img_native.reduceResolution(
            #         reducer=ee.Reducer.mean(), maxPixels=65536),
            #     delta_img_native.resample('bilinear')
            # )).reproject(target_proj)
            
            # delta = delta_img.select('delta_swe')
            rain = rain_img #.select('rain')
            
            # --- Melt Calculation ---
            # If Delta < 0: Melt + Sublimation occurred.
            # Melt = |Delta| * 0.9 (assuming 10% sublimation)
            # If Delta > 0: Accumulation. Melt = 0.
            
            # melt = delta.where(delta.gt(0), 0).abs().multiply(0.9)

            melt = melt_native.reduceResolution(
                reducer=ee.Reducer.mean(), maxPixels=65536
            ).reproject(target_proj) #.select('delta_swe')
            
            # --- Total Input ---
            total_input = rain.add(melt)
            
            return total_input.rename('precip_and_snowmelt_input')\
                .copyProperties(rain_img, ['system:time_start', 'Date_Filter'])

        final_col = ee.ImageCollection(rain_melt_joined.map(solve_balance))

        # Wrap result
        gc = GenericCollection(
            collection=final_col,
            start_date=self.start_date,
            end_date=self.end_date,
            boundary=self.geometry
        )
        
        if self.geometry:
            gc = gc.mask_to_polygon(self.geometry)
            
        return gc
    
    def get_monthly_delta_swe(self, daily_delta_collection=None):
        """
        Aggregates daily Delta SWE to Monthly Net Change in SWE.
        """
        if daily_delta_collection is None:
            daily_delta_collection = self.calculate_daily_delta_swe()
            
        return daily_delta_collection.monthly_sum_collection

    def export_collection(self, collection_obj, asset_path, region=None, scale=1000, crs='EPSG:32612', filename_prefix='export_'):
        """
        Wrapper to export a collection to GEE Asset.
        """
        if region is None:
            region = self.geometry

        collection_obj.export_to_asset_collection(
            asset_collection_path=asset_path,
            region=region,
            scale=scale,
            crs=crs,
            filename_prefix=filename_prefix,
            max_pixels=1e13
        )