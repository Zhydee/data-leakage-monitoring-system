import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import models
from app.database import SessionLocal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION: Set how long to keep scan records ---
RETENTION_DAYS = 14

def delete_old_scan_records():
    """
    Connects to the database and deletes scan jobs and their related
    results/statuses that are older than the defined RETENTION_DAYS.
    """
    logger.info("Starting scheduled cleanup of old scan records...")
    db: Session = SessionLocal()
    
    try:
        # 1. Calculate the cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
        logger.info(f"Deleting records older than: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        # 2. Find all old ScanJob entries to be deleted
        # This is crucial because cascading deletes will handle the related records.
        jobs_to_delete = db.query(models.ScanJob).filter(
            models.ScanJob.created_at < cutoff_date
        ).all()

        if not jobs_to_delete:
            logger.info("No old scan records found to delete.")
            return

        num_jobs = len(jobs_to_delete)
        logger.info(f"Found {num_jobs} old scan job(s) to delete.")

        # 3. Delete them
        for job in jobs_to_delete:
            db.delete(job)
        
        # 4. Commit the transaction to the database
        db.commit()
        logger.info(f"Successfully deleted {num_jobs} old scan job(s) and their related data.")

    except Exception as e:
        logger.error(f"Error during scheduled cleanup: {e}")
        db.rollback() # Roll back in case of an error to maintain data integrity
    finally:
        db.close()
        logger.info("Cleanup task finished.")