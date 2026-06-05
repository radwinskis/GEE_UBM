import ee
import os
import google.auth
from datetime import date, datetime, timedelta, timezone


def get_target_date():
    """Calculates the first day of the previous month (the target update boundary)."""
    today = date.today()
    # Subtract 1 day from the 1st of the current month to get into the previous month
    prev_month_end = today.replace(day=1) - timedelta(days=1)
    # Return the 1st day of that previous month
    return date(prev_month_end.year, prev_month_end.month, 1)

def add_one_month(current_date):
    """Safely increments a Python date object by exactly one month."""
    new_month = current_date.month % 12 + 1
    new_year = current_date.year + (current_date.month // 12)
    return date(new_year, new_month, 1)

def main():
    # Check if we are running inside Google Cloud Run
    if os.environ.get('CLOUD_RUN_JOB'):
        print("Detected Cloud Run environment. Using default credentials.")
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/earthengine', 
                    'https://www.googleapis.com/auth/cloud-platform']
        )
        ee.Initialize(credentials, project='ut-gee-ugs-bsf-dev')
    else:
        print("Detected local environment. Using JSON service account key.")
        service_account = 'localpythonscripts@ut-gee-ugs-bsf-dev.iam.gserviceaccount.com'
        credentials = ee.ServiceAccountCredentials(service_account, 'C:\\Users\\mradwin\\ut-gee-ugs-bsf-dev-53dcc5d729e0.json')
        ee.Initialize(credentials=credentials)
    
    
    collection_path = "projects/ut-gee-ugs-bsf-dev/assets/UT_Monthly_Scaled_Irrigation_Depth_Collection_mm_30m_v2"
    irrigation_col = ee.ImageCollection(collection_path)
    boundary = ee.FeatureCollection("projects/ut-gee-ugs-bsf-dev/assets/Utah_Regional_Boundary").geometry()
    
    target_date = get_target_date()
    
    # 1. Dynamically find the latest image currently in the collection
    try:
        latest_image = irrigation_col.sort('system:time_start', False).first()
        latest_millis = latest_image.get('system:time_start').getInfo()
        latest_dt = datetime.fromtimestamp(latest_millis / 1000.0, tz=timezone.utc)
        latest_date = date(latest_dt.year, latest_dt.month, 1)
    except Exception as e:
        print(f"Error fetching latest image. Ensure the collection exists and is not empty. Details: {e}")
        return

    print(f"Latest available irrigation data is from: {latest_date.strftime('%Y-%m')}")
    print(f"Target forward-fill date is up through: {target_date.strftime('%Y-%m')}")
    
    # 2. Check if we actually need to do any work
    if latest_date >= target_date:
        print("Irrigation collection is already up to date! Exiting gracefully.")
        return

    # 3. Loop through all missing months and submit catch-up exports
    current_fill_date = add_one_month(latest_date)
    
    while current_fill_date <= target_date:
        fill_year = current_fill_date.year
        fill_month = current_fill_date.month
        
        # Find the most recent available year that has data for THIS SPECIFIC MONTH
        # (Since irrigation patterns differ by month, we must copy a matching month)
        source_image = irrigation_col.filter(
            ee.Filter.eq('month', fill_month)
        ).filter(
            ee.Filter.lt('year', fill_year) # Only look backward in time
        ).sort('year', False).first()
        
        source_year = source_image.get('year').getInfo()
        
        # Construct timestamps and strings
        new_date_str = f"{fill_year}-{fill_month:02d}-01"
        new_timestamp = ee.Date(new_date_str).millis()
        asset_id = f"{collection_path}/irrigation_{fill_year}{fill_month:02d}01"
        
        # Update image properties
        forward_filled_image = source_image.set({
            'system:time_start': new_timestamp,
            'year': fill_year,
            'month': fill_month,
            'Date_Filter': new_date_str,
            'is_provisional_copy': True, # Flag so you know it was auto-copied
            'copied_from_year': source_year
        })
        
        print(f"Queueing export for {new_date_str} (Copied from {source_year}-{fill_month:02d})...")
        
        # Delete check to prevent errors if a previous export partially failed
        try:
            ee.data.deleteAsset(asset_id)
            print(f" -> Deleted existing/corrupted asset at {asset_id}")
        except ee.EEException:
            pass # Asset does not exist, which is what we expect
            
        # Trigger the export
        task = ee.batch.Export.image.toAsset(
            image=forward_filled_image,
            description=f"forward_fill_irrigation_{fill_year}{fill_month:02d}",
            assetId=asset_id,
            region=boundary,
            scale=30,
            maxPixels=1e13
        )
        task.start()
        
        # Advance the loop by one month
        current_fill_date = add_one_month(current_fill_date)
        
    print("All required forward-fill tasks have been successfully submitted to GEE.")

if __name__ == "__main__":
    main()