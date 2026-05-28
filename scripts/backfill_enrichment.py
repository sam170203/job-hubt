"""One-shot backfill of new enrichment columns on existing jobs.

Idempotent — only writes when at least one new column needs updating.
"""

from __future__ import annotations

from sqlalchemy import select

from job_hunt.db import init_db, session_scope
from job_hunt.models import Job
from job_hunt.pipeline.enrich import (
    classify_company_tier,
    classify_work_mode,
    compute_match_score,
    extract_country_and_state,
    load_my_skills,
)


def backfill() -> dict[str, int]:
    init_db()
    my_skills = load_my_skills()
    updated = 0
    untouched = 0
    with session_scope() as s:
        for job in s.scalars(select(Job)).all():
            work_mode = classify_work_mode(job.title, job.jd_text)
            country, state = extract_country_and_state(job.location)
            tier = classify_company_tier(job.company, job.jd_text)
            score = compute_match_score(job.tech_tags, my_skills)
            new_values = {
                "work_mode": work_mode,
                "country": country,
                "india_state": state,
                "company_tier": tier,
                "match_score": score,
            }
            current = {k: getattr(job, k) for k in new_values}
            if current == new_values:
                untouched += 1
                continue
            for k, v in new_values.items():
                setattr(job, k, v)
            updated += 1
    return {"updated": updated, "untouched": untouched}


if __name__ == "__main__":
    result = backfill()
    print(f"Backfill complete: updated={result['updated']}, untouched={result['untouched']}")
