"""Pipeline orchestrator: promote unpromoted staging rows into the `jobs` table."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select

from job_hunt.db import session_scope
from job_hunt.models import Job, StagingRaw
from job_hunt.pipeline.dedupe import find_duplicate
from job_hunt.pipeline.enrich import (
    classify_company_tier,
    classify_work_mode,
    compute_match_score,
    enrich_tags,
    extract_country_and_state,
    load_my_skills,
)
from job_hunt.pipeline.normalize import (
    NormalizedJob,
    normalize_gmail_payload,
    normalize_greenhouse_payload,
    normalize_hn_payload,
    normalize_lever_payload,
    normalize_wellfound_payload,
    normalize_x_payload,
)

log = logging.getLogger(__name__)

# Add new sources here as they're built (Plan 2).
NORMALIZERS: dict[str, Callable[..., NormalizedJob]] = {
    "hn": normalize_hn_payload,
    "greenhouse": normalize_greenhouse_payload,
    "lever": normalize_lever_payload,
    "wellfound": normalize_wellfound_payload,
    "x": normalize_x_payload,
    "gmail": normalize_gmail_payload,
}


@dataclass
class PipelineStats:
    promoted: int = 0
    duplicates: int = 0
    skipped_unknown_source: int = 0


def run_pipeline() -> PipelineStats:
    stats = PipelineStats()
    with session_scope() as s:
        staging_rows = s.scalars(select(StagingRaw).where(StagingRaw.promoted.is_(False))).all()

        for sr in staging_rows:
            normalizer = NORMALIZERS.get(sr.source)
            if normalizer is None:
                log.warning("No normalizer for source=%s; skipping staging.id=%s", sr.source, sr.id)
                stats.skipped_unknown_source += 1
                continue

            norm = normalizer(
                external_id=sr.external_id,
                payload=sr.payload,
                scraped_at=sr.scraped_at,
            )

            dup = find_duplicate(s, norm)
            if dup.is_duplicate:
                stats.duplicates += 1
            else:
                tags = enrich_tags(title=norm.title, jd_text=norm.jd_text)
                my_skills = load_my_skills()
                work_mode = classify_work_mode(norm.title, norm.jd_text)
                country, india_state = extract_country_and_state(norm.location)
                company_tier = classify_company_tier(norm.company, norm.jd_text)
                match_score = compute_match_score(tags.tech_tags, my_skills)
                job = Job(
                    source=norm.source,
                    external_id=norm.external_id,
                    company=norm.company,
                    title=norm.title,
                    url=norm.url,
                    jd_text=norm.jd_text,
                    location=norm.location,
                    posted_at=norm.posted_at,
                    scraped_at=norm.scraped_at,
                    role_tag=tags.role_tag,
                    seniority_tag=tags.seniority_tag,
                    tech_tags=tags.tech_tags or None,
                    work_mode=work_mode,
                    country=country,
                    india_state=india_state,
                    company_tier=company_tier,
                    match_score=match_score,
                )
                s.add(job)
                stats.promoted += 1

            sr.promoted = True

    return stats
