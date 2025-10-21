from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from app.database import SessionLocal
from app.models.models import ScanJob, ScanResult
from app.schemas.history import ScanHistoryItem  # <-- IMPORT THE SCHEMA YOU CREATED
from typing import List

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# This decorator now enforces that the output matches your schema
@router.get("/scan-history", response_model=List[ScanHistoryItem])
def get_scan_history(db: Session = Depends(get_db)):
    # This query efficiently fetches jobs and their related results in one go
    jobs = db.query(ScanJob).options(
        joinedload(ScanJob.results)
    ).order_by(ScanJob.created_at.desc()).limit(20).all()
    
    history = []
    for job in jobs:
        job_data = {
            "scan_id": job.id,
            "scan_source": job.scan_source,  # <--- THIS IS THE MISSING LINE
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
                } for result in job.results # Using job.results is more efficient
            }
        }
        history.append(job_data)

    return history