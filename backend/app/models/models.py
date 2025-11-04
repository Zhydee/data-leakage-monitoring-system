from app.database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship, Session
from datetime import datetime
# We no longer need SessionLocal here, as sessions are passed in
# from app.database import SessionLocal

# 👤 Scan Job table
class ScanJob(Base):
    __tablename__ = "scan_jobs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=True)
    scan_source = Column(String(20), nullable=False, default="manual")
    data_type = Column(String)
    search_data = Column(String)
    custom_regex = Column(String, nullable=True)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    results = relationship("ScanResult", back_populates="job", cascade="all, delete-orphan")
    tool_statuses = relationship("ToolStatus", back_populates="job", cascade="all, delete-orphan")

    @classmethod
    def create(cls, db: Session, data_type: str, search_data: str, custom_regex: str, status: str, created_at: datetime, scan_source: str = "manual", user_id: str = None):
        job = cls(
            user_id=user_id,
            scan_source=scan_source,
            data_type=data_type,
            search_data=search_data,
            custom_regex=custom_regex,
            status=status,
            created_at=created_at
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

# 📦 Scan Result table
class ScanResult(Base):
    __tablename__ = "scan_results"
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("scan_jobs.id"))
    tool_name = Column(String(50))
    result_type = Column(String(50))
    result_data = Column(JSON)
    severity = Column(String(20))
    confidence_score = Column(Float)
    source_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    job = relationship("ScanJob", back_populates="results")

    @classmethod
    def create(cls, db: Session, job_id: int, tool_name: str, result: dict, confidence: float, severity: str, result_type: str, source_url: str):
        result_record = cls(
            job_id=job_id,
            tool_name=tool_name,
            result_type=result_type,
            result_data=result,
            confidence_score=confidence,
            severity=severity,
            source_url=source_url
        )
        db.add(result_record)
        db.commit()
        db.refresh(result_record)
        return result_record

# ⚙️ Tool Status table
class ToolStatus(Base):
    __tablename__ = "tool_status"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("scan_jobs.id"))
    tool_name = Column(String)
    status = Column(String)
    error_message = Column(String, nullable=True)
    job = relationship("ScanJob", back_populates="tool_statuses")

    @classmethod
    def create(cls, db: Session, job_id: int, tool_name: str, status: str):
        tool = cls(job_id=job_id, tool_name=tool_name, status=status)
        db.add(tool)
        db.commit()
        db.refresh(tool)
        return tool

    @classmethod
    def update_status(cls, db: Session, job_id: int, tool_name: str, status: str, error_message: str = None):
        record = db.query(cls).filter_by(job_id=job_id, tool_name=tool_name).first()
        if record:
            record.status = status
            record.error_message = error_message
            db.commit()
            return True
        return False

class MonitoredAsset(Base):
    __tablename__ = "monitored_assets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    data_type = Column(String, nullable=False)
    search_data = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_scanned_at = Column(DateTime, nullable=True)
    previous_results_hash = Column(String, nullable=True)
    alerts = relationship("Alert", back_populates="asset", cascade="all, delete-orphan")

    @classmethod
    def create(cls, db: Session, user_id: str, data_type: str, search_data: str):
        asset = cls(user_id=user_id, data_type=data_type, search_data=search_data)
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("monitored_assets.id"), nullable=False)
    user_id = Column(String, nullable=False, index=True)
    scan_id = Column(Integer, nullable=False)
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    asset = relationship("MonitoredAsset", back_populates="alerts")

    @classmethod
    def create(cls, db: Session, asset_id: int, user_id: str, scan_id: int, message: str):
        alert = cls(
            asset_id=asset_id,
            user_id=user_id,
            scan_id=scan_id,
            message=message
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert