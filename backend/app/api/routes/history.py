from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from app.database import SessionLocal
from app.models.models import ScanJob, ScanResult
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.history import ScanHistoryItem  
from typing import List
from app.cache import cache 

router = APIRouter()
CACHE_KEY_SCAN_HISTORY = "scan_history"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# This decorator now enforces that the output matches the schema
@router.get("/scan-history/{user_id}", response_model=List[ScanHistoryItem])
def get_user_scan_history(user_id: str, db: Session = Depends(get_db)):
    """
    Fetches the scan history for a specific user, identified by their user_id.
    """

    jobs = db.query(ScanJob).options(
        joinedload(ScanJob.results)
    ).where(ScanJob.user_id == user_id).order_by(ScanJob.created_at.desc()).limit(20).all()
    
    # The logic for processing the jobs into a response remains the same.
    history = []
    for job in jobs:
        job_data = {
            "scan_id": job.id,
            "scan_source": job.scan_source,
            "data_type": job.data_type,
            "search_data": job.search_data,
            "timestamp": job.created_at,
            "status": job.status,
            "results": {
                result.tool_name: {
                    "type": result.result_type,
                    "data": result.result_data,
                    "confidence": result.confidence_score,
                    "severity": result.severity,
                    "source": result.source_url
                } for result in job.results
            }
        }
        history.append(job_data)
    
    return history

@router.get("/scan/{scan_id}", response_model=ScanHistoryItem)
def get_single_scan(scan_id: int, db: Session = Depends(get_db)):
    """
    Public endpoint to fetch a single scan result by its ID.
    Used for guests to see their most recent scan.
    """
    job = db.query(ScanJob).options(
        joinedload(ScanJob.results)
    ).filter(ScanJob.id == scan_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Reuse the same logic as the history endpoint to format the result
    job_data = {
        "scan_id": job.id,
        "scan_source": job.scan_source,
        "data_type": job.data_type,
        "search_data": job.search_data,
        "timestamp": job.created_at,
        "status": job.status,
        "results": {
            result.tool_name: {
                "type": result.result_type,
                "data": result.result_data,
                "confidence": result.confidence_score,
                "severity": result.severity,
                "source": result.source_url
            } for result in job.results
        }
    }
    return job_data