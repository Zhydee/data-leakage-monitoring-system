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
def get_user_info(code):
    """Exchanges the authorization code for an access token and decodes the ID token using the public JWKS."""
    token_endpoint = f'https://{AUTH0_DOMAIN}/oauth/token'
    
    # Fetch the full token response
    token = session.fetch_token(
        url=token_endpoint,
        code=code,
        authorization_response=st.session_state.get('auth_response', '') 
    )
    
    jwks_uri = f'https://{AUTH0_DOMAIN}/.well-known/jwks.json'
    
    # 2. Fetch the JSON Web Key Set (JWKS)
    jwks = requests.get(jwks_uri).json()
    
    user_info = jwt.decode(
        token['id_token'],
        key=jwks
    )
    
    user_info.validate()

    return user_info

def display_login_prompt():
    """Shows a message and a sign-in button for protected pages."""
    st.warning("🔒 This feature is for signed-in users only.")
    st.markdown("Please sign in to view your personalized dashboard and reports.")
    
    auth_url = get_authorization_url()
    st.link_button("Sign in ", auth_url, use_container_width=True)
# For Authentication
def handle_auth_redirect():
    """Checks for the auth code in URL params and logs the user in."""
    query_params = st.query_params
    auth_code = query_params.get("code")
    
    if auth_code:
        st.session_state['auth_response'] = f"http://localhost:8501/?code={auth_code}"

    if auth_code and 'user' not in st.session_state:
        try:
            user_info = get_user_info(auth_code)
            st.session_state['user'] = user_info
            st.query_params.clear() 
            st.rerun()
        except Exception as e:
            st.error(f"Error during login: {e}")
            st.error("Please try signing in again.")

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
# --- Caching---
@st.cache_data(ttl=60, show_spinner=False) # Cache the result for 60 seconds
def get_scan_history():
    """Fetches and caches the scan history from the backend."""
    try:
        res = requests.get("http://localhost:8000/scan-history")
        if res.status_code == 200:
            return res.json()
        else:
            # Display an error in the app if fetching fails
            st.error(f"Failed to fetch scan data: Status code {res.status_code}")
            return None
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
    "IC Number": "ic", 
    "Password": "password",
    "Phone Number": "phone", 
    "Username": "username",
    "GitHub Repository": "github_repo",
    "Domain Name": "domain",
    "IP Address": "ip"
}
display_name_map = {v: k for k, v in backend_data_type_map.items()}
regex_patterns = {
                    "Email Address": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                    "Password": r".{6,}", "Phone Number": r'^(?:\+?60|60|0)(?:[\s\-\.]?\(?\d{1,3}\)?)(?:[\s\-\.]?\d){6,8}$',
                    "Username": r"^[a-zA-Z0-9_-]{3,16}$", "Domain Name": r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$",
                    "IP Address": r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
                    "IC Number": r"^\d{6}-\d{2}-\d{4}$", "GitHub Repository": r"^https?://github\.com/[\w.-]+/[\w.-]+/?$",
                }

