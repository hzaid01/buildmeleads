from __future__ import annotations

import functools
import hashlib
import inspect
import json
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

from .config import settings
from .qualification import detect_weaknesses, issue_summary, is_qualified

LEGACY_OWNER_ID = "local-owner"
DEFAULT_PROMPT = """Write 1-2 short, natural sentences for a cold outreach email.
Business: {{business_name}}
City: {{city}}
Detected Google Business Profile weaknesses: {{weaknesses}}
Offer: {{offer}}
Call to action: {{cta}}
Use a calm, curiosity-driven, human tone. Avoid hype, sales language, invented facts, greetings, signatures, and footer text."""

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS app_users(
 id TEXT PRIMARY KEY,email TEXT COLLATE NOCASE UNIQUE,password_hash TEXT,display_name TEXT NOT NULL DEFAULT '',
 role TEXT NOT NULL DEFAULT 'member' CHECK(role IN('admin','member')),
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN('pending','active','disabled')),
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
 id INTEGER PRIMARY KEY AUTOINCREMENT,token_hash TEXT NOT NULL UNIQUE,
 user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL,last_seen_at TEXT NOT NULL,expires_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id,expires_at);
CREATE TABLE IF NOT EXISTS leads(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 source_key TEXT NOT NULL,source TEXT NOT NULL DEFAULT 'gosom',place_id TEXT,cid TEXT,name TEXT NOT NULL,
 niche TEXT,category TEXT,city TEXT,timezone TEXT,address TEXT,phone TEXT,website TEXT,email TEXT,email_source TEXT,
 email_valid INTEGER NOT NULL DEFAULT 0,mx_valid INTEGER NOT NULL DEFAULT 0,rating REAL NOT NULL DEFAULT 0,
 review_count INTEGER NOT NULL DEFAULT 0,rank INTEGER,photo_count INTEGER NOT NULL DEFAULT 0,last_review_at TEXT,
 is_closed INTEGER NOT NULL DEFAULT 0,weaknesses_json TEXT NOT NULL DEFAULT '[]',issue_detected TEXT NOT NULL DEFAULT '',
 qualified INTEGER NOT NULL DEFAULT 0,consent_status TEXT NOT NULL DEFAULT 'unknown' CHECK(consent_status IN('unknown','confirmed','revoked')),
 whatsapp_verified INTEGER,unsubscribe_token TEXT NOT NULL UNIQUE,outreach_attempted_at TEXT,contacted_at TEXT,
 opened_at TEXT,replied_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,raw_json TEXT NOT NULL DEFAULT '{}',
 UNIQUE(user_id,source_key));
