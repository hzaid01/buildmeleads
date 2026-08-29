# Azure deployment (pending user Azure setup)

Azure provisioning is intentionally deferred until the subscription, region, VM, DNS name, and inbound-access plan are supplied.

The deployment target is Ubuntu with the project at `/opt/local-lead-scout` and a dedicated `leadscout` user. The supplied units provide:

- `lead-engine.service`: private FastAPI service on `127.0.0.1:8000`.
- `lead-dashboard.service`: Node dashboard on the configured `HOST`/`PORT`.
- `gosom.service`: Docker Compose lifecycle for the local scraper.
- `lead-scheduler.timer`: restart-safe five-minute scheduler ticks. Queue timestamps in SQLite enforce recipient-local weekday 9–5 windows, 15–45 minute randomized spacing, warmup caps, consent, suppression, and no-repeat rules.

Before live deployment:

1. Replace every campaign identity placeholder in `.env`.
2. Configure a verified SendGrid domain, webhook signature key, HTTPS `PUBLIC_BASE_URL`, SPF, DKIM, and DMARC.
3. Keep `OUTREACH_DRY_RUN=true` and `LIVE_SENDING_ENABLED=false` until sample review is complete.
4. Put the dashboard behind HTTPS and authentication; do not expose FastAPI port 8000 publicly.
5. Install Chromium only if `ENABLE_PLAYWRIGHT_ENRICHMENT=true` using `.venv/bin/python -m playwright install --with-deps chromium`.
6. Copy the units to `/etc/systemd/system`, run `systemctl daemon-reload`, and enable only after paths/users are verified.

The B1s VM has limited memory. Run gosom at low concurrency and monitor memory before enabling Playwright enrichment on the same VM.
