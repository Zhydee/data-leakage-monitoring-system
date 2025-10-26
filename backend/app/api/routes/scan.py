from app.schemas.scan import ScanRequest
from app.services.scan_orchestrator import start_scan_job 
from app.limiter import limiter
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, status 

router = APIRouter()

@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def start_scan(scan_request: ScanRequest, request: Request, background_tasks: BackgroundTasks): 
    """
    Accepts a scan request and initiates it in the background. 
    This endpoint is rate-limited and returns immediately.
    """
    background_tasks.add_task(start_scan_job, scan_request, scan_source="manual")
    return {"message": "Scan initiated. Results will appear in Scan History shortly."}