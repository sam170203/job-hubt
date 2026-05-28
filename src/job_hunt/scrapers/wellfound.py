"""Wellfound (AngelList Talent) scraper.

Strategy:
1. Fetch the public sitemap index at https://wellfound.com/sitemap/jobs/sitemap.xml (or .gz).
2. Pick a sample of job URLs (cap to JOB_FETCH_CAP per run).
3. For each job URL, fetch HTML and parse the application/ld+json JobPosting block.
4. If anti-bot blocks us at any step, log warning and return [].

This is intentionally best-effort. The system functions without Wellfound data.
"""
from __future__ import annotations

import gzip
import json
import logging
import re
import time
from io import BytesIO
from typing import Any

import httpx
from selectolax.parser import HTMLParser

from job_hunt.scrapers.base import RawJob

log = logging.getLogger(__name__)

SITEMAP_INDEX = "https://wellfound.com/sitemap.xml"
USER_AGENT = "Mozilla/5.0 (compatible; job-hunt/0.1; +https://github.com/sam170203/job-hubt)"
REQUEST_TIMEOUT = 30.0
JOB_FETCH_CAP = 30  # don't hammer wellfound; cap per-run
INTER_REQUEST_SLEEP = 1.5


def _http_get(url: str) -> httpx.Response | None:
    try:
        r = httpx.get(
            url,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        )
        r.raise_for_status()
        return r
    except Exception as e:
        log.warning("Wellfound HTTP fetch failed for %s: %s", url, e)
        return None


def _decode_xml(content: bytes, url: str) -> str | None:
    try:
        if url.endswith(".gz"):
            content = gzip.decompress(content)
        return content.decode("utf-8", errors="ignore")
    except Exception as e:
        log.warning("Failed to decode XML at %s: %s", url, e)
        return None


def fetch_sitemap_urls(sitemap_url: str = SITEMAP_INDEX, limit: int = JOB_FETCH_CAP) -> list[str]:
    """Fetch a sitemap and return up to `limit` job URLs.

    Handles both sitemap index files (which list other sitemaps) and direct sitemaps
    (which list page URLs). Recurses one level for index files.
    """
    resp = _http_get(sitemap_url)
    if resp is None:
        return []
    body = _decode_xml(resp.content, sitemap_url)
    if not body:
        return []

    locs = re.findall(r"<loc>([^<]+)</loc>", body)
    if not locs:
        return []

    # If this is a sitemap index (entries point to other sitemap.xml files),
    # follow the first one that mentions "jobs".
    if any(l.endswith(".xml") or l.endswith(".xml.gz") for l in locs):
        for child in locs:
            if "job" in child.lower():
                sub = _http_get(child)
                if sub is None:
                    continue
                sub_body = _decode_xml(sub.content, child)
                if not sub_body:
                    continue
                job_urls = re.findall(r"<loc>([^<]+)</loc>", sub_body)
                return [u for u in job_urls if "/jobs/" in u][:limit]
        return []

    # Direct sitemap of job URLs
    return [u for u in locs if "/jobs/" in u][:limit]


def parse_job_page(html: str, url: str) -> dict[str, Any] | None:
    """Extract JobPosting JSON-LD from a Wellfound job HTML page."""
    tree = HTMLParser(html)
    for node in tree.css('script[type="application/ld+json"]'):
        text = node.text() or ""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        # The JobPosting can be a single object or an array
        candidates = data if isinstance(data, list) else [data]
        for c in candidates:
            if isinstance(c, dict) and c.get("@type") == "JobPosting":
                return c
    return None


def job_ld_to_raw(url: str, ld: dict[str, Any]) -> RawJob:
    external_id = re.sub(r"\W+", "-", url.split("wellfound.com")[-1]).rstrip("-")[:200]
    return RawJob(
        source="wellfound",
        external_id=external_id,
        payload={"url": url, "job_ld": ld},
    )


class WellfoundScraper:
    source = "wellfound"

    def run(self) -> list[RawJob]:
        urls = fetch_sitemap_urls()
        if not urls:
            log.warning("Wellfound sitemap returned no URLs; scraper produced 0 rows.")
            return []

        out: list[RawJob] = []
        for url in urls[:JOB_FETCH_CAP]:
            resp = _http_get(url)
            time.sleep(INTER_REQUEST_SLEEP)
            if resp is None:
                continue
            ld = parse_job_page(resp.text, url)
            if ld is None:
                continue
            out.append(job_ld_to_raw(url, ld))
        return out
