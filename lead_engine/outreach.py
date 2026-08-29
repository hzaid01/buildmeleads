from __future__ import annotations

import html
import json
import random
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from urllib import request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import settings, validate_live_configuration
from .database import connect, get_setting, init_db, set_setting, transaction, utc_now
from .qualification import primary_issue


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or settings.outreach_home_timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo(settings.outreach_home_timezone)


def _campaign_start(today: date, live: bool) -> date:
    configured = settings.campaign_start_date.strip()
    stored = get_setting("campaign_started_at")
    value = configured or stored
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    if live:
        set_setting("campaign_started_at", today.isoformat())
    return today


def warmup_cap(now: datetime | None = None, live: bool = False) -> dict[str, Any]:
    home_zone = _zone(settings.outreach_home_timezone)
    local_now = (now or datetime.now(timezone.utc)).astimezone(home_zone)
    start = _campaign_start(local_now.date(), live)
    day_number = max(1, (local_now.date() - start).days + 1)
    cap = 10 if day_number <= 7 else 15
    return {"day": day_number, "cap": cap, "date": local_now.date().isoformat()}


def _next_business_window(moment: datetime, timezone_name: str) -> datetime:
    zone = _zone(timezone_name)
    local = moment.astimezone(zone)
    start_hour = max(0, min(settings.send_window_start_hour, 23))
    end_hour = max(start_hour + 1, min(settings.send_window_end_hour, 24))
    while True:
        if local.weekday() >= 5:
            days = 7 - local.weekday()
            local = datetime.combine(local.date() + timedelta(days=days), time(start_hour), zone)
            continue
        window_start = datetime.combine(local.date(), time(start_hour), zone)
        window_end = datetime.combine(local.date(), time(end_hour % 24), zone)
        if end_hour == 24:
            window_end += timedelta(days=1)
        if local < window_start:
            return window_start.astimezone(timezone.utc)
        if local >= window_end:
            local = datetime.combine(local.date() + timedelta(days=1), time(start_hour), zone)
            continue
        return local.astimezone(timezone.utc)


def _message_for(lead: dict[str, Any]) -> dict[str, str]:
    issue = primary_issue(lead.get("weaknesses_json"))
    business = str(lead.get("name") or "your business").strip()
    city = str(lead.get("city") or "your area").strip()
    unsubscribe_url = f"{settings.public_base_url}/unsubscribe/{lead['unsubscribe_token']}"
    subject = f"Quick question about {business}"
    message = (
        f"Hey — quick one: I noticed {business}'s Google listing {issue} in {city}. "
        "Are you the right person to ask about a free Google Business Profile audit?"
    )
    sender_line = f"{settings.sender_name} · {settings.business_name}"
    ad_line = f"Advertisement · {settings.physical_address}"
    text_body = f"{message}\n\n{sender_line}\n{ad_line}\nUnsubscribe: {unsubscribe_url}"
    website_line = (
        f'<br><a href="{html.escape(settings.business_website, quote=True)}">{html.escape(settings.business_website)}</a>'
        if settings.business_website
        else ""
    )
    html_body = (
        f"<p>{html.escape(message)}</p>"
        f"<p style=\"color:#64748b;font-size:12px\">{html.escape(sender_line)}{website_line}<br>"
        f"Advertisement · {html.escape(settings.physical_address)}<br>"
        f'<a href="{html.escape(unsubscribe_url, quote=True)}">Unsubscribe in one click</a></p>'
    )
    return {"subject": subject, "body_text": text_body, "body_html": html_body, "weakness": issue}


