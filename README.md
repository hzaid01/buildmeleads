# BuildMeLeads — Open-Source Local Lead Discovery & Outreach Engine

BuildMeLeads is a complete, self-hostable B2B lead generation and cold outreach platform built for agencies and service providers. It discovers local businesses (plumbers, roofers, HVAC, electricians, etc.) with weak Google Business Profiles (GBP), enriches their contact information, generates concise AI-personalized email copy with Groq LLMs, and executes compliant multi-channel outreach via Gmail OAuth or SendGrid.

---

## 🌟 Key Features

- **Google Maps Scraping**: Native integration with containerized `gosom` scraper (fast, free, self-hosted) with optional Apify cloud scraper fallback.
- **GBP Weakness Detection**: Automatically evaluates missing websites, unverified profiles, poor review volume, low review ratings, and missing contact information.
- **Deep Lead Enrichment**: Fast HTTP metadata extraction with optional headless Playwright browser rendering to scrape email addresses, phone numbers, and social links.
- **AI-Personalized Outreach (Groq)**: Generates high-converting, 1–2 sentence contextual cold outreach referencing specific observable profile gaps rather than generic sales templates.
- **Multi-Tenant Architecture**: Complete tenant isolation in SQLite with Argon2id password hashing, secure session management, and dedicated campaign workspaces.
- **Responsible Outreach Safeguards**:
  - **Recipient Local Timezone Window**: Automatically restricts sends to recipient business hours (Monday–Friday, 9:00 AM – 5:00 PM).
  - **Human-like Jitter**: Enforces randomized 15–45 minute delays between dispatches.
  - **Circuit Breakers**: Automatically halts campaigns if bounce rates exceed 5% or spam complaints are detected.
  - **Suppression & Unsubscribe Engine**: Global and campaign-level suppression lists with instant opt-out handling.
- **Multi-Provider Email Dispatch**:
  - **Gmail OAuth 2.0**: Native `gmail.send` integration with encrypted at-rest refresh tokens.
  - **SendGrid API**: High-volume transactional sending with webhook signature verification.

---

## 🏗️ Architecture Overview

```
                          ┌──────────────────────────┐
                          │   Node.js Dashboard      │
                          │   (Express / Port 3000)  │
                          └────────────┬─────────────┘
                                       │
                  ┌────────────────────┼────────────────────┐
                  ▼                                         ▼
      ┌───────────────────────┐                 ┌───────────────────────┐
      │  gosom Scraper Engine │                 │  Python Lead Engine   │
      │  (Docker / Port 8080) │                 │  (FastAPI/ Port 8000) │
      └───────────────────────┘                 └───────────┬───────────┘
                                                            │
                                  ┌─────────────────────────┼─────────────────────────┐
                                  ▼                         ▼                         ▼
                        ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
                        │ SQLite Database │       │    Groq AI      │       │ Gmail / SendGrid│
                        │ (data/leads.db) │       │ (Outreach Copy) │       │ (Email Dispatch)│
                        └─────────────────┘       └─────────────────┘       └─────────────────┘
```

---

## 🚀 Quick Start & Self-Hosting Guide

### Prerequisites
- **Node.js** (v18 or v20 LTS)
- **Python** (v3.10, v3.11, or v3.12)
- **Docker & Docker Compose** (for running the local Google Maps scraper)

---

### Step 1: Clone & Configure

```bash
git clone https://github.com/hzaid01/buildmeleads.git
cd buildmeleads

# Copy environment configuration
cp .env.example .env
```

Open `.env` and fill in your configuration:
- `GROQ_API_KEY`: Get your free key at [console.groq.com](https://console.groq.com).
- `GMAIL_TOKEN_ENCRYPTION_KEY`: Generate a 32-byte Fernet key:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- *(Optional)* `GOOGLE_OAUTH_CLIENT_ID` & `GOOGLE_OAUTH_CLIENT_SECRET`: For Gmail OAuth sending.

---

### Step 2: Start the Local Scraper (Docker)

```bash
docker compose up -d
```
Verify the scraper is listening on `http://localhost:8080`.

---

### Step 3: Install Dependencies & Run

#### Using PowerShell / Windows Launcher:
```powershell
.\Launch.bat
```

#### Manual Setup:

1. **Install Node.js dependencies**:
   ```bash
   npm install
   ```

2. **Install Python virtual environment & dependencies**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Start the FastAPI Lead Engine**:
   ```bash
   .venv/bin/python -m uvicorn lead_engine.app:app --host 127.0.0.1 --port 8000
   ```

4. **Start the Node.js Dashboard (in a separate terminal)**:
   ```bash
   npm start
   ```

5. **Open the Dashboard**:
   Navigate to `http://localhost:3000` in your web browser.

---

## ⚙️ Environment Variables Reference

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `PORT` | Node.js dashboard server port | `3000` |
| `HOST` | Node.js server binding address | `127.0.0.1` |
| `PUBLIC_BASE_URL` | Public application base URL | `http://localhost:3000` |
| `GOSOM_API_URL` | Self-hosted gosom scraper API endpoint | `http://localhost:8080` |
| `LEAD_ENGINE_URL` | Internal Python FastAPI service URL | `http://127.0.0.1:8000` |
| `LEAD_ENGINE_TOKEN` | Shared secret token between Node & Python | `random_secret_token` |
| `LEAD_DB_PATH` | Path to SQLite database file | `data/leads.db` |
| `GROQ_API_KEY` | Groq API key for AI email generation | `gsk_...` |
| `GROQ_MODEL` | Groq LLM model identifier | `openai/gpt-oss-120b` |
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth Client ID for Gmail API | `*.apps.googleusercontent.com` |
| `GOOGLE_OAUTH_CLIENT_SECRET`| Google OAuth Client Secret | `GOCSPX-...` |
| `GOOGLE_OAUTH_REDIRECT_URI` | Google OAuth redirect callback URL | `http://127.0.0.1:3000/api/gmail/oauth/callback` |
| `GMAIL_TOKEN_ENCRYPTION_KEY`| 32-byte Fernet key for encrypting tokens | Base64 string |
| `SENDGRID_API_KEY` | *(Optional)* SendGrid API key | `SG...` |

---

## 🧪 Running Tests

The test suite covers Node services, FastAPI endpoints, qualification rules, Groq generators, and outreach circuit breakers:

```bash
# Run Node.js service tests
node scripts/run_tests.js

# Run Python API and Lead Engine unit tests
.venv/Scripts/python -m unittest tests.test_python_api -v
.venv/Scripts/python -m unittest tests.test_python_engine -v
.venv/Scripts/python -m unittest tests.test_marketing_site -v
```

---

## 🛡️ Responsible Outreach & Compliance

BuildMeLeads is engineered with built-in safeguards to maintain sender reputation and adhere to email regulations:
- **CAN-SPAM & GDPR Compliant**: Enforces sender physical address headers, reply-to routing, and one-click unsubscribe links.
- **Automated Domain Suppression**: Prevents re-contacting domains that have unsubscribed, bounced, or were previously contacted within the suppression window.
- **Warmup Rate Limits**: Default daily send limits prevent provider throttling or account suspensions.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
