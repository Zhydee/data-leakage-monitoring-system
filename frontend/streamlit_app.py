import streamlit as st
from streamlit_option_menu import option_menu
import tldextract
from datetime import datetime
import locale
from zoneinfo import ZoneInfo  # ✅ modern timezone handling
import requests
import random
import os
import re
from dotenv import load_dotenv

load_dotenv()

st.markdown("""
    <style>
        [data-testid="collapsedControl"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

# Map display name to backend name
backend_data_type_map = {
"Email Address": "email",
"Phone Number": "phone",
"Username": "username",
"Domain Name": "domain",
"IP Address": "ip",
"Credit Card Number": "credit_card",
"IC Number": "ic",
"API Keys/Tokens": "api_key",
"Custom Regex": "custom"
  }
# Reverse map to display correct label in Scan History
display_name_map = {v: k for k, v in backend_data_type_map.items()}
           
st.markdown("""
    <style>
        /* Remove sidebar collapse button */
        section[data-testid="stSidebar"] > div:first-child button[title="Hide sidebar"] {
            display: none;
        }
        /* Optional: prevent collapsing sidebar area */
        div[data-testid="collapsedControl"] {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)
st.set_page_config(
    page_title="Data Leakage Monitoring System",
    page_icon="🔍",
    layout="wide"
)

st.markdown("""
<h1 style='text-align: center; color: white; font-size: 40px; margin-top: -90px;'>
🔍 <span style='color:#f39c12;'>Data Leakage Monitoring System</span>
</h1>
<p style='text-align: center; color: #CCCCCC; font-size: 16px; margin-top: -10px;'>
A unified platform for monitoring data leakage across multiple open sources.
</p>
""", unsafe_allow_html=True)


# Test backend connection
try:
    response = requests.get("http://localhost:8000/health")
    if response.status_code == 200:
        st.success("✅ Backend connection successful")
    else:
        st.error("❌ Backend connection failed")
except Exception as e:
    st.error(f"❌ Backend connection error: {str(e)}")


with st.sidebar:
        # Logo and title
 selected = option_menu(
    
    menu_title=None,
    options=["Homepage", "Scanner", "About Tools", "Scan History", "Reports"],
    icons=["house", "search", "tools", "clock-history", "bar-chart-line"],
    default_index=0,  # Default is Homepage
    styles={
        "container": {
            "padding": "10px",
            "background-color": "#f7f7f7",  # light gray sidebar
            "border-radius": "8px"
        },
        "icon": {
            "color": "#f39c12",  # orange icons
            "font-size": "18px"
        },
        "nav-link": {
            "font-size": "16px",
            "text-align": "left",
            "margin": "5px",
            "padding": "10px",
            "color": "#333333",  # dark gray text
            "border-radius": "6px"
        },
        "nav-link-selected": {
            "background-color": "#e0e0e0",  # light gray selection
            "font-weight": "bold",
            "color": "#000000"  # black text
        }
    }
)



if selected == "Scanner":
    st.header("🔍 Data Leakage Scanner")
    st.markdown("Select data type and input information to scan across all OSINT platforms")
    
    # Data type selection - simplified without regex patterns display
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Data Type")
        data_type = st.selectbox(
            "Choose data type:",
            [
                "Email Address",
                "Phone Number", 
                "Username",
                "Domain Name",
                "IP Address",
                "Credit Card Number",
                "IC Number",
                "API Keys/Tokens",
                "Custom Regex"
            ],
             help="Select the type of data you want to scan for leaks. E.g., an email address, username, or IC number."
        )
    
    with col2:
        st.subheader("Input Data")
        
        if data_type == "Custom Regex":
            custom_regex = st.text_input(
                "Enter custom regex pattern:",
                placeholder="e.g., ^[A-Z]{2,3}-\\d{4,6}$",
                help="Define your own pattern using regular expressions."
            )
            search_data = st.text_area(
                "Enter data to search:",
                height=100,
                placeholder="Enter the data you want to search for...",
                help="Paste your list of values (e.g., multiple usernames or IC numbers) to search using your custom regex."
            )
        else:
            help_messages = {
                "Email Address": "Check if your email has been leaked in public data breaches. e.g., user@example.com",
                "Phone Number": "Find out if your phone number is exposed in public sources. Format: 012-3456789",
                "Username": "Scan the internet for social media and forum accounts matching a username.",
                "Domain Name": "Discover if a domain (e.g., example.com) has been associated with leaked data.",
                "IP Address": "Check if your IP address is publicly exposed or mentioned.",
                "Credit Card Number": "Scan for potential credit card leaks (input is masked and protected).",
                "IC Number": "Monitor Malaysian IC number exposure. Format: xxxxxx-xx-xxxx",
                "API Keys/Tokens": "Scan public platforms for exposed API keys or secret tokens."
            }

            search_data = st.text_area(
                "Enter data to search:",
                height=100,
                placeholder=f"Enter {data_type.lower()} to search for...",
                help=help_messages.get(data_type, "Enter the value(s) to search.")
            )
        
        # Scan button
        st.markdown("---")
        scan_button = st.button("🚀 Start Comprehensive Scan", type="primary", use_container_width=True)
        
        if scan_button:
            if search_data:
                # Regex patterns for validation (hidden from UI)
                regex_patterns = {
                    "Email Address": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                    "Phone Number": r"(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})",
                    "Username": r"^[a-zA-Z0-9_-]{3,16}$",
                    "Domain Name": r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$",
                    "IP Address": r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
                    "Credit Card Number": r"^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})$",
                    "IC Number": r"^\d{6}-\d{2}-\d{4}$",
                    "API Keys/Tokens": r"^[A-Za-z0-9+/=]{20,}$",
                    "Custom Regex": ""
                }
     
                backend_data_type = backend_data_type_map[data_type]
                # Validate input against regex pattern
                if data_type != "Custom Regex":
                    pattern = regex_patterns[data_type]
                    if not re.search(pattern, search_data.strip()):
                        st.error(f"❌ Input doesn't match {data_type} format")
                        st.stop()
                else:
                    if not custom_regex:
                        st.error("❌ Please enter a custom regex pattern")
                        st.stop()
                
                # Show scanning progress
                st.success("✅ Input validated successfully")
                
                with st.spinner("🚀 Initiating scan..."):
                    # Placeholder for actual scanning logic
                    payload = {
                                "data_type": backend_data_type,
                                "search_data": search_data.strip()
                    }

                    if data_type == "Custom Regex":
                        payload["custom_regex"] = custom_regex

                    try:
                        response = requests.post("http://localhost:8000/scan/start", json=payload)

                        if response.status_code == 200:
                            result = response.json()
                            st.success("🎉 Scan started successfully!")
                            st.info(f"🆔 Scan Job ID: `{result['job_id']}`")
                            st.info("📊 Results will be available in the 'Scan History' tab")

                        else:
                            st.error(f"❌ Scan failed: {response.status_code} - {response.text}") 
                    except Exception as e:
                        st.error(f"❌ Error initiating scan: {str(e)}")
                    
            else:
                st.error("❌ Please enter data to search")

elif selected == "About Tools":
    st.header("🛠️ OSINT Tools Overview")
    st.markdown("Learn about the powerful tools used in our comprehensive scanning platform")
    
    # Tool categories
    st.subheader("🔍 Our Scanning Arsenal")
    
    # GitLeaks
    with st.expander("🔍 GitLeaks - Git Repository Scanner"):
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("**Purpose:**")
            st.markdown("Git repository scanning for secrets and sensitive data")
            st.markdown("**Status:** ✅ Active")
        with col2:
            st.markdown("**What it scans:**")
            st.markdown("- Git repositories and commit history")
            st.markdown("- API keys and authentication tokens")
            st.markdown("- Passwords and secrets in code")
            st.markdown("- Configuration files with sensitive data")
            st.markdown("- Database connection strings")
    
    # TruffleHog
    with st.expander("🔍 TruffleHog - Advanced Secret Scanner"):
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("**Purpose:**")
            st.markdown("Advanced secret scanning with high accuracy")
            st.markdown("**Status:** ✅ Active")
        with col2:
            st.markdown("**What it scans:**")
            st.markdown("- High-entropy strings and secrets")
            st.markdown("- OAuth tokens and API keys")
            st.markdown("- Private keys and certificates")
            st.markdown("- Database credentials")
            st.markdown("- Cloud service credentials")
    
    # theHarvester
    with st.expander("🔍 theHarvester - Email & Domain Intelligence"):
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("**Purpose:**")
            st.markdown("Email and domain harvesting from public sources")
            st.markdown("**Status:** ✅ Active")
        with col2:
            st.markdown("**What it scans:**")
            st.markdown("- Email addresses from search engines")
            st.markdown("- Subdomains and DNS records")
            st.markdown("- Public directory listings")
            st.markdown("- Social media mentions")
            st.markdown("- Professional networking sites")
    
    # SpiderFoot
    with st.expander("🔍 SpiderFoot - Automated Reconnaissance"):
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("**Purpose:**")
            st.markdown("Comprehensive automated reconnaissance")
            st.markdown("**Status:** ✅ Active")
        with col2:
            st.markdown("**What it scans:**")
            st.markdown("- Domain and IP address intelligence")
            st.markdown("- Dark web mentions")
            st.markdown("- Social media profiles")
            st.markdown("- Data breach databases")
            st.markdown("- Public records and documents")
    
    # Sherlock
    with st.expander("🔍 Sherlock - Social Media Hunter"):
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("**Purpose:**")
            st.markdown("Social media username search across platforms")
            st.markdown("**Status:** ✅ Active")
        with col2:
            st.markdown("**What it scans:**")
            st.markdown("- 400+ social media platforms")
            st.markdown("- Professional networking sites")
            st.markdown("- Gaming platforms")
            st.markdown("- Forums and communities")
            st.markdown("- Dating and lifestyle platforms")

         # Leakcheck
        with st.expander("🔍 Leakcheck.io - Email Breach Lookup"):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown("**Purpose:**")
                st.markdown("Checks if your email has appeared in public data breaches")
                st.markdown("**Status:** ✅ Active")
            with col2:
                st.markdown("**What it scans:**")
                st.markdown("- Leaked emails and password hashes")
                st.markdown("- Sources like Exploit.in, Collection1, etc.")
                st.markdown("- Real-time breach database using free API")

    
    st.markdown("---")
    
    # Scanning Process
    st.subheader("⚙️ How Our Scanning Works")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**1. Input Processing**")
        st.markdown("- Validates your input format")
        st.markdown("- Prepares data for scanning")
        st.markdown("- Selects appropriate tools")
    
    with col2:
        st.markdown("**2. Parallel Scanning**")
        st.markdown("- Runs all tools simultaneously")
        st.markdown("- Monitors progress in real-time")
        st.markdown("- Handles errors gracefully")
    
    with col3:
        st.markdown("**3. Results Analysis**")
        st.markdown("- Aggregates findings from all tools")
        st.markdown("- Removes duplicates")
        st.markdown("- Provides risk assessment")
    
    st.markdown("---")
    
    # Data Types Supported
    st.subheader("📊 Supported Data Types")
    
    data_types_info = {
        "Email Address": "Comprehensive email scanning across platforms and databases",
        "Phone Number": "Phone number exposure checking and verification",
        "Username": "Username availability and exposure analysis",
        "Domain Name": "Domain intelligence and subdomain discovery",
        "IP Address": "IP address reputation and exposure analysis",
        "Credit Card Number": "Credit card exposure in data breaches (masked results)",
        "IC Number": "Malaysian IC number exposure monitoring",
        "API Keys/Tokens": "API key and authentication token exposure",
        "Custom Regex": "Custom pattern matching for specific data formats"
    }
    
    for data_type, description in data_types_info.items():
        st.markdown(f"**{data_type}:** {description}")
    
    st.markdown("---")
    
    # Security & Privacy
    st.subheader("🔒 Security & Privacy")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Data Protection:**")
        st.markdown("- All scans are encrypted")
        st.markdown("- No data stored permanently")
        st.markdown("- Results auto-deleted after 30 days")
        st.markdown("- No third-party data sharing")
    
    with col2:
        st.markdown("**Ethical Scanning:**")
        st.markdown("- Only public data sources")
        st.markdown("- Respects robots.txt files")
        st.markdown("- Rate-limited requests")
        st.markdown("- No illegal or harmful activities")
    
    st.success("🛡️ **Your Privacy Matters:** We only scan publicly available information and never store your sensitive data.")

elif selected == "Scan History":
    st.header("📊 Scan History")
    st.markdown("Recent scans from the database")

    try:
        res = requests.get("http://localhost:8000/scan-history")
        if res.status_code == 200:
            scans = res.json()
            for scan in scans:
                with st.expander(f"🔎 Scan ID {scan['scan_id']} - {scan['search_data']} ({scan['data_type']})"):
                                        # Parse timestamp
                  # Convert UTC timestamp to Malaysia time
                    dt = datetime.fromisoformat(scan["timestamp"]).replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kuala_Lumpur"))

                    # Format Malay date
                    try:
                        locale.setlocale(locale.LC_TIME, "ms_MY.utf8")
                    except:
                        locale.setlocale(locale.LC_TIME, "")

                    malay_date = dt.strftime("%d %B %Y")

                    # Format English time (for AM/PM)
                    try:
                        locale.setlocale(locale.LC_TIME, "en_US.utf8")
                    except:
                        locale.setlocale(locale.LC_TIME, "C")

                    english_time = dt.strftime("%I:%M %p")

                    # Show final result
                    st.markdown(f"**🕒 Timestamp:** {malay_date}, {english_time}")

                    st.markdown(f"**Status:** `{scan['status']}`")
                    st.markdown("**Results:**")
                # Explanations for each tool
                    tool_descriptions = {
                        "sherlock": "This tool checks social media websites to see if your username is being used anywhere.",
                        "leakcheck": "This tool checks if your email has been found in any data leaks or hacked websites.",
                        "gitleaks": "This tool looks through public code to find things like passwords or private information that were shared by mistake.",
                        "trufflehog": "This tool searches deeply in code to find secret information that should not be public, like passwords or keys.",
                        "theharvester": "This tool collects emails and other details about a website from public search engines.",
                        "spiderfoot": "This tool gathers information about websites, IP addresses, and even mentions on the dark web."
                    }

                    for tool, result in scan["results"].items():
                        st.markdown(f"### 🔧 {tool.capitalize()}")

                        # Show explanation
                        if tool in tool_descriptions:
                            with st.expander("ℹ️ What is this tool?"):
                                st.info(tool_descriptions[tool])

                        # Display results
                        if tool == "sherlock" and isinstance(result["data"], list):
                            st.markdown(f"🔎 Found `{len(result['data'])}` social profiles:")
                            for url in result["data"]:
                                ext = tldextract.extract(url)
                                platform = ext.domain.capitalize()
                                st.markdown(f"""
                                    <div style='border:1px solid #ddd; border-radius:8px; padding:12px; margin-bottom:10px; background-color:#f9f9f9'>
                                        <b>🛰 Platform:</b> {platform}<br>
                                        <b>🔗 Link:</b> <a href="{url}" target="_blank">{url}</a>
                                    </div>
                                    """, unsafe_allow_html=True)
                        else:
                            if tool == "leakcheck":
                                if result["data"] == []:
                                    st.info("✅ No breaches found.")
                                elif isinstance(result["data"], dict) and "error" in result["data"]:
                                    st.warning(f"⚠️ Error: {result['data']['error']}")
                                else:
                                    st.json(result["data"])
                            else:
                                st.json(result["data"])


        else:
            st.error("❌ Failed to fetch scan history.")
    except Exception as e:
        st.error(f"❌ Error: {e}")
elif selected == "Reports":
    st.header("📈 Security Reports")
    st.markdown("View comprehensive analysis of your security scans")
    
    st.info("📊 Detailed security reports will be available here after completing scans")
    
    # Simple explanation for general users
    st.subheader("What You'll Get:")
    st.markdown("""
    - **📋 Summary Report**: Easy-to-understand overview of findings
    - **🔍 Detailed Analysis**: Complete breakdown of each security check
    - **📊 Risk Assessment**: Understanding what the findings mean for you
    - **💡 Recommendations**: Simple steps to improve your security
    - **📁 Export Options**: Download reports as PDF or spreadsheet
    """)
    
    st.markdown("---")
    st.success("🛡️ **Good to know:** All reports are written in simple language so you can understand your security status without technical knowledge.")

elif selected == "Homepage":
    

    # Modern Homepage UI
    st.markdown("""
        <div style='background: linear-gradient(to right, #f8f9fa, #ffffff); padding: 3rem 2rem; border-radius: 12px; text-align: center;'>
            <h1 style='font-size: 3rem; color: #2c3e50;'>👋 Welcome to the Data Leakage Monitoring System</h1>
            <p style='font-size: 1.25rem; color: #555;'>An open-source platform to help you monitor, detect, and protect your personal data exposure online.</p>
            <p style='font-size: 1rem; color: #777; max-width: 700px; margin: auto;'>
                Whether you're a student, teacher, freelancer, or concerned internet user — our system helps you find exposed emails, IC numbers, phone numbers, and even API keys on public platforms like GitHub and Pastebin.
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🔍 What This System Can Do")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.image("https://cdn-icons-png.flaticon.com/512/1170/1170627.png", width=60)
        st.subheader("Scan for Leaks")
        st.write("Search public platforms for exposed data like emails, IC numbers, or API keys.")

    with col2:
        st.image("https://cdn-icons-png.flaticon.com/512/751/751381.png", width=60)
        st.subheader("Understand Results")
        st.write("Easy-to-read results show what was found, where it was found, and why it matters.")

    with col3:
        st.image("https://cdn-icons-png.flaticon.com/512/1828/1828640.png", width=60)
        st.subheader("Protect Your Identity")
        st.write("Take simple steps to improve your security with our non-technical recommendations.")

    tips = [
        "🔐 Never reuse your password across multiple websites.",
        "📧 Be cautious of emails asking for personal information.",
        "🔍 You can use this system to check for leaks of your IC or phone number.",
        "🧾 Always double-check URLs before clicking links online.",
        "🔑 Use a password manager to generate and store strong, unique passwords.",
        "⚠️ Do not share OTPs or verification codes with anyone — even if they claim to be from a bank.",
        "🔎 Look for HTTPS and lock symbols when browsing sensitive websites.",
        "📱 Be careful when scanning QR codes from untrusted sources.",
    ]

    # Optional: Refresh tip on page reload
    st.markdown("### 💡 Security Tip of the Day")
    st.info(random.choice(tips))

    st.markdown("---")
    st.markdown("### 👥 Who Is This For?")
    st.markdown("""
        - 🧑‍🎓 **Students** uploading assignments with sensitive data<br>
        - 👩‍🏫 **Teachers** managing class files online<br>
        - 👨‍💻 **Freelancers** and small business owners without access to enterprise tools<br>
        - 👵 **Senior users** who want a simple way to check their email or IC safety
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🌐 Tools Behind the System")
    st.markdown("""
        - **GitLeaks**, **TruffleHog** – Detect exposed secrets on GitHub  
        - **Sherlock** – Check for exposed usernames on 400+ social platforms  
        - **LeakCheck.io** – Verify email addresses against breach databases  
        - **SpiderFoot**, **theHarvester** – Reconnaissance tools to collect public OSINT
    """)

    st.success("🔐 We never store your data. Everything runs securely and ethically using only public sources.")

    st.markdown("<div id='start'></div>", unsafe_allow_html=True)
