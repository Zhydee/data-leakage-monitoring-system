# In backend/app/utils/scheduler_jobs.py
import logging
import json
import hashlib
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import models
from app.schemas.scan import ScanRequest
from app.services.scan_orchestrator import start_scan_job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_scan_and_update_asset(asset_id: int, scan_request: ScanRequest):
    """
    Runs an immediate scan for a newly created asset and handles hashing and alerting.
    """
    logger.info(f"BACKGROUND_TASK: Starting immediate scan for asset ID {asset_id}...")
    
    db = SessionLocal()
    scan_id = None
    try:
        # Step 1: Create the ScanJob record.
        scan_job = models.ScanJob.create(
            db=db,
            user_id=scan_request.user_id,
            data_type=scan_request.data_type,
            search_data=scan_request.search_data,
            status="pending",
            created_at=datetime.utcnow(),
            scan_source="automated",
            custom_regex=None
        )
        if not scan_job:
            raise Exception("Failed to create ScanJob in database.")
        
        scan_id = scan_job.id
        logger.info(f"BACKGROUND_TASK: Created pending Job ID {scan_id} for immediate scan.")

        # Step 2: Run the scan.
        start_scan_job(scan_request, scan_source="automated", scan_id=scan_id)
        
        # --- START OF NEW LOGIC ---
        # Step 3: Calculate the hash of the new results.
        new_hash = get_results_hash(db, scan_id)
        asset = db.query(models.MonitoredAsset).filter(models.MonitoredAsset.id == asset_id).first()

        if not asset:
            logger.warning(f"BACKGROUND_TASK: Could not find asset ID {asset_id} to update.")
            return

        logger.info(f"BACKGROUND_TASK: Asset {asset_id} - Previous Hash: {asset.previous_results_hash}, New Hash: {new_hash}")

        # Step 4: Compare hashes and create an alert if they differ.
        if new_hash != asset.previous_results_hash:
            logger.warning(f"BACKGROUND_TASK: New findings detected for asset {asset_id} on its first scan!")
            models.Alert.create(
                db=db,
                asset_id=asset.id,
                user_id=asset.user_id,
                scan_id=scan_id,
                message=f"New potential leaks found for '{asset.search_data}'."
            )
            asset.previous_results_hash = new_hash
        # --- END OF NEW LOGIC ---

        # Step 5: Update the timestamp.
        asset.last_scanned_at = datetime.utcnow()
        db.commit()
        logger.info(f"BACKGROUND_TASK: Successfully processed immediate scan and updated asset ID {asset_id}.")

    except Exception as e:
        logger.error(f"BACKGROUND_TASK: An error occurred during immediate scan for asset {asset_id}. Error: {e}", exc_info=True)
        if db:
            db.rollback()
    finally:
        if db:
            db.close()

# --- The rest of the file remains the same ---
def get_results_hash(db: Session, scan_id: int) -> str:
    """
    Fetches all results for a given scan_id, creates a consistent JSON string,
    and returns its SHA256 hash. This is the final, most robust version.
    """
    results = db.query(models.ScanResult).filter(models.ScanResult.job_id == scan_id).order_by(models.ScanResult.id).all()
    if not results:
        return hashlib.sha256("".encode()).hexdigest()

    # We will build a list of canonical strings for each result set to sort them reliably
    all_results_canonical_strings = []

    for r in results:
        result_data_string = ""
        # --- THIS IS THE BULLETPROOF FIX ---
        # If the result data is a list, we will convert it to a sorted list of strings
        if isinstance(r.result_data, list):
            if not r.result_data:
                # Handle empty list case
                result_data_string = "[]"
            else:
                # Convert each item in the list to a canonical JSON string
                # This handles both simple strings (Sherlock) and complex dicts (TruffleHog)
                string_list = [json.dumps(item, sort_keys=True) for item in r.result_data]
                # Sort the list of strings
                string_list.sort()
                # Join them into a single string representation of the sorted list
                result_data_string = f"[{','.join(string_list)}]"
        else:
            # For any other data type (like a single dict), just create a canonical string
            result_data_string = json.dumps(r.result_data, sort_keys=True)
        # --- END OF FIX ---
        
        # Create a string for the entire result record, ensuring it's always the same
        canonical_record_string = json.dumps({
            "tool_name": r.tool_name,
            "result_type": r.result_type,
            "data": result_data_string, # Use our canonical string
            "severity": r.severity,
        }, sort_keys=True)
        
        all_results_canonical_strings.append(canonical_record_string)

    # Sort the list of all result strings to handle cases where tools finish in a different order
    all_results_canonical_strings.sort()

    # Join the final list into one giant string to be hashed
    final_string_to_hash = "".join(all_results_canonical_strings)
    
    return hashlib.sha256(final_string_to_hash.encode()).hexdigest()