def _candidate_rows(connection: Any, live: bool, limit: int) -> list[dict[str, Any]]:
    consent_clause = "AND l.consent_status='confirmed'" if live else ""
    rows = connection.execute(
        f"""
        SELECT l.* FROM leads l
        LEFT JOIN suppressions s ON lower(s.email)=lower(l.email)
        LEFT JOIN outreach_queue q ON q.lead_id=l.id
        WHERE l.qualified=1 AND l.is_closed=0 AND l.email_valid=1 AND l.mx_valid=1
          AND l.contacted_at IS NULL AND l.outreach_attempted_at IS NULL
          AND s.email IS NULL AND q.id IS NULL {consent_clause}
        ORDER BY l.review_count DESC,l.id ASC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def plan_outreach(now: datetime | None = None) -> dict[str, Any]:
    init_db()
    now = now or datetime.now(timezone.utc)
    live = settings.live_sending_enabled and not settings.dry_run
    config_errors = validate_live_configuration() if live else []
    if config_errors:
        return {"success": False, "dryRun": False, "errors": config_errors, "planned": 0}

    warmup = warmup_cap(now, live=live)
    status = "queued" if live else "preview"
    with transaction(immediate=True) as connection:
        if not live:
            connection.execute("DELETE FROM outreach_queue WHERE status='preview'")
        already = connection.execute(
            """
            SELECT COUNT(*) FROM outreach_queue
            WHERE campaign=? AND substr(scheduled_for,1,10)=? AND status IN ('preview','queued','sending','sent')
            """,
            (settings.campaign_name, warmup["date"]),
        ).fetchone()[0]
        available = max(0, warmup["cap"] - already)
        candidates = _candidate_rows(connection, live, max(available * 3, available))
        cursor = now
        planned: list[dict[str, Any]] = []
        for lead in candidates:
            if len(planned) >= available:
                break
            scheduled = _next_business_window(cursor, str(lead.get("timezone") or settings.outreach_home_timezone))
            home_date = scheduled.astimezone(_zone(settings.outreach_home_timezone)).date().isoformat()
            if home_date != warmup["date"]:
                continue
            message = _message_for(lead)
            created_at = utc_now()
            connection.execute(
                """
                INSERT INTO outreach_queue(lead_id,campaign,scheduled_for,status,subject,body_text,body_html,weakness,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    lead["id"], settings.campaign_name, scheduled.isoformat(), status,
                    message["subject"], message["body_text"], message["body_html"], message["weakness"], created_at,
                ),
            )
            planned.append(
                {
                    "leadId": lead["id"],
                    "business": lead["name"],
                    "city": lead["city"],
                    "email": lead["email"],
                    "scheduledFor": scheduled.isoformat(),
                    "subject": message["subject"],
                    "body": message["body_text"],
                    "consentStatus": lead["consent_status"],
                }
            )
            delay = random.randint(
                max(15, settings.minimum_delay_minutes),
                max(max(15, settings.minimum_delay_minutes), settings.maximum_delay_minutes),
            )
            cursor = scheduled + timedelta(minutes=delay)
    return {
        "success": True,
        "dryRun": not live,
        "planned": len(planned),
        "warmup": warmup,
        "items": planned,
        "notice": "Preview only; SendGrid was not called." if not live else "Live queue created for consented recipients.",
    }


def _sendgrid_send(queue: dict[str, Any], lead: dict[str, Any]) -> str:
    payload = {
        "personalizations": [{
            "to": [{"email": lead["email"], "name": lead["name"]}],
            "custom_args": {"lead_id": str(lead["id"]), "queue_id": str(queue["id"])},
        }],
        "from": {"email": settings.sender_email, "name": settings.sender_name},
        "reply_to": {"email": settings.reply_to_email, "name": settings.sender_name},
        "subject": queue["subject"],
        "content": [
            {"type": "text/plain", "value": queue["body_text"]},
            {"type": "text/html", "value": queue["body_html"]},
        ],
        "headers": {
            "List-Unsubscribe": f"<{settings.public_base_url}/unsubscribe/{lead['unsubscribe_token']}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
        "tracking_settings": {"open_tracking": {"enable": True}},
    }
    req = request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.sendgrid_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=20) as response:
        if response.status != 202:
            raise RuntimeError(f"SendGrid returned HTTP {response.status}")
        return response.headers.get("X-Message-Id", "")


