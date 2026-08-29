from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import settings
from .qualification import detect_weaknesses, issue_summary, is_qualified


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL DEFAULT 'gosom',
    place_id TEXT,
    cid TEXT,
    name TEXT NOT NULL,
    niche TEXT,
    category TEXT,
    city TEXT,
    timezone TEXT,
    address TEXT,
    phone TEXT,
    website TEXT,
    email TEXT,
    email_source TEXT,
    email_valid INTEGER NOT NULL DEFAULT 0,
    mx_valid INTEGER NOT NULL DEFAULT 0,
    rating REAL NOT NULL DEFAULT 0,
    review_count INTEGER NOT NULL DEFAULT 0,
    rank INTEGER,
    photo_count INTEGER NOT NULL DEFAULT 0,
    last_review_at TEXT,
    is_closed INTEGER NOT NULL DEFAULT 0,
    weaknesses_json TEXT NOT NULL DEFAULT '[]',
    issue_detected TEXT NOT NULL DEFAULT '',
    qualified INTEGER NOT NULL DEFAULT 0,
    consent_status TEXT NOT NULL DEFAULT 'unknown' CHECK(consent_status IN ('unknown','confirmed','revoked')),
    whatsapp_verified INTEGER,
    unsubscribe_token TEXT NOT NULL UNIQUE,
    outreach_attempted_at TEXT,
    contacted_at TEXT,
    opened_at TEXT,
    replied_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_leads_pipeline ON leads(qualified, email_valid, mx_valid, contacted_at);
CREATE INDEX IF NOT EXISTS idx_leads_city ON leads(city);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    query TEXT,
    imported_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outreach_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL UNIQUE REFERENCES leads(id) ON DELETE CASCADE,
    campaign TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('preview','queued','sending','sent','failed','cancelled','blocked')),
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    body_html TEXT NOT NULL,
    weakness TEXT NOT NULL,
    created_at TEXT NOT NULL,
    attempted_at TEXT,
    provider_message_id TEXT,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_queue_due ON outreach_queue(status, scheduled_for);

CREATE TABLE IF NOT EXISTS send_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    queue_id INTEGER REFERENCES outreach_queue(id) ON DELETE SET NULL,
    campaign TEXT NOT NULL,
    status TEXT NOT NULL,
    send_date TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    provider_message_id TEXT,
    detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_send_logs_date ON send_logs(send_date, status);