def run_automated_scans():
    logger.info("SCHEDULER: Starting automated scanning job...")
    db_loop_session = SessionLocal()
    try:
        assets_to_scan = db_loop_session.query(models.MonitoredAsset).all()
        if not assets_to_scan:
            logger.info("SCHEDULER: No assets configured for monitoring. Job finished.")
            return

        logger.info(f"SCHEDULER: Found {len(assets_to_scan)} asset(s) to scan.")

        for asset in assets_to_scan:
            logger.info(f"SCHEDULER: Processing asset ID {asset.id} ('{asset.search_data}') for user {asset.user_id}")
            
            try:
                scan_job = models.ScanJob.create(
                    db=db_loop_session,
                    user_id=asset.user_id,
                    data_type=asset.data_type,
                    search_data=asset.search_data,
                    status="pending",
                    created_at=datetime.utcnow(),
                    scan_source="automated",
                    custom_regex=None
                )
                if not scan_job:
                    raise Exception("Failed to create ScanJob in database.")
                
                scan_id = scan_job.id
                logger.info(f"SCHEDULER: Created pending Job ID {scan_id} for asset {asset.id}.")

            except Exception as e:
                logger.error(f"SCHEDULER: Failed to create job for asset {asset.id}. Error: {e}")
                continue

            scan_request = ScanRequest(
                data_type=asset.data_type,
                search_data=asset.search_data,
                user_id=asset.user_id
            )
            
            try:
                start_scan_job(scan_request, scan_source="automated", scan_id=scan_id)
                
                logger.info(f"SCHEDULER: Scan completed for asset {asset.id}. Job ID: {scan_id}")

                db_hash_session = SessionLocal()
                try:
                    new_hash = get_results_hash(db_hash_session, scan_id)
                finally:
                    db_hash_session.close()

                logger.info(f"SCHEDULER: Asset {asset.id} - Previous Hash: {asset.previous_results_hash}, New Hash: {new_hash}")

                if new_hash != asset.previous_results_hash:
                    logger.warning(f"SCHEDULER: New findings detected for asset {asset.id}!")
                    models.Alert.create(
                        db=db_loop_session,
                        asset_id=asset.id,
                        user_id=asset.user_id,
                        scan_id=scan_id,
                        message=f"New potential leaks found for '{asset.search_data}'."
                    )
                    asset_to_update = db_loop_session.query(models.MonitoredAsset).filter(models.MonitoredAsset.id == asset.id).first()
                    asset_to_update.previous_results_hash = new_hash
                else:
                    logger.info(f"SCHEDULER: No new findings for asset {asset.id}.")

                asset_to_update = db_loop_session.query(models.MonitoredAsset).filter(models.MonitoredAsset.id == asset.id).first()
                asset_to_update.last_scanned_at = datetime.utcnow()
                db_loop_session.commit()
                logger.info(f"SCHEDULER: Successfully updated timestamp for asset {asset.id}.")

            except Exception as e:
                logger.exception(f"SCHEDULER: An error occurred while processing asset {asset.id}: {e}")
                db_loop_session.rollback()

    finally:
        db_loop_session.close()