# BuildMeLeads — Project Execution & Deployment Log (Antigravity)

This document contains a comprehensive record of all architectural decisions, actions taken, deployment procedures, DNS/email configurations, and verification steps performed. It is designed to give Codex and any AI agent a complete, accurate, and unambiguous understanding of the system's architecture and setup history.

---

## 1. Project Overview

- **Product Name:** BuildMeLeads / Lead Scout
- **Architecture:** Full-stack B2B lead discovery & automated outreach platform.
- **Product Purpose:** Discover local service businesses (plumbers, roofers, HVAC, electricians) with weak Google Business Profile (GBP) signals, qualify them, generate personalized outreach copy via Groq LLMs, and manage email campaigns with anti-spam safeguards.
- **Components:**
  - Node.js scraper control dashboard & web UI (`server.js`, `public/`).
  - Python FastAPI multi-tenant lead engine (`lead_engine/`).
  - gosom containerized Google Maps scraper (`docker-compose.yml`).
  - Standalone static marketing & waitlist frontend (`marketing/`).

---

## 2. Chronological Summary of Technical Implementation

### Phase 1: Codebase & Markdown Audit
1. **Repository Inspection:** Examined all project documentation and source code:
   - [`PRODUCT.md`](file:///c:/Users/zaids/OneDrive/Desktop/GitHub%20Repos/Scaper/PRODUCT.md): Platform specifications, target audience, pricing tiers (Starter $49/mo, Pro $99/mo, Agency $299/mo), pre-launch policy, and legal commitments.
   - [`DESIGN.md`](file:///c:/Users/zaids/OneDrive/Desktop/GitHub%20Repos/Scaper/DESIGN.md): Service-Area Dispatch Desk design system, color tokens (Mineral Ink `#17211D`, Paper Fog `#EEF1EB`, Utility Green `#28604D`, Signal Yellow `#F4C95D`), typography (Archivo & IBM Plex Mono), and WCAG 2.2 AA standards.
   - [`README.md`](file:///c:/Users/zaids/OneDrive/Desktop/GitHub%20Repos/Scaper/README.md): Authenticated multi-tenant lead scraper, FastAPI backend, Node dashboard, Groq model integration, Gmail OAuth, and queue worker.
2. **Automated Test Validation:** Executed test suite (`test_services.js`, `test_marketing_site.py`, `test_python_api.py`, `test_python_engine.py`); confirmed test pass rate for all core services.

---

### Phase 2: Static Marketing Deployment Architecture
1. **Static Surface Isolation:** The public marketing site (`marketing/`) is designed as a standalone static surface that can be hosted on GitHub Pages, cPanel, Nginx, or Netlify/Vercel without exposing backend databases or scraper containers.
2. **Automated File Structure:** 19 static assets (HTML, CSS, SVGs, WOFF2 fonts, legal policy pages) structured for lightweight, zero-dependency hosting.

---

### Phase 3: Domain & DNS Guidelines
1. **DNS Architecture:**
   - Apex and `www` records pointing to the hosting web server or static provider.
   - SSL / HTTPS certificates provisioned with automatic HTTP to HTTPS redirection.
2. **Email Routing & MX Records:**
   - For business email (e.g. Private Email / Google Workspace), MX records configured to point to the dedicated mail exchanger (`mx1...`, `mx2...`).
   - SPF TXT records configured (`v=spf1 include:spf... ~all`) to prevent outbound spoofing and ensure 100% inbox delivery.

---

### Phase 4: Waitlist Form Automation (`waitlist.php`)
1. **Backend PHP Endpoint:** [`marketing/waitlist.php`](file:///c:/Users/zaids/OneDrive/Desktop/GitHub%20Repos/Scaper/marketing/waitlist.php):
   - Validates incoming email submissions via JSON POST.
   - Appends entries to a server ledger: `waitlist.csv`.
   - Optionally sends authenticated email alerts using configurable environment variables (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`).
2. **Frontend Integration:** [`marketing/assets/site.js`](file:///c:/Users/zaids/OneDrive/Desktop/GitHub%20Repos/Scaper/marketing/assets/site.js) submits asynchronously via `fetch()` and renders an immediate on-page confirmation message.

---

### Phase 5: Payment Processor Verification Compliance
All required legal and compliance pages are structured for standard Merchant of Record (Paddle / Stripe / LemonSqueezy) verification:
- **Pricing URL:** `/pricing/`
- **Terms of Service URL:** `/terms/`
- **Privacy Policy URL:** `/privacy/`
- **Refund Policy URL:** `/refunds/`

---

## 3. Directory & File Reference

```
Scaper/
├── .env.example                  # Environment configuration template
├── LICENSE                       # MIT open-source license
├── README.md                     # Open-source documentation and self-hosting guide
├── PRODUCT.md                    # Core product specifications
├── DESIGN.md                     # Service-Area Dispatch Desk design tokens
├── antigravity.md                # (This file) Architecture & setup history
├── server.js                     # Node.js scraper dashboard entry point
├── public/                       # Node dashboard frontend assets
├── lead_engine/                  # Python FastAPI SaaS engine
│   ├── app.py                    # REST API routes and lifespan
│   ├── auth.py                   # Argon2id authentication & sessions
│   ├── config.py                 # Pydantic settings and env loaders
│   ├── database.py               # SQLite schema, migrations & tenant isolation
│   ├── enrichment.py             # Playwright/HTTP lead enrichment
│   ├── gmail.py                  # Gmail OAuth & encrypted token storage
│   ├── groq_email.py             # Groq AI email copy generator
│   ├── importer.py               # CSV/gosom output parser
│   ├── outreach.py               # Outreach campaign logic & circuit breakers
│   └── worker.py                 # Background send queue worker
├── marketing/                    # Standalone static marketing & waitlist site
│   ├── index.html                # Main landing page
│   ├── 404.html                  # Custom 404 page
│   ├── waitlist.php              # Configurable PHP waitlist handler
│   ├── robots.txt                # Search engine crawlers policy
│   ├── sitemap.xml               # XML sitemap
│   ├── pricing/index.html        # Pricing page
│   ├── privacy/index.html        # Privacy policy
│   ├── terms/index.html          # Terms of service
│   ├── refunds/index.html        # Refund policy
│   └── assets/
│       ├── site.css              # Main responsive stylesheet
│       ├── site.js               # Form logic & navigation
│       ├── theme.css             # HSL design tokens
│       ├── logo.svg              # SVG brand mark
│       ├── favicon.svg           # Site favicon
│       └── fonts/                # Self-hosted Archivo & IBM Plex Mono woff2
└── tests/                        # Automated unit & integration tests
```
