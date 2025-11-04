# In backend/app/api/routes/scan.py

from fastapi import APIRouter, Depends, Request, status, HTTPException
from sqlalchemy.orm import Session
import threading
from datetime import datetime
from app.limiter import limiter
from app.database import SessionLocal
from app.models import models
from app.schemas.scan import ScanRequest, ScanResponse
# No need to import orchestrator at the top level

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- THIS IS THE FINAL, CORRECTED FUNCTION SIGNATURE ---
@router.post("/start", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
def start_scan(
    request: Request,          # The limiter NEEDS this
    scan_request: ScanRequest, # FastAPI correctly maps the body to this
    db: Session = Depends(get_db)  # Dependencies come last
):
# --- END OF FIX ---
    """
    Endpoint to start a new manual scan.
    It creates the job record and then runs the scan in a background thread.
    """
    # Import locally to avoid circular dependencies
    from app.services import scan_orchestrator
    
    try:
        scan_job = models.ScanJob.create(
            db=db,
            user_id=scan_request.user_id,
            data_type=scan_request.data_type,
            search_data=scan_request.search_data,
            custom_regex=scan_request.custom_regex,
            status="pending",
            created_at=datetime.utcnow(),
            scan_source="manual"
        )
        if not scan_job:
            raise HTTPException(status_code=500, detail="Failed to create scan job in database.")

        scan_thread = threading.Thread(
            target=scan_orchestrator.start_scan_job,
            args=(scan_request, "manual", scan_job.id)
        )
        scan_thread.start()

        return ScanResponse(scan_id=scan_job.id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate scan job: {e}")