CREATE INDEX IF NOT EXISTS idx_leads_user_pipeline ON leads(user_id,qualified,email_valid,mx_valid,contacted_at);
CREATE INDEX IF NOT EXISTS idx_leads_user_city ON leads(user_id,city);
CREATE TABLE IF NOT EXISTS scrape_runs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 source TEXT NOT NULL,query TEXT,imported_count INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_scrape_runs_user ON scrape_runs(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS campaigns(
 id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,name TEXT NOT NULL,
 sending_method TEXT NOT NULL DEFAULT 'sendgrid' CHECK(sending_method IN('sendgrid','gmail')),
 workflow_mode TEXT NOT NULL DEFAULT 'manual' CHECK(workflow_mode IN('manual','automatic')),
 offer TEXT NOT NULL,cta TEXT NOT NULL,prompt_template TEXT NOT NULL,
 groq_model TEXT NOT NULL DEFAULT 'openai/gpt-oss-120b' CHECK(groq_model IN('openai/gpt-oss-120b','openai/gpt-oss-20b')),
 daily_cap INTEGER NOT NULL DEFAULT 10 CHECK(daily_cap BETWEEN 1 AND 10000),
 hourly_cap INTEGER NOT NULL DEFAULT 3 CHECK(hourly_cap BETWEEN 1 AND 1000),
 duplicate_lookback_days INTEGER NOT NULL DEFAULT 90 CHECK(duplicate_lookback_days BETWEEN 1 AND 3650),
 bounce_threshold_pct REAL NOT NULL DEFAULT 5 CHECK(bounce_threshold_pct BETWEEN 0 AND 100),
 complaint_threshold_pct REAL NOT NULL DEFAULT .3 CHECK(complaint_threshold_pct BETWEEN 0 AND 100),
 circuit_breaker_window INTEGER NOT NULL DEFAULT 100 CHECK(circuit_breaker_window BETWEEN 10 AND 10000),
 automatic_enabled INTEGER NOT NULL DEFAULT 0 CHECK(automatic_enabled IN(0,1)),paused_at TEXT,pause_reason TEXT,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(user_id,name));
CREATE INDEX IF NOT EXISTS idx_campaigns_user ON campaigns(user_id,updated_at DESC);
CREATE TABLE IF NOT EXISTS email_batches(
 id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
 status TEXT NOT NULL CHECK(status IN('generating','draft','queued','partial','failed','completed')),
 workflow_mode TEXT NOT NULL CHECK(workflow_mode IN('manual','automatic')),
 generated_count INTEGER NOT NULL DEFAULT 0,failed_count INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,approved_at TEXT);
CREATE INDEX IF NOT EXISTS idx_batches_user ON email_batches(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS outreach_queue(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,batch_id TEXT NOT NULL REFERENCES email_batches(id) ON DELETE CASCADE,
 lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,scheduled_for TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN('draft','queued','sending','sent','failed','cancelled','blocked')),
 subject TEXT NOT NULL,body_text TEXT NOT NULL,body_html TEXT NOT NULL,weakness TEXT NOT NULL,
 sending_method TEXT NOT NULL CHECK(sending_method IN('sendgrid','gmail')),generation_provider TEXT NOT NULL DEFAULT 'groq',
 generation_model TEXT NOT NULL,generated_at TEXT NOT NULL,created_at TEXT NOT NULL,attempted_at TEXT,
 provider_message_id TEXT,error TEXT,UNIQUE(user_id,batch_id,lead_id));
CREATE INDEX IF NOT EXISTS idx_queue_user_due ON outreach_queue(user_id,status,scheduled_for);
CREATE INDEX IF NOT EXISTS idx_queue_user_campaign ON outreach_queue(user_id,campaign_id,batch_id);
CREATE TABLE IF NOT EXISTS send_logs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 campaign_id TEXT REFERENCES campaigns(id) ON DELETE SET NULL,batch_id TEXT REFERENCES email_batches(id) ON DELETE SET NULL,
 lead_id INTEGER REFERENCES leads(id) ON DELETE SET NULL,queue_id INTEGER REFERENCES outreach_queue(id) ON DELETE SET NULL,
 status TEXT NOT NULL,send_date TEXT NOT NULL,timestamp TEXT NOT NULL,provider_message_id TEXT,reason TEXT,detail TEXT);
