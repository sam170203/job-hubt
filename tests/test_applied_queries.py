from datetime import datetime

from job_hunt import db
from job_hunt.dashboard.queries import apply_to_job, list_applied_jobs
from job_hunt.models import Job


def _seed(s, **kw):
    defaults = dict(
        source="hn", company="A", title="T", url="u", scraped_at=datetime.utcnow(), status="new"
    )
    defaults.update(kw)
    j = Job(**defaults)
    s.add(j)
    s.flush()
    return j


def test_list_applied_excludes_unapplied(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        _seed(s, external_id="1", url="u1")
        j = _seed(s, external_id="2", url="u2")
        jid = j.id
    apply_to_job(jid, resume_variant="ai-ml", channel="direct")
    rows = list_applied_jobs()
    assert len(rows) == 1
    assert rows[0].external_id == "2"
