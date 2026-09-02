from __future__ import annotations

import json
import random
import re
import time
from typing import Any

import httpx

from .config import settings
from .qualification import issue_summary

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
ALLOWED_MODELS = {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}


def _render_prompt(template: str, context: dict[str, str]) -> str:
    rendered = template
    for key, value in context.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    unresolved = re.findall(r"{{\s*[^{}]+\s*}}", rendered)
    if unresolved:
        raise RuntimeError("Campaign prompt has unresolved fields: " + ", ".join(sorted(set(unresolved))))
    return rendered


def generate_email_text(lead: dict[str, Any], campaign: dict[str, Any], attempts: int = 4) -> str:
    if not settings.groq_api_key.strip():
        raise RuntimeError("GROQ_API_KEY is required to generate outreach emails")
    context = {
        "business_name": str(lead.get("name") or "").strip(),
        "city": str(lead.get("city") or "").strip(),
        "weaknesses": issue_summary(lead.get("weaknesses_json")) or "an opportunity to strengthen the profile",
        "offer": str(campaign.get("offer") or "").strip(),
        "cta": str(campaign.get("cta") or "").strip(),
    }
    if not context["business_name"] or not context["offer"] or not context["cta"]:
        raise RuntimeError("Required personalization data is empty")
    prompt = _render_prompt(str(campaign.get("prompt_template") or ""), context)
    model = str(campaign.get("groq_model") or settings.groq_model)
    if model not in ALLOWED_MODELS:
        raise RuntimeError("Campaign uses an unsupported Groq model")
    payload = {
        "model": model,
        "temperature": 0.55,
        "reasoning_effort": "low",
        "max_completion_tokens": 300,
        "messages": [
            {"role": "system", "content": "Return only the requested short outreach copy. Never add a subject, greeting, signature, or footer."},
            {"role": "user", "content": prompt + "\n\nStructured source data:\n" + json.dumps(context, ensure_ascii=False)},
        ],
    }
    last_error = "unknown error"
    for attempt in range(max(1, attempts)):
        try:
            response = httpx.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            if response.status_code == 429 or response.status_code >= 500:
                last_error = f"HTTP {response.status_code}"
                if attempt + 1 < attempts:
                    retry_after = response.headers.get("retry-after")
                    try:
                        delay = min(30.0, max(0.25, float(retry_after))) if retry_after else min(8.0, 2**attempt + random.random())
                    except ValueError:
                        delay = min(8.0, 2**attempt + random.random())
                    time.sleep(delay)
                    continue
            response.raise_for_status()
            data = response.json()
            cleaned = re.sub(r"\s+", " ", str(data["choices"][0]["message"]["content"] or "")).strip().strip('"')
            if not cleaned:
                raise RuntimeError("Groq returned an empty email")
            if len(cleaned) > 700:
                raise RuntimeError("Groq returned copy longer than the review limit")
            if re.search(r"{{\s*[^{}]+\s*}}", cleaned):
                raise RuntimeError("Groq returned unresolved template fields")
            return cleaned
        except RuntimeError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            last_error = str(exc)
            if attempt + 1 >= attempts:
                break
    raise RuntimeError(f"Groq email generation failed after {attempts} attempts: {last_error}")
