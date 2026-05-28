"""Normalize staging payloads into a flat, jobs-table-shaped dataclass.

One pure function per source. Adding a source = adding a function here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from selectolax.parser import HTMLParser

HN_FALLBACK_URL = "https://news.ycombinator.com/item?id={id}"
MAX_TITLE_LEN = 120


@dataclass
class NormalizedJob:
    source: str
    external_id: str
    company: str
    title: str
    url: str
    jd_text: str | None
    location: str | None
    posted_at: datetime | None
    scraped_at: datetime


def _strip_html(s: str) -> str:
    if "<" not in s:
        return s.strip()
    tree = HTMLParser(s)
    return (tree.text() or "").strip()


def _extract_urls(html: str) -> list[str]:
    tree = HTMLParser(html)
    return [a.attributes.get("href", "") for a in tree.css("a") if a.attributes.get("href")]


def _first_external_url(urls: list[str]) -> str | None:
    for u in urls:
        if u and "news.ycombinator.com" not in u:
            return u
    return None


def _parse_created_at(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_hn_payload(
    external_id: str,
    payload: dict[str, Any],
    scraped_at: datetime,
) -> NormalizedJob:
    text_html = payload.get("text") or ""
    text_plain = _strip_html(text_html)
    urls = _extract_urls(text_html)
    external_url = _first_external_url(urls)

    parts = [p.strip() for p in text_plain.split("|")]
    parts = [p for p in parts if p]

    if len(parts) >= 2:
        company = parts[0][:255]
        title = parts[1][:MAX_TITLE_LEN]
        location = parts[2][:255] if len(parts) >= 3 else None
    else:
        company = f"Unknown (HN comment {external_id})"
        title = (text_plain or "(empty)")[:MAX_TITLE_LEN]
        location = None

    return NormalizedJob(
        source="hn",
        external_id=external_id,
        company=company,
        title=title,
        url=external_url or HN_FALLBACK_URL.format(id=external_id),
        jd_text=text_plain or None,
        location=location,
        posted_at=_parse_created_at(payload.get("created_at")),
        scraped_at=scraped_at,
    )
