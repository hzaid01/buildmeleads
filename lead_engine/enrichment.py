from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

from .config import settings
from .database import connect, init_db, transaction, utc_now


EMAIL_RE = re.compile(r"(?<![\w.+-])([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})(?![\w.-])", re.I)
CONTACT_HINTS = ("contact", "about", "team", "staff", "company")
BLOCKED_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".example")


@dataclass
class EnrichmentResult:
    lead_id: int
    email: str = ""
    email_source: str = ""
    format_valid: bool = False
    mx_valid: bool = False
    error: str = ""


def email_format_valid(email: str) -> bool:
    if not email or len(email) > 254 or not EMAIL_RE.fullmatch(email.strip()):
        return False
    local, domain = email.rsplit("@", 1)
    if len(local) > 64 or domain.startswith("-") or domain.endswith("-"):
        return False
    return not domain.lower().endswith(BLOCKED_SUFFIXES)


def mx_record_valid(email: str) -> bool:
    if not email_format_valid(email):
        return False
    domain = email.rsplit("@", 1)[1].lower()
    try:
        import dns.resolver

        answers = dns.resolver.resolve(domain, "MX", lifetime=6)
        return any(str(answer.exchange).strip(".") for answer in answers)
    except Exception:
        return False


def _public_hostname(hostname: str) -> bool:
    normalized = (hostname or "").strip().lower().rstrip(".")
    if not normalized or normalized in {"localhost", "localhost.localdomain"}:
        return False
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(normalized, None)}
    except socket.gaierror:
        return False
    if not addresses:
        return False
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_multicast, ip.is_reserved, ip.is_unspecified)):
            return False
    return True


def safe_http_url(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError("website is blank")
    if not re.match(r"^https?://", text, re.I):
        text = "https://" + text
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("website URL is not a safe HTTP(S) URL")
    if not _public_hostname(parsed.hostname):
        raise ValueError("website resolves to a non-public address")
    return text


def _fetch_html(url: str) -> tuple[str, str]:
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("httpx is not installed") from exc

    current = safe_http_url(url)
    headers = {"User-Agent": settings.enrichment_user_agent, "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(timeout=settings.website_timeout_seconds, follow_redirects=False, headers=headers) as client:
        for _ in range(5):
            response = client.get(current)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise RuntimeError("redirect response did not include a location")
                current = safe_http_url(urljoin(current, location))
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "html" not in content_type:
                raise RuntimeError("website did not return HTML")
            if len(response.content) > 2_000_000:
                raise RuntimeError("website response exceeded the 2 MB safety limit")
            return response.text, str(response.url)
    raise RuntimeError("website redirected too many times")


def _playwright_html(url: str) -> tuple[str, str]:
    if not settings.enable_playwright:
        raise RuntimeError("Playwright fallback is disabled")
    safe_url = safe_http_url(url)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed") from exc
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(user_agent=settings.enrichment_user_agent)
        page.goto(safe_url, wait_until="domcontentloaded", timeout=settings.website_timeout_seconds * 1000)
        final_url = safe_http_url(page.url)
        html = page.content()
        browser.close()
    return html[:2_000_000], final_url


def _extract_emails(html: str) -> list[str]:
    found = []
    for email in EMAIL_RE.findall(html or ""):
        normalized = email.strip().strip(".,;:()[]<>").lower()
        if email_format_valid(normalized) and normalized not in found:
            found.append(normalized)
    return found


def discover_email(website: str) -> tuple[str, str]:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError("beautifulsoup4 is not installed") from exc

    try:
        html, final_url = _fetch_html(website)
    except Exception as primary_error:
        if not settings.enable_playwright:
            raise RuntimeError(f"website fetch failed: {primary_error}") from primary_error
        try:
            html, final_url = _playwright_html(website)
        except Exception as playwright_error:
            raise RuntimeError(
                f"website fetch failed: {primary_error}; Playwright fallback failed: {playwright_error}"
            ) from playwright_error

    soup = BeautifulSoup(html, "html.parser")
    emails = _extract_emails(html)
    if emails:
        return emails[0], "website-home"

    base_host = urlparse(final_url).hostname
    contact_urls: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "")
        text = (anchor.get_text(" ", strip=True) + " " + href).lower()
        if not any(hint in text for hint in CONTACT_HINTS):
            continue
        candidate = urljoin(final_url, href)
        parsed = urlparse(candidate)
        if parsed.hostname == base_host and candidate not in contact_urls:
            contact_urls.append(candidate)
        if len(contact_urls) >= 3:
            break

    for contact_url in contact_urls:
        try:
            contact_html, _ = _fetch_html(contact_url)
        except Exception:
            continue
        emails = _extract_emails(contact_html)
        if emails:
            return emails[0], "website-contact"
    return "", ""


def enrich_lead(lead: dict[str, Any]) -> EnrichmentResult:
    result = EnrichmentResult(lead_id=int(lead["id"]))
    existing_email = str(lead.get("email") or "").strip().lower()
    if existing_email:
        result.email = existing_email
        result.email_source = str(lead.get("email_source") or "scraper")
    elif lead.get("website"):
        try:
            result.email, result.email_source = discover_email(str(lead["website"]))
        except Exception as exc:
            result.error = str(exc)
    result.format_valid = email_format_valid(result.email)
    result.mx_valid = mx_record_valid(result.email) if result.format_valid else False
    return result


def enrich_batch(limit: int = 25) -> dict[str, Any]:
    init_db()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT l.id,l.name,l.website,l.email,l.email_source
            FROM leads l LEFT JOIN suppressions s ON lower(s.email)=lower(l.email)
            WHERE l.qualified=1 AND l.is_closed=0 AND s.email IS NULL
              AND (l.email_valid=0 OR l.mx_valid=0)
            ORDER BY l.email<>'' DESC,l.review_count DESC LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        ).fetchall()
    results: list[EnrichmentResult] = []
    for row in rows:
        result = enrich_lead(dict(row))
        results.append(result)
        now = utc_now()
        with transaction(immediate=True) as connection:
            connection.execute(
                """
                UPDATE leads SET email=?,email_source=?,email_valid=?,mx_valid=?,updated_at=? WHERE id=?
                """,
                (
                    result.email,
                    result.email_source,
                    1 if result.format_valid else 0,
                    1 if result.mx_valid else 0,
                    now,
                    result.lead_id,
                ),
            )
    return {
        "processed": len(results),
        "valid": len([item for item in results if item.format_valid and item.mx_valid]),
        "results": [item.__dict__ for item in results],
    }
