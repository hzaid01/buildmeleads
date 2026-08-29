from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any


WEAKNESS_LABELS = {
    "no_website": "has no website listed",
    "stale_reviews": "has not received a recent review in 6+ months",
    "missing_photos": "has no profile photos detected",
    "incomplete_category": "has an incomplete business category",
    "low_rating": "has a rating below 4.0",
    "few_reviews": "has fewer than 10 reviews",
}


def _number(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        try:
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.isdigit():
            return parse_datetime(int(text))
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
            else:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def extract_last_review_at(raw_reviews: Any) -> str | None:
    if not raw_reviews:
        return None
    value = raw_reviews
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            candidates = re.findall(r"20\d{2}-\d{2}-\d{2}(?:[T ][^\"']+)?", value)
            parsed = [parse_datetime(item) for item in candidates]
            parsed = [item for item in parsed if item]
            return max(parsed).isoformat() if parsed else None
    if isinstance(value, dict):
        value = value.get("reviews") or value.get("items") or [value]
    if not isinstance(value, list):
        return None
    dates: list[datetime] = []
    for review in value:
        if not isinstance(review, dict):
            continue
        for key in ("publishedAtDate", "published_at", "date", "timestamp", "time", "reviewDate"):
            parsed = parse_datetime(review.get(key))
            if parsed:
                dates.append(parsed)
                break
    return max(dates).isoformat() if dates else None


def count_photos(images: Any, thumbnail: Any = "") -> int:
    count = 0
    value = images
    if isinstance(value, str) and value.strip():
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [part for part in re.split(r"[,;\n]", value) if part.strip()]
    if isinstance(value, dict):
        value = value.get("images") or value.get("items") or list(value.values())
    if isinstance(value, list):
        count = len([item for item in value if item])
    elif value:
        count = 1
    if count == 0 and thumbnail:
        count = 1
    return count


def detect_weaknesses(lead: dict[str, Any], now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    weaknesses: list[str] = []
    website = str(lead.get("website") or lead.get("url") or "").strip()
    if not website:
        weaknesses.append("no_website")

    rating = _number(lead.get("rating"), 0)
    if rating < 4.0:
        weaknesses.append("low_rating")

    review_count = int(_number(lead.get("reviewCount", lead.get("review_count", 0)), 0))
    if review_count < 10:
        weaknesses.append("few_reviews")

    category = str(lead.get("category") or lead.get("niche") or "").strip().lower()
    if category in {"", "general", "business", "establishment", "unknown"}:
        weaknesses.append("incomplete_category")

    photo_count = int(_number(lead.get("photoCount", lead.get("photo_count", 0)), 0))
    if photo_count <= 0:
        weaknesses.append("missing_photos")

    last_review = parse_datetime(lead.get("lastReviewAt", lead.get("last_review_at")))
    if last_review and last_review < now - timedelta(days=183):
        weaknesses.append("stale_reviews")

    return list(dict.fromkeys(weaknesses))


def is_qualified(lead: dict[str, Any], weaknesses: list[str] | None = None) -> bool:
    weaknesses = weaknesses if weaknesses is not None else detect_weaknesses(lead)
    return bool(weaknesses)


def issue_summary(weaknesses: list[str] | str | None) -> str:
    if isinstance(weaknesses, str):
        try:
            weaknesses = json.loads(weaknesses)
        except json.JSONDecodeError:
            weaknesses = [weaknesses]
    weaknesses = weaknesses or []
    labels = [WEAKNESS_LABELS.get(code, code.replace("_", " ")) for code in weaknesses]
    return "; ".join(labels)


def primary_issue(weaknesses: list[str] | str | None) -> str:
    if isinstance(weaknesses, str):
        try:
            weaknesses = json.loads(weaknesses)
        except json.JSONDecodeError:
            weaknesses = [weaknesses]
    weaknesses = weaknesses or []
    if not weaknesses:
        return "could be strengthened"
    return WEAKNESS_LABELS.get(weaknesses[0], weaknesses[0].replace("_", " "))
