from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def _load_local_env() -> None:
    """Load simple KEY=VALUE entries without overriding process environment."""
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


_load_local_env()


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path(os.getenv("LEAD_DB_PATH", ROOT_DIR / "data" / "leads.db"))
    engine_host: str = os.getenv("LEAD_ENGINE_HOST", "127.0.0.1")
    engine_port: int = _int("LEAD_ENGINE_PORT", 8000)
    engine_token: str = os.getenv("LEAD_ENGINE_TOKEN", "")
    manage_pid_file: bool = _bool("LEAD_ENGINE_MANAGE_PID_FILE", True)
    session_hours: int = _int("SESSION_HOURS", 168)
    sendgrid_api_key: str = os.getenv("SENDGRID_API_KEY", "")
    sendgrid_webhook_verification_key: str = os.getenv("SENDGRID_WEBHOOK_VERIFICATION_KEY", "")
    sendgrid_webhook_token: str = os.getenv("SENDGRID_WEBHOOK_TOKEN", "")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    google_oauth_client_id: str = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    google_oauth_client_secret: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
    google_oauth_redirect_uri: str = os.getenv(
        "GOOGLE_OAUTH_REDIRECT_URI",
        f"{os.getenv('PUBLIC_BASE_URL', 'http://127.0.0.1:3000').rstrip('/')}/api/gmail/oauth/callback",
    )
    gmail_token_encryption_key: str = os.getenv("GMAIL_TOKEN_ENCRYPTION_KEY", "")
    gmail_testing_mode: bool = _bool("GMAIL_TESTING_MODE", True)
    gmail_test_user_limit: int = _int("GMAIL_TEST_USER_LIMIT", 100)
    sender_name: str = os.getenv("SENDER_NAME", "[YOUR NAME]")
    business_name: str = os.getenv("BUSINESS_NAME", "[YOUR AGENCY NAME]")
    sender_email: str = os.getenv("SENDER_EMAIL", "")
    reply_to_email: str = os.getenv("REPLY_TO_EMAIL", "")
    physical_address: str = os.getenv("PHYSICAL_ADDRESS", "[YOUR VALID LAHORE ADDRESS]")
    business_website: str = os.getenv("BUSINESS_WEBSITE", "")
    campaign_name: str = os.getenv("CAMPAIGN_NAME", "free-gbp-audit")
    campaign_offer: str = os.getenv("CAMPAIGN_OFFER", "a free Google Business Profile audit")
    campaign_cta: str = os.getenv("CAMPAIGN_CTA", "Ask if they are the right person to share it with")
    campaign_start_date: str = os.getenv("CAMPAIGN_START_DATE", "")
    outreach_home_timezone: str = os.getenv("OUTREACH_HOME_TIMEZONE", "America/New_York")
    send_window_start_hour: int = _int("SEND_WINDOW_START_HOUR", 9)
    send_window_end_hour: int = _int("SEND_WINDOW_END_HOUR", 17)
    minimum_delay_minutes: int = _int("MIN_SEND_DELAY_MINUTES", 15)
    maximum_delay_minutes: int = _int("MAX_SEND_DELAY_MINUTES", 45)
    enable_playwright: bool = _bool("ENABLE_PLAYWRIGHT_ENRICHMENT", False)
    website_timeout_seconds: int = _int("WEBSITE_TIMEOUT_SECONDS", 12)
    enrichment_user_agent: str = os.getenv(
        "ENRICHMENT_USER_AGENT",
        "LocalLeadScout/1.0 (+contact-page email discovery)",
    )


settings = Settings()


PLACEHOLDER_MARKERS = ("[YOUR", "YOUR_", "CHANGE_ME", "EXAMPLE.COM")


def validate_sending_configuration(config: Settings = settings, sending_method: str = "sendgrid") -> list[str]:
    """Return every provider/compliance configuration blocker."""
    errors: list[str] = []
    required = {
        "SENDER_NAME": config.sender_name,
        "BUSINESS_NAME": config.business_name,
        "REPLY_TO_EMAIL": config.reply_to_email,
        "PHYSICAL_ADDRESS": config.physical_address,
        "PUBLIC_BASE_URL": config.public_base_url,
    }
    if sending_method == "sendgrid":
        required["SENDGRID_API_KEY"] = config.sendgrid_api_key
        required["SENDER_EMAIL"] = config.sender_email
    for name, value in required.items():
        normalized = (value or "").strip().upper()
        if not normalized or any(marker in normalized for marker in PLACEHOLDER_MARKERS):
            errors.append(f"{name} must contain a real configured value")
    if not config.public_base_url.startswith("https://"):
        errors.append("PUBLIC_BASE_URL must use HTTPS for live sending")
    return errors


# Backwards-compatible import name for older worker entry points.
validate_live_configuration = validate_sending_configuration
