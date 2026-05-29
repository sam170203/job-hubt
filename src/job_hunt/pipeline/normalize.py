"""Normalize staging payloads into a flat, jobs-table-shaped dataclass.

One pure function per source. Adding a source = adding a function here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from selectolax.parser import HTMLParser

HN_FALLBACK_URL = "https://news.ycombinator.com/item?id={id}"
GMAIL_URL_TEMPLATE = "https://mail.google.com/mail/u/0/#inbox/{msg_id}"
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


def normalize_greenhouse_payload(
    external_id: str,
    payload: dict[str, Any],
    scraped_at: datetime,
) -> NormalizedJob:
    company: str = payload.get("company") or "Unknown"
    job: dict[str, Any] = payload.get("job") or {}

    title: str = (job.get("title") or "")[:MAX_TITLE_LEN]
    url: str = job.get("absolute_url") or ""
    content_html: str = job.get("content") or ""
    jd_text: str | None = _strip_html(content_html) or None
    location_obj: dict[str, Any] = job.get("location") or {}
    location: str | None = location_obj.get("name") or None
    posted_at: datetime | None = _parse_created_at(job.get("updated_at"))

    return NormalizedJob(
        source="greenhouse",
        external_id=external_id,
        company=company,
        title=title,
        url=url,
        jd_text=jd_text,
        location=location,
        posted_at=posted_at,
        scraped_at=scraped_at,
    )


def normalize_lever_payload(
    external_id: str,
    payload: dict[str, Any],
    scraped_at: datetime,
) -> NormalizedJob:
    company: str = payload.get("company") or "Unknown"
    posting: dict[str, Any] = payload.get("posting") or {}

    title: str = (posting.get("text") or "")[:MAX_TITLE_LEN]
    url: str = posting.get("hostedUrl") or posting.get("applyUrl") or ""
    description_plain: str | None = posting.get("descriptionPlain")
    if description_plain:
        jd_text: str | None = description_plain or None
    else:
        description_html: str = posting.get("description") or ""
        jd_text = _strip_html(description_html) or None
    categories: dict[str, Any] = posting.get("categories") or {}
    location: str | None = categories.get("location") or None
    created_at_ms = posting.get("createdAt")
    if created_at_ms:
        try:
            posted_at: datetime | None = datetime.fromtimestamp(int(created_at_ms) / 1000)
        except (ValueError, TypeError, OSError):
            posted_at = None
    else:
        posted_at = None

    return NormalizedJob(
        source="lever",
        external_id=external_id,
        company=company,
        title=title,
        url=url,
        jd_text=jd_text,
        location=location,
        posted_at=posted_at,
        scraped_at=scraped_at,
    )


def _build_location_from_address(address: dict[str, Any]) -> str | None:
    parts = [
        address.get("addressLocality"),
        address.get("addressRegion"),
        address.get("addressCountry"),
    ]
    non_empty = [p for p in parts if p]
    return ", ".join(non_empty) if non_empty else None


def normalize_wellfound_payload(
    external_id: str,
    payload: dict[str, Any],
    scraped_at: datetime,
) -> NormalizedJob:
    job_ld: dict[str, Any] = payload.get("job_ld") or {}

    hiring_org: dict[str, Any] = job_ld.get("hiringOrganization") or {}
    company: str = hiring_org.get("name") or "Unknown"
    title: str = (job_ld.get("title") or "")[:MAX_TITLE_LEN]
    url: str = payload.get("url") or ""
    description_html: str = job_ld.get("description") or ""
    jd_text: str | None = _strip_html(description_html) or None

    job_location: dict[str, Any] = job_ld.get("jobLocation") or {}
    address: dict[str, Any] = job_location.get("address") or {}
    location: str | None = _build_location_from_address(address)

    posted_at: datetime | None = _parse_created_at(job_ld.get("datePosted"))

    return NormalizedJob(
        source="wellfound",
        external_id=external_id,
        company=company,
        title=title,
        url=url,
        jd_text=jd_text,
        location=location,
        posted_at=posted_at,
        scraped_at=scraped_at,
    )


def normalize_x_payload(
    external_id: str,
    payload: dict[str, Any],
    scraped_at: datetime,
) -> NormalizedJob:
    author: str = payload.get("author") or "Unknown"
    text: str = payload.get("text") or ""
    url: str = payload.get("url") or ""
    title: str = text[:MAX_TITLE_LEN]
    posted_at: datetime | None = _parse_created_at(payload.get("date"))

    return NormalizedJob(
        source="x",
        external_id=external_id,
        company=author,
        title=title,
        url=url,
        jd_text=text or None,
        location=None,
        posted_at=posted_at,
        scraped_at=scraped_at,
    )


def _domain_label(from_addr: str) -> str:
    """Extract the label before the first dot of the domain.

    e.g. 'recruiter@acme.com' -> 'acme'
    """
    try:
        domain = from_addr.split("@", 1)[1]
        return domain.split(".")[0]
    except (IndexError, AttributeError):
        return from_addr or "Unknown"


def normalize_gmail_payload(
    external_id: str,
    payload: dict[str, Any],
    scraped_at: datetime,
) -> NormalizedJob:
    msg_id: str = payload.get("msg_id") or external_id
    from_addr: str = payload.get("from_addr") or ""
    subject: str = payload.get("subject") or ""
    received_at: str | None = payload.get("received_at")
    body_excerpt: str | None = payload.get("body_excerpt") or None

    company: str = _domain_label(from_addr) if from_addr else "Unknown"
    title: str = subject[:MAX_TITLE_LEN]
    url: str = GMAIL_URL_TEMPLATE.format(msg_id=msg_id)
    posted_at: datetime | None = _parse_created_at(received_at)

    return NormalizedJob(
        source="gmail",
        external_id=external_id,
        company=company,
        title=title,
        url=url,
        jd_text=body_excerpt,
        location=None,
        posted_at=posted_at,
        scraped_at=scraped_at,
    )