CREATE TABLE IF NOT EXISTS suppressions (
    email TEXT PRIMARY KEY COLLATE NOCASE,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_events (
    event_key TEXT PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _database_path() -> Path:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(_database_path(), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")
    return connection


@contextmanager
def transaction(immediate: bool = False) -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA)


def _source_key(lead: dict[str, Any]) -> str:
    for field in ("placeId", "place_id", "cid", "dataId", "data_id"):
        value = str(lead.get(field) or "").strip()
        if value:
            return f"google:{field.lower()}:{value}"
    identity = "|".join(
        re.sub(r"\s+", " ", str(lead.get(field) or "").strip().lower())
        for field in ("name", "address", "phone")
    )
    return "fallback:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def upsert_leads(leads: list[dict[str, Any]], source: str = "gosom", query: str = "") -> dict[str, int]:
    init_db()
    inserted = 0
    updated = 0
    now = utc_now()
    with transaction(immediate=True) as connection:
        for raw in leads:
            name = str(raw.get("name") or raw.get("title") or "Unknown Business").strip()
            normalized = {
                **raw,
                "website": raw.get("website") or raw.get("url") or "",
                "rating": _as_float(raw.get("rating", raw.get("review_rating", 0))),
                "reviewCount": _as_int(raw.get("reviewCount", raw.get("review_count", 0))),
                "photoCount": _as_int(raw.get("photoCount", raw.get("photo_count", 0))),
                "category": raw.get("category") or raw.get("niche") or "",
                "lastReviewAt": raw.get("lastReviewAt") or raw.get("last_review_at"),
            }
            weaknesses = raw.get("weaknesses") or detect_weaknesses(normalized)
            if isinstance(weaknesses, str):
                try:
                    weaknesses = json.loads(weaknesses)
                except json.JSONDecodeError:
                    weaknesses = [weaknesses]
            source_key = _source_key(raw)
            existing = connection.execute("SELECT id, email, consent_status, unsubscribe_token FROM leads WHERE source_key=?", (source_key,)).fetchone()
            email = str(raw.get("email") or "").strip().lower()
            values = {
                "source_key": source_key,
                "source": str(raw.get("source") or source),
                "place_id": raw.get("placeId") or raw.get("place_id"),
                "cid": raw.get("cid"),
                "name": name,
                "niche": raw.get("niche") or raw.get("category") or "",
                "category": raw.get("category") or raw.get("niche") or "",
                "city": raw.get("city") or "",
                "timezone": raw.get("timezone") or "America/New_York",
                "address": raw.get("address") or raw.get("fullAddress") or "",
                "phone": raw.get("phone") or raw.get("phoneNumber") or "",
                "website": normalized["website"],
                "email": email,
                "rating": normalized["rating"],
                "review_count": normalized["reviewCount"],
                "rank": _as_int(raw.get("rank"), 0) or None,
                "photo_count": normalized["photoCount"],
                "last_review_at": normalized["lastReviewAt"],
                "is_closed": 1 if raw.get("isClosed") or raw.get("permanentlyClosed") else 0,
                "weaknesses_json": json.dumps(weaknesses, ensure_ascii=False),
                "issue_detected": issue_summary(weaknesses),
                "qualified": 1 if is_qualified(normalized, weaknesses) and not raw.get("isClosed") else 0,
                "whatsapp_verified": None if raw.get("whatsappVerified") is None else (1 if raw.get("whatsappVerified") else 0),
                "raw_json": json.dumps(raw, ensure_ascii=False, default=str),
            }
            if existing:
                connection.execute(
                    """
                    UPDATE leads SET source=:source, place_id=COALESCE(:place_id,place_id), cid=COALESCE(:cid,cid),
                      name=:name, niche=:niche, category=:category, city=:city, timezone=:timezone,
                      address=:address, phone=:phone, website=:website,
                      email=CASE WHEN :email<>'' THEN :email ELSE email END,
                      rating=:rating, review_count=:review_count, rank=:rank, photo_count=:photo_count,
                      last_review_at=COALESCE(:last_review_at,last_review_at), is_closed=:is_closed,
                      weaknesses_json=:weaknesses_json, issue_detected=:issue_detected, qualified=:qualified,
                      whatsapp_verified=COALESCE(:whatsapp_verified,whatsapp_verified), raw_json=:raw_json,
                      updated_at=:updated_at WHERE source_key=:source_key
                    """,
                    {**values, "updated_at": now},
                )
                updated += 1
            else:
                connection.execute(
                    """
                    INSERT INTO leads(source_key,source,place_id,cid,name,niche,category,city,timezone,address,phone,
                      website,email,rating,review_count,rank,photo_count,last_review_at,is_closed,weaknesses_json,
                      issue_detected,qualified,whatsapp_verified,unsubscribe_token,created_at,updated_at,raw_json)
                    VALUES(:source_key,:source,:place_id,:cid,:name,:niche,:category,:city,:timezone,:address,:phone,
                      :website,:email,:rating,:review_count,:rank,:photo_count,:last_review_at,:is_closed,:weaknesses_json,
                      :issue_detected,:qualified,:whatsapp_verified,:unsubscribe_token,:created_at,:updated_at,:raw_json)
                    """,
                    {**values, "unsubscribe_token": secrets.token_urlsafe(32), "created_at": now, "updated_at": now},
                )
                inserted += 1
        connection.execute(
            "INSERT INTO scrape_runs(source,query,imported_count,created_at) VALUES(?,?,?,?)",
            (source, query, len(leads), now),
        )
    return {"received": len(leads), "inserted": inserted, "updated": updated}


def list_leads(limit: int = 250, offset: int = 0, qualified_only: bool = False) -> dict[str, Any]:
    init_db()
    clauses = ["1=1"]
    params: list[Any] = []
    if qualified_only:
        clauses.append("qualified=1")
    where = " AND ".join(clauses)
    with connect() as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM leads WHERE {where}", params).fetchone()[0]
        rows = connection.execute(
            f"""
            SELECT id,name,niche,city,timezone,issue_detected,weaknesses_json,email,email_valid,mx_valid,website,
              phone,rating,review_count,qualified,consent_status,whatsapp_verified,outreach_attempted_at,
              contacted_at,opened_at,replied_at,source,updated_at
            FROM leads WHERE {where}
            ORDER BY qualified DESC, contacted_at IS NOT NULL, review_count DESC, id DESC LIMIT ? OFFSET ?
            """,
            [*params, max(1, min(limit, 1000)), max(0, offset)],
        ).fetchall()
    return {"total": total, "leads": [dict(row) for row in rows]}


def analytics() -> dict[str, Any]:
    init_db()
    with connect() as connection:
        counts = dict(
            connection.execute(
                """
                SELECT COUNT(*) total,
                  SUM(CASE WHEN qualified=1 THEN 1 ELSE 0 END) qualified,
                  SUM(CASE WHEN email_valid=1 AND mx_valid=1 THEN 1 ELSE 0 END) sendable,
                  SUM(CASE WHEN contacted_at IS NOT NULL THEN 1 ELSE 0 END) sent,
                  SUM(CASE WHEN opened_at IS NOT NULL THEN 1 ELSE 0 END) opened,
                  SUM(CASE WHEN replied_at IS NOT NULL THEN 1 ELSE 0 END) replied,
                  SUM(CASE WHEN consent_status='confirmed' THEN 1 ELSE 0 END) consented
                FROM leads
                """
            ).fetchone()
        )
        daily = [
            dict(row)
            for row in connection.execute(
                """SELECT send_date date, SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END) sent
                   FROM send_logs GROUP BY send_date ORDER BY send_date DESC LIMIT 14"""
            ).fetchall()
        ]
        queue = dict(
            connection.execute(
                """SELECT SUM(CASE WHEN status='queued' THEN 1 ELSE 0 END) queued,
                   SUM(CASE WHEN status='preview' THEN 1 ELSE 0 END) previews
                   FROM outreach_queue WHERE status IN ('queued','preview')"""
            ).fetchone()
        )
    sent = counts.get("sent") or 0
    replied = counts.get("replied") or 0
    opened = counts.get("opened") or 0
    return {
        **{key: value or 0 for key, value in counts.items()},
        **{key: value or 0 for key, value in queue.items()},
        "replyRate": round((replied / sent * 100), 1) if sent else 0,
        "openRate": round((opened / sent * 100), 1) if sent else 0,
        "daily": daily,
        "dryRun": settings.dry_run or not settings.live_sending_enabled,
    }


def set_consent(lead_id: int, confirmed: bool) -> bool:
    status = "confirmed" if confirmed else "revoked"
    now = utc_now()
    with transaction(immediate=True) as connection:
        row = connection.execute("SELECT email FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not row:
            return False
        if confirmed and row["email"]:
            suppressed = connection.execute(
                "SELECT reason FROM suppressions WHERE lower(email)=lower(?)", (row["email"],)
            ).fetchone()
            if suppressed:
                raise ValueError(f"This address is permanently suppressed: {suppressed['reason']}")
        connection.execute("UPDATE leads SET consent_status=?,updated_at=? WHERE id=?", (status, now, lead_id))
        if not confirmed and row["email"]:
            connection.execute(
                "INSERT OR REPLACE INTO suppressions(email,reason,created_at) VALUES(?,?,?)",
                (row["email"], "consent revoked", now),
            )
    return True


def mark_replied(lead_id: int) -> bool:
    now = utc_now()
    with transaction(immediate=True) as connection:
        cursor = connection.execute("UPDATE leads SET replied_at=?,updated_at=? WHERE id=?", (now, now, lead_id))
        return cursor.rowcount > 0


def mark_contacted(lead_id: int) -> bool:
    now = utc_now()
    home_date = datetime.now(timezone.utc).date().isoformat()
    with transaction(immediate=True) as connection:
        row = connection.execute("SELECT id FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not row:
            return False
        connection.execute(
            "UPDATE leads SET outreach_attempted_at=COALESCE(outreach_attempted_at,?),contacted_at=COALESCE(contacted_at,?),updated_at=? WHERE id=?",
            (now, now, now, lead_id),
        )
        connection.execute(
            "UPDATE outreach_queue SET status='cancelled',error='manually marked as previously contacted' WHERE lead_id=? AND status IN ('preview','queued')",
            (lead_id,),
        )
        existing = connection.execute(
            "SELECT 1 FROM send_logs WHERE lead_id=? AND status='manual-contact'", (lead_id,)
        ).fetchone()
        if not existing:
            connection.execute(
                "INSERT INTO send_logs(lead_id,campaign,status,send_date,timestamp,detail) VALUES(?,?,?,?,?,?)",
                (lead_id, "historical", "manual-contact", home_date, now, "Marked as contacted by dashboard user"),
            )
    return True


def unsubscribe(token: str) -> bool:
    now = utc_now()
    with transaction(immediate=True) as connection:
        lead = connection.execute("SELECT id,email FROM leads WHERE unsubscribe_token=?", (token,)).fetchone()
        if not lead:
            return False
        connection.execute("UPDATE leads SET consent_status='revoked',updated_at=? WHERE id=?", (now, lead["id"]))
        connection.execute(
            "INSERT OR REPLACE INTO suppressions(email,reason,created_at) VALUES(?,?,?)",
            (lead["email"], "one-click unsubscribe", now),
        )
        connection.execute(
            "UPDATE outreach_queue SET status='cancelled',error='recipient unsubscribed' WHERE lead_id=? AND status IN ('preview','queued')",
            (lead["id"],),
        )
    return True


def get_setting(key: str) -> str | None:
    init_db()
    with connect() as connection:
        row = connection.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    with transaction(immediate=True) as connection:
        connection.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
