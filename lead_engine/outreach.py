from __future__ import annotations

import html
import json
import random
import re
import secrets
from datetime import datetime, time, timedelta, timezone
from typing import Any
from urllib import request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import settings, validate_sending_configuration
from .database import connect, get_campaign_settings, init_db, normalize_user_id, tenant_scoped, transaction, utc_now
from .gmail import gmail_status, send_gmail
from .groq_email import generate_email_text
from .qualification import primary_issue


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or settings.outreach_home_timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo(settings.outreach_home_timezone)


def _message_for(lead: dict[str, Any], generated_text: str) -> dict[str, str]:
    unsubscribe_url = f"{settings.public_base_url}/unsubscribe/{lead['unsubscribe_token']}"
    sender_line = f"{settings.sender_name} · {settings.business_name}"
    text_body = f"{generated_text.strip()}\n\n{sender_line}\nAdvertisement · {settings.physical_address}\nUnsubscribe: {unsubscribe_url}"
    website = f'<br><a href="{html.escape(settings.business_website, quote=True)}">{html.escape(settings.business_website)}</a>' if settings.business_website else ""
    html_body = (
        f"<p>{html.escape(generated_text.strip())}</p><p style=\"color:#64748b;font-size:12px\">"
        f"{html.escape(sender_line)}{website}<br>Advertisement · {html.escape(settings.physical_address)}<br>"
        f'<a href="{html.escape(unsubscribe_url, quote=True)}">Unsubscribe in one click</a></p>'
    )
    return {"subject": f"Quick question about {str(lead['name']).strip()}", "body_text": text_body,
            "body_html": html_body, "weakness": primary_issue(lead.get("weaknesses_json"))}


def _next_send_time(cursor: datetime) -> datetime:
    delay = random.randint(max(1, settings.minimum_delay_minutes), max(settings.minimum_delay_minutes, settings.maximum_delay_minutes))
    return cursor + timedelta(minutes=delay)


def _next_business_window(moment: datetime, timezone_name: str | None) -> datetime:
    zone = _zone(timezone_name)
    local = moment.astimezone(zone)
    start = max(0, min(settings.send_window_start_hour, 23))
    end = max(start + 1, min(settings.send_window_end_hour, 24))
    while True:
        if local.weekday() >= 5:
            local = datetime.combine(local.date() + timedelta(days=7-local.weekday()), time(start), zone)
            continue
        window_start = datetime.combine(local.date(), time(start), zone)
        window_end = datetime.combine(local.date(), time(end % 24), zone) + (timedelta(days=1) if end == 24 else timedelta())
        if local < window_start: return window_start.astimezone(timezone.utc)
        if local >= window_end:
            local = datetime.combine(local.date() + timedelta(days=1), time(start), zone)
            continue
        return local.astimezone(timezone.utc)


def _content_error(queue: dict[str, Any], lead: dict[str, Any]) -> str | None:
    if not str(lead.get("name") or "").strip() or not str(lead.get("email") or "").strip():
        return "empty personalization field"
    combined = f"{queue.get('subject','')} {queue.get('body_text','')} {queue.get('body_html','')}"
    if not str(queue.get("body_text") or "").strip() or not str(queue.get("body_html") or "").strip():
        return "generated email is empty"
    if re.search(r"{{\s*[^{}]+\s*}}", combined):
        return "unresolved template field"
    expected = f"/unsubscribe/{lead.get('unsubscribe_token','')}"
    if not lead.get("unsubscribe_token") or expected not in str(queue.get("body_text")) or expected not in str(queue.get("body_html")):
        return "unsubscribe link is missing"
    if queue.get("generation_provider") == "groq" and not queue.get("generated_at"):
        return "Groq generation result is missing"
    return None


