"""Careers-page scraper via public ATS JSON APIs (Greenhouse + Lever).

Reads config/target_companies.yaml, hits each company's ATS public endpoint,
emits one RawJob per job posting. NO auth required — these endpoints are
intentionally public for boards-embed use.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
import yaml

from job_hunt.scrapers.base import RawJob
from job_hunt.settings import PROJECT_ROOT

log = logging.getLogger(__name__)

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
LEVER_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"

REQUEST_TIMEOUT = 30.0
INTER_REQUEST_SLEEP = 1.0  # seconds, conservative — we hit ~25 endpoints


def _load_target_companies() -> list[dict[str, str]]:
    path = PROJECT_ROOT / "config" / "target_companies.yaml"
    data = yaml.safe_load(path.read_text()) or {}
    return list(data.get("companies", []) or [])


def fetch_greenhouse(slug: str) -> list[dict[str, Any]]:
    """Return raw Greenhouse job dicts; empty list on error."""
    url = GREENHOUSE_URL.format(slug=slug)
    try:
        r = httpx.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json().get("jobs", []) or []
    except Exception as e:
        log.warning("Greenhouse fetch failed for slug=%s: %s", slug, e)
        return []


def fetch_lever(slug: str) -> list[dict[str, Any]]:
    """Return raw Lever posting dicts; empty list on error."""
    url = LEVER_URL.format(slug=slug)
    try:
        r = httpx.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json() if isinstance(r.json(), list) else []
    except Exception as e:
        log.warning("Lever fetch failed for slug=%s: %s", slug, e)
        return []


def gh_job_to_raw(company: str, job: dict[str, Any]) -> RawJob:
    job_id = str(job.get("id") or job.get("internal_job_id") or job.get("requisition_id") or "")
    return RawJob(
        source="greenhouse",
        external_id=f"{company}:{job_id}",
        payload={"company": company, "job": job},
    )


def lever_posting_to_raw(company: str, posting: dict[str, Any]) -> RawJob:
    posting_id = str(posting.get("id") or posting.get("lever_id") or "")
    return RawJob(
        source="lever",
        external_id=f"{company}:{posting_id}",
        payload={"company": company, "posting": posting},
    )


class CareersPagesScraper:
    """Iterates target_companies and dispatches to the right ATS fetcher."""

    source = "careers"

    def run(self) -> list[RawJob]:
        out: list[RawJob] = []
        for entry in _load_target_companies():
            name = entry.get("name")
            ats = entry.get("ats")
            slug = entry.get("slug")
            if not name or not ats or not slug:
                continue
            if ats == "greenhouse":
                jobs = fetch_greenhouse(slug)
                out.extend(gh_job_to_raw(name, j) for j in jobs)
            elif ats == "lever":
                postings = fetch_lever(slug)
                out.extend(lever_posting_to_raw(name, p) for p in postings)
            else:
                log.warning("Unknown ATS '%s' for company %s", ats, name)
            time.sleep(INTER_REQUEST_SLEEP)
        return out
