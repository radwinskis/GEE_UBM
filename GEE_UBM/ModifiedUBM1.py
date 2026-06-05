import ee
from RadGEEToolbox import LandsatCollection, GetPalette, GenericCollection

### Modified UBM Model 1 Workflow - ET as input

def Modified_1_UBM_Step_Function(current_image, previous_state_list):
    # Initialization of initial state image to set initial state of soil moisture    
    previous_state_list = ee.List(previous_state_list)

    previous_output_image = ee.Image(previous_state_list.get(-1))

    Soil_Water_End_Of_Previous_Timestep = previous_output_image.select('Soil_Water_End_Of_Previous_Timestep')

    legacy_inputs = False

    # Legacy inputs mean separating precipitation and snowmelt into different datasets, if you have them.
    if legacy_inputs == True:
        # Define inputs from `current_image`
        soil_porosity = current_image.select('soil_porosity')
        soil_thickness = current_image.select('soil_thickness')
        field_capacity = current_image.select('field_capacity')
        wilting_point = current_image.select('wilting_point')
        geo_K = current_image.select('Geo_K')
        precipitation = current_image.select('precipitation')
        snowmelt = current_image.select('snowmelt')
        irrigation = current_image.select('irrigation')
        ET = current_image.select('AET')
        zero_image = precipitation.multiply(0) #⚠️⚠️⚠️ needing to create a zero image with correct projection and properties
        # Calculate Available Water in mm of water
        Available_Water_Initial = precipitation.add(snowmelt).add(irrigation).add(Soil_Water_End_Of_Previous_Timestep)

    elif legacy_inputs == False:
        # This is the chosen iteration version for production
        # Define inputs from `current_image`
        soil_porosity = current_image.select('soil_porosity')
        soil_thickness = current_image.select('soil_thickness')
        field_capacity = current_image.select('field_capacity')
        wilting_point = current_image.select('wilting_point')
        geo_K = current_image.select('Geo_K')
        precip_and_snowmelt = current_image.select('precip_and_snowmelt_input')
        irrigation = current_image.select('irrigation')
        ET = current_image.select('AET')
        zero_image = precip_and_snowmelt.multiply(0) #⚠️⚠️⚠️ needing to create a zero image with correct projection and properties
        # Calculate Available Water in mm of water
        Available_Water_Initial = precip_and_snowmelt.add(irrigation).add(Soil_Water_End_Of_Previous_Timestep)
        

    ET_offset = ET.min(Available_Water_Initial) #If ET is larger than available water, account for this so we don't get a negative value
    Available_Water = Available_Water_Initial.subtract(ET_offset)
    
    # Calclulate Max Soil Moisture in mm of water
    Max_Soil_Moisture = soil_porosity.multiply(soil_thickness)

    ### Defining calculations for each if-else scenario below
    ####################################################
    # Scenario 1: If Available_Water > Max_Soil_Moisture
    # -------------------------------------------------
    Available_Water_for_Recharge_Scenario_1 = Max_Soil_Moisture.subtract(field_capacity)
    Recharge_Scenario_1 = Available_Water_for_Recharge_Scenario_1.min(geo_K).rename('Recharge')

    # Interpediate state/step (after rock drains, before runoff calculation)
    S_intermediate = Available_Water.subtract(Recharge_Scenario_1)

    Runoff_Scenario_1 = S_intermediate.subtract(Max_Soil_Moisture).max(zero_image).rename('Runoff')
    Runoff_Scenario_1 = zero_image.max(Runoff_Scenario_1).rename('Runoff')

    # Clamping soil moisture to max soil moisture after runoff
    Soil_Water_End_Of_Previous_Timestep_Scenario_1 = S_intermediate.where(
            S_intermediate.gt(Max_Soil_Moisture), 
            Max_Soil_Moisture
        ).rename('Soil_Water_End_Of_Previous_Timestep')
    # Clamping soil moisture to zero as a safety check
    Soil_Water_End_Of_Previous_Timestep_Scenario_1 = zero_image.max(Soil_Water_End_Of_Previous_Timestep_Scenario_1).rename('Soil_Water_End_Of_Previous_Timestep')
    Soil_Saturation_Percent_Scenario_1 = ee.Image(Soil_Water_End_Of_Previous_Timestep_Scenario_1.divide(Max_Soil_Moisture).multiply(100)).rename('Soil_Saturation_Percent_End_Of_Timestep')
    Soil_Water_Balance_Scenario_1 = ee.Image([Runoff_Scenario_1, Recharge_Scenario_1, Soil_Water_End_Of_Previous_Timestep_Scenario_1, Soil_Saturation_Percent_Scenario_1])

    ####################################################
    # Scenario 2: Elif Available_Water > Field_Capacity
    # -------------------------------------------------
    
    # Calculate Gravity Water
    Available_Water_for_Recharge_Scenario_2 = Available_Water.subtract(field_capacity)
    
    # Recharge
    Recharge_Scenario_2 = Available_Water_for_Recharge_Scenario_2.min(geo_K).rename('Recharge')
    
    # No Runoff in Scenario 2
    Runoff_Scenario_2 = zero_image.rename('Runoff')
    
    # Soil Moisture Update (Standard Math)
    Soil_Water_Raw_2 = Available_Water.subtract(Recharge_Scenario_2)
    
    # Calculate the max possible gravity water (Static Map)
    Gravity_Zone_Capacity = Max_Soil_Moisture.subtract(field_capacity)
    
    # This condition depends ONLY on rock properties, not on rain/history.
    drain_is_guaranteed = geo_K.gte(Gravity_Zone_Capacity)

    # ==============================================================================
    # If the drain pipe (K) is larger than the bucket's gravity zone size, it is physically impossible for water to remain above FC.
    # In such case, we force the result to the STATIC 'field_capacity' map. This breaks the computation chain immediately, freeing up memory for GEE.
    # ==============================================================================
    
    Soil_Water_End_Of_Previous_Timestep_Scenario_2 = Soil_Water_Raw_2.where(
        drain_is_guaranteed, 
        field_capacity
    ).rename('Soil_Water_End_Of_Previous_Timestep')

    # Safety clamp
    Soil_Water_End_Of_Previous_Timestep_Scenario_2 = Soil_Water_End_Of_Previous_Timestep_Scenario_2.max(zero_image).rename('Soil_Water_End_Of_Previous_Timestep')
    Soil_Saturation_Percent_Scenario_2 = ee.Image(Soil_Water_End_Of_Previous_Timestep_Scenario_2.divide(Max_Soil_Moisture).multiply(100)).rename('Soil_Saturation_Percent_End_Of_Timestep')
    Soil_Water_Balance_Scenario_2 = ee.Image([Runoff_Scenario_2, Recharge_Scenario_2, Soil_Water_End_Of_Previous_Timestep_Scenario_2, Soil_Saturation_Percent_Scenario_2])

    ####################################################
    # Scenario 3: Elif Available_Water <= Field_Capacity
    # -------------------------------------------------
    Available_Water_for_Recharge_Scenario_3 = zero_image #not needed but defining for consistency
    Recharge_Scenario_3 = zero_image.rename('Recharge') # No recharge
    Runoff_Scenario_3 = zero_image.rename('Runoff') # No runoff
    Soil_Water_End_Of_Previous_Timestep_Scenario_3 = Available_Water.rename('Soil_Water_End_Of_Previous_Timestep')
    # Clamping soil moisture to zero as a safety check
    Soil_Water_End_Of_Previous_Timestep_Scenario_3 = zero_image.max(Soil_Water_End_Of_Previous_Timestep_Scenario_3).rename('Soil_Water_End_Of_Previous_Timestep')
    Soil_Saturation_Percent_Scenario_3 = ee.Image(Soil_Water_End_Of_Previous_Timestep_Scenario_3.divide(Max_Soil_Moisture).multiply(100)).rename('Soil_Saturation_Percent_End_Of_Timestep')
    Soil_Water_Balance_Scenario_3 = ee.Image([Runoff_Scenario_3, Recharge_Scenario_3, Soil_Water_End_Of_Previous_Timestep_Scenario_3, Soil_Saturation_Percent_Scenario_3])


    ### outlining conditions
    Scenario_1_Condition = Available_Water.gt(Max_Soil_Moisture)
    Scenario_2_Condition = Available_Water.gt(field_capacity)
    Scenario_3_Condition = Available_Water.lte(field_capacity) # not actually needed since it's the only remaining option, but defining for clarity and consistency

    ##########################################################################################
    ### The actual UBM calculation, performing if/else checks using nested .where() statements
    # ----------------------------------------------------------------------------------------
    
    Soil_Water_Balance = Soil_Water_Balance_Scenario_3.where(Scenario_2_Condition, 
                            Soil_Water_Balance_Scenario_2.where(Scenario_1_Condition,
                                Soil_Water_Balance_Scenario_1))
    
    current_image_date = ee.Date(current_image.get('system:time_start')).format('YYYY-MM-dd') # formatting the date of the output image
    current_output_image = Soil_Water_Balance.set('system:time_start', current_image.get('system:time_start'), 'Date_Filter', current_image_date) # setting the date of the output image

    return previous_state_list.add(current_output_image)

