from app.schemas.scan import ScanRequest
from app.models import models
from app.database import SessionLocal
from app.utils.regex_map import DATA_TYPE_REGEX_MAP
from datetime import datetime
from tools.sherlock_wrapper import run_sherlock
from tools.hibp_email import check_hibp_breaches
from tools.hibp_passwords import check_pwned_password
from tools.trufflehog_wrapper import run_trufflehog
import re
import os
import random
import json
import logging
from sqlalchemy import select


def start_scan_job(request: ScanRequest, scan_source: str = "manual", scan_id: int = None):
    """
    Finds an existing scan job by its ID and runs all the necessary tools.
    This function is now designed to be run in the background.
    The scan_id MUST be provided.
    """
    if scan_id is None:
        logging.error("FATAL: start_scan_job was called without a scan_id.")
        return

    logging.info(f"Background scan task started for Job ID: {scan_id}...")
    db = SessionLocal()

    try:
        # Find the existing job and set its status to 'running'
        stmt = select(models.ScanJob).where(models.ScanJob.id == scan_id)
        scan_job = db.scalars(stmt).first()

        if not scan_job:
            logging.error(f"FATAL: Background task could not find Job ID {scan_id}.")
            return

        scan_job.status = "running"
        db.commit()
        logging.info(f"Job ID {scan_id} status updated to 'running'.")
        
        data_type = request.data_type.strip().lower()

        # Validation is still important
        if data_type not in DATA_TYPE_REGEX_MAP:
            logging.error(f"Invalid data_type for job {scan_id}: {data_type}")
            return
        pattern = request.custom_regex or DATA_TYPE_REGEX_MAP[data_type]
        if not re.match(pattern, request.search_data):
            logging.warning(f"Pattern did not match for job {scan_id}: {request.search_data}")
            return

        tools = ["trufflehog", "google_dork", "hibp_emails", "sherlock", "hibp_passwords"]
        for tool in tools:
            models.ToolStatus.create(db=db, job_id=scan_id, tool_name=tool, status="pending")

        # --- HIBP PASSWORD WORKFLOW ---
        if data_type == "password":
            logging.info(f"[{scan_id}] Running HIBP Password Check...")
            # ... (rest of the HIBP password logic is the same)
            result = check_pwned_password(request.search_data)
            models.ToolStatus.update_status(db, scan_id, "hibp_passwords", "completed" if result["success"] else "failed", result.get("error"))
            if result["success"]:
                models.ScanResult.create(db=db, job_id=scan_id, tool_name="hibp_passwords", result={"pwned": result["pwned"], "count": result.get("count", 0)}, confidence=1.0 if result["pwned"] else 0.0, severity="high" if result["pwned"] else "none", result_type="json", source_url="https://haveibeenpwned.com/Passwords")

        # --- Sherlock Username Workflow ---
        if data_type == "username":
            logging.info(f"[{scan_id}] Running Sherlock...")
            # ... (rest of the Sherlock logic is the same)
            result = run_sherlock(request.search_data)
            models.ToolStatus.update_status(db, scan_id, "sherlock", "completed" if result["success"] else "failed", result.get("error", result.get("note")))
            if result["success"] and result.get("found_on"):
                models.ScanResult.create(db=db, job_id=scan_id, tool_name="sherlock", result=result["found_on"], confidence=0.8, severity="low", result_type="url", source_url="https://github.com/sherlock-project/sherlock")
        
        # --- HIBP Email Workflow ---
        if data_type == "email":
            logging.info(f"[{scan_id}] Running HIBP Email Breach Check...")
            # ... (rest of the HIBP email logic is the same)
            result = check_hibp_breaches(request.search_data)
            models.ToolStatus.update_status(db, scan_id, "hibp_emails", "completed" if result["success"] else "failed", result.get("error"))
            if result["success"]:
                models.ScanResult.create(db=db, job_id=scan_id, tool_name="hibp_emails", result=result.get("breaches", []), confidence=1.0, severity="high" if result.get("breaches") else "none", result_type="json", source_url="https://haveibeenpwned.com")

        # --- Google Dork Workflow ---
        if data_type in ["phone", "ic", "username", "full_name", "email"]:
            logging.info(f"[{scan_id}] Running Google Custom Search...")
            # ... (rest of the Google Dork logic is the same)
            from app.services.google_search import run_google_dork
            result = run_google_dork(request.search_data)
            models.ToolStatus.update_status(db, scan_id, "google_dork", "completed" if result["success"] else "failed", result.get("error"))
            if result["success"] and result.get("results"):
                models.ScanResult.create(db=db, job_id=scan_id, tool_name="google_dork", result=result["results"], confidence=0.8, severity="medium", result_type="json", source_url="https://cse.google.com/")

        # --- TruffleHog GitHub Repo Workflow ---
        if data_type == "github_repo":
            logging.info(f"[{scan_id}] Running live TruffleHog Scan for GitHub repository...")
            # ... (rest of the TruffleHog logic is the same)
            result = run_trufflehog(request.search_data)
            models.ToolStatus.update_status(db, scan_id, "trufflehog", "completed" if result["success"] else "failed", result.get("error"))
            if result["success"] and result.get("results"):
                models.ScanResult.create(db=db, job_id=scan_id, tool_name="trufflehog", result=result["results"], confidence=0.95, severity="critical", result_type="json", source_url="https://github.com/trufflesecurity/trufflehog")

        logging.info(f"Finished all tool scans for Job ID: {scan_id}. Updating final status to 'completed'.")
        
        final_stmt = select(models.ScanJob).where(models.ScanJob.id == scan_id)
        final_scan_job = db.scalars(final_stmt).first()

        if final_scan_job:
            final_scan_job.status = "completed"
            db.commit()
            logging.info(f"Successfully updated Job ID: {scan_id} to 'completed'.")
        else:
            logging.error(f"Could not find Job ID: {scan_id} to finalize status.")
        
    except Exception as e:
        logging.exception(f"FATAL ERROR during scan job {scan_id}: {e}")
        if scan_id:
            error_stmt = select(models.ScanJob).where(models.ScanJob.id == scan_id)
            error_scan_job = db.scalars(error_stmt).first()
            if error_scan_job:
                error_scan_job.status = "failed"
                db.commit()
    finally:
        db.close()