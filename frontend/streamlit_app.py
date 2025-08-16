import streamlit as st
from streamlit_option_menu import option_menu
import tldextract
from datetime import datetime
import locale
from zoneinfo import ZoneInfo
import requests
import random
import os
import re
from dotenv import load_dotenv

load_dotenv()

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Data Leakage Monitoring System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"  # ENSURES SIDEBAR IS INITIALLY OPEN AND BUTTON IS ALWAYS FUNCTIONAL
)

# --- ROBUST & SCALABLE UI STYLES ---
# --- ROBUST & SCALABLE UI STYLES ---
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
        
        /* --- Compact Button Styling --- */
        .stButton>button {
            border: 2px solid #f39c12;
            background-color: #f39c12;
            color: #FFFFFF;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-weight: bold;
            font-size: 0.9rem;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
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
    "Email Address": "email", "Password": "password", "Phone Number": "phone",
    "Username": "username", "Domain Name": "domain", "IP Address": "ip",
    "Credit Card Number": "credit_card", "IC Number": "ic", "API Keys/Tokens": "api_key"
}
display_name_map = {v: k for k, v in backend_data_type_map.items()}



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
        options=["Homepage", "Scanner", "Scan History", "About Tools", "Reports", "FAQ"],
        icons=["house-door", "search", "clock-history", "tools", "clipboard-data", "question-circle"],
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

        with col1:
            st.subheader("1. Select Data Type")
            data_type = st.selectbox(
                label="Choose the type of data to scan for:",
                options=list(backend_data_type_map.keys()),
                label_visibility="collapsed",
                help="Select the type of data you want to scan for leaks."
            )

        with col2:
            help_messages = {
                "Email Address": "Check if your email has been leaked in public data breaches. e.g., user@example.com",
                "Password": "Check if a password has been exposed in a data breach. The password is not sent to any server.",
                "Phone Number": "Find out if your phone number is exposed in public sources. Format: 012-3456789",
                "Username": "Scan the internet for social media and forum accounts matching a username.",
                "Domain Name": "Discover if a domain (e.g., example.com) has been associated with leaked data.",
                "IP Address": "Check if an IP address is publicly exposed or mentioned.",
                "Credit Card Number": "Scan for potential credit card leaks (input is masked and protected).",
                "IC Number": "Monitor Malaysian IC number exposure. Format: xxxxxx-xx-xxxx",
                "API Keys/Tokens": "Scan all of public GitHub for an exposed secret (e.g., API key, password, token).",
            }
            
            if data_type == "Password":
                search_data = st.text_input(
                    label="2. Provide Input Data",
                    type="password",
                    placeholder="Enter password to check...",
                    help=help_messages.get(data_type)
                )
            else:
                search_data = st.text_area(
                    label="2. Provide Input Data",
                    height=100,
                    placeholder=f"Enter {data_type.lower()} to search...",
                    help=help_messages.get(data_type)
                )

        st.markdown("<hr style='border: 1px solid #E0E0E0;'>", unsafe_allow_html=True)
        scan_button = st.button("🚀 Start Comprehensive Scan", use_container_width=True)

    if scan_button:
        if search_data:
            regex_patterns = {
                "Email Address": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                "Password": r".{6,}", "Phone Number": r"(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})",
                "Username": r"^[a-zA-Z0-9_-]{3,16}$", "Domain Name": r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$",
                "IP Address": r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
                "Credit Card Number": r"^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})$",
                "IC Number": r"^\d{6}-\d{2}-\d{4}$", "API Keys/Tokens": r"^[A-Za-z0-9+/=_-]{16,}$",
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

elif selected == "Scan History":
    st.header("📊 Scan History")
    st.markdown("Review the findings from your recent scans. Results are retrieved from the database.")
    
    try:
        res = requests.get("http://localhost:8000/scan-history")
        if res.status_code == 200:
            scans = res.json()
            if not scans:
                st.info("No scan history found. Run a scan from the 'Scanner' page to see results here.", icon="ℹ️")

            tool_display_names = {
                "hibp_emails": "Email Breach Check (Have I Been Pwned)",
                "hibp_passwords": "Password Security Check (Have I Been Pwned)",
                "sherlock": "Username & Social Media Scan (Sherlock)",
                "trufflehog": "Public Code & Secret Leak Scan (TruffleHog)",
                "google_dork": "Public Exposure Scan (Google)",
                "spiderfoot": "Automated Intelligence Scan (SpiderFoot)"
            }

            for scan in scans:
                display_data_type = display_name_map.get(scan['data_type'], scan['data_type'].capitalize())
                expander_title = f"Scan ID: {scan['scan_id']} | Type: {display_data_type} | Data: '{scan['search_data']}'"
                
                with st.expander(expander_title, expanded=False):
                    dt = datetime.fromisoformat(scan["timestamp"]).replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kuala_Lumpur"))
                    
                    try:
                        locale.setlocale(locale.LC_TIME, "en_US.utf8")
                    except locale.Error:
                        locale.setlocale(locale.LC_TIME, "")
                    formatted_date = dt.strftime("%d %B %Y, %I:%M %p")

                    st.markdown(f"**🕒 Timestamp:** {formatted_date} | **Status:** `{scan['status']}`")
                    st.markdown("---")
                    st.markdown("**Results:**")

                    tool_descriptions = {
                        "hibp_emails": "This tool checks if your email has been found in any public data breaches using the Have I Been Pwned service.",
                        "hibp_passwords": "This tool checks if a password has appeared in any known data breaches.",
                        "sherlock": "This tool checks social media websites to see if your username is being used anywhere.",
                        "trufflehog": "This tool scans all of public GitHub to see if a specific secret, like an API key, has been leaked.",
                        "theharvester": "This tool collects emails and other details about a website from public search engines.",
                        "spiderfoot": "This tool gathers information about websites, IP addresses, and even mentions on the dark web.",
                        "google_dork": "Uses advanced Google search techniques (dorks) to find mentions of the input data on public websites, code repositories, and documents."
                    }

                    for tool, result in scan["results"].items():
                        display_name = tool_display_names.get(tool, tool.replace('_', ' ').title())
                        st.markdown(f"<h5 style='margin-bottom:0.5rem; margin-top:1rem;'>🔧 {display_name}</h5>", unsafe_allow_html=True)
                        
                        with st.popover("What is this?"):
                            st.info(tool_descriptions.get(tool, "No description available for this tool."), icon="ℹ️")

                        # --- FULL CODE FOR EACH CONDITION ---
                        if tool == "sherlock" and isinstance(result.get("data"), list):
                            if not result["data"]:
                                st.success("✅ No public social profiles found for this username.")
                            else:
                                st.markdown(f"🔎 Found `{len(result['data'])}` social profiles:")
                                for url in result["data"]:
                                    ext = tldextract.extract(url)
                                    platform = ext.domain.capitalize()
                                    st.markdown(f"""
                                        <div style='border:1px solid #ddd; border-radius:8px; padding:12px; margin-bottom:10px; background-color:#f9f9f9'>
                                            <b>🛰️ Platform:</b> {platform}<br>
                                            <b>🔗 Link:</b> <a href="{url}" target="_blank" style="color:#f39c12;">{url}</a>
                                        </div>
                                        """, unsafe_allow_html=True)

                        elif tool == "hibp_passwords" and isinstance(result.get("data"), dict):
                            is_pwned = result["data"].get("pwned", False)
                            count = result["data"].get("count", 0)
                            with st.container(border=True):
                                if is_pwned:
                                    st.error("🚨 This Password is Unsafe", icon="🔥")
                                    st.metric(label="Found in Data Breaches", value=f"{count:,} times")
                                    st.warning("**Recommendation:** This password is compromised and unsafe. Change it immediately wherever you have used it.", icon="⚠️")
                                    with st.expander("**Show me what to do next**", expanded=True):
                                        st.markdown("""
                                            - **Change This Password Immediately** on any site that uses it.
                                            - **Create a Strong, Unique Password**: Use a long passphrase or a password manager.
                                            - **Use a Password Manager**: Tools like Bitwarden or 1Password can help.
                                            - **Enable Two-Factor Authentication (2FA)** for the best protection.
                                        """)
                                else:
                                    st.success("✅ This Password Appears Safe", icon="🛡️")
                                    st.metric(label="Found in Data Breaches", value="0 times")
                                    st.info("**Good practice:** Keep using strong, unique passwords for every account.")

                        elif tool == "hibp_emails" and isinstance(result.get("data"), list):
                            breaches = result.get("data")
                            if not breaches:
                                st.success("✅ No public breaches found for this email address.", icon="🛡️")
                            else:
                                st.error(f"🚨 Found in {len(breaches)} Public Data Breaches", icon="🔥")
                                st.markdown("Your email address was found in the following data breaches. It is highly recommended to change your password on these services and any other service where you used the same password.")
                                
                                for breach in breaches:
                                    with st.container(border=True):
                                        col1, col2 = st.columns([1, 4])
                                        
                                        with col1:
                                            logo_url = breach.get("LogoPath", "https://cdn-icons-png.flaticon.com/512/732/732203.png")
                                            st.image(logo_url, width=80)

                                        with col2:
                                            st.subheader(breach.get("Name", "Unknown Breach"))
                                            st.markdown(f"**Breach Date:** {breach.get('BreachDate', 'Not specified')}")

                                        compromised_data = breach.get("DataClasses", [])
                                        if compromised_data:
                                            tags_html = "".join([f"<span style='background-color:#ffebee; color:#c62828; padding: 3px 8px; border-radius:12px; margin-right:5px; font-size:0.85rem; border: 1px solid #e57373;'>{item}</span>" for item in compromised_data])
                                            st.markdown(f"**Compromised Data:** {tags_html}", unsafe_allow_html=True)

                                        description_html = breach.get("Description")
                                        if description_html:
                                            st.markdown("**Description:**")
                                            st.markdown(description_html, unsafe_allow_html=True)
                        
                        # Fallback for other tools like trufflehog, etc.
                        elif isinstance(result.get("data"), (dict, list)):
                            if not result.get("data"):
                                st.info("✅ No results returned from this tool.")
                            elif "error" in result.get("data", {}):
                                st.error(f"❌ Error: {result['data']['error']}")
                            else:
                                st.json(result["data"])
                        
                        else:
                            st.write(result)
    except Exception as e:
        st.error(f"❌ An error occurred while fetching scan history: {e}", icon="🔥")
elif selected == "About Tools":
    st.header("🛠️ Our OSINT Arsenal")
    st.markdown("An overview of the powerful, open-source tools that drive our scanning engine.")

    tools_info = {
        "🐷 TruffleHog": { "purpose": "Scans public GitHub repositories for exposed secrets.", "scans": ["Public GitHub Repositories", "API Keys & Tokens", "Passwords & Private Keys"] },
        "🔍 theHarvester": { "purpose": "Gathers emails, subdomains, and more from public sources.", "scans": ["Email Addresses", "Subdomains & DNS Records"] },
        "🕷️ SpiderFoot": { "purpose": "Automated reconnaissance to gather intelligence.", "scans": ["Domain & IP Intelligence", "Dark Web Mentions"] },
        "🕵️ Sherlock": { "purpose": "Hunts down social media accounts by username.", "scans": ["400+ Social Media Platforms", "Forums & Communities"] },
        "📧 HIBP API": { "purpose": "Checks for email and password compromise in public data breaches.", "scans": ["Leaked Emails & Passwords", "Comprehensive Breach Database"] }
    }
    for tool, info in tools_info.items():
        with st.expander(tool, expanded=True):
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
        - **3. Contact Financial Institutions:** If your credit card or bank information was exposed, contact your bank or credit card company right away to report it and request a new card.
        - **4. Enable Two-Factor Authentication (2FA):** For any affected account, enable 2FA (or MFA). This is one of the most effective ways to secure an account even if the password is known.
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
        - Public code repositories (e.g., GitHub)
        - Public text-sharing sites (e.g., Pastebin and its alternatives)
        - Publicly indexed web pages and documents found by search engines.
        - Known data breach collections that are publicly accessible.

        We **do not** access private databases, the deep web, or dark web resources. All scans are performed within the bounds of ethical open-source intelligence gathering.
        """)

    with st.expander("**Do you store my search history or results?**"):
        st.markdown("""
        Yes, the results of your scans are stored temporarily in a secure database so you can review them in the **Scan History** tab. This data is linked only to your user session and is not made public.

        For your privacy, we recommend you review your results and then delete old scan histories when you no longer need them.
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