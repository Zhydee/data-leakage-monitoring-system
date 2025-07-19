import streamlit as st
import requests
import os
import re
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Data Leakage Monitoring System",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Data Leakage Monitoring System")
st.markdown("A unified platform for monitoring data leakage across multiple open sources")

# Test backend connection
try:
    response = requests.get("http://localhost:8000/health")
    if response.status_code == 200:
        st.success("✅ Backend connection successful")
    else:
        st.error("❌ Backend connection failed")
except Exception as e:
    st.error(f"❌ Backend connection error: {str(e)}")

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.selectbox(
    "Select Page",
    ["Scanner", "About Tools", "Scan History", "Reports"]
)

if page == "Scanner":
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
            ]
        )
    
    with col2:
        st.subheader("Input Data")
        
        if data_type == "Custom Regex":
            custom_regex = st.text_input("Enter custom regex pattern:", placeholder="e.g., ^[A-Z]{2,3}-\d{4,6}$")
            search_data = st.text_area("Enter data to search:", height=100, placeholder="Enter the data you want to search for...")
        else:
            search_data = st.text_area("Enter data to search:", height=100, 
                                     placeholder=f"Enter {data_type.lower()} to search for...")
        
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
                
                with st.spinner("🔍 Scanning across all OSINT platforms..."):
                    # Placeholder for actual scanning logic
                    import time
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    tools = ["GitLeaks", "TruffleHog", "theHarvester", "SpiderFoot", "Sherlock", "LeakCheck"]
                    
                    for i, tool in enumerate(tools):
                        status_text.text(f"Running {tool}...")
                        time.sleep(1)  # Simulate scanning time
                        progress_bar.progress((i + 1) / len(tools))
                    
                    status_text.text("Scan completed!")
                    
                    st.success("🎉 Scan completed successfully!")
                    st.info("📊 Results will be available in the 'Scan History' tab")
                    
            else:
                st.error("❌ Please enter data to search")

elif page == "About Tools":
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

elif page == "Scan History":
    st.header("📊 Scan History")
    st.markdown("Recent scans from the database")

    try:
        res = requests.get("http://localhost:8000/scan-history")
        if res.status_code == 200:
            scans = res.json()
            for scan in scans:
                with st.expander(f"🔎 Scan ID {scan['scan_id']} - {scan['search_data']} ({scan['data_type']})"):
                    st.markdown(f"**Timestamp:** {scan['timestamp']}")
                    st.markdown(f"**Status:** `{scan['status']}`")
                    st.markdown("**Results:**")
                    for tool, result in scan["results"].items():
                        st.markdown(f"- **{tool}**")
                        st.json(result["data"])
                        st.caption(f"Confidence: {result['confidence']} | Severity: {result['severity']}")
        else:
            st.error("❌ Failed to fetch scan history.")
    except Exception as e:
        st.error(f"❌ Error: {e}")

    
    
    # Placeholder for scan history table
    st.info("Scan history functionality will be implemented in upcoming weeks")
    
    # Sample data structure for future implementation
    st.subheader("Sample Scan Results Structure")
    st.code("""
    {
        "scan_id": "scan_001",
        "data_type": "Email Address",
        "search_data": "user@example.com",
        "timestamp": "2024-01-15 10:30:00",
        "status": "completed",
        "results": {
            "gitleaks": {"found": 5, "repositories": ["repo1", "repo2"]},
            "trufflehog": {"found": 3, "secrets": ["api_key", "password"]},
            "theharvester": {"found": 10, "emails": ["email1", "email2"]},
            "spiderfoot": {"found": 8, "domains": ["domain1", "domain2"]},
            "sherlock": {"found": 12, "platforms": ["twitter", "github"]},
            "leakcheck": {"found": 3, "breaches": ["exploit.in", "collection1"]}
        }
    }
    """, language="json")

elif page == "Reports":
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