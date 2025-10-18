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
from dotenv import load_dotenv
load_dotenv()
# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Data Leakage Monitoring System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"  # ENSURES SIDEBAR IS INITIALLY OPEN AND BUTTON IS ALWAYS FUNCTIONAL
)
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
        footer { visibility: hidden; }
        
        /* --- Sidebar Styling --- */
        [data-testid="stSidebar"] {
            background-color: #E9ECEF;
            border-right: 1px solid #D1D5DB;
        }
        
        /* --- MODIFICATION: ADDED SELECTOR FOR FORM SUBMIT BUTTON --- */
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
    Returns the contextual risk and actionable playbook text for a given scan type.
    """
    playbooks = {
        "email": {
            "risk": """This is a CRITICAL risk. Your email and other personal details from these breaches are likely available to hackers. They can use this information to:
- Take Over Your Accounts: If you reused the password from a breached site, they can access your other accounts.
- Send Targeted Phishing Scams: They can create very believable scam emails to trick you into giving away more information.
- Commit Identity Theft: With enough personal data, criminals can try to open new accounts or commit fraud in your name.""",
            "playbook": """Follow these steps immediately:
1. Change Your Passwords: Go to the websites listed in the breaches and change your password right away.
2. Change Passwords Everywhere Else: If you used the same password on other websites, change them too.
3. Enable Two-Factor Authentication (2FA): This is your best defense. Turn it on for all important accounts.
4. Be Vigilant: Be extra suspicious of any unexpected emails asking you to click links or download attachments."""
        },
        "password": {
            "risk": """This is a CRITICAL risk. DO NOT USE THIS PASSWORD. It is publicly known and is on lists used by hackers. Using this password for any account is like leaving your front door wide open.
- Attackers will use this password to try and log into your email, bank, and social media accounts (credential stuffing).
- If they get into one account, they will use it to try and reset your passwords for other accounts.""",
            "playbook": """1. Stop Using This Password Immediately: Identify every single online account where you are currently using this password.
2. Change Your Passwords: Change your password on each of those sites to a new, unique, and strong one.
3. Use a Password Manager: This is the best way to manage unique passwords. A password manager is a secure app that creates and remembers strong passwords for you. Popular options include Bitwarden and 1Password.
4. Enable Two-Factor Authentication (2FA): Turn on 2FA everywhere possible for an extra layer of security."""
        },
        "phone": {
            "risk": """Having your phone number or IC number publicly exposed is a HIGH risk. Scammers and identity thieves actively search for this information to:
- Target You with Scams: You may receive an increase in spam calls and phishing text messages.
- Commit Identity Theft: Your IC number is a key piece of information used to impersonate you.
- Hijack Your Accounts: An attacker could use your phone number for account recovery (a "SIM-swap" attack, where they move your number to their phone).""",
            "playbook": """1. Investigate the Source: Review the links found to understand why your information is public.
2. Request Takedown: Contact the website's administrator and formally request that they remove your personal information.
3. Remove it Yourself: If it's a post you made on social media or a forum, log in and delete it immediately.
4. Be Extra Cautious: Be wary of unsolicited calls or texts. Never give out personal information or one-time codes (OTPs)."""
        },
        "github_repo": {
            "risk": """An exposed secret in a GitHub repository is a CRITICAL risk. It's like leaving the master key to your house on the street. An attacker can use this key to:
- Access and Steal Your Data: Read, modify, or delete information from the associated service.
- Impersonate You: Perform actions on your behalf without your knowledge.
- Incur Financial Costs: If the key is for a cloud service (like AWS), an attacker can use it to run expensive services, leaving you with a massive bill.""",
            "playbook": """Act IMMEDIATELY. Every second counts.
