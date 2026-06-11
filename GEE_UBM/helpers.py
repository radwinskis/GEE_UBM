import ee
from RadGEEToolbox import LandsatCollection, GetPalette, GenericCollection

def harmonize_to_target(source_image, target_proj, downsample_method='focal_mean'):
    """
    Resamples a source image to a target projection, intelligently
    choosing the resampling method AND explicitly preserving critical properties.

    Args:
        source_image (ee.Image): The image to be resampled.
        target_proj (ee.Projection): The target projection.
    
    Returns:
        ee.Image: The resampled image with preserved properties.
    """
    source_scale = source_image.projection().nominalScale()
    target_scale = target_proj.nominalScale()
    is_finer = source_scale.lt(target_scale)
    
    if downsample_method == 'focal_mean':
        downsampled = source_image.focal_mean(radius=500, kernelType='square', units='meters').reproject(crs=target_proj)
    elif downsample_method == 'reduceResolution':
        downsampled = source_image.reduceResolution(
            reducer=ee.Reducer.mean(), maxPixels=65536
        ).reproject(crs=target_proj)
    elif downsample_method == 'nearest_neighbor':
        downsampled = source_image.reproject(crs=target_proj)
    else:
        raise ValueError("Invalid downsample_method. Choose 'focal_mean', 'reduceResolution', or 'nearest_neighbor'.")
    
    # interpolated = source_image.resample('bilinear').reproject(
    #     crs=target_proj
    # )
    interpolated = ee.Image(ee.Algorithms.If(
        ee.Number(target_scale).eq(30),
        source_image.reproject(crs=target_proj),
        source_image.resample('bilinear').reproject(crs=target_proj)
    ))

    resampled_image = ee.Image(ee.Algorithms.If(
        is_finer, downsampled, interpolated
    ))
    
    final_image = resampled_image.copyProperties(
        source_image, source_image.propertyNames()
    )
    # Failsafe: Explicitly set critical properties
    final_image = final_image.set(
        'system:time_start', source_image.get('system:time_start'),
        'Date_Filter', source_image.get('Date_Filter')
    )
    return final_image

