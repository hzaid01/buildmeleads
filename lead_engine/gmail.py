from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from .config import settings
from .database import connect, normalize_user_id, transaction, utc_now


GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def _fernet() -> Fernet:
    raw = settings.gmail_token_encryption_key.strip().encode("ascii", errors="ignore")
    if not raw:
        raise RuntimeError("GMAIL_TOKEN_ENCRYPTION_KEY is required before Gmail can be connected")
    try:
        return Fernet(raw)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("GMAIL_TOKEN_ENCRYPTION_KEY must be a valid Fernet key") from exc


def _encrypt(value: str) -> bytes:
    return _fernet().encrypt(value.encode("utf-8"))


def _decrypt(value: bytes | str | None) -> str:
    if not value:
        return ""
    token = value.encode("ascii") if isinstance(value, str) else value
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored Gmail credentials cannot be decrypted with the configured key") from exc


def _oauth_config_errors() -> list[str]:
    errors: list[str] = []
    if not settings.google_oauth_client_id.strip():
        errors.append("GOOGLE_OAUTH_CLIENT_ID is not configured")
    if not settings.google_oauth_client_secret.strip():
        errors.append("GOOGLE_OAUTH_CLIENT_SECRET is not configured")
    if not settings.google_oauth_redirect_uri.strip():
        errors.append("GOOGLE_OAUTH_REDIRECT_URI is not configured")
    try:
        _fernet()
    except RuntimeError as exc:
        errors.append(str(exc))
    return errors


def gmail_status(user_id: str) -> dict[str, Any]:
    normalized = normalize_user_id(user_id)
    with connect() as connection:
        account = connection.execute(
            "SELECT connected_at,updated_at FROM gmail_oauth_accounts WHERE user_id=?", (normalized,)
        ).fetchone()
        count = connection.execute("SELECT COUNT(*) FROM gmail_oauth_accounts").fetchone()[0]
        campaign = connection.execute(
            "SELECT sending_method FROM campaigns WHERE user_id=? ORDER BY created_at LIMIT 1", (normalized,)
        ).fetchone()
    errors = _oauth_config_errors()
    return {
        "userId": normalized,
        "configured": not errors,
        "setupRequired": bool(errors),
        "configurationErrors": errors,
        "redirectUri": settings.google_oauth_redirect_uri,
        "requiredSettings": [
            "GOOGLE_OAUTH_CLIENT_ID",
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "GMAIL_TOKEN_ENCRYPTION_KEY",
        ],
        "connected": bool(account),
        "connectedAt": account["connected_at"] if account else None,
        "sendingMethod": campaign["sending_method"] if campaign else "sendgrid",
        "testingMode": settings.gmail_testing_mode,
        "connectedCount": int(count),
        "maxConnectedUsers": max(1, min(settings.gmail_test_user_limit, 100)) if settings.gmail_testing_mode else None,
        "scope": GMAIL_SEND_SCOPE,
    }


def create_authorization_url(user_id: str) -> str:
    normalized = normalize_user_id(user_id)
    errors = _oauth_config_errors()
    if errors:
        raise RuntimeError("; ".join(errors))
    status = gmail_status(normalized)
    if (
        settings.gmail_testing_mode
        and not status["connected"]
        and status["connectedCount"] >= status["maxConnectedUsers"]
    ):
        raise RuntimeError(
            f"Gmail testing capacity reached ({status['maxConnectedUsers']} connected users). "
            "Complete Google verification before connecting another account."
        )
    state = secrets.token_urlsafe(40)
    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    with transaction(immediate=True) as connection:
        connection.execute("DELETE FROM oauth_states WHERE expires_at<? OR used_at IS NOT NULL", (utc_now(),))
        connection.execute(
            "INSERT INTO oauth_states(state_hash,user_id,expires_at) VALUES(?,?,?)",
            (state_hash, normalized, expires_at),
        )
    query = urlencode(
        {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": GMAIL_SEND_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"{GOOGLE_AUTH_URL}?{query}"


def _claim_state(state: str) -> str:
    state_hash = hashlib.sha256(str(state or "").encode("utf-8")).hexdigest()
    now = utc_now()
    with transaction(immediate=True) as connection:
        row = connection.execute(
            "SELECT user_id,expires_at,used_at FROM oauth_states WHERE state_hash=?", (state_hash,)
        ).fetchone()
        if not row or row["used_at"] or row["expires_at"] < now:
            raise RuntimeError("Gmail authorization state is invalid or expired")
        connection.execute("UPDATE oauth_states SET used_at=? WHERE state_hash=?", (now, state_hash))
    return normalize_user_id(row["user_id"])


def complete_authorization(code: str, state: str) -> str:
    if not code:
        raise RuntimeError("Google did not return an authorization code")
    errors = _oauth_config_errors()
    if errors:
        raise RuntimeError("; ".join(errors))
    user_id = _claim_state(state)
    try:
        response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=20,
        )
        response.raise_for_status()
        token = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(f"Google token exchange failed: {exc}") from exc

    access_token = str(token.get("access_token") or "")
    refresh_token = str(token.get("refresh_token") or "")
    if not access_token:
        raise RuntimeError("Google token exchange did not return an access token")
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=max(60, int(token.get("expires_in") or 3600)))).isoformat()
    now = utc_now()
    with transaction(immediate=True) as connection:
        existing = connection.execute(
            "SELECT refresh_token_encrypted FROM gmail_oauth_accounts WHERE user_id=?", (user_id,)
        ).fetchone()
        if not refresh_token and existing:
            refresh_encrypted = existing["refresh_token_encrypted"]
        elif refresh_token:
            refresh_encrypted = _encrypt(refresh_token)
        else:
            raise RuntimeError("Google did not return a refresh token; reconnect and approve offline access")
        if settings.gmail_testing_mode and not existing:
            count = connection.execute("SELECT COUNT(*) FROM gmail_oauth_accounts").fetchone()[0]
            limit = max(1, min(settings.gmail_test_user_limit, 100))
            if count >= limit:
                raise RuntimeError(
                    f"Gmail testing capacity reached ({limit} connected users). "
                    "Complete Google verification before connecting another account."
                )
        connection.execute(
            """
            INSERT INTO gmail_oauth_accounts(
              user_id,refresh_token_encrypted,access_token_encrypted,access_token_expires_at,
              scope,token_type,connected_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
              refresh_token_encrypted=excluded.refresh_token_encrypted,
              access_token_encrypted=excluded.access_token_encrypted,
              access_token_expires_at=excluded.access_token_expires_at,
              scope=excluded.scope,token_type=excluded.token_type,updated_at=excluded.updated_at
            """,
            (
                user_id,
                refresh_encrypted,
                _encrypt(access_token),
                expires_at,
                GMAIL_SEND_SCOPE,
                str(token.get("token_type") or "Bearer"),
                now,
                now,
            ),
        )
    return user_id


