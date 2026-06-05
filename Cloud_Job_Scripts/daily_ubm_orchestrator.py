import ee 
import os
import google.auth
from datetime import date, timedelta
import calendar

import ubm_updater_script
import snowmelt_and_precip_asset_updater
import irrigation_forward_fill 

def initialize_gee():
    """Initializes Earth Engine for either Cloud Run or Local environments."""
    if os.environ.get('CLOUD_RUN_JOB'):
        print("Orchestrator: Cloud Run environment detected.")
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/earthengine', 
                    'https://www.googleapis.com/auth/cloud-platform']
        )
        ee.Initialize(credentials, project='ut-gee-ugs-bsf-dev')
    else:
        print("Orchestrator: Local environment detected.")
        service_account = 'localpythonscripts@ut-gee-ugs-bsf-dev.iam.gserviceaccount.com'
        credentials = ee.ServiceAccountCredentials(service_account, 'C:\\Users\\mradwin\\ut-gee-ugs-bsf-dev-53dcc5d729e0.json')
        ee.Initialize(credentials=credentials)

def check_provider_ready(collection_id, check_date_str, next_day_str):
    """
    Performs a lightning-fast shallow ping to the GEE catalog to see if data exists.
    """
    try:
        count = ee.ImageCollection(collection_id).filterDate(check_date_str, next_day_str).size().getInfo()
        return count > 0
    except Exception:
        return False

def print_summary(summary_log):
    """Helper function to print the final recap block."""
    print("\n" + "="*60)
    print("ORCHESTRATOR RUN SUMMARY RECAP")
    print("="*60)
    for line in summary_log:
        print(line)
    print("="*60 + "\n")

