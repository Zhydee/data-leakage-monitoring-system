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
    print("🔧 DEBUG: Inside start_scan_job()")
    db = SessionLocal()

    try:
        data_type = request.data_type.strip().lower()
        print("DEBUG: Normalized data_type =", data_type)

        if data_type not in DATA_TYPE_REGEX_MAP:
            print("❌ ERROR: Invalid data_type:", data_type)
            return None

        pattern = request.custom_regex or DATA_TYPE_REGEX_MAP[data_type]
        print("DEBUG: Using pattern:", pattern)

        if not re.match(pattern, request.search_data):
            print("❌ ERROR: Pattern did not match:", request.search_data)
            return None

        print("DEBUG: Creating ScanJob...")
        scan_job = models.ScanJob.create(
            data_type=data_type,
            search_data=request.search_data,
            custom_regex=request.custom_regex,
            status="queued",
            created_at=datetime.utcnow()
        )
        scan_id = scan_job.id
        print("✅ ScanJob created with ID:", scan_id)

        # Add status entries for all tools
        tools = ["gitleaks", "trufflehog", "google_dork", "spiderfoot", "leakcheck", "sherlock"]
        for tool in tools:
            print(f"⏳ Creating ToolStatus: {tool}")
            models.ToolStatus.create(
                job_id=scan_id,
                tool_name=tool,
                status="pending"
            )

        # Run sherlock if type is username
        if data_type == "username":
            print("⚙️ Running Sherlock...")
            result = run_sherlock(request.search_data)
            print("🔍 Sherlock result:", result)

            models.ToolStatus.update_status(
                db, scan_id, "sherlock",
                "completed" if result["success"] else "failed",
                result.get("error", result.get("note"))
            )
            if result["success"] and result.get("found_on"):
                models.ScanResult.create(
                    job_id=scan_id,
                    tool_name="sherlock",
                    result=result["found_on"],
                    confidence=0.8,
                    severity="low",
                    result_type="url",
                    source_url="https://github.com/sherlock-project/sherlock"
                )


                 # ✅ Run leakcheck if type is email
        if data_type == "email":
            print("⚙️ Running Leakcheck...")
            result = check_leakcheck(request.search_data)
            print("🔍 Leakcheck result:", result)
            models.ToolStatus.update_status(
                db, scan_id, "leakcheck",
                "completed" if result["success"] else "failed",
                result.get("error", result.get("note"))
            )

            if result["success"]:
                models.ScanResult.create(
                    job_id=scan_id,
                    tool_name="leakcheck",
                    result=result.get("breaches", []),
                    confidence=0.9,
                    severity="medium",
                    result_type="json",
                    source_url="https://leakcheck.io"
                )
            else:
                models.ScanResult.create(
                    job_id=scan_id,
                    tool_name="leakcheck",
                    result={"error": result.get("error", "No breaches found")},
                    confidence=0.0,
                    severity="low",
                    result_type="text",
                    source_url="https://leakcheck.io"
                )
        
        # Simulate other tools
        for tool in ["gitleaks", "trufflehog", "google_dork", "spiderfoot"]:
            models.ScanResult.create(
                job_id=scan_id,
                tool_name=tool,
                result={"mock": "Tool ran successfully"},
                confidence=0.7,
                severity="low",
                result_type="url",           # 👈 Sherlock finds URLs
                source_url=f"https://github.com/{tool}/{tool}"
            )
            models.ToolStatus.update_status(db, scan_id, tool, "completed")

        print("✅ Finished scan job logic.")
        return scan_id

    except Exception as e:
        print("❌ ERROR during scan job:", str(e))
        return None
    finally:
        db.close()

