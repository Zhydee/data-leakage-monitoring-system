import requests
import os
from dotenv import load_dotenv

load_dotenv()

HIBP_API_KEY = os.getenv("HIBP_API_KEY")
# Endpoint to get the LIST of breaches for an account
API_URL_ACCOUNT = "https://haveibeenpwned.com/api/v3/breachedaccount/"
# Endpoint to get the full DETAILS of a single breach
API_URL_BREACH_DETAILS = "https://haveibeenpwned.com/api/v3/breach/"

def check_hibp_breaches(email: str) -> dict:
    """
    Checks an email address against the HIBP API, fetching full details for each breach.
    """
    if not HIBP_API_KEY:
        return {"success": False, "error": "HIBP_API_KEY is not set in the environment."}

    headers = {
        "hibp-api-key": HIBP_API_KEY,
        "User-Agent": "Data-Leakage-Monitoring-System"
    }
    
    try:
        # --- STEP 1: Get the list of summary breaches for the email ---
        summary_response = requests.get(f"{API_URL_ACCOUNT}{email}", headers=headers, timeout=10)
        
        if summary_response.status_code == 404:
            # No breaches found, this is a successful outcome.
            return {"success": True, "breaches": []}
        
        if summary_response.status_code != 200:
            return {"success": False, "error": f"API (account check) returned status code {summary_response.status_code}: {summary_response.text}"}

        summary_breaches = summary_response.json()
        detailed_breaches = []

        # --- STEP 2: Loop through each summary breach and get its full details ---
        for summary_breach in summary_breaches:
            breach_name = summary_breach.get("Name")
            if not breach_name:
                continue # Skip if a breach has no name

            print(f"🔍 Fetching details for breach: {breach_name}")
            details_response = requests.get(f"{API_URL_BREACH_DETAILS}{breach_name}", headers=headers, timeout=10)

            if details_response.status_code == 200:
                # Append the full, detailed breach object to our list
                detailed_breaches.append(details_response.json())
            else:
                # If details fail, append the summary info so the user still sees something
                print(f"⚠️ Could not fetch details for {breach_name}. Status: {details_response.status_code}")
                detailed_breaches.append(summary_breach) # Fallback to summary

        return {"success": True, "breaches": detailed_breaches}
            
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"An error occurred: {str(e)}"}