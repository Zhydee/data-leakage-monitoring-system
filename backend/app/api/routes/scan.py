from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks # Add BackgroundTasks
from app.schemas.scan import ScanRequest, ScanResponse
from app.services import scan_orchestrator # Import the orchestrator directly
from app.database import SessionLocal
from datetime import datetime

router = APIRouter()

@router.post("/start", status_code=202)
def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """
    Accepts a scan request, creates a job record to get an ID,
    returns the ID immediately, and runs the full scan in the background.
    """
    # Step 1: Create the ScanJob in the database synchronously to get an ID.
    try:
        db = SessionLocal()
        scan_job = scan_orchestrator.models.ScanJob.create(
            user_id=request.user_id,
            data_type=request.data_type,
            search_data=request.search_data,
            custom_regex=request.custom_regex,
            status="pending", # Start as pending
            created_at=datetime.utcnow(),
            scan_source="manual"
        )
        if not scan_job:
            raise HTTPException(status_code=500, detail="Failed to create scan job in database.")

        scan_id = scan_job.id
    finally:
        db.close()

    # Step 2: Add the long-running task to the background.
    background_tasks.add_task(scan_orchestrator.start_scan_job, request, "manual", scan_id)

    # Step 3: Return the ID to the user immediately.
    return {"scan_id": scan_id, "message": "Scan initiated. Results will be available shortly."}