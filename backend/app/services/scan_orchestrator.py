from app.schemas.scan import ScanRequest
from app.models import models
from app.database import SessionLocal
from app.utils.regex_map import DATA_TYPE_REGEX_MAP
from datetime import datetime
from tools.sherlock_wrapper import run_sherlock
from tools.hibp_email import check_hibp_breaches
from tools.hibp_passwords import check_pwned_password
from tools.spiderfoot_wrapper import run_spiderfoot
from tools.trufflehog_wrapper import run_trufflehog
import re
import os
import random
import json  # add at top of file if not already present
import logging  
from sqlalchemy import select 


SPIDERFOOT_MODULE_MAP = {
    "domain": ["sfp_dnsresolve", "sfp_dns", "sfp_whois"],
    "ip": ["sfp_dnsresolve", "sfp_shodan", "sfp_virustotal"]
}
# This sets up a basic logger that prints timestamped messages
logging.basicConfig(
    level=logging.INFO, # Set the minimum level of messages to log
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

async def start_scan_job(request: ScanRequest) -> int:
    logging.info("Scan job initiated...")
    db = SessionLocal()
    scan_id = None # Initialize scan_id

    try:
        data_type = request.data_type.strip().lower()
        logging.info(f"Normalized data_type = {data_type}") 

        if data_type not in DATA_TYPE_REGEX_MAP:
            logging.error(f"Invalid data_type received: {data_type}")
            return None

        pattern = request.custom_regex or DATA_TYPE_REGEX_MAP[data_type]
        logging.info(f"Using pattern for validation: {pattern}") 

        if not re.match(pattern, request.search_data):
            print("❌ ERROR: Pattern did not match:", request.search_data)
            return None

        logging.info("Creating ScanJob in the database...") 
        scan_job = models.ScanJob.create(
            data_type=data_type,
            search_data=request.search_data,
            custom_regex=request.custom_regex,
            status="running",
            created_at=datetime.utcnow()
        )
        scan_id = scan_job.id
        logging.info(f"ScanJob created successfully with ID: {scan_id}")

        # Add status entries for all tools
        tools = ["trufflehog", "google_dork", "spiderfoot", "hibp_emails", "sherlock", "hibp_passwords"]
        for tool in tools:
            logging.info(f"Creating pending ToolStatus for: {tool}")
            models.ToolStatus.create(
                job_id=scan_id,
                tool_name=tool,
                status="pending"
            )
        
        # --- HIBP PASSWORD WORKFLOW ---
        if data_type == "password":
            logging.info("Running HIBP Password Check...")
            result = check_pwned_password(request.search_data)
            logging.info(f"HIBP Password result: {result}")

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
            logging.info("Running Sherlock...")
            result = run_sherlock(request.search_data)
            logging.info(f"Sherlock result: {result}") 

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
            logging.info("Running HIBP Email Breach Check...")
            result = check_hibp_breaches(request.search_data)
            logging.info(f"HIBP Email Breach result: {result}")
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
            logging.info(f"Running SpiderFoot Scan with modules: {modules_to_run}...")
            
            # Call the wrapper with the specific modules
            result = run_spiderfoot(request.search_data, modules=modules_to_run)
            logging.info(f"SpiderFoot result: {result}")

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
            # --- Google API Workflow ---
        from app.services.google_search import run_google_dork

        # --- Google Dork Workflow ---
        if data_type in ["phone", "ic"]:  # Only run for phone or IC
            print("⚙️ Running Google Custom Search...")
            logging.info("Running Google Custom Search...") 
            result = run_google_dork(request.search_data)
            try:
                success = bool(result.get("success"))
                hits = result.get("results", []) or []
                logging.info("orchestrator: run_google_dork returned success=%s results_count=%d", success, len(hits))
                # log a compact JSON sample of up to first 5 hits for inspection
                if hits:
                    sample = hits[:5]
                    logging.debug("orchestrator: run_google_dork sample hits: %s", json.dumps(sample, ensure_ascii=False) )
                else:
                    logging.debug("orchestrator: run_google_dork returned zero hits for query=%s", request.search_data)
            except Exception as e:
                logging.exception("orchestrator: error while inspecting run_google_dork result: %s", e)
            # ----------------------------------------------------------------

            models.ToolStatus.update_status(
                db, scan_id, "google_dork",
                "completed" if result["success"] else "failed",
                result.get("error")
            )

            if result["success"]:
                models.ScanResult.create(
                    job_id=scan_id,
                    tool_name="google_dork",
                    result=result["results"],
                    confidence=0.8,
                    severity="medium",
                    result_type="json",
                    source_url="https://cse.google.com/"
                )

        # Simulate other tools 
        # --- TruffleHog API Key Workflow ---
        # --- TruffleHog GitHub Repo Workflow ---
        if data_type == "github_repo":
            logging.info("Running live TruffleHog Scan for GitHub repository...")
            
            # Call the actual wrapper function from your file
            result = run_trufflehog(request.search_data)
            logging.info(f"TruffleHog wrapper returned: success={result['success']}")

            # Update the status of the tool based on the result
            models.ToolStatus.update_status(
                db, scan_id, "trufflehog",
                "completed" if result["success"] else "failed",
                result.get("error")
            )

            # If the scan was successful and found something, create a result record.
            # This now correctly checks for the "results" key from your wrapper.
            if result["success"] and result.get("results"):
                logging.info(f"TruffleHog found {len(result['results'])} findings. Saving to database.")
                models.ScanResult.create(
                    job_id=scan_id,
                    tool_name="trufflehog",
                    # This now correctly saves the data from the "results" key.
                    result=result["results"], 
                    confidence=0.95,
                    severity="critical",
                    result_type="json",
                    source_url="https://github.com/trufflesecurity/trufflehog"
                )

        logging.info(f"Finished all tool scans for Job ID: {scan_id}. Updating final status to 'completed'.")
        
        # --- MODIFIED: Switched to modern SQLAlchemy 2.0 query style ---
        stmt = select(models.ScanJob).where(models.ScanJob.id == scan_id)
        final_scan_job = db.scalars(stmt).first()

        if final_scan_job:
            final_scan_job.status = "completed"
            db.commit()
            logging.info(f"Successfully updated Job ID: {scan_id} to 'completed'.")
        else:
            logging.error(f"Could not find Job ID: {scan_id} in the database to finalize status.")
        
        return scan_id

    except Exception as e:
        logging.exception(f"FATAL ERROR during scan job {scan_id}: {e}")
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