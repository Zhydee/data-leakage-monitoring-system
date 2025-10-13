# --- File: app/api/routes/scan.py ---

from fastapi import APIRouter, HTTPException, Request  
from app.schemas.scan import ScanRequest
from app.services.scan_orchestrator import start_scan_job 
from app.limiter import limiter  # --- Import the shared limiter ---

router = APIRouter()


@router.post("/start")
@limiter.limit("10/minute")
async def start_scan(scan_request: ScanRequest, request: Request): 
    """
    Starts a new scan job. This endpoint is rate-limited to 10 requests per minute per IP.
    """
    scan_id = await start_scan_job(scan_request) # Pass the Pydantic model directly
    if not scan_id:
        raise HTTPException(status_code=500, detail="Scan could not be initiated.")
    return {"job_id": scan_id}