def dispatch_due(now: datetime | None = None) -> dict[str, Any]:
    init_db()
    now = now or datetime.now(timezone.utc)
    errors = validate_live_configuration()
    if errors:
        return {"success": False, "sent": 0, "errors": errors, "dryRun": True}

    warmup = warmup_cap(now, live=True)
    claimed: tuple[dict[str, Any], dict[str, Any], int] | None = None
    with transaction(immediate=True) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM send_logs WHERE send_date=? AND status IN ('attempting','sent')",
            (warmup["date"],),
        ).fetchone()[0]
        if count >= warmup["cap"]:
            return {"success": True, "sent": 0, "reason": "daily cap reached", "warmup": warmup}

        last_attempt = connection.execute(
            "SELECT timestamp FROM send_logs WHERE status IN ('attempting','sent') ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if last_attempt:
            previous = datetime.fromisoformat(last_attempt["timestamp"])
            if now < previous + timedelta(minutes=max(15, settings.minimum_delay_minutes)):
                return {"success": True, "sent": 0, "reason": "minimum delay guard active", "warmup": warmup}

        row = connection.execute(
            """
            SELECT q.*,l.email,l.name,l.city,l.timezone,l.consent_status,l.unsubscribe_token,l.contacted_at,
              s.email suppressed_email
            FROM outreach_queue q JOIN leads l ON l.id=q.lead_id
            LEFT JOIN suppressions s ON lower(s.email)=lower(l.email)
            WHERE q.status='queued' AND q.scheduled_for<=?
            ORDER BY q.scheduled_for ASC LIMIT 1
            """,
            (now.isoformat(),),
        ).fetchone()
        if not row:
            return {"success": True, "sent": 0, "reason": "nothing due", "warmup": warmup}
        data = dict(row)
        local = now.astimezone(_zone(data.get("timezone")))
        if local.weekday() >= 5 or not (settings.send_window_start_hour <= local.hour < settings.send_window_end_hour):
            next_time = _next_business_window(now, data.get("timezone") or settings.outreach_home_timezone)
            connection.execute("UPDATE outreach_queue SET scheduled_for=? WHERE id=?", (next_time.isoformat(), data["id"]))
            return {"success": True, "sent": 0, "reason": "rescheduled into recipient business hours", "scheduledFor": next_time.isoformat()}
        block_reason = None
        if data["consent_status"] != "confirmed":
            block_reason = "documented affirmative consent is required"
        elif data["suppressed_email"]:
            block_reason = "recipient is permanently suppressed"
        elif data["contacted_at"]:
            block_reason = "business was already contacted"
        if block_reason:
            connection.execute("UPDATE outreach_queue SET status='blocked',error=? WHERE id=?", (block_reason, data["id"]))
            return {"success": True, "sent": 0, "reason": block_reason}

        attempted_at = utc_now()
        connection.execute("UPDATE outreach_queue SET status='sending',attempted_at=? WHERE id=?", (attempted_at, data["id"]))
        connection.execute("UPDATE leads SET outreach_attempted_at=?,updated_at=? WHERE id=?", (attempted_at, attempted_at, data["lead_id"]))
        log_cursor = connection.execute(
            "INSERT INTO send_logs(lead_id,queue_id,campaign,status,send_date,timestamp,detail) VALUES(?,?,?,?,?,?,?)",
            (data["lead_id"], data["id"], data["campaign"], "attempting", warmup["date"], attempted_at, "SendGrid request claimed"),
        )
        queue = {key: data[key] for key in ("id", "subject", "body_text", "body_html")}
        lead = {key: data[key] for key in ("lead_id", "email", "name", "city", "unsubscribe_token")}
        lead["id"] = lead.pop("lead_id")
        claimed = (queue, lead, log_cursor.lastrowid)

    if not claimed:
        return {"success": True, "sent": 0}
    queue, lead, log_id = claimed
    try:
        message_id = _sendgrid_send(queue, lead)
        completed_at = utc_now()
        with transaction(immediate=True) as connection:
            connection.execute(
                "UPDATE outreach_queue SET status='sent',provider_message_id=?,error=NULL WHERE id=?",
                (message_id, queue["id"]),
            )
            connection.execute("UPDATE leads SET contacted_at=?,updated_at=? WHERE id=?", (completed_at, completed_at, lead["id"]))
            connection.execute(
                "UPDATE send_logs SET status='sent',timestamp=?,provider_message_id=?,detail='Accepted by SendGrid' WHERE id=?",
                (completed_at, message_id, log_id),
            )
        return {"success": True, "sent": 1, "leadId": lead["id"], "providerMessageId": message_id, "warmup": warmup}
    except Exception as exc:
        failed_at = utc_now()
        with transaction(immediate=True) as connection:
            connection.execute("UPDATE outreach_queue SET status='failed',error=? WHERE id=?", (str(exc), queue["id"]))
            connection.execute(
                "UPDATE send_logs SET status='failed',timestamp=?,detail=? WHERE id=?",
                (failed_at, str(exc), log_id),
            )
        return {"success": False, "sent": 0, "error": str(exc), "leadId": lead["id"], "warmup": warmup}


def verify_sendgrid_signature(payload: bytes, signature: str, timestamp: str) -> bool:
    key = settings.sendgrid_webhook_verification_key.strip()
    if not key:
        return bool(settings.sendgrid_webhook_token)
    try:
        from sendgrid.helpers.eventwebhook import EventWebhook

        webhook = EventWebhook()
        public_key = webhook.convert_public_key_to_ecdsa(key)
        return bool(webhook.verify_signature(payload, signature, timestamp, public_key))
    except Exception:
        return False


def process_sendgrid_events(events: list[dict[str, Any]]) -> dict[str, int]:
    init_db()
    stored = 0
    opens = 0
    suppressions = 0
    with transaction(immediate=True) as connection:
        for event in events:
            event_type = str(event.get("event") or "unknown").lower()
            lead_id = event.get("lead_id") or (event.get("custom_args") or {}).get("lead_id")
            try:
                lead_id = int(lead_id) if lead_id else None
            except (TypeError, ValueError):
                lead_id = None
            event_key = str(event.get("sg_event_id") or f"{event.get('sg_message_id','')}:{event_type}:{event.get('timestamp','')}:{lead_id or ''}")
            timestamp_value = event.get("timestamp")
            try:
                event_at = datetime.fromtimestamp(float(timestamp_value), tz=timezone.utc).isoformat()
            except (TypeError, ValueError, OSError):
                event_at = utc_now()
            cursor = connection.execute(
                "INSERT OR IGNORE INTO provider_events(event_key,lead_id,event_type,timestamp,raw_json) VALUES(?,?,?,?,?)",
                (event_key, lead_id, event_type, event_at, json.dumps(event, ensure_ascii=False)),
            )
            if cursor.rowcount == 0:
                continue
            stored += 1
            if lead_id and event_type == "open":
                connection.execute("UPDATE leads SET opened_at=COALESCE(opened_at,?),updated_at=? WHERE id=?", (event_at, event_at, lead_id))
                opens += 1
            if lead_id and event_type in {"bounce", "dropped", "spamreport", "unsubscribe", "group_unsubscribe"}:
                lead = connection.execute("SELECT email FROM leads WHERE id=?", (lead_id,)).fetchone()
                if lead and lead["email"]:
                    connection.execute(
                        "INSERT OR REPLACE INTO suppressions(email,reason,created_at) VALUES(?,?,?)",
                        (lead["email"], f"SendGrid {event_type}", event_at),
                    )
                    connection.execute("UPDATE leads SET consent_status='revoked',updated_at=? WHERE id=?", (event_at, lead_id))
                    suppressions += 1
    return {"stored": stored, "opens": opens, "suppressions": suppressions}
