# In app/utils/scheduler_jobs.py
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
    Runs a scan for a specific asset and updates its timestamp upon completion.
    This is designed to be called by a background task.
    """
    logger.info(f"BACKGROUND_TASK: Starting immediate scan for asset ID {asset_id}...")
    
    # Run the scan job; it returns the new scan_id
    scan_id = start_scan_job(scan_request, scan_source="automated")

    if not scan_id:
        logger.error(f"BACKGROUND_TASK: Scan failed to start for asset {asset_id}. Timestamp not updated.")
        return

    # After the scan completes, create a new session to update the asset
    db = SessionLocal()
    try:
        asset = db.query(models.MonitoredAsset).filter(models.MonitoredAsset.id == asset_id).first()
        if asset:
            asset.last_scanned_at = datetime.utcnow()
            db.commit()
            logger.info(f"BACKGROUND_TASK: Successfully updated timestamp for asset ID {asset_id}.")
        else:
            logger.warning(f"BACKGROUND_TASK: Could not find asset ID {asset_id} to update timestamp.")
    finally:
        db.close()
        
def get_results_hash(db: Session, scan_id: int) -> str:
    """
    Fetches all results for a given scan_id, creates a consistent JSON string,
    and returns its SHA256 hash.
    """
    results = db.query(models.ScanResult).filter(models.ScanResult.job_id == scan_id).order_by(models.ScanResult.id).all()
    if not results:
        return hashlib.sha256("".encode()).hexdigest()

    results_list = []
    for r in results:
        # --- START OF THE FIX ---
        # Create a copy of the data to avoid modifying the original
        data_to_hash = r.result_data
        
        # If the data is a list (like Sherlock's URLs), sort it to ensure a consistent order
        if isinstance(data_to_hash, list):
            # We must handle lists of dictionaries and lists of strings differently
            try:
                # This works for simple lists of strings, numbers, etc.
                data_to_hash.sort()
            except TypeError:
                # This handles lists of dictionaries by turning them into a sorted string representation
                data_to_hash = sorted([json.dumps(item, sort_keys=True) for item in data_to_hash])
        # --- END OF THE FIX ---

        results_list.append({
            "tool_name": r.tool_name,
            "result_type": r.result_type,
            "result_data": data_to_hash,
            "severity": r.severity,
        })
    
    canonical_json = json.dumps(results_list, sort_keys=True)
    return hashlib.sha256(canonical_json.encode()).hexdigest()


def run_automated_scans():
    """
    Fetches monitored assets, creates a "pending" job record for each,
    and then runs the scan, updating the record. This now follows the
    same two-step process as manual scans.
    """
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
            
            # --- THIS IS THE CRITICAL FIX ---
            # Step 1: Create the ScanJob record first to get a real scan_id.
            try:
                scan_job = models.ScanJob.create(
                    user_id=asset.user_id,
                    data_type=asset.data_type,
                    search_data=asset.search_data,
                    status="pending", # Start as pending
                    created_at=datetime.utcnow(),
                    scan_source="automated",
                    custom_regex=None # Automated scans don't have custom regex
                )
                if not scan_job:
                    raise Exception("Failed to create ScanJob in database.")
                
                scan_id = scan_job.id
                logger.info(f"SCHEDULER: Created pending Job ID {scan_id} for asset {asset.id}.")

            except Exception as e:
                logger.error(f"SCHEDULER: Failed to create job for asset {asset.id}. Error: {e}")
                continue # Skip to the next asset

            # The ScanRequest object is still needed to pass data to the orchestrator.
            scan_request = ScanRequest(
                data_type=asset.data_type,
                search_data=asset.search_data,
                user_id=asset.user_id
            )
            # --- END OF FIX ---
            
            try:
                # Step 2: Now call start_scan_job with the new scan_id.
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
                        asset_id=asset.id,
                        user_id=asset.user_id,
                        scan_id=scan_id,
                        message=f"New potential leaks found for '{asset.search_data}'."
                    )
                    # Use the db_loop_session to update the asset
                    asset_to_update = db_loop_session.query(models.MonitoredAsset).filter(models.MonitoredAsset.id == asset.id).first()
                    asset_to_update.previous_results_hash = new_hash
                else:
                    logger.info(f"SCHEDULER: No new findings for asset {asset.id}.")

                # Use the db_loop_session to update the asset
                asset_to_update = db_loop_session.query(models.MonitoredAsset).filter(models.MonitoredAsset.id == asset.id).first()
                asset_to_update.last_scanned_at = datetime.utcnow()
                db_loop_session.commit()
                logger.info(f"SCHEDULER: Successfully updated timestamp for asset {asset.id}.")

            except Exception as e:
                logger.exception(f"SCHEDULER: An error occurred while processing asset {asset.id}: {e}")
                db_loop_session.rollback()

    finally:
        db_loop_session.close()