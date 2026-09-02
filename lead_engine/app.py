from __future__ import annotations

import json
import os
import sys
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .auth import AuthError, login, logout, register, session_user
from .config import ROOT_DIR, settings
from .database import analytics, get_campaign_settings, init_db, list_leads, mark_contacted, mark_replied, set_consent, unsubscribe, update_campaign_settings, upsert_leads
from .enrichment import enrich_batch
from .gmail import complete_authorization, create_authorization_url, disconnect_gmail, gmail_status
from .importer import import_csv_directory
from .outreach import approve_batch, generate_batch, list_batches, list_send_logs, process_sendgrid_events, verify_sendgrid_signature

app = FastAPI(title="Lead Scout SaaS Engine", version="2.0.0", docs_url="/docs")


def _process_exists(pid: int) -> bool:
    if pid <= 0: return False
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if handle: kernel32.CloseHandle(handle); return True
        return ctypes.get_last_error() == 5
    try: os.kill(pid, 0); return True
    except ProcessLookupError: return False
    except PermissionError: return True


class AuthRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=1024)
    display_name: str = Field(default="", max_length=100)

class IngestRequest(BaseModel):
    leads: list[dict[str, Any]] = Field(default_factory=list, max_length=5000)
    source: str = "dashboard"
    query: str = ""

class BatchRequest(BaseModel):
    limit: int = Field(default=25, ge=1, le=100)

class ConsentRequest(BaseModel):
    confirmed: bool

class CampaignRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sending_method: str = Field(pattern="^(sendgrid|gmail)$")
    workflow_mode: str = Field(pattern="^(manual|automatic)$")
    automatic_enabled: bool = False
    offer: str = Field(min_length=1, max_length=500)
    cta: str = Field(min_length=1, max_length=500)
    prompt_template: str = Field(min_length=1, max_length=6000)
    groq_model: str = Field(pattern=r"^(openai/gpt-oss-120b|openai/gpt-oss-20b)$")
    daily_cap: int = Field(ge=1, le=10000)
    hourly_cap: int = Field(ge=1, le=1000)
    duplicate_lookback_days: int = Field(ge=1, le=3650)
    bounce_threshold_pct: float = Field(ge=0, le=100)
    complaint_threshold_pct: float = Field(ge=0, le=100)
    circuit_breaker_window: int = Field(ge=10, le=10000)

class OAuthCallbackRequest(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=1, max_length=4096)


def require_engine_token(x_lead_engine_token: str | None = Header(default=None)) -> None:
    if settings.engine_token and x_lead_engine_token != settings.engine_token:
        raise HTTPException(status_code=401, detail="Invalid lead-engine token")

