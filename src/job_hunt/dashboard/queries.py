"""All DB read/write helpers used by the Streamlit dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update

from job_hunt.db import session_scope
from job_hunt.models import Application, CompanyBlocklist, Job, SavedView

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
    work_modes: list[str] | None = None,
    countries: list[str] | None = None,
    india_states: list[str] | None = None,
    company_tiers: list[str] | None = None,
    required_skills: list[str] | None = None,
    min_match_score: float | None = None,
    within_days: int = 7,
) -> list[Job]:
    cutoff = datetime.utcnow() - timedelta(days=within_days)
    with session_scope() as s:
        stmt = select(Job).where(
            Job.status == "new",
            Job.scraped_at >= cutoff,
            Job.hidden.is_(False),
        )
        if role_tags:
            stmt = stmt.where(Job.role_tag.in_(role_tags))
        if sources:
            stmt = stmt.where(Job.source.in_(sources))
        if seniority_tags:
            stmt = stmt.where(Job.seniority_tag.in_(seniority_tags))
        if work_modes:
            stmt = stmt.where(Job.work_mode.in_(work_modes))
        if countries:
            stmt = stmt.where(Job.country.in_(countries))
        if india_states:
            stmt = stmt.where(Job.india_state.in_(india_states))
        if company_tiers:
            stmt = stmt.where(Job.company_tier.in_(company_tiers))
        if min_match_score is not None:
            stmt = stmt.where(Job.match_score >= min_match_score)
        stmt = stmt.order_by(Job.match_score.desc().nullslast(), Job.scraped_at.desc())
        rows = s.scalars(stmt).all()
        # Skills filter is in-Python because tech_tags is JSON
        if required_skills:
            req = {r.lower() for r in required_skills}
            rows = [r for r in rows if r.tech_tags and (req & {t.lower() for t in r.tech_tags})]
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


def apply_to_job(
    job_id: int,
    resume_variant: str | None,
    channel: str | None,
    note: str | None = None,
) -> int:
    """Create an Application row + flip job status to 'applied'. Returns application id."""
    with session_scope() as s:
        job = s.get(Job, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        app = Application(
            job_id=job_id,
            applied_at=datetime.utcnow(),
            resume_variant=resume_variant,
            channel=channel,
            cover_note_path=note,
        )
        s.add(app)
        s.flush()
        job.status = "applied"
        return app.id


def list_applied_jobs() -> list[Job]:
    with session_scope() as s:
        rows = s.scalars(
            select(Job)
            .where(
                Job.status.in_(
                    ["applied", "replied", "interviewing", "rejected", "ghosted", "offer"]
                )
            )
            .order_by(Job.id.desc())
        ).all()
        for r in rows:
            _ = r.applications  # eagerly hydrate to avoid detached access
            s.expunge(r)
        return rows


def blocklist_company(company_name: str, reason: str | None = None) -> None:
    with session_scope() as s:
        existing = s.scalar(
            select(CompanyBlocklist).where(CompanyBlocklist.company_name == company_name)
        )
        if existing is None:
            s.add(
                CompanyBlocklist(
                    company_name=company_name,
                    reason=reason,
                    created_at=datetime.utcnow(),
                )
            )
        s.execute(update(Job).where(Job.company == company_name).values(hidden=True))


def list_blocklist() -> list[CompanyBlocklist]:
    with session_scope() as s:
        rows = s.scalars(select(CompanyBlocklist).order_by(CompanyBlocklist.id.desc())).all()
        for r in rows:
            s.expunge(r)
        return rows


def save_view(name: str, filters: dict[str, Any]) -> None:
    with session_scope() as s:
        existing = s.scalar(select(SavedView).where(SavedView.name == name))
        if existing is not None:
            existing.filters_json = filters
        else:
            s.add(SavedView(name=name, filters_json=filters, created_at=datetime.utcnow()))


def list_saved_views() -> list[SavedView]:
    with session_scope() as s:
        rows = s.scalars(select(SavedView).order_by(SavedView.id.desc())).all()
        for r in rows:
            s.expunge(r)
        return rows


def distinct_filter_values() -> dict[str, list[str]]:
    with session_scope() as s:

        def _d(col):
            return sorted({x for (x,) in s.execute(select(col).distinct()) if x})

        return {
            "sources": _d(Job.source),
            "role_tags": _d(Job.role_tag),
            "seniority_tags": _d(Job.seniority_tag),
            "work_modes": _d(Job.work_mode),
            "countries": _d(Job.country),
            "india_states": _d(Job.india_state),
            "company_tiers": _d(Job.company_tier),
        }
