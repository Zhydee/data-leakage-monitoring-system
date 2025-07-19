from app.schemas.scan import ScanRequest
from app.models import models
from app.database import SessionLocal
from app.utils.regex_map import DATA_TYPE_REGEX_MAP
from datetime import datetime
from tools.sherlock_wrapper import run_sherlock
from tools.leakcheck import check_leakcheck
import re
import random

async def start_scan_job(request: ScanRequest) -> int:
    # Create DB session
    db = SessionLocal()

    try:
        # Validate data_type
        if request.data_type not in DATA_TYPE_REGEX_MAP:
            return None

        # Validate search_data using regex
        pattern = request.custom_regex or DATA_TYPE_REGEX_MAP[request.data_type]
        if not re.match(pattern, request.search_data):
            return None

        # Insert scan_jobs record
        scan_job = models.ScanJob.create(
            data_type=request.data_type,
            search_data=request.search_data,
            custom_regex=request.custom_regex,
            status="queued",
            created_at=datetime.utcnow()
        )
        scan_id = scan_job.id

        # Define tools to run
        tools = ["gitleaks", "trufflehog", "google_dork", "spiderfoot", "leakcheck", "sherlock"]

        # Insert initial tool_status as "pending"
        for tool in tools:
            models.ToolStatus.create(
                scan_job_id=scan_id,
                tool_name=tool,
                status="pending"
            )

        # Sherlock logic (username only)
        if request.data_type == "username":
            result = run_sherlock(request.search_data)
            models.ToolStatus.update_status(
                db, scan_id, "sherlock",
                "completed" if result["success"] else "failed",
                result.get("error")
            )
            if result["success"]:
                models.ScanResult.create(
                    scan_job_id=scan_id,
                    tool_name="sherlock",
                    result=result["found_on"],
                    confidence=0.80,
                    severity="low"
                )

        # Leakcheck logic (email only)
        if request.data_type == "email":
            result = check_leakcheck(request.search_data)
            models.ToolStatus.update_status(
                db, scan_id, "leakcheck",
                "completed" if result["success"] else "failed",
                result.get("error")
            )
            if result["success"]:
                models.ScanResult.create(
                    scan_job_id=scan_id,
                    tool_name="leakcheck",
                    result=result["results"],
                    confidence=0.85,
                    severity="medium"
                )

        # Placeholder mock for the other tools (to be replaced later)
        for tool in ["gitleaks", "trufflehog", "google_dork", "spiderfoot"]:
            models.ScanResult.create(
                scan_job_id=scan_id,
                tool_name=tool,
                result={"mock": "Tool ran successfully"},
                confidence=round(random.uniform(0.6, 0.95), 2),
                severity="low"
            )
            models.ToolStatus.update_status(db, scan_id, tool, "completed")

        return scan_id

    finally:
        db.close()
