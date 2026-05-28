"""Decide whether a NormalizedJob is a duplicate of any existing Job row."""
from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from job_hunt.models import Job
from job_hunt.pipeline.normalize import NormalizedJob

FUZZY_THRESHOLD = 92


@dataclass(frozen=True)
class DedupeResult:
    is_duplicate: bool
    existing_id: int | None

    @classmethod
    def new(cls) -> "DedupeResult":
        return cls(False, None)

    @classmethod
    def duplicate_of(cls, jid: int) -> "DedupeResult":
        return cls(True, jid)


def _fingerprint(company: str, title: str) -> str:
    return f"{company} {title}".lower().strip()


def find_duplicate(session: Session, candidate: NormalizedJob) -> DedupeResult:
    by_url = session.scalar(select(Job).where(Job.url == candidate.url))
    if by_url is not None:
        return DedupeResult.duplicate_of(by_url.id)

    # For v1 with <10k rows this linear scan is sub-second. Optimize when we hit scale.
    candidate_fp = _fingerprint(candidate.company, candidate.title)
    existing = session.scalars(select(Job)).all()
    for j in existing:
        score = fuzz.token_set_ratio(candidate_fp, _fingerprint(j.company, j.title))
        if score >= FUZZY_THRESHOLD:
            return DedupeResult.duplicate_of(j.id)

    return DedupeResult.new()
