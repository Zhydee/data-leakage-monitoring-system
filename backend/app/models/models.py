from app.database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime, JSON
from datetime import datetime

# 👤 Scan Job table
class ScanJob(Base):
    __tablename__ = "scan_jobs"
    id = Column(Integer, primary_key=True, index=True)
    data_type = Column(String)
    search_data = Column(String)
    custom_regex = Column(String, nullable=True)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

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

# ⚙️ Tool Status table (already present)
class ToolStatus(Base):
    __tablename__ = "tool_status"
    id = Column(Integer, primary_key=True, index=True)
    scan_job_id = Column(Integer, ForeignKey("scan_jobs.id"))
    tool_name = Column(String)
    status = Column(String)
    error_message = Column(String, nullable=True)
