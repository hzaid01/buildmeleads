from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .config import ROOT_DIR, settings, validate_live_configuration
from .database import analytics, init_db, list_leads, mark_contacted, mark_replied, set_consent, unsubscribe, upsert_leads
from .enrichment import enrich_batch
from .importer import import_csv_directory
from .outreach import dispatch_due, plan_outreach, process_sendgrid_events, verify_sendgrid_signature, warmup_cap


app = FastAPI(title="Local Lead Scout Engine", version="1.0.0", docs_url="/docs")


def _process_exists(pid: int) -> bool:
    """Return whether a PID exists without sending a signal on Windows."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        process_query_limited_information = 0x1000
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(
            process_query_limited_information, False, pid
        )
        if handle:
            kernel32.CloseHandle(handle)
            return True
        error = ctypes.get_last_error()
        if error == 5:  # Access denied means the process exists but is protected.
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class IngestRequest(BaseModel):
    leads: list[dict[str, Any]] = Field(default_factory=list, max_length=5000)
    source: str = "dashboard"
    query: str = ""


class BatchRequest(BaseModel):
    limit: int = Field(default=25, ge=1, le=100)


class ConsentRequest(BaseModel):
    confirmed: bool


def require_engine_token(x_lead_engine_token: str | None = Header(default=None)) -> None:
    if settings.engine_token and x_lead_engine_token != settings.engine_token:
        raise HTTPException(status_code=401, detail="Invalid lead-engine token")


@app.on_event("startup")
def startup() -> None:
    init_db()
    if not settings.manage_pid_file:
        return
    pid_path = ROOT_DIR / "data" / "lead_engine.pid"
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    if pid_path.exists():
        try:
            existing_pid = int(pid_path.read_text(encoding="ascii").strip())
            if existing_pid != os.getpid() and _process_exists(existing_pid):
                raise RuntimeError(f"Lead engine is already running with PID {existing_pid}")
        except ValueError:
            pass
    pid_path.write_text(str(os.getpid()), encoding="ascii")


@app.on_event("shutdown")
def shutdown() -> None:
    if not settings.manage_pid_file:
        return
    pid_path = ROOT_DIR / "data" / "lead_engine.pid"
    try:
        if pid_path.exists() and pid_path.read_text(encoding="ascii").strip() == str(os.getpid()):
            pid_path.unlink()
    except OSError:
        pass


@app.get("/health")
def health() -> dict[str, Any]:
    live_errors = validate_live_configuration()
    return {
        "success": True,
        "service": "lead-engine",
        "database": str(settings.database_path),
        "dryRun": settings.dry_run or not settings.live_sending_enabled,
        "liveReady": not live_errors,
        "liveBlockers": live_errors,
        "warmup": warmup_cap(),
    }


@app.post("/api/leads/ingest", dependencies=[Depends(require_engine_token)])
def ingest(payload: IngestRequest) -> dict[str, Any]:
    if not payload.leads:
        raise HTTPException(status_code=400, detail="No leads were provided")
    return {"success": True, **upsert_leads(payload.leads, payload.source, payload.query)}


@app.post("/api/leads/import-existing", dependencies=[Depends(require_engine_token)])
def import_existing() -> dict[str, Any]:
    result = import_csv_directory(ROOT_DIR / "data" / "out")
    return {"success": True, **result}


@app.get("/api/leads", dependencies=[Depends(require_engine_token)])
def leads(
    limit: int = Query(default=250, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    qualified_only: bool = Query(default=False),
) -> dict[str, Any]:
    return {"success": True, **list_leads(limit, offset, qualified_only)}


@app.get("/api/analytics", dependencies=[Depends(require_engine_token)])
def get_analytics() -> dict[str, Any]:
    return {"success": True, **analytics()}


@app.post("/api/enrich", dependencies=[Depends(require_engine_token)])
async def enrich(payload: BatchRequest) -> dict[str, Any]:
    result = await run_in_threadpool(enrich_batch, payload.limit)
    return {"success": True, **result}


@app.post("/api/outreach/plan", dependencies=[Depends(require_engine_token)])
def create_outreach_plan() -> dict[str, Any]:
    return plan_outreach()


@app.post("/api/outreach/dispatch", dependencies=[Depends(require_engine_token)])
def run_dispatch() -> dict[str, Any]:
    result = dispatch_due()
    if not result.get("success") and not result.get("dryRun"):
        raise HTTPException(status_code=502, detail=result)
    return result


@app.post("/api/leads/{lead_id}/reply", dependencies=[Depends(require_engine_token)])
def reply(lead_id: int) -> dict[str, Any]:
    if not mark_replied(lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"success": True, "leadId": lead_id}


@app.post("/api/leads/{lead_id}/contacted", dependencies=[Depends(require_engine_token)])
def contacted(lead_id: int) -> dict[str, Any]:
    if not mark_contacted(lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"success": True, "leadId": lead_id}


@app.post("/api/leads/{lead_id}/consent", dependencies=[Depends(require_engine_token)])
def consent(lead_id: int, payload: ConsentRequest) -> dict[str, Any]:
    try:
        updated = set_consent(lead_id, payload.confirmed)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"success": True, "leadId": lead_id, "confirmed": payload.confirmed}


@app.post("/api/webhooks/sendgrid")
async def sendgrid_webhook(
    request: Request,
    token: str = Query(default=""),
    x_twilio_email_event_webhook_signature: str = Header(default=""),
    x_twilio_email_event_webhook_timestamp: str = Header(default=""),
) -> dict[str, Any]:
    payload = await request.body()
    if settings.sendgrid_webhook_verification_key:
        if not verify_sendgrid_signature(
            payload,
            x_twilio_email_event_webhook_signature,
            x_twilio_email_event_webhook_timestamp,
        ):
            raise HTTPException(status_code=401, detail="Invalid SendGrid signature")
    elif not settings.sendgrid_webhook_token or token != settings.sendgrid_webhook_token:
        raise HTTPException(status_code=401, detail="Invalid webhook token")
    try:
        events = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc
    if not isinstance(events, list):
        raise HTTPException(status_code=400, detail="Expected a JSON event array")
    return {"success": True, **process_sendgrid_events(events)}


@app.api_route("/unsubscribe/{token}", methods=["GET", "POST"], response_class=HTMLResponse)
def unsubscribe_route(token: str) -> HTMLResponse:
    removed = unsubscribe(token)
    status = "You have been permanently unsubscribed." if removed else "This unsubscribe link is invalid or expired."
    code = 200 if removed else 404
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'><title>Unsubscribe</title></head>"
        f"<body style='font-family:system-ui;max-width:640px;margin:64px auto;padding:20px'>"
        f"<h1>Email preferences</h1><p>{status}</p></body></html>",
        status_code=code,
    )
