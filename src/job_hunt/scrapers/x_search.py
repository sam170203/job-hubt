"""X (Twitter) scraper via Nitter mirrors.

snscrape is unmaintained and X actively blocks scraping, so we use Nitter — a
public X frontend that exposes search results as plain HTML. Nitter instances
come and go; if they're all down, this scraper returns [] (graceful degrade).

Configure queries in config/x_queries.yaml. The user can add/remove anytime.
"""
from __future__ import annotations

import logging
import re
import time

import httpx
import yaml
from selectolax.parser import HTMLParser

from job_hunt.scrapers.base import RawJob
from job_hunt.settings import PROJECT_ROOT

log = logging.getLogger(__name__)

# Public Nitter instances — community-run, often rotated.
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.cz",
    "https://nitter.kavin.rocks",
]
USER_AGENT = "Mozilla/5.0 (compatible; job-hunt/0.1)"
REQUEST_TIMEOUT = 20.0
INTER_REQUEST_SLEEP = 1.5
MAX_TWEETS_PER_QUERY = 30


def _load_queries() -> list[str]:
    path = PROJECT_ROOT / "config" / "x_queries.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    return list(data.get("queries", []) or [])


def _try_get(url: str) -> httpx.Response | None:
    try:
        r = httpx.get(
            url,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        if r.status_code == 200:
            return r
        log.debug("Nitter %s returned HTTP %s", url, r.status_code)
        return None
    except Exception as e:
        log.debug("Nitter request failed for %s: %s", url, e)
        return None


def _pick_live_instance() -> str | None:
    """Probe Nitter instances; return first one that answers 200."""
    for inst in NITTER_INSTANCES:
        resp = _try_get(inst + "/")
        if resp is not None:
            return inst
    return None


def parse_nitter_search(html: str, query: str) -> list[dict[str, str]]:
    """Extract tweets from a Nitter /search HTML page."""
    tree = HTMLParser(html)
    out = []
    for tw in tree.css(".timeline-item"):
        link_node = tw.css_first("a.tweet-link")
        content_node = tw.css_first(".tweet-content")
        user_node = tw.css_first("a.username")
        date_node = tw.css_first("span.tweet-date a")
        if link_node is None or content_node is None:
            continue
        url_path = link_node.attributes.get("href", "")
        # Extract status ID from path: /username/status/123456...
        m = re.search(r"/status/(\d+)", url_path)
        if not m:
            continue
        out.append({
            "id": m.group(1),
            "url": "https://twitter.com" + url_path.split("#")[0],
            "text": content_node.text(strip=True) if content_node else "",
            "author": user_node.text(strip=True) if user_node else "",
            "date": (date_node.attributes.get("title")
                     if date_node is not None and date_node.attributes else None),
            "query": query,
        })
        if len(out) >= MAX_TWEETS_PER_QUERY:
            break
    return out


def tweet_to_raw(tweet: dict[str, str]) -> RawJob:
    return RawJob(
        source="x",
        external_id=str(tweet["id"]),
        payload=tweet,
    )


class XSearchScraper:
    source = "x"

    def run(self) -> list[RawJob]:
        queries = _load_queries()
        if not queries:
            log.warning("No X queries configured (config/x_queries.yaml); skipping.")
            return []

        instance = _pick_live_instance()
        if instance is None:
            log.warning("No live Nitter instance found; X scraper returning 0 rows.")
            return []

        log.info("Using Nitter instance: %s", instance)
        out: list[RawJob] = []
        seen_ids: set[str] = set()
        for q in queries:
            url = f"{instance}/search?f=tweets&q={httpx.QueryParams({'q': q})['q']}"
            resp = _try_get(url)
            time.sleep(INTER_REQUEST_SLEEP)
            if resp is None:
                continue
            try:
                tweets = parse_nitter_search(resp.text, q)
            except Exception as e:
                log.warning("Nitter parse failed for query %r: %s", q, e)
                continue
            for t in tweets:
                if t["id"] in seen_ids:
                    continue
                seen_ids.add(t["id"])
                out.append(tweet_to_raw(t))
        return out
