"""All DB read/write helpers used by the Streamlit dashboard.

Keeping these out of app.py means we can unit-test them without spinning up Streamlit.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from job_hunt.db import session_scope
from job_hunt.models import Job

VALID_STATUSES = {
    "new",
    "shortlisted",
    "applied",
    "replied",
    "rejected",
    "ghosted",
    "interviewing",
    "offer",
    "skipped",
}


def get_inbox_jobs(
    role_tags: list[str] | None = None,
    sources: list[str] | None = None,
    seniority_tags: list[str] | None = None,
    within_days: int = 7,
) -> list[Job]:
    cutoff = datetime.utcnow() - timedelta(days=within_days)
    with session_scope() as s:
        stmt = select(Job).where(Job.status == "new", Job.scraped_at >= cutoff)
        if role_tags:
            stmt = stmt.where(Job.role_tag.in_(role_tags))
        if sources:
            stmt = stmt.where(Job.source.in_(sources))
        if seniority_tags:
            stmt = stmt.where(Job.seniority_tag.in_(seniority_tags))
        stmt = stmt.order_by(Job.scraped_at.desc())
        rows = s.scalars(stmt).all()
        for r in rows:
            s.expunge(r)
        return rows


def set_job_status(job_id: int, status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    with session_scope() as s:
        job = s.get(Job, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        job.status = status


def distinct_filter_values() -> dict[str, list[str]]:
    with session_scope() as s:
        sources = sorted({x for (x,) in s.execute(select(Job.source).distinct()) if x})
        role_tags = sorted({x for (x,) in s.execute(select(Job.role_tag).distinct()) if x})
        seniority_tags = sorted(
            {x for (x,) in s.execute(select(Job.seniority_tag).distinct()) if x}
        )
    return {"sources": sources, "role_tags": role_tags, "seniority_tags": seniority_tags}
