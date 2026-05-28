from datetime import datetime, timedelta

import pytest

from job_hunt import db
from job_hunt.dashboard.queries import (
    distinct_filter_values,
    get_inbox_jobs,
    set_job_status,
)
from job_hunt.models import Job


def _seed(s, **kw):
    defaults = dict(source="hn", company="A", title="T", url="u",
                    scraped_at=datetime.utcnow(), status="new")
    defaults.update(kw)
    j = Job(**defaults)
    s.add(j)
    s.flush()
    return j


def test_inbox_returns_only_new(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        _seed(s, external_id="1", status="new", url="u1")
        _seed(s, external_id="2", status="shortlisted", url="u2")
        _seed(s, external_id="3", status="skipped", url="u3")

    rows = get_inbox_jobs()
    assert len(rows) == 1
    assert rows[0].status == "new"


def test_inbox_filter_by_role_tag(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        _seed(s, external_id="1", role_tag="ml", url="u1")
        _seed(s, external_id="2", role_tag="frontend", url="u2")

    rows = get_inbox_jobs(role_tags=["ml"])
    assert len(rows) == 1
    assert rows[0].role_tag == "ml"


def test_inbox_filter_by_age_days(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    old = datetime.utcnow() - timedelta(days=30)
    recent = datetime.utcnow() - timedelta(days=1)
    with db.session_scope() as s:
        _seed(s, external_id="1", url="u1", scraped_at=old)
        _seed(s, external_id="2", url="u2", scraped_at=recent)

    rows = get_inbox_jobs(within_days=7)
    assert len(rows) == 1
    assert rows[0].external_id == "2"


def test_set_job_status_updates(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        j = _seed(s, external_id="1", url="u1")
        jid = j.id

    set_job_status(jid, "shortlisted")
    with db.session_scope() as s:
        assert s.get(Job, jid).status == "shortlisted"


def test_set_job_status_rejects_invalid(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with pytest.raises(ValueError):
        set_job_status(1, "bogus_status")


def test_distinct_filter_values(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        _seed(s, external_id="1", url="u1", role_tag="ml", source="hn")
        _seed(s, external_id="2", url="u2", role_tag="frontend", source="hn")
        _seed(s, external_id="3", url="u3", role_tag="ml", source="wellfound")

    vals = distinct_filter_values()
    assert set(vals["sources"]) == {"hn", "wellfound"}
    assert set(vals["role_tags"]) == {"ml", "frontend"}
