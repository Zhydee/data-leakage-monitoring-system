from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.models import ScanJob, ScanResult

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/scan-history")
def get_scan_history(db: Session = Depends(get_db)):
    jobs = db.query(ScanJob).order_by(ScanJob.created_at.desc()).limit(10).all()
    history = []

    for job in jobs:
        results = db.query(ScanResult).filter_by(scan_job_id=job.id).all()
        job_data = {
            "scan_id": job.id,
            "data_type": job.data_type,
            "search_data": job.search_data,
            "timestamp": job.created_at.isoformat(),
            "status": job.status,
            "results": {
                result.tool_name: {
                    "type": result.result_type,
                    "data": result.result_data,
                    "confidence": result.confidence_score,
                    "severity": result.severity,
                    "source": result.source_url
                } for result in results
            }
        }
        history.append(job_data)

    return history