def _log(connection: Any, user_id: str, status: str, *, campaign_id: str | None = None,
         batch_id: str | None = None, lead_id: int | None = None, queue_id: int | None = None,
         reason: str = "", detail: str = "", provider_message_id: str = "", at: str | None = None) -> int:
    stamp = at or utc_now()
    cursor = connection.execute(
        """INSERT INTO send_logs(user_id,campaign_id,batch_id,lead_id,queue_id,status,send_date,timestamp,
           provider_message_id,reason,detail) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (user_id, campaign_id, batch_id, lead_id, queue_id, status, stamp[:10], stamp,
         provider_message_id or None, reason or None, detail or None),
    )
    return int(cursor.lastrowid)


def _circuit_error(connection: Any, user_id: str, campaign: dict[str, Any]) -> str | None:
    if campaign.get("paused_at"):
        return str(campaign.get("pause_reason") or "campaign is paused")
    rows = connection.execute(
        "SELECT timestamp FROM send_logs WHERE user_id=? AND status='sent' ORDER BY timestamp DESC LIMIT ?",
        (user_id, int(campaign["circuit_breaker_window"])),
    ).fetchall()
    total = len(rows)
    if total < 10:
        return None
    cutoff = rows[-1]["timestamp"]
    bounces = connection.execute("SELECT COUNT(*) FROM send_logs WHERE user_id=? AND status='bounce' AND timestamp>=?", (user_id, cutoff)).fetchone()[0]
    complaints = connection.execute("SELECT COUNT(*) FROM send_logs WHERE user_id=? AND status='complaint' AND timestamp>=?", (user_id, cutoff)).fetchone()[0]
    bounce_rate, complaint_rate = bounces / total * 100, complaints / total * 100
    reason = None
    if bounce_rate > float(campaign["bounce_threshold_pct"]):
        reason = f"bounce-rate circuit breaker ({bounce_rate:.2f}% > {campaign['bounce_threshold_pct']}%)"
    elif complaint_rate > float(campaign["complaint_threshold_pct"]):
        reason = f"complaint-rate circuit breaker ({complaint_rate:.2f}% > {campaign['complaint_threshold_pct']}%)"
    if reason:
        now = utc_now()
        connection.execute("UPDATE campaigns SET paused_at=?,pause_reason=?,updated_at=? WHERE user_id=?", (now, reason, now, user_id))
    return reason


def _validation_error(connection: Any, user_id: str, campaign: dict[str, Any], queue: dict[str, Any],
                      lead: dict[str, Any], now: datetime, include_caps: bool = True) -> tuple[str, str] | None:
    circuit = _circuit_error(connection, user_id, campaign)
    if circuit:
        return "circuit-breaker", circuit
    if lead.get("consent_status") != "confirmed":
        return "consent", "documented affirmative consent is required"
    if connection.execute("SELECT 1 FROM suppressions WHERE user_id=? AND email=? COLLATE NOCASE", (user_id, lead["email"])).fetchone():
        return "suppression", "recipient is on this user's suppression list"
    since = (now - timedelta(days=int(campaign["duplicate_lookback_days"]))).isoformat()
    duplicate = connection.execute(
        """SELECT 1 FROM send_logs sl JOIN leads l ON l.id=sl.lead_id AND l.user_id=sl.user_id
           WHERE sl.user_id=? AND lower(l.email)=lower(?) AND sl.status='sent' AND sl.timestamp>=? LIMIT 1""",
        (user_id, lead["email"], since),
    ).fetchone()
    if duplicate:
        return "duplicate", "recipient was contacted inside the campaign lookback window"
    content = _content_error(queue, lead)
    if content:
        return "content", content
    if include_caps:
        day_count = connection.execute("SELECT COUNT(*) FROM send_logs WHERE user_id=? AND status IN('attempting','sent') AND send_date=?", (user_id, now.date().isoformat())).fetchone()[0]
        hour_count = connection.execute("SELECT COUNT(*) FROM send_logs WHERE user_id=? AND status IN('attempting','sent') AND timestamp>=?", (user_id, (now - timedelta(hours=1)).isoformat())).fetchone()[0]
        if day_count >= int(campaign["daily_cap"]):
            return "cap", "daily send cap reached"
        if hour_count >= int(campaign["hourly_cap"]):
            return "cap", "hourly send cap reached"
    return None


@tenant_scoped
def generate_batch(user_id: str, limit: int = 25, now: datetime | None = None) -> dict[str, Any]:
    init_db(); user_id = normalize_user_id(user_id); campaign = get_campaign_settings(user_id)
    if not settings.groq_api_key.strip():
        return {"success": False, "errors": ["GROQ_API_KEY is required"], "generated": 0}
    mode = str(campaign["workflow_mode"])
    if mode == "automatic" and not campaign["automatic_enabled"]:
        return {"success": False, "errors": ["Automatic mode has not been explicitly enabled"], "generated": 0}
    if campaign["sending_method"] == "gmail" and not gmail_status(user_id)["connected"]:
        return {"success": False, "errors": ["Connect Gmail before generating an automatic Gmail batch"], "generated": 0}
    batch_id = secrets.token_urlsafe(18); stamp = utc_now(); now_dt = now or datetime.now(timezone.utc)
    with transaction(True) as connection:
        connection.execute("INSERT INTO email_batches(id,user_id,campaign_id,status,workflow_mode,created_at) VALUES(?,?,?,?,?,?)",
                           (batch_id, user_id, campaign["id"], "generating", mode, stamp))
        rows = connection.execute(
            """SELECT l.* FROM leads l LEFT JOIN suppressions s ON s.user_id=l.user_id AND lower(s.email)=lower(l.email)
               WHERE l.user_id=? AND l.qualified=1 AND l.is_closed=0 AND l.email_valid=1 AND l.mx_valid=1
                 AND l.consent_status='confirmed' AND l.contacted_at IS NULL AND s.email IS NULL
                 AND NOT EXISTS(SELECT 1 FROM outreach_queue q WHERE q.user_id=l.user_id AND q.lead_id=l.id AND q.status IN('draft','queued','sending','sent'))
               ORDER BY l.review_count DESC,l.id LIMIT ?""", (user_id, max(1, min(limit, 100))),
        ).fetchall()
    items: list[dict[str, Any]] = []; failures = 0; cursor = now_dt
    for raw in rows:
        lead = dict(raw)
        try:
            copy = generate_email_text(lead, campaign)
            message = _message_for(lead, copy)
            queue = {**message, "generation_provider": "groq", "generated_at": utc_now()}
            status = "draft"
            with transaction(True) as connection:
                validation = _validation_error(connection, user_id, campaign, queue, lead, now_dt, include_caps=False)
                if mode == "automatic" and validation:
                    code, reason = validation
                    _log(connection, user_id, f"blocked-by-{code}", campaign_id=campaign["id"], batch_id=batch_id, lead_id=lead["id"], reason=reason)
                    failures += 1
                    continue
                if mode == "automatic":
                    status = "queued"
                cursor = _next_business_window(_next_send_time(cursor), lead.get("timezone"))
                result = connection.execute(
                    """INSERT INTO outreach_queue(user_id,campaign_id,batch_id,lead_id,scheduled_for,status,subject,body_text,body_html,
                       weakness,sending_method,generation_provider,generation_model,generated_at,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (user_id,campaign["id"],batch_id,lead["id"],cursor.isoformat(),status,message["subject"],message["body_text"],message["body_html"],
                     message["weakness"],campaign["sending_method"],"groq",campaign["groq_model"],queue["generated_at"],queue["generated_at"]),
                )
                queue_id = result.lastrowid
            items.append({"queueId":queue_id,"leadId":lead["id"],"business":lead["name"],"city":lead["city"],"email":lead["email"],
                          "subject":message["subject"],"body":message["body_text"],"status":status,"scheduledFor":cursor.isoformat()})
        except RuntimeError as exc:
            failures += 1
            with transaction(True) as connection:
                _log(connection,user_id,"groq-generation-failed",campaign_id=campaign["id"],batch_id=batch_id,lead_id=lead["id"],reason="groq-generation-failed",detail=str(exc))
    batch_status = "queued" if mode == "automatic" and items else "draft" if items else "failed"
    with transaction(True) as connection:
        connection.execute("UPDATE email_batches SET status=?,generated_count=?,failed_count=? WHERE id=? AND user_id=?",
                           (batch_status,len(items),failures,batch_id,user_id))
    return {"success":bool(items),"batchId":batch_id,"workflowMode":mode,"status":batch_status,"generated":len(items),"failed":failures,"items":items,
            "notice":"Emails were validated and queued automatically." if mode=="automatic" else "Drafts are stored. Review them, then use Approve & Send."}


@tenant_scoped
def approve_batch(user_id: str, batch_id: str) -> dict[str, Any]:
    user_id = normalize_user_id(user_id); approved = blocked = 0; now = datetime.now(timezone.utc)
    with transaction(True) as connection:
        batch = connection.execute("SELECT * FROM email_batches WHERE id=? AND user_id=?", (batch_id,user_id)).fetchone()
        if not batch: raise ValueError("Draft batch not found")
        campaign = dict(connection.execute("SELECT * FROM campaigns WHERE id=? AND user_id=?", (batch["campaign_id"],user_id)).fetchone())
        rows = connection.execute("""SELECT q.*,l.email,l.name,l.consent_status,l.unsubscribe_token FROM outreach_queue q
          JOIN leads l ON l.id=q.lead_id AND l.user_id=q.user_id WHERE q.user_id=? AND q.batch_id=? AND q.status='draft'""",(user_id,batch_id)).fetchall()
        for raw in rows:
            queue=dict(raw); lead={k:queue[k] for k in ("email","name","consent_status","unsubscribe_token")}
            validation=_validation_error(connection,user_id,campaign,queue,lead,now,include_caps=False)
            if validation:
                code,reason=validation; connection.execute("UPDATE outreach_queue SET status='blocked',error=? WHERE id=? AND user_id=?",(reason,queue["id"],user_id))
                _log(connection,user_id,f"blocked-by-{code}",campaign_id=campaign["id"],batch_id=batch_id,lead_id=queue["lead_id"],queue_id=queue["id"],reason=reason); blocked+=1
            else:
                connection.execute("UPDATE outreach_queue SET status='queued' WHERE id=? AND user_id=?",(queue["id"],user_id)); approved+=1
        connection.execute("UPDATE email_batches SET status=?,approved_at=? WHERE id=? AND user_id=?",("queued" if approved else "failed",utc_now(),batch_id,user_id))
    return {"success":bool(approved),"batchId":batch_id,"queued":approved,"blocked":blocked}


@tenant_scoped
def list_batches(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with connect() as connection:
        rows=connection.execute("""SELECT b.*,c.name campaign_name FROM email_batches b JOIN campaigns c ON c.id=b.campaign_id AND c.user_id=b.user_id
          WHERE b.user_id=? ORDER BY b.created_at DESC LIMIT ?""",(user_id,max(1,min(limit,100)))).fetchall()
    return [dict(row) for row in rows]


@tenant_scoped
def list_send_logs(user_id: str, limit: int = 100) -> list[dict[str, Any]]:
    with connect() as connection:
        rows=connection.execute("""SELECT sl.*,l.name business,l.email FROM send_logs sl LEFT JOIN leads l ON l.id=sl.lead_id AND l.user_id=sl.user_id
          WHERE sl.user_id=? ORDER BY sl.timestamp DESC LIMIT ?""",(user_id,max(1,min(limit,500)))).fetchall()
    return [dict(row) for row in rows]


def _sendgrid_send(queue: dict[str, Any], lead: dict[str, Any]) -> str:
    payload={"personalizations":[{"to":[{"email":lead["email"],"name":lead["name"]}],"custom_args":{"user_id":queue["user_id"],"lead_id":str(lead["id"]),"queue_id":str(queue["id"])}}],
             "from":{"email":settings.sender_email,"name":settings.sender_name},"reply_to":{"email":settings.reply_to_email,"name":settings.sender_name},"subject":queue["subject"],
             "content":[{"type":"text/plain","value":queue["body_text"]},{"type":"text/html","value":queue["body_html"]}],
             "headers":{"List-Unsubscribe":f"<{settings.public_base_url}/unsubscribe/{lead['unsubscribe_token']}>","List-Unsubscribe-Post":"List-Unsubscribe=One-Click"},
             "tracking_settings":{"open_tracking":{"enable":True}}}
    req=request.Request("https://api.sendgrid.com/v3/mail/send",data=json.dumps(payload).encode(),headers={"Authorization":f"Bearer {settings.sendgrid_api_key}","Content-Type":"application/json"},method="POST")
    with request.urlopen(req,timeout=20) as response:
        if response.status!=202: raise RuntimeError(f"SendGrid returned HTTP {response.status}")
        return response.headers.get("X-Message-Id","")


def dispatch_due(now: datetime | None = None, user_id: str | None = None) -> dict[str, Any]:
    init_db(); now=now or datetime.now(timezone.utc); requested=normalize_user_id(user_id) if user_id else None
    claimed: tuple[dict[str,Any],dict[str,Any],int]|None=None
    with transaction(True) as connection:
        clause="AND q.user_id=?" if requested else ""; params=(now.isoformat(),requested) if requested else (now.isoformat(),)
        row=connection.execute(f"""SELECT q.*,l.email,l.name,l.consent_status,l.unsubscribe_token,l.timezone,l.contacted_at
          FROM outreach_queue q JOIN leads l ON l.id=q.lead_id AND l.user_id=q.user_id JOIN campaigns c ON c.id=q.campaign_id AND c.user_id=q.user_id
          WHERE q.status='queued' AND q.scheduled_for<=? AND c.paused_at IS NULL {clause} ORDER BY q.scheduled_for LIMIT 1""",params).fetchone()
        if not row:return {"success":True,"sent":0,"reason":"nothing due"}
        queue=dict(row); uid=queue["user_id"]
        campaign=dict(connection.execute("SELECT * FROM campaigns WHERE id=? AND user_id=?",(queue["campaign_id"],uid)).fetchone())
        local_now=now.astimezone(_zone(queue.get("timezone")))
        if local_now.weekday()>=5 or not (settings.send_window_start_hour<=local_now.hour<settings.send_window_end_hour):
            scheduled=_next_business_window(now,queue.get("timezone"))
            connection.execute("UPDATE outreach_queue SET scheduled_for=? WHERE id=? AND user_id=?",(scheduled.isoformat(),queue["id"],uid))
            return {"success":True,"sent":0,"reason":"rescheduled into recipient business hours","scheduledFor":scheduled.isoformat()}
        errors=validate_sending_configuration(sending_method=queue["sending_method"])
        if queue["sending_method"]=="gmail" and not connection.execute("SELECT 1 FROM gmail_oauth_accounts WHERE user_id=?",(uid,)).fetchone():errors.append("Connect Gmail before sending")
        if errors:
            reason="; ".join(errors); connection.execute("UPDATE outreach_queue SET status='failed',error=? WHERE id=? AND user_id=?",(reason,queue["id"],uid))
            _log(connection,uid,"failed",campaign_id=queue["campaign_id"],batch_id=queue["batch_id"],lead_id=queue["lead_id"],queue_id=queue["id"],reason="configuration",detail=reason)
            return {"success":False,"sent":0,"error":reason}
        validation=_validation_error(connection,uid,campaign,queue,queue,now,include_caps=True)
        if validation:
            code,reason=validation
            if code=="cap":
                connection.execute("UPDATE outreach_queue SET scheduled_for=?,error=? WHERE id=? AND user_id=?",((now+timedelta(hours=1)).isoformat(),reason,queue["id"],uid))
            else:
                connection.execute("UPDATE outreach_queue SET status='blocked',error=? WHERE id=? AND user_id=?",(reason,queue["id"],uid))
            _log(connection,uid,f"blocked-by-{code}",campaign_id=queue["campaign_id"],batch_id=queue["batch_id"],lead_id=queue["lead_id"],queue_id=queue["id"],reason=reason)
            return {"success":True,"sent":0,"reason":reason}
        stamp=utc_now(); connection.execute("UPDATE outreach_queue SET status='sending',attempted_at=?,error=NULL WHERE id=? AND user_id=?",(stamp,queue["id"],uid))
        log_id=_log(connection,uid,"attempting",campaign_id=queue["campaign_id"],batch_id=queue["batch_id"],lead_id=queue["lead_id"],queue_id=queue["id"],reason="provider-attempt",at=stamp)
        claimed=(queue,queue,log_id)
    queue,lead,log_id=claimed
    try:
        message_id=send_gmail(queue["user_id"],queue,lead) if queue["sending_method"]=="gmail" else _sendgrid_send(queue,lead)
        stamp=utc_now()
        with transaction(True) as connection:
            connection.execute("UPDATE outreach_queue SET status='sent',provider_message_id=?,error=NULL WHERE id=? AND user_id=?",(message_id,queue["id"],queue["user_id"]))
            connection.execute("UPDATE leads SET contacted_at=?,outreach_attempted_at=?,updated_at=? WHERE id=? AND user_id=?",(stamp,stamp,stamp,lead["lead_id"],queue["user_id"]))
            connection.execute("UPDATE send_logs SET status='sent',timestamp=?,provider_message_id=?,detail=? WHERE id=? AND user_id=?",(stamp,message_id,f"Accepted by {queue['sending_method']}",log_id,queue["user_id"]))
        return {"success":True,"sent":1,"leadId":lead["lead_id"],"provider":queue["sending_method"],"providerMessageId":message_id}
    except Exception as exc:
        stamp=utc_now()
        with transaction(True) as connection:
            connection.execute("UPDATE outreach_queue SET status='failed',error=? WHERE id=? AND user_id=?",(str(exc),queue["id"],queue["user_id"]))
            connection.execute("UPDATE send_logs SET status='failed',timestamp=?,reason='provider-failed',detail=? WHERE id=? AND user_id=?",(stamp,str(exc),log_id,queue["user_id"]))
        return {"success":False,"sent":0,"error":str(exc),"leadId":lead["lead_id"]}


def verify_sendgrid_signature(payload: bytes,signature: str,timestamp: str) -> bool:
    if not settings.sendgrid_webhook_verification_key.strip():return bool(settings.sendgrid_webhook_token)
    try:
        from sendgrid.helpers.eventwebhook import EventWebhook
        webhook=EventWebhook(); key=webhook.convert_public_key_to_ecdsa(settings.sendgrid_webhook_verification_key.strip())
        return bool(webhook.verify_signature(payload,signature,timestamp,key))
    except Exception:return False


def process_sendgrid_events(events: list[dict[str,Any]]) -> dict[str,int]:
    stored=opens=suppressions=0
    with transaction(True) as connection:
        for event in events:
            custom=event.get("custom_args") or {}; uid=str(event.get("user_id") or custom.get("user_id") or ""); lead_id=event.get("lead_id") or custom.get("lead_id")
            try:lead_id=int(lead_id) if lead_id else None
            except (TypeError,ValueError):lead_id=None
            if not uid and lead_id:
                owner=connection.execute("SELECT user_id FROM leads WHERE id=?",(lead_id,)).fetchone(); uid=owner["user_id"] if owner else ""
            if not uid or not connection.execute("SELECT 1 FROM app_users WHERE id=?",(uid,)).fetchone():continue
            kind=str(event.get("event") or "unknown").lower(); key=str(event.get("sg_event_id") or f"{event.get('sg_message_id','')}:{kind}:{event.get('timestamp','')}:{lead_id or ''}")
            try:stamp=datetime.fromtimestamp(float(event.get("timestamp")),timezone.utc).isoformat()
            except (TypeError,ValueError,OSError):stamp=utc_now()
            if connection.execute("INSERT OR IGNORE INTO provider_events VALUES(?,?,?,?,?,?)",(key,uid,lead_id,kind,stamp,json.dumps(event,ensure_ascii=False))).rowcount==0:continue
            stored+=1
            if lead_id and kind=="open":connection.execute("UPDATE leads SET opened_at=COALESCE(opened_at,?),updated_at=? WHERE id=? AND user_id=?",(stamp,stamp,lead_id,uid));opens+=1
            if lead_id and kind in {"bounce","dropped","spamreport","unsubscribe","group_unsubscribe"}:
                lead=connection.execute("SELECT email FROM leads WHERE id=? AND user_id=?",(lead_id,uid)).fetchone()
                if lead and lead["email"]:
                    connection.execute("INSERT OR REPLACE INTO suppressions VALUES(?,?,?,?)",(uid,lead["email"],f"SendGrid {kind}",stamp));suppressions+=1
                status="complaint" if kind=="spamreport" else "bounce" if kind in {"bounce","dropped"} else "unsubscribe"
                _log(connection,uid,status,lead_id=lead_id,reason=f"sendgrid-{kind}",at=stamp)
    return {"stored":stored,"opens":opens,"suppressions":suppressions}
