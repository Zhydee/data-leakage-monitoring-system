from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")
import os
# --- RATE LIMITING IMPORTS ---
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter # Import the new shared limiter
# --- IMPORTS FOR SCHEDULER ---
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.utils.cleanup import delete_old_scan_records
from app.utils.scheduler_jobs import run_automated_scans 
# --- NEW: STRUCTURED LOGGING IMPORTS ---
import logging
from contextlib import asynccontextmanager 
import asyncio

from app.api.routes import scan # Import the scan router
from app.api.routes import history
from app.api.routes import scan, history, monitoring # Add monitoring

load_dotenv()

# --- Configure logger ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Initialize the scheduler ---
scheduler = AsyncIOScheduler()

# --- A function to start the scheduler and add the job ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    logger.info("Starting up the application...")
    # Schedule the cleanup job to run once every day at 3:00 AM server time
    scheduler.add_job(delete_old_scan_records, 'interval', days=1, id="daily_cleanup_job")
    # --- NEW: Schedule the automated scanning job to run every 6 hours ---
    scheduler.add_job(run_automated_scans, 'interval', hours=12, id="automated_scanning_job")
    scheduler.start()
    logger.info("Scheduler started. Cleanup and Automated Scanning jobs have been scheduled.")
    
    yield # The application is now running

    # Code below yield runs on shutdown
    logger.info("Shutting down the application...")
    scheduler.shutdown()
    logger.info("Scheduler has been shut down.")

app = FastAPI(
    title="Data Leakage Monitor System",
    description="A unified system for comprehensive data leakage monitoring across multiple platforms",
    version="1.0.0",
    # --- NEW: Add lifespan events for scheduler ---
    lifespan=lifespan
)

# --- The limiter to the app's state ---
app.state.limiter = limiter
# --- The exception handler for rate limit errors ---
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router, prefix="/scan")
app.include_router(history.router)
# --- The monitoring router ---
app.include_router(monitoring.router, prefix="/monitoring")

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



app.include_router(scan.router, prefix="/scan") 