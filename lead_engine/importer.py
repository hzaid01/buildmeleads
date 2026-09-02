from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from .database import upsert_leads
from .qualification import count_photos, extract_last_review_at


EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)


def _first_email(value: Any) -> str:
    matches = EMAIL_RE.findall(str(value or ""))
    return matches[0].lower() if matches else ""


def _address_parts(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def csv_row_to_lead(row: dict[str, str], rank: int, filename: str) -> dict[str, Any]:
    complete_address = _address_parts(row.get("complete_address"))
    city = complete_address.get("city") or ""
    state = complete_address.get("state") or ""
    country = complete_address.get("country") or ""
    city_label = ", ".join(part for part in (city, state, country) if part)
    status = str(row.get("status") or "").lower()
    return {
        "placeId": row.get("place_id") or "",
        "cid": row.get("cid") or "",
        "dataId": row.get("data_id") or "",
        "name": row.get("title") or "Unknown Business",
        "niche": row.get("category") or "General",
        "category": row.get("category") or "",
        "city": city_label,
        "timezone": row.get("timezone") or "America/New_York",
        "address": row.get("address") or "",
        "phone": row.get("phone") or "",
        "website": row.get("website") or "",
        "email": _first_email(row.get("emails")),
        "rating": row.get("review_rating") or 0,
        "reviewCount": row.get("review_count") or 0,
        "rank": rank,
        "photoCount": count_photos(row.get("images"), row.get("thumbnail")),
        "lastReviewAt": extract_last_review_at(row.get("user_reviews")),
        "isClosed": "closed" in status,
        "source": "self-hosted (gosom import)",
        "mapsUrl": row.get("link") or "",
        "whatsappVerified": None,
        "importFile": filename,
    }


def import_csv_file(user_id: str, path: Path) -> dict[str, int]:
    leads: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for rank, row in enumerate(reader, start=1):
            leads.append(csv_row_to_lead(row, rank, path.name))
    result = upsert_leads(user_id, leads, source="gosom-csv-import", query=path.name)
    result["files"] = 1
    return result


def import_csv_directory(user_id: str, directory: Path) -> dict[str, int]:
    totals = {"files": 0, "received": 0, "inserted": 0, "updated": 0}
    for path in sorted(directory.glob("*.csv")):
        result = import_csv_file(user_id, path)
        for key in totals:
            totals[key] += result.get(key, 0)
    return totals
