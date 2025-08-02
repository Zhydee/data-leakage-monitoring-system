import subprocess
import tempfile
import os
import sys
import re

def run_sherlock(username: str) -> dict:
    try:
        # Still keep this for future use, but not used now
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_file:
            output_path = tmp_file.name

        sherlock_dir = os.path.abspath(os.path.dirname(__file__))

        print("📁 Sherlock directory (cwd):", sherlock_dir)

        result = subprocess.run(
            [
                sys.executable, "-m", "sherlock_project", username,
                "--print-found"
            ],
            capture_output=True,
            text=True,
            timeout=200,
            cwd=sherlock_dir  # 👈 Run from inside sherlock directory
        )

        print("🧪 STDOUT:", result.stdout[:500])  # Limit output for readability
        print("🧪 STDERR:", result.stderr[:500])

        # Parse stdout for URLs
        found_urls = re.findall(r'https?://\S+', result.stdout)

        if found_urls:
            return {
                "success": True,
                "found_on": found_urls
            }
        else:
            return {
                "success": True,
                "found_on": [],
                "error": "No URLs found in Sherlock output"
            }

    except Exception as e:
        return {"success": False, "error": str(e)}