def main():
    """
    Orchestrator for daily UBM updates. On the 28th of each month, it triggers a 6-month backfill. On all other days, it checks for new data from key providers and triggers updates accordingly.
    This schedule accounts for typical data release and update patterns, where a 6-month rolling rewind updates model results to use updated/improved input data, and the daily sensor mode ensures the model stays current with the latest available data.
    """
    initialize_gee()
    today = date.today()
    summary_log = [] # Initialize our recap tracker
    
    # Target dates for the month that just finished
    first_of_this_month = today.replace(day=1)
    last_day_prev_month = first_of_this_month - timedelta(days=1)
    target_start_str = last_day_prev_month.replace(day=1).strftime('%Y-%m-%d')
    target_end_str = last_day_prev_month.strftime('%Y-%m-%d')

    # Exclusive next-day strings for GEE filtering
    next_day_obj = last_day_prev_month + timedelta(days=1)
    target_end_next_day_str = next_day_obj.strftime('%Y-%m-%d')
    
    target_start_next_day_obj = last_day_prev_month.replace(day=1) + timedelta(days=1)
    target_start_next_day_str = target_start_next_day_obj.strftime('%Y-%m-%d')

    # --------------------------------------------------------- #
    # BRANCH 1: THE 6-MONTH ROLLING REWIND (Runs only on the 28th)
    # --------------------------------------------------------- #
    if today.day >= 28:
        print(f"\n{'='*60}")
        print("ORCHESTRATOR BRANCH 1: 6-MONTH ROLLING REWIND INITIATED")
        print(f"{'='*60}")
        
        new_month = today.month - 6
        new_year = today.year
        if new_month <= 0:
            new_month += 12
            new_year -= 1
        rewind_start_str = date(new_year, new_month, 1).strftime('%Y-%m-%d')

        print(f"Rewind Window: {rewind_start_str} to {target_end_str}")
        summary_log.append(f"🔹 MODE: 6-Month Rolling Rewind ({rewind_start_str} to {target_end_str})")

        # Bypass sensors and forcefully trigger the child scripts with override dates
        irrigation_forward_fill.main()
        snowmelt_and_precip_asset_updater.main(override_start_date=rewind_start_str, override_end_date=target_end_str)
        ubm_updater_script.main(start_date=rewind_start_str, end_date=target_end_str)

        print("✅ 6-Month Rewind Tasks Queued Successfully.")
        summary_log.append("🔹 ACTION: Successfully queued historical backfill for Precip, Irrigation, and UBM.")

    # --------------------------------------------------------- #
    # BRANCH 2: THE DAILY SENSOR MODE (Runs all other days)
    # --------------------------------------------------------- #
    else:
        print(f"\n{'='*60}")
        print("ORCHESTRATOR BRANCH 2: DAILY SENSOR MODE INITIATED")
        print(f"{'='*60}")
        print(f"Targeting: {target_start_str} to {target_end_str}")
        summary_log.append(f"🔹 MODE: Daily Sensor (Targeting {target_start_str} to {target_end_str})")

        # --- SENSOR 1: PRECIPITATION & SNOWMELT ---
        print("\n" + "-"*40)
        print("[Sensor Check] Verifying external Precipitation providers...")
        print("-"*40)
        
        prism_ready = check_provider_ready("OREGONSTATE/PRISM/ANd", target_end_str, target_end_next_day_str)
        prism800_ready = check_provider_ready("projects/sat-io/open-datasets/OREGONSTATE/PRISM_800_DAILY", target_end_str, target_end_next_day_str)
        gridmet_ready = check_provider_ready("IDAHO_EPSCOR/GRIDMET", target_end_str, target_end_next_day_str)
        daymet_ready = check_provider_ready("NASA/ORNL/DAYMET_V4", target_end_str, target_end_next_day_str)

        print(f" -> PRISM (5km):      {'🟢 READY' if prism_ready else '🟡 WAITING'}")
        print(f" -> PRISM (800m):     {'🟢 READY' if prism800_ready else '🟡 WAITING'}")
        print(f" -> GRIDMET:          {'🟢 READY' if gridmet_ready else '🟡 WAITING'}")
        print(f" -> DAYMET:           {'🟢 READY' if daymet_ready else '🟡 WAITING'}")
        print("-"*40)

        # Log precip statuses to the summary block
        summary_log.append(f"🔹 SENSORS: PRISM={'READY' if prism_ready else 'WAITING'}, GRIDMET={'READY' if gridmet_ready else 'WAITING'}, DAYMET={'READY' if daymet_ready else 'WAITING'}")

        if not prism_ready:
            print(f" -> 🛑 Primary trigger (PRISM) for {target_end_str} not yet published. Shutting down until tomorrow.")
            summary_log.append("🔹 ACTION: Halted pipeline. Waiting for PRISM data to trigger updaters.")
            print_summary(summary_log)
            return 

        print(" -> ✅ Primary trigger met. Firing Precipitation & Irrigation Updaters.")
        summary_log.append("🔹 ACTION: Triggered Precipitation & Irrigation updaters.")
        
        # Call main() empty so the script uses its native gap-check
        snowmelt_and_precip_asset_updater.main()
        irrigation_forward_fill.main()

        # --- SENSOR 2: OPENET ---
        print("\n" + "-"*40)
        print("[Sensor Check] Verifying external OpenET providers...")
        print("-"*40)
        
        openet_ready = check_provider_ready("projects/openet/assets/disalexi/conus/gridmet/monthly/v2_1", target_start_str, target_start_next_day_str)
        print(f" -> OpenET (v2_1):    {'🟢 READY' if openet_ready else '🟡 WAITING'}")
        print("-"*40)
        
        summary_log.append(f"🔹 SENSORS: OpenET={'READY' if openet_ready else 'WAITING'}")

        if not openet_ready:
            print(f" -> 🛑 OpenET data for {target_start_str} not yet published. Shutting down until tomorrow.")
            summary_log.append("🔹 ACTION: Halted UBM pipeline. Waiting for OpenET data.")
            print_summary(summary_log)
            return

        print(" -> ✅ OpenET data published. Running UBM Updater.")
        summary_log.append("🔹 ACTION: Triggered Main UBM updater.")
        
        ubm_updater_script.main()

    # Final summary print if the script ran to full completion
    print_summary(summary_log)

if __name__ == "__main__":
    main()