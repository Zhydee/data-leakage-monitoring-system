# --- START OF FINAL, DEFINITIVE tools/spiderfoot_wrapper.py ---

import subprocess
import json
import os
import sys
from dotenv import load_dotenv

def run_spiderfoot(target: str, modules: list[str]) -> dict:
    """
    Runs a SpiderFoot scan and correctly parses the streaming, slightly malformed
    JSON output from stdout by cleaning each line before parsing.

    Args:
        target: The domain, IP, email, etc., to scan.
        modules: A list of SpiderFoot module names (e.g., ["sfp_dns", "sfp_whois"]).

    Returns:
        A dictionary containing the results of the scan.
    """
    print(f"INFO: Starting SpiderFoot scan for '{target}' with modules: {modules}")

    if not modules:
        print("ERROR: No SpiderFoot modules specified.")
        return {"success": False, "error": "No modules specified for the scan."}

    try:
        # --- ROBUST PATH CONSTRUCTION ---
        wrapper_dir = os.path.dirname(os.path.abspath(__file__))
        spiderfoot_dir = os.path.join(wrapper_dir, "spiderfoot")
        sf_script_path = os.path.join(spiderfoot_dir, "sf.py")

        if not os.path.exists(sf_script_path):
            error_msg = f"SpiderFoot executable not found at {sf_script_path}"
            print(f"ERROR: {error_msg}")
            return {"success": False, "error": error_msg}

        python_executable = sys.executable
        module_string = ",".join(modules)
        
        command = [
            python_executable,
            sf_script_path,
            "-s", target,
            "-m", module_string,
            "-o", "json",
            "-q"
        ]

        print(f"INFO: Executing command: {' '.join(command)}")
        print(f"INFO: Using working directory: {spiderfoot_dir}")

        result = subprocess.run(
            command,
            cwd=spiderfoot_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            check=True,
            timeout=300
        )

        # --- PARSE THE STREAMING JSON OUTPUT (WITH CLEANING) ---
        parsed_results = []
        for line in result.stdout.strip().split('\n'):
            # THE CRITICAL FIX IS HERE:
            # 1. Strip whitespace from the line.
            # 2. Remove a trailing comma if it exists.
            clean_line = line.strip().rstrip(',')

            # Ensure the line is a valid JSON object before trying to parse
            if clean_line.startswith('{') and clean_line.endswith('}'):
                try:
                    parsed_results.append(json.loads(clean_line))
                except json.JSONDecodeError:
                    print(f"WARNING: Could not decode a cleaned line: {clean_line}")
        
        print(f"INFO: SpiderFoot scan completed. Parsed {len(parsed_results)} results.")
        return {"success": True, "results": parsed_results}

    except subprocess.CalledProcessError as e:
        error_details = e.stderr.strip()
        print(f"ERROR: SpiderFoot process failed with exit code {e.returncode}.")
        print(f"ERROR Details: {error_details}")
        return {"success": False, "error": f"SpiderFoot exited with an error: {error_details}"}
    except subprocess.TimeoutExpired:
        # specific error handler for timeouts
        print("ERROR: SpiderFoot scan timed out after 5 minutes.")
        return {"success": False, "error": "Scan timed out. The target is very large and the scan took longer than 5 minutes to complete."}
    
    except Exception as e:
        error_msg = f"An unexpected exception occurred: {str(e)}"
        print(f"FATAL: {error_msg}")
        return {"success": False, "error": error_msg}

# --- END OF FINAL, DEFINITIVE tools/spiderfoot_wrapper.py ---