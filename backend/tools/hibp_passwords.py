# tools/hibp_passwords.py

import requests
import hashlib

def check_pwned_password(password: str) -> dict:
    """
    Checks if a password has been pwned using the HIBP Pwned Passwords API.
    
    Args:
        password: The password to check.
        
    Returns:
        A dictionary with the scan results.
    """
    print(f"🔧 Checking password against HIBP: {password[:2]}...") # Log first 2 chars for privacy

    try:
        # 1. Create a SHA-1 hash of the password
        sha1_password = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
        
        # 2. Split the hash into prefix and suffix
        prefix = sha1_password[:5]
        suffix = sha1_password[5:]
        
        # 3. Send the prefix to the HIBP API
        api_url = f'https://api.pwnedpasswords.com/range/{prefix}'
        response = requests.get(api_url, timeout=5) # Add a timeout
        response.raise_for_status()
            
        # 4. Check the response for the suffix
        hashes = (line.split(':') for line in response.text.splitlines())
        
        for h, count in hashes:
            if h == suffix:
                # Found a match!
                return {
                    "success": True,
                    "pwned": True,
                    "count": int(count)
                }
                
        # 5. If no match was found, the password is safe
        return {
            "success": True,
            "pwned": False,
            "count": 0
        }

    except requests.RequestException as e:
        print(f"❌ ERROR connecting to HIBP API: {e}")
        return {
            "success": False,
            "error": "Could not connect to the HIBP API."
        }
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        return {
            "success": False,
            "error": "An unexpected error occurred during the password check."
        }