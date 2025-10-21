from fastapi import APIRouter, HTTPException, Request  
from app.schemas.scan import ScanRequest
from app.services.scan_orchestrator import start_scan_job 
from app.limiter import limiter

router = APIRouter()

@router.post("/start")
@limiter.limit("10/minute")
async def start_scan(scan_request: ScanRequest, request: Request): 
    """
    Starts a new scan job. This endpoint is rate-limited.
    """
    scan_id = await start_scan_job(scan_request, scan_source="manual")
    
    if not scan_id:
        raise HTTPException(status_code=500, detail="Scan could not be initiated.")
    return {"job_id": scan_id}