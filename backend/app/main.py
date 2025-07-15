from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.api.routes import scan # Import the scan router
import os

load_dotenv()

app = FastAPI(
    title="OSINT Data Leakage Monitor System",
    description="A unified system for comprehensive data leakage monitoring across multiple platforms",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Data Leakage Monitor System is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "data-leakage-monitor-system"}

@app.get("/supported-data-types")
async def get_supported_data_types():
    """Return supported data types and their regex patterns"""
    return {
        "data_types": {
            "email": {
                "name": "Email Address",
                "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                "description": "Standard email address format"
            },
            "phone": {
                "name": "Phone Number",
                "pattern": r"^(\+?60|0)1[0-9]{1}-?[0-9]{7,8}$",
                "description": "US phone number format"
            },
            "username": {
                "name": "Username",
                "pattern": r"^[a-zA-Z0-9_-]{3,16}$",
                "description": "Standard username format"
            },
            "domain": {
                "name": "Domain Name",
                "pattern": r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$",
                "description": "Domain name format"
            },
            "ip": {
                "name": "IP Address",
                "pattern": r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
                "description": "IPv4 address format"
            },
            "credit_card": {
                "name": "Credit Card Number",
                "pattern": r"^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})$",
                "description": "Credit card number format"
            },
            "ic": {
                "name": "IC Number",
                "pattern": r"^\d{6}-\d{2}-\d{4}$",
                "description": "Malaysian IC number format (YYMMDD-PB-GGGG)"
            },
            "api_key": {
                "name": "API Keys/Tokens",
                "pattern": r"^[A-Za-z0-9+/=]{20,}$",
                "description": "API key/token format"
            }
        }
    }

@app.get("/available-tools")
async def get_available_tools():
    """Return available OSINT tools and their capabilities"""
    return {
        "tools": {
            "gitleaks": {
                "name": "GitLeaks",
                "description": "Git repository scanning for secrets",
                "capabilities": ["git_repos", "secrets", "api_keys"],
                "status": "active"
            },
            "trufflehog": {
                "name": "TruffleHog",
                "description": "Advanced secret scanning",
                "capabilities": ["secrets", "passwords", "tokens"],
                "status": "active"
            },
            "theharvester": {
                "name": "theHarvester",
                "description": "Email and domain harvesting",
                "capabilities": ["emails", "domains", "subdomains"],
                "status": "active"
            },
            "spiderfoot": {
                "name": "SpiderFoot",
                "description": "Automated reconnaissance",
                "capabilities": ["domains", "ips", "social_media", "dark_web"],
                "status": "active"
            },
            "sherlock": {
                "name": "Sherlock",
                "description": "Social media username search",
                "capabilities": ["usernames", "social_media", "profiles"],
                "status": "active"
            }
        }
    }

# Placeholder endpoints for future implementation
@app.post("/scan/start")
async def start_scan():
    """Start a comprehensive OSINT scan"""
    return {"message": "Scan endpoint will be implemented in Week 2"}

@app.get("/scan/{scan_id}")
async def get_scan_status(scan_id: str):
    """Get scan status and results"""
    return {"message": f"Scan status endpoint for {scan_id} will be implemented in Week 2"}

@app.get("/scans")
async def get_scan_history():
    """Get scan history"""
    return {"message": "Scan history endpoint will be implemented in Week 2"}

app.include_router(scan.router, prefix="/scan") 