def disconnect_gmail(user_id: str) -> bool:
    normalized = normalize_user_id(user_id)
    with transaction(immediate=True) as connection:
        cursor = connection.execute("DELETE FROM gmail_oauth_accounts WHERE user_id=?", (normalized,))
        connection.execute(
            "UPDATE campaigns SET sending_method='sendgrid',updated_at=? WHERE user_id=?",
            (utc_now(), normalized),
        )
    return cursor.rowcount > 0


def _refresh_access_token(user_id: str, refresh_token: str) -> str:
    try:
        response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=20,
        )
        response.raise_for_status()
        token = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(f"Google access-token refresh failed: {exc}") from exc
    access_token = str(token.get("access_token") or "")
    if not access_token:
        raise RuntimeError("Google token refresh did not return an access token")
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=max(60, int(token.get("expires_in") or 3600)))).isoformat()
    with transaction(immediate=True) as connection:
        connection.execute(
            "UPDATE gmail_oauth_accounts SET access_token_encrypted=?,access_token_expires_at=?,updated_at=? WHERE user_id=?",
            (_encrypt(access_token), expires_at, utc_now(), user_id),
        )
    return access_token


def _access_token(user_id: str, force_refresh: bool = False) -> str:
    normalized = normalize_user_id(user_id)
    with connect() as connection:
        row = connection.execute("SELECT * FROM gmail_oauth_accounts WHERE user_id=?", (normalized,)).fetchone()
    if not row:
        raise RuntimeError("Connect Gmail before selecting Gmail as the sending method")
    refresh_token = _decrypt(row["refresh_token_encrypted"])
    expires_at = datetime.fromisoformat(row["access_token_expires_at"]) if row["access_token_expires_at"] else None
    if not force_refresh and row["access_token_encrypted"] and expires_at and expires_at > datetime.now(timezone.utc) + timedelta(minutes=1):
        return _decrypt(row["access_token_encrypted"])
    return _refresh_access_token(normalized, refresh_token)


def send_gmail(user_id: str, queue: dict[str, Any], lead: dict[str, Any]) -> str:
    message = EmailMessage()
    message["To"] = lead["email"]
    message["Subject"] = queue["subject"]
    if settings.reply_to_email:
        message["Reply-To"] = settings.reply_to_email
    message["List-Unsubscribe"] = f"<{settings.public_base_url}/unsubscribe/{lead['unsubscribe_token']}>"
    message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    message.set_content(queue["body_text"])
    message.add_alternative(queue["body_html"], subtype="html")
    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

    for attempt in range(2):
        access_token = _access_token(user_id, force_refresh=attempt == 1)
        response = httpx.post(
            GMAIL_SEND_URL,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"raw": encoded},
            timeout=30,
        )
        if response.status_code == 401 and attempt == 0:
            continue
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError(f"Gmail API send failed: {exc}") from exc
        message_id = str(payload.get("id") or "")
        if not message_id:
            raise RuntimeError("Gmail API accepted the request without returning a message ID")
        return message_id
    raise RuntimeError("Gmail access token was rejected after refresh")
