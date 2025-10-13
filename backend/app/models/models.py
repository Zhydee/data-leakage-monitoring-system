# --- START OF FILE app/models/models.py (Corrected) ---

from app.database import Base
# --- NEW IMPORTS ---
from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime, JSON
from sqlalchemy.orm import relationship # <-- IMPORT THIS
# --- END NEW IMPORTS ---
from datetime import datetime
from app.database import SessionLocal

# 👤 Scan Job table
class ScanJob(Base):
    __tablename__ = "scan_jobs"
    id = Column(Integer, primary_key=True, index=True)
    data_type = Column(String)
    search_data = Column(String)
    custom_regex = Column(String, nullable=True)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # When a ScanJob is deleted, all of its children (results and tool_statuses)
    # will also be deleted automatically by the database because of the cascade rule.
    results = relationship("ScanResult", back_populates="job", cascade="all, delete-orphan")
    tool_statuses = relationship("ToolStatus", back_populates="job", cascade="all, delete-orphan")
    

    @classmethod
    def create(cls, data_type, search_data, custom_regex, status, created_at):
        db = SessionLocal()
        try:
            job = cls(
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
        except Exception as e:
            print("❌ ERROR in ScanJob.create():", str(e))
            return None
        finally:
            db.close()

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

    
    # This creates the child-to-parent link back to the ScanJob.
    job = relationship("ScanJob", back_populates="results")
    

    @classmethod
    def create(cls, job_id, tool_name, result, confidence, severity, result_type, source_url):
        db = SessionLocal()
        try:
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
        except Exception as e:
            print("❌ ERROR in ScanResult.create():", str(e))
            return None
        finally:
            db.close()

# ⚙️ Tool Status table
class ToolStatus(Base):
    __tablename__ = "tool_status"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("scan_jobs.id"))
    tool_name = Column(String)
    status = Column(String)
    error_message = Column(String, nullable=True)

    
    # This creates the child-to-parent link back to the ScanJob.
    job = relationship("ScanJob", back_populates="tool_statuses")
   

    @classmethod
    def create(cls, job_id, tool_name, status):
        db = SessionLocal()
        try:
            tool = cls(
                job_id=job_id,
                tool_name=tool_name,
                status=status
            )
            db.add(tool)
            db.commit()
            db.refresh(tool)
            return tool
        except Exception as e:
            print("❌ ERROR in ToolStatus.create():", str(e))
            return None
        finally:
            db.close()

    @classmethod
    def update_status(cls, db, job_id, tool_name, status, error_message=None):
        try:
            record = db.query(cls).filter_by(job_id=job_id, tool_name=tool_name).first()
            if record:
                record.status = status
                record.error_message = error_message
                db.commit()
                return True
            return False # Corrected this line from your original code
        except Exception as e:
            print("❌ ERROR in ToolStatus.update_status():", str(e))
            return False