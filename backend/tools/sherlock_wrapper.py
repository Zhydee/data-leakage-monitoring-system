import subprocess
import json

def run_sherlock(username: str) -> dict:
    try:
        # Run Sherlock and output to JSON file
        result = subprocess.run(
            ["sherlock", username, "--json", "--print-found"],
            capture_output=True,
            text=True,
            timeout=90
        )
        output = result.stdout.strip()

        # Parse JSON output if available
        if output:
            return {
                "found_on": json.loads(output),
                "success": True
            }
        else:
            return {
                "found_on": {},
                "success": False,
                "error": "No results or output could not be parsed."
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
