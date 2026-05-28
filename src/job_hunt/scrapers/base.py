"""Scraper contract + staging writer.

Scrapers produce RawJob rows and call write_to_staging. They never touch
the `jobs` table directly — the pipeline owns that.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import select

from job_hunt.db import session_scope
from job_hunt.models import StagingRaw


@dataclass(frozen=True)
class RawJob:
    source: str
    external_id: str
    payload: dict[str, Any]


class Scraper(Protocol):
    """All scrapers implement run() returning the rows to stage."""

    source: str

    def run(self) -> list[RawJob]: ...


def write_to_staging(rows: list[RawJob], scraped_at: datetime) -> int:
    """Insert rows into staging_raw, skipping any (source, external_id) that already exist
    AND are still unpromoted. Returns number inserted."""
    if not rows:
        return 0

    inserted = 0
    with session_scope() as s:
        for r in rows:
            existing = s.scalar(
                select(StagingRaw).where(
                    StagingRaw.source == r.source,
                    StagingRaw.external_id == r.external_id,
                    StagingRaw.promoted.is_(False),
                )
            )
            if existing is not None:
                continue
            s.add(
                StagingRaw(
                    source=r.source,
                    external_id=r.external_id,
                    payload=r.payload,
                    scraped_at=scraped_at,
                    promoted=False,
                )
            )
            inserted += 1
    return inserted
