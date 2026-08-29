# Local Lead Scout

Local Lead Scout discovers configurable Google Maps business categories in US cities, identifies weak Google Business Profiles, enriches business emails, preserves lead/contact state in SQLite, and prepares compliance-gated outreach through the existing Node.js dashboard.

The application is deliberately **dry-run locked**. It cannot call SendGrid until real sender details are configured, HTTPS is enabled, both live flags are changed, and each queued recipient is marked as having documented affirmative consent.

## Architecture

- **Node.js dashboard (`127.0.0.1:3000`)** — existing UI, gosom orchestration, Apify fallback, SSE logs, WhatsApp verification, CSV export, and a proxy to the private lead engine.
- **Python lead engine (`127.0.0.1:8000`)** — FastAPI, SQLite persistence, qualification, safe website enrichment, MX validation, dry-run outreach previews, SendGrid delivery/event handling, suppressions, and scheduling.
- **gosom/google-maps-scraper** — free primary Google Maps extractor through Docker. The CLI now enables gosom website-email extraction. Successful local results are preserved when only some niches require Apify recovery.
- **Apify** — paid fallback for failed/unavailable Maps extraction and the existing `maged120/whatsapp-number-checker` flow.

## Lead qualification

Open businesses qualify when they have no website or at least one detected weakness:

- no recent review in 183+ days, when review timestamps are available;
- no profile photos detected;
- incomplete or missing category;
- rating below 4.0;
- fewer than 10 reviews.

Categories and cities are arbitrary Google Maps search inputs. Default UI examples are not hard-coded restrictions.

## Setup and launch on Windows

Requirements: Node.js 18+, Python 3.11+, and optionally Docker Desktop. Apify fallback works without Docker when `APIFY_TOKEN` is configured.

1. Copy `.env.example` values into `.env`, preserving `OUTREACH_DRY_RUN=true` and `LIVE_SENDING_ENABLED=false`.
2. Run `powershell -ExecutionPolicy Bypass -File scripts/setup.ps1` once.
3. Double-click `Launch.exe` or run `Launch.bat`.
4. Use `Stop.exe` or `Stop.bat` to stop only the PIDs recorded by this application.

The setup script creates `.venv`, installs pinned dependencies, initializes SQLite, and idempotently imports every CSV under `data/out`.

Optional JavaScript-rendered enrichment fallback:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -InstallPlaywrightBrowser
```

Then set `ENABLE_PLAYWRIGHT_ENRICHMENT=true`. BeautifulSoup remains the primary, lower-resource path.

## Persistent data and enrichment

`data/leads.db` stores deduplicated leads, weakness reasons, enrichment state, consent, WhatsApp state, send queue entries, provider events, permanent suppressions, and send logs. Google place ID/CID is preferred for deduplication; name/address/phone hashing is the fallback.

Email enrichment:

1. Uses any email returned by gosom/Apify.
2. Otherwise reads the business homepage and up to three same-origin contact/about/team pages.
3. Rejects non-HTTP URLs, private/reserved network destinations, oversized responses, invalid email syntax, and domains without MX records.
4. Optionally renders JavaScript pages with Playwright.

## Outreach safeguards

- Dry-run is the default and produces reviewable samples without calling SendGrid.
- Live use requires `OUTREACH_DRY_RUN=false` **and** `LIVE_SENDING_ENABLED=true`.
- Placeholder sender identity, missing SendGrid credentials, non-HTTPS public URL, suppression, missing consent, an earlier outreach attempt, or an earlier send blocks delivery.
- Warmup cap is hard-coded at 10/day for days 1–7 and 15/day from day 8 onward; it remains 15 until the configuration/code is deliberately changed.
- Queue timestamps use randomized 15–45 minute spacing.
- Dispatch rechecks the daily cap and a 15-minute minimum gap inside an immediate SQLite transaction.
- Recipient-local sends are restricted to Monday–Friday, 9:00–17:00 using IANA timezones and DST rules.
- Ambiguous/failed provider attempts are not automatically retried, preventing accidental duplicate contact.
- Every message contains accurate sender fields, advertisement identification, physical address, a one-click unsubscribe URL, and `List-Unsubscribe` headers.
- Unsubscribes, bounces, drops, and spam complaints create permanent cross-campaign suppressions.

SendGrid’s current policy requires affirmative consent for non-transactional email and prohibits emailing addresses gathered from the internet without it. The dashboard therefore requires a deliberate per-lead consent confirmation before live queueing. See the [Twilio SendGrid Email Policy](https://help.twilio.com/articles/47688363512475).

## Dashboard pipeline

The persisted table displays Business, City, Issue Detected, Email, Consent, Email Sent, Opened, and Replied. It also provides total/qualified/validated/sent/opened counts and reply rate.

- Opens are populated by the SendGrid Event Webhook and remain approximate.
- Replies are marked manually because no inbound parse mailbox is configured yet.
- Consent confirmation includes an explicit documented-consent prompt.

## Scheduler and Azure

Deployment is prepared but Azure provisioning is deferred until the Azure subscription, region, VM, DNS, and access details are supplied. See `deploy/README.md`.

The systemd timer runs a short scheduler tick every five minutes. SQLite queue timestamps—not the timer frequency—control the 15–45 minute spacing. `Persistent=true` catches up after VM restarts, while dispatch sends at most one due message and rechecks the minimum gap to prevent bursts.

## Tests

```powershell
npm test
```

The combined suite checks Node services plus Python qualification, deduplication, persistence, email formatting, dry-run rendering, permanent unsubscribe, and live-send configuration gates.

No test calls Google Maps, Apify, SendGrid, or WhatsApp. Live provider validation must be performed later with user-supplied accounts and explicit authorization.