def build_model_ready_collection(timeseries_collections_list, static_images_list, verbose=False, target_crs='EPSG:32612', target_scale=None):
    """
    Takes a Python list of time-series GenericCollection image collections and a Python
    list of static ee.Images, and builds a combined GenericCollection image collection, 
    where each band of each image corresponds to the provided input collections/images.
    
    Args:
        timeseries_collections_list (list of GenericCollection objects): List of time-series collections.
        static_images_list (list of ee.Image objects): List of static images.
        verbose (bool): If True, prints progress information. Default is False.
    """
    if not timeseries_collections_list:
        raise ValueError("The timeseries_collections_list is empty.")

    # --- Server-Side Orchestration ---
    
    # === Part 1: Find Master Grid (from time-series) ===
    ee_col_list = ee.List([c.collection for c in timeseries_collections_list])

    def get_first_image_proj(coll):
        return ee.ImageCollection(coll).first().projection()
    
    # Map to get projections of first images in each collection
    projections = ee_col_list.map(get_first_image_proj)
    
    # Map to get nominal scales of each projection
    def get_scale(proj):
        return ee.Projection(proj).nominalScale()
    
    # Map to get nominal scales of each projection
    scales = projections.map(get_scale)
    
    # Determine the coarsest scale and its index
    max_scale = scales.reduce(ee.Reducer.max())
    # Get the index of the coarsest scale in the scales list (to find corresponding projection)
    # max_index = scales.indexOf(max_scale)
    # # Get the target projection (coarsest)
    # target_proj = ee.Projection(projections.get(max_index)) # Master grid

    if target_scale:
        ts = ee.Algorithms.If(ee.Number(target_scale).gt(0), target_scale, max_scale)
    else:
        ts = max_scale
    target_proj = ee.Projection(target_crs).atScale(ts)

    if verbose:
        try:
            print(f"Target CRS: {target_crs}, Target scale (m): {ee.Number(ts).getInfo()}")
        except Exception:
            pass
    
    # === Part 2: Harmonize and Merge Time-Series ===
    def harmonize_collection(coll):
        coll = ee.ImageCollection(coll) # Cast
        def harmonize_image(img):
            return harmonize_to_target(img, target_proj)
        return coll.map(harmonize_image)

    # Map harmonization over all time-series collections so that they share the same grid
    harmonized_list = ee_col_list.map(harmonize_collection)
    
    # Get the first collection to start the accumulation
    master_coll = ee.ImageCollection(harmonized_list.get(0))
    # Get the rest of the collections to iterate over. Effectively slicing off the first element.
    others_list = harmonized_list.slice(1)
    
    def server_side_merge(coll_to_add, master_coll_accumulator):
        # Cast inputs to ImageCollections
        master_coll = ee.ImageCollection(master_coll_accumulator)
        coll_to_add = ee.ImageCollection(coll_to_add)
        
        # Join collections on 'Date_Filter' property
        join = ee.Join.inner()
        # Define the filter to match images by 'Date_Filter'
        flt = ee.Filter.equals(leftField='Date_Filter', rightField='Date_Filter')
        # Apply the join, resulting in a FeatureCollection of matched pairs where 'Date_Filter' matches the same date as in master_coll
        paired = join.apply(master_coll, coll_to_add, flt)
        
        # Function to attach bands from secondary to primary image. purpose: merge bands for each date.
        def attach_bands(feature):
            primary = ee.Image(feature.get('primary'))
            secondary = ee.Image(feature.get('secondary'))
            return primary.addBands(secondary, None, True)
        
        return paired.map(attach_bands)

    # Run the iteration to merge all time-series collections
    # Iterating purpose: merge bands from each collection for each date
    merged_timeseries_coll = ee.ImageCollection(
        others_list.iterate(server_side_merge, master_coll)
    )
    
    # === Part 3: Harmonize and Add Static Bands (FIXED) ===
    # Convert static images list to ee.List
    ee_static_list = ee.List(static_images_list)
    
    # Harmonize each static image to the target projection
    def harmonize_static(img):
        return harmonize_to_target(ee.Image(img), target_proj, downsample_method='focal_mean')
    # Map harmonization over static images, resulting in ee.List of harmonized static images
    harmonized_static_images = ee_static_list.map(harmonize_static)
    
    # We must iterate over the ee.List to combine them into one image
    # Get the first image to start the accumulation
    first_static_image = ee.Image(harmonized_static_images.get(0))
    # Get the rest of the images to iterate over
    remaining_static_images = harmonized_static_images.slice(1)
    
    # Define the server-side iteration function
    def combine_images_iterator(image, accumulator_image):
        # Add the next image as a band to the accumulated image
        return ee.Image(accumulator_image).addBands(ee.Image(image))
        
    # Run the iteration - purpose: combine all static images into one image with multiple bands
    combined_static_bands = ee.Image(
        remaining_static_images.iterate(
            combine_images_iterator,  # The function to apply
            first_static_image        # The starting point (accumulator)
        )
    )

    # Map over the merged time-series to add the static bands
    def add_static_bands_map(image):
        return image.addBands(combined_static_bands)
        
    final_collection = merged_timeseries_coll.map(add_static_bands_map)
    
    if verbose:
        print(f"Server-side harmonization and merge plan created for "
              f"{len(timeseries_collections_list)} time-series and "
              f"{len(static_images_list)} static bands.")
    
    # Wrap in GenericCollection for the final output
    # Note: We assume all time-series collections share the same dates and boundary
    # so we can take these from the first collection in the list.
    # start_date, end_date, boundary, _dates_list are preserved from the first collection of the provided list.
    return GenericCollection(
        collection=final_collection,
        start_date=timeseries_collections_list[0].start_date,
        end_date=timeseries_collections_list[0].end_date,
        boundary=timeseries_collections_list[0].boundary,
        _dates_list=timeseries_collections_list[0]._dates_list 
    )

def check_merged_collection(merged_collection):
    """
    Prints out the band names and their scales from the first image of the merged collection. A way to verify harmonization.
    Args:
        merged_collection (GenericCollection): The merged GenericCollection to check.
    """
    first_image = merged_collection.collection.first()
    band_names = first_image.bandNames().getInfo()
    print("Bands and scale in the merged collection's first image:")

    for b in band_names:
        band_proj = first_image.select(b).projection()
        crs = band_proj.crs().getInfo()
        scale = band_proj.nominalScale().getInfo()
        print(f"  Band '{b}': CRS = {crs}, Scale = {scale}m")