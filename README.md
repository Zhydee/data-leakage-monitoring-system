# Data Leakage Monitoring System

A comprehensive OSINT reconnaissance tool for monitoring data leakage with secure, scalable architecture.

## Quick Start

1. Clone repository
2. Copy `.env.example` to `.env` and configure
3. Run with Docker: `docker-compose up`
4. Access frontend: http://localhost:8501
5. Access API docs: http://localhost:8000/docs

## Development Setup

See `docs/SETUP.md` for detailed setup instructions.

## Architecture

- **Frontend:** Streamlit
- **Backend:** FastAPI, HIBP API
- **Database:** PostgreSQL
- **Tools:** GitLeaks, TruffleHog, SpiderFoot, theHarvester, Sherlock
- **Scheduling:** Celery + Redis OR schedule Python module
- **Alerts:** SMTP for Email, Telegram Bot 
- **Deployment:**Docker

Security Features
🔒 Rate Limiting

API Rate Limiting: Configurable request limits per user/IP
Tool Usage Limits: Prevents abuse of resource-intensive OSINT tools
Bypass Protection: Multiple layers to prevent rate limit circumvention

🛡️ CAPTCHA Protection

Interactive CAPTCHA: Human verification for sensitive operations
Adaptive CAPTCHA: Difficulty increases with suspicious activity
Bot Detection: Advanced algorithms to identify automated requests
Session Validation: CAPTCHA tokens integrated with user sessions

🗃️ Temporary Storage

Data Retention: Configurable automatic cleanup of scan results
Secure Deletion: Cryptographic erasure of sensitive data
Memory Management: Efficient handling of large scan datasets
Privacy Compliance: Automated data purging for regulatory compliance

🔍 OSINT Tools Integration

GitLeaks: Secret detection in repositories
TruffleHog: Advanced credential scanning
SpiderFoot: Comprehensive reconnaissance
theHarvester: Email and subdomain enumeration
Sherlock: Social media username analysis

📊 Monitoring & Analytics

Real-time Dashboards: Live scan status and results
Historical Analysis: Trend analysis and reporting
Alert System: Configurable notifications for data leaks
Export Capabilities: Multiple format support (JSON, CSV, PDF)

🔐 Security & Privacy

End-to-end Encryption: All data encrypted in transit and at rest
User Authentication: JWT-based secure access control
Audit Logging: Comprehensive activity tracking