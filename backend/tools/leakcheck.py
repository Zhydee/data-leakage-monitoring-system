import requests
import os
import re

API_KEY = os.getenv("LEAKCHECK_API_KEY")

def detect_type(data: str) -> str:
    """Simple helper to determine if input is an email or username."""
    email_pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return "email" if re.match(email_pattern, data) else "username"

def check_leakcheck(data: str) -> dict:
    query_type = detect_type(data)

    params = {
        "key": API_KEY,
        "check": data,
        "type": query_type
    }

    try:
        response = requests.get("https://leakcheck.io/api/public", params=params)
        if response.status_code == 200:
            return {
                "success": True,
                "type": query_type,
                "results": response.json().get("result", [])
            }
        else:
            return {
                "success": False,
                "error": f"{response.status_code}: {response.text}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

