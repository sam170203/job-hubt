from datetime import datetime

from job_hunt import db
from job_hunt.models import StagingRaw
from job_hunt.scrapers.base import RawJob, write_to_staging


def test_raw_job_dataclass():
    r = RawJob(source="hn", external_id="x1", payload={"k": "v"})
    assert r.source == "hn"


def test_write_to_staging_inserts(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()

    rows = [
        RawJob(source="hn", external_id="a", payload={"title": "ML"}),
        RawJob(source="hn", external_id="b", payload={"title": "SWE"}),
    ]
    n = write_to_staging(rows, scraped_at=datetime(2026, 5, 26, 9, 0))
    assert n == 2

    with db.session_scope() as s:
        all_rows = s.query(StagingRaw).all()
        assert len(all_rows) == 2
        assert all(r.promoted is False for r in all_rows)


def test_write_to_staging_idempotent_for_unpromoted(tmp_data_dir):
    """Re-scraping the same external_ids while still unpromoted should not duplicate."""
    db.reset_engine_for_testing()
    db.init_db()
    ts = datetime(2026, 5, 26, 9, 0)
    write_to_staging([RawJob("hn", "a", {})], scraped_at=ts)
    n = write_to_staging([RawJob("hn", "a", {})], scraped_at=ts)
    assert n == 0
    with db.session_scope() as s:
        assert s.query(StagingRaw).count() == 1
