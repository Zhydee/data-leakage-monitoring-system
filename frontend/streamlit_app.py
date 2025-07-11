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
st.markdown("A unified platform for monitoring data leakage across multiple sources")

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
    st.markdown("Select data type and input information to scan across all platforms")
    
    # Data type selection with predefined regex patterns
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
        
        # Display regex pattern for selected data type
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
        
        st.info(f"**Pattern:** `{regex_patterns[data_type]}`")
    
    with col2:
        st.subheader("Input Data")
        
        if data_type == "Custom Regex":
            custom_regex = st.text_input("Enter custom regex pattern:", placeholder="e.g., ^[A-Z]{2,3}-\d{4,6}$")
            search_data = st.text_area("Enter data to search:", height=100, placeholder="Enter the data you want to search for...")
        else:
            search_data = st.text_area("Enter data to search:", height=100, 
                                     placeholder=f"Enter {data_type.lower()} to search for...")
        
        # Tools selection
        st.subheader("Data Gathering Tools")
        st.markdown("All tools will be used automatically:")
        
        col_tool1, col_tool2 = st.columns(2)
        with col_tool1:
            st.checkbox("🔍 GitLeaks", value=True, disabled=True, help="Git repository scanning")
            st.checkbox("🔍 TruffleHog", value=True, disabled=True, help="Secret scanning")
            st.checkbox("🔍 theHarvester", value=True, disabled=True, help="Email/domain harvesting")
        
        with col_tool2:
            st.checkbox("🔍 SpiderFoot", value=True, disabled=True, help="Automated reconnaissance")
            st.checkbox("🔍 Sherlock", value=True, disabled=True, help="Social media username search")
            st.checkbox("🔍 Custom Scanners", value=True, disabled=True, help="Additional scanning tools")
        
        # Scan button
        st.markdown("---")
        scan_button = st.button("🚀 Start Comprehensive Scan", type="primary", use_container_width=True)
        
        if scan_button:
            if search_data:
                # Validate input against regex pattern
                if data_type != "Custom Regex":
                    pattern = regex_patterns[data_type]
                    if not re.search(pattern, search_data.strip()):
                        st.error(f"❌ Input doesn't match {data_type} pattern")
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
                    
                    tools = ["GitLeaks", "TruffleHog", "theHarvester", "SpiderFoot", "Sherlock"]
                    
                    for i, tool in enumerate(tools):
                        status_text.text(f"Running {tool}...")
                        time.sleep(1)  # Simulate scanning time
                        progress_bar.progress((i + 1) / len(tools))
                    
                    status_text.text("Scan completed!")
                    
                    st.success("🎉 Scan completed successfully!")
                    st.info("📊 Results will be available in the 'Scan History' tab")
                    
            else:
                st.error("❌ Please enter data to search")

elif page == "Scan History":
    st.header("📊 Scan History")
    st.markdown("View and manage your previous scans")
    
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
            "sherlock": {"found": 12, "platforms": ["twitter", "github"]}
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