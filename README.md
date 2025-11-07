# Data Leakage Monitoring System

A comprehensive, web application designed to help individuals and small organizations monitor for unintentional data exposure across the public internet. This system integrates a suite of powerful OSINT tools into a single, user-friendly interface, providing actionable intelligence to help users secure their digital footprint.

This project was developed as a Final Year Project for a degree in Cybersecurity.

## Core Features

*   **Multi-Tool Scanning Engine:** Leverages a suite of industry-standard OSINT tools to provide comprehensive coverage for various data types.
*   **Automated Monitoring & Alerting:** Allows users to add sensitive assets for continuous, scheduled monitoring. The system intelligently detects new findings and generates alerts.
*   **Unified Dashboard:** Aggregates findings into a high-level dashboard with KPIs and visualizations for an at-a-glance view of a user's security posture.
*   **Detailed & Actionable Reports:** Presents enriched scan results in a clear, easy-to-understand format, complete with risk analysis and step-by-step "playbooks" for remediation.
*   **Secure by Design:** Built with a strong focus on security, incorporating features like rate limiting, secure authentication, strict data retention policies, and a robust production-ready architecture using Docker.
*   **User Authentication:** Secure user registration and login provided by the Auth0 identity platform.

## Architecture & Technology Stack

The system is built on a modern, decoupled architecture using a containerized approach for scalability and portability.

*   **Frontend:** A responsive and interactive user interface built with **Streamlit**.
*   **Backend API:** A robust and scalable API built with **FastAPI**.
*   **Database:** A persistent **PostgreSQL** database for storing scan history, user assets, and alerts.
*   **Deployment:** Fully containerized with **Docker** and **Docker Compose** for consistent, isolated, and portable deployments.
*   **Background Tasks:**
    *   **APScheduler:** Manages all scheduled tasks, including automated monitoring scans and the data retention policy.
    *   **FastAPI BackgroundTasks:** Handles immediate, "fire-and-forget" tasks, such as the initial scan after a new asset is added.

---

## Integrated OSINT Arsenal

The system's detection capabilities are powered by a carefully selected suite of open-source tools:

| Tool | Purpose | Data Types Scanned |
| :--- | :--- | :--- |
| **TruffleHog** | Scans public GitHub repositories for exposed secrets. | API Keys, Passwords, Private Keys |
| **Have I Been Pwned**| Checks against a massive database of known data breaches. | Leaked Emails, Exposed Passwords |
| **Sherlock** | Hunts for usernames across hundreds of social media sites. | Social Media Profiles, Usernames |
| **Google Custom Search**| Uses targeted queries to find data on the public web. | Full Names, Emails, Phone Numbers, IC Numbers |

---

## Security Features Implemented

Security was a primary consideration throughout the development of this project.

| Feature | Primary Principle | Implementation Details |
| :--- | :--- | :--- |
| **User Authentication** | Authentication | Securely authenticates users via **Auth0** using the OpenID Connect (OIDC) standard. |
| **Access Control** | Authorization | Private pages (Dashboard, Monitoring) are protected and only accessible to logged-in users. |
| **Data Retention Policy**| Confidentiality | An automated **APScheduler** job permanently deletes all scan records older than 14 days. |
| **SQL Injection Prevention**| Integrity | All database interactions are handled through the **SQLAlchemy ORM**, which uses parameterized queries. |
| **Rate Limiting** | Availability | The **slowapi** library limits API requests per IP, protecting the backend from DoS attacks. |
| **Secure Secrets** | Confidentiality | All sensitive credentials (API keys, secrets) are loaded from **environment variables (`.env`)** and are never hardcoded. |
| **Defense-in-Depth** | Integrity | User input is validated with regex on both the **frontend** (for UX) and **backend** (for security). |

---

## Local Development Quick Start

### Prerequisites

*   Docker and Docker Compose
*   An `.env` file for the `frontend` and `backend` (see below for required variables)

### Running the Application

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/your-project.git
    cd your-project
    ```

2.  **Create your environment files:**
    *   Create `frontend/.env` with your `AUTH0_*` variables.
    *   Create `backend/.env` with your `DATABASE_URL` and all your tool API keys (`HIBP_API_KEY`, etc.).

3.  **Launch with Docker Compose:**
    *   Navigate to the `docker/` directory.
    *   Run the command:
        ```bash
        docker compose up --build
        ```

4.  **Access the application:**
    *   **Frontend UI:** `http://localhost:8501`
    *   **Backend API Docs:** `http://localhost:8000/docs`

---

## Future Work & Potential Improvements

*   **Data Normalization:** Implement an analysis layer to correlate findings from different tools into a single, contextualized risk entity.
*   **Dark Web Monitoring:** Integrate tools or services that specifically monitor dark web forums and marketplaces.
*   **Enhanced Alerting:** Add more notification channels, such as Telegram or Slack, for new alerts.
