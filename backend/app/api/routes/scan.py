from fastapi import APIRouter, HTTPException
from app.schemas.scan import ScanRequest, ScanResponse
from app.services.scan_orchestrator import start_scan_job

router = APIRouter()

@router.post("/scan/start", response_model=ScanResponse)
async def start_scan(request: ScanRequest):
    scan_id = await start_scan_job(request)
    if not scan_id:
        raise HTTPException(status_code=500, detail="Scan could not be initiated.")
    return ScanResponse(scan_id=scan_id)
