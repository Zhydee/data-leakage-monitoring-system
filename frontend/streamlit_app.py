import streamlit as st
from streamlit_option_menu import option_menu
import tldextract
from datetime import datetime
import locale
import traceback
import json
from zoneinfo import ZoneInfo
import requests
import random
import os
import re
import time
import plotly.express as px
import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from authlib.integrations.requests_client import OAuth2Session
from authlib.jose import jwt
import secrets # Used to generate a secure nonce
import asyncio
import threading
import streamlit.components.v1 as components
from dotenv import load_dotenv
load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Data Leakage Monitoring System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"  # ENSURES SIDEBAR IS INITIALLY OPEN AND BUTTON IS ALWAYS FUNCTIONAL
)
# --- AUTH0 CONFIGURATION ---
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
# --- OAUTH SETUP ---
session = OAuth2Session(
    client_id=AUTH0_CLIENT_ID,
    client_secret=AUTH0_CLIENT_SECRET,
    scope='openid profile email',
    redirect_uri="http://localhost:8501",
)

@st.cache_data(ttl=3600, show_spinner=False) # Cache for 1 hour
def get_jwks():
    """Fetches and caches the JSON Web Key Set from Auth0."""
    jwks_uri = f'https://{AUTH0_DOMAIN}/.well-known/jwks.json'
    jwks = requests.get(jwks_uri).json()
    return jwks

# --- Helper Function For Authentication ---
def get_authorization_url():
    """Generates the Auth0 authorization URL."""
    st.session_state['nonce'] = secrets.token_urlsafe(16)
    
    # THE FIX: Manually define the authorization endpoint URL
    authorization_endpoint = f'https://{AUTH0_DOMAIN}/authorize'
    
    authorization_url, _ = session.create_authorization_url(
        url=authorization_endpoint,
        nonce=st.session_state['nonce']
    )
    return authorization_url
# Verified user identity. This is the core proof of authentication.
@st.cache_data(ttl=3600, show_spinner=False)
def get_user_info(code, auth_response):
    """
    Exchanges the authorization code for an access token and decodes the ID token.
    This is the final, robust version with the clock skew fix.
    """
    try:
        token_endpoint = f'https://{AUTH0_DOMAIN}/oauth/token'
        
        token = session.fetch_token(
            url=token_endpoint,
            code=code,
            authorization_response=auth_response 
        )

        jwks = get_jwks()

        # Define the claims options for validation.
        claims_options = {
            'iss': {'essential': True, 'values': [f'https://{AUTH0_DOMAIN}/']},
            'aud': {'essential': True, 'values': [AUTH0_CLIENT_ID]}
        }

        # Decode the token with a 5-minute leeway to handle clock skew robustly.
        user_info = jwt.decode(
            token['id_token'],
            key=jwks,
            claims_options=claims_options,
            claims_params={'leeway': 300}
        )
        
        user_info.validate()
        
        return user_info

    except Exception as e:
        # Log the error to the terminal for debugging, but re-raise it
        # so the handle_auth_redirect function can show an error to the user.
        print(f"An error occurred in get_user_info: {e}")
        raise


def display_login_prompt():
    """Shows a message and a sign-in button for protected pages."""
    st.warning("🔒 This feature is for signed-in users only.")
    st.markdown("Please sign in to view your personalized dashboard and reports.")
    
    auth_url = get_authorization_url()
    st.link_button("Sign in ", auth_url, use_container_width=True)
# For Authentication
def handle_auth_redirect():
    """
    Checks for the auth code, provides immediate user feedback, and logs the user in.
    """
    query_params = st.query_params
    
    # Check if the 'code' parameter exists in the URL
    if "code" in query_params:
        auth_code = query_params.get("code")
        
        # Immediately clear the ugly URL params
        st.query_params.clear()

        # If we have a code but the user is not yet in the session state, process the login
        if auth_code and 'user' not in st.session_state:
            
            # Show a spinner to the user so they know something is happening
            with st.spinner("Authenticating, please wait..."):
                try:
                    # Construct the full response URL required by the library
                    auth_response = f"http://localhost:8501/?code={auth_code}"
                    
                    # Call the function to get user info
                    user_info = get_user_info(auth_code, auth_response)
                    
                    # If successful, store user info in the session and rerun
                    st.session_state['user'] = user_info
                    
                    # A small delay can make the transition feel smoother
                    time.sleep(0.5) 
                    st.rerun()

                except Exception as e:
                    st.error(f"Error during login: {e}")
                    st.error("Authentication failed. Please try signing in again.")
                    # Optionally, add a button to try again
                    auth_url = get_authorization_url()
                    st.link_button("Try Again", auth_url)

# --- PDF ---
def pdf_to_bytes(pdf) -> bytes:
    """
    Works with both FPDF 1.x and fpdf2 2.x.
    """
    try:
        out = pdf.output()                 # fpdf2: returns bytes/bytearray
    except TypeError:
        # Older FPDF that expects the 'dest' kwarg
        out = pdf.output(dest="S")

    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    # FPDF 1.x may return a str
    if isinstance(out, str):
        return out.encode("latin-1")
    # Last resort
    return bytes(out)

def get_scan_history():
    """
    Fetches scan history.
    - For logged-in users, fetches their full history via the secure endpoint.
    - For guests, fetches ONLY the last scan they ran in this session.
    """
    try:
        # --- A. LOGIC FOR LOGGED-IN USERS (This part is mostly the same) ---
        if 'user' in st.session_state:
            user_id = st.session_state['user'].get('sub')
            if not user_id:
                return [] # Return empty list if user_id is missing
            
            api_url = f"{BACKEND_URL}/scan-history/{user_id}"
            res = requests.get(api_url)

            if res.status_code == 200:
                return res.json()
            else:
                st.error(f"Failed to fetch scan data: Status code {res.status_code}")
                return None

        # --- B. NEW LOGIC FOR GUEST USERS ---
        else:
            # Check if we have stored an ID for a scan this guest recently ran
            guest_scan_id = st.session_state.get('last_guest_scan_id')
            
            if guest_scan_id:
                # Use the new public endpoint to get only this specific scan
                api_url = f"{BACKEND_URL}/scan/{guest_scan_id}"
                res = requests.get(api_url)

                if res.status_code == 200:
                    # The UI expects a list of scans, so we wrap the single result in a list
                    return [res.json()]
                else:
                    # If the scan is not found (e.g., still processing), just return empty
                    return []
            else:
                # This guest has not run any scans in this session yet
                return []

    except Exception as e:
        st.error(f"❌ An error occurred while fetching scan history: {e}", icon="🔥")
        return None
    
# --- Footer ---
def render_footer():
    """Renders the custom footer."""
    st.markdown(
        """
        <div class="custom-footer">
            © 2025 Data Leakage Monitoring System | A Final Year Project by M.Zaidi Fahmi. For educational use only.
        </div>
        """,
        unsafe_allow_html=True
    )
st.markdown("""
    <style>
        /* --- General App Styling (Bright Theme) --- */
        html {
            font-size: 16px;
        }
        body, .main {
            background-color: #F8F9FA;
            color: #212529;
            font-size: 0.95rem;
        }
        
        /* --- Main Content Area Centering & Max-Width --- */
        .block-container {
            max-width: 1100px;
            padding: 1.5rem;
            margin: 0 auto;
        }
        /* --- Scalable Typography using REM --- */
        h1 { font-size: 2.25rem; }
        h2 { font-size: 1.6rem; }
        h3 { font-size: 1.25rem; }
        h5 { font-size: 1.1rem; }
        /* --- Hide Unwanted Streamlit Elements --- */
        #MainMenu { visibility: hidden; }
        
        /* --- Custom Footer Styling --- */
        .custom-footer {
            text-align: center;
            padding: 1.5rem 0;
            color: #475569; /* A subtle, professional dark gray */
            font-size: 0.9rem;
            border-top: 1px solid #E0E0E0; /* A faint line to separate it */
            margin-top: 2rem;
        }
        /* --- Sidebar Styling --- */
        [data-testid="stSidebar"] {
            background-color: #E9ECEF;
            border-right: 1px solid #D1D5DB;
        }
        
        /* --- SELECTOR FOR FORM SUBMIT BUTTON --- */
        .stButton>button, [data-testid="stFormSubmitButton"]>button {
            border: 2px solid #f39c12;
            background-color: #f39c12;
            color: #FFFFFF;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-weight: bold;
            font-size: 0.9rem;
            transition: all 0.3s ease;
        }
        .stButton>button:hover, [data-testid="stFormSubmitButton"]>button:hover {
            background-color: #e67e22;
            border-color: #e67e22;
        }
        
        /* --- Input & Selectbox Styling --- */
        .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div {
            background-color: #FFFFFF;
            color: #212529;
            border-radius: 8px;
            border: 1px solid #CED4DA;
            font-size: 0.9rem;
        }
        
        /* --- Compact Expander Styling --- */
        .st-expander, [data-testid="stExpander"] {
            background-color: #FFFFFF;
            border: 1px solid #E0E0E0;
            border-radius: 10px;
        }
        .st-expander header, [data-testid="stExpanderHeader"] {
            font-size: 1.05rem;
            color: #2c3e50;
            font-weight: bold;
            padding-top: 0.75rem;
            padding-bottom: 0.75rem;
        }
    </style>
""", unsafe_allow_html=True)

# --- DATA MAPPING ---
backend_data_type_map = {
    "Email Address": "email",
    "Full Name": "full_name",
    "IC Number": "ic", 
    "Password": "password",
    "Phone Number": "phone", 
    "Username": "username",
    "GitHub Repository": "github_repo",
}
display_name_map = {v: k for k, v in backend_data_type_map.items()}
regex_patterns = {
                    "Email Address": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                    "Password": r".{6,}", "Phone Number": r'^(?:\+?60|60|0)(?:[\s\-\.]?\(?\d{1,3}\)?)(?:[\s\-\.]?\d){6,8}$',
                    "Username": r"^[a-zA-Z0-9_-]{3,16}$",
                    "IC Number": r"^\d{6}-?\d{2}-?\d{4}$", "Full Name": r"^[A-Za-z\s.'@]+$", "GitHub Repository": r"^https?://github\.com/[\w.-]+/[\w.-]+/?$",
                }

