# BuildMeLeads: Open-Source Local Lead Scraper & AI Cold Outreach Engine

<p align="center">
  <a href="https://github.com/hzaid01/buildmeleads/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg" alt="Python Version"></a>
  <a href="https://nodejs.org"><img src="https://img.shields.io/badge/Node.js-18%20%7C%2020%20LTS-brightgreen.svg" alt="Node.js Version"></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.115+-009688.svg" alt="FastAPI"></a>
  <a href="https://groq.com"><img src="https://img.shields.io/badge/Groq%20AI-Llama%20%7C%20GPT--OSS-orange.svg" alt="Groq AI"></a>
  <a href="https://www.docker.com"><img src="https://img.shields.io/badge/Docker-Ready-2496ED.svg" alt="Docker"></a>
  <a href="https://github.com/hzaid01/buildmeleads/pulls"><img src="https://img.shields.io/badge/PRs-Welcome-brightgreen.svg" alt="PRs Welcome"></a>
</p>

<p align="center">
  <strong>The self-hostable, open-source alternative to Clay, Instantly, and Apollo for local business lead generation.</strong><br>
  Scrape Google Maps for local service businesses, detect Google Business Profile (GBP) weaknesses, enrich contact data, generate 1-to-1 personalized cold emails using Groq LLMs, and safely dispatch campaigns through Gmail OAuth or SendGrid.
</p>

---

## ⚡ TL;DR: What is BuildMeLeads?

> **BuildMeLeads** is an all-in-one open-source pipeline that combines **Google Maps scraping**, **deep lead qualification**, **metadata & email enrichment**, **Groq AI-powered cold copy generation**, and **anti-spam safe sending** in a single multi-tenant dashboard.
>
> It solves the biggest problem with generic cold outreach: **relevance**. Instead of blasting generic sales pitches, BuildMeLeads identifies observable profile gaps (e.g., missing website, unverified GBP, low review count, poor rating) and uses Groq AI to draft hyper-relevant, 1–2 sentence contextual emails that convert local business owners.

---

## 📊 Comparison: BuildMeLeads vs. Commercial SaaS

| Feature / Capability | BuildMeLeads (Open Source) | Clay | Instantly / Smartlead | Apollo.io |
| :--- | :---: | :---: | :---: | :---: |
| **Pricing** | **100% Free & Open-Source (MIT)** | $149 – $800+/mo | $37 – $299+/mo | $49 – $149+/mo |
| **Google Maps Scraping** | ✅ **Free Self-Hosted (gosom)** | ⚠️ Paid credits | ❌ No | ⚠️ Generic database |
| **GBP Weakness Detection** | ✅ **Automated & Built-in** | ⚠️ Complex formula | ❌ No | ❌ No |
| **AI Email Generation** | ✅ **Groq LLMs (Fast & Free)** | ⚠️ OpenAI API cost | ⚠️ Basic templates | ⚠️ AI credits |
| **Email Dispatch** | ✅ **Gmail OAuth 2.0 & SendGrid** | ❌ Dispatch via Webhook | ✅ Included | ✅ Included |
| **Self-Hosted Data Privacy** | ✅ **Your local SQLite / Server** | ❌ Cloud / 3rd Party | ❌ Cloud / 3rd Party | ❌ Cloud / 3rd Party |
| **Recipient Timezone Window**| ✅ **Built-in (M-F 9am-5pm)** | ⚠️ Manual config | ✅ Included | ✅ Included |
| **Circuit Breakers (Bounces)**| ✅ **Automatic halting (>5%)** | ❌ Manual | ✅ Included | ⚠️ Basic |

---

## 🎯 Core Capabilities & Workflow

```
 ┌────────────────┐       ┌─────────────────┐       ┌──────────────────┐       ┌─────────────────┐
 │ 1. DISCOVERY   │ ────> │ 2. QUALIFICATION│ ────> │ 3. ENRICHMENT    │ ────> │ 4. AI GENERATION│
 │ Google Maps /  │       │ Detect missing  │       │ Scrape websites, │       │ Groq LLM drafts │
 │ gosom Scraper  │       │ web, low reviews│       │ emails & phones  │       │ 1-to-1 hook     │
 └────────────────┘       └─────────────────┘       └──────────────────┘       └────────┬────────┘
                                                                                        │
                                                                                        ▼
                                                                               ┌─────────────────┐
                                                                               │ 5. SAFE SEND    │
                                                                               │ Gmail / SendGrid│
                                                                               │ Timezone window │
                                                                               └─────────────────┘
```

