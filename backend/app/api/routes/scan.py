from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
import threading
from datetime import datetime

# --- THIS IS THE FIX ---
# Instead of importing 'get_db', we import 'SessionLocal' and create our own 'get_db' function,
# just like your other route files (e.g., monitoring.py) do.
from app.database import SessionLocal
# --- END OF FIX ---

from app.models import models
from app.schemas.scan import ScanRequest, ScanResponse
from app.services import scan_orchestrator

router = APIRouter()

# --- THIS IS THE SECOND PART OF THE FIX ---
# This local 'get_db' function is the standard FastAPI pattern.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# --- END OF FIX ---

@router.post("/start", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
def start_scan(
    request: ScanRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint to start a new manual scan.
    It creates the job record and then runs the scan in a background thread.
    """
    try:
        # Create the ScanJob record in the database first.
        scan_job = models.ScanJob.create(
            db=db,
            user_id=request.user_id,
            data_type=request.data_type,
            search_data=request.search_data,
            custom_regex=request.custom_regex,
            status="pending",
            created_at=datetime.utcnow(),
            scan_source="manual"
        )
        if not scan_job:
            raise HTTPException(status_code=500, detail="Failed to create scan job in database.")

        # Start the long-running scan in a separate background thread.
        scan_thread = threading.Thread(
            target=scan_orchestrator.start_scan_job,
            args=(request, "manual", scan_job.id)
        )
        scan_thread.start()

        # Immediately return the scan_id to the frontend.
        return ScanResponse(scan_id=scan_job.id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate scan job: {e}")