def ModifiedUBM1Run(model_ready_collection, resume_state_image=None, start_date=None, end_date=None):
    """
    Initializes the necessary data and runs the Modified UBM 1 model (ET as input instead of output) step function over the provided model-ready collection 
    (made using `build_model_ready_collection` from the helpers.py module).

    Args:
        model_ready_collection (GenericCollection): The model-ready GenericCollection containing time-series images with necessary bands.
        resume_state_image (ee.Image, optional): An ee.Image containing the last saved state of the model run, used for resuming an interrupted run or updating a collection. Must contain bands: 'Runoff', 'Recharge', 'Soil_Water_End_Of_Previous_Timestep', 'Soil_Saturation_Percent_End_Of_Timestep'. Defaults to None.
        start_date (str, optional): Start date for filtering the collection in 'YYYY-MM-DD' format. Defaults to None.
        end_date (str, optional): End date for filtering the collection in 'YYYY-MM-DD' format. Defaults to None.

    Returns:
        Image Collection (GenericCollection): A GenericCollection containing the UBM model output images.
    """
    #check if model_ready_collection is of type GenericCollection
    if not isinstance(model_ready_collection, GenericCollection):
        raise TypeError("model_ready_collection must be an instance of GenericCollection.")
    
    # handle case where user only specifies one of start_date or end_date
    if (start_date is None) != (end_date is None):
        raise ValueError("Both start_date and end_date must be provided together.")
    
    # Extract the ee.ImageCollection and optionally filter by date
    if start_date is not None and end_date is not None:
        model_ready_collection = model_ready_collection.collection.filterDate(start_date, end_date)
    else:
        model_ready_collection = model_ready_collection.collection

    if not isinstance(model_ready_collection, ee.ImageCollection):
        raise TypeError("Uh oh, there was an issue. The `model_ready_collection.collection` must be an instance of ee.ImageCollection.")

    # Retrieve input collection projection - currently not used but may be useful for future enhancements
    target_proj = model_ready_collection.first().projection()

    if resume_state_image is not None:
        # --- INCREMENTAL UPDATE INITIALIZATION ---
        # Select the specific bands required by the step function to prevent dimension mismatch
        initial_state_image = ee.Image(resume_state_image).select([
            'Runoff',
            'Recharge',
            'Soil_Water_End_Of_Previous_Timestep',
            'Soil_Saturation_Percent_End_Of_Timestep'
        ])
    else:
        # Define the field capacity image for initial state
        field_capacity_img = model_ready_collection.first().select('field_capacity')
        # Create a zero image on the target grid for initializing state variables
        zero_image_on_grid = model_ready_collection.first().select('soil_porosity').multiply(0)
        # Define the initial state image with required bands, reprojecting field capacity to target projection
        initial_state_image = ee.Image([
                                        zero_image_on_grid.rename('Runoff'),
                                        zero_image_on_grid.rename('Recharge'),
                                        field_capacity_img.rename('Soil_Water_End_Of_Previous_Timestep'),
                                        zero_image_on_grid.rename('Soil_Saturation_Percent_End_Of_Timestep')
                                    ]).set('system:time_start', 0)
    
    initial_state_list = ee.List([initial_state_image])
    # Run the Original UBM Step Function over the collection using iterate
    UBM_results_list = ee.List(model_ready_collection.iterate(Modified_1_UBM_Step_Function, initial_state_list)).slice(1) # Slice off the initial state image
    # Convert the results list to an ImageCollection
    UBM_results_collection = ee.ImageCollection(UBM_results_list)

    return GenericCollection(UBM_results_collection)