from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import models
from pydantic import BaseModel, ConfigDict
from typing import List
from datetime import datetime
import threading # <-- Import the threading library

from app.schemas.scan import ScanRequest
# We now need the main scanning function here
from app.services.scan_orchestrator import start_scan_job

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class AssetCreate(BaseModel):
    user_id: str
    data_type: str
    search_data: str

class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: str
    data_type: str
    search_data: str
    last_scanned_at: datetime | None

class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scan_id: int
    message: str
    is_read: bool
    created_at: datetime

# --- THIS IS THE FINAL, CORRECTED FUNCTION ---
@router.post("/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def add_monitored_asset(
    asset: AssetCreate,
    db: Session = Depends(get_db)
):
    # Step 1: Create the asset in the database (this is fast).
    db_asset = models.MonitoredAsset.create(
        db=db,
        user_id=asset.user_id,
        data_type=asset.data_type,
        search_data=asset.search_data
    )
    if not db_asset:
        raise HTTPException(status_code=400, detail="Could not create asset")

    # Step 2: Create the ScanJob record to get a scan_id (this is fast).
    scan_job = models.ScanJob.create(
        db=db,
        user_id=asset.user_id,
        data_type=asset.data_type,
        search_data=asset.search_data,
        status="pending",
        created_at=datetime.utcnow(),
        scan_source="automated",
        custom_regex=None
    )
    if not scan_job:
        raise HTTPException(status_code=500, detail="Failed to create scan job in database for monitoring.")
    
    # Step 3: Prepare the data for the background scan.
    scan_request = ScanRequest(
        data_type=asset.data_type,
        search_data=asset.search_data,
        user_id=asset.user_id
    )

    # Step 4: Start the long-running scan in a completely separate background thread.
    # The 'target' is the function to run, and 'args' are its arguments.
    scan_thread = threading.Thread(
        target=start_scan_job,
        args=(scan_request, "automated", scan_job.id)
    )
    scan_thread.start() # This starts the thread and immediately continues.

    # Step 5: Immediately return the success response to the frontend.
    return db_asset
# --- END OF FIX ---


@router.get("/assets/{user_id}", response_model=List[AssetResponse])
def get_user_assets(user_id: str, db: Session = Depends(get_db)):
    return db.query(models.MonitoredAsset).filter(models.MonitoredAsset.user_id == user_id).all()

@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_monitored_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(models.MonitoredAsset).filter(models.MonitoredAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    db.delete(asset)
    db.commit()

@router.put("/alerts/{alert_id}/read", status_code=200)
def mark_alert_as_read(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    alert.is_read = True
    db.commit()
    
    return {"message": "Alert marked as read"}

@router.get("/alerts/{user_id}", response_model=List[AlertResponse])
def get_user_alerts(user_id: str, db: Session = Depends(get_db)):
    return db.query(models.Alert).filter(models.Alert.user_id == user_id).order_by(models.Alert.created_at.desc()).all()