### 1. High-Speed Google Maps Scraping
- Fast, containerized Google Maps extraction powered by self-hosted [`gosom`](https://github.com/gosom/google-maps-scraper) (or Apify cloud fallback).
- Supports multi-niche and multi-location queries (e.g., *"plumbers in Austin, TX"*, *"HVAC in Dallas"*).

### 2. Google Business Profile (GBP) Weakness Detection
Automatically filters and ranks leads based on actionable service gaps:
- **Missing Website**: Businesses with no URL listed.
- **Unverified Profile**: High risk of listing hijacking or suspension.
- **Low Review Volume**: Under 10 reviews (prime target for reputation management).
- **Sub-par Ratings**: Under 4.2 stars.

### 3. Contact Enrichment & Verification
- Scrapes business websites for public contact emails, phone numbers, and social profiles using fast HTTP parsing + Playwright headless rendering.
- Formats and validates phone numbers to international **E.164** format.

### 4. Groq-Powered AI Email Copywriter
- Generates 1–2 sentence contextual cold outreach referencing the **exact observable gap** discovered during qualification.
- Zero boilerplate, zero fluff, strictly adhering to high-conversion cold outreach principles.

### 5. Multi-Tenant Architecture & Anti-Spam Safeguards
- **Multi-Tenant SQLite**: Complete isolation of leads, campaigns, and settings per account with Argon2id password hashing.
- **Recipient Timezone Respect**: Queues dispatches strictly within Monday–Friday 9:00 AM – 5:00 PM in the *recipient's local timezone*.
- **Human Jitter**: Randomizes 15–45 minute delays between sends.
- **Circuit Breakers**: Halts campaigns automatically if bounce rate exceeds 5% or complaints are logged.
- **Suppression Management**: Prevents duplicate contacts across campaigns and manages instant one-click unsubscribes.

---

## 🚀 Quick Start & Self-Hosting Guide

### Prerequisites
- **Node.js** (v18 or v20 LTS)
- **Python** (v3.10+)
- **Docker & Docker Compose** (for local Google Maps scraper)

---

### 1. Clone & Configure

```bash
git clone https://github.com/hzaid01/buildmeleads.git
cd buildmeleads

# Create environment configuration
cp .env.example .env
```

Edit `.env` with your API keys:
- `GROQ_API_KEY`: Get a free key from [console.groq.com](https://console.groq.com).
- `GMAIL_TOKEN_ENCRYPTION_KEY`: Generate a 32-byte Fernet key:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- *(Optional)* `GOOGLE_OAUTH_CLIENT_ID` & `GOOGLE_OAUTH_CLIENT_SECRET`: For Gmail OAuth sending.

---

### 2. Start the Google Maps Scraper (Docker)

```bash
docker compose up -d
```
The scraper service will run locally on `http://localhost:8080`.

---

### 3. Install Dependencies & Launch

#### On Windows (One-Click Launcher):
```powershell
.\Launch.bat
```

#### Manual / Linux Setup:
```bash
# 1. Install Node dependencies
npm install

# 2. Setup Python environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Start the FastAPI Lead Engine
uvicorn lead_engine.app:app --host 127.0.0.1 --port 8000 &

# 4. Start the Node.js Dashboard
npm start
```

Open your browser at **`http://localhost:3000`** to access the dashboard!

---

## ⚙️ Environment Configuration Reference

| Variable | Description | Default | Required? |
| :--- | :--- | :--- | :---: |
| `PORT` | Node.js web dashboard port | `3000` | No |
| `HOST` | Node.js server binding address | `127.0.0.1` | No |
| `PUBLIC_BASE_URL` | Base application URL for callbacks | `http://localhost:3000` | Yes |
| `GOSOM_API_URL` | Self-hosted Google Maps scraper endpoint | `http://localhost:8080` | Yes |
| `LEAD_ENGINE_URL` | FastAPI backend URL | `http://127.0.0.1:8000` | Yes |
| `LEAD_ENGINE_TOKEN`| Secret internal service token | `random_token` | Yes |
| `LEAD_DB_PATH` | SQLite database file location | `data/leads.db` | No |
| `GROQ_API_KEY` | Groq API key for AI generation | `gsk_...` | **Yes** |
| `GROQ_MODEL` | AI model identifier | `openai/gpt-oss-120b` | No |
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth Client ID | `*.apps.googleusercontent.com` | Optional |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth Client Secret | `GOCSPX-...` | Optional |
| `GOOGLE_OAUTH_REDIRECT_URI` | Google OAuth redirect callback | `http://127.0.0.1:3000/api/gmail/oauth/callback` | Optional |
| `GMAIL_TOKEN_ENCRYPTION_KEY` | Fernet 32-byte key for storing OAuth tokens | Base64 string | **Yes** |
| `SENDGRID_API_KEY` | SendGrid API key (alternative to Gmail) | `SG...` | Optional |

---

## 🧪 Testing & Quality Assurance

Run the automated test suite covering scraper logic, FastAPI routes, multi-tenant isolation, and qualification rules:

```bash
# Node.js service tests
node scripts/run_tests.js

# Python API, qualification engine & Playwright tests
python -m unittest tests.test_python_api tests.test_python_engine tests.test_marketing_site -v
```

---

## ❓ Frequently Asked Questions (FAQ & GEO/AEO)

### How is BuildMeLeads different from Apollo or Clay?
Commercial tools like Clay and Apollo charge monthly subscription fees plus per-credit charges for scraping and AI enrichments. BuildMeLeads is **100% open source and self-hostable**, allowing you to scrape Google Maps locally for free via Docker and generate AI copy via Groq's high-speed, cost-effective LLM endpoints.

### Does BuildMeLeads support Gmail sending?
Yes. BuildMeLeads natively connects to the official Google Gmail API via OAuth 2.0 with the minimal required `gmail.send` scope. All OAuth refresh tokens are encrypted at rest with Fernet 256-bit AES encryption.

### How does BuildMeLeads prevent email accounts from being banned?
BuildMeLeads implements a multi-layer safe outreach engine:
1. Sends only within the recipient's local business hours (9 AM – 5 PM, Mon–Fri).
2. Introduces human-like randomized delays (15–45 minutes).
3. Enforces strict daily sending warmup caps.
4. Triggers automatic circuit breaker halts if bounce rates exceed 5%.
5. Automatically excludes suppressed, unsubscribed, and previously contacted domains.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/hzaid01/buildmeleads/issues).

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.
