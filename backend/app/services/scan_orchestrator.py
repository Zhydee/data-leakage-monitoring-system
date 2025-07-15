from app.schemas.scan import ScanRequest
from app.models import models  # Assuming this includes your DB models
from app.utils.regex_map import DATA_TYPE_REGEX_MAP  # We'll create this next
from datetime import datetime
import random  # Temporary stand-in for actual tool execution

async def start_scan_job(request: ScanRequest) -> int:
    # Validate data_type
    if request.data_type not in DATA_TYPE_REGEX_MAP:
        return None

    # Validate using regex
    import re
    pattern = request.custom_regex or DATA_TYPE_REGEX_MAP[request.data_type]
    if not re.match(pattern, request.search_data):
        return None

    # Insert scan_jobs entry
    scan_job = models.ScanJob.create(
        data_type=request.data_type,
        search_data=request.search_data,
        custom_regex=request.custom_regex,
        status="queued",
        created_at=datetime.utcnow()
    )

    scan_id = scan_job.id

    # Insert tool_status entries
    tools = ["gitleaks", "trufflehog", "hibp", "google_dork", "spiderfoot", "sherlock"]
    for tool in tools:
        models.ToolStatus.create(
            scan_job_id=scan_id,
            tool_name=tool,
            status="pending"
        )

    # Simulate dispatch (replace with Celery/async tasks later)
    for tool in tools:
        # This is just for Week 1 setup — later you'll replace this with real logic
        models.ScanResult.create(
            scan_job_id=scan_id,
            tool_name=tool,
            result={"mock": "Tool ran successfully"},
            confidence=round(random.uniform(0.6, 0.95), 2),
            severity="low"
        )
        models.ToolStatus.update_status(scan_id, tool, "completed")

    return scan_id