RECOMMENDATION_MAP = {
    "blog": """
        **💡 Recommendation:**<br>
        This is a public blog. Review the posts to ensure you are not sharing sensitive personal information (like your full name, address, or workplace) that you want to keep private.
    """,
    "social": """
        **💡 Recommendation:**<br>
        This is a social media profile. Check your privacy settings on this site to control who can see your posts, photos, and personal details. Be mindful of what you share publicly.
    """,
    "hobby": """
        **💡 Recommendation:**<br>
        This account relates to a hobby. Ensure it doesn't reveal sensitive information, like your location through check-ins or photos.
    """,
    "music": """
        **💡 Recommendation:**<br>
        This is a music-related profile. Public playlists or listening habits are generally low-risk, but check your profile page for any personal details you didn't intend to share.
    """,
    "tech": """
        **💡 Recommendation:**<br>
        This is a tech or software development profile. Ensure you have not accidentally shared any API keys, tokens, or other secrets in public posts or code snippets.
    """,
    "default": """
        **💡 Recommendation:**<br>
        Click the link to review this profile. Check for any personal information (like your location, workplace, or phone number) that you did not intend to be public. Consider updating your privacy settings on that site.
    """
}

# --- NEW HELPER FUNCTION TO GET PLAYBOOK TEXT ---
def get_playbook_for_scan(scan_type: str) -> dict:
    """
    Returns the contextual risk and actionable playbook text for a given scan type,
    written in simple, non-technical language for the general public.
    """
    playbooks = {
        "email": {
            "risk": """Your email address is like the master key to your digital life. When it appears in a data breach, hackers get access to both your email and the password you used on that site. They use this to:
- **Break Into Other Accounts:** If you reuse passwords, they will try the leaked password on your email, banking, and social media accounts.
- **Send Convincing Scams:** They can create targeted scam emails (phishing) that look real, tricking you into revealing more sensitive information.
- **Attempt Identity Theft:** With enough information, they can try to impersonate you.""",
            "playbook": """Follow these steps immediately to protect yourself:
1.  **Change Your Passwords Now:** Go to the websites listed in the breach and change your password. Most importantly, if you used that same password anywhere else, change it there too.
2.  **Enable Extra Security (2FA):** Turn on "Two-Factor Authentication" (also called 2FA or MFA) for your important accounts, especially your email. This sends a unique code to your phone when you log in, stopping a hacker even if they have your password.
3.  **Use a Password Manager:** Consider using a password manager (like Bitwarden or 1Password). These tools create and remember a unique, strong password for every site, so you don't have to."""
        },
        "password": {
            "risk": """This password is no longer safe. It has been exposed in a data breach and is now on public lists used by hackers. Using this password for any account is like leaving your front door wide open.
- **Automated Attacks:** Hackers will use this password in automated attacks to try and log into thousands of popular websites, hoping to find one of your accounts.
- **Account Takeover:** If they get into one account, they will try to use it to reset the passwords for your other, more important accounts.""",
            "playbook": """Take these steps immediately for any account using this password:
1.  **Stop Using This Password:** Change this password immediately on every single website and app where you currently use it.
2.  **Create New, Unique Passwords:** Do not just change one character. Each account needs its own completely different, strong password.
3.  **Get a Password Manager:** This is the best way to manage unique passwords. A password manager is a secure app that creates and remembers strong passwords for you, so you only need to remember one master password.
4.  **Turn On Extra Security (2FA):** Enable "Two-Factor Authentication" wherever you can. It's your best defense against password leaks."""
        },
        "phone": {
            "risk": """Having your phone number or IC number public is a high risk. Scammers and identity thieves specifically look for this information to:
- **Target You with Scams:** Expect an increase in spam calls and scam text messages designed to trick you.
- **Impersonate You:** Your IC number is a core piece of your identity and can be used to open fraudulent accounts in your name.
- **Hijack Your Phone Number:** Criminals can try to trick your mobile provider into moving your number to their phone. This lets them intercept your calls, messages, and security codes.""",
            "playbook": """Here is how to handle this exposure:
1.  **Investigate the Source:** Look at the websites listed in the findings to understand why your information is public.
2.  **Request Removal:** Contact the website's administrator and ask them to remove your personal information.
3.  **Delete it Yourself:** If it's a post you made on social media or a forum, log in and delete it immediately.
4.  **Be Extra Cautious:** Be very suspicious of unexpected calls or texts. Never give out personal details or one-time security codes that are sent to you."""
        },
        "full_name": {
            "risk": """Having your full legal name exposed on public websites is a significant privacy risk. It's the primary piece of data that links your online activities to your real-world identity. Attackers can use it to:
- **De-anonymize You:** Connect your anonymous usernames from forums or social media back to who you really are.
- **Craft Targeted Scams:** Phishing emails and scam messages are far more convincing when they use your full name.
- **Build a Profile for Identity Theft:** Your name is the starting point for criminals to gather more information about you, such as your address, phone number, and workplace.""",
            "playbook": """1.  **Investigate the Context:** Carefully review the links from the scan to understand why your name is public. Is it a conference attendee list, a public record, or a forum post you once made?
2.  **Request Takedown for Unintentional Leaks:** If your name is on a list or document where it shouldn't be (like a leaked customer list), contact the website's administrator and request they remove the information, citing privacy concerns.
3.  **Remove it Yourself:** If it's a social media profile or a forum post you created, log in and either edit the post to use a pseudonym or delete it entirely.
4.  **Be Mindful in the Future:** When signing up for new services, consider if it's truly necessary to provide your full legal name. Use an alias or just your first name for non-official accounts."""
        },
        "github_repo": {
            "risk": """An exposed "secret" (like an API key) in a public code repository is a critical risk. It's like leaving the key to your office or cloud services lying on the street for anyone to pick up and use. An attacker can:
- **Steal Your Data:** Access, change, or delete information from the service the key belongs to.
- **Impersonate You:** Take actions on your behalf without your knowledge.
- **Run Up Huge Bills:** If the key is for a cloud service (like AWS or Google Cloud), an attacker can use it to run expensive operations, leaving you with a massive bill.""",
            "playbook": """Act IMMEDIATELY. Every second counts.
1.  **Disable the Leaked Key (Most Important Step):** Log into the dashboard of the service the key belongs to and immediately revoke or delete it. This makes the leaked key useless.
2.  **Generate a New Key:** Create a new, replacement key to be used safely.
3.  **Update Your Applications:** Replace the old, revoked key with the new one in all your applications.
4.  **Remove From History:** Simply deleting the key from your code isn't enough, as it remains in the project's history. You must use a specialized tool to permanently erase it from all past versions."""
        },
        "username": {
            "risk": """Finding your username exposes your digital life in two ways:
- **Digital Footprint:** Public profiles you created reveal your interests, location, and connections. Scammers use this to build a profile on you for targeted phishing attacks.
- **Unintentional Leaks:** Your username might also appear in places you didn't intend, such as public forums discussing a data breach or in leaked log files. This is a more direct security risk.""",
            "playbook": """Follow this two-part plan to secure your identity:
1.  **Manage Your Digital Footprint (Social Media):** Review the public profiles found in the report. Remove sensitive details (full birthdate, phone number, address) and tighten your privacy settings on each site to "Friends Only" or "Private".
2.  **Address Unintentional Leaks (Web Mentions):** Investigate any other links where your username was found. If the context is sensitive, contact the website administrator and request a takedown of the information. If it's a post you made, delete it yourself."""
        },
    }
    # For "ic", the playbook is the same as for "phone"
    playbooks["ic"] = playbooks["phone"]
    
    return playbooks.get(scan_type, {"risk": "No specific risk analysis available.", "playbook": "Review the findings and take appropriate action."})

# --- NEW FUNCTION TO GENERATE PDF REPORTS ---
def safe_filename(text: str, max_len: int = 60) -> str:
    # strip protocol
    text = re.sub(r'^https?://', '', text, flags=re.IGNORECASE)
    # replace anything not alnum, dash, underscore or dot with underscore
    text = re.sub(r'[^A-Za-z0-9._-]+', '_', text).strip("._-")
    if not text:
        text = "report"
    return (text[:max_len])  # keep it short; browsers don’t need full URL here

