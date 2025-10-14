# FILE: tools/trufflehog_wrapper.py

import subprocess
import json
import logging

def run_trufflehog(repo_url: str) -> dict:
    """
    Scans a public GitHub repository using the TruffleHog CLI tool.

    Args:
        repo_url: The full URL of the GitHub repository to scan.

    Returns:
        A dictionary containing the success status and the scan results.
    """
    logging.info(f"Starting TruffleHog scan for repository: {repo_url}")
    
    # Command to execute TruffleHog. The --json flag is crucial for parsing.
    command = [
        "trufflehog",
        "github",
        "--repo",
        repo_url,
        "--json"
    ]

    try:
        # Execute the command
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True  # Decode stdout/stderr as text
        )

        stdout, stderr = process.communicate()

        # Check for errors during execution
        if process.returncode != 0:
            error_message = f"TruffleHog failed with return code {process.returncode}. Error: {stderr}"
            logging.error(error_message)
            # Check for common, user-friendly errors
            if "authentication failed" in stderr or "not found" in stderr:
                return {"success": False, "error": "Failed to access the repository. It might be private, deleted, or the URL may be incorrect."}
            return {"success": False, "error": error_message}

        # TruffleHog outputs one JSON object per line. We need to parse each line.
        findings = []
        if stdout:
            for line in stdout.strip().split('\n'):
                try:
                    findings.append(json.loads(line))
                except json.JSONDecodeError:
                    logging.warning(f"Could not parse a line from TruffleHog output: {line}")
        
        logging.info(f"TruffleHog scan completed. Found {len(findings)} potential secrets.")
        return {"success": True, "results": findings}

    except FileNotFoundError:
        # This error occurs if the 'trufflehog' command is not found in the system's PATH
        error_msg = "TruffleHog executable not found. Please ensure it is installed and in your system's PATH."
        logging.error(error_msg)
        return {"success": False, "error": error_msg}
    except Exception as e:
        # Catch any other unexpected errors
        error_msg = f"An unexpected error occurred while running TruffleHog: {e}"
        logging.error(error_msg)
        return {"success": False, "error": error_msg}