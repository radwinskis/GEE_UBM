import ee
from RadGEEToolbox import GenericCollection

class SnowMeltCollection:
    """
    Class for calculating snowmelt (Delta SWE) from SNODAS data. Options for daily and monthly aggregations, exporting, and masking.
    
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
            difference=25 * 60 * 60 * 1000, # 25 hours (in millis)
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

    def calculate_daily_soil_input(self, precip_collection, delta_swe_collection=None, joinby='date'):
        """
        Calculates Daily Soil Water Input by combining SNODAS Delta-SWE with a Precipitation Collection.
        As the UBM will mainly be used for monthly timesteps, this is necessary to account for daily processes and 
        allow for accurate monthly aggregations from daily data. Depending on the value of Delta_SWE, calculation of water input varies such that 
        Input = Precip - Delta_SWE for accumulation days (Delta_SWE > 0) and Input = Precip + |Delta_SWE|*0.9 for ablation days (Delta_SWE <= 0).
        The 0.9 factor accounts for sublimation losses during melt, assuming roughly 10% sublimation. The expression `Input = Precip - Delta_SWE` accounts for
        precipitation as rain or snow, such that there is no need to account for phase changes separately.

        Features:
        - Reprojects/Resamples SNODAS to match the Precipitation grid.
        - Applies Reverse Mass Balance Logic: Input = Precip - Delta_SWE.
        - Handles Accumulation (clamping negative input) and Ablation (applying sublimation).

        Args:
            precip_collection (GenericCollection): The precipitation collection (e.g., from InputCollections).
                                                   Must have a band named 'precipitation'.
            delta_swe_collection (GenericCollection, optional): The output of calculate_daily_delta_swe(). 
                                                                If None, it is calculated automatically.
            joinby (str, optional): The property to join collections by. Defaults to 'date'. Options: 'date' or 'system:time_start'.

        Returns:
            GenericCollection: A GenericCollection containing 'precip_and_snowmelt_input' (mm).
        """
        # 1. Get Delta SWE (if not provided)
        if delta_swe_collection is None:
            delta_swe_collection = self.calculate_daily_delta_swe()

        # 2. Extract collections
        delta_col = delta_swe_collection.collection.select('delta_swe')
        precip_col = precip_collection.collection.select('precipitation')

        # 3. Capture Target Projection from Precipitation (The "Master Grid")
        # We will force SNODAS to match this grid.
        reference_proj = precip_col.first().projection()

        # 4. Join Precip to Delta SWE with options to use 'date' or 'system:time_start' depending on what is available from input datasets
        if joinby == 'date':
            filter_date = ee.Filter.equals(leftField='Date_Filter', rightField='Date_Filter')
        elif joinby == 'system:time_start':
            filter_date = ee.Filter.equals(leftField='system:time_start', rightField='system:time_start')
        else:
            raise ValueError("joinby must be either 'date' or 'system:time_start'.")
        # Use inner join to ensure only matching dates are processed
        join = ee.Join.inner()
        combined_col = join.apply(delta_col, precip_col, filter_date)

        # 5. Apply Mass Balance Logic with Grid Alignment
        def solve_mass_balance(feature):
            # Inner join returns features with 'primary' (Delta) and 'secondary' (Precip)
            delta_img_native = ee.Image(feature.get('primary'))
            precip_img = ee.Image(feature.get('secondary'))
            
            # Reproject Delta SWE to match Precip grid.
            # Use 'bilinear' resampling to smooth SNODAS pixels into the Precip grid.
            delta_img = delta_img_native.reproject(
                crs=reference_proj).resample('bilinear')
            
            delta = delta_img.select('delta_swe')
            P = precip_img.select('precipitation')
            
            # --- Handling different scenarios  ---
            # Case A: Accumulation (Delta > 0)
            # Snowpack captured the Precip. Input = P - Delta.
            # Clamp to 0 to prevent negative input (if Delta > P due to noise).
            input_accum = P.subtract(delta).max(0)
            
            # Case B: Ablation/Steady (Delta <= 0)
            # Snowpack released water or Rain-on-Snow. Input = P + Melt.
            # Melt = |Delta|. Sublimation (0.9) applied ONLY to Melt.
            melt_component = delta.abs().multiply(0.9)
            input_ablation = P.add(melt_component)
            
            # Combine scenarios using where(), such that delta > 0 uses 
            # accumulation logic and delta <= 0 uses ablation logic
            daily_input = input_ablation.where(delta.gt(0), input_accum)
            
            # the output image has a band named 'precip_and_snowmelt_input' and retains time properties
            return daily_input.rename('precip_and_snowmelt_input')\
                .copyProperties(delta_img_native, ['system:time_start', 'Date_Filter']).set('system:time_start', delta_img_native.get('system:time_start'))

        # Apply the mass balance arithemtic over the combined collection
        final_col = ee.ImageCollection(combined_col.map(solve_mass_balance))

        # Wrap result
        gc = GenericCollection(
            collection=final_col,
            start_date=self.start_date,
            end_date=self.end_date,
            boundary=self.geometry
        )
        
        # Mask to geometry if provided
        if self.geometry:
            gc = gc.mask_to_polygon(self.geometry)
            
        return gc

    def get_monthly_delta_swe(self, daily_delta_collection=None):
        """
        Aggregates daily Delta SWE to Monthly Net Change in SWE.
        
        Args:
            daily_delta_collection (GenericCollection, optional): Result from calculate_daily_delta_swe().
                                   If None, will calculate it on the fly.
        
        Returns:
            GenericCollection: Monthly summed Delta SWE.
        """
        if daily_delta_collection is None:
            daily_delta_collection = self.calculate_daily_delta_swe()
            
        return daily_delta_collection.monthly_sum_collection

    def export_collection(self, collection_obj, asset_path, region=None, scale=1000, filename_prefix='export_'):
        """
        Wrapper to export a collection to GEE Asset using GenericCollection's export tool.
        
        Args:
            collection_obj (GenericCollection): The collection to export (Delta SWE or Soil Input).
            asset_path (str): 'projects/ut-gee-ugs-bsf-dev/assets/...'
            region (ee.Geometry, optional): defaults to self.geometry
            scale (int): defaults to 1000 (1km)
        """
        if region is None:
            region = self.geometry

        collection_obj.export_to_asset_collection(
            asset_collection_path=asset_path,
            region=region,
            scale=scale,
            filename_prefix=filename_prefix,
            max_pixels=1e13
        )