def write_markdown_to_pdf(pdf, text, height=5):
    """
    A helper to write text with simple Markdown (like **bold**) to an FPDF object.
    """
    # Set base font
    pdf.set_font("Helvetica", "", 10)
    
    # Handle bullet points
    if text.strip().startswith("- "):
        text = text.strip()[2:] # Remove the "- "
        pdf.cell(5) # Indent
        pdf.multi_cell(0, height, f"- {text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        return

    # Split the text by the bold delimiter '**'
    parts = text.split('**')
    
    for i, part in enumerate(parts):
        if i % 2 == 0:
            # This is normal text
            pdf.set_font("Helvetica", "", 10)
        else:
            # This is bold text
            pdf.set_font("Helvetica", "B", 10)
        pdf.write(height, part)
    pdf.ln(height) # Move to the next line after processing all parts

# --- PDF GENERATION FUNCTION ---
def generate_scan_report_pdf(scan: dict, display_name_map: dict) -> bytes:
    """
    Generates a robust and visually appealing PDF report for a single scan job.
    This version includes renderers for all supported data types.
    """
    
    pdf = FPDF()
    
    pdf.set_auto_page_break(auto=True, margin=15) 
    pdf.add_page()
    
    # --- Truncate search_data for the title ---
    display_search_data = scan['search_data']
    if len(display_search_data) > 50:
        display_search_data = display_search_data[:47] + "..."

    # --- 1. Main Report Header ---
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, "Data Leakage Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.multi_cell(0, 8, f"Scan Target: {display_search_data}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(8)

    # --- 2. Redesigned Scan Summary Box ---
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(241, 245, 249) # Light gray background
    pdf.cell(0, 10, "  Scan Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.ln(5)

    dt = datetime.fromisoformat(scan["timestamp"]).replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kuala_Lumpur")).strftime("%d %B %Y, %I:%M %p")
    display_data_type = display_name_map.get(scan['data_type'], scan['data_type'].capitalize())
    severity = calculate_overall_severity(scan['data_type'], scan.get("results", {})) or "Not Found"
    
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(40, 7, "  Date of Scan:")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, dt, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(40, 7, "  Data Type Scanned:")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, display_data_type, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(40, 7, "  Overall Severity:")
    
    severity_colors = {
        "CRITICAL": (198, 40, 40), "HIGH": (230, 81, 0),
        "MEDIUM": (249, 168, 37), "LOW": (46, 125, 50),
    }
    badge_color = severity_colors.get(severity.upper(), (84, 110, 122))
    
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(r=badge_color[0], g=badge_color[1], b=badge_color[2])
    pdf.set_text_color(255, 255, 255)
    pdf.cell(30, 7, severity.upper(), fill=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(15)

    # --- 3. Redesigned Detailed Findings ---
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(241, 245, 249)
    pdf.cell(0, 10, "  Detailed Findings", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.ln(5)
    
    results = scan.get("results", {})
    scan_type = scan['data_type']

    has_findings = any(
        (isinstance(res.get("data"), list) and res["data"]) or 
        (isinstance(res.get("data"), dict) and res["data"]) 
        for res in results.values() if isinstance(res, dict)
    )
    
    if not has_findings:
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 7, "  No specific leaks or exposures were found in this scan.")
        pdf.ln(5)

    # --- START OF COMPREHENSIVE RENDERERS ---

    # TruffleHog Renderer (github_repo)
    trufflehog_result = results.get('trufflehog', {})
    if isinstance(trufflehog_result, dict) and isinstance(trufflehog_result.get("data"), list) and trufflehog_result["data"]:
        findings = trufflehog_result["data"]
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "-> Secret Leak Scan (TruffleHog)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, f"  Summary: Found {len(findings)} potential secret(s) exposed in the code.")
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(45, 7, "Secret Type", 1, align="C")
        pdf.cell(110, 7, "File Location", 1, align="C")
        pdf.cell(20, 7, "Line #", 1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8)
        for finding in findings[:10]:
            metadata = finding.get("SourceMetadata", {}).get("Data", {}).get("Github", {})
            detector, file, line = finding.get('DetectorName', 'N/A'), metadata.get('file', 'N/A'), metadata.get('line', 'N/A')
            display_detector = detector[:22] + "..." if len(detector) > 25 else detector
            display_file = "..." + file[-67:] if len(file) > 70 else file
            pdf.cell(45, 6, display_detector, 1)
            pdf.cell(110, 6, display_file, 1)
            pdf.cell(20, 6, str(line), 1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if len(findings) > 10:
            pdf.set_font("Helvetica", "I", 8) # Italic font
            pdf.cell(0, 6, f"...and {len(findings) - 10} more findings. See the web view for the full list.", 1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(8)

    # HIBP (Email Breaches) Renderer
    hibp_result = results.get('hibp_emails', {})
    if isinstance(hibp_result, dict) and isinstance(hibp_result.get("data"), list) and hibp_result["data"]:
        breaches = hibp_result["data"]
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "-> Email Breach Check (Have I Been Pwned)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, f"  Summary: This email was found in {len(breaches)} public data breaches.")
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(65, 7, "Breach Name", 1, align="C")
        pdf.cell(110, 7, "Types of Data Compromised", 1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8)
        for breach in breaches[:10]:
            name, data_classes = breach.get("Name", "N/A"), ", ".join(breach.get("DataClasses", []))
            display_name = name[:37] + "..." if len(name) > 40 else name
            display_data = data_classes[:72] + "..." if len(data_classes) > 75 else data_classes
            start_y = pdf.get_y()
            pdf.multi_cell(65, 6, display_name, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
            y_after_left = pdf.get_y()
            pdf.set_xy(pdf.get_x(), start_y)
            pdf.multi_cell(110, 6, display_data, border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            y_after_right = pdf.get_y()
            pdf.set_y(max(y_after_left, y_after_right))
        pdf.ln(8)

    # Sherlock (Usernames) Renderer
    sherlock_result = results.get('sherlock', {})
    if isinstance(sherlock_result, dict) and isinstance(sherlock_result.get("data"), list) and sherlock_result["data"]:
        urls = sherlock_result["data"]
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "-> Username & Social Media Scan (Sherlock)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, f"  Summary: Found {len(urls)} social media or forum profiles with this username.")
        pdf.ln(4)
        for url in urls[:10]:
            platform = tldextract.extract(url).domain.capitalize()
            pdf.set_font("Helvetica", "B", 9)
            pdf.multi_cell(0, 5, f"  - Platform: {platform}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 8)
            pdf.multi_cell(0, 5, f"    URL: {url}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
        pdf.ln(8)

    # Google Dork (Phone/IC) Renderer
    google_result = results.get('google_dork', {})
    if isinstance(google_result, dict) and isinstance(google_result.get("data"), list) and google_result["data"]:
        findings = google_result["data"]
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "-> Public Web Scan (Google)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, f"  Summary: Found {len(findings)} public source(s) mentioning this data.")
        pdf.ln(4)
        for finding in findings[:10]:
            source_url = finding.get('source_url', 'N/A')
            pdf.set_font("Helvetica", "B", 9)
            pdf.multi_cell(0, 5, "  - Source URL:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 8)
            pdf.multi_cell(0, 5, f"    {source_url}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
        pdf.ln(8)

    # HIBP (Passwords) Renderer
    hibp_pass_result = results.get('hibp_passwords', {})
    if isinstance(hibp_pass_result, dict) and isinstance(hibp_pass_result.get("data"), dict) and hibp_pass_result["data"]:
        data = hibp_pass_result["data"]
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "-> Password Breach Check (HIBP)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if data.get("pwned"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(198, 40, 40)
            pdf.multi_cell(0, 5, f"  Status: UNSAFE. This password was found {data.get('count', 0):,} times in public data breaches.")
        else:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(46, 125, 50)
            pdf.multi_cell(0, 5, "  Status: SAFE. This password was not found in any public data breaches.")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(8)


    # --- 4. Actionable Recommendations Page ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Actionable Recommendations", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)

    playbook = get_playbook_for_scan(scan_type)

    # Risk Section
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(211, 47, 47)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "What is the Risk?", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)

    for line in playbook['risk'].split('\n'):
        if not line.strip():
            pdf.ln(3) # Add a small space for empty lines
            continue
        
        # This is the logic from the playbook, now applied here
        parts = line.split('**')
        is_bullet = line.strip().startswith("- ")
        if is_bullet:
            pdf.cell(5) # Indent for bullet
            pdf.write(5, "- ")
            line = line.strip()[2:] # Remove bullet syntax
            parts = line.split('**') # Re-split after removing bullet

        for i, part in enumerate(parts):
            # Text is bold if it's an odd-indexed part
            is_bold = (i % 2 == 1)
            
            if is_bold:
                pdf.set_font("Helvetica", "B", 10)
            else:
                pdf.set_font("Helvetica", "", 10)
            pdf.write(5, part)
        pdf.ln(5) # Move to the next line
    pdf.ln(4)

    # Playbook Section
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(56, 142, 60)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "What Should I Do? (Your Playbook)", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
    pdf.ln(4)
    pdf.set_text_color(0, 0, 0)
    
    playbook_steps = playbook['playbook'].split('\n')
    for step in playbook_steps:
        match = re.match(r"^\s*(\d+)\.\s*(.*)", step)
        if match:
            number, text = match.groups()
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(5) # Small indent for the number
            pdf.cell(10, 5, f"{number}.")
            
            # Save current position to handle text wrapping correctly
            x_pos = pdf.get_x()
            y_pos = pdf.get_y()
            pdf.set_xy(x_pos, y_pos)

            # Use our new function to render the text part
            write_markdown_to_pdf(pdf, text)
        else:
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 6, step)
            pdf.ln(2)

    # --- NEW: 5. MALAYSIAN AUTHORITIES HELP SECTION ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Get Help from Malaysian Authorities", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5,
        "If your personal data has been exposed online, you can file official reports with the following Malaysian authorities to request takedowns and file formal complaints.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)

    # --- Authority 1: CyberSecurity Malaysia ---
    try:
        img_width = 50
        x_centered = (210 - img_width) / 2
        pdf.image("assets/cybersecurity_logo.png", x=x_centered, w=img_width)
        pdf.ln(2) 
    except FileNotFoundError:
        pdf.cell(0, 10, "[CyberSecurity Malaysia Logo]", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "CyberSecurity Malaysia (Cyber999)", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5,
        "Provides the Cyber999 Help Centre to report online security incidents, including data leaks, identity theft, and harassment.",
        align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(0, 5, "Report at: https://www.mycert.org.my/cyber999", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(15)

    # --- Authority 2: JPDP ---
    try:
        img_width = 50 
        x_centered = (210 - img_width) / 2
        pdf.image("assets/jpdp_logo.png", x=x_centered, w=img_width)
        pdf.ln(2)
    except FileNotFoundError:
        pdf.cell(0, 10, "[JPDP Logo]", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "Jabatan Perlindungan Data Peribadi (JPDP)", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5,
        "Handles violations of the Personal Data Protection Act (PDPA). File a complaint if you believe a company has misused or failed to protect your personal data.",
        align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(0, 5, "File a complaint at: https://www.pdp.gov.my/jpdpv2/ms/aduan/", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return pdf_to_bytes(pdf)

# HELPER FUNCTION TO RENDER SEVERITY BADGES
def render_severity_badge(severity: str):
    """Generates a styled HTML badge for a given severity level."""
    severity = severity.upper()
    severity_styles = {
        "CRITICAL": "background-color:#8B0000; color:white;",
        "HIGH": "background-color:#c62828; color:white;",
        "MEDIUM": "background-color:#f9a825; color:black;",
        "LOW": "background-color:#2e7d32; color:white;",
    }
    style = severity_styles.get(severity, "background-color:#546e7a; color:white;")
    
    return f"<span style='{style} padding: 5px 12px; border-radius:15px; font-size:0.9rem; font-weight:bold;'>{severity.capitalize()}</span>"


# --- HELPER FUNCTION TO CALCULATE OVERALL SEVERITY ---
def calculate_overall_severity(scan_type: str, results: dict) -> str | None:
    """Calculates a single severity level based on the scan type and its results."""
    
    # --- CRITICAL SEVERITY ---
# --- HELPER FUNCTION TO CALCULATE OVERALL SEVERITY ---
def calculate_overall_severity(scan_type: str, results: dict) -> str | None:
    """Calculates a single severity level based on the scan type and its results."""
    
    # --- CRITICAL SEVERITY ---
    if scan_type == 'password':
        hibp_result = results.get('hibp_passwords', {})
        if isinstance(hibp_result, dict) and hibp_result.get("data", {}).get("pwned", False):
            return "CRITICAL"

    if scan_type == 'github_repo':
        trufflehog_result = results.get('trufflehog', {})
        if isinstance(trufflehog_result, dict) and trufflehog_result.get("data"):
            return "CRITICAL"

    # --- HIGH SEVERITY ---
    if scan_type == 'email':
        hibp_result = results.get('hibp_emails', {})
        if isinstance(hibp_result, dict) and hibp_result.get("data"):
            return "HIGH"

    if scan_type in ('phone', 'ic'):
        google_result = results.get("google_dork", {})
        if isinstance(google_result, dict) and google_result.get("data"):
            return "HIGH"
        
    # --- MEDIUM SEVERITY ---
    if scan_type == 'full_name':
        google_result = results.get("google_dork", {})
        if isinstance(google_result, dict) and google_result.get("data"):
            return "MEDIUM"

    # --- LOW SEVERITY ---
    if scan_type == 'username':
        sherlock_result = results.get('sherlock', {})
        # This is now the ONLY check for username scans.
        if isinstance(sherlock_result, dict) and sherlock_result.get("data"):
            return "LOW"
            

    return None
# --- Google Custom Search (Google Dork) friendly display ---
def render_google_results_block(results, scan_type, search_data):
    """
    Renders a much-improved, context-aware block for Google Custom Search results.
    - Shows hit counts and pills for Phone/IC scans.
    - Highlights the search term for Full Name/Username scans.
    """
    google_result = results.get("google_dork")
    google_list = google_result.get("data", []) if isinstance(google_result, dict) else []

    if not google_list:
        st.info("✅ No public web mentions were found by Google for this data.")
        return

    st.markdown("### 🔎 Public Web Findings (Google)")
    st.info(f"Found **{len(google_list)}** potential source(s) mentioning this data.")

    for result in google_list:
        with st.container(border=True):
            source_url = result.get('source_url', 'N/A')
            snippet = result.get('snippet', 'No snippet available.').strip()

            # Display the source URL first for clarity
            st.markdown(f"🔗 **Source:** [{source_url}]({source_url})")

            # --- Context-Aware Display ---
            if scan_type in ('phone', 'ic'):
                # For Phone/IC, display the structured "pills" and hit count
                matches = result.get("matches", {}) or {}
                ic_matches = matches.get("ic_numbers", []) or []
                phone_matches = matches.get("phone_numbers", []) or []
                total_hits = len(ic_matches) + len(phone_matches)

                st.markdown(f"**Hits Found in Snippet:** {total_hits}")
                if phone_matches:
                    st.markdown(f"**Phone:** `{'`, `'.join(phone_matches)}`")
                if ic_matches:
                    st.markdown(f"**IC:** `{'`, `'.join(ic_matches)}`")
                
                # Display the original snippet for context
                st.markdown(f"> *{snippet}*")

            elif scan_type in ('full_name', 'username'):
                # For Full Name/Username, highlight the search term in the snippet
                try:
                    # Use regex to find and bold all case-insensitive matches of the search data
                    highlighted_snippet = re.sub(
                        f"({re.escape(search_data)})",
                        r"**\1**",  # Wrap the found group in Markdown bold
                        snippet,
                        flags=re.IGNORECASE
                    )
                    st.markdown(f"> {highlighted_snippet}", unsafe_allow_html=True)
                except re.error:
                    # Fallback in case of a regex error with a weird name
                    st.markdown(f"> *{snippet}*")



# --- BACKEND CONNECTION TEST ---
try:
    requests.get(f"{BACKEND_URL}/health", timeout=2)
except Exception:
    pass # Keep it silent


# --- 1. AUTHENTICATION HANDLING ---
# This runs on every page load to catch the redirect from Auth0
handle_auth_redirect()

# --- 2. DEFINE PUBLIC AND PRIVATE PAGES ---
PUBLIC_PAGES = ["Homepage", "Scanner", "Scan History", "About Tools", "FAQ"]
PRIVATE_PAGES = ["Dashboard", "Monitoring"]

# --- 3. SETUP SIDEBAR AND NAVIGATION (ALWAYS VISIBLE) ---
with st.sidebar:
    # --- DYNAMICALLY DISPLAY USER INFO OR LOGIN PROMPT ---
    if 'user' in st.session_state:
        user = st.session_state['user']
        st.header(f"Welcome, {user.get('name', 'User').split()[0]}!")
        st.write(f"Logged in as: {user.get('email')}")
        
        if st.button("Logout"):
            del st.session_state['user']
            st.rerun()
    else:
        st.header("Welcome, Guest!")
        st.markdown("Sign in to access your personalized dashboard and reports.")
        auth_url = get_authorization_url()
        st.link_button("Sign in ", auth_url, use_container_width=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<h1 style='color:#2c3e50; text-align:center; font-size: 1.5rem;'>MENU</h1>", unsafe_allow_html=True)
    
    # --- NAVIGATION MENU ---
    selected = option_menu(
        menu_title=None,
        options=["Homepage", "Scanner", "Dashboard", "Scan History", "Monitoring", "About Tools", "FAQ"],
        icons=["house-door", "search", "bar-chart-line", "clock-history", "bell", "tools", "question-circle"],
        default_index=0,
        styles={
            "container": {"padding": "0 !important", "background-color": "transparent"},
            "icon": {"color": "#f39c12", "font-size": "1.1rem"},
            "nav-link": {
                "font-size": "0.95rem", "text-align": "left", "margin": "4px", "padding": "10px",
                "color": "#343A40", "background-color": "#FFFFFF", "border-radius": "8px"
            },
            "nav-link-selected": {"background-color": "#f39c12", "color": "#FFFFFF", "font-weight": "bold"},
        }
    )

# --- 4. PAGE ROUTING AND CONTENT RENDERING ---

# --- Check if the selected page is private and if the user is logged out (Authorization)---
is_private_page = selected in PRIVATE_PAGES
is_logged_in = 'user' in st.session_state

if is_private_page and not is_logged_in:
    # If a non-logged-in user tries to access a private page, show the login prompt
    st.header(f"🔒 Access Denied: {selected}")
    display_login_prompt()

else:
    # --- Render the selected page (either public, or private for a logged-in user) ---
    if selected == "Scanner":
        st.header("🔍 Data Leakage Scanner")
        st.markdown("Select a data type and provide the information to scan across all integrated OSINT platforms.")

        with st.container(border=True):
            col1, col2 = st.columns([1, 2], gap="large")

            # --- Column 1: The controlling widget, placed OUTSIDE the form ---
            with col1:
                st.subheader("1. Select Data Type")
                data_type = st.selectbox(
                    label="Choose the type of data to scan for:",
                    options=list(backend_data_type_map.keys()),
                    label_visibility="collapsed",
                    help="Select the type of data you want to scan for leaks."
                )

            # --- Column 2: The entire form is placed here ---
            with col2:
                # The form starts here, encapsulating everything that needs to be submitted
                with st.form(key="scan_form"):
                    help_messages = {
                        "Email Address": "Check if your email has been leaked in public data breaches. E.g., user@example.com",
                        "Password": "Check if a password has been exposed in a data breach. The password is not sent to any server.",
                        "Phone Number": "Find out if your phone number is exposed in public sources. E.g., 0123456789, 012-3456789 or +60123456789",
                        "Username": "Scan the internet for social media and forum accounts matching a username. E.g., testuser123",
                        "IC Number": "Monitor Malaysian IC number exposure. E.g., 990101-14-1234 or 990101141234",
                        "Full Name": "Find where your full name is mentioned on public websites, documents, and lists. E.g., Mohd Ali Bin Abu",
                        "GitHub Repository": "Scan an entire public GitHub repository for any exposed secrets. E.g., https://github.com/user/repository",
}
                    
                    placeholder_examples = {
                        "Email Address": "e.g., user@example.com",
                        "Password": "Enter a password to check its exposure",
                        "Phone Number": "e.g., 0123456789, 012-3456789 or +60123456789",
                        "Username": "e.g., testuser123",
                        "IC Number": "e.g., 990101-14-1234 or 990101141234",
                        "Full Name": "e.g., Mohd Ali Bin Abu",
                        "GitHub Repository": "e.g., https://github.com/user/repository",
                    }

                    # The input widget is now correctly inside the form
                    if data_type == "Password":
                        search_data = st.text_input(
                            label="2. Provide Input Data",
                            type="password",
                            placeholder=placeholder_examples.get(data_type, "Enter data to search..."),
                            help=help_messages.get(data_type)
                        )
                    else:
                        search_data = st.text_input(
                            label="2. Provide Input Data",
                            placeholder=placeholder_examples.get(data_type, "Enter data to search..."),
                            help=help_messages.get(data_type)
                        )

                    st.markdown("<hr style='border: 1px solid #E0E0E0;'>", unsafe_allow_html=True)
                    
                    # The submit button is also inside the form
                    scan_button = st.form_submit_button("🚀 Start Comprehensive Scan", use_container_width=True)

        # --- The submission logic block ---
        if scan_button:
            if search_data:
                # 1. Validate the user's input
                pattern = regex_patterns[data_type]
                backend_data_type = backend_data_type_map[data_type]
                
                if not re.search(pattern, search_data.strip()):
                    st.error(f"❌ Input does not match the expected {data_type} format. Please check and try again.", icon="🚨")
                else:
                    # --- THIS IS THE CLEANED-UP LOGIC ---
                    # Show a single, clear message BEFORE making the request.
                    if data_type in ["Username", "GitHub Repository", "Email Address"]:
                        st.info(f"✅ Scan for **{data_type}** initiated. This may take several minutes. You can safely navigate to other pages, and the results will appear in 'Scan History' when ready.", icon="⏳")
                    else:
                        st.success("✅ Scan initiated successfully! Please go to the 'Scan History' page to see the results shortly.", icon="🚀")
                    
                    # Prepare the data for the scan
                    payload = {"data_type": backend_data_type, "search_data": search_data.strip()}
                    
                    if 'user' in st.session_state:
                        payload['user_id'] = st.session_state['user'].get('sub')
                    
                    try:
                        # Make the request to the backend
                        response = requests.post(f"{BACKEND_URL}/scan/start", json=payload, timeout=10)

                        if response.status_code == 202:
                            scan_id = response.json().get("scan_id")
                            if 'user' not in st.session_state:
                                st.session_state['last_guest_scan_id'] = scan_id
                            # We add a small sleep to ensure the message is visible before the form clears.
                            time.sleep(2)
                        else:
                            # If the request fails, we clear the positive message and show an error.
                            st.empty()
                            st.error(f"Failed to start scan. Server responded with: {response.status_code} - {response.text}")

                    except requests.exceptions.RequestException as e:
                        # Clear the positive message and show a connection error.
                        st.empty()
                        st.error(f"❌ Could not connect to the backend: {e}", icon="🔥")
                    # --- END OF CLEANUP ---

            else:
                st.warning("⚠️ Please enter data to search before starting a scan.", icon="❗️")

        render_footer()

    # --- NEW: SECURITY DASHBOARD PAGE ---
    elif selected == "Dashboard":
        st.header("📈 Security Dashboard")
        st.markdown("A high-level, aggregated, and visual overview of your overall security risk based on all historical scans.")

        with st.spinner("Loading dashboard..."):
            scans = get_scan_history() # Use the cached function

            if scans is None:
                # Error is already displayed by the function, so we do nothing.
                pass
            elif not scans:
                st.info("No scan history found. Run a scan from the 'Scanner' page to build your dashboard.", icon="ℹ️")
            else:
                    # --- A. EXECUTIVE SUMMARY DASHBOARD ---
                    st.subheader("Executive Summary")

                    # --- 1. Calculate KPIs ---
                    total_scans = len(scans)
                    all_findings = []
                    leaks_by_type = {}

                    for scan in scans:
                        severity = calculate_overall_severity(scan['data_type'], scan.get('results', {}))
                        if severity:
                            display_type = display_name_map.get(scan['data_type'], scan['data_type'].capitalize())
                            all_findings.append({
                                "severity": severity,
                                "data_type": display_type,
                                "search_data": scan['search_data'],
                                "timestamp": datetime.fromisoformat(scan["timestamp"])
                            })
                            leaks_by_type[display_type] = leaks_by_type.get(display_type, 0) + 1

                    total_leaks = len(all_findings)

                    # --- 2. Display Key Metrics (KPIs) ---
                    kpi_cols = st.columns(3)
                    kpi_cols[0].metric(label="Total Scans Performed", value=total_scans)
                    kpi_cols[1].metric(label="Total Leaks Found", value=total_leaks)
                    critical_leaks = sum(1 for f in all_findings if f['severity'] == 'CRITICAL')
                    kpi_cols[2].metric(label="Critical Leaks", value=critical_leaks, delta_color="inverse")

                    st.markdown("---")

                    # --- 3. Create Charts ---
                    chart_cols = st.columns(2)
                    
                    # Pie Chart: Leaks by Severity
                    with chart_cols[0]:
                        st.markdown("<h5>Leaks by Severity</h5>", unsafe_allow_html=True)
                        if all_findings:
                            severity_counts = pd.DataFrame(all_findings)['severity'].value_counts().reset_index()
                            severity_counts.columns = ['severity', 'count']
                            
                            # Define a color map for consistent styling
                            color_map = {'CRITICAL': '#8B0000', 'HIGH': '#c62828', 'MEDIUM': '#f9a825', 'LOW': '#2e7d32'}

                            fig_pie = px.pie(severity_counts, 
                                        names='severity', 
                                        values='count',
                                        color='severity',
                                        color_discrete_map=color_map,
                                        hole=.3)
                            fig_pie.update_layout(margin=dict(l=0, r=0, t=20, b=20), legend_title_text='Severity')
                            st.plotly_chart(fig_pie, use_container_width=True)
                        else:
                            st.info("No leaks found to display severity distribution.")

                    # Bar Chart: Leaks by Type
                    with chart_cols[1]:
                        st.markdown("<h5>Leaks by Data Type</h5>", unsafe_allow_html=True)
                        if leaks_by_type:
                            type_df = pd.DataFrame(list(leaks_by_type.items()), columns=['Data Type', 'Count']).sort_values('Count', ascending=False)
                            fig_bar = px.bar(type_df, 
                                        x='Data Type', 
                                        y='Count',
                                        text='Count',
                                        color_discrete_sequence=['#f39c12'])
                            fig_bar.update_traces(textposition='outside')
                            fig_bar.update_layout(margin=dict(l=0, r=0, t=20, b=20), yaxis_title=None, xaxis_title=None)
                            st.plotly_chart(fig_bar, use_container_width=True)
                        else:
                            st.info("No leaks found to display by data type.")
                    
                    st.markdown("---")

                    # --- 4. Most Recent Critical Findings Table ---
                    st.subheader("Recent High-Priority Findings")
                    critical_high_findings = sorted(
                        [f for f in all_findings if f['severity'] in ['CRITICAL', 'HIGH']],
                        key=lambda x: x['timestamp'],
                        reverse=True
                    )

                    if not critical_high_findings:
                        st.success("✅ No recent 'Critical' or 'High' severity leaks found. Keep up the great work!", icon="🛡️")
                    else:
                        display_findings = []
                        for f in critical_high_findings[:5]: # Display top 5
                            display_findings.append({
                                "Severity": f['severity'],
                                "Data Type": f['data_type'],
                                "Leaked Data": f['search_data'],
                                "Date Found": f['timestamp'].strftime("%d %b %Y, %I:%M %p")
                            })
                        
                        df_display = pd.DataFrame(display_findings)

                        # Custom styling for the severity column
                        def style_severity(val):
                            color = {'CRITICAL': '#c62828', 'HIGH': '#e67e22'}.get(val, 'black')
                            return f'color: {color}; font-weight: bold;'

                        st.dataframe(
                            df_display.style.map(style_severity, subset=['Severity']),
                            use_container_width=True,
                            hide_index=True
                        )
        render_footer() 

    elif selected == "Scan History":
        st.header("📊 Scan History")
        st.markdown("Review the enriched findings from your recent scans. Results from multiple tools are combined for better insights.")
        
        with st.spinner("Loading scan history..."):
            scans = get_scan_history() # Use the cached function we created earlier

            if scans is None:
                # The function already showed an error, so we do nothing here.
                pass
            elif not scans:
                st.info("No scan history found. Run a scan from the 'Scanner' page to see results here.", icon="ℹ️")
            else:

                for scan in scans:
                    display_data_type = display_name_map.get(scan['data_type'], scan['data_type'].capitalize())
                    icon = "👤" 
                    source_text = "Manual Scan"
                    
                    # Check if the scan source is automated and update the icon/text
                    if scan.get('scan_source') == 'automated':
                        icon = "🤖"
                        source_text = "Automated Scan"
                    
                    expander_title = f"{icon} {source_text} | ID: {scan['scan_id']} | Type: {display_data_type} | Data: '{scan['search_data']}'"
                    
                    with st.expander(expander_title, expanded=False):
                        # --- Timestamp and Status ---
                        dt = datetime.fromisoformat(scan["timestamp"]).replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kuala_Lumpur"))
                        try:
                            locale.setlocale(locale.LC_TIME, "en_US.utf8")
                        except locale.Error:
                            locale.setlocale(locale.LC_TIME, "")
                        formatted_date = dt.strftime("%d %B %Y, %I:%M %p")
                        
                        results = scan.get("results", {})
                        severity = calculate_overall_severity(scan['data_type'], results)

                        # --- NEW: Create a compact summary bar with columns ---
                        col1, col2 = st.columns([3, 1])

                        with col1:
                            st.markdown(f"**🕒 Timestamp:** {formatted_date} | **Status:** `{scan['status']}`")
                            if severity:
                                st.markdown(f"**Overall Severity:** {render_severity_badge(severity)}", unsafe_allow_html=True)

                        with col2:
                            try:
                                # Attempt to generate the PDF data as before
                                pdf_data = generate_scan_report_pdf(scan, display_name_map)
                                fname = f"Leakage_Report_{scan['scan_id']}_{safe_filename(scan['search_data'])}.pdf"
                                
                                # Display the download button
                                st.download_button(
                                    label="📥 Download Report (PDF)",
                                    data=pdf_data,
                                    file_name=fname,
                                    mime="application/pdf",
                                )
                            except TypeError as e:
                                # --- THIS IS THE NEW, DETAILED LOGGING BLOCK ---
                                if "unhashable type: 'slice'" in str(e):
                                    st.error("Caught the specific 'unhashable type: slice' PDF error. Please provide the details below for a final fix.", icon="🚨")
                                    
                                    # Create a detailed error report
                                    error_details = {
                                        "error_message": str(e),
                                        "error_type": type(e).__name__,
                                        "traceback": traceback.format_exc(),
                                        "problematic_scan_object": scan  # This is the crucial part
                                    }
                                    
                                    # Display the detailed report in the Streamlit app
                                    with st.expander("Click to view detailed error log"):
                                        # Use json.dumps for a clean, readable print of the dictionary
                                        st.code(json.dumps(error_details, indent=2), language="json")
                                else:
                                    # For any other TypeError, show a generic message
                                    st.error(f"PDF Generation Error: {e}", icon="🚨")
                            except Exception as e:
                                # For any other general exception
                                st.error(f"An unexpected PDF error occurred: {e}", icon="🚨")# Shortened error for compact layout
                        
                        st.markdown("---")

                        

                        # --- ENRICHED/CONSOLIDATED VIEWS ---

                        # 1. ENRICHED USERNAME VIEW
                        if scan['data_type'] == 'username':
                            st.markdown("### 🕵️ Username Footprint & Exposure Analysis")
                            
                            sherlock_result = results.get('sherlock', {})
                            google_result = results.get('google_dork', {})
                            
                            # --- Section 1: Sherlock for Digital Footprint ---
                            st.subheader("Social Media Presence (Digital Footprint)")
                            if isinstance(sherlock_result, dict) and isinstance(sherlock_result.get("data"), list) and sherlock_result["data"]:
                                sherlock_data = sherlock_result["data"]
                                st.metric(label="Public Profiles Found", value=len(sherlock_data))
                                st.info("These are public profiles you likely created. The risk comes from attackers combining information from them.", icon="👤")
                                for url in sherlock_data:
                                    ext = tldextract.extract(url)
                                    platform = ext.domain.capitalize()
                                    st.markdown(f"🔗 **{platform}:** [{url}]({url})")
                            else:
                                st.success("✅ No public social profiles were found by Sherlock.")

                            st.markdown("---")

                            # --- Section 2: Google for Unintentional Leaks ---
                            st.subheader("Public Web Mentions (Potential Leaks)")
                            render_google_results_block(results, scan['data_type'], scan['search_data'])

                            # --- Section 3: Combined Risk & Playbook ---
                            # Show this section if either tool found something.
                            if (isinstance(sherlock_result, dict) and sherlock_result.get("data")) or \
                               (isinstance(google_result, dict) and google_result.get("data")):
                                
                                st.markdown("---")
                                st.error("🚨 What is the Risk?", icon="🤔")
                                st.markdown("""
                                Your username analysis has two parts:
                                - **Digital Footprint (Social Media):** Attackers can combine information from your public profiles (interests, location, friends) to build a detailed picture of you for targeted phishing scams or to guess security questions.
                                - **Potential Leaks (Web Mentions):** If your username was found on public forums or documents, it could be part of an unintentional data leak. This is higher risk as it exposes your username in contexts you did not intend.
                                """)

                                st.info("✅ What Should I Do? (Your Playbook)", icon="🛡️")
                                st.markdown("""
                                1.  **For Social Media Profiles:** Click the links and review what is publicly visible. Remove sensitive details (phone number, full birthdate) and tighten your privacy settings on each site from "Public" to "Friends Only".
                                2.  **For Public Web Mentions:** Investigate the source links found by the web scan. If they contain sensitive information, contact the website administrator and request a takedown. If it's a post you made, log in and delete it.
                                """)
                            else:
                                st.info("No Sherlock results available for this scan.")


                        # 2. ENRICHED EMAIL VIEW
                        elif scan['data_type'] == 'email':
                            st.markdown("### 📧 Email Exposure Analysis")
                            
                            # --- Part 1: Display HIBP results with corrected logic ---
                            hibp_result = results.get('hibp_emails', {})
                            hibp_data = hibp_result.get("data", []) if isinstance(hibp_result, dict) else []
                            
                            st.subheader("Data Breach Exposure (from HIBP)")
                            if hibp_data:
                                st.metric(label="Found In", value=f"{len(hibp_data)} Breaches")
                                st.error("This email was found in the databases of past company data breaches.", icon="🔥")
                                for breach in hibp_data:
                                    with st.container(border=True):
                                        st.subheader(breach.get("Name", "Unknown Breach"))
                                        tags_html = "".join([f"<span style='background-color:#ffebee; color:#c62828; padding: 3px 8px; border-radius:12px; margin-right:5px; font-size:0.85rem;'>{item}</span>" for item in breach.get("DataClasses", [])])
                                        st.markdown(f"**Compromised Data:** {tags_html}", unsafe_allow_html=True)
                            else:
                                st.success("✅ Good News! This email was not found in any of the public data breaches checked by HIBP.")

                            # --- Part 2: Display Google Search results (this part is the same) ---
                            st.markdown("---")
                            st.subheader("Where Your Email is Publicly Visible (from Google Search)")
                            st.info("""
                            **What is this?** Unlike data breaches, the results below show where your email is **currently visible** on public websites.
                            """, icon="💡")
                            
                            google_result = results.get("google_dork", {})
                            google_list = google_result.get("data", []) if isinstance(google_result, dict) else []
                            render_google_results_block(results, scan['data_type'], scan['search_data'])

                            # --- Part 3: Combined Risk & Playbook with corrected logic ---
                            if hibp_data or google_list:
                                st.markdown("---")
                                st.error("🚨 What is the Risk?", icon="🤔")
                                st.markdown("""
                                Your email address has been exposed, which creates two primary risks:
                                - **From Data Breaches:** Criminals can use the leaked passwords from these breaches to try and take over your other accounts (like email, social media, and banking).
                                - **From Public Exposure:** Your email can be collected by spammers and scammers, leading to a significant increase in targeted phishing attacks and unwanted junk mail.
                                """)

                                st.info("✅ What Should I Do? (Your Playbook)", icon="🛡️")
                                st.markdown("""
                                1.  **Change Passwords Immediately:** If your email was in a breach, change the password on that site and any other site where you reused it.
                                2.  **Enable Two-Factor Authentication (2FA):** This is your best defense against account takeover.
                                3.  **Remove Public Postings:** For any results found by the web scan, visit the links and delete or request removal of your email address.
                                4.  **Be Vigilant:** Be extra suspicious of any unexpected emails that ask you to click links or provide personal information.
                                """)
                            else:
                                st.info("No HIBP results available for this scan.")
                                                
                        
                        # 4. PHONE & IC VIEW
                        elif scan['data_type'] in ("phone", "ic", "full_name"):
                            # NEW: Conditional title and icon based on the specific data type
                            if scan['data_type'] == 'ic':
                                st.markdown("### 🪪 Public Exposure Analysis")
                            elif scan['data_type'] == 'full_name': # <--- ADD THIS LINE
                                st.markdown("### 👤 Public Exposure Analysis") # <--- ADD THIS LINE
                            else:
                                st.markdown("### 📞 Public Exposure Analysis")

                            render_google_results_block(results, scan['data_type'], scan['search_data'])
                            google_result = results.get("google_dork", {})
                            google_list = google_result.get("data", []) if isinstance(google_result, dict) else []

                            if google_list:
                                playbook = get_playbook_for_scan(scan['data_type'])
                                st.markdown("---")
                                st.error("🚨 What is the Risk? (HIGH)", icon="🔥")
                                st.markdown(playbook['risk'])

                                st.info("✅ What Should I Do? (Your Playbook)", icon="🛡️")
                                st.markdown(playbook['playbook'])
                                
                        elif scan['data_type'] == "github_repo":
                            st.markdown("### 🔑 GitHub Repository Exposure Analysis")
                            trufflehog_result = results.get('trufflehog', {})
                            
                            if isinstance(trufflehog_result, dict) and trufflehog_result.get("data"):
                                findings = trufflehog_result["data"]
                                st.metric(label="Secrets Found", value=len(findings), delta_color="inverse")
                                st.error(f"🚨 Found potential secret(s) exposed in this repository. Details below:", icon="🔥")

                                for finding in findings:
                                    # Safely extract the nested GitHub metadata
                                    github_meta = finding.get("SourceMetadata", {}).get("Data", {}).get("Github", {})
                                    
                                    secret = finding.get("Raw", "Not found")
                                    repo = github_meta.get("repository", "N/A")
                                    file = github_meta.get("file", "N/A")
                                    link = github_meta.get("link", "#")

                                    with st.container(border=True):
                                        st.markdown(f"**🔗 Source Repository:**")
                                        st.markdown(f"[{repo}]({repo})")
                                        
                                        st.markdown(f"**📄 File:** `{file}`")

                                        st.error("**🤫 Leaked Data:**")
                                        st.code(secret, language="text")

                                        st.markdown(f"**➡️ [Click here to view the exposed line on GitHub]({link})**")
                            else:
                                st.success("✅ No exposed secrets were found in this repository by our tools.")
                            
                            # --- CONTEXTUAL RISK ANALYSIS (This is still relevant) ---
                            st.markdown("---")
                            st.error("🚨 What is the Risk? (CRITICAL)", icon="🔥")
                            st.markdown("""
                            An exposed secret in a GitHub repository is a **CRITICAL** risk. It's like leaving the master key to your house, car, or business lying on the street. An attacker can use this key to:
                            - **Access and Steal Your Data:** Read, modify, or delete information from the associated service.
                            - **Impersonate You:** Perform actions on your behalf without your knowledge.
                            - **Incur Financial Costs:** If the key is for a cloud service (like AWS or Google Cloud), an attacker can use it to run expensive services, leaving you with a massive bill.
                            """)

                            st.info("✅ What Should I Do? (Your Playbook)", icon="🛡️")
                            st.markdown("""
                            **Act IMMEDIATELY. Every second counts.**
                            1.  **Identify the Leaked Key:** Determine which key was exposed and what service it belongs to.
                            2.  **Revoke the Key:** Log into the dashboard of that service and **revoke** or **delete** the compromised key. This is the most critical step.
                            3.  **Generate a New Key:** Create a new, replacement key.
                            4.  **Remove from History:** Remove the secret from the file and then use a tool like `git-filter-repo` or BFG Repo-Cleaner to erase it from the entire Git history. A simple commit is not enough.
                            5.  **Update Your Applications:** Replace the old, revoked key with the new one in all your applications.
                            """)
                        elif scan['data_type'] == "password":
                            st.markdown("### 🔑 Password Security Analysis")
                            hibp_result = results.get('hibp_passwords', {})
                            
                            if isinstance(hibp_result, dict) and isinstance(hibp_result.get("data"), dict):
                                with st.container(border=True):
                                    is_pwned = hibp_result["data"].get("pwned", False)
                                    count = hibp_result["data"].get("count", 0)
                                    if is_pwned:
                                        st.error("🚨 This Password is Unsafe", icon="🔥")
                                        st.metric(label="Found in Public Data Breaches", value=f"{count:,} times", delta_color="inverse")
                                        # --- CONTEXTUAL RISK ANALYSIS ---
                                        st.markdown("---")
                                        st.error("🚨 What is the Risk? (CRITICAL)", icon="🔥")
                                        st.markdown("""
                                        This is a **CRITICAL** risk. **DO NOT USE THIS PASSWORD.** It is publicly known and is on lists used by hackers. Using this password for any account is like leaving your front door wide open.
                                        - Attackers will use this password to try and log into your email, bank, and social media accounts (this is called "credential stuffing").
                                        - If they get into one account, they will use it to try and reset your passwords for other accounts.
                                        """)

                                        st.info("✅ What Should I Do? (Your Playbook)", icon="🛡️")
                                        st.markdown("""
                                        1.  **Stop Using This Password Immediately:** Identify every single online account where you are currently using this password.
                                        2.  **Change Your Passwords:** Go to each of those websites and change your password to a **new, unique, and strong** one. Do not reuse passwords across different sites.
                                        3.  **Use a Password Manager:** This is the best way to manage unique passwords. A password manager is a secure app that can generate and store very strong passwords for you, so you only have to remember one master password.
                                            *   **Popular and trusted options include Bitwarden (which has a great free version) and 1Password.**
                                        4.  **Enable Two-Factor Authentication (2FA):** Turn on 2FA everywhere possible. It provides a vital extra layer of security.
                                        """)
                                    else:
                                        st.success("✅ This Password Appears Safe", icon="🛡️")
                                        st.metric(label="Found in Data Breaches", value="0 times")
                            else:
                                st.info("No password check results available for this scan.")

        render_footer()


    # --- END OF THE CORRECTED AND FINAL "Scan History" BLOCK ---
    elif selected == "About Tools":
        st.header("🛠️ Our OSINT Arsenal")
        st.markdown("An overview of the powerful, open-source tools that drive our scanning engine.")
        tools_info = {
            "🔑 TruffleHog": { 
                "purpose": "Scans public GitHub repositories for exposed secrets.", 
                "scans": ["API Keys & Tokens", "Passwords & Private Keys"] 
            },
            "🌐 Google Custom Search": { 
                "purpose": "Uses targeted search queries to find data indexed on the public web.", 
                "scans": ["Full Name", "Phone Numbers", "IC Numbers"]
            },
            "🕵️ Sherlock": { 
                "purpose": "Hunts down social media and forum accounts by username.", 
                "scans": ["Social Media Profiles", "Forum Accounts"] 
            },
            "📧 HIBP API": { 
                "purpose": "Checks against a massive database of known public data breaches.", 
                "scans": ["Leaked Emails", "Exposed Passwords"] 
            }
        }
        for tool, info in tools_info.items():
            with st.expander(tool, expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Purpose:**")
                    st.markdown(f"<p style='color:#343A40;'>{info['purpose']}</p>", unsafe_allow_html=True)
                with col2:
                    st.markdown("**What it scans:**")
                    for item in info['scans']:
                        st.markdown(f"- {item}")
        st.markdown("---")
        
        st.subheader("⚙️ How Our Scanning Works")
        col1, col2, col3 = st.columns(3, gap="large")
        with col1:
            st.markdown("**1. Input Processing**")
            st.markdown("- Validates input\n- Selects tools")
        with col2:
            st.markdown("**2. Parallel Scanning**")
            st.markdown("- Runs tools simultaneously\n- Monitors progress")
        with col3:
            st.markdown("**3. Results Analysis**")
            st.markdown("- Aggregates findings\n- Removes duplicates")
        st.markdown("---")
        st.subheader("🔒 Security & Privacy")
        col1, col2 = st.columns(2, gap="large")
        with col1:
            st.markdown("**Data Protection:**")
            st.markdown("- Scans are encrypted\n- No permanent storage\n- Auto-delete results")
        with col2:
            st.markdown("**Ethical Scanning:**")
            st.markdown("- Public sources only\n- Respects limits\n- No illegal acts")
        render_footer()

    elif selected == "Monitoring":
        st.header("🛡️ Automated Monitoring")
        st.markdown("Add sensitive data here to have it automatically scanned on a regular schedule. You will be alerted to new findings.")

        # This page is protected, so we know 'user' is in st.session_state
        user_id = st.session_state['user'].get('sub') # Use 'sub' for a more permanent ID

        if not user_id:
            st.error("Could not identify user. Please try logging in again.")
        else:
            # --- Section for Alerts ---
            st.subheader("🚨 Recent Alerts")
            try:
                alert_res = requests.get(f"{BACKEND_URL}/monitoring/alerts/{user_id}")
                if alert_res.status_code == 200:
                    all_alerts = alert_res.json()
                    
                    # Filter for only unread alerts
                    unread_alerts = [alert for alert in all_alerts if not alert.get('is_read')]

                    # --- FIX 1: Check the correct variable ---
                    if not unread_alerts:
                        st.success("No new alerts. Your monitored assets look clear!", icon="✅")
                    else:
                        # --- FIX 2: Loop over the correct variable ---
                        for alert in unread_alerts:
                            alert_time = datetime.fromisoformat(alert['created_at']).replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kuala_Lumpur"))
                            formatted_time = alert_time.strftime("%d %b %Y, %I:%M %p")
                            
                            col1, col2 = st.columns([4, 1])
                            
                            with col1:
                                st.warning(f"**{formatted_time}:** {alert['message']} (Scan ID: {alert['scan_id']})")

                            with col2:
                                if st.button("Dismiss", key=f"dismiss_{alert['id']}", use_container_width=True):
                                    dismiss_res = requests.put(f"{BACKEND_URL}/monitoring/alerts/{alert['id']}/read")
                                    if dismiss_res.status_code == 200:
                                        st.rerun()
                                    else:
                                        st.error("Failed to dismiss alert.")
                else:
                    st.error("Could not fetch alerts.")
            except Exception as e:
                st.error(f"Error fetching alerts: {e}")

            st.markdown("---")

            # --- Section to add new assets ---
            st.subheader("Add New Asset to Monitor")
            # The form starts here. The logic that uses its variables MUST be inside.
            with st.form("add_asset_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    asset_type_display = st.selectbox(
                        "Select Data Type",
                        options=list(backend_data_type_map.keys()),
                        help="Choose the type of data you want to monitor."
                    )
                with col2:
                    asset_data = st.text_input(
                        "Enter Data",
                        help="Enter the email, username, etc., to monitor."
                    )

                submitted = st.form_submit_button("➕ Add to Monitoring List")

                # --- Code snippet for Accountability ---
                if submitted:
                    if asset_data:

                        pattern = regex_patterns[asset_type_display]
                        if not re.search(pattern, asset_data.strip()):
                            st.error(f"❌ Input does not match the expected {asset_type_display} format. Please check and try again.", icon="🚨")
                        else:
                            # This is the original logic, now nested in the 'else' block
                            st.success("✅ Input validated. Adding to monitoring list...", icon="👍")
                            payload = {
                                "user_id": user_id,
                                "data_type": backend_data_type_map[asset_type_display],
                                "search_data": asset_data.strip()
                            }
                            try:
                                response = requests.post(f"{BACKEND_URL}/monitoring/assets", json=payload)
                                if response.status_code == 201:
                                    st.success(f"Successfully added '{asset_data}' to the monitoring list!")
                                    st.rerun() # This will now work correctly
                                else:
                                    st.error(f"Failed to add asset: {response.text}")
                            
                            # This is now more specific and will NOT catch the rerun exception
                            except requests.exceptions.RequestException as e:
                                st.error(f"An error occurred while connecting to the backend: {e}")
                    else:
                        st.warning("Please enter the data to monitor.")
                   

            st.markdown("---")

            # --- Section to display and manage current assets ---
            st.subheader("Currently Monitored Assets")
            try:
                res = requests.get(f"{BACKEND_URL}/monitoring/assets/{user_id}")
                if res.status_code == 200:
                    assets = res.json()
                    
                    # --- START OF FIX 2: Added the indented block ---
                    if not assets:
                        st.info("You are not currently monitoring any assets.")
                    else:
                        for asset in assets:
                            col1, col2, col3, col4 = st.columns([2, 3, 2, 1])
                            with col1:
                                st.write(f"**{display_name_map.get(asset['data_type'], 'Unknown')}**")
                            with col2:
                                st.code(asset['search_data'])
                            with col3:
                                last_scan = "Never"
                                if asset.get('last_scanned_at'):
                                    # 1. Parse the string from the database into a datetime object
                                    dt_utc = datetime.fromisoformat(asset['last_scanned_at'])
                                    
                                    # 2. Tell Python that this datetime is in UTC
                                    dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
                                    
                                    # 3. Convert it to your local timezone
                                    dt_local = dt_utc.astimezone(ZoneInfo("Asia/Kuala_Lumpur"))
                                    
                                    # 4. Format the local time for display
                                    last_scan = dt_local.strftime("%d %b %Y, %I:%M %p")

                                    st.write(f"Last Scanned: {last_scan}")
                            with col4:
                                if st.button("Delete", key=f"del_{asset['id']}", use_container_width=True):
                                    del_res = requests.delete(f"{BACKEND_URL}/monitoring/assets/{asset['id']}")
                                    if del_res.status_code == 204:
                                        st.success("Asset removed.")
                                        st.rerun()
                                    else:
                                        st.error("Failed to remove asset.")
                    # --- END OF FIX 2 ---
                else:
                    st.error("Could not fetch monitored assets.")
            except Exception as e:
                st.error(f"Error fetching assets: {e}")
        render_footer() 

    elif selected == "FAQ":
        st.header("❓ Frequently Asked Questions")
        st.markdown("Find answers to common questions about our platform, security, and how to interpret your results.")
        # --- NEW CATEGORY ---
        st.subheader("🚨 Understanding Your Results")
        with st.expander("**What should I do if I find my data has been leaked?**", expanded=True): # Expanded by default
            st.markdown("""
            Finding your data has been exposed can be stressful, but taking swift action is key. Here are the recommended steps:
            - **1. Change Compromised Credentials:** If a password or username was leaked, change that password **immediately** on every site where you have used it. Prioritize critical accounts like email and banking.
            - **2. Revoke and Regenerate Keys:** If an API key or token was exposed, revoke it immediately in that service's dashboard and generate a new one.
            - **3. Enable Two-Factor Authentication (2FA):** For any affected account, enable 2FA (or MFA). This is one of the most effective ways to secure an account even if the password is known.
            """)
        with st.expander("**Why do some scans show “No Leaks Found” even if I suspect an exposure?**"):
            st.markdown("""
            There are a few reasons why a scan might not find something you suspect is out there:
            - **Not Yet Publicly Indexed:** The data leak may have occurred, but it might not have been discovered and indexed in the public breach databases that our tools scan.
            - **Outside Our Scan Scope:** The leak could be on a private forum, a marketplace on the dark web, or another source that our public-facing OSINT tools do not cover.
            - **Data Has Been Removed:** The exposed data may have been found and removed from the public site where it was posted (like Pastebin).
            We recommend rescanning periodically, as databases are constantly updated with new information.
            """)
        st.subheader("🛡️ Security & Privacy")
        with st.expander("**Is it safe to enter my password or API key here?**"):
            st.markdown("""
            **Yes.** We prioritize your security and privacy above all else. Here’s how we handle sensitive data:
            - **Passwords:** We **never** send your actual password to any server. We use a technique called "k-Anonymity" (the same model used by the trusted Have I Been Pwned service). This allows us to check for a breach without ever exposing the full password you entered.
            - **API Keys & Other Secrets:** Your input is saved to your private Scan History so you can review it later. This data is linked only to your user session, is never shared, and is **automatically and permanently deleted from our system after 14 days.**
            Our fundamental goal is to help you find *existing* public leaks, not create new ones.
            """)
        with st.expander("**Where does the system search for my data?**"):
            st.markdown("""
            The system scans **only publicly available sources**. This includes places like:
            - **Public Code Repositories:** Searching sites like GitHub for exposed API keys and secrets (via TruffleHog).
            - **Public Web Pages:** Using targeted searches to find indexed information on websites and public documents (via Google Custom Search).
            - **Social Media & Forums:** Searching for public profiles across hundreds of sites that match a username (via Sherlock).
            - **Known Data Breaches:** Checking against a large, aggregated database of credentials from past public breaches (via HIBP).

            We **do not** access private databases or systems. All scans are performed within the bounds of ethical open-source intelligence gathering.
            """)
        with st.expander("**Do you store my search history or results?**"):
            st.markdown("""
            Yes, the results of your scans are stored in a secure database so you can review them later in the **Scan History** tab. This data is linked only to your user session and is never made public or shared.

            To protect your privacy, this data is not stored indefinitely. **All scan results are automatically and permanently deleted from our system after 14 days.**

            This 14-day period provides a convenient window for you to review your findings, while ensuring your search history is not retained long-term, prioritizing your security and privacy.
            """)
        with st.expander("**Is this service legal to use?**"):
            st.markdown("""
            **Yes.** This system exclusively uses **Open-Source Intelligence (OSINT)** tools and techniques. This means it only searches for, aggregates, and displays data that is **already publicly available** on the internet.
            It does not perform any hacking, cracking, or unauthorized access of any kind into private systems. It is a tool for discovering your public footprint, not for malicious activity.
            """)
        st.subheader("⚙️ Using the Scanner")
        with st.expander("**Why did my scan take a long time?**"):
            st.markdown("Some scans, especially for general data types like API keys, require searching vast sources like all of public GitHub. This can naturally take several minutes. Scans for more specific data types, like checking a password against a breach list, are usually much faster.")
        with st.expander("**What do I do if a tool returns an error?**"):
            st.markdown("Occasionally, a third-party service that a tool relies on may be temporarily unavailable. If you receive an error, we recommend waiting a few minutes and trying the scan again. If the problem persists, it may be an issue with the specific open-source tool itself.")
        render_footer() 

    elif selected == "Homepage":
        st.markdown("""
            <style>
                .step-container {
                    display: flex;
                    align-items: center;
                    background-color: #F8F9FA;
                    border-left: 5px solid #f39c12;
                    padding: 1rem;
                    margin-bottom: 1rem;
                    border-radius: 5px;
                }
                .pill {
                    display: inline-block;
                    margin: 4px 4px 4px 0;
                    padding: 5px 12px;
                    background-color: #e9ecef; /* A light gray that matches the sidebar */
                    color: #495057; /* A darker gray for the text */
                    border-radius: 15px;
                    font-size: 0.85rem;
                    font-weight: 500;
                }
                .step-icon {
                    font-size: 2.5rem;
                    margin-right: 1.5rem;
                }
                .step-text h4 {
                    margin-bottom: 0.2rem;
                    color: #2c3e50;
                }
                .step-text p {
                    margin-bottom: 0;
                    color: #495057;
                }
            </style>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div style='text-align: center; background: linear-gradient(135deg, #f39c12, #e67e22); border-radius:10px; padding: 2rem; margin-bottom:1.5rem;'>
                <h1 style='color: #FFFFFF;'>Is Your Digital Life Truly Private?</h1>
                <p style='color: #FFFFFF; font-size: 1.15rem;'>Let's explore what 'data leakage' means and how to protect the information you share online.</p>
            </div>
        """, unsafe_allow_html=True)

        # --- Section 1: What Exactly is a Data Leak? ---
        st.subheader("🤔 What Exactly is a Data Leak?")
        with st.expander("Imagine a data leak is like dropping your wallet in a crowded place... it's the digital version of that."):
            st.markdown("""
            It means your **private information** (like an email address, password, or phone number) has been unintentionally exposed on the public internet.

            Once it's out there, anyone—including criminals—can find and use it. This is why understanding your digital footprint is so important.
            """)
        st.markdown("---")

        # --- Section 2: How a Small Leak Becomes a Big Problem ---
        st.subheader("Domino Effect: How a Small Leak Becomes a Big Problem")
        st.info("Click on the tabs below to see how a single piece of your data can be exploited.")


        email_tab, phone_tab, password_tab = st.tabs(["**With Your Email Address**", "**With Your Phone Number**", "**With a Leaked Password**"])

        with email_tab:
            st.markdown("""
            <div class="step-container">
                <div class="step-icon">📧</div>
                <div class="step-text">
                    <h4>Step 1: They find your leaked email and password from a company's data breach.</h4>
                    <p>For example, a shopping website you used years ago gets hacked.</p>
                </div>
            </div>
            <div class="step-container">
                <div class="step-icon">🔑</div>
                <div class="step-text">
                    <h4>Step 2: They try that same email and password on other major websites.</h4>
                    <p>They hope you reused the password for your email, social media, or banking accounts.</p>
                </div>
            </div>
            <div class="step-container">
                <div class="step-icon">🎭</div>
                <div class="step-text">
                    <h4>Step 3: If they get in, they can lock you out, steal your identity, or scam your friends.</h4>
                    <p>This is called an "Account Takeover," and it's a very serious risk.</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with phone_tab:
            st.markdown("""
            <div class="step-container">
                <div class="step-icon">📱</div>
                <div class="step-text">
                    <h4>Step 1: A scammer finds your phone number and full name online.</h4>
                    <p>It might be publicly listed on a social media profile or an old website.</p>
                </div>
            </div>
            <div class="step-container">
                <div class="step-icon">🎣</div>
                <div class="step-text">
                    <h4>Step 2: They send you a very convincing text message (a "smishing" attack).</h4>
                    <p>The message might look like it's from your bank or a delivery service, asking you to click a link.</p>
                </div>
            </div>
            <div class="step-container">
                <div class="step-icon">💸</div>
                <div class="step-text">
                    <h4>Step 3: If you click the link, it might install malware or take you to a fake website to steal your login info.</h4>
                    <p>They can also use your number to target you with scam phone calls.</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with password_tab:
            st.markdown("""
            <div class="step-container">
                <div class="step-icon">🔓</div>
                <div class="step-text">
                    <h4>Step 1: Your password from an old account is exposed in a data breach.</h4>
                    <p>This password is now on public lists that hackers share and use.</p>
                </div>
            </div>
            <div class="step-container">
                <div class="step-icon">🤖</div>
                <div class="step-text">
                    <h4>Step 2: Hackers use software to automatically try that password on thousands of popular sites.</h4>
                    <p>This is called "Credential Stuffing." It's a fast and easy way for them to find your other accounts if you reuse passwords.</p>
                </div>
            </div>
            <div class="step-container">
                <div class="step-icon">🚨</div>
                <div class="step-text">
                    <h4>Step 3: Any account using that password is now at critical risk of being taken over.</h4>
                    <p>This highlights why using a unique password for every single account is so important.</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
       
        st.markdown("---")
        
        # --- Prominent Login for Guests ---
        if 'user' not in st.session_state:
            st.subheader("Ready to Check Your Own Digital Footprint?")
            with st.container(border=True):
                st.markdown("#### Sign in to use our free scanner.")
                st.markdown("You can check your email, username, phone number, and more against public data leaks. Get a private dashboard, view detailed reports, and receive simple advice to improve your security.")
                auth_url = get_authorization_url()
                st.link_button("Sign in to Scan Now", auth_url, use_container_width=True)
            st.markdown("---")
        
        # --- How to Protect Yourself Section (Now 4 Steps) ---
        st.subheader("🛡️ How You Can Protect Yourself: 4 Simple Steps")
        with st.expander("**Step 1: Use a Password Manager (Most Important)**"):
             st.markdown("""
            ✅ This is the single most effective thing you can do for your online security. A password manager creates and remembers strong, unique passwords for every site, so you don't have to.
            """)
        with st.expander("**Step 2: Enable Two-Factor Authentication (2FA)**"):
            st.markdown("""
            ✅ This is your security backup. It requires a code from your phone to log in. Even if a hacker has your password, they can't get into your account without your phone.
            """)
        with st.expander("**Step 3: Think Before You Click and Share**"):
            st.markdown("""
            ✅ This is about being careful. Be suspicious of urgent emails or texts, and check your social media privacy settings to avoid sharing sensitive data publicly.
            """)
        with st.expander("**Step 4 (Local Tip): Verify Accounts with 'Semak Mule'**"):
            st.markdown("""
            ✅ Before you transfer money to an unknown person or online seller, check their bank account or phone number on the PDRM's **Semak Mule portal**. It is a free, official tool that tells you if an account has been reported for scam activities.
            """)
            st.link_button("Check an Account on Semak Mule ➜", "https://semakmule.rmp.gov.my/")

        st.markdown("---")
        
        st.subheader("Local Threats: What to Watch Out For in Malaysia")
        st.markdown("Scammers often use your leaked personal data—like your phone number or name—as a starting point. Here are some of the common ways they exploit that information in Malaysia.")
        
        # --- ROW 1 of cards ---
        col1, col2 = st.columns(2, gap="large")

        with col1:
            with st.container(border=True):
                icon_col, title_col = st.columns([1, 5])
                with icon_col:
                    st.image("assets/stats.png", width=48)
                with title_col:
                    st.markdown("<h5><b>Fake Job & Investment Scams</b></h5>", unsafe_allow_html=True)

                st.markdown("""
                You get an unsolicited offer on WhatsApp for an easy, high-paying job. They pay you a little at first to build trust, then ask you to pay for an "upgrade" to earn more, which you will lose.
                
                **Remember:** Be wary of offers that seem too good to be true.
                """)

        with col2:
            with st.container(border=True):
                icon_col, title_col = st.columns([1, 5])
                with icon_col:
                    st.image("assets/Beware_ic.png", width=48)
                with title_col:
                    st.markdown("<h5><b>Your IC Number (MyKad)</b></h5>", unsafe_allow_html=True)
                
                st.markdown("""
                Scammers use your name and IC number to impersonate you or make their scams more convincing.
                
                **Remember:** Never post a photo of your MyKad online and only provide it to trusted, official organizations when absolutely necessary.
                """)

        # --- ROW 2 of cards ---
        col3, col4 = st.columns(2, gap="large")

        with col3:
            with st.container(border=True):
                icon_col, title_col = st.columns([1, 5])
                with icon_col:
                    st.image("assets/phone_scam.png", width=48)
                with title_col:
                    st.markdown("<h5><b>Impersonation Phone Scams</b></h5>", unsafe_allow_html=True)
                
                st.markdown("""
                Scammers often pretend to be from LHDN, PDRM, or PosLaju, claiming you owe taxes or are linked to a crime.

                **Remember:** Authorities **NEVER** ask for money transfers to personal accounts over the phone. If a call feels wrong, hang up and call their official hotline.
                """)

        with col4:
            with st.container(border=True):
                icon_col, title_col = st.columns([1, 5])
                with icon_col:
                    st.image("assets/otp.png", width=48)
                with title_col:
                    st.markdown("<h5><b>The TAC / OTP Code Scam</b></h5>", unsafe_allow_html=True)
                
                st.markdown("""
                Someone asks you to forward a 6-digit code they "accidentally" sent to your number. In reality, that is the login code for **YOUR** account.
                
                **Remember: NEVER** share a 6-digit code from an SMS with anyone. It is for your eyes only.
                """)
        
        st.markdown("---")

        # --- Get Help from Malaysian Authorities ---
        st.subheader("Get Help from Malaysian Authorities")
        st.markdown("If you've found your personal data exposed online, you can report it to the official channels below to request takedowns and file complaints.")

        col1, col2 = st.columns(2, gap="large")

        with col1:
            with st.container(border=True):
                st.image("assets/cybersecurity_logo.png", width=90)
                st.markdown("CyberSecurity Malaysia provides the **Cyber999 Help Centre** for you to report online security incidents, including data leaks, identity theft, and harassment.")
                st.link_button("Report to Cyber999 ➜", "https://www.mycert.org.my/cyber999")

        with col2:
            with st.container(border=True):
                st.image("assets/jpdp_logo.png", width=90)
                st.markdown("The JPDP handles violations of the Personal Data Protection Act (PDPA). File a complaint if you believe a **company has misused or failed to protect** your personal data.")
                st.link_button("File a Complaint with JPDP ➜", "https://www.pdp.gov.my/jpdpv2/ms/aduan/")

        st.markdown("---")

        # --- Footer sections ---
        st.subheader("🛠️ Powered by Leading Open-Source Tools")
        st.markdown("""
        Our system integrates a suite of powerful OSINT tools to provide comprehensive coverage:
        - **🔑 TruffleHog:** Scans public GitHub repositories for exposed API keys, passwords, and other secrets.
        - **🕵️ Sherlock:** Hunts for your username across hundreds of social media sites and online communities.
        - **📧 HIBP API:** Checks if your email or password has appeared in thousands of known public data breaches.
        - **🌐 Google Custom Search:** Uses targeted queries to find sensitive information exposed on the public web.
        """)
        st.markdown("---")
        st.success("🔐 **Your Privacy is Our Priority:** Scan inputs are saved to your private history and auto-deleted after 14 days. All scans use public data only.")
        render_footer()