def current_user(x_lead_session_token: str | None = Header(default=None)) -> dict[str, Any]:
    user = session_user(x_lead_session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@app.on_event("startup")
def startup() -> None:
    init_db()
    if not settings.manage_pid_file: return
    path = ROOT_DIR / "data" / "lead_engine.pid"; path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            pid = int(path.read_text(encoding="ascii").strip())
            if pid != os.getpid() and _process_exists(pid): raise RuntimeError(f"Lead engine is already running with PID {pid}")
        except ValueError: pass
    path.write_text(str(os.getpid()), encoding="ascii")

@app.on_event("shutdown")
def shutdown() -> None:
    if not settings.manage_pid_file: return
    path = ROOT_DIR / "data" / "lead_engine.pid"
    try:
        if path.exists() and path.read_text(encoding="ascii").strip() == str(os.getpid()): path.unlink()
    except OSError: pass


@app.get("/health")
def health() -> dict[str, Any]:
    return {"success":True,"service":"lead-engine","database":str(settings.database_path),"groqConfigured":bool(settings.groq_api_key.strip()),
            "gmailOAuthConfigured":bool(settings.google_oauth_client_id.strip() and settings.google_oauth_client_secret.strip() and settings.gmail_token_encryption_key.strip())}

@app.post("/api/auth/register", dependencies=[Depends(require_engine_token)])
def register_route(payload: AuthRequest) -> dict[str, Any]:
    try: token,user=register(payload.email,payload.password,payload.display_name)
    except AuthError as exc: raise HTTPException(status_code=409 if "exists" in str(exc) else 400,detail=str(exc)) from exc
    return {"success":True,"sessionToken":token,"user":user}

@app.post("/api/auth/login", dependencies=[Depends(require_engine_token)])
def login_route(payload: AuthRequest) -> dict[str, Any]:
    try: token,user=login(payload.email,payload.password)
    except AuthError as exc: raise HTTPException(status_code=401,detail=str(exc)) from exc
    return {"success":True,"sessionToken":token,"user":user}

@app.post("/api/auth/logout", dependencies=[Depends(require_engine_token)])
def logout_route(x_lead_session_token: str | None = Header(default=None)) -> dict[str, Any]:
    logout(x_lead_session_token); return {"success":True}

@app.get("/api/auth/me", dependencies=[Depends(require_engine_token)])
def me_route(user: dict[str,Any]=Depends(current_user)) -> dict[str, Any]:
    return {"success":True,"user":user}

@app.post("/api/leads/ingest", dependencies=[Depends(require_engine_token)])
def ingest(payload: IngestRequest,user: dict[str,Any]=Depends(current_user)) -> dict[str, Any]:
    if not payload.leads: raise HTTPException(status_code=400,detail="No leads were provided")
    return {"success":True,**upsert_leads(user["id"],payload.leads,payload.source,payload.query)}

@app.post("/api/leads/import-existing", dependencies=[Depends(require_engine_token)])
def import_existing(user: dict[str,Any]=Depends(current_user)) -> dict[str, Any]:
    return {"success":True,**import_csv_directory(user["id"],ROOT_DIR/"data"/"out")}

@app.get("/api/leads", dependencies=[Depends(require_engine_token)])
def leads(limit:int=Query(250,ge=1,le=1000),offset:int=Query(0,ge=0),qualified_only:bool=False,user:dict[str,Any]=Depends(current_user)) -> dict[str,Any]:
    return {"success":True,**list_leads(user["id"],limit,offset,qualified_only)}

@app.get("/api/analytics", dependencies=[Depends(require_engine_token)])
def analytics_route(user:dict[str,Any]=Depends(current_user)) -> dict[str,Any]: return {"success":True,**analytics(user["id"])}

@app.post("/api/enrich", dependencies=[Depends(require_engine_token)])
async def enrich(payload:BatchRequest,user:dict[str,Any]=Depends(current_user)) -> dict[str,Any]:
    return {"success":True,**await run_in_threadpool(enrich_batch,user["id"],payload.limit)}

@app.post("/api/outreach/generate", dependencies=[Depends(require_engine_token)])
def generate(payload:BatchRequest,user:dict[str,Any]=Depends(current_user)) -> dict[str,Any]: return generate_batch(user["id"],payload.limit)

@app.post("/api/outreach/batches/{batch_id}/approve", dependencies=[Depends(require_engine_token)])
def approve(batch_id:str,user:dict[str,Any]=Depends(current_user)) -> dict[str,Any]:
    try:return approve_batch(user["id"],batch_id)
    except ValueError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc

@app.get("/api/outreach/batches", dependencies=[Depends(require_engine_token)])
def batches(limit:int=Query(20,ge=1,le=100),user:dict[str,Any]=Depends(current_user))->dict[str,Any]:return {"success":True,"batches":list_batches(user["id"],limit)}

@app.get("/api/outreach/logs", dependencies=[Depends(require_engine_token)])
def logs(limit:int=Query(100,ge=1,le=500),user:dict[str,Any]=Depends(current_user))->dict[str,Any]:return {"success":True,"logs":list_send_logs(user["id"],limit)}

@app.post("/api/leads/{lead_id}/reply", dependencies=[Depends(require_engine_token)])
def reply(lead_id:int,user:dict[str,Any]=Depends(current_user))->dict[str,Any]:
    if not mark_replied(user["id"],lead_id):raise HTTPException(status_code=404,detail="Lead not found")
    return {"success":True,"leadId":lead_id}

@app.post("/api/leads/{lead_id}/contacted", dependencies=[Depends(require_engine_token)])
def contacted(lead_id:int,user:dict[str,Any]=Depends(current_user))->dict[str,Any]:
    if not mark_contacted(user["id"],lead_id):raise HTTPException(status_code=404,detail="Lead not found")
    return {"success":True,"leadId":lead_id}

@app.post("/api/leads/{lead_id}/consent", dependencies=[Depends(require_engine_token)])
def consent(lead_id:int,payload:ConsentRequest,user:dict[str,Any]=Depends(current_user))->dict[str,Any]:
    try:updated=set_consent(user["id"],lead_id,payload.confirmed)
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc
    if not updated:raise HTTPException(status_code=404,detail="Lead not found")
    return {"success":True,"leadId":lead_id,"confirmed":payload.confirmed}

@app.get("/api/settings/campaign", dependencies=[Depends(require_engine_token)])
def campaign(user:dict[str,Any]=Depends(current_user))->dict[str,Any]:return {"success":True,**get_campaign_settings(user["id"])}

@app.put("/api/settings/campaign", dependencies=[Depends(require_engine_token)])
def save_campaign(payload:CampaignRequest,user:dict[str,Any]=Depends(current_user))->dict[str,Any]:
    if payload.sending_method=="gmail" and not gmail_status(user["id"])["connected"]:raise HTTPException(status_code=409,detail="Connect Gmail before selecting Gmail")
    try:return {"success":True,**update_campaign_settings(user["id"],payload.model_dump())}
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

@app.get("/api/gmail/status", dependencies=[Depends(require_engine_token)])
def gmail_status_route(user:dict[str,Any]=Depends(current_user))->dict[str,Any]:return {"success":True,**gmail_status(user["id"])}

@app.post("/api/gmail/connect", dependencies=[Depends(require_engine_token)])
def connect_gmail(user:dict[str,Any]=Depends(current_user))->dict[str,Any]:
    try:return {"success":True,"authorizationUrl":create_authorization_url(user["id"])}
    except RuntimeError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc

@app.post("/api/gmail/oauth/callback", dependencies=[Depends(require_engine_token)])
async def gmail_callback(payload:OAuthCallbackRequest,user:dict[str,Any]=Depends(current_user))->dict[str,Any]:
    try:owner=await run_in_threadpool(complete_authorization,payload.code,payload.state)
    except RuntimeError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
    if owner!=user["id"]:raise HTTPException(status_code=403,detail="OAuth state belongs to another user")
    return {"success":True}

@app.post("/api/gmail/disconnect", dependencies=[Depends(require_engine_token)])
def disconnect(user:dict[str,Any]=Depends(current_user))->dict[str,Any]:return {"success":True,"disconnected":disconnect_gmail(user["id"])}

@app.post("/api/webhooks/sendgrid")
async def sendgrid_webhook(request:Request,token:str="",x_twilio_email_event_webhook_signature:str=Header(default=""),x_twilio_email_event_webhook_timestamp:str=Header(default=""))->dict[str,Any]:
    payload=await request.body()
    if settings.sendgrid_webhook_verification_key:
        if not verify_sendgrid_signature(payload,x_twilio_email_event_webhook_signature,x_twilio_email_event_webhook_timestamp):raise HTTPException(status_code=401,detail="Invalid SendGrid signature")
    elif not settings.sendgrid_webhook_token or token!=settings.sendgrid_webhook_token:raise HTTPException(status_code=401,detail="Invalid webhook token")
    try:events=json.loads(payload)
    except json.JSONDecodeError as exc:raise HTTPException(status_code=400,detail="Invalid JSON") from exc
    if not isinstance(events,list):raise HTTPException(status_code=400,detail="Expected event array")
    return {"success":True,**process_sendgrid_events(events)}

@app.api_route("/unsubscribe/{token}",methods=["GET","POST"],response_class=HTMLResponse)
def unsubscribe_route(token:str)->HTMLResponse:
    removed=unsubscribe(token); text="You have been permanently unsubscribed." if removed else "This unsubscribe link is invalid or expired."
    return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><title>Unsubscribe</title></head><body style='font-family:system-ui;max-width:640px;margin:64px auto;padding:20px'><h1>Email preferences</h1><p>{text}</p></body></html>",status_code=200 if removed else 404)