# --- HELPER FUNCTION TO PARSE SPIDERFOOT DATA ---
def parse_spiderfoot_account(raw_data_string: str) -> dict:
    """
    Parses the raw string from SpiderFoot's sfp_accounts module
    into a clean, structured dictionary.
    """
    platform = "Unknown"
    category = "N/A"
    url = ""

    # 1. Extract the URL and remove the <SFURL>...</SFURL> tag from the string
    url_match = re.search(r"<SFURL>(.*?)</SFURL>", raw_data_string)
    if url_match:
        url = url_match.group(1)
        # Remove the entire tag block
        raw_data_string = raw_data_string.replace(url_match.group(0), "").strip()

    # 2. Extract the platform and category (e.g., "Blogspot (Category: blog)")
    # We look for the entire pattern including the parentheses.
    category_match = re.search(r"\((Category: .*?)\)", raw_data_string)

    if category_match:
        # Extract the category text (e.g., "Category: blog")
        full_category_string = category_match.group(0) # e.g., "(Category: blog)"
        category_content = category_match.group(1)     # e.g., "Category: blog"

        # Clean up the category name
        category = category_content.replace("Category: ", "").strip()

        # THE FIX: Remove the entire "(Category...)" block to get the clean platform name
        platform = raw_data_string.replace(full_category_string, "").strip()

    else:
        # If no category was found, the whole string is the platform name
        platform = raw_data_string

    # Final cleanup
    return {
        "platform": platform.strip(),
        "category": category,
        "url": url
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
- Break Into Other Accounts: If you reuse passwords, they will try the leaked password on your email, banking, and social media accounts.
- Send Convincing Scams: They can create targeted scam emails (phishing) that look real, tricking you into revealing more sensitive information.
- Attempt Identity Theft: With enough information, they can try to impersonate you.""",
            "playbook": """Follow these steps immediately to protect yourself:
1. Change Your Passwords Now: Go to the websites listed in the breach and change your password. Most importantly, if you used that same password anywhere else, change it there too.
2. Enable Extra Security (2FA): Turn on "Two-Factor Authentication" (also called 2FA or MFA) for your important accounts, especially your email. This sends a unique code to your phone when you log in, stopping a hacker even if they have your password.
3. Use a Password Manager: Consider using a password manager (like Bitwarden or 1Password). These tools create and remember a unique, strong password for every site, so you don't have to."""
        },
        "password": {
            "risk": """This password is no longer safe. It has been exposed in a data breach and is now on public lists used by hackers. Using this password for any account is like leaving your front door wide open.
- Automated Attacks: Hackers will use this password in automated attacks to try and log into thousands of popular websites, hoping to find one of your accounts.
- Account Takeover: If they get into one account, they will try to use it to reset the passwords for your other, more important accounts.""",
            "playbook": """Take these steps immediately for any account using this password:
1. Stop Using This Password: Change this password immediately on every single website and app where you currently use it.
2. Create New, Unique Passwords: Do not just change one character. Each account needs its own completely different, strong password.
3. Get a Password Manager: This is the best way to manage unique passwords. A password manager is a secure app that creates and remembers strong passwords for you, so you only need to remember one master password.
4. Turn On Extra Security (2FA): Enable "Two-Factor Authentication" wherever you can. It's your best defense against password leaks."""
        },
        "phone": {
            "risk": """Having your phone number or IC number public is a high risk. Scammers and identity thieves specifically look for this information to:
- Target You with Scams: Expect an increase in spam calls and scam text messages designed to trick you.
- Impersonate You: Your IC number is a core piece of your identity and can be used to open fraudulent accounts in your name.
- Hijack Your Phone Number: Criminals can try to trick your mobile provider into moving your number to their phone. This lets them intercept your calls, messages, and security codes.""",
            "playbook": """Here is how to handle this exposure:
1. Investigate the Source: Look at the websites listed in the findings to understand why your information is public.
2. Request Removal: Contact the website's administrator and ask them to remove your personal information.
3. Delete it Yourself: If it's a post you made on social media or a forum, log in and delete it immediately.
4. Be Extra Cautious: Be very suspicious of unexpected calls or texts. Never give out personal details or one-time security codes that are sent to you."""
        },
        "github_repo": {
            "risk": """An exposed "secret" (like an API key) in a public code repository is a critical risk. It's like leaving the key to your office or cloud services lying on the street for anyone to pick up and use. An attacker can:
- Steal Your Data: Access, change, or delete information from the service the key belongs to.
- Impersonate You: Take actions on your behalf without your knowledge.
- Run Up Huge Bills: If the key is for a cloud service (like AWS or Google Cloud), an attacker can use it to run expensive operations, leaving you with a massive bill.""",
            "playbook": """Act IMMEDIATELY. Every second counts.
1. Disable the Leaked Key (Most Important Step): Log into the dashboard of the service the key belongs to and immediately revoke or delete it. This makes the leaked key useless.
2. Generate a New Key: Create a new, replacement key to be used safely.
3. Update Your Applications: Replace the old, revoked key with the new one in all your applications.
4. Remove From History: Simply deleting the key from your code isn't enough, as it remains in the project's history. You must use a specialized tool to permanently erase it from all past versions."""
        },
        "username": {
            "risk": """Finding your username on many sites reveals your "digital footprint." Scammers can look at your different public profiles to piece together information about you (your hobbies, location, friends). They use this to:
- Create Personalized Scams: They can craft very convincing fake emails or messages that you are more likely to trust.
- Guess Security Questions: They can try to use details from your profiles to answer security questions and break into more sensitive accounts.""",
            "playbook": """Follow these steps to manage your digital footprint:
1. Review Your Public Profiles: Click on the links found and look at them as if you were a stranger. What can they learn about you?
2. Remove Sensitive Details: Go through your profiles and remove personal information you don't want the public to see, like your phone number, full birthdate, or home address.
3. Tighten Your Privacy Settings: On each website, go into the account settings and change who can see your posts and personal information from "Public" to "Friends Only" or "Private."""
        },
        "domain": {
            "risk": """The main risk for a domain owner is having your personal contact information (name, address, email) publicly listed in the ownership record (called a WHOIS record). This is like having your personal details in a phone book for the whole world to see, making you a target for spam and scams.""",
            "playbook": """Here is how you can protect your privacy:
1. Enable WHOIS Privacy (Most Important Step): Contact the company where you bought your domain name (your "Registrar") and ask them to turn on "WHOIS Privacy" or "Domain Privacy Protection." Most providers offer this to hide your personal details from the public record.
2. Review Technical Settings: The other information found is usually technical. You only need to check these settings if your website or email is not working properly."""
        },
        "ip": {
            "risk": """An IP address is your computer's or network's public address on the internet. The report can show "open doors" (or "ports") that are visible to the public. Each open door is a potential way for attackers to get into your network. If your IP address gets a bad reputation, other websites might block you.""",
            "playbook": """Follow these steps to secure your network:
1. Close Unnecessary "Doors": The report may list open services. Any service you don't recognize or need for public access should be closed. This is usually done in the security or "firewall" settings of your internet router.
2. Secure What's Left: For any services that must remain public (like a web server for a website), make sure the software is always fully updated and protected with strong passwords.
3. Investigate a Bad Reputation: If the report shows your IP has a bad reputation, it often means a device on your network (like a computer or phone) has a virus. Run antivirus scans on all your devices."""
        }
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

    dt = datetime.fromisoformat(scan["timestamp"]).strftime("%d %B %Y, %I:%M %p")
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

    # SpiderFoot (Domain/IP) Renderer
    spiderfoot_result = results.get('spiderfoot', {})
    if isinstance(spiderfoot_result, dict) and isinstance(spiderfoot_result.get("data"), list) and spiderfoot_result["data"]:
        sf_data = spiderfoot_result["data"]
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "-> Intelligence Scan (SpiderFoot)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, f"  Summary: Found {len(sf_data)} related intelligence items.")
        pdf.ln(4)
        
        # Group similar items for a cleaner report
        grouped_items = {}
        for item in sf_data[:15]: # Limit to 15 items
            item_type = item.get('type', 'UNCATEGORIZED').replace("_", " ").title()
            if item_type not in grouped_items:
                grouped_items[item_type] = []
            grouped_items[item_type].append(item.get('data', 'N/A'))
        
        for item_type, data_list in grouped_items.items():
            pdf.set_font("Helvetica", "B", 9)
            pdf.multi_cell(0, 5, f"  - {item_type}:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 8)
            for data_item in data_list:
                display_data = data_item[:100] + "..." if len(data_item) > 103 else data_item
                pdf.multi_cell(0, 5, f"    - {display_data}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
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
    pdf.multi_cell(0, 6, playbook['risk'])
    pdf.ln(8)

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
            pdf.cell(10, 6, f"{number}.")
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
        else:
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 6, step)
            pdf.ln(2)

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

    if scan_type == 'ip':
        spiderfoot_result = results.get('spiderfoot', {})
        if isinstance(spiderfoot_result, dict) and isinstance(spiderfoot_result.get("data"), list):
            vt_results = [r for r in spiderfoot_result.get("data", []) if r.get('module') == 'sfp_virustotal']
            if vt_results:
                detections_str = vt_results[0].get('data', '0/0').split('/')[0]
                if detections_str.isdigit() and int(detections_str) > 0:
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

    if scan_type == 'ip':
        spiderfoot_result = results.get('spiderfoot', {})
        if isinstance(spiderfoot_result, dict) and isinstance(spiderfoot_result.get("data"), list):
            if any(r.get('module') == 'sfp_shodan' for r in spiderfoot_result.get("data", [])):
                return "HIGH"

    # --- MEDIUM SEVERITY ---
    if scan_type == 'email':
        spiderfoot_result = results.get('spiderfoot', {})
        if isinstance(spiderfoot_result, dict) and isinstance(spiderfoot_result.get("data"), list):
            if any(r.get('module') == 'sfp_whois' for r in spiderfoot_result.get("data", [])):
                return "MEDIUM"

    # --- LOW SEVERITY ---
    if scan_type == 'username':
        sherlock_result = results.get('sherlock', {})
        # This is now the ONLY check for username scans.
        if isinstance(sherlock_result, dict) and sherlock_result.get("data"):
            return "LOW"
            
    if scan_type == 'domain':
        spiderfoot_result = results.get('spiderfoot', {})
        if isinstance(spiderfoot_result, dict) and spiderfoot_result.get("data"):
            return "LOW"
        
    if scan_type in ('domain', 'ip'):
        spiderfoot_result = results.get('spiderfoot', {})
        if isinstance(spiderfoot_result, dict) and isinstance(spiderfoot_result.get("data"), list) and spiderfoot_result["data"]:
            return "LOW"

    return None
# --- Google Custom Search (Google Dork) friendly display ---
def render_google_results_block(results):
    """
    Nicely formatted Google Custom Search block for Streamlit.
    Paste this function to replace your existing render_google_results_block.
    """
    google_result = results.get("google_dork")
    # Normalise shape (supports either list or {"data": [...]})
    if isinstance(google_result, dict) and isinstance(google_result.get("data"), list):
        google_list = google_result["data"]
    elif isinstance(google_result, list):
        google_list = google_result
    else:
        google_list = []

    # Small CSS for "pill" badges
    pill_css = """
    <style>
      .pill { display:inline-block; margin:4px 6px 4px 0; padding:6px 10px; 
              border-radius:999px; background:#f1f5f9; color:#0f172a; font-family:inherit; }
      .source_link { font-weight:600; font-size:16px; color:#0b69ff; text-decoration:none; }
      .snippet { color:#334155; margin-top:6px; margin-bottom:6px; font-style:italic; }
      .card { padding:14px 18px; border-radius:8px; background: #ffffff; box-shadow: 0 1px 4px rgba(15,23,42,0.04); }
      .meta { color:#475569; font-size:13px; }
      .divider { margin-top:12px; margin-bottom:12px; border-top:1px solid #e6eef8; }
    </style>
    """

    if not google_list:
        st.info("Nice — no public matches found right now. Your data looks safe ✅")
        return

    # Header
    st.markdown("### 🔎 Google Custom Search (Public Web Findings)")
    st.info(f"Found **{len(google_list)}** source(s) from Google Custom Search.")

    # Inject pill CSS once
    st.markdown(pill_css, unsafe_allow_html=True)

    # Render each result as a card
    for gr in google_list:
        src = gr.get("source_url", "") or "N/A"
        matches = gr.get("matches", {}) or {}
        ic_matches = matches.get("ic_numbers", []) or []
        phone_matches = matches.get("phone_numbers", []) or []
        snippet = (gr.get("snippet") or "").strip()

        with st.container():
            cols = st.columns([8, 2])
            # left column: source + pills + snippet
            left = cols[0]
            right = cols[1]

            # Source link (clickable)
            if src and src != "N/A":
                left.markdown(f"<a class='source_link' href='{src}' target='_blank' rel='noopener noreferrer'>🔗 {src}</a>", unsafe_allow_html=True)
            else:
                left.markdown("🔗 N/A")

            # Pills for phone & IC matches
            pills_html = ""
            if phone_matches:
                pills_html += "<div style='margin-top:8px'><strong>Phone:</strong> "
                for p in phone_matches:
                    pills_html += f"<span class='pill'>{p}</span>"
                pills_html += "</div>"
            if ic_matches:
                pills_html += "<div style='margin-top:6px'><strong>IC:</strong> "
                for i in ic_matches:
                    pills_html += f"<span class='pill'>{i}</span>"
                pills_html += "</div>"

            if pills_html:
                left.markdown(pills_html, unsafe_allow_html=True)

            # Right column: compact meta (counts)
            total_hits = len(phone_matches) + len(ic_matches)
            right.markdown(f"<div class='meta'>Hits: <strong>{total_hits}</strong></div>", unsafe_allow_html=True)

            # Snippet (shorten to 300 chars)
            if snippet:
                trimmed = snippet if len(snippet) <= 300 else snippet[:297].rstrip() + "..."
                left.markdown(f"<div class='snippet'>{trimmed}</div>", unsafe_allow_html=True)
            else:
                left.markdown("<div class='meta'>No snippet available.</div>", unsafe_allow_html=True)

            # divider
            st.markdown("<div class='divider'></div>", unsafe_allow_html=True)



# --- BACKEND CONNECTION TEST ---
try:
    requests.get("http://localhost:8000/health", timeout=2)
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
                        "Email Address": "Check if your email has been leaked in public data breaches.",
                        "Password": "Check if a password has been exposed in a data breach. The password is not sent to any server.",
                        "Phone Number": "Find out if your phone number is exposed in public sources.",
                        "Username": "Scan the internet for social media and forum accounts matching a username.",
                        "Domain Name": "Discover if a domain has been associated with leaked data.",
                        "IP Address": "Check if an IP address is publicly exposed or mentioned.",
                        "IC Number": "Monitor Malaysian IC number exposure.",
                        "GitHub Repository": "Scan an entire public GitHub repository for any exposed secrets.",
                    }
                    
                    placeholder_examples = {
                        "Email Address": "e.g., user@example.com",
                        "Password": "Enter a password to check its exposure",
                        "Phone Number": "e.g., 012-3456789 or +60123456789",
                        "Username": "e.g., testuser123",
                        "Domain Name": "e.g., example.com",
                        "IP Address": "e.g., 8.8.8.8",
                        "IC Number": "e.g., 990101-14-1234",
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
                    # This is the only code that runs after successful validation
                    
                    # 2. Define the function that will run in the background
                    def trigger_scan_in_background(payload):
                        try:
                            # This network request happens on a separate thread and does not block the app
                            requests.post("http://localhost:8000/scan/start", json=payload, timeout=50)
                        except Exception as e:
                            # Log any errors to the console without disturbing the user
                            print(f"Error in background scan trigger: {str(e)}")

                    # 3. Prepare the data for the scan
                    payload = {"data_type": backend_data_type, "search_data": search_data.strip()}
                    
                    # 4. Create and start the background thread
                    scan_thread = threading.Thread(target=trigger_scan_in_background, args=(payload,))
                    scan_thread.start()
                    
                    # 5. Give the user immediate feedback and let them navigate away
                    st.success("✅ Scan initiated in the background!", icon="🚀")
                    st.info("The results will appear in 'Scan History' when ready.", icon="ℹ️")
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

    # --- START OF THE CORRECTED AND FINAL "Scan History" BLOCK ---
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
                            st.markdown("### 🕵️ Username Footprint Analysis")
                            
                            sherlock_result = results.get('sherlock')
                            
                            st.subheader("Social Media Presence (from Sherlock)")
                            if isinstance(sherlock_result, dict) and isinstance(sherlock_result.get("data"), list):
                                sherlock_data = sherlock_result["data"]
                                if not sherlock_data:
                                    st.success("✅ No public social profiles found by Sherlock.")
                                else:
                                    st.metric(label="Public Profiles Found", value=len(sherlock_data))
                                    st.warning("Found Public Social Profile(s)", icon="🕵️")
                                    for url in sherlock_data:
                                        ext = tldextract.extract(url)
                                        platform = ext.domain.capitalize()
                                        st.markdown(f"🔗 **{platform}:** [{url}]({url})")
                                    # --- CONTEXTUAL RISK ANALYSIS ---
                                    st.markdown("---")
                                    st.error("🚨 What is the Risk?", icon="🤔")
                                    st.markdown("""
                                    Even though these are public profiles, they create a 'digital footprint'. Attackers can combine information from different accounts (like your interests, location, friends, and workplace) to build a detailed profile of you. This information can be used for:
                                    - **Targeted Phishing:** Creating very convincing scam emails or messages that you are more likely to fall for.
                                    - **Identity Theft:** Answering 'security questions' to try and access your more sensitive accounts.
                                    - **Social Engineering:** Tricking you or your friends into revealing more information.
                                    """)

                                    st.info("✅ What Should I Do? (Your Playbook)", icon="🛡️")
                                    st.markdown("""
                                    1.  **Review Each Profile:** Click on the links above and check what information is publicly visible.
                                    2.  **Remove Sensitive Details:** Take down any personal data you don't want strangers to know, like your full date of birth, phone number, home address, or specific location check-ins.
                                    3.  **Tighten Privacy Settings:** Go into the settings of each platform and limit who can see your posts, photos, and personal information. Change settings from "Public" to "Friends Only" or "Private".
                                    """)
                            else:
                                st.info("No Sherlock results available for this scan.")


                        # 2. ENRICHED EMAIL VIEW
                        elif scan['data_type'] == 'email':
                            st.markdown("### 📧 Email Exposure Analysis")
                            
                            hibp_result = results.get('hibp_emails')

                            st.subheader("Data Breach Exposure (from HIBP)")
                            if isinstance(hibp_result, dict) and isinstance(hibp_result.get("data"), list):
                                hibp_data = hibp_result["data"]
                                if not hibp_data:
                                    st.success("✅ No public breaches found for this email by HIBP.")
                                else:
                                    st.metric(label="Breaches Found", value=len(hibp_data), delta_color="inverse")
                                    st.error("🚨 Found in Public Data Breach", icon="🔥")
                                    
                                    for breach in hibp_data:
                                        with st.container(border=True):
                                            st.subheader(breach.get("Name", "Unknown Breach"))
                                            tags_html = "".join([f"<span style='background-color:#ffebee; color:#c62828; padding: 3px 8px; border-radius:12px; margin-right:5px; font-size:0.85rem;'>{item}</span>" for item in breach.get("DataClasses", [])])
                                            st.markdown(f"**Compromised Data:** {tags_html}", unsafe_allow_html=True)

                                    # --- CONTEXTUAL RISK ANALYSIS ---
                                    st.markdown("---")
                                    st.error("🚨 What is the Risk? (CRITICAL)", icon="🔥")
                                    st.markdown("""
                                    This is a **CRITICAL** risk. Your email and other personal details from these breaches are likely available to hackers. They can use this information to:
                                    - **Take Over Your Accounts:** If you reused the password from a breached site, they can access your other accounts (email, banking, social media).
                                    - **Send Targeted Phishing Scams:** They can create very believable scam emails that appear to come from the breached company to trick you into giving away more information.
                                    - **Commit Identity Theft:** With enough personal data, criminals can try to open new accounts or commit fraud in your name.
                                    """)

                                    st.info("✅ What Should I Do? (Your Playbook)", icon="🛡️")
                                    st.markdown("""
                                    **Follow these steps immediately:**
                                    1.  **Change Your Passwords:** Go to the websites listed in the breaches above and change your password right away.
                                    2.  **Change Passwords Everywhere Else:** If you used the same (or a similar) password on other websites, change them too. Hackers will try the leaked password on hundreds of other popular sites.
                                    3.  **Enable Two-Factor Authentication (2FA):** This is your best defense. Turn on 2FA for all your important accounts (especially email). This means that even if a hacker has your password, they can't log in without a code from your phone.
                                    4.  **Be Vigilant:** Be extra suspicious of any unexpected emails, especially those that ask you to click links or download attachments.
                                    """)
                            else:
                                st.info("No HIBP results available for this scan.")
                                                

                        # 2.5 (NEW) ENRICHED DOMAIN VIEW
                        elif scan['data_type'] == 'domain':
                            st.markdown("### 📈 Domain Intelligence Report")
                            st.markdown("This report shows the public information available about your domain, including its ownership records and technical connections to the internet.")

                            spiderfoot_result = results.get('spiderfoot')

                            if isinstance(spiderfoot_result, dict) and isinstance(spiderfoot_result.get("data"), list):
                                spiderfoot_data = spiderfoot_result["data"]
                                
                                whois_results = [r for r in spiderfoot_data if r.get('module') == 'sfp_whois']
                                if whois_results:
                                    with st.container(border=True):
                                        st.markdown("<h5>📝 Ownership & Registration Details (WHOIS)</h5>", unsafe_allow_html=True)
                                        st.info("**What is this?** This is the official public record of who owns this domain, like a deed for a house.", icon="💡")

                                        raw_whois = whois_results[0].get('data', '')
                                        
                                        st.markdown("---")
                                        st.subheader("Key Information")
                                        col1, col2, col3 = st.columns(3)
                                        with col1:
                                            registrar = next((line.split(': ')[1] for line in raw_whois.splitlines() if 'Registrar:' in line), 'N/A')
                                            st.metric(label="✅ Official Provider (Registrar)", value=registrar)
                                        with col2:
                                            creation_date_str = next((line.split(': ')[1] for line in raw_whois.splitlines() if 'Creation Date:' in line), 'N/A')
                                            st.metric(label="📅 Registered On", value=creation_date_str.split('T')[0] if 'T' in creation_date_str else creation_date_str)
                                        with col3:
                                            expiry_date_str = next((line.split(': ')[1] for line in raw_whois.splitlines() if 'Expiry Date:' in line), 'N/A')
                                            st.metric(label="⏳ Expires On", value=expiry_date_str.split('T')[0] if 'T' in expiry_date_str else expiry_date_str)
                                        st.markdown("---")
                                        
                                        st.subheader("Why This Matters & Recommendations")
                                        
                                        if "REDACTED" in raw_whois or "Privacy" in raw_whois:
                                            st.success("""
                                                **✅ Good News: Your personal contact information appears to be private.**
                                                The record shows that details like your name, address, and email are hidden. This is excellent for security, as it prevents spammers and scammers from harvesting your personal data from this public record.
                                            """, icon="🛡️")
                                        else:
                                            st.error("""
                                                **⚠️ High-Risk Alert: Your Personal Information is Public.**
                                                The ownership record for this domain appears to contain public contact details (name, address, email). This is a significant privacy risk.
                                                **💡 Recommendation:** Contact your domain provider (the 'Registrar' listed above) and ask to enable **"WHOIS Privacy"** or **"Domain Privacy Protection."** Most providers offer this service for free or a small fee to hide your personal details.
                                            """, icon="🔥")

                                        with st.expander("View the full raw technical record"):
                                            st.code(raw_whois, language="text")

                                dns_results = [r for r in spiderfoot_data if r.get('module') in ['sfp_dns', 'sfp_dnsresolve']]
                                if dns_results:
                                    with st.container(border=True):
                                        st.markdown("<h5>📡 Website & Email Server Connections (DNS)</h5>", unsafe_allow_html=True)
                                        st.info("**What is this?** These are the technical records that act like the internet's phonebook. They tell browsers where to find your website and email servers.", icon="💡")
                                        
                                        st.markdown("---")
                                        st.subheader("Key Connections")

                                        primary_ip = None
                                        ipv4_candidate = None
                                        ipv6_candidate = None
                                        fallback_candidate = None

                                        for item in dns_results:
                                            item_type = item.get('type', '').upper()
                                            item_data = item.get('data', '')
                                            item_source = item.get('source', '')

                                            if item_type == 'IP_ADDRESS':
                                                ipv4_candidate = item_data
                                                break

                                            if item_type == 'IPV6_ADDRESS' and not ipv6_candidate:
                                                ipv6_candidate = item_data
                                            
                                            if item_data == scan['search_data']:
                                                if '.' in item_source or ':' in item_source:
                                                    if not fallback_candidate:
                                                        fallback_candidate = item_source

                                        primary_ip = ipv4_candidate or ipv6_candidate or fallback_candidate

                                        if primary_ip:
                                            st.metric(label="🌐 Website's Digital Address (IP)", value=primary_ip)
                                            st.markdown(f"This is the unique address of the server hosting your website. When someone types `{scan['search_data']}` into a browser, DNS tells it to go to `{primary_ip}`.")
                                        else:
                                            st.markdown("No primary website address (IP Address) was found in this scan.")

                                        st.markdown("---")
                                        st.subheader("Why This Matters")
                                        st.markdown("""
                                        These records are essential for your online presence to function. If they are incorrect, your website or email service could go offline. While they don't typically contain sensitive personal data themselves, they confirm that your domain is actively connected to the internet.
                                        **💡 Recommendation:** No action is typically needed here unless you are experiencing technical issues with your website or email. This information is mainly for verification and technical troubleshooting.
                                        """)

                                        with st.expander("View all technical DNS records"):
                                            for item in dns_results:
                                                readable_type = item.get('type', 'N/A').replace('_', ' ').title()
                                                st.markdown(f"**{readable_type}:** `{item.get('data', 'N/A')}`")
                                # NEW: Catch-all for other unhandled DNS/intel results
                                other_results = [
                                    r for r in spiderfoot_data 
                                    if r.get('module') not in ['sfp_whois', 'sfp_dns', 'sfp_dnsresolve']
                                ]
                                if other_results:
                                    with st.container(border=True):
                                        st.markdown("<h5>📝 Other Intelligence Findings</h5>", unsafe_allow_html=True)
                                        # Group remaining items for a clean display
                                        grouped_items = {}
                                        for item in other_results:
                                            item_type = item.get('type', 'UNCATEGORIZED').replace("_", " ").title()
                                            if item_type not in grouped_items:
                                                grouped_items[item_type] = []
                                            grouped_items[item_type].append(item.get('data', 'N/A'))
                                        
                                        for item_type, data_list in sorted(grouped_items.items()):
                                            st.markdown(f"**{item_type}** ({len(data_list)} found):")
                                            for data_item in data_list:
                                                st.code(data_item, language="text")
                                            st.markdown("""<hr style="margin:0.5rem 0;" />""", unsafe_allow_html=True)

                            else:
                                st.info("No SpiderFoot results available for this scan.")

                        # 2.6 (NEW) ENRICHED IP ADDRESS VIEW
                        elif scan['data_type'] == 'ip':
                            st.markdown("### 📈 IP Address Intelligence Report")
                            st.markdown("This report shows public information about this IP address, including associated hostnames, open services, and its reputation.")

                            spiderfoot_result = results.get('spiderfoot')

                            if isinstance(spiderfoot_result, dict) and isinstance(spiderfoot_result.get("data"), list):
                                spiderfoot_data = spiderfoot_result["data"]
                                
                                vt_results = [r for r in spiderfoot_data if r.get('module') == 'sfp_virustotal']
                                hostname_results = [r for r in spiderfoot_data if r.get('type', '').upper() == 'INTERNET_NAME']

                                with st.container(border=True):
                                    st.markdown("<h5>📝 Reputation & Associated Hostnames</h5>", unsafe_allow_html=True)
                                    
                                    if vt_results:
                                        detections = vt_results[0].get('data', '0/0').split('/')[0]
                                        if detections == "0":
                                            st.success("**✅ Reputation Clean:** This IP was not found in any security blacklists on VirusTotal.", icon="🛡️")
                                        else:
                                            st.error(f"**🔥 Malicious Reputation:** This IP was flagged by **{detections}** security vendors on VirusTotal as potentially malicious.", icon="🚨")
                                    else:
                                        st.info("Reputation data not available for this IP.")

                                    st.markdown("---")
                                    if hostname_results:
                                        st.markdown(f"**Found {len(hostname_results)} associated hostname(s):**")
                                        for item in hostname_results:
                                            st.code(item.get('data', 'N/A'), language="text")
                                    else:
                                        st.markdown("**No associated hostnames were found.** This could be a dynamic IP address or one not linked to a specific domain name.")

                                shodan_results = [r for r in spiderfoot_data if r.get('module') == 'sfp_shodan']
                                if shodan_results:
                                    import json
                                    shodan_data_str = shodan_results[0].get('data', '{}')
                                    try:
                                        shodan_data = json.loads(shodan_data_str)
                                        
                                        with st.container(border=True):
                                            st.markdown(
                                                "<h5>🔌 Open Services & Location (from Shodan)</h5>",
                                                unsafe_allow_html=True,
                                                help="Shodan scans the internet for devices. This data reveals what services are publicly accessible from this IP address."
                                            )
                                            
                                            st.subheader("Location & Provider")
                                            col1, col2, col3 = st.columns(3)
                                            with col1:
                                                st.metric("📍 Country", shodan_data.get('country_name', 'N/A'))
                                            with col2:
                                                st.metric("🏙️ City", shodan_data.get('city', 'N/A'))
                                            with col3:
                                                st.metric("🏢 ISP", shodan_data.get('isp', 'N/A'))
                                            st.markdown("---")

                                            st.subheader("Exposed Services / Open Ports")
                                            if shodan_data.get('data'):
                                                for service in shodan_data['data']:
                                                    port = service.get('port', 'N/A')
                                                    service_name = service.get('product', 'Unknown Service')
                                                    transport = service.get('transport', 'tcp').upper()
                                                    st.error(f"**Port {port}/{transport}:** Running `{service_name}`", icon="⚠️")
                                            else:
                                                st.success("✅ No open ports or exposed services were identified by Shodan.")
                                            
                                            st.markdown("---")
                                            st.subheader("Why This Matters")
                                            st.warning("""
                                            **Exposed services can be a major security risk.** Each open port is a potential entry point for attackers. Services like databases (MySQL, PostgreSQL) or remote access (SSH, RDP) should almost never be exposed directly to the public internet.
                                            **💡 Recommendation:** If this is your IP address, review the list above. Any service that is not intentionally public should be firewalled. Ensure all public services are up-to-date and securely configured.
                                            """)
                                            with st.expander("View full raw Shodan data"):
                                                st.json(shodan_data)

                                    except json.JSONDecodeError:
                                        st.error("Could not parse raw Shodan data.")
                                # NEW: Catch-all for other unhandled intel results
                                other_results = [
                                    r for r in spiderfoot_data 
                                    if r.get('module') not in ['sfp_virustotal', 'sfp_shodan'] and r.get('type', '').upper() != 'INTERNET_NAME'
                                ]
                                if other_results:
                                    with st.container(border=True):
                                        st.markdown("<h5>📝 Other Intelligence Findings</h5>", unsafe_allow_html=True)
                                        # Group remaining items for a clean display
                                        grouped_items = {}
                                        for item in other_results:
                                            item_type = item.get('type', 'UNCATEGORIZED').replace("_", " ").title()
                                            if item_type not in grouped_items:
                                                grouped_items[item_type] = []
                                            grouped_items[item_type].append(item.get('data', 'N/A'))
                                        
                                        for item_type, data_list in sorted(grouped_items.items()):
                                            st.markdown(f"**{item_type}** ({len(data_list)} found):")
                                            for data_item in data_list:
                                                st.code(data_item, language="text")
                                            st.markdown("""<hr style="margin:0.5rem 0;" />""", unsafe_allow_html=True)
                            else:
                                st.info("No SpiderFoot results available for this scan.")
                        
                        # 4. PHONE & IC VIEW
                        elif scan['data_type'] in ("phone", "ic"):
                            # NEW: Conditional title and icon based on the specific data type
                            if scan['data_type'] == 'ic':
                                st.markdown("### 🪪 Public Exposure Analysis")
                            else:
                                st.markdown("### 📞 Public Exposure Analysis")

                            render_google_results_block(results)
                            google_result = results.get("google_dork", {})
                            google_list = google_result.get("data", []) if isinstance(google_result, dict) else []

                            if google_list:
                                # --- CONTEXTUAL RISK ANALYSIS ---
                                st.markdown("---")
                                st.error("🚨 What is the Risk? (HIGH)", icon="🔥")
                                st.markdown("""
                                Having your phone number or IC number publicly exposed online is a **HIGH** risk. Scammers and identity thieves actively search for this information. They can use it to:
                                - **Target You with Scams:** You may receive an increase in spam calls and phishing text messages (SMSishing) trying to trick you into giving away money or passwords.
                                - **Commit Identity Theft:** Your IC number is a key piece of information used to impersonate you, open fraudulent accounts, or apply for loans in your name.
                                - **Hijack Your Accounts:** Many online services use your phone number for account recovery. An attacker could use this to try and take over your accounts (an attack called "SIM-swapping", where a scammer tricks your mobile provider into moving your number to their phone).
                                """)

                                st.info("✅ What Should I Do? (Your Playbook)", icon="🛡️")
                                st.markdown("""
                                1.  **Investigate the Source:** Carefully review the links found above to understand why your information is public.
                                2.  **Request Takedown:** If the information is on a website you don't control (like a forum or public directory), contact the website's administrator and formally request that they remove your personal information.
                                3.  **Remove it Yourself:** If it's a post you made on social media or a forum, log in and delete it immediately.
                                4.  **Be Extra Cautious:** Be extremely wary of unsolicited calls or text messages. Never give out personal information or one-time codes (OTPs) to anyone who contacts you unexpectedly.
                                """)
                                
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
                "scans": ["Phone Numbers", "IC Numbers"] 
            },
            "🕷️ SpiderFoot": { 
                "purpose": "Automated OSINT to gather public intelligence on internet assets.", 
                "scans": ["Domain & IP Intelligence", "Public Server Information (WHOIS, DNS)"] 
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
                alert_res = requests.get(f"http://localhost:8000/monitoring/alerts/{user_id}")
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
                                    dismiss_res = requests.put(f"http://localhost:8000/monitoring/alerts/{alert['id']}/read")
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
                                response = requests.post("http://localhost:8000/monitoring/assets", json=payload)
                                if response.status_code == 201:
                                    st.success(f"Successfully added '{asset_data}' to the monitoring list!")
                                    st.rerun()
                                else:
                                    st.error(f"Failed to add asset: {response.text}")
                            except Exception as e:
                                st.error(f"An error occurred: {e}")
                    else:
                        st.warning("Please enter the data to monitor.")
                   

            st.markdown("---")

            # --- Section to display and manage current assets ---
            st.subheader("Currently Monitored Assets")
            try:
                res = requests.get(f"http://localhost:8000/monitoring/assets/{user_id}")
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
                                    del_res = requests.delete(f"http://localhost:8000/monitoring/assets/{asset['id']}")
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
            - **Domain & IP Records:** Querying public records like WHOIS and DNS to understand a domain's footprint (via SpiderFoot).

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
            <div style='text-align: center; background: linear-gradient(135deg, #f39c12, #e67e22); border-radius:10px; padding: 1.5rem; margin-bottom:1rem;'>
                <h1 style='color: #FFFFFF;'>👋 Welcome to the Data Leakage Monitoring System</h1>
                <p style='color: #FFFFFF; font-size: 1.1rem;'>An open-source platform to help you monitor, detect, and protect your personal data exposure online.</p>
            </div>
        """, unsafe_allow_html=True)
        
        # --- NEW: PROMINENT LOGIN CALL-TO-ACTION FOR GUESTS ---
        if 'user' not in st.session_state:
            st.subheader("Get Started")
            with st.container(border=True):
                st.markdown("#### Ready to secure your digital footprint?")
                st.markdown("Sign in to access your private dashboard, view detailed reports, and manage your scan history.")
                auth_url = get_authorization_url()
                st.link_button("Sign in ", auth_url, use_container_width=True)
            st.markdown("---")
        # --- END OF NEW SECTION ---

        st.subheader("🔍 What This System Can Do")
        col1, col2, col3 = st.columns(3, gap="large")
        with col1:
            with st.container(border=True):
                st.markdown(
                    """
                    <div style="text-align:center;">
                        <img src="https://cdn-icons-png.flaticon.com/512/3502/3502601.png" width="50">
                        <h3>Automated Leak Scanning</h3>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                st.write("Search public platforms for exposed data.")
        with col2:
            with st.container(border=True):
                st.markdown(
                    """
                    <div style="text-align:center;">
                        <img src="https://cdn-icons-png.flaticon.com/512/1055/1055645.png" width="50">
                        <h3>Understand Results</h3>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                st.write("Get clear results on what was found and why it matters.")
        with col3:
            with st.container(border=True):
                st.markdown(
                    """
                    <div style="text-align:center;">
                        <img src="https://cdn-icons-png.flaticon.com/512/942/942792.png" width="50">
                        <h3>Protect Your Identity</h3>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                st.write("Receive simple, non-technical steps to improve your security.")

        st.markdown("---")
        # --- 3. NEW SECTION: WHY IT MATTERS ---
        # --- WHY IT MATTERS SECTION (with larger, more readable text) ---
        st.subheader("👣 Why Your Digital Footprint Matters")
        st.markdown("Every day, personal data is leaked online. This exposure can lead to serious consequences.")
        col1, col2, col3 = st.columns(3, gap="large")
        with col1:
            st.markdown("""
                <div style='text-align:center'>
                    <p style='font-size: 2rem;'>💰</p>
                    <h4 style='margin-bottom: 0.5rem;'>Financial Fraud</h4>
                    <p>Stolen credit cards or bank details can be used for unauthorized purchases.</p>
                </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown("""
                <div style='text-align:center'>
                    <p style='font-size: 2rem;'>🎭</p>
                    <h4 style='margin-bottom: 0.5rem;'>Identity Theft</h4>
                    <p>Leaked personal info can be used to open accounts or commit crimes in your name.</p>
                </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown("""
                <div style='text-align:center'>
                    <p style='font-size: 2rem;'>📧</p>
                    <h4 style='margin-bottom: 0.5rem;'>Targeted Phishing</h4>
                    <p>Hackers use leaked data to create convincing scams to trick you into revealing more.</p>
                </div>
            """, unsafe_allow_html=True)
        st.markdown("---")
        # --- 4. NEW SECTION: HOW IT WORKS ---
        st.subheader("⚙️ A Simple, Powerful Process")
        col1, col2, col3 = st.columns(3, gap="large")
        with col1:
            st.markdown("### 1. Provide Input\nSelect a data type (like an email or username) and enter the information you want to check.", unsafe_allow_html=True)
        with col2:
            st.markdown("### 2. Intelligent Scanning\nOur system intelligently selects the best tools for the job. Based on your chosen data type, we run targeted scans against the most relevant sources.", unsafe_allow_html=True)
        with col3:
            st.markdown("### 3. Get Unified Results\nWe consolidate all findings into a single, easy-to-read report in your 'Scan History' with clear recommendations.", unsafe_allow_html=True)
        # --- 5. SECURITY TIP (MOVED HERE) ---
        st.subheader("💡 Security Tip of the Day")
        tips = [
            ("🔐 Use a Password Manager", "Tools like Bitwarden or 1Password create and store strong, unique passwords for every account, which is the single best thing you can do for your security."),
            ("🤔 Think Before You Click", "Be cautious of phishing emails and messages. Never click suspicious links or download unexpected attachments. Always verify the sender."),
            ("🔑 Enable Two-Factor Authentication (2FA)", "2FA adds a critical second layer of security to your accounts, requiring a code from your phone in addition to your password."),
        ]
        tip_title, tip_body = random.choice(tips)
        with st.container(border=True):
            st.markdown(f"#### {tip_title}")
            st.markdown(tip_body)
        st.markdown("---")
        st.subheader("🛠️ Powered by Leading Open-Source Tools")
        st.markdown("""
        Our system integrates a suite of powerful OSINT tools to provide comprehensive coverage:
        - **🔑 TruffleHog:** Scans public GitHub repositories for exposed API keys, passwords, and other secrets.
        - **🕵️ Sherlock:** Hunts for your username across hundreds of social media sites and online communities.
        - **📧 HIBP API:** Checks if your email or password has appeared in thousands of known public data breaches.
        - **🕷️ SpiderFoot:** Gathers public intelligence on domains and IPs to map your digital footprint.
        - **🌐 Google Custom Search:** Uses targeted queries to find sensitive information exposed on the public web.
        """)
        
        st.markdown("---")
        
        st.success("🔐 **Your Privacy is Our Priority:** Scan inputs are saved to your private history and auto-deleted after 14 days. All scans use public data only.")
        render_footer()