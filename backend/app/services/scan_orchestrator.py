from app.schemas.scan import ScanRequest
from app.models import models
from app.database import SessionLocal
from app.utils.regex_map import DATA_TYPE_REGEX_MAP
from datetime import datetime
from tools.sherlock_wrapper import run_sherlock
from tools.hibp_email import check_hibp_breaches
from tools.hibp_passwords import check_pwned_password
from tools.spiderfoot_wrapper import run_spiderfoot
import re
import os
import random
from sqlalchemy import select 


SPIDERFOOT_MODULE_MAP = {
    "domain": ["sfp_dnsresolve", "sfp_dns", "sfp_whois"],
    "username": ["sfp_accounts", "sfp_breachcompilation"],
    "email": ["sfp_leakix", "sfp_whois"],
    "ip": ["sfp_dnsresolve", "sfp_shodan", "sfp_virustotal"],
    "metadata_domain": ["sfp_metadata"]
}

async def start_scan_job(request: ScanRequest) -> int:
    print("🔧 DEBUG: Inside start_scan_job()")
    db = SessionLocal()
    scan_id = None # Initialize scan_id

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
            status="running",
            created_at=datetime.utcnow()
        )
        scan_id = scan_job.id
        print("✅ ScanJob created with ID:", scan_id)

        # Add status entries for all tools
        tools = ["trufflehog", "google_dork", "spiderfoot", "hibp_emails", "sherlock", "hibp_passwords"]
        for tool in tools:
            print(f"⏳ Creating ToolStatus: {tool}")
            models.ToolStatus.create(
                job_id=scan_id,
                tool_name=tool,
                status="pending"
            )
        
        # --- HIBP PASSWORD WORKFLOW ---
        if data_type == "password":
            print("⚙️ Running HIBP Password Check...")
            result = check_pwned_password(request.search_data)
            print("🔍 HIBP Password result:", result)

            models.ToolStatus.update_status(
                db, scan_id, "hibp_passwords",
                "completed" if result["success"] else "failed",
                result.get("error")
            )

            if result["success"]:
                severity = "high" if result["pwned"] else "none"
                confidence = 1.0 if result["pwned"] else 0.0
                
                models.ScanResult.create(
                    job_id=scan_id,
                    tool_name="hibp_passwords",
                    result={"pwned": result["pwned"], "count": result.get("count", 0)},
                    confidence=confidence,
                    severity=severity,
                    result_type="json",
                    source_url="https://haveibeenpwned.com/Passwords"
                )

        # --- Sherlock Username Workflow ---
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

        # --- HIBP Email Workflow ---
        if data_type == "email":
            print("⚙️ Running HIBP Email Breach Check...")
            result = check_hibp_breaches(request.search_data)
            print("🔍 HIBP Email Breach result:", result)
            models.ToolStatus.update_status(
                db, scan_id, "hibp_emails",
                "completed" if result["success"] else "failed",
                result.get("error")
            )

            if result["success"]:
                severity = "high" if result.get("breaches") else "none"
                models.ScanResult.create(
                    job_id=scan_id,
                    tool_name="hibp_emails",
                    result=result.get("breaches", []),
                    confidence=1.0,
                    severity=severity,
                    result_type="json",
                    source_url="https://haveibeenpwned.com"
                )
            else:
                models.ScanResult.create(
                    job_id=scan_id,
                    tool_name="hibp_emails",
                    result={"error": result.get("error", "An unknown error occurred")},
                    confidence=0.0,
                    severity="low",
                    result_type="text",
                    source_url="https://haveibeenpwned.com"
                )
        # --- SpiderFoot Workflow ---
        if data_type in SPIDERFOOT_MODULE_MAP:
            modules_to_run = SPIDERFOOT_MODULE_MAP[data_type]
            print(f"⚙️ Running SpiderFoot Scan with modules: {modules_to_run}...")
            
            # Call the wrapper with the specific modules
            result = run_spiderfoot(request.search_data, modules=modules_to_run)
            print("🔍 SpiderFoot result:", result)

            models.ToolStatus.update_status(
                db, scan_id, "spiderfoot",
                "completed" if result["success"] else "failed",
                result.get("error")
            )

            if result["success"] and result.get("results"):
                severity = "medium"  # Default severity, can be refined later
                
                models.ScanResult.create(
                    job_id=scan_id,
                    tool_name="spiderfoot",
                    result=result["results"],
                    confidence=0.9, # Higher confidence as results are very specific
                    severity=severity,
                    result_type="json",
                    source_url="https://www.spiderfoot.net/"
                )


        # Simulate other tools 
        for tool in ["google_dork", "trufflehog"]:
            models.ScanResult.create(
                job_id=scan_id,
                tool_name=tool,
                result={"mock": "Tool ran successfully"},
                confidence=0.7,
                severity="low",
                result_type="url",
                source_url=f"https://github.com/{tool}/{tool}"
            )
            models.ToolStatus.update_status(db, scan_id, tool, "completed")

        print(f"✅ Finished all tool scans for Job ID: {scan_id}. Updating final status to 'completed'.")
        
        # --- MODIFIED: Switched to modern SQLAlchemy 2.0 query style ---
        stmt = select(models.ScanJob).where(models.ScanJob.id == scan_id)
        final_scan_job = db.scalars(stmt).first()

        if final_scan_job:
            final_scan_job.status = "completed"
            db.commit()
            print(f"✅ Successfully updated Job ID: {scan_id} to 'completed'.")
        else:
            print(f"❌ ERROR: Could not find Job ID: {scan_id} in the database to finalize status.")
        
        return scan_id

    except Exception as e:
        print(f"❌ FATAL ERROR during scan job {scan_id}: {str(e)}")
        if scan_id:
            # --- MODIFIED: Switched to modern SQLAlchemy 2.0 query style ---
            stmt = select(models.ScanJob).where(models.ScanJob.id == scan_id)
            error_scan_job = db.scalars(stmt).first()
            if error_scan_job:
                error_scan_job.status = "failed"
                db.commit()
        return None
    finally:
        db.close()