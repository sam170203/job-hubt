"""Hacker News 'Who is hiring' scraper via the Algolia HN API.

Strategy:
1. Algolia search for latest 'Ask HN: Who is hiring' story.
2. Fetch the story's full thread.
3. Each top-level child comment is one job posting — emit one RawJob per comment.

Per-comment parsing into structured (company/title/location/url) happens in
pipeline.normalize, NOT here. This scraper just hands raw text downstream.
"""
from __future__ import annotations

import httpx

from job_hunt.scrapers.base import RawJob

SEARCH_URL = "https://hn.algolia.com/api/v1/search"
ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"


def parse_comment_to_raw(comment: dict) -> RawJob | None:
    text = comment.get("text")
    if not text:
        return None
    return RawJob(
        source="hn",
        external_id=str(comment["id"]),
        payload={
            "text": text,
            "author": comment.get("author"),
            "created_at": comment.get("created_at"),
        },
    )


class HNHiringScraper:
    source = "hn"

    def _latest_thread_id(self) -> str:
        resp = httpx.get(
            SEARCH_URL,
            params={
                "query": "Ask HN: Who is hiring",
                "tags": "story",
                "hitsPerPage": 1,
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        hits = resp.json()["hits"]
        if not hits:
            raise RuntimeError("No HN 'Who is hiring' thread found")
        return hits[0]["objectID"]

    def _fetch_thread(self, story_id: str) -> dict:
        resp = httpx.get(ITEM_URL.format(id=story_id), timeout=30.0)
        resp.raise_for_status()
        return resp.json()

    def run(self) -> list[RawJob]:
        story_id = self._latest_thread_id()
        thread = self._fetch_thread(story_id)
        out: list[RawJob] = []
        for child in thread.get("children", []):
            raw = parse_comment_to_raw(child)
            if raw is not None:
                out.append(raw)
        return out
