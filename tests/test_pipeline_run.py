from datetime import datetime

from job_hunt import db
from job_hunt.models import Job, StagingRaw
from job_hunt.pipeline.run import run_pipeline
from job_hunt.scrapers.base import RawJob, write_to_staging


def test_pipeline_promotes_new_job(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()

    write_to_staging(
        [RawJob("hn", "100",
                {"text": "Acme | ML Engineer | Remote | <a href='https://acme.io/j'>apply</a>"})],
        scraped_at=datetime(2026, 5, 26),
    )

    stats = run_pipeline()
    assert stats.promoted == 1
    assert stats.duplicates == 0

    with db.session_scope() as s:
        jobs = s.query(Job).all()
        assert len(jobs) == 1
        assert jobs[0].company == "Acme"
        assert jobs[0].role_tag == "ml"
        staging = s.query(StagingRaw).one()
        assert staging.promoted is True


def test_pipeline_skips_duplicates(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()

    with db.session_scope() as s:
        s.add(Job(source="hn", external_id="seed", company="Acme",
                  title="ML Engineer", url="https://acme.io/j",
                  scraped_at=datetime(2026, 5, 25)))

    write_to_staging(
        [RawJob("hn", "200",
                {"text": "Acme | ML Engineer | Remote | <a href='https://acme.io/j'>apply</a>"})],
        scraped_at=datetime(2026, 5, 26),
    )

    stats = run_pipeline()
    assert stats.promoted == 0
    assert stats.duplicates == 1

    with db.session_scope() as s:
        assert s.query(Job).count() == 1
        assert s.query(StagingRaw).one().promoted is True


def test_pipeline_only_handles_unpromoted_rows(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    write_to_staging(
        [RawJob("hn", "300", {"text": "X | Y | Z"})],
        scraped_at=datetime(2026, 5, 26),
    )
    run_pipeline()
    stats2 = run_pipeline()
    assert stats2.promoted == 0
    assert stats2.duplicates == 0
    assert stats2.skipped_unknown_source == 0