CREATE INDEX IF NOT EXISTS idx_send_logs_user_time ON send_logs(user_id,timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_send_logs_user_status ON send_logs(user_id,status,send_date);
CREATE TABLE IF NOT EXISTS suppressions(
 user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,email TEXT NOT NULL COLLATE NOCASE,
 reason TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(user_id,email));
CREATE INDEX IF NOT EXISTS idx_suppressions_user ON suppressions(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS provider_events(
 event_key TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 lead_id INTEGER REFERENCES leads(id) ON DELETE SET NULL,event_type TEXT NOT NULL,timestamp TEXT NOT NULL,raw_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_provider_events_user ON provider_events(user_id,timestamp DESC);
CREATE TABLE IF NOT EXISTS analytics_results(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 result_type TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_analytics_user ON analytics_results(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS gmail_oauth_accounts(
 user_id TEXT PRIMARY KEY REFERENCES app_users(id) ON DELETE CASCADE,refresh_token_encrypted BLOB NOT NULL,
 access_token_encrypted BLOB,access_token_expires_at TEXT,scope TEXT NOT NULL,token_type TEXT NOT NULL DEFAULT 'Bearer',
 connected_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_gmail_tokens_user ON gmail_oauth_accounts(user_id);
CREATE TABLE IF NOT EXISTS oauth_states(
 state_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,expires_at TEXT NOT NULL,used_at TEXT);
CREATE INDEX IF NOT EXISTS idx_oauth_states_user ON oauth_states(user_id,expires_at);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
"""

class TenantScopeError(ValueError):
    pass

F = TypeVar("F", bound=Callable[..., Any])

def tenant_scoped(function: F) -> F:
    signature = inspect.signature(function)
    @functools.wraps(function)
    def guarded(*args: Any, **kwargs: Any) -> Any:
        user_id = str(signature.bind_partial(*args, **kwargs).arguments.get("user_id") or "").strip()
        if not user_id:
            raise TenantScopeError(f"{function.__name__} requires authenticated user_id scope")
        return function(*args, **kwargs)
    return guarded  # type: ignore[return-value]

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

def _exists(c: sqlite3.Connection, table: str) -> bool:
    return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())

def _columns(c: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in c.execute(f"PRAGMA table_info({table})")}

def _campaign_id(user_id: str) -> str:
    return "campaign-" + hashlib.sha256(user_id.encode()).hexdigest()[:20]

def _migrate_legacy(c: sqlite3.Connection) -> None:
    if not _exists(c, "leads") or "user_id" in _columns(c, "leads"):
        return
    names = ("app_users","leads","scrape_runs","campaign_settings","gmail_oauth_accounts","oauth_states","outreach_queue","send_logs","suppressions","provider_events")
    old = {name: [dict(row) for row in c.execute(f"SELECT * FROM {name}")] if _exists(c, name) else [] for name in names}
    now = utc_now()
    c.commit(); c.execute("PRAGMA foreign_keys=OFF"); c.execute("BEGIN IMMEDIATE")
    try:
        for name in reversed(names):
            if _exists(c, name):
                c.execute(f"ALTER TABLE {name} RENAME TO legacy_{name}")
        c.executescript(SCHEMA)
        users = old["app_users"] or [{"id": LEGACY_OWNER_ID,"display_name":"Legacy owner","created_at":now}]
        known: set[str] = set()
        for row in users:
            uid = str(row.get("id") or LEGACY_OWNER_ID); known.add(uid)
            c.execute("INSERT INTO app_users(id,email,password_hash,display_name,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                      (uid,row.get("email"),row.get("password_hash"),row.get("display_name") or "Legacy owner",row.get("role") or "admin",
                       "active" if row.get("password_hash") else "pending",row.get("created_at") or now,row.get("updated_at") or now))
        if LEGACY_OWNER_ID not in known:
            c.execute("INSERT INTO app_users VALUES(?,?,?,?,?,?,?,?)",(LEGACY_OWNER_ID,None,None,"Legacy owner","admin","pending",now,now))
        lead_owner: dict[int,str] = {}
        for row in old["leads"]:
            uid = str(row.pop("user_id", None) or LEGACY_OWNER_ID); lead_owner[int(row["id"])] = uid
            keys = list(row)
            c.execute(f"INSERT INTO leads(user_id,{','.join(keys)}) VALUES(?,{','.join('?' for _ in keys)})",[uid,*[row[k] for k in keys]])
        for row in old["scrape_runs"]:
            c.execute("INSERT INTO scrape_runs VALUES(?,?,?,?,?,?)",(row["id"],row.get("user_id") or LEGACY_OWNER_ID,row.get("source") or "legacy",row.get("query"),row.get("imported_count") or 0,row.get("created_at") or now))
        campaign_ids: dict[str,str] = {}
        for row in old["campaign_settings"] or [{"user_id":LEGACY_OWNER_ID}]:
            uid = str(row.get("user_id") or LEGACY_OWNER_ID); cid = _campaign_id(uid); campaign_ids[uid] = cid
            c.execute("""INSERT INTO campaigns(id,user_id,name,sending_method,workflow_mode,offer,cta,prompt_template,groq_model,
              daily_cap,hourly_cap,duplicate_lookback_days,bounce_threshold_pct,complaint_threshold_pct,circuit_breaker_window,
              automatic_enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (cid,uid,settings.campaign_name,row.get("sending_method") or "sendgrid","manual",row.get("offer") or settings.campaign_offer,
               row.get("cta") or settings.campaign_cta,DEFAULT_PROMPT,settings.groq_model,10,3,90,5,.3,100,0,row.get("updated_at") or now,row.get("updated_at") or now))
        batches: dict[str,str] = {}
        for row in old["outreach_queue"]:
            uid = str(row.get("user_id") or lead_owner.get(int(row["lead_id"]),LEGACY_OWNER_ID)); cid = campaign_ids.get(uid)
            if not cid:
                cid = _campaign_id(uid); campaign_ids[uid] = cid
                c.execute("""INSERT INTO campaigns(id,user_id,name,sending_method,workflow_mode,offer,cta,prompt_template,groq_model,created_at,updated_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(cid,uid,settings.campaign_name,row.get("sending_method") or "sendgrid","manual",settings.campaign_offer,settings.campaign_cta,DEFAULT_PROMPT,settings.groq_model,now,now))
            bid = batches.setdefault(uid,"legacy-batch-"+hashlib.sha256(uid.encode()).hexdigest()[:16])
            c.execute("INSERT OR IGNORE INTO email_batches(id,user_id,campaign_id,status,workflow_mode,created_at) VALUES(?,?,?,?,?,?)",(bid,uid,cid,"draft","manual",row.get("created_at") or now))
            status = row.get("status") or "draft"
            if status not in {"draft", "queued", "sending", "sent", "failed", "cancelled", "blocked"}:
                status = "draft"
            c.execute("""INSERT INTO outreach_queue(id,user_id,campaign_id,batch_id,lead_id,scheduled_for,status,subject,body_text,body_html,
              weakness,sending_method,generation_provider,generation_model,generated_at,created_at,attempted_at,provider_message_id,error)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (row["id"],uid,cid,bid,row["lead_id"],row.get("scheduled_for") or now,status,row.get("subject") or "",row.get("body_text") or "",
               row.get("body_html") or "",row.get("weakness") or "",row.get("sending_method") or "sendgrid",row.get("generation_provider") or "legacy-template",
               row.get("generation_model") or "",row.get("generated_at") or row.get("created_at") or now,row.get("created_at") or now,
               row.get("attempted_at"),row.get("provider_message_id"),row.get("error")))
        for row in old["send_logs"]:
            lead_id = row.get("lead_id"); uid = str(row.get("user_id") or (lead_owner.get(int(lead_id)) if lead_id else None) or LEGACY_OWNER_ID)
            c.execute("""INSERT INTO send_logs(id,user_id,campaign_id,batch_id,lead_id,queue_id,status,send_date,timestamp,provider_message_id,reason,detail)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",(row["id"],uid,campaign_ids.get(uid),batches.get(uid),lead_id,row.get("queue_id"),row.get("status") or "legacy",
               row.get("send_date") or str(row.get("timestamp") or now)[:10],row.get("timestamp") or now,row.get("provider_message_id"),row.get("detail"),row.get("detail")))
        for row in old["suppressions"]:
            c.execute("INSERT OR IGNORE INTO suppressions VALUES(?,?,?,?)",(row.get("user_id") or LEGACY_OWNER_ID,row["email"],row.get("reason") or "legacy",row.get("created_at") or now))
        for row in old["provider_events"]:
            lead_id=row.get("lead_id"); uid=str(row.get("user_id") or (lead_owner.get(int(lead_id)) if lead_id else None) or LEGACY_OWNER_ID)
            c.execute("INSERT INTO provider_events VALUES(?,?,?,?,?,?)",(row["event_key"],uid,lead_id,row.get("event_type") or "legacy",row.get("timestamp") or now,row.get("raw_json") or "{}"))
        for row in old["gmail_oauth_accounts"]:
            c.execute("INSERT INTO gmail_oauth_accounts VALUES(?,?,?,?,?,?,?,?)",tuple(row.get(k) for k in ("user_id","refresh_token_encrypted","access_token_encrypted","access_token_expires_at","scope","token_type","connected_at","updated_at")))
        for row in old["oauth_states"]:
            c.execute("INSERT INTO oauth_states VALUES(?,?,?,?)",tuple(row.get(k) for k in ("state_hash","user_id","expires_at","used_at")))
        for name in reversed(names):
            if _exists(c,f"legacy_{name}"): c.execute(f"DROP TABLE legacy_{name}")
        c.commit()
    except Exception:
        c.rollback(); raise
    finally:
        c.execute("PRAGMA foreign_keys=ON")

def _migrate_groq_models(c: sqlite3.Connection) -> None:
    """Replace retired Groq model constraints while preserving campaigns and their foreign keys."""
    if not _exists(c, "campaigns"):
        return
    schema = str(c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='campaigns'").fetchone()[0] or "")
    if "openai/gpt-oss-120b" in schema:
        return
    c.commit()
    c.execute("PRAGMA foreign_keys=OFF")
    try:
        c.execute("BEGIN IMMEDIATE")
        c.execute("""CREATE TABLE campaigns_groq_migration(
         id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,name TEXT NOT NULL,
         sending_method TEXT NOT NULL DEFAULT 'sendgrid' CHECK(sending_method IN('sendgrid','gmail')),
         workflow_mode TEXT NOT NULL DEFAULT 'manual' CHECK(workflow_mode IN('manual','automatic')),
         offer TEXT NOT NULL,cta TEXT NOT NULL,prompt_template TEXT NOT NULL,
         groq_model TEXT NOT NULL DEFAULT 'openai/gpt-oss-120b' CHECK(groq_model IN('openai/gpt-oss-120b','openai/gpt-oss-20b')),
         daily_cap INTEGER NOT NULL DEFAULT 10 CHECK(daily_cap BETWEEN 1 AND 10000),
         hourly_cap INTEGER NOT NULL DEFAULT 3 CHECK(hourly_cap BETWEEN 1 AND 1000),
         duplicate_lookback_days INTEGER NOT NULL DEFAULT 90 CHECK(duplicate_lookback_days BETWEEN 1 AND 3650),
         bounce_threshold_pct REAL NOT NULL DEFAULT 5 CHECK(bounce_threshold_pct BETWEEN 0 AND 100),
         complaint_threshold_pct REAL NOT NULL DEFAULT .3 CHECK(complaint_threshold_pct BETWEEN 0 AND 100),
         circuit_breaker_window INTEGER NOT NULL DEFAULT 100 CHECK(circuit_breaker_window BETWEEN 10 AND 10000),
         automatic_enabled INTEGER NOT NULL DEFAULT 0 CHECK(automatic_enabled IN(0,1)),paused_at TEXT,pause_reason TEXT,
         created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(user_id,name))""")
        columns = "id,user_id,name,sending_method,workflow_mode,offer,cta,prompt_template,groq_model,daily_cap,hourly_cap,duplicate_lookback_days,bounce_threshold_pct,complaint_threshold_pct,circuit_breaker_window,automatic_enabled,paused_at,pause_reason,created_at,updated_at"
        c.execute(f"""INSERT INTO campaigns_groq_migration({columns}) SELECT
         id,user_id,name,sending_method,workflow_mode,offer,cta,prompt_template,
         CASE groq_model WHEN 'llama-3.1-8b-instant' THEN 'openai/gpt-oss-20b' ELSE 'openai/gpt-oss-120b' END,
         daily_cap,hourly_cap,duplicate_lookback_days,bounce_threshold_pct,complaint_threshold_pct,circuit_breaker_window,
         automatic_enabled,paused_at,pause_reason,created_at,updated_at FROM campaigns""")
        c.execute("DROP TABLE campaigns")
        c.execute("ALTER TABLE campaigns_groq_migration RENAME TO campaigns")
        c.execute("CREATE INDEX idx_campaigns_user ON campaigns(user_id,updated_at DESC)")
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.execute("PRAGMA foreign_keys=ON")
    violations = c.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError("Groq model migration left invalid campaign references")

def init_db() -> None:
    with connect() as c:
        _migrate_legacy(c); _migrate_groq_models(c); c.executescript(SCHEMA)
        if not c.execute("SELECT 1 FROM app_users LIMIT 1").fetchone():
            now=utc_now(); c.execute("INSERT INTO app_users VALUES(?,?,?,?,?,?,?,?)",(LEGACY_OWNER_ID,None,None,"Legacy owner","admin","pending",now,now))

def normalize_user_id(value: str | None) -> str:
    candidate=re.sub(r"[^A-Za-z0-9_-]","",str(value or "").strip())[:64]
    if not candidate: raise TenantScopeError("A valid authenticated user_id is required")
    return candidate

@tenant_scoped
def get_campaign_settings(user_id: str) -> dict[str,Any]:
    init_db(); user_id=normalize_user_id(user_id)
    with connect() as c: row=c.execute("SELECT * FROM campaigns WHERE user_id=? ORDER BY created_at LIMIT 1",(user_id,)).fetchone()
    if not row: raise ValueError("Campaign not found")
    return dict(row)

@tenant_scoped
def update_campaign_settings(user_id: str, values: dict[str,Any]) -> dict[str,Any]:
    user_id=normalize_user_id(user_id); campaign=get_campaign_settings(user_id)
    allowed={"name","sending_method","workflow_mode","offer","cta","prompt_template","groq_model","daily_cap","hourly_cap","duplicate_lookback_days","bounce_threshold_pct","complaint_threshold_pct","circuit_breaker_window","automatic_enabled"}
    updates={k:v for k,v in values.items() if k in allowed}
    if updates.get("sending_method") not in {None,"sendgrid","gmail"}: raise ValueError("Sending method must be sendgrid or gmail")
    if updates.get("workflow_mode") not in {None,"manual","automatic"}: raise ValueError("Workflow mode must be manual or automatic")
    if updates.get("groq_model") not in {None,"openai/gpt-oss-120b","openai/gpt-oss-20b"}: raise ValueError("Unsupported Groq model")
    if updates.get("workflow_mode")=="automatic" and not bool(updates.get("automatic_enabled")): raise ValueError("Automatic mode requires explicit confirmation")
    for field in ("name","offer","cta","prompt_template"):
        if field in updates and not str(updates[field] or "").strip(): raise ValueError(f"{field} is required")
    if updates:
        with transaction(True) as c:
            c.execute(f"UPDATE campaigns SET {','.join(k+'=?' for k in updates)},updated_at=? WHERE id=? AND user_id=?",[*updates.values(),utc_now(),campaign["id"],user_id])
    return get_campaign_settings(user_id)

def _source_key(lead: dict[str,Any]) -> str:
    for field in ("placeId","place_id","cid","dataId","data_id"):
        value=str(lead.get(field) or "").strip()
        if value: return f"google:{field.lower()}:{value}"
    identity="|".join(re.sub(r"\s+"," ",str(lead.get(f) or "").strip().lower()) for f in ("name","address","phone"))
    return "fallback:"+hashlib.sha256(identity.encode()).hexdigest()

def _num(value: Any, cast: Callable[[Any],Any], default: Any=0) -> Any:
    try: return cast(value)
    except (TypeError,ValueError): return default

@tenant_scoped
def upsert_leads(user_id: str, leads: list[dict[str,Any]], source: str="gosom", query: str="") -> dict[str,int]:
    init_db(); user_id=normalize_user_id(user_id); inserted=updated=0; now=utc_now()
    with transaction(True) as c:
        for raw in leads:
            name=str(raw.get("name") or raw.get("title") or "Unknown Business").strip(); website=raw.get("website") or raw.get("url") or ""
            rating=_num(raw.get("rating",raw.get("review_rating",0)),float); reviews=_num(raw.get("reviewCount",raw.get("review_count",0)),lambda v:int(float(v)))
            photos=_num(raw.get("photoCount",raw.get("photo_count",0)),lambda v:int(float(v))); normalized={**raw,"website":website,"rating":rating,"reviewCount":reviews,"photoCount":photos}
            weaknesses=raw.get("weaknesses") or detect_weaknesses(normalized)
            if isinstance(weaknesses,str):
                try: weaknesses=json.loads(weaknesses)
                except json.JSONDecodeError: weaknesses=[weaknesses]
            key=_source_key(raw); exists=c.execute("SELECT 1 FROM leads WHERE user_id=? AND source_key=?",(user_id,key)).fetchone()
            v={"user_id":user_id,"source_key":key,"source":str(raw.get("source") or source),"place_id":raw.get("placeId") or raw.get("place_id"),"cid":raw.get("cid"),"name":name,
               "niche":raw.get("niche") or raw.get("category") or "","category":raw.get("category") or raw.get("niche") or "","city":raw.get("city") or "","timezone":raw.get("timezone") or "America/New_York",
               "address":raw.get("address") or raw.get("fullAddress") or "","phone":raw.get("phone") or raw.get("phoneNumber") or "","website":website,"email":str(raw.get("email") or "").strip().lower(),
               "rating":rating,"review_count":reviews,"rank":_num(raw.get("rank"),lambda x:int(float(x)),None),"photo_count":photos,"last_review_at":raw.get("lastReviewAt") or raw.get("last_review_at"),
               "is_closed":int(bool(raw.get("isClosed") or raw.get("permanentlyClosed"))),"weaknesses_json":json.dumps(weaknesses,ensure_ascii=False),"issue_detected":issue_summary(weaknesses),
               "qualified":int(is_qualified(normalized,weaknesses) and not raw.get("isClosed")),"whatsapp_verified":None if raw.get("whatsappVerified") is None else int(bool(raw.get("whatsappVerified"))),
               "raw_json":json.dumps(raw,ensure_ascii=False,default=str),"updated_at":now}
            if exists:
                c.execute("""UPDATE leads SET source=:source,place_id=COALESCE(:place_id,place_id),cid=COALESCE(:cid,cid),name=:name,niche=:niche,category=:category,city=:city,timezone=:timezone,
                 address=:address,phone=:phone,website=:website,email=CASE WHEN :email<>'' THEN :email ELSE email END,rating=:rating,review_count=:review_count,rank=:rank,photo_count=:photo_count,
                 last_review_at=COALESCE(:last_review_at,last_review_at),is_closed=:is_closed,weaknesses_json=:weaknesses_json,issue_detected=:issue_detected,qualified=:qualified,
                 whatsapp_verified=COALESCE(:whatsapp_verified,whatsapp_verified),raw_json=:raw_json,updated_at=:updated_at WHERE user_id=:user_id AND source_key=:source_key""",v); updated+=1
            else:
                c.execute("""INSERT INTO leads(user_id,source_key,source,place_id,cid,name,niche,category,city,timezone,address,phone,website,email,rating,review_count,rank,photo_count,last_review_at,is_closed,
                 weaknesses_json,issue_detected,qualified,whatsapp_verified,unsubscribe_token,created_at,updated_at,raw_json) VALUES(:user_id,:source_key,:source,:place_id,:cid,:name,:niche,:category,:city,:timezone,
                 :address,:phone,:website,:email,:rating,:review_count,:rank,:photo_count,:last_review_at,:is_closed,:weaknesses_json,:issue_detected,:qualified,:whatsapp_verified,:unsubscribe_token,:created_at,:updated_at,:raw_json)""",
                 {**v,"unsubscribe_token":secrets.token_urlsafe(32),"created_at":now}); inserted+=1
        c.execute("INSERT INTO scrape_runs(user_id,source,query,imported_count,created_at) VALUES(?,?,?,?,?)",(user_id,source,query,len(leads),now))
    return {"received":len(leads),"inserted":inserted,"updated":updated}

@tenant_scoped
def list_leads(user_id: str,limit: int=250,offset: int=0,qualified_only: bool=False) -> dict[str,Any]:
    clause=" AND qualified=1" if qualified_only else ""; user_id=normalize_user_id(user_id)
    with connect() as c:
        total=c.execute(f"SELECT COUNT(*) FROM leads WHERE user_id=?{clause}",(user_id,)).fetchone()[0]
        rows=c.execute(f"""SELECT id,name,niche,city,timezone,issue_detected,weaknesses_json,email,email_valid,mx_valid,website,phone,rating,review_count,qualified,consent_status,
          whatsapp_verified,outreach_attempted_at,contacted_at,opened_at,replied_at,source,updated_at FROM leads WHERE user_id=?{clause}
          ORDER BY qualified DESC,contacted_at IS NOT NULL,review_count DESC,id DESC LIMIT ? OFFSET ?""",(user_id,max(1,min(limit,1000)),max(0,offset))).fetchall()
    return {"total":total,"leads":[dict(r) for r in rows]}

@tenant_scoped
def analytics(user_id: str) -> dict[str,Any]:
    user_id=normalize_user_id(user_id)
    with connect() as c:
        counts=dict(c.execute("""SELECT COUNT(*) total,SUM(qualified=1) qualified,SUM(email_valid=1 AND mx_valid=1) sendable,SUM(contacted_at IS NOT NULL) sent,
          SUM(opened_at IS NOT NULL) opened,SUM(replied_at IS NOT NULL) replied,SUM(consent_status='confirmed') consented FROM leads WHERE user_id=?""",(user_id,)).fetchone())
        daily=[dict(r) for r in c.execute("SELECT send_date date,SUM(status='sent') sent FROM send_logs WHERE user_id=? GROUP BY send_date ORDER BY send_date DESC LIMIT 14",(user_id,))]
        queue=dict(c.execute("SELECT SUM(status='queued') queued,SUM(status='draft') drafts FROM outreach_queue WHERE user_id=? AND status IN('queued','draft')",(user_id,)).fetchone())
    sent=counts.get("sent") or 0; opened=counts.get("opened") or 0; replied=counts.get("replied") or 0
    return {**{k:v or 0 for k,v in counts.items()},**{k:v or 0 for k,v in queue.items()},"replyRate":round(replied/sent*100,1) if sent else 0,"openRate":round(opened/sent*100,1) if sent else 0,"daily":daily}

@tenant_scoped
def set_consent(user_id: str,lead_id: int,confirmed: bool) -> bool:
    user_id=normalize_user_id(user_id); now=utc_now()
    with transaction(True) as c:
        row=c.execute("SELECT email FROM leads WHERE id=? AND user_id=?",(lead_id,user_id)).fetchone()
        if not row:return False
        if confirmed and row["email"]:
            blocked=c.execute("SELECT reason FROM suppressions WHERE user_id=? AND email=? COLLATE NOCASE",(user_id,row["email"])).fetchone()
            if blocked: raise ValueError(f"This address is suppressed: {blocked['reason']}")
        c.execute("UPDATE leads SET consent_status=?,updated_at=? WHERE id=? AND user_id=?",("confirmed" if confirmed else "revoked",now,lead_id,user_id))
        if not confirmed and row["email"]: c.execute("INSERT OR REPLACE INTO suppressions VALUES(?,?,?,?)",(user_id,row["email"],"consent revoked",now))
    return True

@tenant_scoped
def mark_replied(user_id: str,lead_id: int) -> bool:
    now=utc_now()
    with transaction(True) as c:return c.execute("UPDATE leads SET replied_at=?,updated_at=? WHERE id=? AND user_id=?",(now,now,lead_id,user_id)).rowcount>0

@tenant_scoped
def mark_contacted(user_id: str,lead_id: int) -> bool:
    now=utc_now()
    with transaction(True) as c:
        if not c.execute("SELECT 1 FROM leads WHERE id=? AND user_id=?",(lead_id,user_id)).fetchone():return False
        c.execute("UPDATE leads SET outreach_attempted_at=COALESCE(outreach_attempted_at,?),contacted_at=COALESCE(contacted_at,?),updated_at=? WHERE id=? AND user_id=?",(now,now,now,lead_id,user_id))
        c.execute("UPDATE outreach_queue SET status='cancelled',error='manually marked contacted' WHERE lead_id=? AND user_id=? AND status IN('draft','queued')",(lead_id,user_id))
        c.execute("INSERT INTO send_logs(user_id,lead_id,status,send_date,timestamp,reason,detail) VALUES(?,?,?,?,?,?,?)",(user_id,lead_id,"manual-contact",now[:10],now,"manually-marked","Marked contacted by dashboard user"))
    return True

def unsubscribe(token: str) -> bool:
    now=utc_now()
    with transaction(True) as c:
        lead=c.execute("SELECT id,user_id,email FROM leads WHERE unsubscribe_token=?",(token,)).fetchone()
        if not lead:return False
        c.execute("UPDATE leads SET consent_status='revoked',updated_at=? WHERE id=? AND user_id=?",(now,lead["id"],lead["user_id"]))
        if lead["email"]:c.execute("INSERT OR REPLACE INTO suppressions VALUES(?,?,?,?)",(lead["user_id"],lead["email"],"one-click unsubscribe",now))
        c.execute("UPDATE outreach_queue SET status='cancelled',error='recipient unsubscribed' WHERE lead_id=? AND user_id=? AND status IN('draft','queued')",(lead["id"],lead["user_id"]))
    return True

def get_setting(key: str) -> str|None:
    with connect() as c:row=c.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
    return row["value"] if row else None

def set_setting(key: str,value: str) -> None:
    with transaction(True) as c:c.execute("INSERT OR REPLACE INTO settings VALUES(?,?)",(key,value))
