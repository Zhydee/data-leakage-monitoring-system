from fastapi import APIRouter, HTTPException
from app.schemas.scan import ScanRequest
from app.services.scan_orchestrator import start_scan_job

router = APIRouter()

@router.post("/start")
async def start_scan(request: ScanRequest):
    scan_id = await start_scan_job(request)
    if not scan_id:
        raise HTTPException(status_code=500, detail="Scan could not be initiated.")
    return {"job_id": scan_id}