1. Identify the Leaked Key: Determine which key was exposed and what service it belongs to.
2. Revoke the Key: Log into the service's dashboard and revoke or delete the compromised key. This is the most critical step.
3. Generate a New Key: Create a new, replacement key.
4. Remove from History: Remove the secret from the file and then use a tool to erase it from the entire Git history. A simple commit is not enough. (Note: Revoking the key is the most important step).
5. Update Your Applications: Replace the old, revoked key with the new one in all your applications."""
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

# --- FULLY REVISED AND ENHANCED PDF GENERATION FUNCTION ---
# --- FINAL, FULLY ENHANCED, AND STABLE PDF GENERATION FUNCTION (WITH TABLE FIX) ---
def generate_scan_report_pdf(scan: dict, display_name_map: dict) -> bytes:
    """
    Generates a robust and visually appealing PDF report for a single scan job.
    This version includes the definitive fix for the table layout corruption by
    correctly calculating variable row heights.
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

    has_findings = any(isinstance(res.get("data"), list) and res["data"] for res in results.values() if isinstance(res, dict))
    
    if not has_findings:
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 7, "  No specific leaks or exposures were found in this scan.")
        pdf.ln(5)

    # TruffleHog Renderer (Stable)
    trufflehog_result = results.get('trufflehog', {})
    if isinstance(trufflehog_result, dict) and isinstance(trufflehog_result.get("data"), list):
        findings = trufflehog_result["data"]
        if findings:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, f"-> Secret Leak Scan (TruffleHog)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
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
                detector = finding.get('DetectorName', 'N/A')
                file = metadata.get('file', 'N/A')
                line = metadata.get('line', 'N/A')
                display_detector = detector if len(detector) < 25 else detector[:22] + "..."
                display_file = file if len(file) < 70 else "..." + file[-67:]
                pdf.cell(45, 6, display_detector, 1)
                pdf.cell(110, 6, display_file, 1)
                pdf.cell(20, 6, str(line), 1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(8)

    # --- HIBP (Email Breaches) Renderer - CORRECTED TABLE LOGIC ---
    hibp_result = results.get('hibp_emails', {})
    if isinstance(hibp_result, dict) and isinstance(hibp_result.get("data"), list):
        breaches = hibp_result["data"]
        if breaches:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, f"-> Email Breach Check (Have I Been Pwned)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5, f"  Summary: This email was found in {len(breaches)} public data breaches.")
            pdf.ln(3)
            
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(65, 7, "Breach Name", 1, align="C")
            pdf.cell(110, 7, "Types of Data Compromised", 1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
            pdf.set_font("Helvetica", "", 8)
            for breach in breaches[:10]:
                name = breach.get("Name", "N/A")
                data_classes = ", ".join(breach.get("DataClasses", []))
                display_name = name if len(name) < 40 else name[:37] + "..."
                display_data = data_classes if len(data_classes) < 75 else data_classes[:72] + "..."

                # --- START OF THE FIX ---
                start_y = pdf.get_y()
                
                # Draw the left cell
                pdf.multi_cell(65, 6, display_name, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
                
                # Store the Y position after drawing the potentially multi-line left cell
                y_after_left = pdf.get_y()
                
                # Reset Y to the start of the row and move X for the right cell
                pdf.set_xy(pdf.get_x(), start_y)
                
                # Draw the right cell
                pdf.multi_cell(110, 6, display_data, border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                
                # Store the Y position after drawing the potentially multi-line right cell
                y_after_right = pdf.get_y()
                
                # Set the final Y position to the bottom of whichever cell was taller
                pdf.set_y(max(y_after_left, y_after_right))
                # --- END OF THE FIX ---

            pdf.ln(8)

    # Sherlock (Usernames) Renderer (Stable)
    sherlock_result = results.get('sherlock', {})
    if isinstance(sherlock_result, dict) and isinstance(sherlock_result.get("data"), list):
        urls = sherlock_result["data"]
        if urls:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, f"-> Username & Social Media Scan (Sherlock)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5, f"  Summary: Found {len(urls)} social media or forum profiles with this username.")
            pdf.ln(4)
            for url in urls[:10]:
                ext = tldextract.extract(url)
                platform = ext.domain.capitalize()
                pdf.set_font("Helvetica", "B", 9)
                pdf.multi_cell(0, 5, f"  - Platform: {platform}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_font("Helvetica", "", 8)
                pdf.multi_cell(0, 5, f"    URL: {url}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(2)
            pdf.ln(8)

    # --- 4. Actionable Recommendations Page (Styled and Stable) ---
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
# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.markdown("<h1 style='color:#2c3e50; text-align:center; font-size: 1.5rem;'>MENU</h1>", unsafe_allow_html=True)
    selected = option_menu(
        menu_title=None,
        options=["Homepage", "Scanner", "Dashboard", "Scan History", "About Tools", "Reports", "FAQ"],
        icons=["house-door", "search", "bar-chart-line", "clock-history", "tools", "clipboard-data", "question-circle"],
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
# --- PAGE ROUTING ---
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

    # --- The submission logic block is OUTSIDE all layout elements ---
    # This part remains unchanged and will now work correctly.
    if scan_button:
        if search_data:
            regex_patterns = {
                "Email Address": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                "Password": r".{6,}", "Phone Number": r'^(?:\+?60|60|0)(?:[\s\-\.]?\(?\d{1,3}\)?)(?:[\s\-\.]?\d){6,8}$',
                "Username": r"^[a-zA-Z0-9_-]{3,16}$", "Domain Name": r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$",
                "IP Address": r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
                "IC Number": r"^\d{6}-\d{2}-\d{4}$", "GitHub Repository": r"^https?://github\.com/[\w.-]+/[\w.-]+/?$",
            }
            backend_data_type = backend_data_type_map[data_type]
            pattern = regex_patterns[data_type]
            if not re.search(pattern, search_data.strip()):
                st.error(f"❌ Input does not match the expected {data_type} format. Please check and try again.", icon="🚨")
            else:
                st.success("✅ Input validated. Initiating scan...", icon="👍")
                with st.spinner("🚀 Scanning... This may take a few minutes for public scans."):
                    payload = {"data_type": backend_data_type, "search_data": search_data.strip()}
                    try:
                        response = requests.post("http://localhost:8000/scan/start", json=payload)
                        if response.status_code == 200:
                            result = response.json()
                            st.success(f"🎉 Scan started successfully! Job ID: `{result['job_id']}`", icon="✅")
                            st.info("📊 Results will appear in 'Scan History' shortly.", icon="ℹ️")
                        else:
                            st.error(f"❌ Scan failed: {response.status_code} - {response.text}", icon="🔥")
                    except Exception as e:
                        st.error(f"❌ Error initiating scan: {str(e)}", icon="🔥")
        else:
            st.warning("⚠️ Please enter data to search before starting a scan.", icon="❗️")

# --- NEW: SECURITY DASHBOARD PAGE ---
elif selected == "Dashboard":
    st.header("📈 Security Dashboard")
    st.markdown("A high-level, aggregated, and visual overview of your overall security risk based on all historical scans.")

    try:
        res = requests.get("http://localhost:8000/scan-history")
        if res.status_code != 200:
            st.error(f"Failed to fetch scan data: Status code {res.status_code}")
        else:
            scans = res.json()
            if not scans:
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
    except Exception as e:
        st.error(f"❌ An error occurred while building the dashboard: {e}", icon="🔥")

# --- START OF THE CORRECTED AND FINAL "Scan History" BLOCK ---
elif selected == "Scan History":
    st.header("📊 Scan History")
    st.markdown("Review the enriched findings from your recent scans. Results from multiple tools are combined for better insights.")
    
    try:
        res = requests.get("http://localhost:8000/scan-history")
        if res.status_code == 200:
            scans = res.json()
            if not scans:
                st.info("No scan history found. Run a scan from the 'Scanner' page to see results here.", icon="ℹ️")

            for scan in scans:
                display_data_type = display_name_map.get(scan['data_type'], scan['data_type'].capitalize())
                expander_title = f"Scan ID: {scan['scan_id']} | Type: {display_data_type} | Data: '{scan['search_data']}'"
                
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

        else:
            st.error(f"Failed to fetch scan history: Status code {res.status_code}")
    except Exception as e:
        st.error(f"❌ An error occurred while processing scan history: {e}", icon="🔥")



# --- END OF THE CORRECTED AND FINAL "Scan History" BLOCK ---
elif selected == "About Tools":
    st.header("🛠️ Our OSINT Arsenal")
    st.markdown("An overview of the powerful, open-source tools that drive our scanning engine.")
    tools_info = {
        "🐷 TruffleHog": { 
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
elif selected == "Reports":
    st.header("📈 Security Reports")
    st.markdown("View comprehensive analysis and generate downloadable reports of your security scans.")
    
    with st.container(border=True):
        st.info("📊 This feature is under development. Detailed reports will be available here soon.", icon="💡")
        st.subheader("What You'll Get:")
        st.markdown("""
        - **📋 Summary Report**: An easy-to-understand overview of all findings.
        - **🔍 Detailed Analysis**: A complete breakdown of each security check.
        - **🚨 Risk Assessment**: Clear explanations of what the findings mean for you.
        - **💡 Actionable Recommendations**: Simple steps to improve your digital safety.
        - **📁 Export Options**: Download reports as PDF or spreadsheets.
        """)
    st.success("🛡️ **Our Goal:** Reports are written in simple language for everyone to understand.")
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
        - **API Keys & Other Secrets:** Your input is sent directly to the scanning tools (like TruffleHog) to be checked against public data. It is **never** written to our database or stored after the scan is complete.
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
elif selected == "Homepage":
    st.markdown("""
        <div style='text-align: center; background: linear-gradient(135deg, #f39c12, #e67e22); border-radius:10px; padding: 1.5rem; margin-bottom:1rem;'>
            <h1 style='color: #FFFFFF;'>👋 Welcome to the Data Leakage Monitoring System</h1>
            <p style='color: #FFFFFF; font-size: 1.1rem;'>An open-source platform to help you monitor, detect, and protect your personal data exposure online.</p>
        </div>
    """, unsafe_allow_html=True)
    
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
    - **🐷 TruffleHog:** Scans public GitHub repositories for exposed API keys, passwords, and other secrets.
    - **🕵️ Sherlock:** Hunts for your username across over 400 social media sites and online communities.
    - **📧 HIBP API:** Checks if your email address or password has appeared in thousands of known public data breaches.
    - **🕷️ SpiderFoot & theHarvester:** Gathers public intelligence on domains and IPs to map your digital footprint.
    """)
    st.markdown("---")
    
    st.success("🔐 **Your Privacy is Our Priority:** We never store your sensitive data. All scans are conducted ethically using only publicly available information.")