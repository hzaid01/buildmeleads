from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from .config import settings
from .database import DEFAULT_PROMPT, LEGACY_OWNER_ID, _campaign_id, connect, init_db, transaction, utc_now

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_HASHER = PasswordHasher()
TENANT_TABLES = (
    "leads", "suppressions", "campaigns", "email_batches", "outreach_queue", "send_logs",
    "analytics_results", "gmail_oauth_accounts", "oauth_states", "scrape_runs", "provider_events",
)


class AuthError(ValueError):
    pass


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _public_user(row: Any) -> dict[str, Any]:
    return {"id": row["id"], "email": row["email"], "displayName": row["display_name"], "role": row["role"]}


def register(email: str, password: str, display_name: str = "") -> tuple[str, dict[str, Any]]:
    init_db()
    normalized_email = str(email or "").strip().lower()
    if len(normalized_email) > 254 or not EMAIL_RE.fullmatch(normalized_email):
        raise AuthError("Enter a valid email address")
    if len(password or "") < 10 or len(password) > 1024:
        raise AuthError("Password must be at least 10 characters")
    clean_name = re.sub(r"\s+", " ", str(display_name or "").strip())[:100]
    user_id = secrets.token_hex(16)
    now = utc_now()
    password_hash = PASSWORD_HASHER.hash(password)
    with transaction(immediate=True) as connection:
        if connection.execute("SELECT 1 FROM app_users WHERE email=? COLLATE NOCASE", (normalized_email,)).fetchone():
            raise AuthError("An account with this email already exists")
        first_admin = not connection.execute("SELECT 1 FROM app_users WHERE status='active' LIMIT 1").fetchone()
        connection.execute(
            "INSERT INTO app_users(id,email,password_hash,display_name,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (user_id, normalized_email, password_hash, clean_name, "admin" if first_admin else "member", "active", now, now),
        )
        legacy = connection.execute("SELECT 1 FROM app_users WHERE id=? AND status='pending'", (LEGACY_OWNER_ID,)).fetchone()
        if first_admin and legacy:
            for table in TENANT_TABLES:
                connection.execute(f"UPDATE {table} SET user_id=? WHERE user_id=?", (user_id, LEGACY_OWNER_ID))
            connection.execute("DELETE FROM app_users WHERE id=?", (LEGACY_OWNER_ID,))
        if not connection.execute("SELECT 1 FROM campaigns WHERE user_id=?", (user_id,)).fetchone():
            connection.execute(
                """INSERT INTO campaigns(id,user_id,name,sending_method,workflow_mode,offer,cta,prompt_template,groq_model,
                   created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (_campaign_id(user_id), user_id, settings.campaign_name, "sendgrid", "manual", settings.campaign_offer,
                 settings.campaign_cta, DEFAULT_PROMPT, settings.groq_model, now, now),
            )
        row = connection.execute("SELECT * FROM app_users WHERE id=?", (user_id,)).fetchone()
    return create_session(user_id), _public_user(row)


def login(email: str, password: str) -> tuple[str, dict[str, Any]]:
    init_db()
    with connect() as connection:
        row = connection.execute("SELECT * FROM app_users WHERE email=? COLLATE NOCASE AND status='active'", (str(email or "").strip().lower(),)).fetchone()
    if not row or not row["password_hash"]:
        raise AuthError("Invalid email or password")
    try:
        PASSWORD_HASHER.verify(row["password_hash"], password or "")
    except (VerifyMismatchError, InvalidHashError):
        raise AuthError("Invalid email or password") from None
    if PASSWORD_HASHER.check_needs_rehash(row["password_hash"]):
        with transaction(immediate=True) as connection:
            connection.execute("UPDATE app_users SET password_hash=?,updated_at=? WHERE id=?", (PASSWORD_HASHER.hash(password), utc_now(), row["id"]))
    return create_session(row["id"]), _public_user(row)


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    with transaction(immediate=True) as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at<=?", (now.isoformat(),))
        connection.execute(
            "INSERT INTO sessions(token_hash,user_id,created_at,last_seen_at,expires_at) VALUES(?,?,?,?,?)",
            (_token_hash(token), user_id, now.isoformat(), now.isoformat(), (now + timedelta(hours=max(1, settings.session_hours))).isoformat()),
        )
    return token


def session_user(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    now = utc_now()
    with transaction(immediate=True) as connection:
        row = connection.execute(
            """SELECT u.* FROM sessions s JOIN app_users u ON u.id=s.user_id
               WHERE s.token_hash=? AND s.expires_at>? AND u.status='active'""",
            (_token_hash(token), now),
        ).fetchone()
        if row:
            connection.execute("UPDATE sessions SET last_seen_at=? WHERE token_hash=?", (now, _token_hash(token)))
    return _public_user(row) if row else None


def logout(token: str | None) -> None:
    if not token:
        return
    with transaction(immediate=True) as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token),))
